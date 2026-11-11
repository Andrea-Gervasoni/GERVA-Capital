"""A10 - 05: controlli di troncamento, costi doppi / ritardo sulle correzioni, tabella finale dei profili e returns.parquet. SIMULATO."""
from common import *
M = pd.read_parquet(HERE + '/_mtm.parquet'); adj = B['adj']; bil = adj['BIL'].pct_change(fill_method=None).reindex(IDX).fillna(0.0)
cu = cash_used(); idle = 1 - cu
def park(idle, buffer=0.05, band=0.05, fee=0.001, lag=1):
    tgt = (idle - buffer).clip(lower=0.0).shift(lag).fillna(0.0).values; y = bil.values; w = 0.0; out = np.zeros(len(tgt))
    for t in range(len(tgt)):
        out[t] = w * y[t]
        if abs(tgt[t] - w) > band or (tgt[t] == 0 and w > 0): out[t] -= abs(tgt[t] - w) * fee; w = tgt[t]
    return pd.Series(out, index=idle.index)
print('== 1. Controllo di troncamento (il segnale ricalcolato sui dati tagliati a t deve essere identico)')
rng = np.random.default_rng(1); bad = 0
for t in rng.choice(np.arange(400, len(IDX) - 1), 25, replace=False):
    d = IDX[t]; S5t = S5.loc[:d]; a_t = with_carry(risk_parity(S5t)).iloc[-1]; bad += int((a_t - A6.loc[d]).abs().max() > 1e-12)
    L_full = vol_target_leverage(NEW, 0.15, 60, 2.0).loc[d]; L_t = vol_target_leverage(NEW.loc[:d], 0.15, 60, 2.0).iloc[-1]; bad += int(abs(L_full - L_t) > 1e-12)
    tgt_full = (idle - 0.05).clip(lower=0).shift(1).loc[d]; cu_t = (A6.loc[:d] * G6.loc[:d] * CASHUSE).sum(axis=1); tgt_t = (1 - cu_t - 0.05).clip(lower=0).shift(1).iloc[-1]; bad += int(abs(tgt_full - tgt_t) > 1e-12)
print('   pesi di parita\' di rischio, leva a volatilita\' obiettivo, quota parcheggiata: 25 date a caso x 3 segnali, differenze:', bad)
print('   NB: l\'esposizione degli sleeve (G6) usa DIP = 0,07 costante (media dell\'intero periodo, dal .out della ricerca v4): e\' l\'unica grandezza non puntuale; pesa 0,6% del capitale.')
print('\n== 2. Robustezza delle due correzioni di conto')
line('B pubblicato', NEW); line('B + T-bill (10 pb, ritardo 1)', NEW + park(idle)); line('B + T-bill costi x2 (20 pb)', NEW + park(idle, fee=0.002)); line('B + T-bill ritardo +1 giorno', NEW + park(idle, lag=2)); line('B + T-bill, cuscinetto 20% (cassa ferma sulle sedi crypto)', NEW + park(idle, buffer=0.20))
for sp in (0.015, 0.03, 0.06):
    for L in (2, 3):
        c = cash_used(lev=L); x = L * NEW - np.maximum(c - 1, 0) * (rf + sp / 365); line(f'B {L}x debito reale, spread {sp:.1%}', x)
    # caso prudente: la cassa delle sedi crypto e perp non e' trasferibile -> il debito si calcola solo sulla parte IBKR
ib = (A6 * G6 * CASHUSE)[['MA-TREND', 'EQ-MR']].sum(axis=1); ibcap = A6[['MA-TREND', 'EQ-MR']].sum(axis=1)
for L in (2, 3):
    debt = np.maximum(L * ib - ibcap, 0) + np.maximum(L * (A6 * G6 * CASHUSE)[['CR-TREND', 'CR-XSMOM', 'DIP', 'CARRY']].sum(axis=1) - A6[['CR-TREND', 'CR-XSMOM', 'DIP', 'CARRY']].sum(axis=1), 0)
    line(f'B {L}x debito per sede (nessun trasferimento tra sedi), rf+1,5%', L * NEW - debt * (rf + 0.015 / 365), extra=f'| debito medio {debt.mean():.2f}')
print('\n== 3. Profili: pubblicato -> corretto (statistiche MENSILI; DD giornaliero a mercato)')
F = pd.read_parquet(ROOT + '/research/v5/v4/fondo_serie.parquet')
def row(lab, x):
    t = three(x, monthly=True); m = mm(x); print(f"{lab[:74]:74s} Sh {t['sh_tot']:5.2f} | {t['sh_sel']:5.2f} | {t['sh_ver']:5.2f}  CAGR {100*t['cagr_tot']:5.1f}% {100*t['cagr_sel']:5.1f}% {100*t['cagr_ver']:5.1f}%  DD giorn {100*t['dd_tot']:6.1f}%  mese medio {100*m.mean():4.1f}% mediano {100*m.median():4.1f}% peggiore {100*m.min():6.1f}%")
row('B. 6 strategie 1x (pubblicato)', NEW); row('B + cassa libera in T-bill', NEW + park(idle))
row('B2. 6 strategie 2x (pubblicato)', F['new2x']); row('B2 con debito reale', M['B2_debito_reale']); row('B2 con il motore di rischio attuale', M['B2_motore_di_rischio_attuale'])
row('C1 pubblicato (uscita)', NEW + trade_book(.005, .01, mtm=False)[0]); row('C1 a mercato + limiti live', M['C1_mtm_limiti']); row('C1 con il motore di rischio attuale', M['C1_motore_di_rischio_attuale'])
row('C3. 2x + trade (pubblicato: P&L sul giorno di uscita)', F['C3']); row('C3 a mercato + limiti del libro live', M['C3_mtm_limiti']); row('C3 a mercato + limiti + debito reale', M['C3_mtm_limiti_debito_reale']); row('C3 con il motore di rischio attuale (config/gerva.yaml)', M['C3_motore_di_rischio_attuale'])
out = pd.DataFrame({'B_pubblicato': NEW, 'B_cassa_in_tbill': NEW + park(idle)}).join(M.drop(columns=['B_pubblicato']))
out.to_parquet(HERE + '/returns.parquet'); print('\nreturns.parquet:', out.shape, list(out.columns))
print('rischio per trade delle serie con il libro dei trade: 1% (confermato) / 2% (eccezionale), stop 1 x ATR, leva ~11x; C1: 0,5% / 1%.')
