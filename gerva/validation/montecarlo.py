"""
Monte Carlo sui rendimenti: bootstrap a blocchi stazionario (Politis & Romano 1994).

Perche' a blocchi: i rendimenti hanno volatilita' a grappoli; ricampionare giorni singoli distrugge i
grappoli e sottostima le cadute. Con blocchi di lunghezza media `block` i periodi brutti restano interi.

Cosa NON fa: non inventa crisi peggiori di quelle nel campione. Per questo `stress()` aggiunge a mano
gli scenari che la storia della strategia non contiene (gap, exchange che fallisce, correlazioni a 1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _block_index(n: int, horizon: int, block: float, rng: np.random.Generator, n_paths: int) -> np.ndarray:
    idx = np.empty((n_paths, horizon), dtype=np.int64)
    start = rng.integers(0, n, size=n_paths)
    idx[:, 0] = start
    jump = rng.random((n_paths, horizon)) < 1.0 / block
    fresh = rng.integers(0, n, size=(n_paths, horizon))
    for t in range(1, horizon):
        idx[:, t] = np.where(jump[:, t], fresh[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def paths(ret, horizon: int, n_paths: int = 5000, block: float = 20.0, seed: int = 7) -> np.ndarray:
    """Matrice n_paths x horizon di rendimenti ricampionati. `ret` puo' essere una serie o una tabella
    (in quel caso si ricampionano le RIGHE: le correlazioni tra colonne restano quelle osservate)."""
    x = np.asarray(pd.DataFrame(ret).dropna(), float)
    rng = np.random.default_rng(seed)
    idx = _block_index(len(x), horizon, block, rng, n_paths)
    out = x[idx]                                    # n_paths x horizon x k
    return out[:, :, 0] if out.shape[2] == 1 else out


def outcomes(sim: np.ndarray, ruin_level: float = 0.5, periods: int = 252, month: int = 21) -> dict:
    """Riassunto di una simulazione (n_paths x horizon di rendimenti del PORTAFOGLIO).
    ruin_level: frazione del capitale iniziale sotto la quale il percorso conta come 'rovina'."""
    eq = np.cumprod(1.0 + np.clip(sim, -1.0, None), axis=1)
    peak = np.maximum.accumulate(eq, axis=1)
    mdd = (eq / peak - 1.0).min(axis=1)
    final = eq[:, -1]
    years = sim.shape[1] / periods
    cagr = np.where(final > 0, final ** (1.0 / years) - 1.0, -1.0)
    nm = sim.shape[1] // month
    mret = np.prod(1.0 + sim[:, :nm * month].reshape(sim.shape[0], nm, month), axis=2) - 1.0
    q = lambda a, p: float(np.quantile(a, p))
    return dict(
        anni=round(years, 2),
        cagr_p05=q(cagr, .05), cagr_p25=q(cagr, .25), cagr_p50=q(cagr, .50), cagr_p75=q(cagr, .75), cagr_p95=q(cagr, .95),
        maxdd_p50=q(mdd, .50), maxdd_p05=q(mdd, .05), maxdd_p01=q(mdd, .01),
        p_perdita=float((final < 1.0).mean()),
        p_rovina=float((eq.min(axis=1) <= ruin_level).mean()),
        p_dd_30=float((mdd <= -0.30).mean()), p_dd_50=float((mdd <= -0.50).mean()),
        mese_medio=float(mret.mean()), mese_p05=q(mret, .05), mese_p95=q(mret, .95),
        p_mese_ge_20=float((mret >= 0.20).mean()), p_mese_le_m20=float((mret <= -0.20).mean()),
        finale_p05=q(final, .05), finale_p50=q(final, .50), finale_p95=q(final, .95),
    )


def leverage_sweep(ret: pd.Series, levs, rf_daily: float = 0.0, borrow_spread: float = 0.015, horizon: int = 756,
                   n_paths: int = 4000, block: float = 20.0, ruin_level: float = 0.5, periods: int = 252,
                   seed: int = 7, shock: tuple[float, float] | None = None) -> pd.DataFrame:
    """Per ogni leva: distribuzione del CAGR, cadute, probabilita' di rovina, probabilita' di un mese >= 20%.
    La leva e' ribilanciata ogni giorno (come un conto a margine tenuto a leva costante).
    shock=(p, taglia): ogni giorno, con probabilita' p, il portafoglio NON a leva perde `taglia` in piu'
    (evento che il campione non contiene: gap, sospensione, controparte)."""
    base = paths(ret, horizon, n_paths, block, seed)
    rng = np.random.default_rng(seed + 1)
    if shock:
        base = base - (rng.random(base.shape) < shock[0]) * shock[1]
    rows = []
    for L in levs:
        debt = max(L - 1.0, 0.0)
        cash = max(1.0 - L, 0.0)
        sim = L * base - debt * (rf_daily + borrow_spread / periods) + cash * rf_daily
        o = outcomes(sim, ruin_level, periods, month=max(int(round(periods / 12)), 1))
        o["leva"] = L
        rows.append(o)
    return pd.DataFrame(rows).set_index("leva")


def kelly_leverage(ret: pd.Series, rf_daily: float = 0.0, borrow_spread: float = 0.015, periods: int = 252,
                   grid=None) -> tuple[float, pd.Series]:
    """Leva che massimizza la crescita logaritmica media NEL CAMPIONE (Kelly empirico, senza ipotesi di normalita').
    E' un tetto teorico, non un consiglio: l'errore di stima del rendimento medio la gonfia sempre."""
    x = ret.dropna().to_numpy(float)
    grid = np.arange(0.25, 20.01, 0.25) if grid is None else np.asarray(grid, float)
    g = []
    for L in grid:
        r = L * x - max(L - 1.0, 0.0) * (rf_daily + borrow_spread / periods) + max(1.0 - L, 0.0) * rf_daily
        g.append(-np.inf if (r <= -1.0).any() else np.log1p(r).mean() * periods)
    s = pd.Series(g, index=grid)
    return float(s.idxmax()), s
