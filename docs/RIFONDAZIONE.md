# GERVA Capital: documento di rifondazione

Versione 5.0, 11 novembre 2026. Autore: sessione di lavoro con Claude, su incarico di Andrea Gervasoni.

**Come leggere questo documento.** Ogni affermazione porta una di quattro etichette, perché confonderle è il modo più rapido di perdere denaro:

| Etichetta | Che cosa vuol dire |
|---|---|
| **FATTO** | Verificato in questa sessione su una fonte aperta e letta, oppure su codice eseguito. Le fonti sono in fondo, con `[V]` se la pagina è stata aperta, `[S]` se ne ho visto solo un estratto, `[R]` se è un ricordo non verificato. |
| **SIMULATO** | Risultato di un backtest su dati storici reali, al netto dei costi dichiarati. Non è mai un rendimento ottenuto. Tutti i numeri simulati escono da `python -m gerva research` e stanno in [`research/v5/RESULTS.md`](../research/v5/RESULTS.md). |
| **STIMA** | Un numero mio, ragionato ma non misurato (per esempio un costo annuo). |
| **IPOTESI** | Qualcosa che va ancora verificato, da te o da un professionista. |

**I dati di partenza che mi hai dato:** capitale reale 10–12 mila euro; residenza fiscale in Italia, maggiorenne; denaro soltanto tuo e della famiglia per i primi 12–24 mesi; sedi disponibili Interactive Brokers, un exchange crypto autorizzato nell'UE, Alpaca (solo paper).

**Glossario minimo.** *Sharpe*: rendimento in eccesso del tasso a breve diviso per la volatilità, annualizzato; misura quanto rendimento si ottiene per unità di rischio. *CAGR*: rendimento annuo composto. *Caduta massima* (drawdown): la perdita dal massimo precedente. *pb*: punto base, 0,01%. *Periodo di scelta*: fino al 31/12/2022, usato per decidere. *Periodo di verifica*: dal 1/1/2023, mai usato per decidere. *Leva 2x*: esposizione pari a due volte il patrimonio.

---

## Il verdetto in dodici righe

1. **L'obiettivo del 20–30% al mese non è sostenuto da alcun dato**, né della letteratura né dei nostri test. Composto, vale tra il 792% e il 2.230% l'anno; il miglior fondo della storia documentata (Medallion) ha reso il 66% lordo l'anno. Lo dimostro con i numeri nella sezione 2.1 e misuro nella sezione 4.6 quanto ci si può avvicinare.
2. **GEX e VWAP non sono segnali di direzione.** Sui dati 2011–2026 il GEX prevede bene la *volatilità* del giorno dopo (27,6% annuo nel quintile basso contro 9,9% nell'alto) ma nessuna regola GEX batte il semplice comprare e tenere. La regola "long sopra il VWAP, short sotto" perde già *prima* dei costi su 24 azioni e su Bitcoin (sezione 3).
3. **L'unico effetto GEX che funzionava è scomparso.** Il momentum dell'ultima mezz'ora nei giorni di gamma basso aveva Sharpe 1,38 nel 2011–2018; nel 2023–2026 ha cambiato segno su S&P 500, Nasdaq e Russell (sezione 3.3).
4. **Su 110 configurazioni provate, quattro strategie reggono** ai costi veri di un conto piccolo: due sulle crypto (trend e momentum), una sulle azioni (ritorno alla media), una multi-asset (trend lento).
5. **Il portafoglio delle quattro, SIMULATO, senza leva:** 13,8% l'anno con volatilità 9,0%, Sharpe 1,18, caduta massima −9,4%. Nel periodo di verifica lo Sharpe scende a 0,86.
6. **Non è una prova.** Il Deflated Sharpe, che tiene conto delle 110 prove, è 0,51 contro una soglia di 0,95. Evidenza promettente, non conclusiva: decide il paper trading.
7. **La leva scelta è 2x al massimo**, con volatilità obiettivo 15%. Nel caso realistico (metà del rendimento del backtest) a 2x il CAGR mediano è il 10% e la probabilità di dimezzare il capitale in tre anni è sotto lo 0,1%; a 6x è il 31%; a 12x il 76% (sezione 4.3).
8. **Per avere in media il 20% al mese servirebbe una leva vicina a 30x.** Già a 15x, dove il mese medio simulato è il 10%, la probabilità di dimezzare il capitale in tre anni è tra il 62% e l'87% secondo lo scenario. Non è un percorso: è una roulette con le commissioni.
9. **Il codice esistente proteggeva la strada sbagliata.** I controlli migliori erano sui pod, che sono spenti; i percorsi che scambiavano davvero avevano i controlli più deboli, e un voto di tre agenti poteva portare la leva a 3x (sezione 1).
10. **Ho riscritto il nucleo** in un pacchetto nuovo, `gerva/`: stesse funzioni per backtest e live, rischio in tempo reale con KILL a ritenuta, ordini che non si possono duplicare, supervisore, con 50 test nuovi sul motore e 20 di regressione sul codice esistente.
11. **La forma giusta oggi è la persona fisica**, con conto proprio; nessuna società sotto i 300–500 mila euro. Gestire denaro di amici con un compenso è attività riservata: reclusione da uno a otto anni (sezione 7).
12. **Il traguardo onesto:** 10–20% l'anno con cadute entro il 20%, dimostrato prima in paper per 90 giorni e poi con un quarto del capitale. È ciò che rende un fondo credibile; il capitale di terzi, più avanti, si ottiene con un registro verificabile, non con una promessa.

---

## 1. Audit del repository

### 1.1 Che cosa c'era

Un progetto serio e insolito: una "società" di 28 agenti (11 LLM) che leggono, propongono e giudicano, attorno a un motore esterno (GERVA-Q, non presente in questo repository) che invia gli ordini; un laboratorio statistico (`quantlab/`) con PSR, Deflated Sharpe, PBO, parità di rischio; un portale; 290 test. Le scelte di fondo erano giuste e restano: gli LLM non generano segnali, un solo registro delle prove, un gateway deterministico, un registro di audit con catena di hash. Il lavoro precedente aveva già trovato e dichiarato molti dei propri limiti.

I due audit indipendenti che ho commissionato (uno su esecuzione e rischio, uno sulla correttezza quantitativa) hanno però trovato un problema di architettura riassumibile in una frase del primo revisore: *i controlli più forti proteggevano una strada spenta (i pod), mentre le strade che scambiavano davvero avevano i controlli più deboli.*

### 1.2 I difetti, e che cosa ne è stato

| # | Gravità | Difetto | Dimostrazione | Stato |
|---:|---|---|---|---|
| 1 | Critica | Il KILL non chiudeva nulla e non fermava le strade che muovevano denaro: sede crypto, banco libero, strategie, segnali non lo controllavano; GERVA-Q leggeva un altro file | Letto nel codice | **Corretto**: un solo stato rispettato ovunque; il conto Alpaca viene svuotato; il file viene scritto anche per GERVA-Q |
| 2 | Critica | Un voto di tre agenti poteva portare la leva del motore a 3x e i tetti di esposizione al 100%, lo stesso giorno, senza alcuna approvazione | Letto nel codice | **Corretto**: ciò che alza il rischio attende la tua approvazione ed è comunque limitato dai tetti di `risk_limits.yaml` |
| 3 | Critica | Il banco libero dava agli LLM accesso diretto al broker con regole aggirabili | Riprodotto: 20 ordini da 9.000 $ accettati su un conto da 100.000 con leva massima 1 | **Corretto**: limiti sull'esposizione cumulata nel giro; lati ignoti rifiutati |
| 4 | Alta | Un'eccezione fermava l'intero battito; con i pod attivi e capitale iniziale zero, una divisione per zero bloccava ogni giro | Riprodotto | **Corretto**: passi isolati, rischio e stop per primi |
| 5 | Alta | Ordini verso Alpaca senza identificativo: un errore di rete dopo l'accettazione produceva un duplicato | Letto nel codice | **Riscritto** nel nuovo motore (intenzione più identificativo); nel vecchio percorso resta |
| 6 | Alta | Il gateway controllava concentrazione e leva solo sugli acquisti; in caduta bloccava anche le chiusure | Riprodotto: short pari al 190% del capitale di un pod accettato; la ricopertura rifiutata | **Corretto**, con test sui limiti di produzione |
| 7 | Alta | Misure ottimistiche: obiettivo contato anche se il prezzo di ingresso non era mai stato toccato; eventi del fine settimana scartati | Riprodotto: −7,9% di perdite di sabato e domenica mostrato come +0,1% | **Corretto** per segnali osservati e banco simulato; i segnali eseguiti si misurano ancora sul prezzo dichiarato |
| 8 | Alta | Stop sui segnali reali controllati a intervalli, con la vendita un battito dopo | Letto nel codice | **Aperto** nel vecchio codice; il nuovo motore non usa segnali esterni |
| 9 | Critica (ricerca) | Lo Sharpe era calcolato sui rendimenti grezzi: il banco v4 premiava la cassa che rende il tasso a breve come se fosse alpha | Riprodotto: su mercati di puro rumore il banco promuoveva la variante "con cassa" 9–12 volte su 12. In eccesso del tasso la v4 non supera il proprio cancello (P = 0,66 contro 0,90 richiesto) | **Superato**: il nuovo motore usa solo rendimenti in eccesso. **La decisione "v4 approvata" va considerata sospesa** |
| 10 | Alta (ricerca) | La regola del portafoglio ombra a 40 giorni approvava un terzo delle volte anche senza alcun vantaggio | Riprodotto su 136 finestre storiche: 35% | **Aperto**: la regola va riscritta (sezione 5.2 dà il modello) |
| 11 | Alta (ricerca) | Il backtester eseguiva sulla stessa chiusura che generava il segnale, mentre la documentazione diceva "il giorno dopo" | Riprodotto | **Superato**: `lag` esplicito nel nuovo motore, ed entrambi i casi riportati |
| 12 | Alta (ricerca) | Il test anti look-ahead si poteva aggirare; un cancello aveva l'esito "superato" scritto a mano | Riprodotto: un segnale che usa la chiusura di domani a fine mese passava e dava Sharpe 9,1 sul rumore | **Superato** nel nuovo motore (40 punti di taglio casuali); aperto in `quantlab` |
| 13 | Alta (ricerca) | Valute non modellate; tasso americano accreditato a un conto in euro | Riprodotto: lo Sharpe della v4 scende da 0,91 a 0,75 in euro | **Aperto** anche nel nuovo motore (dichiarato in 6.7) |
| 14 | Media | Crypto annualizzate a 252 giorni; caso "realistico" migliore del modello con storia negativa | Riprodotto | **Corretto** |
| 15 | Media | Aggiornamento automatico dal repository senza verifica della firma; token del proprietario dentro la pagina del portale | Letto nel codice | **Aperto**: vedi 1.4 |
| 16 | Impostazioni | KILL automatico al −35%, appena oltre la caduta massima del backtest (non scattava mai); leva fino a 25x nel banco simulato scelta dagli agenti; segnali Telegram eseguibili | `config/` | Il nuovo motore ha i propri limiti (KILL al −20%, leva 2x). Le tue scelte nel vecchio `config/` non le ho toccate |

Riepilogo: dei 16 punti, 8 corretti nel codice esistente con 20 test di regressione (`tests/test_audit_v5.py`), 4 superati dal nuovo motore, 4 ancora aperti e dichiarati. Che cosa andava già bene, e resta: il gateway con le intenzioni scritte prima dell'invio, l'esecutore IBKR, il blocco "solo paper", l'audit a catena di hash, l'isolamento dei contenitori, le formule statistiche di `quantlab` (verificate contro gli esempi pubblicati).

### 1.3 La decisione

- **Scelta:** riscrivere il nucleo di trading in un pacchetto nuovo (`gerva/`) e tenere la società di agenti (`firm/`) come laboratorio in paper, con i difetti critici corretti.
- **Motivazione:** nel vecchio codice le strade verso un broker erano quattro (gateway dei pod, sede crypto, banco libero, strategie in codice), ciascuna con le proprie regole. Un sistema per denaro reale deve avere **un solo punto** da cui passa ogni ordine e **una sola definizione** di ogni strategia, uguale in backtest e dal vivo. Aggiungerli sopra l'esistente avrebbe lasciato in piedi le altre tre strade.
- **Alternative scartate:** *buttare tutto* (la società di agenti ha valore come laboratorio di ricerca, e l'audit ha confermato che molte sue parti sono solide); *correggere soltanto* (non avrebbe dato né la parità backtest/live né il punto unico di controllo).

### 1.4 Che cosa resta aperto

1. `quantlab/`: Sharpe in eccesso nei banchi v4 e crypto, ritardo di esecuzione, test anti look-ahead più fitto. Sono superati dal nuovo motore; se continui a usare i vecchi banchi vanno corretti.
2. La regola di adozione del portafoglio ombra (40 giorni): da sospendere.
3. Sicurezza del vecchio portale e dell'aggiornamento automatico.
4. Valute e rischio di cambio, in entrambi i motori.
5. Adattatore IBKR per il nuovo motore; verifica dal vivo dell'adattatore Alpaca.
6. Gli stop dei segnali Telegram nel vecchio codice: finché restano controllati a intervalli, quei segnali non vanno eseguiti su un conto reale.

---

## 2. Ricerca di mercato

### 2.1 La matematica dell'obiettivo

Prima di cercare la strategia, conviene chiedere alla matematica che cosa dovrebbe essere vero perché l'obiettivo sia raggiungibile.

**Capitalizzazione.** Un rendimento mensile *m* dà in un anno (1 + m)¹² − 1:

| Al mese | In un anno | In cinque anni, 12.000 € diventano |
|---:|---:|---:|
| 1% | 12,7% | 21.800 € |
| 2% | 26,8% | 39.400 € |
| 5% | 79,6% | 224.000 € |
| 20% | 791,6% | 676 milioni |
| 25% | 1.355% | 7,8 miliardi |
| 30% | 2.230% | 82 miliardi |

L'ultima colonna è il controllo di realtà più semplice: se una regola pubblica rendesse il 25% al mese, in cinque anni chi la usa possiederebbe una quota visibile del PIL mondiale.

**Il vincolo di Kelly.** Nel 1956 John Kelly, ai Bell Labs, dimostrò che esiste una dimensione della scommessa che massimizza il tasso di crescita del capitale, e che superarla fa crescere *meno* [K1]. Edward Thorp lo portò dai tavoli di blackjack ai mercati [K2]. In tempo continuo, per un portafoglio con rendimento in eccesso μ e volatilità σ tenuto a leva L, il tasso di crescita logaritmica è

```
g(L) = r + L·μ − L²·σ²/2
```

Il termine L²σ²/2 è il *trascinamento da volatilità*: cresce col quadrato della leva. Il massimo è a L* = μ/σ² = Sharpe/σ, dove la crescita vale

```
g(L*) − r = Sharpe² / 2
```

Questo è il punto decisivo: **il tasso di crescita massimo raggiungibile dipende soltanto dallo Sharpe**, non da quanta leva si è disposti a usare. A 2·L* la crescita torna a zero; oltre diventa negativa [K3].

Il 25% al mese è una crescita logaritmica di 12·ln(1,25) = 2,68 l'anno. Quindi:

| Frazione di Kelly usata | Crescita relativa | Sharpe necessario per il 25% al mese | Volatilità annua del conto | Probabilità di dimezzare il capitale prima o poi |
|---|---:|---:|---:|---:|
| Kelly pieno | 100% | 2,31 | 231% | 50% |
| Mezzo Kelly | 75% | 2,67 | 134% | 12,5% |
| Un quarto di Kelly | 44% | 3,50 | 87% | 0,8% |

(Colonne 2 e 5 da MacLean, Thorp e Ziemba [K3]; la probabilità di toccare la frazione *x* del capitale giocando *c* volte Kelly è x^(2/c − 1). Colonne 3 e 4: mia aritmetica dalle formule sopra.)

Serve dunque uno **Sharpe stabile tra 2,3 e 3,5**, tenuto per anni, con una leva che porta la volatilità del conto oltre il 100% l'anno. Confronto con ciò che esiste:

| Chi | Rendimento | Al mese | Fonte |
|---|---:|---:|---|
| Medallion (Renaissance), 1988–2018 | 66,1% lordo, 39,2% netto l'anno | 4,3% / 2,8% | Cornell, via CXO [B5] `[V]` |
| Citadel Wellington, dal 1990 | circa 19% l'anno | 1,5% | Reuters [B6] `[V]` |
| D.E. Shaw Composite, dal 2001 | 12,9% l'anno netto | 1,0% | Reuters [B6] `[V]` |
| Indice SG Trend (i maggiori fondi trend), dal 2000 | 4,9–5,2% l'anno | 0,4% | Meketa, TTU [S3] `[V]` |
| Vincitore World Cup Trading Championship 2025 (futures) | +324,7% in un anno | 12,8% | classifica ufficiale [B7] `[V]` |
| Nostro portafoglio, SIMULATO, senza leva | 13,8% l'anno | 1,1% | `research/v5` |

Medallion raggiunge quei numeri con centinaia di dottori di ricerca, costi di esecuzione vicini a zero, un capitale chiuso a dieci miliardi proprio perché la strategia non regge di più, e una leva che nessun broker concede a un privato. Il vincitore di una gara annuale è il migliore di centinaia di iscritti su un conto piccolo: la distribuzione di chi perde non viene pubblicata.

**Le frequenze di base.** Chi prova a vivere di trading di breve periodo:

- Taiwan, circa 360.000 day trader l'anno, 1992–2006: meno dell'1% è profittevole in modo prevedibile [B1] `[V]`.
- Brasile, mini-futures sull'indice, 2013–2015: tra chi ha insistito per più di 300 giorni, il 97% ha perso denaro [B2] `[V]`.
- CFD in Europa: tra il 74% e l'89% dei conti al dettaglio perde (decisione ESMA 2018) [B3] `[V]`.
- Sfide delle prop firm: su 300.000 conti, il 14% supera la prova e il 7% riceve un pagamento [B4] `[V]`.

Come scrisse Feynman, «il primo principio è che non devi ingannare te stesso, e tu sei la persona più facile da ingannare». Tutto ciò che segue è costruito attorno a quel principio.

### 2.2 Le famiglie di strategie: letteratura contro i nostri test

Ho provato sui dati reali ogni famiglia accessibile a un conto come il tuo. La tabella affianca ciò che dice la letteratura a ciò che esce dal nostro motore, con i nostri costi.

| Famiglia | Fonte principale | Sharpe in letteratura | Nostro test, netto (tutto / scelta / verifica) | Con 12 mila euro | Verdetto |
|---|---|---|---|---|---|
| Trend following multi-asset | Moskowitz, Ooi, Pedersen 2012 [S1]; Hurst e altri 2017 [S2] | 1,0–1,3 lordo nei backtest; 0,77 netto su un secolo; **0,28 l'indice SG Trend reale dal 2000** [S4] `[S]` | giornaliero: −0,47; lento settimanale solo long: 0,46 / 0,59 / −0,22 | Sì, ma lento e senza leva | **Tenuto** come diversificatore (MA-TREND), peso piccolo nel rischio |
| Ritorno alla media di breve su indici (IBS) | pratica nota; nessun paper canonico | — | 0,55 su 27 anni; dal 2018: 0,73 / 0,97 / 0,33 | Sì, via CFD su indice | **Tenuto** (EQ-MR); vive solo se eseguito in chiusura |
| Leva a regime (media a 200 giorni) | Gayed e Bilello 2016 [S12] | 0,51 contro 0,30 del comprare e tenere, senza costi di cambio | 2x SPY: 0,53; 2x QQQ: 0,42 con caduta −83% | Sì | Scartato: Sharpe uguale al comprare e tenere, cadute enormi |
| Volatilità gestita | Moreira e Muir 2017 [S11] | +25% di Sharpe in campione; fuori campione peggiora 72 strategie su 103 (Cederburg e altri 2020) `[S]` | 0,51 contro 0,49 di SPY | Sì | Scartato come strategia; usato come regola di rischio |
| Vendere volatilità | Bondarenko 2016 sull'indice PUT [S6] | 0,67 lordo | SVXY con filtro: 0,54, giorno peggiore −26,5% (senza filtro −83%) | No (manca il KID) | **Scartato**: rischio di coda non controllabile |
| GEX come segnale | SqueezeMetrics [G1]; Baltussen e altri 2021 [G4] | prevede volatilità e momentum intraday, non la direzione | nessuna regola batte SPY (0,81); l'ultima mezz'ora: 1,38 → negativo | — | **Scartato** come segnale; usato per capire il regime |
| VWAP trend | Zarattini e Aziz 2023 [G8] | 2,1 dichiarato, senza slippage | −1,9 lordo su 24 azioni; rovina con 1 pb di costo | — | **Scartato** |
| Momentum intraday ("zona di rumore") | Zarattini, Aziz, Barbon 2024 [G9] | 1,33 dichiarato con leva 4x; 0,39 fuori campione [G11] `[S]` | lordo 0,50; a 0,5 pb di costo 0,10; a 1 pb negativo | Solo con MES, troppo grande | **Scartato** |
| Trend sulle crypto | Liu e Tsyvinski 2021 [S10] | forte in campione (2011–2018) | BTC+ETH: 0,99 / 1,33 / 0,54 | Sì, spot | **Tenuto** (CR-TREND) |
| Momentum trasversale crypto | Liu, Tsyvinski, Wu 2022 [S10] | circa 3% a settimana lordo in campione | con filtro e volatilità 25%: 1,04 / 1,02 / 1,08 | Sì, spot | **Tenuto** (CR-XSMOM) |
| Carry sui perpetual | BIS WP 1087 [S9] | carry medio oltre il 10% l'anno, picchi al 60% `[V]` | 6,9% l'anno; funding 2026: 2–3% | Dubbio legale (2.3) | **Sospeso**: oggi rende meno di un BOT |
| Fattori azionari, pairs trading | McLean e Pontiff 2016 [S7]; Do e Faff 2010 | −58% dopo la pubblicazione `[V]` | non provati | No (short, PRIIPs, ampiezza) | Fuori portata |
| Market making, alta frequenza | Aquilina, Budish, O'Neill 2022 [S20] | — | — | No: gare decise in 5–10 microsecondi | Fuori portata |

Tre letture della tabella:

1. **Lo scarto tra backtest e realtà è la regola.** Il trend following ha Sharpe superiore a 1 nei backtest accademici e 0,28 nell'indice dei fondi veri. Le anomalie pubblicate perdono in media il 58% del rendimento dopo la pubblicazione [S7]. Nel nostro portafoglio lo Sharpe di verifica è il 58% di quello di scelta: la stessa cifra, per coincidenza, ma lo stesso fenomeno.
2. **Il rendimento sta dove c'è rischio che gli altri non vogliono.** Le due strategie che rendono di più sono sulle crypto, cioè dove la volatilità è del 60–80% e le controparti possono fallire (Mt. Gox, FTX). Non è un pranzo gratis: è un premio.
3. **I costi decidono più dei segnali.** Lo stesso trend su 17 ETF passa da Sharpe +0,57 lordo a −0,47 netto solo perché ribilancia ogni giorno.

### 2.3 Che cosa può fare davvero un conto da 12 mila euro in Italia

Questi vincoli hanno scartato più strategie di qualunque statistica.

| Vincolo | Fatto | Conseguenza |
|---|---|---|
| ETF americani | Un cliente al dettaglio dello Spazio economico europeo non può comprare ETF quotati negli USA: manca il documento KID (regolamento PRIIPs) [S17] `[S]` | SPY, QQQ, SVXY non sono acquistabili. Si usano ETF UCITS, CFD su indice, oppure opzioni e futures (che hanno il KID) |
| Micro futures | Un contratto MES vale 5 dollari per punto: con l'S&P 500 a 7.550 sono circa 37.700 dollari di controvalore (mia aritmetica) | Un solo MES è circa 3 volte il conto: niente dimensionamento fine. I micro futures diventano utili sopra i 50–100 mila euro |
| Leva sui CFD | Limiti ESMA per il dettaglio: 30:1 cambi maggiori, 20:1 indici principali e oro, 5:1 azioni, **2:1 crypto**; chiusura forzata al 50% del margine [S15] `[V]` | La leva sulle crypto è limitata per legge a 2x |
| Perpetual crypto | Per ESMA (24/2/2026) i perpetual ricadono "verosimilmente" nelle misure sui CFD: leva 2:1, KID, protezione dal saldo negativo [S15] `[V]` | Short e carry sulle crypto: disponibilità per residenti italiani **da verificare sede per sede** (IPOTESI) |
| Età e margine | IBKR: 18 anni per il conto cash, **21 per il conto a margine** [S17] `[S]` | Se hai meno di 21 anni: niente leva né short su IBKR (da farti confermare per iscritto) |
| Commissione minima | IBKR, azioni USA a tariffa fissa: 0,005 dollari per azione, minimo 1 dollaro [S17] `[S]` | Su un ordine da 500 euro il minimo pesa 0,2%: si ribilancia di rado e con una banda |
| Cliente professionale | Servono 2 requisiti su 3: 10 operazioni significative a trimestre per un anno; portafoglio oltre 500.000 euro; un anno di lavoro nel settore [S16] `[V]` | Non raggiungibile ora; toglierebbe i limiti di leva ma anche le protezioni |
| Costo del denaro | IBKR al 28/10/2026: dollaro 3,88% + 1,5% = 5,38% fino a 100 mila; euro 2,55% + 1,5% = 4,05% (da Lynx, broker introducente) [S17] `[V]` | Ogni punto di leva oltre 1x costa circa il 5% l'anno: nei backtest è contato |

### 2.4 I costi usati nei backtest

Ogni tabella di `RESULTS.md` dichiara il suo costo. Le ipotesi di base (STIMA, da sostituire con i costi misurati in paper):

| Strumento | Costo per lato | Come è composto |
|---|---:|---|
| Crypto spot su exchange UE | 30 pb | commissione taker 15–40 pb secondo la sede (Bitvavo 0,25%, Kraken Pro 0,40% `[S]`) più slippage |
| Perpetual crypto | 7 pb | taker 5 pb (Kraken 0,02%/0,05% `[S]`) più slippage |
| ETF / ETP su conto piccolo | 10 pb | commissione minima più mezzo spread |
| CFD o ETF su indice molto liquido | 5 pb | commissione 0,5 pb, mezzo spread, margine per il minimo di 1 dollaro |
| Indice intraday (prova di sensibilità) | 0,3–2 pb | SPY ha uno spread di circa 0,18 pb [S] ; un tick di ES è 0,33 pb |
| Leva a margine o CFD tenuto la notte | tasso a breve + 1,5% l'anno | tariffa IBKR |
| Cassa ferma | 0 (conto piccolo) | IBKR non remunera i saldi piccoli; sull'exchange la cassa non rende |

Ogni strategia tenuta è stata ricalcolata con i costi raddoppiati e con un giorno di ritardo nell'esecuzione (sezione 5.1).

### 2.5 Che cosa NON ho potuto verificare

- Le pagine ufficiali di IBKR hanno risposto con errore 403: commissioni, età e PRIIPs vengono da estratti di ricerca o da Lynx.
- La disponibilità dei perpetual per un residente italiano su una sede specifica.
- I rendimenti anno per anno dell'indice SG Trend tra il 2015 e il 2021 (i grafici sono immagini).
- Una replica indipendente di Kronos su mercati diversi dalle azioni cinesi (vedi 2.6).

### 2.6 I progetti open source che hai citato

Li ho fatti analizzare uno per uno. Sette su nove sono *strumenti* (framework, modelli, piattaforme): non hanno rendimenti propri da battere. Nessuno pubblica un registro di operazioni reali verificabile.

| Progetto | Che cos'è | Evidenza di rendimento | Limite per denaro reale | Che cosa ne ho preso |
|---|---|---|---|---|
| QuantOrb | Scanner di chi detiene memecoin su Solana, in gran parte chiuso; promuove un proprio token `[V]` | Nessuna | Non è un sistema di trading | Nulla |
| TradingAgents | Framework multi-agente LLM (analisti, dibattito rialzista/ribassista, trader, rischio) `[V]` | Paper degli autori: 3 mesi, 3 titoli, Sharpe 5,6–8,2, **senza costi**; replica indipendente su 12 mesi: Sharpe 0,43 lordo, 0,22 netto, peggio del comprare e tenere [R14] `[V]` | Non deterministico; un errore di look-ahead sulle notizie è rimasto aperto fino a giugno 2026 | Critica rialzista/ribassista come *ricerca*, mai come decisione d'ordine |
| day-trader-skill | 11 comandi per Claude Code; conto paper di default, conferma umana `[V]` | Nessuna; l'esempio del README: 33 segnali, 13 a obiettivo, 15 a stop, definito "quasi testa o croce" | Day trading su dati Yahoo | L'idea dei comandi: `/gerva-ricerca`, `/gerva-stato`, `/gerva-ipotesi` |
| Kronos | Modello fondazionale addestrato su 12 miliardi di candele, dati fino a giugno 2024 `[V]` | Backtest degli autori su azioni cinesi, costo 0,15%: extra-rendimento 18–21% l'anno, information ratio 1,4–1,6 [R15] `[V]`; nessuna replica indipendente trovata | Solo un segnale; il modello migliore non è pubblico | Verificato sui nostri dati: vedi sotto |
| ai-hedge-fund | Esempio didattico; il README dice "Not intended for real trading" `[V]` | Nessuna | Non esegue ordini | Registro con catena di hash (già presente nel repo, ora anche nel registro delle prove) |
| freqtrade | Bot crypto maturo: stesso codice in backtest, prova e reale `[V]` | Nessuna propria | Rischio di sovradattamento con l'ottimizzatore | **Parità backtest/live** (`gerva/strategies/book.py`) e test anti look-ahead |
| Qlib, RD-Agent | Piattaforma di ricerca di Microsoft `[V]` | Benchmark su azioni cinesi, media su 20 semi | Ricerca, non esecuzione | LLM che propone, backtest deterministico che giudica (`gerva/agents`) |
| AI-Trader | Banco di prova dal vivo per agenti LLM `[V]` | 5 settimane, 6 modelli: gli autori concludono "most agents exhibit poor returns and weak risk management" | Campione minuscolo | Confrontarsi sempre con l'indice |
| Hummingbot | Framework per market making e arbitraggio `[V]` | Solo volumi dichiarati | Il market making richiede capitale e gestione dell'inventario | Ciclo dell'ordine come macchina a stati |

**L'evidenza indipendente sugli agenti LLM che decidono le operazioni** è coerente e negativa:

- **FINSABER** (2004–2024, con costi): nessun agente LLM genera alpha statisticamente significativo (p > 0,34); Sharpe 0,09–0,10 contro 0,32–0,38 del comprare e tenere [R10] `[V]`.
- **Alpha Arena**, stagione 1 (18 ottobre–3 novembre 2025, 10.000 dollari *veri* per modello, perpetual): Qwen3 Max +22,3%, DeepSeek +4,9%, Claude Sonnet 4.5 −30,8%, Grok 4 −45,3%, Gemini 2.5 Pro −56,7%, GPT-5 −62,7% [R13] `[V, stampa secondaria]`. Il fondatore: "It's not yet feasible to directly hand over money to an LLM".
- **StockBench**: nella fase ribassista tutti gli agenti fanno peggio del riferimento passivo [R11] `[V]`.
- **LiveTradeBench**: la correlazione tra la classifica generale dei modelli e il loro rendimento è 0,05 [R12] `[V]`.

**Che cosa significa, onestamente, "battere questi progetti".** Non si può battere un rendimento che non esiste. Si può essere misurabilmente migliori su cinque dimensioni, ed è su queste che ho costruito:

| Dimensione | Stato in GERVA v5 |
|---|---|
| Rigore di validazione | Periodo di verifica separato, 110 prove contate, Deflated Sharpe pubblicato anche se è sotto soglia, walk-forward misurato |
| Realismo dei costi | Costi per sede, finanziamento della leva, costi raddoppiati e ritardo di un giorno su ogni strategia tenuta |
| Controlli di rischio fuori dagli LLM | Motore deterministico, KILL a ritenuta, tetto fisico di leva nel codice |
| Affidabilità | Ordini idempotenti, recupero dopo un crash, supervisore, misura dell'età dei dati |
| Registro reale verificabile | **Ancora da costruire**: è l'unica dimensione che richiede tempo, non codice (sezione 9) |

**Verifica di Kronos sui nostri dati** (SIMULATO; rapporto completo in [`research/v5/kronos_eval.md`](../research/v5/kronos_eval.md), script `research/v5/kronos_eval.py`). Ho fatto eseguire proprio la procedura che circola: Kronos-small, le ultime 128–256 candele, percorsi campionati, previsione a 24–48 barre, "quante volte il prezzo vero cade nella banda p10–p90", "gara tra i percorsi verso stop e obiettivo". Solo su date successive all'addestramento del modello (da luglio 2024 a ottobre 2026), con 50 percorsi per previsione invece di 1.000 per limiti di calcolo.

| Configurazione | Previsioni | Prezzo dentro la banda "80%": Kronos / estrazione ingenua | Direzione azzeccata [intervallo al 95%] / "sempre long" | Correlazione previsto–realizzato | Long/short netto per operazione |
|---|---:|---|---|---|---|
| BTC orario, 256 candele, 24 ore avanti | 704 | 41,1% / 83,2% | 51,7% [48,0; 55,4] / 53,1% | +0,004 [−0,07; +0,08] | −13,8 pb a 7 pb di costo; −59,8 pb a 30 pb |
| BTC orario, 128 candele, 48 ore (la "ricetta") | 417 | 33,6% / 82,0% | 52,0% [47,2; 56,8] / 50,1% | +0,009 | −8,4 pb; −54,4 pb |
| ETH orario, 24 ore avanti | 688 | 39,4% / 81,2% | 50,3% [46,6; 54,0] / 51,7% | −0,008 | −29,6 pb; −75,6 pb |
| SPY giornaliero, 5 giorni avanti | 117 | 29,4% / 81,4% | 42,7% [34,1; 51,8] / 61,5% | +0,144 [−0,002; +0,30] | −14,4 pb a 2 pb |

Tre conclusioni. (1) **Non è calibrato:** la banda che dovrebbe contenere il prezzo l'80% delle volte lo contiene tra il 29% e il 63%; un'estrazione casuale dei rendimenti passati, gratuita, lo fa nell'81–85% dei casi. (2) **Non prevede la direzione:** percentuali indistinguibili dal lancio di una moneta, e su SPY peggiori del semplice "sempre long". (3) **La "gara" verso stop e obiettivo non contiene informazione:** su Bitcoin l'obiettivo viene raggiunto nel 33% dei casi sia quando il modello gli assegna l'1% di probabilità sia quando gli assegna il 65%. Limiti: solo la versione piccola, senza addestramento ulteriore; circa 120 finestre indipendenti sui dati giornalieri. Verdetto: così com'è non entra nel sistema. Per riaprire la questione servirebbe un test in avanti dichiarato prima, su almeno 500 previsioni indipendenti per strumento.


---

## 3. Indicatori: GEX, VWAP e gli altri

### 3.1 VWAP: che cos'è e a che cosa serve davvero

Il VWAP (*volume weighted average price*) è il prezzo medio della seduta ponderato per i volumi:

```
VWAP_k = Σ_{j≤k} (P_j · V_j) / Σ_{j≤k} V_j        con  P_j = (massimo_j + minimo_j + chiusura_j) / 3
```

È il prezzo medio pagato da chi ha scambiato fino a quel momento. Nasce alla fine degli anni Ottanta come metro per giudicare la qualità di un'esecuzione (Berkowitz, Logue e Noser, 1988 `[R]`): un gestore che compra sotto il VWAP ha eseguito meglio della media del mercato. Per questo le istituzioni lo "difendono", ed è da qui che viene l'idea, diffusa tra i trader al dettaglio, che il prezzo sopra il VWAP indichi forza. Non ho trovato alcuno studio sottoposto a revisione che mostri un potere predittivo del VWAP al netto dei costi.

Codice: `gerva/indicators.py`, funzioni `session_vwap` e `vwap_bands` (VWAP più o meno *k* deviazioni standard ponderate). Sono causali: il valore alla barra *k* usa solo barre fino a *k* (test `test_session_vwap_is_causal_and_resets_each_day`).

### 3.2 GEX: che cos'è, e perché la versione "ingenua" è fragile

Chi vende un'opzione e non vuole rischio direzionale copre il *delta* comprando o vendendo il sottostante. Il *gamma* (Γ) dice quanto cambia quel delta quando il prezzo si muove, cioè quanto sottostante il venditore dovrà scambiare. Nel modello di Black e Scholes:

```
Γ = φ(d₁) / (S · σ · √T)        d₁ = [ ln(S/K) + (r + σ²/2)·T ] / (σ·√T)
```

Il GEX (*gamma exposure*) somma il gamma di tutte le opzioni aperte, per strike e scadenza, con un segno che dipende da chi si suppone abbia venduto [G1] `[V]`:

```
GEX = Σ_strike ( Γ_call · OI_call  −  Γ_put · OI_put ) · 100 · S        (dollari da scambiare per 1% di movimento)
```

- **GEX positivo**: i dealer sono "lunghi di gamma". Per restare coperti comprano quando il prezzo scende e vendono quando sale: smorzano i movimenti.
- **GEX negativo**: fanno il contrario, inseguono il prezzo: amplificano i movimenti.

Il segno poggia su quattro ipotesi dichiarate dagli stessi autori [G1] `[V]`: tutte le opzioni passano da chi copre il delta; le call sono vendute dagli investitori e comprate dai dealer; le put sono comprate dagli investitori e vendute dai dealer; la copertura è esatta. Tre critiche, tutte documentate:

1. **L'open interest non dice chi ha comprato.** Se a uno strike metà dei contratti è stata comprata e metà venduta dai clienti, l'esposizione netta dei dealer è circa zero, ma la formula restituisce un numero grande [G7] `[V]`.
2. **Le posizioni misurate non coincidono con quelle supposte.** Con i dati riservati del Cboe (2020–2023) il gamma dei market maker risulta "typically positive, [but] often negative" [G5] `[V]`.
3. **Le opzioni a scadenza giornaliera sfuggono alla fotografia.** Il Cboe stima che i privati facciano il 50–60% dei volumi 0DTE sull'S&P 500 e che la copertura netta dei market maker valga al massimo lo 0,2% della liquidità giornaliera dell'indice [G6b] `[V]`. Una fotografia di fine giornata dell'open interest non vede posizioni aperte e chiuse nella stessa seduta.

SqueezeMetrics stessa, nel 2020, ha abbandonato la convenzione ingenua per una basata sulla direzione delle singole transazioni [G2] `[V]`. Le fonti non concordano nemmeno su quante volte i dealer siano corti di gamma: 2.930 giorni su 6.088 secondo Baltussen e colleghi, "molto raramente" secondo SqueezeMetrics, 320 giorni su 3.779 (8,5%) nella serie che ho usato.

**Che cosa costa il dato.** La serie giornaliera di SqueezeMetrics dal 2011 è scaricabile gratuitamente ed è quella dei nostri test. I servizi intraday: SpotGamma da 89 a 299 dollari al mese, MenthorQ 129–349, ORATS (catene storiche dal 2007) 199–899, ThetaData 40–160 [G13] `[V]`. Per calcolare un GEX proprio da una catena di opzioni c'è `gex_from_chain` in `gerva/indicators.py` (profilo per strike, "muro" delle call e delle put, livello a cui il GEX cambia segno).

### 3.3 Che cosa dicono i nostri test (SIMULATO, dati 2011–2026)

**Il GEX prevede la volatilità, non la direzione.**

| Quintile del GEX di oggi (rango su 252 giorni) | Giorni | Rendimento medio di domani | t | Volatilità annua di domani | Giorno peggiore |
|---|---:|---:|---:|---:|---:|
| Q1, il più basso | 688 | +12,6 pb | 1,90 | 27,6% | −12,0% |
| Q2 | 631 | +9,9 pb | 2,34 | 16,8% | −4,0% |
| Q3 | 695 | +3,9 pb | 1,12 | 14,4% | −4,4% |
| Q4 | 707 | −1,7 pb | −0,57 | 12,5% | −3,6% |
| Q5, il più alto | 1.058 | +3,3 pb | 1,72 | 9,9% | −5,9% |

La volatilità quasi triplica passando dal quintile alto a quello basso (correlazione di rango −0,33, p ≈ 10⁻⁹³). Ma **il rendimento medio è più alto proprio quando il GEX è basso**: è un premio per il rischio, non un segnale di vendita. E il GEX aggiunge pochissimo a ciò che il VIX dice già: l'R² della regressione del movimento assoluto sul solo VIX è 0,292; aggiungendo il GEX sale a 0,301.

**Nessuna regola di esposizione basata sul GEX batte il comprare e tenere** (SPY, novembre 2011–novembre 2026, 5 pb per lato):

| Regola | CAGR | Volatilità | Sharpe | Caduta massima |
|---|---:|---:|---:|---:|
| SPY comprato e tenuto | 14,7% | 16,6% | **0,81** | −33,7% |
| "Regola diffusa": 1,5x con GEX nel 75% alto, cassa altrimenti | 9,6% | 17,0% | 0,53 | −32,3% |
| "Regola diffusa": long solo con GEX positivo | 11,9% | 13,2% | 0,79 | −22,4% |
| Contraria: 1,5x con GEX nel 25% basso, 1x altrimenti | 15,9% | 21,5% | 0,72 | −47,0% |
| Volatilità obiettivo 12% usando il VIX | 10,7% | 11,6% | 0,79 | −17,7% |

**L'effetto intraday condizionato al GEX: vero, poi scomparso.** Baltussen e colleghi [G4] `[V]` mostrano che il rendimento del resto della giornata prevede quello dell'ultima mezz'ora, e che sui futures S&P l'effetto è forte solo quando il gamma del giorno prima è negativo (pendenza 6,63, t = 4,78, contro 0,82, t = 1,03). L'ho replicato sull'S&P 500 a un minuto:

| Momentum dell'ultima mezz'ora | Periodo | Giorni | Rendimento lordo medio | t | Sharpe netto (0,5 pb) |
|---|---|---:|---:|---:|---:|
| Tutti i giorni | 2011–2018 | 1.906 | +1,5 pb | ≈ 3 | 0,45 |
| Solo con GEX di ieri nel 20% basso | 2011–2018 | 343 | **+7,5 pb** | **4,30** | **1,38** |
| Tutti i giorni, SPY | 2023-12 → 2026-11 | 721 | −2,0 pb | −2,54 | negativo |
| Solo con GEX basso, SPY | 2023-12 → 2026-11 | 122 | −2,9 pb | −1,02 | −0,81 |
| Solo con GEX basso, QQQ | 2023-12 → 2026-11 | 122 | −4,7 pb | −1,31 | −0,93 |
| Solo con GEX basso, IWM | 2023-12 → 2026-11 | 122 | −6,6 pb | −2,43 | −1,62 |

Nel periodo di scelta era la migliore strategia dell'intera ricerca. Nel periodo di verifica ha cambiato segno su tutti e tre gli indici. È l'esempio più istruttivo del documento: sette anni di backtest eccellente, con un meccanismo economico plausibile e una pubblicazione su una rivista di primo piano, non hanno retto ai tre anni successivi. (Limite: la verifica usa barre orarie di Yahoo, non a un minuto.)

**VWAP trend: la regola "Santo Graal".** Zarattini e Aziz [G8] `[V]` dichiarano per QQQ, 2018–2023, +671% con Sharpe 2,1 seguendo la regola "long se il prezzo chiude sopra il VWAP, short se sotto". Assumono una commissione di 0,0005 dollari per azione e *nessuno slippage*, con 21.967 operazioni (15 al giorno) e il 17% di operazioni in utile. Gli stessi autori, un anno dopo, indicano in 0,0035 dollari la tariffa d'ingresso di Interactive Brokers: sette volte tanto [G9] `[V]`. Chi ha provato a replicarla su QuantConnect non c'è riuscito [G10] `[V]`. I nostri numeri:

| Test | Operazioni al giorno | Lordo al giorno | Costo al giorno | Sharpe netto |
|---|---:|---:|---:|---:|
| 24 azioni del Nasdaq a 1 minuto, 2022–2024, costo zero | 17,4 | **−8,4 pb** | 0 | −1,89 |
| Idem, 1 pb per lato | 17,4 | −8,4 pb | 32,8 pb | −8,6 |
| Bitcoin a 5 minuti, 2017–2026, costo zero | 20,4 | **−16,3 pb** | 0 | −0,79 |
| Ether a 5 minuti, costo zero | 19,6 | +17,5 pb | 0 | 0,66 |
| Ether a 5 minuti, 7 pb per lato | 19,6 | +17,5 pb | 260 pb | −7,8 |
| Bitcoin con fascia morta dello 0,5%, 7 pb | 3,7 | +1,4 pb | 37,6 pb | −1,96 |

Su un paniere di azioni e su Bitcoin la regola perde già prima dei costi. Dove ha un margine lordo (Ether, Solana, singoli titoli molto volatili come Tesla) quel margine è di 17–45 pb al giorno contro 60–270 pb di costi.

**Momentum intraday fuori dalla "zona di rumore".** Zarattini, Aziz e Barbon [G9] `[V]` dichiarano il 19,6% l'anno con Sharpe 1,33 su SPY, 2007–2024, con leva fino a 4x. La regola di base, senza leva, nel loro stesso paper ha Sharpe 0,61 e rende meno di SPY: il risultato di copertina è la leva. Sull'S&P 500 2010–2018 ottengo uno Sharpe lordo di 0,50, coerente; ma il margine è di 1,16 pb al giorno con 1,84 operazioni: bastano 0,6 pb di costo per lato per azzerarlo. Fuori campione (maggio 2024–marzo 2026) uno studio indipendente trova +9,4% contro +29,5% del comprare e tenere, Sharpe 0,39 [G11] `[S]`.

### 3.4 Gli altri indicatori valutati

| Indicatore | Che cosa misura | Esito nei nostri test | Uso in GERVA |
|---|---|---|---|
| Segno del rendimento a 1, 3, 6, 12 mesi (insieme) | Trend | Sharpe 0,46 (ETF, lento) e 0,99 (BTC+ETH) | Segnale di CR-TREND e MA-TREND |
| Momentum relativo a 14, 28, 56 giorni | Forza relativa tra monete | Sharpe 0,77; con filtro 1,02 | Segnale di CR-XSMOM |
| BTC sopra la media a 100 giorni | Regime del mercato crypto | Porta la caduta da −83% a −75% e lo Sharpe da 0,77 a 1,02 | Filtro di CR-XSMOM |
| IBS, (chiusura − minimo) / (massimo − minimo) | Ipervenduto di giornata | Sharpe 0,55 su 27 anni | Segnale di EQ-MR |
| Volatilità realizzata a 60 giorni | Rischio corrente | — | Dimensionamento e leva |
| VIX / VIX a 3 mesi | Struttura a termine della volatilità | Evita alcune crisi, non tutte, e per un soffio | Non usato |
| Funding dei perpetual | Domanda di leva long | Dal 30–40% (2021) al 2–5% (2025–26) | Sospeso |
| DIX (vendite allo scoperto nei dark pool) | Presunto flusso istituzionale | Rendimento a 60 giorni per quintile: 3,6 / 3,2 / 2,9 / 3,0 / 3,1% contro 3,2% medio: nessuna relazione | Non usato |
| Media a 200 giorni | Regime azionario | Sharpe uguale al comprare e tenere | Non usato |

### 3.5 Decisione

- **Scelta:** GEX e VWAP non entrano nella generazione dei segnali. Il GEX resta un indicatore di *regime di volatilità* da mostrare, non da scambiare; il VWAP resta ciò per cui è nato, il metro per misurare la qualità delle esecuzioni in paper (cancello "costi reali / costi ipotizzati", sezione 5.2).
- **Motivazione:** nei dati il GEX non prevede la direzione e non aggiunge informazione al VIX; l'unico effetto intraday misurabile si è invertito fuori campione; il VWAP trend perde prima dei costi.
- **Alternative scartate:** (a) comprare un servizio GEX intraday (90–300 dollari al mese, cioè il 9–30% l'anno di un conto da 12 mila euro) per una strategia che nei dati non c'è; (b) usare l'ultima mezz'ora "finché funziona": non funziona più dal 2023; (c) combinare GEX e VWAP in un filtro: due segnali senza valore predittivo non ne producono uno con valore, producono più parametri da sovradattare.
- **La combinazione che rende di più**, tra tutte quelle provate, non contiene né GEX né VWAP: è il portafoglio della sezione 4.

---

## 4. Portafoglio e leva

### 4.1 Le quattro strategie

Ognuna è una funzione pura in [`gerva/strategies/book.py`](../gerva/strategies/book.py), usata identica dal backtest e dal ciclo live. Nessuna ha parametri ottimizzati: dove serve un orizzonte si fa la media su più orizzonti.

**CR-TREND, trend su Bitcoin ed Ether (solo long, spot).**
- *Regola:* per ciascuna moneta, segnale = media dei segni del rendimento a 30, 60 e 120 giorni, mai negativo; peso = segnale × (40% / volatilità recente) / 2, con tetto al 50% per moneta; ricalcolo ogni 7 giorni.
- *Perché dovrebbe funzionare:* nei mercati dominati da investitori che inseguono i prezzi e da leva che viene liquidata a cascata, i movimenti si prolungano. Stare fuori quando il trend è negativo evita la maggior parte delle cadute del 70–80%.
- *Numeri (SIMULATO, 30 pb per lato):* CAGR 25,3%, volatilità 22,6%, Sharpe 0,99, caduta massima −25,2%. Scelta 1,33, verifica 0,54.
- *Che cosa la uccide:* mercati laterali con falsi segnali; un exchange che fallisce.

**CR-XSMOM, momentum trasversale sulle crypto (solo long, spot).**
- *Regola:* ogni 7 giorni, tra le 20 monete più scambiate in quel momento si tengono le 5 con il momentum medio (14, 28, 56 giorni) più alto e positivo, un quinto ciascuna; tutto in cassa se Bitcoin è sotto la sua media a 100 giorni; esposizione ridotta per tenere la volatilità al 25%, mai sopra 1x.
- *Perché dovrebbe funzionare:* l'attenzione degli investitori si sposta lentamente da una moneta all'altra (Liu, Tsyvinski, Wu [S10]).
- *Numeri:* CAGR 32,1%, volatilità 27,9%, Sharpe 1,04, caduta massima −27,7%. Scelta 1,02, verifica 1,08. Senza il filtro e la riduzione: CAGR 36,9% ma caduta −82,6% e mesi da −47%.
- *Che cosa la uccide:* monete poco liquide (per questo solo le 20 più scambiate), distorsione di sopravvivenza dell'universo, un giorno di ritardo nell'esecuzione (Sharpe da 1,04 a 0,79).

**EQ-MR, ritorno alla media di breve su S&P 500 e Nasdaq 100.**
- *Regola:* si entra long quando la seduta chiude nel 20% basso del suo intervallo (IBS < 0,2), si esce quando chiude sopra il 70%; metà su ciascun indice. In posizione circa il 30% del tempo.
- *Perché dovrebbe funzionare:* le vendite forzate di fine giornata creano una pressione temporanea che rientra nei giorni successivi; chi compra fornisce liquidità ed è pagato per farlo.
- *Numeri (5 pb per lato più finanziamento notturno):* dal 2000 Sharpe 0,55; dal 2018 CAGR 12,1%, volatilità 13,2%, Sharpe 0,73, caduta −17,0%. Scelta 0,97, verifica 0,33.
- *Che cosa la uccide:* eseguire in ritardo (Sharpe 0,22 con un giorno di ritardo): va scambiata tra le 15:45 e le 16:00 di New York. È la strategia più fragile sul piano operativo.

**MA-TREND, trend lento su 17 ETF multi-asset (solo long, senza leva).**
- *Regola:* stessa logica di CR-TREND su azioni, obbligazioni, oro, materie prime, valute, con orizzonti a 3, 6 e 12 mesi, volatilità obiettivo 10% senza mai superare 1x, ricalcolo ogni 5 giorni.
- *Numeri (10 pb per lato):* dal 2005 CAGR 4,9%, Sharpe 0,46; dal 2018 Sharpe 0,16; verifica −0,12.
- *Perché è tenuta:* correlazione bassa con le altre e guadagni nelle crisi lunghe (2008, 2022). È però **la prima candidata all'esclusione**: con i costi raddoppiati il suo Sharpe dal 2018 è −0,05. Se in paper i costi reali superano quelli ipotizzati, va tolta.

Correlazioni dei rendimenti mensili: CR-TREND e CR-XSMOM 0,55; entrambe con MA-TREND circa 0,3; **EQ-MR con tutte le altre tra −0,06 e −0,08**. È la diversificazione, non una singola strategia, a portare lo Sharpe del portafoglio sopra quello di ciascun componente.

### 4.2 Allocazione tra strategie

- **Scelta:** parità di rischio. Ogni strategia riceve capitale in proporzione inversa alla propria volatilità degli ultimi 180 giorni, ricalcolata a inizio mese con soli dati passati; nessuna oltre il 60%; la volatilità usata non scende sotto metà di quella di lungo periodo (`gerva/portfolio/allocate.py`). Pesi medi: MA-TREND 44%, EQ-MR 27%, CR-TREND 17%, CR-XSMOM 12%.
- **Motivazione:** non richiede di stimare i rendimenti attesi, che sono la grandezza stimata peggio: con 8,6 anni di dati l'errore standard dello Sharpe è ±0,34.
- **Alternative scartate:** *media-varianza* (Markowitz) amplifica l'errore di stima e concentra tutto sulla strategia fortunata; *Kelly per strategia* richiede i rendimenti attesi; *pesi uguali* merita una nota onesta: **nel backtest fa meglio** (20,0% l'anno, volatilità 12,4%, Sharpe 1,31 contro 1,18), perché dà alle crypto il 50% del capitale invece del 29% e nel campione le crypto sono andate meglio. Non la adotto per due ragioni: sceglierla ora, dopo aver visto il risultato, sarebbe scegliere col senno di poi (una prova in più, non dichiarata prima), e quasi raddoppia l'esposizione al rischio che nessuno stop controlla, la controparte crypto. È la prima alternativa da riesaminare, a registro aperto, dopo il paper.
- **Un difetto trovato e corretto durante il lavoro:** una strategia rimasta in cassa per mesi ha volatilità quasi nulla e, senza il pavimento, si prendeva il 60% del capitale proprio mentre non lo usava.

### 4.3 La leva: teoria, numeri, scelta

**Il portafoglio senza leva (SIMULATO):** CAGR 13,8%, volatilità 9,0%, Sharpe 1,18, caduta massima −9,4%, mese peggiore −3,1%. Scelta 1,49, verifica 0,86.

**Che cosa direbbe Kelly.** La leva che massimizza la crescita logaritmica nel campione è 10,25x. Con quel numero in mano si sarebbe tentati di usare "mezzo Kelly", cioè 5x. È un errore, per tre ragioni:

1. *Kelly è ottimo solo se si conosce il vantaggio vero.* La formula usa il rendimento medio del backtest. Se il rendimento vero è la metà, la leva ottima è la metà; chi usa quella del backtest sta giocando a due volte Kelly, dove la crescita attesa è zero. E il nostro periodo di verifica dice proprio che il rendimento vero è più vicino alla metà.
2. *Kelly ignora ciò che il campione non contiene.* Otto anni di dati non includono il fallimento del proprio exchange.
3. *Kelly massimizza la mediana di lungo periodo, non la sopravvivenza.* Come osservò Samuelson, chi ha un orizzonte finito e un capitale che non può permettersi di dimezzare non ha la funzione obiettivo di Kelly.

**Che cosa dice il Monte Carlo** (4.000 percorsi di 3 anni, blocchi di 30 giorni, leva costante, costo della leva tasso + 1,5%). Tre scenari: *base* = la storia si ripete; *metà* = il rendimento in eccesso vero è metà di quello del backtest; *shock* = come il base, ma ogni giorno c'è lo 0,1% di probabilità di perdere un 15% in più (un evento ogni 2,7 anni circa).

| Leva | CAGR mediano: base / metà / shock | Caduta massima mediana: base / metà / shock | Probabilità di dimezzare il capitale in 3 anni: base / metà / shock |
|---:|---|---|---|
| 1x | 14% / 8% / 8% | −8% / −9% / −17% | 0,0% / 0,0% / 0,1% |
| 1,5x | 18% / 9% / 8% | −13% / −15% / −27% | 0,0% / 0,0% / 2,5% |
| **2x** | **22% / 10% / 8%** | **−17% / −21% / −35%** | **0,0% / 0,0% / 8,9%** |
| 3x | 29% / 12% / 6% | −25% / −32% / −52% | 0,1% / 2,4% / 27,6% |
| 4x | 36% / 12% / 1% | −33% / −42% / −67% | 1,3% / 9,6% / 45,9% |
| 6x | 47% / 11% / −30% | −47% / −58% / −93% | 9,0% / 31,4% / 67,0% |
| 10x | 57% / −3% / −100% | −70% / −81% / — | 34,6% / 65,2% / 77,7% |
| 15x | 43% / −31% / −100% | −87% / −95% / — | 61,7% / 86,1% / 87,2% |

La riga da guardare è la colonna "metà": **oltre 3x il CAGR mediano smette di crescere** (12% a 3x, 12% a 4x, 11% a 6x) mentre la probabilità di dimezzare passa dal 2% al 31%. Più leva, lì, compra solo rischio.

**Decisione.**
- **Scelta:** volatilità obiettivo del 15% annuo, leva massima operativa **2x**, tetto fisico nel codice **3x** (`HARD_MAX_LEVERAGE` in `gerva/risk/engine.py`: un valore più alto nel file di configurazione fa fallire l'avvio). La leva effettiva è volatilità obiettivo / volatilità recente del portafoglio: media 1,7x nel backtest.
- **Motivazione del 2x:** è il punto più alto in cui, nello scenario realistico, la probabilità di dimezzare il capitale resta sotto lo 0,1%, e anche nello scenario con shock resta sotto il 10%. A 3x lo shock porta la rovina al 28%.
- **Motivazione del tetto a 3x:** è dove il CAGR mediano realistico smette di crescere. Sopra non c'è alcun motivo, nemmeno teorico, per andare.
- **Risultato atteso a questa leva (SIMULATO):** CAGR 18,8%, volatilità 14,6%, Sharpe 1,07, caduta massima −15,1%. Nel periodo di verifica: 16,0% con Sharpe 0,74. Nello scenario realistico: **circa il 10% l'anno**.
- **Alternative scartate:** *1x fisso* (è il punto di partenza della fase reale, non l'obiettivo finale); *3x operativo* (28% di rovina nello scenario con shock); *mezzo Kelly, circa 5x* (rovina tra il 9% e il 67% secondo lo scenario); *leva scelta dagli agenti LLM segnale per segnale*, com'era nel banco futures simulato del vecchio codice fino a 25x: un modello linguistico stima male le probabilità ed è proprio l'errore di calibrazione, moltiplicato per la leva, che fa saltare un conto.

**Da dove viene, fisicamente, la leva con 12 mila euro.** Le crypto in spot non si possono portare oltre 1x, e i CFD crypto sono limitati a 2:1. La leva del conto può venire solo dalla parte azionaria (CFD su indice, margine). In pratica, nei primi mesi l'esposizione lorda reale starà tra 0,8x e 1,3x: il tetto a 2x diventerà rilevante solo con un conto a margine e più capitale.

### 4.4 Regole di stop e limiti

Tutto in `config/gerva.yaml`, applicato da `gerva/risk/engine.py` a ogni giro, prima di qualunque ordine.

| Regola | Soglia | Che cosa fa il sistema | Come si rientra |
|---|---:|---|---|
| Caduta dal massimo | −10% | Stato REDUCED: esposizione dimezzata | Solo quando la caduta rientra sotto il −5% |
| Caduta dal massimo | −15% | Stato HALTED: un quarto dell'esposizione, nessun aumento | Sotto il −7,5% passa a REDUCED |
| Caduta dal massimo | −20% | **KILL**: annulla gli ordini, chiude tutto, si ferma | Solo a mano: togliere il file KILL *e* `python -m gerva reset-kill --confirm`; riparte da HALTED |
| Perdita in 24 ore | −4% | REDUCED | Il giorno dopo, se la caduta lo consente |
| Perdita in 7 giorni | −8% | HALTED | Idem |
| Dati più vecchi di 36 ore (crypto) o 100 ore (azioni) | — | HALTED: si può solo ridurre | Automatico, quando tornano i dati |
| Ordine dall'esito ignoto | — | HALTED finché il broker non conferma | Automatico, dopo la riconciliazione |
| 5 giri falliti di fila | — | HALTED e allarme critico | Automatico, al primo giro riuscito |
| Peso di un singolo strumento | 35% | Il peso obiettivo viene tagliato | — |
| Esposizione su una sede crypto | 40% | L'insieme delle crypto viene ridotto in proporzione | — |
| Singolo ordine | 25% del patrimonio | Rifiutato (errore di battitura, bug) | — |
| Prezzo dell'ordine | oltre il 5% dall'ultimo noto | Rifiutato | — |
| Leva lorda | 2x (mai oltre 3x) | I pesi vengono riscalati | — |

Due principi: **si scende subito e si risale con isteresi**, per non rientrare a pieno carico in mezzo a una crisi; e **un ordine che riduce una posizione passa sempre**, in qualunque stato. Il vecchio gateway faceva il contrario: in caduta bloccava anche le chiusure.

*Perché queste soglie.* A 2x la caduta massima mediana simulata a tre anni è del 17% e il quinto percentile del 26%. Il KILL al 20% taglia la coda di quella distribuzione; lo scalino al 10% dimezza l'esposizione prima di arrivarci. Se le strategie smettessero semplicemente di funzionare, la perdita si fermerebbe attorno al 20–22%.

### 4.5 Il piano per il caso peggiore

| Scenario | Perdita massima plausibile | Che cosa la limita | Che cosa resta scoperto |
|---|---:|---|---|
| Le strategie smettono di funzionare (declino lento) | 20–22% | Scalini a −10%, −15%, KILL a −20% | Nulla: è il caso per cui gli scalini esistono |
| Crollo delle crypto del 50% in un fine settimana | fino al 20% | Tetto del 40% sulla sede crypto; il trend è spesso già fuori | Il salto di prezzo avviene prima che il ciclo possa reagire |
| **L'exchange crypto fallisce o blocca i prelievi** | **fino al 40%** | Tetto del 40%; cassa non impegnata tenuta in banca; sopra i 25 mila euro, due sedi | **Nessuno stop protegge da questo.** È il rischio più grande del progetto |
| S&P 500 a −20% in un giorno (ottobre 1987) | 5–10% | EQ-MR pesa circa un quarto ed è in posizione il 30% del tempo | Il CFD si chiude al 50% del margine |
| Interactive Brokers non raggiungibile | Nessuna diretta | Stato HALTED, posizioni ferme, allarme | Non si può chiudere finché non torna |
| Errore del software (ordine sbagliato, ciclo impazzito) | 25% del patrimonio per ordine | Tetto per ordine, controllo del prezzo, un ordine per simbolo al giorno, KILL manuale | Un errore nella logica dei pesi: per questo servono 90 giorni di paper |
| Il computer si spegne | Nessuna diretta | Supervisore e servizio di sistema riavviano; nessun ordine va perso o duplicato | Le posizioni restano senza sorveglianza finché non riparte: serve un server, non un portatile |

### 4.6 Quanto ci si avvicina al 20–30% al mese

| Leva | Mese medio (base) | Mese medio (realistico) | Mesi con almeno +20% | Mesi con −20% o peggio | Probabilità di dimezzare in 3 anni (base → shock) |
|---:|---:|---:|---:|---:|---|
| 1x | 1,1% | 0,7% | 0,0% | 0,0% | 0,0% → 0,1% |
| 2x | 1,7% | 0,9% | 0,6% | 0,0% | 0,0% → 8,9% |
| 3x | 2,4% | 1,2% | 2,5% | 0,1% | 0,1% → 27,6% |
| 6x | 4,4% | 1,9% | 14,4% | 2,5% | 9,0% → 67,0% |
| 10x | 7,0% | 2,8% | 23,9% | 11,0% | 34,6% → 77,7% |
| 15x | 10,1% | 3,8% | 29,3% | 22,0% | 61,7% → 87,2% |

Risposta diretta alla tua domanda: **con un rischio di rovina accettabile ci si avvicina fino a circa l'1–2% al mese**, cioè un quindicesimo dell'obiettivo. Singoli mesi sopra il 20% compaiono solo quando compaiono, in numero quasi uguale, mesi sotto il −20%. Nemmeno a 15x il mese *medio* supera il 10%, e a quella leva due conti su tre vengono dimezzati entro tre anni.

**La leva che conta davvero a questa scala è il risparmio.** Aggiungere 300 euro al mese per tre anni porta 10.800 euro: quanto un rendimento del 90% sul capitale iniziale, a rischio zero. Fino a 50 mila euro circa i versamenti pesano più di qualunque scelta di leva. Il rendimento composto diventa il motore solo dopo.

---

## 5. Validazione

### 5.1 Il protocollo e che cosa ha mostrato

| Controllo | Come è fatto | Esito |
|---|---|---|
| Periodo di verifica separato | Scelte fino al 31/12/2022; dal 2023 solo misura | Sharpe del portafoglio 1,49 → 0,86 |
| Costi realistici | Per sede, più finanziamento della leva, più cassa che non rende | Già nei numeri di base |
| Costi raddoppiati | Ogni strategia ricalcolata | Portafoglio 1,18 → 0,97; MA-TREND diventa negativa |
| Un giorno di ritardo nell'esecuzione | `lag=2` nel motore | Portafoglio 1,18 → 0,83; EQ-MR 0,73 → 0,22 |
| Nessun look-ahead | Test di troncamento: il peso alla riga *t* calcolato con i dati fino a *t* deve coincidere con quello calcolato su tutta la storia, in 40 punti casuali, per ogni strategia in produzione. Un segnale che usa la chiusura di domani viene scoperto | Verde (`tests/test_gerva_core.py`) |
| Walk-forward sui parametri | Ogni 1° gennaio si sceglie la configurazione migliore dei 3 anni precedenti e la si usa per l'anno dopo | Le configurazioni scelte avevano Sharpe 1,40 in addestramento e **0,54** l'anno dopo; l'insieme di tutte, senza scegliere, 0,63 |
| Walk-forward su allocazione e leva | Pesi e leva usano solo dati precedenti, per costruzione | È il risultato riportato |
| Fortuna da prove multiple | Registro di 110 configurazioni; Sharpe atteso dal migliore di 110 tentativi senza abilità: 1,18 | **Deflated Sharpe 0,51** (soglia 0,95): non superato |
| Monte Carlo | Bootstrap a blocchi, tre scenari, 4.000 percorsi | Tabelle della sezione 4.3 |
| Parità backtest/live | I pesi del ciclo live sono l'ultima riga delle stesse funzioni della ricerca | Test `test_live_weights_equal_backtest_last_row` |

Il walk-forward merita un commento. Scegliere ogni anno la configurazione che è andata meglio negli ultimi tre fa *peggio* che non scegliere affatto (0,54 contro 0,63). La differenza tra 1,40 e 0,54 è il sovradattamento da selezione, misurato su dati veri. È il motivo per cui le strategie in produzione mediano su più orizzonti.

**Limiti dichiarati.** (1) Conosco la storia dei mercati fino a oggi: le *famiglie* di strategie che ho scelto di provare sono influenzate da ciò che so aver funzionato, anche se i parametri non sono stati scelti sul periodo di verifica. (2) L'universo crypto comprende monete poi fallite (LUNA, FTT, EOS) ma non quelle mai quotate su Binance. (3) Gli ETF americani sono usati come sostituti degli strumenti realmente acquistabili (UCITS, CFD), che hanno costi e orari diversi. (4) Tutto è in dollari: per un conto in euro il cambio aggiunge una volatilità del 7–8% l'anno alla parte non coperta. (5) Otto anni e mezzo sono pochi: l'intervallo di confidenza dello Sharpe è largo.

### 5.2 Paper trading: i cancelli numerici

Il ciclo live gira in paper con prezzi veri (`python -m gerva run`). Il passaggio al denaro reale non è un'opinione: è una tabella calcolata dal codice (`gerva/live/gates.py`, comando `python -m gerva gates`, visibile nella dashboard). **Tutti verdi, oppure si resta in paper.**

| # | Cancello | Soglia | Perché |
|---:|---|---|---|
| 1 | Giorni consecutivi di paper | ≥ 90 | Un trimestre copre almeno 12 ribilanciamenti settimanali e una sessantina di operazioni di EQ-MR |
| 2 | Disponibilità del ciclo | ≥ 99% dei giri attesi | Un sistema che salta l'1% dei giri salta anche gli stop |
| 3 | Ordini non riconciliati | 0 | Un solo ordine dall'esito ignoto è un difetto del software |
| 4 | KILL scattati | 0 (oppure spiegati per iscritto) | Un KILL per mercato va capito; uno per bug va corretto |
| 5 | Caduta massima in paper | ≤ 10% | È la soglia del primo scalino |
| 6 | PSR, probabilità che lo Sharpe vero sia sopra zero | ≥ 0,60 | Novanta giorni non provano uno Sharpe; bastano a scoprire che è negativo |
| 7 | Scostamento dal backtest sugli stessi giorni | ≤ 3 punti | Se il paper non replica il backtest, il backtest non descrive il sistema |
| 8 | Costi reali / costi ipotizzati | ≤ 1,5 | Se i costi veri sono il doppio, MA-TREND esce e il portafoglio va ricalcolato |

I cancelli 7 e 8 richiedono il confronto con la replica del backtest sugli stessi giorni: oggi restano rossi per costruzione finché quel confronto non viene eseguito. È il primo lavoro da fare dopo l'avvio del paper.

### 5.3 Dal paper al reale: la rampa

| Fase | Capitale | Leva massima | Si passa alla successiva se |
|---|---|---:|---|
| Paper | 0 | 2x simulata | Tutti gli 8 cancelli verdi |
| Reale 1 | 25% (circa 3.000 €) | 1x | 60 giorni; scostamento dal paper parallelo ≤ 3 punti; nessun incidente operativo |
| Reale 2 | 50% | 1x | Altri 60 giorni; caduta ≤ 10% |
| Reale 3 | 100% | 1,5x | 6 mesi; Sharpe realizzato ≥ 0,4 |
| Regime | 100% più versamenti | 2x | Mai senza 12 mesi di registro reale |

In ogni fase il paper continua a girare in parallelo: è il gruppo di controllo. Si torna indietro di una fase a ogni KILL o a ogni caduta oltre il 15%.

---

## 6. Architettura: un sistema che non si ferma, e che quando si ferma lo fa apposta

### 6.1 Il principio

Un sistema di trading "che non si blocca mai" non esiste: esistono sistemi in cui **ogni guasto ha una risposta decisa in anticipo**, e in cui il guasto di un componente non diventa né un ordine sbagliato né un silenzio. Il vecchio ciclo aveva tre debolezze strutturali: un'eccezione fermava tutto il giro, gli ordini verso Alpaca potevano duplicarsi dopo un errore di rete, e il lavoro critico (stop, rischio) stava in coda a chiamate lente agli LLM. Il nuovo nucleo le elimina per costruzione.

### 6.2 Lo schema

```
                         ┌─────────────────────────────────────────────┐
   systemd / Docker ───► │ supervisore            gerva/ops/supervisor │  riavvia se muore o se smette di battere
                         └───────────────┬─────────────────────────────┘
                                         ▼
   ┌──────────────────────────────── ciclo, ogni 15 minuti ── gerva/live/runner.py ─────────────────────────┐
   │ 1 battito → 2 recupero ordini → 3 dati → 4 conto → 5 RISCHIO → 6 KILL? → 7 pesi → 8 ordini → 9 foto    │
   └───┬──────────────┬───────────────┬──────────────┬──────────────┬────────────────┬──────────────┬──────┘
       ▼              ▼               ▼              ▼              ▼                ▼              ▼
   registro       dati di         broker        motore di      strategie        portafoglio    fotografia
   SQLite WAL     mercato         (paper,       rischio        book.py          risk parity,   JSON atomica
   ops/journal    live/market     Alpaca)       risk/engine    (= backtest)     leva           live/snapshot
                                                                                                    │
                                                              dashboard/ (sola lettura) ◄───────────┘
                                                              può soltanto CREARE il file KILL

   consiglio di ricerca (gerva/agents): propone schede → backtest → registro delle prove → cancello
   NON ha accesso a: broker, limiti di rischio, file KILL, ciclo live
```

### 6.3 Guasto per guasto

| Che cosa si rompe | Che cosa fa il sistema | Dove |
|---|---|---|
| Un passo del giro solleva un'eccezione | Il giro fallisce, viene registrato e segnalato; il giro dopo riparte. Nessuna eccezione esce da `run_forever` | `runner.py`, test `test_run_forever_survives_exceptions_and_counts_streak` |
| Cinque giri falliti di fila | Stato HALTED, allarme critico | `risk/engine.py` |
| Una sorgente dati non risponde | L'altra sede continua; dopo 3 errori l'interruttore si apre per 5 minuti e non si insiste | `ops/resilience.py`, `live/market.py` |
| I dati sono vecchi | Si può solo ridurre; stato HALTED | `Market.ages`, test `test_stale_data_blocks_increases_but_not_the_cycle` |
| Il processo muore tra "decido l'ordine" e "lo invio" | L'intenzione era già nel registro: al riavvio si chiede al broker; se non l'ha mai vista, l'ordine viene annullato e ricalcolato | `Runner.recover`, test `test_crash_between_intent_and_submit_is_recovered_without_resend` |
| Il processo muore dopo l'invio ma prima di registrare l'esito | Il broker conosce l'identificativo: l'esito viene letto, l'ordine non viene ripetuto | idem |
| La rete cade durante l'invio (esito ignoto) | L'ordine resta "in sospeso"; nessun altro ordine finché il broker non risponde | test `test_unknown_outcome_halts_trading_until_reconciled` |
| Lo stesso giro viene eseguito due volte | Un ordine per simbolo e per giorno di decisione: la chiave primaria del registro lo impedisce | test `test_cycle_trades_once_and_rerun_does_not_duplicate` |
| Il processo si appende senza morire | Il supervisore vede il battito fermo da 15 minuti, lo termina e lo riavvia | `ops/supervisor.py` |
| Il processo cade in continuazione | Dopo 10 riavvii in un'ora il supervisore si ferma e avvisa: insistere farebbe solo danni | test `test_supervisor_restarts_then_gives_up` |
| La macchina si riavvia | systemd (`deploy/gerva.service`) o Docker (`deploy/docker-compose.gerva.yml`) rilanciano il supervisore | — |
| Caduta del 20%, o KILL premuto | Annulla gli ordini, chiude tutto, esce con codice 3: né il supervisore né systemd lo riavviano | test `test_kill_flattens_and_runner_exits_with_code_3` |
| Il disco si riempie o il database si corrompe | Le scritture falliscono, il giro fallisce, scatta HALTED. Il registro è in modalità WAL con sincronizzazione completa | `ops/journal.py` |
| La dashboard cade | Nessun effetto sul trading: legge un file | — |
| Il ciclo cade e la dashboard resta su | La fotografia invecchia; la dashboard mostra "DATI VECCHI" invece di numeri fermi | `meta.stale_after_s` |

### 6.4 Monitoraggio, log, allarmi

- **Registro degli eventi**: ogni cambio di stato, ordine rifiutato, guasto, riavvio è una riga nella tabella `events`, e compare nella dashboard.
- **Battiti dei componenti**: dati per sede, broker, con latenza ed età dell'ultimo successo.
- **Allarmi esterni**: Telegram o un webhook qualsiasi, da variabili d'ambiente (`GERVA_TELEGRAM_TOKEN`, `GERVA_TELEGRAM_CHAT`, `GERVA_WEBHOOK_URL`). Non sollevano mai eccezioni e non si ripetono più di una volta ogni 15 minuti, tranne i critici.
- **Log**: su standard output, raccolti da journald o da Docker con rotazione (10 MB × 5).

### 6.5 Decisioni di architettura

| Decisione | Scelta | Motivazione | Alternative scartate |
|---|---|---|---|
| Dove vive la logica di trading | Pacchetto nuovo `gerva/`, senza LLM nel percorso degli ordini | L'evidenza indipendente sugli LLM che decidono le operazioni è negativa (2.6); il codice deterministico si può provare | Aggiustare `firm/` in loco: i percorsi verso il broker erano quattro, senza un punto unico di controllo |
| Stato durevole | Un file SQLite in WAL, un solo processo che scrive | Transazioni vere, nessun servizio da amministrare; adatto a un giro ogni 15 minuti | PostgreSQL o Redis: un altro processo che può cadere, per un carico che non lo richiede |
| Duplicati | Identificativo dell'ordine deterministico (giorno + simbolo), intenzione scritta prima dell'invio | È l'unica difesa che regge a un crash in qualunque punto | Retry sull'invio: è esattamente ciò che crea i duplicati |
| Cadenza | Giro ogni 15 minuti; decisioni giornaliere o settimanali | Tutte le strategie tenute sono lente; la velocità non è un vantaggio che possiamo avere | Flussi in tempo reale: complessità senza beneficio |
| Dashboard | Sola lettura su un file; unico potere, creare il file KILL | Una vulnerabilità web non può inviare ordini né cambiare limiti | Dashboard che scrive nel database del ciclo |
| Dove gira | Un server Linux piccolo (4–6 € al mese), non il portatile | Il vecchio sistema girava su un Mac tenuto sveglio | Il Mac con `launchd`: basta chiudere il coperchio |
| Agenti LLM | Solo ricerca: propongono schede, criticano, non decidono | Un errore costa una prova in più, non denaro | Agenti che scelgono leva e operazioni, com'era nel banco libero |

### 6.6 Struttura del repository

```
gerva/                 il motore deterministico (nuovo)
  data/                sorgenti pubbliche con cache e impronta del contenuto
  indicators.py        VWAP, GEX, zona di rumore, volatilità: funzioni causali
  backtest/            motore giornaliero con leva, finanziamento, costi
  strategies/          daily.py, intraday.py (tutte le regole provate); book.py (le quattro in produzione)
  validation/          metriche, PSR, Deflated Sharpe, Monte Carlo, Kelly empirico
  portfolio/           parità di rischio, leva a volatilità obiettivo
  risk/                limiti e motore di rischio in tempo reale
  execution/           interfaccia broker, broker paper, adattatore Alpaca paper
  ops/                 registro, retry, interruttore, allarmi, supervisore
  live/                feed, pipeline dei pesi, ciclo, fotografia, cancelli
  agents/              consiglio di ricerca: schede, cancello, registro delle prove
  research/run.py      tutti i backtest del documento, in un comando
dashboard/             server e pagina (nuovi)
config/gerva.yaml      limiti e parametri del ciclo
research/v5/           risultati generati: RESULTS.md, results.json, series.parquet
tests/test_gerva_*.py  test del motore; test_audit_v5.py: regressioni dell'audit
.claude/               sotto-agenti e comandi per lavorare sul progetto da Claude Code
firm/, llm/, agents/,  la società di agenti preesistente: resta come laboratorio in paper,
portal/, quantlab/     con i difetti critici corretti (sezione 1)
```

### 6.7 Che cosa NON è verificato

- **L'adattatore Alpaca** è collaudato contro un servizio finto che ne imita le risposte, non contro Alpaca: da questo ambiente non avevo chiavi. Il primo collegamento va fatto con `python -m gerva check-broker` e un ordine da 25 dollari guardato a mano.
- **Non esiste ancora un adattatore del nuovo motore per Interactive Brokers.** Il vecchio `firm/ibkr.py` è solido (ordini limite, idempotenza con `orderRef`, annullamenti confermati) e va incapsulato nell'interfaccia `Broker`: è un lavoro della fase 2 della roadmap, da fare con il conto paper di IBKR davanti.
- **I prezzi delle azioni in paper vengono da Yahoo**, che non è una fonte ufficiale e può cambiare senza preavviso. Con IBKR collegato vanno presi da lì.
- **Le festività di borsa** non sono gestite esplicitamente: in un giorno festivo la barra del giorno manca e il ciclo non scambia le azioni (comportamento corretto, ma per assenza, non per calendario).
- **Il conto è in dollari**: la conversione in euro e il rischio di cambio non sono modellati.

---

## 7. Struttura societaria

**Avvertenza.** Non sono un avvocato né un commercialista, e questa sezione non è una consulenza. Le norme sono cambiate molto tra il 2025 e il 2026; dove non ho potuto leggere la fonte primaria lo dico. Ogni scelta va confermata da un professionista: l'elenco di ciò che deve verificare è in 7.5.

### 7.1 Che cosa è cambiato di recente (FATTO, salvo dove indicato)

| Tema | Stato a novembre 2026 | Fonte |
|---|---|---|
| Plusvalenze su cripto-attività | **33% dal 1° gennaio 2026** (era 26%); resta al 26% solo per gli e-money token in euro; franchigia di 2.000 euro abolita dal 2025 | L. 207/2024 e L. 199/2025 [L1] `[V]` |
| Imposta sulle transazioni finanziarie (Tobin tax) | Raddoppiata dal 2026: 0,2% sui mercati regolamentati, 0,4% fuori, 0,04% sull'alta frequenza. Riguarda le azioni di società italiane sopra i 500 milioni di capitalizzazione, non gli ETF né i futures esteri | [L2] `[V]` |
| Nuovo testo unico delle imposte sui redditi | Dal 1° gennaio 2027 cambia la numerazione degli articoli | [L3] `[S]` |
| Perpetual | Per ESMA ricadono verosimilmente nelle regole sui CFD (leva 2:1 sulle crypto) | [S15] `[V]` |
| Scambio automatico di dati sulle crypto (DAC8) | Raccolta dei dati dal 2026, primo scambio tra amministrazioni nel 2027 | [L4] `[S]` |
| Abusivismo finanziario | Cassazione 14193/2026: il reato richiede esercizio *professionale* e *nei confronti del pubblico* | [L5] `[V, massima]` |

### 7.2 I veicoli a confronto

| Veicolo | Che cosa permette | Tassazione | Costi annui (STIMA) | Quando ha senso |
|---|---|---|---:|---|
| **Persona fisica, conto proprio** | Operare con denaro proprio, senza alcuna autorizzazione (art. 4-terdecies TUF) `[V]` | 26% (12,5% sui titoli di Stato); crypto 33%; IVAFE 0,2%; quadri RW, RT, RM in dichiarazione | 300–1.000 € di commercialista | **Da 10 mila a 500 mila euro** |
| Conto dei genitori con delega (o Family Account IBKR) | Operare sui conti dei familiari, **senza compenso** | In capo a ciascun titolare | Come sopra, per titolare | Capitale dei genitori, se non te lo donano |
| Società semplice | Patrimonio comune di pochi familiari; nessuna attività commerciale | Per trasparenza, regole della persona fisica | 500–1.500 € più LEI | Sopra i 100 mila, solo per dare regole chiare tra familiari |
| SRL o SRLS | Trading in conto proprio (non è attività riservata) | IRES 24% più IRAP, poi 26% sui dividendi: carico complessivo 43–44% | 3.000–7.000 € più 1.500–3.500 di costituzione | Sopra i 300–500 mila, o come futuro gestore |
| Consulente finanziario autonomo (albo OCF) | Sola consulenza; mai detenere denaro dei clienti | Reddito professionale | Contributo OCF, polizza | Primi clienti esterni |
| Fornitore di strategia su piattaforma autorizzata | La piattaforma è il gestore; tu fornisci il segnale | Compenso | Variabile | La via leggera più usata per raccogliere capitale esterno `[R]` |
| Fondo ospitato all'estero, SIM, SGR | Raccolta di capitale di terzi | Variabile | 100–250 mila € | Massa critica di 10–20 milioni |

### 7.3 Decisione

- **Scelta:** persona fisica, con il conto intestato a te. Il capitale dei genitori entra in uno di due modi: **donazione** (la franchigia in linea retta è di 1 milione di euro per beneficiario `[V, fonte divulgativa]`; per importi non modici la forma è l'atto pubblico, e un bonifico "per liberalità" senza atto può essere nullo secondo le Sezioni Unite del 2017 `[S]`), oppure **prestito infruttifero** con scrittura a data certa. In alternativa il conto resta loro e tu operi con una delega, senza alcun compenso.
- **Motivazione:** a questa scala ogni struttura costa più di quanto fa risparmiare. Una SRL da 5.000 euro l'anno su 12.000 di capitale assorbe il 40% del patrimonio prima di qualunque rendimento, e tassa due volte.
- **Il nodo fiscale che orienta la scelta degli strumenti.** In Italia i guadagni sugli ETF sono *redditi di capitale*, le perdite *redditi diversi*: **non si compensano**. Azioni, futures, opzioni, CFD ed ETC sono tutti redditi diversi e si compensano tra loro per quattro anni `[R]`. Le crypto fanno categoria a sé: si compensano solo con altre crypto. Conseguenze pratiche: EQ-MR via CFD su indice è fiscalmente più efficiente che via ETF; per MA-TREND, dove servono gli ETF, la non compensabilità è un costo da mettere nel conto; gli ETF americani (non armonizzati) sarebbero tassati ad aliquota progressiva IRPEF, e comunque non sono acquistabili.
- **Regime dichiarativo.** Interactive Brokers non fa da sostituto d'imposta: tutto va in dichiarazione (quadri RW, RT, RM, oppure W e T nel 730) `[S]`. Un broker italiano in regime amministrato toglierebbe questo lavoro, ma con meno strumenti e commissioni più alte.
- **Alternative scartate:** *SRL subito* (costi e doppia tassazione); *società estera* (LLC americana, OÜ estone, LTD inglese, Dubai): è residente in Italia se qui ha la direzione effettiva, art. 73 TUIR `[S]`, quindi non cambia le tasse e aggiunge obblighi e rischi; *"gestire" il denaro di amici dividendo gli utili*: vedi sotto.

### 7.4 La linea da non superare

L'articolo 166 del Testo unico della finanza punisce chi presta servizi di investimento o gestione collettiva senza autorizzazione con **la reclusione da uno a otto anni** e la multa da 4.000 a 10.000 euro `[V]`. Gestire in modo occasionale e gratuito il denaro dei propri genitori non dovrebbe integrare il reato; non ho trovato precedenti specifici sul caso "familiari", quindi resta un punto da parere legale (IPOTESI). Gli indici di rischio sono chiari:

- un compenso o una quota degli utili;
- più persone, soprattutto non familiari;
- il passaparola, i social, qualunque forma di sollecitazione;
- la continuità organizzata.

Anche pubblicare segnali ha regole: generici e rivolti al pubblico sono "raccomandazioni di investimento" (regolamento sugli abusi di mercato, art. 20) con obblighi di trasparenza; personalizzati o eseguiti in automatico diventano attività riservata. Per l'ESMA il copy trading con esecuzione automatica è di regola gestione di portafogli [L6] `[S]`. Il nome "GERVA Capital" e una dashboard pubblica con rendimenti, se rivolti a terzi, vanno valutati con un legale *prima* della pubblicazione.

**Quando vorrai capitale esterno**, le strade sono, in ordine di leggerezza: fornitore di strategia dentro una piattaforma autorizzata; consulente autonomo iscritto all'albo; fondo ospitato o SIM quando la massa lo giustifica. In tutte, ciò che conta è un **registro reale verificabile di almeno 12–24 mesi**: è quello che questo progetto deve produrre.

### 7.5 Da far verificare a un professionista

1. Testo in Gazzetta Ufficiale della legge di bilancio 2026 (crypto al 33%, eccezione per gli e-money token in euro) ed esito della legge di bilancio 2027.
2. Qualifica fiscale dei perpetual e dei derivati su crypto: 26% o 33%? Non ho trovato un chiarimento ufficiale.
3. Donazione o prestito dei genitori: forma, "modico valore" rispetto al loro patrimonio, franchigia vigente.
4. Delega sul conto dei genitori e art. 166: parere di un avvocato, soprattutto se compare qualunque forma di compenso.
5. Età minima, tipo di conto e accesso ai futures e ai CFD su IBKR: conferma scritta del broker.
6. Regole IBKR su procure e Family Account per residenti italiani.
7. IVAFE sulla liquidità presso IBKR e credito per le ritenute estere sui dividendi.
8. Rischio che un sistema automatico con molte operazioni sia considerato attività d'impresa abituale (basso, ma non nullo).
9. Stato autorizzativo (MiCA, MiFID) dell'exchange crypto scelto e copertura in caso di insolvenza. Il fondo di indennizzo irlandese copre il 90% fino a 20.000 euro per i clienti di IBKR Ireland `[S]`; per le crypto non esiste una garanzia analoga.
10. Ogni schema di segnali, copy trading o pagina pubblica con rendimenti, prima del lancio.
11. Qualunque struttura estera, prima di costituirla.
12. La nuova numerazione del testo unico dal 2027, per i riferimenti in dichiarazione.

---

## 8. Sito e dashboard

<!-- DASHBOARD -->

---

## 9. Roadmap

### 9.1 Fasi, tempi, criteri

| Fase | Durata | Che cosa si fa | Criterio per andare avanti (GO) | Criterio per fermarsi (NO-GO) |
|---|---|---|---|---|
| **0. Messa in opera** | 1–2 settimane | Server Linux; ciclo in paper interno; dashboard; allarmi Telegram; conto paper Alpaca collegato per le crypto | Ciclo attivo 7 giorni senza interventi; fotografia sempre fresca | Più di 2 giri falliti al giorno |
| **1. Paper** | 90 giorni | Paper trading completo; misura dei costi reali; replica quotidiana del backtest per i cancelli 7 e 8; adattatore IBKR sul conto paper | Tutti gli 8 cancelli verdi (5.2) | Scostamento dal backtest oltre 3 punti, oppure Sharpe paper negativo con PSR < 0,3: si torna alla ricerca |
| **2. Reale, un quarto** | 60 giorni | 25% del capitale, leva 1x, paper in parallelo; apertura dei conti; commercialista | Scostamento dal paper ≤ 3 punti; nessun incidente | Un KILL per difetto del software; costi reali oltre il doppio di quelli ipotizzati |
| **3. Reale, metà e poi intero** | 4–6 mesi | 50% poi 100%, leva fino a 1,5x | Sharpe realizzato ≥ 0,4 su 6 mesi; caduta ≤ 15% | Caduta oltre il 15%: si torna alla fase precedente |
| **4. Regime** | dal mese 12 | Leva fino a 2x; versamenti mensili; due sedi crypto sopra i 25 mila euro; nuove strategie dal consiglio di ricerca, sempre via paper | Rivalutazione ogni 6 mesi: se lo Sharpe a 12 mesi è sotto 0,3 si riduce a 1x | Sharpe a 18 mesi negativo: stop e riesame completo |
| **5. Capitale esterno** | non prima del mese 24 | Registro reale di 24 mesi; parere legale; piattaforma autorizzata oppure albo dei consulenti | Registro verificabile; struttura approvata da un legale | Nessuna raccolta senza struttura autorizzata |

### 9.2 Costi (STIMA)

| Voce | Costo | Note |
|---|---:|---|
| Server (2 vCPU, 4 GB) | 5–8 € al mese | Un VPS europeo qualunque |
| Dati di mercato | 0 € | Sorgenti pubbliche; i dati IBKR in tempo reale costano 5–15 € al mese se servono |
| Dati GEX intraday | 0 € | Non acquistati: la sezione 3 spiega perché |
| Agenti LLM per la ricerca | 0–20 € al mese | Facoltativi: il consiglio funziona anche con i ruoli deterministici |
| Commissioni di trading | 1–2% del capitale l'anno | Già dentro i backtest |
| Commercialista (RW, RT con broker estero) | 300–1.000 € l'anno | Dalla fase 2 |
| Parere legale su delega, donazione, comunicazione | 300–800 €, una volta | Prima della fase 2 |
| Struttura societaria | 0 € | Nessuna fino a 300–500 mila euro |
| **Totale del primo anno** | **circa 700–2.200 €** | Cioè il 6–18% di un capitale di 12.000 euro |

L'ultima riga è il numero più scomodo della tabella: **su 12 mila euro, i costi fissi possono assorbire l'intero rendimento atteso del primo anno**. È un altro motivo per cui a questa scala contano i versamenti e il registro che si costruisce, più del rendimento.

### 9.3 Che cosa può far fallire il piano

- **Le strategie smettono di funzionare** (probabilità non piccola: il Deflated Sharpe è 0,51). Risposta: il paper lo rivela senza perdite; nel reale gli scalini limitano il danno al 20%.
- **L'exchange crypto fallisce.** Risposta: tetto del 40%, sede autorizzata nell'UE, cassa non impegnata fuori dall'exchange.
- **La disciplina cede**: alzare la leva dopo una buona serie, togliere il KILL dopo una cattiva. Risposta: i limiti sono nel codice e nel file di configurazione, il tetto di 3x non è configurabile, e questo documento è scritto per essere riletto in quei momenti.
- **Le regole cambiano** (tassazione delle crypto, perpetual, PRIIPs). Risposta: revisione normativa ogni 6 mesi con il commercialista.

---

---

## Riepilogo di una pagina

**La domanda.** Rifondare GERVA Capital per puntare al 20–30% al mese con 10–12 mila euro, da privato residente in Italia.

**La risposta sui numeri.** Quell'obiettivo richiede uno Sharpe stabile tra 2,3 e 3,5 e una volatilità del conto superiore al 100% l'anno; il miglior fondo documentato ha reso il 4,3% lordo al mese. Tutto ciò che ho potuto provare su dati reali (110 configurazioni, dal 2000 al 2026, con i costi di un conto piccolo) converge su un portafoglio con Sharpe 1,18 nel backtest e 0,86 fuori campione: **circa l'1% al mese senza leva, 1,5–2% con la leva massima difendibile**. Oltre, il rendimento atteso smette di crescere e cresce solo la probabilità di rovina: a 15x due conti su tre vengono dimezzati in tre anni e il mese medio è ancora il 10%.

**Che cosa non funziona** (verificato): il GEX come segnale di direzione; la regola del VWAP; il momentum intraday con costi realistici; l'effetto dell'ultima mezz'ora dopo il 2023; il modello Kronos; il carry sui perpetual ai tassi di oggi; vendere volatilità senza rischio di coda; affidare le operazioni a un LLM.

**Che cosa regge** (simulato, da confermare in paper): trend su Bitcoin ed Ether; momentum tra le 20 crypto più scambiate con un filtro di regime; ritorno alla media di breve su S&P 500 e Nasdaq; trend lento multi-asset come diversificatore. Insieme, a parità di rischio.

**Che cosa ho costruito.**
- `gerva/`: motore di ricerca riproducibile in un comando, strategie definite una volta sola per backtest e live, rischio in tempo reale con scalini a −10%, −15% e KILL a −20%, leva massima 2x con tetto fisico a 3x, ordini che non si possono duplicare, recupero dopo un crash, supervisore, cancelli numerici per il passaggio al reale, consiglio di ricerca in cui gli agenti propongono e il codice decide.
- `dashboard/`: pagina professionale in sola lettura con P&L, esposizione, rischio, strategie, ordini, stato del sistema e pulsante KILL.
- Correzioni al codice esistente: 8 difetti critici o alti con 20 test di regressione.
- Verifiche indipendenti: GEX, VWAP, Kronos, nove progetti open source, quadro legale italiano.

**Che cosa non ho fatto e perché.** Non ho collegato denaro reale: nessun cancello è ancora verde. Non ho verificato l'adattatore Alpaca contro il servizio vero né scritto quello per IBKR nel nuovo motore: servono le tue chiavi e il tuo conto paper. Non ho modellato il rischio di cambio. Non ho corretto i banchi del vecchio `quantlab`, sostituiti dal nuovo motore.

**Il giudizio.** L'evidenza è promettente e non conclusiva: il Deflated Sharpe è 0,51 contro una soglia di 0,95. Il progetto vale la pena per ciò che può dimostrare, un registro reale e verificabile, più che per il rendimento del primo anno, che su 12 mila euro i costi fissi possono assorbire per intero.

**La struttura.** Persona fisica, conto intestato a te, nessuna società. Mai denaro di terzi con un compenso senza una struttura autorizzata.

---

## I primi cinque passi

1. **Oggi: guarda il sistema girare, senza rischi.**
   ```bash
   python -m venv .venv && .venv/bin/pip install -r requirements.txt
   .venv/bin/python -m pytest                      # tutti i test devono essere verdi
   .venv/bin/python -m gerva research              # rifà tutti i backtest: circa 2 minuti dopo il primo scarico dei dati
   .venv/bin/python -m gerva demo                  # fotografia dimostrativa dal backtest (marcata SIMULATO)
   .venv/bin/python -m dashboard.server            # apri http://127.0.0.1:8787
   ```
   Leggi `research/v5/RESULTS.md` dall'inizio alla fine: è il documento da cui dipende ogni altra decisione.

2. **Questa settimana: avvia il paper trading su un server.** Prendi un VPS Linux da pochi euro, copia il repository, avvia `python -m gerva supervise -- run` sotto systemd (`deploy/gerva.service`) o Docker (`deploy/docker-compose.gerva.yml`), configura gli allarmi Telegram. Da quel momento decorrono i 90 giorni del cancello 1. Non usare il portatile.

3. **Entro due settimane: collega il conto paper di Alpaca** (`mode: alpaca-paper` in `config/gerva.yaml`, chiavi nelle variabili d'ambiente, mai nel repository). Prova con `python -m gerva check-broker`, poi fai passare un ordine da 25 dollari e controllalo a mano sul sito di Alpaca. È la verifica che io non ho potuto fare.

4. **Entro un mese: tre telefonate.** (a) A Interactive Brokers: conferma scritta su età minima per il conto a margine, accesso ai CFD su indice e Family Account. (b) A un commercialista che conosca il quadro RW e i broker esteri: preventivo e regime delle crypto al 33%. (c) A un avvocato dei mercati finanziari: donazione o prestito dei genitori, delega, e che cosa puoi pubblicare con il nome "GERVA Capital". La lista delle domande è nella sezione 7.5.

5. **Durante i 90 giorni: i due lavori che chiudono i cancelli rossi.** Scrivi (o fammi scrivere) la replica quotidiana del backtest per misurare scostamento e costi reali (cancelli 7 e 8), e l'adattatore IBKR sul conto paper. Ogni domenica: `python -m gerva gates` e mezz'ora sulla dashboard. Nessun cambiamento alle strategie o ai limiti durante il periodo: se cambi il sistema, il conto dei giorni riparte.

Soltanto con otto cancelli verdi, il parere del legale e il commercialista scelto: 3.000 euro, leva 1x.

---

## Fonti

Legenda: `[V]` pagina aperta e letta in questa sessione; `[S]` visto solo un estratto di ricerca; `[R]` ricordo non verificato. Le pagine ufficiali di Interactive Brokers e di SSRN hanno risposto con errore 403: dove compaiono, il dato viene da fonti secondarie.

**Teoria della leva**
- [K1] J. L. Kelly, "A New Interpretation of Information Rate", Bell System Technical Journal, 1956 `[R]`.
- [K2] E. O. Thorp, "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market", 2006 `[R]`.
- [K3] L. MacLean, E. Thorp, W. Ziemba, "Good and bad properties of the Kelly criterion", 2010. https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf `[V]`

**Strategie**
- [S1] Moskowitz, Ooi, Pedersen, "Time Series Momentum", Journal of Financial Economics, 2012; via https://quantpedia.com/strategies/time-series-momentum-effect/ `[S]`
- [S2] Hurst, Ooi, Pedersen, "A Century of Evidence on Trend-Following Investing", 2017. https://www.TrendFollowing.com/whitepaper/Century_Evidence_Trend_Following.pdf `[S]`
- [S3] Indice SG Trend: https://www.toptradersunplugged.com/trend-following-performance-report-december-2025/ `[V]`; Meketa, "Trend Following Strategies", 2025. https://meketa.com/wp-content/uploads/2025/12/MEKETA_Trend-Following.pdf `[V]`
- [S4] AQR, "You Can't Always Trend When You Want". https://www.aqr.com/Insights/Research/Journal-Article/You-Cant-Always-Trend-When-You-Want `[S]`
- [S6] Bondarenko, studio sull'indice Cboe PutWrite, 2016; via https://www.cxoadvisory.com/equity-options/performance-of-cboe-putwrite-indexes `[S]`
- [S7] McLean, Pontiff, "Does Academic Research Destroy Stock Return Predictability?", Journal of Finance, 2016. https://gwern.net/doc/economics/2016-mclean.pdf `[V]`
- [S9] Schmeling, Schrimpf, Todorov, "Crypto carry", BIS Working Paper 1087, 2023. https://www.bis.org/publ/work1087.htm `[V]`
- [S10] Liu, Tsyvinski, Wu, "Common Risk Factors in Cryptocurrency", Journal of Finance, 2022. https://www.nber.org/papers/w25882.pdf `[S]`
- [S11] Moreira, Muir, "Volatility-Managed Portfolios", Journal of Finance, 2017; Cederburg, O'Doherty, Wang, Yan, 2020. https://www.lehigh.edu/~xuy219/research/COWY.pdf `[S]`
- [S12] Gayed, Bilello, "Leverage for the Long Run", 2016; via https://www.cxoadvisory.com/volatility-effects/leveraging-the-u-s-stock-market-based-on-sma-rules/ `[S]`
- [S20] Aquilina, Budish, O'Neill, "Quantifying the High-Frequency Trading Arms Race", Quarterly Journal of Economics, 2022. https://www.nber.org/system/files/working_papers/w29011/w29011.pdf `[S]`

**Regole e costi**
- [S15] ESMA, misure di intervento sui CFD, 2018. https://www.esma.europa.eu/press-news/esma-news/esma-adopts-final-product-intervention-measures-cfds-and-binary-options `[V]`; dichiarazione ESMA del 24/2/2026 sui perpetual. https://www.dirittobancario.it/wp-content/uploads/2026/02/Dichiarazione-ESMA-24-febbraio-2026-ESMA35-243228190-8024.pdf `[V]`
- [S16] MiFID II, Allegato II. https://www.esma.europa.eu/publications-and-data/interactive-single-rulebook/mifid-ii/annex-ii `[V]`
- [S17] Tassi a margine IBKR (da Lynx). https://www.lynxbroker.com/info/ibkr-margin-rates/ `[V]`; commissioni. https://www.interactivebrokers.ie/en/pricing/commissions-stocks.php `[S]`; PRIIPs. https://www.ibkr.info/node/2993 `[S]`; conti. https://www.interactivebrokers.ie/en/accounts/individual.php `[S]`
- [S18] Sedi UE con perpetual. https://cryptoticker.io/en/crypto-futures-exchanges-eu/ `[V, fonte secondaria]`; commissioni. https://blog.kraken.com/product/pro/new-kraken-pro-fee-tiers , https://bitvavo.com/en/fees `[S]`

**GEX e VWAP**
- [G1] SqueezeMetrics, "Gamma Exposure (GEX)", 2017. https://squeezemetrics.com/monitor/download/pdf/white_paper.pdf `[V]`
- [G2] SqueezeMetrics, "The Implied Order Book", 2020. https://squeezemetrics.com/download/The_Implied_Order_Book.pdf `[V]`
- [G3] Barbon, Buraschi, "Gamma Fragility", 2021. http://www.abarbon.com/assets/Barbon_Buraschi_2021_Gamma_Fragility.pdf `[V]`
- [G4] Baltussen, Da, Lammers, Martens, "Hedging demand and market intraday momentum", Journal of Financial Economics, 2021. https://www3.nd.edu/~zda/intramom.pdf `[V]`
- [G5] Amaya, Garcia-Ares, Pearson, Vasquez, "0DTE Index Options and Market Volatility", 2025. https://cdn.cboe.com/resources/education/research_publications/gammasqueezes.pdf `[V]`
- [G6] Adams, Dim, Eraker e altri, "Do S&P 500 Options Increase Market Volatility? Evidence from 0DTEs", 2026. https://www.jean-sebastienfontaine.com/papers/0dte-options-volatility.pdf `[V]`
- [G6b] Cboe, "0DTEs Decoded", 2025. https://www.cboe.com/insights/posts/0-dt-es-decoded-positioning-trends-and-market-impact `[V]`
- [G7] Glassnode, "Taker-Flow-Based Gamma Exposure", 2025. https://research.glassnode.com/gamma-exposure `[V]`
- [G8] Zarattini, Aziz, "Volume Weighted Average Price (VWAP): The Holy Grail for Day Trading Systems", 2023. https://concretumgroup.com/wp-content/uploads/2026/02/Volume-Weighted-Average-Price.pdf `[V]`
- [G9] Zarattini, Aziz, Barbon, "Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)", 2024–2025. https://alexandria.unisg.ch/server/api/core/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/content `[V]`
- [G10] Discussione su QuantConnect sulla replica del paper VWAP. https://www.quantconnect.com/forum/discussion/16706/bear-bull-traders-039-paper-on-quot-the-holy-grail-quot-not-so-fast/ `[V]`
- [G11] Paz Serpa, valutazione fuori campione, 2026 (SSRN 7290621); via Swedroe. https://larryswedroe.substack.com/p/when-beat-the-market-meets-the-real `[S]`
- [G13] Prezzi dei dati: https://squeezemetrics.com/monitor/plans , https://spotgamma.com/subscribe-to-spotgamma/ , https://menthorq.com/pricing/ , https://orats.com/data-api , https://www.thetadata.net/pricing `[V]`
- Dati GEX usati nei test: https://squeezemetrics.com/monitor/static/DIX.csv (scaricato il 10/11/2026).

**Frequenze di base e termini di paragone**
- [B1] Barber, Lee, Liu, Odean, "The Cross-Section of Speculator Skill: Evidence from Day Trading", 2011/2014. https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trading%20Skill%20110523.pdf `[V]`
- [B2] Chague, De-Losso, Giovannetti, "Day Trading for a Living?". https://econpapers.repec.org/RePEc:fgv:eesptd:525 `[V]`
- [B3] ESMA, decisione sui CFD, 2018. https://www.consob.it/documents/1912911/1970971/esma35_43_1000.pdf/6dc9bc30-c528-09dc-9430-398c8df4c3af `[V]`
- [B4] Finance Magnates su dati FPFX Tech, 2024. https://www.financemagnates.com/forex/exclusive-only-7-of-300000-prop-trading-accounts-achieved-payouts/ `[V]`
- [B5] Cornell, "Medallion Fund: The Ultimate Counterexample?", 2020; via https://www.cxoadvisory.com/investing-expertise/proof-of-superior-investment-expertise/ `[V]`
- [B6] Reuters, rendimenti 2025 dei maggiori hedge fund, 2/1/2026 (ripubblicato). https://www.itiger.com/news/2600609750 `[V]`
- [B7] World Cup Trading Championships, classifiche. https://www.worldcupchampionships.com/world-cup-trading-championship-standings `[V]`

**Progetti open source e agenti LLM**
- Repository: https://github.com/QuantumOrb/QuantOrb , https://github.com/TauricResearch/TradingAgents , https://github.com/Jakeschincariol/day-trader-skill , https://github.com/shiyu-coder/Kronos , https://github.com/virattt/ai-hedge-fund , https://github.com/freqtrade/freqtrade , https://github.com/microsoft/qlib , https://github.com/HKUDS/AI-Trader , https://github.com/hummingbot/hummingbot (tutti `[V]`, visti il 10/11/2026)
- [R10] FINSABER. https://arxiv.org/html/2505.07078v6 `[V]`
- [R11] StockBench. https://arxiv.org/html/2510.02209 `[V]`
- [R12] LiveTradeBench. https://arxiv.org/html/2511.03628 `[V]`
- [R13] Alpha Arena, stagione 1. https://protos.com/llm-crypto-trading-contest-finds-llms-cant-trade-crypto , https://www.gncrypto.news/news/qwen-wins-alpha-arena-season-1-with-22-percent-returns/ `[V, stampa secondaria]`
- [R14] TradingAgents: paper https://arxiv.org/html/2412.20138 `[V]`; replica indipendente https://arxiv.org/html/2605.16895v1 `[V]`
- [R15] Kronos: paper https://arxiv.org/html/2508.02739 `[V]`

**Quadro legale e fiscale italiano**
- [L1] Crypto al 33%: https://www.eutekne.info/Sezioni/Art_1082976_tassazione_al_33_per_le_plusvalenze_su_cripto_attivita_realizzate.aspx , https://blog.moneyviz.it/tasse-crypto-2026-33-confermato-26-solo-per-stablecoin-euro-micar/ `[V]`
- [L2] Tobin tax 2026: https://www.ipsoa.it/documents/quotidiano/2026/01/07/tobin-tax-2026-raddoppiano-aliquote-proporzionali `[V]`
- [L3] Nuovo TUIR: https://taxing.it/nuovo-testo-unico-delle-imposte-sui-redditi-tabella-di-destinazioni/ `[S]`
- [L4] DAC8: https://www.fiscal-focus.it/news-24/ore-19-59-dac8-in-italia-scambio-fiscale-automatico-sulle-cripto-attivita,3,180282 `[S]`
- [L5] Art. 166 TUF: https://www.brocardi.it/testo-unico-intermediazione-finanziaria/parte-v/titolo-i/capo-i/art166.html `[V]`; Cass. 14193/2026: https://www.eutekne.info/Sezioni/Art_1101515_abusivismo_finanziario_solo_con_esercizio_professionale_e_nei.aspx `[V, massima]`; art. 4-terdecies TUF: https://www.brocardi.it/testo-unico-intermediazione-finanziaria/parte-i/art4terdecies.html `[V]`
- [L6] ESMA, nota di vigilanza sul copy trading, 2023. https://www.esma.europa.eu/sites/default/files/2023-03/ESMA35-42-1428_Supervisory_Briefing_on_Copy_Trading.pdf `[S]`
- Donazioni: https://www.ecnews.it/fiscale/fisco-e-patrimonio/patrimonio-e-trust/liberalita-indirette-il-caso-del-bonifico-bancario/ `[S]`; MiCA in Italia: https://www.consob.it/web/area-pubblica/w/comunicato-stampa-congiunto-consob-banca-d-italia-del-30-giugno-2026 `[V]`

**Dati usati nei backtest:** Yahoo Finance (azioni ed ETF, giornalieri e orari); archivio pubblico data.binance.vision (crypto e funding); SqueezeMetrics (GEX); histdata.com via un archivio pubblico su GitHub (S&P 500 a 1 minuto, 2010–2018); dataset pubblico su Hugging Face (25 azioni a 1 minuto, 2022–2024). Le impronte dei file sono in testa a `research/v5/RESULTS.md`.
