"""
Il contratto tra gli agenti e il motore: una IPOTESI e' una scheda dichiarativa, non codice.

Un agente (LLM o persona) puo' solo riempire una `StrategySpec`: famiglia, universo, parametri dentro limiti fissati qui.
Il backtest lo esegue `evaluate`, con i costi e il ritardo di esecuzione standard; il verdetto lo emette `gate`.
Nessun agente scrive codice di strategia, tocca i limiti di rischio o vede il broker.

Ogni valutazione finisce nel registro delle prove (append-only, con catena di hash): il numero di prove alza la soglia
di fortuna per tutte le ipotesi successive. Provare cento varianti ha un prezzo, ed e' il registro a farlo pagare.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass, field

import pandas as pd

from ..backtest import Costs, run
from ..strategies import book
from ..strategies import daily as SD
from ..validation import metrics as M

SPLIT = "2023-01-01"

# famiglia -> parametri ammessi con (minimo, massimo). Fuori da qui la scheda e' respinta prima di ogni calcolo.
FAMILIES = {
    "crypto_trend": dict(venue="crypto", params=dict(lookback_fast=(5, 60), lookback_slow=(40, 250), rebalance_days=(1, 30),
                                                     asset_vol=(0.2, 0.8)), universes=("BTC_ETH", "TOP10")),
    "crypto_xsmom": dict(venue="crypto", params=dict(lookback=(7, 120), top=(2, 8), universe=(8, 30), rebalance_days=(3, 30)),
                         universes=("TOP_VOLUME",)),
    "index_ibs": dict(venue="ibkr", params=dict(enter=(0.05, 0.4), exit=(0.5, 0.95)), universes=("SPY", "QQQ", "SPY_QQQ")),
    "etf_trend": dict(venue="ibkr", params=dict(lookback_fast=(20, 130), lookback_slow=(120, 300), rebalance_days=(1, 30)),
                      universes=("MULTI_ASSET_17",)),
}


@dataclass
class StrategySpec:
    family: str
    universe: str
    params: dict
    hypothesis: str                      # perche' dovrebbe funzionare: il meccanismo economico, scritto PRIMA del test
    author: str = "anonimo"
    refs: list = field(default_factory=list)

    def key(self) -> str:
        return hashlib.sha256(json.dumps([self.family, self.universe, sorted(self.params.items())]).encode()).hexdigest()[:12]


def validate(spec: StrategySpec) -> list[str]:
    errs = []
    fam = FAMILIES.get(spec.family)
    if not fam:
        return [f"famiglia sconosciuta: {spec.family} (ammesse: {', '.join(FAMILIES)})"]
    if spec.universe not in fam["universes"]:
        errs.append(f"universo non ammesso per {spec.family}: {spec.universe}")
    for k, v in spec.params.items():
        if k not in fam["params"]:
            errs.append(f"parametro non ammesso: {k}")
        elif not isinstance(v, (int, float)) or isinstance(v, bool) or not fam["params"][k][0] <= v <= fam["params"][k][1]:
            errs.append(f"{k}={v} fuori da {fam['params'][k]}")
    missing = set(fam["params"]) - set(spec.params)
    if missing:
        errs.append(f"parametri mancanti: {sorted(missing)}")
    if "lookback_fast" in spec.params and spec.params.get("lookback_fast", 0) >= spec.params.get("lookback_slow", 10 ** 9):
        errs.append("lookback_fast deve essere minore di lookback_slow")
    if len(spec.hypothesis.strip()) < 40:
        errs.append("ipotesi troppo breve: serve il meccanismo economico (almeno 40 caratteri)")
    return errs


def _returns(spec: StrategySpec, lab, fee_mult: float = 1.0, lag: int = 1) -> tuple[pd.Series, pd.Series, int]:
    """Rendimenti netti giornalieri della scheda, tasso a breve corrispondente, periodi per anno."""
    p = spec.params
    if spec.family in ("crypto_trend", "crypto_xsmom"):
        close, dvol, ret = lab.cclose, lab.cdvol, lab.cret
        cost = Costs(trade=book.CRYPTO_FEE * fee_mult, cash_haircut=1.0)
        if spec.family == "crypto_trend":
            if spec.universe == "BTC_ETH":
                c = close[["BTC", "ETH"]]
                cap = 0.5
            else:
                adv = dvol.rolling(30, min_periods=20).mean()
                c = close.where(adv.rank(axis=1, ascending=False) <= 10)
                cap = 0.15
            lbs = tuple(sorted({int(p["lookback_fast"]), int((p["lookback_fast"] + p["lookback_slow"]) / 2), int(p["lookback_slow"])}))
            W = SD.trend(c, lookbacks=lbs, long_only=True, asset_vol=p["asset_vol"], span=30, periods=365).clip(upper=cap)
            W = SD.hold(W, int(p["rebalance_days"]))
            r = run(W, ret[W.columns], 0.0, cost, lag=lag, periods=365, band=0.03).ret
        else:
            btc_up = close["BTC"] > close["BTC"].rolling(100).mean()
            lb = int(p["lookback"])
            W = SD.xs_momentum(close, dvol, (max(lb // 2, 3), lb, lb * 2), int(p["top"]), int(p["universe"]),
                               int(p["rebalance_days"]), btc_up)
            r = run(W, ret, 0.0, cost, lag=lag, periods=365, band=0.03).ret
        return r.loc["2018":], lab.rf365, 365
    P, rf = lab.P, lab.rf
    eret = P["adj"].pct_change(fill_method=None)
    if spec.family == "index_ibs":
        syms = ["SPY", "QQQ"] if spec.universe == "SPY_QQQ" else [spec.universe]
        W = pd.DataFrame({s: SD.ibs_reversion(P["high"][s], P["low"][s], P["close"][s], p["enter"], p["exit"], None) / len(syms)
                          for s in syms})
        held = W.shift(lag).fillna(0.0)
        carry = rf + book.CFD_SPREAD / 252
        r = (held * eret[syms].sub(carry, axis=0)).sum(axis=1) - W.diff().abs().fillna(0.0).sum(axis=1) * book.INDEX_FEE * fee_mult
        return r.loc["2005":], rf, 252
    c = P["adj"][book.TREND_UNIVERSE].loc["2003":]
    R = c.pct_change(fill_method=None)
    lbs = tuple(sorted({int(p["lookback_fast"]), int((p["lookback_fast"] + p["lookback_slow"]) / 2), int(p["lookback_slow"])}))
    W = SD.hold(SD.vol_target(SD.trend(c, lookbacks=lbs, long_only=True), R, 0.10, max_leverage=1.0), int(p["rebalance_days"]))
    r = run(W, R, rf, Costs(trade=book.ETF_FEE * fee_mult, cash_haircut=1.0), lag=lag, band=0.02).ret
    return r.loc["2005":], rf, 252


def evaluate(spec: StrategySpec, lab) -> dict:
    """Backtest standard di una scheda valida. `lab` e' un gerva.research.run.Lab con i dati caricati."""
    errs = validate(spec)
    if errs:
        return dict(spec=asdict(spec), valida=False, errori=errs)
    r, rf, per = _returns(spec, lab)
    r2, _, _ = _returns(spec, lab, fee_mult=2.0)
    rl, _, _ = _returns(spec, lab, lag=2)
    s_all, s_sel, s_ver = M.summary(r, rf, per), M.summary(r.loc[:SPLIT], rf, per), M.summary(r.loc[SPLIT:], rf, per)
    return dict(spec=asdict(spec), key=spec.key(), valida=True, periodi=per,
                sharpe=s_all.get("sharpe"), sharpe_scelta=s_sel.get("sharpe"), sharpe_verifica=s_ver.get("sharpe"),
                cagr=s_all.get("cagr"), vol=s_all.get("vol"), max_dd=s_all.get("max_dd"), mese_peggiore=s_all.get("mese_peggiore"),
                sharpe_costi_doppi=M.summary(r2, rf, per).get("sharpe"), sharpe_ritardo_1g=M.summary(rl, rf, per).get("sharpe"),
                anni_scelta=s_sel.get("anni"), psr_scelta=s_sel.get("psr0"),
                excess=(r - rf.reindex(r.index).fillna(0.0)).loc[:SPLIT])


def gate(res: dict, n_trials: int) -> dict:
    """Cancello automatico. Tutte le condizioni devono valere; ognuna ha un motivo leggibile se fallisce."""
    if not res.get("valida"):
        return dict(passa=False, motivi=res.get("errori", ["scheda non valida"]))
    why = []
    years = res.get("anni_scelta") or 1.0
    luck = M.expected_max_sharpe(max(n_trials, 1), 1.0 / years)
    dsr = M.dsr(res["excess"], max(n_trials, 1), 1.0 / years, res["periodi"])
    if (res["sharpe_scelta"] or 0) < 0.5:
        why.append(f"Sharpe nel periodo di scelta {res['sharpe_scelta']:.2f} < 0,50")
    if (res["sharpe_verifica"] or 0) < 0.25:
        why.append(f"Sharpe nel periodo di verifica {res['sharpe_verifica']:.2f} < 0,25")
    if (res["sharpe_costi_doppi"] or 0) <= 0:
        why.append("con i costi raddoppiati lo Sharpe non e' positivo")
    if (res["sharpe_ritardo_1g"] or 0) <= 0:
        why.append("con un giorno di ritardo nell'esecuzione lo Sharpe non e' positivo")
    if (res["max_dd"] or -1) < -0.45:
        why.append(f"caduta massima {res['max_dd']:.0%} oltre il 45%")
    if dsr < 0.5:
        why.append(f"Deflated Sharpe {dsr:.2f} < 0,50 contro {n_trials} prove (Sharpe del migliore a caso: {luck:.2f})")
    return dict(passa=not why, motivi=why, dsr=dsr, sharpe_fortuna=luck, prove=n_trials)


class TrialRegistry:
    """Registro append-only con catena di hash: ogni riga contiene l'hash della precedente."""

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    def rows(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        with open(self.path) as f:
            return [json.loads(x) for x in f if x.strip()]

    def count(self) -> int:
        return len({r["key"] for r in self.rows()})

    def append(self, res: dict, verdict: dict, baseline: int = 0) -> dict:
        rows = self.rows()
        prev = rows[-1]["hash"] if rows else "0" * 16
        row = dict(ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), key=res.get("key") or "invalida",
                   spec=res["spec"], sharpe_scelta=res.get("sharpe_scelta"), sharpe_verifica=res.get("sharpe_verifica"),
                   passa=verdict["passa"], motivi=verdict["motivi"], prev=prev)
        row = {k: (None if isinstance(v, float) and not math.isfinite(v) else v) for k, v in row.items()}
        row["hash"] = hashlib.sha256((prev + json.dumps(row, sort_keys=True, default=str)).encode()).hexdigest()[:16]
        with open(self.path, "a") as f:
            f.write(json.dumps(row, default=str) + "\n")
        return row

    def verify(self) -> bool:
        prev = "0" * 16
        for r in self.rows():
            h = r.pop("hash")
            if r["prev"] != prev or hashlib.sha256((prev + json.dumps(r, sort_keys=True, default=str)).encode()).hexdigest()[:16] != h:
                return False
            prev = h
        return True
