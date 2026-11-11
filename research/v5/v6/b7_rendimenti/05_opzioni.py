"""B7.5 - carry da opzioni su Deribit: vendita di call coperte / put garantite da cassa su BTC ed ETH. STIMA: non ci sono prezzi storici delle
opzioni; il premio e' Black-Scholes alla volatilita' DVOL (indice a 30 giorni, at-the-money) ridotta del 10% (spread denaro-lettera e
ala) meno commissione Deribit (0,03% del sottostante, tetto 12,5% del premio). Uscita a scadenza sul prezzo di chiusura. DVOL del giorno prima."""
import pandas as pd, numpy as np, warnings
from scipy.stats import norm
from lib import *
warnings.filterwarnings('ignore'); C='/home/user/GERVA-Capital/data_cache/'
def run(cur,T,delta,kind,hair=0.10):
    px=pd.read_parquet(C+f'yahoo_1d_{cur}-USD.parquet').close; dv=pd.read_parquet(C+f'v4_dvol_{cur}.parquet').close/100
    x=pd.concat([px,dv.shift(1)],axis=1,keys=['s','v']).dropna(); d=x.index[::T]; rows=[]
    for a,b in zip(d[:-1],d[1:]):
        S=x.s[a]; v=x.v[a]*(1-hair); t=T/365; z=norm.ppf(delta)   # d1 tale che N(d1)=delta (call) ; put: N(-d1)=delta
        if kind=='call':
            K=S*np.exp(-z*v*np.sqrt(t)+v*v*t/2); d1=z; prem=S*norm.cdf(d1)-K*norm.cdf(d1-v*np.sqrt(t)); pay=max(x.s[b]-K,0)
        else:
            K=S*np.exp(z*v*np.sqrt(t)+v*v*t/2); d1=-z; prem=K*norm.cdf(-(d1-v*np.sqrt(t)))-S*norm.cdf(-d1); pay=max(K-x.s[b],0)
        fee=min(0.0003*S,0.125*prem); rows.append((b,(prem-fee-pay)/S,(x.s[b]/S-1),prem/S))
    r=pd.DataFrame(rows,columns=['t','opt','und','prem']).set_index('t'); return r
n=0; print('P&L della sola opzione venduta, in % del sottostante; per=cicli/anno. beta = sensibilita\' al sottostante nel ciclo')
for cur in ['BTC','ETH']:
    for T in (7,30):
        for delta in (0.10,0.25):
            for kind in ('call','put'):
                r=run(cur,T,delta,kind); n+=1; per=365/T
                o=[]
                for nm,x in (('pieno',r),('scelta',r[:SEL_END]),('verifica',r[VER0:])):
                    m=x.opt.mean()*per*100; s=x.opt.std()*np.sqrt(per)*100; o.append(f'{nm} {m:+6.1f}%/a Sh {m/s:+.2f}')
                eq=r.opt.cumsum(); beta=np.polyfit(r.und,r.opt,1)[0]
                print(f'{cur} {kind:4s} {T:2d}g delta {delta:.2f}: '+' | '.join(o)+f' | premio lordo {r.prem.mean()*per*100:5.1f}%/a | peggior ciclo {r.opt.min()*100:+.1f}% | maxDD somma {((eq-eq.cummax()).min())*100:+.1f}% | beta {beta:+.2f} | t {r.opt.mean()/r.opt.std()*np.sqrt(len(r)):+.2f}')
                if (cur,T,delta)==('BTC',7,0.25): print('     per anno %:',(r.opt.groupby(r.index.year).sum()*100).round(1).to_dict())
print('varianti',n)
# strangle 25-delta settimanale BTC = call+put: e' vendita di varianza (gia' bocciata in v4), riportata per confronto
a=run('BTC',7,0.25,'call').opt+run('BTC',7,0.25,'put').opt; print('BTC strangle 7g 25d: media %+.1f%%/a Sharpe %.2f ; verifica %+.1f%%/a ; peggior settimana %+.1f%%'%(a.mean()*52*100,a.mean()/a.std()*np.sqrt(52),a[VER0:].mean()*52*100,a.min()*100))
for h in (0.0,0.2): 
    a=run('BTC',7,0.25,'call',h).opt; print(f'  sensibilita\' al taglio della volatilita\' ({h:.0%}): call BTC 7g 25d {a.mean()*52*100:+.1f}%/a (verifica {a[VER0:].mean()*52*100:+.1f}%/a)')
