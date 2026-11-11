"""Converte la registrazione live (data_cache/v6_live/*.jsonl.gz) in griglie a 100 ms per moneta, indicizzate sull'ORA DI RICEZIONE
LOCALE (quello che un trader su questa macchina vede davvero). Salva data_cache/v6_livegrid_{coin}.parquet e le statistiche di latenza."""
import glob, gzip, json, sys, numpy as np, pandas as pd
DC = "/home/user/GERVA-Capital/data_cache"; LV = DC + "/v6_live"; G = 100_000_000
def rd(prefix):
    for f in sorted(glob.glob(f"{LV}/{prefix}_*.jsonl.gz")):
        try:
            with gzip.open(f, "rt") as fh:
                for line in fh:
                    try: yield json.loads(line)
                    except Exception: pass
        except (EOFError, OSError):
            pass
def last_state(n, b, vals):
    """stato all'ultima riga con cella <= i (forward fill)"""
    li = np.full(n, -1, np.int64); li[b] = np.arange(len(b)); li = np.maximum.accumulate(li)
    out = []
    for v in vals:
        x = np.asarray(v, float)[np.maximum(li, 0)]; x[li < 0] = np.nan; out.append(x)
    return out
def tgrid(n, b, px, q, buy):
    bv = np.bincount(b[buy], q[buy], n); sv = np.bincount(b[~buy], q[~buy], n)
    g = pd.DataFrame({"b": b, "p": px}).groupby("b")["p"].agg(["max", "min", "last"])
    hi = np.full(n, np.nan); lo = np.full(n, np.nan); la = np.full(n, np.nan); hi[g.index] = g["max"]; lo[g.index] = g["min"]; la[g.index] = g["last"]
    return bv, sv, hi, lo, la
MAP = {"BTC": ("BTCUSDT", "PF_XBTUSD"), "ETH": ("ETHUSDT", "PF_ETHUSD"), "SOL": ("SOLUSDT", "PF_SOLUSD")}
raw = {}
for p in ("hl_bbo", "hl_l2", "hl_l2f", "hl_tr", "bn_bt", "bn_d5", "bn_tr", "sp_bt", "kr_tk", "kr_tr", "bn_liq"):
    raw[p] = list(rd(p)); print(p, len(raw[p]), flush=True)
t0 = max(min(r[0] for r in raw[p]) for p in ("hl_bbo", "bn_bt", "bn_tr", "kr_tk")) + 5 * 10**9
t1 = min(max(r[0] for r in raw[p]) for p in ("hl_bbo", "bn_bt", "bn_tr", "kr_tk")) - 10**9
n = int((t1 - t0) // G); print("inizio", pd.Timestamp(t0, unit="ns"), "fine", pd.Timestamp(t1, unit="ns"), "celle", n, "ore %.2f" % (n / 36000))
lat = []
def sel(p, key):
    r = [x for x in raw[p] if x[1] == key and t0 <= x[0] < t0 + n * G]
    b = np.array([(x[0] - t0) // G for x in r], dtype=np.int64); return r, b
# book Kraken: ricostruzione da snapshot + delta
def kraken_book(prod):
    bids, asks = {}, {}; nxt = 0; out = np.full((n, 6), np.nan); have = False
    def snap(i):
        if not bids or not asks: return
        bb = max(bids); ba = min(asks); m = (bb + ba) / 2
        out[i] = (bb, ba, bids[bb], asks[ba], sum(q for p, q in bids.items() if p >= m * (1 - 5e-4)), sum(q for p, q in asks.items() if p <= m * (1 + 5e-4)))
    for x in rd("kr_bk"):
        if x[1] != prod: continue
        i = (x[0] - t0) // G
        if have and i > nxt:
            for k in range(max(nxt, 0), min(i, n)): snap(k)     # stato a fine cella k
            nxt = i
        if x[3] == "S":
            bids = {float(l["price"]): float(l["qty"]) for l in x[4]}; asks = {float(l["price"]): float(l["qty"]) for l in x[5]}; have = True; nxt = max(i, 0)
            # NB: lo snapshot registrato e' troncato a 20 livelli per lato: i livelli piu' lontani arrivano dai delta
        else:
            side = bids if x[3] == "buy" else asks
            if x[5] == 0: side.pop(float(x[4]), None)
            else: side[float(x[4])] = float(x[5])
            # pulizia di livelli incrociati rimasti da uno snapshot troncato
        if i >= n: break
    return out
for coin, (bs, kp) in MAP.items():
    D = {}
    r, b = sel("hl_bbo", coin)
    D["hl_bid"], D["hl_ask"], D["hl_bq"], D["hl_aq"] = last_state(n, b, [[float(x[3] or "nan") for x in r], [float(x[5] or "nan") for x in r], [float(x[4] or "nan") for x in r], [float(x[6] or "nan") for x in r]])
    lat.append(("hl_bbo", coin, np.array([x[0] / 1e6 - x[2] for x in r])))
    r, b = sel("hl_l2", coin)
    cols = {k: [] for k in ("i1", "i5", "i10", "i20", "d5b", "d5a", "l2bid", "l2ask")}
    for x in r:
        bp = np.array([[float(l[0]), float(l[1])] for l in x[3]]); ap = np.array([[float(l[0]), float(l[1])] for l in x[4]])
        for k in (1, 5, 10, 20):
            sb, sa = bp[:k, 1].sum(), ap[:k, 1].sum(); cols[f"i{k}"].append((sb - sa) / (sb + sa))
        m = (bp[0, 0] + ap[0, 0]) / 2
        cols["d5b"].append((bp[bp[:, 0] >= m * (1 - 5e-4), 1] * bp[bp[:, 0] >= m * (1 - 5e-4), 0]).sum()); cols["d5a"].append((ap[ap[:, 0] <= m * (1 + 5e-4), 1] * ap[ap[:, 0] <= m * (1 + 5e-4), 0]).sum())
        cols["l2bid"].append(bp[0, 0]); cols["l2ask"].append(ap[0, 0])
    for k, v in zip(cols, last_state(n, b, list(cols.values()))): D["hl_" + k] = v
    D["hl_l2n"] = np.bincount(b, minlength=n)
    lat.append(("hl_l2", coin, np.array([x[0] / 1e6 - x[2] for x in r])))
    r, b = sel("hl_l2f", coin)
    if len(r):
        c2 = {k: [] for k in ("f1", "f2", "f5", "fmp")}
        for x in r:
            bp = np.array([[float(l[0]), float(l[1])] for l in x[3]]); ap = np.array([[float(l[0]), float(l[1])] for l in x[4]])
            for k in (1, 2, 5):
                sb, sa = bp[:k, 1].sum(), ap[:k, 1].sum(); c2[f"f{k}"].append((sb - sa) / (sb + sa))
            c2["fmp"].append(((ap[0, 0] * bp[0, 1] + bp[0, 0] * ap[0, 1]) / (bp[0, 1] + ap[0, 1]) / ((ap[0, 0] + bp[0, 0]) / 2) - 1) * 1e4)
        for k, v in zip(c2, last_state(n, b, list(c2.values()))): D["hl_" + k] = v
        D["hl_l2fn"] = np.bincount(b, minlength=n)
        lat.append(("hl_l2f", coin, np.array([x[0] / 1e6 - x[2] for x in r])))
    r, b = sel("hl_tr", coin)
    D["hl_bv"], D["hl_sv"], D["hl_thi"], D["hl_tlo"], D["hl_tlast"] = tgrid(n, b, np.array([float(x[4]) for x in r]), np.array([float(x[5]) for x in r]), np.array([x[3] == "B" for x in r]))
    lat.append(("hl_tr", coin, np.array([x[0] / 1e6 - x[2] for x in r])))
    r, b = sel("bn_bt", bs)
    D["bn_bid"], D["bn_ask"], D["bn_bq"], D["bn_aq"] = last_state(n, b, [[float(x[4]) for x in r], [float(x[6]) for x in r], [float(x[5]) for x in r], [float(x[7]) for x in r]])
    lat.append(("bn_bt", coin, np.array([x[0] / 1e6 - x[2] for x in r])))
    r, b = sel("bn_d5", bs)
    i5 = [(sum(float(l[1]) for l in x[4]) - sum(float(l[1]) for l in x[5])) / (sum(float(l[1]) for l in x[4]) + sum(float(l[1]) for l in x[5]) + 1e-12) for x in r]
    D["bn_i5"], = last_state(n, b, [i5])
    r, b = sel("bn_tr", bs)
    D["bn_bv"], D["bn_sv"], D["bn_thi"], D["bn_tlo"], D["bn_tlast"] = tgrid(n, b, np.array([float(x[4]) for x in r]), np.array([float(x[5]) for x in r]), np.array([x[6] == 0 for x in r]))
    lat.append(("bn_tr", coin, np.array([x[0] / 1e6 - x[2] for x in r])))
    r, b = sel("sp_bt", bs)
    if len(r): D["sp_bid"], D["sp_ask"] = last_state(n, b, [[float(x[3]) for x in r], [float(x[5]) for x in r]])
    r, b = sel("kr_tk", kp)
    D["krt_bid"], D["krt_ask"] = last_state(n, b, [[x[3] for x in r], [x[5] for x in r]])
    lat.append(("kr_tk", coin, np.array([x[0] / 1e6 - x[2] for x in r])))
    r, b = sel("kr_tr", kp)
    if len(r):
        D["kr_bv"], D["kr_sv"], D["kr_thi"], D["kr_tlo"], D["kr_tlast"] = tgrid(n, b, np.array([float(x[4]) for x in r]), np.array([float(x[5]) for x in r]), np.array([x[3] == "buy" for x in r]))
        lat.append(("kr_tr", coin, np.array([x[0] / 1e6 - x[2] for x in r])))
    kb = kraken_book(kp)
    for j, k in enumerate(("kr_bid", "kr_ask", "kr_bq", "kr_aq", "kr_d5b", "kr_d5a")): D[k] = kb[:, j]
    df = pd.DataFrame(D); df.attrs = {}
    df.to_parquet(f"{DC}/v6_livegrid_{coin}.parquet", compression="zstd")
    print(coin, df.shape, "NaN%:", (df[["hl_bid", "bn_bid", "kr_bid", "krt_bid"]].isna().mean() * 100).round(2).to_dict(), flush=True)
print("\nLATENZA osservata = ora di ricezione locale - timestamp dello exchange (ms). Include lo scarto dell'orologio locale (non sincronizzato via NTP: vedi REPORT).")
for nm, coin, x in lat:
    if len(x): print(f"{nm:7s} {coin}: n={len(x):7d} p5={np.percentile(x,5):7.0f} mediana={np.median(x):7.0f} p95={np.percentile(x,95):7.0f} p99={np.percentile(x,99):7.0f}")
# alt: bbo + trades
ab = list(rd("hl_altbbo")); at = list(rd("hl_alttr"))
if ab:
    a0 = min(x[0] for x in ab) + 5 * 10**9; a1 = max(x[0] for x in ab) - 10**9; na = int((a1 - a0) // G)
    for coin in sorted({x[1] for x in ab}):
        r = [x for x in ab if x[1] == coin and a0 <= x[0] < a0 + na * G and x[3] and x[5]]; b = np.array([(x[0] - a0) // G for x in r], dtype=np.int64)
        if len(r) < 50: continue
        D = {}
        D["hl_bid"], D["hl_ask"], D["hl_bq"], D["hl_aq"] = last_state(na, b, [[float(x[3]) for x in r], [float(x[5]) for x in r], [float(x[4]) for x in r], [float(x[6]) for x in r]])
        r = [x for x in at if x[1] == coin and a0 <= x[0] < a0 + na * G]; b = np.array([(x[0] - a0) // G for x in r], dtype=np.int64)
        if len(r) == 0: continue
        D["hl_bv"], D["hl_sv"], D["hl_thi"], D["hl_tlo"], D["hl_tlast"] = tgrid(na, b, np.array([float(x[4]) for x in r]), np.array([float(x[5]) for x in r]), np.array([x[3] == "B" for x in r]))
        pd.DataFrame(D).to_parquet(f"{DC}/v6_livealt_{coin}.parquet", compression="zstd")
    print("alt: ore %.2f" % (na / 36000), "monete", len({x[1] for x in ab}))
json.dump({"t0": int(t0), "n": int(n), "liq": raw["bn_liq"]}, open(f"{DC}/v6_livegrid_meta.json", "w"))
