"""
Il rischio e le aspettative del NOSTRO fondo (non di un titolo qualunque): cosa tiene GERVA-Q dopo la scala di
investimento, i desk e il lungo periodo; quanto puo' perdere in un giorno; cosa succederebbe in una crisi gia' vista;
e un Monte Carlo vero su un anno (o tre).

Come si calcola, in chiaro:
  1. Portafoglio atteso = pesi di GERVA-Q (modello azioni + crypto, gia' con la scala) + posizioni dei desk
     (firm_overlay.json) + rate del lungo periodo approvate (longterm_plan.json). Totale = esposizione lorda.
  2. Storia del portafoglio ("backcast"): i pesi di oggi applicati ai rendimenti giornalieri veri di ogni titolo.
     Dove un titolo non esiste ancora (per esempio un'azienda quotata da poco) i pesi degli altri si riscalano; si usano solo
     i giorni in cui almeno il 70% dell'esposizione ha dati. La leva paga il tasso a breve USA piu' l'1,5% (IBKR Pro).
  3. Monte Carlo = ricampionamento a blocchi (21 giorni) di quella storia: mantiene code grasse e giorni cattivi
     consecutivi, senza ipotizzare una distribuzione normale. 5.000 percorsi.
  4. Stress test = la stessa storia, ma nelle crisi piu' note (2008, 2011, 2018, 2020, 2022).

Limiti dichiarati: il passato non e' il futuro; i titoli di oggi sono quelli che hanno funzionato (sopravvivenza); non
modella margin call, ne' slippage. Sono scenari, non previsioni.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os

import numpy as np
import pandas as pd

from . import charts, db, paths, pod_zero
from . import settings as S

TD = 252
MARGIN_SPREAD = 0.015
EPISODES = [
    ("Crisi Lehman", "2008-09-12", "2008-11-20"),
    ("Agosto 2011 (debito USA)", "2011-07-22", "2011-10-03"),
    ("Fine 2018 (stretta Fed)", "2018-09-20", "2018-12-24"),
    ("Covid", "2020-02-19", "2020-03-23"),
    ("2022 (tassi e inflazione)", "2022-01-03", "2022-06-16"),
]


# ---------------------------------------------------------------------------------------------- portafoglio atteso
def _scaled(model: dict | None, v3_scale: float = 1.0) -> dict[str, float]:
    """Pesi di un file di stato di GERVA-Q. Se il file porta 'scale' e 'gross_base' e i pesi sono ancora quelli base,
    si applica la scala (stessa moltiplicazione di live.py); se sono gia' scalati si lasciano."""
    if not model:
        return {}
    w = {k: float(v) * v3_scale for k, v in (model.get("weights") or {}).items()}
    sc, gb = model.get("scale"), model.get("gross_base")
    tot = sum(abs(v) for v in w.values())
    if sc and gb and tot > 0 and abs(tot - float(gb)) <= 0.03 * float(gb) + 0.005:
        w = {k: v * float(sc) for k, v in w.items()}
    return w


def portfolio(model_eq=None, model_cr=None, overlay=None, lt_plan=None) -> dict:
    eq = pod_zero.equity_model() if model_eq is None else model_eq
    cr = pod_zero.crypto_model() if model_cr is None else model_cr
    w: dict[str, float] = {}
    fonti: dict[str, float] = {}

    def add(d, label):
        for k, v in d.items():
            w[k] = w.get(k, 0.0) + v
        fonti[label] = round(sum(abs(v) for v in d.values()), 4)

    add(_scaled(eq, pod_zero.equity_scale(eq) if eq else 1.0), "modello azioni e ETF")
    add(_scaled(cr), "crypto")
    ov = overlay if overlay is not None else (db.runtime_get("desk.overlay") or {})
    add({k: float(v) for k, v in (ov.get("targets") or {}).items()}, "desk")
    plan = lt_plan if lt_plan is not None else _lt_plan()
    from . import lt_committee
    cfg = lt_committee.config()
    core = {k: cfg["quota_nav"] / max(len(cfg["titoli"]), 1) for k in cfg["titoli"]}
    expl_cfg = cfg.get("esplorativo", {})
    core.update({k: expl_cfg.get("quota_nav", 0.02) / max(len(expl_cfg.get("titoli", {})), 1) for k in expl_cfg.get("titoli", {})})
    add({k: core[k] * float(f) for k, f in (plan.get("frazioni") or {}).items() if k in core and f}, "lungo periodo")
    gross = sum(abs(v) for v in w.values())
    cr_w = sum(abs(v) for k, v in w.items() if k in (cr or {}).get("weights", {}))
    return dict(pesi={k: round(v, 5) for k, v in sorted(w.items(), key=lambda x: -abs(x[1]))}, lordo=round(gross, 4),
                leva=round(max(gross - 1.0, 0.0), 4), quota_crypto=round(cr_w, 4), fonti=fonti)


def _lt_plan() -> dict:
    from . import lt_committee
    try:
        return json.load(open(lt_committee.plan_path()))
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------------------------------------- storia e backcast
def returns_matrix(symbols: list[str], close: pd.DataFrame | None = None) -> pd.DataFrame:
    """Rendimenti giornalieri sui giorni di borsa; le crypto (7 giorni su 7) si allineano all'ultimo prezzo disponibile."""
    close = charts.load_close() if close is None else close
    cols = {}
    stock_days = close[[c for c in ("SPY",) if c in close]].dropna().index if "SPY" in close else close.dropna(how="all").index
    for s in symbols:
        s2 = charts.ALIAS.get(s, s)
        if s2 in close:
            cols[s] = close[s2].dropna().reindex(stock_days, method="ffill")
    px = pd.DataFrame(cols)
    return px.pct_change(fill_method=None).iloc[1:]


def backcast(weights: dict[str, float], rets: pd.DataFrame, irx: pd.Series | None = None, min_coverage: float = 0.7) -> dict:
    w = {k: v for k, v in weights.items() if k in rets and abs(v) > 1e-9}
    senza = sorted(k for k in weights if k not in w)
    if not w:
        return dict(serie=pd.Series(dtype=float), senza_dati=senza, copertura=0.0)
    gross = sum(abs(v) for v in w.values())
    W = pd.Series(w)
    R = rets[list(w)]
    avail = R.notna()
    cov = (avail * W.abs()).sum(axis=1) / gross
    num = (R.fillna(0.0) * W).sum(axis=1)
    rp = (num / (cov.where(cov > 0))).clip(-1, 1)                    # riscala i pesi disponibili al lordo pieno
    rp = rp[cov >= min_coverage]
    full_gross = sum(abs(v) for v in weights.values())
    lev = max(full_gross - 1.0, 0.0)
    if lev > 0 and irx is not None:
        fin = (irx.reindex(rp.index, method="ffill").fillna(irx.dropna().iloc[-1] if irx.notna().any() else 2.0) / 100.0 + MARGIN_SPREAD) / TD
        rp = rp - lev * fin
    return dict(serie=rp, senza_dati=senza, copertura=round(float(gross / max(full_gross, 1e-9)), 3))


# ---------------------------------------------------------------------------------------------- Monte Carlo
def monte_carlo(rp: pd.Series, nav0: float, years: int = 1, n: int = 5000, block: int = 21, seed: int = 20261106,
                kill_dd: float = 0.35) -> dict:
    r = rp.dropna().values.astype(float)
    if len(r) < 252:
        raise ValueError("storia troppo corta per un Monte Carlo (servono almeno 252 giorni)")
    H = int(years * TD)
    rng = np.random.default_rng(seed)
    nb = math.ceil(H / block)
    starts = rng.integers(0, len(r), size=(n, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % len(r)
    sim = r[idx.reshape(n, -1)[:, :H]]
    nav = nav0 * np.cumprod(1.0 + sim, axis=1)
    nav = np.concatenate([np.full((n, 1), nav0), nav], axis=1)
    peak = np.maximum.accumulate(nav, axis=1)
    mdd = (nav / peak - 1.0).min(axis=1)
    term = nav[:, -1]
    steps = np.unique(np.linspace(0, H, 53).astype(int))
    qs = (5, 25, 50, 75, 95)
    fan = {str(q): [round(float(x), 0) for x in np.percentile(nav[:, steps], q, axis=0)] for q in qs}
    hist, edges = np.histogram(term / nav0 - 1.0, bins=40)
    return dict(anni=years, percorsi=n, blocco=block, giorni=H, passi=[int(s) for s in steps], ventaglio=fan,
                istogramma=dict(conteggi=[int(x) for x in hist], bordi=[round(float(e), 4) for e in edges]),
                nav0=round(nav0, 0), kill_livello=round(nav0 * (1 - kill_dd), 0),
                finale={str(q): round(float(np.percentile(term, q)), 0) for q in qs},
                p_perdita=round(float((term < nav0).mean()), 4), p_perdita_10=round(float((term < 0.9 * nav0).mean()), 4),
                p_guadagno_20=round(float((term > 1.2 * nav0).mean()), 4), p_guadagno_50=round(float((term > 1.5 * nav0).mean()), 4),
                p_kill=round(float((mdd <= -kill_dd).mean()), 4),
                dd_mediano=round(float(np.median(mdd)), 4), dd_95=round(float(np.percentile(mdd, 5)), 4),
                rendimento_medio=round(float(term.mean() / nav0 - 1), 4), rendimento_mediano=round(float(np.median(term) / nav0 - 1), 4),
                storia_giorni=int(len(r)), storia_dal=str(rp.dropna().index[0].date()))


# ---------------------------------------------------------------------------------------------- stress e rischio
def stress(rp: pd.Series, nav0: float) -> list[dict]:
    out = []
    for name, a, b in EPISODES:
        seg = rp[(rp.index >= pd.Timestamp(a)) & (rp.index <= pd.Timestamp(b))]
        if len(seg) < 10:
            out.append(dict(nome=name, dal=a, al=b, disponibile=False))
            continue
        curve = (1 + seg).cumprod()
        out.append(dict(nome=name, dal=a, al=b, disponibile=True, rendimento=round(float(curve.iloc[-1] - 1), 4),
                        drawdown=round(float((curve / curve.cummax() - 1).min()), 4), euro=round(float((curve.iloc[-1] - 1) * nav0), 0)))
    return out


def risk_metrics(rp: pd.Series, rets: pd.DataFrame, weights: dict[str, float], nav0: float, kill_dd: float = 0.35) -> dict:
    r = rp.dropna()
    var95, var99 = float(-np.percentile(r, 5)), float(-np.percentile(r, 1))
    cvar95 = float(-r[r <= np.percentile(r, 5)].mean())
    spy = rets["SPY"].reindex(r.index) if "SPY" in rets else None
    beta = corr = None
    if spy is not None and spy.notna().sum() > 60:
        both = pd.concat([r, spy], axis=1).dropna()
        cov = np.cov(both.iloc[:, 0], both.iloc[:, 1])
        beta, corr = float(cov[0, 1] / cov[1, 1]), float(np.corrcoef(both.iloc[:, 0], both.iloc[:, 1])[0, 1])
    curve = (1 + r).cumprod()
    out = dict(vol_annua=round(float(r.std() * math.sqrt(TD)), 4), var95=round(var95, 4), var99=round(var99, 4), cvar95=round(cvar95, 4),
               var95_eur=round(var95 * nav0, 0), cvar95_eur=round(cvar95 * nav0, 0),
               beta_spy=None if beta is None else round(beta, 2), corr_spy=None if corr is None else round(corr, 2),
               dd_storico=round(float((curve / curve.cummax() - 1).min()), 4),
               giorni_var_al_kill=round(float(kill_dd / var95), 1) if var95 > 0 else None,
               rendimento_annuo_storico=round(float(curve.iloc[-1] ** (TD / len(r)) - 1), 4))
    # contributi al rischio (ultimi 2 anni, titoli con storia completa)
    w = pd.Series({k: v for k, v in weights.items() if k in rets})
    R = rets[list(w.index)].tail(504).dropna(axis=1, how="any")
    w = w[R.columns]
    if len(R) > 120 and len(w) >= 2:
        C = R.cov().values * TD
        wv = w.values
        marg = C @ wv
        tot = float(wv @ marg)
        rc = wv * marg / tot if tot > 0 else wv * 0
        order = np.argsort(-np.abs(rc))
        out["contributi"] = [dict(simbolo=str(w.index[i]), peso=round(float(wv[i]), 4), quota_rischio=round(float(rc[i]), 4)) for i in order[:14]]
        cls = {"azioni": 0.0, "ETF": 0.0, "crypto": 0.0}
        etf = set(charts.PROXY_ETF) | set(charts.ALIAS)
        for name, c_ in zip(w.index, rc):
            cls["crypto" if name in charts.CRYPTO else "ETF" if name in etf else "azioni"] += float(c_)
        out["rischio_classi"] = {k: round(v, 4) for k, v in cls.items()}
        out["titoli_indipendenti"] = round(float(math.exp(-np.sum(np.where(rc > 0, rc * np.log(np.where(rc > 0, rc, 1)), 0)))), 1)
    return out


def composition(weights: dict[str, float]) -> dict:
    crypto = set(charts.CRYPTO)
    etf = set(charts.PROXY_ETF) | set(charts.ALIAS)
    cls = {"azioni": 0.0, "ETF": 0.0, "crypto": 0.0}
    for k, v in weights.items():
        cls["crypto" if k in crypto else "ETF" if k in etf else "azioni"] += abs(v)
    return {k: round(v, 4) for k, v in cls.items()}


def forecasts_open(limit: int = 12) -> list[dict]:
    return db.q("SELECT agent_id, statement, prob, deadline, criterion FROM forecasts WHERE outcome IS NULL AND canary=0 "
                "ORDER BY deadline LIMIT ?", (limit,))


# ---------------------------------------------------------------------------------------------- tutto insieme
def overview(years: int = 1, nav0: float | None = None, weights: dict | None = None, close: pd.DataFrame | None = None, **kw) -> dict:
    close = charts.load_close() if close is None else close
    if close is None:
        return dict(ok=False, motivo="mancano i prezzi: lancia firm.py data")
    pf = portfolio(**kw) if weights is None else dict(pesi=weights, lordo=sum(abs(v) for v in weights.values()),
                                                       leva=max(sum(abs(v) for v in weights.values()) - 1, 0), quota_crypto=0.0, fonti={})
    if not pf["pesi"]:
        return dict(ok=False, motivo="GERVA-Q non ha ancora scritto i suoi pesi (state/model_latest.json)", portafoglio=pf)
    if nav0 is None:
        ch = db.runtime_get("ibkr.challenge") or {}
        nav0 = float(ch.get("nav_eur") or (db.runtime_get("ibkr.start_nav") or {}).get("nav") or 1_000_000)
    kill = float(S.risk_limits()["firm"]["kill_drawdown"]) if os.path.exists(S.RISK_FILE) else 0.35
    rets = returns_matrix(list(pf["pesi"]), close)
    irx = None
    for src in ("^IRX",):
        if src in close:
            irx = close[src]
    bc = backcast(pf["pesi"], rets, irx)
    rp = bc["serie"]
    if len(rp) < 252:
        return dict(ok=False, motivo="storia insufficiente per i titoli del portafoglio", portafoglio=pf, senza_dati=bc["senza_dati"])
    return dict(ok=True, nav=round(nav0, 0), portafoglio=pf, composizione=composition(pf["pesi"]), copertura=bc["copertura"],
                senza_dati=bc["senza_dati"], kill=kill, rischio=risk_metrics(rp, rets, pf["pesi"], nav0, kill),
                montecarlo=monte_carlo(rp, nav0, years, kill_dd=kill), stress=stress(rp, nav0), previsioni=forecasts_open())
