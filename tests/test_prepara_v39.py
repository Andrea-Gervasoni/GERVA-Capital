"""v3.9: le azioni USA a mercato aperto si mandano per la giornata (non OPG); a mercato chiuso resta OPG."""
import datetime as dt
import os
import re
import subprocess
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = '''import math, json, os
import datetime as dt
import pandas as pd


def round_to_tick(ib, c, price):
    return round(price, 2)


def place(ib, orders: pd.DataFrame):
    from ib_async import Contract, LimitOrder, MarketOrder
    trades = []
    # prima le vendite (liberano liquidita'), poi gli acquisti
    for _, o in orders.sort_values("action", ascending=False).iterrows():
        c = Contract(conId=int(o.conId), exchange="SMART")   # SMART: evita il blocco 10311 sul routing diretto
        ib.qualifyContracts(c)
        if o.kind == "stock":
            ordr = MarketOrder(o.action, int(o.qty), tif="OPG")      # market-on-open USA
        else:
            lim = o.price * (1.005 if o.action == "BUY" else 0.995)  # limite +-0.5%
            ordr = LimitOrder(o.action, int(o.qty), round_to_tick(ib, c, lim), tif="DAY")
        ordr.orderRef = "GERVA-Q"
        trades.append(ib.placeOrder(c, ordr))
    ib.sleep(3)
    return [(t.contract.symbol, t.order.action, t.order.totalQuantity, t.orderStatus.status) for t in trades]
'''


def _run(tmp_path):
    gq, out = tmp_path / "GQ", tmp_path / "out"
    gq.mkdir(); (gq / "live.py").write_text(LIVE)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "deploy", "mac", "prepara_v39.py")], capture_output=True, text=True,
                       env=dict(os.environ, GERVA_Q_PATH=str(gq), PREPARA_OUT_DIR=str(out)))
    return gq, out, r


def test_patch_is_written_applies_and_changes_only_the_opg_line(tmp_path):
    gq, out, r = _run(tmp_path)
    assert r.returncode == 0 and "OK: scritto" in r.stdout, r.stdout + r.stderr
    patch = (out / "gervaq_v3_9_ordini_seduta.patch").read_text()
    assert (gq / "live.py").read_text() == LIVE                                                         # GERVA-Q non e' toccato dallo script
    sys.path.insert(0, ROOT)
    from firm.release import apply_unified_diff
    apply_unified_diff(patch, str(gq))                                                                  # come fa `firm.py release --apply`
    new = (gq / "live.py").read_text()
    compile(new, "live.py", "exec")
    assert 'tif=("DAY" if us_market_open(ib, c) else "OPG")' in new and new.count('tif="OPG"') == 0
    assert "LimitOrder(o.action, int(o.qty), round_to_tick(ib, c, lim), tif=\"DAY\")" in new            # gli ETF restano come prima
    r2 = subprocess.run([sys.executable, os.path.join(ROOT, "deploy", "mac", "prepara_v39.py")], capture_output=True, text=True,
                        env=dict(os.environ, GERVA_Q_PATH=str(gq), PREPARA_OUT_DIR=str(out)))
    assert "gia' presente" in r2.stdout                                                                 # non si applica due volte


class _Det:
    def __init__(self, hours, tz="US/Eastern"):
        self.liquidHours, self.timeZoneId = hours, tz


class _IB:
    def __init__(self, hours, tz="US/Eastern"):
        self.d = _Det(hours, tz)

    def reqContractDetails(self, c):
        return [self.d]


def _helper(tmp_path):
    gq, out, r = _run(tmp_path)
    sys.path.insert(0, ROOT)
    from firm.release import apply_unified_diff
    apply_unified_diff((out / "gervaq_v3_9_ordini_seduta.patch").read_text(), str(gq))
    src = (gq / "live.py").read_text()
    m = re.search(r"_US_OPEN_CACHE = \{\}.*?(?=\n\ndef place)", src, re.S)
    ns = {}
    exec(m.group(0), ns)
    return ns["us_market_open"]


def test_market_open_closed_and_unknown(tmp_path):
    f = _helper(tmp_path)
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/New_York")
    now = dt.datetime.now(tz)
    fmt = "%Y%m%d:%H%M"
    seg = lambda a, b: f"{a.strftime(fmt)}-{b.strftime(fmt)}"
    c = types.SimpleNamespace(conId=1)
    assert f(_IB(seg(now - dt.timedelta(hours=1), now + dt.timedelta(hours=1))), c) is True            # dentro la sessione: aperto -> DAY
    c2 = types.SimpleNamespace(conId=2)
    assert f(_IB(seg(now - dt.timedelta(days=1, hours=7), now - dt.timedelta(days=1))), c2) is False   # sessione di ieri: chiuso -> OPG
    c3 = types.SimpleNamespace(conId=3)
    assert f(_IB(f"{now.strftime('%Y%m%d')}:CLOSED;" + seg(now + dt.timedelta(days=1), now + dt.timedelta(days=1, hours=7))), c3) is False   # festivo + domani
    c4 = types.SimpleNamespace(conId=4)

    class _Broken:
        def reqContractDetails(self, c): raise RuntimeError("TWS non risponde")
    assert f(_Broken(), c4) is False                                                                   # non si sa: come prima (OPG)
