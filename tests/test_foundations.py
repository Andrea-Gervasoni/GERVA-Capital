"""M1: audit con catena di hash, append-only, impostazioni, filtro dei segreti, registro agenti."""
import sqlite3

import pytest


def test_hash_chain_verifies_and_detects_tampering(firm_env):
    from firm import audit, db
    for i in range(20):
        audit.log("tester", "azione", {"i": i})
    v = audit.verify()
    assert v["ok"] and v["n"] == 20
    # il DB rifiuta modifiche e cancellazioni
    with pytest.raises(sqlite3.IntegrityError):
        db.ex("UPDATE audit_log SET payload='{}' WHERE seq=5")
    with pytest.raises(sqlite3.IntegrityError):
        db.ex("DELETE FROM audit_log WHERE seq=5")
    # un attaccante che toglie i trigger e modifica una riga viene scoperto dalla catena
    db.connect().execute("DROP TRIGGER audit_log_no_update")
    db.ex("UPDATE audit_log SET payload='{\"i\": 999}' WHERE seq=7")
    v = audit.verify()
    assert not v["ok"] and v["prima_rottura"] == 7


def test_events_append_only_and_audited(firm_env):
    from firm import events, db, audit
    ev = events.publish("test.kind", "tester", {"x": 1})
    assert events.since(0)[0]["id"] == ev["id"]
    with pytest.raises(sqlite3.IntegrityError):
        db.ex("DELETE FROM events")
    assert audit.verify()["n"] == 1


def test_secrets_never_reach_the_log(firm_env, monkeypatch):
    from firm import audit, db
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-SEGRETISSIMA-1234567890")
    audit.log("tester", "x", {"msg": "chiave sk-ant-api03-SEGRETISSIMA-1234567890 conto DU1234567",
                              "password": "hunter2", "nested": [{"api_key": "abc"}]})
    row = db.one("SELECT payload FROM audit_log")["payload"]
    assert "SEGRETISSIMA" not in row and "DU1234567" not in row and "hunter2" not in row and "abc" not in row


def test_only_andrea_changes_settings(firm_env):
    from firm import settings as S
    token = S.ensure_token()
    with pytest.raises(S.SettingsPermissionError):
        S.AndreaCapability("token-sbagliato")
    with pytest.raises(S.SettingsPermissionError):
        S.set("budget.daily_eur", 99, cap=object())
    cap = S.AndreaCapability(token)
    S.set("budget.daily_eur", 0.4, cap)
    assert S.get("budget.daily_eur") == 0.4
    with pytest.raises(KeyError):
        S.set("non.esiste", 1, cap)
    S.set_risk_limit("pod.dd_close", 0.06, cap)
    assert S.risk_limits()["pod"]["dd_close"] == 0.06
    with pytest.raises(S.SettingsPermissionError):
        S.set_risk_limit("pod.dd_close", 0.5, cap=None)


def test_registry_sync_and_org_tree(firm_env):
    from firm import registry, org_seed
    org_seed.seed()
    n = registry.sync()
    assert n >= 20
    tree = registry.org_tree()
    assert tree["id"] == "capo"
    ids = {c["id"] for c in tree["children"]}
    assert {"cro", "head_research", "head_intel"} <= ids
    llm = [a for a in registry.all_agents() if a["kind"] == "llm"]
    assert 8 <= len(llm) <= 16           # 5/11/2026: Andrea ha chiesto il desk crypto e il comitato di lungo periodo
    assert any(a["status"] == "posizione_aperta" for a in registry.all_agents())
    assert registry.model_for(registry.get("news_analyst")) == "claude-sonnet-5-5"   # 6/11: Sonnet a tutti i gradi
    assert registry.model_for(registry.get("capo"), "committee") == "claude-opus-5-5"


def test_mailbox_only_big_requests(firm_env):
    from firm import mailbox, settings as S
    with pytest.raises(ValueError):
        mailbox.big_request(7, "Pranzo", "x", ["a"], "a", "b")
    with pytest.raises(ValueError):
        mailbox.big_request(2, "Allentare il DD", "", ["a"], "a", "b")
    r = mailbox.big_request(2, "Allentare il DD dei pod", "perche'", ["si", "no"], "no", "resta 7,5%", "k1")
    assert mailbox.big_request(2, "dup", "x", ["a"], "a", "b", "k1") is None
    with pytest.raises(S.SettingsPermissionError):
        mailbox.decide(r["id"], "si", cap=None)
    mailbox.decide(r["id"], "__rimanda__", S.AndreaCapability(S.ensure_token()))
    assert mailbox.items()[0]["status"] == "rimandata"
