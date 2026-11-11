# GERVA Capital — STRUTTURA operativa (v4)

Ricerca chiusa il **2026-11-11**. Tutte le fonti web sono state consultate in questa data (elenco completo in §G).

**Legenda**
- **FATTO VERIFICATO [n]** = letto oggi su fonte citata in §G. "(primaria)" = regolatore/documentazione ufficiale; "(secondaria)" = stampa o guida di terzi.
- **NON RIVERIFICATO** = conoscenza pregressa dell'autore (cutoff giugno 2026), non ricontrollata oggi: da trattare come ipotesi finché non confermata.
- **STIMA** = ordine di grandezza ragionato. **IPOTESI** = lettura giuridica/operativa non confermata da fonte.
- Questo documento non è consulenza legale o fiscale. Le parti C richiedono conferma di commercialista e avvocato (domande in §C.8).

---

## 0. Sintesi brutale (leggere prima del resto)

1. **La leva 10–30x su perpetual cripto non è ottenibile in modo regolamentato da un retail italiano.** Le sedi UE autorizzate MiFID (Kraken, OKX "X-Perps", Coinbase, One Trading, Robinhood/Bitstamp) danno **al massimo 10x** [3][5][6][8]. E quel 10x è a sua volta contestato: ESMA il 24/02/2026 ha scritto che i "perpetual" ricadono *probabilmente* nelle misure sui CFD, che per le cripto impongono **2:1** al retail [1][2][9]. Nessuna sede ha annunciato tagli, nessun regolatore nazionale risulta aver sanzionato (non ho trovato notizie; non è prova che non esistano).
2. **Binance è fuori dall'Italia dal 01/07/2026** (domanda MiCA ritirata) [10][11]. **Bybit EU** non ha perpetual (MiFID in domanda, non rilasciata) [7][8]. **Bitget** non ha licenza MiCA [12]. Chi oggi vi fa aprire un conto "global" da residente italiano lo fa fuori dal perimetro autorizzato.
3. **Hyperliquid**: nessuna autorizzazione nello SEE, nessun geo-blocco sull'Italia, l'Italia non è tra le giurisdizioni vietate dai termini (USA, Ontario, paesi sanzionati) [8][13]. Tradotto: *la piattaforma ve lo lascia fare; non è un servizio autorizzato; non avete alcuna tutela UE*. Non ho trovato una norma che sanzioni il cliente retail per l'uso di una piattaforma estera non autorizzata (il reato di abusivismo colpisce chi presta il servizio) — **IPOTESI da far confermare a un avvocato**. Gli obblighi fiscali restano tutti.
4. **Fisco 2026**: plusvalenze su cripto-attività **33%** dal 01/01/2026, **26%** solo per i token di moneta elettronica in euro, franchigia 2.000 € abolita [14][15][16]. I **derivati con sottostante cripto** (CFD, future) per l'Agenzia sono redditi diversi ex art. 67 c.1 lett. **c-quater** TUIR, **26%**, quadro RT — testo letto nella circolare 30/E/2023 [17]. Non esiste (non ho trovato) una pronuncia specifica sui *perpetual* né su quelli regolati in USDC su DEX: zona grigia.
5. **Soldi di terzi**: gestire denaro altrui in modo professionale verso il pubblico senza autorizzazione è reato (art. 166 TUF: reclusione 1–8 anni, multa 4.000–10.000 €) [18]. Con 10–12 k€ la sola strada pulita è che il denaro dei familiari diventi **denaro del titolare** (donazione o prestito documentato) e che operi **in conto proprio, come persona fisica**.
6. **Con 10–12 k€ nessun veicolo societario ha senso**: una SRL costa più all'anno (STIMA 2.500–4.500 €) del rendimento atteso plausibile del capitale e porta la tassazione complessiva al ~44% in caso di distribuzione.
7. **Osservazione di progetto (IPOTESI, ma aritmetica)**: una posizione "20x isolata con margine M" ha lo stesso profilo di perdita massima di una posizione "10x con margine 2M e stop a −5%" fino al gap di prezzo. Con capitale piccolo e pochi trade simultanei il tetto 10x di una sede regolamentata limita il *numero* di posizioni aperte, non il rischio per trade. Prima di scegliere una sede non regolamentata per avere 20–30x, verificare se il motore ne ha davvero bisogno.

---

## A. Sedi di esecuzione

### A.1 Quadro giuridico (vale per tutte le sedi)

- **FATTO VERIFICATO [1] (primaria)** — ESMA, public statement 24/02/2026, "ESMA reminds firms of their obligations under CFD product intervention measures amid rising offerings of perpetual futures": i derivati commercializzati come perpetual futures/contracts, anche su cripto, "are likely to fall within the scope of the existing national product intervention measures on CFDs"; se soddisfano la definizione di CFD si applicano limiti di leva, margin close-out, protezione dal saldo negativo, avvertenza standard, divieto di incentivi; ricorda inoltre target market ristretto, test di appropriatezza, conflitti d'interesse. La pagina non cita DeFi né distingue order-book/OTC.
- **FATTO VERIFICATO [2][9] (secondarie, concordi; testo ufficiale Consob non letto integralmente)** — Misure CFD in Italia: delibera Consob n. 20976 del 20/06/2019. Leva massima retail: 30:1 valute principali; 20:1 valute minori, oro, indici principali; 10:1 altre materie prime e indici minori; 5:1 azioni; **2:1 criptovalute**. Close-out al 50% del margine, protezione saldo negativo, avvertenza con % di clienti in perdita, divieto di incentivi.
- **FATTO VERIFICATO [2] (secondaria, 27/02/2026)** — Finance Magnates: nessun provider UE di perps mostrava l'avvertenza CFD; nessuno ha annunciato riduzioni di leva; "Perps, if treated as CFDs, will be subject to all these restrictions". Bitstamp, Gemini, Bybit davano lanci in preparazione.
- **FATTO VERIFICATO [8][19] (secondarie)** — I derivati sono strumenti MiFID II, non MiCA: per offrire perps a retail UE serve autorizzazione MiFID (oltre a MiCA per lo spot). Il periodo transitorio MiCA è finito il **01/07/2026**.
- **FATTO VERIFICATO [20] (secondaria: Teleborsa/Borsa Italiana, 15/10/2026)** — Consob aveva oscurato 1.848 siti dal 2019, di cui 240 legati a cripto-attività; base: MiCAR + d.lgs. 129/2024 + "Decreto Crescita". Una guida del 09/11/2026 riporta 1.878 al 05/11/2026 [8].
- **NON VERIFICATO** — Non ho trovato provvedimenti Consob di oscuramento o avvertenze nominative contro Hyperliquid, Bybit, Bitget, Deribit, dYdX. Non ho scorso l'elenco integrale dei provvedimenti: *assenza di risultato ≠ assenza di provvedimento*. Controllare la sezione "Occhio alle truffe!" di consob.it prima di depositare.
- **Cliente professionale su richiesta** — **NON RIVERIFICATO sul testo vigente** (i risultati di oggi confermano solo la fonte: Allegato 3 del Regolamento Intermediari Consob, § II.1 [21]): almeno **due su tre** tra (a) ≥10 operazioni di dimensione significativa per trimestre nei 4 trimestri precedenti sul mercato rilevante; (b) portafoglio di strumenti finanziari + depositi > **500.000 €**; (c) almeno un anno di lavoro nel settore finanziario in posizione professionale pertinente. L'intermediario *può* rifiutare. **Cosa sblocca**: le misure CFD (leva 2:1/30:1 ecc.) valgono solo per i clienti al dettaglio; si perdono però protezione dal saldo negativo, tutele di appropriatezza e in parte l'accesso ai sistemi di indennizzo. **Con 10–12 k€ il criterio (b) è irraggiungibile; servirebbero (a)+(c)**: se il titolare non ha lavorato un anno nel settore finanziario, la strada è chiusa. Dichiarare il falso per ottenere lo status espone a perdita delle tutele e a contestazioni.

### A.2 Tabella comparativa

Leva = quella effettivamente disponibile **oggi a un residente italiano retail**. "Reg." = sede con autorizzazione UE pertinente al prodotto.

| Sede | Disponibilità legale per retail IT | Leva max retail IT | Margine isolato | Fee base maker/taker | Funding | API / test | Rischio controparte |
|---|---|---|---|---|---|---|---|
| **Hyperliquid** (DEX, L1 propria) | Non autorizzata SEE; non geo-bloccata; Italia non nei ToS vietati [8][13] | Tecnicamente fino a 40x BTC [8]; **nessuna è "regolamentata"** | Sì (`updateLeverage isCross:false`, `updateIsolatedMargin`) [22] | **0,015% / 0,045%** [23] | Oraria (NON RIVERIFICATO) | REST+WS; testnet; `scheduleCancel` [22] | Nessuna entità vigilata; 24–27 validatori, ~49% dello stake a validatori della Foundation [24]; incidenti JELLY, ADL 10/10/2025, POPCAT [25][26] |
| **Kraken Pro** (Payward, entità CySEC MiFID) | **Reg.** MiFID; perps SEE dal 05/2025; Italia: non confermato paese per paese | **10x** al livello I, poi 5x / 3,33x / 2x a scaglioni di size [5]; a rischio 2x [1] | Sì su Multi-Collateral (secondaria) [27] | NON VERIFICATO oggi (storico 0,02% / 0,05%) | NON VERIFICATO | REST+WS; demo futures; `cancelallordersafter` [28] | Gruppo USA; PoR periodica (NON RIVERIFICATO); wallet unificato può esporre lo spot alle perdite futures [27] |
| **OKX Europe** (OKX Europe Markets Ltd, MFSA) | **Reg.** MiFID; "X-Perps" = future con scadenza a 5 anni; 30 paesi SEE [6] | **10x** [6]; a rischio 2x [1] | NON VERIFICATO | **0,02% / 0,05%** (pagina OKX EU via ricerca) [29] | Meccanismo di funding presente; intervallo NON VERIFICATO | REST+WS; demo; `cancel-all-after` (NON RIVERIFICATO) | Gruppo Seychelles/Malta; PoR mensile (NON RIVERIFICATO) |
| **Coinbase** (entità MiFID UE; CySEC secondo [8], non confermato da fonte primaria) | **Reg.**; future UE dal 09/03/2026 in 26 paesi, **Italia inclusa** secondo una testata [3]; fonti discordi su retail vs solo clienti "Advanced" idonei | **10x** BTC/ETH; ~4–5x altri [3][8] | NON VERIFICATO | NON VERIFICATO | "perpetual-style" con scadenza 5 anni + dated | Advanced Trade API | Società quotata USA |
| **One Trading** (AFM, sede di negoziazione MiFID) | **Reg.** [8] | 10x [8] | NON VERIFICATO | NON VERIFICATO | — | — | Piccola; liquidità ridotta (STIMA) |
| **Robinhood EU** (esecuzione su MTF Bitstamp) | **Reg.** [8] | 10x [8] | — | — | — | Nessuna API di trading utile (NON VERIFICATO) | — |
| **Binance** | **Non disponibile**: domanda MiCA ritirata 24/06/2026; dal 01/07/2026 stop a nuovi conti e nuovi ordini per residenti SEE [8][10][11] | 0 | (sì, globalmente) | (0,02% / 0,05% globale, NON RIVERIFICATO) | 8h | Ottima; testnet `testnet.binancefuture.com` [30] | Derivati già fermati in Italia nel 2021 (NON RIVERIFICATO) |
| **Bybit** | Bybit EU (Austria, MiCA): **solo spot e margin**; MiFID richiesta 09/2025, non rilasciata; residenti SEE migrati su Bybit EU [7][8] | 0 sui perps | (sì, globalmente) | (0,02% / 0,055% globale, NON RIVERIFICATO) | 8h | Ottima; testnet; DCP [31] | **Hack 21/02/2025, ~1,5 mld $, attribuito dall'FBI a Lazarus/RPDC** [32]; clienti rimborsati |
| **Bitget** | **Nessuna licenza MiCA** al 14/10/2026; domanda FMA Austria pendente [12] | 0 regolamentata | — | (0,02% / 0,06%, NON RIVERIFICATO) | 8h | Buona | Offshore |
| **Deribit** (Coinbase dal 2025; Deribit FZE, VARA Dubai) | **NON VERIFICATO** per retail IT; fonti secondarie in conflitto [33] | — | Sì (NON RIVERIFICATO) | (0% / 0,05% BTC perp, NON RIVERIFICATO) | Continuo | Ottima; `test.deribit.com`; `private/enable_cancel_on_disconnect` [28] | Hack hot wallet 11/2022 (~28 mln $, NON RIVERIFICATO) |
| **dYdX** (chain Cosmos) | Non autorizzata; ToS vietano USA, Canada, UK (front-end) e paesi sanzionati; **nessun paese UE citato** [34] | Fino a 20–50x (NON RIVERIFICATO) | Sì (NON RIVERIFICATO) | **0,01% / 0,05%** [34] | Oraria (NON RIVERIFICATO) | Indexer REST/WS; testnet | Validatori (25 al lancio) [34]; liquidità molto inferiore a Hyperliquid (STIMA) |
| **Interactive Brokers Ireland** | **Reg.** (Central Bank of Ireland); cripto spot retail SEE dal 31/03/2026 [35] | Azioni: margine Reg-T/portfolio; **CFD: tetti ESMA 30/20/10/5/2**; future quotati: margine di borsa (STIMA 10–20x su micro-indici, ~2–3x su future BTC CME); cripto spot: 1x | n/a (margine di conto) | Cripto 0,12–0,18%, min 1,75 $ (secondaria) [35]; resto NON VERIFICATO oggi | n/a | TWS API / Client Portal / FIX; **paper account** | Broker quotato; **regime dichiarativo** in Italia [36] |
| **Alpaca** | Solo paper nel progetto | — | — | — | — | Paper API | — |

### A.3 Note per sede

**Hyperliquid**
- **FATTO VERIFICATO [23] (primaria, docs)** — Fee perps tier 0: taker 0,045%, maker 0,015%; tier per volume 14 gg (>5 M$ → 0,040/0,012 …); sconti staking HYPE dal 5% (>10 HYPE) al 40%.
- **FATTO VERIFICATO [22] (primaria)** — Ordini: campo `r` = reduceOnly; trigger `t.trigger {isMarket, triggerPx, tpsl:"tp"|"sl"}`; `grouping`: `na` | `normalTpsl` | `positionTpsl`. `updateLeverage` con `isCross:false` imposta la leva isolata; `updateIsolatedMargin` aggiunge/toglie margine. `scheduleCancel` (vedi §D.6).
- **FATTO VERIFICATO [37] (primaria)** — API wallet (agent): firmano per conto di master o sub-account; nonce per firmatario (100 più alti, finestra T−2gg…T+1g); raccomandato un agent diverso per sub-account; un agent decade se scade, è deregistrato o il conto resta senza fondi; non riusare indirizzi.
- **FATTO VERIFICATO [38] (secondarie che citano Glassnode, 03/2026)** — Validatori in AWS ap-northeast-1 (Tokyo); API dietro CloudFront; latenza ordine→fill mediana ~884 ms da Tokyo, ~1.079 ms da Ashburn; ~879 ms sono elaborazione lato server.
- **FATTO VERIFICATO [24] (secondarie, 2026)** — Set attivo salito da 4 → 16 → 21 → 24 → 27 validatori; validatori della Foundation ≈ 49,3% dello stake; nessuna dashboard pubblica on-chain per verificarlo. Fonti discordi tra 24 e 27 secondo la data.
- **FATTO VERIFICATO [25] (stampa)** — JELLY, 26/03/2025: dopo una manipolazione che aveva scaricato uno short sul vault HLP (perdita non realizzata fino a ~13,5 M$), i validatori hanno delistato il perp e regolato le posizioni a 0,0095 $. Critiche di centralizzazione ("FTX 2.0", CEO Bitget). Le cifre riportate divergono tra fonti.
- **FATTO VERIFICATO [26] (stampa)** — 10/10/2025: prima attivazione dell'ADL cross-margin in oltre due anni; stime di perdite "in eccesso" per i trader ~650 M$ (Gauntlet) contro la tesi del fondatore di un beneficio netto. 11/2025 POPCAT: perdita HLP ~4,9 M$; terzo attacco di manipolazione del 2025.
- **Conseguenza operativa (IPOTESI)**: su Hyperliquid una posizione vincente può essere chiusa d'autorità (ADL) o regolata a un prezzo deciso dai validatori. Il rischio non è solo "hack": è **discrezionalità di governance**. Capitale sulla sede = capitale che si può perdere per intero senza ricorso.
- **Termini d'uso** — **FATTO VERIFICATO solo su fonti secondarie [13]** (il testo ufficiale non è stato recuperato): "Restricted Persons" = USA (anche cittadini), Ontario, giurisdizioni sanzionate (Cuba, Iran, Corea del Nord, Siria, aree dell'Ucraina); uso di VPN per aggirare vietato (§3.1.5, versione 26/01/2025). L'Italia non compare. **Da rileggere sul testo ufficiale prima del primo deposito.**
- **Liquidità** — NON VERIFICATO oggi con dati. STIMA: BTC/ETH perp con spread di 1 tick (≈0,1–1 bps) e volumi giornalieri di miliardi di $; per ordini da centinaia/migliaia di $ lo slippage è trascurabile su tutte le sedi maggiori. Misurarlo dal book via API prima del live.

**Kraken Pro (SEE)**
- **FATTO VERIFICATO [5] (primaria, support Kraken, "Last updated: October 30, 2026")** — Margin schedule SEE: livello I 10x (IM 10%, MM 5%), II 5x, III 3,33x, IV 2x in funzione della size; ogni contratto ha una classe A–G (la mappa per contratto non è stata letta). Kraken può cambiare lo schema senza preavviso.
- **FATTO VERIFICATO [4] (stampa)** — Offerta su licenza MiFID ottenuta acquisendo una società d'investimento cipriota (CySEC); >150–300 mercati.
- **Conflitto tra fonti**: una guida sostiene che la disponibilità varia per Stato membro (Francia esclusa) [8]; nessuna fonte conferma esplicitamente l'Italia. **Verificare aprendo il conto**: è il test definitivo.
- Fee: la pagina fee generale letta oggi non riporta la tabella futures [39]. NON VERIFICATO.

**OKX Europe**
- **FATTO VERIFICATO [6]** — X-Perps lanciati 04/2026 da OKX Europe Markets Ltd (licenza MFSA n. OEML-15905), struttura a scadenza quinquennale scelta per non ricadere nella definizione di CFD; fino a 10x; retail e istituzionali; estesi a Magnificent 7, oro, argento, petrolio, SPY, QQQ (06/2026), "Simple Mode" mobile dal 28/07/2026. **Nessun regolatore ha confermato che la scadenza a 5 anni regga** [6]: se ESMA/MFSA la riqualificano, leva → 2x.
- Interessante per GERVA: **un'unica sede regolamentata con perps cripto + indici/azioni/commodity 24/7** a 10x.

**Coinbase**
- **FATTO VERIFICATO [3] (The Block e altri, 09/03/2026)** — Future regolamentati in 26 paesi europei; perpetual-style a 5 anni e contratti datati; fino a 10x. **Fonti discordi** su: inclusione dell'Italia (una sola testata la cita), accesso retail vs solo utenti Coinbase Advanced idonei, leva sugli indici (5x vs 10x).

**Binance / Bybit / Bitget** — vedi tabella. Punto fermo: **non costruire il motore live su queste tre** finché non hanno autorizzazione MiFID nello SEE. Usarle solo per **dati di mercato pubblici** (gratuiti, senza conto) e testnet.

**Bybit, hack 2025** — **FATTO VERIFICATO [32]**: 21/02/2025, ~1,5 mld $ in ETH sottratti da un cold wallet multisig; FBI (PSA 26/02/2025) attribuisce a RPDC; vettore riportato: compromissione della macchina di uno sviluppatore Safe{Wallet} e firma "cieca" di una transazione manipolata. **Lezione per GERVA**: ciò che si vede sull'interfaccia di firma può non essere ciò che si firma → hardware wallet con verifica dell'hash/indirizzo sul display.

**FTX (precedente)** — NON RIVERIFICATO oggi (fatto storico noto): 11/2022 insolvenza con fondi clienti usati dalla società collegata; i clienti hanno atteso anni. **Lezione**: una "proof of reserves" non prova le passività; il solo presidio è **tenere sulla sede il minimo**.

**Interactive Brokers**
- **FATTO VERIFICATO [35]** — 31/03/2026: IBKR lancia il trading di cripto-attività per investitori individuali SEE tramite Interactive Brokers Ireland Ltd (CASP MiCA); ~11 token. Il comunicato avverte che la disponibilità varia per paese di residenza: **Italia non confermata esplicitamente**.
- **FATTO VERIFICATO [36]** — IBKR applica ai clienti italiani il solo **regime dichiarativo** (non è sostituto d'imposta): plusvalenze, RW e IVAFE li calcola il cliente.
- **STIMA / NON RIVERIFICATO** — Future quotati (CME Micro E-mini, Micro Bitcoin/Ether, Eurex) sono accessibili al retail UE e **non sono CFD**: la leva è data dal margine di borsa/broker, non dal tetto ESMA. Per gli indici significa ~10–20x; per i future cripto CME IBKR chiede margini elevati (≈30–50% → 2–3x). È l'unico modo *pienamente regolamentato* per avere leva >5x su indici azionari da retail. Opzioni: disponibili (permessi a livelli). ETF USA non acquistabili (assenza KID/PRIIPs), opzioni su ETF USA sì.

**Broker CFD/futures UE** (IG, Saxo, Fineco, Directa, ecc.) — rilevanti solo se si vuole il regime amministrato (sostituto d'imposta) su indici/azioni; sulle cripto restano a 2:1. Non approfonditi.

### A.4 Hyperliquid e DeFi per un residente italiano: tre piani distinti

| Piano | Risposta | Livello |
|---|---|---|
| **Tecnico** ("la piattaforma me lo lascia fare?") | Sì: nessun KYC, nessun geo-blocco su IP italiani; Italia non nei ToS vietati | FATTO (fonti secondarie) [8][13] |
| **Regolamentare lato fornitore** | Nessuna autorizzazione SEE; per ESMA un perp offerto a retail UE è verosimilmente un CFD soggetto a 2:1; offrire servizi d'investimento in Italia senza autorizzazione è abusivismo. Consob può oscurare il front-end (non il protocollo) | FATTO [1][8][18][20] + IPOTESI sull'applicazione concreta a un protocollo senza sede |
| **Lato cliente** | Non ho trovato norme che vietino o sanzionino il retail che *usa* una sede estera non autorizzata. Conseguenze reali: zero tutele (nessun Arbitro/ACF, nessun fondo di garanzia, nessuna protezione saldo negativo), possibile blocco dell'accesso, e banche/exchange di on-ramp che possono chiedere spiegazioni sui flussi (antiriciclaggio) | **IPOTESI — da confermare con avvocato** |
| **Fiscale** | Obblighi pieni: redditi in dichiarazione, monitoraggio RW/W, imposta 2‰ sul valore. I DEX non sono soggetti DAC8 (STIMA), quindi **nessuno comunica per voi**: la tracciabilità on-chain resta totale e l'omissione è sanzionata | FATTO sull'obbligo [17][40]; STIMA su DAC8 |

**Giudizio senza sconti**: usare Hyperliquid da residente italiano oggi è *accessibile, non regolamentato, non espressamente vietato al cliente*, con rischio regolatorio in aumento (ESMA ha già messo il prodotto nel mirino; un articolo di settore lega esplicitamente lo statement a Hyperliquid [2bis]). Chi lo fa deve accettare che l'accesso possa sparire con breve preavviso e deve avere una procedura di uscita pronta (§B.6).

---

## B. Custodia e struttura dei conti

### B.1 Principi
1. **Nessuna chiave capace di prelevare vive sul server.** Il motore possiede solo chiavi "trade-only".
2. **Sulla sede sta solo il margine di lavoro.** Il resto in banca (EUR) o su wallet hardware.
3. **Un conto/sub-account per strategia**, così un bug o una liquidazione non contagia il resto (equivalente di conto del margine isolato).
4. **Prelievi solo verso indirizzi in allow-list**, con ritardo di attivazione dove la sede lo offre.

### B.2 Chiavi API sulle sedi centralizzate (Kraken, OKX, Coinbase, IBKR)
- Permessi: **lettura + trading**; **prelievo disattivato**; trasferimenti interni disattivati se separabili.
- **Allow-list IP**: solo l'IP fisso del VPS (e del VPS di riserva). Un IP che cambia = chiave inutilizzabile: è il comportamento voluto.
- Una chiave per processo (esecuzione ≠ monitor in sola lettura ≠ ricerca in sola lettura). Rotazione ogni 90 giorni e a ogni sospetto.
- 2FA con app TOTP o chiave FIDO2 sull'account; mai SMS. Email dedicata all'account, non usata altrove.
- Allow-list degli indirizzi di prelievo con blocco temporale (Kraken, OKX, Coinbase la offrono — NON RIVERIFICATO oggi per le entità UE).
- IBKR: utente secondario "paper"/API separato; prelievi solo verso il conto bancario intestato; Secure Login System attivo. L'API IBKR non può disporre bonifici verso terzi (NON RIVERIFICATO).

### B.3 Hyperliquid: master, agent, sub-account
- **Master key** (l'unica che può prelevare e approvare agent): generata e custodita su **hardware wallet**; mai importata su PC o VPS; seed su supporto metallico/cartaceo in due luoghi fisici.
- **Agent/API wallet** sul VPS: firma ordini, cancellazioni, leva. **FATTO VERIFICATO [37]**: "API wallets are only used to sign"; i dati del conto si interrogano con l'indirizzo reale del master/sub-account.
- **Cosa NON può fare un agent** — la pagina letta oggi non lo dice esplicitamente. **NON RIVERIFICATO**: la documentazione e l'interfaccia Hyperliquid descrivono gli agent come privi del permesso di prelievo/trasferimento (prelievi e `usdSend` richiedono la firma del master). **Azione obbligatoria prima del live**: su testnet, provare con la chiave agent a eseguire `withdraw3` e `usdSend` e verificare che vengano rifiutati; annotare l'esito nell'audit log.
- **Cosa PUÒ fare un agent compromesso** (IPOTESI ragionata): non rubare direttamente, ma **distruggere il capitale** — aprire posizioni enormi a leva massima, o fare wash-trading contro un conto dell'attaccante su un mercato illiquido trasferendogli valore. Mitigazione: capitale limitato sulla sede, sub-account per strategia, agent con scadenza, revoca immediata dal master.
- Un agent per sub-account (raccomandazione ufficiale [37], per non condividere il set di nonce). Scadenza esplicita (es. 30–90 giorni) e rinnovo manuale con il wallet hardware.
- Sub-account: NON RIVERIFICATO — storicamente richiedono una soglia di volume cumulato; se non disponibili, usare **indirizzi master distinti** per strategia (ognuno con il suo agent).
- Bridge: deposito/prelievo in USDC via Arbitrum (commissione di prelievo ~1 $, NON RIVERIFICATO). Il bridge è custodito dal set di validatori: è un rischio aggiuntivo rispetto al book.

### B.4 Quanto capitale tenere dove (STIMA, regola proposta)
| Stadio | Sulla sede (totale) | Riserva | Regola |
|---|---|---|---|
| Paper → primi 30 gg live | 5–10% del capitale (500–1.000 €) | banca | size minima, serve a validare esecuzione e fisco |
| Live a regime, ≤50 k€ | **20–30%** (margine delle posizioni × 2–3) | 70–80% in banca/EUR o conto IBKR | rabbocco settimanale manuale, mai automatico |
| Sede non regolamentata (Hyperliquid) | **mai più di quanto si accetta di perdere al 100%**; tetto proposto 10–15% del patrimonio di progetto | — | prelievo dei profitti sopra soglia ogni settimana |

Con margine isolato la perdita per trade è già limitata al margine: tenere sulla sede più di 2–3 volte la somma dei margini aperti non aggiunge nulla al motore e aumenta solo il rischio di controparte.

### B.5 Procedura depositi/prelievi (manuale, a due passaggi)
1. Bonifico SEPA dal conto intestato al titolare verso la sede regolamentata (Kraken/OKX/Coinbase) — causale chiara; conservare contabile.
2. (Solo se si usa Hyperliquid) acquisto USDC sulla sede regolamentata → prelievo su **indirizzo in allow-list** = wallet hardware su Arbitrum → *transazione di prova di 10 $* → deposito nel bridge firmando dall'hardware wallet, verificando indirizzo e importo **sul display del dispositivo**.
3. Prelievo: percorso inverso; EUR sempre e solo verso il conto bancario intestato.
4. Ogni movimento va registrato lo stesso giorno in un registro (data, importo, tx hash, controvalore EUR, cambio) — serve al calcolo fiscale (§C.1) e all'audit.
5. Mai depositi/prelievi avviati dal software. Mai chiavi di prelievo su macchine connesse al motore.
Nota fiscale: ogni conversione BTC/ETH→USDC è evento imponibile (§C.1); EUR→USDC→EUR genera differenze di cambio imponibili sulla parte in USDC.

### B.6 Piano di uscita da una sede (da scrivere prima di entrare)
Trigger: annuncio di restrizione per residenti UE/Italia, blocco prelievi > 2 h, depeg USDC > 2%, incidente di governance, oscuramento Consob. Azione: chiudere le posizioni (reduce-only), revocare gli agent, prelevare tutto dal master, documentare.

---

## C. Veicolo giuridico e fiscale (Italia)

### C.1 Persona fisica — regime dichiarativo

**Aliquote**
- **FATTO VERIFICATO [14][15][16] (secondarie concordi; testo di legge non letto direttamente)** — Plusvalenze e altri proventi da cripto-attività (art. 67 c.1 lett. c-sexies TUIR): **26% fino al 31/12/2025, 33% dal 01/01/2026** (L. 207/2024, art. 1 c. 24). La L. 199/2025 (Bilancio 2026) conferma il 33% e mantiene il **26% solo per i token di moneta elettronica denominati in euro** conformi a MiCAR, e solo quando l'EMT in euro è il bene ceduto (convertire BTC in EMT-euro resta al 33%). USDT/USDC: 33%. **Franchigia di 2.000 € abolita** (dal 2025).
- **Conflitto tra fonti**: alcune guide scrivono ancora "33% sopra i 2.000 €" o "26%" — sono datate. Un emendamento al Milleproroghe (D.L. 200/2025) proponeva di rinviare il 33% al 2027: **non risulta approvato** nelle misure convertite [16]; non ho trovato il resoconto parlamentare che lo boccia formalmente.
- **NON VERIFICATO** — Non ho trovato notizie su modifiche nel disegno di legge di bilancio 2027 (in discussione in queste settimane). **Ricontrollare a fine dicembre 2026.**
- **FATTO VERIFICATO [17] (primaria: testo della circolare AdE 30/E del 27/10/2023, § 2.3.2 e § 3)** — "In generale, i redditi derivanti da contratti derivati, ancorché aventi come sottostante cripto-attività, costituiscono redditi diversi ai sensi dell'articolo 67, comma 1, lettera c-quater), del Tuir"; per i CFD su cripto: quadro RT, **imposta sostitutiva 26%**, "tali contratti non rientrano nell'ambito di applicazione della lettera c-sexies)". Base imponibile (art. 68 c. 8): somma algebrica di differenziali positivi/negativi e altri proventi/oneri.
- **Zona grigia (IPOTESI)** — La circolare parla di CFD e future, non di *perpetual*; non considera perps regolati in stablecoin su un protocollo senza controparte identificata. La lettura più coerente è c-quater (26%) anche per i perps; ma (i) una guida del 09/11/2026 afferma che non c'è ancora una pronuncia sui derivati cripto dopo il passaggio al 33% [8]; (ii) l'Agenzia potrebbe sostenere che un perp su DEX non è uno "strumento finanziario derivato" ex TUF e ricondurlo a c-sexies (33%). **Differenza: 7 punti percentuali sul risultato netto. Punto n. 1 per il commercialista; valutare un interpello.**
- Il funding pagato/incassato e le commissioni sono, in c-quater, "altri proventi od oneri" del rapporto (IPOTESI coerente con art. 68 c. 8).

**USDC come margine: il secondo strato di imposta**
- **FATTO VERIFICATO [17]** — La permuta tra cripto-attività "aventi eguali caratteristiche e funzioni" non è imponibile; ma "la permuta tra una cripto-valuta e un e-money token … è fiscalmente rilevante".
- Conseguenze (IPOTESI): EUR→USDC non realizza nulla; USDC→EUR realizza la differenza di cambio sulla quantità ceduta (c-sexies, 33%, anche se piccola); il P&L dei perps accreditato in USDC entra con costo fiscale pari al valore normale del giorno. Servono un software di contabilità cripto e il registro di §B.5.

**Minusvalenze**
- **FATTO VERIFICATO [17]** — Le minusvalenze c-sexies eccedenti si portano in deduzione **nei quattro periodi d'imposta successivi**, dai redditi della stessa lettera, se indicate in dichiarazione. (L'esempio della circolare con la franchigia di 2.000 € è superato.)
- **NON RIVERIFICATO / IPOTESI** — Le perdite da derivati (c-quater) si compensano con plusvalenze c-bis…c-quinquies (azioni, obbligazioni, derivati, anche su IBKR) e si riportano per 4 anni; **non** si compensano con le plusvalenze cripto c-sexies e viceversa. Quindi una perdita sui perps non abbatte un guadagno su BTC spot. Da confermare.

**Monitoraggio e patrimoniali**
- **FATTO VERIFICATO [17][40]** — Quadro **RW** (quadro W nel 730): un rigo per ogni portafoglio/conto/wallet; vale anche per wallet self-custody. **Imposta sul valore delle cripto-attività (IVCA) 2‰ annuo** sul valore al 31/12 per le cripto non già soggette a bollo (exchange esteri, wallet privati, DeFi): si autoliquida in dichiarazione. Redditi in quadro **RT** (T nel 730).
- **NON RIVERIFICATO** — Conto IBKR: **IVAFE** 2‰ sul valore dei prodotti finanziari, 34,20 € fissi sulla liquidità di conto corrente oltre giacenza media 5.000 €; RW sempre.
- **FATTO VERIFICATO [14] (secondaria)** — **DAC8** (Dir. UE 2023/2226, recepita con D.Lgs. 194/2025) operativa dal 01/01/2026: gli operatori cripto autorizzati comunicano automaticamente i dati dei clienti al fisco. Kraken/OKX/Coinbase/IBKR: l'Agenzia vedrà i conti.
- **FATTO VERIFICATO [36]** — IBKR: solo regime dichiarativo.

**Altre note**
- Trading sistematico come attività d'impresa? **IPOTESI**: la prassi tratta il trading del privato su strumenti finanziari come reddito diverso anche se frequente; un'organizzazione stabile (server, software, eventuali collaboratori, raccolta da terzi) può però essere letta come attività commerciale (art. 55 TUIR) con IRPEF progressiva e INPS. Con capitale proprio e nessun terzo il rischio è basso; chiedere.
- Costo: commercialista esperto di cripto + broker estero **STIMA 300–800 €/anno**; software fiscale cripto **STIMA 50–200 €/anno**.

### C.2 SRL / SRLS / holding
- **NON RIVERIFICATO (regole note)** — IRES 24% sull'utile; IRAP 3,9% (base e aliquota dipendono dalla qualifica: una società che detiene prevalentemente partecipazioni/attività finanziarie ha regole proprie); dividendi al socio persona fisica: ritenuta 26%. Carico complessivo in caso di distribuzione ≈ **1 − (0,76 × 0,74) = 43,8%** (+ IRAP). Senza distribuzione: 24% (+IRAP), ma il denaro resta nella società.
- **FATTO VERIFICATO [41] (secondaria)** — Cripto in bilancio d'impresa: IRES ordinaria 24% ed eventuale IRAP; le **variazioni di valore a fine esercizio non rilevano fiscalmente** (art. 110 c. 3-bis TUIR), rileva il realizzo; risposta AdE n. 78/2025 sul metodo di valutazione.
- **Vantaggi reali**: compensazione piena tra tutti i tipi di risultato (perps, spot, azioni) e deducibilità dei costi (VPS, dati, API LLM, commercialista); perdite riportabili senza limite di tempo (entro l'80% dell'utile, NON RIVERIFICATO); responsabilità limitata.
- **Svantaggi**: costi fissi; doppia tassazione in uscita; LEI obbligatorio per operare in derivati (STIMA 50–90 €/anno); obblighi EMIR/MiFIR di segnalazione da chiarire; conti "business" su exchange con onboarding più pesante; **disciplina delle società di comodo** (art. 30 L. 724/1994, coefficienti ridotti dal 2024 — NON RIVERIFICATO): una SRL con soli attivi finanziari e ricavi bassi/perdite rischia un reddito minimo presunto.
- **Il trading in conto proprio di una società è attività riservata?** **FATTO VERIFICATO in parte [42]**: la negoziazione per conto proprio è attività d'investimento MiFID, ma esiste un'esenzione per chi negozia esclusivamente per conto proprio; l'esenzione **non** vale per i market maker e — NON RIVERIFICATO nel dettaglio (art. 2(1)(d) MiFID II / art. 4-terdecies TUF) — per chi è membro/partecipante di un mercato regolamentato o MTF o ha accesso elettronico diretto, per chi applica **tecniche di negoziazione algoritmica ad alta frequenza**, e per chi esegue ordini di clienti. **Punti da far verificare all'avvocato**: (i) barre da 5 minuti non sono HFT in senso MiFID (richiede colocation/latenze minime e alto traffico infragiornaliero di messaggi), ma il motore è "negoziazione algoritmica"; (ii) operare su una sede come Kraken/One Trading/OKX rende la società "partecipante a un MTF"? Per le cripto spot (non strumenti finanziari) la riserva MiFID non si applica; rileva MiCA solo se si prestano servizi a terzi.
- **Costi (STIMA)**: costituzione SRL ordinaria 1.500–2.500 € (notaio, imposte, CCIAA); SRLS 300–700 €; annui: commercialista 1.800–3.500 €, diritto camerale ~120 €, tassa libri sociali 309,87 €, PEC/firma/bolli ~150 €, eventuale INPS del socio amministratore (da verificare caso per caso). **Totale realistico 2.500–4.500 €/anno = 21–45% di un capitale di 10–12 k€.**
- **Conclusione**: non prima di ~150–200 k€ di capitale o di un reddito da trading tale da giustificare la deducibilità dei costi e la pianificazione della distribuzione.

### C.3 Società semplice
- **FATTO VERIFICATO [43]** — Può esercitare solo attività economiche **non commerciali** (art. 2249 c.c.); reddito imputato ai soci per trasparenza (art. 5 TUIR).
- **IPOTESI** — I redditi finanziari mantengono la natura di redditi diversi (26%/33%) in capo ai soci; nessun vantaggio d'aliquota. Utile solo come contenitore di patrimonio familiare con regole tra soci. Rischi: se il trading è letto come attività commerciale, riqualificazione in s.n.c. di fatto (responsabilità illimitata, reddito d'impresa); se raccoglie da più persone per investire secondo una politica predefinita, rischio di qualificazione come **organismo di investimento collettivo** gestito senza autorizzazione. Costi STIMA: atto 500–1.500 €, 800–1.500 €/anno.
- Non raccomandata a questo stadio.

### C.4 Trust
- **NON RIVERIFICATO** — Costi di istituzione STIMA 3.000–10.000 € + trustee e contabilità annui; tassazione per trasparenza (beneficiari individuati) o opaca (IRES 24%); se il disponente mantiene il controllo sul patrimonio, il fisco lo considera **interposto** e tassa il disponente come se il trust non esistesse. Un trust "autogestito" per fare trading è il caso di scuola dell'interposizione. **Inutile e costoso per questo progetto.**

### C.5 Strutture offshore — perché non funzionano per un residente con 10 k€
- **NON RIVERIFICATO sul testo aggiornato; norme note**:
  - **Residenza della persona**: resta fiscalmente residente in Italia chi per la maggior parte dell'anno ha qui domicilio (relazioni personali e familiari), residenza civilistica o presenza fisica, o è iscritto all'anagrafe (presunzione relativa dal 2024). L'iscrizione AIRE non basta; per i paesi a fiscalità privilegiata l'onere della prova è invertito (art. 2 c. 2-bis TUIR). Il residente è tassato sui redditi **ovunque prodotti**.
  - **Esterovestizione (art. 73 c. 3 TUIR)**: una società estera è residente in Italia se qui ha sede legale, **sede di direzione effettiva** o **gestione ordinaria in via principale**. Una LLC/Ltd il cui unico amministratore decide e fa girare il motore da casa in Italia è una società italiana: IRES, sanzioni per omessa dichiarazione, possibile rilevanza penale sopra soglia.
  - **CFC (art. 167 TUIR)**: se un residente controlla un soggetto estero con tassazione effettiva inferiore alla metà di quella italiana (o test semplificato del 15%) e oltre un terzo di proventi "passivi" (redditi finanziari: è esattamente il caso del trading), il reddito è imputato per trasparenza al socio italiano e tassato in Italia.
  - **Monitoraggio**: partecipazioni e conti esteri in RW; scambio automatico CRS/DAC8.
- **Economia**: società offshore + agente + conto + contabilità = STIMA 2.000–6.000 €/anno, senza alcun beneficio fiscale lecito finché il titolare vive in Italia. L'unica via reale è **trasferire davvero la vita all'estero** (casa, famiglia, >183 giorni, cancellazione anagrafica), il che è una scelta di vita, non una struttura.
- **Giudizio**: per un residente con 10 k€ l'offshore è costo certo + rischio sanzionatorio/penale + zero risparmio.

### C.6 Gestire denaro di terzi
- **FATTO VERIFICATO [18]** — **Art. 166 TUF (abusivismo)**: reclusione **da uno a otto anni** e multa da 4.000 a 10.000 € per chi, senza abilitazione, svolge servizi o attività di investimento o di gestione collettiva del risparmio (alcune fonti online riportano ancora la vecchia pena 6 mesi–4 anni: è superata). Reato di pericolo presunto: non serve il danno. La riserva (art. 18 TUF) riguarda l'esercizio **professionale nei confronti del pubblico**; occasionalità e non professionalità possono escludere il reato, "ma il confine non è sempre nitido": gratuità e cerchia familiare non sono garanzia.
- **FATTO VERIFICATO [44]** — Cassazione (richiamata da stampa giuridica): se l'"analista" gestisce di fatto il capitale dei clienti, è intermediazione abusiva; il reato si consuma in Italia anche con investimenti esteri.

| Modello | Stato | Fattibilità per GERVA |
|---|---|---|
| **Denaro dei familiari donato/prestato al titolare**, che opera in proprio | Non è gestione per terzi: il denaro è suo. Prestito infruttifero tra familiari con scrittura datata e bonifico tracciato; **nessuna partecipazione agli utili** (altrimenti torna la zona grigia) | **Unica via pulita oggi** — IPOTESI da confermare con commercialista (donazioni, prova della provenienza) |
| Delega/procura sul conto intestato al familiare, gratuita, senza sollecitazione | Zona grigia tollerata se davvero occasionale e familiare; diventa art. 166 con compenso, pluralità di deleganti, pubblicità | Sconsigliata con un motore automatico e leva |
| **IBKR "Friends and Family" advisor** | **FATTO VERIFICATO [45]**: è una *struttura di conto*, riservata a consulenti **esenti da registrazione** che gestiscono per non professionali (familiari/amici); il titolare master **non può addebitare commissioni** (pagina HK) e non può sollecitare clienti né presentarsi come consulente; limite di 15 clienti citato solo da un forum (regola USA), 5 nomi nella versione Singapore. **Non crea alcuna esenzione nel diritto italiano**: la pagina irlandese non è stata letta (403) | Solo familiari stretti, gratis, e dopo parere legale |
| **Copy trading / strategy provider / vault** | **FATTO VERIFICATO [46]**: ESMA (briefing 30/03/2023) qualifica il copy trading come gestione di portafogli (esecuzione automatica dei segnali = discrezionalità) o consulenza; per le cripto vale per analogia sotto MiCA. Un **vault Hyperliquid** aperto al pubblico con profit share è, in sostanza, gestione (collettiva) senza autorizzazione se rivolto a italiani (IPOTESI forte) | No, senza veicolo autorizzato |
| **Vendita di segnali/newsletter** | Raccomandazioni generalizzate = non riservato; raccomandazioni personalizzate = consulenza riservata; promesse di rendimento = pratiche scorrette | Possibile solo come informazione generica; parere legale |
| **Consulente finanziario autonomo (albo OCF)** | NON RIVERIFICATO: esame + requisiti; solo consulenza a parcella; **non può detenere denaro dei clienti né eseguire in autonomia** | Non risolve la gestione |
| **SGR / GEFIA sotto soglia** | **FATTO VERIFICATO [47]**: capitale minimo 50.000 € (vs 1 M€); dal **29/04/2026** (D.Lgs. 27/03/2026 n. 47, G.U. n. 86 del 14/04/2026) i nuovi gestori sotto soglia seguono un regime di **registrazione** presso Banca d'Italia (art. 35-quaterdecies TUF) invece dell'autorizzazione; i gestori registrati possono gestire **solo FIA chiusi riservati** a professionali o a soggetti con elevata disponibilità patrimoniale, orientati all'economia reale (PE/VC/immobiliare); la procedura di dettaglio è demandata a Banca d'Italia | **Non adatta** a un fondo liquido di trading cripto/derivati aperto a familiari retail. Costi di struttura STIMA ≥100–250 k€/anno |
| **SICAF / FIA riservato** | NON RIVERIFICATO: FIA riservato = investitori professionali o non professionali con ticket minimo 500.000 € (ridotto a 100.000 € a condizioni, DM 30/2015 modificato nel 2022); SICAF in gestione esterna richiede una SGR | Solo >500 k€ per investitore e con SGR partner |
| **EuVECA** | Venture capital in PMI non quotate | Irrilevante |
| **"Incubator fund" offshore (BVI/Cayman)** | **Mito**: l'esenzione vale nel paese del fondo, non in Italia. Gestire dall'Italia = esterovestizione + gestione abusiva; offrire a italiani = commercializzazione non autorizzata | No |
| **Piattaforme "prop firm"** | Si paga per un conto simulato; non è gestione di denaro di terzi ma nemmeno capitale vero; controparte non vigilata | Fuori scopo |

### C.7 Percorso raccomandato per stadio di capitale

| Stadio | Veicolo | Sedi | Note |
|---|---|---|---|
| **≤ 50 k€ (oggi)** | **Persona fisica**, regime dichiarativo; denaro dei familiari solo come donazione/prestito infruttifero documentato | IBKR (indici/azioni/opzioni/future) + **una** sede MiFID per perps cripto (Kraken o OKX, max 10x) + eventuale quota piccola e a perdere su Hyperliquid se e solo se si accetta §A.4 | Commercialista con esperienza cripto dal primo mese live; registro movimenti; interpello sui perps se i volumi crescono |
| **50–500 k€** | Ancora persona fisica finché il capitale è proprio. Valutare **SRL** quando: costi deducibili rilevanti, utili da reinvestire senza distribuzione, o necessità di separare il rischio. Verificare esenzione conto proprio, LEI, società di comodo | Come sopra; status professionale possibile solo con 2 criteri su 3 | Parere legale scritto prima di costituire |
| **> 500 k€ (proprio)** | SRL/holding con consulente fiscale strutturato; possibile cliente professionale su richiesta (criterio portafoglio) → accesso a leva oltre i tetti retail su sedi regolamentate | Sedi regolamentate con status professionale; prime broker | Rinuncia consapevole alle tutele retail |
| **Denaro di terzi (qualsiasi importo)** | Nessuna scorciatoia. Opzioni: (a) diventare gestore *presso* un intermediario autorizzato (SGR/SIM che ospita la strategia: "fondo in delega", conto gestito sotto la loro licenza); (b) licenziare il software/segnali a un soggetto autorizzato; (c) FIA riservato con SGR partner da qualche milione in su | — | Track record certificato in conto proprio (estratti conto delle sedi regolamentate) è il prerequisito commerciale |

### C.8 Domande da portare ai professionisti

**Al commercialista**
1. Perpetual su cripto (Kraken/OKX "a scadenza 5 anni" e Hyperliquid): lett. c-quater al 26% (circ. 30/E § 2.3.2) o c-sexies al 33%? È opportuno un interpello?
2. Funding e commissioni: confermati come "altri proventi/oneri" ex art. 68 c. 8? Calcolo "per ciascun rapporto"?
3. Margine in USDC: come determinare costo e valore normale; la conversione USDC→EUR è imponibile al 33% anche per differenze minime; il P&L accreditato in USDC ha costo pari al valore del giorno?
4. Compensazioni: perdite c-quater (perps, future IBKR) contro plusvalenze c-sexies (spot)? Riporto quadriennale e indicazione in RT.
5. RW/IVCA per: conto Kraken/OKX (entità UE), wallet hardware, saldo su Hyperliquid (che "stato estero" indicare?), conto IBKR (IVAFE).
6. Regime: per il conto presso una sede UE è possibile/opportuna l'opzione per il regime amministrato tramite un intermediario italiano? Per ora dichiarativo ovunque?
7. Esiste il rischio che trading algoritmico sistematico sia riqualificato come reddito d'impresa/lavoro autonomo? Indicatori da evitare.
8. Denaro dei familiari: donazione o prestito infruttifero? Forma, data certa, imposta di registro, prova in caso di accertamento sintetico.
9. Deducibilità zero dei costi (VPS, dati, LLM) da persona fisica: confermato? A che livello di costi/utili conviene la SRL (simulazione numerica)?
10. SRL: IRAP applicabile, società di comodo con attivi solo finanziari, trattamento dei derivati cripto in bilancio, LEI, riporto perdite.
11. Novità della legge di bilancio 2027 su cripto e redditi finanziari.
12. Software/formato di reportistica che lo studio accetta (export per RT/RW).

**All'avvocato (diritto dei mercati finanziari)**
1. Uso di Hyperliquid/dYdX da residente italiano: esiste un profilo di illecito *per il cliente*? Effetti dello statement ESMA 24/02/2026 e di un eventuale oscuramento Consob.
2. La leva 10x di Kraken/OKX/Coinbase UE è stabile? Cosa succede alle posizioni aperte se la sede passa a 2x?
3. Cliente professionale su richiesta: requisiti concreti presso ciascuna sede; conseguenze di un'autocertificazione imprecisa.
4. Familiari: confine tra delega familiare gratuita e art. 166 TUF; il prestito infruttifero al titolare elimina il problema? E un prestito con partecipazione agli utili?
5. IBKR Family/Friends & Family per IBKR Ireland in Italia: è utilizzabile senza abilitazione? Limiti.
6. SRL in conto proprio: esenzione ex art. 4-terdecies TUF con negoziazione algoritmica non-HFT; partecipazione a MTF; obblighi EMIR/MiFIR.
7. Pubblicare risultati, codice, segnali o un vault: quando diventa consulenza, gestione, offerta al pubblico o commercializzazione di OICR?
8. Percorso minimo per gestire capitali di terzi: ospitalità presso SGR/SIM, gestore sotto soglia registrato (D.Lgs. 47/2026), tempi e costi reali.
9. Antiriciclaggio: come documentare l'origine dei fondi e i flussi cripto per evitare blocchi bancari.

---

## D. Stack tecnico per un motore 24/7

### D.1 Dove stanno le sedi
| Sede | Posizione dell'infrastruttura | Livello |
|---|---|---|
| Hyperliquid | Validatori in **AWS ap-northeast-1 (Tokyo)**, API dietro CloudFront | FATTO (stampa che cita Glassnode, 03/2026) [38] |
| Binance | Infrastruttura principale in AWS Tokyo | FATTO debole (stessa stampa) [38] |
| BitMEX | Migrata da AWS Dublino a Tokyo, 08/2025 | FATTO (stampa) [38] |
| Bybit | AWS Singapore (ap-southeast-1) | NON RIVERIFICATO |
| OKX (globale) | Alibaba Cloud Hong Kong | NON RIVERIFICATO; l'entità UE può differire |
| Kraken Futures / OKX EU / Coinbase EU | — | NON VERIFICATO |
| Deribit | Equinix LD4 (Londra) | NON RIVERIFICATO |
| IBKR | Il Gateway/TWS gira sul vostro server e si collega ai server IBKR (per conti europei: Europa) | NON RIVERIFICATO nel dettaglio |

### D.2 La latenza conta per barre da 5 minuti a giornaliere? **No.**
- **FATTO [38]**: su Hyperliquid il tempo ordine→fill mediano è ~0,9 s *anche da Tokyo*, quasi tutto lato server; stare in Europa aggiunge ~0,2–0,3 s.
- Su una barra da 5 minuti (300 s) 0,3 s sono lo 0,1% dell'intervallo. Lo slippage dipende da spread e profondità, non dalla regione del VPS.
- Conta invece: **stabilità della connessione**, sincronizzazione dell'orologio (chrony/NTP; i nonce Hyperliquid e le firme Binance/Bybit hanno finestre temporali), IP fisso per le allow-list.
- Scelta: VPS **in UE** (vicino a IBKR/Kraken, giurisdizione e fatturazione semplici). Tokyo solo se in futuro si scende sotto il minuto.

### D.3 Prezzi (mensili, IVA esclusa)
| Fornitore / piano | Prezzo | Livello |
|---|---|---|
| **Hetzner CX23** (2 vCPU, 4 GB, UE) | **5,49 €** + IPv4 ≈ 5,99 € dopo due rincari 2026 (1/4 e 15/6; prima 3,99 €). CX22 sostituito da CX23. Una fonte segnala piani cost-optimized non ordinabili al 20/10/2026 | FATTO (secondarie) [48]; disponibilità NON VERIFICATA |
| **Vultr Tokyo** 2 vCPU / 4 GB | 36 $ secondo un aggregatore (03/11/2026); listino storico 20–24 $ | Fonte unica, **NON VERIFICATO** [49] |
| **AWS Lightsail** | 3,50 $ (solo IPv6) / 5 $ (0,5 GB, IPv4); 2 GB ≈ 12 $, 4 GB ≈ 24 $ | Primi due FATTO [50]; gli altri NON RIVERIFICATI |
| **OVHcloud VPS-1** | STIMA 4–7 € | NON VERIFICATO |
| AWS EC2 t4g.small Tokyo | STIMA 15–20 $ + traffico | NON VERIFICATO |

### D.4 Componenti raccomandati
| Tema | Minimo (raccomandato ora) | Alternativa migliore / più costosa |
|---|---|---|
| Linguaggio | **Python 3.12 + asyncio** per tutto (coerente con la ricerca; parità paper/live con lo stesso codice) | Rust solo per il percorso di esecuzione se si scende a barre < 1 min o a market making. Oggi sarebbe complessità senza ritorno |
| Database | **SQLite (WAL)** per stato, ordini, fill, audit; **Parquet** per le serie storiche (già in uso) | Postgres (+TimescaleDB) quando ci sono più processi scrittori o dashboard concorrenti |
| Coda | **Nessuna**: un processo, `asyncio.Queue` interna | Redis Streams o NATS quando esecuzione, segnali e monitor diventano processi/host separati |
| Supervisione | **systemd** (`Restart=always`, `WatchdogSec`, `MemoryMax`, utente dedicato, `ProtectSystem=strict`) | Docker Compose con immagini fissate per digest; utile per riproducibilità, non necessario |
| Monitoraggio | **healthchecks.io** (heartbeat ogni minuto dal ciclo principale, piano gratuito) + notifiche **Telegram/ntfy** su: ordine, fill, errore, drawdown, heartbeat mancato | Prometheus + Grafana (o Grafana Cloud free) + Alertmanager; uptime esterno |
| Orologio | chrony, allarme se offset > 250 ms | — |
| Backup | `sqlite3 .backup` ogni ora → cifrato con **age** → storage esterno (Backblaze B2 / Hetzner Storage Box); prova di ripristino mensile | Replica continua (Litestream) |
| Audit log | Tabella append-only + file JSONL con hash concatenati (ogni riga include l'hash della precedente): segnale → decisione → richiesta firmata (senza segreti) → risposta della sede → fill; copia giornaliera fuori dal server | Log firmati e archiviati su storage WORM |
| Riconciliazione | Ogni minuto: posizioni/ordini della sede vs stato interno; divergenza → stop nuove aperture + allarme | — |

### D.5 Failover
- **Regola base: la protezione deve stare sulla sede, non sul server.** Ogni ingresso nasce con il suo stop *reduce-only* già a riposo sull'exchange (Hyperliquid: `grouping:"normalTpsl"` o `"positionTpsl"`, ordine trigger `tpsl:"sl"` con `r:true` [22]); margine isolato = perdita massima nota anche se lo stop salta su un gap.
- **Secondo VPS (altro fornitore/regione) con dead-man switch**: non esegue strategie; controlla l'heartbeat del primario e, se manca da N minuti, (a) avvisa, (b) opzionalmente cancella gli ordini di ingresso pendenti e mette il sistema in "solo riduzione". **Mai due motori attivi insieme** (rischio di ordini doppi): passaggio manuale o con lock esplicito.
- Dopo un riavvio il motore riparte **sempre** dalla riconciliazione con la sede, mai dallo stato locale.

### D.6 Protezioni lato exchange (verificate)
| Sede | Funzione | Chiamata | Dettagli | Livello |
|---|---|---|---|---|
| **Hyperliquid** | Dead man's switch | `POST /exchange`, azione `{"type":"scheduleCancel","time":<ms>}` | `time` almeno **5 s** nel futuro; senza `time` rimuove la programmazione; **max 10 attivazioni al giorno** (reset 00:00 UTC); disponibile solo sull'API pubblica ufficiale, non su nodi di terzi | **FATTO (primaria)** [22] |
| **Binance** USDⓈ-M / COIN-M | Auto-Cancel All Open Orders | `POST /fapi/v1/countdownCancelAll` (`symbol`, `countdownTime` in ms) — percorso NON RIVERIFICATO oggi | Va richiamata come heartbeat; `countdownTime=0` ferma il timer; per simbolo. Esiste una variante "kill-switch" per le opzioni | Esistenza e comportamento **FATTO** [30]; non utilizzabile da residenti IT |
| **Bybit** | Disconnect Cancel All (DCP) | `POST /v5/order/disconnected-cancel-all` (`timeWindow` 3–300 s, default 10 s; `product`: OPTIONS default / DERIVATIVES / SPOT) | Si attiva alla disconnessione del **WebSocket privato**, che deve sottoscrivere il topic `dcp`. Il riassunto della pagina indica che l'attivazione può richiedere il client manager / clienti istituzionali: **da rileggere** | **FATTO (primaria)** [31], con riserva sull'accesso retail |
| **Kraken Futures** | Dead Man's Switch | `POST /cancelallordersafter` (`timeout` in secondi) | Va rinnovata; disattivarla prima delle manutenzioni programmate (alla ripartenza del motore di matching cancella tutto). Spot WS v2: `cancel_all_orders_after`, consigliato richiamo ogni 15–30 s con timeout 60 s | **FATTO (primaria)** [28] |
| **Deribit** | Cancel on Disconnect | `private/enable_cancel_on_disconnect` (scope connection/account) | Non scatta con logout "pulito"; non tocca ordini creati da altre connessioni | **FATTO (primaria)** [28] |
| **OKX** | Cancel All After | `POST /api/v5/trade/cancel-all-after` (`timeOut` 10–120 s, 0 disattiva) | — | **NON RIVERIFICATO** |
| **IBKR** | Nessun dead-man nativo | — | Usare ordini bracket/OCA residenti sui server IBKR, `outsideRth`, e limiti di rischio di conto | NON RIVERIFICATO |

**Avvertenza critica (IPOTESI da testare su testnet/demo per ogni sede)**: un "cancel all" può cancellare **anche gli stop protettivi**. Prima del live verificare se `scheduleCancel` / `cancelallordersafter` / DCP rimuovono gli ordini trigger reduce-only. Se sì, il dead-man switch va usato **solo** nelle fasi con ordini d'ingresso pendenti, oppure non usato affatto, lasciando la protezione a stop + margine isolato. Il limite di 10 attivazioni/giorno di Hyperliquid va gestito (non far scattare il timer per errore).

### D.7 Ambienti di prova
Hyperliquid testnet; Binance futures testnet (`testnet.binancefuture.com` [30]); Bybit testnet; OKX demo trading (anche X-Perps secondo una recensione [29]); Kraken Futures demo; Deribit `test.deribit.com`; IBKR paper; Alpaca paper. NON RIVERIFICATI oggi salvo dove indicato. I testnet hanno liquidità e funding irrealistici: validano il codice, non la strategia.

Limiti di frequenza (NON RIVERIFICATI oggi, da documentazione): Hyperliquid ~1.200 "weight"/min per IP su REST più limiti per indirizzo legati al volume; Binance futures 2.400 weight/min; Bybit e OKX per endpoint. Per barre ≥ 5 min non sono vincolanti: usare WebSocket per i dati e REST per gli ordini.

### D.8 Configurazioni
**Minima raccomandata (~10–15 €/mese)**: 1 VPS UE 2 vCPU/4 GB (Hetzner CX23 o equivalente OVH) con IP fisso · Python/asyncio in un solo servizio systemd · SQLite + Parquet · healthchecks.io gratuito + bot Telegram · backup cifrato su object storage (1–3 €) · stop sulla sede + margine isolato.

**Migliore (~40–80 €/mese)**: 2 VPS di fornitori diversi (primario UE, secondario UE o Tokyo) · Postgres · Prometheus/Grafana · Tailscale · backup con Litestream · uptime esterno · secondo canale di allarme (chiamata/SMS). Ha senso sopra ~50 k€ o con più sedi live.

---

## E. Sicurezza

### E.1 Gestione delle chiavi
- Segreti **mai in git** (neanche cifrati male, neanche in branch): `.gitignore` + pre-commit con scanner (gitleaks/trufflehog) + secret scanning del repository.
- A riposo: **sops + age**; la chiave age del server sta solo sul server (permessi 600, utente del servizio). In memoria: caricati all'avvio via `systemd LoadCredential`/EnvironmentFile non leggibile da altri utenti.
- Alternativa: secrets manager (Infisical, Doppler, AWS Secrets Manager) — utile con più host, superfluo con uno.
- Chiave master Hyperliquid e seed: solo hardware wallet e backup fisico; mai fotografati, mai in cloud, mai in un password manager sincronizzato.
- Chiavi LLM/API dati separate da quelle di trading; budget e limiti di spesa impostati dal fornitore.

### E.2 Separazione dei ruoli
| Ruolo | Dove gira | Cosa può fare |
|---|---|---|
| **Ricerca** (backtest, agenti LLM, notebook) | PC/sandbox | Solo dati pubblici e chiavi in sola lettura; **nessun accesso al VPS di esecuzione né alle chiavi di trading** |
| **Esecuzione** | VPS | Chiavi trade-only con IP allow-list; nessun prelievo |
| **Prelievo/tesoreria** | Titolare, hardware wallet + 2FA | Unico a muovere fondi, a mano |
Un agente LLM non deve mai avere in contesto chiavi di trading né poter scrivere sul ramo/artefatto che va in produzione senza revisione umana. Il rilascio in produzione è un passo manuale (tag firmato → deploy).

### E.3 Supply chain
- Dipendenze **fissate con hash** (`uv lock`/`pip-compile --generate-hashes`, installazione con `--require-hashes`); aggiornamenti deliberati, mai automatici in produzione; `pip-audit` periodico.
- Poche dipendenze sul percorso di esecuzione; SDK ufficiali delle sedi a versione fissata, letti almeno una volta nella parte di firma.
- Diffidare di pacchetti con nomi simili (typosquatting) e di "bot"/estensioni che chiedono chiavi. Il caso Bybit [32] nasce da una macchina di sviluppo compromessa.
- Build riproducibile: stessa lockfile in paper e live.

### E.4 Protezione dai bug (controlli pre-ordine, in codice e non configurabili a caldo)
1. **Nozionale massimo per ordine** e **per simbolo**; **leva massima** e **margine massimo per trade**; numero massimo di posizioni.
2. **Fascia di prezzo**: rifiuta ordini con prezzo oltre ±X% dal mark/mid; rifiuta se il dato è più vecchio di N secondi.
3. **Limiti di frequenza**: max ordini/minuto, max rifiuti consecutivi → stop.
4. **Perdita massima giornaliera/settimanale** → modalità solo riduzione.
5. **Idempotenza**: client order id deterministico (Hyperliquid `cloid`), nessun reinvio cieco dopo timeout: prima interrogare lo stato.
6. **Kill switch**: file/flag locale + comando Telegram autenticato + procedura manuale dal telefono (revoca agent / disattiva chiave API dal sito della sede). Deve funzionare anche con il VPS irraggiungibile: per questo la revoca della chiave è il vero interruttore.
7. **Parità paper/live**: stesso codice, stesso percorso ordini, adattatore di sede scambiabile; ogni modifica passa prima N giorni in paper/testnet; confronto sistematico fill attesi vs reali.
8. Test su: arrotondamenti di tick/lot, ordini parziali, riconnessione WebSocket, orologio sfasato, sede in manutenzione, funding anomalo.

### E.5 Hardening del VPS
- SSH solo con chiavi (ed25519), `PasswordAuthentication no`, `PermitRootLogin no`, utente non privilegiato; accesso SSH **solo via Tailscale/WireGuard**, porta 22 chiusa verso Internet.
- Firewall (ufw/nftables + firewall del fornitore): ingresso negato per default; uscita consentita verso le sedi.
- **Nessuna dashboard pubblica.** Grafana/pannelli solo sulla rete privata.
- Aggiornamenti di sicurezza automatici (unattended-upgrades), riavvii pianificati a mercato tranquillo.
- Servizio con utente dedicato e sandbox systemd (`NoNewPrivileges`, `ProtectHome`, `PrivateTmp`).
- 2FA sull'account del fornitore cloud (chi controlla la console controlla il disco).
- Disco/backup cifrati; niente segreti negli snapshot condivisi.

### E.6 Checklist incidente
1. **Fermare**: kill switch; se dubbio di compromissione, **revocare subito** chiavi API/agent dal sito della sede con un dispositivo pulito.
2. **Mettere in sicurezza**: chiudere o ridurre le posizioni a mano; verificare che gli stop sulla sede esistano.
3. **Spostare**: se la compromissione può riguardare l'account, prelevare verso gli indirizzi in allow-list; se riguarda la sede, eseguire §B.6.
4. **Isolare**: spegnere il VPS (snapshot prima, per l'analisi), non riusarlo.
5. **Ruotare tutto**: chiavi API, agent, chiave age, password, token Telegram, chiavi SSH.
6. **Ricostruire** da immagine pulita e lockfile; ripartire in paper.
7. **Documentare**: cronologia, estratti, hash di transazione (servono anche per fisco e, in caso di furto, per la denuncia — la circolare 30/E richiede la denuncia per escludere dal RW le cripto sottratte [17]).
8. **Post-mortem scritto** e nuova regola/controllo prima del ritorno al live.

---

## F. Costi mensili e ordine di attivazione

### F.1 Tabella costi (STIMA, €/mese)
| Voce | Minimo | Raccomandato | Note |
|---|---|---|---|
| VPS primario | 6–7 | 6–7 | Hetzner CX23 ≈ 5,99 € + IVA [48] |
| VPS secondario / dead-man | 0 | 5–30 | altro fornitore; Tokyo costa di più |
| Backup storage | 1 | 3–5 | B2 / Storage Box |
| Monitoraggio/alert | 0 | 0–10 | healthchecks.io free, Telegram/ntfy gratis; Grafana Cloud free |
| Dati di mercato | 0 | 0–15 | API pubbliche cripto gratuite; IBKR: pacchetti dati opzionali |
| Budget API LLM (segnaposto) | 20 | 50–100 | da fissare con tetto di spesa lato fornitore |
| Commercialista | 25–40 | 50–70 | 300–800 €/anno ripartiti |
| Software fiscale cripto | 4–8 | 8–17 | 50–200 €/anno |
| Hardware wallet (una tantum 80–150 €) | 3 | 3 | ammortizzato su 3 anni |
| **Totale persona fisica** | **≈ 60–80** | **≈ 125–260** | |
| *Se SRL (in aggiunta)* | *+210* | *+375* | 2.500–4.500 €/anno |

Rapportato a 10–12 k€: il minimo vale **~7–9% annuo del capitale**, il raccomandato **~15–30%**. È il vero ostacolo economico del progetto a questo stadio: tenere i costi al minimo finché il capitale non cresce.

### F.2 Passi in ordine
1. **Subito (gratis)**: completare paper/testnet con il percorso ordini definitivo; implementare controlli §E.4, riconciliazione, audit log.
2. **Commercialista** (prima del primo euro live): domande §C.8; impostare registro movimenti e software fiscale.
3. **Denaro dei familiari**: formalizzare donazione/prestito infruttifero; bonifici tracciati sul conto del titolare.
4. **IBKR**: conto personale, permessi future/opzioni, utente API, paper → live a size minima.
5. **Sede MiFID per perps**: aprire Kraken Pro *e/o* OKX EU; verificare a schermo disponibilità per l'Italia, leva effettiva per contratto, fee; chiave API trade-only + IP allow-list; demo → live minimo.
6. **VPS + hardening + sops/age + systemd + healthchecks + Telegram**; prova di ripristino backup; prova del kill switch.
7. **Test delle protezioni lato sede** (§D.6): stop reduce-only, comportamento del dead-man sugli stop.
8. **(Opzionale, dopo parere legale e solo con quota a perdere)** Hyperliquid: hardware wallet, lettura dei ToS ufficiali, testnet (incluso test "l'agent non può prelevare"), deposito di prova, agent con scadenza.
9. **30 giorni live a size minima** con confronto paper/live; poi aumento graduale.
10. **Dicembre 2026**: ricontrollare legge di bilancio 2027; **primavera 2027**: prima dichiarazione con RT/RW/IVCA; rivalutare leva UE (ESMA) e veicolo.

---

## G. Fonti (tutte consultate il 2026-11-11)

Nota di metodo: molte fonti sono state lette tramite un riassuntore automatico della pagina; dove indicato "risultato di ricerca" ho visto solo estratto/titolo. Le fonti secondarie su leva, disponibilità per paese e fee vanno riverificate a schermo al momento dell'apertura del conto.

1. ESMA, statement 24/02/2026 sui perpetual futures e le misure CFD (primaria) — https://www.esma.europa.eu/node/228326
2. Finance Magnates, "10x Down to 2x…", 27/02/2026 — https://www.financemagnates.com/forex/10x-down-to-2x-has-europe-killed-crypto-perps-even-before-it-started/ · Finance Magnates, ESMA tells firms… — https://www.financemagnates.com/forex/regulation/esma-tells-firms-perpetual-futures-fall-under-eu-cfd-rules/
2bis. FinTelegram, "ESMA Draws The Line: Why Hyperliquid's Crypto Perpetuals Look Increasingly Like CFDs…" (solo titolo, risultato di ricerca) — https://fintelegram.com/?p=80678
3. The Block, Coinbase futures in 26 paesi europei, 09/03/2026 — https://www.theblock.co/post/392797/coinbase-opens-crypto-futures-trading-europe · Cointelegraph — https://cointelegraph.com/news/coinbase-perpetual-futures-contracts-europe-esma · Decrypt — https://decrypt.co/360420/coinbase-debuts-crypto-futures-european-traders-bitcoin-ethereum
4. Cointelegraph, Kraken lancia derivati regolamentati in Europa — https://cointelegraph.com/news/kraken-launches-regulated-crypto-derivatives-europe · BusinessWire 20/05/2025 — https://www.businesswire.com/news/home/20250520169459/en/Kraken-Launches-Europes-Largest-Regulated-Futures-Offering-Strengthening-Market-Leading-Position-in-the-Region · Blog Kraken — https://blog.kraken.com/product/kraken-derivatives/eea-futures-30-days-no-trading-fees · pagina Kraken Pro perps — https://www.kraken.com/be/pro/perps/crypto-perpetuals
5. Kraken Support, "Derivatives margin schedule & maximum leverage for EEA clients" (primaria) — https://support.kraken.com/articles/derivatives-margin-schedule-and-maximum-leverage-eea
6. Fintech Futures, OKX X-Perps — https://www.fintechfutures.com/press-releases/okx-launches-x-perps-in-europe-mifid-regulated-crypto-derivatives-with-up-to-10x-leverage · Cointelegraph — https://cointelegraph.com/news/okx-europex-perps-regulated-crypto-derivatives · https://cointelegraph.com/news/okx-targets-eu-retail-mica-mag-7-stock-perps · The Fintech Times — https://thefintechtimes.com/okx-europe-launches-simplified-leveraged-trading-under-mica-and-mifid-ii/ · Ledger Insights — https://www.ledgerinsights.com/okx-launches-x-perps-on-us-stocks-in-eu-despite-esma-pushback-on-perpetuals/
7. PR Newswire, Bybit EU domanda MiFID II (09/2025) — https://www.prnewswire.com/in/news-releases/bybit-eu-group-sets-sights-on-mifid-ii-license-to-unlock-derivatives-market-across-europe-302547707.html · Finance Magnates — https://www.financemagnates.com/cryptocurrency/bybit-pursues-mifid-license-for-eu-derivatives-phases-out-mt5-for-in-house-trafi/
8. CoinPerps, "Best Crypto Perpetual Futures Exchanges in Europe (2026)", agg. 09/11/2026 (secondaria, sito comparatore) — https://www.coinperps.com/learn/best-crypto-futures-platforms-in-europe
9. Consob, delibera n. 20976 del 20/06/2019 — https://www.consob.it/web/area-pubblica/bollettino/documenti/bollettino2019/d20976.htm · comunicato 21/06/2019 — https://www.consob.it/web/consob-and-its-activities/news-in-detail/-/asset_publisher/kcxlUuOyjO9x/content/press-release-21-june-2019/718268 · InvestireOggi — https://www.investireoggi.it/cfd-investitori-retail-limiti-consob-rischi-reali-possibilita-risarcimento/
10. Teleborsa, Binance stop UE dal 1° luglio, 25/06/2026 — https://www.teleborsa.it/AMP/News/2026/06/25/binance-stop-operativita-in-ue-dal-1-luglio-cosa-devono-fare-i-clienti-125.html
11. AziendaBanca — https://www.aziendabanca.it/notizie/fintech-insurtech/binance-licenza-micar · CASP Tracker Binance — https://casptracker.eu/it/exchange/binance/ · QuiFinanza — https://quifinanza.it/economia/finanza/binance-stop-operativita/1005361/
12. CASP Tracker Bitget (verifica 14/10/2026) — https://casptracker.eu/it/exchange/bitget/
13. Datawallet, Hyperliquid restricted countries — https://www.datawallet.com/crypto/hyperliquid-supported-and-restricted-countries · CoinPerps — https://www.coinperps.com/learn/hyperliquid-restricted-countries
14. Rankia — https://rankia.it/tassazione-bitcoin-tasse-su-criptovalute · Waltio — https://www.waltio.com/it/tassazione-criptovalute-2026-guida/ · Centro Fiscale DAC8 — https://centrofiscale.com/dac8-criptovalute-2026-scambio-dati-controlli-3/ · Agenda Digitale — https://www.agendadigitale.eu/mercati-digitali/tassazione-criptovalute-cosa-cambia-con-la-legge-di-bilancio-2026/
15. Milano Finanza, guida tasse cripto 2026 (contenuto sponsorizzato) — https://www.milanofinanza.it/news/tasse-criptovalute-2026-la-guida-completa-con-aliquote-scadenze-e-adempimenti-202605131159008630
16. Fiscal Focus — https://www.fiscal-focus.it/quotidiano/il-quotidiano/articoli-fisco/cripto-attivita-2026-aliquota-al-33-ma-scatta-una-deroga-per-i-token-di-moneta-elettronica-in-euro,3,180507 · ItaliaOggi (emendamento Milleproroghe) — https://www.italiaoggi.it/diritto-e-fisco/fisco/fisco-nel-milleproroghe-prove-di-aliquota-al-26-per-le-plusvalenze-da-cripto-oykrkfzv · InvestireOggi (Milleproroghe definitivo) — https://www.investireoggi.it/decreto-milleproroghe-2026-definitivo-cosa-slitta-tra-iva-cantieri-tari-e-lavoro/ · MoneyViz — https://blog.moneyviz.it/tasse-crypto-2026-33-legge-bilancio/
17. Agenzia delle Entrate, **Circolare n. 30/E del 27/10/2023** (testo integrale letto: §§ 2.3.2, 2.3.5, 3) — https://www.dirittobancario.it/wp-content/uploads/2023/10/Circolare-Agenzia-delle-Entrate-27-ottobre-2023-n.-30-E.pdf
18. Art. 166 TUF — https://brocardi.it/testo-unico-intermediazione-finanziaria/parte-v/titolo-i/capo-i/art166.html · https://miolegale.it/testi-unici/finanza/art-166/ · Fiscomania — https://fiscomania.com/abusivismo-finanziario-trading-online/
19. Finance Magnates, Europe's crypto market after July 1 — https://www.financemagnates.com/cryptocurrency/regulation/europes-crypto-market-after-july-1-who-stays-who-leaves-and-what-changes-under-mica/ · PwC Legal — https://legal.pwc.de/content/services/regcore-client-alert/pwc-legal-client-alert-after-the-micar-cliff-edge-june-2026.pdf
20. Borsa Italiana/Teleborsa, Consob oscura 10 siti, totale 1.848 (15/10/2026) — https://www.borsaitaliana.it/borsa/notizie/teleborsa/finanza/abusivismo-finanziario-consob-oscura-10-siti-totale-sale-a-1848-89_2026-10-15_TLB.html?lang=it · Consob 26/06/2026 — https://www.consob.it/web/consob/w/occhio-alle-truffe-abusivismo-finanziario-consob-oscura-21-siti-internet
21. Allegato 3 Regolamento Intermediari Consob (copia; risultato di ricerca) — https://www.fiscoetasse.com/files/14558/allegato-3-regolamento-consob-clienti-professionali.pdf
22. Hyperliquid Docs, Exchange endpoint (primaria) — https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint · Chainstack (nota su scheduleCancel) — https://docs.chainstack.com/reference/hyperliquid-exchange-schedule-cancel
23. Hyperliquid Docs, Fees (primaria) — https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees
24. OneKey, Hyperliquid Validator Risk 2026 — https://onekey.so/blog/ecosystem/hyperliquid-validator-risk/ · Komainu (27/05/2026) — https://komainu.com/insights/komainu-insights-hyperliquid-staking/ · Blofin — https://blofin.com/academy/education/hyperliquid/how-decentralized-is-hyperliquid · Blockworks — https://blockworks.co/news/hyperliquid-decentralization-validator-put · crypto.news — https://crypto.news/who-actually-runs-hyperliquid-the-governance-audit/
25. The Block, JELLY — https://www.theblock.co/post/348314/hyperliquid-delists-jellyjelly-memecoin-amid-whale-manipulation-fiasco · Decrypt — https://decrypt.co/311713/hyperliquid-delists-solana-meme-coin-liquidation-crisis · Cointelegraph — https://cointelegraph.com/news/bitget-ceo-slams-hyperliquid-jelly-perps-delisting
26. Cointelegraph, POPCAT — https://cointelegraph.com/news/hyperliquid-hlp-popcat-attack-3m-wipeout · Wu Blockchain, ADL — https://wublock.substack.com/p/hyperliquid-activates-cross-margin · ZeroHedge — https://www.zerohedge.com/crypto/after-octobers-liquidation-day-collapse-adl-are-3-most-important-letters-crypto · Halborn — https://www.halborn.com/blog/post/explained-the-hyperliquid-hack-november-2025
27. CryptoSlate, Kraken unified wallet — https://cryptoslate.com/krakens-opt-in-european-wallet-can-expose-spot-holdings-to-futures-losses/
28. Kraken Docs, Dead Man's Switch — https://docs.kraken.com/api-reference/order-management/dead-mans-switch · https://docs.kraken.com/api/docs/websocket-v2/cancel_after · Deribit Docs — https://docs.deribit.com/api-reference/session-management/private-enable_cancel_on_disconnect.md
29. OKX EU, X-Perps — https://www.okx.com/en-eu/x-perps (risultato di ricerca)
30. Binance Developers, Auto-Cancel All Open Orders — https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Auto-Cancel-All-Open-Orders
31. Bybit API v5, Set Disconnect Cancel All — https://bybit-exchange.github.io/docs/v5/order/dcp
32. The Block, Bybit/Lazarus — https://www.theblock.co/post/342769/north-koreas-lazarus-group-responsible-for-bybit-hack-resulting-in-losses-of-over-1-5-billion-arkham · NBC — https://www.nbcnews.com/tech/crypto/hackers-steal-15-billion-exchange-bybit-biggest-ever-crypto-heist-rcna193273 · TechTarget (FBI) — https://www.techtarget.com/cybersecurity/news/366619872/FBI-Lazarus-Group-behind-15-billion-Bybit-heist
33. Datawallet, Deribit restricted countries — https://datawallet.com/crypto/deribit-restricted-countries · https://wherelegalcrypto.pages.dev/exchanges/deribit/
34. dYdX Docs, integration compliance — https://docs.dydx.xyz/interaction/integration/integration-compliance · Help, geo-restrictions — https://help.dydx.trade/en/articles/166970-geo-restrictions-site-access · Fees — https://docs.dydx.xyz/concepts/trading/rewards · Validators — https://dydx.foundation/validators/introduction
35. BusinessWire, IBKR crypto EEA, 31/03/2026 — https://www.businesswire.com/news/home/20260331327850/en/interactive-brokers-launches-crypto-asset-trading-for-individual-investors-in-the-european-economic-area/ · 01net — https://www.01net.it/interactive-brokers-lancia-il-trading-di-criptoattivita-per-i-singoli-investitori-nello-spazio-economico-europeo-see/ · fee (secondaria) — https://investingintheweb.com/brokers/interactive-brokers-crypto/
36. IBKR Knowledge Base, Italian regulations on capital gain taxes — https://ibkb.interactivebrokers.com/nl/node/2091 · MoneyViz — https://blog.moneyviz.it/come-pagare-le-tasse-su-interactive-brokers-guida-completa/
37. Hyperliquid Docs, Nonces and API wallets (primaria) — https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/nonces-and-api-wallets
38. Invezz, Hyperliquid Tokyo 200 ms — https://invezz.com/en-ae/news/2026/03/30/hyperliquid-traders-in-tokyo-gain-200ms-edge-over-global-rivals/ · Glassnode latency monitor — https://latency.glassnode.com/hyperliquid/fill-latency
39. Kraken fee schedule — https://www.kraken.com/features/fee-schedule
40. Centro Fiscale, IVCA 2‰ — https://centrofiscale.com/imposta-valore-cripto-attivita-2026-2-per-mille/ · FiscoInvestimenti, RW 2026 — https://fiscoinvestimenti.it/crypto-dichiarazione-redditi-quadro-rw-2026/ · Fiscomania — https://fiscomania.com/imposta-cripto-attivita/
41. Fiscomania, cripto-attività nelle imprese — https://fiscomania.com/cripto-attivita-imprese-fiscalita-bilancio/ · AdE, risposta n. 78/2025 — https://dirittobancario.it/wp-content/uploads/2025/04/Agenzia-delle-Entrate-Risposta-a-interpello-22-marzo-2025-n.-78.pdf
42. Diritto Bancario, proposte correttivo MiFID II (estratto sull'esenzione per il conto proprio; risultato di ricerca) — https://www.dirittobancario.it/wp-content/uploads/sites/default/files/allegati/proposte_correttivo_mifid_ii.pdf
43. EC News, tassazione delle società semplici — https://www.ecnews.it/fiscale/fisco-e-patrimonio/imposte-sul-reddito/la-tassazione-delle-societa-semplici/
44. Studio Cataldi — https://www.studiocataldi.it/articoli/20696-se-il-capitale-dei-clienti-viene-gestito-dall-analista-finanziario-c-e-intermediazione-finanziaria-abusiva.asp · Fiscal Focus — https://www.fiscal-focus.it/quotidiano/il-quotidiano/articoli-legali/abusivismo-finanziario-e-truffa-consumazione-in-italia-anche-con-investimenti-esteri,3,181957
45. IBKR, Non-Professional Advisors / Family Advisor — https://www.interactivebrokers.com/en/accounts/friends-family.php · https://www.interactivebrokers.com.hk/en/accounts/friends-family.php · forum — https://www.elitetrader.com/et/threads/advisor-account.363574 (pagina IBKR Ireland non raggiungibile: HTTP 403)
46. ESMA, Supervisory Briefing on Copy Trading, 30/03/2023 — https://www.esma.europa.eu/sites/default/files/2023-03/ESMA35-42-1428_Supervisory_Briefing_on_Copy_Trading.pdf
47. Banca d'Italia, FAQ operatori del risparmio gestito — https://www.bancaditalia.it/compiti/vigilanza/accesso-mercato/operatori-risparmio-gestito/faq-operatori-risparmio-gestito/index.html · Legance, D.Lgs. 27/03/2026 n. 47 — https://www.legance.it/wp-content/uploads/2026/04/Newsletter-Decreto-Legislativo-27-marzo-2026-n.-47.pdf · LCA, Riforma TUF gestori sotto soglia (11/12/2025, testo letto) — https://www.lcalex.it/wp-content/uploads/2025/12/Riforma-TUF.-Gestori-sotto-soglia-e-societa-di-partenariato.pdf · Diritto Bancario (G.U.) — https://www.dirittobancario.it/art/riforma-tuf-il-testo-del-decreto-in-gazzetta-ufficiale/ · Fisco e Tasse — https://www.fiscoetasse.com/normativa-prassi/13566-riforma-mercato-capitali-2026-cosa-cambia-per-mercati-gestori-e-investitori.html
48. Hetzner, price adjustment — https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/ · Bitdoze — https://www.bitdoze.com/hetzner-cloud-cost-optimized-plans/ · VPSBenchmarks CX23 — https://www.vpsbenchmarks.com/hosters/hetzner/plans/cx23 · Tom's Hardware — https://www.tomshardware.com/tech-industry/hetzner-to-raise-prices-by-up-to-37-percent-from-april-1
49. Valebyte, VPS Japan (Vultr Tokyo) — https://valebyte.com/en/vps/japan/?city=Tokyo&page=2
50. AWS, Lightsail bundles — https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.md

### Punti non verificati (riepilogo)
- Testo ufficiale dei Termini d'uso Hyperliquid; elenco integrale dei provvedimenti Consob; disponibilità *Italia* per Kraken derivati, Coinbase futures, cripto IBKR; stato di Deribit per retail UE.
- Fee futures correnti di Kraken, Coinbase UE; intervalli di funding per sede; spread e volumi (nessun dato misurato oggi).
- Percorso esatto dell'endpoint Binance `countdownCancelAll` e OKX `cancel-all-after`; accesso retail al DCP Bybit; se i "cancel all" rimuovono gli stop.
- Permessi degli agent Hyperliquid (assenza di prelievo): documentato altrove, non nella pagina letta oggi → test su testnet.
- Testo vigente dell'Allegato 3 Consob (cliente professionale), art. 4-terdecies TUF, artt. 73 e 167 TUIR, società di comodo, IVAFE: citati da conoscenza pregressa.
- Legge di bilancio 2027: nessuna informazione trovata.
- Prezzi Vultr/Lightsail (tagli maggiori)/OVH; disponibilità dei piani Hetzner.

### Dove le fonti divergono
- Leva retail UE sui perps: 10x (sedi) contro 2x (lettura ESMA dei perps come CFD).
- Coinbase UE: retail vs solo utenti "Advanced" idonei; Italia inclusa o no; 5x vs 10x sugli indici.
- Aliquota/franchigia cripto: guide datate riportano ancora 26% o la soglia di 2.000 €; un titolo indica "33% dal 2027".
- Hyperliquid: 24 vs 27 validatori; cifre del caso JELLY.
- Pena dell'art. 166 TUF: 1–8 anni (vigente) vs 6 mesi–4 anni (testi non aggiornati).
- Deribit: perimetro UE e proprietà riportati in modo incoerente da fonti secondarie.
