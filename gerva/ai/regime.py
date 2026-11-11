"""
Regime di mercato, deterministico e verificabile sul passato (nessun LLM).

Quattro stati, dal piu' tranquillo al piu' teso. Ogni grandezza e' nota la sera prima:
    VIX rispetto alla sua mediana a un anno, curva VIX (VIX / VIX a 3 mesi), volatilita' realizzata a 20 giorni
    del portafoglio rispetto alla sua mediana, Bitcoin sopra o sotto la media a 100 giorni.

Il regime NON prevede i rendimenti (i regimi si riconoscono in ritardo: Ang e Bekaert; Cederburg e altri 2020):
serve soltanto a ridurre l'esposizione quando il rischio e' alto. Il moltiplicatore non supera mai 1.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

STATES = ("calmo", "normale", "teso", "crisi")
MULT = {"calmo": 1.0, "normale": 1.0, "teso": 0.7, "crisi": 0.4}


def classify(vix: pd.Series, vix3m: pd.Series, port_ret: pd.Series, btc_close: pd.Series) -> pd.DataFrame:
    idx = port_ret.index
    v = vix.reindex(idx).ffill()
    ratio = (vix / vix3m).reindex(idx).ffill()
    rv = port_ret.rolling(20).std()
    stress = pd.DataFrame(dict(
        vix_alto=v > v.rolling(365, min_periods=120).quantile(0.80),
        backwardation=ratio > 1.0,
        vol_alta=rv > rv.rolling(365, min_periods=120).quantile(0.80),
        btc_giu=(btc_close < btc_close.rolling(100).mean()).reindex(idx).ffill(),
    )).astype(float)
    score = stress.sum(axis=1)
    state = pd.Series(np.select([score >= 3, score == 2, score == 1], ["crisi", "teso", "normale"], "calmo"), index=idx)
    out = pd.DataFrame(dict(state=state, score=score, mult=state.map(MULT)))
    return out.shift(1).dropna()                     # noto la sera prima
