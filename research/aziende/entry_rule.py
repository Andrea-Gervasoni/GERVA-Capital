import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
names = ["NVDA","AVGO","AMD","TSM","ASML","MSFT","GOOGL","AMZN","META","COHR","GLW","CIEN","CRDO","ALAB","MU","VRT","BE","GEV","NBIS"]
px = yf.download(names, start="2014-01-01", auto_adjust=True, progress=False, group_by="column")["Close"].ffill(limit=5)
sma = px.rolling(200, min_periods=200).mean()
months = px.resample("MS").first().index
H = 504          # orizzonte: 24 mesi di borsa dopo la data della rata
rows = []
for s in names:
    p, m = px[s], sma[s]
    for d in months:
        idx = p.index.searchsorted(d)
        if idx + H + 63 >= len(p) or np.isnan(m.iloc[idx]) or np.isnan(p.iloc[idx]):
            continue
        a_px = p.iloc[idx]                                   # A: compra alla data
        j = idx
        while j < idx + 63 and not (p.iloc[j] > m.iloc[j]):  # B: aspetta il prezzo sopra la media, al massimo 3 mesi
            j += 1
        b_px = p.iloc[j]
        end = p.iloc[idx + H]
        rows.append(dict(s=s, d=d, waited=j > idx, logA=np.log(end / a_px), logB=np.log(end / b_px)))
df = pd.DataFrame(rows)
df["diff"] = df.logB - df.logA
by_month = df.groupby("d")["diff"].mean()                 # una osservazione per mese (i titoli si muovono insieme)
rng = np.random.default_rng(0)
boot = [by_month.sample(len(by_month), replace=True, random_state=int(rng.integers(1e9))).mean() for _ in range(2000)]
print("rate simulate:", len(df), "| mesi:", len(by_month), "| rate in cui la regola B aspetta:", f"{df.waited.mean():.0%}")
print(f"B meno A, log-rendimento medio a 24 mesi: {df['diff'].mean():+.4f}; per mese: {by_month.mean():+.4f}")
print(f"intervallo 90% (bootstrap sui mesi): {np.percentile(boot,5):+.4f} .. {np.percentile(boot,95):+.4f}")
print(f"P(B meglio di A): {(np.array(boot)>0).mean():.2f}")
w = df[df.waited]
print(f"solo le rate in cui B aspetta ({len(w)}): differenza media {w['diff'].mean():+.4f}")
