"""A3 - scarico barre 5m dei perpetual USDT-M Binance (data.binance.vision) CON volume taker. Chiavi v5_um_5m_<SYM>."""
import sys, warnings, concurrent.futures as cf
sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import pandas as pd
from gerva.data.sources import Store, _get, _zip_csv, _KCOLS, _months, _to_ts, _clean
st = Store('/home/user/GERVA-Capital/data_cache')
SYMS = "BTC ETH SOL BNB XRP DOGE ADA LTC LINK AVAX".split()
base = "https://data.binance.vision/data/futures/um/monthly/klines"
def kl(sym):
    def one(m):
        raw = _get(f"{base}/{sym}/5m/{sym}-5m-{m}.zip", allow_404=True, timeout=60)
        if raw is None: return None
        d = _zip_csv(raw, _KCOLS); d.columns = _KCOLS[:len(d.columns)]; return d
    with cf.ThreadPoolExecutor(8) as ex:
        parts = [p for p in ex.map(one, list(_months('2020-01', '2026-10'))) if p is not None and len(p)]
    d = pd.concat(parts, ignore_index=True)
    out = d[["open", "high", "low", "close", "volume", "quote_volume", "trades", "taker_quote"]].astype(float)
    out.index = _to_ts(d["open_time"])
    out = out[~out.index.duplicated()].sort_index()
    return out
for c in SYMS:
    k = f'v5_um_5m_{c}USDT'
    if st.has(k): print('gia', k); continue
    try:
        d = kl(c + 'USDT'); st.put(k, d, 'binance.vision um 5m'); print('ok', k, len(d), d.index[0], d.index[-1], flush=True)
    except Exception as e: print('FAIL', k, str(e)[:200], flush=True)
