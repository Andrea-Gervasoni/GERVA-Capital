"""B5 (1) - inversione di breve periodo sui singoli titoli, neutrale per settore. SIMULATO."""
from lab import *
P = load(); U = P['member']; r = P['ret']
c, h, l = P['ac'], P['ah'], P['al']
def W_of(mask, K): return mask.astype(float) / K
def hold_avg(W, H): return W.rolling(H, min_periods=1).sum() / H
sig = {}
sig['rev1'] = -sector_demean(r, P, U)
sig['rev5'] = -sector_demean(c / c.shift(5) - 1, P, U)
sig['rev3'] = -sector_demean(c / c.shift(3) - 1, P, U)
ibs = (P['close'] - P['low']) / (P['high'] - P['low']).replace(0, np.nan)
sig['ibs'] = -sector_demean(ibs, P, U)
d = c.diff(); up = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
rsi2 = 100 * up / (up + dn)
sig['rsi2'] = -sector_demean(rsi2, P, U)
# controllo di troncamento: il segnale a t ricalcolato su dati tagliati a t deve coincidere
t0 = c.index[3000]; Pc = {k: (v.loc[:t0] if hasattr(v, 'loc') and k not in ('sector',) else v) for k, v in P.items()}
chk = -sector_demean(Pc['ret'], Pc, Pc['member'])
print('troncamento rev1: diff max', float((chk.loc[t0] - sig['rev1'].loc[t0]).abs().max()))
print('================ griglia: K=20 e 50 per gamba, tenuta 1 e 5 giorni, esecuzione apertura t+1')
res = {}
for nm in ['rev1', 'rev3', 'rev5', 'ibs', 'rsi2']:
    for K in (20, 50):
        for H in (1, 5):
            Wl = hold_avg(W_of(topk(sig[nm], U, K, True), K), H); Ws = hold_avg(W_of(topk(sig[nm], U, K, False), K), H)
            res[(nm, K, H)] = evaluate(P, f'{nm} K{K} H{H}', Wl, Ws, full=(K == 20))
# RSI-2 classico: long se RSI2<10 e chiusura>SMA200, esce quando chiusura>SMA5; (short speculare)
sma200, sma5 = c.rolling(200).mean(), c.rolling(5).mean()
def state(entry, exit_):
    e = entry.values; x = exit_.values; s = np.zeros(e.shape, bool)
    for t in range(1, len(e)): s[t] = (s[t - 1] & ~x[t]) | e[t]
    return pd.DataFrame(s, index=entry.index, columns=entry.columns)
for thr in (5, 10):
    L = state((rsi2 < thr) & (c > sma200) & U, (c > sma5) | ~U); S = state((rsi2 > 100 - thr) & (c < sma200) & U, (c < sma5) | ~U)
    Wl = L.astype(float) / 20; Wl = Wl.div(Wl.sum(axis=1).clip(lower=1), axis=0)     # 5% per titolo, mai oltre 100% lordo
    Ws = S.astype(float) / 20; Ws = Ws.div(Ws.sum(axis=1).clip(lower=1), axis=0)
    res[('rsi2c', thr)] = evaluate(P, f'RSI2<{thr} classico', Wl, Ws)
print('================ decadimento per periodo (Sharpe LORDO e netto conto grande, LS)')
for k in [('rev1', 20, 1), ('rev5', 20, 5), ('ibs', 20, 1), ('rsi2', 20, 1), ('rsi2c', 10)]:
    x = res[k][[n for n in res[k] if n.endswith(' LS')][0]]
    row = []
    for a, b in (('2005', '2009'), ('2010', '2014'), ('2015', '2019'), ('2020', '2022'), ('2023', '2026')):
        g = x['gross'].loc[a:b]; n = x['net'].loc[a:b]
        row.append(f'{a}-{b[2:]}: lordo {g.mean()/g.std()*252**.5:5.2f} ({g.mean()*25200:5.1f}%) netto {n.mean()/n.std()*252**.5:5.2f}')
    print(k, ' | '.join(row))
print('================ sopravvivenza: stessi segnali su (a) membri PIT, (b) solo membri di oggi, (c) PIT dal 2018 (copertura >=85%)')
T = P['today']
for nm, K, H in [('rev1', 20, 1), ('rev5', 20, 5), ('ibs', 20, 1)]:
    rows = []
    for lab_, UU in (('PIT', U), ('oggi', T)):
        s = {'rev1': -sector_demean(r, P, UU), 'rev5': -sector_demean(c / c.shift(5) - 1, P, UU), 'ibs': -sector_demean(ibs, P, UU)}[nm]
        Wl = hold_avg(W_of(topk(s, UU, K, True), K), H); Ws = hold_avg(W_of(topk(s, UU, K, False), K), H)
        for leg, W in (('LO', Wl), ('SO', -Ws), ('LS', Wl - Ws)):
            x = run_weights(P, W); rows.append(stats(x['net'], f'{nm} {leg} {lab_}')); rows.append(stats(x['net'].loc['2018':], f'{nm} {leg} {lab_} dal 2018'))
    print(fmt(rows))
pd.to_pickle({k: {n: x['net'] for n, x in v.items()} for k, v in res.items()}, D + 'data/res_reversal.pkl')
print('varianti provate:', len(TRIALS)); json.dump(TRIALS, open(D + 'trials_03.json', 'w'))
