"""A3/6 - (a) lo stop stretto migliora o peggiora R/sigma? sweep della larghezza dello stop sulla rottura a 7 giorni long;
(b) lato short e monete fuori dal libro del candidato A; (c) Sharpe^2 combinato ottimo con trade11 / C3 (= N(R/sig)^2 del BRIEF);
(d) salvataggio di returns.parquet e trades.parquet. SIMULATO."""
from lab import *
import importlib, pickle
D1 = importlib.import_module('01_donchian'); C5 = importlib.import_module('05_candidati')
tr = Trials('finale')
def sh(d): return d.mean() / d.std() * np.sqrt(365) if d.std() > 0 else np.nan
print('== (a) rottura massimo 7 giorni, LONG, trailing 6R, 72h: larghezza dello stop')
rows = []
for k in (0.75, 1.5, 3.0, 6.0, 12.0):
    T = runall(C5.brk(2016, k, side=1), smax=0.20, trail_R=6.0, maxhold=864, smin=0.001)
    if k in (0.75, 12.0): tr.add(T, f'sweep k={k}')
    a = stats(T, f'stop {k} x vol oraria'); a['costo_R'] = (2 * FEE / T.stop).mean(); rows.append(a)
show(pd.DataFrame(rows), cols=['cfg', 'n', 'stop_med', 'lev_med', 'costo_R', 'R', 'hit', 'RsuSig', 'R_sel', 'sh_sel', 'R_ver', 'sh_ver'], sort=None)
print('\n== (a2) Donchian 4h N=100 trailing 4R: larghezza dello stop')
rows = []
for k in (0.5, 1.0, 2.0, 4.0):
    T = runall(D1.mk('4h', 100, k), maxhold=48 * 48, smax=0.25, trail_R=4.0)
    if k in (0.5, 4.0): tr.add(T, f'sweep don k={k}')
    a = stats(T, f'stop {k} x ATR(4h)'); a['costo_R'] = (2 * FEE / T.stop).mean(); rows.append(a)
show(pd.DataFrame(rows), cols=['cfg', 'n', 'stop_med', 'lev_med', 'costo_R', 'R', 'hit', 'RsuSig', 'R_sel', 'sh_sel', 'R_ver', 'sh_ver'], sort=None)

K = pickle.load(open('cand_trades.pkl', 'rb')); A = K['A_DON4h']; B = book()['F']
print('\n== (b) candidato A scomposto')
parts = {'A tutto': A, 'A solo short': A[A.side == -1], 'A solo long': A[A.side == 1], 'A solo 7 monete fuori dal libro': A[~A.symbol.isin(['BTC', 'ETH', 'SOL'])],
         'A fuori dai giorni del libro': A[~A.entry.dt.normalize().isin(book()['days'])], 'A nei giorni del libro': A[A.entry.dt.normalize().isin(book()['days'])]}
mm = lambda x: (1 + x).resample('ME').prod() - 1
def comb2(x, y):
    """Sharpe^2 massimo della combinazione di due serie giornaliere."""
    m = np.array([x.mean(), y.mean()]) * 365; S = np.cov(np.vstack([x.values, y.values])) * 365
    return float(m @ np.linalg.solve(S, m))
for nm, T in parts.items():
    d = daily(T, 0.01); f = B.reindex(d.index).fillna(0.0); a = stats(T, nm)
    line = '%-32s n=%4d R_sel %.3f tg %.2f | R_ver %.3f tg %.2f | corr mese trade11 %.2f' % (nm, len(T), a['R_sel'], a['tg_sel'], a['R_ver'], a['tg_ver'], mm(d).corr(mm(f['trade11'])))
    for pn, sl in (('SCELTA', slice('2020-01-01', '2022-12-31')), ('VERIFICA', slice('2023-01-01', '2026-10-31'))):
        y = d[sl]; t11 = f.loc[y.index, 'trade11']; c3 = f.loc[y.index, 'C3'] - f.loc[y.index, 'rf']
        line += ' | %s Sh %.2f; Sh^2: trade11 %.2f -> +cand %.2f; C3 %.2f -> +cand %.2f' % (pn, sh(y), sh(t11) ** 2, comb2(t11, y), sh(c3) ** 2, comb2(c3, y))
    print(line)
print('  (Sh^2 della combinazione ottima ex-post: e\' un tetto, non una stima; in VERIFICA i pesi ottimi sono scelti sugli stessi dati)')
# pesi scelti in SCELTA, applicati in VERIFICA (onesto)
for nm in ('A tutto', 'A solo short', 'A fuori dai giorni del libro'):
    d = daily(parts[nm], 0.01); f = B.reindex(d.index).fillna(0.0); c3 = f['C3'] - f['rf']
    s = slice('2020-01-01', '2022-12-31'); v = slice('2023-01-01', '2026-10-31')
    m = np.array([c3[s].mean(), d[s].mean()]); S = np.cov(np.vstack([c3[s].values, d[s].values])); w = np.linalg.solve(S, m); w = w / w[0]
    print('  pesi da SCELTA (C3=1, %s=%.2f x rischio 1%%): VERIFICA Sharpe C3 %.2f -> %.2f ; Sharpe^2 %.2f -> %.2f' % (nm, w[1], sh(c3[v]), sh(c3[v] + w[1] * d[v]), sh(c3[v]) ** 2, sh(c3[v] + w[1] * d[v]) ** 2))
# Kelly del candidato A da solo
d = daily(A, 0.01)
for pn, sl in (('SCELTA', slice('2020-01-01', '2022-12-31')), ('VERIFICA', slice('2023-01-01', '2026-10-31'))):
    y = d[sl]; fk = y.mean() / y.var(); g = lambda r: np.log1p(np.maximum(r * y / 0.01, -0.99)).sum() / len(y) * 365
    print('  Kelly A %s: rischio/trade ottimo ~ %.2f%%; crescita log/anno a Kelly pieno %.2f, a mezzo Kelly %.2f (obiettivo 3.15); mese mediano a mezzo Kelly %.1f%%' % (
        pn, fk, g(0.01 * fk), g(0.005 * fk), 100 * ((1 + (0.5 * fk) * y).resample('ME').prod() - 1).median()))
tr.save()
# (d) deliverable
RISK = 0.005
R = pd.DataFrame({'A_don4h_100_2atr_trail4': daily(A, RISK), 'A_solo_short': daily(A[A.side == -1], RISK), 'D_long_7g_stop3hv': daily(K['D_LONG_tight'], RISK)})
R.to_parquet('returns.parquet'); print('\nreturns.parquet: rischio per trade %.2f%%, colonne %s' % (100 * RISK, list(R.columns)))
T = pd.concat([K[k].assign(candidato=k) for k in ('A_DON4h', 'D_LONG_tight')], ignore_index=True).rename(columns={'stop': 'stop_dist', 'lev': 'leverage'})
T.to_parquet('trades.parquet'); print('trades.parquet:', T.shape)
import glob
tot = {os.path.basename(f): json.load(open(f))['n'] for f in sorted(glob.glob('trials_*.json'))}; print('varianti per file:', tot, 'TOTALE', sum(tot.values()))
