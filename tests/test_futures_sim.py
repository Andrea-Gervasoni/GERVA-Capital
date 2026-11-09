"""Banco futures simulato: la leva la sceglie l'agente (entro i tetti fisici), liquidazione a ~1/leva, risultati per fascia di leva."""
import json

import pytest

from firm import db, futures_sim as FS, signals as SG

P_LONG = dict(ok=True, moneta="SOL", direzione="long", ingresso=100.0, stop=96.0, obiettivi=[108.0])
P_SHORT = dict(ok=True, moneta="ATOM", direzione="short", ingresso=1.34, stop=1.40, obiettivi=[1.20])


def test_leverage_is_read_from_the_signal_text():
    assert SG.parse_leverage("ATOMUSDT Modalità Margine: Isolato Leva Consigliata: Minima: 3x Massima: 8x Tipo Ordine: Mercato") == dict(leva_min=3.0, leva_max=8.0)
    assert SG.parse_leverage("BTC long leverage 10x entry 67000") == dict(leva_min=10.0, leva_max=10.0)
    assert SG.parse_leverage("BUY SOL entry 150 SL 140 TP 165") == {}                                  # nessuna leva proposta
    assert SG.parse_leverage("Leva 500x per i coraggiosi") == {}                                       # fuori scala: ignorata


def test_liquidation_geometry_and_cap(firm_env):
    assert FS.liq_price(100.0, "long", 10) == pytest.approx(90.5, abs=1e-6)                           # 1/10 dall'ingresso meno lo 0,5% di mantenimento
    assert FS.liq_price(100.0, "short", 10) == pytest.approx(109.5, abs=1e-6)
    assert FS.lev_cap(dict(leva_max=8)) == 8 and FS.lev_cap({}) == 10 and FS.lev_cap(dict(leva_max=80)) == 25   # propone 8 -> 8; niente -> 10; oltre il tetto fisico -> 25
    st = FS.study(dict(P_LONG, leva_min=3, leva_max=25), dict(sigma_giornaliera=0.04))
    row = {r["leva"]: r for r in st["tabella_per_leva"]}
    assert row[10]["stop_prima_della_liquidazione"] is True        # stop al 4%, liquidazione a 9,5%: lo stop arriva prima
    assert row[25]["stop_prima_della_liquidazione"] is False       # con 25x la liquidazione e' al 3,5%: arriva PRIMA dello stop
    assert row[10]["perdita_allo_stop_su_margine"] == 0.4 and row[10]["guadagno_all_obiettivo_su_margine"] == 0.8
    assert "Kelly" in st["principi"] and "non sei obbligato" in st["nota"]


def test_agent_chooses_leverage_and_margin_within_physical_caps(firm_env):
    a = FS.open_position(1, dict(P_LONG, leva_max=10), dict(leva=7, margine_pct=5, motivo_leva="stop stretto e probabilita' alta"))
    assert a["lev"] == 7 and a["margin_usd"] == 5000 and a["notional_usd"] == 35000                    # sceglie lui: non il massimo
    b = FS.open_position(2, dict(P_LONG, leva_max=10), dict(leva=50, margine_pct=90))
    assert b["lev"] == 10 and b["margin_usd"] == 20000                                                 # leva 50 stretta a 10; margine stretto al 20% per segnale
    assert FS.open_position(1, P_LONG, dict(leva=2, margine_pct=2)) is None                            # un segnale = una posizione
    for i in (3, 4):                                                                                   # 5000 + 20000 + 20000 + 20000 = 65000 di margine
        assert FS.open_position(i, P_LONG, dict(leva=3, margine_pct=20))["margin_usd"] == 20000
    e = FS.open_position(5, P_LONG, dict(leva=3, margine_pct=20))
    assert e["margin_usd"] == 15000 and FS.margin_used() == 80000                                      # tetto sul margine totale (80%): l'ultimo si riduce
    assert FS.open_position(6, P_LONG, dict(leva=3, margine_pct=20)) is None                           # conto pieno: non si apre


def _k(hi, lo, close=0.0, t=0):
    return [t, "0", str(hi), str(lo), str(close or lo)]


def test_events_liquidation_before_stop_and_worst_case_in_a_candle():
    liq = FS.liq_price(100.0, "long", 20)                                                              # 95,5: oltre lo stop a 96? no: 95,5 < 96 -> prima lo stop
    assert FS.first_event([_k(101, 99), _k(104, 95.9)], "long", 96.0, 108.0, liq) == ("stop", 96.0, 0)
    liq25 = FS.liq_price(100.0, "long", 25)                                                            # 96,5: sopra lo stop a 96 -> la liquidazione arriva prima
    assert FS.first_event([_k(101, 96.4, t=5)], "long", 96.0, 108.0, liq25)[0] == "liquidazione"
    assert FS.first_event([_k(109, 99, t=7)], "long", 96.0, 108.0, FS.liq_price(100.0, "long", 5)) == ("obiettivo", 108.0, 7)
    assert FS.first_event([_k(109, 95, t=9)], "long", 96.0, 108.0, 80.0)[0] == "stop"                  # obiettivo e stop nella stessa candela: il peggiore
    assert FS.first_event([_k(1.41, 1.30)], "short", 1.40, 1.20, FS.liq_price(1.34, "short", 3))[0] == "stop"


def test_track_closes_with_pnl_on_margin_and_stats_by_leverage(firm_env, monkeypatch):
    FS.open_position(1, dict(P_LONG, leva_max=10), dict(leva=10, margine_pct=5))                       # 5000 di margine, 50000 di posizione
    FS.open_position(2, dict(P_LONG, leva_max=10), dict(leva=2, margine_pct=5))
    FS.open_position(3, dict(P_SHORT, leva_max=5), dict(leva=5, margine_pct=4))
    paths = {"SOL": [_k(108.5, 99, 108, t=1)], "ATOM": [_k(1.42, 1.30, 1.4, t=1)]}                    # SOL arriva all'obiettivo; ATOM tocca lo stop dello short
    monkeypatch.setattr(SG, "_candles", lambda coin, since: paths[coin])
    assert FS.track() == 3
    rows = {r["signal_id"]: r for r in db.q("SELECT * FROM fut_positions")}
    assert rows[1]["esito"] == "obiettivo" and rows[1]["pnl_usd"] == pytest.approx(0.08 * 50000 - 0.001 * 50000, abs=0.01)    # +8% x 10 = +80% sul margine, meno le commissioni
    assert rows[2]["pnl_margin"] == pytest.approx(0.16 - 0.002, abs=1e-3) and rows[3]["esito"] == "stop" and rows[3]["pnl_usd"] < 0
    assert FS.equity() == pytest.approx(100000 + sum(r["pnl_usd"] for r in rows.values()), abs=0.01)
    s = {b["fascia"]: b for b in FS.stats_by_leverage()}
    assert s["7-10x"]["n"] == 1 and s["1-3x"]["n"] == 1 and s["4-6x"]["n"] == 1                       # i risultati tornano agli agenti per fascia di leva


def test_liquidation_loses_exactly_the_margin(firm_env, monkeypatch):
    FS.open_position(1, dict(P_LONG, stop=80.0, leva_max=25), dict(leva=25, margine_pct=10))           # stop a 80 (-20%): la liquidazione a ~96,5 arriva prima
    monkeypatch.setattr(SG, "_candles", lambda coin, since: [_k(100, 95, t=3)])
    FS.track()
    r = db.one("SELECT * FROM fut_positions WHERE signal_id=1")
    assert r["esito"] == "liquidazione" and r["pnl_usd"] == -r["margin_usd"] and r["pnl_margin"] == -1.0
    assert FS.overview()["liquidazioni"] == 1


def test_end_to_end_atom_short_agent_gets_the_study_and_chooses(firm_env, monkeypatch):
    """Il segnale ATOMUSDT (leva 3x-8x, short) arriva all'agente con lo studio sulla leva; lui sceglie, il conto virtuale apre la posizione."""
    from firm import org_seed, registry
    from llm import runtime
    from tests.test_telegram_ai import ATOM, _futures_env
    org_seed.seed(); registry.sync(); _futures_env(monkeypatch)
    seen = {}

    def call(agent, task, **kw):
        if agent == "senior_crypto":
            seen["data"], seen["task"] = kw.get("data"), task
            return dict(ok=True, output=dict(decisione="accetta", probabilita_tp1=0.6, peso_pct=1.0, motivo="ok", rischi=[], invalidazione="x",
                                             leva=6, margine_pct=4, motivo_leva="stop al 4%: con 6x la liquidazione e' a ~16%, resta lontana"))
        if agent == "cro":
            return dict(ok=True, output=dict(veto=False, motivo="ok"))
        return dict(ok=False, motivo="no")
    monkeypatch.setattr(runtime, "call", call)
    sid = SG.create(ATOM, "sala segnali")
    SG.process(sid, execute=True)
    st = seen["data"]["studio_leva"]
    assert st["il_segnale_propone"] == dict(minima=3.0, massima=8.0) and st["leva_massima_ammessa"] == 8 and "non sei obbligato" in seen["task"]
    assert any(r["leva"] == 8 for r in st["tabella_per_leva"]) and not any(r["leva"] == 10 for r in st["tabella_per_leva"])      # il segnale dice 8: oltre non si propone
    pos = db.one("SELECT * FROM fut_positions WHERE signal_id=?", (sid,))
    assert pos["side"] == "short" and pos["lev"] == 6 and pos["margin_usd"] == 4000 and pos["coin"] == "ATOM"                    # ha scelto 6x, non l'8x massimo
    assert "liquidazione" in pos["motivo"]
