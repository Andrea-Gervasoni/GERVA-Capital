"""Squilibrio del book a piu' profondita' (±1%, ±2%, ±3%, ±5% dal mid), Binance USDT-M bookDepth (istantanee ~30 s, disponibili dal 2023-01).
Un giorno su due 2023-01 -> 2026-10. Fit 2023-2024, verifica 2025-2026 (la selezione <=2022 del brief non e' possibile: il dato non esiste).
Prezzi: barre 1m gia' in cache (v5_um_1m_*). Ingresso all'apertura della prima barra 1m successiva all'istantanea."""
import glob, zipfile, io, numpy as np, pandas as pd, sys
DC = "/home/user/GERVA-Capital/data_cache"
def load(sym):
    out = []
    for f in sorted(glob.glob(f"{DC}/v6_raw/bd/{sym}-bookDepth-*.zip")):
        try:
            d = pd.read_csv(f)
        except Exception: continue
        d = d[d["percentage"].abs().isin([1, 2, 3, 5])]
        p = d.pivot_table(index="timestamp", columns="percentage", values="notional", aggfunc="last")
        out.append(p)
    P = pd.concat(out); P.index = pd.to_datetime(P.index); return P.sort_index()
HZ = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}
for sym in ("BTCUSDT", "ETHUSDT"):
    P = load(sym)
    P = P[~P.index.duplicated()].iloc[::2]                # ~1 al minuto
    F = pd.DataFrame(index=P.index)
    for k in (1, 2, 3, 5):
        F[f"imb{k}"] = (P[-k] - P[k]) / (P[-k] + P[k])
    F["imb1_d5m"] = F["imb1"] - F["imb1"].rolling("5min").mean()
    F["imb5_d1h"] = F["imb5"] - F["imb5"].rolling("60min").mean()
    px = pd.read_parquet(f"{DC}/v5_um_1m_{sym}.parquet", columns=["open"])["open"]
    t_in = F.index.ceil("1min") + pd.Timedelta(minutes=0)
    t_in = t_in.where(t_in > F.index, t_in + pd.Timedelta(minutes=1))     # barra che apre DOPO l'istantanea
    p0 = px.reindex(t_in).to_numpy()
    for hk, h in HZ.items():
        F["y_" + hk] = (px.reindex(t_in + pd.Timedelta(minutes=h)).to_numpy() / p0 - 1) * 1e4
    F = F.dropna(); feats = [c for c in F.columns if c.startswith("imb")]
    sel = F.index < "2025-01-01"; ver = ~sel
    mu, sd = F.loc[sel, feats].mean(), F.loc[sel, feats].std()
    Z = ((F[feats] - mu) / sd).clip(-5, 5).to_numpy(); Z1 = np.column_stack([np.ones(len(Z)), Z])
    print(f"\n=== {sym}: istantanee {len(F)}; fit 2023-24: {sel.sum()}, verifica 2025-26: {ver.sum()}; giorni {F.index.normalize().nunique()}")
    print("profondita' mediana entro 1% per lato (M$):", round(P[-1].median() / 1e6, 1), round(P[1].median() / 1e6, 1))
    for hk in HZ:
        y = F["y_" + hk].to_numpy(); b, *_ = np.linalg.lstsq(Z1[sel], y[sel], rcond=None); p = Z1 @ b
        r2 = lambda m: 1 - ((y[m] - p[m]) ** 2).sum() / ((y[m] - y[m].mean()) ** 2).sum()
        s = f"h={hk:>3}: R2 fit {r2(sel):+.5f} verifica {r2(ver):+.5f} |"
        for q in (.9, .99):
            thr = np.quantile(np.abs(p[sel] - p[sel].mean()), q); k = ver & (np.abs(p - p[sel].mean()) >= thr)
            g = np.sign(p[k] - p[sel].mean()) * y[k]
            dm = pd.Series(g, index=F.index[k]).groupby(lambda x: x.strftime("%Y-%m")).mean()
            s += f" top{round((1-q)*100)}%: {g.mean():+.2f} bp (n {k.sum()}, t mesi {dm.mean()/(dm.std(ddof=1)/np.sqrt(len(dm))):+.1f}) |"
        uni = " ".join(f"{f}={np.corrcoef(Z[ver, i], y[ver])[0,1]:+.3f}" for i, f in enumerate(feats))
        print(s, "corr ver:", uni)
