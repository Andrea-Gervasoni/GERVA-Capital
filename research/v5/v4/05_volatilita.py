"""Famiglia 5 - volatilita': premio per il rischio di varianza su BTC/ETH (indice DVOL di Deribit, REALE, dal 2021-03)
contro la volatilita' realizzata successiva (candele 1h Binance); proxy di vendita di volatilita'; DVOL e vol-della-vol come
filtro di regime per CR-TREND e CR-XSMOM.
ATTENZIONE: non ho prezzi storici delle opzioni (denaro/lettera). Il P&L 'short varianza' e' una STIMA: variance swap
teorico venduto a (DVOL - 3 punti)^2, senza margini ne' liquidazioni intragiornaliere. Selezione: solo 2021-03 -> 2022-12.
Esecuzione per un retail italiano: Deribit (opzioni su BTC/ETH, margine in coin o USDC) oppure IBKR (opzioni su ETF spot
bitcoin USA: non acquistabili senza KID; opzioni su future CME: contratto troppo grande). Tutti i numeri sono SIMULATI."""
from lab import *
F = Fam('vol')
days = pd.date_range('2021-03-24', '2026-10-31')
out = {}
for cur in ('BTC', 'ETH'):
    dv = get(f'v4_dvol_{cur}')['close'].reindex(days).ffill() / 100          # chiusura giornaliera (00:00 UTC del giorno dopo)
    h = get(f'v4_um_1h_{cur}USDT')['close']; rh = np.log(h).diff()
    rv_d = (rh ** 2).groupby(rh.index.normalize()).sum().reindex(days)        # varianza realizzata del giorno (da rendimenti orari)
    rd = h.groupby(h.index.normalize()).last().pct_change().reindex(days)
    rv30_fwd = np.sqrt(rv_d.rolling(30).sum().shift(-30) * 365 / 30); rv30_bwd = np.sqrt(rv_d.rolling(30).sum() * 365 / 30)
    out[cur] = dict(dv=dv, rv_d=rv_d, rd=rd, fwd=rv30_fwd, bwd=rv30_bwd)
    vrp = (dv - rv30_fwd).dropna()
    print(f'== 5a. {cur}: premio di volatilita\' = DVOL - volatilita\' realizzata dei 30 giorni successivi (punti di vol)')
    t = pd.DataFrame({'DVOL medio': dv.groupby(dv.index.year).mean() * 100, 'RV 30g succ.': rv30_fwd.groupby(rv30_fwd.index.year).mean() * 100,
                      'premio medio': vrp.groupby(vrp.index.year).mean() * 100, 'premio mediano': vrp.groupby(vrp.index.year).median() * 100,
                      'giorni con premio>0 %': (vrp > 0).groupby(vrp.index.year).mean() * 100, 'premio minimo': vrp.groupby(vrp.index.year).min() * 100}).round(1)
    print(t.to_string()); print(f'   intero periodo: premio medio {vrp.mean() * 100:.1f} punti, positivo nel {100 * (vrp > 0).mean():.0f}% dei giorni; scelta {vrp.loc[:SEL_END].mean() * 100:.1f}, verifica {vrp.loc[SPL:].mean() * 100:.1f}')

print('\n== 5b. STIMA: vendita sistematica di varianza a 30 giorni (1/30 al giorno), strike = (DVOL - spread)^2, vega = 1% del capitale per punto di vol (un errore di 50 punti = -50% e oltre, per la convessita)')
def short_var(cur, spread=0.03, vega=0.01, gate=None, lag=1):
    o = out[cur]; K = (o['dv'] - spread).clip(lower=0.05)
    # ogni strip: nozionale di varianza = vega/(2K) per punto (in unita' di vol^2 annua); matura in 30 giorni: accumula K^2/365 - r_t^2 ogni giorno
    nv = (vega * 100) / (2 * K) / 30
    if gate is not None: nv = nv * gate.reindex(days).fillna(0.0)
    nv = nv.shift(lag - 1) if lag > 1 else nv
    Ks = (K.shift(lag - 1) if lag > 1 else K)
    A = (nv * Ks ** 2).rolling(30).sum().shift(1); B = nv.rolling(30).sum().shift(1)       # strip aperte fino a ieri
    return (A / 365 - B * o['rv_d']).fillna(0.0)
for cur in ('BTC', 'ETH'):
    for sp in (0.0, 0.03, 0.06):
        x = short_var(cur, sp); F.line(f'short varianza {cur}, spread {int(sp * 100)} punti', x, extra=f'| Sharpe rf=0: tot {sh0(x):.2f} scelta {sh0(x.loc[:SEL_END]):.2f} verifica {sh0(x.loc[SPL:]):.2f}')
sv = 0.5 * (short_var('BTC') + short_var('ETH')); F.line('short varianza BTC+ETH, spread 3 punti', sv)
print('   giorno peggiore %.1f%%, 5 giorni peggiori: %s' % (100 * sv.min(), (sv.nsmallest(5) * 100).round(1).to_dict()))
print('   Sharpe per anno:', by_year(sv), ' rendimento % per anno:', ((1 + sv).groupby(sv.index.year).prod() - 1).mul(100).round(1).to_dict())
print('\n== 5b-bis. Con filtro: si vende solo se DVOL > volatilita\' realizzata degli ultimi 30 giorni + x punti (premio ex-ante positivo), oppure solo se DVOL < percentile (niente vendite in crisi)')
for x in (0.0, 0.05, 0.10):
    g = {c: (out[c]['dv'] - out[c]['bwd'] > x).astype(float) for c in out}
    y = 0.5 * (short_var('BTC', gate=g['BTC']) + short_var('ETH', gate=g['ETH'])); F.line(f'short varianza BTC+ETH solo se DVOL-RV30 passata > {int(x * 100)} punti', y, extra=f'| Sharpe rf=0: tot {sh0(y):.2f} scelta {sh0(y.loc[:SEL_END]):.2f} verifica {sh0(y.loc[SPL:]):.2f}')
for q in (0.5, 0.8):
    g = {c: (out[c]['dv'] < out[c]['dv'].rolling(365, min_periods=120).quantile(q)).astype(float) for c in out}
    F.line(f'short varianza BTC+ETH solo se DVOL < percentile {int(q * 100)} a 1 anno', 0.5 * (short_var('BTC', gate=g['BTC']) + short_var('ETH', gate=g['ETH'])))
g = {c: (out[c]['dv'] - out[c]['bwd'] > 0.05).astype(float) for c in out}
svg = 0.5 * (short_var('BTC', gate=g['BTC']) + short_var('ETH', gate=g['ETH']))
F.line('   filtro 5 punti: spread 6 punti (costi x2)', 0.5 * (short_var('BTC', 0.06, gate=g['BTC']) + short_var('ETH', 0.06, gate=g['ETH'])))
F.line('   filtro 5 punti: ritardo +1 giorno', 0.5 * (short_var('BTC', gate=g['BTC'], lag=2) + short_var('ETH', gate=g['ETH'], lag=2)))
F.keep('SHORT-VAR BTC+ETH (STIMA, filtro 5 punti)', svg); F.keep('SHORT-VAR BTC+ETH (STIMA, sempre)', sv)

print('\n== 5c. DVOL e vol-della-vol come filtro di regime sulle strategie di trend esistenti (CR-TREND, CR-XSMOM)')
print('   Il filtro moltiplica l\'esposizione per 0 / 0,5 / 1; costo del cambio: 30 pb x esposizione media (0,5) x variazione del moltiplicatore.')
dvb = out['BTC']['dv']; vov = dvb.diff().rolling(30).std() * math.sqrt(365)
def apply(s, mult):
    m = mult.reindex(IDX).shift(1).fillna(1.0); return S0[s] * m - m.diff().abs().fillna(0.0) * 0.5 * 0.003
filters = {
    'DVOL < percentile 80 (1 anno)': (dvb < dvb.rolling(365, min_periods=120).quantile(0.8)).astype(float),
    'DVOL < percentile 50 (1 anno)': (dvb < dvb.rolling(365, min_periods=120).quantile(0.5)).astype(float),
    'DVOL > percentile 50 (1 anno)': (dvb > dvb.rolling(365, min_periods=120).quantile(0.5)).astype(float),
    'DVOL in calo a 10 giorni': (dvb < dvb.shift(10)).astype(float),
    'DVOL in salita a 10 giorni': (dvb > dvb.shift(10)).astype(float),
    'premio ex-ante > 0 (DVOL > RV30 passata)': (dvb > out['BTC']['bwd']).astype(float),
    'premio ex-ante < 0': (dvb < out['BTC']['bwd']).astype(float),
    'vol-della-vol < percentile 80': (vov < vov.rolling(365, min_periods=120).quantile(0.8)).astype(float),
    'vol-della-vol > percentile 50': (vov > vov.rolling(365, min_periods=120).quantile(0.5)).astype(float),
    'scala continua: min(1, 60% / DVOL)': (0.60 / dvb).clip(upper=1.0),
}
W0 = '2021-08-01'
for s in ('CR-TREND', 'CR-XSMOM'):
    base = S0[s].loc[W0:]; tb = three(base); print(f'{s} senza filtro (dal {W0}):  Sh {tb["sh_tot"]:.2f} | {tb["sh_sel"]:.2f} | {tb["sh_ver"]:.2f}   DD {100 * tb["dd_tot"]:.1f}%')
    for lab, m in filters.items():
        t = F.line(f'{s} x [{lab}]', apply(s, m).loc[W0:])
print('   nota: la scelta copre solo 2021-08 -> 2022-12 (17 mesi, mercato in discesa): un filtro "migliore" qui e\' quasi certamente rumore.')
F.save()
