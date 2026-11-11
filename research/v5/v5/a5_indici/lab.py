"""Laboratorio A5: trade a leva su indici, oro, obbligazioni e cambi (IBKR: CFD su indici / micro future 20x, oro 20x, FX 30x).
Motore su barre GIORNALIERE con stop fisso. SIMULATO.

Regole del motore (convenzioni del BRIEF):
- segnale calcolato sulla chiusura del giorno t; ingresso all'apertura di t+1 ('open', base), di t+2 ('open2', ritardo)
  oppure alla chiusura di t ('close': ammesso come base solo per i setup di CALENDARIO, che non usano il prezzo di t);
- stop a distanza s dal prezzo d'ingresso: se l'apertura salta oltre lo stop si esce all'apertura; se il minimo (massimo per gli
  short) lo tocca si esce allo stop meno 2 bp; il giorno d'ingresso all'apertura e' controllato per intero;
- uscita a segnale: all'apertura successiva (o alla chiusura stessa se exit_at='close', solo per uscite a tempo/calendario);
- leva = min(tetto, 1/(s/0.6+0.005)); perdita massima = nozionale/leva (margine isolato);
- costi: c bp per lato sul nozionale; finanziamento CFD per notte: long (rf+1,5%)/360, short (1,5%-rf)/360; FX 0,5 bp/notte;
  dividendi accreditati ai long e addebitati agli short (differenza tra serie rettificata e non rettificata);
- R = rendimento netto sul nozionale / s.
Con stop fisso e uscite ad apertura/chiusura la barra giornaliera e' esatta per la seduta regolare; NON vede il percorso notturno
del CFD (uno stop toccato di notte e poi rientrato qui non scatta: ottimistico) -> controllo con spx_m1 (24h) in 04_percorso.py."""
import sys, json, os, warnings
sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd

ROOT = '/home/user/GERVA-Capital'; HERE = ROOT + '/research/v5/v5/a5_indici'
SEL_END = '2022-12-31'; VER_START = '2023-01-01'
CAP = {'SPY': 20, 'QQQ': 20, 'IWM': 20, 'DIA': 20, 'GLD': 20, 'TLT': 20, 'EFA': 20, 'EEM': 20,
       'EURUSD=X': 30, 'USDJPY=X': 30, 'GBPUSD=X': 30, 'AUDUSD=X': 30}
COST = {'SPY': 2.0, 'QQQ': 2.0, 'IWM': 3.0, 'DIA': 2.0, 'GLD': 3.0, 'TLT': 3.0, 'EFA': 3.0, 'EEM': 4.0,
        'EURUSD=X': 1.0, 'USDJPY=X': 1.0, 'GBPUSD=X': 1.5, 'AUDUSD=X': 1.5}          # bp per lato
TRIALS = []


def load(sym):
    for k in (f'yahoo_1d_{sym}', f'v5_yahoo_1d_{sym}'):
        p = f'{ROOT}/data_cache/{k}.parquet'
        if os.path.exists(p):
            d = pd.read_parquet(p)
            d = d[(d.high >= d.low) & (d.open > 0)]
            d = d[d.index <= '2026-11-09']
            # dividendo del giorno j come frazione della chiusura precedente
            d['div'] = ((d.adj / d.adj.shift(1)) - (d.close / d.close.shift(1))).fillna(0.0).clip(lower=0, upper=0.05)
            d.loc[d['div'] < 5e-4, 'div'] = 0.0
            if sym.endswith('=X'):
                d['div'] = 0.0
            return d
    raise FileNotFoundError(sym)


_rf = None
def rf_daily(index):
    global _rf
    if _rf is None:
        _rf = pd.read_parquet(f'{ROOT}/data_cache/yahoo_1d_^IRX.parquet')['close'] / 100.0
    return _rf.reindex(index, method='ffill').fillna(0.02).to_numpy()


def atr(d, n=14):
    pc = d.close.shift(1)
    tr = pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def ibs(d):
    return ((d.close - d.low) / (d.high - d.low).replace(0, np.nan)).fillna(0.5)


def rsi(c, n=2):
    x = c.diff(); u = x.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-x.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + u / dn.replace(0, np.nan))


def lev_for(s, cap):
    return min(cap, 1.0 / (s / 0.6 + 0.005))


def sim(sym, d, sig, side, stop_frac, entry='open', exit_sig=None, maxhold=None, exit_at='open', trail=None,
        cost_mult=1.0, name='', smin=0.002):
    """sig, stop_frac, exit_sig: Serie indicizzate come d, note alla chiusura del giorno. Restituisce DataFrame dei trade.
    trail: se dato, stop a inseguimento = massimo delle chiusure dall'ingresso - trail*s (aggiornato a fine giornata)."""
    o, h, l, c = (d[k].to_numpy() for k in ('open', 'high', 'low', 'close'))
    dv = d['div'].to_numpy(); rf = rf_daily(d.index); idx = d.index
    sg = sig.reindex(idx).fillna(False).to_numpy(bool); sf = stop_frac.reindex(idx).to_numpy(float)
    xs = exit_sig.reindex(idx).fillna(False).to_numpy(bool) if exit_sig is not None else None
    cb = COST[sym] * 1e-4 * cost_mult; cap = CAP[sym]; fx = sym.endswith('=X'); n = len(d)
    out = []; t = 0
    while t < n - 2:
        if not sg[t] or not np.isfinite(sf[t]) or sf[t] <= 0:
            t += 1; continue
        s = max(sf[t], smin)
        if entry == 'close':
            e = t; pe = c[t]; first = t + 1
        elif entry == 'open':
            e = t + 1; pe = o[e]; first = e
        else:
            e = t + 2; pe = o[e]; first = e
        if first >= n:
            break
        L = lev_for(s, cap); stop = pe * (1 - side * s); best = pe
        px = None; why = ''; j = first; hold = 0; fin = 0.0; divs = 0.0; xbar = None
        while j < n:
            # notte tra j-1 e j (solo se la posizione era aperta alla chiusura di j-1)
            if j > e or (entry == 'close'):
                nights = max((idx[j] - idx[j - 1]).days, 1)
                if fx:
                    fin += 0.5e-4 * nights
                else:
                    fin += ((rf[j - 1] + 0.015) if side > 0 else (0.015 - rf[j - 1])) / 360.0 * nights
                divs += side * dv[j]
            hold += 1
            if side * (o[j] - stop) <= 0 and not (j == e and entry != 'close'):
                px = o[j]; why = 'gap'; xbar = j; break
            ext = l[j] if side > 0 else h[j]
            if side * (ext - stop) <= 0:
                px = stop * (1 - side * 2e-4); why = 'stop'; xbar = j; break
            if maxhold is not None and hold >= maxhold and exit_at == 'close':
                px = c[j]; why = 'tempo'; xbar = j; break
            if (xs is not None and xs[j]) or (maxhold is not None and hold >= maxhold):
                if exit_at == 'close':
                    px = c[j]; why = 'segnale'; xbar = j; break
                if j + 1 >= n:
                    break
                # uscita all'apertura successiva: paga la notte
                nights = max((idx[j + 1] - idx[j]).days, 1)
                fin += (0.5e-4 * nights) if fx else ((rf[j] + 0.015) if side > 0 else (0.015 - rf[j])) / 360.0 * nights
                divs += side * dv[j + 1]
                px = o[j + 1]; why = 'segnale'; xbar = j + 1; hold += 0; break
            if trail is not None:
                best = max(best, c[j]) if side > 0 else min(best, c[j])
                ns = best * (1 - side * trail * s)
                stop = max(stop, ns) if side > 0 else min(stop, ns)
            j += 1
        if px is None:
            break
        ret = side * (px / pe - 1) - 2 * cb - fin + divs
        ret = max(ret, -1.0 / L)
        out.append((sym, idx[e], idx[xbar], side, s, L, ret / s, ret, why, hold, name))
        t = max(xbar - (1 if why == 'segnale' and exit_at == 'open' else 0), t + 1) if entry != 'close' else max(xbar, t + 1)
    return pd.DataFrame(out, columns=['symbol', 'entry', 'exit', 'side', 'stop', 'lev', 'R', 'ret', 'why', 'days', 'setup'])


def stats(T, name=''):
    """Statistiche in R: intero / scelta / verifica."""
    def one(x):
        if len(x) < 5:
            return dict(n=len(x), meanR=np.nan, sd=np.nan, t=np.nan, hit=np.nan, q=np.nan)
        m, s = x.R.mean(), x.R.std()
        return dict(n=len(x), meanR=m, sd=s, t=m / s * np.sqrt(len(x)), hit=(x.R > 0).mean(), q=m / s)
    if len(T) == 0:
        return dict(setup=name, n=0)
    yrs = max((T.exit.max() - T.entry.min()).days / 365.25, 0.5)
    a, i, v = one(T), one(T[T.entry <= SEL_END]), one(T[T.entry >= VER_START])
    ys = max((min(T.exit.max(), pd.Timestamp(SEL_END)) - T.entry.min()).days / 365.25, 0.5)
    yv = max((T.exit.max() - pd.Timestamp(VER_START)).days / 365.25, 0.5)
    return dict(setup=name, n=a['n'], n_anno=a['n'] / yrs, meanR=a['meanR'], sdR=a['sd'], t=a['t'], hit=a['hit'],
                q=a['q'], NQ2=a['n'] / yrs * a['q'] ** 2 if a['q'] > 0 else -a['n'] / yrs * a['q'] ** 2,
                R_sel=i['meanR'], t_sel=i['t'], q_sel=i['q'], n_sel=i['n'], NQ2_sel=np.sign(i['q']) * i['n'] / ys * i['q'] ** 2,
                R_ver=v['meanR'], t_ver=v['t'], q_ver=v['q'], n_ver=v['n'], NQ2_ver=np.sign(v['q']) * v['n'] / yv * v['q'] ** 2 if v['n'] >= 5 else np.nan,
                lev=T.lev.mean(), stop_pct=(T.why.isin(['stop', 'gap'])).mean())


def trial(name, T):
    r = stats(T, name); TRIALS.append(name); return r


def daily_pnl(T, risk=0.01, start='1993-01-01', end='2026-11-09'):
    """P&L giornaliero (giorni di calendario) a rischio fisso per trade, attribuito al giorno di uscita."""
    ix = pd.date_range(start, end, freq='D')
    if len(T) == 0:
        return pd.Series(0.0, index=ix)
    return (risk * T.R).groupby(pd.to_datetime(T.exit.values)).sum().reindex(ix).fillna(0.0)


def monthly(x):
    return x.resample('ME').sum()


def per_year(T):
    g = T.groupby(T.entry.dt.year).R
    return pd.DataFrame({'n': g.size(), 'meanR': g.mean(), 'sumR': g.sum()})


def save_trials(tag):
    json.dump(sorted(set(TRIALS)), open(f'{HERE}/trials_{tag}.json', 'w'), indent=0)
    return len(set(TRIALS))
