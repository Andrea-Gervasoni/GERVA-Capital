"""A10 - 03: (1) cassa libera parcheggiata in titoli di Stato a breve; (2) allocazione walk-forward; (3) ribilanciamento tra sleeve
con costi veri; (4) volatilita' obiettivo. Parametri scelti SOLO sul periodo di scelta. SIMULATO."""
from common import *
import json
adj = B['adj']
bil = adj['BIL'].pct_change(fill_method=None).reindex(IDX).fillna(0.0)          # ETF di T-bill 1-3 mesi (rendimento vero, TER incluso)
print('BIL: rendimento annuo %.3f%% contro rf %.3f%% (2018-04 ->)' % (bil.mean() * 365 * 100, rf.mean() * 365 * 100))
def park(idle, buffer=0.05, band=0.05, fee=0.001, yld=None):
    """Quota parcheggiata: (cassa libera - cuscinetto), decisa con i dati di ieri, ritoccata solo oltre la banda. Ritorna rendimento aggiuntivo."""
    tgt = (idle - buffer).clip(lower=0.0).shift(1).fillna(0.0).values; y = (bil if yld is None else yld).values; w = 0.0; out = np.zeros(len(tgt)); ws = np.zeros(len(tgt))
    for t in range(len(tgt)):
        out[t] = w * y[t]
        if abs(tgt[t] - w) > band or (tgt[t] == 0 and w > 0): out[t] -= abs(tgt[t] - w) * fee; w = tgt[t]
        ws[t] = w
    return pd.Series(out, index=idle.index), pd.Series(ws, index=idle.index)
print('\n== 1. Cassa libera in T-bill (ETF monetario; 10 pb per lato; cuscinetto 5%, banda 5%; quota decisa il giorno prima)')
cu = cash_used(); idle_all = 1 - cu
idle_ibkr = A6[['MA-TREND', 'EQ-MR']].sum(axis=1) - (A6 * G6 * CASHUSE)[['MA-TREND', 'EQ-MR']].sum(axis=1)
Tm, mg, no, rk = trade_book()
base = trial('cassa', 'B. 6 strategie 1x (cassa a rendimento zero)', NEW)
for lab, idle in (('solo la cassa gia\' presso IBKR', idle_ibkr), ('tutta la cassa libera (capitale accentrato su IBKR)', idle_all), ('tutta la cassa libera meno 15% riservato al margine dei trade', idle_all - 0.15)):
    add, w = park(idle); t = trial('cassa', f'B + T-bill: {lab}', NEW + add, extra=f'parcheggiato medio {w.mean():.2f}, +{add.mean()*365:.3%}/anno (sel {add[:SEL_END].mean()*365:.3%}, ver {add[SPL:].mean()*365:.3%})')
add, w = park(idle_all, yld=(rf - 0.005 / 365).clip(lower=0)); trial('cassa', 'B + cassa remunerata a rf-0,5% (conto IBKR >10k o stablecoin a rendimento: IPOTESI)', NEW + add)
for bf, bd in ((0.02, 0.02), (0.05, 0.10), (0.10, 0.05), (0.10, 0.10)):
    add, w = park(idle_all, bf, bd); trial('cassa', f'  sensibilita\': cuscinetto {bf:.0%} banda {bd:.0%}', NEW + add)
addT, wT = park(idle_all - mg - 0.05)
trial('cassa', 'C2 (1x + trade 1/2% mtm), cassa a zero', NEW + Tm, monthly=True); trial('cassa', 'C2 + T-bill sulla cassa libera al netto del margine dei trade', NEW + Tm + addT, monthly=True, extra=f'parcheggiato medio {wT.mean():.2f}')
PARK = park(idle_all)[0]

print('\n== 2. Allocazione tra i 5 sleeve a rischio di mercato (CARRY resta a quota fissa 20%). Walk-forward: pesi a inizio mese con i dati fino al giorno prima')
def wf(fn, S=S5, window=180, minp=90, cap=0.60):
    """fn(X finestra senza NaN-colonne, Xexp storia intera) -> pesi (somma 1). Ricalcolo a inizio mese con dati <= t-1."""
    idx = S.index; months = idx.to_period('M'); rows = {}; first = np.where(months[1:] != months[:-1])[0] + 1
    for i in first:
        if i < minp: continue
        X = S.iloc[max(0, i - window):i]; ok = [c for c in S if X[c].notna().sum() >= minp]
        if not ok: continue
        Xe = S.iloc[:i][ok]; w = pd.Series(fn(X[ok].fillna(0.0), Xe), index=ok).clip(lower=0); w = (w / w.sum()).clip(upper=cap)
        rows[idx[i]] = w
    a = pd.DataFrame(rows).T.reindex(columns=S.columns).reindex(idx).ffill().dropna(how='all').fillna(0.0)
    return a
def shr_corr(X, d):
    c = X.corr().values; n = len(c); avg = (c.sum() - n) / (n * (n - 1)) if n > 1 else 0.0; t = np.full((n, n), avg); np.fill_diagonal(t, 1.0); return (1 - d) * c + d * t
def vols(X, Xe, floor=0.5): return np.maximum(X.std().values, floor * Xe.std().values)
def f_rp(X, Xe): return 1 / vols(X, Xe)
def f_rp_nofloor(X, Xe): return 1 / np.maximum(X.std().values, 1e-6)
def f_eq(X, Xe): return np.ones(X.shape[1])
def f_iv(s):  # varianza inversa, varianze contratte verso la media trasversale
    def f(X, Xe): v = vols(X, Xe) ** 2; return 1 / ((1 - s) * v + s * v.mean())
    return f
def minvar(Sig, iters=500):
    n = len(Sig); w = np.ones(n) / n
    for _ in range(iters):                                   # gradiente proiettato sul simplesso (solo long)
        g = Sig @ w; w = w * np.exp(-0.5 * g / (np.abs(g).max() + 1e-12)); w /= w.sum()
    return w
def f_mv(d):
    def f(X, Xe): v = vols(X, Xe); return minvar(np.outer(v, v) * shr_corr(X, d))
    return f
def erc(Sig, iters=2000):
    n = len(Sig); w = 1 / np.sqrt(np.diag(Sig)); w /= w.sum()
    for _ in range(iters):
        m = Sig @ w; rc = w * m; w = w * (rc.mean() / rc) ** 0.5; w /= w.sum()
    return w
def f_erc(d):
    def f(X, Xe): v = vols(X, Xe); return erc(np.outer(v, v) * shr_corr(X, d))
    return f
def f_sharpe(sh, k=1.0):  # parita' di rischio inclinata dallo Sharpe storico (espansivo), contratto verso la media trasversale
    def f(X, Xe):
        s = (Xe.mean() / Xe.std() * math.sqrt(365)).values; s = (1 - sh) * s + sh * np.nanmean(s); return (1 / vols(X, Xe)) * np.clip(1 + k * (s - np.nanmean(s)), 0.2, None)
    return f
METH = [('RP con pavimento 0,5 (attuale; ricalcolata qui)', f_rp, 180), ('RP senza pavimento', f_rp_nofloor, 180), ('pesi uguali', f_eq, 180), ('RP finestra 90', f_rp, 90), ('RP finestra 365', f_rp, 365),
        ('varianza inversa, contrazione 0', f_iv(0.0), 180), ('varianza inversa, contrazione 0,5', f_iv(0.5), 180), ('varianza inversa, contrazione 0,8', f_iv(0.8), 180),
        ('minima varianza, corr contratta 0,5', f_mv(0.5), 180), ('minima varianza, corr contratta 0,9', f_mv(0.9), 180), ('minima varianza, corr contratta 0,5, finestra 365', f_mv(0.5), 365),
        ('ERC, corr contratta 0,5', f_erc(0.5), 180), ('ERC, corr contratta 0,5, finestra 365', f_erc(0.5), 365), ('ERC, corr grezza', f_erc(0.0), 180),
        ('RP x Sharpe, contrazione 0,9', f_sharpe(0.9), 180), ('RP x Sharpe, contrazione 0,75', f_sharpe(0.75), 180), ('RP x Sharpe, contrazione 0,5', f_sharpe(0.5), 180)]
line('RIFERIMENTO: portafoglio pubblicato (gerva.portfolio.risk_parity)', NEW); AL = {}
for nm, fn, win in METH:
    a = with_carry(wf(fn, window=win)); p = (a * S6.reindex(a.index).fillna(0.0)).sum(axis=1).reindex(IDX).dropna(); AL[nm] = (a, p)
    t = trial('allocazione', nm, p, extra=f"| pesi medi {' '.join('%s %.2f' % (k[:5], v) for k, v in a.mean().items())} | giro pesi/anno {a.diff().abs().sum(axis=1).mean() * 365:.1f}")
print("   A parita' di volatilita' (7,6%): CAGR in eccesso = Sharpe x 7,6%. Differenza di Sharpe tra il migliore in scelta e l'attuale va letta contro l'errore standard (~0,45 su 5 anni).")

print('\n== 3. Ribilanciamento TRA sleeve: combine() ribilancia ogni giorno gratis. Conto vero: le quote derivano; costi sugli spostamenti')
FEEK = pd.Series({'CR-TREND': .003, 'CR-XSMOM': .003, 'EQ-MR': .0005, 'MA-TREND': .001, 'DIP': .0007, 'CARRY': .0037 * .75})
def rebal(a=A6, every='M', band=0.0, cost=True):
    Sx = S6.reindex(a.index).fillna(0.0).values; A = a.values; Gx = (G6.reindex(a.index) * FEEK).values; n, K = A.shape
    per = a.index.to_period({'M': 'M', 'W': 'W', 'Q': 'Q', 'D': 'D', 'Y': 'Y'}[every]); newp = np.r_[True, per[1:] != per[:-1]]
    f = A[0].copy(); cash = 1 - f.sum(); out = np.zeros(n); tc = 0.0; turn = 0.0
    for t in range(n):
        g = f * (1 + Sx[t]); tot = g.sum() + cash; r = tot - 1; f = g / tot; cash = cash / tot      # quote dopo la giornata
        c = 0.0
        if newp[t] if t < n else False:
            tgt = A[min(t + 1, n - 1)]                                                                # quota valida da domani (nota oggi)
            mv = np.abs(tgt - f) > band
            if mv.any():
                d = np.where(mv, tgt - f, 0.0); c = float((np.abs(d) * Gx[t]).sum()) if cost else 0.0; turn += np.abs(d).sum(); f = f + d; cash = 1 - f.sum()
        out[t] = (1 + r) * (1 - c) - 1; tc += c
    return pd.Series(out, index=a.index), tc / n * 365, turn / n * 365
line('combine() pubblicato (ribilancio giornaliero implicito, gratis)', NEW)
for ev, bd in (('D', 0.0), ('D', 0.02), ('W', 0.0), ('M', 0.0), ('M', 0.02), ('M', 0.05), ('Q', 0.0), ('Q', 0.05), ('Y', 0.0)):
    p, c, tu = rebal(every=ev, band=bd); trial('ribilancio', f'ribilancio {ev} banda {bd:.0%}', p, extra=f'| costo {c:.3%}/anno, giro {tu:.1f}x/anno')
print('   Bande e frequenza DENTRO gli sleeve (costi pieni): CR-TREND e MA-TREND')
from gerva.strategies import book, daily as SD
from gerva.backtest import Costs, run
cc, cr = B['cclose'], B['cret']
for hold in (1, 7, 14, 30):
    for band in (0.0, 0.03, 0.06, 0.10):
        W = SD.hold(SD.trend(cc[['BTC', 'ETH']], lookbacks=(30, 60, 120), long_only=True, asset_vol=0.40, span=30, periods=365).clip(upper=0.5), hold)
        res = run(W, cr[['BTC', 'ETH']], 0.0, Costs(trade=.003, cash_haircut=1.0), periods=365, band=band)
        trial('ribilancio', f'CR-TREND ogni {hold}g banda {band:.0%}', res.ret.loc['2018-04':].reindex(IDX).fillna(0), extra=f'| giro {res.turnover.loc["2018":].mean()*365:.1f}x costo {res.cost.loc["2018":].mean()*365:.2%}')
ad = B['adj']; c17 = ad[book.TREND_UNIVERSE].loc['2003':]; R17 = c17.pct_change(fill_method=None)
for hold in (1, 5, 10, 21):
    for band in (0.0, 0.02, 0.04):
        W = SD.hold(SD.vol_target(SD.trend(c17, lookbacks=(63, 126, 252), long_only=True), R17, 0.10, max_leverage=1.0), hold)
        res = run(W, R17, B['rfd'], Costs(trade=.001, cash_haircut=1.0), band=band)
        trial('ribilancio', f'MA-TREND ogni {hold}g banda {band:.0%}', res.ret.loc['2018-04':].reindex(IDX).fillna(0), extra=f'| giro {res.turnover.loc["2018":].mean()*252:.1f}x costo {res.cost.loc["2018":].mean()*252:.2%}')

print('\n== 4. Volatilita\' obiettivo sul libro giornaliero (obiettivo 15%): finestra, tetto, volatilita\' al ribasso. Finanziamento sul debito REALE; costo del cambio di leva 12 pb x esposizione')
cuv = cash_used()
def vt(target=0.15, window=60, cap=2.0, kind='std', band=0.0, x=NEW):
    if kind == 'std': v = x.rolling(window, min_periods=min(30, window)).std() * math.sqrt(365)
    elif kind == 'down': v = (x.clip(upper=0) ** 2).rolling(window, min_periods=min(30, window)).mean() ** .5 * math.sqrt(2 * 365)
    elif kind == 'ewma': v = x.ewm(span=window, min_periods=30).std() * math.sqrt(365)
    L = (target / v.where(v > 0)).clip(upper=cap).shift(1).fillna(0.0)
    if band > 0:
        Lv = L.values.copy(); cur = Lv[0]
        for i in range(len(Lv)):
            if abs(Lv[i] - cur) > band: cur = Lv[i]
            Lv[i] = cur
        L = pd.Series(Lv, index=L.index)
    r = L * x - np.maximum(L * cuv - 1, 0) * (rf + 0.015 / 365) - L.diff().abs().fillna(0) * 0.0012 * (A6 * G6).sum(axis=1)
    return r.iloc[90:], L.iloc[90:]
line('1x', NEW.iloc[90:])
for Lc in (1.5, 2.0, 3.0):
    r = Lc * NEW - np.maximum(Lc * cuv - 1, 0) * (rf + 0.015 / 365); trial('voltarget', f'leva costante {Lc}x (debito reale)', r.iloc[90:])
for cap in (2.0, 3.0):
    for kind in ('std', 'down', 'ewma'):
        for w in (20, 40, 60, 120, 250):
            r, L = vt(window=w, cap=cap, kind=kind); trial('voltarget', f'vol 15% {kind} finestra {w} tetto {cap}x', r, extra=f'| leva media {L.mean():.2f} giro leva {L.diff().abs().mean()*365:.1f}/anno')
for band in (0.1, 0.25, 0.5):
    r, L = vt(window=60, cap=2.0, band=band); trial('voltarget', f'vol 15% std finestra 60 tetto 2x, banda leva {band}', r, extra=f'| leva media {L.mean():.2f} giro leva {L.diff().abs().mean()*365:.1f}/anno')
json.dump(TRIALS, open(HERE + '/trials_03.json', 'w'), indent=0); print('\nvarianti provate in questo script:', {k: len(v) for k, v in TRIALS.items()}, 'totale', sum(len(v) for v in TRIALS.values()))
PARK.to_frame('park').to_parquet(HERE + '/_park.parquet')
