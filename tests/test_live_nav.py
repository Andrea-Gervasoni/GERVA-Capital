"""Valore del conto in tempo reale: connessione in sola lettura, stima tra un valore esatto e l'altro, mai ordini."""
import types

import pytest

from firm import db, ibkr


class FakeIB:
    """TWS finto: valore esatto fermo per un po', P&L che si muove."""
    def __init__(self, navs, pnls, accounts=("DU1234567",)):
        self.navs, self.pnls, self.accts, self.i = navs, pnls, list(accounts), 0
        self.pnl_obj = types.SimpleNamespace(unrealizedPnL=0.0, realizedPnL=0.0)
        self.disconnected = False

    def connect(self, *a, **k): pass
    def managedAccounts(self): return self.accts
    def reqPnL(self, acct): return self.pnl_obj
    def sleep(self, s):
        self.i += 1
        self.pnl_obj.unrealizedPnL = self.pnls[min(self.i - 1, len(self.pnls) - 1)]
    def accountValues(self, acct):
        n = self.navs[min(self.i - 1, len(self.navs) - 1)]
        return [types.SimpleNamespace(tag="NetLiquidation", currency="EUR", value=str(n))]
    def disconnect(self): self.disconnected = True
    def placeOrder(self, *a): raise AssertionError("l'osservatore non deve mai inviare ordini")


def test_estimate_moves_with_pnl_between_exact_values(firm_env):
    fake = FakeIB(navs=[1000000, 1000000, 1000000, 1002000], pnls=[100, 600, 1100, 2100])
    ibkr.live_loop(factory=lambda: fake, interval=0, max_iter=4)
    lv = db.runtime_get("ibkr.live")
    assert lv["nav_exact"] == 1002000 and lv["nav"] == 1002000        # arrivato il valore esatto nuovo: stima = esatto
    # al terzo giro: esatto fermo a 1.000.000, il P&L e' salito di 1.000 dal primo giro -> stima 1.001.000
    fake2 = FakeIB(navs=[1000000] * 3, pnls=[100, 600, 1100])
    ibkr.live_loop(factory=lambda: fake2, interval=0, max_iter=3)
    lv = db.runtime_get("ibkr.live")
    assert lv["nav_exact"] == 1000000 and abs(lv["nav"] - 1001000) < 1e-6 and lv["stima"] is True
    assert db.one("SELECT nav FROM nav_marks WHERE pod='pod_zero' AND day=?", (db.today(),))["nav"] == lv["nav"]
    assert fake2.disconnected and db.q("SELECT * FROM nav_ticks")


def test_live_loop_is_read_only_and_refuses_live_accounts(firm_env, monkeypatch):
    ro = ibkr._ReadOnlyIB(FakeIB([1e6], [0]))
    with pytest.raises(PermissionError):
        ro.placeOrder("x")
    monkeypatch.delenv("IBKR_CHALLENGE_ACCOUNT", raising=False)
    live_acct = FakeIB([1e6], [0], accounts=("U7654321",))              # conto vero: si rifiuta
    ibkr.live_loop(factory=lambda: live_acct, interval=0, max_iter=1, retry=0, sleep=lambda s: None)
    assert "paper" in db.runtime_get("ibkr.live")["errore"] and not db.q("SELECT * FROM nav_ticks")


def test_live_state_freshness(firm_env):
    from portal import app as A
    db.runtime_set("ibkr.live", dict(ts=db.now_iso(), nav=1.0, nav_exact=1.0, stima=False))
    assert A._live_state()["fresca"] is True
    db.runtime_set("ibkr.live", dict(ts="2020-01-01T00:00:00Z", nav=1.0, nav_exact=1.0, stima=False))
    assert A._live_state()["fresca"] is False


class FakeEvent:
    def __init__(self): self.callbacks=[]
    def __iadd__(self,f): self.callbacks.append(f); return self
    def __isub__(self,f): self.callbacks.remove(f); return self
    def emit(self,*args):
        for f in self.callbacks[:]: f(*args)


@pytest.mark.parametrize('code',[1100,1101,1300])
def test_upstream_loss_reconnects_without_accepting_cached_nav(firm_env,code):
    class EventIB(FakeIB):
        def __init__(self):
            super().__init__([1e6],[0])
            self.errorEvent,self.accountValueEvent,self.pnlEvent=FakeEvent(),FakeEvent(),FakeEvent()
        def sleep(self,s):
            super().sleep(s)
            self.errorEvent.emit(-1,code,'upstream disconnected')
    bad=EventIB(); good=FakeIB([1001000],[0]); instances=iter([bad,good]); waits=[]
    ibkr.live_loop(factory=lambda:next(instances),interval=0,max_iter=3,sleep=waits.append)
    assert bad.disconnected and good.disconnected
    assert not bad.errorEvent.callbacks
    assert len(waits)==1
    assert db.runtime_get('ibkr.live')['nav']==1001000
    assert not db.runtime_get('ibkr.live').get('errore')
