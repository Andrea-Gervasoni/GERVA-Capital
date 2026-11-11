"""Famiglia 7 - altro: flussi on-chain (offerta di stablecoin, flussi netti verso gli exchange, MVRV, indirizzi attivi),
sentiment (Fear & Greed), ora del giorno con commissioni maker, effetto nuove quotazioni dei perpetual, carry trasversale
perp-contro-perp su tutti i perpetual Binance. Dati REALI: DefiLlama, Coinmetrics community, alternative.me, Binance.
I dati on-chain sono rivisti dopo la pubblicazione (stato 'flash'): uso 2 giorni di ritardo, ma il rischio di look-ahead da
revisione NON e' eliminabile con questi file. Tutti i numeri sono SIMULATI."""
from lab import *
F = Fam('altro')
days = pd.date_range('2018-01-01', '2026-10-31')
px = pd.DataFrame({c: get(f'bn_spot_1d_{c}USDT')['close'] for c in ('BTC', 'ETH')}).reindex(days); ret = px.pct_change(fill_method=None)
bh = ret.mean(axis=1)
def timing(sig, fee=0.003, lag=1, w=1.0):
    """sig: serie 0..1 nota alla chiusura del giorno; 50% BTC + 50% ETH spot."""
    p = (sig.reindex(days).ffill().fillna(0.0) * w); return p.shift(lag).fillna(0.0) * bh - p.shift(lag - 1).diff().abs().fillna(0.0) * fee
F.line('riferimento: 50% BTC + 50% ETH comprati e tenuti', bh)
print('\n== 7a. Offerta di stablecoin (DefiLlama, totale agganciato al dollaro), ritardo 2 giorni')
stb = get('v4_stable')['stable'].reindex(days).ffill().shift(2)
for k in (7, 30, 90):
    g = stb / stb.shift(k) - 1
    F.line(f'long se crescita stablecoin a {k}g > 0', timing((g > 0).astype(float)))
    F.line(f'long se crescita stablecoin a {k}g > mediana a 1 anno', timing((g > g.rolling(365, min_periods=180).median()).astype(float)))
g30 = stb / stb.shift(30) - 1; s_st = (g30 > 0).astype(float); r_st = timing(s_st)
F.line('   crescita 30g > 0: costi x2', timing(s_st, fee=0.006)); F.line('   crescita 30g > 0: ritardo +1 giorno', timing(s_st, lag=2)); F.line('   crescita 30g > 0: ritardo +5 giorni', timing(s_st, lag=6))
F.keep('STABLE-30 (BTC+ETH se offerta stablecoin cresce)', r_st)
ct = S0['CR-TREND']; inpos = (ct != 0)
print('   giorni in cui STABLE-30 e CR-TREND sono entrambi investiti / solo uno:', {'entrambi': int(((s_st.shift(1) > 0) & inpos.reindex(days)).sum()), 'solo stable': int(((s_st.shift(1) > 0) & ~inpos.reindex(days)).sum()), 'solo trend': int(((s_st.shift(1) == 0) & inpos.reindex(days)).sum())})

print('\n== 7b. Flussi verso gli exchange, MVRV, indirizzi attivi (Coinmetrics community), ritardo 2 giorni')
for a, c in (('btc', 'BTC'), ('eth', 'ETH')):
    cm = get(f'v4_cm_{a}').reindex(days).shift(2); r1 = ret[c]
    def t1(sig, fee=0.003, lag=1): p = sig.reindex(days).ffill().fillna(0.0); return p.shift(lag).fillna(0.0) * r1 - p.shift(lag - 1).diff().abs().fillna(0.0) * fee
    F.line(f'{c} comprato e tenuto', r1)
    nf = (cm['FlowInExUSD'] - cm['FlowOutExUSD']); 
    for k in (7, 30):
        z = nf.rolling(k).sum() / cm['CapMrktCurUSD']
        F.line(f'{c} long se flusso netto verso exchange a {k}g < 0 (deflussi)', t1((z < 0).astype(float)))
        F.line(f'{c} long se flusso netto a {k}g < mediana 1 anno', t1((z < z.rolling(365, min_periods=180).median()).astype(float)))
    sx = cm['SplyExNtv']; F.line(f'{c} long se monete sugli exchange in calo a 30g', t1((sx < sx.shift(30)).astype(float)))
    mv = cm['CapMVRVCur']; F.line(f'{c} long se MVRV < mediana a 2 anni', t1((mv < mv.rolling(730, min_periods=365).median()).astype(float)))
    F.line(f'{c} long se MVRV in salita a 30g (momentum)', t1((mv > mv.shift(30)).astype(float)))
    aa = cm['AdrActCnt'].rolling(7).mean(); F.line(f'{c} long se indirizzi attivi (media 7g) in crescita a 30g', t1((aa > aa.shift(30)).astype(float)))

print('\n== 7c. Fear & Greed (alternative.me), noto il giorno stesso; ritardo 1 giorno')
fg = get('v4_fng')['fng'].reindex(days).ffill().shift(1)
def hyst(x, lo, hi):   # entra sotto lo, esce sopra hi
    s = pd.Series(np.nan, index=x.index); s[x < lo] = 1.0; s[x > hi] = 0.0; return s.ffill().fillna(0.0)
F.line('contrarian: compra con paura < 25, vende con avidita\' > 75', timing(hyst(fg, 25, 75)))
F.line('contrarian: compra < 20, vende > 50', timing(hyst(fg, 20, 50)))
F.line('contrarian: long solo nei giorni con indice < 25', timing((fg < 25).astype(float)))
F.line('momentum: long se indice > 50', timing((fg > 50).astype(float)))
F.line('momentum: long se indice > media a 30g', timing((fg > fg.rolling(30).mean()).astype(float)))
F.line('momentum: long se indice in salita a 7g', timing((fg > fg.shift(7)).astype(float)))
F.line('fuori solo con avidita\' estrema > 80', timing((fg <= 80).astype(float)))
s_fg = (fg > fg.rolling(30).mean()).astype(float); r_fg = timing(s_fg)
F.line('   F&G > media 30g: costi x2', timing(s_fg, fee=0.006)); F.line('   F&G > media 30g: ritardo +1', timing(s_fg, lag=2))
F.keep('FNG-MOM (BTC+ETH se F&G > media 30g)', r_fg)

print('\n== 7d. Ora del giorno 21-23 UTC con commissioni maker (IPOTESI: ordini passivi sempre eseguiti, senza selezione avversa)')
for c3 in (['BTC', 'ETH', 'SOL'],):
    tot = []
    for c in c3:
        cl = get(f'v4_um_1h_{c}USDT')['close']; r = cl.pct_change(); p = pd.Series(np.isin((cl.index.hour + 1) % 24, (21, 22)).astype(float), index=cl.index)
        for fee in (0.00015, 0.0007): tot.append((fee, daily(p.shift(1) * r - p.diff().abs() * fee)))
    for fee in (0.00015, 0.0007): F.line(f'long 21-23 UTC BTC/ETH/SOL perp, {fee * 1e4:.1f} pb/lato', pd.concat([x for f_, x in tot if f_ == fee], axis=1).mean(axis=1))
    rr = pd.concat([x for f_, x in tot if f_ == 0.00015], axis=1).mean(axis=1); F.keep('ORE 21-23 UTC (maker 1,5 pb: IPOTESI)', rr)

if has('v4_allperp_close'):
    C = get('v4_allperp_close'); V = get('v4_allperp_qvol'); Fd = get('v4_allperp_fund')
    C = C.loc[:'2026-10-31']; V = V.reindex(C.index); Fd = Fd.reindex(C.index).reindex(columns=C.columns)
    R = C.pct_change(fill_method=None); R = R.where(R.abs() < 5)        # salti da ridenominazione scartati
    first = C.apply(lambda s: s.first_valid_index()); last = C.apply(lambda s: s.last_valid_index())
    new = first[first > pd.Timestamp('2020-03-01')]
    print(f'\n== 7e. Nuove quotazioni di perpetual USDT-M su Binance: {len(C.columns)} simboli in archivio, {len(new)} quotati dopo il 2020-03; per anno:', new.dt.year.value_counts().sort_index().to_dict())
    age = pd.DataFrame({c: (C.index - first[c]).days for c in C.columns}, index=C.index).where(C.notna())
    btc = R['BTCUSDT']
    rows = []
    for a0, a1 in ((1, 7), (7, 30), (30, 90), (90, 180), (180, 365)):
        m = (age >= a0) & (age < a1) & (first > pd.Timestamp('2020-03-01'))
        ex = R.sub(btc, axis=0).where(m); fu = Fd.where(m)
        row = dict(giorni=f'{a0}-{a1}')
        for nm, sl in (('scelta', slice(None, SEL_END)), ('verifica', slice(SPL, None))):
            x = ex.loc[sl]; row[f'eccesso_su_BTC_pb_giorno_{nm}'] = round(np.nanmean(x.to_numpy()) * 1e4, 1); row[f'funding_pb_giorno_{nm}'] = round(np.nanmean(fu.loc[sl].to_numpy()) * 1e4, 2); row[f'n_{nm}'] = int(x.notna().sum().sum())
        rows.append(row)
    print(pd.DataFrame(rows).to_string(index=False)); print('   (eccesso negativo = la nuova quotazione rende meno di BTC; funding positivo = lo short lo incassa)')
    def listing_short(a0, a1, w=0.05, fee=0.0015, lag=1, cap=1.0, hedge=True, minvol=5e6):
        liq = V.rolling(7, min_periods=3).mean().shift(1) > minvol
        m = ((age >= a0) & (age < a1) & (first > pd.Timestamp('2020-03-01')) & liq).astype(float) * w
        g = m.sum(axis=1); m = m.mul((cap / g).clip(upper=1.0).fillna(1.0), axis=0)
        held = m.shift(lag).fillna(0.0)
        pnl = -(held * (R.fillna(0.0) - Fd.fillna(0.0))).sum(axis=1) + (held.sum(axis=1) * (btc - Fd['BTCUSDT'].fillna(0.0)) if hedge else 0.0)
        tr = m.shift(lag - 1).diff().abs().sum(axis=1).fillna(0.0)
        return (pnl - tr * fee - (tr * 0.0007 if hedge else 0.0)).loc['2020-06-01':], float(held.sum(axis=1).mean())
    print('   strategia: short di ogni nuova quotazione dal giorno a0 al giorno a1, 5% ciascuna (lordo short max 1), coperta con long BTC perp; costi 15 pb/lato sugli alt, 7 pb su BTC, funding reale')
    for a0, a1 in ((2, 30), (7, 30), (7, 60), (7, 90), (30, 90), (30, 180)):
        r, expo = listing_short(a0, a1); F.line(f'short nuove quotazioni giorni {a0}-{a1}, coperto con BTC', r, extra=f'esp {expo:.2f}')
        if (a0, a1) == (7, 90): r_ls = r
    F.line('   giorni 7-90: costi x2 (30 pb alt)', listing_short(7, 90, fee=0.003)[0]); F.line('   giorni 7-90: ritardo +1 giorno', listing_short(7, 90, lag=2)[0])
    F.line('   giorni 7-90: senza copertura BTC', listing_short(7, 90, hedge=False)[0]); F.line('   giorni 7-90: solo volume > 20 mln $', listing_short(7, 90, minvol=2e7)[0])
    F.line('   giorni 7-90: lordo short max 0,5', listing_short(7, 90, cap=0.5)[0])
    F.keep('NEW-LIST short 7-90g coperto BTC', r_ls)
    print('   giorno peggiore %.1f%%; 5 peggiori: %s' % (100 * r_ls.min(), (r_ls.nsmallest(5) * 100).round(1).to_dict()))

    print('\n== 7f. Carry trasversale perp-contro-perp su tutti i perpetual liquidi: short il quintile col funding piu\' alto, long il quintile col funding piu\' basso')
    def xs_fund(k=7, q=0.2, reb=7, fee=0.0015, lag=1, minvol=2e7, gross=1.0, mom=False):
        liq = (V.rolling(30, min_periods=10).mean() > minvol) & (age > 30)
        sg = Fd.rolling(k, min_periods=k).mean().where(liq); rk = sg.rank(axis=1, pct=True)
        w = (rk <= q).astype(float).div((rk <= q).sum(axis=1).replace(0, np.nan), axis=0).fillna(0) - (rk >= 1 - q).astype(float).div((rk >= 1 - q).sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
        w = w * gross / 2 * (-1.0 if mom else 1.0)
        kk = pd.Series(np.arange(len(w)) % reb == 0, index=w.index); w = w.where(kk, np.nan).ffill().fillna(0.0)
        held = w.shift(lag).fillna(0.0)
        price = (held * R.fillna(0.0)).sum(axis=1); fund = -(held * Fd.fillna(0.0)).sum(axis=1); cost = w.shift(lag - 1).diff().abs().sum(axis=1).fillna(0.0) * fee
        return (price + fund - cost).loc['2020-09-01':], fund.loc['2020-09-01':], price.loc['2020-09-01':]
    for k in (3, 7, 30):
        for reb in (1, 7):
            r, fu, pr = xs_fund(k, reb=reb); F.line(f'funding L/S k{k} ribilancio {reb}g (15 pb)', r, extra=f'| funding incassato {fu.mean() * 36500:.1f}%/anno, prezzi {pr.mean() * 36500:.1f}%/anno')
    r, fu, pr = xs_fund(7, reb=7); r_xf = r
    F.line('   k7 settimanale: costi x2', xs_fund(7, reb=7, fee=0.003)[0]); F.line('   k7 settimanale: ritardo +1', xs_fund(7, reb=7, lag=2)[0]); F.line('   k7 settimanale: decili', xs_fund(7, q=0.1, reb=7)[0])
    F.line('   k7 settimanale: volume > 50 mln $', xs_fund(7, reb=7, minvol=5e7)[0]); F.line('   k7 settimanale: lordo (senza costi)', xs_fund(7, reb=7, fee=0.0)[0])
    F.keep('XS-FUNDING L/S perp (k7, settimanale)', r_xf)
F.save()
