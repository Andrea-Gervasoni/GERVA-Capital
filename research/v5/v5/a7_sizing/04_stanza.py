"""A7 parte 2b - la 'trading room': 100.000 trader simulati (risultati riportati per 1.000), ognuno rischia 2-5% per trade a leva 20-30x.
Quanti mostrano >=30%/mese per 3, 6, 12 mesi di fila e quanti saltano, con vantaggio ZERO e con il vantaggio misurato del fondo. SIMULATO.
R estratti dalla distribuzione empirica dei trade del fondo a 30x (stop 1,7%) e 20x (stop 2,7%), con la media spostata al vantaggio voluto;
perdita per trade limitata dal margine isolato. Ogni trader: rischio r~U(2%,5%) fisso, leva 20x o 30x (50/50), n trade al mese fisso."""
import lib,numpy as np,pandas as pd,json
pd.set_option('display.width',260,'display.max_rows',500,'display.max_columns',40)
D=lib.load(); rng=np.random.default_rng(2026); NT=100_000
SH={30:D['A30'],20:D['B20']}; COST={30:2*0.00065/0.017+0.0003*3.5/0.017,20:2*0.00065/0.027+0.0003*3.5/0.027}   # commissioni+slippage+funding medio (3,5 giorni) in R
EDGE={'zero netto (R medio = 0)':lambda L:0.0,'zero lordo (R medio = -costi)':lambda L:-COST[L],
      'fondo, verifica (0,196R a 30x; 0,124R a 20x)':lambda L:{30:lib.scen(D['A30'],'verifica').R.mean(),20:lib.scen(D['B20'],'verifica').R.mean()}[L],
      'fondo, intero campione (0,364R; 0,246R)':lambda L:{30:D['A30'].R.mean(),20:D['B20'].R.mean()}[L],
      'doppio del fondo (0,73R; 0,49R)':lambda L:{30:2*D['A30'].R.mean(),20:2*D['B20'].R.mean()}[L]}
print('costo per trade in R: 30x %.3f, 20x %.3f'%(COST[30],COST[20]))
def run(edge,npm,months=36,rlo=.02,rhi=.05):
    res=[]
    for L in (30,20):
        X=SH[L]; R0=X.R.values-X.R.mean()+edge(L); cap=X.cap.values; R0=np.maximum(R0,-cap); n=NT//2
        r=rng.uniform(rlo,rhi,n); eq=np.ones(n); mn=np.ones(n); M=np.zeros((n,months))
        for m in range(months):
            x=R0[rng.integers(0,len(R0),(n,npm))]; path=np.cumprod(1+r[:,None]*x,1)*eq[:,None]
            mn=np.minimum(mn,path.min(1)) if m<12 else mn; 
            if m==11: mn12=mn.copy()
            M[:,m]=path[:,-1]/eq-1; eq=path[:,-1]
            if m==11: eq12=eq.copy()
            if m==0: mnall=path.min(1)
            else: mnall=np.minimum(mnall,path.min(1))
        res.append((M,mn12,eq12,mnall,eq,r))
    M=np.vstack([a[0] for a in res]); mn12=np.concatenate([a[1] for a in res]); eq12=np.concatenate([a[2] for a in res]); mnall=np.concatenate([a[3] for a in res]); eq=np.concatenate([a[4] for a in res])
    ok=M>=.30
    def run_any(k,T):   # almeno una serie di k mesi consecutivi >=30% nei primi T mesi
        c=np.cumsum(np.c_[np.zeros(len(ok)),ok[:,:T]],1); return ((c[:,k:]-c[:,:-k])==k).any(1)
    cum=np.cumprod(1+M,1)
    d={'primi 3 mesi tutti >=30%':ok[:,:3].all(1).mean(),'3 di fila in 12 mesi':run_any(3,12).mean(),'6 di fila in 12 mesi':run_any(6,12).mean(),'12 su 12':ok[:,:12].all(1).mean(),
       '3 di fila in 36 mesi':run_any(3,36).mean(),'6 di fila in 36 mesi':run_any(6,36).mean(),'12 di fila in 36 mesi':run_any(12,36).mean(),
       'media composta >=30%/mese su 3':(cum[:,2]>=1.3**3).mean(),'su 6':(cum[:,5]>=1.3**6).mean(),'su 12':(cum[:,11]>=1.3**12).mean(),'su 36':(cum[:,35]>=1.3**36).mean(),
       'anno chiuso in utile':(eq12>1).mean(),'anno >= +100%':(eq12>=2).mean(),'mediana anno':np.median(eq12)-1,'media anno':eq12.mean()-1,
       '-50% entro 12 mesi':(mn12<=.5).mean(),'-90% entro 12 mesi (saltato)':(mn12<=.1).mean(),'-50% entro 36 mesi':(mnall<=.5).mean(),'-90% entro 36 mesi (saltato)':(mnall<=.1).mean(),
       'mediana capitale a 36 mesi':np.median(eq),'in utile a 36 mesi':(eq>1).mean()}
    # fra chi mostra 3 mesi di fila >=30% nei primi 12: quanti saltano (-90%) entro 36 mesi
    s=run_any(3,12); d['fra chi ha fatto 3 di fila: saltati entro 36 mesi']=(mnall[s]<=.1).mean() if s.any() else np.nan; d['fra chi ha fatto 3 di fila: in utile a 36 mesi']=(eq[s]>1).mean() if s.any() else np.nan
    return d
ALL={}
for npm,lab in ((11,'11 trade/mese (frequenza del fondo, 129/anno)'),(21,'21 trade/mese (1 al giorno)'),(42,'42 trade/mese (2 al giorno)')):
    T=pd.DataFrame({e:run(f,npm) for e,f in EDGE.items()}); ALL[lab]=T
    print(f'\n##### {lab} — valori PER 1.000 TRADER (le righe mediana/media sono rendimenti, non conteggi)')
    Z=T.copy(); cnt=[i for i in Z.index if not i.startswith('media') or 'composta' in i]; cnt=[i for i in cnt if not i.startswith('mediana') and not i.startswith('fra chi')]
    Z.loc[cnt]=Z.loc[cnt]*1000; print(Z.map(lambda v:'%.2f'%v if abs(v)<1e5 else '%.2e'%v).to_string())
pd.concat(ALL).to_csv('stanza.csv')
print('\n##### Sensibilita\' al rischio per trade (vantaggio zero netto, 21 trade/mese), per 1.000 trader')
rows={}
for lo,hi in ((.005,.01),(.01,.02),(.02,.05),(.05,.10),(.10,.20)):
    d=run(EDGE['zero netto (R medio = 0)'],21,rlo=lo,rhi=hi); rows[f'r {lo*100:.1f}-{hi*100:.0f}%']={k:d[k]*1000 for k in ('3 di fila in 12 mesi','6 di fila in 12 mesi','12 su 12','media composta >=30%/mese su 3','su 12','-50% entro 12 mesi','-90% entro 12 mesi (saltato)','-90% entro 36 mesi (saltato)')}
print(pd.DataFrame(rows).round(2).to_string())
print('\n##### Quanti trader a vantaggio ZERO servono perche\' la stanza abbia in vetrina almeno un track record (P>=50%): n = ln(0,5)/ln(1-p)')
T=ALL['21 trade/mese (1 al giorno)']['zero netto (R medio = 0)']
for k in ('3 di fila in 12 mesi','6 di fila in 12 mesi','12 su 12','media composta >=30%/mese su 3','su 6','su 12'):
    p=T[k]; print(f'  {k:38s} p={p:.5f}  -> servono {np.log(.5)/np.log(1-p):,.0f} trader' if 0<p<1 else f'  {k:38s} p={p} (0 su {NT:,}: meno di 1 su {NT//3:,})')
json.dump(dict(trials=0),open('trials_04.json','w'))
