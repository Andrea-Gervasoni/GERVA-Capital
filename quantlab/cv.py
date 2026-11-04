"""
Validazione incrociata per serie storiche (Lopez de Prado, AFML 2018, capp. 7 e 12):
walk-forward, K-fold con purging ed embargo, CPCV.

Ogni osservazione i ha una finestra di etichetta [t0_i, t1_i]: il periodo in cui si
realizza l'esito che il modello impara. Il purging toglie dal training le osservazioni
la cui finestra si sovrappone a quella di un'osservazione di test; l'embargo toglie
anche un margine DOPO il test, per l'autocorrelazione dei segnali.
"""
from __future__ import annotations

from itertools import combinations
from math import comb

import numpy as np


def walk_forward(n: int, train: int, test: int, step: int | None = None):
    """Finestre (train_idx, test_idx) che avanzano nel tempo, training mai nel futuro."""
    step = step or test
    s = 0
    while s + train + test <= n:
        yield np.arange(s, s + train), np.arange(s + train, s + train + test)
        s += step


def _purge(train_idx, test_idx, t0, t1, embargo: int):
    test_start, test_end = t0[test_idx].min(), t1[test_idx].max()
    keep = []
    for i in train_idx:
        overlaps = (t0[i] <= test_end) and (t1[i] >= test_start)
        in_embargo = test_end < t0[i] <= test_end + embargo
        if not overlaps and not in_embargo:
            keep.append(i)
    return np.array(keep, dtype=int)


def purged_kfold(t0, t1, k: int = 5, embargo: int = 0):
    """t0, t1: array di inizio/fine finestra di etichetta (in indici di tempo)."""
    t0, t1 = np.asarray(t0), np.asarray(t1)
    n = len(t0)
    folds = np.array_split(np.arange(n), k)
    for f in folds:
        train = np.setdiff1d(np.arange(n), f)
        yield _purge(train, f, t0, t1, embargo), f


def cpcv_splits(t0, t1, n_groups: int = 6, k_test: int = 2, embargo: int = 0):
    """Combinatorial Purged CV: tutte le combinazioni di k_test gruppi su n_groups.
    Numero di traiettorie di backtest ricostruibili: phi = k/N * C(N, k)."""
    t0, t1 = np.asarray(t0), np.asarray(t1)
    n = len(t0)
    groups = np.array_split(np.arange(n), n_groups)
    for test_groups in combinations(range(n_groups), k_test):
        test = np.concatenate([groups[g] for g in test_groups])
        train = np.setdiff1d(np.arange(n), test)
        # purging gruppo per gruppo (i gruppi di test possono non essere contigui)
        for g in test_groups:
            train = _purge(train, groups[g], t0, t1, embargo)
        yield train, test, test_groups


def n_paths(n_groups: int, k_test: int) -> int:
    return comb(n_groups, k_test) * k_test // n_groups
