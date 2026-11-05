"""
Collegamento a Interactive Brokers (IB Gateway) — SOLO PAPER, con due ruoli separati.

1. OSSERVATORE del conto della sfida (GERVA-Q / Pod Zero): connessione `readonly=True` (a livello di
   API IBKR non puo' inviare ordini), legge NAV, posizioni ed eseguiti per il portale e il Rischio.
   Gli ordini del Pod Zero restano di live.py / crypto_live.py di GERVA-Q.

2. ESECUTORE dei pod (usato solo dal Gateway): opera su un SECONDO conto paper, diverso da quello della
   sfida. Perche' due conti:
     * live.py e crypto_live.py costruiscono gli ordini su TUTTE le posizioni del conto: cio' che non e'
       nel loro target viene venduto, quindi il Pod Zero liquiderebbe ogni sera le posizioni dei pod;
     * REGOLE_SFIDA §1: ogni sistema opera su un conto paper separato; i trade dei pod falserebbero
       il NAV della sfida con Kimi.
   Il codice lo impone: l'esecutore rifiuta un conto che non inizi con "DU" o che coincida con quello
   della sfida. Senza secondo conto i pod restano sul broker paper simulato (default sicuro).

Regole d'esecuzione: solo ordini LIMITE con prezzo protetto, orderRef univoco (idempotenza dopo una
riconnessione), attesa limitata e annullamento del residuo, cadenza di invio per non superare i limiti
di messaggi IBKR, KILL che annulla gli ordini aperti dei pod.
Le credenziali di IBKR non passano mai da qui: le custodisce IB Gateway (IBC). Questo modulo conosce
solo host, porta, clientId e numero di conto, e scrive il numero di conto nel DB solo mascherato.
"""
from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass

import yaml

from . import db, events, paths, risk

ORDER_PREFIX = "GERVA-CAP-"
PACING_S = 0.25                    # <= 4 ordini al secondo, molto sotto i limiti di messaggi di IBKR
FILL_TIMEOUT_S = 30.0


def mask(acct: str | None) -> str:
    return (acct[:2] + "****" + acct[-3:]) if acct and len(acct) > 5 else "****"


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int
    client_id: int
    account: str | None = None


def challenge_endpoint() -> Endpoint:
    return Endpoint(os.environ.get("IBKR_GERVAQ_HOST", "127.0.0.1"), int(os.environ.get("IBKR_GERVAQ_PORT", "4002")),
                    int(os.environ.get("IBKR_OBSERVER_CLIENT_ID", "32")), os.environ.get("IBKR_CHALLENGE_ACCOUNT") or None)


def firm_endpoint() -> Endpoint:
    return Endpoint(os.environ.get("IBKR_FIRM_HOST", "127.0.0.1"), int(os.environ.get("IBKR_FIRM_PORT", "4004")),
                    int(os.environ.get("IBKR_FIRM_CLIENT_ID", "31")), os.environ.get("IBKR_FIRM_ACCOUNT") or None)


def _default_factory():
    from ib_async import IB          # installato sul server / sul Mac (requirements-ibkr.txt)
    return IB()


# ---------------------------------------------------------------------------
# Anagrafica degli strumenti (config/instruments.yaml)
# ---------------------------------------------------------------------------
def instruments() -> dict:
    return yaml.safe_load(open(os.path.join(paths.CONFIG, "instruments.yaml")))


def contract_for(symbol: str, kind: str):
    from ib_async import Stock, Crypto
    spec = instruments().get(symbol, {})
    if kind == "crypto":
        return Crypto(symbol, spec.get("exchange", "PAXOS"), spec.get("currency", "USD"))
    if kind in ("etf_ucits", "etc"):
        if not spec:
            raise ValueError(f"{symbol}: strumento UCITS senza anagrafica in config/instruments.yaml")
        return Stock(symbol, spec["exchange"], spec["currency"])
    if kind == "stock":
        return Stock(symbol.replace("-", " "), "SMART", spec.get("currency", "USD"))
    raise ValueError(f"tipo non gestito: {kind}")


def round_qty(kind: str, qty: float) -> float:
    """Azioni ed ETF a pezzi interi (niente frazioni sugli UCITS); crypto a 6 decimali per difetto."""
    if kind == "crypto":
        return math.floor(qty * 1e6) / 1e6
    return float(math.floor(qty + 1e-9))


def limit_price(side: str, ref: float, kind: str) -> float:
    """Prezzo limite protetto: al massimo meta' della deviazione ammessa dal Gateway."""
    from . import settings as S
    dev = float(S.risk_limits()["order"]["max_price_deviation"]) / 2
    p = ref * (1 + dev) if side == "BUY" else ref * (1 - dev)
    return round(p, 2)


# ---------------------------------------------------------------------------
# Osservatore del conto della sfida (sola lettura)
# ---------------------------------------------------------------------------
def observe_challenge(factory=_default_factory, timeout: float = 15) -> dict:
    ep = challenge_endpoint()
    ib = factory()
    snap = dict(ok=False, ts=db.now_iso())
    try:
        ib.connect(ep.host, ep.port, clientId=ep.client_id, timeout=timeout, readonly=True)
        accts = ib.managedAccounts()
        acct = ep.account if ep.account in accts else (accts[0] if accts else None)
        if not acct or not acct.startswith("DU"):
            snap.update(errore="il conto della sfida non e' un conto paper (DU...): osservazione interrotta")
            events.publish("risk.alert", "ibkr", dict(cosa=snap["errore"], gravita=5))
            return snap
        vals = {(v.tag, v.currency): v.value for v in ib.accountValues(acct)}
        nav = float(vals.get(("NetLiquidation", "EUR")) or vals.get(("NetLiquidation", "BASE")) or 0)
        pos = [dict(simbolo=p.contract.localSymbol or p.contract.symbol, tipo=p.contract.secType,
                    qty=float(p.position), costo_medio=float(p.avgCost)) for p in ib.positions(acct)]
        snap.update(ok=True, conto=mask(acct), nav_eur=nav, posizioni=pos,
                    eseguiti_oggi=len(ib.fills()))
    except Exception as e:                       # gateway spento, rete, login: si registra, non si crasha
        snap.update(errore=f"{type(e).__name__}: {str(e)[:160]}")
    finally:
        try:
            ib.disconnect()
        except Exception:
            pass
    db.runtime_set("ibkr.challenge", snap)
    if snap["ok"]:
        db.ex("INSERT OR REPLACE INTO nav_marks(day,pod,nav,capital,gross) VALUES(?,?,?,?,?)",
              (db.today(), "pod_zero", snap["nav_eur"], 1.0, 0.0))
    return snap


# ---------------------------------------------------------------------------
# Esecutore dei pod (secondo conto paper)
# ---------------------------------------------------------------------------
class IBKRPaperBroker:
    venue = "ibkr-paper"

    def __init__(self, factory=_default_factory, timeout: float = 20):
        ep = firm_endpoint()
        challenge = challenge_endpoint().account
        if not ep.account or not ep.account.startswith("DU"):
            raise PermissionError("IBKR_FIRM_ACCOUNT mancante o non paper (DU...): i pod restano sul broker simulato")
        if challenge and ep.account == challenge:
            raise PermissionError("il conto dei pod coincide con quello della sfida: vietato (REGOLE_SFIDA §1)")
        self.ep = ep
        self.ib = factory()
        self.ib.connect(ep.host, ep.port, clientId=ep.client_id, timeout=timeout)
        accts = self.ib.managedAccounts()
        if ep.account not in accts:
            self.ib.disconnect()
            raise PermissionError(f"il gateway non gestisce il conto {mask(ep.account)}")
        if challenge and challenge in accts:
            self.ib.disconnect()
            raise PermissionError("il gateway dei pod vede anche il conto della sfida: usare login separati")
        self._last = 0.0

    def close(self):
        try:
            self.ib.disconnect()
        except Exception:
            pass

    def _already_sent(self, ref: str):
        for t in self.ib.openTrades():
            if getattr(t.order, "orderRef", "") == ref:
                return t
        for f in self.ib.fills():
            if getattr(f.execution, "orderRef", "") == ref:
                return f
        return None

    def execute(self, instrument: str, kind: str, side: str, qty: float, price: float, ref: str | None = None):
        """Ritorna (prezzo medio, commissioni, quantita' eseguita). Quantita' 0 = niente eseguito."""
        from ib_async import LimitOrder
        if risk.kill_active():
            raise PermissionError("KILL attivo")
        q = round_qty(kind, qty)
        if q <= 0:
            return price, 0.0, 0.0
        ref = ref or f"{ORDER_PREFIX}{int(time.time() * 1000)}"
        prev = self._already_sent(ref)
        if prev is not None:                        # idempotenza: dopo una riconnessione non si reinvia
            events.publish("gateway.duplicate_blocked", "gateway", dict(ref=ref, strumento=instrument))
            return price, 0.0, 0.0
        c = contract_for(instrument, kind)
        qualified = self.ib.qualifyContracts(c)
        if not qualified:
            raise ValueError(f"contratto IBKR non trovato: {instrument}")
        c = qualified[0]
        wait = PACING_S - (time.monotonic() - self._last)
        if wait > 0:
            self.ib.sleep(wait)
        o = LimitOrder(side, q, limit_price(side, price, kind), tif="IOC" if kind == "crypto" else "DAY",
                       orderRef=ref, account=self.ep.account)
        trade = self.ib.placeOrder(c, o)
        self._last = time.monotonic()
        t0 = time.monotonic()
        while trade.orderStatus.status not in ("Filled", "Cancelled", "ApiCancelled", "Inactive") \
                and time.monotonic() - t0 < FILL_TIMEOUT_S:
            self.ib.sleep(0.5)
        if trade.orderStatus.status not in ("Filled", "Cancelled", "ApiCancelled", "Inactive"):
            self.ib.cancelOrder(trade.order)          # niente ordini appesi: il residuo si annulla
            self.ib.sleep(1.0)
        filled = sum(float(f.execution.shares) for f in trade.fills)
        if filled <= 0:
            return price, 0.0, 0.0
        avg = sum(float(f.execution.shares) * float(f.execution.price) for f in trade.fills) / filled
        fee = sum(float(getattr(f.commissionReport, "commission", 0) or 0) for f in trade.fills)
        if fee > 1e9:                                 # IBKR usa un valore enorme per "commissione non ancora nota"
            fee = 0.0
        return avg, fee, filled

    def cancel_open(self) -> int:
        n = 0
        for t in self.ib.openTrades():
            if getattr(t.order, "orderRef", "").startswith(ORDER_PREFIX):
                self.ib.cancelOrder(t.order)
                n += 1
        return n

    def positions(self) -> dict[str, float]:
        out = {}
        for p in self.ib.positions(self.ep.account):
            k = p.contract.symbol if p.contract.secType == "CRYPTO" else (p.contract.localSymbol or p.contract.symbol)
            out[k] = out.get(k, 0.0) + float(p.position)
        return out


def reconcile(broker) -> list[dict]:
    """Confronta le posizioni del conto dei pod con la somma dei sub-ledger: ogni scarto e' un allarme."""
    from . import gateway, pods
    ledger: dict[str, float] = {}
    for p in pods.all_pods():
        if p["id"] == "pod_zero":
            continue
        for k, q in gateway.positions(p["id"]).items():
            ledger[k] = ledger.get(k, 0.0) + q
    real = broker.positions()
    diffs = []
    for k in sorted(set(ledger) | set(real)):
        d = real.get(k, 0.0) - ledger.get(k, 0.0)
        if abs(d) > 1e-6:
            diffs.append(dict(strumento=k, broker=real.get(k, 0.0), ledger=ledger.get(k, 0.0), scarto=d))
    if diffs:
        events.publish("risk.alert", "ibkr", dict(cosa=f"riconciliazione: {len(diffs)} scarti tra broker e sub-ledger",
                                                  gravita=4, dettagli=diffs[:5]))
    db.runtime_set("ibkr.reconcile", dict(ts=db.now_iso(), scarti=diffs))
    return diffs


def status() -> dict:
    """Per il portale: solo cio' che il battito ha scritto (il portale non si collega mai al broker)."""
    return dict(sfida=db.runtime_get("ibkr.challenge"), riconciliazione=db.runtime_get("ibkr.reconcile"),
                broker_pod=os.environ.get("GATEWAY_BROKER", "simulato"))
