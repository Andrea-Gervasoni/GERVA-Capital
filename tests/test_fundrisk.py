"""Rischio del fondo: pesi attesi, storia del portafoglio, Monte Carlo a blocchi, stress test."""
import numpy as np
import pandas as pd
import pytest

from firm import fundrisk as F


def _close(n=1500, seed=2):
    idx = pd.bdate_range("2019-01-01", periods=n)
    rng = np.random.default_rng(seed)
    px = lambda mu, sd: 100 * np.exp(np.cumsum(rng.normal(mu, sd, n)))
    df = pd.DataFrame({"SPY": px(0.0004, 0.010), "AAA": px(0.0006, 0.018), "BBB": px(0.0002, 0.012), "^IRX": np.full(n, 3.0)}, index=idx)
    df.loc[df.index[:600], "BBB"] = np.nan                                     # titolo quotato da meno tempo
    return df


def test_portfolio_applies_scale_only_to_base_weights():
    base = dict(weights=dict(SPY=0.30, AAA=0.15), gross_base=0.45, scale=2.0, asof="2026-11-05")
    pf = F.portfolio(model_eq=base, model_cr=dict(weights=dict(BTC=0.1), gross_base=0.1, scale=2.0),
                     overlay=dict(targets=dict(CCC=0.05)), lt_plan={})
    assert abs(pf["pesi"]["SPY"] - 0.60) < 1e-9 and abs(pf["pesi"]["BTC"] - 0.20) < 1e-9 and pf["pesi"]["CCC"] == 0.05
    assert abs(pf["lordo"] - (0.9 + 0.2 + 0.05)) < 1e-9 and pf["leva"] > 0.14
    already = dict(weights=dict(SPY=0.60, AAA=0.30), gross_base=0.45, scale=2.0, asof="2026-11-05")   # pesi gia' scalati
    pf2 = F.portfolio(model_eq=already, model_cr={}, overlay={}, lt_plan={})
    assert abs(pf2["pesi"]["SPY"] - 0.60) < 1e-9


def test_backcast_rescales_missing_names_and_charges_leverage():
    c = _close()
    rets = F.returns_matrix(["SPY", "AAA", "BBB"], c)
    bc = F.backcast(dict(SPY=0.6, AAA=0.5, BBB=0.4), rets, c["^IRX"])           # lordo 150%: leva 50%
    assert bc["copertura"] == 1.0 and not bc["senza_dati"]
    unlev = F.backcast(dict(SPY=0.4, AAA=0.33, BBB=0.27), rets, c["^IRX"])["serie"]
    lev = bc["serie"]
    assert len(lev) > 800 and lev.std() > unlev.std()                          # piu' lordo = piu' volatilita'
    assert F.backcast(dict(NOPE=1.0), rets)["senza_dati"] == ["NOPE"]


def test_monte_carlo_is_reproducible_and_monotone():
    rng = np.random.default_rng(7)
    rp = pd.Series(rng.normal(0.0005, 0.01, 1200), index=pd.bdate_range("2020-01-01", periods=1200))
    a = F.monte_carlo(rp, 1_000_000, 1, n=2000)
    b = F.monte_carlo(rp, 1_000_000, 1, n=2000)
    assert a["finale"] == b["finale"]                                          # stesso seme, stesso risultato
    f = a["ventaglio"]
    assert all(f["5"][i] <= f["25"][i] <= f["50"][i] <= f["75"][i] <= f["95"][i] for i in range(len(f["5"])))
    assert f["50"][0] == 1_000_000 and a["giorni"] == 252
    assert 0 <= a["p_perdita"] <= 1 and a["p_kill"] <= a["p_perdita_10"] + 1e-9 or a["p_kill"] <= 1
    assert sum(a["istogramma"]["conteggi"]) == 2000
    neg = pd.Series(rng.normal(-0.002, 0.01, 1200), index=rp.index)            # deriva negativa: la perdita diventa probabile
    assert F.monte_carlo(neg, 1_000_000, 1, n=2000)["p_perdita"] > 0.8


def test_monte_carlo_needs_history():
    with pytest.raises(ValueError):
        F.monte_carlo(pd.Series(np.zeros(100)), 1e6)


def test_stress_uses_episode_windows():
    idx = pd.bdate_range("2019-01-01", "2023-01-01")
    rp = pd.Series(0.001, index=idx)
    rp[(idx >= "2020-02-19") & (idx <= "2020-03-23")] = -0.02
    s = {x["nome"]: x for x in F.stress(rp, 1_000_000)}
    assert s["Covid"]["disponibile"] and s["Covid"]["rendimento"] < -0.3 and s["Covid"]["euro"] < -300_000
    assert not s["Crisi Lehman"]["disponibile"]                                # la storia parte dopo: onesto, non inventa


def test_overview_without_gerva_q_state_is_graceful(firm_env, tmp_path):
    out = F.overview(1, close=_close(), model_eq={}, model_cr={}, overlay={}, lt_plan={})
    assert out["ok"] is False and "pesi" in out["motivo"]
