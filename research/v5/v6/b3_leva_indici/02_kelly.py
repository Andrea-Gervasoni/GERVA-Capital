"""02 - Leva costante che massimizza la crescita geometrica, per indice e per periodo; incertezza (bootstrap a blocchi mensili);
costo del decadimento da volatilita'; leva scelta sul passato e applicata al futuro. SIMULATO."""
from lab import *
U = underlying()
KS = np.arange(0, 8.01, 0.25)
SPREAD, TER = 0.010, 0.0075     # finanziamento sopra T-bill sul debito (k-1); TER se k>1 (tipo ETP)
def logmat(r, cash, dc, spread=SPREAD, ter=TER):
    r = r.values[:, None]; c = cash.values[:, None]; d = dc.values[:, None]; k = KS[None, :]
    x = k * r - (k - 1) * (c + spread * d / 360.0 * (k > 1)) - ter * d / 365.0 * (k > 1)
    x = np.where(k < 1, k * r + (1 - k) * c, x)
    return np.log(np.clip(1 + x, 1e-12, None)), (1 + x <= 0).any(axis=0)
def gk(L):  # crescita log annua per k
    return L.mean(axis=0) * 252
PER = [("1970-79","1970","1979"),("1980-89","1980","1989"),("1990-99","1990","1999"),("2000-09","2000","2009"),("2010-19","2010","2019"),("2020-26","2020","2026"),
       ("2000-02","2000","2002"),("<=2007","1970","2007"),(">=2008","2008","2026"),("<=2022 scelta","1970","2022"),(">=2023 verif.","2023","2026"),("intero","1970","2026")]
print(f"Finanziamento: T-bill + {SPREAD*100:.1f}% sul debito, TER {TER*100:.2f}% per k>1. g = crescita composta annua (CAGR).")
res = {}
for und in ["SPX", "NDX", "IXIC"]:
    r = U[und].dropna(); c = U["cash"].reindex(r.index); d = U["dc"].reindex(r.index)
    print(f"\n=== {und} ({r.index[0].date()} -> {r.index[-1].date()})")
    print(f"{'periodo':14s} {'vol':>6s} {'k*':>5s} {'CAGR(k*)':>9s} {'1x':>7s} {'2x':>7s} {'3x':>7s} {'5x':>8s} {'decad.3x':>9s} {'decad.5x':>9s} {'k* teorico':>10s} {'rovina k>=':>10s}")
    for nm, a, b in PER:
        rr = r.loc[a:b]
        if len(rr) < 200: continue
        cc, dd = c.loc[a:b], d.loc[a:b]
        L, ruin = logmat(rr, cc, dd); g = gk(L); g[ruin] = -np.inf
        ks = KS[np.argmax(g)]
        cg = lambda k: np.exp(g[np.where(KS == k)[0][0]]) - 1
        vol = rr.std() * np.sqrt(252); mu_ex = (rr - cc).mean() * 252
        dec = lambda k: k * (k - 1) / 2 * vol ** 2      # costo (in log) rispetto a k volte la crescita 1x
        kth = (mu_ex - SPREAD) / vol ** 2
        rk = KS[ruin].min() if ruin.any() else np.nan
        print(f"{nm:14s} {vol*100:5.1f}% {ks:5.2f} {cg(ks)*100:8.1f}% {cg(1)*100:6.1f}% {cg(2)*100:6.1f}% {cg(3)*100:6.1f}% {cg(5)*100:7.1f}% {dec(3)*100:8.1f}% {dec(5)*100:8.1f}% {kth:10.2f} {rk:10.2f}")
        res[f"{und}|{nm}"] = dict(k=float(ks), vol=float(vol))
    # bootstrap a blocchi di 21 sedute sull'intero campione: distribuzione di k* su orizzonti di 10 e di 30 anni
    rng = np.random.default_rng(7)
    L, _ = logmat(r, c, d); n = len(L); nb = n // 21
    Lb = L[: nb * 21].reshape(nb, 21, -1).sum(axis=1)      # log per blocco e per k
    for H in (3, 10, 30):
        m = int(H * 12); ksamp = []; g3 = []; g5 = []; g1 = []
        for _ in range(3000):
            ii = rng.integers(0, nb, m); gg = Lb[ii].sum(axis=0) / H
            ksamp.append(KS[np.argmax(gg)]); g1.append(gg[4]); g3.append(gg[12]); g5.append(gg[20])
        q = np.percentile(ksamp, [5, 25, 50, 75, 95]); g1, g3, g5 = map(np.array, (g1, g3, g5))
        print(f"  bootstrap orizzonte {H:2d} anni: k* percentili 5/25/50/75/95 = {q}; P(3x batte 1x)={np.mean(g3>g1):.2f}; P(5x batte 1x)={np.mean(g5>g1):.2f}; "
              f"P(3x perde denaro)={np.mean(g3<0):.2f}; P(5x perde denaro)={np.mean(g5<0):.2f}; P(1x perde)={np.mean(g1<0):.2f}")
    # mezzo vantaggio: tolgo meta' dell'extra-rendimento medio
    ex_half = ((r - c).mean() / 2)
    L2, _ = logmat(r - ex_half, c, d); g2 = gk(L2)
    print(f"  mezzo extra-rendimento (premio dimezzato): k* = {KS[np.argmax(g2)]:.2f}, CAGR(k*) = {(np.exp(g2.max())-1)*100:.1f}%, CAGR(3x) = {(np.exp(g2[12])-1)*100:.1f}%, CAGR(5x) = {(np.exp(g2[20])-1)*100:.1f}%")
    # fuori campione: k* stimato sui 10/20 anni precedenti (o tutto il passato), applicato all'anno dopo
    yrs = sorted(set(r.index.year)); Ld = pd.DataFrame(L, index=r.index)
    for look in (10, 20, 99):
        tot = 0.0; totopt = 0.0; ny = 0; kk = []
        for yv in yrs:
            past = Ld.loc[str(max(yrs[0], yv - look)):str(yv - 1)]
            if len(past) < 252 * min(look, 10): continue
            ks_i = int(np.argmax(past.values.mean(axis=0))); cur = Ld.loc[str(yv)].values
            tot += cur[:, ks_i].sum(); ny += len(cur) / 252; kk.append(KS[ks_i])
        base = Ld.loc[str(yrs[0] + min(look, 10)):]
        g_all = base.values.mean(axis=0) * 252
        print(f"  fuori campione, k* dai {look if look<99 else 'tutti i'} anni precedenti: CAGR realizzato {(np.exp(tot/ny)-1)*100:6.1f}% | k usato: media {np.mean(kk):.2f}, min {np.min(kk):.2f}, max {np.max(kk):.2f} | "
              f"stesso periodo: 1x {(np.exp(g_all[4])-1)*100:.1f}%, 2x {(np.exp(g_all[8])-1)*100:.1f}%, 3x {(np.exp(g_all[12])-1)*100:.1f}%, ottimo a posteriori k={KS[np.argmax(g_all)]:.2f} -> {(np.exp(g_all.max())-1)*100:.1f}%")
json.dump(res, open("kelly.json", "w"), indent=1)
# sensibilita' al costo di finanziamento
print("\n=== Sensibilita' di k* (intero campione) allo spread di finanziamento e al TER")
for und in ["SPX", "NDX"]:
    r = U[und].dropna(); c = U["cash"].reindex(r.index); d = U["dc"].reindex(r.index)
    for sp, te in [(0.0, 0.0), (0.005, 0.0), (0.01, 0.0075), (0.02, 0.0075), (0.035, 0.0075)]:
        L, ruin = logmat(r, c, d, sp, te); g = gk(L); g[ruin] = -np.inf
        print(f"  {und} spread {sp*100:.1f}% TER {te*100:.2f}%: k* = {KS[np.argmax(g)]:.2f}  CAGR(k*) {(np.exp(g.max())-1)*100:.1f}%  3x {(np.exp(g[12])-1)*100:.1f}%  5x {(np.exp(g[20])-1)*100 if np.isfinite(g[20]) else -100:.1f}%")
# tabelle di rischio dei k x costanti
print("\n=== Leva costante con costi di prodotto reali (2x ETF, 3x ETP, 5x ETP): intero / scelta / verifica")
PROD["5x_ETP"] = (5, 0.0075, 0.035)
print(f"{'serie':16s} {'periodo':8s}    CAGR     vol Sharpe   maxDD  mese-  sott'acqua(anni)")
for und in ["SPX", "NDX"]:
    r = U[und].dropna(); c = U["cash"].reindex(r.index); d = U["dc"].reindex(r.index)
    for nm, (k, ter, sp) in [("1x", (1, 0.0007, 0))] + list(PROD.items()):
        s = lev(r, c, d, k, ter, sp).clip(lower=-1)
        for per, ss in [("intero", s), ("<=2007", s.loc[:"2007"]), (">=2008", s.loc["2008":]), ("2000-02", s.loc["2000":"2002"]), ("scelta", s.loc[:SEL_END]), ("verif.", s.loc[VER_START:])]:
            print(f"{und+' '+nm:16s} {per:8s} {fmt(stats(ss, c))}")
