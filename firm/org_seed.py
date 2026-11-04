"""
Organico iniziale (brief: 1 Capo, 3 manager attivi — Rischio, Ricerca, Intelligence — 6-8 agenti LLM).

Deviazione dichiarata (STATUS.md): oltre agli 8 agenti iniziali ci sono i 3 Capi Pod richiesti
da M5, con budget minimo e sveglia settimanale. Le funzioni che si calcolano sono "automi"
(codice). Le altre scrivanie sono posizioni aperte, visibili nel portale.

Questo modulo scrive profile.yaml e memory.md SOLO se mancano: dopo il primo avvio la
configurazione vive nei file versionati in git (le promozioni li aggiornano).
"""
from __future__ import annotations

import os

import yaml

from . import paths

# id, nome, ruolo, reparto, grado, superiore, tipo, stanza, scrivania, budget/giorno EUR, strumenti, extra
ROSTER = [
    ("capo", "Lorenzo Bassi", "Capo (CEO)", "direzione", 6, None, "llm", "capo", 0, 0.12,
     ["delegate_task", "read_task_results", "firm_snapshot", "register_forecast", "mailbox_propose"], {}),
    # --- Rischio (indipendente, riferisce anche ad Andrea)
    ("cro", "Elena Conti", "Chief Risk Officer", "rischio", 5, "capo", "llm", "rischio", 0, 0.08,
     ["risk_snapshot", "stress_test", "recommend_kill", "register_forecast", "mailbox_propose"],
     {"reports_also_to": "andrea"}),
    ("risk_analyst", "—", "Risk Analyst", "rischio", 2, "cro", "open", "rischio", 1, 0.0, [], {}),
    ("limit_monitor", "Automa LM-1", "Limit Monitor", "rischio", 1, "cro", "code", "rischio", 2, 0.0, [], {}),
    # --- Ricerca
    ("head_research", "Giulia Moretti", "Head of Research", "ricerca", 5, "capo", "llm", "ricerca", 0, 0.06,
     ["delegate_task", "read_task_results", "trial_registry_view", "research_queue", "register_forecast"], {}),
    ("senior_trend", "Marco Ferri", "Senior Researcher — Trend/Momentum", "ricerca", 4, "head_research", "llm",
     "ricerca", 1, 0.06, ["trial_register", "run_backtest", "trial_gate", "write_research_doc", "register_forecast"], {}),
    ("senior_meanrev", "—", "Senior Researcher — Mean reversion/microstruttura", "ricerca", 4, "head_research",
     "open", "ricerca", 2, 0.0, [], {}),
    ("senior_crypto", "—", "Senior Researcher — Crypto/on-chain", "ricerca", 4, "head_research", "open",
     "ricerca", 3, 0.0, [], {}),
    ("senior_macro", "—", "Senior Researcher — Macro/regimi", "ricerca", 4, "head_research", "open",
     "ricerca", 4, 0.0, [], {}),
    ("senior_stats", "—", "Senior Researcher — Statistica/ML", "ricerca", 4, "head_research", "open",
     "ricerca", 5, 0.0, [], {}),
    ("research_analyst", "—", "Research Analyst", "ricerca", 1, "senior_trend", "open", "ricerca", 6, 0.0, [], {}),
    # --- Model Validation / Red Team (indipendente dalla Ricerca)
    ("senior_validator", "Chiara Romano", "Senior Validator (Red Team)", "validazione", 4, "capo", "llm",
     "validazione", 0, 0.06, ["read_research_doc", "run_backtest", "lookahead_test", "trial_registry_view",
                              "write_validation_report", "register_forecast"], {}),
    ("validation_analyst", "—", "Validation Analyst", "validazione", 1, "senior_validator", "open",
     "validazione", 1, 0.0, [], {}),
    # --- Redazione / Intelligence
    ("head_intel", "Paolo Ricci", "Head of Intelligence", "redazione", 5, "capo", "llm", "redazione", 0, 0.05,
     ["read_news_queue", "publish_bulletin", "register_forecast"], {}),
    ("news_analyst", "Sara Colombo", "News Analyst", "redazione", 1, "head_intel", "llm", "redazione", 1, 0.05,
     ["read_news_queue", "submit_news_item"], {}),
    ("fact_checker", "Davide Greco", "Fact-Checker", "redazione", 2, "head_intel", "llm", "redazione", 2, 0.04,
     ["read_news_queue", "find_second_source", "verify_news_item"], {}),
    ("event_calendar", "—", "Event Calendar Analyst", "redazione", 1, "head_intel", "open", "redazione", 3, 0.0, [], {}),
    # --- Dati e infrastruttura
    ("data_engineer", "Automa DE-1", "Data Engineer", "dati", 2, "capo", "code", "dati", 0, 0.0, [], {}),
    ("gateway", "Automa GW-1", "Gateway di Esecuzione", "dati", 3, "cro", "code", "dati", 1, 0.0, [], {}),
    ("budget_governor", "Automa BG-1", "Budget Governor", "dati", 3, "capo", "code", "dati", 2, 0.0, [], {}),
    # --- Performance & Talent
    ("scorekeeper", "Automa SK-1", "Scorekeeper", "talent", 3, "capo", "code", "hr", 0, 0.0, [], {}),
    ("auditor", "Automa AU-1", "Auditor/Compliance", "talent", 3, "capo", "code", "hr", 1, 0.0, [], {}),
    ("talent_manager", "—", "Talent Manager", "talent", 4, "capo", "open", "hr", 2, 0.0, [], {}),
    # --- Pod di trading (M5): Pod Zero = GERVA-Q, piu' tre pod in competizione
    ("pod_zero", "GERVA-Q v3", "Pod Zero (benchmark sistematico)", "pod", 5, "capo", "code", "trading", 0, 0.0, [], {}),
    ("execution_monitor", "Automa EM-1", "Execution Monitor (TCA)", "pod", 2, "cro", "code", "trading", 1, 0.0, [], {}),
    ("pod_trend", "Federico Marino", "Capo Pod Trend/Macro", "pod", 4, "capo", "llm", "trading", 2, 0.03,
     ["pod_snapshot", "strategy_library", "submit_order", "register_forecast"],
     {"pod": "trend", "philosophy": "Segue i trend lenti su piu' classi di attivo; taglia le perdite, lascia correre i profitti."}),
    ("pod_reversal", "Martina Gallo", "Capo Pod Reversal/Microstruttura", "pod", 4, "capo", "llm", "trading", 3, 0.03,
     ["pod_snapshot", "strategy_library", "submit_order", "register_forecast"],
     {"pod": "reversal", "philosophy": "Fornisce liquidita' quando gli altri la ritirano: compra l'ipervenduto di qualita', poco e per poco."}),
    ("pod_crypto", "Luca De Santis", "Capo Pod Crypto/Eventi", "pod", 4, "capo", "llm", "trading", 4, 0.03,
     ["pod_snapshot", "strategy_library", "submit_order", "register_forecast"],
     {"pod": "crypto", "philosophy": "Trend crypto con freno sul rischio di crash: riduce quando il carry e la leva altrui sono estremi."}),
]

MEMORY_TEMPLATE = """# Memoria di {name}

## Regole apprese

## Preferenze del superiore

## Errori ricorrenti da evitare
"""


def seed(force: bool = False) -> int:
    n = 0
    for (aid, name, role, dept, grade, sup, kind, room, desk, budget, tools, extra) in ROSTER:
        d = os.path.join(paths.AGENTS, aid)
        os.makedirs(d, exist_ok=True)
        pf = os.path.join(d, "profile.yaml")
        if force or not os.path.exists(pf):
            prof = dict(id=aid, name=name, role=role, dept=dept, grade=grade, superior=sup, kind=kind,
                        room=room, desk=desk, daily_budget_eur=budget, tools=tools,
                        provider="anthropic" if kind == "llm" else None, prompt_version=1, **extra)
            with open(pf, "w") as f:
                yaml.safe_dump(prof, f, allow_unicode=True, sort_keys=False)
            n += 1
        if kind == "llm" and not os.path.exists(os.path.join(d, "memory.md")):
            with open(os.path.join(d, "memory.md"), "w") as f:
                f.write(MEMORY_TEMPLATE.format(name=name))
    return n
