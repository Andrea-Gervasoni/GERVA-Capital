"""B4 - dati: Yahoo (indici di volatilita', ETN, indici strategia CBOE), CBOE (futures VIX per contratto)."""
import sys, io, json, time
sys.path.insert(0, "/home/user/GERVA-Capital")
import pandas as pd, numpy as np
from gerva.data.sources import yahoo, Store, _get, DataError
st = Store("/home/user/GERVA-Capital/data_cache")
SYMS = ["^VIX","^VIX3M","^VIX9D","^VIX6M","^VVIX","^SKEW","^GSPC","^SP500TR","SPY","VXX","VIXY","SVXY","UVXY","VIXM","VXZ","ZIV","XIV",
        "^PUT","^BXM","^BXMD","^VPD","^VPN","^SVRO","^PPUT","^CLL","^WPUT","^BFLY","^CNDR","^SPVXSTR","^SPVXSP","^SPVXMP","^VSTOXX","^STOXX50E","^IRX","^SHORTVOL","^VXX"]
for s in SYMS:
    k = "v6b4_y_" + s.replace("^", "i")
    try:
        d = st.cached(k, lambda: yahoo(s), "yahoo")
        print(f"{s:10s} {d.index[0].date()} {d.index[-1].date()} n={len(d)} last={d.close.iloc[-1]:.2f}")
    except Exception as e:
        print(f"{s:10s} ERR {str(e)[:90]}")
    time.sleep(0.3)
