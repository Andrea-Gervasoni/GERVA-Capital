import sys, warnings; sys.path.insert(0,'/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from gerva.validation import metrics as M, montecarlo as MC
D=pd.read_parquet('/home/user/GERVA-Capital/research/v5/series.parquet')
port=D['PORT'].dropna(); rf=D['RF'].reindex(port.index).fillna(0)
conv=pd.read_pickle('research/v5/v2/_cache/conv.pkl')
n={'BTC':12,'ETH':12,'SPY':11,'QQQ':11}
Z=pd.DataFrame({k:(v['score']/n[k]) for k,v in conv.items()}).reindex(port.index).ffill()
comp=Z.mean(axis=1).shift(1)                # nota la sera prima
SPL='2023-01-01'
q=comp.loc[:SPL].quantile([1/3,2/3,0.9]).values
tier=pd.Series(np.where(comp<=q[0],0,np.where(comp<=q[1],1,np.where(comp<=q[2],2,3))),index=port.index).where(comp.notna())
print('soglie',q.round(3))
for lab,sl in (('scelta',slice(None,SPL)),('verifica',slice(SPL,None))):
    x=pd.DataFrame(dict(r=(port-rf)[sl],t=tier[sl])).dropna()
    t=x.groupby('t').r.agg(n='size',media_pb=lambda s:s.mean()*1e4,vol=lambda s:s.std()*np.sqrt(365),sharpe=lambda s:s.mean()/s.std()*np.sqrt(365),hit=lambda s:(s>0).mean(),peggiore='min')
    t['kelly']=x.groupby('t').r.apply(lambda s:s.mean()/s.var())
    print(lab); print(t.round(3).to_string())
print('peggior giorno del portafoglio senza leva', round(port.min(),4), '| 1° percentile', round(port.quantile(0.01),4))
# schemi di leva per livello (bassa, media, alta, eccezionale)
schemes={'fissa 1x':(1,1,1,1),'fissa 2x':(2,2,2,2),'A 0.5/1/2/3':(0.5,1,2,3),'B 0.5/1.5/3/5':(0.5,1.5,3,5),'C 1/2/5/10':(1,2,5,10),'D 1/3/10/15':(1,3,10,15),'E 2/5/15/20':(2,5,15,20),'F 2/5/15/30':(2,5,15,30)}
def lev_ret(r,L,rfx,spread=0.015):
    return L*r-np.maximum(L-1,0)*(rfx+spread/365)+np.maximum(1-L,0)*rfx
def run(r,t,rfx,sch,breaker=None):
    L=np.array(sch)[t.astype(int).values]
    x=lev_ret(r.values,L,rfx.values)
    if breaker: x=np.maximum(x,-breaker-0.002*L)      # interruttore giornaliero: la perdita del giorno si ferma li' (piu' slittamento)
    return pd.Series(x,index=r.index),L
ok=tier.notna(); r0,t0,rf0=port[ok],tier[ok],rf[ok]
rows=[]
for name,sch in schemes.items():
    for br in (None,0.06):
        x,L=run(r0,t0,rf0,sch,br)
        s=M.summary(x,rf0,365) if (x>-1).all() else dict(cagr=-1,vol=np.nan,sharpe=np.nan,max_dd=-1,mese_medio=np.nan,mese_peggiore=-1,giorno_peggiore=x.min())
        sv=M.summary(x.loc[SPL:],rf0,365) if (x>-1).all() else {}
        rows.append(dict(schema=name,interruttore=br,leva_media=L.mean(),cagr=s['cagr'],vol=s['vol'],sharpe=s['sharpe'],maxdd=s['max_dd'],mese_medio=s['mese_medio'],mese_peggiore=s['mese_peggiore'],giorno_peggiore=s['giorno_peggiore'],cagr_ver=sv.get('cagr'),sharpe_ver=sv.get('sharpe'),dist_liq=1/max(sch)))
T=pd.DataFrame(rows); pd.set_option('display.width',250); print(T.round(3).to_string(index=False))
# Monte Carlo: ricampiono coppie (rendimento, livello) a blocchi di 30 giorni
X=np.column_stack([r0.values,t0.values,rf0.values]); rng=np.random.default_rng(7)
idx=MC._block_index(len(X),3*365,30,rng,4000)
def mc(sch,scen,br=0.06):
    r=X[idx,0].copy(); t=X[idx,1].astype(int); rfx=X[idx,2]
    if scen=='pessimista': r=r-0.5*(r0.mean()-rf0.mean())
    if scen=='stress': r=r-(np.random.default_rng(8).random(r.shape)<0.001)*0.15
    if scen=='ottimista': pass
    L=np.array(sch)[t]; x=lev_ret(r,L,rfx)
    if br: 
        capped=np.maximum(x,-br-0.002*L)
        if scen=='stress': capped=np.where(r<-0.10, x, capped)   # un gap non si ferma all'interruttore
        x=capped
    x=np.maximum(x,-1)
    eq=np.cumprod(1+x,axis=1); mdd=(eq/np.maximum.accumulate(eq,axis=1)-1).min(axis=1); fin=eq[:,-1]
    cagr=np.where(fin>0,fin**(1/3)-1,-1)
    m=np.prod(1+x[:,:36*30].reshape(len(x),36,30),axis=2)-1
    return dict(cagr_p50=np.median(cagr),cagr_p05=np.quantile(cagr,.05),cagr_p95=np.quantile(cagr,.95),maxdd_p50=np.median(mdd),maxdd_p05=np.quantile(mdd,.05),p_rovina=(eq.min(axis=1)<=0.5).mean(),p_azzerato=(eq.min(axis=1)<=0.05).mean(),mese_medio=m.mean(),p_mese_ge20=(m>=0.2).mean())
out=[]
for name,sch in schemes.items():
    for scen in ('base','pessimista','stress'):
        o=mc(sch,scen); o.update(schema=name,scenario=scen); out.append(o)
R=pd.DataFrame(out).set_index(['schema','scenario']); print(R.round(3).to_string())
R.to_pickle('research/v5/v2/_cache/mc_tiers.pkl'); T.to_pickle('research/v5/v2/_cache/hist_tiers.pkl')
