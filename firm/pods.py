"""
Pod di trading (modello multi-manager, DECISIONS D4).

  pod_zero  GERVA-Q v3: libro sistematico di riferimento, riceve il capitale non assegnato
  trend / reversal / crypto: pod in competizione, 5% del NAV ciascuno all'avvio

Regole a scalini (valori in risk_limits.yaml, li cambia Andrea): drawdown del pod oltre dd_cut
-> capitale dimezzato; oltre dd_close -> pod chiuso, il capitale torna al Pod Zero.
"""
from __future__ import annotations

import numpy as np

from . import db, events
from . import settings as S

POD_DEFS = [
    ("trend", "Pod Trend/Macro", "pod_trend", "Trend lento multi-asset", "pod_zero", "ewma_trend"),
    ("reversal", "Pod Reversal/Microstruttura", "pod_reversal", "Fornitura di liquidita' di breve", "pod_zero", "short_reversal"),
    ("crypto", "Pod Crypto/Eventi", "pod_crypto", "Trend crypto con freno sul carry", "pod_zero", "donchian"),
]


def enabled() -> bool:
    return bool(S.get("pods.enabled", False))


def sim_pod_ids() -> list[str]:
    """Pod con capitale simulato: nessuno finche' i pod sono spenti (scelta di Andrea del 6/11)."""
    if not enabled():
        return []
    return [r["id"] for r in db.q("SELECT id FROM pods WHERE id!='pod_zero'")]


def ensure_pods():
    if not enabled():
        # I pod non esistono piu': il conto e' uno solo e tutto il capitale e' del Pod Zero (GERVA-Q).
        if not db.one("SELECT id FROM pods WHERE id='pod_zero'"):
            db.ex("INSERT INTO pods(id,name,head,philosophy,benchmark,capital_frac,status,hwm,created_ts,strategy)"
                  " VALUES(?,?,?,?,?,?,?,?,?,?)",
                  ("pod_zero", "Conto — GERVA-Q", "pod_zero", "Sistematico validato (STUDIO.md)", "SPY",
                   1.0, "attivo", 1.0, db.now_iso(), "gervaq_v3"))
        db.ex("UPDATE pods SET status='chiuso', capital_frac=0 WHERE id!='pod_zero' AND status!='chiuso'")
        db.ex("UPDATE pods SET capital_frac=1.0 WHERE id='pod_zero' AND capital_frac!=1.0")
        if not db.runtime_get("pods.off_marks_cleaned"):
            # Le marcature storiche della societa' includevano il capitale simulato dei pod: il massimo storico (e quindi il
            # drawdown e il KILL) sarebbe calcolato su un NAV gonfiato. Si cancellano: ripartono dal NAV del solo conto.
            db.ex("DELETE FROM nav_marks WHERE pod!='pod_zero'")
            db.runtime_set("pods.off_marks_cleaned", db.now_iso())
        return
    frac = float(S.get("pods.initial_capital_frac"))
    if not db.one("SELECT id FROM pods WHERE id='pod_zero'"):
        db.ex("INSERT INTO pods(id,name,head,philosophy,benchmark,capital_frac,status,hwm,created_ts,strategy)"
              " VALUES(?,?,?,?,?,?,?,?,?,?)",
              ("pod_zero", "Pod Zero — GERVA-Q v3", "pod_zero", "Sistematico validato (STUDIO.md)", "SPY",
               1 - frac * len(POD_DEFS), "attivo", 1.0, db.now_iso(), "gervaq_v3"))
    for pid, name, head, phil, bench, strat in POD_DEFS:
        if not db.one("SELECT id FROM pods WHERE id=?", (pid,)):
            db.ex("INSERT INTO pods(id,name,head,philosophy,benchmark,capital_frac,status,hwm,created_ts,strategy)"
                  " VALUES(?,?,?,?,?,?,?,?,?,?)", (pid, name, head, phil, bench, frac, "attivo", 1.0, db.now_iso(), strat))


def all_pods() -> list[dict]:
    if not enabled():
        return db.q("SELECT * FROM pods WHERE id='pod_zero'")
    return db.q("SELECT * FROM pods ORDER BY CASE id WHEN 'pod_zero' THEN 0 ELSE 1 END, id")


def get(pid: str) -> dict | None:
    return db.one("SELECT * FROM pods WHERE id=?", (pid,))


def pod_of_agent(agent_id: str) -> str | None:
    r = db.one("SELECT id FROM pods WHERE head=?", (agent_id,))
    return r["id"] if r else None


def set_capital(pid: str, frac: float, reason: str, actor: str = "risk_engine"):
    old = get(pid)["capital_frac"]
    db.ex("UPDATE pods SET capital_frac=? WHERE id=?", (frac, pid))
    # il capitale tolto o aggiunto passa dal Pod Zero
    if pid != "pod_zero":
        db.ex("UPDATE pods SET capital_frac=capital_frac+? WHERE id='pod_zero'", (old - frac,))
    events.publish("pod.capital", actor, dict(pod=pid, da=round(old, 4), a=round(frac, 4), motivo=reason))


def apply_drawdown_rules() -> list[dict]:
    """Chiamato dal battito ogni giorno, dopo le marcature di NAV."""
    from . import gateway
    lim = S.risk_limits()["pod"]
    actions = []
    for p in all_pods():
        if p["id"] == "pod_zero" or p["status"] == "chiuso":
            continue
        dd = gateway.pod_book(p["id"])["drawdown"]
        if dd <= -lim["dd_close"]:
            set_capital(p["id"], 0.0, f"drawdown {dd:.1%} oltre {lim['dd_close']:.1%}: pod chiuso")
            db.ex("UPDATE pods SET status='chiuso' WHERE id=?", (p["id"],))
            actions.append(dict(pod=p["id"], azione="chiuso", drawdown=dd))
            from . import compensation
            compensation.clawback(p["head"], f"pod {p['id']} chiuso per drawdown {dd:.1%}")
        elif dd <= -lim["dd_cut"] and p["status"] == "attivo":
            set_capital(p["id"], p["capital_frac"] / 2, f"drawdown {dd:.1%} oltre {lim['dd_cut']:.1%}: capitale dimezzato")
            db.ex("UPDATE pods SET status='ridotto' WHERE id=?", (p["id"],))
            actions.append(dict(pod=p["id"], azione="dimezzato", drawdown=dd))
    return actions


def pod_returns(pid: str) -> list[float]:
    navs = [r["nav"] for r in db.q("SELECT nav FROM nav_marks WHERE pod=? ORDER BY day", (pid,))]
    return [b / a - 1 for a, b in zip(navs, navs[1:]) if a > 0]


def mean_pod_correlation(window: int = 60) -> float | None:
    series = {p["id"]: pod_returns(p["id"])[-window:] for p in all_pods() if p["id"] != "pod_zero"}
    series = {k: v for k, v in series.items() if len(v) >= 20}
    if len(series) < 2:
        return None
    n = min(len(v) for v in series.values())
    M = np.array([v[-n:] for v in series.values()])
    if (M.std(axis=1) == 0).any():
        return None
    C = np.corrcoef(M)
    iu = np.triu_indices(len(series), 1)
    return float(C[iu].mean())
