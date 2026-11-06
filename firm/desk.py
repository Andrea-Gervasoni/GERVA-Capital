"""
Desk di trading: i capi desk (gli ex capi pod) propongono posizioni LONG per il conto reale (paper) di Andrea.

Chi fa cosa, in una riga: gli agenti PROPONGONO, il codice VALIDA e scrive var/firm_overlay.json, GERVA-Q ESEGUE.
Sul conto scrive ordini un solo programma (GERVA-Q): se ne scrivessero due, GERVA-Q venderebbe la sera stessa tutto
cio' che non e' nel suo target (e' successo con AAPL, MSFT e CRM il 5/11).

Il codice controlla (gli agenti non possono aggirarlo):
  * solo simboli presenti nella tabella dati che gli agenti ricevono (azioni USA liquide + titoli del lungo periodo);
  * peso massimo per titolo e totale massimo del desk (impostazioni desk.* che cambia Andrea);
  * un titolo proposto da piu' desk si somma, ma resta sotto il tetto per titolo;
  * il totale di tutti i desk scala in proporzione se supera il tetto complessivo.
GERVA-Q rifa' gli stessi controlli con i suoi limiti e ignora un file piu' vecchio di 3 giorni.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os

import numpy as np
import pandas as pd

from . import audit, db, events, paths, registry
from . import settings as S

OVERLAY_NAME = "firm_overlay.json"
DESKS = ["pod_trend", "pod_reversal", "pod_crypto"]          # i tre capi desk
MAX_PROPOSALS = 5


def overlay_path() -> str:
    return os.path.join(paths.VAR, OVERLAY_NAME)


def universe() -> list[str]:
    from quantlab import gervaq4 as G4
    from . import lt_committee
    syms = set(G4.STOCKS) | set(lt_committee.symbols())
    return sorted(s for s in syms if s.isalnum() and s.isupper())


def table(close: pd.DataFrame | None = None, syms: list[str] | None = None) -> list[dict]:
    """Tabella dati reale (da codice): rendimenti, volatilita' e distanza dalla media a 200 giorni."""
    if close is None:
        f = os.path.join(paths.VAR, "data", "gq4_close.pkl")
        if not os.path.exists(f):
            return []
        close = pd.read_pickle(f)
    syms = syms or universe()
    rows = []
    for s in syms:
        if s not in close:
            continue
        c = close[s].dropna()
        if len(c) < 252:
            continue
        r = c.pct_change().dropna()
        rows.append(dict(simbolo=s, r1m=round(float(c.iloc[-1] / c.iloc[-22] - 1), 3),
                         r3m=round(float(c.iloc[-1] / c.iloc[-64] - 1), 3),
                         r12m=round(float(c.iloc[-1] / c.iloc[-253] - 1), 3),
                         vol=round(float(r.tail(60).std() * math.sqrt(252)), 2),
                         vs_media200=round(float(c.iloc[-1] / c.tail(200).mean() - 1), 3)))
    return rows


def caps() -> dict:
    return dict(max_name=float(S.get("desk.max_name_frac", 0.05)), max_total=float(S.get("desk.max_total_frac", 0.30)))


def merge(by_desk: dict[str, list[dict]], allowed: set[str], c: dict | None = None) -> dict:
    """Valida e unisce le proposte dei desk. Ritorna dict(targets={simbolo: frazione del NAV}, per_desk, scartate)."""
    c = c or caps()
    n = max(len(by_desk), 1)
    desk_total = c["max_total"] / n
    targets: dict[str, float] = {}
    per_desk, scartate = {}, []
    for desk, props in by_desk.items():
        mine: dict[str, float] = {}
        for p in props or []:
            sym = str(p.get("simbolo", "")).upper().strip()
            try:
                w = float(p.get("peso_pct", 0)) / 100.0
            except (TypeError, ValueError):
                w = 0.0
            if sym not in allowed:
                scartate.append(dict(desk=desk, simbolo=sym, motivo="fuori dalla tabella"))
                continue
            if not (w > 0 and math.isfinite(w)):
                scartate.append(dict(desk=desk, simbolo=sym, motivo="peso non valido"))
                continue
            mine[sym] = min(mine.get(sym, 0.0) + w, c["max_name"])
        tot = sum(mine.values())
        if tot > desk_total > 0:                                   # tetto del desk: si scala in proporzione
            mine = {k: v * desk_total / tot for k, v in mine.items()}
        per_desk[desk] = {k: round(v, 4) for k, v in mine.items()}
        for k, v in mine.items():
            targets[k] = min(targets.get(k, 0.0) + v, c["max_name"])
    tot = sum(targets.values())
    if tot > c["max_total"] > 0:
        targets = {k: v * c["max_total"] / tot for k, v in targets.items()}
    return dict(targets={k: round(v, 4) for k, v in sorted(targets.items()) if v >= 0.0005},
                per_desk=per_desk, scartate=scartate)


def write_overlay(result: dict, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    doc = dict(data=today.isoformat(), targets=result["targets"], per_desk=result["per_desk"], regole=caps())
    tmp = overlay_path() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, indent=1)
    os.replace(tmp, overlay_path())
    db.runtime_set("desk.overlay", doc)
    audit.log("desk", "desk.overlay", dict(data=doc["data"], titoli=len(doc["targets"]), totale=round(sum(doc["targets"].values()), 4),
                                           scartate=len(result["scartate"])))
    events.publish("desk.overlay", "desk", dict(titoli=len(doc["targets"]), totale=round(sum(doc["targets"].values()), 4),
                                                 targets=doc["targets"]))
    return doc


def cycle(today: dt.date | None = None) -> dict:
    """Un giro dei capi desk: ognuno propone fino a 5 posizioni; il codice valida e scrive il file per GERVA-Q."""
    if not S.get("desk.enabled", True):
        return dict(nota="desk spento")
    from . import workflows as W
    from llm import runtime
    rows = table()
    if not rows:
        return dict(nota="mancano i dati di mercato (firm.py data): nessuna proposta oggi")
    allowed = {r["simbolo"] for r in rows}
    c = caps()
    news = [dict(titolo=n["title"], sintesi=(n["summary"] or "")[:200])
            for n in db.q("SELECT title, summary FROM news WHERE status='verificata' ORDER BY id DESC LIMIT 8")]
    libro, reale = W.libro_posizioni(), W.dati_reali()
    by_desk = {}
    for desk in DESKS:
        a = registry.get(desk)
        if not a or a["kind"] != "llm" or a["status"] not in ("attivo", "in_prova"):
            continue
        r = runtime.call(
            desk, "Da oggi i pod non esistono piu': sei Capo Desk e proponi posizioni LONG per il conto reale (paper), "
                  f"in percentuale del NAV. Scegli al massimo {MAX_PROPOSALS} simboli, SOLO dalla tabella. Peso massimo "
                  f"{c['max_name'] * 100:.1f}% per titolo e {c['max_total'] / len(DESKS) * 100:.1f}% in totale per il tuo desk. "
                  "Motiva con i numeri della tabella o con notizie verificate. Se non c'e' un'idea valida, lista vuota: "
                  "non e' obbligatorio proporre. Tieni conto del libro attuale e non ripetere idee gia' in portafoglio.",
            data=dict(tabella=rows, libro=libro, notizie_verificate=news, _reale=reale),
            schema=W.DESK_PROPOSAL, purpose="desk", status_label="pensa")
        if r["ok"]:
            by_desk[desk] = r["output"]["proposte"][:MAX_PROPOSALS]
    if not by_desk:
        return dict(nota="nessun desk ha risposto")
    result = merge(by_desk, allowed, c)
    doc = write_overlay(result, today)
    return dict(ok=True, desk=list(by_desk), targets=doc["targets"], scartate=result["scartate"])
