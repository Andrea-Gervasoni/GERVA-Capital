"""A6 - DIP-24h condizionato all'AMPIEZZA del crollo, nota al momento della decisione. SIMULATO.
ampiezza(t) = numero di monete dell'universo (36 perp) che all'apertura della barra t hanno il rendimento a 24h sotto il proprio
2o percentile a 90 giorni (compresa la moneta stessa). Ipotesi: il rimbalzo esiste quando crolla UNA moneta (chi vende e' forzato,
chi compra fornisce liquidita'), non quando crolla tutto il mercato (li' il crollo continua).
Attenzione: contare i crolli 'nello stesso giorno' sarebbe un'informazione futura; qui si usa solo il conteggio all'ora t."""
import lib; from lib import *
lib.CLU = 'D'
import importlib; gm = importlib.import_module('04_grandi_mosse') if False else None
def feats(df):
    c = df['close']; r24 = (c.shift(1) / c.shift(25) - 1); sig = pd.Series(Bars.sigma(df), index=df.index)
    return pd.DataFrame(dict(r24=r24, z=r24 / (sig * np.sqrt(24)), q02=r24.shift(1).rolling(2160, min_periods=720).quantile(0.02)))
SIG = {c: feats(bars(c, '1h').df) for c in ALTS}
STATE = pd.DataFrame({c: (SIG[c].r24 < SIG[c].q02) for c in ALTS}).fillna(False)
BREADTH = STATE.sum(axis=1); NAV = pd.DataFrame({c: SIG[c].q02.notna() for c in ALTS}).fillna(False).sum(axis=1)
for c in ALTS: SIG[c]['br'] = BREADTH.reindex(SIG[c].index); SIG[c]['nav'] = NAV.reindex(SIG[c].index)
# troncamento: lo stato di ogni moneta dipende solo dalle sue barre chiuse (verificato in 04); l'ampiezza e' la somma degli stati
print('controllo di troncamento dello stato DIP (SOL, XRP):', sum(trunc_check(lambda d: (feats(d).r24 < feats(d).q02).astype(float), bars(c, '1h').df.iloc[-6000:], n=8) for c in ('SOL', 'XRP')), 'differenze')
print('monete con storia sufficiente, per anno (mediana):', NAV.groupby(NAV.index.year).median().to_dict())
print('distribuzione dell''ampiezza nelle ore con almeno un DIP:', BREADTH[BREADTH > 0].describe(percentiles=[.5, .75, .9]).round(1).to_dict())
def dedup(idx, gap=24):
    out = []; last = None
    for t in idx:
        if last is None or (t - last) >= pd.Timedelta(hours=gap): out.append(t); last = t
    return out
def fam(cond, H=24, k=1.5, coins=ALTS, tp=None, maker=None, first=True):
    """first=True: l'evento e' il PRIMO istante in cui la moneta e' in DIP e la condizione e' vera (poi 24h di pausa)."""
    def fn(cm, delay):
        out = []
        for c in coins:
            F = SIG[c]; m = ((F.r24 < F.q02) & cond(F)).fillna(False); ts = dedup(F.index[m.values]); B = bars(c, '1h')
            if not ts: continue
            ev = pd.DataFrame(dict(t=ts, side=1))
            if maker is None: out.append(run(B, ev, H=H, k=k, cm=cm, delay=delay, tp=tp)); continue
            for t, s_ in ev.itertuples(index=False):
                i = B.idx(t) + delay
                if i + H + 2 >= len(B.t): continue
                s = float(np.clip(k * B.sig1h[i] * np.sqrt(H), 0.003, 0.15)); lim = B.op[i] * (1 - maker * B.sig1h[i])
                f = np.nonzero(B.lo[i:i + 4] < lim)[0]
                if len(f) == 0: continue
                r = sim(B, i + f[0] + 1, 1, s, H, cm=cm, entry_px=lim, entry_fee=MAKER)
                if r: r['t_dec'] = t; out.append(pd.DataFrame([r]))
        return pd.concat(out) if out else pd.DataFrame()
    return fn
print('\n=== DIP per ampiezza nota alla decisione (scelta del taglio sul periodo di scelta)')
K = {}
for a, b in ((1, 1), (2, 2), (3, 4), (5, 8), (9, 16), (17, 99)):
    K[(a, b)] = report(f'DIP, ampiezza tra {a} e {b}', fam(lambda F, a=a, b=b: (F.br >= a) & (F.br <= b)), 'dipiso')
for kk in (2, 4, 8):
    K[kk] = report(f'DIP, ampiezza <= {kk}', fam(lambda F, kk=kk: F.br <= kk), 'dipiso')
report('DIP, ampiezza > 8 (di mercato)', fam(lambda F: F.br > 8), 'dipiso')
report('DIP, ampiezza <= 10% delle monete disponibili', fam(lambda F: F.br <= np.maximum(1, 0.1 * F.nav)), 'dipiso')
pd.to_pickle(K, HERE + '/_dipiso.pkl'); save('dipiso')
