"""B7.1 - SCELTA dei parametri della rotazione sul funding di Binance (918 perps, 2020-2022: un italiano oggi NON puo' incassarlo;
serve solo a scegliere k, N, soglie senza toccare Hyperliquid). Poi le stesse regole su Binance 2023-2026 per confronto. SIMULATO."""
import pandas as pd, numpy as np, itertools, json, os
from lib import *
C='/home/user/GERVA-Capital/data_cache/'
F=pd.read_parquet(C+'v4_allperp_fund.parquet'); Q=pd.read_parquet(C+'v4_allperp_qvol.parquet')
spot={f[len('bn_spot_1d_'):-len('.parquet')] for f in os.listdir(C) if f.startswith('bn_spot_1d_') and f.endswith('.parquet')}
print('perps',F.shape,'con spot in cache',len(spot&set(F.columns)))
elig=(Q.rolling(30,min_periods=20).median().shift(1)>20e6)&F.notna()
elig=elig.loc[:,[c for c in F.columns if c in spot]]; F=F[elig.columns]
big=['BTCUSDT','ETHUSDT','SOLUSDT']
res=[]; n=0
for k,N,ent,ext in itertools.product([3,7,14,30],[3,5,10],[0.10,0.15,0.25],[0.0,0.05,0.10]):
    if ext>=ent: continue
    r,nh,L=rotate(F,elig,k,N,ent,ext); n+=1
    s=stats(r[:SEL_END]); s2=stats(r[:SEL_END]-0.0073/2*0)  # stessa cosa
    r2,_,_=rotate(F,elig,k,N,ent,ext,cost_rt=0.0146)
    res.append(dict(k=k,N=N,ent=ent,ext=ext,sel=s['cagr'],sel_x2=stats(r2[:SEL_END])['cagr'],ver=stats(r[VER0:])['cagr'],occ=nh[:SEL_END].mean()/N,hold=(L['out']-L['in']).dt.days.mean()))
R=pd.DataFrame(res); print('varianti',n)
print(R.sort_values('sel_x2',ascending=False).head(12).round(3).to_string())
print('medie per parametro (CAGR scelta a costi doppi):'); 
for p in ['k','N','ent','ext']: print(p,R.groupby(p).sel_x2.mean().round(4).to_dict())
b=R.sort_values('sel_x2',ascending=False).iloc[0]; P=dict(k=int(b.k),N=int(b.N),ent=float(b.ent),ext=float(b.ext)); json.dump(P,open('congelato.json','w')); print('CONGELATO (scelto su costi doppi, <=2022):',P)
print('\n--- per unita\' di nozionale, Binance')
r,nh,L=rotate(F,elig,**P); [pr(x) for x in fss(r,'rotazione tutte le monete')]
r2,_,_=rotate(F,elig,**P,cost_rt=0.0146); [pr(x) for x in fss(r2,'  costi x2')]
r3,_,_=rotate(F,elig,**P,delay=2); [pr(x) for x in fss(r3,'  un giorno di ritardo in piu\'')]
rb,_,_=rotate(F[big],elig[big],**P,N=3) if False else rotate(F[big],elig[big],k=P['k'],N=3,ent=P['ent'],ext=P['ext']); [pr(x) for x in fss(rb,'rotazione solo BTC/ETH/SOL')]
bh=F[big].mean(axis=1); [pr(x) for x in fss(bh,'BTC/ETH/SOL sempre dentro (lordo costi)')]
print('per anno (rendimento sul nozionale, %): rotazione | solo big3 | big3 sempre dentro')
print(pd.DataFrame({'rot':r.groupby(r.index.year).sum()*100,'big3_rot':rb.groupby(rb.index.year).sum()*100,'big3_hold':bh.groupby(bh.index.year).sum()*100,'occup':nh.groupby(nh.index.year).mean()/P['N']}).round(2).to_string())
print('durata media posizione (giorni):',(L['out']-L['in']).dt.days.mean().round(1),'rotazioni/anno',round(len(L)/((F.index[-1]-F.index[0]).days/365),1))
