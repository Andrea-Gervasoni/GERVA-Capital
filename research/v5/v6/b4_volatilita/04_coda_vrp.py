"""B4 - Test 4 (copertura di coda finanziata dal carry) e Test 5 (VRP come filtro per EQ-MR e per la leva sull'indice)."""
from lab import *
d0 = "2006-10-24"; idx = F.index[F.index >= d0]
st, mt = F.st.reindex(idx), F.mt.reindex(idx)
spx, vix, v3, v9 = [IX[c].reindex(idx).ffill() for c in ("SPX", "VIX", "VIX3M", "VIX9D")]
lvl = F.st_lvl.reindex(idx); rf = RF.reindex(idx)
rv21 = np.log(IX.SPX).diff().rolling(21).std().mul(np.sqrt(252) * 100).reindex(idx)
bs = pickle.load(open("_best02.pkl", "rb"))["bs"].reindex(idx).fillna(0)       # filtro scelto nel test 1 (VIX < livello ST)
one = pd.Series(1.0, idx)
print("=== TEST 4: coda lunga finanziata dal carry ===")
print("(i) corto ST + lungo h x MT (la curva: si incassa il roll del tratto breve, si tiene convessita' sul tratto medio)\n" + HEAD)
R4 = {}
for nm, s in (("sempre", one), ("filtro VIX<ST", bs)):
    for h in (0.0, 0.5, 1.0, 2.0):
        r = apply(-s, st) + apply(h * s, mt); R4[(nm, h)] = r; count("T4 curva"); print(row(f"-ST + {h:.1f} MT | {nm}", r))
print("\n(ii) lungo volatilita' puro come assicurazione (costo del premio visto dal lato di chi lo paga)\n" + HEAD)
for nm, r in (("lungo ST sempre", apply(one, st)), ("lungo MT sempre", apply(one, mt)), ("lungo ST solo in backwardation (VIX>ST)", apply(1 - bs, st)),
              ("lungo ST se VIX/VIX3M>1", apply((vix / v3 > 1).astype(float), st))):
    R4[nm] = r; count("T4 lungo vol"); print(row(nm, r))
print("\n(iii) effetto sul fondo esistente (2018-04 -> 2026-10): fondo + x * gamba di volatilita' (rendimenti giornalieri di calendario)")
f = fund(); cal = lambda r: to_cal(r).reindex(f.index).fillna(0)
legs = {"lungo ST sempre": R4["lungo ST sempre"], "lungo MT sempre": R4["lungo MT sempre"], "lungo ST in backw.": R4["lungo ST solo in backwardation (VIX>ST)"],
        "corto ST filtro": R4[("filtro VIX<ST", 0.0)], "-ST+1MT filtro": R4[("filtro VIX<ST", 1.0)], "-ST+2MT sempre": R4[("sempre", 2.0)]}
sh365 = lambda r: r.mean() / r.std() * np.sqrt(365)
for fk in ("C1_mtm_limiti", "C3_mtm_limiti_debito_reale"):
    b = f[fk]; print(f"[{fk}] da solo: Sharpe {sh365(b):.2f} CAGR {(1+b).prod()**(365/len(b))-1:+.1%} DD {maxdd(b):+.1%}  mar20 {(1+b.loc['2020-02-24':'2020-03-18']).prod()-1:+.1%}  ago24 {(1+b.loc['2024-08-01':'2024-08-06']).prod()-1:+.1%}")
    for nm, r in legs.items():
        for x in (0.05, 0.15):
            c = b + x * cal(r); count("T4 sul fondo")
            print(f"   + {x:.2f} x {nm:22s} Sharpe {sh365(c):.2f} (scelta {sh365(c.loc[:SEL_END]):.2f} / verifica {sh365(c.loc[VER_START:]):.2f})  CAGR {(1+c).prod()**(365/len(c))-1:+.1%} DD {maxdd(c):+.1%}  corr gamba-fondo {np.corrcoef(cal(r), b)[0,1]:+.2f}")

print("\n=== TEST 5: VRP (implicita meno realizzata) come filtro ===")
vrp = vix - rv21
S5 = {"VRP>0": (vrp > 0), "VRP>mediana 252g": (vrp > vrp.rolling(252).median()), "VIX/VIX3M<1": (vix / v3 < 1), "VIX9D<VIX": (v9 < vix).where(v9.notna()), "VIX<20": vix < 20}
S5 = {k: v.astype(float) for k, v in S5.items()}
print(f"VRP medio {vrp.mean():.1f} punti di vol; positivo il {(vrp>0).mean():.0%} dei giorni")
print("\n(a) leva sull'indice (S&P 500 TR in eccesso sul T-bill; via future MES/ETF UCITS). Segnale alla chiusura d, eseguito alla chiusura d+1, 2 pb per cambio.\n" + HEAD)
ex = IX.SPXTR.reindex(idx).ffill().pct_change() - rf
print(row("indice 1x sempre", ex)); count("T5 leva indice")
vt = (10 / rv21).clip(upper=2.0); print(row("riferimento: vol-target 10% (max 2x)", apply(vt, ex, cost=0.0002, roll=0))); count("T5 leva indice")
R5 = {}
for k, s in S5.items():
    for lo, hi_ in ((0, 1), (0, 2), (1, 2)):
        r = apply(lo + (hi_ - lo) * s, ex, cost=0.0002, roll=0); R5[(k, lo, hi_)] = r; count("T5 leva indice"); print(row(f"{k}: leva {hi_} se vero, {lo} se falso", r))
r = apply((vrp / 4).clip(0, 2), ex, cost=0.0002, roll=0); count("T5 leva indice"); print(row("leva continua = VRP/4 limitata 0-2", r))
print("\n(b) filtro sulla gamba EQ-MR esistente (research/v5/series.parquet, 2018 -> 2026; rendimento della gamba, non pesato)")
s = pd.read_parquet("/home/user/GERVA-Capital/research/v5/series.parquet")["EQ-MR"]; e = s.reindex(idx).dropna(); e = e.loc["2018-01-02":]
print(HEAD); print(row("EQ-MR com'e'", e)); count("T5 EQ-MR")
for k, sg in S5.items():
    for lag in (0, 1):
        on = sg.shift(1 + lag).reindex(e.index).fillna(0)
        a, b_ = e[on == 1], e[on == 0]; count("T5 EQ-MR", 2)
        print(row(f"solo se {k} (lag{lag})", e * on), f"| media/g acceso {a.mean()*1e4:+.1f} pb (n={len(a)}) spento {b_.mean()*1e4:+.1f} pb (n={len(b_)})  t diff {(a.mean()-b_.mean())/np.sqrt(a.var()/len(a)+b_.var()/len(b_)):+.2f}")
        print(row(f"solo se NON {k} (lag{lag})", e * (1 - on)))
pd.DataFrame({"T4_curva_1MT_filtro": R4[("filtro VIX<ST", 1.0)], "T4_curva_2MT_sempre": R4[("sempre", 2.0)], "T4_lungoST_backw": R4["lungo ST solo in backwardation (VIX>ST)"],
              "T5_SPX_VRPpos_0_2": R5[("VRP>0", 0, 2)], "T5_SPX_ratio_0_1": R5[("VIX/VIX3M<1", 0, 1)]}).to_parquet("_r04.parquet")
save_trials("trials_04.json"); print("\nvarianti:", TRIALS)
