"""Test 2: simulazione di market making su quote e trade REALI (Binance USDT-M BTC/ETH, bookTicker tick -> 100 ms).
Fill conservativo (trade strettamente oltre la quota), post-only, limiti di inventario, latenza.
Scelta della configurazione sui giorni 2023, verifica sui giorni 2024. Commissioni: maker Hyperliquid 1.5 bp (base),
0 bp (>= 500M$ in 14 giorni), -0.3 bp (rebate massimo)."""
import numpy as np, pandas as pd, itertools
from lib import *
from mm import *
INV = 5
def load(sym):
    out = []
    for d, f in day_files(sym):
        df = pd.read_parquet(f)
        if "bid" not in df.columns: continue
        bid, ask = ffill(df["bid"]), ffill(df["ask"]); mid = (bid + ask) / 2
        thi = np.where(np.isnan(df["thi"]), -np.inf, df["thi"]); tlo = np.where(np.isnan(df["tlo"]), np.inf, df["tlo"])
        bq, aq = ffill(df["bq"]), ffill(df["aq"])
        dep = pd.Series(bq + aq).rolling(3000, min_periods=1).mean().to_numpy() + 1e-9
        sig = pd.Series(df["ofi"].to_numpy(float)).rolling(50, min_periods=1).sum().to_numpy() / dep   # OFI 5s / profondita' media
        out.append((d, bid, ask, thi, tlo, np.nan_to_num(sig), mid))
    return out
cfgs = [dict(d=d, R=R, L=L, gate=g) for d in (0, 0.5, 1, 2, 3, 5, 10) for R in (10, 50) for L in (2, 10) for g in (0, 1)]
print("configurazioni provate:", len(cfgs), "x 2 simboli")
rows = []
for sym in ("BTCUSDT", "ETHUSDT"):
    days = load(sym)
    thr = np.quantile(np.abs(np.concatenate([x[5][::50] for x in days if x[0] < "2024"])), 0.7)
    for c in cfgs:
        for (d, bid, ask, thi, tlo, sig, mid) in days:
            skew = c["d"] / INV if c["d"] > 0 else 0.0
            r = mm_sim(bid, ask, thi, tlo, sig, float(c["d"]), c["R"], c["L"], INV, skew, thr if c["gate"] else 0.0, 3000)
            s = summarize(*r, mid); s.update(c); s["sym"] = sym; s["day"] = d; rows.append(s)
T = pd.DataFrame(rows).fillna(0.0); T.to_csv("03_mm_days.csv", index=False)
T["per"] = np.where(T["day"] < "2024", "sel2023", "ver2024")
def agg(g):
    ntl = g["ntl"].sum(); w = g["fills"] / max(g["fills"].sum(), 1)
    gross = g["pnl_gross_$"].sum() / max(ntl, 1e-9) * 1e4
    unit = g["ntl"] / g["fills"].clip(lower=1)                     # nozionale di 1 unita'
    o = dict(fills_day=g["fills"].mean(), capt=(g["capt_bp"] * w).sum(), mo1s=(g["mo_1s"] * w).sum(), mo10s=(g["mo_10s"] * w).sum(),
             mo60s=(g["mo_60s"] * w).sum(), mo300s=(g["mo_300s"] * w).sum(), gross_bp=gross)
    for nm, fee in (("net1.5", 1.5), ("net0", 0.0), ("netReb", -0.3)):
        daily = (g["pnl_gross_$"] - fee * 1e-4 * g["ntl"]) / (INV * unit.replace(0, np.nan))    # rendimento giornaliero sul capitale = inventario massimo (1x)
        o[nm + "_bp"] = gross - fee
        o[nm + "_day%"] = daily.mean() * 100
        o[nm + "_sharpe"] = daily.mean() / (daily.std(ddof=1) + 1e-12) * np.sqrt(365)
    return pd.Series(o)
A = T.groupby(["sym", "d", "R", "L", "gate", "per"]).apply(agg).unstack("per")
pd.set_option("display.width", 300); pd.set_option("display.max_rows", 500)
for sym in ("BTCUSDT", "ETHUSDT"):
    a = A.loc[sym]
    print(f"\n=== {sym}: tutte le configurazioni (bp per $ eseguito; capt = semispread incassato; mo = markout dopo il fill, include capt)")
    cols = [("fills_day", "ver2024"), ("capt", "ver2024"), ("mo1s", "ver2024"), ("mo10s", "ver2024"), ("mo60s", "ver2024"), ("mo300s", "ver2024"),
            ("gross_bp", "sel2023"), ("gross_bp", "ver2024"), ("net1.5_bp", "sel2023"), ("net1.5_bp", "ver2024"), ("net0_bp", "ver2024")]
    print(a[cols].round(2).to_string())
    for nm in ("net1.5", "net0", "netReb"):
        best = a[(nm + "_day%", "sel2023")].idxmax()
        b = a.loc[best]
        print(f"[{nm}] migliore in selezione: d,R,L,gate={best}: sel {b[(nm+'_bp','sel2023')]:.2f} bp/$ {b[(nm+'_day%','sel2023')]:.3f}%/g Sharpe {b[(nm+'_sharpe','sel2023')]:.1f}"
              f" | VERIFICA {b[(nm+'_bp','ver2024')]:.2f} bp/$ {b[(nm+'_day%','ver2024')]:.3f}%/g Sharpe {b[(nm+'_sharpe','ver2024')]:.1f} fills/g {b[('fills_day','ver2024')]:.0f}")
A.to_csv("03_mm_summary.csv")
