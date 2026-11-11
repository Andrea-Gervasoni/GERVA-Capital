"""B7.3 - rotazione trasversale del carry su TUTTI i perps di Hyperliquid (parametri congelati su Binance <=2022: congelato.json).
Gamba lunga: spot su Kraken (30 pb per lato) oppure spot Hyperliquid (10 pb) dove esiste; gamba corta: perp HL (6,5 pb per lato).
Tutto il periodo Hyperliquid (2024-01 -> 2026-11) e' VERIFICA: la sede non esisteva nel periodo di scelta. SIMULATO."""
import pandas as pd, numpy as np, json, os, re, warnings, sys
from lib import *
warnings.filterwarnings('ignore'); pd.set_option('display.width',250)
C='/home/user/GERVA-Capital/data_cache/'; D=C+'v6_b7/'; H=D+'hl/'
M=json.load(open(H+'_meta.json')); P=json.load(open('congelato.json')); print('parametri congelati:',P)
maxlev={}; dexof={}; delisted=set()
for k,v in M.items():
    if k=='main' or k.startswith('dex_'):
        for a in v[0]['universe']:
            maxlev[a['name']]=a.get('maxLeverage',3); dexof[a['name']]=k
            if a.get('isDelisted'): delisted.add(a['name'])
F={};PR={};O={};Hi={};Cl={};V={}
for fn in os.listdir(H):
    if fn.endswith('_1d.parquet') or not fn.endswith('.parquet'): continue
    c=fn[:-8].replace('__',':'); f=pd.read_parquet(H+fn); d=pd.read_parquet(H+fn[:-8]+'_1d.parquet')
    if len(f)<48: continue
    f=f.set_index('t'); f=f[~f.index.duplicated()]
    v4=C+f'v4_hl_fund_{c}.parquet'
    if os.path.exists(v4):
        o=pd.read_parquet(v4); o.index=o.index.floor('h'); o=o[~o.index.duplicated()]; o=o[o.index<f.index[0]]
        f=pd.concat([o.rename(columns={'fundingRate':'f','premium':'p'}),f])
    cnt=f.f.resample('1D').count(); F[c]=f.f.resample('1D').sum().where(cnt>=20); PR[c]=f.p.resample('1D').last()
    d=d.set_index('t'); O[c]=d.o; Hi[c]=d.h; Cl[c]=d.c; V[c]=d.v*d.c
F=pd.DataFrame(F).sort_index(); F=F[F.index<F.index[-1]]; PR=pd.DataFrame(PR).reindex(F.index); O=pd.DataFrame(O).reindex(F.index); Hi=pd.DataFrame(Hi).reindex(F.index); Cl=pd.DataFrame(Cl).reindex(F.index); V=pd.DataFrame(V).reindex(F.index)
main=[c for c in F if dexof.get(c)=='main']; hip3=[c for c in F if dexof.get(c,'main')!='main']
print('monete con funding scaricato:',F.shape[1],'| dex principale',len(main),'(di cui oggi fuori listino',len([c for c in main if c in delisted]),') | HIP-3',len(hip3),'| periodo',F.index[0].date(),F.index[-1].date())
print('copertura dex principale: quotati oggi',sum(1 for c,d in dexof.items() if d=='main' and c not in delisted),'scaricati',len([c for c in main if c not in delisted]))
# ---- copertura spot
kb=set(json.load(open(D+'kraken_spot_bases.json'))); alias={'XXBT':'BTC','XBT':'BTC','XETH':'ETH','XXDG':'DOGE','XDG':'DOGE','XLTC':'LTC','XXRP':'XRP','XXLM':'XLM','XZEC':'ZEC','XXMR':'XMR','XETC':'ETC'}
kb={alias.get(b,b) for b in kb}
def base(c): return c[1:] if re.match(r'^k[A-Z]',c) else c
kr_ok={c for c in main if base(c) in kb}
st=M['spot'][0]; tok={t['index']:t['name'] for t in st['tokens']}; sv={}
cv={cx['coin']:float(cx.get('dayNtlVlm') or 0) for cx in M['spot'][1]}
for u in st['universe']: sv[tok[u['tokens'][0]]]=max(sv.get(tok[u['tokens'][0]],0),cv.get(u['name'],0))
print('spot Hyperliquid, primi per volume (M$/g):',{k:round(v/1e6,1) for k,v in sorted(sv.items(),key=lambda x:-x[1])[:14]})
hls={c for c in main if max(sv.get(c,0),sv.get('U'+c,0),sv.get('UFART',0) if c=='FARTCOIN' else 0)>3e5}
print('copribili con spot Kraken (lista di OGGI: lieve look-ahead):',len(kr_ok),'su',len(main),'| con spot Hyperliquid (volume>0,3 M$/g):',sorted(hls))
liq=V.rolling(30,min_periods=15).median().shift(1)
S0=pd.Timestamp('2024-02-01')
def run(cols,N,cost,minliq=5e6,delay=1,k=None,ent=None,ext=None,start=S0,sign=1,extra=0.0):
    cols=[c for c in cols if c in F]; f=sign*F[cols]-extra; e=(liq[cols]>minliq)&F[cols].notna()
    r,nh,L=rotate(f,e,k or P['k'],N,ent if ent is not None else P['ent'],ext if ext is not None else P['ext'],cost_rt=cost,delay=delay,dP=sign*PR[cols].diff())
    return r[start:],nh[start:],L
def tab(r,lab): 
    d=stats(r,lab); pr(d); return d
def peryear(r): 
    a=(r.groupby(r.index.year).sum()*100).round(2).to_dict(); a['ult90g_annuo']=round(r.iloc[-90:].mean()*36500,2); a['ult30g_annuo']=round(r.iloc[-30:].mean()*36500,2); return a
print('\n=== A. per unita\' di NOZIONALE (senza leva: 1 di spot + margine a parte), netto costi, 2024-02 -> oggi')
big=['BTC','ETH','SOL']; R={}
r,nh,L=run(sorted(kr_ok),P['N'],0.0073); R['rot_tutte']=r; tab(r,'rotazione TUTTE (spot Kraken), N=%d'%P['N']); print('   per anno %:',peryear(r),'| occupazione',round(nh.mean()/P['N'],2),'| durata media g',round((L['out']-L['in']).dt.days.mean(),1),'| ingressi/anno',round(len(L)/((r.index[-1]-r.index[0]).days/365),1))
print('   monete tenute piu\' a lungo (giorni):',(L.assign(d=(L['out']-L['in']).dt.days).groupby('coin').d.sum().sort_values(ascending=False).head(12)).to_dict())
Lall=L
r2,_,_=run(sorted(kr_ok),P['N'],0.0146); tab(r2,'   costi x2'); r3,_,_=run(sorted(kr_ok),P['N'],0.0073,delay=2); tab(r3,'   un giorno di ritardo in piu\'')
rb,nhb,Lb=run(big,3,0.0073); R['rot_big3']=rb; tab(rb,'rotazione solo BTC/ETH/SOL (stesse soglie)'); print('   per anno %:',peryear(rb),'| occupazione',round(nhb.mean()/3,2))
bh=F[big].mean(axis=1)[S0:]; R['hold_big3']=bh; tab(bh,'BTC/ETH/SOL sempre dentro (lordo costi d\'ingresso)'); print('   per anno %:',peryear(bh))
bh23=F[big].mean(axis=1)['2023-06-01':]; print('   idem dal 2023-06, per anno %:',peryear(bh23))
r10,nh10,L10=run(sorted(kr_ok),10,0.0073); tab(r10,'rotazione TUTTE, N=10 (variante)'); print('   per anno %:',peryear(r10))
rq,nhq,Lq=run(sorted(kr_ok),P['N'],0.0073,k=7,ent=0.15,ext=0.05); tab(rq,'rotazione TUTTE, veloce k=7 ent15 ext5 (variante)'); print('   per anno %:',peryear(rq))
rl,nhl,Ll=run(sorted(kr_ok),P['N'],0.0073,minliq=20e6); tab(rl,'rotazione TUTTE, liquidita\' >20 M$/g (variante)'); print('   per anno %:',peryear(rl))
rh,nhh,Lh=run(sorted(hls),min(3,len(hls)),0.0033,minliq=5e6); R['rot_hlspot']=rh; tab(rh,'rotazione con SPOT HYPERLIQUID (10 pb), N=3'); print('   per anno %:',peryear(rh),'| occupazione',round(nhh.mean()/3,2))
rn,nhn,Ln=run(sorted(kr_ok),P['N'],0.0073,sign=-1,extra=0.0012); tab(rn,'lato NEGATIVO: perp lungo + spot corto a prestito (0,02%/4h Kraken)'); print('   occupazione',round(nhn.mean()/P['N'],2))
ntr=7
# troncamento: il diario fino a t calcolato su dati tagliati a t deve coincidere
t=pd.Timestamp('2025-06-30'); cols=sorted(kr_ok); e=(liq[cols]>5e6)&F[cols].notna()
_,_,La=rotate(F[cols][:t],e[:t],P['k'],P['N'],P['ent'],P['ext']); _,_,Lb2=rotate(F[cols],e,P['k'],P['N'],P['ent'],P['ext'])
a=La[La['out']<=t].reset_index(drop=True); b=Lb2[Lb2['out']<=t].reset_index(drop=True); print('controllo di troncamento (diario posizioni chiuse entro 2025-06-30 identico):',a.equals(b),len(a))
print('\n=== B. leva sulla gamba corta e liquidazioni (massimi giornalieri = massimo dei massimi orari; rimargine a meta\' strada)')
print('capitale = spot (nozionale) + margine (nozionale/leva): rendimento sul capitale = rendimento sul nozionale x leva/(leva+1), meno liquidazioni')
for lab,rr,LL,N in (('rotazione TUTTE',r,Lall,P['N']),('BTC/ETH/SOL sempre dentro',bh,pd.DataFrame([(c,S0,F.index[-1]+pd.Timedelta(days=1)) for c in big],columns=['coin','in','out']),3)):
    for lev in (1,2,3,5):
        ls,nl,nr,ev=liq_scan(LL,O,Hi,Cl,maxlev,lev,N); ls=ls.reindex(rr.index).fillna(0); rc=(rr-ls)*lev/(lev+1); d=stats(rc)
        yrs=(rr.index[-1]-rr.index[0]).days/365
        print(f'  {lab:26s} leva {lev}x: quota investita {lev/(lev+1):.0%} | CAGR sul capitale {d["cagr"]*100:5.2f}% | liquidazioni {nl} ({nl/yrs:.1f}/anno), rimargini {nr} | costo liquidazioni {ls.sum()*lev/(lev+1)/yrs*100:.2f}%/anno | 2026: {rc[rc.index.year==2026].sum()*100:.2f}% | ult90g annuo {rc.iloc[-90:].mean()*36500:.2f}%')
        if lab.startswith('rot') and lev==3: print('     esempi:',[(c,str(t.date()),round(x,2)) for c,t,x in ev[:8]])
        if lab.startswith('rot'): R['rot_tutte_cap%dx'%lev]=rc
        else: R['hold_big3_cap%dx'%lev]=rc
print('  leva massima consentita da Hyperliquid per le monete tenute dalla rotazione:',{c:maxlev[c] for c in Lall.coin.unique()[:25]})
print('\n=== C. HIP-3 (perps su azioni/materie prime, dex xyz e altri): funding annuo % dalla quotazione e ultimi 90 g; copertura = titolo vero su IBKR')
h=[c for c in hip3 if V[c].iloc[-30:].median()>2e6]
T=pd.DataFrame({'dal':[str(F[c].first_valid_index().date()) for c in h],'annuo%':[F[c].mean()*36500 for c in h],'ult90%':[F[c].iloc[-90:].mean()*36500 for c in h],'ult30%':[F[c].iloc[-30:].mean()*36500 for c in h],'pos%':[(F[c].dropna()>0).mean()*100 for c in h],'vol_M$':[V[c].iloc[-30:].median()/1e6 for c in h],'maxlev':[maxlev[c] for c in h]},index=h).sort_values('vol_M$',ascending=False)
print(T.head(30).round(1).to_string()); print('  mediana di tutti (n=%d): annuo %.1f%% | ult90 %.1f%% ; media pesata per volume: %.1f%%'%(len(T),T['annuo%'].median(),T['ult90%'].median(),(T['annuo%']*T['vol_M$']).sum()/T['vol_M$'].sum()))
eq=[c for c in h if c.startswith('xyz:')]
r_h,nh_h,L_h=run(eq,5,0.0030,minliq=5e6,start=pd.Timestamp('2025-11-15')); 
if len(r_h)>40: tab(r_h,'rotazione HIP-3 xyz (hedge IBKR, 30 pb a/r), N=5'); print('   per anno %:',peryear(r_h),'occupazione',round(nh_h.mean()/5,2),'| tenute:',(L_h.assign(d=(L_h['out']-L_h['in']).dt.days).groupby('coin').d.sum().sort_values(ascending=False).head(10)).to_dict()); R['rot_hip3']=r_h; ntr+=1
print('\nvarianti provate in questo script:',ntr+8)
pd.DataFrame(R).to_parquet('_rot_hl.parquet'); F.to_parquet(D+'hl_F_daily.parquet')
