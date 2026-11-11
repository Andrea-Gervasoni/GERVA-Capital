"""Lab v4 - scarico dei dati reali (tutto pubblico, senza chiave). Scrive in data_cache/ con prefisso v4_.
Uso: /tmp/gv/bin/python research/v5/v4/00_dati.py [klines|fund|metrics|hl|misc|m5]"""
import sys, warnings, json, time, io, zipfile, urllib.request, concurrent.futures as cf
sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from gerva.data.sources import Store, binance_klines, binance_funding, _get, _zip_csv, DataError
st = Store('/home/user/GERVA-Capital/data_cache')
# universo perpetual: i piu' scambiati + due morti (LUNA, FTT) contro il survivorship bias
PERP = ("BTC ETH SOL BNB XRP DOGE ADA LTC LINK AVAX DOT BCH ETC ATOM NEAR FIL UNI AAVE TRX XLM MATIC APT ARB OP SUI "
        "INJ SEI TIA WIF TON RUNE HBAR LUNA FTT EOS SAND").split()
what = sys.argv[1:] or ['klines', 'fund', 'm5', 'misc', 'hl', 'metrics']

def safe(key, fn, src):
    if st.has(key): return
    try:
        d = fn()
        if isinstance(d, pd.Series): d = d.to_frame()
        st.put(key, d, src); print('ok', key, len(d), flush=True)
    except Exception as e:
        print('FAIL', key, str(e)[:120], flush=True)

if 'klines' in what:
    for c in PERP:
        safe(f'v4_um_1h_{c}USDT', lambda: binance_klines(c + 'USDT', '1h', 'um', '2020-01'), 'binance.vision')
        safe(f'v4_spot_1h_{c}USDT', lambda: binance_klines(c + 'USDT', '1h', 'spot', '2020-01'), 'binance.vision')
if 'fund' in what:
    for c in PERP:
        safe(f'bn_fund_{c}USDT', lambda: binance_funding(c + 'USDT'), 'binance.vision')
if 'm5' in what:
    for c in ('BTC', 'ETH', 'SOL'):
        safe(f'v4_um_5m_{c}USDT', lambda: binance_klines(c + 'USDT', '5m', 'um', '2020-01'), 'binance.vision')
if 'misc' in what or 'cm' in what:
    def dvol(cur):
        out = []; end = int(time.time() * 1000); start = int(pd.Timestamp('2021-03-01').timestamp() * 1000)
        while True:
            j = json.loads(_get(f'https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={cur}&start_timestamp={start}&end_timestamp={end}&resolution=1D'))['result']
            out += j['data']
            if not j.get('continuation'): break
            end = j['continuation']
        d = pd.DataFrame(out, columns=['t', 'open', 'high', 'low', 'close']); d.index = pd.to_datetime(d['t'], unit='ms')
        return d.drop(columns='t').sort_index().loc[lambda x: ~x.index.duplicated()]
    for cur in ('BTC', 'ETH'): safe(f'v4_dvol_{cur}', lambda: dvol(cur), 'deribit')
    def fng():
        j = json.loads(_get('https://api.alternative.me/fng/?limit=0'))['data']
        s = pd.Series({pd.to_datetime(int(x['timestamp']), unit='s'): float(x['value']) for x in j}).sort_index(); return s.rename('fng')
    safe('v4_fng', fng, 'alternative.me')
    def stable():
        j = json.loads(_get('https://stablecoins.llama.fi/stablecoincharts/all'))
        s = pd.Series({pd.to_datetime(int(x['date']), unit='s'): float(x['totalCirculatingUSD']['peggedUSD']) for x in j}).sort_index(); return s.rename('stable')
    safe('v4_stable', stable, 'defillama')
    def cm(asset):
        mets = 'PriceUSD,CapMrktCurUSD,CapMVRVCur,FlowInExUSD,FlowOutExUSD,AdrActCnt,SplyExNtv'
        url = f'https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets={asset}&metrics={mets}&frequency=1d&page_size=10000&start_time=2017-01-01'
        rows = []
        while url:
            j = json.loads(_get(url)); rows += j['data']; url = j.get('next_page_url')
        d = pd.DataFrame(rows); d.index = pd.to_datetime(d['time']).dt.tz_localize(None); return d[mets.split(',')].apply(pd.to_numeric, errors='coerce')
    for a in ('btc', 'eth'): safe(f'v4_cm_{a}', lambda: cm(a), 'coinmetrics community')
if 'hl' in what:
    def post(body):
        for k in range(6):
            try:
                req = urllib.request.Request('https://api.hyperliquid.xyz/info', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read())
            except Exception as e:
                last = e; time.sleep(2 + 3 * k)
        raise DataError(str(last))
    def hl_f(c):
        t = int(pd.Timestamp('2023-05-01').timestamp() * 1000); out = []
        while True:
            j = post(dict(type='fundingHistory', coin=c, startTime=t))
            if not j: break
            out += j; t2 = j[-1]['time'] + 1
            if len(j) < 500 or t2 <= t: break
            t = t2; time.sleep(0.25)
        d = pd.DataFrame(out); d.index = pd.to_datetime(d['time'], unit='ms').dt.floor('h')
        return d[['fundingRate', 'premium']].astype(float).loc[lambda x: ~x.index.duplicated()]
    def hl_c(c, itv):
        j = post(dict(type='candleSnapshot', req=dict(coin=c, interval=itv, startTime=int(pd.Timestamp('2023-01-01').timestamp() * 1000), endTime=int(time.time() * 1000))))
        d = pd.DataFrame(j); d.index = pd.to_datetime(d['t'], unit='ms')
        return d[['o', 'h', 'l', 'c', 'v']].astype(float).rename(columns=dict(o='open', h='high', l='low', c='close', v='volume'))
    for c in "BTC ETH SOL BNB XRP DOGE ADA LTC LINK AVAX SUI ARB OP APT NEAR HYPE".split():
        safe(f'v4_hl_fund_{c}', lambda: hl_f(c), 'hyperliquid'); safe(f'v4_hl_1d_{c}', lambda: hl_c(c, '1d'), 'hyperliquid'); safe(f'v4_hl_1h_{c}', lambda: hl_c(c, '1h'), 'hyperliquid')
if 'metrics' in what:
    def met(c):
        days = pd.date_range('2021-12-01', pd.Timestamp.utcnow().tz_localize(None).normalize() - pd.Timedelta(days=1))
        def one(d):
            try:
                raw = _get(f'https://data.binance.vision/data/futures/um/daily/metrics/{c}USDT/{c}USDT-metrics-{d:%Y-%m-%d}.zip', allow_404=True, tries=3)
            except Exception: return None
            if raw is None: return None
            x = _zip_csv(raw); x.index = pd.to_datetime(x['create_time']); return x.drop(columns=['create_time', 'symbol']).astype(float)
        with cf.ThreadPoolExecutor(24) as ex: parts = [p for p in ex.map(one, days) if p is not None]
        d = pd.concat(parts).sort_index(); d = d[~d.index.duplicated()]
        return d.resample('1h').last()      # valore all'ultimo campione dell'ora (indice = inizio ora)
    for c in "BTC ETH SOL BNB XRP DOGE ADA LINK AVAX LTC".split(): safe(f'v4_metrics_1h_{c}', lambda: met(c), 'binance.vision')
print('fine', what)
