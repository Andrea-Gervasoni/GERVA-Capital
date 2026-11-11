"""
Mattoni di robustezza: retry con attesa esponenziale, interruttore automatico, limite di tempo.

Idea: un errore di rete non deve mai (a) fermare il ciclo, (b) far ripetere un'azione non ripetibile.
`retry` si usa SOLO per letture o per azioni idempotenti; l'invio di un ordine si protegge con
l'identificativo del cliente (vedi gerva.ops.journal), non con un retry cieco.
"""
from __future__ import annotations

import random
import threading
import time
from typing import Callable, TypeVar

T = TypeVar("T")


class CircuitOpen(RuntimeError):
    """L'interruttore e' aperto: la dipendenza e' considerata giu', non la si chiama."""


class Timeout(RuntimeError):
    pass


def retry(fn: Callable[[], T], tries: int = 4, base: float = 0.5, cap: float = 15.0,
          retry_on: tuple = (Exception,), give_up_on: tuple = (), sleep=time.sleep) -> T:
    """Chiama fn fino a `tries` volte; attese base*2^k con rumore casuale (evita le tempeste di richieste)."""
    last = None
    for k in range(tries):
        try:
            return fn()
        except give_up_on:
            raise
        except retry_on as e:
            last = e
            if k == tries - 1:
                break
            sleep(min(cap, base * (2 ** k)) * (0.5 + random.random() / 2))
    raise last


class CircuitBreaker:
    """Dopo `fail_max` errori consecutivi si apre per `reset_after` secondi: le chiamate falliscono subito.
    Poi lascia passare UNA chiamata di prova (semiaperto): se riesce si richiude, se fallisce si riapre."""

    def __init__(self, name: str, fail_max: int = 5, reset_after: float = 60.0, clock=time.monotonic):
        self.name, self.fail_max, self.reset_after, self.clock = name, fail_max, reset_after, clock
        self.fails, self.opened_at = 0, None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        return "half-open" if self.clock() - self.opened_at >= self.reset_after else "open"

    def call(self, fn: Callable[[], T]) -> T:
        with self._lock:
            if self.state == "open":
                raise CircuitOpen(f"{self.name}: interruttore aperto")
        try:
            out = fn()
        except Exception:
            with self._lock:
                self.fails += 1
                if self.fails >= self.fail_max or self.opened_at is not None:
                    self.opened_at = self.clock()
            raise
        with self._lock:
            self.fails, self.opened_at = 0, None
        return out


def with_timeout(fn: Callable[[], T], seconds: float) -> T:
    """Esegue fn in un thread e smette di aspettarlo dopo `seconds`. Il thread non si puo' uccidere:
    serve a non bloccare il ciclo su una chiamata appesa, non a liberare la risorsa."""
    box: dict = {}

    def run():
        try:
            box["v"] = fn()
        except BaseException as e:           # riportato al chiamante
            box["e"] = e
    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise Timeout(f"nessuna risposta in {seconds:.0f}s")
    if "e" in box:
        raise box["e"]
    return box["v"]
