# B4 — Premio per il rischio di volatilità azionaria (tutto SIMULATO)

**Esito in una riga: il premio esiste ed è grande per chi lo paga (chi compra futures VIX perde il 47% l'anno), ma per chi lo incassa vale Sharpe 0,4–0,6, cioè quanto l'S&P 500 comprato e tenuto, con una coda che in un giorno porta via il 96%. Non migliora il fondo e non avvicina il 30% al mese.**

## 1. Dati (FATTO)
- Futures VIX: 270 contratti mensili CFE, 2004 → 10/11/2026, con apertura, massimo, minimo e settle (cdn.cboe.com, un file per contratto; prima del 26/3/2007 prezzi ÷10; settimanali esclusi).
- Ho ricostruito gli indici a scadenza costante con la metodologia S&P: **ST** (mesi 1–2, quello che replica VXX) e **MT** (mesi 4–7, VXZ).
- Controllo: ST ricostruito contro VIXY reale 2011–2026: CAGR −48,5% contro −48,4%; MT contro VIXM −18,5% contro −18,2%. Il 5/2/2018 l'indice ST fa **+96,1%** (massimo del giorno +101,8%): è il giorno in cui XIV è morto, ed è nel campione.
- Indici strategia CBOE reali (cdn-api.cboe.com): PUT, PUTY, WPUT, BXM, BXMD, CMBO, CNDR, BFLY, VPD, VPN, PPUT, CLL, VXTH. SVRO non scaricabile. Yahoo: VIX, VIX3M, VIX9D, VVIX, SKEW, SVXY, VIXY, UVXY.
- `^SHORTVOL` di Yahoo non è l'indice inverso di XIV (non mostra il −96%): scartato.
- Dati sulle singole opzioni non ottenibili: le strutture con opzioni sono modellate (Black-76 / Black-Scholes) e marcate **STIMA**.

## 2. Che cosa può usare davvero un residente italiano
| Strumento | Stato | Fonte |
|---|---|---|
| Mini VIX future (VXM), moltiplicatore 100 $ | FATTO: negoziabile a IBKR. Un contratto ≈ 1.900 $ di nozionale, cioè il 15% di un conto da 12.000 € | CFTC/CFE, macroption.com |
| Margine VXM | FATTO: minimo di borsa 977 $ iniziale / 888 $ mantenimento sul primo mese (avviso CFE del 15/4/2026). STIMA: la tabella IBKR riporta per VXM 1.026/892 e 2.525/2.196 senza intestazioni leggibili; la seconda coppia è verosimilmente il lato corto. Con 2.500 $ di margine su 1.900 $ di nozionale chi vende non supera ≈ 0,75x | cdn.cboe.com/resources/margin_updates/2026/CFEMargins20260415.pdf; interactivebrokers.co.uk margin-futures-fops |
| ETP UCITS sul VIX | FATTO: esistono solo prodotti **lunghi**: WisdomTree VIXL 2,25x (XS2819843736, Borsa Italiana, 0,99%), Amundi S&P 500 VIX Futures Enhanced Roll (LU0832435464), Leverage Shares 2,25x Long VIX (XS3299470099, maggio 2026). Nessun ETP inverso sul VIX trovato in Europa dopo il 2018 | wisdomtree.com, borsaitaliana.it, justetf.com |
| SVXY, VXX, UVXY | Non acquistabili (PRIIPs). Le opzioni su di essi sì | brief |
| Opzioni XSP / SPX / Euro Stoxx 50 | Negoziabili. Ma un XSP vale ≈ 75.000 $ di nozionale: una put nuda è già leva 5–6x su 12.000 €. Sono praticabili solo gli spread (5% di larghezza = 3.750 $ di perdita massima) | noto, non riverificato oggi |

## 3. Risultati (Sharpe e CAGR: tutto / scelta ≤ 2022 / verifica ≥ 2023)
Esecuzione base: segnale alla chiusura del giorno d, eseguito al settle del giorno d+1. Costi futures: 20 pb per lato + 1,9 pb al giorno di roll. Rendimenti in eccesso sul T-bill. Peso 1 = nozionale pari al capitale.

| Test | Regola | Sharpe | CAGR | Max DD | Giorno / settimana peggiore |
|---|---|---|---|---|---|
| 1 | Corto ST sempre | 0,43 / 0,40 / 0,56 | −4,8% / −8,7% / +14,1% | −99,3% | −96,1% / −96,6% |
| 1 | Corto ST se VIX/VIX3M < 1, altrimenti piatto | 0,40 / 0,45 / 0,18 | −4,2% / −2,9% / −9,9% | −98,8% | −96,1% / −96,7% |
| 1 | Corto ST se VIX/VIX3M < 0,90 | 0,27 / 0,33 / −0,04 | +2,6% / +5,2% / −8,2% | −83,8% | −27,7% / −28,1% |
| 1 | **K1: corto ST se VIX < livello ST** (migliore in scelta) | **0,54 / 0,59 / 0,28** | +14,9% / +18,2% / +1,7% | −76,9% | −39,0% / −40,4% |
| 1 | K1 con un giorno di ritardo in più | 0,35 / 0,31 / 0,57 | −6,0% / −10,6% / +16,8% | −99,1% | −96,3% / −96,3% |
| 1 | K1 con costi ×2 | 0,38 / 0,43 / 0,10 | +5,7% / +8,6% / −6,4% | −81,6% | −39,0% / −40,4% |
| 1 | Lungo in backwardation invece che piatto | sempre peggio (0,33 al massimo) | | | |
| 2a | K1 a peso 0,10 (ST +100% costa il 10%) | 0,54 / 0,59 / 0,28 | +2,7% / +3,1% / +1,2% | −12,7% | −3,9% / −4,1% |
| 2b | K1 + stop a +15%, eseguito allo stop | 0,42 / 0,50 / 0,05 | +8,6% / +13,1% / −9,3% | −82,3% | −15,7% / −28,3% |
| 2b | K1 + stop a +15%, **eseguito al massimo del giorno** | 0,25 / 0,32 / −0,10 | −2,3% / +1,5% / −17,6% | −96,6% | −39,8% / −44,2% |
| 2c | Future mensile corto + call VIX strike 1,3×F, con filtro (STIMA) | 0,06 / 0,11 / −0,17 | −10,1% | −93,6% | −32,8% / −35,0% |
| 2c | idem, call strike 2×F (STIMA) | 0,36 / 0,38 / 0,27 | +3,0% | −83,9% | −44,0% / −45,5% |
| 2 | **VPD, indice CBOE reale** (corto futures VIX a leva limitata), sempre | 0,47 / 0,42 / 0,73 | +8,7% / +7,6% / +13,3% | −62,0% | −31,2% / −40,0% |
| 2 | **K2: VPD solo se S&P 500 > media 200 giorni** | **0,54 / 0,55 / 0,53** | +7,2% / +7,3% / +6,8% | −23,4% | −18,3% / −20,1% |
| 2 | VPN, indice CBOE reale (corto futures VIX + call) | 0,46 / 0,46 / 0,43 | +7,2% / +7,5% / +6,0% | −53,1% | −18,1% / −19,8% |
| 3 | PUT, indice CBOE reale (put ATM mensile) | 0,43 / 0,37 / 0,85 | +5,1% / +4,5% / +8,0% | −37,7% | −11,5% / −18,3% |
| 3 | PUT se S&P 500 > media 200 giorni | 0,53 / 0,51 / 0,63 | +3,6% / +3,6% / +3,6% | −13,2% | −4,4% / −10,3% |
| 3 | Iron condor (CNDR), iron butterfly (BFLY) | −0,06 e −0,29 | negativi | | |
| 3 | Put-spread 3% OTM largo 5% (STIMA) | 0,33 / 0,15 / 1,39 | +1,5% / +0,6% / +5,3% | −27,7% | −3,6% / −6,3% |
| 3 | Put ATM nuda se VIX/VIX3M < 1 (STIMA) | 0,71 / 0,63 / 1,11 | +7,5% / +6,8% / +10,6% | −23,8% | −7,8% / −15,5% |
| 4 | Corto ST + lungo 1×MT, con filtro | 0,27 / 0,35 / −0,09 | +3,4% | −59,1% | −22,3% / −24,4% |
| 4 | Lungo ST sempre (assicurazione pura) | −0,54 | −47,2% | −100% | |
| 4 | VXTH, indice CBOE reale (S&P + call VIX) | 0,54 / 0,56 / 0,48 | +7,9% | −45,1% | marzo 2020: +37,6% |
| 5 | S&P 500 1x (riferimento) | 0,55 / 0,47 / 1,05 | +9,2% / +7,7% / +15,5% | −56,2% | −12,0% / −18,3% |
| 5 | S&P solo se VRP > 0 | 0,59 / 0,58 / 0,68 | +8,5% | −28,6% | −12,0% / −16,6% |
| 5 | S&P con volatilità a bersaglio 10% (riferimento) | 0,63 / 0,60 / 0,77 | +6,7% | −25,5% | −5,3% / −9,6% |
| 5 | S&P 2x se VIX9D < VIX, 1x altrimenti | 0,71 / 0,62 / 1,09 | +14,7% | −39,0% | −12,0% / −18,3% |

Finestre di crisi (rendimento composto nella finestra, peso 1):
| | Feb 2018 | Ago 2015 | Mar 2020 | Ago 2024 |
|---|---|---|---|---|
| Corto ST sempre | −95,9% | −39,4% | −85,4% | −52,6% |
| K1 | −14,4% | −22,8% | −17,8% | 0,0% |
| K1 con un giorno di ritardo | −96,3% | −42,5% | −26,1% | 0,0% |
| K2 (VPD se > MM200) | −14,1% | −4,2% | −12,3% | −10,1% |
| PUT sempre | −5,9% | −4,8% | −26,7% | −4,0% |
| SVXY reale comprato e tenuto | −91,1% | −39,0% | −59,2% | −27,3% |

K1 per anno: 2006 +44%, 2007 −42%, 2008 −7%, 2009 +100%, 2010 +117%, 2011 −30%, 2012 +123%, 2013 +50%, 2014 −17%, 2015 −8%, 2016 +177%, 2017 +81%, 2018 −41%, 2019 +53%, 2020 −27%, 2021 +37%, 2022 −40%, 2023 +150%, 2024 −61%, 2025 +21%, 2026 −11%. t del rendimento medio 2,45. Controllo di troncamento superato.

## 4. Migliore candidato: K1 (e K2 come versione a rischio limitato)
- **Regola K1**: alla chiusura, se VIX < livello dell'indice ST (media pesata dei primi due futures) si è corti di VXM per un nozionale pari a w × capitale; altrimenti piatti. In posizione l'81% dei giorni.
- **Chi paga**: chi compra assicurazione di portafoglio e chi tiene ETP lunghi sul VIX (2,25x UCITS compresi). Continueranno: è domanda di copertura. FATTO: costo per loro 47% l'anno sul tratto breve, 18% sul tratto medio.
- **Capacità**: nessun limite a questa scala. Il limite è la granularità (1 VXM = 15% del conto) e il margine.
- **Leva di crescita massima e rendimento mensile composto** (ricampionamento a blocchi mensili, 4.000 percorsi, 3 anni):

| | L* | Mese a L* | Mese a L*/2 | P(−50%) a L* | P(−50%) a L*/2 | Metà vantaggio: P(−50%) a L* / L*/2 |
|---|---|---|---|---|---|---|
| K1 base | 0,95 | +1,17% | +0,86% | 60% | 6% | 72% / 12% |
| K1 con un giorno di ritardo | 0,50 | +0,47% | +0,34% | 22% | 1% | 27% / 1% |
| K1 costi ×2 | 0,70 | +0,58% | +0,44% | 37% | 2% | 47% / 3% |
| K2 (VPD se > MM200) | 3,15 | +1,13% | +0,82% | 51% | 3% | 62% / 6% |
| PUT sempre | 3,00 | +0,76% | +0,57% | 39% | 4% | 45% / 6% |
| S&P 500 (riferimento) | 2,85 | +1,34% | +1,00% | 65% | 7% | 74% / 13% |

- **Correlazione col fondo** (giornaliera / mensile, 2018-04 → 2026-10): K1 +0,33/+0,37 con B, +0,23/+0,32 con C1, +0,24/+0,32 con C3. K2: +0,37/+0,35, +0,24/+0,27, +0,25/+0,27.
- **Effetto sul fondo**: C1 da solo Sharpe 1,43; con 0,10×K1 scende a 1,36; con 0,10×K2 sale a 1,45; il migliore peso scelto a posteriori dà 1,45. B da solo 1,84: K1, K2 e PUT lo abbassano (1,44 / 1,79 / 1,77 a peso 0,10); solo il put-spread STIMA lo lascia a 1,85. In termini dell'aritmetica del brief: ΔSharpe ≈ 0, quindi Δ(N·(R̄/σ)²) ≈ 0.
- **L'evento che lo uccide**: un salto dei futures VIX in giornata o dopo le 16:00 con la curva ancora in contango, cioè un altro 5/2/2018. K1 l'ha evitato per **un solo giorno** di differenza nel segnale: con un giorno di ritardo lo prende in pieno.

## 5. Che cosa la barra giornaliera non vede
- Il 5/2/2018 il grosso del movimento è avvenuto tra le 15:00 e le 16:15 e nel dopo-mercato: uno stop sul future non garantisce il prezzo. Stress fatto: esecuzione al massimo del giorno. Uno stop a +10% passa da Sharpe 0,40 a −0,05; a +15% da 0,42 a 0,25; solo lo stop a +30% regge (0,49), ma non protegge.
- I massimi dei contratti non sono simultanei: il mio «massimo dell'indice» li somma, quindi è una stima per eccesso della perdita (prudente).
- I futures VIX trattano quasi 24 ore: i salti notturni compaiono solo nel settle del giorno dopo. Agosto 2024: massimo del giorno +64% contro settle +42%.
- Il margine: in un giorno a +96% IBKR liquida prima del settle e alza i margini. Non simulato; peggiora il risultato, non lo migliora.
- La call di copertura è valutata con VVIX più un'ipotesi di skew: con skew 0,3 lo Sharpe sale a 0,20, con 1,0 scende a −0,14. In ogni caso sotto il future nudo: la copertura costa più del premio che resta.
- Il modello delle put sovrastima: put ATM modellata +8,2% l'anno contro +6,4% dell'indice PUT reale (correlazione 0,95). I numeri STIMA vanno ridotti di circa un quinto.

## 6. Che cosa non ha funzionato
- Filtro di contango classico (VIX/VIX3M): non evita il 5/2/2018 a soglia 0,95 e 1,00; a soglia 0,90 e 0,85 toglie il premio.
- Girarsi lunghi in backwardation: perde sempre.
- Ogni forma di rischio definito sui futures: lo stop realistico e la call mangiano il premio.
- Iron condor e butterfly (indici CBOE reali): Sharpe negativo.
- Copertura di coda finanziata dal carry: corto ST + lungo MT scende da 0,55 a 0,27. Sul fondo, 5% lungo MT lascia lo Sharpe a 1,43 e toglie 0,5 punti di CAGR; 5% lungo ST lo porta a 1,36.
- VRP come filtro per la leva sull'indice: 0,59 contro 0,55, meno di una semplice volatilità a bersaglio (0,63). Non aggiunge informazione.
- VRP come filtro per EQ-MR: nessun effetto (t della differenza +0,69 con lag 0, −0,36 con lag 1). Il filtro che conta è il livello del VIX: con VIX ≥ 20 EQ-MR rende +15,4 pb al giorno, sotto 20 rende −0,8 (t −3,5). **Già noto** (A5 e validazione): lo confermo con dati indipendenti, non è una scoperta.

## 7. Varianti provate: 229
T1 15, T2 33 (taglia 4, stop 16, call 13), T3 106 (indici 78, put modellate 28), T4 36, T5 39.

## 8. Dubbi
- K1 è il migliore di 15 varianti con Sharpe di scelta 0,59: dopo la correzione per le prove non è distinguibile da «corto sempre» (0,40). In verifica fa 0,28.
- La fragilità al ritardo è il dato più importante: tra «evitato» e «−96%» c'è un giorno. Non lo considero un vantaggio dimostrato.
- Il margine IBKR sul lato corto è una STIMA da una tabella senza intestazioni: va letto sulla piattaforma prima di ogni decisione.
- Gli indici CBOE non sono acquistabili: replicarli con opzioni reali costa. Ho tolto lo 0,4% l'anno (IPOTESI).
- 2023–2026 è un mercato rialzista: tutto ciò che è beta azionario mascherato (PUT, BXM, put modellate) ha Sharpe di verifica gonfiato.
- Il fondo parte da aprile 2018: la correlazione non contiene febbraio 2018.

## File
`00_dati.py`, `00b_cboe.py` (scarico), `01_base.py` (pannello e indici; scrive `data_cache/v6b4_base.pkl`), `lab.py`, `02_futures.py` (test 1–2), `03_put.py` (test 3), `04_coda_vrp.py` (test 4–5), `05_sintesi.py`, i rispettivi `.out`, `returns.parquet` (7 colonne, giornaliere, calendario, senza leva, in eccesso sul T-bill).
