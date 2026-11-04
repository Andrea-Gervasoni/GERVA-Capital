import numpy as np
import pytest

from quantlab import portfolio as P
from quantlab import costs


def _cov(n=10, seed=0):
    rng = np.random.default_rng(seed)
    A = rng.normal(size=(n, n))
    C = A @ A.T / n + np.eye(n) * 0.1
    d = rng.uniform(0.1, 0.4, n) / np.sqrt(252)
    s = np.sqrt(np.diag(C))
    return C / np.outer(s, s) * np.outer(d, d)


def test_ledoit_wolf_beats_sample_when_T_close_to_N():
    true = _cov(30, 1)
    rng = np.random.default_rng(2)
    err_s, err_lw = [], []
    for _ in range(20):
        X = rng.multivariate_normal(np.zeros(30), true, size=40)
        S = np.cov(X, rowvar=False, bias=True)
        LW, delta = P.ledoit_wolf(X)
        assert 0 <= delta <= 1
        err_s.append(np.linalg.norm(S - true))
        err_lw.append(np.linalg.norm(LW - true))
    assert np.mean(err_lw) < np.mean(err_s)


def test_erc_equalizes_risk_contributions():
    C = _cov(8, 3)
    w = P.erc(C)
    assert w.sum() == pytest.approx(1)
    rc = P.risk_contributions(w, C)
    assert np.allclose(rc, 1 / 8, atol=1e-6)


def test_hrp_long_only_and_sums_to_one():
    w = P.hrp(_cov(12, 4))
    assert (w > 0).all() and w.sum() == pytest.approx(1)


def test_hrp_diagonal_equals_inverse_variance():
    d = np.array([0.01, 0.02, 0.03, 0.04]) ** 2
    w = P.hrp(np.diag(d))
    iv = (1 / d) / (1 / d).sum()
    assert np.allclose(w, iv, atol=1e-9)


def test_black_litterman_no_views_returns_prior_and_confident_view_moves_it():
    C = _cov(3, 5)
    pi = np.array([0.0002, 0.0003, 0.0001])
    P1 = np.array([[1.0, 0, 0]])
    weak = P.black_litterman(C, pi, P1, [0.002], omega=[1e3])
    assert np.allclose(weak, pi, atol=1e-6)
    strong = P.black_litterman(C, pi, P1, [0.002], omega=[1e-12])
    assert strong[0] == pytest.approx(0.002, rel=1e-3)


def test_kelly_identities():
    assert P.kelly_growth_share(0.5) == pytest.approx(0.75)
    assert P.prob_touch_fraction(0.5, 1.0) == pytest.approx(0.5)
    assert P.prob_touch_fraction(0.5, 0.5) == pytest.approx(0.125)
    assert P.kelly_fraction(0.05, 0.2, 1.0) == pytest.approx(1.25)


def test_ibkr_crypto_minimum_and_cap():
    m = costs.IBKR_CRYPTO
    # 100 USD: minimo 1,75 ma tetto all'1% -> 1,00 di commissione
    assert m.cost(100) == pytest.approx(1.0 + 100 * m.half_spread)
    # 10.000 USD: 0,18%
    assert m.cost(10_000) == pytest.approx(18.0 + 10_000 * m.half_spread)
    # impatto a radice quadrata cresce con la dimensione
    assert m.rate(1e6, 0.03, 1e8) > m.rate(1e5, 0.03, 1e8)
