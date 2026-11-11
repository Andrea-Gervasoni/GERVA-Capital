"""
La Costituzione: cosa il comitato puo' cambiare votando, e fino a dove.

Gli agenti propongono, il comitato vota (riunione con voto pesato per precisione storica), il codice applica. I limiti qui sotto non
sono una prudenza imposta: sono i limiti FISICI (pesi tra 0 e 100% del conto, la leva che il broker accetta) e servono a non scrivere
valori senza senso. La scelta dentro questi limiti e' del comitato.

Cosa NON si cambia votando (resta di Andrea): il solo conto paper (firm.mode), le credenziali, il budget in soldi veri, i limiti di rischio
del file risk_limits.yaml (freno del -35%, ordine massimo) e ogni passo verso soldi veri.

Ogni cambiamento: scritto in rules_log (valore vecchio e nuovo, chi, quale idea), pubblicato come evento, nell'audit, ANNULLABILE
(`firm.py regole --annulla ID`). Per il motore (GERVA-Q) si modifica una costante di config.py con copia di sicurezza e controllo di sintassi.

Piu' rischio = serve Andrea. Un voto che ALZA la leva o un tetto di esposizione (RISK_UP e tutte le costanti del motore) non si applica
da solo: diventa una proposta in attesa (rules_log.status = 'in_attesa', grande richiesta "limite di rischio" nella Posta del Capo) e
entra in vigore solo con la capability di Andrea (`firm.py regole --approva ID`, oppure la risposta nella Posta). Abbassare il rischio
si applica subito. In ogni caso il valore non supera i tetti di config/risk_limits.yaml (ceiling): per andare oltre Andrea cambia il limite.
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
    "signals.leverage_cap": (1, 25), "futures.margin_per_signal_max_pct": (1, 50), "futures.margin_total_max_pct": (5, 100),
}
ENGINE = {                                 # costante di GERVA-Q (config.py) -> (minimo, massimo)
    "SCALE_K": (0.5, 4.0), "SCALE_CAP": (0.5, 3.0), "SCALE_HARD_CAP": (1.0, 3.0),   # oltre ~2x lordo sulle azioni e' il broker a rifiutare gli ordini
    "OVERLAY_MAX_NAME": (0.01, 0.25), "OVERLAY_MAX_TOTAL": (0.05, 1.0),
    "VOL_MULT_MIN": (0.1, 1.0), "VOL_MULT_MAX": (1.0, 3.0), "TURNOVER_MIN": (0.05, 1.0),
}


# Impostazioni per cui un valore PIU' ALTO vuol dire piu' leva o piu' esposizione (per il motore: tutte le costanti di ENGINE).
RISK_UP = {"desk.max_name_frac", "desk.max_total_frac", "ideas.max_name_frac", "ideas.max_total_frac",
           "algo.crypto_tsmom.capital_frac", "algo.spy_intraday_momentum.capital_frac", "volmgmt.lo", "volmgmt.hi",
           "signals.risk_frac", "signals.max_frac", "signals.max_total_frac", "crypto.venue_max_frac"}
# chiave -> voce di risk_limits.yaml che fa da tetto (i limiti sono di Andrea: qui si leggono soltanto)
CEILINGS = {
    ("motore", "SCALE_CAP"): ("firm", "max_gross"), ("motore", "SCALE_HARD_CAP"): ("firm", "max_gross"), ("motore", "VOL_MULT_MAX"): ("firm", "max_gross"),
    ("motore", "OVERLAY_MAX_TOTAL"): ("firm", "max_gross"), ("motore", "OVERLAY_MAX_NAME"): ("pod", "max_position_frac"),
    ("regola", "volmgmt.hi"): ("firm", "max_gross"), ("regola", "desk.max_total_frac"): ("firm", "max_gross"), ("regola", "ideas.max_total_frac"): ("firm", "max_gross"),
    ("regola", "desk.max_name_frac"): ("pod", "max_position_frac"), ("regola", "ideas.max_name_frac"): ("pod", "max_position_frac"),
    ("regola", "crypto.venue_max_frac"): ("firm", "max_crypto_frac"), ("regola", "signals.max_total_frac"): ("firm", "max_crypto_frac"),
    ("regola", "signals.max_frac"): ("order", "max_notional_frac_nav"),
}
PENDING = "in_attesa"
APPROVE = "Approva: applica il nuovo valore"          # la risposta nella Posta del Capo che applica la proposta


def raises_risk(kind: str, key: str, old, new) -> bool:
    """True se il nuovo valore AUMENTA leva o esposizione rispetto a quello in vigore (o se quello in vigore non si conosce)."""
    if kind != "motore" and key not in RISK_UP:
        return False
    try:
        return old is None or float(new) > float(old) + 1e-12
    except (TypeError, ValueError):
        return True


def ceiling(kind: str, key: str) -> float | None:
    """Tetto dal file dei limiti di rischio (config/risk_limits.yaml). Vale SEMPRE, anche con l'approvazione di Andrea."""
    ref = CEILINGS.get((kind, key))
    if ref is None:
        return None
    try:
        return float(S.risk_limits()[ref[0]][ref[1]])
    except (KeyError, TypeError, ValueError, OSError):
        return None


def _is_owner(cap) -> bool:
    return isinstance(cap, S.AndreaCapability) and getattr(cap, "_ok", False)


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
    for kind, table, read in (("regola", RULES, S.get), ("motore", ENGINE, _engine_read)):
        for k, (lo, hi) in table.items():
            top = ceiling(kind, k)
            out[f"{kind}:{k}"] = dict(attuale=read(k), minimo=lo, massimo=hi if top is None else min(hi, top))
            if kind == "motore" or k in RISK_UP:
                out[f"{kind}:{k}"]["alzare_richiede_andrea"] = True
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


def _write(kind: str, key: str, old, v: float, who: str, idea: int | None, pending_id: int | None = None) -> dict:
    """Scrive davvero il valore (impostazione o costante del motore) e lo registra. Chi chiama ha gia' deciso che si puo'."""
    if kind == "motore":
        try:
            _engine_write(key, v)
        except Exception as e:
            return dict(ok=False, motivo=f"GERVA-Q non modificato: {str(e)[:120]}")
    else:
        v = type(S.get(key))(v) if isinstance(S.get(key), (int, float)) and not isinstance(S.get(key), bool) else v
        db.ex("INSERT INTO settings(key,value,updated_ts,updated_by) VALUES(?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
              "updated_ts=excluded.updated_ts, updated_by=excluded.updated_by", (key, db.dumps(v), db.now_iso(), who))
    if pending_id is not None:
        db.ex("UPDATE rules_log SET ts=?, old=?, new=?, who=?, status='applicata' WHERE id=?", (db.now_iso(), db.dumps(old), db.dumps(v), who, pending_id))
        rid = pending_id
    else:
        rid = db.ex("INSERT INTO rules_log(ts,kind,key,old,new,who,idea,status) VALUES(?,?,?,?,?,?,?,?)",
                    (db.now_iso(), kind, f"{kind}:{key}", db.dumps(old), db.dumps(v), who, idea, "applicata"))
    audit.log("comitato", "rule.applied", dict(id=rid, tipo=kind, chiave=key, vecchio=old, nuovo=v, chi=who))
    events.publish("rule.applied", "comitato", dict(id=rid, tipo=kind, chiave=key, vecchio=old, nuovo=v))
    return dict(ok=True, id=rid, vecchio=old, nuovo=v)


def _propose(kind: str, key: str, old, v: float, who: str, idea: int | None, what: str = "alzare") -> dict:
    """Piu' rischio: il voto non basta. Si registra la proposta e si chiede ad Andrea (Posta del Capo, categoria 'limite di rischio')."""
    for r in db.q("SELECT id, new FROM rules_log WHERE key=? AND status=?", (f"{kind}:{key}", PENDING)):
        if abs(float(json.loads(r["new"])) - v) < 1e-12:                 # la stessa proposta e' gia' in attesa: non se ne apre un'altra
            return dict(ok=False, in_attesa=True, id=r["id"], vecchio=old, proposto=v, motivo="proposta gia' in attesa dell'approvazione di Andrea")
    rid = db.ex("INSERT INTO rules_log(ts,kind,key,old,new,who,idea,status) VALUES(?,?,?,?,?,?,?,?)",
                (db.now_iso(), kind, f"{kind}:{key}", db.dumps(old), db.dumps(v), who, idea, PENDING))
    audit.log("comitato", "rule.pending", dict(id=rid, tipo=kind, chiave=key, attuale=old, proposto=v, chi=who))
    events.publish("rule.pending", "comitato", dict(id=rid, tipo=kind, chiave=key, attuale=old, proposto=v))
    try:
        from . import mailbox
        mailbox.big_request(2, f"Il comitato chiede di {what} {key}: da {old} a {v}"[:140],
                            f"Il voto ({who}) aumenta la leva o l'esposizione ({'costante del motore GERVA-Q' if kind == 'motore' else 'impostazione'} {key}). "
                            "Un aumento del rischio non si applica senza di te.",
                            [APPROVE, "Respingi"], "Decidi tu: il codice non ha un'opinione sul tuo rischio", "Resta il valore attuale",
                            dedup_key=f"rule-pending:{rid}")
    except Exception as e:                                               # la proposta resta comunque in attesa nel registro delle regole
        events.publish("risk.alert", "comitato", dict(cosa=f"proposta di regola #{rid} in attesa ma non arrivata nella Posta del Capo ({str(e)[:80]})", gravita=2))
    return dict(ok=False, in_attesa=True, id=rid, vecchio=old, proposto=v,
                motivo=f"aumenta il rischio: serve l'approvazione di Andrea (firm.py regole --approva {rid})")


def pending() -> list[dict]:
    return db.q("SELECT * FROM rules_log WHERE status=? ORDER BY id", (PENDING,))


def approve(rule_id: int, cap) -> dict:
    """Solo Andrea (capability): applica una proposta in attesa. Il valore resta comunque sotto il tetto di risk_limits.yaml di ADESSO."""
    if not _is_owner(cap):
        raise S.SettingsPermissionError("solo Andrea approva un aumento del rischio")
    r = db.one("SELECT * FROM rules_log WHERE id=?", (rule_id,))
    if not r or r["status"] != PENDING:
        return dict(ok=False, motivo="proposta non trovata o non piu' in attesa")
    kind, key = r["key"].split(":", 1)
    v = float(json.loads(r["new"]))
    ok, why = check(kind, key, v)
    if not ok:
        return dict(ok=False, motivo=why)
    top = ceiling(kind, key)
    if top is not None and v > top:
        v = top
    res = _write(kind, key, current(kind, key), v, f"andrea (proposta di {r['who']})", r["idea"], pending_id=rule_id)
    if res["ok"] and r["idea"]:
        try:
            from . import ideas
            ideas.on_rule_decided(r["idea"], True, res)
        except Exception as e:
            events.publish("heartbeat.error", "sistema", dict(passo="idea dopo approvazione", errore=str(e)[:200]))
    return res


def reject(rule_id: int, cap) -> dict:
    if not _is_owner(cap):
        raise S.SettingsPermissionError("solo Andrea risponde a una proposta di aumento del rischio")
    r = db.one("SELECT * FROM rules_log WHERE id=?", (rule_id,))
    if not r or r["status"] != PENDING:
        return dict(ok=False, motivo="proposta non trovata o non piu' in attesa")
    db.ex("UPDATE rules_log SET status='respinta' WHERE id=?", (rule_id,))
    audit.log("andrea", "rule.rejected", dict(id=rule_id, chiave=r["key"]))
    events.publish("rule.rejected", "andrea", dict(id=rule_id, chiave=r["key"]))
    if r["idea"]:
        try:
            from . import ideas
            ideas.on_rule_decided(r["idea"], False, dict(ok=False, motivo="respinta da Andrea"))
        except Exception as e:
            events.publish("heartbeat.error", "sistema", dict(passo="idea dopo rifiuto", errore=str(e)[:200]))
    return dict(ok=True, id=rule_id, stato="respinta")


def apply(kind: str, key: str, value, who: str, idea: int | None = None, cap=None) -> dict:
    """kind: 'regola' (impostazione) o 'motore' (costante di GERVA-Q). Senza la capability di Andrea (`cap`) un valore che aumenta
    il rischio NON si applica: torna ok=False, in_attesa=True e l'id della proposta."""
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
    if kind == "motore" and old is None:
        return dict(ok=False, motivo=f"GERVA-Q non modificato: {key} non si legge in config.py")
    v = float(value)
    top = ceiling(kind, key)
    if top is not None and v > top:                    # il tetto di risk_limits.yaml vale sempre: il valore si ferma li'
        v = top
    if raises_risk(kind, key, old, v) and not _is_owner(cap):
        return _propose(kind, key, old, v, who, idea)
    res = _write(kind, key, old, v, who, idea)
    if res["ok"] and top is not None and float(value) > top:
        res["limitato_a"] = top
    return res


def revert(rule_id: int, who: str = "andrea", cap=None) -> dict:
    """Ripristina il valore precedente. Se il ripristino AUMENTA il rischio (si annulla una regola che lo aveva ridotto) serve Andrea:
    senza la sua capability diventa una proposta in attesa e la regola resta in vigore."""
    r = db.one("SELECT * FROM rules_log WHERE id=?", (rule_id,))
    if not r or r["status"] != "applicata":
        return dict(ok=False, motivo="regola non trovata o gia' annullata")
    kind, key = r["key"].split(":", 1)
    old = json.loads(r["old"])
    if old is None:
        return dict(ok=False, motivo="non c'e' un valore precedente da ripristinare")
    top = ceiling(kind, key)
    if top is not None and float(old) > top:
        old = top
    if raises_risk(kind, key, current(kind, key), old) and not _is_owner(cap):
        return _propose(kind, key, current(kind, key), float(old), who, None, what="riportare")
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
    waiting = {r["key"] for r in pending()}              # una regola con una proposta in attesa di Andrea non torna in consiglio ogni giorno
    for r in db.q("SELECT * FROM rules_log WHERE status='applicata' AND id IN (SELECT MAX(id) FROM rules_log WHERE status='applicata' GROUP BY key)"):
        t = dt.datetime.fromisoformat(r["ts"].replace("Z", "+00:00"))
        if (now - t).days >= review_days and r["key"] not in waiting:
            kind, key = r["key"].split(":", 1)
            out.append(dict(origine=kind, chiave=key, valore=json.loads(r["new"]), da=r["ts"][:10], regola=r["id"]))
    return out


def history(limit: int = 30) -> list[dict]:
    return db.q("SELECT * FROM rules_log ORDER BY id DESC LIMIT ?", (limit,))
