"""Diagnosi in sola lettura dei dati di mercato di IBKR: distingue 'tempo reale', 'solo ritardati' e 'nessun dato'."""
import math

from firm import ibkr


class _Ev(list):
    def __iadd__(self, f):
        self.append(f); return self


class _T:
    def __init__(self, last=None, bid=None, ask=None, close=None, mdt=1):
        self.last, self.bid, self.ask, self.close, self.marketDataType = last, bid, ask, close, mdt


class FakeIB:
    """Cosa risponde IBKR: AMD solo ritardati (con errore 10167), AAPL tempo reale, ZZZ niente."""
    def __init__(self):
        self.errorEvent, self.mtype, self.connected = _Ev(), 1, False

    def connect(self, *a, **k): self.connected = True
    def disconnect(self): self.connected = False
    def qualifyContracts(self, c): return [c]
    def reqMarketDataType(self, t): self.mtype = t
    def sleep(self, s): pass
    def cancelMktData(self, c): pass

    def reqMktData(self, c, *a):
        if c.symbol == "AAPL":
            return _T(200.0, 199.9, 200.1, 199.0, 1)
        if c.symbol == "AMD":
            if self.mtype == 1:
                for f in self.errorEvent:
                    f(5, 10167, "Requested market data is not subscribed. Displaying delayed market data.", None)
                return _T(math.nan, math.nan, math.nan, math.nan, 1)
            return _T(472.0, 471.9, 472.1, 470.0, 3)
        return _T(math.nan, -1, math.nan, math.nan, 1)


class _Stock:
    def __init__(self, symbol, exch, cur): self.symbol = symbol


def test_probe_tells_delayed_from_live_from_nothing():
    r = ibkr.probe_market_data(("AAPL", "AMD", "ZZZ"), factory=FakeIB, stock=_Stock, wait=0)
    assert r["AAPL"]["lettura"] == "prezzi in tempo reale disponibili" and r["AAPL"]["tempo_reale"]["ultimo"] == 200.0
    assert r["AMD"]["lettura"].startswith("SOLO prezzi ritardati") and r["AMD"]["ritardati"]["ultimo"] == 472.0
    assert r["AMD"]["tempo_reale"]["errori"][0]["codice"] == 10167                                   # l'errore di IBKR e' riportato
    assert r["ZZZ"]["lettura"].startswith("nessun prezzo")


def test_probe_never_places_orders():
    assert not hasattr(FakeIB, "placeOrder")
    import inspect
    assert "placeOrder" not in inspect.getsource(ibkr.probe_market_data)
