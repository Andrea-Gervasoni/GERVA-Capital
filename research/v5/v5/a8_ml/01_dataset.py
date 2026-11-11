"""A8 - 01: costruzione del dataset dei candidati (ogni giorno x coin, long e short) e controlli.
Candidato: trade generico all'apertura del giorno i, stop 1xATR14 (come libro v4), trailing 2x, durata max 7 giorni,
NESSUNA uscita legata alla conviction (cosi' l'etichetta non dipende dalla regola che si vuole battere).
Controlli: (a) riproduzione del libro v4 '1xATR alta trail=2' da trades.pkl; (b) troncamento delle feature."""
import pickle, time
from lib import *
t0 = time.time(); dt = Data(); MAXH = 7
rows = []; SIMS = {c: Sim(dt, c) for c in COINS}; XS = {c: features(dt, c) for c in COINS}
for c in COINS:
    X = XS[c]; s = SIMS[c]; atr = X['atr_stop'].values
    for i in range(250, s.n - MAXH - 1):
        if not np.isfinite(atr[i]) or X['tier'].iloc[i] is None: continue
        sd = float(np.clip(atr[i], 0.003, 0.15)); r = dict(coin=c, date=s.days[i], sd=sd)
        for side, nm in ((1, 'L'), (-1, 'S')):
            t = s.trade(i, side, sd, i + MAXH); r[f'R_{nm}'] = t['R']; r[f'why_{nm}'] = t['why']; r[f'days_{nm}'] = t['days']
            r[f'R2_{nm}'] = s.trade(i, side, sd, i + MAXH, cm=2.0)['R']            # costi doppi
            r[f'Rd_{nm}'] = s.trade(i, side, sd, i + MAXH, delay=12)['R']          # ritardo: 1 ora (12 barre 5m)
        rows.append(r)
Y = pd.DataFrame(rows).set_index(['coin', 'date'])
X = pd.concat({c: XS[c] for c in COINS}, names=['coin', 'date']); DS = Y.join(X, how='left')
DS.to_parquet(HERE + '/dataset.parquet')
print('dataset', DS.shape, 'feature', len(feat_names(X)), f'{time.time()-t0:.0f}s')
g = DS.reset_index().groupby('coin')['date']; print(g.agg(['size', 'min', 'max']))
d = DS.reset_index(); d['per'] = np.where(d.date < SPL, 'scelta', 'verifica')
print('\nCandidati generici (TUTTI i giorni, sovrapposti): R medio per periodo e lato')
for nm in ('L', 'S'):
    print(nm, d.groupby('per')[f'R_{nm}'].agg(['size', 'mean', 'std', lambda x: (x > 0).mean()]).round(3).to_string().replace('\n', ' | '))
print('\nLong generico per livello di conviction (regola attuale):')
print(d.groupby(['per', 'tier'])['R_L'].agg(['size', 'mean', 'std', lambda x: (x > 0).mean()]).round(3))
print('\nQuota di NaN per feature nel periodo di scelta (>5%):'); na = d[d.per == 'scelta'][feat_names(X)].isna().mean(); print(na[na > 0.05].round(2).to_dict())

# (a) riproduzione del libro v4
print('\n== Controllo (a): riproduzione libro v4 "stop 1xATR alta trail=2" ==')
ref = pickle.load(open(ROOT + '/research/v5/v4/_cache/trades.pkl', 'rb'))[('atr1.0', ('alta',), 2.0, 'long')]
out = []
for c in COINS:
    s = SIMS[c]; tier = XS[c]['tier'].values; atr = XS[c]['atr_stop'].values; sc = XS[c]['score'].values; i = 250
    while i < s.n - 1:
        if tier[i] != 'alta' or not np.isfinite(sc[i]): i += 1; continue
        sd = float(np.clip(atr[i], 0.003, 0.15)); j = i + 1
        while not (j >= s.n - 1 or j - i >= 7 or tier[j] == 'bassa'): j += 1
        t = s.trade(i, 1, sd, j); out.append(t); i = t['j'] + 1
mine = pd.DataFrame(out)
print(f"v4: n={len(ref)} R medio={ref.R.mean():.4f} | mio: n={len(mine)} R medio={mine.R.mean():.4f}")
mg = ref.merge(mine, on=['coin', 'entry'], suffixes=('_v4', '_a8'))
print(f"trade con stessa data d'ingresso: {len(mg)}; max |R_v4 - R_a8| = {(mg.R_v4-mg.R_a8).abs().max():.2e}")

# (b) troncamento: ricalcolo delle feature con dati tagliati a t; devono coincidere
print('\n== Controllo (b): troncamento ==')
rng = np.random.default_rng(0); bad = 0; tot = 0
for cut in pd.to_datetime(['2019-03-15', '2021-06-01', '2022-11-20', '2024-02-10', '2025-09-05']):
    dc = Data(cut)
    for c in COINS:
        if dc.D[c].shape[0] < 300: continue
        a = features(dc, c).drop(columns='tier').iloc[-30:]; b = XS[c].drop(columns='tier').reindex(a.index)
        # l'ultima riga 'a' (giorno cut-1) usa dati fino a cut-2: tutte e 30 devono coincidere
        diff = (a.astype(float) - b.astype(float)).abs().max().max(); nanmis = (a.isna() != b.isna()).sum().sum()
        tot += 1; bad += int(diff > 1e-9 or nanmis > 0)
        if diff > 1e-9 or nanmis > 0:
            w = (a.astype(float) - b.astype(float)).abs().max(); print('  DIVERSO', cut.date(), c, w[w > 1e-9].to_dict(), 'nan diversi', (a.isna() != b.isna()).sum()[lambda x: x > 0].to_dict())
print(f'controlli {tot}, diversi {bad}')
