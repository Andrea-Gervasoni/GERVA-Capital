"""B4 - Test 1 e 2: corto sui futures VIX a breve (indice ST ricostruito = cio' che fa VXX), con filtro di contango,
e versioni a rischio definito (taglia piccola, stop, call di copertura STIMA Black-76 su VVIX)."""
from lab import *
from scipy.stats import norm
st, hi = F.st.loc["2006-01-03":], F.st_hi.loc["2006-01-03":]
vix, v3 = IX.VIX.reindex(st.index).ffill(), IX.VIX3M.reindex(st.index).ffill()
f1 = B["f1"].reindex(st.index); F1, F2 = f1.F.astype(float), f1.F2.astype(float)
lvl = F.st_lvl.reindex(st.index)
SIG = {"sempre corto": pd.Series(1.0, st.index),
       "F1<F2 (contango futures)": (F1 < F2).astype(float),
       "VIX<ST (base positiva)": (vix < lvl).astype(float),
       "VIX<ST e F1<F2": ((vix < lvl) & (F1 < F2)).astype(float)}
for thr in (0.85, 0.90, 0.95, 1.00): SIG[f"VIX/VIX3M<{thr:.2f}"] = (vix / v3 < thr).astype(float).where(v3.notna())
print("=== TEST 1: corto ST (peso 1 = nozionale pari al capitale; perdita del 96% il 5/2/2018 se non filtrato) ===")
print("Esecuzione base: segnale alla chiusura d, eseguito al settle d+1. Costi 20 pb per lato + roll 1,9 pb/giorno.\n" + HEAD)
R = {}
for k, s in SIG.items():
    for mode in ("piatto", "lungo"):
        if k == "sempre corto" and mode == "lungo": continue
        pos = -s if mode == "piatto" else -(2 * s - 1)
        r = apply(pos, st); count("T1 corto ST con filtro"); R[(k, mode)] = r
        print(row(f"{k} | in backw. {mode}", r))
print("\nNB i CAGR a peso 1 sono indicativi: un corto 1x perde tutto o quasi in un giorno come il 5/2/2018 (ST +96%, massimo +102%).")
# scelta sul periodo di scelta
selsh = {k: sharpe(r.loc[:SEL_END]) for k, r in R.items()}
best = max(selsh, key=selsh.get); print("\nMigliore per Sharpe sul periodo di scelta:", best, f"{selsh[best]:.2f}")
bs = SIG[best[0]]; bpos = -bs if best[1] == "piatto" else -(2 * bs - 1)
print("\n--- robustezza del migliore ---\n" + HEAD)
for nm, kw in [("lag0 (stessa chiusura, ottimistico)", dict(lag=0)), ("base (lag1)", {}), ("lag2 (un giorno in piu')", dict(lag=2)),
               ("costi x2", dict(cost=2 * C_FUT, roll=2 * ROLL_D))]:
    print(row(nm, apply(bpos, st, **kw)))
rb = apply(bpos, st); print(f"t-stat rendimento medio giornaliero: {tstat(rb):.2f}   giorni in posizione: {(bpos.shift(2).fillna(0) != 0).mean():.0%}")
print("per anno:", "  ".join(f"{y}:{(1 + g).prod() - 1:+.0%}" for y, g in rb.groupby(rb.index.year)))
# controllo di troncamento
for d in ["2012-06-15", "2018-02-02", "2020-03-10", "2024-08-02"]:
    d = pd.Timestamp(d); vv, v33 = IX.VIX.loc[:d], IX.VIX3M.loc[:d]
    assert float(vv.iloc[-1] / v33.iloc[-1] < 0.90) == SIG["VIX/VIX3M<0.90"][d]
print("controllo di troncamento: OK (il segnale usa solo le chiusure del giorno d)")
# confronto con ETN reali (SVXY: -1x fino al 27/2/2018, poi -0,5x)
sv = ETN.SVXY.pct_change().reindex(st.index)
print("\n--- strumenti reali: SVXY comprato e tenuto / con lo stesso filtro (prezzi 16:00, quindi il 5-6/2/2018 e' spalmato su due giorni) ---\n" + HEAD)
print(row("SVXY reale sempre", sv.loc["2011-10-05":])); print(row("SVXY reale con filtro migliore", apply(bs, sv, cost=0.0005, roll=0).loc["2011-10-05":]))
print(row("ricostruito -ST sempre, stesso periodo", apply(-SIG['sempre corto'], st).loc["2011-10-05":]))

print("\n=== TEST 2: rischio definito ===")
print("(a) taglia: peso w tale che ST +100% in un giorno costi x% del capitale -> w = x. Stesso Sharpe, tutto scalato.\n" + HEAD)
for w in (0.05, 0.10, 0.20, 0.30):
    print(row(f"filtro migliore, w={w:.2f}", apply(w * bpos, st))); count("T2a taglia")
print("\n(b) stop intragiornaliero sull'indice ST: se il massimo del giorno supera +s% dal settle precedente si chiude; rientro dopo k giorni se il filtro lo consente.")
print("    'allo stop' = eseguito al livello +0,5% (cio' che la barra giornaliera lascia credere); 'al massimo' = eseguito al prezzo peggiore del giorno (stress).\n" + HEAD)
def with_stop(pos, s, cool, at_high):
    p = pos.shift(2).reindex(st.index).fillna(0).values.copy(); r, h = st.values, hi.values; out = np.zeros(len(p)); block = 0; prev = 0.0
    for i in range(len(p)):
        w = p[i] if block == 0 else 0.0
        if block > 0: block -= 1
        c = C_FUT * abs(w - prev) + ROLL_D * abs(w)
        if w < 0 and h[i] >= s:
            fill = h[i] if at_high else s + 0.005
            out[i] = w * fill - c - C_FUT * abs(w); prev = 0.0; block = cool
        else:
            out[i] = w * (r[i] if not np.isnan(r[i]) else 0) - c; prev = w
    return pd.Series(out, st.index)
for s in (0.10, 0.15, 0.20, 0.30):
    for cool in (1, 5):
        for ah in (False, True):
            count("T2b stop"); print(row(f"stop +{s:.0%} pausa {cool}g {'AL MASSIMO' if ah else 'allo stop'}", with_stop(bpos, s, cool, ah)))
print("\n(c) corto 1 future VIX del mese (stesso moltiplicatore di VXM, 100$) + 1 call VIX lunga sulla stessa scadenza, strike = F0*(1+m). STIMA:")
print("    call valutata Black-76 con vol = VVIX*(1+0,6*ln(K/F)) (skew crescente delle call VIX), costo 7,5% del premio (min 0,03) per lato. VVIX dal 2007.\n" + HEAD)
vv = IX.VVIX.reindex(st.index).ffill() / 100
def b76(Fw, K, T, s):
    if T <= 0: return max(Fw - K, 0.0)
    s = max(s, 0.05); d1 = (np.log(Fw / K) + 0.5 * s * s * T) / (s * np.sqrt(T)); return Fw * norm.cdf(d1) - K * norm.cdf(d1 - s * np.sqrt(T))
S_, H_ = B["S"], B["H"]; exp = B["exp"]; days = st.index
def hedged(m, sig, w=1.0, hedge=True, skew=0.6, at_high=False):
    """ciclo mensile: il giorno dopo ogni scadenza si vende il future che scade il mese dopo (se il filtro e' acceso alla chiusura precedente)
    e si compra la call; si tiene fino al giorno prima della scadenza; se il filtro si spegne si chiude tutto al settle del giorno dopo."""
    out = pd.Series(0.0, days); yms = list(exp.index)
    on = sig.shift(1).reindex(days).fillna(0)          # segnale di ieri, eseguo al settle di oggi
    for j in range(len(yms) - 1):
        e0, e1, ym = exp.iloc[j], exp.iloc[j + 1], yms[j + 1]
        seg = days[(days >= e0) & (days < e1)]
        if len(seg) < 3 or ym not in S_ or seg[0] < pd.Timestamp("2007-03-01"): continue
        inpos = False; K = F0 = prem_prev = 0.0
        for i, d in enumerate(seg):
            Ft = S_.at[d, ym]
            if np.isnan(Ft): continue
            T = (e1 - d).days / 365.0; pnl = 0.0
            if inpos:
                Fp = S_.at[seg[i - 1], ym]; iv = vv[d] * (1 + skew * np.log(K / Ft)) if hedge else 0
                prem = b76(Ft, K, T, min(max(iv, 0.3), 3.0)) if hedge else 0.0
                Fuse = max(H_.at[d, ym], Ft) if (at_high and (Ft / Fp - 1) > 0.15) else Ft
                pnl = -(Fuse - Fp) + (prem - prem_prev); prem_prev = prem
                if Fuse != Ft: pnl += 0  # chiuso al massimo: da li' in poi piatto
                last = (i == len(seg) - 1) or on[d] == 0 or Fuse != Ft
                if last:
                    pnl -= C_FUT * Ft + (max(0.03, 0.075 * prem) if hedge else 0); inpos = False
                    out[d] += w * pnl / F0
                    if Fuse != Ft: break
                    continue
                out[d] += w * pnl / F0
            elif on[d] == 1 and i < len(seg) - 2 and (i == 0 or True):
                inpos = True; F0 = Ft; K = round(F0 * (1 + m) * 2) / 2 if hedge else 0
                prem_prev = b76(Ft, K, T, min(max(vv[d] * (1 + skew * np.log(K / Ft)), 0.3), 3.0)) if hedge else 0.0
                out[d] += w * (-C_FUT * Ft - (max(0.03, 0.075 * prem_prev) if hedge else 0)) / F0
    return out.loc["2007-03-01":]
sgn = {"sempre": SIG["sempre corto"], "filtro": bs}
RH = {}
for nm, sg in sgn.items():
    r0 = hedged(0, sg, hedge=False); RH[(nm, "nudo")] = r0; count("T2c call"); print(row(f"future mensile corto NUDO, {nm}", r0))
    for m in (0.2, 0.3, 0.5, 1.0):
        r = hedged(m, sg); RH[(nm, m)] = r; count("T2c call"); print(row(f"+ call strike F0*{1+m:.1f}, {nm}", r))
print("sensibilita' allo skew (call piu' cara) e stress 'chiuso al massimo del giorno' per il caso filtro + call 1,3:")
for sk in (0.3, 1.0): count("T2c call"); print(row(f"skew {sk}", hedged(0.3, bs, skew=sk)))
print(row("premio call x1,5 (approx: skew 1,5)", hedged(0.3, bs, skew=1.5))); count("T2c call")
pd.DataFrame({"T1_best": rb, "T1_sempre": R[("sempre corto", "piatto")], "T2b_stop15_max": with_stop(bpos, 0.15, 1, True), "T2b_stop15": with_stop(bpos, 0.15, 1, False),
              "T2c_call13_filtro": RH[("filtro", 0.3)], "T2c_call15_filtro": RH[("filtro", 0.5)], "T2c_nudo_filtro": RH[("filtro", "nudo")],
              "T2c_call13_sempre": RH[("sempre", 0.3)]}).to_parquet("_r02.parquet")
pickle.dump({"best": best, "bs": bs}, open("_best02.pkl", "wb")); save_trials("trials_02.json"); print("\nvarianti:", TRIALS)
