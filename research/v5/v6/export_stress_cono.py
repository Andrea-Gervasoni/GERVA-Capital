"""Due dati chiesti dal gruppo dei quant per il terminale, aggiunti a research/v5/quant_v4.json:
  stress_days        : rendimento di ogni strumento dell'universo nelle quattro giornate storiche di riferimento (FATTO: dati reali),
                       piu' il minimo intraday rispetto all'apertura per BTC, ETH, SOL (barre a 5 minuti);
  paper_profile_cone : ventaglio a 36 mesi del profilo ESATTO del paper (libro fino a 2x + trade 0,5% / 1%, scalini 20 / 30 / 40, con il
                       motore di rischio applicato a ogni percorso), percentili 5/25/50/75/95 del patrimonio e distribuzione della caduta.
                       SIMULATO: ricampionamento a blocchi di 30 giorni dei rendimenti storici simulati."""
import json, sys, warnings; warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/user/GERVA-Capital'); sys.path.insert(0, 'research/v5/v6')
import numpy as np, pandas as pd
from gerva.__main__ import _runner
from gerva.data import Store
A10 = pd.read_parquet('research/v5/v5/a10_sistema/returns.parquet')
def engine(x, r, h, k, day=-0.04, week=-0.08, pause=20):
    """Stessa replica del motore di rischio di scelta_profilo.py."""
    v = x.values; out = np.zeros(len(v)); eq = 1.0; hw = 1.0; scale = 1.0; off = 0; kills = 0; hist = []
    for i in range(len(v)):
        if off > 0:
            off -= 1; out[i] = 0.0; hist.append(eq)
            if off == 0: hw = eq; scale = 1.0
            continue
        out[i] = scale * v[i]; eq *= 1 + out[i]; hist.append(eq); hw = max(hw, eq); dd = eq / hw - 1
        s = 1.0
        if dd <= -k: kills += 1; off = pause; continue
        if dd <= -h: s = 0.25
        elif dd <= -r: s = 0.5
        if out[i] <= day: s = min(s, 0.5)
        if i >= 7 and eq / hist[i - 7] - 1 <= week: s = min(s, 0.25)
        scale = s
    return pd.Series(out, index=x.index), kills, 0
Q = json.load(open('research/v5/quant_v4.json'))
run = _runner(); run.market.refresh(); adj = run.market.P['adj']; cc = run.market.cclose; st = Store('data_cache')
DAYS = {'2020-03-12': 'Crollo Covid', '2021-05-19': 'Crollo crypto di maggio', '2024-08-05': 'Lunedi nero dello yen', '2025-10-10': 'Liquidazioni a cascata'}
out = []
for d, name in DAYS.items():
    t = pd.Timestamp(d); row = dict(date=d, name=name, shocks={}, intraday_low={})
    for sym in adj.columns:
        if sym.startswith('^'): continue
        s = adj[sym].dropna()
        if t in s.index and s.index.get_loc(t) > 0: row['shocks'][sym] = float(s.loc[t] / s.iloc[s.index.get_loc(t) - 1] - 1)
    for sym in cc.columns:
        s = cc[sym].dropna()
        if t in s.index and s.index.get_loc(t) > 0: row['shocks'][sym] = float(s.loc[t] / s.iloc[s.index.get_loc(t) - 1] - 1)
    for c in ('BTC', 'ETH', 'SOL'):
        try:
            b = st.get(f'bn_spot_5m_{c}USDT'); x = b.loc[d]
            if len(x): row['intraday_low'][c] = float(x['low'].min() / x['open'].iloc[0] - 1)
        except Exception: pass
    out.append(row)
Q['stress_days'] = dict(source='prezzi reali di chiusura (rendimento del giorno) e barre a 5 minuti (minimo intraday rispetto all apertura)', simulated=False, days=out)
x = A10['B2_debito_reale'] + (A10['C1_mtm_limiti'] - A10['B_pubblicato']); v = x.values; rng = np.random.default_rng(21); H, B, N = 36 * 30, 30, 2000
paths = np.empty((N, H)); dds = np.empty(N); kills = 0
for i in range(N):
    y = np.concatenate([v[a:a + B] for a in rng.integers(0, len(v) - B, H // B)])
    z, k, _ = engine(pd.Series(y), .20, .30, .40); eq = np.cumprod(1 + z.values); paths[i] = eq; dds[i] = (eq / np.maximum.accumulate(eq) - 1).min(); kills += k > 0
months = list(range(0, 37)); idx = [0] + [m * 30 - 1 for m in months[1:]]
pct = {f'p{p:02d}': [1.0] + [float(np.percentile(paths[:, j], p)) for j in idx[1:]] for p in (5, 25, 50, 75, 95)}
edges = np.round(np.arange(-0.60, 0.0001, 0.05), 2); counts, _ = np.histogram(dds, bins=edges)
Q['paper_profile_cone'] = dict(simulated=True, profile='Libro giornaliero fino a 2x + trade 0,5% / 1%, scalini 20 / 30 / 40', paths=N, method='ricampionamento a blocchi di 30 giorni; motore di rischio applicato a ogni percorso',
    months=months, **pct, cagr_p50=float(np.median(paths[:, -1]) ** (1 / 3) - 1), cagr_p05=float(np.percentile(paths[:, -1], 5) ** (1 / 3) - 1), cagr_p95=float(np.percentile(paths[:, -1], 95) ** (1 / 3) - 1),
    drawdown=dict(edges=[float(e) for e in edges], counts=[int(c) for c in counts], p50=float(np.median(dds)), p05=float(np.percentile(dds, 5)), steps=[-0.20, -0.30, -0.40],
                  p_reach_20=float((dds <= -0.20).mean()), p_reach_30=float((dds <= -0.30).mean()), p_kill=float(kills / N)))
json.dump(Q, open('research/v5/quant_v4.json', 'w'), ensure_ascii=False)
c = Q['paper_profile_cone']; print('cono: CAGR p05/p50/p95', round(c['cagr_p05'], 3), round(c['cagr_p50'], 3), round(c['cagr_p95'], 3), '| caduta p50/p05', round(c['drawdown']['p50'], 3), round(c['drawdown']['p05'], 3), '| P(-20%)', c['drawdown']['p_reach_20'], 'P(-30%)', c['drawdown']['p_reach_30'], 'P(arresto)', c['drawdown']['p_kill'])
for r in out: print(r['date'], len(r['shocks']), 'strumenti; SPY', round(r['shocks'].get('SPY', float('nan')), 3), 'BTC', round(r['shocks'].get('BTC', float('nan')), 3), 'intraday', {k: round(v, 3) for k, v in r['intraday_low'].items()})
