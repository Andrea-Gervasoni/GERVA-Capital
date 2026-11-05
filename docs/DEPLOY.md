# GERVA Capital su un server — guida completa (solo PAPER)

> Obiettivo: far girare GERVA-Q e la società 24 ore su 24 su un server che non è il tuo Mac, collegati a
> IBKR **paper**, senza aprire nessuna porta su internet oltre a SSH. Il portale lo apri dal tuo computer
> con un tunnel SSH; per il resto del mondo non esiste.

Tempo richiesto: circa 45 minuti la prima volta. Costo: un piccolo VPS (vedi §9, prezzi da verificare).

---

## 0. Il modello di sicurezza in una pagina

| Strato | Cosa lo protegge | Dove |
|---|---|---|
| Rete | `ufw`: entra solo SSH (con limite di frequenza). Tutte le porte dei container sono pubblicate **solo su 127.0.0.1**: Docker scavalca `ufw`, perciò nel compose non c'è mai una porta su `0.0.0.0`. | `deploy/server_setup.sh`, `deploy/docker-compose.yml` |
| SSH | Solo chiavi, niente root, niente password, un solo utente ammesso (`AllowUsers`), solo tunnel *locali*, `fail2ban`. | `server_setup.sh` |
| Portale | Raggiungibile solo dal tunnel. Password obbligatoria fuori da 127.0.0.1 (il portale **rifiuta di partire** senza `PORTAL_PASSWORD_HASH`), hash scrypt, cookie di sessione firmato HMAC (`HttpOnly`, `SameSite=Strict`, 12 ore), 5 tentativi ogni 5 minuti, controllo dell'header `Host` contro il DNS rebinding, lista delle reti client, CSP senza `unsafe-inline`, `X-Frame-Options: DENY`, nessun header `Server`. | `portal/app.py` |
| Container | Utente non root (uid 10001), filesystem in sola lettura, `cap_drop: ALL`, `no-new-privileges`, limiti di memoria e processi, log a rotazione. Lo stato sta solo nel volume `gerva_firmdata` (permessi 700/600). | `deploy/Dockerfile`, compose |
| Rete interna | Gateway IBKR ↔ società sulla rete `ibnet`, marcata `internal` (nessuna uscita su internet). Il portale sta su una rete a parte e **non** può parlare con IB Gateway. | compose |
| Broker | Solo conti `DU…` (paper). Il conto della sfida è osservato in **sola lettura** (`readonly=True`). I pod possono eseguire solo su un **secondo** conto paper distinto; l'esecutore rifiuta se il conto manca, non è DU, coincide con quello della sfida o se il gateway vede anche quello della sfida. | `firm/ibkr.py` |
| Segreti | Solo in `secrets/*.env` sul server (permessi 600, esclusi da git e dall'immagine). Mai nei log (`llm/redact.py`), mai nel DB in chiaro (numero di conto mascherato `DU****999`), mai nei prompt. | `.gitignore`, `.dockerignore` |
| Aggiornamenti | `update.sh`: `git pull --ff-only`, build, **test dentro l'immagine nuova senza rete**, riavvio solo se verdi. Aggiornamenti di sicurezza del sistema automatici. | `deploy/update.sh` |
| Backup | Ogni notte copia coerente del DB (`sqlite3 .backup`) + stato di GERVA-Q, cifrata con `age` verso una chiave che resta sul tuo computer, 30 giorni. | `deploy/backup.sh` |

**Perché i pod non usano il conto della sfida.** `live.py` e `crypto_live.py` di GERVA-Q vendono ogni posizione
che non è nel loro target. Un ordine di un pod sullo stesso conto verrebbe liquidato la sera stessa e
falserebbe il track record della sfida (REGOLE_SFIDA §1). Quindi: GERVA-Q ha il suo conto, i pod un altro.
Senza il secondo conto i pod restano sul broker simulato (default sicuro) e la società lo chiede nella
mailbox come grande richiesta n. 4 (credenziali).

---

## 1. Creare il server

1. Un VPS **Ubuntu 24.04 LTS**, almeno 2 vCPU, 4 GB di RAM (IB Gateway è Java: ~1–1,5 GB per istanza), 40 GB di disco, in UE.
2. Alla creazione incolla la tua chiave SSH **pubblica** (sul Mac: `cat ~/.ssh/id_ed25519.pub`; se non l'hai: `ssh-keygen -t ed25519`).
3. Non aprire porte nel pannello del provider oltre alla 22. Se il provider ha un firewall di rete, lascia solo TCP 22 in ingresso.

## 2. Indurire il server (una volta)

Dal tuo Mac:

```bash
scp deploy/server_setup.sh root@IP_DEL_SERVER:/root/
```

```bash
ssh root@IP_DEL_SERVER 'less /root/server_setup.sh && bash /root/server_setup.sh'
```

Lo script crea l'utente `gerva` con la tua stessa chiave, chiude root e password, attiva `ufw` e `fail2ban`,
gli aggiornamenti automatici (riavvio alle 04:30 se serve, fuori dagli orari di GERVA-Q), l'orologio
sincronizzato, Docker dal repository ufficiale con impostazioni prudenti.

**Prima di chiudere la sessione di root**, da un secondo terminale verifica che entri come `gerva`:

```bash
ssh gerva@IP_DEL_SERVER
```

Comodo sul Mac, in `~/.ssh/config`:

```
Host gerva
  HostName IP_DEL_SERVER
  User gerva
  IdentityFile ~/.ssh/id_ed25519
  LocalForward 8765 127.0.0.1:8765
  ServerAliveInterval 60
```

Da qui in avanti `ssh gerva` apre anche il tunnel del portale.

## 3. Codice e GERVA-Q sul server

```bash
ssh gerva 'cd /srv/gerva && git clone https://github.com/Andrea-Gervasoni/GERVA-Capital'
```

GERVA-Q **non** è nel repository pubblico: copialo dal Mac (stato e ledger compresi, così la sfida continua):

```bash
rsync -a --exclude '.venv' --exclude '__pycache__' ~/Documents/GERVA-Q/ gerva:/srv/gerva/GERVA-Q/
```

> Importante: da quando GERVA-Q gira sul server, **spegni lo scheduler sul Mac** (cron/launchd di `run_daily.sh`
> e `crypto_live.py`). Due motori sullo stesso conto paper si rincorrerebbero.

Il container gira con uid 10001: dai a quell'utente la cartella di GERVA-Q.

```bash
ssh gerva 'sudo chown -R 10001:10001 /srv/gerva/GERVA-Q && sudo chmod -R u+rwX,go-rwx /srv/gerva/GERVA-Q'
```

## 4. I segreti (solo sul server, mai in git)

```bash
ssh gerva
```

```bash
cd /srv/gerva/GERVA-Capital && install -d -m 700 secrets && cp deploy/secrets.example/*.env secrets/ && chmod 600 secrets/*.env && cp deploy/server.env.example deploy/server.env
```

Poi compila con `nano`:

- `secrets/ibgw-gervaq.env` — `TWS_USERID` / `TWS_PASSWORD` del **login paper** della sfida. Nel Client Portal di IBKR il conto paper ha un nome utente proprio, diverso da quello del conto reale: usa quello. `VNC_SERVER_PASSWORD` serve solo se devi completare una 2FA a mano (§6).
- `secrets/firm.env` — `ANTHROPIC_API_KEY`; `IBKR_CHALLENGE_ACCOUNT=DU…` (serve all'esecutore per **rifiutarsi** di operarci); lascia vuoto `IBKR_FIRM_ACCOUNT` finché non hai il secondo conto.
- `secrets/portal.env` — l'hash della password del portale. Generalo così (la password non viene salvata da nessuna parte):

```bash
cd /srv/gerva/GERVA-Capital && docker compose -f deploy/docker-compose.yml --env-file deploy/server.env build gervaq && docker run --rm -it --entrypoint python gerva-capital:local firm.py set-password
```

  Copia la riga `PORTAL_PASSWORD_HASH=scrypt$…` in `secrets/portal.env`. Almeno 12 caratteri; meglio una frase lunga.

## 5. Avvio

```bash
cd /srv/gerva/GERVA-Capital && docker compose -f deploy/docker-compose.yml --env-file deploy/server.env up -d --build
```

Controlli:

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/server.env ps
```

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/server.env logs --tail 50 ibgw-gervaq heartbeat
```

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/server.env exec heartbeat python firm.py ibkr-check
```

`ibkr-check` dice se il gateway risponde, se il conto è DU e mostra solo il numero mascherato.

**Fissa la versione di IB Gateway** (difesa da un'immagine compromessa o da un aggiornamento che rompe):

```bash
docker inspect --format '{{index .RepoDigests 0}}' ghcr.io/gnzsnz/ib-gateway:stable
```

Metti il risultato (`ghcr.io/gnzsnz/ib-gateway@sha256:…`) in `deploy/server.env` alla voce `IBGW_IMAGE`.

## 6. Aprire il portale dal tuo computer

```bash
ssh -N -L 8765:127.0.0.1:8765 gerva
```

Poi nel browser: **http://127.0.0.1:8765** → pagina di accesso → password. Chiudendo il terminale il tunnel
si chiude e il portale torna irraggiungibile.

Usa esattamente `127.0.0.1:8765` (o `localhost:8765`): il portale controlla l'header `Host` e rifiuta gli altri
nomi, è la difesa dal DNS rebinding. Se ti serve un altro nome, aggiungilo a `PORTAL_ALLOWED_HOSTS` in
`secrets/portal.env`.

**2FA di IBKR.** Il conto paper di norma non la chiede a ogni accesso; se la chiede, apri il VNC del gateway
dentro un tunnel, mai esposto:

```bash
ssh -N -L 5901:127.0.0.1:5901 gerva
```

e collegati con un client VNC a `127.0.0.1:5901` (password `VNC_SERVER_PASSWORD`). `AUTO_RESTART_TIME` fa
ripartire il gateway ogni notte senza nuova 2FA per circa una settimana; IBKR richiede comunque un nuovo
login completo periodicamente.

## 7. Secondo conto paper per i pod (facoltativo)

1. Nel Client Portal di IBKR crea un ulteriore conto paper (o un utente paper separato) **diverso** da quello della sfida.
2. Compila `secrets/ibgw-firm.env` con il suo login e in `secrets/firm.env` metti `IBKR_FIRM_ACCOUNT=DU…` e `GATEWAY_BROKER=ibkr_paper`.
3. Avvia anche il suo gateway:

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/server.env --profile pods-ibkr up -d
```

L'esecutore (`IBKRPaperBroker`) all'avvio rifiuta: conto non DU, conto uguale a quello della sfida, gateway
che vede anche il conto della sfida. Gli ordini sono **limite** (mai a mercato) a ± metà della deviazione
massima ammessa, quantità intere per gli ETF, IOC per le crypto, `orderRef` con prefisso `GERVA-CAP-` per
l'idempotenza, residui annullati dopo 30 s, ripartizione pro quota dei parziali. Con il file `KILL` gli ordini
aperti dei pod vengono annullati a ogni battito. Ogni sera alle 21 la società riconcilia le posizioni
del broker con quelle del registro e alza un'allerta se divergono.

## 8. Esercizio quotidiano

Aggiornare (test obbligatori prima del riavvio):

```bash
/srv/gerva/GERVA-Capital/deploy/update.sh
```

Backup notturno (crontab di **root**, perché il volume Docker è di root):

```bash
sudo crontab -e
```

```
15 4 * * * AGE_RECIPIENT=age1... /srv/gerva/GERVA-Capital/deploy/backup.sh >> /srv/gerva/backups/backup.log 2>&1
```

La chiave privata `age` (`age-keygen -o ~/.gerva-backup.key`) resta **sul Mac**; sul server metti solo la
pubblica (`age1…`). Scaricare l'ultimo backup:

```bash
rsync -a gerva:/srv/gerva/backups/ ~/GERVA-backups/
```

Fermare tutto subito. Ci sono due interruttori, uno per motore, e conviene usarli insieme:

- `GERVA-Q/KILL`: `live.py` e `crypto_live.py` annullano gli ordini aperti e non ne inviano altri;
- il KILL della società (`/data/var/KILL` nel volume): il motore di rischio ferma i pod e, con il secondo conto, annulla i loro ordini aperti. Dal portale c'è il pulsante KILL; da terminale:

```bash
ssh gerva 'sudo -u "#10001" touch /srv/gerva/GERVA-Q/KILL && cd /srv/gerva/GERVA-Capital && docker compose -f deploy/docker-compose.yml --env-file deploy/server.env exec heartbeat touch /data/var/KILL'
```

Spegnere anche i container (lo stato resta nel volume):

```bash
ssh gerva 'cd /srv/gerva/GERVA-Capital && docker compose -f deploy/docker-compose.yml --env-file deploy/server.env stop gervaq heartbeat'
```

## 9. Quale server (da verificare)

Qualsiasi VPS con Ubuntu 24.04 e almeno 4 GB di RAM va bene; la latenza verso IBKR è irrilevante per una
strategia giornaliera. Esempi in UE: Hetzner Cloud (Germania/Finlandia), OVHcloud, Scaleway, Contabo.
I prezzi indicativi stanno sui 5–15 €/mese, ma cambiano spesso: **verificali sul sito del provider prima di
scegliere**. È una spesa nuova, cioè una tua decisione (grande richiesta n. 4); la società non ne attiva nessuna.

## 10. Cose verificate e cose da verificare

Verificato in questa sessione:

- immagine costruita e **94 test verdi dentro il container** non root, con filesystem in sola lettura e senza capability;
- portale nel container:
  - senza password rifiuta di partire;
  - con password: `/` → 303 al login, `/api/state` → 401, Host estraneo → 403, cookie falsificato → 401, login → cookie `HttpOnly; SameSite=Strict`;
  - il sesto tentativo errato → 429, senza bloccare le altre richieste;
  - header di sicurezza presenti, nessun header `Server`;
  - file di stato 600 e cartelle 700 di proprietà dell'uid 10001;
- `docker compose config` valido; tutte le porte pubblicate solo su 127.0.0.1;
- porte dell'immagine `gnzsnz/ib-gateway` dal suo README: API paper interna 4002, rilanciata da `socat` su 4004 per gli altri container; VNC 5900; variabili `TWS_USERID`, `TWS_PASSWORD` (anche `TWS_PASSWORD_FILE`), `TRADING_MODE`, `READ_ONLY_API`, `TWOFA_TIMEOUT_ACTION`, `RELOGIN_AFTER_TWOFA_TIMEOUT`, `AUTO_RESTART_TIME`, `TIME_ZONE`, `VNC_SERVER_PASSWORD`.

Non verificabile da qui (nessun conto IBKR in questa sessione):

- il login reale di IB Gateway e la 2FA;
- i nomi esatti delle linee UCITS su IBKR (`config/instruments.yaml`: borsa e valuta di CSPX, CNDX, …): controlla con `ibkr-check` e, se un contratto non si qualifica, correggi la riga;
- i prezzi in pence (GBX) delle linee di Londra;
- le regole IBKR sugli ordini crypto per il conto paper.

Il primo giorno guarda i log di `heartbeat` e la scheda IBKR del portale.
