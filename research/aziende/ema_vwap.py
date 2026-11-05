import warnings; warnings.filterwarnings("ignore")
import math, numpy as np, pandas as pd, yfinance as yf
from scipy.stats import binom
def test(sym, interval, cost_bp):
    d = yf.download(sym, period="60d", interval=interval, auto_adjust=False, progress=False, prepost=False)
    if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    d = d.dropna(); d["day"] = d.index.date
    tp = (d.High + d.Low + d.Close) / 3
    d["vwap"] = (tp * d.Volume).groupby(d.day).cumsum() / d.Volume.groupby(d.day).cumsum()
    d["ema9"] = d.Close.groupby(d.day).transform(lambda s: s.ewm(span=9, adjust=False).mean())
    trades = []
    for day, g in d.groupby("day"):
        pos, entry = 0, None
        c, e, v = g.Close.values, g.ema9.values, g.vwap.values
        for i in range(10, len(g) - 1):
            if pos == 0 and e[i-1] <= v[i-1] and e[i] > v[i]:          # EMA9 incrocia sopra il VWAP: entra al prossimo
                pos, entry = 1, g.Open.values[i+1]
            elif pos == 1 and c[i] < e[i]:                               # candela chiude sotto l'EMA9: esci al prossimo
                trades.append(g.Open.values[i+1] / entry - 1 - 2*cost_bp/1e4); pos = 0
        if pos == 1: trades.append(c[-1] / entry - 1 - 2*cost_bp/1e4)  # chiusura a fine giornata
    t = np.array(trades); w = int((t > 0).sum()); n = len(t)
    gross = t + 2*cost_bp/1e4
    return dict(simbolo=sym, candele=interval, giorni=d.day.nunique(), trade=n, vinti=w,
                pct_vinti=w/n if n else None, media_lorda_bp=gross.mean()*1e4 if n else None,
                media_netta_bp=t.mean()*1e4 if n else None, totale_netto=float(np.prod(1+t)-1) if n else None,
                p_caso=float(binom.sf(w-1, n, 0.5)) if n else None,
                t_stat=float(t.mean()/t.std(ddof=1)*math.sqrt(n)) if n > 2 else None)
rows = [test(s, i, 1.0) for s in ("SPY", "QQQ") for i in ("2m", "5m")]
print(pd.DataFrame(rows).round(4).to_string())
