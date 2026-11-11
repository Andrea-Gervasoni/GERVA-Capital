# A1 — Un indicatore d'ingresso originale (GQ) contro la conviction attuale

**Tutto SIMULATO** su dati storici reali. Versione condensata del rapporto dell'analista; i numeri vengono dai file `.out` di questa cartella.

## Indicatore congelato (`indicatore.py`, `congelato.json`)

    GQ(t) = [ TQ_moneta/0,20 + TQ_BTC/0,20 + VWM_moneta/0,40 ] / 3      calcolato alla chiusura di t, usato da t+1
    TQ  = media degli efficiency ratio con segno a 10, 30, 60, 120 giorni
    VWM = (chiusura / VWAP ancorato all'apertura del mese − 1) / ATR%14, limitato a ±3, diviso 3
    soglie (quantili della scelta): eccezionale ≥ 1,42 · alta ≥ 0,53 · bassa ≤ −0,50

## Risultati

| Libro (BTC, ETH, SOL) | Trade/anno | R medio (t) | Scelta | Verifica (t) | Verifica, costi ×2 | Verifica, +1 barra |
|---|---:|---:|---:|---:|---:|---:|
| 11x · conviction alta (attuale) | 77 | +0,237 (3,5) | +0,309 | +0,180 (2,0) | +0,141 | +0,166 |
| 11x · GQ alta | 72 | +0,339 (4,5) | +0,415 | +0,276 (2,7) | +0,239 | +0,259 |
| 30x · conviction alta | 129 | +0,364 (2,8) | +0,553 | +0,196 (1,3) | +0,096 | +0,147 |
| 30x · GQ alta | 126 | +0,355 (2,6) | +0,427 | +0,285 (1,7) | +0,185 | +0,280 |

- GQ **non batte** il livello eccezionale della conviction (verifica, trade-sonda a 11x: +0,18 contro +0,23 R).
- Come soglia d'ingresso "alta" a 11x migliora di +0,10 R: probabilità 0,96 che sia positivo sul periodo intero, 0,83 in verifica. Sui trade-sonda il vantaggio è +0,03 / +0,05 R; a 30x è nullo.
- GQ e conviction hanno correlazione 0,85: è la stessa informazione di regime, misurata in modo continuo.
- Su 18 altre monete nessuno dei due indicatori ordina i trade in verifica.
- In verifica la conviction stessa separa poco: eccezionale meno bassa = +0,12 R, intervallo da −0,28 a +0,50. Entrambi i libri rendono circa zero nel 2025–2026.

## Effetto sul fondo

N·(R̄/σ_R)² da 1,42 a 2,43 sul periodo intero (verifica da 1,05 a 1,96); stima prudente 1,4–2,0. Obiettivo: 6,3.

## Prove e dubbi

79 varianti contate. GQ era il migliore di 15 composti quasi identici, e il criterio di scelta è stato formulato dopo aver visto le tabelle della scelta (non la verifica). Libro e trade-sonda danno vantaggi diversi. Prezzi spot al posto dei perpetual.
