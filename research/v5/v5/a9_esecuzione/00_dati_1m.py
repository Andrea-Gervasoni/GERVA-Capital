"""A9 - scarico barre a 1 minuto dei perpetual USDT-M (data.binance.vision) per BTC, ETH, SOL. Cache: v5_um_1m_*."""
import sys, warnings; sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
from gerva.data.sources import Store, binance_klines
st = Store('/home/user/GERVA-Capital/data_cache')
for c in ('BTC', 'ETH', 'SOL'):
    k = f'v5_um_1m_{c}USDT'
    if st.has(k): print('gia in cache', k); continue
    try:
        d = binance_klines(c + 'USDT', '1m', 'um', '2020-01', workers=6)
        st.put(k, d, 'binance.vision'); print('ok', k, d.shape, d.index[0], d.index[-1], flush=True)
    except Exception as e: print('FAIL', k, str(e)[:200], flush=True)
