#!/usr/bin/env python3
"""
Installa su macOS i programmi di GERVA Capital e di GERVA-Q come servizi launchd (al posto di cron).

Perche': cron su macOS si ferma o perde i permessi, e quando un programma esce (anche di proposito, per ripartire dopo un aggiornamento
del codice) nessuno lo rialza. launchd lo rialza da solo entro 10 secondi, riparte dopo un riavvio del Mac, e recupera le esecuzioni
pianificate che il Mac ha perso mentre dormiva.

Il permesso: macOS protegge Documenti. launchd non puo' entrarci da solo (errore 78, EX_CONFIG), quindi ogni servizio parte con
/bin/bash -c 'cd <cartella> && python ...': e' bash che entra nella cartella, e a /bin/bash si da' UNA volta il permesso
(Impostazioni di Sistema > Privacy e sicurezza > Accesso completo al disco). Lo script lo PROVA prima di toccare qualsiasi cosa:
se manca, spiega come darlo e non cambia niente (i programmi accesi a mano restano accesi).

Cosa fa (si puo' rilanciare quante volte si vuole):
  0. prova il permesso con un servizio di prova; se manca, si ferma qui;
  1. salva la pianificazione di cron e ne toglie le righe di GERVA (firm.py, live.py, caffeinate);
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
import shlex
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
FIRM = os.path.join(HOME, "Documents", "GERVA-Capital")
Q = os.path.join(HOME, "Documents", "GERVA-Q")
PORT = "7497"
PREFIX = "com.gerva."
PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
SONDA_OUT = "/tmp/gerva_sonda.out"


def _py(root: str) -> str:
    return os.path.join(root, ".venv", "bin", "python")


def _shell(wd: str, cmd: list[str], log: str) -> list[str]:
    """bash entra nella cartella e lancia il programma, scrivendo il log li' (launchd non tocca mai Documenti)."""
    line = f"cd {shlex.quote(wd)} && " + " ".join(shlex.quote(c) for c in cmd) + f" >> {shlex.quote(log)} 2>&1"
    return ["/bin/bash", "-c", line]


def services(firm: str = FIRM, q: str = Q) -> dict[str, dict]:
    """nome -> contenuto del plist."""
    env = lambda extra=None: dict({"PATH": PATH, "PYTHONUNBUFFERED": "1"}, **(extra or {}))
    always = lambda label, cmd, wd, log: {                          # sempre acceso: se esce, riparte dopo 10 secondi
        "Label": PREFIX + label, "ProgramArguments": _shell(wd, cmd, log), "RunAtLoad": True, "KeepAlive": True, "ThrottleInterval": 10, "EnvironmentVariables": env()}
    cal = lambda label, cmd, wd, log, hours, minute, extra=None: {  # lun-ven a certi orari; se il Mac dorme parte al risveglio
        "Label": PREFIX + label, "ProgramArguments": _shell(wd, cmd, log), "EnvironmentVariables": env(extra),
        "StartCalendarInterval": [{"Weekday": d, "Hour": h, "Minute": minute} for d in range(1, 6) for h in hours]}
    fp = _py(firm)
    return {
        "telegram": always("telegram", [fp, "-u", "firm.py", "telegram"], firm, os.path.join(firm, "var/telegram.log")),
        "freedesk": always("freedesk", [fp, "-u", "firm.py", "free-desk"], firm, os.path.join(firm, "var/free-desk.log")),
        "livenav": always("livenav", [fp, "-u", "firm.py", "live-nav"], firm, os.path.join(firm, "var/live-nav.log")),
        "portal": always("portal", [fp, "-u", "firm.py", "portal"], firm, os.path.join(firm, "var/portal.log")),
        "caffeinate": {"Label": PREFIX + "caffeinate", "ProgramArguments": ["/usr/bin/caffeinate", "-ims"], "RunAtLoad": True, "KeepAlive": True},
        "heartbeat": {"Label": PREFIX + "heartbeat", "ProgramArguments": _shell(firm, [fp, "firm.py", "heartbeat"], os.path.join(firm, "var/heartbeat.log")),
                      "RunAtLoad": True, "StartInterval": 900, "EnvironmentVariables": env()},
        # GERVA-Q: l'unico che scrive su IBKR. Chiusura 22:35 e in seduta alle 15:45, 17:45, 19:45, 21:45 (senza riscaricare i prezzi)
        "gervaq-chiusura": cal("gervaq-chiusura", [_py(q), "-W", "ignore", "live.py", "--mode", "paper"], q, os.path.join(q, "logs/live.log"), [22], 35, {"GERVAQ_IB_PORT": PORT}),
        "gervaq-seduta": cal("gervaq-seduta", [_py(q), "-W", "ignore", "live.py", "--mode", "paper", "--no-refresh"], q, os.path.join(q, "logs/live-seduta.log"),
                             [15, 17, 19, 21], 45, {"GERVAQ_IB_PORT": PORT}),
    }


def sonda_plist(firm: str = FIRM, q: str = Q) -> dict:
    """Servizio di prova: sotto launchd, con lo stesso meccanismo dei veri, entra in entrambe le cartelle e legge un file con Python. Scrive OK o NO in /tmp."""
    code = "import os,sys; [os.listdir(d) for d in sys.argv[1:]]; open(os.path.join(sys.argv[1],'firm.py')).read(1)"
    line = f"{shlex.quote(_py(firm))} -c {shlex.quote(code)} {shlex.quote(firm)} {shlex.quote(q)} >/dev/null 2>&1 && echo OK > {SONDA_OUT} || echo NO > {SONDA_OUT}"
    return {"Label": PREFIX + "sonda", "ProgramArguments": ["/bin/bash", "-c", line], "RunAtLoad": True}


def _sh(*cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _load(path: str, label: str) -> subprocess.CompletedProcess:
    uid = str(os.getuid())
    _sh("launchctl", "bootout", f"gui/{uid}/{label}")                       # se c'era gia', si ricarica
    r = _sh("launchctl", "bootstrap", f"gui/{uid}", path)
    return r if r.returncode == 0 else _sh("launchctl", "load", "-w", path)  # macOS piu' vecchi


def permission_ok() -> bool:
    """Prova VERA: un servizio launchd con lo stesso meccanismo deve poter leggere le cartelle di GERVA."""
    la = os.path.join(HOME, "Library", "LaunchAgents")
    os.makedirs(la, exist_ok=True)
    if os.path.exists(SONDA_OUT):
        os.remove(SONDA_OUT)
    p = sonda_plist()
    path = os.path.join(la, p["Label"] + ".plist")
    with open(path, "wb") as f:
        plistlib.dump(p, f)
    _load(path, p["Label"])
    ok = None
    for _ in range(16):
        time.sleep(0.5)
        if os.path.exists(SONDA_OUT):
            ok = open(SONDA_OUT).read().strip() == "OK"
            break
    _sh("launchctl", "bootout", f"gui/{os.getuid()}/{p['Label']}")
    os.remove(path)
    return bool(ok)


COME_SI_DA = """
MANCA UN PERMESSO (una volta sola). macOS protegge la cartella Documenti e i servizi non ci possono entrare.
Non ho cambiato niente: i tuoi programmi accesi a mano restano accesi.

  1. Apri  Impostazioni di Sistema  >  Privacy e sicurezza  >  Accesso completo al disco
  2. Clicca il pulsante  +  (chiede la password o Touch ID)
  3. Nella finestra di scelta premi  Maiusc + Comando + G  e scrivi:   /bin/bash    poi Invio, poi Apri
  4. Controlla che  bash  sia nell'elenco e con l'interruttore ACCESO
  5. Rilancia lo stesso comando:   python3 deploy/mac/installa_launchd.py
"""


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
    if not dest:
        for root, sub in ((FIRM, "var"), (Q, "logs")):                       # le cartelle dei log devono esistere
            os.makedirs(os.path.join(root, sub), exist_ok=True)
    for plist in services().values():
        path = os.path.join(la, plist["Label"] + ".plist")
        with open(path, "wb") as f:
            plistlib.dump(plist, f)
        if dest:
            continue
        r = _load(path, plist["Label"])
        print(f"  {'ok ' if r.returncode == 0 else 'ERRORE'} {plist['Label']}" + ("" if r.returncode == 0 else f"  {r.stderr.strip()[:120]}"))


def remove() -> None:
    uid = str(os.getuid())
    for plist in list(services().values()) + [sonda_plist()]:
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
    print("Provo il permesso di accesso alle cartelle di GERVA...")
    if not permission_ok():
        print(COME_SI_DA)
        raise SystemExit(2)
    print("Permesso ok.")
    clean_cron()
    stop_manual()
    print("servizi launchd:")
    install()
    time.sleep(5)
    out = _sh("launchctl", "list").stdout
    print("\nIn esecuzione (PID, ultimo codice di uscita, nome; 0 = ok):")
    print("\n".join(l for l in out.splitlines() if PREFIX in l) or "(nessuno: qualcosa non e' andato)")
    print("\nFatto. Da ora un programma che si ferma riparte da solo entro pochi secondi, anche dopo uno stop del Mac.")


if __name__ == "__main__":
    main(sys.argv[1:])
