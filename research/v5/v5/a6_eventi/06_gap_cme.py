"""A6 - approfondimento: momentum del fine settimana all'apertura CME (domenica 17:00 CT). SIMULATO.
Regola: gap = prezzo perp all'apertura CME / prezzo alla chiusura CME di venerdi' (16:00 CT) - 1. Se |gap| >= soglia, si entra
NELLA DIREZIONE del gap e si tiene 24 ore. Stop = 1,5 sigma oraria x sqrt(24). Placebo: la stessa regola (mossa di 49 ore) negli
altri giorni della settimana, per capire se e' un effetto del fine settimana o momentum generico."""
from lib import *
COINS = ['BTC', 'ETH', 'SOL']; H1 = 12
days = pd.date_range('2020-01-15', '2026-10-28', freq='D')
def utc(d, hh): return pd.Timestamp(year=d.year, month=d.month, day=d.day, hour=hh, tz='America/Chicago').tz_convert('UTC').tz_localize(None)
def ev_gap(B, thr, wd=6, zthr=None, look=49):
    rows = []
    for d in days:
        if d.weekday() != wd: continue
        t1 = utc(d, 17); t0 = t1 - pd.Timedelta(hours=look); i0 = B.idx(t0); i1 = B.idx(t1)
        if i1 >= len(B.t) or B.t[i0] != t0.value or B.t[i1] != t1.value: continue
        g = B.cl[i1 - 1] / B.op[i0] - 1
        ok = abs(g) >= thr if zthr is None else abs(g) >= zthr * B.sig1h[i1] * np.sqrt(look)
        if ok and g != 0: rows.append(dict(t=t1, side=int(np.sign(g))))
    return pd.DataFrame(rows)
def fam(thr=0.01, coins=('BTC',), H=24, wd=6, zthr=None, k=1.5, tp=None, look=49):
    def fn(cm, delay):
        return pd.concat([run(bars(c), ev_gap(bars(c), thr, wd, zthr, look), H=H * H1, k=k, cm=cm, delay=delay, tp=tp) for c in coins])
    return fn
print('=== soglia (BTC, 24h)')
for thr in (0.0, 0.005, 0.01, 0.015, 0.02, 0.03): report(f'gap CME a favore, BTC, |gap|>={thr:.1%}, 24h', fam(thr), 'gap')
for z in (0.5, 1.0): report(f'gap CME a favore, BTC, |gap|>={z} sigma(49h), 24h', fam(zthr=z), 'gap')
print('=== durata (BTC, 1%)')
for H in (4, 8, 12, 48): report(f'gap CME a favore, BTC, 1%, {H}h', fam(H=H), 'gap')
print('=== altre monete (1%, 24h)')
for c in ('ETH', 'SOL'): report(f'gap CME a favore, {c}', fam(coins=(c,)), 'gap')
T3 = report('gap CME a favore, BTC+ETH+SOL', fam(coins=COINS), 'gap')
print('=== stop')
for k in (1.0, 2.5): report(f'gap CME a favore, BTC, 1%, 24h, stop {k} sigma', fam(k=k), 'gap')
print('=== placebo: stessa regola (mossa di 49h >= 1%) alle 17:00 CT degli altri giorni')
for wd, nm in enumerate(('lun', 'mar', 'mer', 'gio', 'ven', 'sab')):
    report(f'  placebo {nm} 17:00 CT, BTC', fam(wd=wd), 'gap')
print('=== solo la parte di sabato-domenica (mossa da sab 00:00 UTC, ~46h) e solo domenica (ultime 17h)')
report('gap misurato sulle ultime 24h (dom), BTC, 1%', fam(look=24), 'gap')
TB = report('RIFERIMENTO: gap CME a favore, BTC, 1%, 24h', fam(), 'gap')
TB.to_parquet(HERE + '/_gap_btc.parquet'); T3.to_parquet(HERE + '/_gap_3.parquet'); save('gap')
