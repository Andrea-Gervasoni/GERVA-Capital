"""Consiglio di ricerca: gli agenti propongono schede, il codice valida, esegue il backtest, conta le prove e decide."""
import json

import numpy as np
import pandas as pd
import pytest

from gerva.agents import Council, StrategySpec, default_roles, gate, validate
from gerva.agents.spec import TrialRegistry, evaluate
from gerva.strategies import book

HYP = "Gli investitori reagiscono lentamente alle notizie: i rendimenti passati continuano per alcune settimane."


class FakeLab:
    def __init__(self, drift=0.0, seed=0, n=3000):
        rng = np.random.default_rng(seed)
        idx = pd.date_range("2018-01-01", periods=n, freq="D")
        coins = ["BTC", "ETH"] + [f"C{i}" for i in range(10)]
        r = rng.normal(drift, 0.03, (n, len(coins)))
        if drift:                                         # trend persistenti: regimi lunghi di salita e discesa
            regime = np.repeat(rng.choice([-1.0, 1.5], n // 100 + 1), 100)[:n]
            r = rng.normal(0, 0.02, (n, len(coins))) + drift * regime[:, None]
        self.cclose = pd.DataFrame(100 * np.exp(np.cumsum(r, 0)), index=idx, columns=coins)
        self.cdvol = pd.DataFrame(rng.uniform(1e6, 1e8, r.shape), index=idx, columns=coins)
        self.cret = self.cclose.pct_change(fill_method=None)
        self.rf365 = pd.Series(0.0, index=idx)
        bidx = pd.bdate_range("2003-01-01", idx[-1])
        e = rng.normal(0.0002, 0.01, (len(bidx), len(book.TREND_UNIVERSE)))
        c = pd.DataFrame(50 * np.exp(np.cumsum(e, 0)), index=bidx, columns=book.TREND_UNIVERSE)
        self.P = dict(high=c * (1 + np.abs(rng.normal(0, 0.005, c.shape))), low=c * (1 - np.abs(rng.normal(0, 0.005, c.shape))),
                      close=c, adj=c)
        self.rf = pd.Series(0.0, index=bidx)


def spec(**kw):
    base = dict(family="crypto_trend", universe="BTC_ETH",
                params=dict(lookback_fast=20, lookback_slow=100, rebalance_days=7, asset_vol=0.4), hypothesis=HYP)
    base.update(kw)
    return StrategySpec(**base)


def test_validate_rejects_anything_outside_the_whitelist():
    assert validate(spec()) == []
    assert validate(spec(family="hft_magic"))
    assert validate(spec(universe="SHITCOINS"))
    assert validate(spec(params=dict(lookback_fast=20, lookback_slow=100, rebalance_days=7, asset_vol=5.0)))       # fuori limite
    assert validate(spec(params=dict(lookback_fast=20, lookback_slow=100, rebalance_days=7, asset_vol=0.4, leverage=25)))
    assert validate(spec(params=dict(lookback_fast=120, lookback_slow=100, rebalance_days=7, asset_vol=0.4)))
    assert validate(spec(params=dict(lookback_fast=20)))                                                         # mancanti
    assert validate(spec(hypothesis="funziona"))                                                                 # nessun meccanismo
    assert validate(spec(params=dict(lookback_fast=True, lookback_slow=100, rebalance_days=7, asset_vol=0.4)))


def test_gate_rejects_noise_and_accepts_a_real_edge():
    noise = evaluate(spec(), FakeLab(0.0, seed=1))
    v = gate(noise, 105)
    assert v["passa"] is False and v["motivi"]
    edge = evaluate(spec(), FakeLab(0.004, seed=2))
    ok = gate(edge, 105)
    assert edge["sharpe_scelta"] > 1.0 and ok["passa"] is True, ok["motivi"]
    assert gate(edge, 10 ** 9)["dsr"] < ok["dsr"]                      # piu' prove = soglia di fortuna piu' alta


def test_every_family_evaluates():
    lab = FakeLab(0.0, seed=3)
    for s in (spec(universe="TOP10"),
              spec(family="crypto_xsmom", universe="TOP_VOLUME", params=dict(lookback=28, top=3, universe=10, rebalance_days=7)),
              spec(family="index_ibs", universe="SPY_QQQ", params=dict(enter=0.2, exit=0.7)),
              spec(family="etf_trend", universe="MULTI_ASSET_17", params=dict(lookback_fast=63, lookback_slow=252, rebalance_days=5))):
        r = evaluate(s, lab)
        assert r["valida"] and np.isfinite(r["sharpe"]) and r["sharpe_costi_doppi"] <= r["sharpe"] + 0.05


def test_registry_is_append_only_and_tamper_evident(tmp_path):
    reg = TrialRegistry(str(tmp_path / "t.jsonl"))
    lab = FakeLab(0.0, seed=4)
    for lb in (10, 20, 20):
        s = spec(params=dict(lookback_fast=lb, lookback_slow=100, rebalance_days=7, asset_vol=0.4))
        res = evaluate(s, lab)
        reg.append(res, gate(res, 105))
    assert len(reg.rows()) == 3 and reg.count() == 2 and reg.verify()     # la stessa scheda non conta due volte
    lines = open(reg.path).read().splitlines()
    row = json.loads(lines[0])
    row["sharpe_scelta"] = 9.9                                            # qualcuno ritocca un risultato
    open(reg.path, "w").write("\n".join([json.dumps(row)] + lines[1:]) + "\n")
    assert reg.verify() is False


def test_council_code_decides_not_the_agents(tmp_path):
    lab = FakeLab(0.004, seed=2)
    c = Council(lab, str(tmp_path / "t.jsonl"))
    out = c.review(spec())
    assert out["esito"] == "AMMESSA AL PAPER TRADING" and out["difetti"] and c.reg.count() == 1
    # un critico compiacente (nessun difetto) invalida la revisione
    lazy = dict(default_roles(), critic=lambda ctx: dict(difetti=[]))
    assert Council(lab, str(tmp_path / "a.jsonl"), lazy).review(spec())["esito"] == "RESPINTA"
    # il rischio puo' solo porre il veto
    veto = dict(default_roles(), risk=lambda ctx: dict(veto=True, motivo="troppo concentrata"))
    out = Council(lab, str(tmp_path / "b.jsonl"), veto).review(spec())
    assert out["esito"] == "RESPINTA" and "veto" in " ".join(out["verdetto"]["motivi"])
    # un agente entusiasta non puo' far passare il rumore
    hype = dict(critic=lambda ctx: dict(difetti=["nessuno di rilievo"]), risk=lambda ctx: dict(veto=False, approva=True))
    assert Council(FakeLab(0.0, seed=1), str(tmp_path / "c.jsonl"), hype).review(spec())["esito"] == "RESPINTA"


def test_critic_never_sees_the_author_and_session_survives_garbage(tmp_path):
    seen = {}

    def critic(ctx):
        seen.update(ctx["result"]["spec"])
        return dict(difetti=["x"])
    c = Council(FakeLab(0.0, seed=5), str(tmp_path / "t.jsonl"), dict(default_roles(), critic=critic))
    c.review(spec(author="Il Capo"))
    assert seen["author"] == "(nascosto)"
    props = iter([dict(family="crypto_trend"), "non un dizionario" and {}, dict(spec().__dict__)])
    out = c.session(lambda ctx: next(props), rounds=3)
    assert [o["esito"] for o in out[:2]] == ["RESPINTA", "RESPINTA"] and len(out) == 3
