"""A3/3 - studio a eventi: deriva LORDA (pb) dopo la prima chiusura 5m oltre il massimo/minimo a N barre, per orizzonte.
Serve a capire dove (se da qualche parte) la deriva lorda supera i costi (13 pb andata e ritorno, 18 pb con stop). SIMULATO."""
from lab import *
HZ = {'1h': 12, '4h': 48, '12h': 144, '24h': 288, '72h': 864}
NS = {'6h': 72, '24h': 288, '3g': 864, '7g': 2016, '30g': 8640}
def events(c):
    b = load(c); cl = b['close']; o = b['open'].values; n = len(b); out = []
    lr = np.log(cl).diff(); hv = (lr.rolling(288).std() * np.sqrt(12))
    rv = b['quote_volume'] / b['quote_volume'].rolling(288).median()
    share = (b['taker_quote'] / b['quote_volume'].replace(0, np.nan)).fillna(0.5)
    hvr = hv.rolling(8640).rank(pct=True)                   # percentile della vol su 30 giorni
    for nm, N in NS.items():
        hh = b['high'].rolling(N).max().shift(1); ll = b['low'].rolling(N).min().shift(1)
        up = (cl > hh); dn = (cl < ll)
        # primo attraversamento: nessuna rottura dallo stesso lato nelle N/4 barre precedenti
        fu = up & (up.shift(1).rolling(max(N // 4, 12)).sum() == 0); fd = dn & (dn.shift(1).rolling(max(N // 4, 12)).sum() == 0)
        for side, f in ((1, fu), (-1, fd)):
            i = np.flatnonzero(f.values); i = i[i < n - 870]
            d = dict(symbol=c, N=nm, side=side, t=b.index[i], hv=hv.values[i], rv=rv.values[i], share=share.values[i], hvr=hvr.values[i], hour=b.index[i].hour, dow=b.index[i].dayofweek)
            for hn, H in HZ.items(): d[hn] = side * (o[i + 1 + H] / o[i + 1] - 1) * 1e4
            d['d1'] = side * (o[i + 2 + 288] / o[i + 2] - 1) * 1e4      # ritardo di una barra, 24h
            out.append(pd.DataFrame(d))
    return pd.concat(out, ignore_index=True)
def tcl(x, t):
    """media e t a grappoli per giorno."""
    g = x.groupby(t.dt.normalize()).sum(); k = x.groupby(t.dt.normalize()).count()
    if len(g) < 5: return np.nan, np.nan
    m = x.mean(); return m, g.mean() / g.std() * np.sqrt(len(g))
def tab(E, by, h):
    rows = []
    for k, g in E.groupby(by):
        r = dict(zip(by if isinstance(by, list) else [by], k if isinstance(k, tuple) else [k])); r['n'] = len(g)
        for nm, m in (('sel', g.t < SPLIT), ('ver', g.t >= SPLIT)):
            mu, t = tcl(g.loc[m, h], g.loc[m, 't']); r[f'{h}_{nm}'] = mu; r[f't_{nm}'] = t
        rows.append(r)
    return pd.DataFrame(rows)
if __name__ == '__main__':
    import os
    if os.path.exists('eventi.parquet'): E = pd.read_parquet('eventi.parquet')
    else: E = pd.concat([events(c) for c in SYMS], ignore_index=True); E.to_parquet('eventi.parquet')
    pd.set_option('display.width', 250)
    print('eventi:', len(E)); nt = 0
    print('\n== deriva lorda media (pb) per lookback x orizzonte: SCELTA | VERIFICA  [t a grappoli per giorno]')
    for h in HZ:
        T = tab(E, 'N', h).set_index('N').loc[list(NS)]; nt += len(T); print(f'-- orizzonte {h}'); print(T.round(2).to_string())
    print('\n== per lato (24h)'); T = tab(E, ['N', 'side'], '24h'); nt += len(T); print(T.round(2).to_string(index=False))
    E['volb'] = pd.cut(E.rv, [0, 2, 5, 1e9], labels=['vol<2', '2-5', '>5'])
    E['tkb'] = pd.cut(E.share * E.side + (1 - E.side) / 2, [-1, 0.45, 0.55, 0.65, 2], labels=['contro', 'neutro', 'a favore', 'molto a favore'])
    E['hvb'] = pd.cut(E.hvr, [0, 0.2, 0.5, 0.8, 1.01], labels=['vol bassa', 'medio-bassa', 'medio-alta', 'alta'])
    E['sess'] = pd.cut(E.hour, [-1, 6, 12, 20, 24], labels=['asia', 'europa', 'usa', 'sera'])
    E['we'] = E.dow >= 5
    for cond in ('volb', 'tkb', 'hvb', 'sess', 'we'):
        for h in ('4h', '24h'):
            T = tab(E[E.N.isin(['24h', '3g', '7g'])], [cond], h); nt += len(T); print(f'\n== lookback 24h/3g/7g, per {cond}, orizzonte {h}'); print(T.round(2).to_string(index=False))
    T = tab(E, ['N'], 'd1').set_index('N').loc[list(NS)]; print('\n== 24h con una barra di ritardo'); print(T.round(2).to_string())
    print('\ncelle guardate (contano come varianti):', nt)
    json.dump(dict(n=nt), open('trials_eventi.json', 'w'))
