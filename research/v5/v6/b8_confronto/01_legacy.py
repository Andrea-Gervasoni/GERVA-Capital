"""B8 - 01. Riesprime il sistema ORIGINALE (GERVA-Q v3 come descritto in quantlab/gervaq4.py e quantlab/crypto4.py:
meta' libro azionario S1-S4 a pesi uguali, meta' sleeve crypto H1+H2) e lo misura con le STESSE convenzioni del
nuovo fondo: motore gerva.backtest.daily.run, costi per sede di gerva/strategies/book.py (ETF e azioni 10 pb, crypto 30 pb),
Sharpe in eccesso del tasso, scelta <= 2022 / verifica >= 2023, costi x2, una barra di ritardo. SIMULATO.
Uso: /tmp/gv/bin/python 01_legacy.py > 01_legacy.out"""
import sys, math, warnings; sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from gerva.backtest.daily import run, Costs
from gerva.data.sources import Store
from quantlab import gervaq4 as G4, crypto4 as C4, backtest as QBT, stats as QS
ROOT = '/home/user/GERVA-Capital'; HERE = ROOT + '/research/v5/v6/b8_confronto'
st = Store(ROOT + '/data_cache'); SEL_END, SPL = '2022-12-31', '2023-01-01'
ETF_FEE, STOCK_FEE, CRYPTO_FEE, SPREAD = 0.0010, 0.0010, 0.0030, 0.015

def ykey(s):
    for p in ('yahoo_1d_', 'v6_b8_y_', 'v6_b3_y_', 'v5_yahoo_1d_'):
        if st.has(p + s): return p + s
    raise KeyError(s)
EQ_SYMS = G4.TREND_SET + G4.SECTORS + G4.STOCKS + ['^VIX', '^IRX']
close = pd.DataFrame({s: st.get(ykey(s))['adj'] for s in EQ_SYMS}).loc['2004':'2026-10-31']
close = close[close['SPY'].notna()]
cc = pd.DataFrame({c: st.get(f'bn_spot_1d_{c}USDT')['close'] for c in C4.COINS}).loc[:'2026-10-31']
cc.index = pd.to_datetime(cc.index).normalize()
SER = pd.read_parquet(ROOT + '/research/v5/series.parquet'); RF = SER['RF']            # tasso per giorno di calendario
A10 = pd.read_parquet(ROOT + '/research/v5/v5/a10_sistema/returns.parquet'); IDX = A10.index
rf_bd = (close['^IRX'] / 100 / 252).ffill().fillna(0.0)

# ---- pesi (definizioni del repository, non toccate) ---------------------------------------------------------------
def eq_weights(cl):
    v = G4.Variant('v3_riferimento'); sl = G4.sleeves(cl, v, G4.STOCKS); return G4.combine(cl, sl, 'equal', 0.0008), sl
def cr_weights(c): return C4.weights(c, C4.CVariant('v3_crypto'))
W_eq, SL = eq_weights(close); W_cr = cr_weights(cc)

# ---- controllo 1: la riespressione riproduce i numeri che STATUS.md riporta? (motore e costi di quantlab, Sharpe grezzo)
r_q = QBT.run(W_eq, close[W_eq.columns], cost_rate=0.0008, band=0.02).returns.iloc[300:]
split = r_q.index[-1] - pd.DateOffset(years=2); p = QS.performance(r_q[r_q.index <= split].values)
print(f"[controllo] libro azionario v3, motore quantlab, periodo di scelta del banco (fino a {split.date()}): Sharpe {p['Sharpe']:.2f} CAGR {p['CAGR']:.1%} vol {p['Vol']:.1%} MaxDD {p['MaxDD']:.1%}  | STATUS.md: 0,69 / 5,7% / 8,6% / -15,9% (dati al 5/11/2026)")
# ---- controllo 2: nessun look-ahead (troncamento) -------------------------------------------------------------------
for cut in ('2019-06-28', '2020-03-20', '2024-08-05'):
    a = eq_weights(close.loc[:cut])[0].iloc[-1]; b = W_eq.loc[cut].reindex(a.index)
    c1 = cr_weights(cc.loc[:cut]).iloc[-1]; c2 = W_cr.loc[cut].reindex(c1.index)
    print(f"[troncamento {cut}] scarto massimo pesi azionari {float((a - b).abs().max()):.2e}, crypto {float((c1 - c2).abs().max()):.2e}")

# ---- rendimenti con il motore del nuovo fondo ----------------------------------------------------------------------
def sleeves(fee=1.0, lag=1):
    Re = close[W_eq.columns].pct_change(fill_method=None)
    tc = {c: (STOCK_FEE if c in G4.STOCKS else ETF_FEE) * fee for c in W_eq.columns}
    e = run(W_eq, Re, 0.0, Costs(trade=tc, cash_haircut=1.0), lag=lag, periods=252, band=0.02)
    Rc = cc[W_cr.columns].pct_change(fill_method=None)
    c = run(W_cr, Rc, 0.0, Costs(trade=CRYPTO_FEE * fee, cash_haircut=1.0), lag=lag, periods=365, band=0.05)
    return e, c
def fund(fee=1.0, lag=1, lever=False, cash_yield=True, k=2.5, cap=1.5):
    """Conto intero: 50% libro azionario + 50% crypto sul NAV; scala = min(k, cap / esposizione) (v3.3, 6/11) nota il giorno prima."""
    e, c = sleeves(fee, lag); idx = c.ret.index
    re = e.ret.reindex(idx).fillna(0.0); ge = e.gross.reindex(idx).ffill().fillna(0.0)
    base = 0.5 * re + 0.5 * c.ret; expo = 0.5 * ge + 0.5 * c.gross
    sc = (np.minimum(k, cap / expo.where(expo > 0)).fillna(k) if lever else pd.Series(1.0, index=idx)).shift(1).fillna(1.0)
    ex_prev = expo.shift(1).fillna(0.0); tot = sc * ex_prev; rf = RF.reindex(idx).ffill().fillna(0.0)
    carry = -(tot - 1).clip(lower=0) * (rf + SPREAD / 365)
    if cash_yield: carry = carry + (1 - tot).clip(lower=0) * (rf - 0.005 / 365).clip(lower=0)
    extra = sc.diff().abs().fillna(0.0) * ex_prev * 0.0015 * fee           # costo del cambio di scala (media ETF/crypto)
    return (sc * base + carry - extra), tot, e, c

def ann(y, per=365):
    y = y.dropna(); ex = y - RF.reindex(y.index).fillna(0.0); eq = (1 + y).cumprod(); m = (1 + y).resample('ME').prod() - 1
    return dict(sh=ex.mean() / y.std() * math.sqrt(per), cagr=eq.iloc[-1] ** (per / len(y)) - 1, vol=y.std() * math.sqrt(per),
                dd=(eq / eq.cummax() - 1).min(), wm=m.min(), mm=m.median())
def line(lab, y):
    t, s, v = ann(y), ann(y.loc[:SEL_END]), ann(y.loc[SPL:])
    print(f"{lab[:58]:58s} Sh {t['sh']:5.2f} | {s['sh']:5.2f} | {v['sh']:5.2f}  CAGR {t['cagr']:6.1%} | {s['cagr']:6.1%} | {v['cagr']:6.1%}  vol {t['vol']:5.1%}  DD {t['dd']:6.1%} | {v['dd']:6.1%}  mese peggiore {t['wm']:6.1%}", flush=True)
    return t

OUT = {}
r0, t0, e0, c0 = fund(); r1, t1, _, _ = fund(lever=True)
OUT['LEG_azionario_v3'] = e0.ret.reindex(IDX).fillna(0.0) + (1 - e0.gross.reindex(IDX).ffill()).clip(lower=0) * (RF.reindex(IDX) - 0.005 / 365).clip(lower=0)
OUT['LEG_crypto_v3'] = c0.ret.reindex(IDX) + (1 - c0.gross.reindex(IDX)).clip(lower=0) * (RF.reindex(IDX) - 0.005 / 365).clip(lower=0)
OUT['LEG_v3_1x'] = r0.reindex(IDX); OUT['LEG_v33_leva15'] = r1.reindex(IDX)
OUT['LEG_v3_1x_cassa_a_zero'] = fund(cash_yield=False)[0].reindex(IDX)
print(f"\nesposizione media (2018-04 -> 2026-10): libro azionario {e0.gross.reindex(IDX).ffill().mean():.0%} del suo capitale, crypto {c0.gross.reindex(IDX).mean():.0%}; conto 1x {t0.reindex(IDX).mean():.0%}, conto v3.3 {t1.reindex(IDX).mean():.0%} (massimo {t1.reindex(IDX).max():.0%})")
print(f"turnover annuo: azionario {e0.turnover.loc['2018-04':].mean()*252:.1f}x, crypto {c0.turnover.loc['2018-04':].mean()*365:.1f}x; costi annui {e0.cost.loc['2018-04':].mean()*252:.2%} / {c0.cost.loc['2018-04':].mean()*365:.2%}")
print("\n=== PERIODO COMUNE 2018-04-01 -> 2026-10-31, giorni di calendario; valori: tutto | scelta | verifica ===")
print("--- sistema originale (riespresso; SIMULATO) ---")
for k in OUT: line(k, OUT[k])
print("--- robustezza del sistema originale ---")
for lab, kw in (('costi x2', dict(fee=2.0)), ('ritardo +1 barra', dict(lag=2)), ('costi x2 + ritardo', dict(fee=2.0, lag=2))):
    line(f'LEG_v3_1x  {lab}', fund(**kw)[0].reindex(IDX)); line(f'LEG_v33_leva15  {lab}', fund(lever=True, **kw)[0].reindex(IDX))
OUT['LEG_v33_leva15_ritardo'] = fund(lever=True, lag=2)[0].reindex(IDX)
print("--- nuovo fondo (serie esistenti) ---")
NEW = {'B_cassa_in_tbill': A10['B_cassa_in_tbill'], 'B2_debito_reale': A10['B2_debito_reale'], 'C1_mtm_limiti': A10['C1_mtm_limiti'],
       'C3_mtm_limiti_debito_reale': A10['C3_mtm_limiti_debito_reale'], 'C1_motore_di_rischio_attuale': A10['C1_motore_di_rischio_attuale']}
for k, y in NEW.items(): line('NUOVO ' + k, y)
for k in ('CR-TREND', 'CR-XSMOM', 'EQ-MR', 'MA-TREND'): line('sleeve ' + k, SER[k].reindex(IDX))
print("--- riferimenti passivi ---")
spy = close['SPY'].pct_change().reindex(IDX).fillna(0.0); btc = cc['BTC'].pct_change().reindex(IDX)
line('SPY (compra e tieni, USD)', spy); line('BTC (compra e tieni, USD)', btc); line('60% SPY + 40% IEF', (0.6 * close['SPY'].pct_change() + 0.4 * close['IEF'].pct_change()).reindex(IDX).fillna(0.0))
D = pd.DataFrame({**OUT, **NEW, 'SPY': spy, 'BTC': btc})
print("\n=== per anno (rendimento composto) ===")
Y = (1 + D[['LEG_v3_1x', 'LEG_v33_leva15', 'B_cassa_in_tbill', 'B2_debito_reale', 'C1_mtm_limiti', 'C3_mtm_limiti_debito_reale', 'SPY']]).groupby(D.index.year).prod() - 1
print((Y * 100).round(1).to_string())
print("\n=== a pari volatilita' (nuovo fondo riscalato alla volatilita' del sistema originale, debito al tasso + 1,5%) ===")
rf = RF.reindex(IDX).fillna(0.0)
def at_vol(y, target):
    L = target / (y.std() * math.sqrt(365)); return L * y - max(L - 1, 0) * (rf + SPREAD / 365) + max(1 - L, 0) * rf, L
for leg in ('LEG_v3_1x', 'LEG_v33_leva15'):
    tv = OUT[leg].std() * math.sqrt(365)
    for k in ('B_cassa_in_tbill', 'C1_mtm_limiti'):
        y, L = at_vol(NEW[k], tv); line(f'{k} x{L:.2f} (vol {tv:.1%} = {leg})', y)
print("\n=== correlazioni giornaliere / mensili con il sistema originale ===")
M = (1 + D).resample('ME').prod() - 1
for leg in ('LEG_v3_1x', 'LEG_v33_leva15'):
    print(leg, ' '.join(f"{k}: {D[leg].corr(D[k]):.2f}/{M[leg].corr(M[k]):.2f}" for k in list(NEW) + ['SPY', 'BTC']))
print("\n=== beta giornaliero su SPY e BTC (regressione a due fattori, 2018-04 -> 2026-10 e 2025-11 -> 2026-10) ===")
for per in (slice(None, None), slice('2025-11-01', None)):
    X = np.column_stack([np.ones(len(D.loc[per])), D['SPY'].loc[per], D['BTC'].loc[per]])
    for k in ('LEG_v3_1x', 'LEG_v33_leva15', 'B_cassa_in_tbill', 'C1_mtm_limiti'):
        b = np.linalg.lstsq(X, D[k].loc[per].values, rcond=None)[0]; print(f"  {k:28s} beta SPY {b[1]:.2f}  beta BTC {b[2]:.2f}  vol {D[k].loc[per].std()*math.sqrt(365):.1%}")
D.to_parquet(HERE + '/returns.parquet')
last_e = (0.5 * W_eq.iloc[-1]); last_c = 0.5 * W_cr.iloc[-1]
print("\npesi del modello riespresso al 31/10/2026 (frazione del NAV, prima della scala):")
print('  azionario:', {k: round(float(v), 3) for k, v in last_e[last_e > 0.002].sort_values(ascending=False).items()})
print('  crypto   :', {k: round(float(v), 3) for k, v in last_c[last_c > 0.002].sort_values(ascending=False).items()})
print('prove: 2 profili x 4 (base, costi x2, ritardo, entrambi) + 1 (cassa a zero) = 9, nessuna scelta di parametri')
