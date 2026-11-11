"""A8 - dati aggiuntivi: candele orarie Binance con volume taker-buy (spot dal 2017-08, perp USDT-M dal 2020-01).
La cache v4 non conserva la colonna taker; qui la riscarico (archivio pubblico data.binance.vision). Chiavi v5_a8_*."""
import sys, warnings, concurrent.futures as cf; sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import pandas as pd
from gerva.data.sources import Store, _get, _zip_csv, _KCOLS, _to_ts, _months, _clean
st = Store('/home/user/GERVA-Capital/data_cache')
def kl(symbol, market, start):
    base = ("https://data.binance.vision/data/spot/monthly/klines" if market == "spot" else "https://data.binance.vision/data/futures/um/monthly/klines")
    def one(m):
        raw = _get(f"{base}/{symbol}/1h/{symbol}-1h-{m}.zip", allow_404=True, timeout=60)
        if raw is None: return None
        d = _zip_csv(raw, _KCOLS); d.columns = _KCOLS[:len(d.columns)]; return d
    with cf.ThreadPoolExecutor(8) as ex: parts = [p for p in ex.map(one, list(_months(start, '2026-10'))) if p is not None and len(p)]
    d = pd.concat(parts, ignore_index=True)
    out = d[["open", "high", "low", "close", "volume", "quote_volume", "trades", "taker_base", "taker_quote"]].astype(float)
    out.index = _to_ts(d["open_time"]); return _clean(out)
for c in ('BTC', 'ETH', 'SOL'):
    for mk, s0 in (('spot', '2017-08'), ('um', '2020-01')):
        k = f'v5_a8_{mk}_1h_{c}'
        if st.has(k): continue
        d = kl(c + 'USDT', mk, s0); st.put(k, d, 'binance.vision'); print(k, d.shape, d.index[0], d.index[-1], flush=True)
