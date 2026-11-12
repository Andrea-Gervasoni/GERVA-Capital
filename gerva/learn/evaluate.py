"""Motore di valutazione: non misura solo il rendimento, cerca dove la strategia e' debole.

Tre gruppi di misure (prestazione, rischio, robustezza) e una ricerca delle DEBOLEZZE: fette di trade, definite dal
contesto all'ingresso, il cui R medio e' significativamente sotto quello degli altri. Una debolezza non e' una correzione:
e' un'ipotesi da validare (gerva.learn.improve)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .features import CATEGORICAL, NUMERIC

MIN_SLICE = 30                  # trade minimi in una fetta perche' se ne parli


def _streak(x: np.ndarray) -> int:
    best = cur = 0
    for v in x:
        cur = cur + 1 if v < 0 else 0
        best = max(best, cur)
    return best


def evaluate(df: pd.DataFrame) -> dict:
    """df: tabella della memoria (colonne R, pnl, exit_reason, entry_time, ...)."""
    if df is None or not len(df):
        return dict(n=0)
    R = df["R"].to_numpy(float)
    n = len(R)
    wins, losses = R[R > 0], R[R <= 0]
    eq = np.cumsum(R)
    dd = float((eq - np.maximum.accumulate(eq)).min())
    years = max((df["entry_time"].max() - df["entry_time"].min()).days / 365.25, 1e-9)
    sd = R.std(ddof=1) if n > 1 else float("nan")
    out = dict(
        n=n, per_year=n / years if years > 0.05 else None,
        performance=dict(mean_R=float(R.mean()), total_R=float(R.sum()), win_rate=float((R > 0).mean()),
                         profit_factor=float(wins.sum() / -losses.sum()) if losses.sum() < 0 else None,
                         payoff=float(wins.mean() / -losses.mean()) if len(wins) and len(losses) and losses.mean() < 0 else None,
                         t_stat=float(R.mean() / sd * math.sqrt(n)) if n > 2 and sd > 0 else None,
                         ratio=float(R.mean() / sd) if n > 2 and sd > 0 else None,
                         kelly_fraction=float(R.mean() / R.var(ddof=1)) if n > 2 and R.var(ddof=1) > 0 else None),
        risk=dict(max_drawdown_R=dd, max_losing_streak=_streak(R), worst_R=float(R.min()), var95_R=float(np.quantile(R, 0.05)),
                  cvar95_R=float(R[R <= np.quantile(R, 0.05)].mean())),
        robustness=dict(by_year={int(y): dict(n=int(len(g)), mean_R=float(g.mean())) for y, g in df.groupby(df["entry_time"].dt.year)["R"]},
                        by_exit={str(k): dict(n=int(len(g)), mean_R=float(g.mean())) for k, g in df.groupby("exit_reason")["R"]},
                        recent_vs_past=_recent(df)),
    )
    if "source" in df.columns:
        out["by_source"] = {str(k): dict(n=int(len(g)), mean_R=float(g.mean())) for k, g in df.groupby("source")["R"]}
    paper = df[df.get("source", "sim") != "sim"] if "source" in df.columns else df.iloc[0:0]
    if len(paper):
        out["execution"] = dict(n=int(len(paper)), slippage_bp=float(paper["slippage"].mean() * 1e4) if "slippage" in paper else None,
                                cost_R=float(((paper.get("commission", 0) + paper.get("funding", 0)) / paper["risk"]).mean()))
    return out


def _recent(df: pd.DataFrame, k: int = 40) -> dict | None:
    if len(df) < 2 * k:
        return None
    a, b = df["R"].iloc[:-k], df["R"].iloc[-k:]
    se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return dict(past_mean_R=float(a.mean()), recent_mean_R=float(b.mean()), t=float((b.mean() - a.mean()) / se) if se > 0 else None, recent_n=k)


def buckets(df: pd.DataFrame, ref: pd.DataFrame | None = None) -> dict[str, list]:
    """Fette candidate: terzili delle grandezze numeriche (soglie calcolate su `ref`, di norma il periodo di scelta) e
    valori delle grandezze categoriche. Restituisce feature -> lista di (etichetta, maschera, definizione della regola)."""
    ref = df if ref is None else ref
    out = {}
    for f in NUMERIC:
        if f not in df.columns or ref[f].notna().sum() < 3 * MIN_SLICE:
            continue
        q1, q2 = ref[f].quantile([1 / 3, 2 / 3])
        if not q1 < q2:
            continue
        x = df[f]
        out[f] = [(f"{f} <= {q1:.4g}", x <= q1, dict(feature=f, op="<=", value=float(q1))),
                  (f"{f} > {q2:.4g}", x > q2, dict(feature=f, op=">", value=float(q2)))]
    for f in CATEGORICAL:
        if f in df.columns:
            out[f] = [(f"{f} = {v}", df[f] == v, dict(feature=f, op="==", value=(v.item() if hasattr(v, "item") else v)))
                      for v in sorted(df[f].dropna().unique(), key=str)]
    return out


def weaknesses(df: pd.DataFrame, ref: pd.DataFrame | None = None, t_min: float = -2.0) -> list[dict]:
    """Fette con R medio significativamente sotto il resto (test di Welch), in ordine di gravita'."""
    if df is None or len(df) < 2 * MIN_SLICE:
        return []
    found = []
    for f, items in buckets(df, ref).items():
        for label, mask, rule in items:
            mask = mask.fillna(False).to_numpy(bool)
            a, b = df["R"].to_numpy(float)[mask], df["R"].to_numpy(float)[~mask]
            if len(a) < MIN_SLICE or len(b) < MIN_SLICE:
                continue
            se = math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
            t = (a.mean() - b.mean()) / se if se > 0 else 0.0
            if t <= t_min:
                found.append(dict(slice=label, feature=f, n=int(len(a)), share=float(mask.mean()), mean_R=float(a.mean()),
                                  rest_mean_R=float(b.mean()), t=float(t), cost_total_R=float(a.sum()), rule=rule,
                                  action="Provare a saltare o a dimezzare i trade di questa fetta"))
    return sorted(found, key=lambda w: w["t"])
