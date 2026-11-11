"""Sintesi della quinta tornata: il fondo con le correzioni dell'analista A10 (debito vero, trade valutati ogni giorno, limiti del
libro) piu' i due flussi nuovi sopravvissuti (A5 indici a leva, A6 short delle nuove quotazioni). SIMULATO. Statistiche mensili.
Il flusso A6 NON e' ancora dimostrato eseguibile da un residente italiano: e' riportato a parte."""
import numpy as np, pandas as pd
A10=pd.read_parquet('research/v5/v5/a10_sistema/returns.parquet'); A5=pd.read_parquet('research/v5/v5/a5_indici/returns.parquet'); A6=pd.read_parquet('research/v5/v5/a6_eventi/returns.parquet')
F=pd.read_parquet('research/v5/v4/fondo_serie.parquet'); rf=F.rf
idx=A10.index; a5=A5['A5_flusso_r1%'].reindex(idx).fillna(0); a6=A6['LISTING-SHORT_r0.5%'].reindex(idx).fillna(0)
mm=lambda x:(1+x).resample('ME').prod()-1; mrf=mm(rf.reindex(idx).fillna(0))
def st(x,name,start=None):
    x=x[start:] if start else x; m=mm(x); e=m-mrf.reindex(m.index); s=lambda a,b:(e[a:b].mean()/e[a:b].std()*np.sqrt(12)) if len(e[a:b])>6 else np.nan
    eq=(1+m).cumprod(); d=(1+x).cumprod()
    return dict(portafoglio=name,sharpe=s(None,None),sh_scelta=s(None,'2022-12-31'),sh_verifica=s('2023-01-01',None),cagr=eq.iloc[-1]**(12/len(m))-1,cagr_verifica=(1+m['2023-01-01':]).prod()**(12/len(m['2023-01-01':]))-1,
                vol=m.std()*np.sqrt(12),maxdd_giornaliero=(d/d.cummax()-1).min(),mese_medio=m.mean(),mese_mediano=m.median(),mese_peggiore=m.min(),mesi_ge10=(m>=.1).mean(),mesi_ge20=(m>=.2).mean(),mesi_ge30=(m>=.3).mean())
P={'B. libro giornaliero 1x, cassa remunerata':A10['B_cassa_in_tbill'],'B2. libro giornaliero 2x, debito vero':A10['B2_debito_reale'],
   'C1. prudente (corretto)':A10['C1_mtm_limiti'],'C3. massimo (corretto)':A10['C3_mtm_limiti_debito_reale'],'C3 con il motore di rischio di oggi':A10['C3_motore_di_rischio_attuale'],
   'D1. C1 + indici a leva (rischio 1%)':A10['C1_mtm_limiti']+a5,'D3. C3 + indici a leva (rischio 1%)':A10['C3_mtm_limiti_debito_reale']+a5,'D3b. C3 + indici a leva (rischio 2%)':A10['C3_mtm_limiti_debito_reale']+2*a5,
   'E3. D3 + short nuove quotazioni 0,5% (NON verificato eseguibile)':A10['C3_mtm_limiti_debito_reale']+a5+a6,'E3b. D3b + short nuove quotazioni 1% (NON verificato eseguibile)':A10['C3_mtm_limiti_debito_reale']+2*a5+2*a6}
R=pd.DataFrame([st(x,n) for n,x in P.items()]).set_index('portafoglio'); pd.set_option('display.width',260); print('Dal 2018-04'); print(R.round(3).to_string())
R2=pd.DataFrame([st(x,n,'2020-01-01') for n,x in P.items()]).set_index('portafoglio'); print('\nDal 2020-01 (da quando esiste il flusso delle nuove quotazioni)'); print(R2.round(3).to_string())
print('\ncorrelazioni mensili:', {k:round(mm(a).corr(mm(b)),2) for k,(a,b) in {'indici/trade crypto':(a5,A10['trade11_mtm']),'indici/libro giornaliero':(a5,A10['B_pubblicato']),'quotazioni/trade crypto':(a6['2020':],A10['trade11_mtm']['2020':]),'quotazioni/indici':(a6['2020':],a5['2020':])}.items()})
rng=np.random.default_rng(9)
def mc(x,scen,n=5000,H=36,B=3):
    m=mm(x).values; e=(mm(x)-mrf.reindex(mm(x).index)).mean(); out=[]
    for s in rng.integers(0,len(m)-B+1,(n,H//B)):
        y=np.concatenate([m[a:a+B] for a in s]).copy()
        if scen=='meta_vantaggio': y=y-0.5*e
        eq=np.cumprod(1+np.maximum(y,-1)); out.append((eq[-1],(eq/np.maximum.accumulate(np.maximum(eq,1e-9))-1).min(),eq.min()))
    o=np.array(out); cg=o[:,0]**(1/3)-1
    return dict(mese_composto_p50=(1+np.median(cg))**(1/12)-1,cagr_p50=np.median(cg),cagr_p05=np.quantile(cg,.05),dd_p50=np.median(o[:,1]),dd_p95=np.quantile(o[:,1],.05),p_dd50=(o[:,1]<=-.5).mean(),p_dimezzato=(o[:,2]<=.5).mean())
out=[]
for n,x in P.items():
    for sc in ('base','meta_vantaggio'):
        o=mc(x,sc); o.update(portafoglio=n,scenario=sc); out.append(o)
M=pd.DataFrame(out).set_index(['portafoglio','scenario']); print('\nMonte Carlo mensile (cadute mensili: quelle giornaliere sono piu profonde di circa un terzo), 3 anni'); print(M.round(3).to_string())
R.to_csv('research/v5/v5/sintesi/statistiche.csv'); M.to_csv('research/v5/v5/sintesi/montecarlo.csv')
