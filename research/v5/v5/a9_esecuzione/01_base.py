"""A9/01 - (1) il motore riscritto riproduce v4? (2) effetto del funding contato esattamente; (3) SPOT contro PERPETUAL:
quanta parte dell'R simulato e' un artefatto dell'uso delle barre spot. SIMULATO."""
import pickle
from lib import *
V4 = pickle.load(open('/home/user/GERVA-Capital/research/v5/v4/_cache/trades.pkl', 'rb'))
BASE = dict(A=dict(stop='atr', k=1.0, trail=2.0), C=dict(stop='fix', k=0.017, trail=None))
print('=== 1. Riproduzione di v4 (spot, funding contato come in v4) ===')
for nm, kw, key in (('A 1xATR trail2', BASE['A'], ('atr1.0', ('alta',), 2.0, 'long')), ('C 1,7% fisso', BASE['C'], (0.017, ('alta',), None, 'long'))):
    T = run(fund='v4', **kw); count('riproduzione'); o = V4[key]
    print(f"{nm}: mio n={len(T)} R={T.R.mean():.4f} | v4 n={len(o)} R={o.R.mean():.4f} | scarto massimo su R trade per trade: "
          f"{np.abs(T.sort_values(['coin','entry']).R.values - o.sort_values(['coin','entry']).R.values).max() if len(T)==len(o) else 'n diverso'}")
print('\n=== 2. Funding: somma giornaliera di v4 contro regolamenti effettivamente attraversati (spot, tutto il periodo) ===')
rows = []
for nm, kw in BASE.items():
    for f in ('v4', 'bn_exact', 'none'):
        T = run(fund=f, **kw); count('funding'); rows.append(stats(T, f'{nm} spot fund={f}'))
show(rows, SHORT)
print('\n=== 3. SPOT contro PERP (Binance USDT-M 5m), stesso segnale, stessi costi, funding esatto. Periodo comune 2020-01 -> 2026-10 ===')
print('    (BTC/ETH perp dal 2020-01, SOL perp dal 2020-09; il segnale resta calcolato sullo spot)')
rows = []; KEEP = {}
for nm, kw in BASE.items():
    for coins, lab in ((COINS, 'BTC+ETH+SOL'), (('BTC', 'ETH'), 'BTC+ETH')):
        P = run(coins, perp=True, **kw); count('spot_vs_perp')
        S = run(coins, **kw); S = S[S.entry >= P.entry.min()]
        # spot ristretto alle stesse date di partenza per moneta
        S = pd.concat([S[(S.coin == c) & (S.entry >= P[P.coin == c].entry.min())] for c in coins])
        rows.append(stats(S, f'{nm} SPOT {lab}')); rows.append(stats(P, f'{nm} PERP {lab}')); KEEP[(nm, lab)] = (S, P)
        m = S.merge(P, on=['coin', 'entry'], suffixes=('_s', '_p'))
        d = m.R_p - m.R_s
        print(f"{nm} {lab}: trade con stessa data d'ingresso {len(m)} (spot {len(S)}, perp {len(P)}); R perp-spot su questi: media {d.mean():+.4f} "
              f"(t {d.mean()/d.std()*np.sqrt(len(d)):+.2f}); scelta {d[m.entry<CUT].mean():+.4f} verifica {d[m.entry>=CUT].mean():+.4f}; "
              f"esito diverso (stop/tempo) {(m.why_s!=m.why_p).mean():.1%}; stop solo sul perp {((m.why_p!='tempo')&(m.why_s=='tempo')).mean():.1%}, solo sullo spot {((m.why_s!='tempo')&(m.why_p=='tempo')).mean():.1%}")
        print(f"      base all'ingresso (perp/spot-1): media {((m.pe_p/m.pe_s-1)*1e4).mean():+.2f} pb, mediana {((m.pe_p/m.pe_s-1)*1e4).median():+.2f} pb, dev.std {((m.pe_p/m.pe_s-1)*1e4).std():.1f} pb")
show(rows, SHORT)
print('\nPer anno, A (1xATR) BTC+ETH+SOL: spot | perp')
S, P = KEEP[('A', 'BTC+ETH+SOL')]; print(per_year(S).join(per_year(P), lsuffix='_spot', rsuffix='_perp').to_string())
print('\nPer anno, C (1,7%) BTC+ETH+SOL: spot | perp')
S, P = KEEP[('C', 'BTC+ETH+SOL')]; print(per_year(S).join(per_year(P), lsuffix='_spot', rsuffix='_perp').to_string())
print('\n=== 3b. Stop piu\' stretti: lo scarto spot-perp cresce? (BTC+ETH+SOL, 2020+, senza trailing) ===')
rows = []
for s in (0.006, 0.009, 0.012, 0.017, 0.027, 0.04):
    P = run(perp=True, stop='fix', k=s, trail=None); S = run(stop='fix', k=s, trail=None); count('spot_vs_perp')
    S = pd.concat([S[(S.coin == c) & (S.entry >= P[P.coin == c].entry.min())] for c in COINS])
    a, b = stats(S, ''), stats(P, '')
    rows.append(dict(stop=s, n_spot=a['n'], n_perp=b['n'], R_spot=a['R'], R_perp=b['R'], diff=b['R'] - a['R'], Rsel_spot=a['R_sel'], Rsel_perp=b['R_sel'], Rver_spot=a['R_ver'], Rver_perp=b['R_ver'],
                     stop_spot=a['stop_pct'], stop_perp=b['stop_pct']))
show(rows)
print('\n=== 3c. Le candele perp hanno code piu\' lunghe? minimo giornaliero perp contro spot (2020+) ===')
for c in COINS:
    a = SPOT[c].daily; b = PERP(c).daily; m = a.join(b, lsuffix='_s', rsuffix='_p', how='inner')
    x = (m.low_p / m.low_s - 1) * 1e4; r = ((m.high_p - m.low_p) / (m.high_s - m.low_s) - 1)
    b5 = pd.Series(PERP(c).lo, index=PERP(c).ts); s5 = pd.Series(SPOT[c].lo, index=SPOT[c].ts); j = pd.concat([b5, s5], axis=1, join='inner'); z = (j.iloc[:, 0] / j.iloc[:, 1] - 1) * 1e4
    print(f"{c}: minimo del giorno perp-spot media {x.mean():+.2f} pb, 5o percentile {x.quantile(.05):+.1f} pb, 1o {x.quantile(.01):+.1f} pb; ampiezza del giorno perp/spot-1 media {r.mean():+.3%}; "
          f"minimo della barra 5m perp-spot: media {z.mean():+.2f} pb, 1o percentile {z.quantile(.01):+.1f} pb, 0,1o {z.quantile(.001):+.1f} pb")
save_trials('01')
print('prove:', TRIALS)
