# Kronos (foundation model per candele finanziarie): verifica empirica fuori campione

> TEST SU DATI STORICI. Nessun numero di questa pagina viene da trading live o paper.

Data del test: 2026-11-10/11. Script: research/v5/kronos_eval.py.

## 1. Sintesi
Risultato nullo. Su 7 configurazioni (BTC, ETH, SPY; orario e giornaliero) Kronos-small usato cosi' com'e' non prevede la direzione, non e' calibrato e non produce un rendimento netto positivo dopo i costi.
Numeri chiave (BTC 1h, contesto 256, orizzonte 24h, 704 previsioni): hit rate 51,7% [48,0; 55,4] contro 53,1% di "sempre long"; IC +0,004 [-0,070; +0,082]; banda p10-p90 che contiene il prezzo nel 41,1% dei casi (bootstrap ingenuo 83,2%); long/short +0,2 bp lordi per trade, -13,8 bp a 0,07% per lato, -59,8 bp a 0,30% per lato; gara stop/target AUC 0,489.

## 2. Cosa e' stato testato
- Modello NeoQuasar/Kronos-small (24,7 M parametri, revisione 901c26c), tokenizer NeoQuasar/Kronos-Tokenizer-base (revisione 0e01173), codice github.com/shiyu-coder/Kronos clonato il 2026-11-10. Zero-shot, senza fine-tuning.
- Cutoff di addestramento: giugno 2024 (paper arXiv 2508.02739, appendice "Forecasting Task Setup"). README e model card non riportano date.
- Periodo di test: origini dal 2024-07-01 al 2026-10-31. Controllo in piu': sotto-periodo dopo il 2025-09-10, data dell'ultima modifica dei pesi su Hugging Face (Tabella H).
- Dati: cache parquet del progetto. Binance spot 5m ricampionato a 1h (BTCUSDT, ETHUSDT), Binance 1d (BTCUSDT), Yahoo SPY 1d rettificato per dividendi, Yahoo SPY 1h.
- Campionamento: T=1,0 e top_p=0,9 (default del README), 50 percorsi per origine; una configurazione di sensibilita' con top_p=1,0.
- Disegno ridotto per il tempo di calcolo: 50 percorsi (la ricetta social ne chiede 1.000) e tetto di 20 minuti per processo. BTC 1h usa 704 origini su 818, ETH 1h 688 su 818, distribuite uniformemente sul periodo. L'affidabilita' Monte Carlo del segnale e' 0,90-0,99: il risultato nullo non dipende dal numero di percorsi.
- Runtime: circa 21 minuti su 4 core CPU (73 minuti-CPU di inferenza).
- Inferenza: campionatore a cache che restituisce ogni percorso, verificato contro il codice ufficiale (logits uguali entro 1e-5, stessa uscita a parita' di seed, coerente con KronosPredictor.predict su 8 origini giornaliere).

## 3. Metodo
- Origine = ultima barra del contesto. Origini non sovrapposte sugli orari (passo H+1); passo 1 giorno sui giornalieri, con bootstrap a blocchi e sottoinsieme non sovrapposto per direzione e trading.
- Calibrazione: copertura delle bande p10-p90 e p25-p75 all'orizzonte, contro un bootstrap ingenuo dei rendimenti del contesto senza drift.
- Direzione: segno della mediana prevista, contro "sempre long" e momentum (segno del rendimento delle ultime H barre).
- IC: Spearman fra rendimento medio previsto e realizzato, all'orizzonte e a 1 barra.
- Trading: long sopra la soglia, short sotto (piu' variante solo long), uscita all'orizzonte. Soglie fissate prima: 0 e 0,5 x volatilita' del contesto all'orizzonte. Costi per lato 0,07% e 0,30% (crypto), 0,02% (SPY), andata e ritorno a ogni trade. Sharpe annualizzato, tasso privo di rischio 0.
- Gara: stop -1 ATR(14), target +2 ATR(14); se la stessa barra tocca entrambi conta come stop.
- Intervalli: Wilson per le frequenze, bootstrap (2.000 ricampionamenti) per il resto.

## 4. Risultati
### Tabella A - Configurazioni e campioni

| config | dataset | contesto | orizzonte | passo | top_p | percorsi | origini usate / pianificate | non sovrapposte | prima origine | ultima origine | inferenza (s, 1 thread) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| btc_1h_c256_h24 | btc_1h | 256 | 24 | 25 | 0.9 | 50 | 704 / 818 | 704 | 2024-07-01 | 2026-10-30 | 966 |
| btc_1h_c128_h48 | btc_1h | 128 | 48 | 49 | 0.9 | 50 | 417 / 417 | 417 | 2024-07-01 | 2026-10-28 | 1062 |
| eth_1h_c256_h24 | eth_1h | 256 | 24 | 25 | 0.9 | 50 | 688 / 818 | 688 | 2024-07-01 | 2026-10-30 | 949 |
| btc_1d_c256_h7 | btc_1d | 256 | 7 | 1 | 0.9 | 50 | 846 / 846 | 121 | 2024-07-01 | 2026-10-24 | 408 |
| spy_1d_c256_h5 | spy_1d | 256 | 5 | 1 | 0.9 | 50 | 582 / 582 | 117 | 2024-07-01 | 2026-10-23 | 235 |
| spy_1h_c256_h7 | spy_1h | 256 | 7 | 8 | 0.9 | 50 | 508 / 508 | 508 | 2024-07-01 | 2026-10-28 | 254 |
| btc_1h_c256_h24_topp1 | btc_1h | 256 | 24 | 25 | 1.0 | 50 | 400 / 400 | 400 | 2024-07-01 | 2026-10-30 | 506 |

### Tabella B - Calibrazione all'orizzonte (quota di chiusure reali dentro la banda; atteso 80% / 50%)

| config | Kronos p10-p90 | IC95% | Kronos p25-p75 | IC95% | sotto p10 / sopra p90 | naive p10-p90 | naive p25-p75 | larghezza banda Kronos/naive (mediana) |
|---|---|---|---|---|---|---|---|---|
| btc_1h_c256_h24 | 41.1% | [37.6; 44.7] | 24.1% | [20.9; 27.1] | 25.4% / 33.5% | 83.2% [80.5; 85.9] | 58.9% [55.3; 62.6] | 0.40 |
| btc_1h_c128_h48 | 33.6% | [29.3; 37.9] | 17.3% | [13.7; 21.1] | 28.1% / 38.4% | 82.0% [78.2; 85.9] | 55.4% [50.6; 60.4] | 0.33 |
| eth_1h_c256_h24 | 39.4% | [35.8; 42.9] | 23.4% | [20.1; 26.5] | 26.2% / 34.4% | 81.2% [78.5; 84.3] | 56.8% [53.2; 60.8] | 0.42 |
| btc_1d_c256_h7 | 40.8% | [33.7; 47.8] | 23.6% | [18.7; 28.8] | 25.7% / 33.6% | 85.0% [80.0; 89.2] | 59.7% [54.8; 65.0] | 0.58 |
| spy_1d_c256_h5 | 29.4% | [23.2; 35.4] | 15.5% | [11.0; 20.3] | 6.0% / 64.6% | 81.4% [76.1; 86.3] | 54.1% [48.5; 60.1] | 0.89 |
| spy_1h_c256_h7 | 62.8% | [58.5; 67.1] | 37.4% | [33.3; 41.5] | 16.5% / 20.7% | 81.5% [78.1; 84.8] | 50.2% [45.9; 54.3] | 0.71 |
| btc_1h_c256_h24_topp1 | 47.2% | [42.2; 52.0] | 29.2% | [24.8; 34.0] | 23.5% / 29.2% | 82.2% [78.5; 86.0] | 63.7% [59.0; 68.5] | 0.53 |

### Tabella C - Direzione (origini non sovrapposte; IC95% di Wilson)

| config | n | Kronos (segno mediana) | IC95% | p vs 50% | sempre long | momentum (segno ultimo rend. H barre) | Kronos - sempre long | IC95% diff. | quota previsioni long |
|---|---|---|---|---|---|---|---|---|---|
| btc_1h_c256_h24 | 704 | 51.7% | [48.0; 55.4] | 0.39 | 53.1% | 51.3% [47.6; 55.0] | -1.4 pp | [-7.4; 4.7] | 37.5% |
| btc_1h_c128_h48 | 417 | 52.0% | [47.2; 56.8] | 0.43 | 50.1% | 53.2% [48.4; 58.0] | +1.9 pp | [-6.0; 10.3] | 28.5% |
| eth_1h_c256_h24 | 688 | 50.3% | [46.6; 54.0] | 0.91 | 51.7% | 48.8% [45.1; 52.6] | -1.5 pp | [-7.4; 4.4] | 35.8% |
| btc_1d_c256_h7 | 121 | 43.0% | [34.5; 51.9] | 0.15 | 49.6% | 44.6% [36.1; 53.5] | -6.6 pp | [-19.8; 5.8] | 47.1% |
| spy_1d_c256_h5 | 117 | 42.7% | [34.1; 51.8] | 0.14 | 61.5% | 47.0% [38.2; 56.0] | -18.8 pp | [-35.9; -2.6] | 16.2% |
| spy_1h_c256_h7 | 508 | 52.0% | [47.6; 56.3] | 0.40 | 54.1% | 47.2% [42.9; 51.6] | -2.2 pp | [-8.5; 3.9] | 49.0% |
| btc_1h_c256_h24_topp1 | 400 | 48.8% | [43.9; 53.6] | 0.65 | 52.0% | 50.2% [45.4; 55.1] | -3.3 pp | [-11.0; 4.5] | 36.2% |

### Tabella D - Information coefficient (Spearman, rendimento medio previsto vs realizzato)

| config | IC orizzonte | t | IC95% bootstrap | IC 1 passo | t | IC95% bootstrap | IC momentum orizzonte | IC momentum 1 passo | IC orizzonte (ancora = close ricostruito) | IC 1 passo (ancora ricostruita) |
|---|---|---|---|---|---|---|---|---|---|---|
| btc_1h_c256_h24 | +0.004 | +0.10 | [-0.070; +0.082] | -0.011 | -0.28 | [-0.094; +0.071] | +0.052 | -0.046 | -0.004 (t -0.11) | -0.033 (t -0.87) |
| btc_1h_c128_h48 | +0.009 | +0.19 | [-0.093; +0.109] | -0.009 | -0.18 | [-0.112; +0.093] | +0.017 | +0.005 | +0.012 (t +0.25) | -0.026 (t -0.52) |
| eth_1h_c256_h24 | -0.008 | -0.20 | [-0.087; +0.072] | +0.081 | +2.12 | [+0.002; +0.158] | -0.015 | -0.060 | -0.008 (t -0.22) | +0.024 (t +0.63) |
| btc_1d_c256_h7 | -0.023 | -0.25 | [-0.144; +0.110] | +0.023 | +0.65 | [-0.046; +0.090] | -0.019 | -0.003 | -0.027 (t -0.29) | -0.004 (t -0.11) |
| spy_1d_c256_h5 | +0.144 | +1.56 | [-0.002; +0.301] | +0.057 | +1.37 | [-0.025; +0.141] | -0.103 | -0.057 | +0.133 (t +1.44) | +0.055 (t +1.32) |
| spy_1h_c256_h7 | -0.003 | -0.07 | [-0.099; +0.094] | +0.047 | +1.05 | [-0.046; +0.146] | -0.070 | -0.028 | +0.026 (t +0.59) | +0.033 (t +0.75) |
| btc_1h_c256_h24_topp1 | -0.018 | -0.35 | [-0.117; +0.089] | -0.009 | -0.19 | [-0.110; +0.093] | +0.061 | -0.048 | -0.022 (t -0.45) | -0.042 (t -0.83) |

### Tabella E - Regola di trading netta dei costi (origini non sovrapposte, uscita all'orizzonte, andata+ritorno pagati a ogni trade)

| config | soglia | variante | costo/lato | trade (long/short) su finestre | netto medio per trade (bp) | IC95% (bp) | % vincenti | Sharpe ann. | max drawdown | rend. totale | Sharpe ann. se costo solo sui cambi di posizione |
|---|---|---|---|---|---|---|---|---|---|---|---|
| btc_1h_c256_h24 | - | **buy&hold stesse finestre** | 0 | 704 | +6.9 | - | - | +0.57 | -48.2% | 35.4% | - |
| btc_1h_c256_h24 | 0 | long_short | 0.00% | 704 (239/465) su 704 | +0.2 | [-17.0; +17.1] | 50.1% | +0.01 | -50.3% | -16.0% | +0.01 |
| btc_1h_c256_h24 | 0 | long_short | 0.07% | 704 (239/465) su 704 | -13.8 | [-31.5; +2.3] | 46.7% | -1.13 | -75.1% | -68.7% | -0.34 |
| btc_1h_c256_h24 | 0 | long_short | 0.30% | 704 (239/465) su 704 | -59.8 | [-76.9; -43.6] | 34.5% | -4.88 | -98.9% | -98.8% | -1.50 |
| btc_1h_c256_h24 | 0 | long_only | 0.00% | 239 (239/0) su 704 | +10.5 | [-21.0; +42.1] | 54.8% | +0.46 | -24.6% | 19.2% | +0.46 |
| btc_1h_c256_h24 | 0 | long_only | 0.07% | 239 (239/0) su 704 | -3.5 | [-35.1; +27.2] | 50.6% | -0.15 | -35.3% | -14.7% | +0.18 |
| btc_1h_c256_h24 | 0 | long_only | 0.30% | 239 (239/0) su 704 | -49.5 | [-81.7; -17.0] | 36.4% | -2.14 | -72.5% | -71.7% | -0.75 |
| btc_1h_c256_h24 | 0.5vol | long_short | 0.00% | 242 (90/152) su 704 | -21.6 | [-55.1; +7.7] | 50.4% | -0.94 | -51.7% | -45.2% | -0.94 |
| btc_1h_c256_h24 | 0.5vol | long_short | 0.07% | 242 (90/152) su 704 | -35.6 | [-69.1; -4.5] | 48.3% | -1.54 | -65.1% | -61.0% | -1.24 |
| btc_1h_c256_h24 | 0.5vol | long_short | 0.30% | 242 (90/152) su 704 | -81.6 | [-113.7; -50.5] | 36.0% | -3.44 | -88.2% | -87.3% | -2.22 |
| btc_1h_c256_h24 | 0.5vol | long_only | 0.00% | 90 (90/0) su 704 | -7.8 | [-73.4; +49.2] | 58.9% | -0.18 | -32.6% | -10.3% | -0.18 |
| btc_1h_c256_h24 | 0.5vol | long_only | 0.07% | 90 (90/0) su 704 | -21.8 | [-85.6; +36.4] | 56.7% | -0.50 | -36.1% | -21.0% | -0.34 |
| btc_1h_c256_h24 | 0.5vol | long_only | 0.30% | 90 (90/0) su 704 | -67.8 | [-130.8; -9.3] | 40.0% | -1.53 | -50.4% | -47.9% | -0.85 |
| btc_1h_c128_h48 | - | **buy&hold stesse finestre** | 0 | 417 | +8.7 | - | - | +0.36 | -53.6% | 16.3% | - |
| btc_1h_c128_h48 | 0 | long_short | 0.00% | 417 (126/291) su 417 | +5.6 | [-24.2; +33.7] | 51.3% | +0.24 | -44.4% | 2.1% | +0.24 |
| btc_1h_c128_h48 | 0 | long_short | 0.07% | 417 (126/291) su 417 | -8.4 | [-39.2; +22.9] | 49.4% | -0.35 | -57.1% | -43.1% | -0.01 |
| btc_1h_c128_h48 | 0 | long_short | 0.30% | 417 (126/291) su 417 | -54.4 | [-85.6; -23.0] | 42.9% | -2.28 | -93.0% | -91.7% | -0.80 |
| btc_1h_c128_h48 | 0 | long_only | 0.00% | 126 (126/0) su 417 | +23.7 | [-33.7; +77.8] | 52.4% | +0.53 | -26.3% | 26.0% | +0.53 |
| btc_1h_c128_h48 | 0 | long_only | 0.07% | 126 (126/0) su 417 | +9.7 | [-48.5; +66.5] | 51.6% | +0.22 | -33.4% | 5.7% | +0.32 |
| btc_1h_c128_h48 | 0 | long_only | 0.30% | 126 (126/0) su 417 | -36.3 | [-97.5; +16.4] | 43.7% | -0.82 | -53.5% | -40.9% | -0.39 |
| btc_1h_c128_h48 | 0.5vol | long_short | 0.00% | 121 (43/78) su 417 | -31.2 | [-100.5; +31.0] | 47.1% | -0.61 | -45.6% | -37.0% | -0.61 |
| btc_1h_c128_h48 | 0.5vol | long_short | 0.07% | 121 (43/78) su 417 | -45.2 | [-111.4; +19.3] | 44.6% | -0.88 | -53.6% | -46.9% | -0.81 |
| btc_1h_c128_h48 | 0.5vol | long_short | 0.30% | 121 (43/78) su 417 | -91.2 | [-156.7; -27.4] | 41.3% | -1.75 | -72.7% | -69.7% | -1.48 |
| btc_1h_c128_h48 | 0.5vol | long_only | 0.00% | 43 (43/0) su 417 | +3.9 | [-98.4; +105.4] | 44.2% | +0.05 | -19.6% | -0.9% | +0.05 |
| btc_1h_c128_h48 | 0.5vol | long_only | 0.07% | 43 (43/0) su 417 | -10.1 | [-112.9; +89.9] | 41.9% | -0.13 | -21.0% | -6.7% | -0.10 |
| btc_1h_c128_h48 | 0.5vol | long_only | 0.30% | 43 (43/0) su 417 | -56.1 | [-159.9; +50.9] | 39.5% | -0.69 | -30.7% | -23.5% | -0.59 |
| eth_1h_c256_h24 | - | **buy&hold stesse finestre** | 0 | 688 | -2.1 | - | - | -0.11 | -67.8% | -43.1% | - |
| eth_1h_c256_h24 | 0 | long_short | 0.00% | 688 (232/456) su 688 | -15.6 | [-41.2; +10.1] | 49.7% | -0.83 | -83.9% | -77.7% | -0.83 |
| eth_1h_c256_h24 | 0 | long_short | 0.07% | 688 (232/456) su 688 | -29.6 | [-56.6; -4.3] | 47.8% | -1.58 | -93.7% | -91.5% | -1.04 |
| eth_1h_c256_h24 | 0 | long_short | 0.30% | 688 (232/456) su 688 | -75.6 | [-101.9; -50.9] | 38.8% | -4.05 | -99.7% | -99.6% | -1.73 |
| eth_1h_c256_h24 | 0 | long_only | 0.00% | 232 (232/0) su 688 | -26.1 | [-74.8; +24.4] | 52.2% | -0.72 | -61.1% | -54.7% | -0.72 |
| eth_1h_c256_h24 | 0 | long_only | 0.07% | 232 (232/0) su 688 | -40.1 | [-91.7; +11.8] | 49.1% | -1.11 | -70.6% | -67.3% | -0.88 |
| eth_1h_c256_h24 | 0 | long_only | 0.30% | 232 (232/0) su 688 | -86.1 | [-135.7; -37.2] | 38.4% | -2.34 | -89.4% | -88.8% | -1.41 |
| eth_1h_c256_h24 | 0.5vol | long_short | 0.00% | 259 (96/163) su 688 | -23.0 | [-69.0; +22.2] | 51.7% | -0.69 | -63.6% | -54.7% | -0.69 |
| eth_1h_c256_h24 | 0.5vol | long_short | 0.07% | 259 (96/163) su 688 | -37.0 | [-85.2; +8.6] | 50.6% | -1.11 | -74.2% | -68.6% | -0.90 |
| eth_1h_c256_h24 | 0.5vol | long_short | 0.30% | 259 (96/163) su 688 | -83.0 | [-128.1; -36.7] | 42.9% | -2.46 | -91.7% | -90.5% | -1.60 |
| eth_1h_c256_h24 | 0.5vol | long_only | 0.00% | 96 (96/0) su 688 | -63.0 | [-155.3; +23.5] | 54.2% | -0.99 | -58.4% | -50.7% | -0.99 |
| eth_1h_c256_h24 | 0.5vol | long_only | 0.07% | 96 (96/0) su 688 | -77.0 | [-168.0; +11.0] | 51.0% | -1.20 | -63.0% | -56.9% | -1.09 |
| eth_1h_c256_h24 | 0.5vol | long_only | 0.30% | 96 (96/0) su 688 | -123.0 | [-215.8; -39.0] | 42.7% | -1.88 | -74.8% | -72.5% | -1.42 |
| btc_1d_c256_h7 | - | **buy&hold stesse finestre** | 0 | 121 | +41.2 | - | - | +0.45 | -51.7% | 27.4% | - |
| btc_1d_c256_h7 | 0 | long_short | 0.00% | 121 (58/63) su 121 | -89.8 | [-210.3; +18.9] | 40.5% | -0.99 | -78.0% | -74.6% | -0.99 |
| btc_1d_c256_h7 | 0 | long_short | 0.07% | 121 (58/63) su 121 | -103.8 | [-226.6; +8.8] | 40.5% | -1.14 | -81.3% | -78.6% | -1.02 |
| btc_1d_c256_h7 | 0 | long_short | 0.30% | 121 (58/63) su 121 | -149.8 | [-271.8; -41.1] | 38.8% | -1.65 | -89.0% | -87.9% | -1.11 |
| btc_1d_c256_h7 | 0 | long_only | 0.00% | 58 (58/0) su 121 | -50.8 | [-202.3; +113.6] | 39.7% | -0.42 | -43.1% | -33.3% | -0.42 |
| btc_1d_c256_h7 | 0 | long_only | 0.07% | 58 (58/0) su 121 | -64.8 | [-223.1; +85.1] | 39.7% | -0.53 | -46.2% | -38.6% | -0.44 |
| btc_1d_c256_h7 | 0 | long_only | 0.30% | 58 (58/0) su 121 | -110.8 | [-273.1; +46.8] | 39.7% | -0.90 | -56.5% | -53.1% | -0.51 |
| btc_1d_c256_h7 | 0.5vol | long_short | 0.00% | 69 (27/42) su 121 | -6.7 | [-129.3; +106.8] | 49.3% | -0.07 | -34.0% | -12.7% | -0.07 |
| btc_1d_c256_h7 | 0.5vol | long_short | 0.07% | 69 (27/42) su 121 | -20.7 | [-139.1; +103.2] | 49.3% | -0.22 | -36.9% | -20.8% | -0.12 |
| btc_1d_c256_h7 | 0.5vol | long_short | 0.30% | 69 (27/42) su 121 | -66.7 | [-194.3; +48.0] | 46.4% | -0.71 | -50.1% | -42.4% | -0.27 |
| btc_1d_c256_h7 | 0.5vol | long_only | 0.00% | 27 (27/0) su 121 | +9.6 | [-222.9; +232.0] | 48.1% | +0.06 | -32.1% | -2.1% | +0.06 |
| btc_1d_c256_h7 | 0.5vol | long_only | 0.07% | 27 (27/0) su 121 | -4.4 | [-225.4; +215.8] | 48.1% | -0.03 | -34.0% | -5.7% | +0.03 |
| btc_1d_c256_h7 | 0.5vol | long_only | 0.30% | 27 (27/0) su 121 | -50.4 | [-280.7; +165.0] | 48.1% | -0.29 | -39.9% | -16.8% | -0.07 |
| spy_1d_c256_h5 | - | **buy&hold stesse finestre** | 0 | 117 | +33.5 | - | - | +1.22 | -13.8% | 44.8% | - |
| spy_1d_c256_h5 | 0 | long_short | 0.00% | 117 (19/98) su 117 | -10.4 | [-46.0; +26.0] | 42.7% | -0.38 | -28.4% | -13.5% | -0.38 |
| spy_1d_c256_h5 | 0 | long_short | 0.02% | 117 (19/98) su 117 | -14.4 | [-51.9; +19.0] | 42.7% | -0.52 | -30.2% | -17.4% | -0.40 |
| spy_1d_c256_h5 | 0 | long_only | 0.00% | 19 (19/0) su 117 | +71.2 | [-54.1; +197.7] | 63.2% | +0.69 | -10.1% | 13.6% | +0.69 |
| spy_1d_c256_h5 | 0 | long_only | 0.02% | 19 (19/0) su 117 | +67.2 | [-68.0; +190.6] | 63.2% | +0.65 | -10.3% | 12.7% | +0.68 |
| spy_1d_c256_h5 | 0.5vol | long_short | 0.00% | 91 (7/84) su 117 | -27.8 | [-65.6; +9.1] | 39.6% | -0.94 | -27.5% | -23.6% | -0.94 |
| spy_1d_c256_h5 | 0.5vol | long_short | 0.02% | 91 (7/84) su 117 | -31.8 | [-70.4; +6.2] | 39.6% | -1.08 | -30.0% | -26.3% | -0.96 |
| spy_1d_c256_h5 | 0.5vol | long_only | 0.00% | 7 (7/0) su 117 | -62.1 | [-314.4; +202.5] | 42.9% | -0.31 | -8.7% | -4.7% | -0.31 |
| spy_1d_c256_h5 | 0.5vol | long_only | 0.02% | 7 (7/0) su 117 | -66.1 | [-310.0; +198.5] | 42.9% | -0.33 | -8.8% | -4.9% | -0.32 |
| spy_1h_c256_h7 | - | **buy&hold stesse finestre** | 0 | 508 | +4.4 | - | - | +0.70 | -14.0% | 22.4% | - |
| spy_1h_c256_h7 | 0 | long_short | 0.00% | 508 (245/263) su 508 | +0.3 | [-7.6; +8.1] | 51.6% | +0.05 | -16.5% | -0.7% | +0.05 |
| spy_1h_c256_h7 | 0 | long_short | 0.02% | 508 (245/263) su 508 | -3.7 | [-11.9; +4.2] | 49.8% | -0.59 | -20.7% | -19.0% | -0.16 |
| spy_1h_c256_h7 | 0 | long_only | 0.00% | 245 (245/0) su 508 | +4.9 | [-7.9; +17.7] | 55.9% | +0.50 | -10.5% | 11.3% | +0.50 |
| spy_1h_c256_h7 | 0 | long_only | 0.02% | 245 (245/0) su 508 | +0.9 | [-12.3; +13.3] | 55.1% | +0.09 | -13.4% | 0.9% | +0.36 |
| spy_1h_c256_h7 | 0.5vol | long_short | 0.00% | 78 (34/44) su 508 | +3.6 | [-22.4; +32.6] | 51.3% | +0.17 | -5.8% | 2.2% | +0.17 |
| spy_1h_c256_h7 | 0.5vol | long_short | 0.02% | 78 (34/44) su 508 | -0.4 | [-27.5; +27.3] | 47.4% | -0.02 | -6.4% | -0.9% | +0.04 |
| spy_1h_c256_h7 | 0.5vol | long_only | 0.00% | 34 (34/0) su 508 | +6.1 | [-40.7; +58.0] | 52.9% | +0.16 | -4.6% | 1.7% | +0.16 |
| spy_1h_c256_h7 | 0.5vol | long_only | 0.02% | 34 (34/0) su 508 | +2.1 | [-43.9; +52.0] | 50.0% | +0.05 | -5.3% | 0.3% | +0.09 |
| btc_1h_c256_h24_topp1 | - | **buy&hold stesse finestre** | 0 | 400 | -8.5 | - | - | -0.68 | -46.1% | -36.2% | - |
| btc_1h_c256_h24_topp1 | 0 | long_short | 0.00% | 400 (146/254) su 400 | +10.0 | [-13.4; +31.7] | 52.0% | +0.81 | -28.6% | 34.1% | +0.81 |
| btc_1h_c256_h24_topp1 | 0 | long_short | 0.07% | 400 (146/254) su 400 | -4.0 | [-26.5; +18.3] | 48.0% | -0.32 | -42.6% | -23.4% | +0.35 |
| btc_1h_c256_h24_topp1 | 0 | long_short | 0.30% | 400 (146/254) su 400 | -50.0 | [-73.9; -27.6] | 35.5% | -4.02 | -89.3% | -87.9% | -1.17 |
| btc_1h_c256_h24_topp1 | 0 | long_only | 0.00% | 146 (146/0) su 400 | +2.1 | [-39.9; +40.9] | 55.5% | +0.10 | -22.7% | -1.3% | +0.10 |
| btc_1h_c256_h24_topp1 | 0 | long_only | 0.07% | 146 (146/0) su 400 | -11.9 | [-53.5; +27.5] | 50.7% | -0.55 | -30.3% | -19.6% | -0.26 |
| btc_1h_c256_h24_topp1 | 0 | long_only | 0.30% | 146 (146/0) su 400 | -57.9 | [-98.8; -20.1] | 37.7% | -2.63 | -60.5% | -59.0% | -1.45 |
| btc_1h_c256_h24_topp1 | 0.5vol | long_short | 0.00% | 156 (55/101) su 400 | -23.9 | [-64.3; +14.1] | 51.3% | -1.13 | -43.8% | -34.4% | -1.13 |
| btc_1h_c256_h24_topp1 | 0.5vol | long_short | 0.07% | 156 (55/101) su 400 | -37.9 | [-78.5; +0.8] | 48.7% | -1.79 | -53.8% | -47.3% | -1.55 |
| btc_1h_c256_h24_topp1 | 0.5vol | long_short | 0.30% | 156 (55/101) su 400 | -83.9 | [-122.1; -45.3] | 34.0% | -3.86 | -76.3% | -74.4% | -2.90 |
| btc_1h_c256_h24_topp1 | 0.5vol | long_only | 0.00% | 55 (55/0) su 400 | -37.4 | [-124.8; +39.0] | 56.4% | -0.87 | -31.4% | -20.6% | -0.87 |
| btc_1h_c256_h24_topp1 | 0.5vol | long_only | 0.07% | 55 (55/0) su 400 | -51.4 | [-135.6; +19.9] | 52.7% | -1.19 | -35.5% | -26.6% | -1.10 |
| btc_1h_c256_h24_topp1 | 0.5vol | long_only | 0.30% | 55 (55/0) su 400 | -97.4 | [-180.0; -25.8] | 30.9% | -2.18 | -47.2% | -43.1% | -1.87 |

### Tabella F - Gara stop/target (stop = -1 ATR14, target = +2 ATR14, entro l'orizzonte)

| config | realizzato: target / stop / nessuno | Kronos previsto: target / stop / nessuno | naive: target / stop | Brier Kronos | Brier naive | Brier costante (in-sample) | AUC Kronos | IC95% | AUC naive |
|---|---|---|---|---|---|---|---|---|---|
| btc_1h_c256_h24 | 33.2% / 62.1% / 4.7% | 23.2% / 71.4% / 5.4% | 30.8% / 66.6% | 0.2960 | 0.2249 | 0.2219 | 0.489 | [0.444; 0.535] | 0.488 |
| btc_1h_c128_h48 | 33.8% / 64.7% / 1.4% | 20.4% / 77.8% / 1.9% | 32.4% / 67.4% | 0.2973 | 0.2246 | 0.2238 | 0.460 | [0.403; 0.517] | 0.515 |
| eth_1h_c256_h24 | 34.3% / 60.3% / 5.4% | 23.7% / 71.7% / 4.7% | 31.1% / 66.2% | 0.3158 | 0.2291 | 0.2254 | 0.474 | [0.428; 0.521] | 0.507 |
| btc_1d_c256_h7 | 18.9% / 52.4% / 28.7% | 23.1% / 66.2% / 10.7% | 22.3% / 58.1% | 0.2203 | 0.1524 | 0.1534 | 0.517 | [0.438; 0.594] | 0.583 |
| spy_1d_c256_h5 | 17.7% / 48.5% / 33.8% | 7.8% / 79.2% / 12.9% | 19.2% / 50.9% | 0.1632 | 0.1489 | 0.1457 | 0.541 | [0.454; 0.639] | 0.552 |
| spy_1h_c256_h7 | 25.8% / 54.5% / 19.7% | 19.3% / 59.6% / 21.2% | 23.2% / 55.7% | 0.2130 | 0.1940 | 0.1914 | 0.551 | [0.492; 0.606] | 0.530 |
| btc_1h_c256_h24_topp1 | 36.0% / 59.0% / 5.0% | 22.6% / 75.9% / 1.5% | 31.1% / 66.6% | 0.2913 | 0.2310 | 0.2304 | 0.494 | [0.432; 0.552] | 0.574 |

### Tabella G - Affidabilita' della probabilita' "target prima dello stop" (quintili della probabilita' prevista)

| config | quintile | P prevista (min-max) | P prevista media | frequenza realizzata | IC95% | n |
|---|---|---|---|---|---|---|
| btc_1h_c256_h24 | 1 | 0.00-0.04 | 1.2% | 33.3% | [26.1; 41.5] | 141 |
| btc_1h_c256_h24 | 2 | 0.04-0.10 | 6.8% | 34.0% | [26.7; 42.2] | 141 |
| btc_1h_c256_h24 | 3 | 0.10-0.20 | 14.7% | 34.0% | [26.7; 42.2] | 141 |
| btc_1h_c256_h24 | 4 | 0.20-0.40 | 28.2% | 31.2% | [24.1; 39.3] | 141 |
| btc_1h_c256_h24 | 5 | 0.40-1.00 | 65.4% | 33.6% | [26.3; 41.7] | 140 |
| btc_1h_c128_h48 | 1 | 0.00-0.06 | 2.1% | 33.3% | [24.2; 43.9] | 84 |
| btc_1h_c128_h48 | 2 | 0.06-0.12 | 8.5% | 35.7% | [26.3; 46.4] | 84 |
| btc_1h_c128_h48 | 3 | 0.12-0.18 | 15.2% | 43.4% | [33.2; 54.1] | 83 |
| btc_1h_c128_h48 | 4 | 0.18-0.32 | 23.9% | 32.5% | [23.4; 43.2] | 83 |
| btc_1h_c128_h48 | 5 | 0.32-0.94 | 52.7% | 24.1% | [16.2; 34.3] | 83 |
| eth_1h_c256_h24 | 1 | 0.00-0.04 | 1.2% | 37.7% | [30.0; 46.0] | 138 |
| eth_1h_c256_h24 | 2 | 0.04-0.10 | 7.2% | 34.8% | [27.3; 43.0] | 138 |
| eth_1h_c256_h24 | 3 | 0.10-0.20 | 15.8% | 33.3% | [26.0; 41.6] | 138 |
| eth_1h_c256_h24 | 4 | 0.20-0.38 | 28.6% | 36.5% | [28.9; 44.8] | 137 |
| eth_1h_c256_h24 | 5 | 0.38-1.00 | 65.9% | 29.2% | [22.2; 37.3] | 137 |
| btc_1d_c256_h7 | 1 | 0.00-0.02 | 0.1% | 19.4% | [14.2; 26.0] | 170 |
| btc_1d_c256_h7 | 2 | 0.02-0.06 | 3.3% | 18.3% | [13.2; 24.9] | 169 |
| btc_1d_c256_h7 | 3 | 0.06-0.20 | 11.7% | 15.4% | [10.7; 21.6] | 169 |
| btc_1d_c256_h7 | 4 | 0.20-0.46 | 32.0% | 23.1% | [17.4; 30.0] | 169 |
| btc_1d_c256_h7 | 5 | 0.48-1.00 | 68.4% | 18.3% | [13.2; 24.9] | 169 |
| spy_1d_c256_h5 | 1 | 0.00-0.00 | 0.0% | 17.1% | [11.3; 24.9] | 117 |
| spy_1d_c256_h5 | 2 | 0.00-0.02 | 0.5% | 16.2% | [10.6; 24.0] | 117 |
| spy_1d_c256_h5 | 3 | 0.02-0.04 | 2.8% | 14.7% | [9.4; 22.2] | 116 |
| spy_1d_c256_h5 | 4 | 0.04-0.12 | 7.9% | 16.4% | [10.7; 24.2] | 116 |
| spy_1d_c256_h5 | 5 | 0.12-0.86 | 28.1% | 24.1% | [17.3; 32.7] | 116 |
| spy_1h_c256_h7 | 1 | 0.00-0.04 | 1.9% | 20.6% | [13.9; 29.4] | 102 |
| spy_1h_c256_h7 | 2 | 0.04-0.12 | 7.5% | 28.4% | [20.6; 37.8] | 102 |
| spy_1h_c256_h7 | 3 | 0.12-0.20 | 15.5% | 20.6% | [13.9; 29.4] | 102 |
| spy_1h_c256_h7 | 4 | 0.20-0.32 | 25.7% | 31.7% | [23.4; 41.3] | 101 |
| spy_1h_c256_h7 | 5 | 0.32-0.92 | 46.2% | 27.7% | [19.9; 37.1] | 101 |
| btc_1h_c256_h24_topp1 | 1 | 0.00-0.04 | 2.2% | 36.2% | [26.6; 47.2] | 80 |
| btc_1h_c256_h24_topp1 | 2 | 0.04-0.12 | 8.8% | 40.0% | [30.0; 51.0] | 80 |
| btc_1h_c256_h24_topp1 | 3 | 0.12-0.22 | 16.9% | 27.5% | [18.9; 38.1] | 80 |
| btc_1h_c256_h24_topp1 | 4 | 0.22-0.36 | 28.5% | 38.8% | [28.8; 49.7] | 80 |
| btc_1h_c256_h24_topp1 | 5 | 0.36-1.00 | 56.6% | 37.5% | [27.7; 48.5] | 80 |

### Tabella H - Controlli: volatilita', errore di ricostruzione, sotto-periodi

| config | IC larghezza banda vs \|rend. realizzato\| (Kronos) | idem naive | errore ricostruzione ultimo close (mediana, bp) | sigma 1 barra (bp) | bias medio previsto-realizzato | affidabilita' Monte Carlo del segnale | dev.st. rend. medio previsto / realizzato | hit pre 2025-09-10 (n) | hit post 2025-09-10 (n) | IC orizzonte pre | IC orizzonte post |
|---|---|---|---|---|---|---|---|---|---|---|---|
| btc_1h_c256_h24 | +0.111 (t +3.0) | +0.175 | 9.1 | 43.6 | -0.36% | 0.97 | 2.39% / 2.29% | 52.6% (361) | 50.7% (343) | +0.028 (t +0.53) | -0.017 (t -0.31) |
| btc_1h_c128_h48 | +0.130 (t +2.7) | +0.077 | 7.9 | 42.4 | -0.56% | 0.98 | 1.95% / 3.19% | 53.3% (214) | 50.7% (203) | +0.007 (t +0.10) | +0.016 (t +0.23) |
| eth_1h_c256_h24 | +0.062 (t +1.6) | +0.162 | 12.4 | 64.2 | -0.27% | 0.98 | 3.82% / 3.49% | 51.6% (353) | 49.0% (335) | -0.021 (t -0.39) | +0.008 (t +0.14) |
| btc_1d_c256_h7 | +0.053 (t +0.6) | +0.048 | 58.6 | 244.9 | -2.36% | 0.99 | 9.70% / 6.08% | 41.3% (63) | 44.8% (58) | -0.018 (t -0.14) | +0.127 (t +0.96) |
| spy_1d_c256_h5 | +0.114 (t +1.2) | -0.061 | 27.0 | 81.6 | -2.83% | 0.99 | 2.41% / 2.07% | 36.7% (60) | 49.1% (57) | +0.214 (t +1.66) | +0.100 (t +0.74) |
| spy_1h_c256_h7 | +0.186 (t +4.2) | +0.201 | 7.0 | 30.2 | -0.04% | 0.90 | 0.44% / 0.93% | 53.1% (260) | 50.8% (248) | -0.016 (t -0.25) | -0.000 (t -0.00) |
| btc_1h_c256_h24_topp1 | +0.022 (t +0.4) | +0.154 | 9.5 | 43.3 | -0.31% | 0.96 | 2.34% / 2.32% | 47.8% (205) | 49.7% (195) | -0.062 (t -0.89) | +0.021 (t +0.29) |

## 5. Lettura dei risultati
1. Calibrazione scarsa: p10-p90 contiene il prezzo nel 29-63% dei casi invece dell'80%, p25-p75 nel 15-37% invece del 50%; il bootstrap ingenuo da' 81-85% e 50-60%. Le bande sono strette (0,33-0,89 volte quelle ingenue) e il loro centro e' spesso lontano dall'ultima chiusura. Con top_p=1,0 la copertura sale solo al 47%.
2. Direzione: hit rate fra 43,0% e 52,0%, mai distinguibile dal 50%. Su SPY giornaliero e' peggiore di "sempre long" di 18,8 punti [-35,9; -2,6]: il modello prevedeva ribassi nell'84% dei casi in un mercato rialzista.
3. IC: sotto 0,03 in valore assoluto su crypto e SPY orario. SPY giornaliero +0,144 con intervallo [-0,002; +0,301]. A 1 barra ETH +0,081 (t 2,1), che scende a +0,024 cambiando l'ancora di prezzo e non compare su BTC: atteso per caso con 14 test.
4. Trading: nessuna cella con rendimento netto medio sopra zero in modo significativo. Con 0,30% per lato il risultato e' negativo in modo significativo su tutte le configurazioni crypto orarie. Le celle positive hanno campioni troppo piccoli (SPY giornaliero solo long: +67 bp su 19 trade, intervallo [-68; +191]).
5. Gara stop/target: AUC fra 0,46 e 0,55, Brier peggiore del bootstrap ingenuo ovunque. Su BTC 24h il target arriva nel 33% dei casi sia quando il modello dice 1% sia quando dice 65%.
6. Volatilita': la larghezza della banda ordina l'ampiezza del movimento (IC +0,11 su BTC 24h), ma la volatilita' storica del contesto fa uguale o meglio in 4 configurazioni su 7.
7. Distorsione sui giornalieri: previsione media sotto il realizzato di 2,4 punti (BTC, 7 giorni) e 2,8 punti (SPY, 5 giorni). Esempio: BTC a 95.644 il 2024-11-28, previsione media a 7 giorni 63.580, realizzato +1,4%. Il predittore ufficiale da' gli stessi valori.

## 6. Incertezza e limiti
- Campioni: 400-704 previsioni non sovrapposte sugli orari, 117-121 finestre sui giornalieri (hit rate +/- 9 punti).
- Potenza: su BTC 24h si esclude un hit rate sopra il 55,4% e un IC sopra 0,08. Un IC di 0,02-0,05 non e' escluso ma starebbe sotto i costi.
- Test multipli: 7 configurazioni, ciascuna con 2 IC, un hit rate e 8-12 celle di trading; nessun risultato positivo e' significativo, nemmeno senza correzione.
- BTC ed ETH sono correlati: non sono sette conferme indipendenti.
- Ambito: solo Kronos-small, zero-shot, 50 percorsi, top_p 0,9 e 1,0, contesti 128 e 256. Non sono stati provati Kronos-base ne' il fine-tuning.
- Esecuzione alla chiusura della barra senza latenza: ipotesi favorevole al modello.

## 7. Verdetto
1. Vantaggio dopo i costi: nessuna evidenza.
2. Calibrazione: no; un bootstrap ingenuo e' calibrato e gratuito.
3. Gara stop/target: probabilita' senza contenuto informativo.
4. Pipeline con denaro reale: no.
5. Condizione per riaprire: una versione diversa che, in un test in avanti dichiarato prima su almeno 500 previsioni non sovrapposte per asset, mostri insieme IC con estremo inferiore sopra zero, rendimento netto per trade con estremo inferiore sopra zero a 0,07% per lato, copertura p10-p90 fra 75% e 85%, e risultati migliori di momentum e volatilita' storica; poi 3 mesi di paper trading.

## 8. Riproduzione
git clone --depth 1 https://github.com/shiyu-coder/Kronos /tmp/kronos_eval/kronos_src
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install einops huggingface_hub safetensors tqdm numpy pandas scipy pyarrow
python research/v5/kronos_eval.py --selftest
python research/v5/kronos_eval.py --suite --only spy_1d_c256_h5,btc_1h_c256_h24 --threads 1 --max-minutes 20
python research/v5/kronos_eval.py --suite --only spy_1h_c256_h7,eth_1h_c256_h24 --threads 1 --max-minutes 20
python research/v5/kronos_eval.py --suite --only btc_1h_c128_h48 --threads 1 --max-minutes 20
python research/v5/kronos_eval.py --suite --only btc_1d_c256_h7,btc_1h_c256_h24_topp1 --threads 1 --max-minutes 20
python research/v5/kronos_eval.py --suite --analyze-only
I percorsi campionati sono in /tmp/kronos_eval/out (fuori dal repository).
