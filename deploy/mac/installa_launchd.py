#!/usr/bin/env python3
"""
Installa su macOS i programmi di GERVA Capital e di GERVA-Q come servizi launchd (al posto di cron).

Perche': cron su macOS si ferma o perde i permessi, e quando un programma esce (anche di proposito, per ripartire dopo un aggiornamento
del codice) nessuno lo rialza. launchd lo rialza da solo entro 10 secondi, riparte dopo un riavvio del Mac, e recupera le esecuzioni
pianificate che il Mac ha perso mentre dormiva.

Cosa fa (si puo' rilanciare quante volte si vuole):
  1. salva la pianificazione di cron e ne toglie le righe di GERVA (firm.py, live.py, caffeinate), per non far partire due volte lo stesso programma;
  2. ferma i programmi gia' accesi a mano;
  3. scrive i servizi in ~/Library/LaunchAgents e li avvia.
Solo paper: GERVA-Q ha GERVAQ_IB_PORT=7497 (conto paper di Trader Workstation). Nessun ordine parte da qui.

Uso:  python3 deploy/mac/installa_launchd.py          (installa)
      python3 deploy/mac/installa_launchd.py --togli   (li toglie tutti)
      python3 deploy/mac/installa_launchd.py --prova DIR  (scrive i file in DIR senza toccare il sistema)
"""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
FIRM = os.path.join(HOME, "Documents", "GERVA-Capital")
Q = os.path.join(HOME, "Documents", "GERVA-Q")
PORT = "7497"
PREFIX = "com.gerva."
PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def _py(root: str) -> str:
    return os.path.join(root, ".venv", "bin", "python")


def services(firm: str = FIRM, q: str = Q) -> dict[str, dict]:
    """label -> contenuto del plist."""
    log = lambda root, name: os.path.join(root, name)
    always = lambda label, args, wd, out: {                      # sempre acceso: se esce, riparte
        "Label": PREFIX + label, "ProgramArguments": args, "WorkingDirectory": wd, "RunAtLoad": True, "KeepAlive": True, "ThrottleInterval": 10,
        "StandardOutPath": out, "StandardErrorPath": out, "EnvironmentVariables": {"PATH": PATH, "PYTHONUNBUFFERED": "1"}}
    cal = lambda label, args, wd, out, hours, minute, env=None: {   # lun-ven a certi orari; se il Mac dorme parte al risveglio
        "Label": PREFIX + label, "ProgramArguments": args, "WorkingDirectory": wd, "StandardOutPath": out, "StandardErrorPath": out,
        "StartCalendarInterval": [{"Weekday": d, "Hour": h, "Minute": minute} for d in range(1, 6) for h in hours],
        "EnvironmentVariables": dict({"PATH": PATH, "PYTHONUNBUFFERED": "1"}, **(env or {}))}
    fp = _py(firm)
    return {
        "telegram": always("telegram", [fp, "-u", "firm.py", "telegram"], firm, log(firm, "var/telegram.log")),
        "freedesk": always("freedesk", [fp, "-u", "firm.py", "free-desk"], firm, log(firm, "var/free-desk.log")),
        "livenav": always("livenav", [fp, "-u", "firm.py", "live-nav"], firm, log(firm, "var/live-nav.log")),
        "portal": always("portal", [fp, "-u", "firm.py", "portal"], firm, log(firm, "var/portal.log")),
        "caffeinate": {"Label": PREFIX + "caffeinate", "ProgramArguments": ["/usr/bin/caffeinate", "-ims"], "RunAtLoad": True, "KeepAlive": True},
        "heartbeat": {"Label": PREFIX + "heartbeat", "ProgramArguments": [fp, "firm.py", "heartbeat"], "WorkingDirectory": firm, "RunAtLoad": True,
                      "StartInterval": 900, "StandardOutPath": log(firm, "var/heartbeat.log"), "StandardErrorPath": log(firm, "var/heartbeat.log"),
                      "EnvironmentVariables": {"PATH": PATH, "PYTHONUNBUFFERED": "1"}},
        # GERVA-Q: l'unico che scrive su IBKR. Chiusura 22:35 e in seduta alle 15:45, 17:45, 19:45, 21:45 (senza riscaricare i prezzi)
        "gervaq-chiusura": cal("gervaq-chiusura", [_py(q), "-W", "ignore", "live.py", "--mode", "paper"], q, log(q, "logs/live.log"), [22], 35, {"GERVAQ_IB_PORT": PORT}),
        "gervaq-seduta": cal("gervaq-seduta", [_py(q), "-W", "ignore", "live.py", "--mode", "paper", "--no-refresh"], q, log(q, "logs/live-seduta.log"), [15, 17, 19, 21], 45,
                             {"GERVAQ_IB_PORT": PORT}),
    }


def _sh(*cmd: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def clean_cron() -> None:
    cur = _sh("crontab", "-l")
    if cur.returncode != 0:
        return
    stamp = time.strftime("%Y%m%d-%H%M%S")
    os.makedirs(os.path.join(FIRM, "var"), exist_ok=True)
    open(os.path.join(FIRM, "var", f"crontab.prima-launchd.{stamp}"), "w").write(cur.stdout)
    keep = [l for l in cur.stdout.splitlines() if not any(k in l for k in ("firm.py", "live.py", "caffeinate"))]
    if keep:
        subprocess.run(["crontab", "-"], input="\n".join(keep) + "\n", text=True)
    else:
        _sh("crontab", "-r")
    print("cron: righe di GERVA tolte (copia salvata in var/crontab.prima-launchd.*)")


def stop_manual() -> None:
    for pat in ("firm.py [t]elegram", "firm.py free-[d]esk", "firm.py live-[n]av", "firm.py [p]ortal", "firm.py [h]eartbeat"):
        _sh("pkill", "-f", pat)
    time.sleep(2)


def install(dest: str | None = None) -> None:
    la = dest or os.path.join(HOME, "Library", "LaunchAgents")
    os.makedirs(la, exist_ok=True)
    uid = str(os.getuid())
    for name, plist in services().items():
        for root in (FIRM, Q):                                              # le cartelle dei log devono esistere
            os.makedirs(os.path.join(root, "var" if root == FIRM else "logs"), exist_ok=True)
        path = os.path.join(la, plist["Label"] + ".plist")
        with open(path, "wb") as f:
            plistlib.dump(plist, f)
        if dest:
            continue
        _sh("launchctl", "bootout", f"gui/{uid}/{plist['Label']}")           # se c'era gia', si ricarica
        r = _sh("launchctl", "bootstrap", f"gui/{uid}", path)
        if r.returncode != 0:
            r = _sh("launchctl", "load", "-w", path)                           # macOS piu' vecchi
        print(f"  {'ok ' if r.returncode == 0 else 'ERRORE'} {plist['Label']}" + ("" if r.returncode == 0 else f"  {r.stderr.strip()[:120]}"))


def remove() -> None:
    uid = str(os.getuid())
    for plist in services().values():
        path = os.path.join(HOME, "Library", "LaunchAgents", plist["Label"] + ".plist")
        _sh("launchctl", "bootout", f"gui/{uid}/{plist['Label']}")
        if os.path.exists(path):
            os.remove(path)
    print("servizi GERVA tolti")


def main(argv: list[str]) -> None:
    if "--togli" in argv:
        return remove()
    if "--prova" in argv:
        d = argv[argv.index("--prova") + 1]
        install(dest=d)
        print(f"scritti {len(services())} servizi in {d} (nessuna modifica al sistema)")
        return
    if sys.platform != "darwin":
        raise SystemExit("questo script e' per macOS")
    for need in (FIRM, Q):
        if not os.path.isdir(need):
            raise SystemExit(f"non trovo {need}")
    clean_cron()
    stop_manual()
    print("servizi launchd:")
    install()
    time.sleep(4)
    out = _sh("launchctl", "list").stdout
    print("\nIn esecuzione:")
    print("\n".join(l for l in out.splitlines() if PREFIX in l) or "(nessuno: qualcosa non e' andato)")
    print("\nFatto. Da ora un programma che si ferma riparte da solo entro pochi secondi, anche dopo uno stop del Mac.")


if __name__ == "__main__":
    main(sys.argv[1:])
