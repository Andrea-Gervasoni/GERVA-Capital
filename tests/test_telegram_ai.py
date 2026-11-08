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
