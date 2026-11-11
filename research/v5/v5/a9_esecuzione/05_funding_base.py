"""A9/05 - FUNDING e BASE. (d) quanto costa tenere i long attraverso i regolamenti; funding alto all'ingresso = trade peggiori?;
Hyperliquid (orario) contro Binance (8h) sugli stessi trade; (e) base perp/spot all'ingresso; Hyperliquid contro Binance: code delle candele.
Perpetual Binance 5m, 2020-2026, ingresso taker alle 00:00. SIMULATO. Scelta 2020-2022, verifica 2023+."""
from lib import *
BASE = dict(A=dict(stop='atr', k=1.0, trail=2.0), C=dict(stop='fix', k=0.017, trail=None))
HL = {c: fund_hl(c) for c in COINS}; HL0 = np.datetime64('2023-05-12')
for nm, kw in BASE.items():
    T = run(perp=True, **kw); count('funding'); T = T[T.filled].copy()
    print(f'\n################ {nm}: {kw} ################')
    hrs = (T.t_out - T.t_in).dt.total_seconds() / 3600
    print(f"durata media {hrs.mean():.1f} ore (mediana {hrs.median():.1f}); funding pagato per trade: media {T.fund.mean()*1e4:.2f} pb = {(T.fund/T.s).mean():.4f} R; "
          f"commissioni+slippage {(T.fee/T.s).mean():.4f} R; R netto {T.R.mean():.3f} -> il funding e' il {(T.fund/T.s).mean()/((T.R+T.fund/T.s).mean()):.0%} dell'R ante-funding")
    print(f"  per periodo: scelta {(T.fund/T.s)[T.entry<CUT].mean():.4f} R, verifica {(T.fund/T.s)[T.entry>=CUT].mean():.4f} R; tasso medio annualizzato pagato durante i trade: {T.fund.sum()/hrs.sum()*8760:.1%} "
          f"(contro media incondizionata BTC {FBN['BTC'].r[FBN['BTC'].t>=np.datetime64('2020-01-01')].mean()*3*365:.1%})")
    # (d2) funding noto all'ingresso -> R
    T['f_last'] = [FBN[c].last(t) for c, t in zip(T.coin, T.t_in.values)]
    T['f_3'] = [FBN[c].c[np.searchsorted(FBN[c].t, t, 'right')] - FBN[c].c[max(np.searchsorted(FBN[c].t, t, 'right') - 3, 0)] for c, t in zip(T.coin, T.t_in.values)]
    print('\n--- R per livello dell\'ultimo funding regolato (noto all\'ingresso); soglie = quartili del periodo di scelta ---')
    q = T[T.entry < CUT].f_last.quantile([.25, .5, .75]).values; print('soglie (pb/8h):', (q * 1e4).round(2))
    T['fq'] = np.searchsorted(q, T.f_last.values, 'right')
    g = T.groupby('fq'); S = T[T.entry < CUT].groupby('fq'); V = T[T.entry >= CUT].groupby('fq')
    print(pd.DataFrame(dict(n=g.size(), f_medio_pb=g.f_last.mean() * 1e4, R=g.R.mean(), R_lordo_funding=g.apply(lambda x: (x.R + x.fund / x.s).mean()), fund_R=g.apply(lambda x: (x.fund / x.s).mean()),
                            n_sel=S.size(), R_sel=S.R.mean(), n_ver=V.size(), R_ver=V.R.mean())).round(3).to_string())
    print('corr(funding ultimo, R): scelta %+.3f verifica %+.3f | corr(funding ultimi 3, R): scelta %+.3f verifica %+.3f' % (
        T[T.entry < CUT][['f_last', 'R']].corr().iloc[0, 1], T[T.entry >= CUT][['f_last', 'R']].corr().iloc[0, 1], T[T.entry < CUT][['f_3', 'R']].corr().iloc[0, 1], T[T.entry >= CUT][['f_3', 'R']].corr().iloc[0, 1]))
    print('\n--- Filtro: niente ingresso se l\'ultimo funding supera la soglia (si riprova il giorno dopo) ---')
    rows = [stats(T, f'{nm} base')]
    for thr in (0.0001, 0.0002, 0.0003, 0.0005, 0.001):
        X = run(perp=True, skip_fn=lambda c, i, t, pe, sd, thr=thr: FBN[c].last(t) > thr, **kw); count('funding'); rows.append(stats(X, f'{nm} salta se funding > {thr*1e4:.0f} pb/8h'))
    show(rows, SHORT)
    # (d3) entrare subito dopo o subito prima di un regolamento
    print('\n--- Ora d\'ingresso e regolamenti: funding pagato (pb) entrando all\'ora h (dai trade di 03: qui solo il conto del funding) ---')
    for h in (0, 1, 4, 7, 8):
        X = run(perp=True, hour=h, **kw); X = X[X.filled]; print(f"  h={h:02d}: funding medio {X.fund.mean()*1e4:.2f} pb = {(X.fund/X.s).mean():.4f} R; regolamenti attraversati per trade {((X.t_out-X.t_in).dt.total_seconds()/28800).mean():.2f} (stima)")
    print(f"  valore di un regolamento evitato: {T.f_last.mean()*1e4:.2f} pb = {(T.f_last/T.s).mean():.4f} R per trade")
    # (d4) Hyperliquid contro Binance sugli stessi trade (dal 2023-05-12)
    X = T[T.entry >= HL0].copy()
    X['fund_hl'] = [HL[c].paid(a, b) for c, a, b in zip(X.coin, X.t_in.values, X.t_out.values)]
    X['hl_last8'] = [HL[c].c[np.searchsorted(HL[c].t, a, 'right')] - HL[c].c[max(np.searchsorted(HL[c].t, a, 'right') - 8, 0)] for c, a in zip(X.coin, X.t_in.values)]
    X['pick_hl'] = X.hl_last8 < X.f_last; X['fund_pick'] = np.where(X.pick_hl, X.fund_hl, X.fund)
    print(f"\n--- Sede piu' conveniente per il funding, {len(X)} trade dal 2023-05-12 ---")
    print(f"  Binance 8h: {X.fund.mean()*1e4:.2f} pb = {(X.fund/X.s).mean():.4f} R | Hyperliquid oraria: {X.fund_hl.mean()*1e4:.2f} pb = {(X.fund_hl/X.s).mean():.4f} R | "
          f"sceglie la sede col funding recente piu' basso (HL ultime 8 ore contro ultimo Binance): {X.fund_pick.mean()*1e4:.2f} pb = {(X.fund_pick/X.s).mean():.4f} R (HL scelta nel {X.pick_hl.mean():.0%} dei casi)")
    print(f"  R medio: su Binance {X.R.mean():.4f}; con funding Hyperliquid {(X.R + (X.fund - X.fund_hl)/X.s).mean():.4f}; con sede scelta {(X.R + (X.fund - X.fund_pick)/X.s).mean():.4f}   (differenza HL-Binance: {((X.fund - X.fund_hl)/X.s).mean():+.4f} R, t {((X.fund - X.fund_hl)/X.s).mean()/((X.fund - X.fund_hl)/X.s).std()*np.sqrt(len(X)):+.2f})")
    for yy in (2023, 2024, 2025, 2026):
        Y = X[pd.DatetimeIndex(X.entry).year == yy]; print(f"    {yy}: n={len(Y)} Binance {(Y.fund/Y.s).mean():.4f} R, HL {(Y.fund_hl/Y.s).mean():.4f} R")
    # (e) base all'ingresso
    T['basis'] = [PERP(c).op[np.searchsorted(PERP(c).ts, t)] / SPOT[c].op[np.searchsorted(SPOT[c].ts, t)] - 1 for c, t in zip(T.coin, T.t_in.values)]
    T['basis_out'] = [PERP(c).op[min(np.searchsorted(PERP(c).ts, t), len(PERP(c).op) - 1)] / SPOT[c].op[min(np.searchsorted(SPOT[c].ts, t), len(SPOT[c].op) - 1)] - 1 for c, t in zip(T.coin, T.t_out.values)]
    print(f"\n--- (e) Base perp/spot all'ingresso: media {T.basis.mean()*1e4:+.2f} pb, mediana {T.basis.median()*1e4:+.2f}, 5-95 percentile {T.basis.quantile(.05)*1e4:+.1f}/{T.basis.quantile(.95)*1e4:+.1f} pb; "
          f"variazione ingresso->uscita {((T.basis_out-T.basis)).mean()*1e4:+.2f} pb = {((T.basis_out-T.basis)/T.s).mean():+.4f} R ---")
    q = T[T.entry < CUT].basis.quantile([1 / 3, 2 / 3]).values; T['bq'] = np.searchsorted(q, T.basis.values, 'right'); print('soglie dei terzili (scelta, pb):', (q * 1e4).round(2))
    g = T.groupby('bq'); S = T[T.entry < CUT].groupby('bq'); V = T[T.entry >= CUT].groupby('bq')
    print(pd.DataFrame(dict(n=g.size(), base_pb=g.basis.mean() * 1e4, R=g.R.mean(), n_sel=S.size(), R_sel=S.R.mean(), n_ver=V.size(), R_ver=V.R.mean())).round(3).to_string())
    print('corr(base, R): scelta %+.3f verifica %+.3f' % (T[T.entry < CUT][['basis', 'R']].corr().iloc[0, 1], T[T.entry >= CUT][['basis', 'R']].corr().iloc[0, 1]))
    rows = [stats(T, f'{nm} base')]
    for thr in (5, 10):
        def sk(c, i, t, pe, sd, thr=thr): return pe / SPOT[c].op[np.searchsorted(SPOT[c].ts, t)] - 1 > thr * 1e-4
        X = run(perp=True, skip_fn=sk, **kw); count('base'); rows.append(stats(X, f'{nm} salta se base > {thr} pb'))
    show(rows, SHORT)
print('\n=== Hyperliquid contro Binance perp: candele orarie (cache v4_hl_1h, 2026-04 -> 2026-10). Il perp Binance e\' un buon sostituto? ===')
for c in COINS:
    h = st.get(f'v4_hl_1h_{c}'); b = st.get(f'v4_um_1h_{c}USDT'); m = h.join(b, lsuffix='_hl', rsuffix='_bn', how='inner')
    x = (m.low_hl / m.low_bn - 1) * 1e4; o = (m.open_hl / m.open_bn - 1) * 1e4; r = (m.high_hl - m.low_hl) / (m.high_bn - m.low_bn) - 1
    print(f"{c}: {len(m)} ore; apertura HL-Binance media {o.mean():+.2f} pb (dev.std {o.std():.1f}); minimo orario HL-Binance media {x.mean():+.2f} pb, 1o percentile {x.quantile(.01):+.1f}, minimo {x.min():+.1f} pb; ampiezza HL/Binance-1 mediana {r.median():+.2%}")
save_trials('05'); print('prove:', TRIALS)
