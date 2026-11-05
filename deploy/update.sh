#!/usr/bin/env bash
# Aggiornamento sicuro: scarica, ricostruisce, RIESEGUE I TEST nell'immagine nuova; riavvia solo se sono verdi.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
# consigliato: firmare i commit (git config commit.gpgsign true) e attivare REQUIRE_SIGNED=1 sul server
if [ "${REQUIRE_SIGNED:-0}" = "1" ]; then git verify-commit HEAD || { echo "commit non firmato: aggiornamento annullato"; exit 1; }; fi
DC="docker compose -f deploy/docker-compose.yml --env-file deploy/server.env"
$DC build
docker run --rm --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges -e HOME=/tmp --network none --entrypoint python gerva-capital:local -m pytest -q -p no:cacheprovider
$DC up -d
$DC ps
