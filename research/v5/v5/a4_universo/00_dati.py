"""A4 - universo point-in-time dei perpetual USDT-M Binance (anche tolti dal listino) e scarico delle candele orarie.
Regola dell'universo (nota al giorno t, senza guardare avanti): al primo di ogni mese, tra i perpetual con almeno 200 giorni
di storia, i TOPN per volume mediano in dollari degli ultimi 90 giorni (fino a ieri). Esclusi azioni/metalli tokenizzati e indici.
Uso: /tmp/gv/bin/python research/v5/v5/a4_universo/00_dati.py [N]"""
import sys, warnings, concurrent.futures as cf
sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from gerva.data.sources import Store, binance_klines
st = Store('/home/user/GERVA-Capital/data_cache')
HERE = '/home/user/GERVA-Capital/research/v5/v5/a4_universo/'
TOPN = 30
NONCRYPTO = {'XAUUSDT', 'XAGUSDT', 'PAXGUSDT', 'TSLAUSDT', 'MSTRUSDT', 'INTCUSDT', 'CRCLUSDT', 'BTCDOMUSDT', 'DEFIUSDT', 'USDCUSDT',
             'CLUSDT', 'BZUSDT', 'QQQUSDT', 'AAPLUSDT', 'SOXLUSDT', 'SOXSUSDT', 'MUUSDT', 'EWYUSDT', 'MRVLUSDT', 'SPXUSDT'}

def universe(topn=TOPN):
    q = st.get('v4_allperp_qvol'); c = st.get('v4_allperp_close')
    q = q[[s for s in q.columns if s not in NONCRYPTO]]; c = c[q.columns]
    age = c.notna().cumsum()
    med = q.rolling(90, min_periods=60).median().shift(1).where(age.shift(1) >= 200)
    alive = q.rolling(5).sum().shift(1) > 0                       # scambiato negli ultimi 5 giorni
    med = med.where(alive)
    rank = med.rank(axis=1, ascending=False)
    ms = rank[rank.index.day == 1]
    member = (ms <= topn).reindex(rank.index).ffill().fillna(False).astype(bool)   # appartenenza fissata il 1° del mese
    top10 = (ms <= 10).reindex(rank.index).ffill().fillna(False).astype(bool)
    return member, top10, med

if __name__ == '__main__':
    member, top10, med = universe()
    syms = [s for s in member.columns if member[s].any()]
    print('simboli mai entrati nel top', TOPN, ':', len(syms))
    print('membri per anno (media):'); print(member[syms].sum(axis=1).resample('YE').mean().round(1).to_string())
    def one(s):
        key = f'v5_um_1h_{s}'
        if st.has(key): return s, 'cache'
        old = f'v4_um_1h_{s}'
        try:
            d = st.get(old) if st.has(old) else binance_klines(s, '1h', 'um', '2020-01', workers=6)
            st.put(key, d, 'binance.vision'); return s, len(d)
        except Exception as e:
            return s, 'FAIL ' + str(e)[:100]
    with cf.ThreadPoolExecutor(4) as ex:
        for s, r in ex.map(one, syms): print(s, r, flush=True)
    member[syms].to_parquet(HERE + 'universo_membri.parquet'); top10[syms].to_parquet(HERE + 'universo_top10.parquet')
    med[syms].to_parquet(HERE + 'universo_volmed90.parquet')
    print('fatto')
