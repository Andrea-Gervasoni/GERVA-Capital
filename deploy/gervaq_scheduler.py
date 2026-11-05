#!/usr/bin/env python3
"""
Scheduler di GERVA-Q sul server (sostituisce il crontab del Mac, senza binari esterni).

  * motore azionario: run_daily.sh alle 22:35 ora italiana, lunedi'-venerdi' (README di GERVA-Q);
  * sleeve crypto: crypto_live.py 5 minuti dopo la chiusura di ogni candela 4h UTC (00:05, 04:05, ... UTC):
    scritto in UTC, cosi' il cambio dell'ora legale non sposta l'esecuzione (nel crontab del Mac andava corretto a mano).
Non modifica il codice di GERVA-Q: lo esegue con GERVAQ_IB_PORT (supportato da live.py e crypto_live.py) e
GERVAQ_MODE=paper. Un file KILL nella cartella di GERVA-Q resta il freno di emergenza di live.py.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

GQ = os.environ.get("GERVA_Q_PATH", "/gervaq")
ROME = ZoneInfo("Europe/Rome")
STATE = os.path.join(GQ, "logs", "scheduler_state.json")


def load_done() -> set[str]:
    try:
        return set(json.load(open(STATE)))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def mark_done(done: set[str], key: str):
    """Persistente: un riavvio del container non deve rilanciare lo stesso giro (ordini OPG ancora pendenti)."""
    done.add(key)
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(sorted(done)[-400:], f)
    os.replace(tmp, STATE)


def run(cmd: list[str], tag: str):
    os.makedirs(os.path.join(GQ, "logs"), exist_ok=True)
    log = os.path.join(GQ, "logs", f"{tag}_{dt.date.today().isoformat()}.log")
    env = dict(os.environ, GERVAQ_MODE="paper")
    with open(log, "a") as f:
        f.write(f"===== {dt.datetime.now(ROME).isoformat(timespec='minutes')} {tag} =====\n")
        f.flush()
        r = subprocess.run(cmd, cwd=GQ, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=3600)
    print(f"{tag}: codice di uscita {r.returncode}", flush=True)


def main():
    if os.environ.get("GERVAQ_MODE", "paper") != "paper":
        sys.exit("solo paper")
    os.makedirs(os.path.join(GQ, "logs"), exist_ok=True)
    done = load_done()
    while True:
        now_r, now_u = dt.datetime.now(ROME), dt.datetime.now(dt.timezone.utc)
        # finestre strette: se il server era spento all'ora giusta, il giro salta (meglio un giorno fermo che un doppio ordine)
        k_eq = f"eq:{now_r.date()}"
        if now_r.weekday() < 5 and (22, 35) <= (now_r.hour, now_r.minute) < (23, 15) and k_eq not in done:
            mark_done(done, k_eq)                       # segnato PRIMA di partire: un crash a meta' non rilancia
            run(["sh", "run_daily.sh"], "daily")
        k_cr = f"cr:{now_u.date()}:{now_u.hour}"
        if now_u.hour % 4 == 0 and 5 <= now_u.minute < 35 and k_cr not in done:
            mark_done(done, k_cr)
            run([sys.executable, "crypto_live.py", "--mode", "paper"], "crypto")
        time.sleep(20)


if __name__ == "__main__":
    main()
