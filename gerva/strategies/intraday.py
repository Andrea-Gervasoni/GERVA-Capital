"""
Strategie intraday e il loro simulatore.

Convenzione: `desired[k]` e' la posizione (-1..+1) DECISA alla chiusura della barra k con dati <= k;
viene tenuta dalla chiusura di k alla chiusura di k+1. Ogni cambio di posizione paga `cost_side` per
unita' di controvalore. Con `flat_at_close` l'ultima barra di ogni seduta forza la posizione a zero:
nessun rischio di gap notturno, nessun costo di finanziamento.

Limite dichiarato: l'esecuzione e' al prezzo di chiusura della barra della decisione piu' il costo.
Con barre da 1 minuto e' quasi l'apertura della barra successiva; con barre da 30 o 60 minuti e'
un'approssimazione ottimistica di pochi punti base, che va coperta dal costo ipotizzato.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .. import indicators as ind


def simulate(bars: pd.DataFrame, desired: pd.Series, cost_side: float = 0.0002, leverage: pd.Series | float = 1.0,
             flat_at_close: bool = True) -> pd.DataFrame:
    """Restituisce una tabella giornaliera: ret (netto), gross_ret (senza costi), trades (cambi di posizione), lev."""
    day = pd.Series(bars.index.normalize(), index=bars.index)
    pos = desired.reindex(bars.index).fillna(0.0).clip(-1.0, 1.0).copy()
    last_of_day = day != day.shift(-1)
    if flat_at_close:
        pos[last_of_day] = 0.0
    r = bars["close"].pct_change(fill_method=None).fillna(0.0)
    new_day = day != day.shift(1)
    if flat_at_close:
        r[new_day] = 0.0                                   # tra una seduta e l'altra si e' fuori
    held = pos.shift(1).fillna(0.0)
    turn = (pos - held).abs()
    L = pd.Series(leverage, index=bars.index) if np.ndim(leverage) == 0 else \
        pd.Series(leverage.reindex(day.values).to_numpy(), index=bars.index).fillna(0.0)
    gross = L * held * r
    cost = L * turn * cost_side
    out = pd.DataFrame(dict(gross_ret=gross.groupby(day).sum(), cost=cost.groupby(day).sum(),
                            trades=(turn > 0).groupby(day).sum(), lev=L.groupby(day).first()))
    out["ret"] = out["gross_ret"] - out["cost"]
    return out


def daily_vol_leverage(daily_close: pd.Series, target_daily: float = 0.02, lookback: int = 14,
                       max_leverage: float = 4.0) -> pd.Series:
    """Leva del giorno d = min(tetto, vol obiettivo / vol giornaliera degli ultimi `lookback` giorni PRIMA di d)."""
    v = daily_close.pct_change(fill_method=None).rolling(lookback, min_periods=lookback).std().shift(1)
    return (target_daily / v.where(v > 0)).clip(upper=max_leverage)


# ---------------------------------------------------------------------------
# 1. VWAP trend (Zarattini & Aziz 2023): long sopra il VWAP di seduta, short sotto
# ---------------------------------------------------------------------------
def vwap_trend(bars: pd.DataFrame, deadband: float = 0.0, long_only: bool = False) -> pd.Series:
    """deadband: fascia attorno al VWAP (frazione del prezzo) dentro la quale si tiene la posizione che si ha."""
    vw = ind.session_vwap(bars)
    d = bars["close"] / vw - 1.0
    raw = pd.Series(np.where(d > deadband, 1.0, np.where(d < -deadband, -1.0, np.nan)), index=bars.index)
    day = pd.Series(bars.index.normalize(), index=bars.index)
    pos = raw.groupby(day).ffill().fillna(0.0)
    return pos.clip(lower=0.0) if long_only else pos


# ---------------------------------------------------------------------------
# 2. Momentum intraday fuori dalla "zona di rumore" (Zarattini, Aziz, Barbon 2024)
# ---------------------------------------------------------------------------
def noise_breakout(bars: pd.DataFrame, lookback: int = 14, stop: str = "band", vwap: pd.Series | None = None) -> pd.Series:
    """bars: barre alla frequenza di DECISIONE (es. 30 minuti), colonne open, close (+ high, low, volume per il VWAP).
    Long se la chiusura supera la banda alta, short se scende sotto la bassa.
    stop="band": si esce quando il prezzo rientra nella banda.
    stop="vwap": per il long lo stop e' max(banda alta, VWAP); per lo short min(banda bassa, VWAP)."""
    na = ind.noise_area(bars, lookback)
    c = bars["close"].to_numpy()
    up, lo = na["upper"].to_numpy(), na["lower"].to_numpy()
    if stop == "vwap":
        vw = (ind.session_vwap(bars) if vwap is None else vwap.reindex(bars.index)).to_numpy()
        stop_long, stop_short = np.fmax(up, vw), np.fmin(lo, vw)
    else:
        stop_long, stop_short = up, lo
    day = bars.index.normalize().to_numpy()
    pos = np.zeros(len(c))
    cur = 0.0
    for i in range(len(c)):
        if i == 0 or day[i] != day[i - 1]:
            cur = 0.0
        if not np.isfinite(up[i]):
            pos[i] = 0.0
            continue
        if cur > 0 and c[i] < stop_long[i]:
            cur = 0.0
        elif cur < 0 and c[i] > stop_short[i]:
            cur = 0.0
        if cur == 0.0:
            if c[i] > up[i]:
                cur = 1.0
            elif c[i] < lo[i]:
                cur = -1.0
        pos[i] = cur
    return pd.Series(pos, index=bars.index)


# ---------------------------------------------------------------------------
# 3. Momentum dell'ultima mezz'ora (Gao, Han, Li, Zhou 2018; Baltussen et al. 2021)
# ---------------------------------------------------------------------------
def last_half_hour(bars30: pd.DataFrame, prev_close: pd.Series | None = None) -> pd.Series:
    """Alle 15:30 si prende il segno del rendimento dalla chiusura di ieri (o dall'apertura) alle 15:30
    e lo si tiene fino alle 16:00. bars30: barre da 30 minuti con indice = ORARIO DI FINE BARRA."""
    day = pd.Series(bars30.index.normalize(), index=bars30.index)
    ref = bars30["open"].groupby(day).transform("first") if prev_close is None else \
        pd.Series(prev_close.reindex(day.values).to_numpy(), index=bars30.index)
    rod = bars30["close"] / ref - 1.0
    is_1530 = (bars30.index.hour == 15) & (bars30.index.minute == 30)
    return pd.Series(np.where(is_1530, np.sign(rod), 0.0), index=bars30.index)


def resample_session(bars: pd.DataFrame, minutes: int = 30, start: str = "09:30", end: str = "16:00") -> pd.DataFrame:
    """Da barre da 1 minuto (indice = inizio barra, ora di New York) a barre da `minutes` con indice = FINE barra.
    Aggiunge `vwap`: il VWAP di seduta calcolato sui minuti (se c'e' il volume) o il prezzo medio nel tempo (TWAP)."""
    b = bars.between_time(start, end, inclusive="left")
    has_vol = "volume" in b and b["volume"].fillna(0).sum() > 0
    b = b.assign(volume=b["volume"] if has_vol else 1.0)
    vw = ind.session_vwap(b)
    agg = dict(open="first", high="max", low="min", close="last", volume="sum")
    r = b.resample(f"{minutes}min", label="right", closed="left").agg(agg).dropna(subset=["close"])
    r["vwap"] = vw.resample(f"{minutes}min", label="right", closed="left").last().reindex(r.index)
    r.attrs["vwap_kind"] = "vwap" if has_vol else "twap"
    return r
