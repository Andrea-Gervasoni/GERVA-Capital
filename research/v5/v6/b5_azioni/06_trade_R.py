"""B5 - le stesse idee come flusso di trade a leva misurato in R con stop ad ATR (dati giornalieri: lo stop e' verificato su
massimo/minimo del giorno, gap oltre lo stop -> uscita all'apertura). Strumento: CFD su azioni IBKR (5x) o margine (2x).
R = P&L netto / distanza dello stop. SIMULATO."""
from lab import *
P = load(); U = P['member']; r = P['ret']; c = P['ac']; cal = c.index
hs, psh = cost_parts(P); cost = hs + psh
A = atr(P)
me = pd.Series(cal, index=cal).groupby([cal.year, cal.month]).last().values
ismE = pd.Series(cal.isin(me), index=cal)
s5 = -sector_demean(c / c.shift(5) - 1, P, U)
d = c.diff(); up_ = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean(); dn_ = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
rsi2 = 100 * up_ / (up_ + dn_); sma200, sma5 = c.rolling(200).mean(), c.rolling(5).mean()
mom = c.shift(21) / c.shift(252) - 1
vol60 = r.rolling(60, min_periods=40).std().shift(1); gap = P['ao'] / c.shift(1) - 1
adjr = r - r.where(U).mean(axis=1).values[:, None]; vrat = P['volume'] / P['volume'].rolling(60, min_periods=40).mean().shift(1)
big = (adjr.abs() >= 3 * vol60) & (adjr.abs() >= 0.04) & (vrat >= 2) & (gap.abs() >= 0.02) & (np.sign(gap) == np.sign(adjr)) & U
hi = c >= c.rolling(252, min_periods=200).max(); fresh = hi & ~(hi.shift(1).rolling(20).max().fillna(0).astype(bool)) & U & (vrat >= 1.5)
vol252 = r.rolling(252, min_periods=126).std()
mon = lambda m: m & ismE.values[:, None]
STREAMS = {
 'rev5 perdenti long':      dict(sig=topk(s5, U, 10, True), side=1, k_atr=2, hold=5, score=s5),
 'rev5 vincenti short':     dict(sig=topk(s5, U, 10, False), side=-1, k_atr=2, hold=5, score=-s5),
 'RSI2<10 >SMA200 long':    dict(sig=(rsi2 < 10) & (c > sma200) & U, side=1, k_atr=2, hold=5, score=-rsi2, exit_sig=c > sma5),
 'RSI2>90 <SMA200 short':   dict(sig=(rsi2 > 90) & (c < sma200) & U, side=-1, k_atr=2, hold=5, score=rsi2, exit_sig=c < sma5),
 'mom12-1 top20 mensile':   dict(sig=mon(topk(mom, U, 20, True)), side=1, k_atr=3, hold=21, max_new=20),
 'mom12-1 bottom20 short':  dict(sig=mon(topk(mom, U, 20, False)), side=-1, k_atr=3, hold=21, max_new=20),
 'PEADproxy SU long':       dict(sig=big & (adjr > 0), side=1, k_atr=2, hold=20, score=adjr / vol60),
 'PEADproxy GIU short':     dict(sig=big & (adjr < 0), side=-1, k_atr=2, hold=20, score=-adjr / vol60),
 'breakout52+volume long':  dict(sig=fresh, side=1, k_atr=2, hold=20, score=vrat),
 'breakout52+volume H60 3ATR': dict(sig=fresh, side=1, k_atr=3, hold=60, score=vrat),
 'lowvol top20 mensile':    dict(sig=mon(topk(-vol252, U, 20, True)), side=1, k_atr=3, hold=21, max_new=20),
}
rows = []; allT = {}
for nm, kw in STREAMS.items():
    tr = trades_R(P, cost=cost, atr_=A, lev=5, fin=0.045, **kw); tr = tr[tr.signal >= START]; allT[nm] = tr
    d0 = r_stats(tr, nm)
    x = trade_daily(tr, 1.0, cal[cal >= START]); d0['SR_flusso'] = x.mean() / x.std() * 252 ** .5; d0['N(R/s)^2'] = d0['SR_flusso'] ** 2
    for lab_, k2 in (('R_costi_x2', dict(cost_mult=2)), ('R_ritardo', dict(delay=1)), ('R_10kEUR', dict(cost=cost + 3e-4))):
        kk = dict(kw); kk.update(k2); kk.setdefault('cost', cost)
        t2 = trades_R(P, atr_=A, lev=5, fin=0.045, **kk); d0[lab_] = t2[t2.signal >= START].R.mean()
    rows.append(d0)
df = pd.DataFrame(rows).round(3); pd.set_option('display.width', 300)
print(df.to_string(index=False))
print('================ R medio per anno')
print(pd.DataFrame({nm: t.groupby(t.signal.dt.year).R.mean().round(2) for nm, t in allT.items()}).T.to_string())
print('================ varianti dello stop sul candidato migliore per selezione (solo <=2022)')
best = max(STREAMS, key=lambda n: r_stats(allT[n])['t_sel'] if r_stats(allT[n])['t_sel'] == r_stats(allT[n])['t_sel'] else -9); print('migliore per t in selezione:', best)
rows = []
for k in (1.0, 1.5, 2.0, 3.0):
    for H in (3, 5, 10, 20):
        kk = dict(STREAMS[best]); kk.update(k_atr=k, hold=H)
        t2 = trades_R(P, cost=cost, atr_=A, lev=5, fin=0.045, **kk); t2 = t2[t2.signal >= START]; d0 = r_stats(t2, f'{best} k{k} H{H}')
        rows.append({q: d0[q] for q in ('label', 'n', 'R', 'R_sel', 'R_ver', 't_sel', 't_ver', 'win', 'stop_pct')})
print(pd.DataFrame(rows).round(3).to_string(index=False))
pd.concat([t.assign(stream=nm) for nm, t in allT.items()]).to_parquet(D + 'trades.parquet')
print('varianti provate:', len(STREAMS) + 16); json.dump(list(STREAMS) + ['grid'] * 16, open(D + 'trials_06.json', 'w'))
