#!/usr/bin/env python3
"""
GERVA Capital — comando unico.

    python firm.py init         # crea DB, token di Andrea, organico, prove storiche di GERVA-Q
    python firm.py portal       # portale su http://127.0.0.1:8765 (solo locale)
    python firm.py heartbeat    # un battito: controlla condizioni e sveglia solo gli agenti necessari
    python firm.py run          # battito ogni N minuti (impostazione firm.heartbeat_minutes)
    python firm.py data         # (sul Mac) scarica i prezzi reali per la ricerca
    python firm.py research gervaq4   # (sul Mac) banco di prova dei miglioramenti contro la v3
    python firm.py set-password # hash della password del portale (obbligatoria sul server)
    python firm.py ibkr-check   # prova in sola lettura la connessione a IB Gateway (conto della sfida)
    python firm.py report       # report del giorno con correzioni proposte
    python firm.py status       # budget, rischio, catena di hash, prove
    python firm.py verify       # verifica la catena di hash dell'audit log
    python firm.py release      # elenca i rilasci di GERVA-Q in coda e chiede la scelta ad Andrea
    python firm.py release --apply 2026-11-08   # domenica: backup, patch, changelog
    python firm.py demo         # 45 giorni SINTETICI in var/demo/ (mai nel DB vero)
    python firm.py portal --demo  # portale sul database dimostrativo

Solo paper. Non esiste un comando per la modalita' live.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def _load_env():
    """Legge .env (gitignored) senza dipendenze esterne. I valori non vengono mai stampati."""
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def cmd_init(_):
    from firm import db, org_seed, registry, trials, settings, events, pods
    db.connect()
    settings.ensure_token()
    created = org_seed.seed()
    n = registry.sync()
    seeded = trials.seed_gervaq()
    pods.ensure_pods()
    events.publish("firm.init", "sistema", dict(profili_nuovi=created, agenti=n, prove_storiche=seeded))
    print(f"[init] DB pronto, {n} scrivanie ({created} profili nuovi), {seeded} prove storiche GERVA-Q.")
    print(f"[init] Token di Andrea in var/andrea.token (permessi 600): il portale lo usa per le Impostazioni.")


def cmd_portal(a):
    import uvicorn
    from firm import db
    db.connect()
    bind = os.environ.get("PORTAL_BIND", "127.0.0.1")      # in Docker 0.0.0.0, pubblicato solo su 127.0.0.1 dell'host
    if bind not in ("127.0.0.1", "::1") and not os.environ.get("PORTAL_PASSWORD_HASH"):
        sys.exit("Rifiuto: fuori da 127.0.0.1 il portale richiede PORTAL_PASSWORD_HASH (python firm.py set-password)")
    print(f"GERVA Capital — portale su http://{bind}:8765  (Ctrl+C per chiudere)")
    uvicorn.run("portal.app:app", host=bind, port=8765, log_level="warning", proxy_headers=False, server_header=False)


def cmd_set_password(_):
    """Crea l'hash della password del portale (la password non viene mai salvata ne' stampata)."""
    import getpass
    from portal.app import hash_password
    a, b = getpass.getpass("Nuova password del portale: "), getpass.getpass("Ripeti: ")
    if a != b or len(a) < 12:
        sys.exit("Le password non coincidono o sono piu' corte di 12 caratteri.")
    print("Aggiungi questa riga al file .env (permessi 600):")
    print("PORTAL_PASSWORD_HASH=" + hash_password(a))


def cmd_ibkr_check(_):
    """Prova la connessione in sola lettura al conto della sfida e mostra cosa vede (conto mascherato)."""
    from firm import ibkr
    print(json.dumps(ibkr.observe_challenge(), ensure_ascii=False, indent=1, default=str))


def cmd_heartbeat(_):
    from firm import heartbeat
    print(json.dumps(heartbeat.beat(), ensure_ascii=False, indent=1, default=str))


def cmd_run(_):
    from firm import heartbeat, settings
    while True:
        r = heartbeat.beat()
        print(time.strftime("%H:%M"), r.get("svegliati"), r.get("note"))
        time.sleep(60 * float(settings.get("firm.heartbeat_minutes", 15)))


def cmd_status(_):
    from firm import budget, audit, trials, risk
    st = dict(budget=budget.status(), audit=audit.verify(), prove=trials.counts(), rischio=risk.snapshot())
    print(json.dumps(st, ensure_ascii=False, indent=1, default=str))


def cmd_verify(_):
    from firm import audit
    v = audit.verify()
    print(("OK" if v["ok"] else "ROTTA") + f" — {v['n']} voci" + ("" if v["ok"] else f", prima rottura alla {v['prima_rottura']}"))
    sys.exit(0 if v["ok"] else 1)


def cmd_release(a):
    from firm import release, settings
    rels = release.pending()
    if not a.apply:
        for r in rels:
            print(r["id"], f"{len(r['patches'])} patch", "-", (r["note"].splitlines() or [""])[0])
            release.request_permission(r)
        print("Finestra di rilascio aperta" if release.in_window() else "Fuori dalla finestra di rilascio (default: domenica)")
        return
    release.export_trials()
    cap = settings.AndreaCapability(settings.ensure_token())   # chi lancia il comando dal Mac e' Andrea
    print(release.apply(a.apply, cap))


def cmd_data(_):
    """Sul Mac: scarica i prezzi reali dei proxy ETF (gli stessi di GERVA-Q) per la ricerca su dati veri.
    Senza questo file la pipeline di ricerca usa dati SINTETICI e i risultati valgono solo come collaudo."""
    import pandas as pd
    from firm import paths
    from quantlab import data as QD
    try:
        import yfinance as yf
    except ImportError:
        sys.exit("serve yfinance: pip install yfinance")
    from quantlab import gervaq4 as G4
    tk = sorted(set(G4.TREND_SET + G4.SECTORS + G4.STOCKS + ["^VIX", "^IRX"]))
    raw = yf.download(tk, start="2004-01-01", auto_adjust=True, progress=False, group_by="column")
    close = raw["Close"].dropna(how="all").ffill(limit=5)
    os.makedirs(os.path.join(paths.VAR, "data"), exist_ok=True)
    close.to_pickle(os.path.join(paths.VAR, "data", "gq4_close.pkl"))      # universo completo per gervaq4
    close = close[[c for c in G4.TREND_SET if c in close]]
    rep = QD.quality_check(close)
    os.makedirs(os.path.join(paths.VAR, "data"), exist_ok=True)
    close.to_pickle(os.path.join(paths.VAR, "data", "etf_close.pkl"))
    print(f"{close.shape[0]} giorni x {close.shape[1]} ETF, impronta {QD.fingerprint(close)}, qualita' ok={rep.ok}")
    for pr in rep.problems[:10]:
        print("  ", pr)


def cmd_research(a):
    """python firm.py research gervaq4 : banco di prova dei miglioramenti contro la v3 (dati reali del Mac)."""
    import pandas as pd
    from firm import paths, trials, db, events, release
    from quantlab import gervaq4 as G4, data as QD
    p = os.path.join(paths.VAR, "data", "gq4_close.pkl")
    if not os.path.exists(p):
        sys.exit("mancano i dati reali: lancia prima `python firm.py data` sul Mac")
    close = pd.read_pickle(p)
    fp = QD.fingerprint(close)
    hyp = {"v3_riferimento": "Riferimento: GERVA-Q v3 riespressa nel motore quantlab (stessi segnali, deriva dei pesi).",
           "cash": "La quota non investita rende il tasso a breve via ETF UCITS monetario: premio quasi senza rischio.",
           "dyn": "Il momentum crolla nei rimbalzi dopo i bear market con vol alta (Daniel-Moskowitz 2016): frenarlo li.",
           "vix": "Il premio della fornitura di liquidita' cresce col VIX (Nagel 2012): dimensionare il reversal col VIX.",
           "erc": "Contributi di rischio uguali tra sleeve con covarianza ristretta: meno peso al rischio azionario comune.",
           "hrp": "HRP tra sleeve: diversificazione gerarchica senza invertire la covarianza (Lopez de Prado 2016).",
           "band5": "Banda di non intervento piu' larga: meno turnover e meno costi a parita' di esposizione.",
           "vt": "Vol target con stima di crisi: meno esposizione quando le correlazioni salgono (Longin-Solnik 2001).",
           "tutto": "Combinazione di tutti i miglioramenti: verifica che i guadagni si sommino e non si annullino."}
    reg = lambda v: trials.register("head_research", f"gervaq4:{v.name}", "gervaq4", v.params(), hyp[v.name])
    dsr = lambda tid, r: trials.record_result(tid, r, fp)["dsr"]
    res = G4.bench(dict(close=close, stocks=[s for s in G4.STOCKS if s in close]), register=reg, dsr_fn=dsr)
    out = os.path.join(paths.RESEARCH, "gervaq4")
    os.makedirs(out, exist_ok=True)
    md = res.to_markdown() + f"\n\nImpronta dei dati: {fp}\n"
    open(os.path.join(out, f"{db.today()}.md"), "w").write(md)
    events.publish("research.gervaq4", "head_research", dict(scelta=res.scelta, motivo=res.motivo, pbo=res.pbo["pbo"]))
    print(md)


def cmd_report(_):
    from firm import reports
    r = reports.daily()
    print(f"Report del {r['giorno']}: NAV {r['societa']['nav']:,.0f} EUR, {len(r['correzioni'])} correzioni proposte")
    for c in r["correzioni"]:
        print(f"  [{c['gravita']}] {c['cosa']} -> {c['azione']} ({c['chi']})")


def cmd_demo(_):
    from firm import demo
    print(json.dumps(demo.run(), ensure_ascii=False, indent=1, default=str))


def main():
    _load_env()
    ap = argparse.ArgumentParser(description="GERVA Capital")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ["init", "portal", "heartbeat", "run", "status", "verify", "demo", "release", "data", "research", "report",
                 "set-password", "ibkr-check"]:
        sp = sub.add_parser(name)
        sp.add_argument("--demo", action="store_true", help="usa il database dimostrativo var/demo/")
        if name == "research":
            sp.add_argument("what", nargs="?", default="gervaq4")
        if name == "release":
            sp.add_argument("--apply", metavar="ID", help="applica il rilascio (solo nella finestra, con la scelta di Andrea)")
    a = ap.parse_args()
    if a.cmd == "demo" or a.demo:
        # il demo non tocca MAI il database vero: tutto in var/demo/
        os.environ["GERVA_VAR"] = os.path.join(ROOT, "var", "demo")
        # anche i profili: le promozioni del demo non devono toccare i file versionati in agents/
        import shutil
        demo_agents = os.path.join(ROOT, "var", "demo", "agents")
        if not os.path.isdir(demo_agents):
            shutil.copytree(os.path.join(ROOT, "agents"), demo_agents)
        os.environ["GERVA_AGENTS"] = demo_agents
    if a.cmd not in ("init",):
        from firm import db, paths
        if not os.path.exists(paths.DB_PATH):
            cmd_init(a)
    globals()[f"cmd_{a.cmd.replace('-', '_')}"](a)


if __name__ == "__main__":
    main()
