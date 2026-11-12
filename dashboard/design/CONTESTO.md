# Contesto comune per le squadre (quant e design)

## Che cosa chiede il proprietario (parole sue, in sintesi)
"Entro a Wall Street, tutti si stupiscono e mi chiedono il mio terminale perché è completo ma BELLO, PULITO, COMPRENSIBILE, con ARIA, LIQUID GLASS, come se Apple preparasse un terminale, con animazioni." Prima aveva detto: deve far capire tutto ai principianti e ai quant esperti; ordinato ma ricco; tanti grafici dettagliati, aggiornati di continuo e utili; poi: "poco professionale, pochi grafici professionali". Quindi: la completezza di un terminale di trading, la qualità visiva e la chiarezza di un prodotto consumer di altissimo livello. Non la densità nera e ambra dei terminali classici.

## Che cosa è il fondo
GERVA Capital: un fondo sistematico personale, oggi solo in PAPER. Un ciclo ogni 15 minuti calcola quattro strategie giornaliere (trend su BTC/ETH; momentum sulle 20 crypto più scambiate; ritorno alla media su S&P 500 e Nasdaq; trend lento su 17 ETF), le pesa a parità di rischio, applica leva fino a 2x, un livello AI che può solo ridurre, e un motore di rischio che decide per ultimo (scalini di caduta −20 / −30 / −40%, arresto di emergenza). In più: un libro di trade a margine isolato su BTC/ETH/SOL nei giorni ad alta "conviction" (leva ~11x, rischio 0,5–1% per trade, stop a 1×ATR), un indicatore proprietario in ombra ("indicatore Gervasoni", GQ), un ciclo di automiglioramento (memoria dei trade → valutazione → ipotesi → validazione → ombra → approvazione), e un confronto giornaliero con il sistema originale del proprietario. Leggi docs/COME_FUNZIONA.md e docs/PAPER.md.

## Dati disponibili (tutti in sola lettura)
- Fotografia live `snapshot.json` (ogni 5 s): patrimonio, P&L giorno/mese/anno/dall'avvio, curva del patrimonio e benchmark, caduta, esposizione lorda/netta/leva, per classe e sede, posizioni, stato del rischio con limiti e utilizzi, VaR/ES, volatilità realizzata/obiettivo, strategie (quota, esposizione, P&L, Sharpe live vs backtest, sparkline), ordini, salute del sistema, cancelli paper→reale, stato AI (regime, conviction del giorno, overlay). Formato: gerva/live/snapshot.py; esempio dashboard/static/sample_snapshot.json.
- Ricerca: research/v5/quant.json e quant_v4.json (curve, correlazioni, Monte Carlo, leva per trade, profili, sistema originale ricostruito, esito di 18 analisti).
- Apprendimento: learn/report.json (esempio dashboard/static/sample_learn.json).
- In arrivo dal costruttore: OHLCV giornalieri per strumento con conviction e GQ (`/api/v1/market/ohlc`), stato del libro dei trade (`/api/v1/tradebook`), storico dei trade simulati e paper (`/api/v1/trades/history`), confronto con l'originale (`/api/v1/compare`).
- NON esistono: book di negoziazione, tick, dati intraday del patrimonio più fitti di 15 minuti, notizie in tempo reale.

## Che cosa esiste oggi
dashboard/ (leggi dashboard/README.md): 12 pagine (Panoramica, Performance, Esposizione, Rischio, Strategie, Ordini, Sistema, AI, Apprendimento, Ricerca, Leva per trade, Come funziona), HTML/CSS/JS scritti a mano, livelli Semplice/Esperto, glossario, tema chiaro/scuro. Schermate recenti in docs/img/dashboard-*.png (apri con Read: dashboard-v2-semplice-panoramica.png, dashboard-v3-leva.png, dashboard-v4-confronto.png, dashboard-v5-apprendimento.png).

## Vincoli che non si discutono
- Nessuna libreria esterna, nessun CDN, nessun passo di build; font solo locali o di sistema.
- Sola lettura: l'unico comando che scrive è l'arresto di emergenza (KILL), protetto da token. Nessun pulsante che invii ordini o attivi regole.
- Ogni numero simulato porta l'etichetta SIMULATO; nessun dato finto presentato come vero; stati vuoti espliciti.
- Lingua: italiano. Due pubblici: principiante (livello Semplice) ed esperto.
- Accessibilità: contrasto AA sul testo anche sopra superfici traslucide, tastiera completa, `prefers-reduced-motion` e `prefers-reduced-transparency` rispettati, telefono senza scorrimento orizzontale.
- Niente marchi, nomi o loghi di terzi (né Bloomberg né Apple): lo stile è originale, "vetro liquido" come linguaggio, non come copia.
