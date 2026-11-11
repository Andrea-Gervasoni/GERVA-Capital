"""
Allarmi verso l'esterno. Non sollevano mai eccezioni: un allarme che non parte non deve fermare il trading.

Canali (variabili d'ambiente, tutte facoltative):
    GERVA_TELEGRAM_TOKEN + GERVA_TELEGRAM_CHAT   bot Telegram
    GERVA_WEBHOOK_URL                            POST JSON generico (ntfy, Slack, Discord...)
Senza canali configurati l'allarme resta nel registro degli eventi e nel log.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
import urllib.request

log = logging.getLogger("gerva.alerts")
_last: dict[str, float] = {}


def send(level: str, msg: str, key: str | None = None, min_interval: float = 900.0) -> bool:
    """level: info | warn | critical. key: allarmi con la stessa chiave non si ripetono prima di `min_interval`
    secondi (i critici passano sempre)."""
    k = key or msg[:60]
    now = time.time()
    if level != "critical" and now - _last.get(k, 0.0) < min_interval:
        return False
    _last[k] = now
    text = f"[GERVA {level.upper()}] {msg}"
    log.log(logging.CRITICAL if level == "critical" else logging.WARNING if level == "warn" else logging.INFO, text)
    sent = False
    tok, chat = os.environ.get("GERVA_TELEGRAM_TOKEN"), os.environ.get("GERVA_TELEGRAM_CHAT")
    try:
        if tok and chat:
            data = urllib.parse.urlencode({"chat_id": chat, "text": text[:3500]}).encode()
            urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=10).read()
            sent = True
    except Exception as e:
        log.warning("telegram non raggiungibile: %s", type(e).__name__)
    hook = os.environ.get("GERVA_WEBHOOK_URL")
    try:
        if hook:
            req = urllib.request.Request(hook, data=json.dumps({"level": level, "text": text}).encode(),
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10).read()
            sent = True
    except Exception as e:
        log.warning("webhook non raggiungibile: %s", type(e).__name__)
    return sent
