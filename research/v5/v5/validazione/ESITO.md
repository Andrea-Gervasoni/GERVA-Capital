# Validazione v5 — esito sui tre claim (tutto SIMULATO)

Script e output in questa cartella (`c1_indici`, `c2_listing`, `c2_hl`, `c2_hl_hip3`, `c2_tradfi`, `c3_gq`: `.py` + `.out`). Ogni numero di testa è stato ricalcolato con codice mio dai dati grezzi in cache.

## Claim 1 — A5 MR (IBS < 0,2 e VIX ≥ 20): INDEBOLITO
- Riprodotto: +0,112 R, t 3,69, 32 trade/anno; verifica +0,262 su 62 (analista +0,11 / 3,7 / 32 / +0,26). 978 trade su 978 coincidono.
- Nessun look-ahead: ingresso sempre alla barra dopo il segnale; con il VIX del giorno prima +0,114; IBS e ATR su prezzi non rettificati; troncamento 900 confronti, 0 differenze. Stop prudenti (`a5_indici/lab.py:108,111`). Il raggruppamento non gonfia t (t mensile 3,66).
- Difetto 1, ritardo: con un giorno di ritardo MR scende a +0,061 (t 2,0), verifica +0,123 (t 0,8). `REPORT.md:55` riporta solo il flusso intero (+0,082).
- Difetto 2, verifica fragile: senza filtro −0,044 (n 241); VIX ≥ 18 +0,102 (t 0,9); ≥ 22 +0,303; ≥ 25 +0,266 (n 18). Senza i 5 trade migliori +0,049; il 2025 fa 10 R su 16. In scelta l'effetto cresce con la soglia (0,069 / 0,102 / 0,110 / 0,143): il 20 non è un punto isolato.
- Difetto 3, non è nuovo (`gerva/strategies/book.py:65`): il 100% dei segnali su SPY e QQQ cade con EQ-MR già long; il 72% delle notti A5 è già in EQ-MR; il 75–80% del rendimento lordo di EQ-MR viene dai giorni con VIX ≥ 20. Sono gli stessi trade a leva 18–20x, più IWM.
- Lo stop a 1 ATR dimezza il margine (senza stop +0,219).
- Numero da usare: +0,06…+0,09 R; la verifica (t 1,8) non autorizza +0,26. Non contare ΔN pieno.

## Claim 2 — A6 LISTING-SHORT: ROTTO come trade eseguibile
- Riprodotto su Binance: +0,158 R (t 3,18), verifica +0,118 (t 2,21); 773 trade identici.
- Hyperliquid (API raggiungibile): di 655 quotazioni Binance dal 2023-06, **134 (20,5%) negoziabili entro 24h, 136 (20,8%) entro 7 giorni**; 517 mai. Per anno: 48%, 43%, 19%, **2% nel 2026**. 102 delle 134 erano già su Hyperliquid prima di Binance.
- R sulle candele e sul funding di Hyperliquid, stesso ingresso: **+0,139 R, t 1,1, n 133, 41 trade/anno** (candele 4h per 71, giornaliere per 61, orarie per 1: l'API conserva 5000 candele). Senza i 5 migliori per anno −0,196. Ancorato alla quotazione di Hyperliquid: +0,103 (t 0,8, n 141).
- Il funding non è il problema: su Hyperliquid lo short incassa ≈ 0 (Binance −0,42% per trade).
- `a6_eventi/07_listing.py:10`: l'universo include almeno 93 perp su azioni, ETF e materie prime (91 nel 2026: R −0,076) e migrazioni (POL, RENDER, S). Senza, verifica +0,148, ma N cala.
- `a6_eventi/lib.py:67`: sulle barre orarie il salto oltre lo stop non scatta mai (0 casi). Con 300 pb verifica +0,024; riempimento al massimo della barra −0,001.
- `a6_eventi/REPORT.md:61`: +0,152 e +0,044 sono calcolati sul libro a 773 trade (base +0,179); su 836 sono +0,128 e +0,032.
- Numero da usare: ΔN ≈ 41 l'anno a +0,10…+0,14 R non significativo. Per il fondo: zero finché non c'è una sede.

## Claim 3 — A1 GQ ≥ 0,53: REGGE come stima, differenza non significativa
- Riprodotto esattamente: conviction +0,237 / verifica +0,180; GQ +0,339 / +0,276 (605 trade, scarto 0). Soglie ricalcolate 0,532 e −0,503. Troncamento 240 confronti, 0 differenze: il VWAP del mese (`a1_indicatore/lib.py:94`) è causale.
- Soglia, verifica: 0,4 → +0,209; 0,53 → +0,280; 0,7 → +0,300 (sempre sopra la conviction).
- Componenti, verifica: senza VWM +0,180 (vantaggio azzerato); solo VWM +0,276; senza TQ +0,279; senza TQ_BTC +0,342. Tutto il miglioramento è il VWAP.
- Perp 5m, verifica: GQ +0,247 contro +0,160. Con funding ×2,1: **+0,217 contro +0,130**; con costi doppi +0,179 contro +0,090.
- Bootstrap appaiato a blocchi mensili, verifica: +0,096, IC 90% [−0,058; +0,252], P(>0) 0,84.
- 2025: +0,07; 2026: −0,01 (conviction +0,14).
- Numero da usare: +0,22 R in verifica (perp, funding Hyperliquid); guadagno +0,09 R non distinguibile da zero.

## Non controllato
Notte dei CFD dopo il 2018; liquidità e scarti nelle prime 48 ore; candele orarie Hyperliquid prima del 2026-04; score della conviction (importato, non riscritto); perp regolati UE.
