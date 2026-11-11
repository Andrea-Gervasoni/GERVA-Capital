"""Validazione claim 1 (A5 MR): ri-derivazione indipendente dai parquet grezzi. SIMULATO."""
import numpy as np, pandas as pd, sys
ROOT='/home/user/GERVA-Capital'
def ld(s):
    d=pd.read_parquet(f'{ROOT}/data_cache/yahoo_1d_{s}.parquet'); return d[d.index<='2026-11-09']
vix=ld('^VIX').close; rf=(ld('^IRX').close/100)
COST={'SPY':2e-4,'QQQ':2e-4,'IWM':3e-4}
def feats(d):
    pc=d.close.shift(1)
    tr=np.maximum(d.high-d.low,np.maximum((d.high-pc).abs(),(d.low-pc).abs()))
    a=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()/d.close
    rng=(d.high-d.low); ib=((d.close-d.low)/rng.where(rng>0)).fillna(0.5)
    return ib,a
def trades(sym, vthr=20, vlag=0, lag=1, cm=1.0, ibs_in=0.2, stopmode='stop', vmax=None, nostop=False):
    d=ld(sym); ib,a=feats(d); v=vix.reindex(d.index).shift(vlag); r=rf.reindex(d.index,method='ffill').fillna(0.02).values
    div=((d.adj/d.adj.shift(1))-(d.close/d.close.shift(1))).fillna(0).clip(0,0.05); div[div<5e-4]=0; div=div.values
    sig=(ib<ibs_in)
    if vthr is not None: sig&=(v>=vthr)
    if vmax is not None: sig&=(v<vmax)
    sig=sig.values; o,h,l,c=d.open.values,d.high.values,d.low.values,d.close.values; ibv=ib.values; av=a.values; ix=d.index; n=len(d)
    out=[]; t=0
    while t<n-1-lag:
        if not sig[t] or not np.isfinite(av[t]): t+=1; continue
        e=t+lag; pe=o[e]; s=max(av[t],0.002); L=min(20,1/(s/0.6+0.005)); stop=pe*(1-s); fin=0; dv=0; j=e; hold=0; px=None
        while j<n:
            if j>e:
                fin+=(r[j-1]+0.015)/360*max((ix[j]-ix[j-1]).days,1); dv+=div[j]
            hold+=1
            if j>e and o[j]<=stop and not nostop: px=o[j]; why='gap'; xb=j; break
            if l[j]<=stop and not nostop:
                px=stop*(1-2e-4) if stopmode=='stop' else c[j]; why='stop'; xb=j; break
            if ibv[j]>0.7 or hold>=5:
                if j+1>=n: break
                fin+=(r[j]+0.015)/360*max((ix[j+1]-ix[j]).days,1); dv+=div[j+1]; px=o[j+1]; why='sig'; xb=j+1; break
            j+=1
        if px is None: break
        ret=max(px/pe-1-2*COST[sym]*cm-fin+dv,-1/L)
        out.append((sym,ix[t],ix[e],ix[xb],s,ret/s,why,v.iloc[t]))
        t=max(xb-1 if why=='sig' else xb,t+1)
    return pd.DataFrame(out,columns=['sym','sigday','entry','exit','s','R','why','vix'])
def book(**k):
    T=pd.concat([trades(s,**k) for s in COST]); T=T[T.entry>='1994-01-01']
    g=T.groupby('entry'); C=pd.DataFrame({'R':g.R.mean(),'k':g.size(),'exit':g.exit.max()}).reset_index(); return T,C
def st(x,lab):
    def o(y):
        if len(y)<3: return 'n %d'%len(y)
        m=y.R.mean(); sd=y.R.std(); w=y.set_index('entry').R.resample('W').sum(); w=w[w!=0]
        mo=y.set_index('entry').R.resample('ME').sum()
        return 'n %4d R %+.3f t %+.2f t_mese %+.2f'%(len(y),m,m/sd*np.sqrt(len(y)),mo.mean()/mo.std()*np.sqrt(len(mo)))
    print(f'{lab:44s} | tutto {o(x)} | scelta {o(x[x.entry<="2022-12-31"])} | verifica {o(x[x.entry>="2023-01-01"])}')
T,C=book(); st(C,'BASE raggruppato (IBS<.2,VIX>=20)'); st(T,'BASE non raggruppato (per indice)')
yrs=(C.exit.max()-C.entry.min()).days/365.25; print('trade/anno %.1f  stop %% %.2f'%(len(C)/yrs,(T.why!='sig').mean()))
print('entrata = barra dopo il segnale per tutti:', bool((T.entry>T.sigday).all()), ' VIX min ai segnali %.2f'%T.vix.min())
for lab,k in [('costi x2',dict(cm=2)),('ritardo 1 giorno (lag=2)',dict(lag=2)),('VIX del giorno prima (t-1)',dict(vlag=1)),
  ('SENZA filtro VIX',dict(vthr=None)),('VIX<20',dict(vthr=None,vmax=20)),('VIX>=18',dict(vthr=18)),('VIX>=22',dict(vthr=22)),('VIX>=25',dict(vthr=25)),('VIX>=15',dict(vthr=15)),('VIX>=30',dict(vthr=30)),
  ('stop toccato -> esce in chiusura (diagn.)',dict(stopmode='close')),('senza stop (diagn.)',dict(nostop=True))]:
    st(book(**k)[1],lab)
print('\nper indice:'); [st(trades(s).query("entry>='1994'"),s) for s in COST]
V=C[C.entry>='2023']; print('\nverifica per anno:\n',V.groupby(V.entry.dt.year).R.agg(['size','mean','sum']).round(2))
print('verifica senza i 5 trade migliori: %.3f ; senza 2025: %.3f (n %d)'%(V.R.sort_values()[:-5].mean(),V[V.entry.dt.year!=2025].R.mean(),(V.entry.dt.year!=2025).sum()))
# bootstrap verifica: VIX>=20 vs senza filtro (per mese)
rng=np.random.default_rng(0); m=V.set_index('entry').R.resample('ME').agg(['sum','size']); b=[]
for _ in range(5000):
    i=rng.integers(0,len(m),len(m)); b.append(m['sum'].values[i].sum()/max(m['size'].values[i].sum(),1))
print('verifica R medio, bootstrap a blocchi mensili: IC90 [%.3f, %.3f]  P(<=0) %.3f'%(*np.percentile(b,[5,95]),np.mean(np.array(b)<=0)))
# confronto con analista
A=pd.read_parquet(ROOT+'/research/v5/v5/a5_indici/trades.parquet'); A=A[A.setup=='MR']
mm=C.merge(A,on='entry',how='outer',suffixes=('','_a'),indicator=True); print('\nconfronto con analista:',mm._merge.value_counts().to_dict(),' corr R %.4f  max|diff| %.4f'%(mm.R.corr(mm.R_a),(mm.R-mm.R_a).abs().max()))
# troncamento: segnale ricalcolato su dati tagliati a t
bad=0; nchk=0
for s in COST:
    d=ld(s); ib,a=feats(d)
    for t in rng.integers(300,len(d),300):
        ib2,a2=feats(d.iloc[:t+1]); nchk+=1
        if abs(ib2.iloc[-1]-ib.iloc[t])>1e-12 or abs(a2.iloc[-1]-a.iloc[t])>1e-12: bad+=1
print('troncamento IBS/ATR: %d confronti, %d differenze'%(nchk,bad))
# sovrapposizione con sleeve EQ-MR (IBS<0.2 -> long alla chiusura, fuori a IBS>0.7, SPY e QQQ, senza filtro)
print('\nsovrapposizione con EQ-MR (gerva/strategies/book.py:65):')
for s in ['SPY','QQQ']:
    d=ld(s); ib,_=feats(d); pos=np.zeros(len(d)); cur=0
    for i,x in enumerate(ib.values):
        if cur==0 and x<0.2: cur=1
        elif cur==1 and x>0.7: cur=0
        pos[i]=cur
    pos=pd.Series(pos,index=d.index); Ts=trades(s); Ts=Ts[Ts.entry>='2003']
    inpos=pos.reindex(Ts.sigday).values
    # giorni detenuti da A5 MR che sono anche giorni EQ-MR long
    held=pd.Series(0,index=d.index)
    for _,r in Ts.iterrows(): held[(d.index>=r.sigday)&(d.index<r.exit)]=1
    p2=pos.loc['2003':]; h2=held.loc['2003':]
    print(f'{s}: segnali A5 con EQ-MR gia\' long alla chiusura del segnale: {inpos.mean():.1%} ; notti A5 coperte da EQ-MR: {(h2*p2).sum()/h2.sum():.1%} ; notti EQ-MR coperte da A5: {(h2*p2).sum()/p2.sum():.1%}')
    for nm,sl in (('scelta',slice('2003','2022')),('verifica',slice('2023',None))):
        cc=d.close.pct_change(); e=(pos.shift(1)*cc).loc[sl]; e_hi=(pos.shift(1)*cc*(vix.reindex(d.index).shift(1)>=20)).loc[sl]
        print(f'   {nm}: EQ-MR lordo annuo {e.sum()/len(e)*252:+.3f}, di cui in giorni con VIX(t-1)>=20 {e_hi.sum()/len(e)*252:+.3f}')
