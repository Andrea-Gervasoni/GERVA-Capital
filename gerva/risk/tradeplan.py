"""
Leva del SINGOLO TRADE, distinta dalla leva del CONTO.

Decisione di Andrea (11/11/2026): leva bassa sul conto, leve piu' alte sul singolo trade.
Sono due grandezze diverse e questo modulo le tiene separate:

    leva del trade  = controvalore della posizione / margine isolato messo su QUEL trade        (anche 10-20x)
    leva del conto  = somma dei controvalori / patrimonio                                        (tetto: gerva.risk.engine)
    rischio a trade = patrimonio perso se scatta lo stop                                         (0,25%-1%)

Un trade a 15x con un margine pari all'1,5% del patrimonio espone il conto per il 22%: se va a zero il margine,
il conto perde l'1,5%. La leva alta qui e' un modo di usare meno capitale per la stessa esposizione, non un modo
di rischiare di piu'. Quello che NON si fa e' portare l'intero conto a 10x: nei dati un conto a 10x viene dimezzato
nel 62% dei casi in tre anni nello scenario prudente (research/v5/v2/leva_montecarlo_e_stop_intraday.out).

Regole dure (non configurabili da un agente):
  * lo stop deve stare PRIMA della liquidazione, con un margine di sicurezza: distanza_stop <= 0,6 * distanza_liquidazione;
  * la leva del trade non supera il tetto di legge dello strumento per un cliente al dettaglio UE;
  * il rischio per trade dipende dal livello di conviction e non supera MAX_RISK;
  * il controvalore non porta il conto oltre il tetto di esposizione residuo.
"""
from __future__ import annotations

from dataclasses import dataclass

# tetti di leva per un cliente al dettaglio UE (ESMA 2018; perpetual: dichiarazione ESMA 24/2/2026; i futures quotati non
# hanno tetto ESMA: vale il margine della borsa, qui limitato a 20x per prudenza)
LEGAL_MAX = {"cfd_fx_major": 30.0, "cfd_index": 20.0, "cfd_commodity": 10.0, "cfd_equity": 5.0, "cfd_crypto": 2.0,
             "perp_crypto": 2.0, "future_index": 20.0, "spot": 1.0}
RISK_BY_TIER = {"bassa": 0.0, "media": 0.005, "alta": 0.010}      # quota di patrimonio rischiata sullo stop
MAX_RISK = 0.010
STOP_TO_LIQ = 0.6                                                  # lo stop a non piu' del 60% della strada verso la liquidazione
MAINTENANCE = 0.005


@dataclass
class TradePlan:
    ok: bool
    reason: str = ""
    notional: float = 0.0            # controvalore
    margin: float = 0.0              # margine isolato
    trade_leverage: float = 0.0
    risk: float = 0.0                # perdita in valuta se scatta lo stop
    risk_frac: float = 0.0
    stop_distance: float = 0.0
    liquidation_distance: float = 0.0
    account_exposure: float = 0.0    # controvalore / patrimonio


def plan(equity: float, tier: str, stop_distance: float, instrument: str, exposure_room: float,
         desired_leverage: float | None = None, ai_multiplier: float = 1.0) -> TradePlan:
    """stop_distance: distanza dello stop dal prezzo di ingresso, in frazione (es. 0,02 = 2%; tipicamente 2 x ATR).
    exposure_room: quanta esposizione (in multipli del patrimonio) il motore di rischio concede ancora.
    ai_multiplier: fattore dell'overlay AI, ammesso solo in [0, 1]: l'AI puo' ridurre o vietare, mai aumentare."""
    if instrument not in LEGAL_MAX:
        return TradePlan(False, f"strumento sconosciuto: {instrument}")
    if not 0.0 <= ai_multiplier <= 1.0:
        return TradePlan(False, "moltiplicatore AI fuori da [0, 1]")
    risk_frac = min(RISK_BY_TIER.get(tier, 0.0), MAX_RISK) * ai_multiplier
    if risk_frac <= 0 or equity <= 0:
        return TradePlan(False, f"conviction '{tier}': nessun trade")
    if not 0.001 <= stop_distance <= 0.5:
        return TradePlan(False, "distanza dello stop non plausibile")
    cap = LEGAL_MAX[instrument]
    # la leva piu' alta per cui lo stop sta ancora al sicuro dalla liquidazione: 1/L - mm >= stop / STOP_TO_LIQ
    safe = 1.0 / (stop_distance / STOP_TO_LIQ + MAINTENANCE)
    lev = min(cap, safe, desired_leverage or cap)
    if lev < 1.0:
        lev = 1.0
    notional = min(risk_frac * equity / stop_distance, max(exposure_room, 0.0) * equity)
    if notional <= 0:
        return TradePlan(False, "nessuno spazio di esposizione residuo")
    margin = notional / lev
    risk = notional * stop_distance
    return TradePlan(True, "", notional, margin, lev, risk, risk / equity, stop_distance, 1.0 / lev - MAINTENANCE,
                     notional / equity)
