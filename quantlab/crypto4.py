"""
Zona di ricerca crypto: banco di prova della sleeve crypto della v3 (meta' del conto) contro varianti dichiarate.

Stesse regole del banco azionario (quantlab/gervaq4.py): ogni variante e' una prova registrata, PBO su tutte,
bootstrap appaiato contro il riferimento, ultimi 2 anni messi da parte e guardati una volta sola; se nessuna supera
tutti i cancelli si tiene la v3.

Riferimento "v3_crypto": la sleeve di GERVA-Q (crypto_lab.v3_weights) RIESPRESSA SU CANDELE GIORNALIERE:
  * H1 trend giornaliero multi-lookback (10/20/40/80) sul paniere, vol target 60%, tetto 35% per moneta;
  * H2 breakout Donchian su BTC/ETH/SOL. Nella v3 e' su candele di 4 ore (55 / 20 candele = circa 9 / 3 giorni);
    qui e' approssimato con 9 / 3 giorni, perche' Yahoo non da' lo storico a 4 ore. E' un'APPROSSIMAZIONE dichiarata.
  * 50% H1 + 50% H2, solo long/flat, niente leva, costo 0,23% per lato (commissione IBKR + slippage, come la v3).

Varianti candidate (meccanismo documentato, scritto PRIMA del test):
  cash    la quota ferma rende il tasso a breve (meno 0,10%): nella crypto la sleeve e' spesso flat
  ibkr3   paniere H1 ridotto a BTC/ETH/SOL: meno monete piccole, meno spread e rischio di liquidita'
  slow    lookback piu' lunghi (20/40/80/160) e Donchian 20/10: meno operazioni, meno costi (0,23% per lato pesa)
  vt      volatilita' target sull'intera sleeve (40%), mai oltre il 100% investito
  erc     H1 e H2 a contributi di rischio uguali (inverso della volatilita' a 60 giorni) invece di 50/50
  tutto   cash + slow + vt + erc
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import backtest as BT

COINS = ["BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "LTC", "LINK", "AVAX", "BCH"]
IBKR3 = ["BTC", "ETH", "SOL"]
YAHOO = {c: f"{c}-USD" for c in COINS}
COST = 0.0023
TD = 365


@dataclass(frozen=True)
class CVariant:
    name: str
    cash: bool = False
    univ: str = "all"
    slow: bool = False
    vt: bool = False
    comb: str = "half"

    def params(self) -> dict:
        return dict(cash=self.cash, univ=self.univ, slow=self.slow, vt=self.vt, comb=self.comb)


VARIANTS = [
    CVariant("v3_crypto"),
    CVariant("cash", cash=True),
    CVariant("ibkr3", univ="ibkr3"),
    CVariant("slow", slow=True),
    CVariant("vt", vt=True),
    CVariant("erc", comb="erc"),
    CVariant("tutto", cash=True, slow=True, vt=True, comb="erc"),
]


def h1_trend(D: pd.DataFrame, lookbacks=(10, 20, 40, 80), target_vol: float = 0.60, cap: float = 0.35) -> pd.DataFrame:
    sig = sum((D > D.shift(L)).astype(float) for L in lookbacks) / len(lookbacks)
    vol = D.pct_change().rolling(30, min_periods=20).std() * np.sqrt(TD)
    n = D.notna().sum(axis=1).clip(lower=1)
    W = (sig * (target_vol / vol)).div(n, axis=0).clip(upper=cap)
    g = W.sum(axis=1)
    return W.div(g.where(g > 1, 1), axis=0).fillna(0.0)


def h2_donchian(D: pd.DataFrame, entry: int = 9, exit_: int = 3, coins=IBKR3) -> pd.DataFrame:
    out = pd.DataFrame(0.0, index=D.index, columns=D.columns)
    cs = [c for c in coins if c in D]
    for c in cs:
        s = D[c]
        hi, lo = s.rolling(entry).max().shift(1), s.rolling(exit_).min().shift(1)
        pos, p = np.zeros(len(s)), 0.0
        for i, (x, h, l) in enumerate(zip(s.values, hi.values, lo.values)):
            if np.isnan(h) or np.isnan(x):
                pos[i] = 0.0
                continue
            if p == 0 and x > h:
                p = 1.0
            elif p == 1 and x < l:
                p = 0.0
            pos[i] = p
        out[c] = pos / max(len(cs), 1)
    return out


def _vol_scale(D: pd.DataFrame, W: pd.DataFrame, target: float = 0.40) -> pd.DataFrame:
    r = D.pct_change().fillna(0.0)
    port = (W.shift(1).fillna(0) * r).sum(axis=1)
    vol = port.rolling(60, min_periods=30).std() * np.sqrt(TD)
    k = (target / vol).clip(upper=3.0).fillna(1.0)
    W2 = W.mul(k, axis=0)
    g = W2.sum(axis=1)
    return W2.div(g.where(g > 1, 1), axis=0)                 # mai oltre il 100%: niente leva


def weights(close: pd.DataFrame, v: CVariant) -> pd.DataFrame:
    D = close[[c for c in COINS if c in close]].astype(float)
    U = D[[c for c in IBKR3 if c in D]] if v.univ == "ibkr3" else D
    lb = (20, 40, 80, 160) if v.slow else (10, 20, 40, 80)
    a = h1_trend(U, lb).reindex(columns=D.columns).fillna(0.0)
    b = h2_donchian(D, *((20, 10) if v.slow else (9, 3)))
    if v.comb == "erc":
        r = D.pct_change().fillna(0.0)
        va = (a.shift(1) * r).sum(axis=1).rolling(60, min_periods=30).std()
        vb = (b.shift(1) * r).sum(axis=1).rolling(60, min_periods=30).std()
        ia, ib = 1 / va.replace(0, np.nan), 1 / vb.replace(0, np.nan)
        wa = (ia / (ia + ib)).fillna(0.5).clip(0.2, 0.8)       # mai tutta su una sola gamba
        W = a.mul(wa, axis=0) + b.mul(1 - wa, axis=0)
    else:
        W = 0.5 * a + 0.5 * b
    if v.vt:
        W = _vol_scale(D, W)
    return W


def run_variant(data: dict, v: CVariant, scale: float = 1.0, return_result: bool = False):
    close = data["close"]
    W = weights(close, v)
    if scale != 1.0:
        g = W.abs().sum(axis=1)
        W = W.mul(np.minimum(scale, np.where(g > 0, 1 / g.where(g > 0, 1.0), scale)), axis=0)
    D = close[W.columns]
    res = BT.run(W, D, cost_rate=COST, band=0.05)
    r = res.returns
    if v.cash:
        rate = (close["^IRX"] / 100).ffill().bfill() if "^IRX" in close else pd.Series(0.02, index=close.index)
        idle = (1 - res.daily["gross"]).clip(lower=0)
        r = r + idle * (rate - 0.001).clip(lower=0) / TD
    return (r, res) if return_result else r


def bench(data: dict, **kw):
    """Stesso banco (e stessi cancelli) di quello azionario, con il motore crypto e 365 giorni l'anno."""
    from . import gervaq4 as G4
    return G4.bench(data, variants=VARIANTS, runner=run_variant, ref="v3_crypto", periods=TD, **kw)
