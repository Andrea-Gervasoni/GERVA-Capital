"""
La plancia: il registro unico di TUTTE le operazioni, azioni (IBKR) e crypto (Alpaca), aperte e chiuse.

Ogni esecuzione (fill) finisce in `fills_all`, con CHI l'ha decisa (idea con la sua catena, capo desk, banco libero, modello GERVA-Q,
lungo periodo, segnale). Da li' il codice ricostruisce le operazioni con il metodo del costo medio: aperta, aumentata, ridotta, chiusa.
Per ogni operazione: lato (long/short), ingresso, uscita, risultato realizzato; se e' aperta, il guadagno del momento. E la storia
della decisione, che si legge cliccando sull'operazione.

Limiti dichiarati: le commissioni di Alpaca sulle crypto non sono ancora lette (il risultato crypto e' lordo); la "leva" si misura sul conto
(esposizione lorda / valore del conto), non su una singola operazione; i fill di IBKR sono quelli che TWS tiene (di solito gli ultimi giorni).
"""
from __future__ import annotations

import datetime as dt
import json

from . import charts, crypto_venue as V, db, registry

FALLBACK_USD_EUR = 1 / 1.12


# ---------------------------------------------------------------------------------------------- chi ha deciso
def attribute(symbol: str) -> dict:
    """Origine di un acquisto/vendita sul conto IBKR: l'idea in corso, il capo desk, il lungo periodo o il modello."""
    try:
        r = db.q("SELECT id, author FROM ideas WHERE status='in_corso' AND azione LIKE ? ORDER BY id DESC LIMIT 1", (f'%"simbolo": "{symbol}"%',))
        if r:
            return dict(kind="idea", ref=r[0]["id"], agent=r[0]["author"])
        ov = db.runtime_get("desk.overlay") or {}
        for desk, w in (ov.get("per_desk") or {}).items():
            if symbol in (w or {}):
                return dict(kind="idea" if desk == "idee" else "desk", desk=desk, agent=None if desk == "idee" else desk)
        from . import lt_committee, pod_zero
        if symbol in lt_committee.symbols():
            return dict(kind="lungo", agent="lt_head")
        eq = pod_zero.equity_model() or {}
        if symbol in (eq.get("weights") or {}):
            return dict(kind="modello", agent=None)
    except Exception:
        pass
    return dict(kind="sconosciuta", agent=None)


def record(venue: str, ext_id: str, ts: str, symbol: str, side: str, qty, price, fee, currency: str, status: str, order_id: str, origine: dict, agent=None) -> None:
    db.ex("INSERT OR IGNORE INTO fills_all(ext_id,venue,ts,symbol,side,qty,price,fee,currency,status,order_id,origine,agent) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
          (ext_id, venue, ts, symbol, side, qty, price, fee or 0.0, currency, status, order_id, json.dumps(origine, ensure_ascii=False), agent or origine.get("agent")))


# ---------------------------------------------------------------------------------------------- IBKR
def ingest_ibkr(fills) -> int:
    n = 0
    for f in fills:
        ex, c = f.execution, f.contract
        ts = ex.time.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if getattr(ex.time, "tzinfo", None) else str(ex.time)[:19].replace(" ", "T") + "Z"
        sym = c.localSymbol or c.symbol
        if db.one("SELECT 1 FROM fills_all WHERE ext_id=?", (ex.execId,)):
            continue
        fee = getattr(getattr(f, "commissionReport", None), "commission", 0.0) or 0.0
        record("ibkr", ex.execId, ts, sym, "buy" if str(ex.side).upper().startswith("B") else "sell", float(ex.shares), float(ex.price), float(fee),
               c.currency or "USD", "eseguito", str(ex.orderId), attribute(sym))
        n += 1
    return n


def snapshot_ibkr(ib, acct: str, vals: dict) -> None:
    """Prezzi di mercato e guadagno non realizzato delle posizioni (sola lettura) e leva del conto."""
    port = []
    for p in ib.portfolio(acct):
        port.append(dict(simbolo=p.contract.localSymbol or p.contract.symbol, qty=float(p.position), px=float(p.marketPrice), medio=float(p.averageCost),
                         non_realizzato=float(p.unrealizedPNL), valuta=p.contract.currency))
    db.runtime_set("ibkr.portfolio", dict(ts=db.now_iso(), posizioni=port))
    nav = float(vals.get(("NetLiquidation", "EUR")) or vals.get(("NetLiquidation", "BASE")) or 0)
    gross = float(vals.get(("GrossPositionValue", "EUR")) or vals.get(("GrossPositionValue", "BASE")) or 0)
    rate = vals.get(("ExchangeRate", "USD"))
    if rate:
        db.runtime_set("fx.usd_eur", float(rate))
    db.runtime_set("ibkr.account", dict(ts=db.now_iso(), nav=nav, lordo=gross, leva=round(gross / nav, 3) if nav else None))


# ---------------------------------------------------------------------------------------------- Alpaca
def record_alpaca_order(order_id: str, symbol: str, side: str, usd: float, origine: dict, agent=None) -> None:
    record("alpaca", f"alp:{order_id}", db.now_iso(), symbol, side, None, None, 0.0, "USD", "pendente", order_id, dict(origine, usd=round(usd, 2)), agent)


def sync_alpaca() -> int:
    """Aggiorna i fill degli ordini inviati (prezzo e quantita' veri) e fotografa conto e posizioni."""
    if not V.keys_ok():
        return 0
    n = 0
    try:
        acc = V.account()
        pos = []
        for p in V._req("GET", "/v2/positions"):
            sym = str(p["symbol"]).replace("/", "")
            sym = sym[:-3] if p.get("asset_class") == "crypto" and sym.endswith("USD") else sym
            pos.append(dict(simbolo=sym, qty=float(p["qty"]), px=float(p["current_price"]), medio=float(p["avg_entry_price"]), valore=float(p["market_value"]),
                            non_realizzato=float(p.get("unrealized_pl", 0))))
        eq = float(acc["equity"])
        if not db.runtime_get("alpaca.start_equity"):                # i conti paper Alpaca partono da 100.000 $: la base e' quella, se il valore e' vicino
            db.runtime_set("alpaca.start_equity", 100000.0 if abs(eq / 100000.0 - 1) < 0.10 else eq)
        db.runtime_set("alpaca.account", dict(ts=db.now_iso(), equity=eq, cash=float(acc.get("cash", 0)), last_equity=float(acc.get("last_equity") or eq),
                                              lordo=sum(abs(p["valore"]) for p in pos), posizioni=pos))
    except Exception:
        return 0
    if not db.runtime_get("blotter.alpaca_backfill"):             # una volta: gli ordini gia' eseguiti prima che la plancia esistesse
        try:
            mine = {r["order_id"]: r for r in db.q("SELECT order_id, id, agent FROM free_trades")}
            for o in V._req("GET", "/v2/orders?status=closed&limit=500&direction=asc"):
                if o.get("status") != "filled" or db.one("SELECT 1 FROM fills_all WHERE ext_id=?", (f"alp:{o['id']}",)):
                    continue
                sym = str(o["symbol"]).replace("/USD", "")
                ft = mine.get(o["id"])
                record("alpaca", f"alp:{o['id']}", str(o.get("filled_at") or o.get("submitted_at"))[:19] + "Z", sym, o["side"], float(o["filled_qty"]),
                       float(o["filled_avg_price"]), 0.0, "USD", "eseguito", o["id"], dict(kind="free", ref=ft["id"], agent=ft["agent"]) if ft else dict(kind="modello"),
                       ft["agent"] if ft else None)
                n += 1
            db.runtime_set("blotter.alpaca_backfill", db.now_iso())
        except Exception:
            pass
    for r in db.q("SELECT id, order_id, symbol FROM fills_all WHERE venue='alpaca' AND status='pendente'"):
        try:
            o = V._req("GET", f"/v2/orders/{r['order_id']}")
        except Exception:
            continue
        if o.get("status") == "filled":
            ts = str(o.get("filled_at") or db.now_iso())[:19] + "Z"
            db.ex("UPDATE fills_all SET status='eseguito', qty=?, price=?, ts=? WHERE id=?", (float(o["filled_qty"]), float(o["filled_avg_price"]), ts, r["id"]))
            n += 1
        elif o.get("status") in ("canceled", "expired", "rejected"):
            db.ex("UPDATE fills_all SET status=? WHERE id=?", (o["status"], r["id"]))
    return n


def sync_alpaca_throttled(seconds: int = 60) -> int:
    last = db.runtime_get("blotter.last_sync")
    now = dt.datetime.now(dt.timezone.utc)
    if last and (now - dt.datetime.fromisoformat(last.replace("Z", "+00:00"))).total_seconds() < seconds:
        return 0
    db.runtime_set("blotter.last_sync", now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    return sync_alpaca()


# ---------------------------------------------------------------------------------------------- operazioni (costo medio)
def usd_eur() -> float:
    return float(db.runtime_get("fx.usd_eur") or FALLBACK_USD_EUR)


def _eur(v, cur: str):
    return None if v is None else (v * usd_eur() if cur == "USD" else v)


def _live_prices() -> dict[tuple[str, str], float]:
    out = {}
    for p in (db.runtime_get("ibkr.portfolio") or {}).get("posizioni", []):
        out[("ibkr", p["simbolo"])] = p["px"]
    for p in (db.runtime_get("alpaca.account") or {}).get("posizioni", []):
        out[("alpaca", p["simbolo"])] = p["px"]
    return out


def trades(venue: str | None = None, stato: str | None = None) -> list[dict]:
    rows = db.q("SELECT * FROM fills_all WHERE status='eseguito' ORDER BY venue, symbol, ts, id")
    live = _live_prices()
    navs = dict(ibkr=(db.runtime_get("ibkr.account") or {}).get("nav") or 0.0,
                alpaca=((db.runtime_get("alpaca.account") or {}).get("equity") or 0.0) * usd_eur())
    out, cycles = [], {}
    for f in rows:
        k = (f["venue"], f["symbol"])
        c = cycles.get(k)
        sign = 1 if f["side"] == "buy" else -1
        qty = float(f["qty"])
        while qty > 1e-9:
            if c is None:
                c = dict(venue=f["venue"], symbol=f["symbol"], lato="long" if sign > 0 else "short", dir=sign, aperta_il=f["ts"], valuta=f["currency"], eq=0.0, ec=0.0,
                         xq=0.0, xv=0.0, real=0.0, fee=0.0, origine=json.loads(f["origine"] or "{}"), agent=f["agent"], fills=[], pos=0.0, qmax=0.0)
                cycles[k] = c
            c["fills"].append(f["id"]); c["fee"] += float(f["fee"] or 0)
            if sign == c["dir"]:
                c["eq"] += qty; c["ec"] += qty * f["price"]; c["pos"] += qty; c["qmax"] = max(c["qmax"], c["pos"]); qty = 0.0
            else:
                close = min(qty, c["pos"])
                avg = c["ec"] / c["eq"]
                c["real"] += (f["price"] - avg) * close * c["dir"]; c["xq"] += close; c["xv"] += close * f["price"]; c["pos"] -= close; qty -= close
                if c["pos"] <= 1e-9:
                    c["chiusa_il"] = f["ts"]; out.append(c); cycles[k] = None; c = None
    out += [c for c in cycles.values() if c]
    res = []
    for c in out:
        aperta = "chiusa_il" not in c
        avg = c["ec"] / c["eq"] if c["eq"] else None
        px = live.get((c["venue"], c["symbol"])) if aperta else None
        non_real = (px - avg) * c["pos"] * c["dir"] if (aperta and px and avg) else None
        cur = c["valuta"]
        entry_notional = (c["ec"]) if c["ec"] else 0.0
        nav = navs.get(c["venue"]) or 0.0
        t = dict(chiave=f"{c['venue']}:{c['symbol']}:{c['aperta_il']}", venue=c["venue"], simbolo=c["symbol"], lato=c["lato"], aperta=aperta, aperta_il=c["aperta_il"],
                 chiusa_il=c.get("chiusa_il"), qty=round(c["pos"] if aperta else c["qmax"], 6), ingresso=round(avg, 6) if avg else None,
                 uscita=round(c["xv"] / c["xq"], 6) if c["xq"] else None, attuale=px, valuta=cur, realizzato=round(c["real"], 2), realizzato_eur=round(_eur(c["real"], cur), 2),
                 non_realizzato=None if non_real is None else round(non_real, 2), non_realizzato_eur=None if non_real is None else round(_eur(non_real, cur), 2),
                 commissioni=round(c["fee"], 2), pnl_pct=round((c["real"] / (c["xq"] * avg)) * 100, 3) if (c["xq"] and avg) else (round((non_real / (c["pos"] * avg)) * 100, 3) if (non_real is not None and avg and c["pos"]) else None),
                 peso_conto_pct=round(_eur(entry_notional, cur) / nav * 100, 2) if nav else None, origine=c["origine"], agente=c["agent"],
                 durata_min=int((dt.datetime.fromisoformat((c.get("chiusa_il") or db.now_iso()).replace("Z", "+00:00")) - dt.datetime.fromisoformat(c["aperta_il"].replace("Z", "+00:00"))).total_seconds() // 60))
        if venue and t["venue"] != venue:
            continue
        if stato == "aperta" and not aperta or stato == "chiusa" and aperta:
            continue
        res.append(t)
    res.sort(key=lambda t: t["aperta_il"], reverse=True)
    return res


def totals() -> dict:
    """Valore dei due conti e il totale in euro, con la leva di ciascuno."""
    ib = db.runtime_get("ibkr.live") or {}
    ia = db.runtime_get("ibkr.account") or {}
    st = db.runtime_get("ibkr.start_nav") or {}
    al = db.runtime_get("alpaca.account") or {}
    ib_nav = float(ib.get("nav") or ia.get("nav") or 0.0)
    al_eq = float(al.get("equity") or 0.0)
    al_eur = al_eq * usd_eur()
    al0 = float(db.runtime_get("alpaca.start_equity") or al_eq or 0.0)
    ib0 = float(st.get("nav") or ib_nav)
    return dict(ibkr=dict(nav_eur=round(ib_nav, 2), pnl_eur=round(ib_nav - ib0, 2), leva=ia.get("leva")),
                alpaca=dict(equity_usd=round(al_eq, 2), nav_eur=round(al_eur, 2), pnl_eur=round((al_eq - al0) * usd_eur(), 2),
                            leva=round(al.get("lordo", 0) / al_eq, 3) if al_eq else None, disponibile=bool(al)),
                totale=dict(nav_eur=round(ib_nav + al_eur, 2), pnl_eur=round((ib_nav - ib0) + (al_eq - al0) * usd_eur(), 2)), cambio_usd_eur=round(usd_eur(), 5))


def overview(venue=None, stato=None) -> dict:
    t = trades(venue, stato)
    closed = [x for x in t if not x["aperta"]]
    return dict(totali=totals(), operazioni=t,
                riepilogo=dict(aperte=sum(1 for x in t if x["aperta"]), chiuse=len(closed), realizzato_eur=round(sum(x["realizzato_eur"] for x in closed), 2),
                               non_realizzato_eur=round(sum(x["non_realizzato_eur"] or 0 for x in t if x["aperta"]), 2),
                               vincenti=sum(1 for x in closed if x["realizzato"] > 0), perdenti=sum(1 for x in closed if x["realizzato"] < 0)))


# ---------------------------------------------------------------------------------------------- la storia di una decisione
def _who(agent_id):
    a = registry.get(agent_id) if agent_id else None
    return dict(id=agent_id, nome=(a or {}).get("name", agent_id), ruolo=(a or {}).get("role", ""))


def story(key: str) -> dict:
    t = next((x for x in trades() if x["chiave"] == key), None)
    if not t:
        return dict(ok=False)
    o = t["origine"] or {}
    steps = []
    kind = o.get("kind", "sconosciuta")
    if kind == "idea" and o.get("ref"):
        from . import ideas
        d = ideas.detail(int(o["ref"]))
        i = d.get("idea") or {}
        steps.append(dict(chi=_who(i.get("author")), cosa="ha avuto l'idea", testo=i.get("tesi"), evidenze=i.get("evidenze"), dati=dict(azione=i.get("azione"), probabilita_dichiarata=i.get("p_success"))))
        for h in i.get("history") or []:
            if h.get("cosa") == "portata su":
                steps.append(dict(chi=_who(h.get("chi")), cosa="ha controllato parametri e dati e l'ha portata su", testo=h.get("motivo"), evidenze=[h["miglioramenti"]] if h.get("miglioramenti") else [], dati=dict(sua_probabilita=h.get("p"))))
        m = d.get("riunione")
        if m:
            for p, v in (m.get("voti") or {}).items():
                steps.append(dict(chi=_who(p), cosa=f"in comitato: {v.get('posizione')} (fiducia {v.get('fiducia')})", testo=v.get("argomento"), evidenze=[], dati={}))
            steps.append(dict(chi=dict(id="comitato", nome="Comitato", ruolo=""), cosa=f"decisione della riunione #{m['id']}: {m.get('decisione')}", testo=f"punteggi {m.get('punteggi')}", evidenze=[], dati={}))
    elif kind == "free":
        r = db.one("SELECT * FROM free_trades WHERE id=?", (o.get("ref"),)) or {}
        steps.append(dict(chi=_who(o.get("agent") or t["agente"]), cosa="ha deciso da solo, nel banco libero (nessuna approvazione richiesta)", testo=r.get("motivo"),
                          evidenze=[], dati=dict(probabilita_dichiarata=r.get("p"), stop_pct=r.get("stop_pct"), obiettivo_pct=r.get("take_pct"), tenuta_fino=r.get("hold_until"))))
        try:
            from . import free_desk
            rr = free_desk.rules_detail()
            steps.append(dict(chi=dict(id="codice", nome="Regole di casa in vigore", ruolo=""), cosa="regole di casa al momento della decisione" if rr else "nessuna regola di casa in vigore",
                              testo="; ".join(f"{x['tipo']}={x['valore']}" for x in rr), evidenze=[], dati={}))
        except Exception:
            pass
    elif kind == "desk":
        p = (db.runtime_get("desk.proposals") or {}).get("per_desk", {}).get(o.get("desk"), {}).get(t["simbolo"], {})
        steps.append(dict(chi=_who(o.get("desk")), cosa="ha proposto la posizione come capo desk; il codice ha validato tetti e simboli e li ha scritti per GERVA-Q",
                          testo=p.get("motivo") or "(motivazione non registrata per questo giro)", evidenze=[], dati=dict(peso_pct=p.get("peso_pct"))))
    elif kind == "segnale":
        s = db.one("SELECT * FROM signals WHERE id=?", (o.get("ref"),)) or {}
        a = json.loads(s.get("analisi") or "{}")
        steps.append(dict(chi=_who("senior_crypto"), cosa="ha analizzato il segnale ricevuto", testo=a.get("motivo"), evidenze=a.get("rischi") or [], dati=dict(probabilita_obiettivo=a.get("probabilita_tp1"))))
        if a.get("veto"):
            steps.append(dict(chi=_who("cro"), cosa="ha controllato e " + ("BLOCCATO" if a["veto"].get("bloccato") else "non ha posto il veto"), testo=a["veto"].get("motivo"), evidenze=[], dati={}))
    elif kind == "lungo":
        steps.append(dict(chi=_who("lt_head"), cosa="rata del lungo periodo decisa dal comitato di lungo periodo", testo="vedi la sezione Riunioni (tipo 'lungo')", evidenze=[], dati={}))
    elif kind == "modello":
        steps.append(dict(chi=dict(id="gervaq", nome="GERVA-Q", ruolo="motore quantitativo"), cosa="posizione calcolata dal modello (trend e reversal), scalata con la leva del giorno",
                          testo="Nessun agente decide queste posizioni: sono l'uscita del modello a ogni chiusura.", evidenze=[], dati={}))
    else:
        steps.append(dict(chi=dict(id="", nome="Origine non tracciata", ruolo=""), cosa="operazione eseguita prima che la plancia esistesse o non attribuibile", testo="", evidenze=[], dati={}))
    les = db.one("SELECT * FROM lessons WHERE trade_key=?", (key,))
    return dict(ok=True, operazione=t, passi=steps, lezione=les)
