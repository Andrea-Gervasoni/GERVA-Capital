"""A6 - giorni di depeg delle stablecoin. SIMULATO. Fonte: candele spot 1h Binance di USDC, BUSD, TUSD, DAI, FDUSD contro USDT.
Evento: una stablecoin chiude l'ora a piu' dello 0,5% (o 1%) dalla parita' con USDT; un evento ogni 7 giorni per coppia; eventi
entro 48 ore su coppie diverse sono lo stesso evento. Trade: long (o short) BTC/ETH/SOL perp per 24h o 72h dall'ora successiva."""
import lib; from lib import *
from gerva.data.sources import binance_klines
lib.CLU = '7D'
PX = {}
for s in ('USDC', 'BUSD', 'TUSD', 'DAI', 'FDUSD'):
    k = f'v5_a6_spot_1h_{s}USDT'
    try:
        if not st.has(k): st.put(k, binance_klines(s + 'USDT', '1h', 'spot', '2019-09'), 'binance.vision')
        PX[s] = st.get(k)['close']
    except Exception as e: print('manca', s, str(e)[:80])
P = pd.DataFrame(PX).loc['2020-02-01':]
print('coppie:', {s: (str(P[s].first_valid_index())[:10], str(P[s].last_valid_index())[:10]) for s in P})
def events(thr):
    ev = []
    for s in P:
        x = (P[s] - 1).abs(); last = None
        for t in x.index[(x > thr).values]:
            if last is None or (t - last) >= pd.Timedelta(days=7): ev.append((t + pd.Timedelta(hours=1), s, float(P[s][t]))); last = t
    ev = sorted(ev); out = []
    for e in ev:
        if not out or (e[0] - out[-1][0]) > pd.Timedelta(hours=48): out.append(e)
    return out
for thr in (0.005, 0.01):
    E = events(thr); print(f'\nsoglia {thr:.1%}: {len(E)} eventi ({len(E) / 6.75:.1f} per anno)')
    for e in E: print('   ', e[0], e[1], round(e[2], 4))
    for H in (24, 72):
        for side, nm in ((1, 'long'), (-1, 'short')):
            def fn(cm, delay, H=H, side=side, E=E):
                return pd.concat([run(bars(c), pd.DataFrame(dict(t=[e[0] for e in E], side=side)), H=H * 12, cm=cm, delay=delay) for c in ('BTC', 'ETH', 'SOL')])
            report(f'depeg >{thr:.1%}: {nm} BTC/ETH/SOL {H}h', fn, 'depeg')
save('depeg')
