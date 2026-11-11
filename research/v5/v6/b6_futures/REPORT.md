# B6 — Future diversificati ad alta leva (cassetta degli attrezzi CTA) — tutto SIMULATO

Dati reali Yahoo (future continui `=F` 2000-09 → 2026-11, indici, ETF di controllo) e FRED (tassi). Nulla è stato negoziato.
Selezione ≤ 2022-12-31, verifica ≥ 2023-01-01. Script: `00_dati.py`, `01_rolls.py`, `02_trend.py`, `03_altre.py`,
`04_breakout.py`, `05_portafoglio.py`, `06_diagnosi.py` (+ `lib.py`, `engine.py`), ognuno col suo `.out`.

## 1. Come ho trattato i salti di roll (FATTO, verificato)
- FATTO: le serie `=F` di Yahoo tengono il contratto in scadenza fino all'ultimo giorno (LTD); il volume salta il giorno
  dell'LTD e il **prezzo cambia contratto il giorno dopo** (studio a evento: salto notturno mediano 50–640 bp contro 4–45 normali).
- Metodo A (26 mercati: tassi, energia, cereali, coloniali, carni, cripto): calendario LTD per mercato; nel giorno di roll il
  rendimento è apertura→chiusura del nuovo contratto (si perde una notte, il salto sparisce). Dove Yahoo cambia in giorni non
  costanti (cereali, coloniali, ZF/ZT) il giorno è cercato in una finestra attorno alla regola (salto > 3× il normale).
- Metodo B (FX, oro, argento, rame): le date non sono rilevabili (contratti mensili illiquidi) → grezzo ≈ spot, eccesso =
  grezzo + carry da tassi a 3 mesi (STIMA). Azionario USA: ETF total return − T-bill (esatto); N225/DAX/STOXX: indice ± dividendi − tasso (STIMA).
- Controllo contro ETF (rend. in eccesso annuo): ZN 1,65% vs IEF 1,67%; ZF 1,16 vs IEI 1,22; GC 9,9 vs GLD 9,5; SI 10,9 vs SLV 10,0;
  FX entro 0,5–1,3 punti dagli ETF valutari (che pagano commissioni). Il metodo A sugli indici azionari sbaglia di +1%/anno
  (la barra del terzo venerdì è il prezzo di regolamento): per questo lì uso gli ETF.
- Quanto conta: grezzo − ripulito = +4,8%/anno energia, +4,9 coloniali, +10,2 cripto, −1,3 tassi. Il trend sulle serie grezze
  ha Sharpe 0,29 invece di 0,47 (2010-19: 0,07 invece di 0,36): chi usa i dati grezzi sbaglia segnale e risultato.
- Limiti (STIMA): contratto tenuto fino a scadenza (un operatore reale rolla prima); coloniali con barre illiquide nel mese di
  consegna (es. cotone 2022-06-24 non corretto); carni con autocorrelazione spuria vicino alla scadenza (HE 0,21 contro 0,03):
  il trend "solo carni" Sharpe 0,90 è in parte un artefatto. Esclusi BZ, DX, PL, PA (dati non affidabili o doppioni).

## 2. Costi dei micro in bp del nozionale per lato (commissione tutto compreso + 1 tick), prezzi di oggi
| Mercato | bp | Mercato | bp | Mercato | bp |
|---|---|---|---|---|---|
| MES 0,5 · MNQ 0,2 · MYM 0,4 · M2K 0,8 | | Micro Nikkei 1,0 · FDXS 0,6 · FSXE 1,6 | | Micro yield 2Y 0,3 · 5Y 0,7 · 10Y 1,0 · 30Y 1,7 | |
| M6E 1,2 · M6B 1,2 · MSF 1,1 | | MJY 2,1 · M6A 2,1 · MCD 2,0 | | MGC 0,4 · SIL 1,2 · MHG 1,4 | |
| MCL 2,1 · MHO 0,7 · MRB 1,1 · **MNG 5,4** | | **MZC 14,9 · MZW 11,3 · MZM 8,7** · MZS 5,5 · MZL 5,4 | | MBT 4,7 · **MET 26,7** | |
Coloniali e carni esistono solo interi (KC 102k$, LE 88k$, CC 47k$, CT 39k$): 1,5–6,8 bp ma non dimensionabili sotto ~250k€.
Costo totale del libro trend a vol 10%: 1,6%/anno (di cui roll mensile dei micro-yield e cereali micro la parte maggiore);
costi ×2 tolgono 0,15 di Sharpe, ×4 lo azzerano. I micro NON sono "a costo quasi zero" per un sistema che ribilancia ogni giorno.

## 3. Risultati (Sharpe netto; vol obiettivo 10%; decisione alla chiusura t, esecuzione alla chiusura t+1)
| Strategia (37 mercati) | tutto | 2001-09 | 2010-19 | 2020-26 | selez. | verif. | CAGR | MaxDD | skew m. |
|---|---|---|---|---|---|---|---|---|---|
| TSMOM 1 mese / 3 mesi / 12 mesi | 0,08 / 0,25 / 0,72 | 0,38 / 0,44 / 1,04 | −0,40 / 0,40 / 0,42 | 0,38 / −0,20 / 0,72 | 0,13 / 0,45 / 0,80 | −0,23 / −0,89 / 0,28 | 0,3 / 2,1 / 7,3% | −49 / −39 / −25% | 0,2–0,3 |
| EWMAC 8-32 / 16-64 / 32-128 / 64-256 | 0,31 / 0,41 / 0,44 / 0,48 | 0,41–0,77 | 0,14–0,30 | 0,31–0,43 | 0,40–0,59 | −0,46…−0,11 | 2,8–4,5% | −24…−29% | 0,3–0,8 |
| Donchian 20 / 55 / 120 / 250 | 0,13 / 0,27 / 0,40 / 0,64 | 0,30–1,05 | −0,31–0,47 | 0,00–0,53 | 0,14–0,76 | −0,80…0,07 | 0,8–6,4% | −29…−46% | 0,1–0,5 |
| **TREND_TUTTI** (media delle 12, fissata a priori) | **0,47** (lordo 0,62) | 0,65 | 0,36 | 0,40 | 0,63 | **−0,41** | 4,5% | −25% | +0,61 |
| TREND_TUTTI costi ×2 / ritardo +1 barra | 0,32 / 0,42 | 0,52 / 0,65 | 0,20 / 0,26 | 0,24 / 0,38 | 0,48 / 0,57 | −0,60 / −0,43 | 2,9 / 4,0% | −29 / −27% | 0,6 |
| TREND_TUTTI **solo 31 micro** | 0,30 | 0,49 | 0,21 | 0,19 | 0,49 | **−0,79** | 2,6% | −34% | +0,53 |
| Carry TS / XS (STIMA: salto di roll, tassi) | −0,16 / −0,08 | −0,16 / 0,33 | 0,44 / −0,20 | −1,01 / −0,44 | −0,11 / −0,02 | −0,39 / −0,44 | −2,1 / −1,4% | −65 / −57% | ≈0 |
| IBS<0,2 lungo, 4 indici USA, ordine in chiusura (IPOTESI 15:50) | 0,71 | 0,90 | 0,49 | 0,82 | 0,67 | 0,96 | 7,9% | −28% | 0,0 |
| IBS<0,2 lungo, 7 indici, chiusura successiva | 0,42 | 0,38 | 0,36 | 0,56 | 0,34 | 0,88 | 4,2% | −31% | −0,6 |
| Risk parity solo lungo (pari rischio per 7 settori) | 0,67 | 1,16 | 0,37 | 0,50 | 0,69 | 0,56 | 6,7% | −32% | 0,0 |
| RP + trend 50/50 | 0,73 | 1,11 | 0,52 | 0,55 | 0,84 | 0,14 | 7,3% | −23% | +0,4 |
| Stagionalità materie prime (stesso mese, 5/10/30 anni, TS e XS) | −0,68…0,03 | 0,44–0,58 | −0,85…−0,32 | −1,34…0,23 | −0,53…−0,02 | −1,41…0,25 | <0 | −48…−88% | — |
| **C4 = trend + RP + IBS, 1/3 ciascuno, 31 micro** | **0,91** | 1,49 | 0,62 | 0,62 | 1,04 | **0,21** | 9,5% | −20% | +0,15 |
| C4 costi ×2 / ritardo +1 / entrambi | 0,74 / 0,73 / 0,57 | 1,35 / 1,18 / 1,04 | 0,43 / 0,39 / 0,22 | 0,46 / 0,67 / 0,50 | 0,88 / 0,83 / 0,67 | 0,03 / 0,15 / −0,04 | 7,6 / 7,5 / 5,6% | −21 / −33 / −38% | 0,2 |

Trend per anno (37 mercati, vol 10%): 2008 +21,9; 2010 +12,5; 2014 +9,0; 2015 −5,0; 2016 −7,2; 2020 +32,2 (tassi +10, BTC +7, metalli +5);
2022 +17,6; **2023 −12,6; 2024 −1,1; 2025 −2,3; 2026 −2,7**. Il priore è confermato: Sharpe lordo 0,6, netto ≈0,5, debole 2010-19, negativo dal 2023.
Solo il lato lungo guadagna (Sharpe 0,69; lato corto −0,14). Controllo di troncamento: pesi identici (corr 0,99999, stessi segni) a tre date.

### Breakout stile Turtle come flusso di operazioni in R (stop 2 ATR, 37 mercati, 2000-2026, netto)
| Sistema | n/anno | R̄ | σ_R | t | vincenti | R̄ selez. | R̄ verif. | N·(R̄/σ)² | Sharpe dell'R mensile |
|---|---|---|---|---|---|---|---|---|---|
| S1 20/10 | 408 | +0,04 | 1,67 | 2,6 | 36% | +0,05 | +0,02 | 0,26 | 0,34 |
| S2 55/20 | 198 | +0,13 | 2,56 | 3,5 | 31% | +0,15 | **−0,03** | 0,47 | 0,46 |
| 120/40 | 108 | +0,30 | 4,16 | 3,8 | 25% | +0,41 | **−0,26** | 0,55 | 0,59 |
| 250/60 | 69 | +0,35 | 4,47 | 3,3 | 24% | +0,40 | +0,08 | 0,42 | 0,55 |
| S2 costi ×2 / ritardo +1 / stop 1N / stop 3N | 198 / 197 / 324 / 174 | 0,10 / 0,13 / −0,08 / 0,11 | | 2,8 / 3,6 / −1,9 / 3,9 | | | −0,05 / −0,02 / −0,26 / 0,01 | 0,30 / 0,51 / 0,13 / 0,58 | |
Mediana −1,0 R; senza le 50 operazioni migliori su 5.187 la media è −0,04 R: tutto il guadagno sta nell'1% delle operazioni.
Le operazioni simultanee non sono indipendenti: la misura giusta è lo Sharpe dell'R mensile (≈0,5), cioè N·(R̄/σ)² effettivo ≈ 0,25.
Distanza media dello stop 3,5% → leva teorica per operazione ≈ 19x, ma è lo stesso trend della tabella sopra, non un vantaggio in più.

## 4. Scommesse indipendenti, conto minimo, leva
- Rapporto di partecipazione (rendimenti settimanali): 37 mercati → **10,4 scommesse effettive** (9,4–11,5 per decennio);
  31 micro → 8,8. Sui flussi di P&L del trend: 17,5 (14,8 sui micro). Trentasette mercati non sono trentasette scommesse.
- Rischio annuo di UN contratto in % di 10.000 €: MES 43%, MNQ 97%, MGC 99%, SIL 282%, MCL 40%, MBT 29%, M2K 23%;
  sotto il 10% solo micro-yield (6%), micro FX (3–10%), cereali micro (4–9%), FSXE (10%), MET (1%).
- Trend su 31 micro con contratti interi (Sharpe ideale 0,34 dal 2001-06):

| Conto | vol 15% | vol 25% | vol 40% | mercati tenuti in media (15/25/40%) | margine p99 (25% / 40%) |
|---|---|---|---|---|---|
| 10k € | **−0,22** | **0,08** | 0,17 (MaxDD −78%) | 0,9 / 2,7 / 5,6 | 29% / 58% |
| 25k € | 0,15 | 0,10 | 0,22 | 5 / 9 / 13 | 45% / 89% |
| 50k € | 0,09 | 0,39 | 0,30 | 10 / 14 / 18 | 56% / 99% |
| 100k € | 0,36 | 0,38 | 0,34 | 16 / 19 / 22 | 61% / 95% |
| 250k € | 0,35 | 0,36 | 0,38 | 22 / 24 / 26 | 60% / 96% |

  Con 10k € a vol 25% nessun indice azionario, metallo, energia o BTC è mai dimensionabile; restano micro-yield, MCD/MJY/M6A, MZC/MZM, MET.
  Sottoinsieme di 15 micro "piccoli" (scelto per rischio per contratto): 10k € → Sharpe 0,24 a vol 25% (4 mercati tenuti, MaxDD −72%),
  0,14 a vol 40% (MaxDD −95%). **Conto minimo perché il libro sia quello ideale: ≈50k € a vol 25%, ≈100k € a vol 15%** (STIMA: nozionali di oggi).
- Vincolo di margine: a vol 40% il margine p99 è ≈100% del capitale, a vol 60% è 150% → **il tetto pratico è vol ≈25–30%** (leva lorda ≈7x).

## 5. Volatilità ottimale per la crescita e ritorno mensile composto (bootstrap a blocchi di 3 mesi, 36 mesi, 20.000 percorsi)
| Libro, scenario | vol ottimale | mese composto | MaxDD storico | P(drawdown −50%) | P(−50% dal capitale) | a metà leva: mese / P(dd −50%) |
|---|---|---|---|---|---|---|
| Trend 31 micro, base | 29% | **+0,37%** | −71% | 20% | 10% | +0,27% / 0,2% |
| Trend 31 micro, metà vantaggio | 16% | +0,09% | −52% | 1% | 0,7% | +0,07% / 0% |
| C4, base (campione intero) | 85% (non finanziabile) | +3,35% | −88% | 88% | 36% | **+2,5% a vol 42% / 18%** |
| C4, metà vantaggio | 45% | **+0,85%** | −82% | 46% | 21% | +0,64% a vol 23% / 3% |
| C4, solo verifica 2023-26 | 22% | +0,18% | −30% | — | — | +0,14% |
C4 a obiettivi fissi (base → metà vantaggio): vol 15%: +1,05%/mese, P(dd −50%) 0% → 0,1%; vol 25%: +1,64%, 0,9% → 5,5%;
vol 40%: +2,38%, 14% → 34%; vol 60%: +3,05%, 53% → 76% (e margine insufficiente).

## 6. Correlazione col fondo esistente (2018-04 → 2026-10)
Mensile con `B_cassa_in_tbill` / `C1_mtm_limiti` / `C3_mtm_limiti_debito_reale`: trend micro 0,30 / 0,30 / 0,31; C4 0,55 / 0,45 / 0,45;
RP 0,58 / 0,48 / 0,48; IBS 0,15 / 0,03 / 0,03. Sharpe nello stesso periodo: fondo C1 1,43, trend micro 0,29, C4 0,52.
Aggiungere B6 al fondo a pari volatilità **abbassa** lo Sharpe: 20% di C4 → 1,39 (verifica 1,20 contro 1,28); 20% di trend → 1,39 (verifica 1,04).

## 7. Candidato migliore e risposte richieste
- Regola esatta (C4, 31 micro): per ogni mercato peso = segnale × quota di rischio (pari per 7 settori, pari dentro il settore) × 10% / vol EWMA 60g;
  tre gambe a pari rischio: (i) media di 12 segnali di trend (TSMOM 21/63/252, EWMAC 4…64, Donchian 20…250); (ii) lungo fisso;
  (iii) lungo MES/MNQ/MYM/M2K quando IBS<0,2, un giorno; scala finale alla volatilità obiettivo.
- Chi paga: trend → coperture commerciali e capitale lento (sottoreazione); RP → premi al rischio (è beta, non vantaggio);
  IBS → chi vende in chiusura per necessità. Capienza: ampia sui micro CME (limite vero: cereali micro e MET, pochi contratti al giorno).
- Sede: IBKR Irlanda, micro CME/CBOT/NYMEX/COMEX + Eurex FDXS/FSXE (leva di margine 10–50x per mercato).
- Sharpe / CAGR a vol 10%: tutto 0,91 / 9,5%; selezione 1,04 / 11,0%; verifica **0,21 / 1,7%**. MaxDD −20% (−38% con costi ×2 e ritardo).
- Evento che lo uccide: inversione simultanea di tassi e azioni con trend fermo (2022 per la gamba RP, 2023 per il trend) a vol >40%;
  salti notturni su contratti interi non dimensionabili; chiamata di margine a vol ≥40%.
- Leve dell'aritmetica: ΔN ≈ +9 scommesse effettive, ma R̄/σ per scommessa ≈ 0,05 → N·(R̄/σ)² ≈ 0,25–0,8 contro 6,3 richiesto.

## 8. Cosa è fallito
Carry (misurabile solo come STIMA: negativo, −1,0 nel 2020-26); stagionalità delle materie prime (tutte le 6 varianti ≤ 0 in selezione);
trend veloci (1 mese, Donchian 20, EWMAC 4-16: ≤ 0,15); lato corto del trend; FX e cereali come trend autonomi (0,06 e −0,33);
stop a 1 ATR (−0,08 R); qualunque libro diversificato su 10k €.

## 9. Conteggio delle prove e dubbi
- **134 varianti** contate (16 trend + 36 robustezze/settori/vol; 24 altre famiglie; 12 breakout; 11 libri combinati; 30 griglia conto×vol; 5 diagnosi).
  Regole candidate alla selezione: 60. Il trend da solo (t ≈ 2,3 in selezione) non supera la soglia per 60 prove (≈ 2,9).
- IPOTESI: nozionali e commissioni di oggi applicati a tutta la storia (i micro esistono dal 2019-2025); micro-yield usati al posto di ZT/ZF/ZN/ZB
  (seguono il rendimento, non il future); un tick di scivolamento sui cereali micro è ottimista.
- STIMA: rendimenti di coloniali, carni, rame e FX (carry da tassi interbancari); il +32% del 2020 dipende da ZT a volatilità minima (leva alta) e da BTC.
- Il risultato di C4 nel 2001-09 (Sharpe 1,49; +35/+40% nel 2002-03) viene da IBS e risk parity in un decennio irripetibile; in verifica resta 0,21.
- I rendimenti sono in eccesso (senza interessi sulla cassa); `returns.parquet` è a vol 10% (leva lorda ≈2,9x), indice di calendario.
