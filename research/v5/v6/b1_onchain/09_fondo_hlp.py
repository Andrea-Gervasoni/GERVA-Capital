"""Cassa ferma (40% del capitale) in HLP invece che in T-bill: effetto sul fondo. Bootstrap a blocchi mensili, con scenario di coda esplicito."""
import numpy as np, pandas as pd
from comune import *
pd.set_option('display.width',250)
h=pd.read_parquet('returns_hlp.parquet')['HLP']; F=fondo(); tb=tbill()
ix=h.index.intersection(F.index); h=h[ix]; t=tb.reindex(ix).ffill(); F=F.loc[ix]
print('periodo comune',ix[0].date(),ix[-1].date(),len(ix),'giorni')
def m(x): return (1+x).resample('ME').prod()-1
def riga(lab,x):
    mm=m(x); eq=(1+x).cumprod(); ex=m(x-t)
    print(f"{lab:46s} CAGR={eq.iloc[-1]**(365.25/len(x))-1:+.3f} vol mens.={mm.std()*np.sqrt(12):.3f} Sharpe mens. (ecc. T-bill)={ex.mean()/ex.std()*np.sqrt(12):+.2f} maxDD={(eq/eq.cummax()-1).min():.3f} mese medio={mm.mean():+.4f}")
riga('HLP da solo',h); riga('T-bill',t)
for c in F.columns:
    riga(c,F[c]); riga(c+' + 40% (HLP - Tbill)',F[c]+0.4*(h-t))
    for lab,a,b in [('2023-06..2024-12','2023-06-01','2024-12-31'),('2025-01..2026-10','2025-01-01','2026-12-31')]:
        x=(0.4*(h-t))[a:b]; print(f"      di cui {lab}: contributo annuo {x.mean()*365.25:+.4f}")
# ultimi 12 mesi = stima prudente del regime attuale (TVL 150-500M)
l=h[h.index>h.index[-1]-pd.Timedelta(days=365)]; lt=t.reindex(l.index); print(f"\nultimi 12 mesi: HLP {((1+l).prod()-1):+.4f}, T-bill {((1+lt).prod()-1):+.4f}, eccesso {((1+l).prod()-(1+lt).prod()):+.4f}; contributo al fondo con il 40%: {0.4*((1+l).prod()-(1+lt).prod()):+.4f}/anno")
# bootstrap mensile sul regime 2025-2026 (22 mesi), 3 anni, con e senza coda
mm=m(h['2025-01-01':]).iloc[:-1].values; rng=np.random.default_rng(11); N=20000
def sim(scale,ptail,loss):
    out=[];dd=[]
    for _ in range(N):
        r=rng.choice(mm,36)*scale; hit=rng.random(36)<ptail; r=np.where(hit,(1+r)*(1-loss)-1,r); eq=np.cumprod(1+r); out.append(eq[-1]**(1/36)-1); dd.append((eq/np.maximum.accumulate(eq)).min()-1)
    out=np.array(out);dd=np.array(dd); return out.mean(),np.percentile(out,5),(dd<=-.5).mean(),(dd<=-.2).mean(),np.median(dd)
print('\nbootstrap 3 anni, mesi 2025-01..2026-10 di HLP (leva 1: un deposito non si puo\' mettere a leva):')
for lab,sc,pt,ls in [('base (storia 2025-26, nessuna coda)',1,0,0),('meta\' rendimento',.5,0,0),('base + coda: 3%/anno di probabilita\' di perdere il 50% (exploit/bridge/manipolazione)',1,.03/12,.5),('meta\' + coda 3%/anno x -50%',.5,.03/12,.5),('base + coda 10%/anno x -30%',1,.10/12,.3)]:
    a,b,c,d,e=sim(sc,pt,ls); print(f"  {lab:86s} mese composto medio={a:+.4f} (5° pct {b:+.4f}) P(DD<=-50%)={c:.3f} P(DD<=-20%)={d:.3f} DD mediano={e:.3f}")
print('  NB: le probabilita\' di coda sono IPOTESI dichiarate, non stime: 3,5 anni di storia non contengono una perdita > 6%.')
# returns.parquet richiesto dal brief
pd.DataFrame({'HLP_deposito':h,'HLP_meno_tbill_x0.4':0.4*(h-t)}).to_parquet('returns.parquet'); print('salvato returns.parquet')
