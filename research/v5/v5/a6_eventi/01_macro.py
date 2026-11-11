"""A6 - eventi macro USA (CPI, NFP, FOMC) su BTC/ETH/SOL perp, barre a 5 minuti. SIMULATO.
Pre-evento: long da T-24h (o T-4h) fino a T-5m. Post-evento: direzione dei primi 30 minuti (o 5) -> continuazione per 4h/24h (o 1h).
Stop = 1,5 x sigma oraria x sqrt(ore di tenuta). t-stat raggruppato per evento (3 monete = 1 osservazione)."""
from lib import *
cal = pd.read_csv(HERE + '/calendario.csv', parse_dates=['t'])
COINS = ['BTC', 'ETH', 'SOL']; M5 = pd.Timedelta('5min')
print('controllo di troncamento sigma1h (BTC):', trunc_check(lambda d: pd.Series(Bars.sigma(d), index=d.index), bars('BTC').df.iloc[-60000:], n=8), 'differenze')
def pre(kinds, hours):
    def fn(cm, delay):
        out = []
        for c in COINS:
            B = bars(c); ev = pd.DataFrame(dict(t=cal[cal.kind.isin(kinds)].t - pd.Timedelta(hours=hours), side=1))
            out.append(run(B, ev, H=hours * 12 - 1, cm=cm, delay=delay))
        return pd.concat(out)
    return fn
def post(kinds, react_bars, hold_bars, sign=1):
    def fn(cm, delay):
        out = []
        for c in COINS:
            B = bars(c); rows = []
            for t in cal[cal.kind.isin(kinds)].t:
                i = B.idx(t)
                if i + react_bars >= len(B.t) or B.t[i] != t.value: continue
                r = B.cl[i + react_bars - 1] / B.op[i] - 1                      # reazione: barre [T, T+react), chiuse alla decisione
                if r == 0: continue
                rows.append(dict(t=t + react_bars * M5, side=int(np.sign(r)) * sign))
            out.append(run(B, pd.DataFrame(rows), H=hold_bars, cm=cm, delay=delay))
        return pd.concat(out)
    return fn
KEEP = {}
for name, kinds in (('CPI', ['CPI']), ('NFP', ['NFP']), ('FOMC', ['FOMC']), ('TUTTI', ['CPI', 'NFP', 'FOMC'])):
    print(f'\n--- {name}')
    report(f'{name} pre-evento long T-24h -> T-5m', pre(kinds, 24), 'macro')
    report(f'{name} pre-evento long T-4h -> T-5m', pre(kinds, 4), 'macro')
    report(f'{name} continuazione: reazione 30m, tengo 4h', post(kinds, 6, 48), 'macro')
    KEEP[name] = report(f'{name} continuazione: reazione 30m, tengo 24h', post(kinds, 6, 288), 'macro')
    report(f'{name} continuazione: reazione 5m, tengo 1h', post(kinds, 1, 12), 'macro')
print('\n--- contrario (fade), tutti gli eventi')
report('TUTTI fade: reazione 30m, tengo 4h', post(['CPI', 'NFP', 'FOMC'], 6, 48, -1), 'macro')
report('TUTTI fade: reazione 30m, tengo 24h', post(['CPI', 'NFP', 'FOMC'], 6, 288, -1), 'macro')
report('TUTTI fade: reazione 5m, tengo 1h', post(['CPI', 'NFP', 'FOMC'], 1, 12, -1), 'macro')
print('\n--- solo dal 2022 (quando le crypto reagiscono ai dati macro: vedi 00_calendario.out) - e'' un taglio fatto a posteriori')
cal0 = cal.copy(); cal = cal[cal.t >= '2022-01-01']
report('TUTTI 2022+ continuazione 30m -> 24h', post(['CPI', 'NFP', 'FOMC'], 6, 288), 'macro')
report('TUTTI 2022+ pre-evento long 24h', pre(['CPI', 'NFP', 'FOMC'], 24), 'macro')
save('macro')
