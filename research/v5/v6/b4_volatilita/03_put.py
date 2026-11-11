"""B4 - Test 3: vendita di put (indici CBOE reali) e di put-spread (STIMA Black-Scholes su VIX + skew), con filtri di trend e VIX.
Rendimenti in ECCESSO sul T-bill (gli indici CBOE includono l'interesse sul collaterale)."""
import sys; sys.path.insert(0, "/home/user/GERVA-Capital")
from lab import *
from scipy.stats import norm
from gerva.data.sources import Store
stc = Store("/home/user/GERVA-Capital/data_cache")
d0 = "2006-07-17"; idx = F.index[F.index >= d0]
spx, vix, v3 = IX.SPX.reindex(idx).ffill(), IX.VIX.reindex(idx).ffill(), IX.VIX3M.reindex(idx).ffill()
rf = RF.reindex(idx)
rv21 = np.log(IX.SPX).diff().rolling(21).std().mul(np.sqrt(252) * 100).reindex(idx)
ma200 = IX.SPX.rolling(200).mean().reindex(idx)
FIL = {"nessuno": pd.Series(1.0, idx), "SPX>MM200": (spx > ma200).astype(float), "VIX/VIX3M<1": (vix / v3 < 1).astype(float),
       "MM200 e VIX/VIX3M<1": ((spx > ma200) & (vix / v3 < 1)).astype(float), "VRP>0 (VIX>RV21)": (vix > rv21).astype(float),
       "VIX<25": (vix < 25).astype(float)}
def cboe(s): return stc.get("v6b4_cboe_" + s).iloc[:, 0].reindex(idx).ffill().pct_change()
X = {"SPX TR (riferimento)": IX.SPXTR.reindex(idx).ffill().pct_change()}
for s, nm in [("PUT", "PUT put ATM mensile"), ("PUTY", "PUTY put 2% OTM"), ("WPUT", "WPUT put settimanale"), ("BXM", "BXM buy-write"), ("BXMD", "BXMD buy-write 30d"),
              ("CMBO", "CMBO"), ("CNDR", "CNDR iron condor"), ("BFLY", "BFLY iron butterfly"), ("VPD", "VPD corto fut VIX a rischio limitato"), ("VPN", "VPN corto fut VIX + call"),
              ("PPUT", "PPUT SPX + put 5% OTM"), ("VXTH", "VXTH SPX + call VIX")]:
    X[nm] = cboe(s)
X = {k: (v - rf) for k, v in X.items()}
FEE = 0.004 / 252    # replica degli indici con opzioni reali: stima 0,4%/anno di attrito
print("=== TEST 3a: indici strategia CBOE (dati reali d'indice; non direttamente acquistabili: replica con opzioni XSP/SPX) ===\n" + HEAD)
R3 = {}
for k, r in X.items():
    print(row(k + " | sempre", r - FEE)); count("T3a indici"); R3[(k, "nessuno")] = r - FEE
print("\n--- con filtri (segnale alla chiusura d, eseguito alla chiusura d+1; 5 pb per cambio) ---")
for fn, f in list(FIL.items())[1:]:
    print(f"[filtro {fn}]")
    for k, r in X.items():
        if "riferimento" in k and fn != "SPX>MM200": pass
        rr = apply(f, r, cost=0.0005, roll=FEE); R3[(k, fn)] = rr; count("T3a indici"); print(row(k, rr))
sel = {k: sharpe(v.loc[:SEL_END]) for k, v in R3.items() if "SPX TR" not in k[0] and "VXTH" not in k[0] and "PPUT" not in k[0]}
top = sorted(sel, key=sel.get, reverse=True)[:6]
print("\nI 6 migliori per Sharpe sul periodo di scelta (vendita di premio):")
for k in top: print(row(f"{k[0][:26]} | {k[1]}", R3[k]), f" t={tstat(R3[k]):.1f}")

print("\n=== TEST 3b: put e put-spread su SPX modellati (STIMA) ===")
print("Ciclo di 21 sedute, scadenza a 30 giorni, tenuto a scadenza. Vol implicita dello strike: VIX*(0,92+4*max(0,1-K/S)). Costo per gamba in ingresso: max(0,5 punti SPX, 3% del premio).")
print("Rendimento per unita' di nozionale SPX (un XSP = 1/10 SPX x 100$ ~ 75.000$ di nozionale: per 12k EUR la put nuda e' gia' leva 5-6x).\n" + HEAD)
def bsput(S, K, T, s):
    if T <= 1e-9: return max(K - S, 0.0)
    d1 = (np.log(S / K) + 0.5 * s * s * T) / (s * np.sqrt(T)); return K * norm.cdf(-(d1 - s * np.sqrt(T))) - S * norm.cdf(-d1)
iv = lambda S, K, v: v / 100 * (0.92 + 4 * max(0.0, 1 - K / S))
Sv, Vv = spx.values, vix.values
def putsim(a, b, filt=None, skew_mult=1.0):
    out = np.zeros(len(idx)); n = len(idx); f = filt.shift(1).fillna(0).values if filt is not None else np.ones(n)
    i = 1
    while i < n - 1:
        if f[i] == 0: i += 1; continue
        S0 = Sv[i]; K1 = S0 * (1 - a); K2 = S0 * (1 - a - b) if b else None; end = min(i + 21, n - 1)
        val = lambda j: (bsput(Sv[j], K1, (end - j) / 252, iv(Sv[j], K1, Vv[j]) * skew_mult) -
                         (bsput(Sv[j], K2, (end - j) / 252, iv(Sv[j], K2, Vv[j]) * skew_mult) if b else 0.0))
        p1 = bsput(S0, K1, 21 / 252, iv(S0, K1, Vv[i]) * skew_mult); p2 = bsput(S0, K2, 21 / 252, iv(S0, K2, Vv[i]) * skew_mult) if b else 0.0
        cost = max(0.5, 0.03 * p1) + (max(0.5, 0.03 * p2) if b else 0.0)
        prev = p1 - p2; out[i] -= cost / S0
        for j in range(i + 1, end + 1):
            v = val(j); out[j] += -(v - prev) / S0; prev = v
        i = end
    return pd.Series(out, idx)
PS = {}
for a in (0.0, 0.03, 0.05):
    for b in (None, 0.05, 0.10):
        for fn in ("nessuno", "SPX>MM200", "VIX/VIX3M<1"):
            r = putsim(a, b, None if fn == "nessuno" else FIL[fn]); count("T3b put modellate"); PS[(a, b, fn)] = r
            print(row(f"put {a:.0%} OTM {'nuda' if not b else f'spread {b:.0%}'} | {fn}", r))
c = pd.concat([PS[(0.0, None, "nessuno")], X["PUT put ATM mensile"]], axis=1).dropna()
print(f"\nControllo del modello: put ATM modellata vs indice PUT reale (eccesso): corr giornaliera {c.corr().iloc[0,1]:.2f}; media annua modello {c.iloc[:,0].mean()*252:+.2%} vs indice {c.iloc[:,1].mean()*252:+.2%}")
print("sensibilita' allo skew (vol implicita x0,9: premi piu' magri) per lo spread 3% OTM largo 5%:"); print(row("vol x0,9", putsim(0.03, 0.05, None, 0.9))); count("T3b put modellate")
pd.DataFrame({"T3_" + (k[0].split()[0]) + "_" + k[1].replace(" ", ""): R3[k] for k in top[:4]} |
             {"T3_PUT_sempre": R3[("PUT put ATM mensile", "nessuno")], "T3_VPD_sempre": R3[("VPD corto fut VIX a rischio limitato", "nessuno")],
              "T3_VPN_sempre": R3[("VPN corto fut VIX + call", "nessuno")], "T3b_spread3_5": PS[(0.03, 0.05, "nessuno")],
              "T3b_spread3_5_ratio": PS[(0.03, 0.05, "VIX/VIX3M<1")], "SPX_ecc": X["SPX TR (riferimento)"]}).to_parquet("_r03.parquet")
save_trials("trials_03.json"); print("\nvarianti:", TRIALS)
