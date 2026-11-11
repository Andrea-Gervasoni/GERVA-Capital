"""A9 - motore di esecuzione (SIMULATO). Il SEGNALE e' quello di v4 (conviction 'alta', nota la sera prima, calcolata sulle
barre spot giornaliere): qui cambia solo COME si entra, DOVE sta lo stop, su QUALE serie di prezzi si esegue e quanto costa.
Riscritto da zero rispetto a research/v5/v4/leva_trade_isolato.py (seconda derivazione): 01_base.py verifica che coincidano.
Convenzioni: R = P&L netto / distanza dello stop; gap oltre lo stop = uscita all'apertura della barra; leva = min(50, 1/(s/0.6+0.005));
margine isolato: perdita massima 1/leva."""
import sys, warnings, json, os
sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from numba import njit
from gerva.data import Store
from gerva import ensemble as E

HERE = os.path.dirname(os.path.abspath(__file__))
st = Store('/home/user/GERVA-Capital/data_cache')
COINS = ('BTC', 'ETH', 'SOL')
TAKER, MAKER, SLIP, STOPSLIP, MM, RATIO = 0.00045, 0.00015, 0.0002, 0.0005, 0.005, 0.6
H = np.timedelta64(1, 'h'); DAY = np.timedelta64(1, 'D'); M5 = np.timedelta64(5, 'm')
CUT = np.datetime64('2023-01-01')
TRIALS = {}


def count(group, n=1):
    TRIALS[group] = TRIALS.get(group, 0) + n


def save_trials(name):
    json.dump(TRIALS, open(os.path.join(HERE, f'trials_{name}.json'), 'w'), indent=1)


class Bars:
    def __init__(self, key, per_day=288):
        b = st.get(key); self.per_day = per_day
        self.ts = b.index.values.astype('datetime64[ns]')
        self.op, self.hi, self.lo, self.cl = (b[k].values.astype(float) for k in ('open', 'high', 'low', 'close'))
        g = b.groupby(b.index.normalize())
        self.daily = pd.DataFrame(dict(open=g['open'].first(), high=g['high'].max(), low=g['low'].min(), close=g['close'].last()))


def daily_fund(c):
    f = st.get(f'bn_fund_{c}USDT').iloc[:, 0]
    return f.groupby(f.index.normalize()).sum()


class Fund:
    """Funding per regolamento: cumulata per sommare i regolamenti in (t_ingresso, t_uscita]."""
    def __init__(self, times, rates):
        self.t = np.asarray(times).astype('datetime64[ns]'); self.r = np.asarray(rates, float); self.c = np.concatenate([[0.0], np.cumsum(self.r)])

    def paid(self, t0, t1):
        a = np.searchsorted(self.t, t0, 'right'); b = np.searchsorted(self.t, t1, 'right')
        return self.c[b] - self.c[a]

    def last(self, t):          # ultimo tasso regolato a t o prima (noto a t)
        a = np.searchsorted(self.t, t, 'right') - 1
        return self.r[a] if a >= 0 else np.nan


def fund_bn(c, first_bar):
    f = st.get(f'bn_fund_{c}USDT').iloc[:, 0]; f.index = f.index.floor('h'); f = f[~f.index.duplicated()]
    pre = pd.date_range(pd.Timestamp(first_bar).normalize(), f.index[0], freq='8h', inclusive='left')   # prima dei dati: 0,01%/8h
    return Fund(np.concatenate([pre.values, f.index.values]), np.concatenate([np.full(len(pre), 0.0001), f.values]))


def fund_hl(c):
    f = st.get(f'v4_hl_fund_{c}')['fundingRate']
    return Fund(f.index.values, f.values)


SPOT = {c: Bars(f'bn_spot_5m_{c}USDT') for c in COINS}
_PERP = {}


def PERP(c):
    if c not in _PERP: _PERP[c] = Bars(f'v4_um_5m_{c}USDT')
    return _PERP[c]


_P1 = {}


def PERP1(c):                                                             # perpetual a 1 minuto (scaricati da 00_dati_1m.py)
    if c not in _P1: _P1[c] = Bars(f'v5_um_1m_{c}USDT', per_day=1440)
    return _P1[c]


DFUND = {c: daily_fund(c) for c in COINS}
CONV = {}; ATR = {}
for c in COINS:
    d = SPOT[c].daily
    F = E.crypto_signals(d, SPOT['BTC'].daily['close'], DFUND[c]); CONV[c] = E.conviction(F, 'crypto').shift(1)
    ATR[c] = ((d['high'] - d['low']) / d['close']).rolling(14).mean().shift(1)
FBN = {c: fund_bn(c, SPOT[c].ts[0]) for c in COINS}


def levmax(s, cap=50.0): return min(cap, 1 / (s / RATIO + MM))


@njit(cache=True)
def path(op, hi, lo, kf, kend, pe, stop, trail_d, use_first_high, check_first):
    """Dalla barra kf (quella dell'eseguito) alla barra kend esclusa. Ritorna (prezzo d'uscita lordo, barra, 1=stop/0=tempo).
    Ordine dentro la barra come in v4: prima lo stop (col livello delle barre precedenti), poi l'aggiornamento del trailing."""
    best = pe
    for k in range(kf, kend):
        if (k > kf or check_first) and lo[k] <= stop:
            return min(stop, op[k]) if k > kf else stop, k, 1
        if trail_d > 0 and (k > kf or use_first_high) and hi[k] > best:
            best = hi[k]; ns = best * (1 - trail_d)
            if ns > stop: stop = ns
    return op[min(kend, len(op) - 1)], kend, 0


def round_step(p): return 10.0 ** np.floor(np.log10(p * 0.05))      # passo 'tondo': tra 0,5% e 5% del prezzo


def simulate(c, bars=None, stop='atr', k=1.0, trail=2.0, entry='taker', hour=0, lim_bp=0.0, win=12, thru_bp=0.0, fallback='skip',
             fund='bn_exact', cost_mult=1.0, delay=0, maxhold=7, tiers=('alta',), buf=0.001, taker=TAKER, maker=MAKER, slip=SLIP,
             exit_maker=False, skip_fn=None, start_from=250, brk_stop=None, exit_hour=0):
    """Un trade alla volta per moneta, come in v4.
    stop: 'fix' (k = frazione), 'atr' (k x ATR14 giornaliero), 'pdl' (sotto il minimo di ieri), 'swing' (minimo degli ultimi k giorni),
          'round' (sotto il numero tondo che sta sotto lo stop k x ATR), 'atr_noround' (k x ATR, spostato se cade entro 0,15% da un tondo)
    entry: 'taker' all'apertura della barra dell'ora `hour`; 'maker' limite a open*(1-lim_bp) valido `win` barre, eseguito se il minimo
           scende SOTTO limite*(1-thru_bp); se non eseguito: fallback 'skip' | 'taker' (alla barra dopo la finestra);
           'breakout' buy-stop sul massimo delle prime `win` barre, valido fino a fine giornata.
    fund: 'v4' (somma giornaliera come in v4), 'bn_exact' (regolamenti Binance effettivamente attraversati), 'hl_exact', 'none'."""
    b = bars or SPOT[c]; ts, op, hi, lo = b.ts, b.op, b.hi, b.lo
    d = SPOT[c].daily; days = d.index.values.astype('datetime64[ns]'); nd_ = len(days)
    tier = CONV[c]['tier'].values; score = CONV[c]['score'].values; atr = ATR[c].values
    xd = b.daily.reindex(d.index); pdl = xd['low'].shift(1).values
    sw = xd['low'].rolling(int(k) if stop in ('swing', 'swing_placebo') else 3).min().shift(1).values
    lag = 5; plc_pdl = (1 - xd['low'].shift(1) * (1 - buf) / xd['open']).shift(lag).values    # placebo: la distanza 'minimo di ieri' di 5 giorni prima
    plc_sw = (1 - xd['low'].rolling(int(k) if stop in ('swing', 'swing_placebo') else 3).min().shift(1) * (1 - buf) / xd['open']).shift(lag).values
    start = np.searchsorted(ts, days)                                     # prima barra di ogni giorno (>=)
    F = FBN[c] if fund in ('bn_exact', 'v4') else (fund_hl(c) if fund == 'hl_exact' else None)
    fd = DFUND[c]
    tk, mk, sl, ss = taker * cost_mult, maker * cost_mult, slip * cost_mult, STOPSLIP * cost_mult
    out = []; i = start_from; nb = len(ts)
    while i < nd_ - 1:
        if tier[i] not in tiers or np.isnan(score[i]) or start[i] >= nb or ts[start[i]] - days[i] >= DAY: i += 1; continue
        k0 = (start[i] if hour == 0 else int(np.searchsorted(ts, days[i] + hour * H))) + delay
        # giorno d'uscita a tempo
        j = i + 1
        while not (j >= nd_ - 1 or j - i >= maxhold or tier[j] == 'bassa'): j += 1
        kend = min((start[j] if exit_hour == 0 else int(np.searchsorted(ts, days[j] + exit_hour * H))) + delay, nb - 1)
        if k0 >= kend: i += 1; continue
        ref = op[k0]; filled = True; fee_in = tk + sl; kf = k0; pe = ref; mode = 'taker'; first_hi = True; chk = True
        if entry == 'maker':
            limit = ref * (1 - lim_bp * 1e-4); thr = limit * (1 - thru_bp * 1e-4)
            w = lo[k0:min(k0 + win, kend)]; hit = np.nonzero(w < thr)[0]
            if len(hit):
                kf = k0 + int(hit[0]); pe = limit; fee_in = mk; mode = 'maker'; first_hi = False
            elif fallback == 'taker' and k0 + win < kend:
                kf = k0 + win; pe = op[kf]; mode = 'rincorsa'
            else: filled = False
        elif entry == 'breakout':
            ke = min(k0 + win, kend); level = hi[k0:ke].max(); day_end = min(start[i + 1], kend)
            w = hi[ke:day_end]; hit = np.nonzero(w >= level)[0]
            if len(hit):
                kf = ke + int(hit[0]); pe = max(level, op[kf]); mode = 'breakout'; first_hi = False
                rng_lo = lo[k0:ke].min()
            else: filled = False
        if not filled:
            # che cosa avrebbe fatto il trade a mercato (per misurare la selezione avversa)
            out.append(dict(coin=c, entry=days[i], filled=False, ref=ref, mode='saltato')); i += 1; continue
        # distanza dello stop (in frazione del prezzo d'ingresso), con dati noti alla decisione
        if stop == 'fix': sd = k
        elif stop == 'atr': sd = k * atr[i]
        elif stop == 'pdl': sd = 1 - pdl[i] * (1 - buf) / pe
        elif stop == 'swing': sd = 1 - sw[i] * (1 - buf) / pe
        elif stop == 'pdl_placebo': sd = plc_pdl[i]
        elif stop == 'swing_placebo': sd = plc_sw[i]
        elif stop == 'round':
            s0 = pe * (1 - k * atr[i]); stp = round_step(pe); sd = 1 - (np.floor(s0 / stp) * stp) * (1 - buf) / pe
        elif stop == 'atr_noround':
            s0 = pe * (1 - k * atr[i]); stp = round_step(pe); near = np.round(s0 / stp) * stp
            if abs(s0 - near) / pe < 0.0015: s0 = near * (1 - 0.0015)      # se lo stop cade su un tondo, lo si mette 0,15% sotto
            sd = 1 - s0 / pe
        elif stop == 'brk': sd = max(1 - rng_lo * (1 - buf) / pe, 0.0)
        else: raise ValueError(stop)
        if not np.isfinite(sd): i += 1; continue
        sd_raw = sd; sd = float(np.clip(sd, 0.003, 0.15))
        if skip_fn is not None and skip_fn(c, i, ts[kf], pe, sd): i += 1; continue
        L = levmax(sd); liq = pe * (1 - (1 / L - MM)); stp_px = pe * (1 - sd)
        px, kx, st_ = path(op, hi, lo, kf, kend, pe, stp_px, (trail * sd) if trail else 0.0, first_hi, chk)
        why = 'tempo'; fee_out = tk + sl
        if st_ == 1:
            px = px * (1 - ss); why = 'stop'
            if px <= liq: px = liq; why = 'liquidazione'
        elif exit_maker:
            # uscita a tempo con limite all'apertura: eseguito se nelle `win` barre il massimo supera il prezzo; altrimenti taker dopo
            w = hi[kx:min(kx + 3, nb)]
            if (w > px).any(): fee_out = mk
            else: px = op[min(kx + 3, nb - 1)]
        t_in = ts[kf]; t_out = ts[min(kx, nb - 1)]
        jx = int(np.searchsorted(days, t_out, 'right') - 1)                # giorno dell'uscita
        if fund == 'v4':
            ndays = max(jx - i, 1); fu = float(fd.reindex(pd.DatetimeIndex(days[i:i + ndays])).fillna(0.0003).sum())
        elif F is not None: fu = float(F.paid(t_in, t_out))
        else: fu = 0.0
        gross = px / pe - 1; net = max(gross - fee_in - fee_out - fu, -1 / L)
        # stop-hunt: dopo lo stop il prezzo torna sopra l'ingresso entro 24 ore?
        hunt = np.nan; hunt_stop = np.nan
        if st_ == 1:
            w = hi[kx + 1:kx + 1 + b.per_day]; hunt = float(len(w) > 0 and w.max() > pe)
        out.append(dict(coin=c, entry=days[i], t_in=t_in, t_out=t_out, exit=days[jx], filled=True, mode=mode, ref=ref, pe=pe, px=px, s=sd,
                        s_raw=sd_raw, L=L, R=net / sd, ret=net, gross=gross, fee=fee_in + fee_out, fund=fu, why=why, hunt=hunt,
                        score=score[i], side=1, wait=(kf - k0)))
        i = max(jx, i) + 1
    T = pd.DataFrame(out)
    return T


def run(coins=COINS, perp=False, m1=False, **kw):
    T = pd.concat([simulate(c, bars=PERP1(c) if m1 else PERP(c) if perp else None, **kw) for c in coins], ignore_index=True)
    return T


def blk(x):
    n = len(x)
    if n < 3: return dict(n=n, R=np.nan, sd=np.nan, t=np.nan, hit=np.nan)
    return dict(n=n, R=x.R.mean(), sd=x.R.std(), t=x.R.mean() / x.R.std() * np.sqrt(n), hit=(x.R > 0).mean())


def stats(T, label, t0=None, t1=None):
    """full / scelta (<2023) / verifica (>=2023). N/anno sul periodo coperto. kelly = N*(R/sd)^2 (obiettivo 6,3)."""
    T = T[T.filled] if 'filled' in T else T
    if len(T) < 3: return dict(cfg=label, n=len(T))
    t0 = t0 or T.entry.min(); t1 = t1 or T.entry.max()
    y = (pd.Timestamp(t1) - pd.Timestamp(t0)).days / 365.25
    a = blk(T); s = blk(T[T.entry < CUT]); v = blk(T[T.entry >= CUT])
    ys = max((min(pd.Timestamp(t1), pd.Timestamp(CUT)) - pd.Timestamp(t0)).days / 365.25, 1e-9); yv = max((pd.Timestamp(t1) - max(pd.Timestamp(CUT), pd.Timestamp(t0))).days / 365.25, 1e-9)
    return dict(cfg=label, n=a['n'], N_anno=a['n'] / y, s_med=T.s.median(), R=a['R'], sdR=a['sd'], t=a['t'], hit=a['hit'],
                R_sel=s['R'], sd_sel=s['sd'], t_sel=s['t'], N_sel=s['n'] / ys, R_ver=v['R'], sd_ver=v['sd'], t_ver=v['t'], N_ver=v['n'] / yv,
                costo_R=(T.fee / T.s).mean(), fund_R=(T.fund / T.s).mean(), stop_pct=(T.why != 'tempo').mean(),
                K_sel=s['n'] / ys * (s['R'] / s['sd']) ** 2 * np.sign(s['R']) if s['n'] > 2 else np.nan,
                K_ver=v['n'] / yv * (v['R'] / v['sd']) ** 2 * np.sign(v['R']) if v['n'] > 2 else np.nan)


def per_year(T):
    T = T[T.filled] if 'filled' in T else T
    g = T.groupby(pd.DatetimeIndex(T.entry).year).R
    return pd.DataFrame(dict(n=g.size(), R=g.mean(), somma_R=g.sum())).round(3)


def show(rows, cols=None):
    R = pd.DataFrame(rows)
    if cols: R = R[[c for c in cols if c in R]]
    pd.set_option('display.width', 280); pd.set_option('display.max_columns', 40); pd.set_option('display.max_colwidth', 60)
    print(R.round(3).to_string(index=False)); return R


SHORT = ['cfg', 'n', 'N_anno', 's_med', 'R', 'sdR', 't', 'hit', 'R_sel', 't_sel', 'R_ver', 't_ver', 'costo_R', 'fund_R', 'stop_pct', 'K_sel', 'K_ver']
