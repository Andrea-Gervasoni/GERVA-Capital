"""Quante 'nuove quotazioni' Binance 2025-26 sono perp su azioni/ETF/materie prime (non monete nuove)? Proxy: omonimo su un dex HIP-3 di
Hyperliquid (mercati tradfi) oppure volatilita' oraria delle prime 24h molto bassa. E funding HL solo dove i record esistono."""
import pandas as pd, numpy as np, re
HERE='/home/user/GERVA-Capital/research/v5/v5/validazione/'
T=pd.read_parquet(HERE+'c2_trades_binance.parquet'); D=pd.read_parquet('/home/user/GERVA-Capital/data_cache/v5_a6_listing_1h.parquet')
X=[l.split() for l in open(HERE+'c2_hl_hip3.out') if re.match(r'^\d+\s+\w+USDT\s',l)]; h3={x[1]:x[2] for x in X}
crypto_dex=('hyna',)   # hyna quota monete; gli altri azioni/ETF/materie prime/pre-IPO
T['tradfi']=T.sym.map(lambda s: s in h3 and not h3[s].startswith(crypto_dex))
sg=D.sort_values('t').groupby('sym').apply(lambda d: np.log(d.close.iloc[:24]).diff().std()); T['s24']=T.sym.map(sg)
def st(x,lab):
    w=x.groupby(x.entry.dt.floor('7D')).R.sum(); print(f'{lab:60s} n {len(x):3d} R {x.R.mean():+.3f} t_sett {w.mean()/w.std()*np.sqrt(len(w)):+.2f} stop {(x.why=="stop").mean():.0%} sigma1h mediana {x.s24.median():.4f}')
print('perp tradfi (omonimo HIP-3 non-cripto) per anno:',T[T.tradfi].groupby(T.entry.dt.year).size().to_dict(),' su',T.groupby(T.entry.dt.year).size().to_dict())
st(T[T.tradfi],'perp su azioni/ETF/materie prime'); st(T[~T.tradfi],'il resto (tutto il periodo)'); V=T[T.entry>='2023']
st(V[~V.tradfi],'verifica senza tradfi'); st(V,'verifica (tutti)'); 
for y in (2025,2026): st(T[(T.entry.dt.year==y)&~T.tradfi],f'{y} senza tradfi'); 
low=T.s24<0.004; print('sigma oraria prime 24h < 0.4%% (non si comporta da moneta nuova): %d, di cui tradfi %d'%(low.sum(),(low&T.tradfi).sum())); st(T[low],'sigma bassa'); st(V[~(V.s24<0.004)],'verifica senza sigma bassa')
P=pd.read_parquet(HERE+'c2_trades_hl.parquet'); q=P[P.nf>0]
print('\nfunding HL dove esistono record (n %d, %.0f ore medie): media %+.3f%% = %+.3f R ; Binance stessi trade %+.3f%% = %+.3f R'%(len(q),q.nf.mean(),q.fund.mean()*100,q.fund.mean()/0.15,q.fund_bn.mean()*100,q.fund_bn.mean()/0.15))
print('R HL su quei trade %+.3f ; R Binance %+.3f'%(q.R.mean(),q.R_bn.mean()))
