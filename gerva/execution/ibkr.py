"""
Adattatore per il conto PAPER di Interactive Brokers (TWS o IB Gateway, tramite ib_async). Solo paper.

ATTENZIONE: questo modulo e' collaudato contro un ib_async FINTO (tests/test_gerva_ibkr.py), non contro IBKR:
nell'ambiente in cui e' stato scritto non c'erano ne' TWS ne' IB Gateway. Il primo collegamento va fatto con
`python -m gerva check-broker` (sola lettura) e il primo ordine di ogni simbolo va guardato a mano in TWS.

Che cosa viene da firm/ibkr.py (l'esecutore dei pod, giudicato "da tenere" dall'audit) e NON e' riscritto:
    _open_trade, _fills_for, _totals, _finish   stato di un ordine dal suo orderRef, attesa limitata, annullamento
                                                 del residuo CONFERMATO prima di contare gli eseguiti
    _ReadOnlyIB                                  involucro di sola lettura (qui con qualche lettura in piu')
    _default_factory, mask, EXCHANGE_HOURS       connessione, numero di conto mascherato, orari delle borse
Di firm/ibkr.py NON si usa `execute`: dipende dal database e dal KILL della vecchia societa'. Qui il KILL e i
limiti sono del motore di rischio di gerva, che decide prima di chiamare `submit`.

Perche' nessun ordine puo' arrivare a un conto reale:
    1. le porte dei conti reali (7496 TWS, 4001 Gateway) sono rifiutate prima di collegarsi;
    2. dopo il collegamento TUTTI i conti gestiti dalla sessione devono iniziare per "DU" (paper): basta un conto
       reale visibile e l'adattatore si scollega e solleva PermissionError;
    3. il conto della sfida GERVA-Q (IBKR_CHALLENGE_ACCOUNT), se dichiarato, e' escluso: `flatten` lo liquiderebbe;
    4. c'e' un solo punto che chiama placeOrder (`_place`): ricontrolla il prefisso e scrive il conto nell'ordine;
    5. in sola lettura (`read_only=True`, usato da check-broker) placeOrder non e' nemmeno raggiungibile.

Unita' di misura. Il ciclo ragiona sul simbolo di ricerca (SPY a ~600 $), IBKR scambia lo strumento mappato
(CSPX a ~700 $, o il CFD IBUS500 a ~6000 $). Si conserva il CONTROVALORE in dollari:
    pezzi = |qty| x prezzo di riferimento / prezzo in dollari dello strumento     (arrotondati per difetto)
e l'eseguito torna al ciclo nelle unita' del simbolo di ricerca (stesso controvalore), cosi' lo scostamento di
prezzo misurato dai cancelli e' quello vero: eseguito contro prezzo dello strumento al momento dell'invio.
`positions()` restituisce pezzi e prezzo dello strumento negoziato: il loro prodotto e' il valore in dollari.

Limiti noti (da sapere prima di fidarsi):
    * IBKR ricorda eseguiti e ordini conclusi solo per la giornata: `lookup` di un ordine piu' vecchio risponde None;
    * dopo un riavvio `lookup` non conosce piu' il rapporto di conversione: restituisce i pezzi dello strumento
      negoziato e prezzo 0 (il cancello dei costi ignora la riga invece di misurare uno scostamento falso);
    * il clientId deve restare lo stesso tra un avvio e l'altro: IBKR mostra a un client solo i suoi ordini aperti;
    * le festivita' non sono gestite: un ordine in un giorno di chiusura non si esegue e viene annullato.

Variabili d'ambiente: IBKR_GERVA_HOST (127.0.0.1), IBKR_GERVA_PORT (4002 = IB Gateway paper; TWS paper = 7497),
IBKR_GERVA_CLIENT_ID (41), IBKR_GERVA_ACCOUNT (serve solo se la sessione gestisce piu' conti paper).
Le credenziali di IBKR non passano mai da qui: le custodisce TWS / IB Gateway.
"""
from __future__ import annotations

import datetime as dt
import logging
import math
import os
import time
from typing import Callable
from zoneinfo import ZoneInfo

import yaml

from firm import ibkr as _firm

from .broker import Account, BrokerError, Fill, Position

log = logging.getLogger("gerva.ibkr")

ORDER_PREFIX = "GERVA-"                      # orderRef = GERVA-<client_id>: diverso da GERVA-CAP- dei pod solo per il seguito
LIVE_PORTS = frozenset({7496, 4001})         # TWS e IB Gateway sui conti REALI
US_EXCHANGES = frozenset({"SMART", "ARCA", "NYSE", "NASDAQ", "ISLAND", "AMEX", "BATS", "IEX", "NYSENAT", "PSX", "CBOE"})
DEFAULT_MAP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config", "ibkr_gerva.yaml"))
PACING_S = _firm.PACING_S


# ---------------------------------------------------------------------------
# Mappatura simbolo di ricerca -> strumento negoziabile
# ---------------------------------------------------------------------------
def load_map(path: str | None = None) -> dict[str, dict]:
    """Legge config/ibkr_gerva.yaml. Una riga vuota = simbolo senza strumento (ordine rifiutato, mai inviato).
    Un ETF/azione su una borsa americana fa fallire l'avvio: un cliente al dettaglio UE non puo' comprarlo (PRIIPs)."""
    with open(path or os.environ.get("GERVA_IBKR_MAP") or DEFAULT_MAP) as f:
        raw = yaml.safe_load(f) or {}
    out = {}
    for ours, spec in raw.items():
        if not spec:
            continue
        missing = [k for k in ("symbol", "sec_type", "exchange", "currency") if not spec.get(k)]
        if missing:
            raise ValueError(f"{ours}: mancano {missing} nella mappatura IBKR")
        if spec["sec_type"] not in ("STK", "CFD"):
            raise ValueError(f"{ours}: sec_type '{spec['sec_type']}' non gestito (STK o CFD)")
        if spec["sec_type"] == "STK" and str(spec["exchange"]).upper() in US_EXCHANGES:
            raise ValueError(f"{ours} -> {spec['symbol']} su {spec['exchange']}: ETF quotato negli USA, vietato a un cliente "
                             "al dettaglio UE (PRIIPs). Serve l'equivalente UCITS o un CFD")
        session = spec.get("session") or spec["exchange"]
        if session not in _firm.EXCHANGE_HOURS:
            raise ValueError(f"{ours}: orario '{session}' sconosciuto (ammessi: {sorted(_firm.EXCHANGE_HOURS)})")
        out[ours] = dict(symbol=str(spec["symbol"]), sec_type=spec["sec_type"], exchange=str(spec["exchange"]),
                         currency=str(spec["currency"]), session=session, verified=bool(spec.get("verified", False)))
    seen: dict[tuple, str] = {}
    for ours, s in out.items():
        k = (s["symbol"], s["sec_type"], s["currency"])
        if k in seen:
            raise ValueError(f"{ours} e {seen[k]} puntano allo stesso strumento {s['symbol']}: le posizioni non si distinguerebbero")
        seen[k] = ours
    return out


def session_open(session: str, now: dt.datetime | None = None) -> bool:
    tz, a, b = _firm.EXCHANGE_HOURS[session]
    t = (now or dt.datetime.now(dt.timezone.utc)).astimezone(ZoneInfo(tz))
    return t.weekday() < 5 and a <= (t.hour, t.minute) < b


def limit_price(side: str, ref: float, dev: float, tick: float | None) -> float:
    """Limite protetto: riferimento +/- dev, sul tick del contratto, arrotondato VERSO il riferimento (mai oltre la
    protezione). Stessa regola di firm.ibkr.limit_price, senza leggere i limiti della vecchia societa'."""
    p = ref * (1 + dev) if side == "BUY" else ref * (1 - dev)
    t = tick if tick and tick > 0 else 0.01
    n = math.floor(p / t + 1e-9) if side == "BUY" else math.ceil(p / t - 1e-9)
    return round(n * t, 10)


class _ReadOnly(_firm._ReadOnlyIB):
    """L'involucro di sola lettura di firm/ibkr.py con le letture che servono qui. Tutto il resto, a partire da
    placeOrder e cancelOrder, solleva PermissionError."""
    _ALLOWED = _firm._ReadOnlyIB._ALLOWED | {"isConnected", "openTrades", "reqExecutions", "reqCompletedOrders", "qualifyContracts",
                                             "reqContractDetails", "reqTickers", "reqMarketDataType", "reqHistoricalData"}

    def __getattr__(self, name):
        if name not in _ReadOnly._ALLOWED:
            raise PermissionError(f"IBKR in sola lettura: {name} non consentito")
        return getattr(object.__getattribute__(self, "_ib"), name)


def _num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v > 0 else None


# ---------------------------------------------------------------------------
# Adattatore
# ---------------------------------------------------------------------------
class IBKRPaper:
    name = "ibkr-paper"

    # la meccanica dell'ordine e' quella dell'esecutore dei pod, presa cosi' com'e'
    _open_trade = _firm.IBKRPaperBroker._open_trade
    _fills_for = _firm.IBKRPaperBroker._fills_for
    _totals = _firm.IBKRPaperBroker._totals
    _finish = _firm.IBKRPaperBroker._finish

    def __init__(self, factory: Callable | None = None, symbols: dict[str, dict] | None = None, read_only: bool = False,
                 host: str | None = None, port: int | None = None, client_id: int | None = None, account: str | None = None,
                 price_dev: float = 0.005, timeout: float = 20.0, now: Callable[[], dt.datetime] | None = None,
                 contracts: dict | None = None):
        self.host = host or os.environ.get("IBKR_GERVA_HOST", "127.0.0.1")
        self.port = int(port or os.environ.get("IBKR_GERVA_PORT", "4002"))
        self.client_id = int(client_id if client_id is not None else os.environ.get("IBKR_GERVA_CLIENT_ID", "41"))
        self.wanted = account or os.environ.get("IBKR_GERVA_ACCOUNT") or None
        if self.port in LIVE_PORTS:
            raise PermissionError(f"porta {self.port}: e' quella dei conti REALI. Paper: 7497 (TWS) o 4002 (IB Gateway)")
        if self.wanted and not self.wanted.startswith("DU"):
            raise PermissionError("IBKR_GERVA_ACCOUNT non e' un conto paper (DU...)")
        self.map = load_map() if symbols is None else symbols
        self._rev = {(s["symbol"], s["sec_type"], s["currency"]): ours for ours, s in self.map.items()}
        self.factory, self.read_only, self.price_dev, self.timeout = factory or _firm._default_factory, read_only, price_dev, timeout
        self.now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self._contracts = contracts                    # per i test: {"STK": costruttore, "CFD": ..., "LimitOrder": ...}
        self._raw = None                               # l'oggetto IB vero
        self._ib = None                                # cio' che usano le letture (in sola lettura: l'involucro)
        self.account_id: str | None = None
        self._last = 0.0
        self._scale: dict[str, float] = {}             # client_id -> dollari dello strumento per unita' di prezzo di ricerca
        self._warned: set[str] = set()
        self._delayed = False

    # ---- collegamento e controllo del conto ----------------------------------
    @property
    def ib(self):
        if self._ib is not None and self._raw.isConnected():
            return self._ib
        self.close()
        raw = self.factory()
        try:
            raw.connect(self.host, self.port, clientId=self.client_id, timeout=self.timeout, readonly=self.read_only,
                        account=self.wanted or "")
        except Exception as e:
            raise BrokerError(f"IBKR non raggiungibile su {self.host}:{self.port} ({type(e).__name__}): TWS o IB Gateway "
                              "sono accesi, in modalita' paper, con l'API abilitata?") from e
        try:
            self.account_id = self._check_accounts(list(raw.managedAccounts()))
        except Exception:
            try:
                raw.disconnect()
            except Exception:
                pass
            raise
        self._raw, self._ib, self._delayed = raw, (_ReadOnly(raw) if self.read_only else raw), False
        log.info("IBKR collegato: conto %s, %s", _firm.mask(self.account_id), "SOLA LETTURA" if self.read_only else "ordini abilitati (paper)")
        return self._ib

    def _check_accounts(self, accts: list[str]) -> str:
        real = [a for a in accts if not a.startswith("DU")]
        if real or not accts:
            raise PermissionError(f"la sessione IBKR gestisce {len(real)} conti non paper (ammessi solo DU...): collegamento rifiutato"
                                  if real else "la sessione IBKR non gestisce alcun conto")
        if self.wanted:
            if self.wanted not in accts:
                raise PermissionError(f"la sessione IBKR non gestisce il conto {_firm.mask(self.wanted)}")
            acct = self.wanted
        elif len(accts) == 1:
            acct = accts[0]
        else:
            raise PermissionError("la sessione IBKR gestisce piu' conti paper: scegline uno con IBKR_GERVA_ACCOUNT")
        challenge = os.environ.get("IBKR_CHALLENGE_ACCOUNT") or None
        if challenge and challenge == acct:
            raise PermissionError("questo e' il conto della sfida GERVA-Q: il motore lo liquiderebbe. Serve un conto paper dedicato")
        return acct

    def close(self) -> None:
        raw, self._raw, self._ib = self._raw, None, None
        if raw is not None:
            try:
                raw.disconnect()
            except Exception:
                pass

    # ---- l'unico punto che invia ordini a IBKR ------------------------------
    def _place(self, contract, order):
        if self.read_only:
            raise PermissionError("IBKR in sola lettura: nessun ordine")
        self.ib                                                         # collega e ricontrolla i conti, se serve
        if not (self.account_id or "").startswith("DU") or order.account != self.account_id:
            raise PermissionError("ordine verso un conto non paper: bloccato")
        wait = PACING_S - (time.monotonic() - self._last)
        if wait > 0:
            self._raw.sleep(wait)
        trade = self._raw.placeOrder(contract, order)
        self._last = time.monotonic()
        return trade

    # ---- conto ---------------------------------------------------------------
    def _values(self) -> dict:
        return {(v.tag, v.currency): v.value for v in self.ib.accountValues(self.account_id)}

    def _usd_per(self, ccy: str, vals: dict | None = None) -> float:
        """Dollari per una unita' di `ccy`, dai cambi che IBKR pubblica tra i valori del conto (ExchangeRate = valore
        della valuta nella valuta base). Se il conto non ha mai avuto dollari la riga puo' mancare: si prova il cambio
        a pronti; se manca anche quello si solleva, mai un cambio inventato."""
        if ccy == "USD":
            return 1.0
        vals = vals or self._values()
        base = next((c for (tag, c) in vals if tag == "NetLiquidation" and c not in ("BASE", "")), None)
        rate = lambda c: 1.0 if c == base else _num(vals.get(("ExchangeRate", c)))
        a, b = rate(ccy), rate("USD")
        if a and b:
            return a / b
        try:
            fx = self.ib.qualifyContracts(self._make("CASH", ccy, "IDEALPRO", "USD"))
            px = self._price(fx[0]) if fx and fx[0] is not None else None
        except Exception:
            px = None
        if not px:
            raise BrokerError(f"cambio {ccy}/USD non disponibile da IBKR: il valore in dollari non e' calcolabile")
        return px

    def account(self) -> Account:
        vals = self._values()
        base = next((c for (tag, c) in vals if tag == "NetLiquidation" and c not in ("BASE", "")), None)
        nav = _num(vals.get(("NetLiquidation", base))) if base else None
        if not nav:                                    # dati non ancora arrivati: MAI un patrimonio a zero
            raise BrokerError("valore del conto IBKR non ancora disponibile")
        fx = self._usd_per(base, vals)
        try:
            cash = float(vals.get(("TotalCashValue", base)))
        except (TypeError, ValueError):
            raise BrokerError("cassa del conto IBKR non disponibile") from None
        return Account(nav * fx, cash * fx)

    def positions(self) -> dict[str, Position]:
        """Chiave = simbolo di ricerca se lo strumento e' nella mappatura, altrimenti "IBKR:<simbolo>" (posizione non
        del motore: resta visibile e conta nell'esposizione, ma il ciclo non ha un prezzo per ritoccarla)."""
        out: dict[str, Position] = {}
        vals = None
        for p in self.ib.portfolio(self.account_id):
            q = float(p.position)
            if abs(q) < 1e-9:
                continue
            c = p.contract
            px = _num(p.marketPrice)
            if not px:
                raise BrokerError(f"nessun prezzo per la posizione {c.symbol}: il valore del conto non e' calcolabile")
            if c.currency != "USD":
                vals = vals or self._values()
                px *= self._usd_per(c.currency, vals)
            px *= float(getattr(c, "multiplier", "") or 1)
            key = self._rev.get((c.symbol, c.secType, c.currency)) or f"IBKR:{c.localSymbol or c.symbol}"
            if key in out:
                raise BrokerError(f"due posizioni IBKR per {key}")
            out[key] = Position(q, px)
        return out

    # ---- contratti e prezzi --------------------------------------------------
    def _make(self, sec_type: str, symbol: str, exchange: str, currency: str):
        if self._contracts:
            return self._contracts[sec_type](symbol, exchange, currency)
        import ib_async
        if sec_type == "CASH":
            return ib_async.Forex(symbol + currency, exchange)
        return {"STK": ib_async.Stock, "CFD": ib_async.CFD}[sec_type](symbol, exchange, currency)

    def _contract(self, symbol: str):
        """Contratto qualificato dello strumento negoziabile, o None se IBKR non lo trova o lo trova ambiguo."""
        s = self.map[symbol]
        q = self.ib.qualifyContracts(self._make(s["sec_type"], s["symbol"], s["exchange"], s["currency"]))
        return q[0] if q and q[0] is not None else None

    def _price(self, contract) -> float | None:
        """Ultimo prezzo nella valuta del contratto: in tempo reale se c'e' l'abbonamento, altrimenti ritardato;
        in mancanza, l'ultima chiusura giornaliera. None se IBKR non da' nulla."""
        ib = self.ib
        if not self._delayed:
            ib.reqMarketDataType(3)                    # 3 = ritardati quando il tempo reale non e' sottoscritto
            self._delayed = True
        try:
            for t in ib.reqTickers(contract):
                for v in (t.marketPrice(), getattr(t, "last", None), getattr(t, "close", None)):
                    if _num(v):
                        return _num(v)
        except PermissionError:
            raise
        except Exception as e:
            log.info("prezzo istantaneo non disponibile (%s): provo lo storico", type(e).__name__)
        what = "TRADES" if getattr(contract, "secType", "STK") == "STK" else "MIDPOINT"
        bars = ib.reqHistoricalData(contract, "", "2 D", "1 day", what, True, 1, False)
        return _num(bars[-1].close) if bars else None

    def prices(self, symbols: list[str]) -> dict[str, float]:
        """Prezzo IN DOLLARI dello STRUMENTO NEGOZIATO (non del simbolo di ricerca), per i simboli mappati."""
        out = {}
        for s in symbols:
            if s not in self.map:
                continue
            c = self._contract(s)
            px = self._price(c) if c is not None else None
            if px:
                out[s] = px * self._usd_per(self.map[s]["currency"])
        return out

    # ---- ordini --------------------------------------------------------------
    def _ref(self, client_id: str) -> str:
        return ORDER_PREFIX + client_id

    def _completed(self, ref: str):
        try:
            return next((t for t in self.ib.reqCompletedOrders(True) if getattr(t.order, "orderRef", "") == ref), None)
        except PermissionError:
            raise
        except Exception:
            return None

    def _to_fill(self, client_id: str, requested: float | None, side: str | None, note: str = "") -> Fill | None:
        """Esito dell'ordine dai suoi eseguiti (riletti da IBKR). None se non ce ne sono."""
        ref = self._ref(client_id)
        avg, fee, filled = self._totals(ref, refresh=True)
        if filled <= 0:
            return None
        if side is None:
            ex = self._fills_for(ref)[0].execution
            side = "SELL" if str(getattr(ex, "side", "")).upper().startswith("S") else "BUY"
        sign = 1.0 if side == "BUY" else -1.0
        status = "partial" if requested and filled < requested - 1e-9 else "filled"
        scale = self._scale.get(client_id)
        if scale:
            return Fill(client_id, status, sign * filled * scale, avg / scale, fee, note)
        return Fill(client_id, status, sign * filled, 0.0, fee,
                    (note + " " if note else "") + f"recuperato: {filled:g} pezzi dello strumento negoziato a {avg:g}")

    def lookup(self, client_id: str) -> Fill | None:
        """None = IBKR non ha traccia dell'ordine (nella giornata). Un ordine ancora aperto viene portato a termine:
        si aspetta, si annulla il residuo e si attende la conferma, come fa `submit`."""
        ref = self._ref(client_id)
        try:
            t = self._open_trade(ref)
            if t is not None:
                self._wait(t, ref)
            done = t or self._completed(ref)
            requested = _num(getattr(done.order, "totalQuantity", None)) if done is not None else None
            side = getattr(done.order, "action", None) if done is not None else None
            f = self._to_fill(client_id, requested, side or None)
        except (BrokerError, PermissionError):
            raise
        except Exception as e:
            raise BrokerError(f"lookup {client_id}: {type(e).__name__}: {str(e)[:160]}") from e
        if f is not None:
            return f
        if done is not None:
            return Fill(client_id, "rejected", reason=f"nessun eseguito ({getattr(done.orderStatus, 'status', '?')})")
        return None

    def _wait(self, trade, ref: str) -> None:
        """Attesa limitata, annullamento del residuo, conferma dell'annullamento: e' firm.ibkr._finish, invariato."""
        self.ib                                        # ricollega se serve, prima di aspettare
        self._finish(trade, ref)

    def submit(self, client_id: str, symbol: str, qty: float, ref_price: float) -> Fill:
        if self.read_only:
            raise PermissionError("IBKR in sola lettura: nessun ordine")
        prior = self.lookup(client_id)                 # idempotenza: se esiste gia' se ne legge l'esito
        if prior is not None:
            return prior
        no = lambda why: Fill(client_id, "rejected", reason=why)       # rifiuti PRIMA dell'invio: nulla e' partito
        spec = self.map.get(symbol)
        if spec is None:
            return no(f"{symbol}: nessuno strumento negoziabile nella mappatura IBKR")
        if not qty or not ref_price or ref_price <= 0:
            return no("quantita' o prezzo di riferimento nulli")
        if not session_open(spec["session"], self.now()):
            return no(f"{spec['symbol']}: borsa chiusa ({spec['session']})")
        try:
            c = self._contract(symbol)
            if c is None:
                return no(f"contratto IBKR non trovato o ambiguo: {spec['symbol']} ({spec['exchange']})")
            px = self._price(c)
            if not px:
                return no(f"nessun prezzo IBKR per {spec['symbol']}")
            px_usd = px * self._usd_per(spec["currency"])
            tick = step = min_size = None
            try:
                det = self.ib.reqContractDetails(c)
                if det:
                    tick, step, min_size = (_num(getattr(det[0], k, None)) for k in ("minTick", "sizeIncrement", "minSize"))
            except Exception:
                pass
            step = step or 1.0
            pieces = math.floor(abs(qty) * ref_price / px_usd / step + 1e-9) * step
            held = next((float(p.position) for p in self.ib.portfolio(self.account_id)
                         if (p.contract.symbol, p.contract.secType, p.contract.currency) == (spec["symbol"], spec["sec_type"], spec["currency"])), 0.0)
            if held * qty < 0 and abs(abs(qty) * ref_price / px_usd - abs(held)) < step:
                pieces = abs(held)                     # chiusura: esattamente cio' che c'e', mai un pezzo in piu' o in meno
            pieces = round(pieces, 10)
            if pieces <= 0 or (min_size and pieces < min_size):
                return no(f"meno di un pezzo di {spec['symbol']} (a {px_usd:,.2f} $ l'uno)")
            side = "BUY" if qty > 0 else "SELL"
            order = self._order(side, pieces, limit_price(side, px, self.price_dev, tick), self._ref(client_id))
        except (BrokerError, ValueError) as e:
            return no(f"{type(e).__name__}: {str(e)[:160]}")
        if not spec["verified"] and symbol not in self._warned:
            self._warned.add(symbol)
            log.warning("mappatura DA VERIFICARE: %s -> %s %s su %s. Controlla questo ordine in TWS, poi metti verified: true",
                        symbol, spec["sec_type"], spec["symbol"], spec["exchange"])
        note = f"{spec['symbol']} {pieces:g} pezzi" + ("" if spec["verified"] else " [mappatura da verificare]")
        self._scale[client_id] = px_usd / ref_price
        trade = self._place(c, order)                  # da qui in poi un'eccezione = esito ignoto: il ciclo riconcilia
        self._wait(trade, self._ref(client_id))
        f = self._to_fill(client_id, pieces, side, note)
        return f or Fill(client_id, "rejected", reason=f"{note}: non eseguito al limite {order.lmtPrice:g}, annullato "
                                                       f"({getattr(trade.orderStatus, 'status', '?')})")

    def _order(self, side: str, pieces: float, lmt: float, ref: str):
        make = self._contracts["LimitOrder"] if self._contracts else __import__("ib_async").LimitOrder
        return make(side, pieces, lmt, tif="DAY", orderRef=ref, account=self.account_id)

    # ---- KILL ----------------------------------------------------------------
    def flatten(self) -> list[Fill]:
        """Annulla gli ordini aperti del motore e chiude le posizioni degli strumenti in mappatura. Le posizioni che non
        sono del motore non si toccano (si segnalano). Se una posizione del motore resta aperta (borsa chiusa, ordine
        non eseguito) si SOLLEVA: il ciclo riprova al giro dopo e non dichiara chiuso cio' che non lo e'."""
        if self.read_only:
            raise PermissionError("IBKR in sola lettura: nessun ordine")
        ib = self.ib
        for t in list(ib.openTrades()):
            if getattr(t.order, "orderRef", "").startswith(ORDER_PREFIX):
                ib.cancelOrder(t.order)
        t0 = time.monotonic()
        while any(getattr(t.order, "orderRef", "").startswith(ORDER_PREFIX) for t in ib.openTrades()) and time.monotonic() - t0 < 15:
            ib.sleep(0.5)
        out, left, stamp = [], [], int(time.time())
        for p in list(ib.portfolio(self.account_id)):
            q, c = float(p.position), p.contract
            if abs(q) < 1e-9:
                continue
            ours = self._rev.get((c.symbol, c.secType, c.currency))
            if ours is None:
                out.append(Fill(f"KILL-{stamp}-IBKR:{c.symbol}", "rejected", reason="posizione non del motore: chiudere a mano"))
                log.warning("KILL: %s non e' in mappatura, non viene toccata", c.symbol)
                continue
            cid, spec = f"KILL-{stamp}-{ours}", self.map[ours]
            if not session_open(spec["session"], self.now()):
                out.append(Fill(cid, "rejected", reason=f"{spec['symbol']}: borsa chiusa ({spec['session']})"))
                left.append(spec["symbol"])
                continue
            qc = self._contract(ours)
            px = (self._price(qc) if qc is not None else None) or _num(p.marketPrice)
            if qc is None or not px:
                out.append(Fill(cid, "rejected", reason=f"{spec['symbol']}: contratto o prezzo non disponibili"))
                left.append(spec["symbol"])
                continue
            side = "SELL" if q > 0 else "BUY"
            tick = None
            try:
                det = ib.reqContractDetails(qc)
                tick = _num(getattr(det[0], "minTick", None)) if det else None
            except Exception:
                pass
            ref = self._ref(cid)
            trade = self._place(qc, self._order(side, abs(q), limit_price(side, px, 4 * self.price_dev, tick), ref))
            self._wait(trade, ref)
            avg, fee, filled = self._totals(ref)
            avg = avg or 0.0
            sign = -1.0 if q > 0 else 1.0
            done = filled >= abs(q) - 1e-9
            out.append(Fill(cid, "filled" if done else "partial" if filled > 0 else "rejected", sign * filled, avg, fee,
                            f"{spec['symbol']}: chiusi {filled:g} di {abs(q):g} pezzi"))
            if not done:
                left.append(spec["symbol"])
        if left:
            raise BrokerError(f"KILL incompleto su IBKR, restano aperte: {', '.join(left)}")
        return out
