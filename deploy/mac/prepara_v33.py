#!/usr/bin/env python3
"""Prepara il rilascio v3.3 (desk di trading: le proposte dei capi desk entrano nel conto) SULLA VERSIONE ATTUALE di GERVA-Q.
Non modifica GERVA-Q: scrive solo il file research/releases/2026-11-06/gervaq_v3_3_desk.patch, che poi si applica
con `python firm.py release --apply 2026-11-06` (backup, changelog e audit compresi).
Si ferma senza scrivere nulla se un punto di aggancio non si trova o se il codice risultante non e' valido.
Uso, dalla cartella di GERVA Capital:  .venv/bin/python deploy/mac/prepara_v33.py"""
import difflib, os, re, sys

HERE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))   # cartella di GERVA Capital
GQ = os.environ.get("GERVA_Q_PATH") or os.path.expanduser("~/Documents/GERVA-Q")
GQ = os.path.expanduser(GQ)
OUT = os.path.join(HERE, "research", "releases", "2026-11-06", "gervaq_v3_3_desk.patch")

CFG = ['', '# v3.3: desk di trading di GERVA Capital (6/11): i capi desk propongono, il suo codice valida (var/firm_overlay.json),', "# GERVA-Q rifa' i controlli con questi tetti e ignora un file piu' vecchio di OVERLAY_MAX_AGE_DAYS giorni.", 'OVERLAY_MAX_NAME = 0.05                # al massimo il 5% del NAV su un titolo', "OVERLAY_MAX_TOTAL = 0.30               # al massimo il 30% del NAV in totale (sopra il modello: e' la leva)", 'OVERLAY_MAX_AGE_DAYS = 3']
FUNCS = ['# ----------------------------------------------------------------------------', '# 1c. DESK DI TRADING (v3.3)', '# ----------------------------------------------------------------------------', 'def overlay_targets(today: dt.date) -> dict:', '    """Pesi (frazione del NAV) proposti dai capi desk di GERVA Capital e validati dal suo codice.', '    File var/firm_overlay.json: solo se fresco (C.OVERLAY_MAX_AGE_DAYS), solo simboli maiuscoli alfanumerici, tetto per', '    titolo e totale. Assente, vecchio o non valido: nessuna posizione in piu\'."""', '    p = os.environ.get("GERVAQ_OVERLAY") or os.path.join(os.path.dirname(HERE), "GERVA-Capital", "var", "firm_overlay.json")', '    try:', '        doc = json.load(open(p))', '        age = (today - dt.date.fromisoformat(doc["data"])).days', '    except (OSError, ValueError, KeyError, TypeError):', '        return {}', '    if not 0 <= age <= C.OVERLAY_MAX_AGE_DAYS:', '        return {}', '    out = {}', '    for sym, f in (doc.get("targets") or {}).items():', '        if isinstance(sym, str) and sym.isalnum() and sym.isupper() and isinstance(f, (int, float)) and f == f and f > 0:', '            out[sym] = min(float(f), C.OVERLAY_MAX_NAME)', '    tot = sum(out.values())', '    if tot > C.OVERLAY_MAX_TOTAL:', '        out = {k: v * C.OVERLAY_MAX_TOTAL / tot for k, v in out.items()}', '    return out', '', '']
BUILD = []
SCALE = ['    ov = overlay_targets(dt.date.today())              # v3.3: posizioni dei capi desk, sopra il modello', '    for sym, f in ov.items():', '        inst.setdefault(sym, dict(weight=0.0, exchange="SMART", currency="USD", kind="stock", proxy=sym))', '        inst[sym]["weight"] = inst[sym].get("weight", 0.0) + f', '    if ov:', '        print("[desk] posizioni proposte dai capi desk: " + ", ".join(f"{k} {v:.1%}" for k, v in sorted(ov.items())))']
MAINLT = []


def stop(msg):
    print("FERMO:", msg); sys.exit(1)


def find(lines, pred, what):
    hits = [i for i, l in enumerate(lines) if pred(l.strip())]
    if len(hits) != 1:
        stop(f"punto di aggancio '{what}' trovato {len(hits)} volte (ne serve una)")
    return hits[0]


def main():
    cfg_p, live_p = os.path.join(GQ, "config.py"), os.path.join(GQ, "live.py")
    for p in (cfg_p, live_p):
        if not os.path.exists(p):
            stop(f"non trovo {p}")
    cfg0, live0 = open(cfg_p).read(), open(live_p).read()
    if "OVERLAY_MAX_NAME" in cfg0 or "overlay_targets" in live0:
        stop("la v3.3 e' gia' presente in GERVA-Q")
    for name in (r"^import datetime as dt", r"^import json", r"^import math", r"^import os", r"^HERE\s*=", r"^STATE\s*=",
                 r"^def qualify\(", r"^def last_price\("):
        if not re.search(name, live0, re.M):
            stop(f"in live.py manca '{name[1:]}': servono i nomi usati dalla v3.2")
    if not re.search(r"^import config as C|^from . import config as C|^import config as C", live0, re.M):
        stop("in live.py non trovo 'import config as C'")
    cfg1 = cfg0.rstrip("\n") + "\n" + "\n".join(CFG) + "\n"
    L = live0.split("\n")
    i = find(L, lambda s: s.startswith("# 2. IBKR"), "# 2. IBKR")
    L[i:i] = FUNCS
    i = find(L, lambda s: s == "inst = to_instruments(w)", "inst = to_instruments(w)")
    L[i + 1:i + 1] = SCALE
    live1 = "\n".join(L)
    for name, src in (("config.py", cfg1), ("live.py", live1)):
        try:
            compile(src, name, "exec")
        except SyntaxError as e:
            stop(f"{name} non sarebbe valido: {e}")
    diff = []
    for name, a, b in (("config.py", cfg0, cfg1), ("live.py", live0, live1)):
        diff += difflib.unified_diff(a.splitlines(True), b.splitlines(True), f"a/{name}", f"b/{name}", n=3)
    text = "".join(l if l.endswith("\n") else l + "\n" for l in diff)
    sys.path.insert(0, HERE)
    from firm.release import apply_unified_diff
    try:
        apply_unified_diff(text, GQ, dry_run=True)
    except Exception as e:
        stop(f"il file di rilascio non si applicherebbe: {e}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write(text)
    open(os.path.join(os.path.dirname(OUT), "RELEASE.md"), "w").write(
        "# Desk di trading (v3.3)\n\nGERVA-Q legge var/firm_overlay.json di GERVA Capital: le posizioni proposte dai capi desk e "
        "validate dal codice entrano nel conto sopra il modello (tetti OVERLAY_MAX_* in config.py). Scelta di Andrea del 6/11.\n")
    print(f"OK: scritto {OUT} ({len(text.splitlines())} righe). GERVA-Q non e' stato toccato.")
    print("Ora: .venv/bin/python firm.py release --apply 2026-11-06")


main()
