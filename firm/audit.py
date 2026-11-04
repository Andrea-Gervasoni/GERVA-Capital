"""
Audit log append-only con catena di hash (regola inviolabile 11).

  hash_i = SHA256(prev_hash || seq || ts || actor || action || payload || model || cost)

Modificare una riga qualsiasi rompe tutti gli hash successivi: verify() lo trova.
UPDATE e DELETE sono comunque bloccati dai trigger del database (firm/db.py).
Il payload passa dal filtro dei segreti PRIMA di essere scritto.
"""
from __future__ import annotations

import hashlib
import threading

from . import db
from llm import redact

GENESIS = "0" * 64
_lock = threading.Lock()


def _digest(prev: str, seq: int, ts: str, actor: str, action: str, payload: str,
            model: str | None, cost: float) -> str:
    h = hashlib.sha256()
    for part in (prev, str(seq), ts, actor, action, payload, model or "", f"{cost:.8f}"):
        h.update(part.encode())
        h.update(b"\x1f")
    return h.hexdigest()


def log(actor: str, action: str, payload: dict | None = None, model: str | None = None,
        cost_eur: float = 0.0) -> dict:
    payload_s = db.dumps(redact.obj(payload or {}))
    ts = db.now_iso()
    with _lock:
        conn = db.connect()
        conn.execute("BEGIN IMMEDIATE")
        try:
            last = conn.execute("SELECT seq, hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
            prev, seq = (last["hash"], last["seq"] + 1) if last else (GENESIS, 1)
            h = _digest(prev, seq, ts, actor, action, payload_s, model, cost_eur)
            conn.execute("INSERT INTO audit_log(seq,ts,actor,action,payload,model,cost_eur,prev_hash,hash)"
                         " VALUES(?,?,?,?,?,?,?,?,?)",
                         (seq, ts, actor, action, payload_s, model, cost_eur, prev, h))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return dict(seq=seq, hash=h)


def verify(conn=None) -> dict:
    """Ricalcola l'intera catena. Ritorna {'ok', 'n', 'prima_rottura'}."""
    rows = db.q("SELECT * FROM audit_log ORDER BY seq", conn=conn)
    prev = GENESIS
    for i, r in enumerate(rows, start=1):
        h = _digest(prev, r["seq"], r["ts"], r["actor"], r["action"], r["payload"], r["model"],
                    r["cost_eur"] or 0.0)
        if r["seq"] != i or r["prev_hash"] != prev or r["hash"] != h:
            return dict(ok=False, n=len(rows), prima_rottura=r["seq"])
        prev = h
    return dict(ok=True, n=len(rows), prima_rottura=None, testa=prev)
