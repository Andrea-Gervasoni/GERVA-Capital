"""
Il dossier di ogni operazione: le prove al momento della decisione, salvate PRIMA di sapere come va a finire.

  * indicatori del titolo quel giorno (prezzo, medie a 20/50/200, RSI, volatilita', Bollinger, rendimenti a 1/3/12 mesi, trend, drawdown);
  * regime di mercato (S&P 500 rispetto alla media a 200 giorni, VIX e suo percentile);
  * previsione statistica: com'e' andato il titolo nei giorni successivi quando era nella stessa situazione di trend (probabilita' di salire,
    mediana, intervallo al 90%), e senza condizione; dice anche su quanti casi si basa;
  * cosa diceva il modello (peso nel modello di GERVA-Q, se c'e');
  * la sera, la revisione: un capo desk scrive gli argomenti A FAVORE e il CRO quelli CONTRO, con gli indicatori usati e una probabilita'.
Nessun numero viene da un agente se non e' stato calcolato prima dal codice.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os

import numpy as np
import pandas as pd

from . import charts, db, paths
from . import settings as S

_CACHE: dict = {}


def _close():
    f = os.path.join(paths.VAR, "data", "gq4_close.pkl")
    m = os.path.getmtime(f) if os.path.exists(f) else 0
    if _CACHE.get("m") != m:
        _CACHE.update(m=m, df=charts.load_close())
    return _CACHE.get("df")


def _trend_series(c: pd.Series) -> pd.Series:
    e50, e200 = c.ewm(span=50, adjust=False).mean(), c.ewm(span=200, adjust=False).mean()
    return pd.Series(np.where((c > e50) & (e50 > e200), "su", np.where((c < e50) & (e50 < e200), "giu", "misto")), index=c.index)


def forecast(sym: str, horizon: int = 5, close: pd.DataFrame | None = None) -> dict:
    close = _close() if close is None else close
    src = charts.ALIAS.get(sym, sym)
    if close is None or src not in close:
        return dict(ok=False, motivo="nessuna storia di prezzi per questo titolo")
    c = close[src].dropna()
    if len(c) < 300:
        return dict(ok=False, motivo="storia troppo corta")
    fwd = c.shift(-horizon) / c - 1
    tr = _trend_series(c)
    now = tr.iloc[-1]

    def summ(x: pd.Series) -> dict:
        x = x.dropna()
        return dict(casi=int(len(x)), p_sale=round(float((x > 0).mean()), 3), mediana=round(float(x.median()), 4),
                    p5=round(float(x.quantile(0.05)), 4), p95=round(float(x.quantile(0.95)), 4))
    return dict(ok=True, orizzonte_giorni=horizon, trend_oggi=now, condizionata=summ(fwd[tr == now]), tutte=summ(fwd),
                nota=f"rendimenti a {horizon} giorni nella storia del titolo, quando il trend era '{now}' (condizionata) e sempre (tutte)")


def build(sym: str, origine: dict | None = None, horizon: int = 5) -> dict:
    close = _close()
    out = dict(simbolo=sym, ts=db.now_iso(), origine=origine or {})
    try:
        out["indicatori"] = charts.indicators(sym, 120, close)["riepilogo"] if close is not None else None
    except Exception:
        out["indicatori"] = None
    try:
        out["regime"] = charts.regime(close)
    except Exception:
        out["regime"] = None
    out["previsione"] = forecast(sym, horizon, close)
    try:
        from . import fundrisk, pod_zero
        w = {}
        w.update(fundrisk._scaled(pod_zero.equity_model()) or {})
        w.update(fundrisk._scaled(pod_zero.crypto_model()) or {})
        if sym in w:
            out["modello"] = dict(peso_nel_conto=round(float(w[sym]), 4), nota="peso deciso dal modello di GERVA-Q (trend e reversal sui prezzi di chiusura), gia' moltiplicato per la scala di leva")
    except Exception:
        pass
    return out


def save(ext_id: str, sym: str, data: dict) -> None:
    db.ex("INSERT OR IGNORE INTO dossiers(ext_id,ts,symbol,data) VALUES(?,?,?,?)", (ext_id, db.now_iso(), sym, json.dumps(data, ensure_ascii=False, default=str)))


def get(ext_id: str) -> dict | None:
    r = db.one("SELECT data FROM dossiers WHERE ext_id=?", (ext_id,))
    return json.loads(r["data"]) if r else None


def _update(ext_id: str, data: dict) -> None:
    db.ex("UPDATE dossiers SET data=? WHERE ext_id=?", (json.dumps(data, ensure_ascii=False, default=str), ext_id))


def review_daily(runtime=None, limit: int = 12) -> dict:
    """La sera: argomenti a favore (capo desk) e contro (CRO) per le operazioni nuove, con indicatori e probabilita'. Due chiamate in tutto."""
    if runtime is None:
        from llm import runtime
    from . import workflows as W
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    todo = []
    for r in db.q("SELECT ext_id, symbol, data FROM dossiers WHERE ts>=? ORDER BY id DESC LIMIT 60", (since,)):
        d = json.loads(r["data"])
        if not d.get("revisione"):
            todo.append((r["ext_id"], d))
    todo = todo[:limit]
    if not todo:
        return dict(nota="nessuna operazione nuova da rivedere")
    items = [dict(chiave=e, simbolo=d["simbolo"], lato=(db.one("SELECT side FROM fills_all WHERE ext_id=?", (e,)) or {}).get("side"), origine=(d.get("origine") or {}).get("kind"),
                  indicatori=d.get("indicatori"), previsione=d.get("previsione"), modello=d.get("modello")) for e, d in todo]
    reg = todo[0][1].get("regime")
    out = {}
    for role, agent, task in (("pro", "pod_trend", "Scrivi per ogni operazione gli argomenti A FAVORE, usando SOLO gli indicatori e la previsione forniti (cita i numeri)."),
                              ("contro", "cro", "Scrivi per ogni operazione gli argomenti CONTRO e i rischi, usando SOLO gli indicatori e la previsione forniti (cita i numeri).")):
        r = runtime.call(agent, task + " Indica gli indicatori usati e la tua probabilita' che l'operazione chiuda in guadagno. Usa la stessa chiave.",
                         data=dict(operazioni=items, regime=reg), schema=W.TRADE_REVIEW, purpose="revisione-trade", status_label="rivede")
        if r["ok"]:
            for v in r["output"].get("valutazioni", []):
                out.setdefault(v.get("chiave"), {}).setdefault(role, []).append(dict(agente=agent, testo=str(v.get("argomento", ""))[:900],
                                                                                    indicatori=[str(x)[:60] for x in (v.get("indicatori_usati") or [])][:8],
                                                                                    probabilita=v.get("probabilita_guadagno")))
    n = 0
    for e, d in todo:
        if e in out:
            d["revisione"] = out[e]; _update(e, d); n += 1
    return dict(riviste=n)


def chart(sym: str, days: int = 160) -> dict | None:
    close = _close()
    try:
        x = charts.indicators(sym, days, close)
        return dict(date=x["date"], close=x["close"], ema50=x["ema50"], ema200=x["ema200"], bb_su=x["bb_su"], bb_giu=x["bb_giu"])
    except Exception:
        return None
