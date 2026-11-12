"""
Dashboard di GERVA Capital — piccolo server FastAPI, pensato per girare su 127.0.0.1.

Che cosa fa:
  * serve la pagina statica (dashboard/static/) su "/";
  * GET  /api/v1/snapshot  restituisce lo snapshot JSON scritto dal motore (env GERVA_SNAPSHOT);
                           se il file non esiste serve l'esempio, marcato "DEMO: dati di esempio";
  * GET  /api/v1/health    {"ok": true, "snapshot_age_s": ...};
  * GET  /api/v1/quant     i risultati della ricerca (env GERVA_QUANT, default research/v5/quant.json): tutto SIMULATO;
  * GET  /api/v1/learn     il rapporto del ciclo di automiglioramento (env GERVA_LEARN, default $GERVA_HOME/learn/report.json);
  * GET  /api/v1/market/symbols, /api/v1/market/ohlc   barre giornaliere dalla cache dei dati (env GERVA_CACHE), con
                           conviction e indicatore Gervasoni calcolati dalle funzioni del fondo; sola lettura;
  * GET  /api/v1/tradebook, /api/v1/trades/history, /api/v1/compare   libro dei trade, storico dei trade, confronto;
  * GET  /api/v1/quant4    la quarta tornata di ricerca (env GERVA_QUANT4, default research/v5/quant_v4.json): SIMULATO;
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
import csv
import hmac
import json
import math
import os
import re
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STATIC = HERE / "static"
SAMPLE = STATIC / "sample_snapshot.json"
SAMPLE_LEARN = STATIC / "sample_learn.json"
SAMPLE_OHLC = STATIC / "sample_ohlc.json"
SAMPLE_TRADEBOOK = STATIC / "sample_tradebook.json"
SAMPLE_TRADES = STATIC / "sample_trades.json"
SAMPLE_COMPARE = STATIC / "sample_compare.json"

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


def quant4_path() -> Path:
    raw = os.environ.get("GERVA_QUANT4", "").strip()
    return Path(raw).expanduser() if raw else ROOT / "research" / "v5" / "quant_v4.json"


def learn_path() -> Path:
    """Rapporto del ciclo di automiglioramento: GERVA_LEARN, altrimenti $GERVA_HOME/learn/report.json."""
    raw = os.environ.get("GERVA_LEARN", "").strip()
    if raw:
        return Path(raw).expanduser()
    home = os.environ.get("GERVA_HOME", "").strip()
    return (Path(home).expanduser() if home else ROOT / "var" / "gerva") / "learn" / "report.json"


def home_dir() -> Path:
    raw = os.environ.get("GERVA_HOME", "").strip()
    return Path(raw).expanduser() if raw else ROOT / "var" / "gerva"


def cache_dir() -> Path:
    raw = os.environ.get("GERVA_CACHE", "").strip()
    return Path(raw).expanduser() if raw else ROOT / "data_cache"


def trades_hist_path() -> Path:
    raw = os.environ.get("GERVA_TRADES_HIST", "").strip()
    return Path(raw).expanduser() if raw else ROOT / "research" / "v5" / "v6" / "trade_storici.parquet"


def is_demo() -> bool:
    """Nessuno snapshot del motore: la pagina mostra l'esempio, e così fanno le fonti che mancano."""
    return not snapshot_path().is_file()


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
    snap = _shift_dates(snap, _demo_shift_days())         # …e così le sue date senza ora: una sola storia, tutta alla data di oggi
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
    return _research(quant_path())


@app.get("/api/v1/quant4")
def get_quant4():
    """Quarta tornata di ricerca (leva per trade, fondo intero, strategie provate): stesse regole di /quant."""
    return _research(quant4_path())


@app.get("/api/v1/learn")
def get_learn():
    """Rapporto di `python -m gerva learn`. Sola lettura: nessun endpoint attiva una regola (lo fa solo il comando).
    Senza rapporto e senza snapshot (modalità demo) si serve l'esempio, marcato come tale."""
    return _file_or_example(learn_path(), SAMPLE_LEARN, "X-Gerva-Learn-Source")


def _file_or_example(path: Path, sample: Path, header: str = "X-Gerva-Source", missing: str = "ricerca non disponibile", shift: bool = False):
    """Il file vero se c'è; in modalità demo l'esempio in dotazione, marcato `example: true`; altrimenti 404."""
    if path.is_file() or not is_demo() or not sample.is_file():
        return _research(path, missing)
    try:
        data = _read_json(sample, attempts=1)
    except SnapshotError as exc:
        return _error(503, str(exc).replace("snapshot", "file della ricerca"))
    data["example"] = True
    if shift:
        data = _shift_dates(data, _demo_shift_days())
    return JSONResponse(data, headers={header: "demo"})


_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")


def _demo_shift_days() -> int:
    """Di quanti giorni va spostato l'insieme degli esempi perché il suo giorno di riferimento sia oggi.
    Tutti gli esempi (fotografia, barre, libro dei trade, confronto) nascono dallo stesso generatore con la stessa data:
    spostarli insieme li tiene coerenti e mai «vecchi di giorni» accanto a una fotografia «di adesso»."""
    try:
        as_of = str((_read_json(SAMPLE, attempts=1).get("meta") or {}).get("as_of") or "")[:10]
        return (datetime.now(timezone.utc).date() - datetime.strptime(as_of, "%Y-%m-%d").date()).days
    except (SnapshotError, ValueError):
        return 0


def _shift_dates(obj, days: int):
    """Sposta di `days` giorni ogni stringa che è una data senza ora (AAAA-MM-GG); il resto non si tocca."""
    if not days:
        return obj
    if isinstance(obj, str):
        if _DATE_RE.match(obj):
            try:
                return (datetime.strptime(obj, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
            except (ValueError, OverflowError):
                return obj
        return obj
    if isinstance(obj, dict):
        return {k: _shift_dates(v, days) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_shift_dates(v, days) for v in obj]
    return obj


_rules_cache: dict = {}


def _engine_rules() -> dict:
    """Le regole che la pagina deve conoscere ma non deve mai scrivere: lette dai moduli del motore e dalla configurazione.
    Se un pezzo non si può leggere manca dalla risposta, e la pagina scrive «n.d.» invece di un valore predefinito."""
    if _rules_cache.get("t", 0) > time.time() - 600:
        return _rules_cache["v"]
    out: dict = {}
    try:
        from gerva import ensemble as E, gervasoni as G
        from gerva.risk import isolated as I
        from gerva.live import tradecycle as T
        out.update(max_hold_days=int(T.MAX_HOLD), score_confirmed=float(I.SCORE_CONFIRMED), score_exceptional=float(I.SCORE_EXCEPTIONAL),
                   conviction_tiers={k: [float(v[0]), float(v[1])] for k, v in E.THRESHOLDS.items()},
                   gq_tiers={k: float(v) for k, v in G.THRESHOLDS.items()})
    except Exception:
        pass
    try:
        import yaml
        cfg = yaml.safe_load((ROOT / "config" / "gerva.yaml").read_text(encoding="utf-8")) or {}
        lim = cfg.get("limits") or {}
        ages = lim.get("max_data_age_h") or {}
        out["max_data_age_h"] = {str(k): float(v) for k, v in ages.items() if isinstance(v, (int, float))}
        tr = cfg.get("trades") or {}
        out["trade_risk"] = {k: float(v) for k, v in tr.items() if isinstance(v, (int, float))}
        if isinstance(cfg.get("interval_s"), (int, float)):
            out["interval_s"] = float(cfg["interval_s"])
    except Exception:
        pass
    _rules_cache.update(t=time.time(), v=out)
    return out


# ---------------------------------------------------------------------------
# Mercato: barre giornaliere dalla cache dei dati, con gli indicatori calcolati dalle funzioni del fondo
# ---------------------------------------------------------------------------
_SYMBOL_RE = re.compile(r"^\^?[A-Z0-9]{1,10}(-[A-Z]{3})?$")        # BTC, SPY, ^VIX, BTC-USD: nient'altro arriva al disco
_MARKET_TTL_S = 300.0
_market_cache: dict = {}
MAX_BARS = 5000


def _cached(key, build):
    now = time.monotonic()
    hit = _market_cache.get(key)
    if hit and hit[0] > now:
        return hit[1]
    value = build()
    if len(_market_cache) > 96:
        _market_cache.clear()
    _market_cache[key] = (now + _MARKET_TTL_S, value)
    return value


def _symbol_file(symbol: str) -> tuple[Path, str] | None:
    """Simbolo -> (file nella cache, tipo). Il nome si costruisce da un simbolo già validato e deve restare nella cartella."""
    if not isinstance(symbol, str) or not _SYMBOL_RE.match(symbol):
        return None
    root = cache_dir().resolve()
    for name, kind in ((f"bn_spot_1d_{symbol}USDT.parquet", "crypto"), (f"yahoo_1d_{symbol}.parquet", "indice" if symbol.startswith("^") else "etf")):
        path = (root / name).resolve()
        if path.parent == root and path.is_file():
            return path, kind
    return None


def _list_symbols() -> list[dict]:
    root = cache_dir()
    found: dict[str, str] = {}
    try:
        names = sorted(e.name for e in os.scandir(root) if e.is_file() and e.name.endswith(".parquet"))
    except OSError:
        return []
    for name in names:
        if name.startswith("bn_spot_1d_") and name.endswith("USDT.parquet"):
            sym, kind = name[len("bn_spot_1d_"):-len("USDT.parquet")], "crypto"
        elif name.startswith("yahoo_1d_"):
            sym = name[len("yahoo_1d_"):-len(".parquet")]
            kind = "indice" if sym.startswith("^") else "etf"
        else:
            continue
        if _SYMBOL_RE.match(sym) and not (kind != "crypto" and sym.endswith("-USD")) and sym not in found:
            found[sym] = kind
    order = {"crypto": 0, "etf": 1, "indice": 2}
    return [dict(symbol=k, kind=v) for k, v in sorted(found.items(), key=lambda kv: (order[kv[1]], kv[0]))]


def _sample_ohlc() -> dict | None:
    if not is_demo() or not SAMPLE_OHLC.is_file():
        return None
    try:
        return _shift_dates(_read_json(SAMPLE_OHLC, attempts=1), _demo_shift_days())
    except SnapshotError:
        return None


def _num_list(series) -> list:
    return [None if v != v or v in (float("inf"), float("-inf")) else float(v) for v in series.tolist()]


def _build_ohlc(path: Path, kind: str, symbol: str, limit: int) -> dict:
    import pandas as pd                                     # solo qui: il resto del server non dipende da pandas

    df = pd.read_parquet(path)
    df = df[["open", "high", "low", "close", "volume"]].dropna(subset=["close"]).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    extra: dict = {"conviction": None, "gq": None, "thresholds": None}
    if kind == "crypto":
        # stesse funzioni del motore (gerva.ensemble, gerva.gervasoni): grafico e ciclo dicono la stessa cosa
        try:
            from gerva import ensemble as E, gervasoni as G
            from gerva.risk import isolated as I
            btc_file = _symbol_file("BTC")
            btc = df["close"] if symbol == "BTC" or btc_file is None else pd.read_parquet(btc_file[0])["close"].sort_index()
            score = E.conviction(E.crypto_signals(df, btc))["score"]
            g = G.gq(df, df["volume"], btc)
            extra = dict(conviction=_num_list(score.tail(limit)), gq=_num_list(g.tail(limit)),
                         thresholds=dict(conviction=[E.THRESHOLDS["crypto"][1], I.SCORE_EXCEPTIONAL],
                                         gq=[G.THRESHOLDS["bassa"], G.THRESHOLDS["alta"], G.THRESHOLDS["eccezionale"]]))
        except Exception:                                   # indicatori non calcolabili: restano le barre
            pass
    df = df.tail(limit)
    return dict(symbol=symbol, kind=kind, tf="1d", source="cache", rows=int(len(df)),
                t=[str(d.date()) for d in df.index], o=_num_list(df["open"]), h=_num_list(df["high"]), l=_num_list(df["low"]),
                c=_num_list(df["close"]), v=_num_list(df["volume"]), **extra)


@app.get("/api/v1/market/symbols")
def get_symbols():
    symbols = _cached(("symbols", str(cache_dir())), _list_symbols)
    if symbols:
        return {"source": "cache", "symbols": symbols}
    sample = _sample_ohlc()
    if sample and isinstance(sample.get("symbols"), dict):
        return {"source": "esempio", "example": True,
                "symbols": [dict(symbol=k, kind=str(v.get("kind", ""))) for k, v in sample["symbols"].items() if isinstance(v, dict)]}
    return _error(404, "nessun dato di mercato nella cache")


@app.get("/api/v1/market/ohlc")
def get_ohlc(symbol: str = "", tf: str = "1d", limit: int = 1500):
    symbol = symbol.strip().upper()
    if not _SYMBOL_RE.match(symbol):
        return _error(400, "simbolo non valido")
    if tf != "1d":
        return _error(400, "intervallo non disponibile: solo 1d")
    limit = max(10, min(int(limit), MAX_BARS))
    hit = _symbol_file(symbol)
    if hit is None:
        sample = _sample_ohlc() if not _cached(("symbols", str(cache_dir())), _list_symbols) else None
        entry = sample and isinstance(sample.get("symbols"), dict) and sample["symbols"].get(symbol)
        if isinstance(entry, dict):
            return JSONResponse({**entry, "symbol": symbol, "source": "esempio", "example": True}, headers={"X-Gerva-Source": "demo"})
        return _error(404, "simbolo non presente nella cache")
    path, kind = hit
    try:
        if path.stat().st_size > MAX_SNAPSHOT_BYTES:
            return _error(503, "file dei prezzi troppo grande")
        payload = _cached(("ohlc", str(path), path.stat().st_mtime_ns, limit), lambda: _build_ohlc(path, kind, symbol, limit))
    except Exception:
        return _error(503, "prezzi non leggibili")
    return JSONResponse(payload)


# ---------------------------------------------------------------------------
# Libro dei trade a margine isolato, storico dei trade, confronto con il conto originale
# ---------------------------------------------------------------------------
@app.get("/api/v1/tradebook")
def get_tradebook():
    """Stato del libro dei trade (`$GERVA_HOME/tradebook.json`), compreso il registro in ombra dell'indicatore."""
    return _file_or_example(home_dir() / "tradebook.json", SAMPLE_TRADEBOOK, missing="libro dei trade non disponibile", shift=True)


TRADE_FIELDS = ("strategy_id", "symbol", "entry_time", "exit_time", "leverage", "R", "exit_reason", "mae", "mfe", "weekday", "tier",
                "conviction", "gq", "atr_pct")


def _trade_row(rec: dict, source: str) -> dict:
    row = {k: rec.get(k) for k in TRADE_FIELDS}
    ctx = rec.get("context") if isinstance(rec.get("context"), dict) else {}
    for k in ("weekday", "tier", "conviction", "gq", "atr_pct"):
        if row.get(k) is None and k in ctx:
            row[k] = ctx[k]
    for k in ("entry_time", "exit_time"):
        row[k] = None if row[k] is None else str(row[k])[:19]
    row["source"] = source
    return row


def _sim_trades(path: Path) -> list[dict]:
    import pandas as pd

    df = pd.read_parquet(path)
    return [_trade_row(r, "sim") for r in df.to_dict("records")]


def _paper_trades(path: Path) -> list[dict]:
    rows = []
    if not path.is_file() or path.stat().st_size > MAX_SNAPSHOT_BYTES:
        return rows
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict) and rec.get("source", "paper") != "sim":
                rows.append(_trade_row(rec, "paper" if rec.get("source", "paper") == "paper" else str(rec.get("source"))))
    return rows


@app.get("/api/v1/trades/history")
def get_trades_history():
    """Trade del libro a margine isolato: simulazioni storiche (sim) e trade del conto di prova (paper), ogni riga marcata."""
    hist, paper = trades_hist_path(), home_dir() / "learn" / "trades.jsonl"
    if not hist.is_file() and not paper.is_file():
        return _file_or_example(hist.with_suffix(".json"), SAMPLE_TRADES, missing="storico dei trade non disponibile")
    try:
        sim = []
        if hist.is_file():
            if hist.stat().st_size > MAX_SNAPSHOT_BYTES:
                return _error(503, "storico dei trade troppo grande")
            sim = _cached(("trades", str(hist), hist.stat().st_mtime_ns), lambda: _sim_trades(hist))
        pap = _paper_trades(paper)
    except Exception:
        return _error(503, "storico dei trade non leggibile")
    return JSONResponse(_finite(dict(label="SIMULATO: i trade 'sim' sono simulazioni storiche; i 'paper' sono del conto di prova",
                                     n_sim=len(sim), n_paper=len(pap), rows=sim + pap)))


@app.get("/api/v1/compare")
def get_compare():
    """Confronto giornaliero con il conto GERVA Capital originale (`$GERVA_HOME/confronto_nav.csv`), se esiste."""
    path = home_dir() / "confronto_nav.csv"
    if not path.is_file():
        return _file_or_example(path.with_suffix(".json"), SAMPLE_COMPARE, missing="confronto non disponibile", shift=True)
    try:
        if path.stat().st_size > MAX_SNAPSHOT_BYTES:
            return _error(503, "file del confronto troppo grande")
        rows = []
        with open(path, encoding="utf-8", newline="") as f:
            for rec in csv.DictReader(f):
                row = {}
                for k, v in rec.items():
                    if k is None:
                        continue
                    try:
                        row[k] = float(v) if v not in ("", None) else None
                    except ValueError:
                        row[k] = v
                rows.append(row)
    except (OSError, UnicodeDecodeError, csv.Error):
        return _error(503, "file del confronto non leggibile")
    return JSONResponse(_finite(dict(rows=rows)))


def _research(path: Path, missing: str = "ricerca non disponibile"):
    if not path.is_file():
        return _error(404, missing)
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
        "rules": _engine_rules(),
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
