"""A1 - controlli: (1) troncamento: GQ ricalcolato su dati tagliati al giorno t deve coincidere; (2) bootstrap a blocchi mensili della
differenza tra libro GQ e libro conviction; (3) da dove viene la differenza: incrocio ingresso/uscita; (4) seconda derivazione del R medio
del libro GQ con il simulatore ORIGINALE (leva_trade_isolato.trades con CONV sostituita). SIMULATO."""
import json, importlib.util, numpy as np, pandas as pd, lib, indicatore, feat
import leva_trade_isolato as L
spec = importlib.util.spec_from_file_location('libro', '04_libro.py')
pd.set_option('display.width', 250); fz = json.load(open('congelato.json')); rng = np.random.default_rng(11)
# ---------- (1) troncamento ----------
bad = 0; tot = 0; mx = 0.0
for c in feat.COINS:
    b = L.B[c]; tk = lib.st.get(f'v5_spot_1d_tk_{c}'); P = feat.PATH[c]; full = indicatore.gq(P.d, tk['volume'], feat.PATH['BTC'].d['close'])
    for t in rng.choice(P.d.index[300:], 40, replace=False):
        t = pd.Timestamp(t); cut = t + pd.Timedelta(days=1)
        bc = b[b.index < cut]; g = bc.groupby(bc.index.normalize()); d = pd.DataFrame(dict(open=g['open'].first(), high=g['high'].max(), low=g['low'].min(), close=g['close'].last()))
        bb = L.B['BTC']; bb = bb[bb.index < cut]; btc = bb.groupby(bb.index.normalize())['close'].last()
        v = indicatore.gq(d, tk['volume'][tk.index < cut], btc).iloc[-1]; e = abs(v - full.loc[t]); mx = max(mx, e); tot += 1; bad += e > 1e-9
print(f'(1) troncamento: {tot} date a caso, differenze > 1e-9: {bad}, differenza massima {mx:.2e}')
vol5 = {c: L.B[c]['volume'].groupby(L.B[c].index.normalize()).sum() for c in feat.COINS}
print('    volume giornaliero: file con taker vs somma dei 5 minuti, scarto relativo mediano:', {c: float(((lib.st.get(f"v5_spot_1d_tk_{c}")["volume"] / vol5[c] - 1).abs()).median()) for c in feat.COINS})
# ---------- libri ----------
GQ = {}; SC = {}
for c in feat.COINS:
    P = feat.PATH[c]; GQ[c] = indicatore.gq(P.d, lib.st.get(f'v5_spot_1d_tk_{c}')['volume'], feat.PATH['BTC'].d['close']).shift(1).values; SC[c] = L.CONV[c]['score'].values
def book(en_kind, ex_kind, conv='C'):
    out = []
    for c in feat.COINS:
        g = GQ[c]; s = SC[c]; en = ((s > 0.60) if en_kind == 'conv' else (g >= fz['alta'])) & ~np.isnan(s); ex = ~(s > 0.30) if ex_kind == 'conv' else ~(g > fz['bassa'])
        if ex_kind == 'none': ex = np.zeros(len(s), bool)
        T = feat.PATH[c].book(en, ex, **(dict(atr_k=1.0, trail=2.0) if conv == 'C' else dict(s=0.017, atr_k=None, trail=None))); T['coin'] = c; out.append(T)
    return pd.concat(out, ignore_index=True)
def bootdiff(A, B, n=4000):
    out = {}
    for per, fa in (('tutto', lambda x: x), ('scelta', lambda x: x[x.entry < lib.SPLIT]), ('verifica', lambda x: x[x.entry >= lib.SPLIT])):
        a = fa(A); b = fa(B); ma = a.entry.dt.to_period('M'); mb = b.entry.dt.to_period('M'); idx = sorted(set(ma) | set(mb))
        G = np.array([(a.R[ma == m].sum(), (ma == m).sum(), b.R[mb == m].sum(), (mb == m).sum()) for m in idx], float)
        s = G[rng.integers(0, len(G), (n, len(G)))].sum(axis=1); d = s[:, 0] / s[:, 1] - s[:, 2] / s[:, 3]
        out[per] = (round(a.R.mean() - b.R.mean(), 3), np.percentile(d, [5, 95]).round(3).tolist(), round(float((d > 0).mean()), 3))
    return out
print('\n(2) differenza di R medio, libro GQ alta - libro conviction alta: (differenza, [5%,95%], P(>0)); blocchi = mesi')
for conv in ('C', 'A'):
    print('   ', conv, bootdiff(book('gq', 'gq', conv), book('conv', 'conv', conv)))
print('\n(3) incrocio ingresso/uscita (diagnostica, NON candidati):')
rows = []
for conv in ('C', 'A'):
    for en in ('conv', 'gq'):
        for ex in ('conv', 'gq', 'none'):
            T = book(en, ex, conv); r = lib.three(T); rows.append(dict(conv=conv, ingresso=en, uscita=ex, n=r['n'], R=r['R'], t=r['t'], R_scelta=r['R_sc'], R_verifica=r['R_ve'], t_ver=r['t_ve'], giorni=T.days.mean(), stop=(T.why == 'stop').mean()))
print(pd.DataFrame(rows).round(3).to_string(index=False))
# ---------- (4) seconda derivazione con il simulatore originale ----------
keep = {c: L.CONV[c].copy() for c in feat.COINS}
for c in feat.COINS:
    g = GQ[c]; cv = L.CONV[c].copy(); cv['tier'] = np.where(g >= fz['alta'], 'alta', np.where(g > fz['bassa'], 'media', 'bassa')); cv.loc[np.isnan(SC[c]) , 'tier'] = 'bassa'; L.CONV[c] = cv
O = pd.concat([L.trades(c, 0, ('alta',), atr_k=1.0, trail=2.0) for c in feat.COINS]); N = book('gq', 'gq', 'C')
print(f'\n(4) libro GQ alta 1xATR con il simulatore ORIGINALE: n={len(O)} R={O.R.mean():+.4f} | con il mio: n={len(N)} R={N.R.mean():+.4f}')
for c in feat.COINS: L.CONV[c] = keep[c]
