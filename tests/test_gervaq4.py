"""GERVA-Q v4: il banco di prova non promuove varianti per fortuna, e il miglioramento 'cash' fa quel che dice."""
import numpy as np
import pandas as pd
import pytest

from quantlab import gervaq4 as G4, strategies as ST, lookahead as LA


def synth(seed=0, years=10, trend=0.0):
    names = G4.TREND_SET + G4.SECTORS + [f"STK{i}" for i in range(8)]
    _, close = ST.synthetic_market(n_days=252 * years, n_assets=len(names), seed=seed, trend_strength=trend, vol=0.18)
    close.columns = names
    close["^VIX"] = 15 + 5 * np.abs(np.sin(np.arange(len(close)) / 50))
    close["^IRX"] = 2.0
    return dict(close=close, stocks=[f"STK{i}" for i in range(8)])


def test_cash_sleeve_adds_about_rate_times_idle():
    d = synth(1, years=4)
    base = G4.run_variant(d, G4.Variant("b"))
    cash = G4.run_variant(d, G4.Variant("c", cash=True))
    extra = (cash - base).mean() * 252
    assert 0.0 < extra < 0.02 - 0.001 + 1e-9          # al massimo (2% - 0,1%) se tutto in liquidita'


def test_combined_weights_have_no_lookahead():
    d = synth(2, years=3)
    v = G4.Variant("x", comb="equal", dyn=True)
    fn = lambda c: G4.combine(c, G4.sleeves(c, v, d["stocks"]), "equal", 0.0008)
    assert LA.truncation_test(fn, d["close"], cut_points=2, min_history=400)["ok"]


def test_bench_on_noise_does_not_promote_a_lucky_signal():
    d = synth(3, years=7)
    res = G4.bench(d, variants=[G4.Variant("v3_riferimento"), G4.Variant("dyn", dyn=True),
                                G4.Variant("erc", comb="erc"), G4.Variant("cash", cash=True)], holdout_years=2)
    assert res.scelta in ("v3_riferimento", "cash"), res.motivo
    assert 0 <= res.pbo["pbo"] <= 1
    assert "Sharpe" in res.tabella.columns and "v3 " in res.to_markdown() or "v3_riferimento" in res.to_markdown()


def test_paired_bootstrap_detects_a_real_edge():
    rng = np.random.default_rng(0)
    b = rng.normal(0.0003, 0.01, 2000)
    assert G4.paired_sharpe_prob(b + 0.0004, b) > 0.95
    assert 0.2 < G4.paired_sharpe_prob(b + rng.normal(0, 0.002, 2000), b) < 0.8
