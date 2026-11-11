"""B7 - scarico Hyperliquid (API pubblica): universo perps (dex principale + HIP-3), contesti correnti, candele 1d,
funding orario dal 2024-01-01 (o dalla quotazione). Cache: data_cache/v6_b7/hl/. Ripartibile."""
import json, os, sys, time, urllib.request, concurrent.futures as cf, pandas as pd
D='/home/user/GERVA-Capital/data_cache/v6_b7/hl/'; H=3600_000
def post(body, tries=8):
    for k in range(tries):
        try:
            rq=urllib.request.Request('https://api.hyperliquid.xyz/info',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':'research-client'})
            return json.loads(urllib.request.urlopen(rq,timeout=40).read())
        except Exception as e:
            err=e; time.sleep(min(3*(k+1),20))
    raise err
now=int(time.time()*1000); T0=int(pd.Timestamp('2024-01-01').value//10**6)
if not os.path.exists(D+'_meta.json'):
    M={}
    M['main']=post({'type':'metaAndAssetCtxs'}); M['spot']=post({'type':'spotMetaAndAssetCtxs'}); M['dexs']=post({'type':'perpDexs'})
    for dx in [d['name'] for d in M['dexs'] if d]:
        try: M['dex_'+dx]=post({'type':'metaAndAssetCtxs','dex':dx})
        except Exception as e: print('dex fail',dx,e)
    json.dump(M,open(D+'_meta.json','w'))
M=json.load(open(D+'_meta.json'))
coins=[]
for k,v in M.items():
    if k=='main' or k.startswith('dex_'):
        u=v[0]['universe']; ctx=v[1]
        for a,c in zip(u,ctx):
            coins.append((a['name'],float(c.get('dayNtlVlm') or 0),bool(a.get('isDelisted'))))
coins.sort(key=lambda x:-x[1]); print('perps totali',len(coins),'non delisted',sum(1 for c in coins if not c[2]),flush=True)
def one(c):
    n=c[0]; fn=D+n.replace(':','__')+'.parquet'
    if os.path.exists(fn): return n,0
    try:
        d=post({'type':'candleSnapshot','req':{'coin':n,'interval':'1d','startTime':0,'endTime':now}})
        if not d: return n,-1
        day=pd.DataFrame([(x['t'],float(x['o']),float(x['h']),float(x['l']),float(x['c']),float(x['v'])) for x in d],columns=['t','o','h','l','c','v'])
        t=max(T0,d[0]['t']-24*H); rows=[]; nc=0
        while t<now:
            f=post({'type':'fundingHistory','coin':n,'startTime':t,'endTime':now}); nc+=1
            if not f: break
            rows+= [(r['time'],float(r['fundingRate']),float(r['premium'])) for r in f]
            if len(f)<500: break
            t=f[-1]['time']+1
        fd=pd.DataFrame(rows,columns=['t','f','p']).drop_duplicates('t')
        fd['t']=pd.to_datetime(fd.t,unit='ms').dt.floor('h'); day['t']=pd.to_datetime(day.t,unit='ms')
        fd.to_parquet(fn); day.to_parquet(fn.replace('.parquet','_1d.parquet'))
        return n,nc
    except Exception as e:
        print('FAIL',n,str(e)[:100],flush=True); return n,-2
t0=time.time()
with cf.ThreadPoolExecutor(2) as ex:
    for k,(n,nc) in enumerate(ex.map(one,coins)):
        if k%10==0: print(k,n,nc,round(time.time()-t0),flush=True)
print('fatto',flush=True)
