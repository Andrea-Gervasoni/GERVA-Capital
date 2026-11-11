"""A7 parte 1b - regole di sizing a confronto: bootstrap a blocchi di mesi (1 e 3 anni; base / meta' vantaggio / sola verifica)
e frontiere crescita-rischio (stesso rischio, quale regola cresce di piu'?). Tutti i parametri (Kelly, pesi di cella) sono stimati sulla SCELTA. SIMULATO."""
import lib,numpy as np,pandas as pd,pickle,json,sys
from multiprocessing import Pool
pd.set_option('display.width',260,'display.max_rows',2000,'display.max_columns',40)
P=pickle.load(open(lib.HERE+'pesi.pkl','rb')); D=P['D']; WC=P['W']; U=pd.read_csv(lib.HERE+'kelly_incertezza.csv').set_index(['flusso','stima_su'])
def weights(n,fam):
    X=D[n]
    if fam=='piatto': return np.ones(len(X))
    if fam=='livelli_v4': return np.where(X.score>0.75,2.,1.)
    if fam=='solo_ecc': return np.where(X.score>0.80,1.,0.)
    if fam=='no_0.67': return np.where(X.score>0.70,1.,0.)
    w=WC[n][fam].astype(float); return w/max(w.mean(),1e-12)
KS={}
def ksel(n,fam):
    if (n,fam) not in KS: KS[(n,fam)]=lib.kelly_coh(lib.scen(D[n].assign(w=weights(n,fam)),'scelta'),None if fam=='piatto' else lib.scen(D[n].assign(w=weights(n,fam)),'scelta').w.values)[0]
    return KS[(n,fam)]
_T={}
def job(a):
    n,fam,sc,base,dyn,years,npaths,label=a
    key=(n,fam,sc)
    if key not in _T:
        Y=lib.scen(D[n].assign(w=weights(n,fam)),sc); _T[key]=lib.tensors(Y,Y.w.values)
    o=lib.sim(_T[key],base,years=years,n=npaths,dyn=dyn); o.update(flusso=n,regola=label,scenario=sc,anni=years,r_base=base); return o
DYN={'dd10 x0.5':dict(kind='dd',x=.10,f=.5),'dd20 x0.5':dict(kind='dd',x=.20,f=.5),'dd30 x0.5':dict(kind='dd',x=.30,f=.5),'dd20 x0.25':dict(kind='dd',x=.20,f=.25),
     'dd20 x0.5 isteresi':dict(kind='dd',x=.20,f=.5,rec=.5),'pavimento -30%':dict(kind='floor',x=.30,kmin=0.1),'pavimento -50%':dict(kind='floor',x=.50,kmin=0.1),
     'anti-mart x1.5 max3':dict(kind='anti',up=1.5,kmax=3.),'anti-mart x1.25 max2':dict(kind='anti',up=1.25,kmax=2.),'martingala x1.5 max3':dict(kind='mart',up=1.5,kmax=3.),
     'dopo 3 perdite x0.5':dict(kind='streak',nL=3,f=.5)}
FAMS=['piatto','livelli_v4','score','vol','score_vol','moneta','solo_ecc','no_0.67']
if __name__=='__main__':
    jobs=[]; SC=('base','mezzo','verifica')
    for n in ('A30','C11'):
        kf=ksel(n,'piatto'); rules=[]
        for r in (.0025,.005,.01,.02,.03,.05): rules.append(('fisso %.2f%%'%(100*r),'piatto',r,None))
        for f in (1,.5,.25): rules.append(('Kelly(scelta) x%.2f'%f,'piatto',kf*f,None))
        rules+= [('Kelly -1SE','piatto',U.loc[(n,'scelta'),'r_meno1se'],None),('Kelly max p25','piatto',U.loc[(n,'scelta'),'r_maxp25'],None),('Kelly max p10','piatto',U.loc[(n,'scelta'),'r_maxp10'],None)]
        rules.append(('livelli v4 (%s)'%('1%/2%' if n=='C11' else '0.5%/1%'),'livelli_v4',0.01 if n=='C11' else 0.005,None))
        for fam in FAMS[1:]:
            for f in (.5,.25): rules.append((f'{fam} Kelly x{f}',fam,ksel(n,fam)*f,None))
        for dn,dy in DYN.items(): rules.append((f'1/2 Kelly + {dn}','piatto',kf*.5,dy))
        for lab,fam,b,dy in rules:
            for sc in SC:
                for yrs in (1,3): jobs.append((n,fam,sc,b,dy,yrs,4000,lab))
    with Pool(4) as p: res=p.map(job,jobs,chunksize=8)
    R=pd.DataFrame(res); R.to_csv(lib.HERE+'regole.csv',index=False)
    print('Kelly (scelta) per famiglia di pesi [rischio per trade di peso medio 1]:',{k:round(v,4) for k,v in KS.items()})
    cols=['r_base','cagr_p50','cagr_p05','mese_p50','dd_p50','dd_p95','p_dd50','p_meta','p_rovina']
    print("Colonne: r_base rischio per trade; cagr mediano e 5o percentile; mese = mediana mensilizzata; dd mediano e 95o percentile; p_dd50 = P(drawdown >=50% dal massimo); p_meta = P(capitale <= 50% dell'iniziale); p_rovina = P(<=10%).")
    for n in ('A30','C11'):
        for yrs in (3,1):
            for sc in SC:
                print(f'\n##### {n} | {yrs} anni | scenario {sc}')
                x=R[(R.flusso==n)&(R.anni==yrs)&(R.scenario==sc)].set_index('regola')[cols]; print(x.round(3).to_string())
    # ---------- frontiere ----------
    MULT=[.05,.1,.15,.2,.3,.4,.5,.65,.8,1.,1.3,1.7,2.2,3.0]; jobs=[]
    for n in ('A30','C11'):
        kf=ksel(n,'piatto')
        for fam in FAMS:
            for m in MULT:
                for sc in SC: jobs.append((n,fam,sc,ksel(n,fam)*m,None,3,6000,f'{fam}|{m}'))
        for dn,dy in DYN.items():
            for m in MULT:
                for sc in SC: jobs.append((n,'piatto',sc,kf*m,dy,3,6000,f'piatto + {dn}|{m}'))
    with Pool(4) as p: res=p.map(job,jobs,chunksize=8)
    F=pd.DataFrame(res); F[['famiglia','mult']]=F.regola.str.split('|',expand=True); F['mult']=F.mult.astype(float); F.to_csv(lib.HERE+'frontiere.csv',index=False)
    print('\n'+'='*20,'FRONTIERE (3 anni): rendimento mensile mediano ottenibile a parita\' di rischio','='*20)
    print("m@p = mensile mediano al livello di rischio in cui P(drawdown>=50% in 3 anni) = p (interpolato); max = massimo mensile mediano sulla griglia e moltiplicatore del Kelly(scelta) a cui si ottiene.")
    def interp(g,target,col='p_dd50'):
        g=g.sort_values('mult'); x=g[col].values; y=g.mese_p50.values; m=g.mult.values
        # limita al tratto crescente fino al massimo della crescita
        im=y.argmax(); x=x[:im+1]; y=y[:im+1]; m=m[:im+1]
        if x.max()<target: return y[-1],m[-1],True
        j=np.argmax(x>=target)
        if j==0: return y[0]*target/max(x[0],1e-9),m[0]*target/max(x[0],1e-9),False
        w=(target-x[j-1])/max(x[j]-x[j-1],1e-12); return y[j-1]+w*(y[j]-y[j-1]),m[j-1]+w*(m[j]-m[j-1]),False
    rows=[]
    for (n,sc,fam),g in F.groupby(['flusso','scenario','famiglia'],sort=False):
        d=dict(flusso=n,scenario=sc,regola=fam)
        for p in (.01,.05,.10,.25):
            v,m,capped=interp(g,p); d['m@%d%%'%(100*p)]=v; d['r@%d%%'%(100*p)]=m*(ksel(n,fam.split(' + ')[0]))
        v,m,_=interp(g,.30,'dd_p95'); d['m@dd95=30%']=v
        gg=g.sort_values('mult'); i=gg.mese_p50.values.argmax(); d['max_mese']=gg.mese_p50.values[i]; d['mult_max']=gg.mult.values[i]; d['p_dd50_al_max']=gg.p_dd50.values[i]; d['dd95_al_max']=gg.dd_p95.values[i]
        rows.append(d)
    FR=pd.DataFrame(rows); FR.to_csv(lib.HERE+'frontiere_sintesi.csv',index=False)
    for n in ('A30','C11'):
        for sc in SC:
            print(f'\n##### {n} | scenario {sc}'); print(FR[(FR.flusso==n)&(FR.scenario==sc)].drop(columns=['flusso','scenario']).set_index('regola').round(4).to_string())
    ntr=len(set((j[0],j[1],str(j[4]),round(j[3],6)) for j in jobs))+ (R.groupby(['flusso','regola']).ngroups)
    json.dump(dict(trials=int(ntr)),open(lib.HERE+'trials_02.json','w')); print('\nvarianti di sizing valutate in questo script:',ntr)
