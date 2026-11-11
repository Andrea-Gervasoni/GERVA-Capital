import sys, warnings; sys.path.insert(0,'/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from gerva.data import Store, yahoo_panel
from gerva import indicators as ind
st=Store('/home/user/GERVA-Capital/data_cache')
SPL='2023-01-01'
def feats_crypto(c):
    d=st.get(f'bn_spot_1d_{c}USDT'); cl=d['close']; r=cl.pct_change()
    F=pd.DataFrame(index=cl.index)
    for lb in (10,30,60,120): F[f'trend{lb}']=(cl/cl.shift(lb)-1>0)
    F['ma100']=cl>cl.rolling(100).mean()
    F['ma200']=cl>cl.rolling(200).mean()
    F['brk20']=cl>=cl.rolling(20).max().shift(1)
    v=r.rolling(20).std(); F['lowvol']=v<v.rolling(365,min_periods=120).median()
    F['ibs_low']=ind.ibs(d['high'],d['low'],cl)<0.2
    F['mom7']=(cl/cl.shift(7)-1>0)
    btc=st.get('bn_spot_1d_BTCUSDT')['close']; F['btc_ma100']=(btc>btc.rolling(100).mean()).reindex(cl.index)
    try:
        f=st.get(f'bn_fund_{c}USDT').iloc[:,0]; fd=f.groupby((f.index-pd.Timedelta(seconds=1)).normalize()).sum()
        F['fund_ok']=(fd.rolling(7).mean()*365<0.30).reindex(cl.index).fillna(True)   # funding non surriscaldato
    except Exception: pass
    return F.astype(float), r, d
def feats_eq(s,P,g):
    cl=P['adj'][s]; r=cl.pct_change(); F=pd.DataFrame(index=cl.index)
    for lb in (21,63,126,252): F[f'trend{lb}']=(cl/cl.shift(lb)-1>0)
    F['ma200']=cl>cl.rolling(200).mean()
    F['ibs_low']=ind.ibs(P['high'][s],P['low'][s],P['close'][s])<0.2
    v=r.rolling(20).std(); F['lowvol']=v<v.rolling(252,min_periods=120).median()
    vix,v3=P['adj']['^VIX'],P['adj']['^VIX3M']; F['contango']=(vix/v3<0.95)
    F['vix_calm']=vix<vix.rolling(252).median()
    gf=ind.gex_features(g['gex']); F['gex_hi']=(gf['rank']>0.5).reindex(cl.index)
    F['down3']=(cl/cl.shift(3)-1<0)        # ritorno alla media a 3 giorni
    return F.astype(float), r
P=yahoo_panel("SPY QQQ ^VIX ^VIX3M ^IRX".split(), st); keep=P['adj']['SPY'].notna(); P={k:v[keep] for k,v in P.items()}
g=st.get('gex')
out={}
def study(name,F,r,start,per):
    F=F.loc[start:].dropna(); nxt=r.shift(-1).reindex(F.index)
    score=F.sum(axis=1); n=F.shape[1]
    df=pd.DataFrame(dict(score=score,nxt=nxt)).dropna()
    # terzili fissati sul periodo di scelta
    q=df.loc[:SPL,'score'].quantile([1/3,2/3]).values
    df['tier']=np.where(df.score<=q[0],'bassa',np.where(df.score<=q[1],'media','alta'))
    print(f'\n== {name}: {n} segnali, {len(df)} giorni, soglie terzili {q}')
    for lab,sub in (('scelta',df.loc[:SPL]),('verifica',df.loc[SPL:])):
        t=sub.groupby('tier').nxt.agg(n='size',media_pb=lambda x:x.mean()*1e4,hit=lambda x:(x>0).mean(),vol=lambda x:x.std()*np.sqrt(per),sharpe=lambda x:x.mean()/x.std()*np.sqrt(per),peggiore='min').reindex(['bassa','media','alta'])
        print(lab); print(t.round(3).to_string())
    # correlazione media tra segnali, e numero effettivo di segnali indipendenti
    C=F.corr().values; ev=np.linalg.eigvalsh(C); neff=(ev.sum()**2)/(ev**2).sum()
    print('correlazione media tra segnali',round((C.sum()-n)/(n*n-n),2),'| segnali effettivi',round(neff,1))
    # singoli segnali: Sharpe del "long quando acceso" IS/OOS
    rows={}
    for c in F:
        x=(F[c]*nxt).dropna(); rows[c]=(x.loc[:SPL].mean()/x.loc[:SPL].std()*np.sqrt(per), x.loc[SPL:].mean()/x.loc[SPL:].std()*np.sqrt(per))
    print('Sharpe per segnale (scelta, verifica):',{k:(round(a,2),round(b,2)) for k,(a,b) in rows.items()})
    out[name]=df; return df,F
for c in ('BTC','ETH'):
    F,r,d=feats_crypto(c); study(c,F,r,'2018-06-01',365)
for s in ('SPY','QQQ'):
    F,r=feats_eq(s,P,g); study(s,F,r,'2012-01-01',252)
pd.to_pickle(out,'research/v5/v2/_cache/conv.pkl')
