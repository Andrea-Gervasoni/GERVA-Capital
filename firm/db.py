"""
Database SQLite della societa'. Uno schema unico per tutte le milestone.

Le tabelle 'storiche' (audit_log, events, forecasts nella parte gia' registrata, fills,
gc_ledger, llm_calls) sono append-only: i trigger fanno fallire qualunque UPDATE o DELETE.
Non e' una convenzione: e' un vincolo del database (regola inviolabile 11).
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time

from . import paths

SCHEMA = r"""
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS audit_log (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
  payload TEXT NOT NULL, model TEXT, cost_eur REAL DEFAULT 0,
  prev_hash TEXT NOT NULL, hash TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, kind TEXT NOT NULL, actor TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_events_actor ON events(actor, id);
CREATE INDEX IF NOT EXISTS ix_events_kind ON events(kind, id);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_ts TEXT, updated_by TEXT
);
-- stato operativo scritto dal codice deterministico (es. sciopero automatico per budget)
CREATE TABLE IF NOT EXISTS runtime (
  key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_ts TEXT
);

CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY, name TEXT, role TEXT, dept TEXT, grade INTEGER, superior TEXT,
  status TEXT, daily_budget_eur REAL, room TEXT, desk INTEGER, kind TEXT,
  profile TEXT, hired_ts TEXT
);
CREATE TABLE IF NOT EXISTS career (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, agent_id TEXT, kind TEXT,
  from_grade INTEGER, to_grade INTEGER, reason TEXT
);

CREATE TABLE IF NOT EXISTS llm_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, day TEXT, agent_id TEXT, dept TEXT,
  provider TEXT, model TEXT, input_tokens INTEGER, output_tokens INTEGER,
  cache_read INTEGER, cache_write INTEGER, cost_usd REAL, cost_eur REAL, ok INTEGER,
  purpose TEXT
);
CREATE INDEX IF NOT EXISTS ix_llm_day ON llm_calls(day);

CREATE TABLE IF NOT EXISTS trials (
  id TEXT PRIMARY KEY, ts TEXT, agent_id TEXT, strategy_id TEXT, family TEXT,
  params TEXT, params_hash TEXT, hypothesis TEXT, status TEXT,
  sharpe_daily REAL, n_obs INTEGER, skew REAL, kurt REAL, result TEXT, data_fingerprint TEXT
);

CREATE TABLE IF NOT EXISTS forecasts (
  id TEXT PRIMARY KEY, ts TEXT, agent_id TEXT, statement TEXT, prob REAL,
  deadline TEXT, criterion TEXT, source TEXT, hash TEXT,
  outcome INTEGER, resolved_ts TEXT, resolved_by TEXT, canary INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS evaluations (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, agent_id TEXT, metric TEXT,
  value REAL, weight REAL DEFAULT 1, kind TEXT, details TEXT
);
CREATE INDEX IF NOT EXISTS ix_eval_agent ON evaluations(agent_id, metric);
CREATE TABLE IF NOT EXISTS peer_reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, reviewer TEXT, reviewee TEXT,
  rubric TEXT, score REAL, defect TEXT
);
CREATE TABLE IF NOT EXISTS postmortems (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, agent_id TEXT, severity INTEGER,
  what TEXT, why TEXT, change TEXT, lesson TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER, parent_id INTEGER,
  ts TEXT, assignee TEXT, assigner TEXT, title TEXT, status TEXT, result TEXT, done_ts TEXT
);
CREATE TABLE IF NOT EXISTS commands (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, text TEXT, status TEXT, answer TEXT
);
CREATE TABLE IF NOT EXISTS mailbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, category INTEGER, title TEXT, why TEXT,
  options TEXT, recommendation TEXT, safe_default TEXT, status TEXT, choice TEXT,
  decided_ts TEXT, dedup_key TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS news (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, title TEXT, url TEXT, domain TEXT,
  published TEXT, summary TEXT, status TEXT, second_url TEXT, checked_by TEXT, agent_id TEXT,
  tags TEXT
);

CREATE TABLE IF NOT EXISTS research (
  id TEXT PRIMARY KEY, ts TEXT, owner TEXT, title TEXT, stage TEXT, trial_id TEXT,
  gate TEXT, validation TEXT, decision TEXT, updated_ts TEXT
);

CREATE TABLE IF NOT EXISTS pods (
  id TEXT PRIMARY KEY, name TEXT, head TEXT, philosophy TEXT, benchmark TEXT,
  capital_frac REAL, status TEXT, hwm REAL, created_ts TEXT, strategy TEXT
);
CREATE TABLE IF NOT EXISTS gateway_orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, pod TEXT, agent_id TEXT, instrument TEXT,
  side TEXT, qty REAL, ref_price REAL, reason TEXT, horizon TEXT, status TEXT, reject TEXT
);
CREATE TABLE IF NOT EXISTS fills (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, order_id INTEGER, pod TEXT,
  instrument TEXT, side TEXT, qty REAL, price REAL, fee REAL, venue TEXT, model_cost REAL
);
CREATE TABLE IF NOT EXISTS nav_marks (
  id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT, pod TEXT, nav REAL, capital REAL,
  gross REAL, UNIQUE(day, pod)
);
CREATE TABLE IF NOT EXISTS meetings (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, kind TEXT, title TEXT, reason TEXT, participants TEXT,
  options TEXT, status TEXT, decision TEXT, transcript TEXT, resolve_after TEXT, outcome TEXT, context TEXT
);
CREATE TABLE IF NOT EXISTS gc_ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, agent_id TEXT, pod TEXT,
  amount REAL, kind TEXT, memo TEXT
);
"""

APPEND_ONLY = ["audit_log", "events", "llm_calls", "fills", "gc_ledger", "career", "postmortems"]

TRIGGERS = "\n".join(
    f"""CREATE TRIGGER IF NOT EXISTS {t}_no_update BEFORE UPDATE ON {t}
        BEGIN SELECT RAISE(ABORT, '{t} e'' append-only'); END;
        CREATE TRIGGER IF NOT EXISTS {t}_no_delete BEFORE DELETE ON {t}
        BEGIN SELECT RAISE(ABORT, '{t} e'' append-only'); END;"""
    for t in APPEND_ONLY
) + """
-- una previsione registrata non si puo' piu' cambiare: si puo' solo risolvere UNA volta
CREATE TRIGGER IF NOT EXISTS forecasts_frozen BEFORE UPDATE ON forecasts
BEGIN
  SELECT CASE
    WHEN NEW.statement IS NOT OLD.statement OR NEW.prob IS NOT OLD.prob OR NEW.deadline IS NOT OLD.deadline
      OR NEW.criterion IS NOT OLD.criterion OR NEW.hash IS NOT OLD.hash OR NEW.ts IS NOT OLD.ts
      OR NEW.agent_id IS NOT OLD.agent_id
    THEN RAISE(ABORT, 'previsione congelata: si puo'' solo risolvere')
    WHEN OLD.outcome IS NOT NULL THEN RAISE(ABORT, 'previsione gia'' risolta')
  END;
END;
CREATE TRIGGER IF NOT EXISTS forecasts_no_delete BEFORE DELETE ON forecasts
BEGIN SELECT RAISE(ABORT, 'forecasts e'' append-only'); END;
-- una prova registrata non sparisce (il contatore del Deflated Sharpe ne dipende)
CREATE TRIGGER IF NOT EXISTS trials_no_delete BEFORE DELETE ON trials
BEGIN SELECT RAISE(ABORT, 'trials non si cancellano'); END;
"""

_local = threading.local()


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


def today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def connect(path: str | None = None) -> sqlite3.Connection:
    """Connessione per thread (SQLite non condivide connessioni tra thread)."""
    path = path or paths.DB_PATH
    key = f"conn_{path}"
    conn = getattr(_local, key, None)
    if conn is None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.executescript(TRIGGERS)
        setattr(_local, key, conn)
    return conn


def reset_connection_cache():
    for k in list(vars(_local)):
        try:
            getattr(_local, k).close()
        except Exception:
            pass
        delattr(_local, k)


def q(sql: str, args=(), conn=None) -> list[dict]:
    return [dict(r) for r in (conn or connect()).execute(sql, args).fetchall()]


def one(sql: str, args=(), conn=None) -> dict | None:
    r = (conn or connect()).execute(sql, args).fetchone()
    return dict(r) if r else None


def ex(sql: str, args=(), conn=None) -> int:
    cur = (conn or connect()).execute(sql, args)
    return cur.lastrowid


def dumps(x) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)


def runtime_get(key: str, default=None):
    r = one("SELECT value FROM runtime WHERE key=?", (key,))
    return json.loads(r["value"]) if r else default


def runtime_set(key: str, value):
    ex("INSERT INTO runtime(key,value,updated_ts) VALUES(?,?,?) "
       "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_ts=excluded.updated_ts",
       (key, dumps(value), now_iso()))
