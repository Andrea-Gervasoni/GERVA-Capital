"""A4 - estensioni e controlli. SIMULATO.
A) conviction sul top-3 / top-5 point-in-time (invece del trio scelto col senno di poi)
B) libro neutrale a orizzonte lungo (stop larghi, tenuta 14-28 giorni)
C) conviction RELATIVA: segnali sul rapporto moneta/BTC, long moneta + short BTC (percorso sui soli open/close orari: STIMA)
D) percorso a 5 minuti contro 1 ora sul trio (errore di misura delle barre orarie)
E) controllo di troncamento dei segnali
F) libro scelto sulla sola selezione (trio + i migliori candidati di ampiezza) e suo esito in verifica"""
import sys, pickle, copy; sys.path.insert(0, '/home/user/GERVA-Capital/research/v5/v5/a4_universo')
from lab import *
pd.set_option('display.width', 300); pd.set_option('display.max_columns', 50)
U, RANK = load_all(30)
TRIO = ('BTCUSDT', 'ETHUSDT', 'SOLUSDT'); nvar = 0; rows = []; KEEP = {}
def add(lab, T, M): KEEP[lab] = (T, M); rows.append(row(lab, T, M))
def show(rows):
    R = pd.DataFrame(rows).set_index('cfg')
    print(R[['n', 'R', 't', 'hit', 'R_sc', 't_sc', 'R_ver', 't_ver', 'n_ver', 'N', 'sR', 'Neff', 'K', 'K_sc', 'K_ver', 'rho']].round(3).to_string())
def conv_sig(U, topn=None, only=None):
    ent, ext = {}, {}
    for s, o in U.items():
        if only is not None and s not in only: continue
        ent[s] = (o.tier == 'alta') & ((o.rank <= topn) if topn else True); ext[s] = (o.tier == 'bassa')
    return ent, ext

print('== A) conviction, top-3 e top-5 per volume point-in-time, 1xATR ==')
for n in (3, 5):
    T, M = run(U, *conv_sig(U, topn=n)); add(f'A top{n} point-in-time 1xATR', T, M); nvar += 1
T0, M0 = run(U, *conv_sig(U, only=TRIO)); add('trio (riferimento)', T0, M0)
show(rows)

print('\n== B) neutrale a orizzonte lungo: long primi 5 / short ultimi 5 per rendimento a L giorni ==')
C = pd.DataFrame({s: o.D['close'].reindex(CAL) for s, o in U.items()})
MEM = pd.DataFrame({s: pd.Series(o.rank <= 30, index=o.days).reindex(CAL).fillna(False) for s, o in U.items()}).astype(bool)
def ranks(L, C=C, MEM=MEM):
    sc = (C / C.shift(L) - 1).where(MEM); return sc.rank(axis=1, ascending=False).shift(1), sc.rank(axis=1, ascending=True).shift(1)
def rs_sig(rk, k, hyst=2):
    ent, ext = {}, {}
    for s, o in U.items():
        r = rk[s].reindex(o.days).values; ent[s] = r <= k; ext[s] = ~(r <= hyst * k)
    return ent, ext
rb = []
for L in (30, 90):
    top, bot = ranks(L)
    for ak in (2.0, 3.0):
        for mh in (14, 28):
            Tl, Ml = run(U, *rs_sig(top, 5), atr_k=ak, maxhold=mh); Ts, Ms = run(U, *rs_sig(bot, 5), side=-1, atr_k=ak, maxhold=mh); nvar += 1
            lab = f'B neutro L{L} k5 stop {ak:.0f}xATR tenuta {mh}g'; KEEP[lab] = (pd.concat([Tl, Ts]), Ml + Ms); rb.append(row(lab, *KEEP[lab]))
            rb.append(row('   di cui gamba long', Tl, Ml)); rb.append(row('   di cui gamba short', Ts, Ms))
show(rb)

print('\n== C) conviction relativa (moneta/BTC), long moneta + short BTC, costi delle due gambe ==')
B = U['BTCUSDT']; bix = pd.DatetimeIndex(st.get('v5_um_1h_BTCUSDT').index)
UR = {}
for s, o in U.items():
    if s == 'BTCUSDT': continue
    b = st.get(f'v5_um_1h_{s}'); b = b[(b['high'] > 0) & (b.index >= CAL[0])]; bb = st.get('v5_um_1h_BTCUSDT').reindex(b.index)
    ok = bb['open'].notna().values; b = b[ok]; bb = bb[ok]
    if len(b) < 24 * 260: continue
    r = Coin(); r.sym = s; r.op = (b['open'] / bb['open']).values; r.cl = (b['close'] / bb['close']).values
    r.hi = np.maximum(r.op, r.cl); r.lo = np.minimum(r.op, r.cl)
    day = b.index.normalize(); g = pd.DataFrame(dict(open=r.op, high=r.hi, low=r.lo, close=r.cl), index=b.index).groupby(day)
    r.D = pd.DataFrame(dict(open=g['open'].first(), high=g['high'].max(), low=g['low'].min(), close=g['close'].last()))
    r.days = r.D.index; r.start = np.searchsorted(day.values, r.days.values); r.end = np.append(r.start[1:], len(b)); r.cal = CAL.get_indexer(r.days)
    r.atr = ((r.D['high'] - r.D['low']) / r.D['close']).rolling(14).mean().shift(1).values
    fb = pd.Series(B.fund, index=B.days).reindex(r.days).values; fc = pd.Series(o.fund, index=o.days).reindex(r.days).values
    r.fund = np.where(np.isnan(fc), 0.0003, fc) - np.where(np.isnan(fb), 0.0003, fb); r.fund_s = pd.Series(r.fund, index=r.days)
    r.rank = pd.Series(o.rank, index=o.days).reindex(r.days).values; r.volmed = pd.Series(o.volmed, index=o.days).reindex(r.days).values
    r.xfee = TAKER + SLIP_TOP                                           # la gamba BTC
    F = E.crypto_signals(r.D, B.D['close'], r.fund_s); cv = E.conviction(F, 'crypto').shift(1); r.tier = cv['tier'].values; r.score = cv['score'].values
    UR[s] = r
rc = []
for n in (10, 30):
    for ak in (1.0, 2.0):
        T, M = run(UR, *conv_sig(UR, topn=n), atr_k=ak); lab = f'C relativa top{n} stop {ak:.0f}xATR'; KEEP[lab] = (T, M); rc.append(row(lab, T, M)); nvar += 1
show(rc)

print('\n== D) trio: percorso a 5 minuti contro 1 ora (stessi segnali, stessi giorni) ==')
U5 = {}
for s in TRIO:
    o = copy.copy(U[s]); b = st.get(f'v4_um_5m_{s}'); b = b[(b.index >= CAL[0]) & (b.index <= CAL[-1] + pd.Timedelta(hours=24))]
    o.op, o.hi, o.lo, o.cl = (b[c].values.astype(np.float64) for c in ('open', 'high', 'low', 'close'))
    dn = b.index.normalize().values; o.start = np.searchsorted(dn, o.days.values); o.end = np.searchsorted(dn, o.days.values, side='right'); U5[s] = o
rd = []
for lab, UU, kw in (('1h', U, {}), ('5m', U5, {}), ('5m ritardo +5min', U5, dict(delay=1)), ('5m costi x2', U5, dict(cost_mult=2.0))):
    for ak in (1.0, 2.0):
        T, M = run(UU, *conv_sig(UU, only=TRIO), atr_k=ak, **kw); rd.append(row(f'trio {lab} {ak:.0f}xATR', T, M))
show(rd)

print('\n== E) troncamento: segnali ricalcolati sui dati tagliati al giorno t-1 ==')
rng = np.random.default_rng(7); bad = 0; tot = 0
for s in rng.choice(list(U), 12, replace=False):
    o = U[s]
    if len(o.days) < 400: continue
    for i in rng.integers(260, len(o.days) - 1, 8):
        Dc = o.D.iloc[:i]; f = o.fund_s[o.fund_s.index < o.days[i]] if o.fund_s is not None else None
        cv = E.conviction(E.crypto_signals(Dc, B.D['close'][B.D.index < o.days[i]], f), 'crypto')
        a = cv['score'].iloc[-1]; b_ = o.score[i]; tot += 1
        if not ((np.isnan(a) and np.isnan(b_)) or abs(a - b_) < 1e-12) or (cv['tier'].iloc[-1] != o.tier[i]): bad += 1
top, bot = ranks(30)
for t in rng.integers(300, len(CAL) - 1, 12):
    t2, _ = ranks(30, C.iloc[:t], MEM.iloc[:t]); a = (C.iloc[:t] / C.iloc[:t].shift(30) - 1).where(MEM.iloc[:t]).rank(axis=1, ascending=False).iloc[-1]
    tot += 1; bad += int(not np.allclose(a.fillna(-1).values, top.iloc[t].fillna(-1).values))
print(f'confronti: {tot}, differenze: {bad}')

print('\n== F) libro scelto sulla SOLA selezione: trio + candidati di ampiezza con t di selezione > 2 ==')
A = pickle.load(open('/home/user/GERVA-Capital/data_cache/v5_a4_a.pkl', 'rb')); BC = pickle.load(open('/home/user/GERVA-Capital/data_cache/v5_a4_bc.pkl', 'rb'))
alt_conv = A['top30 stop 1xATR']; Ta = alt_conv[0][~alt_conv[0].symbol.isin(TRIO)]; Ma = alt_conv[1].drop(columns=list(TRIO)).reindex(columns=M0.columns, fill_value=0.0)
parts = {'trio': (T0, M0), '+ conviction alt top30': (Ta, Ma), '+ SHORT L7 k5 BTC<MA100': BC['b SHORT L7 k5 BTC<MA100'], '+ LONG L30 k5 BTC>MA100': BC['b LONG L30 k5 BTC>MA100']}
rf = []; Tc = None; Mc = None
for k, (T, M) in parts.items():
    Tc = T if Tc is None else pd.concat([Tc, T]); Mc = M.copy() if Mc is None else Mc + M.reindex(columns=Mc.columns, fill_value=0.0)
    rf.append(row(('trio' if k == 'trio' else 'trio ' + k + ' (cumulato)'), Tc, Mc))
show(rf)
print('\nvarianti nuove provate in questo script:', nvar)
pickle.dump(KEEP, open('/home/user/GERVA-Capital/data_cache/v5_a4_x.pkl', 'wb'))
