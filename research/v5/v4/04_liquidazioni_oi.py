"""Famiglia 4 - cascate di liquidazioni, open interest, estremi di funding, posizionamento.
Dati REALI: Binance USDT-M 'metrics' (open interest, rapporto long/short dei top trader e di tutti i conti, rapporto taker
buy/sell) a 5 minuti aggregati all'ora, 10 monete, dal 2021-12 (prima non esistono: il periodo di SCELTA e' solo 2021-12 -> 2022-12);
funding Binance dal 2020; candele perp 1h. L'archivio liquidationSnapshot NON esiste piu' (404): le liquidazioni sono
approssimate con 'calo dell'open interest + calo del prezzo'. Costi 7 pb/lato + funding reale. Tutti i numeri sono SIMULATI."""
from lab import *
F = Fam('oi')
C10 = "BTC ETH SOL BNB XRP DOGE ADA LINK AVAX LTC".split()
P = hourly_panel('um', C10).loc['2020-01-01':'2026-10-31']; R = P.pct_change(fill_method=None)
M_ = {c: get(f'v4_metrics_1h_{c}') for c in C10}
OI = pd.DataFrame({c: M_[c]['sum_open_interest'] for c in C10}).reindex(P.index)            # in monete (non in dollari: non dipende dal prezzo)
TOP = pd.DataFrame({c: M_[c]['sum_toptrader_long_short_ratio'] for c in C10}).reindex(P.index)   # top trader, per posizioni
ALL = pd.DataFrame({c: M_[c]['count_long_short_ratio'] for c in C10}).reindex(P.index)           # tutti i conti
TAK = pd.DataFrame({c: M_[c]['sum_taker_long_short_vol_ratio'] for c in C10}).reindex(P.index)
fh = {}
for c in C10:
    s = get(f'bn_fund_{c}USDT').iloc[:, 0]; s.index = s.index.floor('h'); fh[c] = s.groupby(level=0).sum()
FH = pd.DataFrame(fh).reindex(P.index).fillna(0.0)
print('copertura metrics:', OI.dropna(how='all').index[0], '->', OI.dropna(how='all').index[-1], ' ore mancanti %:', (100 * OI.loc['2021-12-01':].isna().mean()).round(1).to_dict())

def ev(pos, fee=0.0007, lag=1, cap=1.5):
    """pos: DataFrame ore x monete (nozionale per moneta, frazione del capitale). Lordo massimo `cap`."""
    g = pos.abs().sum(axis=1); pos = pos.mul((cap / g).clip(upper=1.0).fillna(1.0), axis=0)
    held = pos.shift(lag).fillna(0.0)
    pnl = (held * (R.fillna(0.0) - FH)).sum(axis=1) - pos.shift(lag - 1).diff().abs().sum(axis=1).fillna(0.0) * fee
    return daily(pnl), float(held.abs().sum(axis=1).mean())
def hold(sig, H):
    """Mantiene il segnale per H ore dall'ultimo evento."""
    return sig.where(sig != 0).ffill(limit=H - 1).fillna(0.0)

print('\n== 4a. Studio d\'evento: rendimento successivo (pb) dopo calo di OI + calo di prezzo nelle ultime h ore')
def fwd(H): return (P.shift(-H) / P - 1)
rows = []
for h in (1, 4, 24):
    dOI = OI / OI.shift(h) - 1; dP = P / P.shift(h) - 1
    qo = dOI.rolling(24 * 90, min_periods=24 * 30).quantile(0.02).shift(1); qp = dP.rolling(24 * 90, min_periods=24 * 30).quantile(0.05).shift(1)
    evt = (dOI < qo) & (dP < qp); evu = (dOI < qo) & (dP > dP.rolling(24 * 90, min_periods=24 * 30).quantile(0.95).shift(1))
    for lab, e in (('OI giu + prezzo giu (long liquidati)', evt), ('OI giu + prezzo su (short liquidati)', evu)):
        for H in (4, 24, 72):
            f = fwd(H); row = dict(h=h, evento=lab, H=H)
            for nm, sl in (('sel', slice('2021-12-01', SEL_END)), ('ver', slice(SPL, None))):
                x = f.loc[sl][e.loc[sl]].stack().dropna(); u = f.loc[sl].stack().dropna()
                row[f'n_{nm}'] = len(x); row[f'medio_{nm}'] = round(x.mean() * 1e4, 1); row[f'incond_{nm}'] = round(u.mean() * 1e4, 1); row[f'vinti_{nm}'] = round((x > 0).mean(), 2)
            rows.append(row)
print(pd.DataFrame(rows).to_string(index=False))
print('  (n = ore-moneta con evento; gli eventi sono raggruppati nel tempo, quindi i t-statistici ingenui sarebbero gonfiati: non li riporto)')

print('\n== 4b. Strategia: dopo la cascata (OI giu sotto il 2° percentile + prezzo giu sotto il 5°, finestre mobili di 90 giorni) si compra e si tiene H ore')
for h in (1, 4, 24):
    dOI = OI / OI.shift(h) - 1; dP = P / P.shift(h) - 1
    for qo_, qp_ in ((0.02, 0.05), (0.05, 0.10), (0.01, 0.02)):
        qo = dOI.rolling(24 * 90, min_periods=24 * 30).quantile(qo_).shift(1); qp = dP.rolling(24 * 90, min_periods=24 * 30).quantile(qp_).shift(1)
        evt = ((dOI < qo) & (dP < qp)).astype(float)
        for H in (4, 24, 72):
            r, expo = ev(hold(evt, H) * 0.5); r = r.loc['2021-12-01':]
            t = F.line(f'cascata h{h} q({qo_},{qp_}) tieni {H}h', r, extra=f'esposizione media {expo:.2f}')
            if (h, qo_, H) == (4, 0.02, 24): r_casc = r; pos_casc = hold(evt, H) * 0.5
print('   robustezza della variante centrale (h=4, 2°/5° percentile, 24 ore):')
F.line('   cascata centrale costi x2', ev(pos_casc, fee=0.0014)[0].loc['2021-12-01':]); F.line('   cascata centrale ritardo +1 ora', ev(pos_casc, lag=2)[0].loc['2021-12-01':]); F.line('   cascata centrale lordo', ev(pos_casc, fee=0.0)[0].loc['2021-12-01':])
# stessa regola SENZA open interest (solo crollo del prezzo): disponibile dal 2020, serve a capire se l'OI aggiunge qualcosa
for h in (4, 24):
    dP = P / P.shift(h) - 1; qp = dP.rolling(24 * 90, min_periods=24 * 30).quantile(0.02).shift(1); evt = (dP < qp).astype(float)
    for H in (24, 72):
        F.line(f'solo crollo del prezzo h{h} (2° pct) tieni {H}h, dal 2020', ev(hold(evt, H) * 0.5)[0].loc['2020-06-01':])
F.keep('CASCATA-OI (h4, 24h)', r_casc)
print('   compra-il-crollo senza OI (prezzo sotto il q-esimo percentile mobile a 24 ore, tieni H ore): griglia e robustezza, dal 2020-06')
dP = P / P.shift(24) - 1
for q_ in (0.01, 0.02, 0.05):
    qp = dP.rolling(24 * 90, min_periods=24 * 30).quantile(q_).shift(1); evt = (dP < qp).astype(float)
    for H in (12, 24, 48):
        for w_, cap_ in ((0.5, 1.5), (0.1, 0.5)):
            r, expo = ev(hold(evt, H) * w_, cap=cap_); F.line(f'crollo 24h q{q_} tieni {H}h peso {w_} tetto {cap_}', r.loc['2020-06-01':], extra=f'esp {expo:.2f}')
            if (q_, H, w_) == (0.02, 24, 0.1): pos_dip = hold(evt, H) * w_; r_dip = r.loc['2020-06-01':]
F.line('   DIP centrale (q2%, 24h, peso 0.1, tetto 0.5) costi x2', ev(pos_dip, fee=0.0014, cap=0.5)[0].loc['2020-06-01':]); F.line('   DIP centrale ritardo +1 ora', ev(pos_dip, lag=2, cap=0.5)[0].loc['2020-06-01':])
F.line('   DIP centrale ritardo +4 ore', ev(pos_dip, lag=5, cap=0.5)[0].loc['2020-06-01':]); F.line('   DIP centrale spot 30 pb', ev(pos_dip, fee=0.003, cap=0.5)[0].loc['2020-06-01':])
F.keep('DIP-24h (compra il crollo, perp)', r_dip)

print('\n== 4c. Estremi di funding: si va contro la folla. Funding medio delle ultime 3 rilevazioni sopra il 95° percentile mobile (1 anno) -> short; sotto il 5° -> long')
f8 = pd.DataFrame({c: get(f'bn_fund_{c}USDT').iloc[:, 0] for c in C10}); f8.index = f8.index.floor('h'); f8 = f8[~f8.index.duplicated()]
fm = f8.rolling(3).mean(); hi = fm.rolling(3 * 365, min_periods=3 * 120).quantile(0.95).shift(1); lo = fm.rolling(3 * 365, min_periods=3 * 120).quantile(0.05).shift(1)
for q, (hi_, lo_) in (('95/5', (hi, lo)), ('99/1', (fm.rolling(3 * 365, min_periods=3 * 120).quantile(0.99).shift(1), fm.rolling(3 * 365, min_periods=3 * 120).quantile(0.01).shift(1)))):
    sig = (-(fm > hi_).astype(float) + (fm < lo_).astype(float)).reindex(P.index).fillna(0.0)
    for H in (8, 24, 72, 168):
        for side in ('entrambi', 'solo short su funding alto', 'solo long su funding basso'):
            s = sig if side == 'entrambi' else (sig.clip(upper=0) if 'short' in side else sig.clip(lower=0))
            r, expo = ev(hold(s, H) * 0.5); r = r.loc['2020-06-01':]
            F.line(f'funding estremo {q} {side} tieni {H}h', r, extra=f'esp {expo:.2f}')
            if (q, H, side) == ('95/5', 72, 'solo long su funding basso'): r_fl = r; pos_fl = hold(s, H) * 0.5
F.line('   long su funding basso 95/5 72h: costi x2', ev(pos_fl, fee=0.0014)[0].loc['2020-06-01':]); F.line('   long su funding basso 95/5 72h: ritardo +1', ev(pos_fl, lag=2)[0].loc['2020-06-01':])
F.keep('FUNDING-BASSO long (95/5, 72h)', r_fl)

print('\n== 4d. Posizionamento: rapporto long/short di tutti i conti (contrarian) e dei top trader (seguire), z-score su 30 giorni, ribilanciato ogni 24 ore')
def zpos(X, w=24 * 30, sign=1.0, thr=1.0, reb=24):
    lx = np.log(X); z = (lx - lx.rolling(w, min_periods=w // 2).mean()) / lx.rolling(w, min_periods=w // 2).std()
    s = sign * ((z > thr).astype(float) - (z < -thr).astype(float))
    k = pd.Series(np.arange(len(s)) % reb == 0, index=s.index); return s.where(k, np.nan).ffill().fillna(0.0) * 0.15
for lab, X, sg in (('tutti i conti, contrarian', ALL, -1.0), ('tutti i conti, seguire', ALL, 1.0), ('top trader, seguire', TOP, 1.0), ('top trader, contrarian', TOP, -1.0), ('taker buy/sell 24h, seguire', TAK.rolling(24).mean(), 1.0), ('taker buy/sell 24h, contrarian', TAK.rolling(24).mean(), -1.0)):
    for thr in (1.0, 2.0):
        r, expo = ev(zpos(X, sign=sg, thr=thr)); F.line(f'{lab} |z|>{thr}', r.loc['2022-01-01':], extra=f'esp {expo:.2f}')
pc = zpos(ALL, sign=-1.0, thr=1.0); r_c = ev(pc)[0].loc['2022-01-01':]
F.line('   contro i conti al dettaglio |z|>1: costi x2', ev(pc, fee=0.0014)[0].loc['2022-01-01':]); F.line('   contro i conti al dettaglio |z|>1: ritardo +1 ora', ev(pc, lag=2)[0].loc['2022-01-01':])
for w_ in (24 * 14, 24 * 60):
    F.line(f'   contro i conti al dettaglio |z|>1, finestra {w_ // 24}g', ev(zpos(ALL, w=w_, sign=-1.0, thr=1.0))[0].loc['2022-01-01':])
F.line('   contro i conti al dettaglio |z|>1, ribilancio 72h', ev(zpos(ALL, sign=-1.0, thr=1.0, reb=72))[0].loc['2022-01-01':])
F.keep('CONTRO-DETTAGLIO (L/S conti, z30)', r_c)
# trasversale: long le monete dove i conti al dettaglio sono meno long, short dove lo sono di piu'
for lab, X, sg in (('trasversale: contro i conti al dettaglio', ALL, -1.0), ('trasversale: con i top trader', TOP, 1.0), ('trasversale: OI in crescita 7g (seguire)', OI / OI.shift(168), 1.0), ('trasversale: OI in crescita 7g (contrarian)', OI / OI.shift(168), -1.0)):
    lx = np.log(X); z = (lx - lx.rolling(720, min_periods=360).mean()) / lx.rolling(720, min_periods=360).std()
    w = sg * z.sub(z.mean(axis=1), axis=0); w = w.div(w.abs().sum(axis=1), axis=0).fillna(0.0)
    k = pd.Series(np.arange(len(w)) % 24 == 0, index=w.index); w = w.where(k, np.nan).ffill().fillna(0.0)
    r, expo = ev(w, cap=1.0); F.line(lab + ' (lordo 1, giornaliero)', r.loc['2022-01-01':]); F.line(lab + ' senza costi', ev(w, fee=0.0, cap=1.0)[0].loc['2022-01-01':])
    if 'top trader' in lab: r_top = r.loc['2022-01-01':]
F.keep('XS top trader (seguire)', r_top)
F.save()
