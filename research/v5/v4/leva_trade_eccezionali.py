import sys,pickle,numpy as np,pandas as pd; sys.path.insert(0,'/tmp/lab4'); sys.path.insert(0,'/home/user/GERVA-Capital')
import trade as T
ALL=pickle.load(open('/tmp/lab4/trades.pkl','rb'))
for name,k in {'A 1,7% 30x':(0.017,('alta',),None,'long'),'C 1xATR 11x':('atr1.0',('alta',),2.0,'long')}.items():
    X=ALL[k].copy(); X['score']=[T.CONV[c]['score'].get(pd.Timestamp(d)) for c,d in zip(X.coin,X.entry)]
    X['btcscore']=[T.CONV['BTC']['score'].get(pd.Timestamp(d)) for d in X.entry]
    X['n_alta']=[sum(T.CONV[c]['tier'].get(pd.Timestamp(d))=='alta' for c in T.CONV) for d in X.entry]
    X['ver']=X.entry>='2023-01-01'
    print(name)
    for lab,m in {'score 0,60-0,75':X.score<=0.75,'score 0,75-0,90':(X.score>0.75)&(X.score<=0.9),'score >0,90':X.score>0.9,'1 moneta alta':X.n_alta==1,'2 monete alte':X.n_alta==2,'3 monete alte':X.n_alta==3}.items():
        g=X[m]; print(f"  {lab:18s} n={len(g):4d} R={g.R.mean():+.3f} t={g.R.mean()/g.R.std()*np.sqrt(len(g)):+.2f} scelta={g[~g.ver].R.mean():+.3f} verifica={g[g.ver].R.mean():+.3f} vincenti={(g.R>0).mean():.0%}")
    print('  per moneta:',X.groupby('coin').R.agg(['count','mean']).round(3).to_dict('index'))
    print('  per anno:',X.groupby(pd.to_datetime(X.entry).dt.year).R.mean().round(2).to_dict())
