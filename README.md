# GERVA Capital

Una società di trading quantitativo **simulata ma vera nelle regole**, fatta di agenti AI e costruita
attorno al motore GERVA-Q v3 (Pod Zero). Solo conto paper. Il rischio, i costi, i punteggi e le
esecuzioni sono codice deterministico e testato; gli agenti leggono, verificano, propongono e giudicano.

> Non c'è nessuna promessa di rendimento. La società massimizza il rendimento **corretto per il rischio**
> e registra i risultati negativi come quelli positivi.

## Avvio sul Mac (una volta)

```bash
cd ~/Documents
git clone https://github.com/Andrea-Gervasoni/GERVA-Capital
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

## Comandi

| Comando | Cosa fa |
|---|---|
| `firm.py init` | DB, token di Andrea (`var/andrea.token`, 0600), organico, 55 prove storiche di GERVA-Q |
| `firm.py portal [--demo]` | portale locale, solo 127.0.0.1:8765 |
| `firm.py heartbeat` / `run` | un battito / battito continuo |
| `firm.py status` · `verify` | budget, rischio, prove · verifica della catena di hash |
| `firm.py data` | (sul Mac) prezzi reali per la ricerca; senza, la ricerca usa dati sintetici e vale solo come collaudo |
| `firm.py release` · `release --apply ID` | rilasci di GERVA-Q in coda · applicazione di domenica con backup e changelog |
| `python -m llm.evals [agente]` | eval dei prompt (senza chiave: solo validità dello schema) |
| `python -m pytest` | 72 test |

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
