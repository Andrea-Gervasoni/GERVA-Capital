"""A3/4 - rottura del range a N barre SOLO in regime di volatilita' compressa (percentile 30g della vol oraria), stop in multipli della vol.
Nasce dallo studio a eventi (03): l'unica cella con deriva lorda a 4h significativa in scelta. SIMULATO. Scelta solo su *_sel."""
from lab import *
F = {}
def feats(c, b):
    if c not in F:
        lr = np.log(b['close']).diff(); hv = lr.rolling(288).std() * np.sqrt(12); F[c] = (hv.values, hv.rolling(8640).rank(pct=True).values)
    return F[c]
def mk(N, q, k, side=0, qlo=0.0):
    def fn(c, b):
        hv, hvr = feats(c, b); cl = b['close']
        hh = b['high'].rolling(N).max().shift(1); ll = b['low'].rolling(N).min().shift(1)
        up = (cl > hh).values; dn = (cl < ll).values
        s = np.zeros(len(b), 'int8'); ok = (hvr < q) & (hvr >= qlo); s[up & ok] = 1; s[dn & ok] = -1
        if side: s[s != side] = 0
        return s, cl.values * (1 - s * k * hv)
    return fn
EXITS = {'trail3 24h': dict(trail_R=3.0, maxhold=288), 'trail6 72h': dict(trail_R=6.0, maxhold=864), 'tempo 4h': dict(maxhold=48), 'tempo 24h': dict(maxhold=288)}
if __name__ == '__main__':
    tr = Trials('sqzreg'); ALL = {}
    for N in (288, 864, 2016):
        for q in (0.2, 0.4):
            for k in (1.5, 3.0, 6.0):
                for en, ekw in EXITS.items():
                    T = runall(mk(N, q, k), smax=0.10, **ekw); lab_ = f'SQR N={N} hvr<{q} stop={k}hv {en}'
                    tr.add(T, lab_, N=N, q=q, k=k, ex=en); ALL[lab_] = T
    R = tr.table(); show(R, top=25); print('...'); show(R, top=None, sort='tg_sel', cols=COLS) if False else None
    R.to_parquet('res_sqzreg.parquet')
    best = R.sort_values('tg_sel', ascending=False).iloc[0]; print('\nMIGLIORE IN SCELTA:', best.cfg)
    T = ALL[best.cfg]
    print('per lato:'); print(T.groupby('side').apply(lambda g: pd.Series(dict(n=len(g), R=g.R.mean(), R_sel=g.R[g.entry < SPLIT].mean(), R_ver=g.R[g.entry >= SPLIT].mean()))).round(3))
    print('per anno (R medio, n):', peryear(T))
    # controllo: regime NON compresso con gli stessi parametri (la compressione aggiunge qualcosa?)
    for qlo, qhi in ((0.2, 0.5), (0.5, 0.8), (0.8, 1.01)):
        ekw = EXITS[best.ex]; T2 = runall(mk(int(best.N), qhi, float(best.k), qlo=qlo), smax=0.10, **ekw)
        r = tr.add(T2, f'controllo hvr in [{qlo},{qhi})'); print('controllo', r['cfg'], 'n', r['n'], 'R_sel %.3f tg_sel %.2f R_ver %.3f tg_ver %.2f' % (r['R_sel'], r['tg_sel'], r['R_ver'], r['tg_ver']))
    tr.save(); print('varianti:', len(tr.rows))
