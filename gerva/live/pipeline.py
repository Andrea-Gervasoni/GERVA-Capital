"""
Dai dati ai pesi obiettivo del conto. Usa le STESSE funzioni della ricerca (gerva.strategies.book):

    peso finale di uno strumento = leva * somma_strategie( quota della strategia * peso nella strategia )

  quota della strategia : parita' di rischio sulle volatilita' simulate recenti (gerva.portfolio.risk_parity)
  leva                  : volatilita' obiettivo / volatilita' recente del portafoglio, con tetto
  peso nella strategia  : ultima riga dei pesi calcolati sui dati fino all'ultima barra chiusa

Il motore di rischio moltiplica poi tutto per la scala dello stato (1, 0,5, 0,25, 0) e applica i tetti.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..portfolio import combine, risk_parity, vol_target_leverage
from ..strategies import book


@dataclass
class Targets:
    weights: dict                          # simbolo -> peso sul patrimonio (prima della scala di rischio)
    by_sleeve: dict                        # strategia -> {simbolo: contributo al peso}
    alloc: dict                            # strategia -> quota di capitale
    leverage: float
    sleeve_ret: pd.DataFrame               # rendimenti simulati giornalieri delle strategie (per le statistiche)
    port_ret: pd.Series
    asof: dict = field(default_factory=dict)


def _next_row(obj):
    """Aggiunge una riga per 'domani' (rendimento zero): le funzioni di portafoglio restituiscono valori
    'noti il giorno prima', quindi il valore da usare per la PROSSIMA giornata e' quello della riga aggiunta."""
    nxt = obj.index[-1] + pd.Timedelta(days=1)
    if isinstance(obj, pd.DataFrame):
        return pd.concat([obj, pd.DataFrame(0.0, index=[nxt], columns=obj.columns)])
    return pd.concat([obj, pd.Series(0.0, index=[nxt])])


def build(market, vol_target: float, max_leverage: float, sleeves=("CR-TREND", "CR-XSMOM", "EQ-MR", "MA-TREND"),
          overlay=None) -> Targets:
    """overlay: gerva.ai.overlay.Overlay. Puo' solo RIDURRE il contributo di una strategia (moltiplicatore in [0, 1])."""
    W, R = {}, {}
    if market.cclose is not None:
        close, dvol, ret = market.cclose, market.cdvol, market.cret
        if "CR-TREND" in sleeves:
            W["CR-TREND"] = book.cr_trend(close).iloc[-1]
            R["CR-TREND"] = book.cr_trend_returns(close, ret).ret.loc["2018":]
        if "CR-XSMOM" in sleeves:
            raw = book.cr_xsmom_returns(close, dvol, ret).ret.loc["2018":]
            scale = book.xs_scale(_next_row(raw)).iloc[-1]
            W["CR-XSMOM"] = book.cr_xsmom(close, dvol).iloc[-1] * scale
            R["CR-XSMOM"] = raw * book.xs_scale(raw)
    if market.P is not None:
        P, rf = market.P, market.rf
        ret = P["adj"].pct_change(fill_method=None)
        if "EQ-MR" in sleeves:
            W["EQ-MR"] = book.eq_mr(P["high"], P["low"], P["close"]).iloc[-1]
            R["EQ-MR"] = book.eq_mr_returns(P["high"], P["low"], P["close"], ret, rf).loc["2018":]
        if "MA-TREND" in sleeves:
            W["MA-TREND"] = book.ma_trend(P["adj"]).iloc[-1]
            R["MA-TREND"] = book.ma_trend_returns(P["adj"], rf).ret.loc["2018":]
    if not R:
        raise RuntimeError("nessuna strategia calcolabile: mancano i dati di tutte le sedi")
    end = max(r.index[-1] for r in R.values())
    idx = pd.date_range("2018-01-01", end, freq="D")
    S = pd.DataFrame(R).reindex(idx).fillna(0.0)
    a_hist = risk_parity(S)
    port = combine(S, a_hist)
    a = risk_parity(_next_row(S)).iloc[-1]
    lev = float(vol_target_leverage(_next_row(port), vol_target, 60, max_leverage).iloc[-1])
    weights, by = {}, {}
    for s, w in W.items():
        by[s] = {}
        for sym, v in w.items():
            c = float(lev * a[s] * v) * (min(max(overlay.mult(s), 0.0), 1.0) if overlay is not None else 1.0)
            if abs(c) > 1e-9:
                by[s][sym] = c
                weights[sym] = weights.get(sym, 0.0) + c
    return Targets(weights, by, {k: float(v) for k, v in a.items()}, lev, S, port,
                   {k: str(r.index[-1].date()) for k, r in R.items()})
