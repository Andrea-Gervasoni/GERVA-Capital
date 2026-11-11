"""A10 - 04: (5) sleeve crypto giornalieri contro libro dei trade; (6) commissioni e sede per sleeve; (7) tasse italiane con
liquidazione annuale. SIMULATO."""
from common import *
import json
from gerva.strategies import book, daily as SD
from gerva.backtest import Costs, run
from gerva.data.sources import Store
st = Store(ROOT + '/data_cache')
cc, cr, cdv = B['cclose'], B['cret'], B['cdvol']
def fund_daily(c):
    try:
        s = st.get(f'bn_fund_{c}USDT').iloc[:, 0]; s.index = (s.index - pd.Timedelta(minutes=5)).normalize(); return s.groupby(level=0).sum()
    except Exception: return None
FUND = pd.DataFrame({c: f for c in cc.columns if (f := fund_daily(c)) is not None}).reindex(cc.index)
print('funding annuo medio (Binance) BTC %.1f%%  ETH %.1f%% ; nei giorni in cui CR-TREND e\' investito: BTC %.1f%% ETH %.1f%%' % (
    FUND['BTC'].mean() * 36500, FUND['ETH'].mean() * 36500, FUND['BTC'][B['Wtrend']['BTC'] > 0.05].mean() * 36500, FUND['ETH'][B['Wtrend']['ETH'] > 0.05].mean() * 36500))
def fundcost(Wheld, default=0.0003):
    F = FUND.reindex(columns=Wheld.columns).reindex(Wheld.index); F = F.where(F.notna(), default)
    return (Wheld.shift(1).fillna(0.0) * F).sum(axis=1)
def port_with(sub):
    S = S6.copy()
    for k, v in sub.items(): S[k] = v.reindex(S.index).fillna(0.0)
    return (A6 * S.fillna(0.0)).sum(axis=1)

print('\n== 6. Commissioni e sede per sleeve (effetto sullo sleeve e sul portafoglio a 6, pesi invariati)')
line('PORTAFOGLIO base', NEW)
rows = {}
for fee, lab in ((0.0030, 'spot 30 pb (base: Kraken/Bitstamp taker + slippage)'), (0.0040, 'spot 40 pb (Kraken Pro taker al primo scaglione)'), (0.0010, 'spot 10 pb (Binance/OKX taker, o maker altrove)'), (0.00065, 'spot 6,5 pb (Hyperliquid spot / maker)')):
    r = book.cr_trend_returns(cc, cr, fee).ret.loc['2018':]; t = trial('fee', f'CR-TREND {lab}', r.reindex(IDX).fillna(0)); rows[f'CT {fee}'] = r
    raw = book.cr_xsmom_returns(cc, cdv, cr, fee).ret.loc['2018':]; x = raw * book.xs_scale(raw); trial('fee', f'CR-XSMOM {lab}', x.reindex(IDX).fillna(0)); rows[f'XS {fee}'] = x
    trial('fee', f'   -> portafoglio con crypto {lab[:11]}', port_with({'CR-TREND': r, 'CR-XSMOM': x}))
# perpetual: 6,5 pb per lato + funding reale sul controvalore tenuto
res = book.cr_trend_returns(cc, cr, 0.00065); ctp = (res.ret - fundcost(res.weights)).loc['2018':]; trial('fee', 'CR-TREND su PERP: 6,5 pb + funding reale', ctp.reindex(IDX).fillna(0), extra=f'| funding pagato {fundcost(res.weights).loc["2018-04":].mean()*365:.2%}/anno')
resx = book.cr_xsmom_returns(cc, cdv, cr, 0.0010); rawp = (resx.ret - fundcost(resx.weights)).loc['2018':]; xsp = rawp * book.xs_scale(rawp); trial('fee', 'CR-XSMOM su PERP: 10 pb + funding reale (0,03%/g dove manca)', xsp.reindex(IDX).fillna(0), extra=f'| funding pagato {fundcost(resx.weights).loc["2018-04":].mean()*365:.2%}/anno')
trial('fee', '   -> portafoglio con CR-TREND e CR-XSMOM su perp', port_with({'CR-TREND': ctp, 'CR-XSMOM': xsp})); trial('fee', '   -> portafoglio con solo CR-TREND su perp', port_with({'CR-TREND': ctp}))
H, Lo, Cc, ret, rfd = B['H'], B['Lo'], B['C'], B['ret'], B['rfd']
def eqmr(fee, spread, lag=1):
    W = book.eq_mr(H, Lo, Cc); held = W.shift(lag).fillna(0.0); carry = rfd + spread / 252
    return ((held * ret[W.columns].sub(carry, axis=0)).sum(axis=1) - W.diff().abs().fillna(0.0).sum(axis=1) * fee).loc['2018':]
for fee, sp, lab in ((0.0005, 0.015, 'CFD 5 pb, rf+1,5% (base)'), (0.0010, 0.025, 'CFD caro: 10 pb, rf+2,5%'), (0.0001, 0.005, 'micro future MES/MNQ: 1 pb, rf+0,5% implicito'), (0.0002, 0.005, 'micro future 2 pb, rf+0,5%'), (0.0003, 0.015, 'CFD IBKR 3 pb, rf+1,5%')):
    e = eqmr(fee, sp); trial('fee', f'EQ-MR {lab}', e.reindex(IDX).fillna(0)); rows[f'EQ {fee} {sp}'] = e
    trial('fee', f'   -> portafoglio con EQ-MR {lab[:14]}', port_with({'EQ-MR': e}))
for fee in (0.0005, 0.0010, 0.0025, 0.0050):
    m = book.ma_trend_returns(B['adj'], rfd, fee).ret.loc['2018':]; trial('fee', f'MA-TREND {fee*1e4:.0f} pb per lato', m.reindex(IDX).fillna(0)); trial('fee', f'   -> portafoglio con MA-TREND {fee*1e4:.0f} pb', port_with({'MA-TREND': m}))
best = port_with({'CR-TREND': rows['CT 0.001'], 'CR-XSMOM': rows['XS 0.001'], 'EQ-MR': rows['EQ 0.0001 0.005']}); trial('fee', 'PORTAFOGLIO: crypto 10 pb + EQ-MR su micro future', best)
print('   Commissione minima per ordine (conto piccolo): numero di ordini l\'anno e costo fisso')
Wm = B['Wma'].loc['2018-04':]; nord_ma = ((Wm.diff().abs() > 1e-6).sum(axis=1)).mean() * 252; Weq = B['Weq'].loc['2018-04':]; nord_eq = ((Weq.diff().abs() > 1e-6).sum(axis=1)).mean() * 252
print(f'   MA-TREND: {nord_ma:.0f} ordini/anno; EQ-MR: {nord_eq:.0f} ordini/anno')
for cap in (12000, 50000, 200000):
    kma = A6['MA-TREND'].mean() * cap; avg_order = kma * B['TO']['MA-TREND'].loc['2018-04':].mean() * 365 / nord_ma
    print(f'   capitale {cap:>7,} $: ordine medio MA-TREND {avg_order:6.0f} $ -> minimo 1,25 EUR = {1.35/avg_order*1e4:5.0f} pb per lato (ipotesi di ricerca: 10 pb); costo fisso MA+EQ {(nord_ma*1.35+nord_eq*1.0)/cap:.2%} del conto l\'anno')

print('\n== 5. Sleeve crypto giornalieri e libro dei trade: stesso trend?')
Tm, mg, no, rk = trade_book()
ct = S0['CR-TREND'].reindex(IDX); xs = S0['CR-XSMOM'].reindex(IDX)
print('correlazione del libro dei trade (mtm) con CR-TREND: giornaliera %.2f mensile %.2f;  con CR-XSMOM: %.2f / %.2f;  con il libro a 6: %.2f / %.2f' % (Tm.corr(ct), mm(Tm).corr(mm(ct)), Tm.corr(xs), mm(Tm).corr(mm(xs)), Tm.corr(NEW), mm(Tm).corr(mm(NEW))))
on = no > 0; expo_ct = (A6['CR-TREND'] * G6['CR-TREND']); expo_xs = (A6['CR-XSMOM'] * G6['CR-XSMOM'])
print('giorni con trade aperti: %.0f%%; in quei giorni controvalore medio dei trade %.2f del patrimonio contro esposizione di CR-TREND %.3f e CR-XSMOM %.3f (a 1x)' % (100 * on.mean(), no[on].mean(), expo_ct[on].mean(), expo_xs[on].mean()))
print('quota dei giorni di trade in cui CR-TREND e\' investito (>5%% del suo capitale): %.0f%%; quota dei giorni CR-TREND investito con un trade aperto: %.0f%%' % (100 * (G6['CR-TREND'][on] > .05).mean(), 100 * on[G6['CR-TREND'] > .05].mean()))
a4 = with_carry(risk_parity(S5.drop(columns=['CR-TREND']))); S4 = S6.drop(columns=['CR-TREND']).reindex(a4.index); NOCT = (a4 * S4.fillna(0.0)).sum(axis=1).reindex(IDX)
a3_ = with_carry(risk_parity(S5.drop(columns=['CR-TREND', 'CR-XSMOM']))); NOCR = (a3_ * S6.drop(columns=['CR-TREND', 'CR-XSMOM']).reindex(a3_.index).fillna(0.0)).sum(axis=1).reindex(IDX)
# sizing dei trade al netto di quanto gli sleeve tengono gia' della stessa moneta
Wt = B['Wtrend'].reindex(IDX).fillna(0.0); Wx = (B['Wxs'].mul(B['xs'], axis=0)).reindex(IDX).fillna(0.0)
def overlap_scale(L=1.0, rc=.01, re=.02):
    X, paths = trade_tables(); sc = {}
    for _, t in X.iterrows():
        d = pd.Timestamp(t.entry) - pd.Timedelta(days=1)
        if d not in IDX: continue
        held = L * (A6['CR-TREND'].get(d, 0) * (Wt[t.coin].get(d, 0) if t.coin in Wt else 0) + A6['CR-XSMOM'].get(d, 0) * (Wx[t.coin].get(d, 0) if t.coin in Wx else 0))
        risk = re if (t.score is not None and t.score > .75) else rc; sc[(t.coin, pd.Timestamp(t.entry))] = max(1 - held / (risk / t.s), 0.0)
    return sc
sc = overlap_scale(); v = np.array(list(sc.values())); print('riduzione media del controvalore dei trade se si sottrae cio\' che gli sleeve tengono gia\': %.1f%% (1x), mediana %.1f%%' % (100 * (1 - v.mean()), 100 * (1 - np.median(v))))
def tb_net(L, rc, re):
    X, paths = trade_tables(); sc = overlap_scale(L, rc, re); r = pd.Series(0.0, index=IDX)
    for (i, t), p in zip(X.iterrows(), paths):
        risk = re if (t.score is not None and t.score > .75) else rc; r = r.add(p * (risk / t.s) * sc.get((t.coin, pd.Timestamp(t.entry)), 1.0), fill_value=0.0)
    return r.reindex(IDX).fillna(0.0)
# alternativa: niente libro dei trade, ma CR-TREND su perp portato alla stessa volatilita' (scelta della scala SOLO sul periodo di scelta)
ctp_ = ctp.reindex(IDX).fillna(0.0); k = Tm[:SEL_END].std() / ctp_[:SEL_END].std(); print('scala di CR-TREND (perp) che pareggia la volatilita\' del libro dei trade in scelta: %.2f x il capitale' % k)
for L in (1, 2):
    base = NEW if L == 1 else lev09(NEW, 2); b_noct = NOCT if L == 1 else lev09(NOCT, 2); b_nocr = NOCR if L == 1 else lev09(NOCR, 2)
    print(f'  --- libro giornaliero {L}x, trade 1%/2% (statistiche MENSILI, mtm) ---')
    trial('interazione', f'{L}x: 6 strategie, senza trade', base, monthly=True)
    trial('interazione', f'{L}x: 6 strategie + trade (attuale C{2 if L == 1 else 3})', base + Tm, monthly=True)
    trial('interazione', f'{L}x: SENZA CR-TREND (5 strategie) + trade', b_noct + Tm, monthly=True)
    trial('interazione', f'{L}x: SENZA CR-TREND e CR-XSMOM (4 strategie) + trade', b_nocr + Tm, monthly=True)
    trial('interazione', f'{L}x: 6 strategie + trade al netto degli sleeve', base + tb_net(L, .01, .02), monthly=True)
    trial('interazione', f'{L}x: 6 strategie + CR-TREND perp x{k:.2f} al posto dei trade', base + k * ctp_, monthly=True)
    trial('interazione', f'{L}x: 6 strategie + meta\' trade + meta\' CR-TREND perp', base + 0.5 * Tm + 0.5 * k * ctp_, monthly=True)
trial('interazione', 'solo trade (mtm)', Tm, monthly=True); trial('interazione', f'solo CR-TREND perp x{k:.2f}', k * ctp_, monthly=True)
X, _ = trade_tables(); y = (X.entry.max() - X.entry.min()).days / 365.25
print('aritmetica del brief: N = %.0f trade/anno, R medio %.3f, sigma_R %.2f, R/sigma %.3f -> N (R/sigma)^2 = %.2f (serve 6,3)' % (len(X) / y, X.R.mean(), X.R.std(), X.R.mean() / X.R.std(), len(X) / y * (X.R.mean() / X.R.std()) ** 2))

print('\n== 7. Tasse italiane, liquidazione annuale: 33% crypto (spot, carry), 26% derivati (perp, CFD) ed ETF; minus riportabili 4 anni nella stessa categoria')
def after_tax(parts, rates, start=None, end=None, etf_asym=True):
    """parts: dict categoria -> serie del contributo giornaliero (frazione del patrimonio). Tassa a fine anno sul netto dell'anno per categoria,
    al netto delle minus riportate (max 4 anni). ETF: i guadagni sono redditi di capitale (non compensabili), le perdite vanno tra le minus dei derivati."""
    df = pd.DataFrame(parts).loc[start:end]; E = 1.0; pnl = {k: 0.0 for k in parts}; loss = {k: [] for k in parts}; eq = []; taxes = 0.0; gross = 1.0
    yrs = df.index.year.values; V = df.values; cols = list(df.columns)
    for i in range(len(df)):
        for j, k in enumerate(cols): pnl[k] += E * V[i, j]
        E *= 1 + V[i].sum(); gross *= 1 + V[i].sum()
        if i == len(df) - 1 or yrs[i + 1] != yrs[i]:
            if etf_asym and 'etf' in pnl and pnl['etf'] < 0 and 'deriv' in pnl: pnl['deriv'] += pnl['etf']; pnl['etf'] = 0.0
            for k in cols:
                g = pnl[k]
                if g > 0:
                    if not (etf_asym and k == 'etf'):
                        for l in loss[k]:
                            u = min(l[1], g); l[1] -= u; g -= u
                    tx = g * rates[k]; E -= tx; taxes += tx
                elif g < 0 and k != 'nodeduct': loss[k].append([yrs[i], -g])
                loss[k] = [l for l in loss[k] if l[1] > 1e-12 and yrs[i] - l[0] < 4]; pnl[k] = 0.0
        eq.append(E)
    n = len(df) / 365; return gross ** (1 / n) - 1, E ** (1 / n) - 1, pd.Series(eq, index=df.index)
C6c = (A6 * S6.fillna(0.0)).reindex(IDX)
def parts(L=1.0, rc=0.0, re=0.0, fin='09', park=False):
    T = trade_book(rc, re)[0] if rc > 0 else pd.Series(0.0, index=IDX)
    cu = cash_used(lev=L); finc = (L - 1) * (rf + .015 / 365) if fin == '09' else np.maximum(cu - 1, 0) * (rf + .015 / 365)
    p = dict(crypto=L * C6c[['CR-TREND', 'CR-XSMOM', 'CARRY']].sum(axis=1), deriv=L * C6c[['EQ-MR', 'DIP']].sum(axis=1) + T, etf=L * C6c['MA-TREND'], nodeduct=-finc)
    if park: p['tbill'] = pd.read_parquet(HERE + '/_park.parquet')['park'].reindex(IDX).fillna(0.0)
    return p
RATES = dict(crypto=.33, deriv=.26, etf=.26, nodeduct=0.0, tbill=.125); RATES33 = dict(RATES, deriv=.33); RATES26 = dict(RATES, crypto=.26)
PROF = [('B. 6 strategie 1x', parts(1)), ('B + cassa in T-bill', parts(1, park=True)), ('B2. 6 strategie 2x (09)', parts(2)), ('B2 con debito reale', parts(2, fin='reale')),
        ('C1. 1x + trade 0,5/1%', parts(1, .005, .01)), ('C2. 1x + trade 1/2%', parts(1, .01, .02)), ('C3. 2x + trade 1/2% (profilo massimo)', parts(2, .01, .02)), ('C3 con debito reale', parts(2, .01, .02, fin='reale')), ('C6. 3x + trade 1,5/3%', parts(3, .015, .03))]
out = []
for nm, p in PROF:
    row = dict(profilo=nm)
    for lab, (a, b) in (('tot', (None, None)), ('sel', (None, SEL_END)), ('ver', (SPL, None))):
        g, n, _ = after_tax(p, RATES, a, b); row[f'lordo_{lab}'] = g; row[f'netto_{lab}'] = n
    g, n33, _ = after_tax(p, RATES33); g, n26, _ = after_tax(p, RATES26); g, nsym, _ = after_tax(p, RATES, etf_asym=False)
    row.update(netto_perp33=n33, netto_crypto26=n26, netto_etf_simm=nsym, mese_netto=(1 + row['netto_tot']) ** (1 / 12) - 1); out.append(row)
T7 = pd.DataFrame(out).set_index('profilo'); print((T7 * 100).round(1).to_string())
print('   lordo/netto = CAGR prima/dopo le imposte; netto_perp33 = se i perpetual su crypto fossero tassati al 33%; netto_crypto26 = aliquota crypto del 2025; netto_etf_simm = se gli ETF compensassero come i derivati')
print('   Nota: gli interessi passivi del debito non sono deducibili per una persona fisica; le imposte si pagano il 31/12 (in realta\' a giugno dell\'anno dopo: leggero vantaggio non contato).')
# crypto sleeve su perp: 26% invece di 33% + cassa liberata
pp = parts(1); pp2 = dict(pp); pp2['crypto'] = C6c['CARRY']; pp2['deriv'] = pp['deriv'] + A6['CR-TREND'] * ctp_ + A6['CR-XSMOM'] * xsp.reindex(IDX).fillna(0.0)
g, n, _ = after_tax(pp2, RATES); print('   B con CR-TREND e CR-XSMOM su perpetual (26%% invece di 33%%): lordo %.1f%% netto %.1f%%  (B spot: lordo %.1f%% netto %.1f%%)' % (100 * g, 100 * n, 100 * T7.loc['B. 6 strategie 1x', 'lordo_tot'], 100 * T7.loc['B. 6 strategie 1x', 'netto_tot']))
json.dump(TRIALS, open(HERE + '/trials_04.json', 'w'), indent=0); print('\nvarianti provate in questo script:', {k: len(v) for k, v in TRIALS.items()}, 'totale', sum(len(v) for v in TRIALS.values()))
