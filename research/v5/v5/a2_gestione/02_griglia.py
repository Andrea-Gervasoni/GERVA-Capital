"""A2 - griglia delle regole di gestione, una famiglia alla volta, su tre basi di stop (SIMULATO).
Basi: T = stop fisso 1,7% (30x), M = stop 1xATR (~11x), W = stop 2xATR (~6x); tutte senza trailing, ingresso a mercato all'apertura.
Per ogni variante: costi x1, costi x2, una barra (5m) di ritardo. La scelta usa solo il periodo <= 2022."""
import time, numpy as np, pandas as pd, engine as G
from engine import params, book, row
pd.set_option('display.width', 280); pd.set_option('display.max_rows', 2000)
BASES = {'T': dict(sd=0.017), 'M': dict(atr_k=1.0), 'W': dict(atr_k=2.0)}
V = []                                                     # (famiglia, etichetta, parametri extra)
def add(fam, lab, **kw): V.append((fam, lab, kw))
add('base', 'nessuna gestione')
for m in (1, 1.5, 2, 3, 4): add('trail', f'trailing {m}x stop dal massimo', tmode=1, tm=m)
for m, a in ((1, 1), (1, 2), (2, 1), (2, 2)): add('trail_att', f'trailing {m}x attivo da +{a}R', tmode=1, tm=m, tact=a)
for m in (0.5, 1, 1.5, 2, 3): add('chandelier', f'chandelier {m}x ATR intraday', tmode=2, tm=m)
for a0, am in ((0.0002, 0.002), (0.0005, 0.005), (0.002, 0.02), (0.02, 0.2)): add('parabolico', f'SAR af {a0}/{am}', tmode=3, tm=a0, afmax=am)
for b in (0.5, 1, 2, 3): add('pareggio', f'stop a pareggio da +{b}R', be=b)
for b in (1, 2): add('pareggio', f'stop a pareggio+0,1R da +{b}R', be=b, beoff=0.1)
for h, nb in ((0.5, 6), (1, 12), (2, 24), (4, 48), (8, 96), (12, 144), (24, 288), (48, 576)): add('stop_tempo', f'esci se non in utile dopo {h}h', ts=nb)
for t in (1, 2, 3, 5, 8): add('obiettivo', f'obiettivo pieno a +{t}R', tp=t)
for t in (1, 2, 3, 5): add('parziale', f'meta\' a +{t}R', tp=t, tpf=0.5)
for t in (1, 2): add('parziale', f'meta\' a +{t}R poi pareggio', tp=t, tpf=0.5, be=t)
PM = {0: 'stop al livello prec.', 1: 'stop al prezzo medio', 2: 'stop invariato'}
for n in (1, 2):
    for pm in (0, 1, 2):
        for sz in (1.0, 0.5): add('piramide', f'{n} aggiunt{"a" if n==1 else "e"} x{sz} ogni +1R, {PM[pm]}', pyn=n, pymode=pm, pysz=sz)
for pm in (0, 1, 2): add('piramide', f'1 aggiunta x1.0 a +2R, {PM[pm]}', pyn=1, pymode=pm, pystep=2.0)
for c_, h in ((12, 1), (48, 4), (96, 8)):
    for mx in (1, 2): add('rientro', f'rientro dopo {h}h, max {mx}', remode=1, rec=c_, remax=mx)
for mx in (1, 2): add('rientro', f'rientro su riconquista dell\'ingresso, max {mx}', remode=2, remax=mx)
for x in (0.1, 0.25, 0.5, 1.0): add('ingresso', f'limite {x}xATR sotto l\'apertura', emode=1, ex=x)
for nb, h in ((12, 1), (48, 4), (96, 8)): add('ingresso', f'ritorno al VWAP dopo {h}h', emode=2, earg=nb)
for nb, h in ((96, '08:00'), (162, '13:30'), (240, '20:00')): add('ingresso', f'mercato alle {h} UTC', emode=3, earg=nb)
for x in (0.25, 0.5): add('ingresso', f'stop-buy {x}xATR sopra l\'apertura', emode=4, ex=x)

if __name__ == '__main__':
    t0 = time.time(); rows = []
    for bn, bk in BASES.items():
        for fam, lab, kw in V:
            P = params(**bk, **kw)
            T = book(P); d = row(T, lab, base=bn, fam=fam)
            T2 = book(P, cost=2.0); r2 = row(T2, lab)
            P1 = P.copy(); P1[G.DELAY] = 1; T1 = book(P1); r1 = row(T1, lab)
            for k in ('R', 'q', 'G', 'S2', 'R_s', 'q_s', 'G_s', 'S2_s', 'R_v', 'q_v', 'G_v', 'S2_v'):
                d[k + '_c2'] = r2.get(k, np.nan); d[k + '_d1'] = r1.get(k, np.nan)
            d['add_share'] = (T.nadd > 0).mean(); d['L'] = T.L.median()
            rows.append(d)
    R = pd.DataFrame(rows); R.to_parquet('griglia.parquet')
    print(f'varianti provate: {len(R)}  ({len(V)} per base x {len(BASES)} basi)   tempo {time.time()-t0:.0f}s')
    print('Legenda: n/anno, R medio, sigma_R, q=Rm/sigma, vinc=quota vincenti, serie=max perdite consecutive, t / t_cl (a grappoli per giorno),')
    print('G = N*(Rm/sigma)^2 (per trade, ignora la simultaneita\'), S2 = Sharpe annuo^2 del flusso giornaliero di R (ne tiene conto).')
    print('_s = scelta (<=2022), _v = verifica (>=2023), c2 = costi x2, d1 = +1 barra di ritardo.\n')
    cols = ['fam', 'cfg', 'npy_s', 'R_s', 'sig_s', 'q_s', 'hit_s', 'streak_s', 'G_s', 'S2_s', 'npy_v', 'R_v', 'sig_v', 'q_v', 'hit_v', 'streak_v', 't_v', 't_cl_v',
            'G_v', 'S2_v', 'R_v_c2', 'q_v_c2', 'G_v_c2', 'S2_v_c2', 'R_v_d1', 'G_v_d1']
    for bn in BASES:
        X = R[R.base == bn]
        print(f'===== BASE {bn}: {BASES[bn]}  leva mediana {X.L.iloc[0]:.1f}x =====')
        print(X[cols].round(3).to_string(index=False)); print()
