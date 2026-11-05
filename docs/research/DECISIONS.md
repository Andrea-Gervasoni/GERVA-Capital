# Dieci decisioni di progetto che derivano dalla ricerca

| # | Decisione | Motivazione (fonte) | Reversibile? |
|---|---|---|---|
| D1 | **Gli LLM non generano alpha; l'alpha viene da codice deterministico validato.** Gli agenti leggono, verificano, propongono ipotesi, giudicano, scrivono post-mortem. | Nei test lunghi e ampi il vantaggio delle strategie LLM si deteriora (FINSABER); le classifiche generali dei modelli non predicono il trading (LiveTradeBench); look-ahead impossibile da escludere su storico (Glasserman & Lin). `llm_agents_in_finance.md` §1–2 | Sì: un segnale LLM può entrare nel Pod Zero dopo una valutazione **in avanti** abbastanza lunga (MinTRL). |
| D2 | **Un solo `trial_registry` globale alimenta il Deflated Sharpe di ogni proposta**; vietato calcolare il DSR con prove non registrate. | Con molte prove la maggior parte delle scoperte è falsa (Harvey-Liu-Zhu, Hou-Xue-Zhang); il DSR dipende da N e dalla varianza degli Sharpe delle prove (Bailey & López de Prado). Rilievo R1 dell'audit. `alpha_research.md` §0, §4 | No: è il cuore della difesa contro i falsi positivi. |
| D3 | **Cancello automatico in codice prima della Validazione:** DSR ≥ 0,95, PBO ≤ 0,3 se ci sono varianti, Sharpe netto con costi raddoppiati > 0, stabilità dei parametri, test di look-ahead superato. La Validazione (agenti) lavora solo su ciò che passa il cancello. | Fabbrica di alpha alla WorldQuant: il valore è nel filtro automatico. Risparmia token: gli LLM giudicano solo i candidati plausibili. `firms.md` §8 | Sì: le soglie sono in `config/settings` e le cambia Andrea. |
| D4 | **Pod con stop a scalini (−5% dimezza, −7,5% chiude), capitale iniziale 5% del NAV ciascuno, limite di correlazione tra pod.** Il Pod Zero è escluso dagli stop a scalini (ha il suo regime validato). | Meccanismo multi-manager riportato dalla stampa; affollamento e perdite correlate (agosto 2007, regolatori); lo stop peggiora lo Sharpe del libro sistematico (STUDIO §3). `firms.md` §1–2, `risk_and_execution.md` §2, §5 | Sì, valori modificabili da Andrea. |
| D5 | **Gateway di Esecuzione deterministico come unico accesso al broker**, con sub-ledger per pod e compensazione interna; gli agenti non hanno mai le credenziali. | Injection indiretta: chi legge testo esterno non deve avere strumenti con effetti (Greshake et al.). `llm_agents_in_finance.md` §6 | No. |
| D6 | **Riallocazione del capitale con stima bayesiana a shrinkage** verso zero alpha, campione minimo, penalità per drawdown e correlazione; se nessun pod batte il Pod Zero con evidenza, il capitale resta al Pod Zero. | Con pochi trade la classifica è rumore: MinTRL di ~2,7 anni per distinguere Sharpe 1 da 0 (`alpha_research.md` §3). | Sì. |
| D7 | **Pareri indipendenti aggregati da codice, non dibattiti.** Revisore cieco rispetto all'opinione dell'autore, obbligo di un difetto concreto, un solo giro di replica. | Il dibattito non batte il voto a parità di calcolo e può peggiorare (Smit et al.; arXiv 2509.05396); sycophancy da RLHF (Sharma et al.). `llm_agents_in_finance.md` §4–5 | Sì. |
| D8 | **Previsioni con probabilità, scadenza e criterio di risoluzione registrati con hash prima dell'esito; punteggio con Brier e calibrazione; Ω del Black-Litterman dalla calibrazione dell'agente.** | Brier come misura standard (ForecastBench); Black-Litterman combina viste e prior in modo bayesiano. `llm_agents_in_finance.md` §7, `alpha_research.md` §7.4 | Sì. |
| D9 | **Società a eventi con Budget Governor in codice:** battito deterministico ogni 15 minuti, sveglia solo gli agenti necessari; Haiku per triage, Sonnet per giudizio, Opus solo per il Comitato settimanale e la validazione profonda; prompt stabili in testa per la cache. | Prezzi ufficiali e calcolo del budget di 0,60 €/giorno. `llm_agents_in_finance.md` §8 | Sì, routing in `config/models.yaml`. |
| D10 | **Niente modifiche al codice di produzione GERVA-Q fuori dalla domenica; le correzioni dell'audit diventano proposte di rilascio con test.** La ricerca nuova vive in `quantlab/` e confronta ogni idea con il Pod Zero. | REGOLE_SFIDA regola 7; il codice è congelato con hash nel ledger della sfida. `gervaq_audit.md` | Sì: Andrea può cambiare la finestra dalle Impostazioni. |

## Scelte prese in autonomia per conflitti o costi del brief

- **GERVA-Q non è raggiungibile dal cloud.** Il brief indica `~/Documents/GERVA-Q`; l'ambiente di sviluppo è un container cloud senza accesso al Mac. Soluzione: adattatore di sola lettura configurato da `GERVA_Q_PATH`. Lo snapshot caricato da Andrea è in `_incoming/` ed è **escluso da git**: il repository GERVA-Capital è pubblico e pubblicare il codice delle strategie è una scelta di Andrea, non mia.
- **Dati di mercato bloccati dalla rete del cloud.** Il motore è testato su dati sintetici con risultati noti; i backtest reali si lanciano dal Mac.
- **Agenti a flusso, non a ciclo di strumenti aperto.** Il codice raccoglie i numeri, l'agente restituisce un JSON a schema, il codice esegue solo le azioni consentite al ruolo. Costa meno (una chiamata per compito) ed è più robusto contro l'injection (D1, D5, D9). Il registro `llm/tools.py` resta la fonte dei permessi.
- **Le prove di collaudo su dati sintetici** restano nel registro ma non entrano nel contatore del DSR: verificano la pipeline, non una strategia, e falserebbero la varianza degli Sharpe.
- **Organico:** 8 agenti iniziali come da brief, più i 3 Capi Pod richiesti da M5 con budget minimo (0,03 €/giorno ciascuno, sveglia settimanale).
- **Il brief non è pubblicato** (repo pubblico, contiene dettagli personali): è escluso da git e resta solo in locale.
- **IBKR con due ruoli separati (v3).** Il conto della sfida è solo osservato; i pod eseguono su IBKR solo con un secondo conto paper (R12). Senza, restano sul broker simulato. Se IBKR è configurato e non risponde, i pod si fermano invece di ripiegare sul simulato.
- **Server: difesa in profondità invece di fiducia nel codice (v3).** Gli agenti LLM leggono testo dal web, quindi il loro container non raggiunge il gateway della sfida, non vede le chiavi del portale e non può scrivere i limiti di rischio. Il portale è raggiungibile solo dal tunnel SSH, con password.
- **La patch di rilascio per GERVA-Q esce da git (v3).** Conteneva righe del codice privato di GERVA-Q; il branch non era mai stato pubblicato, quindi l'ho tolta anche dalla storia locale. Resta su disco.
- **`/cost` non è disponibile per me in questa sessione.** STATUS.md lo dichiara e non riporta stime inventate; Andrea legge il valore vero con `/cost` dal suo terminale.

## Decisioni di Andrea del 5/11/2026 (grandi richieste n.6 e n.5)
- **Cambio di direzione (n.6): non è più una sfida.** L'obiettivo della società diventa la **crescita massima del
  capitale** nel lungo periodo, non lo Sharpe di un confronto a tre mesi. Il capitale passerà poi a essere vero, dei
  genitori di Andrea.
- **Cosa resta uguale, perché protegge proprio quei soldi:**
  - solo paper finché non sono superati i cancelli (backtest al netto dei costi, DSR, almeno 2 mesi di paper senza
    errori) e c'è la firma dei titolari del conto in `approvals/`;
  - i limiti di rischio, la leva compresa, li decide solo Andrea;
  - si parte con il 20-25% del capitale previsto.
- **Crescita massima, in pratica:** si massimizza la crescita composta (il logaritmo della ricchezza, criterio di
  Kelly), non il rendimento atteso. Oltre il punto di Kelly più rischio fa crescere MENO e avvicina la rovina. Con
  stime incerte si sta sotto quel punto (frazione di Kelly). Senza leva, il punto più alto raggiungibile è usare tutto
  il capitale fermo: la scala del rischio del banco v4 lo misura.
- **Il capitale lo legge IBKR:** il capitale iniziale è la prima lettura riuscita del conto, scritta una volta. Il
  valore di ogni giorno arriva da IBKR. Un balzo di oltre il 20% in un giorno (versamento, prelievo, reset del paper)
  fa scattare un allarme invece di essere contato come profitto.
- **Approvato il piano v4 (n.5, condizionato):** portafoglio ombra dal 5/11 → dopo 40 giorni di borsa, se la regola
  scritta è soddisfatta, patch di GERVA-Q applicata di domenica con backup. L'applicazione resta un comando di Andrea
  (`firm.py release --apply`): il codice non la esegue da solo.

## Organico del 5/11/2026 (richiesta di Andrea: "piu' e' specifica l'azienda e i professionisti, piu' e' reale")
- **Desk crypto** sotto la Ricerca: Valentina Esposito (Senior Quant Researcher, Digital Assets; posizione prima
  vacante) e Tommaso Galli (Analista Senior, mercati crypto). Le prove del banco crypto sono registrate a nome suo.
- **Lungo periodo**, reparto nuovo con tetto di 0,08 EUR/giorno: Francesca Lombardi (Head of Long-Term Investments,
  presiede il Comitato), Riccardo Bianchi (semiconduttori e infrastruttura AI), Elisa Fontana (energia e data center).
  Il Comitato e' composto da loro e dalla CRO; gli agenti possono solo RINVIARE una rata approvata dal codice.
- Il tetto di spesa globale resta 0,60 EUR/giorno: piu' persone, ciascuna svegliata un po' meno spesso.
- Uffici privati 4: chi viene promosso a Manager quando sono pieni resta "in attesa" nel suo ufficio, visibile nel
  portale, finche' uno non si libera.
