"""
Battito deterministico (brief <budget>: societa' a eventi, non a ciclo continuo).

A ogni battito il CODICE controlla le condizioni e sveglia solo gli agenti necessari:
  sempre      motore di rischio, regole di drawdown dei pod, controllo del budget, catena di hash (1/giorno)
  comandi     se Andrea ha scritto al Capo -> delega
  notizie     raccolta RSS ogni battito; Redazione se >= 5 notizie nuove o alle 07 UTC
  rischio     CRO se gli allarmi cambiano o alle 20 UTC
  ricerca     un ciclo il martedi' e il giovedi'
  pod         venerdi' sera
  domenica    Comitato, ciclo talent, riallocazione (prima domenica del mese)
In sciopero gli agenti non vengono svegliati; il codice deterministico continua.
"""
from __future__ import annotations

import datetime as dt
import re

from . import settings as S
from . import db, events, paths, risk, pods, budget, audit, gateway, news_feed, mailbox, workflows, economy, compensation, meetings, reports, registry


def _once(key: str) -> bool:
    """True la prima volta che `key` viene chiesto (per giorno/settimana)."""
    # atomico: due battiti concorrenti (run + heartbeat manuale) non pagano due volte
    cur = db.connect().execute("INSERT OR IGNORE INTO runtime(key,value,updated_ts) VALUES(?,?,?)",
                               (f"once:{key}", db.dumps(db.now_iso()), db.now_iso()))
    return cur.rowcount == 1


def beat(now: dt.datetime | None = None, use_agents: bool = True) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    day = now.strftime("%Y-%m-%d")
    woke, notes = [], []
    # ---- codice deterministico, sempre
    snap = risk.snapshot()
    acts = pods.apply_drawdown_rules()
    if acts:
        notes.append(f"regole drawdown: {acts}")
    budget.runway_check()
    if _once(f"audit:{day}"):
        v = audit.verify()
        if not v["ok"]:
            events.publish("risk.alert", "auditor", dict(cosa=f"catena di hash rotta alla voce {v['prima_rottura']}",
                                                         gravita=5))
    # IBKR: osservazione in sola lettura del conto della sfida (il portale non si collega mai al broker)
    import os
    if os.environ.get("IBKR_OBSERVE") == "1":            # sul Mac; sul server lo fa il container 'observer'
        from . import ibkr
        obs = ibkr.observe_challenge()                          # (non chiamarla snap: e' lo snapshot del rischio)
        if obs and obs.get("ok") and (obs.get("nav_eur") or 0) > 0:          # un punto per battito: serve al grafico del conto
            db.ex("INSERT INTO nav_ticks(ts,nav) VALUES(?,?)", (db.now_iso(), float(obs["nav_eur"])))
    pods.ensure_pods()
    try:
        S.refresh_defaults()
    except Exception:
        pass
    try:
        from . import crypto_venue
        if crypto_venue.configured():
            crypto_venue.rebalance()                       # crypto: 24 ore su 24, a ogni battito
    except Exception:
        pass
    registry.sync_if_profiles_changed()
    if os.environ.get("IBKR_CHALLENGE_ACCOUNT") and pods.enabled():
        if not os.environ.get("IBKR_FIRM_ACCOUNT"):
            # i pod non possono usare il conto della sfida (live.py vende tutto cio' che non e' nel suo target):
            # serve un secondo conto paper, cioe' una nuova credenziale -> grande richiesta n.4
            mailbox.big_request(
                4, "Secondo conto paper IBKR per i pod?",
                "I pod della societa' oggi eseguono sul broker simulato. Per eseguire su IBKR serve un SECONDO conto paper "
                "(DU...) distinto da quello della sfida: GERVA-Q vende ogni posizione che non e' nel suo target, quindi "
                "ordini dei pod sullo stesso conto verrebbero liquidati la sera stessa e violerebbero REGOLE_SFIDA §1.",
                ["Aprire un secondo conto paper (gratuito) e mettere il login in secrets/ibgw-firm.env",
                 "Restare sul broker simulato"],
                "Restare sul simulato finche' i pod non hanno 3 mesi di track record forward: il secondo conto aggiunge "
                "realismo di esecuzione, non rendimento",
                "Pod sul broker simulato; GERVA-Q invariato sul suo conto", dedup_key="ibkr-second-paper-account")
    if os.environ.get("GATEWAY_BROKER") == "ibkr_paper" and (risk.kill_active() or (now.hour == 21 and _once(f"reconcile:{day}"))):
        from . import ibkr
        try:
            br = ibkr.IBKRPaperBroker()
            try:
                if risk.kill_active():
                    n = br.cancel_open()
                    if n:
                        events.publish("risk.kill", "gateway", dict(motivo=f"KILL: annullati {n} ordini aperti dei pod"))
                else:
                    ibkr.reconcile(br)
            finally:
                br.close()
        except Exception as e:
            notes.append(f"ibkr pod: {str(e)[:80]}")
    # ordini dei pod: scadenza dei vecchi e invio del netto (fermo con KILL; fermo se IBKR configurato ma assente)
    gateway.expire_stale()
    if not risk.kill_active():
        try:
            fr = gateway.flush()
            if fr.get("al_broker") or fr.get("interni"):
                notes.append(f"gateway: {fr['al_broker']} al broker, {fr['interni']} incroci interni")
        except Exception as e:
            if _once(f"gwdown:{day}:{now.hour}"):        # un allarme l'ora, non uno per battito
                events.publish("risk.alert", "gateway", dict(cosa=f"esecuzione dei pod sospesa: {str(e)[:120]}", gravita=3))
            notes.append(f"gateway fermo: {str(e)[:80]}")
    # comitato di lungo periodo: valuta le rate della quota AI prima del giro di GERVA-Q (22:35 ora italiana)
    if os.environ.get("GERVA_SHADOW", "1") != "0" and now.hour >= 20 and _once(f"lt_eval:{day}"):
        try:
            from . import lt_committee
            pl = lt_committee.run()
            notes.append(f"comitato lungo: rata {pl['calendario']:.0%}, rinviati {len(pl['rinvii'])}")
        except Exception as e:                   # senza piano fresco GERVA-Q non compra nulla di nuovo
            notes.append(f"comitato lungo non eseguito: {str(e)[:60]}")
    # portafoglio ombra v4 contro v3: una volta al giorno dopo la chiusura USA (22 UTC), se i dati si scaricano
    if os.environ.get("GERVA_SHADOW", "1") != "0" and now.hour >= 22 and _once(f"shadow:{day}"):
        try:
            import subprocess, sys
            subprocess.run([sys.executable, os.path.join(paths.ROOT, "firm.py"), "data"], cwd=paths.ROOT,
                           capture_output=True, timeout=600)
            from . import shadow
            sh = shadow.update()
            notes.append(f"ombra: {sh.get('giorni', 0)} giorni, {sh.get('verdetto', '')[:60]}")
        except Exception as e:
            notes.append(f"ombra non aggiornata: {str(e)[:60]}")
    nf = news_feed.fetch_all()
    if nf["errori"] and not nf["nuove"]:
        notes.append("notizie: rete non disponibile o feed in errore")
    if now.hour >= 21 and _once(f"mark:{day}"):
        gateway.mark_day(day)
        reports.daily(day)                               # report della sera con le correzioni proposte
    if _once(f"vest:{day}"):
        compensation.vest(day)                           # maturano i bonus differiti scaduti
        meetings.resolve_due(day)                        # i fatti decidono chi aveva ragione nelle riunioni
    strike, why = budget.on_strike()
    if strike or not use_agents:
        events.publish("firm.heartbeat", "sistema", dict(sciopero=strike, motivo=why, semaforo=snap["semaforo"]),
                       audit_it=False)
        return dict(svegliati=[], note=notes + ([f"sciopero: {why}"] if strike else []), semaforo=snap["semaforo"])
    # ---- agenti, solo quando servono
    for c in db.q("SELECT id FROM commands WHERE status='ricevuto' ORDER BY id"):
        workflows.handle_command(c["id"])
        woke.append("capo")
    new_news = db.one("SELECT COUNT(*) n FROM news WHERE status='nuova'")["n"]
    if new_news >= 5 or (now.hour == 7 and new_news and _once(f"news:{day}")):
        workflows.news_cycle()
        woke += ["news_analyst", "fact_checker", "head_intel"]
    for a in snap["allarmi"]:                            # un pod vicino al taglio: riunione di rischio
        m = re.match(r"pod (\w+) vicino al taglio", a["cosa"])
        if m and _once(f"riskmeet:{m.group(1)}:{day}"):
            meetings.risk_meeting(m.group(1), a["cosa"])
            woke += ["cro", "capo"]
    alerts_sig = str(sorted(a["cosa"] for a in snap["allarmi"]))
    if alerts_sig != db.runtime_get("last_alerts", "") or (now.hour == 20 and _once(f"cro:{day}")):
        db.runtime_set("last_alerts", alerts_sig)
        if snap["allarmi"] or now.hour == 20:
            workflows.risk_review()
            woke.append("cro")
    if now.hour >= 9 and _once(f"research:{day}"):          # ogni giorno (6/11: era martedi' e giovedi')
        workflows.research_cycle()
        woke += ["senior_trend", "senior_validator"]
    from . import expectations
    try:
        expectations.resolve_outlooks(now)
        if not expectations.latest() and _once(f"exp-try:{day}:{now.hour}"):      # prima registrazione, appena i dati ci sono
            expectations.register(note="prima registrazione automatica")
        if now.hour >= 8 and expectations.latest() and _once(f"outlook:{day}"):
            expectations.outlook_cycle()
            woke.append("capo")
    except Exception as e:                                    # le aspettative non devono fermare il battito
        notes.append(f"aspettative: {str(e)[:80]}")
    if _once(f"signals-track:{day}:{now.hour // 4}"):                 # ogni 4 ore: obiettivo, stop, scadenza dei segnali
        try:
            from . import signals
            signals.track()
        except Exception as e:
            notes.append(f"segnali: {str(e)[:80]}")
    if now.hour >= 8 and _once(f"ideas:{day}"):                # ogni agente cerca idee, i superiori le portano su, il comitato vota
        try:
            from . import ideas
            r = ideas.daily()
            notes.append(f"idee: {len(r.get('nuove', []))} nuove, {r.get('salite', 0)} valutazioni, {len(r.get('comitato', []))} al comitato, {len(r.get('chiuse', []))} chiuse")
            woke += [n["a"] for n in r.get("nuove", []) if n.get("a")]
        except Exception as e:
            notes.append(f"idee non eseguite: {str(e)[:80]}")
    if now.hour >= 7 and _once(f"desk:{day}"):               # i capi desk propongono posizioni per il conto
        from . import desk
        try:
            r = desk.cycle()
            try:
                notes.append(f"leva gestita: x{desk.refresh_scale()['mult']}")
            except Exception:
                pass
            try:
                notes.append(f"ritmo di ingresso: {desk.refresh_pace()['max_turnover'] * 100:.0f}% del conto al giorno")
            except Exception:
                pass
            woke += r.get("desk", [])
            notes.append(f"desk: {len(r.get('targets', {}))} titoli proposti" if r.get("ok") else f"desk: {r.get('nota', '')}")
        except Exception as e:                               # un errore del desk non ferma il battito
            notes.append(f"desk non eseguito: {str(e)[:80]}")
    if now.weekday() == 6 and now.hour >= 17 and _once(f"sunday:{day}"):
        workflows.committee()
        workflows.talent_cycle()
        compensation.pay_salaries(day)
        woke += ["capo"]
        if now.day <= 7:
            # riunione di allocazione per ogni pod, poi la regola a shrinkage: vince la scelta piu' prudente
            decided = {}
            for p in pods.all_pods():
                if p["id"] != "pod_zero" and p["status"] != "chiuso":
                    decided[p["id"]] = meetings.allocation_meeting(p["id"]).get("decisione", "mantieni")
            for r in economy.reallocate(apply=False):
                d = decided.get(r["pod"], "mantieni")
                new = r["a"]
                if d == "riduci":
                    new = min(new, r["da"] * 0.5)
                elif d == "mantieni":
                    new = min(new, r["da"])
                if abs(new - r["da"]) > 1e-12:
                    pods.set_capital(r["pod"], new, f"riallocazione mensile (riunione: {d}; regola: {r['motivo']})", actor="economia")
            for p in pods.all_pods():
                if p["id"] != "pod_zero":
                    economy.distribute_bonus(p["id"])
    events.publish("firm.heartbeat", "sistema", dict(svegliati=woke, semaforo=snap["semaforo"]), audit_it=False)
    return dict(svegliati=woke, note=notes, semaforo=snap["semaforo"])
