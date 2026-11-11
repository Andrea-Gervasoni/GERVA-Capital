"""B5 (3)(4b) - deriva post-annuncio con proxy di solo prezzo (gap + volume) e continuazione dei breakout a 52 settimane.
Le date degli utili e le sorprese NON sono recuperabili da Yahoo da qui (crumb/quoteSummary rispondono 'Too Many Requests',
events=earn nel chart e' vuoto): si usa il proxy. SIMULATO."""
from lab import *
P = load(); U = P['member']; r = P['ret']; c = P['ac']
vol60 = r.rolling(60, min_periods=40).std().shift(1)
gap = P['ao'] / c.shift(1) - 1
adjr = r - r.where(U).mean(axis=1).values[:, None]                # rendimento al netto del mercato equipesato
vrat = P['volume'] / P['volume'].rolling(60, min_periods=40).mean().shift(1)
def events(zthr, vthr, gthr=0.02):
    big = (adjr.abs() >= zthr * vol60) & (adjr.abs() >= 0.04) & (vrat >= vthr) & (gap.abs() >= gthr) & (np.sign(gap) == np.sign(adjr)) & U
    return big & (adjr > 0), big & (adjr < 0)
up, dn = events(3, 2)
ny = (len(c.loc[START:]) / 252)
print('eventi (3 sigma, volume 2x, gap 2%%): su %d (%.0f/anno), giu %d (%.0f/anno)' % (up.loc[START:].sum().sum(), up.loc[START:].sum().sum() / ny, dn.loc[START:].sum().sum(), dn.loc[START:].sum().sum() / ny))
# verifica che il proxy colga gli utili: stagionalita' mensile degli eventi (attesi picchi in gen-feb, apr-mag, lug-ago, ott-nov)
m = (up | dn).loc[START:].sum(axis=1); print('eventi per mese di calendario:', m.groupby(m.index.month).sum().to_dict())
# studio d'evento: rendimento cumulato al netto del mercato da apertura t+1
print('================ studio di evento: rendimento medio al netto del mercato EW (apertura t+1 -> chiusura t+h), in %')
ao = P['ao']; mk = (1 + r.where(U).mean(axis=1).fillna(0)).cumprod()
def car(ev, h, sl):
    e = ev.loc[sl]; x = (c.shift(-h) / ao.shift(-1) - 1).loc[sl]; mm = (mk.shift(-h) / mk - 1).loc[sl]
    v = x.sub(mm, axis=0).where(e).stack().dropna()
    byday = v.groupby(level=0).mean()
    return v.mean() * 100, byday.mean() / byday.std() * np.sqrt(len(byday)), len(v)
for lab_, ev in (('SU', up), ('GIU', dn)):
    for sl_l, sl in (('2005-2010', slice('2005', '2010')), ('2011-2016', slice('2011', '2016')), ('2017-2022', slice('2017', '2022')), ('2023-2026', slice('2023', '2026-07'))):
        print(lab_, sl_l, ' | '.join('h=%d: %+.2f%% (t %.1f)' % ((h,) + car(ev, h, sl)[:2]) for h in (1, 5, 20, 60)), ' n=%d' % car(ev, 5, sl)[2])
def slots(ev, H, K):
    W = ev.astype(float).rolling(H, min_periods=1).max() / K          # in portafoglio per H giorni dopo l'evento
    return W.div((W.sum(axis=1)).clip(lower=1), axis=0)
res = {}
print('================ portafogli a slot (peso 1/K per evento, lordo mai oltre 100% per gamba)')
for z, v in ((3, 2), (4, 3)):
    u_, d_ = events(z, v)
    for H in (5, 20, 60):
        K = 20
        res[(z, v, H)] = evaluate(P, f'PEADproxy z{z} v{v} H{H}', slots(u_, H, K), slots(d_, H, K), full=(z == 3))
# contrarian: l'evento negativo rimbalza? (lo studio d'evento lo dice; qui la versione long sui GIU)
for H in (5, 20):
    res[('contr', H)] = evaluate(P, f'gap GIU comprato H{H}', slots(dn, H, 20), None, full=False)
print('================ breakout: nuova chiusura massima a 252 giorni (non massimo nei 20 giorni prima), con/senza volume')
hi = c >= c.rolling(252, min_periods=200).max()
fresh = hi & ~(hi.shift(1).rolling(20).max().fillna(0).astype(bool)) & U
for vq, nm in ((0, 'tutti'), (1.5, 'volume>1.5x')):
    ev = fresh & (vrat >= vq)
    print(nm, 'eventi/anno %.0f' % (ev.loc[START:].sum().sum() / ny), ' | '.join('h=%d: %+.2f%% (t %.1f)' % ((h,) + car(ev, h, slice('2005', '2026-07'))[:2]) for h in (5, 20, 60)))
    for H in (20, 60):
        res[('brk', vq, H)] = evaluate(P, f'breakout52 {nm} H{H}', slots(ev, H, 20), None, full=False)
pd.to_pickle({k: {n: x['net'] for n, x in v.items()} for k, v in res.items()}, D + 'data/res_eventi.pkl')
print('varianti provate:', len(TRIALS)); json.dump(TRIALS, open(D + 'trials_05.json', 'w'))
