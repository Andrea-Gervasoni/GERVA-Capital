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
__version__ = "5.0.0"
