"""
Bus eventi. Ogni evento e' una riga append-only in `events` e una voce nell'audit log.
Il portale legge gli eventi nuovi (id > ultimo visto) e li spinge via WebSocket: cosi' il
battito, gli agenti e il portale possono girare in processi diversi senza un broker.

Tipi di evento usati (prefisso = reparto/area):
  agent.status      cosa sta facendo un agente (scrive, pensa, dorme, riunione, cammina)
  task.created / task.done / task.handoff   delega lungo la catena (cartelline nel portale)
  news.verified / news.rejected             Redazione
  risk.alert / risk.kill / risk.kill_recommended
  budget.*          Budget Governor
  trial.*           registro delle prove
  career.*          promozioni, retrocessioni, licenziamenti
  postmortem        errori materiali
  gateway.accepted / gateway.rejected / gateway.fill
  mailbox.new       grande richiesta per Andrea
  settings.changed  modifica di Andrea
"""
from __future__ import annotations

import json
from typing import Callable

from . import db, audit
from llm import redact

_subscribers: list[Callable[[dict], None]] = []


def subscribe(fn: Callable[[dict], None]):
    _subscribers.append(fn)


def publish(kind: str, actor: str, payload: dict | None = None, audit_it: bool = True) -> dict:
    payload = redact.obj(payload or {})
    ev = dict(ts=db.now_iso(), kind=kind, actor=actor, payload=payload)
    ev["id"] = db.ex("INSERT INTO events(ts,kind,actor,payload) VALUES(?,?,?,?)",
                     (ev["ts"], kind, actor, db.dumps(payload)))
    if audit_it:
        audit.log(actor, f"event:{kind}", payload)
    for fn in list(_subscribers):
        try:
            fn(ev)
        except Exception:
            pass
    return ev


def since(last_id: int, limit: int = 200) -> list[dict]:
    rows = db.q("SELECT * FROM events WHERE id>? ORDER BY id LIMIT ?", (last_id, limit))
    for r in rows:
        r["payload"] = json.loads(r["payload"])
    return rows


def recent(actor: str | None = None, kinds: tuple[str, ...] | None = None, limit: int = 10) -> list[dict]:
    sql, args = "SELECT * FROM events WHERE 1=1", []
    if actor:
        sql += " AND actor=?"
        args.append(actor)
    if kinds:
        sql += " AND (" + " OR ".join("kind LIKE ?" for _ in kinds) + ")"
        args += [k.replace("*", "%") for k in kinds]
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    rows = db.q(sql, tuple(args))
    for r in rows:
        r["payload"] = json.loads(r["payload"])
    return rows
