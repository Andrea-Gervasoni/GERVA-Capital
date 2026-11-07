"""
Il diario dell'azienda: tutte le conversazioni tra le persone e tutte le tecniche del fondo, con il loro stato.

Conversazioni = cio' che le persone si sono dette davvero, preso dalle tabelle che il codice scrive (niente testo inventato):
riunioni (posizioni e repliche), idee (chi le ha presentate, chi le ha portate su e perche'), compiti (chi li ha dati, chi li ha fatti,
con il risultato), segnali (lettura, analisi, veto del Rischio), banco libero (la motivazione di ogni trade), lezioni.

Tecniche = cio' che il fondo usa, ha approvato, sta provando o ha bocciato: modello e strumenti di base (adottati), strategie dai paper,
prove del registro (con Sharpe, Deflated Sharpe e cancello), idee e regole votate dal comitato.
"""
from __future__ import annotations

import json

from . import db, registry


def _nm(aid):
    a = registry.get(aid) if aid else None
    return (a or {}).get("name") or aid or "?"


def conversations(limit: int = 60, agent: str | None = None) -> list[dict]:
    out = []
    for m in db.q("SELECT * FROM meetings ORDER BY id DESC LIMIT 40"):
        tr = json.loads(m["transcript"] or "{}")
        msgs = []
        for a, p in (tr.get("posizioni") or {}).items():
            msgs.append(dict(chi=a, nome=_nm(a), fase="posizione", testo=f"[{p.get('posizione')}, fiducia {p.get('fiducia')}] {p.get('argomento', '')}",
                             evidenze=p.get("evidenza") or [], cambierei=p.get("cambierei_idea_se")))
        for a, p in (tr.get("repliche") or {}).items():
            msgs.append(dict(chi=a, nome=_nm(a), fase="replica", testo=f"[{p.get('posizione_finale')}, fiducia {p.get('fiducia')}] {p.get('replica', '')}"))
        if m["decision"]:
            msgs.append(dict(chi="codice", nome="Decisione", fase="esito", testo=f"{m['decision']} · punteggi {tr.get('punteggi')}"))
        out.append(dict(ts=m["ts"], tipo="riunione", titolo=m["title"], motivo=m["reason"], partecipanti=json.loads(m["participants"] or "[]"), messaggi=msgs))
    for i in db.q("SELECT * FROM ideas ORDER BY id DESC LIMIT 40"):
        msgs = [dict(chi=i["author"], nome=_nm(i["author"]), fase="presenta", testo=i["tesi"], evidenze=json.loads(i["evidenze"] or "[]"))]
        for h in json.loads(i["history"] or "[]"):
            if h.get("cosa") in ("portata su", "scarta", "rimanda", "respinta", "approvata", "chiusa (stop)", "chiusa (obiettivo)", "chiusa (scadenza)", "applicata", "riconfermata", "decaduta"):
                msgs.append(dict(chi=h.get("chi"), nome=_nm(h.get("chi")), fase=h.get("cosa"), testo=" ".join(str(x) for x in (h.get("motivo"), h.get("miglioramenti") and "Migliorie: " + h["miglioramenti"]) if x) or ""))
        part = list(dict.fromkeys([i["author"]] + [m["chi"] for m in msgs if m["chi"]]))
        out.append(dict(ts=i["ts"], tipo="idea", titolo=f"Idea #{i['id']}: {i['title']}", motivo=i["status"], partecipanti=part, messaggi=msgs))
    for c in db.q("SELECT * FROM commands ORDER BY id DESC LIMIT 20"):
        msgs = [dict(chi="andrea", nome="Andrea", fase="ordine", testo=c["text"])]
        for t in db.q("SELECT * FROM tasks WHERE order_id=? ORDER BY id", (c["id"],)):
            res = t["result"]
            try:
                r = json.loads(res) if res else None
                res = (r.get("risultato") or r.get("sintesi") or json.dumps(r, ensure_ascii=False)) if isinstance(r, dict) else res
            except (TypeError, ValueError):
                pass
            msgs.append(dict(chi=t["assigner"], nome=_nm(t["assigner"]), fase=f"a {_nm(t['assignee'])}", testo=t["title"]))
            if res:
                msgs.append(dict(chi=t["assignee"], nome=_nm(t["assignee"]), fase=t["status"], testo=str(res)[:1500]))
        if c["answer"]:
            msgs.append(dict(chi="capo", nome=_nm("capo"), fase="risposta ad Andrea", testo=c["answer"][:3000]))
        out.append(dict(ts=c["ts"], tipo="ordine", titolo=f"Ordine #{c['id']}: {c['text'][:80]}", motivo=c["status"], partecipanti=list(dict.fromkeys(m["chi"] for m in msgs)), messaggi=msgs))
    for s in db.q("SELECT * FROM signals ORDER BY id DESC LIMIT 30"):
        a = json.loads(s["analisi"] or "{}")
        msgs = [dict(chi="sala", nome=s["fonte"] or "sala segnali", fase="segnale", testo=s["testo"][:600])]
        if a.get("motivo"):
            msgs.append(dict(chi="senior_crypto", nome=_nm("senior_crypto"), fase=f"analisi: {a.get('decisione')}", testo=f"{a['motivo']} (probabilita' obiettivo {a.get('probabilita_tp1')})", evidenze=a.get("rischi") or []))
        if a.get("veto"):
            msgs.append(dict(chi="cro", nome=_nm("cro"), fase="veto" if a["veto"].get("bloccato") else "nessun veto", testo=a["veto"].get("motivo", "")))
        msgs.append(dict(chi="codice", nome="Decisione", fase=s["stato"], testo=s["motivo"] or ""))
        out.append(dict(ts=s["ts"], tipo="segnale", titolo=f"Segnale #{s['id']}", motivo=s["stato"], partecipanti=["senior_crypto", "cro"], messaggi=msgs))
    for t in db.q("SELECT * FROM free_trades ORDER BY id DESC LIMIT 40"):
        out.append(dict(ts=t["ts"], tipo="banco libero", titolo=f"{_nm(t['agent'])}: {t['side']} {t['symbol']} {round(t['notional'] or 0)} $", motivo=t["status"], partecipanti=[t["agent"]],
                        messaggi=[dict(chi=t["agent"], nome=_nm(t["agent"]), fase="decide", testo=f"{t['motivo'] or ''} (probabilita' {t['p']}, stop {t['stop_pct']}%, obiettivo {t['take_pct']}%)")] +
                                 ([dict(chi="codice", nome="Esito", fase=t["esito"] or "chiusa", testo=f"risultato {t['pnl']:+.2f} $")] if t["pnl"] is not None else [])))
    for l in db.q("SELECT * FROM lessons ORDER BY id DESC LIMIT 30"):
        out.append(dict(ts=l["ts"], tipo="lezione", titolo=f"Lezione di {_nm(l['agent'])} ({l['giudizio']})", motivo=l["giudizio"], partecipanti=[l["agent"]],
                        messaggi=[dict(chi=l["agent"], nome=_nm(l["agent"]), fase=l["giudizio"], testo=f"{l['cosa']} — Lezione: {l['lezione']} — Per il futuro: {l['regola']}")]))
    if agent:
        out = [c for c in out if agent in (c.get("partecipanti") or []) or any(m.get("chi") == agent for m in c["messaggi"])]
    out.sort(key=lambda c: c["ts"] or "", reverse=True)
    return out[:limit]


BASE = [
    ("adottata", "Modello GERVA-Q: trend e reversal su azioni ed ETF", "Moskowitz, Ooi & Pedersen (2012); Jegadeesh & Titman (1993)", "motore del conto IBKR"),
    ("adottata", "Leva con tetto di esposizione (scala di GERVA-Q)", "scelta di Andrea; analisi di Kelly sui dati del fondo", "fino al 150% del conto"),
    ("adottata", "Leva gestita per volatilita' (si alza solo se il VIX e' sotto il 90 percentile)", "Moreira & Muir (2017, JF); Harvey et al. (2018)", "accesa"),
    ("adottata", "Analisi di Kelly sulla leva ottima (pieno e mezzo edge)", "Kelly (1956); Thorp; MacLean, Thorp & Ziemba", "firm.py kelly"),
    ("adottata", "Monte Carlo a blocchi (code grasse) e stress test sulle crisi passate", "Kunsch (1989); Politis & Romano (1994)", "pagina Mercati"),
    ("adottata", "Registro globale delle prove e Deflated Sharpe", "Bailey & Lopez de Prado (2014)", "ogni prova conta"),
    ("adottata", "Previsioni con punteggio di Brier e voto pesato per calibrazione", "Brier (1950); Tetlock (2015)", "riunioni e idee"),
    ("adottata", "Bonus differito con clawback", "pratica delle multi-manager", "4 settimane"),
    ("adottata", "Ritmo di ingresso deciso dal comitato", "riduce il rischio della data di ingresso", "riunione 'ritmo'"),
    ("adottata", "Dossier di ogni trade con previsione condizionata e revisione pro/contro", "", "plancia"),
]


def techniques() -> list[dict]:
    from . import strategies
    out = [dict(stato=s, nome=n, fonte=f, nota=x, tipo="metodo del fondo") for s, n, f, x in BASE]
    for k, v in strategies.overview().items():
        bt = v.get("backtest") or {}
        st = "adottata" if v["accesa"] else ("in prova" if not bt else ("in attesa del voto" if bt.get("ok") else "bocciata"))
        r = bt.get("risultati") or {}
        out.append(dict(stato=st, nome=v["nome"], fonte=v["fonte"], tipo="strategia dai paper",
                        nota=f"Sharpe {r.get('sharpe')}, DSR {(bt.get('deflated') or {}).get('dsr')}, cancello {'superato' if (bt.get('cancello') or {}).get('passa') else 'non superato'}" if r else "backtest da fare"))
    for t in db.q("SELECT * FROM trials ORDER BY ts DESC LIMIT 60"):
        if t["agent_id"] == "gervaq_legacy":
            continue
        sr = round(t["sharpe_daily"] * 252 ** 0.5, 2) if t["sharpe_daily"] is not None else None
        out.append(dict(stato="provata" if t["status"] == "testata" else t["status"], nome=f"Prova {t['family']} ({t['strategy_id']})", fonte=t["hypothesis"][:200], tipo="prova del registro",
                        nota=f"Sharpe {sr}" if sr is not None else "senza risultato"))
    for i in db.q("SELECT * FROM ideas WHERE kind IN ('regola','motore','regola_casa','riesame') ORDER BY id DESC LIMIT 60"):
        st = {"applicata": "approvata", "riconfermata": "approvata", "respinta": "bocciata", "decaduta": "bocciata", "scartata": "bocciata", "al_comitato": "in attesa del voto", "al_superiore": "in attesa del voto"}.get(i["status"], i["status"])
        out.append(dict(stato=st, nome=i["title"], fonte=f"proposta da {_nm(i['author'])}", tipo="regola votata", nota=(i["tesi"] or "")[:200]))
    return out
