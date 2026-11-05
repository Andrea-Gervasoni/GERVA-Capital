"""
Modello dei costi di transazione (docs/research/risk_and_execution.md §7):

    costo = commissione + spread/2 + Y * sigma_d * sqrt(Q / V_d)

Con un NAV di 100k EUR l'impatto e' trascurabile su ETF liquidi; il costo vero e'
commissione + spread. Il modello resta completo perche' i pod possono crescere.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class CostModel:
    commission_rate: float = 0.0005      # frazione del controvalore
    commission_min: float = 0.0          # minimo per ordine, in valuta del conto
    commission_cap_rate: float = 1.0     # tetto del minimo come frazione del controvalore (IBKR crypto: 1%)
    half_spread: float = 0.0002          # meta' spread, frazione del prezzo
    impact_y: float = 0.7                # costante della legge a radice quadrata (scelta prudente)

    def cost(self, notional: float, sigma_daily: float = 0.0, adv_notional: float = math.inf) -> float:
        """Costo in valuta per un ordine di controvalore `notional` (valore assoluto)."""
        q = abs(notional)
        if q == 0:
            return 0.0
        comm = max(self.commission_rate * q, min(self.commission_min, self.commission_cap_rate * q))
        impact = 0.0
        if math.isfinite(adv_notional) and adv_notional > 0:
            impact = self.impact_y * sigma_daily * math.sqrt(q / adv_notional) * q
        return comm + self.half_spread * q + impact

    def rate(self, notional: float, sigma_daily: float = 0.0, adv_notional: float = math.inf) -> float:
        q = abs(notional)
        return self.cost(q, sigma_daily, adv_notional) / q if q else 0.0


def min_efficient_notional(m: CostModel, max_rate: float = 0.005) -> float:
    """Controvalore minimo perche' il costo di un ordine resti sotto `max_rate`.
    Sotto questa soglia la commissione minima mangia il rendimento: meglio non ribilanciare.
    Dove vale il minimo la commissione E' il minimo, quindi costo = minimo + meta' spread * q <= max_rate * q.
    Esempio: minimo 3 EUR, meta' spread 0,03% -> 3 / (0,005 - 0,0003) = ~638 EUR."""
    if m.commission_rate + m.half_spread >= max_rate:
        return float("inf")
    return m.commission_min / (max_rate - m.half_spread)


# Tariffe di partenza (verificate o dichiarate come stime nel commento)
IBKR_CRYPTO = CostModel(commission_rate=0.0018, commission_min=1.75, commission_cap_rate=0.01,
                        half_spread=0.0005)          # tariffa IBKR (fonte A); spread: stima
UCITS_ETF = CostModel(commission_rate=0.0005, commission_min=3.0, half_spread=0.0003)   # stima
US_LARGE_CAP = CostModel(commission_rate=0.0001, commission_min=1.0, half_spread=0.0001)  # stima
