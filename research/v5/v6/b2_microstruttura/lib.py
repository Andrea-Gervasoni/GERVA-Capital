import os, glob, numpy as np, pandas as pd
DC = "/home/user/GERVA-Capital/data_cache"
G = 100; N = 864000
def day_files(sym):
    fs = sorted(glob.glob(f"{DC}/v6_g100_{sym}_*.parquet"))
    return [(os.path.basename(f).split("_")[-1][:10], f) for f in fs]
def ffill(x):
    x = np.asarray(x, float); idx = np.where(~np.isnan(x), np.arange(len(x)), -1)
    idx = np.maximum.accumulate(idx); out = x[np.maximum(idx, 0)]; out[idx < 0] = np.nan; return out
def csum0(x):
    return np.concatenate([[0.0], np.cumsum(np.nan_to_num(x, nan=0.0), dtype=float)])
def wsum(c, t, w):
    """somma sulle ultime w celle fino a t inclusa (causale)"""
    return c[t + 1] - c[np.maximum(t + 1 - w, 0)]
HS = {"1s": 10, "5s": 50, "30s": 300, "1m": 600, "5m": 3000}
LATS = {"0": 0, "200ms": 2, "500ms": 5, "1s": 10}
def features(df, step=10, book=True):
    """campiona ogni `step` celle. Tutte le feature usano solo dati <= t (fine cella t)."""
    n = len(df); t = np.arange(3000, n - 3000 - 20, step)     # 5 min di riscaldamento, coda per i target
    f = {}
    sgn = df["bv"].to_numpy(float) - df["sv"].to_numpy(float); vol = df["bv"].to_numpy(float) + df["sv"].to_numpy(float)
    cs, cv = csum0(sgn), csum0(vol)
    v5m = wsum(cv, t, 3000) + 1e-9
    if book:
        bid, ask = ffill(df["bid"]), ffill(df["ask"]); bq, aq = ffill(df["bq"]), ffill(df["aq"])
        mid = (bid + ask) / 2
        cd = csum0(bq + aq); dep = wsum(cd, t, 3000) / 3000 + 1e-9
        co = csum0(df["ofi"].to_numpy(float))
        for k, w in (("1s", 10), ("5s", 50), ("30s", 300)):
            f["ofi_" + k] = wsum(co, t, w) / dep
        f["imb"] = ((bq - aq) / (bq + aq))[t]
        micro = (ask * bq + bid * aq) / (bq + aq)
        f["mpd"] = ((micro - mid) / mid * 1e4)[t]
        f["spr"] = ((ask - bid) / mid * 1e4)[t]
    else:
        mid = ffill(df["tlast"]); bid = ask = mid
    for k, w in (("1s", 10), ("5s", 50), ("30s", 300)):
        f["tfi_" + k] = np.clip(wsum(cs, t, w) / (v5m * w / 3000), -30, 30)
        f["ret_" + k] = (mid[t] / mid[np.maximum(t - w, 0)] - 1) * 1e4
    F = pd.DataFrame(f); F["t"] = t
    return F, t, mid, bid, ask
