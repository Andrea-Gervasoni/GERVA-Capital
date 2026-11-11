"""A9/02 - Ingressi MAKER sui perpetual (Binance USDT-M 5m e 1m, 2020-2026). Commissioni Hyperliquid: maker 1,5 pb, taker 4,5 pb.
Limite a open*(1-x pb) valido W barre; eseguito solo se il prezzo scende SOTTO il limite (attraversamento, non semplice tocco).
Domanda chiave: i trade NON eseguiti sono i vincenti (selezione avversa)? SIMULATO. Scelta = 2020-2022, verifica = 2023+."""
from lib import *
BASE = dict(A=dict(stop='atr', k=1.0, trail=2.0), C=dict(stop='fix', k=0.017, trail=None))
XS = (0, 1, 2, 5, 10, 25, 50); WS = ((1, '5m'), (3, '15m'), (12, '1h'), (48, '4h'), (288, '24h'))
for nm, kw in BASE.items():
    T0 = run(perp=True, **kw); count('maker_base'); b0 = stats(T0, f'{nm} taker (base perp)')
    print(f'\n################ {nm}: {kw} ################'); show([b0], SHORT)
    print('\n--- Selezione avversa: sugli STESSI trade del libro taker, R (taker) dei trade il cui limite sarebbe stato eseguito / non eseguito ---')
    rows = []
    for c in COINS:
        b = PERP(c); T0.loc[T0.coin == c, 'k0'] = np.searchsorted(b.ts, T0[T0.coin == c].t_in.values)
    for x in XS:
        for w, wl in WS:
            f = np.zeros(len(T0), bool)
            for q, (c, k0, ref) in enumerate(zip(T0.coin, T0.k0.astype(int), T0.ref)):
                f[q] = PERP(c).lo[k0:k0 + w].min() < ref * (1 - x * 1e-4)
            a, u = T0[f], T0[~f]; sel = T0.entry < CUT
            rows.append(dict(x_pb=x, W=wl, fill=f.mean(), fill_sel=f[sel].mean(), fill_ver=f[~sel].mean(), R_eseguiti=a.R.mean(), R_non_eseg=u.R.mean() if len(u) else np.nan,
                             Rsel_eseg=a[a.entry < CUT].R.mean(), Rsel_non=u[u.entry < CUT].R.mean() if len(u) else np.nan, Rver_eseg=a[a.entry >= CUT].R.mean(), Rver_non=u[u.entry >= CUT].R.mean() if len(u) else np.nan,
                             R_persi_tot=u.R.sum(), quota_R_persa=u.R.sum() / T0.R.sum()))
    show(rows)
    print('\n--- Simulazione completa: limite, poi (a) si salta il trade, (b) si rincorre a mercato dopo la finestra ---')
    rows = [b0]
    for fb in ('skip', 'taker'):
        for x in XS:
            for w, wl in WS:
                if fb == 'taker' and w == 288: continue
                T = run(perp=True, entry='maker', lim_bp=x, win=w, fallback=fb, **kw); count('maker')
                r = stats(T, f'{nm} lim -{x}pb W={wl} poi {fb}'); r['fill'] = (T[T.filled]['mode'] == 'maker').mean() if fb == 'taker' else T.filled.mean(); rows.append(r)
    R = show(rows, SHORT + ['fill'])
    R['dK_sel'] = R.K_sel - b0['K_sel']; R['dR_sel'] = R.R_sel - b0['R_sel']
    best = R.iloc[1:].sort_values('K_sel', ascending=False).head(8)
    print('\nMigliori per K_sel = N*(R/sd)^2 in SCELTA (parametri scelti solo li\'):'); show(best.to_dict('records'), SHORT + ['fill', 'dK_sel'])
    print(f"Quante delle {len(R)-1} varianti maker battono il taker: in scelta su R {(R.R_sel.iloc[1:] > b0['R_sel']).sum()}, su K {(R.K_sel.iloc[1:] > b0['K_sel']).sum()}; "
          f"in verifica su R {(R.R_ver.iloc[1:] > b0['R_ver']).sum()}, su K {(R.K_ver.iloc[1:] > b0['K_ver']).sum()}; in entrambe su K {((R.K_sel.iloc[1:] > b0['K_sel']) & (R.K_ver.iloc[1:] > b0['K_ver'])).sum()}")
    print('\n--- Uscite a tempo con limite (maker 1,5 pb, 15 minuti, poi taker) + sensibilita\' al criterio di esecuzione ---')
    rows = [b0]
    T = run(perp=True, exit_maker=True, **kw); count('maker'); rows.append(stats(T, f'{nm} taker in, uscita a tempo maker'))
    for x, w in ((0, 3), (0, 12), (2, 12)):
        for thru in (0, 1, 3):
            T = run(perp=True, entry='maker', lim_bp=x, win=w, fallback='taker', thru_bp=thru, **kw); count('maker')
            r = stats(T, f'{nm} lim -{x}pb W={w} barre poi taker, attraversamento {thru}pb'); r['fill'] = (T[T.filled]['mode'] == 'maker').mean(); rows.append(r)
    show(rows, SHORT + ['fill'])
    print('\n--- Controllo sulle barre a 1 MINUTO (stesso libro, percorso piu\' fine): taker e limite con finestre di 1-15 minuti ---')
    rows = []
    T = run(perp=True, m1=True, **kw); count('maker_1m'); rows.append(stats(T, f'{nm} taker, percorso 1m'))
    for x in (0, 1, 2):
        for w in (1, 2, 5, 15, 60):
            T = run(perp=True, m1=True, entry='maker', lim_bp=x, win=w, fallback='taker', **kw); count('maker_1m')
            r = stats(T, f'{nm} 1m lim -{x}pb W={w}min poi taker'); r['fill'] = (T[T.filled]['mode'] == 'maker').mean(); rows.append(r)
    show(rows, SHORT + ['fill'])
save_trials('02'); print('prove:', TRIALS)
