#!/usr/bin/env bash
# Attiva GERVA Capital sul Mac: la collega al conto PAPER di Trader Workstation (porta 7497)
# e la fa lavorare da sola (battito, ordini delle azioni, crypto dal giorno dopo l'esecuzione delle vendite).
# Si puo' rilanciare quante volte si vuole: non duplica nulla. Solo paper, nessun ordine parte da qui.
set -euo pipefail

BRANCH="claude/gifted-ramanujan-n3a5gg"
FIRM="$HOME/Documents/GERVA-Capital"
Q="$HOME/Documents/GERVA-Q"
PORT=7497
CRYPTO_FROM="2026-11-06 17:00"     # dopo l'apertura USA: le vendite delle azioni sono eseguite e i contanti disponibili

say() { printf '\n== %s\n' "$1"; }
[ -d "$Q" ] || { echo "Non trovo $Q (GERVA-Q). Fermo qui."; exit 1; }

say "1/6 Codice della societa'"
if [ -d "$FIRM/.git" ]; then
  git -C "$FIRM" fetch origin "$BRANCH" && git -C "$FIRM" checkout "$BRANCH" && git -C "$FIRM" pull --ff-only origin "$BRANCH"
else
  git clone -b "$BRANCH" https://github.com/Andrea-Gervasoni/GERVA-Capital "$FIRM"
fi
cd "$FIRM"

say "2/6 Ambiente Python"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt yfinance ib_async
[ -f .env ] || cp .env.example .env
chmod 600 .env

setenv() {  # setenv CHIAVE VALORE: toglie ogni riga vecchia (anche commentata) e scrive quella nuova
  grep -v -E "^[# ]*$1=" .env > .env.tmp || true
  printf '%s=%s\n' "$1" "$2" >> .env.tmp
  mv .env.tmp .env && chmod 600 .env
}

say "3/6 Collegamento al conto paper (TWS, porta $PORT)"
ACCT="$(grep -E '^IBKR_CHALLENGE_ACCOUNT=DU' .env | head -1 | cut -d= -f2 || true)"
if [ -z "$ACCT" ]; then
  read -r -p "Numero del conto paper (inizia con DU, lo trovi in alto in TWS): " ACCT
fi
case "$ACCT" in DU*) ;; *) echo "Il conto deve iniziare con DU (paper). Fermo qui."; exit 1;; esac
setenv GERVA_Q_PATH "$Q"
setenv IBKR_OBSERVE 1
setenv IBKR_GERVAQ_PORT "$PORT"
setenv IBKR_CHALLENGE_ACCOUNT "$ACCT"

say "4/6 Creazione della societa' e prova del collegamento (sola lettura)"
.venv/bin/python firm.py init
.venv/bin/python firm.py ibkr-check

say "5/6 Dati di mercato e prova delle idee (puo' richiedere qualche minuto)"
.venv/bin/python firm.py data || echo "(dati non scaricati ora: li riprovera' il battito)"

say "6/6 Programmazione automatica"
cat > "$Q/run_crypto.sh" <<EOF
#!/usr/bin/env bash
# Crypto ogni 4 ore, ma solo da $CRYPTO_FROM: prima i contanti non bastano (le vendite delle azioni sono ancora in coda).
[ "\$(date '+%Y-%m-%d %H:%M')" \\< "$CRYPTO_FROM" ] && exit 0
cd "$Q" && mkdir -p logs && GERVAQ_IB_PORT=$PORT .venv/bin/python -W ignore crypto_live.py --mode paper >> logs/crypto.log 2>&1
EOF
chmod +x "$Q/run_crypto.sh"
mkdir -p "$Q/logs" "$FIRM/var"
{
  crontab -l 2>/dev/null | grep -v -E "firm.py heartbeat|GERVA-Q.*live.py --mode paper|run_crypto.sh" || true
  echo "*/15 * * * * cd $FIRM && .venv/bin/python firm.py heartbeat >> var/heartbeat.log 2>&1"
  echo "35 22 * * 1-5 cd $Q && mkdir -p logs && GERVAQ_IB_PORT=$PORT .venv/bin/python -W ignore live.py --mode paper >> logs/live.log 2>&1"
  echo "5 1,5,9,13,17,21 * * * $Q/run_crypto.sh"
} | crontab -
crontab -l

cat <<EOF

FATTO. La societa' e' collegata al conto e lavora da sola.
 - Portale:   cd $FIRM && .venv/bin/python firm.py portal     poi apri http://127.0.0.1:8765
 - Azioni:    ogni giorno di borsa alle 22:35
 - Crypto:    ogni 4 ore, da $CRYPTO_FROM
 - Battito:   ogni 15 minuti (controlli, riunioni, report, portafoglio ombra)
Tieni il Mac acceso (senza stop) e Trader Workstation aperta e collegata.
EOF
