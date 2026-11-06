"""
Grafici quant: gli stessi indicatori che usano i bot di trading, calcolati dal codice sui prezzi veri
(var/data/gq4_close.pkl, scaricati da `firm.py data`). Solo lettura: nessuna di queste funzioni invia ordini.

Indicatori: medie mobili esponenziali (20/50/200), bande di Bollinger (20 giorni, 2 deviazioni), RSI(14),
volatilita' realizzata a 20 giorni (annua), drawdown dal massimo, distanza dalla media a 200 giorni,
rendimenti a 1/3/12 mesi, correlazioni a 120 giorni, regime di mercato (S&P 500 sopra/sotto la media a 200
giorni, VIX), e il conto contro l'S&P 500.
"""
from __future__ import annotations

import math
import os

import numpy as np
import pandas as pd

from . import db, paths

TD = 252


def _file() -> str:
    return os.path.join(paths.VAR, "data", "gq4_close.pkl")


def load_close() -> pd.DataFrame | None:
    f = _file()
    if not os.path.exists(f):
        return None
    return pd.read_pickle(f).sort_index()


def symbols(close: pd.DataFrame | None = None) -> list[str]:
    close = load_close() if close is None else close
    if close is None:
        return []
    ok = [c for c in close.columns if close[c].dropna().shape[0] >= 260 and not str(c).startswith("^")]
    return sorted(ok)


def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    tot = up + dn
    out = 100 * up / tot.where(tot > 0)                       # = 100 - 100/(1+RS), stabile anche senza ribassi o senza rialzi
    return out.where(tot.isna() | (tot > 0), 50.0)


def _clean(x) -> list:
    return [None if (v is None or (isinstance(v, float) and not math.isfinite(v))) else round(float(v), 4) for v in x]


def indicators(sym: str, days: int = 250, close: pd.DataFrame | None = None) -> dict:
    close = load_close() if close is None else close
    if close is None or sym not in close:
        raise KeyError(sym)
    c = close[sym].dropna()
    days = max(30, min(int(days), len(c) - 1))
    ema = {n: c.ewm(span=n, adjust=False).mean() for n in (20, 50, 200)}
    sma20, sd20 = c.rolling(20).mean(), c.rolling(20).std()
    up, dn = sma20 + 2 * sd20, sma20 - 2 * sd20
    r = c.pct_change()
    vol20 = r.rolling(20).std() * math.sqrt(TD)
    rs = rsi(c)
    tail = c.tail(days)
    peak = tail.cummax()
    dd = tail / peak - 1
    idx = tail.index
    last = float(c.iloc[-1])

    def pick(s):
        return _clean(s.reindex(idx).values)

    pct_b = (last - float(dn.iloc[-1])) / (float(up.iloc[-1]) - float(dn.iloc[-1])) if float(up.iloc[-1]) != float(dn.iloc[-1]) else 0.5
    summary = dict(ultimo=round(last, 2), data=str(c.index[-1].date()),
                   r1m=round(float(c.iloc[-1] / c.iloc[-22] - 1), 4) if len(c) > 22 else None,
                   r3m=round(float(c.iloc[-1] / c.iloc[-64] - 1), 4) if len(c) > 64 else None,
                   r12m=round(float(c.iloc[-1] / c.iloc[-253] - 1), 4) if len(c) > 253 else None,
                   vs_ema200=round(last / float(ema[200].iloc[-1]) - 1, 4),
                   rsi=round(float(rs.iloc[-1]), 1), vol20=round(float(vol20.iloc[-1]), 3),
                   drawdown=round(float(dd.iloc[-1]), 4), pct_b=round(float(pct_b), 2),
                   trend="rialzista" if last > float(ema[50].iloc[-1]) > float(ema[200].iloc[-1]) else
                         "ribassista" if last < float(ema[50].iloc[-1]) < float(ema[200].iloc[-1]) else "misto",
                   segnale_rsi="ipercomprato" if rs.iloc[-1] > 70 else "ipervenduto" if rs.iloc[-1] < 30 else "neutro")
    return dict(simbolo=sym, date=[str(d.date()) for d in idx], close=_clean(tail.values),
                ema20=pick(ema[20]), ema50=pick(ema[50]), ema200=pick(ema[200]),
                bb_su=pick(up), bb_giu=pick(dn), rsi=pick(rs), vol20=pick(vol20), drawdown=_clean(dd.values),
                riepilogo=summary)


def screener(close: pd.DataFrame | None = None, limit: int = 120) -> list[dict]:
    close = load_close() if close is None else close
    rows = []
    for s in symbols(close):
        c = close[s].dropna()
        r = c.pct_change()
        e50, e200 = c.ewm(span=50, adjust=False).mean().iloc[-1], c.ewm(span=200, adjust=False).mean().iloc[-1]
        rows.append(dict(simbolo=s, r1m=round(float(c.iloc[-1] / c.iloc[-22] - 1), 4), r3m=round(float(c.iloc[-1] / c.iloc[-64] - 1), 4),
                         r12m=round(float(c.iloc[-1] / c.iloc[-253] - 1), 4), vs_ema200=round(float(c.iloc[-1] / e200 - 1), 4),
                         rsi=round(float(rsi(c).iloc[-1]), 1), vol=round(float(r.tail(60).std() * math.sqrt(TD)), 3),
                         trend="su" if c.iloc[-1] > e50 > e200 else "giu" if c.iloc[-1] < e50 < e200 else "misto"))
    rows.sort(key=lambda x: x["r3m"], reverse=True)
    return rows[:limit]


def regime(close: pd.DataFrame | None = None) -> dict:
    close = load_close() if close is None else close
    out = {}
    if close is not None and "SPY" in close:
        c = close["SPY"].dropna()
        e200 = c.ewm(span=200, adjust=False).mean()
        out.update(spy=round(float(c.iloc[-1]), 2), spy_vs_ema200=round(float(c.iloc[-1] / e200.iloc[-1] - 1), 4),
                   spy_sopra_ema200=bool(c.iloc[-1] > e200.iloc[-1]), spy_r1m=round(float(c.iloc[-1] / c.iloc[-22] - 1), 4),
                   spy_dd=round(float(c.iloc[-1] / c.tail(252).max() - 1), 4))
    if close is not None and "^VIX" in close:
        v = close["^VIX"].dropna()
        out.update(vix=round(float(v.iloc[-1]), 2), vix_percentile=round(float((v.tail(504) < v.iloc[-1]).mean()), 2))
    if out:
        calm = out.get("vix", 20) < 20 and out.get("spy_sopra_ema200", True)
        out["lettura"] = ("mercato calmo e in trend" if calm else
                          "mercato sotto tensione" if out.get("vix", 0) >= 28 else "mercato misto")
    return out


def correlation(syms: list[str], days: int = 120, close: pd.DataFrame | None = None) -> dict:
    close = load_close() if close is None else close
    have = [s for s in dict.fromkeys(syms) if close is not None and s in close][:20]
    if len(have) < 2:
        return dict(simboli=have, matrice=[])
    r = close[have].pct_change().tail(days).dropna(how="all")
    m = r.corr().fillna(0.0)
    return dict(simboli=have, matrice=[[round(float(x), 2) for x in row] for row in m.values])


def equity_vs_benchmark(close: pd.DataFrame | None = None) -> dict:
    """Il conto (valore marcato ogni giorno e ogni battito) contro l'S&P 500, entrambi in base 100 dal primo punto."""
    close = load_close() if close is None else close
    ticks = db.q("SELECT ts, nav FROM nav_ticks ORDER BY ts")
    marks = db.q("SELECT day, nav FROM nav_marks WHERE pod='pod_zero' ORDER BY day")
    pts = [(r["ts"][:16], float(r["nav"])) for r in ticks]
    st = db.runtime_get("ibkr.start_nav")
    if st and (not pts or pts[0][0][:10] > st.get("giorno", "")):             # il primo valore letto da IBKR e' il punto 100
        pts.insert(0, (st["giorno"] + "T08:00", float(st["nav"])))
    if not pts:
        pts = [(r["day"] + "T21:00", float(r["nav"])) for r in marks]
    if not pts:
        return dict(conto=[], spy=[], nota="ancora nessun valore del conto registrato")
    base = pts[0][1]
    conto = [dict(t=t, v=round(100 * n / base, 3)) for t, n in pts]
    spy = []
    if close is not None and "SPY" in close:
        s = close["SPY"].dropna()
        t0 = pd.Timestamp(pts[0][0][:10])
        before = s[s.index <= t0]
        s = s[s.index >= (before.index[-1] if len(before) else t0)]      # base 100 = ultima chiusura fino al primo punto del conto
        if len(s) >= 1:
            b = float(s.iloc[0])
            spy = [dict(t=str(d.date()) + "T22:00", v=round(100 * float(x) / b, 3)) for d, x in s.items()]
    return dict(conto=conto, spy=spy, base=round(base, 2))
