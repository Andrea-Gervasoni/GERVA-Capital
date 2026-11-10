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
import base64
import calendar
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import threading
import time

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from firm import (db, events, registry, budget, risk, pods, gateway, economy, mailbox, tasks, trials,
                  scorekeeper as SK, pod_zero, audit, settings as S, building, meetings, reports, compensation, charts, fundrisk, expectations, signals)

HERE = os.path.dirname(os.path.abspath(__file__))
# Host ammessi (difesa dal DNS rebinding) e reti dei client: sul server il portale sta dietro un tunnel SSH
# e, in Docker, le richieste arrivano dal bridge interno: le reti si configurano, mai "tutti".
_PORT = os.environ.get("PORTAL_PORT", "8765")
ALLOWED_HOSTS = {f"127.0.0.1:{_PORT}", f"localhost:{_PORT}", "127.0.0.1", "localhost", "testserver"} | {
    h.strip() for h in os.environ.get("PORTAL_ALLOWED_HOSTS", "").split(",") if h.strip()}
CLIENT_NETS = [ipaddress.ip_network(n.strip()) for n in
               os.environ.get("PORTAL_CLIENT_NETS", "127.0.0.1/32,::1/128").split(",") if n.strip()]
PASSWORD_HASH = os.environ.get("PORTAL_PASSWORD_HASH", "")        # scrypt:sale:hash (python firm.py set-password)
SESSION_HOURS = 12
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                               "connect-src 'self' ws: wss:; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    "X-Frame-Options": "DENY", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()", "Cache-Control": "no-store",
}

app = FastAPI(title="GERVA Capital", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")


def _origin_ok(origin: str | None) -> bool:
    """Un browser manda Origin su WebSocket e POST: deve essere il portale stesso (niente siti terzi)."""
    if not origin:
        return True                      # client non-browser (curl, test): restano Host, rete e sessione
    from urllib.parse import urlparse
    u = urlparse(origin)
    return u.scheme in ("http", "https") and u.netloc in ALLOWED_HOSTS


def _client_ok(host: str) -> bool:
    if host == "testclient":
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(ip in n for n in CLIENT_NETS)


# ---------------------------------------------------------------------------
# Password e sessione (attive quando PORTAL_PASSWORD_HASH e' impostato: obbligatorio sul server)
# ---------------------------------------------------------------------------
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    # separatore ':' e non '$': Docker Compose interpola i '$' nei file env_file e troncherebbe l'hash
    return f"scrypt:{salt.hex()}:{h.hex()}"


def check_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.replace("$", ":").split(":")          # accetta anche il vecchio formato scrypt$..$..
        calc = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


def _session_key() -> bytes:
    """Chiave delle sessioni: sul server in un volume che SOLO il portale monta (GERVA_PORTAL_KEYS)."""
    from firm import paths
    d = os.environ.get("GERVA_PORTAL_KEYS", paths.VAR)
    p = os.path.join(d, "session.key")
    if not os.path.exists(p):
        os.makedirs(d, exist_ok=True)
        try:
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)   # 0600 fin dalla creazione
            with os.fdopen(fd, "wb") as f:
                f.write(secrets.token_bytes(32))
        except FileExistsError:
            pass
    return open(p, "rb").read()


def _make_session() -> str:
    exp = str(int(time.time()) + SESSION_HOURS * 3600)
    sig = hmac.new(_session_key(), exp.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{exp}.{sig}".encode()).decode()


def _session_ok(tok: str | None) -> bool:
    if not PASSWORD_HASH:
        return True
    try:
        exp, sig = base64.urlsafe_b64decode(tok.encode()).decode().split(".")
        good = hmac.new(_session_key(), exp.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, good) and int(exp) > time.time()
    except Exception:
        return False


_attempts: dict[str, list[float]] = {}
_scrypt_slots = asyncio.Semaphore(2)     # scrypt costa ~50 ms e 16 MB: al massimo due alla volta, fuori dal loop
# senza sessione si serve SOLO cio' che serve alla pagina di accesso (percorsi esatti, niente prefissi)
PUBLIC_PATHS = frozenset({"/login", "/logout", "/healthz", "/static/style.css", "/static/favicon.svg",
                          "/static/fonts/general-sans-400.woff2", "/static/fonts/general-sans-500.woff2",
                          "/static/fonts/general-sans-600.woff2", "/static/fonts/bodoni-moda-italic.woff2",
                          "/static/fonts/PressStart2P.woff2", "/static/fonts/VT323.woff2", "/static/fonts/bodoni-moda-roman.woff2"})


@app.middleware("http")
async def local_only(request: Request, call_next):
    host = request.headers.get("host", "")
    client = request.client.host if request.client else ""
    if host not in ALLOWED_HOSTS or not _client_ok(client):
        return JSONResponse({"errore": "accesso non consentito"}, status_code=403, headers=SECURITY_HEADERS)
    path = request.url.path
    if request.method not in ("GET", "HEAD", "OPTIONS") and not _origin_ok(request.headers.get("origin")):
        return JSONResponse({"errore": "origine non consentita"}, status_code=403, headers=SECURITY_HEADERS)
    if PASSWORD_HASH and path not in PUBLIC_PATHS and not _session_ok(request.cookies.get("gerva_session")):
        if path.startswith("/api"):
            return JSONResponse({"errore": "login richiesto"}, status_code=401, headers=SECURITY_HEADERS)
        return RedirectResponse("/login", status_code=303, headers=SECURITY_HEADERS)
    resp = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        resp.headers.setdefault(k, v)
    return resp


LOGIN_HTML = """<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>GERVA Capital — accesso</title><link rel="icon" href="/static/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/static/style.css"></head><body class="login">
<form method="post" action="/login" class="win loginbox"><div class="wh"><span class="login-mark">GERVA</span><span class="login-sub">CAPITAL · ACCESSO RISERVATO</span></div><div class="wb">
<p>{msg}</p><input type="password" name="password" autofocus autocomplete="current-password" placeholder="password">
<button>Entra</button></div></form></body></html>"""


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return LOGIN_HTML.format(msg="Inserisci la password del portale.")


@app.post("/login")
async def login(request: Request):
    ip = request.client.host if request.client else "?"
    now = time.time()
    recent = [t for t in _attempts.get(ip, []) if now - t < 300]
    if len(recent) >= 5:
        return HTMLResponse(LOGIN_HTML.format(msg="Troppi tentativi: riprova tra 5 minuti."), status_code=429)
    _attempts[ip] = recent + [now]                        # registrato PRIMA della verifica: niente corse in parallelo
    form = (await request.body()).decode()
    from urllib.parse import parse_qs
    pw = parse_qs(form).get("password", [""])[0][:1024]
    async with _scrypt_slots:
        ok = bool(PASSWORD_HASH) and await asyncio.to_thread(check_password, pw, PASSWORD_HASH)
    if not ok:
        await asyncio.sleep(1.0)                          # rallenta la forza bruta senza bloccare l'event loop
        return HTMLResponse(LOGIN_HTML.format(msg="Password errata."), status_code=401)
    _attempts.pop(ip, None)
    r = RedirectResponse("/", status_code=303)
    r.set_cookie("gerva_session", _make_session(), max_age=SESSION_HOURS * 3600, httponly=True, samesite="strict",
                 secure=os.environ.get("PORTAL_COOKIE_SECURE") == "1")
    return r


@app.get("/logout")
def logout():
    r = RedirectResponse("/login", status_code=303)
    r.delete_cookie("gerva_session", path="/")
    return r


@app.get("/healthz")
def healthz():
    return {"ok": True}


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


def _live_state() -> dict:
    """Il valore del conto e' 'in diretta' se la connessione in sola lettura ha scritto da meno di 90 secondi."""
    lv = db.runtime_get("ibkr.live") or {}
    try:
        age = time.time() - calendar.timegm(time.strptime(lv["ts"][:19], "%Y-%m-%dT%H:%M:%S")) if lv.get("ts") else None
    except (ValueError, KeyError):
        age = None
    return dict(fresca=bool(lv.get("nav") and age is not None and 0 <= age < 90 and not lv.get("errore")), eta_s=None if age is None else round(age),
                stima=bool(lv.get("stima")), errore=lv.get("errore"))


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
        diretta=_live_state(), telegram=db.runtime_get("telegram.alive"), portafogli=__import__("firm.blotter", fromlist=["x"]).totals(), nav=fb["nav"], nav_conto=gateway.pod_zero_nav(), nav_pod_simulati=fb["nav"] - gateway.pod_zero_nav(),
        pnl=fb["pnl"], capitale=gateway.capital_source(), capitale_iniziale=fb["capitale_iniziale"],
        semaforo=rk["semaforo"], kill=rk["kill"], allarmi=rk["allarmi"],
        budget_oggi=st["spent_today"], tetto_oggi=st["daily_cap"], budget_totale=st["spent_total"],
        tetto_totale=st["total_cap"], giorni_residui=st["days_left"], ritmo=st["pace_eur_day"],
        ledger=dict(righe=len(ledger), ultima=ledger[-1] if ledger else None, disponibile=pz["disponibile"]),
        posta_aperta=len(mailbox.items("aperta")), catena=audit.verify()["ok"], ibkr=_ibkr_state()))


def _ibkr_state():
    from firm import ibkr
    st = ibkr.status()
    sf = st["sfida"] or {}
    return dict(osservato=bool(sf), ok=sf.get("ok", False), conto=sf.get("conto"), nav=sf.get("nav_eur"), ts=sf.get("ts"),
                errore=sf.get("errore"), broker_pod=st["broker_pod"],
                scarti=len((st["riconciliazione"] or {}).get("scarti", [])))


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
        memoria=registry.memory(aid),
        serie=_series(aid),
        previsioni_lista=db.q("SELECT statement, prob, deadline, outcome FROM forecasts WHERE agent_id=? ORDER BY ts DESC LIMIT 15", (aid,)),
        persona=_people_row(a) if a["kind"] == "llm" else None,
        ufficio=next((o for o in building.offices() if o["agent_id"] == aid), None)))


def _series(aid):
    ev = db.q("SELECT substr(ts,1,10) d, AVG(CASE WHEN metric='brier' THEN 1 - value/0.25 ELSE value END) v FROM evaluations "
              "WHERE agent_id=? GROUP BY d ORDER BY d", (aid,))
    gc = db.q("SELECT substr(ts,1,10) d, SUM(amount) v FROM gc_ledger WHERE agent_id=? AND kind!='differito' GROUP BY d ORDER BY d", (aid,))
    run, cum = 0.0, []
    for r in gc:
        run += r["v"]
        cum.append(dict(d=r["d"], v=run))
    cost = db.q("SELECT day d, SUM(cost_eur) v FROM llm_calls WHERE agent_id=? GROUP BY day ORDER BY day", (aid,))
    return dict(punteggio=ev, gc=cum, costo=cost)


@app.get("/api/world")
def world():
    """Tutto cio' che serve alla scena: edificio, uffici e arredi per grado, agenti e cosa fanno."""
    lv = building.level()
    strike = budget.on_strike()[0]
    agents = {}
    for a in registry.all_agents():
        act = _activity(a["id"]) if a["kind"] == "llm" else dict(stato="automa", compito="", ts=None)
        if strike and a["kind"] == "llm":
            act["stato"] = "dorme"
        agents[a["id"]] = dict(id=a["id"], name=a["name"], role=a["role"], dept=a["dept"], kind=a["kind"],
                               status=a["status"], grade=a["grade"], grade_name=a["grade_name"], superior=a["superior"],
                               gc=economy.gc_balance(a["id"]) if a["kind"] == "llm" else 0, **act)
    meet = meetings.history(1)
    return _json(dict(edificio=lv, uffici=building.offices(), agenti=agents, sciopero=strike,
                      riunione_in_corso=meet[0] if meet and meet[0]["status"] == "in_corso" else None,
                      ultima_riunione=meet[0] if meet else None))


def _people_row(a):
    comp = SK.composite(a["id"], a["dept"])
    f = SK.agent_forecasts(a["id"])
    c = db.one("SELECT COALESCE(SUM(cost_eur),0) c, COUNT(*) n FROM llm_calls WHERE agent_id=?", (a["id"],))
    errs = db.one("SELECT COUNT(*) n FROM postmortems WHERE agent_id=?", (a["id"],))["n"]
    off = next((o for o in building.offices() if o["agent_id"] == a["id"]), {})
    return dict(id=a["id"], nome=a["name"], ruolo=a["role"], reparto=a["dept"], grado=a["grade"], grado_nome=a["grade_name"],
                ufficio=off.get("tier"), stato=a["status"], punteggio=comp["punteggio"], valutazioni=comp["n_valutazioni"],
                brier=f["brier"], previsioni=f["risolte"], giuste=f["giuste"], gc=economy.gc_balance(a["id"]),
                differito=economy.gc_unvested(a["id"]), costo=c["c"], chiamate=c["n"], errori=errs,
                stipendio=compensation.BASE_WEEKLY_GC[a["grade"]])


@app.get("/api/people")
def people():
    rows = [_people_row(a) for a in registry.all_agents() if a["kind"] == "llm"]
    for g in {r["grado"] for r in rows}:
        same = sorted([r for r in rows if r["grado"] == g], key=lambda r: -(r["punteggio"] or -1))
        for i, r in enumerate(same):
            r["rank_grado"] = f"{i + 1}/{len(same)}"
    return _json(rows)


@app.get("/api/meetings")
def meetings_list():
    return _json(meetings.history(30))


@app.get("/api/reports")
def reports_list():
    return _json(reports.listing())


@app.get("/api/report/{day}")
def report_day(day: str):
    r = reports.load(day) if day != "oggi" else None
    return _json(r or reports.daily(save=False))


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
    except (TypeError, ValueError) as e:
        raise HTTPException(400, str(e))
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


@app.get("/api/charts/list")
def charts_list():
    return _json(dict(simboli=charts.symbols()))


@app.get("/api/fund/overview")
def fund_overview(years: int = 1):
    """Rischio e aspettative del nostro fondo: portafoglio atteso, VaR, Monte Carlo a blocchi, stress test, contributi al rischio."""
    if years not in (1, 3):
        raise HTTPException(400, "years deve essere 1 o 3")
    try:
        return _json(fundrisk.overview(years))
    except Exception as e:                                   # dati incompleti: il portale lo dice, non si rompe
        return _json(dict(ok=False, motivo=f"{type(e).__name__}: {str(e)[:160]}"))


@app.get("/api/fund/kelly")
def fund_kelly(haircut: float = 0.5):
    """Leva ottima (Kelly) con i dati storici: crescita logaritmica, mediana a un anno e probabilita' di toccare il freno."""
    if not 0.1 <= haircut <= 1.0:
        raise HTTPException(400, "haircut tra 0,1 e 1")
    try:
        pf = fundrisk.portfolio()
        return _json(fundrisk.growth_curve(pf["pesi"], haircut=haircut) if pf["pesi"] else dict(ok=False, motivo="nessun peso"))
    except Exception as e:
        return _json(dict(ok=False, motivo=f"{type(e).__name__}: {str(e)[:160]}"))


@app.get("/api/blotter")
def api_blotter(venue: str = "", stato: str = ""):
    """La plancia: tutte le operazioni (azioni su IBKR, crypto su Alpaca), aperte e chiuse, con il valore dei due conti e il totale."""
    from firm import blotter as BL
    if venue not in ("", "ibkr", "alpaca") or stato not in ("", "aperta", "chiusa"):
        raise HTTPException(400, "filtro non valido")
    try:
        BL.sync_alpaca_throttled()
    except Exception:
        pass
    return _json(BL.overview(venue or None, stato or None))


@app.get("/api/blotter/story")
def api_blotter_story(key: str):
    """Come e' nata una operazione: chi l'ha pensata, chi l'ha controllata, il comitato, e cosa se n'e' imparato."""
    from firm import blotter as BL
    return _json(BL.story(key))


@app.get("/api/lessons")
def api_lessons(limit: int = 50):
    return _json(db.q("SELECT * FROM lessons ORDER BY id DESC LIMIT ?", (min(max(limit, 1), 200),)))


@app.get("/api/free")
def api_free():
    """Banco libero: regole di casa attive (all'inizio nessuna) e ultimi trade degli agenti."""
    from firm import free_desk as FD
    return _json(dict(regole=FD.active_rules(), classifica=FD.leaderboard(), telegram=db.runtime_get("telegram.alive"), trade=db.q("SELECT * FROM free_trades ORDER BY id DESC LIMIT 60"),
                      storia_regole=db.q("SELECT * FROM house_rules ORDER BY id DESC LIMIT 30")))


@app.get("/api/strategies")
def api_strategies():
    """Strategie in codice dai paper: fonte, ipotesi, backtest, accesa o spenta (lo decide il comitato)."""
    from firm import strategies as ST
    return _json(ST.overview())


@app.get("/api/conversations")
def api_conversations(limit: int = 60, agent: str = ""):
    """Tutte le conversazioni vere: riunioni, idee, ordini e compiti, segnali, banco libero, lezioni."""
    from firm import journal
    return _json(journal.conversations(min(max(limit, 1), 200), agent or None))


@app.get("/api/techniques")
def api_techniques():
    """Le tecniche del fondo: adottate, approvate, in prova, bocciate, con fonte."""
    from firm import journal
    return _json(journal.techniques())


@app.get("/api/tape")
def api_tape():
    """Il nastro in alto: S&P 500, VIX, BTC ed EUR/USD con la variazione dell'ultimo giorno, il regime e lo stato di Wall Street."""
    import datetime as _dt
    from zoneinfo import ZoneInfo
    out = dict(voci=[], regime=None, mercato="")
    try:
        c = charts.load_close()
        for nome, col, dec in (("S&P 500", "SPY", 2), ("VIX", "^VIX", 1), ("BTC", "BTC", 0), ("ETH", "ETH", 0), ("ORO", "GLD", 2), ("TREASURY 20A", "TLT", 2)):
            if c is not None and col in c:
                s_ = c[col].dropna()
                if len(s_) > 2:
                    out["voci"].append(dict(nome=nome, valore=round(float(s_.iloc[-1]), dec), var=round(float(s_.iloc[-1] / s_.iloc[-2] - 1), 4), dec=dec))
        out["regime"] = charts.regime(c).get("lettura")
    except Exception:
        pass
    ny = _dt.datetime.now(ZoneInfo("America/New_York"))
    aperta = ny.weekday() < 5 and (9, 30) <= (ny.hour, ny.minute) < (16, 0)
    out["mercato"] = f"NEW YORK {ny:%H:%M} · {'APERTA' if aperta else 'CHIUSA'} · MILANO {_dt.datetime.now(ZoneInfo('Europe/Rome')):%H:%M}"
    return _json(out)


@app.get("/api/terminal")
def api_terminal():
    from firm.terminal import snapshot
    return _json(snapshot())


@app.get("/api/health")
def api_health():
    """L'orologio del portale: tutti i programmi vivi? Se no, da quando e cosa manca."""
    from firm import health
    return _json(health.status())


@app.get("/api/feed")
def api_feed(limit: int = 60):
    """Gli ultimi eventi (piu' recenti per primi) per la Panoramica."""
    return _json(events.recent(None, None, min(max(limit, 1), 200)))


@app.get("/api/equity")
def api_equity():
    """Il conto contro l'S&P 500 (base 100), leggero: senza screener e correlazioni."""
    try:
        return _json(charts.equity_vs_benchmark())
    except Exception as e:
        return _json(dict(conto=[], spy=[], nota=f"{type(e).__name__}: {str(e)[:120]}"))


@app.get("/api/ideas/{iid}")
def api_idea(iid: int):
    from firm import ideas as ID
    d = ID.detail(iid)
    if not d:
        raise HTTPException(404)
    return _json(d)


@app.get("/api/ideas")
def api_ideas(limit: int = 40):
    """Le idee degli agenti con il loro percorso (chi le ha portate su, chi le ha votate, che esito hanno avuto) e le regole votate."""
    from firm import ideas as ID, rules as RU
    return _json(dict(idee=ID.listing(min(max(limit, 1), 100)), regole=RU.history(30)))


@app.get("/api/fund/expectation")
def fund_expectation():
    """I due ventagli registrati prima (modello e realistico), il valore reale del conto, e le previsioni del Capo."""
    try:
        return _json(expectations.overview())
    except Exception as e:
        return _json(dict(registrata=None, nota=f"{type(e).__name__}: {str(e)[:160]}"))


@app.post("/api/signals")
async def signals_new(request: Request):
    body = await request.json()
    text = (body.get("text") or "").strip()[:2000]
    if not text:
        raise HTTPException(400, "segnale vuoto")
    _cap(request)
    sid = signals.create(text, (body.get("fonte") or "sala segnali")[:60])

    def work():
        try:
            signals.process(sid)
        except Exception as e:                       # un errore non deve far cadere il portale ne' lasciare il segnale 'accettato'
            db.ex("UPDATE signals SET stato='osservato', motivo=? WHERE id=?", (f"analisi non riuscita: {str(e)[:120]}", sid))
    threading.Thread(target=work, daemon=True).start()
    return _json(dict(id=sid))


@app.get("/api/telegram/letti")
def telegram_letti():
    """Sale con AI: come e' stato capito ogni messaggio (segnale, aggiornamento, chiacchiere...) e perche'."""
    import os as _os
    log = db.runtime_get("telegram.ai_log") or []
    conta: dict = {}
    for x in log:
        conta[x["tipo"]] = conta.get(x["tipo"], 0) + 1
    return _json(dict(sale_ai=[s for s in _os.environ.get("TELEGRAM_CHATS_AI", "").split(",") if s.strip()], letti=log[:40], conteggio=conta))


@app.get("/api/sleeves")
def sleeves_overview():
    """Il portafoglio di strategie: metriche per sleeve, correlazioni, diversificazione (con le regole di onesta' sui pochi dati)."""
    from firm import sleeves
    return _json(sleeves.overview())


@app.get("/api/futures")
def futures_overview():
    """Il banco futures simulato: conto virtuale, posizioni, risultati per fascia di leva."""
    from firm import futures_sim
    return _json(futures_sim.overview())


@app.get("/api/signals")
def signals_list():
    return _json(dict(segnali=signals.listing(), statistiche=signals.stats(), posizioni=signals.active_targets()))


@app.get("/api/charts/series")
def charts_series(sym: str, days: int = 250):
    close = charts.load_close()
    if close is None or sym not in charts.symbols(close):
        raise HTTPException(404, "simbolo sconosciuto o dati non scaricati (firm.py data)")
    return _json(charts.indicators(sym, days, close))


@app.get("/api/charts/overview")
def charts_overview():
    close = charts.load_close()
    pos = [p["simbolo"] for p in ((db.runtime_get("ibkr.challenge") or {}).get("posizioni") or [])]
    desk_syms = list(((db.runtime_get("desk.overlay") or {}).get("targets") or {}))
    have = set(charts.symbols(close))
    mine = [x for x in dict.fromkeys(desk_syms + pos) if x in have]
    return _json(dict(portafoglio=mine, simboli=sorted(have), regime=charts.regime(close), equity=charts.equity_vs_benchmark(close),
                      screener=charts.screener(close, 400, mine) if close is not None else [],
                      corr=charts.correlation(["SPY", "QQQ", "TLT", "GLD"] + desk_syms + pos, 120, close)))


@app.get("/api/desk")
def desk_view():
    """Le posizioni proposte dai capi desk (validate dal codice) che GERVA-Q compra sopra il modello."""
    doc = db.runtime_get("desk.overlay") or {}
    return _json(dict(data=doc.get("data"), targets=doc.get("targets", {}), per_desk=doc.get("per_desk", {}),
                      regole=doc.get("regole", {}), pod_zero=pod_zero.summary()))


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
    client = websocket.client.host if websocket.client else ""
    if host not in ALLOWED_HOSTS or not _client_ok(client) or not _origin_ok(websocket.headers.get("origin")) \
            or not _session_ok(websocket.cookies.get("gerva_session")):
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
