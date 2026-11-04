"""
Livello dati con impronta (corregge il rilievo R2 dell'audit di GERVA-Q).

  * chiave di cache STABILE (SHA-256), non hash() di Python che cambia a ogni processo;
  * impronta SHA-256 del contenuto salvata accanto: ogni risultato di ricerca cita l'impronta
    dei dati su cui e' stato calcolato, quindi due studi sono confrontabili solo se l'impronta
    coincide;
  * controllo di qualita' del Data Engineer: buchi, salti anomali, prezzi non positivi,
    candele non ancora chiuse.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd


def stable_key(*parts) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:20]


def fingerprint(df: pd.DataFrame) -> str:
    """Impronta del contenuto: indipendente dall'ordine delle colonne."""
    d = df.sort_index(axis=1)
    h = hashlib.sha256()
    h.update("|".join(map(str, d.columns)).encode())
    h.update(pd.util.hash_pandas_object(d, index=True).values.tobytes())
    return h.hexdigest()[:16]


@dataclass
class QualityReport:
    ok: bool
    problems: list

    def to_dict(self):
        return dict(ok=self.ok, problems=self.problems)


def quality_check(close: pd.DataFrame, max_gap_days: int = 5, jump_sigma: float = 8.0,
                  now: pd.Timestamp | None = None, bar_close: pd.Series | None = None) -> QualityReport:
    """Regole del Data Engineer. Un problema 'blocca' ferma la pipeline."""
    probs = []
    if not close.index.is_monotonic_increasing:
        probs.append(dict(tipo="indice_non_ordinato", blocca=True))
    if close.index.has_duplicates:
        probs.append(dict(tipo="date_duplicate", blocca=True))
    if (close <= 0).any().any():
        probs.append(dict(tipo="prezzi_non_positivi", colonne=list(close.columns[(close <= 0).any()]), blocca=True))
    r = np.log(close).diff()
    for c in close.columns:
        s = r[c].dropna()
        if len(s) > 30:
            mad = (s - s.median()).abs().median() * 1.4826
            if mad > 0:
                z = ((s - s.median()) / mad).abs()
                big = z[z > jump_sigma]
                if len(big):
                    probs.append(dict(tipo="salto_anomalo", colonna=c, date=[str(x) for x in big.index[:5]],
                                      blocca=False))
        valid = close[c].dropna()
        if len(valid) > 2:
            gaps = valid.index.to_series().diff().dt.days
            if (gaps > max_gap_days).any():
                probs.append(dict(tipo="buco", colonna=c, giorni_max=int(gaps.max()), blocca=False))
    if bar_close is not None and now is not None:
        open_bars = bar_close[bar_close > now]
        if len(open_bars):
            probs.append(dict(tipo="candele_non_chiuse", n=len(open_bars), blocca=True))
    return QualityReport(ok=not any(p["blocca"] for p in probs), problems=probs)


class Cache:
    """Cache su disco con chiave stabile e impronta del contenuto."""

    def __init__(self, root: str):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def path(self, key: str) -> str:
        return os.path.join(self.root, f"{key}.pkl")

    def get(self, key: str):
        p = self.path(key)
        if not os.path.exists(p):
            return None
        meta = json.load(open(p + ".json"))
        df = pd.read_pickle(p)
        if fingerprint(df) != meta["fingerprint"]:
            raise RuntimeError(f"cache corrotta: {key}")
        return df, meta

    def put(self, key: str, df: pd.DataFrame, source: str) -> dict:
        meta = dict(fingerprint=fingerprint(df), source=source, rows=len(df),
                    saved=pd.Timestamp.now(tz="UTC").isoformat())
        df.to_pickle(self.path(key))
        json.dump(meta, open(self.path(key) + ".json", "w"))
        return meta
