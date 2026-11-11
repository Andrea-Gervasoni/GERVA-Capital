"""B5 - scarica OHLCV giornaliero Yahoo per tutti i ticker (membri attuali + rimossi). Cache v6_b5_yahoo_1d_*."""
import sys, time, json, os
sys.path.insert(0, '/home/user/GERVA-Capital')
os.chdir('/home/user/GERVA-Capital')
from gerva.data.sources import yahoo, Store, DataError
import concurrent.futures as cf
st = Store('data_cache')
D = 'research/v5/v6/b5_azioni/'
tick = open(D + 'tickers_all.txt').read().split() + ['SPY', 'QQQ', 'XLK', 'XLF', 'XLV', 'XLY', 'XLP', 'XLE', 'XLI', 'XLB', 'XLU', 'XLRE', 'XLC', '^IRX']
fail = json.load(open(D + 'download_fail.json')) if os.path.exists(D + 'download_fail.json') else {}
def one(s):
    k = f'v6_b5_yahoo_1d_{s}'
    if st.has(k): return s, 'cache'
    if s in fail and 'retry' not in sys.argv: return s, 'fail:' + fail[s]
    for a in range(3):
        try:
            df = yahoo(s); st.put(k, df, 'yahoo'); time.sleep(0.35); return s, 'ok'
        except DataError as e:
            msg = str(e)[:120]
            if 'Not Found' in msg or 'delisted' in msg or 'nessuna barra' in msg or '404' in msg: return s, 'fail:' + msg
            time.sleep(3 + 5 * a)
        except Exception as e:
            msg = repr(e)[:120]; time.sleep(3 + 5 * a)
    return s, 'fail:' + msg
n = {'ok': 0, 'cache': 0, 'fail': 0}
with cf.ThreadPoolExecutor(3) as ex:
    for i, (s, r) in enumerate(ex.map(one, tick)):
        n[r.split(':')[0]] += 1
        if r.startswith('fail'): fail[s] = r[5:]
        if i % 100 == 0: print(i, s, r, n, flush=True)
json.dump(fail, open(D + 'download_fail.json', 'w'), indent=0)
print('FINE', n); print('falliti', len(fail))
