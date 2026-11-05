#!/usr/bin/env bash
# Backup giornaliero: DB della societa' (copia coerente con .backup di SQLite) + stato e ledger di GERVA-Q.
# Cifrato con age se AGE_RECIPIENT e' impostato (consigliato: la chiave privata resta sul tuo computer).
#   crontab -e  ->  15 4 * * *  /srv/gerva/GERVA-Capital/deploy/backup.sh >> /srv/gerva/backups/backup.log 2>&1
set -euo pipefail
umask 077
OUT=/srv/gerva/backups; DAY=$(date -u +%F); TMP=$(mktemp -d)
VOL=$(docker volume inspect -f '{{ .Mountpoint }}' gerva_firmdata)
sqlite3 "$VOL/var/firm.sqlite" ".backup '$TMP/firm.sqlite'"
tar -C /srv/gerva -czf "$TMP/gervaq_state.tgz" GERVA-Q/state GERVA-Q/challenge GERVA-Q/orders 2>/dev/null || true
tar -C "$TMP" -czf "$OUT/gerva_$DAY.tgz" .
if [ -n "${AGE_RECIPIENT:-}" ]; then age -r "$AGE_RECIPIENT" -o "$OUT/gerva_$DAY.tgz.age" "$OUT/gerva_$DAY.tgz" && rm "$OUT/gerva_$DAY.tgz"; fi
rm -rf "$TMP"
find "$OUT" -name 'gerva_*' -mtime +30 -delete
echo "$(date -u +%FT%TZ) backup ok"
