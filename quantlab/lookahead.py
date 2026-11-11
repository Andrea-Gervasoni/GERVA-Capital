"""
Test anti look-ahead, generalizzazione del "test di controllo" di GERVA-Q (STUDIO.md §7).

Due controlli complementari:

1. Test di troncamento (invarianza nel passato): una funzione di segnale corretta deve dare
   ESATTAMENTE gli stessi valori fino a t sia sui dati completi sia sui dati tagliati a t.
   Se cambia, sta usando dati successivi a t. Si taglia a OGNI riga di ribilanciamento piu' un campione
   casuale a seme fisso: un errore che compare solo in certe righe (fine mese) non deve poter passare.

2. Test dell'oracolo: un segnale che conosce il futuro (rendimento di domani) deve dare uno
   Sharpe enorme nel motore di backtest, e uno che conosce solo il passato no. Serve a provare
   che il MOTORE applica il ritardo giusto tra decisione ed esecuzione.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd


def _trunc(x, ts):
    """Taglia un ingresso (DataFrame o Serie indicizzati nel tempo) alle righe con etichetta <= ts."""
    return x.loc[x.index <= ts]


def _frame(x) -> pd.DataFrame:
    return x.to_frame("valore") if isinstance(x, pd.Series) else x


def rebalance_rows(index: pd.Index) -> np.ndarray:
    """Posizioni delle righe in cui un segnale a calendario tipicamente ribilancia: ultima e prima riga di ogni
    mese. Sono le righe in cui un errore "solo a fine mese" si nasconde: vanno tagliate TUTTE, non a campione."""
    if not isinstance(index, pd.DatetimeIndex) or len(index) < 2:
        return np.array([], dtype=int)
    key = index.year * 12 + index.month
    change = np.asarray(key[1:] != key[:-1])
    last = np.where(change)[0]                    # ultima riga del mese
    return np.unique(np.concatenate([last, last + 1]))


def truncation_test(signal_fn: Callable[..., pd.DataFrame], prices: pd.DataFrame,
                    cut_points: int = 5, min_history: int = 300, atol: float = 1e-10,
                    rebalance_mask: pd.Series | None = None, random_cuts: int = 60, seed: int = 7,
                    extra: dict | None = None, allowed_mask: pd.Series | None = None) -> dict:
    """Ritorna {'ok': bool, 'violazioni': [...]}: per ogni punto di taglio confronta il segnale
    calcolato sui dati completi con quello calcolato sui soli dati fino al taglio.

    Punti di taglio (audit del 10/11, rilievo 11: con 3-5 tagli equispaziati un segnale che guardava la chiusura
    di domani SOLO nelle righe di fine mese passava, perche' nessun taglio cadeva su una di quelle righe):
      * `cut_points` tagli equispaziati, come prima;
      * OGNI riga di ribilanciamento: quelle di `rebalance_mask` (True = riga in cui il segnale puo' cambiare
        il portafoglio) e comunque l'ultima e la prima riga di ogni mese (`rebalance_rows`);
      * `random_cuts` righe a caso (almeno 60 di default) con seme fisso: stesso risultato a ogni esecuzione.
    `allowed_mask` limita i tagli alle righe in cui tagliare ha senso (es. l'ultima barra di ogni giornata, per
    un segnale che lavora per giornate intere): senza, tutte le righe da `min_history` in poi.

    Ingressi: `prices` e TUTTI gli altri dati del segnale devono passare da qui. Gli ingressi in piu' vanno in
    `extra` (nome -> Serie o DataFrame): vengono tagliati alla stessa data e passati come argomenti con nome,
    signal_fn(prezzi_tagliati, **extra_tagliati). Una serie catturata dalla funzione (lambda c: f(c, MERCATO))
    NON viene tagliata e il test non puo' accorgersi se contiene il futuro.

    Il segnale puo' restituire una Serie o un DataFrame, anche con un indice diverso da quello dei prezzi
    (es. rendimenti giornalieri da barre intraday): il confronto e' per etichetta, sulle righe fino al taglio."""
    extra = dict(extra or {})
    full = _frame(signal_fn(prices, **extra))
    n = len(prices)
    lo, hi = min(min_history, max(n - 2, 0)), n - 2
    allowed = np.ones(n, bool) if allowed_mask is None else np.asarray(allowed_mask.reindex(prices.index).fillna(False).values, bool)
    pool = np.array([i for i in range(lo, hi + 1) if allowed[i]], dtype=int)
    cuts = set()
    if len(pool):
        cuts.update(pool[np.unique(np.linspace(0, len(pool) - 1, min(cut_points, len(pool))).astype(int))].tolist())
        reb = set(rebalance_rows(prices.index).tolist())
        if rebalance_mask is not None:
            reb.update(np.where(np.asarray(rebalance_mask.reindex(prices.index).fillna(False).values, bool))[0].tolist())
        cuts.update(i for i in reb if lo <= i <= hi and allowed[i])
        if random_cuts > 0:
            rng = np.random.default_rng(seed)
            cuts.update(rng.choice(pool, size=min(random_cuts, len(pool)), replace=False).tolist())
    bad = []
    for c in sorted(cuts):
        ts = prices.index[c]
        part = _frame(signal_fn(prices.iloc[: c + 1], **{k: _trunc(v, ts) for k, v in extra.items()}))
        a = full.loc[full.index <= ts]
        cols = a.columns.union(part.columns)
        a = a.reindex(columns=cols)
        # una riga presente con i dati completi e assente con quelli tagliati (o viceversa) e' un'asimmetria: conta come NaN
        b = part.loc[part.index <= ts].reindex(index=a.index.union(part.index[part.index <= ts]), columns=cols)
        a = a.reindex(index=b.index)
        diff = (a - b).abs().where(~(a.isna() & b.isna()))
        worst = float(np.nanmax(diff.values)) if np.isfinite(diff.values).any() else 0.0
        mismatch = int((a.isna() ^ b.isna()).values.sum())      # valore noto con il futuro, assente senza
        if mismatch:
            worst = max(worst, float("inf"))
        if worst > atol:
            bad.append(dict(taglio=str(ts), differenza_max=worst, nan_asimmetrici=mismatch))
    return dict(ok=bool(cuts) and not bad, violazioni=bad, tagli=len(cuts))


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
