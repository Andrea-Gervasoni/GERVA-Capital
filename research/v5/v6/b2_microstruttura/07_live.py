"""Analisi della registrazione live (griglia 100 ms sull'ora di ricezione locale). Uso: python 07_live.py A B ...
A) spread e profondita' reali  B) lead-lag Binance -> Hyperliquid / Kraken  C) prevedibilita' del mid Hyperliquid (fit prima meta', verifica seconda)
D) market making su Hyperliquid (BTC/ETH/SOL e 20 perps meno liquidi) con fill conservativo  E) liquidazioni Binance."""
import sys, glob, json, os, numpy as np, pandas as pd
from lib import ffill, csum0, wsum
from mm import mm_sim, summarize
DC = "/home/user/GERVA-Capital/data_cache"; SEGS = sys.argv[1:] or ["A"]
pd.set_option("display.width", 250)
def L(seg, coin): return pd.read_parquet(f"{DC}/v6_livegrid_{seg}_{coin}.parquet")
hours = sum(len(L(s, "BTC")) for s in SEGS) / 36000
print(f"segmenti {SEGS}: {hours:.2f} ore di registrazione (BTC/ETH/SOL)")
print("\n=== A) SPREAD E PROFONDITA' (mediane; bp e migliaia di $)")
rows = []
for c in ("BTC", "ETH", "SOL"):
    d = pd.concat([L(s, c) for s in SEGS]); m = (d.hl_bid + d.hl_ask) / 2
    rows.append(dict(coin=c, HL_spread_bp=((d.hl_ask - d.hl_bid) / m * 1e4).median(), HL_spread_media=((d.hl_ask - d.hl_bid) / m * 1e4).mean(), HL_L1_k=((d.hl_bq + d.hl_aq) / 2 * m).median() / 1e3,
                     HL_entro5bp_k=((d.hl_d5b + d.hl_d5a) / 2).median() / 1e3, BN_spread_bp=((d.bn_ask - d.bn_bid) / d.bn_bid * 1e4).median(), BN_L1_k=((d.bn_bq + d.bn_aq) / 2 * d.bn_bid).median() / 1e3,
                     KR_spread_bp=((d.kr_ask - d.kr_bid) / d.kr_bid * 1e4).median(), KR_spread_media=((d.kr_ask - d.kr_bid) / d.kr_bid * 1e4).mean(),
                     HL_vol_M_ora=((d.hl_bv + d.hl_sv) * m).sum() / 1e6 / hours, BN_vol_M_ora=((d.bn_bv + d.bn_sv) * d.bn_bid).sum() / 1e6 / hours, KR_vol_M_ora=((d.get("kr_bv", 0) + d.get("kr_sv", 0)) * d.kr_bid).sum() / 1e6 / hours))
print(pd.DataFrame(rows).set_index("coin").round(3).T.to_string())

print("\n=== B) LEAD-LAG Binance perp -> Hyperliquid e -> Kraken Futures")
LAT = {"0": 0, "200ms": 2, "500ms": 5, "700ms": 7, "1s": 10}
ALL = []
for c in ("BTC", "ETH", "SOL"):
    cc = {}; ev = []
    for s in SEGS:
        d = L(s, c); n = len(d); bn = ((d.bn_bid + d.bn_ask) / 2).to_numpy()
        ven = {"HL": (d.hl_bid.to_numpy(), d.hl_ask.to_numpy()), "KR": (d.kr_bid.to_numpy(), d.kr_ask.to_numpy())}
        t = np.arange(100, n - 400)
        for v, (b, a) in ven.items():
            m = (b + a) / 2
            for lk, l in (("-1s", -10), ("-500ms", -5), ("0", 0), ("200ms", 2), ("500ms", 5), ("1s", 10), ("2s", 20), ("5s", 50)):
                x = (bn[t] / bn[t - 10] - 1); y = (m[t + l + 10] / m[t + l] - 1); k = ~np.isnan(x) & ~np.isnan(y)
                cc.setdefault((v, lk), []).append(np.corrcoef(x[k], y[k])[0, 1])
            r5 = (bn[t] / bn[t - 5] - 1) * 1e4; own = (m[t] / m[t - 5] - 1) * 1e4
            for X in (2, 4, 6, 8):
                idx = t[np.abs(r5) >= X]; keep = []; last = -100
                for i in idx:
                    if i - last >= 20: keep.append(i); last = i
                keep = np.array(keep, dtype=int)
                if len(keep) == 0: continue
                sg = np.sign(bn[keep] / bn[keep - 5] - 1)
                for lk, l in LAT.items():
                    for hk, h in (("5s", 50), ("30s", 300)):
                        gross = sg * (m[keep + l + h] / m[keep + l] - 1) * 1e4
                        tk = np.where(sg > 0, b[keep + l + h] / a[keep + l] - 1, 1 - a[keep + l + h] / b[keep + l]) * 1e4
                        ev.append(pd.DataFrame(dict(seg=s, cl=keep // 30, v=v, X=X, L=lk, h=hk, lead=np.abs(r5[keep - 100]), gia=sg * own[keep - 100], gross=gross, taker_no_fee=tk)))
    C = pd.Series({k: np.nanmean(v) for k, v in cc.items()}).unstack(1)[["-1s", "-500ms", "0", "200ms", "500ms", "1s", "2s", "5s"]]
    print(f"\n{c}: corr( rend. 1s Binance fino a t , rend. 1s della sede da t+l a t+l+1s )  [l<0: finestre sovrapposte]"); print(C.round(3).to_string())
    E = pd.concat(ev); ALL.append(E.assign(coin=c))
    print(f"{c}: evento = mid Binance mosso >= X bp in 500 ms. 'gia' = quanto la sede si e' gia' mossa; gross = mid->mid dopo latenza L; taker_no_fee = attraversando lo spread (commissioni: HL 9 bp a/r, Kraken ~10 bp a/r)")
    print(E.groupby(["v", "X", "h", "L"]).agg(n=("gross", "size"), lead=("lead", "mean"), gia=("gia", "mean"), gross=("gross", "mean"), taker_no_fee=("taker_no_fee", "mean"),
          t=("gross", lambda x: x.mean() / (x.std() / np.sqrt(len(x)) + 1e-12))).round(2).to_string())

P = pd.concat(ALL); P["net_taker"] = P.taker_no_fee - np.where(P.v == "HL", 9.0, 10.0)
print("\nTUTTE E TRE LE MONETE insieme: net_taker = dopo spread e commissioni (HL 9 bp, Kraken 10 bp a/r); win = quota di eventi con netto > 0")
print(P[P.L.isin(["500ms", "700ms", "1s"])].groupby(["v", "X", "h", "L"]).agg(n=("gross", "size"), lead=("lead", "mean"), gross=("gross", "mean"), taker_no_fee=("taker_no_fee", "mean"),
      net_taker=("net_taker", "mean"), mediana=("net_taker", "median"), t_net=("net_taker", lambda x: x.mean() / (x.std() / np.sqrt(len(x)) + 1e-12)), win=("net_taker", lambda x: (x > 0).mean())).round(2).to_string())
print("\nStessi eventi raggruppati in grappoli indipendenti (le tre monete saltano insieme: un grappolo = 3 s). HL, uscita a 30 s e a 5 s:")
for X in (4, 6, 8):
    for hk in ("5s", "30s"):
        for lk in ("500ms", "700ms", "1s"):
            x = P[(P.v == "HL") & (P.X == X) & (P.h == hk) & (P.L == lk)]; g = x.groupby(["seg", "cl"]).net_taker.mean()
            if len(g) > 1: print(f"  X>={X} bp, uscita {hk}, L={lk}: grappoli {len(g)} ({len(g)/hours:.1f}/ora), netto medio {g.mean():+.2f} bp, t {g.mean()/(g.std(ddof=1)/np.sqrt(len(g))):+.2f}, positivi {(g>0).mean():.0%}")
print("\n=== C) PREVEDIBILITA' del mid Hyperliquid (campioni ogni 1 s; fit prima meta', verifica seconda meta')")
HZ = {"1s": 10, "5s": 50, "30s": 300, "1m": 600, "5m": 3000}
for c in ("BTC", "ETH", "SOL"):
    FS = []
    for s in SEGS:
        d = L(s, c); n = len(d); t = np.arange(3000, n - 3020, 10)
        if len(t) < 100: continue
        b, a = d.hl_bid.to_numpy(), d.hl_ask.to_numpy(); m = (b + a) / 2; bn = ((d.bn_bid + d.bn_ask) / 2).to_numpy()
        gap = np.log(bn / m); gs = pd.Series(gap); gapd = (gs - gs.rolling(3000, min_periods=300).mean()).to_numpy() * 1e4
        sg = (d.hl_bv - d.hl_sv).to_numpy(); cs = csum0(sg); cv = csum0((d.hl_bv + d.hl_sv).to_numpy())
        bs = csum0((d.bn_bv - d.bn_sv).to_numpy()); bv = csum0((d.bn_bv + d.bn_sv).to_numpy())
        F = pd.DataFrame({"hl_imbL1": ((d.hl_bq - d.hl_aq) / (d.hl_bq + d.hl_aq)).to_numpy()[t], "hl_imb2": d.hl_f2.to_numpy()[t], "hl_imb5": d.hl_f5.to_numpy()[t], "hl_imb10": d.hl_i10.to_numpy()[t],
                          "hl_imb20": d.hl_i20.to_numpy()[t], "hl_micro": d.hl_fmp.to_numpy()[t], "hl_tfi5s": np.clip(wsum(cs, t, 50) / (wsum(cv, t, 3000) / 60 + 1e-9), -30, 30),
                          "hl_ret1s": (m[t] / m[t - 10] - 1) * 1e4, "hl_ret5s": (m[t] / m[t - 50] - 1) * 1e4, "gap_bn_hl": gapd[t], "bn_ret1s": (bn[t] / bn[t - 10] - 1) * 1e4,
                          "bn_ret5s": (bn[t] / bn[t - 50] - 1) * 1e4, "bn_imb5": d.bn_i5.to_numpy()[t], "bn_tfi5s": np.clip(wsum(bs, t, 50) / (wsum(bv, t, 3000) / 60 + 1e-9), -30, 30)})
        for hk, h in HZ.items():
            for lk, l in LAT.items():
                F[f"y_{hk}_{lk}"] = (m[t + l + h] / m[t + l] - 1) * 1e4
                F[f"tl_{hk}_{lk}"] = (b[t + l + h] / a[t + l] - 1) * 1e4; F[f"ts_{hk}_{lk}"] = (1 - a[t + l + h] / b[t + l]) * 1e4
        FS.append(F)
    X = pd.concat(FS, ignore_index=True).dropna(); feats = [x for x in X.columns if not x.startswith(("y_", "tl_", "ts_"))]
    cut = len(X) // 2; sel = np.arange(len(X)) < cut; ver = ~sel
    mu, sd = X.loc[sel, feats].mean(), X.loc[sel, feats].std() + 1e-12; Z = ((X[feats] - mu) / sd).clip(-5, 5).to_numpy(); Z1 = np.column_stack([np.ones(len(Z)), Z])
    print(f"\n{c}: {len(X)} campioni ({sel.sum()} fit, {ver.sum()} verifica)")
    for hk in HZ:
        y = X[f"y_{hk}_0"].to_numpy(); be, *_ = np.linalg.lstsq(Z1[sel], y[sel], rcond=None); p = Z1 @ be
        s = f"  h={hk:>3} R2 fit {1 - ((y[sel]-p[sel])**2).sum()/((y[sel]-y[sel].mean())**2).sum():+.4f} |"
        for lk in LAT:
            yy = X[f"y_{hk}_{lk}"].to_numpy(); s += f" R2 ver L{lk} {1 - ((yy[ver]-p[ver])**2).sum()/((yy[ver]-yy[ver].mean())**2).sum():+.4f}"
        thr = np.quantile(np.abs(p[sel]), 0.9); k = ver & (np.abs(p) >= thr)
        for lk in ("200ms", "1s"):
            g = np.sign(p[k]) * X.loc[k, f"y_{hk}_{lk}"]; tk = np.where(p[k] > 0, X.loc[k, f"tl_{hk}_{lk}"], X.loc[k, f"ts_{hk}_{lk}"])
            s += f" | top10% L{lk}: lordo {g.mean():+.2f} bp, taker senza comm. {tk.mean():+.2f} (n {k.sum()})"
        print(s)
        if hk == "5s": print("      corr univariata in verifica (5s): " + " ".join(f"{f}={np.corrcoef(Z[ver, i], y[ver])[0,1]:+.3f}" for i, f in enumerate(feats)))

print("\n=== D) MARKET MAKING su Hyperliquid, fill conservativo (trade oltre la quota) e limite superiore 'al tocco'. Commissione maker 1.5 bp.")
def mmrun(d, dd, Lg, touch):
    b, a = d.hl_bid.to_numpy(float), d.hl_ask.to_numpy(float); m = (b + a) / 2
    hi = np.where(np.isnan(d.hl_thi), -np.inf, d.hl_thi); lo = np.where(np.isnan(d.hl_tlo), np.inf, d.hl_tlo)
    r = mm_sim(b, a, hi, lo, np.zeros(len(b)), float(dd), 10, Lg, 5, dd / 5 if dd > 0 else 0.0, 0.0, 100, touch)
    return summarize(*r, m)
rows = []
alts = sorted({os.path.basename(f).split("_")[-1][:-8] for s in SEGS for f in glob.glob(f"{DC}/v6_livealt_{s}_*.parquet")})
for c in ["BTC", "ETH", "SOL"] + alts:
    for dd in (0.0, 2.0, 5.0):
        for Lg in (5, 10):
            for touch in (False, True):
                tot = dict(fills=0, pnl=0.0, ntl=0.0, capt=0.0, mo1=0.0, mo60=0.0, cells=0); spr = []
                for s in SEGS:
                    f = f"{DC}/v6_livegrid_{s}_{c}.parquet" if c in ("BTC", "ETH", "SOL") else f"{DC}/v6_livealt_{s}_{c}.parquet"
                    if not os.path.exists(f): continue
                    d = pd.read_parquet(f); r = mmrun(d, dd, Lg, touch); tot["cells"] += len(d); spr.append(((d.hl_ask - d.hl_bid) / d.hl_bid * 1e4).median())
                    if r["fills"]:
                        k = r["fills"]; tot["fills"] += k; tot["pnl"] += r["pnl_gross_$"]; tot["ntl"] += r["ntl"]; tot["capt"] += r["capt_bp"] * k; tot["mo1"] += r["mo_1s"] * k; tot["mo60"] += r["mo_60s"] * k
                if tot["fills"] == 0: continue
                k = tot["fills"]; g = tot["pnl"] / tot["ntl"] * 1e4
                rows.append(dict(coin=c, d_bp=dd, lat="500ms" if Lg == 5 else "1s", fill="tocco" if touch else "oltre", spread_bp=np.mean(spr), fills_ora=k / (tot["cells"] / 36000), capt=tot["capt"] / k, mo1s=tot["mo1"] / k, mo60s=tot["mo60"] / k, lordo_bp=g, netto_1_5=g - 1.5))
M = pd.DataFrame(rows); M.to_csv("07_live_mm.csv", index=False)
print(M[M.coin.isin(["BTC", "ETH", "SOL"])].round(2).to_string(index=False))
A = M[~M.coin.isin(["BTC", "ETH", "SOL"])]
if len(A):
    print("\n20 perps meno liquidi (quota al miglior bid/ask, latenza 500 ms):")
    print(A[(A.d_bp == 0) & (A.lat == "500ms")].pivot(index="coin", columns="fill", values=["spread_bp", "fills_ora", "capt", "mo60s", "netto_1_5"]).round(2).to_string())
    for fill in ("oltre", "tocco"):
        for dd in (0.0, 2.0, 5.0):
            x = A[(A.fill == fill) & (A.d_bp == dd) & (A.lat == "500ms")]
            w = x.fills_ora / x.fills_ora.sum()
            print(f"  alt, fill {fill}, d={dd}: media semplice netto {x.netto_1_5.mean():+.2f} bp/$, pesata per fill {(x.netto_1_5*w).sum():+.2f}, monete positive {(x.netto_1_5>0).sum()}/{len(x)}, fill/ora totali {x.fills_ora.sum():.0f}")

print("\n=== E) LIQUIDAZIONI Binance (forceOrder) durante la registrazione")
for s in SEGS:
    meta = json.load(open(f"{DC}/v6_livegrid_{s}_meta.json")); lq = meta["liq"]
    print(s, "eventi:", len(lq), "nozionale totale $:", round(sum(float(x[5]) * float(x[6]) for x in lq)), "massimo $:", round(max([float(x[5]) * float(x[6]) for x in lq] or [0])))
