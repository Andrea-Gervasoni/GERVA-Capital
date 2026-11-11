import json, numpy as np, pandas as pd
ROOT='/home/user/GERVA-Capital'
def serie(d, key='all'):
    """da {accountValueHistory,pnlHistory} a DataFrame [av,pnl] indicizzato sul tempo (UTC)."""
    p=d.get(key)
    if not p or not p['accountValueHistory']: return None
    a=pd.Series({x[0]:float(x[1]) for x in p['accountValueHistory']}); q=pd.Series({x[0]:float(x[1]) for x in p['pnlHistory']})
    df=pd.DataFrame({'av':a,'pnl':q}).dropna(); df.index=pd.to_datetime(df.index,unit='ms'); df=df[~df.index.duplicated(keep='last')].sort_index()
    return df
def rendimenti(df, floor=100.0):
    """rendimento per intervallo = dPnL / capitale medio investito (Dietz: av iniziale + meta' dei flussi).
    Intervalli con capitale < floor USD: NaN (conto vuoto)."""
    dp=df.pnl.diff(); flow=df.av.diff()-dp; base=df.av.shift()+0.5*flow
    base=np.maximum(base, df.av.shift()*0.5)   # un prelievo a meta' non riduce la base sotto meta' capitale iniziale
    r=dp/base; r[base<floor]=np.nan
    return r.clip(lower=-1.0).iloc[1:]
def tbill():
    s=pd.read_parquet(ROOT+'/data_cache/yahoo_1d_^IRX.parquet')['close']/100.0; s.index=pd.to_datetime(s.index)
    return (s.reindex(pd.date_range(s.index[0],s.index[-1])).ffill()/365.0)   # rendimento giornaliero di calendario
def fondo():
    f=pd.read_parquet(ROOT+'/research/v5/v5/a10_sistema/returns.parquet'); f.index=pd.to_datetime(f.index); return f[['B_cassa_in_tbill','C1_mtm_limiti','C3_mtm_limiti_debito_reale']]
def stat(r, per_year):
    r=r.dropna(); eq=(1+r).cumprod(); n=len(r)
    cagr=eq.iloc[-1]**(per_year/n)-1; vol=r.std()*np.sqrt(per_year); dd=(eq/eq.cummax()-1).min()
    return dict(n=n,cagr=cagr,vol=vol,sharpe=r.mean()/r.std()*np.sqrt(per_year) if r.std()>0 else np.nan,maxdd=dd,worst=r.min())
