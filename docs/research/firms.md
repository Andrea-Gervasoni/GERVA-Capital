# Come sono organizzate le società di trading — e cosa copiamo

Fase 0, ricerca del 4/11/2026. Ogni affermazione porta un'etichetta:

- **[A]** confidenza alta: fonte primaria (documento della società, paper firmato dai suoi dipendenti, sentenza o documento regolatorio).
- **[M]** confidenza media: grande testata (Bloomberg, WSJ, FT, Reuters) o libro basato su interviste, ma senza conferma della società.
- **[B]** confidenza bassa: blog, guide ai colloqui, forum, aggregatori. Riportata solo se coerente con fonti migliori; mai usata come base di una decisione.

Regola di lettura: queste società sono private e reticenti. Quasi tutto ciò che si sa sul loro funzionamento interno è **ricostruzione giornalistica**. Copiamo i *meccanismi* che hanno una logica economica verificabile da noi, non i numeri raccontati.

---

## 1. Millennium Management — il modello a pod "puro"

**Reparti.** Centinaia di team indipendenti (pod), ciascuno con un portfolio manager (PM), analisti e un trader; funzioni centrali di rischio, esecuzione, tecnologia e allocazione del capitale. [M] Il rischio centrale può ridurre l'esposizione di un pod in qualsiasi momento. [B] ([profilo terzo](https://freenance.io/funds/millennium-management/), [Fool](https://www.fool.com/investing/how-to-invest/famous-investors/millennium-management))

**Flusso di un'idea.** L'idea nasce e muore *dentro il pod*: il PM decide le posizioni entro un budget di rischio (volatilità, VaR, drawdown) assegnato dal centro. Il centro non valuta le singole idee: valuta il P&L del pod e il rispetto dei limiti. [B]

**Regola dei drawdown.** La regola più citata: un pod che perde circa il **5%** del capitale assegnato vede il capitale **dimezzato**; intorno al **7,5%** di perdita il PM viene di norma licenziato, con eccezioni. [M] La base di misura (dal capitale iniziale o dal massimo) varia tra le fonti: alcune ricostruzioni WSJ parlano di 5% + ulteriore 2,5% come secondo scalino. [M] ([eFinancialCareers su WSJ](https://www.efinancialcareers.com/news/pratik-madhvani-glen-scheinberg), [The Wealth Advisor](https://www.thewealthadvisor.com/article/millennium-management-has-built-its-success-one-straightforward-approach?page=436), [WSO, forum](https://www.wallstreetoasis.com/forum/hedge-fund/multi-manager-risk-limits) [B])

**Valutazione e promozione.** Payout come quota del P&L del pod (la stampa cita 20–30% dei profitti per i PM migliori). [M] ([Hedgeweek](https://www.hedgeweek.com/top-hedge-fund-traders-take-home-nearly-25-of-profits/)) Chi viene fermato perde il payout accumulato; il capitale va ad altri team. [B]

**Rischio.** Centralizzato, indipendente dai PM, con monitoraggio di fattori ed esposizioni; i pod tipicamente devono neutralizzare il mercato e i fattori (questo punto *non* l'ho trovato confermato da fonti primarie: [B]).

## 2. Citadel — pod settoriali più rischio centrale in tempo reale

**Reparti.** Pod di 4–8 persone guidati da un PM con mandato settoriale; team centrale di rischio che riporta al vertice e vede tutte le posizioni in tempo reale. [B] ([Thairath](https://en.thairath.co.th/money/business_marketing/business_strategy/2949800), [Substack](https://youngandcalculated.substack.com/p/risk-management-inside-a-pod-how))

**Rischio.** Al primo scalino di drawdown il pod deve tagliare l'esposizione lorda *meccanicamente*, a prescindere dall'opinione del PM. [B] Non ho trovato fonti primarie sui valori.

**Fragilità documentata.** I regolatori segnalano che le multi-manager sono "molto più rapide a tagliare e scappare" (approccio a grilletto facile) e che i pod tendono ad affollarsi sugli stessi trade, quindi la diversificazione apparente può diventare perdita correlata. [M] ([Bloomberg Law](https://news.bloomberglaw.com/securities-law/citadel-and-peers-face-more-scrutiny-as-risks-grow-for-pod-shops), [Advisor Perspectives](https://www.advisorperspectives.com/articles/2023/11/30/citadel-and-peers-are-piling-into-same-trades-regulators-taking-notice))

**Lezione per noi:** il limite di correlazione tra pod non è un dettaglio, è la difesa contro il fallimento tipico del modello. Agosto 2007 lo dimostra (vedi `risk_and_execution.md` §5).

## 3. Economia del modello multi-manager

- I costi (soprattutto il personale) vengono "passati" agli investitori: nel campione Cambridge Associates i *pass-through* vanno dallo 0,87% al 12,99% annuo, media 5,93%. [A, dato di un consulente su campione proprio] ([Cambridge Associates 2024](https://publishedresearch.cambridgeassociates.com/2024-hedge-fund-discretionary-expense-summary/))
- Conseguenza per noi: il modello funziona solo se **ogni pod paga il suo costo** (tassa sul capitale + costo di calcolo). È quello che il brief chiama "alpha netto". Una società di agenti dove gli agenti non pagano i token è un modello a pod senza conto economico.

## 4. Jane Street — cultura collaborativa e probabilistica

**Reparti.** Niente titoli gerarchici classici: si è trader, ricercatore o ingegnere. [B] Le linee tra ricerca, tecnologia e trading sono "volutamente sfumate". [A, annuncio di lavoro ufficiale] ([Yale OCS, annuncio Jane Street](https://ocs.yale.edu/jobs/jane-street-capital-llc-quantitative-trader-4/)) Attività principale: market making e fornitura di liquidità, anche su ETF. [B]

**Cultura dichiarata dalla società** ([Jane Street, Who we are](https://www.janestreet.com/who-we-are/)) [A]:
- nessuno viene chiesto di difendere un'opinione che non condivide;
- post-mortem anche per guasti minori, con l'obiettivo di migliorare il processo, non di trovare il colpevole;
- attenzione ai casi limite e ai rischi di coda che altri trascurano.

**Valutazione.** La retribuzione sarebbe legata ai profitti della società più che al P&L individuale, per favorire la collaborazione. [B] Fonti diverse lo contraddicono parzialmente (bonus discrezionale, opacità). [B]

**Lezione per noi:** le due regole verificate (niente posizioni difese per obbligo, post-mortem senza colpa) entrano direttamente nei prompt. Il compenso collettivo invece *non* lo copiamo alla lettera: il brief vuole competizione tra pod. Lo combiniamo così: competizione tra pod, ma *dentro* il pod il bonus si ripartisce per contributo misurato dallo Scorekeeper, non per decisione del Capo Pod.

## 5. Two Sigma — metodo scientifico industrializzato

- La società descrive il proprio processo per fasi: dati → modelli → costruzione del portafoglio → esecuzione, con team specializzati di modellisti e ingegneri che cooperano. [A] ([Two Sigma, Investment Management](https://www.twosigma.com/businesses/investment-management))
- Flusso tipico raccontato da una ricercatrice: idea (da paper, notizie, conferenze), codifica e test, poi la messa in produzione se i risultati reggono; l'analisi dei risultati genera nuove idee. [B, intervista] ([NYC Fintech Women](https://nycfintechwomen.com/post/fintech-female-fridays-barbara-zhan-vice-president-quantitative-research-two-sigma))
- Gli ingegneri trasformano i prototipi in sistemi di produzione, con pipeline automatiche di addestramento e valutazione. [B, annunci di lavoro]

**Lezione:** separare chi *prototipa* (Ricerca) da chi *industrializza* (Dati e Infrastruttura), con un formato di consegna standard. Da noi il formato è il fascicolo `research/<id>/`.

## 6. D. E. Shaw — informatica prima della finanza

- Fondata nel 1988 da David E. Shaw, informatico, ex professore alla Columbia, con sei dipendenti e 28 milioni di dollari; pioniera della finanza computazionale. [A per i fatti di fondazione] ([D. E. Shaw, Founder](https://www.deshaw.com/who-we-are/founder), [Wikipedia](https://en.wikipedia.org/wiki/D._E._Shaw_%26_Co.))
- Come convivano oggi i rami sistematici e discrezionali: **non lo so**. Non ho trovato fonti affidabili. Per verificarlo: documenti ADV della SEC e interviste a ex dipendenti.

## 7. Renaissance Technologies — un solo modello, codice condiviso

- Medallion funziona come **un unico sistema** che combina decine di "strategie" su un codice di milioni di righe; tutti i dipendenti avevano accesso a ogni riga, perché i ricercatori si scambiassero idee invece di coltivare progetti privati. [M, da Zuckerman, *The Man Who Solved the Market*, 2019, tramite recensioni] ([recensione](https://ishanjmukherjee.github.io/how-rentec-won), [Bloomberg](https://www.bloombergquint.com/markets/how-renaissance-s-medallion-fund-became-finance-s-blackest-box))
- Circa 150 tra ricercatori e programmatori, metà con dottorato scientifico. [M] ([Wikipedia](https://en.wikipedia.org/wiki/Renaissance_Technologies))

**Lezione:** Renaissance è l'**opposto** del modello a pod. Molti segnali deboli in un unico portafoglio battono molti portafogli in competizione, *se* la ricerca è condivisa. Per noi la conseguenza pratica è il "libro unico" del Pod Zero: i segnali che superano la validazione possono entrare nel Pod Zero come componenti, invece di restare per forza nel pod che li ha trovati. Il bonus resta a chi li ha trovati (attribuzione per idea).

## 8. WorldQuant — la fabbrica di alpha

- Il paper *101 Formulaic Alphas* (Kakushadze, Lauprete, Tulchinsky — questi ultimi due di WorldQuant) pubblica 101 alpha reali; **80 erano in produzione** al momento della pubblicazione. Correlazione media a coppie 15,9%, holding medio 0,6–6,4 giorni; si combinano in una "mega-alpha". [A] ([arXiv:1601.00991](https://www.arxiv.org/abs/1601.00991))
- La piattaforma BRAIN permette a consulenti esterni di inviare alpha, accettate solo se superano soglie automatiche. Le soglie citate (Sharpe > 1,25, fitness > 1, auto-correlazione < 0,7; fitness = Sharpe·√(|rendimento|/max(turnover, 0,125))) vengono da guide di terzi e non sono confermate. [B] ([lancio di BRAIN](https://www.worldquant.com/ideas/worldquant-launches-brain-platform-and-inaugural-global-alphathon-competition) [A per l'esistenza], [guida terza](https://www.quantt.co.uk/resources/worldquant-brain) [B])

**Lezione:** il valore di una fabbrica di alpha sta nel **cancello automatico** (soglie di Sharpe, turnover, correlazione con le alpha esistenti) e nella **combinazione**, non nella singola alpha. È esattamente il rischio che il brief chiama falsi positivi: con migliaia di prove servono soglie che tengano conto del numero di prove (Deflated Sharpe, `alpha_research.md` §4).

---

## 9. Sintesi: il flusso di un'idea nelle varie società

| Fase | Pod shop (Millennium/Citadel) | Jane Street | Two Sigma / D. E. Shaw | Renaissance | WorldQuant |
|---|---|---|---|---|---|
| Origine | PM del pod | Team misto | Ricercatore | Ricercatore | Consulente o ricercatore |
| Validazione | Del PM; il centro guarda solo P&L e limiti | Revisione tra pari | Processo di modellazione rigoroso | Collettiva, codice condiviso | Soglie automatiche |
| Capitale | Budget di rischio del pod | Libro di società | Portafoglio centrale | Modello unico | Combinazione centrale |
| Uscita | Stop a scalini sul drawdown | Giudizio | Decadimento misurato | Rimozione dal modello | Decadimento e correlazione |

## 10. Cosa copiamo (meccanismi, non miti)

1. **Pod in competizione con budget di rischio e stop a scalini** (Millennium/Citadel): taglio del capitale al −5% del pod, chiusura al −7,5%. Valori di partenza, modificabili da Andrea; le fonti sono [M]/[B], ma la logica è verificabile: limita la perdita massima per pod a un valore noto prima.
2. **Rischio centrale indipendente che vede tutto, e pod che non vedono gli altri** (pod shop): impedisce che un pod copi le posizioni di un altro e permette di misurare l'affollamento.
3. **Limite di correlazione tra pod** (lezione dei regolatori e di agosto 2007).
4. **Post-mortem senza colpa e niente opinioni difese per obbligo** (Jane Street, fonte primaria).
5. **Cancello automatico e combinazione dei segnali deboli** (WorldQuant, Renaissance), con il numero di prove incluso nella soglia.
6. **Separazione prototipo / produzione** (Two Sigma), con un formato di consegna unico.
7. **Ogni pod paga i suoi costi** (economia delle multi-manager).

## 11. Cosa NON copiamo, e perché

- **La competizione spietata come fine.** Con pochi trade la classifica è rumore. Da noi la riallocazione usa shrinkage bayesiano e un campione minimo (`DECISIONS.md` D6).
- **La velocità di taglio alla Citadel senza un modello di costi.** Su un conto retail, ogni taglio e ogni rientro costano commissioni (0,18% per lato sulle crypto IBKR). Lo studio GERVA-Q mostra già che lo stop sul drawdown *peggiora* lo Sharpe del libro azionario (STUDIO.md §3). Per questo gli stop a scalini valgono per i pod sperimentali (capitale piccolo, rischio di modello alto) e non per il Pod Zero, che ha il suo governatore già validato.
- **I numeri raccontati sui payout.** Non verificabili e irrilevanti per agenti.
