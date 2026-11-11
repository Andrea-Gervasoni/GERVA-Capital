"""Regressioni dei due audit del 10/11 (esecuzione e rischio; quantlab). Ogni test fallisce sul codice di prima e passa su quello corretto.

Dove serve si usano i limiti di PRODUZIONE (config/risk_limits.yaml: allow_short true, max_gross 2.0): tests/conftest.py forza l'opposto
(niente short, lorda 1.0), quindi la configurazione vera non era coperta da nessun test."""
import datetime as dt
import json
import math
import os
import shutil

import numpy as np
import pandas as pd
import pytest

from firm import crypto_venue as V, db, free_desk as FD, ideas as ID, org_seed, registry, risk, rules as R, settings as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TUE = dt.datetime(2026, 11, 10, 15, 0, tzinfo=dt.timezone.utc)          # martedi', 15 UTC: azioni ed ETF aperti


def _cap():
    return S.AndreaCapability(S.ensure_token())


@pytest.fixture()
def prod_env(firm_env):
    """Come firm_env, ma con i limiti di rischio di produzione copiati cosi' come sono."""
    shutil.copy(os.path.join(ROOT, "config", "risk_limits.yaml"), S.RISK_FILE)
    lim = S.risk_limits()
    assert lim["pod"]["allow_short"] is True and lim["pod"]["max_gross"] == 2.0 and lim["firm"]["max_gross"] == 2.0
    return firm_env


class Alpaca:
    """Conto paper finto: registra ogni chiamata; DELETE /v2/orders e /v2/positions rispondono come Alpaca (una voce per ordine/posizione)."""

    def __init__(self, equity=100000.0, positions=None):
        self.equity, self.pos, self.calls, self.orders = equity, list(positions or []), [], []

    def req(self, method, path, body=None, timeout=15):
        self.calls.append((method, path, body))
        if path == "/v2/account":
            return dict(equity=str(self.equity), last_equity=str(self.equity), buying_power=str(self.equity * 4), cash=str(self.equity))
        if method == "GET" and path == "/v2/positions":
            return list(self.pos)
        if path.startswith("/v2/assets"):
            return [dict(symbol=f"{c}/USD", tradable=True) for c in ("BTC", "ETH", "SOL")]
        if method == "DELETE" and path == "/v2/orders":
            n, self.orders = len(self.orders), []
            return [dict(id=f"o{i}", status=200) for i in range(n)]
        if method == "DELETE" and path.startswith("/v2/positions"):
            n, self.pos = len(self.pos), []
            return [dict(symbol="X", status=200) for _ in range(n)]
        if method == "POST" and path == "/v2/orders":
            self.orders.append(body)
            return dict(id=f"o{len(self.orders)}")
        if method == "GET" and path.startswith("/v2/orders/"):
            return dict(status="new")
        raise AssertionError((method, path))

    def posts(self):
        return [c[2] for c in self.calls if c[0] == "POST"]


@pytest.fixture()
def alpaca(firm_env, monkeypatch):
    org_seed.seed(); registry.sync()
    monkeypatch.setenv("ALPACA_PAPER_KEY", "k" * 12); monkeypatch.setenv("ALPACA_PAPER_SECRET", "s" * 12)
    a = Alpaca()
    monkeypatch.setattr(V, "_req", a.req)
    monkeypatch.setattr(V, "last_price", lambda sym: 100.0)
    return a


def _trade(sym="AAPL", usd=1000, lato="buy", **k):
    return dict(simbolo=sym, lato=lato, importo_usd=usd, tipo_ordine="market", prezzo_limite=0, stop_pct=0.5, take_pct=1.0, tieni_minuti=2,
                motivo="prova", probabilita=0.55, **k)


# =============================================================================================== C1: un solo KILL per ogni strada
def test_kill_blocks_buys_on_every_alpaca_path_but_sells_pass(alpaca, monkeypatch):
    from firm import strategies as ST
    S.set("crypto.venue", "alpaca", _cap()); S.set("crypto.venue_mirror_model", False, _cap())
    db.runtime_set("desk.overlay", dict(crypto_targets={"BTC": 0.03}))                     # un obiettivo da comprare...
    alpaca.pos = [dict(symbol="ETHUSD", asset_class="crypto", market_value="5000")]         # ...e una posizione da vendere (fuori obiettivo)
    monkeypatch.setattr(risk, "on_kill", lambda *a, **k: {})                                 # qui si prova il RIFIUTO; lo svuotamento ha il suo test
    risk.engage_kill("risk_engine", "prova")
    r = V.rebalance()
    assert r["ok"] and [o["side"] for o in r["ordini"]] == ["sell"] and any("KILL" in x for x in r["saltate"])
    assert not [b for b in alpaca.posts() if b["side"] == "buy"]                            # nessun acquisto parte con il KILL attivo
    # banco libero: nessun nuovo trade, nessuna chiamata agli agenti
    x = FD.execute("senior_crypto", _trade(), FD.state())
    assert not x["ok"] and "KILL" in x["motivo"] and "KILL" in FD.cycle()["nota"]
    # strategie in codice: obiettivi azzerati, nessun ingresso su SPY
    S_on = lambda k: db.ex("INSERT INTO settings(key,value,updated_ts,updated_by) VALUES(?,?,?,?)", (k, "1", db.now_iso(), "t"))
    S_on("algo.crypto_tsmom.on"); S_on("algo.spy_intraday_momentum.on")
    db.runtime_set("algo.crypto_targets", {"BTC": 0.2})
    assert ST.live_crypto(close=pd.DataFrame())["obiettivi"] == {} and db.runtime_get("algo.crypto_targets") == {}
    monkeypatch.setattr(ST, "stock_bars", lambda *a, **k: (_ for _ in ()).throw(AssertionError("con il KILL non si scaricano nemmeno le barre")))
    at_1540 = dt.datetime(2026, 11, 10, 20, 40, tzinfo=dt.timezone.utc)                    # 15:40 a New York
    assert "KILL" in ST.live_spy(now=at_1540)["nota"]
    assert not alpaca.posts() and [c[1] for c in alpaca.calls if c[0] == "DELETE"] == ["/v2/positions/ETHUSD"]   # in tutto: la sola chiusura di ETH


def test_kill_makes_an_accepted_signal_observed_only(alpaca, monkeypatch):
    from firm import signals as SG
    from llm import runtime
    idx = pd.bdate_range(end=dt.date.today() + dt.timedelta(days=3), periods=300)
    px = 150.0 + np.sin(np.arange(300) / 7.0)
    close = pd.DataFrame({"SOL": px * (150.0 / px[-1]), "SPY": px, "^VIX": 20.0}, index=idx)
    S.set("crypto.venue", "alpaca", _cap())

    def call(agent, task, **kw):
        if agent == "senior_crypto":
            return dict(ok=True, output=dict(decisione="accetta", probabilita_tp1=0.6, peso_pct=90.0, motivo="ok", rischi=[], invalidazione="x"))
        return dict(ok=True, output=dict(veto=False, motivo="ok"))
    monkeypatch.setattr(runtime, "call", call)
    monkeypatch.setattr(risk, "on_kill", lambda *a, **k: {})
    risk.engage_kill("risk_engine", "prova")
    r = SG.process(SG.create("BUY SOL entry 150 SL 140 TP1 165"), close)
    assert r["stato"] == "osservato" and r["peso"] == 0.0 and "KILL" in r["motivo"]
    assert SG.active_targets() == {} and not alpaca.posts()


def test_kill_flattens_alpaca_and_mirrors_to_the_engine(alpaca, monkeypatch, tmp_path):
    from firm import paths
    gq = tmp_path / "GERVA-Q"; gq.mkdir()
    monkeypatch.setattr(paths, "GERVA_Q", str(gq))
    assert FD.execute("senior_crypto", _trade("AAPL", 5000), FD.state())["ok"]              # un ordine del banco libero ancora in coda
    db.ex("INSERT INTO free_trades(ts,agent,symbol,side,notional,kind,tif,status,order_id,entry_px,qty) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
          (db.now_iso(), "a", "MSFT", "buy", 1000, "market", "day", "aperta", "o9", 100.0, 10.0))
    alpaca.pos = [dict(symbol="BTCUSD", asset_class="crypto", market_value="3000"), dict(symbol="MSFT", asset_class="us_equity", market_value="1000")]
    risk.engage_kill("risk_engine", "drawdown di prova")                                    # il KILL scatta: tutto da qui
    dels = [c[1] for c in alpaca.calls if c[0] == "DELETE"]
    assert "/v2/orders" in dels and any(p.startswith("/v2/positions") for p in dels) and alpaca.pos == []
    assert {r["status"] for r in db.q("SELECT status FROM free_trades")} == {"rifiutato", "chiusa"}   # il registro non resta con posizioni fantasma
    assert FD.monitor() == [] and len(alpaca.posts()) == 1                                  # il monitor non "richiude" (venderebbe allo scoperto)
    st = db.runtime_get("alpaca.flatten")
    assert st["ok"] and st["posizioni_chiuse"] == 2 and st["ordini_annullati"] == 1
    assert (gq / "KILL").read_text().startswith(risk.ENGINE_KILL_MARK)                      # GERVA-Q legge il SUO file: lo stesso stato arriva anche li'
    risk.release_kill(_cap())
    assert not (gq / "KILL").exists() and not risk.kill_active()
    (gq / "KILL").write_text("messo a mano da Andrea\n")                                    # un KILL del motore messo a mano non si tocca
    risk.engage_kill("risk_engine", "di nuovo"); risk.release_kill(_cap())
    assert (gq / "KILL").exists()


def test_flatten_failure_is_reported_and_keeps_the_ledger(alpaca, monkeypatch):
    assert FD.execute("senior_crypto", _trade("AAPL", 5000), FD.state())["ok"]

    def down(method, path, body=None, timeout=15):
        raise RuntimeError("Alpaca 503")
    monkeypatch.setattr(V, "_req", down)
    out = V.flatten("prova")
    assert not out["ok"] and len(out["errori"]) == 2
    assert db.one("SELECT status FROM free_trades")["status"] == "inviato"                  # il broker non ha risposto: stop e tempi restano seguiti
    assert db.one("SELECT 1 FROM events WHERE kind='risk.alert' AND payload LIKE '%NON e%svuotato%'")


# =============================================================================================== C2: il voto non alza il rischio da solo
def _vote(monkeypatch, idea):
    import llm.runtime as rt

    def call(agent, task, data=None, schema=None, purpose="", **k):
        if purpose == "idea":
            return dict(ok=True, output=idea)
        if purpose == "idea-revisione":
            return dict(ok=True, output=dict(decisione="porta_su", motivo="ok", miglioramenti="", probabilita_successo=0.6))
        if purpose.endswith(":replica"):
            return dict(ok=True, output=dict(replica="si", posizione_finale="approva", fiducia=0.7))
        return dict(ok=True, output=dict(posizione="approva", argomento="a", evidenza=["x"], fiducia=0.7, cambierei_idea_se="b"))
    monkeypatch.setattr(rt, "call", call)


def _rule_idea(kind, key, value):
    return dict(ho_un_idea=True, tipo=kind, titolo="piu' leva", tesi="vol bassa", evidenze=["vol"], simbolo="", peso_pct=0, orizzonte_giorni=0,
                stop_pct=0, obiettivo_pct=0, chiave=key, valore=value, probabilita_successo=0.55)


def test_committee_vote_cannot_raise_engine_leverage_without_andrea(prod_env, monkeypatch, tmp_path):
    org_seed.seed(); registry.sync()
    gq = tmp_path / "GERVA-Q"; gq.mkdir(); (gq / "config.py").write_text("SCALE_K = 2.5\nSCALE_CAP = 1.5\nSCALE_HARD_CAP = 1.5\n")
    monkeypatch.setenv("GERVA_Q_PATH", str(gq))
    _vote(monkeypatch, _rule_idea("motore", "SCALE_HARD_CAP", 3.0))                         # tre agenti convinti votano 3x
    g = ID.generate("senior_crypto", rows=[]); ID.advance()
    out = ID.committee()
    assert out[0]["stato"] == "in_attesa" and "Andrea" in out[0]["motivo"]
    assert "SCALE_HARD_CAP = 1.5" in (gq / "config.py").read_text()                         # il motore NON e' stato toccato
    pend = R.pending()
    assert len(pend) == 1 and json.loads(pend[0]["new"]) == 2.0                             # e comunque mai oltre firm.max_gross (2.0), non 3.0
    assert ID.get(g["id"])["status"] == "in_attesa"
    assert db.one("SELECT category FROM mailbox WHERE dedup_key=?", (f"rule-pending:{pend[0]['id']}",))["category"] == 2   # arriva ad Andrea: limite di rischio
    with pytest.raises(S.SettingsPermissionError):
        R.approve(pend[0]["id"], cap=None)                                                  # senza la capability non si approva
    with pytest.raises(S.SettingsPermissionError):
        R.approve(pend[0]["id"], cap="comitato")
    res = R.approve(pend[0]["id"], _cap())
    assert res["ok"] and res["nuovo"] == 2.0 and "SCALE_HARD_CAP = 2.0" in (gq / "config.py").read_text()
    assert ID.get(g["id"])["status"] == "applicata" and R.pending() == []
    # ridurre il rischio resta del comitato, subito
    assert R.apply("motore", "SCALE_HARD_CAP", 1.2, "comitato#2")["ok"] and "SCALE_HARD_CAP = 1.2" in (gq / "config.py").read_text()
    # ...ma annullare quella riduzione (tornare a 2.0) e' di nuovo un aumento
    rid = R.history(1)[0]["id"]
    assert R.revert(rid, "decaduta comitato#3").get("in_attesa") and "SCALE_HARD_CAP = 1.2" in (gq / "config.py").read_text()
    assert R.revert(rid, "andrea", cap=_cap())["ok"] and "SCALE_HARD_CAP = 2.0" in (gq / "config.py").read_text()


def test_settings_caps_need_andrea_to_go_up_and_are_clamped_to_risk_limits(prod_env, monkeypatch):
    org_seed.seed(); registry.sync()
    for key, asked, top in (("signals.max_total_frac", 1.0, 0.60), ("signals.max_frac", 0.25, 0.10), ("desk.max_total_frac", 1.0, 1.0)):
        before = S.get(key)
        r = R.apply("regola", key, asked, "comitato#1")
        assert r["ok"] is False and r["in_attesa"] and r["proposto"] == top and S.get(key) == before      # niente cambia; il tetto e' quello di risk_limits.yaml
        assert R.apply("regola", key, asked, "comitato#1")["id"] == r["id"]                                # la stessa proposta non si duplica
    r = R.apply("regola", "crypto.venue_max_frac", 1.0, "comitato#1")                                       # prima: 100% crypto con un voto
    assert r["ok"] and r["nuovo"] == 0.60 and S.get("crypto.venue_max_frac") == 0.60                        # ora resta al limite di Andrea (firm.max_crypto_frac)
    assert R.apply("regola", "signals.max_frac", 0.01, "comitato#2")["ok"] and S.get("signals.max_frac") == 0.01   # abbassare: subito
    assert R.apply("regola", "ideas.horizon_days", 30, "comitato#3")["ok"]                                  # non e' rischio: resta del comitato
    r = R.apply("regola", "crypto.venue_max_frac", 1.0, "andrea", cap=_cap())                               # anche Andrea si ferma al SUO limite scritto
    assert r["ok"] and r["nuovo"] == 0.60 and r["limitato_a"] == 0.60 and S.get("crypto.venue_max_frac") == 0.60
    # la risposta nella Posta del Capo applica o respinge la proposta
    from firm import mailbox
    pid = R.apply("regola", "signals.risk_frac", 0.02, "comitato#4")["id"]
    mid = db.one("SELECT id FROM mailbox WHERE dedup_key=?", (f"rule-pending:{pid}",))["id"]
    assert mailbox.decide(mid, R.APPROVE, _cap())["regola"]["ok"] and S.get("signals.risk_frac") == 0.02
    pid = R.apply("regola", "signals.risk_frac", 0.04, "comitato#5")["id"]
    mid = db.one("SELECT id FROM mailbox WHERE dedup_key=?", (f"rule-pending:{pid}",))["id"]
    assert mailbox.decide(mid, "Respingi", _cap())["regola"]["stato"] == "respinta" and S.get("signals.risk_frac") == 0.02
    cat = R.catalog()
    assert cat["regola:crypto.venue_max_frac"]["massimo"] == 0.60 and cat["motore:SCALE_HARD_CAP"]["massimo"] == 2.0   # gli agenti vedono il tetto vero


# =============================================================================================== H2: un guasto non ferma il battito
def test_heartbeat_isolates_failures_and_runs_stop_tracking_first(firm_env, monkeypatch):
    from firm import heartbeat, signals as SG, gateway, reports
    order = []
    monkeypatch.setattr(heartbeat.news_feed, "fetch_all", lambda *a, **k: dict(errori=[], nuove=0))
    monkeypatch.setattr(heartbeat.risk, "snapshot", lambda: (_ for _ in ()).throw(ZeroDivisionError("float division by zero")))
    monkeypatch.setattr(SG, "track", lambda *a, **k: order.append("track") or 0)
    monkeypatch.setattr(V, "configured", lambda: True)
    monkeypatch.setattr(V, "rebalance", lambda *a, **k: order.append("rebalance") or dict(ok=True))
    monkeypatch.setattr(gateway, "mark_day", lambda day: order.append("mark"))
    boom = [True]

    def report(day):
        if boom[0]:
            raise RuntimeError("disco pieno")
        order.append("report")
    monkeypatch.setattr(reports, "daily", report)
    now = dt.datetime(2026, 11, 10, 21, 5, tzinfo=dt.timezone.utc)
    r = heartbeat.beat(now=now, use_agents=False)                                           # prima: ZeroDivisionError alla prima riga e niente altro
    assert order == ["track", "rebalance", "mark"]                                          # gli stop PRIMA del ribilanciamento; il NAV si marca lo stesso
    assert r["semaforo"] == "rosso" and any("motore di rischio non riuscito" in n for n in r["note"]) and any("report della sera" in n for n in r["note"])
    errs = [json.loads(e["payload"]) for e in db.q("SELECT payload FROM events WHERE kind='heartbeat.error'")]
    assert {e["passo"] for e in errs} >= {"motore di rischio", "report della sera"} and any("ZeroDivisionError" in e["errore"] for e in errs)
    assert db.one("SELECT 1 FROM events WHERE kind='risk.alert' AND payload LIKE '%motore di rischio%'")
    # la chiave "una volta al giorno" del report NON e' stata consumata dal fallimento: al battito dopo si riprova e riesce
    boom[0] = False
    heartbeat.beat(now=now + dt.timedelta(minutes=15), use_agents=False)
    assert order.count("report") == 1 and order.count("mark") == 1                         # il NAV, riuscito, non si rifa'
    heartbeat.beat(now=now + dt.timedelta(minutes=30), use_agents=False)
    assert order.count("report") == 1


def test_heartbeat_with_agents_survives_when_every_agent_call_fails(firm_env, monkeypatch):
    """Domenica sera, tutti i lavori degli agenti in calendario e il modello che non risponde: il battito arriva in fondo lo stesso."""
    from firm import heartbeat, pods
    import llm.runtime as rt
    org_seed.seed(); registry.sync(); pods.ensure_pods()
    monkeypatch.setattr(heartbeat.news_feed, "fetch_all", lambda *a, **k: dict(errori=[], nuove=0))
    monkeypatch.setattr(rt, "call", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("modello non raggiungibile")))
    db.ex("INSERT INTO commands(ts,text,status) VALUES(?,?,?)", (db.now_iso(), "fai il punto", "ricevuto"))
    sunday = dt.datetime(2026, 11, 1, 21, 30, tzinfo=dt.timezone.utc)                       # prima domenica del mese, dopo le 21
    r = heartbeat.beat(now=sunday)
    assert r["semaforo"] in ("verde", "giallo", "rosso") and any("non riuscito" in n for n in r["note"])
    assert db.one("SELECT COUNT(*) n FROM events WHERE kind='heartbeat.error'")["n"] >= 1   # i guasti sono eventi, non silenzi
    assert db.one("SELECT 1 FROM events WHERE kind='firm.heartbeat'")                       # e il battito si chiude con il suo evento
    assert db.one("SELECT 1 FROM nav_marks WHERE day='2026-11-01' AND pod='firm'")          # il NAV della sera e' marcato comunque


def test_once_key_gives_up_after_max_tries(firm_env):
    from firm import heartbeat
    notes, n = [], [0]

    def bad():
        n[0] += 1
        raise ValueError("sempre rotto")
    for _ in range(6):
        heartbeat._step("passo rotto", bad, notes, once="k:2026-11-10")
    assert n[0] == heartbeat.MAX_TRIES and len(notes) == heartbeat.MAX_TRIES             # si riprova, ma non all'infinito


def test_pods_enabled_with_zero_capital_do_not_crash_the_risk_engine(firm_env):
    from firm import gateway, pods
    db.ex("UPDATE settings SET value='0.0' WHERE key='pods.initial_capital_frac'")          # il default di produzione
    org_seed.seed(); registry.sync(); pods.ensure_pods()
    assert gateway.pod_book("trend")["drawdown"] == 0.0                                     # prima: ZeroDivisionError (nav / peak con peak = 0)
    assert risk.snapshot()["semaforo"] in ("verde", "giallo", "rosso")


# =============================================================================================== C3: banco libero
def test_free_desk_rules_apply_to_cumulative_exposure_within_a_cycle(alpaca):
    FD.set_house_rule("max_leverage", 1.0, "t"); FD.set_house_rule("max_position_frac", 0.10, "t")
    st = dict(equity=100000.0, lordo=0.0, posizioni=[], pnl_giorno_frac=0.0)               # la stessa fotografia per tutti i trade del giro
    ok = [FD.execute("pod_trend", _trade("AAPL", 9000), st).get("ok") for _ in range(20)]
    assert sum(ok) == 1 and sum(float(b["notional"]) for b in alpaca.posts()) == 9000.0     # prima: 20 accettati, 180.000 $ su 100.000
    # leva 1x sul totale: 9 simboli diversi da 10.000 $ (meno i 9.000 gia' presi) riempiono il conto, poi basta
    ok = [FD.execute("pod_trend", _trade(f"S{i}", 10000), st).get("ok") for i in range(12)]
    assert sum(ok) == 9 and sum(float(b["notional"]) for b in alpaca.posts()) == 99000.0
    x = FD.execute("pod_trend", _trade("ZZZ", 5000), st)
    assert not x["ok"] and "leva massima" in x["motivo"]
    FD.set_house_rule("max_leverage", 0, "t"); FD.set_house_rule("max_position_frac", 0, "t"); FD.set_house_rule("max_open_positions", 10, "t")
    assert not FD.execute("pod_trend", _trade("NEW", 100), st)["ok"]                        # 10 simboli gia' aperti o in coda
    assert FD.execute("pod_trend", _trade("AAPL", 100), st)["ok"]                           # aggiungere a uno gia' aperto resta possibile


def test_free_desk_rejects_unknown_side(alpaca):
    st = FD.state()
    for lato in ("long", "compra", "", None, "short"):
        x = FD.execute("pod_trend", _trade("AAPL", 1000, lato=lato), st)
        assert not x["ok"] and "lato" in x["motivo"], lato                                  # prima: tutto cio' che non era "buy" diventava una vendita allo scoperto
    assert not alpaca.posts()
    assert FD.execute("pod_trend", _trade("AAPL", 1000, lato=" SELL "), st)["ok"] and alpaca.posts()[-1]["side"] == "sell"


# =============================================================================================== H6: gateway con i limiti di produzione
@pytest.fixture()
def prod_firm(prod_env):
    from firm import gateway, pods
    org_seed.seed(); registry.sync(); pods.ensure_pods()
    for s in ("AAPL", "MSFT", "NVDA", "AMZN"):
        gateway.set_price(s, 100.0, "stock")
    return gateway


def _order(gw, side, sym, qty, pod="trend", why="prova dei limiti di produzione"):
    return gw.submit_order(pod, f"pod_{pod}", sym, side, qty, why, "1d", now=TUE)


def test_short_concentration_and_gross_are_checked_on_absolute_exposure(prod_firm):
    gw = prod_firm
    cap = gw.pod_book("trend")["capitale_ammesso"]                                          # ~5.000 EUR
    r = _order(gw, "BUY", "AAPL", 0.30 * cap / 100)
    assert r["status"] == "respinto" and any("concentrazione" in x for x in r["reasons"])
    r = _order(gw, "SELL", "AAPL", 1.9 * cap / 100)                                         # prima: short del 190% del capitale in UN titolo, accettato
    assert r["status"] == "respinto" and any("concentrazione" in x for x in r["reasons"])
    assert _order(gw, "SELL", "AAPL", 0.25 * cap / 100)["status"] == "accettato"            # lo short e' ammesso, dentro lo stesso 25% dei long
    gw.flush()
    assert gw.positions("trend")["AAPL"] < 0
    r = _order(gw, "SELL", "AAPL", 0.05 * cap / 100)                                        # aumentare lo short oltre il 25%: no
    assert r["status"] == "respinto" and any("concentrazione" in x for x in r["reasons"])
    # lorda di societa' sull'esposizione assoluta: con il limite a un soffio dall'esposizione attuale uno short in piu' non passa
    from firm import settings
    import yaml
    lim = settings.risk_limits(); lim["firm"]["max_gross"] = gw._firm_gross_eur() / gw.firm_nav_estimate() + 1e-4
    yaml.safe_dump(lim, open(settings.RISK_FILE, "w"))
    r = _order(gw, "SELL", "MSFT", 0.20 * cap / 100)
    assert r["status"] == "respinto" and any("lorda di societa'" in x for x in r["reasons"])   # prima: il controllo valeva solo per gli acquisti


def test_reducing_orders_pass_in_drawdown_and_closed_pod_is_liquidated(prod_firm):
    from firm import pods
    gw = prod_firm
    cap = gw.pod_book("trend")["capitale_ammesso"]
    for s in ("AAPL", "MSFT", "NVDA", "AMZN"):
        assert _order(gw, "SELL", s, 0.25 * cap / 100)["status"] == "accettato"             # quattro short dentro i limiti: lorda 100%
    gw.flush()
    for s in ("AAPL", "MSFT", "NVDA", "AMZN"):
        gw.set_price(s, 110.0, "stock")                                                     # +10% contro: drawdown del pod oltre la soglia di chiusura
    assert gw.pod_book("trend")["drawdown"] <= -S.risk_limits()["pod"]["dd_close"]
    r = _order(gw, "SELL", "AAPL", 1.0)
    assert r["status"] == "respinto" and any("drawdown" in x for x in r["reasons"])         # aumentare il rischio in drawdown: no
    r = _order(gw, "BUY", "AAPL", 0.10 * cap / 100, why="copertura parziale dello short in perdita")
    assert r["status"] == "accettato"                                                       # prima: respinto, lo short restava aperto a perdere
    r = _order(gw, "BUY", "MSFT", 0.50 * cap / 100)
    assert r["status"] == "respinto"                                                        # girare la posizione (da short a long) non e' "ridurre"
    acts = pods.apply_drawdown_rules(now=TUE)
    assert pods.get("trend")["status"] == "chiuso" and [a for a in acts if a["pod"] == "trend"][0]["liquidazione"]
    gw.flush()
    assert gw.positions("trend") == {}                                                      # prima: pod 'chiuso' con gli short ancora aperti e ogni ordine respinto
    assert _order(gw, "BUY", "AAPL", 1.0)["status"] == "respinto"                           # a pod chiuso e senza posizioni non si apre niente
    assert all(a["pod"] != "trend" for a in pods.apply_drawdown_rules(now=TUE))             # niente da liquidare due volte


# =============================================================================================== Quant H6: taglio delle aspettative
def test_realistic_case_is_never_better_than_model_with_negative_history(firm_env):
    from firm import expectations as X
    n = 1500
    idx = pd.bdate_range("2019-01-01", periods=n)
    rng = np.random.default_rng(3)
    px = lambda mu, sd: 100 * np.exp(np.cumsum(rng.normal(mu, sd, n)))
    close = pd.DataFrame({"SPY": px(-0.0008, 0.010), "AAA": px(-0.0010, 0.018), "^IRX": np.full(n, 3.0)}, index=idx)    # storia in perdita
    b = X.build(1_000_000, weights=dict(SPY=0.7, AAA=0.5), close=close)
    assert b["modello"]["rendimento_mediano"] < 0                                           # la media storica e' negativa
    assert b["realistico"]["finale"]["50"] < b["modello"]["finale"]["50"]                   # prima: il "realistico" usciva MIGLIORE del modello
    assert b["realistico"]["p_perdita"] >= b["modello"]["p_perdita"]


# =============================================================================================== Quant M3: le crypto hanno 365 giorni
def test_crypto_trials_and_backtest_are_annualised_on_365_days(firm_env, monkeypatch):
    from firm import strategies as ST, trials
    from quantlab import stats as QS
    r = np.random.default_rng(1).normal(0.001, 0.02, 730)                                   # due anni di giorni di CALENDARIO
    hyp = "ipotesi scritta prima della prova, abbastanza lunga"
    tid = trials.register("senior_crypto", "crypto4:prova", "crypto4", dict(a=1), hyp)
    d = trials.record_result(tid, r, periods=365)
    sr = QS.moments(r).sr
    assert d["sharpe_annuo"] == pytest.approx(sr * math.sqrt(365)) and d["min_trl_anni"] == pytest.approx(QS.min_trl(QS.moments(r)) / 365)
    assert trials.gate(tid, lookahead_ok=True)["controlli"]["anni_di_storia"]["valore"] == 2.0      # prima: 730 / 252 = 2,9 "anni"
    tid2 = trials.register("head_research", "gervaq4:prova", "gervaq4", dict(a=2), hyp)             # chi non dichiara nulla resta su 252
    assert trials.record_result(tid2, r[:504])["sharpe_annuo"] == pytest.approx(QS.moments(r[:504]).sr * math.sqrt(252))
    assert trials.gate(tid2, lookahead_ok=True)["controlli"]["anni_di_storia"]["valore"] == 2.0
    # la strategia crypto in codice: stesso calendario nel riepilogo e nella prova registrata
    n = 24 * 200
    idx = pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(3)
    c = pd.DataFrame({k: 100 * np.exp(np.cumsum(np.sign(np.sin(np.arange(n) / (300 + 50 * i))) * 0.0004 + rng.normal(0, 0.006, n)))
                      for i, k in enumerate(["BTC", "ETH", "SOL"])}, index=idx)
    monkeypatch.setitem(ST.STRATS["crypto_tsmom"]["params"], "coins", list(c))
    res = ST.backtest("crypto_tsmom", data=c, propose=False)
    daily = ST.to_daily(ST.bt_crypto_tsmom(c, dict(ST.STRATS["crypto_tsmom"]["params"])))
    assert res["risultati"]["sharpe"] == pytest.approx(float(daily.mean() / daily.std() * math.sqrt(365)), abs=2e-3)   # prima: radice di 252
    assert trials.periods_of(db.one("SELECT result FROM trials WHERE id=?", (res["prova"],))) == 365


# =============================================================================================== H4 / M6: sleeve, weekend e giorni veri
def test_weekend_events_are_not_dropped_from_sleeves(firm_env):
    from firm import sleeves as SL
    ev = [("2026-11-06T10:00:00Z", 100.0), ("2026-11-07T10:00:00Z", -5000.0), ("2026-11-08T10:00:00Z", -3000.0)]   # venerdi', sabato, domenica
    s = SL._event_series(ev, 100000.0)
    assert float(s.sum()) == pytest.approx(-0.079)                                          # prima: +0,001 (le perdite del weekend sparivano)
    assert s[pd.Timestamp("2026-11-07")] == pytest.approx(-0.05) and s[pd.Timestamp("2026-11-08")] == pytest.approx(-0.03)
    assert (s.index[1] - s.index[0]).days == 1 and len(s) >= 3                              # calendario a 7 giorni, giorni vuoti = 0


def test_genuine_big_day_stays_in_engine_series_and_glitches_do_not(firm_env):
    from firm import sleeves as SL
    days = ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"]
    for d, v in zip(days, [1000000, 1005000, 750000, 754000, 752000]):                      # -25% in un giorno, e il conto RESTA li': e' vero
        db.ex("INSERT OR REPLACE INTO nav_marks(day,pod,nav,capital,gross) VALUES(?,?,?,?,?)", (d, "pod_zero", v, 1.0, 0.0))
    r, bad = SL.engine_series()
    assert bad == 0 and r.min() == pytest.approx(750000 / 1005000 - 1) and len(r) == 4      # prima: scartato, il calo massimo usciva -0,3%
    assert SL.metrics(r)["calo_massimo"] < -0.25
    for d, v in zip(days, [970000, 970500, 86000, 971000, 971200]):                         # lettura sbagliata: salta e torna
        db.ex("INSERT OR REPLACE INTO nav_marks(day,pod,nav,capital,gross) VALUES(?,?,?,?,?)", (d, "pod_zero", v, 1.0, 0.0))
    r, bad = SL.engine_series()
    assert bad == 2 and r.abs().max() < 0.01 and len(r) == 3                                # la lettura si toglie, il rendimento vero tra i due giorni buoni resta
    db.ex("INSERT OR REPLACE INTO nav_marks(day,pod,nav,capital,gross) VALUES(?,?,?,?,?)", ("2026-11-07", "pod_zero", 700000, 1.0, 0.0))
    r, bad = SL.engine_series()
    assert bad == 3 and r.abs().max() < 0.01                                                # salto nell'ultima lettura: in attesa di conferma, contato


# =============================================================================================== H4: prima si entra, poi si conta
def test_target_counts_only_after_the_entry_price_was_touched(firm_env, monkeypatch):
    from firm import futures_sim as FS, signals as SG
    never = [[1, "104", "106.5", "103.5", "106", "0"]]                                      # apre a 104 e sale a 106,5: a 100 non si e' mai scambiato
    liq = FS.liq_price(100.0, "long", 10)
    assert SG.first_touch(never, True, 95.0, 106.0, entry=100.0) is None                    # prima: ("obiettivo", 1), un guadagno mai esistito
    assert FS.first_event(never, "long", 95.0, 106.0, liq, entry=100.0) is None
    path = never + [[2, "106", "106.2", "99.5", "100.5", "0"], [3, "100.5", "106.4", "100.2", "106", "0"]]   # scende a 100 (entra), poi sale
    assert SG.first_touch(path, True, 95.0, 106.0, entry=100.0) == ("obiettivo", 3)
    assert FS.first_event(path, "long", 95.0, 106.0, liq, entry=100.0) == ("obiettivo", 106.0, 3)
    crash = [[1, "104", "104.5", "94", "94.5", "0"]]                                        # passa dall'ingresso e arriva allo stop nella stessa candela: stop
    assert SG.first_touch(crash, True, 95.0, 106.0, entry=100.0) == ("stop", 1)
    spike = [[1, "104", "106.5", "99.8", "100", "0"]]                                       # obiettivo e ingresso nella stessa candela, aperta SOPRA l'ingresso: ordine ignoto
    assert SG.first_touch(spike, True, 95.0, 106.0, entry=100.0) is None
    assert SG.first_touch([[1, "100", "106.5", "99.9", "106", "0"]], True, 95.0, 106.0, entry=100.0) == ("obiettivo", 1)   # aperta all'ingresso: entrato subito
    assert SG.first_touch(never, False, 110.0, 103.6, entry=108.0) is None                  # vale anche per gli short
    # conto futures simulato: una posizione mai entrata scade a zero e non entra nelle statistiche
    p = dict(ok=True, moneta="SOL", direzione="long", ingresso=100.0, stop=95.0, obiettivi=[106.0], leva_max=10)
    FS.open_position(1, p, dict(leva=10, margine_pct=5))
    monkeypatch.setattr(SG, "_candles", lambda coin, since: never)
    assert FS.track() == 0 and db.one("SELECT stato FROM fut_positions")["stato"] == "aperta"           # prima: chiusa come obiettivo, +60% sul margine
    db.ex("UPDATE fut_positions SET ts='2026-10-01T00:00:00Z'")                             # oltre la durata del segnale
    assert FS.track() == 1
    r = db.one("SELECT * FROM fut_positions")
    assert r["esito"] == "non_entrato" and r["pnl_usd"] == 0.0 and FS.equity() == FS.equity0()
    assert all(b["n"] == 0 for b in FS.stats_by_leverage()) and FS.overview()["chiuse"] == 0


def test_observed_signal_never_entered_is_not_a_win_but_executed_one_still_closes(firm_env, monkeypatch):
    from firm import signals as SG
    never = [[1, "104", "106.5", "103.5", "106", "0"]]
    monkeypatch.setattr(SG, "_candles", lambda coin, since: never)
    idx = pd.bdate_range(end=dt.date.today() + dt.timedelta(days=3), periods=120)
    close = pd.DataFrame({"SOL": np.full(120, 104.0)}, index=idx)
    par = json.dumps(dict(ok=True, moneta="SOL", direzione="long", ingresso=100.0, stop=95.0, obiettivi=[106.0]))
    far = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    for stato, peso in (("osservato", 0.0), ("accettato", 0.02)):
        db.ex("INSERT INTO signals(ts,fonte,testo,stato,parsed,controlli,peso,scade) VALUES(?,?,?,?,?,?,?,?)",
              (db.now_iso(), "prova", "BUY SOL", stato, par, json.dumps(dict(prezzo=104.0)), peso, far))
    assert SG.track(close) == 1                                                              # solo quello ESEGUITO si chiude: e' nel conto, l'obiettivo lo vende
    rows = {r["peso"]: r for r in db.q("SELECT * FROM signals")}
    assert rows[0.02]["stato"] == "chiuso" and rows[0.02]["esito"] == "obiettivo"
    assert rows[0.0]["stato"] == "osservato"                                                 # prima: chiuso come obiettivo, +1,2 R mai guadagnati
    db.ex("UPDATE signals SET scade='2026-01-01' WHERE stato='osservato'")
    assert SG.track(close) == 1
    r = db.one("SELECT * FROM signals WHERE peso=0")
    assert r["esito"] == "non_entrato" and r["r_multiple"] == 0.0
    st = SG.stats()
    assert st["non_entrati"] == 1 and st["chiusi"] == 1 and st["tasso_obiettivo"] == 1.0   # il mai entrato non e' un'operazione
