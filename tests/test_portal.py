"""M2: portale locale — solo 127.0.0.1, scritture solo con il token di Andrea, nessun ordine dal portale."""
import ast
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(firm_env):
    from firm import org_seed, registry, pods, settings as S
    org_seed.seed(); registry.sync(); pods.ensure_pods()
    from portal.app import app
    return TestClient(app), S.ensure_token()


def test_pages_and_read_endpoints(client):
    c, tok = client
    r = c.get("/")
    assert r.status_code == 200 and tok in r.text and "GERVA" in r.text
    for path in ("/api/state", "/api/office", "/api/org", "/api/pods", "/api/research", "/api/mailbox",
                 "/api/settings", "/api/commands", "/api/agent/cro", "/api/events"):
        assert c.get(path).status_code == 200, path
    st = c.get("/api/state").json()
    assert st["modalita"] == "PAPER" and st["live_bloccato"] is True


def test_foreign_host_is_refused(client):
    c, _ = client
    assert c.get("/api/state", headers={"Host": "evil.example"}).status_code == 403


def test_writes_need_token_and_live_is_impossible(client):
    c, tok = client
    body = {"key": "budget.daily_eur", "value": 0.3}
    assert c.post("/api/settings", json=body).status_code == 403
    assert c.post("/api/settings", json=body, headers={"X-Andrea-Token": "sbagliato"}).status_code == 403
    assert c.post("/api/settings", json=body, headers={"X-Andrea-Token": tok}).status_code == 200
    r = c.post("/api/settings", json={"key": "firm.mode", "value": "live"}, headers={"X-Andrea-Token": tok})
    assert r.status_code == 400
    assert c.post("/api/kill", json={"on": True}).status_code == 403
    assert c.post("/api/kill", json={"on": True}, headers={"X-Andrea-Token": tok}).status_code == 200
    assert c.get("/api/state").json()["kill"] is True
    c.post("/api/kill", json={"on": False}, headers={"X-Andrea-Token": tok})
    assert c.post("/api/command", json={"text": "ciao"}).status_code == 403


def test_portal_code_never_calls_the_gateway_order_functions():
    src = open(os.path.join(os.path.dirname(__file__), "..", "portal", "app.py")).read()
    tree = ast.parse(src)
    calls = {f"{n.func.value.id}.{n.func.attr}" for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)}
    assert not {"gateway.submit_order", "gateway.flush", "gateway.broker"} & calls


def test_v2_endpoints(client):
    c, tok = client
    w = c.get("/api/world").json()
    assert w["edificio"]["livello"] == 0 and any(o["tier"] == "ceo" for o in w["uffici"])
    assert "capo" in w["agenti"]
    people = c.get("/api/people").json()
    assert people and all("rank_grado" in p for p in people)
    assert c.get("/api/meetings").status_code == 200
    r = c.get("/api/report/oggi").json()
    assert "correzioni" in r
    a = c.get("/api/agent/capo").json()
    assert a["ufficio"]["tier"] == "ceo" and "serie" in a
