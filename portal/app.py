"""
Portale di GERVA Capital — solo 127.0.0.1:8765. Mostra e comanda; non esegue ordini.

Sicurezza:
  * ascolta solo su 127.0.0.1 (firm.py portal) e rifiuta richieste con Host diverso da
    127.0.0.1/localhost (difesa dal DNS rebinding);
  * le scritture (Impostazioni, Posta del Capo, Sciopero, KILL) richiedono l'header X-Andrea-Token,
    letto da var/andrea.token e inserito nella pagina servita al browser locale. Una pagina di un'altra
    origine non puo' leggerlo (same-origin, nessun header CORS) ne' inviare l'header (preflight bloccato);
  * nessun endpoint chiama il Gateway: lo verifica tests/test_portal.py.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from firm import (db, events, registry, budget, risk, pods, gateway, economy, mailbox, tasks, trials,
                  scorekeeper as SK, pod_zero, audit, settings as S)

HERE = os.path.dirname(os.path.abspath(__file__))
ALLOWED_HOSTS = {"127.0.0.1:8765", "localhost:8765", "127.0.0.1", "localhost", "testserver"}

app = FastAPI(title="GERVA Capital", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")


@app.middleware("http")
async def local_only(request: Request, call_next):
    host = request.headers.get("host", "")
    client = request.client.host if request.client else ""
    if host not in ALLOWED_HOSTS or client not in ("127.0.0.1", "::1", "testclient"):
        return JSONResponse({"errore": "solo accesso locale"}, status_code=403)
    return await call_next(request)


def _cap(request: Request) -> S.AndreaCapability:
    try:
        return S.AndreaCapability(request.headers.get("x-andrea-token", ""))
    except S.SettingsPermissionError:
        raise HTTPException(403, "solo Andrea, dal portale locale")


def _json(x):
    """JSON sicuro per il browser: inf/NaN (es. giorni di autonomia senza spesa) diventano null."""
    def fix(o):
        if isinstance(o, float) and (o != o or o in (float("inf"), float("-inf"))):
            return None
        if isinstance(o, dict):
            return {k: fix(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [fix(v) for v in o]
        return o
    return JSONResponse(fix(json.loads(json.dumps(x, default=str))))


# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index():
    html = open(os.path.join(HERE, "static", "index.html")).read()
    return html.replace("{{ANDREA_TOKEN}}", S.ensure_token())


@app.get("/api/state")
def state():
    st = budget.status()
    rk = risk.snapshot()
    fb = gateway.firm_book()
    pz = pod_zero.summary()
    ledger = pz["ledger_sfida"]
    return _json(dict(
        modalita="PAPER", live_bloccato=True, sciopero=st["strike"], motivo_sciopero=st["strike_reason"],
        simulato=not os.environ.get("ANTHROPIC_API_KEY"), demo=bool(db.runtime_get("demo", False)),
        nav=fb["nav"], pnl=fb["pnl"], semaforo=rk["semaforo"], kill=rk["kill"], allarmi=rk["allarmi"],
        budget_oggi=st["spent_today"], tetto_oggi=st["daily_cap"], budget_totale=st["spent_total"],
        tetto_totale=st["total_cap"], giorni_residui=st["days_left"], ritmo=st["pace_eur_day"],
        ledger=dict(righe=len(ledger), ultima=ledger[-1] if ledger else None, disponibile=pz["disponibile"]),
        posta_aperta=len(mailbox.items("aperta")), catena=audit.verify()["ok"]))


def _activity(aid: str) -> dict:
    ev = events.recent(aid, ("agent.status",), limit=1)
    if ev:
        return dict(stato=ev[0]["payload"].get("stato", "lavora"), compito=ev[0]["payload"].get("compito", ""),
                    ts=ev[0]["ts"])
    return dict(stato="attesa", compito="", ts=None)


@app.get("/api/office")
def office():
    out = []
    strike = budget.on_strike()[0]
    for a in registry.all_agents():
        act = _activity(a["id"]) if a["kind"] == "llm" else dict(stato="automa", compito="", ts=None)
        if strike and a["kind"] == "llm":
            act["stato"] = "dorme"
        out.append(dict(id=a["id"], name=a["name"], role=a["role"], dept=a["dept"], room=a["room"], desk=a["desk"],
                        kind=a["kind"], status=a["status"], grade=a["grade_name"], superior=a["superior"], **act))
    return _json(out)


@app.get("/api/agent/{aid}")
def agent(aid: str):
    a = registry.get(aid)
    if not a:
        raise HTTPException(404)
    llm_today = db.one("SELECT COALESCE(SUM(input_tokens),0) i, COALESCE(SUM(output_tokens),0) o, "
                       "COALESCE(SUM(cost_eur),0) c FROM llm_calls WHERE agent_id=? AND day=?", (aid, db.today()))
    llm_all = db.one("SELECT COALESCE(SUM(input_tokens),0) i, COALESCE(SUM(output_tokens),0) o, "
                     "COALESCE(SUM(cost_eur),0) c, COUNT(*) n FROM llm_calls WHERE agent_id=?", (aid,))
    evals = db.q("SELECT metric, COUNT(*) n, AVG(value) media FROM evaluations WHERE agent_id=? GROUP BY metric", (aid,))
    return _json(dict(
        profilo=dict(id=a["id"], nome=a["name"], ruolo=a["role"], reparto=a["dept"], grado=a["grade_name"],
                     superiore=a["superior"], subordinati=registry.subordinates(aid), tipo=a["kind"],
                     stato=a["status"], modello=registry.model_for(a) if a["kind"] == "llm" else "codice deterministico",
                     budget_giorno=a["daily_budget_eur"], strumenti=a["profile"].get("tools", []),
                     filosofia=a["profile"].get("philosophy"), versione_prompt=a["profile"].get("prompt_version")),
        ora=dict(attivita=_activity(aid), eventi=events.recent(aid, limit=10)),
        risultati=dict(punteggio=SK.composite(aid, a["dept"]), previsioni=SK.agent_forecasts(aid), metriche=evals),
        errori=db.q("SELECT * FROM postmortems WHERE agent_id=? ORDER BY id DESC", (aid,)),
        carriera=registry.career(aid),
        costi=dict(oggi=llm_today, totale=llm_all, gc=economy.gc_history(aid)),
        memoria=registry.memory(aid)))


@app.get("/api/org")
def org():
    return _json(registry.org_tree())


@app.post("/api/command")
async def command(request: Request):
    body = await request.json()
    text = (body.get("text") or "").strip()[:2000]
    if not text:
        raise HTTPException(400, "ordine vuoto")
    _cap(request)
    cid = tasks.new_command(text)

    def work():
        from firm import workflows
        try:
            workflows.handle_command(cid)
        except Exception as e:                    # un errore non deve far cadere il portale
            db.ex("UPDATE commands SET status='errore', answer=? WHERE id=?", (str(e)[:300], cid))
    threading.Thread(target=work, daemon=True).start()
    return _json(dict(id=cid))


@app.get("/api/commands")
def commands():
    return _json(tasks.commands())


@app.get("/api/tasks/{order_id}")
def task_tree(order_id: int):
    return _json(tasks.tree(order_id))


@app.get("/api/mailbox")
def mail():
    return _json(mailbox.items())


@app.post("/api/mailbox/{mid}")
async def mail_decide(mid: int, request: Request):
    body = await request.json()
    return _json(mailbox.decide(mid, body.get("choice", "__rimanda__"), _cap(request)))


@app.get("/api/settings")
def get_settings():
    return _json(dict(impostazioni=S.all_settings(), limiti=S.risk_limits(), budget=budget.status()))


@app.post("/api/settings")
async def set_setting(request: Request):
    body = await request.json()
    cap = _cap(request)
    try:
        if body.get("kind") == "risk":
            S.set_risk_limit(body["key"], body["value"], cap)
        else:
            if body["key"] == "firm.mode" and body["value"] != "paper":
                raise HTTPException(400, "LIVE e' bloccato: servono i cancelli 13-15 e la firma dei titolari")
            S.set(body["key"], body["value"], cap)
    except KeyError as e:
        raise HTTPException(400, f"impostazione sconosciuta: {e}")
    return _json(dict(ok=True))


@app.post("/api/strike")
async def strike(request: Request):
    body = await request.json()
    cap = _cap(request)
    S.set("firm.strike", bool(body.get("on")), cap)
    if not body.get("on"):
        db.runtime_set("budget.auto_strike", None)
    return _json(dict(ok=True))


@app.post("/api/kill")
async def kill(request: Request):
    body = await request.json()
    cap = _cap(request)
    if body.get("on"):
        risk.engage_kill("andrea", "KILL dal portale", cap)
    else:
        risk.release_kill(cap)
    return _json(dict(ok=True))


@app.get("/api/pods")
def pods_view():
    lb = economy.leaderboard()
    books = {p["id"]: gateway.pod_book(p["id"]) for p in pods.all_pods() if p["id"] != "pod_zero"}
    return _json(dict(classifica=lb, libri=books, ordini=gateway.orders(40), pod_zero=pod_zero.summary(),
                      correlazione=pods.mean_pod_correlation()))


@app.get("/api/research")
def research():
    rows = db.q("SELECT * FROM research ORDER BY ts DESC LIMIT 30")
    for r in rows:
        for k in ("gate", "validation", "decision"):
            try:
                r[k] = json.loads(r[k]) if r[k] else None
            except json.JSONDecodeError:
                pass
    return _json(dict(fascicoli=rows, prove=trials.counts()))


@app.get("/api/events")
def ev(since: int = 0, limit: int = 100):
    return _json(events.since(since, limit))


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    host = websocket.headers.get("host", "")
    if host not in ALLOWED_HOSTS:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    last = (db.one("SELECT MAX(id) m FROM events") or {}).get("m") or 0
    last = max(0, last - 30)
    try:
        while True:
            new = events.since(last, 100)
            if new:
                last = new[-1]["id"]
                await websocket.send_text(json.dumps(new, default=str))
            await asyncio.sleep(1.0)
    except (WebSocketDisconnect, RuntimeError):
        return
