"""B5 - laboratorio comune: pannelli, universo point-in-time, costi IBKR, motore a pesi, flusso di trade in R, statistiche.
Tutto SIMULATO su dati giornalieri Yahoo."""
import sys, os, json
sys.path.insert(0, '/home/user/GERVA-Capital')
import numpy as np, pandas as pd
from gerva.data.sources import Store
ROOT = '/home/user/GERVA-Capital/'
D = ROOT + 'research/v5/v6/b5_azioni/'
st = Store(ROOT + 'data_cache')
START, SPLIT, END = '2005-01-03', '2022-12-31', '2026-10-30'
USD_PER_EUR = 1.15

def load():
    pk = D + 'panel.pkl'
    if os.path.exists(pk): return pd.read_pickle(pk)
    tick = open(D + 'tickers_all.txt').read().split()
    raw = {}
    for s in tick + ['SPY', 'QQQ', '^IRX']:
        k = f'v6_b5_yahoo_1d_{s}'
        if st.has(k):
            df = st.get(k); df = df[~df.index.duplicated()]
            if len(df) > 60: raw[s] = df
    P = {}
    for f in ('open', 'high', 'low', 'close', 'adj', 'volume'):
        P[f] = pd.DataFrame({s: d[f] for s, d in raw.items()}).sort_index().loc['2003-01-01':END]
    cal = P['close']['SPY'].dropna().index
    for f in P: P[f] = P[f].reindex(cal)
    c, a = P['close'], P['adj']
    k = (a / c)
    # pulizia: barre con OHLC incoerenti -> NaN su open/high/low; rendimenti assurdi -> NaN
    o, h, l = P['open'].where(P['open'] > 0), P['high'], P['low']
    bad = (o > h * 1.001) | (o < l * 0.999) | (h < l)
    o = o.where(~bad)
    P['ao'], P['ah'], P['al'], P['ac'] = o * k, h * k, l * k, a
    r = P['ac'].pct_change(fill_method=None)
    P['ret'] = r.where(r.abs() < 1.5)                       # close-close totale
    P['dv'] = (c * P['volume'])
    mem = pd.read_csv(D + 'membership.csv', parse_dates=['start', 'end'])
    M = pd.DataFrame(False, index=cal, columns=c.columns)
    for t, s, e in zip(mem.ticker, mem.start, mem.end):
        if t in M.columns:
            M.loc[(cal >= s) & ((cal < e) if pd.notna(e) else True), t] = True
    P['member'] = M & c.notna()
    today = set(mem[mem.end.isna()].ticker)
    P['today'] = pd.DataFrame(np.tile([t in today for t in c.columns], (len(cal), 1)), index=cal, columns=c.columns) & c.notna()
    P['member_nominal'] = M
    P['sector'] = sectors(P)
    P['rf'] = (P['close']['^IRX'].ffill() / 100 / 252) if '^IRX' in P['close'] else pd.Series(0.0, index=cal)
    for f in list(P):
        if isinstance(P[f], pd.DataFrame) and f != 'close': P[f] = P[f].drop(columns=['SPY', 'QQQ', '^IRX'], errors='ignore')
    P['spy_ret'] = a['SPY'].pct_change()
    P['close'] = P['close'].drop(columns=['SPY', 'QQQ', '^IRX'], errors='ignore')
    pd.to_pickle(P, pk)
    return P

def sectors(P):
    """Settore GICS noto per i membri attuali; per gli altri: settore il cui indice equipesato (membri noti) e' piu' correlato
    con il residuo di mercato del titolo. E' una classificazione di comodo, non point-in-time (i settori cambiano poco)."""
    known = json.load(open(D + 'sectors_known.json'))
    r = P['ret'].drop(columns=['SPY', 'QQQ', '^IRX'], errors='ignore')
    mkt = r.mean(axis=1)
    names = sorted({v for v in known.values() if v})
    idx = pd.DataFrame({s: r[[t for t in r.columns if known.get(t) == s]].mean(axis=1) - mkt for s in names})
    out = {}
    for t in r.columns:
        if known.get(t): out[t] = known[t]; continue
        x = (r[t] - mkt).dropna()
        if len(x) < 120: out[t] = 'Unknown'; continue
        cc = idx.loc[x.index].corrwith(x)
        out[t] = cc.idxmax() if cc.notna().any() else 'Unknown'
    return pd.Series(out)

# ---------------------------------------------------------------- costi
def cost_parts(P):
    """Mezzo spread per lato: 2 bp (terzile piu' liquido per controvalore a 20 giorni), 3.5 bp, 5 bp.
    Commissione IBKR tiered USA: 0.0035 $/azione + ~0.003 $/azione di fee di borsa/regolatorie (ordine che toglie liquidita'),
    MINIMO 0.35 $ per ordine, massimo 1% del controvalore. Ritorna (mezzo_spread, commissione_per_azione_in_frazione)."""
    if 'hs' in P: return P['hs'], P['psh']
    dv = P['dv'].rolling(20, min_periods=5).median().shift(1)
    rk = dv.where(P['member'] | P['today']).rank(axis=1, pct=True)
    hs = pd.DataFrame(np.select([rk.values > 2 / 3, rk.values > 1 / 3], [2.0, 3.5], 5.0), index=dv.index, columns=dv.columns) * 1e-4
    psh = (0.0065 / P['close'].shift(1)).clip(upper=0.01).fillna(1e-4)
    P['hs'], P['psh'] = hs, psh
    return hs, psh

def run_weights(P, W, exec_='open', delay=0, borrow=0.01, fin_spread=0.015, cost_mult=1.0, account=None, lev=1.0):
    """W[t]: pesi decisi alla chiusura di t (solo dati fino a t). exec_='open': si esegue all'apertura di t+1+delay e si tiene
    da apertura ad apertura. exec_='close': si esegue alla chiusura stessa di t (MOC: ottimistico, il segnale usa quella chiusura).
    account (in $): se dato, ogni ordine paga almeno 0.35 $ -> 0.35/account di capitale per ordine (lev scala il nozionale).
    Finanziamento: debito oltre il capitale a T-bill+1.5%; prestito titoli sugli short `borrow`/anno; la cassa non rende nulla."""
    hs, psh = cost_parts(P)
    W = W.fillna(0.0) * lev
    if exec_ == 'open':
        ao = P['ao']; r = (ao.shift(-1) / ao - 1); Wd = W.shift(1 + delay)
        # ultimo giorno di vita del titolo: nessuna apertura successiva -> si esce alla chiusura
        r = r.where(r.notna(), P['ac'] / ao - 1)
    else:
        r = P['ret'].shift(-1); Wd = W.shift(delay)
    r = r.where(r.abs() < 1.5).fillna(0.0)
    Wd = Wd.fillna(0.0)
    gross = (Wd * r).sum(axis=1)
    dW = (Wd - Wd.shift(1).fillna(0.0)).abs()
    com = dW * psh
    if account is not None: com = np.maximum(com, 0.35 / account).where(dW > 1e-9, 0.0)
    c = ((dW * hs).sum(axis=1) + com.sum(axis=1)) * cost_mult
    short = (-Wd.clip(upper=0)).sum(axis=1); long = Wd.clip(lower=0).sum(axis=1)
    fin = (long - 1).clip(lower=0) * (P['rf'] + fin_spread / 252) + short * borrow / 252
    return pd.DataFrame({'net': gross - c - fin, 'gross': gross, 'cost': c, 'com': com.sum(axis=1) * cost_mult, 'fin': fin,
                         'tov': dW.sum(axis=1), 'long': long, 'short': short, 'n_ord': (dW > 1e-9).sum(axis=1)}).loc[START:END]

def topk(score, U, K, largest=True):
    """maschera dei K titoli con punteggio piu' alto (o basso) per riga, solo dentro l'universo U"""
    s = score.where(U)
    rk = s.rank(axis=1, ascending=not largest, method='first')
    return (rk <= K)

def sector_demean(x, P, U):
    x = x.where(U); out = x.copy()
    for s in P['sector'].unique():
        cols = P['sector'].index[P['sector'] == s].intersection(x.columns)
        out[cols] = x[cols].sub(x[cols].mean(axis=1), axis=0)
    return out

TRIALS = []
def evaluate(P, name, Wl, Ws=None, full=True, K=None):
    """stampa: LO, SO, LS per conto grande; LS e LO per conto da 10k EUR; costi x2; ritardo; MOC. Conta le varianti."""
    rows = []; out = {}
    def add(lab_, W, **kw):
        x = run_weights(P, W, **kw); d = stats(x['net'], lab_, x['tov']); d['gross_sh'] = round(stats(x['gross'])['sh'], 2)
        d['cost%yr'] = round(x['cost'].mean() * 25200, 1); rows.append(d); out[lab_] = x; return x
    ew = P['member'].div(P['member'].sum(axis=1), axis=0)
    bench = run_weights(P, ew)['gross']
    lo = add(name + ' LO', Wl)
    act = lo['net'] - bench; d = stats(act, name + ' LO-EW(attivo)'); rows.append(d)
    if Ws is not None:
        add(name + ' LS', Wl - Ws)
        if full: add(name + ' SO', -Ws)
    if full:
        Wb = Wl - Ws if Ws is not None else Wl; tag = ' LS' if Ws is not None else ' LO'
        add(name + tag + ' 10kEUR', Wb, account=10000 * USD_PER_EUR)
        add(name + tag + ' costi x2', Wb, cost_mult=2.0)
        add(name + tag + ' ritardo+1', Wb, delay=1)
        add(name + tag + ' MOC', Wb, exec_='close')
    TRIALS.append(name)
    print(fmt(rows)); return out

# ---------------------------------------------------------------- statistiche
def stats(r, label='', tov=None):
    r = r.dropna()
    def one(x):
        if len(x) < 30 or x.std() == 0: return dict(sh=np.nan, cagr=np.nan, mdd=np.nan, t=np.nan)
        eq = (1 + x).cumprod(); yrs = len(x) / 252
        return dict(sh=x.mean() / x.std() * np.sqrt(252), cagr=eq.iloc[-1] ** (1 / yrs) - 1, mdd=(eq / eq.cummax() - 1).min(),
                    t=x.mean() / x.std() * np.sqrt(len(x)))
    f, s, v = one(r), one(r.loc[:SPLIT]), one(r.loc['2023-01-01':])
    d = dict(label=label, sh=f['sh'], sh_sel=s['sh'], sh_ver=v['sh'], cagr=f['cagr'], cagr_sel=s['cagr'], cagr_ver=v['cagr'],
             mdd=f['mdd'], t=f['t'], vol=r.std() * np.sqrt(252))
    if tov is not None: d['tov_yr'] = tov.loc[r.index].mean() * 252
    return d

def fmt(rows, cols=None):
    df = pd.DataFrame(rows)
    pct = [c for c in df.columns if c.startswith('cagr') or c in ('mdd', 'vol')]
    for c in pct: df[c] = (df[c] * 100).round(1)
    for c in df.columns:
        if c.startswith('sh') or c in ('t', 'tov_yr'): df[c] = df[c].round(2)
    return df.to_string(index=False)

def by_year(r):
    g = r.groupby(r.index.year)
    return pd.DataFrame({'ret%': g.apply(lambda x: ((1 + x).prod() - 1) * 100).round(1), 'sh': g.apply(lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else np.nan).round(2)})

def kelly(r, rf, fin_spread=0.015, grid=np.arange(0.25, 12.01, 0.25)):
    """leva che massimizza la crescita geometrica: r_L = L*r - max(L-1,0)*(rf+spread). Ritorna (L*, g annuo, mensile)."""
    r = r.dropna(); rf = rf.reindex(r.index).fillna(0)
    best = (0, -9)
    for L in grid:
        x = L * r - max(L - 1, 0) * (rf + fin_spread / 252)
        if (x <= -1).any(): break
        g = np.log1p(x).mean() * 252
        if g > best[1]: best = (L, g)
    return best

def lev_series(r, rf, L, fin_spread=0.015):
    return L * r - max(L - 1, 0) * (rf.reindex(r.index).fillna(0) + fin_spread / 252)

def boot_p50(r, n=2000, years=3, seed=1, edge_mult=1.0):
    """P(drawdown <= -50%) in 3 anni, bootstrap a blocchi mensili della serie giornaliera (gia' a leva)."""
    r = r.dropna()
    if edge_mult != 1.0: r = r - r.mean() * (1 - edge_mult)
    months = [g.values for _, g in r.groupby([r.index.year, r.index.month])]
    rng = np.random.default_rng(seed); hit = 0; fin = []
    for _ in range(n):
        x = np.concatenate([months[i] for i in rng.integers(0, len(months), 12 * years)])
        eq = np.cumprod(1 + np.maximum(x, -0.999)); dd = (eq / np.maximum.accumulate(eq) - 1).min()
        hit += dd <= -0.5; fin.append(eq[-1])
    return hit / n, np.median(fin) ** (1 / (12 * years)) - 1

def atr(P, n=14):
    h, l, c = P['ah'], P['al'], P['ac']
    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()]).groupby(level=0).max()
    return tr.rolling(n, min_periods=n).mean()

def trades_R(P, sig, side=1, k_atr=2.0, hold=5, max_new=10, score=None, cost=None, atr_=None, stop_slip=5e-4, borrow=0.01,
             fin=0.06, lev=5.0, delay=0, cost_mult=1.0, exit_sig=None):
    """Flusso di trade: segnale alla chiusura di t (bool), ingresso all'apertura di t+1+delay, stop a k*ATR(14) dal prezzo
    d'ingresso (gap oltre lo stop -> si esce all'apertura), uscita a tempo dopo `hold` sedute all'apertura (o exit_sig alla
    chiusura -> apertura dopo). Max `max_new` nuovi trade al giorno (i migliori per `score`). R = P&L netto / distanza stop.
    Costi: `cost` per lato, +5 bp sullo stop, finanziamento sul nozionale a debito (lev-1)/lev * fin annuo, prestito titoli sugli short."""
    ao, ah, al = P['ao'].values, P['ah'].values, P['al'].values
    A = (atr_ if atr_ is not None else atr(P)).values
    C = cost.values if cost is not None else np.full(ao.shape, 4e-4)
    S = sig.values; idx = sig.index; cols = sig.columns
    sc = score.values if score is not None else None
    X = exit_sig.values if exit_sig is not None else None
    out = []; T = len(idx)
    for t in range(T - 2 - delay):
        js = np.flatnonzero(S[t])
        if len(js) == 0: continue
        if len(js) > max_new:
            if sc is not None: js = js[np.argsort(-np.nan_to_num(sc[t, js], nan=-1e9))[:max_new]]
            else: js = js[:max_new]
        e = t + 1 + delay
        for j in js:
            p0 = ao[e, j]; a = A[t, j]
            if not (p0 > 0) or not (a > 0): continue
            d = k_atr * a
            if d / p0 < 0.005: continue
            stop = p0 - side * d; px = None; why = 'time'; x = e
            for x in range(e, min(e + hold, T - 1) + 1):
                o = ao[x, j]
                if x > e:
                    if not (o > 0): px = ao[x - 1, j] if ao[x - 1, j] > 0 else p0; why = 'nodata'; break
                    if side * (o - stop) <= 0: px = o * (1 - side * stop_slip); why = 'gap'; break
                    if x == e + hold or (X is not None and X[x - 1, j]): px = o; why = 'time' if x == e + hold else 'sig'; break
                lo, hi = al[x, j], ah[x, j]
                if side == 1 and lo <= stop: px = stop * (1 - stop_slip); why = 'stop'; break
                if side == -1 and hi >= stop: px = stop * (1 + stop_slip); why = 'stop'; break
            if px is None: px = ao[x, j] if ao[x, j] > 0 else p0
            days = max(x - e, 1)
            c = (C[t, j] if C[t, j] == C[t, j] else 5e-4) * 2 * cost_mult
            carry = ((lev - 1) / lev * fin if side == 1 else borrow + (lev - 1) / lev * 0) * days / 252
            pnl = side * (px / p0 - 1) - c - carry
            out.append((idx[t], idx[e], idx[x], cols[j], side, d / p0, pnl / (d / p0), pnl, days, why))
    return pd.DataFrame(out, columns=['signal', 'entry', 'exit', 'symbol', 'side', 'stop_dist', 'R', 'ret', 'days', 'why'])

def r_stats(tr, label=''):
    if len(tr) == 0: return dict(label=label, n=0)
    def one(x):
        if len(x) < 5: return (np.nan,) * 3
        dd = x.groupby('signal')['R'].sum()             # trade dello stesso giorno sono correlati: t sui totali giornalieri
        return x.R.mean(), x.R.mean() / x.R.std(), dd.mean() / dd.std() * np.sqrt(len(dd))
    f, s, v = one(tr), one(tr[tr.signal <= SPLIT]), one(tr[tr.signal > SPLIT])
    yrs = (tr.signal.max() - tr.signal.min()).days / 365.25
    return dict(label=label, n=len(tr), n_yr=round(len(tr) / yrs, 0), days_yr=round(tr.signal.nunique() / yrs, 0), R=f[0], R_sel=s[0], R_ver=v[0],
                R_sd=f[1], t_day=f[2], t_sel=s[2], t_ver=v[2], win=(tr.R > 0).mean(), stop_pct=tr.stop_dist.median() * 100,
                hold=tr.days.mean())

def trade_daily(tr, risk=0.005, idx=None):
    """serie giornaliera (per data di uscita) rischiando `risk` del capitale per trade"""
    s = (tr.groupby('exit')['R'].sum() * risk)
    return s.reindex(idx).fillna(0.0) if idx is not None else s

def fund():
    f = pd.read_parquet(ROOT + 'research/v5/v5/a10_sistema/returns.parquet')
    return f[['B_cassa_in_tbill', 'C1_mtm_limiti', 'C3_mtm_limiti_debito_reale']]

def corr_fund(r):
    f = fund(); x = r.copy(); x.index = pd.to_datetime(x.index)
    x = x.reindex(f.index).fillna(0.0)
    m = pd.concat([x.rename('x'), f], axis=1).loc['2018-04-01':]
    mm = (1 + m).resample('ME').prod() - 1
    return {c: (round(m['x'].corr(m[c]), 2), round(mm['x'].corr(mm[c]), 2)) for c in f.columns}
