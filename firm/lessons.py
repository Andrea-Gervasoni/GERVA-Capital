"""
Le lezioni: dopo la chiusura di un'operazione l'agente che l'ha decisa dice cosa e' successo e cosa se ne impara.

Una chiamata per agente al giorno (tutte le sue operazioni chiuse insieme), cosi' il costo e' limitato anche se il banco libero chiude
centinaia di trade. Il giudizio puo' essere "errore" (da non ripetere), "tecnica_vincente" (da riusare) o "rumore" (e' stata fortuna o sfortuna:
non se ne impara niente). Errori e tecniche vanno nella memoria dell'agente e tornano nei prompt di tutti: e' il manuale che l'azienda si scrive.
"""
from __future__ import annotations

import datetime as dt
import json

from . import blotter, db, registry
from . import settings as S


def pending(days: int = 3) -> list[dict]:
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    done = {r["trade_key"] for r in db.q("SELECT trade_key FROM lessons")}
    out = []
    for t in blotter.trades(stato="chiusa"):
        if t["chiave"] in done or (t["chiusa_il"] or "") < since:
            continue
        out.append(t)
    return out


def _owner(t: dict) -> str:
    a = t.get("agente") or (t.get("origine") or {}).get("agent")
    if a and registry.get(a) and registry.get(a)["kind"] == "llm":
        return a
    return "capo"                                              # modello, lungo periodo, origine non tracciata: ne risponde il Capo


def daily(runtime=None) -> dict:
    if not S.get("lessons.enabled", True):
        return dict(nota="lezioni spente")
    if runtime is None:
        from llm import runtime
    from . import workflows as W
    by: dict[str, list[dict]] = {}
    for t in pending():
        by.setdefault(_owner(t), []).append(t)
    res = dict(agenti=[], lezioni=0)
    ranked = sorted(by.items(), key=lambda kv: -sum(abs(x["realizzato_eur"]) for x in kv[1]))
    for agent, ts in ranked[:int(S.get("lessons.agents_per_day", 3))]:
        ts = sorted(ts, key=lambda x: -abs(x["realizzato_eur"]))[:8]
        data = [dict(chiave=t["chiave"], simbolo=t["simbolo"], lato=t["lato"], ingresso=t["ingresso"], uscita=t["uscita"], durata_min=t["durata_min"],
                     risultato_eur=t["realizzato_eur"], risultato_pct=t["pnl_pct"], origine=(t["origine"] or {}).get("kind")) for t in ts]
        r = runtime.call(agent, "Rivedi le tue operazioni chiuse. Per ognuna: giudizio (errore da non ripetere, tecnica_vincente da riusare, oppure rumore se e' stata fortuna "
                                "o sfortuna), cosa e' successo (con i numeri), la lezione, e una regola per il futuro. Sii onesto: un guadagno ottenuto per caso non e' una tecnica. "
                                "Usa la stessa chiave dell'operazione.", data=dict(operazioni=data, lezioni_gia_apprese=recent(8)),
                         schema=W.LESSONS, purpose="lezioni", status_label="rivede")
        if not r["ok"]:
            res["agenti"].append(dict(agente=agent, esito=f"nessuna risposta: {str(r.get('motivo', ''))[:60]}"))
            continue
        keys = {t["chiave"]: t for t in ts}
        n = 0
        for x in r["output"].get("lezioni", []):
            t = keys.get(x.get("chiave"))
            if not t:
                continue
            db.ex("INSERT OR IGNORE INTO lessons(ts,trade_key,agent,giudizio,cosa,lezione,regola) VALUES(?,?,?,?,?,?,?)",
                  (db.now_iso(), t["chiave"], agent, x["giudizio"], str(x["cosa_e_successo"])[:600], str(x["lezione"])[:600], str(x["regola_per_il_futuro"])[:400]))
            if x["giudizio"] != "rumore":
                try:
                    registry.add_lesson(agent, f"[{t['simbolo']} {t['lato']} {x['giudizio']}] {x['lezione']}"[:300])
                except Exception:
                    pass
            n += 1
        res["lezioni"] += n
        res["agenti"].append(dict(agente=agent, esito=f"{n} lezioni"))
    return res


def recent(limit: int = 12) -> list[dict]:
    """Il manuale dell'azienda: ultime lezioni utili (errori e tecniche vincenti), per i prompt di tutti."""
    return [dict(agente=r["agent"], giudizio=r["giudizio"], lezione=r["lezione"], regola=r["regola"])
            for r in db.q("SELECT * FROM lessons WHERE giudizio!='rumore' ORDER BY id DESC LIMIT ?", (limit,))]
