"""
Libreria di segnali. Ogni funzione: prezzi (e dati ausiliari) fino a t -> pesi target decisi
alla chiusura di t. Nessuna funzione puo' guardare oltre t: lo verifica
quantlab.lookahead.truncation_test in tests/test_quantlab_lookahead.py per OGNI segnale.

Le prime funzioni riesprimono il nucleo di GERVA-Q (Pod Zero) per poterlo confrontare a pari
motore; le ultime sono i candidati con meccanismo pubblicato (alpha_research.md §1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TD = 252


def _vol(close: pd.DataFrame, span: int = 36, periods: int = TD) -> pd.DataFrame:
    return close.pct_change().ewm(span=span, min_periods=span).std() * np.sqrt(periods)


# ---------------------------------------------------------------------------
# Trend (nucleo di S1): crossover EWMA continui, long/flat, dimensionati a vol costante
# ---------------------------------------------------------------------------
def ewma_trend(close: pd.DataFrame, pairs=((8, 32), (16, 64), (32, 128), (64, 256)),
               asset_vol: float = 0.10, max_w: float = 0.25) -> pd.DataFrame:
    sd_px = close.diff().ewm(span=36, min_periods=36).std()
    fc = []
    for f, s in pairs:
        raw = (close.ewm(span=f, adjust=False).mean() - close.ewm(span=s, adjust=False).mean()) / sd_px
        scal = 10 / raw.abs().expanding(min_periods=252).mean()
        fc.append((raw * scal).clip(-20, 20))
    F = (sum(fc) / len(fc)).clip(lower=0) / 10
    W = (F * asset_vol / _vol(close) / close.shape[1]).clip(upper=max_w)
    g = W.sum(axis=1)
    W = W.div(g.where(g > 1, 1), axis=0)
    return W.where(close.notna()).fillna(0.0)


def tsmom(close: pd.DataFrame, lookback: int = 252, target_vol: float = 0.40) -> pd.DataFrame:
    """Moskowitz-Ooi-Pedersen 2012, versione long/flat (niente short sul conto retail)."""
    sig = np.sign(close / close.shift(lookback) - 1).clip(lower=0)
    W = sig * (target_vol / _vol(close, 60)) / close.shape[1]
    g = W.sum(axis=1)
    return W.div(g.where(g > 1, 1), axis=0).fillna(0.0)


def donchian(close: pd.DataFrame, entry: int = 55, exit_: int = 20) -> pd.DataFrame:
    """Breakout (nucleo di H2): entra sopra il massimo a `entry` periodi, esce sotto il minimo a `exit_`."""
    hi = close.rolling(entry).max().shift(1)
    lo = close.rolling(exit_).min().shift(1)
    out = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    for c in close.columns:
        x, h, l = close[c].values, hi[c].values, lo[c].values
        p, pos = 0.0, np.zeros(len(x))
        for i in range(len(x)):
            if np.isnan(h[i]):
                p = 0.0
            elif p == 0 and x[i] > h[i]:
                p = 1.0
            elif p == 1 and x[i] < l[i]:
                p = 0.0
            pos[i] = p
        out[c] = pos / close.shape[1]
    return out


# ---------------------------------------------------------------------------
# Momentum settoriale 12-1 (nucleo di S3) e versione dinamica alla Daniel-Moskowitz
# ---------------------------------------------------------------------------
def sector_momentum(close: pd.DataFrame, top: int = 3) -> pd.DataFrame:
    mom = close.shift(21) / close.shift(252) - 1
    ranks = mom.rank(axis=1, ascending=False)
    W = ((ranks <= top) & (mom > 0)).astype(float) / top
    # fine mese dal CALENDARIO dei giorni lavorativi (noto in anticipo), non dalla riga successiva
    # dei dati: altrimenti l'ultima riga di qualunque campione sembrerebbe un fine mese
    nxt = close.index + pd.offsets.BDay(1)
    month_end = pd.Series(nxt.month != close.index.month, index=close.index)
    return W.where(month_end, np.nan).ffill().fillna(0.0)


def dynamic_momentum_overlay(market: pd.Series, lookback_bear: int = 504, vol_win: int = 126,
                             vol_q: float = 0.8, cut: float = 0.5) -> pd.Series:
    """Moltiplicatore di esposizione per le strategie momentum (Daniel & Moskowitz 2016):
    si riduce quando il mercato e' in bear (rendimento a 24 mesi < 0) E la volatilita'
    e' nel quintile alto della propria storia (soglia calcolata solo col passato)."""
    bear = market / market.shift(lookback_bear) - 1 < 0
    vol = market.pct_change().rolling(vol_win).std()
    thr = vol.expanding(min_periods=vol_win * 2).quantile(vol_q)
    panic = bear & (vol > thr)
    return pd.Series(np.where(panic, cut, 1.0), index=market.index)


# ---------------------------------------------------------------------------
# Reversal di breve (nucleo di S4) e versione condizionata al VIX (Nagel 2012)
# ---------------------------------------------------------------------------
def rsi(close: pd.DataFrame, n: int = 2) -> pd.DataFrame:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def short_reversal(close: pd.DataFrame, market: pd.Series, max_pos: int = 6, rsi_entry: float = 10,
                   max_hold: int = 5, size_mult: pd.Series | None = None) -> pd.DataFrame:
    r2 = rsi(close, 2)
    up = close > close.rolling(200).mean()
    mkt_ok = market > market.rolling(200).mean()
    ex = close > close.rolling(5).mean()
    W = np.zeros(close.shape)
    hold: dict[int, int] = {}
    R2, UP, EX, MK = r2.values, up.values, ex.values, mkt_ok.values
    mult = np.ones(len(close)) if size_mult is None else size_mult.reindex(close.index).fillna(1.0).values
    for i in range(len(close)):
        for a in list(hold):
            hold[a] += 1
            if EX[i, a] or hold[a] >= max_hold:
                del hold[a]
        if MK[i] and len(hold) < max_pos:
            cand = [j for j in np.argsort(np.nan_to_num(R2[i], nan=1e9))
                    if R2[i, j] < rsi_entry and UP[i, j] and j not in hold]
            for j in cand[: max_pos - len(hold)]:
                hold[j] = 0
        for a in hold:
            W[i, a] = min(mult[i] / max_pos, 0.25)
    out = pd.DataFrame(W, index=close.index, columns=close.columns)
    g = out.sum(axis=1)
    return out.div(g.where(g > 1, 1), axis=0)


def vix_size_multiplier(vix: pd.Series, lo: float = 0.5, hi: float = 2.0, win: int = 252) -> pd.Series:
    """Nagel (2012): il premio della fornitura di liquidita' cresce col VIX.
    Moltiplicatore = VIX / mediana mobile del VIX (solo passato), limitato in [lo, hi]."""
    med = vix.rolling(win, min_periods=win // 2).median()
    return (vix / med).clip(lo, hi)


# ---------------------------------------------------------------------------
# Carry crypto come segnale di RISCHIO (Schmeling-Schrimpf-Todorov 2023)
# ---------------------------------------------------------------------------
def carry_risk_filter(basis_annual: pd.Series, q: float = 0.9, cut: float = 0.5,
                      min_obs: int = 180) -> pd.Series:
    """Un carry (base futures-spot annualizzata) estremo predice crash: quando supera il
    proprio quantile q storico (calcolato solo col passato) l'esposizione spot si riduce."""
    thr = basis_annual.expanding(min_periods=min_obs).quantile(q).shift(1)
    return pd.Series(np.where(basis_annual > thr, cut, 1.0), index=basis_annual.index)


# ---------------------------------------------------------------------------
# Mercati sintetici con risultato noto (per i test e per i canarini della Validazione)
# ---------------------------------------------------------------------------
def synthetic_market(n_days: int = 2520, n_assets: int = 8, seed: int = 0, trend_strength: float = 0.0,
                     vol: float = 0.15, corr: float = 0.3, start: str = "2010-01-01"):
    """Prezzi con autocorrelazione dei rendimenti di forza `trend_strength`
    (0 = rumore puro: nessuna strategia trend deve risultare significativa).
    Ritorna (open, close)."""
    rng = np.random.default_rng(seed)
    d = vol / np.sqrt(TD)
    cov = d * d * (corr * np.ones((n_assets, n_assets)) + (1 - corr) * np.eye(n_assets))
    eps = rng.multivariate_normal(np.zeros(n_assets), cov, size=n_days)
    r = np.zeros_like(eps)
    drift = np.zeros(n_assets)
    for t in range(n_days):
        # componente persistente: media mobile esponenziale dei rendimenti passati
        drift = 0.98 * drift + 0.02 * (r[t - 1] if t else 0)
        r[t] = eps[t] + trend_strength * drift * 50
    idx = pd.bdate_range(start, periods=n_days)
    cols = [f"A{i}" for i in range(n_assets)]
    close = pd.DataFrame(100 * np.exp(np.cumsum(r, axis=0)), index=idx, columns=cols)
    gap = rng.normal(0, d * 0.3, size=close.shape)
    open_ = close.shift(1).fillna(100) * np.exp(gap)
    return open_, close
