"""A1 - VERIFICA: R medio dei trade-sonda per decile di GQ (soglie congelate sulla scelta) e per livello della conviction attuale,
nei due periodi; monotonia; confronto dei secchi alti a parita' di quota di giorni; bootstrap a blocchi mensili. SIMULATO."""
import json, numpy as np, pandas as pd, lib
pd.set_option('display.width', 250); fz = json.load(open('congelato.json')); rng = np.random.default_rng(7)
def prep(Z):
    Z = Z.copy(); Z['gq'] = (Z.tq / 0.2 + Z.btc / 0.2 + Z.vwm / 0.4) / 3; Z = Z.dropna(subset=['gq', 'score'])
    Z['dec'] = np.searchsorted(fz['decili'], Z.gq.values) + 1; Z['ver'] = Z.entry >= lib.SPLIT
    Z['slev'] = pd.cut(Z.score, [-1, 0.2, 0.3, 0.45, 0.6, 0.7, 0.75, 0.85, 2], labels=['<=0,17', '0,25', '0,33-0,42', '0,50-0,58', '0,67', '0,75', '0,83', '>=0,92'])
    return Z
def rho(m): return pd.Series(m.values).corr(pd.Series(range(len(m))), method='spearman')
def tab(Z, col):
    out = {}
    for nm, g in (('tutto', Z), ('scelta', Z[~Z.ver]), ('verifica', Z[Z.ver])):
        a = g.groupby(col, observed=True).R.agg(['size', 'mean']); out[(nm, 'n')] = a['size']; out[(nm, 'R')] = a['mean']
    T = pd.DataFrame(out); print(T.round(3).to_string())
    print('   monotonia (Spearman tra numero del secchio e R medio):', {nm: round(rho(T[(nm, 'R')].dropna()), 2) for nm in ('tutto', 'scelta', 'verifica')},
          '| secchi consecutivi in salita:', {nm: int((T[(nm, 'R')].dropna().diff() > 0).sum()) for nm in ('scelta', 'verifica')}, 'su', len(T) - 1)
def boot(Z, fa, fb, n=2000):
    """differenza R medio(maschera a) - R medio(maschera b); blocchi = mesi di calendario."""
    m = Z.entry.dt.to_period('M'); G = [(g.R[fa(g)].sum(), fa(g).sum(), g.R[fb(g)].sum(), fb(g).sum()) for _, g in Z.groupby(m)]; G = np.array(G, float)
    idx = rng.integers(0, len(G), (n, len(G))); s = G[idx].sum(axis=1); d = s[:, 0] / s[:, 1] - s[:, 2] / s[:, 3]; d = d[np.isfinite(d)]
    return np.percentile(d, [5, 50, 95]).round(3), round((d > 0).mean(), 3)
def tiers(Z, lab):
    print(f'\n{lab}: secchi alti a parita\' di quota di giorni (soglie congelate)')
    rows = []
    for nm, m in (('conviction eccezionale (score>0,75)', Z.score > 0.75), ('GQ eccezionale (>= %.2f)' % fz['ecc'], Z.gq >= fz['ecc']),
                  ('conviction alta (score>0,60)', Z.score > 0.60), ('GQ alta (>= %.2f)' % fz['alta'], Z.gq >= fz['alta']),
                  ('entrambe eccezionali', (Z.score > 0.75) & (Z.gq >= fz['ecc'])), ('conv ecc, GQ no', (Z.score > 0.75) & (Z.gq < fz['ecc'])), ('GQ ecc, conv no', (Z.score <= 0.75) & (Z.gq >= fz['ecc'])),
                  ('conviction bassa (<=0,30)', Z.score <= 0.30), ('GQ bassa (<= %.2f)' % fz['bassa'], Z.gq <= fz['bassa'])):
        g = Z[m]; s = g[~g.ver]; v = g[g.ver]
        rows.append(dict(secchio=nm, n=len(g), quota_scelta=len(s) / (~Z.ver).sum(), quota_verifica=len(v) / max(Z.ver.sum(), 1), R=g.R.mean(), R_scelta=s.R.mean(), R_verifica=v.R.mean(),
                         vincenti_ver=(v.R > 0).mean(), mediana_ver=v.R.median()))
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    for per, g in (('scelta', Z[~Z.ver]), ('verifica', Z[Z.ver])):
        print(f'   bootstrap {per}: GQ ecc - conviction ecc  [5%,50%,95%], P(>0) =', *boot(g, lambda x: x.gq >= fz['ecc'], lambda x: x.score > 0.75),
              '| GQ alta - conv alta =', *boot(g, lambda x: x.gq >= fz['alta'], lambda x: x.score > 0.60),
              '| GQ decile 10 - decile 1 =', *boot(g, lambda x: x.dec == 10, lambda x: x.dec == 1),
              '| conv ecc - conv bassa =', *boot(g, lambda x: x.score > 0.75, lambda x: x.score <= 0.30))
def peryear(Z, lab):
    y = Z.entry.dt.year
    T = pd.DataFrame({'tutti i giorni': Z.groupby(y).R.mean(), 'conv ecc': Z[Z.score > 0.75].groupby(y).R.mean(), 'n conv ecc': Z[Z.score > 0.75].groupby(y).size(),
                      'GQ ecc': Z[Z.gq >= fz['ecc']].groupby(y).R.mean(), 'n GQ ecc': Z[Z.gq >= fz['ecc']].groupby(y).size(),
                      'conv alta': Z[Z.score > 0.6].groupby(y).R.mean(), 'GQ alta': Z[Z.gq >= fz['alta']].groupby(y).R.mean(), 'GQ dec 1-3': Z[Z.dec <= 3].groupby(y).R.mean()})
    print(f'\n{lab}: R medio per anno'); print(T.round(3).to_string())
for lab, fn in (('BTC/ETH/SOL, percorso 5m, stop 1xATR trail 2 (convenzione C, ~11x)', '_panel_C.parquet'),
                ('BTC/ETH/SOL, percorso 5m, stop 1,7% senza trail (convenzione A, 30x)', '_panel_A.parquet'),
                ('18 ALTRE MONETE, percorso perp 1h, stop 1xATR trail 2', '_panel_alt_C.parquet'),
                ('BTC/ETH/SOL su percorso PERP 1h (controllo incrociato del percorso), stop 1xATR trail 2', '_panel_big3_1h_C.parquet')):
    Z = prep(pd.read_parquet(fn)); print('\n' + '=' * 150 + '\n' + lab, '| trade-sonda:', len(Z), '| R medio: scelta %.3f verifica %.3f' % (Z[~Z.ver].R.mean(), Z[Z.ver].R.mean()))
    print('\nGQ per decile (1 = peggiore; soglie = decili della scelta su BTC/ETH/SOL)'); tab(Z, 'dec')
    print('\nConviction attuale per livello dello score'); tab(Z, 'slev')
    tiers(Z, lab.split(',')[0]); peryear(Z, lab.split(',')[0])
    if fn == '_panel_C.parquet':
        print('\nPer moneta, verifica:'); print(pd.DataFrame({c: dict(conv_ecc=g[g.ver & (g.score > 0.75)].R.mean(), GQ_ecc=g[g.ver & (g.gq >= fz['ecc'])].R.mean(), conv_alta=g[g.ver & (g.score > 0.6)].R.mean(), GQ_alta=g[g.ver & (g.gq >= fz['alta'])].R.mean(),
              rho_decili_GQ=rho(g[g.ver].groupby('dec').R.mean())) for c, g in Z.groupby('coin')}).round(3).to_string())
        print('correlazione di rango GQ-score: scelta %.2f, verifica %.2f' % (Z[~Z.ver][['gq', 'score']].corr(method='spearman').iloc[0, 1], Z[Z.ver][['gq', 'score']].corr(method='spearman').iloc[0, 1]))
