"""Leva per singolo trade a margine isolato: simulazione sul percorso a 5 minuti (BTC, ETH, SOL spot Binance come proxy dei perpetual).
SIMULATO. Ingresso all'apertura del giorno dopo il segnale (conviction nota la sera prima). Uscita: stop sul percorso a 5m,
oppure conviction scesa a 'bassa', oppure durata massima. Costi: 4,5 pb taker per lato + 2 pb slippage per lato + 5 pb in piu' sullo stop
+ funding reale Binance. La leva e' la massima che tiene lo stop a non piu' del 60% della strada verso la liquidazione."""
import sys, warnings, pickle; sys.path.insert(0,'/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from gerva.data import Store
from gerva import ensemble as E
st=Store('/home/user/GERVA-Capital/data_cache')
FEE=0.00045+0.0002; STOPSLIP=0.0005; MM=0.005; RATIO=0.6
def load(c):
    b=st.get(f'bn_spot_5m_{c}USDT'); day=b.index.normalize(); g=b.groupby(day)
    d=pd.DataFrame(dict(open=g['open'].first(),high=g['high'].max(),low=g['low'].min(),close=g['close'].last()))
    return b,d
B={};D={}
for c in ('BTC','ETH','SOL'): B[c],D[c]=load(c)
def fund(c):
    try:
        f=st.get(f'bn_fund_{c}USDT'); s=f.iloc[:,0] if f.shape[1]==1 else f[[k for k in f.columns if 'rate' in k.lower()][0]]
        return s.groupby(s.index.normalize()).sum()
    except Exception as e: return None
CONV={}
for c in D:
    F=E.crypto_signals(D[c],D['BTC']['close'],fund(c)); cv=E.conviction(F,'crypto'); CONV[c]=cv.shift(1)   # nota la sera prima
def levmax(s,cap=50): return min(cap,1/(s/RATIO+MM))
def trades(c,s,tiers=('alta',),maxhold=7,trail=None,side=1,short_thr=0.2,atr_k=None,tp=None):
    b=B[c]; d=D[c]; cv=CONV[c]; f=fund(c)
    op=b['open'].values; hi=b['high'].values; lo=b['low'].values; cl=b['close'].values
    dn=b.index.normalize().values; days=d.index.values; start=np.searchsorted(dn,days); end=np.append(start[1:],len(dn))
    atr=((d['high']-d['low'])/d['close']).rolling(14).mean().shift(1).values
    tier=cv['tier'].values; score=cv['score'].values
    out=[]; i=250
    while i<len(days)-1:
        ok=(tier[i] in tiers) if side==1 else (score[i]<=short_thr)
        if not ok or np.isnan(score[i]): i+=1; continue
        sd=s if atr_k is None else float(np.clip(atr_k*atr[i],0.003,0.15))
        L=levmax(sd); p0=op[start[i]]; stop=p0*(1-side*sd); best=p0; j=i; exitp=None; why='tempo'
        liq=p0*(1-side*(1/L-MM))
        while True:
            a,z=start[j],end[j]
            for k in range(a,z):
                o,h,l=op[k],hi[k],lo[k]
                adv=l if side==1 else h
                if side*(adv-stop)<=0:
                    px=min(stop,o) if side==1 else max(stop,o)                       # gap: si esce all'apertura della barra
                    px=px*(1-side*STOPSLIP)
                    if side*(px-liq)<=0: px=liq; why='liquidazione'
                    else: why='stop'
                    exitp=px; break
                if tp is not None and side*((h if side==1 else l)-p0)/p0>=tp*sd:
                    exitp=p0*(1+side*tp*sd); why='obiettivo'; break
                fav=h if side==1 else l
                if trail is not None and side*(fav-best)>0:
                    best=fav; ns=best*(1-side*trail*sd)
                    if side*(ns-stop)>0: stop=ns
            if exitp is not None: break
            j+=1
            if j>=len(days)-1 or j-i>=maxhold or ((tier[j]=='bassa') if side==1 else (score[j]>0.45)):
                exitp=op[start[min(j,len(days)-1)]]; break
        nd=max(j-i,1); fu=0.0
        if f is not None:
            fu=float(f.reindex(pd.DatetimeIndex(days[i:i+nd])).fillna(0.0001*3).sum())*side
        gross=side*(exitp/p0-1); net=gross-2*FEE-fu
        lossmax=1/L                                                                   # margine isolato: oltre non si perde
        net=max(net,-lossmax)
        out.append(dict(coin=c,entry=days[i],exit=days[min(j,len(days)-1)],s=sd,L=L,R=net/sd,ret=net,why=why,days=nd,tier=tier[i],side=side))
        i=j+1
    return pd.DataFrame(out)
def stats(T,label):
    if len(T)==0: return dict(cfg=label,n=0)
    y=(T.entry.max()-T.entry.min()).days/365.25
    def blk(x): 
        return dict(n=len(x),meanR=x.R.mean(),hit=(x.R>0).mean(),t=x.R.mean()/x.R.std()*np.sqrt(len(x)) if len(x)>2 else np.nan)
    a=blk(T); i=blk(T[T.entry<'2023-01-01']) if (T.entry<'2023-01-01').any() else dict(meanR=np.nan,n=0); o=blk(T[T.entry>='2023-01-01']) if (T.entry>='2023-01-01').any() else dict(meanR=np.nan,n=0)
    return dict(cfg=label,n=a['n'],per_anno=a['n']/y,L=T.L.median(),meanR=a['meanR'],t=a['t'],hit=a['hit'],R_scelta=i['meanR'],R_verifica=o['meanR'],n_ver=o['n'],
                stop_pct=(T.why=='stop').mean(),liq=(T.why=='liquidazione').sum(),costo_R=(2*FEE/T.s).mean(),R_anno=a['meanR']*a['n']/y)
if __name__=='__main__':
    pd.set_option('display.width',250); rows=[]; ALL={}
    for s in (0.004,0.006,0.009,0.012,0.017,0.027,0.04,0.06,0.10):
        for tiers in (('alta',),('media','alta')):
            for trail in (None,2.0):
                T=pd.concat([trades(c,s,tiers,trail=trail) for c in B]); k=(s,tiers,trail,'long'); ALL[k]=T
                rows.append(stats(T,f"stop {s:.1%} {'+'.join(tiers)} trail={trail}"))
    for k_ in (0.5,1.0,2.0):
        T=pd.concat([trades(c,0,('alta',),atr_k=k_,trail=2.0) for c in B]); ALL[(f'atr{k_}',('alta',),2.0,'long')]=T; rows.append(stats(T,f"stop {k_}xATR alta trail=2"))
    for s in (0.012,0.027,0.06):
        T=pd.concat([trades(c,s,side=-1,trail=2.0) for c in B]); ALL[(s,'short',2.0,'short')]=T; rows.append(stats(T,f"SHORT stop {s:.1%} score<=0,2 trail=2"))
    R=pd.DataFrame(rows); print(R.round(3).to_string(index=False)); print('varianti provate:',len(rows))
    pickle.dump(ALL,open('research/v5/v4/_cache/trades.pkl','wb'))
