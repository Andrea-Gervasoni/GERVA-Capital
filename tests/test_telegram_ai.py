"""Sala Telegram con l'AI: non tutti i messaggi sono segnali. L'AI li capisce; il resto della filiera (controlli, analisi, veto, tetti) resta del codice."""
import datetime as dt

import pytest

from firm import db, org_seed, registry, signals as SG, telegram_feed as TG
from tests.test_telegram_feed import _close  # noqa: F401  (stessi prezzi finti)

NOW = dt.datetime.now(dt.timezone.utc)


def _reset():
    TG._CTX.clear(); TG._AI_CALLS.clear(); TG._SEEN_AI.clear()


def _ai(monkeypatch, answers, calls=None):
    """Un'AI finta che risponde secondo il testo del messaggio nuovo; registra cosa le e' stato mostrato."""
    from llm import runtime

    def call(agent, task, **kw):
        if calls is not None:
            calls.append((agent, kw.get("purpose"), kw.get("untrusted")))
        if kw.get("purpose") == "interpreta:telegram":
            new = (kw.get("untrusted") or "").split("MESSAGGIO NUOVO:\n")[-1]
            for key, out in answers.items():
                if key in new:
                    return dict(ok=True, output=dict(dict(confidenza=0.95, moneta="", direzione="long", ingresso=0, stop=0, obiettivi=[], a_mercato=False, testo_segnale="", motivo="x"), **out))
            return dict(ok=False, motivo="nessuna regola")
        return dict(ok=False, motivo="no")
    monkeypatch.setattr(runtime, "call", call)


def test_chatter_ads_and_results_are_not_signals(firm_env, monkeypatch):
    org_seed.seed(); registry.sync(); _reset()
    _ai(monkeypatch, {"Buongiorno": dict(tipo="chiacchiere"), "VIP": dict(tipo="pubblicita"), "raggiunto": dict(tipo="risultato", moneta="SOL")})
    for t in ("Buongiorno a tutti, che mercato oggi!", "Iscriviti al VIP per segnali garantiti", "SOL TP1 raggiunto +8%, complimenti a chi era dentro"):
        assert TG.handle_message(t, "Sala AI", NOW, NOW, background=False, ai=True)["azione"] in ("chiacchiere", "pubblicita", "risultato")
    assert db.one("SELECT COUNT(*) n FROM signals")["n"] == 0                                   # nessuno entra nella sala segnali
    log = db.runtime_get("telegram.ai_log")
    assert [x["tipo"] for x in log] == ["risultato", "pubblicita", "chiacchiere"]               # ma ogni lettura resta visibile


def test_signal_split_in_two_messages_is_reassembled(firm_env, monkeypatch):
    org_seed.seed(); registry.sync(); _reset()
    seen = []
    _ai(monkeypatch, {"SOL long": dict(tipo="analisi", motivo="solo un annuncio, nessun livello"),
                      "Entry": dict(tipo="segnale", moneta="SOL", direzione="long", ingresso=150, stop=140, obiettivi=[165, 180], testo_segnale="SOL long entry 150 SL 140 TP1 165 TP2 180")}, seen)
    monkeypatch.setattr(SG, "process", lambda sid, execute=True, pre=None: seen.append(("process", pre)) or dict(id=sid))
    assert TG.handle_message("SOL long, preparatevi", "Sala AI", NOW, NOW, background=False, ai=True)["azione"] == "analisi"      # solo l'annuncio: non e' ancora un segnale
    TG._SEEN_AI.clear()
    r = TG.handle_message("Entry 150 / SL 140 / TP 165 - 180", "Sala AI", NOW, NOW, background=False, ai=True)
    assert r["azione"] == "inviato"
    ctx = [x for x in seen if x[0] == "crypto_analyst"][-1][2]
    assert "SOL long, preparatevi" in ctx and "Entry 150" in ctx                                   # l'AI ha visto anche il messaggio di prima
    pre = [x for x in seen if x[0] == "process"][-1][1]
    assert pre["moneta"] == "SOL" and pre["stop"] == 140
    assert db.one("SELECT testo FROM signals ORDER BY id DESC LIMIT 1")["testo"].startswith("SOL long entry 150")   # il segnale e' ricomposto per intero


def test_market_signal_updates_and_low_confidence(firm_env, monkeypatch):
    org_seed.seed(); registry.sync(); _reset()
    _ai(monkeypatch, {"adesso": dict(tipo="segnale", moneta="BTC", a_mercato=True, testo_segnale="BTC long adesso"),
                      "pareggio": dict(tipo="aggiornamento", moneta="BTC", motivo="sposta lo stop a pareggio"),
                      "forse": dict(tipo="segnale", confidenza=0.4, moneta="ETH", motivo="sembra un'opinione")})
    got = []
    monkeypatch.setattr(SG, "process", lambda sid, execute=True, pre=None: got.append(pre) or db.ex("UPDATE signals SET stato='osservato', parsed=? WHERE id=?", ('{"moneta": "BTC"}', sid)) or dict(id=sid))
    assert TG.handle_message("BTC long adesso, ingresso a mercato", "Sala AI", NOW, NOW, background=False, ai=True)["azione"] == "inviato"
    assert got[0]["a_mercato"] is True                                                             # arriva alla filiera come segnale a mercato
    assert TG.handle_message("BTC: sposto lo stop a pareggio", "Sala AI", NOW, NOW, background=False, ai=True)["azione"] == "aggiornamento"
    assert "sposta lo stop a pareggio" in db.one("SELECT motivo FROM signals ORDER BY id DESC LIMIT 1")["motivo"]    # annotato sul segnale aperto
    assert TG.handle_message("forse ETH sale oggi, vedremo", "Sala AI", NOW, NOW, background=False, ai=True)["azione"] == "dubbio"   # troppo incerto: non entra


def test_ai_down_never_loses_an_obvious_signal_and_cap(firm_env, monkeypatch):
    org_seed.seed(); registry.sync(); _reset()
    _ai(monkeypatch, {})                                                                           # l'AI non risponde a nulla
    monkeypatch.setattr(SG, "process", lambda sid, execute=True, pre=None: dict(id=sid))
    assert TG.handle_message("ciao a tutti ragazzi", "Sala AI", NOW, NOW, background=False, ai=True)["azione"] == "ignorato"
    assert TG.handle_message("BUY SOL entry 150 SL 140 TP1 165 TP2 180", "Sala AI", NOW, NOW, background=False, ai=True)["azione"] == "inviato"    # il filtro a parole chiave lo salva
    monkeypatch.setattr("firm.settings.get", lambda k, d=None: 1 if k == "signals.telegram_ai_max_per_hour" else (d if d is not None else 10))
    _reset()
    _ai(monkeypatch, {"uno": dict(tipo="chiacchiere"), "due": dict(tipo="chiacchiere")})
    TG.handle_message("messaggio uno qualunque", "Sala AI", NOW, NOW, background=False, ai=True)
    TG.handle_message("messaggio due qualunque", "Sala AI", NOW, NOW, background=False, ai=True)
    assert db.runtime_get("telegram.ai_log")[0]["tipo"] == "non_letto" or db.runtime_get("telegram.ai_log")[0]["tipo"] == "saltato"       # oltre il tetto: niente costo, vale il filtro


def test_health_counts_ai_rooms(firm_env, monkeypatch):
    from firm import health
    monkeypatch.delenv("TELEGRAM_CHATS", raising=False); monkeypatch.setenv("TELEGRAM_CHATS_AI", "Sala AI")
    assert any(p["nome"] == "Telegram" for p in health.status()["parti"])


def test_filtered_messages_leave_a_trace_and_diagnosis_reads_it(firm_env, monkeypatch):
    org_seed.seed(); registry.sync(); _reset()
    r = TG.handle_message("Che bella giornata oggi ragazzi, buon lavoro a tutti", "Sala filtro", NOW, NOW, background=False, ai=False)
    assert r["azione"] == "ignorato"
    x = db.runtime_get("telegram.ai_log")[0]
    assert x["tipo"] == "filtrato" and "nessuna moneta riconosciuta" in x["motivo"]                      # il motivo e' scritto, non sparisce
    out = TG.diagnose()
    assert "FILTRATO" in out and "Che bella giornata" in out


def test_plain_room_gives_second_chance_to_a_coin_message(firm_env, monkeypatch):
    """"Entrata a mercato su BTC adesso" non ha BUY/LONG: il filtro lo scarta, ma nomina una moneta, quindi lo legge l'AI."""
    org_seed.seed(); registry.sync(); _reset()
    _ai(monkeypatch, {"Entrata": dict(tipo="segnale", moneta="BTC", a_mercato=True, testo_segnale="BTC long a mercato adesso")})
    got = []
    monkeypatch.setattr(SG, "process", lambda sid, execute=True, pre=None: got.append(pre) or dict(id=sid))
    r = TG.handle_message("Entrata a mercato su BTC adesso", "Sala filtro", NOW, NOW, background=False, ai=False)
    assert r["azione"] == "inviato" and got[0]["a_mercato"] is True and got[0]["moneta"] == "BTC"


def test_any_alpaca_coin_is_accepted_with_alpaca_prices(firm_env, monkeypatch):
    """Le crypto si negoziano su Alpaca: una moneta fuori dalla lista di base (PEPE) non e' 'non ammessa su IBKR'."""
    import numpy as np
    import pandas as pd
    from firm import crypto_venue as V
    from llm import runtime
    org_seed.seed(); registry.sync(); _reset()
    monkeypatch.setattr(V, "keys_ok", lambda: True)
    monkeypatch.setattr(V, "supported", lambda: {"BTC", "PEPE", "SOL"})
    monkeypatch.setattr(V, "accepting", lambda: False)                                             # nessuna esecuzione: qui si prova l'ammissione
    assert "PEPE" in SG.allowed_coins() and SG.first_coin("buy pepe e anche btc, entry 1") == "PEPE"        # la prima nominata e' quella del segnale
    idx = pd.bdate_range(end=dt.date.today(), periods=300)
    rng = np.random.default_rng(2)
    base = pd.DataFrame({"SOL": 150 * np.exp(np.cumsum(rng.normal(0, 0.02, 300))), "SPY": np.full(300, 500.0), "^VIX": np.full(300, 20.0)}, index=idx)
    pepe = pd.Series(0.00001 * np.exp(np.cumsum(rng.normal(0, 0.04, 300))), index=idx)
    monkeypatch.setattr(SG.charts, "load_close", lambda: base)
    monkeypatch.setattr(SG, "_alpaca_daily", lambda coin: pepe if coin == "PEPE" else None)
    monkeypatch.setattr(V, "last_price", lambda s: float(pepe.iloc[-1]))

    def call(agent, task, **kw):
        if agent == "senior_crypto":
            return dict(ok=True, output=dict(decisione="accetta", probabilita_tp1=0.55, peso_pct=1.0, motivo="ok", rischi=[], invalidazione="x"))
        if agent == "cro":
            return dict(ok=True, output=dict(veto=False, motivo="ok"))
        return dict(ok=False, motivo="no")
    monkeypatch.setattr(runtime, "call", call)
    sid = SG.create("PEPE long a mercato adesso", "Telegram: Sala")
    r = SG.process(sid, execute=False, pre=dict(moneta="PEPE", direzione="long", ingresso=0, stop=0, obiettivi=[], a_mercato=True))
    row = db.one("SELECT stato, controlli FROM signals WHERE id=?", (sid,))
    assert "non negoziabile" not in (row["controlli"] or "") and "nessun dato di prezzo" not in (row["controlli"] or "")
    assert r["stato"] in ("osservato", "accettato")                                                 # analizzato davvero, non scartato per la moneta


ATOM = ("ATOMUSDT ® Impostazioni di Trading Modalità Margine: Isolato Leva Consigliata: Minima: 3x Massima: 8x Tipo Ordine: Mercato "
        "Range (CMP): 1.335-1.34 • Quantità da Investire: Inserisci l'importo desiderato. Stop Loss: 1.40 Take Profit: 0.8563 short")
FIL = "FILUSDT Impostazioni di Trading Modalità Margine: Isolato Leva Consigliata: Minima: 3x Massima: 8x Tipo Ordine: Mercato Range (CMP): 0.77-0.775 long"


def _futures_env(monkeypatch):
    import numpy as np
    import pandas as pd
    from firm import crypto_venue as V
    from llm import runtime
    monkeypatch.setattr(V, "keys_ok", lambda: True)
    monkeypatch.setattr(V, "supported", lambda: {"BTC", "ETH", "SOL"})                              # ATOM e FIL non sono su Alpaca
    monkeypatch.setattr(V, "accepting", lambda: True)
    idx = pd.bdate_range(end=dt.date.today(), periods=300)
    rng = np.random.default_rng(4)
    base = pd.DataFrame({"SOL": 150 * np.exp(np.cumsum(rng.normal(0, 0.02, 300))), "SPY": np.full(300, 500.0), "^VIX": np.full(300, 20.0)}, index=idx)
    px = {"ATOM": 1.3375, "FIL": 0.7725}
    pub = lambda c: pd.Series(px[c] * np.exp(np.cumsum(rng.normal(0, 0.03, 300)) - 0.0), index=idx) * (px[c] / 1.0) / (px[c]) if False else pd.Series(
        px[c] * np.exp(np.cumsum(rng.normal(0, 0.03, 300))), index=idx).pipe(lambda s: s * (px[c] / float(s.iloc[-1])))
    monkeypatch.setattr(SG.charts, "load_close", lambda: base)
    monkeypatch.setattr(SG, "_alpaca_daily", lambda coin: None)
    monkeypatch.setattr(SG, "_public_daily", lambda coin: pub(coin) if coin in px else None)

    def call(agent, task, **kw):
        if agent == "senior_crypto":
            return dict(ok=True, output=dict(decisione="accetta", probabilita_tp1=0.5, peso_pct=1.0, motivo="ok", rischi=[], invalidazione="x"))
        if agent == "cro":
            return dict(ok=True, output=dict(veto=False, motivo="ok"))
        return dict(ok=False, motivo="no")
    monkeypatch.setattr(runtime, "call", call)


def test_futures_signals_on_coins_alpaca_does_not_have_are_followed_not_discarded(firm_env, monkeypatch):
    """ATOMUSDT (short) e FILUSDT (long, a mercato, senza stop ne' obiettivi): non si eseguono su Alpaca ma si seguono e si misurano."""
    org_seed.seed(); registry.sync(); _reset(); _futures_env(monkeypatch)
    assert SG.first_coin(ATOM) == "ATOM" and SG.first_coin(FIL) == "FIL"
    p = SG.parse(ATOM)
    assert p["moneta"] == "ATOM" and p["direzione"] == "short" and abs(p["ingresso"] - 1.3375) < 1e-6 and p["stop"] == 1.4        # "1.335-1.34": un intervallo, letto bene
    for txt in (ATOM, FIL):
        sid = SG.create(txt, "sala segnali")
        r = SG.process(sid, execute=True)
        row = db.one("SELECT parsed, controlli, motivo FROM signals WHERE id=?", (sid,))
        assert r["stato"] == "osservato", (r, row["controlli"])
        assert "IBKR" not in (r["motivo"] or "") and "non negoziabile su Alpaca" in r["motivo"] and "si segue e si misura" in r["motivo"]
    import json
    parsed = json.loads(db.one("SELECT parsed FROM signals WHERE id=?", (sid,))["parsed"])
    assert parsed["ok"] and abs(parsed["ingresso"] - 0.7725) < 0.2 and parsed["stop"] < parsed["ingresso"] < parsed["obiettivi"][0]      # FIL: livelli calcolati dal desk


def test_no_message_names_ibkr_for_crypto():
    import inspect
    src = inspect.getsource(SG)
    assert "non ammessa su IBKR" not in src and "non su IBKR" not in src and "IBKR paper le rifiuta" not in src


def test_intraday_touch_catches_a_fast_move_that_daily_closes_miss():
    """+6% in meno di un'ora e poi il prezzo torna indietro: la chiusura giornaliera non lo vede, i massimi di 15 minuti si'."""
    rows = [[0, "1.00", "1.01", "0.99", "1.00"], [900_000, "1.00", "1.02", "1.00", "1.02"], [1_800_000, "1.02", "1.065", "1.02", "1.06"], [2_700_000, "1.06", "1.06", "0.97", "0.98"]]
    assert SG.first_touch(rows, True, 0.95, 1.06) == ("obiettivo", 1_800_000)                      # obiettivo +6% toccato alla terza candela
    assert SG.first_touch(rows, False, 1.05, 0.97) == ("stop", 1_800_000)                          # per uno short lo stop sopra viene toccato prima
    both = [[0, "1", "1.07", "0.94", "1"]]
    assert SG.first_touch(both, True, 0.95, 1.06) == ("stop", 0)                                   # entrambi nella stessa candela: stima prudente
