"""
Indicatore Gervasoni (GQ): qualita' del trend, in ombra.

    GQ(t) = [ TQ_moneta / 0,20 + TQ_BTC / 0,20 + VWM_moneta / 0,40 ] / 3          calcolato alla chiusura di t, usato da t+1

    TQ  = media degli efficiency ratio con segno a 10, 30, 60, 120 giorni:
          (ln C_t - ln C_{t-n}) / somma |variazioni giornaliere di ln C|.  1 = linea retta in salita, 0 = rumore.
    VWM = (C / VWAP ancorato all'apertura del mese - 1) / ATR%14, limitato a +-3 e diviso per 3:
          chi ha comprato nel mese e' in guadagno (non vende) o in perdita (vende ai rimbalzi)?
    Le tre scale (0,20 / 0,20 / 0,40) sono le deviazioni standard arrotondate delle componenti fino al 2022.

Che cosa dice la ricerca (research/v5/v5/a1_indicatore e validazione/ESITO.md, SIMULATO, BTC ETH SOL a ~11x):
  * come soglia d'ingresso "alta" (GQ >= 0,53) al posto della conviction: R medio +0,34 contro +0,24; dal 2023, sui prezzi dei
    perpetual, +0,25 contro +0,16; con il funding di Hyperliquid +0,22 contro +0,13;
  * il vantaggio (+0,09 R) NON e' distinguibile da zero: intervallo al 90% da -0,06 a +0,25; nel 2025-2026 rende circa zero;
  * correlazione 0,85 con la conviction: e' la stessa informazione di regime, misurata in modo continuo;
  * non batte il livello "eccezionale" della conviction e non funziona su altre 18 monete.

Per questo e' IN OMBRA: si calcola e si registra a ogni giro, non decide nulla. Diventa soglia d'ingresso solo se, dopo almeno
40 trade paper, i trade che avrebbe scelto hanno R medio superiore a quelli della conviction (cancello nel documento, 4.2).
Le soglie sono congelate: quantili del periodo di scelta (fino al 31/12/2022), mai ristimate dal vivo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SCALE = {"tq": 0.20, "btc": 0.20, "vwm": 0.40}
THRESHOLDS = {"eccezionale": 1.4205535120908974, "alta": 0.5317842685566442, "bassa": -0.5033858160836456}
HORIZONS = (10, 30, 60, 120)


def efficiency_ratio(log_close: pd.Series, n: int) -> pd.Series:
    """Spostamento netto su n giorni diviso per la strada percorsa (somma dei valori assoluti delle variazioni)."""
    path = log_close.diff().abs().rolling(n).sum()
    return (log_close - log_close.shift(n)) / path.where(path > 0)


def trend_quality(close: pd.Series) -> pd.Series:
    lc = np.log(close)
    return sum(efficiency_ratio(lc, n) for n in HORIZONS) / len(HORIZONS)


def month_vwap_distance(bars: pd.DataFrame, volume: pd.Series) -> pd.Series:
    """Distanza della chiusura dal VWAP ancorato all'apertura del mese, in unita' di ATR%14, in [-1, 1]."""
    tp = (bars["high"] + bars["low"] + bars["close"]) / 3
    m = bars.index.to_period("M")
    vw = (tp * volume).groupby(m).cumsum() / volume.groupby(m).cumsum()
    atr = ((bars["high"] - bars["low"]) / bars["close"]).rolling(14).mean()
    return ((bars["close"] / vw - 1) / atr).clip(-3, 3) / 3


def gq(bars: pd.DataFrame, volume: pd.Series, btc_close: pd.Series) -> pd.Series:
    """bars: open, high, low, close giornalieri; volume: volume giornaliero; btc_close: chiusure di BTC.
    Ogni valore usa solo dati fino alla propria riga."""
    tq = trend_quality(bars["close"])
    btc = trend_quality(btc_close).reindex(bars.index)
    vwm = month_vwap_distance(bars, volume.reindex(bars.index))
    return (tq / SCALE["tq"] + btc / SCALE["btc"] + vwm / SCALE["vwm"]) / 3


def tier(value: float | None) -> str:
    """'eccezionale' | 'alta' | 'media' | 'bassa'. Valore mancante: 'bassa' (nel dubbio, il livello piu' prudente)."""
    if value is None or value != value:
        return "bassa"
    if value >= THRESHOLDS["eccezionale"]:
        return "eccezionale"
    if value >= THRESHOLDS["alta"]:
        return "alta"
    return "bassa" if value <= THRESHOLDS["bassa"] else "media"
