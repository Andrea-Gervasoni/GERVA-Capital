# Strategie dai paper: cosa dice la ricerca e cosa abbiamo implementato

Novembre 2026. Regola: ogni strategia ha una fonte pubblicata e un'ipotesi scritta. Il backtest si fa al netto dei costi, la prova finisce nel registro (Deflated Sharpe) e il comitato decide se accenderla.

## Prima, una nota onesta su "+1000% in una settimana"

- **HyperGrok** è un framework open source per far operare agenti su Hyperliquid (futures perpetui crypto, leva alta). Chi lo pubblica dichiara che non contiene strategie e non promette rendimenti (galleonlabs/hypergrok-trading-desk).
- **Alpha Arena (nof1, stagione 1, ottobre–novembre 2025)** è la prova pubblica più vicina: sei modelli, 10.000 $ ciascuno, perpetui su Hyperliquid, 17 giorni. Ha vinto Qwen 3 Max con circa +22%. DeepSeek ha fatto circa +5%; GPT-5 e Gemini hanno perso circa il 60%. Più della metà dei modelli ha chiuso in perdita. Grok era in testa con +500% il primo giorno e poi ha perso il primato.
- **Matematica:** una settimana di crypto ha una volatilità tipica dell'8%. Per fare +1000% serve una leva intorno a 50 volte su un movimento favorevole. Con la stessa leva, un movimento contrario del 2% azzera il conto. Chi mostra +1000% in una settimana è quasi sempre uno dei pochi sopravvissuti tra i tanti che hanno fatto la stessa scommessa e sono stati liquidati (vedi "Kelly", sotto).
- **Cosa vuol dire per noi:** cerchiamo uno Sharpe più alto (più vantaggio per unità di rischio), non una leva più alta. Il tetto alla crescita composta è g* = r + SR²/2 (Kelly 1956; Thorp). La leva sposta solo dove si arriva a quel tetto, e quanto si rischia per arrivarci.

## Cosa funziona, secondo la letteratura

| Idea | Fonte | Cosa mostra | Usabile da noi |
|---|---|---|---|
| Momentum di serie storica | Moskowitz, Ooi & Pedersen (2012, *JFE*); Hurst, Ooi & Pedersen (2017, *JPM*), un secolo di dati | Il rendimento degli ultimi 1–12 mesi predice il prossimo, su tutte le classi di attività | Sì (GERVA-Q lo usa già sulle azioni e gli ETF) |
| Momentum nelle crypto | Liu & Tsyvinski (2021, *RFS*); Liu, Tsyvinski & Wu (2022, *JF*) | Le crypto hanno un forte momentum di serie storica, da giorni a settimane, legato all'attenzione degli investitori | **Sì: `crypto_tsmom`** |
| Volatilità obiettivo / gestita | Moreira & Muir (2017, *JF*); Harvey et al. (2018, *JPM*) | Esporsi meno quando la volatilità è alta migliora lo Sharpe e riduce le code | Sì (leva gestita su IBKR; pesi in `crypto_tsmom`) |
| Crolli del momentum | Daniel & Moskowitz (2016, *JFE*); Barroso & Santa-Clara (2015, *JFE*) | Il momentum crolla dopo i ribassi e con la volatilità alta; scalarlo per la volatilità ne dimezza i crolli | Sì (nella volatilità obiettivo) |
| Momentum intraday del mercato | Gao, Han, Li & Zhou (2018, *JFE*) | Il rendimento fino alle 10:00 predice quello dell'ultima mezz'ora dell'S&P 500 | **Sì: `spy_intraday_momentum`** |
| Reversal a breve con VIX alto | Nagel (2012, *RFS*) | I profitti del reversal a breve salgono quando il VIX è alto (chi dà liquidità è pagato di più) | Prossimo candidato |
| Carry delle crypto (funding) | Schmeling, Schrimpf & Todorov (BIS WP 1087) | Il funding dei perpetui contiene un premio | No su Alpaca (niente perpetui); sì con Hyperliquid testnet |
| Il rovescio della medaglia | McLean & Pontiff (2016, *JF*) | Dopo la pubblicazione i rendimenti delle anomalie calano in media di circa un terzo, di più per quelle facili da sfruttare | Per questo il backtest va al comitato con tutti i numeri |
| Troppe prove | Bailey & López de Prado (2014, *JPM*), Deflated Sharpe | Più varianti si provano, più alta deve essere la soglia | Già nel registro delle prove |

## Le due strategie implementate (`firm/strategies.py`)

1. **`crypto_tsmom`**, momentum crypto con volatilità obiettivo. Nove monete, barre orarie. Il segnale è la media dei segni del rendimento a 24, 72 e 168 ore. Il peso è inversamente proporzionale alla volatilità a 7 giorni, con obiettivo 40% annuo, al massimo 25% per moneta e mai oltre il capitale della strategia (Alpaca non dà leva né short sulle crypto). Si ribilancia solo oltre una banda del 2%, perché i costi (stimati in 30 punti base per giro) altrimenti si mangiano tutto. Esegue attraverso il ribilanciamento crypto di Alpaca.
2. **`spy_intraday_momentum`**, momentum dell'ultima mezz'ora. Alle 15:30 di New York si entra su SPY nella direzione del rendimento dalla chiusura di ieri alle 10:00, e alle 15:58 si chiude. Barre a 5 minuti.

**Come si accendono:** `firm.py strategie --backtest tutte` scarica i dati storici da Alpaca, fa il backtest con i costi singoli e doppi, registra la prova, calcola Deflated Sharpe e cancello, e porta al comitato un'idea "accendere la strategia" con tutti i numeri nella tesi. Se il comitato approva, la strategia gira da sola. Si spegne con un voto contrario o con `firm.py regole --annulla N`.

## Prossimi candidati

- Reversal a breve condizionato al VIX (Nagel 2012) sulle azioni liquide.
- Breakout di Donchian sulle crypto (Hudson & Urquhart, *Annals of Operations Research*, 2021).
- Perpetui con leva su **Hyperliquid testnet**, che è paper, con funding carry (BIS WP 1087) e momentum. È il terreno di HyperGrok, ma con soldi finti e con le stesse regole di prova: si apre solo se lo vuoi.
