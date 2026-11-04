"""
Battito deterministico (brief <budget>: societa' a eventi, non a ciclo continuo).

A ogni battito il CODICE controlla le condizioni e sveglia solo gli agenti necessari:
  sempre      motore di rischio, regole di drawdown dei pod, controllo del budget, catena di hash (1/giorno)
  comandi     se Andrea ha scritto al Capo -> delega
  notizie     raccolta RSS ogni battito; Redazione se >= 5 notizie nuove o alle 07 UTC
  rischio     CRO se gli allarmi cambiano o alle 20 UTC
  ricerca     un ciclo il martedi' e il giovedi'
  pod         venerdi' sera
  domenica    Comitato, ciclo talent, riallocazione (prima domenica del mese)
In sciopero gli agenti non vengono svegliati; il codice deterministico continua.
"""
from __future__ import annotations

import datetime as dt
import re

from . import db, events, risk, pods, budget, audit, gateway, news_feed, workflows, economy, compensation, meetings, reports


def _once(key: str) -> bool:
    """True la prima volta che `key` viene chiesto (per giorno/settimana)."""
    if db.runtime_get(f"once:{key}"):
        return False
    db.runtime_set(f"once:{key}", db.now_iso())
    return True


def beat(now: dt.datetime | None = None, use_agents: bool = True) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    day = now.strftime("%Y-%m-%d")
    woke, notes = [], []
    # ---- codice deterministico, sempre
    snap = risk.snapshot()
    acts = pods.apply_drawdown_rules()
    if acts:
        notes.append(f"regole drawdown: {acts}")
    budget.runway_check()
    if _once(f"audit:{day}"):
        v = audit.verify()
        if not v["ok"]:
            events.publish("risk.alert", "auditor", dict(cosa=f"catena di hash rotta alla voce {v['prima_rottura']}",
                                                         gravita=5))
    nf = news_feed.fetch_all()
    if nf["errori"] and not nf["nuove"]:
        notes.append("notizie: rete non disponibile o feed in errore")
    if now.hour >= 21 and _once(f"mark:{day}"):
        gateway.mark_day(day)
        reports.daily(day)                               # report della sera con le correzioni proposte
    if _once(f"vest:{day}"):
        compensation.vest(day)                           # maturano i bonus differiti scaduti
        meetings.resolve_due(day)                        # i fatti decidono chi aveva ragione nelle riunioni
    strike, why = budget.on_strike()
    if strike or not use_agents:
        events.publish("firm.heartbeat", "sistema", dict(sciopero=strike, motivo=why, semaforo=snap["semaforo"]),
                       audit_it=False)
        return dict(svegliati=[], note=notes + ([f"sciopero: {why}"] if strike else []), semaforo=snap["semaforo"])
    # ---- agenti, solo quando servono
    for c in db.q("SELECT id FROM commands WHERE status='ricevuto' ORDER BY id"):
        workflows.handle_command(c["id"])
        woke.append("capo")
    new_news = db.one("SELECT COUNT(*) n FROM news WHERE status='nuova'")["n"]
    if new_news >= 5 or (now.hour == 7 and new_news and _once(f"news:{day}")):
        workflows.news_cycle()
        woke += ["news_analyst", "fact_checker", "head_intel"]
    for a in snap["allarmi"]:                            # un pod vicino al taglio: riunione di rischio
        m = re.match(r"pod (\w+) vicino al taglio", a["cosa"])
        if m and _once(f"riskmeet:{m.group(1)}:{day}"):
            meetings.risk_meeting(m.group(1), a["cosa"])
            woke += ["cro", "capo"]
    alerts_sig = str(sorted(a["cosa"] for a in snap["allarmi"]))
    if alerts_sig != db.runtime_get("last_alerts", "") or (now.hour == 20 and _once(f"cro:{day}")):
        db.runtime_set("last_alerts", alerts_sig)
        if snap["allarmi"] or now.hour == 20:
            workflows.risk_review()
            woke.append("cro")
    if now.weekday() in (1, 3) and now.hour >= 9 and _once(f"research:{day}"):
        workflows.research_cycle()
        woke += ["senior_trend", "senior_validator"]
    if now.weekday() == 6 and now.hour >= 17 and _once(f"sunday:{day}"):
        workflows.committee()
        workflows.talent_cycle()
        compensation.pay_salaries(day)
        woke += ["capo"]
        if now.day <= 7:
            # riunione di allocazione per ogni pod, poi la regola a shrinkage: vince la scelta piu' prudente
            decided = {}
            for p in pods.all_pods():
                if p["id"] != "pod_zero" and p["status"] != "chiuso":
                    decided[p["id"]] = meetings.allocation_meeting(p["id"]).get("decisione", "mantieni")
            for r in economy.reallocate(apply=False):
                d = decided.get(r["pod"], "mantieni")
                new = r["a"]
                if d == "riduci":
                    new = min(new, r["da"] * 0.5)
                elif d == "mantieni":
                    new = min(new, r["da"])
                if abs(new - r["da"]) > 1e-12:
                    pods.set_capital(r["pod"], new, f"riallocazione mensile (riunione: {d}; regola: {r['motivo']})", actor="economia")
            for p in pods.all_pods():
                if p["id"] != "pod_zero":
                    economy.distribute_bonus(p["id"])
    events.publish("firm.heartbeat", "sistema", dict(svegliati=woke, semaforo=snap["semaforo"]), audit_it=False)
    return dict(svegliati=woke, note=notes, semaforo=snap["semaforo"])
