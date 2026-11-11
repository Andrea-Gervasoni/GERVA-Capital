"""
Indicatori. Regola unica: il valore alla riga t usa solo dati con indice <= t.
Chi li usa per decidere un peso deve poi applicare quel peso dal periodo SUCCESSIVO (lo fa il motore).

VWAP (prezzo medio ponderato per i volumi), ancorato all'inizio della seduta:

    VWAP_k = somma_{j<=k}(P_j * V_j) / somma_{j<=k}(V_j),     P_j = (massimo + minimo + chiusura) / 3

E' il prezzo medio pagato da chi ha scambiato nella seduta: nasce come metro di qualita' dell'esecuzione
(Berkowitz, Logue, Noser 1988), non come segnale. Qui lo si usa in tutti e due i modi e lo si misura.

GEX (esposizione gamma dei dealer), convenzione SqueezeMetrics:

    GEX = somma_strike( Gamma_call * OI_call - Gamma_put * OI_put ) * 100 * S      (dollari per 1% di movimento)

sotto l'ipotesi che i dealer siano lunghi di call e corti di put. Gamma di Black-Scholes:
    Gamma = phi(d1) / (S * sigma * sqrt(T)),   d1 = [ln(S/K) + (r + sigma^2/2) T] / (sigma sqrt(T))
GEX > 0: i dealer comprano sui ribassi e vendono sui rialzi (smorzano); GEX < 0: inseguono il prezzo (amplificano).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import norm


# ---------------------------------------------------------------------------
# Volatilita' e momentum
# ---------------------------------------------------------------------------
def ewma_vol(ret: pd.DataFrame | pd.Series, span: int = 32, periods: int = 252, min_periods: int = 20):
    return ret.ewm(span=span, min_periods=min_periods).std() * math.sqrt(periods)


def total_return(close: pd.DataFrame | pd.Series, lookback: int):
    return close / close.shift(lookback) - 1.0


def ibs(high, low, close):
    """Internal Bar Strength: dove chiude la barra dentro il suo intervallo (0 = sul minimo, 1 = sul massimo)."""
    rng = (high - low)
    return ((close - low) / rng.where(rng > 0)).clip(0, 1)


# ---------------------------------------------------------------------------
# VWAP di seduta
# ---------------------------------------------------------------------------
def session_vwap(bars: pd.DataFrame, session: pd.Series | None = None) -> pd.Series:
    """bars: indice temporale, colonne high, low, close, volume. session: chiave di seduta (default: la data).
    Barre senza volume non spostano il VWAP; prima del primo volume vale il prezzo tipico."""
    key = pd.Series(bars.index.normalize(), index=bars.index) if session is None else session
    tp = (bars["high"] + bars["low"] + bars["close"]) / 3.0
    v = bars["volume"].fillna(0.0)
    num = (tp * v).groupby(key).cumsum()
    den = v.groupby(key).cumsum()
    return (num / den.where(den > 0)).fillna(tp)


def vwap_bands(bars: pd.DataFrame, k: float = 1.0, session: pd.Series | None = None):
    """VWAP +- k deviazioni standard ponderate per il volume, cumulate nella seduta."""
    key = pd.Series(bars.index.normalize(), index=bars.index) if session is None else session
    tp = (bars["high"] + bars["low"] + bars["close"]) / 3.0
    v = bars["volume"].fillna(0.0)
    den = v.groupby(key).cumsum()
    vw = (tp * v).groupby(key).cumsum() / den.where(den > 0)
    var = ((tp * tp * v).groupby(key).cumsum() / den.where(den > 0) - vw * vw).clip(lower=0.0)
    sd = np.sqrt(var)
    return vw.fillna(tp), (vw + k * sd).fillna(tp), (vw - k * sd).fillna(tp)


# ---------------------------------------------------------------------------
# GEX
# ---------------------------------------------------------------------------
def bs_gamma(S: float, K, T: float, sigma, r: float = 0.0):
    K = np.asarray(K, float)
    sigma = np.asarray(sigma, float)
    T = max(T, 1e-6)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return norm.pdf(d1) / (S * sigma * math.sqrt(T))


def gex_from_chain(chain: pd.DataFrame, spot: float, r: float = 0.0, multiplier: int = 100) -> dict:
    """GEX 'ingenuo' da una catena di opzioni: colonne strike, expiry_years, iv, oi, type ('C' o 'P').
    Restituisce il totale (dollari per 1% di movimento), il profilo per strike e il livello di 'gamma flip'
    (prezzo al quale il GEX totale, ricalcolato spostando lo spot, cambia segno)."""
    c = chain.copy()
    sign = np.where(c["type"].str.upper().str[0] == "C", 1.0, -1.0)

    def total(s):
        g = np.array([bs_gamma(s, k, t, iv, r) for k, t, iv in zip(c["strike"], c["expiry_years"], c["iv"])])
        return g * c["oi"].to_numpy(float) * multiplier * s * s * 0.01 * sign

    per = total(spot)
    grid = np.linspace(spot * 0.85, spot * 1.15, 121)
    tot = np.array([total(s).sum() for s in grid])
    flip = None
    cross = np.where(np.diff(np.sign(tot)) != 0)[0]
    if len(cross):
        i = cross[np.argmin(np.abs(grid[cross] - spot))]
        x0, x1, y0, y1 = grid[i], grid[i + 1], tot[i], tot[i + 1]
        flip = float(x0 - y0 * (x1 - x0) / (y1 - y0)) if y1 != y0 else float(x0)
    by_strike = pd.Series(per, index=c["strike"].to_numpy()).groupby(level=0).sum()
    return dict(gex=float(per.sum()), flip=flip, by_strike=by_strike,
                call_wall=float(by_strike.idxmax()), put_wall=float(by_strike.idxmin()))


def gex_features(gex: pd.Series, window: int = 252) -> pd.DataFrame:
    """Trasforma la serie GEX (pubblicata dopo la chiusura di t) in grandezze usabili per decidere a t:
    segno, rango percentile mobile (0..1) e z-score mobile. Nessuna usa dati futuri: la finestra guarda indietro."""
    g = gex.astype(float)
    rank = g.rolling(window, min_periods=window // 2).rank(pct=True)
    mu = g.rolling(window, min_periods=window // 2).mean()
    sd = g.rolling(window, min_periods=window // 2).std()
    return pd.DataFrame(dict(gex=g, neg=(g < 0).astype(float), rank=rank, z=(g - mu) / sd))


# ---------------------------------------------------------------------------
# "Zona di rumore" intraday (Zarattini, Aziz, Barbon 2024)
# ---------------------------------------------------------------------------
def noise_area(bars: pd.DataFrame, lookback: int = 14) -> pd.DataFrame:
    """Per ogni barra: sigma = media, sugli ultimi `lookback` giorni PRECEDENTI, di |chiusura/apertura_seduta - 1|
    alla stessa ora. Bande: max(apertura, chiusura di ieri) * (1 + sigma) e min(...) * (1 - sigma).
    bars: indice temporale, colonne open, close. Restituisce upper, lower, day_open, prev_close."""
    day = bars.index.normalize()
    tod = bars.index.time
    day_open = bars["open"].groupby(day).transform("first")
    move = (bars["close"] / day_open - 1.0).abs()
    wide = pd.DataFrame({"m": move.values, "d": day, "t": tod}).pivot_table(index="d", columns="t", values="m")
    sig = wide.rolling(lookback, min_periods=lookback).mean().shift(1)          # solo giorni precedenti
    sig_long = sig.stack(future_stack=True).rename("sigma")
    idx = pd.MultiIndex.from_arrays([day, tod])
    sigma = pd.Series(sig_long.reindex(idx).to_numpy(), index=bars.index)
    last_close = bars["close"].groupby(day).last()
    prev_close = pd.Series(last_close.shift(1).reindex(day).to_numpy(), index=bars.index)
    up_ref = np.maximum(day_open, prev_close.fillna(day_open))
    dn_ref = np.minimum(day_open, prev_close.fillna(day_open))
    return pd.DataFrame(dict(upper=up_ref * (1 + sigma), lower=dn_ref * (1 - sigma), sigma=sigma,
                             day_open=day_open, prev_close=prev_close))
