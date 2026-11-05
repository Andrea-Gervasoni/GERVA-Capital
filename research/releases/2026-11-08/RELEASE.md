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
| `config.py` | `LONGTERM`: 5% del NAV su 19 titoli a pesi uguali. Nucleo 3%: NVDA, AVGO, AMD, TSM, ASML, MSFT, GOOGL, AMZN, META. Esplorativo 2%: COHR, GLW, CIEN, CRDO, ALAB, MU, VRT, BE, GEV, NBIS. Partenza lunedì 9/11/2026, 3 rate mensili. |
| `live.py` | La quota si ricava dalla parte azionaria (i pesi del motore scalano da 50% a 50% − 5% × rate entrate: niente leva). Le azioni della quota sono un NUMERO FISSO salvato in `state/longterm.json`, ricalcolato solo a una nuova rata (mai sotto quelle già tenute) o una volta l'anno: tra un ribilanciamento e l'altro `live.py` non vende i titoli saliti. Se un titolo è anche nel reversal S4, le azioni si sommano. |

Effetto: dal 9/11 circa 16.400 EUR al mese di acquisti per tre mesi (su un conto da 984.000 EUR), il resto del motore azionario un po' più piccolo. Rischio misurato (dal 2022) sulla quota a regime: caduta peggiore −43% (circa −21.300 EUR, circa −2,2% del conto). Ricerca: `research/lungo/`, `research/aziende/`.

## Test

- Le modifiche compilano (`py_compile`) e le due patch si applicano in sequenza, con l'applicatore rigoroso di GERVA Capital, su una copia dello snapshot del 3/11/2026 (test `tests/test_release.py`).
- v3.2 provata con prezzi finti: frazione 0 prima del 9/11, poi 1/3, 2/3, 3/3; azioni fisse tra le rate; un titolo triplicato non viene venduto; le azioni della quota si sommano a quelle del motore in `build_orders`.
- Va eseguito sul Mac dopo l'applicazione: `python v3_validate.py` (con e senza `trials_export.csv`) e `python live.py` / `python crypto_live.py` in dry run.

## Come si applica

`python firm.py release --apply 2026-11-08` dalla cartella di GERVA Capital, di domenica (UTC 8–20), dopo che Andrea ha scelto «Applicare» nella Posta del Capo. Prima di applicare viene salvato un backup dei file in `GERVA-Q/backups/pre-2026-11-08/`; la voce del changelog di REGOLE_SFIDA.md si scrive da sola.
