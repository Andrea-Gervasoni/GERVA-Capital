"""
Posta del Capo: SOLO le grandi richieste (brief <autonomia>), niente altro arriva ad Andrea.

Categorie:
  1 passo verso soldi veri · 2 allentare un limite di rischio · 3 spesa oltre il tetto
  4 credenziali/servizi a pagamento · 5 azioni distruttive fuori dal progetto
  6 cambio di direzione dell'intera societa'
Ogni richiesta ha: titolo, perche', opzioni, raccomandazione, default sicuro.
Se Andrea non risponde vale il default sicuro e la societa' continua sul resto.
"""
from __future__ import annotations

import json

from . import db, events

CATEGORIES = {1: "Soldi veri", 2: "Limite di rischio", 3: "Budget", 4: "Credenziali",
              5: "Azione distruttiva", 6: "Cambio di direzione"}


def big_request(category: int, title: str, why: str, options: list[str], recommendation: str,
                safe_default: str, dedup_key: str | None = None) -> dict | None:
    if category not in CATEGORIES:
        raise ValueError("solo le sei categorie di grande richiesta arrivano ad Andrea")
    if not (title and why and options and recommendation and safe_default):
        raise ValueError("una grande richiesta deve avere titolo, perche', opzioni, raccomandazione, default")
    if dedup_key and db.one("SELECT id FROM mailbox WHERE dedup_key=?", (dedup_key,)):
        return None
    mid = db.ex("INSERT INTO mailbox(ts,category,title,why,options,recommendation,safe_default,status,dedup_key)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (db.now_iso(), category, title, why, db.dumps(options), recommendation, safe_default,
                 "aperta", dedup_key))
    events.publish("mailbox.new", "capo", dict(id=mid, title=title, categoria=CATEGORIES[category]))
    return dict(id=mid, title=title)


def items(status: str | None = None) -> list[dict]:
    rows = db.q("SELECT * FROM mailbox" + (" WHERE status=?" if status else "") + " ORDER BY id DESC",
                (status,) if status else ())
    for r in rows:
        r["options"] = json.loads(r["options"])
        r["categoria"] = CATEGORIES.get(r["category"], "?")
    return rows


def decide(mid: int, choice: str, cap) -> dict:
    """Solo Andrea (capability del portale). 'Rimanda' lascia valere il default sicuro."""
    from .settings import AndreaCapability, SettingsPermissionError
    if not isinstance(cap, AndreaCapability):
        raise SettingsPermissionError("solo Andrea risponde alla Posta del Capo")
    status = "rimandata" if choice == "__rimanda__" else "decisa"
    db.ex("UPDATE mailbox SET status=?, choice=?, decided_ts=? WHERE id=?",
          (status, None if status == "rimandata" else choice, db.now_iso(), mid))
    events.publish("mailbox.decided", "andrea", dict(id=mid, scelta=choice, stato=status))
    return dict(id=mid, status=status)
