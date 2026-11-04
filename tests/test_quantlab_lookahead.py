"""Anti look-ahead: ogni segnale della libreria e il motore di backtest."""
import numpy as np
import pandas as pd
import pytest

from quantlab import strategies as ST, backtest as BT, lookahead as LA, cv


OPEN, CLOSE = ST.synthetic_market(n_days=900, n_assets=5, seed=11, trend_strength=0.01)
MKT = CLOSE.mean(axis=1)

SIGNALS = {
    "ewma_trend": lambda c: ST.ewma_trend(c),
    "tsmom": lambda c: ST.tsmom(c, lookback=126),
    "donchian": lambda c: ST.donchian(c),
    "sector_momentum": lambda c: ST.sector_momentum(c, top=2),
    "short_reversal": lambda c: ST.short_reversal(c, c.mean(axis=1)),
    "dynamic_overlay": lambda c: ST.dynamic_momentum_overlay(c.mean(axis=1), 252, 63).to_frame("m"),
    "vix_mult": lambda c: ST.vix_size_multiplier(c.iloc[:, 0] / 5).to_frame("m"),
    "carry_filter": lambda c: ST.carry_risk_filter(c.iloc[:, 1].pct_change(20) * 10).to_frame("m"),
}


@pytest.mark.parametrize("name", list(SIGNALS))
def test_signal_does_not_use_future_data(name):
    res = LA.truncation_test(SIGNALS[name], CLOSE, cut_points=4, min_history=300)
    assert res["ok"], res["violazioni"]


def test_truncation_test_catches_a_leaky_signal():
    leaky = lambda c: (c.shift(-1) > c).astype(float)       # guarda domani
    assert not LA.truncation_test(leaky, CLOSE, cut_points=3)["ok"]


def test_engine_applies_one_period_delay():
    res = LA.oracle_test(lambda W: BT.run(W, CLOSE, cost_rate=0.0).returns, CLOSE)
    assert res["ok"], res


def test_engine_with_open_execution_also_delays():
    res = LA.oracle_test(lambda W: BT.run(W, CLOSE, OPEN, cost_rate=0.0).returns, CLOSE)
    assert res["ok"], res


def test_weights_drift_and_band_reduce_turnover():
    W = pd.DataFrame(1 / 5, index=CLOSE.index, columns=CLOSE.columns)
    no_band = BT.run(W, CLOSE, cost_rate=0.001, band=0.0)
    banded = BT.run(W, CLOSE, cost_rate=0.001, band=0.02)
    # pesi costanti con deriva: senza banda si ribilancia ogni giorno, con banda molto meno
    assert banded.daily["turnover"].sum() < 0.5 * no_band.daily["turnover"].sum()
    assert no_band.daily["turnover"].iloc[2:].gt(0).mean() > 0.9


def test_buy_and_hold_matches_price_return():
    W = pd.DataFrame(0.0, index=CLOSE.index, columns=CLOSE.columns)
    W["A0"] = 1.0
    # banda 0,5: si entra (scarto iniziale 1 > 0,5) e poi la deriva non basta mai a ritoccare
    res = BT.run(W, CLOSE, cost_rate=0.0, band=0.5)
    nav = (1 + res.returns).prod()
    # deciso alla chiusura del giorno 0, la posizione matura da close(0) a close(fine)
    assert nav == pytest.approx(CLOSE["A0"].iloc[-1] / CLOSE["A0"].iloc[0], rel=1e-9)


def test_purged_kfold_removes_overlap():
    n = 200
    t0 = np.arange(n)
    t1 = t0 + 10                                         # etichette a 10 giorni
    for train, test in cv.purged_kfold(t0, t1, k=4, embargo=5):
        lo, hi = t0[test].min(), t1[test].max()
        for i in train:
            assert not (t0[i] <= hi and t1[i] >= lo)
            assert not (hi < t0[i] <= hi + 5)


def test_cpcv_paths():
    assert cv.n_paths(6, 2) == 5
    splits = list(cv.cpcv_splits(np.arange(120), np.arange(120) + 3, 6, 2, embargo=2))
    assert len(splits) == 15
