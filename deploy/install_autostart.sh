#!/usr/bin/env bash
# Makes paper trading start by itself on macOS: at login, after a restart, and again within 10 seconds if a part stops.
# It installs three launchd services (live loop under its supervisor, daily steps, terminal) in ~/Library/LaunchAgents,
# the same mechanism the original GERVA Capital uses (deploy/mac/installa_launchd.py in the GERVA-Capital repository).
#   bash deploy/install_autostart.sh            install (or reinstall) and start now
#   bash deploy/install_autostart.sh remove     stop and remove the services (then start by hand with the start script)
#   bash deploy/install_autostart.sh status     show the services
# Paper only: the services run the same commands as the start script; no setting about orders is touched.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"; NAME="$(basename "$ROOT" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9\n' '-')"
PREFIX="com.gerva.${NAME}."
AGENTS="$HOME/Library/LaunchAgents"; UID_="$(id -u)"
HOME_DIR="${GERVA_HOME:-$ROOT/var/gerva}"; LOG="$HOME_DIR/log"; PY="$ROOT/.venv/bin/python"
PORT="${GERVA_DASH_PORT:-8787}"

[ "$(uname)" = "Darwin" ] || { echo "macOS only (on Linux use deploy/gerva.service or Docker)"; exit 1; }

remove() { for s in runner daily dashboard; do p="$AGENTS/${PREFIX}$s.plist"; launchctl bootout "gui/$UID_" "$p" 2>/dev/null || true; rm -f "$p"; done; }
case "${1:-install}" in
  remove|uninstall) remove; echo "autostart removed: start by hand with the start script"; exit 0 ;;
  status) launchctl list | grep -F "$PREFIX" || echo "no autostart service for $ROOT"; exit 0 ;;
esac

[ -x "$PY" ] || { echo "run the start script once first (it creates .venv)"; exit 1; }
"$PY" -m pip install -q certifi
CERT="$("$PY" -c 'import certifi; print(certifi.where())')"
mkdir -p "$AGENTS" "$LOG"
bash deploy/avvia_paper.sh stop >/dev/null 2>&1 || true          # the processes started by hand give way to the services

# every service: bash enters the folder, loads the secrets if any, sets the same variables as the start script
pre="cd '$ROOT' && { [ -f secrets/gerva.env ] && set -a && . secrets/gerva.env && set +a; true; } && export GERVA_HOME='$HOME_DIR' SSL_CERT_FILE='$CERT' REQUESTS_CA_BUNDLE='$CERT' PYTHONUNBUFFERED=1"
# exit code 3 = the loop stopped for KILL: reported as a normal exit, so launchd does NOT restart it
RUNNER="$pre && '$PY' -m gerva supervise -- run >> '$LOG/runner.log' 2>&1; c=\$?; [ \$c -eq 3 ] && exit 0; exit \$c"
DAILY="$pre && while true; do '$PY' -m gerva daily; '$PY' research/v5/v6/b8_confronto/confronto.py --var-dir '$HOME_DIR' --csv '$HOME_DIR/confronto_nav.csv' --legacy-file '$HOME_DIR/legacy_nav.csv' || true; sleep 3600; done >> '$LOG/daily.log' 2>&1"
DASH="$pre && GERVA_DASH_PORT='$PORT' GERVA_SNAPSHOT='$HOME_DIR/snapshot.json' exec '$PY' -m dashboard.server >> '$LOG/dashboard.log' 2>&1"

xml() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }
write() {   # name, command
  cat > "$AGENTS/${PREFIX}$1.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>${PREFIX}$1</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>-c</string><string>$(xml "$2")</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
</dict></plist>
PLIST
  plutil -lint "$AGENTS/${PREFIX}$1.plist" >/dev/null
}
remove
write runner "$RUNNER"; write daily "$DAILY"; write dashboard "$DASH"
for s in runner daily dashboard; do launchctl bootstrap "gui/$UID_" "$AGENTS/${PREFIX}$s.plist"; done
sleep 3; launchctl list | grep -F "$PREFIX" || true
echo "autostart installed: it starts at every login and restarts within 10 s if a part stops"
echo "terminal: http://127.0.0.1:$PORT   |   logs: $LOG   |   remove: bash deploy/install_autostart.sh remove"
