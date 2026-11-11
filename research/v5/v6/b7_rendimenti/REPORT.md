# B7 — Rendimenti neutrali al mercato per un residente italiano (v6)

Tutto **SIMULATO** su serie pubbliche reali; nulla è stato negoziato. Etichette: **[F]** fatto misurato, **[S]** stima, **[I]** ipotesi.
Script: `00_dati_*.py`, `01_scelta_binance.py`, `02_sedi.py`, `03_rotazione_hl.py`, `04_stable_staking.py`, `05_opzioni.py`, `06_portafoglio.py` (+ `.out`). Serie: `returns.parquet`.

## Risposta in breve
- La rotazione del carry su **tutti** i perpetual di Hyperliquid rende più della versione BTC/ETH/SOL: nel 2026 **11,1%** sul nozionale contro 3,5% (7,6% senza Monero, che Kraken non vende nel SEE **[I]**).
- Sul capitale (spot su Kraken + short a 2x) fa **6,7% nel 2026 fino a oggi, 7,5% negli ultimi 12 mesi**: circa **0,5–0,6% al mese**, cioè 3,5–4 punti l'anno sopra i T-bill, **prima** di tasse e rischi di sede.
- Dopo l'imposta del 33% (contro il 12,5% dei titoli di Stato) e il costo atteso degli eventi di coda (2,6% l'anno, stima), rende **meno dei T-bill**: 2,4–2,6% contro 3,5% netti.
- Non sposta il fondo verso il 30% al mese: al più +0,03–0,06% al mese sul fondo, con metà dei rischi fuori dalla serie.
- Staking coperto, prestiti di stablecoin, Pendle, T-bill tokenizzati e vendita di opzioni non battono i T-bill dopo le tasse.

## 1. Funding e base per sede **[F]**
Profondità delle storie pubbliche: Deribit dal 2019, Hyperliquid dal 5/2023, Kraken Futures solo dal 30/10/2025, OKX solo 90 giorni. I perpetual di OKX Europe espongono lo stesso listino del sito globale; non ho trovato una storia separata.

Funding annuo % incassato dallo short:

| Sede / moneta | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | ultimi 90 g |
|---|---|---|---|---|---|---|---|
| Binance BTC (non accessibile) | 30,6 | 4,2 | 7,9 | 11,9 | 5,1 | 3,1 | 5,9 |
| **Hyperliquid BTC** | – | – | 15,1 | 24,1 | 10,6 | 5,6 | 9,2 |
| Hyperliquid ETH | – | – | 22,4 | 22,1 | 8,5 | 6,0 | 8,7 |
| Hyperliquid SOL | – | – | 13,0 | 28,1 | 5,3 | 0,8 | 7,3 |
| Deribit BTC perp | 16,5 | −2,3 | 6,9 | 10,3 | 5,4 | 2,4 | 4,5 |
| Deribit BTC trimestrale (base) | 14,5 | 0,8 | 5,2 | 12,3 | 6,4 | 3,1 | 5,3 |
| Kraken Futures BTC | – | – | – | – | 5,5 | 3,4 | 8,4 |
| OKX BTC | – | – | – | – | – | 6,4 | 6,3 |
| CME BTC front (Yahoo, rumoroso **[S]**) | 3,9 | −4,7 | 6,1 | 9,8 | 4,9 | 6,3 | 4,8 |

- Hyperliquid paga circa 1,5–2 volte le altre sedi sulla stessa moneta. Sullo stesso periodo (dal 30/10/2025): HYPE 9,9% contro 6,9% su Kraken; XMR 28,6% contro 18,9%.
- Persistenza: correlazione tra il funding medio di un mese e del successivo 0,4–0,6. Il segnale lento funziona per questo.
- Tasso di riferimento: T-bill a 3 mesi in dollari 3,7% medio nel 2026, 4,0% oggi.
- Perpetual su azioni e materie prime (HIP-3, dex xyz, 3,9 mld $ al giorno): funding mediano 8,8% dalla quotazione, 7,3% negli ultimi 90 giorni; NVDA 5%, GOOGL 7,6%, oro 7%. Copribili con il titolo vero su IBKR.

## 2. Rotazione su tutti i perpetual di Hyperliquid
**Regola (congelata su Binance ≤ 2022, 96 varianti, scelta a costi doppi):** ogni giorno, per ogni moneta idonea, media a 30 giorni del funding annualizzato (solo giorni completi). Tre posizioni di peso uguale; si entra nella migliore se supera il 25%; si esce solo se la media scende sotto zero o la moneta non è più idonea. Idonea = volume mediano a 30 giorni sopra 5 M$ e spot presente su Kraken.
**Costi:** spot 30 pb per lato, perp 6,5 pb per lato (73 pb andata e ritorno), variazione del premio perp–spot inclusa.
**Periodi:** Hyperliquid non esisteva nel periodo di scelta, quindi tutto il 2024–2026 è verifica. La scelta è fatta sul funding di Binance, che un italiano non può incassare.

Rendimento sul **nozionale**, netto costi (2/2024 → 11/2026, 498 perpetual scaricati, 235 del dex principale di cui 56 tolti dal listino):

| Variante | CAGR | 2024 | 2025 | 2026 | ultimi 90 g (annuo) |
|---|---|---|---|---|---|
| **Rotazione, tutte le monete** | 18,7% | 22,3 | 14,4 | 11,1 | 20,7 |
| costi doppi | 18,3% | | | | |
| un giorno di ritardo in più | 18,6% | | | | |
| senza XMR | 17,3% | 22,3 | 14,4 | 7,6 | 13,8 |
| solo monete con volume > 20 M$ | 15,6% | 22,3 | 14,4 | 3,6 | 6,3 |
| 10 posizioni | 15,2% | 25,5 | 9,6 | 4,3 | 8,8 |
| spot su Hyperliquid (10 pb) | 15,4% | 22,3 | 11,7 | 5,8 | 8,4 |
| Stessa regola, solo BTC/ETH/SOL | 10,0% | 22,3 | 4,2 | 0,2 | 0,0 |
| BTC/ETH/SOL sempre dentro | 13,0% | 22,3 | 8,2 | 3,5 | 8,4 |
| HIP-3 xyz con titolo su IBKR (361 giorni) | 14,4% | – | – | 13,3 | 23,5 |

- Posizioni tenute: SOL, ETH, BTC dal 11/2023; poi HYPE (dal 3/2025), FARTCOIN (dal 4/2025), XMR (2026). 2,5 ingressi l'anno, durata media 455 giorni: i costi contano poco.
- **Il vantaggio 2026 viene da tre monete** (HYPE 9,4%, FARTCOIN 14,7%, XMR 28,6%). Con soglia di volume a 20 M$ scende al 3,6%: non è ampiezza, è concentrazione.
- Lato negativo (perp lungo, spot corto a prestito al 44% l'anno): occupato il 10% del tempo, 6,2% sul nozionale, t 3,7; non ho verificato che quelle monete siano prestabili **[I]**.
- Serie lunga con Binance come surrogato fino al 1/2024: pieno 17,9%, scelta 23,5%, verifica 13,7% sul nozionale. Per anno: 2020 22,2; 2021 41,1; 2022 0,2; 2023 1,5.
- Sharpe misurato 10–15: **è un artefatto**. La volatilità dell'1% non contiene il rischio vero. Controllo incrociato: il funding di HYPE e XMR su Kraken conferma segno e ordine di grandezza. Controllo di troncamento superato.

## 3. Leva sulla gamba corta e liquidazioni **[F sui massimi giornalieri]**
Capitale = spot + margine; rendimento sul capitale = nozionale × leva/(leva+1). Liquidazione se il massimo del giorno supera la distanza di liquidazione dall'ultimo rimargine (fatto a metà strada).

| Leva short | Investito | Crescita annua | Mese composto | Liquidazioni/anno | 2026 | Capitale su Hyperliquid |
|---|---|---|---|---|---|---|
| 1x | 50% | 8,4% | 0,70% | 0 | 5,4% | 50% |
| **2x** | 67% | **10,7%** | **0,89%** | 0 | 6,7% | 33% |
| 3x | 75% | 8,8% | 0,73% | 2,5 | 3,4% | 25% |
| 5x | 83% | −32,6% | −2,7% | 29,5 | −65% | 17% |

**La crescita è massima a 2x; metà leva è 1x.** A 3x le monete piccole (leva massima 5–10x, margine di mantenimento 5–10%) vengono liquidate su rialzi del 29–46% in un giorno. Per BTC/ETH/SOL il massimo è a 3x (8,5%).
**Looping [S]:** prendere il margine a prestito su Aave contro lo spot (USDC al 5%) aggiunge circa 1,7 punti e una seconda liquidazione, al ribasso, su un'altra sede. Tenere tutto su Hyperliquid porta il 100% del capitale sulla sede non regolata (costo atteso delle code 5,2% l'anno contro 6,8% di rendimento). Il loop sUSDe contro USDC oggi ha margine nullo (5,0% contro 5%).

## 4. Collaterale in staking coperto con short perp **[F, lordo costi]**
| % annuo sul nozionale | 2023 | 2024 | 2025 | 2026 | ultimi 90 g |
|---|---|---|---|---|---|
| stETH (staking) | 3,9 | 3,2 | 2,8 | 2,4 | 2,4 |
| stETH + short ETH Hyperliquid | 24,0 | 25,2 | 11,4 | 8,4 | 11,0 |
| stETH + short ETH Deribit | 12,2 | 11,6 | 3,8 | 3,9 | 6,0 |
| JitoSOL + short SOL Hyperliquid | – | – | 12,7 | 6,2 | 12,1 |
| JitoSOL + short SOL Deribit | – | – | 11,0 | 8,6 | 9,6 |

- Sul capitale a 2x: stETH 5,6%, JitoSOL 4,1% nel 2026. Sotto la rotazione.
- Nella rotazione lo staking aggiunge zero oggi: ETH e SOL sono usciti nella primavera 2025.
- Scarto stETH/ETH: minimo filtrato 0,91 a giugno 2022 (mercato circa 0,93–0,94 **[S]**), 50 giorni sotto 0,97, rientro a fine luglio. Coppia diretta OKX dal 7/2023: minimi infragiornalieri 0,953 (2024) e 0,967 (2025), chiusure mai sotto 0,994. I prezzi giornalieri di DefiLlama danno minimi falsi (0,78) nei giorni di crollo.

## 5. Stablecoin e rendimenti fissi **[F: APY dichiarati, lordi]**
| APY % | 2023 | 2024 | 2025 | 2026 | oggi |
|---|---|---|---|---|---|
| T-bill 3m USD | 5,05 | 4,95 | 4,05 | 3,71 | 4,03 |
| Aave v3 USDC | 3,8 | 7,2 | 4,1 | 3,4 | 4,0 |
| Compound v3 USDC | 4,0 | 8,0 | 4,7 | 3,5 | 3,2 |
| Morpho Steakhouse USDC | – | – | 4,0 | 4,0 | 4,5 |
| Fluid USDC | – | 11,1 | 6,8 | 5,1 | 5,4 |
| Ethena sUSDe | – | 17,5 | 6,5 | 4,2 | 5,0 |
| Sky sUSDS | – | – | 4,8 | 3,7 | 3,8 |
| Pendle PT-sUSDe (fisso) | – | – | – | 4,8 | 5,3 |
| Ondo USDY / BlackRock BUIDL | – | – | – | 3,6 / 3,2 | 3,8 / 3,8 |

- Nel 2026 Aave USDC è sopra il T-bill solo il 18% dei giorni (−0,28 punti in media); sUSDe +0,5 punti; Fluid +1,4.
- Depeg misurati: USDC 0,882 l'11/3/2023 (31 ore sotto 0,97, rientro in 3 giorni); DAI 0,967 lo stesso giorno; USDe 0,979 il 2/2/2026; UST a zero (5/2022).
- Storia degli incidenti **[S, a memoria, da verificare]**: Euler 3/2023 (197 M$, restituiti); Curve 7/2023 (~70 M$); Balancer e Stream/xUSD 11/2025 con debito cattivo in alcuni vault curati; USDe a 0,65 su una sola sede il 10/10/2025. Aave e Compound non hanno perso capitale dei depositanti sui mercati principali.
- Tasse: 33% su ogni provento e su ogni conversione, contro 12,5% dei titoli di Stato. Aave al 4% dà 2,65% netto contro 3,53% del T-bill. **Scartati tutti.**

## 6. Opzioni su Deribit **[S: premi stimati da DVOL, nessun prezzo storico]**
16 varianti (BTC/ETH, 7/30 giorni, delta 0,10/0,25, call/put). Nessuna con |t| > 2. Call BTC a 7 giorni delta 0,25: +42% l'anno nella scelta, −15% nella verifica. Put BTC 7 giorni delta 0,25: +10,8% l'anno, Sharpe 0,5, beta +0,27, peggior settimana −25%. Non è neutrale e non è distinguibile da zero. **Scartata.**

## 7. Il portafoglio neutrale migliore, e che cosa regge
**Struttura:** spot su Kraken (67% del capitale) + short perp su Hyperliquid a 2x (33%), rotazione a tre posizioni.
**Chi paga:** i long a leva su Hyperliquid, che non hanno altro modo di finanziarsi; pagano finché cercano leva su monete di tendenza. Il compenso è già sceso da 22% (2024) a 11% (2026).
**Capacità:** oltre 1 M€ su BTC/ETH/HYPE; poche centinaia di migliaia sulle monete piccole. Irrilevante per 10–12 mila euro.

| Sul capitale, short 2x | Pieno | Scelta (Binance) | Verifica | 2024 | 2025 | 2026 | ultimi 12 mesi |
|---|---|---|---|---|---|---|---|
| CAGR / rendimento | 11,3% | 15,1% | 8,3% | 14,7 | 8,6 | 6,7 | 7,5 |
| Eccesso sul T-bill | | | | 9,7 | 4,6 | 3,5 | 3,8 |
Peggior drawdown misurato −0,4%: non significa nulla.
**Eventi di coda fuori dalla serie [S]:**
| Evento | Probabilità annua | Perdita | Precedenti |
|---|---|---|---|
| Hyperliquid: fallimento, hack del bridge, blocco prelievi | 5% | 80% del margine | FTX (fondi bloccati 2+ anni), Mt. Gox, WazirX |
| Kraken: fallimento o blocco | 1% | 50% dello spot | Celsius (60–80% recuperato in 19 mesi) |
| ADL o chiusura forzata dello short, poi rimbalzo | 40% | 3% del nozionale | 10/10/2025, JELLY 3/2025, POPCAT 11/2025 |
| USDC depeg permanente | 0,5% | 100% del margine | UST; USDC 3/2023 rientrato |

Costo atteso: **2,6% l'anno** a 2x (5,3% raddoppiando le probabilità). Il furto a Bybit (2/2025, 1,46 mld $) è stato coperto dalla sede: perdita zero per i clienti.
**Bootstrap a blocchi mensili, 3 anni, code iniettate:**
| Scenario | Leva | Mese composto mediano | P(−20%) | P(−50%) |
|---|---|---|---|---|
| Base 2024–26 | 2x | 0,77% | 17,7% | 0,3% |
| Base 2024–26 | 1x | 0,61% | 17,2% | 1,5% |
| Metà vantaggio | 2x | 0,35% | 17,8% | 0,4% |
| **Regime di oggi (ultimi 12 mesi)** | 2x | **0,50%** | 17,6% | 0,3% |
| Oggi, metà vantaggio | 2x | 0,21% | 17,4% | 0,5% |

**Contro i T-bill, oggi:** lordo 7,5–7,8% contro 4,0%. Netto d'imposta 5,1–5,2% contro 3,5%. Netto anche delle code attese **2,4–2,6% contro 3,5%**.
**Quota ottima della cassa (crescita con salti):** 100% con l'eccesso di oggi e le probabilità base; **0%** se le probabilità raddoppiano o l'eccesso si dimezza. La decisione dipende interamente da una stima che non so misurare.
**Correlazione con il fondo:** giornaliera circa 0 (+0,03 / 0,00 / 0,00 con B, C1, C3); **mensile +0,48–0,63** sul periodo Hyperliquid (+0,28–0,41 dal 2020). Il funding è alto quando le crypto salgono, cioè quando il fondo già guadagna.
**Effetto sul fondo:** la cassa è circa il 47% del libro a 1x. Spostarla tutta dà +1,8–1,9 punti lordi l'anno, +0,6–0,7 netti di code: **+0,05% al mese**.

## 8. Che cosa non so
- Le probabilità degli eventi di coda sono giudizi; il verdetto si rovescia entro un fattore 2.
- La lista spot di Kraken è quella di oggi (lieve look-ahead); XMR e alcune monete possono non essere acquistabili dal SEE.
- Liquidazioni misurate sui massimi giornalieri con rimargine a fine giornata; un controllo orario farebbe meglio, un blocco della sede peggio.
- Accesso di un residente italiano a Deribit e a HIP-3 non verificato **[I]**. HIP-3 ha solo 12 mesi di storia e la copertura con azioni è chiusa nel fine settimana.
- Trattamento fiscale del funding e delle conversioni in USDC: da far confermare al commercialista.
- Selezione fatta su una sede (Binance) diversa da quella di verifica.

**Varianti provate: 141** (96 griglia Binance, 17 Hyperliquid, 16 opzioni, 4 staking, 8 leva e looping).
