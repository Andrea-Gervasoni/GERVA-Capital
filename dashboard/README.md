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

## Due livelli di lettura

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
static/js/views/          una sezione per file (dodici)
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
