"""
Scorekeeper: punteggi calcolati da codice, mai auto-valutazione (brief <valutazione_e_promozioni>).

  * Previsioni: registrate con hash PRIMA dell'esito (trigger: non si cambiano), Brier e calibrazione.
  * Metriche per ruolo -> tabella `evaluations` (una riga = una valutazione indipendente).
  * Punteggio composito = 70% metriche dure + 30% valutazioni dei pari (rubrica fissa, cieca).
  * Promozione: >= 30 valutazioni, miglioramento statisticamente distinguibile dalla media del
    grado (Welch, una coda), poi periodo di prova di 14 giorni.
"""
from __future__ import annotations

import hashlib
import json
import math
import uuid

import numpy as np
from scipy import stats as sps

from . import db, events
from . import settings as S

GRADES = ["Stagista", "Analista", "Analista Senior", "Ricercatore", "Senior", "Manager", "Head"]

# metriche dure per ruolo: (nome, verso) con verso +1 = piu' alto e' meglio, -1 = piu' basso e' meglio
ROLE_METRICS = {
    "previsioni": [("brier", -1)],
    "ricerca": [("tasso_validazione", +1), ("forward_vs_atteso", +1), ("bug_dopo_approvazione", -1)],
    "redazione": [("precisione_eventi", +1), ("affermazioni_non_verificabili", -1)],
    "validazione": [("bug_reali_trovati", +1), ("canarini_individuati", +1)],
    "rischio": [("allarmi_veri", +1), ("allarmi_falsi", -1)],
    "pod": [("contributo_alpha", +1), ("disciplina_rischio", +1)],
    "esecuzione": [("slippage_vs_modello", -1)],
    "direzione": [("brier", -1)],
}


# ---------------------------------------------------------------------------
# Previsioni
# ---------------------------------------------------------------------------
def register_forecast(agent_id: str, statement: str, prob: float, deadline: str, criterion: str,
                      source: str, canary: bool = False) -> str:
    if not (0.0 <= prob <= 1.0):
        raise ValueError("probabilita' in [0,1]")
    if not statement or not criterion or not deadline:
        raise ValueError("enunciato, scadenza e criterio di risoluzione sono obbligatori")
    ts = db.now_iso()
    fid = f"F-{uuid.uuid4().hex[:10]}"
    h = hashlib.sha256(db.dumps([fid, ts, agent_id, statement, prob, deadline, criterion, source]).encode()).hexdigest()
    db.ex("INSERT INTO forecasts(id,ts,agent_id,statement,prob,deadline,criterion,source,hash,canary)"
          " VALUES(?,?,?,?,?,?,?,?,?,?)",
          (fid, ts, agent_id, statement, prob, deadline, criterion, source, h, int(canary)))
    events.publish("forecast.registered", agent_id, dict(id=fid, prob=prob, scadenza=deadline, hash=h[:12]))
    return fid


def resolve_forecast(fid: str, outcome: bool, resolver: str):
    f = db.one("SELECT * FROM forecasts WHERE id=?", (fid,))
    db.ex("UPDATE forecasts SET outcome=?, resolved_ts=?, resolved_by=? WHERE id=?",
          (int(outcome), db.now_iso(), resolver, fid))
    b = (f["prob"] - int(outcome)) ** 2
    add_eval(f["agent_id"], "brier", b, kind="dura", details=dict(forecast=fid))
    events.publish("forecast.resolved", resolver, dict(id=fid, agente=f["agent_id"], esito=bool(outcome),
                                                       brier=round(b, 4)))


def brier(probs, outcomes) -> float:
    p, o = np.asarray(probs, float), np.asarray(outcomes, float)
    return float(np.mean((p - o) ** 2)) if len(p) else float("nan")


def calibration(probs, outcomes, bins: int = 10) -> dict:
    """Curva di calibrazione e scomposizione di Murphy (affidabilita' - risoluzione + incertezza).
    La scomposizione e' esatta quando le previsioni coincidono con i valori dei bin."""
    p, o = np.asarray(probs, float), np.asarray(outcomes, float)
    n = len(p)
    if n == 0:
        return dict(n=0, curva=[], affidabilita=None, risoluzione=None, incertezza=None, brier=None)
    k = np.minimum((p * bins).astype(int), bins - 1)
    obar = o.mean()
    rel = res = 0.0
    curve = []
    for b in range(bins):
        m = k == b
        if m.any():
            pk, ok, nk = p[m].mean(), o[m].mean(), m.sum()
            rel += nk * (pk - ok) ** 2
            res += nk * (ok - obar) ** 2
            curve.append(dict(bin=b, prob_media=float(pk), frequenza=float(ok), n=int(nk)))
    return dict(n=n, curva=curve, affidabilita=rel / n, risoluzione=res / n,
                incertezza=float(obar * (1 - obar)), brier=brier(p, o))


def agent_forecasts(agent_id: str) -> dict:
    rows = db.q("SELECT prob, outcome FROM forecasts WHERE agent_id=? AND outcome IS NOT NULL", (agent_id,))
    open_n = db.one("SELECT COUNT(*) n FROM forecasts WHERE agent_id=? AND outcome IS NULL", (agent_id,))["n"]
    cal = calibration([r["prob"] for r in rows], [r["outcome"] for r in rows])
    right = sum(1 for r in rows if (r["prob"] >= 0.5) == bool(r["outcome"]))
    return dict(risolte=len(rows), aperte=open_n, giuste=right, sbagliate=len(rows) - right, **cal)


# ---------------------------------------------------------------------------
# Valutazioni
# ---------------------------------------------------------------------------
def add_eval(agent_id: str, metric: str, value: float, kind: str = "dura", weight: float = 1.0,
             details: dict | None = None):
    db.ex("INSERT INTO evaluations(ts,agent_id,metric,value,weight,kind,details) VALUES(?,?,?,?,?,?,?)",
          (db.now_iso(), agent_id, metric, float(value), weight, kind, db.dumps(details or {})))


RUBRIC = ["correttezza", "chiarezza", "uso_delle_fonti", "rispetto_delle_regole", "utilita"]


def peer_review(reviewer: str, reviewee: str, scores: dict, defect: str):
    """Rubrica fissa 1-5, cieca (il revisore riceve il lavoro, non l'opinione dell'autore).
    Anti-sycophancy: un difetto concreto o la motivazione della sua assenza e' obbligatorio."""
    if reviewer == reviewee:
        raise ValueError("auto-valutazione vietata")
    if set(scores) != set(RUBRIC) or not all(1 <= v <= 5 for v in scores.values()):
        raise ValueError(f"rubrica fissa: {RUBRIC}, voti 1-5")
    if not defect or len(defect.strip()) < 15:
        raise ValueError("serve un difetto concreto o la motivazione del perche' non ce ne sono")
    score = float(np.mean(list(scores.values())))
    db.ex("INSERT INTO peer_reviews(ts,reviewer,reviewee,rubric,score,defect) VALUES(?,?,?,?,?,?)",
          (db.now_iso(), reviewer, reviewee, db.dumps(scores), score, defect))
    add_eval(reviewee, "pari", (score - 1) / 4, kind="pari")


def _hard_component(agent_id: str, dept: str) -> tuple[float | None, int]:
    """Media delle metriche dure normalizzate in [0,1] (1 = ottimo)."""
    metrics = ROLE_METRICS.get(dept, []) + ([("brier", -1)] if dept not in ("previsioni", "direzione") else [])
    vals, n = [], 0
    for name, sign in metrics:
        rows = db.q("SELECT value FROM evaluations WHERE agent_id=? AND metric=? AND kind='dura'", (agent_id, name))
        if not rows:
            continue
        x = np.array([r["value"] for r in rows])
        n += len(x)
        if name == "brier":
            vals.append(float(np.clip(1 - x.mean() / 0.25, 0, 1)))     # 0,25 = sempre 50%
        else:
            m = float(np.clip(x.mean(), 0, 1))
            vals.append(m if sign > 0 else 1 - m)
    return (float(np.mean(vals)) if vals else None), n


def composite(agent_id: str, dept: str) -> dict:
    hard, n_hard = _hard_component(agent_id, dept)
    peers = db.q("SELECT value FROM evaluations WHERE agent_id=? AND kind='pari'", (agent_id,))
    peer = float(np.mean([r["value"] for r in peers])) if peers else None
    if hard is None and peer is None:
        score = None
    elif peer is None:
        score = hard
    elif hard is None:
        score = peer
    else:
        score = 0.7 * hard + 0.3 * peer
    canaries = db.q("SELECT value FROM evaluations WHERE agent_id=? AND metric='canarino'", (agent_id,))
    return dict(punteggio=score, dure=hard, pari=peer, n_valutazioni=n_hard + len(peers),
                canarini_superati=sum(1 for c in canaries if c["value"] >= 1), canarini=len(canaries))


# ---------------------------------------------------------------------------
# Promozioni e retrocessioni (proposte dal Talent Manager, decise da codice)
# ---------------------------------------------------------------------------
def promotion_test(agent_id: str, dept: str, grade: int, peers: list[str]) -> dict:
    """Welch a una coda: la media dei punteggi per valutazione dell'agente supera quella degli
    agenti dello stesso grado? Richiede il campione minimo."""
    min_n = int(S.get("talent.min_evals_promotion"))
    alpha = float(S.get("talent.p_value"))

    def series(a):
        return np.array([r["value"] for r in db.q(
            "SELECT value FROM evaluations WHERE agent_id=? AND kind IN ('dura','pari') AND metric!='brier'", (a,))]
            + [1 - r["value"] / 0.25 for r in db.q(
                "SELECT value FROM evaluations WHERE agent_id=? AND metric='brier'", (a,))])

    x = series(agent_id)
    pool = np.concatenate([series(p) for p in peers if p != agent_id] or [np.array([])])
    if len(x) < min_n or len(pool) < 2:
        return dict(idoneo=False, motivo=f"campione insufficiente ({len(x)}/{min_n})", n=len(x))
    t, p_two = sps.ttest_ind(x, pool, equal_var=False)
    p = p_two / 2 if t > 0 else 1 - p_two / 2
    ok = p < alpha
    return dict(idoneo=bool(ok), p_value=float(p), media=float(x.mean()), media_grado=float(pool.mean()),
                n=len(x), motivo="migliore della media del grado" if ok else "non distinguibile dalla media")


def demotion_reasons(agent_id: str) -> list[str]:
    reasons = []
    severe = db.one("SELECT COUNT(*) n FROM postmortems WHERE agent_id=? AND severity>=4", (agent_id,))["n"]
    if severe:
        reasons.append(f"{severe} errori gravi con post-mortem")
    can = db.q("SELECT value FROM evaluations WHERE agent_id=? AND metric='canarino'", (agent_id,))
    if len(can) >= 5 and np.mean([c["value"] for c in can]) < 0.5:
        reasons.append("canarini falliti in maggioranza")
    return reasons
