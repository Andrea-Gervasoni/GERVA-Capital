---
name: gerva-ipotesi
description: Fa lavorare insieme i sotto-agenti di GERVA Capital su una nuova ipotesi di strategia: il ricercatore la propone, il motore la misura, il validatore la attacca, il rischio puo' porre il veto. Usalo quando l'utente chiede di cercare o valutare una nuova strategia.
---

Catena (ogni passo e' un sotto-agente diverso; non saltarne nessuno):
1. `gerva-ricercatore`: cerca l'evidenza e scrive UNA scheda JSON (famiglia e parametri ammessi da `gerva/agents/spec.py`).
2. Motore: `python -m gerva propose scheda.json`. La prova viene contata nel registro `research/v5/trials.jsonl`.
3. `gerva-validatore`: riceve scheda e numeri SENZA il nome dell'autore e cerca difetti concreti (look-ahead, costi, sovradattamento).
4. `gerva-rischio`: guarda caduta massima e mese peggiore; puo' solo porre il veto.
5. Decisione: e' quella del comando al passo 2. Se e' "AMMESSA AL PAPER TRADING", la strategia entra in paper solo dopo
   che Andrea l'ha aggiunta a `gerva/strategies/book.py` con il suo test anti look-ahead. Mai direttamente nel conto reale.

Riferisci all'utente: esito, numeri (scelta, verifica, costi doppi, ritardo), difetti trovati, e quante prove sono state
consumate finora (piu' prove = soglia piu' alta per tutte le successive).
