import json, math, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, yfinance as yf
U = {
 "ottica e connessioni": ["MRVL","LITE","COHR","GLW","CIEN","FN","AAOI","CRDO","ALAB"],
 "memoria e storage": ["MU","SNDK","WDC","STX"],
 "energia e rete": ["VRT","GEV","PWR","BE","CEG","VST","OKLO","SMR","CCJ","LEU"],
 "raffreddamento": ["MOD","NVT"],
 "data center e neocloud": ["IREN","CRWV","NBIS","APLD","CIFR","WULF","CORZ"],
 "macchine per chip": ["AMAT","LRCX","KLAC","ONTO","CAMT"],
 "partecipate Nvidia": ["INTC","NOK"],
}
tk = sorted({t for v in U.values() for t in v})
px = yf.download(tk + ["SPY"], start="2021-01-01", auto_adjust=True, progress=False, group_by="column")["Close"]
rows = []
for g, names in U.items():
    for t in names:
        s = px[t].dropna() if t in px else pd.Series(dtype=float)
        if len(s) < 60:
            rows.append(dict(gruppo=g, ticker=t, dati="assenti")); continue
        r = s.pct_change().dropna()
        def ret(days):
            return float(s.iloc[-1] / s.iloc[-min(days, len(s)-1)-1] - 1) if len(s) > days else None
        mc = None
        try:
            mc = yf.Ticker(t).fast_info.get("market_cap")
        except Exception:
            pass
        rows.append(dict(gruppo=g, ticker=t, prezzo=float(s.iloc[-1]), cap_mld=(mc/1e9 if mc else None),
                         r6m=ret(126), r1a=ret(252), r3a=ret(756), dal_massimo=float(s.iloc[-1]/s.max()-1),
                         vol=float(r.tail(252).std()*math.sqrt(252)), caduta_max=float((s/s.cummax()-1).min()),
                         anni=round(len(s)/252,1)))
df = pd.DataFrame(rows)
df.to_csv("screen.csv", index=False)
pd.set_option("display.width", 220)
print(df.round(3).to_string())
