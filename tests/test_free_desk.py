"""Banco libero: nessuna regola all'inizio; le regole di casa nascono da un voto; il codice chiude e misura."""
import datetime as dt

import pytest

from firm import crypto_venue as V, db, free_desk as FD, ideas as ID, org_seed, registry, settings as S


class FakeBroker:
    def __init__(self, equity=100000.0, last_equity=100000.0):
        self.equity, self.last_equity, self.orders, self.px = equity, last_equity, [], {}

    def req(self, method, path, body=None, timeout=15):
        if path == "/v2/account":
            return dict(equity=str(self.equity), last_equity=str(self.last_equity), buying_power=str(self.equity * 4), cash=str(self.equity))
        if path == "/v2/positions":
            return []
        if method == "POST" and path == "/v2/orders":
            self.orders.append(body)
            return dict(id=f"o{len(self.orders)}")
        if method == "GET" and path.startswith("/v2/orders/"):
            i = int(path.rsplit("o", 1)[1]) - 1
            b = self.orders[i]
            px = self.px.get(b["symbol"].split("/")[0], 100.0)
            return dict(status="filled", filled_avg_price=str(px), filled_qty=str(float(b.get("notional", 1000)) / px if "notional" in b else float(b["qty"])))
        raise AssertionError(path)


@pytest.fixture()
def broker(firm_env, monkeypatch):
    org_seed.seed(); registry.sync()
    monkeypatch.setenv("ALPACA_PAPER_KEY", "k" * 12); monkeypatch.setenv("ALPACA_PAPER_SECRET", "s" * 12)
    b = FakeBroker()
    monkeypatch.setattr(V, "_req", b.req)
    monkeypatch.setattr(V, "last_price", lambda sym: b.px.get(sym, 100.0))
    return b


def _trade(sym="AAPL", usd=1000, hold=2, **k):
    return dict(simbolo=sym, lato="buy", importo_usd=usd, tipo_ordine="market", prezzo_limite=0, stop_pct=0.5, take_pct=1.0, tieni_minuti=hold,
                motivo="prova", probabilita=0.55, **k)


def test_no_rules_at_start_ten_trades_go_through(broker):
    assert FD.active_rules() == {}
    st = FD.state()
    for i in range(10):
        assert FD.execute("senior_crypto", _trade("AAPL" if i % 2 else "BTC", 5000), st)["ok"]               # 10 trade, 50.000 $, nessun limite del codice
    assert len(broker.orders) == 10
    crypto = [o for o in broker.orders if "/" in o["symbol"]][0]
    stock = [o for o in broker.orders if "/" not in o["symbol"]][0]
    assert crypto["time_in_force"] == "gtc" and crypto["symbol"] == "BTC/USD" and stock["time_in_force"] == "day" and stock["notional"] == "5000.00"


def test_monitor_closes_by_time_stop_and_pays(broker):
    st = FD.state()
    FD.execute("senior_crypto", _trade("AAPL", 10000, hold=2), st)
    FD.monitor()                                                           # riempito: diventa aperta, non ancora da chiudere
    assert db.one("SELECT status FROM free_trades")["status"] == "aperta"
    broker.px["AAPL"] = 100.4                                              # +0,4%: dentro stop e obiettivo
    assert FD.monitor() == []
    later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=3)
    out = FD.monitor(now=later)
    assert out and out[0]["motivo"] == "tempo"
    row = db.one("SELECT * FROM free_trades")
    assert row["status"] == "chiusa" and abs(row["pnl"] - 40.0) < 1e-6    # 10.000 $ * 0,4%
    assert db.one("SELECT 1 FROM gc_ledger WHERE agent_id='senior_crypto' AND kind='differito' AND amount>0")   # il guadagno e' dell'agente


def test_stop_loss_closes_and_penalises(broker):
    FD.execute("senior_crypto", _trade("AAPL", 10000, hold=0), FD.state())
    FD.monitor()
    broker.px["AAPL"] = 99.0                                               # -1% con stop 0,5%
    out = FD.monitor()
    assert out[0]["motivo"] == "stop" and db.one("SELECT pnl FROM free_trades")["pnl"] < 0
    assert db.one("SELECT 1 FROM gc_ledger WHERE agent_id='senior_crypto' AND kind='penale'")


def test_house_rules_enforced_and_revocable(broker):
    st = FD.state()
    assert FD.set_house_rule("max_trades_per_hour", 2, "comitato#1")["ok"]
    assert FD.execute("a1", _trade(), st)["ok"] and FD.execute("a1", _trade(), st)["ok"]
    x = FD.execute("a1", _trade(), st)
    assert not x["ok"] and "massimo 2 trade all'ora" in x["motivo"]
    assert FD.execute("a2", _trade(), st)["ok"]                            # il limite e' per agente
    FD.set_house_rule("max_leverage", 0.5, "comitato#2")
    assert not FD.execute("a3", _trade(usd=80000), st)["ok"]               # 80% del conto con leva massima 0,5x
    FD.set_house_rule("max_trades_per_hour", 0, "comitato#3")              # 0 = revoca
    assert "max_trades_per_hour" not in FD.active_rules() and FD.active_rules() == {"max_leverage": 0.5}
    assert not FD.check_house_rule("max_leverage", -3)[0] and not FD.check_house_rule("firm.mode", 1)[0]


def test_house_rule_is_born_from_a_vote(broker, monkeypatch):
    import llm.runtime as rt
    idea = dict(ho_un_idea=True, tipo="regola_casa", titolo="Massimo 5 trade all'ora", tesi="troppo rumore e costi", evidenze=["pnl"], simbolo="", peso_pct=0,
                orizzonte_giorni=0, stop_pct=0, obiettivo_pct=0, chiave="max_trades_per_hour", valore=5, probabilita_successo=0.6)

    def call(agent, task, data=None, schema=None, purpose="", **k):
        if purpose == "idea":
            return dict(ok=True, output=idea)
        if purpose == "idea-revisione":
            return dict(ok=True, output=dict(decisione="porta_su", motivo="ok", miglioramenti="", probabilita_successo=0.6))
        if purpose.endswith(":replica"):
            return dict(ok=True, output=dict(replica="si", posizione_finale="approva", fiducia=0.7))
        return dict(ok=True, output=dict(posizione="approva", argomento="a", evidenza=["x"], fiducia=0.7, cambierei_idea_se="b"))
    monkeypatch.setattr(rt, "call", call)
    assert FD.active_rules() == {}
    g = ID.generate("senior_crypto", rows=[]); ID.advance(); out = ID.committee()
    assert out and out[0]["stato"] == "applicata" and FD.active_rules() == {"max_trades_per_hour": 5.0}           # nata da un voto, non da me
    assert ID.generate("senior_crypto", rows=[], note="x") is not None


def test_cycle_agent_sends_many_intents_and_riesame_on_loss(broker, monkeypatch):
    import llm.runtime as rt
    monkeypatch.setattr(rt, "call", lambda agent, task, data=None, schema=None, purpose="", **k: dict(
        ok=True, output=dict(trades=[dict(_trade("AAPL", 1000), tipo_ordine="market") for _ in range(12)], nota="scalping")))
    r = FD.cycle()
    assert len(r["trade"]) == 12 * len(r["agenti"]) and not r["rifiutati"]     # 12 trade per chiamata
    broker.equity, broker.last_equity = 94000.0, 100000.0                  # -6% di giornata
    seen = []
    monkeypatch.setattr(ID, "generate", lambda a, rows=None, runtime=None, note=None: (seen.append((a, note)) or dict(ok=False, motivo="x")))
    out = FD.riesame_if_needed()
    assert out and {a for a, _ in seen} == {"capo", "cro", "head_research", "head_intel"}                        # perdita: si parla, non si blocca niente
    assert FD.riesame_if_needed() is None                                  # una volta al giorno


def test_not_configured_is_a_noop(firm_env, monkeypatch):
    monkeypatch.delenv("ALPACA_PAPER_KEY", raising=False)
    assert "chiavi" in FD.cycle()["nota"] and FD.riesame_if_needed() is None


def _age_rule(kind, days):
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    db.ex("UPDATE house_rules SET ts=? WHERE kind=?", (old, kind))


def _vote(monkeypatch, decision):
    import llm.runtime as rt

    def call(agent, task, data=None, schema=None, purpose="", **k):
        if purpose.endswith(":replica"):
            return dict(ok=True, output=dict(replica="x", posizione_finale=decision, fiducia=0.7))
        return dict(ok=True, output=dict(posizione=decision, argomento="a", evidenza=["x"], fiducia=0.7, cambierei_idea_se="b"))
    monkeypatch.setattr(rt, "call", call)


def test_rule_comes_back_to_council_to_be_reconfirmed_or_lapse(broker, monkeypatch):
    FD.set_house_rule("max_trades_per_hour", 3, "comitato#1")
    assert ID.schedule_reviews() == 0                                       # appena votata: nessun riesame
    _age_rule("max_trades_per_hour", 20)
    assert ID.schedule_reviews() == 1 and ID.schedule_reviews() == 0        # scaduta: va in consiglio (una sola volta)
    _vote(monkeypatch, "approva")
    out = ID.committee()
    assert out[0]["stato"] == "riconfermata" and FD.active_rules() == {"max_trades_per_hour": 3.0}     # riconfermata: resta, e il riesame riparte
    assert FD.rules_detail()[0]["voti"] == 2 and ID.schedule_reviews() == 0
    _age_rule("max_trades_per_hour", 40)
    assert ID.schedule_reviews() == 1
    _vote(monkeypatch, "respingi")
    assert ID.committee()[0]["stato"] == "decaduta" and FD.active_rules() == {}                        # respinta: la regola decade


def test_agent_can_change_or_revoke_rule_anytime_and_rule_is_binding_meanwhile(broker):
    FD.set_house_rule("max_leverage", 0.5, "comitato#1")
    assert not FD.execute("a1", _trade(usd=90000), FD.state())["ok"]       # finche' e' in vigore, il codice la fa rispettare
    FD.set_house_rule("max_leverage", 5, "comitato#2")                     # riportata in consiglio e cambiata: nessuna pausa imposta
    assert FD.execute("a1", _trade(usd=90000), FD.state())["ok"]


def test_class_share_symbol_and_hold_timer_starts_at_fill(broker):
    assert FD._norm("BRK-B") == ("BRK.B", False) and FD._norm("btc/usd") == ("BTC", True) and FD._norm("SOL") == ("SOL", True)
    assert FD.execute("pod_trend", _trade("BRK-B", 1000, hold=120), FD.state())["ok"]
    assert broker.orders[0]["symbol"] == "BRK.B"
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")      # ordine inviato sabato, riempito lunedi'
    until = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2) + dt.timedelta(minutes=120)).strftime("%Y-%m-%dT%H:%M:%SZ")
    db.ex("UPDATE free_trades SET ts=?, hold_until=?", (old, until))
    assert FD.monitor() == []                                                  # riempito adesso: le 2 ore partono da adesso, non e' gia' scaduto
    row = db.one("SELECT * FROM free_trades")
    assert row["status"] == "aperta" and row["hold_until"] > dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_agent_chooses_when_to_be_called_again(broker, monkeypatch):
    import llm.runtime as rt
    out = dict(trades=[], nota="aspetto", richiamami_tra_minuti=5)
    monkeypatch.setattr(rt, "call", lambda *a, **k: dict(ok=True, output=out))
    FD.cycle(agents=["pod_crypto"])
    assert "pod_crypto" in FD._wake() and FD.due_agents() == []                         # richiamato tra 5 minuti, non adesso
    db.runtime_set("free.wake", {"pod_crypto": "2000-01-01T00:00:00Z"})
    assert FD.due_agents() == ["pod_crypto"]                                            # il suo momento e' arrivato
    monkeypatch.setattr(rt, "call", lambda *a, **k: dict(ok=False, motivo="budget"))
    FD.cycle(agents=["pod_crypto"])
    assert FD.due_agents() == []                                                        # budget finito: non si martella, riprova tra 15 minuti
    out["richiamami_tra_minuti"] = 0
    monkeypatch.setattr(rt, "call", lambda *a, **k: dict(ok=True, output=out))
    db.runtime_set("free.wake", {"pod_crypto": "2000-01-01T00:00:00Z"})
    FD.cycle(agents=["pod_crypto"])
    assert FD._wake() == {}                                                              # 0 = torna al giro normale


def test_traders_come_first_and_leaderboard(broker):
    picked = FD.pick_agents(3)
    assert sum(1 for a in picked if a in FD.traders()) >= 2                       # il banco e' dei trader
    FD.execute("pod_trend", _trade("AAPL", 1000, hold=0), FD.state()); FD.monitor()
    broker.px["AAPL"] = 102.0; db.ex("UPDATE free_trades SET take_pct=1")
    FD.monitor()
    lb = FD.leaderboard()
    assert lb[0]["agent"] == "pod_trend" and lb[0]["pnl"] > 0 and lb[0]["vinti"] == 1
