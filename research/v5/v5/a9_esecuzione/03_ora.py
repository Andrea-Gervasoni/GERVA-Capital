"""A9/03 - ORA d'ingresso. Il segnale e' noto alle 00:00 UTC; si entra (taker) all'ora h dello stesso giorno, l'uscita a tempo resta
alle 00:00. Poi: ingresso solo alla rottura del massimo della prima ora / delle prime 4 ore (buy-stop), stop ATR o sotto il minimo
dell'intervallo. Perpetual Binance 5m, 2020-2026. SIMULATO. Scelta 2020-2022, verifica 2023+."""
from lib import *
BASE = dict(A=dict(stop='atr', k=1.0, trail=2.0), C=dict(stop='fix', k=0.017, trail=None))
COLS = ['cfg', 'n', 'N_anno', 'R', 'sdR', 't', 'hit', 'R_sel', 't_sel', 'R_ver', 't_ver', 'K_sel', 'K_ver', 'stop_pct']
for nm, kw in BASE.items():
    print(f'\n################ {nm}: {kw} ################\n--- ingresso all\'ora h UTC ---')
    rows = []
    for h in range(24):
        T = run(perp=True, hour=h, **kw); count('ora'); rows.append(stats(T, f'{nm} h={h:02d}'))
    R = show(rows, COLS)
    print(f"correlazione tra ore di R_sel e R_ver: {np.corrcoef(R.R_sel, R.R_ver)[0,1]:+.2f}; rango di h=00 su 24: per R_sel {int((R.R_sel > R.R_sel[0]).sum())+1}, per R_ver {int((R.R_ver > R.R_ver[0]).sum())+1}, "
          f"per K_sel {int((R.K_sel > R.K_sel[0]).sum())+1}, per K_ver {int((R.K_ver > R.K_ver[0]).sum())+1}")
    b = R.K_sel.idxmax(); print(f"ora migliore in scelta (K): h={b:02d} -> R_ver {R.R_ver[b]:.3f} K_ver {R.K_ver[b]:.2f} contro h=00 R_ver {R.R_ver[0]:.3f} K_ver {R.K_ver[0]:.2f}")
    print(f"media su tutte le ore: R_sel {R.R_sel.mean():.3f} R_ver {R.R_ver.mean():.3f}; blocchi: 00-07 R_sel {R.R_sel[:8].mean():.3f} R_ver {R.R_ver[:8].mean():.3f} | 08-15 {R.R_sel[8:16].mean():.3f} {R.R_ver[8:16].mean():.3f} | 16-23 {R.R_sel[16:].mean():.3f} {R.R_ver[16:].mean():.3f}")
    print('\n--- ingresso e uscita a tempo spostati insieme all\'ora h (stessa durata) ---')
    rows = []
    for h in (0, 4, 8, 12, 14, 16, 20):
        T = run(perp=True, hour=h, exit_hour=h, **kw); count('ora'); rows.append(stats(T, f'{nm} in/out h={h:02d}'))
    show(rows, COLS)
    print('\n--- rottura del massimo iniziale (buy-stop valido fino a fine giornata) ---')
    rows = [stats(run(perp=True, **kw), f'{nm} base h=00')]
    for w, wl in ((12, '1h'), (48, '4h'), (96, '8h')):
        T = run(perp=True, entry='breakout', win=w, **kw); count('rottura'); r = stats(T, f'{nm} rottura max {wl}, stop come base'); r['fill'] = T.filled.mean(); rows.append(r)
        T = run(perp=True, entry='breakout', win=w, stop='brk', trail=kw['trail']); count('rottura'); r = stats(T, f'{nm} rottura max {wl}, stop sotto il minimo {wl}'); r['fill'] = T.filled.mean(); rows.append(r)
    show(rows, COLS + ['s_med', 'fill'])
save_trials('03'); print('prove:', TRIALS)
