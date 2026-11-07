#!/usr/bin/env python3
"""Prepara il rilascio v3.8: ritmo di ingresso. GERVA-Q legge `max_turnover` da var/firm_overlay.json (lo sceglie il Capo di
GERVA Capital ogni giorno, entro i limiti del codice) e limita gli ACQUISTI del giorno a quella frazione del conto, sopra le
vendite del giorno (le vendite non hanno tetto). Il giorno dopo ricalcola gli obiettivi e compra la rata successiva.
File assente, vecchio o non valido: nessun tetto. Non modifica GERVA-Q: scrive solo il file del rilascio.
Uso, dalla cartella di GERVA Capital:  .venv/bin/python deploy/mac/prepara_v38.py"""
import difflib
import os
import re
import sys

HERE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
GQ = os.path.expanduser(os.environ.get("GERVA_Q_PATH") or "~/Documents/GERVA-Q")
REL = "2026-11-07-ritmo"
OUT = os.path.join(HERE, "research", "releases", REL, "gervaq_v3_8_ritmo.patch")
ANCHOR_CALL = "orders = build_orders(ib, inst, nav_eur, eurusd, pos)"
ANCHOR_FUNC = "def overlay_targets(today: dt.date) -> dict:"

CFG = ["", "# v3.8: ritmo di ingresso. Il Capo di GERVA Capital sceglie max_turnover (frazione del conto acquistabile al giorno);", "# GERVA-Q lo accetta solo tra TURNOVER_MIN e 1.0.", "TURNOVER_MIN = 0.10"]
FUNC = ['def apply_turnover_cap(orders, nav_eur, today=None):',
        '    """v3.8: limita gli ACQUISTI del giorno a max_turnover * NAV, in piu\' alle vendite del giorno. Gli acquisti si riducono in',
        '    proporzione (azioni intere, mai oltre); le vendite restano intere. File assente, vecchio o non valido: nessun tetto."""',
        '    today = today or dt.date.today()',
        '    p = os.environ.get("GERVAQ_OVERLAY") or os.path.join(os.path.dirname(HERE), "GERVA-Capital", "var", "firm_overlay.json")',
        '    try:',
        '        doc = json.load(open(p))',
        '        age = (today - dt.date.fromisoformat(doc["turnover_data"])).days',
        '        cap = float(doc["max_turnover"])',
        '    except (OSError, ValueError, KeyError, TypeError):',
        '        return orders',
        '    if not 0 <= age <= C.OVERLAY_MAX_AGE_DAYS or cap != cap or cap >= 1.0:',
        '        return orders',
        '    cap = max(cap, C.TURNOVER_MIN)',
        '    if orders is None or len(orders) == 0 or not {"action", "qty", "value_eur"} <= set(orders.columns):',
        '        return orders',
        '    o = orders.copy()',
        '    buy = o["action"] == "BUY"',
        '    tot = float(o.loc[buy, "value_eur"].sum())',
        '    allowed = cap * float(nav_eur) + float(o.loc[~buy, "value_eur"].sum())',
        '    if tot <= allowed or tot <= 0:',
        '        return orders',
        '    f = allowed / tot',
        '    old_q = o.loc[buy, "qty"].astype(float)',
        '    new_q = (old_q * f).apply(math.floor).astype(int)',
        '    o.loc[buy, "value_eur"] = o.loc[buy, "value_eur"].astype(float) * (new_q / old_q.where(old_q > 0, 1)).astype(float)',
        '    o.loc[buy, "qty"] = new_q',
        '    o = o[o["qty"] > 0]',
        '    print(f"[ritmo] ingresso a rate: acquisti limitati al {cap:.0%} del conto (+ vendite): {tot:,.0f} -> {float(o.loc[o[\'action\'] == \'BUY\', \'value_eur\'].sum()):,.0f} EUR")',
        '    return o.reset_index(drop=True)',
        '', '']
APPLY = ["orders = apply_turnover_cap(orders, nav_eur)          # v3.8: ritmo di ingresso scelto dal Capo"]


def stop(msg):
    print("FERMO:", msg)
    sys.exit(1)


def main():
    cp, lp = os.path.join(GQ, "config.py"), os.path.join(GQ, "live.py")
    for p in (cp, lp):
        if not os.path.exists(p):
            stop(f"non trovo {p}")
    cfg0, live0 = open(cp).read(), open(lp).read()
    if "apply_turnover_cap" in live0 or "TURNOVER_MIN" in cfg0:
        stop("la v3.8 e' gia' presente")
    if "def overlay_targets" not in live0 or "OVERLAY_MAX_AGE_DAYS" not in cfg0:
        stop("manca la v3.3 (desk): applicala prima")
    for mod in (r"math", r"json", r"os", r"datetime as dt"):
        if not re.search(rf"^import\s+(?:[\w., ]*,\s*)?{mod}\b", live0, re.M):
            stop(f"in live.py manca 'import {mod}'")
    L = live0.split("\n")
    hits = [i for i, l in enumerate(L) if l.strip() == ANCHOR_CALL]
    if len(hits) != 1:
        stop(f"la riga degli ordini e' stata trovata {len(hits)} volte (ne serve una): mandami `grep -n build_orders live.py`")
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
        "# Ritmo di ingresso (v3.8)\n\nGERVA-Q limita gli acquisti del giorno a max_turnover * NAV (+ le vendite del giorno), con max_turnover "
        "scelto ogni giorno dal Capo di GERVA Capital entro limiti del codice (VIX alto: al massimo 50% al giorno). Il giorno dopo compra la rata "
        "successiva. File assente o vecchio: nessun tetto.\n")
    print(f"OK: scritto {OUT} ({len(text.splitlines())} righe). GERVA-Q non e' stato toccato.")
    print(f"Ora: .venv/bin/python firm.py release --apply {REL}")


main()
