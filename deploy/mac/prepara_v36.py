#!/usr/bin/env python3
"""Prepara il rilascio v3.6: le posizioni crypto dei segnali approvati dal desk di GERVA Capital entrano nel conto.

Cosa fa a crypto_live.py (e solo a lui):
  * aggiunge la funzione crypto_overlay(), che legge var/firm_overlay.json (campo crypto_targets) e lo ripulisce di nuovo:
    solo monete ammesse, al massimo il 3% del conto per moneta e il 10% in totale, file fresco (campo crypto_data, 3 giorni);
  * dopo che il modello ha calcolato i suoi pesi (gia' con la scala) e li ha salvati, SOMMA le posizioni dei segnali. Non vengono
    moltiplicate per la scala, non finiscono in crypto_latest.json e, se il file manca o e' vecchio, la posizione sparisce
    (a 0 il motore vende: e' il comportamento prudente).
Non modifica GERVA-Q: scrive solo il file del rilascio, che poi si applica con `python firm.py release --apply ...`.
Uso, dalla cartella di GERVA Capital:  .venv/bin/python deploy/mac/prepara_v36.py"""
import difflib
import os
import re
import sys

HERE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
GQ = os.path.expanduser(os.environ.get("GERVA_Q_PATH") or "~/Documents/GERVA-Q")
REL = "2026-11-06-segnali"
OUT = os.path.join(HERE, "research", "releases", REL, "gervaq_v3_6_segnali.patch")

FUNC = '''# ----------------------------------------------------------------------------
# SEGNALI APPROVATI DAL DESK CRYPTO DI GERVA CAPITAL (v3.6)
# ----------------------------------------------------------------------------
def crypto_overlay(today):
    """Pesi (frazione del NAV) delle posizioni dei segnali approvati: var/firm_overlay.json, campo crypto_targets.
    Solo monete ammesse, tetto per moneta e totale, file fresco. Assente, vecchio o non valido: nessuna posizione."""
    allowed = {"BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "LTC", "LINK", "AVAX", "BCH", "SUI"}
    p = os.environ.get("GERVAQ_OVERLAY") or os.path.join(os.path.dirname(HERE), "GERVA-Capital", "var", "firm_overlay.json")
    try:
        doc = json.load(open(p))
        age = (today - dt.date.fromisoformat(doc["crypto_data"])).days
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    if not 0 <= age <= getattr(C, "OVERLAY_MAX_AGE_DAYS", 3):
        return {}
    out = {}
    for sym, f in (doc.get("crypto_targets") or {}).items():
        if sym in allowed and isinstance(f, (int, float)) and f == f and f > 0:
            out[sym] = min(float(f), getattr(C, "CRYPTO_OVERLAY_MAX_NAME", 0.03))
    tot = sum(out.values())
    cap = getattr(C, "CRYPTO_OVERLAY_MAX_TOTAL", 0.10)
    if tot > cap:
        out = {k: v * cap / tot for k, v in out.items()}
    return out
'''.split("\n")
CALL = '''    cov = crypto_overlay(dt.date.today())                  # v3.6: segnali approvati, sopra il modello e senza scala
    for _s, _f in cov.items():
        w[_s] = w.get(_s, 0.0) + _f
    if cov:
        print("[segnali] posizioni dai segnali approvati: " + ", ".join(f"{k} {v:.1%}" for k, v in sorted(cov.items())))'''.split("\n")


def stop(msg):
    print("FERMO:", msg)
    sys.exit(1)


def main():
    p = os.path.join(GQ, "crypto_live.py")
    if not os.path.exists(p):
        stop(f"non trovo {p}")
    src = open(p).read()
    if "def crypto_overlay" in src:
        stop("la v3.6 e' gia' presente")
    for name in (r"^import datetime as dt", r"^import json", r"^import os", r"^HERE\s*=", r"^STATE\s*=", r"^(import config as C|from . import config as C)"):
        if not re.search(name, src, re.M):
            stop(f"in crypto_live.py manca '{name[1:]}': servono i nomi usati dalla v3.6")
    L = src.split("\n")
    m = [i for i, l in enumerate(L) if l.strip() == "def main():"]
    d = [i for i, l in enumerate(L) if l.strip().startswith('json.dump(dict(bar=str(last_bar), weights=w')]
    sc = [i for i, l in enumerate(L) if l.strip().startswith("w = {k: v * scale for k, v in w.items()}")]
    if len(m) != 1 or len(d) != 1 or len(sc) != 1 or not sc[0] < d[0]:
        stop("non trovo i punti di aggancio in crypto_live.py (def main, la scala dei pesi e il salvataggio): mandami le righe 100-135")
    L[d[0] + 1:d[0] + 1] = CALL                      # dopo il salvataggio: crypto_latest.json resta quello del modello
    L[m[0]:m[0]] = FUNC + ["", ""]
    new = "\n".join(L)
    try:
        compile(new, "crypto_live.py", "exec")
    except SyntaxError as e:
        stop(f"crypto_live.py non sarebbe valido: {e}")
    diff = "".join(l if l.endswith("\n") else l + "\n" for l in
                   difflib.unified_diff(src.splitlines(True), new.splitlines(True), "a/crypto_live.py", "b/crypto_live.py", n=3))
    sys.path.insert(0, HERE)
    from firm.release import apply_unified_diff
    try:
        apply_unified_diff(diff, GQ, dry_run=True)
    except Exception as e:
        stop(f"il file di rilascio non si applicherebbe: {e}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w").write(diff)
    open(os.path.join(os.path.dirname(OUT), "RELEASE.md"), "w").write(
        "# Segnali crypto nel conto (v3.6)\n\ncrypto_live.py somma ai pesi del modello le posizioni dei segnali approvati dal desk di GERVA Capital "
        "(var/firm_overlay.json, crypto_targets): tetto del 3% per moneta e 10% in totale, solo se il file e' fresco, senza scala di "
        "investimento. Se il file manca o e' vecchio, la posizione sparisce.\n")
    print(f"OK: scritto {OUT} ({len(diff.splitlines())} righe). GERVA-Q non e' stato toccato.")
    print(f"Ora: .venv/bin/python firm.py release --apply {REL}")


main()
