# B3 — Leva incorporata sugli indici azionari (ETP 2x/3x/5x, CFD, micro future) — TUTTO SIMULATO

Nessun ordine inviato. Script: `00_dati.py`, `lab.py`, `01_validazione.py`, `02_kelly.py`, `03_strategie.py`, `04_ibs.py`, `05_sintesi.py` (+ `.out`, tabelle `03_tabella.csv`, `04_tabella.csv`, `05_sintesi.csv`). Serie: `returns.parquet`.
Varianti contate: **268** (210 regole in 03, 48 IBS in 04, 10 regole × 20 livelli di leva in 05) + le curve di leva costante su 3 indici.

## Risposta in tre righe
1. **La leva che massimizza la crescita su azioni USA e' circa 2x** (S&P 500 e Nasdaq-100, campione intero, costi reali). Stimata sul passato e applicata al futuro rende **meno dell'1x**. 3x costante ha perso il 98–100% almeno una volta; 5x costante e' stato azzerato.
2. Le regole (tendenza, volatilita' obiettivo, controllo della caduta, HFEA, IBS) **non creano vantaggio nuovo**: Sharpe 0,5–0,66 contro 0,53 del Nasdaq-100 comprato e tenuto. Spostano la leva ottima da 2x a 2,25–3x e tagliano le cadute.
3. Rendimento composto che i dati sostengono: **1,1–1,4% al mese** con caduta massima intorno al 50%; **1,7–1,9% al mese** alla leva ottima, con caduta 78–87% e probabilita' 60–68% di perdere meta' del conto entro 3 anni. Il 30% al mese non c'e': manca un fattore 16–25.

## Prodotti che un residente italiano puo' comprare (verifica web, 11-2026)
| Prodotto | Leva | Costo dichiarato | Costo di finanziamento misurato qui | Fonte |
|---|---|---|---|---|
| WisdomTree NASDAQ 100 3x Daily Leveraged, QQQ3 (Borsa Italiana, EUR; ISIN IE00BLRPRL42; swap BNP, collateralizzato) | 3x | 0,75% + tasso swap giornaliero | T-bill + 0,1–1,8% sul debito | [WisdomTree](https://www.wisdomtree.com/it/products/equities/wisdomtree-nasdaq-100-3x-daily-leveraged) |
| WisdomTree S&P 500 3x, 3USL | 3x | 0,75% + swap | T-bill + 1,0% (linea USD) | idem, serie Yahoo |
| Leverage Shares 5x Long Nasdaq 100, 5QQQ (XS2399364152) e 5x S&P 500, 5SPY | 5x | 0,75% + interessi sul margine (aumentati 07-2024) | T-bill + 3,0–3,9% | [Leverage Shares](https://leverageshares.com/en/etps/leverage-shares-5x-long-nasdaq-100-etp/), [KID](https://leverageshares.com/documents/en/kid/1126_5x_ndx_kid_en.pdf) |
| Amundi Nasdaq-100 Daily (2x) Leveraged UCITS ETF, LQQ (FR0010342592) | 2x | TER 0,60% | T-bill + 1,7% | [Finanzfluss](https://www.finanzfluss.de/informer/etf/fr0010342592/), [justETF](https://www.justetf.com/uk/how-to/invest-in-leveraged-etfs.html) |
| Xtrackers S&P 500 2x Leveraged Daily Swap (LU0411078552) | 2x | TER 0,60% | serie Yahoo sporca, non usata | idem |
| CFD su indici IBKR Irlanda (IBUS500, IBUST100) | fino a 16–20x | margine ESMA 5%, IBKR 6,25% su IBUS500 | tasso + 1,5% (ipotesi A5) | [IBKR margini CFD](https://www.interactivebrokers.ie/en/trading/margin-cfd.php) |
| Micro future MNQ ($2 × indice), MES ($5 × indice) | — | 1 pb | implicito nel prezzo | [CME](https://www.cmegroup.com/markets/equities/nasdaq/micro-e-mini-nasdaq-100.margins.html) |

- FATTO: ETFplus negozia in continua 9:00–17:30 ([Borsa Italiana](https://www.borsaitaliana.it/etf/formazione/segmentazioneemicrostrutturamercatoetfplus/etfplussegmentazioneemicrostruttura.en.htm)). Un segnale calcolato alla chiusura USA si esegue il giorno dopo: per questo la base e' "eseguito a t+1".
- FATTO (aritmetica): con 11.000 € un MNQ vale circa 55.500 $ = **4,5 volte il conto**, un MES 37.600 $ = 3,1 volte. I micro future non permettono di graduare l'esposizione: per un conto cosi' servono ETP o CFD.
- NON VERIFICATO: che IBKR Irlanda abiliti QQQ3/5QQQ a un cliente al dettaglio italiano. Ho trovato solo l'informativa IBKR sui "complex or leveraged ETP" e la regola PRIIPs (serve il KID, che esiste). Da controllare sul conto.
- I dati TER di 5QQQ sui siti terzi vanno da 0,75% a 9,75% (alcuni includono il finanziamento): ho usato quello misurato sulla serie reale.

## Validazione delle serie sintetiche (`01_validazione.out`)
Formula: `k·r − (k−1)·(T-bill + spread) − TER`. Sottostante: QQQ/SPY rettificati (prima ^NDX + 0,3% e VFINX/^GSPC + dividendi: STIMA).
| Reale | k | Dal | CAGR reale | Sintetico a spread 0 | Spread che pareggia | Correlazione |
|---|---|---|---|---|---|---|
| TQQQ | 3 | 2010 | 39,9% | 42,4% | 0,84% | 0,999 giorn. |
| UPRO | 3 | 2009 | 31,9% | 33,8% | 0,72% | 0,998 |
| SSO / QLD | 2 | 2006 | 15,4% / 24,1% | 16,3% / 25,4% | 0,80% / 0,99% | 0,996 |
| QQQ3.L (USD) / QQQ3.MI (EUR→USD) | 3 | 2012 / 2014 | 38,8% / 33,9% | 39,0% / 38,8% | 0,10% / 1,79% | 0,96 mens. |
| 3USL.L | 3 | 2012 | 27,2% | 29,8% | 1,00% | 0,95 mens. |
| 5QQQ.L / 5SPY.L | 5 | 2022 | **−58,3%** / −2,3% l'anno | −51,3% / +10,3% | 3,87% / 3,02% | 0,95 mens. |
Costi usati nelle simulazioni: 2x TER 0,60% + spread 0,4% (ottimista di circa 0,5–1 punto rispetto al misurato), 3x 0,75% + 1,0%, 5x 0,75% + 3,5%. FATTO: dal 2022 il 5x sul Nasdaq reale ha perso il 58% l'anno mentre l'indice saliva.

## Leva costante ottima (`02_kelly.out`) — finanziamento T-bill + 1%, TER 0,75%
| Periodo | S&P 500: k* | CAGR 1x / 2x / 3x / 5x | Nasdaq-100: k* | CAGR 1x / 2x / 3x / 5x |
|---|---|---|---|---|
| 1970–79 | 0 | 5,6 / 1,0 / −4,5 / −19 | — | — |
| 1980–89 | 1,0 | 14,0 / 13,0 / 8,4 / **azzerato** (19-10-1987: −20,5%) | 2,25 | 18,0 / 22,0 / 20,6 / −4,7 |
| 1990–99 | 5,25 | 18,0 / 27,5 / 35,6 / 43,3 | 4,25 | 32,5 / 55,0 / 72,5 / 78,8 |
| 2000–09 | 0 | −0,9 / −10,7 / −23,0 / −51 | 0 | −6,2 / −25,4 / −47,0 / −82 |
| 2010–19 | 5,5 | 13,6 / 23,3 / 31,9 / 41,1 | 5,5 | 18,1 / 32,2 / 44,7 / 58,0 |
| 2020–26 | 3,0 | 14,8 / 20,9 / 22,9 / 11,0 | 2,75 | 19,3 / 27,6 / 28,9 / 7,0 |
| 2000–02 | 0 | −14,5 / −34,7 / −52,6 / −79 | 0 | −35,7 / −70,0 / −89,3 / −99,4 |
| ≤ 2007 | 1,0 | 10,1 / 9,2 / 6,2 / azzerato | 1,5 | 14,3 / 13,4 / 4,6 / −31 |
| ≥ 2008 | 2,5 | 11,2 / 15,1 / 15,3 / 2,0 | 3,0 | 15,8 / 23,5 / 26,0 / 11,5 |
| Scelta ≤ 2022 | 1,75 | 9,7 / 9,7 / 6,8 / azzerato | 1,75 | 13,7 / 15,2 / 9,6 / −21 |
| Verifica ≥ 2023 | 6,25 | 20,7 / 33,8 / 46,1 / 62,7 | 5,0 | 28,4 / 48,3 / 65,6 / 81,6 |
| **Intero** | **2,0** | 10,4 / 11,1 / 9,1 / azzerato | **2,0** | 15,0 / 17,9 / 13,9 / −14 |

- **Incertezza** (bootstrap a blocchi di 21 sedute): k* al 5°–95° percentile = 0–5,25 su 10 anni e 0,75–3,75 (S&P) / 1,0–3,25 (Nasdaq) su 30 anni; mediana 2. Su 10 anni il 3x batte l'1x solo nel 48–49% dei casi e perde denaro nel 27–29%; il 5x perde denaro nel 56–63%.
- **Fuori campione**: k* stimato sui 10 anni precedenti e applicato all'anno dopo rende **+2,5% (S&P) e −25,5% (Nasdaq) l'anno** contro 11,5% e 15,0% dell'1x; con 20 anni 8,9% e 4,9%; con tutto il passato 10,7% e 7,1%. La leva scelta guardando indietro e' massima proprio prima dei crolli.
- **Costo del decadimento da volatilita'** (k(k−1)σ²/2, intero): Nasdaq 19,5 punti l'anno a 3x e 65 punti a 5x; S&P 9,0 e 30,0. Nel 2000–02 sul Nasdaq: 81 e 269 punti.
- Con il premio azionario dimezzato k* scende a **1,0** su tutti e tre gli indici e il 3x diventa negativo (−1,7% / −7,8%).
- Sensibilita' al finanziamento: a spread 2% k* dell'S&P scende a 1,0; a 3,5% (5x reali) il Nasdaq scende a 1,5.

## Regole sistematiche (`03_strategie.out`): migliore per famiglia, scelto sul CAGR ≤ 2022, storie dal 1986
Esecuzione a t+1; costi per lato 3 / 5 / 10 / 25 pb (1x / 2x / 3x / 5x); cassa = T-bill − 0,2%.
| Regola (Nasdaq-100) | CAGR intero | Sharpe | Caduta max | Mese peggiore | Scelta | Verifica | ≤ 2007 | ≥ 2008 | 2000–02 | Costi ×2 | Ritardo +1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x comprato e tenuto | 15,0% | 0,55 | −83% | −27% | 13,7% | 28,3% | 14,3% | 15,8% | −36% | — | — |
| 2x costante | 18,9% | 0,53 | −99% | −51% | 16,1% | 49,4% | 14,4% | 24,5% | −70% | — | — |
| 3x costante | 14,0% | 0,52 | −100% | −71% | 9,7% | 65,6% | 4,7% | 26,0% | −89% | — | — |
| 3x, fuori se l'indice e' −20% dal massimo a 1 anno, rientro a −10% | 24,9% | 0,63 | −78% | **−71%** | 24,0% | 34,3% | 27,3% | 22,2% | −11% | 24,8% | 25,1% |
| Volatilita' obiettivo 50% con 3x | 26,0% | 0,66 | −90% | −56% | 23,7% | 50,8% | 22,1% | 30,8% | −48% | 25,7% | 25,5% |
| Volatilita' obiettivo 20% con 3x + cassa | 16,1% | 0,64 | −55% | −24% | 15,0% | 26,7% | 15,0% | 17,4% | −19% | 15,8% | 16,1% |
| Dual momentum 12 mesi, 3x, riparo in obbligazioni 3x | 23,8% | 0,61 | −89% | −65% | 22,3% | 39,2% | 15,6% | 33,8% | −36% | 22,4% | 17,9% |
| 3x sopra la media a 200 sedute | 17,6% | 0,52 | −84% | −62% | 15,6% | 39,4% | 13,0% | 23,2% | −31% | — | — |
| HFEA 55% azioni 3x / 45% Treasury 10 anni 3x | 17,5% | 0,52 | −96% | −41% | 15,9% | 34,4% | 14,1% | 21,6% | −58% | 17,4% | 17,5% |
| HFEA 55/45 + media 200 sulla gamba azionaria | 17,0% | 0,56 | −55% | −35% | 16,5% | 21,3% | 16,3% | 17,8% | −6% | 16,5% | 16,8% |
| HFEA 34/33/33 con oro 3x + media 200 (solo dal 2000-08) | 20,2% | 0,78 | −44% | −19% | 17,5% | 37,7% | 21,1% | 19,9% | +5% | — | — |

- FATTO: nessuna famiglia supera Sharpe 0,66 su 40 anni. La media a 200 sedute sul 3x non salva dal 1987 (mese −62/−71%): il crollo parte da sopra la media.
- FATTO: la classifica per CAGR si conserva poco (correlazione di rango scelta→verifica 0,39; ≤2007→≥2008 0,59). In verifica (2023–26, mercato toro) vince chi ha piu' leva: non e' una prova.
- La variante con l'oro ha Sharpe 0,78 ma parte dal 2000 e l'oro ha fatto +10 volte nel periodo: IPOTESI, non selezionabile con la regola "storia dal 1986".
- S&P 500: stessi risultati con numeri piu' bassi (migliori CAGR 11–14%, Sharpe 0,35–0,50).

## IBS in ETP 3x/5x (`04_ibs.out`, QQQ dal 1999, SPY dal 1993)
| Variante | Trade/anno | CAGR intero | Sharpe | Caduta max | Scelta | Verifica |
|---|---|---|---|---|---|---|
| QQQ 1x, IBS < 0,2 e VIX ≥ 20, ingresso all'apertura | 18 | 12,7% | 0,67 | −49% | 12,5% | 13,4% |
| QQQ 3x, stessa regola | 18 | 26,0% | 0,66 | **−92%** | 25,4% | 29,6% |
| QQQ 5x, stessa regola | 18 | 20,1% | 0,61 | −99% | 17,3% | 39,1% |
| QQQ 3x, ingresso alla chiusura stessa (non eseguibile in ETP europei) | 19 | 29,1% | 0,71 | −86% | 27,9% | 36,5% |
| SPY 3x, IBS < 0,1, apertura | 22 | 16,9% | 0,58 | −59% | 17,6% | 11,4% |
Il vantaggio IBS e' gia' nel fondo. In ETP 3x non migliora lo Sharpe; il 5x rende meno del 3x (decadimento + 3,5% di finanziamento + 25 pb di differenziale).

## Candidato migliore e leva ottima (`05_sintesi.out`)
**Regola**: esposizione al Nasdaq-100 = 20% / volatilita' realizzata a 20 sedute, tetto 3x, tenuta con QQQ3 + ETF monetario, aggiornata quando cambia di oltre il 10%, ordine il giorno dopo.
| Leva (moltiplicatore) | Esposizione media | CAGR intero / scelta / verifica | Mese composto | Sharpe i/s/v | Caduta max | Mese peggiore | P(−50%) in 3 anni: base / mezzo vantaggio |
|---|---|---|---|---|---|---|---|
| 1,0 (meta' dell'ottimo) | 1,16 | 16,2% / 15,0% / 28,2% | **1,26%** | 0,64 / 0,60 / 1,02 | −54% | −27% | 2% / 6% (mese 0,56%) |
| 2,25 (ottimo, uguale su intero e su scelta) | 2,5 | 22,9% / 20,2% / 51,9% | **1,73%** | 0,60 / 0,56 / 1,00 | −87% | −54% | 60% / 74% (mese 0,21%) |
Alternativa a crescita piu' alta e coda peggiore: uscita a −20% dal massimo, leva 3 → 24,6% (1,85% al mese), caduta −78%, mese −71%, P(−50%) 68% / 79%; a leva 1,5 → 18,2% (1,40%), caduta −48%, mese −42%, P(−50%) 11% / 18%.
Leva scelta su ≤ 2007 (1,75) e applicata a ≥ 2008: 27,1% contro 31,5% dell'ottimo a posteriori. Per decennio (leva 1): 1986–89 +20%, anni '90 +24%, **2000–09 −0,5%**, 2010–19 +21%, 2020–22 +8%, 2023–26 +27%.

- **Chi paga**: nessuno in particolare. E' il premio per il rischio azionario (beta), piu' il fatto che la volatilita' e' persistente e il rendimento atteso non sale in proporzione (Sharpe 0,53 → 0,64). Non e' una classe di vantaggio nuova.
- **Capienza**: illimitata per un conto al dettaglio (QQQ3 ha 593 milioni di $ di masse).
- **Evento che uccide**: un giorno da −15/−20% (1987) con leva 3 = −45/−60% in una seduta; un decennio piatto e volatile (2000–09) = dieci anni a zero. Rischio emittente dell'ETP (swap/ETN) e chiusura anticipata del prodotto.
- **Correlazione con il fondo** (2018-04 → 2026-10, mensile): 0,44 con `B_cassa_in_tbill`, 0,32 con `C1_mtm_limiti`, 0,31 con `C3_mtm_limiti_debito_reale`. Miscela a pari rischio con B: Sharpe mensile **1,64 contro 1,83 del fondo da solo**: aggiungerla abbassa la qualita' del fondo. Solo l'IBS (gia' dentro al fondo) la alzerebbe.

## Tasse (Italia) — da confermare con un commercialista
- ETP a leva WisdomTree / Leverage Shares / GraniteShares (ETN/ETC, non OICR): plusvalenze e minusvalenze sono entrambe **redditi diversi**, 26%, compensabili fra loro e con lo "zainetto" per 4 anni ([Milano Finanza](https://www.milanofinanza.it/investimenti-trading/la-fiscalita-degli-etp-201406121606303524), [Money.it](https://www.money.it/Tassazione-ETF-dividendi-capital-gain-guida)).
- ETF armonizzati 2x (Amundi LQQ, Xtrackers): plusvalenze = **redditi di capitale** (26%, non compensabili), minusvalenze = redditi diversi ([Morningstar](https://global.morningstar.com/it/etf/guida-alla-tassazione-degli-etf)). Per una strategia che entra ed esce gli ETP sono fiscalmente migliori.
- IPOTESI: IBKR Irlanda non fa da sostituto d'imposta, quindi regime dichiarativo (quadri RT/RW, IVAFE). Al 26% il 16,2% lordo diventa circa 12% netto (0,95% al mese).

## Dubbi
- 40 anni di Nasdaq-100 contengono un solo 1987 e un solo 2000–02; il periodo 2009–2026 pesa molto e ha premiato la leva.
- Dividendi pre-1993/1999 stimati; spread dei prodotti UCITS misurato su serie Yahoo con chiusure europee e alcuni salti tolti (da 0,1% a 1,8% sul 3x).
- La cassa del conto rende solo se parcheggiata in un ETF monetario; cambio EUR/USD non coperto e non simulato.
- L'apertura USA come prezzo d'ingresso dell'ETP europeo e' un'approssimazione; nessuna serie intraday degli ETP.
- Il sintetico 5x non modella il ripristino infragiornaliero dei prodotti Leverage Shares.
