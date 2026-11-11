"""
Allocazione del capitale tra strategie e leva di portafoglio.

Scelta: parita' di rischio (pesi inversamente proporzionali alla volatilita' recente di ogni strategia).
Motivo: non richiede di stimare i rendimenti attesi, che sono la grandezza stimata peggio (l'errore standard
di uno Sharpe su 5 anni e' circa 0,45). Alternative scartate: media-varianza (amplifica l'errore di stima),
pesi uguali (lascia che la strategia piu' volatile domini il rischio), Kelly per strategia (richiede i
rendimenti attesi).

Tutte le funzioni restituiscono grandezze "note il giorno prima": si possono moltiplicare direttamente per i
rendimenti dello stesso giorno senza look-ahead.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def risk_parity(S: pd.DataFrame, window: int = 180, min_periods: int = 90, periods: int = 365,
                rebalance: str = "M", cap: float = 0.60, floor: float = 0.5) -> pd.DataFrame:
    """Pesi (somma 1) dalle volatilita' degli ultimi `window` giorni, ricalcolati a inizio mese.
    cap: nessuna strategia sopra questa quota (l'eccesso resta in cassa).
    floor: la volatilita' usata non scende sotto questa frazione della volatilita' di lungo periodo della
    strategia. Senza, una strategia rimasta in cassa per mesi (volatilita' quasi zero) si prenderebbe tutto il
    capitale proprio mentre non lo usa, e rientrerebbe sul mercato con un peso enorme."""
    vol = S.rolling(window, min_periods=min_periods).std() * math.sqrt(periods)
    vol = np.maximum(vol, floor * S.expanding(min_periods=min_periods).std() * math.sqrt(periods))
    iv = 1.0 / vol.where(vol > 0)
    a = iv.div(iv.sum(axis=1), axis=0).clip(upper=cap)
    a = a.shift(1)
    if rebalance == "M":
        m = pd.Series(a.index.to_period("M"), index=a.index)
        a = a.where(m != m.shift(1)).ffill()
    return a.dropna(how="all").fillna(0.0)


def combine(S: pd.DataFrame, a: pd.DataFrame) -> pd.Series:
    return (a * S.reindex(a.index)).sum(axis=1)


def vol_target_leverage(port: pd.Series, target: float, window: int = 60, cap: float = 2.0,
                        periods: int = 365, min_periods: int = 30) -> pd.Series:
    """Leva = vol obiettivo / vol realizzata degli ultimi `window` giorni, con tetto. Nota il giorno prima."""
    v = (port.rolling(window, min_periods=min_periods).std() * math.sqrt(periods)).shift(1)
    return (target / v.where(v > 0)).clip(upper=cap).fillna(0.0)


def kelly_from_sharpe(sharpe: float, vol: float, fraction: float = 0.5) -> float:
    """Leva di Kelly in tempo continuo per un portafoglio di Sharpe e volatilita' dati: L* = Sharpe / vol.
    La crescita e' g(L) = L*mu - L^2*sigma^2/2: massima a L*, nulla a 2*L*, negativa oltre."""
    return fraction * sharpe / vol if vol > 0 else 0.0


def ruin_probability(fraction_of_kelly: float, level: float) -> float:
    """Probabilita' di scendere PRIMA O POI alla frazione `level` del capitale (0<level<1) giocando una frazione
    c di Kelly, in tempo continuo: level^(2/c - 1). A Kelly pieno il dimezzamento ha probabilita' 50%,
    a mezzo Kelly 12,5%, a un quarto 0,8%. (Thorp 2006; MacLean, Thorp, Ziemba 2010)"""
    c = fraction_of_kelly
    if c <= 0:
        return 0.0
    if c >= 2:
        return 1.0
    return float(level ** (2.0 / c - 1.0))
