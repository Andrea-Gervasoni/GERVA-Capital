"""
Riga di comando del motore GERVA.

    python -m gerva research [--quick] [--refresh]   tutti i backtest -> research/v5/RESULTS.md
    python -m gerva demo                             fotografia per la dashboard costruita dal backtest (SIMULATO)
    python -m gerva cycle                            un giro del ciclo live (paper)
    python -m gerva run                              ciclo continuo
    python -m gerva supervise -- run                 ciclo continuo sotto supervisore (riavvio automatico)
    python -m gerva status                           stato del rischio, conto, ultimi eventi
    python -m gerva gates                            cancelli numerici paper -> reale
    python -m gerva kill "motivo"                    KILL: chiude tutto al prossimo giro e ferma il sistema
    python -m gerva reset-kill --confirm             toglie il KILL (riparte da HALTED)
    python -m gerva check-broker                     prova in sola lettura del collegamento al broker
    python -m gerva ai [--dry]                       una passata del livello AI: fonti -> desk -> regime -> decadimento -> overlay
    python -m gerva propose scheda.json              il consiglio di ricerca valuta un'ipotesi (backtest, critica, verdetto)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from .config import ROOT, load


def _runner():
    from .data import Store
    from .execution.broker import PaperBroker
    from .live.market import Market
    from .live.runner import Runner
    from .ops.journal import Journal
    s, limits, cfg = load()
    market = Market(Store(os.environ.get("GERVA_CACHE") or os.path.join(ROOT, "data_cache")))
    j = Journal(os.path.join(s.home, "journal.sqlite"))
    if s.mode == "alpaca-paper":
        from .execution.alpaca import AlpacaPaper
        broker = AlpacaPaper()
    else:
        p = cfg.get("paper") or {}
        broker = PaperBroker(j, market.last_prices, s.start_cash, p.get("fee"), p.get("slippage"), market.venue_of)
    return Runner(s, limits, broker, market, j)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "supervise":
        from .ops.supervisor import main as sup
        return sup([a for a in argv[1:] if a != "--"])
    ap = argparse.ArgumentParser(prog="python -m gerva", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("research")
    r.add_argument("--quick", action="store_true")
    r.add_argument("--refresh", action="store_true")
    d = sub.add_parser("demo")
    d.add_argument("--column", default="VT15")
    sub.add_parser("cycle")
    sub.add_parser("run")
    sub.add_parser("status")
    sub.add_parser("gates")
    k = sub.add_parser("kill")
    k.add_argument("reason", nargs="?", default="comando manuale")
    rk = sub.add_parser("reset-kill")
    rk.add_argument("--confirm", action="store_true")
    sub.add_parser("check-broker")
    ai = sub.add_parser("ai")
    ai.add_argument("--dry", action="store_true", help="non scrive l'overlay: mostra soltanto")
    pr = sub.add_parser("propose")
    pr.add_argument("spec", help="file JSON: family, universe, params, hypothesis, author")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if a.cmd == "research":
        from .research.run import main as research
        research(refresh=a.refresh, quick=a.quick)
        return 0
    if a.cmd == "demo":
        from .live import snapshot
        s, limits, _ = load()
        out = os.path.join(s.home, "snapshot.json")
        snapshot.write(out, snapshot.demo(os.path.join(ROOT, "research", "v5", "series.parquet"), a.column, s.start_cash, limits))
        print("scritto", out, "(SIMULATO: backtest)")
        return 0
    if a.cmd == "kill":
        from .ops.journal import Journal
        from .risk.engine import RiskEngine
        s, limits, _ = load()
        RiskEngine(limits, Journal(os.path.join(s.home, "journal.sqlite")), os.path.join(s.home, "KILL")).trigger_kill(a.reason)
        print("KILL registrato: al prossimo giro il sistema chiude tutto e si ferma.")
        return 0
    if a.cmd == "reset-kill":
        from .ops.journal import Journal
        from .risk.engine import RiskEngine
        s, limits, _ = load()
        if not a.confirm:
            print("serve --confirm. Prima togli a mano il file", os.path.join(s.home, "KILL"), "e capisci perche' era scattato.")
            return 1
        j = Journal(os.path.join(s.home, "journal.sqlite"))
        ok = RiskEngine(limits, j, os.path.join(s.home, "KILL")).reset_kill()
        j.set("killed.flattened", False)
        print("KILL azzerato: stato HALTED." if ok else "il file KILL e' ancora presente: toglilo a mano prima.")
        return 0 if ok else 1
    if a.cmd == "propose":
        from .agents import Council, StrategySpec
        from .research.run import Lab
        lab = Lab(ROOT)
        lab.load_daily()
        lab.load_crypto()
        raw = json.load(open(a.spec))
        out = Council(lab, os.path.join(ROOT, "research", "v5", "trials.jsonl")).review(StrategySpec(**raw))
        print(json.dumps(out, indent=1, ensure_ascii=False, default=str))
        return 0 if out["verdetto"]["passa"] else 1
    run = _runner()
    if a.cmd == "ai":
        from .ai import decay, desk, feeds, overlay, regime
        from .live import pipeline
        from .strategies.book import SLEEVES
        from .validation import metrics as M
        run.market.refresh()
        t = pipeline.build(run.market, run.l.vol_target, run.l.max_leverage)
        items, errs = feeds.collect()
        agents = desk.run(items, log=lambda rec: run.j.event("info", "ai.desk", json.dumps(rec, default=str)[:1900]))
        P = run.market.P["adj"]
        reg = regime.classify(P["^VIX"], P["^VIX3M"], t.port_ret, run.market.cclose["BTC"]).iloc[-1]
        import pandas as pd
        start = pd.Timestamp(run.j.get("start_ts") or 0, unit="s").normalize()
        live = {k: t.sleeve_ret[k][t.sleeve_ret.index >= start] for k in t.sleeve_ret}
        dec = decay.review(live, {k: M.summary(t.sleeve_ret[k], 0.0, 365).get("max_dd", -0.3) for k in t.sleeve_ret},
                           {k: 365 for k in SLEEVES})
        scale = bool((load()[2].get("ai") or {}).get("regime_scaling", False))      # spento: nei dati peggiora lo Sharpe
        raw = overlay.combine([agents, {"global": dict(mult=float(reg["mult"]) if scale else 1.0, motivo=f"regime {reg['state']}")},
                               {"sleeves": {k: v for k, v in dec.items() if v["mult"] < 1.0}}])
        print(json.dumps(dict(fonti=len(items), fonti_in_errore=errs, regime=reg["state"], decadimento=dec, overlay=raw), indent=1,
                         ensure_ascii=False, default=str))
        if not a.dry:
            overlay.save(os.path.join(run.s.home, "ai_overlay.json"), raw)
        return 0
    if a.cmd == "cycle":
        print(json.dumps(run.cycle(), indent=1, default=str))
        return 0
    if a.cmd == "run":
        run.j.event("info", "runner", "avvio del ciclo")
        return run.run_forever()
    if a.cmd == "check-broker":
        acct = run.broker.account()
        print(f"{run.broker.name}: patrimonio {acct.equity:,.2f}, cassa {acct.cash:,.2f}, posizioni {len(run.broker.positions())}")
        return 0
    if a.cmd == "status":
        j = run.j
        print("stato del rischio:", j.get("risk.state", "NORMAL"), "| massimo storico:", j.get("risk.high_water"))
        nav = j.nav_history()
        if nav:
            print(f"patrimonio: {nav[-1]['equity']:,.2f} | lorda {nav[-1]['gross']:.2f}x | rilevazioni: {len(nav)}")
        for e in j.events(10):
            print(f"  [{e['level']}] {e['component']}: {e['msg']}")
        return 0
    if a.cmd == "gates":
        import pandas as pd
        from .live import gates
        nav = pd.DataFrame([dict(x) for x in run.j.nav_history()])
        daily = pd.Series(dtype=float)
        if len(nav):
            nav["d"] = pd.to_datetime(nav["ts"], unit="s").dt.normalize()
            daily = nav.groupby("d")["equity"].last().pct_change().dropna()
        from .live import pipeline, snapshot
        try:                                              # serve il portafoglio simulato per il cancello "scostamento"
            run.market.refresh()
            run.targets = pipeline.build(run.market, run.l.vol_target, run.l.max_leverage)
        except Exception as e:
            print(f"  (dati non disponibili, scostamento non calcolato: {type(e).__name__})")
        g = gates.evaluate(run.j, daily, None, run.s.interval, snapshot.model_daily(run))
        for x in g:
            print(f"  [{'OK' if x['ok'] else '  '}] {x['name']}: {x['value']} (obiettivo {x['target']} {x['unit']})")
        print("TUTTI VERDI: si puo' proporre il passaggio al reale." if gates.all_green(g) else "Non tutti verdi: si resta in paper.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
