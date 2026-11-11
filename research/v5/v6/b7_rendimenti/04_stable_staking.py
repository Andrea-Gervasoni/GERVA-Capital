"""B7.3/4 - rendimenti realizzati (DefiLlama yields, APY giornaliero dichiarato dal protocollo) di staking liquido e stablecoin; prezzi e depeg
(DefiLlama coins / Binance USDCUSDT 1h). FATTO = serie pubbliche; i rendimenti sono APY lordi, prima di gas, tasse e costi di conversione."""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings('ignore')
C='/home/user/GERVA-Capital/data_cache/'; D=C+'v6_b7/'; pd.set_option('display.width',250)
y=pd.read_parquet(D+'llama_yields.parquet'); Y=y[[c for c in y if not c.endswith('_tvl')]]; P=pd.read_parquet(D+'llama_px.parquet')
irx=pd.read_parquet(C+'yahoo_1d_^IRX.parquet').close
a=Y.groupby(Y.index.year).mean().T; a['ult90g']=Y[Y.index>=Y.index[-1]-pd.Timedelta(days=90)].mean(); a['oggi']=Y.ffill().iloc[-1]; a['dal']=[str(Y[c].first_valid_index().date()) for c in Y]; a['tvl_M$']=[y[c+'_tvl'].dropna().iloc[-1]/1e6 for c in Y]
a.loc['T-bill 3m USD (^IRX)']=list(irx.groupby(irx.index.year).mean().reindex([2022,2023,2024,2025,2026]))+[irx.iloc[-90:].mean(),irx.iloc[-1],'',np.nan]
print('APY medio % per anno'); print(a.round(2).to_string())
print('\n--- quota dei giorni in cui il rendimento supera il T-bill 3m, dal 2023 e nel 2026')
for c in ['aave_usdc','comp_usdc','susde','susds','fluid_usdc','lido_steth']:
    x=pd.concat([Y[c],irx],axis=1).ffill().dropna(); x=x[x.index>=Y[c].first_valid_index()]; d=x.iloc[:,0]-x.iloc[:,1]
    print(f'  {c:12s} eccesso medio {d.mean():+.2f} pt ; giorni sopra {(d>0).mean():.0%} ; 2026: eccesso {d[d.index.year==2026].mean():+.2f} pt, sopra {(d[d.index.year==2026]>0).mean():.0%}')
print('\n--- depeg e drawdown di prezzo (chiusure giornaliere DefiLlama; il minimo infragiornaliero e\' piu\' basso)')
def dd(s,lab,ref=None):
    s=s.dropna(); r=s/ref.reindex(s.index) if ref is not None else s; r=r.dropna(); m=r.idxmin(); rr=r/r.cummax()-1 if ref is None and r.iloc[-1]>1.02 else r/r.rolling(60,min_periods=1).median()-1
    print(f'  {lab:22s} minimo {r.min():.4f} il {m.date()} ; peggior scarto dalla mediana a 60g {rr.min()*100:+.2f}% il {rr.idxmin().date()} ; giorni sotto -1%: {(rr<-0.01).sum()} ; ultimo {r.iloc[-1]:.4f}')
    return r
st=dd(P['staked-ether'],'stETH/ETH',P['ethereum']); dd(P['msol'],'mSOL/SOL (cresce)',P['solana']); dd(P['jito-staked-sol'],'JitoSOL/SOL (cresce)',P['solana'])
dd(P['usd-coin'],'USDC/USD'); dd(P['tether'],'USDT/USD'); dd(P['dai'],'DAI/USD'); dd(P['ethena-usde'],'USDe/USD'); dd(P['terrausd'][:'2022-06-30'],'UST/USD (2022)')
sm=st.rolling(3,center=True,min_periods=1).median(); print('  stETH/ETH filtrato (mediana a 3 giorni: i minimi grezzi 0.78/0.85/0.87 sono chiusure non sincrone nei giorni di crollo): minimo per anno',sm.groupby(sm.index.year).min().round(4).to_dict(),'; minimo assoluto',round(sm.min(),4),'il',sm.idxmin().date())
ok=pd.read_parquet(D+'okx_steth_eth_1d.parquet'); print('  stETH/ETH coppia diretta OKX (dal 2023-07), minimo infragiornaliero per anno:',ok.l.groupby(ok.index.year).min().to_dict(),'; minimo di chiusura:',ok.c.groupby(ok.index.year).min().to_dict())
print('  stETH/ETH grezzo per anno, minimo:',st.groupby(st.index.year).min().round(4).to_dict())
print('  stETH/ETH giugno 2022: giorni sotto 0.97 =',(sm['2022-05-01':'2022-12-31']<0.97).sum(),'; rientro sopra 0.99 il',sm['2022-06-18':][sm['2022-06-18':]>0.99].index[0].date())
u=pd.read_parquet(C+'v5_a6_spot_1h_USDCUSDT.parquet'); x=u['2023-03-09':'2023-03-15']
print('  USDC/USDT orario (Binance) marzo 2023: minimo',x.low.min(),'il',x.low.idxmin(),'; ore sotto 0.97:',(x.close<0.97).sum(),'; ore sotto 0.99:',(x.close<0.99).sum())
x=u['2025-10-10':'2025-10-12']; print('  USDC/USDT 10-11 ottobre 2025: min',x.low.min(),'max',x.high.max())
e=P['ethena-usde']; print('  USDe min giornaliero per anno:',e.groupby(e.index.year).min().round(4).to_dict())
# ---- staking coperto: stETH lungo + short ETH perp (funding Hyperliquid / Deribit)
print('\n--- staking coperto, % annuo lordo costi per anno: rendimento staking + funding dello short (per unita\' di nozionale)')
hl=lambda c: pd.read_parquet(C+f'v4_hl_fund_{c}.parquet').fundingRate.resample('1D').sum()
de=lambda i: pd.read_parquet(D+f'deribit_fund_{i}.parquet').f.resample('1D').sum()
T={}
for lab,yy,f in (('stETH + short ETH Hyperliquid',Y.lido_steth,hl('ETH')),('stETH + short ETH Deribit',Y.lido_steth,de('ETH-PERPETUAL')),('JitoSOL + short SOL Hyperliquid',Y.jitosol,hl('SOL')),('JitoSOL + short SOL Deribit',Y.jitosol,de('SOL_USDC-PERPETUAL'))):
    x=pd.concat([yy/100/365,f],axis=1,keys=['stk','fund']).dropna(); tot=x.sum(axis=1)
    g=lambda s: pd.concat([s.groupby(s.index.year).mean().rename(str)*36500,pd.Series({'ult90g':s.iloc[-90:].mean()*36500})])
    T[lab+' | staking']=g(x.stk); T[lab+' | funding']=g(x.fund); T[lab+' | TOTALE']=g(tot)
    tot.to_frame('r').to_parquet(D+'stk_'+lab.split()[0]+'_'+lab.split()[-1]+'.parquet')
print(pd.DataFrame(T).T.round(2).to_string())
