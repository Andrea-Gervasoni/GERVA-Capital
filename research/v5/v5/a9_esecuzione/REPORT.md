# A9 — Esecuzione, costi e posizione dello stop (v5) — tutto SIMULATO

Mandato: alzare l'R NETTO per trade **senza toccare il segnale** (conviction "alta" di v4, nota la sera prima), tagliando costi e slippage.
Libri di partenza: **A** = stop 1×ATR, trailing 2× (≈11x); **C** = stop 1,7% fisso, senza trailing (30x). BTC, ETH, SOL.
Dati: spot Binance 5m, perpetual Binance USDT-M 5m (cache `v4_um_5m_*`) e **1 minuto** (scaricati: `v5_um_1m_*`, 2020-01 → 2026-10),
funding Binance per regolamento, funding orario Hyperliquid (dal 2023-05-12). Sui perpetual: **scelta = 2020–2022, verifica = 2023+**.
Costi: taker 4,5 pb + 2 pb slippage per lato, +5 pb sullo stop, maker 1,5 pb, funding reale. K = N·(R̄/σ_R)² (l'obiettivo del brief è 6,3).

## 0. Controlli (FATTO)
- Motore riscritto da zero (`lib.py`): riproduce v4 trade per trade (A: 652 trade, R 0,2365; C: 1099, R 0,3635; scarto massimo 7·10⁻¹⁵).
- Troncamento: segnale e ATR ricalcolati sui dati tagliati a t−1: 120/120 identici.
- Percorso a 1 minuto al posto del 5 minuti: R invariato alla terza cifra (A 0,229 / 0,229; C 0,284 / 0,285).
- R̄ > 0,5 su > 100 trade compare solo nei sotto-periodi di scelta di C con filtri (2020–21), mai nella regola finale.

## 1. Quanto dell'R simulato è un artefatto dello SPOT usato al posto del perpetual (FATTO)
Stesso segnale, stessi costi, funding esatto, 2020-01 → 2026-10 (`01_base.out`).

| Libro | serie | n | R̄ | σ_R | t | R scelta | R verifica | K scelta | K verifica |
|---|---|---|---|---|---|---|---|---|---|
| A 1×ATR | spot | 586 | 0,220 | 1,72 | 3,09 | 0,289 | 0,179 | 2,09 | 1,03 |
| A 1×ATR | **perp** | 592 | 0,216 | 1,73 | 3,04 | 0,313 | **0,159** | 2,58 | 0,79 |
| C 1,7% | spot | 995 | 0,331 | 4,14 | 2,52 | 0,514 | 0,201 | 1,60 | 0,47 |
| C 1,7% | **perp** | 1026 | 0,252 | 4,05 | 1,99 | 0,468 | **0,104** | 1,35 | 0,14 |

- A: l'artefatto è piccolo: −0,01 R sugli stessi trade (t −0,7), −0,02 R in verifica. Il livello 11x regge.
- C: l'artefatto è grande: **−0,08 R** (da 0,33 a 0,25), in verifica l'R si **dimezza** (0,20 → 0,10, t 0,7). Con stop più stretti lo scarto
  resta (0,9%: −0,056; 0,6%: −0,040). Causa: le candele perp hanno code più lunghe (minimo a 5m in media −1,6 pb sotto lo spot per BTC, −3,8 pb
  per SOL; 1° percentile −10 / −33 pb): lo 0,8–1,9% dei trade è fermato **solo** sul perp, quasi mai il contrario; ogni stop in più genera
  un rientro il giorno dopo (1026 trade contro 995).
- Il funding contato esattamente (regolamenti davvero attraversati) invece della somma giornaliera di v4 sposta poco: A −0,002 R, C +0,015 R.
- Hyperliquid contro Binance perp (candele orarie, 2026-04 → 10, 4728 ore): i minimi HL sono in media 1,7–3,2 pb **più alti**, ampiezza −1 / −4%:
  il perp Binance è un sostituto prudente di HL (STIMA: solo 7 mesi di dati HL).

## 2. (a) Ingressi maker (`02_maker.out`, 146 varianti a 5m + 32 a 1m)
Limite a open·(1−x), valido W; eseguito solo se il prezzo **scende sotto** il limite (non basta il tocco).
- Probabilità di esecuzione con x = 0: 96,8% in 5 minuti, 98% in 15 minuti, 99% in 1 ora (93% nel primo minuto). x = 5 pb: 72% / 83% / 91%.
  x = 25 pb: 29% / 43% / 64%.
- **Selezione avversa**: con limiti vicini (0–2 pb) NON c'è: i pochi trade non eseguiti hanno R medio **negativo** (A −0,69 R; C −0,47 R
  per x = 0, 5m), ma sono 19–30 trade: rumore. Con limiti profondi c'è ed è forte: x = 25 pb / 5m lascia fuori il 71% dei trade, che portano
  l'**81%** dell'R totale (A) e il 93% (C); x = 50 pb / 24h: i non eseguiti rendono 0,86 R contro 0,12 degli eseguiti. "Aspettare lo sconto" costa.
- Regola difendibile (non il massimo della griglia): **limite all'apertura, 15 minuti, poi ordine a mercato**. Nessun trade perso; il guadagno è
  puro risparmio di costo: A +0,010 R, C +0,028 R. Le varianti "poi si salta" sembrano migliori ma dipendono da meno di 30 trade.
- Uscite a tempo con limite (15 minuti, poi mercato): altri +0,003 R (A) / +0,004 R (C).

## 3. (b) Ora d'ingresso (`03_ora.out`, 74 varianti)
- 00:00 UTC è già la scelta giusta per A: 1ª su 24 ore in scelta, 4ª in verifica; l'R **decresce** con il ritardo (blocchi 00–07 / 08–15 / 16–23:
  scelta 0,29 / 0,27 / 0,22; verifica 0,145 / 0,105 / 0,083). Correlazione tra ore scelta–verifica +0,63: è decadimento del segnale, non rumore.
- C: nessuna struttura (correlazione +0,05); l'ora migliore in scelta (h=10) in verifica fa peggio di h=00.
- Rottura del massimo della prima ora / 4 ore / 8 ore: meglio in scelta (A 4h: 0,446), peggio in verifica (0,114 contro 0,159). SCARTATA.
- Entrare un'ora dopo costa 0,03–0,06 R (A verifica 0,159 → 0,100): la puntualità vale più di tutta l'ottimizzazione delle commissioni.

## 4. (c) Posizione dello stop e "caccia agli stop" (`04_stop.out`, 47 varianti)
"Cacciato" = stop preso e poi prezzo sopra l'ingresso entro 24 ore. Tabella senza trailing (con il trailing lo stop può stare sopra l'ingresso).

| Stop | distanza mediana | stop presi | cacciati / stop | atteso per caso | R scelta | R verifica | K scelta | K verifica |
|---|---|---|---|---|---|---|---|---|
| fisso 1,7% | 1,7% | 83% | 62% | 61% | 0,468 | 0,104 | 1,35 | 0,14 |
| 0,5×ATR | 2,5% | 75% | 48% | 42% | 0,359 | 0,235 | 1,37 | 0,73 |
| **1×ATR** | 5,0% | 52% | 18% | 11% | 0,388 | 0,151 | **3,01** | 0,62 |
| 2×ATR | 10% | 23% | 5,5% | 1,4% | 0,211 | 0,129 | 2,07 | 1,08 |
| minimo di ieri −0,1% | 2,7% | 68% | 49% | 45% | 0,545 | 0,048 | 2,36 | 0,03 |
| placebo (stessa distanza, 5 giorni prima) | 2,3% | 70% | 52% | — | 0,341 | 0,131 | 0,96 | 0,22 |
| minimo 3 giorni | 4,7% | 56% | 39% | 35% | 0,354 | 0,062 | 1,50 | 0,06 |
| placebo 3 giorni | 4,5% | 54% | 36% | — | 0,425 | 0,205 | 1,86 | 0,67 |
| sotto il numero tondo (1×ATR) | 6,1% | 41% | 13% | — | 0,268 | 0,157 | 1,96 | 0,92 |

- La frequenza di "caccia" è quella di una passeggiata casuale più 1–7 punti: dipende dalla distanza, non dal tipo di livello.
- Gli stop "strutturali" (minimo di ieri, swing) NON battono in verifica un placebo con la stessa distanza; lo swing perde anche in scelta.
- Numeri tondi: stop entro il 10% del passo da un tondo presi il 60,7% delle volte contro 59,3% lontano; spostarli non cambia nulla (K 2,63 contro 2,58).
- Conclusione: **1×ATR resta il migliore in scelta** (con trailing K 2,58, senza 3,01; in verifica 0,79 contro 0,62: indistinguibili). Nessun cambio.

## 5. (d) Funding e (e) base (`05_funding_base.out`, 16 varianti)
- Il funding pesa più delle commissioni su A: 0,043 R per trade (24,7 pb in 109 ore) contro 0,028 R di commissioni + slippage; è il 17% dell'R
  ante-funding (C: 0,062 R, 20%). I long pagano un tasso annualizzato del 19,8% contro l'11,6% medio: si entra quando il funding è caro.
- Ora rispetto al regolamento: alle 00:00 si entra già subito dopo un regolamento; un regolamento evitato vale 1,6 pb = 0,003 R (A). Irrilevante.
- **Sede**: sugli stessi trade dal 2023-05-12 il funding orario **Hyperliquid costa 2,1 volte Binance**: A 29,9 pb contro 13,8 (0,063 contro 0,030 R,
  differenza −0,033 R, t −12,5); C 0,087 contro 0,039 R (−0,048 R). Vero in ogni anno 2023–2026. Scegliere trade per trade la sede col funding
  recente più basso non aiuta (0,031 R). Quindi il livello A (≤ 10x) costerebbe meno su una sede con funding a 8 ore (Kraken / OKX Europa:
  IPOTESI, non ho i loro dati; commissioni 5 / 2 pb: −0,003 R); C a 30x può stare solo su Hyperliquid e lì paga il funding doppio.
- Funding alto all'ingresso = trade peggiori: ultimo funding sopra il 3° quartile di scelta (> 3,2 pb/8h per A, > 4,0 per C): R −0,16 (A), −0,65 (C);
  in verifica −0,17 / −1,17 ma su 20 / 18 trade. Filtro "salta se funding > 3 pb" (soglia migliore in scelta): A scelta 0,313 → 0,435,
  verifica 0,159 → 0,154: **non confermato** (dal 2023 il funding Binance supera raramente la soglia).
- Base perp/spot all'ingresso: media +0,8 pb (5°–95° percentile −6 / +12 pb), variazione ingresso → uscita +1 pb = 0,004 R: come COSTO è nulla.
  Come informazione: terzile alto (> 7,4 pb) R scelta 0,21 / verifica −0,44 (25 trade). "Salta se base > 5 pb": A scelta 0,435, verifica 0,198
  (base 0,313 / 0,159); C 0,834 / 0,259 (base 0,468 / 0,104). Coerente nei due periodi ma **è un cambio di segnale** (filtro di affollamento),
  toglie il 20–30% dei trade, 2 soglie provate: IPOTESI da passare a chi lavora sul segnale, non fa parte della combinazione.

## 6. La combinazione difendibile (`06_combinazione.out`) — regola esatta
Segnale, stop e ora invariati. Alle 00:00 UTC: **limite d'acquisto al prezzo d'apertura (maker), valido 15 minuti; se non eseguito, ordine a mercato**.
Stop 1×ATR14 sotto l'eseguito, trailing 2× (stop a mercato). **Uscita a tempo: limite all'apertura, 15 minuti, poi mercato.** Sede: Hyperliquid (maker 1,5 pb).

| Libro A (1×ATR, ≈11x), perp | n | N/anno | R̄ | σ_R | t | R scelta (σ; N) | R verifica (σ; N) | K scelta | K verifica |
|---|---|---|---|---|---|---|---|---|---|
| base taker | 592 | 87 | 0,216 | 1,73 | 3,04 | 0,313 (1,67; 73) | 0,159 (1,76; 97) | 2,58 | 0,79 |
| **combinazione** | 593 | 87 | 0,229 | 1,73 | 3,22 | **0,325** (1,66; 73) | **0,172** (1,76; 98) | 2,83 | 0,93 |
| combinazione, costi ×2 | 593 | 87 | 0,208 | 1,73 | 2,93 | 0,310 | 0,148 | 2,54 | 0,69 |
| base, costi ×2 | 592 | 87 | 0,181 | 1,73 | 2,54 | 0,285 | 0,119 | 2,14 | 0,45 |
| combinazione, ritardo +1 barra | 590 | 87 | 0,218 | 1,72 | 3,08 | 0,322 | 0,157 | 2,77 | 0,78 |
| combinazione, attraversamento 3 pb | 596 | 88 | 0,213 | 1,72 | 3,02 | 0,298 | 0,162 | 2,41 | 0,83 |
| combinazione, **funding Hyperliquid** (2023-05+) | 319 | 92 | 0,111 | 1,67 | 1,19 | — | 0,111 | — | 0,41 |

| Libro C (1,7%, 30x), perp | n | N/anno | R̄ | σ_R | t | R scelta (σ; N) | R verifica (σ; N) | K scelta | K verifica |
|---|---|---|---|---|---|---|---|---|---|
| base taker | 1026 | 151 | 0,252 | 4,05 | 1,99 | 0,468 (4,75; 140) | 0,104 (3,49; 159) | 1,35 | 0,14 |
| **combinazione** | 1026 | 151 | 0,284 | 4,06 | 2,25 | **0,499** (4,76; 140) | **0,137** (3,49; 159) | 1,54 | 0,25 |
| combinazione, costi ×2 | 1026 | 151 | 0,218 | 4,07 | 1,71 | 0,431 | 0,072 | 1,14 | 0,07 |
| combinazione, ritardo +1 barra | 1026 | 151 | 0,250 | 3,91 | 2,05 | 0,384 | 0,155 | 1,06 | 0,31 |
| combinazione, funding Hyperliquid (2023-05+) | 529 | 153 | 0,078 | 3,49 | 0,51 | — | 0,078 | — | 0,08 |

- Sugli stessi trade: A **+0,013 R** (scelta +0,010, verifica +0,015; t appaiato +20,9), C **+0,032 R** (+0,031 / +0,033; t +42); 98% degli ingressi maker.
  σ_R e N invariati. È un risparmio meccanico: il costo per trade scende da 0,028 a 0,014 R (A) e da 0,076 a 0,043 R (C).
- Per anno (A, combinazione): 2020 +0,46; 2021 +0,29; 2022 −0,23 (16 trade); 2023 +0,34; 2024 +0,14; 2025 −0,00; 2026 +0,13: decade il segnale, non i costi.
- Per moneta (A, scelta / verifica): BTC 0,19 / 0,23; ETH 0,48 / **−0,02**; SOL 0,29 / 0,30.

## 7. Che cosa aggiunge al fondo (aritmetica del brief)
- ΔN = 0. ΔR̄: +0,013 R (A), +0,032 R (C). ΔR̄/σ_R: A verifica 0,090 → 0,097; C 0,030 → 0,039. K verifica A 0,79 → 0,93 (obiettivo 6,3).
- Il conto onesto parte però più in basso di quanto scritto nel brief: sul perp e con il funding della sede che concede la leva (Hyperliquid),
  A in verifica vale **R̄ ≈ 0,11, K ≈ 0,4** (non 0,18 e 1,5); C vale R̄ ≈ 0,08 (t 0,5): **il livello 30x non è sostenuto**.
- Crescita logaritmica a Kelly pieno = K/2: A su HL ≈ 0,2 l'anno (≈ +1,7% al mese) contro 3,15 necessari. L'esecuzione sposta K del 10–17% (A):
  non è la leva che porta al 30% al mese.

## 8. Che cosa è fallito
Limiti profondi (selezione avversa), ore diverse dalle 00:00, rottura del massimo iniziale, stop sul minimo di ieri / swing / numeri tondi,
scelta della sede per funding trade per trade, evitare il regolamento, filtro funding > 3 pb (non confermato in verifica).

## 9. Prove contate
367 esecuzioni in tutto (18 riproduzione e spot/perp, 180 maker, 74 ora, 47 stop, 16 funding/base, 32 combinazione e robustezza); circa 290 sono
varianti vere, le altre controlli. La regola finale non è il massimo di una griglia: è la variante più semplice (x = 0, 15 minuti).

## 10. Dubbi
- L'esecuzione maker è dedotta dalle barre: "il prezzo è sceso sotto il limite" non vede la coda né lo spread; per SOL e per taglie grandi è
  un'ipotesi ottimistica. Se si richiede un attraversamento di 3 pb il guadagno di A in scelta si annulla (0,298 contro 0,313).
- Lo slippage di stop (2 + 5 pb) è un'ipotesi non verificabile sulle barre; su HL lo stop scatta sul mark price (mediana di più sedi), quindi
  per C la verità sta tra lo spot e il perp Binance.
- Sul perp la scelta ha solo 3 anni (2020–2022) e il 2022 ha 16 trade. Il funding HL esiste solo dal 2023-05: nessuna scelta possibile su HL.
- Funding di Kraken / OKX Europa non misurato: "A costa meno su una sede a 8 ore" è IPOTESI.
- K somma BTC, ETH, SOL come trade indipendenti: non lo sono (solo BTC+ETH: K verifica 0,31).

File: `lib.py`, `00_dati_1m.py`, `01_base` … `06_combinazione` (.py + .out), `trades.parquet` (8 libri), `returns.parquet` (rendimenti giornalieri
all'1% di rischio per trade, R contabilizzato nel giorno d'uscita; colonne `_HL` dal 2023-05-12), `trials_*.json`.
