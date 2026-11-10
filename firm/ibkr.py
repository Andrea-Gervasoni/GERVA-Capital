"""
Collegamento a Interactive Brokers (IB Gateway) — SOLO PAPER, con due ruoli separati.

1. OSSERVATORE del conto della sfida (GERVA-Q / Pod Zero): legge NAV, posizioni ed eseguiti per il portale
   e il Rischio. `readonly=True` in ib_async evita solo la sincronizzazione degli ordini, NON impedisce
   placeOrder: per questo l'osservatore riceve un involucro (_ReadOnlyIB) che espone solo letture e
   solleva PermissionError su qualsiasi altro metodo.
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

import datetime as dt
import math
import os
import time
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import yaml

from . import db, events, paths, risk

ORDER_PREFIX = "GERVA-CAP-"
# contrattazione continua, ora LOCALE della borsa (segue l'ora legale; le festivita' non sono gestite:
# un ordine DAY in un giorno di chiusura non si esegue e si annulla allo scadere)
EXCHANGE_HOURS = {"LSEETF": ("Europe/London", (8, 0), (16, 30)), "IBIS": ("Europe/Berlin", (9, 0), (17, 30)),
                  "SMART": ("America/New_York", (9, 30), (16, 0))}


class NotSent(Exception):
    """L'ordine NON e' stato inviato al broker (KILL, contratto o valuta non validi): niente da recuperare."""
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
    ib = IB()
    try:
        # ib_async, a ogni avviso 1102 ("connessione ripristinata"), apre da solo un abbonamento al riepilogo del conto:
        # noi non lo usiamo, e TWS ne concede pochissimi (errore 322): occuparli puo' togliere il posto a GERVA-Q.
        ib.errorEvent -= ib._onError
    except Exception:
        pass
    return ib


def probe_market_data(symbols=("AMD", "NVDA", "CSCO", "CRM", "AAPL"), factory=None, stock=None, wait: float = 6.0) -> dict:
    """SOLA LETTURA, nessun ordine. Perche' le azioni americane vengono annullate mentre gli ETF europei si eseguono?
    Per ogni titolo chiede un'istantanea dei prezzi in tempo reale e poi ritardati, e raccoglie gli errori di IBKR (354, 10089, 10167...)."""
    factory = factory or _default_factory
    ep = challenge_endpoint()
    ib = factory()
    errors: list[dict] = []
    try:
        ib.errorEvent += lambda reqId=None, code=None, msg=None, *a: errors.append(dict(richiesta=reqId, codice=code, testo=str(msg)[:200]))
    except Exception:
        pass
    out: dict = {}
    import collections
    import logging
    raw: list[str] = []
    cap = type("Cap", (logging.Handler,), {"emit": lambda self, rec: raw.append(rec.getMessage())})()
    lg = logging.getLogger("ib_async.client")
    old_level, old_prop = lg.level, lg.propagate
    lg.propagate = False                                                   # si registra soltanto: niente righe sul Terminale
    try:
        ib.connect(ep.host, ep.port, clientId=ep.client_id + 5, timeout=15, readonly=True)
        if stock is None:
            from ib_async import Stock as stock
        now_ny = dt.datetime.now(ZoneInfo("America/New_York"))
        open_us = now_ny.weekday() < 5 and dt.time(9, 30) <= now_ny.time() <= dt.time(16, 0)
        info = dict(ora_mac=dt.datetime.now().strftime("%a %H:%M"), ora_new_york=now_ny.strftime("%a %H:%M"), borsa_usa_aperta_ora=open_us, messaggi_connessione=list(errors))
        for k, fn in (("conti", lambda: list(ib.managedAccounts())), ("versione_server", lambda: ib.client.serverVersion())):
            try:
                info[k] = fn()
            except Exception:
                pass
        out["_info"] = info
        clean = lambda v: None if v is None or (isinstance(v, float) and not math.isfinite(v)) or v == -1 else round(float(v), 4)
        lg.addHandler(cap); lg.setLevel(logging.DEBUG)                      # i messaggi veri tra noi e TWS, per capire se TWS risponde ai prezzi
        for sym in symbols:
            c = stock(sym, "SMART", "USD")
            try:
                ib.qualifyContracts(c)
            except Exception as e:
                out[sym] = dict(errore=f"contratto non trovato: {e}")
                continue
            row = {}
            for label, mtype in (("tempo_reale", 1), ("ritardati", 3), ("ritardati_congelati", 4)):
                n0 = len(errors)
                ib.reqMarketDataType(mtype)
                t = ib.reqMktData(c, "", False, False)
                ib.sleep(wait)
                row[label] = dict(ultimo=clean(getattr(t, "last", None)), denaro=clean(getattr(t, "bid", None)), lettera=clean(getattr(t, "ask", None)),
                                  chiusura=clean(getattr(t, "close", None)), tipo_dati=getattr(t, "marketDataType", None), errori=errors[n0:])
                ib.cancelMktData(c)
            live, dl = row["tempo_reale"], row["ritardati"]
            has = lambda d: any(d[k] is not None for k in ("ultimo", "denaro", "lettera", "chiusura"))
            if sym == symbols[0]:                                    # lo storico giornaliero risponde anche senza prezzi in tempo reale
                n0 = len(errors)
                try:
                    bars = ib.reqHistoricalData(c, "", "2 D", "1 day", "TRADES", True, 1, False)
                    row["storico_giornaliero"] = dict(barre=len(bars or []), ultima_chiusura=clean(bars[-1].close) if bars else None, errori=errors[n0:])
                except Exception as e:
                    row["storico_giornaliero"] = dict(errore=f"{type(e).__name__}: {str(e)[:120]}", errori=errors[n0:])
            row["lettura"] = ("prezzi in tempo reale disponibili" if has(live) and live["tipo_dati"] in (1, 2, None)
                              else "SOLO prezzi ritardati: manca l'abbonamento ai dati americani in tempo reale" if has(dl) or has(live)
                              else "nessun prezzo ricevuto e nessun errore da IBKR: guarda i messaggi di connessione" if not any(row[k]["errori"] for k in ("tempo_reale", "ritardati"))
                          else "nessun prezzo ricevuto: guarda gli errori di IBKR qui sotto")
            out[sym] = row
            if sym == symbols[0]:
                ids = collections.Counter(m[4:].split(",")[0] for m in raw if m.startswith("<<<"))
                pick = lambda pre, ids_: [m[:150] for m in raw if m.startswith(pre) and m[4:].split(",")[0] in ids_][:4]
                out["_raw"] = dict(ricevuti_per_tipo=dict(ids), inviati_prezzi=pick(">>>", {"1", "59"}), ricevuti_prezzi=pick("<<<", {"1", "2", "45", "46", "58", "81"}), ricevuti_errori=pick("<<<", {"4"}))
                lg.removeHandler(cap)
    except Exception as e:
        out["errore"] = f"{type(e).__name__}: {str(e)[:160]}"
    finally:
        lg.removeHandler(cap); lg.setLevel(old_level); lg.propagate = old_prop
        try:
            ib.disconnect()
        except Exception:
            pass
    return out


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


def limit_price(side: str, ref: float, kind: str, tick: float | None = None) -> float:
    """Prezzo limite protetto: al massimo meta' della deviazione ammessa dal Gateway, sul tick del contratto
    (arrotondato verso il prezzo di riferimento, quindi mai oltre la protezione)."""
    from . import settings as S
    dev = float(S.risk_limits()["order"]["max_price_deviation"]) / 2
    p = ref * (1 + dev) if side == "BUY" else ref * (1 - dev)
    t = tick if tick and tick > 0 else 0.01
    n = math.floor(p / t + 1e-9) if side == "BUY" else math.ceil(p / t - 1e-9)
    return round(n * t, 10)


def market_open(symbol: str, kind: str, now: dt.datetime | None = None) -> bool:
    if kind == "crypto":
        return True
    exch = "SMART" if kind == "stock" else instruments().get(symbol, {}).get("exchange", "SMART")
    tz, a, b = EXCHANGE_HOURS.get(exch, EXCHANGE_HOURS["SMART"])
    t = (now or dt.datetime.now(dt.timezone.utc)).astimezone(ZoneInfo(tz))
    return t.weekday() < 5 and a <= (t.hour, t.minute) < b


# ---------------------------------------------------------------------------
# Osservatore del conto della sfida (sola lettura)
# ---------------------------------------------------------------------------
class _ReadOnlyIB:
    """Involucro dell'osservatore: solo letture. placeOrder/cancelOrder e tutto il resto sono vietati."""
    _ALLOWED = frozenset({"connect", "disconnect", "managedAccounts", "accountValues", "positions", "fills", "portfolio", "sleep", "reqPnL", "cancelPnL", "isConnected", "errorEvent", "accountValueEvent", "pnlEvent"})

    def __init__(self, ib):
        object.__setattr__(self, "_ib", ib)

    def __getattr__(self, name):
        if name not in _ReadOnlyIB._ALLOWED:
            raise PermissionError(f"osservatore in sola lettura: {name} non consentito")
        return getattr(object.__getattribute__(self, "_ib"), name)


def observe_challenge(factory=_default_factory, timeout: float = 15) -> dict:
    ep = challenge_endpoint()
    ib = _ReadOnlyIB(factory())
    snap = dict(ok=False, ts=db.now_iso())
    try:
        ib.connect(ep.host, ep.port, clientId=ep.client_id, timeout=timeout, readonly=True)
        accts = list(ib.managedAccounts())
        if ep.account:
            acct = ep.account if ep.account in accts else None
            if not acct:
                snap.update(errore=f"il gateway osservato non gestisce il conto configurato {mask(ep.account)}")
        else:
            acct = accts[0] if len(accts) == 1 else None
            if not acct:
                snap.update(errore="IBKR_CHALLENGE_ACCOUNT non impostato e il gateway gestisce piu' conti")
        if acct and not acct.startswith("DU"):
            snap.update(errore="il conto della sfida non e' un conto paper (DU...): osservazione interrotta")
            events.publish("risk.alert", "ibkr", dict(cosa=snap["errore"], gravita=5))
            acct = None
        if acct:
            vals = {(v.tag, v.currency): v.value for v in ib.accountValues(acct)}
            nav = float(vals.get(("NetLiquidation", "EUR")) or vals.get(("NetLiquidation", "BASE")) or 0)
            if nav <= 0:                       # valuta base non EUR o dati non ancora arrivati: MAI un NAV a zero
                snap.update(errore="NAV non disponibile (valuta base non EUR o dati di conto non ancora ricevuti)")
            else:
                pos = [dict(simbolo=p.contract.localSymbol or p.contract.symbol, tipo=p.contract.secType,
                            qty=float(p.position), costo_medio=float(p.avgCost)) for p in ib.positions(acct)]
                snap.update(ok=True, conto=mask(acct), nav_eur=nav, posizioni=pos, eseguiti_oggi=len(ib.fills()))
                try:                                   # plancia: le esecuzioni, i prezzi di mercato e la leva del conto (sola lettura)
                    from . import blotter
                    blotter.ingest_ibkr(ib.fills())
                    blotter.snapshot_ibkr(ib, acct, vals)
                except Exception:
                    pass
    except Exception as e:                       # gateway spento, rete, login: si registra, non si crasha
        snap.update(errore=f"{type(e).__name__}: {str(e)[:160]}")
    finally:
        try:
            ib.disconnect()
        except Exception:
            pass
    db.runtime_set("ibkr.challenge", snap)
    if snap["ok"]:
        from .gateway import START_KEY
        # il capitale iniziale e' la prima lettura riuscita: si scrive UNA volta (INSERT OR IGNORE), mai a mano
        db.connect().execute("INSERT OR IGNORE INTO runtime(key,value,updated_ts) VALUES(?,?,?)",
                             (START_KEY, db.dumps(dict(nav=snap["nav_eur"], giorno=db.today())), db.now_iso()))
        prev = db.one("SELECT nav FROM nav_marks WHERE pod='pod_zero' AND day<? ORDER BY day DESC LIMIT 1", (db.today(),))
        if prev and prev["nav"] > 0 and abs(snap["nav_eur"] / prev["nav"] - 1) > 0.20:
            # IBKR non distingue un versamento (o un reset del paper) da un guadagno: non lo si conta in silenzio
            events.publish("risk.alert", "ibkr", dict(
                cosa=f"il valore del conto e' passato da {prev['nav']:,.0f} a {snap['nav_eur']:,.0f} EUR in un giorno: "
                     "versamento, prelievo o reset del conto paper? Da verificare prima di leggerlo come risultato",
                gravita=4))
        db.ex("INSERT OR REPLACE INTO nav_marks(day,pod,nav,capital,gross) VALUES(?,?,?,?,?)",
              (db.today(), "pod_zero", snap["nav_eur"], 1.0, 0.0))
    return snap


# ---------------------------------------------------------------------------
# Valore del conto in tempo reale (sola lettura): connessione che resta aperta
# ---------------------------------------------------------------------------
def _pick_account(ib, ep) -> tuple[str | None, str | None]:
    accts = list(ib.managedAccounts())
    acct = (ep.account if ep.account in accts else None) if ep.account else (accts[0] if len(accts) == 1 else None)
    if not acct:
        return None, "il gateway non gestisce il conto configurato (IBKR_CHALLENGE_ACCOUNT)"
    if not acct.startswith("DU"):
        return None, "il conto osservato non e' un conto paper (DU...): osservazione interrotta"
    return acct, None


def live_loop(factory=_default_factory, interval: float = 5.0, max_iter: int | None = None, retry: float = 15.0,
              sleep=None) -> None:
    """Tiene aperta UNA connessione in sola lettura e scrive il valore del conto ogni pochi secondi.

    TWS manda il valore esatto (NetLiquidation) ogni ~3 minuti; in mezzo si usa il P&L in tempo reale (reqPnL) per stimare
    la variazione: stima = ultimo valore esatto + variazione del P&L da quel momento. Il valore esatto resta salvato
    accanto alla stima. Scrive ibkr.live, la marcatura di oggi e un punto al minuto per il grafico (nav_ticks).
    Si riconnette da sola. Mai ordini: l'involucro _ReadOnlyIB li vieta."""
    import time
    sleep = sleep or time.sleep
    ep = challenge_endpoint()
    client_id = int(os.environ.get("IBKR_LIVE_CLIENT_ID", ep.client_id + 1))
    n, last_tick, failures = 0, 0.0, 0
    from collections import deque
    import statistics
    recent = deque(maxlen=15)                                   # gli ultimi punti scritti: una lettura lontana dalla loro mediana e' quasi sempre un errore
    from .selfupdate import Watch
    watch = Watch("lettura IBKR") if max_iter is None else None
    while max_iter is None or n < max_iter:
        if watch:
            watch.check()
        ib = _ReadOnlyIB(factory())
        # The socket may remain open while TWS loses its upstream connection.
        connection = {"lost": False, "last_data": time.monotonic()}
        handlers = []
        def on_error(req_id, code, message, *args):
            if code in (1100, 1101, 1300):
                connection["lost"] = True  # recreate subscriptions on a fresh read-only session
        def on_data(*args):
            connection["last_data"] = time.monotonic()
        for event_name, callback in (("errorEvent", on_error), ("accountValueEvent", on_data), ("pnlEvent", on_data)):
            event = getattr(ib, event_name, None)
            if event is not None:
                event += callback
                handlers.append((event, callback))
        try:
            ib.connect(ep.host, ep.port, clientId=client_id, timeout=15, readonly=True)
            acct, err = _pick_account(ib, ep)
            if not acct:
                raise RuntimeError(err)
            pnl = ib.reqPnL(acct)
            base = None
            while max_iter is None or n < max_iter:
                ib.sleep(interval)
                n += 1
                connected = getattr(ib, "isConnected", None)
                if connection["lost"] or (connected is not None and not connected()):
                    raise ConnectionError("IBKR disconnected; rebuilding read-only subscriptions")
                if handlers and time.monotonic() - connection["last_data"] > 240:
                    raise TimeoutError("no account/PnL update for 240 seconds")
                if watch and watch.changed():
                    ib.disconnect(); watch.last = 0; watch.check()
                vals = {(v.tag, v.currency): v.value for v in ib.accountValues(acct)}
                exact = float(vals.get(("NetLiquidation", "EUR")) or vals.get(("NetLiquidation", "BASE")) or 0)
                if not math.isfinite(exact) or exact <= 0:
                    continue                                   # mai un valore a zero
                tot = sum(float(x) for x in (getattr(pnl, "unrealizedPnL", None), getattr(pnl, "realizedPnL", None))
                          if x is not None and math.isfinite(float(x)))
                if base is None or exact != base[0]:
                    base = (exact, tot)                        # arrivato un valore esatto nuovo: si riparte da lui
                est = exact + (tot - base[1])
                if not math.isfinite(est) or est <= 0:
                    raise ValueError("invalid estimated NAV")
                failures = 0
                now = db.now_iso()
                db.runtime_set("ibkr.live", dict(ts=now, nav=round(est, 2), nav_exact=round(exact, 2), stima=abs(est - exact) > 0.005,
                                                source_age_s=round(time.monotonic() - connection["last_data"], 1)))
                db.runtime_set("ibkr.live_ok", now)                     # l'orologio del portale: IBKR collegato e leggibile
                db.ex("INSERT OR REPLACE INTO nav_marks(day,pod,nav,capital,gross) VALUES(?,?,?,?,?)",
                      (db.today(), "pod_zero", est, 1.0, 0.0))
                if time.time() - last_tick >= 60:
                    med = statistics.median(recent) if len(recent) >= 8 else None
                    if not (med and abs(est / med - 1) > 0.015):        # oltre l'1,5% dai vicini: non entra nel grafico (se dura davvero, la mediana si sposta e passa)
                        db.ex("INSERT INTO nav_ticks(ts,nav) VALUES(?,?)", (now, est))
                    recent.append(est)
                    last_tick = time.time()
        except Exception as e:                                 # TWS spento o in riavvio: si registra e si riprova
            prev = db.runtime_get("ibkr.live") or {}                          # l'ultimo valore noto resta: l'errore si aggiunge, non lo cancella
            db.runtime_set("ibkr.live", dict(prev, errore=f"{type(e).__name__}: {str(e)[:120]}", errore_ts=db.now_iso()))
            n += 1
            failures += 1
        finally:
            for event, callback in handlers:
                event -= callback
            try:
                ib.disconnect()
            except Exception:
                pass

        if failures and (max_iter is None or n < max_iter):
            import random
            sleep(min(120.0, retry * 2 ** min(failures - 1, 4)) * random.uniform(0.8, 1.2))


# ---------------------------------------------------------------------------
# Esecutore dei pod (secondo conto paper)
# ---------------------------------------------------------------------------
class IBKRPaperBroker:
    venue = "ibkr-paper"

    def __init__(self, factory=_default_factory, timeout: float = 20):
        ep, ch = firm_endpoint(), challenge_endpoint()
        challenge = ch.account
        if not ep.account or not ep.account.startswith("DU"):
            raise PermissionError("IBKR_FIRM_ACCOUNT mancante o non paper (DU...): i pod restano sul broker simulato")
        if not challenge or not challenge.startswith("DU"):
            raise PermissionError("IBKR_CHALLENGE_ACCOUNT mancante: senza il conto della sfida l'esecutore non puo' escluderlo")
        if ep.account == challenge:
            raise PermissionError("il conto dei pod coincide con quello della sfida: vietato (REGOLE_SFIDA §1)")
        if (ep.host, ep.port) == (ch.host, ch.port):
            raise PermissionError("l'esecutore dei pod punta al gateway della sfida: serve il gateway del secondo conto")
        self.ep = ep
        self.ib = factory()
        self.ib.connect(ep.host, ep.port, clientId=ep.client_id, timeout=timeout)
        accts = self.ib.managedAccounts()
        if ep.account not in accts:
            self.ib.disconnect()
            raise PermissionError(f"il gateway non gestisce il conto {mask(ep.account)}")
        if challenge in accts:
            self.ib.disconnect()
            raise PermissionError("il gateway dei pod vede anche il conto della sfida: usare login separati")
        self._last = 0.0

    def close(self):
        try:
            self.ib.disconnect()
        except Exception:
            pass

    # ---------------------------------------------------------------- stato di un ordine dal suo orderRef
    def _open_trade(self, ref: str):
        return next((t for t in self.ib.openTrades() if getattr(t.order, "orderRef", "") == ref), None)

    def _fills_for(self, ref: str, refresh: bool = False) -> list:
        src = self.ib.reqExecutions() if refresh and hasattr(self.ib, "reqExecutions") else self.ib.fills()
        seen, out = set(), []
        for f in src:
            if getattr(f.execution, "orderRef", "") != ref:
                continue
            key = getattr(f.execution, "execId", None) or id(f)
            if key not in seen:
                seen.add(key)
                out.append(f)
        return out

    def _totals(self, ref: str, refresh: bool = False):
        fills = self._fills_for(ref, refresh)
        filled = sum(float(f.execution.shares) for f in fills)
        if filled <= 0:
            return None, 0.0, 0.0
        avg = sum(float(f.execution.shares) * float(f.execution.price) for f in fills) / filled
        fee = 0.0
        for f in fills:
            c = float(getattr(getattr(f, "commissionReport", None), "commission", 0) or 0)
            fee += c if c < 1e9 else 0.0             # IBKR usa un valore enorme per "commissione non ancora nota"
        return avg, fee, filled

    def _finish(self, trade, ref: str):
        """Attende la fine; allo scadere annulla il residuo e aspetta che l'annullamento sia CONFERMATO
        (gli eseguiti arrivati durante PendingCancel restano nel conto e nel registro)."""
        t0 = time.monotonic()
        while not trade.isDone() and time.monotonic() - t0 < FILL_TIMEOUT_S:
            self.ib.sleep(0.5)
        if not trade.isDone():
            self.ib.cancelOrder(trade.order)
            t1 = time.monotonic()
            while not trade.isDone() and time.monotonic() - t1 < 15:
                self.ib.sleep(0.5)
            if not trade.isDone():
                raise RuntimeError(f"annullamento di {ref} non confermato: si recupera al prossimo giro")
        t2 = time.monotonic()                        # le commissioni arrivano dopo l'eseguito
        while any(float(getattr(getattr(f, "commissionReport", None), "commission", 0) or 0) == 0
                  for f in self._fills_for(ref)) and time.monotonic() - t2 < 3:
            self.ib.sleep(0.5)

    def can_trade(self, instrument: str, kind: str) -> bool:
        return market_open(instrument, kind)

    def recover(self, ref: str):
        """Dopo un crash tra l'invio e la registrazione: (prezzo, commissioni, qty) se l'ordine esiste, None se
        il broker non ne ha traccia (si marca da verificare: MAI reinviare alla cieca)."""
        t = self._open_trade(ref)
        if t is not None:
            self._finish(t, ref)
        avg, fee, filled = self._totals(ref, refresh=True)
        if filled > 0:
            return avg, fee, filled
        return (0.0, 0.0, 0.0) if t is not None else None

    def execute(self, instrument: str, kind: str, side: str, qty: float, price: float, ref: str | None = None,
                currency: str | None = None):
        """Ritorna (prezzo medio, commissioni, quantita' eseguita). Quantita' 0 = niente eseguito."""
        from ib_async import LimitOrder
        if risk.kill_active():
            raise NotSent("KILL attivo")
        ref = ref or f"{ORDER_PREFIX}{int(time.time() * 1000)}"
        if self._open_trade(ref) is not None or self._fills_for(ref):   # idempotenza: mai un secondo invio
            events.publish("gateway.duplicate_blocked", "gateway", dict(ref=ref, strumento=instrument))
            r = self.recover(ref)
            return r if r else (price, 0.0, 0.0)
        c = contract_for(instrument, kind)
        if currency and currency != c.currency:
            raise NotSent(f"{instrument}: prezzo in {currency} ma il contratto e' in {c.currency}")
        qualified = self.ib.qualifyContracts(c)
        if not qualified or qualified[0] is None:     # ib_async restituisce [None] se il contratto e' ambiguo
            raise NotSent(f"contratto IBKR non trovato o ambiguo: {instrument}")
        c = qualified[0]
        tick, step, min_size = None, None, None
        try:
            det = self.ib.reqContractDetails(c)
            if det:
                tick = float(det[0].minTick or 0) or None
                step = float(det[0].sizeIncrement or 0) or None
                min_size = float(det[0].minSize or 0) or None
        except Exception:
            pass
        q = round_qty(kind, qty)
        if step and step > 0:
            q = round(math.floor(q / step + 1e-9) * step, 10)
        if q <= 0 or (min_size and q < min_size):
            return price, 0.0, 0.0
        wait = PACING_S - (time.monotonic() - self._last)
        if wait > 0:
            self.ib.sleep(wait)
        o = LimitOrder(side, q, limit_price(side, price, kind, tick), tif="IOC" if kind == "crypto" else "DAY",
                       orderRef=ref, account=self.ep.account)
        trade = self.ib.placeOrder(c, o)
        self._last = time.monotonic()
        self._finish(trade, ref)
        avg, fee, filled = self._totals(ref)
        return (avg, fee, filled) if filled > 0 else (price, 0.0, 0.0)

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
            k = k.replace(" ", "-")                    # BRK B (IBKR) = BRK-B (registro)
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
