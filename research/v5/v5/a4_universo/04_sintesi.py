"""A4 - sintesi: contributo marginale per fascia, ampiezza come filtro del trio, soglie teoriche, sedi, file di consegna. SIMULATO."""
import sys, pickle, json, urllib.request; sys.path.insert(0, '/home/user/GERVA-Capital/research/v5/v5/a4_universo')
from lab import *
pd.set_option('display.width', 300); pd.set_option('display.max_columns', 50)
U, RANK = load_all(30)
TRIO = ('BTCUSDT', 'ETHUSDT', 'SOLUSDT'); nvar = 0
A = pickle.load(open('/home/user/GERVA-Capital/data_cache/v5_a4_a.pkl', 'rb')); BC = pickle.load(open('/home/user/GERVA-Capital/data_cache/v5_a4_bc.pkl', 'rb')); X = pickle.load(open('/home/user/GERVA-Capital/data_cache/v5_a4_x.pkl', 'rb'))
def show(rows, cols=('n', 'R', 't', 'hit', 'R_sc', 't_sc', 'R_ver', 't_ver', 'n_ver', 'N', 'sR', 'Neff', 'K', 'K_sc', 'K_ver', 'rho')):
    print(pd.DataFrame(rows).set_index('cfg')[list(cols)].round(3).to_string())

print('== 1) contributo marginale per fascia di rango (conviction alta), esclusi BTC/ETH/SOL ==')
rr = []
for lab in ('top30 stop 1xATR', 'top30 stop 2xATR'):
    T, M = A[lab]
    for lo, hi in ((0, 10), (10, 20), (20, 30)):
        x = T[(T['rank'] > lo) & (T['rank'] <= hi) & ~T.symbol.isin(TRIO)]
        Mx = pd.DataFrame(0.0, index=CAL, columns=['p'])
        rr.append(row(f'{lab} ranghi {lo+1}-{hi} senza trio', x))
print(pd.DataFrame(rr).set_index('cfg')[['n', 'R', 't', 'hit', 'R_sc', 't_sc', 'n_sc', 'R_ver', 't_ver', 'n_ver']].round(3).to_string())

print('\n== 2) ampiezza come FILTRO del trio: quota di membri del top-30 con conviction alta (nota la sera prima) ==')
br = pd.DataFrame({s: pd.Series((o.tier == 'alta') & (o.rank <= 30), index=o.days).reindex(CAL) for s, o in U.items()}).fillna(False).astype(float).sum(axis=1) / \
     pd.DataFrame({s: pd.Series(o.rank <= 30, index=o.days).reindex(CAL) for s, o in U.items()}).fillna(False).astype(float).sum(axis=1).replace(0, np.nan)
T0, M0 = X['trio (riferimento)']; T0 = T0.copy(); T0['amp'] = br.reindex(T0.entry).values
sel = T0[T0.entry < SPLIT]; q = sel.amp.quantile([1/3, 2/3]).values; print('terzili di selezione dell\'ampiezza nei giorni di ingresso:', q.round(3))
T0['fascia'] = np.where(T0.amp <= q[0], '1 bassa', np.where(T0.amp <= q[1], '2 media', '3 alta')); nvar += 2
g = T0.groupby(['fascia', T0.entry >= SPLIT])['R']; print(pd.DataFrame(dict(n=g.count(), R=g.mean(), t=g.mean() / g.std() * np.sqrt(g.count()))).round(3).to_string())

print('\n== 3) quanto vale l\'ampiezza SE il margine per trade fosse quello del trio (STIMA: conto controfattuale) ==')
z0 = neff(T0, M0); r0 = z0['ratio']
print(f"trio: N={z0['N']:.0f} N_eff={z0['N_eff_var']:.0f} Rm/sR={r0:.3f} K={z0['K']:.2f}  (K se indipendenti: {z0['K_indip']:.2f})")
for lab, (T, M) in (('top10 1xATR', A['top10 stop 1xATR']), ('top20 1xATR', A['top20 stop 1xATR']), ('top30 1xATR', A['top30 stop 1xATR']),
                    ('neutro L30 k5 (1xATR, 7g)', BC['c NEUTRO L30 k5']), ('neutro L30 k5 2xATR 28g', X['B neutro L30 k5 stop 2xATR tenuta 28g'])):
    z = neff(T, M); need = np.sqrt(6.3 / z['N_eff_var'])
    print(f"{lab:28s} N={z['N']:6.0f} N_eff={z['N_eff_var']:6.0f} PR={z['PR']:5.1f} rho={z['rho_stesso_giorno']:5.2f} | misurato Rm/sR={z['ratio']:+.3f} K={z['K']:+.2f} | "
          f"K col margine del trio={z['N_eff_var'] * r0 ** 2:5.2f} | Rm/sR necessario per K=6,3: {need:.3f} (= {need * z['sR']:.3f} R netti; costi medi {((T.ret - T.side * (T.p_out / T.p_in - 1)).abs() / T['stop']).mean():.3f} R)")

print('\n== 4) robustezza dei candidati meno deboli ==')
def conv_sig(U, topn=None, only=None):
    ent, ext = {}, {}
    for s, o in U.items():
        if only is not None and s not in only: continue
        ent[s] = (o.tier == 'alta') & ((o.rank <= topn) if topn else True); ext[s] = (o.tier == 'bassa')
    return ent, ext
rb = []
for name, kw, ak in (('top5 1xATR', dict(topn=5), 1.0), ('top10 2xATR', dict(topn=10), 2.0)):
    for lab, k2 in (('base', {}), ('costi x2', dict(cost_mult=2.0)), ('ritardo +1h', dict(delay=1)), ('tetto 10x', dict(cap=10.0))):
        T, M = run(U, *conv_sig(U, **kw), atr_k=ak, **k2); rb.append(row(f'{name} {lab}', T, M))
        if lab == 'base': print(name, 'per anno:'); print(per_year(T).round(3).T.to_string())
show(rb)
print('neutro L30 k5 per anno:'); print(per_year(BC['c NEUTRO L30 k5'][0]).round(3).T.to_string())
print('alt (fuori dal trio) conviction top30 1xATR per anno:'); Ta = A['top30 stop 1xATR'][0]; print(per_year(Ta[~Ta.symbol.isin(TRIO)]).round(3).T.to_string())

print('\n== 5) sedi: quali monete dell\'universo sono quotate oggi su Hyperliquid e su Kraken Futures ==')
def get(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers={'Content-Type': 'application/json', 'User-Agent': 'python'})
    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read())
base = lambda s: s.replace('USDT', '').replace('1000', '')
now = [s for s, o in U.items() if o.rank[-1] <= 30 and o.days[-1] >= CAL[-2]]; ever = list(U)
try:
    m = get('https://api.hyperliquid.xyz/info', dict(type='meta'))['universe']; hl = {x['name'].replace('k', '', 1) if x['name'].startswith('k') else x['name'] for x in m if not x.get('isDelisted')}
    hlmax = {(x['name'][1:] if x['name'].startswith('k') else x['name']): x.get('maxLeverage') for x in m}
    inn = [s for s in now if base(s) in hl]; print(f'Hyperliquid: {len(inn)}/{len(now)} dei membri attuali del top-30; {sum(base(s) in hl for s in ever)}/{len(ever)} di tutti i mai-membri')
    print('  mancanti tra gli attuali:', [s for s in now if base(s) not in hl]); print('  leva massima HL sugli attuali:', {base(s): hlmax.get(base(s)) for s in inn})
except Exception as e: print('Hyperliquid non raggiunto:', str(e)[:100])
try:
    k = get('https://futures.kraken.com/derivatives/api/v3/instruments')['instruments']; kr = {x['symbol'].upper().replace('PF_', '').replace('USD', '').replace('XBT', 'BTC') for x in k if x['symbol'].upper().startswith('PF_') and x.get('tradeable')}
    inn = [s for s in now if base(s) in kr]; print(f'Kraken Futures: {len(inn)}/{len(now)} dei membri attuali; {sum(base(s) in kr for s in ever)}/{len(ever)} di tutti i mai-membri'); print('  mancanti tra gli attuali:', [s for s in now if base(s) not in kr])
except Exception as e: print('Kraken non raggiunto:', str(e)[:100])
dead = [s for s, o in U.items() if o.days[-1] < CAL[-30]]; print(f'monete dell\'universo non piu\' scambiate su Binance (tolte dal listino o rinominate): {len(dead)}/{len(U)}', dead)

print('\n== 6) file di consegna ==')
keep = {'trio_1h_1xATR (riferimento, non nuovo)': X['trio (riferimento)'], 'top5_pit_1xATR': X['A top5 point-in-time 1xATR'], 'top10_pit_2xATR': A['top10 stop 2xATR'],
        'top30_pit_1xATR (scartato)': A['top30 stop 1xATR'], 'neutro_L30_k5 (scartato)': BC['c NEUTRO L30 k5']}
RISK = 0.01
pd.DataFrame({k: v[1].sum(axis=1) * RISK for k, v in keep.items()}).to_parquet(HERE + 'returns.parquet')
tt = pd.concat([v[0].assign(book=k, why=lambda d: d['why']) for k, v in keep.items()]).rename(columns={'stop': 'stop_distance', 'lev': 'leverage'})
tt[['book', 'symbol', 'entry', 'exit', 'side', 'stop_distance', 'leverage', 'R', 'ret', 'why', 'days', 'rank', 'volmed', 'score', 'p_in', 'p_out']].to_parquet(HERE + 'trades.parquet')
print('returns.parquet: rendimenti giornalieri netti a rischio 1% per trade (somma semplice, senza capitalizzazione), colonne:', list(keep)); print('trades.parquet:', len(tt), 'righe')
print('\nvarianti nuove in questo script:', nvar)
