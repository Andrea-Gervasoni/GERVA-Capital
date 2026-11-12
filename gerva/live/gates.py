"""
Cancelli numerici per passare dal paper al denaro reale. Li valuta il codice sul registro del paper trading:
non c'e' un'opinione da dare, c'e' una tabella da leggere. Tutti devono essere verdi; uno rosso = si resta in paper.

    1. almeno 90 giorni di paper trading consecutivo
    2. disponibilita' del ciclo >= 99% (giri eseguiti / giri attesi)
    3. zero ordini rimasti non riconciliati
    4. zero KILL scattati per difetti del software (un KILL per caduta di mercato va capito, non contato)
    5. caduta massima in paper <= 15% (la soglia del primo scalino di rischio)
    6. Sharpe realizzato >= 0 e non incompatibile con il backtest: PSR(Sharpe vero > 0) >= 0,60
       (90 giorni non bastano a "provare" uno Sharpe: bastano a scoprire che e' negativo o che il sistema non
       replica il backtest)
    7. scostamento dal backtest: |rendimento paper - rendimento del backtest sugli stessi giorni| <= 3 punti
    8. costi reali <= 1,5 volte quelli ipotizzati nel backtest

Criterio 7: a ogni giro il ciclo annota il moltiplicatore di esposizione usato (leva x scala di rischio); il rendimento
"da modello" di un giorno e' quel moltiplicatore per il rendimento simulato del portafoglio il giorno dopo. Si confrontano
i rendimenti cumulati di paper e modello sugli stessi giorni. E' un confronto a grana grossa (i prezzi del paper sono le
ultime chiusure): serve a scoprire se il sistema NON replica il backtest, non a misurare i centesimi.
Criterio 8: dagli eseguiti nel registro, (|prezzo eseguito - prezzo di riferimento| x quantita' + commissioni) / controvalore,
diviso per il costo ipotizzato nei backtest per quella sede.
"""
from __future__ import annotations

import time

import pandas as pd

from ..validation import metrics as M

MIN_DAYS = 90
MIN_UPTIME = 0.99
MAX_DD = 0.15                  # il primo scalino del motore di rischio nel profilo scelto (config/gerva.yaml)
MIN_PSR = 0.60
MAX_TRACKING = 0.03
MAX_COST_RATIO = 1.5
ASSUMED_COST = {"crypto": 0.0030, "ibkr": 0.0008}     # per lato, come in gerva.strategies.book (ibkr: media tra ETF e CFD su indice)


def tracking(daily: pd.Series, model_daily: pd.Series | None) -> float | None:
    """Differenza tra rendimento cumulato del paper e del modello sui giorni in comune (None se meno di 20)."""
    if model_daily is None or not len(daily) or not len(model_daily):
        return None
    idx = daily.index.intersection(model_daily.index)
    if len(idx) < 20:
        return None
    return float((1 + daily.loc[idx]).prod() - (1 + model_daily.loc[idx]).prod())


def cost_ratio(journal) -> float | None:
    """Costo medio realizzato per lato, ponderato per controvalore, diviso per quello ipotizzato (None sotto i 10 eseguiti)."""
    rows = journal.db.execute("SELECT venue, fill_qty, fill_price, ref_price, fee FROM orders WHERE status IN ('filled','partial') "
                              "AND fill_price > 0 AND ref_price > 0").fetchall()
    if len(rows) < 10:
        return None
    paid = assumed = 0.0
    for r in rows:
        notional = abs(r["fill_qty"]) * r["fill_price"]
        paid += abs(r["fill_price"] - r["ref_price"]) * abs(r["fill_qty"]) + (r["fee"] or 0.0)
        assumed += notional * ASSUMED_COST.get(r["venue"], 0.001)
    return paid / assumed if assumed > 0 else None


def evaluate(journal, daily: pd.Series, now: float | None = None, interval: float = 900.0,
             model_daily: pd.Series | None = None) -> list[dict]:
    now = now or time.time()
    if journal is None:
        return [dict(name="Giorni di paper trading", value=0, target=MIN_DAYS, unit="giorni", ok=False),
                dict(name="Disponibilita' del ciclo", value=None, target=MIN_UPTIME, unit="%", ok=False),
                dict(name="Ordini non riconciliati", value=None, target=0, unit="ordini", ok=False),
                dict(name="Caduta massima in paper", value=None, target=-MAX_DD, unit="%", ok=False),
                dict(name="PSR (Sharpe vero > 0)", value=None, target=MIN_PSR, unit="", ok=False)]
    start = journal.get("start_ts") or now
    days = (now - start) / 86400.0
    n_nav = journal.db.execute("SELECT COUNT(*) c FROM nav").fetchone()["c"]
    expected = max((now - start) / interval, 1.0)
    uptime = min(n_nav / expected, 1.0)
    unknown = journal.db.execute("SELECT COUNT(*) c FROM orders WHERE status IN ('intent','unknown') AND ts < ?", (now - 3600,)).fetchone()["c"]
    kills = journal.db.execute("SELECT COUNT(*) c FROM events WHERE component='risk' AND msg LIKE 'KILL:%'").fetchone()["c"]
    eq = (1 + daily).cumprod() if len(daily) else pd.Series(dtype=float)
    dd = float((eq / eq.cummax() - 1).min()) if len(eq) else 0.0
    psr = M.psr(daily, 0.0, 365) if len(daily) >= 30 else None
    te, cr = tracking(daily, model_daily), cost_ratio(journal)
    return [
        dict(name="Giorni di paper trading", value=round(days, 1), target=MIN_DAYS, unit="giorni", ok=days >= MIN_DAYS),
        dict(name="Disponibilita' del ciclo", value=uptime, target=MIN_UPTIME, unit="%", ok=uptime >= MIN_UPTIME and days >= 1),
        dict(name="Ordini non riconciliati", value=unknown, target=0, unit="ordini", ok=unknown == 0),
        dict(name="KILL scattati", value=kills, target=0, unit="eventi", ok=kills == 0),
        dict(name="Caduta massima in paper", value=dd, target=-MAX_DD, unit="%", ok=dd >= -MAX_DD),
        dict(name="PSR (Sharpe vero > 0)", value=psr, target=MIN_PSR, unit="", ok=bool(psr is not None and psr >= MIN_PSR)),
        dict(name="Scostamento dal backtest", value=te, target=MAX_TRACKING, unit="%", ok=bool(te is not None and abs(te) <= MAX_TRACKING)),
        dict(name="Costi reali / costi ipotizzati", value=cr, target=MAX_COST_RATIO, unit="x", ok=bool(cr is not None and cr <= MAX_COST_RATIO)),
    ]


def all_green(g: list[dict]) -> bool:
    return bool(g) and all(x["ok"] for x in g)
