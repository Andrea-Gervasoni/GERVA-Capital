"""Scarica `portfolio` (indirizzi) e `vaultDetails` (vault) e tiene solo le serie allTime/perpAllTime.
uso: 02_scarica.py <gruppo>  con gruppo in vaults | pit | lb"""
import json,sys,os,time
from concurrent.futures import ThreadPoolExecutor
from hl import post
g=sys.argv[1]; out=f'data/{g}.jsonl'
done=set()
if os.path.exists(out):
    for l in open(out):
        try: done.add(json.loads(l)['a'])
        except Exception: pass
if g=='vaults':
    import pandas as pd
    v=json.load(open('data/vaults_2026-11-11.json')); L=[]
    for x in v:
        s=x['summary']; m=max([abs(float(p)) for p in dict(x['pnls'])['allTime']] or [0])
        if s['createTimeMillis']<1762819200000 and (m>3e3 or float(s['tvl'])>3e4) or s['relationship']['type']!='normal': L.append(s['vaultAddress'])
elif g=='pit':
    L=[u for u,c,t in json.load(open('data/pit_users.json'))['users']][:int(sys.argv[2])]
elif g=='lb':
    r=json.load(open('data/leaderboard_2026-11-11.json'))['leaderboardRows']
    f=lambda x,k: float(dict(x['windowPerformances'])['allTime'][k])
    top=sorted(r,key=lambda x:-f(x,'pnl'))[:700]; big=sorted(r,key=lambda x:-float(x['accountValue']))[:700]
    import random; random.seed(3); rnd=random.sample(r,1500)
    L=list(dict.fromkeys([x['ethAddress'] for x in top+big+rnd]))
elif g=='stat':
    # indirizzi dalle tabelle pubbliche di stats (d2v1fiwobg9w6.cloudfront.net): i piu' liquidati, i piu' attivi per giorno (lista punto-nel-tempo)
    L=[]
    for k in ['largest_liquidated_notional_by_user','largest_users_by_usd_volume','largest_user_depositors','largest_user_trade_count']:
        L+=[x['name'] for x in json.load(open(f'data/stats/{k}.json'))['table_data']]
    for k in ['daily_usd_volume_by_user','daily_trades_by_user']:
        L+=[x['user'] for x in json.load(open(f'data/stats/{k}.json'))['chart_data']]
    L=list(dict.fromkeys(L))
L=[a for a in L if a not in done and isinstance(a,str) and a.startswith('0x') and len(a)==42]; print(g,'da scaricare',len(L),flush=True)
def one(a):
    if g=='vaults':
        r=post({"type":"vaultDetails","vaultAddress":a})
        if not r: return dict(a=a,err=1)
        p=dict(r['portfolio']); 
        return dict(a=a,name=r['name'],leader=r['leader'],closed=r['isClosed'],comm=r['leaderCommission'],lf=r['leaderFraction'],nfol=len(r['followers']),apr=r['apr'],
                    all=p['allTime'],perp=p.get('perpAllTime'))
    r=post({"type":"portfolio","user":a})
    if not r: return dict(a=a,err=1)
    p=dict(r); return dict(a=a,all=p['allTime'],perp=p.get('perpAllTime'))
with ThreadPoolExecutor(5) as ex, open(out,'a') as f:
    for i,d in enumerate(ex.map(one,L)):
        f.write(json.dumps(d)+'\n')
        if i%200==0: f.flush(); print(i,time.strftime('%H:%M:%S'),flush=True)
print('fine',g)
