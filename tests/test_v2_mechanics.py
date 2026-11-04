"""v2: compensi con differito e clawback, regola propria, edificio monotono, uffici per grado, riunioni, report."""
import json

import numpy as np
import pytest


@pytest.fixture()
def org(firm_env):
    from firm import org_seed, registry, pods
    org_seed.seed(); registry.sync(); pods.ensure_pods()
    return firm_env


def test_bonus_vests_after_28_days_and_clawback_wipes_unvested(org):
    from firm import compensation as C, economy as E
    C.award_bonus("pod_trend", 50, "test", today="2026-11-01")
    C.award_bonus("pod_trend", 30, "test2", today="2026-11-20")
    assert E.gc_balance("pod_trend") == 0 and E.gc_unvested("pod_trend") == 80
    assert C.vest("2026-11-28") == 0
    assert C.vest("2026-11-29") == 1
    assert E.gc_balance("pod_trend") == 50 and E.gc_unvested("pod_trend") == 30
    assert C.vest("2026-11-29") == 0                       # nessuna doppia maturazione
    assert C.clawback("pod_trend", "errore grave") == 30
    assert E.gc_unvested("pod_trend") == 0 and E.gc_balance("pod_trend") == 50
    assert C.vest("2027-01-01") == 0                       # il clawback chiude la voce per sempre


def test_reward_rule_is_proper():
    from firm.compensation import proper_reward
    for q in (0.2, 0.5, 0.8):          # probabilita' vera
        grid = np.linspace(0, 1, 101)
        exp = [q * proper_reward(p, True) + (1 - q) * proper_reward(p, False) for p in grid]
        assert abs(grid[int(np.argmax(exp))] - q) < 0.011


def test_salaries_once_per_week(org):
    from firm import compensation as C, economy as E
    assert C.pay_salaries("2026-11-08") > 0
    assert C.pay_salaries("2026-11-08") == 0
    assert E.gc_balance("capo") == C.BASE_WEEKLY_GC[6]


def test_severe_postmortem_triggers_clawback(org):
    from firm import compensation as C, economy as E, workflows as W
    C.award_bonus("news_analyst", 20, "precisione")
    W._postmortem("news_analyst", 4, "affermazione inventata arrivata a un desk", "x", "y", "Mai numeri senza fonte.")
    assert E.gc_unvested("news_analyst") == 0


def test_building_level_is_monotonic_and_offices_follow_grade(org):
    from firm import building, db, registry
    assert building.level()["livello"] == 0
    db.ex("INSERT INTO nav_marks(day,pod,nav,capital,gross) VALUES('2026-11-01','firm',101700,1,0)")
    assert building.level()["livello"] == 2                # massimo storico +1,7% -> mensa
    db.ex("INSERT INTO nav_marks(day,pod,nav,capital,gross) VALUES('2026-11-02','firm',99000,1,0)")
    assert building.level()["livello"] == 2                # un drawdown non toglie i servizi
    off = {o["agent_id"]: o for o in building.offices()}
    assert off["capo"]["tier"] == "ceo" and "vista_panoramica" in off["capo"]["arredo"]
    assert off["cro"]["tier"] == "privato"
    assert off["senior_trend"]["tier"] == "vetro"
    assert off["news_analyst"]["tier"] == "open"
    assert off["gateway"]["tier"] == "ops" and off["pod_zero"]["tier"] == "trading"
    registry.change_grade("news_analyst", 5, "promozione", "test")
    off = {o["agent_id"]: o for o in building.offices()}
    assert off["news_analyst"]["tier"] == "privato"        # promossa: ufficio privato
    assert len(off["capo"]["arredo"]) > len(off["cro"]["arredo"]) > len(off["fact_checker"]["arredo"])


def test_meeting_full_cycle_with_scripted_agents(org, monkeypatch):
    from firm import meetings, db, economy as E, gateway
    from llm import providers
    from llm.providers import LLMResult

    class P:
        name = "scripted"

        def complete(self, model, system, user, schema, max_tokens, effort="low"):
            cro = "Elena Conti" in system
            if "posizione_finale" in json.dumps(schema):
                out = {"replica": "confermo", "posizione_finale": "riduci" if cro else "mantieni", "fiducia": 0.8 if cro else 0.6}
            else:
                out = {"posizione": "riduci" if cro else "mantieni", "argomento": "dati", "evidenza": ["libro.drawdown"],
                       "fiducia": 0.8 if cro else 0.6, "cambierei_idea_se": "drawdown in recupero"}
            return LLMResult(text=json.dumps(out), model=model, provider="scripted", input_tokens=100, output_tokens=50)
    monkeypatch.setattr(providers, "for_agent", lambda p: P())
    r = meetings.risk_meeting("crypto", "pod crypto vicino al taglio")
    assert r["ok"] and r["decisione"] in ("riduci", "mantieni")
    m = meetings.history(1)[0]
    assert m["status"] == "decisa" and set(m["transcript"]["repliche"]) == {"cro", "capo", "pod_crypto"}
    # i fatti: il pod perde nei giorni successivi -> 'riduci' era giusto
    start = m["ts"][:10]
    for i, nav in enumerate([5000, 4950, 4900, 4880]):
        db.ex("INSERT INTO nav_marks(day,pod,nav,capital,gross) VALUES(?,?,?,?,?)", (f"{start}-{i}", "crypto", nav, 0, 0))
    db.ex("UPDATE meetings SET resolve_after=? WHERE id=?", (start, m["id"]))
    res = meetings.resolve_due(start)
    assert res[0]["giusta"] == "riduci"
    assert res[0]["gc"]["cro"] > 0 > res[0]["gc"]["capo"]
    assert E.gc_unvested("cro") > 0 and E.gc_balance("capo") < 0


def test_daily_report_has_corrections(org):
    from firm import reports
    r = reports.daily(save=True)
    assert "correzioni" in r and isinstance(r["correzioni"], list)
    assert any("DSR della v3" in c["cosa"] for c in r["correzioni"])
    assert reports.listing()[0] == r["giorno"]
