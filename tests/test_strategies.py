"""Strategie dai paper: niente sguardo nel futuro, costi che pesano, backtest registrato e portato al comitato, accensione per voto."""
import datetime as dt

import numpy as np
import pandas as pd

from firm import crypto_venue as V, db, ideas as ID, org_seed, registry, settings as S, strategies as ST


def _crypto(n=24 * 200, trend=0.0004, seed=3):
    idx = pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(seed)
    out = {}
    for i, c in enumerate(["BTC", "ETH", "SOL"]):
        regime = np.sign(np.sin(np.arange(n) / (300 + 50 * i)))                 # fasi di trend su e giu' (il momentum le segue)
        out[c] = 100 * np.exp(np.cumsum(regime * trend + rng.normal(0, 0.006, n)))
    return pd.DataFrame(out, index=idx)


def _spy(days=90, edge=0.002, seed=4):
    rng = np.random.default_rng(seed)
    rows, px = [], 400.0
    for d in pd.bdate_range("2025-03-03", periods=days):
        t0 = pd.Timestamp(d.date()).tz_localize("America/New_York") + pd.Timedelta(hours=9, minutes=30)
        first, prev_close = None, px
        for k in range(78):                                                      # 9:30 -> 15:55, barre da 5 minuti
            t = t0 + pd.Timedelta(minutes=5 * k)
            step = rng.normal(0, 0.0008)
            if k == 6:
                first = px / prev_close - 1                                      # dalla chiusura di ieri alle 10:00
            if k >= 72 and first is not None:                                    # ultima mezz'ora nella direzione della prima
                step += np.sign(first) * edge / 6
            o = px; px = px * (1 + step); rows.append((t, px, o))
    df = pd.DataFrame(rows, columns=["t", "c", "o"]).set_index("t")
    df.index = df.index.tz_convert("UTC")
    return df


def test_tsmom_has_no_look_ahead_and_is_long_only():
    c = _crypto()
    w1 = ST.tsmom_weights(c, ST.STRATS["crypto_tsmom"]["params"] | dict(coins=list(c)))
    c2 = c.copy(); c2.iloc[-100:] *= 3                                           # cambio il futuro...
    w2 = ST.tsmom_weights(c2, ST.STRATS["crypto_tsmom"]["params"] | dict(coins=list(c)))
    assert np.allclose(w1.iloc[:-100].values, w2.iloc[:-100].values)             # ...il passato non cambia
    assert (w1.values >= 0).all() and (w1.sum(axis=1) <= 1 + 1e-9).all()         # solo long, mai oltre il capitale


def test_costs_matter_and_trend_is_captured():
    c = _crypto()
    p = ST.STRATS["crypto_tsmom"]["params"] | dict(coins=list(c))
    d0 = ST.to_daily(ST.bt_crypto_tsmom(c, dict(p, cost_bps=0)))
    d1 = ST.to_daily(ST.bt_crypto_tsmom(c, dict(p, cost_bps=100)))
    assert ST.stats(d0)["sharpe"] > ST.stats(d1)["sharpe"] and ST.stats(d0)["sharpe"] > 0


def test_spy_intraday_momentum_backtest_reads_the_right_times():
    b = _spy()
    d = ST.bt_spy_intraday(b, dict(cost_bps=0.0))
    assert len(d) >= 80 and d.mean() > 0                                         # l'effetto messo nei dati viene trovato
    assert ST.bt_spy_intraday(_spy(edge=0.0), dict(cost_bps=2.0)).mean() < d.mean()


def test_backtest_goes_to_the_committee_and_a_vote_turns_it_on(firm_env, monkeypatch):
    org_seed.seed(); registry.sync()
    c = _crypto()
    monkeypatch.setitem(ST.STRATS["crypto_tsmom"]["params"], "coins", list(c))
    r = ST.backtest("crypto_tsmom", data=c)
    assert r["ok"] and r["prova"].startswith("T-") and "sharpe" in r["risultati"] and r["idea"]
    i = ID.get(r["idea"])
    assert i["status"] == "al_comitato" and i["azione"]["chiave"] == "algo.crypto_tsmom.on" and "Liu & Tsyvinski" in i["tesi"]
    assert ST.backtest("crypto_tsmom", data=c).get("idea") is None               # gia' al comitato: non si duplica
    import llm.runtime as rt

    def call(agent, task, data=None, schema=None, purpose="", **k):
        if purpose.endswith(":replica"):
            return dict(ok=True, output=dict(replica="si", posizione_finale="approva", fiducia=0.7))
        return dict(ok=True, output=dict(posizione="approva", argomento="a", evidenza=["x"], fiducia=0.7, cambierei_idea_se="b"))
    monkeypatch.setattr(rt, "call", call)
    out = ID.committee()
    assert out and out[0]["stato"] == "applicata" and ST.enabled("crypto_tsmom")
    t = ST.live_crypto(close=c)
    assert t["obiettivi"] and abs(sum(t["obiettivi"].values()) - sum(t["obiettivi"].values())) < 1e-12
    S.set("crypto.venue_mirror_model", False, S.AndreaCapability(S.ensure_token()))
    db.runtime_set("desk.overlay", dict(crypto_targets={}))
    assert V.targets() == {k: v for k, v in t["obiettivi"].items()}             # il ribilanciamento di Alpaca le esegue


def test_strategies_api(firm_env):
    from fastapi.testclient import TestClient
    org_seed.seed(); registry.sync()
    from portal.app import app
    j = TestClient(app).get("/api/strategies").json()
    assert set(j) == {"crypto_tsmom", "spy_intraday_momentum"} and j["crypto_tsmom"]["accesa"] is False
