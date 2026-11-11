# GERVA Capital — Rifondazione, versione 3

**11 novembre 2026.** Tutti i rendimenti di questo documento sono **SIMULATI** su dati storici reali. Il fondo non ha un solo giorno di operatività, nemmeno in paper. Le etichette: **[F]** fatto verificato (dato o fonte letta), **[S]** stima, **[I]** ipotesi.

La versione precedente è in [`archivio_RIFONDAZIONE_v2.md`](archivio_RIFONDAZIONE_v2.md). I dettagli di questa versione stanno in tre file che il documento riassume:

- [`research/v5/v4/RISULTATI.md`](../research/v5/v4/RISULTATI.md): le strategie provate nella quarta tornata, con script, uscite e fonti;
- [`research/v5/v4/STRUTTURA.md`](../research/v5/v4/STRUTTURA.md): sedi, custodia, veicolo giuridico e fiscale, infrastruttura, sicurezza, con 50 fonti;
- `research/v5/v4/leva_trade_*.py` e `09_fondo.py`: la leva per singolo trade e il fondo intero.

---

## 0. Che cosa è cambiato rispetto alla versione 2

| Tema | Versione 2 | Versione 3 |
|---|---|---|
| **Strategie** | 4 strategie giornaliere; 122 varianti provate | 6 strategie giornaliere più un libro di trade a leva; **812 varianti** provate in tutto, di cui 680 nuove in sette famiglie |
| **Leva** | Tetto 2x sul conto; leva per trade solo progettata | **Libro dei trade a margine isolato**, misurato sul percorso a 5 minuti: 11x sui setup confermati, 30x sugli eccezionali, 50x respinta dai dati. Il tetto 2x resta solo sul libro giornaliero |
| **Rendimento atteso** | 23% l'anno (base), 10% (prudente) | Profilo prudente **28% / 15%**; profilo massimo **55% / 22%** (base / prudente) |
| **Rischio** | Caduta tipica −17% | Prudente −9%; massimo −19% tipica, −35% nel 5% dei casi peggiori |
| **Sedi** | IBKR, exchange UE, Alpaca paper | Verificato che cosa è lecito per un residente italiano: perpetual a 10x su sedi MiFID; Binance chiusa; Hyperliquid solo come quota a perdere |
| **Struttura** | Persona fisica, indicazioni generali | Veicolo, fisco (33% / 26%), custodia, costi mensili, domande per commercialista e avvocato |
| **AI** | Può ridurre o vietare le strategie | In più: moltiplicatore sul rischio del singolo trade, sempre tra 0 e 1 |
| **Evidenza statistica** | Deflated Sharpe 0,51 su 110 prove | **0,38 su 812 prove** (0,20 per il vecchio portafoglio): contare tutte le prove ha abbassato la fiducia, non alzata |

**Un errore mio corretto in questa versione.** La prima misura del fondo combinato dava uno Sharpe di 1,50. Era gonfiata: attribuivo l'intero guadagno di un trade al giorno di uscita, e la correlazione giornaliera con il resto del portafoglio risultava 0,16 invece di 0,64. Sui rendimenti mensili lo Sharpe è 1,17. Tutti i numeri del fondo combinato qui sotto sono mensili.

---

## Verdetto

1. **Il 20–30% al mese resta non sostenuto.** Il profilo più spinto che i dati reggono rende in media il 3,7% al mese nello scenario base e l'1,7% in quello prudente. Mesi sopra il 20% capitano (il 12% dei mesi nella simulazione), ma insieme a mesi da −17%.
2. **La leva alta sul singolo trade è sostenibile fino a 30x**, a una condizione: che il rischio per trade resti tra lo 0,5% e il 2% del patrimonio. A margine isolato la leva decide quanto margine impegni, non quanto perdi.
3. **Il rendimento in più non viene da nuova abilità.** Lo Sharpe del portafoglio giornaliero è 1,34; quello del fondo con il libro dei trade è 1,17. Si guadagna di più perché si rischia di più, in modo controllato.
4. **Le strategie "da hedge fund" cercate non reggono per un conto al dettaglio**: arbitraggio statistico, market making, vendita di volatilità, intraday con GEX e VWAP perdono dopo i costi. Reggono il carry su Hyperliquid (in esaurimento) e l'acquisto dei crolli a 24 ore (di misura).
5. **Il vincolo più duro è legale ed economico, non tecnico**: 10x è il massimo lecito in Europa sui perpetual, e i costi fissi valgono dal 7% al 30% l'anno su 10.000 €.

---

## 1. Strategie

### 1.1 Che cosa è stato provato

680 varianti nuove, sette famiglie, dati reali: archivio Binance (918 perpetual, compresi quelli tolti dal listino), funding e candele di Hyperliquid, DVOL di Deribit, GEX giornaliero, indice Fear & Greed, DefiLlama, Coinmetrics. Periodo di scelta fino al 31/12/2022, verifica dal 1/1/2023. Costi: 30 pb per lato sullo spot, 7 pb sui perpetual (4,5 pb taker su Hyperliquid **[F]**), funding effettivo. Ogni candidata è riprovata a costi doppi e con una barra di ritardo.

Sharpe in eccesso del tasso a breve: tutto | scelta | verifica.

| Famiglia | Strategia | Edge dichiarato | Sharpe | CAGR | Verifica a costi doppi | Correlazione col portafoglio | Decadimento | Esito |
|---|---|---|---|---:|---:|---:|---|---|
| Carry | Spot lungo + perpetual corto su Binance, 5 monete | I long a leva pagano il funding | 3,21 \| 7,43 \| −2,56 | 7,3% | −3,21 | 0,30 | Sotto i Treasury dal 2023 | Scartata |
| Carry | Lo stesso su **Hyperliquid** (dal 6/2023) | Funding circa doppio di Binance | 4,34 | 9,8% | 2,08 | 0,36 | 19,9% nel 2024, 4,9% nel 2025, 1,8% nel 2026 | **Passa con riserva** |
| Carry | Differenza di funding Hyperliquid − Binance | Due mercati non allineati | 4,87 | 12,5% | −0,36 | 0,46 | Negativo nel 2026 | Scartata |
| Stat arb | Coppie cointegrate, scelta walk-forward | Ritorno alla media dei rapporti | −0,95 \| −0,69 \| −1,19 | −32% | — | −0,10 | — | Scartata: perde anche senza costi |
| Stat arb | Inversione dei residui a 5 giorni | Come sopra, su 20 monete | −1,44 | −61% | — | −0,37 | — | Scartata |
| Intraday | Trend orario lento su perpetual | Persistenza dei movimenti | 0,71 \| 1,31 \| 0,27 | 16,5% | −0,55 | 0,67 | Forte | Scartata: copia di CR-TREND |
| Intraday | **GEX + VWAP** su S&P 500 (ritorno al VWAP con GEX alto, trend con GEX negativo) | I dealer smorzano o amplificano | −0,14 scelta, −1,04 verifica | 0% | — | 0,04 | — | Scartata |
| Liquidazioni | Open interest in calo + prezzo in calo, 24h | Vendite forzate esaurite | 0,30 \| 0,25 \| 0,33 | 6% | −0,04 | 0,52 | — | Scartata |
| Liquidazioni | **DIP-24h**: rendimento a 24h sotto il 2° percentile, tenere 24h | Chi è liquidato vende sotto il valore | 0,93 \| 1,23 \| 0,66 | 20,6% | 0,40 | 0,41 | Circa zero nel 2026 | **Passa di misura** |
| Posizionamento | Contro i conti al dettaglio (rapporto long/short) | Il dettaglio sbaglia agli estremi | 0,79 \| 1,58 \| 0,50 | 32% | 0,15 | 0,12 | Solo 12 mesi di scelta | In osservazione |
| Volatilità | Vendita di varianza BTC + ETH **[S]** | Premio per il rischio di volatilità | −0,92 \| 1,31 \| −2,80 | 1,3% | — | 0,05 | Premio sparito | Scartata |
| Volatilità | DVOL come filtro sui trend | Volatilità implicita alta = pericolo | Nessuno dei 10 filtri migliora la verifica | | | | | Scartata |
| Market making | Quotare sui due lati **[I]** | Incassare lo spread | −3,7 / −4,0 pb per esecuzione | | | | | Scartata al livello base di commissioni |
| On-chain | Offerta di stablecoin in crescita | Liquidità in arrivo | 0,76 \| 0,91 \| 0,48 | 34% | 0,42 | 0,61 | — | Scartata: correlazione 0,81 con CR-TREND |
| Sentiment | Fear & Greed sopra la media a 30 giorni | Momentum dell'umore | 0,71 \| 0,87 \| 0,43 | 28% | −0,08 | 0,62 | — | Scartata |
| Stagionalità | Ore 21–23 UTC con commissioni maker **[I]** | Flussi di chiusura USA | 0,70 \| 0,46 \| 0,99 | 16% | — | 0,16 | — | Ipotesi: a 7 pb fa −1,24 |
| Eventi | Short delle nuove quotazioni, coperto con BTC | Entusiasmo iniziale che rientra | 0,26 \| 0,07 \| 0,38 | 1,3% | 0,32 | −0,23 | — | Scartata: caduta −85% |
| Funding | Long/short per funding su tutti i perpetual | Come il carry, senza spot | 0,58 \| 1,59 \| −0,14 | 15% | −0,47 | 0,34 | Sparita dopo il 2022 | Scartata |

Tre lezioni dai numeri:

- **Il carry sta finendo.** Su Hyperliquid ha reso il 19,9% nel 2024 e l'1,8% nei primi dieci mesi del 2026, contro un tasso a breve del 3–5%. Il suo Sharpe sopra 3 è reale ma ingannevole: la volatilità misurata è l'1%, mentre il rischio vero (la sede, la stablecoin, la liquidazione della gamba corta) non compare nel campione. A leva 3x la gamba corta sarebbe stata liquidata 30 volte in sei anni, a 5x 104 volte.
- **Nelle crypto i prezzi relativi seguono il trend, non tornano alla media.** Per questo l'arbitraggio statistico perde già prima dei costi, e il momentum trasversale (CR-XSMOM) funziona.
- **L'open interest non aggiunge informazione** alla regola fatta con il solo prezzo.

### 1.2 Il libro, con capacità e costi

| Strategia | Che cosa fa | Sharpe (tutto \| scelta \| verifica) | Costi ipotizzati | Capacità **[S]** | Stato nel codice |
|---|---|---|---|---|---|
| CR-TREND | Bitcoin ed Ether quando salgono da settimane | 1,02 \| 1,40 \| 0,54 | 30 pb per lato | Oltre 10 M€ | In produzione (paper) |
| CR-XSMOM | Le 5 crypto più forti tra le 20 più scambiate | 1,05 \| 1,04 \| 1,08 | 30 pb per lato | 1–3 M€ | In produzione (paper) |
| EQ-MR | S&P 500 e Nasdaq dopo una chiusura sui minimi | 0,83 \| 1,14 \| 0,33 | 5 pb + finanziamento | Oltre 10 M€ | In produzione (paper) |
| MA-TREND | Trend lento su 17 ETF | 0,17 \| 0,37 \| −0,12 | 10 pb per lato | Oltre 10 M€ | In produzione (paper) |
| DIP-24h | Compra un crollo a 24 ore sui perpetual, tiene 24 ore | 0,93 \| 1,23 \| 0,66 | 7 pb per lato | 1 M€ circa | **Solo ricerca** |
| Carry | Spot lungo + perpetual corto, quota fissa 20% | 5,39 \| 7,43 \| 3,66 (ingannevole) | Due gambe + funding | 1 M€ circa | **Solo ricerca** |
| Libro dei trade | Trade a leva sui giorni ad alta conviction (sezione 3) | 0,85 \| 1,01 \| 0,75 | 6,5 pb per lato + funding | 1 M€ circa | Modulo di rischio pronto, non collegato |

- **Scelta:** sei strategie giornaliere più il libro dei trade.
- **Motivazione:** sono le sole con Sharpe di verifica positivo, tenuta a costi doppi e correlazione tra loro abbastanza bassa.
- **Alternative scartate:** le tredici della tabella 1.1 e le ventidue delle versioni precedenti (GEX come segnale di direzione, VWAP trend, Kronos, acquisti dei dirigenti, meta-modello, e le altre), ciascuna con i suoi numeri nei file di ricerca.

---

## 2. Portafoglio: da dove viene il rendimento

### 2.1 I portafogli a confronto

Statistiche sui rendimenti mensili, aprile 2018 – ottobre 2026. "Trade 1%/2%" significa rischio dell'1% sui setup confermati e del 2% sugli eccezionali.

| Portafoglio | Sharpe (tutto \| scelta \| verifica) | CAGR | Volatilità | Caduta massima (mensile) | Mese medio | Mese mediano | Mese peggiore |
|---|---|---:|---:|---:|---:|---:|---:|
| A. Versione 2: 4 strategie, 1x | 1,19 \| 1,48 \| 0,87 | 13,8% | 8,9% | −6,4% | 1,1% | 0,6% | −3,1% |
| B. 6 strategie, 1x | 1,34 \| 1,62 \| 0,98 | 13,6% | 7,7% | −6,4% | 1,1% | 0,6% | −3,4% |
| B2. 6 strategie, 2x | 1,23 \| 1,51 \| 0,88 | 23,1% | 15,7% | −14,7% | 1,8% | 0,8% | −7,0% |
| B3. 6 strategie, 3x | 1,18 \| 1,47 \| 0,85 | 32,5% | 23,9% | −22,3% | 2,6% | 0,9% | −10,6% |
| T. Solo libro dei trade 11x, 1%/2% | 0,85 \| 1,01 \| 0,75 | 24,9% | 27,2% | −18,6% | 2,1% | 0,0% | −14,8% |
| **C1. 6 strategie 1x + trade 0,5%/1%** | **1,20 \| 1,43 \| 1,00** | **27,6%** | **19,7%** | **−10,5%** | **2,2%** | **0,4%** | **−8,4%** |
| C2. 6 strategie 1x + trade 1%/2% | 1,12 \| 1,31 \| 0,97 | 41,5% | 33,5% | −18,3% | 3,4% | 0,3% | −15,6% |
| **C3. 6 strategie 2x + trade 1%/2%** | **1,17 \| 1,38 \| 0,99** | **52,9%** | **40,7%** | **−21,8%** | **4,2%** | **0,4%** | **−16,7%** |
| C4. 6 strategie 2x + trade 1,5%/3% | 1,13 \| 1,32 \| 0,99 | 67,5% | 55,3% | −28,8% | 5,5% | 0,5% | −23,3% |
| C6. 6 strategie 3x + trade 1,5%/3% | 1,17 \| 1,35 \| 1,00 | 79,7% | 63,3% | −32,0% | 6,4% | 0,4% | −24,4% |

La colonna da guardare è il **mese mediano**: resta sotto l'1% in tutti i portafogli. Il rendimento dei profili con il libro dei trade viene da pochi mesi molto grandi, in gran parte nel 2020–2021 e nei rialzi del 2023–2024. La caduta misurata sui dati mensili sottostima quella dentro il mese.

### 2.2 Scomposizione: diversificazione, leva, AI

| Passo | Da | A | Che cosa lo produce |
|---|---|---|---|
| **Diversificazione** | Sharpe medio delle singole strategie 0,80 (0,50 in verifica) | Sharpe del portafoglio 1,34 (0,98) | Strategie poco correlate tra crypto, azioni e multi-asset |
| **Leva del conto, 2x** | CAGR 13,6% | 23,1% | Debito al tasso a breve + 1,5%; lo Sharpe scende a 1,23 |
| **Libro dei trade a leva** | CAGR 23,1% | 52,9% | Più esposizione al trend crypto, con perdita per trade limitata; lo Sharpe scende a 1,17 |
| **AI** | — | — | **Non misurabile sul passato.** Vale zero finché due libri paper in parallelo, con e senza AI, non dicono altro |

In parole: circa metà della qualità del portafoglio viene dalla diversificazione; tutto l'aumento di rendimento dalla versione 2 viene da più rischio, non da più abilità; il contributo dell'AI è un'ipotesi da verificare in avanti.

### 2.3 Quote

- **Scelta:** parità di rischio tra le strategie a rischio di mercato; al carry una quota fissa del 20%.
- **Motivazione:** la parità di rischio darebbe al carry il tetto del 60%, perché la sua volatilità misurata è quasi nulla; il suo rischio vero è la sede, e nessuno stop lo controlla. Il 20% è un giudizio, non un risultato **[S]**.
- **Alternative scartate:** parità di rischio pura (Sharpe 1,64, ma è un artefatto); carry al 30% (Sharpe 1,44, più rischio di controparte); nessun carry (Sharpe 1,23).

---

## 3. Leva

### 3.1 Due leve diverse

- **Leva del libro giornaliero** (controvalore / patrimonio): resta a 2x operativa, 3x come tetto nel codice. A 5x il conto viene dimezzato nel 20% dei casi in tre anni nello scenario prudente, a 10x nel 62% (versione 2, confermato).
- **Leva del singolo trade** (controvalore / margine isolato): fino a 30x. Qui la leva non è una scelta libera, discende dallo stop.

### 3.2 Come si calcola un trade

```
rischio          = quota di patrimonio persa se scatta lo stop          (1% confermato, 2% eccezionale)
controvalore     = rischio × patrimonio / distanza dello stop
leva             = la più alta che tiene lo stop entro il 60% della distanza dalla liquidazione
margine isolato  = controvalore / leva  ≈ 1,7 × rischio
```

Esempio su 10.000 €, setup confermato, stop a 1 × ATR = 5%: rischio 100 €, controvalore 2.000 €, leva 11x, margine 177 €, liquidazione a −8,4%. Se il prezzo crolla del 60% senza che lo stop venga eseguito, la perdita è 177 €, l'1,8% del conto. Codice: [`gerva/risk/isolated.py`](../gerva/risk/isolated.py), 11 test.

### 3.3 Quale leva sostengono i dati

1.099–1.558 trade simulati per riga su Bitcoin, Ether e Solana, 2018–2026, percorso a 5 minuti. Ingresso all'apertura dopo un giorno ad alta conviction. "R" è il guadagno in multipli del rischio.

| Stop | Leva | Distanza dalla liquidazione | Trade l'anno | R medio (tutto / verifica) | Vincenti | Perdite di fila (massimo) | Costi in R | Liquidazioni | Esito |
|---|---:|---:|---:|---|---:|---:|---:|---:|---|
| 10% | 6x | 16,7% | 62 | +0,14 / +0,11 | 48% | — | 0,01 | 0 | Sostenuta |
| 6% | 9,5x | 10,0% | 71 | +0,17 / +0,12 | 41% | 15 | 0,02 | 0 | Sostenuta |
| **1 × ATR (≈ 5%), stop mobile** | **11x** | **8,4%** | **77** | **+0,24 / +0,18** | **43%** | **17** | **0,03** | **0** | **Livello confermato** |
| 2,7% | 20x | 4,5% | 104 | +0,25 / +0,12 | 26% | — | 0,05 | 0 | Sostenuta, più debole |
| **1,7%** | **30x** | **2,8%** | **129** | **+0,36 / +0,20** | **18%** | **29** | **0,08** | **0** | **Solo eccezionali, rischio dimezzato** |
| 1,2% | 40x | 2,0% | 155 | +0,33 / +0,20 | 13% | 33 | 0,11 | 0 | Al limite: 87% dei trade in perdita |
| 0,9% | 50x | 1,5% | 183 | +0,18 / +0,13 | 9% | 53 | 0,14 | 0 | **Non sostenuta** |
| 0,4% | 50x | 1,5% | 249 | −0,21 / −0,28 | 4% | — | 0,33 | 0 | **Non sostenuta**: i costi valgono un terzo dello stop |

- Nessuna liquidazione in otto anni fino a 50x: lo stop scatta sempre prima. La leva alta è quindi praticabile.
- Oltre 30x il guadagno medio non cresce più e le serie di perdite diventano ingestibili: 53 di fila a 50x.
- **Setup eccezionali.** Con conviction sopra 0,75 il guadagno medio per trade è circa doppio (R +0,40 contro +0,19 a 11x; +1,07 contro +0,20 a 30x), in entrambi i periodi. Sono 17–24 trade l'anno: il campione è piccolo **[S]**.
- Sotto 0,60 di conviction il rendimento atteso è nullo. Lo short non paga: R di verifica negativo in tutte e tre le varianti.

### 3.4 Dal trade al conto: rendimento, caduta, rovina

Monte Carlo a blocchi mensili, 3 anni. Scenari: base; prudente (metà del guadagno medio); solo verifica (trade dal 2023); stress (uno stop su dieci salta e si perde l'intero margine, più un evento l'anno in cui tre posizioni perdono il margine insieme).

| Schema (rischio confermato / eccezionale) | Scenario | Rendimento annuo mediano | Caso peggiore (5%) | Caduta tipica | Caduta nel 5% peggiore | P(−30%) | P(conto dimezzato) |
|---|---|---:|---:|---:|---:|---:|---:|
| 11x, 0,5% / 1% | base | 15% | 2% | −11% | −20% | 0% | 0% |
| | prudente | 8% | −5% | −15% | −27% | 1% | 0% |
| | stress | 8% | −5% | −16% | −29% | 2% | 0% |
| **11x, 1% / 2%** | base | 32% | 3% | −22% | −37% | 3% | 0% |
| | prudente | 15% | −10% | −28% | −48% | 12% | 1% |
| | solo verifica | 34% | −1% | −27% | −45% | 8% | 1% |
| | stress | 17% | −10% | −29% | −50% | 14% | 2% |
| 11x, 1,5% / 3% | base | 49% | 2% | −31% | −50% | 9% | 1% |
| | prudente | 22% | −16% | −39% | −63% | 27% | 7% |
| 11x, 2% / 4% | base | 66% | 1% | −39% | −61% | 17% | 4% |
| | prudente | 29% | −21% | −49% | −74% | 39% | 16% |
| 30x, 0,5% / 1% | base | 45% | 6% | −26% | −41% | 3% | 0% |
| | prudente | 23% | −9% | −34% | −53% | 15% | 2% |
| | solo verifica | 26% | −8% | −32% | −52% | 15% | 2% |
| 30x, 1% / 2% | base | 90% | 6% | −47% | −67% | 20% | 5% |
| | prudente | 36% | −22% | −58% | −80% | 44% | 20% |
| 50x, 1% su tutti | base | 9% | −46% | −74% | −93% | 71% | 49% |

- **Scelta:** rischio 1% / 2% a 11x come massimo; 0,5% / 1% per partire. Il livello a 30x è ammesso solo sugli eccezionali e con rischio 0,5%.
- **Motivazione:** è l'ultimo schema in cui la probabilità di dimezzare il conto resta sotto il 2% in tutti gli scenari.
- **Alternative scartate:** 1,5% / 3% (7% di probabilità di dimezzare nello scenario prudente); 30x con rischio pieno (20%); 50x (49% già nello scenario base).

### 3.5 Stress sui dati reali

Quanto spesso il prezzo ha percorso l'intera distanza di liquidazione, cioè che cosa succede se la sede non risponde e lo stop non viene eseguito **[F]**:

| Leva | Distanza dalla liquidazione | Bitcoin: in 1 ora | in 4 ore | in 24 ore | Solana: in 24 ore |
|---:|---:|---:|---:|---:|---:|
| 5x | 19,5% | 0,00% | 0,03% | 0,3% | 1,2% |
| 10x | 9,5% | 0,04% | 0,3% | 3,3% | 9,1% |
| 15x | 6,2% | 0,2% | 1,1% | 8,3% | 21,7% |
| 20x | 4,5% | 0,4% | 2,5% | 14,7% | 33,8% |
| 30x | 2,8% | 1,4% | 6,6% | 28,6% | 51,9% |
| 50x | 1,5% | 5,7% | 18,9% | 51,4% | 72,0% |

| Evento reale | Bitcoin | Ether | Solana | Effetto su un trade a margine isolato |
|---|---|---|---|---|
| 12 marzo 2020 | −44% in giornata, −12,7% in 5 minuti | −48%, −12,9% | — | Stop saltato: si perde il margine (≈ 1,7 × rischio) |
| 19 maggio 2021 | −30%, −9,8% | −44%, −16,5% | −53%, −16,5% | Come sopra |
| 5 agosto 2024 | −16%, −4,5% | −22%, −9,7% | −21%, −6,2% | Stop eseguito con slippage a 11x; margine perso a 30x |
| 10 ottobre 2025 (prima attivazione dell'ADL su Hyperliquid) | −16%, −7,5% | −21%, −6,7% | −24%, −8,7% | Come sopra; possibile chiusura forzata anche di posizioni in guadagno |

Il caso peggiore del libro dei trade è quindi noto prima: tutte le posizioni aperte perdono il margine insieme. Con il 6% di rischio aperto e la leva "sicura" è circa il **10% del conto**; il tetto sul margine totale lo ferma comunque al **15%**.

**Meno leva dalla sede significa meno protezione dal gap, non più.** Il margine di un trade vale rischio / (stop × leva). Con stop al 3%: a 20x è 1,7 volte il rischio; a 10x, 3,3 volte; a 2x, 16 volte. Su una sede a 10x il tetto del 15% di margine basta quasi sempre; su una sede a 2x riduce il libro a circa un terzo dei trade, e la sola difesa dal gap resta lo stop.

### 3.6 I limiti nel codice

| Limite | Valore | Dove |
|---|---|---|
| Rischio per trade | 1% confermato, 2% eccezionale; mai oltre 2% | `isolated.py` |
| Leva per trade | Minimo tra: leva sicura per lo stop, tetto del livello (15x o 30x), tetto della sede, 30x assoluto | `isolated.py` |
| Stop | Entro il 60% della distanza dalla liquidazione; mobile, si sposta solo a favore | `isolated.py` |
| Rischio aperto totale | 6% del patrimonio | `isolated.py` |
| Margine totale | 15% del patrimonio: è la perdita massima del libro in un solo evento | `isolated.py` |
| Controvalore totale dei trade | 1,5 volte il patrimonio | `isolated.py` |
| Trade aperti | 4 | `isolated.py` |
| Interruttore di giornata | −3%: nessun nuovo trade; −5%: si chiude tutto fino a domani | `isolated.py` |
| Leva del libro giornaliero | 2x operativa, 3x assoluta | `risk/engine.py` |
| Scalini di caduta del conto | −10% dimezza, −15% un quarto, −20% chiude tutto e resta fermo | `risk/engine.py` |
| Arresto di emergenza | Manuale o automatico; si riaccende solo a mano | `risk/engine.py` |

Quando il motore di rischio del conto è in stato ridotto, il rischio per trade si dimezza; quando è fermo, nessun trade parte.

---

## 4. Validazione e criteri per il denaro reale

### 4.1 Che cosa dice la statistica oggi

- **Prove contate: 812.** Lo Sharpe atteso della migliore tra 812 prove senza alcuna abilità è 1,47.
- **Deflated Sharpe: 0,38** per il portafoglio a sei strategie (0,20 per quello a quattro), contro una soglia di 0,95. L'evidenza storica **non basta** a dire che il vantaggio è reale.
- Le prove sul libro dei trade sono 42, più 9 schemi; la migliore riga ha t = 3,6, da scontare per la selezione.
- I dati dei trade sono prezzi spot a 5 minuti usati al posto dei perpetual; il carry prima di giugno 2023 usa il funding di Binance, che un italiano non poteva incassare.

Per questo il passaggio al denaro reale dipende dal paper trading, non dal backtest.

### 4.2 Cancelli numerici

**Libro giornaliero** (già nel codice, `gerva/live/gates.py`): 90 giorni di paper; disponibilità del ciclo ≥ 99%; nessun ordine non riconciliato; caduta massima ≤ 10%; probabilità che lo Sharpe vero sia positivo ≥ 60%; scostamento dal backtest sugli stessi giorni ≤ 3 punti; costi reali ≤ 1,5 volte quelli ipotizzati.

**Libro dei trade** (da aggiungere al codice):

| Cancello | Soglia | Se non passa |
|---|---|---|
| Trade chiusi in paper o testnet | ≥ 40 | Si continua in paper |
| R medio realizzato | > 0, e ≥ metà di quello simulato sugli stessi giorni | No-go |
| Slippage medio sullo stop | ≤ 10 pb | Si allarga lo stop o si scende di leva |
| Stop presenti sulla sede a ogni controllo | 100% | No-go: è la protezione principale |
| Liquidazioni | 0 | No-go e revisione |
| Perdita massima su un trade | ≤ margine isolato | No-go: il presupposto è violato |
| Caduta massima del libro | ≤ 20% | Rischio per trade dimezzato |
| Prova dell'arresto di emergenza e dell'interruttore di giornata | Eseguita con esito positivo | No-go |

**Dopo il via**, in ordine: 30 giorni a rischio 0,25% per trade con 5–10% del capitale sulla sede; poi 0,5% / 1%; il profilo 1% / 2% solo dopo 100 trade reali con R medio positivo. Si torna indietro di uno scalino se la caduta supera il 15% o se dopo 60 trade l'R medio è negativo.

---

## 5. Sedi, custodia, infrastruttura

Dettaglio e fonti in [`STRUTTURA.md`](../research/v5/v4/STRUTTURA.md).

### 5.1 Sedi di esecuzione

| Sede | Stato per un residente italiano al dettaglio | Leva massima | Commissioni maker / taker | Rischio di controparte | Ruolo |
|---|---|---|---|---|---|
| **Interactive Brokers Ireland** | Autorizzata **[F]** | CFD: 30 / 20 / 10 / 5 / 2; futures a margine di borsa | Variabili | Broker quotato | Azioni, ETF, indici, cassa |
| **Kraken Pro** (entità CySEC) | Autorizzata MiFID; disponibilità in Italia da verificare a schermo | **10x**, poi 5x / 3,3x / 2x al crescere della posizione **[F]** | Circa 2 / 5 pb (non verificato) | Gruppo USA | Perpetual regolamentati |
| **OKX Europe** (MFSA) | Autorizzata MiFID **[F]** | **10x** | 2 / 5 pb | Struttura "a 5 anni" non confermata dai regolatori | Alternativa a Kraken |
| Coinbase UE | Autorizzata; Italia citata da una sola fonte | 10x | Non verificato | Società quotata USA | Riserva |
| **Hyperliquid** | Non autorizzata nello SEE; non bloccata; Italia non tra i paesi vietati (fonti secondarie) | Fino a 40x su Bitcoin | 1,5 / 4,5 pb **[F]** | Nessuna vigilanza; 24–27 validatori, circa 49% dello stake alla fondazione; casi JELLY e POPCAT | Quota a perdere, dopo parere legale |
| Binance | Chiusa a nuovi conti e ordini per residenti SEE dal 1/7/2026 **[F]** | — | — | — | Esclusa |
| Bybit EU | Solo spot e margine | — | — | Furto da 1,5 miliardi di dollari nel 2025 | Esclusa |
| Bitget, Deribit, dYdX | Senza licenza o non verificato | — | — | — | Escluse |
| Alpaca | Solo paper | — | — | — | Prove |

Il quadro giuridico **[F]**: i derivati sono strumenti MiFID II, non MiCA. La delibera Consob 20976/2019 limita i CFD su crypto a 2x per i clienti al dettaglio. Il 24 febbraio 2026 l'ESMA ha scritto che i perpetual ricadono "probabilmente" in quelle misure: il 10x delle sedi europee può scendere a 2x.

- **Scelta:** IBKR per azioni, ETF e cassa; Kraken (o OKX Europe) per il libro dei trade a 10x; Hyperliquid solo per il livello a 30x e per il carry, con non più del 10–15% del capitale e dopo un parere legale.
- **Motivazione:** il livello confermato lavora a 11x, quindi sta dentro il 10x regolamentato con una perdita trascurabile. Se il tetto scende a 2x, un trade impegna il 10–20% del patrimonio in margine invece del 2%: il tetto del 15% sul margine totale lascia spazio a un trade alla volta, e si perde la protezione dal gap che il margine isolato dà a leva alta (sezione 3.5). A 2x il libro dei trade si riduce a circa un terzo.
- **Alternative scartate:** tutto su Hyperliquid (nessuna tutela, accesso revocabile, zona grigia); status di cliente professionale (servono 500.000 € o un anno di lavoro nel settore finanziario); sedi offshore con VPN (viola i termini d'uso, e il conto può essere congelato).
- **Costo mensile:** nessun canone; commissioni sul controvalore.
- **Passi:** aprire IBKR e Kraken; verificare a schermo leva e commissioni per l'Italia; chiave API di solo trading con lista di IP; conto demo prima del reale.

### 5.2 Custodia e conti

- **Chiavi API:** solo trading, mai prelievo, vincolate all'IP del server. Una chiave per strategia dove la sede lo permette.
- **Sottoconti:** uno per il libro giornaliero crypto, uno per il libro dei trade, uno per il carry. Un errore in uno non tocca gli altri.
- **Hyperliquid:** chiave principale su hardware wallet, mai su un computer; sul server solo un "agent wallet" che firma gli ordini, con scadenza a 30–90 giorni. Che un agent non possa prelevare va provato su testnet prima di depositare (la documentazione letta non lo dice in modo esplicito).
- **Quanto capitale sulla sede:** il 20–30% a regime, cioè due o tre volte la somma dei margini aperti; il resto in banca o su IBKR. Con il margine isolato tenere di più sulla sede non aiuta il motore e aumenta solo il rischio di controparte.
- **Depositi e prelievi:** sempre manuali, mai avviati dal software; prelievi solo verso indirizzi in lista bianca e verso il conto bancario intestato a te; ogni movimento annotato lo stesso giorno, perché serve al fisco.
- **Alternativa migliore:** custodia qualificata presso terzi; ha senso sopra i 500.000 €.

### 5.3 Stack tecnico

| Tema | Scelta | Alternativa migliore | Costo al mese **[S]** |
|---|---|---|---:|
| Server | Un VPS in Europa, 2 vCPU e 4 GB (Hetzner CX23) | Due VPS di fornitori diversi, il secondo solo come guardiano | 6–7 € / 12–40 € |
| Vicinanza alle API | Irrilevante: le decisioni sono su barre da 5 minuti a giornaliere, e l'esecuzione mediana su Hyperliquid è circa 0,9 secondi anche da Tokyo **[F]** | Tokyo, se un giorno si scendesse sotto il minuto | — |
| Linguaggio | Python con asyncio, lo stesso codice per ricerca, paper e reale | Rust per il solo percorso di esecuzione, se servisse market making | 0 |
| Dati | SQLite per stato, ordini e audit; Parquet per le serie | Postgres con TimescaleDB quando i processi scrittori saranno più di uno | 0 |
| Coda di messaggi | Nessuna: un processo solo | Redis Streams o NATS quando segnali ed esecuzione staranno su macchine diverse | 0 |
| Riavvio automatico | systemd con `Restart=always` e il supervisore già nel repository | Docker Compose con immagini fissate | 0 |
| Monitoraggio | Battito ogni minuto a healthchecks.io; avvisi su Telegram per ordini, errori, cadute | Prometheus e Grafana | 0–10 € |
| Failover | Lo stop sta **sulla sede**, non sul server; il secondo VPS avvisa e mette in "sola riduzione", non opera mai in parallelo | — | — |
| Interruttore lato sede | Hyperliquid `scheduleCancel`; Kraken `cancelallordersafter` **[F]** | — | 0 |
| Riconciliazione | Ogni minuto posizioni e ordini della sede contro lo stato interno; se divergono, niente nuove aperture | — | 0 |
| Log e audit | Registro a sola aggiunta con hash concatenati; copia giornaliera fuori dal server | Archiviazione non modificabile | 1–5 € |
| Backup | Copia cifrata ogni ora; prova di ripristino ogni mese | Replica continua | 1–3 € |

Un punto da provare su testnet prima di tutto: se un "cancella tutto" automatico rimuove anche gli stop protettivi. Se sì, l'interruttore lato sede va usato solo mentre ci sono ordini d'ingresso in attesa.

### 5.4 Sicurezza

- **Chiavi:** mai nel repository; cifrate con sops e age, o in variabili d'ambiente del servizio; rotazione ogni 90 giorni.
- **Separazione dei ruoli:** chi fa ricerca non ha chiavi; il motore ha chiavi di solo trading; i prelievi li fai solo tu, da un altro dispositivo.
- **Protezione dai bug:** controlli prima di ogni ordine, nel codice e non modificabili a caldo (dimensione massima, banda di prezzo, un ordine per simbolo e giorno); arresto di emergenza; stesso codice in paper e in reale.
- **Server:** accesso solo con chiave SSH, firewall chiuso, dashboard mai esposta su Internet (si raggiunge con Tailscale o WireGuard), aggiornamenti automatici di sicurezza.
- **Dipendenze:** versioni fissate con hash.
- **Attacchi tramite l'AI:** il testo delle notizie è trattato come dato non fidato; un'istruzione nascosta in una notizia non ha effetto (c'è un test).
- **Incidente:** arresto di emergenza, revoca delle chiavi dalla sede, verifica delle posizioni a mano, poi analisi.

---

## 6. Veicolo giuridico e fiscale

| Opzione | Fattibile ora? | Costo l'anno **[S]** | Tasse | Giudizio |
|---|---|---:|---|---|
| **Persona fisica**, regime dichiarativo | Sì | 300–800 € di commercialista | Crypto 33% dal 2026 **[F]**; derivati su crypto 26% secondo la circolare 30/E/2023, che però non nomina i perpetual; IVCA 2‰; quadri RT e RW | **Scelta** |
| SRL o SRLS | Sì, ma antieconomica | 2.500–4.500 € | IRES 24% + IRAP, poi 26% sui dividendi: circa 44% in tutto | Sopra i 300–500.000 € |
| Società semplice | Sì | 1.000–2.000 € | Trasparenza: tassata sui soci | Nessun vantaggio a questo stadio |
| Trust | Sì | Migliaia di euro | Complessa | Serve a proteggere un patrimonio, non a fare trading |
| Struttura offshore | No | — | Le norme su società estere controllate ed esterovestizione la riportano in Italia | Non funziona per un residente |
| Fondo (SGR, SICAF, FIA) | No | Capitale minimo 50.000 € e autorizzazione | — | Solo con capitale di terzi e investitori professionali |

**Denaro altrui.** Gestire denaro di terzi senza autorizzazione è reato: art. 166 TUF, reclusione da 1 a 8 anni **[F]**. Gratuità e cerchia familiare non sono una garanzia. Secondo l'ESMA il copy trading con esecuzione automatica è gestione di portafogli. La struttura "Friends and Family" di IBKR non crea alcuna esenzione nel diritto italiano.

- **Scelta:** conto intestato a te. Il denaro dei familiari entra solo come donazione o prestito infruttifero scritto, senza partecipazione agli utili.
- **Per stadio:** fino a 50.000 € persona fisica; 50–500.000 € persona fisica, valutando la SRL con il commercialista; oltre, o con denaro di terzi, un avvocato esperto di gestione collettiva prima di qualsiasi passo.

**Da far verificare.** Al commercialista: aliquota applicabile ai perpetual (26% o 33%); se le perdite sui derivati si compensano con i guadagni sulle crypto; come dichiarare un wallet Hyperliquid; trattamento delle conversioni in USDC, che sono eventi imponibili. All'avvocato: liceità dell'uso di Hyperliquid per un residente; forma corretta per il denaro dei familiari; confine con l'art. 166 se un familiare delega l'operatività.

**Costi totali di esercizio [S]:** 60–80 € al mese al minimo, 125–260 € nella versione raccomandata. Su 10.000 € sono dal 7% al 30% l'anno, da sottrarre ai rendimenti della sezione 2. Fino a 50.000 € vale tenere la versione minima.

---

## 7. Livello AI

Gli agenti propongono e filtrano; il motore di rischio deterministico decide. Codice in [`gerva/ai/`](../gerva/ai/) e [`gerva/agents/`](../gerva/agents/).

| Ruolo | Modello | Frequenza | Che cosa fa | Che cosa non può fare |
|---|---|---|---|---|
| Scout | Claude Haiku 5.5 | Ogni 6 ore, e a ogni evento in calendario | Sceglie al massimo 5 voci che possono cambiare il rischio | Cercare da solo; citare ciò che non ha ricevuto |
| Analista | Claude Opus 5.5 | Ogni 6 ore | Per ogni voce propone "riduci" o "veto" su una strategia o su un trade, citando la fonte | Proporre aumenti; produrre numeri |
| Scettico | Claude Opus 5.5, chiamata separata | Ogni 6 ore | Riceve le stesse fonti senza il parere dell'analista | Vedere il parere dell'analista |
| **Rischio per trade** (nuovo) | Codice + parere dei due modelli | Prima di ogni ingresso | Moltiplica il rischio del trade per un fattore tra 0 e 1 se c'è un evento entro 24 ore (banca centrale, dato macro, scadenza, sblocco di token) | Superare 1; toccare stop, leva o limiti |
| Regime | Codice | Ogni giro | Classifica il mercato in calmo, normale, teso, crisi | Scalare l'esposizione: provato, peggiora lo Sharpe da 1,18 a 1,10 |
| Decadimento | Codice | Ogni giorno | Confronta ogni strategia con l'attesa; dimezza o mette in pausa | Riattivare una strategia: lo fai tu |
| Ricercatore | Claude Opus 5.5, su richiesta | Settimanale | Propone nuove ipotesi come schede; il motore le misura, il validatore le attacca | Scrivere codice di strategia o toccare il libro |

- **Aggiornamento dei parametri.** Volatilità, quote e leva si ricalcolano ogni giorno sui soli dati passati, in modo deterministico. Soglie di conviction, livelli di rischio e limiti non cambiano mai da soli: una modifica passa da una proposta scritta, dal validatore e dalla tua approvazione.
- **Fonti:** comunicati di Federal Reserve, BCE, SEC, ESMA; CoinDesk; indice Fear & Greed; FRED; funding e open interest pubblici; DVOL. Tutte gratuite. I flussi di opzioni a pagamento (da 150 dollari al mese) restano fuori: costerebbero il 15% l'anno del conto senza evidenza di rendimento.
- **Latenza:** 20–60 secondi a passata, irrilevante per decisioni giornaliere. Il parere sul singolo trade usa l'ultima passata: nessuna chiamata al modello sta sul percorso dell'ordine.
- **Costi [S]:** circa 0,05 dollari a passata, 6 dollari al mese; con il ricercatore settimanale 15–20 dollari. Tetto di spesa impostato dal fornitore.
- **Contro le allucinazioni** (regole nel codice, con test): le fonti le raccoglie il codice; ogni proposta deve citare un identificativo consegnato; il modello sceglie tra tre parole e non scrive numeri; risposta non valida significa astensione; servono due pareri concordi; il testo delle fonti è dato non fidato.
- **Contro il sovradattamento:** il livello AI non ha parametri stimati sui rendimenti, e un modello linguistico non si può validare sul passato perché lo conosce. Si misura solo in avanti, con due libri paper in parallelo: cancello per tenerlo acceso, dopo 90 giorni caduta non peggiore e rendimento non inferiore di oltre 1 punto rispetto al libro senza AI.

---

## 8. Dashboard

Console in [`dashboard/`](../dashboard/): dieci pagine, senza librerie esterne, due livelli di lettura (Semplice ed Esperto), glossario, conto aggiornato ogni 5 secondi e ricerca ogni 10 minuti. Pagine: Panoramica, Performance, Esposizione, Rischio, Strategie, Ordini, Sistema, AI, Ricerca, Come funziona. Avvio: `python -m dashboard.server`, poi `http://127.0.0.1:8787`.

In aggiornamento per questa versione: pagina "Leva per trade" (tabella stop / leva / esito, schemi di rischio per scenario, stress), sezione "Il fondo intero" con la scomposizione del rendimento, tabella delle strategie provate con il loro decadimento, tabella delle sedi. I dati vengono da `research/v5/quant_v4.json`.

![Panoramica in modalità Semplice (dati di esempio)](img/dashboard-v2-semplice-panoramica.png)

---

## 9. Architettura del motore e stato del codice

```
dati ─► 6 strategie giornaliere ─► quote ─► leva 2x ─┐
     └► conviction ─► libro dei trade (isolated.py) ─┼─► overlay AI [0,1] ─► motore di rischio ─► ordini ─► sede
                                                     │                        (ultima parola)       (stop sulla sede)
                                          registro a hash, riconciliazione, supervisore, dashboard
```

| Modulo | Stato |
|---|---|
| Motore di rischio del conto, ordini idempotenti, supervisore, registro | Fatto e testato |
| Quattro strategie giornaliere nel ciclo paper | Fatto |
| Libro dei trade: ammissione, limiti, stop mobile, interruttore di giornata | Fatto e testato (11 test) |
| Ciclo paper del libro dei trade (`python -m gerva trades`), su barre giornaliere, registro interno | Fatto e testato (5 test); **non ancora dentro il ciclo principale né verso una sede** |
| DIP-24h e carry | **Solo ricerca**: non sono nel motore |
| Livello AI su strategie | Fatto; moltiplicatore sul singolo trade: previsto dall'interfaccia, **non collegato** |
| Adattatori: Alpaca | Provato solo contro un servizio finto |
| Adattatori: IBKR, Kraken, Hyperliquid | **Da scrivere** |
| Due libri paper in parallelo (con e senza AI) | **Da costruire** |
| Liquidità ferma in un fondo monetario (+1,1 punti l'anno) | **Da fare** |

---

## 10. Roadmap

| Fase | Durata | Che cosa | Criterio per passare |
|---|---|---|---|
| 0 | 2 settimane | Adattatore Kraken demo e Hyperliquid testnet; libro dei trade collegato al ciclo; prova che lo stop resta sulla sede e che l'agent non può prelevare | Tutti i test verdi; stop presente al 100% dei controlli |
| 1 | 90 giorni | Paper: libro giornaliero, libro dei trade, due libri con e senza AI | Cancelli della sezione 4.2 |
| 2 | In parallelo alla fase 1 | Commercialista e avvocato con le domande della sezione 6; apertura di IBKR e Kraken | Pareri scritti |
| 3 | 30 giorni | Reale a rischio 0,25% per trade, 5–10% del capitale sulla sede | R medio positivo, nessun incidente operativo |
| 4 | 3–6 mesi | Profilo prudente C1 (0,5% / 1%) | 100 trade reali, caduta entro il 15% |
| 5 | Poi | Profilo massimo C3 (1% / 2%, libro giornaliero a 2x) | Decisione tua, con i dati reali davanti |
| — | Dicembre 2026 | Ricontrollare la legge di bilancio 2027 e la posizione ESMA sulla leva | — |

---

## Riepilogo di una pagina

- **Obiettivo chiesto:** 20–30% al mese. **Che cosa sostengono i dati:** in media 2,2% al mese nel profilo prudente e 4,2% in quello massimo (simulato, scenario base); circa la metà nello scenario prudente. Il mese tipico resta sotto l'1%: il rendimento arriva in pochi mesi grandi.
- **Come:** sei strategie giornaliere poco correlate (Sharpe 1,34) più un libro di trade a leva sui giorni ad alta conviction.
- **Leva:** 2x sul libro giornaliero; 11x per trade sui setup confermati, 30x sugli eccezionali, sempre a margine isolato, con rischio dell'1–2% per trade. 50x respinta: 9% di trade vincenti e 53 perdite di fila.
- **Rischio:** nel profilo massimo caduta tipica −19%, −35% nel 5% dei casi peggiori, probabilità di dimezzare il conto fino al 4,5% nello scenario prudente. Caso peggiore del libro dei trade in un solo evento: circa −10%, mai oltre −15%.
- **Evidenza:** 812 prove, Deflated Sharpe 0,38 contro una soglia di 0,95. Promettente, non provato.
- **Sedi:** IBKR, più Kraken o OKX Europe a 10x; Hyperliquid solo come quota a perdere.
- **Veicolo:** persona fisica; denaro dei familiari solo come donazione o prestito.
- **Costi fissi:** 60–260 € al mese, cioè dal 7% al 30% l'anno su 10.000 €.
- **AI:** filtra e riduce, non decide; il suo valore si misura solo in paper.
- **Prima del denaro reale:** 90 giorni di paper e almeno 40 trade con i cancelli della sezione 4.2.

## I primi cinque passi

1. **Scrivere l'adattatore per Kraken demo e Hyperliquid testnet** e portarvi il libro dei trade (oggi gira in paper interno con `python -m gerva trades`), con lo stop che nasce insieme all'ordine.
2. **Provare su testnet le due ipotesi di sicurezza**: l'agent non può prelevare; il "cancella tutto" non rimuove gli stop.
3. **Avviare i 90 giorni di paper** con i due libri in parallelo, con e senza AI.
4. **Portare al commercialista e all'avvocato** le domande della sezione 6, prima di depositare un euro.
5. **Aprire IBKR e Kraken** e verificare a schermo leva, commissioni e disponibilità per l'Italia.

## Fonti principali

Elenco completo, con link e date di consultazione, in [`STRUTTURA.md`](../research/v5/v4/STRUTTURA.md) (50 fonti) e in [`RISULTATI.md`](../research/v5/v4/RISULTATI.md).

- ESMA, dichiarazione pubblica del 24 febbraio 2026 sui perpetual e le misure sui CFD.
- Consob, delibera 20976 del 20 giugno 2019 (limiti di leva sui CFD).
- Agenzia delle Entrate, circolare 30/E del 27 ottobre 2023 (cripto-attività).
- Legge 207/2024, art. 1 comma 24 (aliquota al 33% dal 2026).
- Testo unico della finanza, art. 166 (abusivismo).
- Hyperliquid, documentazione ufficiale: commissioni, `scheduleCancel`, margine isolato, API wallet.
- Kraken, pagina di supporto sui limiti di leva per lo SEE (aggiornata al 30 ottobre 2026) e `cancelallordersafter`.
- Dati: archivio pubblico Binance, API pubblica Hyperliquid, Deribit DVOL, SqueezeMetrics GEX, alternative.me, DefiLlama, Coinmetrics, Yahoo, FRED.
- Bailey e López de Prado (2014), *The Deflated Sharpe Ratio*; Blitz, Huij e Martens (2011), *Residual Momentum*; Lopez-Lira e Tang (2023), sui segnali da notizie con modelli linguistici.
