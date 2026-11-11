"""Stress della leva per trade sui dati reali a 5 minuti (BTC, ETH, SOL spot Binance): quanto spesso il prezzo ha percorso
la distanza che separa lo stop dalla liquidazione in una sola barra, e la distanza intera di liquidazione in 1 ora, 4 ore, 24 ore
(= che cosa succede se l'exchange non risponde per quel tempo e lo stop non viene eseguito). FATTO sui dati; l'uso come stima e' un'IPOTESI."""
import sys; sys.path.insert(0,'/home/user/GERVA-Capital')
import numpy as np, pandas as pd
from gerva.data import Store
st=Store('/home/user/GERVA-Capital/data_cache'); MM=0.005; pd.set_option('display.width',250)
rows=[]
for c in ('BTC','ETH','SOL'):
    b=st.get(f'bn_spot_5m_{c}USDT'); yrs=len(b)/(288*365.25)
    bar=b['low']/b['open']-1                                   # caduta massima dentro una barra da 5 minuti
    lo={h:(b['low'][::-1].rolling(n).min()[::-1]/b['open']-1) for h,n in (('1h',12),('4h',48),('24h',288))}
    print(f"{c}: {yrs:.1f} anni. Peggiori barre da 5 minuti:"); print((bar.nsmallest(5)*100).round(1).to_string())
    for L in (5,10,15,20,30,50):
        liq=1/L-MM; stop=0.6*liq
        rows.append(dict(moneta=c,leva=L,dist_stop=stop,dist_liq=liq,
            barre5m_oltre_stop_liq_anno=(bar<=-(liq-stop)).sum()/yrs,       # una barra copre da sola la distanza stop -> liquidazione
            barre5m_oltre_liq_anno=(bar<=-liq).sum()/yrs,
            p_liq_1h=(lo['1h']<=-liq).mean(),p_liq_4h=(lo['4h']<=-liq).mean(),p_liq_24h=(lo['24h']<=-liq).mean()))
R=pd.DataFrame(rows); print(R.round(4).to_string(index=False))
print("\nGiornate storiche (minimo intraday rispetto all'apertura del giorno):")
for d in ('2020-03-12','2021-05-19','2022-06-13','2022-11-08','2024-08-05','2025-10-10'):
    o=[]
    for c in ('BTC','ETH','SOL'):
        b=st.get(f'bn_spot_5m_{c}USDT'); x=b.loc[d] if d in b.index.normalize().strftime('%Y-%m-%d') else None
        if x is not None and len(x): o.append(f"{c} {x['low'].min()/x['open'].iloc[0]-1:+.1%} (barra peggiore {(x['low']/x['open']-1).min():+.1%})")
    print(d,' | '.join(o))
