#!/usr/bin/env python3
"""Prepara il rilascio v3.4 (sicurezza: GERVA-Q non invia ordini se Trader Workstation non risponde) SULLA VERSIONE ATTUALE di GERVA-Q.
Non modifica GERVA-Q: scrive solo il file research/releases/2026-11-06-sicurezza/gervaq_v3_4_sicurezza.patch, che poi si applica
con `python firm.py release --apply 2026-11-06-sicurezza` (backup, changelog e audit compresi).
Si ferma senza scrivere nulla se un punto di aggancio non si trova o se il codice risultante non e' valido.
Uso, dalla cartella di GERVA Capital:  .venv/bin/python deploy/mac/prepara_v34.py"""
import difflib, os, re, sys

HERE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))   # cartella di GERVA Capital
GQ = os.environ.get("GERVA_Q_PATH") or os.path.expanduser("~/Documents/GERVA-Q")
GQ = os.path.expanduser(GQ)
OUT = os.path.join(HERE, "research", "releases", "2026-11-06-sicurezza", "gervaq_v3_4_sicurezza.patch")

CFG = []
FUNCS = ['# ----------------------------------------------------------------------------', '# 1d. SICUREZZA SE TWS NON RISPONDE (v3.4)', '# ----------------------------------------------------------------------------', 'POS_SEEN = os.path.join(STATE, "positions_seen.json")', '', '', 'def account_looks_broken(nav_eur, pos):', '    """Motivo per NON inviare ordini se i dati del conto sembrano incompleti (TWS in timeout o in riavvio), altrimenti None.', '    Senza questo controllo un conto che sembra vuoto verrebbe ricomprato da capo, raddoppiando le posizioni."""', '    if not (isinstance(nav_eur, (int, float)) and nav_eur == nav_eur and nav_eur > 0):', '        return "valore del conto non disponibile"', '    try:', '        seen = json.load(open(POS_SEEN))', '    except (OSError, ValueError):', '        seen = {}', '    n0, nav0 = int(seen.get("n", 0) or 0), float(seen.get("nav", 0) or 0)', '    if n0 >= 3 and len(pos) == 0:', '        return f"nessuna posizione, ma l\'ultima volta erano {n0}: Trader Workstation non ha risposto"', '    if nav0 > 0 and abs(nav_eur / nav0 - 1) > 0.30 and os.environ.get("GERVAQ_ACCEPT_NAV_JUMP") != "1":', '        return f"valore del conto {nav_eur:,.0f} EUR contro {nav0:,.0f} dell\'ultima volta (oltre il 30%)"', '    return None', '', '', 'def remember_positions(nav_eur, pos):', '    os.makedirs(STATE, exist_ok=True)', '    tmp = POS_SEEN + ".tmp"', '    json.dump(dict(n=len(pos), nav=round(float(nav_eur), 2), date=dt.date.today().isoformat()), open(tmp, "w"))', '    os.replace(tmp, POS_SEEN)', '', '']
BUILD = []
SCALE = ['    if a.mode in ("paper", "live"):                    # v3.4: fail-closed se i dati del conto sembrano incompleti', '        why = account_looks_broken(nav_eur, pos)', '        if why:', '            print(f"BLOCCO: {why}. Nessun ordine inviato.")', '            ib.disconnect()', '            return 4', '        remember_positions(nav_eur, pos)', '    else:', '        why = account_looks_broken(nav_eur, pos)', '        if why:', '            print(f"[attenzione] {why}: in paper o live non invierebbe ordini")']
MAINLT = []
CRY = ['    if a.mode in ("paper", "live") and not nav_eur > 0:        # v3.4: fail-closed se TWS non risponde', '        print("BLOCCO: valore del conto non disponibile (Trader Workstation non ha risposto). Nessun ordine inviato.")', '        ib.disconnect()', '        return 4']


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
    if "account_looks_broken" in live0:
        stop("la v3.4 e' gia' presente in GERVA-Q")
    for name in (r"^import datetime as dt", r"^import json", r"^import math", r"^import os", r"^HERE\s*=", r"^STATE\s*=",
                 r"^def qualify\(", r"^def last_price\("):
        if not re.search(name, live0, re.M):
            stop(f"in live.py manca '{name[1:]}': servono i nomi usati dalla v3.2")
    if not re.search(r"^import config as C|^from . import config as C|^import config as C", live0, re.M):
        stop("in live.py non trovo 'import config as C'")
    cfg1 = cfg0
    L = live0.split("\n")
    i = find(L, lambda s: s.startswith("# 2. IBKR"), "# 2. IBKR")
    L[i:i] = FUNCS
    i = find(L, lambda s: s.startswith('print(f"[ibkr] conto {acct}'), "riga [ibkr] conto")
    L[i + 1:i + 1] = SCALE
    live1 = "\n".join(L)
    cry_p = os.path.join(GQ, "crypto_live.py")
    cry0 = cry1 = None
    if os.path.exists(cry_p):
        cry0 = open(cry_p).read()
        CL = cry0.split("\n")
        hits = [j for j, l in enumerate(CL) if l.strip().startswith('nav_eur = float(vals.get(("NetLiquidation", "EUR")')]
        if len(hits) == 1 and "BLOCCO: valore del conto non disponibile" not in cry0:
            CL[hits[0] + 1:hits[0] + 1] = CRY
            cry1 = "\n".join(CL)
        else:
            print("(nota: in crypto_live.py non trovo il punto per la sicurezza: lo salto, live.py e' comunque protetto)")
    checks = [("live.py", live1)] + ([("crypto_live.py", cry1)] if cry1 else [])
    for name, src in checks:
        try:
            compile(src, name, "exec")
        except SyntaxError as e:
            stop(f"{name} non sarebbe valido: {e}")
    diff = []
    for name, a, b in [("live.py", live0, live1)] + ([("crypto_live.py", cry0, cry1)] if cry1 else []):
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
        "# Sicurezza se Trader Workstation non risponde (v3.4)\n\nGERVA-Q non invia ordini se il valore del conto non arriva, "
        "se le posizioni risultano vuote quando l'ultima volta erano almeno 3, o se il valore del conto cambia di oltre il 30% "
        "(con GERVAQ_ACCEPT_NAV_JUMP=1 si accetta un versamento voluto). Cosi' un conto che sembra vuoto non viene ricomprato da capo.\n")
    print(f"OK: scritto {OUT} ({len(text.splitlines())} righe). GERVA-Q non e' stato toccato.")
    print("Ora: .venv/bin/python firm.py release --apply 2026-11-06-sicurezza")


main()
