"""A pod spenti (scelta di Andrea del 6/11) il conto e' uno solo: il NAV e' quello di IBKR e non ci sono capitali simulati."""
from firm import db, gateway, pods, workflows


def test_pods_off_nav_is_the_account(firm_env):
    db.ex("DELETE FROM settings WHERE key LIKE 'pods.%'")           # torna il default: pod spenti
    pods.ensure_pods()
    assert [p["id"] for p in pods.all_pods()] == ["pod_zero"]
    assert pods.sim_pod_ids() == []
    assert gateway.firm_nav_estimate() == gateway.pod_zero_nav()
    assert "pod_simulati" not in workflows.libro_posizioni()


def test_existing_pods_get_closed_when_switched_off(firm_env):
    pods.ensure_pods()                                               # pod accesi (fixture)
    assert len(pods.all_pods()) == 4
    db.ex("DELETE FROM settings WHERE key LIKE 'pods.%'")
    pods.ensure_pods()
    left = db.q("SELECT id,status,capital_frac FROM pods ORDER BY id")
    assert all(r["status"] == "chiuso" and r["capital_frac"] == 0 for r in left if r["id"] != "pod_zero")
    assert [r for r in left if r["id"] == "pod_zero"][0]["capital_frac"] == 1.0


def test_switching_pods_off_drops_inflated_history(firm_env):
    pods.ensure_pods()                                               # pod accesi (fixture)
    for pod, nav in (("pod_zero", 969000.0), ("trend", 48000.0), ("firm", 1115000.0)):
        db.ex("INSERT INTO nav_marks(day,pod,nav,capital,gross) VALUES('2026-11-05',?,?,1,0)", (pod, nav))
    db.ex("DELETE FROM settings WHERE key LIKE 'pods.%'")
    pods.ensure_pods()
    left = {r["pod"] for r in db.q("SELECT pod FROM nav_marks")}
    assert left == {"pod_zero"}                                      # via il massimo storico gonfiato del 'firm'
    assert gateway.firm_book()["peak"] <= gateway.firm_nav_estimate() * 1.0001 or gateway.firm_book()["peak"] < 1115000.0


def test_building_level_restarts_after_pods_off(firm_env):
    from firm import building
    pods.ensure_pods()
    db.runtime_set("building.level", 5)                              # salito per il capitale simulato dei pod
    db.ex("DELETE FROM settings WHERE key LIKE 'pods.%'")
    pods.ensure_pods()
    assert db.runtime_get("building.level") == 0
    assert building.level()["livello"] <= 1                           # ricalcolato dal conto, senza il capitale simulato
    db.runtime_set("building.level", 3)
    pods.ensure_pods()                                               # una volta sola: non azzera di nuovo
    assert db.runtime_get("building.level") == 3


def test_refresh_defaults_overrides_old_db_value_once(firm_env):
    from firm import db, settings as S
    S.set("models.by_grade_map", {"0": "claude-sonnet-5-5"}, S.AndreaCapability(S.ensure_token())) if False else db.ex(
        "INSERT OR REPLACE INTO settings(key,value,updated_ts,updated_by) VALUES(?,?,?,?)",
        ("budget.daily_eur", db.dumps(0.5), db.now_iso(), "andrea"))
    assert S.get("budget.daily_eur") == 0.5
    assert S.refresh_defaults() and S.get("budget.daily_eur") == S.defaults()["budget"]["daily_eur"]
    assert S.refresh_defaults() == []                                            # una volta sola
