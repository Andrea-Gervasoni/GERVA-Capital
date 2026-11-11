"""B3 - scarico dati (Yahoo giornaliero, FRED). Chiavi cache con prefisso v6_b3_ / riuso yahoo_1d_*."""
import sys, warnings
sys.path.insert(0, "/home/user/GERVA-Capital")
warnings.filterwarnings("ignore")
import pandas as pd, numpy as np
from gerva.data.sources import Store, yahoo, fred, DataError
st = Store("/home/user/GERVA-Capital/data_cache")
SYMS = ["^NDX","^GSPC","^IXIC","QQQ","SPY","TQQQ","UPRO","SSO","QLD","SPXL","TLT","TMF","UBT","IEF","GLD","UGL","GC=F","^IRX","^GDAXI","^VIX","SHY","BIL",
        "QQQ3.MI","QQQ3.L","3USL.L","3USL.MI","LQQ.PA","CL2.PA","DBPG.DE","XS2L.DE","5QQQ.L","QQQ5.L","5SPY.L","SPY5.L","3DEL.L","3DEL.MI","LQQ3.L","3LUS.L","XS2D.L","18MF.DE","LVE.PA","DAXLEV.PA","L8I7.DE","QQQ3.DE","3QQQ.L","5QQE.L","QQQ5.MI","3TYL.MI","3GOL.MI","3GOL.L","3TYL.L","EQQQ.L","EQQQ.MI","CSSPX.MI","SXR8.DE","EURUSD=X","GBPUSD=X","VUSTX","VFINX","VBMFX","VWESX","RYOCX"]
for s in SYMS:
    key = f"v6_b3_y_{s}"
    try:
        df = st.cached(key, lambda: yahoo(s), "yahoo", refresh=("--refresh" in sys.argv))
        print(f"{s:10s} {df.index[0].date()} -> {df.index[-1].date()} n={len(df)} last={df['close'].iloc[-1]:.2f}")
    except Exception as e:
        print(f"{s:10s} ERRORE {str(e)[:80]}")
for f in ["DTB3","DGS10","DGS30","DGS20","DFF","SOFR","ECBESTRVOLWGTTRMDMNRT","DGS5"]:
    try:
        s = st.cached(f"v6_b3_fred_{f}", lambda: fred(f).to_frame(), "fred")
        print(f"FRED {f:8s} {s.index[0].date()} -> {s.index[-1].date()} n={len(s)}")
    except Exception as e:
        print(f"FRED {f} ERRORE {str(e)[:80]}")
