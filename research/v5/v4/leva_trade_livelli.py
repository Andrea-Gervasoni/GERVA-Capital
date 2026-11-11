"""Schema a livelli: rischio per trade legato alla conviction (confermato: score 0,60-0,75; eccezionale: > 0,75). SIMULATO."""
import sys,pickle,numpy as np,pandas as pd; sys.path.insert(0,'/tmp/lab4'); sys.path.insert(0,'/home/user/GERVA-Capital')
import trade as T
ALL=pickle.load(open('/tmp/lab4/trades.pkl','rb')); rng=np.random.default_rng(5)
def prep(k):
    X=ALL[k].copy().sort_values('exit').reset_index(drop=True); X['score']=[T.CONV[c]['score'].get(pd.Timestamp(d)) for c,d in zip(X.coin,X.entry)]
    X['exc']=X.score>0.75; X['m']=pd.to_datetime(X.exit).dt.to_period('M'); return X
A=prep((0.017,('alta',),None,'long')); C=prep(('atr1.0',('alta',),2.0,'long'))
def mc(X,rc,re,scen,years=3,n=3000):
    if scen=='verifica': X=X[X.entry>='2023-01-01'].reset_index(drop=True)
    R=X.R.values.copy(); r=np.where(X.exc,re,rc); full=(1/(X.L*X.s)).values
    if scen=='pessimista': R=R-0.5*X.R.mean()
    groups=[g.index.values for _,g in X.groupby('m')]; yrs=(pd.to_datetime(X.entry).max()-pd.to_datetime(X.entry).min()).days/365.25; out=[]
    for _ in range(n):
        ix=np.concatenate([groups[p] for p in rng.integers(0,len(groups),12*years)]); x=R[ix].copy()
        if scen=='stress':
            bad=(x<=-0.9)&(rng.random(len(x))<0.10); x[bad]=-full[ix][bad]
            ev=rng.random(len(x))<yrs/len(R); x[ev]=-full[ix][ev]*3
        eq=np.cumprod(np.maximum(1+r[ix]*x,0)); pk=np.maximum.accumulate(np.maximum(eq,1e-12)); out.append((eq[-1],(eq/pk-1).min(),eq.min()))
    o=np.array(out); cg=o[:,0]**(1/years)-1
    return dict(cagr_p50=np.median(cg),cagr_p05=np.quantile(cg,.05),dd_p50=np.median(o[:,1]),dd_p95=np.quantile(o[:,1],.05),p_meno30=(o[:,2]<=.7).mean(),p_dimezzato=(o[:,2]<=.5).mean(),mese=(1+np.median(cg))**(1/12)-1)
S={'S1 11x: 0,5% / 1%':(C,.005,.01),'S2 11x: 1% / 2%':(C,.01,.02),'S3 11x: 1,5% / 3%':(C,.015,.03),'S4 11x: 2% / 4%':(C,.02,.04),'S5 30x: 0,25% / 0,5%':(A,.0025,.005),'S6 30x: 0,5% / 1%':(A,.005,.01),'S7 30x: 1% / 2%':(A,.01,.02),
   'S8 11x solo eccezionali 2%':(C,0,.02),'S9 30x solo eccezionali 1%':(A,0,.01)}
rows=[]
for n,(X,rc,re) in S.items():
    for sc in ('base','pessimista','verifica','stress'):
        o=mc(X,rc,re,sc); o.update(schema=n,scenario=sc); rows.append(o)
R=pd.DataFrame(rows).set_index(['schema','scenario']); pd.set_option('display.width',250,'display.max_rows',200); print(R.round(3).to_string()); R.to_pickle('/tmp/lab4/tier.pkl')
for nm,X in (('A',A),('C',C)):
    print(nm,'eccezionali/anno',X.exc.sum()/((pd.to_datetime(X.entry).max()-pd.to_datetime(X.entry).min()).days/365.25),'R ecc',X[X.exc].R.mean(),'R conf',X[~X.exc].R.mean(),'esposizione mediana per 1% di rischio',(0.01/X.s).median())
