"""A10 - 01: controlli di coerenza, cassa inutilizzata, uso doppio del capitale. SIMULATO."""
from common import *
print('controllo: NEW ricostruito = portafogli.parquet?  diff max', float((NEW - P['3. 4 sleeve + DIP-24h + CARRY 20%']).abs().max()))
F = pd.read_parquet(ROOT + '/research/v5/v4/fondo_serie.parquet')
T0, mg, no, rk = trade_book(mtm=False); print('controllo: libro trade (uscita) = fondo_serie.trade11?  diff max', float((T0 - F['trade11']).abs().max()))
print('\n== 1. Dove sta il capitale (media, quota del patrimonio), portafoglio a 6 strategie 1x')
inv = (A6 * G6); print('quota di capitale ASSEGNATA (media):'); print(A6.mean().round(3).to_string())
print('esposizione lorda (assegnata x esposizione dello sleeve):'); print(inv.mean().round(3).to_string())
cu = cash_used()
for lab, sl in (('tot', slice(None, None)), ('scelta', slice(None, SEL_END)), ('verifica', slice(SPL, None))):
    print(f'  {lab:9s} cassa impegnata {cu.loc[sl].mean():.3f}  ->  cassa LIBERA media {1 - cu.loc[sl].mean():.3f}  (min {1 - cu.loc[sl].max():.3f}, 5° pct {(1 - cu.loc[sl]).quantile(.05):.3f});  rf medio {rf.loc[sl].mean() * 365:.3%}')
print('  cassa libera per sede (media): IBKR (MA-TREND+EQ-MR) %.3f su %.3f assegnato; crypto spot (CR-TREND+CR-XSMOM) %.3f su %.3f; perp (DIP) %.3f su %.3f' % (
    (A6[['MA-TREND', 'EQ-MR']].sum(axis=1) - (A6 * G6 * CASHUSE)[['MA-TREND', 'EQ-MR']].sum(axis=1)).mean(), A6[['MA-TREND', 'EQ-MR']].sum(axis=1).mean(),
    (A6[['CR-TREND', 'CR-XSMOM']].sum(axis=1) - (A6 * G6)[['CR-TREND', 'CR-XSMOM']].sum(axis=1)).mean(), A6[['CR-TREND', 'CR-XSMOM']].sum(axis=1).mean(),
    (A6['DIP'] - (A6 * G6 * CASHUSE)['DIP']).mean(), A6['DIP'].mean()))
print('\n== 2. Uso doppio del capitale: cassa impegnata dal libro giornaliero + margine del libro dei trade')
for L in (1, 2, 3):
    for nm, (rc, re) in (('0,5/1%', (.005, .01)), ('1/2%', (.01, .02)), ('1,5/3%', (.015, .03))):
        _, mg, no, rk = trade_book(rc, re); _, mg10, _, _ = trade_book(rc, re, lev_cap=10)
        tot = cash_used(lev=L) + mg; tot10 = cash_used(lev=L) + mg10
        print(f'  libro {L}x + trade {nm}: cassa richiesta media {tot.mean():.2f} max {tot.max():.2f}; giorni oltre il 100% {100 * (tot > 1).mean():.1f}%; debito medio {np.maximum(tot - 1, 0).mean():.3f} | con leva sede 10x: margine max {mg10.max():.3f}, giorni oltre 100% {100 * (tot10 > 1).mean():.1f}% | margine max {mg.max():.3f} (limite live 0,15), controvalore max {no.max():.2f} (limite 1,5), rischio aperto max {rk.max():.3f} (limite 0,06)')
print('\n== 3. Costo del finanziamento: quello di 09_fondo.py [ (L-1) x (rf+1,5%) su TUTTO il capitale ] contro il debito realmente necessario')
for L in (2, 3):
    cu = cash_used(lev=L); debt = np.maximum(cu - 1, 0); idle = np.maximum(1 - cu, 0)
    ass = ((L - 1) * (rf + 0.015 / 365)).mean() * 365; real = (debt * (rf + 0.015 / 365)).mean() * 365
    print(f'  {L}x: cassa impegnata media {cu.mean():.2f}; debito medio {debt.mean():.3f}; cassa ancora libera {idle.mean():.3f};  costo addebitato {ass:.3%}/anno, costo del debito reale {real:.3%}/anno  -> sottostima del CAGR ~ {ass - real:.3%}/anno')
    x = L * NEW - debt * (rf + 0.015 / 365)
    line(f'  6 strategie {L}x come 09_fondo', lev09(NEW, L)); line(f'  6 strategie {L}x con il debito reale', x)
print("  NB: EQ-MR paga gia' (rf+1,5%) sul controvalore dentro il suo rendimento; a leva L lo paga L volte (giusto) PIU' la quota di (L-1)(rf+1,5%): doppio addebito.")
