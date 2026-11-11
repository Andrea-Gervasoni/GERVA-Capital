"""Dal singolo trade al conto: rischio per trade, composizione, Monte Carlo a blocchi mensili, stress. SIMULATO."""
import pickle, numpy as np, pandas as pd, sys
ALL=pickle.load(open('research/v5/v4/_cache/trades.pkl','rb')); rng=np.random.default_rng(11)
CFG={'A stop 1,7% (30x)':(0.017,('alta',),None,'long'),'B stop 2,7% trail (20x)':(0.027,('alta',),2.0,'long'),'C stop 1xATR trail (~11x)':('atr1.0',('alta',),2.0,'long'),
     'D stop 6% (9,5x)':(0.06,('alta',),None,'long'),'E stop 0,9% (50x)':(0.009,('alta',),None,'long'),'F stop 1,2% (40x)':(0.012,('alta',),None,'long')}
def paths(T,r,years,scen,n=3000):
    T=T.sort_values('exit').copy(); T['m']=pd.to_datetime(T.exit).dt.to_period('M')
    if scen=='verifica': T=T[T.entry>='2023-01-01']
    R=T.R.values.copy(); full=(1/(T.L*T.s)).values                        # perdita se si perde tutto il margine, in R
    if scen=='pessimista': R=R-0.5*T.R.mean()
    groups=[g.index.values for _,g in T.reset_index(drop=True).groupby('m')]
    T=T.reset_index(drop=True); out=[]
    for _ in range(n):
        pick=rng.integers(0,len(groups),12*years); ix=np.concatenate([groups[p] for p in pick]); x=R[ix].copy()
        if scen=='stress':
            lost=x<=-0.9; bad=lost&(rng.random(len(x))<0.10); x[bad]=-full[ix][bad]          # 1 stop su 10 salta: si perde tutto il margine
            ev=rng.random(len(x))<(1/ (len(R)/ ((pd.to_datetime(T.entry).max()-pd.to_datetime(T.entry).min()).days/365.25)))  # un evento l'anno
            x[ev]=-full[ix][ev]*3                                                              # cascata: tre posizioni perdono il margine insieme
        eq=np.cumprod(np.maximum(1+r*x,0.0)); peak=np.maximum.accumulate(np.maximum(eq,1e-12))
        out.append((eq[-1],(eq/peak-1).min(),eq.min()))
    o=np.array(out); cagr=o[:,0]**(1/years)-1
    return dict(cagr_p50=np.median(cagr),cagr_p05=np.quantile(cagr,.05),cagr_p95=np.quantile(cagr,.95),dd_p50=np.median(o[:,1]),dd_p95=np.quantile(o[:,1],.05),
                p_meno30=(o[:,2]<=0.7).mean(),p_dimezzato=(o[:,2]<=0.5).mean(),mese_medio=(1+np.median(cagr))**(1/12)-1)
rows=[]
for name,k in CFG.items():
    T=ALL[k]; y=(T.entry.max()-T.entry.min()).days/365.25
    hist=T.sort_values('exit'); 
    streak=mx=0
    for v in (hist.R<0).values:
        streak=streak+1 if v else 0; mx=max(mx,streak)
    print(f"\n== {name}: {len(T)} trade, {len(T)/y:.0f}/anno, leva {T.L.median():.0f}x, distanza liquidazione {(1/T.L-0.005).median():.2%}, stop {T.s.median():.2%}, R medio {T.R.mean():.3f} (dev.std {T.R.std():.2f}), vincenti {(T.R>0).mean():.0%}, serie negativa piu' lunga {mx}, margine per 1% di rischio {(0.01/(T.L*T.s)).median():.2%} del patrimonio, controvalore per 1% di rischio {(0.01/T.s).median():.0%}")
    kelly=T.R.mean()/T.R.var(); print(f"   Kelly pieno: rischio {kelly:.2%} per trade; meta' Kelly {kelly/2:.2%}")
    for r in (0.0025,0.005,0.01,0.02,0.03):
        for scen in ('base','pessimista','verifica','stress'):
            o=paths(T,r,3,scen); o.update(cfg=name,rischio=r,scenario=scen); rows.append(o)
R=pd.DataFrame(rows).set_index(['cfg','rischio','scenario']); pd.set_option('display.width',250,'display.max_rows',500)
print(R.round(3).to_string()); R.to_pickle('research/v5/v4/_cache/account.pkl')
