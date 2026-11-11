"""Enumerazione punto-nel-tempo degli indirizzi attivi: campiona blocchi storici dall'explorer
(POST https://rpc.hyperliquid.xyz/explorer {"type":"blockDetails","height":h}) nella finestra 2024-09-15 -> 2024-12-31
e raccoglie gli utenti che hanno inviato ordini. Nessuna informazione successiva al 2024-12-31 entra nella lista."""
import json,random,sys,time,collections
from concurrent.futures import ThreadPoolExecutor
from hl import post,EX
random.seed(7); N=int(sys.argv[1]) if len(sys.argv)>1 else 2500
hs=sorted(random.sample(range(300_000_000,443_000_000),N))
def one(h):
    r=post({"type":"blockDetails","height":h},EX)
    if not r: return h,None,[]
    b=r['blockDetails']; return h,b['blockTime'],[(x['user'],x['action'].get('type')) for x in b['txs'] if not x.get('error')]
cnt=collections.Counter(); first={}; nb=0; tmin=1e18; tmax=0
with ThreadPoolExecutor(4) as ex:
    for h,t,us in ex.map(one,hs):
        if t is None: continue
        nb+=1; tmin=min(tmin,t); tmax=max(tmax,t)
        if t>1735689600000: continue   # oltre il 2024-12-31: scartato
        for u,a in us:
            if a in('order','batchModify','modify','twapOrder'): cnt[u]+=1; first.setdefault(u,t)
json.dump(dict(blocks=nb,tmin=tmin,tmax=tmax,users=[[u,c,first[u]] for u,c in cnt.most_common()]),open('data/pit_users.json','w'))
print('blocchi',nb,'utenti',len(cnt),time.strftime('%Y-%m-%d',time.gmtime(tmin/1000)),time.strftime('%Y-%m-%d',time.gmtime(tmax/1000)))
