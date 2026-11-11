"""B6 (3)-(6): carry (STIMA), IBS sugli indici, risk parity + trend, stagionalita' delle materie prime."""
from engine import *
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
B = Book(); R = B.R; idx = R.index
rows = []; SER = {}
def add(name, W, **kw):
    net, gross, Wf, info = B.run(W, **kw); rows.append(line(name, net, gross, info)); SER[name] = net; return net

# ---------------- trend di riferimento ----------------
S = {}
for k in (21, 63, 252): S[f"T{k}"] = B.sig_tsmom(k)
for f in (4, 8, 16, 32, 64): S[f"E{f}"] = B.sig_ewmac(f)
for n in (20, 55, 120, 250): S[f"D{n}"] = B.sig_donchian(n)
trend = (sum(S[n].fillna(0) / S[n].abs().mean().mean() for n in S) / len(S)).where(B.active)
slow = (sum(S[n].fillna(0) / S[n].abs().mean().mean() for n in ("T252", "E32", "E64", "D120", "D250")) / 5).where(B.active)
add("TREND_TUTTI", B.weights(trend)); add("TREND_LENTO(12m,E32,E64,D120,D250)", B.weights(slow))

# ---------------- (3) carry ----------------
gaps = pd.read_parquet(f"{CACHE}/v5_b6_rollgaps.parquet")["gap"]
carry = pd.DataFrame(np.nan, index=idx, columns=R.columns)
rf = fred("DTB3").reindex(pd.date_range("1999-01-01", idx[-1])).ffill().reindex(idx) / 100
def frate(n): return fred(n).reindex(pd.date_range("1999-01-01", idx[-1])).ffill().shift(45).reindex(idx) / 100   # dato mensile: noto con ritardo
for k in R.columns:
    if k in gaps.index.get_level_values(0):
        g = gaps.loc[k]; g = g[~g.index.duplicated()]
        s = pd.Series(0.0, index=idx); c = pd.Series(0.0, index=idx)
        gi = g.reindex(idx)
        tot = gi.fillna(0).rolling(252, min_periods=120).sum()       # somma dei salti dell'ultimo anno = - carry annuo
        carry[k] = -tot
FXR = {"6E=F": "IR3TIB01EZM156N", "6J=F": "IR3TIB01JPM156N", "6B=F": "IR3TIB01GBM156N", "6A=F": "IR3TIB01AUM156N", "6C=F": "IR3TIB01CAM156N", "6S=F": "IR3TIB01CHM156N"}
for k, f in FXR.items(): carry[k] = frate(f) - rf
for k in ("GC=F", "SI=F", "HG=F"): carry[k] = -rf
for k, e in [("ES_etf", "SPY"), ("NQ_etf", "QQQ"), ("YM_etf", "DIA"), ("RTY_etf", "IWM")]:
    d = raw(e); dy = ((d.adj / d.adj.shift(252)) / (d.close / d.close.shift(252)) - 1).reindex(idx).ffill()
    carry[k] = dy - rf
carry["^N225"] = 0.017 - frate("IR3TIB01JPM156N"); carry["^GDAXI"] = -frate("IR3TIB01EZM156N"); carry["^STOXX50E"] = 0.032 - frate("IR3TIB01EZM156N")
carry = carry.where(B.active)
cz = carry / B.vol
print("carry annuo medio stimato per mercato (%):"); print((carry.mean() * 100).round(1).to_dict())
add("CARRY_TS_segno", B.weights(np.sign(carry)))
add("CARRY_TS_proporzionale(carry/vol, limite 2)", B.weights((cz / cz.abs().stack().median()).clip(-2, 2)))
xs = cz.copy()
for sct in SECTORS:
    m = B.sec[B.sec == sct].index; xs[m] = cz[m].sub(cz[m].mean(axis=1), axis=0)
add("CARRY_XS_entro_settore", B.weights((xs / xs.abs().stack().median()).clip(-2, 2)))
nofin = [k for k in R.columns if B.sec[k] in ("ENERGY", "AG", "RATE", "CRYPTO")]
add("CARRY_TS_prop. solo mercati con salto di roll misurato", B.weights((cz[nofin] / cz.abs().stack().median()).clip(-2, 2).reindex(columns=R.columns)))

# ---------------- (4) IBS sugli indici azionari ----------------
EQ = list(B.sec[B.sec == "EQ"].index)
ibs = pd.DataFrame({k: ((B.P[k].close - B.P[k].low) / (B.P[k].high - B.P[k].low).replace(0, np.nan)).reindex(idx) for k in EQ})
rw_eq = pd.DataFrame(0.0, index=idx, columns=R.columns)
for k in EQ: rw_eq[k] = (B.active[k] / B.active[EQ].sum(axis=1).replace(0, np.nan)).fillna(0)
def ibsW(lo, hi=None):
    s = pd.DataFrame(0.0, index=idx, columns=R.columns)
    for k in EQ:
        s[k] = (ibs[k] < lo).astype(float) - ((ibs[k] > hi).astype(float) if hi else 0.0)
    return B.weights(s.where(B.active), rw=rw_eq)
for nm, lo, hi in [("IBS<0.2 lungo", 0.2, None), ("IBS<0.2 lungo / >0.8 corto", 0.2, 0.8), ("IBS<0.1 lungo", 0.1, None)]:
    add(f"{nm} [esec. stessa chiusura, IPOTESI ordine alle 15:50]", ibsW(lo, hi), lag=1)
    add(f"{nm} [esec. chiusura successiva]", ibsW(lo, hi), lag=2)
us = ["ES_etf", "NQ_etf", "YM_etf", "RTY_etf"]
s = pd.DataFrame(0.0, index=idx, columns=R.columns)
for k in us: s[k] = (ibs[k] < 0.2).astype(float)
rw_us = rw_eq.copy(); rw_us[[k for k in EQ if k not in us]] = 0; rw_us[us] = 0.25
add("IBS<0.2 lungo solo USA [stessa chiusura]", B.weights(s.where(B.active), rw=rw_us), lag=1)
add("IBS<0.2 lungo solo USA [stessa chiusura] costi x2", B.weights(s.where(B.active), rw=rw_us), lag=1, cmult=2)

# ---------------- (5) risk parity + trend ----------------
one = pd.DataFrame(1.0, index=idx, columns=R.columns).where(B.active)
add("RP solo lungo (pari rischio per settore)", B.weights(one))
add("RP con filtro di tendenza (lungo solo se trend>0)", B.weights(one.where(trend > 0, 0.0).where(B.active)))
add("RP + TREND 50/50", B.weights(one * 0.5 + trend / trend.abs().stack().mean() * 0.5))
nocr = one.copy(); nocr[["BTC=F", "ETH=F"]] = np.nan
add("RP solo lungo senza cripto", B.weights(nocr))

# ---------------- (6) stagionalita' delle materie prime ----------------
COM = [k for k in R.columns if B.sec[k] in ("METAL", "ENERGY", "AG")]
mret = (1 + R[COM].fillna(0)).groupby([idx.year, idx.month]).prod() - 1
mact = R[COM].notna().groupby([idx.year, idx.month]).sum() > 10
mret = mret.where(mact); mz = mret / mret.rolling(36, min_periods=12).std().shift(1)
mz.index = pd.PeriodIndex([f"{y}-{m:02d}" for y, m in mz.index], freq="M")
def seas(kyears, xsec=False):
    sig = pd.DataFrame(np.nan, index=mz.index, columns=COM)
    for i, p in enumerate(mz.index):
        prev = [q for q in mz.index[:i] if q.month == p.month][-kyears:]
        if len(prev) >= min(5, kyears): sig.loc[p] = mz.loc[prev].mean()
    if xsec: sig = sig.sub(sig.mean(axis=1), axis=0)
    d = sig.reindex(idx.to_period("M")); d.index = idx     # il segnale del mese e' noto alla fine del mese precedente
    return d
rw_c = pd.DataFrame(0.0, index=idx, columns=R.columns)
for k in COM: rw_c[k] = (B.active[k] / B.active[COM].sum(axis=1).replace(0, np.nan)).fillna(0)
for ky in (5, 10, 30):
    for xs_ in (False, True):
        sg = seas(ky, xs_)
        W = B.weights(np.sign(sg).reindex(columns=R.columns).where(B.active), rw=rw_c)
        add(f"STAGIONALITA' stesso mese ultimi {ky} anni {'XS' if xs_ else 'TS'}", W, lag=1)   # posizione nota da un mese: nessun ritardo necessario

T = pd.DataFrame(rows).set_index("strategia")
print("\n== Sharpe netto per periodo, vol obiettivo 10% =="); print(T.round(2).to_string())
print("varianti contate in questo file: %d" % len(T))
D = pd.DataFrame(SER)
keys = ["TREND_TUTTI", "CARRY_TS_proporzionale(carry/vol, limite 2)", "CARRY_XS_entro_settore", "IBS<0.2 lungo [esec. stessa chiusura, IPOTESI ordine alle 15:50]", "RP solo lungo (pari rischio per settore)", "STAGIONALITA' stesso mese ultimi 10 anni TS"]
c = D[keys].loc[:SEL_END].resample("ME").sum().corr(); c.index = c.columns = ["TREND", "CARRY_TS", "CARRY_XS", "IBS", "RP", "STAG"]
print("\n== Correlazione mensile tra famiglie (selezione) =="); print(c.round(2).to_string())
D.to_parquet("serie_altre.parquet")
