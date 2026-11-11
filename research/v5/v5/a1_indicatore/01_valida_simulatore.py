"""A1 - il simulatore riscritto deve dare gli STESSI trade dell'originale (leva_trade_isolato.trades). SIMULATO."""
import lib, numpy as np, pandas as pd, time
import leva_trade_isolato as L
t0 = time.time()
for c in ('BTC', 'ETH', 'SOL'):
    P = lib.Path(L.B[c], L.fund(c)); tier = L.CONV[c]['tier'].values
    for nm, kwo, kwn in (('C 1xATR trail2', dict(s=0, atr_k=1.0, trail=2.0), dict(atr_k=1.0, trail=2.0)),
                         ('A 1,7% no trail', dict(s=0.017, trail=None), dict(s=0.017, atr_k=None, trail=None))):
        O = L.trades(c, tiers=('alta',), **kwo); N = P.book(tier == 'alta', tier == 'bassa', **kwn)
        same = len(O) == len(N) and (O.entry.values == N.entry.values).all() and np.allclose(O.R.values, N.R.values, atol=1e-9)
        print(f'{c} {nm}: originale n={len(O)} R={O.R.mean():+.4f} | riscritto n={len(N)} R={N.R.mean():+.4f} | identici={same} maxdiff={np.abs(O.R.values-N.R.values).max() if len(O)==len(N) else np.nan:.2e}')
print('secondi', round(time.time() - t0, 1))
