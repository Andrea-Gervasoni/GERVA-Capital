"""B7.6 - il portafoglio neutrale realizzabile: serie, decadimento, leva ottima con gli eventi di coda che NON sono nella serie,
bootstrap a blocchi mensili, correlazione con il fondo, confronto con i T-bill al netto delle tasse italiane. SIMULATO + STIMA (code)."""
import pandas as pd, numpy as np, json, os, warnings
from lib import *
warnings.filterwarnings('ignore'); pd.set_option('display.width',250)
C='/home/user/GERVA-Capital/data_cache/'; D=C+'v6_b7/'; P=json.load(open('congelato.json'))
R=pd.read_parquet('_rot_hl.parquet'); irx=pd.read_parquet(C+'yahoo_1d_^IRX.parquet').close/100
tb=(irx.reindex(pd.date_range('2019-01-01',R.index[-1])).ffill()/365)
# ---- serie lunga: Binance (proxy NON incassabile, solo per pieno/scelta) fino al 2024-01-31, poi Hyperliquid
F=pd.read_parquet(C+'v4_allperp_fund.parquet'); Q=pd.read_parquet(C+'v4_allperp_qvol.parquet')
spot={f[len('bn_spot_1d_'):-len('.parquet')] for f in os.listdir(C) if f.startswith('bn_spot_1d_') and f.endswith('.parquet')}
el=((Q.rolling(30,min_periods=20).median().shift(1)>20e6)&F.notna()).loc[:,[c for c in F.columns if c in spot]]
rbn,_,_=rotate(F[el.columns],el,**P)
noz=pd.concat([rbn[:'2024-01-31'],R.rot_tutte]).rename('noz')            # per unita' di nozionale, senza leva
cap2=pd.concat([rbn[:'2024-01-31']*2/3,R.rot_tutte_cap2x]).rename('cap2')    # sul capitale, short a 2x (prima del 2024 senza scansione liquidazioni)
print('=== 1. Serie del candidato: rotazione del carry (N=%d, k=%d, ingresso>%.0f%%, uscita<%.0f%%). Binance fino al 2024-01 (proxy), Hyperliquid dopo'%(P['N'],P['k'],P['ent']*100,P['ext']*100))
for lab,s in (('per unita\' di nozionale (senza leva)',noz),('sul capitale, short a 2x (67% investito)',cap2)):
    [pr(x) for x in fss(s,lab)]
    print('   per anno %:',(s.groupby(s.index.year).sum()*100).round(2).to_dict(),'| ult. 12 mesi %.2f%% | ult. 90 g annuo %.2f%%'%(s.iloc[-365:].sum()*100,s.iloc[-90:].mean()*36500))
ex=(cap2-tb.reindex(cap2.index)).dropna(); print('   eccesso sul T-bill 3m USD, sul capitale a 2x, per anno %:',(ex.groupby(ex.index.year).sum()*100).round(2).to_dict(),'| ult. 12 mesi %.2f%%'%(ex.iloc[-365:].sum()*100))
print('   NB: Sharpe>3 e\' un artefatto: la volatilita\' misurata (1-2%) non contiene il rischio vero (sede, stablecoin, ADL). Vedi punto 3.')
# ---- 2. leva sulla gamba corta: crescita geometrica misurata (solo Hyperliquid 2024-02 ->)
print('\n=== 2. Leva della gamba corta (Hyperliquid 2024-02 -> oggi): crescita geometrica annua sul capitale, liquidazioni comprese')
G={}
for L in (1,2,3,5):
    s=R['rot_tutte_cap%dx'%L].dropna(); g=np.log1p(s).mean()*365; G[L]=g
    print(f'  leva {L}x: crescita {g*100:6.2f}%/anno = {(np.exp(g/12)-1)*100:5.2f}%/mese composto | 2025 {s[s.index.year==2025].sum()*100:6.2f}% | 2026 {s[s.index.year==2026].sum()*100:6.2f}% | capitale presso Hyperliquid (margine) {1/(L+1):.0%}')
Lstar=max(G,key=G.get); print('  leva che massimizza la crescita misurata:',Lstar,'x ; meta\':',Lstar/2,'x (=1x: 50% spot, 50% margine)')
# ---- 3. eventi di coda non nella serie (STIMA da storia: vedi REPORT) e allocazione ottima
print('\n=== 3. Eventi di coda fuori serie (probabilita\' annua, perdita sulla parte esposta) - STIMA')
TAIL=[('Hyperliquid: fallimento/hack del bridge/blocco prelievi',0.05,0.80,'margine'),('Kraken (sede UE regolata): fallimento/blocco',0.01,0.50,'spot'),
      ('ADL o chiusura forzata dello short + rimbalzo (10/10/2025, JELLY)',0.40,0.03,'nozionale'),('USDC depeg permanente (margine in USDC)',0.005,1.0,'margine')]
def tail_cost(L,scale=1.0):
    sh={'margine':1/(L+1),'spot':L/(L+1),'nozionale':L/(L+1)}; return sum(p*scale*l*sh[w] for _,p,l,w in TAIL)
for n,p,l,w in TAIL: print(f'  {n:66s} p {p:5.1%}  perdita {l:4.0%} di: {w}')
for L in (1,2,3): print(f'  costo atteso delle code a leva {L}x: {tail_cost(L)*100:.2f}%/anno del capitale nello stack (raddoppiando le probabilita\': {tail_cost(L,2)*100:.2f}%)')
# ---- 4. bootstrap a blocchi mensili con code iniettate
rng=np.random.default_rng(7)
def boot(s,L,edge=1.0,pscale=1.0,nsim=20000,months=36,alloc=1.0):
    m=(1+s).resample('ME').prod()-1; m=m.values; sh={'margine':1/(L+1),'spot':L/(L+1),'nozionale':L/(L+1)}
    ix=rng.integers(0,len(m),(nsim,months)); r=m[ix]*edge
    for _,p,l,w in TAIL:
        hit=rng.random((nsim,months))<p*pscale/12; r=np.where(hit,(1+r)*(1-l*sh[w])-1,r)
    r=r*alloc; eq=np.cumprod(1+r,axis=1); dd=(eq/np.maximum.accumulate(np.concatenate([np.ones((nsim,1)),eq],axis=1),axis=1)[:,1:]-1).min(axis=1)
    g=np.log(eq[:,-1])/months
    return dict(mese_med=(np.exp(np.median(g))-1)*100,mese_medio_geo=(np.exp(g.mean())-1)*100,p50=(dd<=-0.5).mean()*100,p20=(dd<=-0.2).mean()*100,q05=(np.exp(np.quantile(g,0.05)*12)-1)*100)
print('\n=== 4. Bootstrap a blocchi mensili, 3 anni, 20.000 percorsi, code del punto 3 iniettate (base: mesi Hyperliquid 2024-02 -> oggi)')
last12=lambda s: s.iloc[-365:]
for lab,sel,edge in (('base (tutti i mesi 2024-26)',lambda s:s,1.0),('meta\' vantaggio',lambda s:s,0.5),('regime di oggi (ultimi 12 mesi)',last12,1.0),('oggi, meta\' vantaggio',last12,0.5)):
    for L in (Lstar,Lstar/2 if Lstar>1 else 1):
        L=int(L); b=boot(sel(R['rot_tutte_cap%dx'%L].dropna()),L,edge)
        print(f'  {lab:32s} leva {L}x: mese composto mediano {b["mese_med"]:5.2f}% (media geometrica {b["mese_medio_geo"]:5.2f}%) | P(-20%) {b["p20"]:4.1f}% | P(-50%) {b["p50"]:4.2f}% | 5° percentile CAGR {b["q05"]:6.1f}%')
b=boot(R['rot_tutte_cap%dx'%Lstar].dropna(),Lstar,1.0,pscale=2.0); print(f'  base, probabilita\' di coda x2, leva {Lstar}x: mese {b["mese_med"]:.2f}% | P(-20%) {b["p20"]:.1f}% | P(-50%) {b["p50"]:.2f}%')
# ---- 5. allocazione ottima della cassa del fondo (Kelly con salto): g(f)=f*mu_ecc + sum p*ln(1-f*l)
print('\n=== 5. Quota ottima della cassa del fondo da mettere nello stack invece che in T-bill (crescita con salti), leva %dx'%Lstar)
sh={'margine':1/(Lstar+1),'spot':Lstar/(Lstar+1),'nozionale':Lstar/(Lstar+1)}
def kelly(mu,pscale=1.0):
    f=np.linspace(0,1,201); g=f*mu+sum(p*pscale*np.log(1-f*l*sh[w]) for _,p,l,w in TAIL); return f[g.argmax()],g.max()
s2=R['rot_tutte_cap%dx'%Lstar].dropna(); e2=(s2-tb.reindex(s2.index)).dropna()
for lab,mu in (('eccesso medio 2024-26',e2.mean()*365),('eccesso 2026',e2[e2.index.year==2026].mean()*365),('eccesso ultimi 12 mesi',e2.iloc[-365:].mean()*365),('meta\' dell\'eccesso 2026',e2[e2.index.year==2026].mean()*365/2)):
    f,g=kelly(mu); f2,g2=kelly(mu,2.0); print(f'  {lab:26s} mu {mu*100:5.2f}%/a: quota ottima {f:4.0%} (guadagno di crescita {g*100:+.2f}%/a) ; con code x2: {f2:4.0%} ({g2*100:+.2f}%/a)')
# ---- 6. tasse italiane
print('\n=== 6. Dopo le tasse (residente italiano 2026: 33% su cripto-attivita\' e funding; 12,5% su titoli di Stato) - rendimento annuo netto, oggi')
g26=s2[s2.index.year==2026].mean()*365; g12=s2.iloc[-365:].mean()*365; t=irx.iloc[-1]
for lab,g,tax in (('T-bill 3m USD (via ETF monetario di titoli di Stato / BOT)',t,0.125),('stack carry 2x, livello 2026',g26,0.33),('stack carry 2x, ultimi 12 mesi',g12,0.33),('USDC su Aave (oggi 3,96%)',0.0396,0.33),('sUSDe (oggi 5,0%)',0.0501,0.33),('sUSDS / Sky (oggi 3,8%)',0.038,0.33)):
    print(f'  {lab:58s} lordo {g*100:5.2f}%  netto {g*(1-tax)*100:5.2f}%  netto meno code {(g*(1-tax)-(tail_cost(Lstar) if "stack" in lab else (0.015 if "USD" in lab and "T-bill" not in lab else 0)))*100:5.2f}%')
# ---- 7. correlazione con il fondo
print('\n=== 7. Correlazione con il fondo esistente (a10_sistema)')
A=pd.read_parquet('/home/user/GERVA-Capital/research/v5/v5/a10_sistema/returns.parquet')
for lab,s in (('serie lunga (nozionale, 2020->)',noz),('solo Hyperliquid 2x (2024-02->)',s2)):
    for c in ['B_cassa_in_tbill','C1_mtm_limiti','C3_mtm_limiti_debito_reale']:
        x=pd.concat([s,A[c]],axis=1).dropna(); xm=(1+x).resample('ME').prod()-1
        print(f'  {lab:34s} vs {c:28s} corr giornaliera {x.corr().iloc[0,1]:+.3f} | mensile {xm.corr().iloc[0,1]:+.3f} (n mesi {len(xm)})')
# effetto sul fondo: 47% del libro a 1x e' cassa
print('\n=== 8. Effetto sul fondo: cassa (circa 47% del libro a 1x) nello stack invece che in T-bill')
for lab,e in (('eccesso 2026',e2[e2.index.year==2026].mean()*365),('eccesso ultimi 12 mesi',e2.iloc[-365:].mean()*365),('eccesso medio 2024-26',e2.mean()*365)):
    for q in (0.25,0.47): print(f'  {lab:24s} quota del fondo {q:.0%}: +{q*e*100:.2f} punti/anno lordi ; netti di code attese +{q*(e-tail_cost(Lstar))*100:.2f} = +{q*(e-tail_cost(Lstar))*100/12:.3f}%/mese')
# ---- salvataggio
stk=pd.read_parquet(D+'stk_stETH_Hyperliquid.parquet').r
out=pd.DataFrame({'carry_rot_nozionale_1x':noz,'carry_rot_capitale_short2x':cap2,'carry_big3_hold_nozionale':R.hold_big3,'carry_rot_spotHL_nozionale':R.rot_hlspot,'steth_short_eth_hl_nozionale_lordo':stk})
if 'rot_hip3' in R: out['carry_hip3_nozionale']=R.rot_hip3
out=out.reindex(pd.date_range(out.index.min(),out.index.max())); out.to_parquet('returns.parquet'); print('\nsalvato returns.parquet',out.shape,out.notna().sum().to_dict())
