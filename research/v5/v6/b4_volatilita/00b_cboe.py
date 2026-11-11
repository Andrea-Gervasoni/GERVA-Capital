"""B4 - dati CBOE: futures VIX per contratto (OHLC + settle) e indici strategia."""
import sys, io, re, time, concurrent.futures as cf
sys.path.insert(0, "/home/user/GERVA-Capital")
import pandas as pd, numpy as np
from gerva.data.sources import Store, _get
st = Store("/home/user/GERVA-Capital/data_cache")

def fut():
    html = _get("https://www.cboe.com/us/futures/market_statistics/historical_data/product/list/VX/").decode()
    exps = sorted(set(re.findall(r"VX/VX_(\d{4}-\d{2}-\d{2})\.csv", html)))
    def new(e):
        raw = _get(f"https://cdn.cboe.com/data/us/futures/market_statistics/historical_data/VX/VX_{e}.csv", allow_404=True)
        if raw is None: return None
        d = pd.read_csv(io.BytesIO(raw)); d["expiry"] = pd.Timestamp(e); return d
    MC = "FGHJKMNQUVXZ"
    def old(my):
        m, y = my
        try: raw = _get(f"https://cdn.cboe.com/resources/futures/archive/volume-and-price/CFE_{MC[m-1]}{y%100:02d}_VX.csv", allow_404=True, tries=2)
        except Exception: return None      # 403 = contratto inesistente
        if raw is None: return None
        txt = raw.decode(errors="ignore"); i = txt.find("Trade Date")
        d = pd.read_csv(io.StringIO(txt[i:]), usecols=range(11), on_bad_lines="skip", engine="python"); d["expiry"] = pd.NaT; d["ym"] = f"{y}-{m:02d}"; return d
    with cf.ThreadPoolExecutor(8) as ex:
        A = [x for x in ex.map(new, exps) if x is not None]
        B = [x for x in ex.map(old, [(m, y) for y in range(2004, 2014) for m in range(1, 13)]) if x is not None]
    a = pd.concat(A); b = pd.concat(B)
    for d in (a, b):
        d["Trade Date"] = pd.to_datetime(d["Trade Date"], errors="coerce", format="mixed")
    a["ym"] = a.expiry.dt.strftime("%Y-%m")
    a["monthly"] = ~a["Futures"].str.match(r"^VX\d")      # i settimanali si chiamano "VX06 ..."
    b["monthly"] = True
    d = pd.concat([a, b]).dropna(subset=["Trade Date"])
    d.columns = [c.strip().lower().replace(" ", "_") for c in d.columns]
    return d[["trade_date","futures","open","high","low","close","settle","total_volume","open_interest","expiry","ym","monthly"]].reset_index(drop=True)
d = st.cached("v6b4_cfe_vx_raw", fut, "cboe")
print(d.shape, d.trade_date.min(), d.trade_date.max(), d.monthly.mean()); print(d.groupby(d.trade_date.dt.year).ym.nunique())

for s in ["BXM","BXMD","PUT","PPUT","CLL","WPUT","BFLY","CNDR","VPD","VPN","SVRO","BXMW","CMBO","PUTY","BXY","VXTH","LOVOL","VSTG","SPRO","PPUT3M","VIX","VIX1D","SPVXSP","SPVXSTR"]:
    def f():
        raw = _get(f"https://cdn-api.cboe.com/api/global/us_indices/daily_prices/{s}_History.csv", tries=2).decode()
        x = pd.read_csv(io.StringIO(raw)); x.columns = [c.strip().lower() for c in x.columns]
        x["date"] = pd.to_datetime(x["date"], format="mixed"); x = x.set_index("date").sort_index()
        return x[~x.index.duplicated()].astype(float)
    try:
        x = st.cached("v6b4_cboe_" + s, f, "cboe"); print(f"{s:8s} {x.index[0].date()} {x.index[-1].date()} n={len(x)} cols={list(x.columns)}")
    except Exception as e: print(f"{s:8s} ERR {str(e)[:80]}")
