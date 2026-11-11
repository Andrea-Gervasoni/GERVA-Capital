"""Il fondo intero: libro giornaliero (4 strategie + DIP-24h + carry 20%) piu' libro dei trade a margine isolato.
Scomposizione del rendimento: singole strategie -> diversificazione -> leva del conto -> libro dei trade. SIMULATO."""
import sys, pickle, warnings; sys.path.insert(0,'/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
P=pd.read_parquet('research/v5/v4/portafogli.parquet'); S=pd.read_parquet('research/v5/series.parquet')
ALL=pickle.load(open('research/v5/v4/_cache/trades.pkl','rb')); sys.path.insert(0,'research/v5/v4'); import leva_trade_isolato as TR
rf=S['RF'].reindex(P.index).fillna(0.0); old=P['0. ATTUALE: 4 sleeve']; new=P['3. 4 sleeve + DIP-24h + CARRY 20%']
def book(key,rc,re):
    X=ALL[key].copy(); X['score']=[TR.CONV[c]['score'].get(pd.Timestamp(d)) for c,d in zip(X.coin,X.entry)]
    r=np.where(X.score>0.75,re,rc); return (pd.Series(r*X.R.values,index=pd.to_datetime(X.exit.values)).groupby(level=0).sum()).reindex(P.index).fillna(0.0)
C=('atr1.0',('alta',),2.0,'long'); A=(0.017,('alta',),None,'long')
def lev(x,L): return L*x-(L-1)*(rf+0.015/365)
def st(x,name):
    def one(y):
        if len(y)<60: return (np.nan,)*4
        e=y-rf.reindex(y.index); eq=(1+y).cumprod(); return (e.mean()/y.std()*np.sqrt(365), eq.iloc[-1]**(365/len(y))-1, y.std()*np.sqrt(365), (eq/eq.cummax()-1).min())
    a,i,o=one(x),one(x[:'2022-12-31']),one(x['2023-01-01':])
    m=(1+x).resample('ME').prod()-1
    return dict(portafoglio=name,sharpe=a[0],sh_scelta=i[0],sh_verifica=o[0],cagr=a[1],cagr_verifica=o[1],vol=a[2],maxdd=a[3],mese_medio=m.mean(),mese_peggiore=m.min(),mesi_ge10=(m>=.10).mean(),mesi_ge20=(m>=.20).mean())
T1=book(C,.005,.01); T2=book(C,.01,.02); T3=book(C,.015,.03); TA=book(A,.005,.01)
rows=[st(old,'A. 4 strategie, senza leva (versione precedente)'),st(lev(old,2),'A2. 4 strategie, leva 2x'),
      st(new,'B. 6 strategie (+DIP +carry), senza leva'),st(lev(new,2),'B2. 6 strategie, leva 2x'),st(lev(new,3),'B3. 6 strategie, leva 3x'),
      st(T2,'T. solo libro dei trade 11x (1% / 2%)'),st(TA,'T30. solo libro dei trade 30x (0,5% / 1%)'),
      st(new+T1,'C1. 6 strategie 1x + trade 11x (0,5% / 1%)'),st(new+T2,'C2. 6 strategie 1x + trade 11x (1% / 2%)'),st(lev(new,2)+T2,'C3. 6 strategie 2x + trade 11x (1% / 2%)'),
      st(lev(new,2)+T3,'C4. 6 strategie 2x + trade 11x (1,5% / 3%)'),st(lev(new,2)+TA,'C5. 6 strategie 2x + trade 30x (0,5% / 1%)'),st(lev(new,3)+T3,'C6. 6 strategie 3x + trade 11x (1,5% / 3%)')]
R=pd.DataFrame(rows).set_index('portafoglio'); pd.set_option('display.width',260); print(R.round(3).to_string())
mm=lambda x:(1+x).resample('ME').prod()-1
print('\ncorrelazione mensile del libro dei trade (11x) con: 6 strategie %.2f, CR-TREND %.2f, CR-XSMOM %.2f'%(mm(T2).corr(mm(new)),mm(T2).corr(mm(S['CR-TREND'].reindex(P.index).fillna(0))),mm(T2).corr(mm(S['CR-XSMOM'].reindex(P.index).fillna(0)))))
# Monte Carlo a blocchi di 30 giorni, 3 anni
rng=np.random.default_rng(3)
def mc(x,scen,n=4000,H=3*365,B=30):
    v=x.values; e=(x-rf).mean(); out=[]
    starts=rng.integers(0,len(v)-B,(n,H//B+1)); 
    for s in starts:
        y=np.concatenate([v[a:a+B] for a in s])[:H].copy()
        if scen=='pessimista': y=y-0.5*e
        if scen=='stress': y=y-(rng.random(H)<0.001)*0.15
        eq=np.cumprod(1+np.maximum(y,-1)); out.append((eq[-1],(eq/np.maximum.accumulate(eq)-1).min(),eq.min()))
    o=np.array(out); cg=o[:,0]**(1/3)-1
    return dict(cagr_p50=np.median(cg),cagr_p05=np.quantile(cg,.05),cagr_p95=np.quantile(cg,.95),dd_p50=np.median(o[:,1]),dd_p95=np.quantile(o[:,1],.05),p_meno30=(o[:,2]<=.7).mean(),p_dimezzato=(o[:,2]<=.5).mean(),mese=(1+np.median(cg))**(1/12)-1)
out=[]
for name,x in {'B. 6 strategie 1x':new,'B2. 6 strategie 2x':lev(new,2),'B3. 6 strategie 3x':lev(new,3),'C2. 1x + trade 1%/2%':new+T2,'C3. 2x + trade 1%/2%':lev(new,2)+T2,'C4. 2x + trade 1,5%/3%':lev(new,2)+T3,'C5. 2x + trade 30x 0,5%/1%':lev(new,2)+TA,'C6. 3x + trade 1,5%/3%':lev(new,3)+T3}.items():
    for sc in ('base','pessimista','stress'):
        o=mc(x,sc); o.update(portafoglio=name,scenario=sc); out.append(o)
M=pd.DataFrame(out).set_index(['portafoglio','scenario']); print('\nMonte Carlo, 3 anni, 4.000 percorsi'); print(M.round(3).to_string())
R.to_csv('research/v5/v4/fondo_statistiche.csv'); M.to_csv('research/v5/v4/fondo_montecarlo.csv')
pd.DataFrame({'old':old,'new':new,'new2x':lev(new,2),'trade11':T2,'trade30':TA,'C3':lev(new,2)+T2,'rf':rf}).to_parquet('research/v5/v4/fondo_serie.parquet')

# ---- CORREZIONE: lo Sharpe giornaliero dei portafogli con il libro dei trade e' gonfiato, perche' il P&L di un trade e' attribuito
# tutto al giorno di uscita e la correlazione giornaliera con il resto risulta 0,16 invece di 0,64 (mensile). Statistiche e Monte Carlo
# corretti si calcolano sui rendimenti MENSILI (blocchi di 3 mesi). Le cadute mensili sottostimano quelle dentro il mese.
print('\n=== STATISTICHE SUI RENDIMENTI MENSILI (quelle da usare) ===')
mrf=mm(rf)
def stm(x,name):
    m=mm(x); e=m-mrf; s=lambda a,b:(e[a:b].mean()/e[a:b].std()*np.sqrt(12))
    eq=(1+m).cumprod()
    return dict(portafoglio=name,sharpe=s(None,None),sh_scelta=s(None,'2022-12-31'),sh_verifica=s('2023-01-01',None),cagr=eq.iloc[-1]**(12/len(m))-1,vol=m.std()*np.sqrt(12),
                maxdd_mensile=(eq/eq.cummax()-1).min(),mese_medio=m.mean(),mese_mediano=m.median(),mese_peggiore=m.min(),mesi_negativi=(m<0).mean(),mesi_ge10=(m>=.1).mean(),mesi_ge20=(m>=.2).mean())
PORT={'A. 4 strategie 1x (versione precedente)':old,'A2. 4 strategie 2x':lev(old,2),'B. 6 strategie 1x':new,'B2. 6 strategie 2x':lev(new,2),'B3. 6 strategie 3x':lev(new,3),
      'T. solo trade 11x (1%/2%)':T2,'T30. solo trade 30x (0,5%/1%)':TA,'C1. 1x + trade 11x (0,5%/1%)':new+T1,'C2. 1x + trade 11x (1%/2%)':new+T2,'C3. 2x + trade 11x (1%/2%)':lev(new,2)+T2,
      'C4. 2x + trade 11x (1,5%/3%)':lev(new,2)+T3,'C5. 2x + trade 30x (0,5%/1%)':lev(new,2)+TA,'C6. 3x + trade 11x (1,5%/3%)':lev(new,3)+T3}
RM=pd.DataFrame([stm(x,n) for n,x in PORT.items()]).set_index('portafoglio'); print(RM.round(3).to_string()); RM.to_csv('research/v5/v4/fondo_statistiche.csv')
rng=np.random.default_rng(4)
def mcm(x,scen,n=5000,H=36,B=3):
    m=mm(x).values; e=(mm(x)-mrf).mean(); out=[]
    for s in rng.integers(0,len(m)-B+1,(n,H//B)):
        y=np.concatenate([m[a:a+B] for a in s]).copy()
        if scen=='pessimista': y=y-0.5*e
        if scen=='stress': y=y-(rng.random(H)<0.03)*0.15                    # un mese su 33 con un -15% in piu'
        eq=np.cumprod(1+np.maximum(y,-1)); out.append((eq[-1],(eq/np.maximum.accumulate(np.maximum(eq,1e-9))-1).min(),eq.min(),(y>=.2).mean(),(y<=-.1).mean()))
    o=np.array(out); cg=o[:,0]**(1/3)-1
    return dict(cagr_p50=np.median(cg),cagr_p05=np.quantile(cg,.05),cagr_p95=np.quantile(cg,.95),dd_p50=np.median(o[:,1]),dd_p95=np.quantile(o[:,1],.05),p_meno30=(o[:,2]<=.7).mean(),p_dimezzato=(o[:,2]<=.5).mean(),
                mese=(1+np.median(cg))**(1/12)-1,p_mese_ge20=o[:,3].mean(),p_mese_le10=o[:,4].mean())
out=[]
for n,x in PORT.items():
    for sc in ('base','pessimista','stress'):
        o=mcm(x,sc); o.update(portafoglio=n,scenario=sc); out.append(o)
MM=pd.DataFrame(out).set_index(['portafoglio','scenario']); print('\nMonte Carlo mensile, 3 anni, 5.000 percorsi, blocchi di 3 mesi'); print(MM.round(3).to_string()); MM.to_csv('research/v5/v4/fondo_montecarlo.csv')
