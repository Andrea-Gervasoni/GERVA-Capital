"""A6 - nuove quotazioni di perpetual su Binance (data di quotazione = prima candela nell'archivio data.binance.vision). SIMULATO.
Scarica le candele 1h del mese di quotazione e del successivo per ogni perp USDT-M quotato dal 2020-03. Funding: quello giornaliero
reale (v4_allperp_fund). Stop = 1,5 x sigma oraria delle prime 24 ore x sqrt(ore), massimo 15%. t-stat della somma settimanale.
Le rimozioni dal listino (delisting) non sono verificabili: l'archivio da' l'ultima candela, non la data dell'ANNUNCIO (che e' l'evento)."""
import lib; from lib import *
import concurrent.futures as cf
from gerva.data.sources import binance_klines
lib.CLU = '7D'
C = st.get('v4_allperp_close'); FU = st.get('v4_allperp_fund')
first = C.apply(lambda s: s.first_valid_index()); syms = [s for s in C.columns if first[s] >= pd.Timestamp('2020-03-01') and first[s] <= pd.Timestamp('2026-08-31')]
KEY = 'v5_a6_listing_1h'
if not st.has(KEY):
    def one(s):
        m0 = first[s].strftime('%Y-%m'); m1 = (first[s] + pd.offsets.MonthBegin(1)).strftime('%Y-%m')
        try:
            d = binance_klines(s, '1h', 'um', m0, m1, workers=2); d = d.iloc[:24 * 40].copy(); d['sym'] = s; return d
        except Exception as e: return None
    with cf.ThreadPoolExecutor(12) as ex: parts = [p for p in ex.map(one, syms) if p is not None]
    D = pd.concat(parts); D.index.name = 't'; st.put(KEY, D.reset_index(), 'binance.vision')
D = st.get(KEY); print('simboli scaricati:', D.sym.nunique(), 'su', len(syms))
BB = {}
for s, d in D.groupby('sym'):
    d = d.set_index('t').sort_index()
    if len(d) < 24 * 12: continue
    B = Bars(s[:-4], '1h', df=d[['open', 'high', 'low', 'close', 'volume', 'quote_volume']])
    f = FU[s].dropna() if s in FU else pd.Series(dtype=float)
    B.ft = (f.index + pd.Timedelta(hours=23, minutes=59)).values.astype('datetime64[ns]').astype(np.int64); B.fv = f.values; B.fcum = np.concatenate([[0.0], np.cumsum(B.fv)])
    r = np.log(d['close']).diff(); B.s24 = float(r.iloc[1:24].std()); B.r24 = float(d['close'].iloc[23] / d['open'].iloc[0] - 1); B.r1 = float(d['close'].iloc[0] / d['open'].iloc[0] - 1)
    BB[s] = B
print('simboli utilizzabili:', len(BB), '| per anno:', pd.Series([pd.Timestamp(B.t[0]).year for B in BB.values()]).value_counts().sort_index().to_dict())
def fam(off_h, H, side, cond=None):
    def fn(cm, delay):
        out = []
        for s, B in BB.items():
            if cond is not None and not cond(B): continue
            i = off_h + delay
            if i + H >= len(B.t) or not np.isfinite(B.s24) or B.s24 <= 0: continue
            sd = side if isinstance(side, int) else int(np.sign(B.r24) or 1) * (1 if side == 'cont' else -1)
            sg = B.s24 if off_h >= 24 else 0.03                              # prima delle 24h la volatilita' non e' nota: 3%/ora fisso
            r = sim(B, i, sd, float(np.clip(1.5 * sg * np.sqrt(H), 0.003, 0.15)), H, cm=cm)
            if r: r['t_dec'] = pd.Timestamp(B.t[off_h]); out.append(r)
        return pd.DataFrame(out)
    return fn
print('\n=== dopo le prime 24 ore')
for H in (24, 72, 168):
    report(f'short a +24h, tengo {H}h', fam(24, H, -1), 'listing')
report('long a +24h, tengo 24h', fam(24, 24, 1), 'listing')
report('a +24h nella direzione delle prime 24h, tengo 24h', fam(24, 24, 'cont'), 'listing')
report('a +24h contro le prime 24h, tengo 24h', fam(24, 24, 'rev'), 'listing')
report('short a +24h se le prime 24h > +20%, tengo 72h', fam(24, 72, -1, lambda B: B.r24 > 0.2), 'listing')
report('short a +24h se le prime 24h < -20%, tengo 72h', fam(24, 72, -1, lambda B: B.r24 < -0.2), 'listing')
print('=== subito (stop fisso 1,5 x 3% x sqrt(ore), max 15%)')
report('short a +1h, tengo 23h', fam(1, 23, -1), 'listing')
report('long a +1h, tengo 23h', fam(1, 23, 1), 'listing')
report('short a +1h se la prima ora > +10%, tengo 23h', fam(1, 23, -1, lambda B: B.r1 > 0.10), 'listing')
print('=== una settimana dopo')
report('short a +168h, tengo 168h', fam(168, 168, -1), 'listing')
save('listing')
