"""A5 - tutti i setup, in R, su barre giornaliere. Base: segnale alla chiusura, ingresso all'apertura successiva (calendario: alla
chiusura). Per ogni variante: intero / scelta (<=2022) / verifica (>=2023), costi x2, un giorno di ritardo. SIMULATO."""
import sys; sys.path.insert(0, '/home/user/GERVA-Capital/research/v5/v5/a5_indici')
from lab import *
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
IDX = ['SPY', 'QQQ', 'IWM']
D = {s: load(s) for s in IDX + ['GLD', 'TLT', 'EURUSD=X', 'USDJPY=X', 'GBPUSD=X']}
A = {s: atr(D[s]) / D[s].close for s in D}
vix = pd.read_parquet(ROOT + '/data_cache/yahoo_1d_^VIX.parquet').close
v3m = pd.read_parquet(ROOT + '/data_cache/yahoo_1d_^VIX3M.parquet').close
ts = (vix / v3m).dropna()
gex = pd.read_parquet(ROOT + '/data_cache/gex.parquet').gex
fomc = pd.to_datetime(pd.read_csv(HERE + '/fomc_dates.csv').date)
rows = []; KEEP = {}

def run(name, sym, sig, side, sf, base='open', **kw):
    d = D[sym]
    T = sim(sym, d, sig, side, sf, entry=base, name=name, **kw)
    r = trial(name, T)
    T2 = sim(sym, d, sig, side, sf, entry=base, cost_mult=2.0, **kw)
    r['R_costi2'] = T2.R.mean() if len(T2) else np.nan
    if base == 'open':
        T3 = sim(sym, d, sig, side, sf, entry='open2', **kw)
    else:   # calendario: ritardo = ingresso all'apertura successiva
        T3 = sim(sym, d, sig, side, sf, entry='open', **kw)
    r['R_ritardo'] = T3.R.mean() if len(T3) else np.nan
    r['fam'] = name.split('|')[0]; r['sym'] = sym
    rows.append(r); KEEP[name] = T
    return T

# ---------- 1. IBS (EQ-MR come flusso di trade) ----------
for s in IDX:
    d = D[s]; x = ibs(d); up = d.close > d.close.rolling(200).mean()
    for thr in (0.1, 0.2):
        for k in (1.0, 2.0):
            for tf in (False, True):
                sig = (x < thr) & (up if tf else True)
                run(f'IBS|{s}|thr{thr}|stop{k}ATR|ma200={int(tf)}', s, sig, 1, k * A[s], exit_sig=x > 0.7, maxhold=5)
    # stessa regola con ingresso alla chiusura (decisione alle 15:50, come la sleeve EQ-MR esistente): ottimistico
    sig = (x < 0.2)
    T = sim(s, d, sig, 1, 1.0 * A[s], entry='close', exit_sig=x > 0.7, maxhold=5, exit_at='close', name=f'IBSclose|{s}')
    r = trial(f'IBSclose|{s}|thr0.2|stop1ATR (ingresso e uscita in chiusura: ottimistico)', T); r['fam'] = 'IBSclose'; r['sym'] = s; rows.append(r); KEEP[r['setup']] = T
    # short speculare
    run(f'IBSshort|{s}|thr0.9|stop1ATR', s, x > 0.9, -1, 1.0 * A[s], exit_sig=x < 0.3, maxhold=5)
# ---------- 2. RSI(2) ----------
for s in IDX:
    d = D[s]; r2 = rsi(d.close, 2); ma5 = d.close.rolling(5).mean()
    for k in (1.0, 2.0):
        run(f'RSI2|{s}|<10|stop{k}ATR', s, r2 < 10, 1, k * A[s], exit_sig=d.close > ma5, maxhold=7)
# ---------- 3. filtri di regime sull'IBS (thr 0.2, stop 1 ATR, senza ma200) ----------
for s in IDX:
    d = D[s]; x = ibs(d); base = x < 0.2
    tsr = ts.reindex(d.index); g = gex.reindex(d.index); v = vix.reindex(d.index)
    gq = g.rolling(252, min_periods=120).rank(pct=True)
    for nm, f in {'contango(VIX<VIX3M)': tsr < 1.0, 'backwardation(VIX>=VIX3M)': tsr >= 1.0, 'GEX>=0': g >= 0, 'GEX<0': g < 0,
                  'GEXbasso(q<0.33)': gq < 0.33, 'GEXalto(q>0.67)': gq > 0.67, 'VIX>=20': v >= 20, 'VIX<20': v < 20}.items():
        run(f'IBSf|{s}|{nm}', s, base & f, 1, 1.0 * A[s], exit_sig=x > 0.7, maxhold=5)
# ---------- 4. notte / giorno ----------
for s in IDX:
    d = D[s]; a = A[s]; rfv = pd.Series(rf_daily(d.index), index=d.index)
    nights = pd.Series(d.index, index=d.index).diff().shift(-1).dt.days.fillna(1)
    for cm, tag in ((1, ''), (2, '2')):
        ret = d.open.shift(-1) / d.close - 1 - 2 * COST[s] * 1e-4 * cm - (rfv + 0.015) / 360 * nights + d['div'].shift(-1)
        R = (ret / a).dropna()
        if cm == 1:
            T = pd.DataFrame({'symbol': s, 'entry': R.index, 'exit': R.index, 'side': 1, 'stop': a.reindex(R.index), 'lev': 20.0, 'R': R.values, 'ret': ret.reindex(R.index), 'why': 'tempo', 'days': 1, 'setup': f'NOTTE|{s}'})
            T = T[T.entry >= '1994-01-01']; r = trial(f'NOTTE|{s}|close->open', T)
        else:
            r['R_costi2'] = R[R.index >= '1994-01-01'].mean()
    r['fam'] = 'NOTTE'; r['sym'] = s; rows.append(r); KEEP[r['setup']] = T
    run(f'GIORNO|{s}|open->close', s, pd.Series(True, index=d.index), 1, 1.0 * A[s], maxhold=1, exit_at='close')
# ---------- 5. cambio del mese ----------
def tom_flags(ix):
    m = pd.Series(ix.to_period('M'), index=ix)
    pos_from_end = m.groupby(m).cumcount(ascending=False)      # 0 = ultimo giorno di borsa del mese
    pos_from_start = m.groupby(m).cumcount()                   # 0 = primo
    return pos_from_end, pos_from_start
for s in IDX:
    d = D[s]; pe, ps = tom_flags(d.index)
    for nm, sig in {'ingresso chiusura giorno -2': pe == 1, 'ingresso chiusura giorno -1': pe == 0}.items():
        run(f'TOM|{s}|{nm}|uscita chiusura +3', s, sig, 1, 2.0 * A[s], base='close', exit_sig=ps == 2, exit_at='close')
# ---------- 6. FOMC ----------
for s in IDX + ['GLD', 'TLT']:
    d = D[s]; isf = pd.Series(d.index.isin(fomc), index=d.index); pre = isf.shift(-1).fillna(False)
    run(f'FOMC|{s}|pre: chiusura t-1 -> chiusura t', s, pre, 1, 1.0 * A[s], base='close', maxhold=1, exit_at='close')
    run(f'FOMC|{s}|post: chiusura t -> chiusura t+1 long', s, isf, 1, 1.0 * A[s], base='close', maxhold=1, exit_at='close')
# ---------- 7. lavaggi di ampiezza (settori) ----------
SEC = ['XLB', 'XLE', 'XLF', 'XLI', 'XLK', 'XLP', 'XLU', 'XLV', 'XLY']
sd = {s: load(s) for s in SEC}
nlow = pd.DataFrame({s: ibs(sd[s]) < 0.2 for s in SEC}).dropna().sum(axis=1)
n10 = pd.DataFrame({s: sd[s].close <= sd[s].close.rolling(10).min() for s in SEC}).dropna().sum(axis=1)
d = D['SPY']; x = ibs(d)
for nm, sig in {'>=8 settori IBS<0.2': nlow >= 8, '>=7 settori al minimo di 10g': n10 >= 7}.items():
    for k in (1.0, 2.0):
        run(f'AMPIEZZA|SPY|{nm}|stop{k}ATR', 'SPY', sig.reindex(d.index).fillna(False), 1, k * A['SPY'], exit_sig=x > 0.7, maxhold=5)
# ---------- 8. gap ----------
for s in IDX:
    d = D[s]; a = A[s]
    gap = (d.open / d.close.shift(1) - 1) / a.shift(1)        # nota all'apertura di t; il motore entra a open[t] => segnale spostato a t-1
    for k in (0.5, 1.0):
        run(f'GAP|{s}|giu>{k}ATR long open->close', s, (gap < -k).shift(-1).fillna(False), 1, 1.0 * a, maxhold=1, exit_at='close')
        run(f'GAP|{s}|su>{k}ATR short open->close', s, (gap > k).shift(-1).fillna(False), -1, 1.0 * a, maxhold=1, exit_at='close')
# ---------- 9. tendenza (Donchian + stop a inseguimento) ----------
for s in ['GLD', 'TLT', 'SPY', 'QQQ', 'EURUSD=X', 'USDJPY=X', 'GBPUSD=X']:
    d = D[s]
    for N in (20, 55):
        hi = d.high.rolling(N).max().shift(1); lo = d.low.rolling(N).min().shift(1)
        xl = d.close < d.low.rolling(N // 2).min().shift(1); xh = d.close > d.high.rolling(N // 2).max().shift(1)
        run(f'TREND|{s}|N{N}|long', s, d.close > hi, 1, 2.0 * A[s], exit_sig=xl, trail=1.5)
        run(f'TREND|{s}|N{N}|short', s, d.close < lo, -1, 2.0 * A[s], exit_sig=xh, trail=1.5)
# ---------- 10. settimana delle scadenze ----------
def opex_flags(ix):
    wk = pd.Series(ix.to_period('W-FRI'), index=ix)
    fri = pd.Series([p.end_time.normalize() for p in wk], index=ix)
    is_opex = (fri.dt.day >= 15) & (fri.dt.day <= 21)
    last_of_week = wk != wk.shift(-1)
    return is_opex, last_of_week
for s in IDX:
    d = D[s]; io, lw = opex_flags(d.index)
    pre = lw & io.shift(-1).fillna(False)         # ultimo giorno della settimana prima delle scadenze
    run(f'OPEX|{s}|settimana scadenze long', s, pre, 1, 2.0 * A[s], base='close', exit_sig=lw & io, exit_at='close')
    run(f'OPEX|{s}|settimana dopo short', s, lw & io, -1, 2.0 * A[s], base='close', exit_sig=lw & ~io, exit_at='close')
# ---------- 11. GEX come regime: momentum quando e' negativo ----------
d = D['SPY']; g = gex.reindex(d.index); dn = d.close < d.close.shift(1)
run('GEXMOM|SPY|GEX<0 e giorno giu -> short 1g', 'SPY', (g < 0) & dn, -1, 1.0 * A['SPY'], maxhold=1, exit_at='close')
run('GEXMOM|SPY|GEX<0 e giorno su -> long 1g', 'SPY', (g < 0) & ~dn, 1, 1.0 * A['SPY'], maxhold=1, exit_at='close')
run('GEXMOM|SPY|GEX>=0 e giorno giu -> long 1g', 'SPY', (g >= 0) & dn, 1, 1.0 * A['SPY'], maxhold=1, exit_at='close')
# ---------- 12. FX: inversione a 3 giorni ----------
for s in ['EURUSD=X', 'USDJPY=X', 'GBPUSD=X']:
    d = D[s]; dn3 = (d.close.diff() < 0).rolling(3).sum() == 3; up3 = (d.close.diff() > 0).rolling(3).sum() == 3
    run(f'FXREV|{s}|3 giu -> long', s, dn3, 1, 1.5 * A[s], exit_sig=d.close.diff() > 0, maxhold=5)
    run(f'FXREV|{s}|3 su -> short', s, up3, -1, 1.5 * A[s], exit_sig=d.close.diff() < 0, maxhold=5)
# ---------- 13. struttura a termine del VIX come evento ----------
d = D['SPY']; tsr = ts.reindex(d.index)
run('VIXTS|SPY|primo giorno di backwardation -> long 5g', 'SPY', (tsr >= 1) & (tsr.shift(1) < 1), 1, 2.0 * A['SPY'], maxhold=5, exit_at='close')
run('VIXTS|SPY|ritorno in contango -> long 5g', 'SPY', (tsr < 1) & (tsr.shift(1) >= 1), 1, 2.0 * A['SPY'], maxhold=5, exit_at='close')

R = pd.DataFrame(rows).set_index('setup')
cols = ['n', 'n_anno', 'meanR', 'sdR', 't', 'hit', 'q', 'NQ2', 'R_sel', 't_sel', 'n_sel', 'R_ver', 't_ver', 'n_ver', 'R_costi2', 'R_ritardo', 'lev', 'stop_pct']
print(R[cols].round(3).to_string())
R.to_parquet(HERE + '/setups.parquet')
print('\nvarianti provate:', save_trials('01'))
