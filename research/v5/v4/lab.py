"""Lab v4 - funzioni comuni. Tutti i numeri prodotti sono SIMULATI su dati storici reali, al netto dei costi dichiarati.
Convenzioni: scelta <= 2022-12-31, verifica >= 2023-01-01; Sharpe in ECCESSO del tasso a breve (RF di series.parquet);
la liquidita' su exchange crypto non rende nulla; i pesi decisi alla chiusura della barra t si eseguono a quel prezzo
(= apertura della barra t+1) e incassano dalla barra t+1; 'ritardo +1' = una barra in piu'."""
import sys, warnings, json, math, os
sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from gerva.data.sources import Store
from gerva.validation import metrics as M
ROOT = '/home/user/GERVA-Capital'; HERE = ROOT + '/research/v5/v4'
st = Store(ROOT + '/data_cache'); SPL = '2023-01-01'; SEL_END = '2022-12-31'
D = pd.read_parquet(ROOT + '/research/v5/series.parquet')
SLEEVES = ['CR-TREND', 'CR-XSMOM', 'EQ-MR', 'MA-TREND']
S0 = D[SLEEVES]; PORT = D['PORT'].dropna(); RF = D['RF']          # RF: tasso giornaliero (base 365)
IDX = D.index
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 500)

def get(key): return st.get(key)
def has(key): return st.has(key)

def stats(r, rf=None):
    """r: rendimenti giornalieri di calendario. Ritorna dict sharpe/cagr/vol/maxdd."""
    r = r.dropna()
    if len(r) < 60 or r.std() == 0: return dict(sh=np.nan, cagr=np.nan, vol=np.nan, dd=np.nan)
    rfx = (RF if rf is None else rf).reindex(r.index).ffill().fillna(0.0)
    eq = (1 + r).cumprod(); yrs = len(r) / 365
    return dict(sh=M.sharpe(r, rfx, 365), cagr=float(eq.iloc[-1]) ** (1 / yrs) - 1 if eq.iloc[-1] > 0 else -1.0,
                vol=float(r.std() * math.sqrt(365)), dd=float(M.drawdown(r).min()))

def three(r):
    r = r.dropna(); out = {}
    for lab, sl in (('tot', slice(None, None)), ('sel', slice(None, SEL_END)), ('ver', slice(SPL, None))):
        s = stats(r.loc[sl]); out.update({f'{k}_{lab}': v for k, v in s.items()})
    return out

def sh0(r):  # Sharpe senza sottrarre il tasso (strategie autofinanziate su margine)
    r = r.dropna(); return float(r.mean() / r.std() * math.sqrt(365)) if len(r) > 60 and r.std() > 0 else np.nan

def by_year(r):
    r = r.dropna(); rfx = RF.reindex(r.index).ffill().fillna(0)
    return {int(y): round(M.sharpe(x, rfx.loc[x.index], 365), 2) for y, x in r.groupby(r.index.year) if len(x) > 90 and x.std() > 0}

def corrs(r):
    x = r.reindex(IDX); m = lambda s: (1 + s.fillna(0)).resample('ME').prod() - 1
    ok = x.notna()
    out = {c: round(float(m(x[ok]).corr(m(S0[c][ok]))), 2) for c in SLEEVES}
    out['PORT'] = round(float(m(x[ok & PORT.reindex(IDX).notna()]).corr(m(PORT.reindex(IDX)[ok & PORT.reindex(IDX).notna()]))), 2)
    return out

class Fam:
    """Registro di una famiglia: prove (ogni variante valutata conta), candidati salvati, stampa."""
    def __init__(self, name):
        self.name = name; self.trials = {}; self.cand = {}
    def trial(self, label, r):
        """Registra una variante: Sharpe (eccesso) nel periodo di scelta. Ritorna il dict a tre periodi."""
        t = three(r); self.trials[label] = None if not np.isfinite(t.get('sh_sel', np.nan)) else round(t['sh_sel'], 3)
        return t
    def line(self, label, r, extra=''):
        t = self.trial(label, r)
        f = lambda k, p=False: ('%6.1f%%' % (100 * t[k])) if p else ('%5.2f' % t[k])
        print(f"{label[:62]:62s} Sh {f('sh_tot')} | {f('sh_sel')} | {f('sh_ver')}  CAGR {f('cagr_tot',1)} {f('cagr_sel',1)} {f('cagr_ver',1)}  vol {f('vol_tot',1)}  DD {f('dd_tot',1)} {f('dd_ver',1)} {extra}", flush=True)
        return t
    def keep(self, label, r):
        """Salva la serie tra i candidati (indice di calendario) e stampa correlazioni e Sharpe per anno."""
        r = r.reindex(IDX)
        self.cand[label] = r
        print(f"   >> CANDIDATO {label}: corr mensile {corrs(r)}  Sharpe/anno {by_year(r)}  Sharpe rf=0 {sh0(r):.2f}", flush=True)
    def save(self):
        if self.cand: pd.DataFrame(self.cand).to_parquet(f'{HERE}/cand_{self.name}.parquet')
        json.dump(self.trials, open(f'{HERE}/trials_{self.name}.json', 'w'), indent=0)
        v = [x for x in self.trials.values() if x is not None]
        print(f"\n[{self.name}] varianti provate: {len(self.trials)}  (Sharpe di scelta: media {np.mean(v):.2f}, dev.std {np.std(v):.2f}, max {np.max(v):.2f})")

def daily(x):
    """Somma per giorno di calendario rendimenti intraday (indice = apertura barra UTC)."""
    return x.groupby(x.index.normalize()).sum()

def hourly_panel(kind, coins, field='close'):
    out = {}
    for c in coins:
        k = f'v4_{kind}_1h_{c}USDT'
        if has(k): out[c] = get(k)[field]
    return pd.DataFrame(out)

def funding_daily(coins):
    """Somma del funding per giorno UTC. Il funding delle 00:00 del giorno D+1 e' attribuito al giorno D (lo incassa chi
    ha tenuto la posizione durante D)."""
    out = {}
    for c in coins:
        k = f'bn_fund_{c}USDT'
        if has(k):
            s = get(k).iloc[:, 0]; s.index = (s.index - pd.Timedelta(minutes=5)).normalize(); out[c] = s.groupby(level=0).sum()
    return pd.DataFrame(out)
PERP = ("BTC ETH SOL BNB XRP DOGE ADA LTC LINK AVAX DOT BCH ETC ATOM NEAR FIL UNI AAVE TRX XLM MATIC APT ARB OP SUI "
        "INJ SEI TIA WIF TON RUNE HBAR LUNA FTT EOS SAND").split()
