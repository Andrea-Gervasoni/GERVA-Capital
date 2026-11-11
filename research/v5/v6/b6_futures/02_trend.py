"""B6 (1) - momentum su serie temporali: orizzonti 1/3/12 mesi, incroci EWMA, Donchian. Volatilita' obiettivo 10% (unita')."""
from engine import *
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
B = Book()
print("mercati:", len(B.R.columns), " periodo:", B.R.index[0].date(), "->", B.R.index[-1].date())
SIG = {}
for k in (21, 63, 252): SIG[f"TSMOM{k}"] = B.sig_tsmom(k)
for f in (4, 8, 16, 32, 64): SIG[f"EWMAC{f}/{4*f}"] = B.sig_ewmac(f)
for n in (20, 55, 120, 250): SIG[f"DONCH{n}"] = B.sig_donchian(n)
rows = []; SER = {}
for name, s in SIG.items():
    net, gross, Wf, info = B.run(B.weights(s))
    rows.append(line(name, net, gross, info)); SER[name] = net
# miscele predefinite (non scelte sul risultato): media dei segnali
def blend(names): return sum(SIG[n].fillna(0) / (SIG[n].abs().mean().mean()) for n in names) / len(names)
BL = {"TREND_TSMOM(1,3,12m)": ["TSMOM21", "TSMOM63", "TSMOM252"], "TREND_EWMAC(8..64)": ["EWMAC8/32", "EWMAC16/64", "EWMAC32/128", "EWMAC64/256"],
      "TREND_DONCH(20..250)": ["DONCH20", "DONCH55", "DONCH120", "DONCH250"], "TREND_TUTTI": list(SIG)}
for name, ns in BL.items():
    s = blend(ns).where(B.active); SIG[name] = s
    net, gross, Wf, info = B.run(B.weights(s))
    rows.append(line(name, net, gross, info)); SER[name] = net
T = pd.DataFrame(rows).set_index("strategia")
print("\n== Sharpe netto per periodo (vol obiettivo 10%, ritardo: decisione chiusura t, esecuzione chiusura t+1) =="); print(T.round(2).to_string())
print("varianti contate: %d" % len(T))

# robustezza della miscela TREND_TUTTI
s = SIG["TREND_TUTTI"]; W = B.weights(s); rows = []
for nm, kw in [("base", {}), ("costi x2", dict(cmult=2)), ("costi x4", dict(cmult=4)), ("ritardo +1 giorno", dict(lag=3)), ("esecuzione stessa chiusura (ottimista)", dict(lag=1)),
               ("zona di non intervento 20%", dict(buffer=0.2)), ("zona 20% + costi x2", dict(buffer=0.2, cmult=2))]:
    net, gross, Wf, info = B.run(W, **kw); rows.append(line("TREND_TUTTI " + nm, net, gross, info))
    if nm == "zona di non intervento 20%": SER["TREND_TUTTI_buf"] = net
# senza singoli settori
SUBS = B.spec.sotto
for sec in SUBS.unique():
    m = SUBS[SUBS != sec].index
    net, gross, Wf, info = B.run(B.weights(s[m].reindex(columns=B.R.columns)))
    rows.append(line(f"TREND_TUTTI senza {sec}", net, gross, info))
for sec in SUBS.unique():
    m = SUBS[SUBS == sec].index
    net, gross, Wf, info = B.run(B.weights(s[m].reindex(columns=B.R.columns)))
    rows.append(line(f"TREND_TUTTI solo {sec}", net, gross, info))
# universo dei soli micro (senza coloniali e carni, che esistono solo a contratto intero)
Bm = Book(only_micro=True)
Sm = {}
for k in (21, 63, 252): Sm[f"TSMOM{k}"] = Bm.sig_tsmom(k)
for f in (4, 8, 16, 32, 64): Sm[f"EWMAC{f}/{4*f}"] = Bm.sig_ewmac(f)
for n in (20, 55, 120, 250): Sm[f"DONCH{n}"] = Bm.sig_donchian(n)
sm = (sum(Sm[n].fillna(0) / (Sm[n].abs().mean().mean()) for n in Sm) / len(Sm)).where(Bm.active)
for nm, kw in [("base", {}), ("costi x2", dict(cmult=2)), ("ritardo +1", dict(lag=3)), ("zona 20%", dict(buffer=0.2))]:
    net, gross, Wf, info = Bm.run(Bm.weights(sm), **kw); rows.append(line("TREND_TUTTI solo micro (31 mercati) " + nm, net, gross, info))
    if nm == "base": SER["TREND_TUTTI_micro"] = net
# solo lungo / solo corto
for nm, ss in [("solo lungo", s.clip(lower=0)), ("solo corto", s.clip(upper=0))]:
    net, gross, Wf, info = B.run(B.weights(ss), voltarget=False); rows.append(line("TREND_TUTTI " + nm + " (senza riscalatura)", net, gross, info))
print("\n== Robustezza TREND_TUTTI =="); print(pd.DataFrame(rows).set_index("strategia").round(2).to_string())

# obiettivi di volatilita'
print("\n== TREND_TUTTI a diversi obiettivi di volatilita' (netto) ==")
rows = []
for tv in (0.10, 0.15, 0.25, 0.40, 0.60):
    net, gross, Wf, info = B.run(W, target=tv)
    marg = (Wf.abs() * B.spec.margine.astype(float)).sum(axis=1)
    d = line(f"vol {int(tv*100)}%", net, gross, info); d["margine_medio"] = marg.loc[net.index[0]:].mean(); d["margine_p99"] = marg.loc[net.index[0]:].quantile(.99)
    m = (1 + net).groupby([net.index.year, net.index.month]).prod() - 1
    d["mese_mediano%"] = m.median() * 100; d["mese_peggiore%"] = m.min() * 100; d["rovina(<-90%)"] = bool(((1 + net).cumprod() / (1 + net).cumprod().cummax() - 1).min() < -0.9)
    rows.append(d)
print(pd.DataFrame(rows).set_index("strategia")[["S_tutto", "S_selezione", "S_verifica", "cagr", "vol", "mdd", "skew_m", "leva", "costo", "margine_medio", "margine_p99", "mese_mediano%", "mese_peggiore%"]].round(2).to_string())

# tabella per decennio completa per la miscela
print("\n== TREND_TUTTI (10% vol) per periodo =="); print(fmt(table(SER["TREND_TUTTI"])).to_string())
# per anno
y = SER["TREND_TUTTI"]; print("\nper anno (%):", ((1 + y).groupby(y.index.year).prod() - 1).mul(100).round(1).to_dict())

# controllo di troncamento: i pesi a T ricalcolati su dati tagliati a T devono coincidere
print("\n== Controllo di troncamento ==")
_, _, Wfull, _ = B.run(W)
for T0 in ("2008-10-15", "2016-03-01", "2024-06-28"):
    Bt = Book(end=T0); st = sum((getattr(Bt, "sig_" + a)(b)).fillna(0) for a, b in [])  # placeholder
    S2 = {}
    for k in (21, 63, 252): S2[f"TSMOM{k}"] = Bt.sig_tsmom(k)
    for f in (4, 8, 16, 32, 64): S2[f"EWMAC{f}/{4*f}"] = Bt.sig_ewmac(f)
    for n in (20, 55, 120, 250): S2[f"DONCH{n}"] = Bt.sig_donchian(n)
    # stessa normalizzazione della miscela: usa i fattori calcolati sul campione intero? No: la normalizzazione e' una costante di scala,
    # la confrontiamo a meno di una costante positiva (correlazione dei pesi = 1 e stesso segno)
    s2 = (sum(S2[n].fillna(0) / (S2[n].abs().mean().mean()) for n in S2) / len(S2)).where(Bt.active)
    w2 = Bt.weights(s2).iloc[-1]; w1 = W.loc[T0]
    print(T0, "corr pesi %.6f" % np.corrcoef(w1, w2)[0, 1], " segni uguali:", bool((np.sign(w1) == np.sign(w2)).all()), " rapporto mediano %.4f" % (w2[w1 != 0] / w1[w1 != 0]).median())
pd.DataFrame(SER).to_parquet("serie_trend.parquet")
