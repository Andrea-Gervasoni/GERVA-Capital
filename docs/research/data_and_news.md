# Fonti di dati e notizie gratuite

Etichette: [A] documentazione ufficiale della fonte, [M] documentazione di terzi coerente, [B] debole o in conflitto.

**Vincolo ambientale verificato il 4/11/2026:** dall'ambiente cloud in cui è stato scritto questo codice le richieste a Binance, Yahoo Finance, Stooq e SEC sono bloccate dalla policy di rete (codice 000); passano solo PyPI e Google Fonts. Tutte le fonti sotto vanno quindi usate **dal Mac di Andrea** (dove GERVA-Q già scarica Yahoo e Binance). Il codice di raccolta è scritto per funzionare là e degrada senza errori quando la rete manca.

## 1. Prezzi

| Fonte | Cosa | Limiti | Licenza / condizioni | Conf. |
|---|---|---|---|---|
| `data-api.binance.vision` | Candele crypto, ticker; mirror di sola lettura dell'API Binance | Peso per IP 6.000/minuto; una chiamata klines pesa 2 | Uso dati di mercato pubblici; da rileggere i termini Binance | [M] ([libreria Go](https://pkg.go.dev/github.com/algo-one/binance-data-downloader/internal/vision)) |
| `data.binance.vision` | Archivi storici in blocco (zip giornalieri/mensili) | Bucket statico, senza i limiti dell'API | Come sopra | [M] |
| Yahoo Finance via `yfinance` | Prezzi aggiustati di azioni ed ETF | Non ufficiale, può rompersi o essere limitato | Termini Yahoo: uso personale | [B] |
| FRED | Tassi, macro USA | 120 richieste/minuto per chiave (riportato da librerie client) | Chiave gratuita; termini da rileggere sul sito FRED | [M] ([fredr](https://cran.r-project.org/web/packages/fredr/news/news.html)) |
| CoinGecko Demo | Prezzi e capitalizzazioni crypto | Circa 30 chiamate/minuto (varia con il traffico), 10.000/mese; contano anche le chiamate in errore | Chiave Demo gratuita | [A] ([CoinGecko docs](https://docs.coingecko.com/docs/common-errors-rate-limit)) |
| DefiLlama | TVL, stablecoin, rendimenti | Nessun limite pubblicato; ≈300/minuto come indicazione prudente; unlock ed emissioni sono a pagamento | API gratuita senza chiave; Pro 300 $/mese | [B] ([guida](https://eco.com/support/en/articles/14800367-defillama-free-tvl-and-defi-analytics)) |

**Regola Data Engineer:** solo **candele chiuse** (GERVA-Q filtra già `close_time < now`); ogni file di dati ha hash e timestamp di download; un buco o un salto > 8 deviazioni standard blocca la pipeline e apre un evento.

## 2. Filing e annunci societari

| Fonte | Cosa | Limiti | Conf. |
|---|---|---|---|
| SEC EDGAR | Filing (8-K, 10-Q, 10-K, Form 4); feed RSS/Atom per società, tipo di modulo, filing recenti | Massimo **10 richieste/secondo** in totale, indipendentemente dal numero di macchine; User-Agent obbligatorio con nome e contatto | [A] ([SEC, Accessing EDGAR Data](https://www.sec.gov/os/accessing-edgar-data); [SEC RSS](https://www.sec.gov/about/secrss.shtml)) |

Lo User-Agent deve contenere un contatto reale: per scelta di privacy il codice lo legge da `.env` (`SEC_USER_AGENT`) e non lo scrive mai nei log.

## 3. Calendari macro

| Evento | Fonte ufficiale | Date note | Conf. |
|---|---|---|---|
| FOMC | federalreserve.gov (calendario provvisorio, confermato alla riunione precedente) | 2026: ultima riunione **8–9 dicembre**. 2027 (provvisorio): 26–27 gen, 16–17 mar, 27–28 apr, 8–9 giu, 27–28 lug, 14–15 set, 26–27 ott, 7–8 dic | [M] ([fedratecalc](https://fedratecalc.com/fomc-meeting-schedule/), [MNI](https://www.mnimarkets.com/articles/mni-federal-reserve-sets-2027-fomc-meeting-schedule-1757093400287)); da confermare sul sito Fed |
| CPI USA | bls.gov, calendario e feed iCal `bls.gov/schedule/news_release/bls.ics` | Ottobre 2026 → **10 novembre 2026** 8:30 ET; novembre → **10 dicembre 2026** | [M] ([BLS schedule](https://www.bls.gov/schedule/news_release/cpi.htm)); da confermare su BLS |

L'Event Calendar Analyst *non* inventa date: le carica da `data/calendar/*.yaml`, file che il codice aggiorna dal feed iCal BLS e dalla pagina Fed quando la rete lo consente, e segna ogni data con la fonte e lo stato (confermata o provvisoria).

## 4. Notizie

| Fonte | Cosa | Limiti | Conf. |
|---|---|---|---|
| GDELT DOC 2.0 | Monitoraggio notizie mondiali, aggiornamento ogni 15 minuti, ricerca per parole e temi | Senza chiave; copertura storica in conflitto tra le fonti (3 mesi mobili o dal 2017) | [M] ([GDELT blog](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)) |
| Feed RSS di banche centrali e regolatori | Comunicati Fed, BCE, SEC, ESMA | Nessuno significativo | [A, sono le fonti stesse] |
| Feed RSS di testate | Titoli e sommari | Licenza: solo titolo, link e breve estratto; mai il testo integrale | — |

**Regola Fact-Checker:** una notizia arriva ai desk solo se confermata da una **seconda fonte indipendente** (dominio diverso, non una ripubblicazione) oppure se la fonte è *primaria* (comunicato ufficiale della Fed, filing SEC). Altrimenti resta "non verificata" e non può essere citata come base di una decisione.

## 5. AI esterne (consulenti e Capi Pod ospiti)

| Fornitore | Endpoint | Note | Conf. |
|---|---|---|---|
| Anthropic | SDK ufficiale `anthropic` | Modelli e prezzi in `config/models.yaml` | [A] |
| Moonshot (Kimi) | `https://api.moonshot.ai/v1`, formato Chat Completions di OpenAI | Account da ricaricare (≥1 $); nomi dei modelli e prezzi da verificare sulla piattaforma | [M] ([guida](https://www.chatbase.co/blog/kimi-k2-api)) |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | Livello di compatibilità OpenAI ufficiale | [A] ([Google AI](https://ai.google.dev/gemini-api/docs/openai?hl=en)) |

Nuove chiavi = grande richiesta ad Andrea (regola di autonomia 4). Nessun dato sensibile in uscita: il filtro `llm/redact.py` toglie numeri di conto, NAV reali e chiavi prima di ogni chiamata esterna, e un test lo verifica.
