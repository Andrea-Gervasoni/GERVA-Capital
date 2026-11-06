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
