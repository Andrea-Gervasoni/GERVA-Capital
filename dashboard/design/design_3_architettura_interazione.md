# Design 3 — Architettura dell'informazione e interazione

Tavole in scala: `wireframes.html` (Oggi Semplice e Terminale, Mercati, Rischio, Evidenza, tavolozza, Oggi a 390 px, fascia e KILL). Materiali, colori e durate sono quelli di `tokens.glass.css`: qui si citano per nome. **Il tema scuro è il predefinito a ogni livello** (nero, vetro vero, colori vivi); il chiaro è secondario, a scelta dell'utente o del sistema. Sigle: **G** = gestore (quant 1), **R** = rischio e trading (quant 2), **E** = ricerca (quant 3); `-I` indispensabile, `-U` utile.

## a. Struttura: sette spazi, due gruppi
Il gestore chiede gerarchia «tra ciò che si guarda ogni giorno e ciò che si guarda una volta al mese» (G, errore 5): il binario ha due gruppi.

| Spazio | Domanda a cui risponde | Schede interne | Pagine di oggi che assorbe |
|---|---|---|---|
| **Oggi** (ogni giorno) | Guadagno? Qualcosa è rotto o frenato? Perché? Quanto manca al freno? | nessuna: una sola schermata | Panoramica; la conviction del giorno di AI |
| **Mercati** | Che cosa fa lo strumento, dove sono i livelli del trade? | Elenco · Grafico · Libro dei trade (Aperti, Chiusi, Decisioni) | nuova; la parte operativa di «Leva per trade»; regime e conviction di AI |
| **Portafoglio** | Da dove viene il risultato, che cosa ho in mano? | Attribuzione · Risultato (curva, mesi × anni, mercati) · Posizioni · Strategie | Performance, Strategie, Esposizione (composizione), overlay di AI («Freni dell'AI» accanto a ogni strategia) |
| **Rischio** | Che cosa può andare storto e chi frena? | Freni · Tetti · Stress · Dati e ordini · Statistiche (ancore di una pagina sola) | Rischio, Esposizione (contro i tetti) |
| **Evidenza** (quando serve) | Il vantaggio è vero? | Verdetto · Decadimento · Distribuzione di R · Correlazioni · Indicatore GQ · Archivio della ricerca | Ricerca; la tabella di «Leva per trade» (in Archivio, con la riga a 30x segnata «ritirata») |
| **Apprendimento** | Che cosa ha provato, respinto, tenuto in ombra il ciclo? | Registro · In ombra · Attive · Come impara | Apprendimento |
| **Sistema** | La macchina gira? Quanto manca al denaro reale? | Salute (il diagramma di «Come funziona» con lo stato vivo su ogni nodo) · Ordini · Cancelli · Registro | Sistema, Ordini, Come funziona (la parte didattica va nella Guida, sezione g) |

Perché così: il rischio chiede che il libro a 11x non sia una pagina di ricerca (R, errori 3–4) → sta in Mercati e Rischio, la ricerca in Archivio. La ricerca chiede «Evidenza» come prima pagina (E-I2). Il gestore chiede che tabelle di stop, portafogli A…C6 e Monte Carlo escano dal menu (G §5) → Archivio. Dodici voci diventano sette, e quattro bastano ogni giorno.

## b. Tre livelli, un solo disegno
| | Semplice | Esperto | Terminale |
|---|---|---|---|
| Aggiunge | frase per pagina e per riquadro, stati a parole, un numero protagonista, un grafico | colonne, σ, errori standard, n, schede e grafici secondari, note di metodo; le frasi si chiudono in «?» | più riquadri per schermo, nessuno scorrimento di pagina, selezione collegata tra riquadri, riga dei comandi, tutte le colonne |
| Riquadri sopra la piega (1440 × 900) | 5 (uno grande + 4) | 7 | 10 (12 da 1920) |
| Margine · distanza · interno | `--page-gutter` 29 · `--gap-grid` 20 · `--pad-card` 27 | uguale; interno 20 | 14 · 14 · 16 (minimi assoluti) |
| Binario | 236 (`--rail-w`) | 236 | 64, solo icone |

**Non cambia mai:** il tema (scuro predefinito) e il fondale visibile tra i riquadri; fascia di stato e posizione del KILL; valori, arrotondamenti e provenienza di ogni cifra; ordine di lettura dei riquadri; semantica dei colori; materiali (`--glass-panel-*`, `--glass-chrome-*`, `--glass-sheet-*`), raggi, caratteri; indirizzi (`#/spazio/scheda?s=BTC`). Terminale non è un tema: è lo stesso riquadro con meno testo e più vicini. Il livello è una preferenza del browser, si cambia dal binario o con `l`.

## c. Fascia di stato, KILL, provenienza
**Fascia**: una capsula di vetro che galleggia (materiale cromatura `--glass-chrome-*`, alta `--topbar-h` 60, raggio `--radius-xl`, staccata 14 dal bordo); il contenuto le scorre sotto e resta intravisto; non è mai coperta né attenuata da fogli o tavolozza. Ordine fisso da sinistra: (1) modalità `PAPER · giorno 24 di 90` oppure `ESEMPIO`; (2) stato del rischio come pastiglia + scala (1 / 0,5 / 0,25 / 0) + motivo + da quando + condizione di rientro; (3) età dei dati e prossimo ciclo; (4) sistema, solo se non tutto ok (`7 di 8 · dati crypto lenti`); (5) avvisi con contatore; (6) KILL. A 1024 il motivo si accorcia; a 768 e 390 restano modalità, stato, età, KILL e il motivo scende in seconda riga.
- Dati fermi oltre `stale_after_s` oppure offline: lo stato diventa **SCONOSCIUTO** (pastiglia tratteggiata `--unknown-*`, «ultimo visto: NORMAL alle 14:45»), i numeri sotto si attenuano. Mai l'ultimo «sicuro» visto (R-I1).
- Critico (HALTED, KILLED, dati oltre l'età massima, ordine non riconciliato): la fascia cresce di una riga in ogni spazio con che cosa è successo, che cosa ha già fatto il motore, che cosa devi fare tu; «Prendi in carico» (`x`) la riduce a «preso in carico alle hh:mm» finché la condizione dura. KILLED è l'unico stato a fondo pieno (`--killed-bg`).
- **KILL**: estremo destro della fascia, stessa posizione a ogni larghezza (a 390: bottone 44 × 44). Dice prima se è utilizzabile: «pronto», «spento su questo server», «già attivo». Apre solo il foglio (`Maiusc`+`K` apre, non invia): anteprima degli effetti (quante posizioni, quale controvalore, entro quando, che cosa non fa, come si riparte), token, parola KILL, motivo; fuoco iniziale su «Annulla», `Invio` non invia dal campo del token, `Esc` chiude e svuota. Dopo: «Richiesto» → «Eseguito: N posizioni alle hh:mm» oppure «NON attivato». Nessun «annulla KILL». In Rischio c'è solo un rimando.
- **Provenienza** (SIMULATO / PAPER / REALE / ESEMPIO, `--prov-*`): è un campo del dato, non una decorazione. Cinque regole: (1) eredità: l'etichetta sta al livello più alto in cui è omogenea (fascia → riquadro → colonna → cella); (2) la forma del bordo la distingue senza colore: tratteggiato SIMULATO, pieno PAPER, fondo pieno REALE, puntinato con tratteggio diagonale ESEMPIO; (3) dentro ogni grafico un'etichetta nell'area del tracciato e un tratto per provenienza (`--chart-dash-sim`, `--chart-dash-demo`, pieno per paper e reale), con il confine verticale «avvio del paper»; (4) paper e simulato mai nella stessa cifra né nella stessa riga «tutti»: colonne affiancate; (5) contatore «giorni simulati · paper · reali» sempre visibile al piede del binario e accanto al verdetto in Evidenza; segue il numero anche in suggerimenti, CSV e stampa.

## d. Griglia, punti di rottura, scorrimento
Griglia a 12 colonne dentro la colonna dei contenuti (larga 1.141 a 1440, massimo 1.560 come lo specimen). Larghezze di prova e comportamento (le soglie CSS sono quelle dello specimen: 1180, 860, 520):

| Larghezza | Binario | Colonne | Taglie del riquadro (XL · L · M · S) | Note |
|---|---|---|---|---|
| ≥ 1440 | 236 (64 in Terminale) | 12 | 12 · 8 · 6 o 4 · 3 | altezze di riga 324 / 284 / 232 in Semplice; 246 / 246 / 236 in Terminale |
| 1024 | 64, solo icone | 8 | 8 · 8 · 4 · 4 | Terminale scende a 6 riquadri sopra la piega; il grafico di Mercati va sopra l'elenco |
| 768 | capsula in basso | 4 | 4 · 4 · 4 · 2 | Terminale non disponibile: ricade su Esperto e lo dice |
| 390 | capsula in basso (4 spazi + «Altro») | 1 | tutte 1 | margine 16, distanza 16, interno 16; tabelle → schede a righe; bersagli 44 (`--control-h-lg`) |

Un «workspace» è un elenco ordinato di riquadri con una taglia: al restringersi i riquadri vanno a capo **nell'ordine di lettura**, non si rimpiccioliscono sotto la taglia S e non cambiano mai di ordine. Che cosa resta fermo: fascia e binario (o barra in basso), intestazioni di tabella, riga di lettura del grafico. Che cosa scorre: la pagina in Semplice ed Esperto, sotto la fascia; in Terminale solo l'interno di tabelle ed elenchi.

**Cromature che galleggiano, fondale che si vede.** Binario, fascia, barra del telefono e riga dei comandi sono capsule di vetro staccate 14 dal bordo e tra loro; fogli e tavolozza sono vetro più spesso (`--glass-sheet-*`). È lo spazio tra i riquadri a far leggere il vetro, quindi è un vincolo di layout e non un lusso: nessun riquadro tocca un altro riquadro, una cromatura o il bordo; nessun riquadro a tutta larghezza senza margine; dentro un riquadro i sotto-riquadri (grafico, tabella) non hanno un secondo vetro. Aria minima, a ogni livello: 16 dentro il riquadro, 14 tra riquadri, 14 dal bordo; mai due cifre protagoniste nello stesso riquadro; una sola cifra eroe per schermata (`--fs-hero`).

## e. Navigazione, tavolozza, tastiera
- **Binario**: «Ogni giorno» (Oggi, Mercati, Portafoglio, Rischio) e «Quando serve» (Evidenza, Apprendimento, Sistema); sotto: Cerca, Glossario e guida, livello di lettura, contatore di provenienza. Un punto di attenzione sulla voce il cui spazio ha un avviso.
- **Tavolozza** (`/` oppure `Ctrl`/`Cmd`+`K`; foglio `--glass-sheet-*` largo 680): quattro gruppi in ordine fisso — strumenti (aprono Mercati), spazi e riquadri, termini del glossario (aprono la definizione), azioni di sola navigazione (cambia livello o tema, apri avvisi, apri la finestra KILL che non invia, esporta il CSV del riquadro attivo). Nessuna voce scrive. `↑` `↓` scelgono, `Invio` apre, `Tab` salta al gruppo successivo, `Esc` chiude e rende il fuoco a dove era.
- **Mappa dei tasti** (le dodici del rischio, con due modifiche dichiarate tra i conflitti):

| Tasto | Che cosa fa | Tasto | Che cosa fa |
|---|---|---|---|
| `/`, `Ctrl`/`Cmd`+`K` | tavolozza | `+` `−` `0` | zoom e ripristino |
| `g` poi `o m p r e a s` | vai allo spazio; `g t` libro dei trade, `g b` ordini | `c` · `m` | confronto · misura |
| `j` `k` | riga successiva / precedente; il grafico segue | `[` `]` | trade precedente / successivo |
| `Invio` · `Esc` | apre la riga · chiude, torna, toglie il mirino | `a` · `x` | centro avvisi · prende in carico |
| `←` `→` (`Maiusc` × 10) | mirino di una barra | `i` · `l` | «Che cosa significa?» del riquadro · livello |
| `1`…`5` | intervalli 1M 3M 6M 1A Tutto | `?` · `Maiusc`+`K` | scorciatoie · apre la finestra KILL |

- **Ordine del fuoco**: salta al contenuto → fascia (stato, avvisi, KILL) → binario → titolo dello spazio → riquadri in ordine di lettura (`Tab` entra nel riquadro, `F6` salta al successivo) → dentro il riquadro: controlli, poi grafico (frecce), poi tabella. I tasti a lettera singola sono spenti mentre si scrive in un campo. Anello `--focus-ring` sempre visibile.
- **Tocco**: niente gesti nascosti. Tocco = seleziona; tocco lungo sul grafico = mirino; due dita = zoom; popover, glossario, avvisi e KILL diventano fogli dal basso; nessuna azione solo al passaggio del puntatore.

## f. Coreografia del movimento (durate e curve per nome)
Il movimento è parte del prodotto, non una rifinitura: dice dove si va, che cosa è vivo e che cosa è cambiato. Tre piani: **ambiente** (il fondale), **struttura** (spazi, riquadri, fogli), **dato** (cifre e stati). I nomi sono quelli di `tokens.glass.css`; i tre segnati *nuovo* vanno aggiunti dal designer visivo.

| Momento | Che cosa si muove | Token |
|---|---|---|
| Fondale | le macchie di colore dietro il vetro derivano lentissime, fuori fase; si fermano a scheda nascosta e mentre si trascina un grafico | *nuovo* `--dur-drift` (circa 60 s per ciclo), lineare |
| Cambio di spazio | molla: il contenuto uscente arretra (scala 0,985) e sfuma; i riquadri entranti arrivano da 12 px, **da sfocati a nitidi**, in sequenza nell'ordine di lettura (al massimo 8, poi insieme); fascia e binario fermi; la goccia di vetro del binario scivola sulla nuova voce | uscita `--dur-fast` `--ease-in`; entrata `--dur-slow` `--ease-spring-soft` con `--stagger`; sfocatura iniziale *nuovo* `--blur-enter` (8 px); goccia `--dur-base` `--ease-spring` |
| Segmentati (livello, intervalli, schede) | il cursore di vetro si allunga verso la nuova voce e si ricompone (morphing); il contenuto sotto sfuma soltanto | `--dur-base` `--ease-spring` |
| Cambio di livello | i riquadri cambiano misura e posto sul piano, senza ricaricare; il testo che entra o esce sfuma | `--dur-slow` `--ease-standard` |
| Cifra che cambia (al ciclo, ogni 15 minuti) | rotolano solo le cifre cambiate, verso l'alto se cresce e verso il basso se cala; nessun lampo verde o rosso | `--dur-slower` `--ease-out` |
| Valore vivo | il punto «dati di adesso» nella fascia e l'ultimo punto delle curve respirano piano (opacità 0,6 → 1). **Respira solo ciò che è fresco**: con dati fermi il respiro si ferma, ed è il primo segnale che qualcosa non va | *nuovo* `--dur-breathe` (circa 3,2 s) |
| Foglio, popover, tavolozza | vetro spesso che nasce dal punto che lo ha aperto (`--sheet-from-scale`, `--sheet-from-y`), il fondo si attenua e si sfoca; chiusura più breve, senza molla | `--dur-slow` `--ease-spring`; chiusura `--dur-fast` `--ease-in` |
| Riquadro sotto il puntatore o a fuoco | si solleva (`--lift`) e passa al vetro rialzato; alla pressione `--press-scale` | `--dur-fast`; pressione `--dur-instant` |
| Stato NORMAL → REDUCED | una volta sola: la fascia prende la tinta `--warn-soft`, un riflesso la attraversa, la pastiglia si allarga per mostrare motivo e scala; poi tutto fermo, con icona, parola e scala diverse (il colore non è l'unico segno) | tinta `--dur-slow`; riflesso `--dur-sweep`, una volta |
| Stato → HALTED / KILLED | la fascia cresce di una riga con una molla e resta; titolo della scheda del browser; suono solo se scelto | `--dur-slow` `--ease-spring-soft` |
| Rientro a NORMAL | la tinta si spegne senza festa; una riga nel registro | `--dur-slow` |
| Caricamento | sagome di vetro con la misura finale (nessun salto di layout); il bagliore passa per 3 secondi, poi sagoma ferma con «in attesa dei dati» | `--dur-shimmer` |
| Grafico al primo ingresso | la linea si traccia una volta, le barre crescono dallo zero; ai cambi di intervallo solo dissolvenza | `--dur-slower`; poi `--dur-fade` |

**Non si anima mai:** prezzi e cifre sotto il mirino o nella riga di lettura; il grafico mentre l'utente trascina o ingrandisce (segue il dito, senza inerzia); le righe di una tabella ordinata dall'utente (scatto immediato; cambia solo la freccia); il riordino dovuto ai dati mentre una riga è a fuoco o sotto il puntatore (si applica dopo, con la pastiglia «ordine aggiornato»); le cifre a ogni lettura da 5 secondi se il valore non è cambiato; il conto alla rovescia; la finestra KILL (solo dissolvenza: nessuna molla su un comando irreversibile); candele e livelli del trade; nulla che lampeggi. Gli unici cicli continui sono fondale e respiro, e nessuno dei due tocca un numero. In Terminale il fondale deriva a metà velocità e gli ingressi non hanno sequenza: chi usa la tastiera non aspetta.
**Riduci movimento** (`--motion-on: 0`): restano solo dissolvenze `--dur-fade`; fondale fermo, niente respiro, molle, sequenze, sfocature d'ingresso, rotoli, riflessi, bagliori; i cambi di stato si affidano a icona, parola e annuncio `aria-live`. **Riduci trasparenza** (`--glass-on: 0`): superfici piene `--glass-*-solid` con filetto e ombra, fondale uniforme, nessuna sfocatura né d'ingresso né dei fogli; la gerarchia resta la stessa.

## g. Spiegazioni senza ingombro
- **«In una frase»**: una riga sotto il titolo di ogni spazio, generata dai dati. Semplice: sempre aperta. Esperto: chiusa in una pastiglia accanto al titolo. Terminale: tasto `i`.
- **Frase del riquadro** (le dieci del gestore, G §6): una riga sotto il titolo, al massimo 90 caratteri, solo in Semplice.
- **«Che cosa significa?»**: popover ancorato al «?» nell'intestazione del riquadro, a ogni livello (testo esteso in Semplice, icona negli altri): che cosa mostra, come si legge, che cosa è bene e male, da dove viene il dato. Mai testo esplicativo più lungo dei numeri nel riquadro.
- **Glossario e guida**: un foglio laterale (dal basso su telefono) con tre schede — Guida («Come funziona» in sette passi), Glossario, Scorciatoie. Si apre dal binario, da `?`, dalla tavolozza e toccando un termine sottolineato a puntini.

## h. Stati vuoti, fermi, offline, errore
Regola comune: il riquadro tiene la sua misura; dice che cosa manca, perché e quando arriverà; mai uno zero o una stima al posto di un dato assente; con dati fermi le cifre restano leggibili ma attenuate e la fascia dice SCONOSCIUTO; offline non cancella l'ultima fotografia, la data.

| Spazio | Vuoto | Dati fermi / offline | Errore |
|---|---|---|---|
| Oggi | «Nulla è cambiato»; «Nessun trade aperto: oggi la conviction è media» | cifre attenuate, età in evidenza, frase «Non so dirti com'è adesso: i dati sono fermi da 14 minuti» | la somma delle voci non torna (> 1 pb): riga «non attribuito» in evidenza |
| Mercati | ETF: «conviction e GQ non calcolati per questo strumento»; «Nessun trade chiuso in paper» | «ultima barra chiusa: data» sempre scritta; fonte oltre l'età massima segnata sulla riga | strumento senza barre: il grafico resta con assi vuoti e motivo |
| Portafoglio | «Nessuna posizione: il fondo è in liquidità» | pesi attenuati | strategia senza serie: riga con «—» e motivo |
| Rischio | Stress: «manca la tabella degli shock»; «Nessun limite sopra il 60%» | ogni distanza diventa «sconosciuta»; mai barre verdi su dati vecchi | soglia assente in configurazione: «soglia non letta», mai un valore predefinito |
| Evidenza | «Paper contro modello: da calcolare»; «Sharpe: — · 24 giorni su 60» | ricerca più vecchia della fotografia: data di generazione nel verdetto | file di ricerca illeggibile: lo spazio resta, i riquadri lo dicono |
| Apprendimento | «Nessuna regola in ombra»; «Respinta è l'esito normale» | data del rapporto | rapporto mancante: comando per generarlo, nessun pulsante |
| Sistema | «Nessun ordine oggi»; «Nessun avviso» | battito assente = critico in fascia | componente senza «ultimo ok»: «mai visto» |

## i. Tracciabilità: dove vive ogni «indispensabile»
| # | Richiesta | Spazio · riquadro · livello | Dato |
|---|---|---|---|
| G-I1 | Patrimonio totale (due libri), P&L in €, %, σ, mese, anno, avvio | Oggi · Patrimonio · S/E/T (σ a parole in S) | c'è; il totale richiede `/tradebook` e la conferma che il patrimonio della fotografia non lo includa già |
| G-I2 | Riga di stato unica, sopra il P&L se qualcosa non va | Fascia di stato · ovunque; componenti in Sistema · Salute | c'è |
| G-I3 | Cascata per strategia e libro con «non attribuito» | Oggi · Da dove viene il risultato; Portafoglio · Attribuzione (pb in E/T) | oggi, mese, avvio: c'è. Manca: anno per strategia; costi come voce; base dichiarata di `pnl_*_pct` |
| G-I4 | Scala della caduta con gli scalini veri | Oggi · Quanto manca ai freni; Rischio · Stato e freni | c'è, ma le soglie vanno lette da una fonte sola (l'esempio ha valori vecchi) |
| G-I5 | Cono dell'atteso con il paper sopra | Oggi · Atteso contro reale; Evidenza · Come sarebbe andato | manca il Monte Carlo del profilo esatto del paper: fino ad allora fascia del profilo C3, dichiarata |
| G-I6 | Imbuto del distacco, z, giorni comuni e necessari, esito | Oggi · Confronto con l'originale (esito a parole in S); Evidenza · Contro l'originale | `/compare` dà le righe; z, giorni ed esito vanno restituiti dall'endpoint o ricalcolati con un test contro `confronto.py` |
| G-I7 | Contro S&P 500 e Bitcoin, con i beta | Oggi · Contro i mercati (T); Portafoglio · Risultato (E) | `/compare`; Sharpe e volatilità solo da 60 giorni |
| G-I8 | «Che cosa è cambiato da ieri», al massimo 8 righe | Oggi · Che cosa è cambiato (3 righe in S, 8 in E/T) | ordini, avvisi, trade, overlay attuale: c'è. Manca lo storico di stati del rischio e freni dell'AI |
| G-I9 | Trade aperti: righello, R, margine a rischio | Oggi · Trade a leva aperti; Mercati · Libro dei trade | `/tradebook`; il prezzo è l'ultima barra chiusa e lo si scrive |
| G-I10 | SIMULATO, PAPER o DEMO su ogni numero | sistema di provenienza (sezione c) · ovunque | c'è |
| R-I1 | Fascia fissa: stato, scala, motivo, da quando, rientro, età; «sconosciuto» | Fascia di stato | manca «da quando» e la condizione di rientro nella fotografia: campo «n.d.» finché non arrivano |
| R-I2 | Scala dei freni unica con 24 ore e 7 giorni, in punti, € e giornate di ES | Rischio · Stato e freni (E/T); sintesi in Oggi | manca il patrimonio di riferimento a 24 ore e 7 giorni |
| R-I3 | Peggior caso di oggi proiettato sulla scala | Rischio · Il peggio di oggi; riga in Oggi · Freni (T) | margini e stop da `/tradebook`; il gap del libro giornaliero è uno scenario dichiarato, SIMULATO |
| R-I4 | KILL ovunque, due passi, anteprima, conferma | Fascia + foglio KILL | c'è; da confermare con il costruttore che cosa succede ai trade a margine aperti |
| R-I5 | Candele con volume, conviction, GQ, ATR, VWAP e livelli del trade | Mercati · Grafico (riquadri sotto chiudibili) | `/market/ohlc`; le medie usate dalle strategie vanno dichiarate (in mancanza 50 e 200) |
| R-I6 | Libro dei trade con distanze, R, MAE/MFE, giorni, funding, totali contro tetti | Mercati · Libro dei trade (9 colonne in E, tutte in T) | `/tradebook`; funding «stimato» |
| R-I7 | Esposizione con i tetti disegnati; leva contro 2x e 3x | Rischio · Tetti di esposizione, Leva e volatilità | c'è; manca la serie a 90 giorni della leva |
| R-I8 | Stress sulle quattro giornate storiche | Rischio · Stress | **non realizzabile oggi: manca la tabella degli shock per strumento (chiusura e minimo)**; stato vuoto esplicito |
| R-I9 | Centro avvisi a tre gravità, presa in carico | foglio Avvisi dalla fascia (`a`); critici nella fascia | c'è; la presa in carico resta nel browser (una seconda scrittura è vietata) |
| R-I10 | Blotter: non riconciliati, rifiuti per motivo, costi | Sistema · Ordini | c'è; slittamento e costi reali: «non misurabile in paper interno» |
| E-I1 | Provenienza su ogni numero, mai statistiche mescolate | sezione c · ovunque | c'è |
| E-I2 | «Evidenza» come prima pagina della ricerca | Evidenza · Verdetto | c'è |
| E-I3 | Fortuna: 4.071 prove, 1,24, Deflated Sharpe come intervallo | Evidenza · Quanto può essere fortuna | c'è; la distribuzione empirica delle prove manca (si disegna quella teorica, dichiarata) |
| E-I4 | Paper contro modello, per strategia, con banda | Evidenza · Paper contro modello | **non realizzabile oggi: manca il modello rigiocato sui giorni del paper**; stato vuoto |
| E-I5 | Confine scelta / verifica su ogni serie e tabella | regola di ogni grafico storico; colonne in Evidenza e Portafoglio · Strategie | c'è |
| E-I6 | Ventaglio a 1–3 anni con il percorso vero; distribuzione della caduta con gli scalini | Evidenza · Come sarebbe andato + Archivio · Proiezione | solo percentili di C1 e C3: manca il profilo del paper e i percorsi |
| E-I7 | Incertezza ovunque: errori, intervalli, n, minima differenza rilevabile | ogni media in E/T; in S a parole («troppo presto per dirlo») | c'è dove la ricerca la calcola |
| E-I8 | Decadimento: Sharpe mobile con banda, R per anno con barre d'errore | Evidenza · Decadimento | c'è |
| E-I9 | Distribuzione di R e «da che cosa dipende» | Evidenza · Distribuzione di R; sintesi in Mercati · Chiusi | `/trades/history`; MAE/MFE, funding e trend di Bitcoin mancano nei simulati |
| E-I10 | Scala log, caduta sotto la curva, assi comuni, tabelle esportabili | regola di ogni riquadro: menu «Tabella · CSV» | c'è |

**Utili, in breve.** Gestore: mesi × anni e barre del mese → Portafoglio · Risultato; Sharpe live / backtest / verifica → Portafoglio · Strategie (da 60 giorni, con l'errore); vista delle 21:30 → Oggi · Prossima chiusura; candele → Mercati; esposizione con limite → Rischio · Tetti; dispersione MAE–R → Evidenza. *Mancano i dati per:* curva a 15 minuti, correlazione mobile live, registro dei freni dell'AI con l'esito, costi per sede. Rischio: confronto di due strumenti (`c`), misura (`m`), calcolatore «se aprisse oggi», griglia di shock (calcolata in pagina, SIMULATO), scadenze in una riga, CSV → Mercati, Rischio, Oggi; replay di un trade → incremento 5. *Mancano:* nastro degli stati, nastro dei cicli, contributo al VaR. Ricerca: correlazioni mobili e di coda → Evidenza · Correlazioni; soglia in funzione di K → Apprendimento; tabella 3 × 3 → Evidenza · Indicatore GQ; R senza i primi 5, CUSUM, scomposizione → Evidenza. *Mancano:* registro delle 4.071 prove, slittamento reale, capacità.

**Conflitti tra le note e come sono risolti**
1. Scala della caduta verticale (G) o orizzontale (R): una sola, orizzontale (regge 24 ore, 7 giorni, peggior caso e il telefono), con i segni chiesti dal gestore (massimo simulato −21%, punto peggiore in paper).
2. «Tutte e nove le domande senza scorrere» (G) contro l'aria: in Semplice cinque riquadri rispondono a D1–D4, D7, D8 e gli altri sono a uno scorrimento; in Terminale stanno tutte in uno schermo.
3. Sharpe live: nascosto prima di 90 giorni (G), non prima di 60 (E): vale la regola più severa per schermo: mai in Oggi; da 60 giorni solo in Esperto e Terminale con l'errore; prima «— · n giorni su 60».
4. Una voce per componente sempre visibile (G) contro fascia essenziale (R): la fascia mostra il sistema solo se qualcosa non è ok; l'elenco completo è a un clic in Sistema · Salute.
5. Esposizione: «utile» per il gestore, «indispensabile con i tetti» per il rischio: i tetti stanno in Rischio, la composizione in Portafoglio, lo stesso riquadro.
6. Punteggi grezzi di conviction e GQ: rumore in prima schermata (G), colonne nell'elenco (R): livello a parole in Oggi, punteggi in Mercati da Esperto in su.
7. `g o` era «ordini» (R): diventa Oggi; gli ordini sono `g b`. `m` resta «misura»: Mercati si raggiunge con `g m`.
8. Avvertenze statistiche «accanto al numero» (G, E) contro la pulizia: una riga breve sotto la cifra in E/T, la versione lunga nel «?»; in Semplice la cautela è nella frase («servono ancora molti giorni»).
9. Livello nella barra in alto (specimen del sistema visivo) o nel binario: nel binario, perché la fascia a 1440 è piena di stato; da decidere insieme al designer visivo.
10. Più animazione (proprietario) contro «lo schermo non deve fingere altro» (G §5) e la stanchezza da allarme (R): si muovono ambiente e struttura, mai i numeri tra un ciclo e l'altro; il respiro è legato alla freschezza del dato, quindi dice una cosa vera.

## j. Ordine di costruzione: cinque incrementi, ognuno pubblicabile
1. **Guscio e verità.** Fascia di stato con SCONOSCIUTO, KILL nella fascia con disponibilità e anteprima, sistema di provenienza, binario a sette spazi che per ora ospitano le viste esistenti, tavolozza per la sola navigazione, soglie e valuta da una fonte sola (corregge l'esempio DEMO). Token del vetro scuro, cromature galleggianti, molle di base (spazi, fogli, segmentati) e ripieghi.
2. **Oggi e Rischio.** Patrimonio con i due libri e σ, cascata di attribuzione, scala dei freni, «che cosa è cambiato», trade aperti; Rischio con freni, peggior caso, tetti, riga dati e ordini; centro avvisi con presa in carico.
3. **Mercati.** Elenco, grafico a candele con i riquadri sotto e i livelli del trade, libro dei trade, selezione collegata, mappa dei tasti del grafico.
4. **Evidenza, Portafoglio, Apprendimento, Sistema.** Verdetto in una schermata stampabile, fortuna, confronto con l'originale, schede di ricerca; attribuzione e risultato; registro dell'apprendimento; ordini e cancelli; «Leva per trade» corretta in Archivio.
5. **Terminale e rifinitura.** Livello Terminale, coreografia completa (fondale, respiro, sequenze sfocato → nitido), tema chiaro secondario, esportazioni, stampa, telefono; i riquadri oggi vuoti (stress, paper contro modello, nastri) si accendono quando il motore espone i dati.
