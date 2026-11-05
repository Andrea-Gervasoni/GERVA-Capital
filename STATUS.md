# STATUS — GERVA Capital (4/11/2026)

Test: **84 verdi** (`python -m pytest`). Branch `claude/gifted-ramanujan-n3a5gg`.
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

## v2 — richiesta di Andrea: grafica, uffici, edificio, riunioni, incentivi, motore, report ✅
- **Portale riscritto** ad alta risoluzione (72×45 tessere, persone 16×24 con 4 direzioni e passo, robot per gli automi), telecamera con zoom e spostamento, insegna con stemma e font pixel, cielo e skyline che seguono l'ora reale. Verificato nel browser, senza errori.
- **Uffici per grado** con arredo crescente; **edificio** a 6 livelli legato al massimo storico del NAV (non scende mai), con servizi che si sbloccano per tutti. Nel demo: livello 3 (palestra aperta).
- **Sala riunioni** (`firm/meetings.py`): convocate da allarmi, allocazione mensile, fascicoli che passano il cancello. Posizione indipendente → una replica → decide il codice pesando per calibrazione → alla scadenza i fatti risolvono e si paga con una regola di Brier **propria**.
- **Incentivi** (`firm/compensation.py`): stipendio per grado, bonus sempre differito 4 settimane, clawback automatico (errore grave, pod chiuso). Prompt v2 con un carattere per agente e le regole di guadagno (`agents/PROMPTS_CHANGELOG.md`).
- **Motore:** banco `quantlab/gervaq4.py` con 9 varianti contro la v3. Vincoli: PBO, bootstrap appaiato, holdout di 2 anni mai usato per scegliere; se nessuna supera i cancelli si tiene la v3. Ordine minimo efficiente (costo ≤ 0,5%).
- **Report** giornalieri con correzioni automatiche (`firm/reports.py`, pannello Report).

### Analisi e correzioni di questo giro (errori trovati e corretti)
1. Regola di ricompensa delle riunioni: la prima versione pagava anche chi sbagliava al 60% di fiducia. Ora vale zero per chi dichiara 50%, ed è sempre una regola propria (test).
2. Il demo scriveva promozioni e lezioni nei file versionati di `agents/`: ora usa una copia in `var/demo/agents` e ho ripulito una lezione "[DEMO]" finita in un commit.
3. La diagnostica ha trovato che i pod del demo mandavano ordini da 120–300 € con commissione minima > 1%: introdotto l'ordine minimo efficiente. Lo stesso problema esiste in GERVA-Q (`live.py`, ordini da 200 €): **rilievo R11**, da verificare con la tariffa reale.
4. Grafica: strisce "in costruzione" che sbordavano nella palestra; indice di palette negativo per hash sopra 2³¹; nome `table` in conflitto. Tutti corretti.
5. Backtester: `W.values` letto dentro il ciclo (costo quadratico) → letto una volta sola.

### Cosa è ancora finto o da verificare
- Agenti in simulazione senza chiave; banco v4 testato solo su dati sintetici (sul Mac: `firm.py data` e poi `firm.py research gervaq4`).
- Le tariffe UCITS (minimo 3 €) sono stime: vanno lette sul listino IBKR prima di cambiare R11.
- Il livello dell'edificio e gli arredi sono rappresentazione: non cambiano nessuna regola di rischio.

## v3 — IBKR, server, sicurezza, revisione con una squadra di agenti ✅
- **IBKR (`firm/ibkr.py`)**: osservatore in sola lettura del conto della sfida (involucro che vieta ogni metodo
  di scrittura, mai un NAV a zero, mai il conto sbagliato) ed esecutore dei pod **solo** su un secondo conto paper.
  Ordini limite sul tick, quantità intere, orari di borsa con ora legale, registrazione prima dell'invio e
  recupero dopo un crash, annullamento confermato, KILL. Senza secondo conto la società lo chiede nella posta (cat. 4).
- **Server (`deploy/`, guida in `docs/DEPLOY.md`)**: Docker con utente non root, filesystem in sola lettura, nessuna
  capability; reti interne separate (gateway della sfida raggiungibile solo dall'osservatore); portale solo via
  tunnel SSH con password; backup cifrati; aggiornamenti che rieseguono i test.
- **Demo provabile**: il portale vero impacchettato su un'istantanea del demo, in sola lettura
  (pubblicato come pagina privata su claude.ai).

### La revisione: quattro agenti indipendenti, 50 rilievi
Revisori in parallelo su sicurezza (12), ordini IBKR (13), correttezza quantitativa (11) e interfaccia (14).
Corretti tutti quelli di gravità critica, alta e media, quasi sempre con un test che riproduce il caso. I più gravi:
1. **KILL inutilizzabile sul server**: il file stava nel codice, in sola lettura. Ora nel volume.
2. **Gateway che ignorava gli ordini in attesa**: dieci acquisti accettati prima del flush portavano la leva a 2,4×
   e permettevano short. Ora gli ordini aperti contano nei controlli.
3. **Crash dopo l'invio**: l'eseguito andava perso o l'ordine si poteva reinviare. Ora registrazione prima
   dell'invio, recupero dal broker, "da verificare" se manca la traccia.
4. **Bonus pagato ogni mese sullo stesso alpha** (cumulato dall'inizio). Ora solo sull'alpha nuovo.
5. **Test anti look-ahead cieco a un passo di futuro** (NaN asimmetrici ignorati). Ora li conta.
6. **Promozioni** che premiavano valori alti anche delle metriche "meno è meglio". Ora normalizzate.
7. **Riunioni**: il capo di un pod scommetteva sul proprio pod e vinceva "mantieni" a pod fermo. Ora escluso,
   finestra fissa, annullamento se l'esito non è verificabile.
8. **Sicurezza**: il container degli agenti raggiungeva il gateway della sfida; WebSocket senza controllo
   dell'Origin; rate limit aggirabile in parallelo; backup mai eseguiti (nome del volume); demo che scriveva i
   limiti di rischio veri; impostazioni senza validazione (budget a −5 accettato). Tutti corretti con test.
9. Trovato da me nella prova con compose: **Docker Compose troncava l'hash della password** (interpreta i `$`).
   Nuovo formato senza `$`.

Rimasti aperti, di gravità bassa, dichiarati:
- `nav_marks`, `meetings` e `trials` accettano ancora UPDATE (servono per ricalcolare i segni giornalieri e lo stato);
  la testa dell'audit fuori dal DB rileva le cancellazioni, ma chi controlla il server può riscrivere tutto (serve una copia esterna: il backup cifrato la contiene).
- Valute: i controlli di rischio trattano i prezzi come EUR; l'esecutore IBKR rifiuta un prezzo in una valuta diversa da quella del contratto invece di convertire. Le festività di borsa non sono gestite (l'ordine non si esegue e si annulla).
- Sul server i segreti passati come variabili si vedono con `docker inspect` (chi può farlo è già root); i container di IB Gateway non hanno `cap_drop` perché l'immagine ne ha bisogno per l'interfaccia grafica.
- Sessioni del portale: c'è il logout, ma non la revoca di una singola sessione (si revocano tutte cancellando `session.key`).
- Interfaccia: sul telefono l'edificio intero ha scritte troppo piccole (ora c'è lo zoom a due dita); i pannelli gestiscono il fuoco all'apertura e alla chiusura ma non lo intrappolano.

Test: **127** (126 nel container, uno richiede lo snapshot di GERVA-Q).

### Cosa resta da verificare (non verificabile da qui)
- Login reale di IB Gateway, 2FA, nomi delle linee UCITS su IBKR, regole crypto del conto paper.
- Un feed di prezzi reale per i pod: senza, sul server i pod non inviano ordini (i prezzi li scrive solo il demo).
- `git push`: il permesso è stato negato in questa sessione; i commit sono pronti nel branch locale.

## Materiale esterno del 5/11 (post, guide, video): valutato
Dettagli, fonti e livelli di fiducia in `docs/research/fonti_esterne_2026-11.md`. In breve:
- **Applicato:** `firm.py check-backtest` (`quantlab/luck.py`) per verificare quanto un risultato visto in giro possa
  essere fortuna: DSR, MinTRL deflazionata, varianti necessarie per spiegarlo col caso, intervallo di Wilson e coerenza
  della percentuale di vincite, soglia di pareggio, margine dopo i costi. 9 test sulle proprieta' matematiche.
- **Ipotesi per la Ricerca:** H-ATT-1, attenzione e crypto, da registrare nel trial registry prima di qualsiasi test.
- **Non adottati, con motivo:** TradingView via MCP, Vibe-Trading, Freqtrade, bot di memecoin Solana,
  DeepSeek Super-Agent, Grok come secondo modello. OpenBB e Lean restano utili sul Mac, piu' avanti.

## 5/11/2026: il banco v4 su dati REALI (2004-oggi, 116 serie, Yahoo Finance)
Report: `research/gervaq4/2026-11-05.md`. Solo il motore azionario (meta' della v3); la sleeve crypto non e' toccata.

| | Sharpe | CAGR | Vol | MaxDD |
|---|---|---|---|---|
| v3 (riespressa in quantlab, periodo di scelta) | 0,69 | 5,7% | 8,6% | -15,9% |
| v4 "tutto" (ERC + liquidita' al tasso a breve + freno momentum + VIX + banda 5%) | 0,86 | 4,0% | 4,7% | -9,0% |
| v4 "tutto", esposizione massima senza leva (x2, 76% investito, periodo intero) | 0,81 | 6,2% | 7,7% | -13,2% |

- **Supera tutti i cancelli:** P(Sharpe > v3) 0,97 nel periodo di scelta e 0,97 nei 2 anni mai usati per scegliere
  (Sharpe 1,38 contro 0,88); PBO 0,22; DSR 0,996 contando tutte le 64 prove del registro.
- **Il DSR della v3 ricalcolato con gli Sharpe veri e' 0,97** (rilievo R1: prima era calcolato su valori inventati).
- **Cosa vuol dire in soldi:** a esposizione normale la v4 guadagna MENO della v3 (rischia la meta'). Usando il
  capitale che lascia fermo, senza leva, guadagna un po' di piu' (6,2% contro 5,7%) con perdite massime minori
  (-13% contro -16%). E' un miglioramento di qualita', non un moltiplicatore.
- **Limiti dichiarati:** la riespressione della v3 in quantlab non coincide con i numeri di GERVA-Q (CAGR 5,7% contro
  7,1% del README della v3), quindi vale il confronto relativo; survivorship nell'universo azionario (R6) per entrambe.

### Prossimo passo, deciso prima di vedere i dati: il portafoglio ombra
Dal 5/11/2026 `firm/shadow.py` registra ogni sera, senza ordini, il rendimento in avanti di v3 e v4 (ogni giorno
scritto una volta sola). Dopo **40 giorni di borsa** (meta' gennaio 2027): se P(Sharpe v4 > v3) >= 0,80 e il drawdown
della v4 non e' peggiore, la societa' propone ad Andrea di adottarla (grande richiesta n.5, finestra della domenica,
dichiarata in REGOLE_SFIDA come modifica decisa dopo aver visto i risultati). Altrimenti si resta sulla v3.

## 5/11/2026: nuova direzione (Andrea)
Non più sfida: crescita massima del capitale, poi soldi veri dei genitori (dettagli e limiti in `docs/research/DECISIONS.md`).
- Capitale letto da IBKR (prima osservazione, scritta una volta); nel portale il valore del conto dice "prova" finché
  IBKR non è collegato. Corretto il doppio conteggio tra conto IBKR e capitale virtuale dei pod.
- Piano v4 approvato in modo condizionato: ombra fino a metà gennaio, poi patch nella finestra della domenica.
