"""B5 (5 bis) - persistenza del rendimento notturno per titolo: comprare in asta di chiusura i titoli con la notte media
piu' alta negli ultimi LB giorni, vendere in asta d'apertura. Ri-derivazione con prezzi grezzi, specchio intraday,
griglia scelta SOLO su selezione (<=2022), costi d'asta IBKR, conto da 10k EUR, leva. SIMULATO."""
from lab import *
P = load(); U = P['member']; c = P['ac']; ao = P['ao']; cal = c.index
hs, psh = cost_parts(P)
on = (ao / c.shift(1) - 1); on = on.where(on.abs() < 0.5)
intr = (c / ao - 1); intr = intr.where(intr.abs() < 0.5)
k = P['adj'] / P['close']; same = (k / k.shift(1) - 1).abs() < 1e-6
on_raw = (P['open'].where(P['open'] > 0) / P['close'].shift(1) - 1).where(same); on_raw = on_raw.where(on_raw.abs() < 0.5)
days = pd.Series(cal, index=cal).diff().dt.days.fillna(1)              # notti di calendario fino all'apertura di t
px = P['px']                                                            # prezzo reale storico (non rettificato per split)
def sig_of(LB, src=on): return src.rolling(LB, min_periods=LB // 2).mean()
def run(K=20, LB=252, pmin=0, UU=U, account=None, lev=1.0, mode='asta', lag=0, cost_mult=1.0, src=on, ret=on, extra=0.0, short=False, score=None):
    s = (score if score is not None else sig_of(LB, src)).shift(lag)
    W = (topk(s, UU & (px > pmin), K, not short) / K) * lev * (-1 if short else 1)
    Wd = W.shift(1).fillna(0)                                           # deciso prima della chiusura di t-1, in essere nella notte che finisce a t
    g = (Wd * ret.fillna(0)).sum(axis=1)
    com = Wd.abs() * psh
    if account is not None: com = np.maximum(com, 0.35 / account).where(Wd.abs() > 0, 0)
    cc = (com * 2 + Wd.abs() * 2 * ((hs if mode == 'spread' else 0) + extra)).sum(axis=1) * cost_mult
    fin = (Wd.clip(lower=0).sum(axis=1) - 1).clip(lower=0) * (P['rf'] + 0.015 / 252) * days + (-Wd.clip(upper=0)).sum(axis=1) * 0.01 / 252 * days
    return pd.DataFrame({'net': g - cc - fin, 'gross': g, 'cost': cc, 'fin': fin}).loc[START:END]
def row(lab_, x):
    d = stats(x['net'], lab_); d['gross_sh'] = round(stats(x['gross'])['sh'], 2); d['lordo%yr'] = round(x['gross'].mean() * 25200, 1); d['cost%yr'] = round(x['cost'].mean() * 25200, 1); return d
# troncamento
t0 = cal[4000]; s_full = sig_of(252).loc[t0]; s_cut = (on.loc[:t0]).rolling(252, min_periods=126).mean().loc[t0]
print('troncamento: diff max', float((s_full - s_cut).abs().max()))
print('================ 1. ri-derivazione (K20, LB252, lordo): prezzi rettificati vs prezzi grezzi senza giorni di stacco/split; specchio intraday')
b = run(); rows = [row('rettificati: notte', b)]
rows.append(row('grezzi (segnale e rendimento): notte', run(src=on_raw, ret=on_raw)))
rows.append(row('stessi titoli: INTRADAY (apertura->chiusura)', run(ret=intr.shift(0))))
rows.append(row('stessi titoli: close-close (notte+giorno)', run(ret=P['ret'])))
ewon = on.where(U.shift(1).fillna(False)).mean(axis=1).loc[START:END]
rows.append(stats(b['gross'] - ewon, 'notte top20 meno notte EW (alfa lordo)')); rows.append(stats(ewon, 'notte EW tutti i membri (lordo)'))
print(fmt(rows))
print('nota: lo specchio intraday e\' attribuito al giorno t (stessa selezione), prima della notte? no: stesso giorno della notte appena finita')
print('================ 2. griglia (asta: solo commissione; conto grande) - si sceglie su SELEZIONE')
rows = []; G = {}; n_tr = 0
for LB in (20, 60, 126, 252):
    for K in (5, 10, 20, 50):
        for pmin in (0, 30):
            x = run(K, LB, pmin); G[(LB, K, pmin)] = x; rows.append(row(f'LB{LB} K{K} prezzo>{pmin}', x)); n_tr += 1
print(fmt(rows))
best = max(G, key=lambda q: stats(G[q]['net'])['sh_sel']); print('migliore per Sharpe in selezione:', best)
LB, K, pm = best
print('================ 3. robustezza del prescelto e del vicino piu\' semplice (LB252 K20)')
for (LB, K, pm) in (best, (252, 20, 0), (252, 10, 30)):
    rows = []
    rows.append(row(f'LB{LB} K{K} p>{pm} asta, conto grande', run(K, LB, pm)))
    rows.append(row('  costi x2', run(K, LB, pm, cost_mult=2)))
    rows.append(row('  + scarto dal prezzo d\'asta 1 bp per lato', run(K, LB, pm, extra=1e-4)))
    rows.append(row('  + 3 bp per lato', run(K, LB, pm, extra=3e-4)))
    rows.append(row('  ordini a mercato (mezzo spread)', run(K, LB, pm, mode='spread')))
    rows.append(row('  segnale in ritardo di 1 giorno', run(K, LB, pm, lag=1)))
    rows.append(row('  segnale in ritardo di 5 giorni', run(K, LB, pm, lag=5)))
    rows.append(row('  universo: solo membri di oggi', run(K, LB, pm, UU=P['today'])))
    rows.append(row('  conto 10k EUR 1x', run(K, LB, pm, account=11500)))
    rows.append(row('  conto 10k EUR 2x', run(K, LB, pm, account=11500, lev=2)))
    rows.append(row('  conto 25k EUR 2x', run(K, LB, pm, account=28750, lev=2)))
    rows.append(row('  conto 100k EUR 1x', run(K, LB, pm, account=115000)))
    rows.append(row('  gamba short: bottom K di notte', run(K, LB, pm, short=True)))
    print(fmt(rows)); n_tr += 6
x = G[best]
print('================ 4. per anno (prescelto, asta conto grande): netto %, Sharpe; lordo %; notte EW %')
by = by_year(x['net']); by['lordo%'] = x['gross'].groupby(x.index.year).sum().mul(100).round(1); by['notteEW%'] = ewon.groupby(ewon.index.year).sum().mul(100).round(1)
by2 = by_year(G[(252, 20, 0)]['net']); by['LB252K20 net%'] = by2['ret%']
print(by.T.to_string())
print('================ 5. chi sono: prezzo mediano, vol, beta dei selezionati vs universo; rotazione')
W = topk(sig_of(best[0]), U & (px > best[2]), best[1], True)
v = P['ret'].rolling(60).std() * 252 ** .5
print('prezzo mediano selezionati %.0f $ (universo %.0f); vol 60g %.0f%% (universo %.0f%%); titoli cambiati al giorno %.1f su %d' % (
    px.where(W).stack().median(), px.where(U).stack().median(), v.where(W).stack().median() * 100, v.where(U).stack().median() * 100,
    (W.astype(int).diff().clip(lower=0)).sum(axis=1).loc[START:].mean(), best[1]))
sec = P['sector']; cnt = W.loc[START:].sum().groupby(sec).sum(); print('settori (%):', (cnt / cnt.sum() * 100).round(0).to_dict())
pd.to_pickle({'best': best, 'G': {q: G[q]['net'] for q in G}, 'k10eur_2x': run(best[1], best[0], best[2], account=11500, lev=2)['net'],
              'k10eur_1x': run(best[1], best[0], best[2], account=11500)['net'], 'simple': G[(252, 20, 0)]['net'], 'ewon': ewon}, D + 'data/res_notte2.pkl')
print('varianti provate:', n_tr); json.dump(['x'] * n_tr, open(D + 'trials_09.json', 'w'))
