"""A2 - motore di gestione del trade sul percorso a 5 minuti (SIMULATO).
Ingressi: gli stessi di research/v5/v4/leva_trade_isolato.py (giorni a conviction 'alta', nota la sera prima, BTC/ETH/SOL, solo long).
Tutto in R = P&L / rischio iniziale (nozionale iniziale x distanza dello stop iniziale).
Costi: 4,5 pb taker + 2 pb slippage per lato, +5 pb sugli ordini stop, funding reale Binance alle 00/08/16 UTC (0,01%/8h prima del 2020).
Convenzioni: lo stop colpito in gap esce all'apertura della barra; gli aggiornamenti dello stop (trailing, pareggio) valgono dalla barra dopo;
dopo un'aggiunta piramidale nella stessa barra si assume il caso peggiore (stop nuovo colpito se il minimo o la chiusura lo toccano)."""
import sys, warnings, importlib.util
sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from numba import njit

spec = importlib.util.spec_from_file_location('lti', '/home/user/GERVA-Capital/research/v5/v4/leva_trade_isolato.py')
LTI = importlib.util.module_from_spec(spec); spec.loader.exec_module(LTI)      # carica B, D, CONV (conviction.shift(1))
FEE, STOPSLIP, MM, RATIO = LTI.FEE, LTI.STOPSLIP, LTI.MM, LTI.RATIO
COINS = ('BTC', 'ETH', 'SOL')
NP = 26
# indici dei parametri
(SD, ATRK, MAXH, TMODE, TM, TACT, AFMAX, BE, BEOFF, TSB, TSTHR, TPR, TPF, PYN, PYSTEP, PYMODE, PYSZ,
 EMODE, EX, EWIN, REMODE, REC, REMAX, DELAY, CAP, EARG) = range(NP)
WHY = {0: 'tempo', 1: 'stop', 2: 'obiettivo', 3: 'stop_tempo', 4: 'liquidazione', 5: 'fine_dati'}

def params(**kw):
    p = np.zeros(NP); p[SD] = 0.017; p[MAXH] = 7; p[TPF] = 1.0; p[PYSTEP] = 1.0; p[PYSZ] = 1.0; p[EWIN] = 288; p[CAP] = 50
    m = dict(sd=SD, atr_k=ATRK, maxhold=MAXH, tmode=TMODE, tm=TM, tact=TACT, afmax=AFMAX, be=BE, beoff=BEOFF, ts=TSB, tsthr=TSTHR,
             tp=TPR, tpf=TPF, pyn=PYN, pystep=PYSTEP, pymode=PYMODE, pysz=PYSZ, emode=EMODE, ex=EX, ewin=EWIN, remode=REMODE,
             rec=REC, remax=REMAX, delay=DELAY, cap=CAP, earg=EARG)
    for k, v in kw.items(): p[m[k]] = v
    return p

def prep(c):
    b = LTI.B[c]; d = LTI.D[c]; cv = LTI.CONV[c]
    op, hi, lo, cl, vol = (b[k].values.astype(np.float64) for k in ('open', 'high', 'low', 'close', 'volume'))
    dn = b.index.normalize().values; days = d.index.values
    start = np.searchsorted(dn, days).astype(np.int64); end = np.append(start[1:], len(dn)).astype(np.int64)
    dayidx = (np.searchsorted(days, dn)).astype(np.int64)
    atr = ((d['high'] - d['low']) / d['close']).rolling(14).mean().shift(1).values
    tier = cv['tier'].values; score = cv['score'].values
    enter_ok = (tier == 'alta') & ~np.isnan(score); exit_flag = (tier == 'bassa')
    # VWAP di sessione (giorno UTC) fino alla barra precedente
    tp_ = (hi + lo + cl) / 3; g = pd.Series(dn)
    cpv = pd.Series(tp_ * vol).groupby(g.values).cumsum().values; cv_ = pd.Series(vol).groupby(g.values).cumsum().values
    vw = np.full(len(op), np.nan); ok = cv_ > 0; vw[ok] = cpv[ok] / cv_[ok]
    vw = np.roll(vw, 1); vw[start] = np.nan
    # volatilita' intraday: media del true range a 5m su 288 barre, portata a scala giornaliera, nota alla barra precedente
    pc = np.roll(cl, 1); pc[0] = cl[0]
    tr = np.maximum(hi, pc) - np.minimum(lo, pc)
    a5 = (pd.Series(tr / cl).rolling(288).mean().shift(1) * np.sqrt(288)).values
    # funding alla barra del pagamento
    fr = np.zeros(len(op)); idx = b.index
    is8 = (idx.hour % 8 == 0) & (idx.minute == 0); fr[is8] = 0.0001
    try:
        f = LTI.st.get(f'bn_fund_{c}USDT').iloc[:, 0]; ft = f.index.floor('5min')
        pos = idx.get_indexer(ft); m = pos >= 0
        first = idx.searchsorted(ft[0]); fr[first:] = 0.0
        fr[pos[m]] = f.values[m]
    except Exception as e: print('funding mancante', c, e)
    return dict(op=op, hi=hi, lo=lo, cl=cl, vw=vw, a5=np.nan_to_num(a5, nan=0.05), fr=fr, start=start, end=end, dayidx=dayidx,
                enter_ok=enter_ok, exit_flag=exit_flag, atr=atr, days=days, idx=idx)

@njit(cache=True)
def _run(kent, pent, i, sd, op, hi, lo, cl, a5, fr, start, dayidx, exit_flag, P, fee, stopslip, usefund):
    """Gestisce un trade dall'ingresso all'uscita. Ritorna (k_uscita, giorno_uscita, pnl su nozionale iniziale, why, n_aggiunte, L)."""
    nb = len(op); nd = len(start)
    L = min(P[24], 1.0 / (sd / 0.6 + 0.005)); R1 = pent * sd
    stop = pent * (1 - sd); best = pent
    e = np.zeros(4); sz = np.zeros(4); Lu = np.zeros(4); e[0] = pent; sz[0] = 1.0; Lu[0] = L; n = 1
    pnl = -fee; nadd = 0; tp_done = False; be_done = False
    tmode = int(P[3]); af0 = P[4]; af = af0; sar = stop
    delay = int(P[23]); maxh = P[2]; ts = int(P[9])
    why = -1; px = 0.0; kx = kent
    k = kent
    while True:
        j = dayidx[k]
        if k > kent and k == start[j] and (j >= nd - 1 or j - i >= maxh or exit_flag[j]):
            kx = min(k + delay, nb - 1); px = op[kx]; why = 0; break
        o = op[k]; h = hi[k]; l = lo[k]; c = cl[k]
        if usefund and k > kent and fr[k] != 0.0:
            tot = 0.0
            for u in range(n): tot += sz[u]
            pnl -= fr[k] * tot
        if l <= stop:
            px = min(stop, o) * (1 - stopslip); why = 1; kx = k; break
        added = False
        while nadd < int(P[13]) and h >= pent + (nadd + 1) * P[14] * R1:
            lvl = pent + (nadd + 1) * P[14] * R1
            pa = max(lvl, o) * (1 + stopslip)
            e[n] = pa; sz[n] = P[16]; n += 1; pnl -= fee * P[16]; nadd += 1; added = True
            pm = int(P[15]); ns = stop
            if pm == 0: ns = pent + (nadd - 1) * P[14] * R1
            elif pm == 1:
                a = 0.0; w = 0.0
                for u in range(n): a += sz[u] * e[u]; w += sz[u]
                ns = a / w
            if ns > stop: stop = ns
            Lu[n - 1] = min(P[24], 1.0 / (max(pa - stop, 0.0) / pa / 0.6 + 0.005))      # leva dell'aggiunta: dal suo stop effettivo
        if P[11] > 0 and not tp_done and h >= pent + P[11] * R1:
            tpx = pent + P[11] * R1; fr_ = P[12]; tp_done = True
            for u in range(n):
                pnl += fr_ * sz[u] * (tpx / e[u] - 1) - fee * fr_ * sz[u]; sz[u] *= (1 - fr_)
            if fr_ >= 0.999999:
                why = 2; kx = k; px = tpx; break
        if added and (c <= stop or (o > stop and l <= stop)):
            px = stop * (1 - stopslip); why = 1; kx = k; break
        if P[7] > 0 and not be_done and h >= pent + P[7] * R1:
            be_done = True; ns = pent * (1 + P[8] * sd)
            if ns > stop: stop = ns
        newhigh = False
        if h > best: best = h; newhigh = True
        if tmode > 0 and best - pent >= P[5] * R1:
            if tmode == 1:
                ns = best * (1 - P[4] * sd)
                if ns > stop: stop = ns
            elif tmode == 2:
                ns = best * (1 - P[4] * a5[k])
                if ns > stop: stop = ns
            elif tmode == 3:
                if sar < stop: sar = stop
                sar = sar + af * (best - sar)
                if newhigh: af = min(af + af0, P[6])
                cap_ = l if k == kent else min(l, lo[k - 1])
                if sar > cap_: sar = cap_
                if sar > stop: stop = sar
        if ts > 0 and k - kent + 1 == ts and (c - pent) / R1 <= P[10]:
            kx = min(k + 1 + delay, nb - 1); px = op[kx]; why = 3; break
        k += 1
        if k >= nb:
            kx = nb - 1; px = cl[kx]; why = 5; break
    tot = 0.0; floor_hit = False
    for u in range(n):
        g = px / e[u] - 1
        if g < -(1.0 / Lu[u] - 0.005): g = -(1.0 / Lu[u] - 0.005); floor_hit = True
        x = sz[u] * g - fee * sz[u]
        pnl += x; tot += sz[u]
    if floor_hit and why == 1: why = 4
    return kx, dayidx[kx], pnl, why, nadd, L

@njit(cache=True)
def _sim(op, hi, lo, cl, vw, a5, fr, start, end, dayidx, enter_ok, exit_flag, atr, P, fee, stopslip, usefund):
    nd = len(start); out = np.zeros((40000, 10)); m = 0
    delay = int(P[23]); em = int(P[17]); x = P[18]; win = int(P[19]); earg = int(P[25])
    i = 250
    while i < nd - 1:
        if not enter_ok[i]: i += 1; continue
        if P[1] > 0:
            if np.isnan(atr[i]): i += 1; continue
            sd = min(max(P[1] * atr[i], 0.003), 0.15)
        else: sd = P[0]
        a = start[i]; z = end[i]; kent = -1; pent = 0.0
        av = atr[i] if not np.isnan(atr[i]) else 0.04
        if em == 0:
            kent = a + delay; pent = op[kent]
        elif em == 1:                                   # limite x*ATR sotto l'apertura del giorno
            lim = op[a] * (1 - x * av)
            for k in range(a + delay, min(a + win, z)):
                if lo[k] < lim:
                    kent = k; pent = min(lim, op[k]); break
        elif em == 2:                                   # ritorno al VWAP di sessione dopo earg barre
            for k in range(a + earg + delay, min(a + win, z)):
                v = vw[k]
                if np.isnan(v): continue
                if op[k] <= v: kent = k; pent = op[k]; break
                if lo[k] < v: kent = k; pent = v; break
        elif em == 3:                                   # mercato ritardato di earg barre
            kent = min(a + earg + delay, z - 1); pent = op[kent]
        elif em == 4:                                   # stop-buy x*ATR sopra l'apertura
            trg = op[a] * (1 + x * av)
            for k in range(a + delay, min(a + win, z)):
                if hi[k] >= trg:
                    kent = k; pent = max(trg, op[k]) * (1 + stopslip); break
        if kent < 0: i += 1; continue
        kx, jx, pnl, why, nadd, L = _run(kent, pent, i, sd, op, hi, lo, cl, a5, fr, start, dayidx, exit_flag, P, fee, stopslip, usefund)
        out[m, 0] = kent; out[m, 1] = kx; out[m, 2] = i; out[m, 3] = sd; out[m, 4] = L; out[m, 5] = pnl / sd; out[m, 6] = pnl
        out[m, 7] = why; out[m, 8] = nadd; out[m, 9] = 0; m += 1
        nre = 0; rm = int(P[20])
        while rm > 0 and (why == 1 or why == 4) and pnl < 0 and nre < int(P[22]):
            j = jx
            if not enter_ok[j] or j >= nd - 1: break
            k2 = -1
            if rm == 1:
                kk = kx + int(P[21]) + delay
                if kk < end[j]: k2 = kk
            else:                                       # riconquista del prezzo d'ingresso precedente (chiusura a 5m sopra)
                for k in range(kx + 1, end[j] - 1 - delay):
                    if cl[k] > pent: k2 = k + 1 + delay; break
            if k2 < 0: break
            pent = op[k2]; kent = k2
            kx, jx, pnl, why, nadd, L = _run(kent, pent, j, sd, op, hi, lo, cl, a5, fr, start, dayidx, exit_flag, P, fee, stopslip, usefund)
            out[m, 0] = kent; out[m, 1] = kx; out[m, 2] = j; out[m, 3] = sd; out[m, 4] = L; out[m, 5] = pnl / sd; out[m, 6] = pnl
            out[m, 7] = why; out[m, 8] = nadd; out[m, 9] = 1; m += 1; nre += 1
        i = jx + 1
    return out[:m]

PREP = {}
def book(P, cost=1.0, usefund=True, coins=COINS):
    """Libro dei trade sulle tre monete con i parametri P. cost moltiplica commissioni, slippage e slippage dello stop."""
    fs = []
    for c in coins:
        if c not in PREP: PREP[c] = prep(c)
        q = PREP[c]
        o = _sim(q['op'], q['hi'], q['lo'], q['cl'], q['vw'], q['a5'], q['fr'], q['start'], q['end'], q['dayidx'], q['enter_ok'],
                 q['exit_flag'], q['atr'], P, FEE * cost, STOPSLIP * cost, usefund)
        T = pd.DataFrame(o, columns=['kent', 'kx', 'di', 's', 'L', 'R', 'ret', 'why', 'nadd', 're'])
        T['coin'] = c; T['entry'] = q['idx'][T.kent.astype(int)]; T['exit'] = q['idx'][T.kx.astype(int)]
        T['entry_day'] = q['days'][T.di.astype(int)]
        fs.append(T)
    T = pd.concat(fs, ignore_index=True).sort_values('entry', kind='stable').reset_index(drop=True)
    T['why'] = T.why.map(WHY); return T

CUT = pd.Timestamp('2023-01-01')
def _streak(r):
    b = 0; cur = 0
    for v in r:
        if v <= 0: cur += 1; b = max(b, cur)
        else: cur = 0
    return b
def blk(T, t0=None, t1=None):
    """Statistiche di un blocco. S2 = Sharpe annuo al quadrato del flusso giornaliero di R (somma per giorno d'uscita, zeri inclusi):
    e' la versione di N*(Rm/sigma)^2 che tiene conto dei trade simultanei sulle tre monete."""
    x = T
    if t0 is not None: x = x[x.entry >= t0]
    if t1 is not None: x = x[x.entry < t1]
    if len(x) < 3: return dict(n=len(x))
    a = x.entry.min() if t0 is None else max(x.entry.min(), t0); b = x.exit.max()
    y = max((b - a).days / 365.25, 0.1)
    r = x.R.values; mu = r.mean(); sg = r.std(ddof=1)
    g = x.groupby(x.entry.dt.normalize()).R.agg(['sum', 'count'])
    se_cl = np.sqrt((((g['sum'] - g['count'] * mu) ** 2).sum())) / len(r)                 # errore standard a grappoli per giorno d'ingresso
    dd = x.groupby(x.exit.dt.normalize()).R.sum().reindex(pd.date_range(a.normalize(), b.normalize()), fill_value=0.0)
    S = dd.mean() / dd.std() * np.sqrt(365.25) if dd.std() > 0 else np.nan
    npy = len(r) / y
    return dict(n=len(r), npy=npy, R=mu, sig=sg, q=mu / sg, hit=(r > 0).mean(), streak=_streak(r), t=mu / sg * np.sqrt(len(r)), t_cl=mu / se_cl,
                G=npy * (mu / sg) ** 2 * np.sign(mu), S=S, S2=S * abs(S), Rpy=mu * npy)
def row(T, label, **extra):
    a = blk(T); s = blk(T, None, CUT); v = blk(T, CUT, None)
    d = dict(cfg=label, **extra)
    for nm, z in (('', a), ('_s', s), ('_v', v)):
        for k_, val in z.items(): d[k_ + nm] = val
    return d
