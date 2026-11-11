"""B5 - eventi di split da Yahoo (leggero: barre trimestrali + events=splits) per ricostruire il prezzo REALE storico
(la chiusura Yahoo e' rettificata per gli split: serve il prezzo vero per commissione per azione e filtri di prezzo)."""
import sys, time, json, os, urllib.parse
sys.path.insert(0, '/home/user/GERVA-Capital'); os.chdir('/home/user/GERVA-Capital')
import pandas as pd
from gerva.data.sources import _get, Store, DataError
import concurrent.futures as cf
st = Store('data_cache'); D = 'research/v5/v6/b5_azioni/'
tick = [f[len('v6_b5_yahoo_1d_'):-len('.parquet')] for f in os.listdir('data_cache') if f.startswith('v6_b5_yahoo_1d_') and f.endswith('.parquet')]
def one(s):
    k = f'v6_b5_splits_{s}'
    if st.has(k): return s, 'cache'
    try:
        raw = json.loads(_get(f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}?period1=0&period2=4102444800&interval=3mo&events=splits", tries=3))
        ev = (raw['chart']['result'][0].get('events') or {}).get('splits') or {}
        df = pd.DataFrame([(pd.Timestamp(v['date'], unit='s').normalize(), v['numerator'] / v['denominator']) for v in ev.values()], columns=['date', 'ratio'])
        if not len(df): df = pd.DataFrame({'date': [pd.Timestamp('1900-01-01')], 'ratio': [1.0]})
        st.put(k, df, 'yahoo'); time.sleep(0.3); return s, 'ok'
    except Exception as e:
        return s, 'fail ' + repr(e)[-80:]
n = {}
with cf.ThreadPoolExecutor(3) as ex:
    for s, r in ex.map(one, tick):
        n[r.split()[0]] = n.get(r.split()[0], 0) + 1
        if r.startswith('fail'): print(s, r, flush=True)
print(n)
