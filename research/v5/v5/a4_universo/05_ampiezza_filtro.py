"""A4 - l'ampiezza usata come FILTRO (non come fonte di trade): si entra sui maggiori con conviction alta solo se la quota di
membri del top-30 con conviction alta, nota la sera prima, e' sotto una soglia. Soglie = terzili di selezione (0,375 e 0,633). SIMULATO."""
import sys, pickle; sys.path.insert(0, '/home/user/GERVA-Capital/research/v5/v5/a4_universo')
from lab import *
pd.set_option('display.width', 300); pd.set_option('display.max_columns', 50)
U, RANK = load_all(30); TRIO = ('BTCUSDT', 'ETHUSDT', 'SOLUSDT'); nvar = 0
num = pd.DataFrame({s: pd.Series((o.tier == 'alta') & (o.rank <= 30), index=o.days).reindex(CAL) for s, o in U.items()}).fillna(False).astype(float).sum(axis=1)
den = pd.DataFrame({s: pd.Series(o.rank <= 30, index=o.days).reindex(CAL) for s, o in U.items()}).fillna(False).astype(float).sum(axis=1).replace(0, np.nan)
AMP = num / den
def sig(thr=None, topn=None, only=None, lo=None):
    ent, ext = {}, {}
    for s, o in U.items():
        if only is not None and s not in only: continue
        e = (o.tier == 'alta') & ((o.rank <= topn) if topn else True); a = AMP.reindex(o.days).values
        if thr is not None: e = e & (a <= thr)
        if lo is not None: e = e & (a > lo)
        ent[s] = e; ext[s] = (o.tier == 'bassa')
    return ent, ext
rows = []; KEEP = {}
for name, kw in (('trio', dict(only=TRIO)), ('top3 pit', dict(topn=3)), ('top5 pit', dict(topn=5)), ('top10 pit', dict(topn=10)), ('top30 pit', dict(topn=30))):
    for lab, k2 in (('nessun filtro', {}), ('ampiezza <= 0,633', dict(thr=0.633)), ('ampiezza <= 0,375', dict(thr=0.375)), ('ampiezza > 0,633 (lo scarto)', dict(lo=0.633))):
        T, M = run(U, *sig(**kw, **k2)); KEEP[f'{name} {lab}'] = (T, M); rows.append(row(f'{name} {lab}', T, M))
        if lab.startswith('ampiezza <') and name in ('trio', 'top30 pit'): nvar += 1
R = pd.DataFrame(rows).set_index('cfg')
print(R[['n', 'R', 't', 'hit', 'R_sc', 't_sc', 'n_sc', 'R_ver', 't_ver', 'n_ver', 'N', 'sR', 'Neff', 'K', 'K_sc', 'K_ver', 'rho']].round(3).to_string())
print('\n== trio, ampiezza <= 0,633: robustezza ==')
rb = []
for lab, k2 in (('base', {}), ('costi x2', dict(cost_mult=2.0)), ('ritardo +1h', dict(delay=1)), ('tetto 10x', dict(cap=10.0)), ('stop 2xATR', dict(atr_k=2.0))):
    T, M = run(U, *sig(0.633, only=TRIO), **k2); rb.append(row(lab, T, M))
print(pd.DataFrame(rb).set_index('cfg')[['n', 'R', 't', 'hit', 'R_sc', 't_sc', 'R_ver', 't_ver', 'N', 'sR', 'Neff', 'K', 'K_sc', 'K_ver']].round(3).to_string())
T, M = KEEP['trio ampiezza <= 0,633']; print('\nper anno (trio, ampiezza <= 0,633):'); print(per_year(T).round(3).T.to_string())
T2 = KEEP['trio ampiezza > 0,633 (lo scarto)'][0]; print('per anno (trio, lo scarto: ampiezza > 0,633):'); print(per_year(T2).round(3).T.to_string())
print('\nsensibilita\' alla soglia (trio; solo descrittivo, la soglia resta il terzile di selezione):')
for thr in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
    t, m = run(U, *sig(thr, only=TRIO), pnl=False); a = t[t.entry < SPLIT]; b = t[t.entry >= SPLIT]
    print(f'  <= {thr:.1f}: n {len(t):4d}  R scelta {a.R.mean():+.3f} (n {len(a)})  R verifica {b.R.mean():+.3f} (n {len(b)})')
print('\nl\'ampiezza e\' solo un altro modo di dire "punteggio della moneta"? R medio per punteggio di conviction della moneta e fascia di ampiezza (trio, tutto il periodo):')
T0 = KEEP['trio nessun filtro'][0].copy(); T0['amp'] = AMP.reindex(T0.entry).values; T0['f'] = np.where(T0.amp <= 0.375, '1 bassa', np.where(T0.amp <= 0.633, '2 media', '3 alta'))
T0['sc'] = pd.cut(T0.score, [0.6, 0.7, 0.8, 1.0]); g = T0.groupby(['sc', 'f'])['R']; print(pd.DataFrame(dict(n=g.count(), R=g.mean())).round(3).unstack().to_string())
print('giorni l\'anno con ampiezza <= 0,633:', (AMP.loc['2021':] <= 0.633).groupby(AMP.loc['2021':].index.year).mean().round(2).to_dict())
# aggiunge ai file di consegna
r = pd.read_parquet(HERE + 'returns.parquet'); r['trio_filtro_ampiezza_0633'] = M.sum(axis=1) * 0.01; r.to_parquet(HERE + 'returns.parquet')
tt = pd.read_parquet(HERE + 'trades.parquet'); tt = tt[tt.book != 'trio_filtro_ampiezza_0633']
x = T.rename(columns={'stop': 'stop_distance', 'lev': 'leverage'}).assign(book='trio_filtro_ampiezza_0633'); pd.concat([tt, x[tt.columns]]).to_parquet(HERE + 'trades.parquet')
print('\nvarianti nuove contate qui:', nvar, '(le due soglie sul trio erano gia\' contate in 04; qui si aggiungono le due sul top-30)')
