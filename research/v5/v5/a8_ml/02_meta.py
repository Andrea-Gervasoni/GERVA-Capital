"""A8 - 02: META-LABELLING. Un modello appreso ordina i trade meglio della conviction a pesi uguali?
Protocollo: iper-parametri scelti SOLO sul periodo di scelta (blocchi OOS 2019H2-2022H2, walk-forward a finestra crescente,
purga 7g + embargo 7g); UNA configurazione congelata valutata sulla verifica (2023-01 -> 2026-10, ristima semestrale)."""
import json, itertools, time
from ml import *
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 200)
D, F = load(); F12 = SIG; r = D['R_L'].values; sel = (D['date'] <= SEL_LAST).values; ver = (D['date'] >= SPL).values
print(f'righe {len(D)}  feature {len(F)}  scelta {sel.sum()}  verifica {ver.sum()}')
GRID = [('LOGIT12', dict(kind='logit', C=C, fs='12')) for C in (0.003, 0.03, 0.3)] + [('LOGITALL', dict(kind='logit', C=C, fs='all')) for C in (0.0003, 0.003, 0.03)]
for k, fam in (('hgbc', 'HGBC'), ('hgbr', 'HGBR')):
    GRID += [(fam, dict(kind=k, depth=d, iters=n, leaf=l, fs='all')) for d, n, l in itertools.product((2, 3), (50, 150), (100, 300))]
fs = lambda cfg: F12 if cfg['fs'] == '12' else F

print('\n== 1. Scelta degli iper-parametri (solo <=2022). Criterio pre-dichiarato: IC medio per blocco (Spearman previsione-R) ==')
rows = []; t0 = time.time()
for fam, cfg in GRID:
    p = walk(D, fs(cfg), cfg, SEL_BLOCKS); ic = block_ic(D, p, r, SEL_BLOCKS, SEL_LAST); m = sel & np.isfinite(p)
    rows.append(dict(fam=fam, cfg=json.dumps({k: v for k, v in cfg.items() if k not in ('kind', 'fs')}), ic=ic.mean(), ic_t=ic.mean() / ic.std(ddof=1) * np.sqrt(len(ic)), ic_pos=(ic > 0).mean(),
                     top20=top_minus_all(p[m], r[m]), _cfg=cfg))
G = pd.DataFrame(rows); print(G.drop(columns='_cfg').round(3).to_string(index=False)); print(f'varianti di modello provate: {len(G)}  ({time.time()-t0:.0f}s)')
# riferimento: conviction a pesi uguali come "previsione" sugli stessi blocchi
mref = sel & (D['date'] >= SEL_BLOCKS[0]).values; sc = D['score'].values
ic0 = block_ic(D, np.where(D['date'] >= SEL_BLOCKS[0], sc, np.nan), r, SEL_BLOCKS, SEL_LAST)
print(f"riferimento conviction (pesi uguali): IC medio {ic0.mean():.3f} t {ic0.mean()/ic0.std(ddof=1)*np.sqrt(len(ic0)):.2f} blocchi>0 {(ic0>0).mean():.2f}  top20-all {top_minus_all(sc[mref], r[mref]):.3f}")
best = G.loc[G.ic.idxmax()]; PRIM = best['_cfg']; fam_best = {f: G[G.fam == f].loc[G[G.fam == f].ic.idxmax(), '_cfg'] for f in G.fam.unique()}
print('\nCONFIGURAZIONE CONGELATA (primaria):', best['fam'], PRIM); print('secondarie (migliore di ogni famiglia):', {k: {a: b for a, b in v.items() if a not in ("kind", "fs")} for k, v in fam_best.items()})
json.dump(dict(primary=PRIM, primary_fam=best['fam'], fam_best=fam_best, n_grid=len(G)), open(HERE + '/frozen.json', 'w'))

print('\n== 2. Verifica (>=2023): configurazione congelata, walk-forward semestrale ==')
ALLB = list(SEL_BLOCKS) + list(VER_BLOCKS); P = {}
for fam, cfg in fam_best.items(): P[fam] = walk(D, fs(cfg), cfg, ALLB)
P['CONV'] = np.where(D['date'] >= SEL_BLOCKS[0], sc, np.nan)
pd.DataFrame(P).assign(coin=D.coin, date=D.date).to_parquet(HERE + '/preds.parquet')
mon = D['date'].dt.to_period('M').astype(str).values
def summ(p, mask, lab):
    m = mask & np.isfinite(p); blocks = SEL_BLOCKS if lab == 'scelta' else VER_BLOCKS; ic = block_ic(D, np.where(mask, p, np.nan), r, blocks)
    o = dict(per=lab, n=m.sum(), ic=ic.mean(), ic_t=ic.mean() / ic.std(ddof=1) * np.sqrt(len(ic)), ic_pos=f'{(ic>0).sum()}/{len(ic)}', Rall=r[m].mean())
    for q, nm in ((0.7, 'top30'), (0.8, 'top20'), (0.9, 'top10')):
        t = m & (p >= np.quantile(p[m], q)); o[f'R_{nm}'] = r[t].mean(); o[f't_{nm}'] = block_t(r[t] - r[m].mean(), mon[t])
    b = m & (p <= np.quantile(p[m], 0.2)); o['R_bot20'] = r[b].mean()
    return o
rows = []
for k, p in P.items():
    for lab, mask in (('scelta', sel), ('verifica', ver)): rows.append(dict(modello=k + ('*' if k == best['fam'] else ''), **summ(p, mask, lab)))
print(pd.DataFrame(rows).round(3).to_string(index=False))
print('(* = primaria. t_top = t della differenza R(top)-R(tutti) con errori raggruppati per mese. Soglie dei quantili calcolate nel periodo stesso: descrittivo.)')

def deciles(p, mask, nq=10):
    m = mask & np.isfinite(p); q = pd.qcut(pd.Series(p[m]).rank(method='first'), nq, labels=False).values; x = pd.DataFrame(dict(q=q + 1, p=p[m], R=r[m], mon=mon[m]))
    g = x.groupby('q'); o = g.agg(n=('R', 'size'), p_medio=('p', 'mean'), hit=('R', lambda v: (v > 0).mean()), R=('R', 'mean'), sd=('R', 'std'))
    o['R/sd'] = o.R / o.sd; o['t_mese'] = [block_t(v.R.values, v.mon.values) for _, v in g]; return o
pp = P[best['fam']]
for lab, mask in (('SCELTA (OOS 2019H2-2022)', sel), ('VERIFICA (2023-2026)', ver)):
    print(f'\n-- R per decile di probabilita prevista, modello primario, {lab} --'); print(deciles(pp, mask).round(3).to_string())
print('\n-- stessa tabella per la conviction a pesi uguali (quintili dello score), VERIFICA --'); print(deciles(P['CONV'], ver, 5).round(3).to_string())
yrs_v = (D.date[ver].max() - D.date[ver].min()).days / 365.25
print('\n-- uplift in verifica se si tengono solo i decili alti (candidati giornalieri SOVRAPPOSTI: non e\' ancora un libro eseguibile) --')
m = ver & np.isfinite(pp); base = rstats(r[m]); rows = [dict(insieme='tutti i giorni', **base, cand_anno=m.sum() / yrs_v)]
ta = m & (D.tier == 'alta').values; rows.append(dict(insieme='regola: conviction alta', **rstats(r[ta]), cand_anno=ta.sum() / yrs_v))
for q in (0.7, 0.8, 0.9):
    t = m & (pp >= np.quantile(pp[m], q)); rows.append(dict(insieme=f'modello top {round((1-q)*100)}%', **rstats(r[t]), cand_anno=t.sum() / yrs_v))
u = pd.DataFrame(rows).drop(columns='t'); print(u.round(3).to_string(index=False))
print('\n-- per anno: IC e R(top20%)-R(tutti) del modello primario; R(alta)-R(tutti) della regola --')
rows = []
for y in range(2019, 2027):
    m = (D.date.dt.year == y).values & np.isfinite(pp)
    if m.sum() < 50: continue
    rows.append(dict(anno=y, n=m.sum(), ic=spearmanr(pp[m], r[m])[0], ic_conv=spearmanr(sc[m], r[m])[0], top20_modello=top_minus_all(pp[m], r[m]), alta_regola=r[m & (D.tier == 'alta').values].mean() - r[m].mean(), R_tutti=r[m].mean()))
print(pd.DataFrame(rows).round(3).to_string(index=False))
