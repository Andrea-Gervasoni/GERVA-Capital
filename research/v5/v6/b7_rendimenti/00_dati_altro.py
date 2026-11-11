"""B7 - scarico delle altre sorgenti pubbliche: Kraken Futures, OKX, Deribit (funding perps + futures datati), DefiLlama yields e prezzi.
Cache: data_cache/v6_b7/*.parquet. Nessun dato privato inviato."""
import json, os, time, urllib.request, urllib.parse, pandas as pd, numpy as np, concurrent.futures as cf
D='/home/user/GERVA-Capital/data_cache/v6_b7/'
def get(url,tries=5):
    for k in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'research-client'}),timeout=60).read())
        except Exception as e: err=e; time.sleep(2*(k+1))
    raise err
def cached(name,fn):
    p=D+name+'.parquet'
    if os.path.exists(p): return pd.read_parquet(p)
    d=fn(); d.to_parquet(p); print(name,d.shape,d.index[0] if len(d) else None,d.index[-1] if len(d) else None,flush=True); return d
# ---- Kraken Futures
def kr_all():
    tk=[x for x in get('https://futures.kraken.com/derivatives/api/v3/tickers')['tickers'] if x['symbol'].startswith('PF_')]
    tk.sort(key=lambda x:-float(x.get('volumeQuote',0) or 0)); out={}
    for x in tk[:60]:
        try:
            r=get('https://futures.kraken.com/derivatives/api/v4/historicalfundingrates?symbol='+x['symbol'])['rates']
            out[x['symbol']]=pd.Series({pd.Timestamp(a['timestamp']).tz_localize(None):a['relativeFundingRate'] for a in r})
        except Exception as e: print('kr fail',x['symbol'],e)
    d=pd.DataFrame(out).sort_index(); d.attrs={}; return d
kr=cached('kraken_fund',kr_all)
pd.Series({x['symbol']:float(x.get('volumeQuote',0) or 0) for x in get('https://futures.kraken.com/derivatives/api/v3/tickers')['tickers'] if x['symbol'].startswith('PF_')}).to_frame('vol').to_parquet(D+'kraken_vol.parquet')
# ---- OKX
def okx_all():
    out={}
    for c in ['BTC','ETH','SOL','XRP','DOGE','HYPE','ADA','LINK','SUI','AVAX','BNB','LTC','ZEC','PEPE','TRX','NEAR','AAVE','UNI','TON','DOT']:
        rows=[]; after=''
        for _ in range(60):
            r=get(f'https://www.okx.com/api/v5/public/funding-rate-history?instId={c}-USDT-SWAP&limit=100'+(f'&after={after}' if after else ''))['data']
            if not r: break
            rows+=[(int(a['fundingTime']),float(a['realizedRate'])) for a in r]; after=r[-1]['fundingTime']; time.sleep(0.12)
        if rows: out[c]=pd.Series({pd.Timestamp(t,unit='ms'):v for t,v in rows})
    return pd.DataFrame(out).sort_index()
okx=cached('okx_fund',okx_all)
# ---- Deribit perps
def der(inst):
    def f():
        rows=[]; t=int(pd.Timestamp('2019-01-01').value//10**6); now=int(time.time()*1000)
        while t<now:
            r=get(f'https://www.deribit.com/api/v2/public/get_funding_rate_history?instrument_name={inst}&start_timestamp={t}&end_timestamp={t+700*3600_000}')['result']
            rows+=[(a['timestamp'],a['interest_1h'],a['index_price']) for a in r]; t+=700*3600_000
        d=pd.DataFrame(rows,columns=['t','f','idx']).drop_duplicates('t'); d.index=pd.to_datetime(d.pop('t'),unit='ms'); return d.sort_index()
    return f
for inst in ['BTC-PERPETUAL','ETH-PERPETUAL','SOL_USDC-PERPETUAL','BTC_USDC-PERPETUAL','ETH_USDC-PERPETUAL']:
    try: cached('deribit_fund_'+inst,der(inst))
    except Exception as e: print('deribit fail',inst,e)
# ---- Deribit futures trimestrali (scaduti compresi): chiusure giornaliere
def quarterlies(y0=2019,y1=2027):
    out=[]
    for y in range(y0,y1+1):
        for m in (3,6,9,12):
            d=pd.Timestamp(year=y,month=m,day=1)+pd.offsets.MonthEnd(0)
            while d.weekday()!=4: d-=pd.Timedelta(days=1)
            out.append(d)
    return out
def der_fut(cur):
    def f():
        out={}
        for d in quarterlies():
            nm=f"{cur}-{d.day}{d.strftime('%b').upper()}{d.strftime('%y')}"
            a=int((d-pd.Timedelta(days=300)).value//10**6); z=int((d+pd.Timedelta(days=1)).value//10**6)
            try:
                r=get(f'https://www.deribit.com/api/v2/public/get_tradingview_chart_data?instrument_name={nm}&start_timestamp={a}&end_timestamp={z}&resolution=1D',tries=2)['result']
                if r.get('ticks'): out[nm]=pd.Series(r['close'],index=pd.to_datetime(r['ticks'],unit='ms'))
            except Exception as e: print('fut skip',nm,str(e)[:60])
        return pd.DataFrame(out).sort_index()
    return f
for cur in ['BTC','ETH']: cached('deribit_fut_'+cur,der_fut(cur))
# ---- DefiLlama yields
POOLS={'lido_steth':'747c1d2a-c668-4682-b9f9-296708a3dd90','jitosol':'0e7d0722-9054-4907-8593-567b353c0900','aave_usdc':'aa70268e-4b52-42bf-a116-608b370f9501',
'comp_usdc':'7da72d09-56ca-4ec5-a45f-59114353e487','morpho_steakusdc':'931ea9be-5f4d-428e-beaf-205fc5b4e2b5','susde':'66985a81-9c51-46ca-9977-42b4fe7bc6df',
'susds':'d8c4eff5-c8a9-46fc-a888-057c4c668e72','spark_usdc':'c5c74dd1-995c-4445-9d84-3e710bad7d52','pendle_pt_susde':'fc9a73bc-8ccc-5701-9007-1aeb68ff6a51',
'usdy':'ac61ee82-2fe4-4f9b-a9cd-7fb33f598859','buidl':'bd0f5a2a-5d74-40bd-a7db-bf1538b314a2','hl_usdc_earn':'6cd85774-b80b-5fd4-8194-7b4126b24634',
'hlp':'c676790b-ba37-5aa8-9ccf-d9a533daafdc','fluid_usdc':'4438dabc-7f0c-430b-8136-2722711ae663','aave_usdt':'f981a304-bb6c-45b8-b0c5-fd2f515ad23a','wbeth':'80b8bf92-b953-4c20-98ea-c9653ef2bb98','reth':'d4b3c522-6127-4b89-bedf-83641cdcd2eb'}
def yl():
    out={};tv={}
    for k,p in POOLS.items():
        try:
            r=get('https://yields.llama.fi/chart/'+p)['data']; ix=pd.to_datetime([a['timestamp'][:10] for a in r])
            out[k]=pd.Series([a['apy'] for a in r],index=ix); tv[k+'_tvl']=pd.Series([a['tvlUsd'] for a in r],index=ix); time.sleep(0.3)
        except Exception as e: print('yield fail',k,e)
    f=lambda o: pd.DataFrame({k:v[~v.index.duplicated()] for k,v in o.items()}).sort_index()
    return pd.concat([f(out),f(tv)],axis=1)
cached('llama_yields',yl)
# ---- prezzi (DefiLlama coins)
def px():
    out={}
    for c in ['staked-ether','ethereum','wrapped-steth','jito-staked-sol','solana','ethena-staked-usde','ethena-usde','usd-coin','tether','dai','terrausd','ondo-us-dollar-yield','msol','hyperliquid']:
        s={}; t=int(pd.Timestamp('2020-12-01').timestamp()); now=int(time.time())
        while t<now:
            try:
                r=get(f'https://coins.llama.fi/chart/coingecko:{c}?start={t}&span=400&period=1d',tries=3)['coins'].get('coingecko:'+c,{}).get('prices',[])
            except Exception as e: print('px fail',c,e); r=[]
            for a in r: s[pd.Timestamp(a['timestamp'],unit='s').normalize()]=a['price']
            t+=400*86400; time.sleep(0.2)
        if s: out[c]=pd.Series(s)
    return pd.DataFrame(out).sort_index()
cached('llama_px',px)
print('fatto')
