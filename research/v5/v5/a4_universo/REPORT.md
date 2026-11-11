# A4 — Ampiezza: più monete, long e short

**Tutto SIMULATO** su candele orarie reali dei perpetual USDT-M Binance (archivio pubblico), 2020-01 → 2026-10. Nulla è stato scambiato.
Etichette: **FATTO** = letto dai dati; **STIMA** = dipende da un'ipotesi dichiarata; **IPOTESI** = non misurabile qui.

## 1. Risposta in breve

**L'ampiezza non avvicina il fondo al 30% al mese. Lo allontana.**

- Estendere il libro di trade da BTC/ETH/SOL alle 30 monete più liquide porta i trade da 89 a 720 l'anno, ma i trade
  **effettivamente indipendenti** passano solo da 50 a 85 (×1,7). Nel frattempo R̄ scende da +0,23 a +0,04 (in verifica −0,005).
  La quantità che conta, N_eff·(R̄/σ_R)², scende da **0,93 a 0,05**.
- Un libro neutrale long-forti/short-deboli produce davvero trade indipendenti (N_eff 650–1.100 l'anno, correlazione tra esiti ≈ 0,05),
  ma il margine per trade è zero o negativo (R̄ tra −0,02 e +0,01) e i costi sulle alt valgono 0,05 R per trade.
- Dato scomodo sul libro attuale: anche il trio vale meno di quanto scritto nel brief. I suoi 89 trade l'anno equivalgono a 50 indipendenti
  (correlazione 0,63 tra esiti dello stesso giorno), quindi N_eff·(R̄/σ_R)² = **0,93, non 1,5**. In verifica 0,54.

## 2. Che cosa ho provato

**Universo senza senno di poi (FATTO).** Al primo di ogni mese: tra i perpetual con almeno 200 giorni di storia, i 30 con il volume
mediano a 90 giorni più alto (misurato fino al giorno prima). Esclusi azioni e metalli tokenizzati. 133 monete sono entrate almeno una
volta; 6 non sono più scambiate (LUNA, EOS, MATIC, RNDR, SXP, TOMO) e restano nel campione fino all'ultimo giorno.
Sedi oggi (FATTO, API pubbliche): dei 31 membri attuali, 29 sono su Hyperliquid (leva massima 5–10x sulle alt, 20–40x su BTC/ETH/SOL/XRP)
e 28 su Kraken Futures. Dei 133 storici: 81 su Hyperliquid, 88 su Kraken.

**Motore.** Segnale noto alla chiusura del giorno prima, ingresso all'apertura della prima barra oraria. Stop k×ATR(14) con trailing a 2×stop,
uscita a tempo (7 giorni) o su segnale. Costi per lato: 4,5 pb + slippage 2 pb (top 10 per volume) oppure **10 pb** (le altre),
+5 pb sullo stop, funding reale. Leva = min(40, 1/(stop/0,6+0,005)); margine isolato.

**Misura dell'indipendenza.** P&L giornaliero in R di ogni posizione, sommato sul libro. N_eff = N²·σ_R² / varianza annua del libro
(da somme settimanali, così entra anche l'autocorrelazione). K = N_eff·(R̄/σ_R)² = Sharpe annuo² del flusso. In più: rapporto di
partecipazione (PR) della covarianza moneta×giorno e correlazione ρ tra esiti di trade aperti lo stesso giorno.

## 3. Risultati (R netto; tutto | scelta ≤2022 | verifica ≥2023)

### (a) Conviction alta per moneta, stop 1×ATR (stessa regola del libro v4)

| Universo | Trade/anno | R̄ tutto | R̄ scelta (t) | R̄ verifica (t) | σ_R | N_eff | ρ | PR | K tutto | K scelta | K verifica |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Trio BTC/ETH/SOL | 89 | +0,231 | +0,290 (2,6) | +0,197 (2,2) | 1,70 | 50 | 0,63 | 2,2 | **0,93** | 1,60 | 0,54 |
| Top 3 per volume, point-in-time | 92 | +0,175 | +0,168 (1,7) | +0,179 (2,0) | 1,62 | 51 | 0,54 | — | 0,60 | 0,78 | 0,49 |
| Top 5 | 146 | +0,147 | +0,153 (1,8) | +0,144 (2,0) | 1,66 | 65 | 0,48 | — | 0,51 | 0,71 | 0,38 |
| Top 10 | 280 | +0,098 | +0,142 (2,1) | +0,072 (1,4) | 1,69 | 77 | 0,42 | 8,6 | 0,26 | 0,52 | 0,14 |
| Top 20 | 510 | +0,047 | +0,130 (2,4) | 0,000 (0,0) | 1,66 | 85 | 0,36 | 14,1 | 0,07 | 0,40 | 0,00 |
| Top 30 | 720 | +0,039 | +0,120 (2,6) | −0,005 (−0,2) | 1,67 | 85 | 0,35 | 18,4 | 0,05 | 0,32 | 0,00 |
| Solo le alt (top 30 senza trio) | 635 | +0,015 | +0,103 (2,1) | −0,033 (−1,1) | 1,67 | 83 | 0,35 | 20,2 | 0,01 | 0,21 | −0,06 |
| Short, conviction ≤ 0,2, top 30 | 526 | +0,009 | +0,041 (1,2) | −0,014 (−0,5) | 1,27 | 43 | 0,57 | 8,4 | 0,00 | 0,07 | −0,01 |

Top 30, stress: costi ×2 R̄ +0,003 (verifica −0,045); ritardo +1 ora +0,020 (verifica −0,027); tetto di leva 10x: identico
(la leva mediana sulle alt è 7x, lo stop a 1×ATR è circa l'8%). Con stop 2×ATR: top 10 R̄ +0,090 (scelta +0,086, verifica +0,092, t 2,4), K 0,32.

Alt soltanto, per anno (R̄): 2020 −0,15 · **2021 +0,29 (t 4,2)** · 2022 −0,28 · 2023 −0,03 · 2024 −0,02 · 2025 −0,16 · 2026 +0,08.
Il margine sulle alt è il solo 2021. Trio per anno: +0,54 · +0,22 · −0,26 · +0,32 · +0,21 · +0,01 · +0,19.

### (b) Selezione trasversale per forza relativa (rendimento a L giorni, primi/ultimi k del top 30)

| Regola (k=5, stop 1×ATR) | Trade/anno | R̄ tutto | R̄ scelta (t) | R̄ verifica (t) | N_eff | K scelta | K verifica |
|---|---:|---:|---:|---:|---:|---:|---:|
| Long i più forti a 30 g, sempre | 473 | −0,030 | +0,025 (0,6) | −0,067 (−1,9) | 165 | 0,03 | −0,26 |
| Long i più forti a 30 g, BTC sopra la media a 100 g | 277 | +0,037 | +0,167 (2,3) | −0,027 (−0,6) | 105 | 1,10 | −0,04 |
| Long i più forti a 30 g e conviction alta | 256 | +0,056 | +0,100 (1,3) | +0,031 (0,6) | 112 | 0,34 | 0,04 |
| Short i più deboli a 7 g, BTC sotto la media a 100 g | 318 | +0,036 | +0,113 (2,9) | −0,031 (−0,9) | 84 | 1,07 | −0,06 |

Le 24 varianti (L = 7, 30, 90; k = 3, 5; tre filtri long, uno short) danno lo stesso quadro: ciò che è positivo in scelta è nullo in verifica.
Migliore in verifica: L30 k3 con conviction alta, +0,106 (t 1,7), ma in scelta +0,049 (t 0,6): non l'avrei scelta.

### (c) Libro neutrale long-forti / short-deboli, stop per gamba

| Regola | Trade/anno | R̄ tutto (t) | R̄ scelta | R̄ verifica (t) | σ_R | N_eff | ρ | K tutto | K verifica |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| L30 k5, 1×ATR, 7 g | 994 | −0,016 (−0,9) | +0,007 | −0,032 (−1,4) | 1,38 | 1.105 | 0,07 | −0,16 | −0,53 |
| L7 k5, 1×ATR, 7 g | 1.314 | −0,022 (−1,5) | +0,002 | −0,036 (−2,0) | 1,28 | 1.348 | 0,02 | −0,38 | −1,02 |
| L90 k5, 1×ATR, 7 g | 894 | −0,025 (−1,3) | 0,000 | −0,041 (−1,7) | 1,42 | 960 | 0,12 | −0,29 | −0,81 |
| L30 k5, 2×ATR, 28 g | 550 | +0,007 (0,3) | +0,016 | +0,001 (0,0) | 1,46 | 653 | 0,05 | 0,02 | 0,01 |
| Inversione a 7 g (long deboli, short forti), k5 | 1.494 | −0,061 (−5,5) | −0,033 | −0,079 (−5,5) | 1,07 | 1.630 | 0,03 | −5,3 | −8,1 |
| Conviction relativa moneta/BTC, coperta con BTC, top 30 (STIMA: percorso su open/close) | 543 | −0,003 | +0,150 (2,5) | −0,103 (−2,6) | 1,96 | 162 | 0,16 | 0,00 | −0,53 |

Qui N_eff supera N perché le due gambe si coprono. L'indipendenza c'è; il margine no.

### Controlli

- **5 minuti contro 1 ora** (trio, stessi segnali): R̄ 0,234 contro 0,231, verifica 0,198 contro 0,197. La barra oraria non falsa la misura; non ho scaricato i 5 minuti delle alt.
- **Troncamento**: 108 confronti (conviction e ranghi ricalcolati sui dati tagliati a t−1), 0 differenze.
- **Tetto di liquidità** (posizione ≤ 0,1% del volume mediano, conto 100k, top 30): a rischio 1% per trade tagliato l'1,9% dei trade (0,3% dal 2023); al 3% il 7,1%; al 5% il 13,5%. Non è il vincolo.
- Nessun risultato supera le soglie d'allarme del brief (Sharpe > 3, R̄ > 0,5 su oltre 100 trade).
- Un errore trovato e corretto: il filtro «BTC sotto la media» degli short era sempre acceso (negazione su una colonna non booleana). I numeri sopra sono quelli corretti.

## 4. Il risultato migliore, con la regola esatta

Nessuna regola di ampiezza batte il trio. Il risultato che vale è la **misura del tetto**:

1. **Long nella stessa direzione: il tetto è N_eff ≈ 85.** La correlazione tra esiti dello stesso giorno è 0,35–0,42 e il guadagno si esaurisce
   tra 10 e 20 monete (77 → 85 → 85). STIMA controfattuale: se le alt avessero lo stesso R̄/σ_R del trio (0,136), K salirebbe da 0,93 a 1,58.
   Per arrivare a 6,3 con 85 trade indipendenti servirebbe R̄/σ_R = 0,27, cioè R̄ ≈ +0,45 netti. Misurato sulle alt: −0,03 in verifica.
2. **Neutrale: N_eff ≈ 650–1.100, ma serve R̄ netto di +0,10–0,14 R** (R̄/σ_R 0,08–0,10) per K = 6,3. Misurato: tra −0,02 e +0,01, con costi di 0,05 R.
   È l'unica strada in cui l'aritmetica del 30% al mese regge sulla carta; con questi segnali il margine non c'è.

Candidato meno debole, solo per completezza (**non lo propongo**): conviction alta sul top 10 point-in-time, entrando solo quando meno del 37,5%
del top 30 ha conviction alta (soglia = primo terzile di selezione). 119 trade l'anno, R̄ +0,240 (scelta +0,300 t 2,6; verifica +0,207 t 2,5),
N_eff 54, K 0,90 (verifica 0,70). Pareggia il trio, non lo supera, e il filtro è fragile: sul trio con soglia 0,633 la verifica peggiora
(K 0,36 contro 0,54) e i trade scartati rendono +0,25 in verifica. **IPOTESI debole.**

## 5. Che cosa aggiunge al fondo, nei termini dell'aritmetica

| | N | N_eff | R̄/σ_R | N_eff·(R̄/σ_R)² | Crescita log a Kelly pieno |
|---|---:|---:|---:|---:|---:|
| Obiettivo 30%/mese | | | | 6,3 | 3,15 |
| Libro attuale (trio), tutto il periodo | 89 | 50 | 0,136 | 0,93 | 0,46 |
| Libro attuale, sola verifica | 96 | 42 | 0,114 | 0,54 | 0,27 |
| Top 30 conviction | 720 | 85 | 0,024 | 0,05 | 0,02 |
| Neutrale L30 k5 | 994 | 1.105 | −0,012 | −0,16 | negativa |

ΔN_eff = +35 (long) oppure +600/+1.000 (neutrale); ΔR̄/σ_R = −0,11 (long) oppure −0,15 (neutrale). Effetto netto su K: **da 0,93 a 0,05 o sotto**.
Aggiungere le alt a rischio pieno accanto al trio porta K in verifica da 0,54 a −0,01 (script 03, sezione F).

## 6. Che cosa è fallito

Tutto ciò che ho provato oltre i primi 3–5 nomi: conviction sulle alt, short a bassa conviction, forza relativa long (tre filtri), short dei deboli
in mercato ribassista, neutrale a 7/30/90 giorni, neutrale a orizzonte lungo, inversione a 7 giorni, conviction relativa contro BTC.
Lo schema è costante: positivo in scelta (2021), nullo o negativo dal 2023.

## 7. Conteggio delle prove

**67 varianti**: 10 (conviction per universo e stop, short) + 32 (trasversale e neutrale) + 14 (top 3/5, neutrale lungo, relativa) + 11 (filtro di ampiezza:
due soglie su cinque universi, più lo stop 2×ATR). Nessuna va aggiunta ai candidati del fondo.

## 8. Dubbi

- **Il trio del brief contiene senno di poi** (SOL scelta sapendo che sarebbe diventata grande): col top 3 point-in-time K è 0,60 e non 0,93.
- La regola dei costi sulle alt è la mia lettura più severa (4,5 pb + 10 pb di slippage = 14,5 pb per lato). Con 10 pb tutto compreso
  R̄ sulle alt salirebbe di circa 0,01 R: non cambia il verdetto.
- Venue: i prezzi sono Binance, che un retail italiano non può usare. Su Hyperliquid e Kraken gli spread delle alt minori sono più larghi (IPOTESI: peggio, non meglio).
- Il volume è in dollari e il conto in euro: il tetto di liquidità è calcolato 1:1.
- N_eff dipende dalla finestra con cui si misura la varianza (settimanale qui). Con quella giornaliera cambia di poco per i long, di più per il neutrale.
- Il segnale di conviction è stato costruito su BTC/ETH; non ho cercato un segnale nato per le alt. È la domanda aperta: il neutrale ha i trade
  indipendenti, manca un margine di +0,15 R lordi per gamba. Non l'ho trovato e la v4 (coppie, residui, funding trasversale) nemmeno.

## File

`00_dati.py` universo e scarico · `lab.py` motore · `01_convinzione` (a) · `02_trasversale` (b)(c) · `03_estensioni` controlli e 5 minuti ·
`04_sintesi` tetti, sedi, file · `05_ampiezza_filtro` · `returns.parquet` (rendimenti giornalieri a rischio 1% per trade, somma semplice) ·
`trades.parquet` (6 libri, 14.022 trade) · `universo_*.parquet`. Le cache intermedie sono in `data_cache/v5_a4_*.pkl`.
