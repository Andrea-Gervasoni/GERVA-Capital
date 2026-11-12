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
    monkeypatch.setenv("GERVA_QUANT4", str(tmp_path / "quant_v4.json"))
    monkeypatch.setenv("GERVA_LEARN", str(tmp_path / "learn" / "report.json"))
    monkeypatch.setenv("GERVA_HOME", str(tmp_path / "casa"))
    monkeypatch.setenv("GERVA_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("GERVA_TRADES_HIST", str(tmp_path / "trade_storici.parquet"))
    server._market_cache.clear()
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


# ---- quarta tornata (quant_v4.json): stesse regole di /quant ----
def test_quant4_assente_da_404_json(client, env):
    _write(env / "quant.json", {"label": "SIMULATO"})                 # i due file sono indipendenti
    r = client.get("/api/v1/quant4")
    assert r.status_code == 404 and r.json() == {"ok": False, "error": "ricerca non disponibile"}
    assert r.headers["cache-control"] == "no-store" and "default-src 'self'" in r.headers["content-security-policy"]
    assert client.get("/api/v1/quant").status_code == 200


def test_quant4_dal_file_con_nan_ripuliti(client, env):
    _write(env / "quant_v4.json", '{"simulated": true, "trials": 812, "deflated_sharpe": {"old": 0.2, "new": 0.38, "threshold": 0.95}, '
                                  '"stop_table": [{"label": "1.7%", "leverage": 30.0, "mean_R_verify": NaN}], "decomposition": {"ai_contribution": null}}')
    r = client.get("/api/v1/quant4")
    assert r.status_code == 200
    q = r.json()
    assert q["trials"] == 812 and q["stop_table"][0]["mean_R_verify"] is None and q["decomposition"]["ai_contribution"] is None
    assert int(r.headers["x-gerva-quant-age"]) >= 0 and r.headers["x-content-type-options"] == "nosniff"
    assert client.get("/api/v1/quant").status_code == 404                # e non si confondono


@pytest.mark.parametrize("contenuto", ['{"trials": 8', "[]", ""])
def test_quant4_illeggibile_o_troppo_grande_da_503(client, env, monkeypatch, contenuto):
    _write(env / "quant_v4.json", contenuto)
    r = client.get("/api/v1/quant4")
    assert r.status_code == 503 and r.json()["ok"] is False and str(env) not in r.text
    _write(env / "quant_v4.json", {"x": "y" * 4000})
    monkeypatch.setattr(server, "MAX_SNAPSHOT_BYTES", 1000)
    assert client.get("/api/v1/quant4").status_code == 503


def test_quant4_host_metodo_e_percorso_predefinito(client, env, monkeypatch):
    _write(env / "quant_v4.json", {"simulated": True})
    assert client.get("/api/v1/quant4", headers={"Host": "esempio.invalid"}).status_code == 400
    assert client.post("/api/v1/quant4").status_code == 404
    monkeypatch.delenv("GERVA_QUANT4")
    assert server.quant4_path() == Path(server.ROOT) / "research" / "v5" / "quant_v4.json"


def test_quant4_vero_se_presente_ha_la_forma_attesa():
    path = Path(server.ROOT) / "research" / "v5" / "quant_v4.json"
    if not path.is_file():
        pytest.skip("research/v5/quant_v4.json non generato")
    q = json.loads(path.read_text(encoding="utf-8"))
    for key in ("stop_table", "tier_mc", "stress", "fund_stats", "fund_mc", "fund_curves", "recommended", "candidates",
                "decomposition", "venues", "trials", "deflated_sharpe"):
        assert key in q, key
    assert {r["scenario"] for r in q["tier_mc"]} >= {"base", "pessimista", "verifica", "stress"}
    names = {r["portafoglio"] for r in q["fund_stats"]}
    assert q["recommended"]["prudent"] in names and q["recommended"]["maximum"] in names
    assert q["decomposition"]["ai_contribution"] is None              # mai un numero: si misura in paper
    # la regola «sostenuta» della pagina (leva ≤ 30x e R in verifica > 0,15) individua solo 1,0 x ATR: il livello a 30x
    # (stop 1,7%) e' stato ritirato dopo la misura sui prezzi veri dei perpetual (quinta tornata, analista A9)
    ok = sorted(r["label"] for r in q["stop_table"] if r["leverage"] <= 30.5 and r["mean_R_verify"] > 0.15)
    assert ok == ["1.0 x ATR"]
    assert all(r["leverage"] > 30.5 or r["mean_R_verify"] <= 0.2 for r in q["stop_table"])


def test_pagina_leva_e_termini_della_quarta_tornata():
    js = (STATIC / "js" / "glossary.js").read_text(encoding="utf-8")
    for term in ("Margine isolato", "R", "Rischio per trade", "Distanza dalla liquidazione", "Carry e funding"):
        assert f"term: '{term}'" in js, term
    assert (STATIC / "js" / "views" / "leva.js").is_file()
    main = (STATIC / "js" / "main.js").read_text(encoding="utf-8")
    assert "leva-trade" in main and "quant4" in main
    leva = (STATIC / "js" / "views" / "leva.js").read_text(encoding="utf-8")
    assert "lev > 30.5" in leva and "rv > 0.15" in leva
    ricerca = (STATIC / "js" / "views" / "ricerca.js").read_text(encoding="utf-8")
    assert "da misurare in paper" in ricerca and "ai_contribution" not in ricerca      # il contributo dell'AI non è mai un numero


# ---- ciclo di automiglioramento (learn/report.json) ----
def _learn_file(env) -> Path:
    path = env / "learn" / "report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def test_learn_in_demo_serve_l_esempio_marcato(client, env):
    r = client.get("/api/v1/learn")                       # né snapshot né rapporto: modalità demo
    assert r.status_code == 200
    body = r.json()
    assert body["example"] is True and r.headers["x-gerva-learn-source"] == "demo"
    assert {"evaluation", "weaknesses", "improvement", "registry"} <= set(body)
    assert r.headers["cache-control"] == "no-store" and "default-src 'self'" in r.headers["content-security-policy"]


def test_learn_assente_con_snapshot_vero_da_404(client, env):
    _write(env / "snapshot.json", {"meta": {"mode": "paper"}})      # conto vero: l'esempio non deve comparire
    r = client.get("/api/v1/learn")
    assert r.status_code == 404 and r.json() == {"ok": False, "error": "ricerca non disponibile"}
    assert "x-gerva-learn-source" not in r.headers


def test_learn_dal_file_con_nan_ripuliti_e_mai_marcato_esempio(client, env):
    _write(_learn_file(env), '{"generated": "2026-11-12 06:05:14+00:00", "evaluation": {"all": {"n": 3, "performance": {"mean_R": NaN}}, "paper": {"n": 0}}, '
                             '"improvement": {"proposed": [], "shadow": [], "active": [], "tried": 4, "threshold_t": 2.0}, "registry": []}')
    r = client.get("/api/v1/learn")
    assert r.status_code == 200
    body = r.json()
    assert "example" not in body and "x-gerva-learn-source" not in r.headers
    assert body["evaluation"]["all"]["performance"]["mean_R"] is None and body["improvement"]["tried"] == 4
    assert int(r.headers["x-gerva-quant-age"]) >= 0


@pytest.mark.parametrize("contenuto", ['{"generated": "20', "[]", ""])
def test_learn_illeggibile_o_troppo_grande_da_503(client, env, monkeypatch, contenuto):
    _write(_learn_file(env), contenuto)
    r = client.get("/api/v1/learn")
    assert r.status_code == 503 and r.json()["ok"] is False and str(env) not in r.text
    assert "weaknesses" not in r.text                      # un rapporto rotto non fa comparire l'esempio
    _write(_learn_file(env), {"x": "y" * 4000})
    monkeypatch.setattr(server, "MAX_SNAPSHOT_BYTES", 1000)
    assert client.get("/api/v1/learn").status_code == 503


def test_learn_percorsi_host_e_sola_lettura(client, env, monkeypatch):
    _write(_learn_file(env), {"generated": "x"})
    assert client.get("/api/v1/learn", headers={"Host": "esempio.invalid"}).status_code == 400
    for method in ("post", "put", "patch", "delete"):       # nessun endpoint attiva o modifica una regola
        assert getattr(client, method)("/api/v1/learn").status_code == 404
        assert getattr(client, method)("/api/v1/learn/approve").status_code == 404
    monkeypatch.delenv("GERVA_LEARN")
    monkeypatch.delenv("GERVA_HOME")
    assert server.learn_path() == Path(server.ROOT) / "var" / "gerva" / "learn" / "report.json"
    monkeypatch.setenv("GERVA_HOME", str(env / "casa"))
    assert server.learn_path() == env / "casa" / "learn" / "report.json"
    monkeypatch.setenv("GERVA_LEARN", str(env / "altro.json"))
    assert server.learn_path() == env / "altro.json"
    writers = [r.path for r in server.app.routes if getattr(r, "methods", None) and r.methods & {"POST", "PUT", "PATCH", "DELETE"} and "{rest" not in r.path]
    assert writers == ["/api/v1/kill"]                     # l'unica scrittura della dashboard resta il KILL


def test_esempio_learn_ha_la_forma_attesa():
    d = json.loads(server.SAMPLE_LEARN.read_text(encoding="utf-8"))
    assert {"generated", "evaluation", "weaknesses", "improvement", "registry"} <= set(d)
    assert {"all", "paper"} <= set(d["evaluation"]) and d["evaluation"]["all"]["n"] > 0
    imp = d["improvement"]
    assert {"proposed", "shadow", "active", "tried", "threshold_t"} <= set(imp)
    for p in imp["proposed"]:
        assert set(p["checks"]) == {"numerosita", "quota", "in_campione", "fuori_campione", "walk_forward", "soglie_vicine"}
        assert p["state"] in ("RESPINTA", "IN_OMBRA")
        assert len(p["fails"]) == sum(1 for ok in p["checks"].values() if not ok)
    assert {r["state"] for r in d["registry"]} <= {"RESPINTA", "IN_OMBRA", "PROMUOVIBILE", "ATTIVA", "RITIRATA"}


def test_pagina_apprendimento_non_puo_attivare_regole():
    view = (STATIC / "js" / "views" / "apprendimento.js").read_text(encoding="utf-8")
    assert "python -m gerva learn --approve ${str(id)} --confirm" in view      # il comando si mostra…
    for vietato in ("fetch(", "XMLHttpRequest", "method: 'POST'", "h('button'", "h('form'", "h('input'", "onclick"):
        assert vietato not in view, vietato                                    # …ma la pagina non può eseguirlo
    for check in ("numerosita", "quota", "in_campione", "fuori_campione", "walk_forward", "soglie_vicine"):
        assert f"key: '{check}'" in view
    main = (STATIC / "js" / "main.js").read_text(encoding="utf-8")
    assert "id: 'apprendimento'" in main and "view: apprendimento" in main
    js = (STATIC / "js" / "glossary.js").read_text(encoding="utf-8")
    for term in ("Ombra (shadow)", "Walk-forward", "Fuori campione", "MAE / MFE"):
        assert f"term: '{term}'" in js, term
    assert "api/v1/learn" in (STATIC / "js" / "store.js").read_text(encoding="utf-8")


# ---- mercato, libro dei trade, storico, confronto (v6): sola lettura ----
def _bars(n=420, seed=1, start=100.0):
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(seed)
    close = start * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    return pd.DataFrame(dict(open=close * 0.995, high=close * 1.02, low=close * 0.98, close=close, volume=rng.uniform(1e3, 5e3, n), quote_volume=1.0), index=idx)


def _cache(env, **frames) -> Path:
    cache = env / "cache"
    cache.mkdir(exist_ok=True)
    for name, df in frames.items():
        df.to_parquet(cache / f"{name}.parquet")
    return cache


def test_mercato_in_demo_serve_l_esempio_marcato(client, env):
    r = client.get("/api/v1/market/symbols")
    assert r.status_code == 200 and r.json()["example"] is True and r.json()["source"] == "esempio"
    syms = {x["symbol"]: x["kind"] for x in r.json()["symbols"]}
    assert syms["BTC"] == "crypto" and "SPY" in syms
    r = client.get("/api/v1/market/ohlc?symbol=BTC")
    assert r.status_code == 200 and r.headers["x-gerva-source"] == "demo"
    d = r.json()
    assert d["example"] is True and d["source"] == "esempio" and d["symbol"] == "BTC"
    n = len(d["t"])
    assert n >= 300 and all(len(d[k]) == n for k in ("o", "h", "l", "c", "v", "conviction", "gq"))
    assert d["thresholds"]["conviction"] == [0.6, 0.75] and [round(x, 2) for x in d["thresholds"]["gq"]] == [-0.5, 0.53, 1.42]
    assert client.get("/api/v1/market/ohlc?symbol=NOPE").status_code == 404


def test_mercato_senza_cache_con_snapshot_vero_da_404(client, env):
    _write(env / "snapshot.json", {"meta": {"mode": "paper"}})
    assert client.get("/api/v1/market/symbols").status_code == 404
    r = client.get("/api/v1/market/ohlc?symbol=BTC")
    assert r.status_code == 404 and r.json()["ok"] is False and "o" not in r.json()


def test_ohlc_dalla_cache_con_indicatori_del_motore(client, env):
    import pandas as pd
    from gerva import ensemble as E, gervasoni as G

    btc, eth, spy = _bars(seed=1, start=60000), _bars(seed=2, start=2000), _bars(n=300, seed=3, start=500)
    _cache(env, bn_spot_1d_BTCUSDT=btc, bn_spot_1d_ETHUSDT=eth, yahoo_1d_SPY=spy.assign(adj=spy["close"]), **{"yahoo_1d_BTC-USD": btc, "yahoo_1d_^VIX": spy, "v5_um_1h_BTCUSDT": btc})
    syms = client.get("/api/v1/market/symbols").json()
    assert syms["source"] == "cache" and "example" not in syms
    assert syms["symbols"] == [dict(symbol="BTC", kind="crypto"), dict(symbol="ETH", kind="crypto"), dict(symbol="SPY", kind="etf"), dict(symbol="^VIX", kind="indice")]

    r = client.get("/api/v1/market/ohlc?symbol=eth&limit=120")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store" and "default-src 'self'" in r.headers["content-security-policy"]
    d = r.json()
    assert (d["symbol"], d["kind"], d["tf"], d["source"], d["rows"]) == ("ETH", "crypto", "1d", "cache", 120) and "example" not in d
    assert d["t"][-1] == str(eth.index[-1].date()) and d["c"][-1] == pytest.approx(float(eth["close"].iloc[-1]))
    # stessi numeri delle funzioni del fondo, calcolati su tutto lo storico e poi tagliati
    score = E.conviction(E.crypto_signals(eth[["open", "high", "low", "close", "volume"]], btc["close"]))["score"].tail(120)
    gq = G.gq(eth, eth["volume"], btc["close"]).tail(120)
    assert d["conviction"] == [None if pd.isna(v) else pytest.approx(float(v)) for v in score]
    assert d["gq"] == [None if pd.isna(v) else pytest.approx(float(v)) for v in gq]
    assert d["thresholds"] == dict(conviction=[0.6, 0.75], gq=[G.THRESHOLDS["bassa"], G.THRESHOLDS["alta"], G.THRESHOLDS["eccezionale"]])

    etf = client.get("/api/v1/market/ohlc?symbol=SPY").json()
    assert etf["kind"] == "etf" and etf["rows"] == 300 and etf["conviction"] is None and etf["gq"] is None and etf["thresholds"] is None
    assert client.get("/api/v1/market/ohlc?symbol=%5EVIX&limit=3").json()["rows"] == 10          # limite minimo 10
    assert client.get("/api/v1/market/ohlc?symbol=BTC&limit=999999").json()["rows"] == 420       # e massimo = ciò che c'è


def test_ohlc_cache_in_memoria_e_file_aggiornato(client, env):
    cache = _cache(env, bn_spot_1d_BTCUSDT=_bars(seed=1))
    first = client.get("/api/v1/market/ohlc?symbol=BTC").json()
    assert any(k[0] == "ohlc" for k in server._market_cache)
    assert client.get("/api/v1/market/ohlc?symbol=BTC").json() == first
    _bars(n=200, seed=9).to_parquet(cache / "bn_spot_1d_BTCUSDT.parquet")
    os.utime(cache / "bn_spot_1d_BTCUSDT.parquet", (1_800_000_000, 1_800_000_000))
    assert client.get("/api/v1/market/ohlc?symbol=BTC").json()["rows"] == 200                   # file cambiato: si rilegge


@pytest.mark.parametrize("symbol", ["../../etc/passwd", "..%2F..%2Fsecret", "BTC/../ETH", "BTCUSDT.parquet", "a b", "BTC;rm", "X" * 40, "", "bn_spot_1d_BTC", "%00"])
def test_ohlc_simbolo_fuori_dalla_lista_bianca(client, env, symbol):
    _cache(env, bn_spot_1d_BTCUSDT=_bars())
    (env / "secret.parquet").write_bytes(b"x")
    r = client.get(f"/api/v1/market/ohlc?symbol={symbol}")
    assert r.status_code == 400 and r.json() == {"ok": False, "error": "simbolo non valido"}
    assert str(env) not in r.text


def test_ohlc_intervallo_file_rotto_e_sola_lettura(client, env):
    cache = _cache(env, bn_spot_1d_BTCUSDT=_bars())
    assert client.get("/api/v1/market/ohlc?symbol=BTC&tf=1h").status_code == 400
    assert client.get("/api/v1/market/ohlc?symbol=ETH").status_code == 404
    (cache / "bn_spot_1d_ETHUSDT.parquet").write_bytes(b"non un parquet")
    r = client.get("/api/v1/market/ohlc?symbol=ETH")
    assert r.status_code == 503 and r.json()["ok"] is False and str(env) not in r.text
    assert client.get("/api/v1/market/ohlc?symbol=BTC", headers={"Host": "esempio.invalid"}).status_code == 400
    for url in ("/api/v1/market/ohlc?symbol=BTC", "/api/v1/market/symbols", "/api/v1/tradebook", "/api/v1/trades/history", "/api/v1/compare"):
        for method in ("post", "put", "patch", "delete"):
            assert getattr(client, method)(url).status_code == 404, (method, url)
    link = cache / "bn_spot_1d_LINKUSDT.parquet"
    try:
        link.symlink_to(env / "fuori.parquet")
        _bars().to_parquet(env / "fuori.parquet")
    except OSError:
        return
    assert client.get("/api/v1/market/ohlc?symbol=LINK").status_code == 404                      # un collegamento che esce dalla cache non si segue


def test_tradebook_demo_file_e_assente(client, env):
    r = client.get("/api/v1/tradebook")
    assert r.status_code == 200 and r.json()["example"] is True and {"open", "closed", "shadow"} <= set(r.json())
    home = env / "casa"
    home.mkdir()
    _write(home / "tradebook.json", '{"asof": "2026-11-12", "equity": 3000.0, "open": {"BTC": {"entry": 70000.0, "stop": NaN}}, "closed": [], "log": [], "shadow": [{"day": "2026-11-12", "coins": {}}]}')
    r = client.get("/api/v1/tradebook")
    assert r.status_code == 200 and "example" not in r.json() and r.json()["open"]["BTC"] == {"entry": 70000.0, "stop": None} and len(r.json()["shadow"]) == 1
    (home / "tradebook.json").write_text("{rotto", encoding="utf-8")
    assert client.get("/api/v1/tradebook").status_code == 503
    (home / "tradebook.json").unlink()
    _write(env / "snapshot.json", {"meta": {}})
    r = client.get("/api/v1/tradebook")
    assert r.status_code == 404 and r.json()["error"] == "libro dei trade non disponibile"


def test_tradebook_chiusura_per_arresto_di_emergenza_passa_intatta(client, env):
    """Il KILL chiude i trade a leva aperti con motivo «arresto di emergenza»: libro e storico lo riportano senza toccarlo."""
    home = env / "casa"
    (home / "learn").mkdir(parents=True)
    closed = [dict(symbol="BTC", opened="2026-11-10", closed="2026-11-12", entry=74120.0, exit=73010.5, leverage=11.2, tier="confermato", pnl=-48.07, R=-0.52,
                   why="arresto di emergenza"),
              dict(symbol="ETH", opened="2026-11-01", closed="2026-11-04", entry=2412.0, exit=2501.0, leverage=11.0, tier="eccezionale", pnl=40.6, R=1.3, why="tempo")]
    _write(home / "tradebook.json", dict(asof="2026-11-12", equity=2951.93, start_equity=3000.0, open={}, closed=closed,
                                         log=[dict(day="2026-11-12", event="arresto di emergenza: chiusi 1 trade")], shadow=[]))
    r = client.get("/api/v1/tradebook")
    assert r.status_code == 200 and "example" not in r.json()
    assert r.json()["closed"] == closed and r.json()["open"] == {} and r.json()["log"][0]["event"].startswith("arresto di emergenza")
    (home / "learn" / "trades.jsonl").write_text(json.dumps(dict(strategy_id="TRADE-11X", symbol="BTC", entry_time="2026-11-10", exit_time="2026-11-12", leverage=11.2,
                                                                 R=-0.52, exit_reason="arresto di emergenza", source="paper"), ensure_ascii=False) + "\n", encoding="utf-8")
    rows = client.get("/api/v1/trades/history").json()["rows"]
    assert [(x["source"], x["exit_reason"], x["R"]) for x in rows] == [("paper", "arresto di emergenza", -0.52)]


def test_storico_dei_trade_sim_e_paper_marcati(client, env):
    import pandas as pd

    assert client.get("/api/v1/trades/history").json()["example"] is True                       # demo: esempio in dotazione
    pd.DataFrame([dict(strategy_id="TRADE-11X", symbol="BTC", entry_time="2024-01-02", exit_time="2024-01-05", leverage=11.0, R=1.5, exit_reason="tempo",
                       mae=None, mfe=None, source="sim", weekday=1, tier="alta", conviction=0.7, gq=float("nan"), atr_pct=0.03, notional=None),
                  dict(strategy_id="TRADE-11X", symbol="ETH", entry_time="2024-02-01", exit_time="2024-02-02", leverage=12.0, R=-1.0, exit_reason="stop",
                       mae=None, mfe=None, source="sim", weekday=3, tier="alta", conviction=0.8, gq=0.9, atr_pct=0.04, notional=None)]).to_parquet(env / "trade_storici.parquet")
    learn = env / "casa" / "learn"
    learn.mkdir(parents=True)
    (learn / "trades.jsonl").write_text(
        json.dumps(dict(strategy_id="TRADE-11X", symbol="SOL", entry_time="2026-11-01", exit_time="2026-11-03", leverage=10.0, R=0.4, exit_reason="tempo", mae=-0.3, mfe=1.1,
                        source="paper", context=dict(weekday=6, tier="alta", conviction=0.66, gq=0.6, atr_pct=0.05))) + "\n"
        + "riga rotta\n" + json.dumps(dict(symbol="BTC", R=9.9, source="sim")) + "\n", encoding="utf-8")
    r = client.get("/api/v1/trades/history")
    assert r.status_code == 200
    d = r.json()
    assert "example" not in d and (d["n_sim"], d["n_paper"]) == (2, 1) and "SIMULATO" in d["label"]
    assert [x["source"] for x in d["rows"]] == ["sim", "sim", "paper"]
    assert d["rows"][0]["gq"] is None and d["rows"][0]["R"] == 1.5 and "notional" not in d["rows"][0]
    paper = d["rows"][2]
    assert (paper["symbol"], paper["mae"], paper["mfe"], paper["weekday"], paper["conviction"]) == ("SOL", -0.3, 1.1, 6, 0.66)
    (env / "trade_storici.parquet").unlink()
    assert [x["source"] for x in client.get("/api/v1/trades/history").json()["rows"]] == ["paper"]
    (learn / "trades.jsonl").unlink()
    _write(env / "snapshot.json", {"meta": {}})
    r = client.get("/api/v1/trades/history")
    assert r.status_code == 404 and r.json()["error"] == "storico dei trade non disponibile"


def test_confronto_csv_demo_e_assente(client, env):
    assert client.get("/api/v1/compare").json()["example"] is True
    home = env / "casa"
    home.mkdir()
    (home / "confronto_nav.csv").write_text("data,nuovo_totale,legacy_nav,legacy_fonte,spy\n2026-11-11,12000.5,1060000,manuale,\n2026-11-12,12010,,manuale,750.2\n", encoding="utf-8")
    r = client.get("/api/v1/compare")
    assert r.status_code == 200 and "example" not in r.json()
    assert r.json()["rows"] == [dict(data="2026-11-11", nuovo_totale=12000.5, legacy_nav=1060000.0, legacy_fonte="manuale", spy=None),
                                dict(data="2026-11-12", nuovo_totale=12010.0, legacy_nav=None, legacy_fonte="manuale", spy=750.2)]
    (home / "confronto_nav.csv").unlink()
    _write(env / "snapshot.json", {"meta": {}})
    r = client.get("/api/v1/compare")
    assert r.status_code == 404 and r.json()["error"] == "confronto non disponibile"


def test_esempi_v6_marcati_e_coerenti():
    ohlc = json.loads(server.SAMPLE_OHLC.read_text(encoding="utf-8"))
    assert ohlc["example"] is True and "ESEMPIO" in ohlc["label"] and {"BTC", "ETH", "SPY"} <= set(ohlc["symbols"])
    for sym, d in ohlc["symbols"].items():
        n = len(d["t"])
        assert n >= 300 and d["t"] == sorted(d["t"]) and all(len(d[k]) == n for k in ("o", "h", "l", "c", "v")), sym
        assert all(lo <= min(o, c) and hi >= max(o, c) for o, hi, lo, c in zip(d["o"], d["h"], d["l"], d["c"])), sym
        assert (d["conviction"] is not None) == (d["kind"] == "crypto")
    book = json.loads(server.SAMPLE_TRADEBOOK.read_text(encoding="utf-8"))
    assert "ESEMPIO" in book["label"] and book["open"] and book["closed"] and book["shadow"]
    for t in book["open"].values():
        assert t["liquidation"] < t["stop"] < t["entry"] and t["side"] == 1                     # lo stop sta prima della liquidazione
    trades = json.loads(server.SAMPLE_TRADES.read_text(encoding="utf-8"))
    assert "ESEMPIO" in trades["label"] and len(trades["rows"]) == trades["n_sim"] and {r["source"] for r in trades["rows"]} == {"sim"}
    cmp_ = json.loads(server.SAMPLE_COMPARE.read_text(encoding="utf-8"))
    assert "ESEMPIO" in cmp_["label"] and len(cmp_["rows"]) >= 60 and {"data", "nuovo_totale", "legacy_nav", "spy"} <= set(cmp_["rows"][0])


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
# Motore dei grafici: logica separata dallo stile, primitive presenti, galleria tecnica
# ---------------------------------------------------------------------------
CHART_JS = ("charts.js", "chart-engine.js", "candles.js", "indicators.js", "gallery.js")


def test_grafici_senza_stile_nel_codice_e_token_tutti_definiti():
    """Colori, raggi, spessori e tempi dei grafici stanno nei token --chart-*: il codice dei grafici non ne contiene."""
    js = STATIC / "js"
    defined = set(re.findall(r"(--chart-[a-z0-9-]+)\s*:", (STATIC / "css" / "tokens.css").read_text(encoding="utf-8")))
    read = set(re.findall(r"'(--chart-[a-z0-9-]+)'", (js / "chart-theme.js").read_text(encoding="utf-8")))
    used = set(re.findall(r"var\((--chart-[a-z0-9-]+)", "".join((STATIC / "css" / n).read_text(encoding="utf-8") for n in ("app.css", "glass.css"))))
    assert len(read) >= 30 and read <= defined, sorted(read - defined)
    assert len(used) >= 30 and used <= defined, sorted(used - defined)
    for name in CHART_JS:
        text = (js / name).read_text(encoding="utf-8")
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", text), name
        assert "getComputedStyle" not in text, name                                              # lo stile si chiede solo a chartTheme()
    assert "chartTheme" in (js / "candles.js").read_text(encoding="utf-8")


def test_primitive_dei_grafici_esportate():
    js = STATIC / "js"
    exported = {name: set(re.findall(r"export (?:async )?(?:function|const) (\w+)", (js / name).read_text(encoding="utf-8")))
                for name in ("charts.js", "chart-engine.js", "candles.js", "indicators.js", "chart-theme.js", "market.js")}
    assert {"timeChart", "heatmap", "histogram", "matrix", "sparkline", "tableFallback", "linearTicks", "logTicks", "timeTicks", "nearest"} <= exported["charts.js"]
    assert {"underwater", "fanChart", "stackedArea", "waterfall", "scatter", "treemap", "heatGrid", "linkCharts", "squarify", "olsLine", "drawdownOf"} <= exported["chart-engine.js"]
    assert {"candleChart", "OVERLAYS", "PANES"} <= exported["candles.js"]
    assert {"sma", "ema", "bollinger", "vwapMonth", "donchian", "atrPct", "rsi"} <= exported["indicators.js"]
    assert {"chartTheme", "onChartThemeChange", "CHART_TOKENS"} <= exported["chart-theme.js"]
    assert {"getSymbols", "getOhlc", "getTradebook", "getTrades", "getCompare"} <= exported["market.js"]


def test_galleria_tecnica_fuori_dal_prodotto_e_senza_codice_in_linea(client):
    r = client.get("/grafici.html")
    assert r.status_code == 200 and "default-src 'self'" in r.headers["content-security-policy"]
    html = r.text
    assert "ESEMPI" in html and 'name="robots" content="noindex"' in html
    assert not re.search(r"<style|\sstyle=|\son[a-z]+=", html)
    assert all("src=" in tag for tag in re.findall(r"<script[^>]*>", html))
    # le pagine del prodotto non cambiano: due livelli, nessun collegamento alla galleria, nessuna pagina Terminale
    index = (STATIC / "index.html").read_text(encoding="utf-8")
    main = (STATIC / "js" / "main.js").read_text(encoding="utf-8")
    assert "grafici.html" not in index and "grafici.html" not in main


# ---------------------------------------------------------------------------
# Guscio «vetro liquido»: spazi, livelli, fascia di stato, KILL protetto, sola lettura
# ---------------------------------------------------------------------------
DYNAMIC_PROPS = {"--bullet", "--d", "--h", "--i", "--k", "--on", "--px", "--py", "--t", "--v", "--w", "--x", "--y", "--tm-height", "--hm-bg", "--hm-ink",
                 "--hm-color", "--tm-color", "--m", "--r", "--c", "--s", "--depth", "--drift", "--delay", "--capsule-h"}


def test_guscio_senza_codice_in_linea_e_con_ordine_del_fuoco():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<style|\sstyle=|\son[a-z]+=", html)                                  # la CSP vieta stili e script in linea
    assert all("src=" in tag for tag in re.findall(r"<script[^>]*>", html))
    for css in ("css/tokens.css", "css/app.css", "css/glass.css"):
        assert f'href="{css}"' in html
    # ordine del fuoco: fascia di stato (con il KILL) → binario → contenuto
    assert html.index('id="capsule"') < html.index('id="kill-open"') < html.index('id="rail"') < html.index('id="main"')
    assert 'class="aurora"' in html and html.count('<i class="a') == 8 and 'id="dock"' in html
    for dialog in ("kill-dialog", "glossary", "cmdk", "alerts-sheet", "keys-sheet", "more-sheet"):
        assert f'id="{dialog}"' in html, dialog
    assert 'id="kill-preview"' in html and "apre la conferma, non invia" in html


def test_token_del_vetro_definiti_e_tema_scuro_predefinito():
    tokens = (STATIC / "css" / "tokens.css").read_text(encoding="utf-8")
    defined = set(re.findall(r"(--[a-z0-9-]+)\s*:", tokens))
    for name in ("--glass-panel-bg", "--glass-chrome-bg", "--glass-sheet-bg", "--aurora-1", "--aurora-6", "--kill-grad", "--kill-guard", "--prov-demo-ink", "--prov-sim-ink",
                 "--prov-paper-ink", "--prov-real-ink", "--dur-drift", "--dur-breathe", "--ease-spring", "--chart-div-1", "--chart-div-9", "--chart-fund", "--chart-orig",
                 "--chart-dash-sim", "--chart-dash-demo", "--chart-slab", "--surface-solid", "--focus"):
        assert name in defined, name
    assert re.search(r"--chart-dash-ref:\s*none;\s*--chart-dash-cross:\s*none", tokens)            # il tratteggio vuol dire «simulato»: soglie e mirino pieni
    assert "prefers-reduced-motion" in tokens and "prefers-reduced-transparency" in tokens and ":root.lite" in tokens
    assert "../fonts/" in tokens and "../static/fonts/" not in tokens and "@import" not in tokens
    for sheet in ("glass.css", "app.css"):
        css = (STATIC / "css" / sheet).read_text(encoding="utf-8")
        local = set(re.findall(r"(--[a-z0-9-]+)\s*:", css))
        used = set(re.findall(r"var\((--[a-z0-9-]+)", css))
        assert used <= defined | local | DYNAMIC_PROPS, sorted(used - defined - local - DYNAMIC_PROPS)
    init = (STATIC / "js" / "theme-init.js").read_text(encoding="utf-8")
    assert "theme === 'light' ? 'light' : 'dark'" in init and "prefers-color-scheme" not in init     # scuro salvo scelta esplicita


def test_spazi_livelli_e_indirizzi_precedenti():
    main = (STATIC / "js" / "main.js").read_text(encoding="utf-8")
    ids = re.findall(r"\{ id: '([a-z]+)', label: '[^']+', icon: '[a-z]+', key: '[a-z]'", main)
    assert ids == ["oggi", "mercati", "portafoglio", "rischio", "evidenza", "apprendimento", "sistema"]
    assert "const LEVELS = ['semplice', 'esperto', 'terminale'];" in main
    legacy = dict(re.findall(r"'?([a-z-]+)'?: '([a-z/]+)'", main[main.index("const LEGACY = {"):main.index("};", main.index("const LEGACY = {"))]))
    for old_route in ("panoramica", "performance", "esposizione", "strategie", "ordini", "ai", "ricerca", "leva-trade", "come-funziona"):
        assert old_route in legacy, old_route                                                   # le dodici pagine restano raggiungibili
    for view in ("panoramica", "performance", "esposizione", "rischioArchivio", "strategie", "ordini", "sistema", "comefunziona", "ricerca", "ai", "leva", "apprendimento", "oggi", "mercati", "rischio"):
        assert f"view: {view}" in main, view
    assert "SCONOSCIUTO" in main.upper() and "lastSeen" in main                                   # dati fermi: mai l'ultimo stato «sicuro»


def test_spazi_nuovi_e_tavolozza_in_sola_lettura():
    js = STATIC / "js"
    for name in ("main.js", "cmd.js", "panels.js", "views/oggi.js", "views/rischio2.js", "views/mercati.js"):
        text = (js / name).read_text(encoding="utf-8")
        for vietato in ("fetch(", "XMLHttpRequest", "method: 'POST'", "sendBeacon", "h('form'", "h('input'", "innerHTML", ".style ="):
            assert vietato not in text, f"{name}: {vietato}"
    kill = (js / "kill.js").read_text(encoding="utf-8")
    assert kill.count("fetch(") == 1 and "els.cancel.focus()" in kill and "e.key === 'Enter'" in kill   # l'unica scrittura; il fuoco parte da «Annulla»
    market = (js / "market.js").read_text(encoding="utf-8")
    assert "method:" not in market                                                              # solo GET
    cmd = (js / "cmd.js").read_text(encoding="utf-8")
    for group in ("Strumenti", "Spazi e schede", "Glossario", "Azioni"):
        assert f"['{group}'" in cmd, group
    oggi = (js / "views" / "oggi.js").read_text(encoding="utf-8")
    rischio = (js / "views" / "rischio2.js").read_text(encoding="utf-8")
    derive = (js / "derive.js").read_text(encoding="utf-8")
    assert "risk.dd_ladder" in derive and not re.search(r"-0\.[234]\b|0\.0[48]\b", oggi + rischio + derive)   # soglie lette dalla fotografia, mai scritte nella pagina
    assert "stress_days" in rischio and "paper_profile_cone" in oggi and "soglia non letta" in (oggi + rischio).lower()


# ---------------------------------------------------------------------------
# Una sola verità: grandezze derivate calcolate una volta (js/derive.js) ed esempi nati da un solo generatore
# ---------------------------------------------------------------------------
def _node_derive(snapshot: dict, tradebook, quant4: dict, tmp_path) -> dict:
    """Esegue js/derive.js con Node sugli oggetti dati: sono le stesse funzioni che usano Oggi, Rischio e Mercati."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("node non disponibile")
    (tmp_path / "in.json").write_text(json.dumps(dict(snap=snapshot, tb=tradebook, q4=quant4)), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text(
        "import fs from 'node:fs';\n"
        f"const D = await import({json.dumps((STATIC / 'js' / 'derive.js').as_uri())});\n"
        f"const {{ snap, tb, q4 }} = JSON.parse(fs.readFileSync({json.dumps(str(tmp_path / 'in.json'))}, 'utf8'));\n"
        "const b = D.brakes(snap); const w = D.worstCase(snap, tb, q4); const rules = { max_hold_days: 7, score_confirmed: 0.6, score_exceptional: 0.75,"
        " conviction_tiers: { crypto: [0.3, 0.6], index: [0.55, 0.82] }, gq_tiers: { eccezionale: 1.42, alta: 0.53, bassa: -0.5 }, max_data_age_h: { crypto: 36, ibkr: 100 } };\n"
        "const open = tb ? Object.values(tb.open) : [];\n"
        "console.log(JSON.stringify({ nav: D.totalNav(snap, tb), sigma: D.sigmaDay(snap), b: { hit: b.hit, next: b.next, distNext: b.distNext, reentry: b.reentry, rows: b.rows, lanes: b.lanes.map((l) => ({ id: l.id, value: l.value, limit: l.limit, ref: l.ref })) },"
        " w, days: D.stressDays(snap, q4).map((d) => ({ pnl: d.pnl, coverage: d.coverage, missing: d.missing })),"
        " lv: [0.27, 0.45, 0.64, 0.8].map((v) => D.convLevel(v, 'crypto', rules)), gq: [-1.33, 0, 0.6, 1.5].map((v) => D.gqLevel(v, rules)), noRules: D.convLevel(0.7, 'crypto', {}),"
        " age: open.map((t) => D.tradeAge(t, tb, rules)), old: D.tradeAge({ opened: '2026-01-01' }, { asof: '2026-01-21' }, rules),"
        " fresh: [D.freshness(Date.UTC(2026, 0, 10), Date.UTC(2026, 0, 11, 12), 'crypto', rules), D.freshness(Date.UTC(2026, 0, 1), Date.UTC(2026, 0, 13), 'crypto', rules), D.freshness(Date.UTC(2026, 0, 1), Date.UTC(2026, 0, 13), 'crypto', {})] }));\n",
        encoding="utf-8")
    res = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr[-800:]
    return json.loads(res.stdout)


def _samples():
    return (json.loads(server.SAMPLE.read_text(encoding="utf-8")), json.loads(server.SAMPLE_TRADEBOOK.read_text(encoding="utf-8")),
            json.loads(server.SAMPLE_OHLC.read_text(encoding="utf-8")), json.loads(server.SAMPLE_COMPARE.read_text(encoding="utf-8")))


STRESS = dict(stress_days=dict(days=[
    dict(date="2020-03-12", name="Crollo", shocks=dict(BTC=-0.40, ETH=-0.45, SPY=-0.10, GLD=-0.03, IEF=0.01, EFA=-0.10, QQQ=-0.09)),      # SOL manca: non coperto
    dict(date="2024-08-05", name="Lunedi nero", shocks=dict(BTC=-0.08, ETH=-0.10, SOL=-0.12, SPY=-0.03, GLD=-0.01, IEF=0.01, EFA=-0.02, QQQ=-0.03))]))


def test_una_sola_verita_patrimonio_sigma_freni(tmp_path):
    snap, tb, _, _ = _samples()
    out = _node_derive(snap, tb, STRESS, tmp_path)
    nav, risk = snap["nav"], snap["risk"]
    # patrimonio in testa = libro giornaliero + contributo dei trade (stesso capitale, non un secondo conto)
    assert out["nav"]["total"] == pytest.approx(nav["equity"] + tb["equity"] - tb["start_equity"]) and out["nav"]["complete"] is True
    # σ della giornata sulla volatilità OBIETTIVO, non su quella realizzata
    assert out["sigma"]["z"] == pytest.approx(nav["pnl_day_pct"] / (risk["vol_target"] / 365 ** 0.5)) and out["sigma"]["target"] == risk["vol_target"]
    # freni: una riga per ogni scalino, distanze e «scatta a» da una sola formula
    ladder = sorted((st["level"] for st in risk["dd_ladder"]), reverse=True)
    rows = out["b"]["rows"]
    assert [r["level"] for r in rows[:3]] == ladder and out["b"]["hit"] == 0 and out["b"]["next"]["level"] == ladder[0]
    assert out["b"]["distNext"] == pytest.approx(nav["drawdown_pct"] - ladder[0])
    for r in rows[:3]:
        assert r["at"] == pytest.approx(nav["high_water"] * (1 + r["level"])) and r["eur"] == pytest.approx(r["dist"] * nav["high_water"])
    # finestre mobili dalla curva: mai lo 0,00% di min(pnl, 0); «scatta a» = patrimonio di riferimento × (1 + soglia)
    curve = [p["equity"] for p in snap["equity_curve"]]
    d1, d7 = out["b"]["lanes"]
    assert d1["value"] == pytest.approx(curve[-1] / curve[-2] - 1) and d7["value"] == pytest.approx(curve[-1] / curve[-8] - 1) and d7["value"] != 0
    assert rows[3]["at"] == pytest.approx(curve[-2] * (1 + d1["limit"])) and rows[4]["at"] == pytest.approx(curve[-8] * (1 + d7["limit"]))


def test_una_sola_verita_peggior_caso_stress_e_scalino_successivo(tmp_path):
    snap, tb, _, _ = _samples()
    out = _node_derive(snap, tb, STRESS, tmp_path)
    w, nav = out["w"], snap["nav"]
    # uno shock che manca non vale zero: SOL non è coperto, la stima è un minimo e non si dichiara «nessun freno»
    sol = next(p["weight"] for p in snap["positions"] if p["symbol"] == "SOL")
    gross = sum(abs(p["weight"]) for p in snap["positions"])
    assert out["days"][0]["missing"] == ["SOL"] and out["days"][0]["coverage"] == pytest.approx(1 - abs(sol) / gross) and out["days"][1]["coverage"] == pytest.approx(1.0)
    assert w["atLeast"] is True and w["coverage"] < 1
    # stessa grandezza, un solo numero: perdita, patrimonio finale e caduta dal massimo tornano tra loro
    margins = sum(t["margin"] for t in tb["open"].values())
    assert w["total"] == pytest.approx(margins + w["gap"]) and w["final"] == pytest.approx(nav["equity"] - w["total"])
    assert w["loss"] == pytest.approx(w["total"] / nav["equity"]) and w["ddAfter"] == pytest.approx(w["final"] / nav["high_water"] - 1)
    # senza libro dei trade resta «almeno»
    assert _node_derive(snap, None, STRESS, tmp_path)["w"]["atLeast"] is True
    # superato uno scalino, la distanza è dal PROSSIMO e c'è la condizione di rientro (metà della soglia scattata)
    red = json.loads(json.dumps(snap))
    red["nav"]["drawdown_pct"] = -0.224
    b = _node_derive(red, tb, STRESS, tmp_path)["b"]
    ladder = sorted((st["level"] for st in snap["risk"]["dd_ladder"]), reverse=True)
    assert b["hit"] == 1 and b["next"]["level"] == ladder[1] and b["distNext"] == pytest.approx(-0.224 - ladder[1]) and b["reentry"] == pytest.approx(ladder[0] / 2)
    assert b["rows"][0]["hit"] is True and b["rows"][1]["hit"] is False
    # livelli con i nomi del motore; senza regole nessun nome inventato
    assert [(x["tier"], x["trade"]) for x in out["lv"]] == [("bassa", None), ("media", None), ("alta", "confermato"), ("alta", "eccezionale")]
    assert out["gq"] == ["bassa", "media", "alta", "eccezionale"] and out["noRules"]["tier"] is None
    # trade: giorni contati fino alla data del libro; oltre la durata massima è un'anomalia; freschezza contro il massimo
    assert all(a["held"] is not None and a["held"] <= 7 and a["over"] is False for a in out["age"]) and out["old"] == dict(held=20, maxHold=7, over=True)
    assert [f["stale"] for f in out["fresh"]] == [False, True, None]


def test_spazi_usano_le_stesse_funzioni_derivate():
    js = STATIC / "js"
    oggi = (js / "views" / "oggi.js").read_text(encoding="utf-8")
    rischio = (js / "views" / "rischio2.js").read_text(encoding="utf-8")
    mercati = (js / "views" / "mercati.js").read_text(encoding="utf-8")
    for name, text in (("oggi", oggi), ("rischio2", rischio), ("mercati", mercati)):
        assert "from '../derive.js'" in text, name
        for vietato in ("function worstCase", "function applyStress", "function stressDays", "function tradeR", "vol_realized_30d / ", "Math.sqrt(365)", "conto separato"):
            assert vietato not in text, f"{name}: {vietato}"                                    # nessun secondo calcolo della stessa grandezza
    assert "worstCase(snap, tb, ctxNow.quant4)" in rischio and "brakes(ctx.snap)" in oggi and "ladderData" in rischio
    assert "totalNav(snap, tb)" in oggi and "sigmaDay(snap)" in oggi and "tradeAge(" in oggi and "tradeAge(" in mercati and "convLevel(" in mercati
    derive = (js / "derive.js").read_text(encoding="utf-8")
    assert not re.search(r"\bdocument\.|\bwindow\.", derive)                                   # funzioni pure: le esegue anche Node nei test


def test_esempi_un_solo_insieme_coerente():
    """Fotografia, barre, libro dei trade e confronto nascono da dashboard/tools/build_samples.py: una sola storia."""
    snap, tb, ohlc, cmp_ = _samples()
    day = snap["meta"]["as_of"][:10]
    bars = ohlc["symbols"]
    # stesso giorno di riferimento ovunque
    assert tb["asof"] == day and cmp_["rows"][-1]["data"] == day and snap["equity_curve"][-1]["t"][:10] == day
    assert all(bars[s]["t"][-1] == day for s in ("BTC", "ETH", "SOL"))
    # un solo prezzo per strumento: le posizioni sono valorizzate all'ultima chiusura delle barre, il confronto riporta la stessa
    for p in snap["positions"]:
        if p["symbol"] in bars:
            assert p["price"] == pytest.approx(bars[p["symbol"]]["c"][-1]), p["symbol"]
    assert cmp_["rows"][-1]["btc"] == pytest.approx(bars["BTC"]["c"][-1])
    # un solo patrimonio: il confronto è la curva della fotografia più il contributo dei trade
    last = cmp_["rows"][-1]
    assert last["nuovo_libro"] == pytest.approx(snap["nav"]["equity"]) and last["nuovo_trade"] == pytest.approx(tb["equity"] - tb["start_equity"], abs=0.01)
    assert last["nuovo_totale"] == pytest.approx(last["nuovo_libro"] + last["nuovo_trade"], abs=0.01)
    curve = {p["t"][:10]: p["equity"] for p in snap["equity_curve"]}
    assert all(r["nuovo_libro"] == pytest.approx(curve[r["data"]]) for r in cmp_["rows"] if r["data"] in curve)
    assert tb["start_equity"] == pytest.approx(cmp_["rows"][0]["nuovo_libro"])                     # il libro lavora sullo stesso capitale
    # trade costruiti sulle barre: R × rischio = P&L, prezzi dentro la candela del giorno, durata entro il massimo, livelli coerenti con il rischio
    dates = {s: {d: i for i, d in enumerate(bars[s]["t"])} for s in ("BTC", "ETH", "SOL")}
    assert len(tb["closed"]) >= 10 and tb["open"]
    for t in tb["closed"]:
        b, i, j = bars[t["symbol"]], dates[t["symbol"]][t["opened"]], dates[t["symbol"]][t["closed"]]
        assert t["pnl"] == pytest.approx(t["R"] * t["risk"], abs=0.02) and t["entry"] == pytest.approx(b["c"][i]) and b["l"][j] - 1e-6 <= t["exit"] <= b["h"][j] + 1e-6
        assert 1 <= j - i <= 7 and t["tier"] == ("eccezionale" if b["conviction"][i] >= 0.75 else "confermato") and b["conviction"][i] >= 0.60
    assert tb["equity"] == pytest.approx(tb["start_equity"] + sum(t["pnl"] for t in tb["closed"]), abs=0.05)
    for sym, t in tb["open"].items():
        i = dates[sym][t["opened"]]
        assert t["entry"] == pytest.approx(bars[sym]["c"][i]) and len(bars[sym]["t"]) - 1 - i <= 7
        assert t["liquidation"] < t["stop"] < t["entry"] and t["risk"] == pytest.approx(t["notional"] * t["initial_stop_distance"], rel=0.01)
        assert t["margin"] == pytest.approx(t["notional"] / t["leverage"], rel=0.01)
    # cancelli: nomi e soglie del motore (90 giorni), giorni di paper = lunghezza della storia della fotografia
    from gerva.live import gates as G
    gates = {g["name"]: g for g in snap["gates"]}
    assert gates["Giorni di paper trading"]["target"] == G.MIN_DAYS == 90 and gates["Giorni di paper trading"]["value"] == snap["performance"]["days"]
    assert "Sharpe in paper (minimo)" not in gates and gates["PSR (Sharpe vero > 0)"]["target"] == G.MIN_PSR
    # livelli scritti con i nomi del motore
    for row in tb["shadow"]:
        for c in row["coins"].values():
            assert c["conviction_tier"] in ("bassa", "media", "alta") and c["gq_tier"] in ("bassa", "media", "alta", "eccezionale")
            assert c["conviction_tier"] == ("alta" if c["conviction"] > 0.60 else "media" if c["conviction"] > 0.30 else "bassa")
    assert all(str(x.get("label", "")).startswith("ESEMPIO") for x in (tb, ohlc, cmp_))


def test_demo_tutti_gli_esempi_alla_data_di_oggi_e_regole_dal_motore(client):
    """In modalità demo gli esempi si spostano insieme a oggi: mai una fotografia «di adesso» accanto a un libro vecchio di giorni."""
    today = datetime.now(timezone.utc).date().isoformat()
    snap = client.get("/api/v1/snapshot").json()
    tb = client.get("/api/v1/tradebook").json()
    assert snap["meta"]["as_of"][:10] == today and snap["equity_curve"][-1]["t"][:10] == today and tb["asof"] == today and tb["example"] is True
    assert client.get("/api/v1/market/ohlc?symbol=BTC").json()["t"][-1] == today
    assert client.get("/api/v1/compare").json()["rows"][-1]["data"] == today
    btc = tb["open"]["BTC"]
    assert (datetime.fromisoformat(today) - datetime.fromisoformat(btc["opened"])).days <= 7
    rules = client.get("/api/v1/health").json()["rules"]
    assert rules["max_hold_days"] == 7 and rules["score_confirmed"] == 0.60 and rules["score_exceptional"] == 0.75
    assert rules["conviction_tiers"]["crypto"] == [0.30, 0.60] and set(rules["gq_tiers"]) == {"eccezionale", "alta", "bassa"}
    if "max_data_age_h" in rules:
        assert rules["max_data_age_h"]["crypto"] == 36.0


def test_grafici_righello_inquadrato_e_kill_spento_senza_token():
    """Giro 2, blocchi B e C: il righello del trade resta nel quadro, i segni non escono dal prezzo, il KILL senza token non si abilita."""
    js = STATIC / "js"
    candles = (js / "candles.js").read_text(encoding="utf-8")
    assert "m.kind === 'level' && !m.past && m.price > 0" in candles                           # i livelli attivi allargano la scala del prezzo
    assert "ctx.rect(0, pp.y0, plotW, pp.y1 - pp.y0); ctx.clip();" in candles and "m.kind === 'rscale'" in candles
    assert "function applyRange" in candles and "chartTheme().reducedMotion" in candles          # transizione dell'intervallo, spenta con «riduci movimento»
    mercati = (js / "views" / "mercati.js").read_text(encoding="utf-8")
    assert "paintLegend" in mercati and "chart.setPanes([...panesOn])" in mercati and "function distances" in mercati and "Trade · esempio" in mercati
    kill = (js / "kill.js").read_text(encoding="utf-8")
    assert "export function setKillEnabled" in kill and "!(enabled && els.token.value.length > 0" in kill
    main = (js / "main.js").read_text(encoding="utf-8")
    assert "setKillEnabled(hl.kill_enabled !== false)" in main and "'serve il token'" in main
    css = (STATIC / "css" / "glass.css").read_text(encoding="utf-8")
    for needle in ("chart-reveal", ".key--ov-vwap", ".app::before", ".linkrow--primary", "clip-path: inset(calc(var(--topbar-h) + 26px) 0 0 0)", ".more__nav .nav__label { display: inline; }"):
        assert needle in css, needle


# ---------------------------------------------------------------------------
# L'esempio: completo e coerente
# ---------------------------------------------------------------------------
def test_esempio_usa_le_soglie_di_rischio_della_configurazione():
    """La fotografia di esempio mostra gli stessi limiti di config/gerva.yaml (scalini, perdite a 24 ore e 7 giorni, sede crypto)."""
    yaml = pytest.importorskip("yaml")
    cfg = Path(server.ROOT) / "config" / "gerva.yaml"
    if not cfg.is_file():
        pytest.skip("configurazione non presente")
    lim = yaml.safe_load(cfg.read_text(encoding="utf-8"))["limits"]
    risk = json.loads(server.SAMPLE.read_text(encoding="utf-8"))["risk"]
    assert [s["level"] for s in risk["dd_ladder"]] == [-lim["dd_reduce"], -lim["dd_halt"], -lim["dd_kill"]]
    by_name = {row["name"]: row for row in risk["limits"]}
    assert by_name["Caduta dal massimo"]["limit"] == -lim["dd_kill"]
    assert by_name["Perdita a 24 ore"]["limit"] == -lim["daily_loss"] and by_name["Perdita a 7 giorni"]["limit"] == -lim["weekly_loss"]
    assert by_name["Esposizione sulla sede crypto"]["limit"] == lim["max_venue"]["crypto"] and by_name["Leva lorda"]["limit"] == lim["max_leverage"]
    assert by_name["Peso massimo di uno strumento"]["limit"] == lim["max_weight"] and risk["vol_target"] == lim["vol_target"]
    assert by_name["Esposizione sulla sede crypto"]["value"] < lim["max_venue"]["crypto"]            # l'esempio non mostra un limite violato
    assert all(row["status"] in ("ok", "warn") for row in risk["limits"])


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
