# Requisiti del terminale: rischio e trading (quant 2)

Parlano il responsabile del rischio e il trader di esecuzione. Contenuto, gerarchia e comportamento; nessuna indicazione di stile.
Premesse lette nel codice: soglie vere in `config/gerva.yaml` (caduta −20 / −30 / −40%, −4% in 24 ore mobili, −8% in 7 giorni mobili, leva 2x operativa e 3x invalicabile, 40% per sede crypto, 35% per strumento); libro dei trade su barre giornaliere chiuse, con registro proprio (somma margini ≤ 15%, rischio aperto ≤ 6%, controvalore ≤ 1,5x, 4 trade, 15x al massimo). Semantica unica dei colori: **sicuro / attenzione / violazione**; lo stato lo decide il motore (`status`), la pagina non inventa soglie. Dove manca, attenzione dal 60% di utilizzo.

## A. RISCHIO

### A1–A2. Le domande a colpo d'occhio, in ordine, con numeri e grafico

| # | Domanda | Numeri | Grafico, assi, soglie disegnate |
|---|---|---|---|
| 1 | Il motore è libero, frenato o fermo, e perché? | Stato, scala (1 / 0,5 / 0,25 / 0), motivi testuali, da quando, condizione di rientro (isteresi: caduta sotto metà soglia, cioè −10% e −15%) | Nessun grafico: una fascia fissa in cima a ogni pagina. Sotto la curva del patrimonio, un nastro temporale degli stati. Sicuro = NORMAL; attenzione = REDUCED; violazione = HALTED e KILLED |
| 2 | Quanto manca a ogni freno? | Caduta attuale e massimo in €; per −20 / −30 / −40: punti mancanti, € mancanti, patrimonio a cui scatta, distanza in «giornate di ES». Per −4% (24 h) e −8% (7 gg): P&L mobile, patrimonio di riferimento, € mancanti | (a) **Scala dei freni**: un solo asse orizzontale da 0 a −40%, segnaposto «adesso», tacche a −20 / −30 / −40 con l'azione scritta, banda di isteresi, riga di riferimento a −21% (caduta massima SIMULATA). (b) Curva sott'acqua nel tempo (x data, y caduta %) con le tre soglie tracciate. (c) Due barre a bersaglio per 24 h e 7 gg con la tacca del limite |
| 3 | Qual è il peggio che può succedere oggi? | Somma dei margini isolati (€, % del registro dei trade, % del fondo) contro il 15%; rischio aperto agli stop contro il 6%; scenario di gap sul libro giornaliero; totale e caduta risultante | **Cascata**: patrimonio di oggi → perdite agli stop → eccedenza fino ai margini (gap oltre lo stop, sede irraggiungibile) → gap del libro giornaliero → patrimonio finale. Il punto d'arrivo è proiettato sulla scala dei freni: si legge quale scalino scatterebbe |
| 4 | Dove siamo esposti, rispetto ai tetti? | Lordo, netto; per classe; per sede contro il 40%; per strumento contro il 35% (primi cinque pesi); long e short separati | Barre orizzontali divergenti dallo zero (short a sinistra), una riga per sede e per strumento, tacca del tetto su ogni riga, utilizzo in % a fine riga |
| 5 | Quanta leva, rispetto al tetto? | Leva del conto contro 2x e 3x; leva di ogni trade contro 15x; volatilità realizzata 30 gg contro obiettivo 15% | Barra a bersaglio con due tacche (operativo, invalicabile); serie a 90 giorni (x data, y leva) con la riga del tetto. Leva del conto e leva del trade mai nello stesso numero |
| 6 | I dati sono freschi? | Età per fonte contro il massimo (crypto 36 h, IBKR 100 h), età della fotografia contro `stale_after_s`, battito, cicli falliti di fila contro 5 | Riga di contatori per fonte con il massimo accanto; nastro delle ultime 24 ore, 96 celle da 15 minuti (riuscito / fallito / mancante). Oltre il massimo = violazione: il motore va in HALTED |
| 7 | Ci sono ordini non riconciliati? | Numero (deve essere 0), età del più vecchio, elenco; ordini in attesa con età | Solo conteggio ed elenco. Qualunque valore sopra zero è violazione |
| 8 | Quanto si perde in un giorno normale? | VaR ed ES 95% a 1 giorno, in % e in € | Istogramma dei rendimenti giornalieri (x rendimento, y frequenza) con righe di VaR, ES e −4%. È una statistica, non un freno: sta sotto le altre |

Gerarchia: 1–3 sempre nel primo schermo della pagina Rischio e riassunte in Panoramica; 4–5 subito sotto; 6–7 in una riga compatta che si espande solo se non sicura; 8 in fondo. Tre famiglie tenute distinte: **freni** (cambiano lo stato), **tetti** (riducono i pesi), **statistiche** (non fanno nulla). Ogni percentuale del libro dei trade dichiara il denominatore: registro dei trade oppure fondo intero.

### A3. Il comando KILL

- **Impossibile da non vedere.** Presente nella fascia fissa di ogni pagina, accanto allo stato del rischio, nella stessa posizione sempre, anche su telefono. Mostra in anticipo se è utilizzabile: «KILL spento su questo server» quando il token non è configurato, non scoperto al momento dell'emergenza.
- **Impossibile da premere per errore.** Il controllo apre solo una finestra; nessuna scorciatoia a tasto singolo; la scorciatoia (`Maiusc`+`K`) apre e non invia. Nella finestra: token digitato a mano, parola KILL per esteso, motivo. Invio disabilitato finché manca qualcosa; `Invio` non invia dal campo del token; il fuoco iniziale è su «Annulla»; `Esc` chiude e svuota.
- **Anteprima degli effetti prima dell'invio.** Quante posizioni e quale controvalore verranno chiusi, entro quando (al ciclo successivo, fino a 15 minuti), che cosa serve per ripartire (togliere il file sul server, `gerva reset-kill`, ripartenza da HALTED con massimo azzerato). Va detto in chiaro che cosa il KILL non fa: dal codice blocca i nuovi trade a margine isolato, ma quelli aperti restano gestiti dai loro stop (da confermare con il costruttore).
- **Dopo l'invio, tre stati distinti.** «Richiesto, in attesa del ciclo» → «Eseguito: N posizioni chiuse alle hh:mm» → oppure «NON attivato» con il motivo. In stato KILLED la fascia occupa ogni pagina con ora, motivo e passi per ripartire; i numeri restano leggibili.
- Mai un pulsante «annulla KILL»: dalla pagina non si toglie.

### A4. Viste di stress

- **Giornate storiche sul libro di oggi** (SIMULATO): 12 mar 2020 (tutto scende insieme), 19 mag 2021 (crollo solo crypto), 5 ago 2024 (gap tra classi dopo il fine settimana), 10 ott 2025 (cascata di liquidazioni sui perpetual). Una riga per data: P&L del libro giornaliero, P&L del libro dei trade, totale in % e €, caduta risultante, freno che scatterebbe, primi tre contributi.
- Due calcoli affiancati: da chiusura a chiusura, e dal minimo del giorno (decide se un trade esce allo stop, oltre lo stop o perde tutto il margine).
- Grafico: barre orizzontali impilate per classe, una per data; righe verticali alla distanza da −4% in 24 ore e dal prossimo scalino di caduta.
- Ipotesi scritte sulla scheda: pesi di oggi fermi, nessuna reazione dentro la giornata, sostituto dichiarato per gli strumenti che allora non esistevano (SOL il 12 mar 2020), «n.d.» se il sostituto non c'è.
- **Griglia di shock** (crypto −10 / −20 / −30 / −50% contro azioni −5 / −10 / −20%): ogni cella dà la caduta e lo stato risultante.
- **Sede irraggiungibile**: per ogni sede, margini isolati persi più esposizione bloccata.

### A5. Avvisi

| Gravità | Eventi | Come emerge | Presa in carico |
|---|---|---|---|
| Critico | Cambio di stato verso HALTED o KILLED; dati oltre l'età massima; ordine non riconciliato; 5 cicli falliti; battito assente; perdita oltre il margine; trade chiuso oltre lo stop | Fascia persistente su tutte le pagine, titolo della scheda del browser, suono solo se scelto | Obbligatoria; la fascia si riduce a «preso in carico alle hh:mm» e resta finché la condizione dura |
| Attenzione | Stato REDUCED; freno o tetto oltre il 60%; trade entro 0,5 ATR dallo stop; giorno 6 su 7 di un trade; ordine rifiutato; overlay AI in scadenza; fonte lenta; costi oltre 1,5 volte | Contatore nel centro avvisi, segno sulla voce di menu della pagina interessata | Facoltativa, anche in blocco |
| Informazione | Trade aperto o chiuso, ribilanciamento, rientro di stato, regola passata in ombra | Solo registro | Nessuna |

Ogni avviso dice: che cosa è successo, valore contro soglia, che cosa ha già fatto il motore, che cosa devi fare tu (spesso: niente), collegamento al riquadro. La stessa condizione è un solo avviso con contatore, primo e ultimo istante. Se peggiora di gravità si ripresenta anche se già presa in carico. Dati fermi o pagina offline: lo stato del rischio diventa «sconosciuto», mai l'ultimo «sicuro» visto.

## B. TRADING

### B1. Il grafico dello strumento

- **Riquadro principale:** candele giornaliere, scala lineare o logaritmica, volume sotto con la sua media a 20 giorni. In chiaro la data dell'ultima barra chiusa: non esiste l'intraday.
- **Sovrapposizioni utili a queste regole:** VWAP ancorato all'apertura del mese (segmenti che ripartono ogni mese, non una linea continua); le medie mobili che le strategie usano davvero (le dichiari il costruttore; in mancanza 50 e 200 giorni); banda a ±1 ATR dall'ultima chiusura, cioè dove cadrebbe lo stop di un trade aperto oggi.
- **Riquadri sotto, stesso asse del tempo:** (1) conviction da 0 a 1, linea a gradini, soglie a 0,60 e 0,75, tre fasce nominate (nessun trade / confermato 0,5% / eccezionale 1%); (2) indicatore Gervasoni con soglie a −0,50, 0,53 e 1,42 e la dicitura «in ombra: non decide»; (3) ATR% a 14 giorni calcolato come nel motore (media di (massimo − minimo) / chiusura), con la leva che ne discende letta nel mirino. Ogni riquadro si chiude; per gli ETF conviction e GQ mostrano «non calcolato per questo strumento».
- **Come si disegna un trade:** ingresso = segno sulla barra e linea orizzontale fino all'uscita o a oggi; stop iniziale = linea tratteggiata; stop mobile = linea a gradini che si muove solo a favore, con il massimo che lo ancora; liquidazione = linea sempre in vista quando un trade è aperto (se fuori scala, un richiamo al bordo con la distanza); uscita = segno con motivo (stop / conviction bassa / durata massima) e R. Zona ingresso–stop etichettata «1 R»; zona stop–liquidazione etichettata con il rapporto (deve restare ≤ 60%). Scala in R sul lato destro per il trade aperto (−1, 0, +1, +2). Riga verticale al giorno 7. Trade passati: segni compatti, dettaglio al passaggio. Etichette al bordo destro con prezzo e distanza in % e in ATR.
- **Onestà della barra giornaliera:** lo stop è verificato sul minimo del giorno; la barra in cui è stato toccato è marcata; il percorso dentro la barra non si conosce.
- **Intervalli:** 1M, 3M, 6M, 1A, Tutto, più «Trade» (inquadra il trade aperto da 20 barre prima dell'ingresso). Barre settimanali oltre un anno. Trascinamento e zoom; intervallo e mirino restano fermi a ogni aggiornamento.
- **Mirino:** si aggancia alla barra; una sola linea verticale attraversa tutti i riquadri; in alto apertura, massimo, minimo, chiusura, variazione, volume, conviction, GQ, ATR%, distanza dal VWAP in ATR. Con un trade aperto il prezzo sotto il mirino è tradotto in R e in distanza da stop e liquidazione. Modalità misura: due punti, differenza in %, ATR, R e barre.
- **Confronto di due strumenti:** entrambi a base 100 dall'inizio dell'intervallo visibile (si ricalcola spostandosi), un solo asse in %; a scelta il rapporto A/B; correlazione mobile a 30 e 90 giorni; le due conviction nello stesso riquadro. Mai due assi di prezzo.

### B2. Il pannello del libro dei trade

- **Intestazione, totali contro tetti:** trade aperti su 4; rischio aperto su 6%; margini su 15%; controvalore su 1,5x; P&L di giornata del libro contro −3% (niente nuovi trade) e −5% (chiude tutto); data dell'ultima barra elaborata; avanzamento dei cancelli (40 trade chiusi, R medio positivo e almeno +0,12, nessuna perdita oltre il margine).
- **Per trade aperto:** strumento, verso, livello (confermato / eccezionale), ingresso, stop attuale e stop iniziale, distanza dallo stop in % e in ATR, distanza dalla liquidazione in % e in ATR, rapporto stop/liquidazione, leva, controvalore, margine (= perdita massima), rischio iniziale in € e in % del registro, rischio residuo con lo stop mobile (può essere un guadagno bloccato), R corrente, MAE e MFE in R, giorni su 7, funding pagato in € e in R (marcato «stimato» se a tasso predefinito), conviction e GQ all'ingresso e oggi, condizioni di uscita in parole («esce se: stop, conviction bassa, giorno 7»).
- Ordinamento predefinito: distanza dallo stop in ATR, crescente. Selezionare una riga apre il grafico inquadrato sul trade.
- **Trade chiusi:** date, giorni, livello, leva, R, P&L in €, motivo di uscita, MAE, MFE, costi (commissioni più funding) in R, origine (paper / SIMULATO, mai mescolati senza etichetta). Sopra: R medio, quota di vincenti, serie perdente in corso, R cumulato nel tempo, istogramma degli R, R medio per motivo di uscita; in Esperto la dispersione MAE–R.
- **Registro delle decisioni:** proposte rifiutate con il motivo del libro («conviction sotto la soglia», «nessuno spazio residuo», «interruttore di giornata») e tagli da regole apprese o da AI.

### B3. Blotter e qualità dell'esecuzione

- **Colonne:** ora, strumento, verso, quantità, prezzo, controvalore in € e in % del patrimonio, stato, strategia, sede, motivo, «riduce / aumenta il rischio», ciclo di origine. Filtri per stato, sede, strategia, periodo. In cima, se presenti: non riconciliati e in attesa oltre un ciclo.
- **Rifiuti:** raggruppati per motivo sugli ultimi 30 giorni (tetto di sede, prezzo oltre il 5% dall'ultimo, ordine oltre il 25% del patrimonio, sotto il minimo di 25, stato HALTED o KILLED), con conteggio e ultimo caso. Un rifiuto del motore è il sistema che funziona: va distinto da un rifiuto della sede.
- **Qualità:** slippage in punti base tra prezzo di decisione e prezzo eseguito, per sede e strategia, con distribuzione; costi reali contro ipotizzati (crypto 25 pb più 5, IBKR 5 pb più 2) e il rapporto contro il cancello di 1,5; quota di eseguiti, tempo all'esecuzione, quota di annullati.
- Nel registro interno l'esecuzione è simulata con le stesse ipotesi: slippage e costi mostrano «non misurabile in paper interno», non zeri. Il libro dei trade non invia ordini: nel blotter non compare, e lo si dice.

### B4. Watchlist

- **Colonne:** strumento, classe, sede, ultima chiusura, variazione del giorno in % e in ATR, 7 giorni, ATR%, conviction (punteggio, livello, variazione su ieri, distanza da 0,60 e 0,75), GQ e livello, distanza dal VWAP mensile in ATR, peso nel libro giornaliero, trade aperto (R corrente), età del dato.
- **Ordinamenti:** predefinito «più vicino a un'azione» (trade aperti per distanza dallo stop, poi conviction decrescente); movimento del giorno in ATR; peso; conviction; età del dato. Filtri: solo in portafoglio, solo con trade, solo sopra soglia.

### B5. Tastiera: le dodici scorciatoie

1. `/` cerca strumento o pagina.
2. `g` + lettera: vai a pagina (`g r` rischio, `g t` trade, `g o` ordini).
3. `j` / `k`: riga successiva / precedente in watchlist, trade, blotter; il grafico segue.
4. `Invio` apre la riga nel grafico; `Esc` chiude, torna indietro, toglie il mirino.
5. `←` / `→`: mirino di una barra; con `Maiusc` di dieci.
6. `1`…`5`: intervalli 1M, 3M, 6M, 1A, Tutto.
7. `+` / `−` / `0`: zoom e ripristino.
8. `c`: confronto con un secondo strumento.
9. `m`: modalità misura.
10. `[` / `]`: trade precedente / successivo sul grafico.
11. `a`: centro avvisi; `x` prende in carico l'avviso selezionato.
12. `?`: elenco delle scorciatoie.

## C. Priorità

**Dieci indispensabili**
1. Fascia fissa su ogni pagina: stato del rischio, scala, motivo, da quando, condizione di rientro, età dei dati; «sconosciuto» se i dati sono fermi.
2. Scala dei freni unica: −20 / −30 / −40, −4% in 24 ore, −8% in 7 giorni, distanza in punti, € e giornate di ES.
3. Peggior caso di oggi: margini isolati più gap, proiettato sulla scala dei freni.
4. KILL raggiungibile ovunque, in due passi, con anteprima degli effetti e conferma di esecuzione.
5. Grafico a candele con volume, conviction, GQ, ATR, VWAP mensile e i livelli del trade (ingresso, stop, stop mobile, liquidazione, uscita).
6. Pannello del libro dei trade: distanze in % e ATR, R corrente, MAE/MFE, giorni su 7, funding, totali contro tetti.
7. Esposizione lorda, netta, per sede e per strumento con i tetti disegnati; leva contro 2x e 3x.
8. Stress sulle quattro giornate storiche applicate al libro di oggi, con il freno che scatterebbe.
9. Centro avvisi a tre gravità, presa in carico, un avviso per condizione, critici persistenti.
10. Blotter con non riconciliati in evidenza, rifiuti per motivo, costi reali contro ipotizzati.

**Dieci graditi**
1. Confronto di due strumenti con rapporto e correlazione mobile.
2. Modalità misura in %, ATR e R.
3. Replay barra per barra di un trade chiuso.
4. Griglia di shock parametrici con lo stato risultante.
5. Nastro storico degli stati del motore sotto la curva del patrimonio.
6. Contributo al VaR per posizione e per strategia.
7. Dispersione MAE–R e istogramma degli R, simulato contro paper.
8. Nastro dei cicli delle ultime 24 ore.
9. Calcolatore «se aprisse oggi»: stop, leva, margine e liquidazione dall'ATR di oggi (solo calcolo, nessun ordine).
10. Scadenze in un'unica riga: giorno 7 dei trade, scadenza dell'overlay AI; esportazione CSV di blotter e trade.

**Cinque cose che le pagine di oggi sbagliano o non hanno**
1. L'esempio DEMO mostra soglie vecchie (scalini −5 / −10 / −15 / −20, giornata −3%, crypto 50%, obiettivo 10%) e non ha la perdita a 7 giorni; anche il docstring di `engine.py` cita 10 / 20. Una pagina di rischio con soglie sbagliate è peggio di nessuna pagina.
2. Il KILL sta in fondo a una sola pagina, sotto un esempio didattico; non si sa se è attivo prima di premerlo; dopo l'invio manca la conferma che il motore abbia chiuso.
3. Il libro dei trade, la parte a 11x, è assente da Rischio e Panoramica: niente somma dei margini, niente rischio aperto, niente distanze da stop e liquidazione. «Leva per trade» è solo ricerca.
4. Non esiste un grafico dello strumento: nessuna candela, nessun livello di trade; la pagina Ordini non misura l'esecuzione.
5. La tabella «Limiti» mette nella stessa barra freni, tetti e statistiche; la caduta è misurata solo contro il KILL; isteresi, durata dello stato e peggior caso non compaiono; gli avvisi non si prendono in carico.

**Desideri che richiedono dati che il fondo non ha (da segnalare)**
- Distanza dallo stop in tempo reale: il libro dei trade vede solo la barra giornaliera chiusa; il prezzo del ciclo a 15 minuti è al massimo indicativo.
- Slippage: servono prezzo di decisione, prezzo eseguito e commissione per ordine; oggi l'ordine ha un solo prezzo.
- Stress sulle date storiche: serve una tabella di shock per strumento (chiusura e minimo) calcolata dal motore; `/market/ohlc` dà 1.500 barre se non si chiede altro (massimo 5.000), quindi il 2020 e il 2021 vanno richiesti apposta, e alcuni strumenti allora non esistevano.
- Liquidazione realistica: minimi dei perpetual per sede e funding vero della sede (oggi Binance in cache o 0,01% ogni 8 ore; mantenimento ipotizzato 0,5%).
- Profondità, spread, impatto: nessun book né tick. Calendario di eventi e notizie: nessuna fonte.
- Durata e storia degli stati, patrimonio di riferimento a 24 ore e 7 giorni: il motore li calcola, la fotografia non li espone tutti.
- Presa in carico condivisa tra dispositivi: sarebbe una seconda scrittura, vietata dal vincolo; resta nel browser.
