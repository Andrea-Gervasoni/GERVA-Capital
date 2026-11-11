"""Persistenza del copy-trading. Formazione: 26 settimane fino a T (13 rendimenti da 14 giorni), usando solo dati <= T.
Punteggio principale: Sharpe (media/dev.std) dei rendimenti di formazione. Valutazione: 4 e 12 settimane dopo T.
Universi: PIT = indirizzi noti a T (attivi nei blocchi 2024-Q4 campionati, top giornalieri per volume/ordini con data <= T, vault esistenti a T);
          LB  = indirizzi presi dalla classifica di OGGI (viziata da sopravvivenza)."""
import json, sys, numpy as np, pandas as pd
from scipy.stats import spearmanr
pd.set_option('display.width',280); pd.set_option('display.float_format',lambda x:f'{x:.3f}')
A=pd.read_parquet('data/panel_av.parquet'); P=pd.read_parquet('data/panel_pnl.parquet'); M=pd.read_parquet('data/panel_meta.parquet')
G=A.index; dp=P.diff(); flow=A.diff()-dp; base=np.maximum(A.shift()+0.5*flow,0.5*A.shift()); R=(dp/base).where(base>=5000).clip(lower=-1.0,upper=3.0)   # conto < 5k USD: rendimento non definito; tetto +300% per 14 giorni
F=13; MINAV=1e4; ntrial=0
T0=G.get_loc(pd.Timestamp('2025-01-02 00:30')); TS=[T0+6*k for k in range(0,9) if T0+6*k+6<len(G)]   # la serie dei soli perpetui parte da maggio 2024: prima formazione utile = fine 2024
LENTO=300   # volume annuo <= 300 volte il conto: sopra, 6,5 bp per lato mangiano >20%/anno a chi copia
def universo(nome,t):
    T=G[t]; ex=A.iloc[t].notna()
    if nome.endswith('_lento'): return universo(nome[:-6],t)&(M.turnover_anno<=LENTO).reindex(A.columns).fillna(False).values
    if nome.endswith('_veloce'): return universo(nome[:-7],t)&(M.turnover_anno>LENTO*10).reindex(A.columns).fillna(False).values
    if nome=='PIT':
        m=(M.vault)|(M.top_giorno_dal<=T)
        if T>=pd.Timestamp('2025-01-01'): m=m|M.pit2024q4
    elif nome=='PIT_noHLP_vault': m=((M.top_giorno_dal<=T)|(M.pit2024q4 if T>=pd.Timestamp('2025-01-01') else False))&~M.vault
    elif nome=='VAULT': m=M.vault
    elif nome=='LB': m=M.in_lb_oggi&M.src.str.contains('lb')
    elif nome=='LIQ': m=M.top_liq
    return m.reindex(A.columns).fillna(False).values&ex.values
def punteggio(t,kind):
    w=R.iloc[t-F+1:t+1]; n=w.notna().sum()
    if kind=='sharpe': s=w.mean()/w.std()
    elif kind=='pnl': s=P.iloc[t]-P.iloc[t-F]
    elif kind=='ret': s=(1+w.fillna(0)).prod()-1
    elif kind=='sharpe52': w2=R.iloc[t-26+1:t+1]; s=w2.mean()/w2.std(); n=w2.notna().sum()*13/26
    ok=(n>=10)&(A.iloc[t]>=MINAV)&(w.std()>1e-6)
    return s.where(ok)
def avanti(t,h):
    w=R.iloc[t+1:t+1+h]; return (1+w.fillna(0)).prod()-1, w
def prova(uni,kind,h,q=0.9,verbose=False):
    global ntrial; ntrial+=1; rows=[]; serie=[]; serie_rest=[]
    for t in TS:
        if uni.startswith('PIT') and kind!='x' and False: pass
        s=punteggio(t,kind); m=universo(uni,t); s=s[m].dropna()
        if len(s)<50: continue
        f,w=avanti(t,h); f=f[s.index]; thr=s.quantile(q); top=s.index[s>=thr]; rest=s.index[s<thr]
        fs=(w[s.index].mean()/w[s.index].std()).replace([np.inf,-np.inf],np.nan)
        ic=spearmanr(s,f).statistic; j=pd.concat([s,fs],axis=1).dropna(); ic2=spearmanr(j.iloc[:,0],j.iloc[:,1]).statistic if len(j)>20 else np.nan
        av_end=A.iloc[min(t+h,len(G)-1)][top]; 
        rows.append(dict(T=G[t].date(),n=len(s),n_top=len(top),top_media=f[top].mean(),top_mediana=f[top].median(),top_pos=(f[top]>0).mean(),top_sotto50=(f[top]<=-.5).mean(),
                         resto_media=f[rest].mean(),resto_mediana=f[rest].median(),resto_pos=(f[rest]>0).mean(),resto_sotto50=(f[rest]<=-.5).mean(),IC_rend=ic,IC_sharpe=ic2,
                         top_in_lb_oggi=M.in_lb_oggi[top].mean(),resto_in_lb_oggi=M.in_lb_oggi[rest].mean()))
        if h==6: serie.append(w[top].fillna(0).mean(axis=1)); serie_rest.append(w[rest].fillna(0).mean(axis=1))
    D=pd.DataFrame(rows)
    if verbose and len(D): print(D.to_string())
    return D,(pd.concat(serie) if serie else None),(pd.concat(serie_rest) if serie_rest else None)
def riassunto(D):
    if not len(D): return {}
    n=len(D); d=D.top_mediana-D.resto_mediana; dp=D.top_pos-D.resto_pos
    return dict(date=n,n_medio=D.n.mean(),top_media=D.top_media.mean(),resto_media=D.resto_media.mean(),top_mediana=D.top_mediana.mean(),resto_mediana=D.resto_mediana.mean(),top_pos=D.top_pos.mean(),resto_pos=D.resto_pos.mean(),
                top_sotto50=D.top_sotto50.mean(),resto_sotto50=D.resto_sotto50.mean(),IC_rend=D.IC_rend.mean(),t_IC=D.IC_rend.mean()/D.IC_rend.std()*np.sqrt(n) if n>2 else np.nan,IC_sharpe=D.IC_sharpe.mean(),t_ICs=D.IC_sharpe.mean()/D.IC_sharpe.std()*np.sqrt(n) if n>2 else np.nan,date_top_meglio=(d>0).mean())
print('conti nel pannello',A.shape[1],'| date di formazione:',[str(G[t].date()) for t in TS])
print('\n=== 1. PRINCIPALE: universo PIT, punteggio Sharpe 26 settimane, decile alto, 12 settimane dopo, per data ===')
D,s_top,s_rest=prova('PIT','sharpe',6,verbose=True)
print('\n=== 2. riassunto per universo / punteggio / orizzonte (media sulle date) ===')
rows=[]
for uni in ['PIT','PIT_lento','PIT_veloce','PIT_noHLP_vault','VAULT','LB','LB_lento','LIQ']:
    for kind in ['sharpe','pnl','ret','sharpe52']:
        for h in (2,6):
            d,_,_=prova(uni,kind,h); x=riassunto(d); 
            if x: rows.append(dict(universo=uni,punteggio=kind,sett=h*2,**x))
S=pd.DataFrame(rows); print(S.to_string())
print('\n=== 3. la sola data 2025-01-02 (formazione <= 2024-12), PIT contro classifica di oggi ===')
for uni in ['PIT','PIT_lento','PIT_veloce','VAULT','LB','LB_lento']:
    for h in (2,6):
        global_TS=TS; TS=[T0]; d,_,_=prova(uni,'sharpe',h); TS=global_TS
        if len(d): print(uni,f'{h*2} sett',d.drop(columns=['T']).iloc[0].round(3).to_dict())
# sopravvivenza: cosa e' successo fino a OGGI al decile alto del 2025-01-02
print('\n=== 4. destino a oggi (2026-11) dei conti PIT ammissibili al 2025-01-02 ===')
for UNI in ['PIT','PIT_lento']:
  print(UNI)
  s=punteggio(T0,'sharpe'); m=universo(UNI,T0); s=s[m].dropna(); f,_=avanti(T0,len(G)-1-T0); f=f[s.index]; top=s.index[s>=s.quantile(.9)]; rest=s.index[s<s.quantile(.9)]
  avT=A.iloc[T0]; avN=A.iloc[-1].fillna(0); dP=(P.iloc[-1].ffill()-P.iloc[T0]) if False else (P.ffill().iloc[-1]-P.iloc[T0])
  for lab,ix in [('decile alto',top),('resto',rest)]:
      print(f"{lab:12s} n={len(ix)} rendimento composto mediano fino a oggi={f[ix].median():+.3f} media={f[ix].mean():+.3f} quota<=-50%={(f[ix]<=-.5).mean():.2f} quota<=-90%={(f[ix]<=-.9).mean():.2f} "
            f"conto oggi <10% di allora={(avN[ix]<0.1*avT[ix]).mean():.2f} in classifica oggi={M.in_lb_oggi[ix].mean():.2f} tra i piu' liquidati={M.top_liq[ix].mean():.2f} PnL USD dopo T: somma={dP[ix].sum()/1e6:+.1f}M mediana={dP[ix].median():+.0f}")
lbm=universo('LB',T0); s2=punteggio(T0,'sharpe')[lbm].dropna(); f2,_=avanti(T0,len(G)-1-T0); print(f"classifica di oggi, ammissibili al 2025-01-02: n={len(s2)} rendimento mediano fino a oggi={f2[s2.index].median():+.3f} quota<=-50%={(f2[s2.index]<=-.5).mean():.2f}")
# copia senza attriti
print('\n=== 5. portafoglio di copia SENZA ATTRITI (limite superiore: niente costi, niente ritardo), decile alto PIT, ribilanciato ogni 12 settimane ===')
def st(x,lab):
    x=x.dropna(); eq=(1+x).cumprod(); print(f"{lab:38s} n={len(x)} {x.index[0].date()}->{x.index[-1].date()} CAGR={eq.iloc[-1]**(26/len(x))-1:+.3f} vol={x.std()*np.sqrt(26):.3f} Sharpe={x.mean()/x.std()*np.sqrt(26):+.2f} t={x.mean()/x.std()*np.sqrt(len(x)):+.2f} maxDD={(eq/eq.cummax()-1).min():.3f}")
    return x
if s_top is not None:
    c=st(s_top,'decile alto, media semplice'); st(s_rest,'resto, media semplice'); st(s_top-s_rest,'alto meno resto')
    c2=st(s_top[s_top.index>pd.Timestamp('2025-01-02 00:30')],'decile alto, solo T>=2025-01-02')
    # mediana trasversale (toglie i pochi conti estremi)
    med=[];medr=[]
    for t in TS:
        s=punteggio(t,'sharpe'); m=universo('PIT',t); s=s[m].dropna()
        if len(s)<50: continue
        w=R.iloc[t+1:t+7]; top=s.index[s>=s.quantile(.9)]; rest=s.index[s<s.quantile(.9)]; med.append(w[top].fillna(0).median(axis=1)); medr.append(w[rest].fillna(0).median(axis=1))
        lo,hi=w[top].fillna(0).quantile(.1,axis=1),w[top].fillna(0).quantile(.9,axis=1)
    st(pd.concat(med),'decile alto, conto MEDIANO'); st(pd.concat(medr),'resto, conto MEDIANO')
    for k in (10,20,50):
        ser=[]
        for t in TS:
            s=punteggio(t,'sharpe'); m=universo('PIT',t); s=s[m].dropna()
            if len(s)<50: continue
            top=s.sort_values().index[-k:]; ser.append(R.iloc[t+1:t+7][top].fillna(0).mean(axis=1)); ntrial+=1
        st(pd.concat(ser),f'primi {k} per Sharpe, media semplice')
    s_top.to_frame('copia_decile_alto').to_parquet('copia_senza_attriti.parquet')
print('\n=== 6. come 5 ma solo conti LENTI (copiabili): portafoglio di copia SENZA ATTRITI (limite superiore: niente costi, niente ritardo), decile alto PIT, ribilanciato ogni 12 settimane ===')
def st(x,lab):
    x=x.dropna(); eq=(1+x).cumprod(); print(f"{lab:38s} n={len(x)} {x.index[0].date()}->{x.index[-1].date()} CAGR={eq.iloc[-1]**(26/len(x))-1:+.3f} vol={x.std()*np.sqrt(26):.3f} Sharpe={x.mean()/x.std()*np.sqrt(26):+.2f} t={x.mean()/x.std()*np.sqrt(len(x)):+.2f} maxDD={(eq/eq.cummax()-1).min():.3f}")
    return x
D,s_top,s_rest=prova('PIT_lento','sharpe',6,verbose=True)
if s_top is not None:
    c=st(s_top,'decile alto, media semplice'); st(s_rest,'resto, media semplice'); st(s_top-s_rest,'alto meno resto')
    c2=st(s_top[s_top.index>pd.Timestamp('2025-01-02 00:30')],'decile alto, solo T>=2025-01-02')
    # mediana trasversale (toglie i pochi conti estremi)
    med=[];medr=[]
    for t in TS:
        s=punteggio(t,'sharpe'); m=universo('PIT_lento',t); s=s[m].dropna()
        if len(s)<50: continue
        w=R.iloc[t+1:t+7]; top=s.index[s>=s.quantile(.9)]; rest=s.index[s<s.quantile(.9)]; med.append(w[top].fillna(0).median(axis=1)); medr.append(w[rest].fillna(0).median(axis=1))
        lo,hi=w[top].fillna(0).quantile(.1,axis=1),w[top].fillna(0).quantile(.9,axis=1)
    st(pd.concat(med),'decile alto, conto MEDIANO'); st(pd.concat(medr),'resto, conto MEDIANO')
    for k in (10,20,50):
        ser=[]
        for t in TS:
            s=punteggio(t,'sharpe'); m=universo('PIT_lento',t); s=s[m].dropna()
            if len(s)<50: continue
            top=s.sort_values().index[-k:]; ser.append(R.iloc[t+1:t+7][top].fillna(0).mean(axis=1)); ntrial+=1
        st(pd.concat(ser),f'primi {k} per Sharpe, media semplice')
    s_top.to_frame('copia_decile_alto').to_parquet('copia_lenti_senza_attriti.parquet')
print('\nprove contate in questo script:',ntrial)
