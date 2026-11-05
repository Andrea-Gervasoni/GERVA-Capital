"""
Quota di lungo periodo sull'infrastruttura AI: piano di acquisto e misura del RISCHIO (non del rendimento).

Perche' non si "dimostra" che rendera': il paniere e' scelto oggi, sapendo quali aziende hanno vinto. Il suo
rendimento passato e' quindi gonfiato dal senno di poi (survivorship e selezione ex post) e non e' una prova.
Il passato serve solo a misurare quanto puo' far male: volatilita', anno peggiore, caduta massima.
Evidenza utile: gli ETF tematici lanciati sull'onda di un tema hanno reso in media meno del mercato dopo il lancio
(Ben-David, Franzoni, Kim e Moussawi, "Competition for Attention in the ETF Space", 2023; citazione a memoria,
da ricontrollare). Per questo: quota piccola, pesi uguali lungo la catena, nessun market timing.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def basket_returns(close: pd.DataFrame, names: list[str]) -> pd.Series:
    """Pesi uguali ribilanciati ogni anno; ogni titolo entra quando e' quotato."""
    P = close[[n for n in names if n in close]].astype(float)
    r = P.pct_change()
    out, w = [], None
    for y, block in r.groupby(r.index.year):
        live = [c for c in block.columns if block[c].notna().any()]
        w = pd.Series(1 / len(live), index=live)
        nav = (1 + block[live].fillna(0)).cumprod()
        val = nav.mul(w, axis=1).sum(axis=1)
        out.append(val.pct_change().fillna(val.iloc[0] - 1))
    return pd.concat(out)


def risk_report(r: pd.Series, capital: float) -> dict:
    nav = (1 + r).cumprod()
    dd = float((nav / nav.cummax() - 1).min())
    yearly = (1 + r).groupby(r.index.year).prod() - 1
    vol = float(r.std() * math.sqrt(252))
    return dict(vol=vol, caduta_massima=dd, anno_peggiore=float(yearly.min()), anno_peggiore_quale=int(yearly.idxmin()),
                caduta_massima_eur=dd * capital, anno_peggiore_eur=float(yearly.min()) * capital,
                giorno_peggiore=float(r.min()), anni=len(yearly))


def plan(nav_eur: float, quota: float, prices_usd: dict[str, float], eurusd: float) -> pd.DataFrame:
    """Quante azioni intere comprare per titolo (pesi uguali sulla quota)."""
    per = nav_eur * quota / len(prices_usd)
    rows = []
    for k, px in prices_usd.items():
        px_eur = px / eurusd
        n = math.floor(per / px_eur)
        rows.append(dict(titolo=k, prezzo_usd=px, euro_obiettivo=per, azioni=n, euro_investiti=n * px_eur))
    return pd.DataFrame(rows).set_index("titolo")


def correlation_with(r: pd.Series, other: pd.Series) -> float:
    j = pd.concat([r, other], axis=1).dropna()
    return float(np.corrcoef(j.iloc[:, 0], j.iloc[:, 1])[0, 1]) if len(j) > 30 else float("nan")
