"""Vault pubblici: i 20 piu' grandi OGGI con >=12 mesi di storia (lista viziata da sopravvivenza) contro
i 20 piu' grandi a una data passata, seguiti in avanti comprese le chiusure (lista punto-nel-tempo)."""
import json, numpy as np, pandas as pd
from comune import *
pd.set_option('display.width',250); pd.set_option('display.float_format',lambda x:f'{x:.3f}'); pd.set_option('display.max_colwidth',34)
HLPFAM={'0xdfc24b077bc1425ad1dea75bcb6f8158e10df303'}
meta={x['summary']['vaultAddress']:x['summary'] for x in json.load(open('data/vaults_2026-11-11.json'))}
V={}
for l in open('data/vaults.jsonl'):
    d=json.loads(l)
    if d.get('err'): continue
    s=serie(d)
    if s is None or len(s)<3: continue
    d['s']=s; d['r']=rendimenti(s); d['created']=pd.to_datetime(meta[d['a']]['createTimeMillis'],unit='ms'); d['tvl']=float(meta[d['a']]['tvl']); d['rel']=meta[d['a']]['relationship']['type']; V[d['a']]=d
print('vault scaricati con storia:',len(V),'| chiusi:',sum(v['closed'] for v in V.values()),'| in elenco totale:',len(meta),'chiusi',sum(m['isClosed'] for m in meta.values()))
NOW=pd.Timestamp('2026-11-11'); tb=tbill()
def riga(v,a=None,b=None,net=True):
    r=v['r'].dropna(); 
    if a is not None: r=r[(r.index>a)&(r.index<=b)]
    if len(r)<3: return None
    dt=max((r.index[-1]-r.index[0]).days/max(len(r)-1,1),1); ppy=365.25/dt; s=stat(r,ppy)
    eq=(1+r).cumprod(); tot=eq.iloc[-1]-1; yrs=max((r.index[-1]-r.index[0]).days+dt,1)/365.25
    c=v.get('comm') or 0.0; totn=tot-c*max(tot,0)       # commissione del gestore sui profitti (stima: sul guadagno finale)
    return dict(nome=v['name'][:32],creato=v['created'].date(),chiuso=v['closed'],tvlM=v['tvl']/1e6,anni=yrs,tot_lordo=tot,tot_netto=totn,cagr_netto=(1+totn)**(1/yrs)-1 if totn>-1 else -1,vol=s['vol'],sharpe=s['sharpe'],maxdd=s['maxdd'],comm=c)
# (a) top 20 oggi
c=[v for v in V.values() if v['rel']=='normal' and not v['closed'] and v['created']<NOW-pd.Timedelta(days=365)]
c=sorted(c,key=lambda v:-v['tvl'])[:20]; A=pd.DataFrame([riga(v) for v in c]).dropna(subset=['nome'])
print('\n== (a) i 20 vault utente piu\' grandi OGGI con >=12 mesi (SOPRAVVISSUTI: lista scelta guardando il presente) =='); print(A.to_string())
print('mediana: CAGR netto %.3f Sharpe %.2f maxDD %.3f | media CAGR netto %.3f | quota con CAGR netto > T-bill 4%%: %.2f'%(A.cagr_netto.median(),A.sharpe.median(),A.maxdd.median(),A.cagr_netto.mean(),(A.cagr_netto>.04).mean()))
# (b) coorti punto-nel-tempo
def tvl_a(v,T):
    s=v['s'].av[:T]; 
    if len(s)==0 or (T-s.index[-1]).days>21: return 0.0   # nessun punto recente: vault fermo o chiuso
    return s.iloc[-1]
def coorte(T,k=20,mesi=12,minage=0):
    E=T+pd.DateOffset(months=mesi); out=[]
    cand=[(tvl_a(v,T),v) for v in V.values() if v['rel']=='normal' and v['created']<=T-pd.Timedelta(days=minage)]
    cand=sorted([x for x in cand if x[0]>0],key=lambda x:-x[0])[:k]
    for tv,v in cand:
        r=v['r'].dropna(); r=r[(r.index>T)&(r.index<=E)]; tot=(1+r).prod()-1 if len(r) else 0.0
        eq=(1+r).cumprod(); dd=(eq/eq.cummax()-1).min() if len(r) else 0.0; dd=min(dd,eq.min()-1 if len(r) else 0)
        cm=v.get('comm') or 0.0; last=v['s'].index[-1]; pp=v['s'].pnl; pp=pp[(pp.index>=T-pd.Timedelta(days=1))&(pp.index<=E)]; usd=(pp.iloc[-1]-v['s'].pnl[:T].iloc[-1]) if len(pp) else 0.0
        out.append(dict(nome=v['name'][:32],usd_M=usd/1e6,tvl_T_M=tv/1e6,tot_lordo=tot,tot_netto=tot-cm*max(tot,0),maxdd=dd,chiuso_oggi=v['closed'],finito_prima=bool(last<E-pd.Timedelta(days=21)),tvl_oggi_M=v['tvl']/1e6))
    return pd.DataFrame(out)
print('\n== (b) i 20 vault utente piu\' grandi ALLA DATA T, seguiti 12 mesi (chiusi compresi) ==')
rows=[]
for T in ['2024-06-30','2024-09-30','2024-12-31','2025-03-31','2025-06-30','2025-09-30','2025-11-11']:
    T=pd.Timestamp(T); C=coorte(T); w=C.tvl_T_M/C.tvl_T_M.sum()
    hl=V['0xdfc24b077bc1425ad1dea75bcb6f8158e10df303']['r']; hl=(1+hl[(hl.index>T)&(hl.index<=T+pd.DateOffset(months=12))]).prod()-1
    t=tb[(tb.index>T)&(tb.index<=T+pd.DateOffset(months=12))].sum()
    rows.append(dict(T=T.date(),n=len(C),media_netto=C.tot_netto.mean(),mediana_netto=C.tot_netto.median(),pesata_tvl=(w*C.tot_netto).sum(),perdenti=(C.tot_netto<0).mean(),usd_su_tvlT=C.usd_M.sum()/C.tvl_T_M.sum(),sotto_meno30=(C.tot_netto<-.3).mean(),chiusi_oggi=C.chiuso_oggi.mean(),maxdd_mediano=C.maxdd.median(),HLP=hl,Tbill=t))
    if str(T.date()) in('2024-12-31','2025-11-11'): print(f'-- coorte {T.date()} --'); print(C.to_string())
R=pd.DataFrame(rows); print(R.to_string())
print('\nNB: coorti sovrapposte (finestre di 12 mesi a passo di 3): circa 2,3 osservazioni indipendenti. Vault con PnL storico < 3k USD e TVL odierno < 30k non scaricati.')
# (c) tutti i vault nati entro T con TVL >= 100k a T
print('\n== (c) TUTTI i vault utente con TVL >= 100k USD alla data T, 12 mesi dopo ==')
for T in ['2024-12-31','2025-06-30','2025-11-11']:
    T=pd.Timestamp(T); C=coorte(T,k=10**6); C=C[C.tvl_T_M>=0.1]
    print(f"{T.date()} n={len(C)} media netto={C.tot_netto.mean():+.3f} mediana={C.tot_netto.median():+.3f} quota<0={ (C.tot_netto<0).mean():.2f} quota<-30%={(C.tot_netto<-.3).mean():.2f} quota>+30%={(C.tot_netto>.3).mean():.2f} chiusi oggi={C.chiuso_oggi.mean():.2f} finiti entro 12m={C.finito_prima.mean():.2f}")
json.dump({a:dict(name=v['name'],closed=v['closed']) for a,v in V.items()},open('data/vault_meta.json','w'))
