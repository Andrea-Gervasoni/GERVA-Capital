"""B6 - diagnosi: (a) quanto contano i salti di roll (serie grezza contro ripulita); (b) da dove viene il 2020; (c) operazioni estreme del breakout;
(d) effetto del tenere il contratto fino a scadenza (autocorrelazione delle carni)."""
from engine import *
pd.set_option("display.width", 250)
B = Book()
def trend_sig(B):
    S = {}
    for k in (21, 63, 252): S[f"T{k}"] = B.sig_tsmom(k)
    for f in (4, 8, 16, 32, 64): S[f"E{f}"] = B.sig_ewmac(f)
    for n in (20, 55, 120, 250): S[f"D{n}"] = B.sig_donchian(n)
    return (sum(S[n].fillna(0) / S[n].abs().mean().mean() for n in S) / len(S)).where(B.active)
tr = trend_sig(B); net, gross, Wf, info = B.run(B.weights(tr))
print("(a) TREND_TUTTI su serie ripulite:", {k: round(v, 2) for k, v in line("x", net).items() if k.startswith("S_")})
# stessa strategia calcolata e valutata sulle serie GREZZE Yahoo (salti di roll dentro i rendimenti)
B2 = Book(); idx = B2.R.index
for k in B2.R.columns:
    if k.endswith("=F"):
        d = clean_bars(raw(k)); r = d.close.pct_change().iloc[1:].reindex(idx); first = d.index[1]
        r[(idx >= first) & r.isna()] = 0.0; B2.R[k] = r
v = B2.R.ewm(span=60, min_periods=40).std() * np.sqrt(252); B2.vol = np.maximum(v, v.expanding(min_periods=40).median() * 0.5)
tr2 = trend_sig(B2); n2, g2, W2, _ = B2.run(B2.weights(tr2))
print("    TREND_TUTTI su serie GREZZE (segnale e P&L contaminati):", {k: round(v, 2) for k, v in line("x", n2).items() if k.startswith("S_")})
# segnale dalle grezze, P&L vero (ripulito): l'errore che farebbe chi usa i dati grezzi per decidere
n3 = B.run(B.weights(tr2))[0]
print("    segnale dalle grezze, P&L sulle ripulite:", {k: round(v, 2) for k, v in line("x", n3).items() if k.startswith("S_")})
bh_clean = (B.R.mean() * 252 * 100); bh_raw = (B2.R.mean() * 252 * 100)
print("    differenza media annua grezzo - ripulito per settore (%):", (bh_raw - bh_clean).groupby(B.spec.sotto).mean().round(2).to_dict())

print("\n(b) contributo per settore al P&L del trend (10% vol), anni scelti, in % del capitale")
contrib = (Wf.shift(2) * B.R.fillna(0))
c = contrib.T.groupby(B.spec.sotto).sum().T
print((c.groupby(c.index.year).sum().loc[[2008, 2014, 2020, 2022, 2023, 2024, 2025, 2026]] * 100).round(1).to_string())
top = contrib.loc["2020"].sum().sort_values(ascending=False)
print("2020, mercati principali (%):", (top.head(6) * 100).round(1).to_dict(), " peggiori:", (top.tail(3) * 100).round(1).to_dict())
print("CL 2020-04: contributo %.1f%%" % (contrib.loc["2020-04", "CL=F"].sum() * 100))
for drop in (["CL=F"], ["CL=F", "NG=F", "HO=F", "RB=F"], ["LE=F", "HE=F"]):
    m = [k for k in B.R.columns if k not in drop]
    nn = B.run(B.weights(tr[m].reindex(columns=B.R.columns)))[0]
    print(f"    senza {drop}: Sharpe tutto {stats(nn)['sharpe']:.2f}, 2020 {((1+nn.loc['2020']).prod()-1)*100:.1f}%, selezione {stats(nn.loc[:SEL_END])['sharpe']:.2f}, verifica {stats(nn.loc[VER_START:])['sharpe']:.2f}")

print("\n(c) breakout S2 55/20: operazioni estreme")
T = pd.read_parquet("trades.parquet")
print(T.sort_values("R", ascending=False).head(8).round(3).to_string())
x = T.R; print("R medio %.3f; senza le 10 migliori %.3f; senza le 50 migliori %.3f; mediana %.3f" % (x.mean(), x.sort_values().iloc[:-10].mean(), x.sort_values().iloc[:-50].mean(), x.median()))

print("\n(d) autocorrelazione giornaliera dei rendimenti (ritardo 1) negli ultimi 15 giorni prima del roll e nel resto")
for k in ("LE=F", "HE=F", "CL=F", "ZC=F", "ZN=F"):
    d = raw(k); rd = roll_days_final(k, d); r = B.P[k].ret
    near = pd.Series(False, index=r.index); pos = r.index.get_indexer(rd)
    for p in pos: near.iloc[max(p - 15, 0):p] = True
    a = pd.concat([r, r.shift(1)], axis=1).dropna(); a.columns = ["r", "l"]
    print(k, "vicino alla scadenza %.3f" % a[near.reindex(a.index)].corr().iloc[0, 1], " lontano %.3f" % a[~near.reindex(a.index)].corr().iloc[0, 1])
