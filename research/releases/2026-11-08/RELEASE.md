# GERVA-Q v3.1 + v3.2 — correzioni dell'audit (R1, R2, R5, R9) e quota di lungo periodo

Rilascio proposto per la finestra di domenica 8 novembre 2026 (REGOLE_SFIDA regola 7). Nessuna di queste
modifiche è stata decisa guardando i risultati della sfida: vengono dall'audit del codice
(`docs/research/gervaq_audit.md`).

## Cosa cambia

| ID | File | Modifica | Effetto sui segnali di oggi |
|---|---|---|---|
| R1 | `v3_validate.py` | Il DSR usa gli Sharpe delle prove vere (`challenge/trials_export.csv`, esportato da GERVA Capital) invece di `np.linspace(0.3, 1.55, 55)`. Le prove senza Sharpe si riempiono ripetendo ciclicamente quelli osservati (riempire con la media ridurrebbe la varianza e renderebbe il DSR ottimista). Senza export il DSR è dichiarato "non verificabile". | Nessuno: tocca solo la validazione. |
| R2 | `engine.py` | Chiave di cache SHA-256 stabile invece di `hash()` di Python, che cambia a ogni processo. | Nessuno: studi ripetibili sugli stessi dati scaricati. |
| R5 | `crypto_live.py` | In modalità live l'approvazione deve contenere l'hash degli ordini del giro (`approvals/crypto_AAAA-MM-GG.ok`), come già fa `live.py`; prima bastava un file statico per sempre. | Nessuno in paper. Chiude un varco per i soldi veri. |
| R9 | `lab.py` | In S1 le righe senza un anno di covarianza sono azzerate (prima restavano pesi non scalati). | Nessuno dal 2006 in poi (il backtest parte dal 2006, i dati dal 2004). |

## v3.2: quota di lungo periodo (decisione di Andrea del 5/11/2026) — QUESTA CAMBIA GLI ORDINI

| File | Modifica |
|---|---|
| `config.py` | `LONGTERM`: 5% del NAV su 19 titoli a pesi uguali. Nucleo 3%: NVDA, AVGO, AMD, TSM, ASML, MSFT, GOOGL, AMZN, META. Esplorativo 2%: COHR, GLW, CIEN, CRDO, ALAB, MU, VRT, BE, GEV, NBIS. Il calendario apre 3 rate mensili dal 9/11/2026 (il massimo acquistabile). `LONGTERM_MAX_NAME` = 3% del NAV per titolo. |
| `live.py` | Compra SOLO cio' che approva il **comitato di GERVA Capital** (`var/longterm_plan.json`, oppure `GERVAQ_LT_PLAN`): piano fresco (al massimo 7 giorni), solo i titoli di `config.py`, mai oltre il calendario, mai una riduzione. Senza piano: nessun acquisto nuovo. Le azioni sono un numero fisso in `state/longterm.json`; il ribilanciamento annuale compra solo i titoli rimasti indietro e non vende i vincitori, salvo un titolo oltre il 3% del NAV. La quota si ricava dalla parte azionaria (niente leva). |

Effetto: dal 9/11 circa 16.400 EUR al mese di acquisti per tre mesi (su un conto da 984.000 EUR), il resto del motore azionario un po' più piccolo. Rischio misurato (dal 2022) sulla quota a regime: caduta peggiore −43% (circa −21.300 EUR, circa −2,2% del conto). Ricerca: `research/lungo/`, `research/aziende/`.

## Test

- Le modifiche compilano (`py_compile`) e le due patch si applicano in sequenza, con l'applicatore rigoroso di GERVA Capital, su una copia dello snapshot del 3/11/2026 (test `tests/test_release.py`).
- v3.2 provata con prezzi finti: senza piano o con piano vecchio non compra; titolo sconosciuto ignorato; richiesta oltre il calendario tagliata; rata rinviata e recuperata alla successiva; piano che azzera non vende; un titolo quadruplicato resta al ribilanciamento, uno dimezzato torna al peso; oltre il 3% del NAV si riduce al tetto; le azioni della quota si sommano a quelle del motore in `build_orders`.
- Va eseguito sul Mac dopo l'applicazione: `python v3_validate.py` (con e senza `trials_export.csv`) e `python live.py` / `python crypto_live.py` in dry run.

## Come si applica

`python firm.py release --apply 2026-11-08` dalla cartella di GERVA Capital, di domenica (UTC 8–20), dopo che Andrea ha scelto «Applicare» nella Posta del Capo. Prima di applicare viene salvato un backup dei file in `GERVA-Q/backups/pre-2026-11-08/`; la voce del changelog di REGOLE_SFIDA.md si scrive da sola.
