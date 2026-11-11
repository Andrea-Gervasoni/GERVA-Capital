"""Test 3a (storico): spot -> perp e perp -> spot su Binance, griglia 100 ms, tutti i giorni campione.
(i) correlazione tra rendimento a 1 s di A in [t-l-1s, t-l] e rendimento a 1 s di B in [t, t+1s]
(ii) evento: A si muove >= soglia (top 0.1% dei rendimenti a 1 s, soglia dalla selezione) -> rendimento di B da t+L a t+L+5s."""
import numpy as np, pandas as pd
from lib import *
LAG = {"0ms": 0, "100ms": 1, "200ms": 2, "500ms": 5, "1s": 10, "2s": 20, "5s": 50}
for sym in ("BTCUSDT", "ETHUSDT"):
    acc = {}; ev = []
    for d, f in day_files(sym):
        df = pd.read_parquet(f)
        if "s_tlast" not in df.columns: continue
        P = ffill(df["tlast"]); S = ffill(df["s_tlast"])
        if "bid" in df.columns: P = (ffill(df["bid"]) + ffill(df["ask"])) / 2
        t = np.arange(3000, N - 200, 10)
        per = "sel" if d < "2023" else "ver"
        rP = (P[t] / P[t - 10] - 1) * 1e4; rS = (S[t] / S[t - 10] - 1) * 1e4
        ok = ~np.isnan(rP) & ~np.isnan(rS)
        for lk, l in LAG.items():
            fP = (P[t + l + 10] / P[t + l] - 1) * 1e4; fS = (S[t + l + 10] / S[t + l] - 1) * 1e4
            acc.setdefault((per, "spot->perp", lk), []).append(np.corrcoef(rS[ok], fP[ok])[0, 1])
            acc.setdefault((per, "perp->spot", lk), []).append(np.corrcoef(rP[ok], fS[ok])[0, 1])
            acc.setdefault((per, "perp->perp", lk), []).append(np.corrcoef(rP[ok], fP[ok])[0, 1])
        for nm, lead, lagp in (("spot->perp", S, P), ("perp->spot", P, S)):
            r = (lead[t] / lead[t - 10] - 1) * 1e4; own = (lagp[t] / lagp[t - 10] - 1) * 1e4
            for lk, l in (("200ms", 2), ("500ms", 5), ("1s", 10)):
                fut = (lagp[t + l + 50] / lagp[t + l] - 1) * 1e4
                ev.append(pd.DataFrame(dict(per=per, day=d, pair=nm, L=lk, r=r, own=own, fut=fut)).dropna().query("abs(r) > 1.0"))
    print(f"\n=== {sym}: correlazione rendimento 1s del leader (ritardato di l) con rendimento 1s successivo del follower (media tra giorni)")
    C = pd.Series({k: np.mean(v) for k, v in acc.items()}).unstack(2)[list(LAG)]
    print(C.round(4).to_string())
    E = pd.concat(ev, ignore_index=True)
    for nm in ("spot->perp", "perp->spot"):
        thr = E[(E.pair == nm) & (E.per == "sel")]["r"].abs().quantile(0.99) if (E.per == "sel").any() else 5.0
        x = E[(E.pair == nm) & (E.r.abs() >= thr)]
        x = x.assign(g=np.sign(x.r) * x.fut, gap=np.sign(x.r) * (x.r - x.own))
        print(f"{nm}: evento |rend 1s del leader| >= {thr:.1f} bp (soglia da selezione). Rendimento del follower nei 5 s dopo la latenza L, firmato (bp):")
        print(x.groupby(["per", "L"]).agg(n=("g", "size"), mossa_leader=("r", lambda s: s.abs().mean()), follower_gia_mosso=("own", lambda s: (np.sign(x.loc[s.index, "r"]) * s).mean()), edge_lordo=("g", "mean")).round(2).to_string())
