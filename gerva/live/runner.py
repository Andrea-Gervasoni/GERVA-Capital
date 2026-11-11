"""
Il ciclo live. Un giro fa sempre le stesse cose, nello stesso ordine, e ogni passo puo' fallire da solo:

    1. battito                              il supervisore sa che siamo vivi
    2. recupero                             ordini rimasti a meta' dopo un crash: si chiede al broker, mai reinvio cieco
    3. dati                                 storia + ultime barre; si misura quanto sono vecchi
    4. conto e posizioni                    dal broker: la verita' e' la sua
    5. rischio                              stato (NORMAL/REDUCED/HALTED/KILLED) e scala dell'esposizione
    6. KILL                                 se serve: annulla tutto, chiude tutto, esce con codice 3 (niente riavvio)
    7. pesi obiettivo                       stesse funzioni del backtest, poi scala e tetti di rischio
    8. ordini                               prima le vendite; ogni ordine: intenzione scritta -> controllo -> invio -> esito
    9. fotografia                           file JSON atomico per la dashboard

Garanzie:
  * nessuna eccezione esce da `run_forever`: si registra, si avvisa, si riprova al giro dopo; dopo N giri falliti
    di fila il motore di rischio passa ad HALTED;
  * un ordine per simbolo e per giorno di decisione: rilanciare il ciclo non duplica nulla;
  * senza dati freschi non si aumenta il rischio; ridurre e chiudere e' sempre permesso.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass

import pandas as pd

from ..execution.broker import Broker, BrokerError
from ..ops import alerts
from ..ops.journal import Journal
from ..ops.resilience import CircuitBreaker, CircuitOpen, retry
from ..risk.engine import Limits, RiskEngine
from ..ai import overlay as ai_overlay
from . import pipeline, snapshot

log = logging.getLogger("gerva.runner")
EXIT_KILLED = 3


@dataclass
class Settings:
    home: str = "var/gerva"
    mode: str = "paper"
    interval: float = 900.0
    band: float = 0.02                    # non si ritocca una posizione per meno del 2% del patrimonio
    equity_window: tuple = ("15:45", "16:00")     # ora di New York: le azioni si scambiano solo qui (a ridosso della chiusura)
    base_ccy: str = "USD"
    start_cash: float = 12_000.0


class Runner:
    def __init__(self, settings: Settings, limits: Limits, broker: Broker, market, journal: Journal | None = None,
                 clock=time.time):
        self.s, self.l, self.broker, self.market, self.clock = settings, limits, broker, market, clock
        os.makedirs(settings.home, exist_ok=True)
        self.j = journal or Journal(os.path.join(settings.home, "journal.sqlite"))
        self.risk = RiskEngine(limits, self.j, os.path.join(settings.home, "KILL"))
        self.hb_file = os.path.join(settings.home, "heartbeat")
        self.cb = {"data": CircuitBreaker("dati", 3, 300.0), "broker": CircuitBreaker("broker", 3, 120.0)}
        self.targets = None
        self.ai_state = None
        self.started = clock()

    # ---- piccoli strumenti --------------------------------------------------
    def _beat(self) -> None:
        with open(self.hb_file, "w") as f:
            f.write(str(self.clock()))

    def _timed(self, component: str, fn, breaker: str | None = None, tries: int = 3):
        t0 = time.perf_counter()
        try:
            call = (lambda: retry(fn, tries=tries, give_up_on=(CircuitOpen,))) if tries > 1 else fn
            out = self.cb[breaker].call(call) if breaker else call()
            self.j.beat(component, True, (time.perf_counter() - t0) * 1000)
            return out
        except Exception as e:
            self.j.beat(component, False, (time.perf_counter() - t0) * 1000, f"{type(e).__name__}: {str(e)[:200]}")
            raise

    def equity_window_open(self, now: pd.Timestamp | None = None) -> bool:
        now = (now or pd.Timestamp.fromtimestamp(self.clock(), tz="UTC")).tz_convert("America/New_York")
        a, b = self.s.equity_window
        return now.weekday() < 5 and a <= now.strftime("%H:%M") < b

    # ---- passo 2: recupero dopo un crash ------------------------------------
    def recover(self) -> bool:
        """True se resta qualcosa di non riconciliato."""
        dirty = False
        for o in self.j.open_intents():
            try:
                f = self.broker.lookup(o["client_id"])
            except Exception as e:
                self.j.event("warn", "recover", f"{o['client_id']}: broker non interrogabile ({type(e).__name__})")
                dirty = True
                continue
            if f is None:
                # l'intenzione era scritta ma il broker non l'ha mai vista: l'invio non era partito. Si chiude come annullata;
                # il prossimo calcolo dei pesi rigenera l'ordine se serve ancora.
                self.j.resolve(o["client_id"], "cancelled", reason="mai arrivato al broker (crash prima dell'invio)")
            elif f.status == "pending":
                dirty = True
            else:
                self.j.resolve(o["client_id"], f.status, f.qty, f.price, f.fee, f.reason or "recuperato dopo un riavvio")
            self.j.event("info", "recover", f"{o['client_id']}: {f.status if f else 'mai inviato'}")
        return dirty

    # ---- un giro ------------------------------------------------------------
    def cycle(self) -> dict:
        now = self.clock()
        self._beat()
        unreconciled = self.recover()
        in_window = self.equity_window_open()
        data_ok = True
        try:
            self._timed("Dati di mercato", lambda: self._refresh(in_window), "data", tries=1)
        except Exception as e:
            data_ok = False
            self.j.event("warn", "data", f"aggiornamento fallito: {type(e).__name__}: {str(e)[:200]}")
        ages = self.market.ages(pd.Timestamp.fromtimestamp(now, tz="UTC"))
        stale = [f"{v} ({ages[v]:.0f}h)" for v in ages if ages[v] > self.l.max_data_age_h.get(v, 48.0)]
        for v, h in ages.items():
            self.j.beat(f"Dati {v}", h != float("inf"), detail=f"ultima barra chiusa {h:.1f} ore fa" if h != float("inf") else
                        self.market.errors.get(v, "assenti"), degraded=bool(self.market.errors.get(v)) or h > self.l.max_data_age_h.get(v, 48.0))
        acct = self._timed("Broker", self.broker.account, "broker")
        pos = self._timed("Broker", self.broker.positions, "broker")
        gross = sum(abs(p.value) for p in pos.values()) / acct.equity if acct.equity > 0 else 0.0
        net = sum(p.value for p in pos.values()) / acct.equity if acct.equity > 0 else 0.0
        self.j.record_nav(acct.equity, acct.cash, gross, net, now)
        if self.j.get("start_equity") is None:
            self.j.set("start_equity", acct.equity)
            self.j.set("start_ts", now)
        a = self.risk.assess(acct.equity, now, stale, unreconciled, int(self.j.get("error_streak", 0)))
        summary = dict(state=a.state, equity=acct.equity, orders=0, rejected=0, stale=stale)
        if a.state == "KILLED":
            if not self.j.get("killed.flattened"):
                try:
                    fills = self.broker.flatten()
                    self.j.set("killed.flattened", True)
                    self.j.event("critical", "kill", f"tutto chiuso: {len(fills)} posizioni")
                except Exception as e:
                    self.j.event("critical", "kill", f"chiusura NON riuscita ({type(e).__name__}): si riprova al prossimo giro")
            alerts.send("critical", f"KILL attivo: {'; '.join(a.reasons)}", key="kill")
            self._snapshot(acct, self._safe_positions(pos), a, [])
            return summary
        notes = []
        if data_ok or self.targets is None:
            try:
                ov = ai_overlay.load(os.path.join(self.s.home, "ai_overlay.json"), now)
                sig = json.dumps([ov.valid, ov.note, ov.global_mult, sorted((k, v["mult"]) for k, v in ov.sleeves.items())])
                if sig != self.j.get("ai.overlay_sig"):
                    self.j.set("ai.overlay_sig", sig)
                    self.j.event("info" if ov.valid else "warn", "ai", ov.note or
                                 f"overlay AI: globale {ov.global_mult:.2f}; " + ", ".join(f"{k} x{v['mult']:.2f} ({v['motivo'][:80]})" for k, v in ov.sleeves.items()))
                self.targets = pipeline.build(self.market, self.l.vol_target, self.l.max_leverage, overlay=ov)
                self.ai_state = self._ai_state(ov)
            except Exception as e:
                self.j.event("warn", "pipeline", f"pesi non calcolabili: {type(e).__name__}: {str(e)[:200]}")
        if self.targets is not None:
            expo = self.j.get("expo") or {}
            expo[pd.Timestamp.fromtimestamp(now, tz="UTC").strftime("%Y-%m-%d")] = self.targets.leverage * a.scale
            self.j.set("expo", dict(sorted(expo.items())[-800:]))            # serve al cancello "scostamento dal backtest"
        if self.targets is not None and not unreconciled:
            w = {k: v * a.scale for k, v in self.targets.weights.items()}
            w, notes = self.risk.clamp_weights(w, {k: self.market.venue_of(k) for k in w})
            done, rej = self._trade(w, pos, acct.equity, a.state, ages, in_window, now)
            summary.update(orders=done, rejected=rej)
            if done:
                acct = self._timed("Broker", self.broker.account, "broker")
                pos = self._timed("Broker", self.broker.positions, "broker")
        self.j.set("error_streak", 0)
        self._snapshot(acct, pos, a, notes)
        return summary

    def _refresh(self, in_window: bool) -> None:
        self.market.refresh(keep_open_bar=in_window)
        if len(self.market.errors) >= 2:
            raise RuntimeError("; ".join(self.market.errors.values()))

    def _safe_positions(self, fallback):
        try:
            return self.broker.positions()
        except Exception:
            return fallback

    def _ai_state(self, ov) -> dict:
        """Stato del livello AI per la dashboard: overlay in vigore, regime, conviction di oggi. Non decide nulla."""
        out = dict(overlay=dict(valido=ov.valid, nota=ov.note, globale=ov.global_mult, motivo_globale=ov.global_reason,
                                scade=snapshot._iso(ov.expires) if ov.expires else None,
                                strategie=[dict(id=k, mult=v["mult"], motivo=v["motivo"], fonti=v.get("fonti", [])) for k, v in ov.sleeves.items()]),
                   regime=None, conviction=[])
        try:
            from .. import ensemble
            from ..ai import regime
            m = self.market
            if m.P is not None and m.cclose is not None and "^VIX" in m.P["adj"]:
                r = regime.classify(m.P["adj"]["^VIX"], m.P["adj"]["^VIX3M"], self.targets.port_ret, m.cclose["BTC"]).iloc[-1]
                out["regime"] = dict(stato=str(r["state"]), punteggio=float(r["score"]), scala_esposizione=False)
            for c in ("BTC", "ETH"):
                if m.cclose is not None and c in m.cclose:
                    px = m.cclose[c].dropna()
                    bars = pd.DataFrame(dict(open=px, high=px, low=px, close=px))      # il feed live tiene solo le chiusure: IBS neutro
                    cv = ensemble.conviction(ensemble.crypto_signals(bars, m.cclose["BTC"]).drop(columns=["ibs_low"]), "crypto").iloc[-1]
                    out["conviction"].append(dict(asset=c, score=float(cv["score"]) if pd.notna(cv["score"]) else None, livello=str(cv["tier"])))
        except Exception as e:
            self.j.event("warn", "ai", f"stato AI non calcolato: {type(e).__name__}")
        return out

    # ---- passo 8: ordini ----------------------------------------------------
    def _trade(self, w: dict, pos: dict, equity: float, state: str, ages: dict, in_window: bool, now: float):
        day_utc = pd.Timestamp.fromtimestamp(now, tz="UTC")
        keys = {"crypto": day_utc.strftime("%Y-%m-%d"), "ibkr": day_utc.tz_convert("America/New_York").strftime("%Y-%m-%d")}
        px = self.market.last_prices(sorted(set(w) | set(pos)))
        plan = []
        for sym in sorted(set(w) | set(pos)):
            venue = self.market.venue_of(sym)
            cur = pos[sym].value if sym in pos else 0.0
            tgt = w.get(sym, 0.0) * equity
            delta = tgt - cur
            closing = abs(tgt) < 1e-9 and abs(cur) > 0
            if not closing and abs(delta) < max(self.l.min_order, self.s.band * equity):
                continue
            reducing = abs(tgt) < abs(cur)
            if venue == "ibkr" and not in_window:
                continue                                   # le azioni si scambiano solo a ridosso della chiusura
            if not reducing and ages.get(venue, float("inf")) > self.l.max_data_age_h.get(venue, 48.0):
                continue                                   # dati vecchi: non si aumenta
            if sym not in px:
                self.j.event("warn", "trade", f"{sym}: nessun prezzo, ordine saltato")
                continue
            plan.append((delta, sym, venue, cur, px[sym]))
        plan.sort(key=lambda x: x[0])                       # prima le vendite: liberano cassa per gli acquisti
        done = rej = 0
        for delta, sym, venue, cur, price in plan:
            cid = f"{keys[venue]}:{sym}"
            qty = delta / price
            strat = next((s for s, m in self.targets.by_sleeve.items() if sym in m), "")
            if not self.j.intent(cid, keys[venue], sym, "BUY" if qty > 0 else "SELL", abs(qty), price, venue, strat):
                continue                                   # gia' fatto in questo giorno di decisione
            ok, why = self.risk.check_order(sym, delta, cur, price, price, equity, state)
            if not ok:
                self.j.resolve(cid, "rejected", reason=why)
                rej += 1
                continue
            try:
                f = self._timed("Broker", lambda: self.broker.submit(cid, sym, qty, price), "broker", tries=1)
            except Exception as e:
                # esito ignoto: l'intenzione resta aperta, il prossimo giro la riconcilia PRIMA di fare altro
                self.j.event("warn", "trade", f"{cid}: esito ignoto ({type(e).__name__}); si riconcilia al prossimo giro")
                break
            if f.status == "pending":
                continue                                   # resta 'intent': la riconciliazione la chiudera'
            self.j.resolve(cid, f.status, f.qty, f.price, f.fee, f.reason)
            done += f.status in ("filled", "partial")
            rej += f.status == "rejected"
            if f.status == "rejected":
                self.j.event("warn", "trade", f"{cid} rifiutato dal broker: {f.reason}")
        return done, rej

    def _snapshot(self, acct, pos, a, notes) -> None:
        try:
            snap = snapshot.build(self, acct, pos, a, notes)
            snapshot.write(os.path.join(self.s.home, "snapshot.json"), snap)
        except Exception as e:
            self.j.event("warn", "snapshot", f"fotografia non scritta: {type(e).__name__}: {str(e)[:200]}")

    # ---- il ciclo infinito --------------------------------------------------
    def run_forever(self, max_cycles: int | None = None, sleep=time.sleep) -> int:
        n = 0
        while max_cycles is None or n < max_cycles:
            n += 1
            try:
                out = self.cycle()
                log.info("giro %d: %s", n, out)
                if out["state"] == "KILLED" and self.j.get("killed.flattened"):
                    return EXIT_KILLED
            except Exception as e:                           # mai fuori da qui
                streak = int(self.j.get("error_streak", 0)) + 1
                self.j.set("error_streak", streak)
                self.j.event("critical" if streak >= self.l.max_errors else "warn", "runner",
                             f"giro fallito ({streak} di fila): {type(e).__name__}: {str(e)[:300]}")
                log.exception("giro fallito")
                alerts.send("critical" if streak >= self.l.max_errors else "warn",
                            f"giro fallito ({streak} di fila): {type(e).__name__}: {str(e)[:200]}", key="cycle-fail")
                self._beat()
            if max_cycles is None or n < max_cycles:
                sleep(self.s.interval)
        return 0
