"""Controllo aggiuntivo: i dex 'HIP-3' di Hyperliquid (mercati creati da terzi) coprono le quotazioni Binance mancanti? Solo per nome + prima candela 1d."""
import hl, json, time, pandas as pd, re
HERE='/home/user/GERVA-Capital/research/v5/v5/validazione/'; now=int(time.time()*1000)
T=pd.read_parquet(HERE+'c2_trades_binance.parquet'); T=T[T.t0>='2023-06-01']
P=pd.read_parquet(HERE+'c2_trades_hl.parquet'); print('controllo funding: numero medio di ore di funding HL per trade %.0f ; quota di trade con 0 record %.2f'%(P.nf.mean(),(P.nf==0).mean()))
print('funding HL per trade, quantili %:',(P.fund*100).quantile([.05,.25,.5,.75,.95]).round(3).to_dict(),' Binance:',(P.fund_bn*100).quantile([.05,.25,.5,.75,.95]).round(3).to_dict())
dex=[d['name'] for d in hl.post({'type':'perpDexs'}) if d]; names={}
for d in dex:
    try:
        for x in hl.post({'type':'meta','dex':d})['universe']: names[x['name'].split(':')[-1].upper()]=x['name']
    except Exception as e: print('FAIL',d,e)
print('dex HIP-3:',dex,' mercati:',len(names))
base=T.sym.str[:-4]; hit=T[base.isin(names)]; print('quotazioni Binance dal 2023-06 con un mercato HIP-3 omonimo: %d su %d'%(len(hit),len(T)))
rows=[]
for _,r in hit.iterrows():
    try:
        c=hl.post({'type':'candleSnapshot','req':{'coin':names[r.sym[:-4]],'interval':'1d','startTime':0,'endTime':now}})
        if c: rows.append((r.sym,names[r.sym[:-4]],r.t0,pd.Timestamp(c[0]['t'],unit='ms'),sum(float(x['v'])*float(x['c']) for x in c[:8])/min(len(c),8)))
    except Exception as e: pass
X=pd.DataFrame(rows,columns=['sym','hl','bn_t0','hl_day0','usd_vol_giorno']); X['lag_g']=(X.hl_day0-X.bn_t0.dt.normalize()).dt.days
print('  con HIP-3 gia\' aperto entro il giorno dopo la quotazione Binance: %d ; volume medio giornaliero mediano dei primi 8 giorni: %.0f USD'%((X.lag_g<=1).sum(),X.usd_vol_giorno.median()))
print(X.sort_values('bn_t0').to_string())
