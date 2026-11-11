"""
Portafoglio ombra: la v4 vincente del banco ("tutto") seguita IN AVANTI accanto alla v3, senza ordini.

Perche': un backtest che vince (anche con DSR, PBO e holdout) non basta per cambiare il motore nel mezzo della
sfida. Da una data di partenza fissa si registra ogni giorno il rendimento di entrambe le versioni, calcolato con
i soli dati disponibili quel giorno (i pesi decisi a t-1 si applicano a t). Ogni giorno si scrive UNA volta
(tabella append-only, UNIQUE(day, variant)): una revisione dei prezzi non puo' riscrivere il passato a favore
di nessuno.

REGOLA DI ADOZIONE SOSPESA (audit del 10/11, rilievi 9 e 10). La regola scritta il 5/11 diceva: dopo 40 giorni di
borsa in avanti, proporre la v4 se P(Sharpe v4 > v3) >= 0,80 nel bootstrap appaiato e il drawdown della v4 non supera
quello della v3. Due difetti:
  * in 40 giorni la regola non distingue un vantaggio dal caso: approvava circa un terzo delle volte anche con due
    serie SENZA alcuna differenza (35% su 136 finestre storiche; tests/test_audit_quantlab.py lo riproduce). Per
    costruzione P >= 0,80 scatta il 20% delle volte sotto l'ipotesi nulla, e la condizione sul drawdown favorisce la
    variante meno volatile, che e' proprio la v4;
  * la v4 "approvata" doveva il suo vantaggio alla liquidita' remunerata, misurata su rendimenti grezzi.
Finche' Andrea non approva una regola nuova, il portafoglio ombra REGISTRA e basta: `decide` non propone mai
l'adozione. Una regola nuova deve dichiarare PRIMA dei dati la sua frequenza di falsa approvazione (al piu' 5% con
vantaggio nullo) e dimostrarla con una simulazione; con una differenza di Sharpe di 0,2 questo richiede anni di
osservazione, non settimane.

Dalla correzione in poi le due varianti ricevono la stessa tesoreria (liquidita' al tasso a breve meno 0,10%) e i
confronti sono in eccesso del tasso. I giorni scritti PRIMA della correzione restano com'erano (tabella append-only):
la v4 con la cassa, la v3 senza. Non sono confrontabili e la sintesi lo segnala.
"""
from __future__ import annotations

import math
import os

import numpy as np
import pandas as pd

from . import db, events, paths

VARIANTS = ("v3_riferimento", "tutto")
START_KEY = "shadow.start"
START_DEFAULT = "2026-11-05"      # ultimo giorno visto dal banco (research/gervaq4/2026-11-05.md): registrata prima
RF_KEY = "shadow.rf"               # tasso a breve giornaliero dei giorni registrati (giorno -> tasso), scritto una volta per giorno
FIX_KEY = "shadow.tesoreria_dal"   # primo giorno registrato con la tesoreria uguale per v3 e v4
MIN_DAYS = 40
P_MIN = 0.80
ADOZIONE_SOSPESA = True            # audit del 10/11: la regola a 40 giorni approvava un terzo delle volte senza alcun vantaggio


def decide(v4, v3, rf=None) -> dict:
    """Verdetto del portafoglio ombra su due serie di rendimenti giornalieri in avanti (stessi giorni).
    rf: tasso a breve giornaliero degli stessi giorni (scalare o serie); il confronto e' in eccesso del tasso.
    Con ADOZIONE_SOSPESA non propone MAI l'adozione: riporta i numeri come informazione."""
    from quantlab import gervaq4 as G4, stats as QS
    v4, v3 = np.asarray(v4, float), np.asarray(v3, float)
    n = min(len(v4), len(v3))
    out = dict(giorni=n, adozione_proposta=False)
    if n >= 20:
        out["p_v4_meglio"] = G4.paired_sharpe_prob(QS.excess(v4, rf) if rf is not None else v4,
                                                   QS.excess(v3, rf) if rf is not None else v3)
    if n < MIN_DAYS:
        out["verdetto"] = f"in osservazione: {n}/{MIN_DAYS} giorni di borsa"
    elif ADOZIONE_SOSPESA:
        out["verdetto"] = ("regola di adozione SOSPESA (audit del 10/11): 40 giorni non distinguono un vantaggio dal caso "
                           "(la regola approvava un terzo delle volte senza alcun vantaggio). Si resta sulla v3; "
                           "i numeri in avanti valgono come informazione")
    else:                                           # ramo spento: resta per documentare la regola del 5/11, non per usarla
        dd = lambda x: float((np.cumprod(1 + x) / np.maximum.accumulate(np.cumprod(1 + x)) - 1).min())
        ok = out.get("p_v4_meglio", 0) >= P_MIN and dd(v4) >= dd(v3)
        out["adozione_proposta"] = bool(ok)
        out["verdetto"] = ("la v4 regge anche in avanti: proporre l'adozione (grande richiesta n.5, finestra della domenica)" if ok
                           else "la v4 non conferma in avanti: si resta sulla v3")
    return out


def _data(close: pd.DataFrame) -> dict:
    from quantlab import gervaq4 as G4
    return dict(close=close, stocks=[s for s in G4.STOCKS if s in close])


def update(close: pd.DataFrame | None = None, start: str | None = None) -> dict:
    """Registra i giorni nuovi dopo la data di partenza, fissata una volta sola (default: START_DEFAULT)."""
    from quantlab import gervaq4 as G4, data as QD
    if close is None:
        p = os.path.join(paths.VAR, "data", "gq4_close.pkl")
        if not os.path.exists(p):
            return dict(ok=False, motivo="mancano i dati: firm.py data")
        close = pd.read_pickle(p)
    start = db.runtime_get(START_KEY) or start
    if not db.runtime_get(START_KEY):
        start = start or START_DEFAULT
        db.runtime_set(START_KEY, start)
        events.publish("shadow.start", "ricerca", dict(da=start, varianti=list(VARIANTS)))
    fp = QD.fingerprint(close)
    added = 0
    rate = G4.short_rate(_data(close))
    known = dict(db.runtime_get(RF_KEY) or {})
    had_rows = bool(db.one("SELECT 1 x FROM shadow_returns LIMIT 1"))
    for name in VARIANTS:
        v = next(x for x in G4.VARIANTS if x.name == name)
        r = G4.run_variant(_data(close), v)
        fwd = r[r.index > pd.Timestamp(start)]
        for d, x in fwd.items():
            if not np.isfinite(x):
                continue
            cur = db.connect().execute(
                "INSERT OR IGNORE INTO shadow_returns(day,variant,ret,recorded_ts,data_fp) VALUES(?,?,?,?,?)",
                (str(d.date()), name, float(x), db.now_iso(), fp))
            added += cur.rowcount
            if cur.rowcount:
                known.setdefault(str(d.date()), float(rate.get(d, 0.0)))        # il tasso di un giorno si scrive una volta, come il rendimento
                if not db.runtime_get(FIX_KEY):
                    # se c'erano gia' righe, sono state scritte dal codice di prima (v4 con la cassa, v3 senza): da qui in poi no
                    db.runtime_set(FIX_KEY, str(d.date()) if had_rows else "dall'inizio")
    if added:
        db.runtime_set(RF_KEY, known)
    return {**summary(), "ok": True, "partenza": start, "nuovi": added}


def summary() -> dict:
    from quantlab import gervaq4 as G4
    rows = db.q("SELECT day, variant, ret FROM shadow_returns ORDER BY day")
    if not rows:
        return dict(giorni=0, verdetto="nessun giorno in avanti ancora")
    df = pd.DataFrame(rows).pivot(index="day", columns="variant", values="ret").dropna()
    out = dict(giorni=len(df), partenza=db.runtime_get(START_KEY))
    for name in VARIANTS:
        if name in df:
            x = df[name].values
            nav = np.cumprod(1 + x)
            sd = x.std(ddof=1) if len(x) > 1 else 0.0
            out[name] = dict(rendimento=float(nav[-1] - 1), sharpe=float(x.mean() / sd * math.sqrt(252)) if sd > 0 else None,
                             max_dd=float((nav / np.maximum.accumulate(nav) - 1).min()))
    if all(n in df for n in VARIANTS):
        rf_by_day = db.runtime_get(RF_KEY) or {}
        rf = np.array([float(rf_by_day.get(d, 0.0)) for d in df.index])
        out.update({k: v for k, v in decide(df["tutto"].values, df["v3_riferimento"].values, rf).items() if k != "giorni"})
        out["regola_sospesa"] = ADOZIONE_SOSPESA
        fix = db.runtime_get(FIX_KEY)
        if fix != "dall'inizio":
            old = len(df) if not fix else int((df.index < fix).sum())
            if old:
                out["nota"] = (f"{old} giorni sono stati scritti prima della correzione della tesoreria (v4 con la cassa remunerata, "
                               "v3 senza): non sono un confronto alla pari")
    else:
        out["verdetto"] = "manca una delle due varianti"
    return out
