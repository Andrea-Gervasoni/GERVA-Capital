"""A pod spenti (scelta di Andrea del 6/11) il conto e' uno solo: il NAV e' quello di IBKR e non ci sono capitali simulati."""
from firm import db, gateway, pods, workflows


def test_pods_off_nav_is_the_account(firm_env):
    db.ex("DELETE FROM settings WHERE key LIKE 'pods.%'")           # torna il default: pod spenti
    pods.ensure_pods()
    assert [p["id"] for p in pods.all_pods()] == ["pod_zero"]
    assert pods.sim_pod_ids() == []
    assert gateway.firm_nav_estimate() == gateway.pod_zero_nav()
    assert workflows.libro_posizioni()["pod_simulati"] == []


def test_existing_pods_get_closed_when_switched_off(firm_env):
    pods.ensure_pods()                                               # pod accesi (fixture)
    assert len(pods.all_pods()) == 4
    db.ex("DELETE FROM settings WHERE key LIKE 'pods.%'")
    pods.ensure_pods()
    left = db.q("SELECT id,status,capital_frac FROM pods ORDER BY id")
    assert all(r["status"] == "chiuso" and r["capital_frac"] == 0 for r in left if r["id"] != "pod_zero")
    assert [r for r in left if r["id"] == "pod_zero"][0]["capital_frac"] == 1.0
