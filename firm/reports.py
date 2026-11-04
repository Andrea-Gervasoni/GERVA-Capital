"""
Report giornaliero e settimanale, con analisi e correzioni proposte dal codice.

Il report non abbellisce: riporta numeri, scarti dal modello, costi contro valore e una lista di
correzioni, ciascuna con gravita', evidenza, azione e chi la esegue (la societa' in autonomia,
oppure Andrea se e' una grande richiesta). Si salva in var/reports/AAAA-MM-GG.json e si legge
nel portale (pannello Report). `python firm.py report` lo genera a mano.
"""
from __future__ import annotations

import datetime as dt
import json
import os

import numpy as np

from . import (db, paths, budget, risk, pods, gateway, economy, building, audit, trials, mailbox,
               scorekeeper as SK, registry, pod_zero, meetings)


def _fix(sev: int, cosa: str, evidenza: str, azione: str, chi: str = "societa'") -> dict:
    return dict(gravita=sev, cosa=cosa, evidenza=evidenza, azione=azione, chi=chi)


def diagnostics() -> list[dict]:
    out = []
    # 1. disciplina dei pod verso il Gateway
    for p in pods.all_pods():
        if p["id"] == "pod_zero":
            continue
        rows = db.q("SELECT status, reject FROM gateway_orders WHERE pod=? ORDER BY id DESC LIMIT 50", (p["id"],))
        if len(rows) >= 10:
            rej = [r for r in rows if r["status"] == "respinto"]
            rate = len(rej) / len(rows)
            if rate > 0.3:
                top = max(set(r["reject"].split(";")[0] for r in rej), key=lambda x: sum(x in r["reject"] for r in rej))
                out.append(_fix(3, f"Pod {p['id']}: {rate:.0%} degli ordini respinti", f"motivo piu' frequente: {top}",
                                "Dimensionare gli ordini dentro i limiti prima dell'invio; post-mortem al Capo Pod se continua"))
        b = gateway.pod_book(p["id"])
        if b["capitale_ammesso"] > 0 and b["lorda"] < 0.3 and p["status"] == "attivo":
            out.append(_fix(1, f"Pod {p['id']} quasi fermo: lorda {b['lorda']:.0%}", "capitale pagato con la tassa ma poco usato",
                            "Verificare se il segnale e' davvero piatto o se gli ordini non partono"))
    # 2. costo contro valore degli agenti
    for a in registry.all_agents():
        if a["kind"] != "llm":
            continue
        cost = db.one("SELECT COALESCE(SUM(cost_eur),0) c FROM llm_calls WHERE agent_id=?", (a["id"],))["c"]
        comp = SK.composite(a["id"], a["dept"])
        if cost > 0.5 and (comp["punteggio"] is None or comp["punteggio"] < 0.4):
            out.append(_fix(2, f"{a['name']} costa {cost:.2f} EUR con punteggio {comp['punteggio']}",
                            "costo superiore al valore misurato", "Talent: correggere il prompt o fondere il ruolo"))
        f = SK.agent_forecasts(a["id"])
        if f["risolte"] >= 10 and f["brier"] is not None and f["brier"] > 0.25:
            out.append(_fix(2, f"{a['name']}: Brier {f['brier']:.3f}, peggio di una moneta", f"{f['risolte']} previsioni risolte",
                            "Peso dimezzato nelle riunioni (automatico); caso aggiunto agli eval"))
    # 3. budget
    st = budget.status()
    if st["pace_eur_day"] > 0.9 * st["daily_cap"]:
        out.append(_fix(2, "Ritmo di spesa vicino al tetto giornaliero", f"{st['pace_eur_day']:.3f} su {st['daily_cap']:.2f} EUR",
                        "Scalare i manager a Haiku per i compiti di routine"))
    # 4. correlazione tra pod
    c = pods.mean_pod_correlation()
    if c is not None and c > 0.5:
        out.append(_fix(3, f"Pod troppo correlati ({c:.2f})", "la diversificazione tra pod e' apparente",
                        "Ridurre il pod con il contributo marginale piu' basso; filosofie piu' diverse nei prompt"))
    # 5. liquidita' ferma del Pod Zero
    if pod_zero.available():
        g = pod_zero.gross_fraction()
        if g < 0.7:
            out.append(_fix(2, f"Pod Zero: {1 - g:.0%} del NAV in liquidita' che non rende", f"lorda target {g:.0%}",
                            "Candidato di ricerca: sleeve di liquidita' in un ETF UCITS sul tasso overnight (€STR); rilascio di domenica",
                            "Andrea (rilascio GERVA-Q, cat. 5)"))
        from quantlab import costs as QC
        thr = QC.min_efficient_notional(QC.UCITS_ETF)
        out.append(_fix(2, "Pod Zero: ordini minimi da 200 EUR (live.py) sotto la soglia efficiente",
                        f"con una commissione minima stimata di {QC.UCITS_ETF.commission_min:.0f} EUR un ordine da 200 EUR costa "
                        f"{QC.UCITS_ETF.cost(200) / 200:.1%}; soglia per restare sotto lo 0,5%: ~{thr:,.0f} EUR",
                        "Rilievo R11: alzare MIN_ORDER_EUR o allargare la banda (variante band5 del banco v4) dopo aver verificato la tariffa reale",
                        "Andrea (rilascio GERVA-Q, cat. 5)"))
        eq = pod_zero.equity_model()
        if eq and eq.get("asof"):
            age = (dt.date.today() - dt.date.fromisoformat(eq["asof"])).days
            if age > 4:
                out.append(_fix(2, f"Dati del Pod Zero vecchi di {age} giorni", f"model_latest.json al {eq['asof']}",
                                "Controllare il cron di run_daily.sh sul Mac"))
    # 6. integrita' e validazione
    if not audit.verify()["ok"]:
        out.append(_fix(5, "Catena di hash dell'audit rotta", "verifica fallita", "Fermare gli agenti e indagare", "Andrea"))
    if not os.path.exists(os.path.join(paths.GERVA_Q, "challenge", "trials_export.csv")):
        out.append(_fix(2, "DSR della v3 non verificabile", "manca challenge/trials_export.csv (rilievo R1)",
                        "Applicare il rilascio 2026-11-08 domenica", "Andrea (cat. 5)"))
    return sorted(out, key=lambda x: -x["gravita"])


def daily(day: str | None = None, save: bool = True) -> dict:
    day = day or db.today()
    fb = gateway.firm_book()
    lb = economy.leaderboard()
    people = []
    for a in registry.all_agents():
        if a["kind"] != "llm":
            continue
        comp = SK.composite(a["id"], a["dept"])
        cost = db.one("SELECT COALESCE(SUM(cost_eur),0) c FROM llm_calls WHERE agent_id=?", (a["id"],))["c"]
        people.append(dict(id=a["id"], nome=a["name"], grado=a["grade_name"], punteggio=comp["punteggio"],
                           gc=economy.gc_balance(a["id"]), differito=economy.gc_unvested(a["id"]), costo=cost))
    people.sort(key=lambda x: -(x["punteggio"] or 0))
    orders = db.q("SELECT status, COUNT(*) n FROM gateway_orders WHERE ts>=? GROUP BY status", (day,))
    rep = dict(
        giorno=day, tipo="giornaliero",
        societa=dict(nav=fb["nav"], pnl=fb["pnl"], rendimento=fb["nav"] / gateway.START_NAV_EUR - 1, lorda=fb["gross"]),
        rischio=risk.snapshot(), budget=budget.status(), edificio=building.level(),
        pod=lb["pod"], persone=people, gateway={r["status"]: r["n"] for r in orders},
        ricerca=dict(prove=trials.counts(), fascicoli=db.q("SELECT id,title,stage FROM research ORDER BY ts DESC LIMIT 5")),
        riunioni=[dict(id=m["id"], tipo=m["kind"], titolo=m["title"], decisione=m["decision"], stato=m["status"])
                  for m in meetings.history(5)],
        posta_aperta=len(mailbox.items("aperta")),
        correzioni=diagnostics(),
    )
    if save:
        d = os.path.join(paths.VAR, "reports")
        os.makedirs(d, exist_ok=True)
        json.dump(rep, open(os.path.join(d, f"{day}.json"), "w"), ensure_ascii=False, indent=1, default=str)
    return rep


def listing() -> list[str]:
    d = os.path.join(paths.VAR, "reports")
    return sorted((f[:-5] for f in os.listdir(d) if f.endswith(".json")), reverse=True) if os.path.isdir(d) else []


def load(day: str) -> dict | None:
    p = os.path.join(paths.VAR, "reports", f"{day}.json")
    return json.load(open(p)) if os.path.exists(p) else None
