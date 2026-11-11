"""A1 - Libro di trade sequenziale (un trade per volta per moneta, come leva_trade_isolato): ingressi decisi da GQ contro ingressi decisi
dalla conviction attuale. Stesse regole di uscita (stop sul percorso a 5m, uscita quando l'indicatore scende a 'bassa', massimo 7 giorni).
Costi x2, un 5-minuti di ritardo, t, per anno. Scrive trades.parquet e returns.parquet. SIMULATO."""
import json, numpy as np, pandas as pd, lib, indicatore, feat
import leva_trade_isolato as L
pd.set_option('display.width', 250); fz = json.load(open('congelato.json'))
GQ = {}; SC = {}
for c in feat.COINS:
    P = feat.PATH[c]; tk = lib.st.get(f'v5_spot_1d_tk_{c}')
    GQ[c] = indicatore.gq(P.d, tk['volume'], feat.PATH['BTC'].d['close']).shift(1).values       # noto la sera prima
    SC[c] = L.CONV[c]['score'].values
def book(kind, lev, conv='C', **kw):
    """kind: 'conv' | 'gq'; lev: 'alta' | 'ecc' (soglia d'ingresso). Uscita su segnale: indicatore a 'bassa'."""
    out = []
    for c in feat.COINS:
        g = GQ[c]; s = SC[c]
        if kind == 'conv': en = s > (0.60 if lev == 'alta' else 0.75); ex = ~(s > 0.30)          # NaN -> bassa, come l'originale
        else: en = g >= fz[lev]; ex = ~(g > fz['bassa'])
        en = en & ~np.isnan(s)
        pk = dict(atr_k=1.0, trail=2.0) if conv == 'C' else dict(s=0.017, atr_k=None, trail=None)
        T = feat.PATH[c].book(en, ex, **pk, **kw)
        if len(T): T['coin'] = c; T['gq'] = g[np.searchsorted(feat.PATH[c].days, T.entry.values)]; T['score'] = s[np.searchsorted(feat.PATH[c].days, T.entry.values)]; out.append(T)
    return pd.concat(out, ignore_index=True)
def row(T, lab):
    y = (T.entry.max() - T.entry.min()).days / 365.25; r = lib.three(T)
    return dict(libro=lab, n=r['n'], per_anno=r['n'] / y, R=r['R'], t=r['t'], vincenti=r['hit'], sigmaR=T.R.std(), R_scelta=r['R_sc'], t_sc=r['t_sc'], n_ver=r['n_ve'], R_verifica=r['R_ve'], t_ver=r['t_ve'],
                R_su_sigma=r['R'] / T.R.std(), R_su_sigma_ver=T[T.entry >= lib.SPLIT].R.mean() / T[T.entry >= lib.SPLIT].R.std(), leva=T.L.median())
rows = []; KEEP = {}; nvar = 0
for conv in ('C', 'A'):
    for kind in ('conv', 'gq'):
        for lev in ('alta', 'ecc'):
            lab = f"{'1xATR trail2 ~11x' if conv == 'C' else '1,7% 30x'} | {'conviction' if kind == 'conv' else 'GQ'} {lev}"
            T = book(kind, lev, conv); KEEP[(conv, kind, lev)] = T; rows.append(row(T, lab)); nvar += 1
            rows.append(row(book(kind, lev, conv, cost=2.0), lab + ' | costi x2')); rows.append(row(book(kind, lev, conv, delay=1), lab + ' | ritardo +1 barra'))
print(pd.DataFrame(rows).round(3).to_string(index=False))
print('\nNota: "conviction alta" 1xATR e\' esattamente la riga "stop 1.0xATR alta trail=2" di leva_trade_isolato.out (652 trade, +0,237 R).')
print('\nDentro il libro "alta": i trade entrati a livello eccezionale contro gli altri (cosi\' e\' definito +0,40 R nel libro attuale)')
r2 = []
for conv in ('C', 'A'):
    T = KEEP[(conv, 'conv', 'alta')]; r2.append(dict(libro=f'{conv} conviction alta: score>0,75 all\'ingresso', **lib.three(T[T.score > 0.75]))); r2.append(dict(libro=f'{conv} conviction alta: score<=0,75', **lib.three(T[T.score <= 0.75])))
    r2.append(dict(libro=f'{conv} conviction alta: e GQ>=ecc', **lib.three(T[T.gq >= fz['ecc']]))); r2.append(dict(libro=f'{conv} conviction alta: e GQ>=alta', **lib.three(T[T.gq >= fz['alta']]))); r2.append(dict(libro=f'{conv} conviction alta: ma GQ<alta', **lib.three(T[T.gq < fz['alta']])))
    T = KEEP[(conv, 'gq', 'alta')]; r2.append(dict(libro=f'{conv} GQ alta: GQ>=ecc all\'ingresso', **lib.three(T[T.gq >= fz['ecc']]))); r2.append(dict(libro=f'{conv} GQ alta: GQ<ecc', **lib.three(T[T.gq < fz['ecc']])))
    for q in range(5):
        lo = [-9, fz['alta'], fz['decili'][7], fz['decili'][8], fz['ecc']][q]; hi = [fz['alta'], fz['decili'][7], fz['decili'][8], fz['ecc'], 99][q]
        if q: r2.append(dict(libro=f'{conv} GQ alta: GQ in [{lo:.2f},{hi:.2f})', **lib.three(T[(T.gq >= lo) & (T.gq < hi)])))
print(pd.DataFrame(r2).round(3).to_string(index=False))
print('\nPer anno (R medio, numero di trade):')
Y = pd.DataFrame({f'{k[0]} {k[1]} {k[2]}': T.groupby(T.entry.dt.year).R.mean() for k, T in KEEP.items()}); N = pd.DataFrame({f'{k[0]} {k[1]} {k[2]}': T.groupby(T.entry.dt.year).size() for k, T in KEEP.items()})
print(Y.round(2).to_string()); print(N.fillna(0).astype(int).to_string())
print('\nPer moneta, verifica:'); print(pd.DataFrame({f'{k[0]} {k[1]} {k[2]}': T[T.entry >= lib.SPLIT].groupby('coin').R.mean() for k, T in KEEP.items()}).round(3).to_string())
# aritmetica dell'obiettivo: N*(R/sigma)^2
print('\nAritmetica (N per anno x (R medio/sigma_R)^2; serve ~6,3 per il 30% al mese a Kelly pieno):')
for k, T in KEEP.items():
    for nm, g in (('tutto', T), ('verifica', T[T.entry >= lib.SPLIT])):
        y = (g.entry.max() - g.entry.min()).days / 365.25; print(f"  {k[0]} {k[1]:4s} {k[2]:4s} {nm:8s}: N/anno={len(g)/y:6.1f}  R/sigma={g.R.mean()/g.R.std():+.3f}  N*(R/sigma)^2={len(g)/y*(g.R.mean()/g.R.std())**2*np.sign(g.R.mean()):+.2f}")
out = []
for k, T in KEEP.items():
    if k[0] == 'C' and k[2] == 'alta':
        t = T.copy(); t['libro'] = 'GQ alta 1xATR' if k[1] == 'gq' else 'conviction alta 1xATR (riferimento)'; out.append(t)
TR = pd.concat(out, ignore_index=True)[['libro', 'coin', 'entry', 'exit', 'side', 's', 'L', 'R', 'ret', 'why', 'days', 'gq', 'score']].rename(columns={'s': 'stop_dist', 'L': 'leverage'})
TR.to_parquet('trades.parquet')
idx = pd.date_range(TR.entry.min(), TR.exit.max(), freq='D'); RISK = 0.01
ret = pd.DataFrame({lab: (g.groupby('exit').R.sum() * RISK).reindex(idx).fillna(0.0) for lab, g in TR.groupby('libro')}); ret.to_parquet('returns.parquet')
print('\nreturns.parquet: rendimento giornaliero (P&L registrato il giorno di uscita) a rischio 1% del conto per trade, senza capitalizzazione dentro il giorno.')
print((ret.mean() * 365).round(3).to_dict(), 'Sharpe annuo', (ret.mean() / ret.std() * np.sqrt(365)).round(2).to_dict(), 'verifica', (ret[ret.index >= lib.SPLIT].mean() / ret[ret.index >= lib.SPLIT].std() * np.sqrt(365)).round(2).to_dict())
print('varianti contate in questo script:', nvar, '(+ 2 prove di robustezza ciascuna)')
