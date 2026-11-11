"""A6 - grandi mosse a 24 ore (|z|>3) e raffinamenti di DIP-24h, 36 perp Binance, barre 1h. SIMULATO.
z = rendimento delle 24 ore chiuse / (sigma oraria dei 14 giorni precedenti x sqrt(24)). Un evento per moneta ogni 24 ore.
DIP (definizione v4): rendimento a 24h sotto il 2o percentile dei 90 giorni precedenti. Stop 1,5 sigma x sqrt(ore). t per giorno."""
import lib; from lib import *
lib.CLU = 'D'
SIG = {}
def feats(df, fund=None):
    """tutto noto all'apertura della barra: usa solo chiusure precedenti."""
    c = df['close']; r24 = (c.shift(1) / c.shift(25) - 1)
    sig = pd.Series(Bars.sigma(df), index=df.index)
    z = r24 / (sig * np.sqrt(24))
    q02 = r24.shift(1).rolling(2160, min_periods=720).quantile(0.02)
    return pd.DataFrame(dict(r24=r24, z=z, q02=q02))
def sig(c):
    if c in SIG: return SIG[c]
    B = bars(c, '1h'); F = feats(B.df)
    if B.fund is not None:
        F['fund'] = B.fund.reindex(F.index, method='ffill')          # ultimo funding regolato (timbro <= apertura barra)
        F['fund3'] = B.fund.rolling(3).mean().reindex(F.index, method='ffill')
    else: F['fund'] = np.nan; F['fund3'] = np.nan
    SIG[c] = F; return F
bad = trunc_check(lambda d: feats(d)['z'], bars('ETH', '1h').df.iloc[-8000:], n=10) + trunc_check(lambda d: feats(d)['q02'], bars('ETH', '1h').df.iloc[-8000:], n=10)
print('controllo di troncamento (z, q02 su ETH):', bad, 'differenze')
BZ = sig('BTC')['z']
def dedup(idx, gap=24):
    out = []; last = None
    for t in idx:
        if last is None or (t - last) >= pd.Timedelta(hours=gap): out.append(t); last = t
    return out
def fam(cond, side, H=24, k=1.5, coins=ALTS, tp=None, maker=None):
    """cond(F)->maschera booleana. side=+1/-1 oppure 'cont'/'rev' (segno della mossa)."""
    def fn(cm, delay):
        out = []
        for c in coins:
            F = sig(c); m = cond(F).fillna(False); ts = dedup(F.index[m.values]); B = bars(c, '1h')
            if not ts: continue
            sd = side if isinstance(side, int) else np.sign(F.r24.reindex(ts).values).astype(int) * (1 if side == 'cont' else -1)
            ev = pd.DataFrame(dict(t=ts, side=sd))
            if maker is None: out.append(run(B, ev, H=H, k=k, cm=cm, delay=delay, tp=tp)); continue
            for t, s_ in ev.itertuples(index=False):                         # ingresso maker: limite a 'maker' sigma sotto l'apertura
                i = B.idx(t) + delay
                if i + H + 2 >= len(B.t): continue
                s = float(np.clip(k * B.sig1h[i] * np.sqrt(H), 0.003, 0.15)); lim = B.op[i] * (1 - s_ * maker * B.sig1h[i])
                f = np.nonzero((B.lo[i:i + 4] < lim) if s_ == 1 else (B.hi[i:i + 4] > lim))[0]
                if len(f) == 0: continue
                r = sim(B, i + f[0] + 1, s_, s, H, cm=cm, entry_px=lim, entry_fee=MAKER)
                if r: r['t_dec'] = t; out.append(pd.DataFrame([r]))
        return pd.concat(out) if out else pd.DataFrame()
    return fn
hb = lambda F, a, b: (F.index.hour >= a) & (F.index.hour < b)
print('\n=== GRANDI MOSSE |z|>3: continuazione o inversione, per ora del giorno (UTC)')
for nm, cz in (('crollo z<-3', lambda F: F.z < -3), ('balzo z>+3', lambda F: F.z > 3)):
    report(f'{nm}: continuazione 24h', fam(cz, 'cont'), 'mosse')
    report(f'{nm}: inversione 24h', fam(cz, 'rev'), 'mosse')
    for a, b in ((0, 8), (8, 16), (16, 24)):
        report(f'{nm}: inversione 24h, ore {a:02d}-{b:02d}', fam(lambda F, a=a, b=b, cz=cz: cz(F) & hb(F, a, b), 'rev'), 'mosse')
    report(f'{nm}: inversione 4h', fam(cz, 'rev', H=4), 'mosse')
print('\n=== DIP-24h in R (base v4: sotto il 2o percentile a 90 giorni, long 24h)')
dip = lambda F: F.r24 < F.q02
T0 = report('DIP base, long 24h, taker', fam(dip, 1), 'dip')
for H in (4, 12, 48): report(f'DIP base, long {H}h', fam(dip, 1, H=H), 'dip')
for zt in (-3, -4, -5): report(f'DIP profondita z<{zt}', fam(lambda F, zt=zt: dip(F) & (F.z < zt), 1), 'dip')
report('DIP poco profondo (z>=-3)', fam(lambda F: dip(F) & (F.z >= -3), 1), 'dip')
print('--- stato del funding (ultimo regolato)')
report('DIP + funding < 0', fam(lambda F: dip(F) & (F.fund < 0), 1), 'dip')
report('DIP + funding tra 0 e 0,01%', fam(lambda F: dip(F) & (F.fund >= 0) & (F.fund <= 0.0001), 1), 'dip')
report('DIP + funding > 0,01%', fam(lambda F: dip(F) & (F.fund > 0.0001), 1), 'dip')
report('DIP + funding > 0,03% (long affollati liquidati)', fam(lambda F: dip(F) & (F.fund > 0.0003), 1), 'dip')
print('--- crollo di mercato o della singola moneta')
bz = lambda F: BZ.reindex(F.index)
report('DIP + anche BTC z<-2 (di mercato)', fam(lambda F: dip(F) & (bz(F) < -2), 1), 'dip')
report('DIP + BTC z>=-2 (idiosincratico)', fam(lambda F: dip(F) & (bz(F) >= -2), 1), 'dip')
print('--- ora del giorno')
for a, b in ((0, 8), (8, 16), (16, 24)):
    report(f'DIP, ore {a:02d}-{b:02d}', fam(lambda F, a=a, b=b: dip(F) & hb(F, a, b), 1), 'dip')
print('--- esecuzione')
report('DIP ingresso MAKER al prezzo di apertura (entro 4h)', fam(dip, 1, maker=0.0), 'dip')
report('DIP ingresso MAKER 1 sigma oraria sotto (entro 4h)', fam(dip, 1, maker=1.0), 'dip')
report('DIP con obiettivo 2R', fam(dip, 1, tp=2.0), 'dip')
report('DIP solo BTC/ETH/SOL', fam(dip, 1, coins=['BTC', 'ETH', 'SOL']), 'dip')
for k in (1.0, 2.5): report(f'DIP stop {k} sigma', fam(dip, 1, k=k), 'dip')
T0.to_parquet(HERE + '/_dip_base.parquet'); save('mosse')
