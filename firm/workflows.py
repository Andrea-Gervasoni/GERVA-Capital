"""
Flussi di lavoro della societa'. Il codice fa tutto cio' che si calcola; gli agenti giudicano,
sintetizzano e propongono, con output a schema. Ogni flusso registra eventi e punteggi.
"""
from __future__ import annotations

import json
import math
import random
import re

import numpy as np

from . import db, events, tasks, trials, scorekeeper as SK, risk, pods, gateway, registry, mailbox
from . import settings as S
from llm import runtime, tools

S_STR = {"type": "string"}
S_PROB = {"type": "number", "minimum": 0, "maximum": 1}
FORECAST = {"type": "object", "additionalProperties": False,
            "properties": {"enunciato": S_STR, "probabilita": S_PROB, "scadenza": S_STR, "criterio": S_STR, "fonte": S_STR},
            "required": ["enunciato", "probabilita", "scadenza", "criterio", "fonte"]}


def obj(props: dict, required: list | None = None) -> dict:
    return {"type": "object", "additionalProperties": False, "properties": props,
            "required": required if required is not None else list(props)}


def arr(items: dict) -> dict:
    return {"type": "array", "items": items}


# ===========================================================================
# 1. REDAZIONE: triage -> verifica su seconda fonte -> bollettino
# ===========================================================================
NEWS_TRIAGE = obj({"items": arr(obj({"news_id": {"type": "integer"}, "rilevanza": S_PROB, "sintesi": S_STR,
                                     "tag": arr(S_STR), "affermazioni": arr(S_STR), "fonte_primaria": {"type": "boolean"}})),
                   "note": S_STR})
FACT_CHECK = obj({"esiti": arr(obj({"news_id": {"type": "integer"}, "verificata": {"type": "boolean"},
                                    "seconda_fonte": S_STR, "motivo": S_STR,
                                    "affermazioni_non_verificabili": arr(S_STR)}))})
BULLETIN = obj({"bollettino": S_STR,
                "punti": arr(obj({"titolo": S_STR, "perche_conta": S_STR, "news_ids": arr({"type": "integer"})})),
                "previsioni": arr(FORECAST)})

PRIMARY_DOMAINS = ("federalreserve.gov", "sec.gov", "ecb.europa.eu", "bls.gov", "bankofengland.co.uk",
                   "esma.europa.eu", "consob.it", "bancaditalia.it")


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-zà-ù0-9]{4,}", (s or "").lower())}


def second_source_candidates(item: dict, pool: list[dict], thr: float = 0.3) -> list[dict]:
    """Fonti indipendenti: dominio diverso e titolo simile (Jaccard). Calcolo, non giudizio."""
    t = _tokens(item["title"])
    out = []
    for o in pool:
        if o["id"] == item["id"] or o["domain"] == item["domain"]:
            continue
        u = _tokens(o["title"])
        j = len(t & u) / len(t | u) if t | u else 0
        if j >= thr:
            out.append(dict(id=o["id"], url=o["url"], domain=o["domain"], somiglianza=round(j, 2)))
    return sorted(out, key=lambda x: -x["somiglianza"])[:3]


def news_cycle(limit: int = 12) -> dict:
    queue = db.q("SELECT * FROM news WHERE status='nuova' ORDER BY id DESC LIMIT ?", (limit,))
    if not queue:
        return dict(nota="nessuna notizia nuova")
    raw = "\n".join(f"[{n['id']}] {n['title']} — {n['domain']} ({n['published']})\n{(n['summary'] or '')[:400]}"
                    for n in queue)
    tri = runtime.call("news_analyst", "Fai il triage delle notizie: rilevanza per i nostri mercati, sintesi "
                       "fedele, affermazioni verificabili. Non aggiungere fatti che non sono nel testo.",
                       untrusted=raw, schema=NEWS_TRIAGE, purpose="triage notizie", status_label="legge")
    submitted = 0
    if tri["ok"]:
        ids = {n["id"] for n in queue}
        for it in tri["output"]["items"]:
            if it["news_id"] in ids:
                db.ex("UPDATE news SET summary=?, tags=?, agent_id='news_analyst', status='da_verificare' WHERE id=?",
                      (it["sintesi"][:600], db.dumps(it["tag"]), it["news_id"]))
                submitted += 1
    # verifica: le fonti primarie passano; le altre servono una seconda fonte indipendente
    pool = db.q("SELECT * FROM news ORDER BY id DESC LIMIT 400")
    to_check, verified, rejected = [], 0, 0
    for n in db.q("SELECT * FROM news WHERE status='da_verificare'"):
        if any(n["domain"].endswith(d) for d in PRIMARY_DOMAINS):
            db.ex("UPDATE news SET status='verificata', checked_by='fact_checker', second_url='fonte primaria' WHERE id=?",
                  (n["id"],))
            verified += 1
        else:
            to_check.append(dict(n, candidati=second_source_candidates(n, pool)))
    if to_check:
        txt = "\n\n".join(f"[{n['id']}] {n['title']} — {n['domain']}\nSintesi: {n['summary']}\nCandidati seconda fonte: "
                          + json.dumps(n["candidati"], ensure_ascii=False) for n in to_check)
        fc = runtime.call("fact_checker", "Verifica ogni notizia: e' confermata da una seconda fonte INDIPENDENTE tra i "
                          "candidati? Se non ci sono candidati adeguati, la notizia NON e' verificata.",
                          untrusted=txt, schema=FACT_CHECK, purpose="verifica notizie", status_label="verifica")
        if fc["ok"]:
            cand = {n["id"]: {c["url"] for c in n["candidati"]} for n in to_check}
            for e in fc["output"]["esiti"]:
                if e["news_id"] not in cand:
                    continue
                # il codice controlla l'agente: una "seconda fonte" che non e' tra i candidati non vale
                ok = e["verificata"] and e["seconda_fonte"] in cand[e["news_id"]]
                db.ex("UPDATE news SET status=?, second_url=?, checked_by='fact_checker' WHERE id=?",
                      ("verificata" if ok else "respinta", e["seconda_fonte"] if ok else None, e["news_id"]))
                verified += ok
                rejected += not ok
                if e["verificata"] and not ok:
                    SK.add_eval("fact_checker", "affermazioni_non_verificabili", 1.0,
                                details=dict(news=e["news_id"], motivo="seconda fonte non tra i candidati"))
                    _postmortem("fact_checker", 3, "Verifica dichiarata con una seconda fonte inesistente",
                                "La fonte citata non era tra i candidati indipendenti trovati dal codice",
                                "Il codice ora rifiuta ogni seconda fonte non presente tra i candidati",
                                "Una notizia e' verificata solo con una fonte che compare tra i candidati forniti.")
    # metriche dure della Redazione
    if submitted:
        tot = db.one("SELECT COUNT(*) n FROM news WHERE agent_id='news_analyst' AND status IN ('verificata','respinta')")["n"]
        ok_n = db.one("SELECT COUNT(*) n FROM news WHERE agent_id='news_analyst' AND status='verificata'")["n"]
        if tot:
            SK.add_eval("news_analyst", "precisione_eventi", ok_n / tot)
    ver = db.q("SELECT id,title,domain,summary FROM news WHERE status='verificata' ORDER BY id DESC LIMIT 10")
    bul = None
    if ver:
        b = runtime.call("head_intel", "Scrivi il bollettino per i desk usando SOLO notizie verificate. Per ogni punto "
                         "spiega perche' conta. Se fai previsioni, servono probabilita', scadenza e criterio.",
                         data=dict(verificate=ver), schema=BULLETIN, purpose="bollettino", status_label="scrive")
        if b["ok"]:
            bul = b["output"]
            events.publish("news.bulletin", "head_intel", dict(testo=bul["bollettino"][:800], punti=len(bul["punti"])))
            for f in bul["previsioni"][:3]:
                SK.register_forecast("head_intel", f["enunciato"], f["probabilita"], f["scadenza"], f["criterio"], f["fonte"])
    return dict(triage=submitted, verificate=verified, respinte=rejected, bollettino=bool(bul))


# ===========================================================================
# 2. RISCHIO: il CRO legge i numeri del motore e segnala
# ===========================================================================
CRO_REVIEW = obj({"allarmi": arr(obj({"id": S_STR, "cosa": S_STR, "evidenza": S_STR,
                                      "gravita": {"type": "integer", "minimum": 1, "maximum": 5},
                                      "azione": S_STR, "smentita": S_STR})),
                  "stato_generale": {"type": "string", "enum": ["verde", "giallo", "rosso"]},
                  "raccomanda_kill": {"type": "boolean"},
                  "proposte_limiti": arr(obj({"limite": S_STR, "valore_attuale": S_STR, "valore_proposto": S_STR,
                                              "allenta": {"type": "boolean"}, "motivo": S_STR})),
                  "note": S_STR})


def risk_review() -> dict:
    from . import pod_zero
    snap = risk.snapshot()
    pz = pod_zero.target_weights()
    kinds = {k: ("crypto" if k in S.risk_limits()["instruments"]["crypto_allowed"] else "stock") for k in pz}
    stress = {k: round(risk.stress(pz, kinds, s), 4) for k, s in risk.SCENARIOS.items()}
    data = dict(motore_di_rischio=snap, stress_pod_zero=stress, limiti=S.risk_limits(),
                libri_pod={p["id"]: gateway.pod_book(p["id"]) for p in pods.all_pods() if p["id"] != "pod_zero"})
    r = runtime.call("cro", "Rivedi lo stato di rischio. Ogni allarme con evidenza numerica copiata dai dati, gravita', "
                     "azione e cosa lo smentirebbe. Proponi modifiche ai limiti solo con motivo e dati.",
                     data=data, schema=CRO_REVIEW, purpose="revisione rischio", status_label="pensa")
    if not r["ok"]:
        return r
    o = r["output"]
    if o["raccomanda_kill"]:
        risk.recommend_kill("cro", "raccomandazione del CRO", "; ".join(a["cosa"] for a in o["allarmi"])[:500])
    for a in o["allarmi"]:
        events.publish("risk.alert", "cro", dict(cosa=a["cosa"], gravita=a["gravita"], azione=a["azione"]))
    for p in o["proposte_limiti"]:
        if p["allenta"]:      # allentare un limite = grande richiesta n.2: lo decide solo Andrea
            mailbox.big_request(2, f"Proposta del CRO: allentare {p['limite']}", p["motivo"],
                                [f"Portare a {p['valore_proposto']}", f"Lasciare {p['valore_attuale']}"],
                                f"Valutare con i dati: {p['motivo'][:120]}", f"Il limite resta {p['valore_attuale']}",
                                dedup_key=f"cro-limit-{p['limite']}-{db.today()}")
    return dict(ok=True, stato=o["stato_generale"], allarmi=len(o["allarmi"]))


# ===========================================================================
# 3. ORDINE DI ANDREA: il Capo scompone, i manager eseguono, i risultati risalgono
# ===========================================================================
MANAGERS = ["cro", "head_research", "head_intel", "senior_validator"]
CEO_PLAN = obj({"comprensione": S_STR, "rischio_vs_vantaggio": S_STR,
                "compiti": arr(obj({"assegnatario": {"type": "string", "enum": MANAGERS}, "titolo": S_STR, "perche": S_STR})),
                "risposta_ad_andrea": S_STR, "grande_richiesta": {"type": "boolean"}})
MANAGER_WORK = obj({"risultato": S_STR, "stato": {"type": "string", "enum": ["fatto", "in_corso", "servono_dati"]},
                    "sotto_compiti": arr(obj({"assegnatario": S_STR, "titolo": S_STR})), "fonti": arr(S_STR)})
CEO_SUMMARY = obj({"sintesi": S_STR, "stato": {"type": "string", "enum": ["fatto", "in_corso", "servono_dati"]}})


def handle_command(cid: int) -> dict:
    cmd = db.one("SELECT * FROM commands WHERE id=?", (cid,))
    snap = dict(rischio=risk.snapshot(), budget=__import__("firm.budget", fromlist=["x"]).status(),
                organigramma=[dict(id=a["id"], ruolo=a["role"], stato=a["status"]) for a in registry.all_agents()
                              if a["kind"] == "llm"])
    plan = runtime.call("capo", "Andrea ti ha dato un ordine. Scomponilo in compiti per i manager. Se porta piu' rischio "
                        "senza piu' vantaggio, dillo e proponi l'alternativa.",
                        data=dict(ordine=cmd["text"], stato_societa=snap), schema=CEO_PLAN, purpose="delega",
                        status_label="riunione")
    if not plan["ok"]:
        db.ex("UPDATE commands SET status='errore', answer=? WHERE id=?", (plan["motivo"], cid))
        return plan
    p = plan["output"]
    root = tasks.create(cid, None, "capo", "andrea", cmd["text"][:120])
    results = []
    for c in p["compiti"][:4]:
        tid = tasks.create(cid, root, c["assegnatario"], "capo", c["titolo"])
        w = runtime.call(c["assegnatario"], f"Compito dal Capo: {c['titolo']}. Perche': {c['perche']}. Lavora con i dati "
                         "che hai; se non bastano, stato 'servono_dati' e indica quali.",
                         data=dict(ordine_originale=cmd["text"]), schema=MANAGER_WORK, purpose="compito",
                         status_label="scrive")
        out = w["output"] if w["ok"] else dict(risultato=w["motivo"], stato="servono_dati", sotto_compiti=[], fonti=[])
        for sc in out.get("sotto_compiti", [])[:2]:
            sub = registry.get(sc["assegnatario"])
            if sub and sub["kind"] == "llm" and sub["superior"] == c["assegnatario"]:
                sid = tasks.create(cid, tid, sc["assegnatario"], c["assegnatario"], sc["titolo"])
                sw = runtime.call(sc["assegnatario"], f"Compito da {c['assegnatario']}: {sc['titolo']}", schema=MANAGER_WORK,
                                  purpose="sotto-compito", status_label="scrive")
                tasks.complete(sid, sw["output"] if sw["ok"] else sw["motivo"])
        tasks.complete(tid, out, out["stato"])
        results.append(dict(da=c["assegnatario"], **out))
    summ = runtime.call("capo", "Riassumi per Andrea i risultati dei manager, in modo onesto: cosa e' fatto, cosa no.",
                        data=dict(ordine=cmd["text"], risultati=results), schema=CEO_SUMMARY, purpose="sintesi",
                        status_label="scrive")
    answer = summ["output"]["sintesi"] if summ["ok"] else p["risposta_ad_andrea"]
    tasks.complete(root, dict(sintesi=answer))
    db.ex("UPDATE commands SET status='risposto', answer=? WHERE id=?", (answer, cid))
    if p["grande_richiesta"]:
        mailbox.big_request(6, f"Ordine di Andrea: {cmd['text'][:60]}", p["rischio_vs_vantaggio"],
                            ["Procedere come proposto", "Non procedere"], p["risposta_ad_andrea"][:300],
                            "Non si procede finche' Andrea non sceglie", dedup_key=f"cmd-{cid}")
    return dict(ok=True, compiti=len(results), risposta=answer)


# ===========================================================================
# 4. RICERCA -> CANCELLO -> VALIDAZIONE (con canarini)
# ===========================================================================
CANDIDATES = [
    dict(id="dynmom_s3", titolo="Momentum settoriale con freno di Daniel-Moskowitz", famiglia="sector_momentum_dyn",
         fonte="Daniel & Moskowitz, JFE 2016"),
    dict(id="vixrev_s4", titolo="Reversal di breve dimensionato col VIX", famiglia="short_reversal_vix",
         fonte="Nagel, RFS 2012"),
    dict(id="carry_crypto", titolo="Filtro di rischio sul carry crypto", famiglia="carry_risk_filter",
         fonte="Schmeling, Schrimpf & Todorov, BIS WP 1087"),
    dict(id="tsmom_lf", titolo="TSMOM long/flat a 12 mesi su ETF UCITS", famiglia="tsmom",
         fonte="Moskowitz, Ooi & Pedersen, JFE 2012"),
]
HYPOTHESIS = obj({"ipotesi": S_STR, "meccanismo": S_STR, "perche_persiste": S_STR, "chi_perde": S_STR,
                  "perche_non_sparito": S_STR, "parametri": obj({"lookback": {"type": "integer", "minimum": 5, "maximum": 504}}),
                  "decisione": {"type": "string", "enum": ["testa", "archivia", "servono_dati"]}, "motivo": S_STR})
SENIOR_REPORT = obj({"risultati": S_STR, "limiti": arr(S_STR),
                     "decisione": {"type": "string", "enum": ["archivia", "passa_a_validazione", "servono_dati"]},
                     "motivo": S_STR})
VALIDATION = obj({"esito": {"type": "string", "enum": ["approva", "respingi", "chiedi_dati"]},
                  "difetti": arr(obj({"tipo": {"type": "string", "enum": ["look_ahead", "survivorship", "costi", "overfitting",
                                                                          "dati", "instabilita", "altro"]},
                                      "descrizione": S_STR, "gravita": {"type": "integer", "minimum": 1, "maximum": 5}})),
                  "motivo": S_STR})


def _market_data():
    """Dati per la ricerca: reali se presenti in var/data (scaricati sul Mac), altrimenti SINTETICI
    con risultato noto. I risultati su dati sintetici non possono mai andare al Comitato."""
    from quantlab import strategies as ST
    from firm import paths
    import os
    import pandas as pd
    p = os.path.join(paths.VAR, "data", "etf_close.pkl")
    if os.path.exists(p):
        close = pd.read_pickle(p)
        return None, close, False
    o, c = ST.synthetic_market(n_days=252 * 8, n_assets=8, seed=random.randint(0, 10_000), trend_strength=0.0)
    return o, c, True


def research_cycle() -> dict:
    from quantlab import strategies as ST, backtest as BT, stats as QS, lookahead as LA, data as QD
    done = {r["id"].split(":")[0] for r in db.q("SELECT id FROM research")}
    cand = next((c for c in CANDIDATES if c["id"] not in done), None)
    if not cand:
        return dict(nota="nessun candidato nuovo in coda")
    rid = f"{cand['id']}:{db.today()}"
    db.ex("INSERT INTO research(id,ts,owner,title,stage,updated_ts) VALUES(?,?,?,?,?,?)",
          (rid, db.now_iso(), "senior_trend", cand["titolo"], "ipotesi", db.now_iso()))
    events.publish("research.new", "head_research", dict(id=rid, titolo=cand["titolo"]))
    tid_head = tasks.create(None, None, "senior_trend", "head_research", cand["titolo"])
    h = runtime.call("senior_trend", f"Scrivi l'ipotesi per: {cand['titolo']} (fonte: {cand['fonte']}). Meccanismo "
                     "economico, perche' dovrebbe persistere, chi perde, perche' non e' gia' sparito.",
                     data=dict(candidato=cand, prove_registrate=trials.counts()), schema=HYPOTHESIS,
                     purpose="ipotesi", status_label="pensa")
    if not h["ok"] or h["output"]["decisione"] != "testa":
        db.ex("UPDATE research SET stage='archiviata', decision=? WHERE id=?",
              (db.dumps(h.get("output") or h.get("motivo")), rid))
        tasks.complete(tid_head, "archiviata prima del test")
        return dict(id=rid, esito="archiviata", motivo=(h.get("output") or {}).get("motivo", h.get("motivo")))
    hyp = h["output"]
    lb = int(hyp["parametri"]["lookback"])
    trial = trials.register("senior_trend", rid, cand["famiglia"], dict(lookback=lb), hyp["ipotesi"] + " " + hyp["meccanismo"])
    o, c, synthetic = _market_data()
    fn = (lambda x: ST.tsmom(x, lookback=lb)) if cand["famiglia"] != "sector_momentum_dyn" else (lambda x: ST.sector_momentum(x))
    W = fn(c)
    res = BT.run(W, c, o, cost_rate=0.0008, band=0.02).returns.iloc[260:]
    res2 = BT.run(W, c, o, cost_rate=0.0016, band=0.02).returns.iloc[260:]
    la = LA.truncation_test(fn, c, cut_points=3)
    defl = trials.record_result(trial, res.values, QD.fingerprint(c), dict(sintetico=synthetic))
    perf = QS.performance(res.values)
    sh2 = QS.performance(res2.values)["Sharpe"]
    g = trials.gate(trial, cost2x_sharpe=sh2, lookahead_ok=la["ok"])
    dossier = dict(id=rid, ipotesi=hyp, prova=trial, metriche=perf, sharpe_costi_doppi=sh2, deflated=defl,
                   cancello=g, look_ahead=la, dati_sintetici=synthetic)
    tools._write_research(rid.replace(":", "_"), "fascicolo.md", "# " + cand["titolo"] + "\n\n```json\n"
                          + json.dumps(dossier, ensure_ascii=False, indent=1, default=str) + "\n```\n")
    rep = runtime.call("senior_trend", "Riporta i risultati della prova copiando i numeri dai dati. Se il vantaggio "
                       "sparisce con i costi o fuori campione, dichiaralo e archivia.",
                       data=dossier, schema=SENIOR_REPORT, purpose="relazione", status_label="scrive")
    stage = "cancello_fallito" if not g["passa"] else "in_validazione"
    if synthetic:
        stage = "solo_collaudo_sintetico"
    db.ex("UPDATE research SET stage=?, trial_id=?, gate=?, updated_ts=? WHERE id=?",
          (stage, trial, db.dumps(g), db.now_iso(), rid))
    tasks.complete(tid_head, rep.get("output") or rep.get("motivo"))
    val = None
    if g["passa"] or synthetic:
        val = validate(rid, dossier)
    if g["passa"] and not synthetic:                    # un fascicolo vero che passa il cancello merita una riunione
        from . import meetings
        meetings.hold("ricerca", cand["titolo"], "il fascicolo ha passato il cancello automatico",
                      ["head_research", "senior_trend", "senior_validator"], data=dossier, context=dict(ricerca=rid))
    SK.add_eval("senior_trend", "tasso_validazione", 1.0 if (val and val.get("esito") == "approva") else 0.0)
    return dict(id=rid, prova=trial, sharpe=round(perf["Sharpe"], 3), dsr=round(defl["dsr"], 3),
                cancello=g["passa"], sintetico=synthetic, validazione=val)


def validate(rid: str, dossier: dict, canary_rate: float = 0.3) -> dict:
    """Il validatore riceve il fascicolo SENZA l'opinione dell'autore. Con probabilita' canary_rate il
    codice semina un difetto noto (canarino): Sharpe impossibile da un segnale che guarda avanti."""
    d = {k: v for k, v in dossier.items() if k not in ("relazione_autore",)}
    canary = random.random() < canary_rate
    if canary:
        d = json.loads(json.dumps(d, default=str))
        d["metriche"]["Sharpe"] = 4.8
        d["look_ahead"] = dict(ok=True, violazioni=[], tagli=3,
                               nota="segnale calcolato con close.shift(-1) per allineare le date")
    r = runtime.call("senior_validator", "Cerca di rompere questa strategia: look-ahead, survivorship, costi, "
                     "overfitting, dati, instabilita'. Devi indicare almeno un difetto concreto o motivare perche' "
                     "non ce ne sono.", data=d, schema=VALIDATION, purpose="validazione", status_label="verifica")
    if not r["ok"]:
        return dict(esito="errore", motivo=r["motivo"])
    out = r["output"]
    if canary:
        found = any(x["tipo"] == "look_ahead" for x in out["difetti"]) and out["esito"] != "approva"
        SK.add_eval("senior_validator", "canarino", 1.0 if found else 0.0, details=dict(ricerca=rid))
        SK.add_eval("senior_validator", "canarini_individuati", 1.0 if found else 0.0)
        if found:
            from . import compensation
            compensation.award_bonus("senior_validator", 5.0, f"canarino individuato ({rid})")
        if not found:
            _postmortem("senior_validator", 3, "Canarino non individuato",
                        "Fascicolo con Sharpe 4,8 e shift(-1) dichiarato non segnalato come look-ahead",
                        "Caso aggiunto agli eval del validatore", "Uno Sharpe sopra 3 e qualunque shift(-1) sono look-ahead fino a prova contraria.")
        return dict(esito="canarino", trovato=found)
    db.ex("UPDATE research SET validation=?, stage=?, updated_ts=? WHERE id=?",
          (db.dumps(out), "validata" if out["esito"] == "approva" else "respinta_validazione", db.now_iso(), rid))
    return dict(esito=out["esito"], difetti=len(out["difetti"]))


# ===========================================================================
# 5. COMITATO DELLA DOMENICA
# ===========================================================================
COMMITTEE = obj({"decisioni": arr(obj({"ricerca_id": S_STR, "esito": {"type": "string",
                                       "enum": ["approva", "respingi", "chiedi_dati"]}, "motivo": S_STR})),
                 "messaggio_settimanale": S_STR})


def committee() -> dict:
    items = db.q("SELECT * FROM research WHERE stage IN ('validata','respinta_validazione','in_validazione')")
    for it in items:
        for k in ("gate", "validation"):
            it[k] = json.loads(it[k]) if it[k] else None
    r = runtime.call("capo", "Comitato Strategie della domenica. Decidi per ogni fascicolo. Regola: non puoi approvare "
                     "cio' che la Validazione ha respinto o che non ha passato il cancello automatico.",
                     data=dict(fascicoli=items, rischio=risk.snapshot()), schema=COMMITTEE, purpose="committee",
                     status_label="riunione")
    applied = []
    if r["ok"]:
        for d in r["output"]["decisioni"]:
            it = next((x for x in items if x["id"] == d["ricerca_id"]), None)
            if not it:
                continue
            allowed_ok = (it["stage"] == "validata" and (it["gate"] or {}).get("passa"))
            esito = d["esito"] if (d["esito"] != "approva" or allowed_ok) else "respingi"
            db.ex("UPDATE research SET decision=?, stage=?, updated_ts=? WHERE id=?",
                  (db.dumps(dict(d, esito=esito)), "approvata_paper" if esito == "approva" else
                   ("archiviata" if esito == "respingi" else it["stage"]), db.now_iso(), it["id"]))
            applied.append(dict(id=it["id"], esito=esito, override=esito != d["esito"]))
            events.publish("committee.decision", "capo", dict(ricerca=it["id"], esito=esito))
        events.publish("committee.message", "capo", dict(testo=r["output"]["messaggio_settimanale"][:600]))
    return dict(decisioni=applied)


# ===========================================================================
# 6. POD: il Capo Pod decide se seguire il segnale del codice
# ===========================================================================
POD_DECISION = obj({"azione": {"type": "string", "enum": ["segui_modello", "riduci", "attendi"]}, "motivo": S_STR,
                    "previsione": FORECAST})


def pod_cycle(pid: str, signal_weights: dict[str, float], now=None) -> dict:
    p = pods.get(pid)
    if not p or p["status"] == "chiuso":
        return dict(pod=pid, nota="pod chiuso")
    head = registry.get(p["head"])
    book = gateway.pod_book(pid)
    r = runtime.call(p["head"], "Il codice ha calcolato i pesi target del tuo segnale. Decidi se seguirli, ridurli o "
                     "attendere, con un motivo verificabile e una previsione calibrata sul tuo pod.",
                     data=dict(pod=p, libro=book, pesi_target=signal_weights), schema=POD_DECISION, purpose="pod",
                     status_label="pensa")
    if not r["ok"]:
        return dict(pod=pid, errore=r["motivo"])
    o = r["output"]
    mult = {"segui_modello": 1.0, "riduci": 0.5, "attendi": 0.0}[o["azione"]]
    cap = book["capitale_ammesso"]
    sent = []
    for instr, w in signal_weights.items():
        q = gateway.quote(instr)
        if not q:
            continue
        target_qty = mult * w * cap / q["price"]
        cur = book["posizioni"].get(instr, {}).get("qty", 0.0)
        delta = target_qty - cur
        from quantlab import costs as QC
        floor = max(S.risk_limits()["order"]["min_notional_eur"],
                    QC.min_efficient_notional(gateway.COST_BY_KIND.get(q["kind"], QC.UCITS_ETF)))
        if abs(delta * q["price"]) < floor:            # ordine troppo piccolo: la commissione minima mangerebbe il guadagno
            continue
        side = "BUY" if delta > 0 else "SELL"
        if not tools.allowed(head, "submit_order"):
            raise PermissionError(f"{p['head']} non ha lo strumento submit_order")
        # il pod viene dal registro (pods.head), non dall'output dell'agente: non puo' operare su altri pod
        res = gateway.submit_order(pid, p["head"], instr, side, round(abs(delta), 6),
                                   f"{o['azione']}: {o['motivo'][:120]}", "settimane", now=now)
        sent.append(dict(strumento=instr, lato=side, esito=res["status"], motivi=res.get("reasons")))
        SK.add_eval(p["head"], "disciplina_rischio", 1.0 if res["status"] == "accettato" else 0.0)
    f = o["previsione"]
    SK.register_forecast(p["head"], f["enunciato"], f["probabilita"], f["scadenza"], f["criterio"], f["fonte"])
    return dict(pod=pid, azione=o["azione"], ordini=sent)


# ===========================================================================
# 7. TALENT (codice): punteggi, promozioni, retrocessioni, post-mortem
# ===========================================================================
def _postmortem(agent_id: str, severity: int, what: str, why: str, change: str, lesson: str):
    db.ex("INSERT INTO postmortems(ts,agent_id,severity,what,why,change,lesson) VALUES(?,?,?,?,?,?,?)",
          (db.now_iso(), agent_id, severity, what, why, change, lesson))
    registry.add_lesson(agent_id, f"{lesson} (errore: {what})")
    events.publish("postmortem", "talent", dict(agente=agent_id, cosa=what, lezione=lesson, gravita=severity))
    if severity >= 4:                                   # errore grave: il bonus differito si perde
        from . import compensation
        compensation.clawback(agent_id, f"post-mortem grave: {what}")


def talent_cycle() -> dict:
    out = []
    agents = [a for a in registry.all_agents() if a["kind"] == "llm" and a["status"] in ("attivo", "in_prova")]
    for a in agents:
        peers = [b["id"] for b in agents if b["grade"] == a["grade"] and b["id"] != a["id"]]
        comp = SK.composite(a["id"], a["dept"])
        prom = SK.promotion_test(a["id"], a["dept"], a["grade"], peers) if peers else dict(idoneo=False, motivo="nessun pari di grado")
        dem = SK.demotion_reasons(a["id"])
        action = None
        if a["status"] == "in_prova":
            pass
        elif prom["idoneo"] and a["grade"] < 6:
            registry.change_grade(a["id"], a["grade"] + 1, "promozione", prom["motivo"])
            registry.set_status(a["id"], "in_prova", f"periodo di prova di {S.get('talent.probation_days')} giorni")
            action = "promosso"
        elif dem and a["grade"] > 0:
            registry.change_grade(a["id"], a["grade"] - 1, "retrocessione", "; ".join(dem))
            action = "retrocesso"
        out.append(dict(agente=a["id"], punteggio=comp["punteggio"], azione=action, promozione=prom.get("motivo"),
                        grado=a["grade"]))
    # il migliore di ogni grado (con almeno 10 valutazioni) prende un bonus differito: la competizione paga
    from . import compensation
    for g in {o["grado"] for o in out}:
        same = [o for o in out if o["grado"] == g and o["punteggio"] is not None
                and SK.composite(o["agente"], registry.get(o["agente"])["dept"])["n_valutazioni"] >= 10]
        if len(same) >= 2:
            top = max(same, key=lambda o: o["punteggio"])
            compensation.award_bonus(top["agente"], 10.0, "migliore del grado questa settimana")
    return dict(valutati=len(out), azioni=[o for o in out if o["azione"]])
