"""Grafici quant: indicatori calcolati dal codice (senza look-ahead sul bordo) e confronto del conto con l'S&P 500."""
import numpy as np
import pandas as pd
import pytest

from firm import charts, db


def _close(n=400, seed=1):
    idx = pd.bdate_range("2025-01-01", periods=n)
    rng = np.random.default_rng(seed)
    px = lambda drift: 100 * np.exp(np.cumsum(rng.normal(drift, 0.01, n)))
    return pd.DataFrame({"AAA": px(0.0008), "SPY": px(0.0004), "^VIX": 18 + 5 * rng.random(n)}, index=idx)


def test_indicators_are_consistent():
    c = _close()
    d = charts.indicators("AAA", 120, c)
    assert len(d["date"]) == len(d["close"]) == len(d["rsi"]) == len(d["ema200"]) == 120
    assert all(0 <= v <= 100 for v in d["rsi"] if v is not None)
    assert all(a >= b for a, b in zip(d["bb_su"], d["bb_giu"]) if a is not None and b is not None)
    assert max(d["drawdown"]) <= 0 and min(d["drawdown"]) >= -1
    s = d["riepilogo"]
    assert s["trend"] in ("rialzista", "ribassista", "misto") and s["segnale_rsi"] in ("ipercomprato", "ipervenduto", "neutro")


def test_rsi_extremes():
    up = pd.Series(np.arange(1, 80, dtype=float))
    assert charts.rsi(up).iloc[-1] > 99                       # solo rialzi
    assert charts.rsi(up[::-1].reset_index(drop=True)).iloc[-1] < 1


def test_unknown_symbol_and_regime():
    c = _close()
    with pytest.raises(KeyError):
        charts.indicators("ZZZ", 100, c)
    r = charts.regime(c)
    assert "vix" in r and "spy_sopra_ema200" in r and r["lettura"]


def test_equity_is_rebased_to_100_for_account_and_spy(firm_env):
    c = _close()
    t0 = str(c.index[-3].date())
    db.runtime_set("ibkr.start_nav", dict(nav=969000.0, giorno=t0))
    db.ex("INSERT INTO nav_ticks(ts,nav) VALUES(?,?)", (t0 + "T10:00:00Z", 969000.0))
    db.ex("INSERT INTO nav_ticks(ts,nav) VALUES(?,?)", (str(c.index[-1].date()) + "T10:00:00Z", 979000.0))
    e = charts.equity_vs_benchmark(c)
    assert e["conto"][0]["v"] == 100 and abs(e["conto"][-1]["v"] - 100 * 979000 / 969000) < 0.01
    assert e["spy"][0]["v"] == 100                            # S&P 500 in base 100 dall'ultima chiusura fino al primo punto
    assert e["spy"][0]["t"][:10] <= t0


def test_charts_api_rejects_unknown_symbol(firm_env):
    from fastapi.testclient import TestClient
    from portal import app as A
    r = TestClient(A.app).get("/api/charts/series?sym=../../etc/passwd")
    assert r.status_code == 404
