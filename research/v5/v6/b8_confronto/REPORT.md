# B8 — Confronto: GERVA Capital originale contro il nuovo fondo `gerva/`

**Tutto SIMULATO** su dati storici reali, salvo dove è scritto FATTO, STIMA o IPOTESI. Niente ha operato.
File: `00_dati.py`, `01_legacy.py` (.out), `02_potenza.py` (.out), `confronto.py` (+ `confronto_selfcheck.out`), `returns.parquet`, `legacy_nav.csv`.

## 1. Che cosa scambia il sistema originale (ricostruito dal solo repository)

| Pezzo | Regola | Dove sta nel repository | Riproducibile? |
|---|---|---|---|
| Libro azionario, 50% del conto (`EQUITY_SHARE`) | 4 sleeve a pesi uguali: S1 trend EWMA (8/32…64/256) long/flat su 15 ETF, vol 10% per asset, tetto 25%; S2 SPY a vol 16% sopra la media a 200 giorni; S3 i 3 settori migliori per momentum 12-1, mensile, resto in IEF; S4 reversal RSI(2) < 10 su 90 large cap USA, 6 posizioni, 5 giorni | `quantlab/strategies.py`, `quantlab/gervaq4.py` (`v3_riferimento`) | **Sì** |
| Sleeve crypto, 50% del conto (`CRYPTO_SHARE`) | H1 trend 10/20/40/80 giorni su 10 monete, vol 60%, tetto 35%; H2 Donchian su BTC/ETH/SOL; 50/50; long/flat | `quantlab/crypto4.py` (`v3_crypto`) | **Sì, approssimata**: H2 nella v3 è a 4 ore (55/20 candele), qui 9/3 giorni |
| Leva (v3.3, 6/11) | scala = min(2,5 ; 1,5 / esposizione): il conto viene portato fino al 150% lordo | `deploy/mac/prepara_v33.py`, `firm/rules.py`, `config/risk_limits.yaml` (max 2x, KILL −35%) | **Sì** |
| Leva per volatilità (v3.7) | moltiplicatore 0,6–1,4, spento di default (`volmgmt.enabled`) | `firm/desk.py`, `firm/fundrisk.py` | non incluso (spento) |
| Desk di trading (v3.3, v3.6) | i capi desk LLM propongono azioni (≤ 5% l'una, ≤ 30% del conto) e crypto (≤ 3% / 10%), sopra il modello | `firm/desk.py`, `var/firm_overlay.json` | **No**: decisioni di un modello linguistico, nessuno storico |
| Lungo periodo | 5% in 19 titoli dell'infrastruttura AI, comprare e tenere | `config/longterm.yaml` | escluso: titoli scelti oggi sapendo che hanno vinto |
| Banco libero, segnali Telegram, pod | conto paper Alpaca separato, non il conto IBKR | `firm/free_desk.py`, `firm/signals.py` | **No** (discrezionale) |

**Che cosa manca per una replica esatta (FATTO):** il codice di GERVA-Q (`lab.py`, `config.py`, `live.py`, `crypto_lab.py`, `crypto_live.py`) è fuori dal repository (`_incoming/` escluso da git); mancano quindi i parametri originali (la riespressione dà CAGR 5,7% contro il 7,1% del README della v3, lo dice STATUS.md), il breakout a 4 ore, lo storico delle proposte dei desk e i file di stato (`state/nav_log.csv`). `var/firm.sqlite` qui ha `nav_marks` e `nav_ticks` vuote.

**Controllo della ricostruzione (FATTO):** con il motore e i costi di `quantlab` il libro azionario dà Sharpe 0,69, CAGR 5,7%, vol 8,6%, caduta −15,9% sul periodo di scelta del banco: **identico alle quattro cifre di STATUS.md**. Troncamento su 3 date: scarto dei pesi 0. Quel 0,69 è però uno Sharpe grezzo, solo metà del conto, 2005–2024, eseguito sulla chiusura del segnale.

## 2. Testa a testa con le stesse convenzioni

Motore `gerva.backtest.daily.run`, costi di `book.py` (ETF e azioni 10 pb, crypto 30 pb per lato), debito a tasso + 1,5%, cassa a tasso − 0,5%, Sharpe in eccesso del tasso, giorni di calendario. Periodo comune **1/4/2018 → 31/10/2026**. Valori: tutto | scelta (≤ 2022) | verifica (≥ 2023).

| Serie | Sharpe | CAGR | Vol | Caduta max (verifica) | Mese peggiore |
|---|---|---|---|---|---|
| **Originale, modello senza leva** (50/50) | 1,14 \| 1,20 \| 1,06 | 20,3% \| 20,3% \| 20,3% | 14,7% | −17,7% (−10,9%) | −9,2% |
| **Originale come gira oggi** (fino al 150%) | 0,97 \| 1,04 \| 0,88 | 33,4% \| 35,9% \| 30,4% | 32,3% | −36,5% (−25,9%) | −20,6% |
| di cui libro azionario | 0,46 \| 0,36 \| 0,58 | 6,6% | 9,1% | −15,1% | −7,2% |
| di cui sleeve crypto | 1,10 \| 1,19 \| 0,98 | 33,2% | 26,8% | −25,4% | −15,3% |
| Nuovo: libro 1x (`B_cassa_in_tbill`) | 1,49 \| 1,63 \| 1,29 | 14,7% \| 14,8% \| 14,5% | 7,6% | −8,8% (−5,6%) | −3,4% |
| **Nuovo: libro 2x** (`B2_debito_reale`) | 1,51 \| 1,64 \| 1,33 | 27,7% \| 29,6% \| 25,4% | 15,2% | −17,9% (−12,0%) | −6,9% |
| Nuovo: C1 (libro + trade) | 1,28 \| 1,54 \| 1,06 | 26,8% \| 26,7% \| 26,9% | 17,6% | −16,5% (−16,5%) | −8,6% |
| Nuovo: C1 con il motore di rischio attuale | 1,07 \| 1,44 \| 0,71 | 18,7% \| 21,3% \| 15,6% | 14,4% | −13,4% | −8,6% |
| **Nuovo: C3** (`C3_mtm_limiti_debito_reale`) | 1,36 \| 1,57 \| 1,17 | 55,0% \| 56,0% \| 53,7% | 34,7% | −31,0% (−31,0%) | −16,7% |
| CR-TREND / CR-XSMOM / EQ-MR / MA-TREND | 1,02 / 1,05 / 0,83 / 0,17 | 26% / 33% / 13% / 4% | 23 / 28 / 13 / 7% | −25 / −28 / −12 / −15% | −12 / −16 / −9 / −4% |
| SPY · BTC (compra e tieni) | 0,68 · 0,73 | 14,8% · 32,5% | 18,9% · 61,7% | −33,7% · −76,6% | −12,5% · −37,3% |

Per anno (%):

| | 2018* | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|---|---|---|
| Originale senza leva | −6,9 | 21,0 | 33,2 | 74,7 | −8,3 | 36,0 | 34,6 | 2,1 | 8,6 |
| Originale 150% | −18,8 | 37,3 | 69,2 | 195,1 | −22,7 | 65,7 | 59,6 | −4,0 | 9,1 |
| Nuovo libro 1x | −5,4 | 20,5 | 26,8 | 32,5 | 0,6 | 22,6 | 17,1 | 11,0 | 5,7 |
| Nuovo libro 2x | −11,9 | 41,6 | 58,2 | 74,6 | −0,4 | 42,7 | 30,3 | 18,2 | 8,5 |
| Nuovo C3 | −17,5 | 107,9 | 130,6 | 126,3 | −7,3 | 136,0 | 54,5 | 19,0 | 19,8 |
| SPY | −3,6 | 31,2 | 18,3 | 28,7 | −18,2 | 26,2 | 24,9 | 17,7 | 11,7 |

**A pari volatilità** (nuovo fondo riscalato, debito pagato):

| Coppia | Sharpe | CAGR | Caduta |
|---|---|---|---|
| Libro nuovo ×1,94 contro originale senza leva (14,7%) | 1,39 contro 1,14 (verifica 1,19 contro 1,06) | 24,7% contro 20,3% | −18,3% contro −17,7% |
| C1 ×0,84 contro originale senza leva | 1,28 contro 1,14 (verifica 1,06 contro 1,06) | 22,7% contro 20,3% | −13,8% contro −17,7% |
| Libro nuovo ×4,25 contro originale 150% (32,3%) | 1,33 contro 0,97 | 50,0% contro 33,4% | −37,9% contro −36,5% |
| C1 ×1,83 contro originale 150% | 1,24 contro 0,97 | 45,7% contro 33,4% | −29,8% contro −36,5% |

Robustezza dell'originale (Sharpe tutto | verifica): costi ×2 0,83 | 0,69 (150%: 0,58 | 0,40); una barra di ritardo 1,02 | 0,80 (150%: 0,89 | 0,72, caduta −52%); entrambi 0,71 | 0,42. Il nuovo portafoglio a 4 strategie con un giorno di ritardo passa da 1,18 a 0,83 (`research/v5/RESULTS.md` 8b-bis): **con il ritardo il vantaggio si chiude**.
Correlazione giornaliera originale–nuovo: 0,66 (libro), 0,77 (C1/C3); mensile 0,78–0,80. Sono in buona parte lo stesso rischio (trend crypto).

**Lettura onesta**
1. Senza leva l'originale rende più del libro nuovo a 1x (20,3% contro 14,7%) perché porta il doppio del rischio. A pari rischio il nuovo è avanti: Sharpe +0,37, CAGR +4–7 punti, stessa caduta.
2. **Quella differenza non è statisticamente dimostrata**: z = 1,3 sul periodo intero, 0,65 in verifica (`02_potenza.out`, 1c). C1 in verifica è pari all'originale (1,06 contro 1,06); C1 con il motore di rischio com'è configurato è sotto (0,71).
3. L'originale come gira oggi (150%) ha avuto una caduta simulata di −36,5%: oltre il proprio KILL al −35%. Con costi doppi lo Sharpe è 0,58.
4. Il backtest dell'originale è lusinghiero: parametri crypto scelti dall'autore sul 2018–2022, 10 monete e 90 azioni scelte tra quelle vive oggi (rilievo R6), costi da conto piccolo applicati a entrambi. Vale anche per il nuovo (Deflated Sharpe 0,38).
5. Nel 2025 l'originale ha fatto +2,1% (−4,0% a leva), il nuovo libro +11,0%.

## 3. Potenza statistica: quanti giorni di paper in parallelo

Test appaiato sulla differenza di Sharpe: anni = (z_α + z_potenza)² · 2(1 − ρ) / Δ². Verificato per simulazione (bootstrap a blocchi: 83% a 6.000 giorni per Δ 0,5; 85% a 1.500 per Δ 1,0).

| Potenza 80% | ρ | Δ Sharpe 0,5 | Δ Sharpe 1,0 |
|---|---|---|---|
| Libro nuovo contro originale, 5% | 0,66 | **6.200 giorni (17 anni)** | **1.550 giorni (4,2 anni)** |
| C1/C3 contro originale, 5% | 0,77 | 4.200–4.300 giorni | 1.040–1.080 giorni |
| Libro nuovo contro originale, soglia z > 1,28 | 0,66 | 4.500 giorni | 1.130 giorni |

Differenza minima rilevabile: 4,1 unità di Sharpe a 90 giorni, 2,9 a 180, 2,1 a un anno. **Novanta giorni di paper non possono dire chi è migliore**: dicono solo se il paper si comporta come il backtest.

**Lo screenshot (FATTO: 1.089.666 €, +2,89% dal 6/11; S&P +2,31%; distacco tutto l'11/11).** Valore di partenza implicito 1.059.059 €; distacco 0,58 punti = 6.143 €.
- Beta apparente (STIMA): 1,00 se il salto dell'11/11 è specifico, 1,25 se è tutto mercato. Il modello riespresso a leva, negli ultimi 12 mesi, ha beta 1,10 su SPY, volatilità 24%, volatilità residua 19,6% l'anno (1,23% al giorno): coerente con il conto.
- Con quella volatilità residua, 0,58 punti in 3 sedute sono z = 0,27: senza alcuna abilità si osserva un distacco così o maggiore il **39%** delle volte (32% se si guarda il solo salto di un giorno; 14–21% anche con un errore di replica di appena 5%).
- Con beta 1,25 e alfa zero il distacco atteso è esattamente 0,58 punti. Per avere z = 2 in cinque giorni servirebbe un alfa del 213% l'anno.
- Il conto è in euro e l'indice in dollari: una parte del distacco può essere cambio (non verificabile da qui).

## 4. Lo strumento per il confronto in avanti: `confronto.py`

`/tmp/gv/bin/python research/v5/v6/b8_confronto/confronto.py`, una volta al giorno. Aggiunge una riga a `confronto_nav.csv` (rilanciarlo non duplica) con:
- nuovo fondo: `var/gerva/snapshot.json` → `nav.equity`, più `var/gerva/tradebook.json` → `equity`;
- originale: `legacy_nav.csv` (`data,nav_eur,flusso_eur`, aggiornabile a mano; c'è già la riga dell'11/11 dallo screenshot), altrimenti `var/firm.sqlite` tabella `nav_marks` con `pod='pod_zero'` (la scrive `firm/ibkr.py` dal NetLiquidation), altrimenti `$GERVA_Q_PATH/state/nav_log.csv` colonna `nav_eur`;
- SPY ed EURUSD (Yahoo), BTC (Binance).

Stampa, sui soli giorni comuni: cumulato, volatilità, Sharpe, caduta massima, differenza di rendimento, errore di replica, correlazione, beta su SPY e BTC, z grezza e a pari volatilità, giorni ancora necessari, esito secondo i criteri sotto. Versamenti e prelievi sono tolti; l'originale è convertito in dollari se il cambio c'è. `--selfcheck`: 23 controlli su dati sintetici, tutti superati. Non modifica `firm/` né `gerva/`.
Oggi (FATTO): `var/gerva/snapshot.json` e `tradebook.json` non esistono ancora; il confronto parte quando parte il paper.

## 5. Che cosa vuol dire «battere GERVA Capital» (da accettare o respingere)

**Confronto equo.** L'originale gira a leva (volatilità 32% nel backtest, 24% negli ultimi 12 mesi): il profilo di pari rischio è **C3** (34,7%); contro il modello senza leva (14,7%) è il **libro a 2x, B2** (15,2%). Proposta: paper con **B2**, il più solido in verifica (1,33), e giudizio a pari volatilità, che lo strumento calcola da solo.

| Criterio | Soglia | Passa se non c'è alcun vantaggio | Passa se il vantaggio è quello del backtest |
|---|---|---|---|
| 0. Prerequisito | ≥ 90 giorni comuni, stessa ora, flussi tolti | — | — |
| A. Vittoria pratica | rende di più **e** caduta ≤ 1,5× quella dell'originale | 48% a 90 giorni, 50% a un anno | 56% a 90 giorni, 68% a un anno |
| B. Vittoria statistica | z a pari volatilità > 1,3 | 8–12% | 17% a 90 giorni, 19–22% a un anno |
| C. Sconfitta netta | z < −1,3: si torna all'originale | 4–12% | 2–6% |
| D. Sul backtest (già misurato) | Sharpe e CAGR maggiori a pari volatilità, caduta ≤ 1,1× | — | B2: 1,51 contro 1,14, 27,7% contro 20,3%, −17,9% contro −17,7%: **superato**, z 1,3 |

**Il criterio A a 90 giorni è quasi una moneta** (48% contro 56%): accettarlo significa accettare che l'esito dipenda soprattutto dal caso. Proposta: a 90 giorni «non smentito» = A vero e C falso; verdetto «batte» solo con B, rivisto a 180 e 365 giorni; fino ad allora vale D, dichiarato per quello che è.

## 6. Prove e dubbi

- Prove: 9 esecuzioni dell'originale (2 profili × base, costi ×2, ritardo, entrambi; cassa a zero), nessun parametro scelto; 3 regole × 3 scenari × 3 orizzonti. Nessuna strategia nuova.
- Dubbi: (1) la riespressione non è GERVA-Q: senza il suo codice non si può dire di quanto differisce il conto vero, che in più porta le posizioni dei desk; (2) la sleeve crypto dell'originale pesa per quasi tutto il risultato ed è in buona parte dentro il campione; (3) i costi del conto paper da 1 milione sono più bassi di quelli usati qui, quelli di un conto da 12.000 € più alti (commissione minima: A10, riga 6); (4) cambio non modellato; (5) le serie del nuovo fondo sono prese come pubblicate da A10, non ricalcolate qui.
