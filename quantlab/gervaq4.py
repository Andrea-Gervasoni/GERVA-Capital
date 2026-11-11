"""
GERVA-Q v4 — banco di prova dei miglioramenti del motore, contro la v3 come riferimento.

Regole del banco (per non ingannarsi, docs/research/alpha_research.md §0-6):
  * ogni variante e' una prova registrata nel trial registry (contatore del DSR);
  * PBO (CSCV) su tutte le varianti insieme;
  * bootstrap stazionario APPAIATO sulla differenza di Sharpe rispetto alla v3;
  * gli ultimi `holdout_years` anni sono messi da parte: la scelta si fa solo sul periodo prima,
    l'holdout si guarda una volta sola per la variante scelta;
  * se nessuna variante supera tutti i cancelli si TIENE la v3. E' il risultato piu' probabile, ed
    e' un buon risultato: vuol dire che il motore non e' stato adattato al passato.

Tasso a breve e tesoreria (correzione dell'audit del 10/11, rilievo 9):
  * OGNI cancello (Sharpe, PSR, DSR, PBO, bootstrap appaiato, holdout) lavora sui rendimenti IN ECCESSO del
    tasso a breve giornaliero (`short_rate`: ^IRX / 100 / giorni l'anno). Sui rendimenti grezzi il banco
    premiava chi teneva piu' liquidita' remunerata: su mercati di puro rumore promuoveva la variante
    "con cassa" 9-12 volte su 12, e una serie di soli T-bill aveva Deflated Sharpe 1,000;
  * la liquidita' ferma rende il tasso a breve meno 0,10% (ETF monetario UCITS) in TUTTE le varianti,
    riferimento compreso. E' una scelta di TESORERIA (data["tesoreria"], default True), uguale per tutti,
    non un miglioramento candidato: mettere la cassa in un monetario non richiede abilita' e non dice
    nulla sul motore. In eccesso del tasso la cassa vale -0,10% l'anno: non puo' piu' sembrare alpha;
  * il banco stampa anche il risultato con un giorno di ritardo in piu' tra segnale ed esecuzione (lag=1):
    il motore senza prezzi di apertura esegue sulla stessa chiusura che genera il segnale (backtest.py).

Miglioramenti candidati, ciascuno con un meccanismo documentato:
  dyn    momentum settoriale con il freno di Daniel-Moskowitz (bear market + volatilita' alta)
  vix    reversal dimensionato con il VIX (Nagel 2012), con lo stesso tetto per titolo
  erc    allocazione tra sleeve a contributi di rischio uguali con covarianza Ledoit-Wolf, mensile
  hrp    allocazione tra sleeve con Hierarchical Risk Parity, mensile
  band   banda di non intervento piu' larga (meno turnover e meno costi)
  vt     volatilita' target del portafoglio con stima di crisi (mai sopra 1x: niente leva)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import strategies as ST, backtest as BT, stats as QS, portfolio as PF

TREND_SET = ["SPY", "QQQ", "IWM", "VGK", "EWJ", "EEM", "IEF", "TLT", "TIP", "LQD", "EMB", "GLD", "SLV", "DBC", "VNQ"]
SECTORS = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLP", "XLY", "XLU", "XLB"]
# universo di S4 come in GERVA-Q config.py (large cap USA attuali: survivorship dichiarato, rilievo R6)
STOCKS = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "BRK-B", "JPM", "JNJ", "V", "PG", "UNH", "HD", "MA", "XOM",
          "CVX", "MRK", "PEP", "KO", "ABBV", "COST", "AVGO", "WMT", "MCD", "CSCO", "ACN", "LLY", "TMO", "ABT", "DHR",
          "ADBE", "CRM", "NFLX", "TXN", "ORCL", "NKE", "PM", "QCOM", "LIN", "HON", "UNP", "LOW", "IBM", "AMGN", "CAT",
          "GS", "BA", "SBUX", "INTC", "AMD", "BLK", "MDT", "GE", "DE", "ISRG", "BKNG", "AXP", "SPGI", "LMT", "MMM",
          "CVS", "MO", "C", "BAC", "WFC", "MS", "USB", "PFE", "BMY", "GILD", "T", "VZ", "CMCSA", "DIS", "TGT", "SO",
          "DUK", "NEE", "COP", "SLB", "EMR", "FDX", "UPS", "GD", "RTX", "CL", "KMB", "MDLZ", "ADP", "INTU"]
TD = 252


@dataclass(frozen=True)
class Variant:
    name: str
    comb: str = "equal"        # equal | erc | hrp
    dyn: bool = False
    vix: bool = False
    band: float = 0.02
    vt: bool = False

    def params(self) -> dict:
        return dict(comb=self.comb, dyn=self.dyn, vix=self.vix, band=self.band, vt=self.vt)


VARIANTS = [
    Variant("v3_riferimento"),
    Variant("dyn", dyn=True),
    Variant("vix", vix=True),
    Variant("erc", comb="erc"),
    Variant("hrp", comb="hrp"),
    Variant("band5", band=0.05),
    Variant("vt", vt=True),
    Variant("tutto", comb="erc", dyn=True, vix=True, band=0.05),
]


def _cols(close, names):
    return [c for c in names if c in close.columns]


def sleeves(close: pd.DataFrame, v: Variant, stocks: list[str] | None = None) -> dict[str, pd.DataFrame]:
    out = {}
    tr = _cols(close, TREND_SET)
    if tr:
        out["S1_trend"] = ST.ewma_trend(close[tr])
    if "SPY" in close:
        spy = close["SPY"]
        rv = spy.pct_change().rolling(21).std() * math.sqrt(TD)
        w = (0.16 / rv).clip(upper=1.0) * (spy > spy.rolling(200).mean()).astype(float)
        out["S2_volman"] = pd.DataFrame({"SPY": w.fillna(0.0)})
    sec = _cols(close, SECTORS)
    if len(sec) >= 3 and "SPY" in close:
        W = ST.sector_momentum(close[sec], top=3)
        ok = (close["SPY"] > close["SPY"].rolling(200).mean()).astype(float)
        W = W.mul(ok, axis=0)
        if v.dyn:
            W = W.mul(ST.dynamic_momentum_overlay(close["SPY"]), axis=0)
        if "IEF" in close:
            W["IEF"] = (1 - W.sum(axis=1)).clip(lower=0)
        out["S3_sector"] = W
    stocks = [s for s in (stocks or []) if s in close.columns]
    if len(stocks) >= 6 and "SPY" in close:
        mult = ST.vix_size_multiplier(close["^VIX"]) if (v.vix and "^VIX" in close) else None
        out["S4_reversal"] = ST.short_reversal(close[stocks], close["SPY"], size_mult=mult)
    return out


def _sleeve_returns(close, sl, cost) -> pd.DataFrame:
    return pd.DataFrame({k: BT.run(W, close[W.columns], cost_rate=cost, band=0.0).returns for k, W in sl.items()})


def combine(close: pd.DataFrame, sl: dict[str, pd.DataFrame], comb: str, cost: float) -> pd.DataFrame:
    cols = sorted(set().union(*[W.columns for W in sl.values()]))
    idx = close.index
    names = list(sl)
    if comb == "equal" or len(names) < 2:
        alloc = pd.DataFrame(1 / len(names), index=idx, columns=names)
    else:
        R = _sleeve_returns(close, sl, cost)
        month_end = pd.Series((idx + pd.offsets.BDay(1)).month != idx.month, index=idx)
        alloc = pd.DataFrame(np.nan, index=idx, columns=names)
        for i in np.where(month_end.values)[0]:
            if i < 252:
                continue
            X = R.iloc[i - 251:i + 1].dropna()
            if len(X) < 200 or (X.std() == 0).any():
                continue
            cov, _ = PF.ledoit_wolf(X.values)
            w = PF.erc(cov) if comb == "erc" else PF.hrp(cov)
            alloc.iloc[i] = w
        alloc = alloc.ffill().fillna(1 / len(names))
    W = pd.DataFrame(0.0, index=idx, columns=cols)
    for k, Wk in sl.items():
        W[Wk.columns] += Wk.reindex(idx).fillna(0.0).mul(alloc[k], axis=0)
    g = W.sum(axis=1)
    return W.div(g.where(g > 1, 1), axis=0)


def vol_target(close: pd.DataFrame, W: pd.DataFrame, target: float = 0.10, cost: float = 0.0008) -> pd.DataFrame:
    """Scala il portafoglio a una vol target con la stima PIU' ALTA tra realizzata (63 giorni) e
    'di crisi' (correlazioni a 0,8 sugli asset rischiosi). Mai sopra 1: niente leva."""
    base = BT.run(W, close[W.columns], cost_rate=cost, band=0.02).returns
    real = base.rolling(63, min_periods=40).std() * math.sqrt(TD)
    rets = close[W.columns].pct_change()
    vols = rets.rolling(63, min_periods=40).std() * math.sqrt(TD)
    crisis = pd.Series(np.nan, index=W.index)
    for i in range(63, len(W), 21):           # stima mensile: basta e costa poco
        w, v = W.iloc[i].values, np.nan_to_num(vols.iloc[i].values)
        if w.sum() > 0:
            crisis.iloc[i] = _crisis(w, v)
    est = pd.concat([real, crisis.ffill()], axis=1).max(axis=1)
    scale = (target / est).clip(upper=1.0).shift(1).fillna(1.0)
    return W.mul(scale, axis=0)


def _crisis(w, v, rho=0.8):
    n = len(w)
    C = rho * np.ones((n, n)) + (1 - rho) * np.eye(n)
    return float(np.sqrt(w @ (np.outer(v, v) * C) @ w))


def scale_exposure(W: pd.DataFrame, k: float) -> pd.DataFrame:
    """Moltiplica i pesi per k usando il capitale inattivo, MAI oltre il 100% lordo (niente leva):
    giorno per giorno il fattore effettivo e' min(k, 1 / lorda)."""
    gross = W.abs().sum(axis=1)
    f = np.minimum(k, np.where(gross > 0, 1.0 / gross.where(gross > 0, 1.0), k))
    return W.mul(f, axis=0)


CASH_FEE = 0.001            # costo annuo dell'ETF monetario che remunera la liquidita'


def short_rate(data: dict, periods: int = TD) -> pd.Series:
    """Tasso a breve PER PERIODO (giornaliero), allineato ai prezzi: ^IRX (T-bill a 13 settimane, % annuo) / 100 / periodi.
    Senza ^IRX vale data["cash_rate"] (annuo, default 2%). E' la stessa serie che remunera la liquidita' e che
    si sottrae nei cancelli: le due cose devono usare lo stesso numero, altrimenti la differenza diventa Sharpe."""
    close = data["close"]
    if "^IRX" in close:
        annual = (close["^IRX"].astype(float) / 100).ffill().bfill()
    else:
        annual = pd.Series(float(data.get("cash_rate", 0.02)), index=close.index)
    return (annual / periods).rename("tasso")


def treasury(r: pd.Series, gross: pd.Series, data: dict, periods: int = TD) -> pd.Series:
    """Accredita alla liquidita' ferma il tasso a breve meno CASH_FEE. Vale per ogni variante, riferimento compreso;
    data["tesoreria"] = False la spegne per tutte (liquidita' a rendimento zero)."""
    if not data.get("tesoreria", True):
        return r
    idle = (1 - gross).clip(lower=0)
    return r + idle * (short_rate(data, periods) - CASH_FEE / periods).clip(lower=0)


def run_variant(data: dict, v: Variant, cost: float = 0.0008, scale: float = 1.0, return_result: bool = False,
                lag: int = 0):
    """Rendimento TOTALE giornaliero della variante (mercato + liquidita' remunerata). lag: giorni di ritardo in piu'
    tra segnale ed esecuzione (0 = stessa chiusura, come finora; 1 = chiusura del giorno dopo)."""
    close = data["close"]
    sl = sleeves(close, v, data.get("stocks"))
    W = combine(close, sl, v.comb, cost)
    if v.vt:
        W = vol_target(close, W, cost=cost)
    if scale != 1.0:
        W = scale_exposure(W, scale)
    res = BT.run(W, close[W.columns], cost_rate=cost, band=v.band, lag=lag)
    r = treasury(res.returns, res.daily["gross"], data)
    return (r, res) if return_result else r


def risk_ladder(data: dict, v: Variant, scales=(1.0, 1.25, 1.5, 2.0), capital: float = 100_000.0,
                start_skip: int = 300) -> pd.DataFrame:
    """Piu' profitto senza leva = usare il capitale che il motore lascia fermo. Non migliora la QUALITA'
    (lo Sharpe resta circa uguale): sposta guadagni e perdite insieme. La scelta del livello e' di Andrea."""
    rows = {}
    for k in scales:
        r, res = run_variant(data, v, scale=k, return_result=True)
        r = r.iloc[start_skip:]
        p = QS.performance(r.values, rf=short_rate(data).reindex(r.index).values)       # Sharpe in eccesso del tasso
        yearly = (1 + r).groupby(r.index.year).prod() - 1
        rows[f"x{k:g}"] = dict(lorda_media=float(res.daily["gross"].iloc[start_skip:].mean()), Sharpe=p["Sharpe"],
                               CAGR=p["CAGR"], Vol=p["Vol"], MaxDD=p["MaxDD"], anno_peggiore=float(yearly.min()),
                               eur_anno=p["CAGR"] * capital, eur_10_anni=capital * ((1 + p["CAGR"]) ** 10 - 1))
    return pd.DataFrame(rows).T


def ladder_markdown(lad: pd.DataFrame, name: str, max_dd: float = 0.20) -> str:
    lines = [f"## Scala del rischio ({name}): piu' esposizione senza leva", "",
             "Lo Sharpe resta circa uguale: cambia quanto si guadagna E quanto si perde. "
             "Il livello lo sceglie Andrea (grande richiesta: limite di rischio).", "",
             "| Livello | Esposizione media | Sharpe | CAGR | Vol | MaxDD | Anno peggiore | EUR/anno su 100k | Guadagno in 10 anni | Sfida |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for k, r in lad.iterrows():
        # REGOLE_SFIDA §10: squalifica oltre il 20% di drawdown; §13: anche per i soldi veri serve DD <= 20%
        ok = "ammesso" if r.MaxDD > -max_dd else f"SQUALIFICA (DD oltre {max_dd:.0%})"
        lines.append(f"| {k} | {r.lorda_media:.0%} | {r.Sharpe:.2f} | {r.CAGR:.1%} | {r.Vol:.1%} | {r.MaxDD:.1%} | "
                     f"{r.anno_peggiore:.1%} | {r.eur_anno:,.0f} | {r.eur_10_anni:,.0f} | {ok} |")
    lines += ["", "Nella sfida conta lo Sharpe (regola 11): piu' esposizione non aiuta a vincerla. Serve per i soldi veri, "
              "dopo i cancelli 13-15, e solo fino al limite di drawdown."]
    return "\n".join(lines)


@dataclass
class BenchResult:
    tabella: pd.DataFrame
    pbo: dict
    scelta: str
    motivo: str
    holdout: dict
    confronti: dict = field(default_factory=dict)
    ritardo: pd.DataFrame | None = None         # stesse varianti con un giorno di ritardo in piu' (solo informazione)
    tasso_medio: float = 0.0                    # tasso a breve medio annuo sottratto nel periodo di scelta

    def to_markdown(self) -> str:
        lines = ["# GERVA-Q v4 — banco di prova contro la v3", "",
                 f"**Scelta: {self.scelta}** — {self.motivo}", "",
                 f"Sharpe, PSR, PBO e confronti sono calcolati sui rendimenti **in eccesso del tasso a breve** "
                 f"(media {self.tasso_medio:.2%} l'anno nel periodo di scelta). La liquidita' ferma rende il tasso meno 0,10% "
                 "in tutte le varianti, riferimento compreso: e' tesoreria, non una variante.", "",
                 f"PBO su {len(self.tabella)} varianti: **{self.pbo['pbo']:.2f}** (0,5 = scegliere la migliore equivale a tirare a caso)", "",
                 "| Variante | Sharpe | CAGR | Vol | MaxDD | Calmar | PSR | P(Sharpe > v3) |", "|---|---|---|---|---|---|---|---|"]
        for name, r in self.tabella.iterrows():
            lines.append(f"| {name} | {r.Sharpe:.2f} | {r.CAGR:.1%} | {r.Vol:.1%} | {r.MaxDD:.1%} | {r.Calmar:.2f} | "
                         f"{r.PSR0:.3f} | {self.confronti.get(name, float('nan')):.2f} |")
        lines += ["", f"Holdout (mai usato per scegliere): {self.holdout}"]
        if self.ritardo is not None and len(self.ritardo):
            lines += ["", "## Con un giorno di ritardo tra segnale ed esecuzione", "",
                      "Sopra, il motore esegue sulla stessa chiusura che genera il segnale (ipotesi ottimistica). Qui il segnale "
                      "di stasera si esegue alla chiusura di domani. Non e' un cancello: e' la misura di quanto il risultato "
                      "dipende dall'esecuzione immediata.", "",
                      "| Variante | Sharpe (stessa chiusura) | Sharpe (+1 giorno) | CAGR (+1 giorno) | P(Sharpe > v3) (+1 giorno) |",
                      "|---|---|---|---|---|"]
            for name, r in self.ritardo.iterrows():
                lines.append(f"| {name} | {self.tabella.loc[name, 'Sharpe']:.2f} | {r.Sharpe:.2f} | {r.CAGR:.1%} | {r.P_v3:.2f} |")
        return "\n".join(lines)


def paired_sharpe_prob(a, b, n_boot: int = 1000, block: int = 20, seed: int = 11) -> float:
    """P(Sharpe(a) > Sharpe(b)) con bootstrap stazionario appaiato (stessi indici per entrambe)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = min(len(a), len(b))
    a, b = a[-n:], b[-n:]
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    restart = rng.random((n_boot, n)) < 1 / block
    restart[:, 0] = True
    start = rng.integers(n, size=(n_boot, n))
    last = np.maximum.accumulate(np.where(restart, t, 0), axis=1)
    idx = (np.take_along_axis(start, last, axis=1) + t - last) % n

    def sr(x):
        sd = x.std(axis=1, ddof=1)
        return np.where(sd > 0, x.mean(axis=1) / np.where(sd > 0, sd, 1), 0)
    return float((sr(a[idx]) > sr(b[idx])).mean())


def _accepts(fn, name: str) -> bool:
    import inspect
    try:
        return name in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def bench(data: dict, variants=VARIANTS, holdout_years: float = 2.0, register=None, start_skip: int = 300,
          dsr_fn=None, p_min: float = 0.90, pbo_max: float = 0.30, runner=None, ref: str = "v3_riferimento",
          periods: int = 252, rf=None, with_lag: bool = True) -> BenchResult:
    """register(variant) -> trial_id; dsr_fn(trial_id, returns) -> dsr. Entrambi facoltativi (test).
    runner(data, variant) -> rendimenti TOTALI: di default il motore azionario; il banco crypto passa il suo.
    rf: tasso a breve per periodo (Serie indicizzata come i prezzi, oppure scalare); se manca si usa short_rate(data).
    Tutti i cancelli lavorano su rendimento - rf; anche dsr_fn riceve i rendimenti in eccesso.
    with_lag: riesegue ogni variante con lag=1 e lo riporta in `ritardo` (se il runner accetta `lag`)."""
    run = runner or run_variant
    R = {}
    for v in variants:
        tid = register(v) if register else None
        r = run(data, v).iloc[start_skip:]
        R[v.name] = (r, tid)
    M = pd.DataFrame({k: v[0] for k, v in R.items()}).dropna()
    rate = short_rate(data, periods) if rf is None else (rf if isinstance(rf, pd.Series) else pd.Series(float(rf), index=M.index))
    rate = rate.reindex(M.index).ffill().bfill()
    if rate.isna().any():
        raise ValueError("tasso a breve mancante per il periodo del banco")
    X = M.sub(rate, axis=0)                               # rendimenti in eccesso: e' su questi che si giudica
    split = M.index[-1] - pd.DateOffset(years=holdout_years)
    is_sel = M.index <= split
    sel, hold, xsel, xhold = M[is_sel], M[~is_sel], X[is_sel], X[~is_sel]
    rsel, rhold = rate[is_sel].values, rate[~is_sel].values
    rows, comp = {}, {}
    for k in M.columns:
        p = QS.performance(sel[k].values, periods=periods, rf=rsel)
        if dsr_fn and R[k][1]:
            p["DSR"] = dsr_fn(R[k][1], xsel[k].values)
        rows[k] = p
        comp[k] = paired_sharpe_prob(xsel[k].values, xsel[ref].values) if k != ref else 0.5
    tab = pd.DataFrame(rows).T
    pbo = QS.pbo_cscv(xsel.values, n_blocks=10).to_dict()
    cand = tab.drop(index=ref).sort_values("Sharpe", ascending=False)
    choice, why = ref, "nessuna variante supera tutti i cancelli: si tiene la v3"
    best = cand.index[0]
    checks = dict(pbo=pbo["pbo"] <= pbo_max, prob=comp[best] >= p_min,
                  dsr=("DSR" not in tab or tab.loc[best].get("DSR", 1) >= 0.95))
    hold_info = {}
    if all(checks.values()):
        hs_best = QS.performance(hold[best].values, periods=periods, rf=rhold)["Sharpe"]
        hs_ref = QS.performance(hold[ref].values, periods=periods, rf=rhold)["Sharpe"]
        hold_info = dict(variante=best, sharpe_holdout=round(hs_best, 3), sharpe_v3_holdout=round(hs_ref, 3))
        if hs_best > hs_ref:
            choice, why = best, (f"supera la v3 nel periodo di scelta (P={comp[best]:.2f}), PBO {pbo['pbo']:.2f}, "
                                 f"e nell'holdout ({hs_best:.2f} contro {hs_ref:.2f})")
        else:
            why = f"{best} batte la v3 nel periodo di scelta ma non nell'holdout: si tiene la v3"
    else:
        why += f" (migliore candidata {best}: " + ", ".join(f"{k}={'ok' if v else 'no'}" for k, v in checks.items()) + ")"
    lagged = None
    if with_lag and _accepts(run, "lag"):
        L = pd.DataFrame({v.name: run(data, v, lag=1).iloc[start_skip:] for v in variants}).reindex(sel.index).dropna()
        rl = rate.reindex(L.index)
        XL = L.sub(rl, axis=0)
        lagged = pd.DataFrame({k: dict(Sharpe=QS.performance(L[k].values, periods=periods, rf=rl.values)["Sharpe"],
                                       CAGR=QS.performance(L[k].values, periods=periods, rf=rl.values)["CAGR"],
                                       P_v3=paired_sharpe_prob(XL[k].values, XL[ref].values) if k != ref else 0.5)
                               for k in L.columns}).T
        if choice != ref and lagged.loc[choice, "P_v3"] < p_min:
            why += (f". ATTENZIONE: con un giorno di ritardo P(Sharpe > v3) scende a {lagged.loc[choice, 'P_v3']:.2f}: "
                    "il vantaggio dipende dall'esecuzione sulla stessa chiusura del segnale")
    return BenchResult(tabella=tab, pbo=pbo, scelta=choice, motivo=why, holdout=hold_info, confronti=comp,
                       ritardo=lagged, tasso_medio=float(np.mean(rsel) * periods))
