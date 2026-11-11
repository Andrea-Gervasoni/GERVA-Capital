"""GERVA-Q v4: il banco di prova non promuove varianti per fortuna, e la tesoreria (liquidita' al tasso a breve) vale per tutte."""
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


def test_treasury_adds_about_rate_times_idle_to_every_variant():
    """La liquidita' remunerata e' tesoreria: vale per il riferimento come per ogni variante (prima era la variante 'cash')."""
    d = synth(1, years=4)
    for v in (G4.VARIANTS[0], G4.Variant("b", comb="erc")):
        base = G4.run_variant(dict(d, tesoreria=False), v)
        cash = G4.run_variant(d, v)
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
                                G4.Variant("erc", comb="erc")], holdout_years=2)
    assert res.scelta == "v3_riferimento", res.motivo     # prima era ammessa anche "cash": la cassa non e' piu' una variante
    assert 0 <= res.pbo["pbo"] <= 1
    assert "Sharpe" in res.tabella.columns and "v3 " in res.to_markdown() or "v3_riferimento" in res.to_markdown()


def test_paired_bootstrap_detects_a_real_edge():
    rng = np.random.default_rng(0)
    b = rng.normal(0.0003, 0.01, 2000)
    assert G4.paired_sharpe_prob(b + 0.0004, b) > 0.95
    assert 0.2 < G4.paired_sharpe_prob(b + rng.normal(0, 0.002, 2000), b) < 0.8


def test_exposure_scaling_never_levers():
    d = synth(2, years=4)
    _, r1 = G4.run_variant(d, G4.Variant("b"), return_result=True)
    _, r2 = G4.run_variant(d, G4.Variant("b"), scale=2.0, return_result=True)
    assert r2.daily["gross"].max() <= 1.0 + 1e-6                       # mai oltre il 100%: niente leva
    assert r2.daily["gross"].mean() >= r1.daily["gross"].mean() - 1e-9


def test_risk_ladder_moves_profit_and_loss_together():
    d = synth(3, years=6)
    lad = G4.risk_ladder(d, G4.Variant("b"), scales=(1.0, 1.5))
    lo, hi = lad.loc["x1"], lad.loc["x1.5"]
    assert hi.lorda_media > lo.lorda_media
    if lo.lorda_media < 0.66:                                           # c'era capitale fermo da usare
        assert abs(hi.CAGR) > abs(lo.CAGR) and hi.MaxDD <= lo.MaxDD + 1e-9     # piu' guadagno, perdite piu' profonde
    assert abs(hi.Sharpe - lo.Sharpe) < 0.35                            # la qualita' non cambia molto
    assert "Scala del rischio" in G4.ladder_markdown(lad, "b")
