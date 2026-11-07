"""L'orologio del portale: corre se tutto e' vivo, si blocca sull'ultimo istante sano e dice cosa manca."""
import datetime as dt

from firm import db, health


def _at(sec):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_clock_runs_when_everything_is_alive_and_freezes_otherwise(firm_env, monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHATS", "Sala")
    db.runtime_set("telegram.alive", dict(ts=_at(20), collegato=True)); db.runtime_set("ibkr.live_ok", _at(5))
    db.runtime_set("heartbeat.alive", _at(300)); db.runtime_set("free.alive", _at(10))
    h = health.status()
    assert h["ok"] and h["bloccato_a"] is None and len(h["parti"]) == 4
    db.runtime_set("telegram.alive", dict(ts=_at(900), collegato=True))                    # Telegram tace da 15 minuti
    h = health.status()
    assert not h["ok"] and h["bloccato_a"][:16] == _at(900)[:16] and [p["nome"] for p in h["parti"] if not p["ok"]] == ["Telegram"]
    db.runtime_set("telegram.alive", dict(ts=_at(5), collegato=False))                     # vivo ma scollegato: conta come fermo
    assert not health.status()["ok"]


def test_without_telegram_configured_it_does_not_count(firm_env, monkeypatch):
    monkeypatch.delenv("TELEGRAM_CHATS", raising=False)
    for k in ("ibkr.live_ok", "heartbeat.alive", "free.alive"):
        db.runtime_set(k, _at(1))
    h = health.status()
    assert h["ok"] and all(p["nome"] != "Telegram" for p in h["parti"])


def test_health_endpoint(firm_env):
    from fastapi.testclient import TestClient
    from portal.app import app
    j = TestClient(app).get("/api/health").json()
    assert "ok" in j and "parti" in j
