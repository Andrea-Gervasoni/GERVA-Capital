"""
Libro dei trade a MARGINE ISOLATO: leva alta sul singolo trade, perdita massima fissata prima di entrare.

Principio (ricerca v4, research/v5/v4/leva_trade_*.out, SIMULATO su BTC, ETH, SOL a 5 minuti, 2018-2026):

    rischio del trade   = quota di patrimonio persa se scatta lo stop                    (decide il rendimento e la rovina)
    controvalore        = rischio * patrimonio / distanza dello stop
    leva del trade      = la piu' alta che lascia lo stop entro il 60% della strada verso la liquidazione
    margine isolato     = controvalore / leva  ~ 1,7 x il rischio: e' il MASSIMO che il trade puo' perdere,
                          anche con un gap oltre lo stop o con l'exchange irraggiungibile

La leva quindi NON e' una scelta libera: discende dalla distanza dello stop. Stop a 1 x ATR (circa 5%) -> ~11x;
stop all'1,7% -> 30x; stop allo 0,9% -> 50x. Che cosa dicono i dati:

    stop 1 x ATR, ~11x : R medio +0,24 (verifica +0,18), 43% di trade vincenti          -> livello CONFERMATO
    stop 1,7%,    30x  : R medio +0,36 su prezzi spot; sui perpetual veri +0,10 in verifica     -> RITIRATO (quinta tornata)
    stop 0,9%,    50x  : R medio +0,18 (verifica +0,13),  9% vincenti, 53 perdite di fila -> NON sostenuta
    stop 0,4%,    50x  : R medio negativo: i costi valgono un terzo dello stop            -> NON sostenuta

I setup con score > 0,75 rendono piu' di quelli tra 0,60 e 0,75 in entrambi i periodi (R +0,40 contro +0,19 a 11x):
per questo il rischio per trade sale con la conviction. Sotto 0,60 il rendimento atteso e' nullo: nessun trade.

Tutti i limiti di questo modulo sono deterministici. Un agente AI puo' passare solo `ai_multiplier` in [0, 1].
"""
from __future__ import annotations

from dataclasses import dataclass, field

STOP_TO_LIQ = 0.6              # lo stop sta a non piu' del 60% della distanza dalla liquidazione
MAINTENANCE = 0.005            # margine di mantenimento ipotizzato (BTC/ETH sui principali perpetual: 0,4-0,5%)
SCORE_CONFIRMED = 0.60         # soglie fissate sul periodo di scelta (fino al 2022), mai ristimate dal vivo
SCORE_EXCEPTIONAL = 0.75


@dataclass(frozen=True)
class Tier:
    name: str
    risk: float                # quota di patrimonio rischiata sullo stop
    stop_atr: float | None     # stop in multipli dell'ATR giornaliero...
    stop_fixed: float | None   # ...oppure distanza fissa
    max_leverage: float        # tetto di leva del livello (oltre al tetto della sede)
    trail: float | None        # stop mobile: distanza dal massimo, in multipli dello stop iniziale


@dataclass(frozen=True)
class BookLimits:
    """Limiti dell'insieme dei trade aperti. Valori della ricerca v4, schema S2 (1% / 2%)."""
    confirmed: Tier = Tier("confermato", 0.010, 1.0, None, 15.0, 2.0)
    exceptional: Tier = Tier("eccezionale", 0.020, 1.0, None, 15.0, 2.0)
    # Il livello a 30x (stop 1,7%, rischio 0,5%) e' RITIRATO: sui prezzi veri dei perpetual il suo R in verifica si dimezza
    # (+0,20 -> +0,10) e con il funding di Hyperliquid scende a +0,08, non distinguibile da zero
    # (research/v5/v5/a9_esecuzione). Il campo resta per poterlo riprovare in paper, ma `propose` non lo usa piu'.
    exceptional_tight: Tier = Tier("eccezionale-30x (ritirato)", 0.005, None, 0.017, 30.0, None)
    max_open_risk: float = 0.06        # somma dei rischi dei trade aperti
    max_margin: float = 0.15           # somma dei margini isolati = PERDITA MASSIMA del libro in un solo evento (gap, sede
                                       # irraggiungibile). Se la sede concede meno leva di quella 'sicura' il margine per trade
                                       # sale (a 10x con stop al 3%: 3,3 volte il rischio; a 2x: 16 volte) e questo tetto riduce i trade
    max_notional: float = 1.5          # somma dei controvalori, in multipli del patrimonio
    max_trades: int = 4
    day_stop_new: float = -0.03        # perdita di giornata oltre la quale non si aprono trade
    day_close_all: float = -0.05       # perdita di giornata oltre la quale si chiude tutto fino a domani
    hard_max_leverage: float = 15.0    # nessun trade oltre, qualunque cosa dica la sede o la configurazione (era 30: ritirato)
    hard_max_risk: float = 0.02        # nessun trade rischia oltre, qualunque sia il livello


@dataclass
class Trade:
    symbol: str
    side: int                  # +1 long, -1 short
    entry: float
    stop: float
    notional: float
    margin: float
    leverage: float
    risk: float                # in valuta, allo stop iniziale
    liquidation: float
    tier: str
    best: float = 0.0
    initial_stop_distance: float = 0.0
    trail: float | None = None

    def __post_init__(self):
        self.best = self.best or self.entry
        self.initial_stop_distance = self.initial_stop_distance or abs(self.entry - self.stop) / self.entry


@dataclass
class Decision:
    ok: bool
    reason: str = ""
    trade: Trade | None = None
    checks: dict = field(default_factory=dict)


def safe_leverage(stop_distance: float) -> float:
    """La leva piu' alta per cui lo stop resta entro STOP_TO_LIQ della distanza dalla liquidazione."""
    return 1.0 / (stop_distance / STOP_TO_LIQ + MAINTENANCE)


def tier_for(score: float | None, limits: BookLimits, tight: bool = False) -> Tier | None:
    if score is None or score != score or score <= SCORE_CONFIRMED:
        return None
    if score > SCORE_EXCEPTIONAL:
        return limits.exceptional          # `tight` e' ignorato: il livello a 30x e' ritirato
    return limits.confirmed


class TradeBook:
    """Stato dei trade aperti e regole di ammissione. Nessun ordine parte da qui: restituisce decisioni."""

    def __init__(self, limits: BookLimits | None = None):
        self.limits = limits or BookLimits()
        self.open: dict[str, Trade] = {}
        self.day_pnl = 0.0             # P&L realizzato di giornata, in frazione del patrimonio di inizio giornata
        self.halted_today = False

    # ---- giornata ------------------------------------------------------------
    def new_day(self) -> None:
        self.day_pnl, self.halted_today = 0.0, False

    def totals(self, equity: float) -> dict:
        t = self.open.values()
        return dict(risk=sum(x.risk for x in t) / equity, margin=sum(x.margin for x in t) / equity,
                    notional=sum(x.notional for x in t) / equity, n=len(self.open))

    # ---- ammissione ----------------------------------------------------------
    def propose(self, symbol: str, side: int, price: float, atr_frac: float, score: float | None, equity: float,
                venue_max_leverage: float, engine_scale: float = 1.0, ai_multiplier: float = 1.0,
                tight: bool = False) -> Decision:
        """atr_frac: ATR giornaliero / prezzo, noto la sera prima. engine_scale: scala del motore di rischio del conto
        (1 NORMAL, 0,5 REDUCED, 0 HALTED/KILLED). ai_multiplier: solo in [0, 1]."""
        L = self.limits
        if side not in (1, -1) or price <= 0 or equity <= 0:
            return Decision(False, "parametri non validi")
        if not 0.0 <= ai_multiplier <= 1.0:
            return Decision(False, "moltiplicatore AI fuori da [0, 1]: rifiutato")
        if not 0.0 <= engine_scale <= 1.0:
            return Decision(False, "scala del motore di rischio non valida")
        if engine_scale == 0.0:
            return Decision(False, "motore di rischio fermo: nessun nuovo trade")
        if self.halted_today or self.day_pnl <= L.day_stop_new:
            return Decision(False, f"interruttore di giornata: P&L {self.day_pnl:.2%}")
        if symbol in self.open:
            return Decision(False, "trade gia' aperto su questo strumento")
        if len(self.open) >= L.max_trades:
            return Decision(False, "numero massimo di trade aperti")
        tier = tier_for(score, L, tight)
        if tier is None:
            return Decision(False, "conviction sotto la soglia: nessun trade")
        stop_d = tier.stop_fixed if tier.stop_fixed is not None else tier.stop_atr * atr_frac
        if not 0.003 <= stop_d <= 0.15:
            return Decision(False, f"distanza dello stop non plausibile ({stop_d:.2%})")
        lev = min(safe_leverage(stop_d), tier.max_leverage, venue_max_leverage, L.hard_max_leverage)
        if lev < 1.0:
            return Decision(False, "leva ammessa dalla sede inferiore a 1")
        risk_frac = min(tier.risk, L.hard_max_risk) * engine_scale * ai_multiplier
        if risk_frac <= 0:
            return Decision(False, "rischio azzerato dall'overlay")
        tot = self.totals(equity)
        risk_frac = min(risk_frac, L.max_open_risk - tot["risk"])
        notional = min(risk_frac * equity / stop_d, (L.max_notional - tot["notional"]) * equity)
        margin = notional / lev
        if margin > (L.max_margin - tot["margin"]) * equity:
            margin = (L.max_margin - tot["margin"]) * equity
            notional = margin * lev
        if notional <= 0 or risk_frac <= 0:
            return Decision(False, "nessuno spazio residuo (rischio, margine o controvalore)")
        liq_d = 1.0 / lev - MAINTENANCE
        if stop_d > STOP_TO_LIQ * liq_d + 1e-12:
            # la sede concede meno leva del necessario: il trade resta valido, lo stop e' ancora piu' lontano dalla liquidazione
            pass
        t = Trade(symbol, side, price, price * (1 - side * stop_d), notional, margin, lev, notional * stop_d,
                  price * (1 - side * liq_d), tier.name, trail=tier.trail)
        checks = dict(stop_distance=stop_d, liquidation_distance=liq_d, stop_over_liq=stop_d / liq_d,
                      risk_frac=t.risk / equity, max_loss_frac=margin / equity, notional_frac=notional / equity)
        return Decision(True, "", t, checks)

    def add(self, trade: Trade) -> None:
        self.open[trade.symbol] = trade

    # ---- gestione ------------------------------------------------------------
    def update_stop(self, symbol: str, high: float, low: float) -> float:
        """Stop mobile: si sposta solo nella direzione che riduce il rischio. Restituisce lo stop corrente."""
        t = self.open[symbol]
        if t.trail is None:
            return t.stop
        fav = high if t.side == 1 else low
        if t.side * (fav - t.best) > 0:
            t.best = fav
            new = t.best * (1 - t.side * t.trail * t.initial_stop_distance)
            if t.side * (new - t.stop) > 0:
                t.stop = new
        return t.stop

    def close(self, symbol: str, exit_price: float, equity_start_of_day: float, costs: float = 0.0) -> float:
        """Chiude il trade e restituisce il P&L in valuta. La perdita non supera MAI il margine isolato."""
        t = self.open.pop(symbol)
        pnl = max(t.side * (exit_price / t.entry - 1) * t.notional - costs, -t.margin)
        self.day_pnl += pnl / equity_start_of_day
        if self.day_pnl <= self.limits.day_close_all:
            self.halted_today = True
        return pnl

    def must_flatten(self) -> bool:
        return self.halted_today
