"""Comitato di lungo periodo: decide titolo per titolo, puo' solo rinviare, non va oltre il calendario."""
import datetime as dt
import json

import numpy as np
import pandas as pd


def _market(days=300, seed=0, crash=None):
    from firm import lt_committee as LC
    idx = pd.bdate_range(end="2026-11-06", periods=days)
    rng = np.random.default_rng(seed)
    syms = LC.symbols()
    close = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.02, (days, len(syms))), axis=0)), index=idx, columns=syms)
    if crash:
        close.loc[idx[-2]:, crash] *= 0.7                     # -30% in un giorno
    volume = pd.DataFrame(5e6, index=idx, columns=syms)
    return close, volume


def test_calendar_and_checks(firm_env):
    from firm import lt_committee as LC
    assert LC.calendar_fraction(dt.date(2026, 11, 8)) == 0
    assert LC.calendar_fraction(dt.date(2026, 12, 9)) == 2 / 3
    close, vol = _market(crash="NBIS")
    p = LC.evaluate(close, vol, today=dt.date(2026, 11, 9))
    assert p["frazioni"]["NVDA"] == 1 / 3 and p["frazioni"]["NBIS"] == 0.0
    assert "crollo" in p["rinvii"]["NBIS"][0]
    saved = json.load(open(LC.plan_path()))
    assert saved["frazioni"]["NVDA"] == 1 / 3 and saved["data"] == "2026-11-09"


def test_low_liquidity_and_suspension_postpone(firm_env, monkeypatch):
    from firm import lt_committee as LC
    close, vol = _market(seed=1)
    vol["CRDO"] = 10.0                                         # scambi irrisori
    cfg = LC.config(); cfg["sospesi"] = ["GEV"]
    monkeypatch.setattr(LC, "config", lambda: cfg)
    p = LC.evaluate(close, vol, today=dt.date(2026, 11, 9))
    assert p["frazioni"]["CRDO"] == 0 and p["frazioni"]["GEV"] == 0
    assert any("sospeso" in w for w in p["rinvii"]["GEV"])


def test_agents_can_only_postpone(firm_env, monkeypatch):
    from firm import lt_committee as LC
    close, vol = _market(seed=2)
    monkeypatch.setattr(LC, "_agents_vote", lambda cand, data: dict(tenuta=True, decisione="rinvia", riunione=7))
    p = LC.evaluate(close, vol, today=dt.date(2026, 11, 9))
    assert all(f == 0 for f in p["frazioni"].values())         # la riunione ha rinviato tutta la rata
    monkeypatch.setattr(LC, "_agents_vote", lambda cand, data: dict(tenuta=True, decisione="compra", riunione=8))
    p2 = LC.evaluate(close, vol, today=dt.date(2026, 11, 9))
    assert max(p2["frazioni"].values()) == 1 / 3               # mai oltre il calendario
