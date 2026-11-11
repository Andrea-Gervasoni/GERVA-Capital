"""A8 (statistical learning) - funzioni comuni. Tutto SIMULATO su dati storici reali.
Dati: Binance spot 5m (percorso dei prezzi, proxy dei perpetual come nel libro v4), funding reale Binance,
candele orarie con volume taker (v5_a8_*), DVOL Deribit, metriche OI Binance, Yahoo giornaliero, Fear&Greed.
Convenzione temporale: le feature della riga 'giorno i' usano SOLO dati fino alla chiusura del giorno i-1 (00:00 UTC);
il trade entra all'apertura della prima barra 5m del giorno i."""
import os; os.environ.setdefault("OMP_NUM_THREADS", "1")   # con piu thread HGB su dati piccoli rallenta di 100x
import sys, warnings; sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from gerva.data import Store
from gerva import ensemble as E
ROOT = '/home/user/GERVA-Capital'; HERE = ROOT + '/research/v5/v5/a8_ml'
st = Store(ROOT + '/data_cache')
COINS = ('BTC', 'ETH', 'SOL'); SPL = pd.Timestamp('2023-01-01')
FEE = 0.00045 + 0.0002; STOPSLIP = 0.0005; MM = 0.005; RATIO = 0.6
SIG = ['trend10', 'trend30', 'trend60', 'trend120', 'ma100', 'ma200', 'brk20', 'lowvol', 'ibs_low', 'mom7', 'btc_ma100', 'fund_ok']

def _cut(d, cut):
    return d if cut is None else d[d.index < cut]

class Data:
    """Carica tutto, eventualmente troncato a 'cut' (per la verifica di troncamento)."""
    def __init__(self, cut=None):
        self.cut = cut; self.B = {}; self.D = {}; self.H = {}; self.HP = {}; self.F = {}; self.MET = {}
        for c in COINS:
            b = _cut(st.get(f'bn_spot_5m_{c}USDT'), cut); g = b.groupby(b.index.normalize())
            self.B[c] = b
            self.D[c] = pd.DataFrame(dict(open=g['open'].first(), high=g['high'].max(), low=g['low'].min(), close=g['close'].last(), qv=g['quote_volume'].sum()))
            self.H[c] = _cut(st.get(f'v5_a8_spot_1h_{c}'), cut); self.HP[c] = _cut(st.get(f'v5_a8_um_1h_{c}'), cut)
            f = _cut(st.get(f'bn_fund_{c}USDT').iloc[:, 0], cut); self.F[c] = f.groupby(f.index.normalize()).sum()
            self.MET[c] = _cut(st.get(f'v4_metrics_1h_{c}'), cut)
        self.dvol = {k: _cut(st.get(f'v4_dvol_{k}')['close'], cut) for k in ('BTC', 'ETH')}
        self.y = {k: _cut(st.get(f'yahoo_1d_{k}'), cut) for k in ('SPY', 'QQQ', '^VIX', 'UUP', 'GLD')}
        self.fng = _cut(st.get('v4_fng').iloc[:, 0], cut)

def features(dt: Data, c: str) -> pd.DataFrame:
    """Feature giornaliere del coin c. Riga t = informazione fino alla chiusura di t; in fondo si fa shift(1)."""
    d = dt.D[c]; cl = d['close']; idx = d.index; lr = np.log(cl).diff(); btc = dt.D['BTC']['close']
    S = E.crypto_signals(d, btc, dt.F[c]); X = S[SIG].copy(); X['score'] = E.conviction(S, 'crypto')['score']
    for h in (1, 3, 7, 14, 30, 60, 120): X[f'ret{h}'] = np.log(cl / cl.shift(h))
    v20 = lr.rolling(20).std(); X['vol7'] = lr.rolling(7).std(); X['vol20'] = v20; X['vol60'] = lr.rolling(60).std()
    X['volratio'] = X['vol7'] / X['vol60']; X['z7'] = X['ret7'] / (v20 * np.sqrt(7)); X['z30'] = X['ret30'] / (X['vol60'] * np.sqrt(30))
    atr = ((d['high'] - d['low']) / cl).rolling(14).mean(); X['atr14'] = atr
    X['atr_pct'] = atr.rolling(365, min_periods=120).rank(pct=True); X['vol_pct'] = v20.rolling(365, min_periods=120).rank(pct=True)
    X['ibs'] = (cl - d['low']) / (d['high'] - d['low']).replace(0, np.nan)
    X['dd20'] = cl / cl.rolling(20).max() - 1; X['dd90'] = cl / cl.rolling(90).max() - 1; X['up90'] = cl / cl.rolling(90).min() - 1
    X['ma200d'] = cl / cl.rolling(200).mean() - 1; X['ma20d'] = cl / cl.rolling(20).mean() - 1
    X['rng1'] = (d['high'] - d['low']) / cl / atr
    # volume e sbilanciamento taker (spot, orario -> giorno)
    h = dt.H[c]; g = h.groupby(h.index.normalize()); qv = g['quote_volume'].sum().reindex(idx); tk = g['taker_quote'].sum().reindex(idx)
    lq = np.log(qv.replace(0, np.nan)); X['vol_z'] = (lq - lq.rolling(30).mean()) / lq.rolling(30).std()
    X['vol_tr'] = lq.rolling(7).mean() - lq.rolling(60).mean()
    X['taker1'] = 2 * tk / qv - 1; X['taker7'] = 2 * tk.rolling(7).sum() / qv.rolling(7).sum() - 1
    hr = np.log(h['close']).diff(); X['rv24'] = (hr ** 2).groupby(h.index.normalize()).sum().reindex(idx) ** 0.5 / v20
    last6 = np.log(h['close'] / h['close'].shift(6)); X['ret_6h'] = last6[last6.index.hour == 23].rename(lambda t: t.normalize()).reindex(idx)
    # perp: base, funding, volume relativo, taker perp
    hp = dt.HP[c]; gp = hp.groupby(hp.index.normalize())
    bas = (hp['close'] / h['close'].reindex(hp.index) - 1); X['basis'] = bas.groupby(bas.index.normalize()).mean().reindex(idx) * 1e4
    X['basis7'] = X['basis'].rolling(7).mean()
    X['perp_taker1'] = (2 * gp['taker_quote'].sum() / gp['quote_volume'].sum() - 1).reindex(idx)
    X['perp_spot_vol'] = np.log(gp['quote_volume'].sum().reindex(idx) / qv)
    f = dt.F[c].reindex(idx); X['fund1'] = f * 365; X['fund7'] = f.rolling(7).mean() * 365; X['fund30'] = f.rolling(30).mean() * 365
    # open interest (dal 2021-12)
    m = dt.MET[c]; oi = m['sum_open_interest'].groupby(m.index.normalize()).last().reindex(idx).replace(0, np.nan)   # 0 = buco nei dati
    X['oi1'] = np.log(oi / oi.shift(1)); X['oi7'] = np.log(oi / oi.shift(7))
    X['top_ls'] = m['sum_toptrader_long_short_ratio'].groupby(m.index.normalize()).last().reindex(idx)
    # volatilita' implicita
    dv = dt.dvol['ETH' if c == 'ETH' else 'BTC'].reindex(idx); X['dvol'] = dv; X['dvol_ch7'] = np.log(dv / dv.shift(7))
    X['vrp'] = dv / 100 - v20 * np.sqrt(365)
    # stato cross-asset
    bl = np.log(btc).diff().reindex(idx)
    X['btc_ret7'] = np.log(btc / btc.shift(7)).reindex(idx); X['btc_ret30'] = np.log(btc / btc.shift(30)).reindex(idx)
    X['btc_vol20'] = bl.rolling(20).std(); X['rel30'] = X['ret30'] - X['btc_ret30']; X['corr_btc30'] = lr.rolling(30).corr(bl)
    eth = dt.D['ETH']['close']; X['ethbtc30'] = np.log((eth / btc) / (eth / btc).shift(30)).reindex(idx)
    for k, nm in (('SPY', 'spy'), ('UUP', 'usd'), ('GLD', 'gld')):
        a = dt.y[k]['adj']; X[f'{nm}_ret5'] = np.log(a / a.shift(5)).reindex(idx, method='ffill'); X[f'{nm}_ret20'] = np.log(a / a.shift(20)).reindex(idx, method='ffill')
    vx = dt.y['^VIX']['close']; X['vix'] = vx.reindex(idx, method='ffill'); X['vix_ch5'] = np.log(vx / vx.shift(5)).reindex(idx, method='ffill')
    X['fng'] = dt.fng.shift(1).reindex(idx, method='ffill')     # il valore datato t esce a inizio giornata t: qui un giorno in piu' di cautela
    X = X.replace([np.inf, -np.inf], np.nan).shift(1)                                              # nota la sera prima
    X['dow'] = idx.dayofweek; X['dom'] = idx.day; X['coin_id'] = COINS.index(c)
    X['atr_stop'] = ((d['high'] - d['low']) / cl).rolling(14).mean().shift(1)   # come nel libro v4
    X['tier'] = E.conviction(S, 'crypto')['tier'].shift(1)
    return X

FEATS_ALL = None
def feat_names(X): return [k for k in X.columns if k not in ('atr_stop', 'tier', 'score')]

def levmax(s, cap=50): return min(cap, 1 / (s / RATIO + MM))

class Sim:
    """Simulatore sul percorso a 5m, identico nella logica a research/v5/v4/leva_trade_isolato.py (verificato in 01)."""
    def __init__(self, dt: Data, c):
        b = dt.B[c]; d = dt.D[c]; self.c = c
        self.op = b['open'].values; self.hi = b['high'].values; self.lo = b['low'].values
        self.days = d.index.values; dn = b.index.normalize().values
        self.start = np.searchsorted(dn, self.days); self.n = len(self.days)
        f = dt.F[c]; self.fd = f.reindex(d.index).fillna(0.0001 * 3).values
    def trade(self, i, side, sd, jend, trail=2.0, delay=0, cm=1.0):
        """Entra all'apertura del giorno i (+delay barre 5m); esce a stop / liquidazione / apertura del giorno jend."""
        a = self.start[i] + delay; z = self.start[jend]; op, hi, lo = self.op[a:z], self.hi[a:z], self.lo[a:z]
        p0 = op[0]; L = levmax(sd); liq = p0 * (1 - side * (1 / L - MM))
        if side == 1:
            best = np.maximum(p0, np.concatenate(([p0], np.maximum.accumulate(hi)[:-1])))
            stop = np.maximum(p0 * (1 - sd), best * (1 - trail * sd)) if trail else np.full(len(op), p0 * (1 - sd))
            hit = lo <= stop
        else:
            best = np.minimum(p0, np.concatenate(([p0], np.minimum.accumulate(lo)[:-1])))
            stop = np.minimum(p0 * (1 + sd), best * (1 + trail * sd)) if trail else np.full(len(op), p0 * (1 + sd))
            hit = hi >= stop
        if hit.any():
            k = int(np.argmax(hit)); px = min(stop[k], op[k]) if side == 1 else max(stop[k], op[k]); px *= (1 - side * STOPSLIP * cm)
            why = 'stop'
            if side * (px - liq) <= 0: px = liq; why = 'liq'
            j = int(np.searchsorted(self.start, a + k, side='right') - 1)
        else:
            px = self.op[z]; why = 'tempo'; j = jend
        nd = max(j - i, 1); fu = float(self.fd[i:i + nd].sum()) * side
        net = max(side * (px / p0 - 1) - 2 * FEE * cm - fu, -1 / L)
        return dict(coin=self.c, entry=self.days[i], exit=self.days[j], side=side, s=sd, L=L, R=net / sd, ret=net, why=why, days=nd, j=j)

def block_t(x, key):
    """t-statistica della media con errori raggruppati per blocco (mese): robusta alla sovrapposizione delle etichette."""
    x = np.asarray(x, float); g = pd.Series(x).groupby(np.asarray(key)); s = g.sum(); n = len(x); m = x.mean()
    e = s - g.size() * m; G = len(s)
    se = np.sqrt((e ** 2).sum() * G / max(G - 1, 1)) / n
    return m / se if se > 0 else np.nan

def rstats(R, yrs=None):
    R = np.asarray(R, float); n = len(R)
    if n < 3: return dict(n=n, R=np.nan, sd=np.nan, ir=np.nan, t=np.nan, hit=np.nan)
    return dict(n=n, R=R.mean(), sd=R.std(ddof=1), ir=R.mean() / R.std(ddof=1), t=R.mean() / R.std(ddof=1) * np.sqrt(n), hit=(R > 0).mean())
