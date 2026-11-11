"""A3/1 - Donchian a 1h e 4h con stop ATR. SIMULATO. Piu' controllo di sanita': ingressi casuali -> R medio ~ -costo/stop."""
from lab import *
tr = Trials('donchian')
F = {}
def feat(c, b, rule):
    k = (c, rule)
    if k not in F:
        a = agg(b, rule); a['atr'] = atr(a, 14); F[k] = a
    return F[k]
def mk(rule, N, k, side=0):
    def fn(c, b):
        a = feat(c, b, rule)
        hh = a['high'].rolling(N).max().shift(1); ll = a['low'].rolling(N).min().shift(1)
        s = pd.Series(0, index=a.index, dtype='int8'); s[a['close'] > hh] = 1; s[a['close'] < ll] = -1
        if side: s[s != side] = 0
        sig = to5(s, b).fillna(0).astype('int8').values
        spx = to5(a['close'] - s * k * a['atr'], b).values
        return sig, spx
    return fn
if __name__ == '__main__':
    # sanita': ingressi casuali, stop 1%, uscita dopo 24 barre
    rng = np.random.default_rng(0)
    def rnd(c, b):
        s = np.zeros(len(b), 'int8'); i = rng.integers(0, len(b), 4000); s[i] = rng.choice([-1, 1], 4000)
        return s, b['close'].values * (1 - s * 0.01)
    T = runall(rnd, maxhold=24); print('SANITA casuale stop 1%%: n=%d R=%.3f (atteso ~ -0.13..-0.15) hit=%.2f' % (len(T), T.R.mean(), (T.R > 0).mean()))
    T0 = runall(rnd, maxhold=24, cost=0.0); print('SANITA casuale costo 0: R=%.3f (atteso ~0)' % T0.R.mean())
    for rule in ('1h', '4h'):
        for N in (20, 50, 100):
            for k in (1.0, 2.0):
                for ex in ('trail2', 'trail4', 'time'):
                    mh = {'1h': 12 * 48, '4h': 48 * 48}[rule]
                    kw = dict(trail_R=2.0) if ex == 'trail2' else dict(trail_R=4.0) if ex == 'trail4' else {}
                    T = runall(mk(rule, N, k), maxhold=mh if ex != 'time' else mh // 4, smax=0.10, **kw)
                    tr.add(T, f'DON {rule} N={N} stop={k}ATR {ex}', fam='don', rule=rule, N=N, k=k, ex=ex)
    show(tr.table()); tr.save(); tr.table().to_parquet('res_donchian.parquet')
    print('varianti:', len(tr.rows))
