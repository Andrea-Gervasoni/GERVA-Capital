"""Posizionamento dei conti migliori contro i peggiori (scelti a T=2026-05-21 con dati <= T) su BTC/ETH/SOL, ricostruito dai fill
(startPosition +/- sz). Segnale orario = esposizione media (nozionale/conto a T, tetto +/-5) dei 'top' meno quella dei 'bottom';
posizione presa all'apertura dell'ora successiva (+1 ora di ritardo nella variante), tenuta 4 o 24 ore. Prezzi: Binance spot 5m in cache (fino al 2026-10-31).
Limite: l'API restituisce al massimo ~10.000 fill recenti per conto (piu' qualche finestra): ogni conto entra solo nell'intervallo coperto."""
import numpy as np, pandas as pd
from comune import *
pd.set_option('display.width',250); pd.set_option('display.float_format',lambda x:f'{x:.3f}')
F=pd.read_parquet('data/fills.parquet'); S=pd.read_parquet('data/fills_sel.parquet')
H=pd.date_range('2026-05-21','2026-10-31 23:00',freq='1h'); cov=F.groupby('a').time.agg(['min','max'])
ntrial=0; rows=[]
for c in ['BTC','ETH','SOL']:
    d=pd.read_parquet(ROOT+f'/data_cache/bn_spot_5m_{c}USDT.parquet'); d.index=pd.to_datetime(d.index); o=d['open'].resample('1h').first().reindex(H).ffill()
    E={}
    for a,f in F[F.coin==c].sort_values('time').groupby('a'):
        pos=f.start+np.where(f.side=='B',f.sz,-f.sz); p=pd.Series(pos.values,index=f.time.values); p=p[~p.index.duplicated(keep='last')]
        x=p.reindex(p.index.union(H)).ffill().reindex(H); x[(H<cov.loc[a,'min'])|(H>cov.loc[a,'max'])]=np.nan
        E[a]=(x*o/S.av_T[a]).clip(-5,5)
    E=pd.DataFrame(E); top=E[[a for a in E if S.gruppo[a]=='top']]; bot=E[[a for a in E if S.gruppo[a]=='bottom']]
    sig={'top-bottom':top.mean(axis=1)-bot.mean(axis=1),'solo top':top.mean(axis=1),'contro bottom':-bot.mean(axis=1)}
    print(c,'conti con fill sulla moneta: top',top.shape[1],'bottom',bot.shape[1],'| conti coperti in media per ora: top %.1f bottom %.1f'%(top.notna().sum(axis=1).mean(),bot.notna().sum(axis=1).mean()))
    for nome,s in sig.items():
        z=(s-s.rolling(24*14).mean())/s.rolling(24*14).std()
        for kind,x in [('livello',s),('z 14g',z)]:
            for h in (4,24):
                for lag in (1,2):
                    ntrial+=1; fwd=o.shift(-(lag+h))/o.shift(-lag)-1; j=pd.concat([x,fwd],axis=1).dropna(); j.columns=['s','f']
                    k=j.iloc[::h]   # finestre non sovrapposte
                    pnl=np.sign(k.s)*k.f-6.5e-4*np.abs(np.sign(k.s).diff().fillna(1)); 
                    rows.append(dict(coin=c,segnale=nome,tipo=kind,ore=h,ritardo=lag,n=len(k),IC=k.s.corr(k.f,method='spearman'),t_IC=k.s.corr(k.f,method='spearman')*np.sqrt(len(k)),Sharpe_netto=pnl.mean()/pnl.std()*np.sqrt(8766/h),t=pnl.mean()/pnl.std()*np.sqrt(len(k))))
T=pd.DataFrame(rows); print(T.to_string()); print('\nprove:',ntrial,'| |t| > 2:',(T.t.abs()>2).sum(),'(attese per caso ~%.0f)'%(ntrial*0.05),'| t medio %.2f | Sharpe netto medio %.2f, massimo %.2f, minimo %.2f'%(T.t.mean(),T.Sharpe_netto.mean(),T.Sharpe_netto.max(),T.Sharpe_netto.min()))
print('periodo: 2026-05-21 -> 2026-10-31 (5,3 mesi, UNA sola coorte): nessuna divisione selezione/verifica possibile.')
