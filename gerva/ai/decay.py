"""
Decadimento del vantaggio e rotazione delle strategie, deterministici.

Ogni strategia ha un'attesa (lo Sharpe del backtest, dimezzato: l'attesa realistica). Dal vivo si misura la
probabilita' che lo Sharpe vero sia sopra zero (PSR). Regole, tutte in riduzione:

    meno di MIN_DAYS giorni dal vivo                      -> 1,0  (troppo presto per giudicare)
    PSR(Sharpe vero > 0) < 0,20                           -> 0,5  (in osservazione)
    PSR < 0,05, oppure caduta dal vivo > 1,5 x quella del backtest  -> 0,0  (in pausa: decide Andrea se riattivarla)

Una strategia in pausa continua a essere calcolata "in ombra": se il PSR risale sopra 0,5 viene proposta per il rientro,
non rientra da sola.
"""
from __future__ import annotations

import pandas as pd

from ..validation import metrics as M

MIN_DAYS = 60


def multiplier(live: pd.Series, backtest_max_dd: float, periods: int = 365) -> tuple[float, str]:
    r = live.dropna()
    if len(r) < MIN_DAYS:
        return 1.0, f"{len(r)} giorni dal vivo: troppo presto"
    psr = M.psr(r, 0.0, periods)
    dd = float(M.drawdown(r).min())
    if psr < 0.05 or (backtest_max_dd < 0 and dd < 1.5 * backtest_max_dd):
        return 0.0, f"in pausa: PSR {psr:.2f}, caduta {dd:.1%} (backtest {backtest_max_dd:.1%})"
    if psr < 0.20:
        return 0.5, f"in osservazione: PSR {psr:.2f}"
    return 1.0, f"regolare: PSR {psr:.2f}"


def review(live_by_sleeve: dict[str, pd.Series], backtest_dd: dict[str, float], periods: dict[str, int]) -> dict:
    out = {}
    for k, r in live_by_sleeve.items():
        m, why = multiplier(r, backtest_dd.get(k, -0.3), periods.get(k, 365))
        out[k] = dict(mult=m, motivo=why)
    return out
