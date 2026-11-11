"""A6 eventi - funzioni comuni. Tutto SIMULATO su dati storici reali.
Barre indicizzate per ora di APERTURA (UTC). Una decisione al tempo T usa solo barre chiuse entro T; l'ingresso e' all'apertura
della barra T (ritardo +1 = barra successiva). R = P&L netto / distanza dello stop.
Costi perp: 4,5 pb taker + 2 pb slippage per lato, +5 pb sugli stop, funding reale Binance (0,01%/8h se manca).
Stop: gap -> apertura della barra. Leva = min(cap, 1/(stop/0,6+0,005)); margine isolato: perdita <= 1/leva."""
import sys, warnings, json, os
sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from gerva.data.sources import Store
ROOT = '/home/user/GERVA-Capital'; HERE = ROOT + '/research/v5/v5/a6_eventi'
st = Store(ROOT + '/data_cache'); SPL = pd.Timestamp('2023-01-01')
TAKER = 0.00045; SLIP = 0.0002; STOPSLIP = 0.0005; MAKER = 0.00015; MM = 0.005; RATIO = 0.6
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 500)
ALTS = ("BTC ETH SOL BNB XRP DOGE ADA LTC LINK AVAX DOT BCH ETC ATOM NEAR FIL UNI AAVE TRX XLM MATIC APT ARB OP SUI "
        "INJ SEI TIA WIF TON RUNE HBAR LUNA FTT EOS SAND").split()

class Bars:
    """Barre di un simbolo + funding + volatilita' oraria nota (sigma1h: dev.std dei rendimenti orari sui 14 giorni precedenti)."""
    def __init__(self, sym, freq='5m', df=None):
        self.sym = sym; self.freq = freq
        b = st.get(f'v4_um_{freq}_{sym}USDT') if df is None else df
        b = b[~b.index.duplicated()].sort_index()
        self.df = b; self.t = b.index.values.astype('datetime64[ns]').astype(np.int64)
        self.op = b['open'].values; self.hi = b['high'].values; self.lo = b['low'].values; self.cl = b['close'].values
        self.bar_ns = int(pd.Timedelta(freq.replace('m', 'min')).value)
        self.sig1h = self.sigma(b)
        try:
            f = st.get(f'bn_fund_{sym}USDT').iloc[:, 0]; f.index = f.index.round('h'); f = f[~f.index.duplicated()]
            self.ft = f.index.values.astype('datetime64[ns]').astype(np.int64); self.fv = np.nan_to_num(f.values, nan=0.0001); self.fund = f
        except Exception:
            self.ft = np.array([], dtype=np.int64); self.fv = np.array([]); self.fund = None
        self.fcum = np.concatenate([[0.0], np.cumsum(self.fv)])
    @staticmethod
    def sigma(b):
        """sigma oraria nota all'apertura di ogni barra: std dei rendimenti log orari delle 336 ore gia' chiuse."""
        h = b['close'].resample('1h').last().dropna(); r = np.log(h).diff()
        s = r.rolling(336, min_periods=168).std()
        s.index = s.index + pd.Timedelta('1h')          # la barra oraria aperta alle H chiude alle H+1: nota da H+1
        return s.reindex(b.index, method='ffill').values
    def idx(self, ts):
        """indice della barra che apre a ts (o la prima successiva)."""
        return int(np.searchsorted(self.t, np.int64(pd.Timestamp(ts).value)))
    def funding(self, t0, t1):
        if len(self.ft) == 0: return 0.0001 * (t1 - t0) / (8 * 3600e9)
        a = np.searchsorted(self.ft, t0, 'right'); z = np.searchsorted(self.ft, t1, 'right')
        return float(self.fcum[z] - self.fcum[a])

def levmax(s, cap=40): return min(cap, 1 / (s / RATIO + MM))

def sim(B, i, side, s, H, tp=None, cm=1.0, entry_px=None, entry_fee=None, exit_maker=False):
    """Un trade: ingresso all'apertura della barra i (o a entry_px, ordine limite), stop a distanza s, uscita a tempo dopo H barre
    (apertura della barra i+H) o obiettivo tp (in multipli di s). cm = moltiplicatore dei costi. Ritorna dict o None."""
    n = len(B.op)
    if i < 0 or i + 1 >= n or not np.isfinite(s) or s <= 0: return None
    j = min(i + H, n - 1); p0 = B.op[i] if entry_px is None else entry_px
    stop = p0 * (1 - side * s); L = levmax(s)
    lo = B.lo[i:j]; hi = B.hi[i:j]; op = B.op[i:j]
    hit = (lo <= stop) if side == 1 else (hi >= stop)
    k_stop = int(np.argmax(hit)) if hit.any() else -1
    k_tp = -1
    if tp is not None:
        tgt = p0 * (1 + side * tp * s); ht = (hi >= tgt) if side == 1 else (lo <= tgt)
        k_tp = int(np.argmax(ht)) if ht.any() else -1
    fee_in = (TAKER + SLIP) * cm if entry_fee is None else entry_fee * cm
    fee_out = (TAKER + SLIP) * cm
    if k_stop >= 0 and (k_tp < 0 or k_stop <= k_tp):          # stesso bar: vince lo stop (prudente)
        o = op[k_stop]; px = (min(stop, o) if side == 1 else max(stop, o)) * (1 - side * STOPSLIP * cm); why = 'stop'; ke = i + k_stop
        te = B.t[ke] + B.bar_ns // 2
    elif k_tp >= 0:
        px = tgt; why = 'tp'; ke = i + k_tp; te = B.t[ke] + B.bar_ns // 2; fee_out = MAKER * cm  # limite a riposo
    else:
        px = B.op[j]; why = 'tempo'; ke = j; te = B.t[j]
        if exit_maker: fee_out = MAKER * cm
    fu = B.funding(B.t[i], te) * side
    net = side * (px / p0 - 1) - fee_in - fee_out - fu
    net = max(net, -1 / L)
    return dict(sym=B.sym, entry=pd.Timestamp(B.t[i]), exit=pd.Timestamp(te), side=side, stop=s, lev=L, R=net / s, ret=net, why=why)

def run(B, ev, H, k=1.5, tp=None, cm=1.0, delay=0, smin=0.003, smax=0.15, **kw):
    """ev: DataFrame con colonne t (decisione), side [, s]. Stop = k * sigma1h * sqrt(ore di tenuta) (noto alla decisione)."""
    out = []; hours = H * B.bar_ns / 3600e9
    for t, side, *rest in ev[['t', 'side'] + (['s'] if 's' in ev else [])].itertuples(index=False):
        i = B.idx(t)
        if i >= len(B.t) or B.t[i] != pd.Timestamp(t).value: continue
        s = rest[0] if rest else float(np.clip(k * B.sig1h[i] * np.sqrt(hours), smin, smax))
        r = sim(B, i + delay, side, s, H, tp=tp, cm=cm, **kw)
        if r: r['t_dec'] = pd.Timestamp(t); out.append(r)
    return pd.DataFrame(out)

def blk(T):
    """media R, t-stat raggruppato per istante di decisione (eventi simultanei su piu' monete = un'osservazione)."""
    if len(T) < 3: return dict(n=len(T), m=np.nan, t=np.nan)
    g = T['R'].groupby(T['t_dec'].values if CLU is None else T['t_dec'].dt.floor(CLU).values).mean()
    t = g.mean() / g.std() * np.sqrt(len(g)) if len(g) > 2 and g.std() > 0 else np.nan
    return dict(n=len(T), m=T.R.mean(), t=t, ne=len(g))

TRIALS = []; ROWS = []; CLU = None      # CLU='D': t-stat raggruppato per giorno (eventi su piu' monete nello stesso giorno = 1 osservazione)
def report(label, fn, fam, keep=None):
    """fn(cm, delay) -> trades. Stampa tutto/scelta/verifica, costi x2, ritardo +1, per anno. Conta la variante."""
    T = fn(1.0, 0); TRIALS.append(label)
    if len(T) < 5:
        print(f'{label:58s} n={len(T)} (troppo pochi)'); return T
    T2 = fn(2.0, 0); Td = fn(1.0, 1)
    a = blk(T); s = blk(T[T.t_dec < SPL]); v = blk(T[T.t_dec >= SPL])
    yrs = (T.t_dec.max() - T.t_dec.min()).days / 365.25 or 1
    py = T['R'].groupby(T['t_dec'].dt.year.values).mean().round(2).to_dict()
    row = dict(fam=fam, label=label, n=a['n'], n_ev=a.get('ne'), per_yr=round(a['n'] / yrs, 1), ev_yr=round(a.get('ne', 0) / yrs, 1), R=a['m'], t=a['t'],
               sd=T.R.std(), hit=(T.R > 0).mean(), R_sel=s['m'], t_sel=s['t'], n_sel=s['n'], R_ver=v['m'], t_ver=v['t'], n_ver=v['n'],
               R_x2=T2.R.mean() if len(T2) else np.nan, R_x2_ver=T2[T2.t_dec >= SPL].R.mean() if len(T2) else np.nan,
               R_del=Td.R.mean() if len(Td) else np.nan, R_del_ver=Td[Td.t_dec >= SPL].R.mean() if len(Td) else np.nan,
               stopped=(T.why == 'stop').mean(), s_med=T.stop.median(), per_year=json.dumps({int(k): v for k, v in py.items()}))
    ROWS.append(row)
    print(f"{label:58s} n={a['n']:5d} ev/a={row['ev_yr']:6.1f} R={a['m']:+.3f} t={a['t']:+.2f} | sel {s['m']:+.3f} (t {s['t']:+.2f}, n {s['n']}) | ver {v['m']:+.3f} (t {v['t']:+.2f}, n {v['n']}) | x2 {row['R_x2']:+.3f} | rit {row['R_del']:+.3f} | hit {row['hit']:.0%} stop {row['stopped']:.0%} s~{row['s_med']:.2%} | {py}")
    return T

def save(fam):
    pd.DataFrame(ROWS).to_csv(f'{HERE}/res_{fam}.csv', index=False)
    json.dump(TRIALS, open(f'{HERE}/trials_{fam}.json', 'w'))
    print(f'\nvarianti provate in questo script: {len(TRIALS)}')

_cache = {}
def bars(sym, freq='5m'):
    k = (sym, freq)
    if k not in _cache: _cache[k] = Bars(sym, freq)
    return _cache[k]

def trunc_check(fn, df, n=12, seed=0, tol=1e-9):
    """fn(df)->Series allineata a df.index (valore NOTO ALL'APERTURA della barra). Ricalcola su dati troncati alla barra i, con
    massimo/minimo/chiusura/volume della barra i sostituiti da valori assurdi (non ancora noti): il valore in i deve coincidere."""
    full = fn(df); rng = np.random.default_rng(seed); bad = 0
    for i in rng.integers(len(df) // 3, len(df) - 1, n):
        d = df.iloc[:i + 1].copy()
        for c in d.columns:
            if c != 'open': d.iloc[-1, d.columns.get_loc(c)] = d.iloc[-1][c] * 7.0
        a = fn(d).iloc[-1]; b = full.iloc[i]
        if not ((pd.isna(a) and pd.isna(b)) or a == b or abs(float(a) - float(b)) <= tol * max(1, abs(float(b)))): bad += 1
    return bad
