"""
Il libro delle strategie in produzione: UNA definizione, usata sia dalla ricerca sia dal ciclo live.

Se il backtest e il live calcolassero i pesi con codice diverso, il backtest non direbbe nulla sul live.
Qui ogni strategia e' una funzione pura (dati -> pesi obiettivo sul capitale assegnato alla strategia);
`gerva.research.run` la passa al motore di backtest, `gerva.live.pipeline` ne legge l'ultima riga.

    CR-TREND   trend su BTC ed ETH, solo long, spot                (crypto)
    CR-XSMOM   momentum trasversale sulle 20 monete piu' scambiate (crypto)
    EQ-MR      ritorno alla media di breve su S&P 500 e Nasdaq 100 (azioni, via CFD o ETF)
    MA-TREND   trend lento su 17 ETF multi-asset, solo long        (multi-asset)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from ..backtest import Costs, run
from . import daily as SD

TREND_UNIVERSE = "SPY QQQ IWM EFA EEM TLT IEF LQD HYG GLD SLV DBC USO VNQ UUP FXE FXY".split()
CRYPTO_FEE = 0.0030          # spot su exchange UE: commissione taker + slippage, per lato
ETF_FEE = 0.0010             # ETF/ETP su conto piccolo: commissione minima + meta' spread
INDEX_FEE = 0.0005           # CFD o ETF su indice molto liquido
CFD_SPREAD = 0.015           # finanziamento notturno: tasso a breve + 1,5%


@dataclass(frozen=True)
class Sleeve:
    id: str
    name: str
    asset_class: str
    venue: str               # "crypto" oppure "ibkr"
    periods: int


SLEEVES = {
    "CR-TREND": Sleeve("CR-TREND", "Crypto trend BTC+ETH", "Crypto", "crypto", 365),
    "CR-XSMOM": Sleeve("CR-XSMOM", "Crypto momentum trasversale", "Crypto", "crypto", 365),
    "EQ-MR": Sleeve("EQ-MR", "Azioni ritorno alla media", "Azioni", "ibkr", 252),
    "MA-TREND": Sleeve("MA-TREND", "Trend multi-asset", "Multi-asset", "ibkr", 252),
}


# ---- pesi obiettivo --------------------------------------------------------
def cr_trend(close: pd.DataFrame) -> pd.DataFrame:
    """close: colonne BTC, ETH, indice giornaliero di calendario."""
    W = SD.trend(close[["BTC", "ETH"]], lookbacks=(30, 60, 120), long_only=True, asset_vol=0.40, span=30, periods=365)
    return SD.hold(W.clip(upper=0.5), 7)


def cr_xsmom(close: pd.DataFrame, dollar_volume: pd.DataFrame) -> pd.DataFrame:
    btc_up = close["BTC"] > close["BTC"].rolling(100).mean()
    return SD.xs_momentum(close, dollar_volume, (14, 28, 56), top=5, universe=20, rebalance=7, trend_filter=btc_up)


def xs_scale(raw_ret: pd.Series, target: float = 0.25) -> pd.Series:
    """Riduzione dell'esposizione di CR-XSMOM a volatilita' 25% (mai sopra 1x), nota il giorno prima."""
    v = (raw_ret.rolling(60, min_periods=30).std() * math.sqrt(365)).shift(1)
    return (target / v.where(v > 0)).clip(upper=1.0).fillna(0.3)


def eq_mr(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({s: 0.5 * SD.ibs_reversion(high[s], low[s], close[s], trend_ma=None) for s in ("SPY", "QQQ")})


def ma_trend(adj: pd.DataFrame) -> pd.DataFrame:
    c = adj[TREND_UNIVERSE].loc["2003":]
    R = c.pct_change(fill_method=None)
    # ribilanciamento MENSILE (21 sedute), non settimanale: la rotazione scende da 13,7 a 5,9 volte l'anno e lo Sharpe sale in
    # entrambi i periodi, a 10 pb (0,14 -> 0,32; verifica -0,18 -> 0,24) e a 50 pb (-0,52 -> 0,02) per ordine (13/11/2026,
    # revisione del sistema research/v5/v5/a10_sistema e verifica diretta). E' una scelta di costo: due valori provati, nessuna ottimizzazione.
    return SD.hold(SD.vol_target(SD.trend(c, lookbacks=(63, 126, 252), long_only=True), R, 0.10, max_leverage=1.0), 21)


# ---- rendimenti simulati (stesse ipotesi di costo della ricerca) -----------
def cr_trend_returns(close: pd.DataFrame, ret: pd.DataFrame, fee: float = CRYPTO_FEE, lag: int = 1):
    return run(cr_trend(close), ret[["BTC", "ETH"]], 0.0, Costs(trade=fee, cash_haircut=1.0), lag=lag, periods=365, band=0.03)


def cr_xsmom_returns(close: pd.DataFrame, dollar_volume: pd.DataFrame, ret: pd.DataFrame, fee: float = CRYPTO_FEE, lag: int = 1):
    return run(cr_xsmom(close, dollar_volume), ret, 0.0, Costs(trade=fee, cash_haircut=1.0), lag=lag, periods=365, band=0.03)


def eq_mr_returns(high, low, close, ret: pd.DataFrame, rf_daily: pd.Series, fee: float = INDEX_FEE, lag: int = 1) -> pd.Series:
    """Long via CFD o margine: ogni notte in posizione costa (tasso + spread) sul controvalore; la cassa non rende."""
    W = eq_mr(high, low, close)
    held = W.shift(lag).fillna(0.0)
    carry = rf_daily + CFD_SPREAD / 252
    return (held * ret[W.columns].sub(carry, axis=0)).sum(axis=1) - W.diff().abs().fillna(0.0).sum(axis=1) * fee


def ma_trend_returns(adj: pd.DataFrame, rf_daily: pd.Series, fee: float = ETF_FEE, lag: int = 1):
    W = ma_trend(adj)
    R = adj[TREND_UNIVERSE].loc["2003":].pct_change(fill_method=None)
    return run(W, R, rf_daily, Costs(trade=fee, cash_haircut=1.0), lag=lag, band=0.02)


# ---------------------------------------------------------------------------
# Candidata IN OMBRA (non riceve capitale): momentum residuo sulle crypto
# ---------------------------------------------------------------------------
def cr_resid(close: pd.DataFrame, dollar_volume: pd.DataFrame, ret: pd.DataFrame, beta_window: int = 60,
             lookback: int = 28) -> pd.DataFrame:
    """Come CR-XSMOM, ma le monete si ordinano per momentum AL NETTO di Bitcoin: il rendimento residuo dopo aver tolto
    beta x rendimento di BTC, diviso per la sua volatilita' (Blitz, Huij, Martens 2011, sulle azioni).
    Ricerca v3 (research/v5/v3): Sharpe 1,11 (scelta 1,06, verifica 1,16), stabile su 9 combinazioni di parametri;
    correlazione 0,94 con CR-XSMOM. Sostituita a CR-XSMOM porta il portafoglio da 1,18 a 1,22: dentro il rumore.
    Per questo NON e' in produzione: gira in ombra e si decide dopo il paper trading."""
    btc = ret["BTC"]
    beta = ret.rolling(beta_window).cov(btc).div(btc.rolling(beta_window).var(), axis=0)
    resid = ret.sub(beta.mul(btc, axis=0))
    score = resid.rolling(lookback).sum() / resid.rolling(lookback).std() / math.sqrt(lookback)
    adv = dollar_volume.rolling(30, min_periods=20).mean()
    btc_up = close["BTC"] > close["BTC"].rolling(100).mean()
    W = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    last = None
    for i, d in enumerate(close.index):
        if i % 7 == 0:
            ok = adv.loc[d].notna() & score.loc[d].notna()
            s = score.loc[d][adv.loc[d][ok].nlargest(20).index]
            pick = s[s > 0].nlargest(5).index
            last = pd.Series(0.0, index=close.columns)
            if len(pick) and bool(btc_up.get(d, False)):
                last[pick] = 0.2
        if last is not None:
            W.loc[d] = last
    return W
