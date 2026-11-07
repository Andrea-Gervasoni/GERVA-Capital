"""
Aspettative del fondo, scritte PRIMA e confrontate con la realta' man mano.

  * due ventagli registrati una volta e mai riscritti (tabella append-only, con impronta nel registro di controllo):
      - "modello": cosa si aspetta il modello, cioe' la storia del portafoglio ricampionata cosi' com'e';
      - "realistico": la stessa storia con il rendimento medio ridotto (sopravvivenza e sovradattamento) e i costi di
        esecuzione tolti: e' il caso su cui conviene ragionare.
  * il valore reale del conto si disegna sopra i ventagli e si dice in che percentile cade.
  * gli agenti (il Capo) scrivono ogni giorno una loro previsione a 1 settimana e a 1 mese, con probabilita'; alla
    scadenza il codice la confronta col conto e calcola il Brier score. Cosi' si vede quanto valgono le loro previsioni.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math

import numpy as np
import pandas as pd

from . import audit, charts, db, events, fundrisk
from . import settings as S

STEPS = list(range(0, 31)) + list(range(35, 253, 5)) + [252]
QS = ("5", "25", "50", "75", "95")


def _params() -> dict:
    return dict(haircut=float(S.get("expectations.haircut", 0.5)), costi_annui=float(S.get("expectations.costs_year", 0.015)))


def build(nav0: float, weights: dict | None = None, close: pd.DataFrame | None = None, **kw) -> dict:
    close = charts.load_close() if close is None else close
    pf = fundrisk.portfolio(**kw) if weights is None else dict(pesi=weights, lordo=sum(abs(v) for v in weights.values()), leva=0.0, fonti={})
    rets = fundrisk.returns_matrix(list(pf["pesi"]), close)
    bc = fundrisk.backcast(pf["pesi"], rets, close["^IRX"] if "^IRX" in close else None)
    rp = bc["serie"]
    if len(rp) < 252:
        raise ValueError("storia insufficiente per registrare le aspettative")
    par = _params()
    rp_real = rp - par["haircut"] * rp.mean() - par["costi_annui"] / fundrisk.TD
    kill = float(S.risk_limits()["firm"]["kill_drawdown"])
    mod = fundrisk.monte_carlo(rp, nav0, 1, steps=STEPS, kill_dd=kill)
    rea = fundrisk.monte_carlo(rp_real, nav0, 1, steps=STEPS, kill_dd=kill)
    return dict(pf=pf, par=par, modello=mod, realistico=rea, storia_dal=mod["storia_dal"], kill=kill)


def register(nav0: float | None = None, note: str = "", **kw) -> dict:
    """Scrive una nuova versione delle aspettative. Non modifica le precedenti."""
    if nav0 is None:
        nav0 = float((db.runtime_get("ibkr.live") or {}).get("nav") or (db.runtime_get("ibkr.challenge") or {}).get("nav_eur") or 0)
    if nav0 <= 0:
        raise ValueError("il valore del conto non e' ancora stato letto da IBKR")
    b = build(nav0, **kw)
    trim = lambda m: {q: m["ventaglio"][q] for q in QS} | dict(finale=m["finale"], p_perdita=m["p_perdita"], p_kill=m["p_kill"],
                                                                   p_guadagno_20=m["p_guadagno_20"], rendimento_mediano=m["rendimento_mediano"],
                                                                   dd_mediano=m["dd_mediano"])
    params = dict(b["par"], nota=note, lordo=b["pf"]["lordo"], leva=b["pf"]["leva"], storia_dal=b["storia_dal"], kill=b["kill"],
                  fonti=b["pf"].get("fonti", {}), pesi=dict(list(b["pf"]["pesi"].items())[:14]), passi=b["modello"]["passi"])
    now = db.now_iso()
    body = json.dumps(dict(ts=now, nav0=round(nav0, 2), params=params, modello=trim(b["modello"]), realistico=trim(b["realistico"])), sort_keys=True)
    h = hashlib.sha256(body.encode()).hexdigest()[:16]
    d = json.loads(body)
    db.ex("INSERT INTO expectations(ts,nav0,params,modello,realistico,hash) VALUES(?,?,?,?,?,?)",
          (now, d["nav0"], json.dumps(params), json.dumps(d["modello"]), json.dumps(d["realistico"]), h))
    rid = db.one("SELECT id FROM expectations ORDER BY id DESC LIMIT 1")["id"]
    audit.log("expectations", "expectation.registered", dict(id=rid, hash=h, nav0=d["nav0"], mediana_modello=d["modello"]["finale"]["50"],
                                                              mediana_realistica=d["realistico"]["finale"]["50"], leva=params["leva"]))
    events.publish("expectation.registered", "expectations", dict(id=rid, nav0=d["nav0"], hash=h))
    return dict(id=rid, hash=h)


def _dates(ts: str, steps: list[int]) -> list[str]:
    start = pd.Timestamp(ts[:10])
    days = pd.bdate_range(start, periods=max(steps) + 1)
    out = [str(days[s].date()) + "T22:00:00" for s in steps]
    out[0] = ts[:19]                                          # il primo punto e' il momento esatto della registrazione
    return out


def _percentile(value: float, curve: dict[str, float]) -> float:
    pts = sorted((curve[q], int(q)) for q in QS)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    if xs[-1] - xs[0] <= 1e-9 * max(abs(xs[0]), 1.0):                      # ventaglio ancora chiuso (partenza, weekend): al centro
        return 50.0 if abs(value - xs[0]) <= 1e-6 * max(abs(xs[0]), 1.0) else (0.0 if value < xs[0] else 100.0)
    if value <= xs[0]:
        return float(ys[0] * max(value, 0) / xs[0]) if xs[0] > 0 else 0.0     # sotto il 5°: indicativo
    if value >= xs[-1]:
        return float(min(100.0, ys[-1] + (100 - ys[-1]) * (value - xs[-1]) / max(xs[-1] * 0.1, 1.0)))
    return float(np.interp(value, xs, ys))


def _at(fan: dict, steps: list[int], t: float) -> dict[str, float]:
    return {q: float(np.interp(t, steps, fan[q])) for q in QS}


def latest() -> dict | None:
    r = db.one("SELECT * FROM expectations ORDER BY id DESC LIMIT 1")
    if not r:
        return None
    params = json.loads(r["params"])
    return dict(id=r["id"], ts=r["ts"], nav0=r["nav0"], hash=r["hash"], params=params, modello=json.loads(r["modello"]),
                realistico=json.loads(r["realistico"]), versioni=db.one("SELECT COUNT(*) n FROM expectations")["n"])


def realized(exp: dict, max_points: int = 400) -> list[dict]:
    pts = [(r["ts"][:19], float(r["nav"])) for r in db.q("SELECT ts, nav FROM nav_ticks WHERE ts>=? ORDER BY ts", (exp["ts"],))]
    live = db.runtime_get("ibkr.live") or {}
    if live.get("nav") and (not pts or live["ts"][:19] > pts[-1][0]):
        pts.append((live["ts"][:19], float(live["nav"])))
    if not pts or pts[0][0] > exp["ts"][:19]:
        pts.insert(0, (exp["ts"][:19], float(exp["nav0"])))
    if len(pts) > max_points:
        k = math.ceil(len(pts) / max_points)
        pts = pts[::k] + ([pts[-1]] if pts[-1] not in pts[::k] else [])
    return [dict(t=t, v=round(v, 2)) for t, v in pts]


def overview() -> dict:
    exp = latest()
    if not exp:
        return dict(registrata=None, nota="Le aspettative non sono ancora state scritte: lo fa il battito appena il conto e' letto da IBKR "
                                         "e GERVA-Q ha scritto i suoi pesi, oppure a mano con firm.py aspettative.")
    steps = exp["params"]["passi"]
    dates = _dates(exp["ts"], steps)
    real = realized(exp)
    last_t, last_v = real[-1]["t"], real[-1]["v"]
    elapsed = float(np.busday_count(exp["ts"][:10], last_t[:10])) + (
        (pd.Timestamp(last_t) - pd.Timestamp(last_t[:10])).total_seconds() / 86400.0 if np.is_busday(last_t[:10]) else 0.0)
    elapsed = max(min(elapsed, max(steps)), 0.0)
    stato = {}
    for k in ("modello", "realistico"):
        cur = _at(exp[k], steps, elapsed)
        pc = _percentile(last_v, cur)
        stato[k] = dict(percentile=round(pc, 0), atteso_mediano=round(cur["50"], 0), scarto_dalla_mediana=round(last_v / cur["50"] - 1, 4),
                        lettura="sopra il 95° percentile" if pc >= 95 else "sopra il 75°" if pc >= 75 else "nella fascia centrale" if pc >= 25
                        else "sotto il 25°" if pc >= 5 else "sotto il 5°: peggio del 95% dei casi")
    ex_par = exp["params"]
    return dict(registrata=exp["ts"], id=exp["id"], hash=exp["hash"], versioni=exp["versioni"], nav0=exp["nav0"], parametri=ex_par,
                date=dates, modello={q: exp["modello"][q] for q in QS}, realistico={q: exp["realistico"][q] for q in QS},
                finale_modello=exp["modello"]["finale"], finale_realistico=exp["realistico"]["finale"],
                p_perdita=dict(modello=exp["modello"]["p_perdita"], realistico=exp["realistico"]["p_perdita"]),
                realizzato=real, giorni_trascorsi=round(elapsed, 2), rendimento_dal_via=round(last_v / exp["nav0"] - 1, 4), stato=stato,
                previsioni_agenti=db.q("SELECT * FROM outlooks ORDER BY id DESC LIMIT 12"), brier=brier_summary())


# ---------------------------------------------------------------------------------------------- previsioni degli agenti
OUTLOOK_HORIZONS = (7, 30)


def brier_summary() -> dict:
    r = db.one("SELECT COUNT(*) n, AVG(brier) b FROM outlooks WHERE outcome IS NOT NULL")
    return dict(risolte=r["n"], brier=None if r["b"] is None else round(r["b"], 3), riferimento=0.25)


def _nav_now() -> float:
    return float((db.runtime_get("ibkr.live") or {}).get("nav") or (db.runtime_get("ibkr.challenge") or {}).get("nav_eur") or 0)


def validate_outlook(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        h = int(it.get("orizzonte_giorni", 0))
        p, m = float(it.get("p_sopra", -1)), float(it.get("mediana_pct", 9))
        if h in OUTLOOK_HORIZONS and 0.02 <= p <= 0.98 and -0.5 <= m <= 0.5:
            out.append(dict(orizzonte=h, p=p, m=m))
    return out


def outlook_cycle(today: dt.date | None = None) -> dict:
    """Il Capo scrive la sua previsione sul conto a 1 settimana e a 1 mese, con probabilita'. Parte dal Monte Carlo
    realistico e dal regime di mercato: puo' discostarsene solo con un motivo."""
    from . import workflows as W
    from llm import runtime
    today = today or dt.date.today()
    nav0 = _nav_now()
    exp = latest()
    if nav0 <= 0 or not exp:
        return dict(nota="mancano il valore del conto o le aspettative registrate")
    if db.one("SELECT id FROM outlooks WHERE substr(ts,1,10)=? LIMIT 1", (today.isoformat(),)):
        return dict(nota="previsione di oggi gia' scritta")
    base = {}
    for h in OUTLOOK_HORIZONS:
        t = float(h) * 5 / 7                                                  # giorni di borsa
        cur = _at(exp["realistico"], exp["params"]["passi"], t)
        base[f"{h}_giorni"] = dict(mediana_pct=round(cur["50"] / exp["nav0"] - 1, 4), p5=round(cur["5"] / exp["nav0"] - 1, 4), p95=round(cur["95"] / exp["nav0"] - 1, 4))
    r = runtime.call("capo", "Scrivi la tua previsione sul valore del conto a 7 e a 30 giorni: probabilita' che sia SOPRA quello di oggi e "
                             "rendimento mediano atteso. Parti dal caso realistico (Monte Carlo) e dal regime di mercato; se te ne discosti, "
                             "spiega perche'. Le tue previsioni verranno confrontate col conto e valutate con il Brier score.",
                     data=dict(caso_realistico=base, regime=charts.regime(), libro=W.libro_posizioni(), rischio={k: v for k, v in __import__("firm.risk", fromlist=["x"]).snapshot().items() if k != "nav"}),
                     schema=W.OUTLOOK, purpose="outlook", status_label="pensa")
    if not r["ok"]:
        return dict(nota=f"previsione non scritta: {r['motivo']}")
    good = validate_outlook(r["output"]["previsioni"])
    for g in good:
        db.ex("INSERT INTO outlooks(ts,agent_id,horizon_days,deadline,nav0,p_up,median_pct,motivo) VALUES(?,?,?,?,?,?,?,?)",
              (db.now_iso(), "capo", g["orizzonte"], (today + dt.timedelta(days=g["orizzonte"])).isoformat(), nav0, g["p"], g["m"],
               str(r["output"].get("motivo", ""))[:400]))
    events.publish("outlook.new", "capo", dict(previsioni=good))
    return dict(ok=True, scritte=len(good))


def resolve_outlooks(now: dt.datetime | None = None) -> int:
    now = now or dt.datetime.now(dt.timezone.utc)
    n = 0
    for o in db.q("SELECT * FROM outlooks WHERE outcome IS NULL AND deadline<=?", (now.date().isoformat(),)):
        row = db.one("SELECT nav FROM nav_ticks WHERE ts>=? ORDER BY ts LIMIT 1", (o["deadline"] + "T00:00:00",)) or \
              db.one("SELECT nav FROM nav_ticks ORDER BY ts DESC LIMIT 1")
        if not row or o["nav0"] <= 0:
            continue
        real = row["nav"] / o["nav0"] - 1
        out = 1 if real > 0 else 0
        db.ex("UPDATE outlooks SET outcome=?, realized_pct=?, resolved_ts=?, brier=? WHERE id=?",
              (out, round(real, 5), db.now_iso(), (o["p_up"] - out) ** 2, o["id"]))
        n += 1
    return n
