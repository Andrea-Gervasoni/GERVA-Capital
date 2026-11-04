"""
Albero dei compiti: un ordine di Andrea al Capo diventa un albero che scende ai manager,
ai senior e agli analisti (le cartelline che viaggiano nel portale) e risale con i risultati.
"""
from __future__ import annotations

import json

from . import db, events


def new_command(text: str) -> int:
    cid = db.ex("INSERT INTO commands(ts,text,status) VALUES(?,?,?)", (db.now_iso(), text, "ricevuto"))
    events.publish("command.received", "andrea", dict(id=cid, testo=text))
    return cid


def create(order_id: int | None, parent_id: int | None, assignee: str, assigner: str, title: str) -> int:
    tid = db.ex("INSERT INTO tasks(order_id,parent_id,ts,assignee,assigner,title,status) VALUES(?,?,?,?,?,?,?)",
                (order_id, parent_id, db.now_iso(), assignee, assigner, title, "assegnato"))
    events.publish("task.handoff", assigner, dict(task=tid, da=assigner, a=assignee, titolo=title, ordine=order_id))
    return tid


def complete(tid: int, result: dict | str, status: str = "fatto"):
    db.ex("UPDATE tasks SET status=?, result=?, done_ts=? WHERE id=?",
          (status, result if isinstance(result, str) else db.dumps(result), db.now_iso(), tid))
    t = db.one("SELECT * FROM tasks WHERE id=?", (tid,))
    events.publish("task.done", t["assignee"], dict(task=tid, a=t["assigner"], stato=status, ordine=t["order_id"]))


def tree(order_id: int) -> dict:
    cmd = db.one("SELECT * FROM commands WHERE id=?", (order_id,))
    rows = db.q("SELECT * FROM tasks WHERE order_id=? ORDER BY id", (order_id,))
    for r in rows:
        try:
            r["result"] = json.loads(r["result"]) if r["result"] else None
        except json.JSONDecodeError:
            pass
    by_parent: dict = {}
    for r in rows:
        by_parent.setdefault(r["parent_id"], []).append(r)

    def build(pid):
        return [dict(r, children=build(r["id"])) for r in by_parent.get(pid, [])]

    return dict(ordine=cmd, compiti=build(None))


def commands(limit: int = 20) -> list[dict]:
    return db.q("SELECT * FROM commands ORDER BY id DESC LIMIT ?", (limit,))
