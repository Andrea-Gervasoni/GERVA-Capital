"""03 - Griglia di strategie sistematiche su indici con leva incorporata (ETP 2x/3x/5x). SIMULATO.
Segnale alla chiusura USA di t, esecuzione alla chiusura di t+1 (lag 2) = prudente per chi compra l'ETP in Europa il giorno dopo.
Controlli: lag 1 (ordine in chiusura), lag 3 (un giorno in piu'), costi x2. Cassa = T-bill - 0,2% (ETF monetario)."""
from lab import *
import itertools, time
U = underlying()
cash = U["cash"]; dc = U["dc"]
PROD["5x_ETP"] = (5, 0.0075, 0.035)
R = pd.DataFrame(index=U.index)
COST = {}
for und in ["NDX", "SPX"]:
    R[f"{und}_1x"] = U[und] - 0.0007 / 252; COST[f"{und}_1x"] = 0.0003
    for nm, c in [("2x_ETF", 0.0005), ("3x_ETP", 0.0010), ("5x_ETP", 0.0025)]:
        k, ter, sp = PROD[nm]
        R[f"{und}_{k}x"] = lev(U[und], cash, dc, k, ter, sp).clip(lower=-1); COST[f"{und}_{k}x"] = c
# obbligazioni: 10 anni ~ IEF dal 2002-07; prima cassa + 0,5*(Treasury lunghi - cassa) (STIMA); lunghi = VUSTX
ief = y("IEF")["adj"].pct_change().reindex(U.index)
b10 = cash + 0.5 * (U["BOND"] - cash); b10.loc[ief.dropna().index] = ief.dropna()
R["B10_1x"] = b10; COST["B10_1x"] = 0.0003
R["B10_3x"] = lev(b10, cash, dc, 3, 0.0030, 0.005); COST["B10_3x"] = 0.0015      # WisdomTree 3TYL: 0,30%
R["BL_3x"] = lev(U["BOND"], cash, dc, 3, 0.0100, 0.010); COST["BL_3x"] = 0.0015  # tipo TMF: in UCITS non esiste (solo confronto)
R["GOLD_3x"] = 3 * U["GOLD"] + cash - 0.0099 * dc / 365; COST["GOLD_3x"] = 0.0015   # WisdomTree 3GOL: 0,99%, su future
R["GOLD_1x"] = U["GOLD"] + cash - 0.0012 * dc / 365; COST["GOLD_1x"] = 0.0003
CASH = cash - 0.002 * dc / 365
P = {u: (1 + U[u].fillna(0)).cumprod().where(U[u].notna()) for u in ["NDX", "SPX", "BOND", "GOLD"]}
P["B10"] = (1 + b10.fillna(0)).cumprod().where(b10.notna())
vol20 = {u: U[u].rolling(20).std() * np.sqrt(252) for u in ["NDX", "SPX"]}
vol60 = {u: U[u].ewm(span=60, min_periods=40).std() * np.sqrt(252) for u in ["NDX", "SPX"]}

V = {}   # nome -> (W, banda)
def add(name, W, band=0.0): V[name] = (W, band)
for und in ["NDX", "SPX"]:
    p = P[und]
    # A. filtro di tendenza
    for k, n, b in itertools.product([1, 2, 3, 5], [50, 100, 150, 200, 250], [0.0, 0.01]):
        sma = p.rolling(n).mean()
        if b == 0: on = (p > sma).astype(float)
        else:
            on = pd.Series(np.nan, index=p.index); on[p > sma * (1 + b)] = 1.0; on[p < sma * (1 - b)] = 0.0; on = on.ffill().fillna(0)
        on[sma.isna()] = np.nan
        add(f"A_trend|{und}|{k}x|sma{n}|b{int(b*100)}", pd.DataFrame({f"{und}_{k}x": on}))
    # B. dual momentum
    for k, look, fb in itertools.product([2, 3], [126, 252], ["cassa", "bond"]):
        ce = (1 + cash).cumprod()
        mom = p / p.shift(look) - 1; mc = ce / ce.shift(look) - 1; mb = P["B10"] / P["B10"].shift(look) - 1
        on = (mom > mc).astype(float); on[mom.isna()] = np.nan
        W = pd.DataFrame({f"{und}_{k}x": on})
        if fb == "bond": W["B10_3x"] = ((on == 0) & (mb > mc)).astype(float)
        add(f"B_dualmom|{und}|{k}x|{look}|{fb}", W)
    # C. volatilita' obiettivo (veicolo 3x o 5x + cassa)
    for kv, tgt, est in itertools.product([3, 5], [0.15, 0.20, 0.25, 0.30, 0.40, 0.50], ["20g", "ewma60"]):
        v = vol20[und] if est == "20g" else vol60[und]
        e = (tgt / v).clip(upper=kv)
        add(f"C_voltgt|{und}|{kv}x|{int(tgt*100)}|{est}", pd.DataFrame({f"{und}_{kv}x": e / kv}), band=0.05)
    for kv, tgt in itertools.product([3, 5], [0.20, 0.30, 0.40, 0.50]):
        e = (tgt / vol20[und]).clip(upper=kv); sma = p.rolling(200).mean(); e = e.where(p > sma, 0.0); e[sma.isna()] = np.nan
        add(f"C2_voltgt+sma200|{und}|{kv}x|{int(tgt*100)}", pd.DataFrame({f"{und}_{kv}x": e / kv}), band=0.05)
    # D. controllo della caduta (sull'indice): esco se l'indice e' sotto X dal massimo a 252 sedute, rientro quando recupera meta'
    for x in [0.10, 0.15, 0.20]:
        dd = p / p.rolling(252, min_periods=60).max() - 1
        on = pd.Series(np.nan, index=p.index); on[dd < -x] = 0.0; on[dd > -x / 2] = 1.0; on = on.ffill().fillna(1.0); on[dd.isna()] = np.nan
        add(f"D_ddidx|{und}|3x|{int(x*100)}", pd.DataFrame({f"{und}_3x": on}))
    # D2. stop sulla caduta della strategia stessa (3x): fuori se la quota 3x perde X dal massimo, rientro quando indice > media 200
    for x in [0.30, 0.40, 0.50]:
        r3 = R[f"{und}_3x"].fillna(0).values; pv = p.values; smav = p.rolling(200).mean().values
        on = np.ones(len(p)); eq = 1.0; pk = 1.0; state = 1
        for t in range(len(p)):
            if state == 1:
                eq *= 1 + r3[t]; pk = max(pk, eq)
                if eq / pk - 1 < -x: state = 0
            else:
                if pv[t] > smav[t]: state = 1; eq = 1.0; pk = 1.0
            on[t] = state
        on = pd.Series(on, index=p.index); on[p.isna() | p.rolling(200).mean().isna()] = np.nan
        add(f"D2_ddstrat|{und}|3x|{int(x*100)}", pd.DataFrame({f"{und}_3x": on}))
    # E. famiglia HFEA: 3x azioni + 3x obbligazioni 10 anni (+ 3x oro); banda di ribilanciamento 7,5 punti
    for we, wb, wg in [(.55, .45, 0), (.60, .40, 0), (.40, .60, 0), (.70, .30, 0), (.50, .25, .25), (.40, .30, .30), (.34, .33, .33)]:
        for tr in [False, True]:
            W = pd.DataFrame({f"{und}_3x": we, "B10_3x": wb}, index=p.index)
            if wg: W["GOLD_3x"] = wg; W[R["GOLD_3x"].isna()] = np.nan
            W[p.isna() | R["B10_3x"].isna()] = np.nan
            if tr:
                sma = p.rolling(200).mean(); W[f"{und}_3x"] = W[f"{und}_3x"].where(p > sma, 0.0); W[sma.isna()] = np.nan
            add(f"E_hfea{'+sma200' if tr else ''}|{und}|{int(we*100)}/{int(wb*100)}/{int(wg*100)}", W, band=0.075)
    W = pd.DataFrame({f"{und}_3x": .55, "BL_3x": .45}, index=p.index); W[p.isna() | R["BL_3x"].isna()] = np.nan
    add(f"E_hfea_lunghi(non UCITS)|{und}|55/45/0", W, band=0.075)
# riferimenti
for und in ["NDX", "SPX"]:
    for k in [1, 2, 3, 5]:
        on = pd.Series(1.0, index=U.index); on[U[und].isna()] = np.nan
        add(f"0_costante|{und}|{k}x", pd.DataFrame({f"{und}_{k}x": on}))
print(f"varianti: {len(V)} (di cui 8 riferimenti a leva costante)")

# controllo di troncamento: il peso deciso a t non cambia se ricalcolo i segnali con i dati tagliati a t (medie mobili e vol: verifico 3 date)
for dt in ["2008-10-10", "2020-03-20", "2024-08-05"]:
    for und in ["NDX"]:
        pc = P[und].loc[:dt]; s1 = float(pc.iloc[-1] > pc.rolling(200).mean().iloc[-1]); s2 = float(P[und].loc[dt] > P[und].rolling(200).mean().loc[dt])
        vt = (U[und].loc[:dt].rolling(20).std() * np.sqrt(252)).iloc[-1]; assert s1 == s2 and abs(vt - vol20[und].loc[dt]) < 1e-12
print("controllo di troncamento: superato (3 date)")

rows = []; series = {}
t0 = time.time()
for name, (W, band) in V.items():
    first = W.dropna(how="any").index[0]
    Wc = W.loc[first:]; Rc = R.loc[first:]
    r, turn = sim_weights(Rc, Wc.fillna(0), COST, lag=2, band=band, cash=CASH)
    r2, _ = sim_weights(Rc, Wc.fillna(0), {k: 2 * v for k, v in COST.items()}, lag=2, band=band, cash=CASH)
    r1, _ = sim_weights(Rc, Wc.fillna(0), COST, lag=1, band=band, cash=CASH)
    r3, _ = sim_weights(Rc, Wc.fillna(0), COST, lag=3, band=band, cash=CASH)
    series[name] = r
    row = dict(nome=name, dal=str(first.date()), giro=turn, esposizione=float(Wc.fillna(0).sum(axis=1).mean()))
    for per, a, b in [("int", None, None), ("sel", None, SEL_END), ("ver", VER_START, None), ("pre08", None, "2007-12-31"), ("post08", "2008-01-01", None), ("c0002", "2000-01-01", "2002-12-31")]:
        s = stats(r.loc[a:b], cash)
        for kk in ("CAGR", "vol", "Sharpe", "maxDD", "mese_peggiore", "sott_acqua_max_anni", "mese_mediano"):
            row[f"{per}_{kk}"] = s.get(kk, np.nan)
    row["int_CAGR_costi2"] = stats(r2, cash)["CAGR"]; row["int_CAGR_lag1"] = stats(r1, cash)["CAGR"]; row["int_CAGR_lag3"] = stats(r3, cash)["CAGR"]
    row["ver_CAGR_costi2"] = stats(r2.loc[VER_START:], cash)["CAGR"]
    rows.append(row)
T = pd.DataFrame(rows).set_index("nome"); T.to_csv("03_tabella.csv")
pd.DataFrame(series).to_parquet("_serie03.parquet")
print(f"tempo {time.time()-t0:.0f}s")
def show(df, title, n=12):
    print(f"\n{title}")
    print(f"{'variante':44s} {'dal':>10s} | {'CAGR int':>8s} {'maxDD':>7s} {'Sh':>5s} | {'sel':>7s} {'DDsel':>7s} | {'ver':>7s} {'DDver':>7s} | {'<=07':>7s} {'>=08':>7s} {'00-02':>7s} | {'c x2':>6s} {'lag1':>6s} {'lag3':>6s} {'mese-':>7s} {'s.a.':>5s}")
    for nm, x in df.head(n).iterrows():
        print(f"{nm:44s} {x['dal']:>10s} | {x.int_CAGR*100:7.1f}% {x.int_maxDD*100:6.1f}% {x.int_Sharpe:5.2f} | {x.sel_CAGR*100:6.1f}% {x.sel_maxDD*100:6.1f}% | {x.ver_CAGR*100:6.1f}% {x.ver_maxDD*100:6.1f}% | "
              f"{x.pre08_CAGR*100:6.1f}% {x.post08_CAGR*100:6.1f}% {x.c0002_CAGR*100:6.1f}% | {x.int_CAGR_costi2*100:5.1f}% {x.int_CAGR_lag1*100:5.1f}% {x.int_CAGR_lag3*100:5.1f}% {x.int_mese_peggiore*100:6.1f}% {x.int_sott_acqua_max_anni:5.1f}")
show(T[T.index.str.startswith("0_")], "RIFERIMENTI: leva costante (stessi costi)")
fam = T.index.str.split("|").str[0]
print("\nMIGLIORE PER FAMIGLIA, scelto sul CAGR di scelta (<=2022), solo storie che iniziano entro il 1990")
old = T[T["dal"] <= "1990-12-31"]
best = old.assign(fam=old.index.str.split("|").str[0]).sort_values("sel_CAGR", ascending=False).groupby("fam").head(1)
show(best, "", 30)
for cap in [0.35, 0.50, 0.65, 1.0]:
    ok = old[old.sel_maxDD >= -cap].sort_values("sel_CAGR", ascending=False)
    show(ok, f"SCELTA <=2022: CAGR di scelta massimo con caduta massima di scelta <= {int(cap*100)}%  (candidati {len(ok)})", 6)
print("\n\n===== SPLIT DURO: scelta <=2007, verifica 2008-> =====")
for cap in [0.35, 0.50, 0.65, 1.0]:
    ok = old[old.pre08_maxDD >= -cap].sort_values("pre08_CAGR", ascending=False)
    show(ok, f"SCELTA <=2007: CAGR <=2007 massimo con caduta massima <=2007 <= {int(cap*100)}%  (candidati {len(ok)})", 6)
# quanto e' affidabile la classifica: correlazione di rango fra CAGR di scelta e di verifica
from scipy.stats import spearmanr
print("\nCorrelazione di rango (Spearman) fra CAGR di scelta e CAGR di verifica:", round(spearmanr(old.sel_CAGR, old.ver_CAGR)[0], 2), "| fra <=2007 e >=2008:", round(spearmanr(old.pre08_CAGR, old.post08_CAGR)[0], 2))
print("Mediana per famiglia (CAGR intero / maxDD intero / CAGR verifica):")
g = T.assign(fam=fam).groupby("fam")[["int_CAGR", "int_maxDD", "sel_CAGR", "ver_CAGR", "pre08_CAGR", "post08_CAGR", "c0002_CAGR"]].median()
print((g * 100).round(1).to_string())
