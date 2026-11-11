"""B6 - libro candidato, scommesse indipendenti, granularita' dei contratti micro e conto minimo, obiettivo di volatilita' ottimale
per la crescita, bootstrap a blocchi mensili, correlazione col fondo esistente. Salva returns.parquet."""
from engine import *
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
rng = np.random.default_rng(7)

def trend_sig(B, names=None):
    S = {}
    for k in (21, 63, 252): S[f"T{k}"] = B.sig_tsmom(k)
    for f in (4, 8, 16, 32, 64): S[f"E{f}"] = B.sig_ewmac(f)
    for n in (20, 55, 120, 250): S[f"D{n}"] = B.sig_donchian(n)
    names = names or list(S)
    return (sum(S[n].fillna(0) / S[n].abs().mean().mean() for n in names) / len(names)).where(B.active)

def ibs_us(B):
    idx = B.R.index; us = ["ES_etf", "NQ_etf", "YM_etf", "RTY_etf"]
    s = pd.DataFrame(0.0, index=idx, columns=B.R.columns); rw = s.copy()
    for k in us:
        p = B.P[k]; ib = ((p.close - p.low) / (p.high - p.low).replace(0, np.nan)).reindex(idx)
        s[k] = (ib < 0.2).astype(float); rw[k] = 0.25
    return B.weights(s.where(B.active), rw=rw)

def sleeves(B):
    tr = trend_sig(B); one = pd.DataFrame(1.0, index=B.R.index, columns=B.R.columns).where(B.active)
    out = {}
    out["TREND"] = B.run(B.weights(tr))
    out["RP"] = B.run(B.weights(one))
    out["IBS"] = B.run(ibs_us(B), lag=1)
    com = [k for k in B.R.columns if B.sec[k] in ("METAL", "ENERGY", "AG")]
    out["TREND_MATERIE"] = B.run(B.weights(tr[com].reindex(columns=B.R.columns)))
    return out, tr

def combine(parts, w):
    c = sum(parts[k][0] * w[k] for k in w).dropna()
    k = (0.10 / (c.ewm(span=60, min_periods=40).std() * np.sqrt(252))).shift(1)
    k = np.minimum(k, 3 * k.expanding(min_periods=60).median()).fillna(0)
    return (c * k).loc["2001-06-01":]

print("=" * 30, "A. LIBRI COMBINATI (vol 10%, netti) ", "=" * 30)
ALL = {}
for lab, B in [("37 mercati", Book()), ("31 micro", Book(only_micro=True))]:
    parts, tr = sleeves(B)
    C = {"C1 TREND": {"TREND": 1}, "C2 RP+TREND 50/50": {"TREND": .5, "RP": .5}, "C3 IBS + TREND materie prime": {"IBS": .5, "TREND_MATERIE": .5},
         "C4 TREND+RP+IBS (1/3 ciascuno)": {"TREND": 1 / 3, "RP": 1 / 3, "IBS": 1 / 3}}
    rows = []
    for nm, w in C.items():
        r = combine(parts, w); ALL[f"{nm} [{lab}]"] = r; rows.append(line(f"{nm} [{lab}]", r))
    print(pd.DataFrame(rows).set_index("strategia").round(2).to_string())
    if lab == "31 micro": Bm, parts_m, tr_m = B, parts, tr
    else: Bf, parts_f, tr_f = B, parts, tr
print("varianti contate: 8")
BEST = "C4 TREND+RP+IBS (1/3 ciascuno) [31 micro]"; PURE = "C1 TREND [31 micro]"
for nm in (PURE, BEST):
    print(f"\n-- {nm} per periodo --"); print(fmt(table(ALL[nm])).to_string())
    y = ALL[nm]; print("per anno (%):", ((1 + y).groupby(y.index.year).prod() - 1).mul(100).round(1).to_dict())
# costi x2 e ritardo sul libro migliore
def book_variant(B, **kw):
    tr = trend_sig(B); one = pd.DataFrame(1.0, index=B.R.index, columns=B.R.columns).where(B.active)
    lagx = kw.pop("lagx", 0)
    p = {"TREND": B.run(B.weights(tr), lag=2 + lagx, **kw), "RP": B.run(B.weights(one), lag=2 + lagx, **kw), "IBS": B.run(ibs_us(B), lag=1 + lagx, **kw)}
    return combine(p, {"TREND": 1 / 3, "RP": 1 / 3, "IBS": 1 / 3})
rows = [line("C4 micro costi x2", book_variant(Bm, cmult=2)), line("C4 micro ritardo +1 barra", book_variant(Bm, lagx=1)), line("C4 micro costi x2 + ritardo", book_variant(Bm, cmult=2, lagx=1))]
print(pd.DataFrame(rows).set_index("strategia").round(2).to_string())

print("\n" + "=" * 30, "B. SCOMMESSE EFFETTIVAMENTE INDIPENDENTI (rapporto di partecipazione) ", "=" * 30)
def PR(X):
    c = X.corr().values; lam = np.linalg.eigvalsh(c); lam = lam[lam > 0]; return lam.sum() ** 2 / (lam ** 2).sum()
Rw = Bf.R.loc["2001-01-01":].resample("W").sum(min_count=1)
pnl = (Bf.weights(tr_f).shift(2) * Bf.R.fillna(0)); pnl = pnl / pnl.std(); Pw = pnl.loc["2001-01-01":].resample("W").sum()
for lab, a, b, cols in [("tutti 37, 2001-2026", "2001", "2026", list(Bf.R.columns)), ("35 senza cripto, 2001-2009", "2001", "2009", list(Bf.R.columns[:-2])),
                        ("35 senza cripto, 2010-2019", "2010", "2019", list(Bf.R.columns[:-2])), ("37, 2021-2026", "2021", "2026", list(Bf.R.columns)),
                        ("31 micro, 2021-2026", "2021", "2026", list(Bm.R.columns))]:
    x = Rw.loc[a:b, cols].dropna(how="all"); x = x.loc[:, x.notna().mean() > 0.9].fillna(0)
    y = Pw.loc[a:b, x.columns]
    print(f"{lab:32s} mercati {x.shape[1]:2d}  PR rendimenti dei mercati {PR(x):5.1f}   PR dei flussi P&L del trend {PR(y):5.1f}")
sec_r = pd.DataFrame({s: Rw[[k for k in Bf.R.columns if Bf.sec[k] == s]].mean(axis=1) for s in SECTORS}).loc["2018":]
print("correlazione settimanale tra settori (2018-2026):"); print(sec_r.corr().round(2).to_string())

print("\n" + "=" * 30, "C. COSTI PER MERCATO E GRANULARITA' ", "=" * 30)
sp = Bf.spec.copy(); eur = float(raw("EURUSD=X").close.iloc[-1])
volnow = Bf.vol.iloc[-250:].mean()
sp["vol_ann%"] = volnow * 100; sp["rischio_contratto_usd_anno"] = sp.nozionale_usd.astype(float) * volnow
sp["%_di_10k_eur"] = sp.rischio_contratto_usd_anno / (10000 * eur) * 100
print(f"EURUSD {eur:.4f}; costo_bp = (commissione + 1 tick)/nozionale per lato")
print(sp[["sotto", "contratto", "nozionale_usd", "tick_usd", "comm_usd", "costo_bp", "roll_anno", "vol_ann%", "rischio_contratto_usd_anno", "%_di_10k_eur"]].astype({"nozionale_usd": float, "costo_bp": float, "tick_usd": float, "comm_usd": float}).round(2).to_string())

def granular(B, W, acct_usd, target, lag=2, cols=None):
    """arrotonda a contratti interi; il nozionale del contratto e' quello di oggi (ipotesi di invarianza di scala)"""
    _, _, Wf, _ = B.run(W, target=target, lag=lag)
    notional = B.spec.nozionale_usd.astype(float)
    n = (Wf * acct_usd / notional).round()
    Wr = n * notional / acct_usd
    R = B.R.fillna(0)
    gross = (Wr.shift(lag) * R).sum(axis=1)
    cost = ((Wr - Wr.shift(1)).abs().fillna(0) * B.cost).sum(axis=1).shift(lag).fillna(0) + (Wr.abs() * (2 * B.cost * B.rolls / 252)).sum(axis=1).shift(lag).fillna(0)
    net = (gross - cost).loc["2001-06-01":]
    ideal = B.run(W, target=target, lag=lag)[0].loc["2001-06-01":]
    held = (n.loc["2001-06-01":].abs() > 0).mean()
    marg = (Wr.abs() * B.spec.margine.astype(float)).sum(axis=1).loc["2001-06-01":]
    return net, ideal, held, marg
W_tr = Bm.weights(tr_m)
one = pd.DataFrame(1.0, index=Bm.R.index, columns=Bm.R.columns).where(Bm.active)
W_c2 = Bm.weights(one * 0.5 + tr_m / tr_m.abs().stack().mean() * 0.5)
print("\n-- Trend su 31 micro con contratti interi: Sharpe netto per dimensione del conto e obiettivo di volatilita' --")
rows = []
for tv in (0.15, 0.25, 0.40):
    for eurk in (10, 25, 50, 100, 250, 1000):
        net, ideal, held, marg = granular(Bm, W_tr, eurk * 1000 * eur, tv)
        s = stats(net); si = stats(ideal)
        rows.append(dict(vol_obiettivo=tv, conto_eur_k=eurk, sharpe=s["sharpe"], sharpe_ideale=si["sharpe"], vol_real=s["vol"] * 100, mdd=s["mdd"] * 100, corr_con_ideale=net.corr(ideal),
                         mercati_tenuti_medio=held.sum(), mercati_tenuti_almeno_meta_tempo=int((held > 0.5).sum()), margine_medio=marg.mean(), margine_p99=marg.quantile(.99),
                         S_sel=stats(net.loc[:SEL_END])["sharpe"], S_ver=stats(net.loc[VER_START:])["sharpe"]))
G = pd.DataFrame(rows); print(G.round(2).to_string(index=False))
net, ideal, held, marg = granular(Bm, W_tr, 10000 * eur, 0.25)
print("\ncon 10k EUR e vol 25%: quota di giorni con posizione non nulla per mercato:"); print(held.round(2).sort_values(ascending=False).to_dict())
# sottoinsieme concentrato per il conto piccolo: per settore i contratti col minor rischio per contratto
sub = ["RTY_etf", "^STOXX50E", "ZN=F", "ZT=F", "6A=F", "6C=F", "6J=F", "HG=F", "CL=F", "NG=F", "ZS=F", "ZL=F", "ZC=F", "BTC=F", "ETH=F"]
Bs = Book(); Bs.R = Bs.R[sub]; Bs = None
class Sub(Book):
    def __init__(self, keep):
        self.P, R, C = load_panel(); R = R[keep]; self.R = R; self.C = C[keep]
        self.spec = specs(self.P).loc[keep]; self.cost = self.spec.costo_bp.astype(float) / 1e4; self.rolls = self.spec.roll_anno.astype(float); self.sec = self.spec.settore
        v = R.ewm(span=60, min_periods=40).std() * np.sqrt(252); self.vol = np.maximum(v, v.expanding(min_periods=40).median() * 0.5); self.active = self.vol.notna()
        rw = pd.DataFrame(0.0, index=R.index, columns=R.columns)
        nsec = pd.DataFrame({s: self.active.loc[:, self.sec[self.sec == s].index].sum(axis=1) for s in SECTORS}); nact = (nsec > 0).sum(axis=1)
        for k in R.columns: rw[k] = (self.active[k] / nsec[self.sec[k]].replace(0, np.nan) / nact).fillna(0.0)
        self.rw = rw
Bs = Sub(sub); trs = trend_sig(Bs); W_s = Bs.weights(trs)
print("\n-- Sottoinsieme di 15 micro 'piccoli' (scelti per rischio per contratto, non per risultato), trend, contratti interi --")
rows = []
for tv in (0.25, 0.40):
    for eurk in (10, 25, 100):
        net, ideal, held, marg = granular(Bs, W_s, eurk * 1000 * eur, tv)
        s = stats(net); rows.append(dict(vol_obiettivo=tv, conto_eur_k=eurk, sharpe=s["sharpe"], sharpe_ideale=stats(ideal)["sharpe"], vol_real=s["vol"] * 100, mdd=s["mdd"] * 100, corr_con_ideale=net.corr(ideal),
                                         mercati_tenuti_medio=held.sum(), margine_p99=marg.quantile(.99), S_sel=stats(net.loc[:SEL_END])["sharpe"], S_ver=stats(net.loc[VER_START:])["sharpe"]))
print(pd.DataFrame(rows).round(2).to_string(index=False)); print("varianti contate: 24 (griglia conto x vol; non sono scelte di parametri)")

print("\n" + "=" * 30, "D. OBIETTIVO DI VOLATILITA' OTTIMALE PER LA CRESCITA E BOOTSTRAP ", "=" * 30)
def growth(r, L): 
    x = 1 + L * r
    return -np.inf if (x <= 0).any() else np.log(x).mean() * 252
def kelly(r):
    Ls = np.arange(0.25, 15.01, 0.25); g = np.array([growth(r, L) for L in Ls]); i = int(np.nanargmax(g)); return Ls[i], g[i]
def boot(r, L, nsim=20000, months=36, block=3):
    m = (1 + L * r).groupby([r.index.year, r.index.month]).prod().values - 1
    # per il drawdown dentro il mese si usa anche il minimo infra-mensile
    lo = ((1 + L * r).groupby([r.index.year, r.index.month]).apply(lambda x: x.cumprod().min())).values
    nb = months // block; st = rng.integers(0, len(m) - block + 1, size=(nsim, nb))
    ix = (st[:, :, None] + np.arange(block)[None, None, :]).reshape(nsim, -1)
    M = np.clip(m[ix], -0.999, None); eq = np.cumprod(1 + M, axis=1); prev = np.c_[np.ones(nsim), eq[:, :-1]]
    low = prev * lo[ix]
    peak = np.maximum.accumulate(np.c_[np.ones(nsim), eq], axis=1)[:, :-1]
    dd = (low / peak).min(axis=1) - 1
    below = low.min(axis=1) <= 0.5
    return dict(P_meno50_dal_capitale_iniziale=below.mean(), P_drawdown_50=(dd <= -0.5).mean(), mediana_3a=np.median(eq[:, -1]) - 1, p5_3a=np.quantile(eq[:, -1], .05) - 1,
                mese_medio_comp=np.median(eq[:, -1]) ** (1 / months) - 1)
rows = []
for nm in (PURE, BEST):
    r0 = ALL[nm]
    for scen, r in [("base", r0), ("meta' vantaggio", r0 - 0.5 * r0.mean()), ("solo selezione", r0.loc[:SEL_END]), ("solo verifica", r0.loc[VER_START:])]:
        L, g = kelly(r); v = r.std() * np.sqrt(252)
        for lab, LL in [("ottimo", L), ("meta'", L / 2)]:
            gg = growth(r, LL); b = boot(r, LL) if scen in ("base", "meta' vantaggio") else {}
            rows.append(dict(libro=nm[:14], scenario=scen, leva=lab, molt_su_10vol=LL, vol_obiettivo=LL * v * 100, crescita_log_anno=gg, mese_composto=(np.exp(gg / 12) - 1) * 100,
                             mdd_storico=((1 + LL * r).cumprod() / (1 + LL * r).cumprod().cummax() - 1).min() * 100, **{k: (x * 100) for k, x in b.items()}))
print(pd.DataFrame(rows).round(2).to_string(index=False))
print("obiettivi fissi sul libro migliore (base): ")
rows = []
for tv in (0.15, 0.25, 0.40, 0.60):
    r0 = ALL[BEST]; LL = tv / (r0.std() * np.sqrt(252)); gg = growth(r0, LL); b = boot(r0, LL); bh = boot(r0 - 0.5 * r0.mean(), LL)
    rows.append(dict(vol=tv * 100, crescita_log=gg, mese_composto=(np.exp(gg / 12) - 1) * 100, mdd_storico=((1 + LL * r0).cumprod() / (1 + LL * r0).cumprod().cummax() - 1).min() * 100,
                     P_dd50_base=b["P_drawdown_50"] * 100, P_meno50_base=b["P_meno50_dal_capitale_iniziale"] * 100, P_dd50_meta=bh["P_drawdown_50"] * 100, P_meno50_meta=bh["P_meno50_dal_capitale_iniziale"] * 100))
print(pd.DataFrame(rows).round(2).to_string(index=False))

print("\n" + "=" * 30, "E. CORRELAZIONE COL FONDO ESISTENTE ", "=" * 30)
F = pd.read_parquet(f"{ROOT}/research/v5/v5/a10_sistema/returns.parquet")[["B_cassa_in_tbill", "C1_mtm_limiti", "C3_mtm_limiti_debito_reale"]]
cal = pd.date_range("2001-06-01", ALL[BEST].index[-1])
OUT = pd.DataFrame({"C1_trend_31micro": ALL[PURE], "C4_trend_rp_ibs_31micro": ALL[BEST], "C2_rp_trend_31micro": ALL["C2 RP+TREND 50/50 [31 micro]"],
                    "C1_trend_37": ALL["C1 TREND [37 mercati]"], "trend_sleeve_31micro": parts_m["TREND"][0], "rp_sleeve_31micro": parts_m["RP"][0], "ibs_sleeve": parts_m["IBS"][0]}).reindex(cal).fillna(0.0)
OUT.index.name = "date"; OUT.to_parquet("returns.parquet")
J = OUT.join(F, how="inner"); Jm = (1 + J).resample("ME").prod() - 1
print("periodo comune:", J.index[0].date(), "->", J.index[-1].date())
print("correlazione mensile:"); print(Jm.corr().loc[OUT.columns, F.columns].round(2).to_string())
print("correlazione giornaliera:"); print(J.corr().loc[OUT.columns, F.columns].round(2).to_string())
# cosa aggiunge al fondo: miscela a rischio 80/20 e 70/30 sul periodo comune
def sh(x): return x.mean() / x.std() * np.sqrt(365)
f = J["C1_mtm_limiti"]; rows = []
for col in ("C1_trend_31micro", "C4_trend_rp_ibs_31micro"):
    b = J[col] * (f.std() / J[col].std())
    for wb in (0.0, 0.2, 0.3, 0.5):
        mix = (1 - wb) * f + wb * b
        rows.append(dict(aggiunta=col, peso_rischio_B6=wb, sharpe_tutto=sh(mix), sharpe_sel=sh(mix.loc[:SEL_END]), sharpe_ver=sh(mix.loc[VER_START:]), mdd=((1 + mix).cumprod() / (1 + mix).cumprod().cummax() - 1).min() * 100))
print("\nfondo C1_mtm_limiti + B6 (pesi di rischio, stessa volatilita'):"); print(pd.DataFrame(rows).round(2).to_string(index=False))
print("Sharpe sul periodo comune 2018-04 -> 2026-10:", {c: round(sh(J[c]), 2) for c in J.columns})
