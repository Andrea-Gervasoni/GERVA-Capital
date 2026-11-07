"""Sede crypto Alpaca (paper): piano degli ordini, sicurezza, comportamento senza chiavi o con il conto che non risponde."""
import pytest

from firm import crypto_venue as V
from firm import db, settings as S


def _cap():
    return S.AndreaCapability(S.ensure_token())


def test_plan_sells_first_skips_noise_and_unsupported(firm_env):
    have = {"BTC": 20_000.0, "ETH": 5_000.0, "DOGE": 0.0}
    tgt = {"BTC": 0.10, "SOL": 0.05, "XYZ": 0.02}
    orders, skipped = V.plan(100_000.0, have, tgt, {"BTC", "ETH", "SOL", "DOGE"})
    by = {o["coin"]: o for o in orders}
    assert by["BTC"]["side"] == "sell" and by["BTC"]["usd"] == 10_000.0
    assert by["ETH"]["side"] == "sell" and by["ETH"]["chiudi"]            # fuori dall'obiettivo: si chiude
    assert by["SOL"]["side"] == "buy" and by["SOL"]["usd"] == 5_000.0
    assert orders[0]["side"] == "sell" and "XYZ: non supportata da Alpaca" in skipped
    near, _ = V.plan(100_000.0, {"BTC": 10_200.0}, {"BTC": 0.10}, {"BTC"})
    assert near == []                                                      # dentro la banda dello 0,5%: niente rumore


def test_not_configured_does_nothing(firm_env, monkeypatch):
    monkeypatch.delenv("ALPACA_PAPER_KEY", raising=False)
    assert not V.configured() and not V.rebalance()["ok"]
    assert V.accepting() is False


def test_only_paper_host(firm_env, monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_KEY", "k" * 12); monkeypatch.setenv("ALPACA_PAPER_SECRET", "s" * 12)
    monkeypatch.setenv("ALPACA_BASE_URL", "https://api.alpaca.markets")
    with pytest.raises(RuntimeError):
        V._req("GET", "/v2/account")


def test_rebalance_sends_orders_and_fails_closed(firm_env, monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_KEY", "k" * 12); monkeypatch.setenv("ALPACA_PAPER_SECRET", "s" * 12)
    S.set("crypto.venue", "alpaca", _cap())
    S.set("crypto.venue_mirror_model", False, _cap())
    db.runtime_set("desk.overlay", dict(crypto_targets={"BTC": 0.03}))
    calls = []

    def fake(method, path, body=None, timeout=15):
        calls.append((method, path, body))
        if path == "/v2/account":
            return dict(equity="100000", cash="100000")
        if path == "/v2/positions":
            return []
        if path.startswith("/v2/assets"):
            return [dict(symbol="BTC/USD", tradable=True), dict(symbol="ETH/USD", tradable=True)]
        return dict(id="abc")
    monkeypatch.setattr(V, "_req", fake)
    assert V.accepting() and V.configured()
    r = V.rebalance()
    assert r["ok"] and r["ordini"][0]["coin"] == "BTC" and r["ordini"][0]["usd"] == 3000.0
    post = [c for c in calls if c[0] == "POST"][0]
    assert post[2]["symbol"] == "BTC/USD" and post[2]["notional"] == "3000.00" and post[2]["time_in_force"] == "gtc"

    def boom(*a, **k):
        raise RuntimeError("rete giu'")
    monkeypatch.setattr(V, "_req", boom)
    r2 = V.rebalance()
    assert not r2["ok"] and "non raggiungibile" in r2["nota"]               # fail-closed


def test_save_keys_paper_only_and_private(tmp_path):
    import os, stat
    env = tmp_path / ".env"
    env.write_text("ANTHROPIC_API_KEY=abc\nALPACA_PAPER_KEY=old\n")
    V.save_keys("PK" + "A1" * 10, "s" * 30, str(env))
    txt = env.read_text()
    assert "ANTHROPIC_API_KEY=abc" in txt and txt.count("ALPACA_PAPER_KEY=") == 1 and "old" not in txt
    assert stat.S_IMODE(os.stat(env).st_mode) == 0o600
    with pytest.raises(ValueError):
        V.save_keys("AK" + "A1" * 10, "s" * 30, str(env))                 # chiave del conto reale: rifiutata
    with pytest.raises(ValueError):
        V.save_keys("PK" + "A1" * 10, "corta", str(env))


def test_rebalance_does_not_sell_what_the_free_desk_bought(firm_env, monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_KEY", "k" * 12); monkeypatch.setenv("ALPACA_PAPER_SECRET", "s" * 12)
    S.set("crypto.venue", "alpaca", _cap()); S.set("crypto.venue_mirror_model", False, _cap())
    db.runtime_set("desk.overlay", dict(crypto_targets={}))
    db.ex("INSERT INTO free_trades(ts,agent,symbol,side,notional,status,qty,entry_px) VALUES(?,?,?,?,?,?,?,?)",
          (db.now_iso(), "pod_crypto", "SOL", "buy", 5000, "aperta", 33.3333, 150.0))
    posted = []

    def fake(method, path, body=None, timeout=15):
        if path == "/v2/account":
            return dict(equity="100000", cash="95000")
        if path == "/v2/positions":
            return [dict(symbol="SOLUSD", asset_class="crypto", market_value="5000")]
        if path.startswith("/v2/assets"):
            return [dict(symbol="SOL/USD", tradable=True)]
        posted.append((method, path))
        return dict(id="x")
    monkeypatch.setattr(V, "_req", fake)
    r = V.rebalance()
    assert r["ok"] and r["ordini"] == [] and posted == []                  # SOL e' del banco libero: nessuna vendita
