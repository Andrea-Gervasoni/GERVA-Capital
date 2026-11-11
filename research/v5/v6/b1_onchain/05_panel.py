"""Pannello punto-nel-tempo: PnL cumulato e valore del conto di ogni indirizzo su griglia comune di 14 giorni
(giovedi' 00:30 UTC, ancorata al 2025-01-02 ~ fine 2024). Valore in griglia = ultimo punto noto <= data (mai dati futuri)."""
import json, numpy as np, pandas as pd, os
from comune import *
G=pd.date_range('2023-06-01 00:30','2026-11-12 00:30',freq='14D'); off=(pd.Timestamp('2025-01-02 00:30')-G[0]).days%14; G=G+pd.Timedelta(days=off); G=G[G<=pd.Timestamp('2026-11-12')]
AV={};PN={};SRC={};VLM={}
KEY='perp'   # solo conto perpetui: il conto totale include lo spot (airdrop HYPE di fine 2024 = falso PnL)
def add(a,d,src):
    SRC.setdefault(a,set()).add(src)
    if a in AV: return
    s=serie(d,KEY)
    try: VLM[a]=float(d[KEY]['vlm'])
    except Exception: VLM[a]=np.nan
    if s is None or len(s)<3: return
    i=s.index.searchsorted(G,side='right')-1; ok=i>=0; age=np.full(len(G),np.inf); age[ok]=(G[ok]-s.index[i[ok]]).total_seconds()/86400
    av=np.where(ok&(age<=15),s.av.values[np.clip(i,0,None)],np.nan); pn=np.where(ok&(age<=15),s.pnl.values[np.clip(i,0,None)],np.nan)
    AV[a]=av; PN[a]=pn
for g in ['pit','stat','lb','vaults']:
    if not os.path.exists(f'data/{g}.jsonl'): continue
    for l in open(f'data/{g}.jsonl'):
        try: d=json.loads(l)
        except Exception: continue
        if d.get('err'): continue
        add(d['a'],d,g)
# etichette di provenienza piu' fini
lbset={r['ethAddress'] for r in json.load(open('data/leaderboard_2026-11-11.json'))['leaderboardRows']}
liq={x['name'] for x in json.load(open('data/stats/largest_liquidated_notional_by_user.json'))['table_data']}
pit={u:t for u,c,t in json.load(open('data/pit_users.json'))['users']} if os.path.exists('data/pit_users.json') else {}
dayfirst={}
for k,f in [('daily_usd_volume_by_user','user'),('daily_trades_by_user','user')]:
    for x in json.load(open(f'data/stats/{k}.json'))['chart_data']:
        t=pd.Timestamp(x['time']); dayfirst[x[f]]=min(dayfirst.get(x[f],t),t)
vm=json.load(open('data/vault_meta.json'))
A=pd.DataFrame(AV,index=G); P=pd.DataFrame(PN,index=G)
M=pd.DataFrame(index=A.columns); M['src']=[','.join(sorted(SRC[a])) for a in M.index]
M['in_lb_oggi']=[a in lbset for a in M.index]; M['top_liq']=[a in liq for a in M.index]; M['pit2024q4']=[a in pit for a in M.index]
M['vlm']=[VLM.get(a,np.nan) for a in M.index]
M['top_giorno_dal']=[dayfirst.get(a,pd.NaT) for a in M.index]; M['vault']=[a in vm for a in M.index]; M['vault_chiuso']=[vm.get(a,{}).get('closed',False) for a in M.index]
A.to_parquet('data/panel_av.parquet'); P.to_parquet('data/panel_pnl.parquet'); M.to_parquet('data/panel_meta.parquet')
yrs=(A.notna().sum()*14/365.25); M['turnover_anno']=M.vlm/A.where(A>0).mean()/yrs.clip(lower=0.25)
M.to_parquet('data/panel_meta.parquet'); print('turnover annuo (volume/conto medio), quantili:',M.turnover_anno.quantile([.1,.25,.5,.75,.9]).round(0).to_dict())
print('griglia',G[0],G[-1],len(G),'| conti',A.shape[1]); print(M[['in_lb_oggi','top_liq','pit2024q4','vault']].sum()); print(M.src.value_counts().head(12))
print('conti con dati al 2025-01-02:',A.loc['2025-01-02 00:30'].notna().sum(),' con AV>=10k:',(A.loc['2025-01-02 00:30']>=1e4).sum())
