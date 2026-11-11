"""Adattatore IBKR del motore GERVA contro un ib_async FINTO: solo paper, idempotenza, recupero, KILL, broker composito."""
import datetime as dt
import types

import pytest

from gerva.execution.broker import Account, BrokerError, Fill, Position
from gerva.execution.composite import CompositeBroker
from gerva.execution.ibkr import IBKRPaper, limit_price, load_map, session_open

MAP = {
    "SPY": dict(symbol="IBUS500", sec_type="CFD", exchange="SMART", currency="USD", session="SMART", verified=False),
    "IWM": dict(symbol="R2US", sec_type="STK", exchange="LSEETF", currency="USD", session="LSEETF", verified=True),
}
NY_WINDOW = dt.datetime(2026, 11, 11, 20, 50, tzinfo=dt.timezone.utc)      # mercoledi', 15:50 a New York: Londra e' chiusa
LONDON = dt.datetime(2026, 11, 11, 15, 0, tzinfo=dt.timezone.utc)          # 15:00 a Londra, 10:00 a New York: aperte entrambe


def _contract(sec):
    return lambda symbol, exchange, currency: types.SimpleNamespace(symbol=symbol, secType=sec, exchange=exchange, currency=currency,
                                                                    localSymbol=symbol, multiplier="")


def _order(action, qty, lmt, tif="DAY", orderRef="", account=""):
    return types.SimpleNamespace(action=action, totalQuantity=qty, lmtPrice=lmt, tif=tif, orderRef=orderRef, account=account)


CONTRACTS = {"STK": _contract("STK"), "CFD": _contract("CFD"), "LimitOrder": _order}


class FakeIB:
    """Finto TWS: conto, portafoglio, prezzi, ordini limite che si eseguono in tutto, in parte o per nulla."""

    def __init__(self, accounts=("DU123456",), px=None, fill_ratio=1.0, base="EUR", usd_rate="0.8", nav=100_000.0, cash=40_000.0):
        self.accounts, self.px, self.fill_ratio = list(accounts), dict(px or {"IBUS500": 6000.0, "R2US": 100.0}), fill_ratio
        self.base, self.usd_rate, self.nav, self.cash = base, usd_rate, nav, cash
        self.calls, self.trades, self._fills, self.pos = [], [], [], {}
        self.connected, self.readonly, self.stuck = False, None, False

    # collegamento
    def connect(self, host, port, clientId, timeout=4, readonly=False, account=""):
        self.connected, self.readonly = True, readonly
        self.calls.append(("connect", port, clientId, readonly))

    def disconnect(self):
        self.connected = False

    def isConnected(self):
        return self.connected

    def managedAccounts(self):
        return self.accounts

    def sleep(self, s=0):
        pass

    # letture
    def accountValues(self, acct=""):
        v = lambda tag, ccy, val: types.SimpleNamespace(tag=tag, currency=ccy, value=str(val))
        rows = [v("NetLiquidation", self.base, self.nav), v("TotalCashValue", self.base, self.cash), v("ExchangeRate", self.base, "1.0")]
        return rows + ([v("ExchangeRate", "USD", self.usd_rate)] if self.usd_rate else [])

    def portfolio(self, acct=""):
        return [types.SimpleNamespace(contract=c, position=q, marketPrice=self.px.get(c.symbol, 0.0)) for c, q in self.pos.values() if q]

    def qualifyContracts(self, c):
        return [c if c.symbol in self.px else None]

    def reqContractDetails(self, c):
        return [types.SimpleNamespace(minTick=0.01, sizeIncrement=0, minSize=0)]

    def reqMarketDataType(self, t):
        self.calls.append(("mdtype", t))

    def reqTickers(self, *cs):
        return [types.SimpleNamespace(marketPrice=lambda c=c: self.px[c.symbol], last=float("nan"), close=float("nan")) for c in cs]

    def reqHistoricalData(self, *a, **k):
        return []

    def fills(self):
        return self._fills

    def reqExecutions(self, f=None):
        return self._fills

    def openTrades(self):
        return [t for t in self.trades if not t.isDone()]

    def reqCompletedOrders(self, apiOnly):
        return [t for t in self.trades if t.isDone()]

    # scritture
    def placeOrder(self, contract, order):
        self.calls.append(("place", order.action, order.totalQuantity, order.lmtPrice, order.orderRef, order.account, contract.symbol))
        q = order.totalQuantity * self.fill_ratio
        if q > 0:
            ex = types.SimpleNamespace(shares=q, price=order.lmtPrice, orderRef=order.orderRef, execId=f"e{len(self._fills)}",
                                       side="BOT" if order.action == "BUY" else "SLD")
            self._fills.append(types.SimpleNamespace(execution=ex, commissionReport=types.SimpleNamespace(commission=1.5)))
            c0, q0 = self.pos.get(contract.symbol, (contract, 0.0))
            self.pos[contract.symbol] = (c0, q0 + (q if order.action == "BUY" else -q))
        t = types.SimpleNamespace(order=order, orderStatus=types.SimpleNamespace(status="Filled" if self.fill_ratio >= 1 else "Submitted"))
        t.isDone = lambda t=t: t.orderStatus.status in ("Filled", "Cancelled", "ApiCancelled", "Inactive")
        self.trades.append(t)
        return t

    def cancelOrder(self, order):
        self.calls.append(("cancel", order.orderRef))
        for t in self.trades:
            if t.order is order and not self.stuck:
                t.orderStatus.status = "Cancelled"

    def placed(self):
        return [c for c in self.calls if c[0] == "place"]


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr("firm.ibkr.FILL_TIMEOUT_S", 0.01)
    monkeypatch.setattr("gerva.execution.ibkr.PACING_S", 0.0)
    for k in ("IBKR_GERVA_HOST", "IBKR_GERVA_PORT", "IBKR_GERVA_CLIENT_ID", "IBKR_GERVA_ACCOUNT", "IBKR_CHALLENGE_ACCOUNT"):
        monkeypatch.delenv(k, raising=False)


def adapter(fake, now=NY_WINDOW, **kw):
    return IBKRPaper(factory=lambda: fake, symbols=MAP, contracts=CONTRACTS, now=lambda: now, **kw)


# ------------------------------------------------------------------ solo paper
def test_live_ports_and_non_paper_accounts_are_refused():
    for port in (7496, 4001):
        with pytest.raises(PermissionError):
            adapter(FakeIB(), port=port)
    with pytest.raises(PermissionError):
        adapter(FakeIB(), account="U7654321")
    for accounts in (["U7654321"], ["DU123456", "U7654321"], []):          # anche un solo conto reale VISIBILE basta a rifiutare
        fake = FakeIB(accounts=accounts)
        a = adapter(fake)
        for call in (a.account, a.positions, lambda: a.submit("x", "SPY", 10.0, 600.0), a.flatten, lambda: a.lookup("x")):
            with pytest.raises(PermissionError):
                call()
        assert fake.placed() == [] and fake.connected is False            # scollegato, e nessun ordine partito


def test_several_paper_accounts_need_a_choice_and_challenge_account_is_excluded(monkeypatch):
    with pytest.raises(PermissionError):
        adapter(FakeIB(accounts=["DU111111", "DU222222"])).account()
    assert adapter(FakeIB(accounts=["DU111111", "DU222222"]), account="DU222222").account().equity > 0
    with pytest.raises(PermissionError):
        adapter(FakeIB(accounts=["DU111111"]), account="DU222222").account()
    monkeypatch.setenv("IBKR_CHALLENGE_ACCOUNT", "DU123456")
    with pytest.raises(PermissionError):
        adapter(FakeIB()).account()


def test_read_only_adapter_reads_but_cannot_order():
    fake = FakeIB()
    a = adapter(fake, read_only=True)
    assert a.account().equity == pytest.approx(125_000.0) and fake.readonly is True
    for call in (lambda: a.submit("x", "SPY", 10.0, 600.0), a.flatten, lambda: a.ib.placeOrder(None, None), lambda: a.ib.cancelOrder(None)):
        with pytest.raises(PermissionError):
            call()
    assert fake.placed() == []


# ------------------------------------------------------------------ conto e posizioni
def test_account_is_converted_to_dollars_and_never_zero():
    a = adapter(FakeIB())
    acct = a.account()                                   # 100.000 EUR, 1 USD = 0,8 EUR
    assert acct.equity == pytest.approx(125_000.0) and acct.cash == pytest.approx(50_000.0)
    assert adapter(FakeIB(base="USD", usd_rate="1.0")).account().equity == pytest.approx(100_000.0)
    with pytest.raises(BrokerError):
        adapter(FakeIB(nav=0.0)).account()
    with pytest.raises(BrokerError):                     # nessun cambio noto: mai un cambio inventato
        adapter(FakeIB(usd_rate=None)).account()


def test_positions_use_research_symbols_and_flag_foreign_ones():
    fake = FakeIB(px={"IBUS500": 6000.0, "R2US": 100.0, "XYZ": 10.0})
    fake.pos = {"IBUS500": (CONTRACTS["CFD"]("IBUS500", "SMART", "USD"), 2.0), "XYZ": (CONTRACTS["STK"]("XYZ", "LSEETF", "USD"), 5.0)}
    pos = adapter(fake).positions()
    assert pos == {"SPY": Position(2.0, 6000.0), "IBKR:XYZ": Position(5.0, 10.0)} and pos["SPY"].value == 12_000.0


# ------------------------------------------------------------------ ordini
def test_submit_keeps_notional_is_idempotent_and_unknown_order_is_none():
    fake = FakeIB()
    a = adapter(fake)
    assert a.lookup("2026-11-11:SPY") is None            # mai visto
    f = a.submit("2026-11-11:SPY", "SPY", 40.0, 600.0)   # 24.000 $ -> 4 CFD da 6.000 $
    (_, action, pieces, lmt, ref, account, sym), = fake.placed()
    assert (action, pieces, ref, account, sym) == ("BUY", 4.0, "GERVA-2026-11-11:SPY", "DU123456", "IBUS500")
    assert 6000.0 < lmt <= 6000.0 * 1.005 + 1e-9
    assert f.status == "filled" and f.qty == pytest.approx(40.0) and f.fee == 1.5
    assert f.qty * f.price == pytest.approx(4.0 * lmt)   # stesso controvalore, nelle unita' del simbolo di ricerca
    assert "da verificare" in f.reason
    again = a.submit("2026-11-11:SPY", "SPY", 40.0, 600.0)
    same = lambda x: (x.status, x.qty, x.price, x.fee) == (f.status, f.qty, f.price, f.fee)
    assert same(again) and len(fake.placed()) == 1        # nessun secondo ordine: si legge l'esito del primo
    assert same(a.lookup("2026-11-11:SPY")) and a.lookup("mai-visto") is None
    b = adapter(fake)                                    # dopo un riavvio: l'esito c'e' ancora, in pezzi dello strumento
    g = b.submit("2026-11-11:SPY", "SPY", 40.0, 600.0)
    assert g.status == "filled" and g.qty == 4.0 and g.price == 0.0 and len(fake.placed()) == 1
    assert a.positions()["SPY"].qty == 4.0


def test_orders_that_must_not_leave():
    fake = FakeIB()
    a = adapter(fake)
    assert "borsa chiusa" in a.submit("d:IWM", "IWM", 100.0, 200.0).reason              # Londra e' chiusa alle 15:50 di New York
    assert "nessuno strumento" in a.submit("d:EFA", "EFA", 10.0, 80.0).reason           # non mappato
    assert "nessuno strumento" in a.submit("d:BTC", "BTC", 0.1, 90_000.0).reason
    assert "meno di un pezzo" in a.submit("d:SPY", "SPY", 5.0, 600.0).reason            # 3.000 $ < un CFD da 6.000 $
    del fake.px["IBUS500"]
    assert "non trovato" in a.submit("d2:SPY", "SPY", 40.0, 600.0).reason
    assert fake.placed() == []
    f = adapter(fake, now=LONDON).submit("d:IWM", "IWM", 100.0, 200.0)                  # a Londra aperta: 20.000 $ -> 200 pezzi da 100 $
    assert f.status == "filled" and fake.placed()[0][2] == 200.0 and "da verificare" not in f.reason


def test_unfilled_and_partial_orders_are_cancelled_and_confirmed():
    fake = FakeIB(fill_ratio=0.0)
    a = adapter(fake)
    f = a.submit("d:SPY", "SPY", 40.0, 600.0)
    assert f.status == "rejected" and f.qty == 0 and ("cancel", "GERVA-d:SPY") in fake.calls
    assert a.submit("d:SPY", "SPY", 40.0, 600.0).status == "rejected" and len(fake.placed()) == 1     # un ordine per identificativo
    fake = FakeIB(fill_ratio=0.5)
    f = adapter(fake).submit("d:SPY", "SPY", 40.0, 600.0)
    assert f.status == "partial" and f.qty == pytest.approx(20.0)
    fake = FakeIB(fill_ratio=0.0)
    fake.stuck = True                                    # l'annullamento non viene confermato: esito ignoto, si solleva
    monkey = adapter(fake)
    import firm.ibkr
    orig = firm.ibkr.time.monotonic
    ticks = iter(range(0, 10_000, 5))
    firm.ibkr.time.monotonic = lambda: next(ticks)
    try:
        with pytest.raises(RuntimeError):
            monkey.submit("d:SPY", "SPY", 40.0, 600.0)
    finally:
        firm.ibkr.time.monotonic = orig


def test_sell_closes_exactly_what_is_held():
    fake = FakeIB()
    fake.pos = {"IBUS500": (CONTRACTS["CFD"]("IBUS500", "SMART", "USD"), 3.0)}
    a = adapter(fake)
    f = a.submit("d:SPY", "SPY", -30.4, 600.0)           # 18.240 $ = 3,04 CFD: e' la chiusura dei 3 in posizione
    assert fake.placed()[0][1:3] == ("SELL", 3.0) and f.qty < 0 and a.positions() == {}


# ------------------------------------------------------------------ KILL
def test_flatten_closes_engine_positions_and_leaves_the_rest():
    fake = FakeIB(px={"IBUS500": 6000.0, "R2US": 100.0, "XYZ": 10.0})
    fake.pos = {"IBUS500": (CONTRACTS["CFD"]("IBUS500", "SMART", "USD"), 2.0), "XYZ": (CONTRACTS["STK"]("XYZ", "LSEETF", "USD"), 5.0)}
    a = adapter(fake)
    fills = a.flatten()
    by = {f.client_id.split("-")[-1]: f for f in fills}
    assert by["SPY"].status == "filled" and by["SPY"].qty == -2.0 and by["IBKR:XYZ"].status == "rejected"
    assert [c[1:3] + c[6:] for c in fake.placed()] == [("SELL", 2.0, "IBUS500")]
    assert set(a.positions()) == {"IBKR:XYZ"}


def test_flatten_raises_while_something_of_ours_is_still_open():
    fake = FakeIB()
    fake.pos = {"R2US": (CONTRACTS["STK"]("R2US", "LSEETF", "USD"), 50.0)}
    with pytest.raises(BrokerError):                     # Londra chiusa: nulla parte, e il KILL non si dichiara riuscito
        adapter(fake).flatten()
    assert fake.placed() == []
    fake.fill_ratio = 0.0
    with pytest.raises(BrokerError):
        adapter(fake, now=LONDON).flatten()
    fake.fill_ratio = 1.0
    assert [f.status for f in adapter(fake, now=LONDON).flatten()] == ["filled"] and fake.pos["R2US"][1] == 0.0


# ------------------------------------------------------------------ mappatura
def test_shipped_map_has_no_us_listed_etf_and_nothing_marked_verified(tmp_path):
    m = load_map()
    assert {"SPY", "QQQ"} <= set(m) and not any(s["verified"] for s in m.values())
    assert all(s["sec_type"] == "CFD" or s["exchange"] not in ("SMART", "ARCA", "NYSE", "NASDAQ") for s in m.values())
    assert "EFA" not in m                                 # senza equivalente: riga vuota, ordine rifiutato
    bad = tmp_path / "m.yaml"
    bad.write_text("SPY: {symbol: SPY, sec_type: STK, exchange: ARCA, currency: USD}\n")
    with pytest.raises(ValueError, match="PRIIPs"):
        load_map(str(bad))
    bad.write_text("SPY: {symbol: CSPX, sec_type: STK, exchange: LSEETF, currency: USD}\n"
                   "IVV: {symbol: CSPX, sec_type: STK, exchange: LSEETF, currency: USD}\n")
    with pytest.raises(ValueError):
        load_map(str(bad))


def test_sessions_and_limit_price():
    assert session_open("SMART", NY_WINDOW) and not session_open("LSEETF", NY_WINDOW) and session_open("LSEETF", LONDON)
    assert not session_open("SMART", dt.datetime(2026, 11, 14, 20, 50, tzinfo=dt.timezone.utc))          # sabato
    assert limit_price("BUY", 100.0, 0.005, 0.01) == 100.5 and limit_price("SELL", 100.0, 0.005, 0.25) == 99.5
    assert limit_price("BUY", 100.03, 0.005, 0.25) == 100.5                                               # mai oltre la protezione


# ------------------------------------------------------------------ broker composito
class Stub:
    def __init__(self, name, equity, pos, known=None, broken=False):
        self.name, self.equity, self.pos, self.known, self.broken, self.sent, self.flat = name, equity, pos, known or {}, broken, [], 0

    def account(self):
        return Account(self.equity, self.equity / 2)

    def positions(self):
        return dict(self.pos)

    def prices(self, symbols):
        return {s: 1.0 for s in symbols}

    def submit(self, client_id, symbol, qty, ref_price):
        self.sent.append(symbol)
        return Fill(client_id, "filled", qty, ref_price)

    def lookup(self, client_id):
        if self.broken:
            raise BrokerError("giu'")
        return self.known.get(client_id)

    def flatten(self):
        self.flat += 1
        if self.broken:
            raise BrokerError("giu'")
        return [Fill(f"KILL-{self.name}", "filled")]


def test_composite_routes_sums_and_never_guesses():
    eq = Stub("ibkr-paper", 100.0, {"SPY": Position(1, 10)}, known={"d:SPY": Fill("d:SPY", "filled", 1, 10)})
    cr = Stub("alpaca-paper", 50.0, {"BTC": Position(2, 5)})
    c = CompositeBroker({"ibkr": eq, "crypto": cr}, lambda s: "crypto" if s in ("BTC", "ETH") else "ibkr")
    assert c.name == "ibkr-paper+alpaca-paper"
    assert c.account() == Account(150.0, 75.0) and set(c.positions()) == {"SPY", "BTC"}
    c.submit("d:BTC", "BTC", 1.0, 5.0), c.submit("d:QQQ", "QQQ", 1.0, 5.0)
    assert cr.sent == ["BTC"] and eq.sent == ["QQQ"]
    assert c.prices(["BTC", "SPY"]) == {"BTC": 1.0, "SPY": 1.0}
    assert c.lookup("d:SPY").status == "filled" and c.lookup("mai-visto") is None
    assert len(c.flatten()) == 2
    cr.broken = True
    assert c.lookup("d:SPY").status == "filled"           # chi lo conosce risponde, anche se l'altra sede e' giu'
    with pytest.raises(BrokerError):                     # nessuno lo conosce ma una sede non risponde: NON e' "mai inviato"
        c.lookup("mai-visto")
    with pytest.raises(BrokerError):
        c.flatten()
    assert eq.flat == 2                                   # la sede sana e' stata chiusa comunque
    cr.pos = {"SPY": Position(1, 1)}
    with pytest.raises(BrokerError):
        c.positions()


def test_config_accepts_ibkr_paper_and_rejects_live(tmp_path):
    from gerva.config import load
    p = tmp_path / "g.yaml"
    p.write_text("mode: ibkr-paper\nibkr: {crypto: paper}\n")
    assert load(str(p))[0].mode == "ibkr-paper"
    for bad in ("mode: live\n", "mode: ibkr\n", "mode: ibkr-live\n", "mode: ibkr-paper\nibkr: {crypto: binance}\n"):
        p.write_text(bad)
        with pytest.raises(ValueError):
            load(str(p))
