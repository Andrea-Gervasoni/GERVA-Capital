# B5 — Azioni singole (S&P 500 + Nasdaq-100): sezione trasversale. Tutto SIMULATO

Script: `00_universo` → `10_sintesi` (+ `.out`), motore in `lab.py`. Dati: OHLCV giornaliero Yahoo 2003 → 2026-10 (cache `v6_b5_*`),
selezione ≤ 2022-12-31, verifica ≥ 2023-01-01. **188 varianti provate.** Nulla ha mai operato.

## 1. Universo e sopravvivenza (FATTO)
- Componenti di oggi + tabelle storiche di ingressi/uscite di Wikipedia («Historical components of the S&P 500» 415 righe,
  «…Nasdaq-100» 229 righe), invertite all'indietro; per i membri attuali la data d'ingresso esatta («Date added»).
- 952 ticker nelle tabelle; **Yahoo ne restituisce 701** (722 con ETF). Dei 592 intervalli chiusi (titoli usciti) solo 290 hanno
  prezzi: i 244 mancanti sono 404 «delisted» (acquisiti o falliti). La tabella S&P è inoltre incompleta prima del 2015.
- Copertura dei membri veri con prezzi: **51% nel 2005, 64% nel 2010, 75% nel 2015, 85% nel 2018, 93% nel 2022, 96–99% dal 2023.**
  La verifica (2023+) è quasi pulita; la selezione no.
- Misura del bias: equipesato dei membri point-in-time (PIT) 14.9%/anno nel 2005–14 contro 17.8% dei soli membri di oggi (SPY 9.4%).
  Sui long il bias residuo è grande: momentum 12-1 long Sharpe 0.63 (PIT) contro 0.91 (solo membri di oggi); inversione 5 giorni long
  CAGR 17% contro 24.5%. Sui long-short quasi si annulla (differenze ≤ 0.2 di Sharpe, segno alterno). Ogni tabella sotto usa PIT;
  il bias vero rimasto è una frazione di quel divario (manca ancora il 7–49% dei nomi) e va nella stessa direzione: **i long sono sovrastimati**.
- Settori: GICS per i membri attuali; per gli altri il settore il cui indice equipesato è più correlato (classificazione di comodo).
- Utili: date e sorprese **non recuperabili** da Yahoo da qui (crumb/quoteSummary «Too Many Requests», `events=earn` vuoto) → proxy di solo prezzo.

## 2. Costi modellati (FATTO le regole, STIMA gli spread)
IBKR tiered USA: 0.0035 $/azione + ~0.003 $ di fee di borsa, **minimo 0.35 $ per ordine**, massimo 1%; calcolata sul prezzo reale
storico (ricostruito dagli split: la chiusura Yahoo è rettificata). Mezzo spread 2 / 3.5 / 5 bp per terzile di liquidità. Prestito
titoli 1%/anno, debito a T-bill + 1.5%, la cassa non rende. Esecuzione: segnale alla chiusura di t, ordine all'apertura di t+1.
Conto da 10k € = 11 500 $: ogni ordine costa almeno 0.30 bp del capitale, cioè 3 bp su una posizione da 1/20 a 1x.

## 3. Risultati per strategia (conto grande, netto; Sharpe pieno / selezione / verifica)
| Strategia (regola) | LS Sharpe | LS CAGR | LO Sharpe | LO attivo vs EW | Max DD (LS) | Rotazione/anno | Lordo LS | 10k € LS |
|---|---|---|---|---|---|---|---|---|
| Inversione 1g, settore-neutrale, 20+20, tenuta 1g | −1.53 / −1.80 / −0.64 | −31% | −0.13 | −1.06 | −100% | 900x | Sharpe 0.64 | −3.15 |
| Inversione 5g, 20+20, tenuta 5g | 0.21 / 0.36 / −0.34 | 2.3% | 0.68 | 0.43 / 0.53 / 0.04 | −56% | 183x | 0.80 | −2.34 |
| IBS estremo, 20+20, tenuta 1g | −3.34 / −3.39 / −3.12 | −37% | −0.46 | −2.49 | −100% | 940x | 0.21 (MOC 1.58) | −6.43 |
| RSI-2 ordinato, 20+20, tenuta 5g | 0.33 / 0.51 / −0.43 | 2.9% | 0.75 | 0.21 | −39% | 186x | 1.33 | −4.55 |
| RSI-2 < 5 sopra SMA200, esce > SMA5 | 0.31 / 0.40 / −0.12 | 3.9% | 0.65 | −0.34 | −49% | 164x | 0.80 | −1.31 |
| Momentum 12-1, 20+20, mensile | −0.07 / −0.17 / 0.32 | −8.6% | 0.62 | 0.21 / 0.15 / 0.38 | −97% | 15x | −0.02 | −0.09 |
| Momentum residuo 12-1 | 0.10 / −0.03 / 0.57 | −1.1% | 0.68 | 0.16 | −78% | 18x | 0.17 | 0.07 |
| Momentum 6-1 / 3-1 / 1 mese | −0.09 / −0.27 / −0.21 | −8…−11% | 0.56–0.68 | ≤ 0.28 | > −90% | 22–43x | < 0 | — |
| Vicinanza al massimo 52 sett. | −0.50 / −0.49 / −0.59 | −21% | 0.59 | −0.37 | −99% | 26x | −0.44 | −0.54 |
| Breakout 52 sett. + volume 1.5x, 60g (solo long) | — | — | 0.76 / 0.72 / 1.00 | −0.12 | −34% (LO) | 13x | — | — |
| Deriva post-annuncio, proxy gap+volume, 20g | −0.17 / −0.24 / 0.12 | −2.8% | 0.48 | −0.51 | −59% | 43x | 0.06 | −1.34 |
| Bassa volatilità 252g, 20 titoli (LO) | −0.56 (LS) | −26% | 0.76 / 0.78 / 0.61 | −0.27 | −33% (LO) | 3x | — | — |
| Bassa vol/beta a leva 2x (LO, 50 titoli) | — | 14.8–16.4% | 0.64–0.69 | — | −62…−67% | 4x | — | — |
| Coppie nel settore (Gatev, 5 per settore, 2σ) | 0.36 / 0.40 / 0.13 | 1.3% | — | — | −7.8% | 10x | 0.64 | −0.05 |
| **Notte: 5 titoli con notte media 252g più alta, prezzo > 30 $, asta chiusura → asta apertura** | (solo long) | — | **1.29 / 1.42 / 1.04** | vedi §5 | −34% | 504x | 1.47 | 1.12 (LO) |

Riferimenti nello stesso periodo: SPY Sharpe 0.64 (0.52 / 1.36), equipesato PIT 0.70. Il «LO attivo» è long meno equipesato.
Costi ×2, ritardo di una barra ed esecuzione MOC sono in ogni `.out`: nessuna riga della tabella cambia segno in meglio.

## 4. I priori accademici: confermati (FATTO su questi dati)
- **Inversione di breve**: alfa lordo reale e in decadimento. Inversione 5g LS lordo: 33.7%/anno (2005–09) → 12.6% (2010–14) → 10.1%
  (2015–19) → 16.4% (2020–22) → **0.8% (2023–26)**. RSI-2 lordo: Sharpe 1.57 → 1.73 → 1.39 → 0.63 → 0.53. Netto è ≤ 0 dal 2010
  anche con conto grande; a 1 giorno i costi (49%/anno) sono 4–8 volte l'alfa. Metà dell'effetto è nella notte successiva al segnale
  (IBS: lordo 0.21 all'apertura, 1.58 in chiusura), cioè non è catturabile senza conoscere la chiusura prima della chiusura.
- **Deriva post-annuncio**: sul proxy (|rendimento netto mercato| ≥ 3σ e ≥ 4%, gap ≥ 2% concorde, volume ≥ 2×; 216 + 238 eventi/anno,
  concentrati in gen-feb, apr-mag, lug-ago, ott-nov, quindi il proxy coglie gli utili) la deriva a 20–60 giorni sulle large cap è zero:
  LS lordo Sharpe 0.04–0.06. Il lato negativo anzi rimbalza (+1.4% a 60g nel 2005–10) e solo dal 2023 continua a scendere (−0.7%).
- **Momentum** large cap 2005–2026: LS ≈ 0 o negativo (crollo 2009), come in letteratura dopo il 2000. **Bassa volatilità**: Sharpe
  0.76 contro 0.70 dell'equipesato, differenza dentro il bias di sopravvivenza; a leva 2x il finanziamento la peggiora.
- **Flussi di trade in R con stop ad ATR** (CFD 5x; `06_trade_R.out`): tutti i long hanno R > 0 (da +0.007 a +0.15) ma un **placebo
  con titoli a caso, stesse date, stesso stop** dà lo stesso R: alfa −0.014…+0.028 R, t ≤ 1.8. Tutti gli short sono negativi
  (−0.025…−0.10 R). N·(R̄/σ_R)² dei long: 0.06–0.9, ed è beta di mercato. Nessuna leva della contabilità (ΔN, ΔR̄/σ_R) si muove.

## 5. Il candidato: persistenza del rendimento notturno (FATTO i numeri, IPOTESI l'eseguibilità)
Regola esatta: ogni giorno, prima della chiusura, tra i membri PIT con prezzo reale > 30 $ si prendono i 5 titoli con il rendimento
notturno medio (chiusura → apertura) più alto negli ultimi 252 giorni; si comprano in asta di chiusura (MOC) e si vendono in asta di
apertura (MOO) del giorno dopo. Di giorno il conto è in cassa. Scelta su selezione dentro una griglia di 32 (LB 20–252, K 5–50, filtro prezzo).
| Versione | Sharpe pieno / sel / ver | CAGR | Max DD | Mese composto |
|---|---|---|---|---|
| Conto grande, 1x, solo commissione | 1.29 / 1.42 / 1.04 | 30.3% | −34% | 2.2% |
| Costi ×2 | 1.11 / 1.18 / 1.00 | 25.1% | −39% | |
| +1 bp per lato di scarto dal prezzo d'asta | 1.07 / 1.16 / 0.89 | 23.9% | −42% | |
| +3 bp per lato | 0.62 / 0.65 / 0.58 | 12.0% | −55% | |
| Ordini a mercato (mezzo spread) invece dell'asta | 0.76 / 0.81 / 0.69 | 15.7% | −52% | |
| Segnale in ritardo di 1 / 5 giorni | 1.26 / 1.31 | 29–31% | −31% | |
| 10k €, azioni 1x | 1.12 / 1.25 / 0.86 | 25.4% | −41% | 1.9% |
| 10k €, azioni a margine 2x | 1.13 / 1.27 / 0.84 | 50.2% | −67.5% | 3.45% |
| Dal 2018 (copertura universo ≥ 85%) | 0.93 | 24.8% | −34% | |
| Solo membri di oggi (bias di sopravvivenza pieno) | 1.43 / 1.39 / 1.70 | 37.7% | −44% | |

Controlli «troppo bello = bug»: ri-derivato con prezzi grezzi senza giorni di stacco/split (Sharpe lordo 1.73 contro 1.75 sulla
versione a 20 titoli); troncamento identico; gli stessi titoli di giorno perdono 14%/anno (specchio atteso, Lou-Polk-Skouras 2019).
**Ma i controlli di attribuzione lo ridimensionano:**
- 5 titoli con il momentum a 12 mesi più alto, tenuti di notte: Sharpe **1.21 / 1.26 / 1.23**. Il segnale notturno aggiunge poco.
- SPY tenuto solo di notte: Sharpe 0.75 (ver 1.27). Beta del candidato verso SPY notte 1.53.
- Coperto con SPY/MES di notte: Sharpe **0.60 / 0.84 / 0.08**. L'alfa di selezione è sparito in verifica.
- Quindi è: premio notturno dell'azionario preso a beta 1.5 su titoli volatili vincenti (volatilità 41% contro 26% dell'universo).
- Per anno: positivo 19 anni su 22; −6% nel 2008, −19% nel 2022, −4% nel 2023. Per titolo 0.3 sostituzioni al giorno su 5.

Richieste del brief v6:
- **Chi paga**: chi compra in apertura e vende in chiusura (flusso al dettaglio sui titoli «di attenzione», gestori che chiudono il
  rischio prima della notte). Continuerà a pagare finché la notte resta il momento in cui arriva l'informazione e i dealer non vogliono
  inventario; la parte di selezione è già stata arbitrata (ETF «overnight», desk che fanno la stessa cosa).
- **Capacità**: irrilevante a questa taglia (aste da centinaia di milioni). **Sede**: IBKR Ireland, azioni USA, ordini MOC e MOO, margine ≤ 2x.
- **Evento che lo uccide**: un gap notturno sui 5 titoli. Peggior notte −12.1% a 1x, −24% a 2x; a 5x in CFD −60%.
- **Correlazione col fondo** (giornaliera / mensile, dal 2018-04): B_cassa_in_tbill 0.26 / 0.26; C1_mtm_limiti 0.17 / 0.23;
  C3_mtm_limiti_debito_reale 0.17 / 0.22. 50/50 con C3: Sharpe 1.57 contro 1.43 del fondo da solo; con C1 invariato (1.43).
- **Leva che massimizza la crescita** (in campione): 5x (solo CFD) → 4.3%/mese composto, max DD −99%, P(−50% in 3 anni) 0.97; in
  verifica a quella leva **−2.2%/mese**. Metà leva (2.5x): 2.7–2.8%/mese, P(−50%) 0.57 (0.73 a metà edge, 0.7%/mese).
  Leva eseguibile in azioni (2x): **3.45%/mese composto**, P(−50% in 3 anni) 0.22 base e 0.41 a metà edge; a 1x 1.9%/mese, P 0.003 / 0.017.

## 6. Conto minimo perché le commissioni smettano di dominare (FATTO)
Il minimo di 0.35 $ non morde più per ordini ≥ 54 azioni (≈ 6 700 $ al prezzo mediano 2023–26 di 124 $).
| Strategia | Ordini/anno | Commissioni su 10k € | Su conto grande | Lordo | Conto oltre cui il minimo non morde |
|---|---|---|---|---|---|
| Inversione 5g 20+20 (tenuta 5g) | 17 285 | 53.7%/anno | 4.7% | 15.3% | ≈ 1.3 M$ |
| Momentum 12-1 20+20 mensile | 294 | 1.0% | 0.4% | −0.8% | ≈ 270 k$ |
| Bassa volatilità 20 titoli mensile | 55 | 0.2% | 0.03% | 10.2% | ≈ 130 k$ |
| Notte, 5 titoli (10 ordini al giorno) | 2 520 | 7.9% | 4.1% | 33.1% | ≈ 33 k$ a 1x, 17 k$ a 2x |

## 7. Cosa aggiunge al fondo, e cosa non so
- Verso il 30%/mese: **niente di nuovo come alfa**. Il candidato regge 1.9%/mese a 1x e 3.4%/mese a 2x con drawdown −41% / −67%,
  ed è in gran parte beta azionario notturno, che il fondo in parte ha già (indici). Come diversificatore sposta lo Sharpe di C3 da 1.43 a 1.57.
- Dubbio principale (IPOTESI): l'apertura Yahoo è il prezzo dell'asta ufficiale? Per i titoli NYSE può essere la prima stampa
  consolidata. 3 bp per lato di scarto dimezzano lo Sharpe (0.62). Serve un mese di carta con eseguiti MOO/MOC veri prima di crederci.
- La copertura dell'universo al 51–75% prima del 2015 gonfia i long in selezione; la verifica (96–99%) dà Sharpe 1.04, non 1.42.
- Il filtro prezzo > 30 $ è nato dai costi (senza filtro la commissione per azione sale a 31%/anno), ma è una delle 32 celle provate.
- Fee d'asta stimate dentro 0.0065 $/azione; fisco italiano (26%, niente compensazione automatica) non modellato; MOC/MOO sui CFD non verificato.
- Momentum, bassa volatilità e pesi mensili sono simulati a pesi costanti (deriva ignorata): errore piccolo, non misurato.
- File: `returns.parquet` (7 colonne giornaliere nette, non a leva, indice di calendario), `trades.parquet` (11 flussi in R), `membership.csv`.
