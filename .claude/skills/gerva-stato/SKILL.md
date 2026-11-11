---
name: gerva-stato
description: Mostra lo stato del motore live di GERVA Capital (rischio, conto, ultimi eventi, cancelli paper->reale). Usalo quando l'utente chiede come sta andando il fondo, se il sistema gira o se e' pronto per il denaro reale.
---

1. Esegui `python -m gerva status` e `python -m gerva gates`.
2. Leggi `var/gerva/snapshot.json`: `meta.as_of` (quanto e' vecchia), `risk.state` e `risk.state_reason`, `nav`, `system.components`.
3. Riferisci: stato del rischio e perche'; patrimonio e caduta dal massimo; componenti non "ok"; cancelli rossi.
4. Se la fotografia ha piu' di 40 minuti, dillo per prima cosa: il ciclo e' fermo. Delega la diagnosi all'agente `gerva-operazioni`.
5. Il passaggio al reale si propone solo con TUTTI i cancelli verdi; anche allora decide Andrea.
