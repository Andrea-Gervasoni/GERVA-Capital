"""
Budget Governor — codice, non un agente (brief <budget>, DECISIONS D9).

Prima di ogni chiamata LLM: authorize() stima il costo e decide
  * NEGATO se si supera un tetto (totale, giornaliero, di reparto, di agente) o se la
    societa' e' in sciopero (manuale da Andrea o automatico a budget totale esaurito);
  * SCALATO verso un modello piu' economico se la spesa di oggi supera downgrade_at del tetto;
  * CONCESSO altrimenti.
Dopo la chiamata: record() scrive il costo reale (token dall'API) in llm_calls e nell'audit.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, asdict

import yaml

from . import db, audit, events, paths
from . import settings as S

MODELS_FILE = os.path.join(paths.CONFIG, "models.yaml")


def models_cfg() -> dict:
    return yaml.safe_load(open(MODELS_FILE))


def price(model: str) -> dict:
    p = models_cfg()["prices_usd_per_mtok"]
    if model in p:
        return p[model]
    for k in p:                                   # "kimi-k2..." -> "kimi"
        if model.startswith(k):
            return p[k]
    raise KeyError(f"prezzo sconosciuto per {model}: aggiungilo a config/models.yaml")


def cost_usd(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0,
             cache_write: int = 0) -> float:
    p = price(model)
    return (input_tokens * p["input"] + output_tokens * p["output"]
            + cache_read * p["cache_read"] + cache_write * p["cache_write"]) / 1e6


def to_eur(usd: float) -> float:
    return usd * float(S.get("budget.usd_eur", 0.9))


def downgrade(model: str) -> str:
    tiers = models_cfg()["tiers"]
    if model in tiers and tiers.index(model) > 0:
        return tiers[tiers.index(model) - 1]
    return model


@dataclass
class Decision:
    allowed: bool
    model: str
    reason: str
    est_cost_eur: float

    def to_dict(self):
        return asdict(self)


def spent(day: str | None = None, agent_id: str | None = None, dept: str | None = None) -> float:
    sql, args = "SELECT COALESCE(SUM(cost_eur),0) AS s FROM llm_calls WHERE 1=1", []
    if day:
        sql += " AND day=?"
        args.append(day)
    if agent_id:
        sql += " AND agent_id=?"
        args.append(agent_id)
    if dept:
        sql += " AND dept=?"
        args.append(dept)
    return float(db.one(sql, tuple(args))["s"])


def on_strike() -> tuple[bool, str]:
    if S.get("firm.strike", False):
        return True, "sciopero deciso da Andrea"
    auto = db.runtime_get("budget.auto_strike")
    if auto:
        return True, auto
    return False, ""


def authorize(agent_id: str, dept: str, model: str, est_input_tokens: int, est_output_tokens: int,
              agent_daily_cap_eur: float | None = None) -> Decision:
    strike, why = on_strike()
    if strike:
        return Decision(False, model, f"sciopero: {why}", 0.0)
    today = db.today()
    daily_cap = float(S.get("budget.daily_eur"))
    total_cap = float(S.get("budget.total_eur"))
    dept_caps = S.get("budget.per_dept_daily_eur_map") or {}
    spent_today, spent_total = spent(today), spent()
    # scala verso il basso vicino al tetto giornaliero
    chosen = model
    if spent_today >= float(S.get("budget.downgrade_at")) * daily_cap:
        chosen = downgrade(model)
    est = to_eur(cost_usd(chosen, est_input_tokens, est_output_tokens))
    checks = [
        (spent_total + est > total_cap, f"tetto totale {total_cap:.2f} EUR"),
        (spent_today + est > daily_cap, f"tetto giornaliero {daily_cap:.2f} EUR"),
        (dept in dept_caps and spent(today, dept=dept) + est > float(dept_caps[dept]),
         f"tetto del reparto {dept}"),
        (agent_daily_cap_eur is not None and spent(today, agent_id=agent_id) + est > agent_daily_cap_eur,
         f"tetto dell'agente {agent_id}"),
    ]
    for fail, why in checks:
        if fail:
            if "totale" in why:
                db.runtime_set("budget.auto_strike", f"budget totale esaurito ({total_cap:.2f} EUR)")
                events.publish("budget.strike", "budget_governor", dict(motivo=why))
            return Decision(False, chosen, why, est)
    reason = "concesso" if chosen == model else f"scalato a {chosen} (spesa di oggi oltre la soglia)"
    return Decision(True, chosen, reason, est)


def record(agent_id: str, dept: str, provider: str, model: str, input_tokens: int, output_tokens: int,
           cache_read: int = 0, cache_write: int = 0, ok: bool = True, purpose: str = "") -> float:
    usd = cost_usd(model, input_tokens, output_tokens, cache_read, cache_write)
    eur = to_eur(usd)
    db.ex("INSERT INTO llm_calls(ts,day,agent_id,dept,provider,model,input_tokens,output_tokens,"
          "cache_read,cache_write,cost_usd,cost_eur,ok,purpose) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
          (db.now_iso(), db.today(), agent_id, dept, provider, model, input_tokens, output_tokens,
           cache_read, cache_write, usd, eur, int(ok), purpose))
    audit.log(agent_id, "llm.call", dict(provider=provider, purpose=purpose, input=input_tokens,
                                         output=output_tokens, cache_read=cache_read, ok=ok),
              model=model, cost_eur=eur)
    return eur


def status() -> dict:
    today = db.today()
    total_cap = float(S.get("budget.total_eur"))
    daily_cap = float(S.get("budget.daily_eur"))
    spent_total, spent_today = spent(), spent(today)
    rows = db.q("SELECT day, SUM(cost_eur) s FROM llm_calls GROUP BY day ORDER BY day DESC LIMIT 7")
    pace = sum(r["s"] for r in rows) / len(rows) if rows else 0.0
    left = max(total_cap - spent_total, 0.0)
    days_left = left / pace if pace > 0 else math.inf
    by_dept = {r["dept"]: r["s"] for r in db.q(
        "SELECT dept, SUM(cost_eur) s FROM llm_calls WHERE day=? GROUP BY dept", (today,))}
    by_agent = {r["agent_id"]: r["s"] for r in db.q(
        "SELECT agent_id, SUM(cost_eur) s FROM llm_calls WHERE day=? GROUP BY agent_id", (today,))}
    strike, why = on_strike()
    return dict(spent_today=spent_today, spent_total=spent_total, daily_cap=daily_cap,
                total_cap=total_cap, pace_eur_day=pace, days_left=days_left,
                by_dept=by_dept, by_agent=by_agent, strike=strike, strike_reason=why,
                calls_today=db.one("SELECT COUNT(*) n FROM llm_calls WHERE day=?", (today,))["n"])


def runway_check() -> dict | None:
    """Se al ritmo attuale il budget finisce entro N giorni: grande richiesta n.3 ad Andrea."""
    st = status()
    thr = float(S.get("budget.alert_days_left"))
    if st["days_left"] < thr:
        from . import mailbox
        return mailbox.big_request(
            category=3,
            title=f"Al ritmo attuale il budget finisce tra {st['days_left']:.1f} giorni",
            why=(f"Spesa media {st['pace_eur_day']:.3f} EUR/giorno, residuo "
                 f"{st['total_cap'] - st['spent_total']:.2f} EUR su {st['total_cap']:.2f}."),
            options=["Alzare il tetto totale dalle Impostazioni",
                     "Lasciare il tetto: la societa' rallenta e poi va in sciopero",
                     "Ridurre il tetto giornaliero per allungare l'autonomia"],
            recommendation="Ridurre il tetto giornaliero a 0,40 EUR finche' non si vede il valore degli agenti",
            safe_default="Nessun cambio: al tetto la societa' va in sciopero e il codice deterministico continua",
            dedup_key=f"budget-runway-{db.today()}")
    return None
