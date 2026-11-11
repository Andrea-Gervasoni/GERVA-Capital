"""A3/5 - i pochi candidati non negativi: robustezza (costi x2, ritardo), per anno, per simbolo, troncamento,
sovrapposizione con il libro dei trade 11x (trade11) e contributo marginale. SIMULATO."""
from lab import *
import importlib
D1 = importlib.import_module('01_donchian')
def hvf(b):
    lr = np.log(b['close']).diff(); hv = lr.rolling(288).std() * np.sqrt(12); return hv
def brk(N, k, side=0, q=None):
    """prima chiusura 5m oltre il massimo/minimo a N barre; stop = k x vol oraria; q = filtro percentile vol 30g."""
    def fn(c, b):
        hv = hvf(b); cl = b['close']
        hh = b['high'].rolling(N).max().shift(1); ll = b['low'].rolling(N).min().shift(1)
        s = np.zeros(len(b), 'int8'); s[(cl > hh).values] = 1; s[(cl < ll).values] = -1
        if q is not None: s[~(hv.rolling(8640).rank(pct=True) < q).values] = 0
        if side: s[s != side] = 0
        return s, cl.values * (1 - s * k * hv.values)
    return fn
def trunc_check(fn, c='ETH', npts=25, seed=1):
    b = load(c); s, x = fn(c, b)[:2]; rng = np.random.default_rng(seed); nz = np.flatnonzero(s != 0)
    pts = np.concatenate([rng.choice(nz, npts // 2), rng.integers(60000, len(b) - 1, npts - npts // 2)]); bad = 0
    for t in pts:
        bb = b.iloc[max(0, t - 60000):t + 1]; s2, x2 = fn(c, bb)[:2]
        if s2[-1] != s[t] or (s[t] != 0 and abs(x2[-1] / x[t] - 1) > 1e-9): bad += 1
    return bad, len(pts)
def sharpe(d): return d.mean() / d.std() * np.sqrt(365) if d.std() > 0 else np.nan
def full(name, fn, kw, tr, risk=0.01):
    print(f'\n######## {name}   {kw}')
    T = runall(fn, **kw); r = tr.add(T, name)
    T2 = runall(fn, cost=2.0, **kw); Td = runall(fn, delay=1, **kw)
    for lab_, X in (('base', T), ('costi x2', T2), ('ritardo +1 barra', Td)):
        a = stats(X, lab_); print('  %-17s n=%5d n/anno=%4.0f stop med=%.2f%% leva med=%.0fx | R=%.3f t=%.2f t_giorni=%.2f hit=%.2f R/sig=%.3f | SCELTA R=%.3f t_g=%.2f sh=%.2f | VERIFICA R=%.3f t_g=%.2f sh=%.2f' % (
            lab_, a['n'], a['n_anno'], 100 * a['stop_med'], a['lev_med'], a['R'], a['t'], a['t_g'], a['hit'], a['RsuSig'], a['R_sel'], a['tg_sel'], a['sh_sel'], a['R_ver'], a['tg_ver'], a['sh_ver']))
    print('  per anno (R medio, n):', peryear(T))
    print('  per lato:', {int(k): (round(g.R.mean(), 3), round(g.R[g.entry < SPLIT].mean(), 3), round(g.R[g.entry >= SPLIT].mean(), 3), len(g)) for k, g in T.groupby('side')}, ' (tutto, scelta, verifica, n)')
    print('  per simbolo (R scelta | R verifica):', {c: (round(g.R[g.entry < SPLIT].mean(), 2), round(g.R[g.entry >= SPLIT].mean(), 2)) for c, g in T.groupby('symbol')})
    print('  uscite:', T.why.value_counts(normalize=True).round(2).to_dict(), ' R peggiore %.2f  R migliore %.1f' % (T.R.min(), T.R.max()))
    bad, npt = trunc_check(fn); print(f'  troncamento: {bad} differenze su {npt} punti')
    ov = overlap(T, risk); print('  sovrapposizione col libro 11x:', {k: round(v, 3) for k, v in ov.items()})
    # contributo marginale: regressione giornaliera su trade11 e new
    B = book()['F']; d = daily(T, risk); X = B.reindex(d.index).fillna(0.0)
    for nm, sl in (('scelta', slice('2020-01-01', '2022-12-31')), ('verifica', slice('2023-01-01', '2026-10-31'))):
        y = d[sl]; Z = np.column_stack([np.ones(len(y)), X.loc[y.index, 'trade11'].values, X.loc[y.index, 'new'].values])
        be, *_ = np.linalg.lstsq(Z, y.values, rcond=None); e = y.values - Z @ be; se = np.sqrt(np.diag(np.linalg.inv(Z.T @ Z)) * e.var(ddof=3))
        s11 = sharpe(X.loc[y.index, 'trade11']); sc = sharpe(X.loc[y.index, 'trade11'] + y); sC3 = sharpe(X.loc[y.index, 'C3']); sC3c = sharpe(X.loc[y.index, 'C3'] + y)
        print('  %-8s Sharpe candidato %.2f (Sharpe^2 = N(R/sig)^2 ~ %.2f) | alfa/anno %.1f%% t=%.2f beta trade11 %.2f beta new %.2f | Sharpe trade11 %.2f -> con candidato %.2f | Sharpe C3 %.2f -> con candidato %.2f' % (
            nm, sharpe(y), max(sharpe(y), 0) ** 2, 365 * 100 * be[0], be[0] / se[0], be[1], be[2], s11, sc, sC3, sC3c))
    alt = T[~T.symbol.isin(['BTC', 'ETH', 'SOL'])]; maj = T[T.symbol.isin(['BTC', 'ETH', 'SOL'])]
    print('  BTC/ETH/SOL: R_sel %.3f R_ver %.3f n %d | altri 7: R_sel %.3f R_ver %.3f n %d' % (maj.R[maj.entry < SPLIT].mean(), maj.R[maj.entry >= SPLIT].mean(), len(maj), alt.R[alt.entry < SPLIT].mean(), alt.R[alt.entry >= SPLIT].mean(), len(alt)))
    return T
if __name__ == '__main__':
    tr = Trials('cand')
    # piccola griglia a priori: solo long (lo studio a eventi in SCELTA dice che gli short dopo rottura al ribasso perdono), senza filtro di regime
    g = []
    for N in (864, 2016, 8640):
        for k in (1.5, 3.0, 6.0):
            T = runall(brk(N, k, side=1), smax=0.10, trail_R=6.0, maxhold=864); g.append(tr.add(T, f'LONG rottura N={N} stop={k}hv trail6 72h', N=N, k=k))
    G = pd.DataFrame(g); print('== griglia LONG rottura (scelta su tg_sel)'); show(G)
    b = G.sort_values('tg_sel', ascending=False).iloc[0]
    K = {}
    K['A_DON4h'] = full('A. Donchian 4h N=100, stop 2 ATR(4h), trailing 4R, max 8 giorni (long+short)', D1.mk('4h', 100, 2.0), dict(maxhold=48 * 48, smax=0.10, trail_R=4.0), tr)
    K['B_SQR'] = full('B. rottura 7 giorni in vol compressa (hvr<0.4), stop 6 hv, trailing 6R, 72h (long+short)', brk(2016, 6.0, q=0.4), dict(smax=0.10, trail_R=6.0, maxhold=864), tr)
    K['C_LONG'] = full(f'C. {b.cfg} (migliore della griglia long in scelta)', brk(int(b.N), float(b.k), side=1), dict(smax=0.10, trail_R=6.0, maxhold=864), tr)
    K['D_LONG_tight'] = full('D. LONG rottura 7 giorni, stop 3 hv (~1,8%, ~28x), trailing 6R, 72h', brk(2016, 3.0, side=1), dict(smax=0.10, trail_R=6.0, maxhold=864), tr)
    import pickle; pickle.dump(K, open('cand_trades.pkl', 'wb')); tr.save(); print('\nvarianti:', len(tr.rows))
