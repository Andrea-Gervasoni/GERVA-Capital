# Ricerca v5: risultati

Generato da `python -m gerva.research.run` il 2026-11-11 01:34 UTC. Dati fino al 2026-11-09 (azioni) e al 2026-10-31 (crypto).

**Tutti i numeri sono SIMULATI su dati storici**, al netto dei costi indicati in ogni tabella. Nessuno e' un risultato reale.
«scelta» = fino al 31/12/2022; «verifica» = dal 1/1/2023, mai usato per scegliere. Sharpe in eccesso del tasso a breve.
cagr = rendimento annuo composto; vol = volatilita' annua; max_dd = caduta massima; mesi_ge_20 = quota di mesi con almeno +20%.

Impronte dei dati: {"gex": "3be6071d6c441ac9", "yahoo_1d_SPY": "ec1da48b15632486", "bn_spot_1d_BTCUSDT": "d289ebb71908e785", "spx_m1": "aacd42ee2f20ab3d"}

## 0. Riferimenti (nessuna strategia)

| strategia | anni | cagr | vol | sharpe | max_dd | mese_medio | mese_peggiore | mesi_ge_20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY comprato e tenuto | 33.74 | 10.7% | 18.5% | 0.51 | -55.2% | 0.9% | -16.5% | 0.0% |
| QQQ comprato e tenuto | 27.62 | 10.5% | 26.9% | 0.43 | -83.0% | 1.1% | -26.2% | 0.3% |
| TLT comprato e tenuto | 24.24 | 3.5% | 14.2% | 0.19 | -48.4% | 0.4% | -13.1% | 0.0% |
| GLD comprato e tenuto | 21.93 | 10.3% | 18.3% | 0.53 | -45.6% | 0.9% | -16.1% | 0.0% |
| 60% SPY / 40% IEF | 24.24 | 8.6% | 10.8% | 0.66 | -31.4% | 0.7% | -9.8% | 0.0% |

## 1. Trend following su 17 ETF (costo 10 punti base per lato)

| strategia | anni | cagr | vol | sharpe | max_dd | mese_medio | mese_peggiore | mesi_ge_20 | turnover | lorda |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| trend giornaliero long/short, vol 10% | 21.82 | -3.7% | 10.6% | -0.47 | -58.9% | -0.3% | -8.0% | 0.0% | 110.50 | 1.95 |
| trend giornaliero long/short, vol 10% · scelta | 17.98 | -1.7% | 10.7% | -0.22 | -38.2% | -0.1% | -7.0% | 0.0% | nan | nan |
| trend giornaliero long/short, vol 10% · verifica | 3.84 | -12.7% | 10.5% | -1.67 | -40.3% | -1.1% | -8.0% | 0.0% | nan | nan |
| trend lento long/short settimanale, vol 10% | 21.82 | 3.8% | 10.9% | 0.23 | -24.1% | 0.3% | -7.2% | 0.0% | 28.80 | 2.04 |
| trend lento long/short settimanale, vol 10% · scelta | 17.98 | 5.7% | 10.9% | 0.45 | -17.0% | 0.5% | -6.3% | 0.0% | nan | nan |
| trend lento long/short settimanale, vol 10% · verifica | 3.84 | -4.5% | 11.0% | -0.77 | -20.2% | -0.3% | -7.2% | 0.0% | nan | nan |
| trend lento solo long settimanale, vol 10% | 21.82 | 5.5% | 10.9% | 0.39 | -18.7% | 0.5% | -7.9% | 0.0% | 21.60 | 1.72 |
| trend lento solo long settimanale, vol 10% · scelta | 17.98 | 6.9% | 10.9% | 0.56 | -17.8% | 0.6% | -7.9% | 0.0% | nan | nan |
| trend lento solo long settimanale, vol 10% · verifica | 3.84 | -0.7% | 10.8% | -0.43 | -15.0% | -0.0% | -7.1% | 0.0% | nan | nan |
| trend lento solo long mensile, vol 10% | 21.82 | 5.4% | 11.7% | 0.36 | -28.7% | 0.5% | -11.7% | 0.0% | 9.03 | 1.70 |
| trend lento solo long mensile, vol 10% · scelta | 17.98 | 5.8% | 11.7% | 0.44 | -28.7% | 0.5% | -11.7% | 0.0% | nan | nan |
| trend lento solo long mensile, vol 10% · verifica | 3.84 | 3.4% | 11.6% | -0.04 | -16.6% | 0.3% | -5.3% | 0.0% | nan | nan |
| MA-TREND: trend lento solo long settimanale, senza leva | 21.82 | 4.9% | 7.1% | 0.46 | -14.9% | 0.4% | -4.5% | 0.0% | 10.93 | 0.98 |
| MA-TREND: trend lento solo long settimanale, senza leva · scelta | 17.98 | 5.4% | 7.2% | 0.59 | -10.9% | 0.5% | -4.5% | 0.0% | nan | nan |
| MA-TREND: trend lento solo long settimanale, senza leva · verifica | 3.84 | 2.9% | 6.5% | -0.22 | -9.5% | 0.2% | -4.4% | 0.0% | nan | nan |

Il trend giornaliero ha un turnover di oltre 100 volte l'anno: con i costi di un conto piccolo perde. Rallentare il segnale e ribilanciare ogni settimana salva la strategia, ma lo Sharpe netto resta tra 0,2 e 0,4.

## 2. Azioni: ritorno alla media, regimi, leva a regime (5 punti base per lato)

| strategia | anni | cagr | vol | sharpe | max_dd | mese_medio | mese_peggiore | mesi_ge_20 | in_posizione |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| IBS SPY (eseguito in chiusura) | 26.80 | 6.8% | 12.7% | 0.43 | -22.0% | 0.6% | -12.3% | 0.3% | 0.32 |
| IBS SPY (eseguito in chiusura) · scelta | 22.96 | 7.1% | 13.0% | 0.48 | -22.0% | 0.6% | -12.3% | 0.4% | nan |
| IBS SPY (eseguito in chiusura) · verifica | 3.84 | 4.7% | 10.4% | 0.06 | -12.1% | 0.4% | -3.1% | 0.0% | nan |
| IBS SPY (eseguito il giorno dopo) | 26.80 | 2.9% | 12.7% | 0.14 | -30.7% | 0.3% | -14.3% | 0.0% | nan |
| IBS QQQ (eseguito in chiusura) | 26.80 | 11.4% | 18.4% | 0.57 | -38.4% | 1.0% | -16.5% | 0.3% | 0.27 |
| IBS QQQ (eseguito in chiusura) · scelta | 22.96 | 11.5% | 19.1% | 0.59 | -38.4% | 1.0% | -16.5% | 0.4% | nan |
| IBS QQQ (eseguito in chiusura) · verifica | 3.84 | 10.7% | 13.6% | 0.49 | -11.2% | 0.9% | -3.9% | 0.0% | nan |
| IBS QQQ (eseguito il giorno dopo) | 26.80 | 4.8% | 18.6% | 0.24 | -44.2% | 0.5% | -17.2% | 0.0% | nan |
| EQ-MR: IBS su SPY e QQQ, meta' ciascuno | 26.80 | 9.3% | 14.5% | 0.55 | -23.8% | 0.8% | -11.6% | 0.3% | nan |
| EQ-MR: IBS su SPY e QQQ, meta' ciascuno · scelta | 22.96 | 9.6% | 14.9% | 0.59 | -23.8% | 0.8% | -11.6% | 0.4% | nan |
| EQ-MR: IBS su SPY e QQQ, meta' ciascuno · verifica | 3.84 | 7.8% | 11.5% | 0.32 | -11.6% | 0.6% | -2.5% | 0.0% | nan |
| media a 200 giorni, 1x SPY | 32.95 | 9.2% | 12.2% | 0.58 | -21.6% | 0.8% | -9.5% | 0.0% | nan |
| media a 200 giorni, 1x SPY · scelta | 29.12 | 8.6% | 12.2% | 0.56 | -18.7% | 0.7% | -9.5% | 0.0% | nan |
| media a 200 giorni, 1x SPY · verifica | 3.84 | 14.1% | 12.2% | 0.78 | -9.6% | 1.1% | -5.5% | 0.0% | nan |
| media a 200 giorni, 2x SPY | 32.95 | 13.3% | 24.3% | 0.53 | -41.0% | 1.2% | -18.8% | 0.3% | nan |
| media a 200 giorni, 2x SPY · scelta | 29.12 | 12.3% | 24.3% | 0.51 | -38.0% | 1.2% | -18.8% | 0.3% | nan |
| media a 200 giorni, 2x SPY · verifica | 3.84 | 20.8% | 24.3% | 0.72 | -20.0% | 1.7% | -11.2% | 0.0% | nan |
| media a 200 giorni, 2x QQQ | 26.83 | 11.1% | 34.3% | 0.42 | -82.8% | 1.3% | -49.7% | 2.2% | nan |
| media a 200 giorni, 2x QQQ · scelta | 23.00 | 8.1% | 34.1% | 0.35 | -82.8% | 1.1% | -49.7% | 1.4% | nan |
| media a 200 giorni, 2x QQQ · verifica | 3.84 | 31.1% | 35.4% | 0.82 | -28.6% | 2.7% | -13.8% | 6.4% | nan |
| SPY a volatilita' gestita 15% | 32.81 | 9.8% | 16.3% | 0.51 | -45.4% | 0.9% | -12.6% | 0.0% | nan |
| SPY a volatilita' gestita 15% · scelta | 28.98 | 9.0% | 16.2% | 0.48 | -45.4% | 0.8% | -12.6% | 0.0% | nan |
| SPY a volatilita' gestita 15% · verifica | 3.84 | 16.3% | 16.7% | 0.72 | -17.9% | 1.3% | -6.7% | 0.0% | nan |
| dual momentum mensile (SPY, EFA, IEF) | 20.82 | 7.9% | 15.9% | 0.45 | -33.7% | 0.7% | -12.5% | 0.0% | nan |
| dual momentum mensile (SPY, EFA, IEF) · scelta | 16.98 | 6.5% | 16.0% | 0.41 | -33.7% | 0.6% | -12.5% | 0.0% | nan |
| dual momentum mensile (SPY, EFA, IEF) · verifica | 3.84 | 14.4% | 15.3% | 0.66 | -18.8% | 1.2% | -7.8% | 0.0% | nan |

IBS vive solo se si esegue SULLA chiusura che genera il segnale: con un giorno di ritardo perde meta' dello Sharpe.

## 3. Vendere volatilita' (SVXY)

| strategia | anni | cagr | vol | sharpe | max_dd | mese_medio | mese_peggiore | mesi_ge_20 | giorno_peggiore |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SVXY comprato e tenuto | 15.06 | 12.1% | 54.8% | 0.53 | -95.2% | 2.6% | -89.6% | 7.7% | -83.0% |
| SVXY solo con VIX/VIX3M < 0,95, peso 100% | 15.06 | 16.3% | 40.4% | 0.54 | -45.5% | 2.0% | -33.2% | 6.0% | -26.5% |
| SVXY solo con VIX/VIX3M < 0,95, peso 100% · scelta | 11.23 | 19.5% | 44.4% | 0.62 | -45.5% | 2.3% | -33.2% | 8.1% | -26.5% |
| SVXY solo con VIX/VIX3M < 0,95, peso 100% · verifica | 3.84 | 7.4% | 25.3% | 0.23 | -29.0% | 0.8% | -15.5% | 0.0% | -15.5% |
| SVXY solo con VIX/VIX3M < 0,95, peso 50% | 15.06 | 10.9% | 20.2% | 0.53 | -24.7% | 1.0% | -16.8% | 0.0% | -13.2% |
| SVXY solo con VIX/VIX3M < 0,95, peso 50% · scelta | 11.23 | 12.4% | 22.2% | 0.61 | -24.7% | 1.2% | -16.8% | 0.0% | -13.2% |
| SVXY solo con VIX/VIX3M < 0,95, peso 50% · verifica | 3.84 | 6.6% | 12.6% | 0.21 | -13.8% | 0.6% | -7.7% | 0.0% | -7.7% |

Il 5/2/2018 SVXY ha perso l'83% in un giorno. Il filtro lo ha evitato solo perche' il rapporto era 0,98 il venerdi' prima: con una soglia a 1,00 lo avrebbe preso in pieno. Scartata: rischio di coda non controllabile, e SVXY non e' acquistabile da un cliente al dettaglio UE (manca il KID).

## 4a. Che cosa predice il GEX (S&P 500, dati SqueezeMetrics)

| quintile del GEX (rango a 252 giorni) | giorni | rendimento medio del giorno dopo (pb) | t | volatilita' annua del giorno dopo | giorno peggiore |
|---|---:|---:|---:|---:|---:|
| Q1 (GEX basso) | 688 | 12.6 | 1.90 | 27.6% | -12.0% |
| Q2 | 631 | 9.9 | 2.34 | 16.8% | -4.0% |
| Q3 | 695 | 3.9 | 1.12 | 14.4% | -4.4% |
| Q4 | 707 | -1.7 | -0.57 | 12.5% | -3.6% |
| Q5 (GEX alto) | 1058 | 3.3 | 1.72 | 9.9% | -5.9% |

Giorni: 3779 (2011-10-27 -> 2026-11-06); giorni con GEX negativo: 320 (8.5%). Correlazione di rango GEX vs |rendimento del giorno dopo|: -0.33 (p = 7e-94); vs rendimento con segno: -0.056 (p = 0.0005). R² della regressione di |rendimento| sul solo VIX: 0.292; aggiungendo il GEX: 0.301.

## 4b. Regole di esposizione basate sul GEX, su SPY

| strategia | anni | cagr | vol | sharpe | max_dd | mese_medio | mese_peggiore | mesi_ge_20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY comprato e tenuto (stesso periodo) | 14.99 | 14.7% | 16.6% | 0.81 | -33.7% | 1.2% | -12.5% | 0.0% |
| SPY comprato e tenuto (stesso periodo) · scelta | 11.15 | 12.6% | 17.2% | 0.74 | -33.7% | 1.1% | -12.5% | 0.0% |
| SPY comprato e tenuto (stesso periodo) · verifica | 3.84 | 20.8% | 15.1% | 1.03 | -18.8% | 1.6% | -5.6% | 0.0% |
| regola diffusa: 1,5x se GEX nel 75% alto, cassa altrimenti | 14.99 | 9.6% | 17.0% | 0.53 | -32.3% | 0.9% | -13.6% | 0.0% |
| regola diffusa: 1,5x se GEX nel 75% alto, cassa altrimenti · scelta | 11.15 | 5.8% | 17.2% | 0.37 | -32.3% | 0.6% | -13.6% | 0.0% |
| regola diffusa: 1,5x se GEX nel 75% alto, cassa altrimenti · verifica | 3.84 | 21.5% | 16.7% | 0.98 | -16.1% | 1.7% | -8.2% | 0.0% |
| regola diffusa: long solo con GEX positivo | 14.99 | 11.9% | 13.2% | 0.79 | -22.4% | 1.0% | -9.7% | 0.0% |
| regola diffusa: long solo con GEX positivo · scelta | 11.15 | 10.2% | 13.2% | 0.75 | -22.4% | 0.9% | -9.7% | 0.0% |
| regola diffusa: long solo con GEX positivo · verifica | 3.84 | 17.2% | 13.3% | 0.93 | -19.6% | 1.4% | -7.3% | 0.0% |
| contraria: 1,5x con GEX nel 25% basso, 1x altrimenti | 14.99 | 15.9% | 21.5% | 0.72 | -47.0% | 1.3% | -19.1% | 0.0% |
| contraria: 1,5x con GEX nel 25% basso, 1x altrimenti · scelta | 11.15 | 14.2% | 22.4% | 0.67 | -47.0% | 1.2% | -19.1% | 0.0% |
| contraria: 1,5x con GEX nel 25% basso, 1x altrimenti · verifica | 3.84 | 21.0% | 18.9% | 0.87 | -26.2% | 1.6% | -8.2% | 0.0% |
| volatilita' obiettivo 12% con la volatilita' realizzata | 14.99 | 10.4% | 13.0% | 0.70 | -18.0% | 0.9% | -10.4% | 0.0% |
| volatilita' obiettivo 12% con la volatilita' realizzata · scelta | 11.15 | 9.6% | 12.9% | 0.72 | -18.0% | 0.8% | -10.4% | 0.0% |
| volatilita' obiettivo 12% con la volatilita' realizzata · verifica | 3.84 | 12.8% | 13.1% | 0.64 | -13.9% | 1.0% | -5.1% | 0.0% |
| volatilita' obiettivo 12% con il VIX | 14.99 | 10.7% | 11.6% | 0.79 | -17.7% | 0.9% | -7.1% | 0.0% |
| volatilita' obiettivo 12% con il VIX · scelta | 11.15 | 9.2% | 11.6% | 0.76 | -17.7% | 0.8% | -7.1% | 0.0% |
| volatilita' obiettivo 12% con il VIX · verifica | 3.84 | 15.0% | 11.6% | 0.88 | -13.2% | 1.2% | -5.0% | 0.0% |

Nessuna regola GEX batte lo Sharpe del semplice comprare e tenere. Il GEX e' un previsore di volatilita' equivalente al VIX, non un segnale di direzione.

## 5a. Intraday sull'indice: zona di rumore e ultima mezz'ora

| strategia | anni | cagr | vol | sharpe | max_dd | operazioni_giorno | lordo_pb_giorno | costo_pb_giorno |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S&P 500 2010-18: fuori dalla zona di rumore, stop sulla banda, costo 0.0 pb | 8.02 | 2.8% | 5.8% | 0.50 | -7.5% | 1.84 | 1.16 | 0.00 |
| S&P 500 2010-18: fuori dalla zona di rumore, stop sulla banda, costo 0.3 pb | 8.02 | 1.4% | 5.8% | 0.26 | -10.8% | 1.84 | 1.16 | 0.55 |
| S&P 500 2010-18: fuori dalla zona di rumore, stop sulla banda, costo 0.5 pb | 8.02 | 0.4% | 5.8% | 0.10 | -14.0% | 1.84 | 1.16 | 0.92 |
| S&P 500 2010-18: fuori dalla zona di rumore, stop sulla banda, costo 1.0 pb | 8.02 | -1.9% | 5.9% | -0.30 | -24.9% | 1.84 | 1.16 | 1.85 |
| S&P 500 2010-18: fuori dalla zona di rumore, stop sulla banda, costo 2.0 pb | 8.02 | -6.4% | 5.9% | -1.08 | -44.3% | 1.84 | 1.16 | 3.69 |
| S&P 500 2010-18: idem con leva a volatilita' (max 4x), costo 0,5 pb | 8.02 | 1.7% | 14.6% | 0.19 | -34.9% | 1.84 | 3.73 | 2.66 |
| S&P 500 2011-18: momentum dell'ultima mezz'ora, tutti i giorni, costo 0.5 pb | 7.06 | 1.4% | 3.1% | 0.45 | -6.9% | 1.98 | 1.55 | 0.99 |
| S&P 500 2011-18: momentum dell'ultima mezz'ora, tutti i giorni, costo 1.0 pb | 7.06 | -1.1% | 3.1% | -0.36 | -17.4% | 1.98 | 1.55 | 1.98 |
| S&P 500 2011-18: momentum dell'ultima mezz'ora, solo se il GEX di ieri era nel 20% basso, costo 0.5 pb | 7.06 | 3.2% | 2.3% | 1.38 | -2.7% | 0.38 | 1.45 | 0.19 |
| S&P 500 2011-18: momentum dell'ultima mezz'ora, solo se il GEX di ieri era nel 20% basso, costo 1.0 pb | 7.06 | 2.7% | 2.3% | 1.18 | -2.8% | 0.38 | 1.45 | 0.38 |
| SPY orario 2023-26 (verifica): zona di rumore, costo 0,5 pb | 2.89 | -2.4% | 5.4% | -0.41 | -11.1% | 1.17 | -0.30 | 0.59 |
| QQQ orario 2023-26 (verifica): zona di rumore, costo 0,5 pb | 2.89 | 5.4% | 8.6% | 0.65 | -7.2% | 1.09 | 2.78 | 0.55 |
| IWM orario 2023-26 (verifica): zona di rumore, costo 0,5 pb | 2.89 | -6.9% | 7.1% | -0.97 | -22.3% | 1.13 | -2.16 | 0.57 |

pb = punti base (0,01%). La regola della zona di rumore guadagna 1,2 pb lordi al giorno: basta un costo di 0,6 pb per lato per azzerarla. L'ultima mezz'ora condizionata al GEX aveva Sharpe 1,4 nel 2011-2018.

## 5b. La stessa regola dell'ultima mezz'ora nel periodo di verifica

| ultima mezz'ora, 2023-12 -> 2026-11 (lordo, senza costi) | giorni | rendimento medio (pb) | t |
|---|---:|---:|---:|
| SPY, tutti i giorni | 721 | -2.04 | -2.54 |
| SPY, GEX di ieri nel 20% basso | 122 | -2.90 | -1.02 |
| QQQ, tutti i giorni | 721 | -2.10 | -2.09 |
| QQQ, GEX di ieri nel 20% basso | 122 | -4.71 | -1.31 |
| IWM, tutti i giorni | 721 | -2.48 | -2.72 |
| IWM, GEX di ieri nel 20% basso | 122 | -6.61 | -2.43 |

Nel 2023-2026 l'effetto ha cambiato segno su tutti e tre gli indici: un backtest brillante su 7 anni non ha superato la prova dei 3 anni successivi.

## 5c. VWAP trend (long sopra il VWAP di seduta, short sotto)

| strategia | anni | cagr | vol | sharpe | max_dd | operazioni_giorno | lordo_pb_giorno | costo_pb_giorno |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| VWAP trend a 1 minuto, 24 azioni Nasdaq 2022-24, costo 0 pb | 2.04 | -19.5% | 11.2% | -1.89 | -36.0% | 17.41 | -8.38 | 0.00 |
| VWAP trend a 1 minuto, 24 azioni Nasdaq 2022-24, costo 1 pb | 2.04 | -64.9% | 12.1% | -8.60 | -88.2% | 17.41 | -8.38 | 32.82 |
| VWAP trend a 1 minuto, 24 azioni Nasdaq 2022-24, costo 2 pb | 2.04 | -84.8% | 13.0% | -14.33 | -97.8% | 17.41 | -8.38 | 65.65 |
| BTC a 5 minuti 2017-26, VWAP trend, costo 0 pb | 9.21 | -58.9% | 75.6% | -0.79 | -100.0% | 20.41 | -16.32 | 0.00 |
| BTC a 5 minuti 2017-26, VWAP trend, costo 7 pb | 9.21 | -100.0% | 92.6% | -11.35 | -100.0% | 20.41 | -16.32 | 271.76 |
| BTC a 5 minuti 2017-26, VWAP trend con fascia 0,5%, costo 7 pb | 9.21 | -78.8% | 67.4% | -1.96 | -100.0% | 3.66 | 1.35 | 37.55 |
| BTC a 5 minuti 2017-26, VWAP trend con fascia 0,5%, costo 30 pb | 9.21 | -99.8% | 79.4% | -7.34 | -100.0% | 3.66 | 1.35 | 160.93 |
| ETH a 5 minuti 2017-26, VWAP trend, costo 0 pb | 9.21 | 15.9% | 96.5% | 0.66 | -100.0% | 19.60 | 17.46 | 0.00 |
| ETH a 5 minuti 2017-26, VWAP trend, costo 7 pb | 9.21 | -100.0% | 113.3% | -7.83 | -100.0% | 19.60 | 17.46 | 260.36 |
| ETH a 5 minuti 2017-26, VWAP trend con fascia 0,5%, costo 7 pb | 9.21 | -65.1% | 88.1% | -0.75 | -100.0% | 4.28 | 27.92 | 46.03 |
| ETH a 5 minuti 2017-26, VWAP trend con fascia 0,5%, costo 30 pb | 9.21 | -99.9% | 102.2% | -6.05 | -100.0% | 4.28 | 27.92 | 197.29 |
| SOL a 5 minuti 2017-26, VWAP trend, costo 0 pb | 6.23 | 137.5% | 107.0% | 1.34 | -71.2% | 19.21 | 39.16 | 0.00 |
| SOL a 5 minuti 2017-26, VWAP trend, costo 7 pb | 6.23 | -100.0% | 122.5% | -6.43 | -100.0% | 19.21 | 39.16 | 255.01 |
| SOL a 5 minuti 2017-26, VWAP trend con fascia 0,5%, costo 7 pb | 6.23 | -87.6% | 109.7% | -1.35 | -100.0% | 5.47 | 21.93 | 62.53 |
| SOL a 5 minuti 2017-26, VWAP trend con fascia 0,5%, costo 30 pb | 6.23 | -100.0% | 125.9% | -7.13 | -100.0% | 5.47 | 21.93 | 267.98 |

17-20 cambi di posizione al giorno: e' lo stesso ordine di grandezza dei 15 al giorno del paper di Zarattini e Aziz, che pero' assume 0,0005 dollari per azione e nessuno slippage. Con qualunque costo realistico la regola distrugge il conto.

## 6. Crypto giornaliero, solo long, spot (commissione + slippage per lato indicati)

| strategia | anni | cagr | vol | sharpe | max_dd | mese_medio | mese_peggiore | mesi_ge_20 | turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BTC comprato e tenuto | 8.84 | 21.7% | 64.0% | 0.59 | -81.2% | 3.4% | -37.3% | 18.9% | nan |
| ETH comprato e tenuto | 8.84 | 13.5% | 84.3% | 0.55 | -94.0% | 4.3% | -53.8% | 21.7% | nan |
| trend BTC+ETH veloce (10-80 giorni), settimanale, 10 pb | 8.84 | 25.9% | 21.0% | 1.08 | -24.1% | 2.2% | -8.6% | 3.8% | 7.76 |
| trend BTC+ETH veloce (10-80 giorni), settimanale, 10 pb · scelta | 5.01 | 33.0% | 21.3% | 1.38 | -24.1% | 2.6% | -6.5% | 4.9% | nan |
| trend BTC+ETH veloce (10-80 giorni), settimanale, 10 pb · verifica | 3.84 | 17.1% | 20.5% | 0.65 | -21.9% | 1.6% | -8.6% | 2.2% | nan |
| trend BTC+ETH veloce (10-80 giorni), settimanale, 30 pb | 8.84 | 24.0% | 21.0% | 1.00 | -24.8% | 2.0% | -8.9% | 3.8% | 7.76 |
| trend BTC+ETH veloce (10-80 giorni), settimanale, 30 pb · scelta | 5.01 | 31.5% | 21.4% | 1.33 | -24.8% | 2.5% | -6.7% | 4.9% | nan |
| trend BTC+ETH veloce (10-80 giorni), settimanale, 30 pb · verifica | 3.84 | 14.7% | 20.5% | 0.55 | -22.9% | 1.4% | -8.9% | 2.2% | nan |
| trend BTC+ETH lento (30-120 giorni), settimanale, 10 pb | 8.84 | 26.6% | 22.6% | 1.04 | -24.0% | 2.2% | -11.9% | 4.7% | 5.27 |
| trend BTC+ETH lento (30-120 giorni), settimanale, 10 pb · scelta | 5.01 | 34.8% | 22.8% | 1.37 | -22.6% | 2.7% | -11.9% | 4.9% | nan |
| trend BTC+ETH lento (30-120 giorni), settimanale, 10 pb · verifica | 3.84 | 16.7% | 22.3% | 0.60 | -24.0% | 1.5% | -8.6% | 4.3% | nan |
| trend BTC+ETH lento (30-120 giorni), settimanale, 30 pb | 8.84 | 25.3% | 22.6% | 0.99 | -25.2% | 2.1% | -11.9% | 4.7% | 5.27 |
| trend BTC+ETH lento (30-120 giorni), settimanale, 30 pb · scelta | 5.01 | 33.7% | 22.8% | 1.33 | -22.8% | 2.7% | -11.9% | 4.9% | nan |
| trend BTC+ETH lento (30-120 giorni), settimanale, 30 pb · verifica | 3.84 | 15.1% | 22.3% | 0.54 | -25.2% | 1.4% | -8.9% | 4.3% | nan |
| momentum trasversale, 5 su 20, 10 pb | 8.84 | 45.0% | 84.0% | 0.83 | -81.5% | 6.4% | -47.3% | 22.6% | 28.62 |
| momentum trasversale, 5 su 20, 10 pb · scelta | 5.01 | 52.2% | 90.0% | 0.91 | -81.5% | 6.8% | -47.3% | 23.0% | nan |
| momentum trasversale, 5 su 20, 10 pb · verifica | 3.84 | 36.1% | 75.3% | 0.72 | -76.2% | 5.7% | -31.1% | 21.7% | nan |
| momentum trasversale, 5 su 20, 30 pb | 8.84 | 36.9% | 84.0% | 0.77 | -82.6% | 5.9% | -47.5% | 22.6% | 28.62 |
| momentum trasversale, 5 su 20, 30 pb · scelta | 5.01 | 43.9% | 90.0% | 0.85 | -82.6% | 6.3% | -47.5% | 23.0% | nan |
| momentum trasversale, 5 su 20, 30 pb · verifica | 3.84 | 28.2% | 75.3% | 0.64 | -78.5% | 5.2% | -31.3% | 21.7% | nan |
| momentum trasversale, 5 su 20, solo con BTC sopra la media a 100 giorni, 10 pb | 8.84 | 69.4% | 68.9% | 1.08 | -74.0% | 6.8% | -51.6% | 18.9% | 19.82 |
| momentum trasversale, 5 su 20, solo con BTC sopra la media a 100 giorni, 10 pb · scelta | 5.01 | 84.4% | 68.3% | 1.23 | -74.0% | 7.4% | -51.6% | 19.7% | nan |
| momentum trasversale, 5 su 20, solo con BTC sopra la media a 100 giorni, 10 pb · verifica | 3.84 | 51.6% | 69.6% | 0.88 | -54.0% | 5.8% | -31.1% | 17.4% | nan |
| momentum trasversale, 5 su 20, solo con BTC sopra la media a 100 giorni, 30 pb | 8.84 | 62.8% | 68.9% | 1.02 | -74.6% | 6.4% | -51.7% | 18.9% | 19.82 |
| momentum trasversale, 5 su 20, solo con BTC sopra la media a 100 giorni, 30 pb · scelta | 5.01 | 78.2% | 68.3% | 1.18 | -74.6% | 7.1% | -51.7% | 19.7% | nan |
| momentum trasversale, 5 su 20, solo con BTC sopra la media a 100 giorni, 30 pb · verifica | 3.84 | 44.6% | 69.7% | 0.81 | -54.8% | 5.4% | -31.3% | 17.4% | nan |
| CR-XSMOM: momentum 5 su 20 con filtro, 30 pb, ridotto a volatilita' 25% (mai sopra 1x) | 8.84 | 32.1% | 27.9% | 1.04 | -27.7% | 2.7% | -16.4% | 4.7% | nan |
| CR-XSMOM: momentum 5 su 20 con filtro, 30 pb, ridotto a volatilita' 25% (mai sopra 1x) · scelta | 5.01 | 26.9% | 25.4% | 1.02 | -27.7% | 2.2% | -16.4% | 1.6% | nan |
| CR-XSMOM: momentum 5 su 20 con filtro, 30 pb, ridotto a volatilita' 25% (mai sopra 1x) · verifica | 3.84 | 39.2% | 30.9% | 1.08 | -26.9% | 3.3% | -12.8% | 8.7% | nan |

Universo: 60 monete scelte tra le maggiori di ogni anno, comprese quelle poi fallite (LUNA, FTT, EOS); a ogni ribilanciamento si guardano solo le 20 piu' scambiate IN QUEL MOMENTO. Resta una distorsione di sopravvivenza: le monete mai quotate su Binance non ci sono.

## 7. Carry sui perpetual: long spot, short perpetual (10 pb per lato e per gamba)

| strategia | anni | cagr | vol | sharpe | max_dd | mese_medio | mese_peggiore | mesi_ge_20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| carry su 10 monete, sempre dentro | 6.84 | 6.9% | 1.6% | 2.40 | -4.5% | 0.6% | -3.6% | 0.0% |
| carry su 10 monete, sempre dentro · scelta | 3.01 | 10.7% | 2.3% | 4.08 | -4.3% | 0.8% | -3.6% | 0.0% |
| carry su 10 monete, sempre dentro · verifica | 3.83 | 3.9% | 0.4% | -1.46 | -0.3% | 0.3% | -0.2% | 0.0% |
| carry su 10 monete, solo con funding > 5% annuo | 6.84 | 5.8% | 1.1% | 2.59 | -3.7% | 0.5% | -0.5% | 0.0% |
| carry su 10 monete, solo con funding > 5% annuo · scelta | 3.01 | 11.8% | 1.5% | 7.09 | -1.6% | 0.9% | -0.3% | 0.0% |
| carry su 10 monete, solo con funding > 5% annuo · verifica | 3.83 | 1.3% | 0.5% | -6.89 | -3.7% | 0.1% | -0.5% | 0.0% |

Lo Sharpe qui e' in eccesso del tasso a breve. Il rischio vero non e' nei dati giornalieri: fallimento o blocco dell'exchange, auto-deleveraging dello short, liquidazione della gamba short in un rialzo violento.

## 7b. Funding incassato dallo short in un anno, % (somma semplice, Binance USDT-M)

| anno | BTC | ETH | SOL | BNB | XRP | DOGE | ADA | LTC | LINK | AVAX |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2019 | -0.0 | 0.0 | — | — | — | — | — | — | — | — |
| 2020 | 17.3 | 27.5 | -3.9 | 2.3 | 24.3 | 4.5 | 25.0 | 25.0 | 11.0 | -3.5 |
| 2021 | 30.6 | 37.5 | 28.8 | 21.7 | 48.1 | 38.5 | 39.9 | 40.1 | 43.0 | 31.0 |
| 2022 | 4.2 | 0.8 | -38.1 | -12.6 | 0.0 | 3.4 | -1.0 | 2.9 | 5.9 | -5.2 |
| 2023 | 7.9 | 8.3 | 1.4 | -8.5 | 8.2 | 10.0 | 7.2 | 9.3 | 10.2 | 7.5 |
| 2024 | 11.9 | 13.0 | 13.6 | -3.2 | 14.2 | 14.0 | 14.0 | 14.4 | 13.4 | 10.5 |
| 2025 | 5.1 | 4.9 | 0.4 | -2.1 | 3.5 | 4.3 | 4.1 | 5.5 | 5.1 | 0.1 |
| 2026 | 2.6 | 1.7 | -0.5 | 2.3 | 0.2 | 2.7 | 1.3 | 2.7 | 3.9 | 1.1 |

Il premio era del 30-40% nel 2021 ed e' sceso al 2-5% nel 2025-2026: oggi rende meno di un titolo di Stato a breve.

## 8a. Le quattro strategie scelte (rendimenti sul capitale assegnato a ciascuna)

| strategia | anni | cagr | vol | sharpe | max_dd | mese_medio | mese_peggiore | mesi_ge_20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CR-TREND | 8.84 | 25.3% | 22.6% | 0.99 | -25.2% | 2.1% | -11.9% | 4.7% |
| CR-TREND · scelta | 5.01 | 33.7% | 22.8% | 1.33 | -22.8% | 2.7% | -11.9% | 4.9% |
| CR-TREND · verifica | 3.84 | 15.1% | 22.3% | 0.54 | -25.2% | 1.4% | -8.9% | 4.3% |
| CR-XSMOM | 8.84 | 32.1% | 27.9% | 1.04 | -27.7% | 2.7% | -16.4% | 4.7% |
| CR-XSMOM · scelta | 5.01 | 26.9% | 25.4% | 1.02 | -27.7% | 2.2% | -16.4% | 1.6% |
| CR-XSMOM · verifica | 3.84 | 39.2% | 30.9% | 1.08 | -26.9% | 3.3% | -12.8% | 8.7% |
| EQ-MR | 8.84 | 12.1% | 13.2% | 0.73 | -17.0% | 1.0% | -8.7% | 0.9% |
| EQ-MR · scelta | 5.01 | 15.5% | 14.5% | 0.97 | -17.0% | 1.3% | -8.7% | 1.6% |
| EQ-MR · verifica | 3.84 | 7.8% | 11.1% | 0.33 | -11.6% | 0.6% | -2.5% | 0.0% |
| MA-TREND | 8.84 | 3.6% | 7.0% | 0.16 | -14.9% | 0.3% | -4.4% | 0.0% |
| MA-TREND · scelta | 5.01 | 3.6% | 7.4% | 0.35 | -9.7% | 0.3% | -4.4% | 0.0% |
| MA-TREND · verifica | 3.84 | 3.6% | 6.4% | -0.12 | -9.5% | 0.3% | -4.4% | 0.0% |

## 8b. Correlazione dei rendimenti mensili

| | CR-TREND | CR-XSMOM | EQ-MR | MA-TREND |
|---|---:|---:|---:|---:|
| CR-TREND | 1.00 | 0.55 | -0.08 | 0.32 |
| CR-XSMOM | 0.55 | 1.00 | -0.06 | 0.25 |
| EQ-MR | -0.08 | -0.06 | 1.00 | -0.08 |
| MA-TREND | 0.32 | 0.25 | -0.08 | 1.00 |

Pesi medi (parita' di rischio): CR-TREND 17%, CR-XSMOM 12%, EQ-MR 27%, MA-TREND 44%.

## 8c. Portafoglio e leva (costo della leva: tasso a breve + 1,5% sulla parte presa a prestito)

| strategia | anni | cagr | vol | sharpe | max_dd | mese_medio | mese_peggiore | mesi_ge_20 | mesi_le_m20 | leva_media |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PORTAFOGLIO senza leva | 8.59 | 13.8% | 9.0% | 1.18 | -9.4% | 1.1% | -3.1% | 0.0% | 0.0% | nan |
| PORTAFOGLIO senza leva · scelta | 4.76 | 14.3% | 8.4% | 1.49 | -9.4% | 1.1% | -3.1% | 0.0% | 0.0% | nan |
| PORTAFOGLIO senza leva · verifica | 3.84 | 13.0% | 9.6% | 0.86 | -8.0% | 1.1% | -2.3% | 0.0% | 0.0% | nan |
| volatilita' obiettivo 10%, leva massima 1.5x | 8.43 | 14.0% | 10.2% | 1.07 | -10.6% | 1.1% | -3.8% | 0.0% | 0.0% | 1.21 |
| volatilita' obiettivo 10%, leva massima 1.5x · scelta | 4.59 | 14.8% | 9.6% | 1.36 | -9.7% | 1.2% | -3.8% | 0.0% | 0.0% | nan |
| volatilita' obiettivo 10%, leva massima 1.5x · verifica | 3.84 | 13.0% | 10.9% | 0.77 | -10.6% | 1.1% | -3.3% | 0.0% | 0.0% | nan |
| volatilita' obiettivo 15%, leva massima 2x | 8.43 | 18.8% | 14.6% | 1.07 | -15.1% | 1.5% | -5.1% | 1.0% | 0.0% | 1.71 |
| volatilita' obiettivo 15%, leva massima 2x · scelta | 4.59 | 21.3% | 13.8% | 1.38 | -13.6% | 1.6% | -5.1% | 0.0% | 0.0% | nan |
| volatilita' obiettivo 15%, leva massima 2x · verifica | 3.84 | 16.0% | 15.6% | 0.74 | -15.1% | 1.3% | -4.7% | 2.2% | 0.0% | nan |
| volatilita' obiettivo 20%, leva massima 3x | 8.43 | 23.4% | 20.4% | 1.00 | -21.8% | 1.9% | -7.8% | 2.0% | 0.0% | 2.42 |
| volatilita' obiettivo 20%, leva massima 3x · scelta | 4.59 | 27.2% | 19.2% | 1.28 | -20.3% | 2.1% | -7.8% | 1.8% | 0.0% | nan |
| volatilita' obiettivo 20%, leva massima 3x · verifica | 3.84 | 19.1% | 21.8% | 0.70 | -21.8% | 1.7% | -6.9% | 2.2% | 0.0% | nan |
| volatilita' obiettivo 30%, leva massima 6x | 8.43 | 31.2% | 33.1% | 0.90 | -36.7% | 2.7% | -13.6% | 4.9% | 0.0% | 4.01 |
| volatilita' obiettivo 30%, leva massima 6x · scelta | 4.59 | 37.5% | 31.3% | 1.14 | -36.7% | 3.0% | -13.6% | 5.3% | 0.0% | nan |
| volatilita' obiettivo 30%, leva massima 6x · verifica | 3.84 | 24.0% | 35.2% | 0.66 | -36.7% | 2.4% | -13.4% | 4.3% | 0.0% | nan |
| volatilita' obiettivo 40%, leva massima 8x | 8.43 | 38.3% | 44.2% | 0.89 | -48.5% | 3.5% | -17.9% | 6.9% | 0.0% | 5.35 |
| volatilita' obiettivo 40%, leva massima 8x · scelta | 4.59 | 48.3% | 41.7% | 1.12 | -46.4% | 3.9% | -17.9% | 7.0% | 0.0% | nan |
| volatilita' obiettivo 40%, leva massima 8x · verifica | 3.84 | 27.1% | 46.9% | 0.65 | -48.5% | 3.0% | -17.9% | 6.5% | 0.0% | nan |
| volatilita' obiettivo 60%, leva massima 12x | 8.43 | 48.0% | 66.3% | 0.88 | -67.6% | 5.2% | -26.6% | 14.7% | 6.9% | 8.03 |
| volatilita' obiettivo 60%, leva massima 12x · scelta | 4.59 | 66.5% | 62.6% | 1.11 | -62.0% | 5.8% | -26.2% | 15.8% | 5.3% | nan |
| volatilita' obiettivo 60%, leva massima 12x · verifica | 3.84 | 28.3% | 70.4% | 0.64 | -67.6% | 4.3% | -26.6% | 13.0% | 8.7% | nan |

## 8d. Quanto puo' essere fortuna

- Configurazioni provate: **104** (59 riprodotte da questo programma + 45 esplorative provate a mano e scartate); varianza dello Sharpe di una strategia SENZA abilita' su 4.8 anni: 0.21 (quella empirica delle prove, 1.43, e' gonfiata dalle regole distrutte dai costi e non si usa).
- Sharpe che ci si aspetta dal MIGLIORE di 104 tentativi senza alcuna abilita': **1.17**.
- Sharpe del portafoglio: 1.18 su tutto il periodo, 1.49 nel periodo di scelta, **0.86 nel periodo di verifica**.
- Probabilita' che lo Sharpe vero sia sopra zero (PSR): 1.000 su tutto il periodo, 0.959 sul solo periodo di verifica.
- Deflated Sharpe (probabilita' che lo Sharpe vero superi quello del migliore a caso): **0.52**. La soglia del progetto e' 0,95: il portafoglio NON la supera. Il test e' severo (il portafoglio e' una combinazione, non la migliore delle prove), ma il verdetto onesto e': evidenza promettente, non conclusiva. Decide il paper trading.
- Errore standard dello Sharpe con 8.6 anni di dati: ±0.34.

## 9a. Monte Carlo a 3 anni: il portafoglio a leva costante (4.000 percorsi, blocchi di 30 giorni)

| leva | CAGR 5° pct | CAGR mediano | CAGR 95° pct | caduta massima mediana | caduta massima 5° pct | P(perdita a 3 anni) | P(capitale dimezzato) | mese medio | P(mese ≥ +20%) | P(mese ≤ −20%) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1x | 5% | 14% | 23% | -8% | -12% | 0.2% | 0.0% | 1.1% | 0.0% | 0.0% |
| 1.5x | 5% | 18% | 33% | -13% | -19% | 1.1% | 0.0% | 1.4% | 0.1% | 0.0% |
| 2x | 4% | 22% | 43% | -17% | -26% | 2.1% | 0.0% | 1.7% | 0.6% | 0.0% |
| 3x | 2% | 29% | 64% | -25% | -39% | 3.5% | 0.1% | 2.4% | 2.5% | 0.1% |
| 4x | -0% | 36% | 87% | -33% | -51% | 5.2% | 1.3% | 3.1% | 6.5% | 0.4% |
| 6x | -7% | 47% | 136% | -47% | -69% | 8.7% | 9.0% | 4.4% | 14.4% | 2.5% |
| 8x | -16% | 55% | 187% | -59% | -81% | 12.3% | 21.8% | 5.7% | 19.9% | 6.3% |
| 10x | -26% | 57% | 238% | -70% | -89% | 16.7% | 34.6% | 7.0% | 23.9% | 11.0% |
| 12x | -38% | 55% | 286% | -78% | -94% | 21.8% | 47.2% | 8.2% | 26.6% | 15.3% |
| 15x | -54% | 43% | 344% | -87% | -98% | 30.8% | 61.7% | 10.1% | 29.3% | 22.0% |

Leva di Kelly empirica (massimizza la crescita logaritmica NEL campione): **10.25x**, crescita log 46% l'anno. E' un tetto teorico gonfiato dall'errore di stima: oltre quel punto piu' leva fa crescere MENO.

## 9b. Lo stesso, se il rendimento in eccesso vero fosse la META' di quello del backtest

| leva | CAGR 5° pct | CAGR mediano | CAGR 95° pct | caduta massima mediana | caduta massima 5° pct | P(perdita a 3 anni) | P(capitale dimezzato) | mese medio | P(mese ≥ +20%) | P(mese ≤ −20%) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1x | 0% | 8% | 18% | -9% | -16% | 4.9% | 0.0% | 0.7% | 0.0% | 0.0% |
| 1.5x | -3% | 9% | 24% | -15% | -26% | 10.6% | 0.0% | 0.8% | 0.1% | 0.0% |
| 2x | -6% | 10% | 30% | -21% | -36% | 15.2% | 0.0% | 0.9% | 0.5% | 0.0% |
| 3x | -12% | 12% | 42% | -32% | -52% | 22.4% | 2.4% | 1.2% | 1.9% | 0.1% |
| 4x | -18% | 12% | 54% | -42% | -64% | 27.2% | 9.6% | 1.4% | 5.1% | 0.7% |
| 6x | -30% | 11% | 77% | -58% | -81% | 36.7% | 31.4% | 1.9% | 11.8% | 3.8% |
| 8x | -43% | 5% | 96% | -71% | -91% | 44.0% | 50.2% | 2.4% | 16.7% | 9.0% |
| 10x | -54% | -3% | 109% | -81% | -96% | 52.1% | 65.2% | 2.8% | 19.8% | 14.9% |
| 12x | -65% | -13% | 117% | -88% | -98% | 59.9% | 75.7% | 3.2% | 22.3% | 20.9% |
| 15x | -78% | -31% | 116% | -95% | -100% | 70.9% | 86.1% | 3.8% | 24.6% | 28.4% |

E' il caso realistico: dopo la pubblicazione le anomalie perdono in media il 58% del rendimento (McLean e Pontiff 2016), e qui il periodo di verifica ha reso il 58% di quello di scelta in termini di Sharpe.

## 9c. Lo stesso, con uno scenario che il campione non contiene

| leva | CAGR 5° pct | CAGR mediano | CAGR 95° pct | caduta massima mediana | caduta massima 5° pct | P(perdita a 3 anni) | P(capitale dimezzato) | mese medio | P(mese ≥ +20%) | P(mese ≤ −20%) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1x | -6% | 8% | 20% | -17% | -34% | 17.8% | 0.1% | 0.6% | 0.0% | 0.0% |
| 1.5x | -12% | 8% | 28% | -27% | -50% | 25.7% | 2.5% | 0.7% | 0.1% | 2.2% |
| 2x | -18% | 8% | 35% | -35% | -63% | 31.2% | 8.9% | 0.8% | 0.6% | 2.9% |
| 3x | -33% | 6% | 51% | -52% | -82% | 40.3% | 27.6% | 1.0% | 2.4% | 3.0% |
| 4x | -49% | 1% | 67% | -67% | -94% | 48.6% | 45.9% | 1.2% | 6.3% | 3.4% |
| 6x | -88% | -30% | 97% | -93% | -100% | 65.8% | 67.0% | 1.6% | 14.0% | 5.4% |
| 8x | -100% | -100% | 129% | nan% | nan% | 70.4% | 73.7% | 1.9% | 19.3% | 9.1% |
| 10x | -100% | -100% | 157% | nan% | nan% | 71.7% | 77.7% | 2.2% | 23.2% | 13.6% |
| 12x | -100% | -100% | 179% | nan% | nan% | 73.4% | 81.7% | 2.5% | 25.8% | 17.8% |
| 15x | -100% | -100% | 196% | nan% | nan% | 76.8% | 87.2% | 2.8% | 28.5% | 24.2% |

Scenario: ogni giorno, con probabilita' 0,1% (una volta ogni 2,7 anni circa), il portafoglio senza leva perde un 15% in piu' (exchange che blocca i prelievi, gap notturno, correlazioni che vanno a 1).
