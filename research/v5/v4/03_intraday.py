"""Famiglia 3 - momentum e ritorno alla media intraday su BTC/ETH/SOL perpetual (Binance USDT-M 5m REALI, 2020-2026)
e variante condizionata al GEX su S&P 500 (spx_m1 2011-2018 per la scelta, SPY orario Yahoo 2023-12 -> 2026-11 per la verifica).
Costi: perp 7 pb/lato (taker + slippage), funding reale; indici 1 pb/lato (e 2 pb). Nozionale 1x, media delle 3 monete.
Segnale alla chiusura della barra, eseguito a quel prezzo, incassa dalla barra successiva; 'ritardo +1' = una barra dopo.
Tutti i numeri sono SIMULATI."""
from lab import *
F = Fam('intraday')
C3 = ['BTC', 'ETH', 'SOL']
B5 = {c: get(f'v4_um_5m_{c}USDT').loc['2020-01-01':'2026-10-31'] for c in C3}
def fund5(idx, c):
    s = get(f'bn_fund_{c}USDT').iloc[:, 0]; s.index = s.index.floor(idx.freqstr if idx.freqstr else '5min'); return s.groupby(level=0).sum().reindex(idx).fillna(0.0)
def bars(freq):
    out = {}
    for c in C3:
        b = B5[c]
        if freq != '5min':
            b = b.resample(freq).agg(dict(open='first', high='max', low='min', close='last', volume='sum', quote_volume='sum')).dropna(subset=['close'])
        out[c] = b
    return out
BARS = {f: bars(f) for f in ('5min', '15min', '1h')}
FUND = {f: {c: fund5(pd.date_range(BARS[f][c].index[0], BARS[f][c].index[-1], freq=f), c).reindex(BARS[f][c].index).fillna(0.0) for c in C3} for f in BARS}

def ev(pos, freq, fee=0.0007, lag=1):
    """pos: dict moneta -> serie di posizioni obiettivo (in [-1,1]) decise alla chiusura della barra. Ritorna rendimenti giornalieri."""
    tot = []; turn = 0.0
    for c in C3:
        b = BARS[freq][c]; r = b['close'].pct_change().fillna(0.0); p = pos[c].reindex(b.index).fillna(0.0)
        held = p.shift(lag).fillna(0.0); tr = p.shift(lag - 1).diff().abs().fillna(0.0)
        tot.append(daily(held * (r - FUND[freq][c]) - tr * fee)); turn += tr.sum() / len(C3)
    r = pd.concat(tot, axis=1).mean(axis=1); return r, turn / (len(r) / 365)

def show(label, pos, freq, keep=False):
    r, turn = ev(pos, freq); rg, _ = ev(pos, freq, fee=0.0)
    tg = three(rg); F.trials[label + ' [lordo]'] = round(tg['sh_sel'], 3)
    t = F.line(label, r, extra=f"| lordo {tg['sh_tot']:.2f}/{tg['sh_sel']:.2f}/{tg['sh_ver']:.2f} giri/anno {turn:.0f}")
    return r, t, tg

print('== 3a. Momentum della serie (segno del rendimento delle ultime k barre), sempre in posizione. Netto 7 pb | lordo')
for freq, ks in (('1h', (1, 2, 4, 8, 12, 24, 48, 72, 168, 336)), ('15min', (1, 4, 8, 16, 32, 96)), ('5min', (1, 3, 6, 12, 36, 72, 288))):
    for k in ks:
        pos = {c: np.sign(BARS[freq][c]['close'].pct_change(k)) for c in C3}
        show(f'tsmom {freq} k{k}', pos, freq)
print('   (il ritorno alla media e\' lo specchio: Sharpe lordo cambiato di segno, costi uguali)')
print('\n== 3a-bis. Momentum 1h lento con banda (posizione = media dei segni su piu\' orizzonti, arrotondata a quarti), solo long e long/short')
for ks in ((24, 72, 168), (72, 168, 336), (168, 336, 720)):
    for lo in (True, False):
        pos = {}
        for c in C3:
            cl = BARS['1h'][c]['close']; s = sum(np.sign(cl.pct_change(k)) for k in ks) / len(ks)
            v = cl.pct_change().ewm(span=168).std() * math.sqrt(24 * 365); s = (s.clip(lower=0) if lo else s) * (0.40 / v).clip(upper=1.0)
            pos[c] = (s * 4).round() / 4
        r, t, tg = show(f'tsmom-lento 1h {ks} {"solo long" if lo else "long/short"} vol 40%', pos, '1h')
        if ks == (72, 168, 336) and lo: r_slow = r; pos_slow = pos

print('\n== 3b. Ora del giorno e giorno della settimana')
H = {c: BARS['1h'][c]['close'].pct_change() for c in C3}
hm = lambda sl: pd.DataFrame({c: H[c].loc[sl].groupby(H[c].loc[sl].index.hour).mean() * 1e4 for c in C3}).mean(axis=1).round(1)
print('rendimento medio per ora UTC (pb, media 3 monete)  scelta:', hm(slice(None, SEL_END)).to_dict()); print('  verifica:', hm(slice(SPL, None)).to_dict())
for h0, h1 in ((21, 23), (22, 24), (20, 24), (0, 2), (13, 16), (16, 20)):
    pos = {c: pd.Series(((BARS['1h'][c].index.hour + 1) % 24 >= h0 % 24) & ((BARS['1h'][c].index.hour + 1) % 24 < (h1 if h1 <= 24 else 24)) if h1 > h0 else False, index=BARS['1h'][c].index).astype(float) for c in C3}
    show(f'long solo nelle ore UTC [{h0},{h1})', pos, '1h')
# walk-forward: ogni mese si scelgono le 3 ore migliori e le 3 peggiori dei 365 giorni precedenti (blocchi di 1 ora)
def wf_hours(nb, short=True):
    pos = {}
    for c in C3:
        r = H[c]; hr = r.index.hour; m = r.index.to_period('M'); out = pd.Series(0.0, index=r.index)
        for per in m.unique():
            st_ = per.start_time; tr = r.loc[st_ - pd.Timedelta(days=365):st_ - pd.Timedelta(hours=1)]
            if len(tr) < 24 * 300: continue
            mu = tr.groupby(tr.index.hour).mean(); best = mu.nlargest(nb).index; worst = mu.nsmallest(nb).index
            sel = (m == per); nxt = (hr[sel] + 1) % 24        # la posizione decisa alla chiusura dell'ora h vale per l'ora h+1
            out[sel] = np.isin(nxt, best).astype(float) - (np.isin(nxt, worst).astype(float) if short else 0.0)
        pos[c] = out
    return pos
for nb in (2, 4, 6):
    show(f'ore migliori/peggiori walk-forward, {nb}+{nb}', wf_hours(nb), '1h'); show(f'ore migliori walk-forward, solo long {nb}', wf_hours(nb, False), '1h')
Dd = {c: BARS['1h'][c]['close'].resample('1D').last().pct_change() for c in C3}
dw = lambda sl: pd.DataFrame({c: Dd[c].loc[sl].groupby(Dd[c].loc[sl].index.dayofweek).mean() * 1e4 for c in C3}).mean(axis=1).round(0)
print('rendimento medio per giorno della settimana (pb; 0=lun) scelta:', dw(slice(None, SEL_END)).to_dict(), ' verifica:', dw(slice(SPL, None)).to_dict())
for lab, dsel in (('long solo sabato+domenica', (5, 6)), ('long solo lun-ven', (0, 1, 2, 3, 4)), ('long lunedi', (0,)), ('long mercoledi', (2,)), ('long venerdi', (4,))):
    pos = {c: pd.Series(np.isin((BARS['1h'][c].index + pd.Timedelta(hours=1)).dayofweek, dsel).astype(float), index=BARS['1h'][c].index) for c in C3}
    show(lab, pos, '1h')

print('\n== 3c. Ritorno al VWAP (ancorato alle 00:00 UTC): si va contro lo scostamento quando |z|>k, si esce all\'incrocio col VWAP o a fine giornata')
def vwap_pos(freq, k, trend=False, anchor_h=0):
    pos = {}; bpd = {'5min': 288, '15min': 96, '1h': 24}[freq]
    for c in C3:
        b = BARS[freq][c]; day = (b.index - pd.Timedelta(hours=anchor_h)).normalize(); tp = (b['high'] + b['low'] + b['close']) / 3
        vw = (tp * b['volume']).groupby(day).cumsum() / b['volume'].groupby(day).cumsum().replace(0, np.nan)
        dev = b['close'] / vw - 1; n = b.groupby(day).cumcount() + 1
        sig = b['close'].pct_change().ewm(span=bpd * 5).std().shift(1) * np.sqrt(n)
        z = dev / sig; s = pd.Series(np.nan, index=b.index)
        s[np.sign(dev) != np.sign(dev.shift(1))] = 0.0; s[n == bpd] = 0.0; s[n == 1] = 0.0
        s[z > k] = 1.0 if trend else -1.0; s[z < -k] = -1.0 if trend else 1.0; s[n == bpd] = 0.0
        pos[c] = s.ffill().fillna(0.0)
    return pos
for freq in ('5min', '15min', '1h'):
    for k in (1.0, 1.5, 2.0, 3.0):
        show(f'vwap-reversione {freq} z>{k}', vwap_pos(freq, k), freq)
print('   (la variante "trend col VWAP" e\' lo specchio lordo; gia\' scartata nelle tornate precedenti)')

print('\n== 3d. Rottura del range di apertura (sessione UTC 00:00 e sessione USA 13:30 UTC), barre 5m; si esce a fine sessione')
def orb_pos(anchor_min, nbars, sess_bars, rev=False):
    pos = {}
    for c in C3:
        b = BARS['5min'][c]; day = (b.index - pd.Timedelta(minutes=anchor_min)).normalize(); n = b.groupby(day).cumcount()
        hi = b['high'].where(n < nbars).groupby(day).transform('max'); lo = b['low'].where(n < nbars).groupby(day).transform('min')
        s = pd.Series(np.nan, index=b.index); act = (n >= nbars) & (n < sess_bars - 1)
        s[act & (b['close'] > hi)] = 1.0; s[act & (b['close'] < lo)] = -1.0; s[n >= sess_bars - 1] = 0.0; s[n < nbars] = 0.0
        p = s.ffill().fillna(0.0); pos[c] = -p if rev else p
    return pos
for lab, am, sb in (('UTC 00:00, sessione 24h', 0, 288), ('USA 13:30 UTC, fino alle 20:00', 13 * 60 + 30, 78), ('Asia 00:00 UTC, fino alle 08:00', 0, 96), ('Europa 07:00 UTC, fino alle 13:30', 7 * 60, 78)):
    for nb in (6, 12):
        show(f'ORB {lab}, range {nb * 5} min', orb_pos(am, nb, sb), '5min')

print('\n== 3e. Momentum intraday alla Gao et al.: il rendimento della sessione USA (13:30->19:30 UTC) predice l\'ultima mezz\'ora (19:30-20:00)? e 00:00->23:00 predice l\'ultima ora?')
def gao(a0, a1, b1):
    pos = {}
    for c in C3:
        cl = BARS['5min'][c]['close']; t = cl.index; mins = t.hour * 60 + t.minute
        px0 = cl.where(mins == a0).ffill(); s = pd.Series(np.nan, index=t); at = mins == a1 - 5        # decisione alla chiusura della barra che finisce ad a1
        s[at] = np.sign(cl[at] / px0[at] - 1); s[mins == b1 - 5] = 0.0
        pos[c] = s.ffill().fillna(0.0)
    return pos
show('Gao USA: segno(13:30->19:30) tenuto 19:30-20:00 UTC', gao(13 * 60 + 30, 19 * 60 + 30, 20 * 60), '5min')
show('Gao USA: segno(13:30->19:00) tenuto 19:00-20:00 UTC', gao(13 * 60 + 30, 19 * 60, 20 * 60), '5min')
show('Gao UTC: segno(00:00->23:00) tenuto 23:00-24:00 UTC', gao(0, 23 * 60, 24 * 60 - 5), '5min')
show('Gao UTC: segno(00:00->22:00) tenuto 22:00-24:00 UTC', gao(0, 22 * 60, 24 * 60 - 5), '5min')

print('\n== 3f. Robustezza del migliore candidato intraday crypto (scelto sulla SCELTA tra le varianti NETTE)')
best = max((k for k in F.trials if '[lordo]' not in k and F.trials[k] is not None), key=lambda k: F.trials[k]); print('migliore netta sulla scelta:', best, F.trials[best])
r1, _ = ev(pos_slow, '1h'); F.line('tsmom-lento 1h (72,168,336) solo long: base', r1)
F.line('   costi x2', ev(pos_slow, '1h', fee=0.0014)[0]); F.line('   ritardo +1 barra', ev(pos_slow, '1h', lag=2)[0]); F.line('   spot 30 pb invece di perp', ev(pos_slow, '1h', fee=0.003)[0])
F.keep('TSMOM-1H lento solo long (perp)', r1)

# ------------------------------------------------------------------ S&P 500 condizionato al GEX
print('\n== 3g. S&P 500 intraday condizionato al GEX (GEX del giorno prima). Scelta: SPX 1 minuto 2011-05 -> 2018 (CFD, senza volumi: VWAP = media dei prezzi);')
print('   verifica: SPY orario Yahoo 2023-12 -> 2026-11 (VWAP vero). Barre da 30 min in scelta e da 1 ora in verifica. Buco 2019-2023-11: nessun dato intraday.')
gex = get('gex')['gex']
def spx_bars(freq):
    m = get('spx_m1'); m = m.between_time('09:30', '15:59'); b = m.resample(freq, origin='start_day', offset='9h30min').agg(dict(open='first', high='max', low='min', close='last')).dropna()
    b['volume'] = 1.0; return b
def gex_strategy(b, mode, k, fee):
    day = b.index.normalize(); n = b.groupby(day).cumcount() + 1; last = n == n.groupby(day).transform('max')
    tp = (b['high'] + b['low'] + b['close']) / 3
    vw = (tp * b['volume']).groupby(day).cumsum() / b['volume'].groupby(day).cumsum()
    dev = b['close'] / vw - 1; dc = b['close'][last]; dvol = dc.pct_change().ewm(span=20).std().shift(1); dvol.index = dvol.index.normalize()
    nb = n.groupby(day).transform('max'); z = dev / (dvol.reindex(day).to_numpy() * np.sqrt(n / nb))
    g = gex.shift(1); gmed = gex.rolling(252, min_periods=120).median().shift(1)         # noto il giorno prima
    gd = g.reindex(day).to_numpy(); gm = gmed.reindex(day).to_numpy()
    reg = dict(alto=gd > gm, basso=(gd <= gm) & (gd >= 0), negativo=gd < 0, tutti=np.isfinite(gd), nonalto=gd <= gm)
    def one(trend, mask):
        s = pd.Series(np.nan, index=b.index); s[np.sign(dev) != np.sign(dev.shift(1))] = 0.0; s[n == 1] = 0.0
        s[z > k] = 1.0 if trend else -1.0; s[z < -k] = -1.0 if trend else 1.0; s[last] = 0.0
        p = s.groupby(day).ffill().fillna(0.0) * mask
        r = b['close'].pct_change().fillna(0.0); r[n == 1] = b['close'][n == 1] / b['open'][n == 1] - 1       # niente gap notturno
        x = p.shift(1).fillna(0.0) * r - p.diff().abs().fillna(0.0) * fee
        return x.groupby(x.index.normalize()).sum()
    if mode == 'MR alto': return one(False, reg['alto'])
    if mode == 'MR tutti': return one(False, reg['tutti'])
    if mode == 'TF negativo': return one(True, reg['negativo'])
    if mode == 'TF nonalto': return one(True, reg['nonalto'])
    if mode == 'TF tutti': return one(True, reg['tutti'])
    if mode == 'MR alto + TF negativo': return one(False, reg['alto']) + one(True, reg['negativo'])
    if mode == 'MR alto + TF nonalto': return one(False, reg['alto']) + one(True, reg['nonalto'])
sel30 = spx_bars('30min').loc['2011-05-03':]; sel60 = spx_bars('60min').loc['2011-05-03':]
y = get('yahoo_1h_SPY'); y = y[(y.index.minute == 30) & (y['volume'] > 0)]; cnt = y.groupby(y.index.normalize()).size(); y = y[y.index.normalize().isin(cnt[cnt >= 6].index)]
cal = lambda r: r.reindex(pd.date_range(r.index[0], r.index[-1])).fillna(0.0)
def st2(r): s = stats(cal(r)); return f"Sh {s['sh']:5.2f} CAGR {100 * s['cagr']:5.1f}% vol {100 * s['vol']:4.1f}% DD {100 * s['dd']:5.1f}%"
for mode in ('MR alto', 'MR tutti', 'TF negativo', 'TF nonalto', 'TF tutti', 'MR alto + TF negativo', 'MR alto + TF nonalto'):
    for k in (0.5, 1.0, 1.5):
        a = gex_strategy(sel30, mode, k, 0.0001); a0 = gex_strategy(sel30, mode, k, 0.0); b_ = gex_strategy(sel60, mode, k, 0.0001); v = gex_strategy(y, mode, k, 0.0001); v0 = gex_strategy(y, mode, k, 0.0)
        for lab_, x in ((f'gex {mode} k{k} 30m scelta', a), (f'gex {mode} k{k} 30m scelta lordo', a0), (f'gex {mode} k{k} 60m scelta', b_)): F.trials[lab_] = round(stats(cal(x))['sh'], 3)
        print(f'{mode:24s} z>{k}: SCELTA 30m 1pb [{st2(a)}] lordo Sh {stats(cal(a0))["sh"]:5.2f} | SCELTA 60m 1pb [{st2(b_)}] | VERIFICA 60m 1pb [{st2(v)}] lordo Sh {stats(cal(v0))["sh"]:5.2f}', flush=True)
gx = pd.concat([cal(gex_strategy(sel60, 'MR alto + TF nonalto', 1.0, 0.0001)), cal(gex_strategy(y, 'MR alto + TF nonalto', 1.0, 0.0001))]); gx = gx[~gx.index.duplicated()]
F.cand['GEX-INTRADAY SPX (MR alto + TF non alto, 60m, 1 pb)'] = gx.reindex(IDX)
print('giorni per regime nella scelta: alto %.0f%%, negativo %.0f%%' % (100 * (gex.shift(1) > gex.rolling(252, min_periods=120).median().shift(1)).loc['2011-05':'2018'].mean(), 100 * (gex.shift(1) < 0).loc['2011-05':'2018'].mean()))
F.save()
