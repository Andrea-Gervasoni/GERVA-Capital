#!/usr/bin/env bash
# Backup giornaliero: DB della societa' (copia coerente con .backup di SQLite) + stato e ledger di GERVA-Q.
# Cifrato in streaming con age verso una chiave PUBBLICA (la privata resta sul tuo Mac): sul disco del server
# non finisce mai una copia in chiaro. Va nel crontab di ROOT (i volumi Docker sono di root):
#   sudo crontab -e  ->  15 4 * * *  AGE_RECIPIENT=age1... /srv/gerva/GERVA-Capital/deploy/backup.sh >> /srv/gerva/backups/backup.log 2>&1
set -euo pipefail
umask 077
[ -n "${AGE_RECIPIENT:-}" ] || [ "${ALLOW_PLAINTEXT_BACKUP:-0}" = "1" ] || {
  echo "manca AGE_RECIPIENT: rifiuto un backup in chiaro (ALLOW_PLAINTEXT_BACKUP=1 per forzare)"; exit 1; }
OUT=/srv/gerva/backups; DAY=$(date -u +%F); TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
install -d -m 700 "$OUT"
VOL=$(docker volume inspect -f '{{ .Mountpoint }}' gerva_firmdata)
sqlite3 "$VOL/var/firm.sqlite" ".backup '$TMP/firm.sqlite'"
sqlite3 "$TMP/firm.sqlite" "PRAGMA integrity_check;" | grep -qx ok || { echo "copia del DB non integra"; exit 1; }
cp "$VOL/var/audit.head" "$TMP/" 2>/dev/null || true          # testa della catena di audit (verifica esterna)
GQ=/srv/gerva/GERVA-Q
for d in state challenge orders; do [ -d "$GQ/$d" ] || echo "attenzione: manca GERVA-Q/$d"; done
tar -C /srv/gerva -czf "$TMP/gervaq_state.tgz" --ignore-failed-read GERVA-Q/state GERVA-Q/challenge GERVA-Q/orders
if [ -n "${AGE_RECIPIENT:-}" ]; then
  tar -C "$TMP" -cz . | age -r "$AGE_RECIPIENT" -o "$OUT/gerva_$DAY.tgz.age"
else
  tar -C "$TMP" -czf "$OUT/gerva_$DAY.tgz" .
fi
find "$OUT" -name 'gerva_*' -mtime +30 -delete
echo "$(date -u +%FT%TZ) backup ok"
