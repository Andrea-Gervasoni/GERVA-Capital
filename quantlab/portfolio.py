"""
Costruzione del portafoglio: shrinkage di Ledoit-Wolf, HRP, ERC (risk parity),
inverso della volatilita', Black-Litterman, tetto di Kelly frazionato.
Formule e fonti: docs/research/alpha_research.md §7.
"""
from __future__ import annotations

import numpy as np
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform


# ---------------------------------------------------------------------------
# Ledoit-Wolf (2004) verso la matrice a correlazione costante
# ---------------------------------------------------------------------------
def ledoit_wolf(X) -> tuple[np.ndarray, float]:
    """X: T x N rendimenti. Ritorna (covarianza ristretta, intensita' delta in [0,1])."""
    X = np.asarray(X, dtype=float)
    T, N = X.shape
    Xc = X - X.mean(axis=0)
    S = Xc.T @ Xc / T
    var = np.diag(S)
    sd = np.sqrt(var)
    R = S / np.outer(sd, sd)
    rbar = (R.sum() - N) / (N * (N - 1))
    F = rbar * np.outer(sd, sd)
    np.fill_diagonal(F, var)
    # pi: somma delle varianze asintotiche degli elementi di S
    Y = Xc ** 2
    pi_mat = (Y.T @ Y) / T - S ** 2
    pi_hat = pi_mat.sum()
    # rho: covarianza asintotica tra target e S
    term1 = ((Xc ** 3).T @ Xc) / T          # theta_ii,ij
    term2 = var[:, None] * S
    theta = term1 - term2
    np.fill_diagonal(theta, 0.0)
    rho_off = rbar * ((np.outer(1 / sd, sd)) * theta).sum()
    rho_hat = np.diag(pi_mat).sum() + rho_off
    gamma_hat = np.linalg.norm(F - S, "fro") ** 2
    kappa = (pi_hat - rho_hat) / gamma_hat if gamma_hat > 0 else 0.0
    delta = float(max(0.0, min(kappa / T, 1.0)))
    return delta * F + (1 - delta) * S, delta


# ---------------------------------------------------------------------------
# Pesi semplici
# ---------------------------------------------------------------------------
def inverse_vol(cov) -> np.ndarray:
    iv = 1 / np.sqrt(np.diag(cov))
    return iv / iv.sum()


def erc(cov, tol: float = 1e-12, max_iter: int = 10_000) -> np.ndarray:
    """Equal Risk Contribution: w_i (Sigma w)_i uguali per ogni i (long-only).

    Formulazione convessa (Spinu 2013): min 1/2 w'Sw - sum_i b_i ln w_i, poi normalizzazione.
    Discesa coordinata ciclica (Griveau-Billion, Richard, Roncalli 2013): per ogni i si
    risolve in forma chiusa S_ii w_i^2 + c_i w_i - b_i = 0 con c_i = sum_{j!=i} S_ij w_j;
    la radice positiva esiste sempre, quindi i pesi restano positivi anche con
    covarianze negative (dove l'iterazione moltiplicativa fallisce)."""
    cov = np.asarray(cov, dtype=float)
    n = cov.shape[0]
    b = np.full(n, 1.0 / n)
    w = inverse_vol(cov)
    for _ in range(max_iter):
        w_old = w.copy()
        for i in range(n):
            c = cov[i] @ w - cov[i, i] * w[i]
            w[i] = (-c + np.sqrt(c * c + 4 * cov[i, i] * b[i])) / (2 * cov[i, i])
        if np.abs(w - w_old).max() < tol * max(1.0, np.abs(w).max()):
            break
    return w / w.sum()


def risk_contributions(w, cov) -> np.ndarray:
    w = np.asarray(w, dtype=float)
    rc = w * (cov @ w)
    return rc / rc.sum()


# ---------------------------------------------------------------------------
# Hierarchical Risk Parity (Lopez de Prado 2016)
# ---------------------------------------------------------------------------
def _cluster_var(cov, idx):
    c = cov[np.ix_(idx, idx)]
    w = 1 / np.diag(c)
    w /= w.sum()
    return float(w @ c @ w)


def hrp(cov) -> np.ndarray:
    cov = np.asarray(cov, dtype=float)
    sd = np.sqrt(np.diag(cov))
    corr = np.clip(cov / np.outer(sd, sd), -1, 1)
    dist = np.sqrt(0.5 * (1 - corr))
    np.fill_diagonal(dist, 0.0)
    order = list(leaves_list(linkage(squareform(dist, checks=False), "single")))
    w = np.ones(len(order))
    stack = [order]
    while stack:
        items = stack.pop()
        if len(items) < 2:
            continue
        half = len(items) // 2
        a, b = items[:half], items[half:]
        va, vb = _cluster_var(cov, a), _cluster_var(cov, b)
        alpha = 1 - va / (va + vb)
        w[a] *= alpha
        w[b] *= 1 - alpha
        stack += [a, b]
    return w / w.sum()


# ---------------------------------------------------------------------------
# Black-Litterman: combina il prior sistematico con le viste degli agenti
# ---------------------------------------------------------------------------
def black_litterman(cov, pi, P, Q, omega, tau: float = 0.05) -> np.ndarray:
    """mu_BL = [(tau S)^-1 + P' O^-1 P]^-1 [(tau S)^-1 pi + P' O^-1 Q].
    omega: varianza delle viste. In GERVA Capital viene dalla calibrazione (Brier)
    dell'agente che ha espresso la vista: piu' e' mal calibrato, piu' omega e' grande."""
    cov, P = np.asarray(cov, float), np.atleast_2d(np.asarray(P, float))
    Q, pi = np.asarray(Q, float), np.asarray(pi, float)
    O = np.diag(np.atleast_1d(omega)) if np.ndim(omega) <= 1 else np.asarray(omega, float)
    ts_inv = np.linalg.inv(tau * cov)
    O_inv = np.linalg.inv(O)
    A = ts_inv + P.T @ O_inv @ P
    return np.linalg.solve(A, ts_inv @ pi + P.T @ O_inv @ Q)


# ---------------------------------------------------------------------------
# Kelly frazionato come TETTO di dimensione (mai come leva: vietata)
# ---------------------------------------------------------------------------
def kelly_fraction(mu_annual: float, vol_annual: float, fraction: float = 0.25) -> float:
    """f = c * mu / sigma^2. Con c=1/2 si ottiene il 75% della crescita con meta' vol."""
    if vol_annual <= 0:
        return 0.0
    return max(0.0, fraction * mu_annual / vol_annual ** 2)


def kelly_growth_share(c: float) -> float:
    """Quota della crescita massima ottenuta con la frazione c di Kelly: c(2-c)."""
    return c * (2 - c)


def prob_touch_fraction(x: float, c: float) -> float:
    """Probabilita' di scendere MAI a x * ricchezza iniziale con frazione c di Kelly
    (moto browniano, parametri noti): x^(2/c - 1)."""
    return x ** (2 / c - 1)
