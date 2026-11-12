# B2 — Microstruttura e alta frequenza (v6) — tutto SIMULATO su dati reali

**Verdetto in una riga.** Nessuna strategia ad alta frequenza ha aspettativa positiva per un conto retail da €10k su VPS:
il segnale esiste (R² fino al 4% a 1 s) ma vale 0,2–0,8 bp contro 9 bp di costo taker; fare il maker perde 2,2–2,6 bp per $ eseguito.

## 1. Dati (FATTO)
- data.binance.vision, USDT-M: `aggTrades` 2019-12-31 → oggi; `trades` 2019-09 → oggi; `bookTicker` (miglior bid/ask tick-by-tick)
  **solo 2023-05-16 → 2024-03-30**; `bookDepth` (profondità cumulata ±1…5%, ogni ~30 s) 2023-01-01 → oggi. Spot: `aggTrades`, `trades`.
- Campione scaricato: 45 giorni × BTCUSDT, ETHUSDT (aggTrades perp + spot): 16 giorni 2020–22 (selezione), 29 giorni 2023–26 (verifica);
  16 di questi hanno anche bookTicker (8 nel 2023, 8 nel 2024; 10–25 milioni di righe al giorno). Ridotti a griglia 100 ms:
  `data_cache/v6_g100_{sym}_{data}.parquet`. bookDepth: un giorno su due 2023-01 → 2026-10 (698 giorni per simbolo).
- **Deviazione dal brief**: i test che usano il book non possono rispettare «selezione ≤ 2022» perché il dato non esiste prima del 2023-05.
  Per quelli: fit sui giorni 2023, verifica sui giorni 2024 (+ registrazione live 2026). I test sui soli trade rispettano il taglio 2022/2023.
- Live: vedi §6.
- Commissioni Hyperliquid lette dall'API (`userFees`, FATTO): taker 4,5 bp, maker 1,5 bp. Maker 0 bp da 500 M$ di volume in 14 giorni;
  rebate −0,1/−0,2/−0,3 bp solo con ≥ 0,5% / 1,5% / 3% del volume maker dell'intero exchange. Volume perps HL nelle 24 h: 4,8 mld $ (FATTO)
  → primo rebate ≈ 24 M$ al giorno di volume maker, tutti i giorni. Un conto da €10k a 40x ha al massimo 0,4 M$ di posizione: dovrebbe
  ruotarla 60 volte al giorno. **Non raggiungibile** (STIMA sull'ipotesi maker ≈ metà del volume). Sconto staking HYPE: 5–40%, non cambia il segno.

## 2. Test 1 — prevedibilità a breve (02_predict.out)
Regressione lineare su OFI (1/5/30 s), squilibrio L1, microprice−mid, flusso firmato dei trade, rendimenti passati. Fit 2023, verifica 2024.
Edge = rendimento mid→mid firmato sui segnali più forti (soglia fissata in selezione), ingresso dopo la latenza indicata.

| BTC perp Binance (verifica 2024) | 1 s | 5 s | 30 s | 1 m | 5 m |
|---|---|---|---|---|---|
| R² fuori campione, latenza 0 | 3,50% | 2,30% | 0,53% | 0,17% | 0,05% |
| R² fuori campione, latenza 200 ms | 2,01% | 1,55% | 0,35% | 0,08% | 0,03% |
| R² fuori campione, latenza 1 s | −0,09% | 0,23% | 0,03% | −0,08% | 0,00% |
| Edge lordo top 10%, latenza 200 ms (bp) | 0,23 | 0,44 | 0,50 | 0,40 | 0,75 |
| Edge lordo top 1%, latenza 200 ms (bp) | 0,30 | 0,54 | 0,40 | 0,19 | 1,89 |
| Edge lordo top 1%, latenza 1 s (bp) | 0,14 | 0,28 | 0,27 | 0,14 | 1,80 |
| Costo taker andata/ritorno HL (bp) | 9,0 | 9,0 | 9,0 | 9,0 | 9,0 |

- ETH: stessi ordini di grandezza (R² 4,2% a 1 s; edge top 1% a 200 ms: 0,30 / 0,48 / 0,38 / 0,48 / 2,47 bp).
- Il numero più alto in assoluto è il top 0,1% a 5 minuti (6,4 bp BTC, 6,7 bp ETH): ~2.000 osservazioni sovrapposte su 8 giorni,
  t tra giorni 1,9–3,0, R² ≈ 0: **non lo considero affidabile** (IPOTESI), e comunque è sotto i 9 bp.
- Solo trade (rispetta il taglio 2022/2023; 16 giorni → 28–29 giorni): R² in verifica 0,29% a 1 s, ≤ 0 da 30 s in su; edge top 10% 0,04–0,19 bp.
- Autocorrelazione del segno dei trade: 0,39–0,50 al ritardo 1, 0,17–0,41 al ritardo 10, 0,01 al ritardo 1000 (09_signacf.out). Vale 0,3–0,7 bp a latenza zero.
- Squilibrio a profondità ±1/2/3/5% (bookDepth, 698 giorni, fit 2023–24, verifica 2025–26): R² fuori campione ≤ 0 a 1 m, 5 m, 15 m, 1 h;
  top 10%: +0,11…+0,38 bp BTC fino a 15 m (08_bookdepth.out).
- **Di quanto fallisce**: edge robusto migliore ≈ 0,5 bp (0,75 bp a 5 m) contro 9,0 bp + spread: manca un fattore 12–18.
  Commissione taker di pareggio ≈ 0,25–0,4 bp per lato. Nessun livello di Hyperliquid (minimo 2,4 bp) o Kraken ci arriva.

## 3. Test 2 — market making con fill conservativo (03_mm.out, 03b_mm_touch.out)
Quote su entrambi i lati, 1 unità per lato, inventario massimo ±5 unità, ordini post-only, riquotazione ogni 1 s o 5 s, informazione vecchia di
200 ms o 1 s, fill **solo se un trade stampa oltre il prezzo quotato**. 56 configurazioni × 2 simboli (distanza dal mid 0–10 bp, con/senza filtro OFI).

| BTC, verifica 2024, riquota 1 s, latenza 200 ms | fill/giorno | spread incassato | markout 1 s | markout 60 s | lordo bp/$ | netto a 1,5 bp |
|---|---|---|---|---|---|---|
| al miglior bid/ask | 20.426 | 0,07 | −0,88 | −1,00 | −1,03 | **−2,53** |
| mid ± 1 bp | 11.540 | 0,57 | −0,68 | −0,75 | −0,78 | −2,28 |
| mid ± 2 bp | 4.628 | 0,99 | −0,69 | −0,69 | −0,69 | −2,19 |
| mid ± 5 bp | 725 | 2,37 | −0,62 | −0,08 | −0,21 | −1,71 |
| mid ± 10 bp | 142 | 4,80 | −0,16 | −0,38 | +0,53 (sel. +0,08) | −0,97 |

- ETH: da −2,61 (al BBO) a −0,20 (±10 bp, selezione −3,76) bp/$ netti. In selezione 2023 **nessuna** configurazione è positiva a 1,5 bp.
- Migliore in selezione → verifica: BTC −1,00 → −0,60 bp/$ (Sharpe giornaliero −6 → −4); ETH −5,85 → +0,50 bp/$ (82 fill/giorno: rumore).
- Cosa lo uccide: **selezione avversa**. Chi ti riempie sa qualcosa: dopo il fill il mid è 0,7–1,1 bp contro di te entro 1 s, qualunque sia la
  distanza a cui quoti, perché la quota è vecchia di 0,2–1 s quando viene colpita. Lo spread di BTC/ETH è 0,02–0,05 bp: non c'è nulla da incassare.
- Limite superiore irrealistico (fill al tocco = testa della coda): lordo −0,05…−0,15 bp/$ → −1,55…−1,65 a 1,5 bp; positivo (+0,2) solo con rebate 0,3 bp.
- Pareggio: servirebbe un **rebate di 0,7–1,1 bp** (coda in fondo). Il massimo di Hyperliquid è 0,3 bp.
- `returns.parquet`: rendimenti giornalieri netti (capitale = inventario massimo, 1x) dei 16 giorni campione, 4 configurazioni; sono negativi.

## 4. Test 3 — lead-lag (storico: 04_leadlag_hist.out; live: §6)
- Binance spot ↔ perp, 45 giorni: il perp guida lo spot (corr. rendimento 1 s ritardato di 200 ms: 0,10–0,14) più di quanto lo spot guidi il perp (0,07).
- Evento «il leader si muove ≥ 7–8 bp in 1 s» (top 1%): il follower si è già mosso di 8–10 bp nello stesso secondo. Resta da prendere, nei 5 s
  successivi: 0,3–1,4 bp a 200 ms di latenza, 0,1–0,9 bp a 500 ms, −0,1…+0,6 bp a 1 s. Contro 9 bp (perp) o 20+ bp (spot).

## 5. Test 4 — raffiche di trade aggressivi (05_bursts.out)
Flusso firmato in 1 s o 5 s ≥ 10/20/50 volte la media dei 30 minuti precedenti, con o senza movimento ≥ 5 bp (12 regole × 5 orizzonti).
- Selezione 2020–22: **inversione** a 5–15 minuti: −0,9…−5,3 bp (t fino a −5,8). Verifica 2023–26: −0,1…−1,9 bp, quasi mai significativa.
- Regola migliore in selezione (5 s, 50×, ≥ 5 bp, 15 m): −9,4 bp (n 66, t −1,2) → verifica −3,7 bp (n 189, t −1,1). Decade anno dopo anno e
  resta sotto il costo taker. Continuazione a 5–60 s: ≤ 0,2 bp, non distinguibile da zero.

## 6. Registrazione live, 11–12 novembre 2026 (07_live_AB.out, 06_live_build_*.out)
1,77 ore in due segmenti (19:11–19:51 e 23:21–00:28 UTC; i recorder sono morti due volte con la sessione: **non** le 2–4 ore chieste).
Hyperliquid (bbo, trades, l2Book a 20 livelli ogni ~8 s e a 5 livelli ~2/s) per BTC, ETH, SOL + bbo/trades di 20 perps meno liquidi (1,4 ore);
Binance USDT-M (bookTicker, depth5, aggTrade, forceOrder) e spot; Kraken Futures (book, ticker, trade). OKX non raggiungibile da qui.
- **Latenza da questa macchina** (FATTO; orologio locale allineato a Binance entro ±93 ms): il dato arriva vecchio di ~95 ms da Binance, 60–145 ms da
  Kraken, **325–385 ms da Hyperliquid** (p95 480–690 ms). Andata e ritorno di una richiesta: ~187 ms Binance e HL, ~116 ms Kraken.
  Un ordine deciso su un dato HL colpisce quindi un book che io vedrò solo ~0,6–0,8 s dopo (STIMA): la latenza realistica è 700 ms, non 200.
- **Spread e profondità** (mediane): HL BTC 0,13 bp, ETH 0,49, SOL 0,12; Kraken BTC 0,13, ETH 0,49, SOL 1,20; Binance BTC 0,01.
  HL entro 5 bp per lato: BTC 4,9 M$, ETH 3,3 M$, SOL 0,4 M$. Volume orario: HL BTC 74 M$, Binance 323 M$, Kraken 13 M$.
- **Prevedibilità del mid HL** (fit prima metà, verifica seconda; 14 variabili fra cui squilibrio HL a 1/2/5/10/20 livelli e scarto Binance−HL):
  R² in verifica a 1 s: 54–63% a latenza 0, 40–44% a 200 ms, **0–2% a 500 ms, negativo a 700 ms e 1 s**. È quasi tutto ritardo del feed HL
  rispetto a Binance (corr. 0,30–0,50 dello scarto Binance−HL, 0,27–0,38 dello squilibrio L1; i livelli 10–20 valgono 0,08–0,22).
  Top 10% dei segnali, taker prima delle commissioni: +0,8…+1,6 bp a 200 ms, **−0,3…+0,4 bp a 1 s** (orizzonti 1–5 s). Costo: 9 bp.

| Binance → Hyperliquid: taker su HL dopo un salto Binance in 500 ms (3 monete insieme) | n | L 500 ms | L 700 ms | L 1 s |
|---|---|---|---|---|
| salto ≥ 2 bp, uscita 5 s: lordo attraversando lo spread → netto dopo 9 bp | 963 | +1,85 → −7,15 | +1,12 → −7,88 | +0,40 → −8,60 |
| salto ≥ 4 bp, uscita 5 s | 84 | +3,40 → −5,60 | +2,31 → −6,69 | +0,59 → −8,41 |
| salto ≥ 6 bp, uscita 30 s | 21 | +9,14 → +0,14 | +7,26 → −1,74 | +4,44 → −4,56 |
| salto ≥ 8 bp, uscita 30 s | 9 | +14,73 → +5,73 | +12,41 → +3,41 | +7,27 → −1,73 |

- I salti ≥ 8 bp sono solo **6 grappoli indipendenti** (le tre monete saltano insieme): netto +4,4 bp (t 1,3) a 500 ms, +1,8 bp (t 0,5) a 700 ms,
  −3,7 bp (t −1,6) a 1 s. Sulla stessa regola con uscita a 5 s: +1,9 / −0,9 / −6,7 bp. **Non è evidenza** (IPOTESI). Vedi §8.
- Binance → Kraken: Kraken ha già fatto 1,5–2,5 bp del movimento quando lo vedo; netto −3,7…−12 bp in ogni cella. Morto.
- **Market making su HL**, quota al miglior bid/ask, fill conservativo, latenza 500 ms: BTC −2,67, ETH −4,06, SOL −2,87 bp/$ netti (markout a 1 s:
  −1,1…−1,7 bp); al tocco −1,7…−2,3. Quote a ±2 bp: −2,3…−3,1. Le uniche celle positive (ETH ±5 bp: +0,15/+0,52) hanno 8–16 fill l'ora.
- **20 perps meno liquidi** (spread mediano 0,1–8,6 bp): netto medio −4,4 bp/$ (coda in fondo), −2,7 (al tocco); positivi 3 su 20 e 2 su 20.
  Dove lo spread è largo (AERO, ETHFI 8 bp) l'incasso è 2–3 bp e il netto +1 bp, ma con 80–110 fill l'ora di taglia ignota: non è una prova.
- Liquidazioni Binance viste: 123 in 1,77 ore, 0,76 M$ in tutto, la più grande 149 k$: troppo poche per un test.

## 7. Verdetto
**No.** Per un conto retail su VPS, con API pubbliche e commissioni base, nessuna delle strategie provate ha aspettativa positiva.

| Strategia | Edge misurato | Costo | Di quanto manca | Cosa servirebbe |
|---|---|---|---|---|
| Taker su segnali di book/flusso (1 s–5 m) | 0,2–0,8 bp | 9,0 bp + spread | fattore 12–18 | commissione ≤ 0,3 bp per lato |
| Maker su BTC/ETH/SOL | −0,7…−1,2 bp lordi | +1,5 bp | −2,2…−4,1 bp per $ | rebate ≥ 0,7–1,2 bp (HL max 0,3) |
| Lead-lag Binance → HL, salti ≥ 2–4 bp | 1,1–3,4 bp | 9,0 bp | 5,6–7,9 bp | taker ≤ 0,6–1,7 bp per lato |
| Lead-lag spot ↔ perp Binance | 0,1–1,4 bp | 9 bp | 7,6–8,9 bp | idem |
| Raffiche: inversione a 15 minuti | 0,2–1,9 bp (verifica) | 9 bp | 7–9 bp | — |

Livelli di commissione: il taker più basso di Hyperliquid è 2,4 bp (7 mld $ in 14 giorni) e non basta nemmeno quello. Maker a 0 bp da 500 M$ in 14 giorni
(36 M$ al giorno); rebate da ~24 M$ al giorno di volume maker. Con €10k a 40x servirebbero 60–90 rotazioni complete della posizione massima al giorno.

**Candidato migliore e consegne del brief.** Non c'è un candidato con aspettativa positiva dimostrata. Chi paga l'edge qui è il retail stesso:
il rendimento della velocità va a chi ha latenza di millisecondi e commissioni maker negative. Leva che massimizza la crescita: **0**.
Rendimento mensile sostenuto: **0%** (negativo se eseguito). Correlazione col fondo e P(−50%) non calcolabili: i rendimenti sono 16 giorni sparsi e
tutti negativi (`returns.parquet`). Nei termini del brief: ΔN grande ma R̄ < 0, quindi N·(R̄/σ_R)² non sale.

## 8. Unico punto aperto (IPOTESI, non un risultato)
Il ritardo Binance → Hyperliquid è reale (3–4 bp dopo salti ≥ 4 bp, 12–15 bp dopo salti ≥ 8 bp) e sui salti grandi supera i 9 bp se si arriva entro
~500 ms. Salti ≥ 8 bp in 500 ms su Binance: 20–140 al giorno per moneta nel 2023–26 (10_jumpfreq.out). Contro: 6 grappoli in tutto; a 1 s il segno si
inverte; HL esegue cancellazioni e post-only prima degli ordini taker nello stesso blocco (da documentazione, non verificato qui), quindi il prezzo vero
di esecuzione è peggiore di quello che ho usato; la taglia al primo livello nei salti non è misurata; ci competono arbitraggisti professionali.
Per decidere servono 1–2 settimane di registrazione da un VPS a Tokyo e ordini reali di taglia minima. Probabilità che regga: bassa.

## 9. Conteggio delle varianti
Circa **320 varianti**: 20 regressioni × 3 soglie (test 1), 8 regressioni bookDepth, 112 + 16 configurazioni di market making storiche, 36 + 240 live
(3 + 20 monete), 60 celle raffiche, 12 lead-lag storico, 80 celle lead-lag live, 15 regressioni live. Nessuna è stata scartata dopo averla vista.

## 10. Dubbi
- Il book storico è Binance, non Hyperliquid: uso Binance come limite superiore della prevedibilità e le commissioni HL come costo.
- bookTicker copre solo 10 mesi (2023-05 → 2024-03): 16 giorni per simbolo; i test col book non hanno selezione ≤ 2022.
- La griglia a 100 ms nasconde ciò che accade sotto i 100 ms; irrilevante per chi ha 200 ms–1 s di latenza.
- Il fill «oltre la quota» è pessimista per chi quota al miglior prezzo; il fill «al tocco» è il limite opposto: la verità sta in mezzo, ed è negativa in entrambi.
- Live: 1,77 ore di una sola serata, mercato tranquillo; latenza misurata attraverso il proxy di questa sessione (un VPS vero può essere più veloce o più lento).
- Kraken: commissione taker presa a 5 bp dal brief, non letta dall'API. Limite di richieste HL per indirizzo (legato al volume scambiato): non testato.
- Il conto del rebate assume volume maker ≈ volume totale dell'exchange (STIMA).

## File
`00*_recorder*.py` (recorder live), `01_build.py` (scarico + griglia 100 ms), `02_predict`, `03_mm`, `03b_mm_touch`, `04_leadlag_hist`, `05_bursts`,
`06_live_build`, `07_live`, `08_bookdepth`, `09_signacf`, `10_jumpfreq` (.py e .out), `lib.py`, `mm.py`, `returns.parquet`, `hl_universe.csv`.
Dati grandi in `data_cache/` (`v6_g100_*`, `v6_live/`, `v6_livegrid_*`, `v6_livealt_*`, `v6_raw/`).
