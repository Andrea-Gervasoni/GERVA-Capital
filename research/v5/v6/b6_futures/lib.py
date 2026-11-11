"""B6 - libreria: costruzione dei rendimenti in eccesso puliti dai salti di roll, metriche, portafoglio."""
import sys, glob, os
sys.path.insert(0, "/home/user/GERVA-Capital")
import numpy as np, pandas as pd
ROOT = "/home/user/GERVA-Capital"
CACHE = f"{ROOT}/data_cache"
FRED = "/tmp/claude-0/-home-user-GERVA-Capital/48f6139d-0078-5bc0-83e9-48c012a4ffa3/scratchpad/fred"
SEL_END, VER_START = "2022-12-31", "2023-01-01"

def raw(sym):
    d = pd.read_parquet(f"{CACHE}/v5_b6_yahoo_1d_{sym}.parquet")
    return d[d.index >= "1999-01-01"]

def fred(name):
    p = f"{CACHE}/v5_b6_fred_{name}.parquet"
    if os.path.exists(p):
        return pd.read_parquet(p).iloc[:, 0]
    d = pd.read_csv(f"{FRED}/{name}.csv", index_col=0, parse_dates=True).iloc[:, 0]
    d = pd.to_numeric(d, errors="coerce").dropna()
    d.to_frame(name).to_parquet(p)
    return d

def daily_rate(name, idx):
    """tasso annuo % -> rendimento per giorno di calendario accumulato sull'indice (ACT/360), noto il giorno prima"""
    r = fred(name).reindex(pd.date_range("1998-01-01", idx[-1])).ffill().shift(1) / 100.0
    days = pd.Series(idx, index=idx).diff().dt.days.fillna(1)
    return (r.reindex(idx).ffill() * days / 360.0).fillna(0.0)

# ---------------- calendario dei roll: ultimo giorno di contrattazione (LTD) del contratto in scadenza ----------
H, M, U, Z = 3, 6, 9, 12
QTR = [3, 6, 9, 12]; ALL = list(range(1, 13))
RULES = {  # simbolo: (mesi contratto, regola, parametro)
    "ES=F": (QTR, "fri3", 0), "NQ=F": (QTR, "fri3", 0), "YM=F": (QTR, "fri3", 0), "RTY=F": (QTR, "fri3", 0),
    "ZB=F": (QTR, "before_last", 7), "ZN=F": (QTR, "before_last", 7), "ZF=F": (QTR, "before_last", 0), "ZT=F": (QTR, "before_last", 0),
    "CL=F": (ALL, "cl", 0), "NG=F": (ALL, "prev_before_last", 2), "HO=F": (ALL, "prev_before_last", 0), "RB=F": (ALL, "prev_before_last", 0),
    "BZ=F": (ALL, "bz", 0),
    "ZC=F": ([3, 5, 7, 9, 12], "pre15", 0), "ZW=F": ([3, 5, 7, 9, 12], "pre15", 0),
    "ZS=F": ([1, 3, 5, 7, 8, 9, 11], "pre15", 0), "ZL=F": ([1, 3, 5, 7, 8, 9, 10, 12], "pre15", 0), "ZM=F": ([1, 3, 5, 7, 8, 9, 10, 12], "pre15", 0),
    "KC=F": ([3, 5, 7, 9, 12], "before_last", 8), "CC=F": ([3, 5, 7, 9, 12], "before_last", 11), "CT=F": ([3, 5, 7, 10, 12], "before_last", 16),
    "SB=F": ([3, 5, 7, 10], "prev_before_last", 0),
    "LE=F": ([2, 4, 6, 8, 10, 12], "before_last", 0), "HE=F": ([2, 4, 5, 6, 7, 8, 10, 12], "nth", 9),
    "BTC=F": (ALL, "lastfri", 0), "ETH=F": (ALL, "lastfri", 0),
}

def ltd_dates(sym, idx):
    months, rule, k = RULES[sym]
    s = pd.Series(idx, index=idx)
    grp = {key: g.values for key, g in s.groupby([idx.year, idx.month])}
    out = []
    for (y, m) in sorted(grp):
        if m not in months: continue
        days = pd.DatetimeIndex(grp[(y, m)])
        pm = (y, m - 1) if m > 1 else (y - 1, 12)
        pdays = pd.DatetimeIndex(grp[pm]) if pm in grp else None
        try:
            if rule == "fri3":
                f = pd.Timestamp(y, m, 1); f += pd.Timedelta(days=(4 - f.weekday()) % 7 + 14)
                d = days[days <= f][-1]
            elif rule == "before_last": d = days[-1 - k]
            elif rule == "prev_before_last": d = pdays[-1 - k]
            elif rule == "nth": d = days[k]
            elif rule == "pre15": d = days[days.day < 15][-1]
            elif rule == "lastfri":
                f = days[days.weekday == 4]; d = f[-1]
            elif rule == "cl":
                q = pdays[pdays.day <= 25]; ref = q[-1]
                pos = len(q) - 1
                d = q[pos - 3]
            elif rule == "bz":
                if (y, m) < (2016, 3):   # 15 giorni prima del primo del mese di consegna
                    lim = pd.Timestamp(y, m, 1) - pd.Timedelta(days=16)
                    d = idx[idx <= lim][-1]
                else:                    # ultimo giorno lavorativo del secondo mese precedente
                    pm2 = (pm[0], pm[1] - 1) if pm[1] > 1 else (pm[0] - 1, 12)
                    d = pd.DatetimeIndex(grp[pm2])[-1]
            out.append(d)
        except Exception:
            continue
    return pd.DatetimeIndex(sorted(set(out)))

def roll_days(sym, d, offset=0):
    """giorno in cui la serie Yahoo mostra il nuovo contratto = giorno di borsa successivo all'LTD (+offset calibrato)"""
    idx = d.index
    ltd = ltd_dates(sym, idx)
    pos = idx.get_indexer(ltd) + 1 + offset
    pos = pos[(pos > 0) & (pos < len(idx))]
    return idx[pos]

ADAPT = {"ZC=F": (-10, 1), "ZW=F": (-10, 1), "ZS=F": (-10, 1), "ZM=F": (-10, 1), "ZL=F": (-10, 1), "KC=F": (-10, 1), "CC=F": (-10, 1), "CT=F": (-10, 1),
         "ZF=F": (-8, 1), "ZT=F": (-8, 1), "HE=F": (-2, 2), "LE=F": (-2, 2), "SB=F": (-2, 2), "NG=F": (-2, 2), "RB=F": (-2, 2)}

def roll_days_final(sym, d):
    """regola fissa; per i mercati in ADAPT (dove Yahoo cambia contratto in giorni non costanti e il salto di roll e'
    molto maggiore del rumore notturno) si prende, nella finestra attorno alla regola, il giorno col salto notturno massimo
    purche' superi 3 volte la mediana normale."""
    rd = roll_days(sym, d, 0)
    if sym not in ADAPT: return rd
    a, b = ADAPT[sym]
    g = (d.open / d.close.shift(1) - 1).abs().values; base = np.nanmedian(g)
    pos = d.index.get_indexer(rd); out = []
    for p in pos:
        lo, hi = max(p + a, 1), min(p + b + 1, len(g))
        k = lo + int(np.nanargmax(g[lo:hi]))
        out.append(k if g[k] > 3 * base else p)
    return d.index[sorted(set(out))]

def fix_ticks(d):
    """tick errati: chiusura che si scosta >30% e il giorno dopo torna entro il 5% del valore precedente"""
    d = d.copy(); c = d.close
    bad = ((c / c.shift(1) - 1).abs() > 0.30) & ((c.shift(-1) / c.shift(1) - 1).abs() < 0.05)
    for i in d.index[bad]:
        p = d.index.get_loc(i); d.iloc[p, d.columns.get_loc("close")] = d.close.iloc[p - 1]
    return d, int(bad.sum())

def clean_bars(d):
    d, _ = fix_ticks(d)
    for c in ("open", "high", "low"):
        d[c] = d[c].where(d[c] > 0, d["close"])
    d["high"] = d[["open", "high", "low", "close"]].max(axis=1)
    d["low"] = d[["open", "high", "low", "close"]].min(axis=1)
    return d

def adjust(d, rdays):
    """rendimento pulito: nei giorni di roll si usa apertura->chiusura del nuovo contratto (si perde la notte).
    Restituisce barre retro-rettificate (rapporto) coerenti col rendimento pulito e la serie dei salti rimossi."""
    d = clean_bars(d)
    r = d.close.pct_change()
    isr = d.index.isin(rdays)
    gap = (d.open / d.close.shift(1) - 1).where(isr)
    r = r.where(~isr, d.close / d.open - 1).fillna(0.0)
    adjc = (1 + r).cumprod(); adjc = adjc / adjc.iloc[-1] * d.close.iloc[-1]
    f = adjc / d.close
    out = pd.DataFrame({"open": d.open * f, "high": d.high * f, "low": d.low * f, "close": adjc, "ret": r, "raw_close": d.close, "volume": d.volume})
    return out, gap.dropna()

def carry_adjust(d, carry_daily):
    """serie grezza ~ spot (ogni contratto converge allo spot a scadenza): eccesso = grezzo + carry giornaliero"""
    d = clean_bars(d)
    r = (d.close.pct_change().fillna(0.0) + carry_daily.reindex(d.index).fillna(0.0))
    adjc = (1 + r).cumprod(); adjc = adjc / adjc.iloc[-1] * d.close.iloc[-1]
    f = adjc / d.close
    return pd.DataFrame({"open": d.open * f, "high": d.high * f, "low": d.low * f, "close": adjc, "ret": r, "raw_close": d.close, "volume": d.volume})

# ---------------- metriche ----------------
def stats(r, name=None, ppy=252):
    r = r.dropna()
    if len(r) < 60 or r.std() == 0: return dict(n=len(r))
    eq = (1 + r).cumprod(); yrs = len(r) / ppy
    m = (1 + r).groupby([r.index.year, r.index.month]).prod() - 1
    return dict(sharpe=r.mean() / r.std() * np.sqrt(ppy), cagr=eq.iloc[-1] ** (1 / yrs) - 1, vol=r.std() * np.sqrt(ppy),
                mdd=(eq / eq.cummax() - 1).min(), skew_m=m.skew(), skew_d=r.skew(), n=len(r))

PERIODS = {"tutto": (None, None), "2000-09": (None, "2009-12-31"), "2010-19": ("2010-01-01", "2019-12-31"),
           "2020-26": ("2020-01-01", None), "selezione": (None, SEL_END), "verifica": (VER_START, None)}

def table(r, label=""):
    rows = []
    for k, (a, b) in PERIODS.items():
        s = stats(r.loc[a:b]); s["periodo"] = k; rows.append(s)
    t = pd.DataFrame(rows).set_index("periodo")[["sharpe", "cagr", "vol", "mdd", "skew_m"]]
    return t

def fmt(t):
    t = t.copy()
    for c in ("cagr", "vol", "mdd"):
        if c in t: t[c] = (t[c] * 100).round(1)
    return t.round(2)

def ewvol(ret, span=60, minp=30):
    return ret.ewm(span=span, min_periods=minp).std() * np.sqrt(252)

# ---------------- universo e specifiche dei contratti (micro dove esiste) ----------------
# chiave pannello: (settore, contratto IBKR, moltiplicatore, valuta, tick in punti prezzo, commissione tutto compreso per lato in valuta, roll/anno, margine % nozionale STIMA)
UNI = {
 "ES_etf": ("EQ", "MES", 5, "USD", 0.25, 0.62, 4, .07), "NQ_etf": ("EQ", "MNQ", 2, "USD", 0.25, 0.62, 4, .08), "YM_etf": ("EQ", "MYM", 0.5, "USD", 1.0, 0.62, 4, .07),
 "RTY_etf": ("EQ", "M2K", 5, "USD", 0.1, 0.62, 4, .08), "^N225": ("EQ", "CME Micro Nikkei USD", 0.5, "USD", 5.0, 0.62, 4, .08),
 "^GDAXI": ("EQ", "Eurex FDXS", 1, "EUR", 1.0, 0.50, 4, .07), "^STOXX50E": ("EQ", "Eurex FSXE", 1, "EUR", 0.5, 0.50, 4, .07),
 "ZT=F": ("RATE", "Micro 2Y Yield (DV01 $10)", None, "USD", None, 0.57, 12, .006), "ZF=F": ("RATE", "Micro 5Y Yield", None, "USD", None, 0.57, 12, .012),
 "ZN=F": ("RATE", "Micro 10Y Yield", None, "USD", None, 0.57, 12, .02), "ZB=F": ("RATE", "Micro 30Y Yield", None, "USD", None, 0.57, 12, .035),
 "6E=F": ("FX", "M6E", 12500, "USD", 0.0001, 0.41, 4, .025), "6J=F": ("FX", "MJY", 1250000, "USD", 0.000001, 0.41, 4, .035), "6B=F": ("FX", "M6B", 6250, "USD", 0.0001, 0.41, 4, .03),
 "6A=F": ("FX", "M6A", 10000, "USD", 0.0001, 0.41, 4, .03), "6C=F": ("FX", "MCD", 10000, "USD", 0.0001, 0.41, 4, .025), "6S=F": ("FX", "MSF", 12500, "USD", 0.0001, 0.41, 4, .035),
 "GC=F": ("METAL", "MGC", 10, "USD", 0.1, 0.77, 6, .08), "SI=F": ("METAL", "SIL", 1000, "USD", 0.005, 1.27, 5, .12), "HG=F": ("METAL", "MHG", 2500, "USD", 0.0005, 0.87, 5, .09),
 "CL=F": ("ENERGY", "MCL", 100, "USD", 0.01, 0.77, 12, .12), "NG=F": ("ENERGY", "MNG", 1000, "USD", 0.001, 0.77, 12, .20),
 "HO=F": ("ENERGY", "MHO", 4200, "USD", 0.0001, 0.77, 12, .12), "RB=F": ("ENERGY", "MRB", 4200, "USD", 0.0001, 0.77, 12, .12),
 "ZC=F": ("AGRI", "MZC", 5, "USD", 0.5, 0.85, 5, .06), "ZW=F": ("AGRI", "MZW", 5, "USD", 0.5, 0.85, 5, .08), "ZS=F": ("AGRI", "MZS", 5, "USD", 0.5, 0.85, 7, .06),
 "ZM=F": ("AGRI", "MZM", 10, "USD", 0.2, 0.85, 8, .07), "ZL=F": ("AGRI", "MZL", 60, "USD", 0.02, 0.85, 8, .07),
 "KC=F": ("SOFT", "KC intero", 375, "USD", 0.05, 2.50, 5, .10), "SB=F": ("SOFT", "SB intero", 1120, "USD", 0.01, 2.50, 4, .08),
 "CC=F": ("SOFT", "CC intero", 10, "USD", 1.0, 2.50, 5, .12), "CT=F": ("SOFT", "CT intero", 500, "USD", 0.01, 2.50, 5, .08),
 "LE=F": ("MEAT", "LE intero", 400, "USD", 0.025, 2.90, 6, .05), "HE=F": ("MEAT", "HE intero", 400, "USD", 0.025, 2.90, 8, .07),
 "BTC=F": ("CRYPTO", "MBT", 0.1, "USD", 5.0, 3.00, 12, .40), "ETH=F": ("CRYPTO", "MET", 0.1, "USD", 0.5, 0.50, 12, .45),
}
RATE_DUR = {"ZT=F": 1.9, "ZF=F": 4.3, "ZN=F": 6.5, "ZB=F": 11.0}   # durata approssimata del future (STIMA)
SECTORS = ["EQ", "RATE", "FX", "METAL", "ENERGY", "AG", "CRYPTO"]   # AG = cereali + coloniali + carni
SUB = {"AGRI": "AG", "SOFT": "AG", "MEAT": "AG"}
MICRO = None

def load_panel():
    P = {k: pd.read_parquet(f"{CACHE}/v5_b6_panel_{k}.parquet") for k in UNI}
    end = max(p.index[-1] for p in P.values())
    idx = pd.bdate_range("2000-01-03", end)
    R = pd.DataFrame({k: p.ret.iloc[1:].reindex(idx) for k, p in P.items()})
    first = {k: P[k].index[1] for k in P}
    for k in R:   # dentro la vita del mercato i giorni mancanti valgono 0
        m = (R.index >= first[k]) & R[k].isna(); R.loc[m, k] = 0.0
    C = pd.DataFrame({k: p.close.reindex(idx).ffill() for k, p in P.items()})
    return P, R, C

def specs(P, eurusd=None):
    """costo per lato in bp del nozionale = (commissione + 1 tick) / nozionale, ai prezzi correnti"""
    if eurusd is None: eurusd = float(raw("EURUSD=X").close.iloc[-1])
    rows = {}
    for k, (sec, name, mult, ccy, tick, comm, rolls, marg) in UNI.items():
        px = float(P[k].raw_close.iloc[-1])
        fx = eurusd if ccy == "EUR" else 1.0
        if sec == "RATE":
            notional = 10.0 / (RATE_DUR[k] * 1e-4); tickval = 1.0
        elif sec == "FX":
            notional = mult * px; tickval = mult * tick
        elif k in ("ZC=F", "ZW=F", "ZS=F"):
            notional = mult * px; tickval = mult * tick      # prezzo in cent/bushel, 500 bushel -> $5 per cent
        elif k == "ZL=F": notional = mult * px; tickval = mult * tick
        elif k == "ZM=F": notional = mult * px; tickval = mult * tick
        elif k in ("KC=F", "SB=F", "CT=F", "LE=F", "HE=F"): notional = mult * px; tickval = mult * tick
        elif k.endswith("_etf"):
            idxpx = {"ES_etf": "^GSPC", "NQ_etf": "^NDX", "YM_etf": "^DJI", "RTY_etf": "^RUT"}[k]
            px = float(raw(idxpx).close.iloc[-1]); notional = mult * px; tickval = mult * tick
        else: notional = mult * px * fx; tickval = mult * tick * fx; comm = comm * fx
        rows[k] = dict(settore=SUB.get(sec, sec), sotto=sec, micro=sec not in ("SOFT", "MEAT"), contratto=name, prezzo=px, nozionale_usd=notional, tick_usd=tickval, comm_usd=comm,
                       costo_bp=(comm + tickval) / notional * 1e4, roll_anno=rolls, margine=marg)
    return pd.DataFrame(rows).T
