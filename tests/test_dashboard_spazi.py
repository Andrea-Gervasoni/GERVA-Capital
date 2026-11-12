"""
Spazi Evidenza, Portafoglio, Apprendimento e Sistema della dashboard (dashboard/static/js/views/evidenza.js, portafoglio.js,
apprendimento2.js, sistema2.js, kit.js; css/spaces.css; le funzioni aggiunte a js/derive.js).

Che cosa si verifica: gli spazi sono instradati e le pagine precedenti restano raggiungibili; nessuna vista scrive o attiva
qualcosa; soglie e criteri non sono scritti nelle viste; le grandezze derivate (z contro l'originale, intervallo del Deflated
Sharpe, attribuzione, cancelli, età per fonte, R per fetta) sono calcolate una volta in derive.js e tornano con la fonte.
"""
import importlib.util
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dashboard import server

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(server.STATIC)
JS = STATIC / "js"
VIEWS = ("evidenza.js", "portafoglio.js", "apprendimento2.js", "sistema2.js", "kit.js")
QUANT4 = ROOT / "research" / "v5" / "quant_v4.json"


def _view(name: str) -> str:
    return (JS / "views" / name).read_text(encoding="utf-8")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Modalità demo pura: nessuno snapshot, nessuna cartella del motore, nessuna cache dei prezzi."""
    monkeypatch.setenv("GERVA_SNAPSHOT", str(tmp_path / "snapshot.json"))
    monkeypatch.setenv("GERVA_KILL_FILE", str(tmp_path / "KILL"))
    monkeypatch.setenv("GERVA_HOME", str(tmp_path / "casa"))
    monkeypatch.setenv("GERVA_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("GERVA_LEARN", str(tmp_path / "learn" / "report.json"))
    monkeypatch.setenv("GERVA_TRADES_HIST", str(tmp_path / "trade_storici.parquet"))
    monkeypatch.delenv("GERVA_DASH_TOKEN", raising=False)
    server._market_cache.clear()
    return TestClient(server.app, base_url="http://127.0.0.1:8787")


# ---------------------------------------------------------------------------
# Instradamento e sola lettura
# ---------------------------------------------------------------------------
def test_quattro_spazi_instradati_e_pagine_precedenti_raggiungibili():
    main = (JS / "main.js").read_text(encoding="utf-8")
    for space, view in (("evidenza", "evidenza"), ("portafoglio", "portafoglio"), ("apprendimento", "apprendimentoNuovo"), ("sistema", "sistemaNuovo")):
        block = main[main.index(f"{{ id: '{space}',"):]
        first = re.search(r"tabs: \[\s*\{ id: '', label: '[^']+', view: (\w+) \}", block)
        assert first and first.group(1) == view, (space, first and first.group(1))            # la scheda predefinita è lo spazio nuovo
    for old in ("ricerca", "leva", "performance", "strategie", "esposizione", "panoramica", "apprendimento", "sistema", "ordini", "comefunziona"):
        assert f"view: {old} " in main or f"view: {old}}}" in main, old                         # il contenuto non migrato resta in archivio
    assert '<link rel="stylesheet" href="css/spaces.css">' in (STATIC / "index.html").read_text(encoding="utf-8")
    for name in VIEWS:
        assert (JS / "views" / name).is_file(), name


def test_viste_in_sola_lettura_e_senza_stili_in_linea():
    for name in VIEWS:
        text = _view(name)
        for vietato in ("fetch(", "XMLHttpRequest", "method: 'POST'", "sendBeacon", "h('form'", "h('input'", "innerHTML", ".style =", "localStorage", "eval("):
            assert vietato not in text, f"{name}: {vietato}"
        assert "http://" not in text and "https://" not in text, name                           # nessuna risorsa esterna
    # l'unico pulsante dei quattro spazi apre il centro avvisi; nessuno invia ordini o attiva regole
    assert _view("sistema2.js").count("h('button'") == 1 and "api.openAlerts()" in _view("sistema2.js")
    for name in ("evidenza.js", "portafoglio.js", "apprendimento2.js", "kit.js"):
        assert "h('button'" not in _view(name), name


def test_apprendimento_mostra_il_comando_ma_non_puo_attivare():
    view = _view("apprendimento2.js")
    assert "`python -m gerva learn --approve ${str(id)} --confirm`" in view                    # il comando esatto si mostra…
    for vietato in ("h('button'", "onclick", "addEventListener('click'", "api.", "fetch("):
        assert vietato not in view, vietato                                                    # …ma lo spazio non può eseguirlo
    for check in ("numerosita", "quota", "in_campione", "fuori_campione", "walk_forward", "soglie_vicine"):
        assert f"key: '{check}'" in view, check                                                # i sei controlli del validatore
    assert view.count("title: '") >= 7 + 10                                                    # sette passaggi più i riquadri
    for testo in ("Chi propone non approva.", "può solo saltare o dimezzare", "alza la soglia", "Nessun trade paper ancora", "0 trade paper chiusi", "Nessuna regola in ombra", "Nessuna regola attiva"):
        assert testo in view, testo
    # simulati e paper mai nella stessa statistica: le serie si leggono sempre per fonte
    assert "rows('sim')" in view and "rows('paper')" in view and "str(r.source) === src" in view


def test_soglie_e_criteri_non_scritti_nelle_viste():
    """Scalini, soglia del Deflated Sharpe, numero di prove, z di decisione: arrivano dai dati o da derive.js, mai dalla vista."""
    for name in ("evidenza.js", "portafoglio.js", "sistema2.js", "apprendimento2.js"):
        text = _view(name)
        assert not re.search(r"-0\.[234]\b|0\.0[48]\b|\b0\.95\b|\b4\.?071\b|\b1\.24\b|\b1\.3\b", text), name
    ev = _view("evidenza.js")
    for campo in ("paper_profile_cone", "fund_curves", "fund_stats", "fund_mc", "candidates", "stop_table", "tier_mc", "stress", "venues", "recommended"):
        assert campo in ev, campo
    for fn in ("luck(", "compareStats(", "coneData(", "provenanceDays(", "SPLIT_T"):
        assert fn in ev, fn                                                                    # le grandezze derivate vengono da derive.js
    pf = _view("portafoglio.js")
    assert "attribution(snap, tb, period)" in pf and "exposure_history" in pf and "rollingSharpe(" in pf
    si = _view("sistema2.js")
    assert "gateState" in si and "sourceAges(" in si and "Non ancora misurabile" in si
    assert "risk.limits" in pf and "rules" in si


def test_ogni_riquadro_dichiara_la_provenienza():
    for name, minimo in (("evidenza.js", 10), ("portafoglio.js", 8), ("apprendimento2.js", 9), ("sistema2.js", 7)):
        text = _view(name)
        panels = len(re.findall(r"= panel\(\{", text))
        assert panels >= minimo and text.count(".setProv(") >= panels, (name, panels, text.count(".setProv("))
    assert "provTag('sim'" in _view("evidenza.js") and "provTag(demo ? 'demo' : 'paper'" in _view("evidenza.js")


def test_css_degli_spazi_usa_solo_token_definiti():
    css = (STATIC / "css" / "spaces.css").read_text(encoding="utf-8")
    tokens = (STATIC / "css" / "tokens.css").read_text(encoding="utf-8")
    defined = set(re.findall(r"(--[a-z0-9-]+)\s*:", tokens))
    local = set(re.findall(r"(--[a-z0-9-]+)\s*:", css)) | {"--a", "--b", "--t", "--v", "--i", "--m", "--cols", "--tm-color", "--tag-top", "--k", "--h"}
    used = set(re.findall(r"var\((--[a-z0-9-]+)", css))
    assert used - defined - local == set(), sorted(used - defined - local)
    assert "url(" not in css and "@import" not in css
    assert not re.search(r"#[0-9a-fA-F]{6}\b", css)                                            # i colori stanno nei token (solo #000/#fff nei miscugli)
    assert "prefers-reduced-motion" in css


# ---------------------------------------------------------------------------
# Una sola verità: le funzioni di derive.js usate dai quattro spazi
# ---------------------------------------------------------------------------
def _node(body: str, data: dict, tmp_path) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node non disponibile")
    (tmp_path / "in.json").write_text(json.dumps(data), encoding="utf-8")
    script = tmp_path / "run.mjs"
    script.write_text(
        "import fs from 'node:fs';\n"
        f"const D = await import({json.dumps((JS / 'derive.js').as_uri())});\n"
        f"const I = JSON.parse(fs.readFileSync({json.dumps(str(tmp_path / 'in.json'))}, 'utf8'));\n"
        f"console.log(JSON.stringify({body}));\n", encoding="utf-8")
    res = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr[-800:]
    return json.loads(res.stdout)


def _confronto():
    path = ROOT / "research" / "v5" / "v6" / "b8_confronto" / "confronto.py"
    if not path.is_file():
        pytest.skip("confronto.py non presente")
    spec = importlib.util.spec_from_file_location("confronto_b8", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rows(n: int, seed: int = 7) -> list[dict]:
    import random
    rnd = random.Random(seed)
    a, b, out = 10000.0, 1_000_000.0, []
    for i in range(n):
        if i:
            a *= 1 + rnd.gauss(0.0012, 0.009)
            b *= 1 + rnd.gauss(0.0004, 0.012)
        out.append(dict(data=f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", nuovo_totale=round(a, 2), legacy_nav=round(b, 2), legacy_flusso=0.0, eurusd=1.08, spy=500.0, btc=60000.0))
    return out


def test_z_contro_l_originale_uguale_a_confronto_py(tmp_path):
    C = _confronto()
    rows = _rows(150)
    out = _node("D.compareStats({ rows: I.rows })", dict(rows=rows), tmp_path)
    s = C.series(rows)
    ds = C.diff_stats(s["nuovo"], s["legacy"], s["per_year"])
    assert out["n"] == ds["n"] == 149
    assert out["z"] == pytest.approx(ds["z_vol"], rel=1e-9) and out["zRaw"] == pytest.approx(ds["z_raw"], rel=1e-9)
    assert out["rho"] == pytest.approx(ds["rho"], rel=1e-9) and out["need10"] == ds["need_10"] and out["need05"] == ds["need_05"]
    assert out["needNow"] == ds["need_now"]
    assert out["minDays"] == C.MIN_DAYS and out["zWin"] == C.Z_WIN                              # stessi criteri del motore di confronto
    # distacco cumulato e imbuto: la somma finale vale z × dev(u) × √n, quindi «dentro l'imbuto» equivale a |z| < soglia
    assert out["cumU"][-1] == pytest.approx(out["z"] * out["su"] * math.sqrt(out["n"]), rel=1e-9)
    esito = C.verdict(C.perf(s["nuovo"], s["per_year"]), C.perf(s["legacy"], s["per_year"]), ds, s["span_days"])[0]
    assert {"beats": "BATTE (criterio B", "beaten": "BATTUTO", "open": ("BATTE (criterio A", "NON BATTE")}[out["verdict"]["code"]]
    assert esito.startswith({"beats": "BATTE (criterio B", "beaten": "BATTUTO", "open": ("BATTE (criterio A", "NON BATTE")}[out["verdict"]["code"]])


def test_confronto_con_pochi_giorni_lo_dice(tmp_path):
    out = _node("[D.compareStats({ rows: I.rows.slice(0, 3) }), D.compareStats({ rows: I.rows.slice(0, 30) }), D.compareStats(null)]", dict(rows=_rows(40)), tmp_path)
    assert out[0]["z"] is None and out[0]["verdict"]["code"] == "few" and "almeno 3" in out[0]["verdict"]["why"]
    assert out[1]["z"] is not None and out[1]["verdict"]["code"] == "running" and "su 90" in out[1]["verdict"]["why"]
    assert out[2]["rows"] == 0 and out[2]["z"] is None
    sample = json.loads(server.SAMPLE_COMPARE.read_text(encoding="utf-8"))
    demo = _node("D.compareStats(I)", sample, tmp_path)
    assert demo["verdict"]["code"] in ("few", "running") and demo["span"] < demo["minDays"]      # l'esempio ha pochi giorni: nessun vincitore


def test_fortuna_intervallo_e_soglia_dal_file(tmp_path):
    q4 = dict(trials=4071, deflated_sharpe=dict(old=0.6375, new=0.76083, fund=0.6361, threshold=0.95, expected_max=1.24054, note="x"))
    out = _node("[D.luck(I.a), D.luck(I.b), D.luck({}), D.normInv(0.975)]", dict(a=q4, b=dict(q4, deflated_sharpe=dict(q4["deflated_sharpe"], threshold=0.5))), tmp_path)
    a, b, vuoto, z = out
    assert a["lo"] == pytest.approx(0.6361) and a["hi"] == pytest.approx(0.76083) and a["pass"] is False and a["threshold"] == 0.95
    assert b["pass"] is True and vuoto is None                                                  # la soglia è quella del file, non della pagina
    assert a["seNull"] == pytest.approx(1 / math.sqrt(8.59), abs=0.01)                          # errore standard nullo ≈ 1/√anni
    assert z == pytest.approx(1.96, abs=0.001)
    if QUANT4.is_file():
        real = _node("D.luck(I)", json.loads(QUANT4.read_text(encoding="utf-8")), tmp_path)
        assert real["trials"] >= 4000 and real["lo"] <= real["hi"] < real["threshold"] and real["pass"] is False


def test_attribuzione_cancelli_fette_e_fonti(tmp_path):
    snap = json.loads(server.SAMPLE.read_text(encoding="utf-8"))
    tb = json.loads(server.SAMPLE_TRADEBOOK.read_text(encoding="utf-8"))
    trades = [dict(R=r, symbol=("BTC", "ETH")[i % 2], source="sim") for i, r in enumerate([-1.0, -1.0, 2.5, 0.4, -0.6, 7.2, -1.1, 0.0])]
    rules = dict(max_data_age_h=dict(crypto=36, ibkr=100), interval_s=900)
    now = 1_800_000_000_000
    body = ("{ day: D.attribution(I.snap, I.tb, 'day'), tot: D.attribution(I.snap, I.tb, 'total'), noTb: D.attribution(I.snap, null, 'total'),"
            " gates: [{ value: null, ok: true }, { value: 3, ok: true }, { value: 3, ok: false }].map(D.gateState),"
            " st: D.rStats(I.trades.map((t) => t.R)), by: D.groupR(I.trades, (t) => t.symbol), hist: D.histR(I.trades.map((t) => t.R), 0.25, -1.5, 6),"
            " ages: D.sourceAges({ snap: { meta: { as_of: new Date(I.now - 5000).toISOString(), stale_after_s: 120 }, system: { heartbeat_age_s: 4000 } }, health: { rules: I.rules }, now: I.now,"
            "   tradebook: { asof: '2026-01-01' }, compare: null, bars: [{ symbol: 'BTC', kind: 'crypto', t: I.now - 20 * 3600000 }, { symbol: 'SPY', kind: 'ibkr', t: I.now - 200 * 3600000 }] }),"
            " noRules: D.sourceAges({ snap: {}, health: {}, now: I.now, tradebook: null, compare: null }),"
            " days: D.provenanceDays(I.snap, { fund_curves: { a: [['2018-04-01', 1], ['2018-04-11', 1.1]] } }) }")
    out = _node(body, dict(snap=snap, tb=tb, trades=trades, rules=rules, now=now), tmp_path)
    day, tot = out["day"], out["tot"]
    assert sum(r["value"] for r in day["rows"]) + day["gap"] == pytest.approx(snap["nav"]["pnl_day"], abs=0.01) and day["trade"] is None
    assert tot["trade"] == pytest.approx(tb["equity"] - tb["start_equity"], abs=0.01) and tot["total"] == pytest.approx(tot["daily"] + tot["trade"], abs=0.01)
    assert tot["estimate"] is True and out["noTb"]["trade"] is None                             # libro assente: n.d., mai zero
    assert out["gates"] == ["unmeasured", "ok", "open"]                                         # senza valore non è mai «superato»
    st = out["st"]
    assert st["n"] == 8 and st["mean"] == pytest.approx(0.8) and st["lo"] < st["mean"] < st["hi"] and st["win"] == pytest.approx(3 / 8)
    assert st["hi"] - st["mean"] == pytest.approx(1.645 * st["sd"] / math.sqrt(8))              # baffo al 90%
    assert [g["key"] for g in out["by"]] == ["BTC", "ETH"] and sum(g["n"] for g in out["by"]) == 8
    assert sum(out["hist"]["counts"]) == 8 and out["hist"]["counts"][-1] == 1                   # +7,2 R finisce nell'ultima classe, dichiarata
    ages = {a["id"]: a for a in out["ages"]}
    assert ages["snap"]["state"] == "ok" and ages["hb"]["state"] == "stale" and ages["tb"]["state"] == "stale" and ages["cmp"]["state"] == "missing"
    assert ages["bar-BTC"]["state"] == "ok" and ages["bar-SPY"]["state"] == "stale"
    assert {a["state"] for a in out["noRules"]} <= {"missing", "unknown"}                       # limiti non letti: mai un valore predefinito
    assert out["days"]["sim"] == 10 and out["days"]["paper"] == 12 and out["days"]["real"] == 0


def test_cono_e_confine_scelta_verifica(tmp_path):
    if not QUANT4.is_file():
        pytest.skip("quant_v4.json non presente")
    snap = json.loads(server.SAMPLE.read_text(encoding="utf-8"))
    q4 = json.loads(QUANT4.read_text(encoding="utf-8"))
    out = _node("{ c: (() => { const c = D.coneData(I.snap, I.q4); return { pct: c.pctNow, days: c.days, hz: c.horizon, n: c.x.length, last: c.last, where: c.where }; })(),"
                " none: D.coneData(I.snap, {}), split: D.SPLIT_T, dd: D.drawdownSeries([1, 1.2, 0.9, 1.5]) }", dict(snap=snap, q4=q4), tmp_path)
    c = out["c"]
    assert c["days"] == 12 and 0.05 <= c["pct"] <= 0.95 and c["hz"] >= 3 and c["n"] == c["hz"] * 10 + 1 and c["where"]
    assert out["none"] is None                                                                  # manca il Monte Carlo: stato vuoto, non una fascia finta
    assert out["split"] == 1672531200000                                                        # 1° gennaio 2023
    assert out["dd"] == [0, 0, pytest.approx(-0.25), 0]


# ---------------------------------------------------------------------------
# I dati che gli spazi leggono esistono e hanno la forma attesa
# ---------------------------------------------------------------------------
def test_ricerca_vera_ha_i_campi_dell_evidenza():
    if not QUANT4.is_file():
        pytest.skip("quant_v4.json non presente")
    q = json.loads(QUANT4.read_text(encoding="utf-8"))
    dd = q["paper_profile_cone"]["drawdown"]
    assert len(dd["edges"]) == len(dd["counts"]) + 1 and len(dd["steps"]) == 3
    assert all(f"p_reach_{round(-s * 100)}" in dd or i == 2 for i, s in enumerate(dd["steps"])) and "p_kill" in dd
    assert {"mese_medio", "mese_mediano", "sh_scelta", "sh_verifica"} <= set(q["fund_stats"][0])
    assert q["recommended"]["prudent"] in q["fund_curves"] and all({"verdict", "name"} <= set(c) for c in q["candidates"])
    assert {"coin", "leverage", "p_liq_24h"} <= set(q["stress"][0]) and {"schema", "scenario", "cagr_p50"} <= set(q["tier_mc"][0])


def test_fonti_degli_spazi_in_demo(client):
    learn = client.get("/api/v1/learn").json()
    assert learn["example"] is True and {"proposed", "shadow", "active", "tried", "threshold_t"} <= set(learn["improvement"])
    assert set(learn["improvement"]["proposed"][0]["checks"]) == {"numerosita", "quota", "in_campione", "fuori_campione", "walk_forward", "soglie_vicine"}
    trades = client.get("/api/v1/trades/history").json()
    assert trades["rows"] and {"R", "source", "symbol", "weekday", "conviction", "entry_time", "exit_time", "mae", "mfe"} <= set(trades["rows"][0])
    assert all(r["source"] in ("sim", "paper") for r in trades["rows"])
    health = client.get("/api/v1/health").json()
    assert {"max_data_age_h", "interval_s", "score_confirmed", "score_exceptional"} <= set(health["rules"])
    snap = client.get("/api/v1/snapshot").json()
    assert any(g["value"] is None for g in snap["gates"]) and {"regime", "conviction", "overlay"} <= set(snap["ai"])
    assert client.get("/css/spaces.css").status_code == 200 and client.get("/js/views/evidenza.js").status_code == 200
