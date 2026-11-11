"""B7 - funzioni comuni: rotazione del carry con isteresi, statistiche. SIMULATO."""
import numpy as np, pandas as pd
SEL_END=pd.Timestamp('2022-12-31'); VER0=pd.Timestamp('2023-01-01')
def stats(r,lab='',per=365.0):
    r=r.dropna()
    if len(r)<20: return dict(lab=lab,n=len(r))
    m=r.mean()*per; s=r.std()*np.sqrt(per); eq=(1+r).cumprod(); dd=(eq/eq.cummax()-1).min()
    return dict(lab=lab,n=len(r),cagr=eq.iloc[-1]**(per/len(r))-1,ann=m,vol=s,sharpe=m/s if s>0 else np.nan,maxdd=dd,t=r.mean()/r.std()*np.sqrt(len(r)) if r.std()>0 else np.nan)
def fss(r,lab=''):
    """pieno / scelta / verifica"""
    out=[]
    for nm,x in (('pieno',r),('scelta',r[:SEL_END]),('verifica',r[VER0:])):
        d=stats(x,lab+' '+nm); out.append(d)
    return out
def pr(d):
    if 'cagr' not in d: print(f"{d['lab']:58s} n {d['n']}"); return
    print(f"{d['lab']:58s} n {d['n']:5d} CAGR {d['cagr']*100:6.2f}% vol {d['vol']*100:5.2f}% Sharpe {d['sharpe']:6.2f} maxDD {d['maxdd']*100:6.2f}% t {d['t']:5.2f}")
def rotate(F,elig,k=7,N=5,ent=0.15,ext=0.05,cost_rt=0.0073,delay=1,dP=None,minhold=0):
    """F: funding giornaliero incassato dallo short (data x moneta). Segnale al giorno t = media annualizzata del funding dei k giorni
    fino a t-delay (delay=1: solo giorni completi). Tiene fino a N monete, peso 1/N del nozionale ciascuna; entra se segnale>ent ed e' tra le
    migliori; esce se segnale<ext o non idonea. cost_rt = costo andata+ritorno delle due gambe sul nozionale (meta' all'ingresso, meta' all'uscita).
    dP: variazione giornaliera del premio perp-spot (lo short guadagna -dP). Ritorna rendimento per unita' di NOZIONALE pieno (N slot) e diario."""
    sig=(F.rolling(k,min_periods=k).mean()*365).shift(delay)
    cols=list(F.columns); idx=F.index; hold={}; out=np.zeros(len(idx)); nh=np.zeros(len(idx)); turns=0; log=[]
    Fv=F.fillna(0).values; Sv=sig.values; Ev=elig.reindex(index=idx,columns=cols).fillna(False).values
    Pv=dP.reindex(index=idx,columns=cols).fillna(0).values if dP is not None else None
    for i in range(len(idx)):
        s=Sv[i]; e=Ev[i]
        for j in list(hold):
            if (not e[j]) or np.isnan(s[j]) or (s[j]<ext and i-hold[j]>=minhold):
                out[i]-=cost_rt/2/N; turns+=1; log.append((cols[j],idx[hold[j]],idx[i])); del hold[j]
        if len(hold)<N:
            cand=[j for j in np.argsort(-np.nan_to_num(s,nan=-9)) if e[j] and not np.isnan(s[j]) and s[j]>ent and j not in hold]
            for j in cand[:N-len(hold)]:
                hold[j]=i; out[i]-=cost_rt/2/N
        for j in hold:
            out[i]+=Fv[i,j]/N
            if Pv is not None and hold[j]<i: out[i]-=Pv[i,j]/N
        nh[i]=len(hold)
    for j in hold: log.append((cols[j],idx[hold[j]],idx[-1]+pd.Timedelta(days=1)))
    L=pd.DataFrame(log,columns=['coin','in','out'])
    return pd.Series(out,index=idx),pd.Series(nh,index=idx),L

def liq_scan(L,O,Hi,Cl,maxlev,lev,N,thr=0.5,cost_rebal=0.00365):
    """Rischio di liquidazione della gamba corta. Per ogni posizione (moneta, in, out): margine = nozionale/leva_eff, leva_eff=min(lev,maxlev);
    distanza di liquidazione d = 1/leva_eff - 1/(2*maxlev) (margine di mantenimento Hyperliquid = meta' dell'iniziale alla leva massima).
    Riferimento = apertura del giorno d'ingresso; se il MASSIMO del giorno (= massimo dei massimi orari) supera rif*(1+d): liquidazione,
    perdita = (mantenimento + 0,2%) del nozionale dello slot e rientro; se la chiusura si e' mossa piu' di thr*d dal riferimento: si rimargina
    (costo = |movimento| * 36,5 pb, le due gambe). Ritorna serie giornaliera di perdita per unita' di nozionale pieno e conteggi."""
    idx=O.index; loss=pd.Series(0.0,index=idx); nl=0; nr=0; ev=[]
    for c,a,b in L.itertuples(index=False):
        if c not in O: continue
        ml=float(maxlev.get(c,3)); le=min(lev,ml); mm=1/(2*ml); d=1/le-mm
        days=idx[(idx>=a)&(idx<b)]
        if not len(days): continue
        ref=O.at[days[0],c]
        for t in days:
            h=Hi.at[t,c]; cl=Cl.at[t,c]
            if not np.isfinite(h) or not np.isfinite(ref): continue
            if h>=ref*(1+d): loss[t]+=(mm+0.002)/N; nl+=1; ev.append((c,t,h/ref-1)); ref=cl
            elif abs(cl/ref-1)>thr*d: loss[t]+=abs(cl/ref-1)*cost_rebal/N; nr+=1; ref=cl
    return loss,nl,nr,ev
