"""
Registro globale delle prove (regola inviolabile 9, DECISIONS D2).

Regole:
  * una prova si registra PRIMA di guardare i risultati (register), poi si chiude con record_result;
  * le prove non si cancellano (trigger del DB); una prova abbandonata resta come 'abbandonata'
    e conta lo stesso: nascondere prove invalida il Deflated Sharpe;
  * N = numero di prove DISTINTE (stessa famiglia e stessi parametri = stessa prova);
  * la varianza degli Sharpe viene SOLO dagli Sharpe osservati e registrati.
Le prove storiche di GERVA-Q sono caricate con seed_gervaq(): 35 con Sharpe noto
(combo_study.py) e 20 "legacy" senza Sharpe individuale (contano in N, non nella varianza).
"""
from __future__ import annotations

import hashlib
import json
import math
import uuid

import numpy as np

from . import db, events
from . import settings as S
from quantlab import stats as QS


def params_hash(family: str, params: dict) -> str:
    return hashlib.sha256(db.dumps([family, params]).encode()).hexdigest()[:16]


def register(agent_id: str, strategy_id: str, family: str, params: dict, hypothesis: str) -> str:
    if not hypothesis or len(hypothesis) < 20:
        raise ValueError("serve un'ipotesi scritta (meccanismo economico) prima della prova")
    tid = f"T-{uuid.uuid4().hex[:10]}"
    db.ex("INSERT INTO trials(id,ts,agent_id,strategy_id,family,params,params_hash,hypothesis,status)"
          " VALUES(?,?,?,?,?,?,?,?,?)",
          (tid, db.now_iso(), agent_id, strategy_id, family, db.dumps(params),
           params_hash(family, params), hypothesis, "registrata"))
    events.publish("trial.registered", agent_id, dict(trial=tid, strategy=strategy_id, family=family))
    return tid


def record_result(trial_id: str, returns, data_fingerprint: str = "", extra: dict | None = None) -> dict:
    t = db.one("SELECT * FROM trials WHERE id=?", (trial_id,))
    if not t:
        raise KeyError(trial_id)
    if t["status"] != "registrata":
        raise ValueError("risultato gia' registrato: una nuova variante e' una NUOVA prova")
    m = QS.moments(returns)
    db.ex("UPDATE trials SET status='testata', sharpe_daily=?, n_obs=?, skew=?, kurt=?, result=?, "
          "data_fingerprint=? WHERE id=?",
          (m.sr, m.n, m.skew, m.kurt, db.dumps(extra or {}), data_fingerprint, trial_id))
    events.publish("trial.tested", t["agent_id"], dict(trial=trial_id, sharpe_annuo=round(m.sr * math.sqrt(252), 3)))
    return deflated(trial_id)


def abandon(trial_id: str, reason: str):
    db.ex("UPDATE trials SET status='abbandonata', result=? WHERE id=? AND status='registrata'",
          (db.dumps(dict(motivo=reason)), trial_id))


def counts() -> dict:
    n_distinct = db.one("SELECT COUNT(DISTINCT params_hash) n FROM trials")["n"]
    srs = [r["sharpe_daily"] for r in db.q("SELECT sharpe_daily FROM trials WHERE sharpe_daily IS NOT NULL")]
    return dict(n_trials=n_distinct, n_with_sharpe=len(srs),
                var_sr=float(np.var(srs, ddof=1)) if len(srs) > 1 else 0.0)


def deflated(trial_id: str) -> dict:
    t = db.one("SELECT * FROM trials WHERE id=?", (trial_id,))
    if t["sharpe_daily"] is None:
        raise ValueError("prova senza risultato")
    m = QS.Moments(sr=t["sharpe_daily"], n=t["n_obs"], skew=t["skew"], kurt=t["kurt"])
    c = counts()
    sr0 = QS.expected_max_sr(c["n_trials"], c["var_sr"])
    return dict(trial=trial_id, sharpe_annuo=m.sr * math.sqrt(252), psr=QS.psr(m),
                dsr=QS.dsr(m, c["n_trials"], c["var_sr"]), sr0_annuo=sr0 * math.sqrt(252),
                min_trl_anni=QS.min_trl(m) / 252, **c)


def gate(trial_id: str, pbo: float | None = None, cost2x_sharpe: float | None = None,
         lookahead_ok: bool | None = None) -> dict:
    """Cancello automatico in codice (DECISIONS D3). Solo cio' che passa va alla Validazione."""
    d = deflated(trial_id)
    years = db.one("SELECT n_obs FROM trials WHERE id=?", (trial_id,))["n_obs"] / 252
    checks = {
        "dsr": (d["dsr"] >= float(S.get("gate.dsr_min")), round(d["dsr"], 4)),
        "anni_di_storia": (years >= float(S.get("gate.min_years")), round(years, 2)),
        "pbo": (pbo is None or pbo <= float(S.get("gate.pbo_max")), pbo),
        "sharpe_costi_doppi": (cost2x_sharpe is None or cost2x_sharpe > 0, cost2x_sharpe),
        "look_ahead": (lookahead_ok is not False, lookahead_ok),
    }
    ok = all(v[0] for v in checks.values())
    out = dict(trial=trial_id, passa=ok, controlli={k: dict(ok=v[0], valore=v[1]) for k, v in checks.items()},
               deflated=d)
    events.publish("trial.gate", "gate", dict(trial=trial_id, passa=ok))
    return out


# Sharpe annui delle 35 prove v1+v2 di GERVA-Q, copiati da combo_study.py (sono i valori reali
# registrati da Andrea; la v3 aggiunge ~20 prove crypto e combinazioni senza Sharpe individuale).
GERVAQ_V1V2_SHARPES = [0.68, 0.69, 0.68, 0.68, 0.68, 0.69, 0.78, 0.80, 0.77, 0.71, 0.68, 0.70, 0.66,
                       0.71, 0.69, 0.72, 0.66, 0.68, 0.57, 0.50, 0.62, 0.72, 0.68, 0.58, 0.69, 0.69,
                       0.64, 0.12, 0.59, 0.71, 0.77, 0.66, 0.71, 0.66, 0.75]


def seed_gervaq() -> int:
    if db.one("SELECT id FROM trials WHERE agent_id='gervaq_legacy' LIMIT 1"):
        return 0
    n = 0
    for i, sr in enumerate(GERVAQ_V1V2_SHARPES):
        tid = f"T-gq-{i:02d}"
        db.ex("INSERT INTO trials(id,ts,agent_id,strategy_id,family,params,params_hash,hypothesis,status,"
              "sharpe_daily,n_obs,skew,kurt,result) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (tid, "2026-10-31T00:00:00Z", "gervaq_legacy", f"gervaq_v12_{i}", "gervaq_v1v2",
               db.dumps({"i": i}), params_hash("gervaq_v1v2", {"i": i}),
               "Prova storica di GERVA-Q v1/v2 (combo_study.py): Sharpe annuo registrato da Andrea.",
               "testata", sr / math.sqrt(252), 5200, 0.0, 3.0, db.dumps({"fonte": "combo_study.py"})))
        n += 1
    for i in range(20):
        tid = f"T-gq-c{i:02d}"
        db.ex("INSERT INTO trials(id,ts,agent_id,strategy_id,family,params,params_hash,hypothesis,status,result)"
              " VALUES(?,?,?,?,?,?,?,?,?,?)",
              (tid, "2026-11-03T00:00:00Z", "gervaq_legacy", f"gervaq_v3_{i}", "gervaq_v3",
               db.dumps({"i": i}), params_hash("gervaq_v3", {"i": i}),
               "Prova storica di GERVA-Q v3 (crypto e combinazioni): Sharpe individuale non disponibile.",
               "legacy", db.dumps({"fonte": "STUDIO.md §7, circa 55 prove in totale"})))
        n += 1
    return n
