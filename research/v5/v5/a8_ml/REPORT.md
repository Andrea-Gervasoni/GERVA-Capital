# A8 — Apprendimento statistico: un modello appreso batte la conviction a pesi uguali?

**Tutto SIMULATO su dati storici reali. Nessun trade eseguito.** Etichette: FATTO = misurato qui; STIMA = calcolo derivato; IPOTESI = non confermato.

## Risposta in tre righe
1. **Meta-labelling (FATTO, negativo):** il modello congelato scelto sul periodo ≤2022 (gradient boosting piccolo, P(R>0)) in verifica ha IC 0,013 (p = 0,31–0,45 ai test di permutazione): **non ordina i trade**. Usato come filtro sopra la regola attuale la **peggiora** (R̄ da +0,18 a 0,00).
2. **Previsione oraria (FATTO, negativo dopo i costi):** il segno a 4h è prevedibile in modo stabile (AUC 0,541 scelta → 0,542 verifica, 100.000 barre) ma il decile migliore rende 8 pb lordi contro 13 pb di costo: R̄ netto −0,03 / −0,06.
3. **Conferma del risultato precedente (FATTO):** la logistica ristimata sui 12 segnali fa peggio dei pesi uguali (R̄ verifica 0,16 contro 0,18; N·(R̄/σ)² 0,72 contro 1,07).

## Che cosa ho fatto
- **Dati:** percorso a 5 minuti Binance spot BTC/ETH/SOL (stesso proxy del libro v4), funding reale, candele orarie con volume taker riscaricate (`00_dati.py`, chiavi `v5_a8_*`), DVOL, open interest, Yahoo giornaliero, Fear&Greed.
- **Candidati (`01_dataset.py`):** ogni giorno × coin, 8.225 righe (2018-04 → 2026-10), trade long generico all'apertura: stop 1×ATR14, trailing 2×, max 7 giorni, leva = min(50, 1/(stop/0,6+0,005)), costi 4,5+2 pb per lato, +5 pb sullo stop, funding reale. 72 feature note la sera prima: i 12 segnali, rendimenti 1–120 g, volatilità, percentile ATR, volume e sbilanciamento taker (spot e perp), funding, base, DVOL, OI, stato di BTC/ETH/SPY/VIX/dollaro/oro, calendario.
- **Controlli (FATTO):** il mio simulatore riproduce il libro v4 «1×ATR alta trail 2» trade per trade (652 su 652, scarto massimo 0,00 R). Troncamento: feature ricalcolate su dati tagliati a 5 date (giornaliero, 13 casi) e 3 date × 3 coin (orario, 9 casi): **0 differenze su 22 casi**.
- **Protocollo (`ml.py`, `02_meta.py`):** walk-forward a finestra crescente, ristima semestrale, purga 7 g + embargo 7 g. Iper-parametri scelti **solo** sui blocchi fuori campione 2019H2–2022H2 con criterio dichiarato prima (IC di Spearman medio per blocco tra previsione e R). 22 configurazioni: logistica L2 sui 12 segnali (3), logistica su tutte (3), HistGradientBoosting classificatore (8) e regressore su R (8); alberi profondi 2–3, 50–150 iterazioni, foglie ≥100–300, tasso 0,03, L2 = 10.
- **Configurazione congelata (primaria):** HGB classificatore, profondità 2, 50 alberi, foglia ≥300. IC di scelta 0,081 (t 1,37; 6 blocchi su 7 positivi).

## Risultati — meta-labelling
**R per decile di probabilità prevista, VERIFICA 2023–2026** (4.176 candidati giornalieri sovrapposti; t con errori raggruppati per mese):

| decile | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| p media | 0,32 | 0,35 | 0,37 | 0,38 | 0,40 | 0,40 | 0,41 | 0,42 | 0,44 | 0,48 |
| quota vincenti | 0,41 | 0,40 | 0,38 | 0,42 | 0,40 | 0,42 | 0,36 | 0,36 | 0,39 | 0,49 |
| R̄ | +0,53 | +0,18 | +0,18 | +0,42 | +0,08 | +0,07 | −0,01 | −0,09 | −0,07 | +0,15 |
| R̄/σ | 0,22 | 0,11 | 0,09 | 0,19 | 0,06 | 0,05 | −0,01 | −0,07 | −0,05 | 0,11 |
| t | 0,97 | 0,87 | 0,79 | 1,33 | 0,64 | 0,49 | −0,05 | −0,66 | −0,46 | 0,86 |

Non è monotona: il decile **più basso** rende più del più alto. Tenendo solo i decili alti: top 30% R̄ −0,00; top 20% +0,04; top 10% +0,15, contro +0,145 di tutti i giorni e +0,113 dei giorni a conviction alta. **Nessun uplift.**

**Qualità dell'ordinamento (fuori campione), tutte le famiglie:**

| modello | IC scelta (t) | IC verifica (t) | blocchi >0 verifica | R̄ top 20% − R̄ tutti, verifica |
|---|---|---|---|---|
| HGB classificatore **(primario)** | +0,081 (1,37) | +0,013 (0,21) | 3/8 | −0,105 |
| Logistica 12 segnali | −0,072 (−1,27) | −0,033 (−0,82) | 2/8 | −0,051 |
| Logistica 72 feature | +0,036 (0,43) | +0,051 (0,78) | 4/8 | −0,054 |
| HGB regressore su R (secondario) | +0,020 (0,45) | −0,015 (−0,29) | 3/8 | +0,409 |
| Conviction a pesi uguali | −0,076 (−1,39) | −0,108 (−2,38) | 2/8 | +0,023 |

**Libri eseguibili** (una posizione per coin, non sovrapposti, soglie ex-ante = quantili delle previsioni dei blocchi precedenti; 2020–2022 scelta, 2023–2026 verifica; `03_books_perm.py`):

| libro | R̄ sel | N·(R̄/σ)² sel | n ver | trade/anno | R̄ ver | σ_R | R̄/σ | t | N·(R̄/σ)² ver | costi ×2 | ritardo 1h |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Regola attuale: conviction alta** | +0,29 | 2,23 | 366 | 97 | +0,181 | 1,73 | 0,105 | 2,01 | **1,07** | +0,142 | +0,105 |
| Sempre long (nessun filtro) | +0,11 | 0,93 | 817 | 215 | +0,042 | 1,58 | 0,027 | 0,76 | 0,15 | +0,004 | +0,036 |
| Modello p ≥ q0,8 | +0,30 | 2,72 | 99 | 27 | +0,321 | 1,69 | 0,190 | 1,90 | 0,99 | +0,289 | +0,297 |
| Modello p ≥ q0,9 | +0,52 | 3,77 | 45 | 14 | +0,460 | 1,65 | 0,278 | 1,87 | 1,11 | +0,429 | +0,468 |
| Alta **E** modello p ≥ mediana | +0,25 | 1,54 | 189 | 51 | +0,002 | 1,43 | 0,002 | 0,02 | 0,00 | −0,033 | −0,009 |
| Alta **O** modello p ≥ q0,9 | +0,33 | 3,32 | 370 | 98 | +0,185 | 1,74 | 0,107 | 2,05 | 1,12 | — | — |
| Logistica 12 segnali p ≥ q0,6 | +0,26 | 1,76 | 273 | 73 | +0,159 | 1,60 | 0,099 | 1,64 | 0,72 | — | — |
| [secondario] HGB regressore E[R] ≥ q0,8 | +0,52 | 4,89 | 206 | 56 | +0,377 | 2,26 | 0,167 | 2,40 | 1,58 | +0,330 | +0,338 |

Lettura (FATTO): le soglie alte del modello primario alzano R̄ per trade (0,32–0,46) ma tagliano i trade a 14–27 l'anno: la crescita attesa N·(R̄/σ)² resta **0,99–1,11 contro 1,07** della regola. I trade veri del libro v4 ordinati per p: terzile basso +0,33 R, medio +0,13, alto +0,08 (verifica, 366 trade): l'ordine è **rovesciato**.

Per anno (R̄ / n): regola attuale 2020 +0,45/95 · 2021 +0,25/108 · 2022 −0,34/16 · 2023 +0,32/119 · 2024 +0,17/114 · 2025 +0,01/84 · 2026 +0,15/49. Modello q0,8: +0,43/51 · +0,45/96 · −0,27/37 · +0,43/17 · +0,15/41 · +0,34/16 · +0,51/25.

**Test di permutazione** (200 permutazioni, pipeline intera ristimata ogni volta):

| statistica in verifica | reale | p (spostamento circolare) | p (blocchi mensili permutati) |
|---|---|---|---|
| IC medio per blocco, primario | 0,013 | 0,45 | 0,31 |
| R̄ top 20% − tutti, primario | −0,105 | 0,65 | 0,62 |
| R̄ libro q0,9, primario | +0,37* | 0,09 | 0,055 |
| R̄ top 20% − tutti, HGB regressore | +0,409 | 0,005 | 0,005 |
| R̄ libro q0,8, HGB regressore | +0,19* | 0,09 | 0,065 |

*calcolo rapido del libro (prossimo ingresso = ingresso + durata), identico per reale e nullo.

**Avvertenza metodologica (FATTO):** il test chiesto dal mandato, «etichette mescolate entro il mese», qui **non è un nullo valido**. L'esito del trade del giorno d è contenuto nelle feature dei giorni d+7…d+30 (ret7, ret30, distanza dai massimi). Mescolando entro il mese l'etichetta finisce su righe che già la conoscono: il nullo dà IC 0,111 ± 0,015 in verifica, cioè 8 volte il modello vero. Ho quindi usato due nulli che conservano la struttura temporale. Riporto il test originale in `03_books_perm.out` (p = 1,00) ma non va letto come prova a favore o contro.

**Stabilità delle feature (FATTO):** importanza per permutazione sul blocco di test, 15 fold. Correlazione di rango media tra fold **−0,004** (da −0,51 a +0,46); **nessuna** feature ha importanza positiva in ≥80% dei fold. Nella logistica sui 12 segnali solo trend10, trend30, trend120 e btc_ma100 hanno segno costante; lowvol ha segno negativo nel 93% dei fold. Il modello primario impara cose diverse a ogni ristima: è rumore.

**Lato short (FATTO):** stessa configurazione, IC verifica −0,013; libro short q0,8 R̄ −0,35 (85 trade). Niente.

## L'unico segnale: il regressore su R prevede l'ampiezza, non la direzione (IPOTESI)
Il regressore **non era la configurazione pre-scelta** (per il criterio IC era tra i peggiori) e l'ho guardato in verifica insieme ad altri tre: vale come ipotesi, non come risultato. Diagnosi (`06_hgbr_diag.out`):
- quintile alto di E[R]: R̄ long +0,46 (scelta) e +0,56 (verifica), ma quota vincenti 0,47 e 0,44, poco sopra la media;
- IC con R long −0,018 in verifica; IC con |R| +0,090 e +0,081: ordina la **dimensione** del movimento;
- nel quintile alto la quota di trade con R > 3 è 10–12% contro 2–7% degli altri; anche lo **short** rende di più (+0,10 contro −0,08 in verifica);
- sono giorni con ATR basso rispetto al proprio anno (percentile 0,30–0,36 contro ~0,49) e stop più stretto (4,2% contro 5,2%).

Cioè: quando l'ATR è compresso lo stop è stretto rispetto al movimento che segue, e con la perdita limitata a −1R più dispersione significa più R medio. È un effetto di **volatilità** (prevedibile), non di direzione. Corretto per 4 modelli × 3 statistiche guardate, p = 0,005 diventa circa 0,06. Regola esatta: entrare long se E[R] previsto ≥ quantile 0,8 delle previsioni fuori campione precedenti; stop 1×ATR14, trailing 2×, 7 giorni; leva massima ammessa dallo stop 11–13×: entra nei limiti di Hyperliquid (40×); su Kraken/OKX Europe (10×) è lo stesso trade con un po' più di margine.

## Risultati — previsione diretta su barre orarie (`04_hourly.py`)
Perpetual Binance BTC/ETH/SOL, 172.817 barre, 45 feature, training dal 2020, scelta su 2021–2022, 6 configurazioni per orizzonte.

| orizzonte | AUC scelta | AUC verifica | IC verifica | AUC per anno 2023→2026 | decile 10 lordo | decile 1 lordo |
|---|---|---|---|---|---|---|
| 4h | 0,541 | 0,542 | 0,056 | 0,563 · 0,549 · 0,535 · 0,523 | +8,0 pb | −1,2 pb |
| 24h | 0,554 | 0,528 | 0,037 | 0,537 · 0,545 · 0,521 · 0,525 | +34,7 pb | +18,9 pb |

Libro eseguibile (long sopra il quantile q, short sotto 1−q, stop 2σ√h sul percorso orario, costo 13 pb andata e ritorno + funding):

| libro | n ver | trade/anno | R̄ ver | t | costi ×2 | ritardo +1 barra | lordo dei costi | R̄ scelta |
|---|---|---|---|---|---|---|---|---|
| 4h, q 0,90 | 5.552 | 1.450 | −0,061 | −8,9 | −0,122 | −0,068 | −0,002 | −0,017 |
| 4h, q 0,97 | 1.198 | 317 | −0,027 | −1,9 | −0,085 | −0,072 | +0,029 | −0,028 |
| 24h, q 0,90 | 699 | 184 | −0,044 | −2,0 | −0,070 | −0,043 | −0,019 | +0,078 |
| 24h, q 0,97 | 276 | 81 | −0,039 | −1,2 | −0,064 | −0,043 | −0,015 | +0,131 |

Il segnale a 4h è reale ma vale meno dei costi e si dimezza in quattro anni. A 24h il libro era buono in scelta (t 3,1–3,4) e negativo in verifica: il lato short perde nel mercato rialzista e il decile più basso sale quanto la media. Solo-long a q0,9 (deciso dopo, descrittivo): −0,051 (4h) e −0,038 (24h).

## Che cosa aggiunge al fondo, nei termini dell'aritmetica
- **Modello primario: ΔN·(R̄/σ)² ≈ 0** (0,99–1,11 contro 1,07). Sposta la leva «R̄/σ per trade» da 0,105 a 0,19–0,28 ma toglie il 70–85% dei trade. Non avvicina il 30% al mese.
- **Regressore (IPOTESI):** N 97 → 56, R̄/σ 0,105 → 0,167, N·(R̄/σ)² 1,07 → 1,58 in verifica (STIMA: crescita logaritmica a Kelly pieno 0,53 → 0,79 l'anno; l'obiettivo richiede 3,15). Non si somma al libro v4: correlazione mensile 0,71, sono in gran parte gli stessi giorni.
- **Orario:** contributo negativo ai costi taker.

## Conteggio delle varianti
**60**: 22 configurazioni di modello, 13 libri giornalieri, 7 prove aggiuntive (short, logistiche come libro), 18 orarie. In verifica ho guardato 4 modelli (1 primario + 3 secondari).

## Dubbi
- Il criterio pre-dichiarato (IC di rango) si è rivelato inadatto a un R con coda destra grossa: premia chi indovina il segno, non chi trova i trade grandi. Un criterio su R̄ avrebbe scelto il regressore; ma lo so solo dopo aver visto la verifica.
- 99 e 45 trade in verifica per i libri del modello: l'errore standard di R̄ è 0,17–0,25. Le differenze tra libri sotto 0,15 R non sono distinguibili.
- La verifica 2023–2024 è un mercato rialzista; il 2025 è quasi piatto per tutti (regola +0,01).
- Percorso spot come proxy dei perpetual (ereditato dal v4); funding 0,03%/giorno prima del 2020.
- Le etichette sovrapposte non sono pesate per unicità; ho solo purgato e raggruppato gli errori per mese.
- OI e DVOL esistono solo dal 2021 (`top_ls` manca nel 94% delle righe di scelta): per buona parte della scelta il modello non li vede.

## File
`00_dati.py` · `lib.py` · `ml.py` · `01_dataset.py/.out` · `02_meta.py/.out` · `03_books_perm.py/.out` (≈18 minuti) · `04_hourly.py/.out` · `05_extra.py/.out` · `06_hgbr_diag.py/.out` · `frozen.json` · `dataset.parquet` · `preds.parquet` · `preds_hourly.parquet` · `trades.parquet` (4 libri: riferimento v4, primario q0,8 e q0,9, regressore secondario) · `returns.parquet` (rendimenti giornalieri a rischio 1% per trade, P&L al giorno d'uscita) · `trades_hourly_{4h,24h}.parquet`.
