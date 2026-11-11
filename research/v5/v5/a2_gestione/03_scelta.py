"""A2 - scelta sul periodo <= 2022 e verifica >= 2023 (SIMULATO).
(a) per base e famiglia: la variante migliore in scelta (G_s = N*(Rm/sigma)^2) e che cosa fa in verifica, con costi x2 e ritardo;
(b) la scelta predice la verifica? correlazione di rango tra il miglioramento in scelta e in verifica su tutte le varianti;
(c) combinazioni delle famiglie migliori in scelta; (d) trailing 2x per larghezza dello stop; (e) durata massima;
(f) bootstrap a mesi appaiati regola-vs-base in verifica; (g) per anno; (h) salvataggio di trades.parquet / returns.parquet."""
import itertools, numpy as np, pandas as pd, engine as G
from engine import params, book, row, blk, CUT
import importlib; g2 = importlib.import_module('02_griglia'); BASES, V = g2.BASES, g2.V
pd.set_option('display.width', 280); pd.set_option('display.max_rows', 500); pd.set_option('display.max_colwidth', 70)
R = pd.read_parquet('griglia.parquet'); NTR = len(R)
KW = {(f, l): kw for f, l, kw in V}
SUPER = {'trail': 'uscita_mobile', 'trail_att': 'uscita_mobile', 'chandelier': 'uscita_mobile', 'parabolico': 'uscita_mobile'}
R['sfam'] = R.fam.map(lambda f: SUPER.get(f, f))
def full(P, lab, **ex):
    T = book(P); d = row(T, lab, **ex)
    r2 = row(book(P, cost=2.0), lab); P1 = P.copy(); P1[G.DELAY] = 1; r1 = row(book(P1), lab)
    for k in ('R', 'q', 'G', 'S2', 'G_s', 'S2_s', 'R_v', 'q_v', 'G_v', 'S2_v'): d[k + '_c2'] = r2.get(k, np.nan); d[k + '_d1'] = r1.get(k, np.nan)
    return d, T
c1 = ['sfam', 'cfg', 'npy_s', 'R_s', 'sig_s', 'q_s', 'hit_s', 'streak_s', 'G_s', 'S2_s', 'npy_v', 'R_v', 'sig_v', 'q_v', 'hit_v', 'streak_v', 't_v', 't_cl_v', 'G_v', 'S2_v',
      'R_v_c2', 'q_v_c2', 'G_v_c2', 'S2_v_c2', 'R_v_d1', 'q_v_d1', 'G_v_d1']
print('SIMULATO. G = N*(Rm/sigma)^2 per trade; S2 = Sharpe annuo^2 del flusso giornaliero di R (tiene conto dei trade simultanei). _s scelta, _v verifica.\n')
print('== (a) per base: la migliore variante di ogni famiglia SCELTA SU G_s, e il suo esito in verifica ==')
BEST = {}; summ = []
for bn in BASES:
    X = R[R.base == bn]; b0 = X[X.fam == 'base'].iloc[0]
    S = X[X.fam != 'base'].sort_values('G_s', ascending=False).groupby('sfam').head(1)
    S = pd.concat([X[X.fam == 'base'], S]); BEST[bn] = S
    print(f'--- base {bn} {BASES[bn]} (leva mediana {b0.L:.1f}x) ---'); print(S[c1].round(3).to_string(index=False))
    Y = X[X.fam != 'base']
    dS = Y.G_s - b0.G_s; dV = Y.G_v - b0.G_v; dV2 = Y.G_v_c2 - b0.G_v_c2
    rho = pd.Series(dS.values).corr(pd.Series(dV.values), method='spearman')
    summ.append(dict(base=bn, G_s_base=b0.G_s, G_v_base=b0.G_v, G_v_c2_base=b0.G_v_c2, n_var=len(Y), meglio_in_scelta=(dS > 0).sum(), meglio_in_verifica=(dV > 0).sum(),
                     meglio_in_entrambe=((dS > 0) & (dV > 0)).sum(), meglio_in_entrambe_e_costi_x2=((dS > 0) & (dV > 0) & (dV2 > 0)).sum(), rho_rango_scelta_verifica=rho,
                     dGv_mediana_delle_scelte=(S[S.fam != 'base'].G_v - b0.G_v).median(), dGv_della_migliore_in_scelta=Y.loc[Y.G_s.idxmax(), 'G_v'] - b0.G_v))
    print()
print('== (b) la scelta predice la verifica? ==')
print(pd.DataFrame(summ).round(3).to_string(index=False))
print('\nvarianti migliori della base in scelta, in verifica E con costi x2 in verifica:')
for bn in BASES:
    X = R[R.base == bn]; b0 = X[X.fam == 'base'].iloc[0]; Y = X[(X.G_s > b0.G_s) & (X.G_v > b0.G_v) & (X.G_v_c2 > b0.G_v_c2) & (X.fam != 'base')]
    Y = Y.assign(dG_s=Y.G_s - b0.G_s, dG_v=Y.G_v - b0.G_v, dG_v_c2=Y.G_v_c2 - b0.G_v_c2, dS2_v=Y.S2_v - b0.S2_v)
    print(f'--- base {bn} ---'); print(Y[['cfg', 'G_s', 'dG_s', 'G_v', 'dG_v', 'dG_v_c2', 'dS2_v', 'q_s', 'q_v']].round(3).to_string(index=False) if len(Y) else '  nessuna')

print('\n== (c) combinazioni: le tre famiglie migliori in scelta (che battono la base in scelta), a coppie e in terna ==')
rows = []; TB = {}
for bn in BASES:
    S = BEST[bn]; b0 = S[S.fam == 'base'].iloc[0]; top = S[(S.fam != 'base') & (S.G_s > b0.G_s)].head(3)
    for r_ in range(2, len(top) + 1):
        for cmb in itertools.combinations(range(len(top)), r_):
            kw = {}; lab = []
            for i in cmb: kw.update(KW[(top.iloc[i].fam, top.iloc[i].cfg)]); lab.append(top.iloc[i].cfg)
            d, T = full(params(**BASES[bn], **kw), ' + '.join(lab), base=bn, sfam='combinazione'); rows.append(d); NTR += 1
C = pd.DataFrame(rows)
if len(C):
    for bn in BASES:
        b0 = R[(R.base == bn) & (R.fam == 'base')].iloc[0]
        print(f'--- base {bn}: G_s {b0.G_s:.3f} G_v {b0.G_v:.3f} G_v_c2 {b0.G_v_c2:.3f} ---'); print(C[C.base == bn][c1[1:]].round(3).to_string(index=False))

print('\n== (d) il trailing a 2x lo stop iniziale, per larghezza dello stop (rimisurato) ==')
rows = []
for lab, bk in [('0,9%', dict(sd=0.009)), ('1,7%', dict(sd=0.017)), ('2,7%', dict(sd=0.027)), ('4%', dict(sd=0.04)), ('6%', dict(sd=0.06)), ('10%', dict(sd=0.10)),
                ('0,5xATR', dict(atr_k=0.5)), ('1xATR', dict(atr_k=1.0)), ('2xATR', dict(atr_k=2.0))]:
    o = {}
    for tl, kw in (('no', {}), ('2x', dict(tmode=1, tm=2.0))):
        d, T = full(params(**bk, **kw), lab); o[tl] = d
        if lab not in ('1,7%', '1xATR', '2xATR'): NTR += 1
    rows.append(dict(stop=lab, n_no=o['no']['npy'], n_2x=o['2x']['npy'], R_s_no=o['no']['R_s'], R_s_2x=o['2x']['R_s'], q_s_no=o['no']['q_s'], q_s_2x=o['2x']['q_s'],
                     G_s_no=o['no']['G_s'], G_s_2x=o['2x']['G_s'], R_v_no=o['no']['R_v'], R_v_2x=o['2x']['R_v'], q_v_no=o['no']['q_v'], q_v_2x=o['2x']['q_v'],
                     G_v_no=o['no']['G_v'], G_v_2x=o['2x']['G_v'], G_v_c2_no=o['no']['G_v_c2'], G_v_c2_2x=o['2x']['G_v_c2']))
print(pd.DataFrame(rows).round(3).to_string(index=False))

print('\n== (e) durata massima (giorni) ==')
rows = []
for bn in BASES:
    for mh in (2, 3, 5, 7, 10, 14):
        d, T = full(params(**BASES[bn], maxhold=mh), f'{bn} max {mh} giorni', base=bn); rows.append(d)
        if mh != 7: NTR += 1
print(pd.DataFrame(rows)[['cfg', 'npy_s', 'R_s', 'q_s', 'G_s', 'S2_s', 'npy_v', 'R_v', 'q_v', 'G_v', 'S2_v', 'G_v_c2', 'G_v_d1']].round(3).to_string(index=False))

print('\n== (f) bootstrap a mesi appaiati in verifica: regola scelta in (a)/(c) contro la sua base (2000 ricampionamenti) ==')
def daily(T, t0=CUT):
    x = T[T.entry >= t0]; idx = pd.date_range(max(t0, T.entry.min().normalize()), '2026-10-31')
    return x.groupby(x.exit.dt.normalize()).R.sum().reindex(idx, fill_value=0.0)
def S2(d):
    s = d.mean() / d.std() * np.sqrt(365.25); return s * abs(s)
def boot(Tr, Tb, nb=2000, seed=1, t0=CUT):
    a = daily(Tr, t0); b = daily(Tb, t0); mo = a.index.to_period('M'); keys = mo.unique()
    ga = [a[mo == k].values for k in keys]; gb = [b[mo == k].values for k in keys]; rng = np.random.default_rng(seed); out = []
    for _ in range(nb):
        ii = rng.integers(0, len(keys), len(keys))
        out.append(S2(pd.Series(np.concatenate([ga[i] for i in ii]))) - S2(pd.Series(np.concatenate([gb[i] for i in ii]))))
    out = np.array(out); return S2(a) - S2(b), np.percentile(out, 5), np.percentile(out, 95), (out > 0).mean()
KEEP = {}
for bn in BASES:
    Tb = book(params(**BASES[bn])); KEEP[f'{bn}_base'] = Tb
    S = BEST[bn]; b0 = S[S.fam == 'base'].iloc[0]; cand = S[(S.fam != 'base') & (S.G_s > b0.G_s)].head(3)
    for _, r_ in cand.iterrows():
        Tr = book(params(**BASES[bn], **KW[(r_.fam, r_.cfg)])); d, lo, hi, p = boot(Tr, Tb)
        print(f'{bn}: {r_.cfg:52s} dS2_v {d:+.3f}  [5%,95%] = [{lo:+.2f},{hi:+.2f}]  P(dS2>0) = {p:.2f}')
        if r_.cfg == cand.iloc[0].cfg: KEEP[f'{bn}_scelta'] = Tr; KEEP[f'{bn}_scelta_cfg'] = r_.cfg

print('\n== (f2) coerenza tra basi: regole che migliorano G in almeno 5 celle su 6 (3 basi x scelta/verifica) - elenco a posteriori, NON una scelta ==')
P_ = R.pivot_table(index=['fam', 'cfg'], columns='base', values=['G_s', 'G_v', 'G_v_c2'])
b0 = {(k, bn): R[(R.base == bn) & (R.fam == 'base')][k].iloc[0] for k in ('G_s', 'G_v', 'G_v_c2') for bn in BASES}
D = pd.DataFrame({f'd{k}_{bn}': P_[(k, bn)] - b0[(k, bn)] for k in ('G_s', 'G_v', 'G_v_c2') for bn in BASES})
D['celle'] = (D[[f'd{k}_{bn}' for k in ('G_s', 'G_v') for bn in BASES]] > 0).sum(axis=1)
Dc = D[D.celle >= 5].drop(index='base', level=0, errors='ignore').sort_values('celle', ascending=False)
print(Dc.round(3).to_string() if len(Dc) else '  nessuna')
print('\nbootstrap delle regole coerenti (verifica e intera storia; a posteriori):')
for (fam, cfg) in Dc.index:
    for bn in BASES:
        Tb = KEEP[f'{bn}_base']; Tr = book(params(**BASES[bn], **KW[(fam, cfg)]))
        d, lo, hi, p = boot(Tr, Tb); d2, lo2, hi2, p2 = boot(Tr, Tb, t0=pd.Timestamp('2017-01-01'))
        print(f'{bn}: {cfg:44s} verifica dS2 {d:+.3f} [{lo:+.2f},{hi:+.2f}] P={p:.2f} | intera storia dS2 {d2:+.3f} [{lo2:+.2f},{hi2:+.2f}] P={p2:.2f}')
        if cfg.startswith('1 aggiunta x1.0 ogni +1R, stop invariato') and bn == 'W': KEEP['W_piramide1'] = Tr; KEEP['W_piramide1_cfg'] = cfg

print('\n== (g) per anno: R medio / n / q (base e regola migliore in scelta) ==')
for bn in BASES:
    for tag in ('base', 'scelta', 'piramide1'):
        T = KEEP.get(f'{bn}_{tag}')
        if T is None: continue
        y = T.groupby(T.entry.dt.year).R.agg(['count', 'mean', 'std']); y['q'] = y['mean'] / y['std']
        print(f'{bn} {tag} ({KEEP.get(bn + "_" + tag + "_cfg", "nessuna gestione")}):')
        print('   ' + '  '.join(f'{int(a)}: {r["mean"]:+.2f}/{int(r["count"])}/{r["q"]:+.2f}' for a, r in y.iterrows()))

print('\n== (h) file salvati ==')
fr = []; ret = {}
for bn in BASES:
    for tag in ('base', 'scelta', 'piramide1'):
        T = KEEP.get(f'{bn}_{tag}')
        if T is None: continue
        nm = f'{bn}_{tag}'; x = T.assign(book=nm, side=1, regola=KEEP.get(bn + '_' + tag + '_cfg', 'nessuna gestione'))
        fr.append(x[['book', 'regola', 'coin', 'side', 'entry', 'exit', 's', 'L', 'R', 'ret', 'why', 'nadd', 're']])
        ret[nm] = (0.01 * T.groupby(T.exit.dt.normalize()).R.sum()).reindex(pd.date_range(T.entry.min().normalize(), '2026-10-31'), fill_value=0.0)
pd.concat(fr).rename(columns={'s': 'stop_dist', 'L': 'leva'}).to_parquet('trades.parquet')
pd.DataFrame(ret).fillna(0.0).to_parquet('returns.parquet')
print('trades.parquet (libri: ' + ', '.join(ret) + '), returns.parquet = rendimenti giornalieri netti con rischio 1% del conto per trade, P&L al giorno d\'uscita, non composti')
print(f'\nVARIANTI PROVATE IN TOTALE (griglia + combinazioni + larghezze + durate): {NTR}')
