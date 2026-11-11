"""Scarica da Hyperliquid (API pubblica, nessun dato privato inviato): universo; per ogni moneta candele 1d (tutta la storia),
prime 500 ore di funding (la prima = ora di quotazione), candele fini dei primi 20 giorni (1h se dentro le ultime 5000 ore, 4h se dentro
le ultime 5000x4 ore: l'API conserva solo le ultime 5000 candele per intervallo). Salva hl_cache.json."""
import hl, json, time, os, concurrent.futures as cf
OUT='/home/user/GERVA-Capital/research/v5/v5/validazione/hl_cache.json'
now=int(time.time()*1000); H=3600_000
C=json.load(open(OUT)) if os.path.exists(OUT) else {}
u=hl.post({'type':'meta'})['universe']
C['_meta']=[(x['name'],bool(x.get('isDelisted')),x.get('maxLeverage')) for x in u]; C['_now']=now
cv=lambda L:[(c['t'],float(c['o']),float(c['h']),float(c['l']),float(c['c']),float(c['v'])) for c in L]
def one(n):
    try:
        d=hl.post({'type':'candleSnapshot','req':{'coin':n,'interval':'1d','startTime':0,'endTime':now}},tries=3)
        if not d: return n,dict(t_fund=None,t_day=None,day=[],iv=None,fine=[],fund=[])
        td=d[0]['t']; f0=hl.post({'type':'fundingHistory','coin':n,'startTime':max(td-24*H,0),'endTime':td+21*24*H},tries=3)
        tf=f0[0]['time'] if f0 else None; t0=tf or td; fine=[]; iv=None
        for i,span in (('1h',4990*H),('4h',4990*4*H)):
            if t0>=now-span:
                fine=hl.post({'type':'candleSnapshot','req':{'coin':n,'interval':i,'startTime':t0-4*H,'endTime':t0+20*24*H}},tries=3); iv=i; break
        return n,dict(t_fund=tf,t_day=td,day=cv(d),iv=iv,fine=cv(fine),fund=[(r['time'],float(r['fundingRate'])) for r in f0])
    except Exception as e:
        print('FAIL',n,str(e)[:100],flush=True); return n,None
todo=[x['name'] for x in u if x['name'] not in C]; print('da fare',len(todo),flush=True)
with cf.ThreadPoolExecutor(3) as ex:
    for k,(n,r) in enumerate(ex.map(one,todo)):
        if r is not None: C[n]=r
        if k%25==0: print(k,n,round(time.time()-now/1000),flush=True); json.dump(C,open(OUT,'w'))
json.dump(C,open(OUT,'w')); print('fatto',len(C)-2)
