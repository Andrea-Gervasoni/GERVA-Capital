"""M1: Budget Governor, trial registry, Scorekeeper."""
import math
import sqlite3

import numpy as np
import pytest


# ---------------------------------------------------------------- Budget Governor
def test_cost_matches_price_table(firm_env):
    from firm import budget
    # 1M input + 1M output Opus 5.5 = 4 + 20 USD
    assert budget.cost_usd("claude-opus-5-5", 1_000_000, 1_000_000) == pytest.approx(24.0)
    assert budget.cost_usd("claude-haiku-5-5", 2_000_000, 0, cache_read=1_000_000) == pytest.approx(0.21)


def test_governor_blocks_downgrades_and_strikes(firm_env):
    from firm import budget, settings as S, db
    cap = S.AndreaCapability(S.ensure_token())
    S.set("budget.daily_eur", 0.10, cap)
    S.set("budget.total_eur", 0.25, cap)
    d = budget.authorize("news_analyst", "redazione", "claude-sonnet-5-5", 10_000, 1_000)
    assert d.allowed and d.model == "claude-sonnet-5-5"
    # spesa fino all'85% del tetto giornaliero -> scala verso il basso
    budget.record("news_analyst", "redazione", "anthropic", "claude-sonnet-5-5", 30_000, 2_000)
    assert budget.spent(db.today()) == pytest.approx(0.0715, rel=0.01)
    budget.record("news_analyst", "redazione", "anthropic", "claude-sonnet-5-5", 7_000, 0)
    d = budget.authorize("news_analyst", "redazione", "claude-sonnet-5-5", 1_000, 100)
    assert d.allowed and d.model == "claude-haiku-5-5"
    # oltre il tetto giornaliero -> negato
    d = budget.authorize("cro", "rischio", "claude-opus-5-5", 50_000, 5_000)
    assert not d.allowed and "giornaliero" in d.reason
    # tetto per agente
    d = budget.authorize("x", "direzione", "claude-haiku-5-5", 1000, 100, agent_daily_cap_eur=0.0)
    assert not d.allowed and "agente" in d.reason
    # sciopero manuale di Andrea
    S.set("firm.strike", True, cap)
    assert not budget.authorize("x", "direzione", "claude-haiku-5-5", 10, 10).allowed
    S.set("firm.strike", False, cap)
    # tetto totale -> sciopero automatico
    S.set("budget.daily_eur", 10.0, cap)
    d = budget.authorize("x", "direzione", "claude-opus-5-5", 100_000, 10_000)
    assert not d.allowed and "totale" in d.reason
    assert budget.on_strike()[0]
    with pytest.raises(sqlite3.IntegrityError):
        db.ex("DELETE FROM llm_calls")


def test_runway_creates_one_big_request(firm_env):
    from firm import budget, settings as S, mailbox
    cap = S.AndreaCapability(S.ensure_token())
    S.set("budget.total_eur", 1.0, cap)
    budget.record("capo", "direzione", "anthropic", "claude-opus-5-5", 100_000, 10_000)   # ~0,54 EUR oggi
    st = budget.status()
    assert st["days_left"] < 7
    assert budget.runway_check() is not None
    assert budget.runway_check() is None                         # niente spam: una al giorno
    assert mailbox.items()[0]["category"] == 3


# ---------------------------------------------------------------- Trial registry
def test_trials_counted_and_dsr_deflates(firm_env):
    from firm import trials, db
    rng = np.random.default_rng(0)
    assert trials.seed_gervaq() == 55
    c = trials.counts()
    assert c["n_trials"] == 55 and c["n_with_sharpe"] == 35
    with pytest.raises(ValueError):
        trials.register("senior_trend", "s1", "trend", {"a": 1}, "corta")
    tid = trials.register("senior_trend", "s1", "trend", {"a": 1},
                          "Il trend esiste per sotto-reazione all'informazione e per gli hedger.")
    r = rng.normal(0.0006, 0.01, 2520)
    d = trials.record_result(tid, r)
    assert d["n_trials"] == 56
    assert d["dsr"] < d["psr"]
    with pytest.raises(ValueError):
        trials.record_result(tid, r)                              # nuova variante = nuova prova
    with pytest.raises(sqlite3.IntegrityError):
        db.ex("DELETE FROM trials WHERE id=?", (tid,))
    g = trials.gate(tid, pbo=0.5)
    assert not g["passa"] and not g["controlli"]["pbo"]["ok"]
    # la stessa famiglia con gli stessi parametri non gonfia N
    tid2 = trials.register("senior_trend", "s1-bis", "trend", {"a": 1},
                           "Stessa prova ripetuta: non e' una nuova ipotesi, non deve contare due volte.")
    assert trials.counts()["n_trials"] == 56


# ---------------------------------------------------------------- Scorekeeper
def test_brier_decomposition_is_exact_on_bin_values(firm_env):
    from firm import scorekeeper as SK
    rng = np.random.default_rng(1)
    p = rng.choice([0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95], 2000)
    o = (rng.random(2000) < p).astype(int)
    c = SK.calibration(p, o)
    assert c["brier"] == pytest.approx(c["affidabilita"] - c["risoluzione"] + c["incertezza"], abs=1e-12)
    assert SK.brier([0.5] * 4, [1, 0, 1, 0]) == 0.25


def test_forecasts_frozen_and_resolved_once(firm_env):
    from firm import scorekeeper as SK, db
    fid = SK.register_forecast("head_intel", "Il CPI USA di ottobre sara' >= 3,0% a/a", 0.6, "2026-11-10",
                               "Dato BLS headline CPI-U a/a del comunicato del 10/11/2026", "bls.gov")
    with pytest.raises(sqlite3.IntegrityError):
        db.ex("UPDATE forecasts SET prob=0.99 WHERE id=?", (fid,))
    SK.resolve_forecast(fid, True, "scorekeeper")
    with pytest.raises(sqlite3.IntegrityError):
        SK.resolve_forecast(fid, False, "scorekeeper")
    st = SK.agent_forecasts("head_intel")
    assert st["risolte"] == 1 and st["giuste"] == 1
    assert st["brier"] == pytest.approx(0.16)


def test_peer_review_rules_and_composite_weights(firm_env):
    from firm import scorekeeper as SK
    with pytest.raises(ValueError):
        SK.peer_review("a", "a", {k: 3 for k in SK.RUBRIC}, "difetto concreto qualsiasi")
    with pytest.raises(ValueError):
        SK.peer_review("a", "b", {k: 3 for k in SK.RUBRIC}, "ok")
    SK.peer_review("a", "b", {k: 5 for k in SK.RUBRIC}, "Nessun difetto: ogni cifra ha fonte e data verificate.")
    SK.add_eval("b", "precisione_eventi", 0.5)
    c = SK.composite("b", "redazione")
    assert c["pari"] == pytest.approx(1.0)
    assert c["punteggio"] == pytest.approx(0.7 * c["dure"] + 0.3 * 1.0)


def test_promotion_needs_sample_and_significance(firm_env):
    from firm import scorekeeper as SK
    rng = np.random.default_rng(2)
    for _ in range(10):
        SK.add_eval("star", "precisione_eventi", 0.9)
    assert not SK.promotion_test("star", "redazione", 1, ["peer1"])["idoneo"]     # campione < 30
    for x in rng.normal(0.85, 0.05, 40):
        SK.add_eval("star", "precisione_eventi", x)
    for x in rng.normal(0.6, 0.1, 60):
        SK.add_eval("peer1", "precisione_eventi", x)
    res = SK.promotion_test("star", "redazione", 1, ["peer1"])
    assert res["idoneo"] and res["p_value"] < 0.05
    res2 = SK.promotion_test("peer1", "redazione", 1, ["star"])
    assert not res2["idoneo"]
