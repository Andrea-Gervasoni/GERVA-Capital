"""Validazione claim 3 (A1 GQ contro conviction alta, libro 11x): simulatore e indicatore riscritti. SIMULATO.
Solo lo score della conviction e' importato (gerva.ensemble via research/v5/v4/leva_trade_isolato): e' il termine di paragone."""
import sys, warnings; warnings.filterwarnings('ignore')
sys.path.insert(0,'/home/user/GERVA-Capital'); sys.path.insert(0,'/home/user/GERVA-Capital/research/v5/v4')
import numpy as np, pandas as pd, numba as nb
ROOT='/home/user/GERVA-Capital/data_cache/'; COINS=('BTC','ETH','SOL'); SPL=pd.Timestamp('2023-01-01')
import leva_trade_isolato as L0
SCORE={c:L0.CONV[c]['score'] for c in COINS}
def rd(k): return pd.read_parquet(ROOT+k+'.parquet')
def daily(b):
    g=b.groupby(b.index.normalize()); return pd.DataFrame(dict(open=g.open.first(),high=g.high.max(),low=g.low.min(),close=g.close.last(),volume=g.volume.sum()))
SPOT={c:rd(f'bn_spot_5m_{c}USDT') for c in COINS}; PERP={c:rd(f'v5_um_5m_{c}USDT') for c in COINS}
DS={c:daily(SPOT[c]) for c in COINS}
FUND={}
for c in COINS:
    f=rd(f'bn_fund_{c}USDT').iloc[:,0]; FUND[c]=f.groupby(f.index.normalize()).sum()
# ---------- indicatore, riscritto ----------
def ER(lc,n): return (lc-lc.shift(n))/lc.diff().abs().rolling(n).sum()
def TQ(c): lc=np.log(c); return sum(ER(lc,n) for n in (10,30,60,120))/4
def VWM(d):
    tp=(d.high+d.low+d.close)/3; m=d.index.year*100+d.index.month
    vw=(tp*d.volume).groupby(m).cumsum()/d.volume.groupby(m).cumsum(); a=((d.high-d.low)/d.close).rolling(14).mean()
    return ((d.close/vw-1)/a).clip(-3,3)/3
def comps(c,cut=None):
    d=DS[c] if cut is None else DS[c].loc[:cut]; b=DS['BTC'].close if cut is None else DS['BTC'].close.loc[:cut]
    return pd.DataFrame(dict(tq=TQ(d.close)/0.2,btc=TQ(b).reindex(d.index)/0.2,vwm=VWM(d)/0.4))
def GQ(c,use=('tq','btc','vwm'),cut=None): return comps(c,cut)[list(use)].mean(axis=1,skipna=False)
# ---------- simulatore, riscritto ----------
@nb.njit(cache=True)
def run(op,hi,lo,st,en_,entry,exitf,atr,fund,i0,trail,maxhold,cost,delay,fmult):
    out=[]; n=len(st); i=i0
    while i<n-1:
        if not entry[i] or np.isnan(atr[i]) or en_[i]-st[i]<=delay: i+=1; continue
        sd=min(max(atr[i],0.003),0.15); Lv=min(50.0,1/(sd/0.6+0.005)); k0=st[i]+delay; p0=op[k0]; stop=p0*(1-sd); best=p0; liq=p0*(1-(1/Lv-0.005))
        j=i; px=np.nan; why=0
        while True:
            a=k0 if j==i else st[j]
            for k in range(a,en_[j]):
                if lo[k]<=stop:
                    px=min(stop,op[k])*(1-0.0005*cost); why=1
                    if px<=liq: px=liq; why=2
                    break
                if hi[k]>best:
                    best=hi[k]; ns=best*(1-trail*sd)
                    if ns>stop: stop=ns
            if why>0: break
            j+=1
            if j>=n-1 or j-i>=maxhold or exitf[j]:
                jj=min(j,n-1); kk=st[jj]+delay
                if kk>=en_[jj]: kk=st[jj]
                px=op[kk]; break
        nd=max(j-i,1); fu=0.0
        for q in range(i,i+nd): fu+=fund[q]*fmult
        net=max(px/p0-1-2*0.00065*cost-fu,-1/Lv)
        out.append((i,min(j,n-1),sd,net/sd,why)); i=j+1
    return out
def book(sig,exf,bars=SPOT,cost=1.0,delay=0,fmult=1.0):
    out=[]
    for c in COINS:
        b=bars[c]; d=DS[c]; days=d.index
        dn=b.index.normalize().values; st=np.searchsorted(dn,days.values); en_=np.searchsorted(dn,days.values,'right')
        atr=((d.high-d.low)/d.close).rolling(14).mean().shift(1).values
        fu=FUND[c].reindex(days).fillna(0.0003).values
        e=sig[c].reindex(days).fillna(False).values.astype(np.bool_); x=exf[c].reindex(days).fillna(True).values.astype(np.bool_)
        e=e&(en_>st)                       # giorno senza barre (perp non ancora quotato): niente ingresso
        r=run(b.open.values,b.high.values,b.low.values,st,en_,e,x,atr,fu,250,2.0,7,cost,delay,fmult)
        if len(r):
            T=pd.DataFrame(r,columns=['i','j','s','R','why']); T['entry']=days[T.i.values]; T['exit']=days[T.j.values]; T['coin']=c; out.append(T)
    return pd.concat(out,ignore_index=True)
def line(T,lab,ref=None):
    def o(y): return 'n %3d R %+.3f t %+.2f'%(len(y),y.R.mean(),y.R.mean()/y.R.std()*np.sqrt(len(y))) if len(y)>2 else 'n %d'%len(y)
    print(f'{lab:58s}| tutto {o(T)} | scelta {o(T[T.entry<SPL])} | verifica {o(T[T.entry>=SPL])}')
sc={c:SCORE[c].reindex(DS[c].index) for c in COINS}; ok={c:sc[c].notna() for c in COINS}
conv_e={c:(sc[c]>0.60)&ok[c] for c in COINS}; conv_x={c:~(sc[c]>0.30) for c in COINS}
G={c:GQ(c).shift(1) for c in COINS}
# soglie: quantili della scelta ricalcolati
pool=pd.concat([pd.DataFrame(dict(g=G[c],s=sc[c])).iloc[250:].loc[:'2022-12-31'] for c in COINS]).dropna()
p_alta=(pool.s>0.60).mean(); p_bassa=(pool.s<=0.30).mean(); thr=pool.g.quantile(1-p_alta); thb=pool.g.quantile(p_bassa)
print('soglie ricalcolate sulla scelta: quota alta %.3f -> GQ alta %.3f (analista 0.532) ; quota bassa %.3f -> bassa %.3f (analista -0.503) ; corr(GQ,score) %.2f ; sd componenti %s'%(p_alta,thr,p_bassa,thb,pool.g.corr(pool.s),
      pd.concat([comps(c).shift(1).iloc[250:].loc[:'2022-12-31'] for c in COINS]).std().mul([0.2,0.2,0.4]).round(3).to_dict()))
def gqbook(th,g=G,tb=-0.5033858,**k): return book({c:(g[c]>=th)&ok[c] for c in COINS},{c:~(g[c]>tb) for c in COINS},**k)
TC=book(conv_e,conv_x); TG=gqbook(0.5317842685566442)
line(TC,'conviction alta (analista +0.237 / +0.309 / +0.180)'); line(TG,'GQ>=0.53 (analista +0.339 / +0.415 / +0.276)')
A=pd.read_parquet('/home/user/GERVA-Capital/research/v5/v5/a1_indicatore/trades.parquet'); a=A[A.libro.str.startswith('GQ')]
m=TG.merge(a,on=['coin','entry'],how='outer',suffixes=('','_a'),indicator=True); print('confronto con trades.parquet dell\'analista:',m._merge.value_counts().to_dict(),'max|dR| %.4f'%(m.R-m.R_a).abs().max())
yr=pd.DataFrame({'conv':TC.groupby(TC.entry.dt.year).R.agg(['size','mean']).round(2).astype(str).agg(' '.join,axis=1),'gq':TG.groupby(TG.entry.dt.year).R.agg(['size','mean']).round(2).astype(str).agg(' '.join,axis=1)}); print('per anno (n, R):\n',yr.to_string())
print('\n--- troncamento: GQ ricalcolato su dati tagliati a t (ultimo valore) contro la serie intera')
rng=np.random.default_rng(1); bad=0; nn=0; mx=0
for c in COINS:
    g=GQ(c)
    for t in rng.choice(DS[c].index[300:],80,replace=False):
        v=GQ(c,cut=t).iloc[-1]; nn+=1; dv=abs(v-g.loc[t]); mx=max(mx,dv if np.isfinite(dv) else 0); bad+=int(dv>1e-9)
print('confronti %d differenze %d max %.1e ; (VWAP del mese: cumulata dal primo giorno del mese a t, ER: finestre all\'indietro)'%(nn,bad,mx))
print('\n--- sensibilita\' alla soglia'); 
for th in (0.2,0.3,0.4,0.53,0.6,0.7,0.8,0.94,1.1): line(gqbook(th),f'GQ>={th}')
print('\n--- senza una componente (soglie = stessi quantili della scelta, ricalcolati)')
for drop in ('tq','btc','vwm'):
    use=[k for k in ('tq','btc','vwm') if k!=drop]; g={c:GQ(c,use).shift(1) for c in COINS}
    pl=pd.concat([pd.DataFrame(dict(g=g[c],s=sc[c])).iloc[250:].loc[:'2022-12-31'] for c in COINS]).dropna(); t1=pl.g.quantile(1-p_alta); t2=pl.g.quantile(p_bassa)
    line(gqbook(t1,g=g,tb=t2),f'senza {drop} (soglia {t1:.2f})')
for only in ('tq','btc','vwm'):
    g={c:GQ(c,[only]).shift(1) for c in COINS}; pl=pd.concat([pd.DataFrame(dict(g=g[c],s=sc[c])).iloc[250:].loc[:'2022-12-31'] for c in COINS]).dropna()
    line(gqbook(pl.g.quantile(1-p_alta),g=g,tb=pl.g.quantile(p_bassa)),f'solo {only}')
print('\n--- costi x2, ritardo, funding'); 
for lab,k in (('costi x2',dict(cost=2.0)),('ritardo +1 barra',dict(delay=1)),('funding x2.1 (Hyperliquid)',dict(fmult=2.1))):
    line(book(conv_e,conv_x,**k),'conviction | '+lab); line(gqbook(0.5317842685566442,**k),'GQ>=0.53  | '+lab)
print('\n--- percorso PERP 5m (Binance USDT-M), stessi segnali; confronto sullo stesso periodo (ingressi dal 2020-10)')
P0='2020-10-01'
def f(T): return T[T.entry>=P0]
for lab,k in (('',{}),(' + funding x2.1',dict(fmult=2.1)),(' + funding x2.1 + costi x2',dict(fmult=2.1,cost=2.0))):
    line(f(book(conv_e,conv_x,**k)),'SPOT conviction'+lab); line(f(gqbook(0.5317842685566442,**k)),'SPOT GQ>=0.53'+lab)
    line(f(book(conv_e,conv_x,bars=PERP,**k)),'PERP conviction'+lab); line(f(gqbook(0.5317842685566442,bars=PERP,**k)),'PERP GQ>=0.53'+lab)
print('\n--- bootstrap appaiato a blocchi mensili della differenza di R medio (GQ - conviction), verifica; 10000 ricampionamenti')
def boot(Ta,Tb,lab,sl=(SPL,None)):
    def mo(T):
        T=T[T.entry>=sl[0]] if sl[1] is None else T[(T.entry>=sl[0])&(T.entry<sl[1])]; g=T.groupby(T.entry.dt.to_period('M')).R; return g.sum(),g.size()
    sa,na=mo(Ta); sb,nb_=mo(Tb); ix=sa.index.union(sb.index); ix=pd.period_range(ix.min(),ix.max(),freq='M')
    sa,na,sb,nb_=[x.reindex(ix).fillna(0).values for x in (sa,na,sb,nb_)]; r=np.random.default_rng(7); n=len(ix); d=[]
    for _ in range(10000):
        i=r.integers(0,n,n); d.append(sa[i].sum()/max(na[i].sum(),1)-sb[i].sum()/max(nb_[i].sum(),1))
    d=np.array(d); print(f'{lab:44s} diff {sa.sum()/na.sum()-sb.sum()/nb_.sum():+.3f}  IC90 [{np.percentile(d,5):+.3f}, {np.percentile(d,95):+.3f}]  P(>0) {np.mean(d>0):.3f}  mesi {n}')
    # differenza di R TOTALE (non media): quello che conta per il conto
    d2=[]; 
    for _ in range(10000):
        i=r.integers(0,n,n); d2.append(sa[i].sum()-sb[i].sum())
    print(f'{"":44s} diff R totale {sa.sum()-sb.sum():+.1f}  IC90 [{np.percentile(d2,5):+.1f}, {np.percentile(d2,95):+.1f}]  P(>0) {np.mean(np.array(d2)>0):.3f}')
boot(TG,TC,'spot, verifica'); boot(TG,TC,'spot, scelta',(pd.Timestamp('2017-01-01'),SPL))
boot(gqbook(0.5317842685566442,bars=PERP,fmult=2.1),book(conv_e,conv_x,bars=PERP,fmult=2.1),'perp + funding x2.1, verifica')
# trade in comune
k=TG.merge(TC,on=['coin','entry'],how='outer',suffixes=('_g','_c'),indicator=True); v=k[k.entry>=SPL]
print('\nverifica: trade in comune %d (R %+.3f) ; solo GQ %d (R %+.3f) ; solo conviction %d (R %+.3f)'%((v._merge=='both').sum(),v[v._merge=='both'].R_g.mean(),(v._merge=='left_only').sum(),v[v._merge=='left_only'].R_g.mean(),(v._merge=='right_only').sum(),v[v._merge=='right_only'].R_c.mean()))
v2=TG[TG.entry>=SPL]; print('verifica GQ per moneta:',v2.groupby('coin').R.agg(['size','mean']).round(3).to_dict('index'))
print('verifica GQ senza i 5 trade migliori: %+.3f ; conviction: %+.3f'%(v2.R.sort_values()[:-5].mean(),TC[TC.entry>=SPL].R.sort_values()[:-5].mean()))
