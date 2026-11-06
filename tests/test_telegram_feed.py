"""Telegram: solo i messaggi che sembrano segnali, senza doppioni, con un tetto orario; il testo resta dato non fidato."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from firm import db, org_seed, registry, signals as SG, telegram_feed as TG


NOW = dt.datetime.now(dt.timezone.utc)
TEXT = "BUY SOL entry 150 SL 140 TP1 165 TP2 180"


def _close(n=300, last=150.0):
    idx = pd.bdate_range(end=dt.date.today(), periods=n)
    rng = np.random.default_rng(5)
    px = last * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    return pd.DataFrame({"SOL": px * (last / px[-1]), "SPY": px, "^VIX": np.full(n, 20.0)}, index=idx)


def _agents(monkeypatch, decisione="accetta"):
    from llm import runtime

    def call(agent, task, **kw):
        if agent == "senior_crypto":
            return dict(ok=True, output=dict(decisione=decisione, probabilita_tp1=0.6, peso_pct=2.0, motivo="ok", rischi=[], invalidazione="x"))
        if agent == "cro":
            return dict(ok=True, output=dict(veto=False, motivo="ok"))
        return dict(ok=False, motivo="no")
    monkeypatch.setattr(runtime, "call", call)
    monkeypatch.setattr(SG, "_series", lambda coin, close=None: _close()[coin] if coin in _close() else None)
    monkeypatch.setattr(SG.charts, "load_close", lambda: _close())


def test_filter_ignores_chatter_and_ads():
    assert TG.looks_like_signal(TEXT)
    assert TG.looks_like_signal("#BTC LONG @ 67500 SL 65000 TP 71000")
    assert not TG.looks_like_signal("Buongiorno a tutti! Oggi SOL sale, che bel mercato")           # niente livelli
    assert not TG.looks_like_signal("Iscriviti al VIP, BUY now!! entry gratis")                      # nessuna moneta
    assert not TG.looks_like_signal("BUY SHIB entry 1 SL 0.5 TP 2")                                  # moneta non ammessa


def test_dedupe_rate_limit_and_old_messages(firm_env, monkeypatch):
    org_seed.seed(); registry.sync(); _agents(monkeypatch)
    assert TG.handle_message("ciao a tutti", "Sala", NOW, NOW, background=False)["azione"] == "ignorato"
    old = NOW - dt.timedelta(hours=2)
    assert TG.handle_message(TEXT, "Sala", old, NOW, background=False)["azione"] == "troppo_vecchio"
    r = TG.handle_message(TEXT, "Sala crypto", NOW, NOW, background=False)
    assert r["azione"] == "inviato"
    s = db.one("SELECT * FROM signals WHERE id=?", (r["id"],))
    assert s["fonte"] == "Telegram: Sala crypto" and s["stato"] == "accettato"
    assert TG.handle_message("  buy sol   ENTRY 150 sl 140   tp1 165 tp2 180 ", "Sala", NOW, NOW, background=False)["azione"] == "doppione"
    db.ex("UPDATE settings SET value=value WHERE 0")
    from firm import settings as S
    S.set("signals.telegram_max_per_hour", 1, S.AndreaCapability(S.ensure_token()))
    assert TG.handle_message("BUY ETH entry 3000 SL 2900 TP1 3200", "Sala", NOW, NOW, background=False)["azione"] == "limite_orario"


def test_execution_can_be_switched_off(firm_env, monkeypatch):
    org_seed.seed(); registry.sync(); _agents(monkeypatch)
    from firm import settings as S
    S.set("signals.telegram_execute", False, S.AndreaCapability(S.ensure_token()))
    r = TG.handle_message(TEXT, "Sala", NOW, NOW, background=False)
    s = db.one("SELECT * FROM signals WHERE id=?", (r["id"],))
    assert s["stato"] == "osservato" and SG.active_targets() == {}                                     # si segue, non si esegue


def test_session_and_hash_are_filtered_from_prompts(monkeypatch):
    from llm import redact
    monkeypatch.setenv("TELEGRAM_API_HASH", "0123456789abcdef0123456789abcdef")
    assert "0123456789abcdef" not in redact.text("hash 0123456789abcdef0123456789abcdef nel testo")


@pytest.fixture(autouse=True)
def _crypto_on(firm_env):
    """Questi test descrivono la filiera con le crypto eseguibili (il conto paper reale oggi non lo consente)."""
    from firm import settings as S
    S.set("crypto.eseguibile", True, S.AndreaCapability(S.ensure_token()))
