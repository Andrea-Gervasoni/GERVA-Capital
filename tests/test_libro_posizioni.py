"""Gli agenti del Capo ricevono i fatti (posizioni, libri dei pod, limiti) presi dal codice, senza conto ne' NAV reale."""
import json

from firm import db, workflows


def test_libro_has_positions_and_no_secrets(firm_env):
    db.runtime_set("ibkr.challenge", dict(ok=True, ts="2026-11-05T22:00:00Z", conto="DU****603", nav_eur=969794.26,
                                          posizioni=[dict(simbolo="NVDA", tipo="STK", qty=224.0, costo_medio=206.99)],
                                          eseguiti_oggi=16))
    libro = workflows.libro_posizioni()
    z = libro["pod_zero"]
    assert z["posizioni"] == [dict(simbolo="NVDA", quantita=224.0, costo_medio=206.99)]
    assert z["collegato"] and z["eseguiti_oggi"] == 16
    txt = json.dumps(libro)
    assert "969794" not in txt and "DU" not in txt and "nav_eur" not in txt
    assert "limiti_di_rischio" in libro and "pod_simulati" in libro


def test_libro_without_ibkr_does_not_crash(firm_env):
    libro = workflows.libro_posizioni()
    assert libro["pod_zero"]["posizioni"] == [] and libro["pod_zero"]["collegato"] is False


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
