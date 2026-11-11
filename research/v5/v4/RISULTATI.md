# Laboratorio v4: ricerca di nuovi margini su dati reali

Generato l'11 novembre 2026. Dati fino al 31 ottobre 2026 (crypto) e al 10 novembre 2026 (SPY orario).

**Ogni numero di rendimento in questo documento è SIMULATO** su dati storici reali, al netto dei costi dichiarati. Nessuno è un risultato ottenuto con denaro.

Etichette usate:

- **FATTO VERIFICATO**: letto direttamente da un dato o da una fonte primaria (un tasso di funding, un listino commissioni).
- **STIMA**: calcolo che dipende da un'ipotesi non verificabile con i dati disponibili (è detto quale).
- **IPOTESI**: idea non misurabile onestamente con questi dati.

Convenzioni: scelta fino al 31/12/2022, verifica dal 1/1/2023. Lo Sharpe è in eccesso del tasso a breve; la liquidità sugli exchange crypto e il margine dei perpetual rendono zero. Il segnale usa solo dati noti alla chiusura della barra e si esegue a quel prezzo (apertura della barra successiva); «ritardo +1» significa una barra in più. Costi: spot crypto 30 pb per lato, perpetual 7 pb per lato, funding reale, indici 1 pb per lato.

## 1. In breve

1. **Su 680 varianti provate, due sole cose reggono, ed entrambe sono deboli.** Il carry sul funding eseguito su Hyperliquid e l'acquisto dopo un crollo a 24 ore («DIP-24h»). Tutto il resto perde, oppure è una copia del trend che il libro ha già.
2. **Il portafoglio migliore che posso difendere non rende di più: rischia di meno.** Con DIP-24h e una quota fissa del 20% al carry lo Sharpe passa da 1,18 a 1,36 (verifica: da 0,86 a 1,07). Il rendimento annuo resta 13,6% contro 13,8%; la volatilità scende dal 9,0% al 7,6%.
3. **Il carry sta finendo.** Su Hyperliquid ha reso il 19,9% nel 2024, il 4,9% nel 2025 e l'1,8% nei primi dieci mesi del 2026, cioè meno di un titolo di Stato a breve. Su Binance è sotto il tasso a breve dal 2023: il verdetto precedente è confermato.
4. **Il rendimento in più viene solo dalla leva**, e costa: a volatilità obiettivo 15% il portafoglio nuovo rende il 20,9% l'anno con caduta massima del 13,6%; a 25% rende il 32,5% con caduta del 26,6%.
5. **Con 812 prove complessive il Deflated Sharpe è 0,38** (0,20 per il portafoglio attuale). La soglia del progetto è 0,95: nessuno dei due la supera.

## 2. Dati: che cosa ho raggiunto e che cosa no

| Sorgente | Esito | Uso |
|---|---|---|
| data.binance.vision: candele spot e USDT-M (1h per 36 monete, 5m per BTC/ETH/SOL), funding dal 2020 | raggiunta | tutte le famiglie |
| data.binance.vision `futures/um/daily/metrics` (open interest, rapporti long/short, taker), 10 monete | raggiunta, **esiste solo dal 2021-12** | famiglia 4 |
| data.binance.vision `liquidationSnapshot` | **404: non esiste più** | liquidazioni approssimate con calo dell'open interest |
| Indice S3 dell'archivio Binance: 918 perpetual USDT-M (anche tolti dal listino), candele 1d e funding | raggiunto | nuove quotazioni, carry trasversale |
| Hyperliquid `fundingHistory` (orario, dal 2023-05) e `candleSnapshot` (1d; 1h solo ultime 5.000 barre), 16 monete | raggiunta | carry |
| Deribit `get_volatility_index_data` (DVOL BTC/ETH giornaliero dal 2021-03) | raggiunta | volatilità |
| alternative.me Fear & Greed, DefiLlama stablecoin, Coinmetrics community | raggiunte (Coinmetrics: `TxTfrValAdjUSD` negato) | on-chain, sentiment |
| OKX API pubblica | raggiunta ma lo storico del funding copre circa tre mesi | non usata |
| Bybit API (`api.bybit.com`) | **403: bloccata per paese** | non usata |
| `fapi.binance.com` | **451: bloccata per paese** | non usata (l'archivio basta) |
| Yahoo intraday | **429** al momento della prova | usata la cache esistente (SPY orario 2023-12 → 2026-11) |
| Prezzi storici delle opzioni Deribit (denaro/lettera) | non scaricati | il P&L «short volatilità» è una STIMA |
| Book L2 di qualunque sede | non disponibile | il market making è un'IPOTESI |
| Dati intraday S&P 500 tra il 2019 e il 2023-11 | non disponibili | buco nella prova GEX intraday |

## 3. Tabella dei candidati

Sharpe in eccesso del tasso a breve: tutto | scelta | verifica. Correlazione mensile con il portafoglio attuale.

| # | Candidato | Sharpe | CAGR | Vol | Caduta max | Corr. portafoglio | Costi ×2 (verifica) | Ritardo +1 (verifica) | Verdetto |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | Carry su Binance (5 monete, isteresi) | 3,21 \| 7,43 \| −2,56 | 7,3% | 1,2% | −1,0% | 0,30 | −3,21 | −2,78 | **Scartato**: sotto il tasso a breve dal 2023 |
| 1 | Carry su Hyperliquid (solo verifica, 2023-06 →) | 4,34 | 9,8% | 1,1% | −0,4% | 0,36 | 2,08 | 4,03 | **Passa con riserva**: in esaurimento |
| 1 | Arbitraggio di funding Hyperliquid − Binance, 2x | 4,87 (solo verifica) | 12,5% | 1,5% | −0,7% | 0,46 | −0,36 a 1x | 1,42 a 1x | **Scartato**: non regge i costi doppi, Binance futures chiuso agli italiani |
| 2 | Coppie con selezione walk-forward | −0,95 \| −0,69 \| −1,19 | −32% | 37% | −94% | −0,10 | — | — | **Scartato**: perde anche senza costi |
| 2 | Inversione dei residui a 5 giorni | −1,44 \| −1,82 \| −1,17 | −61% | 56% | −100% | −0,37 | — | — | **Scartato** |
| 3 | Trend orario lento (3–14 giorni), solo long | 0,71 \| 1,31 \| 0,27 | 16,5% | 20% | −31% | 0,67 | −0,55 | 0,10 | **Scartato**: copia di CR-TREND, non regge i costi doppi |
| 3 | Intraday S&P 500 condizionato al GEX (60 min) | scelta 2011–18: −0,14; verifica: −1,04 | −0,2% / −0,7% | 3–5% | −12,9% | 0,04 | — | — | **Scartato** |
| 4 | Cascata: open interest giù + prezzo giù, 24h | 0,30 \| 0,25 \| 0,33 | 6% | 51% | −73% | 0,52 | −0,04 | 0,46 | **Scartato** |
| 4 | **DIP-24h**: crollo sotto il 2° percentile, 24h | 0,93 \| 1,23 \| 0,66 | 20,6% | 18,8% | −16,3% | 0,41 | 0,40 | 0,57 | **Passa, di misura** |
| 4 | Long su funding molto basso, 72h | 0,21 \| −0,02 \| 0,46 | −9% | 74% | −89% | 0,35 | 0,34 | 0,36 | **Scartato** |
| 4 | Contro i conti al dettaglio (rapporto long/short) | 0,79 \| 1,58 \| 0,50 | 32% | 40% | −26% | 0,12 | 0,15 | 0,39 | **In osservazione**: scelta di soli 12 mesi |
| 5 | Vendita di varianza BTC+ETH (STIMA) | −0,92 \| 1,31 \| −2,80 | 1,3% | 2,2% | −7,1% | 0,05 | — | — | **Scartato**: premio sparito |
| 5 | DVOL come filtro sui trend | nessun filtro migliora la verifica | | | | | | | **Scartato** |
| 6 | Market making (IPOTESI) | −3 / −4 pb per esecuzione sui maggiori | | | | | | | **Scartato** per un conto al livello base |
| 7 | Offerta di stablecoin in crescita | 0,76 \| 0,91 \| 0,48 | 34% | 60% | −72% | 0,61 | 0,42 | 0,49 | **Scartato**: correlazione 0,81 con CR-TREND |
| 7 | Fear & Greed sopra la media a 30 giorni | 0,71 \| 0,87 \| 0,43 | 28% | 46% | −54% | 0,62 | −0,08 | 0,34 | **Scartato** |
| 7 | Ore 21–23 UTC, commissioni maker (IPOTESI) | 0,70 \| 0,46 \| 0,99 | 16% | 21% | −45% | 0,16 | — | — | **Ipotesi**: a 7 pb fa −1,24 |
| 7 | Short delle nuove quotazioni, coperto con BTC | 0,26 \| 0,07 \| 0,38 | 1,3% | 58% | −85% | −0,23 | 0,32 | 0,36 | **Scartato** da solo; diversifica |
| 7 | Funding long/short su tutti i perpetual | 0,58 \| 1,59 \| −0,14 | 15% | 24% | −32% | 0,34 | −0,47 | −0,12 | **Scartato**: sparito dopo il 2022 |

## 4. Famiglia per famiglia

### 4.1 Carry sul funding (`01_carry.py`)

**Margine dichiarato.** Chi vuole leva al rialzo sui perpetual paga il funding a chi sta short; long spot più short perpetual lo incassa senza rischio di prezzo. Paga chi specula al rialzo con leva.

**FATTO VERIFICATO: il funding medio delle dieci monete maggiori su Binance**, in % annuo incassato dallo short, contro il tasso a breve:

| | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 (10 mesi) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Funding Binance | 13,0 | 35,9 | −4,0 | 6,2 | 11,6 | 3,1 | 1,8 |
| Tasso a breve | 0,3 | 0,0 | 2,0 | 5,0 | 5,0 | 4,1 | 3,1 |

**FATTO VERIFICATO: Hyperliquid paga circa il doppio di Binance** sulle 15 monete in comune: 23,5% contro 12,6% nel 2024, 6,3% contro 2,1% nel 2025, 3,1% contro 1,4% nel 2026.

**Carry trasversale su Binance** (le 5 monete col funding più alto, entra sopra il 15% annuo, esce sotto il 5%, leva 3 sulla gamba short): Sharpe di scelta 7,4, di verifica −2,6. Su 96 combinazioni della griglia solo il 5% ha verifica positiva. Rende il 2,7% l'anno in verifica, meno del tasso a breve: scartato, come nella tornata precedente.

**Carry su Hyperliquid** (stessa regola, spot a 30 pb e perpetual a 7 pb):

| | 2023 (da giugno) | 2024 | 2025 | 2026 (10 mesi) |
|---|---:|---:|---:|---:|
| Rendimento % | 7,6 | 19,9 | 4,9 | 1,8 |
| Giorni investiti | 68% | 100% | 83% | 75% |

Restare sempre dentro su BTC, ETH e SOL dà quasi lo stesso: 7,4 / 20,1 / 6,2 / 2,5.

**Lo Sharpe di 4,3 non va letto come tale.** L'ho ricontrollato: il segnale è il funding medio dei 7 giorni precedenti e il ritardo di un giorno lo porta a 4,0, quindi non c'è look-ahead. È alto perché la volatilità misurata è l'1,1%: il rischio vero (insolvenza o attacco alla sede, sgancio della stablecoin, liquidazione della gamba short) non compare nel campione.

**Liquidazione della gamba short** (massimi orari, senza sorveglianza dentro la giornata, Binance 2020–2026): 13 eventi a leva 2, 30 a leva 3, 104 a leva 5. A leva 5 il rendimento in verifica scende all'1,3%.

**Capacità.** FATTO: volume giornaliero mediano 2026 su Hyperliquid in milioni di dollari: BTC 2.389, ETH 961, HYPE 301, SOL 229, XRP 46; le altre tra 1 e 13. Per 10 mila euro non ci sono limiti. Per un milione la quota per moneta (150 mila) supera l'1% del volume delle alt: bisogna restare su BTC, ETH, SOL.

**Arbitraggio tra sedi** (short dove il funding è alto, long dove è basso): 6,1% l'anno a nozionale 1x, cioè poco sopra il tasso a breve; con costi doppi va a −0,36 di Sharpe. Per anno: 2023 forte, 2025 nullo, 2026 negativo. E richiede i futures di Binance, che un retail italiano non può usare.

### 4.2 Arbitraggio statistico (`02_statarb.py`)

**Margine dichiarato.** Monete correlate si allontanano e tornano; paga chi muove un prezzo relativo per ragioni di liquidità.

Nei dati non c'è. Coppie su 20 perpetual con selezione mensile delle più cointegrate: tutte le 54 combinazioni perdono, in scelta e in verifica. Sharpe mediano a 1 ora: −1,24 in scelta e −1,52 in verifica; a 1 giorno: −1,24 e −1,02. Perdono **anche senza costi** (−0,55 a 1 ora, −0,91 a 1 giorno): i prezzi relativi delle crypto proseguono, non rientrano. È lo stesso fenomeno che CR-XSMOM sfrutta dal lato opposto. ETH/BTC, SOL/ETH e SOL/BTC fisse: tra −0,4 e −1,7.

L'inversione dei residui a 1 ora ha Sharpe lordo 5,3 in scelta e 0,5 in verifica, ma gira il portafoglio ogni ora: netto, azzera il capitale.

### 4.3 Intraday (`03_intraday.py`)

- **Momentum a 5 minuti, 15 minuti, 1 ora** (23 orizzonti): lordo tra −4,6 e +1,2, netto sempre negativo in verifica sotto le 336 ore. Sopra diventa il trend giornaliero che il libro ha già (correlazione 0,67).
- **Ora del giorno.** FATTO: le ore 21 e 22 UTC rendono +3,9 e +5,0 pb in verifica (+4,2 alle 21 in scelta). Lordo 0,91 in scelta e 1,63 in verifica; con 7 pb per lato −1,24. La scelta walk-forward delle ore migliori perde sempre.
- **Giorno della settimana**: nessun effetto stabile tra scelta e verifica.
- **Ritorno al VWAP**: sotto 2 deviazioni perde; a 3 deviazioni su 5 minuti fa 0,58 in scelta e 0,61 in verifica con 12 operazioni l'anno, troppo poche per distinguerlo dal caso.
- **Rottura del range di apertura** (4 sessioni, 2 finestre): netto tra −1,0 e −3,5.
- **Momentum alla Gao** (la sessione predice l'ultima ora): lordo 2,2 in scelta e −1,1 in verifica.
- **S&P 500 condizionato al GEX**: su 21 combinazioni nessuna ha Sharpe positivo sia in scelta (2011–2018) sia in verifica (2023-12 → 2026-11). Il ritorno al VWAP con GEX alto perde anche lordo.

### 4.4 Liquidazioni, open interest, posizionamento (`04_liquidazioni_oi.py`)

**Studio d'evento** (calo dell'open interest sotto il 2° percentile e del prezzo sotto il 5° in 4 ore, 10 monete): nelle 24 ore successive +97 pb in verifica contro +13 incondizionati (2.505 ore-moneta), ma −57 contro −28 nella scelta, che copre solo 13 mesi di mercato in discesa.

**L'open interest non aggiunge nulla al solo crollo del prezzo.** La regola senza open interest ha più storia (dal 2020) e risultati migliori: è il candidato DIP-24h.

**DIP-24h**: quando il rendimento a 24 ore di una moneta scende sotto il 2° percentile dei 90 giorni precedenti, si compra il 10% del capitale su quel perpetual per 24 ore, con esposizione totale massima 50%.

- Griglia (3 percentili × 3 durate × 2 dimensioni): 18 su 18 positive sia in scelta sia in verifica; verifica tra 0,31 e 0,98.
- Costi doppi: 0,76 \| 1,11 \| 0,40. Ritardo di 1 ora: 0,71 \| 0,89 \| 0,57. Ritardo di 4 ore: 0,41 \| 0,52 \| 0,32.
- Con lo spot a 30 pb la verifica è −0,18: **funziona solo sui perpetual**.
- Per anno: 0,61 / 2,49 / 0,12 / 1,90 / 0,55 / 0,44 / −0,04. In calo dal 2024.
- Margine dichiarato: chi è liquidato vende a qualunque prezzo; chi compra fornisce liquidità e la fa pagare.

**Estremi di funding**: andare short sul funding alto perde sempre (da −0,3 a −1,1). **Top trader**: seguirli perde. **Conti al dettaglio**: andare contro dà 0,50 in verifica, ma 0,15 con costi doppi.

### 4.5 Volatilità (`05_volatilita.py`)

**FATTO VERIFICATO: il premio di volatilità** (DVOL meno volatilità realizzata dei 30 giorni successivi, in punti):

| | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|
| BTC | 16,7 | 13,0 | 7,1 | 6,3 | 3,8 | 1,1 |
| ETH | 11,0 | 10,5 | 5,6 | 2,4 | −1,3 | 3,7 |

**STIMA**: vendere varianza a 30 giorni a (DVOL − 3 punti), senza prezzi reali delle opzioni. Rendimento per anno con vega pari all'1% del capitale per punto: 4,2 / 4,9 / 3,1 / −0,2 / −3,1 / −1,2. Dopo uno spread di 3 punti il premio in verifica è nullo o negativo.

**Filtri di regime**: dieci filtri su DVOL e vol-della-vol applicati a CR-TREND e CR-XSMOM. Nessuno migliora la verifica: CR-TREND 0,54 senza filtro, al massimo 0,53 con; CR-XSMOM 1,08 senza, al massimo 1,07 con.

**Esecuzione per un retail italiano.** Non ho trovato una fonte che confermi che Deribit accetti clienti al dettaglio italiani (la società operativa è vigilata a Dubai; Coinbase l'ha acquisita nell'agosto 2025). Su IBKR le opzioni sugli ETF bitcoin americani non sono acquistabili senza KID. Da verificare prima di qualunque uso.

### 4.6 Market making (`06_market_making.py`): IPOTESI

**FATTO VERIFICATO**: al livello base Hyperliquid fa pagare 1,5 pb al maker e 4,5 pb al taker. Lo sconto al maker (da −0,1 a −0,3 pb) richiede più dello 0,5% del volume maker dell'intera piattaforma.

**STIMA dai dati a barre** (limite superiore: primi in coda, nessuna latenza): quotando a ±1–10 pb dalla chiusura precedente su BTC/ETH/SOL a 5 minuti, il guadagno lordo per esecuzione è tra −1,0 e −0,7 pb, perché la selezione avversa supera la distanza quotata. Netto: tra −3,7 e −4,0 pb uscendo da maker, −7,5 uscendo da taker. Sulle alt a 1 ora diventa positivo solo oltre i 200 pb di distanza (+2,3 pb netti), dove non è più market making ma inversione dentro la barra, e in verifica è la metà della scelta.

Riferimento esterno: il vault HLP di Hyperliquid ha reso circa l'11% annualizzato nel primo semestre 2025, in buona parte da liquidazioni e non da spread (fonte secondaria, non verificata).

### 4.7 Altro (`07_altro.py`)

- **Offerta di stablecoin** (crescita a 30 giorni positiva): 0,91 in scelta e 0,48 in verifica, ma correlazione 0,81 con CR-TREND.
- **Flussi verso gli exchange, MVRV, indirizzi attivi**: 16 regole; due battono il comprare e tenere in entrambi i periodi (BTC con deflussi a 7 giorni: 0,54 \| 1,02 contro 0,42 \| 1,01; ETH con MVRV in salita a 30 giorni: 0,86 \| 0,96 contro 0,58 \| 0,50). Due su 16 è ciò che ci si aspetta dal caso, e sono regole long-only che seguono il prezzo. I dati on-chain sono rivisti dopo la pubblicazione: rischio di look-ahead non eliminabile.
- **Fear & Greed**: le regole contrarian perdono in scelta; quelle di momentum sono trend (correlazione 0,73).
- **Nuove quotazioni** (894 perpetual quotati dopo marzo 2020). FATTO: nei giorni 7–30 rendono 13,5 pb al giorno meno di BTC in verifica, ma lo short paga 2,8 pb al giorno di funding; nei primi 7 giorni il funding costa 14,5 pb al giorno. La strategia coperta con BTC ha Sharpe 0,38 in verifica, caduta massima −85% e giorno peggiore −17%.
- **Funding long/short su tutti i perpetual**: 1,59 in scelta, −0,14 in verifica.

## 5. Il portafoglio

Parità di rischio (`gerva.portfolio.allocate.risk_parity`) sugli sleeve a rischio di mercato. **Il carry riceve una quota fissa del 20%**: la parità di rischio gli darebbe il tetto del 60% perché la sua volatilità misurata è quasi nulla, mentre il suo rischio vero è di controparte e nessuno stop lo controlla. La quota del 20% è una scelta mia, non un risultato.

| Portafoglio | Sharpe tutto \| scelta \| verifica | CAGR | Vol | Caduta max |
|---|---|---:|---:|---:|
| 0. Attuale, 4 sleeve | 1,18 \| 1,49 \| 0,86 | 13,8% | 9,0% | −9,4% |
| 1. + DIP-24h | 1,23 \| 1,46 \| 0,95 | 14,2% | 9,0% | −9,4% |
| 2. + carry 20% | 1,32 \| 1,61 \| 0,96 | 13,2% | 7,6% | −9,4% |
| **3. + DIP-24h + carry 20%** | **1,36 \| 1,58 \| 1,07** | **13,6%** | **7,6%** | **−9,4%** |
| 3b. come 3, carry 10% | 1,29 \| 1,52 \| 1,00 | 13,9% | 8,3% | −9,4% |
| 3c. come 3, carry 30% | 1,44 \| 1,65 \| 1,15 | 13,3% | 7,0% | −9,4% |
| 4. Parità di rischio pura (artefatto) | 1,64 \| 1,83 \| 1,60 | 11,8% | 5,2% | −9,4% |

In verifica il portafoglio 3 rende il 12,7% contro il 13,0% dell'attuale, con volatilità 7,2% contro 9,6% e caduta massima −6,0% contro −8,0%.

**Solo dove il carry è eseguibile da un italiano** (Hyperliquid, giugno 2023 → ottobre 2026): attuale 0,73 con CAGR 10,9%; portafoglio 3 0,95 con CAGR 11,1%. Prima del giugno 2023 la serie del carry usa il funding di Binance, che un retail italiano non poteva incassare.

### Scomposizione del portafoglio 3

| Sleeve | Peso medio | Sharpe tutto \| scelta \| verifica | CAGR da solo | Contributo annuo | Contributo in verifica |
|---|---:|---|---:|---:|---:|
| CR-TREND | 13,2% | 1,02 \| 1,40 \| 0,54 | 26,2% | 3,0% | 2,4% |
| CR-XSMOM | 9,4% | 1,05 \| 1,04 \| 1,08 | 32,9% | 3,1% | 3,6% |
| EQ-MR | 19,7% | 0,83 \| 1,14 \| 0,33 | 13,4% | 2,6% | 1,4% |
| MA-TREND | 33,5% | 0,17 \| 0,37 \| −0,12 | 3,7% | 1,4% | 1,1% |
| DIP-24h | 9,1% | 0,93 \| 1,23 \| 0,66 | 20,6% | 1,4% | 2,1% |
| Carry | 14,9% | 5,39 \| 7,43 \| 3,66 | 11,1% | 1,6% | 1,7% |

**Guadagno da diversificazione.** Senza il carry, lo Sharpe medio degli sleeve è 0,80 (0,50 in verifica); il portafoglio fa 1,36 (1,07). Con il carry la media sale a 1,56, ma è gonfiata dalla sua volatilità quasi nulla.

### Che cosa aggiunge la leva

Leva = volatilità obiettivo / volatilità a 60 giorni, nota il giorno prima. Costo: tasso a breve + 1,5% sulla parte presa a prestito.

| | Leva media | Sharpe tutto \| scelta \| verifica | CAGR | Vol | Caduta max | Costo del debito |
|---|---:|---|---:|---:|---:|---:|
| Attuale, senza leva | 1,00 | 1,18 \| 1,49 \| 0,86 | 13,8% | 9,0% | −9,4% | — |
| Attuale, vol 15% (max 2x) | 1,71 | 1,07 \| 1,38 \| 0,74 | 18,8% | 14,6% | −15,1% | 3,0% |
| Attuale, vol 25% (max 4x) | 3,11 | 0,96 \| 1,23 \| 0,68 | 27,6% | 26,1% | −28,2% | 9,0% |
| Portafoglio 3, senza leva | 1,00 | 1,36 \| 1,58 \| 1,07 | 13,6% | 7,6% | −9,4% | — |
| Portafoglio 3, vol 15% (max 2x) | 1,85 | 1,27 \| 1,52 \| 0,97 | 20,9% | 13,6% | −13,6% | 3,7% |
| Portafoglio 3, vol 25% (max 4x) | 3,41 | 1,15 \| 1,38 \| 0,88 | 32,5% | 24,8% | −26,6% | 10,4% |

Il tetto di 2x impedisce di raggiungere davvero il 15% (la volatilità realizzata è 13,6%). Il calcolo suppone di potersi indebitare al tasso a breve + 1,5% su tutto il portafoglio: vale per la parte su IBKR, non per lo spot crypto.

## 6. Conteggio delle prove

| Famiglia | Varianti |
|---|---:|
| Carry | 148 |
| Arbitraggio statistico | 101 |
| Intraday | 207 |
| Liquidazioni e open interest | 107 |
| Volatilità | 34 |
| Market making | 22 |
| Altro | 61 |
| Portafogli | 10 |
| **Laboratorio v4** | **690** |
| Precedenti (v5: 110; v3: 12, stima mia dal codice) | 122 |
| **Totale** | **812** |

Lo Sharpe che ci si aspetta dal migliore di 812 tentativi senza abilità è 1,47 (era 1,18 con 110). Deflated Sharpe: 0,20 per il portafoglio attuale, 0,38 per il portafoglio 3. Molte delle 812 prove sono correlate tra loro (griglie di parametri), quindi il conteggio è prudente.

## 7. Provato e fallito

| Che cosa | Numero |
|---|---|
| Carry su Binance, 96 combinazioni | Sharpe di verifica mediano −2,7; 5% positive |
| Carry sempre dentro sulle 10 maggiori | verifica −0,68, CAGR 4,2% |
| Carry su SOL sempre dentro | caduta −40% (funding −38% nel 2022) |
| Arbitraggio di funding tra sedi a 1x, costi doppi | −0,36 |
| Coppie walk-forward, 54 combinazioni | 0 positive in verifica; lordo −0,55 / −0,91 |
| Coppie fisse ETH/BTC, SOL/ETH, SOL/BTC | da −0,4 a −1,7 |
| Inversione dei residui a 1 ora | lordo 5,3 → 0,5; netto −25 |
| Momentum 5m / 15m / 1h sotto le 336 ore | netto da −0,1 a −92; verifica sempre negativa |
| Ore 21–23 UTC a 7 pb | −1,24 |
| Ore migliori walk-forward | da −4,6 a −8,6 |
| Ritorno al VWAP, 12 combinazioni | 3 positive in entrambi i periodi, con 6–59 operazioni l'anno |
| Rottura del range, 8 combinazioni | da −1,0 a −3,5 |
| Momentum alla Gao | lordo 2,2 → −1,1 |
| GEX intraday su S&P 500, 21 combinazioni | 0 positive in entrambi i periodi |
| Cascata con open interest, 27 combinazioni | scelta negativa in 22 su 27 |
| Short su funding estremo | da −0,3 a −1,1 |
| Seguire i top trader | −1,52 trasversale |
| Open interest in crescita, trasversale | lordo −0,03 |
| Vendita di varianza con 3 punti di spread | verifica −2,80; rendimento 2025 −3,1% |
| 10 filtri DVOL sui trend | nessuno migliora la verifica |
| Market making sui maggiori | −3,7 / −4,0 pb per esecuzione |
| 16 regole on-chain | 2 su 16 battono il comprare e tenere in entrambi i periodi, di poco |
| Fear & Greed contrarian | da −0,22 a 0,09 in scelta |
| Short delle nuove quotazioni 7–90 giorni | 0,07 in scelta, caduta −85% |
| Funding long/short su tutti i perpetual | verifica −0,14 |

## 8. Di che cosa non sono sicuro

1. **Lo Sharpe del carry non misura il suo rischio.** La quota del 20% è un giudizio.
2. **DIP-24h è di misura**: verifica 0,66, 0,40 con costi doppi, nulla nel 2026, e dipende da un'esecuzione entro un'ora dal segnale.
3. **Hyperliquid per un italiano.** È una sede decentralizzata senza identificazione. L'ESMA (dichiarazione del 24 febbraio 2026) considera i perpetual derivati soggetti alle regole dei CFD. La posizione legale e fiscale va verificata con un professionista: non l'ho verificata io.
4. **Il prezzo spot del carry è quello di Binance**, il perpetual è di Hyperliquid: la base tra sedi è inclusa a livello giornaliero, non dentro la giornata.
5. **Monete tolte dal listino**: la simulazione del carry esce il giorno prima che i dati finiscano (LUNA, FTT), sapendo che finiranno. Effetto piccolo perché la posizione è coperta, ma è un'informazione futura.
6. **Rischio di liquidazione** calcolato sui massimi orari: dentro l'ora può essere peggiore.
7. **La scelta per open interest e posizionamento è di 13 mesi**: non basta a scegliere nulla.
8. **Il conteggio delle prove precedenti alla v4** (12 per la v3) è una mia stima dal codice.
9. **La leva** applicata all'intero portafoglio al costo di IBKR è una semplificazione.

## 9. File

| File | Contenuto |
|---|---|
| `00_dati.py` | scarico di tutti i dati nella cache (`data_cache/v4_*`) |
| `lab.py` | funzioni comuni: metriche, registro delle prove |
| `01_carry.py` … `07_altro.py`, `.out` | una famiglia per file, con il suo output |
| `08_portafoglio.py`, `.out` | tabella dei candidati, portafogli, leva, Deflated Sharpe |
| `candidates.parquet` | rendimenti giornalieri netti di 19 candidati (anche gli scartati), indice di calendario 2018-01-01 → 2026-10-31; vuoto prima dell'inizio di ciascuno. La serie GEX intraday contiene solo il 2018 e dal 2023-12 |
| `portafogli.parquet` | rendimenti giornalieri dei portafogli della sezione 5 |
| `cand_*.parquet`, `trials_*.json` | candidati e registro delle prove per famiglia |

Per rifare tutto: `/tmp/gv/bin/python research/v5/v4/00_dati.py`, poi gli script da `01` a `08` in ordine.

## 10. Fonti

- Hyperliquid, listino commissioni (taker 0,045%, maker 0,015% al livello base): <https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees>
- «Cryptocurrency as an Investable Asset Class: Coming of Age», arXiv 2510.14435 (2025): Sharpe del carry 6,45 nel 2020–2025, 4,06 dal 2024, negativo nel 2025: <https://arxiv.org/pdf/2510.14435>
- He, Manela, Ross, von Wachter, «Fundamentals of Perpetual Futures», arXiv 2212.06888: <https://arxiv.org/pdf/2212.06888v5>
- Almeida, Grith, Miftachov, Wang, «Risk Premia in the Bitcoin Market», arXiv 2410.15195 (2024): <https://arxiv.org/html/2410.15195v2>
- Alexander e Imeraj, «The Bitcoin VIX and its Variance Risk Premium» (2020): <https://sro.sussex.ac.uk/id/eprint/91094/>
- Padyšák e Vojtko, «Seasonality, Trend-following, and Mean reversion in Bitcoin» (2022), riassunto Quantpedia (tenere BTC due ore dalle 22:00 UTC): <https://quantpedia.com/strategies/intraday-seasonality-in-bitcoin>
- Animoca Research (2024), rendimenti dopo la quotazione sugli exchange: <https://cryptoslate.com/tokens-display-up-to-negative-70-median-returns-after-cex-listing-animoca-research/>
- 4Pillars, «Binance listing: flash or fade»: <https://research.4pillars.io/en/research/binance-listing-flash-or-fade>
- ESMA, dichiarazione del 24 febbraio 2026 sui perpetual: <https://www.dirittobancario.it/wp-content/uploads/2026/02/Dichiarazione-ESMA-24-febbraio-2026-ESMA35-243228190-8024.pdf>
- Finance Magnates, «ESMA Tells Firms Perpetual Futures Fall Under EU CFD Rules»: <https://www.financemagnates.com/forex/regulation/esma-tells-firms-perpetual-futures-fall-under-eu-cfd-rules/>
- «Where does the criticality live?», arXiv 2607.27070 (cascate di liquidazioni con open interest a 5 minuti): <https://arxiv.org/pdf/2607.27070>
- CoinGecko, analisi del vault HLP: <https://www.coingecko.com/learn/hyperliquid-hlp-vault-analysis>
- Dati: <https://data.binance.vision>, <https://api.hyperliquid.xyz/info>, <https://www.deribit.com/api/v2/public/get_volatility_index_data>, <https://api.alternative.me/fng/>, <https://stablecoins.llama.fi/stablecoincharts/all>, <https://community-api.coinmetrics.io>, <https://squeezemetrics.com/monitor/static/DIX.csv>
