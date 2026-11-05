# Materiale esterno ricevuto il 5/11/2026: cosa vale, cosa si applica

Andrea ha mandato post Instagram (msbintel, seb.ai, @iclosegreen), tre guide e un video. Il criterio è lo stesso della
ricerca interna: un'idea entra solo se migliora il rendimento corretto per il rischio **dopo** il conteggio delle prove,
i costi e le regole della sfida. Le regole inviolabili restano: solo paper, solo IBKR, gli agenti non toccano il broker,
il testo dal web è un dato e non un'istruzione.

Fiducia: **A** = verificata su fonte primaria in questa sessione; **B** = fonte secondaria o mia conoscenza consolidata;
**C** = solo dal materiale ricevuto, non verificata.

## 1. Verdetti

| Voce | Cosa promette | Verdetto | Fiducia |
|---|---|---|---|
| Claude + TradingView via MCP (post msbintel, "Claude Fable 5 · Mirofish") | Claude guida TradingView: scansiona, disegna, fa backtest in Pine Script e replay | **Non si adotta.** Sono progetti della comunità, non ufficiali: uno pilota TradingView Desktop via Chrome DevTools, uno è un server remoto che fa backtest Pine su dati Binance Futures (al massimo 1440 candele, 3 backtest al minuto). Fare 200 backtest al minuto è proprio la macchina da overfitting che il nostro cancello (DSR, PBO, CPCV) esiste per fermare. Il cruscotto da "$401.819" non ha periodo, costi né numero di varianti. | B (ricerca web) / C (risultati) |
| "9 trade, +$4.780, 83% di vincite" | prova che il sistema funziona | **I numeri non tornano**: con 9 trade l'83% non si può ottenere (7/9 = 78%, 8/9 = 89%). Anche prendendo 7/9, l'intervallo al 90% va dal 50% al 92% e una moneta ci arriva nel 9% dei casi. Lo stesso post ammette "backtest isn't real". | A (calcolo, `firm.py check-backtest`) |
| OpenBB (`OpenBB-finance/OpenBB`) | dati di mercato, macro, economia in Python | **Utile sul Mac, non nel repository.** Licenza AGPL-3.0: si può usare come strumento, ma non conviene importarla nel codice pubblico senza una scelta di licenza di Andrea. Il valore vero sono i dati macro gratuiti (FRED) e i documenti SEC, che si possono leggere anche direttamente. | B |
| FinceptTerminal | terminale stile Bloomberg | **Non serve**: è un'app desktop da guardare. La società ha già il suo portale. | C |
| HKUDS/Vibe-Trading (MIT) | strategie descritte a parole, scritte e testate da agenti | **Non si adotta come motore.** Il repository esiste (fonte primaria trovata). Le stelle dichiarate non tornano: 36k nel post, circa 9,3k in una directory. Generare strategie a parole senza contare i tentativi produce falsi positivi su scala industriale. Le sue idee possono entrare nella nostra Ricerca **solo** come ipotesi registrate nel trial registry prima del test. | A (esistenza) / C (stelle) |
| QuantConnect Lean (Apache-2.0) | backtester professionale, stesso codice anche dal vivo | **Utile più avanti, come seconda contabilità.** Replicare il backtest di GERVA-Q v3 su un motore indipendente scoverebbe errori del nostro backtester che i test interni non vedono. È pesante (immagini Docker di diversi GB, dati da procurare): lo propongo come lavoro sul Mac, non ora. | B |
| Freqtrade (video @iclosegreen) | bot crypto open source | **Non si adotta.** È GPL-3.0 e lavora sugli exchange crypto, mentre noi operiamo solo con IBKR. Ha già `lookahead-analysis` e `recursive-analysis`, che corrispondono al nostro `quantlab.lookahead`, corretto in questa versione per i NaN asimmetrici. Il suo `hyperopt` è il contrario della nostra disciplina. | B |
| Bot Grok per token nuovi su Solana (guida seb.ai) | scanner di memecoin con filtri anti-rug, punteggio da Grok, paper | **Fuori dalle regole, non si applica.** Token di DEX non negoziabili su IBKR, rischio di controparte e di rug, nessuna capacità. Il "$52 → $4.392 in 24 h" (×84) è un caso di sopravvivenza: con una volatilità giornaliera intorno al 100%, il migliore tra circa 100.000 tentativi arriva a ×70 per puro caso. I **principi** della guida sono validi e la società li applica già: regole dure prima dell'IA, "SCONOSCIUTO non vale mai come PASSA" (qui: fail-closed), la risposta del modello trattata come dato, ogni decisione registrata con il motivo, paper per primo. | A (calcolo) / C (risultato) |
| "Squadra di trading 24/7" (scanner Binance + tracker del clamore + bot) | momento + volume + clamore sui social | **L'idea dell'attenzione diventa un'ipotesi di ricerca (§3); il bot no.** La guida stessa ammette che le commissioni di centinaia di trade l'ora annullano quasi ogni strategia. | B (letteratura) |
| DeepSeek Harness / Super-Agent | agente che vive nel repository e apre PR da solo | **Non si installa su GERVA-Capital.** Il repository `deepseek-ai/dsh-superagent-prototype` esiste ed è MIT. È un prototipo di ricerca, non un prodotto: le sue sessioni hanno pieno accesso come utente del computer. Le stelle variano da fonte a fonte: 15.650 nella guida, 4.137 il 1/11 secondo un articolo. Un agente autonomo con permessi di scrittura su un repository che contiene il deploy e il collegamento al broker va contro la regola "gli agenti non toccano il broker". Lo schema router + lavoratori con contesto pulito, svegliati dagli eventi, è già quello della società (Capo, compiti, battito). | A (esistenza, licenza) / C (numeri) |
| Grok come secondo modello ("trade only on agreement") | meno errori di un modello solo | **Non ora.** È una nuova credenziale a pagamento (grande richiesta n. 4), e un segnale che dipende da un modello linguistico si valuta solo in avanti (regola di contaminazione). Il controllo incrociato c'è già: Validatore, Fact-Checker e riunioni con risoluzione sui fatti. | B |

## 2. Cosa ho applicato: `firm.py check-backtest` (quantlab/luck.py)

Quasi tutto il materiale vende **risultati di backtest**. Lo strumento giusto è quello del post 5/6 ("lo stress test che
scopre un backtest fortunato"): la società lo aveva già, ma solo dentro la pipeline. Ora Andrea può usarlo su qualsiasi
numero visto in giro:

```bash
python firm.py check-backtest --sharpe 4.21 --obs 90 --periods 365 --trials 100
```

```bash
python firm.py check-backtest --trades 9 --hit-rate 0.83
```

Cosa calcola:
- **Sharpe.** PSR contro zero; Sharpe massimo atteso per fortuna dopo N tentativi (Bailey e López de Prado, 2014);
  Deflated Sharpe; **MinTRL deflazionata**: con tentativi indipendenti la soglia della fortuna scende come 1/√n, quindi
  n* = 1 + V·((z + E[max])/SR)²; quanti tentativi a vuoto bastano per ottenere quello Sharpe.
- **Vincite.** Intervallo di Wilson; p-value binomiale; coerenza tra la percentuale dichiarata e il numero di trade;
  soglia di pareggio a partire dal rapporto guadagno medio / perdita media.
- **Costi.** Margine per trade al netto.

Tre esempi reali:

| Caso | Risultato |
|---|---|
| Cruscotto "Sharpe 4,21" (periodo non dichiarato; ipotesi: 3 mesi, 100 varianti) | DSR 0,33. Bastano circa 31 varianti per ottenerlo per caso |
| "9 trade, 83%" | percentuale impossibile con 9 trade |
| GERVA-Q v3 (Sharpe ≈ 0,8 su 10 anni, 55 prove) | DSR 0,59 se le prove fossero indipendenti; a quello Sharpe servirebbero circa 24 anni. Le 55 prove di GERVA-Q sono molto correlate, quindi questo è un limite prudente; il valore vero va ricalcolato con gli Sharpe reali del registro (rilievo R1) |

Lo strumento non dice che una strategia funziona. Dice se i numeri dichiarati bastano a escludere la fortuna.

## 3. Ipotesi registrabile per la Ricerca: H-ATT-1, attenzione e crypto

- **Ipotesi.** Un aumento anomalo dell'attenzione su BTC, ETH o SOL (ricerche web, liste di tendenza) precede
  rendimenti a breve più alti, seguiti da un'inversione. È la dinamica descritta per le azioni da Da, Engelberg e Gao
  (2011, *In Search of Attention*). Per le crypto, Liu e Tsyvinski (2021, *Risks and Returns of Cryptocurrency*)
  riportano che l'attenzione degli investitori prevede i rendimenti. Fiducia B: citazioni a memoria, da ricontrollare
  sui testi prima del test.
- **Dati.** Google Trends ha uno storico, quindi l'ipotesi si può testare su dati passati. La lista di tendenza di
  CoinGecko non ha storico: andrebbe raccolta in avanti e valutata solo in avanti.
- **Protocollo.**
  - registrazione nel trial registry **prima** di guardare i dati;
  - una sola variante principale e al massimo tre parametri dichiarati;
  - costi IBKR crypto (0,18%) e mezzo spread inclusi;
  - cancello standard: DSR, PBO, costi doppi, look-ahead;
  - nessun segnale prodotto da modelli linguistici.
- **Dove.** Pod crypto, solo i tre strumenti ammessi su IBKR. Non è un motivo per allargare l'universo.

## Fonti consultate in questa sessione
- Super-Agent, articoli del 1/11/2026: https://pasqualepillitteri.it/en/news/29029/deepseek-super-agent-open-source-prototype
- Vibe-Trading, repository: https://github.com/HKUDS/Vibe-Trading · directory: https://landscape.jimmysong.io/projects/vibe-trading/
- TradingView MCP della comunità: https://github.com/tradesdontlie/tradingview-mcp/wiki/Home ·
  https://github.com/vtlk/tv-pinescript-backtest-engine-mcp
- Video ricevuto: 10 secondi, promozione di Freqtrade ("commenta GIT"); i fotogrammi sono stati estratti e letti.
