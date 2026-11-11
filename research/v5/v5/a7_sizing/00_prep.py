"""A7 - passo 0: arricchisce i flussi di trade v4 con conviction score e stato di volatilita' (ATR 14g noto la sera prima). SIMULATO."""
import sys,pickle,numpy as np,pandas as pd
sys.path.insert(0,'/home/user/GERVA-Capital/research/v5/v4'); sys.path.insert(0,'/home/user/GERVA-Capital')
import leva_trade_isolato as T
ALL=pickle.load(open('/home/user/GERVA-Capital/research/v5/v4/_cache/trades.pkl','rb'))
ATR={c:((T.D[c]['high']-T.D[c]['low'])/T.D[c]['close']).rolling(14).mean().shift(1) for c in T.D}
KEYS={'A30':(0.017,('alta',),None,'long'),'C11':('atr1.0',('alta',),2.0,'long'),'B20':(0.027,('alta',),None,'long'),'D17':(0.027,('alta',),2.0,'long'),
      'A30m':(0.017,('media','alta'),None,'long'),'S20':(0.027,'short',2.0,'short')}
out={}
for n,k in KEYS.items():
    X=ALL[k].copy().sort_values(['entry','coin']).reset_index(drop=True)
    X['score']=[T.CONV[c]['score'].get(pd.Timestamp(d)) for c,d in zip(X.coin,X.entry)]
    X['atr']=[ATR[c].get(pd.Timestamp(d)) for c,d in zip(X.coin,X.entry)]
    X['cap']=1/(X.L*X.s)   # perdita massima in R (margine isolato)
    out[n]=X
    y=(X.entry.max()-X.entry.min()).days/365.25
    print(n,k,'n',len(X),'per anno %.1f'%(len(X)/y),'R %.3f sd %.3f'%(X.R.mean(),X.R.std()),'minR %.2f cap %.2f'%(X.R.min(),X.cap.median()),'L %.1f'%X.L.median(),'score nan',X.score.isna().sum(),'atr med %.3f'%X.atr.median())
pickle.dump(out,open('trades_enriched.pkl','wb'))
