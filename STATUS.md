# STATUS — GERVA Capital (4/11/2026)

Test: **72 verdi** (`python -m pytest`). Branch `claude/gifted-ramanujan-n3a5gg`.
Costo di sviluppo: non leggibile da me in questa sessione (`/cost` non è disponibile all'agente); Andrea lo legge con `/cost` dal suo terminale. Costo di esecuzione finora: **0,00 €** (nessuna chiave API: tutto in simulazione).

## M0 — Ricerca ✅
- `docs/research/`: firms, alpha_research, risk_and_execution, llm_agents_in_finance, data_and_news, gervaq_audit, DECISIONS. Ogni affermazione ha fonte e confidenza [A]/[M]/[B]; dove non ho trovato fonti ho scritto "non so".
- Audit di GERVA-Q v3: 10 rilievi. I due gravi: **R1** il DSR 0,97 della v3 è calcolato su Sharpe di prova inventati (`np.linspace`), quindi non è verificabile; **R5** l'approvazione live della crypto è un file statico.
- Durante la ricerca una pagina web conteneva una prompt injection reale: documentata come caso d'esempio.

## M1 — Fondamenta ✅
- DB SQLite con trigger append-only (audit, eventi, chiamate LLM, fill, GC, carriera, post-mortem; previsioni congelate e risolvibili una volta sola), audit con catena di hash, bus eventi, impostazioni scrivibili solo con il token di Andrea, Budget Governor (blocca, scala i modelli, sciopero automatico, avviso di autonomia), trial registry (N distinte, varianza solo dagli Sharpe osservati), Scorekeeper (Brier con scomposizione di Murphy, calibrazione, 70/30, Welch per le promozioni).
- `quantlab/`: statistica del Sharpe, PBO, CPCV, portafoglio, costi, backtest con deriva, test anti look-ahead su ogni segnale.

## M2 — Portale ✅ — `python firm.py portal` (oppure `demo` e poi `portal --demo`)
- Ufficio a 8 stanze, sprite originali da matrici, fumetti di stato, cartelline che camminano quando un compito passa di mano, luce della Sala Rischio, scrivanie VACANTE, dialogo RPG a 7 schede, organigramma, albero compiti, Posta del Capo, classifica pod, ricerca, Gateway, Impostazioni (budget, limiti, modelli, finestra, Sciopero/Riprendi, KILL), ticker, suoni 8-bit spenti di default.
- Verificato con il browser: nessun errore in console; Host estraneo → 403; scritture senza token → 403; LIVE impossibile.

## M3–M6 — Agenti, ricerca, Gateway, economia ✅ (codice) / ⏳ (agenti veri)
- 11 agenti LLM con prompt secondo la guida, schemi JSON validati con una sola correzione, eval con trappole. Flussi: Redazione (verifica su seconda fonte controllata dal codice), CRO, delega degli ordini di Andrea, ricerca → cancello → Validazione con canarini, Comitato della domenica (non può approvare ciò che la Validazione respinge), pod, ciclo talent, riallocazione con shrinkage, bonus pool.
- Gateway: 15 controlli pre-trade, sub-ledger per pod, compensazione interna, stop a scalini −5%/−7,5%, broker paper simulato (IBKR paper predisposto, non attivo).

## Cosa è ancora finto (dichiarato)
- **Gli agenti sono in simulazione**: senza `ANTHROPIC_API_KEY` rispondono con il JSON più prudente ("dati insufficienti"). Il portale lo mostra con una fascia arancione.
- **I dati di mercato del cloud sono bloccati**: la ricerca qui gira su dati sintetici (esclusi dal contatore del DSR, mai al Comitato). Sul Mac: `python firm.py data`.
- **Le notizie** non si scaricano dal cloud; sul Mac il lettore RSS è attivo (URL dei feed da verificare al primo avvio).
- **Il demo** (`var/demo/`) è interamente sintetico e marcato DEMO.

## Cosa potrebbe andare storto
- I feed RSS possono cambiare URL; il codice degrada senza errori ma la Redazione resta vuota.
- I prompt non sono ancora stati misurati su risposte vere: gli eval in simulazione verificano solo lo schema.
- Con 0,60 €/giorno ci stanno circa 30.000 token Opus o 3 milioni di token Haiku: se gli agenti si rivelano poco utili, conviene abbassare il tetto, non alzarlo.
- La correlazione tra pod e la riallocazione hanno bisogno di ≥ 60 giorni di dati in avanti prima di significare qualcosa.

## Cosa serve da Andrea (solo grandi richieste)
1. **Credenziali (cat. 4)**: mettere `ANTHROPIC_API_KEY` in `.env` per accendere gli agenti veri. *Default sicuro:* la società resta in simulazione a costo zero.
2. **Modifica di file fuori dal progetto (cat. 5)**: applicare domenica 8/11 il rilascio `research/releases/2026-11-08` (R1, R2, R5, R9) con `python firm.py release --apply 2026-11-08`. *Default sicuro:* GERVA-Q resta com'è e le correzioni restano proposte.
3. **Pubblicazione**: il repository è pubblico. Il brief (`docs/FIRM_BRIEF.md`) l'ho tenuto fuori da git perché contiene dettagli personali; lo snapshot di GERVA-Q (`_incoming/`) è escluso. *Default sicuro:* restano entrambi solo in locale.
