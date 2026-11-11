import sys, warnings, concurrent.futures as cf; sys.path.insert(0,'/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, os
from gerva.data import yahoo, Store
D=pd.read_pickle('research/v5/v2/_cache/sec/purchases.pkl').dropna(subset=['FILING_DATE','ISSUERTRADINGSYMBOL'])
D['tk']=D.ISSUERTRADINGSYMBOL.str.upper().str.strip().str.replace('.','-',regex=False)
D=D[D.tk.str.fullmatch(r'[A-Z\-]{1,6}')]
csu=D.title.fillna('').str.contains(r'CEO|Chief Executive|CFO|Chief Financial|COO|Chief Operating|President|Chair',case=False,regex=True)
nown=D.groupby(['tk','FILING_DATE']).owner.transform('nunique')
print('acquisti totali',len(D),'| >=100k',int((D.val>=1e5).sum()),'| C-suite >=100k',int(((D.val>=1e5)&csu).sum()))
E=D[(D.val>=1e5)&csu&(nown<4)].groupby(['tk','FILING_DATE']).val.sum().reset_index()
E=E[E.FILING_DATE>='2016-01-01']; print('segnali (ticker-giorno) dopo il filtro lotti:',len(E),'ticker unici',E.tk.nunique())
os.makedirs('research/v5/v2/_cache/sec/px',exist_ok=True)
def get(t):
    p=f'research/v5/v2/_cache/sec/px/{t}.pkl'
    if os.path.exists(p): return t,pd.read_pickle(p)
    try: d=yahoo(t)
    except Exception: d=None
    pd.to_pickle(d,p); return t,d
with cf.ThreadPoolExecutor(6) as ex: PX=dict(ex.map(get,sorted(E.tk.unique())))
miss=[t for t,d in PX.items() if d is None or len(d)<30]
print('ticker senza prezzi (delistati o altro):',len(miss),'=',round(len(miss)/len(PX),3))
spy=yahoo('SPY')
rows=[]; unpriced=0
for tk,fd,val in E.itertuples(index=False):
    d=PX.get(tk)
    if d is None or len(d)<30: unpriced+=1; continue
    i=d.index.searchsorted(fd,side='right')            # prima seduta DOPO il deposito
    if i<21 or i+5>=len(d): unpriced+=(i+5>=len(d) and fd<pd.Timestamp('2026-03-01')); continue
    h=d.iloc[i-20:i]; adv=(h.close*h.volume).mean()
    if not adv>=20e6: continue
    pc=d.close.shift(1); trng=pd.concat([d.high-d.low,(d.high-pc).abs(),(d.low-pc).abs()],axis=1).max(axis=1)
    atr=trng.iloc[i-14:i].mean(); entry=d.open.iloc[i]; stop=entry-2*atr
    if not (entry>0 and atr>0 and stop>0): continue
    exit_px=d.close.iloc[i+4]; stopped=False
    for k in range(i,i+5):
        if d.open.iloc[k]<=stop and k>i: exit_px=d.open.iloc[k]; stopped=True; j=k; break
        if d.low.iloc[k]<=stop: exit_px=stop; stopped=True; j=k; break
    else: j=i+4
    r=exit_px/entry-1-0.002
    si=spy.index.searchsorted(d.index[i]); sr=spy.close.iloc[min(si+4,len(spy)-1)]/spy.open.iloc[si]-1 if si<len(spy) else np.nan
    rows.append(dict(tk=tk,filed=fd,entry_day=d.index[i],exit_day=d.index[j],entry=entry,stop_dist=2*atr/entry,ret=r,spy=sr,stopped=stopped,R=r/(2*atr/entry),val=val))
T=pd.DataFrame(rows).sort_values('entry_day'); T.to_pickle('research/v5/v2/_cache/sec/trades.pkl')
print('segnali non prezzabili',unpriced,'| operazioni dopo filtro liquidita',len(T))
HO=T.entry_day.max()-pd.Timedelta(days=365)
def rep(x,lab):
    t=x.ret.mean()/x.ret.std()*np.sqrt(len(x)); ex=(x.ret-x.spy)
    print(f"{lab}: n={len(x)} media={x.ret.mean()*1e4:.0f}pb (t={t:.2f}) mediana={x.ret.median()*1e4:.0f}pb vincenti={(x.ret>0).mean():.1%} vincita media={x.ret[x.ret>0].mean():.2%} perdita media={x.ret[x.ret<=0].mean():.2%} | SPY stessi giorni {x.spy.mean()*1e4:.0f}pb | eccesso {ex.mean()*1e4:.0f}pb (t={ex.mean()/ex.std()*np.sqrt(len(x)):.2f}) | fermati dallo stop {x.stopped.mean():.1%} | R medio {x.R.mean():.3f}")
rep(T,'TUTTO'); rep(T[T.entry_day<=HO],'costruzione'); rep(T[T.entry_day>HO],'ultimi 12 mesi (holdout)')
for y,g in T.groupby(T.entry_day.dt.year): print(y, len(g), f"{g.ret.mean()*1e4:.0f}pb", f"eccesso {(g.ret-g.spy).mean()*1e4:.0f}pb", f"vincenti {(g.ret>0).mean():.0%}")
# portafoglio: 1% di rischio per operazione, max 5 posizioni, max 10% per posizione
days=pd.bdate_range(T.entry_day.min(),T.exit_day.max()); eq=1.0; open_=[]; curve=[]; taken=0; skipped=0
byday={d:g for d,g in T.groupby('entry_day')}
for d in days:
    for p in [p for p in open_ if p[0]<=d]: eq+=p[1]; open_.remove(p)
    for r in (byday[d].itertuples() if d in byday else []):
        if len(open_)>=5: skipped+=1; continue
        size=min(0.01/r.stop_dist,0.10)*eq; open_.append((r.exit_day,size*r.ret)); taken+=1
    curve.append(eq)
c=pd.Series(curve,index=days); yrs=len(c)/252; dr=c.pct_change().dropna()
print(f"PORTAFOGLIO: operazioni prese {taken}, saltate per limite {skipped}, CAGR {c.iloc[-1]**(1/yrs)-1:.2%}, vol {dr.std()*np.sqrt(252):.2%}, caduta massima {(c/c.cummax()-1).min():.2%}, esposizione media stimata {min(0.10,0.01/T.stop_dist.median())*taken*5/len(days):.0%}")
s=spy.close.reindex(days).ffill(); print(f"SPY stesso periodo: CAGR {(s.iloc[-1]/s.iloc[0])**(1/yrs)-1:.2%}")
