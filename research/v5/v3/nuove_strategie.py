import sys, warnings; sys.path.insert(0,'/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, math
from gerva.data import Store, yahoo_panel
from gerva.backtest import Costs, run
from gerva.strategies import daily as SD, book
from gerva.portfolio import risk_parity, combine
from gerva.validation import metrics as M
from gerva import ensemble, indicators as ind
from gerva.research.run import Lab
L=Lab('/home/user/GERVA-Capital'); L.load_daily(); L.load_crypto()
close,dvol,ret,rf=L.cclose,L.cdvol,L.cret,L.rf365
D=pd.read_parquet('/home/user/GERVA-Capital/research/v5/series.parquet'); S0=D[['CR-TREND','CR-XSMOM','EQ-MR','MA-TREND']]; port=D['PORT'].dropna()
SPL='2023-01-01'; C=Costs(trade=0.003,cash_haircut=1.0)
rows=[]; cand={}
def rep(name,r,per=365,rfx=None):
    rfx=rf if rfx is None else rfx; r=r.dropna().loc['2018':]
    a,b,c=M.summary(r,rfx,per),M.summary(r.loc[:SPL],rfx,per),M.summary(r.loc[SPL:],rfx,per)
    x=r.reindex(S0.index).fillna(0.0); cand[name]=x
    S=S0.copy(); S[name]=x; p=combine(S,risk_parity(S))
    pa,pb,pc=(M.sharpe(p.loc[sl],rf,365) for sl in (slice(None,None),slice(None,SPL),slice(SPL,None)))
    mm=((1+x).resample('ME').prod()-1).corr((1+port).resample('ME').prod()-1)
    rows.append(dict(strategia=name,cagr=a['cagr'],vol=a['vol'],sharpe=a['sharpe'],sh_scelta=b['sharpe'],sh_verifica=c['sharpe'],maxdd=a['max_dd'],corr_port=mm,port_sharpe=pa,port_scelta=pb,port_verifica=pc))
base=dict(strategia='PORTAFOGLIO ATTUALE (4 strategie)',port_sharpe=M.sharpe(port,rf,365),port_scelta=M.sharpe(port.loc[:SPL],rf,365),port_verifica=M.sharpe(port.loc[SPL:],rf,365))
# 1. trend dimensionato per conviction
maj=['BTC','ETH']; Wt=book.cr_trend(close)
tiers={}
for c in maj:
    px=close[c].dropna(); bars=pd.DataFrame(dict(open=px,high=px,low=px,close=px))
    cv=ensemble.conviction(ensemble.crypto_signals(bars,close['BTC']).drop(columns=['ibs_low']),'crypto'); tiers[c]=cv['tier'].map({'bassa':0.0,'media':0.5,'alta':1.0}).reindex(close.index).fillna(0)
Wc=SD.hold((Wt.replace(0,np.nan).ffill().fillna(0)*0+0.5)*pd.DataFrame(tiers),1)   # 50% per moneta x livello
rep('1. BTC+ETH pesati per conviction (0 / 0,5 / 1)',run(SD.hold(pd.DataFrame(tiers)*0.5,7),ret[maj],0.0,C,periods=365,band=0.03).ret)
rep('1b. trend attuale x conviction',run(SD.hold(Wt*pd.DataFrame(tiers).clip(lower=0.5),7),ret[maj],0.0,C,periods=365,band=0.03).ret)
# 2. meta-modello: regressione logistica ridge sui 12 segnali, riaddestrata ogni anno sui soli dati precedenti
def logit_fit(X,y,lam=5.0,it=200):
    w=np.zeros(X.shape[1])
    for _ in range(it):
        p=1/(1+np.exp(-X@w)); g=X.T@(p-y)/len(y)+lam*w/len(y); H=(X.T*(p*(1-p)))@X/len(y)+lam*np.eye(len(w))/len(y); w-=np.linalg.solve(H,g)
    return w
pos={}
for c in maj:
    px=close[c].dropna(); bars=pd.DataFrame(dict(open=px,high=px,low=px,close=px)); F=ensemble.crypto_signals(bars,close['BTC']).drop(columns=['ibs_low']).dropna()
    y=(ret[c].shift(-1).reindex(F.index)>0).astype(float); X=np.column_stack([np.ones(len(F)),F.values]); p=pd.Series(np.nan,index=F.index)
    for yr in range(2019,2027):
        tr=(F.index<f'{yr}-01-01')&(F.index>=f'{yr-4}-01-01'); te=(F.index>=f'{yr}-01-01')&(F.index<f'{yr+1}-01-01')
        if tr.sum()>300 and te.sum(): p[te]=1/(1+np.exp(-X[te]@logit_fit(X[tr][:-1],y[tr].values[:-1])))
    pos[c]=((p-0.5)*10).clip(0,1)*0.5
rep('2. meta-modello logistico walk-forward (BTC+ETH)',run(SD.hold(pd.DataFrame(pos).reindex(close.index).fillna(0),7),ret[maj],0.0,C,periods=365,band=0.03).ret.loc['2019':])
# 3. trend a 4 ore su BTC ed ETH (perpetual, 7 pb)
st=Store('/home/user/GERVA-Capital/data_cache'); legs=[]
for c in maj:
    b=st.get(f'bn_spot_5m_{c}USDT')['close'].resample('4h').last().dropna(); r4=b.pct_change()
    sig=sum(np.sign(b/b.shift(k)-1) for k in (6,18,42,84))/4; sig=sig.clip(lower=0); v=r4.ewm(span=42).std()*math.sqrt(6*365)
    w=(sig*(0.40/v)).clip(upper=1.0).fillna(0); wq=(w*4).round()/4
    for fee,lab in ((0.0007,'perp 7 pb'),(0.003,'spot 30 pb')):
        x=(wq.shift(1)*r4-wq.diff().abs().fillna(0)*fee); legs.append((lab,x.groupby(x.index.normalize()).sum()))
for lab in ('perp 7 pb','spot 30 pb'): rep(f'3. trend a 4 ore BTC+ETH, {lab}',pd.concat([x for l,x in legs if l==lab],axis=1).mean(axis=1))
# 4. momentum residuo (alt rispetto a BTC) 5 su 20 con filtro
btc_r=ret['BTC']; beta=ret.rolling(60).cov(btc_r).div(btc_r.rolling(60).var(),axis=0); resid=ret.sub(beta.mul(btc_r,axis=0))
rmom=resid.rolling(28).sum()/resid.rolling(28).std()/math.sqrt(28)
adv=dvol.rolling(30,min_periods=20).mean(); btc_up=close['BTC']>close['BTC'].rolling(100).mean()
def xs(score,top=5,uni=20,reb=7,filt=True,largest=True):
    W=pd.DataFrame(0.0,index=close.index,columns=close.columns); last=None
    for i,d in enumerate(close.index):
        if i%reb==0:
            ok=adv.loc[d].notna()&score.loc[d].notna(); liq=adv.loc[d][ok].nlargest(uni).index; s=score.loc[d][liq]
            pick=(s.nlargest(top) if largest else s.nsmallest(top)).index; last=pd.Series(0.0,index=close.columns)
            if len(pick) and (not filt or bool(btc_up.get(d,False))): last[pick]=1/top
        if last is not None: W.loc[d]=last
    return W
def scaled(r): v=(r.rolling(60,min_periods=30).std()*math.sqrt(365)).shift(1); return r*(0.25/v.where(v>0)).clip(upper=1).fillna(0.3)
rep('4. momentum residuo 5 su 20, filtro BTC, vol 25%',scaled(run(xs(rmom),ret,0.0,C,periods=365,band=0.03).ret.loc['2018':]))
# 5. inversione di breve: i 5 peggiori a 3 giorni tra i 20 piu' scambiati, con BTC in trend
r3=close/close.shift(3)-1
rep('5. inversione a 3 giorni (5 peggiori su 20), filtro BTC, vol 25%',scaled(run(xs(r3,reb=3,largest=False),ret,0.0,C,periods=365,band=0.03).ret.loc['2018':]))
# 11. doppio momentum BTC/ETH: si tiene il piu' forte a 30-60 giorni se sale
mom=(close[maj]/close[maj].shift(30)-1+close[maj]/close[maj].shift(60)-1)/2
W=pd.DataFrame(0.0,index=close.index,columns=maj); best=mom.fillna(-9).idxmax(axis=1)
for c in maj: W[c]=((best==c)&(mom[c]>0)).astype(float)
vol=ind.ewma_vol(ret[maj],30,365); W=(W*(0.40/vol)).clip(upper=1.0).fillna(0)
rep('11. doppio momentum BTC/ETH (il piu forte, se sale)',run(SD.hold(W,7),ret[maj],0.0,C,periods=365,band=0.03).ret)
# 13. IBS su Nasdaq solo con VIX sopra la mediana (ipervenduto in mercati agitati)
P=yahoo_panel(['QQQ','SPY','^VIX','^IRX'],st); k=P['adj']['SPY'].notna(); P={a:b[k] for a,b in P.items()}; er=P['adj'].pct_change(); rfd=(P['adj']['^IRX']/100/252).ffill()
for lab,cond in (('VIX sopra la mediana',P['adj']['^VIX']>P['adj']['^VIX'].rolling(252).median()),('VIX sotto la mediana',P['adj']['^VIX']<=P['adj']['^VIX'].rolling(252).median())):
    leg=[]
    for s in ('SPY','QQQ'):
        w=SD.ibs_reversion(P['high'][s],P['low'][s],P['close'][s],trend_ma=None)*cond.astype(float); leg.append(0.5*(w.shift(1).fillna(0)*(er[s]-(rfd+0.015/252))-w.diff().abs().fillna(0)*0.0005))
    rep(f'13. IBS su indici solo con {lab}',sum(leg),252,rfd)
T=pd.DataFrame([base]+rows); pd.set_option('display.width',260); print(T.round(3).to_string(index=False))
pd.to_pickle(cand,'/tmp/lab3/cand.pkl'); T.to_pickle('/tmp/lab3/table.pkl')
# 6. stagionalita' di BTC
b=st.get('bn_spot_5m_BTCUSDT')['close'].resample('1h').last().pct_change().dropna()
h=b.groupby(b.index.hour).agg(lambda x:x.mean()*1e4); hs=b.loc['2023':].groupby(b.loc['2023':].index.hour).agg(lambda x:x.mean()*1e4)
print('BTC rendimento medio per ora UTC (pb) tutto:',h.round(1).to_dict()); print('dal 2023:',hs.round(1).to_dict())
dw=ret['BTC'].loc['2018':]; print('BTC per giorno della settimana (pb): scelta',(dw.loc[:SPL].groupby(dw.loc[:SPL].index.dayofweek).mean()*1e4).round(0).to_dict(),'verifica',(dw.loc[SPL:].groupby(dw.loc[SPL:].index.dayofweek).mean()*1e4).round(0).to_dict())
# 7. liquidita' ferma remunerata
a=risk_parity(S0); print('nota: quota media di capitale non investita da stimare dalle esposizioni; tasso a breve medio 2023-26:', round(float(rf.loc['2023':].mean()*365),4))
