"""A6 - comportamento del prezzo attorno al regolamento del funding (36 perp Binance, barre 1h). SIMULATO.
Segnale 'stretto' = ultimo funding GIA' regolato (T-8h); segnale 'stimato' = funding che verra' pagato a T (su Binance la stima e'
visibile in tempo reale e nell'ultima ora e' quasi definitiva: IPOTESI, non verificabile sui dati d'archivio).
Trade: 1h prima -> 1h dopo (si incassa/paga il funding), oppure le 1/4 ore dopo il regolamento. Stop 1,5 sigma x sqrt(ore).
t-stat raggruppato per giorno."""
import lib; from lib import *
lib.CLU = 'D'
EV = {}
def events(c):
    if c in EV: return EV[c]
    B = bars(c, '1h'); f = B.fund
    if f is None or len(f) < 300: EV[c] = None; return None
    d = pd.DataFrame(dict(t=f.index, f=f.values)); d['fprev'] = d.f.shift(1); d = d[d.t >= '2020-02-01'].dropna()
    EV[c] = d; return d
def fam(cond, col, off_h, H, side):
    def fn(cm, delay):
        out = []
        for c in ALTS:
            d = events(c)
            if d is None: continue
            e = d[cond(d[col])]
            if len(e) == 0: continue
            out.append(run(bars(c, '1h'), pd.DataFrame(dict(t=e.t + pd.Timedelta(hours=off_h), side=side)), H=H, cm=cm, delay=delay))
        return pd.concat(out) if out else pd.DataFrame()
    return fn
tot = sum(len(events(c)) for c in ALTS if events(c) is not None); print('regolamenti moneta in tutto:', tot)
hi = lambda x: x >= 0.0005; vhi = lambda x: x >= 0.001; neg = lambda x: x <= -0.0002; vneg = lambda x: x <= -0.001
for nm, col in (('stretto (funding precedente)', 'fprev'), ('stimato (funding di T)', 'f')):
    print(f'\n=== segnale {nm}')
    for lab, cond in (('funding >= 0,05%', hi), ('funding >= 0,10%', vhi)):
        report(f'{lab}: SHORT T-1h -> T+1h (incasso)', fam(cond, col, -1, 2, -1), 'funding')
        report(f'{lab}: LONG  T -> T+1h (dopo il pagamento)', fam(cond, col, 0, 1, 1), 'funding')
        report(f'{lab}: SHORT T -> T+4h', fam(cond, col, 0, 4, -1), 'funding')
        report(f'{lab}: SHORT T-1h -> T+7h (incasso, 8h)', fam(cond, col, -1, 8, -1), 'funding')
    for lab, cond in (('funding <= -0,02%', neg), ('funding <= -0,10%', vneg)):
        report(f'{lab}: LONG T-1h -> T+1h (incasso)', fam(cond, col, -1, 2, 1), 'funding')
        report(f'{lab}: SHORT T -> T+1h (dopo il pagamento)', fam(cond, col, 0, 1, -1), 'funding')
        report(f'{lab}: LONG T -> T+4h', fam(cond, col, 0, 4, 1), 'funding')
        report(f'{lab}: LONG T-1h -> T+7h (incasso, 8h)', fam(cond, col, -1, 8, 1), 'funding')
save('funding')
