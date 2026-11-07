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
    port = int(os.environ.get("PORTAL_PORT", "8765"))      # cambiandola, aggiungere host:porta a PORTAL_ALLOWED_HOSTS
    print(f"GERVA Capital — portale su http://{bind}:{port}  (Ctrl+C per chiudere)")
    uvicorn.run("portal.app:app", host=bind, port=port, log_level="warning", proxy_headers=False, server_header=False)


def _research_longterm():
    """python firm.py research lungo : piano della quota di lungo periodo (AI) e quanto puo' far male."""
    import pandas as pd
    import yaml
    from firm import paths, db, gateway
    from quantlab import longterm as LT, gervaq4 as G4
    cfg = yaml.safe_load(open(os.path.join(paths.CONFIG, "longterm.yaml")))
    core = list(cfg["titoli"])
    ex = cfg.get("esplorativo", {"quota_nav": 0.0, "titoli": {}})
    expl = list(ex["titoli"])
    names = core + expl
    ring = {**{k: v["anello"] for k, v in cfg["titoli"].items()}, **{k: v["anello"] for k, v in ex["titoli"].items()}}
    import yfinance as yf
    raw = yf.download(names + ["EURUSD=X", "SPY"], start="2015-01-01", auto_adjust=True, progress=False,
                      group_by="column")["Close"].ffill(limit=5)
    nav = gateway.pod_zero_nav() if gateway.capital_source()["fonte"] == "IBKR" else 984_000.0
    src = "letto da IBKR" if gateway.capital_source()["fonte"] == "IBKR" else "984.000 EUR indicati da Andrea (IBKR non collegato qui)"
    q_core, q_expl = float(cfg["quota_nav"]), float(ex["quota_nav"])
    quota = q_core + q_expl
    rc = LT.basket_returns(raw, core)
    r = (q_core * rc + q_expl * LT.basket_returns(raw, expl)) / quota if expl else rc
    rep = LT.risk_report(r, nav * quota)
    spy = raw["SPY"].pct_change()
    corr_spy = LT.correlation_with(r, spy)
    eq = None
    gq = os.path.join(paths.VAR, "data", "gq4_close.pkl")
    if os.path.exists(gq):
        close = pd.read_pickle(gq)
        eq = G4.run_variant(dict(close=close, stocks=[x for x in G4.STOCKS if x in close]), G4.VARIANTS[0])
    corr_v3 = LT.correlation_with(r, eq) if eq is not None else float("nan")
    last = raw.iloc[-1]
    fx = float(last["EURUSD=X"])
    pl = pd.concat([LT.plan(nav, q_core, {k: float(last[k]) for k in core}, fx)] +
                   ([LT.plan(nav, q_expl, {k: float(last[k]) for k in expl}, fx)] if expl else []))
    lines = [f"# Quota di lungo periodo: infrastruttura AI ({db.today()})", "",
             f"Capitale: {nav:,.0f} EUR ({src}); quota {quota:.0%} = **{nav * quota:,.0f} EUR**: nucleo {q_core:.0%} su "
             f"{len(core)} titoli + esplorativo {q_expl:.0%} su {len(expl)}, pesi uguali dentro ogni parte. "
             "Nel conto entra con il rilascio v3.2 di GERVA-Q, in 3 rate mensili.", "",
             "## Piano di acquisto (azioni intere, prezzi dell'ultima chiusura)", "",
             "| Titolo | Anello della catena | Prezzo USD | Azioni | EUR investiti |", "|---|---|---|---|---|"]
    for k, x in pl.iterrows():
        lines.append(f"| {k} | {ring[k]} | {x.prezzo_usd:,.2f} | {int(x.azioni)} | {x.euro_investiti:,.0f} |")
    lines += ["", f"Totale investito: {pl.euro_investiti.sum():,.0f} EUR (il resto per arrotondamento resta in liquidita').", "",
              "## Quanto puo' far male (dal 2015, pesi uguali ribilanciati ogni anno; alcuni titoli quotati da meno tempo)", "",
              f"- volatilita' annua: {rep['vol']:.0%}",
              f"- anno peggiore: {rep['anno_peggiore']:.0%} ({rep['anno_peggiore_quale']}) = **{rep['anno_peggiore_eur']:,.0f} EUR** sulla quota",
              f"- caduta massima dal punto piu' alto: {rep['caduta_massima']:.0%} = **{rep['caduta_massima_eur']:,.0f} EUR** sulla quota",
              f"- giorno peggiore: {rep['giorno_peggiore']:.1%}",
              f"- correlazione con l'S&P 500: {corr_spy:.2f}; con il motore azionario della v3: {corr_v3:.2f}", "",
              "Il rendimento passato di questo paniere NON e' riportato come argomento: i titoli sono scelti oggi sapendo che hanno "
              "vinto, quindi il passato e' gonfiato dal senno di poi. Conta solo quanto puo' scendere.", "",
              "## Come entra nel conto",
              "- `live.py` di GERVA-Q vende tutto cio' che non e' nel suo obiettivo: questi titoli comprati a parte sarebbero venduti "
              "la sera stessa. La quota va quindi inserita nell'obiettivo di GERVA-Q (rilascio della domenica, con la tua scelta) "
              "oppure tenuta su un conto separato.",
              "- Nessuno stop-loss: e' una quota da tenere anni. Il rischio si controlla con la dimensione (5%), non con le uscite."]
    out = os.path.join(paths.RESEARCH, "lungo")
    os.makedirs(out, exist_ok=True)
    md = "\n".join(lines) + "\n"
    open(os.path.join(out, f"{db.today()}.md"), "w").write(md)
    print(md)


def _research_crypto():
    """python firm.py research crypto : banco della sleeve crypto della v3 contro 6 varianti (dati reali)."""
    import pandas as pd
    from firm import paths, trials, db
    from quantlab import crypto4 as C4, data as QD, gervaq4 as G4
    p = os.path.join(paths.VAR, "data", "crypto_close.pkl")
    if not os.path.exists(p):
        sys.exit("mancano i dati crypto: lancia prima `python firm.py data`")
    close = pd.read_pickle(p)
    fp = QD.fingerprint(close)
    hyp = {"v3_crypto": "Riferimento: sleeve crypto della v3 riespressa su candele giornaliere (H2 approssimato).",
           "cash": "La quota ferma della sleeve rende il tasso a breve: la crypto e' spesso flat.",
           "ibkr3": "Solo BTC/ETH/SOL nel trend: meno monete piccole, meno spread e rischio di liquidita'.",
           "slow": "Lookback piu' lunghi: meno operazioni, quindi meno costi a 0,23% per lato.",
           "vt": "Vol target sulla sleeve intera (40%): meno esposizione quando la volatilita' esplode.",
           "erc": "Trend e breakout a contributi di rischio uguali invece di 50/50.",
           "tutto": "Combinazione: verifica che i guadagni si sommino e non si annullino."}
    reg = lambda v: trials.register("senior_crypto", f"crypto4:{v.name}", "crypto4", v.params(), hyp[v.name])
    dsr = lambda tid, r: trials.record_result(tid, r, fp)["dsr"]
    res = C4.bench(dict(close=close), register=reg, dsr_fn=dsr, start_skip=200)
    chosen = next(v for v in C4.VARIANTS if v.name == res.scelta)
    lad = []
    for k in (1.0, 1.5, 2.0):
        r, rr = C4.run_variant(dict(close=close), chosen, scale=k, return_result=True)
        from quantlab import stats as QS
        pf = QS.performance(r.iloc[200:].values, periods=C4.TD)
        lad.append(f"| x{k:g} | {rr.daily['gross'].iloc[200:].mean():.0%} | {pf['Sharpe']:.2f} | {pf['CAGR']:.1%} | "
                   f"{pf['Vol']:.1%} | {pf['MaxDD']:.1%} |")
    md = (res.to_markdown().replace("GERVA-Q v4 — banco di prova contro la v3", "Zona ricerca crypto — sleeve crypto contro la v3")
          + f"\n\nDati: Yahoo, giornaliero, {close.index[0].date()} - {close.index[-1].date()}; impronta {fp}. "
          "H2 (breakout a 4 ore nella v3) approssimato su candele giornaliere.\n\n"
          f"## Scala del rischio ({chosen.name}), senza leva\n\n| Livello | Investito medio | Sharpe | CAGR | Vol | MaxDD |\n"
          "|---|---|---|---|---|---|\n" + "\n".join(lad) + "\n")
    out = os.path.join(paths.RESEARCH, "crypto")
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, f"{db.today()}.md"), "w").write(md)
    print(md)


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


def cmd_observe(_):
    """Osservatore del conto della sfida, da solo: sul server gira in un container senza agenti, senza internet,
    l'unico che raggiunge il gateway della sfida. Scrive solo l'istantanea (conto mascherato) e il NAV."""
    from firm import ibkr
    every = float(os.environ.get("IBKR_OBSERVE_MINUTES", "5"))
    while True:
        s = ibkr.observe_challenge()
        print(time.strftime("%H:%M"), "ok" if s.get("ok") else s.get("errore"), flush=True)
        time.sleep(60 * every)


def cmd_check_backtest(a):
    """Verifica di un backtest visto altrove: quanto puo' essere fortuna (quantlab/luck.py)."""
    from quantlab import luck
    kw = {k: getattr(a, k) for k in ("sharpe_annual", "n_obs", "periods", "n_trials", "skew", "kurt", "wins", "trades",
                                     "claimed_hit_rate", "payoff_ratio", "edge_per_trade", "cost_per_trade")
          if getattr(a, k, None) is not None}
    r = luck.check(**kw)
    for line in r["giudizio"]:
        print("- " + line)
    print(json.dumps({k: v for k, v in r.items() if k != "giudizio"}, ensure_ascii=False, indent=1, default=str))


def cmd_shadow(_):
    """Aggiorna il portafoglio ombra (v4 contro v3, in avanti, senza ordini) e ne stampa il bilancio."""
    from firm import shadow
    print(json.dumps(shadow.update(), ensure_ascii=False, indent=1, default=str))


def cmd_comitato_lungo(_):
    """Valuta ora le rate della quota di lungo periodo e scrive il piano che GERVA-Q esegue (var/longterm_plan.json)."""
    from firm import lt_committee
    print(json.dumps(lt_committee.run(), ensure_ascii=False, indent=1, default=str))


def cmd_live_nav(_):
    """Tiene aperta una connessione in SOLA LETTURA a TWS e aggiorna il valore del conto ogni pochi secondi."""
    from firm import ibkr
    print("valore del conto in tempo reale: Ctrl+C per fermare")
    ibkr.live_loop()


def cmd_crypto_venue(a):
    """Prova la sede crypto Alpaca (paper): saldo, piano degli ordini. --attiva la accende, --invia manda gli ordini ora."""
    from firm import crypto_venue as V, settings
    cap = settings.AndreaCapability(settings.ensure_token())
    if a.chiavi:
        import getpass
        print("Incolla le chiavi del conto PAPER di Alpaca. Non si vedono mentre le scrivi e non finiscono in nessun registro.")
        try:
            k = getpass.getpass("Key ID (inizia con PK): ")
            sec = getpass.getpass("Secret Key: ")
            V.save_keys(k, sec, os.path.join(ROOT, ".env"))
        except (ValueError, EOFError, KeyboardInterrupt) as e:
            print(f"Non salvato: {e}"); return
        os.environ["ALPACA_PAPER_KEY"], os.environ["ALPACA_PAPER_SECRET"] = k.strip(), sec.strip()
        print("Salvate in .env (permessi 600). Provo il collegamento...")
        try:
            acc = V.account()
            print(f"OK: conto paper {acc.get('account_number', '?')} | stato {acc.get('status')} | valore {float(acc['equity']):,.2f} USD")
            print("Per accendere le crypto su Alpaca:  .venv/bin/python firm.py crypto-venue --attiva")
        except Exception as e:
            print(f"Le chiavi sono salvate ma il collegamento non riesce: {str(e)[:160]}")
        return
    if a.attiva:
        settings.set("crypto.venue", "alpaca", cap)
        print("sede crypto Alpaca (paper) ATTIVA: da ora i segnali accettati e il modello crypto si eseguono li', a ogni battito")
    if not (os.environ.get("ALPACA_PAPER_KEY") and os.environ.get("ALPACA_PAPER_SECRET")):
        print("Mancano ALPACA_PAPER_KEY e ALPACA_PAPER_SECRET nel file .env (le chiavi del conto PAPER di Alpaca)."); return
    r = V.rebalance(dry=not a.invia) if V.configured() else dict(ok=False, nota="accendila con: firm.py crypto-venue --attiva")
    print(json.dumps(r, ensure_ascii=False, indent=1))


def cmd_idee(a):
    """Idee degli agenti: senza opzioni fa un giro adesso (cercano, i superiori valutano, il comitato vota); --lista le mostra."""
    from firm import ideas
    if not a.lista:
        print(json.dumps(ideas.daily(), ensure_ascii=False, indent=1, default=str))
    for i in ideas.listing(25):
        act = i["azione"] or {}
        what = f"{act.get('simbolo', '')} {act.get('peso_pct', '')}%" if i["kind"] == "posizione" else f"{act.get('chiave', '')} -> {act.get('valore', '')}"
        res = f" | alpha {i['result']['alpha']:+.1%} ({i['result']['motivo']})" if i["result"] and "alpha" in i["result"] else ""
        print(f"#{i['id']:<3} {i['status']:<14} {i['author']:<16} {i['kind']:<9} {i['title'][:50]:<50} {what}{res}")


def cmd_regole(a):
    """Regole cambiate dal comitato (con vecchio e nuovo valore); --annulla ID ripristina il valore precedente."""
    from firm import rules
    if a.annulla:
        print(rules.revert(a.annulla)); return
    for r in rules.history(30):
        print(f"#{r['id']:<3} {r['ts'][:16]} {r['status']:<9} {r['key']:<28} {r['old']} -> {r['new']}  ({r['who']})")


def cmd_imposta(a):
    """Cambia un'impostazione dal Mac (come dal pannello Impostazioni): firm.py imposta volmgmt.enabled true"""
    from firm import settings
    try:
        val = json.loads(a.valore)
    except ValueError:
        val = a.valore
    print(settings.set(a.chiave, val, settings.AndreaCapability(settings.ensure_token())))


def cmd_volgest(_):
    """Leva fissa contro leva gestita per volatilita' sui dati veri (stesso rischio medio), a edge pieno e dimezzato."""
    from firm import fundrisk
    pf = fundrisk.portfolio()
    if not pf["pesi"]:
        print("GERVA-Q non ha ancora scritto i suoi pesi."); return
    print("moltiplicatore di oggi:", fundrisk.vol_scale(pf["pesi"]))
    for h in (1.0, 0.5):
        r = fundrisk.vol_managed_test(pf["pesi"], haircut=h)
        if not r.get("ok"):
            print(r); return
        print(f"\n== leva media {r['leva']}x | edge {'pieno' if h == 1.0 else 'dimezzato'} | {r['giorni']} giorni dal {r['dal']}")
        print(" tipo      crescita_log  sharpe   vol    dd_max  peggior_mese")
        for k, v in r["risultati"].items():
            print(f" {k:<9} {v['crescita_log']:>11.1%} {v['sharpe']:>7.2f} {v['vol']:>6.1%} {v['dd_max']:>8.1%} {v['peggior_mese']:>11.1%}")
    print("\nPer accenderla: dal portale, Impostazioni, volmgmt.enabled = true (poi serve il rilascio v3.7 di GERVA-Q).")


def cmd_kelly(_):
    """Quale leva fa crescere di piu' il fondo (Kelly) con i dati storici veri, a edge pieno e a mezzo edge."""
    from firm import fundrisk
    pf = fundrisk.portfolio()
    if not pf["pesi"]:
        print("GERVA-Q non ha ancora scritto i suoi pesi."); return
    for h in (1.0, 0.5):
        g = fundrisk.growth_curve(pf["pesi"], haircut=h)
        if not g.get("ok"):
            print(g); return
        print(f"\n== edge {'pieno' if h == 1.0 else 'dimezzato'} | rendimento {g['mu_ann']:.1%} vol {g['sigma_ann']:.1%} | Kelly empirico {g['kelly_empirico']}x, "
              f"formula {g['kelly_formula']}x, migliore con freno {g['migliore_con_freno']}x (p_kill<= {g['max_p_kill']:.0%}) | {g['giorni']} giorni dal {g['dal']}")
        print(" leva  crescita_log  mediana1a  vol    p_kill  p_perdita  dd_storico")
        for r in g["righe"]:
            print(f" {r['leva']:>4}x {r['crescita_log']:>11.1%} {r['mediana']:>10.1%} {r['vol_ann']:>6.1%} {r['p_kill']:>7.1%} {r['p_perdita']:>9.1%} {r['dd_storico']:>10.1%}")


def cmd_aspettative(_):
    """Scrive una NUOVA versione delle aspettative del fondo (le precedenti restano): da usare quando cambia la strategia."""
    from firm import expectations
    print(json.dumps(expectations.register(note="registrazione manuale di Andrea"), ensure_ascii=False, indent=1))


def cmd_telegram_login(a):
    """Accesso a Telegram, una volta sola, sul tuo Terminale (telefono e codice non passano da nessun altro).
    Con --sms il codice arriva per SMS invece che nell'app."""
    from firm import telegram_feed
    telegram_feed.login(sms=getattr(a, "sms", False), qr=getattr(a, "qr", False))


def cmd_telegram(_):
    """Ascolta le sale segnali di Telegram (sola lettura) e le passa alla sala segnali."""
    from firm import telegram_feed
    telegram_feed.run()


def cmd_desk(_):
    """Fa lavorare subito i capi desk: propongono posizioni, il codice valida e scrive var/firm_overlay.json per GERVA-Q."""
    from firm import desk
    print(json.dumps(desk.cycle(), ensure_ascii=False, indent=1, default=str))


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
    # crypto (zona di ricerca crypto): candele giornaliere Yahoo, 365 giorni l'anno; il tasso a breve si trascina
    from quantlab import crypto4 as C4
    raw = yf.download(list(C4.YAHOO.values()) + ["^IRX"], start="2017-01-01", auto_adjust=True, progress=False,
                      group_by="column")["Close"]
    raw = raw.rename(columns={v: k for k, v in C4.YAHOO.items()})
    coins = [c for c in C4.COINS if c in raw]
    cc = raw[coins].dropna(how="all")
    cc["^IRX"] = raw["^IRX"].reindex(cc.index).ffill().bfill()
    cc.to_pickle(os.path.join(paths.VAR, "data", "crypto_close.pkl"))
    print(f"crypto: {cc.shape[0]} giorni x {len(coins)} monete dal {cc.index[0].date()}, impronta {QD.fingerprint(cc)}")
    # titoli del lungo periodo che non sono nel paniere di ricerca (ASML, TSM, COHR, ...): servono ai grafici e al rischio del fondo
    try:
        from firm import lt_committee
        full = pd.read_pickle(os.path.join(paths.VAR, "data", "gq4_close.pkl"))
        extra = [x for x in lt_committee.symbols() if x not in full.columns]
        if extra:
            ex = yf.download(extra, start="2015-01-01", auto_adjust=True, progress=False, group_by="column")["Close"]
            if hasattr(ex, "to_frame") and getattr(ex, "ndim", 2) == 1:
                ex = ex.to_frame(extra[0])
            ex = ex.dropna(how="all")
            ex.to_pickle(os.path.join(paths.VAR, "data", "extra_close.pkl"))
            print(f"extra (lungo periodo): {ex.shape[1]} titoli, {ex.shape[0]} giorni")
    except Exception as e:                          # un titolo mancante non deve fermare il resto
        print(f"extra non scaricati: {str(e)[:80]}")


def cmd_research(a):
    """python firm.py research gervaq4 : banco di prova dei miglioramenti contro la v3 (dati reali del Mac)."""
    import pandas as pd
    from firm import paths, trials, db, events, release
    from quantlab import gervaq4 as G4, data as QD
    if a.what == "crypto":
        return _research_crypto()
    if a.what == "lungo":
        return _research_longterm()
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
    chosen = next(v for v in G4.VARIANTS if v.name == res.scelta)
    md += "\n" + G4.ladder_markdown(G4.risk_ladder(dict(close=close, stocks=[s for s in G4.STOCKS if s in close]), chosen),
                                    chosen.name) + "\n"
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
                 "set-password", "ibkr-check", "observe", "check-backtest", "shadow", "comitato-lungo", "desk", "live-nav", "aspettative", "kelly", "volgest", "idee", "regole", "imposta", "crypto-venue", "telegram-login", "telegram"]:
        sp = sub.add_parser(name)
        sp.add_argument("--demo", action="store_true", help="usa il database dimostrativo var/demo/")
        if name == "idee":
            sp.add_argument("--lista", action="store_true", help="mostra solo le idee, senza fare un giro")
        if name == "regole":
            sp.add_argument("--annulla", type=int, default=0, help="ripristina il valore precedente della regola con questo numero")
        if name == "imposta":
            sp.add_argument("chiave"); sp.add_argument("valore")
        if name == "crypto-venue":
            sp.add_argument("--chiavi", action="store_true", help="chiede le chiavi paper nel terminale (nascoste) e le salva in .env")
            sp.add_argument("--attiva", action="store_true", help="accende la sede crypto Alpaca (paper)")
            sp.add_argument("--invia", action="store_true", help="invia davvero gli ordini ora (senza: solo il piano)")
        if name == "telegram-login":
            sp.add_argument("--qr", action="store_true", help="accesso con codice QR (nessun codice da ricevere)")
            sp.add_argument("--sms", action="store_true", help="manda il codice per SMS invece che nell'app di Telegram")
        if name == "research":
            sp.add_argument("what", nargs="?", default="gervaq4")
        if name == "check-backtest":
            for flag, typ, h in [("--sharpe", float, "Sharpe annuo dichiarato"), ("--obs", int, "osservazioni (giorni, trade...)"),
                                 ("--periods", int, "osservazioni per anno (252 giorni, 365 crypto...)"),
                                 ("--trials", int, "varianti provate (se non lo dicono, prova 10, 100, 1000)"),
                                 ("--skew", float, "asimmetria"), ("--kurt", float, "curtosi (3 = normale)"),
                                 ("--wins", int, "trade vinti"), ("--trades", int, "trade totali"),
                                 ("--hit-rate", float, "percentuale di vincite dichiarata (0-1)"),
                                 ("--payoff", float, "guadagno medio / perdita media"),
                                 ("--edge", float, "margine medio per trade (frazione)"), ("--cost", float, "costo per trade (frazione)")]:
                dest = {"--sharpe": "sharpe_annual", "--obs": "n_obs", "--trials": "n_trials", "--hit-rate": "claimed_hit_rate",
                        "--payoff": "payoff_ratio", "--edge": "edge_per_trade", "--cost": "cost_per_trade"}.get(flag, flag[2:])
                sp.add_argument(flag, type=typ, dest=dest, help=h)
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
        # e i limiti di rischio: salvarli dal portale demo NON deve toccare config/risk_limits.yaml
        demo_risk = os.path.join(ROOT, "var", "demo", "risk_limits.yaml")
        if not os.path.exists(demo_risk):
            shutil.copy(os.path.join(ROOT, "config", "risk_limits.yaml"), demo_risk)
        os.environ["GERVA_RISK_FILE"] = demo_risk
        os.environ["GERVA_KILL_FILE"] = os.path.join(ROOT, "var", "demo", "KILL")
    if a.cmd not in ("init", "set-password", "check-backtest"):            # set-password non tocca stato (e gira su immagini read-only)
        from firm import db, paths
        if not os.path.exists(paths.DB_PATH):
            cmd_init(a)
    globals()[f"cmd_{a.cmd.replace('-', '_')}"](a)


if __name__ == "__main__":
    main()
