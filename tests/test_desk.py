"""Desk: gli agenti propongono, il codice valida; nessuna proposta puo' superare i tetti ne' uscire dalla tabella."""
import datetime as dt
import json

from firm import desk, db, org_seed, registry


def test_merge_applies_all_caps():
    allowed = {"NVDA", "AMD", "XOM", "COP"}
    by = {"d1": [dict(simbolo="NVDA", peso_pct=50), dict(simbolo="FAKE", peso_pct=5), dict(simbolo="AMD", peso_pct=-3)],
          "d2": [dict(simbolo="NVDA", peso_pct=4), dict(simbolo="XOM", peso_pct=4), dict(simbolo="COP", peso_pct=4)],
          "d3": []}
    r = desk.merge(by, allowed, dict(max_name=0.05, max_total=0.09))
    t = r["targets"]
    assert max(t.values()) <= 0.05 + 1e-9                    # tetto per titolo
    assert sum(t.values()) <= 0.09 + 1e-9                    # tetto complessivo
    assert "FAKE" not in t and "AMD" not in t                # fuori tabella / peso negativo
    assert {x["simbolo"] for x in r["scartate"]} == {"FAKE", "AMD"}


def test_cycle_writes_overlay_within_caps(firm_env, monkeypatch):
    org_seed.seed(); registry.sync()
    rows = [dict(simbolo=s, r1m=0.01, r3m=0.05, r12m=0.2, vol=0.3, vs_media200=0.1) for s in ("NVDA", "XOM", "COP")]
    monkeypatch.setattr(desk, "table", lambda *a, **k: rows)
    from llm import runtime

    def fake(agent, task, **kw):
        assert "_reale" in kw["data"] and "tabella" in kw["data"]
        return dict(ok=True, output=dict(proposte=[dict(simbolo="NVDA", peso_pct=80, motivo="m"),
                                                    dict(simbolo="ZZZZ", peso_pct=5, motivo="m")], nota="n"))
    monkeypatch.setattr(runtime, "call", fake)
    r = desk.cycle(dt.date(2026, 11, 6))
    assert r["ok"]
    doc = json.load(open(desk.overlay_path()))
    assert doc["data"] == "2026-11-06"
    assert doc["targets"] == {"NVDA": 0.05}                  # 80% proposto, tetto del 5% per titolo
    assert db.runtime_get("desk.overlay")["targets"] == {"NVDA": 0.05}


def test_cycle_without_market_data_does_nothing(firm_env, monkeypatch):
    monkeypatch.setattr(desk, "table", lambda *a, **k: [])
    assert "mancano i dati" in desk.cycle()["nota"]


def test_profile_changes_reach_the_db_after_pull(firm_env):
    import yaml
    from firm import paths
    org_seed.seed(); registry.sync()
    assert registry.sync_if_profiles_changed() is True          # prima volta: registra l'impronta
    assert registry.sync_if_profiles_changed() is False         # niente di nuovo
    f = f"{paths.AGENTS}/pod_trend/profile.yaml"
    prof = yaml.safe_load(open(f)); prof["daily_budget_eur"] = 1.5
    yaml.safe_dump(prof, open(f, "w"), allow_unicode=True, sort_keys=False)
    assert registry.sync_if_profiles_changed() is True
    assert registry.get("pod_trend")["daily_budget_eur"] == 1.5


def test_pace_bounds_and_choice(firm_env, monkeypatch):
    from firm import desk, db
    assert desk.pace_bounds(0.95)[1] == 0.50 and desk.pace_bounds(0.8)[1] == 0.75 and desk.pace_bounds(0.3)[1] == 1.0
    monkeypatch.setattr("firm.charts.regime", lambda *a, **k: dict(vix_percentile=0.95))
    monkeypatch.setattr("firm.fundrisk.portfolio", lambda *a, **k: dict(lordo=1.5, leva=0.5))
    import llm.runtime as rt
    monkeypatch.setattr(rt, "call", lambda *a, **k: dict(ok=True, output=dict(ritmo_pct=90.0, motivo="prova")))      # il Capo vorrebbe 90%
    r = desk.refresh_pace()
    assert r["max_turnover"] == 0.5 and r["fonte"] == "Capo"                                                       # il codice lo porta al massimo della fascia
    monkeypatch.setattr(rt, "call", lambda *a, **k: dict(ok=False, motivo="giu"))
    assert desk.refresh_pace()["max_turnover"] == 0.33                                                             # senza Capo: predefinito
    assert db.runtime_get("desk.overlay")["max_turnover"] == 0.33
