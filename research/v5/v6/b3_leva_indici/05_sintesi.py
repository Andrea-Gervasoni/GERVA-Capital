"""05 - Sintesi: per ogni regola di esposizione, curva crescita-leva (lambda), leva ottima sulla scelta e resa in verifica,
bootstrap a blocchi mensili di P(-50%) in 3 anni (base e mezzo vantaggio), correlazione con il fondo esistente, returns.parquet. SIMULATO."""
from lab import *
U = underlying(); cash = U["cash"]; dc = U["dc"]
LAG = 2; CAP = 5.0; CEXP = 0.0004     # costo per unita' di esposizione scambiata (10 pb sul capitale di un ETP 3x ~ 3,3 pb per unita')
LAM = np.arange(0.25, 5.01, 0.25)
def spread_of(E):  # spread di finanziamento per livello di esposizione: 1% fino a 3x, sale a 3,5% a 5x
    return np.where(E <= 3, 0.010, 0.010 + (E - 3) / 2 * 0.025)
def exposures(und):
    p = (1 + U[und].fillna(0)).cumprod().where(U[und].notna()); r = U[und]
    sma = p.rolling(200).mean(); v20 = r.rolling(20).std() * np.sqrt(252)
    dd = p / p.rolling(252, min_periods=60).max() - 1
    on = pd.Series(np.nan, index=p.index); on[dd < -0.20] = 0.0; on[dd > -0.10] = 1.0; on = on.ffill().fillna(1.0)
    E = pd.DataFrame({"BH": 1.0, "TREND200": (p > sma).astype(float), "VT20": 0.20 / v20, "VT20+TREND200": (0.20 / v20).where(p > sma, 0.0), "DD20": on}, index=p.index)
    E[sma.isna()] = np.nan
    return E.shift(LAG)
def run(e, und, lam, half=False, cap=CAP):
    """rendimento giornaliero netto con esposizione lam*e (tetto cap), ribilanciata ogni giorno come fa un ETP; banda 10% sulla variazione."""
    ee = (lam * e).clip(upper=cap).values.copy()
    # banda: aggiorno l'esposizione solo se cambia di oltre il 10% relativo (o va a zero / riparte)
    cur = 0.0; out = np.zeros(len(ee))
    for i, x in enumerate(ee):
        if np.isnan(x): out[i] = np.nan; continue
        if x == 0 or cur == 0 or abs(x - cur) > 0.10 * cur: cur = x
        out[i] = cur
    E = pd.Series(out, index=e.index)
    ru = U[und]; c = cash; d = dc
    prem = (ru - c).mean() / 2 if half else 0.0
    x = E * (ru - prem - c)
    fin = (E - 1).clip(lower=0) * spread_of(E.values) * d / 360 + 0.0075 * d / 365 * (E > 1) + 0.0007 * d / 365 * ((E > 0) & (E <= 1)) + 0.002 * d / 365 * (E < 1) * (1 - E)
    tc = E.diff().abs().fillna(0) * CEXP
    r = (c + x - fin - tc).clip(lower=-1)
    return r[E.notna()], E
def cg(r):
    r = r.dropna(); return np.exp(np.log1p(r.clip(lower=-0.999999)).mean() * 252) - 1
def boot(r, n=2000, months=36, seed=11):
    """bootstrap a blocchi di mesi di calendario: P(caduta <= -50% entro 3 anni), P(fine < inizio), mediana del mese composto."""
    rng = np.random.default_rng(seed); r = r.dropna()
    blocks = [g.values for _, g in r.groupby([r.index.year, r.index.month])]
    hit = 0; lose = 0; fin = []
    for _ in range(n):
        ii = rng.integers(0, len(blocks), months); path = np.concatenate([blocks[i] for i in ii])
        eq = np.cumprod(1 + path); pk = np.maximum.accumulate(np.maximum(eq, 1.0))
        hit += (eq / pk).min() <= 0.5; lose += eq[-1] < 1; fin.append(eq[-1])
    fin = np.array(fin)
    return hit / n, lose / n, np.median(fin) ** (1 / months) - 1, np.percentile(fin, 10) ** (1 / months) - 1
ntrial = 0; RET = {}; SUMM = []
for und in ["NDX", "SPX"]:
    EX = exposures(und)
    print(f"\n=================== {und}: curva crescita-leva per regola (lambda = moltiplicatore dell'esposizione, tetto {CAP:.0f}x) ===================")
    for name in EX.columns:
        e = EX[name]; ntrial += 1
        G = {}
        for lam in LAM:
            r, E = run(e, und, lam)
            G[lam] = dict(intero=cg(r), scelta=cg(r.loc[:SEL_END]), verifica=cg(r.loc[VER_START:]), pre08=cg(r.loc[:"2007"]), post08=cg(r.loc["2008":]), c0002=cg(r.loc["2000":"2002"]),
                          dd=stats(r, cash)["maxDD"], espo=float(E.mean()))
        G = pd.DataFrame(G).T
        ls, l07, lall, lver = G.scelta.idxmax(), G.pre08.idxmax(), G.intero.idxmax(), G.verifica.idxmax()
        r1, E1 = run(e, und, 1.0); s1 = stats(r1, cash)
        RET[f"{und}_{name}"] = r1
        print(f"\n--- {und} {name}: a lambda=1 esposizione media {E1.mean():.2f}, CAGR {s1['CAGR']*100:.1f}%, vol {s1['vol']*100:.1f}%, Sharpe {s1['Sharpe']:.2f}, maxDD {s1['maxDD']*100:.1f}%")
        print("  lambda  espo  CAGR: intero  scelta verifica   <=2007  >=2008  2000-02   maxDD")
        for lam in [0.5, 1, 1.5, 2, 2.5, 3, 4, 5]:
            x = G.loc[lam]; print(f"  {lam:5.2f} {x.espo:5.2f}       {x.intero*100:6.1f}% {x.scelta*100:6.1f}% {x.verifica*100:7.1f}% {x.pre08*100:7.1f}% {x.post08*100:6.1f}% {x.c0002*100:7.1f}% {x.dd*100:7.1f}%")
        print(f"  lambda ottimo: intero {lall}, scelta<=2022 {ls}, <=2007 {l07}, verifica>=2023 {lver}.  Scelto su <=2007 e applicato a >=2008: {G.loc[l07,'post08']*100:.1f}% (ottimo a posteriori {G.post08.max()*100:.1f}% a {G.post08.idxmax()}); "
              f"scelto su <=2022 e applicato a >=2023: {G.loc[ls,'verifica']*100:.1f}%")
        for lam, tag in [(ls, "lambda* (scelta)"), (ls / 2, "meta' di lambda*")]:
            lam = max(0.25, round(lam * 4) / 4)
            r, E = run(e, und, lam); s = split(r, cash)
            rh, _ = run(e, und, lam, half=True)
            b = boot(r); bh = boot(rh)
            m = lambda c_: ((1 + c_) ** (1 / 12) - 1) * 100
            print(f"  {tag:17s} = {lam:4.2f}: CAGR intero {s['intero']['CAGR']*100:5.1f}% (mese composto {m(s['intero']['CAGR']):.2f}%) | scelta {s['scelta']['CAGR']*100:5.1f}% | verifica {s['verifica']['CAGR']*100:5.1f}% | "
                  f"vol {s['intero']['vol']*100:.0f}% Sharpe {s['intero']['Sharpe']:.2f}/{s['scelta']['Sharpe']:.2f}/{s['verifica']['Sharpe']:.2f} | maxDD {s['intero']['maxDD']*100:.0f}% mese peggiore {s['intero']['mese_peggiore']*100:.0f}% sott'acqua {s['intero']['sott_acqua_max_anni']:.1f} anni")
            print(f"       bootstrap 3 anni BASE: P(-50%)={b[0]:.2f}  P(perdita a 3 anni)={b[1]:.2f}  mese composto mediano {b[2]*100:.2f}%  10° percentile {b[3]*100:.2f}%  ||  MEZZO VANTAGGIO: P(-50%)={bh[0]:.2f}  P(perdita)={bh[1]:.2f}  mese mediano {bh[2]*100:.2f}%  (CAGR {cg(rh)*100:.1f}%)")
            SUMM.append(dict(und=und, regola=name, tag=tag, lam=lam, cagr=s['intero']['CAGR'], sel=s['scelta']['CAGR'], ver=s['verifica']['CAGR'], dd=s['intero']['maxDD'], p50=b[0], p50h=bh[0]))
print(f"\nregole x indici provate qui: {ntrial} (ognuna su 20 livelli di lambda)")
pd.DataFrame(SUMM).to_csv("05_sintesi.csv", index=False)

# ---------- correlazione con il fondo esistente ----------
S3 = pd.read_parquet("_serie03.parquet"); S4 = pd.read_parquet("_serie04.parquet")
RET["HFEA+SMA200_NDX_55/45 (3x az. + 3x obb.10a)"] = S3["E_hfea+sma200|NDX|55/45/0"].dropna()
RET["IBS_QQQ_1x_VIX20_apertura"] = S4["IBS|QQQ|1x|<0.2|VIX>=20|apertura"].dropna()
RET["NDX_3x_costante (ETP)"] = S3["0_costante|NDX|3x"].dropna()
F = pd.read_parquet("/home/user/GERVA-Capital/research/v5/v5/a10_sistema/returns.parquet")[["B_cassa_in_tbill", "C1_mtm_limiti", "C3_mtm_limiti_debito_reale"]]
print("\n=== Correlazione con il fondo esistente (2018-04 -> 2026-10): giornaliera | mensile; e miscela 50/50 con B_cassa_in_tbill (Sharpe mensile annualizzato)")
Fm = (1 + F).groupby([F.index.year, F.index.month]).prod() - 1
fs = lambda m: m.mean() / m.std() * np.sqrt(12)
print(f"  fondo: Sharpe mensile B {fs(Fm.iloc[:,0]):.2f}, C1 {fs(Fm.iloc[:,1]):.2f}, C3 {fs(Fm.iloc[:,2]):.2f}; CAGR B {((1+F.iloc[:,0]).prod()**(365/len(F))-1)*100:.1f}%, C1 {((1+F.iloc[:,1]).prod()**(365/len(F))-1)*100:.1f}%, C3 {((1+F.iloc[:,2]).prod()**(365/len(F))-1)*100:.1f}%")
out = {}
for k, r in RET.items():
    rc = r.reindex(pd.date_range(r.index[0], r.index[-1], freq="D")).fillna(0.0); out[k] = rc
    j = pd.concat([rc.rename("x"), F], axis=1).dropna()
    jm = (1 + j).groupby([j.index.year, j.index.month]).prod() - 1
    cd = [j["x"].corr(j[c]) for c in F.columns]; cm = [jm["x"].corr(jm[c]) for c in F.columns]
    # miscela a pari volatilita' mensile
    a = jm["x"] / jm["x"].std(); b = jm["B_cassa_in_tbill"] / jm["B_cassa_in_tbill"].std(); mix = (a + b) / 2
    print(f"  {k:46s} giorn. {cd[0]:5.2f} {cd[1]:5.2f} {cd[2]:5.2f} | mens. {cm[0]:5.2f} {cm[1]:5.2f} {cm[2]:5.2f} | Sharpe mens. da sola {fs(jm['x']):.2f}, miscela pari rischio con B {fs(mix):.2f}")
pd.DataFrame(out).to_parquet("returns.parquet")
print("\nreturns.parquet scritto:", list(out.keys()))
