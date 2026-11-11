"""
Strategie giornaliere. Ogni funzione restituisce PESI OBIETTIVO decisi alla chiusura di t con dati <= t.
Il ritardo di esecuzione lo applica il motore (gerva.backtest.daily.run), mai la strategia.

Scelta di progetto: dove possibile NON ci sono parametri da ottimizzare. Si media su una griglia larga di
orizzonti (insieme di segnali), cosi' non esiste "il parametro migliore" da sovradattare.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .. import indicators as ind


# ---------------------------------------------------------------------------
# Mattoni
# ---------------------------------------------------------------------------
def vol_target(W: pd.DataFrame, ret: pd.DataFrame, target: float, span: int = 40, periods: int = 252,
               max_leverage: float = 2.0) -> pd.DataFrame:
    """Riscalamento a volatilita' obiettivo usando la volatilita' REALIZZATA del portafoglio con i pesi di oggi
    (matrice di covarianza EWMA dei rendimenti fino a t). Il moltiplicatore ha un tetto."""
    W = W.reindex(ret.index).fillna(0.0)
    r = ret[W.columns].fillna(0.0)
    # rendimento "a pesi di oggi" sugli ultimi giorni: proxy della volatilita' ex-ante, tutta nel passato
    cov = r.ewm(span=span, min_periods=span // 2).cov()
    out = np.zeros(len(W))
    Wv = W.to_numpy()
    cols = list(W.columns)
    dates = W.index
    cov_by_date = {d: m.to_numpy() for d, m in cov.groupby(level=0)}
    for i, d in enumerate(dates):
        m = cov_by_date.get(d)
        w = Wv[i]
        if m is None or not np.isfinite(m).all() or not w.any():
            continue
        v = math.sqrt(max(float(w @ m @ w), 0.0) * periods)
        out[i] = min(target / v, max_leverage / max(np.abs(w).sum(), 1e-9)) if v > 0 else 0.0
    return W.mul(pd.Series(out, index=dates), axis=0)


def inverse_vol(ret: pd.DataFrame, span: int = 60, periods: int = 252) -> pd.DataFrame:
    v = ind.ewma_vol(ret, span, periods)
    iv = 1.0 / v.where(v > 0)
    return iv.div(iv.sum(axis=1), axis=0)


# ---------------------------------------------------------------------------
# 1. Trend following (momentum in serie storica), insieme di orizzonti
# ---------------------------------------------------------------------------
def trend(close: pd.DataFrame, lookbacks=(21, 63, 126, 252), long_only: bool = False, asset_vol: float = 0.10,
          span: int = 60, periods: int = 252) -> pd.DataFrame:
    """Segnale = media dei segni del rendimento sugli orizzonti; peso = segnale * (vol obiettivo / vol) / N.
    Moskowitz, Ooi, Pedersen (2012); Hurst, Ooi, Pedersen (2017)."""
    ret = close.pct_change(fill_method=None)
    sig = sum(np.sign(ind.total_return(close, lb)) for lb in lookbacks) / len(lookbacks)
    if long_only:
        sig = sig.clip(lower=0.0)
    vol = ind.ewma_vol(ret, span, periods)
    n = close.notna().sum(axis=1).clip(lower=1)
    W = sig * (asset_vol / vol.where(vol > 0))
    return W.div(n, axis=0).where(close.notna()).fillna(0.0)


# ---------------------------------------------------------------------------
# 2. Momentum trasversale (i piu' forti dell'universo), tipicamente crypto
# ---------------------------------------------------------------------------
def xs_momentum(close: pd.DataFrame, dollar_volume: pd.DataFrame, lookbacks=(14, 28, 56), top: int = 5,
                universe: int = 20, rebalance: int = 7, trend_filter: pd.Series | None = None,
                min_history: int = 90) -> pd.DataFrame:
    """Ogni `rebalance` giorni: tra i `universe` strumenti piu' scambiati (volume medio a 30 giorni, noto a t)
    si tengono i `top` con il momentum medio piu' alto e POSITIVO, a pesi uguali. Solo long.
    trend_filter: serie booleana (es. BTC sopra la sua media): se False si resta in cassa."""
    adv = dollar_volume.rolling(30, min_periods=20).mean()
    age = close.notna().cumsum()
    mom = sum(ind.total_return(close, lb) for lb in lookbacks) / len(lookbacks)
    W = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    last = None
    for i, d in enumerate(close.index):
        if i % rebalance == 0:
            ok = (age.loc[d] >= min_history) & adv.loc[d].notna() & mom.loc[d].notna()
            liquid = adv.loc[d][ok].nlargest(universe).index
            m = mom.loc[d][liquid]
            pick = m[m > 0].nlargest(top).index
            last = pd.Series(0.0, index=close.columns)
            if len(pick) and (trend_filter is None or bool(trend_filter.get(d, False))):
                last[pick] = 1.0 / top                       # posti vuoti = cassa, non si concentra
        if last is not None:
            W.loc[d] = last
    return W


# ---------------------------------------------------------------------------
# 3. Ritorno alla media di breve su un indice (IBS)
# ---------------------------------------------------------------------------
def ibs_reversion(high: pd.Series, low: pd.Series, close: pd.Series, enter: float = 0.2, exit_: float = 0.7,
                  trend_ma: int | None = 200) -> pd.Series:
    """Long quando la barra chiude nel 20% basso del suo intervallo; fuori quando chiude sopra il 70%.
    Opzionale: solo sopra la media a 200 giorni. Restituisce il peso (0 o 1)."""
    x = ind.ibs(high, low, close)
    up = close > close.rolling(trend_ma).mean() if trend_ma else pd.Series(True, index=close.index)
    pos = np.zeros(len(close))
    cur = 0.0
    xv, uv = x.to_numpy(), up.to_numpy()
    for i in range(len(close)):
        if cur == 0.0 and xv[i] < enter and uv[i]:
            cur = 1.0
        elif cur == 1.0 and (xv[i] > exit_):
            cur = 0.0
        pos[i] = cur
    return pd.Series(pos, index=close.index)


# ---------------------------------------------------------------------------
# 4. Leva a regime: sopra la media lunga a leva, sotto in cassa (Gayed & Bilello 2016)
# ---------------------------------------------------------------------------
def ma_regime(close: pd.Series, ma: int = 200, on: float = 2.0, off: float = 0.0, buffer: float = 0.01) -> pd.Series:
    """Con una fascia di isteresi dell'1% per non entrare e uscire a ogni sfioramento."""
    m = close.rolling(ma).mean()
    pos = np.zeros(len(close))
    cur = 0.0
    cv, mv = close.to_numpy(), m.to_numpy()
    for i in range(len(close)):
        if np.isfinite(mv[i]):
            if cv[i] > mv[i] * (1 + buffer):
                cur = on
            elif cv[i] < mv[i] * (1 - buffer):
                cur = off
        pos[i] = cur
    return pd.Series(pos, index=close.index)


# ---------------------------------------------------------------------------
# 5. Premio per il rischio di volatilita': corti di volatilita' solo con la curva VIX in contango
# ---------------------------------------------------------------------------
def vix_term_structure(vix: pd.Series, vix3m: pd.Series, threshold: float = 0.95, weight: float = 1.0) -> pd.Series:
    """Peso sullo strumento corto di volatilita' (es. SVXY): `weight` se VIX/VIX3M < soglia, altrimenti 0."""
    ratio = (vix / vix3m).reindex(vix.index)
    return (ratio < threshold).astype(float) * weight


# ---------------------------------------------------------------------------
# 6. Regime GEX sull'indice
# ---------------------------------------------------------------------------
def gex_exposure(gex_rank: pd.Series, lo: float = 0.0, hi: float = 1.5, cut: float = 0.25) -> pd.Series:
    """Esposizione all'indice in funzione del rango percentile mobile del GEX (noto a fine t):
    sotto `cut` (gamma basso o negativo: mercato che amplifica) -> `lo`; sopra -> `hi`."""
    return pd.Series(np.where(gex_rank < cut, lo, hi), index=gex_rank.index).where(gex_rank.notna(), 0.0)


def vol_managed(ret: pd.Series, target: float = 0.15, span: int = 20, max_leverage: float = 2.0,
                periods: int = 252) -> pd.Series:
    """Esposizione inversa alla volatilita' recente (Moreira & Muir 2017)."""
    v = ind.ewma_vol(ret, span, periods, min_periods=10)
    return (target / v.where(v > 0)).clip(upper=max_leverage).fillna(0.0)


# ---------------------------------------------------------------------------
# 7. Carry sui perpetual: long spot, short perpetual, si incassa il funding
# ---------------------------------------------------------------------------
def funding_carry(spot: pd.Series, perp: pd.Series, funding_daily: pd.Series, fee_side: float = 0.0010,
                  min_funding_annual: float | None = None, lookback: int = 7, margin_frac: float = 0.5) -> pd.DataFrame:
    """Rendimento giornaliero, sul CAPITALE IMPEGNATO, di una posizione neutrale: 1 unita' long spot + 1 short perp.
    Capitale = spot (1) + margine del perp (`margin_frac`), quindi il rendimento si divide per 1 + margin_frac.
    funding_daily: somma dei funding del giorno (positivo = incassato dallo short).
    min_funding_annual: se dato, si sta dentro solo quando il funding medio degli ultimi `lookback` giorni
    (noti a t) annualizzato supera la soglia; ogni entrata e ogni uscita paga le commissioni su DUE gambe.
    Colonne: ret (netto), pos (0/1), basis (perp/spot - 1)."""
    idx = spot.index
    f = funding_daily.reindex(idx).fillna(0.0)
    basis = perp.reindex(idx) / spot - 1.0
    hedge = spot.pct_change(fill_method=None) - perp.reindex(idx).pct_change(fill_method=None)      # long spot, short perp
    if min_funding_annual is None:
        pos = pd.Series(1.0, index=idx)
    else:
        avg = f.rolling(lookback, min_periods=lookback).mean() * 365.0
        pos = (avg > min_funding_annual).astype(float)
    held = pos.shift(1).fillna(0.0)                              # decisione a t, in posizione da t+1
    trade = held.diff().abs().fillna(held.abs())
    gross = held * (hedge.fillna(0.0) + f)
    ret = (gross - trade * 2.0 * fee_side) / (1.0 + margin_frac)
    return pd.DataFrame(dict(ret=ret, pos=held, basis=basis))


def hold(W: pd.DataFrame, every: int | str = 5) -> pd.DataFrame:
    """Tiene fermo l'obiettivo tra un ribilanciamento e l'altro. every: numero di barre, oppure "M" (ultima
    barra del mese presente nell'indice, senza guardare avanti: il mese e' finito quando la barra dopo ne apre un altro
    -> la decisione si prende sulla PRIMA barra del mese nuovo con i dati fino a quel giorno)."""
    if every == "M":
        first = pd.Series(W.index.to_period("M"), index=W.index)
        mask = (first != first.shift(1)).to_numpy()
    else:
        mask = (np.arange(len(W)) % int(every)) == 0
    return W.where(pd.Series(mask, index=W.index), axis=0).ffill().fillna(0.0)
