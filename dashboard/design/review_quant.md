# Revisione quant della build v7 (Oggi, Rischio, Mercati)

Metodo: app avviata con i dati di esempio e usata con Playwright a 1440×900 e 390×844, ai tre livelli; poi una seconda istanza con fotografie costruite apposta (vecchia di 23 minuti, REDUCED a −22,4%, HALTED, KILLED, senza scalini, server spento). Il KILL non è mai stato inviato. Schermate in `scratchpad/shots/` con prefisso `rq-` (qui citate senza estensione). Ogni cifra è stata ricalcolata dai JSON delle API.

## 1. Prova dei cinque secondi (sopra la piega, 1440×900)

| Domanda | S | E | T | Perché fallisce |
|---|---|---|---|---|
| G-D1 Guadagniamo? | sì | sì | sì | ma il patrimonio non è il totale (P0-1) e la σ è calcolata male (P0-11) |
| G-D2 Rotto o frenato? | in parte | in parte | in parte | a 1440 scala e motivo sono nascosti; i dati del libro dei trade vecchi di 12 giorni non accendono nulla (P0-2) |
| G-D3 Perché? | no | in parte | sì | in S la cascata è tagliata dalla piega; mai i 3 strumenti migliori e peggiori, mai il libro dei trade |
| G-D4 Distanza dal freno | sì | sì | sì | solo la distanza: VaR, leva e margine a rischio non ci sono |
| G-D5 Come il backtest? | no | no | no | il cono è in terza riga (y ≥ 1.123) a tutti i livelli |
| G-D6 Avanti a S&P, BTC, originale? | no | no | no | sotto la piega; senza z, senza S&P 500 né Bitcoin |
| G-D7 Cambiato da ieri? | no | in parte | sì | in S si vede 1 riga su 3 |
| G-D8 Prossima chiusura? | no | no | in parte | il righello si vede solo in T; conto alla rovescia, stato di EQ-MR e «perché oggi non apre» non esistono |
| G-D9 Denaro reale? | no | no | no | sotto la piega (accettabile: «a un clic») |
| R-1 Stato, scala, motivo | sì | sì | sì | «da quando» e rientro: n.d. |
| R-2 Distanza da ogni freno | in parte | sì | sì | tabella solo per −20; 24 ore e 7 giorni con valori sbagliati (P0-4, P0-5) |
| R-3 Peggio di oggi | sì | sì | sì | il verdetto non è affidabile (P0-3) |
| R-4/5 Tetti e leva | no | no | no | seconda riga (y ≥ 835) |
| R-6/7 Dati freschi, non riconciliati | no | no | no | una riga a y ≥ 1.312, senza età per fonte né conteggio dei non riconciliati |

Telefono: sopra la piega solo G-D1 e lo stato; Oggi è lunga 3.800 px. Serve almeno la distanza dal freno dentro il riquadro Patrimonio.

## 2. P0: sbagliato o fuorviante

1. **Il patrimonio in testa non è il totale e chiama il libro dei trade «conto separato».** Oggi · Patrimonio (`rq-d-oggi-esperto-full`): 12.197,04 € con sotto «libro dei trade 3.084,20 €, conto separato». `gerva/live/tradecycle.py` dice il contrario: stesso capitale, contributo = `equity − start_equity` (+84,20 €). Chi legge somma 15.281 €. Voglio: cifra eroe = patrimonio + contributo dei trade (dopo conferma che la fotografia non lo includa già), sotto «libro giornaliero … · contributo dei trade +84,20 €»; via «conto separato»; ogni % dei trade con il denominatore scritto («A rischio 0,3%» oggi divide per il libro giornaliero).
2. **Dati vecchi di 12 giorni mostrati come vivi.** Libro dei trade `asof` 31 ott e ultima barra BTC 31 ott, oggi 12 nov, fascia «Normale · 3 s fa». Su quella chiusura si calcolano «+1,23 R» e «Dallo stop −7,2%»; il trade è a «giorno 20» con durata massima 7 (`rq-d-oggi-terminale`, `rq-x-book-Aperti`). Voglio: età per fonte (libro dei trade, ultima barra per simbolo) contro il massimo (crypto 36 h, azioni 100 h); oltre il massimo il riquadro va in «sconosciuto» con R attenuato e l'etichetta «dati del 31 ott»; i giorni contati fino ad `asof` («7 di 7»); la fascia mostra la fonte più vecchia.
3. **Lo shock mancante vale zero e rovescia il verdetto.** Rischio · Il peggio di oggi e Stress (`rq-d-rischio-esperto-full`): SOL (5,5%) non ha shock il 12 mar 2020 e conta 0. Risultato: −15,8%, «nessuno scalino di caduta». Con lo shock mediano delle crypto di quel giorno (−44%): −18,2%, caduta −21,5%, scatta il −20%. Voglio: sostituto dichiarato oppure totale «almeno −15,8% · copertura 94%»; mai «nessun freno» con peso scoperto.
4. **Stessa grandezza, due numeri nello stesso riquadro** (`rq-crop-freni-esperto`). Peggior caso: −19,1% nel verdetto, −19,3% sulla scala (somma di percentuali invece di patrimonio finale / massimo). Freno a 24 ore: «mancano 530 €» ma «scatta a 11.709 €», che è 488 € sotto il patrimonio; il valore giusto è 12.154,64 × 0,96 = 11.668 €. Voglio una sola funzione e un test.
5. **Le corsie 24 ore e 7 giorni non mostrano ciò che il motore misura.** «Ultimi 7 giorni · P&L mobile 0,00%» mentre la curva fa +1,98% in 7 giorni: il campo è `min(week_pnl, 0)`. La corsia 24 ore usa `nav.pnl_day_pct` e non la perdita mobile su cui il motore frena. Voglio `day_pnl`, `week_pnl` e i due patrimoni di riferimento nella fotografia; fino ad allora «perdita usata 0,00% · P&L n.d.».
6. **Superato uno scalino, la distanza resta misurata su quello.** Con REDUCED a −22,4%: «−2,4 punti = −296 €», «giornate di ES −2,5» (`rq-z-reduced-oggi`, `rq-z-reduced-rischio`). Voglio la distanza dal prossimo scalino non toccato (−30%: 7,6 punti) e la riga «rientro a NORMAL sotto −10%»; tabella sempre con i tre scalini.
7. **Il righello del trade sparisce proprio quando si inquadra il trade.** A 1M e dopo `[` o clic sulla riga, la scala y segue solo le candele: entrata, stop e liquidazione escono dal quadro senza richiamo; l'anello d'entrata e il rombo d'uscita finiscono dipinti sopra il VOLUME (`rq-x-1M-trade`, `rq-x-key-bracket`). Voglio i livelli del trade aperto dentro l'intervallo y (o richiami al bordo con distanza in % e ATR) e i segni ritagliati al riquadro del prezzo.
8. **Provenienza ambigua sul grafico.** Trade di esempio sopra prezzi veri, etichette «PREZZI REALI» e «TRADE» senza la parola ESEMPIO (`rq-x-crosshair`). Entrata a 74.120 il 24 ott, giorno con minimo 79.221; l'uscita a «+2,2 R» galleggia fuori dalle candele. Si legge uno slittamento dell'8%. Voglio «TRADE · ESEMPIO» anche dentro l'area del tracciato, e un libro di esempio generato dalla stessa cache dei prezzi; altrimenti nessun segno di trade su prezzi veri.
9. **L'esempio si contraddice da solo, ed è ciò che vedrà il proprietario.** Tre prezzi di BTC (61.842 nelle posizioni, 77.582 in Mercati, 62.113 nel confronto); patrimonio 12.197 contro 12.610 del confronto; «giorno 12 di 60» ma 120 giorni comuni e «dall'avvio +21,97%» su 954 giorni; +1,23 R × «a rischio 30,80 €» = 38 €, mentre la posizione guadagna 150 € (il rischio allo stop su 3.210 € è 92–122 €); livello «confermato» con rischio all'1%. Voglio un solo generatore per fotografia, libro, confronto e barre, con un test: stesso patrimonio, stessi prezzi, stessi giorni, R × rischio = P&L.
10. **Cancelli sbagliati.** «giorno 12 di 60» in fascia e in Oggi; il motore dice 90 (`gates.py`, PAPER.md). Nel conteggio «4 di 7» entra «Sharpe in paper 0,92 ✓» dopo 12 giorni. Era già l'errore 3 della nota del gestore. Voglio l'esempio prodotto da `G.evaluate` e lo Sharpe «in corso · 12 su 60».
11. **σ di giornata sulla volatilità realizzata (8,3%) invece dell'obiettivo (15%).** «+0,8 σ» al posto di +0,44 σ; con mercati calmi ogni giornata sembra «mossa». Voglio `vol_target / √365`, come da convenzione, scritto nel «?».
12. **Livelli di conviction e GQ incoerenti.** In Semplice tutto ciò che sta sotto 0,60 è «conviction media» (ADA 0,27, ALGO 0,36); in Decisioni «GQ −1,33 · media» con soglia a −0,50; nella fotografia 0,64 è «media» e 0,72 «alta» (`rq-d-mercati-semplice`, `rq-x-book-Decisioni`). Voglio una sola funzione con i nomi del libro: sotto 0,60 «nessun trade», 0,60–0,75 «confermato», da 0,75 «eccezionale»; GQ sulle sue tre soglie.

## 3. P1: indispensabile mancante

1. **Terminale non è un terminale.** Oggi scorre 1.545 px a 1440×900 e 1.443 a 1920×1080; sopra la piega 2 riquadri interi e 3 tagliati contro i 10 promessi; righe alte quanto il riquadro più lungo, quindi riquadri mezzi vuoti (`rq-d-oggi-terminale-full`, `rq-w-1920-oggi-terminale`). Voglio griglia fissa senza scorrimento di pagina, liste che scorrono dentro, e lo spazio liberato usato per cono, confronto, prossima chiusura, tetti.
2. **Fascia di stato incompleta.** A 1440 scala e motivo hanno `display: none` e «6 di 7» non dice quale. Con dati fermi la pastiglia è un cerchio tratteggiato vuoto, senza «Sconosciuto · ultimo visto NORMAL 16:42» (`rq-z-old-oggi`). In REDUCED nessuna riga sopra il P&L. In KILLED la pastiglia dice «KILL» accanto al pulsante KILL e la riga afferma «ha già chiuso tutto» con 10 posizioni ancora nella fotografia (`rq-z-killed-oggi`).
3. **ATR e RSI non si vedono mai a 1440×900**, né in Esperto né in Terminale: la tela è alta 436 e 405 px e il codice tiene solo due riquadri. `v7-mercati-ritaglio` viene da una finestra più alta. Voglio il grafico alto almeno 560 px in E/T e riquadri chiudibili uno a uno.
4. **Grafico, ciò che manca rispetto a B1:** legenda dei colori delle linee; VWAP a segmenti mensili (oggi linea continua con salti); media a 20 giorni del volume; banda ±1 ATR; stop mobile a gradini; scala in R a destra; riga del giorno 7; rapporto stop/liquidazione; cartellini con distanza in % e ATR; prezzo dell'ultima chiusura sull'asse; nel mirino prezzo tradotto in R e distanza da stop, liquidazione e VWAP; intervallo «Trade»; barre settimanali; scala log predefinita oltre un anno; «Tutto» sono 1.500 barre (dal 2023) e non lo dice; misura (`m`) e confronto (`c`) assenti.
5. **Libro dei trade:** niente totali contro tetti (aperti su 4, rischio su 6%, margini su 15%, controvalore su 1,5x, P&L di giornata contro −3% e −5%); mancano distanza dalla liquidazione, distanze in ATR, controvalore, stop iniziale e attuale, rischio residuo, funding, conviction e GQ all'ingresso e oggi, condizioni di uscita; MAE/MFE e livello solo in Terminale; Chiusi senza R cumulato, istogramma, R per motivo.
6. **Elenco:** 16 di 102, in ordine alfabetico dopo i primi cinque (AAVE, ADA, ALGO al posto di BNB e LINK che sono in portafoglio); nessuna intestazione, ordinamento o filtro; mancano 7 giorni, ATR%, peso, R del trade, età del dato (BTC del 31 ott accanto a SPY del 9 nov senza data).
7. **Oggi:** confronto senza z, giorni necessari, S&P 500, Bitcoin e beta (le colonne `spy` e `btc` sono già in `/compare`); nessuna «prossima chiusura»; attribuzione senza libro dei trade, senza punti base, senza strumenti; Mese e Dall'avvio lasciano 104 e 244 pb non attribuiti (più di metà del mese): dichiarato, ma inservibile finché la base di `pnl_*_pct` non è definita.
8. **«Che cosa è cambiato»:** ordine per ora e non per gravità; il rifiuto AVAX compare due volte (avviso e ordine); mancano posizioni cambiate oltre 1 punto, regime e conviction di ieri contro oggi, cambi di stato.
9. **Rischio:** tetti senza long e short separati, primi cinque strumenti e classi; «sede crypto 36,5%» somma Kraken e Binance mentre il tetto di configurazione è per sede, e le due sedi portano «nessun tetto di sede»; leva senza la tacca a 3x, leva del trade «tetto n.d.» (è 15x); dati senza età per fonte, senza nastro dei cicli, senza «non riconciliati: 0», con un ordine in attesa da 6 ore non segnalato; righe di stress senza P&L dei trade, caduta risultante, freno che scatta, primi tre contributi; istogramma senza la riga a −4%.
10. **Dati fermi non propagati:** con fotografia vecchia «Il peggio di oggi», Tetti e Stress restano a piena luce con il verdetto «−15,8% in un giorno» e «Scatta a» compilato; senza libro dei trade il «Patrimonio finale 10.272 €» non dice «almeno» (`rq-z-old-rischio`).
11. **Avvisi:** lista piatta, nessuna presa in carico per avviso (`x` non fa nulla), niente valore contro soglia né «che cosa devi fare»; un critico di 6 giorni fa conta ancora nel contatore.
12. **Provenienza:** senza cancelli il binario scrive «Giorni paper 954» (`rq-z-noladder-rischio`); la curva del patrimonio unisce 954 giorni e 12 di paper senza il confine «avvio del paper»; Stress porta solo SIMULATO su posizioni di ESEMPIO; nessuna etichetta dentro l'area di cono e confronto.
13. **KILL:** con il comando spento sul server «Attiva KILL» si abilita lo stesso (`rq-y-kill-filled`); su telefono il pulsante non ha parola né stato; l'anteprima non dice che si riparte da HALTED con massimo azzerato.

## 4. P2: attrito

1. Scala dei freni: azioni a −30% e −40% sovrapposte e illeggibili, «dati fermi» sopra «peggiore finora»; ultima colonna della tabella tagliata in Esperto (`rq-crop-freni-esperto`).
2. Il prezzo del mirino copre il cartellino «Liq.»; i cartellini coprono le ultime candele (un quarto del grafico su telefono) e l'etichetta «1 R».
3. Assi: su SPY «730,00» sopra «125,9 M»; ATR con una sola tacca a 0,6% quando vale 1,3%; conviction con la sola soglia 0,60; titoli dei riquadri sopra le linee; mesi senza anno; volume senza unità.
4. Tastiera: `0` non fa nulla benché elencato; `Maiusc`+frecce scorre invece di muovere il mirino di dieci barre; dopo `[` il selettore resta su «6M».
5. Il titolo «Dov'è il prezzo rispetto ai livelli del trade?» resta anche su SPY o ADA, che non hanno trade.
6. Arrotondamenti e formati: «Totale 42 €» contro «+42,40 €»; «adesso −1,2%» contro «−1,15%»; «aggiornato 2026-10-31»; «Dallo stop −7,2%» (voglio «+7,8% sopra lo stop · 3,2 ATR»).
7. Senza patrimonio, «Il peggio di oggi» aggiunge uno stato vuoto a ogni aggiornamento: cinque in 30 secondi (`rq-z-noladder-rischio`).
8. Un suggerimento resta appeso sopra la nota dell'attribuzione (`rq-w-1920-oggi-terminale`); nel cono «avvio» è tagliato e l'orizzonte è di soli 3 mesi.
9. Tavolozza: strumenti in ordine alfabetico, nessuna esportazione CSV.
10. Telefono: la fascia tronca «DEMO: dati di ese…» e non mostra il contatore degli avvisi.

## 5. Scorecard degli indispensabili

| # | Richiesta | Esito | Nota |
|---|---|---|---|
| G1 | Patrimonio totale, P&L in €, %, σ | parziale | manca il totale; σ sulla base sbagliata |
| G2 | Riga di stato unica, sopra il P&L se serve | parziale | P1-2 |
| G3 | Cascata con «non attribuito» | parziale | solo oggi torna; niente libro dei trade |
| G4 | Scala della caduta con scalini veri | fatto | con il difetto P0-6 |
| G5 | Cono dell'atteso con il paper sopra | fatto | sotto la piega; orizzonte 3 mesi |
| G6 | Imbuto, z, giorni comuni e necessari, esito | parziale | solo due curve a base 100 e «In corso» |
| G7 | Contro S&P 500 e Bitcoin, con i beta | manca | i dati ci sono |
| G8 | «Che cosa è cambiato», 8 righe | parziale | P1-8 |
| G9 | Trade aperti: righello, R, margine | parziale | righello e R sì; dati vecchi, giorni sbagliati |
| G10 | Provenienza su ogni numero | parziale | P0-8, P1-12 |
| R1 | Fascia: stato, scala, motivo, da quando, rientro, età | parziale | P1-2 |
| R2 | Scala dei freni unica in punti, € e giornate di ES | parziale | P0-4, P0-5, P0-6 |
| R3 | Peggior caso proiettato sulla scala | parziale | P0-3 |
| R4 | KILL ovunque, due passi, anteprima, conferma | parziale | fuoco, Invio ed Esc corretti; P1-13; stati dopo l'invio non provati |
| R5 | Candele con volume, conviction, GQ, ATR, VWAP, livelli | parziale | P0-7, P1-3, P1-4 |
| R6 | Libro dei trade completo | parziale | 12 colonne su circa 25, nessun totale contro tetti |
| R7 | Esposizione con tetti; leva contro 2x e 3x | parziale | P1-9 |
| R8 | Stress sulle quattro giornate | parziale | le quattro date ci sono; P0-3 e righe incomplete |
| R9 | Centro avvisi a tre gravità | parziale | presa in carico solo sulla riga critica |
| R10 | Blotter | manca | Sistema non migrato |
| E1 | Provenienza, mai statistiche mescolate | parziale | come G10 |
| E2 | Vista «Evidenza» | manca | non migrata |
| E3 | Riquadro della fortuna | manca | non migrato |
| E4 | Paper contro modello | manca | dato assente, nessuno stato vuoto in questi spazi |
| E5 | Confine scelta / verifica e avvio del paper | manca | nessun confine sulla curva del patrimonio |
| E6 | Ventaglio con il percorso vero; distribuzione della caduta | parziale | ventaglio sì, distribuzione no |
| E7 | Incertezza ovunque | parziale | «n = 5: troppo pochi» c'è; cancello Sharpe a 12 giorni no |
| E8 | Decadimento | manca | non migrato |
| E9 | Distribuzione di R | manca | Chiusi è solo una tabella |
| E10 | Log, caduta sotto la curva, assi comuni, tabelle esportabili | parziale | caduta sotto la curva e tabella sì; CSV e log predefinito no |

Totale: 2 fatti, 20 parziali, 8 mancanti (6 dei quali in spazi non ancora migrati).

## 6. I cinque cambi che alzano di più il valore

1. **Una sola verità.** Patrimonio totale definito con il costruttore, soglie e cancelli da una fonte sola, esempio generato da un'unica storia con test di coerenza, età per fonte che porta ogni riquadro in «sconosciuto» da solo.
2. **Righello del trade da professionista.** Livelli sempre in quadro, scala in R, distanze in % e ATR, stop mobile a gradini, giorno 7, mirino tradotto in R; grafico alto con i quattro riquadri e la legenda; libro con i totali contro i tetti.
3. **Terminale vero.** Nessuno scorrimento, dieci riquadri, selezione collegata; dentro ci vanno prossima chiusura, confronto con z e con S&P 500 e Bitcoin, tetti, dati per fonte.
4. **Rischio senza numeri doppi.** Tabella con tre scalini, 24 ore e 7 giorni sui valori mobili veri e la condizione di rientro; peggior caso con copertura dichiarata e una sola formula; stress con il freno che scatta; fascia con scala e motivo a 1440 e riga sopra il P&L quando non è NORMAL.
5. **Oggi che spiega e anticipa.** Attribuzione che torna al punto base con il libro dei trade e i tre strumenti migliori e peggiori; «che cosa è cambiato» per gravità con le differenze da ieri; vista delle 21:30.
