"""A6 - approfondimento del candidato migliore: SHORT delle nuove quotazioni perp Binance, 24 ore dopo la quotazione. SIMULATO.
Regola base (LISTING-SHORT): a +24h dalla prima candela, short all'apertura della barra oraria; stop fisso 15% sopra l'ingresso
(leva massima 3,9x); uscita a tempo dopo 168 ore. Costi taker + slippage, +5 pb sullo stop, funding giornaliero reale.
Qui: seconda derivazione indipendente, sensibilita' (stop, durata, liquidita'), dipendenza da BTC, serie giornaliera, correlazione col fondo."""
import lib; from lib import *
lib.CLU = '7D'
C = st.get('v4_allperp_close'); FU = st.get('v4_allperp_fund'); D = st.get('v5_a6_listing_1h')
BB = {}
for s, d in D.groupby('sym'):
    d = d.set_index('t').sort_index()
    if len(d) < 24 * 12: continue
    B = Bars(s[:-4], '1h', df=d[['open', 'high', 'low', 'close', 'volume', 'quote_volume']])
    f = FU[s].dropna() if s in FU else pd.Series(dtype=float)
    B.ft = (f.index + pd.Timedelta(hours=23, minutes=59)).values.astype('datetime64[ns]').astype(np.int64); B.fv = f.values; B.fcum = np.concatenate([[0.0], np.cumsum(B.fv)])
    B.r24 = float(d['close'].iloc[23] / d['open'].iloc[0] - 1); B.qv24 = float(d['quote_volume'].iloc[:24].sum()); B.d = d
    BB[s] = B
def fam(H=168, stop=0.15, off=24, cond=None, side=-1, tp=None):
    def fn(cm, delay):
        out = []
        for s, B in BB.items():
            if cond is not None and not cond(B): continue
            if off + delay + H >= len(B.t): continue
            r = sim(B, off + delay, side, stop, H, cm=cm, tp=tp)
            if r: r['t_dec'] = pd.Timestamp(B.t[off]); r['sym'] = s; out.append(r)
        return pd.DataFrame(out)
    return fn
T = report('LISTING-SHORT base: +24h, stop 15%, 168h', fam(), 'ls')
print('\n--- seconda derivazione (senza simulatore): rendimento dello short da apertura +24h ad apertura +192h, con stop 15% sui massimi orari')
rows = []
for s, B in BB.items():
    d = B.d
    if len(d) <= 192: continue
    p0 = d['open'].iloc[24]; w = d.iloc[24:192]; hit = w['high'] >= p0 * 1.15
    if hit.any():
        o = w['open'][hit.values].iloc[0]; px = max(p0 * 1.15, o) * 1.0005; te = w.index[hit.values][0]
    else: px = d['open'].iloc[192]; te = d.index[192]
    f = FU[s].dropna(); f = f[(f.index + pd.Timedelta(hours=23, minutes=59) > d.index[24]) & (f.index + pd.Timedelta(hours=23, minutes=59) <= te)].sum()
    rows.append(dict(sym=s, t=d.index[24], R=(-(px / p0 - 1) - 2 * 0.00065 + f) / 0.15, fund=f, raw=-(d['open'].iloc[192] / p0 - 1)))
X = pd.DataFrame(rows); print(f"n={len(X)} R medio={X.R.mean():+.3f} (simulatore: {T.R.mean():+.3f}) | funding medio incassato dallo short per trade: {X.fund.mean():+.4%} ({X.fund.mean()/0.15:+.3f} R)")
print(f"rendimento grezzo dello short senza stop ne' costi, +24h -> +192h: media {X.raw.mean():+.2%}, mediana {X.raw.median():+.2%}, quota positiva {(X.raw>0).mean():.0%}")
print(f"R: dev.std {T.R.std():.2f}, R/sigma {T.R.mean()/T.R.std():.3f}, vincenti {(T.R>0).mean():.0%}, stop {(T.why=='stop').mean():.0%}, R medio dei vincenti {T.R[T.R>0].mean():+.2f}, dei perdenti {T.R[T.R<=0].mean():+.2f}, minimo {T.R.min():.2f}")
print('\n--- sensibilita'' (sono varianti: contano)')
for stp in (0.08, 0.25, 0.40): report(f'stop {stp:.0%}, 168h', fam(stop=stp), 'ls')
for H in (336, 600): report(f'stop 15%, {H}h', fam(H=H), 'ls')
report('ingresso a +48h, stop 15%, 168h', fam(off=48), 'ls')
report('con obiettivo 2R (-30%)', fam(tp=2.0), 'ls')
med = np.median([B.qv24 for B in BB.values()])
report('solo volume delle prime 24h sopra la mediana', fam(cond=lambda B: B.qv24 >= med), 'ls')
report('solo volume delle prime 24h sotto la mediana', fam(cond=lambda B: B.qv24 < med), 'ls')
for thr in (-0.10, -0.20, -0.30): report(f'solo se prime 24h < {thr:.0%}', fam(cond=lambda B, thr=thr: B.r24 < thr), 'ls')
report('solo se prime 24h tra -10% e +10%', fam(cond=lambda B: abs(B.r24) <= 0.10), 'ls')
report('solo se prime 24h > +10%', fam(cond=lambda B: B.r24 > 0.10), 'ls')
print('\n--- dipendenza da BTC (lo short di una moneta nuova e'' anche uno short del mercato)')
btc = st.get('v4_um_1h_BTCUSDT')['close']
T['btc'] = [btc.asof(x) / btc.asof(e) - 1 for e, x in zip(T.entry, T.exit)]
print(f"correlazione R del trade con il rendimento di BTC nello stesso intervallo: {T.R.corr(T.btc):+.2f}")
for lab, m in (('BTC sale nel periodo', T.btc > 0), ('BTC scende', T.btc <= 0)): print(f"  {lab}: n={m.sum()} R={T.R[m].mean():+.3f}")
b = np.polyfit(T.btc, T.ret, 1); print(f"  regressione rendimento del trade su BTC: beta {b[0]:+.2f}, alfa per trade {b[1]:+.2%} ({b[1]/0.15:+.3f} R)")
T['hedR'] = (T.ret + 1.0 * T.btc - 2 * 0.00065) / 0.15
g = T.hedR.groupby(T.t_dec.dt.floor('7D').values).sum()
print(f"  coperto con long BTC di pari nozionale (STIMA, senza stop sulla gamba BTC): R={T.hedR.mean():+.3f}, t settimanale {g.mean()/g.std()*np.sqrt(len(g)):+.2f}, scelta {T.hedR[T.t_dec<SPL].mean():+.3f}, verifica {T.hedR[T.t_dec>=SPL].mean():+.3f}")
print('\n--- serie giornaliera: rischio 0,5% del capitale per trade, al massimo 8 trade aperti (rischio totale 4%)')
T = T.sort_values('entry').reset_index(drop=True); openx = []; keep = []
for i, r in T.iterrows():
    openx = [x for x in openx if x > r.entry]
    if len(openx) < 8: keep.append(i); openx.append(r.exit)
TK = T.loc[keep]; print(f'trade tenuti {len(TK)} su {len(T)} ({len(TK)/((T.entry.max()-T.entry.min()).days/365.25):.0f} per anno); R medio dei tenuti {TK.R.mean():+.3f}')
idx = pd.date_range(T.entry.min().normalize(), '2026-10-31', freq='D')
dr = (TK.R * 0.005).groupby(TK.exit.dt.normalize().values).sum().reindex(idx).fillna(0.0)
def sh(x): return x.mean() / x.std() * np.sqrt(365) if x.std() > 0 else np.nan
def dd(x): e = (1 + x).cumprod(); return (e / e.cummax() - 1).min()
for lab, x in (('tutto', dr), ('scelta', dr[:'2022-12-31']), ('verifica', dr['2023-01-01':])):
    print(f"  {lab:9s} Sharpe {sh(x):+.2f}  rendimento annuo {x.mean()*365:+.1%}  vol {x.std()*np.sqrt(365):.1%}  caduta max {dd(x):.1%}")
print('  per anno (Sharpe):', {int(y): round(sh(x), 2) for y, x in dr.groupby(dr.index.year)})
F = pd.read_parquet(ROOT + '/research/v5/v4/fondo_serie.parquet')
m = lambda s: (1 + s).resample('ME').prod() - 1
for c in ('new', 'trade11', 'trade30'):
    if c in F: print(f"  correlazione mensile con '{c}' del fondo: {m(dr).corr(m(F[c].reindex(idx).fillna(0))):+.2f}")
TK.assign(cand='LISTING-SHORT').to_parquet(HERE + '/_ls_trades.parquet'); dr.rename('LISTING-SHORT').to_frame().to_parquet(HERE + '/_ls_daily.parquet')
save('listing_short')
