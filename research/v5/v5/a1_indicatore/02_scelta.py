"""A1 - SCELTA dell'indicatore. Usa SOLO trade-sonda con ingresso <= 2022-12-31 (nessun numero della verifica viene letto).
Trade-sonda: un trade long per ogni (moneta, giorno), stop 1xATR, trailing 2, massimo 7 giorni, nessuna uscita su segnale; costi e funding
come leva_trade_isolato. 'big' = BTC/ETH/SOL su percorso spot a 5 minuti; 'alt' = 18 altre monete su percorso perpetual a 1 ora. SIMULATO."""
import json, numpy as np, pandas as pd, lib, indicatore
pd.set_option('display.width', 250)
UNI = "BTC ETH SOL BNB XRP DOGE ADA LTC LINK AVAX DOT BCH ETC ATOM TRX XLM UNI AAVE EOS LUNA FTT".split()
X = []; TQ = {}
for c in UNI:
    d = lib.st.get(f'v5_spot_1d_tk_{c}')
    if c == 'LUNA': d = d[d.index < '2022-05-14']
    if c == 'FTT': d = d[d.index < '2022-11-14']
    a = ((d.high - d.low) / d.close).rolling(14).mean(); f = pd.DataFrame(index=d.index); TQ[c] = lib.trend_quality(d['close'])
    f['dip3'] = -(d.close / d.close.shift(3) - 1) / a; f['dip1'] = -(d.close / d.close.shift(1) - 1) / a; f['ibs'] = -((d.close - d.low) / (d.high - d.low))
    f['thrust'] = (d.close - d.open) / d.close / a; f['vsurge'] = np.log(d.quote_volume / d.quote_volume.rolling(30).median())
    f['volratio'] = -np.log(((d.high - d.low) / d.close).rolling(5).mean() / ((d.high - d.low) / d.close).rolling(60).mean())
    f['dd60'] = d.close / d.high.rolling(60).max() - 1; f['rp60'] = lib.range_pos(d, 60); f['rp120'] = lib.range_pos(d, 120)
    f = f.shift(1); f['coin'] = c; f = f.reset_index(); f.columns = ['entry'] + list(f.columns[1:]); X.append(f)
X = pd.concat(X); br = pd.DataFrame(TQ).mean(axis=1).shift(1)
Z = pd.concat([pd.read_parquet('_panel_C.parquet').assign(u='big'), pd.read_parquet('_panel_alt_C.parquet').assign(u='alt')]).merge(X, on=['entry', 'coin'], how='left')
Z['br'] = br.reindex(Z.entry).values
S = Z[Z.entry < lib.SPLIT].copy(); assert S.entry.max() < lib.SPLIT
print('trade-sonda nel periodo di scelta:', S.groupby('u').size().to_dict(), '| R medio incondizionato:', S.groupby('u').R.mean().round(3).to_dict())
F1 = ['score', 'tq', 'r2', 'comp', 'vwm', 'vws', 'flow', 'fund', 'rpos', 'mtf', 'btc', 'br', 'dip3', 'dip1', 'ibs', 'thrust', 'vsurge', 'volratio', 'dd60', 'rp60', 'rp120']
def qt(x, f, k=5):
    x = x.dropna(subset=[f]); q = pd.qcut(x[f].rank(method='first'), k, labels=False); return x.groupby(q).R.mean()
ntr = 0
print('\n[1] Componenti singole: R medio per quintile della componente (Q1 = valori piu\' bassi)')
for u in ('big', 'alt'):
    x = S[S.u == u]; T = pd.DataFrame({f: qt(x, f) for f in F1}).T; T.columns = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']; T['Q5-Q1'] = T.Q5 - T.Q1
    T['IC'] = [x[[f, 'R']].corr(method='spearman').iloc[0, 1] for f in F1]; print(u); print(T.round(3).to_string()); ntr += len(F1) - 1
print('\n[2] Dentro i giorni di conviction alta (score > 0,60): R medio per terzile della componente')
F2 = ['comp', 'flow', 'fund', 'mtf', 'vwm', 'btc', 'tq', 'dip3', 'thrust', 'vsurge', 'volratio', 'dd60']
for u in ('big', 'alt'):
    h = S[(S.u == u) & (S.score > 0.6)]; T = pd.DataFrame({f: qt(h, f, 3) for f in F2}).T; T.columns = ['T1', 'T2', 'T3']; print(u, 'n', len(h)); print(T.round(3).to_string())
ntr += len(F2)
x = S.copy(); x['R'] = x.R - x.groupby('entry').R.transform('mean')
print('\n[3] Stessa cosa ma su R meno la media del giorno (ordinamento TRA monete nello stesso giorno): quasi nullo -> il segnale e\' di regime, non di selezione')
T = pd.DataFrame({f: qt(x, f) for f in ['score', 'tq', 'vwm', 'mtf', 'flow', 'fund', 'comp']}).T; print(T.round(3).to_string())
print('\n[4] Indici composti (media a pesi uguali delle componenti divise per la loro deviazione standard nella scelta)')
S2 = S.dropna(subset=['tq', 'btc', 'br', 'vwm', 'mtf', 'rp60', 'rp120', 'score']).copy(); sd = {f: S2[f].std() for f in ['tq', 'btc', 'br', 'vwm', 'mtf', 'rp60', 'rp120']}
print('deviazioni standard (scelta):', {k: round(v, 3) for k, v in sd.items()})
C = {'conviction (score)': None, 'tq': ['tq'], 'br': ['br'], 'rp60': ['rp60'], 'tq+btc': ['tq', 'btc'], 'tq+br': ['tq', 'br'], 'btc+br': ['btc', 'br'], 'tq+btc+br': ['tq', 'btc', 'br'],
     'tq+btc+br+vwm+mtf': ['tq', 'btc', 'br', 'vwm', 'mtf'], 'tq+br+vwm': ['tq', 'br', 'vwm'], 'tq+btc+rp60': ['tq', 'btc', 'rp60'], 'tq+btc+rp120': ['tq', 'btc', 'rp120'],
     'tq+btc+rp60+vwm': ['tq', 'btc', 'rp60', 'vwm'], 'btc+rp60': ['btc', 'rp60'], 'tq+btc+rp60+mtf': ['tq', 'btc', 'rp60', 'mtf'], 'GQ = tq+btc+vwm  <-- scelto': ['tq', 'btc', 'vwm']}
rows = []
for nm, fs in C.items():
    v = S2['score'] if fs is None else sum(S2[f] / sd[f] for f in fs) / len(fs)
    r = dict(ind=nm)
    for u in ('big', 'alt'):
        m = S2.u == u; x = S2[m]; rk = v[m].rank(pct=True, method='first'); dec = x.groupby(np.minimum((rk * 10).astype(int), 9)).R.mean()
        yr = x[rk > 0.8].groupby(x.entry.dt.year).R.mean()
        r.update({f'{u}_top10': x[rk > 0.9].R.mean(), f'{u}_top20': x[rk > 0.8].R.mean(), f'{u}_bot20': x[rk <= 0.2].R.mean(),
                  f'{u}_rho': dec.reset_index(drop=True).corr(pd.Series(range(10)), method='spearman'), f'{u}_anni+': f'{(yr > 0).sum()}/{len(yr)}'})
    rows.append(r)
print(pd.DataFrame(rows).round(3).to_string(index=False)); ntr += len(C) - 1
print('\nCriterio di scelta (fissato prima di guardare la verifica): top 20% migliore in media tra big e alt, con rho dei decili >= 0,8 su entrambi e anni positivi.')
# ------- congelamento: soglie sui quantili della scelta (BTC/ETH/SOL) -------
B = S[S.u == 'big'].copy(); B['gq'] = (B.tq / 0.2 + B.btc / 0.2 + B.vwm / 0.4) / 3; B = B.dropna(subset=['gq', 'score'])
p_ecc = (B.score > 0.75).mean(); p_alta = (B.score > 0.60).mean(); p_bassa = (B.score <= 0.30).mean()
fz = dict(decili=[float(B.gq.quantile(q / 10)) for q in range(1, 10)], ecc=float(B.gq.quantile(1 - p_ecc)), alta=float(B.gq.quantile(1 - p_alta)), bassa=float(B.gq.quantile(p_bassa)),
          quota_ecc=float(p_ecc), quota_alta=float(p_alta), quota_bassa=float(p_bassa), sd=indicatore.SD)
json.dump(fz, open('congelato.json', 'w'), indent=1)
print('\nCONGELATO (congelato.json):', json.dumps({k: (np.round(v, 3).tolist() if not isinstance(v, dict) else v) for k, v in fz.items()}))
print('soglie = stessi quantili che la conviction usa nella scelta: eccezionale = top %.1f%%, alta = top %.1f%%, bassa = fondo %.1f%% dei giorni' % (100 * p_ecc, 100 * p_alta, 100 * p_bassa))
print('varianti contate in questo script:', ntr)
