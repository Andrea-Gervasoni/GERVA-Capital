# Requisiti del gestore: chi risponde del P&L e decide

Apro il terminale due volte: la mattina (dopo la notte delle crypto) e alle 21:30, prima della chiusura USA delle 22:00 ora italiana, quando la strategia sugli indici esegue. Ogni domanda sotto deve avere risposta in meno di 5 secondi, senza scorrere e senza cambiare pagina.
Segni usati: **[IN ARRIVO]** = dato di un endpoint annunciato (`/compare`, `/tradebook`, `/trades/history`, `/market/ohlc`); **[MANCA]** = dato che il fondo oggi non produce: senza, il riquadro mostra uno stato vuoto esplicito, mai una stima.
Convenzioni: percentuali sul patrimonio totale; "σ di giornata" = `risk.vol_target` / √365 (con obiettivo 15%: circa 0,8%); tutto ciò che viene dal backtest porta l'etichetta SIMULATO.

## 1. Le domande, in ordine di importanza
1. **Stiamo guadagnando?** Oggi, nel mese, nell'anno, dall'avvio.
2. **C'è qualcosa di rotto o frenato?** Dati vecchi, ciclo fermo, rischio non NORMALE, ordini dall'esito ignoto.
3. **Perché?** Quale strategia e quale strumento hanno fatto il P&L di oggi e del mese.
4. **Quanto rischio ho addosso e quanto manca al prossimo scalino?**
5. **Stiamo andando come il backtest prometteva?**
6. **Siamo avanti all'S&P 500, a Bitcoin e al sistema originale?** E si può già dire?
7. **Che cosa è cambiato da ieri?** Posizioni, freni dell'AI, stato del rischio, trade aperti o chiusi.
8. **Che cosa succede alla prossima chiusura?** (domanda delle 21:30) Segnali in arrivo, trade aperti e distanza dallo stop.
9. **Quanto manca al denaro reale?** (settimanale: può stare a un clic)
Le domande 1 e 2 si leggono insieme: se la 2 dice "no", i numeri della 1 vanno attenuati e l'avviso va sopra di loro.

## 2. Per ogni domanda: i numeri, un solo grafico, le soglie
**D1. Numeri:** patrimonio totale in EUR (libro giornaliero + libro dei trade, con le due parti scritte sotto); P&L di oggi in EUR, in % e in σ di giornata; P&L del mese, dell'anno, dall'avvio in %; a fianco del mese il rendimento atteso pro rata (SIMULATO: 2,8% al mese nello scenario base, 1,4% nel centrale).
**Grafico:** linea del patrimonio; x = giorni, y = EUR in scala lineare (logaritmica oltre un anno); intervalli 1S, 1M, 3M, anno, dall'avvio (predefinito: dall'avvio del paper finché ha meno di 90 giorni); sotto, sullo stesso asse x, la caduta dal massimo in %.
**Soglie:** bene = oggi sopra −1σ e mese ≥ atteso centrale pro rata; attenzione = oggi tra −1σ e −2σ, oppure mese tra zero e l'atteso; male = oggi sotto −2σ, o mese negativo oltre una σ mensile (circa 4,3%).
**D2. Numeri:** stato del rischio (NORMAL, REDUCED, HALTED, KILLED) con il motivo; età della fotografia in secondi; età del battito; riavvii ed errori nelle 24 ore; componenti non "ok" (conteggio e nome del peggiore); ordini rifiutati o pendenti oggi; modalità (paper, backtest, DEMO).
**Grafico:** nessuna curva: una riga di stato sempre visibile con una voce per componente (dati crypto, dati azioni, ciclo, rischio, ordini, AI, passi giornalieri, confronto), ognuna con parola, icona e "ultimo ok" in minuti. Un clic apre il registro.
**Soglie:** bene = NORMAL, fotografia sotto 120 s, zero riavvii; attenzione = un componente in avviso, o errori > 0, o overlay AI scaduto; male = REDUCED o peggio, fotografia ferma, ordine dall'esito ignoto, passo giornaliero non eseguito oggi.
**D3. Numeri:** contributo al P&L di oggi e del mese, in EUR e in punti base sul patrimonio, per le quattro strategie più il libro dei trade; i tre strumenti migliori e i tre peggiori di oggi.
**Grafico:** barre orizzontali a cascata "da ieri a oggi": parte dal patrimonio di ieri, una barra per strategia e una per il libro dei trade, arriva al patrimonio di oggi; x = EUR, ordinate per contributo assoluto. Interruttore oggi / mese / dall'avvio.
**Soglie:** bene = nessuna voce pesa più del 60% della perdita o del guadagno; attenzione = una sola voce spiega più del 60% di una giornata negativa; male = una strategia sotto −2σ della propria giornata, o la somma delle voci non torna con il P&L totale (scarto > 1 pb: è un errore, va scritto).
**D4. Numeri:** caduta dal massimo in % e distanza in punti dal prossimo scalino (−20, −30, −40%, letti dalla configurazione); leva lorda su massimo (2x); esposizione netta; VaR ed ES a un giorno al 95% in % e in EUR; volatilità realizzata a 30 giorni su obiettivo; il limite più vicino alla soglia; margine totale impegnato nei trade a leva (la perdita massima di quel libro) in EUR e in %.
**Grafico:** una scala verticale della caduta: y da 0 a −40%, tre tacche agli scalini con l'azione scritta, una tacca alla caduta massima simulata (−21%), il segnaposto di oggi e quello del punto peggiore raggiunto in paper.
**Soglie:** bene = caduta sopra −10% e ogni limite sotto il 70% di utilizzo; attenzione = caduta tra −10 e −20%, o un limite tra 70 e 90%; male = scalino toccato, limite oltre 90%, o caduta oltre −21% (fuori da tutto ciò che il backtest ha visto).
**D5. Numeri:** rendimento cumulato dall'avvio del paper contro mediana simulata alla stessa data, differenza in punti (cancello: entro 3); Sharpe live con il suo errore (± 1/√anni: a 90 giorni è ± 2,0, quindi va scritto piccolo); probabilità che lo Sharpe vero sia positivo (cancello ≥ 60%); per strategia Sharpe live accanto a quello del backtest; R medio dei trade paper contro simulato (0,24 R; cancello: almeno la metà).
**Grafico:** cono dell'atteso: x = giorni dall'avvio del paper, y = patrimonio a base 100; fascia tra 5° e 95° percentile e linea mediana del profilo scelto (SIMULATO), sopra la linea vera del paper.
**Soglie:** bene = dentro la fascia e sopra la mediana; attenzione = dentro la fascia e sotto la mediana per più di 30 giorni; male = sotto il 5° percentile (il backtest non descrive quello che sta succedendo).
**D6.** Vedi sezione 4: numeri, grafico e soglie stanno lì perché questa domanda ha bisogno dell'avvertenza statistica accanto.
**D7. Numeri:** ordini eseguiti nelle 24 ore (conteggio e controvalore); posizioni aperte, chiuse o cambiate di oltre 1 punto di peso; cambi di stato del rischio; moltiplicatori dell'AI nuovi o scaduti con motivo e fonte; regime di ieri e di oggi; livello di conviction di ieri e di oggi per BTC, ETH, SOL; trade aperti o chiusi con R e motivo d'uscita; regole dell'apprendimento che hanno cambiato stato.
**Grafico:** nessuna curva: una lista cronologica "dalle 22:00 di ieri", al massimo otto righe, la più importante in cima (rischio, poi trade, poi AI, poi ordini), ognuna con ora, che cosa, quanto. Stato vuoto: "Nulla è cambiato".
**Soglie:** bene = solo ribilanciamenti; attenzione = un freno dell'AI nuovo o un cambio di regime; male = cambio di stato del rischio, ordine rifiutato, trade chiuso oltre −1 R (lo stop non ha tenuto).
**D8. Numeri:** conto alla rovescia alla chiusura USA; stato della strategia sugli indici (dentro o fuori, ultimo segnale); per ogni trade aperto: lato, entrata, prezzo, stop, liquidazione, leva, margine, risultato corrente in R, massimo a favore e contro in R; conviction e indicatore GQ di oggi con le soglie; motivo scritto se oggi non si apre nulla (`tradebook.log`).
**Grafico:** per ogni trade aperto un righello orizzontale di prezzo: liquidazione, stop, entrata, prezzo corrente, massimo raggiunto; x = prezzo con sopra la stessa scala in R (−1 R allo stop). Più trade, più righelli allineati sull'entrata.
**Soglie:** bene = prezzo oltre l'entrata o stop già trascinato in pari; attenzione = prezzo tra −0,5 R e −1 R; male = prezzo oltre lo stop senza chiusura registrata.
**D9. Numeri:** per ogni cancello valore, soglia, esito; giorni di paper su 90; trade chiusi su 40; quanti cancelli superati sul totale. **Grafico:** barre di avanzamento, una per cancello, con la soglia segnata. **Soglie:** bene = cancello superato; attenzione = in corso; male = cancello violato che azzera il conteggio (arresto, ordine non riconciliato).

## 3. Attribuzione: come voglio il P&L scomposto
- **Per libro:** giornaliero e trade a leva, per giorno, mese, anno, dall'avvio. [IN ARRIVO] le colonne `nuovo_libro` e `nuovo_trade` del confronto lo permettono per ogni giorno.
- **Per strategia:** oggi, mese, dall'avvio esistono. Anno: [MANCA]. Devono essere contributi sul patrimonio totale che sommano al P&L del fondo: oggi lo snapshot non dice se `pnl_*_pct` è sul capitale della strategia o sul totale: va deciso e scritto in etichetta.
- **Per strumento:** oggi e "da quando è aperta" esistono sulle posizioni aperte. Il realizzato delle posizioni chiuse per mese e anno: [MANCA] per il libro giornaliero; per il libro dei trade [IN ARRIVO] con lo storico dei trade.
- **Per sede:** solo sommando le posizioni aperte (oggi e aperto). Storico per sede, commissioni e finanziamento per sede: [MANCA].
- **Costi:** commissioni, slippage e costo della leva come voce propria della cascata: [MANCA] (gli ordini non portano costo né prezzo atteso). È anche un cancello ("costi entro 1,5 volte quelli ipotizzati"): senza questo dato il cancello non si può mostrare.
- **Per tempo:** tabella mesi × anni dei rendimenti (esiste) e, per il mese in corso, barre giornaliere del P&L in EUR.
- **Contro l'atteso:** per ogni strategia tre numeri affiancati: Sharpe live, Sharpe del backtest, Sharpe nel periodo di verifica (0,86 il portafoglio). Il confronto giusto è con la verifica, non con il periodo usato per scegliere.
- **Trade a leva:** R totale, R medio, quota vincenti, profit factor, serie perdente corrente, divisi per livello (confermato, eccezionale), moneta, motivo d'uscita; sempre paper e simulato in colonne separate, mai sommati.
- Regola: ogni scomposizione mostra in fondo la riga "non attribuito" (totale meno somma delle voci). Se non è zero lo voglio vedere.

## 4. Benchmark e sistema originale: che cosa mi convince
**Numeri**, tutti sui soli giorni comuni e al netto di versamenti e prelievi: rendimento cumulato di nuovo fondo, originale, S&P 500, Bitcoin; volatilità annua, Sharpe e caduta massima di ciascuno; differenza di rendimento nuovo − originale in punti; correlazione; beta del nuovo e dell'originale su S&P 500 e su Bitcoin; **z a pari volatilità**; giorni comuni su 90; giorni ancora necessari al ritmo osservato; esito in parole (IN CORSO, NON SMENTITO, BATTE, BATTUTO) con i motivi.
**Il grafico che mi convince** non sono due curve sovrapposte: è il **distacco cumulato a pari volatilità dentro l'imbuto del caso**. x = giorni comuni; y = somma delle differenze giornaliere dei rendimenti divisi per la propria volatilità; attorno allo zero una fascia che si allarga come √giorni, larga ±1,3 errori standard; tacche verticali a 90, 180 e 365 giorni. Finché la linea sta dentro la fascia, nessuno dei due batte l'altro. Sopra: batte. Sotto: si torna all'originale.
Secondo grafico, a un clic: le quattro curve a base 100 dal primo giorno comune, scala logaritmica, con un interruttore "a pari volatilità" che porta il nuovo fondo alla volatilità dell'originale.
**L'avvertenza, scritta accanto al numero e non in nota:**
- Con la correlazione misurata (0,66) servono circa 1.550 giorni comuni per vedere una differenza vera di Sharpe di 1,0 e circa 6.200 per una di 0,5 (potenza 80%, errore 5%). SIMULATO.
- A 90 giorni la differenza minima rilevabile è 4,1 unità di Sharpe; a 180 è 2,9; a un anno 2,1. Novanta giorni dicono solo se il paper si comporta come il backtest.
- "Rende di più con caduta entro 1,5 volte" a 90 giorni esce nel 48% dei casi anche senza alcuna differenza vera: è una moneta. Per questo l'esito a 90 giorni si chiama "non smentito" e non "batte".
- z > 1,3 esce da solo circa una volta su dieci. La soglia è una regola di decisione, non una prova.
- Sul backtest (SIMULATO) il nuovo è avanti a pari volatilità (Sharpe 1,47 contro 0,96) ma con z = 1,3 sull'intero periodo e 0,65 in verifica: nemmeno lì è dimostrato.
**Soglie:** bene = z > +1,3 confermato a 180 e 365 giorni; attenzione = z tra −1,3 e +1,3 (lo stato normale per anni); male = z < −1,3, oppure caduta oltre 1,5 volte quella dell'originale.
**Dati:** le righe giornaliere sono [IN ARRIVO] da `/compare`; z, giorni necessari ed esito oggi li calcola solo `confronto.py`: o l'endpoint li restituisce, o la pagina li ricalcola con la stessa formula e un test la confronta con lo script. Il conto originale è in EUR e il resto in USD: la valuta del confronto va scritta. Nello snapshot live il benchmark è vuoto (`benchmark: null`): S&P 500 e Bitcoin vengono dal confronto. Un benchmark misto (per esempio metà e metà) come serie propria: [MANCA], si calcola dalle due colonne se si decidono i pesi.

## 5. Rumore: nascosto o a un clic
- Tick, variazioni a 5 secondi, cifre che lampeggiano: il patrimonio cambia ogni 15 minuti, lo schermo non deve fingere altro.
- Sharpe, Sortino, Calmar live prima di 90 giorni: a un clic, con l'errore accanto. In prima schermata fanno credere a un numero che non esiste ancora.
- La tabella dei 12 stop e delle 9 varianti di rischio per trade, i sette portafogli A…C6, le 36 strategie candidate, i Monte Carlo: decisioni già prese. Stanno in Ricerca, non nel menu principale.
- L'elenco completo di ordini e avvisi: in prima schermata solo ciò che chiede attenzione, con il conteggio del resto.
- Latenze in millisecondi, tempo di attività, versione del motore: nella pagina Sistema.
- Punteggi grezzi di conviction e GQ: in prima schermata basta il livello (bassa, media, alta) e se oggi si opera.
- Le spiegazioni lunghe del livello Semplice sotto ogni cifra: una frase, il resto nel glossario.
- Il diagramma del ciclo di apprendimento e le ipotesi respinte: in prima schermata una riga ("4 provate, 0 in ombra, 0 attive").

## 6. Che cosa deve capire il principiante, una frase per riquadro
- **Stato:** "Il sistema sta girando, i dati sono di adesso e nessun freno è tirato."
- **Patrimonio e P&L:** "Il conto vale tanto; oggi ha guadagnato o perso tanto, ed è una giornata normale oppure insolita."
- **Curva e caduta:** "Così è cresciuto il conto, e di quanto siamo sotto il punto più alto mai toccato."
- **Da dove viene il risultato:** "Oggi ha guadagnato soprattutto questa regola e ha perso quest'altra."
- **Rischio:** "Siamo a tanti punti dal livello in cui il motore dimezza da solo le posizioni."
- **Atteso contro reale:** "Stiamo andando come le simulazioni dicevano, meglio o peggio."
- **Confronto:** "Per ora il nuovo sistema è avanti o indietro rispetto al vecchio, ma servono ancora tanti giorni per saperlo davvero."
- **Che cosa è cambiato:** "Da ieri il sistema ha fatto queste tre cose, per questi motivi."
- **Trade a leva:** "C'è una scommessa aperta: al massimo può perdere tanto, e il prezzo è a tanta distanza dall'uscita automatica."
- **Cancelli:** "Mancano tanti giorni e tante prove superate prima di poter usare denaro vero."

## 7. Priorità
**Dieci cose indispensabili**
1. Patrimonio totale (libro giornaliero + trade) e P&L di oggi in EUR, % e σ, con mese, anno e avvio accanto.
2. Riga di stato unica: rischio, età dei dati, battito, componenti, modalità; se qualcosa non va, sta sopra il P&L.
3. Cascata di attribuzione per strategia e libro, oggi e mese, con la riga "non attribuito".
4. Scala della caduta con gli scalini veri della configurazione e la distanza dal prossimo.
5. Cono dell'atteso: paper reale sopra la fascia simulata del profilo scelto.
6. Confronto con l'originale: imbuto del distacco, z a pari volatilità, giorni comuni e giorni necessari, esito in parole.
7. Rendimento contro S&P 500 e Bitcoin sugli stessi giorni, con i beta.
8. "Che cosa è cambiato da ieri" in otto righe al massimo.
9. Trade a leva aperti: righello stop, liquidazione, prezzo, R corrente e margine a rischio totale.
10. Etichetta SIMULATO, PAPER o DEMO su ogni numero, e paper e simulato mai nella stessa cifra.

**Dieci cose utili**
1. Curva di oggi a passi di 15 minuti. [MANCA nello snapshot: il registro del motore ha i punti, la fotografia espone solo i giornalieri.]
2. Tabella mesi × anni e barre giornaliere del mese in corso.
3. Sharpe live, backtest e verifica affiancati per strategia, con l'errore.
4. Vista delle 21:30 con il conto alla rovescia e ciò che la strategia sugli indici sta per fare. [L'IBS del giorno in corso richiede la barra in formazione nella cache: da confermare.]
5. Grafico a candele giornaliere per strumento con entrate, uscite, stop e sotto conviction e GQ. [IN ARRIVO]
6. Dispersione dei trade chiusi: massimo contro in R (x) e risultato in R (y), paper e simulato distinti. [IN ARRIVO]
7. Correlazione mobile tra le quattro strategie nel paper. [MANCA: serve la serie giornaliera per strategia; lo snapshot dà solo 30 punti.]
8. Esposizione per classe e sede come barre, con il limite segnato su ciascuna.
9. Registro dei freni dell'AI con ciò che è successo dopo. [MANCA: lo storico dei freni non è esposto; il loro valore si misura solo con i due libri paper, da costruire.]
10. Costi reali contro ipotizzati per sede. [MANCA]

**Cinque cose che le pagine di oggi sbagliano o non hanno**
1. La Panoramica non dice perché: nessuna attribuzione, strategie ordinate per quota e non per contributo, P&L di oggi senza misura di quanto sia grande.
2. Il benchmark è una linea senza nome e senza numero di distacco; nei dati live è vuoto. Il confronto in avanti con l'originale, che è il criterio per decidere, non ha pagina: quella di oggi mostra solo curve del backtest.
3. Numeri che si contraddicono tra esempio e configurazione: scalini −5/−10/−15/−20 contro 20/30/40, volatilità obiettivo 10% contro 15%, cancello a 60 giorni contro 90, EUR in una schermata e USD in un'altra. Soglie e valuta vanno lette da una fonte sola.
4. Il libro dei trade a leva non compare in Panoramica né in Rischio: non si sa se il patrimonio lo include, né quanto margine è a rischio adesso. "Leva per trade" è una tabella di ricerca messa nel menu come se fosse operativa.
5. Tutto ha lo stesso peso: sei riquadri uguali in testa, testo esplicativo più lungo dei numeri, e nessuna vista "da ieri". Manca la gerarchia tra ciò che si guarda ogni giorno e ciò che si guarda una volta al mese.
