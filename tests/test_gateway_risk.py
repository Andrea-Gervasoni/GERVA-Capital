"""M5: Gateway di Esecuzione, sub-ledger, compensazione interna, motore di rischio, pod, Pod Zero."""
import datetime as dt

import pytest

WED_NOON = dt.datetime(2026, 11, 4, 14, 0, tzinfo=dt.timezone.utc)
SAT = dt.datetime(2026, 11, 7, 14, 0, tzinfo=dt.timezone.utc)


@pytest.fixture()
def firm(firm_env):
    from firm import org_seed, registry, pods, gateway
    org_seed.seed()
    registry.sync()
    pods.ensure_pods()
    gateway.set_price("CSPX", 600.0, "etf_ucits")
    gateway.set_price("BTC", 60_000.0, "crypto")
    gateway.set_price("SPY_US", 500.0, "etf_us")
    return firm_env


def test_accepts_valid_order_and_rejects_with_reasons(firm):
    from firm import gateway
    ok = gateway.submit_order("trend", "pod_trend", "CSPX", "BUY", 2, "trend positivo su 4 orizzonti", "settimane", now=WED_NOON)
    assert ok["status"] == "accettato"
    cases = [
        (("trend", "pod_crypto", "CSPX", "BUY", 1), "non gestisce"),            # pod di un altro
        (("trend", "pod_trend", "SPY_US", "BUY", 1), "non ammesso"),             # ETF USA vietato
        (("trend", "pod_trend", "CSPX", "SELL", 10), "scoperto"),                # short
        (("trend", "pod_trend", "CSPX", "BUY", 50), "fat-finger"),               # 30k EUR > 5% NAV
        (("trend", "pod_trend", "CSPX", "BUY", 0.01), "minimo"),
        (("trend", "pod_trend", "DOGE2", "BUY", 1), "sconosciuto"),
        (("pod_zero", "pod_zero", "CSPX", "BUY", 1), "live.py"),
    ]
    for args, msg in cases:
        r = gateway.submit_order(*args, reason="prova di controllo del gateway", horizon="giorni", now=WED_NOON)
        assert r["status"] == "respinto" and any(msg in x for x in r["reasons"]), (args, r)
    r = gateway.submit_order("trend", "pod_trend", "CSPX", "BUY", 1, "ordine nel weekend", "giorni", now=SAT)
    assert r["status"] == "respinto" and any("orario" in x for x in r["reasons"])
    r = gateway.submit_order("trend", "pod_trend", "CSPX", "BUY", 1, "prezzo sbagliato", "giorni",
                             ref_price=700, now=WED_NOON)
    assert any("lontano" in x for x in r["reasons"])


def test_pod_gross_and_concentration_limits(firm):
    from firm import gateway
    # capitale pod = 5% di ~100k = ~5.000 EUR; 25% di concentrazione = ~1.250 EUR
    r = gateway.submit_order("trend", "pod_trend", "CSPX", "BUY", 4, "troppo concentrato", "mesi", now=WED_NOON)
    assert r["status"] == "respinto" and any("concentrazione" in x for x in r["reasons"])


def test_internal_netting_saves_costs_and_ledger_attributes_pnl(firm):
    from firm import gateway, db
    # il pod crypto compra 0,02 BTC; poi il pod trend (ipotetico) vende: serve una posizione prima
    assert gateway.submit_order("crypto", "pod_crypto", "BTC", "BUY", 0.02, "breakout 55 periodi", "giorni", now=WED_NOON)["status"] == "accettato"
    gateway.flush()
    pos = gateway.positions("crypto")
    assert pos["BTC"] == pytest.approx(0.02)
    fee1 = db.one("SELECT SUM(fee) f FROM fills WHERE pod='crypto'")["f"]
    assert fee1 > 0
    # due pod in direzioni opposte sullo stesso strumento: si compensano internamente
    gateway.set_price("CSPX", 600.0, "etf_ucits")
    gateway.submit_order("trend", "pod_trend", "CSPX", "BUY", 2, "trend in acquisto", "settimane", now=WED_NOON)
    gateway.flush()
    gateway.submit_order("trend", "pod_trend", "CSPX", "SELL", 1, "riduzione su segnale", "settimane", now=WED_NOON)
    gateway.submit_order("reversal", "pod_reversal", "CSPX", "BUY", 1, "ipervenduto di qualita'", "giorni", now=WED_NOON)
    rep = gateway.flush()
    assert rep["interni"] == 2 and rep["al_broker"] == 0 and rep["risparmio_eur"] > 0
    assert gateway.positions("trend")["CSPX"] == pytest.approx(1)
    assert gateway.positions("reversal")["CSPX"] == pytest.approx(1)
    # P&L attribuito al pod giusto quando il prezzo sale
    gateway.set_price("BTC", 66_000.0, "crypto")
    b = gateway.pod_book("crypto")
    assert b["pnl"] == pytest.approx(0.02 * 6000 - b["fees"] - 0.02 * 60_000 * 0.0005, rel=0.05)


def test_kill_blocks_everything_and_only_engine_or_andrea_can_engage(firm):
    from firm import risk, gateway, settings as S
    with pytest.raises(PermissionError):
        risk.engage_kill("cro", "voglio fermare tutto")          # il CRO puo' solo raccomandare
    risk.recommend_kill("cro", "test", "evidenza")
    risk.engage_kill("risk_engine", "test automatico")
    r = gateway.submit_order("trend", "pod_trend", "CSPX", "BUY", 1, "ordine durante il KILL", "giorni", now=WED_NOON)
    assert r["reasons"] == ["KILL attivo"]
    with pytest.raises(PermissionError):
        risk.release_kill(cap=None)
    risk.release_kill(S.AndreaCapability(S.ensure_token()))
    assert not risk.kill_active()


def test_drawdown_rules_cut_then_close(firm):
    from firm import gateway, pods, db
    gateway.submit_order("crypto", "pod_crypto", "BTC", "BUY", 0.02, "breakout 55 periodi", "giorni", now=WED_NOON)
    gateway.flush()
    gateway.mark_day("2026-11-04")
    gateway.set_price("BTC", 60_000 * (1 - 0.30), "crypto")        # -30% su 1.200 EUR = -360 EUR = -7,2% del pod
    acts = pods.apply_drawdown_rules()
    assert acts and acts[0]["azione"] == "dimezzato"
    assert pods.get("crypto")["capital_frac"] == pytest.approx(0.025)
    gateway.set_price("BTC", 60_000 * (1 - 0.34), "crypto")        # oltre -7,5%
    acts = pods.apply_drawdown_rules()
    assert acts[0]["azione"] == "chiuso" and pods.get("crypto")["status"] == "chiuso"
    assert pods.get("pod_zero")["capital_frac"] == pytest.approx(0.85 + 0.05)


def test_pod_zero_adapter_reads_snapshot_without_writing(firm, monkeypatch, tmp_path):
    from firm import pod_zero, paths
    import json, os
    gq = tmp_path / "gq"
    (gq / "state").mkdir(parents=True)
    json.dump({"asof": "2026-10-30", "weights": {"SPY": 0.30, "XLK": 0.08}}, open(gq / "state/model_latest.json", "w"))
    json.dump({"bar": "2026-11-03 10:00", "weights": {"BTC": 0.013, "ETH": 0.017}}, open(gq / "state/crypto_latest.json", "w"))
    monkeypatch.setattr(paths, "GERVA_Q", str(gq))
    before = sorted(os.listdir(gq / "state"))
    s = pod_zero.summary()
    assert s["disponibile"] and s["pesi"]["SPY"] == pytest.approx(0.15)       # v2 -> dimezzato
    assert s["quota_crypto"] == pytest.approx(0.03)
    assert sorted(os.listdir(gq / "state")) == before
