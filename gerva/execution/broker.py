"""
Interfaccia verso il broker e broker PAPER interno.

Ogni adattatore offre le stesse cinque operazioni. Il ciclo live non sa con chi parla:

    account()                      -> Account(equity, cash)                 la VERITA' sul conto e' sempre del broker
    positions()                    -> {simbolo: Position(qty, price)}
    prices(simboli)                -> {simbolo: ultimo prezzo}
    submit(client_id, simbolo, qty con segno, prezzo di riferimento) -> Fill
    lookup(client_id)              -> Fill | None        per sapere, dopo un crash, se un ordine era arrivato
    flatten()                      -> annulla tutto e chiude tutto (KILL)

`submit` deve essere IDEMPOTENTE rispetto a client_id: se l'ordine con quell'identificativo esiste gia',
restituisce il suo esito e non ne crea un secondo.

PaperBroker simula gli eseguiti sui prezzi veri del momento, con slippage e commissioni per sede, e tiene lo
stato nel registro: sopravvive ai riavvii. I suoi risultati sono SIMULATI (nessun libro ordini, nessuna coda).
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Callable, Protocol

from ..risk.engine import HARD_MAX_LEVERAGE


class BrokerError(RuntimeError):
    pass


@dataclass
class Account:
    equity: float
    cash: float


@dataclass
class Position:
    qty: float
    price: float

    @property
    def value(self) -> float:
        return self.qty * self.price


@dataclass
class Fill:
    client_id: str
    status: str                 # filled | partial | rejected | pending
    qty: float = 0.0            # con segno
    price: float = 0.0
    fee: float = 0.0
    reason: str = ""


class Broker(Protocol):
    name: str

    def account(self) -> Account: ...
    def positions(self) -> dict[str, Position]: ...
    def prices(self, symbols: list[str]) -> dict[str, float]: ...
    def submit(self, client_id: str, symbol: str, qty: float, ref_price: float) -> Fill: ...
    def lookup(self, client_id: str) -> Fill | None: ...
    def flatten(self) -> list[Fill]: ...


class PaperBroker:
    name = "paper"

    def __init__(self, journal, price_fn: Callable[[list[str]], dict[str, float]], start_cash: float = 12_000.0,
                 fee: dict | None = None, slippage: dict | None = None, venue_of: Callable[[str], str] | None = None):
        self.j, self.price_fn = journal, price_fn
        self.fee = fee or {"crypto": 0.0025, "ibkr": 0.0005}
        self.slip = slippage or {"crypto": 0.0005, "ibkr": 0.0002}
        self.venue_of = venue_of or (lambda s: "ibkr")
        if self.j.get("paper.cash") is None:
            self.j.set("paper.cash", float(start_cash))
            self.j.set("paper.pos", {})
            self.j.set("paper.fills", {})

    # ---- stato --------------------------------------------------------------
    def _pos(self) -> dict[str, float]:
        return {k: float(v) for k, v in (self.j.get("paper.pos") or {}).items() if abs(v) > 1e-12}

    def prices(self, symbols: list[str]) -> dict[str, float]:
        return {k: float(v) for k, v in self.price_fn(list(symbols)).items() if v and v > 0}

    def positions(self) -> dict[str, Position]:
        pos = self._pos()
        px = self.prices(list(pos)) if pos else {}
        missing = [s for s in pos if s not in px]
        if missing:
            raise BrokerError(f"nessun prezzo per {missing}: il valore del conto non e' calcolabile")
        return {s: Position(q, px[s]) for s, q in pos.items()}

    def account(self) -> Account:
        cash = float(self.j.get("paper.cash"))
        return Account(cash + sum(p.value for p in self.positions().values()), cash)

    # ---- ordini -------------------------------------------------------------
    def lookup(self, client_id: str) -> Fill | None:
        f = (self.j.get("paper.fills") or {}).get(client_id)
        return Fill(**f) if f else None

    def submit(self, client_id: str, symbol: str, qty: float, ref_price: float) -> Fill:
        done = self.lookup(client_id)
        if done:
            return done
        px = self.prices([symbol]).get(symbol)
        if not px:
            return self._save(Fill(client_id, "rejected", reason="nessun prezzo"))
        venue = self.venue_of(symbol)
        fill_px = px * (1 + self.slip.get(venue, 0.0005) * (1 if qty > 0 else -1))
        notional = abs(qty) * fill_px
        fee = notional * self.fee.get(venue, 0.001)
        pos = self._pos()
        cash = float(self.j.get("paper.cash"))
        acct = self.account()
        new_qty = pos.get(symbol, 0.0) + qty
        gross_after = sum(abs(q) * self.prices([s])[s] for s, q in pos.items() if s != symbol) + abs(new_qty) * px
        increasing = abs(new_qty) > abs(pos.get(symbol, 0.0))
        if increasing and gross_after > HARD_MAX_LEVERAGE * acct.equity:
            return self._save(Fill(client_id, "rejected", reason="margine insufficiente"))
        pos[symbol] = new_qty
        with self.j.tx() as db:                           # cassa, posizione ed eseguito cambiano insieme o non cambiano
            fills = self.j.get("paper.fills") or {}
            f = Fill(client_id, "filled", qty, fill_px, fee)
            fills[client_id] = asdict(f)
            if len(fills) > 5000:
                fills = dict(list(fills.items())[-2500:])
            for k, v in (("paper.cash", cash - qty * fill_px - fee), ("paper.pos", pos), ("paper.fills", fills)):
                db.execute("INSERT INTO kv(k,v,ts) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v, ts=excluded.ts",
                           (k, json.dumps(v), time.time()))
        return f

    def _save(self, f: Fill) -> Fill:
        fills = self.j.get("paper.fills") or {}
        fills[f.client_id] = asdict(f)
        self.j.set("paper.fills", fills)
        return f

    def flatten(self) -> list[Fill]:
        out = []
        for s, q in self._pos().items():
            px = self.prices([s]).get(s, 0.0)
            out.append(self.submit(f"KILL-{int(time.time())}-{s}", s, -q, px))
        return out
