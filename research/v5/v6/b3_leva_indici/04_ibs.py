"""04 - Ritorno alla media IBS eseguito in ETP 3x/5x. SIMULATO.
Segnale: chiusura USA di t con IBS=(C-L)/(H-L) sotto soglia (ed eventualmente VIX>=20). Ingresso all'apertura USA di t+1
(l'ETP europeo si compra nella seduta europea del giorno dopo: l'apertura USA e' l'approssimazione), uscita all'apertura dopo la prima
chiusura con IBS>0,7 o dopo 5 sedute. Tutto il capitale nell'ETP quando c'e' il segnale, altrimenti cassa.
'MOC' = ingresso alla chiusura stessa di t: NON eseguibile con ETP quotati in Europa (Borsa Italiana chiude alle 17:30), solo con CFD/future."""
from lab import *
import itertools
U = underlying(); cash = U["cash"]; dc = U["dc"]
vix = y("^VIX")["close"]
SP = {1: (0.0007, 0.0, 0.0003), 3: (0.0075, 0.010, 0.0010), 5: (0.0075, 0.035, 0.0025)}
rows = []; keep = {}
for sym in ["QQQ", "SPY"]:
    d = y(sym); d = d[d.high > d.low]
    ibs = (d.close - d.low) / (d.high - d.low)
    r_cc = d.adj.pct_change(); r_on = d.open / d.close.shift(1) - 1
    r_on = r_on + (r_cc - (d.close / d.close.shift(1) - 1))      # dividendo nella notte
    idx = d.index; c = cash.reindex(idx).fillna(0); dcc = dc.reindex(idx).fillna(1); vx = vix.reindex(idx).ffill()
    for k, thr, vf, moc in itertools.product([1, 3, 5], [0.1, 0.2, 0.3], [0, 20], [False, True]):
        if moc and k != 3: continue
        ter, sp, cost = SP[k]
        fin = (k - 1) * (c + sp * dcc / 360) + ter * dcc / 365
        sig = (ibs < thr) & (vx >= vf); ex = ibs > 0.7
        n = len(idx); pos_close = np.zeros(n)   # 1 se in posizione alla chiusura di t
        inpos = False; held = 0; pend_in = False; pend_out = False
        ret = np.zeros(n); ntr = 0
        rc = r_cc.fillna(0).values; ro = r_on.fillna(0).values; f = fin.values; cs = c.values
        sg = sig.values; exv = ex.values
        for t in range(1, n):
            g_full = 1 + k * rc[t] - f[t]; g_on = 1 + k * ro[t]
            if g_full <= 0: g_full = 1e-9
            if g_on <= 0: g_on = 1e-9
            if inpos and pend_out:      # esco all'apertura di t
                ret[t] = g_on * (1 - cost) - 1; inpos = False; pend_out = False
            elif inpos:
                ret[t] = g_full - 1
            elif pend_in:               # entro all'apertura di t
                ret[t] = (g_full / g_on) * (1 - cost) - 1; inpos = True; pend_in = False; held = 0; ntr += 1
            else:
                ret[t] = cs[t] - 0.002 / 252
            if inpos:
                held += 1
                if moc:
                    if exv[t] or held >= 5: ret[t] = (1 + ret[t]) * (1 - cost) - 1; inpos = False   # esco in chiusura
                elif exv[t] or held >= 5: pend_out = True
            if not inpos and not pend_out and sg[t]:
                if moc: inpos = True; held = 0; ntr += 1; ret[t] = (1 + ret[t]) * (1 - cost) - 1
                else: pend_in = True
        r = pd.Series(ret, index=idx).iloc[1:]
        nm = f"IBS|{sym}|{k}x|<{thr}|VIX>={vf}|{'MOC(non ETP)' if moc else 'apertura'}"
        keep[nm] = r
        row = dict(nome=nm, trade_anno=ntr / (len(r) / 252), in_posizione=float((r != (c - 0.002 / 252).reindex(r.index)).mean()))
        for per, a, b in [("int", None, None), ("sel", None, SEL_END), ("ver", VER_START, None), ("pre08", None, "2007-12-31"), ("post08", "2008-01-01", None)]:
            s = stats(r.loc[a:b], cash)
            for kk in ("CAGR", "vol", "Sharpe", "maxDD", "mese_peggiore"): row[f"{per}_{kk}"] = s[kk]
        rows.append(row)
T = pd.DataFrame(rows).set_index("nome"); T.to_csv("04_tabella.csv"); pd.DataFrame(keep).to_parquet("_serie04.parquet")
print(f"varianti: {len(T)}")
print(f"{'variante':46s} {'tr/a':>5s} {'%pos':>5s} | {'CAGR int':>8s} {'vol':>6s} {'Sh':>5s} {'maxDD':>7s} {'mese-':>7s} | {'sel':>7s} {'Sh':>5s} {'DD':>7s} | {'ver':>7s} {'Sh':>5s} {'DD':>7s} | {'<=07':>7s} {'>=08':>7s}")
for nm, x in T.sort_values("sel_CAGR", ascending=False).iterrows():
    print(f"{nm:46s} {x.trade_anno:5.1f} {x.in_posizione*100:4.0f}% | {x.int_CAGR*100:7.1f}% {x.int_vol*100:5.1f}% {x.int_Sharpe:5.2f} {x.int_maxDD*100:6.1f}% {x.int_mese_peggiore*100:6.1f}% | {x.sel_CAGR*100:6.1f}% {x.sel_Sharpe:5.2f} {x.sel_maxDD*100:6.1f}% | {x.ver_CAGR*100:6.1f}% {x.ver_Sharpe:5.2f} {x.ver_maxDD*100:6.1f}% | {x.pre08_CAGR*100:6.1f}% {x.post08_CAGR*100:6.1f}%")
