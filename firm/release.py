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

from . import db, events, audit, mailbox, paths
from . import settings as S

RELEASES = os.path.join(paths.RESEARCH, "releases")


def apply_unified_diff(patch_text: str, root: str, dry_run: bool = False) -> list[str]:
    """Applicatore rigoroso di diff unificati (come `patch -p1`, senza dipendenze esterne).
    Ogni riga di contesto e ogni riga tolta deve coincidere ESATTAMENTE: altrimenti non si scrive nulla."""
    import re
    files, cur = [], None
    for line in patch_text.splitlines(keepends=True):
        if line.startswith("--- "):
            continue
        if line.startswith("+++ "):
            name = line[4:].split("\t")[0].strip()
            cur = dict(path=name.split("/", 1)[1] if "/" in name else name, hunks=[])
            files.append(cur)
        elif line.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@", line)
            cur["hunks"].append(dict(start=int(m.group(1)), lines=[]))
        elif cur and cur["hunks"] and line[:1] in (" ", "-", "+"):
            cur["hunks"][-1]["lines"].append(line)
        elif cur and cur["hunks"] and line.startswith("\\"):
            continue
    out = {}
    for f in files:
        path = os.path.join(root, f["path"])
        src = open(path).read().splitlines(keepends=True)
        res, pos = [], 0
        for h in f["hunks"]:
            i = h["start"] - 1
            res += src[pos:i]
            for l in h["lines"]:
                if l[0] in " -":
                    if i >= len(src) or src[i] != l[1:]:
                        raise ValueError(f"{f['path']}: il contesto non coincide alla riga {i + 1}")
                    if l[0] == " ":
                        res.append(src[i])
                    i += 1
                else:
                    res.append(l[1:])
            pos = i
        res += src[pos:]
        out[path] = "".join(res)
    if not dry_run:
        for path, txt in out.items():
            with open(path, "w") as fh:
                fh.write(txt)
    return [os.path.relpath(p, root) for p in out]


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
        5, f"Rilascio GERVA-Q {rel['id']}: applicare le patch?",
        "Le patch modificano file nella cartella di GERVA-Q (fuori da questo progetto). Le " + str(len(rel.get("patches", []))) +
        " patch sono descritte una per una in research/releases/" + rel["id"] + "/RELEASE.md: quali correggono l'audit senza "
        "toccare i segnali e quali CAMBIANO gli ordini (per esempio la quota di lungo periodo).",
        ["Applicare domenica nella finestra di rilascio", "Non applicare: restano proposte"],
        "Leggere RELEASE.md: applicare le correzioni dell'audit; la parte che cambia gli ordini solo se la vuoi davvero",
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
        try:
            apply_unified_diff(open(p).read(), root, dry_run=True)
        except (ValueError, FileNotFoundError) as e:
            return dict(ok=False, motivo=f"patch non applicabile: {os.path.basename(p)}", dettaglio=str(e)[:300])
    stamp = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%d")
    backup = os.path.join(root, "backups", f"pre-{release_id}")
    os.makedirs(backup, exist_ok=True)
    for f in glob.glob(os.path.join(root, "*.py")) + [os.path.join(root, "REGOLE_SFIDA.md")]:
        if os.path.exists(f):
            shutil.copy2(f, backup)
    for p in patches:
        apply_unified_diff(open(p).read(), root)
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
