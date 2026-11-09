"""Portafoglio di strategie: metriche prudenti (niente Sharpe su pochi giorni), correlazioni sui giorni in comune, diversificazione."""
import numpy as np
import pandas as pd
import pytest

from firm import db, sleeves as SL


def _s(n, mu=0.0008, sd=0.01, seed=1, start="2026-01-05"):
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(mu, sd, n), index=pd.bdate_range(start, periods=n))


def test_metrics_refuse_to_judge_too_few_days():
    m4 = SL.metrics(_s(4))
    assert m4["stato"] == "dati insufficienti" and m4["sharpe"] is None and m4["calmar"] is None and m4["profit_factor"] is None
    m30 = SL.metrics(_s(30))
    assert m30["stato"] == "pochi dati" and m30["sharpe"] is not None and m30["annuo"] is None          # Sharpe si', rendimento annuo no
    m200 = SL.metrics(_s(200))
    assert m200["stato"] == "ok" and m200["annuo"] is not None and m200["calmar"] is not None and m200["calo_massimo"] < 0
    assert SL.metrics(None)["stato"] == "nessun dato"


def test_correlation_only_on_common_days_and_none_otherwise():
    a, b = _s(100, seed=1), _s(100, seed=2)
    short = _s(10, seed=3)                                                                              # sotto il minimo: fuori dalla matrice
    far = _s(100, seed=4, start="2024-01-01")                                                           # periodo diverso: nessun giorno in comune
    c = SL.correlation(dict(a=a, b=b, s=short, f=far))
    assert c["simboli"] == ["a", "b", "f"]
    idx = {k: i for i, k in enumerate(c["simboli"])}
    assert c["matrice"][idx["a"]][idx["a"]] == 1.0 and abs(c["matrice"][idx["a"]][idx["b"]]) < 0.4     # indipendenti: correlazione bassa
    assert c["matrice"][idx["a"]][idx["f"]] is None                                                     # niente giorni in comune: non si inventa


def test_combined_diversification_matches_theory():
    series = {f"s{i}": _s(500, mu=0.0006, sd=0.01, seed=10 + i) for i in range(6)}                      # 6 sleeve indipendenti con lo stesso Sharpe
    c = SL.combined(series)
    assert c["n_sleeve"] == 6 and c["diversificazione"] >= 80 and c["voto"] == "A"
    assert c["sharpe"] > c["sharpe_medio_sleeve"] * 1.8                                                  # diversificare alza lo Sharpe (circa radice di N)
    same = _s(300, seed=5)
    twins = SL.combined(dict(x=same, y=same * 1.0001))
    assert twins["voto"] == "D" and twins["n_effettivo"] < 1.2                                           # strategie identiche: nessuna diversificazione
    assert SL.combined(dict(solo=_s(100))) is None


def test_overview_with_little_live_data_is_honest(firm_env):
    for i, d in enumerate(["2026-11-05", "2026-11-06", "2026-11-07"]):
        db.ex("INSERT OR REPLACE INTO nav_marks(day,pod,nav,capital,gross) VALUES(?,?,?,?,?)", (d, "pod_zero", 970000 + i * 800, 1.0, 0.0))
    o = SL.overview()
    live = o["gruppi"][0]
    motore = next(r for r in live["sleeve"] if r["nome"].startswith("Motore"))
    assert motore["giorni"] == 2 and motore["stato"] == "dati insufficienti" and motore["sharpe"] is None          # 4 giorni non dicono niente: lo scrive
    assert live["combinato"] is None and live["correlazioni"]["simboli"] == []
    bt = o["gruppi"][1]
    assert all(r["stato"] == "nessun dato" for r in bt["sleeve"])


def test_backtest_series_are_saved_and_read_back(firm_env):
    db.runtime_set("algo.crypto_tsmom.serie", dict(d=[str(x)[:10] for x in pd.bdate_range("2024-01-01", periods=120)], v=[0.001] * 120))
    s = SL.backtest_series("crypto_tsmom")
    assert len(s) == 120 and SL.metrics(s)["stato"] == "ok"


def test_wrong_account_readings_are_discarded_and_counted(firm_env):
    vals = [970000, 970500, 86000, 971000, 971200]                                                      # una lettura sbagliata (valuta/stima) nel mezzo
    for d, v in zip(["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"], vals):
        db.ex("INSERT OR REPLACE INTO nav_marks(day,pod,nav,capital,gross) VALUES(?,?,?,?,?)", (d, "pod_zero", v, 1.0, 0.0))
    r, bad = SL.engine_series()
    assert bad == 2 and r.abs().max() < 0.01                                                            # il -91% e il rimbalzo +1030% sono scartati
    motore = next(x for x in SL.overview()["gruppi"][0]["sleeve"] if x["nome"].startswith("Motore"))
    assert motore["scartati"] == 2 and motore["breve"] == "Motore"
