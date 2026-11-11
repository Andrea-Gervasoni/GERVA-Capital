---
name: gerva-ricerca
description: Riesegue tutti i backtest di GERVA Capital sui dati reali aggiornati e riassume che cosa e' cambiato. Usalo quando l'utente chiede di aggiornare la ricerca, rifare i backtest o vedere i risultati delle strategie.
---

1. Esegui `python -m gerva research` (2 minuti circa; `--refresh` solo se l'utente chiede di riscaricare i dati).
2. Confronta `research/v5/RESULTS.md` con la versione in git (`git diff --stat research/v5/`).
3. Riferisci, in italiano e in poche righe: Sharpe del portafoglio (tutto, scelta, verifica), Deflated Sharpe, caduta massima,
   e quali strategie sono peggiorate nel periodo di verifica. Scrivi sempre che i numeri sono SIMULATI.
4. Non modificare strategie o limiti per "migliorare" il risultato: se qualcosa e' peggiorato, dillo.
