"""B6 - scarica i future continui Yahoo (front-month NON rettificati), indici, ETF di controllo e tassi FRED.
Chiavi cache: v5_b6_*"""
import sys, time
sys.path.insert(0, "/home/user/GERVA-Capital")
import pandas as pd
from gerva.data.sources import Store, yahoo, fred, DataError
st = Store("/home/user/GERVA-Capital/data_cache")
FUT = ["ES=F","NQ=F","YM=F","RTY=F","GC=F","SI=F","HG=F","PL=F","PA=F","CL=F","BZ=F","NG=F","HO=F","RB=F",
       "ZC=F","ZW=F","ZS=F","ZL=F","ZM=F","KC=F","SB=F","CC=F","CT=F","LE=F","HE=F","ZB=F","ZN=F","ZF=F","ZT=F",
       "6E=F","6J=F","6B=F","6A=F","6C=F","6S=F","DX=F","BTC=F","ETH=F"]
IDX = ["^N225","^GDAXI","^STOXX50E","^GSPC","^NDX","^DJI","^RUT","^FTSE"]
ETF = ["SPY","QQQ","DIA","IWM","GLD","SLV","IEF","TLT","SHY","IEI","FXE","FXY","FXB","FXA","FXC","FXF","USO","UNG","DBA","DBC","CPER","BIL","EWJ","EWG","FEZ","CORN","WEAT","SOYB","BTC-USD","ETH-USD",
       "EURUSD=X","JPY=X","GBPUSD=X","AUDUSD=X","CAD=X","CHF=X"]
for s in FUT+IDX+ETF:
    k = f"v5_b6_yahoo_1d_{s}"
    for a in range(3):
        try:
            d = st.cached(k, lambda: yahoo(s), "yahoo")
            print(f"{s:10s} {d.index[0].date()} {d.index[-1].date()} n={len(d)} vol0={int((d.volume==0).sum())}")
            break
        except Exception as e:
            print(s, "ERR", repr(e)[:100]); time.sleep(2)
for f in ["DTB3","DGS2","DGS5","DGS10","DGS30","DEXUSEU"]:
    try:
        d = st.cached(f"v5_b6_fred_{f}", lambda: fred(f).to_frame(f), "fred")
        print(f, d.index[0].date(), d.index[-1].date(), len(d))
    except Exception as e:
        print(f, "ERR", repr(e)[:100])
