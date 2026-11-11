"""A1 - libreria: simulatore (stessa convenzione di research/v5/v4/leva_trade_isolato.py, riscritto in numba e validato contro l'originale),
componenti dell'indicatore, utilita'. SIMULATO."""
import sys, warnings; sys.path.insert(0, '/home/user/GERVA-Capital'); sys.path.insert(0, '/home/user/GERVA-Capital/research/v5/v4')
warnings.filterwarnings('ignore')
import numpy as np, pandas as pd, numba as nb
from gerva.data import Store
st = Store('/home/user/GERVA-Capital/data_cache')
FEE = 0.00045 + 0.0002; STOPSLIP = 0.0005; MM = 0.005; RATIO = 0.6
SPLIT = pd.Timestamp('2023-01-01')
def levmax(s, cap=50): return min(cap, 1 / (s / RATIO + MM))

@nb.njit(cache=True)
def _sim(op, hi, lo, start, end, i, nday, sd, trail, maxhold, exitflag, side, liqdist, stopslip, delay):
    """Un trade dal giorno i. Ritorna (p0, exitp, j, why) why: 0 tempo/segnale, 1 stop, 2 liquidazione."""
    k0 = start[i] + delay
    p0 = op[k0]; stop = p0 * (1 - side * sd); best = p0; j = i; why = 0; exitp = np.nan
    liq = p0 * (1 - side * liqdist)
    while True:
        a = k0 if j == i else start[j]; z = end[j]
        for k in range(a, z):
            o = op[k]; h = hi[k]; l = lo[k]
            adv = l if side == 1 else h
            if side * (adv - stop) <= 0:
                px = min(stop, o) if side == 1 else max(stop, o)
                px = px * (1 - side * stopslip)
                if side * (px - liq) <= 0: px = liq; why = 2
                else: why = 1
                exitp = px; break
            fav = h if side == 1 else l
            if trail > 0 and side * (fav - best) > 0:
                best = fav; ns = best * (1 - side * trail * sd)
                if side * (ns - stop) > 0: stop = ns
        if why > 0: break
        j += 1
        if j >= nday - 1 or j - i >= maxhold or exitflag[j]:
            jj = min(j, nday - 1); exitp = op[start[jj] + (delay if start[jj] + delay < end[jj] else 0)]; break
    return p0, exitp, j, why

class Path:
    """Percorso intraday (5m o 1h) + barre giornaliere di un simbolo."""
    def __init__(self, bars, fund_daily=None):
        self.b = bars; day = bars.index.normalize(); g = bars.groupby(day)
        self.d = pd.DataFrame(dict(open=g['open'].first(), high=g['high'].max(), low=g['low'].min(), close=g['close'].last()))
        self.op = bars['open'].values; self.hi = bars['high'].values; self.lo = bars['low'].values
        dn = day.values; self.days = self.d.index.values
        self.start = np.searchsorted(dn, self.days); self.end = np.append(self.start[1:], len(dn))
        self.atr = ((self.d['high'] - self.d['low']) / self.d['close']).rolling(14).mean().shift(1).values
        f = fund_daily
        self.fund = np.full(len(self.days), 0.0003) if f is None else f.reindex(self.d.index).fillna(0.0003).values
        self.cfund = np.append(0, np.cumsum(self.fund))
    def one(self, i, s=None, atr_k=1.0, trail=2.0, maxhold=7, exitflag=None, side=1, cost=1.0, delay=0, cap=50):
        sd = s if atr_k is None else float(np.clip(atr_k * self.atr[i], 0.003, 0.15))
        L = levmax(sd, cap)
        if exitflag is None: exitflag = np.zeros(len(self.days), dtype=np.bool_)
        p0, ex, j, why = _sim(self.op, self.hi, self.lo, self.start, self.end, i, len(self.days), sd, -1.0 if trail is None else trail,
                              maxhold, exitflag, side, 1 / L - MM, STOPSLIP * cost, delay)
        nd = max(j - i, 1); fu = (self.cfund[i + nd] - self.cfund[i]) * side
        net = max(side * (ex / p0 - 1) - 2 * FEE * cost - fu, -1 / L)
        return dict(entry=self.days[i], exit=self.days[min(j, len(self.days) - 1)], s=sd, L=L, R=net / sd, ret=net,
                    why=('tempo', 'stop', 'liquidazione')[why], days=nd, side=side, j=j)
    def probes(self, i0=250, **kw):
        """Un trade-sonda per OGNI giorno (si sovrappongono): servono a misurare come un indicatore ordina R."""
        out = [self.one(i, **kw) for i in range(i0, len(self.days) - 1) if not np.isnan(self.atr[i])]
        return pd.DataFrame(out)
    def book(self, entry, exitf, i0=250, **kw):
        """Libro sequenziale (un trade per volta per moneta), come l'originale. entry/exitf: bool per giorno, noti la sera prima."""
        out = []; i = i0; n = len(self.days)
        while i < n - 1:
            if not entry[i] or np.isnan(self.atr[i]): i += 1; continue
            t = self.one(i, exitflag=exitf, **kw); out.append(t); i = t['j'] + 1
        return pd.DataFrame(out)

def fund_daily(c):
    try:
        f = st.get(f'bn_fund_{c}USDT'); s = f.iloc[:, 0]; return s.groupby(s.index.normalize()).sum()
    except Exception: return None

# ---------------- componenti dell'indicatore (valore alla CHIUSURA del giorno t; chi li usa li sposta di 1 giorno) ----------------
def er(logc, lb):
    """Efficiency ratio con segno (Kaufman): spostamento netto / cammino totale. In [-1, 1]."""
    return (logc - logc.shift(lb)) / logc.diff().abs().rolling(lb).sum()
def trend_quality(close, lbs=(10, 30, 60, 120)):
    lc = np.log(close); return sum(er(lc, lb) for lb in lbs) / len(lbs)
def r2_signed(close, lb):
    lc = np.log(close); x = np.arange(lb); x = x - x.mean()
    def f(y):
        y0 = y - y.mean(); b = (x * y0).sum() / (x * x).sum(); ss = (y0 * y0).sum()
        return np.sign(b) * (b * b * (x * x).sum() / ss if ss > 0 else 0)
    return lc.rolling(lb).apply(f, raw=True)
def compression(d, n=14, win=365):
    """1 = volatilita' ai minimi dell'ultimo anno, -1 = ai massimi (rango dell'ATR% a 14 giorni)."""
    a = ((d['high'] - d['low']) / d['close']).rolling(n).mean()
    return 1 - 2 * a.rolling(win, min_periods=120).rank(pct=True)
def avwap_month(d, vol):
    """Distanza dal VWAP ancorato all'apertura del mese, in unita' di ATR, limitata a +-3 e divisa per 3."""
    tp = (d['high'] + d['low'] + d['close']) / 3; m = d.index.to_period('M')
    vw = (tp * vol).groupby(m).cumsum() / vol.groupby(m).cumsum()
    a = ((d['high'] - d['low']) / d['close']).rolling(14).mean()
    return ((d['close'] / vw - 1) / a).clip(-3, 3) / 3
def avwap_swing(d, vol, look=60):
    """Distanza dal VWAP ancorato al minimo degli ultimi `look` giorni."""
    tp = ((d['high'] + d['low'] + d['close']) / 3).values; v = vol.values; lo = d['low'].values; c = d['close'].values
    pv = np.append(0, np.nancumsum(tp * v)); cv = np.append(0, np.nancumsum(v)); out = np.full(len(c), np.nan)
    for t in range(look, len(c)):
        k = t - look + 1 + int(np.argmin(lo[t - look + 1:t + 1])); den = cv[t + 1] - cv[k]
        if den > 0: out[t] = c[t] / ((pv[t + 1] - pv[k]) / den) - 1
    a = ((d['high'] - d['low']) / d['close']).rolling(14).mean()
    return (pd.Series(out, index=d.index) / a).clip(-3, 3) / 3
def flow(tk, n=7, win=365):
    """Squilibrio taker: quota di volume comprata a mercato su n giorni, come scarto standardizzato dall'ultimo anno."""
    sh = tk['taker_base'].rolling(n).sum() / tk['volume'].rolling(n).sum()
    z = (sh - sh.rolling(win, min_periods=120).median()) / sh.rolling(win, min_periods=120).std()
    return z.clip(-3, 3) / 3
def funding_state(f, idx):
    """-1 = funding a 7 giorni >= 30% annuo (long affollati), +1 = <= -30%. Senza dati: 0."""
    if f is None: return pd.Series(0.0, index=idx)
    return (-(f.rolling(7).mean() * 365 / 0.30).clip(-1, 1)).reindex(idx).fillna(0.0)
def range_pos(d, n=20):
    """Posizione della chiusura nel canale a n giorni, in [-1, 1] (versione continua della 'rottura dei massimi')."""
    h = d['high'].rolling(n).max(); l = d['low'].rolling(n).min(); return 2 * (d['close'] - l) / (h - l) - 1
def mtf(bars):
    """Accordo multi-orizzonte intraday: media dell'efficiency ratio su 24 barre da 1h e 42 barre da 4h, letta a fine giornata."""
    c1 = np.log(bars['close'].resample('1h').last().dropna()); c4 = np.log(bars['close'].resample('4h').last().dropna())
    e = (er(c1, 24).resample('1D').last() + er(c4, 42).resample('1D').last()) / 2
    return e

def blk(x):
    n = len(x); m = x.R.mean() if n else np.nan
    return dict(n=n, R=m, t=m / x.R.std() * np.sqrt(n) if n > 2 else np.nan, hit=(x.R > 0).mean() if n else np.nan)
def three(T):
    a = blk(T); s = blk(T[T.entry < SPLIT]); v = blk(T[T.entry >= SPLIT])
    return dict(n=a['n'], R=a['R'], t=a['t'], hit=a['hit'], n_sc=s['n'], R_sc=s['R'], t_sc=s['t'], n_ve=v['n'], R_ve=v['R'], t_ve=v['t'])
