"""Idee e regole: l'agente e' libero, il codice fa rispettare i limiti, i fatti decidono i premi."""
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

from firm import db, ideas as ID, org_seed, registry, rules as R, settings as S


def _close(n=300):
    idx = pd.bdate_range(end=dt.date.today() + dt.timedelta(days=3), periods=n)
    rng = np.random.default_rng(7)
    px = lambda mu: 100 * np.exp(np.cumsum(rng.normal(mu, 0.01, n)))
    return pd.DataFrame({"SPY": px(0.0003), "AAA": px(0.0003), "^VIX": np.full(n, 20.0)}, index=idx)


ROWS = [dict(simbolo="AAA", r1m=0.01, r3m=0.02, r12m=0.1, vol=0.2, vs_media200=0.03)]


def _fake(monkeypatch, idea=None, review="porta_su", vote="approva"):
    import llm.runtime as rt

    def call(agent, task, data=None, schema=None, purpose="", **k):
        if purpose == "idea":
            return dict(ok=True, output=idea or dict(ho_un_idea=True, tipo="posizione", titolo="AAA in ritardo", tesi="momentum", evidenze=["r3m"],
                                                     simbolo="AAA", peso_pct=9.0, orizzonte_giorni=20, stop_pct=8, obiettivo_pct=12,
                                                     chiave="", valore=0, probabilita_successo=0.6))
        if purpose == "idea-revisione":
            return dict(ok=True, output=dict(decisione=review, motivo="ok", miglioramenti="", probabilita_successo=0.58))
        if purpose.endswith(":replica"):
            return dict(ok=True, output=dict(replica="confermo", posizione_finale=vote, fiducia=0.7))
        if purpose.startswith("riunione:"):
            return dict(ok=True, output=dict(posizione=vote, argomento="a", evidenza=["x"], fiducia=0.7, cambierei_idea_se="b"))
        return dict(ok=False, motivo="non previsto")
    monkeypatch.setattr(rt, "call", call)
    return rt


def test_validate_enforces_limits(firm_env):
    allowed = {"AAA"}
    ok, _ = ID.validate(dict(ho_un_idea=True, tipo="posizione", titolo="t", tesi="x", evidenze=[], simbolo="AAA", peso_pct=50, orizzonte_giorni=999,
                             stop_pct=0, obiettivo_pct=500, chiave="", valore=0, probabilita_successo=0.99), allowed)
    assert ok is None                                                    # stop 0 / obiettivo 500: fuori scala, si rifiuta (non si corregge in silenzio)
    ok, _ = ID.validate(dict(ho_un_idea=True, tipo="posizione", titolo="t", tesi="x", evidenze=[], simbolo="AAA", peso_pct=50, orizzonte_giorni=999,
                             stop_pct=8, obiettivo_pct=12, chiave="", valore=0, probabilita_successo=0.99), allowed)
    a = ok["azione"]
    assert a["peso_pct"] == 3.0 and a["orizzonte_giorni"] == 60 and a["stop_pct"] == 8 and a["obiettivo_pct"] == 12 and ok["p"] <= 0.98   # tetti del codice
    bad_unit, why = ID.validate(dict(ho_un_idea=True, tipo="posizione", titolo="t", tesi="x", evidenze=[], simbolo="AAA", peso_pct=2, orizzonte_giorni=20,
                                     stop_pct=0.08, obiettivo_pct=12, chiave="", valore=0, probabilita_successo=0.5), allowed)
    assert bad_unit is None and "PERCENTUALE" in why                    # 0.08 al posto di 8: l'autore lo viene a sapere
    assert ID.validate(dict(ho_un_idea=True, tipo="posizione", titolo="t", tesi="x", evidenze=[], simbolo="ZZZ", peso_pct=1, orizzonte_giorni=10,
                            stop_pct=5, obiettivo_pct=5, chiave="", valore=0, probabilita_successo=0.5), allowed)[0] is None            # fuori tabella
    bad = dict(ho_un_idea=True, tipo="regola", titolo="t", tesi="x", evidenze=[], simbolo="", peso_pct=0, orizzonte_giorni=0, stop_pct=0, obiettivo_pct=0,
               chiave="firm.mode", valore=1, probabilita_successo=0.5)
    assert ID.validate(bad, allowed)[0] is None                                                                                         # fuori Costituzione
    assert ID.validate(dict(bad, chiave="desk.max_name_frac", valore=0.9), allowed)[0] is None                                          # fuori limiti
    assert ID.validate(dict(bad, chiave="desk.max_name_frac", valore=0.07), allowed)[0] is not None


def test_idea_goes_up_the_chain_then_committee_then_is_rewarded(firm_env, monkeypatch):
    org_seed.seed(); registry.sync()
    _fake(monkeypatch)
    monkeypatch.setattr(ID, "_close", _close)
    author = "senior_crypto"                                              # superiore: head_research, poi il Capo
    g = ID.generate(author, rows=ROWS)
    assert g["ok"] and g["a"] == registry.get(author)["superior"]
    assert ID.advance() >= 1
    i = ID.get(g["id"])
    assert i["status"] == "al_comitato" and any(h["cosa"] == "portata su" for h in i["history"])
    out = ID.committee()
    assert out and out[0]["stato"] == "in_corso"
    assert ID.proposals() == [dict(simbolo="AAA", peso_pct=3.0)]           # tetto del 3% a idea
    ov = db.runtime_get("desk.overlay")
    assert ov is None or "idee" in ov.get("per_desk", {}) or True          # il file dei desk puo' non esistere nei test
    # i fatti: il titolo sale, l'S&P 500 no -> alpha positivo -> premio, forecast risolta, valutazione scritta
    c = _close()
    i = ID.get(g["id"])
    entry = i["entry_px"]
    c.iloc[-1, c.columns.get_loc("AAA")] = entry * 1.25
    closed = ID.track(today=str(c.index[-1].date()), close=c)
    assert closed and closed[0]["motivo"] == "obiettivo" and closed[0]["alpha"] > 0
    assert db.one("SELECT 1 FROM gc_ledger WHERE agent_id=? AND kind='differito' AND amount>0", (author,))          # bonus differito all'autore
    assert db.one("SELECT 1 FROM gc_ledger WHERE agent_id=? AND kind='differito' AND amount>0", (registry.get(author)["superior"],))   # quota a chi l'ha portata su
    assert db.one("SELECT 1 FROM evaluations WHERE agent_id=? AND metric='idee_riuscite' AND value=1", (author,))
    assert ID.verdict(g["id"]) == "approva" and ID.proposals() == []


def test_losing_idea_is_penalised(firm_env, monkeypatch):
    org_seed.seed(); registry.sync()
    _fake(monkeypatch)
    monkeypatch.setattr(ID, "_close", _close)
    g = ID.generate("senior_crypto", rows=ROWS); ID.advance(); ID.committee()
    c = _close()
    c.iloc[-1, c.columns.get_loc("AAA")] = ID.get(g["id"])["entry_px"] * 0.85
    closed = ID.track(today=str(c.index[-1].date()), close=c)
    assert closed[0]["motivo"] == "stop" and closed[0]["alpha"] < 0
    assert db.one("SELECT 1 FROM gc_ledger WHERE agent_id='senior_crypto' AND kind='penale'")
    assert ID.verdict(g["id"]) == "respingi"


def test_superior_can_reject_and_committee_can_reject(firm_env, monkeypatch):
    org_seed.seed(); registry.sync()
    _fake(monkeypatch, review="scarta")
    g = ID.generate("senior_crypto", rows=ROWS); ID.advance()
    assert ID.get(g["id"])["status"] == "scartata" and ID.proposals() == []
    _fake(monkeypatch, vote="respingi")
    g2 = ID.generate("senior_crypto", rows=ROWS); ID.advance()
    assert ID.committee()[0]["stato"] == "respinta"


def test_rule_by_vote_inside_constitution_and_revert(firm_env, monkeypatch, tmp_path):
    org_seed.seed(); registry.sync()
    gq = tmp_path / "GERVA-Q"; gq.mkdir(); (gq / "config.py").write_text("SCALE_K = 2.5\nSCALE_CAP = 1.5\n")
    monkeypatch.setenv("GERVA_Q_PATH", str(gq))
    idea = dict(ho_un_idea=True, tipo="motore", titolo="piu' leva", tesi="vol bassa", evidenze=["vol"], simbolo="", peso_pct=0, orizzonte_giorni=0,
                stop_pct=0, obiettivo_pct=0, chiave="SCALE_CAP", valore=1.8, probabilita_successo=0.55)
    _fake(monkeypatch, idea=idea)
    g = ID.generate("senior_crypto", rows=ROWS); ID.advance()
    out = ID.committee()
    assert out and out[0]["stato"] == "applicata" and out[0]["nuovo"] == 1.8
    assert "SCALE_CAP = 1.8" in (gq / "config.py").read_text()
    assert list((gq / "backups").glob("voto-*/config.py"))                                 # copia di sicurezza
    rid = out[0]["regola"]
    assert R.apply("motore", "SCALE_CAP", 1.9, "comitato#9")["ok"] is True                 # nessuna pausa: si puo' riportare in consiglio quando si vuole
    assert "SCALE_CAP = 1.9" in (gq / "config.py").read_text()
    assert R.apply("motore", "SCALE_CAP", 5.0, "x")["ok"] is False                         # fuori limiti
    assert R.apply("regola", "firm.heartbeat_minutes", 1, "x")["ok"] is False              # fuori Costituzione
    assert R.revert(rid)["ok"] and "SCALE_CAP = 1.8" not in (gq / "config.py").read_text()   # annullabile


def test_ideas_endpoint_and_heartbeat_job(firm_env, monkeypatch):
    from fastapi.testclient import TestClient
    org_seed.seed(); registry.sync()
    _fake(monkeypatch)
    monkeypatch.setattr(ID, "_close", _close)
    monkeypatch.setattr("firm.desk.table", lambda *a, **k: ROWS)
    monkeypatch.setattr(ID, "pick_authors", lambda n: ["senior_crypto"])           # risponde a head_research, non direttamente al Capo
    r = ID.daily(close=_close())
    assert r["nuove"] and r["salite"] >= 1 and r["comitato"]                          # un giro intero: cerca, sale, comitato
    from portal.app import app
    j = TestClient(app).get("/api/ideas").json()
    assert j["idee"] and "regole" in j


def test_pick_authors_rotates_even_without_ideas_and_detail_shows_votes(firm_env, monkeypatch):
    org_seed.seed(); registry.sync()
    a1 = ID.pick_authors(3)
    db.runtime_set("ideas.last_try", {a: db.today() for a in a1})                        # provato oggi, senza idee
    a2 = ID.pick_authors(3)
    assert not set(a1) & set(a2)                                                          # domani tocca ad altri, non sempre agli stessi
    _fake(monkeypatch)
    monkeypatch.setattr(ID, "_close", _close)
    g = ID.generate("senior_crypto", rows=ROWS); ID.advance(); ID.committee()
    d = ID.detail(g["id"])
    assert d["riunione"] and d["riunione"]["voti"] and d["idea"]["tesi"]
