"""A4 - motore comune. SIMULATO su candele orarie reali dei perpetual USDT-M Binance (archivio, anche monete tolte dal listino).
Segnali giornalieri noti alla chiusura del giorno i-1 (UTC), ingresso all'apertura della prima barra oraria del giorno i.
Stop sul percorso orario: prima si controlla il minimo (massimo per gli short) della barra, poi si aggiorna il trailing: ordine prudente.
Costi per lato: 4,5 pb taker + slippage (2 pb se la moneta e' nel top 10 per volume, 10 pb altrimenti), +5 pb sullo stop, funding reale.
R = P&L netto / distanza dello stop. Leva = min(tetto sede, 1/(stop/0,6+0,005)); margine isolato: perdita massima 1/leva."""
import sys, warnings, importlib.util
sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from numba import njit
from gerva.data import Store
from gerva import ensemble as E
HERE = '/home/user/GERVA-Capital/research/v5/v5/a4_universo/'
st = Store('/home/user/GERVA-Capital/data_cache')
_spec = importlib.util.spec_from_file_location('dati', HERE + '00_dati.py'); _dati = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_dati)
TAKER = 0.00045; SLIP_TOP = 0.0002; SLIP_ALT = 0.0010; STOPSLIP = 0.0005; MM = 0.005; RATIO = 0.6
CAL = pd.date_range('2020-01-01', '2026-10-31', freq='D')
SPLIT = pd.Timestamp('2023-01-01')
EQUITY = 100_000.0; LIQ_SHARE = 0.001

class Coin: pass

def load_all(topn=30, verbose=False):
    """Carica le candele orarie di tutte le monete mai entrate nel top-N e prepara i segnali giornalieri."""
    q = st.get('v4_allperp_qvol'); c = st.get('v4_allperp_close')
    q = q[[s for s in q.columns if s not in _dati.NONCRYPTO]]; c = c[q.columns]
    age = c.notna().cumsum()
    med = q.rolling(90, min_periods=60).median().shift(1).where(age.shift(1) >= 200)
    med = med.where(q.rolling(5).sum().shift(1) > 0)
    rank = med.rank(axis=1, ascending=False)
    rank = rank[rank.index.day == 1].reindex(CAL).ffill()            # rango fissato il 1° del mese
    syms = [s for s in rank.columns if (rank[s] <= topn).any() and st.has(f'v5_um_1h_{s}')]
    FD = st.get('v4_allperp_fund')
    U = {}
    for s in syms:
        b = st.get(f'v5_um_1h_{s}')
        b = b[(b['high'] > 0) & (b.index >= CAL[0]) & (b.index <= CAL[-1] + pd.Timedelta(hours=23))]
        if len(b) < 24 * 30: continue
        o = Coin(); o.sym = s
        o.op = b['open'].values.astype(np.float64); o.hi = b['high'].values.astype(np.float64); o.lo = b['low'].values.astype(np.float64); o.cl = b['close'].values.astype(np.float64)
        day = b.index.normalize(); g = b.groupby(day)
        o.D = pd.DataFrame(dict(open=g['open'].first(), high=g['high'].max(), low=g['low'].min(), close=g['close'].last(), qv=g['quote_volume'].sum()))
        o.days = o.D.index; o.start = np.searchsorted(day.values, o.days.values); o.end = np.append(o.start[1:], len(b))
        o.cal = CAL.get_indexer(o.days)                               # posizione nel calendario globale
        o.atr = ((o.D['high'] - o.D['low']) / o.D['close']).rolling(14).mean().shift(1).values
        f = FD[s].dropna() if s in FD.columns else None
        o.fund = (f.reindex(o.days).values if f is not None else np.full(len(o.days), np.nan))
        o.fund_s = f
        o.rank = rank[s].reindex(o.days).values                        # rango per volume noto al 1° del mese
        o.volmed = med[s].reindex(o.days).values
        U[s] = o
    btc = U['BTCUSDT'].D['close']
    for s, o in U.items():
        F = E.crypto_signals(o.D, btc, o.fund_s); cv = E.conviction(F, 'crypto').shift(1)
        o.tier = cv['tier'].values; o.score = cv['score'].values
    if verbose: print('monete caricate:', len(U))
    return U, rank

@njit(cache=True)
def _sim(op, hi, lo, cl, k0, kend, side, sd, trail, stopslip, liqdist):
    p0 = op[k0]; stop = p0 * (1 - side * sd); best = p0; n = len(op)
    for k in range(k0, min(kend, n)):
        adv = lo[k] if side == 1 else hi[k]
        if side * (adv - stop) <= 0:
            px = min(stop, op[k]) if side == 1 else max(stop, op[k])     # gap: si esce all'apertura della barra
            px = px * (1 - side * stopslip)
            liq = p0 * (1 - side * liqdist)
            if side * (px - liq) <= 0: return liq, k, 2
            return px, k, 1
        fav = hi[k] if side == 1 else lo[k]
        if trail > 0 and side * (fav - best) > 0:
            best = fav; ns = best * (1 - side * trail * sd)
            if side * (ns - stop) > 0: stop = ns
    if kend < n: return op[kend], kend, 0
    return cl[n - 1], n - 1, 0

def run(U, ent, ext, side=1, atr_k=1.0, trail=2.0, maxhold=7, cap=40.0, cost_mult=1.0, delay=0, fixed_stop=None, pnl=True):
    """ent[s], ext[s]: vettori booleani sui giorni della moneta (gia' noti la sera prima). Ritorna (trades, matrice P&L giornaliero in R)."""
    out = []; M = np.zeros((len(CAL), len(U))) if pnl else None
    for ci, (s, o) in enumerate(U.items()):
        e = ent.get(s); x = ext.get(s)
        if e is None or not e.any(): continue
        nd_ = len(o.days); i = 0; idx = np.flatnonzero(e)
        dcl = o.D['close'].values
        for i0 in idx:
            if i0 < i or i0 >= nd_ - 1: continue
            i = i0
            a = o.atr[i]
            if np.isnan(a) or o.end[i] - o.start[i] < 20: continue
            sd = float(np.clip(atr_k * a, 0.003, 0.15)) if fixed_stop is None else fixed_stop
            L = min(cap, 1 / (sd / RATIO + MM))
            j = i + 1
            while j < nd_ - 1 and j - i < maxhold and not x[j]: j += 1
            k0 = o.start[i] + delay; kend = o.start[j] if j < nd_ else len(o.op)
            px, ke, why = _sim(o.op, o.hi, o.lo, o.cl, k0, kend, side, sd, trail if trail else 0.0, STOPSLIP * cost_mult, 1 / L - MM)
            p0 = o.op[k0]; je = int(np.searchsorted(o.start, ke, side='right') - 1)
            slip = SLIP_TOP if (o.rank[i] <= 10) else SLIP_ALT
            fee = (TAKER + slip + getattr(o, 'xfee', 0.0)) * cost_mult
            nd = max(je - i, 1); fr = o.fund[i:i + nd]; fr = np.where(np.isnan(fr), 0.0003, fr) * side
            gross = side * (px / p0 - 1); net = gross - 2 * fee - fr.sum(); net = max(net, -1 / L)
            vm = o.volmed[i]
            out.append((s, o.days[i], o.days[je], side, sd, L, net / sd, net, ('tempo', 'stop', 'liquidazione')[why], nd, o.rank[i], vm, o.score[i], p0, px))
            if pnl:
                marks = np.concatenate(([p0], dcl[i:je], [px])); d = side * np.diff(marks) / p0      # giorni i..je
                d[0] -= fee; d[-1] -= fee; d[:len(fr)] -= fr[:len(d)]
                d[-1] += net - d.sum()                                                                # quadra col netto (tetto del margine isolato)
                M[o.cal[i:je + 1], ci] += d / sd
            i = je + 1
    T = pd.DataFrame(out, columns=['symbol', 'entry', 'exit', 'side', 'stop', 'lev', 'R', 'ret', 'why', 'days', 'rank', 'volmed', 'score', 'p_in', 'p_out'])
    return T, (pd.DataFrame(M, index=CAL, columns=list(U)) if pnl else None)

def liq_scale(T, risk=0.01, equity=EQUITY):
    """Quota della posizione eseguibile col tetto di liquidita' (nozionale <= 0,1% del volume mediano giornaliero)."""
    notional = risk * equity / T['stop']; capn = LIQ_SHARE * T['volmed']
    return np.minimum(1.0, capn / notional).fillna(0.0)

def neff(T, M):
    """Numero effettivo di trade indipendenti l'anno. p_t = somma dei P&L in R di tutte le posizioni nel giorno t.
    K = (media annua)^2 / varianza annua = N_eff*(Rm/sigma_R)^2 ; N_eff = K/(Rm/sigma_R)^2. Varianza da somme settimanali (prende l'autocorrelazione)."""
    if len(T) < 5: return {}
    a, b = T.entry.min(), T.exit.max(); p = M.loc[a:b].sum(axis=1); yrs = len(p) / 365.25
    mu = p.sum() / yrs; w = p.groupby(np.arange(len(p)) // 7).sum(); Vw = w.var() * 365.25 / 7; Vd = p.var() * 365.25
    N = len(T) / yrs; Rm = T.R.mean(); sR = T.R.std(); K = mu * mu / Vw * np.sign(mu)
    act = M.loc[a:b]; act = act.loc[:, (act != 0).any()]
    ev = np.linalg.eigvalsh(np.cov(act.values.T)) if act.shape[1] > 1 else np.array([1.0]); pr = ev.sum() ** 2 / (ev ** 2).sum()
    # correlazione tra esiti di trade aperti lo stesso giorno su monete diverse
    g = T.groupby('entry')['R']; n = g.transform('count'); x = T[n > 1]
    if len(x) > 20:
        gm = x.groupby('entry')['R']; s1 = gm.sum(); s2 = (x.R ** 2).groupby(x.entry).sum(); k = gm.count()
        m = x.R.mean(); v = x.R.var(); rho = (((s1 - k * m) ** 2 - (s2 - 2 * m * s1 + k * m * m)).sum() / (k * (k - 1)).sum()) / v
    else: rho = np.nan
    return dict(N=N, Rm=Rm, sR=sR, ratio=Rm / sR, K_indip=N * (Rm / sR) ** 2, K=K, N_eff=K / (Rm / sR) ** 2 if Rm > 0 else np.nan,
                N_eff_var=N * N * sR * sR / Vw, Vd_su_Vw=Vd / Vw, PR=pr, n_monete=act.shape[1], rho_stesso_giorno=rho, sharpe=mu / np.sqrt(Vw))

def row(label, T, M=None):
    if len(T) == 0: return dict(cfg=label, n=0)
    def blk(x): return (x.R.mean(), x.R.mean() / x.R.std() * np.sqrt(len(x)) if len(x) > 2 else np.nan, len(x))
    A = blk(T); S = blk(T[T.entry < SPLIT]); V = blk(T[T.entry >= SPLIT])
    d = dict(cfg=label, n=A[2], R=A[0], t=A[1], hit=(T.R > 0).mean(), R_sc=S[0], t_sc=S[1], n_sc=S[2], R_ver=V[0], t_ver=V[1], n_ver=V[2], lev=T.lev.median())
    if M is not None:
        for nm, x, m in (('', T, M), ('_sc', T[T.entry < SPLIT], M.loc[:SPLIT - pd.Timedelta(days=1)]), ('_ver', T[T.entry >= SPLIT], M.loc[SPLIT:])):
            z = neff(x, m)
            if z: d.update({'N' + nm: z['N'], 'sR' + nm: z['sR'], 'Neff' + nm: z['N_eff_var'], 'K' + nm: z['K'], 'PR' + nm: z['PR'], 'rho' + nm: z['rho_stesso_giorno']})
    return d

def per_year(T):
    g = T.groupby(T.entry.dt.year)['R']; return pd.DataFrame(dict(n=g.count(), R=g.mean(), t=g.mean() / g.std() * np.sqrt(g.count())))
