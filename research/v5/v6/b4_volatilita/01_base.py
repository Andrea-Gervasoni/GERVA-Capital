"""B4 - base: pannello futures VIX, indici a scadenza costante ricostruiti (ST = mesi 1-2, MT = mesi 4-7,
metodologia S&P VIX Futures Indices), controllo contro ^SHORTVOL / VIXY / SVXY / UVXY / VIXM reali. Tutto SIMULATO."""
import sys, pickle, warnings; warnings.filterwarnings('ignore')
sys.path.insert(0, "/home/user/GERVA-Capital")
import pandas as pd, numpy as np
from gerva.data.sources import Store
st = Store("/home/user/GERVA-Capital/data_cache")
raw = st.get("v6b4_cfe_vx_raw").copy()
def std_exp(ym):
    """scadenza mensile standard: mercoledi' 30 giorni prima del terzo venerdi' del mese successivo."""
    nx = pd.Timestamp(ym + "-01") + pd.offsets.MonthBegin(1)
    fri3 = nx + pd.offsets.WeekOfMonth(week=2, weekday=4) if nx.weekday() != 4 or True else nx
    fri3 = [d for d in pd.date_range(nx, periods=31) if d.weekday() == 4][2]
    return fri3 - pd.Timedelta(days=30)
se = {ym: std_exp(ym) for ym in raw.ym.unique()}
isnew = raw.expiry.notna()
raw = raw[~isnew | ((raw.expiry - raw.ym.map(se)).abs() <= pd.Timedelta(days=2))].copy()   # via i settimanali (stesso nome, altra scadenza)
for c in ["open","high","low","close","settle"]: raw[c] = pd.to_numeric(raw[c], errors="coerce")
old = raw.trade_date < "2007-03-26"                      # prima del 26/3/2007 il contratto era quotato x10
raw.loc[old, ["open","high","low","close","settle"]] /= 10.0
raw = raw[raw.settle > 0]
# scadenza: file nuovi = data nel nome; archivio = ultima data del file
exp_old = raw[raw.expiry.isna()].groupby("ym").trade_date.max()
raw["expiry"] = raw.expiry.fillna(raw.ym.map(exp_old))
raw["src_new"] = raw.futures.str.contains(r"\(\w{3} \d{4}\)")
raw = raw.sort_values(["trade_date","ym","src_new"]).drop_duplicates(["trade_date","ym"], keep="last")
exp = raw.groupby("ym").expiry.max().sort_values()
raw = raw[raw.trade_date <= raw.ym.map(exp)]
S = raw.pivot(index="trade_date", columns="ym", values="settle").sort_index()
H = raw.pivot(index="trade_date", columns="ym", values="high").reindex_like(S)
L = raw.pivot(index="trade_date", columns="ym", values="low").reindex_like(S)
O = raw.pivot(index="trade_date", columns="ym", values="open").reindex_like(S)
H = H.where(H > 0).combine_first(S); H = np.maximum(H, S); L = L.where(L > 0).combine_first(S); L = np.minimum(L, S)
days = S.index; yms = list(exp.index); E = exp.values
# periodo di roll: dal giorno di borsa prima della scadenza E0 a quello prima di E1
pos = {d: i for i, d in enumerate(days)}
T = []                                                   # ultimo giorno di contrattazione "pieno" prima di ogni scadenza
for e in exp:
    prev = days[days < e]
    T.append(prev[-1] if len(prev) else pd.NaT)
T = pd.DatetimeIndex(T)
def weights(first, n_mid):
    """first = quale mese (1 = prossimo a scadere dopo il periodo corrente) entra con peso calante; n_mid mesi pieni in mezzo."""
    W = pd.DataFrame(0.0, index=days, columns=S.columns)
    for j in range(len(yms) - first - n_mid - 1):
        t0, t1 = T[j], T[j + 1]
        if pd.isna(t0) or pd.isna(t1): continue
        seg = days[(days >= t0) & (days < t1)]; dt = len(seg)
        if dt == 0: continue
        k = np.arange(dt) / dt; tot = 1.0 + n_mid
        W.loc[seg, yms[j + first]] = (1 - k) / tot
        for m in range(n_mid): W.loc[seg, yms[j + first + 1 + m]] = 1.0 / tot
        W.loc[seg, yms[j + first + 1 + n_mid]] = k / tot
    return W
def index_ret(W):
    Wl = W.shift(1); P0 = S.shift(1)
    ok = ((Wl > 0) & (S.isna() | P0.isna())).sum(axis=1) == 0
    den = (Wl * P0).sum(axis=1)
    r = ((Wl * (S - P0)).sum(axis=1) / den).where(ok & (den > 0))
    rh = ((Wl * (H - P0)).sum(axis=1) / den).where(ok & (den > 0))     # massimo del giorno (peggiore per chi e' corto)
    rl = ((Wl * (L - P0)).sum(axis=1) / den).where(ok & (den > 0))
    lvl = (W * S).sum(axis=1).where((W > 0).sum(axis=1) > 0)
    return r, rh, rl, lvl
Wst = weights(1, 0); Wmt = weights(4, 2)
rst, rsth, rstl, lst = index_ret(Wst); rmt, rmth, rmtl, lmt = index_ret(Wmt)
# primo e secondo contratto (non a scadenza costante) per coperture con opzioni
f1 = pd.DataFrame(index=days, columns=["ym","F","dte","F2"], dtype=object)
for d in days:
    j = np.searchsorted(E, np.datetime64(d), side="right")              # prima scadenza > d
    if j + 1 < len(yms):
        f1.loc[d] = [yms[j], S.at[d, yms[j]], (exp.iloc[j] - d).days, S.at[d, yms[j + 1]]]
y = lambda s: st.get("v6b4_y_" + s.replace("^", "i"))
ix = pd.DataFrame({"VIX": y("^VIX").close, "VIX3M": y("^VIX3M").close, "VIX9D": y("^VIX9D").close, "VIX6M": y("^VIX6M").close,
                   "VVIX": y("^VVIX").close, "SKEW": y("^SKEW").close, "SPX": y("^GSPC").close, "SPXTR": y("^SP500TR").close,
                   "VIXhi": y("^VIX").high, "IRX": y("^IRX").close, "SHORTVOL": y("^SHORTVOL").close, "PUTy": y("^PUT").close,
                   "SPXo": y("^GSPC").open, "SPXh": y("^GSPC").high, "SPXl": y("^GSPC").low})
etn = pd.DataFrame({s: y(s).adj for s in ["VIXY","SVXY","UVXY","VIXM","VXX","VXZ","SPY"]})
base = dict(S=S, H=H, L=L, O=O, exp=exp, Wst=Wst, Wmt=Wmt, f1=f1, ix=ix, etn=etn,
            fut=pd.DataFrame({"st": rst, "st_hi": rsth, "st_lo": rstl, "st_lvl": lst, "mt": rmt, "mt_hi": rmth, "mt_lo": rmtl, "mt_lvl": lmt}))
pickle.dump(base, open("base.pkl", "wb"))
F = base["fut"]
print("ST valido dal", F.st.first_valid_index().date(), "al", F.st.last_valid_index().date(), " buchi:", int(F.st.loc[F.st.first_valid_index():].isna().sum()))
print("MT valido dal", F.mt.first_valid_index().date(), " buchi:", int(F.mt.loc[F.mt.first_valid_index():].isna().sum()))
ann = lambda r: (1 + r.dropna()).prod() ** (252 / r.dropna().size) - 1
print(f"ST lungo: CAGR {ann(F.st):+.1%}  MT lungo: CAGR {ann(F.mt.loc['2006':]):+.1%}  (roll yield negativo = premio pagato da chi compra)")
# --- controlli contro serie reali
sv = ix.SHORTVOL.pct_change()   # NB: ^SHORTVOL di Yahoo non e' l'indice inverso di XIV (non mostra il -96%): non usato
print("scadenze fuori standard (archivio):", [(k, v.date(), se[k].date()) for k, v in exp.items() if abs((v - se[k]).days) > 2][:12])
for d in ["2018-02-02","2018-02-05","2018-02-06","2015-08-21","2015-08-24","2020-03-12","2020-03-16","2024-08-05"]:
    d = pd.Timestamp(d)
    print(f"  {d.date()} ST {F.st[d]:+7.1%} (max {F.st_hi[d]:+7.1%})  ^SHORTVOL {sv.get(d, np.nan):+7.1%}  SVXY {etn.SVXY.pct_change().get(d, np.nan):+7.1%}  VIXY {etn.VIXY.pct_change().get(d, np.nan):+7.1%}  UVXY {etn.UVXY.pct_change().get(d, np.nan):+7.1%}  VIX {ix.VIX.pct_change()[d]:+7.1%}")
for a, b, k in [("VIXY", F.st, 1), ("VIXM", F.mt, 1), ("VXX", F.st, 1)]:
    c = pd.concat([etn[a].pct_change(), k * b], axis=1, keys=["etn", "mio"]).dropna()
    print(f"{a} vs ricostruito: corr {c.corr().iloc[0,1]:.3f}  CAGR etn {ann(c.etn):+.1%}  mio {ann(c.mio):+.1%}  (differenza = commissioni ETN + chiusura 16:00 contro settle 16:15)")
