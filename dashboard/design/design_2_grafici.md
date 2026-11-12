# Design 2 — Il linguaggio dei grafici

Esempio funzionante: `dashboard/design/charts_specimen.html` (un file solo, nessuna risorsa esterna, dati veri degli esempi incorporati, scuro per primo). Copia `tokens.glass.css` così com'è e vi aggiunge solo i ruoli `--chart-*` elencati al §8. Tutto SVG a mano: i colori stanno nelle classi CSS, quindi il tema cambia senza ridisegnare.

## 1. Grammatica

**Scheda.** Ogni grafico è una scheda di vetro con, in quest'ordine: occhiello (famiglia), **titolo = la domanda** a cui risponde, una riga «Come si legge» per il principiante, comandi (intervallo, periodo), riga dei valori chiave, area, piede con etichette di provenienza + unità, annualizzazione, periodo, n e fonte, e «Tabella dei dati» (`<details>` con `<table>`, intestazioni `scope`, didascalia con provenienza e n).

**Assi e griglia.** Un solo asse y per riquadro, mai doppio: grandezze diverse stanno in riquadri impilati con l'asse del tempo e il mirino in comune. Griglia = filetto pieno a `--grid`, mai tratteggiata; linea di base e zero a `--axis`. Tacche tonde (1-2-5), 4–6 per asse; etichette y dentro l'area in alto a sinistra della riga, oppure sul righello di destra quando ci sono cartellini di prezzo. Scala logaritmica per curve composte oltre ×1,7 (dichiarata nel piede); le barre partono da zero. Perdita e caduta crescono sempre **verso destra** (scala dei freni, istogramma delle cadute) o **verso il basso** (sott'acqua).

**Caratteri.** Testo dei grafici 11 px; cifre in `--font-num` con `--num-variant` (tabellari) ovunque; etichette in `--font-ui`; titoli di riquadro 10 px maiuscoletto spaziato. Il testo non prende mai il colore della serie: usa `--text`, `--text-2`, `--text-3`; l'identità la dà il segno accanto. Sopra i segni il testo ha un alone `--chart-halo`.

**Ruoli del colore** (uno per colore, mai due):
| Ruolo | Token | Dove |
|---|---|---|
| Su / giù | `--chart-up`, `--chart-down` (+ `-soft`) | candele, barre con segno, punti vinti/persi. Sempre con una seconda codifica: vuoto/pieno, segno, posizione |
| Nuovo sistema | `--chart-fund` (= `--accent`) | l'unica linea con l'alone (`.glow`), una per grafico |
| Sistema originale / benchmark | `--chart-orig` (ambra) / `--chart-bench` (grigio, più sottile) | confronti |
| Strategie | `--chart-c1…c4` (blu, rosa, giallo, ciano), `c5` inchiostro per il libro dei trade | ordine fisso CR-TREND, CR-XSMOM, EQ-MR, MA-TREND; il colore segue la strategia, mai il rango |
| Divergente | `--chart-div-1…9` + `-ink` (blu ↔ arancio, centro grigio visibile sul nero) | entrambe le mappe di calore |
| Stato | `--safe`, `--warn`, `--serious`, `--crit` (+ `-soft`) | zone dei freni, stop, liquidazione: sempre con parola o valore scritto |
| Neutro | `--chart-neutral` | indicatore in ombra, ATR, imbuto del caso |

**Spessori.** Serie viva (paper/reale) 2,25; serie 2; simulata e secondaria 1,5; livelli e medie 1,25; griglia 1. Estremi tondi, giunti tondi; gradini con estremi retti.

**Aree e fasce.** Sotto una linea: sfumatura dal colore al trasparente (`--chart-area-top` → 0), mai un blocco pieno. Fasce di percentili: `--chart-band-opacity` (5–95) e `-strong` (25–75). Zone e selezioni (tratto paper, zona 1 R, zone oltre uno scalino, fasce di conviction) = **lastra di vetro**: velo chiaro + filo di luce sul bordo alto (`.slab`). Aree impilate: riempimento all'82% con stacco di 2 px del colore di superficie tra le fasce.

**Segni.** Punto finale r 4,5 con anello di superficie; **anello vuoto = paper, pieno = reale**; ultimo valore vivo con alone che «respira». Rombo = uscita di un trade (pieno) o ipotesi (vuoto, tratteggiato). Barre con testa arrotondata 3–4 px, piede retto; celle con raggio 6 e stacco di 2 px. Dispersione: punto pieno = vinto, anello = perso, bersaglio di puntamento 24 px.

**Righe di riferimento.** Soglia = filetto **pieno** `--chart-rule` con il valore scritto al bordo (mai tratteggiata: il tratteggio è riservato alla provenienza). Confine temporale (scelta | verifica, avvio del paper, 90/180/365 giorni) = verticale piena con la scritta ai due lati. Livello non più attivo (stop iniziale) = puntinato fitto `--chart-dash-past`.

**Righello del trade** (grafico a): entrata = riga piena chiara + anello; stop iniziale = puntinato ambra; stop mobile = gradini ambra pieni; liquidazione = riga piena rossa; uscita = rombo colorato dal segno di R. Zona entrata–stop = lastra «1 R»; zona stop–liquidazione = lastra con il rapporto scritto. Scala in R accanto all'uscita; i livelli proseguono puntinati fino a un **cartellino sul righello di destra** (nome + prezzo), che non si sovrappone mai agli altri. I trade passati sono solo anello → rombo + R.

**Etichette dirette prima della legenda.** Fine linea, bordo del riquadro o cartellino; la riga dei valori sopra l'area fa da legenda minima e porta i numeri chiave. Mai un numero su ogni punto (eccezioni: celle delle mappe e blocchi, dove il numero è il dato).

**Incertezza.** Ogni media ha il baffo al 90% e **n scritto sulla riga**; n < 30 attenuato e segnato «*». Ogni simulazione dichiara percorsi, metodo e frequenza nel piede.

## 2. Schede dei grafici

| | Domanda | Codifica | Interazioni | Stati | Dati |
|---|---|---|---|---|---|
| a | Dov'è il prezzo rispetto ai livelli del trade? | Candele (vuota su, piena giù) + volume velato e media 20 g; VWAP che riparte ogni mese; MM 50 / 200; riquadri conviction (gradini, lastre 0,60 / 0,75), GQ (neutro, soglie −0,50 / 0,53 / 1,42, «in ombra»), ATR%; righello del trade | Mirino unico su 5 riquadri, scheda OHLC + segnali + R e distanze; intervalli Trade/1M/3M/6M/1A/Tutto con transizione; frecce ±1 barra, Maiusc ±10 | ETF: riquadri «non calcolato per questo strumento» | `/market/ohlc`, `/tradebook` (qui `sample_ohlc.json`, trade ricostruiti con le regole del libro) |
| b | Cresce più dell'originale e del mercato, e con quali cadute? | Linee a base 100 su log; simulato tratteggiato, paper pieno su lastra; nastro di provenienza in testa; confini scelta \| verifica e avvio del paper; sott'acqua sotto con −20 / −30 / −40 | Mirino unico sui due riquadri; Tutto / Dal 2023 / 1A / Paper (ribasa all'inizio dell'intervallo) | Benchmark assente: la serie non c'è, non è a zero | `quant_v4.json` `fund_curves`, `/compare` |
| c | Quanto manca a ogni freno, e dove arriva il peggior caso di oggi? | Una scala 0 → −46%: corsia della caduta con zone a lastre, tacche degli scalini con azione e rientro, punto «adesso», anello «peggiore in paper», riferimento simulato −21%; corsie 24 h e 7 gg con il loro freno; peggior caso = segmenti + rombo tratteggiato su tutte e tre | Tacche e segmenti puntabili: punti, €, giornate di ES, patrimonio a cui scatta | Dati fermi: stato «sconosciuto», mai l'ultimo verde | `risk.dd_ladder`, `risk.limits`, `/tradebook`; scenario di gap dichiarato |
| d | Da dove viene il risultato di oggi e del mese? | Cascata orizzontale da ieri = 0: barre su/giù, «Libro dei trade» n.d. puntinato, «Non attribuito» tratteggiato con avviso oltre 1 pb, totale neutro; € e pb | Oggi / Mese con trasformazione delle barre; barre puntabili | Riga n.d. scritta; scarto mostrato | `positions`, `strategies`, `nav` |
| e | Quali mesi hanno fatto l'anno? Le strategie si compensano? | Mappe anno × mese (+ colonna Anno) e matrice 4×4, stessa rampa divergente, valore con segno in ogni cella; mese in corso con bordo tratteggiato; mesi assenti puntinati | Celle puntabili; al telefono la mappa dei mesi si traspone | Cella senza dato = contorno puntinato | `monthly_returns`; `quant.json` `correlation` |
| f | Il paper va come previsto? Quanto in basso può scendere? | Ventaglio 5–95 e 25–75 + mediana tratteggiata, percorso paper bianco pieno sopra, percentile di oggi a parole; istogramma velato della caduta a 3 anni con scalini e quota oltre ciascuno | Mirino sul ventaglio; orizzonte 6 mesi / 1 anno / 3 anni; barre puntabili | Paper < 1 giorno: solo il ventaglio | `quant.json` `leverage_fan`, `/compare`; ricampionamento dichiarato |
| g | Batte davvero l'originale o è il caso? | Distacco cumulato a pari volatilità dentro l'imbuto ±1,3 e.s.·√giorni; confini 90/180/365; barra «giorni osservati / necessari»; esito a parole | Mirino: distacco, z, fascia; 180 giorni / 1 anno | < 3 giorni: «servono almeno 3 giorni comuni» | `/compare` (formula di `confronto.py`) |
| h | Come sono fatti i risultati dei trade, da che cosa dipendono, com'è il percorso? | Istogramma di R a classi 0,25 (zero, −1 R, media, mediana, n); R medio per fetta con baffi 90% e n; dispersione MAE × MFE; R cumulato a gradini | Barre, righe e punti puntabili; mirino sul cumulato | Paper a 0 trade: stato vuoto con «0 su 40» | `/trades/history` |
| i | Quale strategia tiene, quale decade? | Schede affiancate, stessa scala: andamento a 30 giorni (paper) + Sharpe mobile 52 settimane con banda ±1,96 e.s., zero, Sharpe intero, confine 2023 | Scheda che si solleva; cifre scelta \| verifica sotto | In pausa: etichetta con forma diversa | `strategies[].spark`, `quant.json` `sleeve_curves` |
| j | Come si sposta il peso? Dove sono i soldi rispetto ai tetti? | Area impilata al 100%; blocchi per sede → strategia → strumento sulla stessa scala, tacca del tetto di sede e del tetto per strumento, ribasso = blocco vuoto tratteggiato, utilizzo scritto | Mirino con le quattro quote; blocchi puntabili | Sede senza tetto: «nessun tetto di sede» | `quant.json` `weights`, `positions`, tetti di configurazione |

## 3. SIMULATO, PAPER, REALE, ESEMPIO: mai confondibili
1. La provenienza è il **tratto**, non il colore: ESEMPIO puntinato (`--chart-dash-demo`), SIMULATO tratteggiato 7·5 e più sottile, PAPER pieno con punto ad anello, REALE pieno più spesso con punto pieno. Nelle barre: simulato = **velato con contorno**, paper/reale = pieno.
2. L'etichetta sta **dentro l'area** (`ptag`, stessa forma delle `.tag`: bordo puntinato / tratteggiato / filetto / pieno) e di nuovo nel piede; la scheda dei valori la ripete accanto alla data.
3. Sullo stesso asse: nastro di provenienza in testa all'area, confine verticale «avvio del paper», lastra più chiara sotto il tratto paper, e uno stacco tra le due linee. Il paper riparte dal livello simulato (dichiarato), la sua caduta riparte da zero.
4. Mai una statistica su dati mescolati: simulato e paper in colonne o righe separate anche in tabella; distribuzioni sovrapposte e normalizzate, mai sommate.
5. Un'ipotesi (peggior caso, proiezione) usa lo stesso tratteggio del simulato ed è etichettata come tale.

## 4. Numeri
Formato italiano: virgola decimale, punto delle migliaia sempre (`1.234`), meno tipografico «−», segno sempre scritto su variazioni e contributi (`+1,98%`, `−0,65 R`). Percentuali a 2 decimali nelle cifre, 1 nelle etichette, 0 sugli assi; punti base interi oltre 10; prezzi senza decimali sopra 1.000; R a 2 decimali; Sharpe a 2; leva `15,0×`; date `19 ago 2026`, giorno della settimana solo nella scheda dei valori; migliaia abbreviate `26,5k` solo sugli assi. Dato assente = «n.d.» su contorno puntinato, mai zero. Soglie e tetti letti dallo snapshot o dalla configurazione, mai scritti nella pagina.

## 5. Movimento (tutto spento con `prefers-reduced-motion`: stato finale subito, 0 animazioni)
| Che cosa | Come | Durata, curva |
|---|---|---|
| Ingresso, una volta, quando la scheda entra nello schermo | Linee e aree scoperte da sinistra (ritaglio); barre che crescono dalla base, celle e punti che si posano, sfalsati di 14 ms; etichette in dissolvenza per ultime | `--chart-draw` (720 ms), `--ease-out`; barre `--ease-spring-soft` |
| Valore che cambia | Interpolazione dal valore vecchio al nuovo: segni e cifre scorrono insieme, stessa geometria, cifre tabellari → nessuno spostamento dell'impaginato (altezza della scheda misurata identica prima, durante, dopo) | `--chart-morph` (420 ms) |
| Cambio di intervallo o periodo | Il dominio scorre da A a B e gli assi si riadattano a ogni fotogramma; il mirino resta dov'è | `--chart-range` (420 ms), entra-esce |
| Mirino | Riga luminosa sottile agganciata alla barra; la scheda di vetro la segue con una breve inerzia; i numeri cambiano senza animazione | `--chart-cross` (90 ms) |
| Puntamento | Il segno puntato si accende, gli altri scendono a `--chart-dim`; le schede dei piccoli multipli si sollevano di `--lift` | `--dur-fast` |
| Punto vivo | Alone che si allarga e svanisce attorno all'ultimo valore | `--dur-breathe`, continuo |
| Dati che si ricaricano o fermi | Il disegno resta, al 45% e desaturato, con l'età scritta: niente scheletri | `--dur-fast` |
Niente cifre che lampeggiano: il patrimonio cambia ogni 15 minuti e lo schermo non finge altro.

## 6. Accessibilità misurata
- Daltonismo (OKLab ΔE×100, simulazione Machado; obiettivo ≥ 8): su/giù scuro 35 / 9,3 / 24 (normale / deuteranopia / protanopia), chiaro 31 / 8,9 / 16; strategie, tutte le coppie: minimo 12,5 scuro, 11,5 chiaro; nuovo-originale 35 / 35 / 29; rampa divergente, passi simmetrici ≥ 12 scuro e ≥ 10,6 chiaro.
- **`--pnl-*` di `tokens.glass.css` non passa**: i passi simmetrici rosso/verde distano 1,9–6,1 in deuteranopia. Per questo le mappe usano la rampa blu ↔ arancio; il verde/rosso resta ai segni che hanno anche forma e segno.
- Contrasto dei segni sul vetro scuro (#10131d e sul punto più chiaro #1a1f33): minimo 3,5:1 (`--crit`), gli altri ≥ 5,3:1. Testo: `--text-3` 6,8–7,8:1 scuro, 5,4–6,0:1 chiaro; cifre dentro i blocchi ≥ 4,7:1; cifre nelle celle ≥ 5,2:1 scuro, ≥ 4,5:1 chiaro (ogni passo della rampa ha il suo `-ink`).
- Tastiera: l'area è focalizzabile; frecce = mirino o segno successivo, Maiusc = 10 barre, Esc = chiude. Ogni valore del mirino è anche nella tabella.
- Telefono (390 px): nessuno scorrimento orizzontale; etichette accorciate, mappa dei mesi trasposta, scheda dei valori ancorata in alto dalla parte opposta al dito.

## 7. Che cosa mostrano le schermate
`dv-full-dark.png`, `dv-full-light.png` (1440), `dv-m-dark.png`, `dv-m-light.png` (390 @2x), più gli scatti per scheda e quelli di movimento, in `/tmp/claude-0/-home-user-GERVA-Capital/48f6139d-0078-5bc0-83e9-48c012a4ffa3/scratchpad/shots/`. Due giri di correzione: ritaglio per riquadro, cartellini che coprivano le tacche, collisioni sulla scala dei freni (rientri, peggior caso), etichette sopra le linee, scala dei blocchi oltre il 50%, traboccamento al telefono, comandi con transizione.

## 8. Token
**Usati da `tokens.glass.css`:** tipografia (`--font-ui`, `--font-num`, `--num-variant`, `--type-*`, `--fs-*`, `--tr-*`), spazio e raggi, ricette del vetro (`--glass-panel-*`, `--glass-raised-*`, `--glass-sheet-bg`, `--glass-edge`, `--glass-rim`, `--glass-sheen`, `--elev-*`), inchiostri e superfici (`--text*`, `--surface-solid`, `--surface-2/3`, `--border*`), `--accent*`, `--pos`, `--neg`, stati con `-ink` e `-soft`, provenienza `--prov-*` e `--hatch`, `--grid`, `--axis`, `--chart-dash-sim`, `--chart-dash-demo`, `--chart-band-opacity*`, durate e curve (`--dur-*`, `--ease-*`, `--lift`).
**Da aggiungere (definiti nello specimen, scuro / chiaro):**
- `--chart-up`, `--chart-down` = `--pos` / `--neg` nello scuro; nel chiaro segni più luminosi `#0a9a6e` / `#e0352b` (i `--pos` / `--neg` chiari sono inchiostri, troppo scuri come riempimento); `--chart-up-soft`, `--chart-down-soft`.
- `--chart-fund` (= `--accent`), `--chart-orig` `#ff9a3d` / `#c26a00`, `--chart-bench` `#8e96a6` / `#6f7888`.
- `--chart-c1…c5`: `#3b94ff #ff5fa8 #ffd23f #4cc9ff #e9edf5` / `#2a78d6 #c2439a #bd8600 #2f6d3a #0d1117` (le sole quattro che passano a tutte le coppie; `--s1…s8` passano solo tra vicini).
- `--chart-div-1…9` e `-ink` (valori nel file): sostituiscono `--div-*` e `--pnl-*` nelle mappe; il centro `#3a404d` resta visibile sul nero.
- `--chart-neutral`, `--chart-neutral-soft`, `--chart-rule` (+ `-opacity`), `--chart-halo`, `--chart-on-fill`, `--chart-block-opacity`, `--chart-slab`, `--chart-slab-edge`, `--chart-cross-line`, `--chart-dim`.
- `--chart-glow-a`, `--chart-glow-r` (alone per colori diversi dall'accento; per l'accento va bene `--glow-line`), `--chart-area-top`, `--chart-area-bottom`.
- `--chart-line-width-strong` 2,25, `--chart-dash-past` `2 3`, `--chart-draw`, `--chart-morph`, `--chart-range`, `--chart-cross`.
**Da cambiare:** `--chart-dash-ref` e `--chart-dash-cross` oggi sono tratteggi: soglie e mirino devono essere pieni, perché il tratteggio vuol dire «simulato». `--warn` e `--chart-c3` sono quasi lo stesso giallo (ΔE 4): non usarli nello stesso grafico senza parola scritta.

## 9. Questioni aperte per il costruttore
1. Lo specimen ridisegna l'SVG a ogni fotogramma di una transizione: va bene fino a ~500 barre; oltre, candele su canvas con lo stesso tema o barre settimanali.
2. `pnl_mtd_pct` per strategia: su quale capitale? Finché non è deciso la cascata del mese mostra uno scarto di ~100 pb. Il libro dei trade non è nello snapshot: riga «n.d.».
3. Mancano le serie per: curva simulata e percorsi Monte Carlo del profilo esatto del paper (qui C1 e leva 2); MAE/MFE nello storico (qui ricostruiti dalle barre, 57 trade su 160); benchmark lungo; esposizione storica (qui le quote di rischio simulate); scenario di gap calcolato dal motore.
4. I trade sul grafico a sono ricostruiti dalle barre d'esempio perché `sample_tradebook.json` ha prezzi incoerenti con `sample_ohlc.json` (entrata 74.120 con BTC a 80.900).
5. Non fatto: modalità misura, confronto di due strumenti, trascinamento e zoom, esportazione CSV, trama per `forced-colors` e stampa, annuncio dei valori del mirino a chi usa un lettore di schermo (oggi `aria-live` sulla scheda).
6. Il tema chiaro è stato controllato ma è secondario: i colori delle strategie chiare e l'alone spento vanno rivisti quando `tokens.glass.css` chiaro è definitivo.
