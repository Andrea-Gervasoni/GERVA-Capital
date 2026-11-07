"""La plancia: operazioni ricostruite dalle esecuzioni (costo medio), conti sommati, storia della decisione, lezioni."""
import datetime as dt
import json
import types

import pytest

from firm import blotter as B, crypto_venue as V, db, lessons as L, org_seed, registry


def _fill(venue, sym, side, qty, px, minute, origine=None, cur="USD", agent=None):
    ts = (dt.datetime(2026, 11, 9, 15, 30, tzinfo=dt.timezone.utc) + dt.timedelta(minutes=minute)).strftime("%Y-%m-%dT%H:%M:%SZ")
    B.record(venue, f"{venue}:{sym}:{minute}:{side}", ts, sym, side, qty, px, 0.0, cur, "eseguito", str(minute), origine or dict(kind="modello"), agent)


def test_average_cost_cycles_long_short_open(firm_env):
    _fill("ibkr", "AAA", "buy", 100, 10, 0); _fill("ibkr", "AAA", "buy", 100, 12, 1)          # costo medio 11
    _fill("ibkr", "AAA", "sell", 50, 13, 2); _fill("ibkr", "AAA", "sell", 150, 10, 3)          # +100 poi -150: chiusa a -50
    _fill("alpaca", "BTC", "sell", 10, 100, 4); _fill("alpaca", "BTC", "buy", 10, 90, 5)       # short chiuso a +100
    _fill("ibkr", "BBB", "buy", 10, 50, 6)                                                    # ancora aperta
    db.runtime_set("ibkr.portfolio", dict(posizioni=[dict(simbolo="BBB", px=55.0)]))
    db.runtime_set("fx.usd_eur", 0.9)
    t = {(x["simbolo"]): x for x in B.trades()}
    a, b, c = t["AAA"], t["BTC"], t["BBB"]
    assert not a["aperta"] and a["lato"] == "long" and a["ingresso"] == 11.0 and abs(a["uscita"] - 10.75) < 1e-9 and a["realizzato"] == -50.0 and a["realizzato_eur"] == -45.0
    assert b["lato"] == "short" and b["realizzato"] == 100.0 and not b["aperta"]
    assert c["aperta"] and c["non_realizzato"] == 50.0 and c["attuale"] == 55.0 and c["uscita"] is None
    ov = B.overview()
    assert ov["riepilogo"]["aperte"] == 1 and ov["riepilogo"]["chiuse"] == 2 and ov["riepilogo"]["vincenti"] == 1 and ov["riepilogo"]["perdenti"] == 1
    assert len(B.trades(venue="alpaca")) == 1 and len(B.trades(stato="aperta")) == 1


def test_ingest_ibkr_dedupes_and_attributes(firm_env):
    org_seed.seed(); registry.sync()
    db.ex("INSERT INTO ideas(ts,author,holder,kind,title,tesi,evidenze,azione,p_success,status,history) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
          (db.now_iso(), "senior_crypto", "capo", "posizione", "t", "tesi", "[]", json.dumps(dict(simbolo="XOM", peso_pct=2)), 0.6, "in_corso", "[]"))
    mk = lambda eid, side: types.SimpleNamespace(
        execution=types.SimpleNamespace(execId=eid, time=dt.datetime(2026, 11, 9, 15, 31, tzinfo=dt.timezone.utc), side=side, shares=10, price=100.0, orderId=7),
        contract=types.SimpleNamespace(localSymbol="XOM", symbol="XOM", currency="USD"), commissionReport=types.SimpleNamespace(commission=1.0))
    assert B.ingest_ibkr([mk("e1", "BOT"), mk("e2", "SLD")]) == 2 and B.ingest_ibkr([mk("e1", "BOT")]) == 0
    row = db.one("SELECT * FROM fills_all WHERE ext_id='e1'")
    assert json.loads(row["origine"])["kind"] == "idea" and row["agent"] == "senior_crypto" and row["fee"] == 1.0


def test_alpaca_orders_get_their_real_fill_and_totals_sum_both_accounts(firm_env, monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_KEY", "k" * 12); monkeypatch.setenv("ALPACA_PAPER_SECRET", "s" * 12)
    state = dict(filled=False)

    def req(method, path, body=None, timeout=15):
        if path == "/v2/account":
            return dict(equity="101000", cash="50000", last_equity="100000")
        if path == "/v2/positions":
            return [dict(symbol="BTCUSD", asset_class="crypto", qty="0.1", current_price="60000", avg_entry_price="59000", market_value="6000", unrealized_pl="100")]
        if path.startswith("/v2/orders/"):
            return dict(status="filled", filled_qty="0.1", filled_avg_price="59000", filled_at="2026-11-09T16:00:00Z")
        raise AssertionError(path)
    monkeypatch.setattr(V, "_req", req)
    B.record_alpaca_order("abc", "BTC", "buy", 5900, dict(kind="modello"))
    assert B.trades() == []                                                    # ancora pendente: non e' un'operazione
    assert B.sync_alpaca() == 1
    t = B.trades()[0]
    assert t["aperta"] and t["ingresso"] == 59000.0 and t["attuale"] == 60000.0 and t["non_realizzato"] == 100.0
    db.runtime_set("ibkr.live", dict(nav=970000.0)); db.runtime_set("ibkr.start_nav", dict(nav=969794.26, giorno="2026-11-06")); db.runtime_set("fx.usd_eur", 0.9)
    tot = B.totals()
    assert tot["alpaca"]["nav_eur"] == 90900.0 and tot["totale"]["nav_eur"] == 970000.0 + 90900.0 and tot["alpaca"]["pnl_eur"] == 900.0


def test_story_follows_the_idea_chain_and_lessons_are_saved(firm_env, monkeypatch):
    org_seed.seed(); registry.sync()
    hist = [dict(ts="t", chi="senior_crypto", cosa="presentata", p=0.6),
            dict(ts="t", chi="head_research", cosa="portata su", motivo="parametri e grafici controllati", miglioramenti="stop piu' largo", p=0.58)]
    iid = db.ex("INSERT INTO ideas(ts,author,holder,kind,title,tesi,evidenze,azione,p_success,status,history) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (db.now_iso(), "senior_crypto", "capo", "posizione", "t", "momentum su AAA", json.dumps(["r3m alto"]), json.dumps(dict(simbolo="AAA", peso_pct=2)), 0.6, "in_corso", json.dumps(hist)))
    _fill("ibkr", "AAA", "buy", 10, 100, 0, dict(kind="idea", ref=iid, agent="senior_crypto"), agent="senior_crypto")
    _fill("ibkr", "AAA", "sell", 10, 90, 30, dict(kind="idea", ref=iid, agent="senior_crypto"), agent="senior_crypto")
    t = B.trades()[0]
    st = B.story(t["chiave"])
    assert st["ok"] and [p["chi"]["id"] for p in st["passi"]][:2] == ["senior_crypto", "head_research"]
    assert "momentum su AAA" in st["passi"][0]["testo"] and "controllati" in st["passi"][1]["testo"] and st["passi"][1]["evidenze"] == ["stop piu' largo"]
    # lezioni
    import llm.runtime as rt
    monkeypatch.setattr(rt, "call", lambda agent, task, data=None, schema=None, purpose="", **k: dict(ok=True, output=dict(lezioni=[dict(
        chiave=data["operazioni"][0]["chiave"], giudizio="errore", cosa_e_successo="stop colpito", lezione="non comprare dopo +12% in un mese", regola_per_il_futuro="evitare r1m>10%")])))
    saved = []
    monkeypatch.setattr(registry, "add_lesson", lambda a, l, *x, **k: saved.append((a, l)))
    monkeypatch.setattr(L, "pending", lambda days=3: B.trades(stato="chiusa"))
    r = L.daily()
    assert r["lezioni"] == 1 and saved and saved[0][0] == "senior_crypto"
    assert B.story(t["chiave"])["lezione"]["giudizio"] == "errore" and L.recent(3)[0]["regola"] == "evitare r1m>10%"


def test_api_blotter_and_state(firm_env):
    from fastapi.testclient import TestClient
    org_seed.seed(); registry.sync()
    _fill("ibkr", "AAA", "buy", 10, 100, 0)
    from portal.app import app
    c = TestClient(app)
    j = c.get("/api/blotter").json()
    assert j["operazioni"] and "totali" in j and c.get("/api/blotter?venue=alpaca").json()["operazioni"] == []
    assert c.get("/api/blotter?venue=zzz").status_code == 400
    assert c.get("/api/blotter/story", params=dict(key=j["operazioni"][0]["chiave"])).json()["ok"]
    assert "portafogli" in c.get("/api/state").json()


def test_alpaca_history_is_backfilled_once(firm_env, monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_KEY", "k" * 12); monkeypatch.setenv("ALPACA_PAPER_SECRET", "s" * 12)
    calls = []

    def req(method, path, body=None, timeout=15):
        if path == "/v2/account":
            return dict(equity="99862", cash="72000", last_equity="100000")
        if path == "/v2/positions":
            return []
        if path.startswith("/v2/orders?"):
            calls.append(path)
            return [dict(id="a1", symbol="BTC/USD", side="buy", status="filled", filled_qty="0.05", filled_avg_price="62000", filled_at="2026-11-07T08:12:00Z"),
                    dict(id="a2", symbol="AAPL", side="buy", status="canceled")]
        raise AssertionError(path)
    monkeypatch.setattr(V, "_req", req)
    B.sync_alpaca(); B.sync_alpaca()
    assert len(calls) == 1 and len(B.trades()) == 1 and B.trades()[0]["simbolo"] == "BTC" and B.trades()[0]["origine"]["kind"] == "modello"


def test_conversations_and_techniques_endpoints(firm_env):
    from fastapi.testclient import TestClient
    org_seed.seed(); registry.sync()
    db.ex("INSERT INTO ideas(ts,author,holder,kind,title,tesi,evidenze,azione,p_success,status,history) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
          (db.now_iso(), "senior_crypto", "capo", "posizione", "t", "tesi vera", "[]", json.dumps(dict(simbolo="V", peso_pct=2)), 0.6, "al_comitato",
           json.dumps([dict(ts="t", chi="head_research", cosa="portata su", motivo="controllato RSI")])))
    from portal.app import app
    c = TestClient(app)
    conv = c.get("/api/conversations").json()
    assert conv and conv[0]["tipo"] == "idea" and [m["chi"] for m in conv[0]["messaggi"]] == ["senior_crypto", "head_research"]
    assert c.get("/api/conversations?agent=head_research").json() and c.get("/api/conversations?agent=nessuno").json() == []
    tech = c.get("/api/techniques").json()
    assert any(t["stato"] == "adottata" for t in tech) and any(t["tipo"] == "strategia dai paper" for t in tech)
