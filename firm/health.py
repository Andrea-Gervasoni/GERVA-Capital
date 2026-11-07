"""
La salute dei programmi, per l'orologio del portale.

L'orologio segna l'ora giusta solo se tutto e' vivo: il lettore di Telegram, il collegamento a IBKR (Trader Workstation), il battito
(cron ogni 15 minuti) e il banco libero. Se uno si ferma, l'orologio si blocca sull'ultimo istante in cui tutto funzionava e dice cosa manca.
Nel weekend IBKR e' "a riposo" (le azioni non si scambiano, TWS spesso e' chiusa): si vede, ma non ferma l'orologio.
Telegram e il banco libero contano sempre: le crypto girano 24/7.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
from zoneinfo import ZoneInfo

from . import db

PARTS = [  # (nome, chiave runtime, secondi di tolleranza, processo da cercare, cosa fare)
    ("Telegram", "telegram.alive", 180, "firm.py [t]elegram", "il lettore dei segnali non ascolta"),
    ("IBKR", "ibkr.live_ok", 180, "firm.py live-[n]av", "Trader Workstation non risponde"),
    ("Battito", "heartbeat.alive", 1200, None, "il cron non gira: Mac in stop o pianificazione cancellata (ripristina_cron.sh)"),
    ("Banco libero", "free.alive", 180, "firm.py free-[d]esk", "il banco libero non da' segni di vita"),
]


def _parse(v):
    if not v:
        return None
    try:
        return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def _running(pattern: str | None):
    """Il processo esiste su questa macchina? None se non si puo' sapere (Docker, niente pgrep)."""
    if not pattern or not shutil.which("pgrep"):
        return None
    try:
        return subprocess.run(["pgrep", "-f", pattern], capture_output=True, timeout=3).returncode == 0
    except Exception:
        return None


def _weekend(now: dt.datetime) -> bool:
    return now.astimezone(ZoneInfo("America/New_York")).weekday() >= 5


def status(now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    parts, lasts = [], []
    for name, key, tol, proc, why in PARTS:
        if name == "Telegram" and not os.environ.get("TELEGRAM_CHATS"):
            continue                                                        # Telegram non configurato: non conta
        raw = db.runtime_get(key)
        t = _parse(raw.get("ts") if isinstance(raw, dict) else raw)
        fresh = t is not None and (now - t).total_seconds() <= tol
        ok, stato, breve, motivo = fresh, "ok", None, None
        if name == "Telegram" and fresh and isinstance(raw, dict) and raw.get("collegato") is False:
            ok, breve, motivo = False, "scollegato", "il processo e' acceso ma ha perso la rete: si ricollega da solo, se dura controlla il Wi-Fi del Mac"
        if name == "IBKR" and t is None:                                   # prima di questa versione: l'ultima lettura riuscita
            old = db.runtime_get("ibkr.live") or {}
            t = _parse(old.get("ts")) if not old.get("errore") else None
        if not ok and motivo is None:
            run = _running(proc)
            if run is False:
                breve, motivo = "spento", f"{why}: il processo non e' acceso. Lo rialza il cron entro un minuto (se non succede: deploy/mac/ripristina_cron.sh)"
            elif name == "IBKR":
                err = (db.runtime_get("ibkr.live") or {}).get("errore")
                breve = "TWS chiusa" if err else "fermo"
                motivo = f"{why}: aperta, collegata e con l'API attiva?" + (f" Ultimo tentativo: {err}" if err else "")
            elif t is None:
                breve, motivo = "codice vecchio?", f"{why}: acceso ma non ha mai scritto il segno di vita. Se hai appena aggiornato, gira ancora col codice di prima: riavvialo una volta"
            else:
                breve, motivo = "fermo", f"{why} da {int((now - t).total_seconds() // 60)} minuti: processo bloccato o Mac in stop"
        if name == "IBKR" and not ok and _weekend(now):
            stato, breve = "riposo", "weekend"
            motivo = "weekend: le azioni non si scambiano, Trader Workstation puo' restare chiusa. Non ferma l'orologio."
        elif not ok:
            stato = "fermo"
        parts.append(dict(nome=name, ok=ok, stato=stato, breve=breve, ultimo=t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else None, motivo=motivo))
        if stato != "riposo":
            lasts.append(t if ok or t else None)
    counted = [p for p in parts if p["stato"] != "riposo"]
    all_ok = all(p["ok"] for p in counted)
    frozen = None if all_ok else (min(lasts) if lasts and all(lasts) else None)
    return dict(ok=all_ok, ora=now.strftime("%Y-%m-%dT%H:%M:%SZ"), bloccato_a=frozen.strftime("%Y-%m-%dT%H:%M:%SZ") if frozen else None, parti=parts)
