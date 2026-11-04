"""
Gateway di Esecuzione (DECISIONS D5) — unico punto di accesso al broker, codice deterministico.

    submit_order(pod, agente, strumento, lato, quantita', motivazione, orizzonte)

Controlli in ordine (il primo che fallisce respinge l'ordine con il motivo):
  KILL · modalita' paper · pod attivo e dell'agente · strumento ammesso · niente short ·
  ordine minimo · fat-finger · prezzo di riferimento · orari · drawdown del pod ·
  lorda del pod · concentrazione · lorda di societa' · quota crypto · costo stimato.

Sub-ledger: il broker vede un conto solo; qui si attribuiscono fill, posizioni e P&L a ogni pod.
flush() compensa internamente gli ordini opposti di pod diversi (zero commissioni) e manda al
broker solo il netto. Le credenziali (porta di IB Gateway) restano in questo modulo e in .env.
Il Pod Zero NON passa di qui: continua a usare live.py e crypto_live.py di GERVA-Q.
"""
from __future__ import annotations

import datetime as dt
import os
from collections import defaultdict

from . import db, events, risk, pods
from . import settings as S
from quantlab import costs as QC

START_NAV_EUR = 100_000.0          # REGOLE_SFIDA §1: capitale iniziale del conto paper

COST_BY_KIND = {"crypto": QC.IBKR_CRYPTO, "etf_ucits": QC.UCITS_ETF, "etc": QC.UCITS_ETF,
                "stock": QC.US_LARGE_CAP}


# ---------------------------------------------------------------------------
# Prezzi e anagrafica (aggiornati dal Data Engineer o, nel demo, dal simulatore)
# ---------------------------------------------------------------------------
def set_price(instrument: str, price: float, kind: str, ts: str | None = None):
    db.runtime_set(f"px:{instrument}", dict(price=float(price), kind=kind, ts=ts or db.now_iso()))


def quote(instrument: str) -> dict | None:
    return db.runtime_get(f"px:{instrument}")


# ---------------------------------------------------------------------------
# Libri contabili
# ---------------------------------------------------------------------------
def positions(pid: str) -> dict[str, float]:
    pos = defaultdict(float)
    for f in db.q("SELECT instrument, side, qty FROM fills WHERE pod=?", (pid,)):
        pos[f["instrument"]] += f["qty"] if f["side"] == "BUY" else -f["qty"]
    return {k: v for k, v in pos.items() if abs(v) > 1e-12}


def pod_book(pid: str) -> dict:
    p = pods.get(pid)
    base = START_NAV_EUR * float(S.get("pods.initial_capital_frac"))
    cash_flow, fees = 0.0, 0.0
    for f in db.q("SELECT side, qty, price, fee FROM fills WHERE pod=?", (pid,)):
        cash_flow += (-1 if f["side"] == "BUY" else 1) * f["qty"] * f["price"]
        fees += f["fee"]
    pos = positions(pid)
    mv = {k: q * (quote(k) or {"price": 0})["price"] for k, q in pos.items()}
    pnl = cash_flow - fees + sum(mv.values())
    nav = base + pnl
    marks = [r["nav"] for r in db.q("SELECT nav FROM nav_marks WHERE pod=?", (pid,))]
    peak = max(marks + [nav, base])
    allowed = float(p["capital_frac"]) * firm_nav_estimate() if p else 0.0
    gross_eur = sum(abs(v) for v in mv.values())
    return dict(pod=pid, nav=nav, base=base, pnl=pnl, fees=fees, peak=peak, drawdown=nav / peak - 1,
                capitale_ammesso=allowed, lorda_eur=gross_eur,
                lorda=gross_eur / allowed if allowed > 0 else (0.0 if gross_eur == 0 else float("inf")),
                posizioni={k: dict(qty=q, valore=mv[k]) for k, q in pos.items()})


def pod_zero_nav() -> float:
    r = db.one("SELECT nav FROM nav_marks WHERE pod='pod_zero' ORDER BY day DESC LIMIT 1")
    if r:
        return r["nav"]
    p = pods.get("pod_zero")
    return START_NAV_EUR * (p["capital_frac"] if p else 0.85)


def firm_nav_estimate() -> float:
    navs = [pod_zero_nav()]
    for p in db.q("SELECT id FROM pods WHERE id!='pod_zero'"):
        base = START_NAV_EUR * float(S.get("pods.initial_capital_frac"))
        cash = sum((-1 if f["side"] == "BUY" else 1) * f["qty"] * f["price"] - f["fee"]
                   for f in db.q("SELECT side,qty,price,fee FROM fills WHERE pod=?", (p["id"],)))
        mv = sum(q * (quote(k) or {"price": 0})["price"] for k, q in positions(p["id"]).items())
        navs.append(base + cash + mv)
    return float(sum(navs))


def firm_book() -> dict:
    nav = firm_nav_estimate()
    from . import pod_zero
    pz_gross = pod_zero.gross_fraction() * pod_zero_nav()
    gross = pz_gross + sum(pod_book(p["id"])["lorda_eur"] for p in pods.all_pods() if p["id"] != "pod_zero")
    marks = [r["nav"] for r in db.q("SELECT nav FROM nav_marks WHERE pod='firm'")]
    return dict(nav=nav, peak=max(marks + [nav, START_NAV_EUR]), gross=gross / nav if nav > 0 else 0.0,
                pnl=nav - START_NAV_EUR)


def mark_day(day: str | None = None):
    day = day or db.today()
    for p in pods.all_pods():
        nav = pod_zero_nav() if p["id"] == "pod_zero" else pod_book(p["id"])["nav"]
        db.ex("INSERT OR REPLACE INTO nav_marks(day,pod,nav,capital,gross) VALUES(?,?,?,?,?)",
              (day, p["id"], nav, p["capital_frac"], 0.0))
    fb = firm_book()
    db.ex("INSERT OR REPLACE INTO nav_marks(day,pod,nav,capital,gross) VALUES(?,?,?,?,?)",
          (day, "firm", fb["nav"], 1.0, fb["gross"]))


# ---------------------------------------------------------------------------
# Controlli pre-trade
# ---------------------------------------------------------------------------
def _kind(instrument: str, lim: dict) -> str | None:
    q = quote(instrument)
    if q:
        return q["kind"]
    if instrument.upper() in lim["instruments"]["crypto_allowed"]:
        return "crypto"
    return None


def _checks(pod: str, agent: str, instrument: str, side: str, qty: float, ref_price: float | None,
            now: dt.datetime) -> tuple[list[str], dict]:
    lim = S.risk_limits()
    why: list[str] = []
    ctx: dict = {}
    if risk.kill_active():
        return ["KILL attivo"], ctx
    if S.get("firm.mode") != "paper":
        return ["modalita' diversa da paper: bloccato"], ctx
    p = pods.get(pod)
    if not p or pod == "pod_zero":
        return ["pod inesistente (il Pod Zero usa live.py)"], ctx
    if p["status"] not in ("attivo", "ridotto"):
        return [f"pod {pod} {p['status']}"], ctx
    if p["head"] != agent and pods.pod_of_agent(agent) != pod:
        return [f"l'agente {agent} non gestisce il pod {pod}"], ctx
    side = side.upper()
    if side not in ("BUY", "SELL") or not (qty > 0):
        return ["lato o quantita' non validi"], ctx
    kind = _kind(instrument, lim)
    if kind is None:
        return [f"strumento sconosciuto: {instrument}"], ctx
    if kind in lim["instruments"]["forbidden_kinds"] or kind not in lim["instruments"]["allowed_kinds"]:
        return [f"tipo di strumento non ammesso: {kind}"], ctx
    if kind == "crypto" and instrument.upper() not in lim["instruments"]["crypto_allowed"]:
        return [f"crypto non negoziabile su IBKR: {instrument}"], ctx
    q = quote(instrument)
    if not q:
        return [f"nessun prezzo per {instrument}"], ctx
    last = q["price"]
    px = ref_price or last
    if abs(px / last - 1) > lim["order"]["max_price_deviation"]:
        why.append(f"prezzo di riferimento {px} lontano dall'ultimo {last} oltre {lim['order']['max_price_deviation']:.0%}")
    notional = qty * px
    book = pod_book(pod)
    held = book["posizioni"].get(instrument, {}).get("qty", 0.0)
    if side == "SELL" and not lim["pod"]["allow_short"] and qty > held + 1e-9:
        why.append(f"vendita allo scoperto vietata (in portafoglio {held:g})")
    if notional < lim["order"]["min_notional_eur"]:
        why.append(f"ordine sotto il minimo di {lim['order']['min_notional_eur']} EUR")
    firm_nav = firm_nav_estimate()
    if notional > lim["order"]["max_notional_frac_nav"] * firm_nav:
        why.append(f"fat-finger: {notional:,.0f} EUR oltre il {lim['order']['max_notional_frac_nav']:.0%} del NAV")
    h0, h1 = lim["hours_utc"].get(kind, [0, 24])
    if not (h0 <= now.hour < h1) or (kind != "crypto" and now.weekday() >= 5):
        why.append(f"fuori orario per {kind} ({h0}-{h1} UTC, lun-ven)")
    if book["drawdown"] <= -lim["pod"]["dd_close"]:
        why.append(f"drawdown del pod {book['drawdown']:.1%} oltre il limite di chiusura")
    signed = notional if side == "BUY" else -notional
    cur_val = book["posizioni"].get(instrument, {}).get("valore", 0.0)
    new_gross = book["lorda_eur"] - abs(cur_val) + abs(cur_val + signed)
    cap = book["capitale_ammesso"]
    if cap <= 0 or new_gross > lim["pod"]["max_gross"] * cap + 1e-6:
        why.append(f"lorda del pod {new_gross:,.0f} EUR oltre {lim['pod']['max_gross']:.0%} del capitale {cap:,.0f}")
    if abs(cur_val + signed) > lim["pod"]["max_position_frac"] * cap + 1e-6 and side == "BUY":
        why.append(f"concentrazione su {instrument} oltre {lim['pod']['max_position_frac']:.0%} del capitale del pod")
    fb = firm_book()
    if side == "BUY" and (fb["gross"] * firm_nav + notional) > lim["firm"]["max_gross"] * firm_nav + 1e-6:
        why.append("lorda di societa' oltre il 100% del NAV")
    if kind == "crypto" and side == "BUY":
        crypto_eur = sum(v["valore"] for pp in pods.all_pods() if pp["id"] != "pod_zero"
                         for k, v in pod_book(pp["id"])["posizioni"].items() if _kind(k, lim) == "crypto")
        from . import pod_zero
        crypto_eur += pod_zero.crypto_fraction() * pod_zero_nav()
        if crypto_eur + notional > lim["firm"]["max_crypto_frac"] * firm_nav:
            why.append("quota crypto di societa' oltre il limite per controparte")
    est = COST_BY_KIND.get(kind, QC.UCITS_ETF).cost(notional)
    if est > 0.01 * notional:
        why.append(f"costo stimato {est:.2f} EUR oltre l'1% dell'ordine")
    ctx = dict(kind=kind, price=px, notional=notional, est_cost=est)
    return why, ctx


def submit_order(pod: str, agent: str, instrument: str, side: str, qty: float, reason: str,
                 horizon: str, ref_price: float | None = None, now: dt.datetime | None = None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    if not reason or len(reason) < 10:
        return _reject(pod, agent, instrument, side, qty, ref_price, reason, horizon, ["motivazione mancante"])
    why, ctx = _checks(pod, agent, instrument, side, qty, ref_price, now)
    if why:
        return _reject(pod, agent, instrument, side, qty, ctx.get("price", ref_price), reason, horizon, why)
    oid = db.ex("INSERT INTO gateway_orders(ts,pod,agent_id,instrument,side,qty,ref_price,reason,horizon,status)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (db.now_iso(), pod, agent, instrument, side.upper(), qty, ctx["price"], reason, horizon, "accettato"))
    events.publish("gateway.accepted", "gateway", dict(id=oid, pod=pod, agente=agent, strumento=instrument,
                                                       lato=side.upper(), qty=qty, controvalore=round(ctx["notional"], 2)))
    return dict(status="accettato", order_id=oid, est_cost=ctx["est_cost"])


def _reject(pod, agent, instrument, side, qty, price, reason, horizon, why):
    oid = db.ex("INSERT INTO gateway_orders(ts,pod,agent_id,instrument,side,qty,ref_price,reason,horizon,status,reject)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (db.now_iso(), pod, agent, instrument, str(side).upper(), qty, price, reason, horizon,
                 "respinto", "; ".join(why)))
    events.publish("gateway.rejected", "gateway", dict(id=oid, pod=pod, agente=agent, strumento=instrument,
                                                       motivi=why))
    return dict(status="respinto", order_id=oid, reasons=why)


# ---------------------------------------------------------------------------
# Broker (solo paper)
# ---------------------------------------------------------------------------
class SimulatedPaperBroker:
    """Broker paper simulato: fill al prezzo +- meta' spread, commissione dal modello dei costi."""
    venue = "paper-simulato"

    def execute(self, instrument: str, kind: str, side: str, qty: float, price: float) -> tuple[float, float]:
        m = COST_BY_KIND.get(kind, QC.UCITS_ETF)
        fill = price * (1 + m.half_spread if side == "BUY" else 1 - m.half_spread)
        fee = max(m.commission_rate * qty * fill, min(m.commission_min, m.commission_cap_rate * qty * fill))
        return fill, fee


class IBKRPaperBroker:
    """Collegamento a IB Gateway in PAPER. Rifiuta qualunque conto che non inizi con 'DU'.
    Non esiste una variante live: il passaggio a soldi veri richiede i cancelli 13-15 della sfida
    e approvals/*.ok firmato dai titolari, fuori dal perimetro degli agenti."""
    venue = "ibkr-paper"

    def __init__(self):
        from ib_async import IB          # disponibile solo sul Mac di Andrea
        self.ib = IB()
        port = int(os.environ.get("GATEWAY_IB_PORT", "4002"))
        self.ib.connect("127.0.0.1", port, clientId=int(os.environ.get("GATEWAY_IB_CLIENT_ID", "31")), timeout=20)
        acct = self.ib.managedAccounts()[0]
        if not acct.startswith("DU"):
            self.ib.disconnect()
            raise PermissionError("il Gateway opera solo su conti paper (DU...)")

    def execute(self, instrument, kind, side, qty, price):
        raise NotImplementedError("invio a IBKR paper: da attivare sul Mac dopo il collaudo (STATUS.md)")


def broker():
    return IBKRPaperBroker() if os.environ.get("GATEWAY_BROKER") == "ibkr_paper" else SimulatedPaperBroker()


def flush(b=None) -> dict:
    """Compensazione interna tra pod e invio del netto al broker."""
    b = b or broker()
    pending = db.q("SELECT * FROM gateway_orders WHERE status='accettato' ORDER BY id")
    by_instr = defaultdict(list)
    for o in pending:
        by_instr[o["instrument"]].append(o)
    report = dict(interni=0, al_broker=0, risparmio_eur=0.0)
    for instr, orders in by_instr.items():
        q = quote(instr)
        kind, mid = q["kind"], q["price"]
        buys = [o for o in orders if o["side"] == "BUY"]
        sells = [o for o in orders if o["side"] == "SELL"]
        tb, ts = sum(o["qty"] for o in buys), sum(o["qty"] for o in sells)
        matched = min(tb, ts)
        # 1) incrocio interno pro-quota al prezzo medio: nessuna commissione, nessuno spread
        for group, tot in ((buys, tb), (sells, ts)):
            for o in group:
                share = o["qty"] / tot * matched if tot else 0.0
                if share > 0:
                    db.ex("INSERT INTO fills(ts,order_id,pod,instrument,side,qty,price,fee,venue,model_cost)"
                          " VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (db.now_iso(), o["id"], o["pod"], instr, o["side"], share, mid, 0.0, "interno", 0.0))
                    report["interni"] += 1
        if matched > 0:
            m = COST_BY_KIND.get(kind, QC.UCITS_ETF)
            report["risparmio_eur"] += 2 * m.cost(matched * mid)
        # 2) il netto va al broker
        net = tb - ts
        if abs(net) > 1e-12:
            side = "BUY" if net > 0 else "SELL"
            group, tot = (buys, tb) if net > 0 else (sells, ts)
            fill, fee = b.execute(instr, kind, side, abs(net), mid)
            model_cost = COST_BY_KIND.get(kind, QC.UCITS_ETF).cost(abs(net) * mid)
            for o in group:
                rest = o["qty"] - o["qty"] / tot * matched
                if rest > 1e-12:
                    frac = rest / abs(net)
                    db.ex("INSERT INTO fills(ts,order_id,pod,instrument,side,qty,price,fee,venue,model_cost)"
                          " VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (db.now_iso(), o["id"], o["pod"], instr, side, rest, fill, fee * frac, b.venue,
                           model_cost * frac))
            report["al_broker"] += 1
        for o in orders:
            db.ex("UPDATE gateway_orders SET status='eseguito' WHERE id=?", (o["id"],))
    if pending:
        events.publish("gateway.fill", "gateway", report)
    return report


def orders(limit: int = 50) -> list[dict]:
    return db.q("SELECT * FROM gateway_orders ORDER BY id DESC LIMIT ?", (limit,))
