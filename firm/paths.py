"""Percorsi del progetto. Tutto lo stato mutabile sta in var/ (escluso da git)."""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config")
AGENTS = os.environ.get("GERVA_AGENTS", os.path.join(ROOT, "agents"))   # il demo usa una copia in var/demo/agents
EVALS = os.path.join(ROOT, "evals")
RESEARCH = os.environ.get("GERVA_RESEARCH", os.path.join(ROOT, "research"))   # sul server: volume scrivibile
VAR = os.environ.get("GERVA_VAR", os.path.join(ROOT, "var"))
DB_PATH = os.path.join(VAR, "firm.sqlite")
KILL_FILE = os.path.join(ROOT, "KILL")
ANDREA_TOKEN = os.path.join(VAR, "andrea.token")

# GERVA-Q (Pod Zero): sul Mac di Andrea e' ~/Documents/GERVA-Q; qui si puo' puntare allo snapshot
GERVA_Q = os.path.expanduser(os.environ.get("GERVA_Q_PATH", "")) or next(
    (p for p in (os.path.expanduser("~/Documents/GERVA-Q"),
                 os.path.join(ROOT, "_incoming", "quant_engine")) if os.path.isdir(p)),
    os.path.expanduser("~/Documents/GERVA-Q"))


def var(*parts: str) -> str:
    p = os.path.join(VAR, *parts)
    os.makedirs(os.path.dirname(p) if os.path.splitext(p)[1] else p, exist_ok=True)
    return p
