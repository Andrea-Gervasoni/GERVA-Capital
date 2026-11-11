"""
Metriche di performance. Tutto cio' che esce da qui descrive una serie di rendimenti: se la serie
viene da un backtest, i numeri sono SIMULATI e vanno presentati come tali.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import norm

EULER = 0.5772156649015329


def drawdown(ret: pd.Series) -> pd.Series:
    eq = (1.0 + ret.fillna(0.0)).cumprod()
    return eq / eq.cummax() - 1.0


def monthly(ret: pd.Series) -> pd.Series:
    r = ret.dropna()
    return (1.0 + r).groupby([r.index.year, r.index.month]).prod() - 1.0


def sharpe(ret: pd.Series, rf_daily: pd.Series | float = 0.0, periods: int = 252) -> float:
    x = (ret - rf_daily).dropna() if not np.isscalar(rf_daily) else ret.dropna() - rf_daily
    sd = x.std(ddof=1)
    return float(x.mean() / sd * math.sqrt(periods)) if sd > 0 else 0.0


def psr(ret: pd.Series, sr_star_annual: float = 0.0, periods: int = 252) -> float:
    """Probabilistic Sharpe Ratio (Bailey & Lopez de Prado 2012): P(Sharpe vero > soglia)."""
    x = ret.dropna().to_numpy(float)
    n = len(x)
    if n < 30 or x.std(ddof=1) == 0:
        return float("nan")
    sr = x.mean() / x.std(ddof=1)
    s0 = sr_star_annual / math.sqrt(periods)
    z = (x - x.mean()) / x.std(ddof=0)
    g3, g4 = float((z ** 3).mean()), float((z ** 4).mean())
    den = math.sqrt(max(1.0 - g3 * sr + (g4 - 1.0) / 4.0 * sr * sr, 1e-12))
    return float(norm.cdf((sr - s0) * math.sqrt(n - 1) / den))


def expected_max_sharpe(n_trials: int, var_trials_annual: float) -> float:
    """Sharpe annuo che ci si aspetta dal MIGLIORE di n tentativi senza alcuna abilita' (Bailey & Lopez de Prado 2014)."""
    if n_trials <= 1:
        return 0.0
    a = norm.ppf(1.0 - 1.0 / n_trials)
    b = norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    return math.sqrt(var_trials_annual) * ((1.0 - EULER) * a + EULER * b)


def dsr(ret: pd.Series, n_trials: int, var_trials_annual: float, periods: int = 252) -> float:
    """Deflated Sharpe Ratio: PSR contro lo Sharpe atteso dal migliore di n tentativi a caso."""
    return psr(ret, expected_max_sharpe(n_trials, var_trials_annual), periods)


def summary(ret: pd.Series, rf_daily: pd.Series | float = 0.0, periods: int = 252) -> dict:
    r = ret.dropna()
    if len(r) < 20:
        return {}
    years = len(r) / periods
    eq = (1.0 + r).cumprod()
    final = float(eq.iloc[-1])
    cagr = final ** (1.0 / years) - 1.0 if final > 0 else -1.0
    vol = float(r.std(ddof=1) * math.sqrt(periods))
    dd = drawdown(r)
    m = monthly(r)
    down = r[r < 0]
    sortino = float(r.mean() * periods / (math.sqrt((down ** 2).mean() * periods))) if len(down) else float("nan")
    # durata della caduta piu' lunga, in giorni
    under = (dd < 0).astype(int)
    longest = int((under.groupby((under == 0).cumsum()).cumsum()).max())
    return dict(
        anni=round(years, 2), cagr=cagr, vol=vol, sharpe=sharpe(r, rf_daily, periods), sortino=sortino,
        max_dd=float(dd.min()), calmar=cagr / abs(float(dd.min())) if dd.min() < 0 else float("nan"),
        dd_giorni=longest, skew=float(r.skew()), kurt=float(r.kurt()),
        mese_medio=float(m.mean()), mese_mediano=float(m.median()), mese_peggiore=float(m.min()),
        mese_migliore=float(m.max()), mesi_positivi=float((m > 0).mean()),
        mesi_ge_20=float((m >= 0.20).mean()), mesi_le_m20=float((m <= -0.20).mean()),
        giorno_peggiore=float(r.min()), psr0=psr(r - (rf_daily if np.isscalar(rf_daily) else rf_daily.reindex(r.index).fillna(0.0)), 0.0, periods),
    )


def fmt_table(rows: dict[str, dict], cols=("anni", "cagr", "vol", "sharpe", "max_dd", "mese_medio", "mese_peggiore",
                                           "mesi_ge_20")) -> str:
    """Tabella markdown. Percentuali per cagr, vol, max_dd, mesi."""
    pct = {"cagr", "vol", "max_dd", "mese_medio", "mese_mediano", "mese_peggiore", "mese_migliore", "mesi_positivi",
           "mesi_ge_20", "mesi_le_m20", "giorno_peggiore"}
    head = "| strategia | " + " | ".join(cols) + " |\n|---|" + "---:|" * len(cols)
    lines = [head]
    for name, s in rows.items():
        cells = []
        for c in cols:
            v = s.get(c, float("nan"))
            cells.append(f"{v:.1%}" if c in pct else (f"{v:.2f}" if isinstance(v, float) else str(v)))
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines)
