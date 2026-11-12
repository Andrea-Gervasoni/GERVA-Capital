# Avvio del paper trading

Tutto ciò che segue riguarda un conto di prova. Nessun ordine reale parte: il codice accetta solo le modalità `paper` (registro interno) e `alpaca-paper`.

## Il profilo scelto

Scelto misurando ogni combinazione **con il motore di rischio dentro**, perché è così che girerà ([`research/v5/v6/scelta_profilo.out`](../research/v5/v6/scelta_profilo.out), SIMULATO).

| Parte | Impostazione | Dove |
|---|---|---|
| Libro giornaliero | Quattro strategie, volatilità obiettivo 15%, leva al massimo 2x, liquidità ferma in un ETF monetario | `config/gerva.yaml`, `limits` e `cash` |
| Libro dei trade | Margine isolato, circa 11x (mai oltre 15x), rischio 0,5% sui setup confermati e 1% sugli eccezionali | `config/gerva.yaml`, `trades` |
| Scalini di rischio | −20% dimezza, −30% un quarto, −40% chiude tutto e si ferma | `config/gerva.yaml`, `limits` |

| Simulato, 2018–2026, motore di rischio dentro | Rendimento annuo | Sharpe | Caduta massima | Giorni con il freno tirato |
|---|---:|---:|---:|---:|
| **Profilo del paper** (scalini 20 / 30 / 40) | **39,5%** (dal 2023: 37,8%) | **1,27** (1,09) | **−21%** | 2% |
| Stesso profilo con scalini 15 / 22 / 30 | 36,9% (34,6%) | 1,21 (1,02) | −19% | 13% |
| Stesso profilo con gli scalini precedenti (10 / 15 / 20) | 30,2% | 1,12 | −17% | 39% |
| Profilo "massimo" (trade 1% / 2%) con scalini 15 / 22 / 30 | 33,5% | 0,96 | −26% | 53% |

- **Scelta (di Andrea, 12/11/2026):** scalini 20 / 30 / 40 e trade a 0,5% / 1%.
- **Motivazione:** è la combinazione con il rendimento e lo Sharpe più alti tra quelle senza arresti e con caduta massima entro il 25%; i freni scattano nel 2% dei giorni.
- **Il prezzo:** l'arresto totale scatta solo a −40% dal massimo. Nelle simulazioni la caduta massima è −21% e lo scalino dei −30% non viene mai toccato; in un periodo peggiore di quelli del campione il conto può perdere il 40% prima che il motore chiuda tutto.
- **Alternative scartate:** scalini 15 / 22 / 30 (2,6 punti in meno, arresto a −30%: era la mia proposta); scalini 10 / 15 / 20 (frenano quattro giorni su dieci); trade a 1% / 2% (più rischio e meno rendimento, perché i freni scattano metà del tempo).
- **Avvertenza:** il vincolo "freni attivi di rado" è stato aggiunto dopo aver visto che la prima regola di scelta dava un risultato degenere.

Sono circa il 2,8% al mese composto nelle simulazioni; lo scenario centrale è la metà.

## Che cosa gira

| Processo | Comando | Frequenza | Che cosa fa |
|---|---|---|---|
| Ciclo principale | `python -m gerva supervise -- run` | Ogni 15 minuti | Dati, quattro strategie, quote, leva, overlay AI, motore di rischio, ordini paper, fotografia per la dashboard |
| Passi giornalieri | `python -m gerva daily` | Ogni ora (agisce una volta al giorno) | Libro dei trade a margine isolato; ciclo di automiglioramento; indicatore Gervasoni in ombra |
| Confronto | `python research/v5/v6/b8_confronto/confronto.py` | Ogni ora (una riga al giorno) | Valore del nuovo fondo, del sistema originale, dell'S&P 500 e di Bitcoin; confronto corrente |
| Dashboard | `python -m dashboard.server` | Sempre | `http://127.0.0.1:8787` |
| Livello AI | `python -m gerva ai` | Ogni 6 ore | Solo con `ANTHROPIC_API_KEY`; senza chiave il sistema gira lo stesso, senza overlay |

## Avvio

**Con Docker, su un server** (consigliato):

```bash
docker compose -f deploy/docker-compose.gerva.yml up -d --build
```

**Senza Docker, su Mac o Linux:**

```bash
bash deploy/avvia_paper.sh
```

```bash
bash deploy/avvia_paper.sh stato
```

```bash
bash deploy/avvia_paper.sh stop
```

**Per usare il conto di prova Alpaca** invece del registro interno: metti `ALPACA_KEY` e `ALPACA_SECRET` in `secrets/gerva.env` (mai nel repository), imposta `mode: alpaca-paper` in `config/gerva.yaml`, poi:

```bash
python -m gerva check-broker
```

L'adattatore Alpaca è stato provato solo contro un servizio finto: quel comando è la prima prova contro il servizio vero. Il libro dei trade resta comunque un registro interno, perché Alpaca non offre perpetual a leva.

## Il sistema originale nel confronto

Lo strumento legge il valore del conto originale, in quest'ordine, da: `legacy_nav.csv` nella cartella dei dati (colonne `data,nav_eur,flusso_eur`), il database del vecchio sistema, il registro di GERVA-Q. Il file è il modo più semplice: una riga al giorno con il valore del conto. Senza quel valore il confronto non parte.

## Il ciclo di automiglioramento

```
memoria dei trade → valutazione → ipotesi → validazione → ombra → approvazione di Andrea → attiva
```

- Ogni trade chiuso entra in memoria con il contesto d'ingresso, i costi, l'escursione massima a favore e contro, il motivo di uscita.
- Il motore di valutazione cerca le fette di trade che rendono meno delle altre.
- Ogni debolezza diventa un'ipotesi: una regola che può solo **saltare o dimezzare** un trade.
- Il validatore, che è codice e non chi ha proposto, la prova in campione, fuori campione, anno per anno e con soglie vicine. La soglia statistica sale con il numero di ipotesi provate.
- Una regola che passa resta in ombra finché non regge anche su almeno 20 trade paper.
- Diventa attiva solo con questo comando, dato da te:

```bash
python -m gerva learn --approve <id> --confirm
```

Sul passato, oggi, il ciclo trova due fette sospette (volatilità alta, martedì), genera quattro ipotesi e le respinge tutte: in verifica quelle fette rendono più delle altre. È il comportamento giusto.

## Che cosa guardare

| Quando | Che cosa | Comando o pagina |
|---|---|---|
| Ogni giorno | Stato del rischio, battito, avvisi | Dashboard, Panoramica e Sistema |
| Ogni settimana | Trade chiusi, R medio, ipotesi provate | `python -m gerva learn`; dashboard, Apprendimento |
| Ogni settimana | Confronto con l'originale | `confronto.py --report-only` |
| Ogni mese | Cancelli per il denaro reale | `python -m gerva gates` |

## Cancelli

Libro giornaliero: 90 giorni; ciclo disponibile al 99%; nessun ordine non riconciliato; nessun arresto; caduta entro il 20%; probabilità che lo Sharpe vero sia positivo almeno 60%; scostamento dal backtest entro 3 punti; costi reali entro 1,5 volte quelli ipotizzati.

Libro dei trade: almeno 40 trade chiusi; R medio positivo e almeno metà di quello simulato; nessuna perdita oltre il margine.

Contro l'originale, su almeno 90 giorni comuni: "non smentito" con rendimento più alto e caduta non oltre 1,5 volte; "batte" solo con una differenza statisticamente netta (z > 1,3), da rivedere a 180 e 365 giorni; con z < −1,3 si torna all'originale.

## Limiti dichiarati

- Il libro dei trade lavora su barre giornaliere e non invia ordini a una sede: misura la regola, non l'esecuzione.
- Le due strategie di sola ricerca (carry, acquisto dei crolli) non sono nel ciclo.
- Mancano gli adattatori per Kraken, Hyperliquid e IBKR.
- Il libro dei trade dimensiona sul proprio registro (capitale iniziale più i suoi guadagni), non sul patrimonio del libro giornaliero.
