"""Livello Terminale e rifiniture dei tre spazi (Oggi, Rischio, Mercati): controlli sui file statici e sulle funzioni derivate."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "dashboard" / "static"
JS = STATIC / "js"


def _read(rel: str) -> str:
    return (STATIC / rel).read_text(encoding="utf-8")


def test_terminale_e_la_schermata_di_oggi_al_livello_terminale():
    main = _read("js/main.js")
    assert "import * as terminale from './views/terminale.js';" in main
    assert "view: oggi, terminal: terminale" in main                                   # la tabella degli spazi cambia solo qui
    assert "const landing = (route) => (level === 'terminale' && route.tab.terminal" in main and "keyOf(route)" in main


def test_terminale_dieci_riquadri_tastiera_e_sola_lettura():
    t = _read("js/views/terminale.js")
    for key, ident in (("2", "chart"), ("3", "equity"), ("4", "brake"), ("5", "pos"), ("6", "book"), ("7", "strat"), ("8", "attr"), ("9", "orders"), ("0", "alerts")):
        assert f"tp('{key}', '{ident}'" in t, ident
    assert "tp--strip" in t and "dataset: { key: '1' }" in t                           # il decimo: la fascia dei numeri
    for vietato in ("fetch(", "XMLHttpRequest", "method: 'POST'", "sendBeacon", "h('form'", "h('input'", "innerHTML", ".style ="):
        assert vietato not in t, vietato
    for needle in ("e.key === 'Tab' && onPanel", "/^Arrow/.test(e.key)", "e.key === 'j' || e.key === 'k'", "e.key === 'Enter' && onPanel", "function neighbour", "function pick(", "l.link(sym)", "delete document.body.dataset.term"):
        assert needle in t, needle
    # nessun secondo calcolo: le grandezze arrivano da derive.js e dalle stesse funzioni di Oggi
    assert "from '../derive.js'" in t and "ladderData(ctxNow, tb" in t and "totalNav(snap, tb)" in t and "worstCase(snap, tb, ctxNow.quant4)" in t
    assert not re.search(r"-0\.[234]\b|0\.0[48]\b|Math\.sqrt\(365\)", t)                # soglie lette dalla fotografia


def test_terminale_griglia_senza_scorrimento_e_ripieghi():
    css = _read("css/glass.css")
    assert ".tgrid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr));" in css
    assert "body[data-term] .page { height: calc(100dvh - 14px);" in css and "@media (min-width: 1181px) and (min-height: 720px)" in css
    assert ".tlist { flex: 1 1 0; min-height: 0; overflow-y: auto;" in css               # gli elenchi scorrono dentro il riquadro
    assert "@media (max-width: 1180px), (max-height: 719px)" in css and ".tgrid > .tp, .tgrid > .tp--chart, .tgrid > .tp--strip { grid-column: 1 / -1; }" in css
    assert not re.search(r"(?<![\w-])\.term(?![\w-])\s*[{>]", css[css.index("Terminale: la schermata"):])   # .term è il termine del glossario
    assert ".capsule.is-sweep" in css and "grow-y" in css and ".bl-legend" in css and ".gate[data-state=\"none\"]" in css


def test_rifiniture_oggi_rischio_mercati():
    oggi = _read("js/views/oggi.js")
    assert "export function paperStart" in oggi and "label: 'avvio del paper'" in oggi and "cls: 'fund sim'" in oggi
    assert "non ancora misurabile" in oggi and "freshLine(" in oggi and "navChart.setWindow(x[i0], x[n - 1], { animate: rangeMoved })" in oggi
    panels = _read("js/panels.js")
    assert "export function tradeMarkers" in panels and "export const freshLine" in panels and "bl-legend" in panels
    assert "…" not in panels[panels.index("export function brakeLadder"):panels.index("// ---- righello del trade")]     # nessuna ellissi dentro l'SVG della scala
    candles = _read("js/candles.js")
    assert "ATR` : ''}`" in candles and "const GUTTER = Math.round(Math.min(W * 0.4" in candles and "e.key === '0'" in candles
    mercati = _read("js/views/mercati.js")
    assert "{ value: 'trade', label: 'Trade' }" in mercati and "function stepTrade" in mercati
    charts = _read("js/charts.js")
    engine = _read("js/chart-engine.js")
    assert "function tweenWin" in charts and "export function growOnce" in charts and "T.reducedMotion" in charts
    assert "T.morph" in engine and "T.reducedMotion" in engine
    main = _read("js/main.js")
    assert "oldestSource(" in main and "watchedSymbols(" in main and "'Arrestato'" in main


@pytest.mark.skipif(shutil.which("node") is None, reason="serve Node")
def test_fonte_piu_vecchia_e_strumenti_seguiti(tmp_path):
    script = tmp_path / "t.mjs"
    script.write_text(f"""
import {{ oldestSource, watchedSymbols }} from '{(JS / 'derive.js').as_posix()}';
const DAY = 86400000; const now = Date.UTC(2026, 10, 12, 12);
const rules = {{ max_data_age_h: {{ crypto: 36, ibkr: 100 }} }};
const snap = {{ positions: [{{ symbol: 'spy', venue: 'IBKR' }}, {{ symbol: 'ETH', venue: 'KRAKEN' }}, {{ symbol: 'BTC', venue: 'KRAKEN' }}] }};
const tb = {{ open: {{ BTC: {{ symbol: 'BTC' }} }} }};
console.log(JSON.stringify({{
  watched: watchedSymbols(snap, tb),
  fresh: oldestSource([{{ name: 'barre BTC', day: now - 1.2 * DAY, kind: 'crypto' }}, {{ name: 'barre SPY', day: now - 3 * DAY, kind: 'ibkr' }}], now, rules),
  stale: oldestSource([{{ name: 'libro dei trade', day: now - 12 * DAY, kind: 'crypto' }}, {{ name: 'barre BTC', day: now - 4 * DAY, kind: 'crypto' }}, {{ name: 'barre SPY', day: now - 3 * DAY, kind: 'ibkr' }}], now, rules),
  norules: oldestSource([{{ name: 'barre BTC', day: now - 40 * DAY, kind: 'crypto' }}], now, {{}}),
}}));
""", encoding="utf-8")
    out = json.loads(subprocess.run(["node", str(script)], capture_output=True, text=True, check=True).stdout)
    assert out["watched"] == [{"symbol": "BTC", "kind": "crypto"}, {"symbol": "SPY", "kind": "ibkr"}, {"symbol": "ETH", "kind": "crypto"}]
    assert out["fresh"] is None and out["norules"] is None                              # senza regola nessun allarme inventato
    assert out["stale"]["name"] == "libro dei trade" and out["stale"]["count"] == 2
