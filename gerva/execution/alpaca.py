"""
Adattatore per il conto PAPER di Alpaca (API v2). Solo paper: l'indirizzo live non e' nemmeno scritto qui.

ATTENZIONE: questo modulo e' collaudato contro un servizio FINTO (tests/test_gerva_live.py), non contro Alpaca:
dall'ambiente in cui e' stato scritto il servizio non era raggiungibile con delle chiavi. Il primo collegamento va
fatto con `python -m gerva check-broker` e un ordine da 25 dollari guardato a mano.

Chiavi: variabili d'ambiente ALPACA_KEY e ALPACA_SECRET (mai nel repository). Simboli: le crypto sono "BTC/USD".
Idempotenza: `client_order_id` = nostro identificativo; se Alpaca risponde 422 "client_order_id must be unique"
l'ordine esisteva gia' e se ne legge l'esito, senza crearne un secondo.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from .broker import Account, BrokerError, Fill, Position

PAPER_URL = "https://paper-api.alpaca.markets"
DATA_URL = "https://data.alpaca.markets"


def _http(method: str, url: str, headers: dict, body: dict | None = None, timeout: float = 15.0) -> tuple[int, dict | list]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={**headers, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"message": raw[:200].decode(errors="replace")}


class AlpacaPaper:
    name = "alpaca-paper"

    def __init__(self, key: str | None = None, secret: str | None = None, http: Callable = _http,
                 symbol_map: Callable[[str], str] | None = None, wait_fill: float = 20.0):
        key, secret = key or os.environ.get("ALPACA_KEY"), secret or os.environ.get("ALPACA_SECRET")
        if not key or not secret:
            raise BrokerError("mancano ALPACA_KEY / ALPACA_SECRET")
        self.h = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self.http, self.wait_fill = http, wait_fill
        self.sym = symbol_map or (lambda s: f"{s}/USD")
        self._rev: dict[str, str] = {}

    def _call(self, method: str, path: str, body: dict | None = None, base: str = PAPER_URL):
        try:
            code, out = self.http(method, base + path, self.h, body)
        except Exception as e:                                  # rete: il chiamante decide se riprovare
            raise BrokerError(f"alpaca non raggiungibile: {type(e).__name__}") from e
        return code, out

    def account(self) -> Account:
        code, a = self._call("GET", "/v2/account")
        if code != 200:
            raise BrokerError(f"account: {code} {a.get('message', '')}")
        if a.get("trading_blocked") or a.get("account_blocked"):
            raise BrokerError("conto bloccato")
        return Account(float(a["equity"]), float(a["cash"]))

    def positions(self) -> dict[str, Position]:
        code, ps = self._call("GET", "/v2/positions")
        if code != 200:
            raise BrokerError(f"positions: {code}")
        out = {}
        for p in ps:
            s = p["symbol"]
            ours = self._rev.get(s) or self._rev.get(s.replace("USD", "/USD")) or s.replace("/USD", "").replace("USD", "")
            out[ours] = Position(float(p["qty"]) * (1 if p.get("side", "long") == "long" else -1), float(p["current_price"]))
        return out

    def prices(self, symbols: list[str]) -> dict[str, float]:
        if not symbols:
            return {}
        m = {self.sym(s): s for s in symbols}
        self._rev.update(m)
        q = urllib.parse.quote(",".join(m), safe=",")
        code, out = self._call("GET", f"/v1beta3/crypto/us/latest/trades?symbols={q}", base=DATA_URL)
        if code != 200:
            raise BrokerError(f"prices: {code}")
        return {m[k]: float(v["p"]) for k, v in out.get("trades", {}).items() if k in m}

    def _to_fill(self, client_id: str, o: dict) -> Fill:
        side = 1 if o.get("side") == "buy" else -1
        fq = float(o.get("filled_qty") or 0)
        st = o.get("status", "")
        status = ("filled" if st == "filled" else "partial" if fq > 0 else
                  "rejected" if st in ("rejected", "canceled", "expired") else "pending")
        return Fill(client_id, status, side * fq, float(o.get("filled_avg_price") or 0), 0.0, st)

    def lookup(self, client_id: str) -> Fill | None:
        code, o = self._call("GET", "/v2/orders:by_client_order_id?client_order_id=" + urllib.parse.quote(client_id))
        if code == 404:
            return None
        if code != 200:
            raise BrokerError(f"lookup: {code}")
        return self._to_fill(client_id, o)

    def submit(self, client_id: str, symbol: str, qty: float, ref_price: float) -> Fill:
        body = dict(symbol=self.sym(symbol), qty=f"{abs(qty):.8f}", side="buy" if qty > 0 else "sell", type="market",
                    time_in_force="gtc", client_order_id=client_id)
        self._rev[self.sym(symbol)] = symbol
        code, o = self._call("POST", "/v2/orders", body)
        if code == 422 and "unique" in str(o.get("message", "")).lower():
            f = self.lookup(client_id)
            if f:
                return f
        if code not in (200, 201):
            return Fill(client_id, "rejected", reason=f"{code} {str(o.get('message', ''))[:120]}")
        deadline = time.time() + self.wait_fill
        f = self._to_fill(client_id, o)
        while f.status == "pending" and time.time() < deadline:
            time.sleep(1.0)
            f = self.lookup(client_id) or f
        return f

    def flatten(self) -> list[Fill]:
        self._call("DELETE", "/v2/orders")
        code, out = self._call("DELETE", "/v2/positions?cancel_orders=true")
        if code not in (200, 207):
            raise BrokerError(f"flatten: {code}")
        return [Fill(f"KILL-{x.get('symbol', '?')}", "pending" if x.get("status") in (200, None) else "rejected") for x in (out or [])]
