"""A3 lab - simulatore di trade intraday su barre 5m dei perpetual Binance USDT-M. SIMULATO.
Convenzioni (BRIEF): segnale noto alla chiusura della barra t -> ingresso all'apertura di t+1(+ritardo);
costi 4,5 pb taker + 2 pb slippage per lato, +5 pb sullo stop, funding reale; gap oltre lo stop = apertura della barra;
leva = min(cap, 1/(stop/0.6+0.005)); perdita limitata a 1/leva (margine isolato). Stop e obiettivo nella stessa barra -> stop."""
import sys, warnings, json, os
sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from numba import njit
from gerva.data.sources import Store
st = Store('/home/user/GERVA-Capital/data_cache')
HERE = os.path.dirname(os.path.abspath(__file__))
SYMS = "BTC ETH SOL BNB XRP DOGE ADA LTC LINK AVAX".split()
FEE = 0.00045 + 0.0002; STOPSLIP = 0.0005; MM = 0.005; RATIO = 0.6; CAP = 40.0
SPLIT = pd.Timestamp('2023-01-01')
_D = {}

def load(c):
    """barre 5m complete (indice = apertura barra, UTC) + funding cumulato allineato."""
    if c in _D: return _D[c]
    b = st.get(f'v5_um_5m_{c}USDT')
    idx = pd.date_range(b.index[0], b.index[-1], freq='5min')
    miss = len(idx) - len(b)
    b = b.reindex(idx)
    b['close'] = b['close'].ffill()
    for k in ('open', 'high', 'low'): b[k] = b[k].fillna(b['close'])
    b[['volume', 'quote_volume', 'trades', 'taker_quote']] = b[['volume', 'quote_volume', 'trades', 'taker_quote']].fillna(0.0)
    f = st.get(f'bn_fund_{c}USDT').iloc[:, 0]
    f.index = f.index.floor('5min')
    cf = f.groupby(level=0).sum().reindex(idx).fillna(0.0).cumsum()
    b['cumfund'] = cf.values
    b.attrs['missing'] = miss
    _D[c] = b
    return b

@njit(cache=True)
def _sim(o, h, l, c, sig, spx, tex, cumf, tp_R, trail_R, maxhold, delay, fee, stopslip, smin, smax, cap, sigexit, be_R):
    n = len(o)
    E = np.empty(n // 2 + 1, np.int64); X = np.empty(n // 2 + 1, np.int64); SD = np.empty(n // 2 + 1, np.int8)
    S = np.empty(n // 2 + 1); R = np.empty(n // 2 + 1); W = np.empty(n // 2 + 1, np.int8); m = 0
    t = 0
    while t < n - 2 - delay:
        sd = sig[t]
        if sd == 0: t += 1; continue
        e = t + 1 + delay
        p0 = o[e]
        s = sd * (p0 - spx[t]) / p0
        if not (s == s) or s > smax: t += 1; continue
        if s < smin: s = smin
        stop = p0 * (1 - sd * s)
        tp = p0 * (1 + sd * tp_R * s) if tp_R > 0 else 0.0
        L = min(cap, 1.0 / (s / 0.6 + 0.005))
        best = p0; why = 0; px = 0.0; k = e; kx = e
        lim = tex[t]
        while True:
            if sd == 1:
                if l[k] <= stop:
                    px = min(stop, o[k]) * (1 - stopslip); why = 1; kx = k; break
                if tp_R > 0 and h[k] >= tp:
                    px = tp; why = 2; kx = k; break
                if h[k] > best: best = h[k]
            else:
                if h[k] >= stop:
                    px = max(stop, o[k]) * (1 + stopslip); why = 1; kx = k; break
                if tp_R > 0 and l[k] <= tp:
                    px = tp; why = 2; kx = k; break
                if l[k] < best: best = l[k]
            if trail_R > 0:
                ns = best * (1 - sd * trail_R * s)
                if sd * (ns - stop) > 0: stop = ns
            if be_R > 0 and sd * (best - p0) / p0 >= be_R * s:
                ns = p0 * (1 + sd * 2 * fee)
                if sd * (ns - stop) > 0: stop = ns
            if k >= n - 2 or (k - e + 1) >= maxhold or (lim >= 0 and k >= lim) or (sigexit and sig[k] == -sd):
                px = o[k + 1]; why = 3; kx = k + 1; break
            k += 1
        net = sd * (px / p0 - 1) - 2 * fee - sd * (cumf[min(kx, n - 1)] - cumf[e])
        if net < -1.0 / L: net = -1.0 / L; why = 4
        E[m] = e; X[m] = kx; SD[m] = sd; S[m] = s; R[m] = net / s; W[m] = why; m += 1
        t = k if why != 3 else k   # dopo l'uscita si riparte dalla barra di uscita (il suo segnale puo' entrare alla successiva)
        if t < e: t = e
    return E[:m], X[:m], SD[:m], S[:m], R[:m], W[:m]

WHY = np.array(['?', 'stop', 'obiettivo', 'tempo/segnale', 'liquidazione'])

def run(c, sig, spx, tex=None, tp_R=0.0, trail_R=0.0, maxhold=288, delay=0, cost=1.0, smin=0.002, smax=0.05, sigexit=False, be_R=0.0):
    """sig: int8 (+1/-1/0) per barra 5m; spx: prezzo dello stop per barra; tex: indice di barra di uscita forzata (-1 = nessuno)."""
    b = load(c); n = len(b)
    if tex is None: tex = np.full(n, -1, np.int64)
    E, X, SD, S, R, W = _sim(b['open'].values, b['high'].values, b['low'].values, b['close'].values,
                             np.asarray(sig, np.int8), np.asarray(spx, float), np.asarray(tex, np.int64), b['cumfund'].values,
                             float(tp_R), float(trail_R), int(maxhold), int(delay), FEE * cost, STOPSLIP * cost, smin, smax, CAP, bool(sigexit), float(be_R))
    ix = b.index
    return pd.DataFrame(dict(symbol=c, entry=ix[E], exit=ix[X], side=SD, stop=S, lev=np.minimum(CAP, 1 / (S / RATIO + MM)), R=R, why=WHY[W]))

def runall(fn, syms=SYMS, **kw):
    """fn(c, b) -> (sig, spx, tex|None). Restituisce i trade di tutti i simboli."""
    out = []
    for c in syms:
        b = load(c); r = fn(c, b)
        sig, spx = r[0], r[1]; tex = r[2] if len(r) > 2 else None
        out.append(run(c, sig, spx, tex, **kw))
    return pd.concat(out, ignore_index=True)

def daily(T, risk=0.01, maxopen=None):
    """rendimento giornaliero del conto: rischio `risk` per trade, P&L attribuito al giorno di uscita."""
    idx = pd.date_range('2020-01-01', '2026-10-31', freq='D')
    if len(T) == 0: return pd.Series(0.0, index=idx)
    return (risk * T.R).groupby(T.exit.dt.normalize()).sum().reindex(idx).fillna(0.0)

def blk(T):
    if len(T) < 3: return dict(n=len(T), R=np.nan, t=np.nan, td=np.nan, hit=np.nan, q=np.nan)
    d = T.R.groupby(T.entry.dt.normalize()).sum()          # R sommati per giorno di ingresso: t "a grappoli"
    nd = max((T.entry.max() - T.entry.min()).days, 1)
    full = d.reindex(pd.date_range(T.entry.min().normalize(), T.entry.max().normalize(), freq='D')).fillna(0.0)
    return dict(n=len(T), R=T.R.mean(), t=T.R.mean() / T.R.std() * np.sqrt(len(T)), td=d.mean() / d.std() * np.sqrt(len(d)) if len(d) > 2 else np.nan,
                hit=(T.R > 0).mean(), q=T.R.mean() / T.R.std(), sh=full.mean() / full.std() * np.sqrt(365) if full.std() > 0 else np.nan, nyr=len(T) / nd * 365.25)

def stats(T, label, extra=None):
    a = blk(T); i = blk(T[T.entry < SPLIT]); o = blk(T[T.entry >= SPLIT])
    r = dict(cfg=label, n=a['n'], n_anno=a.get('nyr', np.nan), stop_med=T.stop.median() if len(T) else np.nan, lev_med=T.lev.median() if len(T) else np.nan,
             R=a['R'], t=a['t'], t_g=a['td'], hit=a['hit'], RsuSig=a['q'], sh=a.get('sh', np.nan),
             R_sel=i['R'], tg_sel=i['td'], sh_sel=i.get('sh', np.nan), n_sel=i['n'], R_ver=o['R'], tg_ver=o['td'], sh_ver=o.get('sh', np.nan), n_ver=o['n'])
    if extra: r.update(extra)
    return r

def peryear(T):
    g = T.groupby(T.entry.dt.year).R
    return {int(y): (round(float(m), 3), int(n)) for y, m, n in zip(g.mean().index, g.mean().values, g.count().values)}

# ---------- mattoni per i segnali (tutti causali: valori noti alla chiusura della barra) ----------
def agg(b, rule):
    """barre aggregate; il valore e' riportato sull'ULTIMA barra 5m del blocco (quando e' noto)."""
    g = b.resample(rule, label='left', closed='left')
    a = pd.DataFrame(dict(open=g['open'].first(), high=g['high'].max(), low=g['low'].min(), close=g['close'].last(),
                          qv=g['quote_volume'].sum(), tq=g['taker_quote'].sum()))
    a.index = a.index + pd.Timedelta(rule) - pd.Timedelta('5min')     # timbro = ultima barra 5m del blocco
    return a

def atr(a, n):
    pc = a['close'].shift(1)
    tr = np.maximum(a['high'] - a['low'], np.maximum((a['high'] - pc).abs(), (a['low'] - pc).abs()))
    return tr.rolling(n).mean()

def to5(s, b):
    """serie su barre aggregate -> barre 5m: valida solo sulla barra di timbro (NaN altrove)."""
    return s.reindex(b.index)

class Trials:
    def __init__(self, name): self.name = name; self.rows = []
    def add(self, T, label, **extra):
        r = stats(T, label, extra); self.rows.append(r); return r
    def table(self):
        return pd.DataFrame(self.rows)
    def save(self):
        json.dump(dict(n=len(self.rows)), open(os.path.join(HERE, f'trials_{self.name}.json'), 'w'))

COLS = ['cfg', 'n', 'n_anno', 'stop_med', 'lev_med', 'R', 't', 't_g', 'hit', 'R_sel', 'tg_sel', 'sh_sel', 'R_ver', 'tg_ver', 'sh_ver']
def show(df, cols=COLS, sort='tg_sel', top=None):
    d = df.sort_values(sort, ascending=False) if sort else df
    if top: d = d.head(top)
    with pd.option_context('display.width', 280, 'display.max_colwidth', 70, 'display.max_rows', 500):
        print(d[cols].round(3).to_string(index=False))

# ---------- sovrapposizione con il libro dei trade esistente ----------
_BOOK = {}
def book():
    if not _BOOK:
        import pickle
        F = pd.read_parquet('/home/user/GERVA-Capital/research/v5/v4/fondo_serie.parquet')
        ALL = pickle.load(open('/home/user/GERVA-Capital/research/v5/v4/_cache/trades.pkl', 'rb'))
        X = ALL[('atr1.0', ('alta',), 2.0, 'long')]
        days = set()
        for a, z in zip(pd.to_datetime(X.entry), pd.to_datetime(X.exit)):
            days.update(pd.date_range(a, z, freq='D'))
        _BOOK.update(F=F, X=X, days=pd.DatetimeIndex(sorted(days)))
    return _BOOK
def overlap(T, risk=0.01):
    """quota dei trade aperti in giorni in cui il libro 11x e' in posizione; correlazione mensile e giornaliera con trade11 e con il libro giornaliero."""
    B = book(); F = B['F']; d = daily(T, risk).reindex(F.index).fillna(0.0)
    d = d['2020-01-01':]; f = F.loc[d.index]
    mm = lambda x: (1 + x).resample('ME').prod() - 1
    inb = T.entry.dt.normalize().isin(B['days'])
    cal = pd.date_range('2020-01-01', '2026-10-31', freq='D'); base = cal.isin(B['days']).mean()
    return dict(quota_in_giorni_libro=float(inb.mean()), quota_calendario_libro=float(base), R_in=float(T.R[inb].mean()), R_fuori=float(T.R[~inb].mean()),
                corr_mese_trade11=float(mm(d).corr(mm(f['trade11']))), corr_mese_new=float(mm(d).corr(mm(f['new']))), corr_giorno_trade11=float(d.corr(f['trade11'])))
