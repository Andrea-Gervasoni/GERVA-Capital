# Dashboard di GERVA Capital

Console web del fondo: patrimonio e P&L, esposizione, rischio, strategie, ordini, salute del sistema.
Legge **un solo file JSON** scritto dal motore (`gerva.live.snapshot`) e non tocca né il database né il broker.
L'unica cosa che può fare, oltre a leggere, è creare il file KILL.

HTML, CSS e moduli JavaScript scritti a mano: nessun CDN, nessuna build, nessun `npm`.

## Avvio

```bash
python -m dashboard.server            # http://127.0.0.1:8787
# oppure
uvicorn dashboard.server:app --port 8787
```

Senza snapshot la pagina mostra l'esempio `static/sample_snapshot.json`, marcato **DEMO: dati di esempio**.
Per vederla piena con il backtest vero:

```bash
python -c "from gerva.live import snapshot as s; s.write('var/gerva/snapshot.json', s.demo('research/v5/series.parquet'))"
```

Test: `python -m pytest tests/test_dashboard.py -q`

## Spazi, livelli e sistema visivo (v7)

Il progetto di riferimento è in `design/` (`design_1_sistema_visivo.md`, `design_2_grafici.md`, `design_3_architettura_interazione.md`).

**Sette spazi in due gruppi.** Ogni giorno: **Oggi**, **Mercati**, **Portafoglio**, **Rischio**. Quando serve: **Evidenza**,
**Apprendimento**, **Sistema**. Indirizzi `#/spazio/scheda?s=BTC`. Oggi, Rischio e Mercati sono nuovi; gli altri spazi ospitano
per ora le pagine precedenti come schede, e i vecchi indirizzi (`#/panoramica`, `#/ordini`, …) continuano a funzionare.

| Spazio | Che cosa c'è |
|---|---|
| Oggi | Patrimonio (cifra che rotola, σ della giornata, i due libri), quanto manca ai freni, cascata «da dove viene il risultato», che cosa è cambiato in 24 ore, trade a leva aperti con il righello, atteso contro reale (cono del profilo del paper), confronto con l'originale, strada verso il denaro reale. |
| Rischio | Stato e scala dei freni (una sola, orizzontale: caduta, 24 ore, 7 giorni, peggior caso di oggi), tabella delle distanze, il peggio di oggi, tetti di esposizione, leva e volatilità, stress sulle quattro giornate storiche applicate alle posizioni di oggi, dati e ordini, avvisi, rimando al KILL, statistiche. |
| Mercati | Elenco degli strumenti, grafico a candele (vuota su, piena giù) con volume, medie, VWAP, conviction, GQ in ombra, ATR, RSI e il righello del trade (lastra 1 R, livelli con cartellino), libro dei trade (Aperti, Chiusi, Decisioni). Selezione collegata tra i riquadri. |

**Tre livelli di lettura**, nella capsula in alto (sul telefono nel foglio «Altro»): Semplice (frasi, «Come si legge»), Esperto
(colonne, note, tabelle), Terminale (binario a icone, riquadri più vicini, nessuna sequenza d'ingresso; sotto gli 860 px ricade su
Esperto e lo dice). Il livello è una preferenza del browser (`l` lo cambia).

**Fascia di stato** nella capsula che galleggia: provenienza e modalità (ESEMPIO / SIMULATO / PAPER / REALE, distinte anche dalla
forma del bordo), stato del rischio con scala e motivo, età dei dati (il punto respira solo se sono freschi), sistema se non è
tutto a posto, avvisi con contatore, livello, tema, **KILL**. Con dati fermi o offline lo stato diventa **Sconosciuto** e riporta
l'ultimo visto: mai l'ultimo «sicuro». Stati critici aggiungono una riga con «Prendi in carico» (resta nel browser).

**KILL.** Il pulsante nella capsula dice se è pronto, spento o già attivo e apre soltanto la finestra: anteprima degli effetti
(posizioni, controvalore, trade a leva aperti), token, motivo, parola KILL. Il fuoco parte da «Annulla», Invio nel campo del token
non invia, Esc chiude e svuota. È l'unica scrittura della dashboard.

**Tastiera.** `/` o `Ctrl K` tavolozza (strumenti, spazi, glossario, azioni: nessuna voce scrive) · `g` poi `o m p r e a s` spazi ·
`g t` libro dei trade · `g b` ordini · `l` livello · `i` «In una frase» · `a` avvisi · `?` scorciatoie · `Maiusc K` finestra del KILL ·
in Mercati `j k` strumento, `1…5` intervalli, `[ ]` trade · sui grafici frecce, `+ − 0`, Inizio/Fine. Ordine del fuoco: fascia di
stato → binario → contenuto.

**Sistema visivo.** `css/tokens.css` contiene per intero `design/tokens.glass.css` (stessi nomi di prima: scuro predefinito, chiaro
solo a scelta dell'utente) più i ruoli `--chart-*` del linguaggio dei grafici. `css/glass.css` applica materiali (pannello,
rialzato, cromatura con smusso, foglio), fondale a sei luci che derivano a passi, comandi lucidi, segmentati con cursore che cambia
posto e larghezza, ingressi da sfocato a nitido. I valori dinamici (cursore, indice d'ingresso, parallasse, rotolo delle cifre)
sono proprietà personalizzate impostate via CSSOM: la CSP resta senza stili in linea.

**Ripieghi.** `prefers-reduced-motion`: restano solo le dissolvenze. `prefers-reduced-transparency` e browser senza
`backdrop-filter`: superfici piene. **Vetro leggero**: all'avvio la pagina misura il costo di un fotogramma; oltre 34 ms i pannelli
diventano pieni (capsula e binario restano di vetro). Si sceglie anche a mano dalla tavolozza («Vetro pieno o leggero»); la scelta
resta nel browser (`gerva.dash.glass`).

**Grafici.** Il tratto dice la provenienza: puntinato ESEMPIO, tratteggiato SIMULATO, pieno PAPER e REALE; soglie e mirino sono
pieni. Le mappe di calore usano la rampa blu ↔ arancio a nove passi con il numero in ogni cella; verde e rosso solo con segno e forma.
Soglie e tetti arrivano sempre dalla fotografia (`risk.dd_ladder`, `risk.limits`): se mancano si legge «soglia non letta».

## Una sola verità (giro 2, blocco A)

- **`static/js/derive.js`**: ogni grandezza derivata si calcola qui una volta e gli spazi la riusano — patrimonio totale
  (libro giornaliero + contributo dei trade, `equity − start_equity` del libro: stesso capitale), σ della giornata sulla
  volatilità **obiettivo**, scalini e scalino **successivo** con la condizione di rientro, finestre mobili a 24 ore e 7 giorni
  dalla curva (mai lo 0,00% di `min(pnl, 0)`; senza storico: «non calcolabile con i dati presenti»), stress con **copertura**
  (uno shock che manca è «non coperto», mai zero), peggior caso di oggi (un solo calcolo: «almeno −x%» se la copertura è
  parziale o manca il libro), età di un trade contata fino alla data del libro, freschezza per fonte, nomi dei livelli di
  conviction (bassa / media / alta; trade confermato / eccezionale) e GQ. I test le eseguono con Node.
- **Regole dal motore**: `/api/v1/health` porta `rules` (durata massima dei trade, soglie dei livelli, età massime dei dati),
  lette da `gerva/*` e da `config/gerva.yaml`. Se mancano la pagina scrive «n.d.», non un valore predefinito.
- **Freschezza per fonte**: libro dei trade e barre hanno la loro data; oltre l'età massima il riquadro lo dichiara
  («Dati non attuali», R attenuato) anche se la fotografia è di adesso; un trade oltre la durata massima è un'anomalia.
- **Esempi**: `python dashboard/tools/build_samples.py` rigenera fotografia, barre, libro dei trade e confronto come un solo
  insieme (stesso giorno, un prezzo per strumento, un patrimonio, trade costruiti sulle barre con R × rischio = P&L, cancelli
  di `gerva/live/gates.py`). In modalità demo il server li sposta tutti insieme alla data di oggi.

## Due livelli di lettura (pagine precedenti)

In alto c'è un interruttore **Semplice / Esperto** (ricordato nel browser, parte da Semplice).

- **Semplice**: una riga «In una frase» in cima a ogni pagina, generata dai dati; sotto ogni cifra una spiegazione
  in italiano corrente; «Che cosa significa?» accanto al titolo di ogni grafico; gli stati detti come un semaforo.
- **Esperto**: le spiegazioni spariscono e compaiono colonne in più, errori standard, note di metodo e grafici
  aggiuntivi (rendimenti giornalieri e mensili, schemi di leva a livelli, walk-forward, quintili di GEX).

Il **Glossario** (pulsante in alto) si apre anche toccando un termine sottolineato a puntini.

## Pagine

Panoramica, Performance, Esposizione, Rischio, Strategie, Ordini, Sistema, e in più:

- **AI** — regime di mercato, conviction di oggi con le soglie, overlay in vigore (moltiplicatori, motivi, fonti,
  scadenza). Legge il blocco `ai` dello snapshot; se manca lo dice.
- **Apprendimento** — il ciclo di automiglioramento (`python -m gerva learn`): il percorso memoria → valutazione →
  ipotesi → validazione → ombra → approvazione → attiva, come stanno andando i trade (tutti e solo paper), dove
  perdono, le regole provate con i sei controlli, quelle in ombra e quelle attive. **La pagina è di sola lettura**:
  mostra il comando `python -m gerva learn --approve <id> --confirm` ma non ha alcun pulsante che attivi una regola.
- **Ricerca** — tutto ciò che viene da `research/v5/quant.json`: tabella della leva nei tre scenari, ventaglio a tre
  anni, rischio di rovina per leva, scenari, correlazioni, curve delle strategie con il confine scelta/verifica,
  quote nel tempo, Sharpe mobile, drawdown, istogramma, conviction, robustezza, significatività, idee scartate.
  Ogni scheda porta l'etichetta **SIMULATO: ricerca su dati storici**.
- **Come funziona** — il percorso dai dati al broker come diagramma cliccabile, e le quattro strategie spiegate.

- **Leva per trade** — da `research/v5/quant_v4.json`: stop, leva e R medio per operazione (righe «sostenuta» fino a 30x,
  «non sostenuta» a 50x), schemi di rischio per trade nei quattro scenari, e che cosa succede se lo stop non viene eseguito.

Con `quant_v4.json` la pagina Ricerca si apre con «Il fondo intero» (curve, portafogli A…C6 con mese medio e mediano,
Monte Carlo, scomposizione del rendimento, strategie provate) e Come funziona mostra la tabella delle sedi.
Il contributo dell'AI non è mai mostrato come numero: «da misurare in paper».

In fondo a Rischio c'è l'esempio «leva del trade e leva del conto» con i tetti di legge.

## Variabili d'ambiente

| Variabile | Predefinito | A che cosa serve |
|---|---|---|
| `GERVA_SNAPSHOT` | `var/gerva/snapshot.json` | Lo snapshot da servire. Se il file non esiste si serve l'esempio DEMO; se esiste ma è illeggibile la risposta è 503 (mai l'esempio al posto di dati veri). |
| `GERVA_QUANT` | `research/v5/quant.json` | I risultati della ricerca (statici, simulati). Se manca, `/api/v1/quant` risponde 404 e le pagine lo dicono. |
| `GERVA_QUANT4` | `research/v5/quant_v4.json` | La quarta tornata di ricerca. Stesse regole di `GERVA_QUANT`, endpoint `/api/v1/quant4`. |
| `GERVA_LEARN` | `$GERVA_HOME/learn/report.json` (senza `GERVA_HOME`: `var/gerva/learn/report.json`) | Il rapporto del ciclo di automiglioramento. Se manca: 404; in modalità demo (nessuno snapshot) si serve `static/sample_learn.json`, marcato come esempio. |
| `GERVA_HOME` | `var/gerva` | La cartella del motore: da qui si leggono `tradebook.json`, `confronto_nav.csv`, `learn/trades.jsonl`. |
| `GERVA_CACHE` | `data_cache` | La cache dei prezzi giornalieri (`bn_spot_1d_<SIM>USDT.parquet`, `yahoo_1d_<SIM>.parquet`) per `/api/v1/market/*`. |
| `GERVA_TRADES_HIST` | `research/v5/v6/trade_storici.parquet` | Lo storico dei trade simulati per `/api/v1/trades/history`. |
| `GERVA_KILL_FILE` | `var/gerva/KILL` | Il file che il comando KILL crea. |
| `GERVA_DASH_TOKEN` | *(non impostato)* | Token richiesto dal KILL. Senza, il KILL è spento (503). |
| `GERVA_DASH_HOST` | `127.0.0.1` | Indirizzo di ascolto. |
| `GERVA_DASH_PORT` | `8787` | Porta. |
| `GERVA_DASH_ALLOWED_HOSTS` | *(vuoto)* | Altri nomi ammessi nell'header `Host`, separati da virgola (es. dietro un tunnel o un proxy). `localhost` e `127.0.0.1` sono sempre ammessi; gli altri ricevono 400. |
| `GERVA_DASH_ACCESS_LOG` | *(spento)* | `1` per registrare ogni richiesta (la pagina ne fa una ogni 5 secondi). |

I percorsi predefiniti sono relativi alla radice del repository; quelli passati per variabile valgono così come sono.

## API

| Metodo | Percorso | Risposta |
|---|---|---|
| GET | `/api/v1/snapshot` | Lo snapshot così com'è (NaN e infinito diventano `null`). Header `X-Gerva-Snapshot-Source: file` oppure `demo`. |
| GET | `/api/v1/health` | `{"ok": true, "snapshot_age_s": …, "snapshot_source": …, "kill_enabled": …, "kill_active": …}` |
| GET | `/api/v1/quant` | Il file della ricerca così com'è (NaN → `null`); 404 se manca, 503 se illeggibile. Header `X-Gerva-Quant-Age`. |
| GET | `/api/v1/quant4` | Come `/quant`, per `quant_v4.json`. |
| GET | `/api/v1/learn` | Il rapporto di `gerva learn`, stesse regole di `/quant`. Sola lettura: l'unica scrittura della dashboard resta il KILL. |
| GET | `/api/v1/market/symbols` | `{"source", "symbols": [{"symbol", "kind": crypto \| etf \| indice}]}`: gli strumenti presenti nella cache dei prezzi. |
| GET | `/api/v1/market/ohlc?symbol=BTC&tf=1d&limit=1500` | Barre giornaliere a colonne: `t[], o[], h[], l[], c[], v[]` più `conviction[]`, `gq[]` e `thresholds`, calcolati dalle funzioni del fondo (`gerva.ensemble`, `gerva.gervasoni`) su tutta la storia. Il simbolo deve passare una lista bianca (`^\^?[A-Z0-9]{1,10}(-[A-Z]{3})?$`) e risolversi in un file dentro la cache: altrimenti 400 / 404. `tf` diverso da `1d`: 400. `limit` tra 10 e 5.000. Risposte tenute in memoria 5 minuti. |
| GET | `/api/v1/tradebook` | Lo stato del libro dei trade a margine isolato (`$GERVA_HOME/tradebook.json`) così com'è: aperti, chiusi (compreso il motivo, per esempio «arresto di emergenza»), registro, indicatore in ombra. |
| GET | `/api/v1/trades/history` | `{"label", "n_sim", "n_paper", "rows": […]}`: i trade simulati (`source: "sim"`) e quelli chiusi in paper (`source: "paper"`, da `learn/trades.jsonl`), solo i campi utili ai grafici. |
| GET | `/api/v1/compare` | `{"rows": […]}`: il confronto giornaliero con il conto originale (`$GERVA_HOME/confronto_nav.csv`), numeri già convertiti. |
| POST | `/api/v1/kill` | Crea il file KILL. Vedi sotto. |

Gli endpoint di mercato, libro, storico e confronto sono di sola lettura e seguono le regole degli altri: limite di
dimensione, NaN → `null`, 404 in JSON se la fonte manca, 503 se è illeggibile. In modalità demo (nessuno snapshot) una
fonte assente è sostituita dall'esempio in dotazione (`static/sample_ohlc.json`, `sample_tradebook.json`,
`sample_trades.json`, `sample_compare.json`), sempre marcato `"example": true` e con un'etichetta che comincia per ESEMPIO.

Ogni risposta porta le intestazioni di sicurezza (CSP `default-src 'self'` senza script né stili inline,
`X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors 'none'`). Nessuna risposta contiene token,
variabili d'ambiente o percorsi del disco.

## Contratto dei dati

Tutte le percentuali sono frazioni (`0.012` = 1,2%); gli istanti sono ISO-8601 in UTC.
**Ogni campo può mancare o essere `null`**: la pagina mostra «—» o uno stato vuoto, non si rompe.

```
meta            fund, mode (paper | live | backtest), as_of, base_ccy, version, data_label, stale_after_s
nav             equity, cash, start_equity, high_water, pnl_day, pnl_day_pct, pnl_mtd_pct, pnl_ytd_pct,
                pnl_total_pct, drawdown_pct, max_drawdown_pct
equity_curve    [{t, equity, benchmark}]
monthly_returns [{ym, ret}]
performance     cagr, vol, sharpe, sortino, calmar, hit_rate_days, best_month, worst_month, psr, days
exposure        gross, net, leverage, max_leverage, by_asset_class[{name, gross, net}], by_venue[…]
positions       [{symbol, venue, strategy, qty, price, value, weight, pnl_day, pnl_open}]
risk            state (NORMAL | REDUCED | HALTED | KILLED), state_reason, var_95_1d_pct, es_95_1d_pct,
                vol_target, vol_realized_30d, limits[{name, value, limit, unit, status}], dd_ladder[{level, action, hit}]
strategies      [{id, name, status, allocation, exposure, pnl_day_pct, pnl_mtd_pct, pnl_total_pct,
                  sharpe_live, sharpe_backtest, max_dd, last_signal, spark[]}]
orders          [{t, symbol, side, qty, price, status, strategy, venue, reason}]
system          heartbeat_age_s, uptime_s, restarts_24h, errors_24h, components[{name, status, latency_ms, last_ok, detail}]
alerts          [{t, level, msg}]
gates           [{name, value, target, unit, ok}]
ai              overlay{valido, nota, globale, motivo_globale, scade, strategie[{id, mult, motivo, fonti[]}]},
                regime{stato (calmo | normale | teso | crisi), punteggio, scala_esposizione}, conviction[{asset, score, livello}]
```

Lo snapshot si legge ogni 5 secondi, la ricerca al caricamento e poi ogni 10 minuti; sotto il titolo di ogni pagina
c'è l'età di entrambe le fonti. I grafici si aggiornano sul posto: intervallo scelto e mirino restano dove sono.

Come la pagina legge i punti che il contratto lascia aperti:

- **`meta.data_label` e `meta.mode`** stanno sempre nella fascia in alto: ambra tratteggiata per backtest e DEMO,
  blu per paper, a colori invertiti per il reale. Un risultato simulato non può essere scambiato per uno vero.
- **Dati fermi.** L'età si calcola da `meta.as_of` (corretta con l'orologio del server). Oltre `stale_after_s`
  (120 s se manca), o senza `as_of`, compare l'avviso «Dati non aggiornati» e i numeri vengono attenuati; se la
  richiesta fallisce compare «Offline». In modalità `backtest` lo snapshot è statico per natura: si mostra l'età,
  non l'allarme.
- **Esposizione.** `gross`/`net` sono letti come frazioni del patrimonio (così li scrive il motore). Se arrivassero
  importi, lo si riconosce dal confronto con `leverage × equity` e si convertono.
- **Limiti e scalini di perdita** hanno valore e soglia negativi: l'utilizzo è `|valore| / |soglia|`.
  VaR ed ES si mostrano in valore assoluto.
- **Benchmark.** Nel grafico è riportato al valore del fondo nel primo giorno dell'intervallo scelto: un solo asse.
- **Cancelli (`gates`).** Vale `ok`; la barra di avanzamento compare solo quando `valore / soglia` ha senso.
- **Esempio DEMO.** Il server ne aggiorna `as_of` e sposta gli orari di avvisi e ordini, così non risulta «fermo».

## Il comando KILL

Nella sezione **Rischio**, in un riquadro separato. Il pulsante apre una finestra che chiede:

1. il **token** (`GERVA_DASH_TOKEN`), digitato a mano. Resta solo in memoria per il tempo della richiesta:
   non va in `localStorage`, cookie o URL, e il campo si svuota all'invio e alla chiusura;
2. un motivo, facoltativo;
3. la parola **KILL** scritta per esteso. Finché non c'è, l'invio è disabilitato.

La pagina manda `POST /api/v1/kill` con l'header `X-Gerva-Token` e `{"reason": "…"}`. Il server:

- risponde **503** se `GERVA_DASH_TOKEN` non è impostato, **401** senza token, **403** con un token sbagliato
  (confronto a tempo costante) o se la richiesta arriva da un'altra origine;
- con il token giusto crea il file in modo atomico (`<ora UTC> dashboard: <motivo>`), senza sovrascriverlo
  se esiste già, e risponde `{"ok": true, "created": …, "already_active": …, "t": …}`;
- **non cancella mai il file**: per ripartire va tolto a mano sul server e va dato `gerva reset-kill`.

Se la richiesta non arriva, la finestra lo dice in chiaro («Il KILL NON è stato attivato»).

## Com'è fatta

```
server.py                 FastAPI: snapshot, health, kill, controllo dell'Host, intestazioni di sicurezza
static/index.html         cornice della pagina, icone, finestra del KILL
static/css/tokens.css     ogni colore, carattere e misura (tema scuro e chiaro)
static/css/app.css        stile
static/js/main.js         instradamento per hash (#/panoramica, #/rischio…), tema, stato della connessione
static/js/store.js        interrogazione ogni 5 s, dati fermi / offline
static/js/model.js        lettura tollerante dello snapshot (funzioni pure)
static/js/charts.js       grafici SVG: linee con mirino, drawdown, heatmap, barre, sparkline, barre di limite, istogramma
static/js/chart-engine.js caduta dal massimo, ventaglio, aree impilate, cascata, dispersione/bolle, mappa ad albero, griglia di calore
static/js/candles.js      candele su canvas con volume, sovrapposizioni e pannelli (ATR%, RSI, conviction, GQ)
static/js/indicators.js   SMA, EMA, Bollinger, VWAP ancorato al mese, Donchian, ATR%, RSI
static/js/chart-theme.js  l'unico oggetto di stile dei grafici, letto dai token CSS --chart-*
static/js/market.js       letture di prezzi, libro dei trade, storico, confronto (cache di 5 minuti nel browser)
static/grafici.html       galleria tecnica: ogni primitiva con i dati di esempio (non è una pagina del prodotto)
static/js/glossary.js     definizioni e termini cliccabili
static/js/flow.js         diagramma di flusso cliccabile (Come funziona, Apprendimento)
static/js/views/          oggi.js, rischio2.js, mercati.js (spazi nuovi) e le dodici pagine precedenti
static/js/panels.js       riquadri degli spazi nuovi: scheda, provenienza, scala dei freni, righello del trade, rotolo, tetti
static/js/cmd.js          tavolozza e scorciatoie
static/css/glass.css      guscio «vetro liquido»: fondale, materiali, cromature, comandi, coreografia, ripieghi
static/sample_snapshot.json   esempio DEMO, coerente al centesimo (lo verifica il test)
```

Tema scuro di base, chiaro se lo chiede il sistema o l'utente (pulsante in alto a destra, ricordato nel browser).
Verde e rosso compaiono solo sul P&L, sempre insieme a segno e freccia; ambra e rosso di stato solo sulle anomalie,
sempre con icona e parola. Le cifre sono tabellari. I grafici si leggono anche da tastiera (frecce) e in tabella.

## Il motore dei grafici

Nessuna libreria: SVG e HTML scritti a mano, canvas solo per le candele. La logica (geometria, scale, ricerca del punto
più vicino, zoom, tastiera, tabella alternativa) è separata dallo stile: **ogni colore, raggio, spessore, tratteggio,
carattere, opacità e tempo è un token `--chart-*`** definito una volta in `css/tokens.css` (oggi alias dei token del tema).
Le regole SVG in `css/app.css` usano quei token; ciò che il canvas e gli attributi SVG vogliono come numeri arriva da
`chartTheme()` (`js/chart-theme.js`), che rilegge i token al cambio di tema, di livello o di preferenza di movimento.
Per ridisegnare i grafici si cambiano i token, non il codice. `grafici.html` li mostra tutti insieme.

| Primitiva | Firma | Note |
|---|---|---|
| Linee nel tempo | `timeChart(host, { label, zoom, table }) → { update(spec), empty, onHover, setHoverTime, setWindow, resetWindow, onWindow, window }` | `spec = { x, panels: [{ height, title, scale, series: [{ values, cls, area, end, dots, step, name }], format, top, bottom, refs, bands }], marks, xTicks, tip, say, xFormat, xHead }`. `zoom: true`: rotella, trascinamento, doppio clic, `+ − 0`. |
| Candele | `candleChart(host, { label, panes, overlays, table }) → { setData, setOverlays, setPanes, setLog, setRange, redraw, view, onHover, setHoverTime, setWindow, resetWindow, onWindow, destroy }` | Volume sempre; pannelli `atr`, `rsi`, `conv`, `gq`; sovrapposizioni in `OVERLAYS`; segni delle operazioni in `data.markers`. |
| Caduta dal massimo | `underwater(host, opts).update({ x, equity \| values, refs, height, format, title })` | Restituisce `{ min, minIndex, current, daysUnder }`. |
| Ventaglio | `fanChart(host, opts).update({ x, bands: [{ lo, hi, name }], median, lines, scale, format, refs, marks, xTicks, xFormat, xHead })` | Fasce dalla più larga alla più stretta. |
| Aree impilate | `stackedArea(host, opts).update({ x, layers: [{ name, values, cls }], normalize, format, height, title })` | `normalize: true` = 100%. |
| Istogramma | `histogram(host, { edges, counts }, { refs: [{ value, label, cls }], normal, unit, xFormat, rangeFormat, height, log, table })` | Linee verticali di riferimento; curva normale facoltativa. |
| Cascata | `waterfall(host, steps: [{ label, value, total, note }], { label, height, format, levelFormat, orient, valueHead, levelHead, table }) → { update }` | In riga quando le colonne sono troppo strette. |
| Dispersione / bolle | `scatter(host, points: [{ x, y, size, group, label, cls }], { groups, fit, diagonal, refsX, refsY, xScale, yScale, showLabels, tip, table, … }) → { update, setHidden, fit }` | Punto più vicino al puntatore; frecce da tastiera; legenda con interruttori. |
| Mappa ad albero | `treemap(host, items: [{ name, value, cls, k, note, children }], { label, height, format, valueHead, tip, table }) → { update }` | Disposizione «squarified», uno o due livelli. |
| Griglia di calore | `heatGrid(host, { rows, cols, values, counts }, { caption, corner, format, palette, scale, tip }) → { update }` | Una vera tabella; `heatmap()` resta per i rendimenti mensili, `matrix()` per le correlazioni. |
| Legame tra grafici | `linkCharts([grafici…], { window }) → scioglie` | Mirino alla stessa data su tutti; con `window: true` anche zoom e scorrimento. |
| Tabella alternativa | `tableFallback({ summary, caption, head, rows, max }) → { el, refresh }` | `<details>` chiuso, righe costruite solo all'apertura; è ciò che aggiunge `table: true`. |
| Indicatori | `sma, ema, bollinger, vwapMonth, donchian, atrPct, rsi` | Conviction e GQ non si calcolano nel browser: arrivano dal server. |

## Livello Terminale e rifiniture (giro 3, blocco E)

- **Schermata d'apertura del Terminale** (`static/js/views/terminale.js`, griglia `.tgrid` in `css/glass.css`): al livello Terminale lo spazio
  Oggi mostra dieci riquadri su 12 colonne e a 1440 × 900 la pagina non scorre (gli elenchi scorrono dentro): `1` fascia dei numeri ·
  `2` grafico a candele con indicatori e righello del trade · `3` patrimonio contro benchmark con la caduta · `4` freni · `5` posizioni ·
  `6` libro dei trade · `7` strategie · `8` attribuzione · `9` ordini · `0` avvisi. Sotto i 1180 px (o i 720 di altezza) i riquadri si
  impilano nell'ordine di lettura; sotto gli 860 px in una colonna. In `main.js` la tabella degli spazi cambia in un punto solo
  (`terminal: terminale` sulla scheda di Oggi).
- **Tastiera del Terminale**: `Tab` / `Maiusc Tab` e le frecce spostano il fuoco da un riquadro all'altro (per geometria) · `1…9`, `0`
  saltano al riquadro · `j` `k` muovono la riga del riquadro attivo · `Invio` apre lo strumento nel grafico (o entra nel grafico, o apre
  lo spazio del riquadro) · `o` lo apre in Mercati · `Esc` torna al riquadro. Scegliere uno strumento in Posizioni, Libro dei trade o
  Ordini muove il grafico e segna gli altri elenchi. Nessuna richiesta diversa da GET.
- **Provenienza sulla curva**: tratteggiata fino all'«avvio del paper» (linea verticale con etichetta), piena dopo; Mese / Anno /
  Dall'avvio dichiarano quando contengono giorni simulati. In esempio la provenienza resta detta dall'etichetta ESEMPIO.
- **Grafici**: cartellini di vetro del righello in una colonna a destra dell'asse (nome e prezzo, distanza in % e ATR; «Ultima» pieno),
  etichette dell'asse nascoste vicino a un cartellino; intervallo «Trade» e `[` `]` in Mercati; `0` ripristina, `Maiusc ← →` dieci barre.
  `timeChart.setWindow(t0, t1, { animate })` fa scorrere il dominio (`--chart-range`); `waterfall.update` interpola le barre
  (`--chart-morph`, i numeri restano fermi); `growOnce(host, el)` fa crescere barre e celle solo al primo ingresso. Tutto spento con
  «riduci movimento».
- **Scala dei freni e righello**: etichette disposte su righe senza sovrapporsi né troncarsi; l'azione di ogni soglia sta sulla tacca
  solo se entra per intero, altrimenti nell'elenco sotto la scala (sempre al telefono).
- **Fonte più vecchia**: la fascia considera il libro dei trade e l'ultima barra degli strumenti seguiti (`derive.oldestSource`,
  `derive.watchedSymbols`). Test: `python -m pytest tests/test_dashboard_terminale.py -q`.

## Evidenza, Portafoglio, Apprendimento, Sistema (giro 2, blocco B)

I quattro spazi «quando serve» (più Portafoglio) con la stessa grammatica di Oggi, Rischio e Mercati: titolo = domanda, «Come si
legge» in Semplice, provenienza su ogni riquadro e dentro il tracciato, tabella alternativa, stati vuoti dichiarati. Semplice mostra
meno riquadri e più frasi; Esperto tutti i riquadri con le note di metodo; Terminale gli stessi, più stretti.

| Spazio | File | Riquadri |
|---|---|---|
| Evidenza | `views/evidenza.js` | Verdetto a parole con i giorni simulati · paper · reali; profili simulati a base 100 (log) con il confine scelta \| verifica e la caduta sotto; quanto può essere fortuna (prove, Sharpe atteso dal migliore a caso, Deflated Sharpe come intervallo contro la soglia); cono dell'atteso con il percorso del conto; distribuzione della caduta a tre anni con gli scalini e le quote oltre ciascuno; contro l'originale (curve a base 100, distacco cumulato dentro l'imbuto, z, giorni comuni e necessari); profili con mese medio contro mediano e Monte Carlo per scenario; strategie provate con esito e striscia per anno; leva per trade, stress senza stop, schemi di rischio; sedi. |
| Portafoglio | `views/portafoglio.js` | Cascata di attribuzione (oggi / mese / dall'avvio, libro dei trade, «non attribuito»); mappa sede → strumento colorata per strategia; strategie una accanto all'altra (andamento a 30 giorni, risultati, Sharpe del conto solo da 60 giorni, Sharpe mobile simulato con banda); esposizione nel tempo e contro i tetti; posizioni ordinabili con barra del peso e tacca del tetto; mesi × anni; correlazioni; rischio e rendimento di strategie e profili con l'originale. |
| Apprendimento | `views/apprendimento2.js` | I sette passaggi con i conteggi del rapporto e le tre garanzie; tutti i trade contro solo paper (mai sommati); distribuzione di R; R cumulato; R medio per conviction, giorno, moneta e anno con baffo al 90% e n su ogni barra; MAE contro MFE dei soli trade paper; debolezze; regole provate con i sei controlli; in ombra e attive con il comando esatto; registro. **Nessun comando che attivi una regola.** |
| Sistema | `views/sistema2.js` | Battito e componenti; età dei dati per fonte contro i limiti del motore; il ciclo «come funziona» con lo stato vivo su ogni passaggio; registro degli ordini con stati e motivi di rifiuto; avvisi per gravità; cancelli paper → reale; livello AI (regime, conviction con le soglie del libro, overlay). |

- **`views/kit.js`**: i grafici e i mattoni di questo blocco — `errBars` (media, baffo, n; n < 30 attenuato), `colHist` (colonne
  velate = simulato, piene = dati veri; lastre delle zone; righe piene con il valore in testa, mai sovrapposte), `luckChart`,
  `rangeBar`, `yearStrip` (rampa blu ↔ arancio, numero in ogni cella, stacco al 2023), `stepper` (passaggi con stato vivo),
  `sparkArea`, `plot` (etichetta di provenienza dentro l'area), `simpleTable`. Stile solo in `css/spaces.css`, sui token.
- **`derive.js`** (aggiunte): `luck` (intervallo del Deflated Sharpe e soglia dal file della ricerca), `compareStats` (stessa
  formula di `research/v5/v6/b8_confronto/confronto.py`: z a pari volatilità, giorni necessari, esito; con meno di 3 giorni z non
  esiste), `coneData`, `provenanceDays`, `attribution`, `rollingSharpe`, `drawdownSeries`, `rStats` / `groupR` / `histR`,
  `gateState` (un cancello senza valore è «non ancora misurabile», mai superato), `sourceAges`, `SPLIT_T`.
- **Provenienza.** Ricerca = SIMULATO (tratteggiato, colonne velate); conto = PAPER o ESEMPIO (puntinato in demo); mai una cifra
  su dati mescolati: cono e percorso, simulati e paper, memoria e conto stanno in colonne, linee o grafici distinti.
- **Stati vuoti che oggi si vedono.** Storia dell'esposizione vera (la fotografia non ha `exposure_history`: al suo posto le quote
  di rischio simulate, dichiarate, e per sede uno stato vuoto); MAE / MFE (nessun trade paper chiuso); regole in ombra e attive;
  cancelli senza valore; confronto con meno di 90 giorni comuni («In corso»).
- **Pagine precedenti.** Restano come schede d'archivio (`#/evidenza/ricerca`, `#/evidenza/leva`, `#/portafoglio/risultato`,
  `…/strategie`, `…/posizioni`, `…/panoramica`, `#/apprendimento/archivio`, `#/sistema/salute`, `…/ordini`, `…/guida`). Contenuto non
  ancora migrato: di Ricerca ventaglio e rischio di rovina per leva, quote nel tempo, robustezza, walk-forward, quintili di GEX,
  funding per anno, conviction per livello, idee scartate della prima tornata; di Risultato rendimenti giornalieri e statistiche
  mobili; di Come funziona le quattro strategie spiegate. Il resto è nei quattro spazi.

Test: `python -m pytest tests/test_dashboard_spazi.py -q`.
