#!/usr/bin/env python3
"""Prepara il rilascio v3.5: il blocco di sicurezza riconosce da solo una lista di posizioni vuota.

Perche': il 6/11 Trader Workstation ha risposto "positions request timed out" ma ha dato il valore del conto. Con la lista
vuota GERVA-Q avrebbe ricomprato da capo CNDX e IJPA. Il blocco v3.4 confrontava solo con l'ultima volta (e la prima volta non
c'e' un'ultima volta). Ora confronta anche con GrossPositionValue, il valore delle posizioni che IBKR stesso dichiara.

Non modifica GERVA-Q: scrive solo il file del rilascio, che poi si applica con `python firm.py release --apply ...`.
Uso, dalla cartella di GERVA Capital:  .venv/bin/python deploy/mac/prepara_v35.py"""
import difflib
import os
import sys

HERE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
GQ = os.path.expanduser(os.environ.get("GERVA_Q_PATH") or "~/Documents/GERVA-Q")
REL = "2026-11-06-sicurezza2"
OUT = os.path.join(HERE, "research", "releases", REL, "gervaq_v3_5_sicurezza2.patch")

DEF_OLD = "def account_looks_broken(nav_eur, pos):"
DEF_NEW = "def account_looks_broken(nav_eur, pos, ib=None, acct=None):"
CALL_OLD = "account_looks_broken(nav_eur, pos)"
CALL_NEW = "account_looks_broken(nav_eur, pos, ib, acct)"
CHECK = '''    gross = 0.0                                          # v3.5: valore delle posizioni dichiarato da IBKR stesso
    try:
        for v in (ib.accountValues(acct) if ib is not None else []):
            if v.tag == "GrossPositionValue" and v.currency in ("EUR", "BASE"):
                gross = max(gross, abs(float(v.value)))
    except Exception:
        gross = 0.0
    if gross > 0.05 * nav_eur and len(pos) == 0:
        return f"il conto ha posizioni per {gross:,.0f} EUR ma la lista e' vuota: Trader Workstation non ha risposto"'''.split("\n")


def stop(msg):
    print("FERMO:", msg)
    sys.exit(1)


def main():
    p = os.path.join(GQ, "live.py")
    if not os.path.exists(p):
        stop(f"non trovo {p}")
    src = open(p).read()
    if "GrossPositionValue" in src:
        stop("la v3.5 e' gia' presente")
    if DEF_OLD not in src:
        stop("manca il blocco v3.4 (account_looks_broken): applica prima la v3.4")
    if src.count(CALL_OLD) < 1:
        stop("non trovo la chiamata a account_looks_broken in main()")
    L = src.replace(DEF_OLD, DEF_NEW).replace(CALL_OLD, CALL_NEW).split("\n")
    hits = [i for i, l in enumerate(L) if l.strip() == "seen = json.load(open(POS_SEEN))"]
    if len(hits) != 1 or L[hits[0] - 1].strip() != "try:":
        stop("non trovo il punto dove inserire il controllo")
    L[hits[0] - 1:hits[0] - 1] = CHECK
    new = "\n".join(L)
    try:
        compile(new, "live.py", "exec")
    except SyntaxError as e:
        stop(f"live.py non sarebbe valido: {e}")
    diff = "".join(l if l.endswith("\n") else l + "\n" for l in
                   difflib.unified_diff(src.splitlines(True), new.splitlines(True), "a/live.py", "b/live.py", n=3))
    sys.path.insert(0, HERE)
    from firm.release import apply_unified_diff
    try:
        apply_unified_diff(diff, GQ, dry_run=True)
    except Exception as e:
        stop(f"il file di rilascio non si applicherebbe: {e}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write(diff)
    open(os.path.join(os.path.dirname(OUT), "RELEASE.md"), "w").write(
        "# Sicurezza 2 (v3.5)\n\nIl blocco di GERVA-Q riconosce una lista di posizioni vuota anche alla prima volta: se IBKR dichiara "
        "posizioni per piu' del 5% del conto (GrossPositionValue) e la lista e' vuota, non invia ordini.\n")
    print(f"OK: scritto {OUT} ({len(diff.splitlines())} righe). GERVA-Q non e' stato toccato.")
    print(f"Ora: .venv/bin/python firm.py release --apply {REL}")


main()
