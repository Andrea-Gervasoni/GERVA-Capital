# B1 — Dati per-conto di Hyperliquid: essere la casa, copiare i migliori, posizionamento

Tutto SIMULATO o ricostruito da dati pubblici; nulla ha operato. Etichette: FATTO / STIMA / IPOTESI. Data dei dati: 2026-11-11.

## 0. Che cosa espone davvero l'API (FATTO, verificato)
| chiamata | che cosa da' | limite che conta |
|---|---|---|
| `POST api.hyperliquid.xyz/info {"type":"vaultDetails","vaultAddress":..}` | storia valore/PnL del vault, commissione, follower (primi 100), chiuso o no | serie `allTime`: **un punto ogni 7–14 giorni** (HLP: 103 punti dal 2023-05). Non esiste storia giornaliera. |
| `{"type":"portfolio","user":..}` | stessa cosa per ogni indirizzo; `perpAllTime` parte da **maggio 2024** | idem; 160 chiamate in 8 s senza errori 429 |
| `{"type":"userFills"}` / `userFillsByTime` | fill con `startPosition`, `closedPnl`, `crossed` | 2000 per chiamata; in pratica ~10.000 fill recenti per conto (pochi conti di piu'): per un conto attivo sono giorni o settimane |
| `clearinghouseState`, `userFunding`, `userNonFundingLedgerUpdates`, `recentTrades` (con i due indirizzi) | stato attuale, funding, depositi/prelievi | solo presente o finestre brevi |
| `{"type":"leaderboard"}` su /info | **non esiste** (422) | usare `stats-data.hyperliquid.xyz/Mainnet/leaderboard` (48.280 righe) e `/Mainnet/vaults` (9.478 vault, **6.421 chiusi compresi**) |
| `POST rpc.hyperliquid.xyz/explorer {"type":"blockDetails","height":h}` | transazioni di un blocco storico con l'indirizzo | funziona sui blocchi del 2024 (h 300M = 2024-09-15); limitato (~1/s) |
| `d2v1fiwobg9w6.cloudfront.net/<nome>` (stats) | `hlp_positions` (netto giornaliero di HLP per moneta 2023-06→2026-04), `largest_liquidated_notional_by_user`, `daily_usd_volume_by_user`, OI, funding | `hlp_pnl` e simili: 403 |

Indirizzi scaricati: 10.648 (1.960 vault con storia, 1.157 attivi nei blocchi 2024-Q4 campionati [2.500 blocchi], 4.982 dalle tabelle stats, 2.549 dalla classifica di oggi). La convenzione "selezione ≤ 2022" **non e' applicabile**: Hyperliquid nasce nel 2023. Dove serviva ho usato formazione ≤ T e valutazione > T.

## 1. Essere la casa: HLP
Rendimento per intervallo = ΔPnL / capitale medio (Dietz). 98 intervalli di ~14 giorni, 2023-06 → 2026-11 (`03_hlp.out`).

| periodo | rendimento composto | vol annua (su 14g) | Sharpe mensile su T-bill | DD massimo (su griglia 14g) | TVL medio |
|---|---|---|---|---|---|
| 2023 (da giugno) | +43% | 35% | 1,7 | −5,9% | 5 M |
| 2024 | +63% | 12% | 3,2 | 0 | 154 M |
| 2025 | +17% | 8,5% | 1,4 | −0,9% | 403 M |
| 2026 (10 mesi) | +9,3% | 7,0% | 1,1 | −0,5% | 283 M |
| tutto | CAGR 34–37% | 17% | 1,64 | −5,9% | — |
| **ultimi 12 mesi** | **+7,2%** (T-bill +3,8%) | 6,6% | **0,77** | −0,8% | — |

- FATTO: il rendimento scende mentre il capitale sale: e' un deposito a capacita' limitata, non una strategia. 3 mesi negativi su 42, peggiore −0,65% (dopo il 2023).
- FATTO: e' a grumi. Dei +7,2% degli ultimi 12 mesi, +7% viene da gennaio–febbraio 2026 (un solo intervallo +18,8 M$, +6,65%). **Maggio–ottobre 2026: +1,2% in sei mesi, meno dei T-bill (+1,85%)**. Mese mediano 2026: +0,16%. Oggi 100,8 M$ su 149,6 M$ stanno nel sotto-vault "HLP Strategy X", che dichiara un APR del 4,2%: in gran parte capitale parcheggiato.
- Eventi (FATTO dai dati, salvo dove indicato): 12 mar 2025 (liquidazione balena ETH) −4,28 M$ in un giorno, intervallo −0,91%; JELLY 26 mar 2025: intervallo +0,45% perche' i validatori hanno chiuso il mercato a prezzo favorevole — la perdita non realizzata di ~12 M$ (cronaca, non nei miei dati) non compare a 14 giorni; pero' il TVL e' sceso da 354 M a 150 M in quattro settimane (fuga dei depositanti); **10 ott 2025: +41,4 M$, +8,8%** (la casa incassa le liquidazioni); POPCAT 12 nov 2025: −4,66 M$, −0,83%.
- La griglia a 14 giorni nasconde i drawdown infragiornalieri. Ultimo mese (punti ogni ~23 h): vol annua 4%, DD −0,3%.
- Correlazione con il fondo: −0,13 / −0,20 / −0,21 a 14 giorni (B, C1, C3), −0,07 / −0,13 / −0,13 mensile (n=39). Con BTC −0,10, beta −0,04. Esposizione netta HLP/TVL: mediana −1%, 5° percentile −47% (corto nei rialzi).
- Regole (FATTO da documentazione Hyperliquid, non provato con un deposito): blocco di 4 giorni dopo ogni deposito; nessuna commissione; USDC sul ponte Arbitrum; nessuna leva possibile. Nei vault utente: blocco 1 giorno, 10% dei profitti al gestore.
- Chi paga: i trader a leva liquidati e i taker (spread, commissioni di liquidazione). Continueranno a pagare, ma il premio si divide per il TVL: capacita' gia' satura (rendimento ~ 1/TVL).

**E' un deposito, non una strategia.** Rendimento atteso onesto (STIMA): **0,5–0,9% al mese in media, mediana ~0,2%**, contro 0,31% dei T-bill; vol annua 7%; perdita storica massima 6% (con TVL < 10 M). Rischio vero fuori dalla storia: exploit, ponte, manipolazione tipo JELLY senza salvataggio, venue non regolata.
Cassa ferma (40%) in HLP invece che T-bill (`09_fondo_hlp.out`): sul 2023-06→2026-10 B passa da CAGR 13,0% a 26,0%, ma **+19,4 punti/anno vengono dal 2023-24 (TVL piccolo, irripetibile) e +3,5 dal 2025-26; sugli ultimi 12 mesi +1,4 punti/anno**. Bootstrap 3 anni sui mesi 2025-26: mese composto +1,11% (meta' edge +0,56%), P(−50%) = 0 nella storia; con un'IPOTESI di coda del 3%/anno di perdere meta' deposito: mese +0,93%, P(DD ≤ −50%) 2,7%, P(DD ≤ −20%) 8,4%. Leva che massimizza la crescita: 1 (non si puo' fare leva su un deposito).
Giudizio: per il 40% di cassa HLP rende oggi 1–3 punti/anno piu' dei T-bill in cambio di un rischio di coda non assicurabile e di 4 giorni di blocco — e quella cassa e' il margine di riserva del fondo. Al massimo un 10–15% del capitale, non il 40%.

## 2. Gli altri vault: la sopravvivenza e' tutto (`04_vault.out`)
- (a) I 20 vault utente piu' grandi OGGI con ≥ 12 mesi: CAGR netto mediano **+62%**, Sharpe 1,2, DD mediano −42%, 75% sopra i T-bill. E' la vetrina.
- (b) I 20 piu' grandi **alla data T**, seguiti 12 mesi, chiusi compresi (netto del 10%):

| T | media | mediana | pesata TVL | PnL $ / TVL a T | perdenti | sotto −30% | DD mediano | HLP | T-bill |
|---|---|---|---|---|---|---|---|---|---|
| 2024-06-30 | −10% | −6% | −46% | −57% | 60% | 40% | −47% | +18% | +4,4% |
| 2024-09-30 | −27% | −18% | −81% | −191% | 65% | 45% | −81% | +15% | +4,2% |
| 2024-12-31 | −50% | −58% | −59% | −74% | 80% | 60% | −83% | +17% | +4,1% |
| 2025-03-31 | +1% | −15% | −30% | −95% | 65% | 40% | −52% | +22% | +3,9% |
| 2025-06-30 | −12% | −16% | +11% | −25% | 60% | 40% | −47% | +19% | +3,7% |
| 2025-09-30 | −11% | −40% | +3% | −3% | 60% | 55% | −56% | +17% | +3,7% |
| 2025-11-11 | +12% | +4% | +16% | +13% | 45% | 10% | −26% | +7% | +3,7% |

- (c) Tutti i vault con TVL ≥ 100k a T: a 12 mesi mediana −79% (T=2024-12, n=47), −21% (2025-06, n=62), −11% (2025-11, n=75); il 63–83% perde.
- Distanza fra vetrina e realta': ~+62% contro ~−15% mediano. Coorti sovrapposte: ~2,3 osservazioni indipendenti. STIMA: la commissione e' applicata sul guadagno finale; non ho scaricato i vault con PnL storico < 3k$ e TVL < 30k$.

## 3. Copy-trading: la persistenza c'e', ma non dove si puo' copiare (`07_persistenza.out`)
Pannello a 14 giorni, serie **solo perpetui** (quella totale include lo spot: l'airdrop HYPE di fine 2024 e' falso PnL). Formazione 26 settimane ≤ T, 8 date T da 2025-01-02 (formazione ≤ 2024-12) a 2026-08-13, non sovrapposte; conto ≥ 10k$; decile alto per Sharpe; controllo di troncamento superato. Universo PIT = indirizzi noti a T (blocchi 2024-Q4, top giornalieri per volume con data ≤ T, vault esistenti a T).

| universo (n medio) | IC rango→rendimento 12 sett. (t) | % positivi decile alto / resto | finiti ≤ −50%: alto / resto |
|---|---|---|---|
| PIT tutti (442) | 0,19 (3,7) | 70% / 49% | 8% / 18% |
| **PIT veloci**, turnover > 3000×/anno (135) | **0,37 (6,2)** | 79% / 52% | 4% / 21% |
| **PIT lenti**, turnover ≤ 300×/anno (128) | **0,04 (0,4)** | 64% / 52% | 8% / 14% |
| vault (98) | 0,12 (2,4); su Sharpe futuro 0,24 (4,9) | 54% / 44% | 12% / 15% |
| classifica di OGGI (248) | 0,06 (0,8) | 65% / 49% | 15% / 25% |

- FATTO: la persistenza sta nei conti ad altissima rotazione (market maker, arbitraggisti): il loro vantaggio e' l'esecuzione, non la direzione. Copiarli pagando 6,5 bp per lato: **−100%** (portafoglio a maniche, sez. 7 dell'output: Sharpe da +4,1 a −10,7).
- Conti lenti (gli unici copiabili): decile alto come portafoglio comprato e tenuto, leva normalizzata: Sharpe 1,03 senza costi, **0,98 con costi stimati, t = 1,3, DD −47%**; ma il **resto** dei conti lenti fa Sharpe 2,1–2,4 e "alto meno resto" vale Sharpe −0,04. Non c'e' selezione: c'e' solo un universo che nel 2025-26 ha guadagnato sulla gamba perp (molti sono coperti con spot: il PnL perp e' meta' del libro). Pesato per capitale: il decile alto batte il resto in 2 date su 8.
- Vault (l'unica copia letterale, rendimento esatto del follower): decile alto CAGR −20% (maniche comprate e tenute, prima del 10% al gestore); top-20 +13% lordo con Sharpe 0,5 (t = 0,7); tutti i vault ≈ 0%. La persistenza qui e' "chi va male continua ad andare male".
- **Quanto pesa la sopravvivenza**: "copia tutti i conti lenti" rende CAGR +46% / Sharpe 1,6 sull'universo PIT e **+117% / Sharpe 3,0** sugli stessi criteri applicati alla classifica di oggi; il decile alto passa da Sharpe 1,0 (PIT) a **3,7** (classifica). Del decile alto PIT al 2025-01-02 (n=31): oggi il 71% ha un conto < 10% di allora, il 19% ha perso ≥ 50%, il 16% ≥ 90%, solo il 39% e' ancora in classifica.
- Simulazione di copia fill-per-fill a 1–5 minuti: **non eseguita come strategia**, perche' la condizione ("se la persistenza esiste") non e' soddisfatta nei conti copiabili e perche' l'API da' ~10.000 fill per conto: su 80 conti scelti a T=2026-05-21, solo 25 hanno i fill dall'inizio alla fine dei 5 mesi, e solo il 42% del volume e' su BTC/ETH/SOL (le sole monete con barre a 5 minuti in cache).

## 4. Posizionamento
- HLP netto giornaliero per moneta (2023-06→2026-04, 996 giorni; `06_hlp_posizioni.out`): 30 varianti (5 segnali × 3 monete × 2 ritardi), costi inclusi. Segni concordi selezione (≤2024) / verifica (≥2025): **50%**. Il "migliore" in selezione (SOL, variazione 1g, Sharpe 0,90) fa 0,06 in verifica. Nessun segnale. Orizzonti 4–12 h non verificabili: il dato e' giornaliero.
- Top 40 contro bottom 40 conti (scelti a 2026-05-21) dai fill, orario, 4 e 24 h (`10_posizionamento.out`): 72 varianti, **0 con |t| > 2** (attese per caso ~4), Sharpe netto medio −0,54. 5,3 mesi, una coorte, 6–13 conti coperti per ora: potenza quasi nulla.

## 5. Risposte dovute dal brief (miglior candidato = deposito in HLP)
- Chi paga / capacita': vedi §1; capacita' satura a ~150–500 M$ di TVL.
- Venue: Hyperliquid, vault HLP `0xdfc24b07…f303`, USDC. Non regolata; fiscalita' italiana da verificare (IPOTESI: redditi diversi cripto).
- Sharpe/CAGR: tutto 1,64 / 34–37%; "selezione" inesistente; 2025-26 (il solo regime rilevante) Sharpe 1,1–1,4, CAGR 9–17%; ultimi 12 mesi 0,77 / 7,2%.
- Peggior DD −5,9% (2023). Coda che uccide: exploit del contratto/ponte o manipolazione su moneta illiquida ereditata da HLP.
- Leva ottimale 1; mese composto +1,1% (base 2025-26), +0,56% (meta'); P(−50% in 3 anni) 0 storico, 2,5–2,7% con coda ipotizzata.
- `returns.parquet`: `HLP_deposito` (giornaliero, calendario, senza leva; **interpolato** dentro ogni intervallo di 14 giorni: non usarlo per la volatilita' giornaliera) e `HLP_meno_tbill_x0.4`.

## 6. Prove contate e dubbi
- Varianti: 166 (persistenza) + 30 (HLP posizioni) + 72 (fill) = **268**; HLP e coorti vault: nessun parametro scelto.
- Dubbi: (1) griglia a 7–14 giorni: Sharpe di formazione su 10–13 punti, rumoroso; liquidazioni infra-periodo invisibili. (2) PnL/margine non e' il rendimento di un copiatore quando il conto tiene poco margine o e' coperto altrove; per questo conto solo sui confronti alto/resto e sui vault. (3) Turnover misurato su tutta la vita del conto (lieve informazione futura nella sola classificazione lento/veloce). (4) Universo PIT sbilanciato verso i conti grandi e attivi; 1.157 indirizzi da 2.500 blocchi. (5) Storia utile: 3,5 anni per HLP, 22 mesi per la persistenza, 5 mesi per i fill. Ogni conclusione positiva sarebbe debole; quelle negative (vault, copia) reggono perche' l'effetto e' grande.
- Non verificato: regole di blocco con un deposito reale; nome dell'evento di gen–feb 2026.
