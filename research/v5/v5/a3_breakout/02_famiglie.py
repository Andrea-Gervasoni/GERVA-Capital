"""A3/2 - squeeze, opening range, conferma volume/taker, falsa rottura, accensione di momentum. SIMULATO. Griglie su tutti i 10 perp;
la scelta si fa SOLO sulle colonne *_sel (<=2022)."""
from lab import *
import sys
which = sys.argv[1:] or ['squeeze', 'orb', 'vol', 'fade', 'ign']
F = {}
def A(c, b, rule):
    k = (c, rule)
    if k not in F:
        a = agg(b, rule) if rule != '5min' else b.rename(columns={'quote_volume': 'qv', 'taker_quote': 'tq'})[['open', 'high', 'low', 'close', 'qv', 'tq']].copy()
        a['atr'] = atr(a, 14); F[k] = a
    return F[k]
def hv(c, b):
    """vol oraria: dev.std dei rendimenti 5m sulle ultime 288 barre x sqrt(12)."""
    k = (c, 'hv')
    if k not in F: F[k] = (np.log(b['close']).diff().rolling(288).std() * np.sqrt(12)).values
    return F[k]

# ---------- 1. squeeze -> rottura ----------
def squeeze(rule, mode, k, nmin=6):
    def fn(c, b):
        a = A(c, b, rule); m = a['close'].rolling(20).mean(); sd = a['close'].rolling(20).std(); a20 = atr(a, 20)
        if mode == 'bbkc':
            sq = ((m + 2 * sd) < (m + 1.5 * a20)) & ((m - 2 * sd) > (m - 1.5 * a20))
        else:   # ATR in percentile basso
            ap = (a['atr'] / a['close']); sq = ap.rolling(500).rank(pct=True) < 0.2
        was = sq.shift(1).rolling(nmin).sum() >= nmin          # squeeze nelle nmin barre precedenti
        hh = a['high'].rolling(20).max().shift(1); ll = a['low'].rolling(20).min().shift(1)
        s = pd.Series(0, index=a.index, dtype='int8'); s[was & (a['close'] > hh)] = 1; s[was & (a['close'] < ll)] = -1
        return to5(s, b).fillna(0).astype('int8').values, to5(a['close'] - s * k * a['atr'], b).values
    return fn

# ---------- 2. opening range ----------
def orb(sess, mins, stopmode, hold_h, side=0, volf=None):
    def fn(c, b):
        ix = b.index
        if sess == 'utc0': op = ix.normalize()
        elif sess == 'eu':   # 08:00 Londra
            loc = ix.tz_localize('UTC').tz_convert('Europe/London'); op = (loc.normalize() + pd.Timedelta('8h')).tz_convert('UTC').tz_localize(None)
        else:                # 09:30 New York
            loc = ix.tz_localize('UTC').tz_convert('America/New_York'); op = (loc.normalize() + pd.Timedelta('9h30min')).tz_convert('UTC').tz_localize(None)
        el = (ix - op) / pd.Timedelta('5min'); el = np.asarray(el, float)       # barre trascorse dall'apertura (negativo = prima)
        nb = mins // 5; inr = (el >= 0) & (el < nb)
        sid = pd.Series(np.asarray(op.asi8)); hi = b['high'].values; lo = b['low'].values; cl = b['close'].values
        rh = pd.Series(np.where(inr, hi, np.nan)).groupby(sid.values).transform('max').values
        rl = pd.Series(np.where(inr, lo, np.nan)).groupby(sid.values).transform('min').values
        # NB: rh/rl usano solo le barre del range; sono usati soltanto DOPO la fine del range (el>=nb): nessun look-ahead
        live = (el >= nb) & (el < hold_h * 12 - 1)
        up = live & (cl > rh); dn = live & (cl < rl)
        s = np.zeros(len(b), 'int8'); s[up] = 1; s[dn] = -1
        # un solo trade per sessione: solo il primo segnale
        first = pd.Series(s != 0).groupby(sid.values).cumsum().values
        s[(first != 1) | (pd.Series(s).shift(1).fillna(0).values != 0) & (first != 1)] = 0
        s[~((first == 1) & (s != 0))] = 0
        if side: s[s != side] = 0
        if volf is not None:
            q = b['quote_volume']; rv = (q / q.rolling(288).median()).values; s[rv < volf] = 0
        mid = (rh + rl) / 2
        spx = np.where(s == 1, rl if stopmode == 'opp' else mid, rh if stopmode == 'opp' else mid)
        tex = np.arange(len(b)) + (hold_h * 12 - 1 - el).astype(np.int64)
        return s, spx, tex
    return fn

# ---------- 3. rottura a 5m con conferma di volume / taker ----------
def volbrk(N, volq, tk, k):
    def fn(c, b):
        hh = b['high'].rolling(N).max().shift(1); ll = b['low'].rolling(N).min().shift(1); cl = b['close']
        rv = b['quote_volume'] / b['quote_volume'].rolling(288).median()
        share = (b['taker_quote'] / b['quote_volume'].replace(0, np.nan)).fillna(0.5)
        up = (cl > hh); dn = (cl < ll)
        if volq: up &= rv > volq; dn &= rv > volq
        if tk: up &= share > tk; dn &= share < 1 - tk
        s = np.zeros(len(b), 'int8'); s[up.values] = 1; s[dn.values] = -1
        return s, cl.values * (1 - s * k * hv(c, b))
    return fn

# ---------- 4. falsa rottura -> fade ----------
def fade(N, K, buf=0.0):
    def fn(c, b):
        hh = b['high'].rolling(N).max().shift(1); ll = b['low'].rolling(N).min().shift(1); cl = b['close']
        # livello "congelato": massimo a N barre di K barre fa (cosi' la rottura nelle ultime K barre non lo sposta)
        lvh = hh.shift(K - 1); lvl = ll.shift(K - 1)
        rhi = b['high'].rolling(K).max(); rlo = b['low'].rolling(K).min()
        broke_up = rhi > lvh; broke_dn = rlo < lvl
        s = np.zeros(len(b), 'int8')
        s[(broke_up & (cl < lvh) & (cl.shift(1) >= lvh.shift(1))).values] = -1        # rientro sotto il livello: short
        s[(broke_dn & (cl > lvl) & (cl.shift(1) <= lvl.shift(1))).values] = 1
        spx = np.where(s == -1, rhi.values * (1 + buf), rlo.values * (1 - buf))
        return s, spx
    return fn

# ---------- 5. accensione di momentum ----------
def ign(n, m, direction, k):
    def fn(c, b):
        r = np.sign(b['close'] - b['open']); run = r.rolling(n).sum(); mv = np.log(b['close'] / b['open'].shift(n - 1)); v = hv(c, b)
        s = np.zeros(len(b), 'int8')
        s[((run == n) & (mv > m * v)).values] = direction; s[((run == -n) & (mv < -m * v)).values] = -direction
        return s, b['close'].values * (1 - s * k * v)
    return fn

if __name__ == '__main__':
    if 'squeeze' in which:
        tr = Trials('squeeze')
        for rule in ('5min', '15min', '1h'):
            mh = {'5min': 288, '15min': 288 * 2, '1h': 288 * 4}[rule]
            for mode in ('bbkc', 'atrp'):
                for k in (1.0, 2.0):
                    for ex in ('trail3', 'time'):
                        kw = dict(trail_R=3.0) if ex == 'trail3' else {}
                        T = runall(squeeze(rule, mode, k), maxhold=mh if ex != 'time' else mh // 4, **kw)
                        tr.add(T, f'SQZ {rule} {mode} stop={k}ATR {ex}')
        print('== SQUEEZE'); show(tr.table()); tr.save(); tr.table().to_parquet('res_squeeze.parquet')
    if 'orb' in which:
        tr = Trials('orb')
        for sess in ('utc0', 'eu', 'us'):
            for mins in (15, 30, 60):
                for sm in ('opp', 'mid'):
                    for hh in (8, 24):
                        T = runall(orb(sess, mins, sm, hh)); tr.add(T, f'ORB {sess} {mins}m stop={sm} tiene {hh}h')
        print('== ORB'); show(tr.table()); tr.save(); tr.table().to_parquet('res_orb.parquet')
    if 'vol' in which:
        tr = Trials('vol')
        for N in (72, 288):
            for volq in (0, 3, 6):
                for tk in (0, 0.6):
                    for k in (1.0, 2.0):
                        T = runall(volbrk(N, volq, tk, k), maxhold=144, trail_R=3.0); tr.add(T, f'VOLBRK N={N} vol>{volq} taker>{tk} stop={k}hv trail3 12h')
        print('== VOLUME/TAKER'); show(tr.table()); tr.save(); tr.table().to_parquet('res_vol.parquet')
    if 'fade' in which:
        tr = Trials('fade')
        for N in (72, 288, 864):
            for K in (3, 12):
                for ex in ('tp2', 'tp3', 'time'):
                    kw = dict(tp_R=2.0) if ex == 'tp2' else dict(tp_R=3.0) if ex == 'tp3' else {}
                    T = runall(fade(N, K), maxhold=144, **kw); tr.add(T, f'FADE N={N} K={K} {ex} 12h')
        print('== FALSA ROTTURA'); show(tr.table()); tr.save(); tr.table().to_parquet('res_fade.parquet')
    if 'ign' in which:
        tr = Trials('ign')
        for n in (4, 6, 8):
            for m in (1.0, 2.0):
                for d in (1, -1):
                    for hold in (12, 48):
                        T = runall(ign(n, m, d, 1.0), maxhold=hold); tr.add(T, f'IGN n={n} mossa>{m}hv {"segue" if d == 1 else "contro"} tiene {hold} barre')
        print('== ACCENSIONE'); show(tr.table()); tr.save(); tr.table().to_parquet('res_ign.parquet')
