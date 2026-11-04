"""
quantlab — motore di ricerca di GERVA Capital.

Tutto ciò che si calcola sta qui, in codice deterministico e testato: statistica
del Sharpe, overfitting, validazione incrociata nel tempo, costruzione del
portafoglio, costi, backtest con deriva dei pesi, test anti look-ahead.

Gli agenti LLM non calcolano mai: chiamano queste funzioni come strumenti e
copiano i numeri che restituiscono (docs/PROMPT_ENGINEERING.md, §3).
"""
__version__ = "0.1.0"
