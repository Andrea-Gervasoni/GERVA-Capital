"""Scarica da data.binance.vision e riduce a griglia 100 ms (chiavi data_cache/v6_g100_*).
perp: aggTrades (2020-2026) + bookTicker (disponibile SOLO 2023-05-16 -> 2024-03-30) ; spot: aggTrades.
Uso: python 01_build.py [nworkers]"""
import os, sys, io, zipfile, subprocess, numpy as np, pandas as pd, pyarrow as pa, pyarrow.csv as pc
from concurrent.futures import ProcessPoolExecutor
DC = "/home/user/GERVA-Capital/data_cache"; RAW = DC + "/v6_raw"; os.makedirs(RAW, exist_ok=True)
G = 100; N = 86400_000 // G
BASE = "https://data.binance.vision/data"

def days():
    rng = np.random.default_rng(20261111)
    def pick(a, b, n):
        d = pd.date_range(a, b, freq="D"); return sorted(rng.choice(d, n, replace=False))
    out = []
    out += [(d, 0) for d in pick("2020-03-01", "2020-12-31", 4)]
    out += [(d, 0) for d in pick("2021-01-01", "2021-12-31", 6)]
    out += [(d, 0) for d in pick("2022-01-01", "2022-12-31", 6)]
    out += [(d, 1) for d in pick("2023-05-16", "2023-12-31", 8)]      # con bookTicker
    out += [(d, 1) for d in pick("2024-01-01", "2024-03-30", 8)]      # con bookTicker
    out += [(d, 0) for d in pick("2024-04-01", "2024-12-31", 3)]
    out += [(d, 0) for d in pick("2025-01-01", "2025-12-31", 5)]
    out += [(d, 0) for d in pick("2026-01-01", "2026-11-09", 5)]
    return [(pd.Timestamp(d).strftime("%Y-%m-%d"), bt) for d, bt in out]

def fetch(url, dst):
    if os.path.exists(dst) and os.path.getsize(dst) > 0: return True
    r = subprocess.run(["curl", "-s", "-f", "--retry", "3", "-o", dst + ".tmp", url])
    if r.returncode != 0:
        if os.path.exists(dst + ".tmp"): os.remove(dst + ".tmp")
        return False
    os.rename(dst + ".tmp", dst); return True

def read_zip_csv(path, names):
    z = zipfile.ZipFile(path); raw = z.read(z.namelist()[0])
    has_header = not raw[:1].isdigit()
    ro = pc.ReadOptions(column_names=names, skip_rows=1 if has_header else 0, block_size=1 << 26)
    return pc.read_csv(io.BytesIO(raw), read_options=ro)

def ms(t):
    t = np.asarray(t, dtype=np.int64)
    return t // 1000 if t[0] > 10**14 else t

def trades_grid(path, day0, spot):
    names = ["id", "p", "q", "f", "l", "T", "m"] + (["M"] if spot else [])
    t = read_zip_csv(path, names)
    T = ms(t["T"].to_numpy()); p = t["p"].to_numpy().astype(float); q = t["q"].to_numpy().astype(float)
    m = t["m"].to_numpy()
    if m.dtype != bool: m = np.char.lower(m.astype(str)) == "true"
    b = np.clip((T - day0) // G, 0, N - 1)
    buy = ~m
    bv = np.bincount(b[buy], q[buy], N); sv = np.bincount(b[~buy], q[~buy], N)
    nb = np.bincount(b[buy], minlength=N); ns = np.bincount(b[~buy], minlength=N)
    s = pd.DataFrame({"b": b, "p": p}); g = s.groupby("b")["p"].agg(["last", "max", "min"])
    last = np.full(N, np.nan); hi = np.full(N, np.nan); lo = np.full(N, np.nan)
    last[g.index] = g["last"]; hi[g.index] = g["max"]; lo[g.index] = g["min"]
    return dict(bv=bv.astype("f4"), sv=sv.astype("f4"), nb=nb.astype("i4"), ns=ns.astype("i4"), tlast=last, thi=hi, tlo=lo)

def book_grid(path, day0):
    t = read_zip_csv(path, ["u", "b", "bq", "a", "aq", "T", "E"])
    T = t["T"].to_numpy().astype(np.int64); o = np.argsort(T, kind="stable")
    T = T[o]; b = t["b"].to_numpy().astype(float)[o]; a = t["a"].to_numpy().astype(float)[o]
    bq = t["bq"].to_numpy().astype(float)[o]; aq = t["aq"].to_numpy().astype(float)[o]
    del t
    e = np.zeros(len(T))
    e[1:] = ((b[1:] >= b[:-1]) * bq[1:] - (b[1:] <= b[:-1]) * bq[:-1]
             - (a[1:] <= a[:-1]) * aq[1:] + (a[1:] >= a[:-1]) * aq[:-1])
    bn = np.clip((T - day0) // G, 0, N - 1)
    ofi = np.bincount(bn, e, N); nu = np.bincount(bn, minlength=N)
    lastidx = np.full(N, -1, dtype=np.int64); lastidx[bn] = np.arange(len(bn))
    lastidx = np.maximum.accumulate(lastidx)
    ok = lastidx >= 0; li = np.where(ok, lastidx, 0)
    out = {}
    for k, v in (("bid", b), ("ask", a), ("bq", bq), ("aq", aq)):
        x = v[li].copy(); x[~ok] = np.nan; out[k] = x
    out["ofi"] = ofi.astype("f4"); out["nupd"] = nu.astype("i4")
    return out

def do(args):
    sym, d, bt = args
    key = f"{DC}/v6_g100_{sym}_{d}.parquet"
    if os.path.exists(key): return key, "cached"
    day0 = int(pd.Timestamp(d, tz="UTC").timestamp() * 1000)
    cols = {}
    try:
        f = f"{RAW}/um_ag_{sym}_{d}.zip"
        if not fetch(f"{BASE}/futures/um/daily/aggTrades/{sym}/{sym}-aggTrades-{d}.zip", f): return key, "no aggTrades"
        cols.update(trades_grid(f, day0, False))
        f = f"{RAW}/sp_ag_{sym}_{d}.zip"
        if fetch(f"{BASE}/spot/daily/aggTrades/{sym}/{sym}-aggTrades-{d}.zip", f):
            s = trades_grid(f, day0, True)
            cols.update({"s_" + k: v for k, v in s.items() if k in ("bv", "sv", "tlast")})
        if bt:
            f = f"{RAW}/um_bt_{sym}_{d}.zip"
            if fetch(f"{BASE}/futures/um/daily/bookTicker/{sym}/{sym}-bookTicker-{d}.zip", f):
                cols.update(book_grid(f, day0)); os.remove(f)
        pd.DataFrame(cols).to_parquet(key + ".tmp", compression="zstd"); os.rename(key + ".tmp", key)
        return key, "ok " + ",".join(cols)
    except Exception as ex:
        return key, "ERR " + repr(ex)[:300]

if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    jobs = [(s, d, bt) for d, bt in days() for s in ("BTCUSDT", "ETHUSDT")]
    print(len(jobs), "jobs;", days())
    with ProcessPoolExecutor(nw) as ex:
        for k, r in ex.map(do, jobs): print(os.path.basename(k), r, flush=True)
