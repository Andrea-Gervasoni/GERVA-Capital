"""Aspettative scritte prima e confrontate dopo: append-only, percentile del conto reale, previsioni del Capo valutate."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from firm import db, expectations as X


def _close(n=1500, seed=2):
    idx = pd.bdate_range("2019-01-01", periods=n)
    rng = np.random.default_rng(seed)
    px = lambda mu, sd: 100 * np.exp(np.cumsum(rng.normal(mu, sd, n)))
    return pd.DataFrame({"SPY": px(0.0004, 0.010), "AAA": px(0.0006, 0.018), "^IRX": np.full(n, 3.0)}, index=idx)


def _reg(nav0=1_000_000):
    return X.register(nav0=nav0, weights=dict(SPY=0.7, AAA=0.5), close=_close())


def test_register_is_frozen_and_versioned(firm_env):
    r1 = _reg()
    e = X.latest()
    assert e["hash"] == r1["hash"] and e["versioni"] == 1
    for fan in (e["modello"], e["realistico"]):
        assert all(fan["5"][i] <= fan["50"][i] <= fan["95"][i] for i in range(len(fan["5"])))
        assert fan["50"][0] == 1_000_000
    assert e["realistico"]["finale"]["50"] < e["modello"]["finale"]["50"]          # il caso realistico e' piu' prudente
    with pytest.raises(Exception):                                                   # append-only: non si riscrive
        db.ex("UPDATE expectations SET nav0=1 WHERE id=?", (r1["id"],))
    r2 = _reg(1_100_000)
    assert X.latest()["versioni"] == 2 and r2["id"] != r1["id"]
    assert db.one("SELECT nav0 FROM expectations WHERE id=?", (r1["id"],))["nav0"] == 1_000_000


def test_percentile_of_the_real_account(firm_env):
    _reg()
    e = X.latest()
    t0 = e["ts"][:19]
    db.ex("INSERT INTO nav_ticks(ts,nav) VALUES(?,?)", (t0, 1_000_000))
    db.runtime_set("ibkr.live", dict(ts=db.now_iso(), nav=1_000_000.0, nav_exact=1_000_000.0, stima=False))
    ov = X.overview()
    assert ov["registrata"] and 20 <= ov["stato"]["realistico"]["percentile"] <= 80          # appena partito: al centro
    assert len(ov["date"]) == len(ov["modello"]["50"]) and ov["realizzato"][-1]["v"] == 1_000_000
    db.runtime_set("ibkr.live", dict(ts=db.now_iso(), nav=700_000.0, nav_exact=700_000.0, stima=False))
    ov = X.overview()
    assert ov["stato"]["realistico"]["percentile"] < 5 and "sotto" in ov["stato"]["realistico"]["lettura"]
    assert ov["rendimento_dal_via"] < -0.25


def test_overview_before_registration(firm_env):
    assert X.overview()["registrata"] is None


def test_outlook_validation_and_brier(firm_env):
    ok = X.validate_outlook([dict(orizzonte_giorni=7, p_sopra=0.6, mediana_pct=0.004), dict(orizzonte_giorni=3, p_sopra=0.6, mediana_pct=0.0),
                             dict(orizzonte_giorni=30, p_sopra=1.5, mediana_pct=0.0), dict(orizzonte_giorni=30, p_sopra=0.55, mediana_pct=0.9)])
    assert [o["orizzonte"] for o in ok] == [7]                                      # orizzonte sbagliato, probabilita' o rendimento folli: scartati
    db.ex("INSERT INTO nav_ticks(ts,nav) VALUES('2026-11-14T10:00:00Z', 1020000)")
    db.ex("INSERT INTO outlooks(ts,agent_id,horizon_days,deadline,nav0,p_up,median_pct) VALUES('2026-11-07T08:00:00Z','capo',7,'2026-11-14',1000000,0.7,0.01)")
    n = X.resolve_outlooks(dt.datetime(2026, 11, 15, tzinfo=dt.timezone.utc))
    o = db.one("SELECT * FROM outlooks")
    assert n == 1 and o["outcome"] == 1 and abs(o["realized_pct"] - 0.02) < 1e-9 and abs(o["brier"] - 0.09) < 1e-9
    assert X.brier_summary()["risolte"] == 1
