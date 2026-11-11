"""
Broker composito: ogni simbolo va all'adattatore della sua sede (crypto -> Alpaca, azioni -> IBKR).

Per il ciclo e' un broker solo:
    account()    somma patrimonio e cassa dei conti (tutti nella stessa valuta: dollari)
    positions()  unione delle posizioni
    submit()     instradato con `venue_of(simbolo)`
    lookup()     chiede a TUTTI: l'identificativo non dice su quale sede era partito l'ordine. Risponde None solo
                 se nessuno lo conosce E tutti hanno risposto: se una sede non e' interrogabile e le altre non
                 lo conoscono l'esito e' ignoto, e si solleva (None vorrebbe dire "mai inviato")
    flatten()    chiude su tutte le sedi; se una fallisce le altre si chiudono lo stesso, poi si solleva
"""
from __future__ import annotations

from typing import Callable

from .broker import Account, Broker, BrokerError, Fill, Position


class CompositeBroker:
    def __init__(self, routes: dict[str, Broker], venue_of: Callable[[str], str]):
        if not routes:
            raise ValueError("nessun broker")
        self.routes, self.venue_of = dict(routes), venue_of
        self.name = "+".join(b.name for b in self.routes.values())

    def _for(self, symbol: str) -> Broker | None:
        return self.routes.get(self.venue_of(symbol))

    def account(self) -> Account:
        parts = [b.account() for b in self.routes.values()]
        return Account(sum(a.equity for a in parts), sum(a.cash for a in parts))

    def positions(self) -> dict[str, Position]:
        out: dict[str, Position] = {}
        for venue, b in self.routes.items():
            for sym, p in b.positions().items():
                if sym in out:
                    raise BrokerError(f"{sym} e' in posizione su due sedi: il ciclo non saprebbe quale ritoccare")
                out[sym] = p
        return out

    def prices(self, symbols: list[str]) -> dict[str, float]:
        out: dict[str, float] = {}
        for venue, b in self.routes.items():
            mine = [s for s in symbols if self.venue_of(s) == venue]
            if mine:
                out.update(b.prices(mine))
        return out

    def submit(self, client_id: str, symbol: str, qty: float, ref_price: float) -> Fill:
        b = self._for(symbol)
        if b is None:
            return Fill(client_id, "rejected", reason=f"nessun broker per la sede '{self.venue_of(symbol)}'")
        return b.submit(client_id, symbol, qty, ref_price)

    def lookup(self, client_id: str) -> Fill | None:
        errors = []
        for b in self.routes.values():
            try:
                f = b.lookup(client_id)
            except Exception as e:
                errors.append(f"{b.name}: {type(e).__name__}: {str(e)[:120]}")
                continue
            if f is not None:
                return f
        if errors:
            raise BrokerError("esito ignoto, sede non interrogabile: " + "; ".join(errors))
        return None

    def flatten(self) -> list[Fill]:
        out, errors = [], []
        for b in self.routes.values():
            try:
                out += b.flatten()
            except Exception as e:
                errors.append(f"{b.name}: {type(e).__name__}: {str(e)[:200]}")
        if errors:
            raise BrokerError("chiusura incompleta: " + "; ".join(errors))
        return out
