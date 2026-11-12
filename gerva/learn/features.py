"""Contesto di un trade al momento dell'ingresso. UNA definizione, usata sia per i trade storici simulati sia dal ciclo
paper: se le due parti calcolassero il contesto in modo diverso, una regola validata sul passato non varrebbe sul presente.
Ogni grandezza usa solo dati fino alla barra del segnale (la sera prima dell'ingresso)."""
from __future__ import annotations

import pandas as pd

from .. import ensemble as E
from .. import gervasoni as GV

NUMERIC = ("conviction", "gq", "atr_pct", "atr_rank", "btc_ret30", "funding7", "n_alta", "ret7")
CATEGORICAL = ("symbol", "weekday", "tier")


def context(bars: dict[str, pd.DataFrame], sym: str, funding: dict | None = None, at: pd.Timestamp | None = None) -> dict:
    """bars: moneta -> barre giornaliere (open, high, low, close, volume facoltativo); deve contenere BTC.
    at: barra del segnale (default: l'ultima). Restituisce il contesto noto a quella chiusura."""
    cut = {k: (b if at is None else b.loc[:at]) for k, b in bars.items()}
    b = cut[sym]
    f = (funding or {}).get(sym)
    cv = E.conviction(E.crypto_signals(b, cut["BTC"]["close"], None if f is None else f.loc[:b.index[-1]]), "crypto").iloc[-1]
    atr = ((b["high"] - b["low"]) / b["close"]).rolling(14).mean()
    rank = atr.rolling(365, min_periods=120).rank(pct=True).iloc[-1]
    btc = cut["BTC"]["close"]
    n_alta = 0
    for k, x in cut.items():
        if len(x) >= 260:
            fk = (funding or {}).get(k)
            t = E.conviction(E.crypto_signals(x, btc, None if fk is None else fk.loc[:x.index[-1]]), "crypto").iloc[-1]["tier"]
            n_alta += t == "alta"
    gq = GV.gq(b, b["volume"], btc).iloc[-1] if "volume" in b.columns else float("nan")
    f7 = float(f.loc[:b.index[-1]].tail(7).mean() * 365) if f is not None and len(f.loc[:b.index[-1]]) else float("nan")

    def num(v):
        return None if v != v else round(float(v), 6)
    return dict(symbol=sym, weekday=int((b.index[-1] + pd.Timedelta(days=1)).dayofweek), tier=str(cv["tier"]),
                conviction=num(cv["score"]), gq=num(gq), atr_pct=num(atr.iloc[-1]), atr_rank=num(rank),
                btc_ret30=num(btc.iloc[-1] / btc.iloc[-31] - 1) if len(btc) > 31 else None, funding7=num(f7), n_alta=int(n_alta),
                ret7=num(b["close"].iloc[-1] / b["close"].iloc[-8] - 1) if len(b) > 8 else None)
