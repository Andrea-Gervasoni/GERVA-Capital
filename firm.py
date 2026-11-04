#!/usr/bin/env python3
"""
GERVA Capital — comando unico.

    python firm.py init         # crea DB, token di Andrea, organico, prove storiche di GERVA-Q
    python firm.py portal       # portale su http://127.0.0.1:8765 (solo locale)
    python firm.py heartbeat    # un battito: controlla condizioni e sveglia solo gli agenti necessari
    python firm.py run          # battito ogni N minuti (impostazione firm.heartbeat_minutes)
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
    print("GERVA Capital — portale su http://127.0.0.1:8765  (solo locale, Ctrl+C per chiudere)")
    uvicorn.run("portal.app:app", host="127.0.0.1", port=8765, log_level="warning")


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


def cmd_demo(_):
    from firm import demo
    print(json.dumps(demo.run(), ensure_ascii=False, indent=1, default=str))


def main():
    _load_env()
    ap = argparse.ArgumentParser(description="GERVA Capital")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ["init", "portal", "heartbeat", "run", "status", "verify", "demo", "release"]:
        sp = sub.add_parser(name)
        sp.add_argument("--demo", action="store_true", help="usa il database dimostrativo var/demo/")
        if name == "release":
            sp.add_argument("--apply", metavar="ID", help="applica il rilascio (solo nella finestra, con la scelta di Andrea)")
    a = ap.parse_args()
    if a.cmd == "demo" or a.demo:
        # il demo non tocca MAI il database vero: tutto in var/demo/
        os.environ["GERVA_VAR"] = os.path.join(ROOT, "var", "demo")
    if a.cmd not in ("init",):
        from firm import db, paths
        if not os.path.exists(paths.DB_PATH):
            cmd_init(a)
    globals()[f"cmd_{a.cmd}"](a)


if __name__ == "__main__":
    main()
