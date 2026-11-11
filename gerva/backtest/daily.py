"""
Motore di backtest giornaliero con leva, finanziamento e costi.

Convenzione temporale (l'unica difesa che conta contro il look-ahead):
  * W[t] e' il peso obiettivo DECISO con i dati fino alla chiusura di t;
  * si esegue `lag` barre dopo: lag=1 = sulla stessa chiusura (ordine a ridosso della chiusura, o
    crypto subito dopo la candela), lag=2 = alla chiusura successiva (prudente: un giorno intero di ritardo);
  * tra un'esecuzione e l'altra le QUANTITA' restano ferme: i pesi derivano con i prezzi e il turnover
    si misura rispetto ai pesi derivati, non rispetto all'obiettivo di ieri.

Contabilita' di una giornata, in frazione del patrimonio:
    r = somma(w_i * r_i)                         rendimento delle posizioni
      + cassa * (tasso - trattenuta)             la liquidita' rende meno del tasso a breve
      - debito * (tasso + spread)                la leva a margine si paga
      - |short| * costo_prestito                 prendere a prestito i titoli costa
      - somma(|scambio_i| * costo_i)             commissioni, meta' spread, slippage
dove cassa = max(1 - somma(w), 0) e debito = max(somma(w_long) - 1, 0).

`financing="embedded"` vale per futures e perpetual: la leva non richiede un prestito (il costo del
denaro e' gia' nel prezzo del contratto), tutto il patrimonio resta in cassa e rende il tasso.
In quel caso i rendimenti passati devono essere rendimenti in ECCESSO del tasso (li calcola `excess()`).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Costs:
    trade: float | dict = 0.0005        # costo per unita' di controvalore scambiato (per lato)
    borrow_spread: float = 0.015        # spread annuo sul debito a margine (IBKR: benchmark + 1,5%)
    cash_haircut: float = 0.005         # la cassa rende tasso - 0,5% (mai sotto zero)
    short_fee: float = 0.005            # costo annuo del prestito titoli sugli short
    financing: str = "margin"           # "margin" (ETF, azioni, spot) oppure "embedded" (futures, perpetual)


@dataclass
class Result:
    ret: pd.Series                      # rendimento netto giornaliero
    gross: pd.Series                    # esposizione lorda (somma dei valori assoluti dei pesi)
    net: pd.Series                      # esposizione netta
    turnover: pd.Series
    cost: pd.Series                     # costi di scambio pagati nel giorno
    carry: pd.Series                    # interessi netti (cassa, debito, prestito titoli)
    weights: pd.DataFrame               # pesi effettivi a fine giornata

    def equity(self, start: float = 1.0) -> pd.Series:
        return start * (1.0 + self.ret).cumprod()


def excess(ret: pd.DataFrame, rf_daily: pd.Series) -> pd.DataFrame:
    return ret.sub(rf_daily.reindex(ret.index).fillna(0.0), axis=0)


def run(W: pd.DataFrame, ret: pd.DataFrame, rf_daily: pd.Series | float = 0.0, costs: Costs | None = None,
        lag: int = 1, periods: int = 252, band: float = 0.0, max_gross: float | None = None) -> Result:
    """
    W: pesi obiettivo (righe = date, colonne = strumenti), frazione del patrimonio; negativi = short.
    ret: rendimenti semplici giornalieri degli stessi strumenti. NaN = nessun prezzo quel giorno: la posizione
         resta ferma a rendimento zero. Sta alla strategia non dare peso a cio' che non quota.
    band: non si ritocca una posizione se lo scostamento dall'obiettivo e' sotto questa soglia.
    max_gross: tetto fisico all'esposizione lorda; l'obiettivo viene riscalato, mai superato.
    """
    c = costs or Costs()
    cols = list(W.columns)
    idx = ret.index
    R = ret[cols].to_numpy(float)
    Wt = W.reindex(idx).to_numpy(float)
    Wt = np.where(np.isfinite(Wt), Wt, 0.0)
    T, N = R.shape
    rf = (pd.Series(rf_daily, index=idx) if np.ndim(rf_daily) == 0 else rf_daily.reindex(idx).ffill().fillna(0.0)).to_numpy(float)
    tc = np.array([c.trade.get(k, c.trade.get("*", 0.0005)) if isinstance(c.trade, dict) else c.trade for k in cols], float)
    w = np.zeros(N)
    out = np.zeros((T, 6))
    wout = np.zeros((T, N))
    for t in range(T):
        r_t = np.where(np.isfinite(R[t]), R[t], 0.0)
        # 1) la giornata passa con i pesi che avevamo
        pnl = float(w @ r_t)
        longs, shorts = w[w > 0].sum(), -w[w < 0].sum()
        if c.financing == "embedded":
            carry = rf[t]
        else:
            cash = max(1.0 - longs, 0.0) + shorts                 # il ricavato degli short resta in cassa
            debt = max(longs - 1.0, 0.0)
            carry = (cash * max(rf[t] - c.cash_haircut / periods, 0.0)
                     - debt * (rf[t] + c.borrow_spread / periods)
                     - shorts * c.short_fee / periods)
        growth = 1.0 + pnl + carry
        w = w * (1.0 + r_t) / growth if growth > 0 else np.zeros(N)
        # 2) alla chiusura si esegue la decisione presa `lag-1` barre fa
        k = t - (lag - 1)
        cost = turn = 0.0
        if k >= 0 and growth > 0:
            tgt = Wt[k].copy()
            g = np.abs(tgt).sum()
            if max_gross is not None and g > max_gross:
                tgt *= max_gross / g
            move = (np.abs(tgt - w) > band) | ((tgt == 0) & (w != 0))
            new = np.where(move, tgt, w)
            tr = np.abs(new - w)
            turn = float(tr.sum())
            cost = float(tr @ tc)
            w = new
        r = growth * (1.0 - cost) - 1.0 if growth > 0 else -1.0
        out[t] = (r, np.abs(w).sum(), w.sum(), turn, cost, carry)
        wout[t] = w
    d = pd.DataFrame(out, index=idx, columns=["ret", "gross", "net", "turnover", "cost", "carry"])
    return Result(d["ret"], d["gross"], d["net"], d["turnover"], d["cost"], d["carry"],
                  pd.DataFrame(wout, index=idx, columns=cols))


def scale_returns(ret: pd.Series, leverage: float | pd.Series, rf_daily: pd.Series | float = 0.0,
                  borrow_spread: float = 0.015, periods: int = 252) -> pd.Series:
    """Rendimento di una strategia portata a leva L: L*r - (L-1)*(tasso + spread) sulla parte presa a prestito.
    L puo' essere una serie (leva decisa il giorno PRIMA: va passata gia' ritardata)."""
    L = pd.Series(leverage, index=ret.index) if np.ndim(leverage) == 0 else leverage.reindex(ret.index).ffill().fillna(0.0)
    rf = pd.Series(rf_daily, index=ret.index) if np.ndim(rf_daily) == 0 else rf_daily.reindex(ret.index).ffill().fillna(0.0)
    debt = (L - 1.0).clip(lower=0.0)
    cash = (1.0 - L).clip(lower=0.0)
    return L * ret - debt * (rf + borrow_spread / periods) + cash * rf
