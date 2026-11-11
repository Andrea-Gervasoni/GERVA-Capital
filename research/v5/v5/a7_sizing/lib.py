"""A7 - motore comune: Kelly empirico (numerico, perdita limitata dal margine isolato) e bootstrap a blocchi di mesi. SIMULATO.
Unita' di tempo = 'coorte' (trade aperti lo stesso giorno, fino a 3 monete): i trade della stessa coorte sono SIMULTANEI
(il rendimento della coorte e' la somma r_i*R_i; la somma dei margini non puo' superare il capitale).
I mesi senza trade sono inclusi nel ricampionamento (la v4 li escludeva, gonfiando la frequenza)."""
import pickle,numpy as np,pandas as pd
from scipy.optimize import minimize_scalar,minimize
HERE='/home/user/GERVA-Capital/research/v5/v5/a7_sizing/'
SPLIT=pd.Timestamp('2023-01-01')
def load(): return pickle.load(open(HERE+'trades_enriched.pkl','rb'))
def years_of(X): return (X.entry.max()-X.entry.min()).days/365.25
def scen(X,name):
    """base / mezzo (meta' del vantaggio: R - 0,5*media, limitato al margine) / verifica (ingressi >= 2023) / scelta (< 2023)."""
    X=X.copy()
    if name=='mezzo': X['R']=np.maximum(X.R-0.5*X.R.mean(),-X.cap)
    elif name=='zero': X['R']=np.maximum(X.R-X.R.mean(),-X.cap)
    elif name=='verifica': X=X[X.entry>=SPLIT]
    elif name=='scelta': X=X[X.entry<SPLIT]
    return X.reset_index(drop=True)
# ---------- Kelly ----------
def kelly_seq(R,cap=None):
    """max E[log(1+r R)] trade per trade (sequenziale). Ritorna r*, crescita log per trade."""
    R=np.asarray(R,float); hi=0.999/max(-R.min(),1e-9) if R.min()<0 else 50.
    if cap is not None: hi=min(hi,0.999/np.max(cap))
    if R.mean()<=0: return 0.,0.
    o=minimize_scalar(lambda r:-np.mean(np.log1p(r*R)),bounds=(0,hi),method='bounded',options=dict(xatol=1e-7))
    return float(o.x),float(-o.fun)
def cohorts(X,w=None):
    """ritorna (x,m,month): x = somma w_i R_i per coorte (per unita' di rischio), m = somma w_i cap_i (margine per unita' di rischio)."""
    w=np.ones(len(X)) if w is None else np.asarray(w,float)
    g=pd.DataFrame(dict(e=X.entry.values,x=w*X.R.values,m=w*X.cap.values)).groupby('e').sum()
    return g.x.values,g.m.values,pd.DatetimeIndex(g.index).to_period('M')
def kelly_coh(X,w=None):
    """Kelly con trade simultanei nella coorte; r = rischio per trade di peso 1. Ritorna r*, crescita log per ANNO."""
    x,m,_=cohorts(X,w); hi=0.999/m.max()
    if x.mean()<=0: return 0.,0.
    o=minimize_scalar(lambda r:-np.sum(np.log1p(r*x)),bounds=(0,hi),method='bounded',options=dict(xatol=1e-7))
    return float(o.x),float(-o.fun)/years_of(X)
def growth_coh(X,r,w=None):
    x,m,_=cohorts(X,w); r=min(r,0.999/m.max()); return float(np.sum(np.log1p(r*x)))/years_of(X)
def tstat(R): R=np.asarray(R,float); return R.mean()/R.std(ddof=1)*np.sqrt(len(R)) if len(R)>2 else np.nan
# ---------- bootstrap ----------
def tensors(X,w=None):
    """tensori [mese, coorte, slot] con padding; include i mesi vuoti."""
    w=np.ones(len(X)) if w is None else np.asarray(w,float)
    X=X.assign(w=w,mo=X.entry.dt.to_period('M'))
    months=pd.period_range(X.mo.min(),X.mo.max(),freq='M'); mi={p:i for i,p in enumerate(months)}
    co=[(mi[mo],g) for (mo,e),g in X.groupby(['mo','entry'],sort=True)]
    cnt=np.zeros(len(months),int)
    for i,_ in co: cnt[i]+=1
    C=max(cnt.max(),1); S=max(len(g) for _,g in co)
    R=np.zeros((len(months),C,S)); W=np.zeros_like(R); CAP=np.zeros_like(R); pos=np.zeros(len(months),int)
    for i,g in co:
        k=len(g); R[i,pos[i],:k]=g.R.values; W[i,pos[i],:k]=g.w.values; CAP[i,pos[i],:k]=g.cap.values; pos[i]+=1
    return R,W,CAP
def sim(T,base,years=3,n=4000,seed=7,dyn=None,ret_paths=False):
    """T=tensors(); base = rischio per trade di peso 1; dyn = regola dinamica (dict). Ritorna metriche."""
    R,W,CAP=T; M,C,S=R.shape; rng=np.random.default_rng(seed)
    idx=rng.integers(0,M,(n,12*years))
    Rp=R[idx].reshape(n,-1,S); Wp=W[idx].reshape(n,-1,S); Cp=CAP[idx].reshape(n,-1,S); TT=Rp.shape[1]
    eq=np.ones(n); pk=np.ones(n); mdd=np.zeros(n); mn=np.ones(n); k=np.ones(n); cut=np.zeros(n,bool); nl=np.zeros(n,int)
    dyn=dyn or {}; kind=dyn.get('kind')
    mend=np.ones((n,12*years)) if ret_paths else None
    for t in range(TT):
        dd=eq/pk-1
        if kind=='dd':        # taglia il rischio sotto x di drawdown; isteresi opzionale
            x=dyn['x']; cut=np.where(dd<=-x,True,np.where(dd>=-x*dyn.get('rec',1.0),False,cut)); k=np.where(cut,dyn['f'],1.0)
        elif kind=='floor':   # rischio proporzionale alla distanza dal pavimento (TIPP)
            k=np.clip(1+dd/dyn['x'],dyn.get('kmin',0.0),1.0)
        r=base*k[:,None]*Wp[:,t,:]
        mg=(r*Cp[:,t,:]).sum(1); sc=np.where(mg>0.999,0.999/np.maximum(mg,1e-12),1.0)
        ret=(r*Rp[:,t,:]).sum(1)*sc
        eq=eq*np.maximum(1+ret,1e-9); pk=np.maximum(pk,eq); mdd=np.minimum(mdd,eq/pk-1); mn=np.minimum(mn,eq)
        act=Wp[:,t,:].sum(1)>0
        if kind=='anti':      # dopo una coorte vincente aumenta, dopo una perdente torna a 1
            k=np.where(act&(ret>0),np.minimum(k*dyn['up'],dyn['kmax']),np.where(act&(ret<0),1.0,k))
        elif kind=='mart':    # dopo una perdente aumenta, dopo una vincente torna a 1
            k=np.where(act&(ret<0),np.minimum(k*dyn['up'],dyn['kmax']),np.where(act&(ret>0),1.0,k))
        elif kind=='streak':  # dopo nL perdite consecutive dimezza finche' non arriva una vincita
            nl=np.where(act&(ret<0),nl+1,np.where(act&(ret>0),0,nl)); k=np.where(nl>=dyn['nL'],dyn['f'],1.0)
        if ret_paths and (t+1)%C==0: mend[:,(t+1)//C-1]=eq
    cg=eq**(1/years)-1
    out=dict(cagr_p50=np.median(cg),cagr_p05=np.quantile(cg,.05),mese_p50=(1+np.median(cg))**(1/12)-1,dd_p50=-np.median(mdd),dd_p95=-np.quantile(mdd,.05),
             p_dd50=(mdd<=-.5).mean(),p_meta=(mn<=.5).mean(),p_rovina=(mn<=.1).mean())
    return (out,mend) if ret_paths else out
