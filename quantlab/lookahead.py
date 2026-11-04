"""
Test anti look-ahead, generalizzazione del "test di controllo" di GERVA-Q (STUDIO.md §7).

Due controlli complementari:

1. Test di troncamento (invarianza nel passato): una funzione di segnale corretta deve dare
   ESATTAMENTE gli stessi valori fino a t sia sui dati completi sia sui dati tagliati a t.
   Se cambia, sta usando dati successivi a t. E' il controllo piu' forte e non dipende dal caso.

2. Test dell'oracolo: un segnale che conosce il futuro (rendimento di domani) deve dare uno
   Sharpe enorme nel motore di backtest, e uno che conosce solo il passato no. Serve a provare
   che il MOTORE applica il ritardo giusto tra decisione ed esecuzione.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd


def truncation_test(signal_fn: Callable[[pd.DataFrame], pd.DataFrame], prices: pd.DataFrame,
                    cut_points: int = 5, min_history: int = 300, atol: float = 1e-10) -> dict:
    """Ritorna {'ok': bool, 'violazioni': [...]}: per ogni punto di taglio confronta il segnale
    calcolato sui dati completi con quello calcolato sui soli dati fino al taglio."""
    full = signal_fn(prices)
    n = len(prices)
    cuts = np.linspace(min_history, n - 2, cut_points).astype(int)
    bad = []
    for c in cuts:
        part = signal_fn(prices.iloc[: c + 1])
        a = full.iloc[: c + 1].reindex(columns=part.columns)
        b = part
        diff = (a - b).abs().where(~(a.isna() & b.isna()))
        worst = float(np.nanmax(diff.values)) if np.isfinite(diff.values).any() else 0.0
        if worst > atol:
            bad.append(dict(taglio=str(prices.index[c]), differenza_max=worst))
    return dict(ok=not bad, violazioni=bad, tagli=len(cuts))


def oracle_test(engine_run: Callable[[pd.DataFrame], pd.Series], close: pd.DataFrame,
                periods: int = 252) -> dict:
    """engine_run(W) -> serie di rendimenti. Confronta segnale-oracolo e segnale-passato."""
    ret = close.pct_change()
    fut = (ret.shift(-1) > 0).astype(float)          # sa se domani sale: vietato
    past = (ret > 0).astype(float)                    # sa solo se oggi e' salito: ammesso
    n = close.shape[1]

    def sharpe(r):
        r = r.dropna()
        return float(r.mean() / r.std() * np.sqrt(periods)) if r.std() > 0 else 0.0

    s_fut = sharpe(engine_run(fut / n))
    s_past = sharpe(engine_run(past / n))
    # Motore corretto: il peso deciso alla chiusura di t vale per il rendimento di t+1.
    #  - il segnale "oggi e' salito" (lecito) deve dare uno Sharpe modesto: se fosse enorme,
    #    il motore starebbe applicando il peso allo stesso rendimento che lo ha generato;
    #  - l'oracolo "domani sale" (illecito) deve dare uno Sharpe enorme: prova che il test
    #    ha potenza, cioe' che il motore usa davvero il peso sul periodo successivo.
    return dict(sharpe_oracolo=s_fut, sharpe_passato=s_past,
                ok=(abs(s_past) < 3.0) and (s_fut > 5.0))
