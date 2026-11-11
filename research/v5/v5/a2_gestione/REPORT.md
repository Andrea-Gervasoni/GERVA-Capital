# A2 — Gestione del trade (uscite, piramide, ingressi intraday) — TUTTO SIMULATO

**Risposta in una riga.** Nessuna regola di gestione, scelta sul periodo ≤ 2022, migliora in modo affidabile la verifica ≥ 2023.
La gestione non è la leva che avvicina il fondo al 30%/mese: N·(R̄/σ_R)² resta tra 1,0 e 1,4 (servirebbe 6,3).

## Che cosa ho misurato
- Ingressi invariati: giorni a conviction «alta» su BTC/ETH/SOL, long, come `research/v5/v4/leva_trade_isolato.py` (importato).
- Motore nuovo sul percorso a 5 minuti (`engine.py`). In modalità base riproduce il simulatore originale trade per trade
  (5 configurazioni, differenza massima in R 3·10⁻¹⁴: `01_validazione.out`). Troncamento della conviction: 120 date, 0 differenze.
- Tre basi senza gestione: **T** stop 1,7% (30x), **M** stop 1×ATR (~11x), **W** stop 2×ATR (~6x). Durata massima 7 giorni.
- 78 regole per base: trailing (5), trailing con attivazione (4), chandelier su ATR intraday (5), parabolico (4), pareggio (6),
  stop a tempo (8), obiettivo pieno (5), parziale (6), piramide (15), rientro dopo lo stop (8), ingresso intraday (12).
- Costi: 4,5 pb + 2 pb per lato, +5 pb sugli ordini stop (anche sulle aggiunte), funding reale ai pagamenti delle 00/08/16 UTC.
  «Costi ×2» raddoppia commissioni e slippage, non il funding. «Ritardo» = una barra da 5 minuti in più su ingressi e uscite a mercato.
- G = N·(R̄/σ_R)² per trade. S² = Sharpe annuo² del flusso giornaliero di R: tiene conto dei trade simultanei sulle tre monete.
- Venue: T richiede Hyperliquid (30x); M è al limite del 10x dei perp regolati UE; W (≈6x) sta su Kraken / OKX Europe.

## Le basi (FATTO, simulato)
| Base | periodo | trade/anno | R̄ | σ_R | R̄/σ_R | vincenti | serie perdente max | t (a grappoli) | G | G costi×2 | G ritardo |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T 1,7% | intero | 129 | +0,38 | 4,27 | 0,089 | 18% | 30 | 2,96 (2,65) | 1,03 | 0,56 | 0,97 |
| | scelta | 114 | +0,58 | 4,91 | 0,119 | 16% | 30 | — | 1,61 | — | — |
| | verifica | 153 | +0,20 | 3,61 | 0,056 | 19% | 25 | 1,35 (1,22) | 0,48 | 0,12 | 0,30 |
| M 1×ATR | intero | 72 | +0,28 | 1,91 | 0,148 | 43% | 11 | 3,66 (3,18) | 1,57 | 1,22 | 1,49 |
| | scelta | 59 | +0,40 | 2,00 | 0,199 | 46% | 8 | — | 2,31 | — | — |
| | verifica | 92 | +0,20 | 1,85 | 0,106 | 40% | 11 | 1,98 (1,64) | 1,03 | 0,67 | 0,79 |
| W 2×ATR | intero | 61 | +0,18 | 1,12 | 0,162 | 50% | 10 | 3,69 (3,43) | 1,60 | 1,34 | 1,55 |
| | scelta | 49 | +0,23 | 1,18 | 0,196 | 53% | 10 | — | 1,90 | — | — |
| | verifica | 77 | +0,14 | 1,08 | 0,134 | 48% | 10 | 2,29 (2,04) | 1,38 | 1,07 | 1,30 |

L'attuale «1×ATR con trailing 2×» in verifica: 96 trade/anno, R̄ +0,18, σ 1,73, R̄/σ 0,104, 41% vincenti, G 1,04 (0,64 a costi ×2).
Per anno (M base, R̄/n): 2019 +0,65/51 · 2020 +0,50/85 · 2021 +0,38/104 · 2022 −0,22/16 · 2023 +0,38/111 · 2024 +0,15/112 ·
2025 +0,01/80 · 2026 +0,18/47. Il vantaggio cala nel tempo (decadimento), con qualunque gestione.

## La regola migliore di ogni famiglia, scelta su G in scelta → esito in verifica (FATTO)
ΔG = variazione di N·(R̄/σ_R)² rispetto alla base senza gestione.
| Base | Regola migliore in scelta | ΔG scelta | G verifica (base) | ΔG verifica | ΔG verifica costi×2 |
|---|---|---|---|---|---|
| T | 2 aggiunte piene a +1R e +2R, stop invariato | +0,58 | 0,59 (0,48) | +0,11 | +0,14 |
| T | ingresso al ritorno sul VWAP dopo 4h | +0,08 | 0,32 | −0,16 | −0,08 |
| T | rientro quando riconquista l'ingresso | +0,07 | 0,27 | −0,21 | −0,10 |
| M | obiettivo pieno a +2R | +0,86 | 0,93 (1,03) | −0,11 | −0,25 |
| M | trailing 1× attivo da +1R | +0,46 | 1,10 | +0,07 | −0,17 |
| M | stop-buy 0,5×ATR sopra l'apertura | +0,41 | 1,13 | +0,10 | +0,08 |
| M | esci se non in utile dopo 12h | +0,23 | 1,22 | +0,18 | +0,06 |
| W | stop-buy 0,5×ATR sopra l'apertura | +1,42 | 0,94 (1,38) | −0,44 | −0,41 |
| W | obiettivo pieno a +1R | +1,13 | 1,29 | −0,09 | −0,23 |
| W | chandelier 3×ATR intraday | +0,64 | 0,95 | −0,43 | −0,47 |

- La vincitrice assoluta in scelta porta in verifica: T +0,11, M −0,11, W −0,44.
- Bootstrap a mesi appaiati in verifica (2.000 ricampionamenti), ΔS² della scelta contro la base: T +0,09 [−0,13; +0,33];
  M −0,07 [−0,58; +1,28]; W −0,30 [−1,55; +0,46]. Nessun intervallo esclude lo zero.
- Varianti che battono la base in scelta: 10 / 7 / 15 su 78. In scelta + verifica + costi ×2: 5 / 3 / 4.
- Combinazioni delle tre famiglie migliori in scelta (12 prove): tutte peggiori della base in verifica.
- Misura del rumore: cambiare solo la durata massima da 7 a 5 o 10 giorni sposta G in scelta di 0,1–1,2. Differenze sotto 0,5 non significano nulla.

## Famiglia per famiglia (verifica; dettagli in `02_griglia.out`)
- **Trailing a 2× lo stop iniziale (rimisurato).** Confermato. Stop 0,9% / 1,7% / 2,7%: G verifica da 0,17 / 0,48 / 0,30 a
  −1,40 / 0,03 / 0,12. Stop 1×ATR: 1,03 → 1,04 (nullo). Stop 2×ATR e 6%: 1,38 → 1,52 e 0,62 → 0,72, ma in scelta peggiora (1,90 → 1,73).
- **Chandelier e parabolico su volatilità intraday.** Stretti distruggono (parabolico 0,02/0,2: G −6 … −15). Larghi tornano alla base.
- **Pareggio.** A +0,5R / +1R peggiora T e W. Su T il pareggio a +2R dà 0,76 in verifica ma 0,94 in scelta contro 1,61: non sceglibile.
- **Stop a tempo.** 0,5–2h peggiora ovunque. 12–24h su T: meglio in verifica (0,61–0,69), peggio in scelta. 12h su M: +0,23 / +0,18.
  Su W solo 8h è meglio in verifica (1,62), ma in scelta è 1,44 contro 1,90.
- **Obiettivo e parziale.** Vendere metà riduce R̄ più di σ: R̄/σ scende in tutte le basi (M metà a +2R: 0,106 → 0,079).
  L'obiettivo pieno a +2R su W dà 2,41 in verifica, ma 1,64 in scelta contro 1,90: non sceglibile.
- **Piramide con stop spostato a pareggio (anti-martingala classica).** Peggiora T (0,48 → 0,32; a costi ×2 → 0,01) e porta la
  serie perdente massima da 25 a 57–152. Su M e W sta entro ±0,4 dalla base in verifica, sempre peggio in scelta.
- **Piramide con stop invariato.** L'unica famiglia con segno positivo quasi ovunque (vedi sotto).
- **Rientro dopo lo stop.** Mai meglio della base in verifica su T; nullo su M e W. Il libro rientra già il giorno dopo.
- **Ingresso intraday.** VWAP e orari fissi (08:00, 13:30, 20:00 UTC): peggio o pari. Stop-buy: forte in scelta, senza segno coerente
  in verifica (T +0,18, M +0,10, W −0,44). Limite 0,1×ATR sotto l'apertura: vedi sotto. Limite a 1×ATR: R̄ nullo o negativo.

## Miglior risultato, con la regola esatta (IPOTESI, non un fatto)
Due regole migliorano G in 5 celle su 6 (3 basi × scelta/verifica). L'elenco è fatto guardando anche la verifica: è un'osservazione, non una scelta.
1. **Una aggiunta a +1R, stop lasciato dov'è.** Regola: ingresso e stop come la base; quando il prezzo tocca ingresso + 1 distanza
   di stop, si compra un'altra unità uguale con ordine stop; lo stop comune non si muove (l'aggiunta rischia 2R, leva dimezzata);
   uscite come la base. Perdita massima per trade: 3R.
   - W: G scelta 1,90 → 1,97; verifica 1,38 → 1,94 (costi ×2: 1,07 → 1,61; ritardo: 1,30 → 1,87). R̄/σ verifica 0,134 → 0,159.
     Bootstrap ΔS² verifica +0,45 [−0,05; +0,79], P(>0) = 0,94.
   - M: scelta 2,31 → 2,24; verifica 1,03 → 1,26. T: scelta 1,61 → 1,95; verifica 0,48 → 0,49.
2. **Limite a 0,1×ATR sotto l'apertura, valido per il giorno** (circa 0,4% sotto; eseguito il 92–98% delle volte; costi da taker).
   Verifica: T 0,48 → 0,65, M 1,03 → 1,33, W 1,38 → 1,52. Scelta: −0,10 / 0,00 / +0,63. Bootstrap P(>0) = 0,57–0,76.

Un primo calcolo della piramide su T dava G verifica 1,43: era un errore mio (la perdita dell'aggiunta veniva troncata dalla leva
a 30x dell'unità iniziale). Corretto con la leva propria dell'aggiunta, scende a 0,59.

## In termini dell'aritmetica del fondo
- ΔN: zero (gli ingressi non cambiano; rientri e stop a tempo aggiungono trade ma abbassano R̄/σ di più).
- ΔR̄/σ_R onesto (regola scelta in scelta): −0,02 … +0,01. Nel caso più favorevole e non scelto (W + 1 aggiunta): 0,134 → 0,159.
- N·(R̄/σ_R)² in verifica: oggi 1,0 (M) – 1,4 (W). Con la migliore ipotesi 1,9 (STIMA ottimista); a costi ×2 1,6. Obiettivo 6,3.
- Conta di più la larghezza dello stop che la gestione: in verifica W 1,38 > M 1,03 > T 0,48; a costi ×2 1,07 / 0,67 / 0,12.
  Lo stop a 30x è il più fragile ai costi. In scelta l'ordine è diverso (M 2,31, W 1,90, T 1,61): anche questo è dentro il rumore.

## File
`engine.py`, `01_validazione.py/.out`, `02_griglia.py/.out` (237 varianti, `griglia.parquet`), `03_scelta.py/.out`,
`trades.parquet` (libri T/M/W base, le tre scelte, W + 1 aggiunta), `returns.parquet` (rendimenti giornalieri netti con rischio 1%
del conto per trade, P&L al giorno d'uscita, non composti).

## Conteggio e dubbi
- **Varianti provate: 276** (237 griglia + 12 combinazioni + 12 larghezze di stop × trailing + 15 durate massime).
- Barre spot Binance usate come proxy dei perpetual; lo slippage reale sugli stop a 30x in mercato veloce può superare 5 pb.
- Ordine degli eventi dentro una barra da 5 minuti: assunto il caso peggiore dopo un'aggiunta; trailing e pareggio valgono dalla barra dopo.
- Il limite sotto l'apertura è contato come eseguito solo se il prezzo lo attraversa; la coda nel book non è modellata.
- R̄ in scelta sopra 0,5 su T (0,58, 16% vincenti): ricontrollato con il simulatore originale, identico. È la coda dei pochi grandi vincenti.
- Con 276 prove e intervalli che includono lo zero, anche le due ipotesi sopra vanno trattate come rumore fino a prova contraria.
