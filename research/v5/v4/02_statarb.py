"""Famiglia 2 - arbitraggio statistico su coppie e panieri di perpetual (Binance USDT-M, dati REALI 1h, 2020-2026).
a) coppie con z-score del log-rapporto (dollar-neutral), selezione walk-forward mensile delle coppie piu' 'cointegrate'
   (statistica di Dickey-Fuller sui 180 giorni precedenti), a 1h e 1d;  b) coppie fisse ETH/BTC, SOL/ETH, SOL/BTC;
c) inversione dei residui rispetto al fattore di mercato (stile Avellaneda-Lee) a 1h, 4h, 1d.
Costi: 7 pb/lato su ogni gamba, funding reale pagato/incassato. Nozionale lordo 2 (1 long + 1 short per 1 di capitale).
Tutti i numeri sono SIMULATI."""
from lab import *
F = Fam('statarb')
U = "BTC ETH SOL BNB XRP DOGE ADA LTC LINK AVAX DOT BCH ETC ATOM NEAR FIL UNI AAVE TRX XLM".split()
P = hourly_panel('um', U).loc['2020-01-01':'2026-10-31']; P = P.reindex(pd.date_range(P.index[0], P.index[-1], freq='h'))
fh = {}
for c in U:
    s = get(f'bn_fund_{c}USDT').iloc[:, 0]; s.index = s.index.floor('h'); fh[c] = s.groupby(level=0).sum()
FH = pd.DataFrame(fh).reindex(P.index).fillna(0.0)      # funding all'ora in cui viene regolato (lo paga chi e' long)
pairs = [(a, b) for i, a in enumerate(U) for b in U[i + 1:]]
GROSS = 2.0

def prep(freq):
    if freq == '1h': return P, FH
    p = P.resample(freq).last(); f = FH.resample(freq).sum(); return p, f

def pair_positions(lp, W, zin, zout, zstop=4.0):
    """lp: log prezzi (T x N). Ritorna posizioni (T x n_coppie) in {-1,0,1} sul log-rapporto A/B, decise alla chiusura."""
    ia = [lp.columns.get_loc(a) for a, b in pairs]; ib = [lp.columns.get_loc(b) for a, b in pairs]
    X = lp.to_numpy(); S = X[:, ia] - X[:, ib]; Sd = pd.DataFrame(S)
    Z = ((Sd - Sd.rolling(W, min_periods=W).mean()) / Sd.rolling(W, min_periods=W).std()).to_numpy()
    pos = np.zeros_like(Z); cur = np.zeros(Z.shape[1])
    for t in range(len(Z)):
        z = Z[t]; ok = np.isfinite(z)
        cur = np.where(~ok, 0.0, cur)
        cur = np.where((cur > 0) & ((z > -zout) | (z < -zstop)), 0.0, cur)      # long del rapporto: chiude al ritorno o allo stop
        cur = np.where((cur < 0) & ((z < zout) | (z > zstop)), 0.0, cur)
        cur = np.where(ok & (cur == 0) & (z < -zin) & (z > -zstop), 1.0, cur)
        cur = np.where(ok & (cur == 0) & (z > zin) & (z < zstop), -1.0, cur)
        pos[t] = cur
    return pos, ia, ib

def df_tstat(S):
    """Dickey-Fuller senza ritardi, vettoriale sulle colonne: t di b in  dS = a + b*S(-1)."""
    y = np.diff(S, axis=0); x = S[:-1]; xm = x - np.nanmean(x, 0); ym = y - np.nanmean(y, 0)
    sxx = np.nansum(xm * xm, 0); b = np.nansum(xm * ym, 0) / sxx; res = ym - b * xm
    se = np.sqrt(np.nansum(res * res, 0) / (len(y) - 2) / sxx); return b / se

def select_mask(lp, K, Fdays, bars_per_day):
    """Maschera (T x n_coppie): 1 se la coppia e' tra le K con DF piu' negativo sui Fdays precedenti (rifatta a inizio mese)."""
    ia = [lp.columns.get_loc(a) for a, b in pairs]; ib = [lp.columns.get_loc(b) for a, b in pairs]
    X = lp.to_numpy(); S = X[:, ia] - X[:, ib]; mask = np.zeros_like(S); idx = lp.index
    starts = np.where(idx.to_series().dt.to_period('M').ne(idx.to_series().dt.to_period('M').shift()).to_numpy())[0]
    n = Fdays * bars_per_day
    for j, s0 in enumerate(starts):
        if s0 < n: continue
        win = S[s0 - n:s0]; good = np.isfinite(win).all(0)
        if good.sum() < K: continue
        t = np.where(good, df_tstat(np.where(np.isfinite(win), win, 0.0)), np.inf)
        sel = np.argsort(t)[:K]; e = starts[j + 1] if j + 1 < len(starts) else len(S)
        mask[s0:e, sel] = 1.0
    return mask

def pair_pnl(p, f, pos, mask, ia, ib, K, fee=0.0007, lag=1):
    R = p.pct_change(fill_method=None).fillna(0.0).to_numpy(); Fn = f.to_numpy()
    w = pos * mask * (GROSS / K)                         # nozionale lordo per coppia attiva
    held = np.vstack([np.zeros((lag, w.shape[1])), w[:-lag]])
    pnl = (held * 0.5 * ((R[:, ia] - R[:, ib]) - (Fn[:, ia] - Fn[:, ib]))).sum(1)
    wl = np.vstack([np.zeros((lag - 1, w.shape[1])), w[:len(w) - (lag - 1)]]) if lag > 1 else w
    cost = np.abs(np.diff(wl, axis=0, prepend=0)).sum(1) * fee
    return daily(pd.Series(pnl - cost, index=p.index)), float(np.abs(held).sum(1).mean()), float(np.abs(np.diff(wl, axis=0, prepend=0)).sum() / len(w))

cache = {}
def run_pairs(freq, W, zin, zout, K, Fd=180, fee=0.0007, lag=1, fixed=None):
    p, f = prep(freq); lp = np.log(p); bpd = 24 if freq == '1h' else 1
    key = (freq, W, zin, zout)
    if key not in cache: cache[key] = pair_positions(lp, W, zin, zout)
    pos, ia, ib = cache[key]
    if fixed is not None:
        mask = np.zeros_like(pos); 
        for a, b in fixed: mask[:, pairs.index((a, b))] = 1.0
        K = len(fixed)
    elif K is None: mask = np.ones_like(pos); K = len(pairs)
    else:
        mk = (freq, K, Fd)
        if mk not in cache: cache[mk] = select_mask(lp, K, Fd, bpd)
        mask = cache[mk]
    return pair_pnl(p, f, pos, mask, ia, ib, K, fee, lag)

START = '2020-10-01'
print('== 2a. Coppie con selezione walk-forward mensile (DF su 180 giorni): griglia')
rows = []
for freq, Ws in (('1h', (48, 168, 336)), ('1D', (20, 40, 60))):
    for W in Ws:
        for zin in (1.5, 2.0, 2.5):
            for K in (5, 10, 20):
                r, expo, turn = run_pairs(freq, W, zin, 0.5, K); t = F.trial(f'coppie {freq} W{W} z{zin} K{K}', r.loc[START:])
                rows.append(dict(freq=freq, W=W, zin=zin, K=K, lordo_medio=round(expo, 2), turn_barra=round(turn, 4), **{a: t[a] for a in ('sh_tot', 'sh_sel', 'sh_ver', 'cagr_tot', 'vol_tot', 'dd_tot')}))
G = pd.DataFrame(rows); print(G.round(3).to_string(index=False))
for fq in ('1h', '1D'):
    g = G[G.freq == fq]; print(f'{fq}: Sharpe scelta mediano {g.sh_sel.median():.2f}, verifica mediano {g.sh_ver.median():.2f}, varianti con verifica>0: {100 * (g.sh_ver > 0).mean():.0f}%')
print('\n== 2a-bis. Varianti: uscita a z=0, finestra di formazione 90 giorni, tutte le 190 coppie senza selezione, lordo (senza costi)')
for freq, W in (('1h', 168), ('1D', 40)):
    F.line(f'coppie {freq} W{W} z2 K10 uscita z=0', run_pairs(freq, W, 2.0, 0.0, 10)[0].loc[START:])
    F.line(f'coppie {freq} W{W} z2 K10 formazione 90g', run_pairs(freq, W, 2.0, 0.5, 10, Fd=90)[0].loc[START:])
    F.line(f'coppie {freq} W{W} z2 tutte le 190 coppie', run_pairs(freq, W, 2.0, 0.5, None)[0].loc[START:])
    F.line(f'coppie {freq} W{W} z2 K10 SENZA costi (lordo)', run_pairs(freq, W, 2.0, 0.5, 10, fee=0.0)[0].loc[START:])
    F.line(f'coppie {freq} W{W} z2 K10 costi x2', run_pairs(freq, W, 2.0, 0.5, 10, fee=0.0014)[0].loc[START:])
    F.line(f'coppie {freq} W{W} z2 K10 ritardo +1', run_pairs(freq, W, 2.0, 0.5, 10, lag=2)[0].loc[START:])
    F.line(f'coppie {freq} W{W} z2 K10 maker 1,5 pb (IPOTESI)', run_pairs(freq, W, 2.0, 0.5, 10, fee=0.00015)[0].loc[START:])
print('\n== 2b. Coppie fisse')
for fx in ([('BTC', 'ETH')], [('ETH', 'SOL')], [('BTC', 'SOL')], [('BTC', 'ETH'), ('ETH', 'SOL'), ('BTC', 'SOL')]):
    for freq, W in (('1h', 168), ('1D', 40)):
        F.line(f'fissa {fx} {freq} W{W} z2', run_pairs(freq, W, 2.0, 0.5, None, fixed=fx)[0].loc[START:])

print('\n== 2c. Inversione dei residui rispetto al mercato (paniere equipesato), 20 perp')
def resid_rev(freq, h, beta_w, fee=0.0007, lag=1, mom=False):
    p, f = prep(freq); R = p.pct_change(fill_method=None); m = R.mean(axis=1)
    beta = R.rolling(beta_w, min_periods=beta_w // 2).cov(m).div(m.rolling(beta_w, min_periods=beta_w // 2).var(), axis=0)
    res = R - beta.mul(m, axis=0)
    sc = res.rolling(h).sum() / (res.rolling(beta_w, min_periods=beta_w // 2).std() * math.sqrt(h))
    sc = sc.sub(sc.mean(axis=1), axis=0); w = -sc if not mom else sc
    w = w.div(w.abs().sum(axis=1), axis=0).fillna(0.0) * GROSS
    k = np.arange(len(w)) % h == 0; w = w.where(pd.Series(k, index=w.index), np.nan).ffill().fillna(0.0)     # ribilancia ogni h barre
    held = w.shift(lag).fillna(0.0)
    pnl = (held * (R.fillna(0.0) - f)).sum(axis=1) - w.shift(lag - 1).diff().abs().sum(axis=1).fillna(0) * fee
    return daily(pnl)
rows = []
for freq, bw, hs in (('1h', 720, (1, 4, 12, 24)), ('4h', 180, (1, 3, 6)), ('1D', 60, (1, 3, 5, 10))):
    for h in hs:
        r = resid_rev(freq, h, bw).loc[START:]; t = F.trial(f'residui {freq} h{h}', r); rg = resid_rev(freq, h, bw, fee=0.0).loc[START:]; tg = F.trial(f'residui {freq} h{h} lordo', rg)
        rows.append(dict(freq=freq, h=h, sh_lordo=tg['sh_tot'], lordo_sel=tg['sh_sel'], lordo_ver=tg['sh_ver'], **{a: t[a] for a in ('sh_tot', 'sh_sel', 'sh_ver', 'cagr_tot', 'vol_tot', 'dd_tot')}))
print(pd.DataFrame(rows).round(3).to_string(index=False))
# candidato: scelto SOLO sul periodo di scelta tra le varianti nette
G2 = G.sort_values('sh_sel', ascending=False); b = G2.iloc[0]; print('\nmigliore coppie sulla SCELTA:', b.to_dict())
rb, _, _ = run_pairs(b.freq, int(b.W), float(b.zin), 0.5, int(b.K)); rb = rb.loc[START:]
F.line('PAIRS migliore-in-scelta', rb); F.line('PAIRS migliore-in-scelta costi x2', run_pairs(b.freq, int(b.W), float(b.zin), 0.5, int(b.K), fee=0.0014)[0].loc[START:]); F.line('PAIRS migliore-in-scelta ritardo +1', run_pairs(b.freq, int(b.W), float(b.zin), 0.5, int(b.K), lag=2)[0].loc[START:])
F.keep('PAIRS (migliore in scelta)', rb)
rd = resid_rev('1D', 5, 60).loc[START:]; F.keep('RESID-REV 1D h5', rd)
F.save()
