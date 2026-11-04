"""
Compensi: tutti vogliono guadagnare, ma si guadagna solo cio' che regge alla verifica.

  * stipendio settimanale in GC per grado (pagato la domenica);
  * bonus SEMPRE differito: matura dopo 4 settimane (kind='differito' finche' non matura);
  * clawback: un errore grave (post-mortem con gravita' >= 4), una manipolazione scoperta o la
    chiusura del pod per drawdown azzerano il differito dell'agente.
Perche': nelle multi-manager vere il bonus differito con clawback e' cio' che impedisce a chi e'
affamato di rendimento di prendere rischi nascosti. Senza, l'avidita' fa saltare il conto; con,
la rende allineata all'alpha vero (docs/research/firms.md §1, §3).

Le ricompense delle riunioni usano una regola di punteggio PROPRIA (Brier): l'agente massimizza
i GC attesi solo dichiarando la probabilita' in cui crede davvero.
"""
from __future__ import annotations

import datetime as dt
import json

from . import db, events, economy

BASE_WEEKLY_GC = [5, 8, 12, 18, 25, 40, 60]       # per grado: Stagista ... Head
VEST_DAYS = 28


def award_bonus(agent_id: str, amount: float, reason: str, pod: str | None = None, today: str | None = None) -> float:
    if amount <= 0:
        return 0.0
    vest = (dt.date.fromisoformat(today or db.today()) + dt.timedelta(days=VEST_DAYS)).isoformat()
    db.ex("INSERT INTO gc_ledger(ts,agent_id,pod,amount,kind,memo) VALUES(?,?,?,?,?,?)",
          (db.now_iso(), agent_id, pod, float(amount), "differito", json.dumps(dict(matura=vest, motivo=reason))))
    events.publish("gc.bonus", "economia", dict(agente=agent_id, gc=round(amount, 1), matura=vest, motivo=reason))
    return amount


def vest(today: str | None = None) -> int:
    """Fa maturare i bonus differiti scaduti (una voce negativa sul differito, una positiva sul saldo)."""
    today = today or db.today()
    n = 0
    for r in db.q("SELECT * FROM gc_ledger WHERE kind='differito' AND amount>0"):
        meta = json.loads(r["memo"] or "{}")
        if meta.get("matura", "9999") > today:
            continue
        if db.one("SELECT id FROM gc_ledger WHERE kind='differito' AND memo LIKE ?", (f'%"chiude": {r["id"]},%',)):
            continue
        db.ex("INSERT INTO gc_ledger(ts,agent_id,pod,amount,kind,memo) VALUES(?,?,?,?,?,?)",
              (db.now_iso(), r["agent_id"], r["pod"], -r["amount"], "differito", json.dumps(dict(chiude=r["id"], esito="maturato"))))
        db.ex("INSERT INTO gc_ledger(ts,agent_id,pod,amount,kind,memo) VALUES(?,?,?,?,?,?)",
              (db.now_iso(), r["agent_id"], r["pod"], r["amount"], "maturato", meta.get("motivo", "")))
        n += 1
    return n


def clawback(agent_id: str, reason: str) -> float:
    open_items = db.q("SELECT * FROM gc_ledger WHERE agent_id=? AND kind='differito' AND amount>0", (agent_id,))
    total = 0.0
    for r in open_items:
        if db.one("SELECT id FROM gc_ledger WHERE kind='differito' AND memo LIKE ?", (f'%"chiude": {r["id"]},%',)):
            continue
        db.ex("INSERT INTO gc_ledger(ts,agent_id,pod,amount,kind,memo) VALUES(?,?,?,?,?,?)",
              (db.now_iso(), agent_id, r["pod"], -r["amount"], "differito", json.dumps(dict(chiude=r["id"], esito="clawback", motivo=reason))))
        total += r["amount"]
    if total:
        events.publish("career.clawback", "talent", dict(agente=agent_id, gc=round(total, 1), motivo=reason))
    return total


def pay_salaries(today: str | None = None) -> int:
    today = today or db.today()
    key = f"salary:{dt.date.fromisoformat(today).isocalendar()[:2]}"
    if db.runtime_get(key):
        return 0
    n = 0
    for a in db.q("SELECT id, grade FROM agents WHERE kind='llm' AND status IN ('attivo','in_prova')"):
        economy.gc_move(a["id"], BASE_WEEKLY_GC[a["grade"]], "stipendio", f"stipendio settimanale ({today})")
        n += 1
    db.runtime_set(key, today)
    return n


def proper_reward(prob: float, correct: bool, scale: float = 10.0) -> float:
    """Ricompensa con regola di Brier riscalata: scale * (1 - 4 (p - o)^2), in [-3 scale, +scale].
    Zero per chi dichiara 50% (tirare a indovinare non paga), +scale per chi ha ragione con certezza,
    -3 scale per chi sbaglia con certezza. E' propria (trasformazione affine del Brier): il valore
    atteso e' massimo dichiarando la probabilita' in cui si crede davvero."""
    o = 1.0 if correct else 0.0
    return scale * (1 - 4 * (prob - o) ** 2)


def pay_reward(agent_id: str, amount: float, reason: str):
    if amount >= 0:
        award_bonus(agent_id, amount, reason)
    else:
        economy.gc_move(agent_id, amount, "penale", reason)
