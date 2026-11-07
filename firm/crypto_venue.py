"""
Sede delle crypto: Alpaca PAPER (conto simulato con prezzi veri, aperto 24 ore su 24, sette giorni su sette).

Perche': il conto paper di IBKR rifiuta le crypto ("calcolo del margine non disponibile", 6/11) e non si puo' scegliere quando
operare. Qui gli ordini partono quando serve: ogni battito (15 minuti) e subito dopo che un segnale e' accettato.

Chi fa cosa: l'obiettivo e' lo stesso del resto della societa' (modello crypto di GERVA-Q gia' scalato + posizioni dei segnali accettati,
con i loro tetti), espresso in frazione del valore del conto Alpaca; il codice confronta con le posizioni vere e invia ordini a mercato.

Sicurezza (non aggirabile dagli agenti):
  * SOLO paper: l'indirizzo e' fisso (paper-api.alpaca.markets); non esiste nel codice nessun indirizzo di conto reale;
  * le chiavi stanno in .env (ALPACA_PAPER_KEY, ALPACA_PAPER_SECRET), mai nei log: llm/redact le maschera;
  * se il conto non risponde o il valore non e' leggibile, nessun ordine; tetto sul totale crypto (crypto.venue_max_frac);
  * ordini sotto la soglia (crypto.venue_min_trade_usd) o dentro la banda dello 0,5% del conto non si inviano (niente rumore).
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request

from . import audit, db, events
from . import settings as S

BASE = "https://paper-api.alpaca.markets"
BAND = 0.005


def configured() -> bool:
    return S.get("crypto.venue", "none") == "alpaca" and bool(os.environ.get("ALPACA_PAPER_KEY")) and bool(os.environ.get("ALPACA_PAPER_SECRET"))


def accepting() -> bool:
    """I segnali crypto possono entrare nel conto: o IBKR le compra, o c'e' la sede Alpaca pronta."""
    return bool(S.get("crypto.eseguibile", False)) or configured()


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _req(method: str, path: str, body: dict | None = None, timeout: int = 15):
    base = os.environ.get("ALPACA_BASE_URL", BASE).rstrip("/")
    if base != BASE:
        raise RuntimeError("solo il conto paper di Alpaca e' ammesso (ALPACA_BASE_URL diverso dal paper)")
    req = urllib.request.Request(base + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"APCA-API-KEY-ID": os.environ["ALPACA_PAPER_KEY"], "APCA-API-SECRET-KEY": os.environ["ALPACA_PAPER_SECRET"],
                                          "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Alpaca {e.code}: {e.read().decode('utf-8', 'replace')[:200]}") from None


def account() -> dict:
    return _req("GET", "/v2/account")


def positions() -> dict[str, float]:
    """{moneta: valore in USD} (le posizioni crypto di Alpaca hanno simbolo tipo BTCUSD)."""
    out = {}
    for p in _req("GET", "/v2/positions"):
        sym = str(p.get("symbol", "")).replace("/", "")
        if p.get("asset_class") == "crypto" and sym.endswith("USD"):
            out[sym[:-3]] = float(p["market_value"])
    return out


def supported() -> set[str]:
    got = db.runtime_get("alpaca.assets")
    if got and got.get("ts", "")[:10] == db.now_iso()[:10]:
        return set(got["coins"])
    coins = sorted({a["symbol"].split("/")[0] for a in _req("GET", "/v2/assets?status=active&asset_class=crypto") if a.get("tradable") and "/USD" in a["symbol"]})
    db.runtime_set("alpaca.assets", dict(ts=db.now_iso(), coins=coins))
    return set(coins)


def targets() -> dict[str, float]:
    """Frazioni del conto: modello crypto di GERVA-Q (gia' scalato) + segnali accettati, con tetto sul totale."""
    from . import fundrisk, pod_zero
    t: dict[str, float] = {}
    if S.get("crypto.venue_mirror_model", True):
        for k, v in fundrisk._scaled(pod_zero.crypto_model()).items():
            t[k] = t.get(k, 0.0) + max(float(v), 0.0)
    ov = db.runtime_get("desk.overlay") or {}
    for k, v in (ov.get("crypto_targets") or {}).items():
        t[k] = t.get(k, 0.0) + float(v)
    cap = float(S.get("crypto.venue_max_frac", 0.60))
    tot = sum(t.values())
    if tot > cap > 0:
        t = {k: v * cap / tot for k, v in t.items()}
    return {k: round(v, 5) for k, v in t.items() if v > 0}


def plan(equity: float, have: dict[str, float], tgt: dict[str, float], ok_coins: set[str]) -> tuple[list[dict], list[str]]:
    """Ordini necessari (vendite prima). Funzione pura: facile da provare."""
    min_usd = float(S.get("crypto.venue_min_trade_usd", 25.0))
    orders, skipped = [], []
    for coin in sorted(set(have) | set(tgt)):
        want = tgt.get(coin, 0.0) * equity
        if coin not in ok_coins:
            if want > 0:
                skipped.append(f"{coin}: non supportata da Alpaca")
            continue
        diff = want - have.get(coin, 0.0)
        if abs(diff) < max(min_usd, BAND * equity) and not (want == 0 and have.get(coin, 0.0) > 0):
            continue
        orders.append(dict(coin=coin, side="buy" if diff > 0 else "sell", usd=round(abs(diff), 2), chiudi=want == 0))
    orders.sort(key=lambda o: o["side"] != "sell")
    return orders, skipped


def rebalance(dry: bool = False) -> dict:
    if not configured():
        return dict(ok=False, nota="sede crypto non attiva (crypto.venue = alpaca e chiavi ALPACA_PAPER_KEY/SECRET in .env)")
    try:
        acc = account()
        equity = float(acc["equity"])
        if acc.get("trading_blocked") or acc.get("account_blocked") or equity <= 0:
            return dict(ok=False, nota="conto Alpaca bloccato o senza valore: nessun ordine")
        have, tgt = positions(), targets()
        orders, skipped = plan(equity, have, tgt, supported())
    except Exception as e:                                             # fail-closed: non si opera al buio
        db.runtime_set("alpaca.state", dict(ts=db.now_iso(), errore=str(e)[:200]))
        return dict(ok=False, nota=f"sede crypto non raggiungibile: {str(e)[:120]}")
    sent = []
    for o in orders:
        if dry:
            sent.append(dict(o, esito="prova"))
            continue
        try:
            if o["chiudi"]:
                r = _req("DELETE", f"/v2/positions/{o['coin']}USD")
            else:
                r = _req("POST", "/v2/orders", dict(symbol=f"{o['coin']}/USD", side=o["side"], type="market", time_in_force="gtc", notional=f"{o['usd']:.2f}"))
            sent.append(dict(o, esito="inviato", id=str(r.get("id", ""))[:36]))
        except Exception as e:
            sent.append(dict(o, esito="rifiutato", motivo=str(e)[:150]))
    state = dict(ts=db.now_iso(), equity=round(equity, 2), cash=round(float(acc.get("cash", 0)), 2), posizioni={k: round(v, 2) for k, v in have.items()},
                 obiettivi=tgt, ordini=sent, saltate=skipped)
    db.runtime_set("alpaca.state", state)
    if sent and not dry:
        audit.log("crypto_venue", "alpaca.orders", dict(n=len(sent), ordini=sent))
        events.publish("alpaca.orders", "crypto_venue", dict(n=len(sent), ordini=sent))
    return dict(ok=True, **state)
