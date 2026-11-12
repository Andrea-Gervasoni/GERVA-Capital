"""Indicatore Gervasoni (GQ): identico alla versione congelata dalla ricerca, senza look-ahead, e solo in ombra."""
import importlib.util
import os

import numpy as np
import pandas as pd
import pytest

from gerva import gervasoni as G

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def bars(n=400, seed=0, drift=0.002):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 100 * np.exp(np.cumsum(drift + 0.02 * rng.standard_normal(n)))
    d = pd.DataFrame(dict(open=np.r_[100, close[:-1]], close=close), index=idx)
    d["high"] = d[["open", "close"]].max(axis=1) * (1 + 0.01 * rng.random(n))
    d["low"] = d[["open", "close"]].min(axis=1) * (1 - 0.01 * rng.random(n))
    return d, pd.Series(1000 + 500 * rng.random(n), index=idx)


def test_no_lookahead_by_truncation():
    d, v = bars()
    btc, _ = bars(seed=1)
    full = G.gq(d, v, btc["close"])
    for t in (150, 211, 260, 333, 399):
        cut = G.gq(d.iloc[:t + 1], v.iloc[:t + 1], btc["close"].iloc[:t + 1])
        assert cut.iloc[-1] == pytest.approx(full.iloc[t], rel=1e-12)


def test_straight_line_up_scores_high_and_noise_scores_low():
    idx = pd.date_range("2024-01-01", periods=300, freq="D")
    c = pd.Series(100 * np.exp(0.01 * np.arange(300)), index=idx)
    d = pd.DataFrame(dict(open=c.shift(1).fillna(100), high=c * 1.005, low=c.shift(1).fillna(100) * 0.995, close=c))
    v = pd.Series(1000.0, index=idx)
    assert G.trend_quality(c).iloc[-1] == pytest.approx(1.0)
    assert G.tier(G.gq(d, v, c).iloc[-1]) == "eccezionale"
    down = c.iloc[::-1].set_axis(idx)
    dd = pd.DataFrame(dict(open=down.shift(1).fillna(down.iloc[0]), high=down.shift(1).fillna(down.iloc[0]) * 1.005, low=down * 0.995, close=down))
    assert G.tier(G.gq(dd, v, down).iloc[-1]) == "bassa"
    assert G.tier(None) == "bassa" and G.tier(float("nan")) == "bassa" and G.tier(0.0) == "media"


def test_matches_the_frozen_research_version():
    path = os.path.join(ROOT, "research", "v5", "v5", "a1_indicatore", "lib.py")
    if not os.path.exists(path):
        pytest.skip("ricerca non presente")
    spec = importlib.util.spec_from_file_location("a1lib", path)
    try:
        lib = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lib)
    except Exception:
        pytest.skip("la libreria della ricerca richiede dipendenze non installate")
    d, v = bars(seed=3)
    btc, _ = bars(seed=4)
    ref = (lib.trend_quality(d["close"]) / 0.20 + lib.trend_quality(btc["close"]) / 0.20 + lib.avwap_month(d, v) / 0.40) / 3
    pd.testing.assert_series_equal(G.gq(d, v, btc["close"]), ref, check_names=False, rtol=1e-10)


def test_indicator_is_shadow_only():
    """Nessun modulo che decide ordini o rischio importa l'indicatore: resta in ombra finche' il paper non lo promuove."""
    for rel in ("gerva/risk/isolated.py", "gerva/risk/engine.py", "gerva/live/pipeline.py", "gerva/strategies/book.py"):
        assert "gervasoni" not in open(os.path.join(ROOT, rel)).read()
