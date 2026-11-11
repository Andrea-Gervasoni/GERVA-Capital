"""A7 parte 1a - Kelly empirico per flusso, sotto incertezza dei parametri, per conviction/volatilita', e simultaneo sulle 3 monete. SIMULATO."""
import lib,numpy as np,pandas as pd,json
from scipy.optimize import minimize
pd.set_option('display.width',260,'display.max_rows',300,'display.max_columns',40)
D=lib.load(); rng=np.random.default_rng(11); TRIALS=0
mo=lambda g:np.expm1(g/12)
print('='*20,'1.1 KELLY PER FLUSSO (R empirici, perdita limitata dal margine isolato)','='*20)
print("r_gauss = R/sigma^2; r_seq = max E[log(1+rR)] trade per trade; r_coorte = idem con i trade dello stesso giorno simultanei (quello usato).")
print("g = crescita log annua; mese = exp(g/12)-1. 'fuori campione' = r_coorte stimato sulla SCELTA applicato alla VERIFICA.")
rows=[]
for n,X in D.items():
    for sc in ('base','scelta','verifica'):
        Y=lib.scen(X,sc); y=lib.years_of(Y); R=Y.R.values; sd=R.std(ddof=1)
        rs,_=lib.kelly_seq(R,Y.cap); rc,g=lib.kelly_coh(Y)
        rows.append(dict(flusso=n,periodo=sc,n=len(Y),N_anno=len(Y)/y,Rm=R.mean(),sd=sd,t=lib.tstat(R),SRtrade=R.mean()/sd,N_SR2=len(Y)/y*(R.mean()/sd)**2,
            r_gauss=max(R.mean(),0)/sd**2,r_seq=rs,r_coorte=rc,g_pieno=g,mese_pieno=mo(g),g_mezzo=lib.growth_coh(Y,rc/2),mese_mezzo=mo(lib.growth_coh(Y,rc/2)),
            g_quarto=lib.growth_coh(Y,rc/4)))
    rsel,_=lib.kelly_coh(lib.scen(X,'scelta')); V=lib.scen(X,'verifica')
    for f in (1,.5,.25): rows.append(dict(flusso=n,periodo='fuori campione x%.2f'%f,n=len(V),r_coorte=rsel*f,g_pieno=lib.growth_coh(V,rsel*f),mese_pieno=mo(lib.growth_coh(V,rsel*f))))
K=pd.DataFrame(rows); print(K.round(4).to_string(index=False)); K.to_csv('kelly_flussi.csv',index=False); TRIALS+=len(D)
print('\nper anno (A30, C11): n, R medio, t')
for n in ('A30','C11'):
    X=D[n]; print(n); print(X.groupby(X.entry.dt.year).R.agg(n='size',Rm='mean',sd='std',t=lib.tstat).round(3).T.to_string())

print('\n'+'='*20,'1.2 KELLY SOTTO INCERTEZZA DEI PARAMETRI (bootstrap a blocchi di mesi, 3000 ricampionamenti)','='*20)
def boot_kelly(Y,B=3000,G=400):
    x,m,per=lib.cohorts(Y); months=pd.period_range(Y.entry.min().to_period('M'),Y.entry.max().to_period('M'),freq='M'); M=len(months)
    mi=np.array([months.get_loc(p) for p in per]); hi=0.999/m.max(); grid=np.linspace(0,hi,G); LG=np.log1p(np.outer(x,grid))
    cnt=np.stack([np.bincount(rng.integers(0,M,M),minlength=M) for _ in range(B)])[:,mi]      # B x coorti
    Gb=cnt@LG/lib.years_of(Y)                                                                 # crescita log annua per ricampionamento e r
    rstar=grid[Gb.argmax(1)]; means=(cnt@x)/np.maximum(cnt.sum(1),1)
    # numero di trade per coorte per la media per trade
    ntr=Y.groupby('entry').size().values; mt=(cnt@x)/np.maximum(cnt@ntr,1)
    return grid,Gb,rstar,mt
rows=[];ROB={}
for n in ('A30','C11','B20','S20'):
    for sc in ('scelta','base'):
        Y=lib.scen(D[n],sc); grid,Gb,rstar,mt=boot_kelly(Y); se=mt.std(); rc,g=lib.kelly_coh(Y)
        def shr(kse):
            Z=Y.copy(); Z['R']=np.maximum(Z.R-kse*se,-Z.cap); return lib.kelly_coh(Z)[0]
        q=lambda p:grid[np.quantile(Gb,p,axis=0).argmax()]
        d=dict(flusso=n,stima_su=sc,Rm=Y.R.mean(),se_iid=Y.R.std()/np.sqrt(len(Y)),se_blocchi=se,t_blocchi=Y.R.mean()/se,r_pieno=rc,
               r_boot_p05=np.quantile(rstar,.05),r_boot_p25=np.quantile(rstar,.25),r_boot_p50=np.median(rstar),r_boot_p75=np.quantile(rstar,.75),r_boot_p95=np.quantile(rstar,.95),
               P_r0=(rstar<=grid[1]).mean(),r_meno1se=shr(1),r_meno2se=shr(2),r_maxp25=q(.25),r_maxp10=q(.10),
               P_perdita_a_pieno=(Gb[:,np.abs(grid-rc).argmin()]<0).mean(),P_perdita_a_mezzo=(Gb[:,np.abs(grid-rc/2).argmin()]<0).mean(),P_perdita_a_quarto=(Gb[:,np.abs(grid-rc/4).argmin()]<0).mean())
        rows.append(d); ROB[(n,sc)]=d
U=pd.DataFrame(rows); print(U.round(4).T.to_string()); U.to_csv('kelly_incertezza.csv',index=False); TRIALS+=4
print("P_perdita_a_x = quota dei ricampionamenti (storie alternative della stessa lunghezza) in cui puntare x*Kelly da' crescita log NEGATIVA.")

print('\n'+'='*20,'1.3 RISCHIO OTTIMO PER CONVICTION SCORE E STATO DI VOLATILITA\'','='*20)
print("Soglie ATR (terzili) e Kelly di cella stimati sulla SCELTA. k_scelta/k_base = Kelly sequenziale di cella; R_ver = R medio in verifica.")
W={}
def cell_table(X,keys,label):
    S=lib.scen(X,'scelta'); rows=[]
    for kv,g in X.groupby(keys,observed=True):
        gs=g[g.entry<lib.SPLIT]; gv=g[g.entry>=lib.SPLIT]
        rows.append(dict(cella=kv,n=len(g),n_sc=len(gs),n_ver=len(gv),Rm=g.R.mean(),sd=g.R.std(),t=lib.tstat(g.R),R_sc=gs.R.mean() if len(gs) else np.nan,t_sc=lib.tstat(gs.R),
                         R_ver=gv.R.mean() if len(gv) else np.nan,t_ver=lib.tstat(gv.R),k_scelta=lib.kelly_seq(gs.R,gs.cap)[0] if len(gs)>5 else 0.,k_base=lib.kelly_seq(g.R,g.cap)[0],k_ver=lib.kelly_seq(gv.R,gv.cap)[0] if len(gv)>5 else np.nan))
    T=pd.DataFrame(rows); print(label); print(T.round(3).to_string(index=False)); return T
for n in ('A30','C11'):
    X=D[n]; S=X[X.entry<lib.SPLIT]
    X['sb']=np.where(X.score<0.70,'0.67',np.where(X.score<0.80,'0.75','>=0.83'))
    q1,q2=S.atr.quantile([1/3,2/3]); X['vb']=np.where(X.atr<q1,'1bassa',np.where(X.atr<q2,'2media','3alta'))
    print(f'\n--- {n}: terzili ATR (scelta) {q1:.3f} / {q2:.3f}')
    ts=cell_table(X,'sb','per score'); tv=cell_table(X,'vb','per volatilita'); tc=cell_table(X,'coin','per moneta'); t2=cell_table(X,['sb','vb'],'score x volatilita'); TRIALS+=4
    print('corr(score,R)=%.3f  corr(atr,R)=%.3f  (verifica: %.3f, %.3f)'%(X.score.corr(X.R),X.atr.corr(X.R),X[X.entry>=lib.SPLIT].score.corr(X[X.entry>=lib.SPLIT].R),X[X.entry>=lib.SPLIT].atr.corr(X[X.entry>=lib.SPLIT].R)))
    ks=dict(zip(ts.cella,ts.k_scelta)); kv=dict(zip(tv.cella,tv.k_scelta)); k2=dict(zip(t2.cella,t2.k_scelta)); kc=dict(zip(tc.cella,tc.k_scelta))
    W[n]=dict(score=X.sb.map(ks).values,vol=X.vb.map(kv).values,score_vol=np.array([k2.get((a,b),0.) for a,b in zip(X.sb,X.vb)]),moneta=X.coin.map(kc).values)
    D[n]=X
import pickle; pickle.dump(dict(D=D,W=W),open('pesi.pkl','wb'))

print('\n'+'='*20,'1.4 KELLY SIMULTANEO SU 3 MONETE CORRELATE','='*20)
for n in ('A30','C11'):
    X=D[n]; P=X.pivot_table(index='entry',columns='coin',values='R',aggfunc='sum'); 
    print(f'\n--- {n}: coorti {len(P)}, con 1/2/3 monete: {(P.notna().sum(1)).value_counts().sort_index().to_dict()}')
    print('correlazione di R fra monete entrate lo stesso giorno (n coppie):'); print(P.corr(min_periods=10).round(2).to_string())
    for a,b in (('BTC','ETH'),('BTC','SOL'),('ETH','SOL')): print('  n coppie',a,b,P[[a,b]].dropna().shape[0],end=';')
    # trade sovrapposti (non stesso giorno): correlazione dei rendimenti di trade aperti contemporaneamente
    Z=X.sort_values('entry').reset_index(drop=True); pr=[]
    for i in range(len(Z)):
        j=i+1
        while j<len(Z) and Z.entry[j]<Z.exit[i]:
            if Z.coin[j]!=Z.coin[i]: pr.append((Z.R[i],Z.R[j]))
            j+=1
    pr=np.array(pr); print('\n  coppie di trade sovrapposti nel tempo (monete diverse): %d, corr R = %.2f'%(len(pr),np.corrcoef(pr.T)[0,1]))
    for sc in ('scelta','base','verifica'):
        Y=lib.scen(X,sc); Q=Y.pivot_table(index='entry',columns='coin',values='R',aggfunc='sum').fillna(0.); Cq=Y.pivot_table(index='entry',columns='coin',values='cap',aggfunc='sum').fillna(0.)
        y=lib.years_of(Y); cols=list(Q.columns)
        ind={c:lib.kelly_seq(Y[Y.coin==c].R,Y[Y.coin==c].cap) for c in cols}
        f=lambda r:-np.sum(np.log(np.maximum(1+Q.values@r,1e-12)))/y
        cons=[dict(type='ineq',fun=lambda r:0.999-(Cq.values@r).max())]
        o=minimize(f,np.array([ind[c][0] for c in cols])*0.5+1e-3,bounds=[(0,0.5)]*3,constraints=cons,method='SLSQP')
        rj=o.x; rflat,gflat=lib.kelly_coh(Y)
        gind=-f(np.minimum(np.array([ind[c][0] for c in cols]),0.999/Cq.values.max()/3))
        print(f'  [{sc}] Kelly indipendente per moneta {dict((c,round(ind[c][0],4)) for c in cols)} somma {sum(v[0] for v in ind.values()):.4f} -> usato insieme: g={gind:.3f}/anno')
        print(f'  [{sc}] Kelly congiunto          {dict(zip(cols,rj.round(4)))} somma {rj.sum():.4f} -> g={-o.fun:.3f}/anno ; uguale per moneta r={rflat:.4f} g={gflat:.3f}')
    TRIALS+=3
json.dump(dict(trials=TRIALS),open('trials_01.json','w')); print('\nvarianti contate in questo script:',TRIALS)
