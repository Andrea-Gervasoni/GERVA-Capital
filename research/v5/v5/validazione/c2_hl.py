"""Claim 2 - eseguibilita' su Hyperliquid (retail italiano senza Binance Futures). SIMULATO. Dati: API pubblica Hyperliquid (hl_cache.json)
+ quotazioni Binance (c2_trades_binance.parquet, dallo script c2_listing.py)."""
import json, re, time, os, numpy as np, pandas as pd, hl, concurrent.futures as cf
HERE='/home/user/GERVA-Capital/research/v5/v5/validazione/'; H=3600_000
C=json.load(open(HERE+'hl_cache.json')); now=C['_now']; meta={m[0]:m for m in C['_meta']}
T=pd.read_parquet(HERE+'c2_trades_binance.parquet'); T=T[T.t0>='2023-06-01'].copy()
ms=lambda t: int(pd.Timestamp(t).value//10**6); ts=lambda m: pd.Timestamp(m,unit='ms')
def hlname(sym):
    b=sym[:-4]; c=[b]
    m=re.match(r'^1000(?!0)(.+)$',b)
    if m: c=['k'+m.group(1),m.group(1)]
    for x in c:
        if x in C and C[x].get('t_day'): return x
    return None
T['hl']=T.sym.map(hlname)
def hl_t0(n):
    if not isinstance(n,str): return pd.NaT
    r=C[n]; tf=r['t_fund']; td=r['t_day']
    # prima ora di funding se cade nel primo giorno di candele, altrimenti l'inizio della prima candela giornaliera
    return ts(tf) if (tf and td-H<=tf<=td+25*H) else ts(td)
T['hl_t0']=pd.to_datetime([hl_t0(x) for x in T.hl]); T['lag_h']=(T.hl_t0-T.t0).dt.total_seconds()/3600
T=T.reset_index(drop=True); n=len(T); ever=T.hl.notna(); w24=ever&(T.lag_h<=24); w7=ever&(T.lag_h<=168); pre=ever&(T.lag_h<0)
print('universo Hyperliquid (dex principale): %d monete, di cui %d tolte dal listino'%(len(meta),sum(m[1] for m in meta.values())))
print('quotazioni perp Binance dal 2023-06 (con trade simulato): %d'%n)
print('  mai su Hyperliquid (per nome, con mappa 1000X->kX): %d (%.0f%%)'%((~ever).sum(),(~ever).mean()*100))
print('  su Hyperliquid entro 24h dalla quotazione Binance: %d (%.1f%%)  [di cui gia\' quotate PRIMA di Binance: %d]'%(w24.sum(),w24.mean()*100,pre.sum()))
print('  entro 7 giorni: %d (%.1f%%) ; piu\' tardi: %d'%(w7.sum(),w7.mean()*100,(ever&~w7).sum()))
print('  per anno (quota entro 24h / entro 7g / n):',{int(y):(round(w24[g.index].mean(),2),round(w7[g.index].mean(),2),len(g)) for y,g in T.groupby(T.t0.dt.year)})
print('  ritardo Hyperliquid - Binance (ore), quantili sui presenti:',T.lag_h[ever].quantile([.1,.25,.5,.75,.9]).round(0).to_dict())
def st(x,lab):
    if len(x)<3: print(f'{lab:70s} n {len(x)}'); return
    w=x.groupby(x.entry.dt.floor('7D')).R.sum(); print(f'{lab:70s} n {len(x):3d} R {x.R.mean():+.3f} t_sett {w.mean()/w.std()*np.sqrt(len(w)):+.2f} vincenti {(x.R>0).mean():.0%}')
print('\n--- R sulle candele BINANCE, per disponibilita\' su Hyperliquid')
st(T,'tutte le quotazioni Binance dal 2023-06'); st(T[w24],'solo quelle su Hyperliquid entro 24h'); st(T[pre],'  di cui gia\' su Hyperliquid prima di Binance'); st(T[w24&~pre],'  di cui quotate su HL tra 0 e 24h dopo')
st(T[w7&~w24],'su Hyperliquid tra 24h e 7 giorni'); st(T[~w24],'NON su Hyperliquid entro 24h'); st(T[~ever],'mai su Hyperliquid')
# ---- candele e funding Hyperliquid attorno alla finestra del trade (ingresso = quotazione Binance + 24h)
XC=HERE+'hl_cache_win.json'; W=json.load(open(XC)) if os.path.exists(XC) else {}
def fetch(row):
    k=row.sym
    if k in W: return k,W[k]
    a=ms(row.t0)+24*H; z=a+170*H
    try:
        iv='1h' if a>=now-4990*H else ('4h' if a>=now-4990*4*H else '1d')
        pad={'1h':H,'4h':4*H,'1d':24*H}[iv]
        c=hl.post({'type':'candleSnapshot','req':{'coin':row.hl,'interval':iv,'startTime':a-pad,'endTime':z+2*pad}},tries=3)
        f=hl.post({'type':'fundingHistory','coin':row.hl,'startTime':a,'endTime':z+pad},tries=3)
        return k,dict(iv=iv,c=[(x['t'],float(x['o']),float(x['h']),float(x['l']),float(x['c'])) for x in c],f=[(r['time'],float(r['fundingRate'])) for r in f])
    except Exception as e:
        print('FAIL',k,str(e)[:80]); return k,None
S=T[w24]
with cf.ThreadPoolExecutor(3) as ex:
    for k,r in ex.map(fetch,[r for _,r in S.iterrows()]):
        if r is not None: W[k]=r
json.dump(W,open(XC,'w'))
def simhl(c,f,t_in,iv,stop=0.15,cm=1.0,fmult=1.0):
    """short alla prima apertura di barra >= t_in, stop 15% sui massimi, uscita all'apertura della prima barra >= ingresso+168h."""
    c=[x for x in c if x[0]>=t_in]
    if not c: return None
    e=c[0]; 
    if e[0]-t_in>{'1h':H,'4h':4*H,'1d':24*H}[iv]: return None      # la moneta non era ancora negoziabile
    p0=e[1]; sp=p0*(1+stop); px=None; te=None
    for x in c:
        if x[0]>=e[0]+168*H: px=x[1]; te=x[0]; why='tempo'; break
        if x[2]>=sp: px=max(sp,x[1])*(1+0.0005*cm); te=x[0]+{'1h':H,'4h':4*H,'1d':24*H}[iv]//2; why='stop'; break
    if px is None: return None
    fs=sum(r for t,r in f if e[0]<t<=te)
    net=max(-(px/p0-1)-2*0.00065*cm+fs*fmult,-1/min(40,1/(stop/0.6+0.005)))
    return dict(entry=ts(e[0]),R=net/stop,why=why,fund=fs,iv=iv,nf=sum(1 for t,r in f if e[0]<t<=te))
rows=[]
for _,r in S.iterrows():
    w=W.get(r.sym)
    if not w: continue
    x=simhl(w['c'],w['f'],ms(r.t0)+24*H,w['iv'])
    if x: x.update(sym=r.sym,R_bn=r.R,fund_bn=r.fund); rows.append(x)
Hh=pd.DataFrame(rows)
print('\n--- stessa regola sulle candele e sul funding di HYPERLIQUID (ingresso = quotazione Binance + 24h), solo monete negoziabili su HL in quel momento')
print('trade simulati su HL: %d su %d ; per intervallo di candela: %s'%(len(Hh),len(S),Hh.iv.value_counts().to_dict()))
st(Hh,'HL, tutte le candele (1h/4h/1d)'); st(Hh[Hh.iv!='1d'],'HL, solo candele 1h/4h'); st(Hh[Hh.iv=='1h'],'HL, solo candele 1h'); st(Hh[Hh.iv=='1d'],'HL, solo candele 1d (grossolano: ingresso fino a 24h in ritardo)')
st(Hh.assign(R=Hh.R_bn),'stessi trade sulle candele Binance')
print('funding HL per trade (short incassa): media %+.3f%% (%+.3f R) ; Binance sugli stessi trade %+.3f%% ; rapporto %.1fx ; corr R HL-Binance %.2f'%(Hh.fund.mean()*100,Hh.fund.mean()/0.15,Hh.fund_bn.mean()*100,Hh.fund.mean()/Hh.fund_bn.mean() if Hh.fund_bn.mean() else np.nan,Hh.R.corr(Hh.R_bn)))
yrs=(T.t0.max()-T.t0.min()).days/365.25; print('trade eseguibili su HL per anno: %.0f (contro %.0f su Binance)'%(len(Hh)/yrs,n/yrs))
x=Hh.sort_values('R',ascending=False); st(Hh.drop(x.groupby(x.entry.dt.year).head(5).index),'HL senza i 5 migliori trade per anno')
print('per anno HL:',Hh.groupby(Hh.entry.dt.year).R.agg(['size','mean']).round(3).to_dict('index'))
# ---- regola ancorata alla quotazione di Hyperliquid (tutte le monete HL quotate dal 2023-06)
rows=[]
for nme,r in C.items():
    if nme.startswith('_') or not r.get('t_day'): continue
    t0=hl_t0(nme)
    if t0<pd.Timestamp('2023-06-01'): continue
    t_in=ms(t0)+24*H
    if r['iv'] and r['fine']: c=[x[:5] for x in r['fine']]; iv=r['iv']
    else: c=[x[:5] for x in r['day']]; iv='1d'
    x=simhl(c,r['fund'],t_in,iv)
    if x: x['sym']=nme; rows.append(x)
O=pd.DataFrame(rows)
print('\n--- regola ancorata alla quotazione di HYPERLIQUID (short 24h dopo la prima ora di HL), candele e funding HL')
print('monete HL quotate dal 2023-06: %d trade ; per intervallo: %s'%(len(O),O.iv.value_counts().to_dict()))
st(O,'HL propria quotazione, tutte'); st(O[O.iv!='1d'],'  solo candele 1h/4h'); st(O[O.iv=='1d'],'  solo candele 1d (grossolano)')
print('  funding medio per trade %+.3f%% (%+.3f R) ; per anno: %s'%(O.fund.mean()*100,O.fund.mean()/0.15,O.groupby(O.entry.dt.year).R.agg(['size','mean']).round(3).to_dict('index')))
Hh.to_parquet(HERE+'c2_trades_hl.parquet'); O.to_parquet(HERE+'c2_trades_hl_own.parquet')
