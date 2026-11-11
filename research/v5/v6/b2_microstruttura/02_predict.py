"""Test 1: prevedibilita' a breve da OFI, squilibrio L1, microprice, flusso dei trade, rendimenti passati.
A) con book (bookTicker Binance USDT-M, tick-by-tick -> griglia 100ms): fit 8 giorni 2023, verifica 8 giorni 2024.
B) solo trade (aggTrades): fit 2020-2022 (selezione), verifica 2023-2026.
Per ogni orizzonte: R2 in/out, edge lordo (bp, mid->mid) per i segnali piu' forti, a latenza 0/200ms/500ms/1s,
e netto taker (attraversa lo spread reale + 2 x 4.5 bp)."""
import sys, numpy as np, pandas as pd
from lib import *
FEE_T = 4.5
def build(sym, book):
    rows = []
    for d, f in day_files(sym):
        df = pd.read_parquet(f)
        if book and "bid" not in df.columns: continue
        F, t, mid, bid, ask = features(df, 10, book)
        for hk, h in HS.items():
            for lk, L in LATS.items():
                a, b = np.minimum(t + L, N - 1), np.minimum(t + L + h, N - 1)
                F[f"y_{hk}_{lk}"] = (mid[b] / mid[a] - 1) * 1e4
                if book:   # taker: long compra all'ask e rivende al bid; short il contrario (senza commissioni)
                    F[f"tl_{hk}_{lk}"] = (bid[b] / ask[a] - 1) * 1e4
                    F[f"ts_{hk}_{lk}"] = (1 - ask[b] / bid[a]) * 1e4
            ok = t + 10 + h < N
            F.loc[~ok, [c for c in F.columns if c.startswith(("y_" + hk, "tl_" + hk, "ts_" + hk))]] = np.nan
        F["day"] = d; rows.append(F.dropna(subset=[c for c in F.columns if not c.startswith(("y_", "tl_", "ts_"))]))
    return pd.concat(rows, ignore_index=True)

def run(sym, book, split):
    X = build(sym, book)
    feats = [c for c in X.columns if c.split("_")[0] in ("ofi", "imb", "mpd", "tfi", "ret")]
    sel = X["day"] < split; ver = ~sel
    mu, sd = X.loc[sel, feats].mean(), X.loc[sel, feats].std() + 1e-12
    Z = ((X[feats] - mu) / sd).clip(-5, 5).to_numpy(); Z1 = np.column_stack([np.ones(len(Z)), Z])
    print(f"\n=== {sym} {'BOOK+TRADE' if book else 'SOLO TRADE'}  selezione<{split}: {X.loc[sel,'day'].nunique()} giorni {sel.sum()} oss | verifica: {X.loc[ver,'day'].nunique()} giorni {ver.sum()} oss")
    if book: print("spread mediano bp: sel %.3f ver %.3f" % (X.loc[sel, "spr"].median(), X.loc[ver, "spr"].median()))
    res = []
    for hk in HS:
        y0 = X[f"y_{hk}_0"].to_numpy(); m = sel.to_numpy() & ~np.isnan(y0)
        beta, *_ = np.linalg.lstsq(Z1[m], y0[m], rcond=None); p = Z1 @ beta
        def r2(mask, y):
            k = mask & ~np.isnan(y); return 1 - ((y[k] - p[k]) ** 2).sum() / ((y[k] - y[k].mean()) ** 2).sum()
        line = dict(sym=sym, h=hk, R2_sel=r2(sel.to_numpy(), y0))
        for lk in LATS: line["R2_ver_L" + lk] = r2(ver.to_numpy(), X[f"y_{hk}_{lk}"].to_numpy())
        # soglie dei quantili scelte sulla selezione
        ap = np.abs(p); v = ver.to_numpy()
        for qn, q in (("top10%", .90), ("top1%", .99), ("top0.1%", .999)):
            thr = np.quantile(ap[sel.to_numpy()], q); k = v & (ap >= thr)
            for lk in LATS:
                y = X[f"y_{hk}_{lk}"].to_numpy(); kk = k & ~np.isnan(y)
                g = np.sign(p[kk]) * y[kk]; line[f"gross_{qn}_L{lk}"] = g.mean()
                if lk == "1s":
                    dm = pd.Series(g).groupby(X.loc[kk, "day"].to_numpy()).mean()
                    line[f"t_{qn}"] = dm.mean() / (dm.std(ddof=1) / np.sqrt(len(dm)) + 1e-12); line[f"n_{qn}"] = int(kk.sum())
                if book and lk in ("200ms", "1s"):
                    tl = X[f"tl_{hk}_{lk}"].to_numpy(); ts = X[f"ts_{hk}_{lk}"].to_numpy()
                    net = np.where(p[kk] > 0, tl[kk], ts[kk]); line[f"takerNoFee_{qn}_L{lk}"] = np.nanmean(net)
        res.append(line)
        if hk in ("1s", "30s"):
            uni = {f: np.corrcoef(Z[v & ~np.isnan(y0), i], y0[v & ~np.isnan(y0)])[0, 1] for i, f in enumerate(feats)}
            print(f"  corr univariata (verifica) con rendimento a {hk}: " + " ".join(f"{k}={x:+.3f}" for k, x in uni.items()))
            print(f"  beta (bp per 1 sd) a {hk}: " + " ".join(f"{k}={x:+.3f}" for k, x in zip(feats, beta[1:])))
    R = pd.DataFrame(res).set_index("h")
    pd.set_option("display.width", 250); pd.set_option("display.float_format", lambda x: f"{x:.4f}")
    print("R2:"); print(R[[c for c in R.columns if c.startswith("R2")]].to_string())
    for qn in ("top10%", "top1%", "top0.1%"):
        cols = [c for c in R.columns if qn + "_" in c or c.endswith("_" + qn)]
        print(f"edge lordo bp mid->mid, segnali {qn} (soglia da selezione); takerNoFee = attraversando lo spread, prima delle commissioni; t = t-stat tra giorni a L=1s:")
        print(R[cols].rename(columns=lambda c: c.replace("_" + qn, "")).to_string(float_format=lambda x: f"{x:.3f}"))
    best = max(R[f"gross_{q}_L200ms"].max() for q in ("top10%", "top1%", "top0.1%"))
    print(f"MIGLIORE edge lordo a latenza 200ms: {best:.2f} bp  vs costo taker andata/ritorno {2*FEE_T:.1f} bp + spread  -> commissione di pareggio per lato = {best/2:.2f} bp")
    return R

if __name__ == "__main__":
    out = {}
    for sym in ("BTCUSDT", "ETHUSDT"):
        out[sym, "book"] = run(sym, True, "2024-01-01")
        out[sym, "trade"] = run(sym, False, "2023-01-01")
    pd.concat(out).to_csv("02_predict.csv")
