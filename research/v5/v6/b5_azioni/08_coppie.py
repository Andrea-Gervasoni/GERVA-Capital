"""B5 (7) - coppie dentro i settori (Gatev-Goetzmann-Rouwenhorst): formazione 252 giorni, le N coppie per settore con minima
distanza dei prezzi normalizzati, si apre a 2 sigma, si chiude all'incrocio o a fine periodo (126 giorni). SIMULATO."""
from lab import *
P = load(); U = P['member']; c = P['ac']; cal = c.index
def build(n_per_sector=5, k_open=2.0, form=252, trade=126, stop_sig=None):
    W = pd.DataFrame(0.0, index=cal, columns=c.columns); npairs = []
    starts = range(np.searchsorted(cal, pd.Timestamp(START)), len(cal) - 5, trade)
    for s0 in starts:
        f0 = s0 - form
        if f0 < 0: continue
        win = c.iloc[f0:s0]; ok = U.iloc[s0 - 1] & win.notna().all()
        pairs = []
        for sec in P['sector'].unique():
            cols = [t for t in ok.index[ok] if P['sector'].get(t) == sec]
            if len(cols) < 4: continue
            x = np.log(win[cols] / win[cols].iloc[0]).values
            d2 = ((x[:, :, None] - x[:, None, :]) ** 2).sum(axis=0); iu = np.triu_indices(len(cols), 1)
            order = np.argsort(d2[iu])[:n_per_sector]
            for o in order:
                i, j = iu[0][o], iu[1][o]; sd = (x[:, i] - x[:, j]).std()
                if sd > 0: pairs.append((cols[i], cols[j], sd))
        npairs.append(len(pairs))
        if not pairs: continue
        seg = c.iloc[s0 - 1:min(s0 + trade, len(cal))]; base = win.iloc[0]
        wt = 1.0 / len(pairs)
        for a, b, sd in pairs:
            sp = (np.log(seg[a] / base[a]) - np.log(seg[b] / base[b])).values / sd      # spread alla chiusura, in sigma
            pos = 0; out = np.zeros(len(sp))
            for t in range(len(sp)):
                if not np.isfinite(sp[t]): pos = 0
                elif pos == 0:
                    if sp[t] > k_open: pos = -1
                    elif sp[t] < -k_open: pos = 1
                elif (pos == 1 and sp[t] >= 0) or (pos == -1 and sp[t] <= 0): pos = 0
                elif stop_sig and abs(sp[t]) > stop_sig: pos = 0
                out[t] = pos
            out[-1] = 0
            ix = seg.index[1:]                                   # il giorno s0-1 serve solo come stato iniziale
            W.loc[ix, a] += out[1:] * wt; W.loc[ix, b] -= out[1:] * wt
    return W, np.mean(npairs)
res = {}
for n, k in ((5, 2.0), (2, 2.0), (5, 1.5), (5, 2.5), (10, 2.0)):
    W, npair = build(n, k)
    print(f'--- {n} coppie per settore (media {npair:.0f} coppie), apertura a {k} sigma; esposizione lorda media per gamba {W.clip(lower=0).sum(axis=1).loc[START:].mean():.2f}')
    res[(n, k)] = evaluate(P, f'coppie n{n} k{k}', W.clip(lower=0), (-W).clip(lower=0), full=(n == 5 and k == 2.0))
x = res[(5, 2.0)]['coppie n5 k2.0 LS']
print('per periodo (lordo / netto):', ' | '.join(f'{p0}-{p1[2:]}: {x["gross"].loc[p0:p1].mean()*25200:5.1f}% / {x["net"].loc[p0:p1].mean()*25200:5.1f}%' for p0, p1 in (('2005', '2009'), ('2010', '2014'), ('2015', '2019'), ('2020', '2022'), ('2023', '2026'))))
pd.to_pickle({k: {n: v['net'] for n, v in r_.items()} for k, r_ in res.items()}, D + 'data/res_coppie.pkl')
print('varianti provate:', len(TRIALS)); json.dump(TRIALS, open(D + 'trials_08.json', 'w'))
