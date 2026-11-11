"""B3 - laboratorio comune: sottostanti total return, serie a leva sintetiche, metriche. TUTTO SIMULATO."""
import sys, warnings, json
sys.path.insert(0, "/home/user/GERVA-Capital")
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from gerva.data.sources import Store
ST = Store("/home/user/GERVA-Capital/data_cache")
SEL_END = "2022-12-31"; VER_START = "2023-01-01"

def y(sym):
    return ST.get(f"v6_b3_y_{sym}")

def cash_daily(idx):
    """T-bill 13 settimane (^IRX, % annuo) -> rendimento per seduta (giorni di calendario/360)."""
    irx = y("^IRX")["close"].reindex(idx).ffill().bfill() / 100.0
    dc = pd.Series(idx, index=idx).diff().dt.days.fillna(1).clip(1, 5)
    return (irx.shift(1).bfill() * dc / 360.0).rename("cash"), dc

def underlying():
    """Rendimenti giornalieri total return (lordi di TER del fondo usato come fonte).
    NDX: QQQ adj (+0,20% TER) dal 1999-03; prima ^NDX prezzo + dividendo 0,3%/anno (STIMA).
    SPX: SPY adj (+0,09%) dal 1993-02; VFINX adj (+0,25%) 1980-1993; ^GSPC + 4,0%/anno 1970-1979 (STIMA).
    IXIC: ^IXIC prezzo + 1%/anno (STIMA) dal 1971. BOND: VUSTX adj (Treasury lunghi, dal 1986-05). ORO: GC=F dal 2000-08. DAX: ^GDAXI (indice di performance)."""
    spx_p = y("^GSPC")["close"].pct_change()
    idx = spx_p.index[spx_p.index >= "1970-01-05"]
    out = pd.DataFrame(index=idx)
    spy = y("SPY")["adj"].pct_change() + 0.0009 / 252
    vf = y("VFINX")["adj"].pct_change() + 0.0025 / 252
    s = spx_p + 0.040 / 252
    s.loc[vf.index[1]:] = vf.reindex(s.loc[vf.index[1]:].index).fillna(spx_p)
    s.loc[spy.index[1]:] = spy.reindex(s.loc[spy.index[1]:].index).fillna(spx_p)
    out["SPX"] = s.reindex(idx)
    ndx = y("^NDX")["close"].pct_change() + 0.003 / 252
    q = y("QQQ")["adj"].pct_change() + 0.0020 / 252
    ndx.loc[q.index[1]:] = q.reindex(ndx.loc[q.index[1]:].index).fillna(ndx)
    out["NDX"] = ndx.reindex(idx)
    out["IXIC"] = (y("^IXIC")["close"].pct_change() + 0.01 / 252).reindex(idx)
    out["BOND"] = y("VUSTX")["adj"].pct_change().reindex(idx)
    out["GOLD"] = y("GC=F")["close"].pct_change().reindex(idx)
    out["DAX"] = y("^GDAXI")["close"].pct_change().reindex(idx)
    out["VIX"] = y("^VIX")["close"].reindex(idx)
    c, dc = cash_daily(idx)
    out["cash"] = c; out["dc"] = dc
    return out

def lev(r, cash, dc, k, ter=0.0, spread=0.0):
    """k x giornaliero: k*r - (k-1)*(cash + spread*dc/360) - ter*dc/365. Oro (future): il finanziamento e' gia' nel prezzo -> usare lev_fut."""
    return k * r - (k - 1) * (cash + spread * dc / 360.0) - ter * dc / 365.0

# prodotti (FATTO dai prospetti; spread = costo di finanziamento sopra il tasso a breve, STIMA tarata sui prodotti reali in 01)
PROD = {  # nome: (k, ter, spread)
    "2x_ETF": (2, 0.0060, 0.0040),   # Amundi LQQ / Xtrackers 2x: TER 0,60%, swap
    "3x_ETP": (3, 0.0075, 0.0100),   # WisdomTree QQQ3 / 3USL: 0,75% + swap giornaliero
    "5x_ETP": (5, 0.0075, 0.0250),   # Leverage Shares 5QQQ / 5SPY: 0,75% + margine broker
}

def stats(r, cash=None, name=""):
    r = r.dropna()
    if len(r) < 60: return {}
    eq = (1 + r).cumprod()
    yrs = len(r) / 252.0
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if eq.iloc[-1] > 0 else -1.0
    vol = r.std() * np.sqrt(252)
    ex = r - (cash.reindex(r.index) if cash is not None else 0)
    sh = ex.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan
    peak = eq.cummax(); dd = eq / peak - 1
    m = (1 + r).groupby([r.index.year, r.index.month]).prod() - 1
    uw = (dd < 0).astype(int); run = uw.groupby((uw == 0).cumsum()).cumsum()
    return dict(nome=name, anni=round(yrs, 1), CAGR=cagr, vol=vol, Sharpe=sh, maxDD=dd.min(), mese_peggiore=m.min(),
                mese_medio=m.mean(), mese_mediano=m.median(), mesi_neg=(m < 0).mean(),
                sott_acqua_max_anni=run.max() / 252.0, sott_acqua_pct=(dd < -0.05).mean(),
                mese_comp=(1 + cagr) ** (1 / 12) - 1 if cagr > -1 else -1)

def split(r, cash=None, name=""):
    return {"intero": stats(r, cash, name), "scelta": stats(r.loc[:SEL_END], cash, name), "verifica": stats(r.loc[VER_START:], cash, name)}

def fmt(d, keys=("CAGR", "vol", "Sharpe", "maxDD", "mese_peggiore", "sott_acqua_max_anni")):
    if not d: return "   n/d"
    o = []
    for k in keys:
        v = d[k]
        o.append(f"{v:6.2f}" if k in ("Sharpe", "sott_acqua_max_anni") else f"{v*100:7.1f}%")
    return " ".join(o)

def sim_weights(R, W, cost, lag=2, band=0.0, cash=None):
    """Portafoglio con pesi-obiettivo W (decisi alla chiusura t), eseguiti con `lag` sedute di ritardo
    (lag=2: eseguito alla chiusura di t+1; lag=1: alla chiusura di t). I pesi derivano fra un ribilanciamento e l'altro;
    si ribilancia quando un peso dista dall'obiettivo piu' di `band` (assoluto). Il resto e' cassa (T-bill).
    cost: dict/Series costo per lato per unita' di capitale scambiato in quell'attivo. Ritorna (rendimenti netti, giro annuo)."""
    cols = list(W.columns)
    Rv = R[cols].fillna(0).values; Wt = W.shift(lag).fillna(0).values
    cs = cash.reindex(R.index).fillna(0).values if cash is not None else np.zeros(len(R))
    cv = np.array([cost[c] for c in cols])
    n = len(R); out = np.zeros(n); w = np.zeros(len(cols)); turn = 0.0
    for t in range(n):
        tgt = Wt[t]
        # ribilanciamento a inizio giornata t (cioe' alla chiusura di t-1)
        if np.abs(w - tgt).max() > band or (np.abs(tgt).sum() == 0 and np.abs(w).sum() > 0):
            tc = (np.abs(tgt - w) * cv).sum(); turn += np.abs(tgt - w).sum(); w = tgt.copy()
        else:
            tc = 0.0
        g = (w * Rv[t]).sum() + (1 - w.sum()) * cs[t]
        out[t] = (1 - tc) * (1 + g) - 1
        tot = 1 + g
        w = w * (1 + Rv[t]) / tot if tot > 0 else w * 0
    return pd.Series(out, index=R.index), turn / (n / 252.0)
