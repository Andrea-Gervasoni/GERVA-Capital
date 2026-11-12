"""Test 4: raffiche di trade grandi/aggressivi (proxy di liquidazioni) negli aggTrades Binance USDT-M.
Evento: flusso firmato nella finestra W >= K x volume medio per W degli ultimi 30 min, con prezzo mosso >= m bp nella stessa direzione.
Rendimento successivo firmato nella direzione della raffica (>0 continuazione, <0 inversione), entrando 1 s dopo.
Selezione 2020-2022, verifica 2023-2026. 12 varianti x 5 orizzonti."""
import numpy as np, pandas as pd
from lib import *
HZ = {"5s": 5, "30s": 30, "1m": 60, "5m": 300, "15m": 900}
rows = []
for sym in ("BTCUSDT", "ETHUSDT"):
    for d, f in day_files(sym):
        df = pd.read_parquet(f, columns=["bv", "sv", "tlast"])
        s = (df["bv"].to_numpy(float) - df["sv"].to_numpy(float)).reshape(-1, 10).sum(1)
        v = (df["bv"].to_numpy(float) + df["sv"].to_numpy(float)).reshape(-1, 10).sum(1)
        p = ffill(df["tlast"])[9::10]; n = len(p)
        cs, cv = csum0(s), csum0(v); t = np.arange(1800, n - 902)
        for W in (1, 5):
            flow = cs[t + 1] - cs[t + 1 - W]; base = (cv[t + 1 - W] - cv[t + 1 - W - 1800]) / 1800 * W + 1e-9   # media che esclude la finestra
            z = flow / base; mv = (p[t] / p[t - W] - 1) * 1e4
            for K in (10, 20, 50):
                for m in (0, 5):
                    hit = (np.abs(z) >= K) & (np.sign(z) * mv >= m) & ~np.isnan(mv)
                    idx = t[hit]; keep = []; last = -10**9
                    for i in idx:
                        if i - last >= 60: keep.append(i); last = i
                    keep = np.array(keep, dtype=int)
                    if len(keep) == 0: continue
                    sg = np.sign(cs[keep + 1] - cs[keep + 1 - W])
                    r = dict(sym=sym, day=d, W=W, K=K, m=m, i=keep, sg=sg, mv=np.abs((p[keep] / p[keep - W] - 1) * 1e4))
                    for hk, h in HZ.items(): r[hk] = sg * (p[keep + 1 + h] / p[keep + 1] - 1) * 1e4
                    rows.append(pd.DataFrame(r))
E = pd.concat(rows, ignore_index=True); E["per"] = np.where(E["day"] < "2023", "sel", "ver")
E.to_parquet("data/05_bursts_events.parquet")
def st(x):
    x = x.dropna(); return f"{x.mean():+6.2f} (t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))+1e-12):+5.1f})"
print("Rendimento medio in bp dopo la raffica, firmato nella direzione della raffica; ingresso 1 s dopo. Costo taker a/r = 9 bp (HL) + spread.")
print(f"{'W':>2} {'K':>3} {'m':>2} {'per':>3} {'n':>6} {'mossa':>6} " + " ".join(f"{h:>16}" for h in HZ))
for (W, K, m), g in E.groupby(["W", "K", "m"]):
    for per in ("sel", "ver"):
        x = g[g["per"] == per]
        if len(x) == 0: continue
        print(f"{W:>2} {K:>3} {m:>2} {per:>3} {len(x):>6} {x['mv'].mean():>6.1f} " + " ".join(f"{st(x[h]):>16}" for h in HZ))
# migliore regola in selezione (per |media| a qualunque orizzonte), verificata
S = E[E["per"] == "sel"].groupby(["W", "K", "m"])[list(HZ)].mean(); cnt = E[E["per"] == "sel"].groupby(["W", "K", "m"]).size()
S = S[cnt >= 30]; k = S.abs().stack().idxmax(); W, K, m, h = k
x = E[(E.W == W) & (E.K == K) & (E.m == m)]
print(f"\nMigliore in selezione (n>=30): W={W}s K={K} m={m} orizzonte {h}: sel {st(x[x.per=='sel'][h])} n={sum(x.per=='sel')} -> VERIFICA {st(x[x.per=='ver'][h])} n={sum(x.per=='ver')}")
print("per anno:", x.groupby(x["day"].str[:4])[h].agg(["mean", "count"]).round(2).to_dict("index"))
