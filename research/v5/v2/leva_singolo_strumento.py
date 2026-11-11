import sys, warnings; sys.path.insert(0,'/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from gerva.data import Store, yahoo_panel
st=Store('/home/user/GERVA-Capital/data_cache')
conv=pd.read_pickle('research/v5/v2/_cache/conv.pkl')
P=yahoo_panel("SPY QQQ ^IRX".split(), st); keep=P['adj']['SPY'].notna(); P={k:v[keep] for k,v in P.items()}
rfd=(P['adj']['^IRX']/100/252).ffill()
def ohlc(name):
    if name in ('BTC','ETH'):
        d=st.get(f'bn_spot_1d_{name}USDT'); pc=d['close'].shift(1)
        f=st.get(f'bn_fund_{name}USDT').iloc[:,0]; fd=f.groupby((f.index-pd.Timedelta(seconds=1)).normalize()).sum().reindex(d.index).fillna(0.0003)
        return pd.DataFrame(dict(o=d['open']/pc-1,l=d['low']/pc-1,c=d['close']/pc-1,carry=fd)), 365, 0.0007, 0.005
    k=P['adj'][name]/P['close'][name]; pc=P['adj'][name].shift(1)
    return pd.DataFrame(dict(o=P['open'][name]*k/pc-1,l=P['low'][name]*k/pc-1,c=P['adj'][name]/pc-1,carry=rfd)), 252, 0.0001, 0.0   # futures: il finanziamento e' il tasso
def simulate(X, L, cost, stop=None, slip=0.001, mm=0.005):
    """X: o,l,c (rendimenti dal close precedente), carry per unita' di esposizione; L: leva decisa la sera prima (allineata al giorno).
    Restituisce rendimento giornaliero del conto, flag liquidazione, distanza minima dalla liquidazione."""
    o,l,c,car=X['o'].values,X['l'].values,X['c'].values,X['carry'].values
    Lv=L.values; n=len(c); r=np.zeros(n); liq=np.zeros(n,bool); stp=np.zeros(n,bool)
    prev=0.0
    for i in range(n):
        Li=Lv[i]
        if Li<=0: r[i]=-abs(Li-prev)*cost; prev=Li; continue
        tc=abs(Li-prev)*cost; prev=Li
        liq_lvl=-(1.0/Li-mm)                      # movimento avverso che azzera il margine
        if o[i]<=liq_lvl or l[i]<=liq_lvl:
            if stop is not None and -stop/Li>liq_lvl and o[i]>-stop/Li:   # lo stop sta prima della liquidazione e non c'e' stato gap oltre lo stop
                r[i]=-stop-slip*Li-tc; stp[i]=True; prev=0.0; continue
            r[i]=-1.0; liq[i]=True; prev=0.0; continue
        if stop is not None:
            s=-stop/Li
            if o[i]<=s: r[i]=Li*o[i]-slip*Li-tc; stp[i]=True; prev=0.0; continue      # gap oltre lo stop: si esce all'apertura
            if l[i]<=s: r[i]=-stop-slip*Li-tc; stp[i]=True; prev=0.0; continue
        r[i]=Li*(c[i]-car[i])-tc
    return pd.Series(r,index=X.index), liq, stp
def stats(r,per):
    eq=(1+r).cumprod(); yrs=len(r)/per
    if (r<=-1).any(): return dict(cagr=-1.0,vol=np.nan,sharpe=np.nan,maxdd=-1.0,worst=float(r.min()))
    return dict(cagr=eq.iloc[-1]**(1/yrs)-1,vol=r.std()*np.sqrt(per),sharpe=r.mean()/r.std()*np.sqrt(per),maxdd=float((eq/eq.cummax()-1).min()),worst=float(r.min()))
res={}
for name in ('BTC','ETH','SPY','QQQ'):
    X,per,cost,_=ohlc(name); df=conv[name]
    tier=df['tier'].shift(1).reindex(X.index)       # livello deciso con i dati della sera prima
    X=X.loc[df.index[1]:].dropna(); tier=tier.reindex(X.index)
    vol=X['c'].rolling(20).std().shift(1)
    print(f'\n===== {name}: giorni {len(X)}; quota giorni alta {np.mean(tier=="alta"):.2f}, media {np.mean(tier=="media"):.2f}')
    print('distanza: peggior minimo intraday dal close precedente', round(X.l.min(),3),'| 1° percentile', round(X.l.quantile(0.01),3),'| peggior gap apertura', round(X.o.min(),3))
    rows=[]
    for Lhi in (1,2,3,5,10,15,20,30):
        for scheme in ('solo alta','alta + media a 1/3'):
            L=pd.Series(np.where(tier=='alta',Lhi,np.where((tier=='media')&(scheme!='solo alta'),Lhi/3,0.0)),index=X.index)
            for stop in (None,0.05,0.10):
                r,liq,stp=simulate(X,L,cost,stop)
                s=stats(r,per); s2=stats(r.loc['2023':],per)
                rows.append(dict(Lalta=Lhi,schema=scheme,stop=stop,cagr=s['cagr'],vol=s['vol'],sharpe=s['sharpe'],maxdd=s['maxdd'],peggiore=s['worst'],liquidazioni=int(liq.sum()),stop_n=int(stp.sum()),cagr_verifica=s2['cagr'],dist_liq=1/Lhi-0.005))
    T=pd.DataFrame(rows); res[name]=T
    pd.set_option('display.width',220)
    print(T[(T.schema=='solo alta')].round(3).to_string(index=False))
pd.to_pickle(res,'research/v5/v2/_cache/lev_hist.pkl')
