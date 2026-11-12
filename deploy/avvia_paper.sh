#!/usr/bin/env bash
# Avvia il PAPER di GERVA core su un Mac o su Linux senza Docker: ciclo live sotto supervisore, passi giornalieri, dashboard.
#   bash deploy/avvia_paper.sh            avvia tutto in background (log in var/gerva/log/)
#   bash deploy/avvia_paper.sh stop       ferma tutto
#   bash deploy/avvia_paper.sh stato      dice che cosa gira
# Nessun ordine reale: mode in config/gerva.yaml e' "paper" (registro interno) oppure "alpaca-paper" (conto di prova Alpaca).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"; export GERVA_HOME="${GERVA_HOME:-$ROOT/var/gerva}"; LOG="$GERVA_HOME/log"; PIDS="$GERVA_HOME/pids"
mkdir -p "$LOG" "$PIDS"
PY="$ROOT/.venv/bin/python"

stop() { for f in "$PIDS"/*.pid; do [ -f "$f" ] || continue; kill "$(cat "$f")" 2>/dev/null || true; rm -f "$f"; done; echo "fermato"; }
stato() { for n in runner daily dashboard; do f="$PIDS/$n.pid"; if [ -f "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null; then echo "$n: attivo (pid $(cat "$f"))"; else echo "$n: fermo"; fi; done
          [ -f "$GERVA_HOME/heartbeat" ] && echo "ultimo battito: $(date -r "$GERVA_HOME/heartbeat" 2>/dev/null || stat -c %y "$GERVA_HOME/heartbeat")" || echo "nessun battito ancora"; }
case "${1:-avvia}" in
  stop) stop; exit 0 ;;
  stato) stato; exit 0 ;;
esac

if [ ! -x "$PY" ]; then
  echo "creo l'ambiente Python in .venv ..."; python3 -m venv .venv; "$PY" -m pip install -q --upgrade pip; "$PY" -m pip install -q -r requirements.txt
fi
# Certificati di sicurezza: il Python ufficiale per Mac non li ha e rifiuta ogni collegamento (CERTIFICATE_VERIFY_FAILED).
"$PY" -m pip install -q certifi
export SSL_CERT_FILE="$("$PY" -c 'import certifi; print(certifi.where())')"
export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
[ -f "$ROOT/secrets/gerva.env" ] && { set -a; . "$ROOT/secrets/gerva.env"; set +a; }
echo "controllo del broker (sola lettura) ..."; "$PY" -m gerva check-broker || { echo "il broker non risponde: correggi prima di avviare"; exit 1; }
stop >/dev/null 2>&1 || true
nohup "$PY" -m gerva supervise -- run >> "$LOG/runner.log" 2>&1 & echo $! > "$PIDS/runner.pid"
nohup bash -c "while true; do '$PY' -m gerva daily; '$PY' research/v5/v6/b8_confronto/confronto.py --var-dir '$GERVA_HOME' --csv '$GERVA_HOME/confronto_nav.csv' --legacy-file '$GERVA_HOME/legacy_nav.csv' || true; sleep 3600; done" >> "$LOG/daily.log" 2>&1 & echo $! > "$PIDS/daily.pid"
GERVA_SNAPSHOT="$GERVA_HOME/snapshot.json" nohup "$PY" -m dashboard.server >> "$LOG/dashboard.log" 2>&1 & echo $! > "$PIDS/dashboard.pid"
sleep 2; stato
echo "dashboard: http://127.0.0.1:8787   |   log: $LOG   |   arresto di emergenza: $PY -m gerva kill --reason '...'"
