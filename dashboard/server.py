"""
Dashboard di GERVA Capital — piccolo server FastAPI, pensato per girare su 127.0.0.1.

Che cosa fa:
  * serve la pagina statica (dashboard/static/) su "/";
  * GET  /api/v1/snapshot  restituisce lo snapshot JSON scritto dal motore (env GERVA_SNAPSHOT);
                           se il file non esiste serve l'esempio, marcato "DEMO: dati di esempio";
  * GET  /api/v1/health    {"ok": true, "snapshot_age_s": ...};
  * GET  /api/v1/quant     i risultati della ricerca (env GERVA_QUANT, default research/v5/quant.json): tutto SIMULATO;
  * POST /api/v1/kill      crea in modo atomico il file KILL (env GERVA_KILL_FILE). Non lo cancella mai.

Sicurezza:
  * ascolta su 127.0.0.1 (GERVA_DASH_HOST / GERVA_DASH_PORT per cambiare);
  * rifiuta le richieste con un Host diverso da localhost/127.0.0.1 (difesa dal DNS rebinding);
    altri nomi si aggiungono con GERVA_DASH_ALLOWED_HOSTS, mai "tutti";
  * il KILL richiede l'header X-Gerva-Token uguale a GERVA_DASH_TOKEN (confronto a tempo costante);
    senza GERVA_DASH_TOKEN l'endpoint è spento (503);
  * intestazioni di sicurezza su ogni risposta (CSP 'self', niente script inline, niente frame);
  * nessun segreto, variabile d'ambiente o percorso del disco nelle risposte.

Avvio:  python -m dashboard.server      oppure      uvicorn dashboard.server:app --port 8787
"""
from __future__ import annotations

import contextlib
import hmac
import json
import math
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STATIC = HERE / "static"
SAMPLE = STATIC / "sample_snapshot.json"

DEMO_LABEL = "DEMO: dati di esempio"
MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024       # uno snapshot più grande di così è un errore, non un dato
MAX_KILL_BODY = 4096
MAX_REASON_CHARS = 300
DEFAULT_REASON = "attivato dalla dashboard"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]"})

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; "
        "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}


# ---------------------------------------------------------------------------
# Configurazione: letta a ogni richiesta, così cambia senza riavviare (e i test la possono isolare)
# ---------------------------------------------------------------------------
def snapshot_path() -> Path:
    raw = os.environ.get("GERVA_SNAPSHOT", "").strip()
    return Path(raw).expanduser() if raw else ROOT / "var" / "gerva" / "snapshot.json"


def quant_path() -> Path:
    raw = os.environ.get("GERVA_QUANT", "").strip()
    return Path(raw).expanduser() if raw else ROOT / "research" / "v5" / "quant.json"


def kill_path() -> Path:
    raw = os.environ.get("GERVA_KILL_FILE", "").strip()
    return Path(raw).expanduser() if raw else ROOT / "var" / "gerva" / "KILL"


def _token() -> str:
    return os.environ.get("GERVA_DASH_TOKEN", "")


def _extra_hosts() -> set[str]:
    return {h.strip().lower() for h in os.environ.get("GERVA_DASH_ALLOWED_HOSTS", "").split(",") if h.strip()}


# ---------------------------------------------------------------------------
# Host e origine
# ---------------------------------------------------------------------------
_HOST_RE = re.compile(r"^(\[[0-9a-f:.]+\]|[a-z0-9]([a-z0-9.-]*[a-z0-9])?)(:\d{1,5})?$")


def host_allowed(value: str | None) -> bool:
    """True se l'header Host (o la parte host:porta di un Origin) è il dashboard stesso."""
    if not value:
        return False
    host = value.strip().lower()
    m = _HOST_RE.match(host)
    if not m:
        return False
    name = m.group(1)
    extra = _extra_hosts()
    return name in LOCAL_HOSTS or name in extra or host in extra


def _origin_ok(request: Request) -> bool:
    """Un browser manda Origin sulle POST: deve essere questa stessa pagina. Curl e i test non lo mandano."""
    site = request.headers.get("sec-fetch-site")
    if site and site not in ("same-origin", "none"):
        return False
    origin = request.headers.get("origin")
    if not origin:
        return True
    parts = urlsplit(origin)
    return parts.scheme in ("http", "https") and host_allowed(parts.netloc)


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------
class SnapshotError(Exception):
    pass


def _finite(obj):
    """NaN e Infinity non sono JSON: diventano null (la pagina mostra '—')."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_finite(v) for v in obj]
    return obj


def _read_json(path: Path, attempts: int = 3) -> dict:
    """Legge un oggetto JSON; ritenta se lo trova a metà scrittura."""
    last = "illeggibile"
    for i in range(attempts):
        try:
            if path.stat().st_size > MAX_SNAPSHOT_BYTES:
                raise SnapshotError("snapshot troppo grande")
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise SnapshotError("lo snapshot non è un oggetto JSON")
            return _finite(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            last = "snapshot non valido (JSON)"
        except OSError:
            last = "snapshot non leggibile"
        if i + 1 < attempts:
            time.sleep(0.05)
    raise SnapshotError(last)


def load_snapshot() -> tuple[dict, str]:
    """(snapshot, sorgente). Sorgente 'file' = scritto dal motore; 'demo' = esempio, perché il file non c'è."""
    path = snapshot_path()
    if path.is_file():
        return _read_json(path), "file"
    if not SAMPLE.is_file():
        raise SnapshotError("nessuno snapshot disponibile")
    snap = _read_json(SAMPLE, attempts=1)
    meta = snap.get("meta") if isinstance(snap.get("meta"), dict) else {}
    snap = _shift_times(snap, meta.get("as_of"))          # l'esempio resta "di adesso": età e orari relativi non invecchiano
    meta = snap["meta"] if isinstance(snap.get("meta"), dict) else {}
    meta["data_label"] = DEMO_LABEL                       # un esempio non deve mai sembrare un dato vero
    meta["as_of"] = _now_iso()
    snap["meta"] = meta
    return snap, "demo"


_STAMP = "%Y-%m-%dT%H:%M:%SZ"
_STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime(_STAMP)


def _shift_times(snap: dict, as_of) -> dict:
    """Sposta gli istanti dell'esempio (avvisi, ordini, segnali) di quanto è passato dal suo `as_of`.
    Le date senza ora (curva, mesi) restano quelle scritte nel file."""
    if not isinstance(as_of, str) or not _STAMP_RE.match(as_of):
        return snap
    delta = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None) - datetime.strptime(as_of, _STAMP)

    def walk(obj):
        if isinstance(obj, str) and _STAMP_RE.match(obj):
            try:
                return (datetime.strptime(obj, _STAMP) + delta).strftime(_STAMP)
            except (ValueError, OverflowError):
                return obj
        if isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [walk(v) for v in obj]
        return obj

    return walk(snap)


# ---------------------------------------------------------------------------
# KILL
# ---------------------------------------------------------------------------
def _clean_reason(raw) -> str:
    if not isinstance(raw, str):
        return DEFAULT_REASON
    text = " ".join("".join(ch if ch.isprintable() else " " for ch in raw).split())
    return text[:MAX_REASON_CHARS] or DEFAULT_REASON


def engage_kill(reason: str) -> tuple[bool, str]:
    """Crea il file KILL in modo atomico e senza sovrascriverlo. Ritorna (creato_ora, timestamp)."""
    path = kill_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = _now_iso()
    line = f"{ts} dashboard: {reason}\n"                  # stesso formato del KILL storico: "<ora> <chi>: <motivo>"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".kill-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o644)
        try:
            os.link(tmp, path)                            # atomico; fallisce se KILL esiste già
            created = True
        except FileExistsError:
            created = False
        except OSError:                                   # filesystem senza hard link
            created = _create_exclusive(path, line)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
    return created, ts


def _create_exclusive(path: Path, line: str) -> bool:
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())
    return True


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="GERVA Capital · Dashboard", docs_url=None, redoc_url=None, openapi_url=None)


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=status)


@app.middleware("http")
async def guard(request: Request, call_next):
    if not host_allowed(request.headers.get("host")):
        response = _error(400, "host non ammesso")
    else:
        response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers[name] = value
    # i dati non si mettono in cache; la pagina si rivalida a ogni caricamento (ETag)
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
    return response


@app.get("/api/v1/snapshot")
def get_snapshot():
    try:
        snap, source = load_snapshot()
    except SnapshotError as exc:
        return _error(503, str(exc))
    return JSONResponse(snap, headers={"X-Gerva-Snapshot-Source": source})


@app.get("/api/v1/quant")
def get_quant():
    """Risultati della ricerca su dati storici: statici, simulati, serviti così come sono (NaN -> null)."""
    path = quant_path()
    if not path.is_file():
        return _error(404, "ricerca non disponibile")
    try:
        data = _read_json(path)
    except SnapshotError as exc:
        return _error(503, str(exc).replace("snapshot", "file della ricerca"))
    age = None
    with contextlib.suppress(OSError):
        age = str(int(max(0.0, time.time() - path.stat().st_mtime)))
    return JSONResponse(data, headers={"X-Gerva-Quant-Age": age} if age is not None else None)


@app.get("/api/v1/health")
def get_health():
    age, source = None, "demo"
    try:
        age = round(max(0.0, time.time() - snapshot_path().stat().st_mtime), 1)
        source = "file"
    except OSError:
        pass
    return {
        "ok": True,
        "snapshot_age_s": age,
        "snapshot_source": source,
        "kill_enabled": bool(_token()),
        "kill_active": kill_path().exists(),
    }


@app.post("/api/v1/kill")
async def post_kill(request: Request):
    expected = _token()
    if not expected:
        return _error(503, "KILL disabilitato: GERVA_DASH_TOKEN non impostato sul server")
    if not _origin_ok(request):
        return _error(403, "origine non ammessa")
    given = request.headers.get("x-gerva-token")
    if not given:
        return _error(401, "token mancante")
    if not hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8")):
        return _error(403, "token non valido")

    reason = DEFAULT_REASON
    body = await request.body()
    if len(body) > MAX_KILL_BODY:
        return _error(413, "richiesta troppo grande")
    if body.strip():
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return _error(400, "corpo della richiesta non valido")
        if isinstance(payload, dict):
            reason = _clean_reason(payload.get("reason"))
    try:
        created, ts = engage_kill(reason)
    except OSError:
        return _error(500, "impossibile creare il file KILL")
    return {"ok": True, "created": created, "already_active": not created, "t": ts}


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def api_not_found(rest: str):
    return _error(404, "endpoint inesistente")


app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")


def main() -> None:
    import uvicorn

    host = os.environ.get("GERVA_DASH_HOST", "127.0.0.1")
    port = int(os.environ.get("GERVA_DASH_PORT", "8787"))
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.environ.get("GERVA_DASH_LOG_LEVEL", "info"),
        access_log=os.environ.get("GERVA_DASH_ACCESS_LOG", "") == "1",   # la pagina interroga ogni 5 s
        server_header=False,
    )


if __name__ == "__main__":
    main()
