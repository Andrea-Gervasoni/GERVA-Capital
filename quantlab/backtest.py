"""
Backtester con deriva dei pesi (corregge il rilievo R3 dell'audit di GERVA-Q).

Convenzione temporale (identica a GERVA-Q):
  * i pesi target W[t] sono decisi con dati fino alla CHIUSURA di t;
  * si eseguono all'APERTURA di t+1 (se si passano gli open), altrimenti alla chiusura di t+1;
  * tra un ribilanciamento e l'altro le QUANTITA' restano ferme e i pesi derivano con i prezzi.

`rebalance` dice quando si tocca il portafoglio: una soglia (banda) evita di inseguire
la deriva con ordini minuscoli, come fa il paper reale.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    daily: pd.DataFrame          # ret, gross, turnover, cost
    weights: pd.DataFrame        # pesi effettivi a fine giornata (dopo la deriva)

    @property
    def returns(self) -> pd.Series:
        return self.daily["ret"]


def run(W: pd.DataFrame, close: pd.DataFrame, open_: pd.DataFrame | None = None,
        cost_rate: float | pd.Series = 0.0008, band: float = 0.0,
        rebalance_mask: pd.Series | None = None) -> BacktestResult:
    """
    W: pesi target (frazione del NAV) decisi alla chiusura di ogni riga.
    close/open_: prezzi allineati a W (stesse colonne).
    cost_rate: costo per unita' di turnover (scalare o per colonna).
    band: si ritocca un peso solo se |target - attuale| > band (o se il target e' 0).
    rebalance_mask: True nei giorni in cui e' permesso ribilanciare (default: sempre).
    """
    cols = list(W.columns)
    close = close[cols].astype(float)
    W = W.reindex(close.index).fillna(0.0)
    opn = open_[cols].astype(float) if open_ is not None else None
    c = np.broadcast_to(np.asarray(pd.Series(cost_rate, index=cols) if np.ndim(cost_rate) == 0
                                   else pd.Series(cost_rate).reindex(cols).fillna(0.0)), (len(cols),))
    C = close.values
    O = opn.values if opn is not None else None
    T, N = C.shape
    mask = np.ones(T, bool) if rebalance_mask is None else rebalance_mask.reindex(close.index).fillna(False).values
    w = np.zeros(N)                      # pesi a fine giornata t (dopo la deriva)
    target_prev = np.zeros(N)
    out = np.zeros((T, 4))
    wout = np.zeros((T, N))
    for t in range(1, T):
        prev_c, cur_c = C[t - 1], C[t]
        valid = np.isfinite(prev_c) & np.isfinite(cur_c) & (prev_c > 0)
        # 1) decisione di ieri sera, eseguita oggi
        tgt = W.values[t - 1]
        tgt = np.where(np.isfinite(tgt), tgt, 0.0)
        if mask[t - 1]:
            move = (np.abs(tgt - w) > band) | ((tgt == 0) & (w != 0))
            new_target = np.where(move, tgt, w)
        else:
            new_target = w.copy()
        if O is not None:
            # gap close(t-1) -> open(t) con i pesi vecchi, poi esecuzione all'apertura
            o = O[t]
            ok_o = valid & np.isfinite(o) & (o > 0)
            g = np.where(ok_o, o / np.where(valid, prev_c, 1) - 1, 0.0)
            r_gap = float(w @ g)
            w_open = w * (1 + g) / (1 + r_gap) if 1 + r_gap != 0 else w
            turn = np.abs(new_target - w_open)
            cost = float(turn @ c)
            intra = np.where(ok_o & np.isfinite(cur_c), cur_c / np.where(ok_o, o, 1) - 1, 0.0)
            r_int = float(new_target @ intra)
            r = (1 + r_gap) * (1 - cost) * (1 + r_int) - 1
            grow = 1 + intra
            base = 1 + r_int
            w_end = new_target * grow / base if base != 0 else new_target
        else:
            turn = np.abs(new_target - w)
            cost = float(turn @ c)
            ret = np.where(valid, cur_c / np.where(valid, prev_c, 1) - 1, 0.0)
            r_p = float(new_target @ ret)
            r = (1 - cost) * (1 + r_p) - 1
            base = 1 + r_p
            w_end = new_target * (1 + ret) / base if base != 0 else new_target
        # la liquidita' (1 - somma pesi) rende 0: la normalizzazione sopra lo tiene in conto
        w = w_end
        target_prev = new_target
        out[t] = (r, new_target.sum(), turn.sum(), cost)
        wout[t] = w
    daily = pd.DataFrame(out, index=close.index, columns=["ret", "gross", "turnover", "cost"])
    return BacktestResult(daily=daily, weights=pd.DataFrame(wout, index=close.index, columns=cols))
