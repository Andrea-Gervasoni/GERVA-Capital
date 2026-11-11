"""A8 - 04: PREVISIONE DIRETTA del segno del rendimento a 4h e 24h su barre orarie (perpetual Binance USDT-M, BTC/ETH/SOL).
Feature note alla chiusura della barra t; ingresso all'apertura della barra t+1; etichetta = segno di open[t+1+h]/open[t+1]-1.
Walk-forward semestrale a finestra crescente, purga+embargo 7 giorni. Iper-parametri scelti su 2021-2022 (training dal 2020)."""
import json, time, sys
from ml import *
from sklearn.metrics import roc_auc_score
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
SELB = pd.date_range('2021-01-01', '2022-07-01', freq='6MS'); VERB = VER_BLOCKS; COST = 2 * FEE

def hfeat(c, H, HS, dt, cut=None):
    h = H[c] if cut is None else H[c][H[c].index < cut]; s = HS[c].reindex(h.index); cl = h['close']; lr = np.log(cl).diff(); X = pd.DataFrame(index=h.index)
    for k in (1, 2, 4, 8, 12, 24, 48, 72, 168): X[f'r{k}'] = np.log(cl / cl.shift(k))
    v24 = lr.rolling(24).std(); v168 = lr.rolling(168).std(); X['v24'] = v24; X['v168'] = v168; X['vr'] = v24 / v168
    X['z4'] = X['r4'] / (v168 * 2); X['z24'] = X['r24'] / (v168 * np.sqrt(24))
    atr = ((h['high'] - h['low']) / cl).rolling(24).mean(); X['atr_pct'] = atr.rolling(720, min_periods=240).rank(pct=True)
    for k in (24, 168):
        hh = h['high'].rolling(k).max(); ll = h['low'].rolling(k).min(); X[f'pos{k}'] = (cl - ll) / (hh - ll)
    lq = np.log(h['quote_volume'].replace(0, np.nan)); X['vol_z'] = (lq - lq.rolling(168).mean()) / lq.rolling(168).std()
    for k in (1, 4, 24): X[f'tk{k}'] = 2 * h['taker_quote'].rolling(k).sum() / h['quote_volume'].rolling(k).sum() - 1
    X['tk_spot4'] = 2 * s['taker_quote'].rolling(4).sum() / s['quote_volume'].rolling(4).sum() - 1
    X['trsize'] = np.log(h['quote_volume'] / h['trades'].replace(0, np.nan)); X['trsize'] -= X['trsize'].rolling(168).mean()
    b = (cl / s['close'] - 1) * 1e4; X['basis'] = b; X['basis_ch24'] = b - b.shift(24); X['basis_z'] = (b - b.rolling(168).mean()) / b.rolling(168).std()
    f = st.get(f'bn_fund_{c}USDT').iloc[:, 0]; f.index = f.index.floor('h'); f = f[~f.index.duplicated()]
    X['fund'] = f.reindex(h.index, method='ffill') * 3 * 365; X['fund7'] = f.rolling(21).mean().reindex(h.index, method='ffill') * 3 * 365
    m = st.get(f'v4_metrics_1h_{c}').reindex(h.index); oi = m['sum_open_interest']
    X['oi1'] = np.log(oi / oi.shift(1)); X['oi24'] = np.log(oi / oi.shift(24)); X['top_ls'] = m['sum_toptrader_long_short_ratio']; X['tk_ls'] = np.log(m['sum_taker_long_short_vol_ratio'].clip(0.05, 20))
    X['ls_ch24'] = m['count_long_short_ratio'] / m['count_long_short_ratio'].shift(24) - 1
    day = h.index.normalize() - pd.Timedelta(days=1)                         # dati giornalieri: solo fino al giorno prima
    dv = dt.dvol['ETH' if c == 'ETH' else 'BTC']; X['dvol'] = dv.shift(1).reindex(h.index.normalize(), method='ffill').values   # candela DVOL del giorno prima
    X['vrp'] = X['dvol'] / 100 - v168 * np.sqrt(24 * 365)
    spy = dt.y['SPY']['adj']; X['spy5'] = np.log(spy / spy.shift(5)).reindex(day, method='ffill').values; X['vix'] = dt.y['^VIX']['close'].reindex(day, method='ffill').values
    if c != 'BTC':
        bc = H['BTC']['close'].reindex(h.index)
        for k in (1, 4, 24): X[f'btc_r{k}'] = np.log(bc / bc.shift(k))
        X['rel24'] = X['r24'] - X['btc_r24']
    else:
        ec = H['ETH']['close'].reindex(h.index)
        for k in (1, 4, 24): X[f'btc_r{k}'] = np.log(ec / ec.shift(k))          # per BTC: lo stato di ETH
        X['rel24'] = X['r24'] - X['btc_r24']
    X = X.replace([np.inf, -np.inf], np.nan)
    X['hour'] = h.index.hour; X['dow'] = h.index.dayofweek; X['h8'] = h.index.hour % 8; X['coin_id'] = COINS.index(c)
    return X

def build():
    dt = Data(); H = {c: st.get(f'v5_a8_um_1h_{c}') for c in COINS}; HS = {c: st.get(f'v5_a8_spot_1h_{c}') for c in COINS}; out = []
    for c in COINS:
        h = H[c]; X = hfeat(c, H, HS, dt); op = h['open']
        for k in (4, 24): X[f'y{k}'] = np.log(op.shift(-1 - k) / op.shift(-1))      # rendimento da open[t+1] a open[t+1+k]
        X['sig'] = np.log(h['close']).diff().rolling(168).std(); X['coin'] = c; X['date'] = h.index
        out.append(X.iloc[200:])
    # controllo di troncamento
    bad = 0
    for cut in pd.to_datetime(['2021-05-03 07:00', '2023-08-19 13:00', '2025-02-02 22:00']):
        for c in COINS:
            Hc = {k: v[v.index < cut] for k, v in H.items()}; HSc = {k: v[v.index < cut] for k, v in HS.items()}
            a = hfeat(c, Hc, HSc, Data(cut)).iloc[-48:]; b = hfeat(c, H, HS, dt).reindex(a.index)
            bad += int(((a - b).abs().max().max() > 1e-9) or (a.isna() != b.isna()).sum().sum() > 0)
    print('controllo di troncamento (9 casi): diversi =', bad)
    return pd.concat(out).sort_values(['date', 'coin']).reset_index(drop=True), H

def walk_h(D, feats, cfg, blocks, ycol):
    X = D[feats].values.astype(np.float32); y = D[ycol].values; dts = D['date'].values; p = np.full(len(D), np.nan); ok = np.isfinite(y)
    for b in blocks:
        tr = (dts < np.datetime64(b - PURGE - EMB)) & ok; te = (dts >= np.datetime64(b)) & (dts < np.datetime64(b + pd.DateOffset(months=6)))
        if te.sum() == 0: continue
        p[te], _ = fit_pred(cfg, X[tr], (y[tr] > 0).astype(int), y[tr], X[te])
    return p

def trades_h(D, H, p, k, q, blocks, cm=1.0, delay=0, mult=2.0, sides=(1, -1)):
    """Libro eseguibile: per coin, se flat e p >= soglia alta -> long, p <= soglia bassa -> short; si tiene k ore; stop a mult*sigma*sqrt(k)
    sul percorso orario (gap = apertura). Soglie ex-ante: quantili q e 1-q delle previsioni OOS dei blocchi PRECEDENTI."""
    out = []; dts = D['date'].values
    for bi, b in enumerate(blocks):
        prev = np.isfinite(p) & (dts < np.datetime64(b)) & (dts >= np.datetime64(blocks[0]))
        if bi == 0 or prev.sum() < 1000: continue
        hi, lo = np.quantile(p[prev], q), np.quantile(p[prev], 1 - q)
        for c in COINS:
            h = H[c]; m = (D.coin == c).values & (dts >= np.datetime64(b)) & (dts < np.datetime64(b + pd.DateOffset(months=6)))
            d = D[m]; pos = h.index.get_indexer(d['date']); pv = p[m]; sg = d['sig'].values
            op, hh, ll = h['open'].values, h['high'].values, h['low'].values; f = st.get(f'bn_fund_{c}USDT').iloc[:, 0]; f.index = f.index.floor('h'); fr = f[~f.index.duplicated()].reindex(h.index).fillna(0).values
            nxt = -1
            for i in range(len(d)):
                t = pos[i]
                if t <= nxt or not np.isfinite(pv[i]) or not np.isfinite(sg[i]): continue
                side = 1 if pv[i] >= hi else (-1 if pv[i] <= lo else 0)
                if side == 0 or side not in sides: continue
                a = t + 1 + delay; z = a + k
                if z >= len(op): continue
                sd = float(np.clip(mult * sg[i] * np.sqrt(k), 0.003, 0.15)); L = levmax(sd); p0 = op[a]; stp = p0 * (1 - side * sd); ex = op[z]; why = 'tempo'; e = z
                for j in range(a, z):
                    if side * ((ll[j] if side == 1 else hh[j]) - stp) <= 0:
                        ex = (min(stp, op[j]) if side == 1 else max(stp, op[j])) * (1 - side * STOPSLIP * cm); why = 'stop'; e = j; break
                fu = fr[a:e + 1].sum() * side; net = max(side * (ex / p0 - 1) - COST * cm - fu, -1 / L)
                out.append(dict(coin=c, entry=h.index[a], exit=h.index[e], side=side, s=sd, L=L, R=net / sd, ret=net, why=why, p=pv[i])); nxt = e
    return pd.DataFrame(out)

if __name__ == '__main__':
    t0 = time.time(); D, H = build(); F = [k for k in D.columns if k not in ('y4', 'y24', 'sig', 'coin', 'date')]
    print('righe', len(D), 'feature', len(F), f'{time.time()-t0:.0f}s')
    GRID = [dict(kind='logit', C=C) for C in (0.0003, 0.01)] + [dict(kind='hgbc', depth=3, iters=n, leaf=l) for n in (100, 300) for l in (500, 3000)]
    res = {}; ntr = 0
    for k in (4, 24):
        y = D[f'y{k}'].values; rows = []
        print(f'\n===== ORIZZONTE {k}h =====\n-- scelta iper-parametri (blocchi OOS 2021-2022), criterio: AUC medio per blocco --')
        for cfg in GRID:
            p = walk_h(D, F, cfg, SELB, f'y{k}'); aucs = []
            for b in SELB:
                m = (D.date >= b).values & (D.date < b + pd.DateOffset(months=6)).values & np.isfinite(p) & np.isfinite(y) & (D.date < SPL - pd.Timedelta(hours=k + 2)).values
                aucs.append(roc_auc_score(y[m] > 0, p[m]))
            rows.append(dict(cfg=json.dumps({a: b for a, b in cfg.items()}), auc=np.mean(aucs), auc_min=np.min(aucs), _cfg=cfg)); ntr += 1
        G = pd.DataFrame(rows); print(G.drop(columns='_cfg').round(4).to_string(index=False)); cfg = G.loc[G.auc.idxmax(), '_cfg']; print('CONGELATA:', cfg)
        p = walk_h(D, F, cfg, list(SELB) + list(VERB), f'y{k}'); res[k] = p
        print('-- qualita della previsione per periodo (OOS) --'); rows = []
        for lab, m0 in (('scelta 2021-22', (D.date < SPL - pd.Timedelta(hours=k + 2)).values), ('verifica 2023-26', (D.date >= SPL).values)):
            m = m0 & np.isfinite(p) & np.isfinite(y)
            rows.append(dict(per=lab, n=m.sum(), auc=roc_auc_score(y[m] > 0, p[m]), acc=((p[m] > 0.5) == (y[m] > 0)).mean(), quota_up=(y[m] > 0).mean(), ic=spearmanr(p[m], y[m])[0]))
        print(pd.DataFrame(rows).round(4).to_string(index=False))
        m = (D.date >= SPL).values & np.isfinite(p) & np.isfinite(y); q = pd.qcut(pd.Series(p[m]).rank(method='first'), 10, labels=False).values + 1
        x = pd.DataFrame(dict(q=q, p=p[m], y=y[m])); g = x.groupby('q').agg(n=('y', 'size'), p=('p', 'mean'), su=('y', lambda v: (v > 0).mean()), rend_lordo_bp=('y', lambda v: v.mean() * 1e4))
        g['netto_long_bp'] = g.rend_lordo_bp - COST * 1e4; g['netto_short_bp'] = -g.rend_lordo_bp - COST * 1e4
        print(f'-- VERIFICA: rendimento a {k}h per decile di probabilita (barre sovrapposte; costo andata+ritorno {COST*1e4:.0f} bp, funding escluso) --'); print(g.round(3).to_string())
        ya = pd.DataFrame(dict(a=D.date.dt.year[m], p=p[m], y=y[m])).groupby('a').apply(lambda v: pd.Series(dict(auc=roc_auc_score(v.y > 0, v.p), ic=spearmanr(v.p, v.y)[0]))); print('per anno:', ya.round(3).to_dict('index'))
        print('-- libro eseguibile (non sovrapposto, stop 2*sigma*sqrt(h), soglie ex-ante) --'); rows = []
        for q_ in (0.9, 0.97):
            T = trades_h(D, H, p, k, q_, list(SELB) + list(VERB)); ntr += 1
            if q_ == 0.9: T.to_parquet(HERE + f'/trades_hourly_{k}h.parquet')
            for lab, x in (('scelta', T[T.entry < SPL]), ('verifica', T[T.entry >= SPL])):
                yrs = (x.entry.max() - x.entry.min()).days / 365.25; s = rstats(x.R); rows.append(dict(q=q_, per=lab, **s, per_anno=s['n'] / yrs, long=(x.side == 1).mean(), stop=(x.why == 'stop').mean(), costo_R=(COST / x.s).mean(), NxIR2=s['n'] / yrs * s['ir'] ** 2 * np.sign(s['ir'])))
            xv = lambda T: T[T.entry >= SPL].R
            rows.append(dict(q=q_, per='verifica costi x2', **rstats(xv(trades_h(D, H, p, k, q_, list(SELB) + list(VERB), cm=2.0)))))
            rows.append(dict(q=q_, per='verifica ritardo +1 barra', **rstats(xv(trades_h(D, H, p, k, q_, list(SELB) + list(VERB), delay=1)))))
            Tg = T[T.entry >= SPL]; rows.append(dict(q=q_, per='verifica LORDO costi', **rstats(Tg.R + COST / Tg.s)))
        print(pd.DataFrame(rows).round(3).to_string(index=False))
        print('-- POST-HOC (deciso dopo aver visto la verifica: vale solo come descrizione): solo LONG, q=0.9 --'); rows = []
        T = trades_h(D, H, p, k, 0.9, list(SELB) + list(VERB), sides=(1,)); ntr += 1
        for lab, x in (('scelta', T[T.entry < SPL]), ('verifica', T[T.entry >= SPL])):
            yrs = (x.entry.max() - x.entry.min()).days / 365.25; s = rstats(x.R); rows.append(dict(per=lab, **s, per_anno=s['n'] / yrs, NxIR2=s['n'] / yrs * s['ir'] ** 2 * np.sign(s['ir'])))
        rows.append(dict(per='verifica costi x2', **rstats(trades_h(D, H, p, k, 0.9, list(SELB) + list(VERB), cm=2.0, sides=(1,)).loc[lambda x: x.entry >= SPL].R)))
        rows.append(dict(per='verifica: long a caso stesse ore (deriva)', R=float(np.nanmean((D[f'y{k}'].values - COST)[(D.date >= SPL).values] / np.clip(2 * D['sig'].values * np.sqrt(k), 0.003, 0.15)[(D.date >= SPL).values]))))
        print(pd.DataFrame(rows).round(3).to_string(index=False))
    pd.DataFrame(dict(p4=res[4], p24=res[24], coin=D.coin, date=D.date)).to_parquet(HERE + '/preds_hourly.parquet')
    print(f'\nvarianti provate in questo script: {ntr}  ({time.time()-t0:.0f}s)')
