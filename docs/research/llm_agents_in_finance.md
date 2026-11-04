# Agenti LLM in finanza: cosa funziona, cosa no

Etichette: [A] primaria, [M] secondaria seria, [B] debole.

## 1. Il dato più importante: nei test lunghi il vantaggio sparisce

- **FINSABER** (backtest su due decenni e oltre 100 titoli, con liste storiche dell'S&P 500 e titoli delistati): i vantaggi riportati in precedenza per le strategie LLM **si deteriorano in modo significativo** su sezioni più ampie e periodi più lunghi; le strategie LLM sono troppo prudenti nei bull market e troppo aggressive nei bear market. [A] ([arXiv 2505.07078](https://arxiv.org/abs/2505.07078))
- **StockBench** (multi-mese, "senza contaminazione"): la maggior parte dei modelli testati non batte il comprare e tenere. [M, protocollo non verificato da me] ([arXiv 2510.02209](https://fugumt.com/fugumt/paper_check/2510.02209v1_enmode))
- **LiveTradeBench** (50 giorni in tempo reale, 21 LLM, azioni USA e Polymarket): un punteggio alto nelle classifiche generali dei modelli **non predice** risultati di trading migliori. Limite dichiarato: niente costi, slippage, liquidità. [A] ([arXiv 2511.03628](https://arxiv.org/html/2511.03628v1))
- **TradingAgents** (analisti, ricercatori rialzisti e ribassisti in dibattito, trader, team di rischio): riporta risultati migliori dei riferimenti, ma la finestra di test può sovrapporsi ai dati di addestramento (critica non revisionata). [A per il paper, B per la critica] ([arXiv 2412.20138](https://arxiv.org/abs/2412.20138v1))

**Conclusione operativa:** gli agenti LLM non sono il motore di alpha di GERVA Capital. Sono l'**organizzazione** attorno al motore: leggono, verificano, propongono ipotesi, scrivono post-mortem, giudicano la qualità del lavoro. L'alpha viene da codice deterministico validato. È anche la scelta più economica (`DECISIONS.md` D1).

## 2. Bias di look-ahead

- Due effetti separati: **look-ahead** (l'LLM conosce i rendimenti successivi alla notizia) e **distrazione** (la conoscenza generale sull'azienda peggiora il giudizio sul sentiment). Nei dati in-sample anonimizzare il nome dell'azienda *migliora* i rendimenti; fuori campione la differenza perde significatività, quindi gran parte dell'effetto in-sample è conoscenza del futuro. [A] ([Glasserman & Lin 2023](https://arxiv.org/abs/2309.17322))
- Rimedio di ricerca: **modelli "point-in-time"** addestrati solo sul testo disponibile a ogni data (ChronoBERT/ChronoGPT; modelli fino a 4 miliardi di parametri con checkpoint annuali 2013–2024). Il bias risulta modesto in quei test, ma è specifico del modello e dell'applicazione. [A] ([He et al. 2025](https://econpapers.repec.org/paper/arxpapers/2502.21206.htm), [Kelly et al., NBER w35247](https://www.nber.org/papers/w35247))
- **Regola per noi (inviolabile 10):** nessun segnale LLM si valida su storico. Ogni previsione LLM viene scritta nel registro *con timestamp e hash prima dell'esito*; vale solo la valutazione in avanti.

## 3. Allucinazioni sui numeri

- FinanceBench: GPT-4-Turbo con un sistema di retrieval condiviso **sbaglia o rifiuta l'81%** delle domande su documenti societari (di cui circa 13% risposte sbagliate e 68% rifiuti, secondo una sintesi secondaria); con contesto lungo e il documento giusto sale a circa 79% di risposte corrette. [A per l'81%, M per la ripartizione] ([arXiv 2311.11944](https://arxiv.org/abs/2311.11944v1))
- **Regola per noi:** un agente non produce numeri. I numeri vengono dagli strumenti (codice) e l'agente li *copia*; lo schema JSON di output ha campi `fonte` obbligatori; lo Scorekeeper confronta ogni numero citato con il valore dello strumento e penalizza le differenze.

## 4. Sycophancy

- La sycophancy è un comportamento generale dei modelli addestrati con RLHF, guidato in parte dai giudizi umani che premiano le risposte che danno ragione all'utente; le risposte persuasive e compiacenti a volte battono quelle corrette anche per i modelli di preferenza. [A] ([Sharma et al., Anthropic, arXiv 2310.13548](https://arxiv.org/abs/2310.13548v1))
- **Tra agenti** il problema si moltiplica: un revisore che vede l'opinione dell'autore tende ad allinearsi.
- **Regole per noi:** (1) il revisore non riceve l'opinione dell'autore, solo il fascicolo; (2) obbligo di indicare almeno un difetto concreto oppure motivare perché non ce ne sono; (3) il disaccordo motivato e poi confermato dagli esiti alza il punteggio del revisore; (4) il Capo non può modificare il verdetto della Validazione.

## 5. Dibattito multi-agente e collasso delle opinioni

- A parità di calcolo, il dibattito multi-agente **non batte in modo affidabile** l'auto-consistenza (voto di maggioranza su più campioni). [A] ([Smit et al., ICML 2024](https://proceedings.mlr.press/v235/smit24a.html); [Huang et al. 2023, "LLMs cannot self-correct reasoning yet"](https://arxiv.org/pdf/2310.01798); [Zhang et al. 2025](https://arxiv.org/html/2502.08788v2))
- Il dibattito può **peggiorare** con i round e un agente più debole può trascinare giù uno più forte. [A] ([arXiv 2509.05396](https://arxiv.org/html/2509.05396v2))
- **Implicazione:** niente "riunioni" lunghe tra agenti. Per le decisioni importanti: due o tre pareri **indipendenti** (prompt diversi, se possibile modelli diversi), aggregati da **codice** (voto, o media pesata per la calibrazione storica). Un solo giro di replica scritta, poi decide il codice o il Comitato con regola esplicita.

## 6. Prompt injection

- Con l'injection indiretta un attaccante non scrive al modello: pianta istruzioni nei dati che l'applicazione recupererà (pagine web, email, documenti). Le conseguenze dimostrate vanno dal furto di dati all'esecuzione di codice per conto dell'utente e alle chiamate API non autorizzate. [A] ([Greshake et al., AISec 2023, arXiv 2302.12173](https://arxiv.org/abs/2302.12173v2))
- **Caso reale in questa stessa ricerca:** il 4/11/2026, durante le ricerche su HRP e purged CV, una delle pagine restituite (cavac.at) conteneva un'istruzione nascosta per cambiare argomento. Il sistema l'ha ignorata. È la prova pratica che il testo web va trattato come ostile per default. [A, osservato]
- **Regole per noi (inviolabile 7):** separazione dei privilegi. Gli agenti che leggono il web (Redazione) non hanno *nessuno* strumento con effetti: niente ordini, niente scrittura di configurazione, niente messaggi all'esterno. Il loro output è JSON validato da schema; un campo di testo libero non può diventare un comando. Il testo esterno arriva dentro `<dati_non_fidati>`.

## 7. Calibrazione delle previsioni

- ForecastBench: superforecaster Brier 0,093, pubblico 0,107, miglior LLM 0,111 nella prima versione; nell'aggiornamento il miglior modello (0,101) resta dietro ai superforecaster (0,081), con un miglioramento stimato di circa 0,016 punti di Brier all'anno. [A per i numeri del benchmark] ([arXiv 2409.19839](https://arxiv.org/pdf/2409.19839), [FRI](https://forecastingresearch.substack.com/p/ai-llm-forecasting-model-forecastbench-benchmark))
- Un lavoro di dicembre 2025 trova che più ragionamento può **peggiorare** la calibrazione. [M] ([arXiv 2512.16030](https://arxiv.org/html/2512.16030))
- **Per noi:** il Brier score per ogni agente è calcolato da codice su previsioni registrate prima. Riferimento utile: un agente che dice sempre 0,5 su eventi binari bilanciati ha Brier 0,25. Chi non batte quel valore non sta aggiungendo informazione.

Brier e sua scomposizione (Murphy 1973):

$$ BS = \frac1N\sum_{i}(p_i - o_i)^2 = \underbrace{\frac1N\sum_k n_k(\bar p_k - \bar o_k)^2}_{\text{affidabilità}} - \underbrace{\frac1N\sum_k n_k(\bar o_k - \bar o)^2}_{\text{risoluzione}} + \underbrace{\bar o(1-\bar o)}_{\text{incertezza}} $$

La scomposizione è esatta quando le previsioni assumono solo i valori dei bin; in `firm/scorekeeper.py` è implementata con bin di 0,1 e il test verifica la somma.

## 8. Costo

Prezzi ufficiali in vigore (riferimento cache della documentazione Anthropic, 6/10/2026): Opus 5.5 4 $/20 $ per milione di token in ingresso/uscita; Sonnet 5.5 2 $/10 $; Haiku 5.5 0,10 $/0,50 $ (fino a 100K token di prompt). La lettura dalla cache costa circa il 10% dell'ingresso (0,20 $ su Opus 5.5 e Sonnet 5.5). [A, documentazione del fornitore]

Bilancio con 0,60 €/giorno (≈0,65 $): circa **3,2 milioni di token Haiku in ingresso e 650.000 in uscita** al giorno (0,32 $ + 0,33 $), oppure circa **30.000 token Opus in uscita**. Il Capo su Opus una volta a settimana (Comitato) con 20.000 token in ingresso e 4.000 in uscita costa ≈0,16 $. Le scelte di `config/models.yaml` derivano da questo calcolo.

## 9. Pattern che adottiamo e pattern che scartiamo

| Pattern | Evidenza | Decisione |
|---|---|---|
| Planner/executor (il Capo scompone, i manager eseguono) | Utile per costo e tracciabilità; nessuna evidenza di alpha | Adottato per la delega |
| Red team / validazione indipendente | Coerente con la letteratura sull'overfitting; riduce i falsi positivi | Adottato, con canarini |
| Dibattito lungo tra agenti | Non batte il voto a parità di calcolo | Scartato; un solo giro di replica |
| Auto-valutazione | Inflazione dei voti, sycophancy | Vietata; punteggi da codice |
| LLM come generatore di segnali in backtest | Look-ahead | Vietato; solo in avanti |
| Pareri indipendenti multi-modello | Diversità riduce il collasso di opinioni | Adottato per decisioni rare |
