"""
Registro durevole del sistema live (SQLite in modalita' WAL).

E' l'unica memoria che sopravvive a un crash: stato del rischio, massimo storico, intenzioni d'ordine
scritte PRIMA dell'invio al broker, eseguiti, valore del conto, battiti dei componenti, eventi.

Regole:
  * un solo processo scrive (il ciclo live); la dashboard legge il file snapshot, non il database;
  * ogni scrittura e' una transazione; `busy_timeout` evita gli errori di blocco sotto carico;
  * l'intenzione d'ordine ha chiave primaria = identificativo del cliente: reinviare lo stesso ordine
    dopo un riavvio e' impossibile per costruzione.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL, ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS nav (ts REAL PRIMARY KEY, equity REAL NOT NULL, cash REAL NOT NULL, gross REAL, net REAL);
CREATE TABLE IF NOT EXISTS orders (
    client_id TEXT PRIMARY KEY, ts REAL NOT NULL, cycle TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL,
    qty REAL NOT NULL, ref_price REAL NOT NULL, venue TEXT, strategy TEXT,
    status TEXT NOT NULL,            -- intent | filled | partial | rejected | cancelled | unknown
    fill_qty REAL DEFAULT 0, fill_price REAL, fee REAL DEFAULT 0, reason TEXT DEFAULT '', updated REAL);
CREATE INDEX IF NOT EXISTS orders_ts ON orders(ts);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, level TEXT NOT NULL,
    component TEXT NOT NULL, msg TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS events_ts ON events(ts);
CREATE TABLE IF NOT EXISTS heartbeats (component TEXT PRIMARY KEY, ts REAL NOT NULL, status TEXT NOT NULL,
    latency_ms REAL, detail TEXT DEFAULT '', last_ok REAL);
CREATE TABLE IF NOT EXISTS strat_nav (ts REAL NOT NULL, strategy TEXT NOT NULL, ret REAL NOT NULL,
    PRIMARY KEY (ts, strategy));
"""


class Journal:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")          # un ordine registrato deve sopravvivere a un calo di corrente
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.executescript(SCHEMA)

    @contextmanager
    def tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    # ---- stato ------------------------------------------------------------
    def get(self, k: str, default=None):
        r = self.db.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return json.loads(r["v"]) if r else default

    def set(self, k: str, v) -> None:
        with self.tx() as db:
            db.execute("INSERT INTO kv(k,v,ts) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v, ts=excluded.ts",
                       (k, json.dumps(v), time.time()))

    # ---- valore del conto -------------------------------------------------
    def record_nav(self, equity: float, cash: float, gross: float, net: float, ts: float | None = None) -> None:
        with self.tx() as db:
            db.execute("INSERT OR REPLACE INTO nav(ts,equity,cash,gross,net) VALUES(?,?,?,?,?)",
                       (ts or time.time(), equity, cash, gross, net))

    def nav_history(self, since: float = 0.0) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM nav WHERE ts>=? ORDER BY ts", (since,)).fetchall()

    # ---- ordini -----------------------------------------------------------
    def intent(self, client_id: str, cycle: str, symbol: str, side: str, qty: float, ref_price: float,
               venue: str, strategy: str) -> bool:
        """Scrive l'intenzione PRIMA dell'invio. False se quell'ordine esiste gia' (non va reinviato)."""
        try:
            with self.tx() as db:
                db.execute("INSERT INTO orders(client_id,ts,cycle,symbol,side,qty,ref_price,venue,strategy,status,updated) "
                           "VALUES(?,?,?,?,?,?,?,?,?,'intent',?)",
                           (client_id, time.time(), cycle, symbol, side, qty, ref_price, venue, strategy, time.time()))
            return True
        except sqlite3.IntegrityError:
            return False

    def resolve(self, client_id: str, status: str, fill_qty: float = 0.0, fill_price: float | None = None,
                fee: float = 0.0, reason: str = "") -> None:
        with self.tx() as db:
            db.execute("UPDATE orders SET status=?, fill_qty=?, fill_price=?, fee=?, reason=?, updated=? WHERE client_id=?",
                       (status, fill_qty, fill_price, fee, reason, time.time(), client_id))

    def open_intents(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM orders WHERE status='intent' ORDER BY ts").fetchall()

    def orders(self, limit: int = 50) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM orders ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()

    def order(self, client_id: str):
        return self.db.execute("SELECT * FROM orders WHERE client_id=?", (client_id,)).fetchone()

    # ---- eventi e battiti -------------------------------------------------
    def event(self, level: str, component: str, msg: str) -> None:
        with self.tx() as db:
            db.execute("INSERT INTO events(ts,level,component,msg) VALUES(?,?,?,?)", (time.time(), level, component, msg[:2000]))

    def events(self, limit: int = 50, since: float = 0.0, level: str | None = None) -> list[sqlite3.Row]:
        q, a = "SELECT * FROM events WHERE ts>=?", [since]
        if level:
            q += " AND level=?"
            a.append(level)
        return self.db.execute(q + " ORDER BY ts DESC LIMIT ?", (*a, limit)).fetchall()

    def beat(self, component: str, ok: bool, latency_ms: float | None = None, detail: str = "",
             degraded: bool = False) -> None:
        now = time.time()
        status = "ok" if ok and not degraded else ("degraded" if ok else "down")
        with self.tx() as db:
            db.execute("INSERT INTO heartbeats(component,ts,status,latency_ms,detail,last_ok) VALUES(?,?,?,?,?,?) "
                       "ON CONFLICT(component) DO UPDATE SET ts=excluded.ts, status=excluded.status, "
                       "latency_ms=excluded.latency_ms, detail=excluded.detail, "
                       "last_ok=CASE WHEN excluded.status='down' THEN heartbeats.last_ok ELSE excluded.ts END",
                       (component, now, status, latency_ms, detail[:500], now if ok else None))

    def heartbeats(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM heartbeats ORDER BY component").fetchall()

    def record_strategy_returns(self, ts: float, rets: dict[str, float]) -> None:
        with self.tx() as db:
            for k, v in rets.items():
                db.execute("INSERT OR REPLACE INTO strat_nav(ts,strategy,ret) VALUES(?,?,?)", (ts, k, float(v)))

    def strategy_returns(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM strat_nav ORDER BY ts").fetchall()

    def close(self) -> None:
        self.db.close()
