"""A6 - eventi a orario fisso su BTC/ETH/SOL perp (5m): fine settimana e gap CME, fine mese/trimestre, scadenze opzioni Deribit
(venerdi' 08:00 UTC; mensile = ultimo venerdi'; trimestrale = ultimo venerdi' di mar/giu/set/dic), ore 21-23 UTC con ingresso maker.
SIMULATO. Stop = 1,5 x sigma oraria x sqrt(ore)."""
from lib import *
COINS = ['BTC', 'ETH', 'SOL']; H1 = 12
days = pd.date_range('2020-01-15', '2026-10-30', freq='D')
def timed(times, side, H, coins=COINS, tp=None):
    def fn(cm, delay):
        return pd.concat([run(bars(c), pd.DataFrame(dict(t=list(times), side=side)), H=H, cm=cm, delay=delay, tp=tp) for c in coins])
    return fn
def utc(d, hh, tz='America/Chicago'):
    return pd.Timestamp(year=d.year, month=d.month, day=d.day, hour=hh, tz=tz).tz_convert('UTC').tz_localize(None)
print('=== FINE SETTIMANA')
fri = [d for d in days if d.weekday() == 4]
report('long ven 16:00 CT (chiusura CME) -> dom 17:00 CT (49h)', timed([utc(d, 16) for d in fri], 1, 49 * H1), 'weekend')
report('long sab 00:00 UTC -> lun 00:00 UTC (48h)', timed([d + pd.Timedelta(days=1) for d in fri], 1, 48 * H1), 'weekend')
report('long dom 17:00 CT (apertura CME) -> +24h', timed([utc(d + pd.Timedelta(days=2), 17) for d in fri], 1, 24 * H1), 'weekend')
report('long lun 00:00 UTC -> +24h', timed([d + pd.Timedelta(days=3) for d in fri], 1, 24 * H1), 'weekend')
def gap_events(B, thr, sign):
    rows = []
    for d in fri:
        t0 = utc(d, 16); t1 = utc(d + pd.Timedelta(days=2), 17); i0 = B.idx(t0); i1 = B.idx(t1)
        if i1 >= len(B.t) or B.t[i0] != t0.value or B.t[i1] != t1.value: continue
        g = B.cl[i1 - 1] / B.op[i0] - 1                                   # gap noto all'apertura CME (ultima barra chiusa)
        if abs(g) < thr: continue
        rows.append(dict(t=t1, side=int(-np.sign(g)) * sign, g=abs(g)))
    return pd.DataFrame(rows)
def gap(thr, sign, fill, coins=('BTC',)):
    def fn(cm, delay):
        out = []
        for c in coins:
            B = bars(c); ev = gap_events(B, thr, sign); H = 24 * H1
            if not fill: out.append(run(B, ev, H=H, cm=cm, delay=delay)); continue
            for t, side, g in ev.itertuples(index=False):                 # obiettivo = chiusura del gap
                i = B.idx(t); s = float(np.clip(1.5 * B.sig1h[i] * np.sqrt(24), 0.003, 0.15))
                r = sim(B, i + delay, side, s, H, tp=g / s, cm=cm)
                if r: r['t_dec'] = t; out.append(pd.DataFrame([r]))
        return pd.concat(out) if out else pd.DataFrame()
    return fn
for thr in (0.0, 0.01, 0.02):
    report(f'gap CME BTC |gap|>={thr:.0%}: chiudo il gap (contro), 24h a tempo', gap(thr, 1, False), 'weekend')
    report(f'gap CME BTC |gap|>={thr:.0%}: contro, obiettivo = gap chiuso', gap(thr, 1, True), 'weekend')
report('gap CME BTC |gap|>=1%: a favore (continuazione), 24h', gap(0.01, -1, False), 'weekend')
report('gap CME BTC+ETH+SOL |gap|>=1%: contro, 24h', gap(0.01, 1, False, COINS), 'weekend')

print('\n=== FINE MESE / TRIMESTRE')
me = pd.date_range('2020-01-31', '2026-10-31', freq='ME'); qe = [d for d in me if d.month in (3, 6, 9, 12)]
report('long ultimo giorno del mese (00:00 -> 24h)', timed(me, 1, 24 * H1), 'mese')
report('long ultimi 3 giorni del mese (72h)', timed([d - pd.Timedelta(days=2) for d in me], 1, 72 * H1), 'mese')
report('long primo giorno del mese (24h)', timed([d + pd.Timedelta(days=1) for d in me], 1, 24 * H1), 'mese')
report('long primi 3 giorni del mese (72h)', timed([d + pd.Timedelta(days=1) for d in me], 1, 72 * H1), 'mese')
report('long ultimo giorno del trimestre (24h)', timed(qe, 1, 24 * H1), 'mese')
report('long primo giorno del trimestre (24h)', timed([d + pd.Timedelta(days=1) for d in qe], 1, 24 * H1), 'mese')

print('\n=== SCADENZE OPZIONI DERIBIT (08:00 UTC)')
exp = [d + pd.Timedelta(hours=8) for d in fri]
mon = [t for t in exp if (t + pd.Timedelta(days=7)).month != t.month]; qtr = [t for t in mon if t.month in (3, 6, 9, 12)]
wk = [t for t in exp if t not in mon]
for nm, L in (('settimanale (non mensile)', wk), ('mensile', mon), ('trimestrale', qtr)):
    report(f'scadenza {nm}: long 24h prima', timed([t - pd.Timedelta(hours=24) for t in L], 1, 24 * H1 - 1), 'scadenze')
    report(f'scadenza {nm}: long 24h dopo', timed(L, 1, 24 * H1), 'scadenze')
def post_exp(L, sign):
    def fn(cm, delay):
        out = []
        for c in COINS:
            B = bars(c); rows = []
            for t in L:
                i = B.idx(t)
                if i >= len(B.t) or B.t[i] != t.value or i < 24 * H1: continue
                r = B.cl[i - 1] / B.op[i - 24 * H1] - 1
                rows.append(dict(t=t, side=int(np.sign(r) or 1) * sign))
            out.append(run(B, pd.DataFrame(rows), H=24 * H1, cm=cm, delay=delay))
        return pd.concat(out)
    return fn
report('scadenza mensile: dopo, nella direzione delle 24h prima', post_exp(mon, 1), 'scadenze')
report('scadenza mensile: dopo, contro le 24h prima', post_exp(mon, -1), 'scadenze')

print('\n=== ORE 21-23 UTC')
t21 = [d + pd.Timedelta(hours=21) for d in days]
report('21-23 UTC long, taker/taker, tutti i giorni', timed(t21, 1, 2 * H1), 'ore21')
report('21-23 UTC long, taker/taker, lun-ven', timed([t for t in t21 if t.weekday() < 5], 1, 2 * H1), 'ore21')
report('22-23 UTC long, taker/taker', timed([t + pd.Timedelta(hours=1) for t in t21], 1, H1), 'ore21')
def maker21(wd_only=False, exit_maker=False, wait=6, fee=MAKER, start=21, hold=2):
    """Ingresso: ordine limite di acquisto al prezzo di apertura delle 21:00; eseguito solo se una barra nei 30 minuti successivi
    scende SOTTO il limite (selezione avversa inclusa); altrimenti niente trade. Uscita alle 23:00: taker, oppure limite di vendita
    all'apertura delle 23:00 eseguito se il prezzo lo supera entro 30 minuti, altrimenti taker alle 23:30."""
    def fn(cm, delay):
        out = []
        for c in COINS:
            B = bars(c)
            for d in days:
                if wd_only and d.weekday() >= 5: continue
                t = d + pd.Timedelta(hours=start); i = B.idx(t) + delay
                if i + (hold + 1) * H1 >= len(B.t) or B.t[i - delay] != t.value: continue
                lim = B.op[i]; f = np.nonzero(B.lo[i:i + wait] < lim)[0]
                if len(f) == 0: continue
                k = i + f[0] + 1; j = B.idx(t + pd.Timedelta(hours=hold)) + delay
                if k >= j: continue
                s = float(np.clip(1.5 * B.sig1h[i] * np.sqrt(hold), 0.003, 0.15))
                r = sim(B, k, 1, s, j - k, cm=cm, entry_px=lim, entry_fee=fee)
                if r is None: continue
                if exit_maker and r['why'] == 'tempo':
                    lim2 = B.op[j]; g = np.nonzero(B.hi[j:j + wait] > lim2)[0]
                    if len(g): px = lim2; fo = fee * cm
                    else: px = B.op[j + wait]; fo = (TAKER + SLIP) * cm
                    net = (px / lim - 1) - fee * cm - fo - B.funding(B.t[k], B.t[j]); r['ret'] = net; r['R'] = net / s
                r['t_dec'] = t; out.append(r)
        return pd.DataFrame(out)
    return fn
report('21-23 UTC long, ingresso MAKER 1,5pb, uscita taker', maker21(), 'ore21')
report('21-23 UTC long, ingresso MAKER, uscita MAKER (o taker +30m)', maker21(exit_maker=True), 'ore21')
report('21-23 UTC long, maker/maker, lun-ven', maker21(wd_only=True, exit_maker=True), 'ore21')
report('21-23 UTC long, maker/maker a 0 pb (livello alto Hyperliquid)', maker21(exit_maker=True, fee=0.0), 'ore21')
print('controllo placebo: stessa regola maker/maker in altre fasce di 2 ore (stessa selezione avversa)')
for hh in (3, 9, 15):
    report(f'  placebo {hh:02d}-{hh+2:02d} UTC long maker/maker', maker21(exit_maker=True, start=hh), 'ore21')
save('orologio')
