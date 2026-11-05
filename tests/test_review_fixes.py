"""Regressioni dei difetti trovati dalla squadra di revisione (v3). Ogni test riproduce il caso segnalato."""
import json
import sqlite3

import numpy as np
import pandas as pd
import pytest


def test_bonus_is_paid_once_on_the_same_alpha(firm_env, monkeypatch):
    from firm import economy as E, org_seed, registry, pods
    org_seed.seed(); registry.sync(); pods.ensure_pods()
    monkeypatch.setattr(E, "net_alpha", lambda pid: dict(alpha_netto_eur=700.0, giorni=90))
    first = E.distribute_bonus("trend")["bonus_gc"]
    again = E.distribute_bonus("trend")["bonus_gc"]
    assert first > 0 and again == 0                                  # stesso alpha, nessun secondo bonus
    monkeypatch.setattr(E, "net_alpha", lambda pid: dict(alpha_netto_eur=800.0, giorni=120))
    assert E.distribute_bonus("trend")["bonus_gc"] == pytest.approx(first / 7)   # solo i 100 EUR nuovi


def test_lookahead_catches_one_step_future_leak():
    from quantlab import lookahead
    idx = pd.bdate_range("2020-01-01", periods=400)
    p = pd.DataFrame({"A": np.exp(np.cumsum(np.random.default_rng(1).normal(0, 0.01, 400)))}, index=idx)
    assert not lookahead.truncation_test(lambda x: x.pct_change().shift(-1), p)["ok"]
    assert not lookahead.truncation_test(lambda x: x.rolling(11, center=True).mean(), p)["ok"]
    assert lookahead.truncation_test(lambda x: x.pct_change().rolling(20).mean(), p)["ok"]


def test_promotion_respects_lower_is_better_metrics(firm_env):
    from firm import scorekeeper as SK
    for _ in range(35):
        SK.add_eval("noisy", "affermazioni_non_verificabili", 1.0)    # il peggio possibile
        SK.add_eval("peer", "affermazioni_non_verificabili", 0.5)
    assert not SK.promotion_test("noisy", "redazione", 1, ["peer"])["idoneo"]
    assert SK.promotion_test("peer", "redazione", 1, ["noisy"])["idoneo"]


def test_money_tables_are_append_only(firm_env):
    from firm import db, scorekeeper as SK
    SK.add_eval("a", "brier", 0.1)
    with pytest.raises(sqlite3.DatabaseError):
        db.ex("UPDATE evaluations SET value=0")
    with pytest.raises(sqlite3.DatabaseError):
        db.ex("DELETE FROM evaluations")
    fid = SK.register_forecast("a", "BTC sopra 50k a fine mese", 0.6, "2099-01-01", "prezzo di chiusura", "test")
    with pytest.raises(sqlite3.DatabaseError):
        db.ex("UPDATE forecasts SET canary=1 WHERE id=?", (fid,))
    with pytest.raises(sqlite3.DatabaseError):
        db.ex("UPDATE forecasts SET source='altro' WHERE id=?", (fid,))


def test_audit_detects_deleted_tail(firm_env):
    from firm import audit, db
    for i in range(5):
        audit.log("test", "azione", dict(i=i))
    assert audit.verify()["ok"]
    conn = db.connect()
    conn.execute("DROP TRIGGER audit_log_no_delete")
    conn.execute("DELETE FROM audit_log WHERE seq >= (SELECT MAX(seq) - 1 FROM audit_log)")
    v = audit.verify()
    assert not v["ok"]


def test_once_is_atomic(firm_env):
    from firm import heartbeat
    assert heartbeat._once("k") is True and heartbeat._once("k") is False


def test_min_efficient_notional_uses_the_minimum_commission():
    from quantlab import costs as QC
    assert QC.min_efficient_notional(QC.UCITS_ETF) == pytest.approx(3.0 / (0.005 - 0.0003))
    m = QC.UCITS_ETF
    q = QC.min_efficient_notional(m)
    assert m.cost(q) / q == pytest.approx(0.005, rel=1e-6)          # alla soglia il costo e' esattamente il 0,5%


def test_research_read_cannot_escape(firm_env):
    from llm import tools
    for bad in ("../docs", "/etc", "..", "a/../../x", ""):
        with pytest.raises(PermissionError):
            tools._read_research(bad)


def test_gate_does_not_pass_skipped_checks(firm_env):
    from firm import trials
    import numpy as np
    tid = trials.register("senior_trend", "s9", "trend", {"z": 9}, "Ipotesi di prova per il cancello: nessun controllo omesso.")
    trials.record_result(tid, np.random.default_rng(0).normal(0.002, 0.005, 2520))
    assert not trials.gate(tid)["controlli"]["look_ahead"]["ok"]            # non eseguito = non superato
    strict = trials.gate(tid, lookahead_ok=True, strict=True)["controlli"]
    assert not strict["pbo"]["ok"] and not strict["sharpe_costi_doppi"]["ok"]


def _portal(monkeypatch, firm_env, pw="una-password-lunga"):
    from portal import app as A
    monkeypatch.setattr(A, "PASSWORD_HASH", A.hash_password(pw))
    from fastapi.testclient import TestClient
    return A, TestClient(A.app)


def test_portal_rejects_foreign_origin_on_post_and_ws(monkeypatch, firm_env):
    from starlette.websockets import WebSocketDisconnect
    A, c = _portal(monkeypatch, firm_env)
    r = c.post("/login", data={"password": "una-password-lunga"}, headers={"Origin": "https://evil.example"},
               follow_redirects=False)
    assert r.status_code == 403
    r = c.post("/login", data={"password": "una-password-lunga"}, headers={"Origin": "http://127.0.0.1:8765"},
               follow_redirects=False)
    assert r.status_code == 303
    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws", headers={"Origin": "https://evil.example"}) as ws:
            ws.receive_text()


def test_portal_exempts_only_exact_static_paths_and_logs_out(monkeypatch, firm_env):
    A, c = _portal(monkeypatch, firm_env)
    assert c.get("/static/fonts/../ui.js", follow_redirects=False).status_code in (303, 404)
    assert c.get("/static/fonts/VT323.woff2").status_code == 200
    r = c.get("/logout", follow_redirects=False)
    assert r.status_code == 303 and "gerva_session=" in r.headers.get("set-cookie", "")


def test_parallel_wrong_passwords_hit_the_rate_limit(monkeypatch, firm_env):
    import asyncio
    import httpx
    A, _ = _portal(monkeypatch, firm_env)
    A._attempts.clear()
    real_sleep = asyncio.sleep
    monkeypatch.setattr(A.asyncio, "sleep", lambda s: real_sleep(0))

    async def go():
        tr = httpx.ASGITransport(app=A.app, client=("127.0.0.1", 5555))
        async with httpx.AsyncClient(transport=tr, base_url="http://127.0.0.1:8765") as cl:
            rs = await asyncio.gather(*[cl.post("/login", data={"password": f"x{i}"}) for i in range(12)])
            return [r.status_code for r in rs]
    codes = asyncio.run(go())
    assert codes.count(401) <= 5 and codes.count(429) >= 7


def test_settings_reject_wrong_types(firm_env):
    from firm import settings as S
    cap = S.AndreaCapability(S.ensure_token())
    with pytest.raises(ValueError):
        S.set("budget.daily_eur", -5, cap)
    with pytest.raises(TypeError):
        S.set("budget.daily_eur", "0.6", cap)
    S.set("budget.daily_eur", 0.8, cap)
    assert S.get("budget.daily_eur") == 0.8


def test_password_hash_survives_compose_interpolation():
    """Il formato non contiene '$' (Compose li interpola negli env_file) e il vecchio formato resta valido."""
    from portal.app import hash_password, check_password
    h = hash_password("una-frase-lunga-e-sicura")
    assert "$" not in h and check_password("una-frase-lunga-e-sicura", h) and not check_password("altra", h)
    assert check_password("una-frase-lunga-e-sicura", h.replace(":", "$"))


def test_band_rebalancing_never_creates_leverage():
    """Banda di non intervento con obiettivo al 100%: i pesi fermi cresciuti per deriva non devono sommarsi a quelli
    nuovi oltre il capitale (sarebbe comprare senza liquidita')."""
    from quantlab import backtest as BT
    rng = np.random.default_rng(5)
    idx = pd.bdate_range("2020-01-01", periods=500)
    close = pd.DataFrame(np.exp(np.cumsum(rng.normal(0, 0.02, (500, 4)), axis=0)) * 100, index=idx, columns=list("ABCD"))
    W = pd.DataFrame(rng.dirichlet(np.ones(4), 500), index=idx, columns=list("ABCD"))   # ogni giorno somma 1
    res = BT.run(W, close, band=0.05)
    assert res.daily["gross"].max() <= 1 + 1e-9
    assert res.weights.sum(axis=1).max() <= 1 + 1e-9


def test_capital_is_read_from_ibkr_once_and_jumps_are_flagged(firm_env, monkeypatch):
    """Conto paper da ~984.000 EUR: il capitale iniziale e' la prima lettura di IBKR, mai una cifra scritta a mano."""
    import types
    from firm import gateway, ibkr, db, org_seed, registry, pods
    org_seed.seed(); registry.sync(); pods.ensure_pods()
    monkeypatch.setenv("IBKR_CHALLENGE_ACCOUNT", "DU999999")
    assert gateway.capital_source()["fonte"] != "IBKR"                       # prima del collegamento: dichiarato

    class IB:
        def __init__(self, nav): self.nav = nav
        def connect(self, *a, **k): pass
        def disconnect(self): pass
        def managedAccounts(self): return ["DU999999"]
        def accountValues(self, a): return [types.SimpleNamespace(tag="NetLiquidation", currency="EUR", value=str(self.nav))]
        def positions(self, a=""): return []
        def fills(self): return []
    ibkr.observe_challenge(factory=lambda: IB(984_000.0))
    assert gateway.start_nav() == 984_000.0 and gateway.capital_source()["fonte"] == "IBKR"
    assert abs(gateway.firm_book()["pnl"]) < 50_000                           # niente guadagno fantasma
    ibkr.observe_challenge(factory=lambda: IB(990_000.0))
    assert gateway.start_nav() == 984_000.0                                   # scritto una volta sola
    db.ex("UPDATE nav_marks SET day='2026-01-01' WHERE pod='pod_zero'")
    ibkr.observe_challenge(factory=lambda: IB(1_500_000.0))                  # balzo: versamento o reset?
    assert any("versamento" in e["payload"] for e in db.q("SELECT payload FROM events WHERE kind='risk.alert'"))
