"""HLP: ricostruzione dei rendimenti da vaultDetails.portfolio.allTime (punti ogni 7-14 giorni: e' tutto cio' che l'API espone)."""
import json, numpy as np, pandas as pd
from comune import *
pd.set_option('display.width',250); pd.set_option('display.float_format',lambda x:f'{x:.4f}')
h=json.load(open('data/hlp_vaultDetails.json')); P=dict(h['portfolio'])
df=serie({'all':P['allTime']}); r=rendimenti(df)
print('punti',len(df),df.index[0],df.index[-1],'passo mediano giorni',pd.Series(df.index).diff().dt.days.median())
print('TVL oggi %.1fM  PnL cumulato %.1fM  apr dichiarato %.3f'%(df.av.iloc[-1]/1e6,df.pnl.iloc[-1]/1e6,h['apr']))
# griglia regolare: da 2023-06 passo 14 giorni
r=r[r.index>='2023-06-01']; dt=pd.Series(r.index).diff().dt.total_seconds().median()/86400; ppy=365.25/dt
# serie giornaliera di calendario: rendimento dell'intervallo spalmato geometricamente (INTERPOLATA: la volatilita' giornaliera non e' osservata)
t0=df.index[df.index.get_loc(r.index[0])-1]; ends=[t0]+list(r.index); rows={}
for a,b,x in zip(ends[:-1],ends[1:],r.values):
    days=pd.date_range(a.normalize()+pd.Timedelta(days=1),b.normalize()); 
    if len(days)==0: continue
    for d in days: rows[d]=(1+x)**(1/len(days))-1
daily=pd.Series(rows).sort_index(); daily=daily[~daily.index.duplicated()]
tb=tbill().reindex(daily.index).ffill(); F=fondo()
def blocco(lab,mask):
    x=r[mask]; d=daily[(daily.index>=x.index[0]-pd.Timedelta(days=14))&(daily.index<=x.index[-1])]
    s=stat(x,ppy); ex=d-tb.reindex(d.index); m=((1+d).resample('ME').prod()-1); mex=((1+ex).resample('ME').prod()-1)
    print(f"{lab:14s} n={s['n']:3d} CAGR={s['cagr']:.3f} vol(14g)={s['vol']:.3f} Sharpe(14g, lordo rf)={s['sharpe']:.2f} "
          f"Sharpe mensile ecc.T-bill={mex.mean()/mex.std()*np.sqrt(12):.2f} maxDD={s['maxdd']:.3f} peggior 14g={s['worst']:.3f} mese medio={m.mean():.4f} mese mediano={m.median():.4f} mese peggiore={m.min():.4f} mesi<0={int((m<0).sum())}/{len(m)}")
print('\n== HLP, rendimenti per intervallo di ~14 giorni =='); blocco('tutto',r.index>='2023-06-01'); blocco('2023',r.index.year==2023); blocco('2024',r.index.year==2024); blocco('2025',r.index.year==2025); blocco('2026',r.index.year==2026)
blocco('ultimi 24 mesi',r.index>=r.index[-1]-pd.Timedelta(days=730)); blocco('ultimi 12 mesi',r.index>=r.index[-1]-pd.Timedelta(days=365))
print('\nNB: la convenzione selezione<=2022 non e\' applicabile: HLP nasce a maggio 2023. Non c\'e\' nessun parametro scelto: e\' la storia di un deposito.')
# tabella intervalli: TVL, PnL, rendimento
T=pd.DataFrame({'tvl_M':df.av/1e6,'dPnL_M':df.pnl.diff()/1e6,'r':r}).dropna(); 
print('\n== i 8 intervalli peggiori e i 5 migliori =='); print(T.sort_values('r').head(8).to_string()); print(T.sort_values('r').tail(5).to_string())
print('\n== intervalli che contengono gli eventi ==')
for nome,d in [('JELLY 2025-03-26','2025-03-26'),('10 ottobre 2025','2025-10-10'),('POPCAT 2025-11-12','2025-11-12')]:
    i=T.index.searchsorted(pd.Timestamp(d)); print(nome); print(T.iloc[max(i-1,0):i+2].to_string())
L=json.load(open('data/stats/hlp_liquidator_pnl.json'))['chart_data']; L=pd.Series({pd.Timestamp(x['time']):x['total_pnl'] for x in L}).dropna()
print('\nPnL giornaliero del liquidatore HLP (stats, solo 2025-03..07): 5 giorni peggiori (USD)'); print(L.sort_values().head(5).to_string())
# per anno
print('\n== per anno (composto sugli intervalli) =='); print(((1+r).groupby(r.index.year).prod()-1).to_string())
print('rendimento per anno / TVL medio (M):'); print((df.av.groupby(df.index.year).mean()/1e6).to_string())
# quanto la campionatura a 14 giorni nasconde: ultimo mese (punti ~15h)
m=serie({'all':P['month']}); rm=rendimenti(m); hrs=pd.Series(m.index).diff().dt.total_seconds().median()/3600
eqm=(1+rm).cumprod(); print(f"\nultimo mese ad alta frequenza: passo {hrs:.1f}h, n={len(rm)}, vol annua={rm.std()*np.sqrt(8766/hrs):.3f}, DD massimo intra-mese={(eqm/eqm.cummax()-1).min():.4f}, rendimento={eqm.iloc[-1]-1:.4f}, TVL da {m.av.iloc[0]/1e6:.0f}M a {m.av.iloc[-1]/1e6:.0f}M")
# autocorrelazione e correlazioni
print('autocorrelazione lag1 dei rendimenti a 14g: %.2f'%r.autocorr(1))
def agg(s,idx):  # rendimento composto sugli stessi intervalli
    c=(1+s.fillna(0)).cumprod(); c=c.reindex(pd.date_range(c.index[0],c.index[-1])).ffill(); v=c.reindex(idx.normalize(),method='ffill'); return pd.Series(v.values,index=idx).pct_change()
print('\n== correlazione con il fondo (stessi intervalli di 14 giorni | mensile) ==')
rr=r[r.index<=F.index[-1]+pd.Timedelta(days=1)]
mh=(1+daily).resample('ME').prod()-1
for c in F.columns:
    a=agg(F[c],rr.index); mf=(1+F[c]).resample('ME').prod()-1; j=pd.concat([mh,mf],axis=1).dropna().iloc[1:-1]
    print(f"{c:28s} corr14g={rr.corr(a):+.2f} (n={rr.notna().sum()})  corr mensile={j.corr().iloc[0,1]:+.2f} (n={len(j)})")
# BTC: beta di HLP
btc=pd.read_parquet(ROOT+'/data_cache/yahoo_1d_BTC-USD.parquet')['close'] if __import__('os').path.exists(ROOT+'/data_cache/yahoo_1d_BTC-USD.parquet') else None
if btc is not None:
    btc.index=pd.to_datetime(btc.index); b=btc.reindex(pd.date_range(btc.index[0],btc.index[-1])).ffill(); v=b.reindex(r.index.normalize(),method='ffill'); rb=pd.Series(v.values,index=r.index).pct_change()
    print(f"corr HLP-BTC 14g={r.corr(rb):+.2f}  corr HLP-|BTC|={r.corr(rb.abs()):+.2f}  beta={r.cov(rb)/rb.var():+.3f}")
    j=pd.concat([r,rb],axis=1).dropna(); j.columns=['hlp','btc']; print('HLP medio 14g quando BTC<-10%%: %.4f (n=%d); BTC>+10%%: %.4f (n=%d); resto: %.4f'%(j.hlp[j.btc<-.1].mean(),(j.btc<-.1).sum(),j.hlp[j.btc>.1].mean(),(j.btc>.1).sum(),j.hlp[j.btc.abs()<=.1].mean()))
# esposizione netta giornaliera di HLP (stats)
hp=pd.DataFrame(json.load(open('data/stats/hlp_positions.json'))['chart_data']); hp['time']=pd.to_datetime(hp.time)
net=hp.groupby('time').daily_ntl.sum(); gross=hp.groupby('time').daily_ntl_abs.sum(); tv=df.av.reindex(net.index,method='ffill')
print('\nesposizione HLP / TVL (stats hlp_positions, 2023-06..2026-04): netta mediana %.2f, 5%%-95%% [%.2f, %.2f]; lorda mediana %.2f, 95%% %.2f'%((net/tv).median(),(net/tv).quantile(.05),(net/tv).quantile(.95),(gross/tv).median(),(gross/tv).quantile(.95)))
# lock-up dai follower
fo=pd.DataFrame(h['followers']); print('\nfollower elencati (top 100):',len(fo),'equity mediana',fo.vaultEquity.astype(float).median())
pd.DataFrame({'HLP':daily}).to_parquet('returns_hlp.parquet'); r.to_frame('r').to_parquet('hlp_intervalli.parquet')
print('salvato returns_hlp.parquet',daily.index[0],daily.index[-1],len(daily))
