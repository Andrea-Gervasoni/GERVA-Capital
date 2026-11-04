"""
Registro degli agenti e organigramma (brief <organigramma>).

Fonte di verita' della configurazione: agents/<id>/profile.yaml (+ prompt.md, memory.md),
versionati in git. Il DB tiene lo stato dinamico (stato, grado corrente) e la storia di carriera.
Tipi di scrivania:
  llm    agente con modello linguistico
  code   "automa": funzione deterministica (Scorekeeper, Budget Governor, Gateway, ...)
  open   posizione aperta: scrivania vuota nel portale, assunzione quando costo e valore la giustificano
"""
from __future__ import annotations

import glob
import os

import yaml

from . import db, events, paths
from . import settings as S
from .scorekeeper import GRADES


def _profile_files() -> list[str]:
    return sorted(glob.glob(os.path.join(paths.AGENTS, "*", "profile.yaml")))


def load_profiles() -> list[dict]:
    out = []
    for f in _profile_files():
        p = yaml.safe_load(open(f))
        p["_dir"] = os.path.dirname(f)
        out.append(p)
    return out


def sync() -> int:
    """Allinea il DB ai profile.yaml (al primo avvio e dopo modifiche versionate in git)."""
    n = 0
    for p in load_profiles():
        row = db.one("SELECT id FROM agents WHERE id=?", (p["id"],))
        vals = (p["name"], p["role"], p["dept"], int(p.get("grade", 0)), p.get("superior"),
                p.get("status", "attivo" if p.get("kind", "llm") != "open" else "posizione_aperta"),
                float(p.get("daily_budget_eur", 0.0)), p.get("room"), int(p.get("desk", 0)),
                p.get("kind", "llm"), db.dumps({k: v for k, v in p.items() if not k.startswith("_")}))
        if row:
            db.ex("UPDATE agents SET name=?,role=?,dept=?,grade=?,superior=?,status=?,daily_budget_eur=?,"
                  "room=?,desk=?,kind=?,profile=? WHERE id=?", vals + (p["id"],))
        else:
            db.ex("INSERT INTO agents(name,role,dept,grade,superior,status,daily_budget_eur,room,desk,kind,"
                  "profile,id,hired_ts) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", vals + (p["id"], db.now_iso()))
        n += 1
    return n


def get(agent_id: str) -> dict | None:
    import json
    r = db.one("SELECT * FROM agents WHERE id=?", (agent_id,))
    if r:
        r["profile"] = json.loads(r["profile"])
        r["grade_name"] = GRADES[r["grade"]]
    return r


def all_agents() -> list[dict]:
    import json
    rows = db.q("SELECT * FROM agents ORDER BY dept, grade DESC, id")
    for r in rows:
        r["profile"] = json.loads(r["profile"])
        r["grade_name"] = GRADES[r["grade"]]
    return rows


def subordinates(agent_id: str) -> list[str]:
    return [r["id"] for r in db.q("SELECT id FROM agents WHERE superior=? ORDER BY grade DESC", (agent_id,))]


def org_tree(root: str = "capo") -> dict:
    a = get(root)
    if not a:
        return {}
    return dict(id=a["id"], name=a["name"], role=a["role"], grade=a["grade_name"], kind=a["kind"],
                status=a["status"], children=[org_tree(c) for c in subordinates(root)])


def model_for(agent: dict, purpose: str = "") -> str:
    prof = agent.get("profile", {})
    if prof.get("provider") and prof["provider"] != "anthropic":
        return prof.get("model", prof["provider"])
    if purpose == "committee" and agent["id"] == "capo":
        return S.get("models.ceo_committee")
    if purpose == "deep_validation":
        return S.get("models.deep_validation")
    return (S.get("models.by_grade_map") or {})[str(agent["grade"])]


def path_of(agent_id: str, name: str) -> str:
    return os.path.join(paths.AGENTS, agent_id, name)


def memory(agent_id: str) -> str:
    p = path_of(agent_id, "memory.md")
    return open(p).read() if os.path.exists(p) else ""


def add_lesson(agent_id: str, lesson: str, date: str | None = None, max_lines: int = 40):
    """Talent Manager: aggiunge una regola appresa alla memoria (max ~40 righe, guida §9)."""
    p = path_of(agent_id, "memory.md")
    text = memory(agent_id) or "# Memoria\n\n## Regole apprese\n\n## Preferenze del superiore\n\n## Errori ricorrenti da evitare\n"
    line = f"- {date or db.today()}: {lesson.strip()}"
    if "## Regole apprese" in text:
        text = text.replace("## Regole apprese\n", f"## Regole apprese\n{line}\n", 1)
    else:
        text += f"\n{line}\n"
    lines = text.splitlines()
    if len(lines) > max_lines:          # compattazione minima: si tengono intestazioni e regole piu' recenti
        head = [l for l in lines if l.startswith("#")]
        body = [l for l in lines if not l.startswith("#")][: max_lines - len(head)]
        lines = head[:1] + body
    with open(p, "w") as f:
        f.write("\n".join(lines) + "\n")


def _write_profile(agent_id: str, **changes):
    p = path_of(agent_id, "profile.yaml")
    prof = yaml.safe_load(open(p))
    prof.update(changes)
    with open(p, "w") as f:
        yaml.safe_dump(prof, f, allow_unicode=True, sort_keys=False)


def change_grade(agent_id: str, new_grade: int, kind: str, reason: str):
    a = get(agent_id)
    if not 0 <= new_grade < len(GRADES):
        raise ValueError("grado fuori scala")
    db.ex("UPDATE agents SET grade=? WHERE id=?", (new_grade, agent_id))
    db.ex("INSERT INTO career(ts,agent_id,kind,from_grade,to_grade,reason) VALUES(?,?,?,?,?,?)",
          (db.now_iso(), agent_id, kind, a["grade"], new_grade, reason))
    _write_profile(agent_id, grade=new_grade)
    events.publish(f"career.{kind}", "talent", dict(agente=agent_id, da=GRADES[a["grade"]],
                                                  a=GRADES[new_grade], motivo=reason))


def set_status(agent_id: str, status: str, reason: str):
    db.ex("UPDATE agents SET status=? WHERE id=?", (status, agent_id))
    db.ex("INSERT INTO career(ts,agent_id,kind,from_grade,to_grade,reason) VALUES(?,?,?,?,?,?)",
          (db.now_iso(), agent_id, f"stato:{status}", None, None, reason))
    events.publish("career.status", "talent", dict(agente=agent_id, stato=status, motivo=reason))


def career(agent_id: str) -> list[dict]:
    return db.q("SELECT * FROM career WHERE agent_id=? ORDER BY id DESC", (agent_id,))
