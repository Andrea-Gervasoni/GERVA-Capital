"""M6: shrinkage, riallocazione prudente, Gerva-Coin, bonus."""
import numpy as np
import pytest


def test_posterior_shrinks_with_few_days_and_learns_with_many():
    from firm.economy import posterior_alpha
    few = posterior_alpha(0.001, 0.01, 20, 0.05)           # alpha 25%/anno osservato su 20 giorni
    many = posterior_alpha(0.001, 0.01, 2000, 0.05)
    assert few["peso_dati"] < 0.15 and few["media"] < 0.05
    assert many["peso_dati"] > 0.3 and many["media"] > few["media"]
    assert posterior_alpha(0.0, 0.0, 0, 0.05)["p_positivo"] == 0.5


def test_alpha_beta_recovers_planted_values():
    from firm.economy import alpha_beta
    rng = np.random.default_rng(0)
    rb = rng.normal(0.0004, 0.01, 3000)
    rp = 0.0002 + 0.6 * rb + rng.normal(0, 0.002, 3000)
    a, b, sd = alpha_beta(rp, rb)
    assert b == pytest.approx(0.6, abs=0.02) and a == pytest.approx(0.0002, abs=0.0001)


def test_reallocation_keeps_capital_without_evidence(firm_env):
    from firm import org_seed, registry, pods, economy, db
    org_seed.seed(); registry.sync(); pods.ensure_pods()
    rng = np.random.default_rng(1)
    nav = {"pod_zero": 85_000.0, "trend": 5_000.0}
    for i in range(30):                                     # solo 30 giorni < 60
        for p in nav:
            nav[p] *= 1 + rng.normal(0.003 if p == "trend" else 0.0, 0.01)
            db.ex("INSERT INTO nav_marks(day,pod,nav,capital,gross) VALUES(?,?,?,?,?)", (f"d{i:03d}", p, nav[p], 0, 0))
    res = {r["pod"]: r for r in economy.reallocate()}
    assert res["trend"]["a"] == res["trend"]["da"] and "insufficiente" in res["trend"]["motivo"]


def test_gc_ledger_and_bonus(firm_env):
    from firm import economy
    economy.gc_move("pod_trend", 100, "bonus", "test")
    economy.gc_move("pod_trend", -30, "spesa", "modello migliore per una settimana")
    assert economy.gc_balance("pod_trend") == 70
    with pytest.raises(ValueError):
        economy.gc_move("pod_trend", -1000, "spesa", "troppo")
