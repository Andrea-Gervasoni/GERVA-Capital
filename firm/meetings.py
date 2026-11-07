"""
Sala riunioni: riunioni vere, per motivi sensati, dove ognuno vuole avere ragione — e avere
ragione paga solo se i fatti lo confermano.

Protocollo (docs/research/llm_agents_in_finance.md §4-5: niente dibattiti lunghi, pareri
indipendenti aggregati da codice, un solo giro di replica):
  1. POSIZIONE indipendente: posizione, argomento, evidenze (campi dei dati), fiducia, cosa mi
     farebbe cambiare idea. Nessuno vede gli altri.
  2. REPLICA: ognuno legge le posizioni altrui e puo' confermare o cambiare idea.
  3. DECISIONE del codice: voto pesato per calibrazione storica (1 - Brier/0,25) x fiducia;
     a parita', vince l'opzione piu' prudente (la prima della lista).
  4. Ogni partecipante registra la previsione "la mia posizione finale e' quella giusta" con la
     sua fiducia; alla scadenza il codice risolve con un criterio oggettivo e paga con la regola
     di Brier (compensation.proper_reward). Chi urla senza ragione perde GC.

Tipi e inneschi (il battito li convoca):
  rischio      allarme di livello >= 2 su un pod   -> riduci | mantieni      (esito a 5 giorni)
  allocazione  prima domenica del mese, per pod    -> riduci | mantieni | aumenta (esito a 30 giorni)
  ricerca      un fascicolo passa il cancello      -> respingi | approva     (esito in avanti a 60 giorni)
"""
from __future__ import annotations

import datetime as dt
import json

import numpy as np

from . import db, events, scorekeeper as SK, compensation, pods, gateway, registry
from llm import runtime

S_STR = {"type": "string"}
S_PROB = {"type": "number", "minimum": 0, "maximum": 1}


def _obj(props):
    return {"type": "object", "additionalProperties": False, "properties": props, "required": list(props)}


def position_schema(options):
    return _obj({"posizione": {"type": "string", "enum": options}, "argomento": S_STR,
                 "evidenza": {"type": "array", "items": S_STR}, "fiducia": S_PROB, "cambierei_idea_se": S_STR})


def reply_schema(options):
    return _obj({"replica": S_STR, "posizione_finale": {"type": "string", "enum": options}, "fiducia": S_PROB})


KINDS = {
    "rischio": dict(options=["riduci", "mantieni"], days=5,
                    criterion="Il pod perde nei 5 giorni successivi -> 'riduci' era giusto; altrimenti 'mantieni'."),
    "allocazione": dict(options=["riduci", "mantieni", "aumenta"], days=30,
                        criterion="Rendimento del pod meno Pod Zero nei 30 giorni: < -0,5% riduci, > +0,5% aumenta, altrimenti mantieni."),
    "ricerca": dict(options=["respingi", "approva"], days=60,
                    criterion="Sharpe in avanti della strategia in paper a 60 giorni > 0 -> 'approva' era giusto."),
    # quota di lungo periodo: il primo elemento e' la scelta prudente (in caso di pareggio vince "rinvia")
    "idee": dict(options=["respingi", "approva"], days=25,
                 criterion="L'idea approvata rende piu' dell'S&P 500 nella sua finestra (alpha > 0) -> 'approva' era giusto."),
    "ritmo": dict(options=["20", "35", "50", "75", "100"], days=5,
                  criterion="Nessun esito misurabile direttamente: il ritmo si giudica dal conto, non dal voto."),
    "regola": dict(options=["respingi", "approva"], days=30,
                   criterion="Nessun esito misurabile: la regola si giudica nel tempo dal conto, non dal voto."),
    "lungo": dict(options=["rinvia", "compra"], days=90,
                  criterion="Il paniere della rata (pesi uguali) rende piu' di 0 nei 90 giorni -> 'compra' era giusto."),
}


def calibration_weight(agent_id: str) -> float:
    f = SK.agent_forecasts(agent_id)
    if f["risolte"] < 5 or f["brier"] is None:
        return 0.5
    return float(np.clip(1 - f["brier"] / 0.25, 0.1, 1.0))


def hold(kind: str, title: str, reason: str, participants: list[str], data: dict, context: dict | None = None) -> dict:
    spec = KINDS[kind]
    opts = spec["options"]
    participants = [p for p in participants if (registry.get(p) or {}).get("kind") == "llm"]
    if len(participants) < 2:
        return dict(ok=False, motivo="servono almeno due partecipanti")
    mid = db.ex("INSERT INTO meetings(ts,kind,title,reason,participants,options,status,context) VALUES(?,?,?,?,?,?,?,?)",
                (db.now_iso(), kind, title, reason, db.dumps(participants), db.dumps(opts), "in_corso", db.dumps(context or {})))
    events.publish("meeting.start", "sala_riunioni", dict(id=mid, tipo=kind, titolo=title, motivo=reason, partecipanti=participants))
    task = (f"Riunione ({kind}): {title}. Motivo: {reason}. Prendi posizione tra {opts}. Vuoi avere ragione: se i fatti "
            "ti daranno ragione guadagni Gerva-Coin, se sbagli con troppa fiducia li perdi. Usa solo evidenze dai dati.")
    first = {}
    for p in participants:
        r = runtime.call(p, task, data=data, schema=position_schema(opts), purpose=f"riunione:{kind}", status_label="riunione")
        if r["ok"]:
            first[p] = r["output"]
            events.publish("meeting.statement", p, dict(id=mid, fase="posizione", posizione=r["output"]["posizione"],
                                                        testo=r["output"]["argomento"][:220], fiducia=r["output"]["fiducia"]))
    final = {}
    for p in first:
        others = {registry.get(o)["role"]: dict(posizione=v["posizione"], argomento=v["argomento"][:400], evidenza=v["evidenza"][:4])
                  for o, v in first.items() if o != p}
        r = runtime.call(p, "Replica: leggi le posizioni degli altri. Cambia idea solo se le loro evidenze battono le tue.",
                         data=dict(tua_posizione=first[p], altri=others), schema=reply_schema(opts),
                         purpose=f"riunione:{kind}:replica", status_label="riunione")
        out = r["output"] if r["ok"] else dict(replica="(nessuna replica)", posizione_finale=first[p]["posizione"],
                                               fiducia=first[p]["fiducia"])
        final[p] = out
        events.publish("meeting.statement", p, dict(id=mid, fase="replica", posizione=out["posizione_finale"],
                                                    testo=out["replica"][:220], fiducia=out["fiducia"],
                                                    cambia=out["posizione_finale"] != first[p]["posizione"]))
    # decisione del codice
    weights = {p: calibration_weight(p) for p in final}
    score = {o: 0.0 for o in opts}
    for p, out in final.items():
        score[out["posizione_finale"]] += weights[p] * out["fiducia"]
    best = max(score.values()) if final else 0
    decision = next(o for o in opts if score[o] == best) if final else opts[0]     # pareggio -> la piu' prudente
    deadline = (dt.date.fromisoformat(db.today()) + dt.timedelta(days=spec["days"])).isoformat()
    fids = {}
    conflicted = _conflicted(kind, context or {})
    for p, out in final.items():
        if p in conflicted:                      # chi decide i trade del pod non scommette sull'esito del suo pod
            continue
        fids[p] = SK.register_forecast(p, f"Riunione #{mid}: '{out['posizione_finale']}' e' la scelta giusta",
                                       out["fiducia"], deadline, spec["criterion"], "sala_riunioni")
    transcript = dict(posizioni=first, repliche=final, pesi=weights, punteggi=score, previsioni=fids)
    db.ex("UPDATE meetings SET status='decisa', decision=?, transcript=?, resolve_after=? WHERE id=?",
          (decision, db.dumps(transcript), deadline, mid))
    events.publish("meeting.end", "sala_riunioni", dict(id=mid, decisione=decision, punteggi={k: round(v, 3) for k, v in score.items()}))
    return dict(ok=True, id=mid, decisione=decision, punteggi=score)


# ---------------------------------------------------------------------------
# Risoluzione: i fatti decidono chi aveva ragione, e la regola di Brier paga
# ---------------------------------------------------------------------------
VOID_AFTER_DAYS = 30                      # una riunione che i fatti non possono decidere si annulla


def _conflicted(kind: str, ctx: dict) -> set[str]:
    if kind in ("rischio", "allocazione") and ctx.get("pod"):
        p = pods.get(ctx["pod"])
        return {p["head"]} if p else set()
    return set()


def _pod_ret(pid: str, start: str, days: int) -> float | None:
    """Rendimento su una finestra FISSA [start, start+days]: non scivola in avanti con il tempo."""
    end = (dt.date.fromisoformat(start) + dt.timedelta(days=days)).isoformat()
    rows = db.q("SELECT day, nav FROM nav_marks WHERE pod=? AND day>=? AND day<=? ORDER BY day", (pid, start, end))
    if len(rows) < max(2, days // 2):
        return None
    return rows[-1]["nav"] / rows[0]["nav"] - 1


def _traded(pid: str, start: str, days: int) -> bool:
    end = (dt.date.fromisoformat(start) + dt.timedelta(days=days + 1)).isoformat()
    return bool(db.one("SELECT 1 FROM fills WHERE pod=? AND ts>=? AND ts<? LIMIT 1", (pid, start, end)))


def correct_option(m: dict) -> str | None:
    ctx = json.loads(m["context"] or "{}")
    start = m["ts"][:10]
    if m["kind"] == "rischio" and ctx.get("pod"):
        if ctx["pod"] != "pod_zero" and not _traded(ctx["pod"], start, 5):
            return None                          # pod fermo: "mantieni" sarebbe vinto a tavolino
        r = _pod_ret(ctx["pod"], start, 5)
        return None if r is None else ("riduci" if r < 0 else "mantieni")
    if m["kind"] == "allocazione" and ctx.get("pod"):
        r, z = _pod_ret(ctx["pod"], start, 30), _pod_ret("pod_zero", start, 30)
        if r is None or z is None:
            return None
        d = r - z
        return "riduci" if d < -0.005 else "aumenta" if d > 0.005 else "mantieni"
    if m["kind"] == "idee" and ctx.get("idea"):
        from . import ideas
        return ideas.verdict(int(ctx["idea"]))
    if m["kind"] == "lungo" and ctx.get("prezzi"):
        now = db.runtime_get("lt.prezzi") or {}
        r = [now[s] / p - 1 for s, p in ctx["prezzi"].items() if s in now and p]
        if len(r) < max(1, len(ctx["prezzi"]) // 2):
            return None
        return "compra" if float(np.mean(r)) > 0 else "rinvia"
    if m["kind"] == "ricerca" and ctx.get("rendimenti_paper"):
        x = np.asarray(ctx["rendimenti_paper"], float)
        return "approva" if len(x) > 20 and x.mean() > 0 else "respingi"
    return None


def resolve_due(today: str | None = None) -> list[dict]:
    today = today or db.today()
    out = []
    for m in db.q("SELECT * FROM meetings WHERE status='decisa' AND resolve_after<=?", (today,)):
        right = correct_option(m)
        if right is None:
            late = (dt.date.fromisoformat(today) - dt.date.fromisoformat(m["resolve_after"][:10])).days
            if late > VOID_AFTER_DAYS:           # nessun fatto verificabile: annullata, nessuno vince a tavolino
                tr = json.loads(m["transcript"])
                for fid in tr.get("previsioni", {}).values():
                    if fid:
                        db.ex("UPDATE forecasts SET resolved_by='annullata' WHERE id=? AND outcome IS NULL", (fid,))
                db.ex("UPDATE meetings SET status='annullata', outcome=? WHERE id=?",
                      (db.dumps(dict(motivo="esito non verificabile con i dati")), m["id"]))
            continue
        tr = json.loads(m["transcript"])
        conflicted = _conflicted(m["kind"], json.loads(m["context"] or "{}"))
        paid = {}
        for p, rep in tr["repliche"].items():
            if p in conflicted:
                continue
            ok = rep["posizione_finale"] == right
            fid = tr["previsioni"].get(p)
            if fid:
                SK.resolve_forecast(fid, ok, "sala_riunioni")
            g = compensation.proper_reward(rep["fiducia"], ok)
            compensation.pay_reward(p, g, f"riunione #{m['id']}: {'aveva ragione' if ok else 'aveva torto'}")
            paid[p] = round(g, 2)
        db.ex("UPDATE meetings SET status='risolta', outcome=? WHERE id=?", (db.dumps(dict(giusta=right, gc=paid)), m["id"]))
        events.publish("meeting.resolved", "scorekeeper", dict(id=m["id"], giusta=right, gc=paid))
        out.append(dict(id=m["id"], giusta=right, gc=paid))
    return out


def history(limit: int = 20) -> list[dict]:
    rows = db.q("SELECT * FROM meetings ORDER BY id DESC LIMIT ?", (limit,))
    for r in rows:
        for k in ("participants", "options", "transcript", "outcome", "context"):
            r[k] = json.loads(r[k]) if r[k] else None
    return rows


# ---------------------------------------------------------------------------
# Inneschi
# ---------------------------------------------------------------------------
def risk_meeting(pid: str, alert: str) -> dict:
    p = pods.get(pid)
    res = hold("rischio", f"Pod {pid}: ridurre l'esposizione?", alert, ["cro", "capo", p["head"]],
               data=dict(libro=gateway.pod_book(pid), pod=p), context=dict(pod=pid))
    if res.get("ok") and res["decisione"] == "riduci" and p["status"] == "attivo":
        pods.set_capital(pid, p["capital_frac"] * 0.5, f"decisione della riunione #{res['id']}", actor="sala_riunioni")
    return res


def allocation_meeting(pid: str) -> dict:
    from . import economy
    p = pods.get(pid)
    return hold("allocazione", f"Capitale del pod {pid}", "riallocazione mensile",
                ["capo", "cro", p["head"]], data=dict(alpha_netto=economy.net_alpha(pid), libro=gateway.pod_book(pid)),
                context=dict(pod=pid))
