"""
Motore di rischio deterministico: applica i limiti di config/risk_limits.yaml, ha potere di
veto (il Gateway lo interroga) e di kill switch (file KILL). Gli agenti di rischio osservano,
segnalano e PROPONGONO; non possono allentare un limite ne' eseguire il KILL.
"""
from __future__ import annotations

import os

import numpy as np

from . import db, events, paths
from . import settings as S


def limits() -> dict:
    return S.risk_limits()


def kill_active() -> bool:
    return os.path.exists(paths.KILL_FILE)


def engage_kill(actor: str, reason: str, cap=None):
    """Lo eseguono SOLO il motore di rischio (actor='risk_engine') o Andrea dal portale."""
    if actor not in ("risk_engine", "andrea"):
        raise PermissionError("il KILL lo esegue solo il motore di rischio o Andrea")
    if actor == "andrea" and not isinstance(cap, S.AndreaCapability):
        raise PermissionError("serve la capability di Andrea")
    with open(paths.KILL_FILE, "w") as f:
        f.write(f"{db.now_iso()} {actor}: {reason}\n")
    events.publish("risk.kill", actor, dict(motivo=reason))


def release_kill(cap):
    if not isinstance(cap, S.AndreaCapability):
        raise PermissionError("solo Andrea toglie il KILL")
    if os.path.exists(paths.KILL_FILE):
        os.remove(paths.KILL_FILE)
    events.publish("risk.kill_released", "andrea", {})


def recommend_kill(agent_id: str, reason: str, evidence: str):
    """Strumento degli agenti di rischio: solo una raccomandazione registrata."""
    events.publish("risk.kill_recommended", agent_id, dict(motivo=reason, evidenza=evidence))


def stress(weights: dict[str, float], kinds: dict[str, str], scenario: dict[str, float]) -> float:
    """Perdita di portafoglio (frazione del NAV) sotto uno shock per tipo di strumento."""
    return float(sum(w * scenario.get(kinds.get(k, "stock"), scenario.get("default", 0.0))
                     for k, w in weights.items()))


SCENARIOS = {
    "azionario -20%": {"stock": -0.20, "etf_ucits": -0.15, "etc": 0.05, "crypto": -0.30},
    "crypto -50% in 48h": {"crypto": -0.50, "stock": -0.03, "etf_ucits": -0.02},
    "ottobre 2008 (stima)": {"stock": -0.17, "etf_ucits": -0.12, "etc": 0.0, "crypto": -0.40},
    "marzo 2020 (stima)": {"stock": -0.12, "etf_ucits": -0.10, "etc": -0.03, "crypto": -0.45},
}


def crisis_vol(weights: np.ndarray, vols: np.ndarray, rho: float = 0.8) -> float:
    """Volatilita' del portafoglio con tutte le correlazioni portate a rho (stima di crisi)."""
    n = len(weights)
    C = rho * np.ones((n, n)) + (1 - rho) * np.eye(n)
    cov = np.outer(vols, vols) * C
    return float(np.sqrt(weights @ cov @ weights))


def snapshot() -> dict:
    """Semaforo del rischio per il portale e per il CRO (numeri da codice)."""
    from . import gateway, pods
    lim = limits()
    alerts = []
    firm = gateway.firm_book()
    nav, peak = firm["nav"], firm["peak"]
    dd = nav / peak - 1 if peak > 0 else 0.0
    if dd <= -lim["firm"]["kill_drawdown"] and not kill_active():
        engage_kill("risk_engine", f"drawdown di societa' {dd:.1%} oltre il limite")
    if dd <= -lim["firm"]["kill_drawdown"] * 0.6:
        alerts.append(dict(livello=2, cosa=f"drawdown di societa' {dd:.1%}"))
    if firm["gross"] > lim["firm"]["max_gross"] + 1e-9:
        alerts.append(dict(livello=3, cosa=f"lorda di societa' {firm['gross']:.2f} oltre {lim['firm']['max_gross']}"))
    for p in pods.all_pods():
        if p["id"] == "pod_zero":
            continue
        b = gateway.pod_book(p["id"])
        if b["drawdown"] <= -lim["pod"]["dd_cut"] * 0.8 and p["status"] == "attivo":
            alerts.append(dict(livello=1, cosa=f"pod {p['id']} vicino al taglio: drawdown {b['drawdown']:.1%}"))
    corr = pods.mean_pod_correlation()
    if corr is not None and corr > lim["firm"]["max_pod_correlation"]:
        alerts.append(dict(livello=2, cosa=f"correlazione media tra pod {corr:.2f} oltre il limite"))
    level = max([a["livello"] for a in alerts], default=0)
    light = "rosso" if kill_active() or level >= 3 else ("giallo" if level >= 1 else "verde")
    return dict(semaforo=light, kill=kill_active(), drawdown=dd, allarmi=alerts, correlazione_pod=corr,
                lorda=firm["gross"], nav=nav)
