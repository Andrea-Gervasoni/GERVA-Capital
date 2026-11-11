"""Ciclo paper del libro dei trade: apre solo con conviction alta, perde al massimo il margine, e' idempotente."""
import numpy as np
import pandas as pd

from gerva.live import tradecycle as TC


def bars(n=320, drift=0.004, last=None, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    close = 100 * np.exp(np.cumsum(drift + 0.01 * rng.standard_normal(n)))
    df = pd.DataFrame(dict(open=np.r_[100, close[:-1]], close=close), index=idx)
    df["high"] = df[["open", "close"]].max(axis=1) * 1.01
    df["low"] = df[["open", "close"]].min(axis=1) * 0.99
    if last:
        for k, v in last.items():
            df.iloc[-1, df.columns.get_loc(k)] = v
    return df


def test_opens_in_uptrend_and_is_idempotent():
    b = {"BTC": bars(), "ETH": bars(seed=1)}
    s = TC.step(b, TC.empty_state(10_000), 10.0)
    assert set(s["open"]) == {"BTC", "ETH"}
    t = s["open"]["BTC"]
    assert t["leverage"] <= 10.0 and t["risk"] <= 0.02 * 10_000 + 1e-9 and t["margin"] < 0.1 * 10_000
    assert s["totals"]["risk"] <= 0.06 + 1e-9
    again = TC.step(b, s, 10.0)
    assert again is s and len(again["log"]) == 1


def test_no_trade_in_downtrend():
    b = {"BTC": bars(drift=-0.004), "ETH": bars(drift=-0.004, seed=1)}
    assert TC.step(b, TC.empty_state(10_000), 10.0)["open"] == {}


def test_crash_through_stop_loses_at_most_the_margin():
    b = {"BTC": bars()}
    s = TC.step(b, TC.empty_state(10_000), 10.0)
    t = s["open"]["BTC"]
    nxt = b["BTC"].index[-1] + pd.Timedelta(days=1)
    px = t["entry"]
    crash = pd.DataFrame(dict(open=px * 0.4, high=px * 0.41, low=px * 0.35, close=px * 0.38), index=[nxt])     # apre al -60%
    b2 = {"BTC": pd.concat([b["BTC"], crash])}
    s2 = TC.step(b2, s, 10.0)
    assert "BTC" not in s2["open"] or s2["open"]["BTC"]["entry"] != px
    rec = s2["closed"][0]
    assert rec["why"] == "stop" and rec["pnl"] >= -t["margin"] - 1e-9
    assert s2["equity"] >= 10_000 - t["margin"] - 1e-6
    assert -rec["pnl"] / 10_000 <= 0.15 + 1e-9             # mai oltre il tetto di margine del libro, anche con la sede a 10x


def test_engine_halted_or_ai_veto_blocks_entries():
    b = {"BTC": bars()}
    assert TC.step(b, TC.empty_state(10_000), 10.0, engine_scale=0.0)["open"] == {}
    assert TC.step(b, TC.empty_state(10_000), 10.0, ai_multiplier={"BTC": 0.0})["open"] == {}
    half = TC.step(b, TC.empty_state(10_000), 10.0, ai_multiplier={"BTC": 0.5})["open"]["BTC"]
    full = TC.step(b, TC.empty_state(10_000), 10.0)["open"]["BTC"]
    assert abs(half["risk"] - full["risk"] / 2) < 1e-6


def test_summary_gates():
    s = TC.empty_state(10_000)
    s["closed"] = [dict(R=0.5)] * 30 + [dict(R=-1.0)] * 10
    out = TC.summary(s)
    assert out["closed"] == 40 and out["gate_trades"] and out["gate_mean_R"] and abs(out["mean_R"] - 0.125) < 1e-9
