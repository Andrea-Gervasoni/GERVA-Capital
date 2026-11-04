"""
Finestra di rilascio (regola inviolabile 4; REGOLE_SFIDA regola 7).

Il codice di produzione di GERVA-Q cambia SOLO nella finestra (default: domenica, impostazione
release.weekday). Un rilascio e' una cartella research/releases/AAAA-MM-GG/ con:
  *.patch       diff unificati applicabili con `patch -p1` nella radice di GERVA-Q
  RELEASE.md    cosa cambia, perche', test, effetto atteso sui numeri
apply():
  1. verifica la finestra e la capability di Andrea (modificare file fuori dal progetto e' una
     grande richiesta n.5: senza la sua scelta vale il default sicuro, cioe' nessuna modifica);
  2. prova le patch a secco; se una fallisce non applica nulla;
  3. salva una copia completa dei file toccati in GERVA-Q/backups/<data>/;
  4. applica, scrive da sola la voce nel changelog di REGOLE_SFIDA.md e registra tutto nell'audit.
"""
from __future__ import annotations

import datetime as dt
import glob
import os
import shutil
import subprocess

from . import db, events, audit, mailbox, paths
from . import settings as S

RELEASES = os.path.join(paths.RESEARCH, "releases")


def in_window(now: dt.datetime | None = None) -> bool:
    now = now or dt.datetime.now(dt.timezone.utc)
    return (now.weekday() == int(S.get("release.weekday"))
            and int(S.get("release.start_hour_utc")) <= now.hour < int(S.get("release.end_hour_utc")))


def pending() -> list[dict]:
    out = []
    for d in sorted(glob.glob(os.path.join(RELEASES, "*"))):
        if os.path.isdir(d) and not os.path.exists(os.path.join(d, "APPLIED")):
            out.append(dict(id=os.path.basename(d), patches=sorted(glob.glob(os.path.join(d, "*.patch"))),
                            note=open(os.path.join(d, "RELEASE.md")).read() if os.path.exists(os.path.join(d, "RELEASE.md")) else ""))
    return out


def request_permission(rel: dict):
    return mailbox.big_request(
        5, f"Rilascio GERVA-Q {rel['id']}: applicare le correzioni dell'audit?",
        "Le patch modificano file nella cartella di GERVA-Q (fuori da questo progetto). Correggono il DSR della v3 "
        "calcolato su Sharpe inventati (R1), la cache dei prezzi mai riusata (R2), l'approvazione live crypto statica (R5) "
        "e i pesi non scalati del primo anno di S1 (R9). Dettagli in research/releases/" + rel["id"] + "/RELEASE.md.",
        ["Applicare domenica nella finestra di rilascio", "Non applicare: restano proposte"],
        "Applicare: nessuna cambia i segnali correnti di trading; R1 rende il DSR verificabile, R5 chiude un varco per i soldi veri",
        "Nessuna modifica a GERVA-Q: le correzioni restano proposte documentate",
        dedup_key=f"release-{rel['id']}")


def apply(release_id: str, cap: S.AndreaCapability, now: dt.datetime | None = None, gerva_q: str | None = None) -> dict:
    if not isinstance(cap, S.AndreaCapability):
        raise PermissionError("modificare GERVA-Q richiede la scelta di Andrea (grande richiesta n.5)")
    if not in_window(now):
        return dict(ok=False, motivo="fuori dalla finestra di rilascio")
    root = gerva_q or paths.GERVA_Q
    rel = os.path.join(RELEASES, release_id)
    patches = sorted(glob.glob(os.path.join(rel, "*.patch")))
    for p in patches:
        r = subprocess.run(["patch", "-p1", "--dry-run", "-i", p], cwd=root, capture_output=True, text=True)
        if r.returncode != 0:
            return dict(ok=False, motivo=f"patch non applicabile: {os.path.basename(p)}", dettaglio=r.stdout[-500:])
    stamp = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%d")
    backup = os.path.join(root, "backups", f"pre-{release_id}")
    os.makedirs(backup, exist_ok=True)
    for f in glob.glob(os.path.join(root, "*.py")) + [os.path.join(root, "REGOLE_SFIDA.md")]:
        if os.path.exists(f):
            shutil.copy2(f, backup)
    for p in patches:
        subprocess.run(["patch", "-p1", "-i", p], cwd=root, check=True, capture_output=True)
    note = open(os.path.join(rel, "RELEASE.md")).read().split("\n## ")[0].strip().splitlines()
    title = next((l.lstrip("# ").strip() for l in note if l.strip()), release_id)
    regole = os.path.join(root, "REGOLE_SFIDA.md")
    if os.path.exists(regole):
        with open(regole, "a") as f:
            f.write(f"- **{stamp}** — {title}. Rilascio nella finestra della domenica (regola 7), applicato da "
                    f"GERVA Capital con la scelta di Andrea; backup in backups/pre-{release_id}/. "
                    f"Modifica che non dipende dai risultati osservati.\n")
    open(os.path.join(rel, "APPLIED"), "w").write(stamp)
    audit.log("release", "release.applied", dict(id=release_id, patch=[os.path.basename(p) for p in patches]))
    events.publish("release.applied", "release", dict(id=release_id))
    return dict(ok=True, backup=backup, patch=len(patches))


def export_trials(gerva_q: str | None = None) -> str:
    """Esporta il trial registry per il DSR verificabile di v3_validate.py (patch R1)."""
    import csv
    import math
    root = gerva_q or paths.GERVA_Q
    out = os.path.join(root, "challenge", "trials_export.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rows = db.q("SELECT id, family, status, sharpe_daily FROM trials WHERE COALESCE(result,'') NOT LIKE '%\"sintetico\": true%'")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "famiglia", "stato", "sharpe_annuo"])
        for r in rows:
            w.writerow([r["id"], r["family"], r["status"],
                        "" if r["sharpe_daily"] is None else round(r["sharpe_daily"] * math.sqrt(252), 4)])
    return out
