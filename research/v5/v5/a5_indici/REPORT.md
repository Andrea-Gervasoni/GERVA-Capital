# A5 — Trade a leva su indici e macro (fuori dalle cripto) — TUTTO SIMULATO

Sede necessaria: **IBKR** (CFD su indici o micro future, tetto 20x; oro 20x; FX 30x). Nessun ordine e' stato inviato.
Script: `00_fomc.py`, `lab.py`, `01_setups.py`, `02_flusso.py`, `03_percorso.py` (+ `.out`). Serie: `trades.parquet`, `returns.parquet` (rischio 1% per trade).

## Che cosa ho misurato (FATTO)
- Dati: barre **giornaliere** Yahoo 1993/1999/2000 → 2026-11-09 (SPY, QQQ, IWM, GLD, TLT, 9 settori, VIX, VIX3M, EURUSD, USDJPY, GBPUSD), GEX SqueezeMetrics dal 2011, 269 date FOMC programmate scaricate dal sito della Fed.
- Motore: segnale alla chiusura di t, **ingresso all'apertura di t+1** (alla chiusura solo per i setup di calendario, che non usano il prezzo di t); stop fisso in multipli di ATR(14); salto oltre lo stop = uscita all'apertura; stop toccato = stop − 2 bp; leva = min(20, 1/(s/0,6+0,005)); perdita limitata a nozionale/leva.
- Costi: 2–3 bp per lato (indici, oro), 1–1,5 bp (FX); finanziamento CFD per notte (tasso + 1,5%)/360; dividendi accreditati/addebitati. R = rendimento netto / distanza dello stop.
- Con stop fisso e uscite ad apertura/chiusura la barra giornaliera e' esatta per la seduta regolare. Non vede la notte del CFD: verificato a parte (sotto).

## Risultati per famiglia (R netto; scelta ≤ 2022, verifica ≥ 2023) — 144 varianti in `01_setups.out`
| Setup (migliore variante per famiglia, scelta sulla sola scelta) | N/anno | R̄ intero | t | R̄ scelta (t) | R̄ verifica (t, n) | costi ×2 | ritardo |
|---|---|---|---|---|---|---|---|
| IBS<0,1 SPY, stop 1 ATR | 24 | +0,14 | 4,1 | +0,14 (3,9) | +0,14 (1,2; 78) | +0,11 | +0,05 |
| IBS<0,2 **con VIX≥20**, SPY / QQQ / IWM | 22 l'uno | +0,14/+0,14/+0,11 | 3,5/3,5/2,7 | +0,14/+0,13/+0,11 | +0,16/+0,30/+0,17 (n 40) | +0,11/+0,13/+0,09 | +0,11/+0,04/+0,02 |
| IBS<0,2 con VIX<20 (stessi indici) | 20–23 | +0,01/−0,01/−0,10 | — | ≈0 | negativo | — | — |
| IBS short (IBS>0,9) | 33 | −0,07 | −2,3 | −0,04 | −0,31 | — | — |
| RSI(2)<10 SPY, stop 2 ATR | 15 | +0,08 | 2,6 | +0,07 (2,2) | +0,14 (1,7) | +0,07 | +0,06 |
| Ampiezza: ≥8 settori su 9 con IBS<0,2 → SPY | 13 | +0,09 | 2,9 | +0,09 (2,7) | +0,10 (1,1) | +0,07 | +0,08 |
| Cambio del mese (chiusura ultimo giorno → chiusura +3), SPY/QQQ | 12 | +0,09 | 2,6/2,5 | +0,10 (2,7/2,4) | +0,03/+0,08 (0,3/0,8) | +0,07 | +0,05 |
| Pre-FOMC (chiusura vigilia → chiusura annuncio), QQQ / SPY | 8 | +0,13/+0,08 | 2,6/1,8 | +0,15/+0,11 (2,7/2,2) | +0,04/−0,11 | +0,11/+0,05 | +0,02/+0,01 |
| Post-FOMC long | 8 | ≈0 | −0,3 | −0,04 | +0,19 (1,3) | — | — |
| Tendenza QQQ, massimo di 55 sedute, long | 2,9 | +0,55 | 2,4 | +0,49 (2,0) | +0,85 (1,4; 11) | +0,53 | +0,61 |
| Tendenza oro (GLD) 55 sedute, long | 3,2 | +0,59 | 2,1 | +0,49 (1,8) | +0,90 (1,1; 16) | +0,56 | +0,49 |
| Tendenza obbligazioni (TLT), long e short | 3–5 | ≈0 / −0,15 | — | +0,17 / −0,13 | −0,69 / −0,22 | — | — |
| Tendenza short su SPY/QQQ/GLD | 2–4 | −0,3/−0,4 | −3/−4 | negativo | negativo | — | — |
| Notte (chiusura→apertura) SPY/QQQ/IWM | 252 | −0,02/0,00/−0,01 | −3,5 | negativo | negativo | peggio | — |
| Giorno (apertura→chiusura) | 252 | −0,04 | −5,4 | negativo | negativo | — | — |
| Gap fade (gap > 0,5 o 1 ATR, contro) | 2–24 | −0,06…+0,12 | <1,6 | nessuno sopra t 2 | ≈0 | — | negativo |
| Settimana delle scadenze long / settimana dopo short | 12 | +0,05 / −0,07…−0,12 | 1,4 / −3,0 | — | 0,00 / −0,16 | — | — |
| GEX<0 → momentum a 1 giorno | 7–17 | −0,06 / −0,01 | −1,4 | negativo | ≈0 | — | — |
| FX: inversione a 3 giorni; tendenza 20/55 | 2–19 | −0,05…+0,14 | <1 | nessuno | nessuno | — | — |
| VIX: ritorno in contango → long 5 g | 6 | +0,13 | 1,7 | +0,12 (1,6) | +0,19 (0,7) | +0,12 | +0,15 |

Letture (FATTO):
- **L'unico vantaggio robusto e' il ritorno alla media dopo una chiusura debole, e sta tutto nei giorni con VIX ≥ 20.** Con VIX < 20 e' zero o negativo su tutti e tre gli indici, in scelta e in verifica.
- **GEX**: il terzile basso di GEX migliora l'IBS in scelta (+0,19 contro 0,00 nel terzile alto su SPY) ma in verifica non regge (+0,01, n 53). Dice la stessa cosa del VIX ≥ 20, con meno storia. Non lo uso.
- **Struttura a termine del VIX**: in backwardation l'R e' piu' alto (+0,13) ma i trade sono 9 l'anno e t < 1,6; in contango resta +0,10 su SPY. Filtro piu' debole del livello del VIX.
- **Notte contro giorno**: lordo, il rendimento sta nella notte; netto di 4 bp di giro e del finanziamento, **entrambi sono negativi**. Non e' un trade.
- Pre-FOMC e cambio del mese: significativi fino al 2022, quasi nulli dal 2023 (decadimento noto in letteratura).
- Gap, opex, FX, obbligazioni, GEX-momentum: niente.

## Il flusso A5 (regole fissate sulla scelta: t_scelta ≥ 2, positivo a costi doppi e con ritardo)
1. **MR**: chiusura con IBS < 0,2 e VIX ≥ 20 → long all'apertura dopo su SPY, QQQ, IWM; stop 1 ATR (≈ 1,3%, leva ≈ 18–20x); uscita all'apertura dopo la prima chiusura con IBS > 0,7 o dopo 5 sedute. Indici entrati lo stesso giorno = **un solo trade** a rischio diviso.
2. **TOM**: long alla chiusura dell'ultimo giorno di borsa del mese (SPY, QQQ), uscita alla chiusura del terzo giorno; stop 2 ATR.
3. **FOMC**: long alla chiusura della vigilia (SPY, QQQ), uscita alla chiusura del giorno dell'annuncio; stop 1 ATR.
4. **TREND**: QQQ sopra il massimo di 55 sedute → long; stop 2 ATR, inseguimento a 3 ATR dalla miglior chiusura.

| | N | N/anno | R̄ | σ_R | t | vincenti | R̄/σ | N·(R̄/σ)² |
|---|---|---|---|---|---|---|---|---|
| Intero 1994–2026 | 1.710 | 52 | +0,130 | 0,94 | 5,7 | 56% | 0,138 | **0,99** |
| Scelta ≤ 2022 | 1.560 | 54 | +0,125 | 0,94 | 5,3 | | 0,134 | 0,97 |
| Verifica ≥ 2023 | 150 | 39 | +0,181 | 1,05 | 2,1 | | 0,172 | 1,15 |
| Costi ×2 / un giorno di ritardo | | | +0,108 / +0,082 | | | | | |

Per componente (scelta → verifica): MR +0,10 → **+0,26** (t 1,8); TOM +0,11 → +0,06; FOMC +0,13 → **−0,03**; TREND +0,50 → +0,86 (11 trade).
Per periodo: 1994–2002 +0,09 (t 2,4); 2003–2012 +0,17 (4,4); 2013–2022 +0,11 (2,5); 2023–2026 +0,18 (2,1). Anni negativi: 1994, 2001 (−14,5 R), 2002, 2014, 2018 (−8,9 R). Caduta massima −26,9 R (2000–2002); in verifica −7,6 R.
A rischio 1% per trade: mese medio +0,54%, deviazione 2,1%, Sharpe annuo 0,89, mesi negativi 33%, mese peggiore −8,0%.

## Seconda derivazione sul percorso infragiornaliero (FATTO, `03_percorso.out`)
- S&P 500 a 1 minuto quasi 24 ore, 2011–2018, regola MR riscritta da zero: solo seduta regolare +0,151; **24 ore con stop notturni +0,170**; ingresso 5 minuti dopo +0,160; motore giornaliero sulle stesse barre +0,149; SPY Yahoo +0,164 (n ≈ 95, t ≈ 1,3). Lo stop notturno non peggiora il risultato filtrato. Senza filtro VIX lo peggiora (+0,095 → +0,066).
- Barre orarie 2023-12 → 2026-11, 3 indici: percorso orario +0,307 contro giornaliero +0,309 (86 trade, correlazione 0,999).
- Troncamento: 2.400 confronti, 0 differenze.
- Decisione alle 15:30 con ingresso in chiusura: +0,63 R, 78% vincenti su 40 trade → per la regola del brief lo tratto come artefatto di campione piccolo (senza filtro: +0,10, 57%, n 332). **Non usato.**
- Difetto trovato: `gerva.data.sources.histdata_m1` sposta di +1 ora le barre estive (la sorgente e' gia' in ora di New York). Corretto solo nel mio script.

## Che cosa aggiunge al fondo (aritmetica del brief)
Finestra comune 2018-04 → 2026-10; libro cripto = stop 1×ATR, 11x.
| | N/anno | R̄/σ | N·(R̄/σ)² | Sharpe² annuo da P&L mensili |
|---|---|---|---|---|
| Cripto (intero / scelta / verifica) | 76 / 60 / 96 | 0,136 / 0,176 / 0,104 | 1,40 / 1,86 / 1,04 | 0,90 / 1,15 / 0,78 |
| A5 | 52 / 63 / 39 | 0,156 / 0,146 / 0,174 | 1,26 / 1,33 / 1,17 | 1,20 / 1,49 / 0,87 |
| Insieme, libro unico a rischio uguale | 128 / 123 / 134 | 0,137 / 0,158 / 0,116 | 2,41 / 3,07 / 1,81 | |
| Insieme, somma dei due flussi (Kelly separato) | | | **2,66 / 3,18 / 2,21** | **1,86 / 2,14 / 1,56** (combinazione ottima) |

- Correlazione dei P&L mensili A5–cripto (`trade11`): **+0,13** intero, +0,24 scelta, +0,06 verifica. A5–libro giornaliero (`new`): **+0,39** intero, +0,47 scelta, +0,30 verifica.
- Leva mossa: **ΔN ≈ +52 trade l'anno** quasi indipendenti dalle cripto, con R̄/σ ≈ 0,14–0,17, uguale a quello cripto. N·(R̄/σ)² passa da **1,4 a 2,4–2,7** (verifica: da 1,0 a 1,8–2,2). L'obiettivo ne chiede 6,3.
- STIMA: sul P&L mensile (che conta i grappoli di trade) il quadrato dello Sharpe sale da 0,90 a 1,86: crescita logaritmica a Kelly pieno da 0,45 a 0,93 l'anno, cioe' da ≈ 3,8% a ≈ 8% al mese **a Kelly pieno**; a mezzo Kelly ≈ 6% al mese; in verifica ≈ 5%. Kelly pieno su A5 vuol dire rischiare ≈ 15% del conto per trade (nozionale ≈ 12 volte il conto): con il 2001 a −14,5 R il conto sarebbe azzerato. A un rischio sostenibile dell'1–2% per trade A5 aggiunge **0,5–1,1% al mese**.

## Che cosa non ha funzionato
Notte/giorno, gap fade, settimana delle scadenze, FX (inversione e tendenza), tendenza sulle obbligazioni, short di ogni tipo sugli indici, GEX come regime di momentum, GEX e struttura a termine del VIX come filtri (non meglio del VIX ≥ 20), IBS con VIX < 20, IBS su IWM senza filtro.

## Conteggio prove
**157 varianti**: 144 in `01_setups.py`, 10 in `03_percorso.py`, 1 composizione del flusso, 2 controlli della variante 15:30. Con 144 prove il t massimo atteso per puro caso e' ≈ 2,6: MR (t_scelta 3,3) lo supera di poco; TOM (3,0), FOMC (2,8) e TREND (2,0) sono al livello del rumore e in verifica TOM e FOMC sono di fatto spariti.

## Di che cosa non sono sicuro
- **Non e' del tutto nuovo**: il libro giornaliero contiene gia' la sleeve EQ-MR (IBS). La correlazione +0,39 con `new` dice che una parte di A5 e' la stessa scommessa con piu' leva. Il contributo netto al fondo intero e' minore di quello calcolato contro il solo libro cripto.
- Il filtro VIX ≥ 20 l'ho trovato dividendo il campione (8 filtri provati, sulla scelta). Regge in verifica su 3 indici su 3, ma con 40 trade per indice.
- La verifica di MR pesa sul 2025 (+10 R su 16 totali dal 2023). TREND in verifica ha 11 trade.
- ETF come sostituto del CFD/future: base, orari e scarto reali non misurati; il percorso notturno e' verificato solo 2011–2018 e solo per l'S&P 500. Finanziamento CFD stimato (tasso + 1,5%); con i micro future costerebbe meno. IPOTESI: esecuzione all'apertura senza scarto oltre i 2–3 bp.
- Massimi/minimi giornalieri Yahoo per l'FX non sono affidabili: il "niente" sull'FX vale per questi dati.
- Oro: la tendenza long non passa la soglia in scelta (t 1,84) e resta fuori dal flusso; in verifica +0,90 R su 16 trade. Serie in `returns.parquet` come "fuori soglia".
