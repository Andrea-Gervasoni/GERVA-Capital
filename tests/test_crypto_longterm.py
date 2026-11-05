"""Zona ricerca crypto e quota di lungo periodo: niente futuro nei pesi, niente leva, conti del piano giusti."""
import numpy as np
import pandas as pd
import pytest

from quantlab import crypto4 as C4, longterm as LT, lookahead as LA


def synth_crypto(seed=0, days=1400):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", periods=days, freq="D")
    r = rng.normal(0.0008, 0.04, (days, len(C4.COINS)))
    close = pd.DataFrame(100 * np.exp(np.cumsum(r, axis=0)), index=idx, columns=C4.COINS)
    close.iloc[:200, C4.COINS.index("SOL")] = np.nan                  # moneta nata dopo
    close["^IRX"] = 3.0
    return close


@pytest.mark.parametrize("v", C4.VARIANTS, ids=lambda v: v.name)
def test_crypto_weights_have_no_lookahead_and_no_leverage(v):
    close = synth_crypto(1)
    res = LA.truncation_test(lambda c: C4.weights(c, v), close, cut_points=4, min_history=400)
    assert res["ok"], res["violazioni"][:2]
    _, rr = C4.run_variant(dict(close=close), v, return_result=True)
    assert rr.daily["gross"].max() <= 1 + 1e-9
    _, r2 = C4.run_variant(dict(close=close), v, scale=2.0, return_result=True)
    assert r2.daily["gross"].max() <= 1 + 1e-9


def test_crypto_bench_on_noise_keeps_v3():
    res = C4.bench(dict(close=synth_crypto(2, days=1600)), start_skip=200)
    assert res.scelta in [v.name for v in C4.VARIANTS]
    assert "v3_crypto" in res.tabella.index


def test_longterm_plan_and_basket():
    pl = LT.plan(1_000_000, 0.05, {"A": 100.0, "B": 250.0}, eurusd=1.0)
    assert pl.loc["A", "azioni"] == 250 and pl.loc["B", "azioni"] == 100
    assert pl.euro_investiti.sum() <= 50_000 + 1e-6
    idx = pd.bdate_range("2020-01-01", periods=600)
    close = pd.DataFrame({"A": np.linspace(100, 200, 600), "B": np.linspace(100, 50, 600)}, index=idx)
    r = LT.basket_returns(close, ["A", "B"])
    first_day = 0.5 * (close.A.iloc[1] / close.A.iloc[0] - 1) + 0.5 * (close.B.iloc[1] / close.B.iloc[0] - 1)
    assert r.iloc[1] == pytest.approx(first_day)
    rep = LT.risk_report(r, 50_000)
    assert rep["caduta_massima"] <= 0 and rep["caduta_massima_eur"] == pytest.approx(rep["caduta_massima"] * 50_000)
