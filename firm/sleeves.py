"""
Portafoglio di strategie: quali parti del fondo guadagnano davvero, e quanto sono diverse tra loro.

Ogni "sleeve" e' una parte del fondo con la sua serie di rendimenti giornalieri:
  * motore (GERVA-Q sul conto paper di IBKR): dal valore del conto, ogni giorno;
  * segnali eseguiti / segnali seguiti non eseguiti: dal risultato dei segnali chiusi (R x rischio per segnale);
  * banco libero: dalle operazioni chiuse sul conto Alpaca;
  * futures simulato: dalle posizioni virtuali chiuse;
  * strategie dai paper (crypto TSMOM, SPY intraday): dal backtest (storia lunga, ma e' un backtest).

Regole di onesta' (stesse di un fondo vero):
  * ogni sleeve dice da dove vengono i numeri: reale, paper, simulato, backtest. I backtest non si mescolano con il vivo;
  * Sharpe e Calmar si calcolano solo con abbastanza giorni (20: "dati insufficienti", 60: "pochi dati", oltre: ok);
  * la correlazione si calcola solo sui giorni in comune (almeno 20); altrimenti si dice che non si puo'.
"""
from __future__ import annotations

import datetime as dt
import json
import math

import numpy as np
import pandas as pd

from . import db
from . import settings as S

MIN_OBS, OK_OBS = 20, 60
SHORT = {"Motore GERVA-Q (conto paper IBKR)": "Motore", "Segnali eseguiti (Alpaca)": "Segn. eseguiti", "Segnali seguiti, non eseguiti": "Segn. seguiti",
         "Banco libero (Alpaca)": "Banco libero", "Futures simulato (leva scelta dagli agenti)": "Futures sim.", "Crypto TSMOM": "Crypto TSMOM", "SPY intraday momentum": "SPY intraday"}
LIVE_GROUP, BT_GROUP = "dal vivo, paper e simulato", "backtest (storia lunga, scelti sui dati)"


def _days(idx_from, idx_to) -> pd.DatetimeIndex:
    return pd.bdate_range(idx_from, idx_to)


def _event_series(events: list[tuple[str, float]], base: float) -> pd.Series | None:
    """Eventi (giorno, guadagno in valuta) -> rendimento giornaliero su `base`; i giorni senza eventi valgono 0."""
    if not events or base <= 0:
        return None
    s = pd.Series({pd.Timestamp(d[:10]): 0.0 for d, _ in events})
    for d, v in events:
        s[pd.Timestamp(d[:10])] += v / base
    s = s.sort_index()
    return s.reindex(_days(s.index[0], max(s.index[-1], pd.Timestamp(dt.date.today())))).fillna(0.0)


def metrics(r: pd.Series | None, periods: int = 252) -> dict:
    """Metriche di una serie di rendimenti giornalieri. None dove i dati non bastano."""
    if r is None or len(r.dropna()) == 0:
        return dict(giorni=0, stato="nessun dato")
    d = r.dropna()
    n = len(d)
    eq = (1 + d).cumprod()
    dd = float((eq / eq.cummax() - 1).min())
    sd = float(d.std()) if n > 1 else 0.0
    out = dict(giorni=n, dal=str(d.index[0])[:10], al=str(d.index[-1])[:10], totale=round(float(eq.iloc[-1] - 1), 4), calo_massimo=round(dd, 4),
               giorni_vincenti=round(float((d > 0).mean()), 3), miglior_giorno=round(float(d.max()), 4), peggior_giorno=round(float(d.min()), 4), media_giorno=round(float(d.mean()), 5),
               stato="dati insufficienti" if n < MIN_OBS else "pochi dati" if n < OK_OBS else "ok")
    gains, losses = float(d[d > 0].sum()), float(-d[d < 0].sum())
    out["profit_factor"] = round(gains / losses, 2) if losses > 0 and n >= MIN_OBS else None
    out["sharpe"] = round(float(d.mean() / sd * math.sqrt(periods)), 2) if sd > 0 and n >= MIN_OBS else None
    ann = float(eq.iloc[-1] ** (periods / n) - 1) if n >= OK_OBS and eq.iloc[-1] > 0 else None
    out["annuo"] = round(ann, 4) if ann is not None else None
    out["calmar"] = round(ann / abs(dd), 2) if ann is not None and dd < 0 else None
    return out


def correlation(series: dict[str, pd.Series]) -> dict:
    """Correlazione a coppie sui giorni IN COMUNE (almeno MIN_OBS); None se non si puo'."""
    names = [k for k, s in series.items() if s is not None and len(s.dropna()) >= MIN_OBS]
    mat = [[None] * len(names) for _ in names]
    for i, a in enumerate(names):
        for j, b in enumerate(names):
            if i == j:
                mat[i][j] = 1.0
                continue
            both = pd.concat([series[a], series[b]], axis=1, join="inner").dropna()
            if len(both) >= MIN_OBS and both.iloc[:, 0].std() > 0 and both.iloc[:, 1].std() > 0:
                mat[i][j] = round(float(both.corr().iloc[0, 1]), 2)
    return dict(simboli=names, matrice=mat)


def combined(series: dict[str, pd.Series]) -> dict | None:
    """Portafoglio a rischio uguale (peso ~ 1/volatilita') sulle sleeve con abbastanza giorni in comune, e quanto vale la diversificazione."""
    names = [k for k, s in series.items() if s is not None and len(s.dropna()) >= MIN_OBS]
    if len(names) < 2:
        return None
    df = pd.concat([series[k] for k in names], axis=1, join="inner", keys=names).dropna()
    if len(df) < MIN_OBS:
        return None
    vol = df.std().replace(0, np.nan)
    w = (1 / vol).fillna(0)
    w = w / w.sum()
    port = (df * w).sum(axis=1)
    c = df.corr().values
    n = len(names)
    rho = float((c.sum() - n) / (n * (n - 1))) if n > 1 else 0.0
    eff = n / (1 + (n - 1) * max(rho, 0.0))
    score = max(0.0, min(100.0, 100 * (1 - max(rho, 0.0))))
    m = metrics(port)
    m.update(n_sleeve=n, correlazione_media=round(rho, 2), n_effettivo=round(eff, 1), diversificazione=round(score), voto="A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D",
             pesi={k: round(float(w[k]), 3) for k in names}, sharpe_medio_sleeve=round(float(np.mean([metrics(df[k])["sharpe"] or 0 for k in names])), 2))
    return m


# ----------------------------------------------------------------------------- le serie
GLITCH = 0.20          # un fondo che muove piu' del 20% in un giorno e' quasi sempre una lettura sbagliata del conto


def engine_series() -> tuple[pd.Series | None, int]:
    """Rendimenti giornalieri del conto IBKR, senza i giorni anomali (letture sbagliate). Ritorna (serie, quanti giorni scartati)."""
    rows = db.q("SELECT day, nav FROM nav_marks WHERE pod='pod_zero' AND nav>0 ORDER BY day")
    if len(rows) < 2:
        return None, 0
    r = pd.Series({pd.Timestamp(x["day"]): float(x["nav"]) for x in rows}).sort_index().pct_change().dropna()
    bad = r.abs() > GLITCH
    return r[~bad], int(bad.sum())


def signals_series(executed: bool) -> pd.Series | None:
    risk = float(S.get("signals.risk_frac", 0.005))
    ev = [(r["chiuso_ts"], float(r["r_multiple"]) * risk) for r in db.q("SELECT chiuso_ts, r_multiple, peso FROM signals WHERE stato='chiuso' AND r_multiple IS NOT NULL AND chiuso_ts IS NOT NULL")
          if (float(r["peso"] or 0) > 0) == executed]
    return _event_series(ev, 1.0)


def free_desk_series() -> pd.Series | None:
    from . import blotter
    base = float(db.runtime_get("alpaca.start_equity") or 100000.0)
    fx = float(db.runtime_get("fx.usd_eur") or 0.9)
    ev = [(t["chiusa_il"], t["realizzato_eur"]) for t in blotter.trades("alpaca", "chiusa") if (t.get("origine") or {}).get("kind") == "free" and t.get("chiusa_il")]
    return _event_series(ev, base * fx)


def futures_series() -> pd.Series | None:
    try:
        from . import futures_sim
        futures_sim._ensure()
        ev = [(r["chiuso_ts"], float(r["pnl_usd"])) for r in db.q("SELECT chiuso_ts, pnl_usd FROM fut_positions WHERE stato='chiusa' AND chiuso_ts IS NOT NULL")]
        return _event_series(ev, futures_sim.equity0())
    except Exception:
        return None


def backtest_series(name: str) -> pd.Series | None:
    got = db.runtime_get(f"algo.{name}.serie")
    if not got:
        return None
    return pd.Series(got["v"], index=pd.to_datetime(got["d"])).sort_index()


def overview() -> dict:
    eng, scartati = engine_series()
    live = {
        "Motore GERVA-Q (conto paper IBKR)": ("paper IBKR", eng),
        "Segnali eseguiti (Alpaca)": ("paper Alpaca", signals_series(True)),
        "Segnali seguiti, non eseguiti": ("misura", signals_series(False)),
        "Banco libero (Alpaca)": ("paper Alpaca", free_desk_series()),
        "Futures simulato (leva scelta dagli agenti)": ("simulato", futures_series()),
    }
    bt = {"Crypto TSMOM": ("backtest", backtest_series("crypto_tsmom")), "SPY intraday momentum": ("backtest", backtest_series("spy_intraday_momentum"))}
    groups = []
    for name, note, src in ((LIVE_GROUP, "Numeri veri o simulati dall'inizio del fondo: pochi giorni, quindi quasi tutto e' 'dati insufficienti'. E' giusto cosi': 4 giorni non dicono niente.", live),
                            (BT_GROUP, "Storia lunga ma costruita sui dati: le strategie sono state scelte guardando il passato, quindi i numeri sono ottimisti. Non si confrontano con il vivo.", bt)):
        series = {k: v[1] for k, v in src.items()}
        rows = []
        for k, (origin, s) in src.items():
            m = metrics(s)
            m.update(nome=k, origine=origin, breve=SHORT.get(k, k[:12]), scartati=scartati if k.startswith("Motore") else 0)
            rows.append(m)
        cor = correlation(series)
        cor["simboli"] = [SHORT.get(k, k[:12]) for k in cor["simboli"]]                               # nomi corti per la mappa di calore
        groups.append(dict(nome=name, nota=note, sleeve=rows, correlazioni=cor, combinato=combined(series)))
    return dict(gruppi=groups, regole=dict(minimo=MIN_OBS, affidabile=OK_OBS))
