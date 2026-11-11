"""
Supervisore: tiene vivo il ciclo live.

    python -m gerva supervise -- run --mode paper

  * avvia il comando come processo figlio e lo riavvia se muore, con attesa esponenziale (2s, 4s, ... max 5 min);
  * se il figlio smette di battere (file di battito piu' vecchio di `stall_after` secondi) lo termina e lo riavvia:
    un processo vivo ma appeso e' peggio di uno morto;
  * tetto ai riavvii: oltre `max_restarts` in un'ora si ferma e manda un allarme critico. Un sistema che cade
    dieci volte in un'ora ha un difetto, non sfortuna: insistere farebbe solo danni;
  * SIGTERM/SIGINT: passa il segnale al figlio, aspetta la chiusura ordinata, esce.

In produzione va comunque messo sotto systemd (Restart=always) o Docker (restart: unless-stopped): sono loro
a riavviare il supervisore se muore la macchina. Vedi deploy/gerva.service.
"""
from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time

from . import alerts

log = logging.getLogger("gerva.supervisor")


def heartbeat_age(path: str) -> float:
    try:
        return time.time() - os.path.getmtime(path)
    except OSError:
        return float("inf")


def supervise(cmd: list[str], heartbeat_file: str, stall_after: float = 900.0, max_restarts: int = 10,
              window: float = 3600.0, grace: float = 30.0, poll: float = 5.0, sleep=time.sleep) -> int:
    restarts: list[float] = []
    stop = {"flag": False}
    child: dict = {"p": None}

    def on_signal(signum, _frame):
        stop["flag"] = True
        if child["p"] and child["p"].poll() is None:
            child["p"].send_signal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    backoff = 2.0
    while not stop["flag"]:
        started = time.time()
        log.info("avvio: %s", " ".join(cmd))
        p = child["p"] = subprocess.Popen(cmd)
        while p.poll() is None and not stop["flag"]:
            sleep(poll)
            age = heartbeat_age(heartbeat_file)
            if time.time() - started > stall_after and age > stall_after:
                alerts.send("critical", f"ciclo appeso (nessun battito da {age:.0f}s): lo riavvio", key="stall")
                p.terminate()
                try:
                    p.wait(grace)
                except subprocess.TimeoutExpired:
                    p.kill()
                break
        if stop["flag"]:
            try:
                p.wait(grace)
            except subprocess.TimeoutExpired:
                p.kill()
            return 0
        code = p.poll()
        if code == 0:
            log.info("il ciclo e' uscito in modo ordinato: fine")
            return 0
        if code == 3:                      # uscita volontaria per KILL: non si riavvia
            alerts.send("critical", "il ciclo si e' fermato per KILL: nessun riavvio automatico", key="kill-exit")
            return 3
        now = time.time()
        restarts = [t for t in restarts if now - t < window] + [now]
        if len(restarts) > max_restarts:
            alerts.send("critical", f"{len(restarts)} riavvii in un'ora: mi fermo. Serve un intervento.", key="restart-budget")
            return 2
        if now - started > 600:
            backoff = 2.0                  # era rimasto su abbastanza: si riparte da un'attesa breve
        alerts.send("warn", f"ciclo terminato (codice {code}); riavvio tra {backoff:.0f}s [{len(restarts)}/{max_restarts}]",
                    key="restart", min_interval=0)
        sleep(backoff)
        backoff = min(backoff * 2, 300.0)
    return 0


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    root = os.environ.get("GERVA_HOME", "var/gerva")
    cmd = [sys.executable, "-m", "gerva"] + argv
    return supervise(cmd, os.path.join(root, "heartbeat"))
