"""
GERVA core: il motore deterministico di trading (nessun LLM nel percorso degli ordini).

    gerva.data        sorgenti pubbliche con cache e impronta del contenuto
    gerva.indicators  VWAP, GEX, volatilita', momentum: funzioni causali (solo dati <= t)
    gerva.backtest    motore giornaliero (leva, finanziamento, costi) e intraday
    gerva.strategies  una funzione per strategia; ogni output e' gia' "decisione a fine t"
    gerva.validation  walk-forward, Monte Carlo a blocchi, rovina, cancelli numerici
    gerva.portfolio   allocazione tra strategie, volatilita' obiettivo, leva di Kelly
    gerva.risk        limiti e motore di rischio in tempo reale (scala di drawdown, KILL)
    gerva.execution   interfaccia broker, broker paper, macchina a stati degli ordini
    gerva.ops         registro durevole, retry, interruttore, supervisore, allarmi
    gerva.live        il ciclo che gira in produzione

Tutto cio' che esce da gerva.backtest e gerva.validation e' SIMULATO su dati storici.
"""
def _read_version() -> str:
    """La versione sta in un posto solo: il file VERSION alla radice del repository (lo legge anche il distintivo del README)."""
    import os
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "VERSION")) as f:
            return f.read().strip() or "0.0.0"
    except OSError:
        return "0.0.0"


__version__ = _read_version()
