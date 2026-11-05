#!/usr/bin/env bash
# Aggiornamento sicuro: scarica, ricostruisce, RIESEGUE I TEST nell'immagine nuova; riavvia solo se sono verdi.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
docker compose -f deploy/docker-compose.yml build
docker run --rm --read-only --tmpfs /tmp -e HOME=/tmp --entrypoint python gerva-capital:local -m pytest -q -p no:cacheprovider
docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml ps
