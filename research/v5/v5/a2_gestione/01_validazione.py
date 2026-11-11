"""Verifica del motore: (1) deve riprodurre research/v5/v4/leva_trade_isolato.py trade per trade (a funding zero, che e' l'unica differenza
di convenzione); (2) controllo di troncamento della conviction; (3) effetto della convenzione del funding."""
import numpy as np, pandas as pd, engine as G
from engine import params, book, LTI
pd.set_option('display.width', 250)
print('== 1. confronto con il simulatore originale (funding azzerato in entrambi) ==')
of = LTI.fund; LTI.fund = lambda c: None
def orig(s, **kw): return pd.concat([LTI.trades(c, s, **kw) for c in G.COINS], ignore_index=True)
for s, kw_o, kw_n, lab in [(0.017, {}, dict(sd=0.017), 'stop 1,7% senza trailing'),
                           (0.017, dict(trail=2.0), dict(sd=0.017, tmode=1, tm=2.0), 'stop 1,7% trail 2'),
                           (0, dict(atr_k=1.0, trail=2.0), dict(atr_k=1.0, tmode=1, tm=2.0), 'stop 1xATR trail 2'),
                           (0.06, dict(tp=2.0), dict(sd=0.06, tp=2.0), 'stop 6% obiettivo 2R'),
                           (0.004, {}, dict(sd=0.004), 'stop 0,4% senza trailing')]:
    A = orig(s, **kw_o).sort_values(['coin', 'entry']).reset_index(drop=True)
    Bk = book(params(**kw_n), usefund=False).sort_values(['coin', 'entry']).reset_index(drop=True)
    same_n = len(A) == len(Bk)
    md = np.abs(A.R.values - Bk.R.values).max() if same_n else np.nan
    print(f'{lab:28s} n orig {len(A):5d} n nuovo {len(Bk):5d}  R medio orig {A.R.mean():+.5f} nuovo {Bk.R.mean():+.5f}  max|dR| {md:.2e}')
LTI.fund = of
print('\n== 2. effetto della convenzione del funding (originale: somma giornaliera per giorno di calendario; nuovo: pagamenti reali alle 00/08/16 mentre si e\' dentro) ==')
for s, kw_o, kw_n, lab in [(0.017, {}, dict(sd=0.017), 'stop 1,7% senza trailing'), (0, dict(atr_k=1.0, trail=2.0), dict(atr_k=1.0, tmode=1, tm=2.0), 'stop 1xATR trail 2')]:
    A = orig(s, **kw_o); Bk = book(params(**kw_n))
    print(f'{lab:28s} R medio orig {A.R.mean():+.4f} (scelta {A[A.entry<"2023"].R.mean():+.4f} verifica {A[A.entry>="2023"].R.mean():+.4f})  nuovo {Bk.R.mean():+.4f} (scelta {Bk[Bk.entry<"2023"].R.mean():+.4f} verifica {Bk[Bk.entry>="2023"].R.mean():+.4f})')
print('\n== 3. troncamento: conviction ricalcolata su dati tagliati a t (deve essere identica) ==')
from gerva import ensemble as E
rng = np.random.default_rng(0); bad = 0; tot = 0
for c in G.COINS:
    d = LTI.D[c]; f = LTI.fund(c); full = LTI.CONV[c]
    for t in rng.choice(np.arange(400, len(d) - 1), 40, replace=False):
        dc = d.iloc[:t]                                            # dati fino al giorno t-1 compreso
        F = E.crypto_signals(dc, LTI.D['BTC']['close'].loc[:dc.index[-1]], None if f is None else f.loc[:dc.index[-1]])
        cv = E.conviction(F, 'crypto').iloc[-1]                    # conviction del giorno t-1 = segnale usato all'apertura di t
        ref = full.iloc[t]; tot += 1
        if cv['tier'] != ref['tier'] or not (np.isclose(cv['score'], ref['score']) or (np.isnan(cv['score']) and np.isnan(ref['score']))): bad += 1
print(f'date controllate {tot}, differenze {bad}')
q = G.PREP['BTC']; k = 500000
import numpy as np
b = LTI.B['BTC']; j0 = q['start'][q['dayidx'][k]]
tp_ = ((b.high + b.low + b.close) / 3).values; v = b.volume.values
print('VWAP alla barra k usa solo barre < k:', np.isclose(q['vw'][k], (tp_[j0:k] * v[j0:k]).sum() / v[j0:k].sum()))
