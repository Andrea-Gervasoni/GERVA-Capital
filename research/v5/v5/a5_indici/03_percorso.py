"""A5 - seconda derivazione sul percorso infragiornaliero e controllo di troncamento. SIMULATO.
(a) S&P 500 a 1 minuto, quasi 24 ore (histdata, 2011-2018): la regola MR rifatta da zero sul percorso al minuto, solo seduta
    regolare e 24 ore (lo stop del CFD puo' scattare di notte). NB: il loader gerva.data.sources.histdata_m1 sposta di +1h le barre
    estive (la sorgente e' gia' in ora di New York): qui e' corretto.
(b) Barre orarie Yahoo 2023-12 -> 2026-11 su SPY/QQQ/IWM: stessi trade MR sul percorso orario; variante con decisione alle 15:30.
(c) Troncamento: i segnali ricalcolati sui dati tagliati a t coincidono con quelli usati."""
import sys; sys.path.insert(0, '/home/user/GERVA-Capital/research/v5/v5/a5_indici')
from lab import *
pd.set_option('display.width', 220)
vix = pd.read_parquet(ROOT + '/data_cache/yahoo_1d_^VIX.parquet').close

def path_trades(bars, daily, sig, sf, cost_bp=2.0, rth_only=True, exit_sig=None, maxhold=5, entry_delay=0, name=''):
    """bars: OHLC infragiornaliero (indice orario NY). daily: barre giornaliere della seduta regolare. Ingresso alla prima barra della
    seduta di t+1, uscita alla prima barra della seduta dopo il segnale d'uscita; stop controllato su ogni barra del percorso."""
    rth = bars.between_time('09:30', '15:59')
    first = rth.groupby(rth.index.normalize()).apply(lambda x: x.index[0])
    pth = rth if rth_only else bars
    pi = pth.index.values; po, pl = pth.open.to_numpy(), pth.low.to_numpy()
    days = daily.index; rf = rf_daily(days); out = []; i = 0; n = len(days)
    sg = sig.reindex(days).fillna(False).to_numpy(bool); s_ = sf.reindex(days).to_numpy(); xs = exit_sig.reindex(days).fillna(False).to_numpy(bool)
    while i < n - 2:
        if not sg[i] or not np.isfinite(s_[i]) or days[i + 1] not in first.index:
            i += 1; continue
        s = max(s_[i], 0.002); L = lev_for(s, 20)
        t0 = first[days[i + 1]]; k0 = np.searchsorted(pi, np.datetime64(t0)) + entry_delay
        pe = po[k0]; stop = pe * (1 - s)
        # giorno d'uscita
        j = i + 1; hold = 1
        while j < n - 1 and not (xs[j] or hold >= maxhold):
            j += 1; hold += 1
        if j + 1 >= n or days[j + 1] not in first.index:
            break
        k1 = np.searchsorted(pi, np.datetime64(first[days[j + 1]]))
        lows = pl[k0:k1]; hit = np.nonzero(lows <= stop)[0]
        if len(hit):
            k = k0 + hit[0]; px = po[k] if (po[k] <= stop and k > k0) else stop * (1 - 2e-4); why = 'stop'
            xd = pd.Timestamp(pi[k]).normalize()
        else:
            px = po[k1]; why = 'segnale'; xd = days[j + 1]
        nights = max((xd - days[i + 1]).days, 0)
        ret = px / pe - 1 - 2 * cost_bp * 1e-4 - (rf[i] + 0.015) / 360 * nights
        ret = max(ret, -1 / L)
        out.append((days[i + 1], xd, s, ret / s, why))
        xi = days.searchsorted(xd); i = max(xi - (1 if why == 'segnale' else 0), i + 1)
    return pd.DataFrame(out, columns=['entry', 'exit', 'stop', 'R', 'why'])

def line(nm, T):
    if len(T) < 5: print(f'{nm:70s} n {len(T)}'); return
    print(f'{nm:70s} n {len(T):4d}  R medio {T.R.mean():+.3f}  sigma {T.R.std():.2f}  t {T.R.mean()/T.R.std()*np.sqrt(len(T)):+.2f}  vincenti {(T.R>0).mean():.2f}  stop {(T.why=="stop").mean():.2f}')

# ---------------- (a) S&P 500 al minuto, 2011-2018 ----------------
m = pd.read_parquet(ROOT + '/data_cache/spx_m1.parquet')
src = (m.index.tz_localize('America/New_York', ambiguous='NaT', nonexistent='NaT').tz_convert('UTC') - pd.Timedelta(hours=5)).tz_localize(None)
m = m[~src.isna()]; m.index = src[~src.isna()]; m = m[~m.index.duplicated()].sort_index()
r = m.between_time('09:30', '15:59')
g = r.groupby(r.index.normalize()).agg(open=('open', 'first'), high=('high', 'max'), low=('low', 'min'), close=('close', 'last'), n=('close', 'size'))
g = g[g.n > 300].loc['2010-12-01':]
x = ibs(g); a = atr(g) / g.close; v = vix.reindex(g.index)
print('(a) S&P 500 a 1 minuto (CFD-like), 2011-2018, regola MR; costi 2 bp per lato, finanziamento incluso')
for nm, sig in (('IBS<0.2 e VIX>=20', (x < 0.2) & (v >= 20)), ('IBS<0.2 senza filtro', x < 0.2), ('IBS<0.1 senza filtro', x < 0.1)):
    for tag, kw in (('solo seduta regolare, percorso al minuto', dict(rth_only=True)), ('24 ore, percorso al minuto (stop notturni)', dict(rth_only=False)),
                    ('24 ore, ingresso 5 minuti dopo', dict(rth_only=False, entry_delay=5))):
        T = path_trades(m, g, sig, a, exit_sig=x > 0.7, **kw); line(f'{nm} | {tag}', T); TRIALS.append(f'percorso|{nm}|{tag}')
    # motore giornaliero sulle stesse barre (deve coincidere con "solo seduta regolare")
    dd = g.copy(); dd['adj'] = dd.close; dd['div'] = 0.0
    T = sim('SPY', dd, sig, 1, a, exit_sig=x > 0.7, maxhold=5); line(f'{nm} | motore giornaliero sulle stesse barre', T)
# confronto con SPY giornaliero nello stesso periodo
d = load('SPY'); xs_ = ibs(d); T = sim('SPY', d, (xs_ < 0.2) & (vix.reindex(d.index) >= 20), 1, atr(d) / d.close, exit_sig=xs_ > 0.7, maxhold=5)
line('SPY giornaliero (Yahoo), IBS<0.2 e VIX>=20, 2011-2018', T[(T.entry >= '2011-01-01') & (T.entry <= '2018-12-31')])

# ---------------- (b) barre orarie 2023-12 -> 2026-11 ----------------
print('\n(b) barre orarie Yahoo, 2023-12 -> 2026-11, regola MR (IBS<0.2 e VIX>=20), stop 1 ATR')
allh, alld, all15 = [], [], []
for s in ['SPY', 'QQQ', 'IWM']:
    h = pd.read_parquet(f'{ROOT}/data_cache/yahoo_1h_{s}.parquet'); h = h[h.volume > 0]
    d = load(s); x = ibs(d); a = atr(d) / d.close; v = vix.reindex(d.index); sig = (x < 0.2) & (v >= 20)
    dd = d.loc[h.index[0].normalize():h.index[-1].normalize() - pd.Timedelta(days=1)]
    T = path_trades(h, dd, sig, a, cost_bp=COST[s], exit_sig=x > 0.7); T['symbol'] = s; allh.append(T)
    Td = sim(s, d, sig, 1, a, exit_sig=x > 0.7, maxhold=5); Td = Td[(Td.entry >= dd.index[0]) & (Td.exit <= dd.index[-1])]; alld.append(Td)
    # decisione alle 15:30: IBS con massimo/minimo fino alle 15:30 e prezzo delle 15:30; ingresso alla chiusura delle 16:00
    pre = h.between_time('09:30', '15:29'); gp = pre.groupby(pre.index.normalize()).agg(high=('high', 'max'), low=('low', 'min'), close=('close', 'last'))
    x15 = ((gp.close - gp.low) / (gp.high - gp.low)).reindex(d.index); pc = d.close.shift(1)
    a15 = (atr(d).shift(1) / pc)                                   # ATR noto alla vigilia
    v15 = vix.shift(1).reindex(d.index)                           # VIX della vigilia
    T15 = sim(s, d, (x15 < 0.2) & (v15 >= 20), 1, a15, entry='close', exit_sig=x15 > 0.7, maxhold=5, exit_at='close'); all15.append(T15)
H = pd.concat(allh); Dd = pd.concat(alld); H15 = pd.concat(all15)
line('percorso orario, ingresso apertura t+1 (3 indici)', H); line('motore giornaliero, stessi trade', Dd)
line('decisione 15:30 con VIX della vigilia, ingresso/uscita in chiusura (campione piccolo: NON usato)', H15); TRIALS.append('orario|decisione 15:30 ingresso in chiusura')
mrg = H.merge(Dd, on=['symbol', 'entry'], suffixes=('_h', '_d'))
print(f'trade in comune {len(mrg)} su {len(H)}/{len(Dd)}; differenza media R orario-giornaliero {(mrg.R_h-mrg.R_d).mean():+.4f}; massima |diff| {(mrg.R_h-mrg.R_d).abs().max():.3f}; corr {mrg.R_h.corr(mrg.R_d):.4f}')

# ---------------- (c) troncamento ----------------
print('\n(c) controllo di troncamento: segnali ricalcolati sui dati tagliati a t')
rng = np.random.default_rng(5); bad = 0; tot = 0
for s in ['SPY', 'QQQ', 'IWM', 'GLD']:
    d = load(s); x = ibs(d); a = atr(d) / d.close; hi = d.close > d.high.rolling(55).max().shift(1); v = vix.reindex(d.index)
    full = pd.DataFrame({'mr': (x < 0.2) & (v >= 20), 'a': a, 'trend': hi, 'xs': x > 0.7})
    for t in rng.choice(np.arange(400, len(d) - 1), 150, replace=False):
        c = d.iloc[:t + 1]; xc = ibs(c); ac = atr(c) / c.close; vc = vix[:c.index[-1]].reindex(c.index)
        now = dict(mr=bool((xc.iloc[-1] < 0.2) and (vc.iloc[-1] >= 20)), a=ac.iloc[-1], trend=bool(c.close.iloc[-1] > c.high.rolling(55).max().shift(1).iloc[-1]), xs=bool(xc.iloc[-1] > 0.7))
        ref = full.iloc[t]; tot += 4
        bad += int(now['mr'] != ref['mr']) + int(abs(now['a'] - ref.a) > 1e-12) + int(now['trend'] != ref.trend) + int(now['xs'] != ref['xs'])
print(f'confronti {tot}, differenze {bad}  (TOM e FOMC usano solo il calendario di borsa e della Fed, noti in anticipo)')
print('\nvarianti provate in questo script:', save_trials('03'))
