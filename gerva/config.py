"""Lettura di config/gerva.yaml in oggetti tipizzati. Un valore fuori dai limiti del codice fa fallire l'avvio."""
from __future__ import annotations

import os

import yaml

from .live.runner import Settings
from .risk.engine import Limits

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load(path: str | None = None) -> tuple[Settings, Limits, dict]:
    path = path or os.environ.get("GERVA_CONFIG") or os.path.join(ROOT, "config", "gerva.yaml")
    with open(path) as f:
        c = yaml.safe_load(f) or {}
    mode = c.get("mode", "paper")
    if mode not in ("paper", "alpaca-paper"):
        raise ValueError(f"mode '{mode}' non ammesso: solo paper o alpaca-paper (il live richiede i cancelli verdi)")
    home = os.environ.get("GERVA_HOME") or c.get("home", "var/gerva")
    home = home if os.path.isabs(home) else os.path.join(ROOT, home)
    s = Settings(home=home, mode=mode, interval=float(c.get("interval_s", 900)), band=float(c.get("band", 0.02)),
                 equity_window=tuple(c.get("equity_window", ("15:45", "16:00"))), start_cash=float(c.get("start_cash", 12000)),
                 cash_symbol=(c.get("cash") or {}).get("symbol") or None, cash_buffer=float((c.get("cash") or {}).get("buffer", 0.05)))
    if not 0.0 <= s.cash_buffer <= 0.5:
        raise ValueError("cash.buffer deve stare tra 0 e 0,5")
    return s, Limits(**(c.get("limits") or {})), c
