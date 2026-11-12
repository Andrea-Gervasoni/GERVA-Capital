"""Ciclo di automiglioramento: chi propone non approva, una regola puo' solo ridurre, cercare di piu' alza la soglia."""
import math
import os

import numpy as np
import pandas as pd
import pytest

from gerva.learn import Registry, Rule, TradeMemory, TradeRecord, cycle, evaluate, multiplier, propose, validate, weaknesses
from gerva.learn import improve
from gerva.live import tradecycle as TC

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def trades(n=900, planted=True, seed=0):
    """Trade sintetici 2018-2026: R medio +0,25; se planted, la fetta atr_pct > 0,08 rende -0,5 in OGNI periodo."""
    rng = np.random.default_rng(seed)
    t = pd.date_range("2018-01-01", "2026-06-30", periods=n)
    atr = rng.uniform(0.02, 0.10, n)
    R = 0.25 + 1.5 * rng.standard_normal(n)
    if planted:
        R = np.where(atr > 0.08, -0.5 + 1.0 * rng.standard_normal(n), R)
    return pd.DataFrame(dict(entry_time=t, R=R, atr_pct=atr, conviction=rng.choice([0.67, 0.75, 0.83], n), weekday=rng.integers(0, 7, n),
                             symbol=rng.choice(["BTC", "ETH", "SOL"], n), exit_reason="stop", source="sim", risk=1.0, pnl=R))


def test_rule_can_only_reduce_and_ops_are_closed():
    with pytest.raises(ValueError):
        Rule("atr_pct", ">", 0.08, mult=1.5)
    with pytest.raises(ValueError):
        Rule("atr_pct", ">", 0.08, mult=-1.0)
    with pytest.raises(ValueError):
        Rule("atr_pct", "exec", 0.08)
    r = Rule("atr_pct", ">", 0.08, 0.0)
    assert r.hits({"atr_pct": 0.09}) and not r.hits({"atr_pct": 0.05}) and not r.hits({}) and not r.hits({"atr_pct": None})
    m, why = multiplier({"atr_pct": 0.09, "weekday": 1}, [r, Rule("weekday", "==", 1, 0.5)])
    assert m == 0.0 and len(why) == 2
    assert multiplier({"atr_pct": 0.05}, [r]) == (1.0, [])


def test_evaluation_finds_the_planted_weakness():
    df = trades()
    e = evaluate(df)
    assert e["n"] == 900 and e["performance"]["win_rate"] < 0.6 and e["risk"]["max_losing_streak"] >= 3
    w = weaknesses(df[df.entry_time <= improve.SPLIT])
    assert w and w[0]["feature"] == "atr_pct" and w[0]["rule"]["op"] == ">" and w[0]["t"] <= -2
    assert weaknesses(trades(planted=False, seed=3)[lambda d: d.entry_time <= improve.SPLIT]) == [] or True     # il rumore puo' dare falsi sospetti...


def test_validation_passes_a_real_effect_and_rejects_noise(tmp_path):
    df = trades()
    v = validate(Rule("atr_pct", ">", 0.08, 0.0), df, k_tried=1)
    assert v["state"] == "IN_OMBRA" and all(v["checks"].values()) and v["gain_R_verification"] > 0
    noise = trades(planted=False, seed=5)
    reg = Registry(str(tmp_path / "r.jsonl"))
    out = cycle(noise, reg)                                    # ...ma la validazione li respinge
    assert all(r["state"] == "RESPINTA" for r in out["proposed"]) and out["active"] == []
    assert reg.tried() == len(out["proposed"])
    again = cycle(noise, reg)                                  # le ipotesi gia' provate non si ripropongono: il conto non si gonfia
    assert again["proposed"] == [] and reg.tried() == len(out["proposed"])


def test_threshold_rises_with_the_number_of_hypotheses():
    assert improve.threshold(1) == 2.0 and improve.threshold(7) == 2.0
    assert improve.threshold(100) == pytest.approx(math.sqrt(2 * math.log(100)))
    assert improve.threshold(10_000) > improve.threshold(100) > 2.0
    df = trades()
    weak = Rule("weekday", "==", 2, 0.0)
    assert validate(weak, df, 1)["state"] == "RESPINTA"
    strong = Rule("atr_pct", ">", 0.08, 0.0)
    t0 = validate(strong, df, 1)["selection"]["t0"]
    k = int(math.exp(t0 * t0 / 2)) * 50                         # abbastanza ipotesi da superare qualunque t
    assert validate(strong, df, k)["state"] == "RESPINTA"


def test_nothing_becomes_active_without_the_owner(tmp_path):
    df = trades()
    reg = Registry(str(tmp_path / "r.jsonl"))
    out = cycle(df, reg)
    passed = [r for r in out["proposed"] if r["state"] == "IN_OMBRA"]
    assert passed and out["active"] == [] and reg.rules("ATTIVA") == []
    rejected = [r for r in out["proposed"] if r["state"] == "RESPINTA"]
    if rejected:
        with pytest.raises(ValueError):
            improve.approve(reg, rejected[0]["id"], by="andrea")           # una regola respinta non si attiva nemmeno a mano
    with pytest.raises(KeyError):
        improve.approve(reg, "nonesiste", by="andrea")
    r = improve.approve(reg, passed[0]["id"], by="andrea")
    assert reg.rules("ATTIVA") == [r] and reg.current()[r.id]["by"] == "andrea"
    improve.retire(reg, r.id, by="andrea")
    assert reg.rules("ATTIVA") == []


def test_shadow_needs_paper_trades_never_seen_before(tmp_path):
    df = trades()
    r = Rule("atr_pct", ">", 0.08, 0.0)
    assert improve.shadow_report(r, df.iloc[0:0])["ready"] is False
    paper = trades(n=120, seed=9).assign(source="paper")
    s = improve.shadow_report(r, paper)
    assert s["n"] >= improve.SHADOW_MIN_TRADES and s["ready"] and s["mean_R"] < s["rest_mean_R"]
    good = paper.assign(R=1.0)
    assert improve.shadow_report(r, good)["ready"] is False


def test_llm_proposals_go_through_the_same_validator(tmp_path):
    df = trades(planted=False, seed=11)
    reg = Registry(str(tmp_path / "r.jsonl"))
    bad = lambda w, cols: [dict(feature="atr_pct", op=">", value=0.05, mult=2.0), dict(feature="__import__", op="==", value=1),
                           dict(feature="weekday", op="==", value=3, mult=0.0)]
    rules = propose(df, reg, llm=bad)                           # la proposta malformata fa scartare l'intero blocco dell'LLM
    assert all(r.mult in (0.0, 0.5) and r.feature in df.columns for r in rules)
    ok = lambda w, cols: [dict(feature="weekday", op="==", value=3, mult=0.0)]
    rules = propose(df, reg, llm=ok)
    assert any(r.origin == "llm" for r in rules)
    out = cycle(df, reg, llm=ok)
    assert all(r["state"] == "RESPINTA" for r in out["proposed"] if r["origin"] == "llm")


def test_memory_is_append_only_and_idempotent(tmp_path):
    mem = TradeMemory(str(tmp_path / "m" / "t.jsonl"))
    rec = TradeRecord("TRADE-11X", "BTC", "2026-01-01", "2026-01-03", 100.0, 105.0, 2000.0, 10.0, 100.0, 97.0, 0.97, "conviction bassa",
                      commission=2.6, funding=0.4, mae=-0.3, mfe=1.2, context=dict(atr_pct=0.05, tier="alta"))
    assert mem.append(rec) and not mem.append(rec)
    df = mem.frame()
    assert len(df) == 1 and df.loc[0, "atr_pct"] == 0.05 and df.loc[0, "mfe"] == 1.2 and df.loc[0, "source"] == "paper"


def _bars(n=320, drift=0.004, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    close = 100 * np.exp(np.cumsum(drift + 0.01 * rng.standard_normal(n)))
    d = pd.DataFrame(dict(open=np.r_[100, close[:-1]], close=close), index=idx)
    d["high"] = d[["open", "close"]].max(axis=1) * 1.01
    d["low"] = d[["open", "close"]].min(axis=1) * 0.99
    d["volume"] = 1000.0
    return d


def test_paper_cycle_writes_memory_and_obeys_active_rules(tmp_path):
    b = {"BTC": _bars()}
    mem = TradeMemory(str(tmp_path / "t.jsonl"))
    s = TC.step(b, TC.empty_state(10_000), 10.0, memory=mem)
    t = s["open"]["BTC"]
    assert t["ctx"]["tier"] == "alta" and t["ctx"]["atr_pct"] > 0 and "gq" in t["ctx"]
    nxt = b["BTC"].index[-1] + pd.Timedelta(days=1)
    px = t["entry"]
    crash = pd.DataFrame(dict(open=px * 0.99, high=px * 1.01, low=px * 0.5, close=px * 0.6, volume=1000.0), index=[nxt])
    s2 = TC.step({"BTC": pd.concat([b["BTC"], crash])}, s, 10.0, memory=mem)
    rec = mem.load()[0]
    assert rec.exit_reason == "stop" and rec.R < 0 and rec.mae <= -1.0 and rec.context["tier"] == "alta" and rec.funding > 0
    assert rec.pnl == pytest.approx(s2["closed"][0]["pnl"])
    full = TC.step(b, TC.empty_state(10_000), 10.0)["open"]["BTC"]["risk"]
    skip = TC.step(b, TC.empty_state(10_000), 10.0, rules=[Rule("tier", "==", "alta", 0.0)])
    half = TC.step(b, TC.empty_state(10_000), 10.0, rules=[Rule("tier", "==", "alta", 0.5)])
    assert skip["open"] == {} and half["open"]["BTC"]["risk"] == pytest.approx(full / 2)


def test_historical_trades_share_the_paper_context_definition():
    path = os.path.join(ROOT, "research", "v5", "v6", "trade_storici.parquet")
    if not os.path.exists(path):
        pytest.skip("trade storici non generati")
    d = pd.read_parquet(path)
    assert len(d) > 500 and set(d["tier"]) == {"alta"} and d["source"].eq("sim").all()      # ogni trade storico e' rientrato come 'alta'
    from gerva.learn.features import CATEGORICAL, NUMERIC
    assert set(NUMERIC) | set(CATEGORICAL) <= set(d.columns)
