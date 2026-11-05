"""
Comitato di lungo periodo: la societa' valuta OGNI rata della quota AI prima che GERVA-Q la compri.

Chi decide cosa:
  * il CALENDARIO (config.py di GERVA-Q): quanto si puo' comprare al massimo a una data (1/3, 2/3, 3/3 della quota);
  * il COMITATO (questo modulo), titolo per titolo, se la rata matura si compra o si rinvia:
      1. controlli deterministici (sotto): dati freschi, liquidita', volatilita', nessun crollo appena avvenuto,
         nessuna sospensione decisa da Andrea in config/longterm.yaml;
      2. riunione degli agenti, solo se sono agenti veri (chiave API presente): puo' soltanto RINVIARE una rata,
         mai far comprare un titolo che il codice ha scartato (opzioni "rinvia" / "compra", pareggio = rinvia).
  * GERVA-Q esegue il piano solo dentro i suoi limiti: i 19 titoli di config.py, mai oltre il calendario, mai
    vendite fuori dal ribilanciamento annuale. Senza un piano fresco (meno di 7 giorni) non compra nulla di nuovo.

Perche' niente regole di "tempismo" (es. comprare solo sopra la media a 200 giorni): la societa' le ha provate
(research/aziende/entry_rule.py, 1.681 rate dal 2016): aspettare rendeva in media lo 0,75% in meno a 24 mesi,
P(meglio) = 0,05. Il test e' distorto a favore del comprare (titoli scelti col senno di poi), ma nessun dato dice
che aspettare aiuti: si compra alle date, se i controlli passano.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os

import numpy as np
import pandas as pd
import yaml

from . import audit, db, events, paths

PLAN_NAME = "longterm_plan.json"
START = dt.date(2026, 11, 9)          # come LONGTERM_START in config.py di GERVA-Q (patch v3.2)
TRANCHES = 3
MIN_DOLLAR_VOLUME = 20e6              # mediana a 20 giorni degli scambi in dollari
MAX_VOL = 1.50                        # volatilita' annua a 60 giorni
MAX_RECENT_DROP = -0.20               # un giorno peggiore di -20% negli ultimi 5: si aspetta che la notizia si chiarisca
MAX_STALE_DAYS = 5


def plan_path() -> str:
    return os.path.join(paths.VAR, PLAN_NAME)


def config() -> dict:
    return yaml.safe_load(open(os.path.join(paths.CONFIG, "longterm.yaml")))


def symbols(cfg: dict | None = None) -> list[str]:
    cfg = cfg or config()
    return list(cfg["titoli"]) + list(cfg.get("esplorativo", {}).get("titoli", {}))


def calendar_fraction(today: dt.date) -> float:
    if today < START:
        return 0.0
    months = (today.year - START.year) * 12 + today.month - START.month - (1 if today.day < START.day else 0)
    return min(months + 1, TRANCHES) / TRANCHES


def checks(sym: str, close: pd.Series, volume: pd.Series | None, today: dt.date, suspended: set[str]) -> list[str]:
    """Motivi per RINVIARE la rata di questo titolo (lista vuota = via libera)."""
    why = []
    if sym in suspended:
        why.append("sospeso da Andrea in config/longterm.yaml")
    c = close.dropna()
    if len(c) < 60:
        return why + ["storico insufficiente (meno di 60 giorni)"]
    age = (today - c.index[-1].date()).days
    if age > MAX_STALE_DAYS:
        why.append(f"ultimo prezzo vecchio di {age} giorni")
    r = c.pct_change().dropna()
    vol = float(r.tail(60).std() * math.sqrt(252))
    if vol > MAX_VOL:
        why.append(f"volatilita' {vol:.0%} oltre il {MAX_VOL:.0%}")
    if float(r.tail(5).min()) <= MAX_RECENT_DROP:
        why.append(f"crollo di {float(r.tail(5).min()):.0%} negli ultimi 5 giorni: si aspetta la notizia")
    if volume is not None:
        dv = float((c * volume.reindex(c.index)).tail(20).median())
        if not np.isfinite(dv) or dv < MIN_DOLLAR_VOLUME:
            why.append(f"scambi troppo bassi ({dv / 1e6:,.0f} milioni di dollari al giorno)")
    return why


def _agents_vote(cand: list[str], data: dict) -> dict:
    """Riunione degli agenti VERI sulla rata: puo' solo rinviare. Con agenti simulati si salta (decide il codice)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return dict(tenuta=False, decisione="compra", motivo="agenti simulati: decide il codice")
    from . import meetings
    res = meetings.hold("lungo", f"Rata della quota di lungo periodo: {len(cand)} titoli",
                        "il calendario apre una nuova rata e i controlli del codice sono passati",
                        ["capo", "cro", "head_research"], data=data, context=dict(titoli=cand, prezzi=data.get("prezzi")))
    if not res.get("ok"):
        return dict(tenuta=False, decisione="compra", motivo=res.get("motivo", "riunione non tenuta"))
    return dict(tenuta=True, decisione=res["decisione"], riunione=res["id"])


def evaluate(close: pd.DataFrame, volume: pd.DataFrame | None, today: dt.date | None = None,
             write: bool = True) -> dict:
    today = today or dt.date.today()
    cfg = config()
    syms = symbols(cfg)
    suspended = set(cfg.get("sospesi", []) or [])
    cal = calendar_fraction(today)
    prev = {}
    if os.path.exists(plan_path()):
        try:
            prev = json.load(open(plan_path())).get("frazioni", {})
        except (OSError, ValueError):
            prev = {}
    frac, why, cand = {}, {}, []
    for s in syms:
        old = float(prev.get(s, 0.0))
        if cal <= old:                              # niente di nuovo da decidere per questo titolo
            frac[s] = old
            continue
        w = checks(s, close[s] if s in close else pd.Series(dtype=float),
                   volume[s] if volume is not None and s in volume else None, today, suspended)
        if w:
            frac[s], why[s] = old, w                # rinviata: resta la rata gia' comprata
        else:
            frac[s] = cal
            cand.append(s)
    vote = dict(tenuta=False, decisione="compra", motivo="nessuna rata nuova")
    if cand:
        last = {s: float(close[s].dropna().iloc[-1]) for s in cand}
        vote = _agents_vote(cand, dict(titoli=cand, prezzi=last, calendario=cal,
                                       controlli="passati", nota="puoi solo rinviare la rata, non cambiare i titoli"))
        if vote["decisione"] == "rinvia":
            for s in cand:
                frac[s] = float(prev.get(s, 0.0))
                why[s] = [f"rinviata dalla riunione degli agenti #{vote.get('riunione')}"]
    plan = dict(data=today.isoformat(), calendario=cal, frazioni=frac, rinvii=why, riunione=vote,
                regole=dict(min_scambi_usd=MIN_DOLLAR_VOLUME, max_vol=MAX_VOL, max_crollo_5g=MAX_RECENT_DROP))
    if write:
        tmp = plan_path() + ".tmp"
        with open(tmp, "w") as f:
            json.dump(plan, f, indent=1)
        os.replace(tmp, plan_path())
        db.runtime_set("lt.plan", plan)
        db.runtime_set("lt.prezzi", {s: float(close[s].dropna().iloc[-1]) for s in syms if s in close and close[s].notna().any()})
        audit.log("comitato_lungo", "longterm.plan", dict(calendario=cal, approvati=len([s for s in syms if frac[s] >= cal > 0]),
                                                          rinviati=sorted(why)))
        events.publish("longterm.plan", "comitato_lungo",
                       dict(calendario=cal, approvati=[s for s in cand if frac[s] >= cal], rinviati=sorted(why)))
    return plan


def run(today: dt.date | None = None) -> dict:
    """Scarica un anno di prezzi e volumi dei 19 titoli e valuta. Senza rete: nessun piano nuovo (GERVA-Q non compra)."""
    import yfinance as yf
    syms = symbols()
    raw = yf.download(syms, period="1y", auto_adjust=True, progress=False, group_by="column")
    return evaluate(raw["Close"], raw["Volume"], today)
