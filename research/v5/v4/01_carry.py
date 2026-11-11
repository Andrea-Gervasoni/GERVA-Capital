"""Famiglia 1 - carry sul funding / cash-and-carry: long spot + short perpetual.
Dati REALI: Binance spot e USDT-M 1h (36 monete, incluse LUNA e FTT), funding Binance 2020->2026-10, funding orario
Hyperliquid 2023-05->oggi. Tutti i risultati sono SIMULATI.
Contabilita' per unita' di nozionale e per giorno: r_spot - r_perp + funding incassato dallo short.
Capitale: 1 = nozionale spot N + margine del perp N/L  ->  N = L/(1+L)  (L=3: 75% del capitale lavora).
Costi: spot 30 pb/lato, perp 7 pb/lato (entrambe le gambe, in entrata e in uscita: 74 pb a giro completo).
La liquidita' non investita e il margine NON rendono nulla; lo Sharpe sottrae il tasso a breve."""
from lab import *
F = Fam('carry')
coins = PERP
S = hourly_panel('spot', coins); P = hourly_panel('um', coins); PH = hourly_panel('um', coins, 'high'); PV = hourly_panel('um', coins, 'quote_volume')
days = pd.date_range('2020-01-01', '2026-10-31')
dl = lambda X: X.groupby(X.index.normalize()).last().reindex(days)
s_d, p_d = dl(S), dl(P); ph_d = PH.groupby(PH.index.normalize()).max().reindex(days); pv_d = PV.groupby(PV.index.normalize()).sum().reindex(days)
fd = funding_daily(coins).reindex(days)
coins = [c for c in coins if c in s_d and c in p_d and c in fd]; s_d, p_d, ph_d, pv_d, fd = s_d[coins], p_d[coins], ph_d[coins], pv_d[coins], fd[coins]
rs, rp = s_d.pct_change(fill_method=None), p_d.pct_change(fill_method=None)
unit = (rs - rp + fd)                                     # rendimento giornaliero di 1 di nozionale coperto
ok = unit.notna() & (pv_d.rolling(30, min_periods=10).mean() > 2e7)
print('monete:', len(coins), coins)
print('\n== FATTO: funding annuo incassato dallo short, % (somma semplice), Binance USDT-M')
yr = (fd.groupby(fd.index.year).sum() * 100).round(1); print(yr[[c for c in 'BTC ETH SOL BNB XRP DOGE ADA LINK AVAX LTC'.split()]].T.to_string())
print('media delle 10 maggiori:', yr[[c for c in 'BTC ETH SOL BNB XRP DOGE ADA LINK AVAX LTC'.split()]].mean(axis=1).round(1).to_dict())
print('tasso a breve medio annuo %:', (RF.groupby(RF.index.year).sum() * 100).round(1).to_dict())

def bt(sig, enter, exit_, N=5, L=3, fs=0.003, fp=0.0007, lag=1, unit_=unit, ok_=ok, ph=ph_d, pd_=p_d, detail=False, mm=0.01):
    """sig: funding medio annualizzato noto alla chiusura di D. Isteresi: si entra sopra `enter`, si esce sotto `exit_`.
    lag=1: eseguito alla chiusura di D (incassa da D+1); lag=2: una barra in piu'."""
    cs = list(unit_.columns); n = len(cs); U = unit_.to_numpy(); SG = sig.reindex(unit_.index)[cs].to_numpy(); OK = ok_.to_numpy()
    PD, PHh = pd_[cs].to_numpy(), ph[cs].to_numpy()
    Nn = L / (1 + L); w = np.zeros(n); held = np.zeros(n, bool); reset = np.full(n, np.nan)
    out = np.zeros(len(U)); turn = np.zeros(len(U)); nliq = 0; nrem = 0; pend = []
    for t in range(len(U)):
        u = np.where(np.isfinite(U[t]), U[t], 0.0)
        pnl = float(w @ u); cost = 0.0
        # rischio di liquidazione dello short: massimo orario del giorno contro il prezzo dell'ultimo ripristino del margine
        for i in np.where(w > 0)[0]:
            mh = PHh[t, i] / reset[i] - 1 if np.isfinite(PHh[t, i]) else 0.0
            if mh >= 1 / L - mm:                      # margine esaurito dentro la giornata: liquidazione
                nliq += 1; cost += w[i] * (mm + fp + fs * (1 / L)); reset[i] = PD[t, i]   # si perde il margine di mantenimento e si ricostituisce
            else:
                m = PD[t, i] / reset[i] - 1 if np.isfinite(PD[t, i]) else 0.0
                if m > 0.5 / L:                       # ripristino a fine giornata: si vende m di spot e si ricompra m di perp
                    nrem += 1; cost += w[i] * m * (fs + fp); reset[i] = PD[t, i]
        # decisione alla chiusura di t (eseguita con `lag`)
        sg = SG[t]; valid = OK[t] & np.isfinite(sg)
        held = held & valid & (sg >= exit_)
        free = N - held.sum()
        if free > 0:
            cand = np.where(valid & ~held & (sg > enter))[0]
            for i in cand[np.argsort(-sg[cand])][:free]: held[i] = True
        pend.append(held.copy())
        if len(pend) >= lag:
            tgt = pend[-lag] * (Nn / N)
            tgt = np.where(np.isfinite(U[min(t + 1, len(U) - 1)]) | (tgt == 0), tgt, 0.0) if t + 1 < len(U) else tgt
            tr = np.abs(tgt - w); cost += float(tr.sum()) * (fs + fp); turn[t] = tr.sum()
            for i in np.where((tgt > 0) & (w == 0))[0]: reset[i] = PD[t, i]
            w = tgt
        out[t] = pnl - cost
    r = pd.Series(out, index=unit_.index)
    if detail: return r, dict(turn_annuo=float(turn.sum() / len(U) * 365 / 2), liquidazioni=nliq, ripristini=nrem, esposizione_media=float(0))
    return r

ann = lambda k: fd.rolling(k, min_periods=k).mean() * 365
START = '2020-06-01'
print('\n== 1a. Sempre dentro, per moneta (L=3, costi pieni; entra una volta sola): Sharpe tot|scelta|verifica')
for c in 'BTC ETH SOL BNB XRP DOGE ADA LINK AVAX LTC'.split():
    r = bt(ann(7) * 0 + 1, 0.5, -9, N=1, unit_=unit[[c]], ok_=ok[[c]], ph=ph_d[[c]], pd_=p_d[[c]]).loc[START:]
    F.line(f'sempre dentro {c}', r)
r = bt(ann(7) * 0 + 1, 0.5, -9, N=10, unit_=unit['BTC ETH SOL BNB XRP DOGE ADA LINK AVAX LTC'.split()], ok_=ok['BTC ETH SOL BNB XRP DOGE ADA LINK AVAX LTC'.split()], ph=ph_d, pd_=p_d).loc[START:]
F.line('sempre dentro, 10 maggiori equipesate', r)

print('\n== 1b. Trasversale con isteresi: griglia (finestra segnale k, soglia entrata, soglia uscita, N). L=3, costi pieni')
rows = []
for k in (3, 7, 14, 30):
    sg = ann(k)
    for en in (0.10, 0.15, 0.20, 0.30):
        for ex in (0.0, 0.05):
            for N in (3, 5, 8):
                r = bt(sg, en, ex, N).loc[START:]; t = F.trial(f'xs k{k} en{en} ex{ex} N{N}', r)
                rows.append(dict(k=k, en=en, ex=ex, N=N, **{a: t[a] for a in ('sh_tot', 'sh_sel', 'sh_ver', 'cagr_sel', 'cagr_ver', 'vol_tot', 'dd_tot')}))
G = pd.DataFrame(rows); print(G.round(3).to_string(index=False))
print('\nriassunto griglia: Sharpe scelta mediano %.2f, verifica mediano %.2f; quota di varianti con verifica > 0: %.0f%%' % (G.sh_sel.median(), G.sh_ver.median(), 100 * (G.sh_ver > 0).mean()))
best = G.sort_values('sh_sel', ascending=False).iloc[0]; print('migliore sulla SCELTA:', best.to_dict())
k, en, ex, N = int(best.k), float(best.en), float(best.ex), int(best.N)
# configurazione centrale dichiarata (non la migliore): k=7, entra > 15%, esce < 5%, N=5
CK, CEN, CEX, CN = 7, 0.15, 0.05, 5
print('\n== 1c. Configurazione centrale (k=7, entra>15% annuo, esce<5%, 5 monete) e migliore-in-scelta: robustezza')
for lab, (a, b, c_, d) in (('centrale', (CK, CEN, CEX, CN)), ('migliore scelta', (k, en, ex, N))):
    sg = ann(a)
    for L in (2, 3, 5):
        r, info = bt(sg, b, c_, d, L=L, detail=True); F.line(f'{lab} L={L}', r.loc[START:], extra=str({q: round(v, 2) for q, v in info.items() if q != 'esposizione_media'}))
    F.line(f'{lab} L=3 costi x2', bt(sg, b, c_, d, fs=0.006, fp=0.0014).loc[START:])
    F.line(f'{lab} L=3 ritardo +1 barra', bt(sg, b, c_, d, lag=2).loc[START:])
    F.line(f'{lab} L=3 spot 10 pb (IPOTESI maker/Binance)', bt(sg, b, c_, d, fs=0.001).loc[START:])
    F.line(f'{lab} L=3 costi zero (lordo)', bt(sg, b, c_, d, fs=0.0, fp=0.0).loc[START:])
rc = bt(ann(CK), CEN, CEX, CN).loc[START:]
F.keep('CARRY-XS (Binance, centrale, L=3)', rc)
inpos = (rc != 0).groupby(rc.index.year).mean().round(2).to_dict(); print('   quota di giorni investiti per anno:', inpos)
print('   rendimento annuo % per anno:', ((1 + rc).groupby(rc.index.year).prod() - 1).mul(100).round(1).to_dict())

# ---------------- Hyperliquid ----------------
print('\n== 1d. Hyperliquid: funding orario reale 2023-05 -> oggi (solo periodo di VERIFICA)')
HL = [c for c in "BTC ETH SOL BNB XRP DOGE ADA LTC LINK AVAX SUI ARB OP APT NEAR".split() if has(f'v4_hl_fund_{c}') and has(f'v4_hl_1d_{c}')]
print('monete Hyperliquid scaricate:', HL)
if HL:
    hf = {}; hp = {}
    for c in HL:
        x = get(f'v4_hl_fund_{c}')['fundingRate']; x.index = (x.index - pd.Timedelta(minutes=5)).normalize(); hf[c] = x.groupby(level=0).sum()
        hp[c] = get(f'v4_hl_1d_{c}')['close']
    hf = pd.DataFrame(hf).reindex(days); hp = pd.DataFrame(hp).reindex(days); hh = pd.DataFrame({c: get(f'v4_hl_1d_{c}')['high'] for c in HL}).reindex(days)
    both = [c for c in HL if c in fd]
    cmp_ = pd.DataFrame({'HL %/anno': hf[both].loc['2023-06':].groupby(hf.loc['2023-06':].index.year).sum().mean(axis=1) * 100,
                         'Binance %/anno': fd[both].loc['2023-06':].groupby(fd.loc['2023-06':].index.year).sum().mean(axis=1) * 100}).round(1)
    print('funding medio annuo (media semplice sulle monete in comune; 2023 = da giugno; 2026 = fino a ottobre):'); print(cmp_.to_string())
    dsp = (hf[both] - fd[both]).loc['2023-06':]
    print('spread HL-Binance per moneta, % annuo medio:', (dsp.mean() * 36500).round(1).to_dict())
    print('   dev.std giornaliera dello spread (pb):', (dsp.std() * 1e4).round(1).to_dict(), ' autocorrelazione a 1g:', {c: round(dsp[c].autocorr(1), 2) for c in both})
    # carry spot (prezzi spot Binance) + short perp Hyperliquid
    hl_days = hf.index[hf.notna().any(axis=1)]
    u_hl = (rs[HL] - hp.pct_change(fill_method=None) + hf).loc['2023-05-13':]
    ok_hl = u_hl.notna()
    annh = lambda k: (hf.rolling(k, min_periods=k).mean() * 365).loc['2023-05-13':]
    for lab, kw in (('HL carry centrale (spot 30pb + HL 7pb)', {}), ('HL carry centrale, costi x2', dict(fs=0.006, fp=0.0014)), ('HL carry centrale, ritardo +1', dict(lag=2)),
                    ('HL carry centrale, spot 10 pb (IPOTESI)', dict(fs=0.001)), ('HL carry centrale, spot HL 7pb taker (solo BTC/ETH/SOL esistono: IPOTESI)', dict(fs=0.0007))):
        r, info = bt(annh(CK), CEN, CEX, CN, unit_=u_hl, ok_=ok_hl, ph=hh.loc[u_hl.index], pd_=hp.loc[u_hl.index], detail=True, **kw)
        F.line(lab, r.loc['2023-06':], extra=str({q: round(v, 2) for q, v in info.items() if q != 'esposizione_media'}))
        if not kw: rhl = r.loc['2023-06':]
    for kk in (3, 14):
        for en_ in (0.10, 0.20):
            for N_ in (3, 8):
                F.line(f'HL carry k{kk} en{en_} N{N_}', bt(annh(kk), en_, CEX, N_, unit_=u_hl, ok_=ok_hl, ph=hh.loc[u_hl.index], pd_=hp.loc[u_hl.index]).loc['2023-06':])
    yr_ = lambda r: ((1 + r).groupby(r.index.year).prod() - 1).mul(100).round(1).to_dict()
    print('   HL carry centrale: rendimento % per anno (2023 da giugno, 2026 fino a ottobre):', yr_(rhl), ' giorni investiti:', (rhl != 0).groupby(rhl.index.year).mean().round(2).to_dict())
    ra_ = bt(annh(7) * 0 + 1, 0.5, -9, N=3, unit_=u_hl[['BTC', 'ETH', 'SOL']], ok_=ok_hl[['BTC', 'ETH', 'SOL']], ph=hh.loc[u_hl.index], pd_=hp.loc[u_hl.index]).loc['2023-06':]
    print('   HL sempre dentro BTC+ETH+SOL: rendimento % per anno:', yr_(ra_))
    F.line('HL sempre dentro BTC+ETH+SOL', bt(annh(7) * 0 + 1, 0.5, -9, N=3, unit_=u_hl[['BTC', 'ETH', 'SOL']], ok_=ok_hl[['BTC', 'ETH', 'SOL']], ph=hh.loc[u_hl.index], pd_=hp.loc[u_hl.index]).loc['2023-06':])
    # serie incollata: Binance fino al 2023-05, Hyperliquid dopo (cio' che un italiano potrebbe eseguire oggi)
    glued = pd.concat([rc.loc[:'2023-05-31'], rhl]); F.line('CARRY-XS incollato (Binance <=2023-05, Hyperliquid dopo)', glued); F.keep('CARRY-XS-HL (incollato)', glued)
    # arbitraggio di funding tra sedi: short dove il funding e' alto, long dove e' basso (perp contro perp)
    print('\n== 1e. Arbitraggio di funding Hyperliquid vs Binance (perp contro perp; Binance futures NON accessibile a un retail italiano: riferimento)')
    rb = rp[both]; rh = hp[both].pct_change(fill_method=None)
    def spread_bt(k, en_, ex_, fee=0.0007 + 0.0007, lag=1, lev=1.0):
        sg = (dsp.rolling(k, min_periods=k).mean() * 365); pos = pd.DataFrame(0.0, index=dsp.index, columns=both)
        for c in both:
            p = 0.0; v = sg[c].to_numpy(); o = np.zeros(len(v))
            for t in range(len(v)):
                if not np.isfinite(v[t]): p = 0.0
                elif p == 0 and abs(v[t]) > en_: p = np.sign(v[t])
                elif p != 0 and v[t] * p < ex_: p = 0.0
                o[t] = p
            pos[c] = o
        pos = pos / len(both) * lev                       # pos>0: short HL, long Binance
        held = pos.shift(lag).fillna(0)
        pnl = held * (dsp + rb.loc[dsp.index] - rh.loc[dsp.index]).fillna(0)
        return pnl.sum(axis=1) - pos.shift(lag - 1).diff().abs().sum(axis=1).fillna(0) * fee, held.abs().sum(axis=1).mean()
    for k_ in (3, 7, 14):
        for en_ in (0.05, 0.10, 0.20):
            r, expo = spread_bt(k_, en_, en_ / 4); F.line(f'spread HL-BN k{k_} en{en_}', r, extra=f'esposizione media {expo:.2f}')
    r, _ = spread_bt(7, 0.10, 0.025, fee=0.0028); F.line('spread HL-BN k7 en0.10 costi x2', r)
    r, _ = spread_bt(7, 0.10, 0.025, lag=2); F.line('spread HL-BN k7 en0.10 ritardo +1', r)
    r, _ = spread_bt(7, 0.10, 0.025, lev=2.0); F.line('spread HL-BN k7 en0.10, nozionale 2x per gamba', r); F.keep('FUND-ARB HL-BN (k7, 10%, 2x)', r)
# capacita'
v = pv_d.loc['2026-01':].median().sort_values(); print('\n== capacita\': volume giornaliero mediano 2026 dei perp (mln $):', (v / 1e6).round(0).to_dict())
F.save()
