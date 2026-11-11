"""A7 - candidati finali: pesi per conviction (stimati sulla scelta) + pavimento sul drawdown (regola di Grossman-Zhou: rischio proporzionale alla distanza dal pavimento).
(1) frontiera bootstrap; (2) seconda derivazione: percorso storico cronologico reale (P&L al giorno di uscita, stato di drawdown calcolato solo su trade gia' chiusi);
(3) sensibilita' del Kelly al raggruppamento dei trade simultanei (giorno / settimana). Scrive returns.parquet e trades.parquet. SIMULATO."""
import lib,numpy as np,pandas as pd,pickle,json
from multiprocessing import Pool
pd.set_option('display.width',260,'display.max_rows',2000,'display.max_columns',40)
P=pickle.load(open(lib.HERE+'pesi.pkl','rb')); D=P['D']; WC=P['W']
def W(n,fam):
    X=D[n]
    if fam=='piatto': return np.ones(len(X))
    if fam=='livelli_v4': return np.where(X.score>0.75,2.,1.)
    w=WC[n][fam].astype(float); return w/w.mean()
CAND={'A30 piatto':('A30','piatto',None),'A30 score':('A30','score',None),'A30 score + pavimento -30%':('A30','score',dict(kind='floor',x=.30,kmin=.1)),'A30 score + pavimento -50%':('A30','score',dict(kind='floor',x=.50,kmin=.1)),
      'C11 piatto':('C11','piatto',None),'C11 livelli_v4':('C11','livelli_v4',None),'C11 livelli_v4 + pavimento -30%':('C11','livelli_v4',dict(kind='floor',x=.30,kmin=.1)),'C11 livelli_v4 + pavimento -50%':('C11','livelli_v4',dict(kind='floor',x=.50,kmin=.1))}
GRID={'A30':[.0025,.005,.0075,.01,.015,.02,.03,.04,.06],'C11':[.005,.01,.015,.02,.03,.04,.06,.08,.12]}
_T={}
def job(a):
    c,sc,r,yrs=a; n,fam,dyn=CAND[c]
    if (n,fam,sc) not in _T: Y=lib.scen(D[n].assign(w=W(n,fam)),sc); _T[(n,fam,sc)]=lib.tensors(Y,Y.w.values)
    o=lib.sim(_T[(n,fam,sc)],r,years=yrs,n=6000,seed=33,dyn=dyn); o.update(candidato=c,scenario=sc,anni=yrs,r=r); return o
def chrono(X,w,r,dyn=None):
    """percorso storico: ogni trade rischia r*w*k del capitale corrente all'ingresso; k dal drawdown del capitale REALIZZATO (solo trade chiusi prima dell'ingresso). P&L al giorno di uscita."""
    X=X.assign(w=w).sort_values(['entry','coin']).reset_index(drop=True); days=pd.date_range(X.entry.min(),X.exit.max(),freq='D'); pnl=pd.Series(0.,index=days)
    eq=1.; pk=1.; openp=[]; ev=sorted(set(X.entry)|set(X.exit)); byentry=dict(tuple(X.groupby('entry'))); out=[]
    for d in ev:
        closed=[p for p in openp if p[0]<=d]; openp=[p for p in openp if p[0]>d]
        if closed:
            tot=sum(p[1] for p in closed); pnl[d]+=tot/eq; eq+=tot; eq=max(eq,1e-9); pk=max(pk,eq)
        if d in byentry:
            dd=eq/pk-1; k=float(np.clip(1+dd/dyn['x'],dyn.get('kmin',0),1)) if dyn else 1.
            g=byentry[d]; ri=r*k*g.w.values; used=sum(p[2] for p in openp); mg=(ri*g.cap.values).sum()
            if used+mg>0.999: ri=ri*max(0.999-used,0)/max(mg,1e-12)
            for (_,t),x in zip(g.iterrows(),ri): openp.append((t.exit,eq*x*t.R,x*t.cap)); out.append(x)
    return pnl,np.array(out)
def st(x):
    eq=(1+x).cumprod(); y=len(x)/365.25; m=(1+x).resample('ME').prod()-1
    return dict(cagr=eq.iloc[-1]**(1/y)-1,mese_medio=m.mean(),mese_mediano=m.median(),maxdd=(eq/eq.cummax()-1).min(),sharpe=x.mean()/x.std()*np.sqrt(365),mesi_ge30=(m>=.3).mean(),peggior_mese=m.min())
if __name__=='__main__':
    SC=('base','mezzo','verifica'); jobs=[(c,sc,r,y) for c in CAND for sc in SC for r in GRID[c[:3]] for y in (3,1)]
    with Pool(4) as p: res=p.map(job,jobs,chunksize=4)
    R=pd.DataFrame(res); R.to_csv(lib.HERE+'candidati_scan.csv',index=False); cols=['r','mese_p50','cagr_p50','cagr_p05','dd_p50','dd_p95','p_dd50','p_meta','p_rovina']
    print('='*15,'(1) BOOTSTRAP 3 ANNI: r = rischio per trade di peso medio 1','='*15)
    for c in CAND:
        for sc in SC: print(f'\n##### {c} | {sc}'); print(R[(R.candidato==c)&(R.scenario==sc)&(R.anni==3)][cols].round(3).to_string(index=False))
    print('\n'+'='*15,'SINTESI: miglior mensile mediano con dd_p95 <= 35% / 50% e con P(capitale dimezzato) <= 5% (3 anni)','='*15)
    rows=[]
    for c in CAND:
        for sc in SC:
            g=R[(R.candidato==c)&(R.scenario==sc)&(R.anni==3)]; d=dict(candidato=c,scenario=sc)
            for lab,mask in (('dd95<=35%',g.dd_p95<=.35),('dd95<=50%',g.dd_p95<=.50),('P(meta)<=5%',g.p_meta<=.05),('P(dd50)<=5%',g.p_dd50<=.05)):
                h=g[mask]; b=h.loc[h.mese_p50.idxmax()] if len(h) else None; d[lab]=np.nan if b is None else b.mese_p50; d['r '+lab]=np.nan if b is None else b.r
            rows.append(d)
    print(pd.DataFrame(rows).round(4).to_string(index=False))
    print('\n'+'='*15,'(2) PERCORSO STORICO CRONOLOGICO (seconda derivazione, senza ricampionamento)','='*15)
    RET={}; rows=[]
    for c,r in (('A30 piatto',.005),('A30 score',.005),('A30 score + pavimento -30%',.015),('C11 piatto',.01),('C11 livelli_v4',.01),('C11 livelli_v4 + pavimento -30%',.03),('C11 livelli_v4 + pavimento -30%',.04)):
        n,fam,dyn=CAND[c]; x,ri=chrono(D[n],W(n,fam),r,dyn); key=f'{c} @ r={r:.3f}'; RET[key]=x
        for lab,y in (('intero',x),('scelta',x[:'2022-12-31']),('verifica',x['2023-01-01':])): d=st(y); d.update(candidato=key,periodo=lab,rischio_medio_effettivo=ri.mean()); rows.append(d)
    Z=pd.DataFrame(rows).set_index(['candidato','periodo']); print(Z.round(3).to_string())
    pd.DataFrame(RET).to_parquet(lib.HERE+'returns.parquet')
    TR=pd.concat([D[n].assign(flusso=n,symbol=D[n].coin+'USDT perp',side='long',stop_distance=D[n].s,leverage=D[n].L,peso_score=W(n,'score'),peso_livelli_v4=W(n,'livelli_v4'))[['flusso','entry','exit','symbol','side','stop_distance','leverage','R','why','score','atr','peso_score','peso_livelli_v4']] for n in ('A30','C11')])
    TR.to_parquet(lib.HERE+'trades.parquet')
    print('\n'+'='*15,'(3) KELLY E RAGGRUPPAMENTO DEI TRADE SIMULTANEI (i trade durano fino a 7 giorni e si sovrappongono)','='*15)
    for n in ('A30','C11'):
        for sc in ('base','scelta','verifica'):
            Y=lib.scen(D[n],sc); y=lib.years_of(Y); out=[]
            for lab,key in (('sequenziale',np.arange(len(Y))),('stesso giorno',Y.entry.values),('stessa settimana',Y.entry.dt.to_period('W').astype(str).values)):
                g=pd.DataFrame(dict(k=key,x=Y.R.values,m=Y.cap.values)).groupby('k').sum(); hi=0.999/g.m.max()
                from scipy.optimize import minimize_scalar
                o=minimize_scalar(lambda r:-np.sum(np.log1p(r*g.x.values)),bounds=(0,hi),method='bounded'); out.append(f'{lab}: r*={o.x:.4f} g={-o.fun/y:.3f}/anno ({np.expm1(-o.fun/y/12)*100:.1f}%/mese)')
            print(n,sc,' | '.join(out))
    json.dump(dict(trials=len(CAND)*9),open(lib.HERE+'trials_06.json','w'))
