# A6 — Trade guidati da eventi (v5) — tutto SIMULATO

Analista A6. Dati reali (Binance perp USDT-M: 5m per BTC/ETH/SOL, 1h per 36 monete e per 836 nuove quotazioni; funding reale), nulla è stato negoziato. Misura: R = P&L netto / distanza dello stop, su percorso intraday, costi del brief (4,5+2 pb per lato, +5 pb sugli stop, funding reale). Scelta ≤ 2022, verifica ≥ 2023. Stop standard = 1,5 × σ oraria (14 giorni precedenti) × √ore di tenuta. **199 varianti provate.**

## 1. Risposta in breve

1. **FATTO.** Su nove famiglie di eventi, otto non danno nulla di negoziabile ai costi taker: dati macro USA, fine settimana, fine mese, scadenze opzioni, regolamento del funding, grandi mosse, depeg, ore 21–23. Quasi tutte hanno R medio tra −0,1 e +0,05.
2. **FATTO.** L'unica che regge in scelta e in verifica è lo **short delle nuove quotazioni 24 ore dopo l'esordio** (LISTING-SHORT): +0,16 R per trade, t = 3,2, 128 trade l'anno. È in calo (da +0,47 R nel 2020 a +0,07 nel 2026) e **non è eseguibile da un retail italiano su Binance**.
3. **FATTO.** DIP-24h, misurato in R con uno stop vero, è quasi nullo: +0,044 R, t = 1,25. Un filtro che sembrava fortissimo («crollo isolato», t ≈ 7) era un errore di informazione futura: l'ho trovato e scartato (§5).
4. **STIMA.** Verso il 30% al mese: LISTING-SHORT porterebbe N·(R̄/σ_R)² del fondo da circa 1,5 a circa 3,1 (servono 6,3). È metà strada sulla carta, a Kelly pieno, e solo se la sede esiste.

## 2. Tabella dei risultati (R medio per trade; t robusto al raggruppamento degli eventi contemporanei)

| Famiglia / regola | n | eventi/anno | R tutto (t) | R scelta | R verifica | costi ×2 | ritardo +1 | Esito |
|---|---:|---:|---|---:|---:|---:|---:|---|
| CPI+NFP+FOMC: long 24h prima | 625 | 32 | −0,001 (0,0) | +0,052 | −0,039 | −0,031 | +0,005 | nullo |
| CPI+NFP+FOMC: seguo i primi 30m, 24h | 623 | 32 | +0,010 (0,2) | +0,003 | +0,015 | −0,020 | +0,009 | nullo |
| CPI+NFP+FOMC: seguo i primi 5m, 1h | 621 | 32 | −0,136 (−2,2) | −0,006 | −0,229 | −0,290 | −0,160 | perde |
| CPI+NFP+FOMC: contro i primi 5m, 1h | 621 | 32 | −0,268 (−4,6) | −0,232 | −0,293 | −0,424 | −0,218 | perde |
| FOMC: seguo i primi 30m, 24h | 156 | 8 | +0,229 (1,9) | +0,015 | +0,378 | +0,200 | +0,227 | solo verifica, 8/anno |
| Fine settimana: long sab 00 → lun 00 | 1027 | 52 | +0,033 (1,2) | +0,020 | +0,042 | +0,013 | +0,030 | nullo |
| Gap CME BTC ≥1%: chiudo il gap | 180 | 27 | −0,167 (−3,1) | −0,088 | −0,248 | −0,202 | −0,147 | perde |
| **Gap CME BTC ≥1%: a favore, 24h** | 180 | 27 | **+0,151 (2,1)** | +0,111 | +0,194 | +0,119 | +0,153 | in osservazione |
| Ultimo giorno del mese, long | 237 | 12 | −0,101 (−1,6) | +0,057 | −0,214 | −0,130 | −0,089 | nullo |
| Primo giorno del trimestre, long | 78 | 4 | +0,240 (1,8) | +0,218 | +0,254 | +0,210 | +0,218 | 4 eventi/anno |
| Scadenza mensile Deribit: long 24h prima | 238 | 12 | −0,079 (−0,9) | +0,112 | −0,218 | −0,108 | −0,072 | nullo |
| Scadenza mensile Deribit: long 24h dopo | 238 | 12 | +0,005 (0,2) | +0,124 | −0,080 | −0,023 | −0,004 | nullo |
| Ore 21–23 UTC long, taker | 7187 | 365 | −0,066 (−5,3) | −0,078 | −0,059 | −0,166 | −0,082 | perde |
| Ore 21–23 UTC, maker in entrata e uscita (1,5 pb) | 7017 | 365 | −0,016 (−0,8) | −0,037 | −0,002 | −0,048 | −0,026 | nullo |
| Funding ≥0,05%: short 1h prima → 1h dopo | 10440 | — | −0,070 (−3,5) | −0,072 | −0,064 | −0,124 | −0,129 | perde |
| Funding ≤−0,02%: long 1h prima → 7h dopo | 11859 | — | −0,011 (−0,9) | −0,002 | −0,019 | −0,047 | −0,016 | nullo |
| Crollo z<−3: inversione 24h | 1130 | — | −0,063 (−0,8) | −0,090 | −0,045 | −0,089 | −0,028 | nullo |
| Balzo z>+3: inversione 24h | 1999 | — | −0,122 (−3,7) | −0,109 | −0,129 | −0,147 | −0,137 | perde |
| Balzo z>+3: continuazione 24h | 1999 | — | +0,097 (2,0) | +0,103 | +0,093 | +0,073 | +0,084 | debole |
| DIP-24h base (2° percentile), long 24h | 4788 | — | +0,044 (1,25) | +0,030 | +0,051 | +0,024 | +0,041 | debole |
| DIP-24h, ingresso maker 1σ sotto | 3216 | — | +0,087 (1,9) | +0,085 | +0,088 | +0,074 | +0,069 | debole |
| DIP-24h + funding >0,03% | 472 | — | +0,052 (0,5) | −0,038 | +0,206 | +0,037 | +0,092 | nullo |
| Depeg >0,5%: long BTC/ETH/SOL 24h | 109 | 6 | +0,192 (1,4) | +0,371 | +0,147 | +0,162 | +0,166 | troppo raro |
| **Nuove quotazioni: short a +24h, stop 15%, 168h** | 836 | 128 trade | **+0,158 (3,2)** | +0,353 | +0,118 | +0,148 | +0,162 | **tenuto** |
| Nuove quotazioni: short se le prime 24h < −20% | 110 | 17 trade | +0,637 (4,3) | +0,294 (n=13) | +0,684 | +0,627 | +0,586 | IPOTESI |

Per anno, LISTING-SHORT (R medio): 2020 +0,47 · 2021 +0,30 · 2022 +0,23 · 2023 +0,08 · 2024 +0,21 · 2025 +0,13 · 2026 +0,07.
Per anno, gap CME a favore: +0,13 · −0,05 · +0,32 · +0,35 · +0,44 · −0,02 · −0,07.

## 3. Il risultato migliore: LISTING-SHORT

**Regola esatta.** Per ogni nuovo perpetual USDT-M quotato su Binance (prima candela oraria nell'archivio data.binance.vision): 24 ore dopo la prima candela, short all'apertura della barra oraria. Stop fisso al 15% sopra l'ingresso (leva massima 3,9x, margine isolato). Uscita a tempo dopo 168 ore. Nessun filtro.

| | n | N/anno | R̄ | σ_R | R̄/σ_R | t (somma settimanale) |
|---|---:|---:|---:|---:|---:|---:|
| Tutto (2020-03 → 2026-08) | 836 | 128 | +0,158 | 1,29 | 0,122 | 3,18 |
| Scelta | 142 | 58 | +0,353 | 1,37 | 0,259 | 2,66 |
| Verifica | 694 | 181 | +0,118 | 1,27 | 0,093 | 2,21 |

- **FATTO.** Vincenti 49%, stop toccato nel 41% dei casi. Media dei vincenti +1,26 R, dei perdenti −0,89 R, peggiore −1,64 R (gap oltre lo stop).
- **FATTO.** Seconda derivazione senza il simulatore: stesso +0,158 R. Lo short grezzo da +24h a +192h, senza stop né costi, rende in media +3,2% (mediana +7,0%, positivo nel 65% dei casi).
- **FATTO.** Il funding è contro: lo short paga in media lo 0,33% per trade (−0,022 R), già incluso.
- **FATTO.** Sensibilità: stop 8% → +0,220 R; 25% → +0,104; 40% → +0,060. Tenuta 336h → +0,156. Ingresso a +48h → +0,062 (verifica +0,001): **l'effetto sta tutto tra il giorno 1 e il giorno 2**, quindi dipende dalla puntualità.
- **FATTO.** Volume delle prime 24h sopra la mediana: +0,253 R; sotto: +0,062.
- **FATTO.** È anche uno short del mercato: beta −0,52 su BTC. Quando BTC sale nel periodo R = −0,07; quando scende R = +0,41. Correlazione mensile con il libro dei trade del fondo: −0,18.
- **FATTO.** Stress: slippage di 100 pb sugli stop → +0,152 R. Tolti i 5 trade migliori di ogni anno → +0,044 R: **il guadagno viene da pochi crolli grandi**.
- **FATTO.** Serie giornaliera con rischio 0,5% per trade e al massimo 8 trade aperti: Sharpe 1,43 (scelta 1,83, verifica 1,32), rendimento 10,8% l'anno, volatilità 7,5%, caduta massima −16,8%.
- **Sede richiesta.** Binance Futures non è accessibile a un retail italiano. Serve che la stessa moneta sia quotata su Hyperliquid (zona grigia) o su un perp regolato UE entro 24 ore: **non l'ho verificato**. La leva richiesta (≤ 4x) non è un vincolo.

## 4. Che cosa aggiunge al fondo (aritmetica del brief)

- **Leva mossa: più trade indipendenti.** ΔN = +128 l'anno (181 in verifica), con R̄/σ_R = 0,12 (0,09 in verifica), contro 77 trade e 0,14 del libro attuale.
- **STIMA.** N·(R̄/σ_R)² di LISTING-SHORT: 1,9 ingenuo; 1,6 corretto per i trade contemporanei (t²/anni); 1,3 in verifica. Sommato al libro attuale (1,5, correlazione leggermente negativa): **circa 2,8–3,1 contro 6,3 necessari**.
- **STIMA.** Crescita logaritmica a Kelly pieno: da 0,75 a circa 1,5 l'anno, cioè da circa 6% a circa 13% al mese **sulla carta**. A mezzo Kelly circa 10%. Con il livello del 2026 (R̄ = +0,07) il contributo scende a circa un terzo.
- **Risposta onesta:** avvicina, non arriva. E solo se si trova la sede.

## 5. Che cosa è fallito, e un errore evitato

- **Macro (CPI, NFP, FOMC).** Nessuna deriva prima del dato; seguire o contrastare la prima reazione perde per costi e stop. Nel 2020–21 BTC non reagiva nemmeno ai comunicati (volume ×1 nella barra del dato; dal 2022 ×13).
- **Gap CME.** «Il gap si chiude» è falso sui perp: perde a ogni soglia (t fino a −4,4). Il contrario (seguire la mossa del fine settimana) è positivo solo su BTC; ETH +0,025 e SOL −0,011 non confermano, il placebo sugli altri giorni è nullo, 2025–26 negativi. Resta **in osservazione**, non si negozia.
- **Ore 21–23 UTC.** Con ingresso e uscita maker a 1,5 pb, e la selezione avversa nel riempimento, R = −0,016; a 0 pb +0,004. Non c'è nulla da prendere.
- **Funding.** Nessun comportamento sfruttabile attorno al regolamento, né con il funding precedente né con quello in arrivo.
- **DIP-24h.** Profondità, stato del funding, ora del giorno, crollo di mercato o della singola moneta: nessun filtro migliora insieme scelta e verifica. L'ingresso maker 1σ sotto il prezzo raddoppia R (+0,087) ma t resta 1,9.
- **Errore evitato (regola del brief sui risultati troppo belli).** Raggruppando i DIP per numero di crolli **nello stesso giorno**, i giorni con ≤ 8 crolli davano +0,17/+0,24 R con t tra 4 e 8. Il conteggio del giorno contiene il futuro: i giorni con pochi crolli sono quelli in cui il crollo non si è esteso. Con l'ampiezza nota all'ora della decisione l'effetto sparisce (+0,02/+0,04 R, t < 1,6).
- **Depeg.** 3–6 eventi l'anno, quasi tutti rumore su TUSD/FDUSD; il depeg di USDC del marzo 2023 non è nei dati (coppia sospesa su Binance).
- **Delisting.** Non verificabile: l'archivio dà l'ultima candela, non la data dell'annuncio.

## 6. Controlli

- Troncamento: σ oraria, z a 24h, percentile a 90 giorni, stato DIP ricalcolati su dati tagliati a t con la barra corrente falsata: 0 differenze.
- Calendario: FOMC confrontato con federalreserve.gov (47 date su 47 dal 2021). CPI e NFP trascritti dal calendario BLS (bls.gov e FRED non raggiungibili da qui), con i rinvii del blocco del governo 2025–26; ogni data dal 2022 mostra il picco di volume all'ora del comunicato (`00_calendario.out`).
- t-stat: eventi contemporanei su più monete contano come un'osservazione (somma giornaliera o settimanale di R).

## 7. Dubbi

1. **199 prove.** Il massimo atteso di t su 199 prove indipendenti a caso è circa 3,25: il t = 3,2 di LISTING-SHORT da solo non prova nulla. Lo sostengono la scelta e la verifica entrambe positive (t 2,66 e 2,21) e un effetto noto (le nuove quotazioni perdono dopo l'esordio).
2. **Scelta piccola**: 142 quotazioni in tre anni. Durata e stop li ho guardati su tutti i periodi insieme.
3. **Decadimento** continuo dal 2020; nel 2026 R̄ = +0,07.
4. **Esecuzione**: stop su barre orarie; dentro l'ora una strizzata può fare peggio dei 100 pb di stress. La disponibilità di short e la liquidità nelle prime 48 ore non sono verificate.
5. **Variante «prime 24h < −20%»** (+0,64 R, t = 4,3): scelta di soli 13 casi, R sopra 0,5: per la regola del brief va trattata come sospetta. IPOTESI da osservare in avanti.
6. Rispetto alla v4 (short nei giorni 7–90, coperto, Sharpe 0,26: scartato) qui la finestra è il giorno 1–8: sono coerenti, il margine è nella prima settimana.

## 8. File

`lib.py` (simulatore) · `00_calendario` · `01_macro` · `02_orologio` · `03_funding` · `04_grandi_mosse` · `05_dip_isolato` · `06_gap_cme` · `07_listing` · `08_depeg` · `09_listing_short` · `10_finale` (ognuno `.py` + `.out`) · `res_*.csv` (tutte le righe) · `trials_*.json` · `trades.parquet` (773 LISTING-SHORT con limite di 8 aperti + 180 GAP-CME) · `returns.parquet` (giornaliero, rischio 0,5% per trade) · `calendario.csv`.
