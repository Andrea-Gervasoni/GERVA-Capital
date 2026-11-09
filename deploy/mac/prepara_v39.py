#!/usr/bin/env python3
"""Prepara il rilascio v3.9: ordini sulle azioni USA a mercato aperto.

Il problema (visto nel log di live-seduta.log): place() manda le azioni con MarketOrder(..., tif="OPG") (market-on-open). Un ordine OPG si
puo' mandare solo a mercato CHIUSO (si esegue nell'asta di apertura del giorno dopo): se arriva dopo l'apertura, IBKR lo annulla. Per questo
le esecuzioni "di seduta" (15:45, 17:45, 19:45, 21:45) non hanno mai mosso le azioni americane (tutte 'Cancelled', anche le vendite), mentre gli
ETF europei (limite, tif DAY) si eseguono. L'esecuzione delle 22:35, a mercato chiuso, funziona.

La correzione: us_market_open(ib, c) legge le ore di contrattazione del contratto (liquidHours, nel suo fuso) e place() usa
  * mercato aperto  -> MarketOrder(..., tif="DAY"): si esegue subito;
  * mercato chiuso  -> MarketOrder(..., tif="OPG"): come prima (l'esecuzione delle 22:35 resta uguale);
  * se non si riesce a sapere -> "OPG", il comportamento di prima.
Non modifica GERVA-Q: scrive solo il file del rilascio. Uso, dalla cartella di GERVA Capital:  .venv/bin/python deploy/mac/prepara_v39.py"""
import difflib
import os
import sys

HERE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
GQ = os.path.expanduser(os.environ.get("GERVA_Q_PATH") or "~/Documents/GERVA-Q")
REL = "2026-11-09-ordini-seduta"
OUT_DIR = os.environ.get("PREPARA_OUT_DIR") or os.path.join(HERE, "research", "releases", REL)
OUT = os.path.join(OUT_DIR, "gervaq_v3_9_ordini_seduta.patch")
ANCHOR_FUNC = "def place(ib, orders: pd.DataFrame):"
ANCHOR_OPG = 'ordr = MarketOrder(o.action, int(o.qty), tif="OPG")'

FUNC = '''_US_OPEN_CACHE = {}


def us_market_open(ib, c):
    """v3.9: la sessione regolare di questo titolo e' aperta ADESSO? (ore di contrattazione del contratto, nel suo fuso.)
    Un ordine OPG (market-on-open) si puo' mandare solo a mercato chiuso: dopo l'apertura IBKR lo annulla. A mercato aperto serve un ordine
    valido per la giornata. Se non si riesce a sapere: False (il comportamento di prima)."""
    import datetime as _dt
    try:
        from zoneinfo import ZoneInfo
        key = (int(getattr(c, "conId", 0) or 0), _dt.datetime.now().strftime("%Y%m%d%H%M"))
        if key in _US_OPEN_CACHE:
            return _US_OPEN_CACHE[key]
        d = ib.reqContractDetails(c)[0]
        tz = ZoneInfo({"US/Eastern": "America/New_York"}.get(d.timeZoneId, d.timeZoneId))
        now = _dt.datetime.now(tz)
        res = False
        for seg in (d.liquidHours or "").split(";"):
            if "-" not in seg or "CLOSED" in seg:
                continue
            a, b = seg.split("-")
            s = _dt.datetime.strptime(a, "%Y%m%d:%H%M").replace(tzinfo=tz)
            e = _dt.datetime.strptime(b, "%Y%m%d:%H%M").replace(tzinfo=tz)
            if s <= now < e:
                res = True
                break
        _US_OPEN_CACHE[key] = res
        return res
    except Exception:
        return False


'''.split("\n")
NEW_OPG = 'ordr = MarketOrder(o.action, int(o.qty), tif=("DAY" if us_market_open(ib, c) else "OPG"))      # v3.9: mercato aperto -> per la giornata; chiuso -> all\'apertura'


def stop(msg):
    print("FERMO:", msg)
    sys.exit(1)


def main():
    lp = os.path.join(GQ, "live.py")
    if not os.path.exists(lp):
        stop(f"non trovo {lp}")
    live0 = open(lp).read()
    if "us_market_open" in live0:
        stop("la v3.9 e' gia' presente")
    L = live0.split("\n")
    f = [i for i, l in enumerate(L) if l.strip() == ANCHOR_FUNC]
    if len(f) != 1:
        stop(f"non trovo place() una volta sola ({len(f)} volte): mandami `grep -n 'def place' live.py`")
    o = [i for i, l in enumerate(L) if ANCHOR_OPG in l]
    if len(o) != 1:
        stop(f"la riga dell'ordine OPG e' stata trovata {len(o)} volte (ne serve una): mandami `grep -n OPG live.py`")
    ind = L[o[0]][:len(L[o[0]]) - len(L[o[0]].lstrip())]
    L[o[0]] = ind + NEW_OPG
    L[f[0]:f[0]] = FUNC                                  # la funzione prima di place() (gli indici sopra restano validi: si inserisce prima)
    live1 = "\n".join(L)
    try:
        compile(live1, "live.py", "exec")
    except SyntaxError as e:
        stop(f"live.py non sarebbe valido: {e}")
    diff = difflib.unified_diff(live0.splitlines(True), live1.splitlines(True), "a/live.py", "b/live.py", n=3)
    text = "".join(l if l.endswith("\n") else l + "\n" for l in diff)
    sys.path.insert(0, HERE)
    from firm.release import apply_unified_diff
    try:
        apply_unified_diff(text, GQ, dry_run=True)
    except Exception as e:
        stop(f"il file di rilascio non si applicherebbe: {e}")
    os.makedirs(OUT_DIR, exist_ok=True)
    open(OUT, "w").write(text)
    open(os.path.join(OUT_DIR, "RELEASE.md"), "w").write(
        "# Ordini sulle azioni USA a mercato aperto (v3.9)\n\nLe azioni americane si mandavano sempre come market-on-open (OPG), che IBKR annulla se arriva dopo "
        "l'apertura: le esecuzioni di seduta non le hanno mai mosse. Ora, a mercato aperto (ore di contrattazione del contratto), l'ordine e' a mercato "
        "valido per la giornata; a mercato chiuso resta OPG (l'esecuzione delle 22:35 non cambia). Se non si riesce a sapere l'orario: OPG, come prima.\n")
    print(f"OK: scritto {OUT} ({len(text.splitlines())} righe). GERVA-Q non e' stato toccato.")
    print(f"Ora: .venv/bin/python firm.py release --apply {REL}")


main()
