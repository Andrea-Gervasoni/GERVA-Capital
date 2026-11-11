"""A9/06 - La combinazione difendibile e le prove di robustezza. SIMULATO. Perpetual Binance 5m (2020-2026): scelta 2020-2022, verifica 2023+.
Regola finale (solo esecuzione, segnale invariato):
  ingresso: alle 00:00 UTC limite al prezzo d'apertura (maker 1,5 pb), valido 15 minuti, eseguito solo se il prezzo scende sotto il limite;
            se non eseguito: ordine a mercato (taker 4,5 pb + 2 pb slippage) alla barra successiva;
  stop:     1 x ATR14 giornaliero sotto l'eseguito, trailing 2 x (A) / 1,7% fisso (C): stop a mercato (taker + 2 pb + 5 pb);
  uscita a tempo: limite all'apertura (maker), 15 minuti, poi mercato."""
from lib import *
BASE = dict(A=dict(stop='atr', k=1.0, trail=2.0), C=dict(stop='fix', k=0.017, trail=None))
MK = dict(entry='maker', lim_bp=0, win=3, fallback='taker', exit_maker=True)
HL0 = np.datetime64('2023-05-12'); OUT = {}
# controllo di troncamento del segnale: ricalcolato sui soli dati fino a t-1 deve coincidere
rng = np.random.default_rng(0); bad = 0; tot = 0
for c in COINS:
    d = SPOT[c].daily
    for i in rng.choice(np.arange(400, len(d) - 1), 40, replace=False):
        dd = d.iloc[:i]; F = E.crypto_signals(dd, SPOT['BTC'].daily['close'].reindex(dd.index), DFUND[c][DFUND[c].index < d.index[i]]); cv = E.conviction(F, 'crypto').iloc[-1]
        ref = CONV[c].iloc[i]; a = ((dd['high'] - dd['low']) / dd['close']).rolling(14).mean().iloc[-1]; tot += 1
        bad += not ((cv.tier == ref.tier) and (abs(cv.score - ref.score) < 1e-12 or (np.isnan(cv.score) and np.isnan(ref.score))) and abs(a - ATR[c].iloc[i]) < 1e-12)
print(f'Controllo di troncamento (segnale e ATR ricalcolati sui dati tagliati a t-1): {tot - bad}/{tot} identici')
for nm, kw in BASE.items():
    print(f'\n################ {nm}: {kw} ################')
    rows = []
    def add(lab, coins=COINS, key=None, **over):
        T = run(coins, perp=True, **{**kw, **over}); count('combinazione'); rows.append(stats(T, lab))
        if key: OUT[key] = T[T.filled].assign(libro=key)
        return T
    S = run(**kw); S = pd.concat([S[(S.coin == c) & (S.entry >= np.datetime64('2020-01-01' if c != 'SOL' else '2020-09-15'))] for c in COINS]); rows.append(stats(S, f'{nm}0 v4 su SPOT (2020+), taker'))
    T0 = add(f'{nm}1 PERP, taker (base onesta)', key=f'{nm}_base_perp')
    add(f'{nm}2 + ingresso maker 15m poi taker', entry='maker', lim_bp=0, win=3, fallback='taker')
    T1 = add(f'{nm}3 + uscita a tempo maker  [COMBINAZIONE]', key=f'{nm}_combinazione', **MK)
    add(f'{nm}3 costi x2', cost_mult=2.0, **MK); add(f'{nm}1 base costi x2', cost_mult=2.0)
    add(f'{nm}3 ritardo +1 barra', delay=1, **MK); add(f'{nm}1 base ritardo +1 barra', delay=1)
    add(f'{nm}3 attraversamento 1 pb', thru_bp=1, **MK); add(f'{nm}3 attraversamento 3 pb', thru_bp=3, **MK)
    add(f'{nm}3 commissioni UE (taker 5, maker 2 pb)', taker=0.0005, maker=0.0002, **MK)
    T = run(perp=True, m1=True, **{**kw, **dict(MK, win=15)}); count('combinazione'); rows.append(stats(T, f'{nm}3 sul percorso a 1 minuto'))
    add(f'{nm}3 solo BTC+ETH', coins=('BTC', 'ETH'), **MK)
    add(f'{nm}4 = 3 + salta se funding > 3 pb/8h (soglia scelta)', key=f'{nm}_comb_filtro_funding', skip_fn=lambda c, i, t, pe, sd: FBN[c].last(t) > 0.0003, **MK)
    add(f'{nm}5 = 3 + salta se base > 5 pb', skip_fn=lambda c, i, t, pe, sd: pe / SPOT[c].op[np.searchsorted(SPOT[c].ts, t)] - 1 > 5e-4, **MK)
    R = show(rows, ['cfg', 'n', 'N_anno', 'R', 'sdR', 't', 'hit', 'R_sel', 'sd_sel', 't_sel', 'N_sel', 'R_ver', 'sd_ver', 't_ver', 'N_ver', 'costo_R', 'fund_R', 'K_sel', 'K_ver'])
    b, m = rows[1], rows[3]
    print(f"\nEffetto netto della combinazione sul perp: scelta R {b['R_sel']:.3f}->{m['R_sel']:.3f} ({m['R_sel']-b['R_sel']:+.3f}), sd {b['sd_sel']:.2f}->{m['sd_sel']:.2f}, N/anno {b['N_sel']:.0f}->{m['N_sel']:.0f}, R/sd {b['R_sel']/b['sd_sel']:.3f}->{m['R_sel']/m['sd_sel']:.3f}, K {b['K_sel']:.2f}->{m['K_sel']:.2f}")
    print(f"                                          verifica R {b['R_ver']:.3f}->{m['R_ver']:.3f} ({m['R_ver']-b['R_ver']:+.3f}), sd {b['sd_ver']:.2f}->{m['sd_ver']:.2f}, N/anno {b['N_ver']:.0f}->{m['N_ver']:.0f}, R/sd {b['R_ver']/b['sd_ver']:.3f}->{m['R_ver']/m['sd_ver']:.3f}, K {b['K_ver']:.2f}->{m['K_ver']:.2f}")
    mm = T0[T0.filled].merge(T1[T1.filled], on=['coin', 'entry'], suffixes=('_0', '_1')); dlt = mm.R_1 - mm.R_0
    print(f"Stessi trade (n={len(mm)}): differenza di R media {dlt.mean():+.4f}, t appaiato {dlt.mean()/dlt.std()*np.sqrt(len(dlt)):+.2f}; scelta {dlt[mm.entry<CUT].mean():+.4f}, verifica {dlt[mm.entry>=CUT].mean():+.4f}; "
          f"risparmio di costo {(mm.fee_0/mm.s_0-mm.fee_1/mm.s_1).mean():+.4f} R; quota ingressi maker {(T1[T1.filled]['mode']=='maker').mean():.1%}")
    print('\nPer anno: base perp | combinazione'); print(per_year(T0).join(per_year(T1), lsuffix='_base', rsuffix='_comb').to_string())
    print('\nPer moneta (combinazione):'); show([stats(T1[T1.coin == c], c) for c in COINS], ['cfg', 'n', 'R', 'sdR', 't', 'R_sel', 'R_ver'])
    # funding Hyperliquid (dati dal 2023-05-12): stessi trade, cambia solo il funding
    X = T1[T1.filled & (T1.entry >= HL0)].copy(); H = {c: fund_hl(c) for c in COINS}
    X['fund_hl'] = [H[c].paid(a, b_) for c, a, b_ in zip(X.coin, X.t_in.values, X.t_out.values)]; X['R_hl'] = np.maximum(X.ret + X.fund - X.fund_hl, -1 / X.L) / X.s
    Y = T0[T0.filled & (T0.entry >= HL0)]; yrs = (X.entry.max() - X.entry.min()).days / 365.25
    print(f"\nSu HYPERLIQUID (commissioni HL, funding orario HL reale, {len(X)} trade dal 2023-05-12, solo verifica): R medio {X.R_hl.mean():.3f} (sd {X.R_hl.std():.2f}, t {X.R_hl.mean()/X.R_hl.std()*np.sqrt(len(X)):.2f}, N/anno {len(X)/yrs:.0f}, K {len(X)/yrs*(X.R_hl.mean()/X.R_hl.std())**2:.2f}) "
          f"contro {X.R.mean():.3f} con funding Binance e {Y.R.mean():.3f} della base taker con funding Binance")
    X['libro'] = f'{nm}_combinazione_HL'; OUT[f'{nm}_combinazione_HL'] = X.drop(columns=['R']).rename(columns={'R_hl': 'R'})
    for thr in (0.0001, 0.0003):
        Z = run(perp=True, skip_fn=lambda c, i, t, pe, sd, thr=thr: (H[c].c[np.searchsorted(H[c].t, t, 'right')] - H[c].c[max(np.searchsorted(H[c].t, t, 'right') - 8, 0)]) > thr, **{**kw, **MK}); count('combinazione')
        Z = Z[Z.filled & (Z.entry >= HL0)].copy(); Z['fund_hl'] = [H[c].paid(a, b_) for c, a, b_ in zip(Z.coin, Z.t_in.values, Z.t_out.values)]; Z['R_hl'] = np.maximum(Z.ret + Z.fund - Z.fund_hl, -1 / Z.L) / Z.s
        print(f"   esplorativo (solo verifica, NON scelto prima): salta se funding HL delle ultime 8 ore > {thr*1e4:.0f} pb -> n={len(Z)} R {Z.R_hl.mean():.3f} sd {Z.R_hl.std():.2f} K {len(Z)/yrs*(Z.R_hl.mean()/Z.R_hl.std())**2:.2f}")
ALLT = pd.concat(OUT.values(), ignore_index=True)
keep = ['libro', 'coin', 'entry', 't_in', 't_out', 'exit', 'side', 'mode', 'pe', 'px', 's', 'L', 'R', 'ret', 'fee', 'fund', 'why', 'score']
ALLT[keep].rename(columns={'coin': 'symbol', 's': 'stop_distance', 'L': 'leverage'}).to_parquet(os.path.join(HERE, 'trades.parquet'))
# rendimenti giornalieri netti all'1% di rischio per trade (R x 1% contabilizzato nel giorno d'uscita)
idx = pd.date_range('2020-01-01', '2026-10-31', freq='D'); RET = pd.DataFrame(index=idx)
for k_, T in OUT.items(): RET[k_] = (T.groupby(pd.DatetimeIndex(T['exit']).normalize()).R.sum() * 0.01).reindex(idx).fillna(0.0)
RET.to_parquet(os.path.join(HERE, 'returns.parquet'))
print('\nrendimenti giornalieri all\'1% di rischio per trade (somma, non composto): media annua e Sharpe annuo')
print(pd.DataFrame(dict(media_annua=RET.mean() * 365, sharpe=RET.mean() / RET.std() * np.sqrt(365), sharpe_ver=RET[RET.index >= '2023-01-01'].mean() / RET[RET.index >= '2023-01-01'].std() * np.sqrt(365))).round(3).to_string())
save_trials('06'); print('prove:', TRIALS)
