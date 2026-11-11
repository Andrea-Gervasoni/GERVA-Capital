"""Scarica i fill (userFillsByTime, 2000 per chiamata, al massimo i 10.000 piu' recenti per indirizzo) dei conti scelti a T=2026-05-21
con sole informazioni <= T: i 40 migliori e i 40 peggiori per Sharpe di formazione fra i conti PIT con turnover <= 1000x/anno e conto >= 50k."""
import json, sys, numpy as np, pandas as pd, os
from concurrent.futures import ThreadPoolExecutor
from hl import post
A=pd.read_parquet('data/panel_av.parquet'); P=pd.read_parquet('data/panel_pnl.parquet'); M=pd.read_parquet('data/panel_meta.parquet'); G=A.index
dp=P.diff(); flow=A.diff()-dp; base=np.maximum(A.shift()+0.5*flow,0.5*A.shift()); R=(dp/base).where(base>=5000).clip(lower=-1.0,upper=3.0)
t=G.get_loc(pd.Timestamp('2026-05-21 00:30')); T=G[t]; w=R.iloc[t-12:t+1]; s=(w.mean()/w.std()).where((w.notna().sum()>=10)&(A.iloc[t]>=5e4)&(w.std()>1e-6))
m=((M.vault)|(M.top_giorno_dal<=T)|M.pit2024q4)&(M.turnover_anno<=1000); s=s[m.reindex(s.index).fillna(False)].dropna().sort_values()
top=list(s.index[-40:]); bot=list(s.index[:40]); print('ammissibili',len(s),'| Sharpe formazione top min %.2f, bottom max %.2f'%(s[top].min(),s[bot].max()))
sel=pd.DataFrame({'gruppo':['top']*40+['bottom']*40,'sharpe_form':list(s[top])+list(s[bot]),'av_T':list(A.iloc[t][top])+list(A.iloc[t][bot]),'turnover':list(M.turnover_anno[top])+list(M.turnover_anno[bot]),'vault':list(M.vault[top])+list(M.vault[bot])},index=top+bot)
sel.to_parquet('data/fills_sel.parquet')
START=int(T.timestamp()*1000); END=int(pd.Timestamp('2026-11-11').timestamp()*1000)
def one(a):
    out=[]; st=START
    for _ in range(6):
        f=post({"type":"userFillsByTime","user":a,"startTime":st,"endTime":END})
        if not f: break
        out+=f
        if len(f)<2000: break
        st=max(x['time'] for x in f)+1
    return a,out
rows=[]
with ThreadPoolExecutor(4) as ex:
    for a,f in ex.map(one,top+bot):
        for x in f: rows.append((a,x['time'],x['coin'],x['side'],float(x['px']),float(x['sz']),float(x['startPosition']),float(x['closedPnl']),float(x['fee']),x['crossed'],x['dir']))
F=pd.DataFrame(rows,columns=['a','time','coin','side','px','sz','start','closedPnl','fee','crossed','dir']); F['time']=pd.to_datetime(F.time,unit='ms'); F.to_parquet('data/fills.parquet')
g=F.groupby('a'); print('fill scaricati',len(F),'| conti con fill',g.ngroups,'| primo fill mediano',g.time.min().median(),'| conti che toccano il tetto (>=9500 fill):',(g.size()>=9500).sum())
print('quota del volume su BTC/ETH/SOL: %.2f'%((F.px*F.sz)[F.coin.isin(['BTC','ETH','SOL'])].sum()/(F.px*F.sz).sum()))
