"""Validazione claim 2 (A6 LISTING-SHORT): ri-derivazione indipendente dalle candele orarie e dal funding in cache. SIMULATO."""
import numpy as np, pandas as pd, re
ROOT='/home/user/GERVA-Capital'
D=pd.read_parquet(ROOT+'/data_cache/v5_a6_listing_1h.parquet'); FU=pd.read_parquet(ROOT+'/data_cache/v4_allperp_fund.parquet'); C=pd.read_parquet(ROOT+'/data_cache/v4_allperp_close.parquet')
FEE=0.00065
def one(d, f, off=24, H=168, stop=0.15, cm=1.0, sslip=0.0005, fmult=1.0, worst=False):
    if len(d)<=off+H: return None
    o=d.open.values; h=d.high.values; ix=d.index
    p0=o[off]; sp=p0*(1+stop); px=None
    for k in range(off,off+H):
        if h[k]>=sp:
            px=(h[k] if worst else max(sp,o[k]))*(1+sslip*cm); te=ix[k]+pd.Timedelta(minutes=30); why='stop'; break
    if px is None: px=o[off+H]; te=ix[off+H]; why='tempo'
    fs=0.0
    if f is not None and len(f):
        ft=f.index+pd.Timedelta(hours=23,minutes=59); fs=f[(ft>ix[off])&(ft<=te)].sum()
    else: fs=0.0001*3*((te-ix[off]).total_seconds()/86400)
    L=min(40,1/(stop/0.6+0.005)); net=max(-(px/p0-1)-2*FEE*cm+fs*fmult,-1/L)
    return dict(t0=ix[0],entry=ix[off],exit=te,R=net/stop,why=why,fund=fs,gap=(px/sp-1) if why=='stop' else 0.0,qv24=d.quote_volume.iloc[:24].sum(),r24=d.close.iloc[23]/o[0]-1,nofund=f is None or len(f)==0)
G={s:d.set_index('t').sort_index() for s,d in D.groupby('sym')}
def book(**k):
    out=[]
    for s,d in G.items():
        f=FU[s].dropna() if s in FU else None
        r=one(d,f,**k)
        if r: r['sym']=s; out.append(r)
    return pd.DataFrame(out)
def st(T,lab):
    def o(y):
        if len(y)<5: return 'n %d'%len(y)
        w=y.groupby(y.entry.dt.floor('7D')).R.sum(); return 'n %3d R %+.3f t_sett %+.2f'%(len(y),y.R.mean(),w.mean()/w.std()*np.sqrt(len(w)))
    print(f'{lab:52s}| tutto {o(T)} | scelta {o(T[T.entry<"2023"])} | verifica {o(T[T.entry>="2023"])}')
T=book(); st(T,'BASE +24h stop 15% 168h'); yrs=(T.entry.max()-T.entry.min()).days/365.25
print('trade/anno %.0f  sigma_R %.2f  stop %.0f%%  funding medio per trade (short incassa) %+.3f%% = %+.3f R ; trade senza serie di funding: %d'%(len(T)/yrs,T.R.std(),(T.why=='stop').mean()*100,T.fund.mean()*100,T.fund.mean()/0.15,T.nofund.sum()))
print('per anno:',T.groupby(T.entry.dt.year).R.mean().round(3).to_dict())
print('stop saltati (riempiti all\'apertura sopra lo stop): %d ; salto medio %.1f%% ; massimo %.1f%%'%((T.gap>0.001).sum(),T.gap[T.gap>0.001].mean()*100,T.gap.max()*100))
st(book(cm=2),'costi x2'); st(book(off=25),'ritardo +1 barra'); st(book(off=48),'ingresso a +48h')
st(book(sslip=0.01),'slippage stop 100 pb'); st(book(sslip=0.03),'slippage stop 300 pb'); st(book(worst=True),'stop riempito al MASSIMO della barra (estremo)')
st(book(fmult=2.1),'funding x2.1 (livello Hyperliquid, stima)')
x=T.sort_values('R',ascending=False); drop=x.groupby(x.entry.dt.year).head(5).index; st(T.drop(drop),'senza i 5 migliori trade di ogni anno')
st(T[T.R<T.R.quantile(0.99)],'senza l\'1% migliore')
# definizione di quotazione: simboli che non sono monete nuove
def kind(s):
    if re.match(r'^1(000+|M)',s): return 'prefisso 1000/1M'
    return 'altro'
T['kind']=T.sym.map(kind)
# prima candela giornaliera (archivio 1d) contro prima candela oraria
fd=C.apply(lambda s:s.first_valid_index()); T['dgap']=(T.t0.dt.normalize()-T.sym.map(fd)).dt.days
print('\nprima candela 1h vs prima candela 1d dell\'archivio: differenza in giorni !=0 per %d simboli; massimo %s'%((T.dgap!=0).sum(),T.dgap.abs().max()))
print(T[T.dgap!=0][['sym','t0','dgap','R']].head(15).to_string())
st(T[T.dgap==0],'solo simboli con 1h e 1d coerenti')
# monete gia' esistenti a pronti da tempo: spot Binance quotato >30 giorni prima del perp (cache bn_spot_1d / v4_spot_1h se presenti)
import glob,os
sp={}
for p in glob.glob(ROOT+'/data_cache/bn_spot_1d_*USDT.parquet'):
    s=os.path.basename(p)[len('bn_spot_1d_'):-len('.parquet')]
    try: sp[s]=pd.read_parquet(p).index[0]
    except Exception: pass
T['spot0']=T.sym.map(sp); old=T.spot0.notna()&((T.t0-T.spot0).dt.days>30)
print('simboli con spot Binance in cache: %d ; di cui spot piu\' vecchio di 30 giorni: %d'%(T.spot0.notna().sum(),old.sum()))
st(T[old],'perp su monete GIA\' quotate a pronti da >30g'); st(T[~old],'il resto')
st(T[T.kind!='altro'],'prefisso 1000/1M'); 
st(T[T.entry>='2023-06'],'quotazioni dal 2023-06 (campione Hyperliquid)')
med=T.qv24.median(); st(T[T.qv24>=med],'volume 24h sopra la mediana'); st(T[T.qv24<med],'sotto')
A=pd.read_parquet(ROOT+'/research/v5/v5/a6_eventi/_ls_trades.parquet'); print('\nanalista (tenuti, limite 8):',len(A),round(A.R.mean(),3))
m=T.merge(A[['sym','R']],on='sym',suffixes=('','_a')); print('confronto sui comuni: n %d corr %.4f max|diff| %.3f'%(len(m),m.R.corr(m.R_a),(m.R-m.R_a).abs().max()))
T.to_parquet(ROOT+'/research/v5/v5/validazione/c2_trades_binance.parquet')
