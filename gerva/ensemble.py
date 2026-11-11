"""
Ensemble di segnali e conviction.

Idea: nessun indicatore da solo decide. Ogni strumento ha una batteria di segnali binari (trend su piu' orizzonti,
medie, rottura dei massimi, volatilita' bassa, ipervenduto, regime del mercato, funding non surriscaldato, per gli
indici anche struttura della curva VIX e GEX). La conviction e' la quota di segnali accesi, nota la sera prima.

Che cosa ha mostrato la ricerca (research/v5/v2/conviction.out, dati reali, simulato):
  * crypto: i giorni ad alta conviction hanno Sharpe condizionato ~1,9 (BTC, scelta E verifica); bassa e media ~0;
  * indici: la conviction NON ordina i rendimenti; ordina la volatilita' (alta conviction = mercato calmo);
  * la quota di giorni vincenti resta 51-54% anche al livello alto: non esistono "setup ad alta probabilita'",
    il vantaggio sta nell'ampiezza dei guadagni;
  * 11-12 segnali valgono ~5 segnali indipendenti (correlazione media 0,2);
  * i pesi sono UGUALI: stimarli su pochi anni aggiunge errore (Rapach, Strauss, Zhou 2010).

I livelli (bassa / media / alta) usano soglie FISSE scelte sul periodo fino al 2022: non si ristimano dal vivo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind

TIERS = ("bassa", "media", "alta")
# soglie sulla quota di segnali accesi (terzili del periodo di scelta, research/v5/v2/conviction.out)
THRESHOLDS = {"crypto": (0.30, 0.58), "index": (0.55, 0.78)}


def crypto_signals(bars: pd.DataFrame, btc_close: pd.Series, funding_daily: pd.Series | None = None) -> pd.DataFrame:
    """bars: open, high, low, close giornalieri. Ogni colonna e' 0/1 e usa solo dati fino alla riga."""
    cl = bars["close"]
    r = cl.pct_change(fill_method=None)
    F = pd.DataFrame(index=cl.index)
    for lb in (10, 30, 60, 120):
        F[f"trend{lb}"] = cl / cl.shift(lb) - 1 > 0
    F["ma100"] = cl > cl.rolling(100).mean()
    F["ma200"] = cl > cl.rolling(200).mean()
    F["brk20"] = cl >= cl.rolling(20).max().shift(1)
    v = r.rolling(20).std()
    F["lowvol"] = v < v.rolling(365, min_periods=120).median()
    F["ibs_low"] = ind.ibs(bars["high"], bars["low"], cl) < 0.2
    F["mom7"] = cl / cl.shift(7) - 1 > 0
    F["btc_ma100"] = (btc_close > btc_close.rolling(100).mean()).reindex(cl.index)
    if funding_daily is not None:
        F["fund_ok"] = (funding_daily.rolling(7).mean() * 365 < 0.30).reindex(cl.index).fillna(True)
    return F.astype(float)


def index_signals(high, low, close, adj, vix, vix3m, gex_rank: pd.Series | None = None) -> pd.DataFrame:
    r = adj.pct_change(fill_method=None)
    F = pd.DataFrame(index=adj.index)
    for lb in (21, 63, 126, 252):
        F[f"trend{lb}"] = adj / adj.shift(lb) - 1 > 0
    F["ma200"] = adj > adj.rolling(200).mean()
    F["ibs_low"] = ind.ibs(high, low, close) < 0.2
    v = r.rolling(20).std()
    F["lowvol"] = v < v.rolling(252, min_periods=120).median()
    F["contango"] = vix / vix3m < 0.95
    F["vix_calm"] = vix < vix.rolling(252).median()
    if gex_rank is not None:
        F["gex_hi"] = (gex_rank > 0.5).reindex(adj.index)
    F["down3"] = adj / adj.shift(3) - 1 < 0
    return F.astype(float)


def conviction(signals: pd.DataFrame, kind: str = "crypto") -> pd.DataFrame:
    """Colonne: score (0..1, quota di segnali accesi), tier ('bassa'|'media'|'alta'), n (segnali validi).
    Righe con segnali mancanti: tier 'bassa' (nel dubbio, il livello piu' prudente)."""
    ok = signals.notna().all(axis=1)
    score = signals.mean(axis=1).where(ok)
    lo, hi = THRESHOLDS[kind]
    tier = pd.Series(np.where(score > hi, "alta", np.where(score > lo, "media", "bassa")), index=signals.index)
    return pd.DataFrame(dict(score=score, tier=tier.where(ok, "bassa"), n=signals.notna().sum(axis=1)))


def effective_signals(signals: pd.DataFrame) -> float:
    """Numero di segnali 'indipendenti' (rapporto di partecipazione degli autovalori della correlazione)."""
    c = signals.dropna().corr().to_numpy()
    ev = np.linalg.eigvalsh(np.nan_to_num(c))
    return float(ev.sum() ** 2 / (ev ** 2).sum())
