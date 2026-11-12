"""Ciclo live: registro, rischio, broker paper, ordini idempotenti, recupero dopo crash, KILL, fotografia, cancelli."""
import json
import os
import time

import numpy as np
import pandas as pd
import pytest

from gerva.execution.alpaca import AlpacaPaper
from gerva.execution.broker import Fill, PaperBroker
from gerva.live import gates, snapshot
from gerva.live.runner import EXIT_KILLED, Runner, Settings
from gerva.ops.journal import Journal
from gerva.ops.resilience import CircuitBreaker, CircuitOpen, Timeout, retry, with_timeout
from gerva.ops import supervisor
from gerva.risk.engine import HARD_MAX_LEVERAGE, Limits, RiskEngine
from gerva.strategies import book


# ------------------------------------------------------------------ finti
class FakeMarket:
    """Mercato sintetico con la stessa interfaccia di gerva.live.market.Market."""

    def __init__(self, seed=0, n=1200):
        rng = np.random.default_rng(seed)
        idx = pd.date_range(pd.Timestamp.now(tz="UTC").tz_localize(None).normalize() - pd.Timedelta(days=n), periods=n, freq="D")
        coins = ["BTC", "ETH"] + [f"C{i}" for i in range(8)]
        r = rng.normal(0.002, 0.03, (n, len(coins)))
        self.cclose = pd.DataFrame(100 * np.exp(np.cumsum(r, 0)), index=idx, columns=coins)
        self.cdvol = pd.DataFrame(rng.uniform(1e6, 1e8, r.shape), index=idx, columns=coins)
        self.cret = self.cclose.pct_change(fill_method=None)
        bidx = pd.bdate_range(idx[0] - pd.Timedelta(days=6000), idx[-1])
        syms = book.TREND_UNIVERSE
        e = rng.normal(0.0004, 0.01, (len(bidx), len(syms)))
        c = pd.DataFrame(50 * np.exp(np.cumsum(e, 0)), index=bidx, columns=syms)
        c["^IRX"] = 4.0
        self.P = dict(open=c, high=c * 1.01, low=c * 0.99, close=c, adj=c, volume=c * 0 + 1e6)
        self.errors, self.fail, self.age = {}, False, {"crypto": 1.0, "ibkr": 20.0}

    @property
    def rf(self):
        return (self.P["adj"]["^IRX"] / 100 / 252).ffill()

    def refresh(self, keep_open_bar=False):
        if self.fail:
            self.errors = {"crypto": "giu'", "ibkr": "giu'"}
        else:
            self.errors = {}

    def ages(self, now=None):
        return dict(self.age)

    def venue_of(self, s):
        return "crypto" if s in self.cclose.columns else "ibkr"

    def last_prices(self, symbols):
        out = {}
        for s in symbols:
            if s in self.cclose.columns:
                out[s] = float(self.cclose[s].iloc[-1])
            elif s in self.P["close"].columns:
                out[s] = float(self.P["close"][s].iloc[-1])
        return out


@pytest.fixture
def rig(tmp_path):
    m = FakeMarket()
    j = Journal(str(tmp_path / "j.sqlite"))
    b = PaperBroker(j, m.last_prices, 12_000.0, venue_of=m.venue_of)
    s = Settings(home=str(tmp_path), interval=1.0, equity_window=("00:00", "23:59"))
    r = Runner(s, Limits(), b, m, j)
    r.equity_window_open = lambda now=None: True            # i test non dipendono dal giorno della settimana
    return r


# ------------------------------------------------------------------ limiti
def test_limits_reject_leverage_above_hard_cap():
    with pytest.raises(ValueError):
        Limits(max_leverage=HARD_MAX_LEVERAGE + 0.01)
    with pytest.raises(ValueError):
        Limits(dd_reduce=0.2, dd_halt=0.15)
    assert Limits(max_leverage=3.0).max_leverage == 3.0


def test_config_file_is_valid_and_paper_only(tmp_path):
    from gerva.config import load
    s, l, c = load()
    assert s.mode in ("paper", "alpaca-paper") and l.max_leverage <= 2.0 and l.dd_kill == 0.20
    bad = tmp_path / "g.yaml"
    bad.write_text("mode: live\n")
    with pytest.raises(ValueError):
        load(str(bad))


def test_agents_cannot_touch_limits():
    """Nessuno strumento degli agenti LLM cita il file dei limiti del motore o il file KILL del motore."""
    import llm.tools as T
    src = open(T.__file__).read()
    assert "gerva.yaml" not in src and "var/gerva" not in src and "reset_kill" not in src


# ------------------------------------------------------------------ rischio
def _engine(tmp_path, **kw):
    j = Journal(str(tmp_path / "r.sqlite"))
    return RiskEngine(Limits(**kw), j, str(tmp_path / "KILL")), j


def test_drawdown_ladder_and_hysteresis(tmp_path):
    e, j = _engine(tmp_path)
    t = 1_700_000_000.0
    assert e.assess(100.0, t).state == "NORMAL"
    assert e.assess(91.0, t + 1).state == "NORMAL"
    a = e.assess(89.0, t + 2)
    assert a.state == "REDUCED" and a.scale == 0.5 and a.drawdown == pytest.approx(-0.11)
    assert e.assess(93.0, t + 3).state == "REDUCED"           # -7%: non basta, deve rientrare sotto -5%
    assert e.assess(96.0, t + 4).state == "NORMAL"
    assert e.assess(84.0, t + 5).state == "HALTED"
    assert e.assess(90.0, t + 6).state == "HALTED"            # -10%: deve rientrare sotto -7,5%
    assert e.assess(94.0, t + 7).state == "REDUCED"
    assert e.assess(96.0, t + 8).state == "NORMAL"


def test_kill_latches_and_needs_manual_reset(tmp_path):
    e, j = _engine(tmp_path)
    e.assess(100.0, 1.0)
    a = e.assess(79.0, 2.0)
    assert a.state == "KILLED" and a.scale == 0.0 and os.path.exists(e.kill_file)
    assert e.assess(100.0, 3.0).state == "KILLED"             # il rimbalzo non lo toglie
    assert e.reset_kill() is False                            # il file c'e' ancora
    os.remove(e.kill_file)
    assert e.assess(100.0, 4.0).state == "KILLED"             # tolto il file ma non dato il comando
    assert e.reset_kill() is True
    assert e.assess(100.0, 5.0).state == "NORMAL"


def test_kill_file_from_outside_and_other_triggers(tmp_path):
    e, j = _engine(tmp_path)
    assert e.assess(100.0, 1.0, data_stale=["crypto (40h)"]).state == "HALTED"
    assert e.assess(100.0, 2.0, unreconciled=True).state == "HALTED"
    assert e.assess(100.0, 3.0, error_streak=5).state == "HALTED"
    assert e.assess(100.0, 4.0).state == "NORMAL"
    open(e.kill_file, "w").write("dalla dashboard")
    assert e.assess(100.0, 5.0).state == "KILLED"


def test_daily_and_weekly_loss(tmp_path):
    e, j = _engine(tmp_path)
    t = 1_700_000_000.0
    j.record_nav(100.0, 100.0, 0, 0, t)
    assert e.assess(100.0, t).state == "NORMAL"
    j.record_nav(100.0, 100.0, 0, 0, t + 3600)
    a = e.assess(95.5, t + 86400 + 3600)
    assert a.state == "REDUCED" and a.day_pnl == pytest.approx(-0.045)
    assert e.assess(91.5, t + 2 * 86400).state == "HALTED"     # -8,5% in una settimana


def test_clamp_weights_only_reduces(tmp_path):
    e, _ = _engine(tmp_path)
    venue = {"BTC": "crypto", "ETH": "crypto", "SOL": "crypto", "SPY": "ibkr", "TLT": "ibkr", "GLD": "ibkr", "DBC": "ibkr"}
    w, notes = e.clamp_weights({"BTC": 0.5, "ETH": 0.3, "SOL": 0.3, "SPY": 0.9, "TLT": 0.3, "GLD": 0.3, "DBC": 0.3}, venue)
    assert w["BTC"] <= 0.35 and w["SPY"] <= 0.35
    assert sum(abs(v) for k, v in w.items() if venue[k] == "crypto") <= e.l.max_venue["crypto"] + 1e-9
    assert sum(abs(v) for v in w.values()) <= 2.0 + 1e-9 and notes
    small = {"BTC": 0.1, "SPY": 0.1}
    assert e.clamp_weights(small, venue)[0] == small


def test_order_checks_never_block_a_reduction(tmp_path):
    e, _ = _engine(tmp_path)
    ok = lambda *a: e.check_order(*a)[0]
    assert ok("BTC", 1000.0, 0.0, 100.0, 100.0, 10_000.0, "NORMAL")
    assert not ok("BTC", 1000.0, 0.0, 100.0, 100.0, 10_000.0, "HALTED")
    assert not ok("BTC", 1000.0, 0.0, 100.0, 100.0, 10_000.0, "KILLED")
    assert ok("BTC", -500.0, 1000.0, 100.0, 100.0, 10_000.0, "KILLED")          # ridurre passa sempre
    assert ok("BTC", -1000.0, 1000.0, 100.0, 100.0, 10_000.0, "HALTED")
    assert not ok("BTC", -1500.0, 1000.0, 100.0, 100.0, 10_000.0, "HALTED")     # capovolgere in short NON e' ridurre
    assert not ok("BTC", 3000.0, 0.0, 100.0, 100.0, 10_000.0, "NORMAL")         # oltre il 25% del patrimonio
    assert not ok("BTC", 1000.0, 0.0, 110.0, 100.0, 10_000.0, "NORMAL")         # prezzo lontano dall'ultimo noto
    assert not ok("BTC", 10.0, 0.0, 100.0, 100.0, 10_000.0, "NORMAL")           # sotto il minimo
    assert ok("BTC", -10.0, 10.0, 100.0, 100.0, 10_000.0, "NORMAL")             # ...ma la chiusura totale passa


# ------------------------------------------------------- registro e broker
def test_journal_intent_is_unique_and_survives_reopen(tmp_path):
    p = str(tmp_path / "j.sqlite")
    j = Journal(p)
    assert j.intent("2026-01-01:BTC", "2026-01-01", "BTC", "BUY", 1.0, 100.0, "crypto", "CR-TREND") is True
    assert j.intent("2026-01-01:BTC", "2026-01-01", "BTC", "BUY", 1.0, 100.0, "crypto", "CR-TREND") is False
    j.set("x", {"a": 1})
    j.close()
    j2 = Journal(p)
    assert j2.get("x") == {"a": 1} and len(j2.open_intents()) == 1
    j2.resolve("2026-01-01:BTC", "filled", 1.0, 100.5, 0.2)
    assert j2.open_intents() == [] and j2.order("2026-01-01:BTC")["fill_price"] == 100.5


def test_paper_broker_is_idempotent_and_conserves_money(tmp_path):
    j = Journal(str(tmp_path / "b.sqlite"))
    px = {"BTC": 100.0}
    b = PaperBroker(j, lambda s: {k: px[k] for k in s if k in px}, 10_000.0, fee={"crypto": 0.001}, slippage={"crypto": 0.0},
                    venue_of=lambda s: "crypto")
    f1 = b.submit("a", "BTC", 10.0, 100.0)
    f2 = b.submit("a", "BTC", 10.0, 100.0)                    # stesso identificativo: nessun secondo ordine
    assert f1.status == "filled" and f2 == f1 and b.positions()["BTC"].qty == 10.0
    assert b.account().equity == pytest.approx(10_000.0 - 1.0)   # solo la commissione
    px["BTC"] = 110.0
    assert b.account().equity == pytest.approx(10_099.0)
    assert b.submit("big", "BTC", 400.0, 110.0).status == "rejected"     # oltre la leva massima fisica
    assert b.submit("nopx", "XYZ", 1.0, 1.0).status == "rejected"
    b2 = PaperBroker(Journal(str(tmp_path / "b.sqlite")), lambda s: {k: px[k] for k in s if k in px})
    assert b2.positions()["BTC"].qty == 10.0                  # lo stato sopravvive al riavvio
    assert [f.status for f in b2.flatten()] == ["filled"] and b2.positions() == {}


def test_alpaca_adapter_against_fake_service():
    calls, store = [], {}

    def http(method, url, headers, body=None, timeout=15.0):
        calls.append((method, url))
        assert headers["APCA-API-KEY-ID"] == "k" and url.startswith(("https://paper-api.alpaca.markets", "https://data.alpaca.markets"))
        if url.endswith("/v2/account"):
            return 200, {"equity": "1000.5", "cash": "400"}
        if url.endswith("/v2/positions"):
            return 200, [{"symbol": "BTCUSD", "qty": "0.5", "side": "long", "current_price": "100"}]
        if "latest/trades" in url:
            return 200, {"trades": {"BTC/USD": {"p": 101.0}}}
        if method == "POST" and url.endswith("/v2/orders"):
            if body["client_order_id"] in store:
                return 422, {"message": "client_order_id must be unique"}
            store[body["client_order_id"]] = dict(body, status="filled", filled_qty=body["qty"], filled_avg_price="101")
            return 200, store[body["client_order_id"]]
        if "by_client_order_id" in url:
            cid = url.split("client_order_id=")[1].replace("%3A", ":")
            return (200, store[cid]) if cid in store else (404, {})
        return 500, {}
    a = AlpacaPaper("k", "s", http=http, wait_fill=0.0)
    assert a.account().equity == 1000.5 and a.prices(["BTC"]) == {"BTC": 101.0}
    assert a.positions()["BTC"].qty == 0.5
    f = a.submit("2026-01-01:BTC", "BTC", 0.25, 101.0)
    assert f.status == "filled" and f.qty == 0.25 and f.price == 101.0
    again = a.submit("2026-01-01:BTC", "BTC", 0.25, 101.0)    # il servizio risponde 422: si legge l'esito, niente doppione
    assert again.status == "filled" and len(store) == 1
    assert a.lookup("mai-visto") is None
    assert "live" not in " ".join(u for _, u in calls) and all("api.alpaca.markets" not in u or "paper-api" in u for _, u in calls if "data." not in u)


# ------------------------------------------------------------------ ciclo
def test_cycle_trades_once_and_rerun_does_not_duplicate(rig):
    out = rig.cycle()
    assert out["state"] == "NORMAL" and out["orders"] > 0
    pos1 = {k: p.qty for k, p in rig.broker.positions().items()}
    n1 = len(rig.j.orders(500))
    out2 = rig.cycle()
    assert out2["orders"] == 0 and len(rig.j.orders(500)) == n1          # stesso giorno di decisione: nulla di nuovo
    assert {k: p.qty for k, p in rig.broker.positions().items()} == pos1
    acct = rig.broker.account()
    gross = sum(abs(p.value) for p in rig.broker.positions().values()) / acct.equity
    assert gross <= rig.l.max_leverage + 1e-6
    crypto = sum(abs(p.value) for k, p in rig.broker.positions().items() if rig.market.venue_of(k) == "crypto") / acct.equity
    assert crypto <= rig.l.max_venue["crypto"] + 0.02
    snap = json.load(open(os.path.join(rig.s.home, "snapshot.json")))
    for key in ("meta", "nav", "equity_curve", "monthly_returns", "performance", "exposure", "positions", "risk", "strategies",
                "orders", "system", "alerts", "gates"):
        assert key in snap
    assert snap["meta"]["mode"] == "paper" and "PAPER" in snap["meta"]["data_label"] and len(snap["strategies"]) == 4
    assert "NaN" not in open(os.path.join(rig.s.home, "snapshot.json")).read()


def test_stale_data_blocks_increases_but_not_the_cycle(rig):
    rig.market.age = {"crypto": 99.0, "ibkr": 500.0}
    out = rig.cycle()
    assert out["state"] == "HALTED" and out["orders"] == 0 and rig.broker.positions() == {}


def test_data_outage_does_not_crash_and_holds_positions(rig):
    rig.cycle()
    before = {k: p.qty for k, p in rig.broker.positions().items()}
    rig.market.fail = True
    out = rig.cycle()
    assert out["state"] in ("NORMAL", "HALTED") and {k: p.qty for k, p in rig.broker.positions().items()} == before


def test_crash_between_intent_and_submit_is_recovered_without_resend(rig):
    rig.j.intent("2020-01-01:BTC", "2020-01-01", "BTC", "BUY", 1.0, 100.0, "crypto", "CR-TREND")   # il broker non l'ha mai visto
    assert rig.recover() is False
    assert rig.j.order("2020-01-01:BTC")["status"] == "cancelled" and "BTC" not in rig.broker.positions()
    # il broker l'aveva eseguito ma il processo e' morto prima di registrarlo
    rig.j.intent("2020-01-02:ETH", "2020-01-02", "ETH", "BUY", 0.5, 100.0, "crypto", "CR-TREND")
    rig.broker.submit("2020-01-02:ETH", "ETH", 0.5, 100.0)
    assert rig.recover() is False and rig.j.order("2020-01-02:ETH")["status"] == "filled"
    assert rig.broker.positions()["ETH"].qty == 0.5           # una volta sola


def test_unknown_outcome_halts_trading_until_reconciled(rig):
    class Flaky:
        name = "flaky"

        def __init__(self, inner):
            self.inner, self.boom = inner, True

        def __getattr__(self, k):
            return getattr(self.inner, k)

        def submit(self, *a):
            if self.boom:
                raise ConnectionError("timeout dopo l'invio")
            return self.inner.submit(*a)

        def lookup(self, cid):
            return Fill(cid, "pending")
    rig.broker = Flaky(rig.broker)
    out = rig.cycle()
    assert out["orders"] == 0 and len(rig.j.open_intents()) == 1
    out2 = rig.cycle()                                        # esito ancora ignoto: stato HALTED, nessun nuovo ordine
    assert out2["state"] == "HALTED" and out2["orders"] == 0 and len(rig.j.open_intents()) == 1


def test_kill_flattens_and_runner_exits_with_code_3(rig):
    rig.cycle()
    assert rig.broker.positions()
    rig.risk.trigger_kill("prova")
    code = rig.run_forever(max_cycles=3, sleep=lambda s: None)
    assert code == EXIT_KILLED and rig.broker.positions() == {}
    assert rig.j.get("risk.state") == "KILLED"
    out = rig.cycle()                                         # resta fermo anche se richiamato
    assert out["state"] == "KILLED" and out["orders"] == 0


def test_run_forever_survives_exceptions_and_counts_streak(rig):
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise RuntimeError("guasto")
    rig.cycle = boom
    assert rig.run_forever(max_cycles=6, sleep=lambda s: None) == 0 and calls["n"] == 6
    assert rig.j.get("error_streak") == 6
    assert any(e["level"] == "critical" for e in rig.j.events(20))


def test_live_weights_equal_backtest_last_row(rig):
    """Parita' backtest/live: i pesi del ciclo sono l'ultima riga delle stesse funzioni usate dalla ricerca."""
    from gerva.live import pipeline
    t = pipeline.build(rig.market, 0.15, 2.0)
    w = book.cr_trend(rig.market.cclose).iloc[-1]
    for sym in ("BTC", "ETH"):
        assert t.by_sleeve["CR-TREND"].get(sym, 0.0) == pytest.approx(t.leverage * t.alloc["CR-TREND"] * w[sym], abs=1e-12)
    assert 0.5 < sum(t.alloc.values()) <= 1.0 + 1e-9 and 0 < t.leverage <= 2.0     # il tetto del 60% lascia l'eccesso in cassa


# ----------------------------------------------------- robustezza e varie
def test_retry_circuit_breaker_timeout():
    n = {"k": 0}

    def flaky():
        n["k"] += 1
        if n["k"] < 3:
            raise ConnectionError
        return "ok"
    assert retry(flaky, tries=4, sleep=lambda s: None) == "ok" and n["k"] == 3
    with pytest.raises(ValueError):
        retry(lambda: (_ for _ in ()).throw(ValueError()), tries=3, sleep=lambda s: None, give_up_on=(ValueError,))
    clock = {"t": 0.0}
    cb = CircuitBreaker("x", 2, 10.0, clock=lambda: clock["t"])
    for _ in range(2):
        with pytest.raises(ZeroDivisionError):
            cb.call(lambda: 1 / 0)
    with pytest.raises(CircuitOpen):
        cb.call(lambda: 1)
    clock["t"] = 11.0
    assert cb.call(lambda: 7) == 7 and cb.state == "closed"
    with pytest.raises(Timeout):
        with_timeout(lambda: time.sleep(2), 0.05)


def test_supervisor_restarts_then_gives_up(tmp_path, monkeypatch):
    hb = str(tmp_path / "hb")
    sent = []
    monkeypatch.setattr(supervisor.alerts, "send", lambda level, msg, **k: sent.append(level))
    code = supervisor.supervise(["python3", "-c", "import sys; sys.exit(1)"], hb, max_restarts=2, poll=0.01, sleep=lambda s: None)
    assert code == 2 and "critical" in sent
    assert supervisor.supervise(["python3", "-c", "import sys; sys.exit(3)"], hb, poll=0.01, sleep=lambda s: None) == 3
    assert supervisor.supervise(["python3", "-c", "pass"], hb, poll=0.01, sleep=lambda s: None) == 0


def test_gates_need_time_and_clean_record(tmp_path):
    j = Journal(str(tmp_path / "g.sqlite"))
    now = 1_800_000_000.0
    j.set("start_ts", now - 10 * 86400)
    g = gates.evaluate(j, pd.Series(dtype=float), now)
    assert not gates.all_green(g) and next(x for x in g if x["name"].startswith("Giorni"))["ok"] is False
    j.set("start_ts", now - 120 * 86400)
    with j.tx() as db:
        db.executemany("INSERT INTO nav(ts,equity,cash,gross,net) VALUES(?,?,?,?,?)",
                       [(now - 120 * 86400 + i * 900, 100.0, 100.0, 0, 0) for i in range(120 * 96)])
    daily = pd.Series(np.random.default_rng(0).normal(0.002, 0.005, 120))
    g = gates.evaluate(j, daily, now)
    by = {x["name"]: x["ok"] for x in g}
    assert by["Giorni di paper trading"] and by["Disponibilita' del ciclo"] and by["Ordini non riconciliati"] and by["PSR (Sharpe vero > 0)"]
    assert not gates.all_green(g)                             # senza modello e senza eseguiti, scostamento e costi restano rossi
    # con un modello che il paper replica e costi in linea, tutti verdi
    daily.index = pd.date_range("2026-01-01", periods=120)
    for i in range(12):
        j.intent(f"o{i}", "c", "BTC", "BUY", 1.0, 100.0, "crypto", "CR-TREND")
        j.resolve(f"o{i}", "filled", 1.0, 100.05, 0.25)       # 5 pb di slippage + 25 pb di commissione = 30 pb: come ipotizzato
    g = gates.evaluate(j, daily, now, 900.0, daily * 0.99)
    assert gates.all_green(g), [x for x in g if not x["ok"]]
    assert gates.cost_ratio(j) == pytest.approx(1.0, abs=0.01)
    # un paper che NON replica il modello viene fermato
    g = gates.evaluate(j, daily, now, 900.0, daily * 0.2)
    assert not next(x for x in g if x["name"] == "Scostamento dal backtest")["ok"]
    for i in range(12, 40):
        j.intent(f"o{i}", "c", "BTC", "BUY", 1.0, 100.0, "crypto", "CR-TREND")
        j.resolve(f"o{i}", "filled", 1.0, 101.0, 0.25)        # slippage dell'1%: costi quattro volte quelli ipotizzati
    assert not next(x for x in gates.evaluate(j, daily, now, 900.0, daily) if x["name"].startswith("Costi"))["ok"]


def test_cycle_records_exposure_and_model_series(rig):
    rig.cycle()
    expo = rig.j.get("expo")
    assert len(expo) == 1 and 0 < list(expo.values())[0] <= rig.l.max_leverage
    from gerva.live import snapshot as snap
    assert isinstance(snap.model_daily(rig), pd.Series)


def test_demo_snapshot_is_labelled_simulated():
    path = os.path.join(os.path.dirname(__file__), "..", "research", "v5", "series.parquet")
    if not os.path.exists(path):
        pytest.skip("research/v5/series.parquet non generato")
    s = snapshot.demo(path)
    assert s["meta"]["mode"] == "backtest" and s["meta"]["data_label"].startswith("SIMULATO")
    assert len(s["equity_curve"]) > 1000 and len(s["strategies"]) == 4 and s["positions"] == []
    json.dumps(snapshot._clean(s))


def test_park_cash_rules():
    from gerva.live.runner import park_cash
    w = {"BTC": 0.2, "SPY": 0.3}
    assert park_cash(w, None, 0.05, True, "NORMAL") == w                       # non configurato
    assert park_cash(w, "IB01.L", 0.05, False, "NORMAL") == w                  # senza prezzo non si compra
    assert park_cash(w, "IB01.L", 0.05, True, "KILLED") == w                   # in KILLED si chiude tutto, cassa compresa
    out = park_cash(w, "IB01.L", 0.05, True, "NORMAL")
    assert abs(out["IB01.L"] - 0.45) < 1e-12 and out["BTC"] == 0.2
    assert abs(sum(out.values()) - 0.95) < 1e-12                               # mai a debito: resta il 5% liquido
    assert "IB01.L" not in park_cash({"BTC": 0.6, "SPY": 0.5}, "IB01.L", 0.05, True, "NORMAL")   # a leva: niente cassa da parcheggiare
    red = park_cash({"BTC": 0.1, "SPY": 0.15}, "IB01.L", 0.05, True, "REDUCED")                 # rischio ridotto: piu' cassa
    assert abs(red["IB01.L"] - 0.70) < 1e-12
    assert park_cash({"BTC": 0.2, "IB01.L": 0.9}, "IB01.L", 0.05, True, "NORMAL")["IB01.L"] == 0.75  # il peso vecchio si ricalcola
