"""
Ciclo di automiglioramento: il sistema studia i propri trade, trova dove perde, propone una correzione e la fa validare
da codice indipendente prima che tocchi qualcosa.

    memoria dei trade  ->  valutazione (debolezze)  ->  ipotesi  ->  validazione  ->  ombra  ->  approvazione di Andrea  ->  attiva
          ^                                                                                                               |
          +---------------------------------------------- nuovi trade ---------------------------------------------------+

Regole che il codice fa rispettare (test in tests/test_gerva_learn.py):
  1. chi propone non approva: le ipotesi le genera il motore di valutazione (o, se c'e' una chiave, un agente LLM);
     il verdetto lo da' solo `validate`, che e' deterministico;
  2. una correzione puo' solo RIDURRE il rischio: salta un trade o ne riduce la taglia (moltiplicatore in [0, 1]);
     non puo' aumentare rischio, leva o esposizione, ne' toccare stop e limiti;
  3. ogni ipotesi provata e' contata per sempre: la soglia statistica sale con il numero di ipotesi, cosi' cercare di piu'
     rende piu' difficile passare, non piu' facile;
  4. una correzione che passa la validazione storica entra IN OMBRA: viene misurata sui trade paper senza agire;
  5. diventa ATTIVA solo con un comando esplicito di Andrea (`python -m gerva learn --approve ID --confirm`).
"""
from .memory import TradeMemory, TradeRecord
from .evaluate import evaluate, weaknesses
from .improve import Rule, Registry, propose, validate, cycle, multiplier

__all__ = ["TradeMemory", "TradeRecord", "evaluate", "weaknesses", "Rule", "Registry", "propose", "validate", "cycle", "multiplier"]
