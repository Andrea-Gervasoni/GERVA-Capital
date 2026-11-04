"""
Statistica delle performance: Sharpe e suo errore, PSR, DSR, MinTRL, PBO (CSCV),
intervalli di confidenza con bootstrap a blocchi.

Convenzioni (docs/research/alpha_research.md §3-5):
  * gli Sharpe dentro le formule sono alla frequenza ORIGINALE (giornaliera), non annualizzati;
  * gamma4 e' la curtosi NON in eccesso (3 per la normale): pandas.kurt() restituisce
    quella in eccesso, quindi qui si converte sempre in modo esplicito.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from itertools import combinations
import math

import numpy as np
from scipy.stats import norm, skew as _skew, kurtosis as _kurt

EULER_GAMMA = 0.5772156649015329


# ---------------------------------------------------------------------------
# Momenti e Sharpe
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Moments:
    sr: float        # Sharpe per periodo (non annualizzato)
    n: int           # osservazioni
    skew: float      # gamma3
    kurt: float      # gamma4, NON in eccesso


def moments(returns) -> Moments:
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 3 or r.std(ddof=1) == 0:
        raise ValueError("servono almeno 3 rendimenti non costanti")
    sr = r.mean() / r.std(ddof=1)
    return Moments(sr=float(sr), n=len(r), skew=float(_skew(r)),
                   kurt=float(_kurt(r, fisher=False)))


def annualize_sr(sr: float, periods: int = 252) -> float:
    return sr * math.sqrt(periods)


def _var_term(m: Moments, sr: float | None = None) -> float:
    s = m.sr if sr is None else sr
    v = 1.0 - m.skew * s + (m.kurt - 1.0) / 4.0 * s * s
    # con curtosi/asimmetria estreme il termine puo' diventare <= 0: e' il segnale che
    # la stima non e' affidabile; lo si tiene positivo ma minuscolo invece di dividere per 0
    return max(v, 1e-12)


def sharpe_se(m: Moments) -> float:
    """Errore standard dello Sharpe (Lo 2002; Mertens 2002), per periodo."""
    return math.sqrt(_var_term(m) / (m.n - 1))


def psr(m: Moments, sr_star: float = 0.0) -> float:
    """Probabilistic Sharpe Ratio: P(SR vero > sr_star)."""
    z = (m.sr - sr_star) * math.sqrt(m.n - 1) / math.sqrt(_var_term(m))
    return float(norm.cdf(z))


def expected_max_sr(n_trials: int, var_trials: float) -> float:
    """Sharpe massimo atteso tra n_trials prove a Sharpe vero nullo (Bailey-LdP 2014)."""
    if n_trials <= 1 or var_trials <= 0:
        return 0.0
    n = n_trials
    return math.sqrt(var_trials) * ((1 - EULER_GAMMA) * norm.ppf(1 - 1 / n)
                                     + EULER_GAMMA * norm.ppf(1 - 1 / (n * math.e)))


def dsr(m: Moments, n_trials: int, var_trials: float) -> float:
    """Deflated Sharpe Ratio = PSR con soglia pari allo Sharpe massimo atteso sotto H0."""
    return psr(m, expected_max_sr(n_trials, var_trials))


def min_trl(m: Moments, sr_star: float = 0.0, alpha: float = 0.05) -> float:
    """Minimum Track Record Length: osservazioni necessarie perche' PSR >= 1 - alpha.
    Restituisce inf se lo Sharpe osservato non supera la soglia."""
    if m.sr <= sr_star:
        return math.inf
    z = norm.ppf(1 - alpha)
    return 1.0 + _var_term(m) * (z / (m.sr - sr_star)) ** 2


# ---------------------------------------------------------------------------
# Metriche di base di una serie di rendimenti
# ---------------------------------------------------------------------------
def performance(returns, periods: int = 252) -> dict:
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    nav = np.cumprod(1 + r)
    yrs = len(r) / periods
    cagr = nav[-1] ** (1 / yrs) - 1 if yrs > 0 and nav[-1] > 0 else float("nan")
    peak = np.maximum.accumulate(nav)
    dd = float((nav / peak - 1).min())
    vol = float(r.std(ddof=1) * math.sqrt(periods))
    m = moments(r)
    tail = np.sort(r)[: max(1, int(0.05 * len(r)))]
    return dict(CAGR=float(cagr), Vol=vol, Sharpe=annualize_sr(m.sr, periods),
                MaxDD=dd, Calmar=float(cagr / abs(dd)) if dd < 0 else float("nan"),
                CVaR95=float(tail.mean()), Skew=m.skew, Kurt=m.kurt, N=m.n,
                PSR0=psr(m), MinTRL_anni=min_trl(m) / periods)


# ---------------------------------------------------------------------------
# Probability of Backtest Overfitting (CSCV)
# ---------------------------------------------------------------------------
@dataclass
class PBOResult:
    pbo: float
    n_combinations: int
    logits: list
    perf_degradation_slope: float    # pendenza OOS ~ IS dei migliori: < 0 = degrado

    def to_dict(self):
        d = asdict(self)
        d["logits"] = [round(x, 4) for x in d["logits"]]
        return d


def pbo_cscv(M, n_blocks: int = 16, metric=None) -> PBOResult:
    """
    Bailey, Borwein, Lopez de Prado, Zhu (2017).
    M: matrice T x N di rendimenti (righe = periodi, colonne = varianti provate).
    """
    M = np.asarray(M, dtype=float)
    T, N = M.shape
    if N < 2:
        raise ValueError("servono almeno 2 varianti")
    if n_blocks % 2 or n_blocks < 2:
        raise ValueError("n_blocks deve essere pari")
    if metric is None:
        def metric(x):
            sd = x.std(axis=0, ddof=1)
            return np.where(sd > 0, x.mean(axis=0) / np.where(sd > 0, sd, 1), 0.0)
    blocks = np.array_split(np.arange(T), n_blocks)
    logits, is_best, oos_best = [], [], []
    combs = list(combinations(range(n_blocks), n_blocks // 2))
    for J in combs:
        Jc = [b for b in range(n_blocks) if b not in J]
        idx_is = np.concatenate([blocks[b] for b in J])
        idx_oos = np.concatenate([blocks[b] for b in Jc])
        p_is, p_oos = metric(M[idx_is]), metric(M[idx_oos])
        n_star = int(np.argmax(p_is))
        # rango relativo OOS in (0,1): (rango 1..N) / (N+1)
        rank = (np.argsort(np.argsort(p_oos))[n_star] + 1) / (N + 1)
        logits.append(math.log(rank / (1 - rank)))
        is_best.append(p_is[n_star])
        oos_best.append(p_oos[n_star])
    slope = float(np.polyfit(is_best, oos_best, 1)[0]) if len(set(is_best)) > 1 else 0.0
    logits_arr = np.array(logits)
    return PBOResult(pbo=float((logits_arr <= 0).mean()), n_combinations=len(combs),
                     logits=logits, perf_degradation_slope=slope)


# ---------------------------------------------------------------------------
# Bootstrap stazionario (Politis-Romano 1994) per l'intervallo di confidenza dello Sharpe
# ---------------------------------------------------------------------------
def sharpe_ci_bootstrap(returns, periods: int = 252, mean_block: int = 20,
                        n_boot: int = 2000, ci: float = 0.90, seed: int = 7) -> tuple[float, float]:
    """Intervallo di confidenza dello Sharpe annualizzato con blocchi di lunghezza
    geometrica: rispetta l'autocorrelazione, a differenza del bootstrap i.i.d."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    # versione vettoriale: a ogni passo si riparte da un punto a caso con prob. 1/mean_block,
    # altrimenti si prosegue in modo circolare dal punto precedente
    restart = rng.random((n_boot, n)) < 1.0 / mean_block
    restart[:, 0] = True
    start = rng.integers(n, size=(n_boot, n))
    last = np.maximum.accumulate(np.where(restart, t, 0), axis=1)
    idx = (np.take_along_axis(start, last, axis=1) + t - last) % n
    x = r[idx]
    sd = x.std(axis=1, ddof=1)
    out = np.where(sd > 0, x.mean(axis=1) / np.where(sd > 0, sd, 1) * math.sqrt(periods), 0.0)
    lo, hi = np.quantile(out, [(1 - ci) / 2, 1 - (1 - ci) / 2])
    return float(lo), float(hi)
