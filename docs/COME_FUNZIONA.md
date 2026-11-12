# GERVA Capital: come funziona, e perché è meglio della versione precedente

Tutti i rendimenti citati qui sono **simulati** su dati storici. Il fondo non ha ancora un giorno di operatività reale.

## In una frase

Un programma che ogni giorno decide quanto tenere in Bitcoin, Ether, altre crypto, indici azionari ed ETF, seguendo quattro regole fisse; un gruppo di agenti AI può solo frenarlo; un motore di rischio può fermarlo del tutto; tu intervieni soltanto per riaccenderlo o cambiare un limite.

## Il giro di una giornata

```
ogni 15 minuti
 1. DATI          prezzi di chiusura di crypto (Binance) e di azioni ed ETF (Yahoo; IBKR quando sarà collegato)
 2. STRATEGIE     quattro regole calcolano quanto vorrebbero avere di ogni strumento
 3. QUOTE         il capitale si divide tra le quattro in modo che ciascuna porti lo stesso rischio
 4. LEVA          l'esposizione totale si regola per tenere la volatilità al 15% l'anno, mai oltre 2x
 5. AGENTI AI     ogni 6 ore leggono notizie, banche centrali, regolatori: possono ridurre o vietare, mai aumentare
 6. RISCHIO       controlla perdite, limiti, età dei dati: può dimezzare, ridurre a un quarto, o chiudere tutto
 7. ORDINI        solo la differenza tra ciò che si ha e ciò che si vuole; ogni ordine è registrato prima di partire
 8. FOTOGRAFIA    un file che la dashboard legge: è tutto ciò che vedi
```

## Le quattro strategie

| Nome | In parole semplici | Per chi vuole i dettagli |
|---|---|---|
| **CR-TREND** | Tiene Bitcoin ed Ether quando salgono da settimane, esce quando scendono | Media dei segni del rendimento a 30, 60, 120 giorni; peso inverso alla volatilità; ricalcolo settimanale. Sharpe 0,99 |
| **CR-XSMOM** | Tra le 20 crypto più scambiate compra le 5 più forti, ma solo se Bitcoin è in salute | Momentum a 14, 28, 56 giorni; filtro: BTC sopra la media a 100 giorni; volatilità obiettivo 25%. Sharpe 1,04 |
| **EQ-MR** | Compra S&P 500 e Nasdaq dopo una giornata chiusa sui minimi, rivende al rimbalzo | IBS < 0,2 per entrare, > 0,7 per uscire; in posizione il 30% del tempo; va eseguita in chiusura. Sharpe 0,73 |
| **MA-TREND** | Segue le tendenze lente di azioni, obbligazioni, oro, materie prime | Trend a 3, 6, 12 mesi su 17 ETF, solo long, senza leva. Sharpe 0,16–0,46: è un diversificatore |

Insieme, senza leva: 13,8% l'anno, volatilità 9,0%, caduta massima −9,4%, Sharpe 1,18 (0,86 nel periodo mai usato per scegliere). La ricerca v4 aggiunge due strategie non ancora nel motore (acquisto dei crolli a 24 ore, carry su Hyperliquid): Sharpe 1,34, stessa resa, meno volatilità.

## Le tre difese

1. **Agenti AI.** Scout, analista e scettico leggono le fonti che il codice ha raccolto. Per frenare una strategia devono concordare in due e citare una fonte che esiste davvero. Non possono aumentare nulla né fornire numeri.
2. **Motore di rischio.** A −10% dal massimo dimezza l'esposizione; a −15% la porta a un quarto; a −20% chiude tutto e resta fermo finché non lo riaccendi tu. Lo stesso per perdite del 4% in un giorno o dell'8% in una settimana, dati vecchi, ordini dall'esito ignoto.
3. **Supervisore.** Se il programma si blocca lo riavvia; se cade dieci volte in un'ora si ferma e ti avvisa.

## Leva: due numeri diversi

- **Sul libro giornaliero:** al massimo 2x, con un tetto di 3x scritto nel codice.
- **Sul singolo trade, a margine isolato:** circa 11x, mai oltre 15x. La leva discende da quanto è stretto lo stop; ciò che puoi perdere su un trade è il margine, circa 1,7 volte il rischio dichiarato (1% o 2% del patrimonio). I livelli a 30x e 50x sono ritirati: sui prezzi veri dei perpetual non reggono.

## Che cosa aspettarsi

Simulato, tre anni, rendimento mensile composto:

| Profilo | Scenario base | Scenario centrale | Caduta tipica (dati mensili) |
|---|---:|---:|---:|
| Libro giornaliero 2x | 2,1% | 1,1% | −7% |
| Prudente: libro 1x + trade a 0,5% / 1% | 2,1% | 1,1% | −9% |
| Massimo: libro 2x + trade a 1% / 2% | 3,9% | 1,8% | −18% |

Le cadute sui dati giornalieri sono più profonde di circa metà. Dopo le tasse i rendimenti scendono di circa un quarto. Il 30% al mese non è sostenuto da nessuna delle 4.071 varianti provate. Dettaglio in [`RIFONDAZIONE.md`](RIFONDAZIONE.md), sezioni 11 e 12.

## Perché è meglio della versione su GitHub

La versione precedente (ramo principale del repository, fino alla v3.9) era una società simulata di 28 agenti attorno a un motore esterno, GERVA-Q. Aveva idee buone, che ho tenuto: gli LLM non generano segnali, un registro unico delle prove, un audit a catena di hash. Il confronto, punto per punto:

| | Versione precedente | Versione attuale |
|---|---|---|
| **Rendimento simulato, con le stesse convenzioni** | 20,3% l'anno, Sharpe 0,96, caduta −17,7% senza leva; 33,5% e −36,5% con la leva al 150% | Libro a 2x: 27,7% l'anno, Sharpe 1,47, caduta −17,9%; profilo massimo: 55,0% e −31,0% |
| **Come è misurato lo Sharpe** | Sui rendimenti grezzi: la cassa che rende il tasso contava come abilità. In eccesso del tasso la "v4 approvata" non superava il suo stesso cancello | Sempre in eccesso del tasso a breve |
| **Costi** | 8 punti base fissi; nessun costo della leva, nessun prestito titoli | Per sede (30 pb crypto, 5–10 pb indici ed ETF), finanziamento della leva, costi raddoppiati come prova |
| **Quando si esegue** | Sulla stessa chiusura del segnale, mentre la documentazione diceva "il giorno dopo" | Ritardo esplicito; ogni strategia provata anche con un giorno in più |
| **Verifica fuori campione** | Finestra mobile, riusata a ogni lancio | Periodo dal 2023 mai usato per scegliere; walk-forward misurato |
| **Prove contate** | 64–71, mescolando classi diverse | Circa 150, con il Deflated Sharpe pubblicato anche se è sotto soglia |
| **Dove passa un ordine** | Quattro strade diverse verso il broker, ognuna con regole sue | Una sola, con un solo motore di rischio |
| **KILL** | Scriveva un file; non chiudeva nulla e tre strade su quattro non lo guardavano | Chiude tutto, resta fermo, si riaccende solo a mano |
| **Limite di leva** | Tre agenti potevano votare 3x lo stesso giorno; nel banco simulato fino a 25x scelti da un LLM | 2x operativo, 3x nel codice; nessun agente può toccarlo |
| **Stop automatico** | Al −35%, oltre la caduta massima del backtest: non scattava mai | Scalini a −10%, −15%, −20% |
| **Ordini duplicati** | Possibili dopo un errore di rete | Impossibili: un ordine per simbolo e giorno, registrato prima dell'invio |
| **Un errore nel giro** | Fermava tutto il giro, compresi gli stop | Ogni passo fallisce da solo; il giro dopo riparte |
| **Backtest e reale** | Codice diverso (il motore reale stava fuori dal repository) | Le stesse funzioni, con un test che lo dimostra |
| **Ruolo dell'AI** | Agenti con accesso diretto al broker nel "banco libero"; segnali Telegram eseguibili | Agenti che possono solo frenare, con fonti verificate dal codice |
| **Dove gira** | Un Mac tenuto sveglio | Un server, con supervisore e riavvio automatico |
| **Interfaccia** | Ufficio in pixel art | Console con P&L, rischio, strategie, ricerca, AI, in due livelli di lettura |
| **Test** | 290 | 418, di cui 20 riproducono i difetti trovati nell'audit |

In una riga: la versione precedente era costruita per sembrare una società; questa è costruita per non perdere denaro per un errore, e per dire la verità sui propri numeri. Il rendimento simulato è più alto, ma la differenza che conta è un'altra: ogni numero qui si può rifare con un comando (`python -m gerva research`) e ogni limite è scritto in un posto solo.

## Che cosa non è ancora dimostrato

- Nessun giorno di paper trading: i cancelli per il denaro reale sono tutti da superare.
- Il valore degli agenti AI: si misura solo in avanti, con due libri paper in parallelo, ancora da costruire.
- L'adattatore per Interactive Brokers nel nuovo motore manca; quello per Alpaca è provato solo contro un servizio finto.
- Conviction e leva del singolo trade sono moduli pronti e testati, non ancora collegati al ciclo.
- La liquidità ferma non è ancora remunerata nel codice.
