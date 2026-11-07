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


def save_overlay(doc: dict) -> dict:
    tmp = overlay_path() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, indent=1)
    os.replace(tmp, overlay_path())
    db.runtime_set("desk.overlay", doc)
    return doc


def write_overlay(result: dict, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    prev = db.runtime_get("desk.overlay") or {}
    doc = dict(data=today.isoformat(), targets=result["targets"], per_desk=result["per_desk"], regole=caps(),
               crypto_targets=prev.get("crypto_targets", {}), crypto_data=prev.get("crypto_data"),   # le posizioni dei segnali non si perdono
               scale_mult=prev.get("scale_mult"), scale_data=prev.get("scale_data"),
               max_turnover=prev.get("max_turnover"), turnover_data=prev.get("turnover_data"))
    save_overlay(doc)
    audit.log("desk", "desk.overlay", dict(data=doc["data"], titoli=len(doc["targets"]), totale=round(sum(doc["targets"].values()), 4),
                                           scartate=len(result["scartate"])))
    events.publish("desk.overlay", "desk", dict(titoli=len(doc["targets"]), totale=round(sum(doc["targets"].values()), 4),
                                                 targets=doc["targets"]))
    return doc


def refresh_scale(today: dt.date | None = None) -> dict:
    """Leva gestita per volatilita': se acceso (volmgmt.enabled), scrive il moltiplicatore nel file letto da GERVA-Q.
    Spento: scrive 1.0, cosi' un valore vecchio non resta in giro. GERVA-Q lo limita a [0,6; 1,4] e al tetto assoluto di esposizione."""
    from . import fundrisk
    today = today or dt.date.today()
    mult, info = 1.0, dict(ok=False, motivo="spento")
    if S.get("volmgmt.enabled", False):
        pf = fundrisk.portfolio()
        info = fundrisk.vol_scale(pf["pesi"], lo=float(S.get("volmgmt.lo", 0.6)), hi=float(S.get("volmgmt.hi", 1.4))) if pf["pesi"] else dict(ok=False)
        mult = info["mult"] if info.get("ok") else 1.0
    doc = db.runtime_get("desk.overlay") or dict(data=today.isoformat(), targets={}, per_desk={}, regole=caps())
    save_overlay(dict(doc, scale_mult=mult, scale_data=today.isoformat()))
    audit.log("desk", "desk.scale", dict(mult=mult, info=info))
    return dict(mult=mult, **{k: v for k, v in info.items() if k != "mult"})


PACE_OPTIONS = ["20", "35", "50", "75", "100"]         # % del conto acquistabile al giorno, dal piu' prudente (a parita' vince il primo)


def _vix_band(vp) -> str:
    return "alto" if vp is not None and vp >= 0.90 else "medio" if vp is not None and vp >= 0.75 else "basso"


def refresh_pace(today: dt.date | None = None, force: bool = False) -> dict:
    """Il RITMO DI INGRESSO (quanto GERVA-Q puo' comprare al giorno) lo decide una RIUNIONE (Capo, CRO, Head Research, Head Intelligence;
    voto pesato per precisione storica), senza massimi imposti dal codice. La riunione si fa la prima volta, quando cambia la fascia di
    volatilita' del mercato o ogni pace.meeting_every_days giorni; in mezzo vale l'ultima decisione. Senza nessuna decisione: nessun tetto."""
    from . import charts, fundrisk, meetings, workflows as W
    today = today or dt.date.today()
    doc = db.runtime_get("desk.overlay") or dict(data=today.isoformat(), targets={}, per_desk={}, regole=caps())
    if not S.get("pace.enabled", True):
        save_overlay(dict(doc, max_turnover=1.0, turnover_data=today.isoformat()))
        return dict(max_turnover=1.0, nota="spento")
    reg = charts.regime()
    band = _vix_band(reg.get("vix_percentile"))
    last = db.runtime_get("pace.last") or {}
    age = (today - dt.date.fromisoformat(last["day"])).days if last.get("day") else 10 ** 6
    due = force or not last or last.get("band") != band or age >= int(S.get("pace.meeting_every_days", 7))
    meeting = None
    if due:
        pf = fundrisk.portfolio()
        meeting = meetings.hold("ritmo", "Ritmo di ingresso del conto", f"mercato {band} (VIX percentile {reg.get('vix_percentile')}), "
                                f"esposizione lorda attesa {pf['lordo'] * 100:.0f}% del conto",
                                ["capo", "cro", "head_research", "head_intel"],
                                data=dict(regime=reg, esposizione_lorda_attesa=pf["lordo"], leva=pf["leva"], libro=W.libro_posizioni(),
                                          decisione_precedente=last or None,
                                          domanda="Quanta parte del conto puo' COMPRARE GERVA-Q ogni giorno (in %) mentre porta il portafoglio all'obiettivo? "
                                                  "Le vendite non hanno tetto. Piu' alto = piu' veloce all'obiettivo ma piu' esposto al giorno di ingresso; "
                                                  "piu' basso = prezzo medio mediato su piu' giorni."),
                                context=dict(ritmo=True))
        if meeting.get("ok"):
            last = dict(day=today.isoformat(), band=band, pct=int(meeting["decisione"]), riunione=meeting["id"])
            db.runtime_set("pace.last", last)
    pick = (last["pct"] / 100.0) if last.get("pct") else 1.0
    save_overlay(dict(doc, max_turnover=round(pick, 3), turnover_data=today.isoformat()))
    audit.log("comitato", "desk.pace", dict(max_turnover=round(pick, 3), riunione=last.get("riunione"), fascia=band, nuova_riunione=bool(meeting and meeting.get("ok"))))
    return dict(max_turnover=round(pick, 3), riunione=last.get("riunione"), fascia=band, nuova_riunione=bool(meeting and meeting.get("ok")))


def refresh_ideas() -> dict:
    """Riscrive il file dei desk includendo le posizioni delle idee in corso (senza richiamare i capi desk): un'idea approvata
    entra nel conto senza aspettare il giro del giorno dopo. Il codice rifa' tetti e limiti."""
    from . import ideas
    prev = db.runtime_get("desk.overlay") or {}
    by_desk = {d: [dict(simbolo=k, peso_pct=v * 100.0) for k, v in (w or {}).items()] for d, w in (prev.get("per_desk") or {}).items() if d != "idee"}
    props = ideas.proposals()
    if props:
        by_desk["idee"] = props
    rows = table()
    allowed = {r["simbolo"] for r in rows} | {p["simbolo"] for p in props}
    result = merge(by_desk, allowed, caps()) if by_desk else dict(targets={}, per_desk={}, scartate=[])
    return write_overlay(result)


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
    by_desk, motivi = {}, {}
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
            motivi.setdefault(desk, {}).update({str(p.get("simbolo", "")).upper(): dict(peso_pct=p.get("peso_pct"), motivo=str(p.get("motivo", ""))[:500]) for p in by_desk[desk]})
    try:
        from . import ideas
        props = ideas.proposals()
        if props:
            by_desk["idee"] = props                           # le idee approvate dal comitato entrano come un desk in piu'
            allowed |= {p["simbolo"] for p in props}
    except Exception:
        pass
    if not by_desk:
        return dict(nota="nessun desk ha risposto")
    result = merge(by_desk, allowed, c)
    db.runtime_set("desk.proposals", dict(day=(today or dt.date.today()).isoformat(), per_desk=motivi))     # per la plancia: perche' l'ha proposta
    doc = write_overlay(result, today)
    return dict(ok=True, desk=list(by_desk), targets=doc["targets"], scartate=result["scartate"])
