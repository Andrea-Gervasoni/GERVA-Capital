#!/usr/bin/env python3
"""Prepara il rilascio v3.7: la leva di GERVA-Q segue la volatilita' (moltiplicatore scritto da GERVA Capital).

GERVA-Q legge `scale_mult` da var/firm_overlay.json (solo se il file ha al massimo OVERLAY_MAX_AGE_DAYS giorni), lo limita a
[VOL_MULT_MIN, VOL_MULT_MAX] e applica la scala: min(scala * moltiplicatore, SCALE_HARD_CAP / esposizione). Senza file, o con un
file vecchio, o con il moltiplicatore spento (1.0), non cambia nulla. Non modifica GERVA-Q: scrive solo il file del rilascio.
Uso, dalla cartella di GERVA Capital:  .venv/bin/python deploy/mac/prepara_v37.py"""
import difflib
import os
import sys

HERE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
GQ = os.path.expanduser(os.environ.get("GERVA_Q_PATH") or "~/Documents/GERVA-Q")
REL = "2026-11-07-vol"
OUT = os.path.join(HERE, "research", "releases", REL, "gervaq_v3_7_vol.patch")
ANCHOR_SCALE = "scale = min(C.SCALE_K, C.SCALE_CAP / (eq_base + cr_base)) if eq_base + cr_base > 0 else C.SCALE_K"
ANCHOR_FUNC = "def overlay_targets(today: dt.date) -> dict:"

CFG = ["", "# v3.7: leva gestita per volatilita' (Moreira e Muir 2017). Il moltiplicatore lo scrive GERVA Capital in var/firm_overlay.json.",
       "VOL_MULT_MIN = 0.6", "VOL_MULT_MAX = 1.4", "SCALE_HARD_CAP = 2.0                 # esposizione totale assoluta massima (200% del conto)"]
FUNC = ['def vol_multiplier(today: dt.date) -> float:',
        '    """Moltiplicatore della leva scritto da GERVA Capital (scale_mult). File assente, vecchio o non valido: 1.0."""',
        '    p = os.environ.get("GERVAQ_OVERLAY") or os.path.join(os.path.dirname(HERE), "GERVA-Capital", "var", "firm_overlay.json")',
        '    try:',
        '        doc = json.load(open(p))',
        '        age = (today - dt.date.fromisoformat(doc["scale_data"])).days',
        '        m = float(doc["scale_mult"])',
        '    except (OSError, ValueError, KeyError, TypeError):',
        '        return 1.0',
        '    if not 0 <= age <= C.OVERLAY_MAX_AGE_DAYS or m != m:',
        '        return 1.0',
        '    return min(max(m, C.VOL_MULT_MIN), C.VOL_MULT_MAX)',
        '', '']
APPLY = ['vm = vol_multiplier(dt.date.today())          # v3.7: leva gestita per volatilita\'',
         'if vm != 1.0 and eq_base + cr_base > 0:',
         '    scale = min(scale * vm, C.SCALE_HARD_CAP / (eq_base + cr_base))',
         '    print(f"[scala] gestita per volatilita\': x{vm:.2f} -> scala {scale:.2f}x")']


def stop(msg):
    print("FERMO:", msg)
    sys.exit(1)


def main():
    cp, lp = os.path.join(GQ, "config.py"), os.path.join(GQ, "live.py")
    for p in (cp, lp):
        if not os.path.exists(p):
            stop(f"non trovo {p}")
    cfg0, live0 = open(cp).read(), open(lp).read()
    if "vol_multiplier" in live0 or "VOL_MULT_MIN" in cfg0:
        stop("la v3.7 e' gia' presente")
    if "def overlay_targets" not in live0:
        stop("manca la v3.3 (overlay_targets): applicala prima")
    L = live0.split("\n")
    hits = [i for i, l in enumerate(L) if l.strip() == ANCHOR_SCALE]
    if len(hits) != 1:
        stop(f"la riga della scala e' stata trovata {len(hits)} volte (ne serve una): mandami `grep -n SCALE_ live.py`")
    ind = L[hits[0]][:len(L[hits[0]]) - len(L[hits[0]].lstrip())]
    L[hits[0] + 1:hits[0] + 1] = [ind + x for x in APPLY]
    f = [i for i, l in enumerate(L) if l.strip() == ANCHOR_FUNC]
    if len(f) != 1:
        stop("non trovo overlay_targets in live.py")
    L[f[0]:f[0]] = FUNC
    live1 = "\n".join(L)
    cfg1 = cfg0.rstrip("\n") + "\n" + "\n".join(CFG) + "\n"
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
        "# Leva gestita per volatilita' (v3.7)\n\nGERVA-Q legge scale_mult da var/firm_overlay.json (fresco, limitato a 0,6-1,4) e applica "
        "scala = min(scala * m, SCALE_HARD_CAP / esposizione), con SCALE_HARD_CAP 2.0. Senza file o con m=1 non cambia nulla.\n")
    print(f"OK: scritto {OUT} ({len(text.splitlines())} righe). GERVA-Q non e' stato toccato.")
    print(f"Ora: .venv/bin/python firm.py release --apply {REL}")


main()
