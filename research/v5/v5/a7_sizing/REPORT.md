# A7 — Dimensionamento e matematica dell'obiettivo

**Tutto SIMULATO.** Versione condensata del rapporto dell'analista; tabelle complete nei file `.out` di questa cartella. Flussi: **A30** (stop 1,7%, 30x, 129 trade l'anno) e **C11** (stop 1×ATR, circa 11x, 77 trade l'anno). Valori: base / metà vantaggio / sola verifica.

## 1. Kelly sui flussi esistenti

| Flusso | Periodo | R̄ | σ_R | N·(R̄/σ)² | Kelly (trade simultanei) | Mese a Kelly pieno | A mezzo Kelly |
|---|---|---:|---:|---:|---:|---:|---:|
| A30 | intero | 0,364 | 4,28 | 0,93 | 2,3% | 4,1% | 3,2% |
| A30 | verifica | 0,196 | 3,61 | 0,45 | 1,5% | 1,8% | 1,4% |
| C11 | intero | 0,237 | 1,74 | 1,42 | 7,8% | 5,6% | 4,2% |
| C11 | verifica | 0,180 | 1,73 | 1,05 | 5,5% | 3,8% | 2,9% |

- Kelly stimato sulla scelta e applicato alla verifica: pieno 0,6% (A30) e 0,9% (C11) al mese; mezzo 1,8% e 3,8%.
- A costi doppi il flusso a 30x perde il vantaggio in verifica (R̄ 0,05).
- Tre monete correlate: il Kelly congiunto è il 20–25% sotto la somma dei Kelly per moneta.

## 2. Che cosa richiede il 30% al mese

Crescita logaritmica annua necessaria: 3,148, cioè N·(R̄/σ)² = 6,3 a Kelly pieno (8,4 a mezzo). Misurato: 0,93 e 1,42 (verifica 0,45 e 1,05). **Manca un fattore 4–7 sull'intero campione, 6–14 in verifica.**

Anche con un vantaggio vero e noto, ogni combinazione che dà almeno il 30% al mese ha una caduta massima mediana di almeno il 70% (96% a Kelly pieno).

| Obiettivo di mese MEDIO (C11) | Rischio per trade | Mese composto mediano | Caduta mediana / 95° | P(−90%) in 3 anni |
|---|---:|---|---|---|
| 10% | 5,2% | 4,8 / 0,9 / 3,7% | 68% / 91% | 2,5 / 12 / 9% |
| 20% | 9,1% | 5,2 / −1,7 / 2,4% | 89% / 99% | 19 / 44 / 37% |
| 30% | 12,2% | 3,8 / −5,4 / −0,7% | 96% / 100% | 37 / 66 / 57% |

## 3. La sala di trading

Su 1.000 trader **senza alcun vantaggio**, rischio 2–5% per trade a 20–30x, un trade al giorno:

| | Su 1.000 |
|---|---:|
| Tre mesi di fila ≥ 30% entro un anno | 56 |
| Sei mesi di fila | 0,3 |
| Dodici su dodici | 0 |
| Azzerati (−90%) entro 12 / 36 mesi | 444 / 839 |

Il 69% di chi ha mostrato tre mesi di fila è azzerato entro 36 mesi. Bastano 12 trader senza vantaggio perché una sala abbia da mostrare un "tre mesi di fila al 30%".

## 4. Massimo mensile sostenuto dai vantaggi misurati

Mediana composta, tre anni:

| P(caduta ≥ 50% in 3 anni) | A30 | C11 a livelli | Fondo intero (limite superiore, STIMA) |
|---|---|---|---|
| ≤ 1% | 1,2 / 0,4 / 0,6% | 1,9 / 0,7 / 1,7% | 3,4 / 1,0 / 2,7% |
| ≤ 5% | 1,7 / 0,5 / 1,0% | 2,4 / 0,9 / 2,1% | 4,4 / 1,3 / 3,4% |
| ≤ 10% | 2,0 / 0,6 / 1,1% | 2,8 / 1,0 / 2,3% | 4,9 / 1,4 / 3,8% |
| ≤ 25% | 2,5 / 0,7 / 1,3% | 3,4 / 1,2 / 3,0% | 5,8 / 1,8 / 4,7% |

10%, 20%, 30% al mese come rendimento composto mediano non sono raggiungibili con nessun flusso a nessun rischio.

## 5. Miglior risultato

Rischio per trade proporzionale alla conviction, con pesi stimati sulla sola scelta. A30: 0,5% × peso (0,19 a score 0,67; 1,23 a 0,75; 2,81 da 0,83). C11: livelli v4 (1% fino a 0,75, 2% sopra). In verifica, sul percorso storico: A30 CAGR 12% → 27% a parità di caduta; C11 16% → 26%.

## 6. Dubbi

Il bootstrap a mesi indipendenti sottostima le serie di mesi cattivi. Lo score ha tre valori soli. Due correzioni alla v4 ne abbassano i numeri: trade dello stesso giorno trattati come simultanei, mesi senza trade inclusi. Dopo 812 varianti provate, lo scenario "metà vantaggio" va letto come centrale, non come pessimistico. 62 regole di dimensionamento provate.
