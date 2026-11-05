"""
Portafoglio ombra: la v4 vincente del banco ("tutto") seguita IN AVANTI accanto alla v3, senza ordini.

Perche': un backtest che vince (anche con DSR, PBO e holdout) non basta per cambiare il motore nel mezzo della
sfida. Da una data di partenza fissa si registra ogni giorno il rendimento di entrambe le versioni, calcolato con
i soli dati disponibili quel giorno (i pesi decisi a t-1 si applicano a t). Ogni giorno si scrive UNA volta
(tabella append-only, UNIQUE(day, variant)): una revisione dei prezzi non puo' riscrivere il passato a favore
di nessuno.

Regola di decisione scritta PRIMA dei dati (STATUS.md): dopo almeno 40 giorni di borsa in avanti, si propone ad
Andrea di adottare la v4 solo se P(Sharpe v4 > v3) >= 0,80 nel bootstrap appaiato e il drawdown in avanti della v4
non supera quello della v3. Altrimenti si resta sulla v3.
"""
from __future__ import annotations

import math
import os

import numpy as np
import pandas as pd

from . import db, events, paths

VARIANTS = ("v3_riferimento", "tutto")
START_KEY = "shadow.start"
START_DEFAULT = "2026-11-05"      # ultimo giorno visto dal banco (research/gervaq4/2026-11-05.md): registrata prima
MIN_DAYS = 40
P_MIN = 0.80


def _data(close: pd.DataFrame) -> dict:
    from quantlab import gervaq4 as G4
    return dict(close=close, stocks=[s for s in G4.STOCKS if s in close])


def update(close: pd.DataFrame | None = None, start: str | None = None) -> dict:
    """Registra i giorni nuovi dopo la data di partenza, fissata una volta sola (default: START_DEFAULT)."""
    from quantlab import gervaq4 as G4, data as QD
    if close is None:
        p = os.path.join(paths.VAR, "data", "gq4_close.pkl")
        if not os.path.exists(p):
            return dict(ok=False, motivo="mancano i dati: firm.py data")
        close = pd.read_pickle(p)
    start = db.runtime_get(START_KEY) or start
    if not db.runtime_get(START_KEY):
        start = start or START_DEFAULT
        db.runtime_set(START_KEY, start)
        events.publish("shadow.start", "ricerca", dict(da=start, varianti=list(VARIANTS)))
    fp = QD.fingerprint(close)
    added = 0
    for name in VARIANTS:
        v = next(x for x in G4.VARIANTS if x.name == name)
        r = G4.run_variant(_data(close), v)
        fwd = r[r.index > pd.Timestamp(start)]
        for d, x in fwd.items():
            if not np.isfinite(x):
                continue
            cur = db.connect().execute(
                "INSERT OR IGNORE INTO shadow_returns(day,variant,ret,recorded_ts,data_fp) VALUES(?,?,?,?,?)",
                (str(d.date()), name, float(x), db.now_iso(), fp))
            added += cur.rowcount
    return {**summary(), "ok": True, "partenza": start, "nuovi": added}


def summary() -> dict:
    from quantlab import gervaq4 as G4
    rows = db.q("SELECT day, variant, ret FROM shadow_returns ORDER BY day")
    if not rows:
        return dict(giorni=0, verdetto="nessun giorno in avanti ancora")
    df = pd.DataFrame(rows).pivot(index="day", columns="variant", values="ret").dropna()
    out = dict(giorni=len(df), partenza=db.runtime_get(START_KEY))
    for name in VARIANTS:
        if name in df:
            x = df[name].values
            nav = np.cumprod(1 + x)
            sd = x.std(ddof=1) if len(x) > 1 else 0.0
            out[name] = dict(rendimento=float(nav[-1] - 1), sharpe=float(x.mean() / sd * math.sqrt(252)) if sd > 0 else None,
                             max_dd=float((nav / np.maximum.accumulate(nav) - 1).min()))
    if len(df) >= 20 and all(n in df for n in VARIANTS):
        out["p_v4_meglio"] = G4.paired_sharpe_prob(df["tutto"].values, df["v3_riferimento"].values)
    if len(df) < MIN_DAYS:
        out["verdetto"] = f"in osservazione: {len(df)}/{MIN_DAYS} giorni di borsa"
    elif out.get("p_v4_meglio", 0) >= P_MIN and out["tutto"]["max_dd"] >= out["v3_riferimento"]["max_dd"]:
        out["verdetto"] = "la v4 regge anche in avanti: proporre l'adozione (grande richiesta n.5, finestra della domenica)"
    else:
        out["verdetto"] = "la v4 non conferma in avanti: si resta sulla v3"
    return out
