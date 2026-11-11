"""A7 parte 2a - che statistiche di trade richiede il 30% al mese. Griglia N x (R medio/sigma_R): crescita mensile a Kelly pieno e mezzo,
distribuzione del drawdown, probabilita' di rovina. Analitico (gaussiano) + simulazione con la FORMA empirica di R (C11 e A30, standardizzata). SIMULATO."""
import lib,numpy as np,pandas as pd,json
pd.set_option('display.width',260,'display.max_rows',500,'display.max_columns',40)
D=lib.load(); G30=12*np.log(1.30)
print('='*20,'2a.1 ANALITICO','='*20)
print(f"Obiettivo: 30%/mese = crescita log annua {G30:.3f} (= +{np.expm1(G30)*100:.0f}%/anno). g(c*Kelly) = N*SR^2*(c - c^2/2), SR = R medio/sigma_R per trade.")
NS=[50,77,100,129,200,500,1000,2000]; SRS=[0.05,0.085,0.10,0.136,0.20,0.30,0.40,0.50]
fmt=lambda v:'>9999' if v>99.99 else '%.1f'%(100*v)
for c,lab in ((1,'KELLY PIENO'),(.5,'MEZZO KELLY'),(.25,'QUARTO DI KELLY')):
    T=pd.DataFrame({s:[fmt(np.expm1(n*s*s*(c-c*c/2)/12)) for n in NS] for s in SRS},index=pd.Index(NS,name='N/anno')); T.columns.name='SR per trade'
    print(f'\nRendimento mensile % (mediano, composto) a {lab}:'); print(T.to_string())
print('\nSR per trade richiesto per un dato rendimento mensile (e, tra parentesi implicita, il t-statistico che mostrerebbe in UN anno = SR*sqrt(N)):')
rows=[]
for n in NS:
    d=dict(N=n)
    for tg in (.10,.20,.30):
        g=12*np.log1p(tg)
        for c,l in ((1,'pieno'),(.5,'mezzo')):
            s=np.sqrt(g/(n*(c-c*c/2))); d[f'{int(tg*100)}% {l}']=s
    d['t in 1 anno (30% pieno)']=np.sqrt(G30*2); d['R medio se sigma=1.74 (C11)']=d['30% pieno']*1.74; d['R medio se sigma=4.28 (A30)']=d['30% pieno']*4.28; rows.append(d)
print(pd.DataFrame(rows).set_index('N').round(3).to_string())
print('\nMisurato nel fondo (R medio/sigma, N/anno, N*SR^2, mensile a Kelly pieno in campione):')
for n in ('A30','C11'):
    for sc in ('base','scelta','verifica'):
        Y=lib.scen(D[n],sc); s=Y.R.mean()/Y.R.std(); N=len(Y)/lib.years_of(Y); print(f'  {n} {sc:9s} SR={s:.3f} N={N:.0f} N*SR^2={N*s*s:.2f} (serve {2*G30:.2f}) -> mensile Kelly pieno gaussiano {np.expm1(N*s*s/24)*100:.1f}%  | moltiplicatore di N*SR^2 mancante: x{2*G30/(N*s*s):.1f}')
print('\nAnalitico (moto browniano geometrico, orizzonte infinito): P(prima o poi il capitale scende a (1-d) del livello DI OGGI) = (1-d)^(2/c-1).')
print("Attenzione: e' la discesa sotto il livello di partenza, non il drawdown dal massimo; il drawdown massimo su un orizzonte finito e' PEGGIORE e cresce col tempo (vedi simulazione).")
T=pd.DataFrame({f'c={c}':[(1-d)**(2/c-1) for d in (.2,.3,.5,.7,.9)] for c in (2,1.5,1,.75,.5,.25)},index=['-20%','-30%','-50%','-70%','-90%']); print(T.round(3).to_string())
print("(c = frazione del Kelly VERO; c=2 = doppio Kelly: crescita zero; oltre: rovina certa.)")

print('\n'+'='*20,'2a.2 SIMULAZIONE con la forma empirica di R (3 anni, 2000 percorsi, trade i.i.d.)','='*20)
print("Per ottenere un dato SR si ripesano i trade empirici (tilting esponenziale: cambia la FREQUENZA di vincite e perdite, non la loro dimensione; la perdita massima resta quella del margine isolato).")
print("Kelly risolto numericamente sulla distribuzione ripesata. r* = rischio per trade in % del capitale.")
from scipy.optimize import brentq,minimize_scalar
rng=np.random.default_rng(3)
def tilt(R,SR):
    z=(R-R.mean())/R.std()
    def f(th):
        w=np.exp(th*z); w/=w.sum(); m=(w*R).sum(); return m/np.sqrt((w*(R-m)**2).sum())-SR
    th=brentq(f,-3,3); w=np.exp(th*z); return w/w.sum()
def simgrid(R,SR,N,frac,years=3,npaths=2000):
    w=tilt(R,SR); hi=0.999/(-R.min()); rk=minimize_scalar(lambda r:-(w*np.log1p(r*R)).sum(),bounds=(0,hi),method='bounded').x; r=frac*rk; T=N*years; out=[]; cw=np.cumsum(w)
    for ch in range(0,npaths,500):
        ix=np.minimum(np.searchsorted(cw,rng.random((500,T))),len(R)-1); lr=np.log1p(r*R[ix]); cum=np.cumsum(lr,1); pk=np.maximum.accumulate(np.maximum(cum,0),1); out.append(np.c_[cum[:,-1],(cum-pk).min(1)])
    o=np.vstack(out); m=(w*R).sum()
    return dict(Rm=m,vincenti=(w*(R>0)).sum(),r_kelly=rk,g_teorico=N*(w*np.log1p(r*R)).sum(),mese=np.expm1(np.median(o[:,0])/(12*years)),mese_p05=np.expm1(np.quantile(o[:,0],.05)/(12*years)),
                dd50=1-np.exp(np.median(o[:,1])),dd95=1-np.exp(np.quantile(o[:,1],.05)),P50=(o[:,1]<=np.log(.5)).mean(),P90=(o[:,1]<=np.log(.1)).mean())
rows=[]; NG=(50,100,200,500,1000,2000); SG=(0.05,0.085,0.136,0.20,0.30,0.40)
for shape in ('C11','A30'):
    R=D[shape].R.values
    for N in NG:
        for SR in SG:
            for frac in (1.,.5):
                d=simgrid(R,SR,N,frac); d.update(forma=shape,N=N,SR=SR,kelly=frac); rows.append(d)
S=pd.DataFrame(rows); S.to_csv('obiettivo_griglia.csv',index=False)
pc=lambda v:'>9999' if v>99.99 else '%.1f'%(100*v)
for shape in ('C11','A30'):
    x=S[(S.forma==shape)&(S.kelly==1)&(S.N==50)].set_index('SR')
    print(f'\n##### forma {shape}: cosa significa ogni SR (R medio, % di trade vincenti, Kelly pieno r* in % del capitale per trade)')
    print(pd.DataFrame(dict(R_medio=x.Rm.round(3),vincenti=(100*x.vincenti).round(1),r_kelly_pct=(100*x.r_kelly).round(1))).T.to_string())
    for frac in (1.,.5):
        y=S[(S.forma==shape)&(S.kelly==frac)]
        for col,lab in (('mese','rendimento mensile mediano %'),('mese_p05','rendimento mensile, 5o percentile %'),('dd50','drawdown massimo mediano in 3 anni %'),('dd95','drawdown massimo 95o percentile %'),('P50','P(drawdown >= 50% in 3 anni) %'),('P90','P(drawdown >= 90% in 3 anni) = rovina %')):
            print(f'\n[{shape} | Kelly x{frac}] {lab}'); print(y.pivot(index='N',columns='SR',values=col).map(pc).to_string())
print('\nCelle con mediana >= 30%/mese e il loro prezzo:'); Z=S[S.mese>=.30][['forma','N','SR','kelly','Rm','vincenti','r_kelly','mese','dd50','dd95','P50','P90']].copy(); Z['mese']=Z.mese.clip(upper=99.99); print(Z.round(3).to_string(index=False))
json.dump(dict(trials=0),open('trials_03.json','w'))
