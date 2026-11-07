"""
La Costituzione: cosa il comitato puo' cambiare votando, e fino a dove.

Gli agenti propongono, il comitato vota (riunione con voto pesato per precisione storica), il codice applica. I limiti qui sotto non
sono una prudenza imposta: sono i limiti FISICI (pesi tra 0 e 100% del conto, la leva che il broker accetta) e servono a non scrivere
valori senza senso. La scelta dentro questi limiti e' del comitato.

Cosa NON si cambia votando (resta di Andrea): il solo conto paper (firm.mode), le credenziali, il budget in soldi veri, i limiti di rischio
del file risk_limits.yaml (freno del -35%, ordine massimo) e ogni passo verso soldi veri.

Ogni cambiamento: scritto in rules_log (valore vecchio e nuovo, chi, quale idea), pubblicato come evento, nell'audit, ANNULLABILE
(`firm.py regole --annulla ID`). Per il motore (GERVA-Q) si modifica una costante di config.py con copia di sicurezza e controllo di sintassi.
"""
from __future__ import annotations

import json
import os
import re
import shutil

from . import audit, db, events
from . import settings as S

RULES = {                                  # impostazione -> (minimo, massimo): solo limiti "fisici", la scelta e' del comitato
    "desk.max_name_frac": (0.01, 0.25), "desk.max_total_frac": (0.05, 1.0),
    "ideas.max_name_frac": (0.005, 0.25), "ideas.max_total_frac": (0.02, 1.0), "ideas.horizon_days": (3, 120),
    "ideas.agents_per_day": (1, 20), "algo.crypto_tsmom.on": (0, 1), "algo.crypto_tsmom.capital_frac": (0, 1),
    "algo.spy_intraday_momentum.on": (0, 1), "algo.spy_intraday_momentum.capital_frac": (0, 1), "lessons.agents_per_day": (1, 30), "free.cycle_minutes": (1, 1440), "free.agents_per_cycle": (1, 20), "free.max_intents": (1, 200),
    "free.monitor_seconds": (5, 3600), "free.riesame_loss_frac": (0.005, 1.0), "rules.review_days": (1, 365), "ideas.committee_per_day": (1, 10), "pace.meeting_every_days": (1, 30),
    "volmgmt.lo": (0.1, 1.0), "volmgmt.hi": (1.0, 3.0),
    "signals.risk_frac": (0.001, 0.05), "signals.max_frac": (0.005, 0.25), "signals.max_total_frac": (0.02, 1.0),
    "crypto.venue_max_frac": (0.0, 1.0), "expectations.haircut": (0.1, 1.0),
}
ENGINE = {                                 # costante di GERVA-Q (config.py) -> (minimo, massimo)
    "SCALE_K": (0.5, 4.0), "SCALE_CAP": (0.5, 3.0), "SCALE_HARD_CAP": (1.0, 3.0),   # oltre ~2x lordo sulle azioni e' il broker a rifiutare gli ordini
    "OVERLAY_MAX_NAME": (0.01, 0.25), "OVERLAY_MAX_TOTAL": (0.05, 1.0),
    "VOL_MULT_MIN": (0.1, 1.0), "VOL_MULT_MAX": (1.0, 3.0), "TURNOVER_MIN": (0.05, 1.0),
}


def bounds(kind: str, key: str) -> tuple[float, float] | None:
    return (ENGINE if kind == "motore" else RULES).get(key)


def check(kind: str, key: str, value) -> tuple[bool, str]:
    b = bounds(kind, key)
    if b is None:
        return False, f"'{key}' non e' nella Costituzione: non si cambia votando"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False, "valore non numerico"
    if v != v or not (b[0] <= v <= b[1]):
        return False, f"{key} deve stare tra {b[0]} e {b[1]}"
    return True, ""


def current(kind: str, key: str):
    return _engine_read(key) if kind == "motore" else S.get(key)


def catalog() -> dict:
    """Cio' che gli agenti possono proporre, con valore attuale e limiti (e' quello che vedono nel prompt)."""
    out = {}
    for k, (lo, hi) in RULES.items():
        out[f"regola:{k}"] = dict(attuale=S.get(k), minimo=lo, massimo=hi)
    for k, (lo, hi) in ENGINE.items():
        out[f"motore:{k}"] = dict(attuale=_engine_read(k), minimo=lo, massimo=hi)
    return out


# ---------------------------------------------------------------------------------------------- applicazione
def _recent_changes(key: str, days: int) -> int:
    rows = db.q("SELECT ts FROM rules_log WHERE key=? AND status='applicata' ORDER BY id DESC LIMIT 1", (key,))
    if not rows:
        return 0
    import datetime as dt
    t = dt.datetime.fromisoformat(rows[0]["ts"].replace("Z", "+00:00"))
    return int((dt.datetime.now(dt.timezone.utc) - t).days < days)


def _today_count() -> int:
    return len(db.q("SELECT id FROM rules_log WHERE substr(ts,1,10)=? AND status='applicata'", (db.now_iso()[:10],)))


def _gq_dir() -> str:
    return os.path.expanduser(os.environ.get("GERVA_Q_PATH") or "~/Documents/GERVA-Q")


def _engine_read(key: str):
    p = os.path.join(_gq_dir(), "config.py")
    try:
        m = re.search(rf"^{re.escape(key)}\s*=\s*([0-9.]+)", open(p).read(), re.M)
        return float(m.group(1)) if m else None
    except OSError:
        return None


def _engine_write(key: str, value: float) -> None:
    p = os.path.join(_gq_dir(), "config.py")
    src = open(p).read()
    rx = re.compile(rf"^({re.escape(key)}\s*=\s*)[0-9.]+", re.M)
    if not rx.search(src):
        raise KeyError(f"{key} non esiste in config.py di GERVA-Q")
    new = rx.sub(lambda m: f"{m.group(1)}{value}", src, count=1)
    compile(new, "config.py", "exec")
    bdir = os.path.join(_gq_dir(), "backups", f"voto-{db.now_iso().replace(':', '').replace('-', '')}")
    os.makedirs(bdir, exist_ok=True)
    shutil.copy2(p, os.path.join(bdir, "config.py"))
    tmp = p + ".tmp"
    open(tmp, "w").write(new)
    os.replace(tmp, p)


def apply(kind: str, key: str, value, who: str, idea: int | None = None) -> dict:
    """kind: 'regola' (impostazione) o 'motore' (costante di GERVA-Q)."""
    if not S.get("rules.enabled", True):
        return dict(ok=False, motivo="le regole votate sono spente (rules.enabled)")
    ok, why = check(kind, key, value)
    if not ok:
        return dict(ok=False, motivo=why)
    cd, mx = int(S.get("rules.cooldown_days", 0)), int(S.get("rules.max_per_day", 0))      # 0 = nessun limite: una regola si puo' riportare in consiglio quando si vuole
    if cd > 0 and _recent_changes(f"{kind}:{key}", cd):
        return dict(ok=False, motivo="questa regola e' stata cambiata da poco: si aspetta")
    if mx > 0 and _today_count() >= mx:
        return dict(ok=False, motivo="troppe regole cambiate oggi")
    old = current(kind, key)
    v = float(value)
    if kind == "motore":
        try:
            _engine_write(key, v)
        except Exception as e:
            return dict(ok=False, motivo=f"GERVA-Q non modificato: {str(e)[:120]}")
    else:
        v = type(S.get(key))(v) if isinstance(S.get(key), (int, float)) and not isinstance(S.get(key), bool) else v
        db.ex("INSERT INTO settings(key,value,updated_ts,updated_by) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
              "updated_ts=excluded.updated_ts, updated_by=excluded.updated_by", (key, db.dumps(v), db.now_iso(), who))
    rid = db.ex("INSERT INTO rules_log(ts,kind,key,old,new,who,idea,status) VALUES(?,?,?,?,?,?,?,?)",
                (db.now_iso(), kind, f"{kind}:{key}", db.dumps(old), db.dumps(v), who, idea, "applicata"))
    audit.log("comitato", "rule.applied", dict(id=rid, tipo=kind, chiave=key, vecchio=old, nuovo=v, chi=who))
    events.publish("rule.applied", "comitato", dict(id=rid, tipo=kind, chiave=key, vecchio=old, nuovo=v))
    return dict(ok=True, id=rid, vecchio=old, nuovo=v)


def revert(rule_id: int, who: str = "andrea") -> dict:
    r = db.one("SELECT * FROM rules_log WHERE id=?", (rule_id,))
    if not r or r["status"] != "applicata":
        return dict(ok=False, motivo="regola non trovata o gia' annullata")
    kind, key = r["key"].split(":", 1)
    old = json.loads(r["old"])
    if old is None:
        return dict(ok=False, motivo="non c'e' un valore precedente da ripristinare")
    if kind == "motore":
        _engine_write(key, float(old))
    else:
        db.ex("INSERT INTO settings(key,value,updated_ts,updated_by) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
              "updated_ts=excluded.updated_ts, updated_by=excluded.updated_by", (key, db.dumps(old), db.now_iso(), who))
    db.ex("UPDATE rules_log SET status='annullata' WHERE id=?", (rule_id,))
    audit.log(who, "rule.reverted", dict(id=rule_id, chiave=r["key"], ripristinato=old))
    return dict(ok=True, ripristinato=old)


def due(review_days: int, today=None) -> list[dict]:
    """Regole votate (impostazioni e costanti del motore) in vigore da piu' di review_days senza essere state riconfermate."""
    import datetime as dt
    out = []
    now = dt.datetime.now(dt.timezone.utc)
    for r in db.q("SELECT * FROM rules_log WHERE status='applicata' AND id IN (SELECT MAX(id) FROM rules_log WHERE status='applicata' GROUP BY key)"):
        t = dt.datetime.fromisoformat(r["ts"].replace("Z", "+00:00"))
        if (now - t).days >= review_days:
            kind, key = r["key"].split(":", 1)
            out.append(dict(origine=kind, chiave=key, valore=json.loads(r["new"]), da=r["ts"][:10], regola=r["id"]))
    return out


def history(limit: int = 30) -> list[dict]:
    return db.q("SELECT * FROM rules_log ORDER BY id DESC LIMIT ?", (limit,))
