"""Proprieta' note della statistica del Sharpe e dell'overfitting."""
import math

import numpy as np
import pytest

from quantlab import stats as S


def test_moments_kurtosis_is_not_excess():
    r = np.random.default_rng(1).normal(0, 0.01, 200_000)
    m = S.moments(r)
    assert abs(m.kurt - 3.0) < 0.05          # normale: gamma4 = 3, non 0
    assert abs(m.skew) < 0.02


def test_psr_matches_normal_approx():
    # rendimenti normali: PSR(0) = Phi(SR * sqrt(T-1) / sqrt(1 + SR^2/2))
    rng = np.random.default_rng(2)
    r = rng.normal(0.0005, 0.01, 2000)
    m = S.moments(r)
    from scipy.stats import norm
    approx = norm.cdf(m.sr * math.sqrt(m.n - 1) / math.sqrt(1 - m.skew * m.sr + (m.kurt - 1) / 4 * m.sr ** 2))
    assert S.psr(m) == pytest.approx(approx)


def test_dsr_penalizes_more_trials():
    r = np.random.default_rng(3).normal(0.0006, 0.01, 1500)
    m = S.moments(r)
    var = (0.5 / math.sqrt(252)) ** 2
    d1, d10, d1000 = S.dsr(m, 1, var), S.dsr(m, 10, var), S.dsr(m, 1000, var)
    assert d1 == pytest.approx(S.psr(m))
    assert d1 > d10 > d1000


def test_expected_max_sr_grows_like_sqrt_log_n():
    v = 1.0
    e = [S.expected_max_sr(n, v) for n in (10, 100, 1000, 10000)]
    assert all(a < b for a, b in zip(e, e[1:]))
    # per N grande E[max] ~ sqrt(2 ln N)
    assert e[-1] == pytest.approx(math.sqrt(2 * math.log(10000)), rel=0.15)


def test_min_trl_example_in_docs():
    # alpha_research.md §3: Sharpe annuo 1, normale -> ~683 giorni
    sr = 1 / math.sqrt(252)
    m = S.Moments(sr=sr, n=1000, skew=0.0, kurt=3.0)
    assert S.min_trl(m) == pytest.approx(683, abs=3)
    assert S.min_trl(S.Moments(sr=-0.01, n=100, skew=0, kurt=3)) == math.inf


def test_pbo_noise_is_coin_flip_and_signal_is_not():
    # Le combinazioni CSCV di UN dataset sono molto dipendenti tra loro: la PBO di un singolo
    # campione di rumore puo' stare lontano da 0,5 (con questo seme 0,87). La proprieta' vera
    # e' che, su molti dataset di rumore, la PBO media e' circa 0,5.
    pbos = []
    for seed in range(12):
        noise = np.random.default_rng(seed).normal(0, 0.01, (800, 20))
        pbos.append(S.pbo_cscv(noise, n_blocks=8).pbo)
    assert 0.35 < np.mean(pbos) < 0.65
    good = np.random.default_rng(4).normal(0, 0.01, (1600, 20))
    good[:, 7] += 0.004                       # una variante vera e dominante
    assert S.pbo_cscv(good, n_blocks=10).pbo < 0.05


def test_bootstrap_ci_contains_point_estimate():
    r = np.random.default_rng(5).normal(0.0005, 0.01, 1500)
    lo, hi = S.sharpe_ci_bootstrap(r, n_boot=400)
    point = r.mean() / r.std(ddof=1) * math.sqrt(252)
    assert lo < point < hi
    assert hi - lo > 0.3                     # su 6 anni l'incertezza non puo' essere minuscola


def test_performance_keys():
    r = np.random.default_rng(6).normal(0.0004, 0.01, 800)
    p = S.performance(r)
    assert set(["CAGR", "Sharpe", "MaxDD", "PSR0", "MinTRL_anni"]) <= set(p)
    assert p["MaxDD"] <= 0
