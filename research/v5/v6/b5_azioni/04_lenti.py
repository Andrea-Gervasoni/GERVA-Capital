"""B5 (2)(4a)(6) - fattori lenti a ribilanciamento mensile: momentum 12-1 / 6-1 / 3-1 / 1 mese, momentum residuo,
vicinanza al massimo a 52 settimane, bassa volatilita' / basso beta. SIMULATO."""
from lab import *
P = load(); U = P['member']; r = P['ret']; c = P['ac']
cal = c.index
me = pd.Series(cal, index=cal).groupby([cal.year, cal.month]).last().values      # ultimo giorno di borsa del mese
def monthly(mask_fn, UU=U, every=1):
    """pesi decisi a fine mese e tenuti fino al mese dopo"""
    W = pd.DataFrame(np.nan, index=cal, columns=c.columns)
    for d in me[::every]: W.loc[d] = mask_fn(d).astype(float)
    return W.ffill().fillna(0.0)
mkt = r.where(U).mean(axis=1)
beta = r.rolling(252, min_periods=126).cov(mkt).div(mkt.rolling(252, min_periods=126).var(), axis=0)
resid = r - beta.shift(1).mul(mkt, axis=0)
vol252 = r.rolling(252, min_periods=126).std(); vol60 = r.rolling(60, min_periods=40).std()
S = {
 'mom12_1': c.shift(21) / c.shift(252) - 1,
 'mom6_1': c.shift(21) / c.shift(126) - 1,
 'mom3_1': c.shift(21) / c.shift(63) - 1,
 'mom12_0': c / c.shift(252) - 1,
 'mom1': c / c.shift(21) - 1,
 'resmom12_1': (resid.rolling(231, min_periods=150).sum() / resid.rolling(231, min_periods=150).std()).shift(21),
 'hi52': c / P['ah'].rolling(252, min_periods=200).max(),
 'lowvol': -vol252, 'lowvol60': -vol60, 'lowbeta': -beta,
 'mom_voladj': (c.shift(21) / c.shift(252) - 1) / vol252,
}
res = {}
def do(nm, K, UU=U, quiet=False, full=True):
    s = S[nm]
    def mk(largest):
        def f(d):
            x = s.loc[d].where(UU.loc[d]); rk = x.rank(ascending=not largest, method='first'); return (rk <= K) / K
        return f
    Wl, Ws = monthly(mk(True), UU), monthly(mk(False), UU)
    if quiet: return Wl, Ws
    res[(nm, K)] = evaluate(P, f'{nm} K{K}', Wl, Ws, full=full); return Wl, Ws
for nm in S:
    for K in (20, 50):
        do(nm, K, full=(K == 20))
print('================ per periodo (LS netto conto grande, K50) e LO attivo')
ew = run_weights(P, U.div(U.sum(axis=1), axis=0))['gross']
for nm in S:
    x = res[(nm, 50)][f'{nm} K50 LS']['net']; a = res[(nm, 50)][f'{nm} K50 LO']['net'] - ew
    print(f'{nm:12s}', ' | '.join(f'{p0}-{p1[2:]}: LS {x.loc[p0:p1].mean()*25200:6.1f}% sh {x.loc[p0:p1].mean()/x.loc[p0:p1].std()*252**.5:5.2f}  LO-EW {a.loc[p0:p1].mean()*25200:5.1f}%'
          for p0, p1 in (('2005', '2009'), ('2010', '2014'), ('2015', '2019'), ('2020', '2022'), ('2023', '2026'))))
print('================ sopravvivenza: membri PIT vs solo membri di oggi (K50)')
rows = []
for nm in ['mom12_1', 'mom6_1', 'resmom12_1', 'hi52', 'lowvol']:
    for lab_, UU in (('PIT', U), ('oggi', P['today'])):
        Wl, Ws = do(nm, 50, UU, quiet=True)
        for leg, W in (('LO', Wl), ('LS', Wl - Ws)):
            x = run_weights(P, W)['net']; rows.append(stats(x, f'{nm} {leg} {lab_}')); rows.append(stats(x.loc['2018':], f'{nm} {leg} {lab_} dal 2018'))
print(fmt(rows))
print('================ bassa volatilita con leva (LO K50, finanziamento T-bill+1.5%)')
rows = []
for nm in ['lowvol', 'lowbeta']:
    Wl, _ = do(nm, 50, quiet=True)
    for L in (1.0, 1.5, 2.0):
        x = run_weights(P, Wl, lev=L); rows.append(stats(x['net'], f'{nm} LO leva {L}', x['tov']))
x = P['spy_ret'].loc[START:END]; rows.append(stats(x, 'SPY 1x (riferimento, close-close)')); rows.append(stats(ew, 'EW membri PIT (lordo)'))
print(fmt(rows))
pd.to_pickle({k: {n: x['net'] for n, x in v.items()} for k, v in res.items()}, D + 'res_lenti.pkl')
print('varianti provate:', len(TRIALS) + 6); json.dump(TRIALS + ['lev'] * 6, open(D + 'trials_04.json', 'w'))
