# GERVA Capital

> **Novembre 2026: rifondazione (v5).** Il documento da leggere per primo è
> [`docs/RIFONDAZIONE.md`](docs/RIFONDAZIONE.md): audit, ricerca su dati reali, GEX e VWAP verificati, portafoglio e leva,
> validazione, architettura, struttura societaria, dashboard, roadmap. I numeri sono in
> [`research/v5/RESULTS.md`](research/v5/RESULTS.md) e sono tutti **simulati**.

## Il motore nuovo: `gerva/`

Deterministico, senza LLM nel percorso degli ordini, solo paper finché i cancelli numerici non sono verdi.

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest                 # 418 test
.venv/bin/python -m gerva research         # rifà tutti i backtest -> research/v5/RESULTS.md
.venv/bin/python -m gerva demo             # fotografia dimostrativa dal backtest (SIMULATO)
.venv/bin/python -m dashboard.server       # http://127.0.0.1:8787
.venv/bin/python -m gerva cycle            # un giro del ciclo live in paper, con prezzi veri
.venv/bin/python -m gerva supervise -- run # ciclo continuo con riavvio automatico
.venv/bin/python -m gerva gates            # cancelli paper -> reale
.venv/bin/python -m gerva kill "motivo"    # chiude tutto e ferma il sistema
```

| Cartella | Che cosa contiene |
|---|---|
| `gerva/strategies/book.py` | Le quattro strategie in produzione: una sola definizione per backtest e live |
| `gerva/risk/engine.py` | Stati NORMAL / REDUCED / HALTED / KILLED, scalini a −10%, −15%, −20%, leva massima 2x (mai oltre 3x) |
| `gerva/live/runner.py` | Il ciclo: recupero ordini, dati, conto, rischio, pesi, ordini, fotografia |
| `gerva/ops/` | Registro durevole, retry, interruttore, allarmi, supervisore |
| `gerva/agents/` | Consiglio di ricerca: gli agenti propongono schede, il codice misura e decide |
| `gerva/research/run.py` | Tutti i backtest del documento |
| `dashboard/` | Pagina in sola lettura: P&L, esposizione, rischio, strategie, ordini, sistema |
| `config/gerva.yaml` | Limiti di rischio e parametri del ciclo |
| `.claude/` | Sotto-agenti (`gerva-ricercatore`, `gerva-validatore`, `gerva-rischio`, `gerva-operazioni`) e comandi (`/gerva-ricerca`, `/gerva-stato`, `/gerva-ipotesi`) |

Tutto ciò che segue descrive la società di agenti preesistente (`firm/`), che resta come laboratorio in paper.

---

Una società di trading quantitativo **simulata ma vera nelle regole**, fatta di agenti AI e costruita
attorno al motore GERVA-Q v3 (Pod Zero). Solo conto paper. Il rischio, i costi, i punteggi e le
esecuzioni sono codice deterministico e testato; gli agenti leggono, verificano, propongono e giudicano.

> Non c'è nessuna promessa di rendimento. La società massimizza il rendimento **corretto per il rischio**
> e registra i risultati negativi come quelli positivi.

**Per cominciare: [`docs/INIZIA_QUI.md`](docs/INIZIA_QUI.md)**, cinque fasi spiegate passo per passo.

## Avvio sul Mac (una volta)

```bash
cd ~/Documents
git clone -b claude/gifted-ramanujan-n3a5gg https://github.com/Andrea-Gervasoni/GERVA-Capital
cd GERVA-Capital
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt yfinance
cp .env.example .env        # GERVA_Q_PATH=~/Documents/GERVA-Q (gia' impostato)
.venv/bin/python firm.py init
.venv/bin/python firm.py portal          # http://127.0.0.1:8765
```

Battito ogni 15 minuti (la società lavora a eventi e sveglia solo gli agenti necessari):

```
*/15 * * * * cd ~/Documents/GERVA-Capital && .venv/bin/python firm.py heartbeat >> var/heartbeat.log 2>&1
```

Per vedere il portale pieno senza toccare il database vero: `python firm.py demo` e poi
`python firm.py portal --demo` (45 giorni di mercato **sintetico** in `var/demo/`, marcati DEMO).

## Sul server (24 ore su 24, solo paper)

Guida completa, passo per passo: [`docs/DEPLOY.md`](docs/DEPLOY.md). In breve: un VPS Ubuntu indurito da
`deploy/server_setup.sh`, i container di `deploy/docker-compose.yml` (GERVA-Q con il suo IB Gateway paper,
osservatore, battito, portale) e il portale aperto dal tuo computer con un tunnel SSH:

```bash
ssh -N -L 8765:127.0.0.1:8765 gerva
```

## Comandi

| Comando | Cosa fa |
|---|---|
| `firm.py init` | DB, token di Andrea (`var/andrea.token`, 0600), organico, 55 prove storiche di GERVA-Q |
| `firm.py portal [--demo]` | portale locale, solo 127.0.0.1:8765 |
| `firm.py heartbeat` / `run` | un battito / battito continuo |
| `firm.py status` · `verify` | budget, rischio, prove · verifica della catena di hash |
| `firm.py data` | (sul Mac) prezzi reali per la ricerca; senza, la ricerca usa dati sintetici e vale solo come collaudo |
| `firm.py release` · `release --apply ID` | rilasci di GERVA-Q in coda · applicazione di domenica con backup e changelog |
| `firm.py research gervaq4` | (sul Mac) banco di prova dei miglioramenti del motore contro la v3 |
| `firm.py report` | report del giorno con le correzioni proposte dalla diagnostica |
| `python -m llm.evals [agente]` | eval dei prompt (senza chiave: solo validità dello schema) |
| `firm.py observe` | (server) osservatore in sola lettura del conto della sfida |
| `firm.py ibkr-check` | prova la connessione IBKR in sola lettura (conto mascherato) |
| `firm.py set-password` | hash della password del portale per il server |
| `firm.py check-backtest --sharpe S --obs N --trials K` | quanto di un backtest visto altrove puo' essere fortuna (anche `--trades`, `--hit-rate`, `--payoff`) |
| `firm.py research crypto` · `research lungo` | zona ricerca crypto (sleeve della v3 contro 6 varianti) · piano e rischio della quota AI di lungo periodo |
| `firm.py shadow` | portafoglio ombra: v4 contro v3 in avanti dal 5/11/2026 (lo aggiorna anche il battito ogni sera) |
| `python -m pytest` | 153 test |

## Il portale

L'edificio di GERVA Capital visto dall'alto, con l'insegna sul tetto e lo skyline che segue l'ora reale.
**Rotella** = zoom verso il cursore, **trascina** = sposta, **doppio clic** = zoom sulla stanza, ⤢ = tutto l'edificio.
Clic su una persona → scheda con ritratto, indicatori, grafici, previsioni, carriera, errori, costi, memoria.

- **Uffici per grado:** suite d'angolo con vista panoramica per il Capo; uffici privati con finestra per Manager e Head;
  uffici a vetri per i Senior; open space per Analisti e Stagisti. La promozione porta un trasloco (con scatola) e più arredi;
  i Gerva-Coin maturati aggiungono trofei, acquario, quadro d'oro.
- **Edificio che cresce:** il livello dipende dal massimo storico del valore della società e non scende mai.
  Servizi per tutti: caffè → lounge → mensa → palestra → biblioteca → sala giochi.
- **Vita d'ufficio:** deleghe (il superiore chiama, il subordinato va e torna con la cartella), consegne, riunioni in sala
  con le posizioni di ciascuno, promozioni, bonus, allarmi del CRO e rifiuti del Gateway seguono gli **eventi veri** con il loro
  testo. Pause e chiacchiere sono animazioni d'ambiente.

## Com'è fatta

```
quantlab/    motore di ricerca: PSR, DSR, MinTRL, PBO (CSCV), bootstrap, CPCV con purging/embargo,
             Ledoit-Wolf, HRP, ERC, Black-Litterman, Kelly frazionato, backtest con deriva dei pesi,
             modello dei costi a radice quadrata, test anti look-ahead (troncamento e oracolo)
firm/        la società: DB append-only, audit con catena di hash, eventi, impostazioni (solo Andrea),
             registro agenti, Budget Governor, trial registry, Scorekeeper, motore di rischio, pod,
             Gateway di Esecuzione con sub-ledger e compensazione, economia in Gerva-Coin, flussi di
             lavoro, battito, finestra di rilascio, adattatore di sola lettura verso GERVA-Q
llm/         provider (Anthropic, Kimi/Gemini compatibili OpenAI, simulazione), runtime a schema,
             permessi degli strumenti, filtro dei segreti, valutatore dei prompt
agents/      <id>/profile.yaml, prompt.md, memory.md per ogni scrivania (28: 11 agenti, 8 automi, 9 posizioni aperte)
evals/       casi di prova per ogni agente, con trappole (injection, fonti false, dati mancanti)
portal/      FastAPI + WebSocket + canvas pixel art, sprite originali generati da matrici
docs/        ricerca di Fase 0 con fonti e confidenza, decisioni, guida ai prompt
research/    fascicoli di ricerca e rilasci proposti per GERVA-Q
```

## Regole che il codice fa rispettare

- **Solo paper**: `firm.mode` non può valere altro; il Gateway rifiuta conti non `DU`; non esiste un comando live.
- **Gli agenti non toccano il broker**: solo i Capi Pod hanno `submit_order`, legato al proprio pod, e ogni ordine passa dai controlli del Gateway.
- **Limiti di rischio e budget**: li cambia solo Andrea dal portale (token locale); nessuno strumento degli agenti li espone (test).
- **KILL**: lo esegue il motore di rischio (drawdown di società −15%) o Andrea; gli agenti possono solo raccomandarlo.
- **Audit**: tabelle append-only per trigger SQLite e catena di hash verificata ogni giorno.
- **Testo dal web**: sempre dentro `<dati_non_fidati>`; chi legge il web non ha strumenti con effetti.
- **Segreti**: filtrati da audit, eventi e chiamate esterne; solo in `.env`.
