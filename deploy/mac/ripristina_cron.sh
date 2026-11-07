#!/bin/bash
# Rimette la pianificazione automatica del Mac (cron), SENZA le crypto (il conto paper non le compra).
# Sicuro da rilanciare: sostituisce la pianificazione con quella corretta e ne salva una copia.
set -e
Q="$HOME/Documents/GERVA-Q"
FIRM="$HOME/Documents/GERVA-Capital"
PORT=7497
mkdir -p "$FIRM/var" "$Q/logs"
crontab -l > "$FIRM/var/crontab.prima.$(date +%Y%m%d-%H%M%S)" 2>/dev/null || true
{
  echo "*/15 * * * * cd $FIRM && .venv/bin/python firm.py heartbeat >> var/heartbeat.log 2>&1"
  echo "35 22 * * 1-5 cd $Q && mkdir -p logs && GERVAQ_IB_PORT=$PORT .venv/bin/python -W ignore live.py --mode paper >> logs/live.log 2>&1"
  # in seduta (15:30-22:00 ora italiana): stesso esecutore, senza riscaricare i prezzi (--no-refresh): il modello resta quello dell'ultima chiusura,
  # entrano subito desk, rate del lungo periodo e leva gestita; gli ordini ancora in coda non si ripetono.
  echo "45 15,17,19,21 * * 1-5 cd $Q && mkdir -p logs && GERVAQ_IB_PORT=$PORT .venv/bin/python -W ignore live.py --mode paper --no-refresh >> logs/live-seduta.log 2>&1"
  # il Mac non va in stop quando e' collegato alla corrente (la rete che cade fermava Telegram, IBKR e le crypto); a coperchio chiuso dorme comunque
  echo "* * * * * pgrep -x caffeinate >/dev/null || (nohup /usr/bin/caffeinate -ims >/dev/null 2>&1 &)"
  echo "* * * * * pgrep -f 'firm.py [t]elegram' >/dev/null || (cd $FIRM && nohup .venv/bin/python -u firm.py telegram >> var/telegram.log 2>&1 &)"
  echo "* * * * * pgrep -f 'firm.py free-[d]esk' >/dev/null || (cd $FIRM && nohup .venv/bin/python -u firm.py free-desk >> var/free-desk.log 2>&1 &)"
  echo "* * * * * pgrep -f 'firm.py live-[n]av' >/dev/null || (cd $FIRM && nohup .venv/bin/python -u firm.py live-nav >> var/live-nav.log 2>&1 &)"
} | crontab -
echo "Pianificazione ripristinata:"
crontab -l
