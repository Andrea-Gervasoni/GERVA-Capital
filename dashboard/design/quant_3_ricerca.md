# Quant 3 — Ricerca: il vantaggio è vero? Sta decadendo?

Posto: responsabile della ricerca quantitativa. Mi interessa una sola cosa: distinguere abilità, fortuna e decadimento, e non lasciare che un backtest venga letto come una storia vera. Contenuto, gerarchia e comportamento; nessuna indicazione di stile. `[DATI]` = oggi il fondo non ha quel dato.

## 1–2. Le domande, in ordine, con numeri, grafico e avvertenza

**D1. Il paper sta seguendo il backtest?** (per strategia e per il libro dei trade)
- Numeri: differenza cumulata paper − modello (pb e %), tracking error annualizzato, beta e correlazione del paper sul modello, costo per ordine in pb contro quello ipotizzato, giorni osservati. Una riga per CR-TREND, CR-XSMOM, EQ-MR, MA-TREND, libro dei trade, liquidità.
- Grafico: due curve (paper e modello rigiocato sugli stessi giorni) ribasate a 100 all'avvio del paper, asse log; sotto, stesso asse dei tempi, la differenza cumulata con la banda ±2σ attesa e la linea dello zero e della soglia del cancello. Accanto: barre della differenza per strategia, con n giorni su ogni barra.
- Avvertenza visibile: «Misura l'esecuzione, non il vantaggio. Con meno di 60 giorni lo Sharpe non si mostra; a 90 giorni il suo errore standard è circa 2».
- `[DATI]` serve il modello rigiocato giorno per giorno e per strategia (`gates.tracking` lo prevede, oggi è «da calcolare»).

**D2. Qualche strategia sta decadendo?**
- Numeri: Sharpe scelta | verifica | ultimi 12 mesi per strategia e portafoglio (libro giornaliero 1,68 | 1,20; media delle strategie 0,8 | 0,5); R medio per anno dei trade con n (2025: +0,01 R su 84; 2026: +0,14 su 50); ultimi 40 trade contro i precedenti (+0,21 contro +0,24, t −0,07); con costi doppi e ritardo di un giorno (portafoglio 1,18 → 0,97 → 0,83; EQ-MR 0,73 → 0,22).
- Grafico: piccoli multipli, uno per strategia, asse dei tempi comune: Sharpe mobile a 12 mesi con banda ±1,96 errori standard, linee a 0 e allo Sharpe dell'intero periodo, confine al 1° gennaio 2023. Sotto, CUSUM del rendimento meno l'atteso. Per i trade: barre di R per anno con barra d'errore e n.
- Avvertenza: «Uno Sharpe a 12 mesi ha errore standard circa 1: passare da 1,5 a 0,5 non è una prova. Le finestre si sovrappongono. Con 40 trade si vede solo una differenza superiore a circa 0,5 R» (mostrare la minima differenza rilevabile al posto di «nessun peggioramento evidente»).

**D3. Quanto del risultato può essere fortuna?**
- Numeri: prove contate 4.071 (per tornata: 110 → 812 → circa 2.500 → 4.071); Sharpe atteso dal migliore di N senza abilità 1,24; Sharpe osservato con errore standard (0,34): libro giornaliero 1,47 (verifica 1,21), fondo C3 1,20 (1,04), profilo del paper 1,27 (1,09); Deflated Sharpe 0,76 e 0,64 con la varianza teorica, circa 0,4 con quella empirica; soglia 0,95; PSR.
- Grafico: un solo asse orizzontale di Sharpe con la distribuzione del massimo di 4.071 prove a caso, la linea a 1,24 e i punti osservati con baffi ±1 errore standard (intero periodo e verifica, segni diversi). Sotto: barra del Deflated Sharpe da 0 a 1, mostrato come intervallo tra i due metodi, con la tacca a 0,95. A richiesta: curva «Sharpe atteso dal migliore» in funzione di N (asse x log) con il punto di ogni tornata.
- Avvertenza: «Sotto la soglia con entrambi i metodi: promettente, non provato. Il periodo di verifica è stato guardato da tutte le tornate successive: non è più un fuori campione vergine. Scenario centrale = metà del vantaggio misurato».
- `[DATI]` lo Sharpe di tutte le 4.071 prove non è in un registro unico (ci sono 65 + 36 nomi): la distribuzione empirica non si può disegnare.

**D4. Che cosa farebbe il profilo scelto in 1–3 anni?**
- Numeri, per scenario (base, pessimista, stress): rendimento annuo al 5°/50°/95° percentile (C3 base 13% / 57% / 131%), caduta tipica e al 95° (−18% / −33%), P(−30%), P(dimezzare) (0% base, 3,7% pessimista), mese composto, numero di percorsi e metodo.
- Grafico a ventaglio: x = mesi 0–36, y = patrimonio ribasato a 1 su scala log, bande 5–95 e 25–75 più mediana, linee al capitale iniziale e a 0,5; **sopra il ventaglio il percorso vero del paper dal giorno d'avvio**, con il percentile in cui si trova oggi. Accanto: distribuzione della caduta massima a 3 anni (istogramma e curva cumulata) con le verticali a −20 / −30 / −40% (gli scalini) e a −50%.
- Avvertenza: «Lo scenario è scritto accanto a ogni probabilità (per lo stesso profilo i documenti dicono 0–4% e 9–10%: cambia lo scenario). Cadute su dati mensili: su dati giornalieri sono più profonde (−18% diventa circa −30%). Si rimescolano 8,6 anni di una sola storia: ciò che non è nel campione non è nel ventaglio».
- `[DATI]` il Monte Carlo esiste per C1 e C3 e solo come percentili; manca per il profilo esatto del paper (2x, trade 0,5% / 1%, scalini 20/30/40) e mancano i percorsi.

**D5. Come si muovono insieme le strategie, ed è cambiato?**
- Numeri: matrice 6×6 (quattro strategie, libro dei trade, sistema originale) per intero periodo, scelta, verifica, ultimi 90 giorni; media fuori diagonale; correlazione nei giorni peggiori (5% di coda); guadagno da diversificazione (Sharpe medio 0,8 → portafoglio 1,46; in verifica 0,5 → 1,20).
- Grafico: mappa con il numero in ogni cella, scala divergente centrata sullo zero, selettore del periodo e una vista «differenza verifica − scelta». Sotto: correlazione mobile a 90 giorni per coppia (piccoli multipli, stesso asse dei tempi, banda ±0,2, confine al 2023, linea al valore dell'intero periodo).
- Avvertenza: «A 90 giorni l'errore è circa ±0,2. Crypto (7 giorni su 7) e azioni (chiusura) non sono sincrone: la correlazione giornaliera sottostima, mostrare anche la settimanale. Nelle crisi le correlazioni salgono».

**D6. Com'è fatta la distribuzione di R del libro dei trade, e da che cosa dipende?**
- Numeri: n 652 (77 l'anno, circa 50 indipendenti), R medio +0,24 e mediano, vincenti 43%, profit factor 1,45, payoff 1,91, t 3,47, serie perdente 17, caduta −21,4 R, VaR 95% −1,09 R; uscita a stop −0,51 R (388) contro a tempo +1,33 R (264); quota del totale portata dal 5% dei trade migliori; R medio senza i 5 migliori.
- Grafici: (a) istogramma di R a passi di 0,25 R con verticali a −1 R, 0, mediana e media; simulati e paper sovrapposti e normalizzati, mai sommati; interruttore per la curva cumulata. (b) «Da che cosa dipende»: una riga per fetta (livello di conviction, moneta, giorno, terzili di volatilità, trend di Bitcoin, funding, livello GQ, motivo d'uscita, anno), punto = R medio, baffo = intervallo al 90%, n a destra, linea verticale alla media generale, colonne scelta | verifica. (c) dispersione escursione contraria (MAE) contro R finale.
- Avvertenza: «La media la fanno pochi trade grandi. Con tante fette qualcuna sembra cattiva per caso: vale la soglia corretta per il numero di confronti. I trade su BTC, ETH e SOL si sovrappongono: il t di 3,47 sovrastima. Senza Solana lo Sharpe in verifica è 0,45, non 0,68».
- `[DATI]` MAE/MFE sono vuoti nei trade simulati; funding e trend di Bitcoin non sono nello storico dei trade.

**D7. Che cosa ha trovato, respinto e tenuto in ombra il ciclo di automiglioramento?**
- Numeri: ipotesi provate da sempre (K = 4) e soglia in vigore (t ≤ −max(2, √(2 ln K))); conteggi per stato (respinta, in ombra, promuovibile, attiva, ritirata); per regola: n e R medio dei trade colpiti contro gli altri in scelta e in verifica, t, anni in cui regge, sei controlli, R guadagnato o perso applicandola (prima regola: −10,4 R in scelta, −15,2 R in verifica); in ombra: trade colpiti su 20 richiesti.
- Grafico: registro come tabella ordinabile con i conteggi in testa; per regola, coppia di punti con intervallo (colpiti | altri) in due riquadri scelta | verifica; curva della soglia in funzione di K con il punto di oggi; per le regole in ombra, R cumulato dei trade colpiti e degli altri (solo paper) con l'avanzamento n/20.
- Avvertenza: «Respinta è l'esito normale. Le debolezze sono cercate sugli stessi 652 trade che poi le giudicano in scelta. Con 20 trade l'errore sulla media è circa 0,4 R: l'ombra filtra gli errori grossi, non prova un miglioramento».

**D8. Che cosa dice l'indicatore Gervasoni rispetto alla conviction?**
- Numeri: oggi, per moneta, valore e livello di GQ e di conviction, concordi o no; storico: correlazione 0,85; tabella 3×3 dei livelli con n e R medio per cella; in verifica +0,22 R contro +0,13, differenza +0,09 con intervallo al 90% da −0,06 a +0,25; 2025–2026 circa zero; giorni di disaccordo nel registro d'ombra e che cosa sarebbe successo.
- Grafico: prezzo giornaliero e, sotto, due pannelli con lo stesso asse dei tempi (conviction con soglie, GQ con soglie), giorni di disaccordo marcati; R cumulato di tre gruppi (solo GQ, solo conviction, entrambi) con n; tabella 3×3.
- Avvertenza: «In ombra: non decide nulla. Il vantaggio non è distinguibile da zero e viene tutto dalla distanza dal VWAP del mese. Le celle di disaccordo hanno pochi trade».

## 3. SIMULATO, PAPER, REALE: mai confondibili

1. La provenienza è un campo del dato (`sim` | `paper` | `live` | `esempio`), non un'etichetta della scheda: segue il numero in tabelle, suggerimenti, esportazioni e stampa.
2. Mai una curva unica che unisce backtest e paper. Sullo stesso asse: confine verticale «avvio del paper, gg/mm/aaaa», tratto diverso (non solo colore) e voce di legenda per ogni provenienza. Lo stesso per paper → reale.
3. Nessuna statistica su dati mescolati. Ogni cifra porta provenienza, periodo e n: «Sharpe 1,27 · SIMULATO · 2018–2026 · n giorni» accanto a «— · PAPER · 12 giorni: troppo pochi». Simulato e paper in colonne affiancate, mai in una riga «tutti».
4. Soglie minime: Sharpe non prima di 60 giorni, rendimento annualizzato non prima di 90; prima si mostra solo il cumulato, con i giorni che mancano.
5. «Track record» vale solo per il reale. Contatore sempre visibile: giorni simulati, giorni paper, giorni reali (oggi 0).
6. L'etichetta sta dentro l'area del grafico, così sopravvive a un ritaglio o a uno screenshot.
7. Accanto al simulato le ipotesi (costi, ritardo, sede); accanto al paper «esecuzioni ipotizzate, nessun ordine vero»: il paper non misura lo slittamento.

## 4. La vista «Evidenza»: due minuti davanti a un allocatore scettico

Una schermata, stampabile su una pagina, in quest'ordine di lettura:
1. Verdetto in una riga, a parole: «Promettente, non provato. Paper dal gg/mm, N giorni; reale 0 giorni».
2. Curva su scala log con caduta sotto: backtest (scelta | verifica al 1° gennaio 2023), poi paper con tratto diverso dentro il ventaglio atteso.
3. Fortuna: 4.071 prove; atteso dal migliore a caso 1,24; osservato 1,47 e 1,20 (verifica 1,21 e 1,04); Deflated Sharpe 0,4–0,76 contro 0,95.
4. Tenuta: Sharpe scelta | verifica per strategia; costi doppi e ritardo di un giorno (1,18 → 0,97 → 0,83).
5. Paper contro modello: differenza cumulata con banda; contro il sistema originale: z di oggi, soglie ±1,3, giorni mancanti (circa 1.550 per una prova).
6. Che cosa è stato scartato: il livello a 30x, la gestione attiva, l'universo ampio, i modelli statistici, otto classi nuove; una riga ciascuno.
7. Che cosa ci farebbe cambiare idea: z < −1,3 contro l'originale, scalini a −20 / −30 / −40%, cancelli paper → reale con lo stato di ognuno.

## 5. Requisiti di qualità dei grafici

- Scala log per ogni curva composta oltre un anno o oltre ×2; lineare solo a richiesta, con la scala dichiarata.
- Caduta sempre sotto la curva, stesso asse dei tempi, stesso mirino. Mirino sincronizzato tra tutti i grafici temporali della pagina.
- Confronti ribasati allo stesso giorno (dichiarato) e, quando si confrontano profili, anche a parità di volatilità.
- Confine scelta | verifica al 1° gennaio 2023 su ogni serie storica; avvio del paper come secondo confine.
- Dichiarati accanto a ogni cifra: annualizzazione (252 o 365 giorni, radice del tempo), frequenza (giornaliera o mensile), periodo, tasso privo di rischio, netto o lordo di costi e tasse.
- n su ogni barra e cella; barre d'errore o intervalli su ogni media; le fette con n < 30 attenuate e segnate.
- Nessun doppio asse, salvo prezzo e indicatore in pannelli separati con asse dei tempi comune. Gli assi delle barre partono da zero.
- Assi veri: una grandezza numerica (la leva) non va su un asse ordinale con i punti uniti da una linea.
- Piccoli multipli con la stessa scala y quando si confrontano strategie.
- Ogni grafico ha la sua tabella, esportabile in CSV con provenienza, periodo, n e data di generazione; cifre con decimali sensati (Sharpe a 2, probabilità con il numero di percorsi).

## 6. Priorità

**Dieci indispensabili**
1. Provenienza su ogni numero e mai statistiche mescolate (sezione 3).
2. Vista «Evidenza» come prima pagina della ricerca (sezione 4).
3. Riquadro della fortuna: 4.071 prove, 1,24, Deflated Sharpe come intervallo contro 0,95.
4. Paper contro modello, per strategia, con banda attesa e giorni osservati.
5. Confine scelta | verifica su ogni serie e colonne scelta | verifica in ogni tabella.
6. Ventaglio a 1–3 anni del profilo del paper con il percorso vero sovrapposto e la distribuzione della caduta con gli scalini.
7. Incertezza ovunque: errori standard, intervalli, n, minima differenza rilevabile.
8. Decadimento: Sharpe mobile con banda per strategia e R per anno con barre d'errore.
9. Distribuzione di R e grafico «da che cosa dipende» con soglia per confronti multipli.
10. Scala log, caduta sotto la curva, assi dei tempi comuni, annualizzazione dichiarata, tabelle esportabili.

**Dieci utili**
1. Correlazione mobile e matrice «verifica − scelta». 2. Correlazione di coda. 3. Curva della soglia in funzione di K nel ciclo di automiglioramento. 4. Tabella 3×3 GQ × conviction con R per cella. 5. Contributo dei trade migliori (R senza i primi 5). 6. CUSUM per strategia con soglia d'allarme. 7. Scomposizione del rendimento: diversificazione, leva, trade, cassa (AI «da misurare»). 8. Distribuzione empirica delle 4.071 prove `[DATI]`. 9. Slittamento reale per ordine contro l'ipotizzato `[DATI: solo dal reale]`. 10. Capacità e impatto sul prezzo per strategia `[DATI: nessun book]`.

**Cinque cose che le pagine di oggi sbagliano o non hanno**
1. «Leva per trade» segna ancora «Sostenuta» la riga a 30x ed elenca gli schemi a 30x, che la ricerca ha ritirato (in verifica +0,08 R sui prezzi veri); il grafico unisce con una linea righe ordinate «non in scala».
2. La prova contro la fortuna è a metà pagina, con un solo numero; i due metodi (0,4 e 0,76) non compaiono come intervallo.
3. Nessun confronto paper − modello: in Strategie ci sono due Sharpe affiancati, senza intervallo né differenza cumulata; il cancello dice «da calcolare».
4. Stime puntuali senza incertezza: R per anno senza barre d'errore, «t +3,47» come se i 652 trade fossero indipendenti, «nessun peggioramento evidente» su 40 trade, probabilità «0,0%» senza percorsi né scenario; «Tutti i trade» somma simulati e paper.
5. Una sola matrice di correlazione 4×4 sull'intero periodo; «Caduta massima» dei portafogli è mensile ma non lo dice; il ventaglio mostra il libro giornaliero per leva, non il profilo che gira in paper.

**Desideri che richiedono dati che il fondo non ha:** modello rigiocato per strategia sui giorni del paper; percorsi Monte Carlo del profilo del paper; registro unico degli Sharpe delle 4.071 prove; MAE/MFE, funding e trend di Bitcoin nello storico dei trade; esecuzioni vere (slittamento), book e tick; patrimonio più fitto di 15 minuti; contributo dell'AI (serve il secondo libro paper).
