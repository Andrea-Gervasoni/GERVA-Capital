"""A1 - sensibilita' alla fase: il libro sequenziale dipende dal giorno in cui parte (dopo ogni trade si rientra il giorno dopo).
Per togliere la fortuna della fase: (a) si parte da 7 giorni diversi; (b) dopo ogni uscita si aspetta k giorni (k=0..3). SIMULATO."""
import json, numpy as np, pandas as pd, lib, indicatore, feat
import leva_trade_isolato as L
pd.set_option('display.width', 250); fz = json.load(open('congelato.json'))
GQ = {}; SC = {}
for c in feat.COINS:
    P = feat.PATH[c]; GQ[c] = indicatore.gq(P.d, lib.st.get(f'v5_spot_1d_tk_{c}')['volume'], feat.PATH['BTC'].d['close']).shift(1).values; SC[c] = L.CONV[c]['score'].values
def book(kind, conv, i0=250, wait=0, lev='alta'):
    out = []
    for c in feat.COINS:
        P = feat.PATH[c]; g = GQ[c]; s = SC[c]; thr = dict(alta=(0.60, fz['alta']), ecc=(0.75, fz['ecc']))[lev]
        en = ((s > thr[0]) if kind == 'conv' else (g >= thr[1])) & ~np.isnan(s); ex = np.zeros(len(s), bool)
        pk = dict(atr_k=1.0, trail=2.0) if conv == 'C' else dict(s=0.017, atr_k=None, trail=None)
        i = i0; n = len(P.days)
        while i < n - 1:
            if not en[i] or np.isnan(P.atr[i]): i += 1; continue
            t = P.one(i, exitflag=ex, **pk); t['coin'] = c; out.append(t); i = t['j'] + 1 + wait
    return pd.DataFrame(out)
rows = []
for conv in ('C', 'A'):
    for lev in ('alta', 'ecc'):
        for kind in ('conv', 'gq'):
            R = [lib.three(book(kind, conv, i0=250 + k, lev=lev)) for k in range(7)]
            W = [lib.three(book(kind, conv, wait=k, lev=lev)) for k in range(1, 4)]
            f = lambda X, k: np.array([x[k] for x in X])
            rows.append(dict(conv=conv, livello=lev, ind=kind, R_medio_7_partenze=f(R, 'R').mean(), min=f(R, 'R').min(), max=f(R, 'R').max(), scelta=f(R, 'R_sc').mean(), verifica=f(R, 'R_ve').mean(),
                             ver_min=f(R, 'R_ve').min(), ver_max=f(R, 'R_ve').max(), attesa1_3_R=f(W, 'R').mean(), attesa1_3_scelta=f(W, 'R_sc').mean(), attesa1_3_ver=f(W, 'R_ve').mean(), n_medio=f(R, 'n').mean()))
print(pd.DataFrame(rows).round(3).to_string(index=False))
print('varianti di robustezza: 80 libri (non candidati)')
