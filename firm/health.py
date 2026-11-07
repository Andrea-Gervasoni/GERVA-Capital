"""
La salute dei programmi, per l'orologio del portale.

L'orologio segna l'ora giusta solo se TUTTO e' vivo: il lettore di Telegram, il collegamento a IBKR (Trader Workstation), il battito
(cron ogni 15 minuti) e il banco libero. Se uno si ferma, l'orologio si blocca sull'ultimo istante in cui tutto funzionava e dice cosa manca.
"""
from __future__ import annotations

import datetime as dt
import os

from . import db

PARTS = [  # (nome, chiave runtime, secondi di tolleranza, cosa fare)
    ("Telegram", "telegram.alive", 180, "il lettore dei segnali non ascolta: rete del Mac, processo fermo o sessione scaduta"),
    ("IBKR", "ibkr.live_ok", 180, "Trader Workstation non risponde: aperta, collegata e con l'API attiva?"),
    ("Battito", "heartbeat.alive", 1200, "il cron non gira: Mac in stop o pianificazione cancellata (ripristina_cron.sh)"),
    ("Banco libero", "free.alive", 180, "il processo del banco libero e' fermo (lo rialza il cron entro un minuto)"),
]


def _ts(v):
    if isinstance(v, dict):
        if v.get("collegato") is False:
            return None
        v = v.get("ts")
    if not v:
        return None
    try:
        return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def status(now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    parts, lasts = [], []
    for name, key, tol, why in PARTS:
        if name == "Telegram" and not os.environ.get("TELEGRAM_CHATS"):
            continue                                                        # Telegram non configurato: non conta
        t = _ts(db.runtime_get(key))
        ok = t is not None and (now - t).total_seconds() <= tol
        parts.append(dict(nome=name, ok=ok, ultimo=t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else None, motivo=None if ok else why))
        lasts.append(t)
    all_ok = all(p["ok"] for p in parts)
    frozen = None if all_ok else (min(lasts) if all(lasts) else None)
    return dict(ok=all_ok, ora=now.strftime("%Y-%m-%dT%H:%M:%SZ"), bloccato_a=frozen.strftime("%Y-%m-%dT%H:%M:%SZ") if frozen else None, parti=parts)
