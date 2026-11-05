#!/bin/sh
# Prepara il volume di stato (una sola volta) e avvia il comando. Nessun segreto passa da qui.
set -eu
umask 077
VAR="${GERVA_VAR:-/data/var}"
mkdir -p "$VAR" "$VAR/reports" "${GERVA_RESEARCH:-/data/research}"
# profili degli agenti e limiti di rischio: copie scrivibili nel volume (il codice resta in sola lettura)
if [ -n "${GERVA_AGENTS:-}" ] && [ ! -d "$GERVA_AGENTS" ]; then cp -r /app/agents "$GERVA_AGENTS"; chmod -R u+w "$GERVA_AGENTS"; fi
if [ -n "${GERVA_RISK_FILE:-}" ] && [ ! -f "$GERVA_RISK_FILE" ]; then cp /app/config/risk_limits.yaml "$GERVA_RISK_FILE"; chmod 600 "$GERVA_RISK_FILE"; fi
if [ -n "${GERVA_RESEARCH:-}" ] && [ ! -d "$GERVA_RESEARCH/releases" ]; then cp -r /app/research/. "$GERVA_RESEARCH/"; chmod -R u+w "$GERVA_RESEARCH"; fi
cd /app
if [ ! -f "$VAR/firm.sqlite" ] && [ "${1:-}" = "python" ] && [ "${2:-}" = "firm.py" ]; then python firm.py init; fi
exec "$@"
