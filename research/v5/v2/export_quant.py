"""Esporta in research/v5/quant.json i risultati di ricerca che la dashboard mostra nelle pagine per esperti.
Tutti i numeri sono SIMULATI. Va rieseguito dopo `python -m gerva research` e dopo gli script di research/v5/v2/."""
import json, math, sys
import numpy as np, pandas as pd
sys.path.insert(0, ".")
from gerva.validation import metrics as M
C = sys.argv[1] if len(sys.argv) > 1 else "/tmp/lab2"
res = json.load(open("research/v5/results.json"))
D = pd.read_parquet("research/v5/series.parquet")
S = D[["CR-TREND", "CR-XSMOM", "EQ-MR", "MA-TREND"]]; rf = D["RF"]; port = D["PORT"].dropna()
def clean(o):
    if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, (float, np.floating)): return None if not math.isfinite(o) else round(float(o), 6)
    if isinstance(o, (np.integer,)): return int(o)
    return o
mc = pd.read_pickle(f"{C}/mc_nobreaker.pkl")
lev = [dict(schema=n, scenario=s, **mc.loc[(n, s)].to_dict()) for n, s in mc.index]
conv = pd.read_pickle(f"{C}/conv.pkl"); ct = []
for a, df in conv.items():
    per = 365 if a in ("BTC", "ETH") else 252
    for lab, sl in (("scelta", slice(None, "2022-12-31")), ("verifica", slice("2023-01-01", None))):
        for t, g in df.loc[sl].groupby("tier"):
            ct.append(dict(asset=a, periodo=lab, tier=t, n=len(g), media_pb=g.nxt.mean() * 1e4, hit=(g.nxt > 0).mean(), sharpe=g.nxt.mean() / g.nxt.std() * math.sqrt(per)))
roll = lambda r, w: (r.rolling(w).mean() / r.rolling(w).std() * math.sqrt(365)).dropna()
m = ((1 + S).resample("ME").prod() - 1)
eq = (1 + port).cumprod()
sims = np.random.default_rng(7); x = port.to_numpy(); n = 365 * 3
idx = sims.integers(0, len(x) - 30, (2000, n // 30 + 1)); paths = np.concatenate([x[i:i + 30] for row in idx[:400] for i in row]).reshape(400, -1)[:, :n]
fan = {}
for L in (1, 2, 3, 5, 10):
    e = np.cumprod(1 + np.maximum(L * paths - max(L - 1, 0) * (0.04 + 0.015) / 365, -1), axis=1)[:, ::15]
    fan[str(L)] = {f"p{q}": np.quantile(e, q / 100, axis=0).tolist() for q in (5, 25, 50, 75, 95)}
out = dict(
    generated=pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"), label="SIMULATO: ricerca su dati storici",
    sleeves=[dict(id=k, **{p: M.summary(S[k].loc[sl], rf, 365) for p, sl in (("tutto", slice(None, None)), ("scelta", slice(None, "2022-12-31")), ("verifica", slice("2023-01-01", None)))}) for k in S],
    portfolio={p: M.summary(port.loc[sl], rf, 365) for p, sl in (("tutto", slice(None, None)), ("scelta", slice(None, "2022-12-31")), ("verifica", slice("2023-01-01", None)))},
    correlation=dict(labels=list(S.columns), matrix=m.corr().round(3).values.tolist()),
    weights=[dict(t=str(d.date()), **{k[2:]: float(v) for k, v in row.items()}) for d, row in D[[c for c in D if c.startswith("W_")]].dropna().iloc[::30].iterrows()],
    sleeve_curves=[dict(t=str(d.date()), **{k: float(v) for k, v in row.items()}) for d, row in (1 + S).cumprod().iloc[::7].iterrows()],
    rolling_sharpe=[dict(t=str(d.date()), v=float(v)) for d, v in roll(port - rf.reindex(port.index).fillna(0), 365).iloc[::7].items()],
    drawdown=[dict(t=str(d.date()), v=float(v)) for d, v in (eq / eq.cummax() - 1).iloc[::3].items()],
    return_hist=dict(edges=np.linspace(-0.04, 0.04, 41).tolist(), counts=np.histogram(port, bins=np.linspace(-0.04, 0.04, 41))[0].tolist()),
    leverage_mc=lev, leverage_fan=dict(step_days=15, years=3, levels=fan),
    leverage_decision=dict(operativa=2.0, tetto=3.0, rischio_trade={"media": 0.005, "alta": 0.01}, legal_max={"indici": 20, "cambi": 30, "azioni": 5, "crypto": 2}),
    conviction=ct, robustness=res.get("robustezza"), significance=res.get("significativita"), walk_forward=res.get("walk_forward"),
    gex_quintiles=res.get("gex_quintili"), funding_by_year=res.get("funding_annuo_pct"), trials=res.get("prove"),
    scenarios=[dict(nome="Ottimista", cagr=0.43, definizione="95° percentile dello scenario base a leva 2x"), dict(nome="Base", cagr=0.23, definizione="mediana: la storia si ripete"),
               dict(nome="Pessimista", cagr=0.10, definizione="mediana con metà del rendimento del backtest"), dict(nome="Di coda", cagr=-0.06, definizione="5° percentile dello scenario pessimista")],
    rejected=[dict(nome="GEX come segnale di direzione", esito="Prevede la volatilità, non la direzione; nessuna regola batte il comprare e tenere"),
              dict(nome="VWAP trend", esito="Perde prima dei costi su 24 azioni e su Bitcoin"), dict(nome="Momentum intraday (zona di rumore)", esito="1,2 punti base lordi al giorno: bastano 0,6 di costo per azzerarlo"),
              dict(nome="Ultima mezz'ora con GEX basso", esito="Sharpe 1,38 nel 2011-18, segno invertito nel 2023-26"), dict(nome="Kronos (modello fondazionale)", esito="Banda '80%' che contiene il prezzo nel 29-63% dei casi; nessun vantaggio dopo i costi"),
              dict(nome="Acquisti dei dirigenti (Form 4)", esito="Rendimento medio per operazione zero su 2.801 operazioni"), dict(nome="Vendere volatilità", esito="Rischio di coda non controllabile (−83% in un giorno nel 2018)"),
              dict(nome="Carry sui perpetual", esito="Funding sceso dal 30-40% (2021) al 2-5% (2025-26)"), dict(nome="Regime per ridurre l'esposizione", esito="Sharpe da 1,18 a 1,10"),
              dict(nome="Leva del conto a livelli di conviction", esito="Peggio della leva fissa a parità di leva media")])
json.dump(clean(out), open("research/v5/quant.json", "w"), separators=(",", ":"))
print("scritto research/v5/quant.json", round(len(open("research/v5/quant.json").read()) / 1024), "KB")
