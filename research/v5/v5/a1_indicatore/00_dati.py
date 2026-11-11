"""A1 - dati: candele giornaliere spot Binance CON volume taker-buy (la cache esistente lo scarta). Chiavi v5_spot_1d_tk_<COIN>.
Uso: /tmp/gv/bin/python research/v5/v5/a1_indicatore/00_dati.py"""
import sys, warnings, concurrent.futures as cf
sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import pandas as pd
from gerva.data.sources import Store, _get, _zip_csv, _KCOLS, _months, _to_ts, _clean
st = Store('/home/user/GERVA-Capital/data_cache')
UNI = "BTC ETH SOL BNB XRP DOGE ADA LTC LINK AVAX DOT BCH ETC ATOM TRX XLM UNI AAVE EOS LUNA FTT".split()
def kl(sym):
    base = "https://data.binance.vision/data/spot/monthly/klines"
    def one(m):
        raw = _get(f"{base}/{sym}/1d/{sym}-1d-{m}.zip", allow_404=True, timeout=60)
        if raw is None: return None
        d = _zip_csv(raw, _KCOLS); d.columns = _KCOLS[:len(d.columns)]; return d
    with cf.ThreadPoolExecutor(8) as ex:
        parts = [p for p in ex.map(one, list(_months('2017-08', None))) if p is not None and len(p)]
    d = pd.concat(parts, ignore_index=True)
    out = d[["open", "high", "low", "close", "volume", "quote_volume", "trades", "taker_base", "taker_quote"]].astype(float)
    out.index = _to_ts(d["open_time"]); return _clean(out)
for c in UNI:
    k = f'v5_spot_1d_tk_{c}'
    if st.has(k): print('gia', k); continue
    try:
        d = kl(c + 'USDT'); st.put(k, d, 'binance.vision'); print('ok', k, len(d), d.index[0], d.index[-1], flush=True)
    except Exception as e: print('FAIL', k, str(e)[:100], flush=True)
