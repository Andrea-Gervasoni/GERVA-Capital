"""A7 - robustezza dei flussi usati per il sizing: costi raddoppiati e ritardo di esecuzione (1 barra da 5m, 12 barre = 1 ora).
Rigenera i trade con la stessa logica della v4 (leva_trade_isolato.trades) aggiungendo due parametri; la versione senza modifiche deve riprodurre la cache. SIMULATO."""
import sys,pickle,numpy as np,pandas as pd
sys.path.insert(0,'/home/user/GERVA-Capital/research/v5/v4'); sys.path.insert(0,'/home/user/GERVA-Capital')
import leva_trade_isolato as T, lib
pd.set_option('display.width',250)
def trades(c,s,tiers=('alta',),maxhold=7,trail=None,atr_k=None,delay=0,cmult=1.0):
    b=T.B[c]; d=T.D[c]; cv=T.CONV[c]; f=T.fund(c); FEE=T.FEE*cmult; SS=T.STOPSLIP*cmult
    op=b['open'].values; hi=b['high'].values; lo=b['low'].values
    dn=b.index.normalize().values; days=d.index.values; start=np.searchsorted(dn,days); end=np.append(start[1:],len(dn))
    atr=((d['high']-d['low'])/d['close']).rolling(14).mean().shift(1).values; tier=cv['tier'].values; score=cv['score'].values; out=[]; i=250
    while i<len(days)-1:
        if tier[i] not in tiers or np.isnan(score[i]): i+=1; continue
        sd=s if atr_k is None else float(np.clip(atr_k*atr[i],0.003,0.15)); L=T.levmax(sd); k0=start[i]+delay; p0=op[k0]; stop=p0*(1-sd); best=p0; j=i; exitp=None; liq=p0*(1-(1/L-T.MM))
        while True:
            a,z=(k0 if j==i else start[j]),end[j]
            for k in range(a,z):
                o,h,l=op[k],hi[k],lo[k]
                if l<=stop:
                    px=min(stop,o)*(1-SS); px=max(px,liq); exitp=px; break
                if trail is not None and h>best:
                    best=h; ns=best*(1-trail*sd)
                    if ns>stop: stop=ns
            if exitp is not None: break
            j+=1
            if j>=len(days)-1 or j-i>=maxhold or tier[j]=='bassa': exitp=op[start[min(j,len(days)-1)]]; break
        nd=max(j-i,1); fu=float(f.reindex(pd.DatetimeIndex(days[i:i+nd])).fillna(0.0003).sum())*cmult if f is not None else 0.
        net=max(exitp/p0-1-2*FEE-fu,-1/L); out.append(dict(coin=c,entry=pd.Timestamp(days[i]),exit=pd.Timestamp(days[min(j,len(days)-1)]),s=sd,L=L,R=net/sd,cap=1/(L*sd))); i=j+1
    return pd.DataFrame(out)
CFG={'A30':dict(s=0.017),'C11':dict(s=None,atr_k=1.0,trail=2.0)}; OLD=lib.load(); rows=[]; n=0
for name,kw in CFG.items():
    for lab,delay,cm in (('come v4',0,1.),('costi x2',0,2.),('ritardo 1 barra (5m)',1,1.),('ritardo 12 barre (1h)',12,1.),('costi x2 + ritardo 1h',12,2.)):
        X=pd.concat([trades(c,**kw,delay=delay,cmult=cm) for c in ('BTC','ETH','SOL')]).sort_values(['entry','coin']).reset_index(drop=True); n+=1
        for sc in ('base','scelta','verifica'):
            Y=lib.scen(X,sc); rc,g=lib.kelly_coh(Y)
            rows.append(dict(flusso=name,variante=lab,periodo=sc,n=len(Y),Rm=Y.R.mean(),sd=Y.R.std(),t=lib.tstat(Y.R),SR=Y.R.mean()/Y.R.std(),kelly=rc,g_pieno=g,mese_pieno=np.expm1(g/12),mese_mezzo=np.expm1(lib.growth_coh(Y,rc/2)/12)))
        if lab=='come v4': print(name,'riproduce la cache v4:',len(X)==len(OLD[name]),'diff max R = %.2e'%np.abs(np.sort(X.R.values)-np.sort(OLD[name].R.values)).max())
print(pd.DataFrame(rows).round(4).to_string(index=False)); pd.DataFrame(rows).to_csv('costi_ritardo.csv',index=False)
import json; json.dump(dict(trials=n-2),open('trials_07.json','w'))
