"""Gli agenti del Capo ricevono i fatti (posizioni, libri dei pod, limiti) presi dal codice, senza conto ne' NAV reale."""
import json

from firm import db, workflows


def test_libro_has_positions_and_no_secrets(firm_env):
    db.runtime_set("ibkr.challenge", dict(ok=True, ts="2026-11-05T22:00:00Z", conto="DU****603", nav_eur=969794.26,
                                          posizioni=[dict(simbolo="NVDA", tipo="STK", qty=224.0, costo_medio=206.99)],
                                          eseguiti_oggi=16))
    libro = workflows.libro_posizioni()
    z = libro["ibkr"]
    assert z["posizioni"] == [dict(simbolo="NVDA", quantita=224.0, costo_medio=206.99)]
    assert z["collegato"] and z["eseguiti_oggi"] == 16
    txt = json.dumps(libro)
    assert "969794" not in txt and "DU" not in txt and "nav_eur" not in txt
    assert "limiti_di_rischio" in libro and "operazioni" in libro and "alpaca" in libro


def test_libro_without_ibkr_does_not_crash(firm_env):
    libro = workflows.libro_posizioni()
    assert libro["ibkr"]["posizioni"] == [] and libro["ibkr"]["collegato"] is False


def test_real_numbers_only_when_andrea_allows(monkeypatch):
    from llm import runtime
    data = dict(ordine="x", _reale=dict(conto_paper="DU1234567", totale_eur=969794.26))
    monkeypatch.delenv("GERVA_LLM_REAL_NUMBERS", raising=False)
    assert "DU1234567" not in runtime._data_block(data) and "969794" not in runtime._data_block(data)
    monkeypatch.setenv("GERVA_LLM_REAL_NUMBERS", "1")
    blk = runtime._data_block(data)
    assert "DU1234567" in blk and "969794.26" in blk
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-abcdefghijklmnop12345")
    assert "sk-ant-abcdefghijklmnop12345" not in runtime._data_block(dict(ordine="sk-ant-abcdefghijklmnop12345", _reale=data["_reale"]))


def test_libro_tells_who_opened_each_position(firm_env):
    from firm import blotter
    blotter.record("alpaca", "z1", "2026-11-07T08:12:00Z", "BTC", "buy", 0.05, 62000, 0, "USD", "eseguito", "1", dict(kind="modello"))
    blotter.record("alpaca", "z2", "2026-11-07T09:00:00Z", "SOL", "sell", 30, 150, 0, "USD", "eseguito", "2", dict(kind="free", ref=1, agent="pod_trend"), "pod_trend")
    ops = {o["simbolo"]: o for o in workflows.libro_posizioni()["operazioni"]}
    assert ops["BTC"]["deciso_da"] == "modello" and ops["SOL"]["deciso_da"] == "free" and ops["SOL"]["agente"] == "pod_trend"
