exec(open('/tmp/lab3/n1.py').read().split("# 1. trend dimensionato")[0])
import math
btc_r=ret['BTC']; adv=dvol.rolling(30,min_periods=20).mean(); btc_up=close['BTC']>close['BTC'].rolling(100).mean()
def xsW(score,top=5,uni=20,reb=7):
    W=pd.DataFrame(0.0,index=close.index,columns=close.columns); last=None
    for i,d in enumerate(close.index):
        if i%reb==0:
            ok=adv.loc[d].notna()&score.loc[d].notna(); liq=adv.loc[d][ok].nlargest(uni).index; s=score.loc[d][liq]
            pick=s[s>0].nlargest(top).index; last=pd.Series(0.0,index=close.columns)
            if len(pick) and bool(btc_up.get(d,False)): last[pick]=1/top
        if last is not None: W.loc[d]=last
    return W
def scaled(r): v=(r.rolling(60,min_periods=30).std()*math.sqrt(365)).shift(1); return r*(0.25/v.where(v>0)).clip(upper=1).fillna(0.3)
def rmom(bw,lb):
    beta=ret.rolling(bw).cov(btc_r).div(btc_r.rolling(bw).var(),axis=0); res=ret.sub(beta.mul(btc_r,axis=0))
    return res.rolling(lb).sum()/res.rolling(lb).std()/math.sqrt(lb)
def sh(r,sl): return M.sharpe(r.loc[sl],rf,365)
A,I,O=slice('2018',None),slice('2018',SPL),slice(SPL,None)
print('sensibilita ai parametri (Sharpe tutto / scelta / verifica):')
out={}
for bw in (30,60,90):
    for lb in (14,28,56):
        r=scaled(run(xsW(rmom(bw,lb)),ret,0.0,C,periods=365,band=0.03).ret.loc['2018':]); out[(bw,lb)]=r
        print(f' beta {bw}g, momentum {lb}g: {sh(r,A):.2f} / {sh(r,I):.2f} / {sh(r,O):.2f}')
ens=pd.concat(out.values(),axis=1).mean(axis=1); print(f' insieme delle 9: {sh(ens,A):.2f} / {sh(ens,I):.2f} / {sh(ens,O):.2f}')
Wb=xsW(rmom(60,28)); r0=scaled(run(Wb,ret,0.0,C,periods=365,band=0.03).ret.loc['2018':])
r2=scaled(run(Wb,ret,0.0,Costs(trade=0.006,cash_haircut=1.0),periods=365,band=0.03).ret.loc['2018':]); rl=scaled(run(Wb,ret,0.0,C,lag=2,periods=365,band=0.03).ret.loc['2018':])
print(f'base {sh(r0,A):.2f} | costi doppi {sh(r2,A):.2f} | ritardo 1g {sh(rl,A):.2f} | senza top>0: n/a')
s=M.summary(r0,rf,365); print({k:round(s[k],3) for k in ('cagr','vol','sharpe','max_dd','mese_peggiore')})
x=r0.reindex(S0.index).fillna(0); ex=ens.reindex(S0.index).fillna(0)
print('correlazione mensile con CR-XSMOM:',round(((1+x).resample('ME').prod()-1).corr((1+S0['CR-XSMOM']).resample('ME').prod()-1),2),'con CR-TREND:',round(((1+x).resample('ME').prod()-1).corr((1+S0['CR-TREND']).resample('ME').prod()-1),2))
def P(S): p=combine(S,risk_parity(S)); return p
for lab,S in (('attuale',S0),('+ residuo come quinta',S0.assign(**{'CR-RESID':x})),('residuo AL POSTO di CR-XSMOM',S0.drop(columns='CR-XSMOM').assign(**{'CR-RESID':x})),('+ insieme dei 9 residui come quinta',S0.assign(**{'CR-RESID':ex})),('meta XSMOM + meta residuo in una sola strategia',S0.assign(**{'CR-XSMOM':0.5*S0['CR-XSMOM']+0.5*x}))):
    p=P(S); s=M.summary(p,rf,365); print(f'{lab}: Sharpe {sh(p,slice(None,None)):.2f} / {sh(p,slice(None,SPL)):.2f} / {sh(p,O):.2f} | CAGR {s["cagr"]:.1%} vol {s["vol"]:.1%} caduta {s["max_dd"]:.1%}')
pd.to_pickle(dict(resid=r0,ens=ens),'/tmp/lab3/resid.pkl')
