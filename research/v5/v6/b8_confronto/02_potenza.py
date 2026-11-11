"""B8 - 02. Potenza statistica del confronto in avanti, lettura dello screenshot del conto IBKR, e tasso di errore delle
regole "battere GERVA Capital". Usa returns.parquet di 01_legacy.py. SIMULATO / STIMA.
Uso: /tmp/gv/bin/python 02_potenza.py > 02_potenza.out"""
import math, numpy as np, pandas as pd
from statistics import NormalDist
N = NormalDist(); HERE = '/home/user/GERVA-Capital/research/v5/v6/b8_confronto'
D = pd.read_parquet(HERE + '/returns.parquet'); RF = pd.read_parquet('/home/user/GERVA-Capital/research/v5/series.parquet')['RF'].reindex(D.index).fillna(0.0)
PAIRS = [('B_cassa_in_tbill', 'LEG_v3_1x'), ('B2_debito_reale', 'LEG_v3_1x'), ('C1_mtm_limiti', 'LEG_v3_1x'), ('C3_mtm_limiti_debito_reale', 'LEG_v33_leva15'), ('B2_debito_reale', 'LEG_v33_leva15')]
def sh(y): return (y - RF.reindex(y.index)).mean() / y.std() * math.sqrt(365)

print("=== 1. Quanti giorni di paper in parallelo servono (test appaiato sulla differenza di Sharpe) ===")
print("formula (Jobson-Korkie/Memmel, termine dominante): anni = (z_alfa + z_potenza)^2 * 2(1 - rho) / Delta^2 ; rho = correlazione giornaliera")
for a_lab, za in (('unilaterale 5%', N.inv_cdf(0.95)), ('unilaterale 10% (z > 1,28)', N.inv_cdf(0.90))):
    zb = N.inv_cdf(0.80)
    for n, l in PAIRS:
        rho = D[n].corr(D[l]); row = []
        for d in (0.5, 1.0):
            yrs = (za + zb) ** 2 * 2 * (1 - rho) / d ** 2; row.append(f"Delta {d}: {yrs:5.1f} anni = {yrs*365:6.0f} giorni")
        print(f"  [{a_lab}] {n} vs {l}: rho {rho:.2f}  " + ' | '.join(row))
    for rho in (0.0, 0.5, 0.9):
        print(f"  [{a_lab}] rho ipotetica {rho:.1f}: Delta 0.5 -> {(za+zb)**2*2*(1-rho)/0.25*365:6.0f} giorni ; Delta 1.0 -> {(za+zb)**2*2*(1-rho)*365:6.0f} giorni")
print("  differenza minima rilevabile (80% potenza, 5%):", ' '.join(f"{n}g: {math.sqrt((1.645+0.842)**2*2*(1-0.66)/(n/365)):.1f}" for n in (30, 90, 180, 365, 730)), "(unita' di Sharpe annuo, rho 0,66)")

print("\n=== 1b. Verifica per simulazione (bootstrap a blocchi della coppia storica, media del nuovo fondo spostata per avere Delta esatto) ===")
rng = np.random.default_rng(8)
def boot_idx(n, T, nb, block=20):
    restart = rng.random((nb, T)) < 1 / block; restart[:, 0] = True; start = rng.integers(n, size=(nb, T)); t = np.arange(T)
    last = np.maximum.accumulate(np.where(restart, t, 0), axis=1); return (np.take_along_axis(start, last, axis=1) + t - last) % n
def zdiff(a, b):
    """z della differenza di rendimento a pari volatilita' = differenza di Sharpe (per finestra)."""
    x = a / a.std(axis=1, keepdims=True) - b / b.std(axis=1, keepdims=True)
    return x.mean(axis=1) / x.std(axis=1, ddof=1) * np.sqrt(x.shape[1])
n_, l_ = 'B2_debito_reale', 'LEG_v3_1x'; a0 = (D[n_] - RF).values; b0 = (D[l_] - RF).values
for delta in (0.0, 0.5, 1.0):
    a = a0 - a0.mean() + (sh(D[l_]) + delta) * a0.std() / math.sqrt(365)
    for T in (90, 365, 1500, 6000):
        I = boot_idx(len(a), T, 1500); z = zdiff(a[I], b0[I])
        print(f"  Delta vera {delta:.1f}, {T:5d} giorni: P(z > 1,645) = {(z > 1.645).mean():.2f}   P(z > 1,3) = {(z > 1.3).mean():.2f}")

print("\n=== 1c. La differenza misurata nel backtest e' essa stessa significativa? ===")
for n, l in PAIRS:
    for lab, sl in (('tutto', slice(None, None)), ('verifica', slice('2023-01-01', None))):
        a, b = D[n].loc[sl], D[l].loc[sl]; T = len(a) / 365; rho = a.corr(b); d = sh(a) - sh(b)
        se = math.sqrt((2 * (1 - rho) + 0.5 * (sh(a) ** 2 + sh(b) ** 2 - 2 * sh(a) * sh(b) * rho ** 2) / 365) / T)
        print(f"  {n} - {l} [{lab}]: Delta Sharpe {d:+.2f}, errore standard {se:.2f}, z {d/se:+.2f}")

print("\n=== 2. Lo screenshot: conto 1.089.666 EUR, +2,89% dal 6/11; S&P 500 +2,31%; il distacco (0,58 punti) tutto l'11/11 ===")
nav1 = 1089666; nav0 = nav1 / 1.0289; lead = 0.0289 - 0.0231
print(f"  valore di partenza implicito {nav0:,.0f} EUR; distacco {lead:.2%} = {lead*nav0:,.0f} EUR")
print(f"  beta apparente: fino al 10/11 il conto ha fatto come l'indice -> beta ~ {(0.0289-lead)/0.0231:.2f} (se il salto dell'11/11 e' specifico); se invece e' tutto beta: {0.0289/0.0231:.2f}")
bd = D[D.index.day_of_week < 5].loc['2025-11-01':]; x = bd['SPY']
for k in ('LEG_v3_1x', 'LEG_v33_leva15'):
    b = np.cov(bd[k], x)[0, 1] / x.var(); res = bd[k] - b * x
    print(f"  modello riespresso {k} (ultimi 12 mesi, giorni di borsa): beta su SPY {b:.2f}, vol {bd[k].std()*math.sqrt(252):.1%}, vol residua {res.std()*math.sqrt(252):.1%} ({res.std():.2%} al giorno)")
print(f"  SPY ultimi 12 mesi: vol {x.std()*math.sqrt(252):.1%} ({x.std():.2%} al giorno)")
print("  probabilita' di un distacco >= 0,58 punti SENZA alcuna abilita' (alfa 0), per ipotesi di errore di replica (vol residua annua) e giorni:")
for te in (0.05, 0.10, 0.15, 0.20, 0.25):
    row = []
    for nd in (1, 3, 5):
        z = lead / (te / math.sqrt(252) * math.sqrt(nd)); row.append(f"{nd}g: z {z:.2f} P {1-N.cdf(z):.0%}")
    print(f"    vol residua {te:.0%}: " + ' | '.join(row))
print(f"  con beta 1,25 e alfa zero il distacco ATTESO e' {0.25*0.0231:.2%}: lo stesso numero senza alcuna abilita'")
print(f"  z dell'informazione sull'alfa annuo: per avere z = 2 con vol residua 15% servirebbe un alfa di {2*0.15/math.sqrt(5/252):.0%} l'anno sostenuto per 5 giorni")
print("  giorni necessari per distinguere il conto dall'S&P (alfa vero 5% / 10% l'anno, vol residua 15%, 80% potenza, 5%):", ' / '.join(f"{(1.645+0.842)**2*(0.15/a)**2:.0f} anni" for a in (0.05, 0.10)))

print("\n=== 3. Regole 'battere GERVA Capital': quante volte passano (finestre da bootstrap a blocchi; 4000 finestre) ===")
def maxdd(r):
    eq = np.cumprod(1 + r, axis=1); pk = np.maximum.accumulate(np.maximum(eq, 1.0), axis=1); return (eq / pk - 1).min(axis=1)
def rules(a, b):
    ca, cb = np.prod(1 + a, axis=1) - 1, np.prod(1 + b, axis=1) - 1; da, db = maxdd(a), maxdd(b); z = zdiff(a, b)
    A = (ca > cb) & (da >= 1.5 * np.minimum(db, -0.02)); return dict(A=A.mean(), B=(z > 1.3).mean(), AoB=(A | (z > 1.3)).mean(), AeZ0=(A & (z > 0)).mean(), perde=((ca < cb) & (z < -1.3)).mean())
for n, l in (('B2_debito_reale', 'LEG_v3_1x'), ('C3_mtm_limiti_debito_reale', 'LEG_v33_leva15'), ('B_cassa_in_tbill', 'LEG_v3_1x')):
    a_h, b_h = D[n].values, D[l].values; rfv = RF.values
    print(f"  {n} contro {l}  (Sharpe storico {sh(D[n]):.2f} contro {sh(D[l]):.2f})")
    for scen, shift in (('nessun vantaggio vero (Sharpe uguali)', 1.0), ('meta\' del vantaggio del backtest', 0.5), ('vantaggio del backtest', 0.0)):
        gap = (sh(D[n]) - sh(D[l])) * a_h.std() / math.sqrt(365); a = a_h - shift * gap
        for T in (90, 180, 365):
            I = boot_idx(len(a), T, 4000); r = rules(a[I], b_h[I])
            print(f"    {scen:38s} {T:3d}g: A (rende di piu' e caduta <= 1,5x) {r['A']:.0%} | B (z > 1,3) {r['B']:.0%} | A e z > 0 {r['AeZ0']:.0%} | sconfitta netta (z < -1,3) {r['perde']:.0%}")
