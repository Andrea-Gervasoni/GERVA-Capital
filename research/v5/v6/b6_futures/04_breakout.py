"""B6 (2) - sistemi di rottura stile Turtle misurati come flusso di operazioni in R (stop a 2 ATR), barre giornaliere retro-rettificate.
Ingresso con ordine stop al massimo/minimo di n giorni (eseguito a max(apertura, livello)); stop iniziale 2N (N = ATR 20);
uscita al minimo/massimo opposto di m giorni; se nello stesso giorno si toccano ingresso e stop si assume lo stop (prudente).
Costi: costo_bp del mercato per lato (commissione + 1 tick) + 1 tick in piu' sugli stop."""
from engine import *
pd.set_option("display.width", 250)
B = Book(); spec = B.spec

def turtle(k, n, m, stopN=2.0, cmult=1.0, delay=0, sides=(1, -1)):
    p = B.P[k]; p = p[p.index >= "2000-06-01"]
    o, h, l, c = p.open.values, p.high.values, p.low.values, p.close.values
    tr = np.maximum(h[1:], c[:-1]) - np.minimum(l[1:], c[:-1]); tr = np.r_[h[0] - l[0], tr]
    N = pd.Series(tr).rolling(20).mean().shift(1).values           # ATR noto il giorno prima
    hi_n = pd.Series(h).rolling(n).max().shift(1 + delay).values; lo_n = pd.Series(l).rolling(n).min().shift(1 + delay).values
    hi_m = pd.Series(h).rolling(m).max().shift(1).values; lo_m = pd.Series(l).rolling(m).min().shift(1).values
    cb = float(spec.costo_bp[k]) / 1e4 * cmult
    out = []; pos = 0; i0 = max(n, 21) + 1 + delay
    for t in range(i0, len(c)):
        if pos == 0:
            if np.isnan(N[t]) or N[t] <= 0: continue
            up = h[t] > hi_n[t] and 1 in sides; dn = l[t] < lo_n[t] and -1 in sides
            if up and dn: continue
            if up or dn:
                pos = 1 if up else -1
                lvl = hi_n[t] if up else lo_n[t]
                entry = max(o[t], lvl) if up else min(o[t], lvl)
                risk = stopN * N[t]; stop = entry - pos * risk; t_in = t
                # stesso giorno: se il minimo (massimo) del giorno arriva allo stop, si assume stop preso
                if (pos == 1 and l[t] <= stop) or (pos == -1 and h[t] >= stop):
                    pnl = -risk - (2 * cb + cb) * entry
                    out.append((p.index[t], p.index[t], k, pos, risk / entry, pnl / risk, "stop_stesso_giorno")); pos = 0
            continue
        # in posizione
        ex = None
        if pos == 1:
            if o[t] <= stop: ex, why = o[t], "stop_gap"
            elif l[t] <= stop: ex, why = stop, "stop"
            elif l[t] < lo_m[t]: ex, why = min(o[t], lo_m[t]), "uscita_canale"
        else:
            if o[t] >= stop: ex, why = o[t], "stop_gap"
            elif h[t] >= stop: ex, why = stop, "stop"
            elif h[t] > hi_m[t]: ex, why = max(o[t], hi_m[t]), "uscita_canale"
        if ex is not None:
            pnl = pos * (ex - entry) - (2 * cb + (cb if why.startswith("stop") else 0)) * entry
            out.append((p.index[t_in], p.index[t], k, pos, risk / entry, pnl / risk, why)); pos = 0
    return out

def stream(n, m, **kw):
    tr = []
    for k in B.R.columns: tr += turtle(k, n, m, **kw)
    return pd.DataFrame(tr, columns=["entry", "exit", "symbol", "side", "stop_dist", "R", "why"]).sort_values("entry").reset_index(drop=True)

def summ(T, name):
    d = {"sistema": name}
    yrs = (T.entry.max() - T.entry.min()).days / 365.25
    # operazioni simultanee su mercati correlati non sono indipendenti: stima N effettivo dai rendimenti mensili aggregati
    for lab, (a, b) in PERIODS.items():
        x = T[(T.entry >= (a or "1900")) & (T.entry <= (b or "2100"))].R
        d[f"R_{lab}"] = x.mean() if len(x) > 30 else np.nan
    x = T.R
    d.update(n=len(x), n_anno=len(x) / yrs, vincenti=(x > 0).mean() * 100, R_medio=x.mean(), sd=x.std(), t=x.mean() / x.std() * np.sqrt(len(x)),
             rapp=x.mean() / x.std(), N_rapp2=len(x) / yrs * (x.mean() / x.std()) ** 2)
    mo = T.groupby([T.exit.dt.year, T.exit.dt.month]).R.sum()   # R mensile sommato: tiene conto della correlazione tra operazioni simultanee
    d["Sharpe_R_mensile"] = mo.mean() / mo.std() * np.sqrt(12)
    return d
rows = []; KEEP = {}
for nm, n, m, kw in [("Turtle S1 20/10", 20, 10, {}), ("Turtle S2 55/20", 55, 20, {}), ("Lento 120/40", 120, 40, {}), ("Lento 250/60", 250, 60, {}),
                     ("S2 55/20 costi x2", 55, 20, dict(cmult=2)), ("S2 55/20 ritardo +1 barra", 55, 20, dict(delay=1)), ("S2 55/20 solo lungo", 55, 20, dict(sides=(1,))),
                     ("S2 55/20 solo corto", 55, 20, dict(sides=(-1,))), ("S2 55/20 stop 1N", 55, 20, dict(stopN=1.0)), ("S2 55/20 stop 3N", 55, 20, dict(stopN=3.0)),
                     ("Lento 250/60 costi x2", 250, 60, dict(cmult=2)), ("Lento 250/60 ritardo +1 barra", 250, 60, dict(delay=1))]:
    T = stream(n, m, **kw); rows.append(summ(T, nm)); KEEP[nm] = T
print("== Flusso di operazioni in R, 37 mercati, 2000-2026 =="); print(pd.DataFrame(rows).set_index("sistema").round(3).to_string())
print("varianti contate: %d" % len(rows))
T = KEEP["Turtle S2 55/20"]
print("\nS2 55/20 per settore:"); T["sec"] = T.symbol.map(B.spec.sotto)
print(T.groupby("sec").R.agg(["count", "mean", "std"]).assign(t=lambda x: x["mean"] / x["std"] * np.sqrt(x["count"])).round(3).to_string())
print("\nS2 55/20 per anno (R medio, n):"); g = T.groupby(T.entry.dt.year).R.agg(["mean", "count"]); print({int(y): (round(a, 2), int(b)) for y, a, b in zip(g.index, g["mean"], g["count"])})
print("\nmotivi di uscita:", T.why.value_counts().to_dict(), " distanza media dello stop %.2f%% -> leva massima teorica (stop entro il 60%% della liquidazione) %.1fx" % (T.stop_dist.mean() * 100, 1 / (T.stop_dist.median() / 0.6 + 0.005)))
T.drop(columns="sec").to_parquet("trades.parquet")
