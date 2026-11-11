"""A10 - funzioni comuni. Ricostruisce il portafoglio a 6 strategie (identico a portafogli.parquet), l'uso reale della cassa
e il libro dei trade valutato OGNI GIORNO a mercato (non sul giorno di uscita). SIMULATO."""
import sys, pickle, math, warnings; sys.path.insert(0, '/home/user/GERVA-Capital'); sys.path.insert(0, '/home/user/GERVA-Capital/research/v5/v4'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from gerva.portfolio import risk_parity, combine, vol_target_leverage
ROOT = '/home/user/GERVA-Capital'; HERE = ROOT + '/research/v5/v5/a10_sistema'
SEL_END = '2022-12-31'; SPL = '2023-01-01'
B = pickle.load(open(HERE + '/base.pkl', 'rb'))
C = pd.read_parquet(ROOT + '/research/v5/v4/candidates.parquet'); P = pd.read_parquet(ROOT + '/research/v5/v4/portafogli.parquet')
S0 = B['S']; RF = B['rf'].reindex(S0.index).ffill().fillna(0.0)
DIP = C['DIP-24h (compra il crollo, perp)'].rename('DIP'); CAR = C['CARRY-XS-HL (incollato)'].rename('CARRY')
S5 = pd.concat([S0, DIP], axis=1)                      # sleeve a rischio di mercato (NaN prima che DIP esista)
SLV = ['CR-TREND', 'CR-XSMOM', 'EQ-MR', 'MA-TREND', 'DIP', 'CARRY']
def with_carry(a, wc=0.20):
    has = CAR.reindex(a.index).notna().astype(float); a2 = a.mul(1 - wc * has, axis=0); a2['CARRY'] = wc * has; return a2
A6 = with_carry(risk_parity(S5)); S6 = pd.concat([S5, CAR], axis=1).reindex(A6.index)
NEW = (A6 * S6.fillna(0.0)).sum(axis=1)
IDX = NEW.index; rf = RF.reindex(IDX)
# esposizione lorda di ogni sleeve sul proprio capitale; DIP = 0,07 medio (04_liquidazioni_oi.out), CARRY usa tutto il capitale (spot 75% + margine 25%)
G6 = B['G'].reindex(IDX).copy(); G6['DIP'] = 0.07; G6['CARRY'] = 1.0
# quota di CASSA assorbita da 1 di esposizione: spot/ETF 1; CFD su indice 5% (margine ESMA 20x); perp DIP 20% (5x)
CASHUSE = pd.Series({'CR-TREND': 1.0, 'CR-XSMOM': 1.0, 'EQ-MR': 0.05, 'MA-TREND': 1.0, 'DIP': 0.20, 'CARRY': 1.0})
def cash_used(a=A6, lev=1.0): return (a * G6.reindex(a.index) * CASHUSE).sum(axis=1) * lev

def ann(y, per=365):
    y = y.dropna(); e = y - rf.reindex(y.index).fillna(0.0)
    if len(y) < 60 or y.std() == 0: return dict(sh=np.nan, cagr=np.nan, vol=np.nan, dd=np.nan)
    eq = (1 + y).cumprod()
    return dict(sh=e.mean() / y.std() * math.sqrt(per), cagr=eq.iloc[-1] ** (per / len(y)) - 1, vol=y.std() * math.sqrt(per), dd=(eq / eq.cummax() - 1).min())
def mm(x): return (1 + x).resample('ME').prod() - 1
MRF = mm(rf)
def msh(x):
    m = mm(x.dropna()); e = m - MRF.reindex(m.index); return e.mean() / e.std() * math.sqrt(12) if len(m) > 6 else np.nan
def three(y, monthly=False):
    out = {}
    for lab, sl in (('tot', slice(None, None)), ('sel', slice(None, SEL_END)), ('ver', slice(SPL, None))):
        s = ann(y.loc[sl]); 
        if monthly: s['sh'] = msh(y.loc[sl])
        out.update({f'{k}_{lab}': v for k, v in s.items()})
    return out
def line(lab, y, monthly=False, extra=''):
    t = three(y, monthly)
    print(f"{lab[:66]:66s} Sh {t['sh_tot']:5.2f} | {t['sh_sel']:5.2f} | {t['sh_ver']:5.2f}  CAGR {100*t['cagr_tot']:6.1f}% {100*t['cagr_sel']:6.1f}% {100*t['cagr_ver']:6.1f}%  vol {100*t['vol_tot']:5.1f}%  DD {100*t['dd_tot']:6.1f}% {100*t['dd_ver']:6.1f}% {extra}", flush=True)
    return t
TRIALS = {}
def trial(fam, lab, y, monthly=False, extra=''):
    t = line(lab, y, monthly, extra); TRIALS.setdefault(fam, {})[lab] = None if not np.isfinite(t['sh_sel']) else round(float(t['sh_sel']), 3); return t

# ---- libro dei trade valutato a mercato ogni giorno ----------------------------------------------------------------
_TB = {}
def trade_tables(key=('atr1.0', ('alta',), 2.0, 'long')):
    """Per ogni trade: percorso giornaliero del rendimento sul CONTROVALORE (chiusure giornaliere), con il totale = rendimento netto."""
    if key in _TB: return _TB[key]
    import leva_trade_isolato as TR
    ALL = pickle.load(open(ROOT + '/research/v5/v4/_cache/trades.pkl', 'rb')); X = ALL[key].copy().reset_index(drop=True)
    X['score'] = [TR.CONV[c]['score'].get(pd.Timestamp(d)) for c, d in zip(X.coin, X.entry)]
    paths = []
    for _, t in X.iterrows():
        d = TR.D[t.coin]; days = pd.date_range(t.entry, t.exit, freq='D'); cl = d['close'].reindex(days).values; p0 = d['open'].loc[t.entry]
        cum = cl / p0 - 1 - 0.00065                       # costo di ingresso subito
        cum = np.maximum(cum, -1 / t.L)                   # margine isolato
        cum[-1] = t.ret                                   # il giorno di uscita si chiude al rendimento netto vero
        if len(days) == 1: inc = np.array([t.ret])
        else: inc = np.diff(np.concatenate([[0.0], cum]))
        paths.append(pd.Series(inc, index=days))
    _TB[key] = (X, paths); return _TB[key]
def trade_book(rc=0.01, re=0.02, key=('atr1.0', ('alta',), 2.0, 'long'), mtm=True, coins=None, lev_cap=None, scale=None):
    """Rendimento giornaliero del libro in FRAZIONE DEL PATRIMONIO (sovrapposizione additiva, come 09_fondo.py).
    mtm=False riproduce 09_fondo.py (tutto il P&L sul giorno di uscita). Ritorna (serie, margine, controvalore, rischio aperto)."""
    X, paths = trade_tables(key)
    r = pd.Series(0.0, index=IDX); mg = pd.Series(0.0, index=IDX); no = pd.Series(0.0, index=IDX); rk = pd.Series(0.0, index=IDX)
    for (i, t), p in zip(X.iterrows(), paths):
        if coins is not None and t.coin not in coins: continue
        risk = re if (t.score is not None and t.score > 0.75) else rc
        if scale is not None: risk = risk * float(scale.get(pd.Timestamp(t.entry), 1.0))
        notional = risk / t.s; L = t.L if lev_cap is None else min(t.L, lev_cap)
        if mtm: r = r.add(p * notional, fill_value=0.0)
        else: r.loc[pd.Timestamp(t.exit)] += risk * t.R if pd.Timestamp(t.exit) in r.index else 0.0
        days = p.index.intersection(IDX); mg.loc[days] += notional / L; no.loc[days] += notional; rk.loc[days] += risk
    return r.reindex(IDX).fillna(0.0), mg, no, rk
def lev09(x, L): return L * x - (L - 1) * (rf.reindex(x.index) + 0.015 / 365)
