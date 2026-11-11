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

## 6. Registrazione live (PROVVISORIO: solo segmento A, 39 minuti; il segmento B è in corso) — 07_live_A.out
- Latenza misurata da questa macchina (FATTO; orologio locale allineato a Binance entro ±93 ms): il dato arriva vecchio di ~96 ms da Binance,
  ~60–130 ms da Kraken Futures, **~325–370 ms da Hyperliquid** (p95 480–580 ms). Andata/ritorno di una richiesta: 185–190 ms HL e Binance, 115 ms Kraken.
- Spread mediani: HL BTC 0,13 bp, ETH 0,48, SOL 0,12; Kraken BTC 0,13, ETH 0,48, SOL 1,18. Profondità HL entro 5 bp per lato: BTC 4,5 M$, ETH 3,2 M$, SOL 0,4 M$.
- Lead-lag Binance → Hyperliquid: reale e grande. Dopo un movimento Binance ≥ 2 bp in 500 ms, HL non si è ancora mosso e fa +2,9…+3,7 bp nei 5 s successivi
  (latenza 200 ms), +2,4…+3,4 bp a 500 ms, +0,7…+1,6 bp a 1 s. Costo 9 bp. Eventi ≥ 4 bp: 5–12 bp a 500 ms ma n = 4–11.
- Market making su HL, fill conservativo: BTC −2,3, ETH −3,6, SOL −2,0 bp/$ netti; al tocco −1,6…−1,9.
