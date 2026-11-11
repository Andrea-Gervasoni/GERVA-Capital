"""B5 - sintesi: candidato notte (K5, LB252, prezzo>30$), controlli finali (placebo alta volatilita', copertura con SPY),
leva ottima, capitalizzazione mensile, bootstrap P(-50%), correlazione col fondo, conto minimo, returns.parquet. SIMULATO."""
from lab import *
import importlib.util, io, contextlib
P = load(); U = P['member']; c = P['ac']; ao = P['ao']; cal = c.index; px = P['px']
hs, psh = cost_parts(P)
on = (ao / c.shift(1) - 1); on = on.where(on.abs() < 0.5)
days = pd.Series(cal, index=cal).diff().dt.days.fillna(1)
def run(K=5, LB=252, pmin=30, account=None, lev=1.0, extra=0.0, score=None, cfd=False, cost_mult=1.0):
    s = score if score is not None else on.rolling(LB, min_periods=LB // 2).mean()
    Wd = (topk(s, U & (px > pmin), K, True) / K * lev).shift(1).fillna(0)
    g = (Wd * on.fillna(0)).sum(axis=1)
    per = psh if not cfd else (0.005 / px.shift(1)).fillna(1e-4)
    mn = 0.35 if not cfd else 1.0
    com = Wd * per
    if account is not None: com = np.maximum(com, mn / account).where(Wd > 0, 0)
    cc = (com * 2 + Wd * 2 * extra).sum(axis=1) * cost_mult
    L = Wd.sum(axis=1)
    fin = ((L - 1).clip(lower=0) if not cfd else L) * (P['rf'] + 0.015 / 252) * days
    return (g - cc - fin).loc[START:END], g.loc[START:END]
base, gross = run()
rows = [stats(base, 'NOTTE K5 LB252 p>30 (asta, conto grande, 1x)')]
# placebo: 5 titoli piu' volatili (60g) tenuti di notte; 5 a caso
vol60 = P['ret'].rolling(60, min_periods=40).std()
rows.append(stats(run(score=vol60)[0], 'placebo: 5 piu\' volatili, di notte'))
rng = np.random.default_rng(3); rnd = pd.DataFrame(rng.random(c.shape), index=cal, columns=c.columns).rolling(252, min_periods=1).mean()
rows.append(stats(run(score=rnd)[0], 'placebo: 5 a caso (stabili), di notte'))
mom = c / c.shift(252) - 1
rows.append(stats(run(score=mom)[0], 'placebo: 5 con momentum 12m piu\' alto, di notte'))
intr_s = (c / ao - 1).rolling(252, min_periods=126).mean()
rows.append(stats(run(score=-intr_s)[0], 'variante: 5 con intraday medio piu\' BASSO, di notte'))
# copertura: short SPY di notte (beta stimato su 252 giorni precedenti), costo 1 bp per lato
spy = st.get('v6_b5_yahoo_1d_SPY'); spy = spy[~spy.index.duplicated()].reindex(cal); k = spy['adj'] / spy['close']
spy_on = (spy['open'] * k / spy['adj'].shift(1) - 1).loc[START:END]
beta = (gross.rolling(252).cov(spy_on) / spy_on.rolling(252).var()).shift(1).fillna(1.0).clip(0, 3)
hed = base - beta * spy_on - beta * 2e-4
rows.append(stats(hed, 'NOTTE coperta con SPY/MES di notte (beta mobile)')); rows.append(stats(spy_on, 'SPY solo notte (lordo)'))
rows.append(stats(base.loc['2018':], 'NOTTE dal 2018 (copertura universo >=85%)'))
print(fmt(rows)); print('beta medio verso SPY notte: %.2f' % beta.loc['2006':].mean())
print('================ conto piccolo e leva (azioni a margine <=2x; CFD su azioni <=5x: IPOTESI che MOC/MOO siano disponibili sui CFD)')
rows = []; S = {}
for lab_, kw in (('10k EUR azioni 1x', dict(account=11500)), ('10k EUR azioni 1.5x', dict(account=11500, lev=1.5)), ('10k EUR azioni 2x', dict(account=11500, lev=2)),
                 ('10k EUR CFD 3x', dict(account=11500, lev=3, cfd=True)), ('10k EUR CFD 5x', dict(account=11500, lev=5, cfd=True)),
                 ('10k EUR azioni 2x, +1bp per lato', dict(account=11500, lev=2, extra=1e-4)), ('10k EUR azioni 2x, costi x2', dict(account=11500, lev=2, cost_mult=2)),
                 ('10k EUR azioni 2x, K10', dict(account=11500, lev=2, K=10))):
    x = run(**kw)[0]; S[lab_] = x; d = stats(x, lab_); m = (1 + x).resample('ME').prod() - 1
    d['mese_comp%'] = round(((1 + x).prod() ** (21 / len(x)) - 1) * 100, 2); d['mese_mediano%'] = round(m.median() * 100, 2); d['mesi<0'] = round((m < 0).mean(), 2)
    d['P(-50%)3a'] = boot_p50(x)[0]; d['P(-50%)3a_meta_edge'] = boot_p50(x, edge_mult=0.5)[0]; rows.append(d)
print(fmt(rows))
print('================ leva che massimizza la crescita geometrica (conto 10k EUR, azioni fino a 2x poi CFD), griglia 0.5..8')
best = (0, -9, None)
for L in np.arange(0.5, 8.01, 0.5):
    x = run(account=11500, lev=L, cfd=(L > 2))[0]
    if (x <= -1).any(): print(f'  leva {L}: rovina (una notte <= -100%)'); break
    g = np.log1p(x).mean() * 252; eq = (1 + x).cumprod(); print(f'  leva {L:3.1f}: crescita log {g:5.2f}/anno -> {np.expm1(g/12)*100:5.1f}%/mese composto, max drawdown {((eq/eq.cummax())-1).min()*100:5.0f}%, peggior notte {x.min()*100:5.1f}%')
    if g > best[1]: best = (L, g, x)
Ls = best[0]; print(f'leva ottima (in campione, tutto il periodo): {Ls}x -> {np.expm1(best[1]/12)*100:.1f}%/mese; meta\' leva {Ls/2}x:')
for L in (Ls, Ls / 2):
    x = run(account=11500, lev=L, cfd=(L > 2))[0]
    for em in (1.0, 0.5):
        p, mm = boot_p50(x, edge_mult=em); print(f'  leva {L}: edge x{em}: P(-50% in 3 anni) = {p:.2f}, mese composto mediano bootstrap {mm*100:.1f}%')
xs, xv = best[2].loc[:SPLIT], best[2].loc['2023':]
print('  alla leva ottima: selezione %.1f%%/mese, verifica %.1f%%/mese' % (np.expm1(np.log1p(xs).mean() * 21) * 100, np.expm1(np.log1p(xv).mean() * 21) * 100))
print('================ correlazione col fondo esistente (giornaliera, mensile) dal 2018-04')
print('NOTTE 1x:', corr_fund(base)); print('NOTTE coperta:', corr_fund(hed))
f = fund(); xx = base.reindex(f.index).fillna(0.0).loc['2018-04-01':]; ff = f.loc['2018-04-01':]
for col in ff.columns:
    a = ff[col]; comb = 0.5 * a + 0.5 * xx
    sh = lambda z: z.mean() / z.std() * np.sqrt(365)
    print(f'  {col}: Sharpe fondo {sh(a):.2f}, NOTTE {sh(xx):.2f}, 50/50 {sh(comb):.2f}')
print('================ conto minimo: ordini/anno e commissione minima (0.35 $/ordine) su 10k EUR; soglia = conto oltre il quale il minimo non morde')
tests = {}
sp = importlib.util
def weights_of(script_ns): pass
r = P['ret']
s5 = -sector_demean(c / c.shift(5) - 1, P, U)
Wrev = (topk(s5, U, 20, True) / 20).rolling(5, min_periods=1).sum() / 5 - (topk(s5, U, 20, False) / 20).rolling(5, min_periods=1).sum() / 5
me = pd.Series(cal, index=cal).groupby([cal.year, cal.month]).last().values
m12 = c.shift(21) / c.shift(252) - 1
def monthly(sc, K, largest=True):
    W = pd.DataFrame(np.nan, index=cal, columns=c.columns)
    for d in me: W.loc[d] = (topk(sc.loc[[d]], U.loc[[d]], K, largest).iloc[0] / K)
    return W.ffill().fillna(0)
Wmom = monthly(m12, 20) - monthly(m12, 20, False)
Wlv = monthly(-r.rolling(252, min_periods=126).std(), 20)
medpx = px.where(U).loc['2023':].stack().median(); thr_order = 0.35 / (0.0065 / medpx)
print(f'prezzo mediano reale 2023-26: {medpx:.0f} $ -> il minimo di 0.35 $ smette di mordere per ordini >= {thr_order:.0f} $ (54 azioni)')
rows = []
for nm, W, npos in (('inversione 5g K20 LS (tenuta 5g)', Wrev, 200), ('momentum 12-1 K20 LS mensile', Wmom, 40), ('bassa vol K20 LO mensile', Wlv, 20)):
    big = run_weights(P, W); sm = run_weights(P, W, account=11500)
    rows.append(dict(strategia=nm, ordini_anno=round(sm['n_ord'].mean() * 252), comm_10k_pct_anno=round(sm['com'].mean() * 25200, 1), comm_conto_grande_pct=round(big['com'].mean() * 25200, 2),
                     lordo_pct_anno=round(big['gross'].mean() * 25200, 1), conto_minimo_usd=round(thr_order * npos / 1000) * 1000))
rows.append(dict(strategia='NOTTE K5 (10 ordini al giorno)', ordini_anno=2520, comm_10k_pct_anno=round((gross - run(account=11500)[0]).mean() * 25200, 1), comm_conto_grande_pct=round((gross - base).mean() * 25200, 2),
                 lordo_pct_anno=round(gross.mean() * 25200, 1), conto_minimo_usd=round(thr_order * 5 / 1000) * 1000))
print(pd.DataFrame(rows).to_string(index=False))
# ---------------- returns.parquet: rendimenti giornalieri netti non a leva, indice di calendario
out = pd.DataFrame({'notte_K5_asta_conto_grande': base, 'notte_K5_asta_10kEUR_1x': run(account=11500)[0], 'notte_K10_asta_10kEUR_1x': run(K=10, account=11500)[0],
                    'notte_K5_coperta_SPY': hed,
                    'rev5_K20_H5_LS': run_weights(P, Wrev)['net'], 'mom12_1_K20_LS': run_weights(P, Wmom)['net'], 'lowvol_K20_LO': run_weights(P, Wlv)['net']})
out = out.reindex(pd.date_range(out.index[0], out.index[-1], freq='D')).fillna(0.0); out.to_parquet(D + 'returns.parquet')
print('returns.parquet:', out.shape, list(out.columns))
tot = sum(len(json.load(open(D + f))) for f in os.listdir(D) if f.startswith('trials_')) + 5 + 8 + 16
print('VARIANTI TOTALI B5:', tot)
