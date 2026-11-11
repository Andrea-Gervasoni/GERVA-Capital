"""B5 (5) - notte contro giorno per titolo; e placebo per i flussi di trade long (quanta parte dell'R e' solo beta di mercato).
SIMULATO."""
from lab import *
P = load(); U = P['member']; c = P['ac']; ao = P['ao']; cal = c.index
hs, psh = cost_parts(P)
on = (ao / c.shift(1) - 1); on = on.where(on.abs() < 0.5)          # chiusura t-1 -> apertura t
intr = (c / ao - 1); intr = intr.where(intr.abs() < 0.5)
Um = U.shift(1).fillna(False)
a, b = on.where(Um).mean(axis=1).loc[START:], intr.where(Um).mean(axis=1).loc[START:]
print('media equipesata membri: notte %.1f%%/anno (Sharpe %.2f), giorno %.1f%%/anno (Sharpe %.2f)' % (a.mean() * 25200, a.mean() / a.std() * 252 ** .5, b.mean() * 25200, b.mean() / b.std() * 252 ** .5))
for p0, p1 in (('2005', '2009'), ('2010', '2014'), ('2015', '2019'), ('2020', '2022'), ('2023', '2026')):
    print(f'  {p0}-{p1}: notte {a.loc[p0:p1].mean()*25200:6.1f}%  giorno {b.loc[p0:p1].mean()*25200:6.1f}%')
rows = []; keep = {}
def run_on(W, lab_, com_only=False, account=None, legs=2):
    """W deciso prima della chiusura di t (usa notti fino a quella di t): compra in chiusura t, vende in apertura t+1. 2 lati al giorno."""
    Wd = W.shift(1).fillna(0)                              # in essere nella notte che finisce a t
    g = (Wd * on.fillna(0)).sum(axis=1)
    per = (psh if com_only else hs + psh)
    cc = (Wd.abs() * per * 2)
    if account is not None:
        com = np.maximum(Wd.abs() * psh, 0.35 / account).where(Wd.abs() > 0, 0) * 2
        cc = com + (0 if com_only else Wd.abs() * hs * 2)
    n = (g - cc.sum(axis=1) - (-Wd.clip(upper=0)).sum(axis=1) * 0.01 / 252).loc[START:END]
    d = stats(n, lab_); d['gross_sh'] = round(stats(g.loc[START:END])['sh'], 2); d['cost%yr'] = round(cc.sum(axis=1).loc[START:].mean() * 25200, 1); rows.append(d); keep[lab_] = n
n_tr = 0
for LB in (20, 60, 252):
    s = on.rolling(LB, min_periods=LB // 2).mean()
    for K in (10, 20):
        L = topk(s, U, K, True) / K; S = topk(s, U, K, False) / K
        run_on(L, f'notte top{K} LB{LB} LO: spread+commissione'); n_tr += 1
        if K == 20:
            run_on(L, f'notte top{K} LB{LB} LO: asta (solo commissione)', com_only=True)
            run_on(L, f'notte top{K} LB{LB} LO: asta, conto 10k EUR', com_only=True, account=11500)
            run_on(L - S, f'notte top-bottom{K} LB{LB} LS: asta', com_only=True)
print(fmt(rows))
print('per periodo, notte top20 LB60 LO asta:'); x = keep['notte top20 LB60 LO: asta (solo commissione)']
print(' | '.join(f'{p0}-{p1[2:]}: {x.loc[p0:p1].mean()*25200:5.1f}% sh {x.loc[p0:p1].mean()/x.loc[p0:p1].std()*252**.5:5.2f}' for p0, p1 in (('2005', '2009'), ('2010', '2014'), ('2015', '2019'), ('2020', '2022'), ('2023', '2026'))))
pd.to_pickle(keep, D + 'data/res_notte.pkl')
# ---------------- placebo dei flussi long: stessi giorni e stesso numero di trade, titoli a caso tra i membri
print('================ placebo: R dei trade long con titoli scelti a caso (stesse date, stesso numero, stesso stop e durata)')
tr = pd.read_parquet(D + 'trades.parquet'); A = atr(P); cost = hs + psh
rng = np.random.default_rng(7)
for nm, k, H in (('rev5 perdenti long', 2, 5), ('PEADproxy SU long', 2, 20), ('breakout52+volume long', 2, 20), ('breakout52+volume H60 3ATR', 3, 60), ('mom12-1 top20 mensile', 3, 21), ('lowvol top20 mensile', 3, 21)):
    t = tr[tr.stream == nm]; cnt = t.groupby('signal').size().reindex(cal).fillna(0).astype(int)
    Rp = []
    for rep in range(3):
        sv = np.zeros(c.shape, bool); Uv = U.values
        for i in np.flatnonzero(cnt.values):
            js = np.flatnonzero(Uv[i]); sv[i, rng.choice(js, min(cnt.values[i], len(js)), replace=False)] = True
        sig = pd.DataFrame(sv, index=cal, columns=c.columns)
        p = trades_R(P, sig, side=1, k_atr=k, hold=H, max_new=10 ** 6, cost=cost, atr_=A, lev=5, fin=0.045); Rp.append(p)
    pl = pd.concat(Rp)
    f = lambda x, m: x[m(x.signal)].R.mean()
    sel = lambda s: s <= SPLIT; ver = lambda s: s > SPLIT
    dd = t.groupby('signal').R.mean() - pl.groupby('signal').R.mean(); dd = dd.dropna()
    print(f'{nm:28s} R {t.R.mean():+.3f}  placebo {pl.R.mean():+.3f}  ->  alfa {t.R.mean()-pl.R.mean():+.3f} R (sel {f(t,sel)-f(pl,sel):+.3f}, ver {f(t,ver)-f(pl,ver):+.3f}); t dell\'alfa per giorno {dd.mean()/dd.std()*np.sqrt(len(dd)):.2f}')
print('varianti provate:', n_tr + 9); json.dump(['x'] * (n_tr + 9), open(D + 'trials_07.json', 'w'))
