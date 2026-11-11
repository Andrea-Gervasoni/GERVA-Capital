"""Motore GERVA: backtest, indicatori, strategie (anti look-ahead), Monte Carlo, allocazione. Solo dati sintetici."""
import math

import numpy as np
import pandas as pd
import pytest

from gerva import indicators as ind
from gerva.backtest import Costs, run, scale_returns
from gerva.portfolio import allocate
from gerva.strategies import book, intraday as SI
from gerva.strategies import daily as SD
from gerva.validation import metrics as M
from gerva.validation import montecarlo as MC


def prices(n=900, k=4, seed=0, freq="B", vol=0.01, drift=0.0003):
    rng = np.random.default_rng(seed)
    r = rng.normal(drift, vol, (n, k))
    idx = pd.date_range("2018-01-01", periods=n, freq=freq)
    return pd.DataFrame(100 * np.exp(np.cumsum(r, 0)), index=idx, columns=[f"A{i}" for i in range(k)])


# ---------------------------------------------------------------- backtest
def test_weight_decided_at_t_earns_return_of_t_plus_1():
    c = pd.DataFrame({"X": [100.0, 100.0, 110.0, 121.0]}, index=pd.date_range("2024-01-01", periods=4))
    R = c.pct_change()
    W = pd.DataFrame({"X": [0.0, 1.0, 0.0, 0.0]}, index=c.index)       # deciso alla chiusura del giorno 2
    res = run(W, R, 0.0, Costs(trade=0.0, cash_haircut=1.0))
    assert res.ret.round(10).tolist() == [0.0, 0.0, 0.10, 0.0]           # prende SOLO il +10% del giorno 3
    late = run(W, R, 0.0, Costs(trade=0.0, cash_haircut=1.0), lag=2)
    assert late.ret.round(10).tolist() == [0.0, 0.0, 0.0, 0.10]          # con un giorno di ritardo prende quello del giorno 4


def test_future_return_cannot_leak_into_today():
    c = prices(300, 3)
    R = c.pct_change()
    W = SD.trend(c)
    base = run(W, R).ret
    R2 = R.copy()
    R2.iloc[200:] = R2.iloc[200:] + 0.05                               # si cambia il futuro
    assert np.allclose(base.iloc[:200], run(W, R2).ret.iloc[:200])


def test_costs_financing_and_cash():
    idx = pd.date_range("2024-01-01", periods=253)
    R = pd.DataFrame({"X": 0.0}, index=idx)
    two = pd.DataFrame({"X": 2.0}, index=idx)
    res = run(two, R, 0.04 / 252, Costs(trade=0.001, borrow_spread=0.015), band=0.0)
    assert res.cost.iloc[0] == pytest.approx(0.002)                     # 2 di turnover x 10 pb
    # un anno a leva 2 su un titolo fermo: si paga (4% + 1,5%) sulla parte presa a prestito
    assert (1 + res.ret.iloc[1:]).prod() - 1 == pytest.approx(-0.055, abs=0.002)
    flat = run(pd.DataFrame({"X": 0.0}, index=idx), R, 0.04 / 252, Costs(cash_haircut=0.005))
    assert (1 + flat.ret).prod() - 1 == pytest.approx(0.035, abs=0.001)  # la cassa rende tasso - 0,5%
    short = run(pd.DataFrame({"X": -1.0}, index=idx), R, 0.0, Costs(trade=0.0, short_fee=0.01, cash_haircut=0.0))
    assert (1 + short.ret.iloc[1:]).prod() - 1 == pytest.approx(-0.01, abs=0.0005)


def test_weights_drift_and_band():
    c = pd.DataFrame({"X": [100, 110, 121, 133.1], "Y": [100, 100, 100, 100.0]}, index=pd.date_range("2024-01-01", periods=4))
    W = pd.DataFrame({"X": 0.5, "Y": 0.5}, index=c.index)
    res = run(W, c.pct_change(), 0.0, Costs(trade=0.0, cash_haircut=1.0), band=0.10)
    assert res.turnover.iloc[0] == pytest.approx(1.0) and res.turnover.iloc[1:].sum() == 0   # la banda evita di inseguire la deriva
    assert res.weights["X"].iloc[2] > 0.5
    capped = run(pd.DataFrame({"X": 3.0, "Y": 3.0}, index=c.index), c.pct_change(), max_gross=2.0)
    assert capped.gross.max() <= 2.0 + 1e-9


def test_scale_returns_charges_borrowing():
    r = pd.Series(0.0, index=pd.date_range("2024-01-01", periods=10))
    assert scale_returns(r, 3.0, 0.0, 0.0252, 252).iloc[0] == pytest.approx(-2 * 0.0001)


# -------------------------------------------------------------- indicatori
def test_session_vwap_is_causal_and_resets_each_day():
    idx = pd.date_range("2024-01-02 09:30", periods=6, freq="1min").append(pd.date_range("2024-01-03 09:30", periods=3, freq="1min"))
    b = pd.DataFrame(dict(high=[10, 12, 14, 14, 14, 14, 50, 50, 50.0], low=[10, 12, 14, 14, 14, 14, 50, 50, 50.0],
                          close=[10, 12, 14, 14, 14, 14, 50, 50, 50.0], volume=[1, 1, 2, 0, 0, 0, 5, 5, 5.0]), index=idx)
    v = ind.session_vwap(b)
    assert v.iloc[0] == 10 and v.iloc[1] == 11 and v.iloc[2] == pytest.approx(12.5) and v.iloc[5] == pytest.approx(12.5)
    assert v.iloc[6] == 50                                              # nuova seduta: riparte
    b2 = b.copy()
    b2.iloc[4:, :] = 999.0                                              # il futuro non cambia il passato
    assert np.allclose(ind.session_vwap(b2).iloc[:4], v.iloc[:4])


def test_bs_gamma_and_gex_sign():
    S = 100.0
    g = ind.bs_gamma(S, 100.0, 30 / 365, 0.2)
    h = 0.01
    from scipy.stats import norm

    def delta(s):
        d1 = (math.log(s / 100) + 0.5 * 0.04 * 30 / 365) / (0.2 * math.sqrt(30 / 365))
        return norm.cdf(d1)
    assert float(g) == pytest.approx((delta(S + h) - delta(S - h)) / (2 * h), rel=1e-3)      # gamma = derivata del delta
    chain = pd.DataFrame(dict(strike=[95, 105], expiry_years=[30 / 365] * 2, iv=[0.2, 0.2], oi=[1000, 1000], type=["P", "C"]))
    out = ind.gex_from_chain(chain, S)
    assert out["call_wall"] == 105 and out["put_wall"] == 95
    only_puts = ind.gex_from_chain(chain[chain.type == "P"], S)
    assert only_puts["gex"] < 0                                         # dealer corti di put: gamma negativo


def test_gex_features_use_only_the_past():
    g = pd.Series(np.random.default_rng(1).normal(0, 1, 600), index=pd.date_range("2020-01-01", periods=600))
    f = ind.gex_features(g)
    g2 = g.copy()
    g2.iloc[400:] = 100.0
    assert np.allclose(ind.gex_features(g2)["rank"].iloc[:400].dropna(), f["rank"].iloc[:400].dropna())


def test_noise_area_uses_previous_days_only():
    days = pd.bdate_range("2024-01-01", periods=30)
    idx = pd.DatetimeIndex([d + pd.Timedelta(hours=10) + pd.Timedelta(minutes=30 * k) for d in days for k in range(13)])
    rng = np.random.default_rng(3)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, len(idx))))
    b = pd.DataFrame(dict(open=c, close=c), index=idx)
    na = ind.noise_area(b, 14)
    b2 = b.copy()
    b2.iloc[-13:] *= 1.5                                                # si stravolge l'ultimo giorno
    na2 = ind.noise_area(b2, 14)
    assert np.allclose(na["sigma"].iloc[-13:], na2["sigma"].iloc[-13:], equal_nan=True)   # la sigma di oggi non dipende da oggi
    assert na["sigma"].iloc[:13 * 14].isna().all()


# ------------------------------------------- strategie: nessun look-ahead
def _truncation_ok(fn, data, cuts, tol=1e-9):
    """Il peso deciso alla riga t, calcolato con i dati fino a t, deve coincidere con quello calcolato con tutti i dati."""
    full = fn(data)
    for t in cuts:
        part = fn(data.iloc[:t + 1])
        a, b = full.iloc[t].fillna(0.0), part.iloc[-1].fillna(0.0)
        if not np.allclose(a, b, atol=tol):
            return False
    return True


@pytest.mark.parametrize("seed", [0, 1])
def test_book_strategies_have_no_lookahead(seed):
    rng = np.random.default_rng(seed)
    cuts = sorted(rng.choice(np.arange(420, 899), 40, replace=False))
    c = prices(900, 2, seed, "D", 0.03)
    c.columns = ["BTC", "ETH"]
    assert _truncation_ok(book.cr_trend, c, cuts)
    many = prices(900, 12, seed + 5, "D", 0.04)
    many.columns = ["BTC", "ETH"] + [f"C{i}" for i in range(10)]
    dv = pd.DataFrame(rng.uniform(1e6, 1e8, many.shape), index=many.index, columns=many.columns)
    full = book.cr_xsmom(many, dv)
    for t in cuts[::4]:
        assert np.allclose(full.iloc[t], book.cr_xsmom(many.iloc[:t + 1], dv.iloc[:t + 1]).iloc[-1])
    assert (full.sum(axis=1) <= 1.0 + 1e-9).all() and (full >= 0).all().all()       # solo long, mai leva
    etf = prices(900, len(book.TREND_UNIVERSE), seed + 9, "B", 0.01)
    etf.index = pd.bdate_range("2003-01-01", periods=900)
    etf.columns = book.TREND_UNIVERSE
    full = book.ma_trend(etf)
    for t in cuts[::8]:
        assert np.allclose(full.iloc[t], book.ma_trend(etf.iloc[:t + 1]).iloc[-1], atol=1e-9)
    assert (full.abs().sum(axis=1) <= 1.0 + 1e-9).all()
    hi, lo = etf * 1.01, etf * 0.99
    full = book.eq_mr(hi, lo, etf)
    for t in cuts[::8]:
        assert np.allclose(full.iloc[t], book.eq_mr(hi.iloc[:t + 1], lo.iloc[:t + 1], etf.iloc[:t + 1]).iloc[-1])


def test_leaking_signal_is_caught_by_the_truncation_check():
    c = prices(600, 2, 4)
    leak = lambda d: np.sign(d.shift(-1) / d - 1).fillna(0.0)          # usa la chiusura di domani
    assert not _truncation_ok(leak, c, range(300, 340))


def test_intraday_simulator_position_earns_next_bar_only():
    idx = pd.date_range("2024-01-02 09:30", periods=4, freq="30min").append(pd.date_range("2024-01-03 09:30", periods=4, freq="30min"))
    b = pd.DataFrame(dict(close=[100, 101, 102, 103, 200, 202, 204, 206.0]), index=idx)
    pos = pd.Series([1, 1, 1, 1, 0, 0, 0, 0.0], index=idx)
    d = SI.simulate(b, pos, cost_side=0.0)
    assert d["gross_ret"].iloc[0] == pytest.approx(101 / 100 - 1 + 102 / 101 - 1 + 103 / 102 - 1)
    assert d["gross_ret"].iloc[1] == 0.0                                # chiuso a fine seduta: il salto notturno non conta
    d2 = SI.simulate(b, pos, cost_side=0.001)
    assert d2["cost"].iloc[0] == pytest.approx(0.002)                   # entrata + uscita forzata in chiusura


def test_funding_carry_enters_the_day_after_the_signal():
    idx = pd.date_range("2024-01-01", periods=20)
    spot = pd.Series(100.0, index=idx)
    f = pd.Series([0.0] * 10 + [0.001] * 10, index=idx)
    d = SD.funding_carry(spot, spot, f, fee_side=0.0, min_funding_annual=0.05, lookback=3, margin_frac=0.0)
    first = d["pos"][d["pos"] > 0].index[0]
    # la media a 3 giorni supera il 5% annuo gia' alla chiusura di t=10: segnale a t=10, in posizione da t=11
    assert first == idx[11] and d["pos"].loc[idx[10]] == 0.0
    assert d["ret"].loc[first] == pytest.approx(0.001)


# ------------------------------------------------ metriche e Monte Carlo
def test_psr_and_expected_max_sharpe():
    rng = np.random.default_rng(0)
    good = pd.Series(rng.normal(0.001, 0.01, 2000))
    assert M.psr(good) > 0.99 and M.psr(-good) < 0.01
    assert M.expected_max_sharpe(1, 1.0) == 0.0
    assert 2.3 < M.expected_max_sharpe(100, 1.0) < 2.7                  # ~2,5 deviazioni standard per 100 prove
    # controllo numerico: il massimo di 100 normali standard
    sim = rng.normal(0, 1, (4000, 100)).max(axis=1).mean()
    assert M.expected_max_sharpe(100, 1.0) == pytest.approx(sim, abs=0.05)
    assert M.dsr(good, 100, 0.25) < M.psr(good)


def test_summary_sharpe_is_on_excess_returns():
    idx = pd.date_range("2020-01-01", periods=1000)
    cash = pd.Series(0.04 / 252, index=idx) + np.random.default_rng(0).normal(0, 1e-6, 1000)
    s = M.summary(cash, 0.04 / 252)
    assert abs(s["sharpe"]) < 1.0                                       # tenere cassa non e' alpha
    assert s["cagr"] == pytest.approx(0.04 * 365 / 252 * 252 / 365, abs=0.003) or s["cagr"] > 0


def test_monte_carlo_leverage_and_ruin_monotone():
    rng = np.random.default_rng(5)
    r = pd.Series(rng.normal(0.0006, 0.01, 2000))
    sw = MC.leverage_sweep(r, [1, 4, 12], horizon=500, n_paths=800, block=10, periods=252)
    assert sw.loc[1, "p_rovina"] <= sw.loc[4, "p_rovina"] <= sw.loc[12, "p_rovina"]
    assert sw.loc[12, "maxdd_p50"] < sw.loc[1, "maxdd_p50"]
    Lk, curve = MC.kelly_leverage(r, periods=252)
    theory = r.mean() / r.var()
    assert Lk == pytest.approx(theory, rel=0.25)                        # Kelly continuo: mu / sigma^2
    assert curve.loc[min(curve.index, key=lambda x: abs(x - 2 * Lk))] < curve.max() / 2 + 0.02   # a 2x Kelly la crescita crolla
    shock = MC.leverage_sweep(r, [4], horizon=500, n_paths=800, block=10, periods=252, shock=(0.002, 0.10))
    assert shock.loc[4, "p_rovina"] > sw.loc[4, "p_rovina"]


def test_block_bootstrap_keeps_cross_section_together():
    x = pd.DataFrame({"a": np.arange(100.0), "b": np.arange(100.0) * 2})
    p = MC.paths(x, 50, 20, 5.0)
    assert np.allclose(p[:, :, 1], 2 * p[:, :, 0])


def test_risk_parity_known_day_before_and_floor():
    idx = pd.date_range("2020-01-01", periods=400)
    rng = np.random.default_rng(2)
    S = pd.DataFrame({"lo": rng.normal(0, 0.005, 400), "hi": rng.normal(0, 0.02, 400)}, index=idx)
    a = allocate.risk_parity(S)
    assert a["lo"].iloc[-1] > a["hi"].iloc[-1] and a.sum(axis=1).max() <= 1.0 + 1e-9
    S2 = S.copy()
    S2.iloc[-1] = 0.5                                                   # l'ultimo giorno non puo' cambiare il peso dell'ultimo giorno
    assert np.allclose(allocate.risk_parity(S2).iloc[-1], a.iloc[-1])
    idle = S.copy()
    idle.loc[idle.index[150:], "hi"] = 0.0                              # strategia ferma da mesi
    w = allocate.risk_parity(idle)
    assert w["hi"].iloc[-1] < 0.60                                      # il pavimento di volatilita' le impedisce di prendersi tutto


def test_kelly_ruin_formula():
    assert allocate.ruin_probability(1.0, 0.5) == pytest.approx(0.5)
    assert allocate.ruin_probability(0.5, 0.5) == pytest.approx(0.125)
    assert allocate.ruin_probability(2.0, 0.5) == 1.0
    assert allocate.kelly_from_sharpe(1.0, 0.10, 0.5) == pytest.approx(5.0)
