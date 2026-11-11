"""
Dashboard (dashboard/server.py): snapshot e ripiego sull'esempio, KILL con token, controllo dell'Host,
intestazioni di sicurezza, pagina statica senza risorse esterne, coerenza dell'esempio.
"""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dashboard import server

STATIC = Path(server.STATIC)
TOKEN = "token-di-prova-4f9a"
SNAPSHOT_KEYS = {"meta", "nav", "equity_curve", "monthly_returns", "performance", "exposure", "positions", "risk",
                 "strategies", "orders", "system", "alerts", "gates"}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Ambiente isolato: nessuno snapshot, nessun token, file KILL in una cartella temporanea."""
    monkeypatch.setenv("GERVA_SNAPSHOT", str(tmp_path / "snapshot.json"))
    monkeypatch.setenv("GERVA_KILL_FILE", str(tmp_path / "stato" / "KILL"))
    monkeypatch.delenv("GERVA_DASH_TOKEN", raising=False)
    monkeypatch.delenv("GERVA_DASH_ALLOWED_HOSTS", raising=False)
    monkeypatch.setenv("GERVA_QUANT", str(tmp_path / "quant.json"))
    return tmp_path


@pytest.fixture()
def client(env):
    # il browser arriva con Host 127.0.0.1:8787; "testserver" (il default del TestClient) non è ammesso
    return TestClient(server.app, base_url="http://127.0.0.1:8787")


def _write(path: Path, obj) -> None:
    path.write_text(obj if isinstance(obj, str) else json.dumps(obj), encoding="utf-8")


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------
def test_snapshot_ripiega_sull_esempio_marcato_demo(client, env):
    r = client.get("/api/v1/snapshot")
    assert r.status_code == 200
    snap = r.json()
    assert SNAPSHOT_KEYS <= set(snap)
    assert snap["meta"]["data_label"] == "DEMO: dati di esempio"
    assert r.headers["x-gerva-snapshot-source"] == "demo"
    # l'esempio è presentato come "di adesso": la pagina non lo deve segnalare come fermo
    as_of = datetime.strptime(snap["meta"]["as_of"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert abs((datetime.now(timezone.utc) - as_of).total_seconds()) < 30
    # e gli istanti relativi (avvisi, ordini) non stanno nel futuro
    stamps = [a["t"] for a in snap["alerts"]] + [o["t"] for o in snap["orders"]]
    assert stamps and max(stamps) <= snap["meta"]["as_of"]


def test_esempio_forzato_demo_anche_se_il_file_dice_altro(client, env, monkeypatch):
    finto = env / "esempio.json"
    _write(finto, {"meta": {"mode": "live", "data_label": "REALE", "as_of": "2026-01-01T00:00:00Z"}, "nav": {"equity": 1}})
    monkeypatch.setattr(server, "SAMPLE", finto)
    snap = client.get("/api/v1/snapshot").json()
    assert snap["meta"]["data_label"] == "DEMO: dati di esempio"


def test_snapshot_dal_file_passa_invariato(client, env):
    data = {"meta": {"fund": "GERVA Capital", "mode": "paper", "as_of": "2026-11-10T20:45:00Z", "data_label": "PAPER", "stale_after_s": 120},
            "nav": {"equity": 12345.67, "pnl_day": None}, "positions": []}
    _write(env / "snapshot.json", data)
    r = client.get("/api/v1/snapshot")
    assert r.status_code == 200
    assert r.json() == data                                   # né etichetta né orario vengono toccati
    assert r.headers["x-gerva-snapshot-source"] == "file"
    assert r.headers["cache-control"] == "no-store"


def test_snapshot_nan_e_infinito_diventano_null(client, env):
    _write(env / "snapshot.json", '{"meta": {"mode": "paper"}, "nav": {"equity": NaN, "cash": Infinity, "pnl_day": -Infinity, "ok": 1.5}}')
    r = client.get("/api/v1/snapshot")
    assert r.status_code == 200
    assert r.json()["nav"] == {"equity": None, "cash": None, "pnl_day": None, "ok": 1.5}


@pytest.mark.parametrize("contenuto", ['{"meta": {"mode": "pap', "", "[1, 2, 3]", '"testo"'])
def test_snapshot_illeggibile_da_503_e_mai_l_esempio(client, env, contenuto):
    _write(env / "snapshot.json", contenuto)
    r = client.get("/api/v1/snapshot")
    assert r.status_code == 503
    body = r.json()
    assert body["ok"] is False and body["error"]
    assert "nav" not in body                                  # un file rotto non deve far comparire numeri d'esempio
    assert str(env) not in r.text                             # né percorsi del disco


def test_health(client, env):
    h = client.get("/api/v1/health").json()
    assert h["ok"] is True and h["snapshot_age_s"] is None and h["snapshot_source"] == "demo"
    assert h["kill_enabled"] is False and h["kill_active"] is False
    _write(env / "snapshot.json", {"meta": {}})
    os.utime(env / "snapshot.json", (1_700_000_000, 1_700_000_000))
    h = client.get("/api/v1/health").json()
    assert h["snapshot_source"] == "file" and h["snapshot_age_s"] > 1000


def test_endpoint_inesistente(client):
    r = client.get("/api/v1/nonesiste")
    assert r.status_code == 404 and r.json()["ok"] is False
    assert client.get("/api/v1/kill").status_code == 404      # il KILL risponde solo alla POST
    assert client.delete("/api/v1/kill").status_code == 404


# ---------------------------------------------------------------------------
# Ricerca (quant.json): statica, simulata
# ---------------------------------------------------------------------------
def test_quant_assente_da_404_json(client, env):
    r = client.get("/api/v1/quant")
    assert r.status_code == 404
    assert r.json() == {"ok": False, "error": "ricerca non disponibile"}
    assert str(env) not in r.text
    assert r.headers["content-security-policy"].startswith("default-src 'self'")
    assert r.headers["cache-control"] == "no-store"


def test_quant_dal_file_con_nan_ripuliti(client, env):
    _write(env / "quant.json", '{"label": "SIMULATO: ricerca su dati storici", "portfolio": {"tutto": {"sharpe": 1.18, "max_dd": NaN}}, '
                               '"leverage_mc": [{"schema": "fissa 30x", "maxdd_p50": -Infinity}]}')
    r = client.get("/api/v1/quant")
    assert r.status_code == 200
    q = r.json()
    assert q["label"].startswith("SIMULATO")
    assert q["portfolio"]["tutto"] == {"sharpe": 1.18, "max_dd": None}
    assert q["leverage_mc"][0]["maxdd_p50"] is None
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"
    assert int(r.headers["x-gerva-quant-age"]) >= 0


@pytest.mark.parametrize("contenuto", ['{"label": "SIM', "[1, 2]", ""])
def test_quant_illeggibile_da_503(client, env, contenuto):
    _write(env / "quant.json", contenuto)
    r = client.get("/api/v1/quant")
    assert r.status_code == 503 and r.json()["ok"] is False
    assert str(env) not in r.text


def test_quant_troppo_grande_rifiutato(client, env, monkeypatch):
    _write(env / "quant.json", {"label": "x" * 4000})
    monkeypatch.setattr(server, "MAX_SNAPSHOT_BYTES", 1000)
    assert client.get("/api/v1/quant").status_code == 503


def test_quant_host_estraneo_rifiutato_e_percorso_predefinito(client, env, monkeypatch):
    _write(env / "quant.json", {"label": "SIMULATO"})
    assert client.get("/api/v1/quant", headers={"Host": "esempio.invalid"}).status_code == 400
    assert client.post("/api/v1/quant").status_code == 404          # sola lettura
    monkeypatch.delenv("GERVA_QUANT")
    assert server.quant_path() == Path(server.ROOT) / "research" / "v5" / "quant.json"


def test_quant_vero_se_presente_ha_la_forma_attesa():
    path = Path(server.ROOT) / "research" / "v5" / "quant.json"
    if not path.is_file():
        pytest.skip("research/v5/quant.json non generato")
    q = json.loads(path.read_text(encoding="utf-8"))
    assert "SIMULATO" in q["label"]
    for key in ("sleeves", "portfolio", "correlation", "weights", "sleeve_curves", "rolling_sharpe", "drawdown", "return_hist",
                "leverage_mc", "leverage_fan", "leverage_decision", "conviction", "robustness", "significance", "scenarios", "rejected"):
        assert key in q, key
    assert {r["scenario"] for r in q["leverage_mc"]} >= {"base", "pessimista", "stress"}
    assert set(q["leverage_fan"]["levels"]) >= {"1", "2", "3"}


def test_esempio_ha_il_blocco_ai():
    ai = json.loads(server.SAMPLE.read_text(encoding="utf-8"))["ai"]
    assert ai["regime"]["stato"] in ("calmo", "normale", "teso", "crisi")
    assert all(0 <= s["mult"] <= 1 and s["motivo"] and s["fonti"] for s in ai["overlay"]["strategie"])
    assert all(c["livello"] in ("bassa", "media", "alta") and 0 <= c["score"] <= 1 for c in ai["conviction"])


def test_glossario_e_pagine_nuove_presenti():
    js = (STATIC / "js" / "glossary.js").read_text(encoding="utf-8")
    for term in ("Sharpe", "CAGR", "Drawdown", "Leva del conto", "Leva del trade", "Volatilità", "VaR", "PSR", "Deflated Sharpe",
                 "Conviction", "Overlay AI", "KILL", "Periodo di scelta e di verifica", "Punto base"):
        assert f"term: '{term}'" in js, term
    main = (STATIC / "js" / "main.js").read_text(encoding="utf-8")
    for route in ("come-funziona", "ricerca", "'ai'"):
        assert route in main
    for view in ("comefunziona.js", "ricerca.js", "ai.js"):
        assert (STATIC / "js" / "views" / view).is_file()


# ---------------------------------------------------------------------------
# KILL
# ---------------------------------------------------------------------------
def _kill_file(env) -> Path:
    return env / "stato" / "KILL"


def test_kill_spento_senza_token_sul_server(client, env):
    r = client.post("/api/v1/kill", headers={"X-Gerva-Token": TOKEN})
    assert r.status_code == 503
    assert not _kill_file(env).exists()
    # anche un token vuoto nell'ambiente vale "non impostato"
    os.environ["GERVA_DASH_TOKEN"] = ""
    try:
        assert client.post("/api/v1/kill", headers={"X-Gerva-Token": ""}).status_code == 503
    finally:
        del os.environ["GERVA_DASH_TOKEN"]


def test_kill_senza_token_o_con_token_sbagliato(client, env, monkeypatch):
    monkeypatch.setenv("GERVA_DASH_TOKEN", TOKEN)
    assert client.post("/api/v1/kill").status_code == 401
    assert client.post("/api/v1/kill", headers={"X-Gerva-Token": ""}).status_code == 401
    for sbagliato in ("x", TOKEN + "x", TOKEN[:-1], TOKEN.upper(), "tökèn"):
        r = client.post("/api/v1/kill", headers={"X-Gerva-Token": sbagliato.encode("utf-8")})
        assert r.status_code == 403, sbagliato
        assert TOKEN not in r.text
    assert not _kill_file(env).exists()


def test_kill_con_token_giusto_crea_il_file(client, env, monkeypatch):
    monkeypatch.setenv("GERVA_DASH_TOKEN", TOKEN)
    r = client.post("/api/v1/kill", headers={"X-Gerva-Token": TOKEN}, json={"reason": "prova\ndi  arresto\x00 manuale"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["created"] is True and body["already_active"] is False
    assert TOKEN not in r.text and str(env) not in r.text     # niente segreti né percorsi nella risposta
    kill = _kill_file(env)
    assert kill.exists()                                      # crea anche la cartella mancante
    text = kill.read_text(encoding="utf-8")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z dashboard: prova di arresto manuale\n", text)
    assert text.startswith(body["t"])
    assert [p.name for p in kill.parent.iterdir()] == ["KILL"]  # nessun file temporaneo lasciato in giro
    assert client.get("/api/v1/health").json()["kill_active"] is True


def test_kill_non_sovrascrive_e_non_cancella(client, env, monkeypatch):
    monkeypatch.setenv("GERVA_DASH_TOKEN", TOKEN)
    kill = _kill_file(env)
    kill.parent.mkdir(parents=True)
    kill.write_text("2026-01-01T00:00:00Z risk_engine: caduta oltre il limite\n", encoding="utf-8")
    r = client.post("/api/v1/kill", headers={"X-Gerva-Token": TOKEN}, json={"reason": "secondo"})
    assert r.status_code == 200
    assert r.json()["created"] is False and r.json()["already_active"] is True
    assert kill.read_text(encoding="utf-8") == "2026-01-01T00:00:00Z risk_engine: caduta oltre il limite\n"
    # nessun endpoint lo rimuove
    for method in ("delete", "put", "patch"):
        assert getattr(client, method)("/api/v1/kill", headers={"X-Gerva-Token": TOKEN}).status_code in (404, 405)
    assert kill.exists()
    assert not any(isinstance(m, str) and m.upper() == "DELETE" for route in server.app.routes
                   if getattr(route, "path", "") == "/api/v1/kill" for m in getattr(route, "methods", []))


def test_kill_motivo_predefinito_e_corpo_non_valido(client, env, monkeypatch):
    monkeypatch.setenv("GERVA_DASH_TOKEN", TOKEN)
    assert client.post("/api/v1/kill", headers={"X-Gerva-Token": TOKEN}, content=b"{non json").status_code == 400
    assert client.post("/api/v1/kill", headers={"X-Gerva-Token": TOKEN}, content=b"x" * 5000).status_code == 413
    assert not _kill_file(env).exists()
    assert client.post("/api/v1/kill", headers={"X-Gerva-Token": TOKEN}).status_code == 200
    assert _kill_file(env).read_text(encoding="utf-8").rstrip().endswith("dashboard: attivato dalla dashboard")


def test_kill_rifiuta_richieste_da_altre_origini(client, env, monkeypatch):
    monkeypatch.setenv("GERVA_DASH_TOKEN", TOKEN)
    h = {"X-Gerva-Token": TOKEN}
    assert client.post("/api/v1/kill", headers={**h, "Origin": "https://esempio.invalid"}).status_code == 403
    assert client.post("/api/v1/kill", headers={**h, "Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert not _kill_file(env).exists()
    ok = client.post("/api/v1/kill", headers={**h, "Origin": "http://127.0.0.1:8787", "Sec-Fetch-Site": "same-origin"})
    assert ok.status_code == 200 and _kill_file(env).exists()


# ---------------------------------------------------------------------------
# Host
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("host", ["127.0.0.1:8787", "127.0.0.1", "localhost:8787", "localhost", "LOCALHOST:9999", "[::1]:8787"])
def test_host_locali_ammessi(client, host):
    assert client.get("/api/v1/health", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize("host", ["esempio.invalid", "esempio.invalid:8787", "127.0.0.1.esempio.invalid", "localhost.esempio.invalid",
                                  "testserver", "192.168.1.10:8787", "0.0.0.0:8787", "localhost:8787@esempio.invalid", "local host"])
def test_host_estranei_rifiutati(client, host):
    for path in ("/api/v1/snapshot", "/api/v1/health", "/", "/js/main.js"):
        r = client.get(path, headers={"Host": host})
        assert r.status_code == 400, (host, path)
        assert "nav" not in r.text
    assert client.post("/api/v1/kill", headers={"Host": host, "X-Gerva-Token": TOKEN}).status_code == 400


def test_host_aggiunto_dall_elenco_in_ambiente(client, monkeypatch):
    assert client.get("/api/v1/health", headers={"Host": "dash.gerva.internal"}).status_code == 400
    monkeypatch.setenv("GERVA_DASH_ALLOWED_HOSTS", "dash.gerva.internal, altro.internal:9000")
    assert client.get("/api/v1/health", headers={"Host": "dash.gerva.internal"}).status_code == 200
    assert client.get("/api/v1/health", headers={"Host": "dash.gerva.internal:8787"}).status_code == 200
    assert client.get("/api/v1/health", headers={"Host": "altro.internal:9000"}).status_code == 200
    assert client.get("/api/v1/health", headers={"Host": "altro.internal:9001"}).status_code == 400
    assert client.get("/api/v1/health", headers={"Host": "esempio.invalid"}).status_code == 400


# ---------------------------------------------------------------------------
# Intestazioni di sicurezza
# ---------------------------------------------------------------------------
def test_intestazioni_di_sicurezza_su_ogni_risposta(client, env, monkeypatch):
    monkeypatch.setenv("GERVA_DASH_TOKEN", TOKEN)
    risposte = [
        client.get("/"), client.get("/js/main.js"), client.get("/api/v1/snapshot"), client.get("/api/v1/health"),
        client.get("/nonesiste.html"), client.get("/api/v1/nonesiste"), client.post("/api/v1/kill"),
        client.get("/api/v1/health", headers={"Host": "esempio.invalid"}),
    ]
    assert [r.status_code for r in risposte] == [200, 200, 200, 200, 404, 404, 401, 400]
    for r in risposte:
        csp = r.headers["content-security-policy"]
        assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp and "object-src 'none'" in csp
        assert "unsafe-inline" not in csp and "unsafe-eval" not in csp and "*" not in csp
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["referrer-policy"] == "no-referrer"
        assert r.headers["x-frame-options"] == "DENY"
        assert "access-control-allow-origin" not in r.headers  # nessuna apertura CORS
        assert "server" not in r.headers or "uvicorn" not in r.headers["server"].lower()
    assert risposte[2].headers["cache-control"] == "no-store"


def test_nessun_segreto_nelle_risposte(client, env, monkeypatch):
    monkeypatch.setenv("GERVA_DASH_TOKEN", TOKEN)
    for r in (client.get("/api/v1/health"), client.get("/api/v1/snapshot"), client.post("/api/v1/kill", headers={"X-Gerva-Token": "no"})):
        assert TOKEN not in r.text and str(env) not in r.text and "GERVA_KILL_FILE" not in r.text


# ---------------------------------------------------------------------------
# Pagina statica
# ---------------------------------------------------------------------------
def test_pagina_servita_e_senza_script_o_stili_inline(client):
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    html = r.text
    assert '<html lang="it">' in html
    scripts = re.findall(r"<script\b([^>]*)>(.*?)</script>", html, flags=re.S)
    assert scripts and all("src=" in attrs and not body.strip() for attrs, body in scripts)
    assert "<style" not in html and not re.search(r"\sstyle\s*=", html) and not re.search(r"\son[a-z]+\s*=", html)
    for ref in re.findall(r'(?:src|href)="([^"#][^"]*)"', html):
        assert not ref.startswith(("http:", "https:", "//")), ref
        assert client.get("/" + ref).status_code == 200, ref
    assert client.get("/js/main.js").headers["content-type"].startswith(("text/javascript", "application/javascript"))
    assert client.get("/fonts/general-sans-500.woff2").headers["content-type"] == "font/woff2"


def test_nessuna_risorsa_esterna_nei_file_statici():
    """Niente CDN: gli unici URL assoluti ammessi sono gli spazi dei nomi del W3C (SVG)."""
    for path in STATIC.rglob("*"):
        if path.suffix not in {".html", ".css", ".js", ".svg"}:
            continue
        text = path.read_text(encoding="utf-8")
        for url in re.findall(r"""(?:https?:)?//[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^\s"'`)<]*""", text):
            assert "www.w3.org/" in url, f"{path.name}: {url}"
        if path.suffix == ".js":
            assert "innerHTML" not in text.replace("senza innerHTML", "") and "eval(" not in text, path.name
        if path.suffix == ".css":
            assert "@import" not in text, path.name


def test_moduli_importati_esistono():
    for path in (STATIC / "js").rglob("*.js"):
        for ref in re.findall(r"""from\s+['"](\.[^'"]+)['"]""", path.read_text(encoding="utf-8")):
            assert (path.parent / ref).resolve().is_file(), f"{path.name} importa {ref}"


# ---------------------------------------------------------------------------
# L'esempio: completo e coerente
# ---------------------------------------------------------------------------
def test_esempio_completo_e_coerente():
    s = json.loads(server.SAMPLE.read_text(encoding="utf-8"))
    assert SNAPSHOT_KEYS <= set(s)
    meta, nav = s["meta"], s["nav"]
    assert meta["data_label"] == "DEMO: dati di esempio" and meta["mode"] in ("paper", "live", "backtest")
    assert 11_000 < nav["equity"] < 13_000 and meta["base_ccy"] == "EUR"

    curve = s["equity_curve"]
    assert 380 <= len(curve) <= 420
    days = [p["t"] for p in curve]
    assert days == sorted(days) and len(set(days)) == len(days)
    assert curve[-1]["equity"] == pytest.approx(nav["equity"])
    assert nav["pnl_day"] == pytest.approx(curve[-1]["equity"] - curve[-2]["equity"], abs=0.01)
    assert nav["pnl_day_pct"] == pytest.approx(curve[-1]["equity"] / curve[-2]["equity"] - 1, abs=1e-5)
    assert nav["pnl_total_pct"] == pytest.approx(nav["equity"] / nav["start_equity"] - 1, abs=1e-5)
    assert nav["drawdown_pct"] == pytest.approx(nav["equity"] / nav["high_water"] - 1, abs=1e-5)
    assert nav["max_drawdown_pct"] <= nav["drawdown_pct"] <= 0
    assert nav["high_water"] >= max(p["equity"] for p in curve)

    months = s["monthly_returns"]
    assert len(months) >= 30 and len({m["ym"] for m in months}) == len(months)
    assert months[-1]["ret"] == pytest.approx(nav["pnl_mtd_pct"], abs=1e-5)
    total = 1.0
    for m in months:
        total *= 1 + m["ret"]
    assert total - 1 == pytest.approx(nav["pnl_total_pct"], abs=1e-3)   # i mesi compongono il rendimento dall'avvio
    perf = s["performance"]
    assert perf["best_month"] == pytest.approx(max(m["ret"] for m in months)) and perf["worst_month"] == pytest.approx(min(m["ret"] for m in months))
    # i mesi interamente coperti dalla curva coincidono con la curva
    by_month = {}
    for p in curve:
        by_month.setdefault(p["t"][:7], []).append(p["equity"])
    full = sorted(by_month)[1:]
    for prev, cur in zip(full, full[1:]):
        ret = by_month[cur][-1] / by_month[prev][-1] - 1
        assert next(m["ret"] for m in months if m["ym"] == cur) == pytest.approx(ret, abs=1e-5), cur

    pos, exp = s["positions"], s["exposure"]
    assert len(pos) >= 5
    gross = sum(abs(p["value"]) for p in pos) / nav["equity"]
    net = sum(p["value"] for p in pos) / nav["equity"]
    assert exp["gross"] == pytest.approx(gross, abs=1e-4) and exp["net"] == pytest.approx(net, abs=1e-4)
    assert exp["leverage"] == pytest.approx(gross, abs=1e-3) and exp["leverage"] < exp["max_leverage"]
    assert sum(p["pnl_day"] for p in pos) == pytest.approx(nav["pnl_day"], abs=0.01)
    assert nav["cash"] == pytest.approx(nav["equity"] - sum(p["value"] for p in pos), abs=0.01)
    for p in pos:
        assert p["weight"] == pytest.approx(p["value"] / nav["equity"], abs=1e-5)
        assert p["value"] == pytest.approx(p["qty"] * p["price"], abs=0.02)
    for group in ("by_asset_class", "by_venue"):
        assert sum(g["gross"] for g in exp[group]) == pytest.approx(exp["gross"], abs=1e-4)
        assert sum(g["net"] for g in exp[group]) == pytest.approx(exp["net"], abs=1e-4)

    strategies = s["strategies"]
    assert [x["id"] for x in strategies] == ["CR-TREND", "CR-XSMOM", "EQ-MR", "MA-TREND"]
    assert sum(x["allocation"] for x in strategies) == pytest.approx(1.0)
    for x in strategies:
        mine = sum(abs(p["value"]) for p in pos if p["strategy"] == x["id"]) / nav["equity"]
        assert x["exposure"] == pytest.approx(mine, abs=1e-4)
        assert len(x["spark"]) >= 20

    risk = s["risk"]
    assert risk["state"] == "NORMAL"
    assert [l["status"] for l in risk["limits"]].count("warn") == 1
    for l in risk["limits"]:
        use = abs(l["value"]) / abs(l["limit"])
        assert l["status"] == ("breach" if use >= 1 else "warn" if use >= 0.8 else "ok"), l["name"]
    assert all(step["hit"] == (nav["drawdown_pct"] <= step["level"]) for step in risk["dd_ladder"])

    assert len(s["orders"]) >= 8 and {o["status"] for o in s["orders"]} >= {"filled", "rejected", "pending", "cancelled"}
    assert all(o["reason"] for o in s["orders"] if o["status"] == "rejected")
    assert {o["symbol"] for o in s["orders"] if o["status"] == "filled"} <= {p["symbol"] for p in pos}
    assert len(s["alerts"]) >= 3 and len(s["system"]["components"]) >= 4 and len(s["gates"]) >= 4
    assert any(not g["ok"] for g in s["gates"]) and any(g["ok"] for g in s["gates"])
    stamps = [a["t"] for a in s["alerts"]] + [o["t"] for o in s["orders"]] + [c["last_ok"] for c in s["system"]["components"]]
    assert max(stamps) <= meta["as_of"]


def test_configurazione_predefinita(monkeypatch):
    for name in ("GERVA_SNAPSHOT", "GERVA_KILL_FILE"):
        monkeypatch.delenv(name, raising=False)
    assert server.snapshot_path() == Path(server.ROOT) / "var" / "gerva" / "snapshot.json"
    assert server.kill_path() == Path(server.ROOT) / "var" / "gerva" / "KILL"
    assert server.DEMO_LABEL == "DEMO: dati di esempio"
