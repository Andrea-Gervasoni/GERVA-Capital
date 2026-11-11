"""B4 - sintesi: candidati, leva di crescita massima, bootstrap a blocchi mensili, correlazione col fondo, effetto sul fondo, returns.parquet."""
from lab import *
r2, r3, r4 = (pd.read_parquet(f"_r0{i}.parquet") for i in (2, 3, 4))
st = F.st.loc["2006-01-03":]; bs = pickle.load(open("_best02.pkl", "rb"))["bs"]
K = {"K1 corto fut VIX se VIX<ST (1x noz.)": r2.T1_best,
     "K1s idem, un giorno di ritardo (stress)": apply(-bs, st, lag=2),
     "K1c idem, costi x2": apply(-bs, st, cost=2 * C_FUT, roll=2 * ROLL_D),
     "K0 corto fut VIX sempre (1x noz.)": r2.T1_sempre,
     "K2 VPD (indice CBOE) se SPX>MM200": r3["T3_VPD_SPX>MM200"] if "T3_VPD_SPX>MM200" in r3 else r3.filter(like="VPD").iloc[:, 0],
     "K2b VPD sempre": r3.T3_VPD_sempre,
     "K3 PUT (indice CBOE) sempre": r3.T3_PUT_sempre,
     "K4 put-spread 3% OTM largo 5% (STIMA)": r3.T3b_spread3_5,
     "K5 fut+call 1,3 filtro (STIMA)": r2.T2c_call13_filtro,
     "SPX in eccesso (riferimento)": r3.SPX_ecc}
print("colonne disponibili r3:", list(r3.columns))
print("\n" + HEAD)
for k, r in K.items(): print(row(k, r), f" t={tstat(r):.1f}")
print("\n=== leva di crescita massima (sul campione intero, rendimenti giornalieri), rendimento mensile composto, P(drawdown>=50% in 3 anni) ===")
print(f"{'':42s} {'L*':>5s} {'mese@L*':>8s} {'mese@L*/2':>9s} | P(-50%) base L*  L*/2 | meta vantaggio: mese mediano@L*/2  P(-50%) L*  L*/2 | corr col fondo giorn./mens. (B, C1, C3)")
OUT = {}
for k, r in K.items():
    r = r.dropna(); L, mL, mH = kelly(r)
    if L == 0: print(f"{k:42s}  nessuna leva positiva: crescita massima a leva zero"); continue
    pb, _ = boot_p50(r, L); pbh, _ = boot_p50(r, L / 2); ph, _ = boot_p50(r, L, 0.5); phh, medh = boot_p50(r, L / 2, 0.5)
    c = corr_fund(r); cs = " ".join(f"{a:+.2f}/{b:+.2f}" for a, b in c.values())
    print(f"{k:42s} {L:5.2f} {mL:+8.2%} {mH:+9.2%} |      {pb:5.0%}      {pbh:5.0%} |        {medh:+8.2%}        {ph:5.0%} {phh:5.0%} | {cs}")
    OUT[k] = dict(L=L, mL=mL, mH=mH)
print("\nNota: L* e' misurata a posteriori e include il fatto di aver saputo quale giorno peggiore c'e' nel campione. Per K1 il filtro ha evitato il 5/2/2018 per un giorno:")
print("con un giorno di ritardo (K1s) quel giorno entra per intero (-96%) e L* crolla. La leva prudente va calcolata su K1s, non su K1.")
print("Vincolo reale: IBKR chiede ~2.500 $ di margine per un VXM corto (~1.900 $ di nozionale): per chi vende, leva sul nozionale <= ~0,75x. STIMA dalla tabella margini IBKR.")

print("\n=== effetto sul fondo: Sharpe del fondo + x*candidato (2018-04 -> 2026-10) ===")
f = fund(); sh365 = lambda r: r.mean() / r.std() * np.sqrt(365)
for fk in f:
    b = f[fk]; line = f"{fk:28s} da solo {sh365(b):.2f} |"
    for k in list(K)[:1] + list(K)[4:8]:
        c = to_cal(K[k]).reindex(f.index).fillna(0)
        best = max(((sh365(b + x * c), x) for x in (0, .05, .1, .2, .3, .5, 1.0)))
        line += f" {k.split()[0]}: x=0,1 -> {sh365(b + 0.1 * c):.2f}, migliore x={best[1]:.2f} -> {best[0]:.2f} |"
    print(line)
print("(il 'migliore x' e' scelto a posteriori sullo stesso campione: e' un limite superiore, non una stima)")
keep = {"K1_corto_futVIX_filtro_base": K["K1 corto fut VIX se VIX<ST (1x noz.)"], "K1s_stress_ritardo": K["K1s idem, un giorno di ritardo (stress)"],
        "K0_corto_futVIX_sempre": K["K0 corto fut VIX sempre (1x noz.)"], "K2_VPD_MM200": K["K2 VPD (indice CBOE) se SPX>MM200"], "K3_PUT_sempre": K["K3 PUT (indice CBOE) sempre"],
        "K4_putspread_STIMA": K["K4 put-spread 3% OTM largo 5% (STIMA)"], "K5_fut_call13_STIMA": K["K5 fut+call 1,3 filtro (STIMA)"]}
ret = pd.DataFrame({k: to_cal(v) for k, v in keep.items()}); ret.to_parquet("returns.parquet")
print("\nreturns.parquet:", ret.shape, ret.index[0].date(), ret.index[-1].date(), "(rendimenti netti giornalieri, indice di calendario, senza leva; in eccesso sul T-bill)")
tr = {}
for i in (2, 3, 4): tr.update(json.load(open(f"trials_0{i}.json")))
print("varianti provate:", tr, "TOTALE", sum(tr.values()))
