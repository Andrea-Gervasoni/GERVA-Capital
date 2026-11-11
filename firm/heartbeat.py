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

Isolamento dei guasti: ogni passo gira in _step(), con il suo try/except. Un'eccezione diventa una nota del battito e un evento
`heartbeat.error` (mai un `pass` silenzioso) e NON ferma i passi dopo. I passi che proteggono il conto (motore di rischio, KILL,
regole di drawdown, stop e obiettivi dei segnali) girano per primi, prima di ogni ribilanciamento e di ogni lavoro degli agenti.
Un passo "una volta al giorno" che fallisce libera la sua chiave: si riprova al battito dopo (al massimo MAX_TRIES volte).
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sys

from . import settings as S
from . import db, events, paths, risk, pods, budget, audit, gateway, news_feed, mailbox, workflows, economy, compensation, meetings, reports, registry


def _once(key: str) -> bool:
    """True la prima volta che `key` viene chiesto (per giorno/settimana)."""
    # atomico: due battiti concorrenti (run + heartbeat manuale) non pagano due volte
    cur = db.connect().execute("INSERT OR IGNORE INTO runtime(key,value,updated_ts) VALUES(?,?,?)",
                               (f"once:{key}", db.dumps(db.now_iso()), db.now_iso()))
    return cur.rowcount == 1


MAX_TRIES = 3                      # un passo "una volta" che fallisce si riprova al battito dopo, ma non all'infinito


def _release(key: str) -> None:
    """Il lavoro legato alla chiave non e' riuscito: la chiave torna libera (resta presa solo dopo un successo)."""
    db.ex("DELETE FROM runtime WHERE key=?", (f"once:{key}",))


def _step(name: str, fn, notes: list, once: str | None = None, default=None):
    """Un passo del battito, isolato dagli altri. Con `once` il passo gira una volta sola per chiave; la chiave si prende prima
    (atomica: due battiti concorrenti non fanno il lavoro due volte) ma si LIBERA se il lavoro fallisce, fino a MAX_TRIES tentativi.
    L'eccezione non si perde: nota del battito + evento `heartbeat.error` (uno l'ora per passo, per non riempire il registro)."""
    if once is not None and not _once(once):
        return default
    try:
        return fn()
    except Exception as e:
        tries = 1
        try:
            if once is not None:
                tries = int(db.runtime_get(f"tries:{once}") or 0) + 1
                db.runtime_set(f"tries:{once}", tries)
                if tries < MAX_TRIES:
                    _release(once)
            notes.append(f"{name} non riuscito: {str(e)[:80]}")
            if _once(f"err:{name}:{db.now_iso()[:13]}"):
                events.publish("heartbeat.error", "sistema", dict(passo=name, errore=f"{type(e).__name__}: {str(e)[:200]}", tentativo=tries))
        except Exception as e2:                           # nemmeno il registro risponde: resta almeno la riga nel log del processo
            print(f"battito: passo {name} fallito ({e!r}) e non registrato ({e2!r})", file=sys.stderr)
        return default


def beat(now: dt.datetime | None = None, use_agents: bool = True) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    day = now.strftime("%Y-%m-%d")
    woke, notes = [], []
    _step("orologio", lambda: db.runtime_set("heartbeat.alive", db.now_iso()), notes)     # l'orologio del portale: il battito gira
    # ---- prima di tutto cio' che protegge il conto: rischio, KILL, drawdown, stop dei segnali
    snap = _step("motore di rischio", risk.snapshot, notes)
    if snap is None:                                       # senza il semaforo non si finge il verde: rosso, e lo si dice
        snap = dict(semaforo="rosso", kill=risk.kill_active(), allarmi=[], errore=True)
        if _once(f"riskdown:{day}:{now.hour}"):
            _step("allarme rischio", lambda: events.publish("risk.alert", "risk_engine", dict(
                cosa="il motore di rischio non ha completato il controllo: drawdown e KILL automatico NON sono verificati", gravita=5)), notes)
    if risk.kill_active():                                 # KILL: finche' e' attivo il conto Alpaca resta vuoto (e GERVA-Q ha il suo file KILL)
        k = _step("KILL", lambda: risk.on_kill("KILL attivo"), notes) or {}
        al = k.get("alpaca") or {}
        if al.get("posizioni_chiuse") or al.get("ordini_annullati") or al.get("errori"):
            notes.append(f"KILL: Alpaca {al.get('posizioni_chiuse', 0)} posizioni chiuse, {al.get('ordini_annullati', 0)} ordini annullati"
                         + (f", errori: {al['errori']}" if al.get("errori") else ""))
    acts = _step("regole drawdown", pods.apply_drawdown_rules, notes)
    if acts:
        notes.append(f"regole drawdown: {acts}")

    def _track():
        from . import signals
        return signals.track()
    # stop, obiettivo e scadenza dei segnali: a ogni battito (15 minuti), PRIMA del ribilanciamento e anche in sciopero (e' codice, non agenti)
    _step("segnali", _track, notes, once=f"signals-track:{day}:{now.hour}:{now.minute // 15}")
    _step("budget", budget.runway_check, notes)

    def _audit():
        v = audit.verify()
        if not v["ok"]:
            events.publish("risk.alert", "auditor", dict(cosa=f"catena di hash rotta alla voce {v['prima_rottura']}",
                                                         gravita=5))
    _step("catena di hash", _audit, notes, once=f"audit:{day}")
    # IBKR: osservazione in sola lettura del conto della sfida (il portale non si collega mai al broker)
    if os.environ.get("IBKR_OBSERVE") == "1":            # sul Mac; sul server lo fa il container 'observer'
        def _observe():
            from . import ibkr
            obs = ibkr.observe_challenge()                          # (non chiamarla snap: e' lo snapshot del rischio)
            if obs and obs.get("ok") and (obs.get("nav_eur") or 0) > 0:          # un punto per battito: serve al grafico del conto
                db.ex("INSERT INTO nav_ticks(ts,nav) VALUES(?,?)", (db.now_iso(), float(obs["nav_eur"])))
        _step("osservazione IBKR", _observe, notes)
    _step("pod", pods.ensure_pods, notes)
    _step("impostazioni", S.refresh_defaults, notes)

    def _rebalance():
        from . import crypto_venue
        if crypto_venue.configured():
            r = crypto_venue.rebalance()                   # crypto: 24 ore su 24, a ogni battito
            if not r.get("ok"):
                notes.append(f"sede crypto: {str(r.get('nota', ''))[:80]}")
    _step("ribilanciamento crypto", _rebalance, notes)
    _step("profili", registry.sync_if_profiles_changed, notes)
    if os.environ.get("IBKR_CHALLENGE_ACCOUNT") and pods.enabled():
        if not os.environ.get("IBKR_FIRM_ACCOUNT"):
            # i pod non possono usare il conto della sfida (live.py vende tutto cio' che non e' nel suo target):
            # serve un secondo conto paper, cioe' una nuova credenziale -> grande richiesta n.4
            _step("richiesta secondo conto", lambda: mailbox.big_request(
                4, "Secondo conto paper IBKR per i pod?",
                "I pod della societa' oggi eseguono sul broker simulato. Per eseguire su IBKR serve un SECONDO conto paper "
                "(DU...) distinto da quello della sfida: GERVA-Q vende ogni posizione che non e' nel suo target, quindi "
                "ordini dei pod sullo stesso conto verrebbero liquidati la sera stessa e violerebbero REGOLE_SFIDA §1.",
                ["Aprire un secondo conto paper (gratuito) e mettere il login in secrets/ibgw-firm.env",
                 "Restare sul broker simulato"],
                "Restare sul simulato finche' i pod non hanno 3 mesi di track record forward: il secondo conto aggiunge "
                "realismo di esecuzione, non rendimento",
                "Pod sul broker simulato; GERVA-Q invariato sul suo conto", dedup_key="ibkr-second-paper-account"), notes)
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
            if not risk.kill_active():
                _release(f"reconcile:{day}")             # la riconciliazione non e' riuscita: si riprova (la finestra e' l'ora 21)
            if _once(f"err:ibkr pod:{day}:{now.hour}"):
                _step("allarme ibkr", lambda: events.publish("heartbeat.error", "sistema", dict(passo="ibkr pod", errore=f"{type(e).__name__}: {str(e)[:200]}")), notes)
    # ordini dei pod: scadenza dei vecchi e invio del netto (fermo con KILL; fermo se IBKR configurato ma assente)
    _step("scadenza ordini", gateway.expire_stale, notes)
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
    if os.environ.get("GERVA_SHADOW", "1") != "0" and now.hour >= 20:
        def _lt():
            from . import lt_committee
            pl = lt_committee.run()
            notes.append(f"comitato lungo: rata {pl['calendario']:.0%}, rinviati {len(pl['rinvii'])}")
        _step("comitato lungo", _lt, notes, once=f"lt_eval:{day}")       # senza piano fresco GERVA-Q non compra nulla di nuovo
    # portafoglio ombra v4 contro v3: una volta al giorno dopo la chiusura USA (22 UTC), se i dati si scaricano
    if os.environ.get("GERVA_SHADOW", "1") != "0" and now.hour >= 22:
        def _shadow():
            import subprocess
            subprocess.run([sys.executable, os.path.join(paths.ROOT, "firm.py"), "data"], cwd=paths.ROOT,
                           capture_output=True, timeout=600)
            from . import shadow
            sh = shadow.update()
            notes.append(f"ombra: {sh.get('giorni', 0)} giorni, {sh.get('verdetto', '')[:60]}")
        _step("ombra", _shadow, notes, once=f"shadow:{day}")
    nf = _step("notizie", news_feed.fetch_all, notes) or dict(errori=[], nuove=0)
    if nf["errori"] and not nf["nuove"]:
        notes.append("notizie: rete non disponibile o feed in errore")
    if now.hour >= 21:
        _step("marcatura NAV", lambda: gateway.mark_day(day), notes, once=f"mark:{day}")
        _step("report della sera", lambda: reports.daily(day), notes, once=f"report:{day}")   # con le correzioni proposte
    _step("bonus differiti", lambda: compensation.vest(day), notes, once=f"vest:{day}")       # maturano i bonus differiti scaduti
    _step("esiti riunioni", lambda: meetings.resolve_due(day), notes, once=f"meet-resolve:{day}")   # i fatti decidono chi aveva ragione nelle riunioni

    def _blotter():
        from . import blotter
        return blotter.sync_alpaca()
    _step("plancia Alpaca", _blotter, notes)                                                  # fill e conto Alpaca aggiornati ad ogni battito
    strike, why = _step("sciopero", budget.on_strike, notes, default=(True, "controllo del budget non riuscito"))
    if strike or not use_agents:
        _step("evento battito", lambda: events.publish("firm.heartbeat", "sistema", dict(sciopero=strike, motivo=why, semaforo=snap["semaforo"]),
                                                       audit_it=False), notes)
        return dict(svegliati=[], note=notes + ([f"sciopero: {why}"] if strike else []), semaforo=snap["semaforo"])
    # ---- agenti, solo quando servono
    for c in _step("comandi", lambda: db.q("SELECT id FROM commands WHERE status='ricevuto' ORDER BY id"), notes, default=[]):
        _step("comando", lambda c=c: workflows.handle_command(c["id"]), notes)
        woke.append("capo")
    new_news = _step("conteggio notizie", lambda: db.one("SELECT COUNT(*) n FROM news WHERE status='nuova'")["n"], notes, default=0)
    if new_news >= 5:
        _step("redazione", workflows.news_cycle, notes)
        woke += ["news_analyst", "fact_checker", "head_intel"]
    elif now.hour == 7 and new_news:
        if _step("redazione", lambda: workflows.news_cycle() or True, notes, once=f"news:{day}"):
            woke += ["news_analyst", "fact_checker", "head_intel"]
    for a in snap["allarmi"]:                            # un pod vicino al taglio: riunione di rischio
        m = re.match(r"pod (\w+) vicino al taglio", a["cosa"])
        if m:
            if _step("riunione di rischio", lambda m=m, a=a: meetings.risk_meeting(m.group(1), a["cosa"]) or True, notes, once=f"riskmeet:{m.group(1)}:{day}"):
                woke += ["cro", "capo"]
    alerts_sig = str(sorted(a["cosa"] for a in snap["allarmi"]))
    changed = alerts_sig != db.runtime_get("last_alerts", "")
    if changed:
        db.runtime_set("last_alerts", alerts_sig)
    if changed and (snap["allarmi"] or now.hour == 20):
        _step("revisione del rischio", workflows.risk_review, notes)
        woke.append("cro")
    elif now.hour == 20:
        if _step("revisione del rischio", lambda: workflows.risk_review() or True, notes, once=f"cro:{day}"):
            woke.append("cro")
    if now.hour >= 9:                                       # ogni giorno (6/11: era martedi' e giovedi')
        if _step("ricerca", lambda: workflows.research_cycle() or True, notes, once=f"research:{day}"):
            woke += ["senior_trend", "senior_validator"]
    from . import expectations
    _step("previsioni: esiti", lambda: expectations.resolve_outlooks(now), notes)
    has_exp = _step("aspettative", expectations.latest, notes)
    if not has_exp and _step("valore del conto", expectations._nav_now, notes, default=0) > 0:      # prima registrazione, appena i dati ci sono
        has_exp = _step("aspettative: prima registrazione", lambda: expectations.register(note="prima registrazione automatica"), notes,
                        once=f"exp-try:{day}:{now.hour}")
    if now.hour >= 8 and has_exp:
        if _step("previsione del Capo", lambda: expectations.outlook_cycle() or True, notes, once=f"outlook:{day}"):
            woke.append("capo")
    if now.hour >= 20:                                         # la sera: argomenti a favore e contro per ogni operazione nuova
        def _dossier():
            from . import dossier
            notes.append(f"revisione trade: {dossier.review_daily().get('riviste', 0)} operazioni")
        _step("revisione trade", _dossier, notes, once=f"revisione-trade:{day}")
    if now.hour >= 21:                                         # a fine giornata: cosa si e' imparato dalle operazioni chiuse
        def _lessons():
            from . import lessons
            r = lessons.daily()
            notes.append(f"lezioni: {r.get('lezioni', 0)} da {len(r.get('agenti', []))} agenti")
        _step("lezioni", _lessons, notes, once=f"lezioni:{day}")
    if now.hour >= 8:                                          # ogni agente cerca idee, i superiori le portano su, il comitato vota
        def _ideas():
            from . import ideas
            r = ideas.daily()
            notes.append(f"idee: {len(r.get('nuove', []))} nuove, {r.get('salite', 0)} valutazioni, {len(r.get('comitato', []))} al comitato, {len(r.get('chiuse', []))} chiuse")
            woke.extend(n["a"] for n in r.get("nuove", []) if n.get("a"))
        _step("idee", _ideas, notes, once=f"ideas:{day}")

    def _telegram():                                           # Telegram deve ascoltare: se tace da piu' di 10 minuti lo si dice (una volta l'ora)
        tg = db.runtime_get("telegram.alive") or {}
        if (os.environ.get("TELEGRAM_CHATS") or os.environ.get("TELEGRAM_CHATS_AI")) and (not tg.get("ts") or (now - dt.datetime.fromisoformat(tg["ts"].replace("Z", "+00:00"))).total_seconds() > 600 or tg.get("collegato") is False):
            if _once(f"telegram-giu:{now:%Y-%m-%dT%H}"):
                events.publish("risk.alert", "telegram", dict(cosa="il lettore di Telegram non ascolta da piu' di 10 minuti: i segnali si perdono (rete del Mac? processo fermo?)", gravita=3))
                notes.append("ATTENZIONE: Telegram non ascolta")
    _step("controllo Telegram", _telegram, notes)
    if now.hour >= 7:
        from . import desk
        r = _step("leva gestita", desk.refresh_scale, notes, once=f"scala:{day}")              # leva gestita per volatilita' (se accesa)
        if r:
            notes.append(f"leva gestita: x{r['mult']}")
        r = _step("ritmo di ingresso", desk.refresh_pace, notes, once=f"ritmo:{day}")          # lo decide una riunione (ogni 7 giorni o se cambia il mercato)
        if r:
            notes.append(f"ritmo di ingresso: {r['max_turnover'] * 100:.0f}% del conto al giorno" + (" (nuova riunione)" if r.get("nuova_riunione") else ""))
        r = _step("desk", desk.cycle, notes, once=f"desk:{day}")                               # i capi desk propongono posizioni per il conto
        if r:
            woke += r.get("desk", [])
            notes.append(f"desk: {len(r.get('targets', {}))} titoli proposti" if r.get("ok") else f"desk: {r.get('nota', '')}")
    if now.weekday() == 6 and now.hour >= 17:
        # la domenica ogni passo ha la SUA chiave: se uno fallisce gli altri girano lo stesso e solo quello si riprova.
        # `sunday:{day}` resta la chiave d'ingresso: una domenica gia' fatta da un battito precedente a questa versione non si rifa'.
        if _once(f"sunday:{day}"):
            db.runtime_set(f"sunday.steps:{day}", db.now_iso())
            woke += ["capo"]
    if now.weekday() == 6 and now.hour >= 17 and db.runtime_get(f"sunday.steps:{day}"):
        _step("comitato", workflows.committee, notes, once=f"sunday-comitato:{day}")
        _step("ciclo talent", workflows.talent_cycle, notes, once=f"sunday-talent:{day}")
        _step("stipendi", lambda: compensation.pay_salaries(day), notes, once=f"sunday-stipendi:{day}")
        if now.day <= 7:
            def _alloc():
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
            _step("riallocazione mensile", _alloc, notes, once=f"sunday-riallocazione:{day}")
    _step("evento battito", lambda: events.publish("firm.heartbeat", "sistema", dict(svegliati=woke, semaforo=snap["semaforo"]), audit_it=False), notes)
    return dict(svegliati=woke, note=notes, semaforo=snap["semaforo"])
