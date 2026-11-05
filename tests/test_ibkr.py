"""IBKR: osservatore in sola lettura, esecutore solo su un secondo conto paper, ordini limite idempotenti."""
import types

import pytest


class FakeIB:
    """Finto IB Gateway: registra le chiamate e simula gli eseguiti."""
    def __init__(self, accounts=("DU111111",), fill_ratio=1.0, nav=101234.5):
        self.accounts = list(accounts); self.calls = []; self.trades = []; self._fills = []
        self.fill_ratio = fill_ratio; self.nav = nav; self.readonly = None; self.connected = False
    def connect(self, host, port, clientId, timeout=4, readonly=False):
        self.connected = True; self.readonly = readonly; self.calls.append(("connect", port, clientId, readonly))
    def disconnect(self): self.connected = False
    def managedAccounts(self): return self.accounts
    def accountValues(self, acct):
        return [types.SimpleNamespace(tag="NetLiquidation", currency="EUR", value=str(self.nav))]
    def positions(self, acct=""):
        c = types.SimpleNamespace(localSymbol="CSPX", symbol="CSPX", secType="STK")
        return [types.SimpleNamespace(contract=c, position=3, avgCost=600.0)]
    def fills(self): return self._fills
    def openTrades(self): return [t for t in self.trades if t.orderStatus.status == "Submitted"]
    def qualifyContracts(self, c): return [c]
    def sleep(self, s=0): pass
    def placeOrder(self, contract, order):
        self.calls.append(("place", order.action, order.totalQuantity, order.lmtPrice, order.tif, order.orderRef, order.account))
        if self.readonly:
            raise RuntimeError("read-only")
        q = order.totalQuantity * self.fill_ratio
        ex = types.SimpleNamespace(shares=q, price=order.lmtPrice, orderRef=order.orderRef)
        fills = [types.SimpleNamespace(execution=ex, commissionReport=types.SimpleNamespace(commission=1.5))] if q > 0 else []
        self._fills += fills
        st = "Filled" if self.fill_ratio >= 1 else "Submitted"
        t = types.SimpleNamespace(order=order, orderStatus=types.SimpleNamespace(status=st), fills=fills)
        self.trades.append(t); return t
    def cancelOrder(self, order):
        self.calls.append(("cancel", order.orderRef))
        for t in self.trades:
            if t.order is order: t.orderStatus.status = "Cancelled"


@pytest.fixture()
def env(firm_env, monkeypatch):
    pytest.importorskip("ib_async")
    from firm import org_seed, registry, pods
    org_seed.seed(); registry.sync(); pods.ensure_pods()
    monkeypatch.setenv("IBKR_CHALLENGE_ACCOUNT", "DU999999")
    monkeypatch.setattr("firm.ibkr.FILL_TIMEOUT_S", 0.01)
    return firm_env


def test_observer_is_readonly_and_masks_account(env):
    from firm import ibkr, db
    fake = FakeIB(accounts=["DU999999"])
    snap = ibkr.observe_challenge(factory=lambda: fake)
    assert snap["ok"] and fake.readonly is True and snap["conto"] == "DU****999"
    assert "DU999999" not in str(db.runtime_get("ibkr.challenge"))
    assert db.one("SELECT nav FROM nav_marks WHERE pod='pod_zero'")["nav"] == pytest.approx(101234.5)


def test_observer_refuses_live_account(env):
    from firm import ibkr
    snap = ibkr.observe_challenge(factory=lambda: FakeIB(accounts=["U1234567"]))
    assert not snap["ok"] and "paper" in snap["errore"]


def test_executor_requires_a_second_paper_account(env, monkeypatch):
    from firm import ibkr
    monkeypatch.delenv("IBKR_FIRM_ACCOUNT", raising=False)
    with pytest.raises(PermissionError):
        ibkr.IBKRPaperBroker(factory=FakeIB)
    monkeypatch.setenv("IBKR_FIRM_ACCOUNT", "U7654321")
    with pytest.raises(PermissionError):
        ibkr.IBKRPaperBroker(factory=FakeIB)
    monkeypatch.setenv("IBKR_FIRM_ACCOUNT", "DU999999")                 # = conto della sfida
    with pytest.raises(PermissionError):
        ibkr.IBKRPaperBroker(factory=lambda: FakeIB(accounts=["DU999999"]))
    monkeypatch.setenv("IBKR_FIRM_ACCOUNT", "DU222222")
    with pytest.raises(PermissionError):                                  # il gateway dei pod vede anche la sfida
        ibkr.IBKRPaperBroker(factory=lambda: FakeIB(accounts=["DU222222", "DU999999"]))


def test_limit_orders_whole_shares_idempotent_and_partial(env, monkeypatch):
    from firm import ibkr
    monkeypatch.setenv("IBKR_FIRM_ACCOUNT", "DU222222")
    fake = FakeIB(accounts=["DU222222"])
    br = ibkr.IBKRPaperBroker(factory=lambda: fake)
    px, fee, q = br.execute("CSPX", "etf_ucits", "BUY", 2.7, 600.0, ref="GERVA-CAP-1-CSPX")
    place = [c for c in fake.calls if c[0] == "place"][0]
    assert place[2] == 2 and place[3] == pytest.approx(606.0) and place[4] == "DAY" and place[6] == "DU222222"
    assert q == 2 and fee == pytest.approx(1.5)
    # stesso orderRef dopo una riconnessione: non si reinvia
    assert br.execute("CSPX", "etf_ucits", "BUY", 2, 600.0, ref="GERVA-CAP-1-CSPX")[2] == 0
    assert len([c for c in fake.calls if c[0] == "place"]) == 1
    # eseguito parziale allo scadere: il residuo si annulla
    fake.fill_ratio = 0.5
    _, _, q2 = br.execute("BTC", "crypto", "SELL", 0.02, 60000.0, ref="GERVA-CAP-2-BTC")
    assert q2 == pytest.approx(0.01) and ("cancel", "GERVA-CAP-2-BTC") in fake.calls
    assert [c for c in fake.calls if c[0] == "place"][-1][4] == "IOC"


def test_kill_blocks_ibkr_execution(env, monkeypatch):
    from firm import ibkr, risk
    monkeypatch.setenv("IBKR_FIRM_ACCOUNT", "DU222222")
    br = ibkr.IBKRPaperBroker(factory=lambda: FakeIB(accounts=["DU222222"]))
    risk.engage_kill("risk_engine", "test")
    with pytest.raises(PermissionError):
        br.execute("CSPX", "etf_ucits", "BUY", 1, 600.0)


def test_gateway_flush_allocates_partial_fills(env, monkeypatch):
    import datetime as dt
    from firm import gateway, db

    class Half:
        venue = "fake"
        def execute(self, instrument, kind, side, qty, price, ref=None):
            return price, 1.0, qty / 2
    gateway.set_price("CSPX", 600.0, "etf_ucits")
    now = dt.datetime(2026, 11, 4, 14, tzinfo=dt.timezone.utc)
    gateway.submit_order("trend", "pod_trend", "CSPX", "BUY", 2, "trend in acquisto", "settimane", now=now)
    gateway.flush(Half())
    assert gateway.positions("trend")["CSPX"] == pytest.approx(1)
    assert db.one("SELECT status FROM gateway_orders")["status"] == "eseguito_parziale"


def test_reconcile_flags_differences(env, monkeypatch):
    from firm import ibkr, gateway, db
    class B:
        def positions(self): return {"CSPX": 3.0}
    diffs = ibkr.reconcile(B())
    assert diffs and diffs[0]["scarto"] == 3.0
