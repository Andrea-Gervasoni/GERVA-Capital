"""A7 parte 2c - il massimo rendimento mensile che i vantaggi MISURATI sostengono a un dato rischio, e il prezzo di 10/20/30% al mese. SIMULATO.
Bootstrap a blocchi di mesi, 8000 percorsi, 3 anni (e 1 anno). Scenari: base (intero campione), mezzo (meta' vantaggio), verifica (solo >= 2023).
Flussi: A30 (stop 1,7%, 30x, Hyperliquid), C11 (stop 1xATR, ~11x; 10x su venue UE), C11 a livelli v4 (peso 2 sugli eccezionali),
FONDO = serie giornaliera 'C3' della v4 (6 strategie 2x + trade 11x 1%/2%) moltiplicata per k (STIMA: scala lineare, ignora limiti di margine e costo del capitale)."""
import lib,numpy as np,pandas as pd,pickle,json
from multiprocessing import Pool
pd.set_option('display.width',260,'display.max_rows',2000,'display.max_columns',40)
P=pickle.load(open(lib.HERE+'pesi.pkl','rb')); D=P['D']
F=pd.read_parquet('/home/user/GERVA-Capital/research/v5/v4/fondo_serie.parquet')
def fund_tensors(sc,col='C3'):
    x=F[col].copy()
    if sc=='mezzo': x=x-0.5*x.mean()
    if sc=='verifica': x=x[x.index>='2023-01-01']
    g=[v.values for _,v in x.groupby(x.index.to_period('M'))]; R=np.zeros((len(g),31,1))
    for i,v in enumerate(g): R[i,:len(v),0]=v
    return R,(R!=0).astype(float)+0*R+1.0*(R==0)*0,np.zeros_like(R)
GR={'A30':[.001,.0025,.005,.0075,.01,.0125,.015,.02,.025,.03,.04,.05,.068,.10,.15],'C11':[.0025,.005,.01,.015,.02,.025,.03,.04,.05,.065,.08,.10,.13,.177,.25],
    'C11 livelli v4':[.0025,.005,.0075,.01,.015,.02,.025,.03,.04,.05,.065,.08,.10,.13,.18],'FONDO (C3 x k)':[.25,.5,.75,1,1.25,1.5,2,2.5,3,4,5,6,8,10,12]}
_T={}
def job(a):
    name,sc,r,years=a
    if (name,sc) not in _T:
        if name.startswith('FONDO'): _T[(name,sc)]=fund_tensors(sc)
        else:
            X=D[name[:3]]; w=np.where(X.score>0.75,2.,1.) if 'livelli' in name else np.ones(len(X)); Y=lib.scen(X.assign(w=w),sc); _T[(name,sc)]=lib.tensors(Y,Y.w.values)
    o,me=lib.sim(_T[(name,sc)],r,years=years,n=8000,seed=21,ret_paths=True)
    mr=np.diff(np.c_[np.ones(len(me)),me],axis=1)/np.c_[np.ones(len(me)),me][:,:-1]
    o.update(flusso=name,scenario=sc,anni=years,r=r,mese_medio=mr.mean(),mese_mediano=np.median(mr),mesi_ge30=(mr>=.30).mean(),mesi_neg=(mr<0).mean(),mese_p05=np.quantile(mr,.05)); return o
if __name__=='__main__':
    SC=('base','mezzo','verifica'); jobs=[(n,sc,r,y) for n in GR for sc in SC for r in GR[n] for y in (3,1)]
    with Pool(4) as p: res=p.map(job,jobs,chunksize=4)
    R=pd.DataFrame(res); R.to_csv(lib.HERE+'massimo_scan.csv',index=False)
    cols=['r','mese_p50','mese_medio','mese_mediano','mese_p05','mesi_ge30','cagr_p50','cagr_p05','dd_p50','dd_p95','p_dd50','p_meta','p_rovina']
    print("Colonne: r = rischio per trade (per il FONDO: moltiplicatore k); mese_p50 = rendimento mensile composto del percorso MEDIANO; mese_medio = media aritmetica dei mesi (quello che 'si vede' in media);")
    print("mese_mediano = mese tipico; mese_p05 = mese cattivo (1 su 20); mesi_ge30 = quota di mesi >= +30%; dd = drawdown massimo (mediano, 95o perc.); p_dd50 = P(drawdown >= 50% dal massimo); p_meta = P(capitale sotto meta' dell'iniziale); p_rovina = P(capitale <= 10%).")
    for n in GR:
        for sc in SC:
            print(f'\n##### {n} | 3 anni | {sc}'); print(R[(R.flusso==n)&(R.scenario==sc)&(R.anni==3)][cols].round(3).to_string(index=False))
    for n in GR:
        print(f'\n##### {n} | 1 anno | base'); print(R[(R.flusso==n)&(R.scenario=='base')&(R.anni==1)][cols].round(3).to_string(index=False))
    # ---- massimo mensile a rischio dato ----
    def at(g,col,target):
        g=g.sort_values('r'); im=g.mese_p50.values.argmax(); g=g.iloc[:im+1]; x=g[col].values
        if x[-1]<=target: return g.iloc[-1].to_dict(),True          # il vincolo non morde nemmeno al massimo della crescita
        j=np.argmax(x>target)
        if j==0: return None,False
        w=(target-x[j-1])/max(x[j]-x[j-1],1e-12); a=g.iloc[j-1]; b=g.iloc[j]; d={c:a[c]+w*(b[c]-a[c]) for c in cols}; return d,False
    for col,lab in (('p_dd50','P(drawdown >= 50% dal massimo, in 3 anni)'),('p_meta',"P(capitale sotto la meta' dell'iniziale, in 3 anni)")):
        print('\n'+'='*15,f'MASSIMO RENDIMENTO MENSILE (percorso mediano) con {lab} <= soglia','='*15)
        rows=[]
        for n in GR:
            for sc in SC:
                g=R[(R.flusso==n)&(R.scenario==sc)&(R.anni==3)]
                for tg in (.01,.05,.10,.25):
                    d,free=at(g,col,tg)
                    rows.append(dict(flusso=n,scenario=sc,soglia=f'{int(tg*100)}%',r=np.nan if d is None else d['r'],mese_p50=np.nan if d is None else d['mese_p50'],mese_medio=np.nan if d is None else d['mese_medio'],
                                     cagr_p50=np.nan if d is None else d['cagr_p50'],cagr_p05=np.nan if d is None else d['cagr_p05'],dd_p50=np.nan if d is None else d['dd_p50'],dd_p95=np.nan if d is None else d['dd_p95'],nota='max crescita (vincolo non attivo)' if free else ''))
        Z=pd.DataFrame(rows); print(Z.round(4).to_string(index=False)); Z.to_csv(lib.HERE+f'massimo_{col}.csv',index=False)
    # ---- prezzo di 10/20/30% al mese ----
    print('\n'+'='*15,'COSA BISOGNA ACCETTARE PER 10% / 20% / 30% AL MESE','='*15)
    print("(a) come rendimento COMPOSTO del percorso mediano (cio' che il capitale fa davvero): raggiungibile? massimo sulla griglia e rischio a cui si ottiene.")
    rows=[]
    for n in GR:
        for sc in SC:
            g=R[(R.flusso==n)&(R.scenario==sc)&(R.anni==3)].sort_values('r'); b=g.iloc[g.mese_p50.values.argmax()]
            rows.append(dict(flusso=n,scenario=sc,max_mese_p50=b.mese_p50,r_al_max=b.r,dd_p50=b.dd_p50,dd_p95=b.dd_p95,p_dd50=b.p_dd50,p_meta=b.p_meta,p_rovina=b.p_rovina,**{f'{int(t*100)}%':'SI' if b.mese_p50>=t else 'NO' for t in (.10,.20,.30)}))
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    print("\n(b) come MEDIA ARITMETICA dei mesi (il numero che una stanza puo' mostrare 'in media'): rischio necessario nello scenario base, e cosa succede al capitale con quel rischio in ogni scenario.")
    rows=[]
    for n in GR:
        gb=R[(R.flusso==n)&(R.scenario=='base')&(R.anni==3)].sort_values('r')
        for t in (.10,.20,.30):
            x=gb.mese_medio.values; rr=gb.r.values
            if x.max()<t: rows.append(dict(flusso=n,obiettivo=f'{int(t*100)}%',scenario='base',nota=f'non raggiungibile nemmeno in media (max {x.max():.3f} a r={rr[x.argmax()]})')); continue
            j=np.argmax(x>=t); w=(t-x[j-1])/(x[j]-x[j-1]) if j>0 else 0; rt=rr[j-1]+w*(rr[j]-rr[j-1]) if j>0 else rr[0]
            for sc in SC:
                for yrs in (1,3):
                    g=R[(R.flusso==n)&(R.scenario==sc)&(R.anni==yrs)].sort_values('r'); d={c:np.interp(rt,g.r.values,g[c].values) for c in cols}
                    rows.append(dict(flusso=n,obiettivo=f'{int(t*100)}%',scenario=sc,anni=yrs,r=rt,mese_medio=d['mese_medio'],mese_p50=d['mese_p50'],cagr_p50=d['cagr_p50'],cagr_p05=d['cagr_p05'],dd_p50=d['dd_p50'],dd_p95=d['dd_p95'],p_dd50=d['p_dd50'],p_meta=d['p_meta'],p_rovina=d['p_rovina'],mesi_ge30=d['mesi_ge30']))
    Z=pd.DataFrame(rows); print(Z.round(3).to_string(index=False)); Z.to_csv(lib.HERE+'prezzo_obiettivo.csv',index=False)
    json.dump(dict(trials=len(GR)*15),open(lib.HERE+'trials_05.json','w')); print('\nlivelli di rischio valutati:',len(GR)*15)
