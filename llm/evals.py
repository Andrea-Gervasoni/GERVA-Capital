"""
Valutatore dei prompt (docs/PROMPT_ENGINEERING.md §5).

    python -m llm.evals                 # tutti gli agenti; senza chiave API = solo validita' dello schema
    python -m llm.evals news_analyst    # un agente
    GERVA_EVALS_LIVE=1 python -m llm.evals   # con la chiave: chiamate vere (costano, passano dal Governor)

Controlli deterministici sul JSON di output (percorso "a.0.b"):
  valore esatto | {in: [..]} | {min: x} | {max: x} | {contains: s} | {not_contains: [..]} |
  {len_min: n} | {len_max: n} | {min_len: n} (stringa) | {any_field: {k: v}} | {all_field: {k: v}}
Ogni modifica a un prompt si adotta solo se il punteggio migliora senza peggiorare i casi trappola.
"""
from __future__ import annotations

import glob
import json
import os
import sys

import yaml

from firm import paths, workflows as W

WORKFLOWS = {
    "news_triage": ("Fai il triage delle notizie.", W.NEWS_TRIAGE, "untrusted"),
    "fact_check": ("Verifica ogni notizia su una seconda fonte indipendente tra i candidati.", W.FACT_CHECK, "untrusted"),
    "bulletin": ("Scrivi il bollettino usando SOLO notizie verificate.", W.BULLETIN, "data"),
    "validation": ("Cerca di rompere questa strategia.", W.VALIDATION, "data"),
    "cro_review": ("Rivedi lo stato di rischio.", W.CRO_REVIEW, "data"),
    "ceo_plan": ("Scomponi l'ordine di Andrea in compiti per i manager.", W.CEO_PLAN, "data"),
    "senior_report": ("Riporta i risultati della prova copiando i numeri.", W.SENIOR_REPORT, "data"),
    "manager_work": ("Esegui il compito ricevuto.", W.MANAGER_WORK, "data"),
    "pod_decision": ("Decidi se seguire i pesi target del segnale.", W.POD_DECISION, "data"),
}


def _get(o, path: str):
    for part in path.split("."):
        if isinstance(o, list):
            i = int(part)
            if i >= len(o):
                return None
            o = o[i]
        elif isinstance(o, dict):
            o = o.get(part)
        else:
            return None
    return o


def check(out: dict, checks: dict) -> list[str]:
    fails = []
    for path, cond in checks.items():
        v = _get(out, path)
        if not isinstance(cond, dict):
            ok = v == cond
        else:
            ok = True
            for op, x in cond.items():
                if op == "in":
                    ok &= v in x
                elif op == "min":
                    ok &= isinstance(v, (int, float)) and v >= x
                elif op == "max":
                    ok &= isinstance(v, (int, float)) and v <= x
                elif op == "contains":
                    ok &= v is not None and x in v
                elif op == "not_contains":
                    ok &= all(s not in json.dumps(v, ensure_ascii=False) for s in x)
                elif op == "len_min":
                    ok &= isinstance(v, list) and len(v) >= x
                elif op == "len_max":
                    ok &= isinstance(v, list) and len(v) <= x
                elif op == "min_len":
                    ok &= isinstance(v, str) and len(v) >= x
                elif op == "any_field":
                    ok &= isinstance(v, list) and any(all(e.get(k) == val for k, val in x.items()) for e in v)
                elif op == "all_field":
                    ok &= isinstance(v, list) and all(all(e.get(k) == val for k, val in x.items()) for e in v)
        if not ok:
            fails.append(f"{path}: atteso {cond}, ottenuto {json.dumps(v, ensure_ascii=False)[:80]}")
    return fails


def run_file(f: str, live: bool) -> dict:
    from llm import runtime
    spec = yaml.safe_load(open(f))
    task, schema, mode = WORKFLOWS[spec["workflow"]]
    res = []
    for c in spec["cases"]:
        kw = dict(untrusted=c.get("untrusted")) if mode == "untrusted" else dict(data=c.get("data", {}))
        r = runtime.call(spec["agent"], task, schema=schema, purpose=f"eval:{c['id']}", **kw)
        if not r["ok"]:
            res.append(dict(id=c["id"], ok=False, fails=[r["motivo"]], tipo=c["difficolta"]))
            continue
        fails = [] if r.get("simulato") and not live else check(r["output"], c.get("check", {}))
        res.append(dict(id=c["id"], ok=not fails, fails=fails, tipo=c["difficolta"], simulato=r.get("simulato")))
    n = len(res)
    traps = [x for x in res if x["tipo"] == "trappola"]
    return dict(agente=spec["agent"], casi=n, superati=sum(x["ok"] for x in res),
                trappole=f"{sum(x['ok'] for x in traps)}/{len(traps)}", dettagli=res)


def main(argv):
    live = os.environ.get("GERVA_EVALS_LIVE") == "1"
    files = sorted(glob.glob(os.path.join(paths.EVALS, "*.yaml")))
    if len(argv) > 1:
        files = [f for f in files if os.path.basename(f).startswith(argv[1])]
    for f in files:
        r = run_file(f, live)
        if live:
            print(f"{r['agente']:18s} {r['superati']}/{r['casi']} casi superati, trappole {r['trappole']}")
        else:
            print(f"{r['agente']:18s} schema valido {r['superati']}/{r['casi']} — contenuto NON valutato "
                  "(simulazione: serve ANTHROPIC_API_KEY e GERVA_EVALS_LIVE=1)")
        for d in r["dettagli"]:
            if not d["ok"]:
                print("   x", d["id"], "; ".join(d["fails"])[:160])


if __name__ == "__main__":
    sys.path.insert(0, paths.ROOT)
    main(sys.argv)
