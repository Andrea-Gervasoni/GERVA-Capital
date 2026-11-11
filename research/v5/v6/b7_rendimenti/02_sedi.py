"""B7.2 - funding e base per sede (FATTO: serie pubbliche delle sedi). Annualizzato semplice, lordo costi, incassato dallo short."""
import pandas as pd, numpy as np, os
C='/home/user/GERVA-Capital/data_cache/'; D=C+'v6_b7/'
pd.set_option('display.width',220)
def yr(s,per): # s: funding per periodo; ritorna % annuo per anno solare + ultimi 90/30 giorni
    s=s.dropna(); a=s.groupby(s.index.year).mean()*per*100; a['ult90g']=s[s.index>=s.index[-1]-pd.Timedelta(days=90)].mean()*per*100; a['ult30g']=s[s.index>=s.index[-1]-pd.Timedelta(days=30)].mean()*per*100
    a['%ore>0']=(s>0).mean()*100; a.index=a.index.map(str); return a
T={}
for c in ['BTC','ETH','SOL']:
    T['Binance '+c]=yr(pd.read_parquet(C+f'bn_fund_{c}USDT.parquet').iloc[:,0],3*365)
    T['Hyperliquid '+c]=yr(pd.read_parquet(C+f'v4_hl_fund_{c}.parquet').fundingRate,24*365)
for c,i in (('BTC','BTC-PERPETUAL'),('ETH','ETH-PERPETUAL'),('SOL','SOL_USDC-PERPETUAL'),('BTC(usdc)','BTC_USDC-PERPETUAL')):
    if os.path.exists(D+f'deribit_fund_{i}.parquet'): T['Deribit '+c]=yr(pd.read_parquet(D+f'deribit_fund_{i}.parquet').f,24*365)
kr=pd.read_parquet(D+'kraken_fund.parquet'); ok=pd.read_parquet(D+'okx_fund.parquet')
for c,s in (('BTC','PF_XBTUSD'),('ETH','PF_ETHUSD'),('SOL','PF_SOLUSD')): T['Kraken Fut '+c]=yr(kr[s],24*365)
for c in ['BTC','ETH','SOL']:
    s=ok[c].dropna(); per=365*24/((s.index[-1]-s.index[0]).total_seconds()/3600/len(s)); T['OKX '+c]=yr(s,per)
print('Funding annuo %, per anno solare (short incassa). Profondita\' storica pubblica: Kraken Futures',kr.index[0].date(),'| OKX',ok.index[0].date(),'| Deribit 2019 | Hyperliquid 2023-05')
print(pd.DataFrame(T).T.round(2).to_string())
# stesso periodo comune (ultimi 90 giorni e ultimo anno), tutte le sedi
print('\n--- Kraken Futures: 25 perps piu\' scambiati, funding annuo % ultimo anno / ultimi 90 g / quota ore positive')
vol=pd.read_parquet(D+'kraken_vol.parquet').vol; a=pd.DataFrame({'vol24h_M$':vol/1e6,'anno':kr.mean()*8760*100,'ult90':kr[kr.index>=kr.index[-1]-pd.Timedelta(days=90)].mean()*8760*100,'pos%':(kr>0).mean()*100,'n_ore':kr.notna().sum()}).dropna().sort_values('vol24h_M$',ascending=False)
print(a.head(25).round(1).to_string())
print('\n--- OKX: funding annuo % sugli ultimi ~90 giorni (tutta la storia pubblica)')
per=pd.Series({c:365*24/((ok[c].dropna().index[-1]-ok[c].dropna().index[0]).total_seconds()/3600/ok[c].notna().sum()) for c in ok})
print((ok.mean()*per*100).round(2).to_dict())
# persistenza: autocorrelazione del funding medio a 7 giorni con i 7 successivi; e con i 30 successivi
print('\n--- persistenza: corr(funding medio 30g passati, 30g successivi), campioni non sovrapposti')
def pers(s,per_day):
    d=s.resample('1D').sum(); m=d.resample('30D').mean(); return m.corr(m.shift(1)),len(m)
for nm,s in (('Binance BTC',pd.read_parquet(C+'bn_fund_BTCUSDT.parquet').iloc[:,0]),('Deribit BTC',pd.read_parquet(D+'deribit_fund_BTC-PERPETUAL.parquet').f),('Hyperliquid BTC',pd.read_parquet(C+'v4_hl_fund_BTC.parquet').fundingRate),('Hyperliquid SOL',pd.read_parquet(C+'v4_hl_fund_SOL.parquet').fundingRate)):
    print(f'  {nm:18s} corr {pers(s,1)[0]:+.2f} (n mesi {pers(s,1)[1]})')
# ---- futures datati Deribit: base annualizzata del trimestrale con 30-120 giorni a scadenza
print('\n--- Deribit futures trimestrali: base annualizzata % (future/indice-1)*365/giorni, contratto con 30-120 g a scadenza; per anno')
for cur in ['BTC','ETH']:
    p=D+f'deribit_fut_{cur}.parquet'
    if not os.path.exists(p): print('manca',cur); continue
    fu=pd.read_parquet(p); fu.index=fu.index.normalize(); idx=pd.read_parquet(D+f'deribit_fund_{cur}-PERPETUAL.parquet').idx.resample('1D').last()
    rows={}
    for nm in fu:
        exp=pd.to_datetime(nm.split('-')[1],format='%d%b%y')+pd.Timedelta(hours=8); s=fu[nm].dropna()
        for t,v in s.items():
            dte=(exp-t).days
            if 30<=dte<=120 and t in idx.index and idx[t]>0: rows.setdefault(t,[]).append(((v/idx[t]-1)*365/dte,dte))
    b=pd.Series({t:min(v,key=lambda x:x[1])[0] for t,v in rows.items()}).sort_index()
    a=b.groupby(b.index.year).mean()*100; a.index=a.index.map(str); a['ult90g']=b[b.index>=b.index[-1]-pd.Timedelta(days=90)].mean()*100; a['%giorni>0']=(b>0).mean()*100
    print(cur,a.round(2).to_dict()); b.to_frame('basis').to_parquet(D+f'deribit_basis_{cur}.parquet')
# ---- CME: BTC=F (front month continuo Yahoo) contro spot
f=pd.read_parquet(C+'v5_b6_yahoo_1d_BTC=F.parquet').close; s=pd.read_parquet(C+'v5_b6_yahoo_1d_BTC-USD.parquet').close
x=pd.concat([f,s],axis=1,keys=['f','s']).dropna()
# scadenza: ultimo venerdi' del mese; giorni alla scadenza del front
def dte(t):
    e=t+pd.offsets.MonthEnd(0)
    while e.weekday()!=4: e-=pd.Timedelta(days=1)
    if e<t:
        e=t+pd.offsets.MonthEnd(1)
        while e.weekday()!=4: e-=pd.Timedelta(days=1)
    return (e-t).days
x['dte']=[dte(t) for t in x.index]; x=x[x.dte>=7]; x['b']=(x.f/x.s-1)*365/x.dte
a=x.b.groupby(x.index.year).median()*100; a.index=a.index.map(str); a['ult90g']=x.b[x.index>=x.index[-1]-pd.Timedelta(days=90)].median()*100
print('\n--- CME BTC front month (Yahoo BTC=F) contro BTC-USD: base annualizzata mediana % (STIMA: chiusure non sincrone 16:00 CT vs 00:00 UTC, rumore alto)'); print(a.round(2).to_dict())
