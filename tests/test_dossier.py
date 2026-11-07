"""Dossier: le prove di ogni operazione salvate prima dell'esito, e la revisione pro/contro della sera."""
import datetime as dt
import os

import numpy as np
import pandas as pd

from firm import blotter as B, db, dossier as D, org_seed, paths, registry


def _prices():
    n = 600
    idx = pd.bdate_range(end=dt.date.today(), periods=n)
    rng = np.random.default_rng(9)
    df = pd.DataFrame({"SPY": 400 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, n))), "BTC": 30000 * np.exp(np.cumsum(rng.normal(0.001, 0.03, n))),
                       "^VIX": np.full(n, 18.0)}, index=idx)
    os.makedirs(os.path.join(paths.VAR, "data"), exist_ok=True)
    df.to_pickle(os.path.join(paths.VAR, "data", "gq4_close.pkl"))
    D._CACHE.clear()
    return df


def test_every_fill_gets_its_evidence_before_the_outcome(firm_env):
    _prices()
    B.record("alpaca", "x1", "2026-11-09T15:00:00Z", "BTC", "buy", 0.1, 60000, 0, "USD", "eseguito", "1", dict(kind="modello"))
    d = D.get("x1")
    assert d and d["indicatori"]["rsi"] is not None and d["previsione"]["ok"] and 0 <= d["previsione"]["condizionata"]["p_sale"] <= 1
    assert d["previsione"]["condizionata"]["casi"] > 50 and d["regime"]
    B.record("alpaca", "x1", "2026-11-09T15:00:00Z", "BTC", "buy", 0.1, 60000, 0, "USD", "eseguito", "1", dict(kind="modello"))
    assert db.one("SELECT COUNT(*) n FROM dossiers")["n"] == 1                       # una volta sola


def test_evening_review_writes_pro_and_contra_and_story_shows_it(firm_env, monkeypatch):
    org_seed.seed(); registry.sync(); _prices()
    B.record("alpaca", "y1", "2026-11-09T15:00:00Z", "BTC", "buy", 0.1, 60000, 0, "USD", "eseguito", "1", dict(kind="modello"))
    import llm.runtime as rt

    def call(agent, task, data=None, schema=None, purpose="", **k):
        return dict(ok=True, output=dict(valutazioni=[dict(chiave=data["operazioni"][0]["chiave"], argomento=f"{agent}: RSI e trend", indicatori_usati=["RSI", "EMA200"], probabilita_guadagno=0.55)]))
    monkeypatch.setattr(rt, "call", call)
    assert D.review_daily()["riviste"] == 1
    rev = D.get("y1")["revisione"]
    assert rev["pro"][0]["agente"] == "pod_trend" and rev["contro"][0]["agente"] == "cro" and rev["pro"][0]["indicatori"] == ["RSI", "EMA200"]
    st = B.story(B.trades()[0]["chiave"])
    assert st["dossier"]["revisione"] and st["grafico"]["close"] and st["grafico"]["segni"][0]["tipo"] == "ingresso"
