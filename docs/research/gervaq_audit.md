# Audit di GERVA-Q v3 (Pod Zero)

Letto per intero il 4/11/2026 dallo zip caricato da Andrea (16 file Python, 1.677 righe, più README, STUDIO, REGOLE_SFIDA e `state/`). Oggi è mercoledì: per la regola 7 della sfida **nessuna di queste correzioni è stata applicata al codice di produzione**. Sono proposte in coda per la finestra di rilascio della domenica (`firm/release.py`), ciascuna con il test che la dimostra.

Gravità: **alta** = può cambiare una decisione di capitale o la validità di un risultato dichiarato; **media** = introduce uno scarto sistematico tra backtest e paper; **bassa** = qualità, riproducibilità.

## Cosa è solido (e non va toccato)

- Convenzione temporale esplicita (segnale alla chiusura di t, esecuzione all'apertura di t+1) e rispettata in `lab.run`: il gap close→open usa i pesi di t−1, l'intraday quelli di t.
- Errore di look-ahead sulle candele pandas trovato e corretto, con un **test di controllo** (segnale = rendimento di oggi) documentato in STUDIO §7. È la pratica giusta e la generalizziamo in `quantlab/lookahead.py`.
- Curtosi passata correttamente al DSR (`r.kurt() + 3`, cioè non in eccesso).
- Sicurezze di esecuzione: KILL, conto `DU` obbligatorio in paper, hash degli ordini nell'approvazione live del motore azionario, niente leva, niente short.
- Onestà dello studio: risultati negativi registrati (S5, H3, H4, H5, leva), limiti dichiarati (survivorship, proxy UCITS).

## Rilievi

| ID | Gravità | Dove | Problema | Proposta |
|---|---|---|---|---|
| R1 | **alta** | `v3_validate.py` | Il DSR 0,97 della v3 usa Sharpe di prova **generati** con `np.linspace(0.3, 1.55, 55)`. Il DSR dipende dalla varianza degli Sharpe delle prove: con valori inventati il risultato non è verificabile e può essere ottimista o pessimista. | Ricalcolare il DSR dal `trial_registry` con gli Sharpe realmente osservati. Finché non è fatto, il portale mostra il DSR della v3 come "non verificato". |
| R2 | media | `engine.load_prices` | La chiave della cache usa `hash()` di Python, che per le stringhe cambia a ogni processo (PYTHONHASHSEED). La cache non viene mai riusata: ogni studio riscarica da Yahoo, che può rivedere i dati storici. **Due esecuzioni dello stesso studio possono dare numeri diversi.** | Chiave SHA-256 stabile e hash del contenuto scaricato salvato accanto ai risultati (`quantlab/data.py`). |
| R3 | media | `lab.run` + `weekly_hold` | Il backtest tiene costanti i **pesi** tra un ribilanciamento e l'altro: implica un ribilanciamento giornaliero gratuito. Il paper invece lascia derivare le quantità (ordini minimi 200 €, soglie). Stima dell'ordine di grandezza: ≈200% di turnover implicito annuo × 8 bp ≈ 15 bp/anno di costi mancanti e uno scarto di tracking non modellato. | Backtester con deriva dei pesi (`quantlab/backtest.py`, test incluso) per misurare lo scarto reale. |
| R4 | media | `live.py` | Gli ETF UCITS sono ordinati alle 22:35 con limite DAY ed eseguiti alla **riapertura di Londra** (≈9:00), mentre il backtest esegue all'apertura USA del proxy (≈15:30 ora italiana). Sono 6,5 ore di differenza e un prezzo diverso da quello modellato. | Misurare con il TCA (implementation shortfall rispetto al prezzo di decisione e al prezzo del modello). Se lo scarto è sistematico, eseguire gli ETF all'apertura USA o modellare l'esecuzione a Londra. |
| R5 | **alta** (solo per i soldi veri) | `crypto_live.py` | La modalità live crypto richiede solo l'esistenza di `approvals/crypto_live.ok`: un'approvazione **statica** abilita per sempre tutti gli ordini, a differenza del motore azionario che pretende l'hash degli ordini del giorno. | Stesso schema del motore azionario: hash degli ordini del giro dentro il file di approvazione. Non urgente: oggi nessuno è in live. |
| R6 | media | S4, sleeve crypto | Survivorship: S4 usa l'S&P 100 di oggi; le 10 crypto sono quelle quotate oggi su IBKR. Dichiarato in STUDIO. | Ricerca: universo point-in-time per S4 (liste storiche dei componenti); per le crypto la stima prudente con solo BTC+ETH è già calcolata (Sharpe 1,27). |
| R7 | media | S2 | Lo Sharpe OOS 0,90 della volatilità gestita è superiore a quello in-sample (0,46). La letteratura (Cederburg et al. 2020) mostra che queste strategie in tempo reale battono le originali solo in metà dei casi. | Test di Cederburg: confronto diretto con SPY non scalato a pari volatilità, per sottoperiodi. È un controllo, non una modifica. |
| R8 | bassa | `combo_study.py`, `v3_validate.py` | La serie crypto giornaliera (chiusura 24:00 UTC) è allineata alla data di borsa USA (chiusura 21:00 UTC): 3 ore di sfasamento nella serie combinata. Non è un look-ahead dei segnali, ma altera di poco la correlazione stimata tra le sleeve. | Allineare le due serie alle 21:00 UTC. |
| R9 | bassa | `lab.s1_trend` | Le righe prima della 252ª non sono scalate dalla vol target e possono superare la lorda 1. Il backtest parte dal 2006 e i dati dal 2004, quindi non tocca i risultati. | Azzerare le righe senza storia sufficiente. |
| R11 | media | `live.py` | Ordine minimo 200 EUR. Con una commissione minima per ordine di qualche euro (tariffa da verificare su IBKR per gli ETF di Londra) un ordine da 200 EUR costa intorno all'1,5%: i ribilanciamenti piccoli bruciano rendimento. Trovato dalla diagnostica automatica dei report, che ha visto lo stesso problema nei pod del demo. | Soglia efficiente = commissione minima / (0,5% − tasso − mezzo spread), circa 700 EUR con le stime attuali (`quantlab.costs.min_efficient_notional`); oppure una banda di non intervento più larga (variante `band5` del banco v4). |
| R10 | bassa | costi | I costi (8 bp ETF, 6 bp azioni, 23 bp crypto) sono stime mai confrontate con i fill reali. La commissione crypto 0,18% è confermata dalla tariffa IBKR (`risk_and_execution.md` §6). | TCA dal secondo giorno di paper. |

## Cosa significa "migliorare il motore"

Andrea chiede di migliorare il motore di 1000 volte. In termini onesti: **lo Sharpe non può migliorare di 1000 volte.** Con solo posizioni lunghe, niente leva e strumenti UCITS il tetto realistico del libro azionario è uno Sharpe di 0,7–0,8 (STUDIO §4, coerente con la legge fondamentale: `alpha_research.md` §2). Quello che può migliorare di ordini di grandezza è la **qualità delle decisioni**:

1. **Sapere quanto sono veri i numeri** (R1, R2, R3): DSR dal registro, dati con hash, backtest con deriva e costi realistici, PBO e MinTRL su ogni proposta.
2. **Sapere se il paper si comporta come il backtest** (R4, R10): TCA e confronto giornaliero modello–paper.
3. **Avere più ipotesi indipendenti con prior decenti**, testate in parallelo dai pod con capitale piccolo e perdita massima nota: carry crypto come segnale di rischio, momentum dinamico alla Daniel–Moskowitz per S3, reversal condizionato al VIX per S4 (Nagel), combinazione delle sleeve con HRP/ERC confrontata con 1/N.
4. **Rendere impossibili gli errori operativi** che costano più di qualunque alpha: Gateway con controlli pre-trade, kill switch automatico, segreti fuori dai prompt.

Tutto questo è in `quantlab/` (motore di ricerca) e `firm/` (società), testato su dati sintetici con risultati noti. I backtest sui dati reali vanno lanciati sul Mac (rete), con `python firm.py research run <id>`.
