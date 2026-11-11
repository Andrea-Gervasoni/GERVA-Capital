"""Segnale di posizionamento con storia lunga: posizione netta giornaliera di HLP per moneta (stats `hlp_positions`, 2023-06-13 -> 2026-04-03).
HLP e' la controparte passiva della folla dei taker: HLP corto = folla lunga. Domanda: la posizione di HLP prevede il rendimento a 24h di BTC/ETH/SOL?
Selezione 2023-06..2024-12, verifica 2025-01..2026-04 (prima del 2023 il dato non esiste). Il dato e' giornaliero: orizzonti 4-12h NON verificabili qui."""
import json, numpy as np, pandas as pd
from comune import *
pd.set_option('display.width',250); pd.set_option('display.float_format',lambda x:f'{x:.3f}')
hp=pd.DataFrame(json.load(open('data/stats/hlp_positions.json'))['chart_data']); hp['time']=pd.to_datetime(hp.time)
N=hp.pivot_table(index='time',columns='coin',values='daily_ntl',aggfunc='sum')
h=json.load(open('data/hlp_vaultDetails.json')); tv=serie({'all':dict(h['portfolio'])['allTime']}).av; tv=tv.reindex(tv.index.union(N.index)).ffill().reindex(N.index)
oi=pd.DataFrame(json.load(open('data/stats/open_interest.json'))['chart_data']); oi['time']=pd.to_datetime(oi.time); OI=oi.pivot_table(index='time',columns='coin',values='open_interest',aggfunc='sum')
px={}
for c in ['BTC','ETH','SOL']:
    d=pd.read_parquet(ROOT+f'/data_cache/bn_spot_1d_{c}USDT.parquet'); d.index=pd.to_datetime(d.index); px[c]=d['close']
PX=pd.DataFrame(px); R=PX.pct_change()
print('giorni',len(N),N.index[0].date(),N.index[-1].date(),'| prezzi fino a',PX.index[-1].date())
COST=2*(4.5+2)/1e4   # per cambio di segno completo (entrata+uscita) per lato: 6.5 bp per lato
ntrial=0; rows=[]
def prova(nome,sig,coin,lag):
    """sig del giorno D (noto a fine D, 00:00 UTC di D+1); posizione tenuta nel giorno D+1+lag (chiusura-chiusura)."""
    global ntrial; ntrial+=1
    pos=np.sign(sig).shift(1+lag).reindex(R.index); r=(pos*R[coin]); cost=pos.diff().abs().fillna(0)*COST/2; net=(r-cost).dropna()
    out={}
    for lab,a,b in [('tutto','2023-06-01','2026-12-31'),('sel','2023-06-01','2024-12-31'),('ver','2025-01-01','2026-12-31')]:
        x=net[a:b]; x=x[x.index<=N.index[-1]+pd.Timedelta(days=2)]
        out[lab]=x.mean()/x.std()*np.sqrt(365) if x.std()>0 else np.nan
    x=net[net.index<=N.index[-1]+pd.Timedelta(days=2)]; ic=sig.shift(1+lag).reindex(R.index).corr(R[coin],method='spearman')
    rows.append(dict(segnale=nome,coin=coin,lag=lag,S_tutto=out['tutto'],S_sel=out['sel'],S_ver=out['ver'],t=x.mean()/x.std()*np.sqrt(len(x)),IC=ic,gg_in_pos=(pos.abs()>0).mean(),cambi_anno=pos.diff().abs().sum()/2/len(x)*365))
for c in ['BTC','ETH','SOL']:
    lev=N[c]/tv; z=(lev-lev.rolling(30).mean())/lev.rolling(30).std(); ch=lev.diff(); tot=N.sum(axis=1)/tv; sh=N[c]/OI[c].reindex(N.index)
    for lag in (0,1):
        prova('con HLP: segno della posizione netta',lev,c,lag)
        prova('con HLP: z-score 30g della posizione',z,c,lag)
        prova('con HLP: variazione 1g',ch,c,lag)
        prova('con HLP: netto di tutte le monete',tot,c,lag)
        prova('con HLP: z 30g di posizione/OI',(sh-sh.rolling(30).mean())/sh.rolling(30).std(),c,lag)
T=pd.DataFrame(rows); print(T.to_string())
print('\nprove contate:',ntrial,'(x2 se si conta anche il verso opposto: lo Sharpe del verso "contro HLP" e\' circa il negativo meno i costi)')
print('media |Sharpe verifica| =%.2f ; quota di segni concordi selezione/verifica = %.2f'%(T.S_ver.abs().mean(),(np.sign(T.S_sel)==np.sign(T.S_ver)).mean()))
b=T[T.lag==0].sort_values('S_sel',ascending=False).head(3); print('\nmigliori 3 in SELEZIONE (lag 0) e loro verifica:'); print(b[['segnale','coin','S_sel','S_ver','t']].to_string())
# estremi: decili del segnale z
print('\nrendimento medio a 24h (bp) per quintile dello z-score 30g della posizione HLP (giorno dopo):')
for c in ['BTC','ETH','SOL']:
    lev=N[c]/tv; z=((lev-lev.rolling(30).mean())/lev.rolling(30).std()).shift(1).reindex(R.index); j=pd.concat([z,R[c]],axis=1).dropna(); j.columns=['z','r']; j['q']=pd.qcut(j.z,5,labels=False)
    print(c,(j.groupby('q').r.mean()*1e4).round(1).to_dict(),'n',len(j))
