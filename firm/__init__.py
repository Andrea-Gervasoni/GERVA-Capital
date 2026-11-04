"""
GERVA Capital — una societa' di trading quantitativo simulata, fatta di agenti AI,
con regole vere: solo paper, rischio deterministico, audit con catena di hash.

Struttura:
  firm.db          database SQLite (schema e trigger append-only)
  firm.audit       registro append-only con catena di hash (regola inviolabile 11)
  firm.events      bus eventi (tabella + notifiche al portale)
  firm.settings    impostazioni: le scrive SOLO Andrea dal portale
  firm.registry    organigramma e agenti (agents/<id>/profile.yaml)
  firm.budget      Budget Governor (codice, non un agente)
  firm.trials      trial registry globale -> Deflated Sharpe
  firm.scorekeeper punteggi calcolati da codice (Brier, calibrazione, ruoli)
  firm.risk        motore di rischio deterministico, KILL
  firm.gateway     Gateway di Esecuzione, sub-ledger per pod, broker paper
  firm.economy     Gerva-Coin, bonus pool, riallocazione con shrinkage
"""
