import sys, warnings; sys.path.insert(0,'/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from gerva.validation import montecarlo as MC
from gerva.data import Store
exec(open('research/v5/v2/_cache/c1.py').read().split("# Monte Carlo")[0].split("T=pd.DataFrame(rows)")[0])   # riusa port, tier, schemi
X=np.column_stack([r0.values,t0.values,rf0.values]); idx=MC._block_index(len(X),3*365,30,np.random.default_rng(7),4000)
def mc(sch,scen):
    r=X[idx,0].copy(); t=X[idx,1].astype(int); rfx=X[idx,2]
    if scen=='pessimista': r=r-0.5*(r0.mean()-rf0.mean())
    if scen=='stress': r=r-(np.random.default_rng(8).random(r.shape)<0.001)*0.15
    L=np.array(sch)[t]; x=np.maximum(lev_ret(r,L,rfx),-1)
    eq=np.cumprod(1+x,axis=1); mdd=(eq/np.maximum.accumulate(eq,axis=1)-1).min(axis=1); fin=eq[:,-1]
    cagr=np.where(fin>0,fin**(1/3)-1,-1); m=np.prod(1+x[:,:36*30].reshape(len(x),36,30),axis=2)-1
    return dict(cagr_p50=np.median(cagr),cagr_p05=np.quantile(cagr,.05),maxdd_p50=np.median(mdd),p_rovina=(eq.min(axis=1)<=0.5).mean(),p_azzerato=(eq.min(axis=1)<=0.05).mean(),mese_medio=m.mean(),p_mese_ge20=(m>=0.2).mean(),p_mese_le20=(m<=-0.2).mean())
sch2=dict(schemes); sch2.update({'fissa 3x':(3,3,3,3),'fissa 5x':(5,5,5,5),'fissa 10x':(10,)*4,'fissa 15x':(15,)*4,'fissa 20x':(20,)*4,'fissa 30x':(30,)*4})
out=[]
for name,sch in sch2.items():
    for scen in ('base','pessimista','stress'):
        o=mc(sch,scen); o.update(schema=name,scenario=scen,dist_liq=1/max(sch)); out.append(o)
R=pd.DataFrame(out).set_index(['schema','scenario']); pd.set_option('display.width',250); print(R.round(3).to_string()); R.to_pickle('research/v5/v2/_cache/mc_nobreaker.pkl')
print('giorni in cui il portafoglio senza leva ha perso piu di 1/L: ',{L:int((r0<=-1/L).sum()) for L in (10,15,20,30)}, 'su', len(r0))
# ---- stop veri sul percorso a 5 minuti: BTC ed ETH nei giorni ad alta conviction
st=Store('/home/user/GERVA-Capital/data_cache'); conv=pd.read_pickle('research/v5/v2/_cache/conv.pkl')
for c in ('BTC','ETH'):
    b=st.get(f'bn_spot_5m_{c}USDT'); day=b.index.normalize()
    hi=(conv[c]['tier'].shift(1)=='alta')
    g=b.groupby(day); o=g['open'].first(); cl=g['close'].last(); lo=b['low'].values; dn=day.values
    days=[d for d in o.index if hi.get(d,False)]
    pos={d:i for i,d in enumerate(o.index)}
    start=np.searchsorted(dn,o.index.values); end=np.append(start[1:],len(dn))
    rows=[]
    for L in (1,2,3,5,10,15,20,30):
        for stop_eq in (None,0.03,0.06):
            rr=[]; nstop=0; nliq=0
            for d in days:
                i=pos[d]; p0=o.iloc[i]; seg=lo[start[i]:end[i]]/p0-1; c_ret=cl.iloc[i]/p0-1
                liq=-(1/L-0.005); s=-stop_eq/L if stop_eq else None
                lvl=max(liq,s) if s is not None else liq
                if seg.min()<=lvl:
                    if s is not None and s>liq: rr.append(-stop_eq-0.001*L-0.0007*L); nstop+=1
                    else: rr.append(-1.0); nliq+=1
                else: rr.append(L*c_ret-0.0007*L*0.3)
            rr=np.array(rr); alive=(rr>-1).all()
            eq=np.cumprod(1+rr); yrs=len(o)/365
            rows.append(dict(L=L,stop=stop_eq,giorni=len(rr),media_pb=rr.mean()*1e4,cagr=(eq[-1]**(1/yrs)-1) if alive else -1,maxdd=float((eq/np.maximum.accumulate(eq)-1).min()) if alive else -1,stop_pct=nstop/len(rr),liquidazioni=nliq,hit=(rr>0).mean()))
    print(c); print(pd.DataFrame(rows).round(3).to_string(index=False))
