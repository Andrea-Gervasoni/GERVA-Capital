"""
Strumenti degli agenti e permessi (regole inviolabili 2, 3, 5, 7).

Ogni strumento ha: funzione, effetto collaterale (True = cambia qualcosa fuori dal suo output),
categoria. Un agente puo' usare SOLO gli strumenti elencati nel suo profile.yaml, e:
  * nessun agente ha strumenti per impostazioni, limiti di rischio, budget, KILL esecutivo,
    credenziali o modalita' live: non esistono in questo registro (FORBIDDEN li elenca per i test);
  * gli agenti che leggono testo esterno (Redazione) non hanno strumenti con effetti collaterali
    che spostano denaro, scrivono configurazione o inviano messaggi all'esterno;
  * submit_order e' legato al pod dell'agente: non puo' operare sul pod di un altro.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from firm import db, events, risk, trials, gateway, pods, scorekeeper, budget


@dataclass(frozen=True)
class Tool:
    fn: Callable
    side_effect: bool
    category: str        # lettura | calcolo | registro | ordine | comunicazione_interna
    doc: str


def _firm_snapshot():
    return dict(rischio=risk.snapshot(), budget=budget.status(), prove=trials.counts())


def _pod_snapshot(agent_id: str):
    pid = pods.pod_of_agent(agent_id)
    return dict(pod=pods.get(pid), libro=gateway.pod_book(pid)) if pid else {}


def _submit_order(agent_id: str, instrument: str, side: str, qty: float, reason: str, horizon: str):
    pid = pods.pod_of_agent(agent_id)          # il pod viene dal profilo, non dall'agente
    if not pid:
        raise PermissionError("l'agente non gestisce un pod")
    return gateway.submit_order(pid, agent_id, instrument, side, qty, reason, horizon)


def _delegate(agent_id: str, assignee: str, title: str, order_id: int | None = None, parent_id: int | None = None):
    from firm import tasks
    return tasks.create(order_id, parent_id, assignee, agent_id, title)


TOOLS: dict[str, Tool] = {
    "firm_snapshot": Tool(lambda agent_id: _firm_snapshot(), False, "lettura", "stato di rischio, budget, prove"),
    "risk_snapshot": Tool(lambda agent_id: risk.snapshot(), False, "lettura", "semaforo e allarmi del motore di rischio"),
    "stress_test": Tool(lambda agent_id, weights, kinds: {k: risk.stress(weights, kinds, s) for k, s in risk.SCENARIOS.items()},
                        False, "calcolo", "perdita sotto gli scenari di stress"),
    "recommend_kill": Tool(lambda agent_id, reason, evidence: risk.recommend_kill(agent_id, reason, evidence),
                           True, "comunicazione_interna", "raccomanda il KILL al motore di rischio (non lo esegue)"),
    "trial_registry_view": Tool(lambda agent_id: trials.counts(), False, "lettura", "contatore globale delle prove"),
    "trial_register": Tool(lambda agent_id, strategy_id, family, params, hypothesis:
                           trials.register(agent_id, strategy_id, family, params, hypothesis),
                           True, "registro", "registra una prova PRIMA del test"),
    "trial_gate": Tool(lambda agent_id, trial_id, **kw: trials.gate(trial_id, **kw), False, "calcolo",
                       "cancello automatico DSR/PBO/costi/look-ahead"),
    "run_backtest": Tool(lambda agent_id, **kw: {"nota": "eseguito dal codice della pipeline di ricerca"},
                         False, "calcolo", "backtest quantlab (eseguito dal codice)"),
    "lookahead_test": Tool(lambda agent_id, **kw: {"nota": "eseguito dal codice della pipeline di validazione"},
                           False, "calcolo", "test di troncamento e oracolo"),
    "register_forecast": Tool(lambda agent_id, statement, prob, deadline, criterion, source:
                              scorekeeper.register_forecast(agent_id, statement, prob, deadline, criterion, source),
                              True, "registro", "previsione con probabilita', scadenza e criterio"),
    "read_news_queue": Tool(lambda agent_id, status="nuova", limit=20:
                            db.q("SELECT id,title,url,domain,published,summary,status FROM news WHERE status=? "
                                 "ORDER BY id DESC LIMIT ?", (status, limit)), False, "lettura", "coda notizie"),
    "submit_news_item": Tool(lambda agent_id, news_id, summary, tags:
                             db.ex("UPDATE news SET summary=?, tags=?, agent_id=?, status='da_verificare' WHERE id=?",
                                   (summary, db.dumps(tags), agent_id, news_id)),
                             False, "registro", "sintesi e tag di una notizia (resta da verificare)"),
    "find_second_source": Tool(lambda agent_id, news_id: [], False, "lettura", "fonti indipendenti dalla coda"),
    "verify_news_item": Tool(lambda agent_id, news_id, verified, second_url:
                             db.ex("UPDATE news SET status=?, second_url=?, checked_by=? WHERE id=?",
                                   ("verificata" if verified else "respinta", second_url, agent_id, news_id)),
                             False, "registro", "esito della verifica su seconda fonte"),
    "publish_bulletin": Tool(lambda agent_id, text: events.publish("news.bulletin", agent_id, dict(testo=text)),
                             False, "comunicazione_interna", "bollettino interno"),
    "delegate_task": Tool(_delegate, True, "comunicazione_interna", "affida un compito a un subordinato"),
    "read_task_results": Tool(lambda agent_id, order_id: db.q("SELECT * FROM tasks WHERE order_id=?", (order_id,)),
                              False, "lettura", "risultati dei compiti delegati"),
    "research_queue": Tool(lambda agent_id: db.q("SELECT * FROM research ORDER BY ts DESC LIMIT 20"),
                           False, "lettura", "fascicoli di ricerca"),
    "write_research_doc": Tool(lambda agent_id, rid, name, text: _write_research(rid, name, text), False,
                               "registro", "scrive in research/<id>/"),
    "read_research_doc": Tool(lambda agent_id, rid: _read_research(rid), False, "lettura", "legge un fascicolo"),
    "write_validation_report": Tool(lambda agent_id, rid, text: _write_research(rid, "validazione.md", text),
                                    False, "registro", "relazione di validazione"),
    "pod_snapshot": Tool(lambda agent_id: _pod_snapshot(agent_id), False, "lettura", "libro del proprio pod"),
    "strategy_library": Tool(lambda agent_id: ["ewma_trend", "tsmom", "donchian", "short_reversal",
                                               "sector_momentum"], False, "lettura", "segnali validati disponibili"),
    "submit_order": Tool(_submit_order, True, "ordine", "invia un ordine al Gateway (solo per il proprio pod)"),
    "mailbox_propose": Tool(lambda agent_id, **kw: _propose_big_request(agent_id, **kw), True,
                            "comunicazione_interna", "propone una grande richiesta ad Andrea"),
}

# Cio' che NESSUN agente deve poter fare (verificato da tests/test_permissions.py)
FORBIDDEN = {"settings.set", "settings.set_risk_limit", "risk.engage_kill", "risk.release_kill",
             "mailbox.decide", "budget.authorize", "gateway.flush", "live_mode", "read_env"}
WEB_READER_DEPTS = {"redazione"}


def _write_research(rid: str, name: str, text: str):
    import os
    from firm import paths
    if "/" in name or ".." in name or not rid.replace("-", "").replace("_", "").isalnum():
        raise PermissionError("percorso non ammesso")
    d = os.path.join(paths.RESEARCH, rid)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name), "w") as f:
        f.write(text)
    return os.path.join("research", rid, name)


def _read_research(rid: str):
    import glob, os
    from firm import paths
    return {os.path.basename(p): open(p).read()[:6000] for p in glob.glob(os.path.join(paths.RESEARCH, rid, "*.md"))}


def _propose_big_request(agent_id: str, category: int, title: str, why: str, options: list,
                         recommendation: str, safe_default: str):
    from firm import mailbox
    return mailbox.big_request(category, f"[{agent_id}] {title}", why, options, recommendation, safe_default,
                               dedup_key=f"{agent_id}:{title}")


def allowed(agent: dict, tool: str) -> bool:
    prof = agent.get("profile", agent)
    if tool not in TOOLS or tool not in (prof.get("tools") or []):
        return False
    t = TOOLS[tool]
    if prof.get("dept") in WEB_READER_DEPTS and t.category == "ordine":
        return False
    if t.category == "ordine" and not prof.get("pod"):
        return False
    return True


def execute(agent: dict, tool: str, **kwargs):
    if not allowed(agent, tool):
        events.publish("tool.denied", agent["id"], dict(strumento=tool))
        raise PermissionError(f"{agent['id']} non puo' usare {tool}")
    out = TOOLS[tool].fn(agent["id"], **kwargs)
    events.publish("tool.used", agent["id"], dict(strumento=tool, effetto=TOOLS[tool].side_effect), audit_it=True)
    return out
