"""
I processi che restano accesi (banco libero, lettura di IBKR, Telegram) si riavviano da soli quando il codice cambia.

Dopo un git pull ognuno se ne accorge entro un minuto, scrive una riga nel suo log ed esce; il cron (ripristina_cron.sh) lo
rialza entro un altro minuto con il codice nuovo. Cosi' basta aggiornare: niente pkill a mano, niente processi col codice vecchio.
"""
from __future__ import annotations

import glob
import os
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def stamp() -> float:
    files = glob.glob(os.path.join(_ROOT, "firm", "*.py")) + [os.path.join(_ROOT, "firm.py"), os.path.join(_ROOT, ".env")]      # anche una sala nuova in .env
    return max((os.path.getmtime(f) for f in files if os.path.exists(f)), default=0.0)


class Watch:
    """w = Watch('banco libero'); poi nel ciclo: w.check()  -> esce se il codice e' cambiato (al massimo un controllo al minuto)."""

    def __init__(self, name: str, every: float = 60.0):
        self.name, self.every, self.t0, self.last = name, every, stamp(), time.time()

    def changed(self) -> bool:
        if time.time() - self.last < self.every:
            return False
        self.last = time.time()
        return stamp() > self.t0

    def check(self) -> None:
        if self.changed():
            print(f"[{self.name}] codice aggiornato: riparto con quello nuovo (lo rialza il cron entro un minuto)", flush=True)
            os._exit(0)
