"""Esporta i risultati della ricerca v4 per la dashboard: research/v5/quant_v4.json. Tutto SIMULATO salvo dove indicato."""
import json, pickle, sys, warnings; warnings.filterwarnings('ignore'); sys.path.insert(0,'/home/user/GERVA-Capital'); sys.path.insert(0,'research/v5/v4')
import numpy as np, pandas as pd
def clean(o):
    if isinstance(o,dict): return {str(k):clean(v) for k,v in o.items()}
    if isinstance(o,(list,tuple)): return [clean(v) for v in o]
    if isinstance(o,(np.floating,float)): return None if (o!=o or abs(o)==np.inf) else round(float(o),5)
    if isinstance(o,(np.integer,)): return int(o)
    return o
import leva_trade_isolato as TR
ALL=pickle.load(open('research/v5/v4/_cache/trades.pkl','rb'))
stops=[]
for (s,tiers,trail,side),T in ALL.items():
    if side!='long' or tiers!=('alta',) : continue
    if isinstance(s,float) and trail is not None: continue
    v=T[T.entry>='2023-01-01']; yrs=(T.entry.max()-T.entry.min()).days/365.25; streak=mx=0
    for x in (T.sort_values('exit').R<0).values:
        streak=streak+1 if x else 0; mx=max(mx,streak)
    stops.append(dict(label=(f"{s:.1%}" if isinstance(s,float) else s.replace('atr','')+' x ATR'),stop=T.s.median(),leverage=T.L.median(),liq_distance=(1/T.L-0.005).median(),n=len(T),per_year=len(T)/yrs,
        mean_R=T.R.mean(),mean_R_verify=v.R.mean(),hit=(T.R>0).mean(),max_losing_streak=mx,cost_R=(2*0.00065/T.s).mean(),t=T.R.mean()/T.R.std()*np.sqrt(len(T)),liquidations=int((T.why=='liquidazione').sum())))
stops=sorted(stops,key=lambda d:d['stop'])
tier=pd.read_pickle('research/v5/v4/_cache/tier.pkl').reset_index().to_dict('records')
stress=[]
import io,re
txt=open('research/v5/v4/leva_trade_stress.out').read().split('moneta  leva')[1].split('\n\n')[0]
for line in txt.strip().split('\n')[1:]:
    p=line.split(); stress.append(dict(coin=p[0],leverage=int(p[1]),stop_distance=float(p[2]),liq_distance=float(p[3]),bars_stop_to_liq_per_year=float(p[4]),bars_beyond_liq_per_year=float(p[5]),p_liq_1h=float(p[6]),p_liq_4h=float(p[7]),p_liq_24h=float(p[8])))
st=pd.read_csv('research/v5/v4/fondo_statistiche.csv').to_dict('records'); mc=pd.read_csv('research/v5/v4/fondo_montecarlo.csv').to_dict('records')
F=pd.read_parquet('research/v5/v4/fondo_serie.parquet'); W=F.resample('W').apply(lambda x:(1+x).prod()-1)
curves={k:[[d.strftime('%Y-%m-%d'),round(float(v),4)] for d,v in (1+W[c]).cumprod().items()] for k,c in {'Versione precedente (4 strategie, 1x)':'old','6 strategie, 1x':'new','6 strategie, 2x':'new2x','Libro dei trade 11x':'trade11','Fondo: 2x + trade (C3)':'C3'}.items()}
C=pd.read_parquet('research/v5/v4/candidates.parquet'); rf=F.rf.reindex(C.index).fillna(0); port=F.old.reindex(C.index)
mm=lambda x:(1+x.fillna(0)).resample('ME').prod()-1
verdict={'CARRY-XS (Binance':('scartata','sotto il tasso a breve dal 2023'),'CARRY-XS-HL':('passa con riserva','in esaurimento: 19,9% nel 2024, 1,8% nel 2026'),'FUND-ARB':('scartata','non regge i costi doppi'),'PAIRS':('scartata','perde anche senza costi'),'RESID-REV':('scartata','i prezzi relativi seguono il trend'),
 'TSMOM-1H':('scartata','copia di CR-TREND'),'GEX-INTRADAY':('scartata','negativa in verifica'),'CASCATA-OI':('scartata','open interest non aggiunge nulla'),'DIP-24h':('passa di misura','verifica 0,66; 0,40 a costi doppi'),'FUNDING-BASSO':('scartata','caduta -89%'),
 'CONTRO-DETTAGLIO':('in osservazione','scelta di soli 12 mesi'),'XS top trader':('scartata',''),'SHORT-VAR BTC+ETH (STIMA, filtro':('scartata','premio sparito (stima)'),'SHORT-VAR BTC+ETH (STIMA, sempre':('scartata','premio sparito (stima)'),'STABLE-30':('scartata','correlazione 0,81 con CR-TREND'),
 'FNG-MOM':('scartata','non regge i costi doppi'),'ORE 21-23':('ipotesi','solo a commissioni maker'),'NEW-LIST':('scartata','caduta -85%; diversifica'),'XS-FUNDING':('scartata','sparita dopo il 2022')}
cands=[]
for c in C.columns:
    x=C[c].dropna(); 
    if len(x)<200: continue
    e=x-rf.reindex(x.index); s=lambda y:(y.mean()/y.std()*np.sqrt(365)) if len(y)>100 and y.std()>0 else None
    eq=(1+x).cumprod(); v=next((val for k,val in verdict.items() if c.startswith(k)),('',''))
    cands.append(dict(name=c,sharpe=s(e),sharpe_select=s(e[:'2022-12-31']),sharpe_verify=s(e['2023-01-01':]),cagr=eq.iloc[-1]**(365/len(x))-1,vol=x.std()*np.sqrt(365),maxdd=(eq/eq.cummax()-1).min(),
                      corr_portfolio=mm(x).corr(mm(port.reindex(x.index))),verdict=v[0],note=v[1],by_year={int(y):(g.mean()/g.std()*np.sqrt(365) if g.std()>0 else None) for y,g in e.groupby(e.index.year)}))
venues=[dict(venue='Hyperliquid',legal='Non autorizzata nello SEE; non bloccata',max_leverage='fino a 40x',fees='1,5 / 4,5 pb',risk='Nessuna vigilanza; 49% dello stake alla fondazione',role='Quota a perdere, dopo parere legale'),
 dict(venue='Kraken Pro (CySEC)',legal='Autorizzata MiFID',max_leverage='10x (a rischio 2x)',fees='circa 2 / 5 pb (non verificato)',risk='Gruppo USA',role='Perpetual regolamentati'),
 dict(venue='OKX Europe (MFSA)',legal='Autorizzata MiFID',max_leverage='10x (a rischio 2x)',fees='2 / 5 pb',risk='Struttura a 5 anni non confermata dai regolatori',role='Alternativa a Kraken'),
 dict(venue='Coinbase UE',legal='Autorizzata; Italia non confermata',max_leverage='10x',fees='non verificato',risk='Societa quotata USA',role='Riserva'),
 dict(venue='Binance',legal='Chiusa ai residenti SEE dal 1/7/2026',max_leverage='0',fees='-',risk='-',role='Esclusa'),
 dict(venue='Bybit EU',legal='Solo spot e margine',max_leverage='0 sui perpetual',fees='-',risk='Furto di 1,5 mld $ nel 2025',role='Esclusa'),
 dict(venue='Interactive Brokers Ireland',legal='Autorizzata',max_leverage='CFD 30/20/10/5/2; futures a margine di borsa',fees='variabili',risk='Broker quotato',role='Azioni, ETF, indici, cassa')]
out=dict(generated=str(pd.Timestamp.now(tz='UTC')),simulated=True,trials=812,deflated_sharpe=dict(old=0.20,new=0.38,threshold=0.95),
 stop_table=stops,tier_mc=tier,stress=stress,fund_stats=st,fund_mc=mc,fund_curves=curves,candidates=cands,venues=venues,
 decomposition=dict(avg_sleeve_sharpe=0.80,portfolio_sharpe=1.34,avg_sleeve_sharpe_verify=0.50,portfolio_sharpe_verify=0.98,cagr_1x=0.136,cagr_2x=0.231,cagr_fund=0.529,ai_contribution=None,
                    note="Il contributo dell'AI non e' misurabile sui dati storici: vale zero finche' il confronto tra i due libri paper non dice altro."),
 recommended=dict(prudent='C1. 1x + trade 11x (0,5%/1%)',maximum='C3. 2x + trade 11x (1%/2%)'))
json.dump(clean(out),open('research/v5/quant_v4.json','w'),ensure_ascii=False); import os; print(os.path.getsize('research/v5/quant_v4.json'),len(cands),len(stops))
