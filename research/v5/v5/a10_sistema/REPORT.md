# A10 — Revisione dell'intero sistema

**Tutto SIMULATO.** Versione condensata del rapporto dell'analista; i numeri vengono dai file `.out` di questa cartella. Valori: tutto | scelta | verifica.

| # | Correzione | Effetto | Fiducia |
|---|---|---|---|
| 1 | **Il motore di rischio non è nei profili pubblicati.** Con le soglie di `config/gerva.yaml` (−10%, −15%, −20%) il profilo C3 passa il 62% dei giorni a un quarto dell'esposizione | C3: CAGR 49,3% → 25,1% (verifica 45,8 → 11,7); Sharpe mensile 1,11 → 1,00 (verifica 0,93 → 0,46); caduta −32% → −19% | Alta |
| 2 | **Tasse italiane**, liquidazione annua (33% crypto, 26% derivati ed ETF) | C3 49,6% → 35,3% netto; C1 26,9 → 19,6; libro a 1x 13,6 → 9,6 | Alta sull'aritmetica |
| 3 | **Finanziamento calcolato su tutto il capitale invece che sul debito vero** (a 1x il 47% è cassa) | Libro a 2x: CAGR 23,0% → 27,7%; C3 49,3% → 55,0% | Medio-alta |
| 4 | **Libro dei trade valutato ogni giorno** e non al giorno di uscita | C3: Sharpe mensile 1,17 → 1,09; Monte Carlo a 3 anni: caduta mediana −20% → −30%, 5° percentile −37% → −46%, P(−30%) 2,9% → 6,5% | Alta |
| 5 | Cassa ferma in un ETF monetario | Libro a 1x: CAGR +0,93 punti; Sharpe 1,36 → 1,49 | Alta |
| 6 | **Commissione minima su un conto piccolo:** a 12.000 $ un ordine medio di MA-TREND vale 235 $, cioè 62 pb per lato e non 10 | Portafoglio 13,6% → 11,9%; ribilanciare ogni mese o sospendere sotto 100.000 $ | Alta |
| 7 | EQ-MR su micro futures | Sharpe del portafoglio 1,36 → 1,44, solo da circa 200.000 $ | Media |
| 8 | Crypto spot a 10 pb invece di 30 | 13,6% → 13,9% | Media |
| 9–11 | Volatilità obiettivo, allocazioni alternative, sostituire CR-TREND con il libro dei trade | Nessun guadagno | Alta |

**Profilo massimo corretto** (righe 3 e 4, limiti del libro rispettati): CAGR 55,0% lordo (56,0 | 53,7), 40,6% dopo le tasse, cioè 2,9% al mese composto; mese mediano 1,1%; caduta giornaliera −31%. Con il motore di rischio configurato oggi: circa 25% lordo.

**Altri difetti trovati**
- I profili C4 e C6 violano i limiti del libro (rischio per trade 3% contro un tetto del 2%; rischio aperto 9% contro 6%).
- Solana è stata scelta con il senno di poi: con soli BTC ed ETH il libro dei trade ha Sharpe 0,70 | 0,91 | 0,45 invece di 0,78 | 0,93 | 0,68.
- Il libro dei trade da solo non si distingue da CR-TREND portato alla stessa volatilità; il suo merito dimostrato è la perdita limitata.
- `gerva/live/tradecycle.py` non addebita il funding (0,04 R per trade), calcola la conviction senza il segnale di funding, e il comando `trades` non passa la scala del motore di rischio.
- Il ciclo paper usa 4 strategie; i profili della dashboard 6.
- Il Deflated Sharpe 0,38 riguarda il libro a 1x, non il fondo con i trade.
- Nessun look-ahead trovato in `risk_parity`, `vol_target_leverage`, `book()`.

**Rispetto al 30% al mese:** nessuna di queste correzioni cambia N o R̄/σ_R (N·(R̄/σ_R)² = 1,42 contro 6,3). Spostano la base: +0,9 punti (cassa), +4,7 (finanziamento a 2x), −14 (tasse), −24 (motore di rischio com'è configurato).

189 varianti provate, nessuna proposta come strategia nuova.
