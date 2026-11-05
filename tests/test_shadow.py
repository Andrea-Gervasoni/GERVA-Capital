"""Portafoglio ombra: in avanti da una data fissa, ogni giorno scritto una volta, nessuna riscrittura del passato."""
import numpy as np
import pytest

from test_gervaq4 import synth


def test_shadow_records_forward_days_once(firm_env):
    from firm import shadow, db
    d = synth(4, years=4)
    close = d["close"]
    first = shadow.update(close.iloc[:-30], start=str(close.index[-31].date()))
    assert first["ok"] and first["nuovi"] == 0 and first["giorni"] == 0         # la partenza e' l'ultimo giorno visto
    second = shadow.update(close)
    assert second["nuovi"] == 2 * 30 and second["giorni"] == 30
    before = db.q("SELECT day, variant, ret FROM shadow_returns ORDER BY day, variant")
    revised = close.copy()
    revised.iloc[-10:] *= 1.05                                                  # prezzi passati "rivisti"
    assert shadow.update(revised)["nuovi"] == 0
    assert db.q("SELECT day, variant, ret FROM shadow_returns ORDER BY day, variant") == before
    with pytest.raises(Exception):
        db.ex("UPDATE shadow_returns SET ret=0")                               # append-only
    s = shadow.summary()
    assert s["verdetto"].startswith("in osservazione") and set(shadow.VARIANTS) <= set(s)
    assert s["partenza"] == str(close.index[-31].date())


def test_daily_report_includes_shadow(firm_env):
    from firm import reports, org_seed, registry, pods
    org_seed.seed(); registry.sync(); pods.ensure_pods()
    assert "ombra" in reports.daily(save=False)


def test_default_start_is_pre_registered(firm_env):
    from firm import shadow
    d = synth(5, years=3)
    r = shadow.update(d["close"])
    assert r["partenza"] == shadow.START_DEFAULT
