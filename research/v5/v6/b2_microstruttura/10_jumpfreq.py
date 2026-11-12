"""Quante volte al giorno il perp Binance si muove >= X bp in 500 ms (un evento ogni 3 s al massimo)? Serve a tradurre il test lead-lag in trade/anno."""
import numpy as np, pandas as pd
from lib import *
rows = []
for sym in ("BTCUSDT", "ETHUSDT"):
    for d, f in day_files(sym):
        df = pd.read_parquet(f, columns=["tlast"]); p = ffill(df["tlast"]); r = np.abs(p[5:] / p[:-5] - 1) * 1e4
        o = dict(sym=sym, day=d)
        for X in (4, 6, 8, 12):
            idx = np.where(r >= X)[0]; n = 0; last = -100
            for i in idx:
                if i - last >= 30: n += 1; last = i
            o[f">={X}bp"] = n
        rows.append(o)
T = pd.DataFrame(rows); T["anno"] = T.day.str[:4]
print("eventi al giorno (mediana | media) per anno:"); print(T.groupby(["sym", "anno"])[[c for c in T.columns if c.startswith(">=")]].agg(["median", "mean"]).round(0).to_string())
