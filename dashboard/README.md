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

## Variabili d'ambiente

| Variabile | Predefinito | A che cosa serve |
|---|---|---|
| `GERVA_SNAPSHOT` | `var/gerva/snapshot.json` | Lo snapshot da servire. Se il file non esiste si serve l'esempio DEMO; se esiste ma è illeggibile la risposta è 503 (mai l'esempio al posto di dati veri). |
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
| POST | `/api/v1/kill` | Crea il file KILL. Vedi sotto. |

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
```

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
static/js/charts.js       grafici SVG: linee con mirino, drawdown, heatmap, barre, sparkline, barre di limite
static/js/views/          una sezione per file
static/sample_snapshot.json   esempio DEMO, coerente al centesimo (lo verifica il test)
```

Tema scuro di base, chiaro se lo chiede il sistema o l'utente (pulsante in alto a destra, ricordato nel browser).
Verde e rosso compaiono solo sul P&L, sempre insieme a segno e freccia; ambra e rosso di stato solo sulle anomalie,
sempre con icona e parola. Le cifre sono tabellari. I grafici si leggono anche da tastiera (frecce) e in tabella.
