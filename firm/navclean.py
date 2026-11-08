"""
Pulizia della serie del conto prima di disegnarla.

Il programma che legge IBKR scrive un punto al minuto. Ogni tanto una lettura e' sballata (valuta, stima del guadagno, riconnessione):
un picco di qualche punto percentuale che schiaccia la scala del grafico e nasconde l'andamento vero. Qui si raggruppano i punti per
quarto d'ora (mediana) e si tolgono quelli che si discostano troppo dalla mediana dei vicini (filtro di Hampel). Un movimento VERO,
che resta, cambia la mediana dei vicini e non viene toccato; un picco che dura qualche ora si': e' piu' corto della finestra.
Il primo punto (il valore di partenza) resta sempre.
"""
from __future__ import annotations

import calendar
import statistics
import time


def _epoch(ts: str) -> int:
    ts = ts if len(ts) >= 19 else ts + ":00" * ((19 - len(ts)) // 3)
    return calendar.timegm(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))


def clean(points: list[tuple[str, float]], bucket_s: int = 900, window: int = 12, thresh: float = 0.01) -> list[tuple[str, float]]:
    """points: [(iso, valore)]. Ritorna [(iso, valore)] raggruppati per `bucket_s` secondi e senza i punti anomali (> thresh dalla mediana dei vicini)."""
    if len(points) < 4:
        return list(points)
    pts = sorted(points)
    first = pts[0]
    buckets: dict[int, list[tuple[str, float]]] = {}
    for ts, v in pts[1:]:
        buckets.setdefault(_epoch(ts) // bucket_s, []).append((ts, v))
    rows = [first] + [(b[-1][0], statistics.median(v for _, v in b)) for _, b in sorted(buckets.items())]
    if len(rows) < 7:
        return rows
    out = [rows[0]]
    n = len(rows)
    for i in range(1, n):
        ts, v = rows[i]
        med = statistics.median(r[1] for r in rows[max(0, i - window):min(n, i + window + 1)])
        if med and abs(v / med - 1) <= thresh:
            out.append((ts, v))
    return out
