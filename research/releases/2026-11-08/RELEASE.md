# GERVA-Q v3.1 — correzioni dell'audit (R1, R2, R5, R9)

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

## Test

- Le quattro modifiche compilano (`py_compile`) e la patch si applica a secco su una copia dello snapshot del 3/11/2026 (`patch -p1 --dry-run`).
- Va eseguito sul Mac dopo l'applicazione: `python v3_validate.py` (con e senza `trials_export.csv`) e `python live.py` / `python crypto_live.py` in dry run.

## Come si applica

`python firm.py release --apply 2026-11-08` dalla cartella di GERVA Capital, di domenica (UTC 8–20), dopo che Andrea ha scelto «Applicare» nella Posta del Capo. Prima di applicare viene salvato un backup dei file in `GERVA-Q/backups/pre-2026-11-08/`; la voce del changelog di REGOLE_SFIDA.md si scrive da sola.
