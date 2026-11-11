# A3 — Rotture intraday ed espansione della volatilità (v5) — TUTTO SIMULATO

Dati: barre 5 minuti dei perpetual USDT-M Binance (data.binance.vision), 10 monete (BTC ETH SOL BNB XRP DOGE ADA LTC LINK AVAX),
2020-01 → 2026-10, con volume taker; funding reale. Scelta ≤ 2022-12-31, verifica ≥ 2023-01-01. Chiavi cache `v5_um_5m_*`.
Simulatore (`lab.py`): segnale alla chiusura della barra t → ingresso all'apertura di t+1; costi 6,5 pb per lato + 5 pb sullo stop +
funding; gap oltre lo stop = apertura della barra; stop e obiettivo nella stessa barra = stop; leva = min(40, 1/(stop/0,6+0,005));
perdita limitata a 1/leva. Sede ipotizzata: Hyperliquid (fino a 40x); con 10x UE i candidati A/C restano fattibili (stop ≥ 4%).

## Risposta in una riga
**FATTO (negativo): nessun setup intraday con stop stretto (≤ 1,5%, leva 30–40x) sopravvive ai costi.** La deriva lorda dopo una
rottura intraday è ≈ 0 pb; quello che resta è il costo (−0,13…−0,48 R per trade). L'unica rottura che guadagna è quella a più giorni
(massimo a 7–30 giorni, Donchian 4h a 100 barre) con stop largo (4–5%, leva ~12x): è il trend che il fondo ha già
(correlazione mensile con `trade11` 0,54–0,67). Aggiunge poco: in verifica Sharpe² del fondo C3 da 1,66 a ~1,95 (obiettivo 6,3).

## Cosa ho provato (323 varianti contate; 254 strategie + 69 celle dello studio a eventi)
| Famiglia (file) | Varianti | Stop mediano | Migliore in SCELTA: R sel / R ver (t a grappoli per giorno) | Esito |
|---|---|---|---|---|
| Controllo: ingressi casuali, stop 1% | — | 1,0% | R −0,147 (atteso −0,13…−0,15); a costo zero R 0,000 | simulatore corretto |
| Donchian 1h, stop 1–2 ATR (01) | 18 | 1,1–2,5% | +0,079 / −0,029 (t 1,7 / −0,7) | perde in verifica |
| Donchian 4h, stop 1–2 ATR (01) | 18 | 2,3–4,7% | **+0,456 / +0,211 (t 3,0 / 1,9)** N=100, 2 ATR, trail 4R | tiene, ma è trend |
| Squeeze BB-dentro-Keltner / ATR basso, 5m-15m-1h (02) | 24 | 0,3–2% | +0,122 / −0,005 (t 1,6 / −0,1) | zero in verifica |
| Opening range Asia(00 UTC)/Londra 08/NY 09:30, 15-30-60 min (02) | 36 | 0,4–1,5% | −0,000 / −0,121 (t 0,0 / −3,3) | tutte negative |
| Rottura 5m + volume ×3/×6 + quota taker > 60% (02) | 24 | 0,7–1,4% | −0,004 / −0,093 (t −0,1 / −2,7) | tutte negative |
| Falsa rottura → fade (02) | 18 | 0,5–0,8% | −0,169 / −0,282 (t −4,5 / −8,6) | tutte negative |
| Accensione: 4-6-8 barre 5m consecutive, seguire o contrastare (02) | 24 | 0,7–0,8% | −0,141 / −0,203 (t −2,4 / −3,9) | tutte negative |
| Studio a eventi: deriva lorda in pb per lookback×orizzonte×condizione (03) | 69 | — | vedi sotto | deriva simmetrica ≈ 0 |
| Rottura 24h/3g/7g solo in vol compressa (percentile 30g) (04) | 75 | 0,9–3,8% | +0,235 / +0,089 (t 2,7 / 0,75) N=7g, stop 6 hv, 72h | il filtro non aggiunge nulla |
| Rottura long 3g/7g/30g, stop 1,5-3-6 hv (05) | 9+4 | 1,2–4,9% | +0,407 / +0,160 (t 3,4 / 1,4) N=30g, stop 6 hv | trend |
| Sweep larghezza dello stop (06) | 4 | 0,6–9% | vedi sotto | stop stretto = peggio |

**Studio a eventi (FATTO).** Prima chiusura 5m oltre il massimo/minimo a N barre, 146.432 eventi, rendimento lordo nel verso della rottura:
a 4h la deriva è −6,5…+2 pb (scelta) e −1,9…+4,3 pb (verifica) per lookback 6h–3g: sotto i 13–18 pb di costo in ogni cella.
Non è simmetrica: dopo le rotture al rialzo il prezzo sale (+58 pb a 24h in scelta, +15 in verifica), dopo quelle al ribasso **rimbalza**
(lo short perde −39 / −27 pb): le due metà sono entrambe "long", cioè il trend e il DIP-24h che il fondo ha già.
Volume alto e taker a favore non cambiano il segno in verifica. La vol compressa dà +23 pb a 4h in scelta (t 4,2) ma +6,5 in verifica (t 1,5).

## Lo stop stretto NON giustifica la leva alta (FATTO, il risultato più utile)
Stessa regola (rottura del massimo a 7 giorni, long, trailing 6R, max 72h), solo la larghezza dello stop cambia:
| Stop (× vol oraria) | Stop mediano | Leva | Costo in R | R medio | Vincenti | R̄/σ_R | Sharpe scelta | Sharpe verifica |
|---|---|---|---|---|---|---|---|---|
| 0,75 | 0,6% | 40x | 0,24 | −0,141 | 15% | −0,037 | −0,49 | −1,15 |
| 1,5 | 1,2% | 40x | 0,125 | +0,109 | 17% | 0,029 | 0,89 | 0,22 |
| 3 | 2,3% | 23x | 0,064 | +0,246 | 27% | 0,082 | 1,53 | 0,75 |
| 6 | 4,4% | 13x | 0,033 | +0,208 | 41% | 0,103 | 1,99 | 0,77 |
| 12 | 8,5% | 7x | 0,017 | +0,118 | 48% | 0,109 | 1,85 | 0,84 |
Donchian 4h: stesso andamento (stop 0,5 ATR → Sharpe 0,30 / 0,03; 2 ATR → 1,72 / 0,93; 4 ATR → 1,97 / 0,96).
Il R medio ha un massimo attorno al 2% di stop, ma ciò che conta per la crescita è R̄/σ_R (e lo Sharpe del flusso): **cresce con lo stop
largo**. Stringere lo stop fa uscire sul rumore (vincenti dal 41% al 15%) e moltiplica il costo in R. A parità di rischio per trade la
leva non crea rendimento: 30x con stop 1,7% e 12x con stop 4,5% rischiano la stessa cosa, il secondo con un trade migliore.

## Miglior candidato: A — Donchian 4h (regola esatta)
Barre 4h costruite dalle 5m. Long se la chiusura 4h supera il massimo delle 100 barre 4h precedenti; short se scende sotto il minimo.
Ingresso all'apertura della barra 5m successiva. Stop = 2 × ATR(14) a 4h (mediana 4,6% → leva ~12x). Trailing stop a 4R dal massimo
favorevole (aggiornato a fine barra). Uscita a tempo dopo 8 giorni. Un trade alla volta per moneta. Scelto perché primo per t in scelta.
| | n | R medio | t | t a grappoli | Vincenti | R̄/σ_R | Sharpe del flusso |
|---|---|---|---|---|---|---|---|
| Tutto 2020–2026 | 1.534 (226/anno) | +0,306 | 4,55 | 3,42 | 34% | 0,116 | 1,31 |
| Scelta | 591 | +0,456 | — | 3,02 | — | — | 1,74 |
| Verifica | 943 | +0,211 | — | 1,91 | — | — | 0,98 |
| Costi ×2 | 1.534 | +0,265 (sel 0,423 / ver 0,167) | 3,95 | 2,97 | 33% | 0,101 | sel 1,62 / ver 0,77 |
| Ritardo +1 barra | 1.526 | +0,300 (sel 0,465 / ver 0,198) | 4,49 | 3,38 | 33% | 0,115 | sel 1,75 / ver 0,94 |
Per anno (R medio, n): 2020 +0,77 (155) · 2021 +0,58 (203) · 2022 +0,14 (233) · 2023 +0,27 (255) · 2024 +0,17 (232) · 2025 +0,13 (243) ·
2026 +0,28 (213). **Decadimento netto: il R medio di verifica è meno della metà di quello di scelta.**
Per lato: long +0,63 scelta / +0,31 verifica; short +0,20 / +0,08 (t 1,0 / 0,55: non distinguibile da zero).
Uscite: 71% stop, 29% tempo. R peggiore −1,40 (gap + funding), migliore +34,6 (il risultato dipende dalle code). Troncamento: 0 differenze su 25.
Nessuna soglia d'allarme superata (R < 0,5, Sharpe < 3, vincenti < 65%).

## Indipendenza dal libro esistente (FATTO)
| | Trade aperti in giorni in cui il libro 11x è in posizione | Corr. mensile con `trade11` | Corr. mensile con libro giornaliero | R nei giorni del libro / fuori |
|---|---|---|---|---|
| A. Donchian 4h (long+short) | 62% (calendario: 58%) | 0,54 | 0,44 | +0,39 / +0,17 |
| A solo long | — | 0,69 | — | — |
| A solo short | — | −0,08 | — | scelta +0,20, verifica +0,08 |
| A sulle 7 monete che il libro non tratta | — | 0,39 | — | scelta +0,43, verifica +0,17 |
| C. rottura 30 giorni long | 88% | 0,61 | 0,53 | +0,30 / −0,04 |
| D. rottura 7 giorni long, stop 2,3% (23x) | 70% | 0,67 | 0,49 | +0,33 / +0,06 |
I trade che guadagnano sono quelli che cadono negli stessi giorni del libro. I trade fuori da quei giorni (586) rendono +0,17 R con t 0,9.
Regressione giornaliera di A su `trade11` e sul libro giornaliero: alfa t = 3,15 in scelta, **t = 1,30 in verifica**.

## Cosa aggiunge al fondo, nei termini dell'aritmetica del BRIEF
- N·(R̄/σ_R)² va misurato sul flusso giornaliero, non sui trade: 10 monete rompono insieme, quindi 226 trade/anno non sono 226 scommesse
  indipendenti. Sharpe² di A da solo: 3,15 in scelta, **0,79 in verifica** (il conto ingenuo per trade darebbe 3,0).
- Fondo C3 + A con il peso deciso in scelta (A a ~0,5% di rischio per trade): in verifica Sharpe 1,29 → 1,39, cioè **Sharpe² 1,66 → 1,95
  (Δ ≈ +0,3; tetto ex-post 2,02)**. Obiettivo: 6,3. STIMA: crescita logaritmica a Kelly pieno da ~0,83 a ~0,98 l'anno contro 3,15 richiesti.
- ΔN: +226 trade/anno nominali, ma equivalenti a circa +20–30 scommesse indipendenti. ΔR̄/σ_R: nessuno (0,116 contro 0,14 del libro).
- A da solo a mezzo Kelly in verifica (STIMA): crescita log 0,31/anno (≈ +36%/anno), **mese mediano −1,1%**. Non è il 30% al mese:
  è circa il 2–3% al mese di media, concentrato in pochi mesi.
- Il lato short e i trade fuori dai giorni del libro, che sarebbero la vera fonte di N indipendente, non aggiungono nulla in verifica
  (Sharpe C3 1,29 → 1,28 e 1,27).

## Cosa è fallito e perché (FATTO)
1. Tutto ciò che ha stop ≤ 1%: il costo è 0,13–0,25 R per trade (0,48 R per gli stop allo 0,4%) e la deriva lorda è nulla.
2. Opening range: 36 su 36 negative, anche tenendo 24h; l'apertura di sessione non contiene informazione direzionale sui perp crypto.
3. Conferma con volume e taker: non migliora; la rottura con volume ×6 rende −0,06 R.
4. Falsa rottura: la peggiore (−0,23…−0,31 R). Lo stop sopra l'estremo è troppo vicino (0,5–0,8%) e viene preso dal rumore.
5. Accensione di momentum: né seguire né contrastare; R ≈ −costo in entrambi i versi, cioè nessuna prevedibilità a 1–4 ore.
6. Squeeze: bello in scelta (t 4,2 sulla deriva a 4h), sparisce in verifica; con gli stessi parametri il regime NON compresso rende uguale.

## Dubbi
- I 7 perp aggiunti sono sopravvissuti (niente LUNA/FTT a 5m): il risultato sulle altcoin è gonfiato. IPOTESI: effetto piccolo sul long, nullo sullo short.
- Slippage fisso a 2 pb: su DOGE/ADA/LINK a 40x e durante le rotture è ottimistico; i setup stretti sarebbero ancora peggiori.
- Solo ordini taker. Un ingresso maker (1,5 pb su Hyperliquid) dimezzerebbe il costo, ma serve un modello di riempimento che non ho:
  nelle rotture l'ordine passivo viene eseguito soprattutto quando la rottura fallisce (selezione avversa). Non testato.
- Il trailing è aggiornato a fine barra; l'ordine stop/obiettivo dentro la barra è assunto sfavorevole.
- Lo Sharpe² combinato dipende da come si pesa A rispetto a C3; il peso è scelto su 3 anni soli (2020–2022, mercato rialzista).
- Deflated Sharpe: con 323 varianti qui (1.135 in totale col passato) un t a grappoli di 3,0 in scelta e 1,9 in verifica non è una scoperta.

## File
`00_dati.py` scarico · `lab.py` simulatore · `01_donchian` · `02_famiglie` · `03_eventi` · `04_squeeze_regime` · `05_candidati` ·
`06_finale` (ognuno con `.out`) · `res_*.parquet` griglie complete · `trials_*.json` conteggi · `returns.parquet` (rendimenti giornalieri
netti a 0,5% di rischio per trade: A, A solo short, D) · `trades.parquet` (4.356 trade di A e D: ingresso, uscita, simbolo, lato, stop, leva, R, motivo).
