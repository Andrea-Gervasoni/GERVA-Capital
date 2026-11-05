# Inizia qui: usare GERVA Capital sul serio

Cinque fasi, nell'ordine. Ognuna ha un "fatto quando", e non si passa alla successiva prima.
Tutto è solo **paper**: nessun euro vero è mai in gioco.

## Fase 1: installarla sul Mac e guardarla (oggi, 20 minuti)

Finché il lavoro non è unito al ramo principale, si scarica il ramo di sviluppo:

```bash
cd ~/Documents && git clone -b claude/gifted-ramanujan-n3a5gg https://github.com/Andrea-Gervasoni/GERVA-Capital && cd GERVA-Capital
```

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt yfinance && cp .env.example .env
```

Prova prima il demo (dati finti, non tocca nulla):

```bash
.venv/bin/python firm.py demo && .venv/bin/python firm.py portal --demo
```

Apri http://127.0.0.1:8765 e gira tra le persone e i pannelli. Chiudi con Ctrl+C.

**Fatto quando:** il portale demo si apre e ti è chiaro cosa mostra.

## Fase 2: collegarla a GERVA-Q e ai dati veri (questa settimana)

1. In `.env` controlla che `GERVA_Q_PATH=~/Documents/GERVA-Q` sia la cartella giusta.
2. Con IB Gateway **paper** acceso (quello che già usa GERVA-Q), attiva l'osservatore in sola lettura: in `.env` togli
   il `#` davanti a `IBKR_OBSERVE=1`, `IBKR_GERVAQ_PORT=4002` e `IBKR_CHALLENGE_ACCOUNT=DU...` (il tuo numero DU).
3. Crea la società vera e controlla il collegamento:

```bash
.venv/bin/python firm.py init && .venv/bin/python firm.py ibkr-check
```

4. Scarica i dati reali e lancia il banco che confronta i miglioramenti con la v3:

```bash
.venv/bin/python firm.py data && .venv/bin/python firm.py research gervaq4
```

Il risultato è in `research/gervaq4/`. Può dire "si tiene la v3": è un risultato normale e onesto.

**Fatto quando:** `ibkr-check` mostra il conto mascherato (DU****…) e il report del banco esiste.

## Fase 3: farla lavorare ogni giorno (dalla settimana prossima)

1. Il battito: un controllo ogni 15 minuti.

```bash
(crontab -l 2>/dev/null; echo "*/15 * * * * cd ~/Documents/GERVA-Capital && .venv/bin/python firm.py heartbeat >> var/heartbeat.log 2>&1") | crontab -
```

2. Il portale quando vuoi guardare: `.venv/bin/python firm.py portal` → http://127.0.0.1:8765
3. **Facoltativo:** gli agenti veri. Metti `ANTHROPIC_API_KEY` in `.env`. Spesa massima 0,60 €/giorno, il tetto lo decidi
   tu in Impostazioni. Senza chiave la società gira in simulazione a costo zero.

**Fatto quando:** nel portale il feed "Cosa succede" si muove da solo e la sera arriva il report.

## La tua routine (pochi minuti)

| Quando | Cosa fai | Dove |
|---|---|---|
| Ogni giorno, 2 minuti | Guardi i tre numeri in alto: NAV, rischio (semaforo), audit | portale |
| Ogni giorno | Rispondi alla **Posta**: arrivano solo le decisioni che spettano a te (soldi, rischio, budget, credenziali, azioni fuori dal progetto, direzione) | pannello Posta |
| Ogni sera | Leggi il **Report**: cosa è successo e le correzioni proposte | pannello Report |
| Domenica | Decidi i rilasci per GERVA-Q (si applicano solo la domenica, 9-21 ora italiana) | Posta, poi `firm.py release --apply ID` |
| Ogni mese | Niente: riallocazione del capitale e bonus li fa il codice; li vedi nel report | — |
| Ogni sera, da solo | Il battito aggiorna il **portafoglio ombra** (v4 contro v3 in avanti); lo vedi nel report | report, oppure `firm.py shadow` |
| Dopo un risultato visto online | Lo verifichi prima di crederci | `firm.py check-backtest` |

## Fase 4: il server (quando le fasi 1-3 girano senza sorprese da 2 settimane)

Segui `docs/DEPLOY.md`. Quando GERVA-Q passa sul server, **spegni il suo scheduler sul Mac**.

## Fase 5: dopo 3 mesi, la decisione

La società vale la pena solo se è vera almeno una di queste tre cose. Il criterio è scritto adesso, non dopo:
1. una variante v4 ha battuto la v3 su dati mai visti (report del banco);
2. i pod hanno portato rendimento netto (dopo costi e spesa API) con probabilità alta che sia vero;
3. le sue correzioni hanno evitato un errore o una perdita concreta (report e audit).

Se nessuna è vera: tieni la v3 da sola e la società solo per rischio e report.

## Le regole d'oro

- **Mai** soldi veri senza i cancelli 13-15 della sfida e la firma dei titolari del conto. Il codice lo blocca, ma la
  regola è tua.
- Se qualcosa non ti torna: **KILL** dal pannello Impostazioni. Ferma tutto, poi si guarda con calma.
- Non allargare i limiti di rischio dopo una perdita, né dopo un guadagno.
- Una settimana buona in paper prova che il codice gira, non che la strategia funziona.
