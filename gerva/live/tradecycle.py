"""
Ciclo PAPER del libro dei trade a margine isolato (gerva.risk.isolated).

Un passo al giorno, sull'ultima barra giornaliera CHIUSA di ogni moneta:
  1. per ogni trade aperto: stop colpito? -> chiuso allo stop (o all'apertura, se il giorno apre oltre lo stop);
     altrimenti stop mobile aggiornato; conviction scesa a 'bassa' o 7 giorni trascorsi -> chiuso alla chiusura;
  2. per ogni moneta senza trade: conviction > 0,60 -> proposta al libro, che applica tutti i limiti.

Limiti dichiarati di questa versione paper:
  * lavora su barre GIORNALIERE: lo stop e' verificato sul minimo del giorno, non sul percorso; nel reale lo stop e' un
    ordine reduce-only a riposo sulla sede e questo modulo deve solo riconciliarlo;
  * l'ingresso avviene al prezzo di chiusura della barra del segnale (nella ricerca: apertura del giorno dopo);
  * il funding e' quello di Binance quando e' in cache, altrimenti 0,01% ogni 8 ore; su Hyperliquid e' stato circa il doppio;
  * nessun ordine parte verso una sede: e' un registro interno, per misurare i cancelli della sezione 4.2 del documento.
Il passo e' idempotente: rieseguito sulla stessa barra non fa nulla.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict

import pandas as pd

from .. import ensemble as E
from .. import gervasoni as GV
from ..risk.isolated import BookLimits, Trade, TradeBook

_TRADE_FIELDS = set(Trade.__dataclass_fields__)

FEE = 0.00065            # per lato: 4,5 pb taker + 2 pb slippage
STOP_SLIP = 0.0005       # in piu' sullo stop
MAX_HOLD = 7


def empty_state(equity: float) -> dict:
    return dict(asof=None, equity=equity, open={}, closed=[], log=[], shadow=[])


def load_state(path: str, equity: float) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return empty_state(equity)


def save_state(path: str, state: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1, ensure_ascii=False, default=str)
    os.replace(tmp, path)


DEFAULT_FUNDING_DAY = 0.0003   # 0,01% ogni 8 ore, usato quando il funding reale del giorno non e' disponibile


def _conviction(bars: dict[str, pd.DataFrame], coin: str, funding: dict | None = None) -> tuple[float | None, str]:
    f = (funding or {}).get(coin)
    cv = E.conviction(E.crypto_signals(bars[coin], bars["BTC"]["close"], f), "crypto").iloc[-1]
    return (None if cv["score"] != cv["score"] else float(cv["score"])), str(cv["tier"])


def funding_paid(funding: dict | None, coin: str, opened: str, day: str) -> float:
    """Funding pagato da un long tra il giorno di apertura e quello di chiusura, in frazione del controvalore."""
    days = pd.date_range(opened, day, freq="D")[:-1] if opened != day else pd.DatetimeIndex([pd.Timestamp(day)])
    f = (funding or {}).get(coin)
    if f is None:
        return DEFAULT_FUNDING_DAY * len(days)
    return float(f.reindex(days).fillna(DEFAULT_FUNDING_DAY).sum())


def step(bars: dict[str, pd.DataFrame], state: dict, venue_max_leverage: float, engine_scale: float = 1.0,
         ai_multiplier: dict | None = None, limits: BookLimits | None = None, funding: dict | None = None,
         memory=None, rules: list | None = None) -> dict:
    """bars: moneta -> DataFrame giornaliero (open, high, low, close) fino all'ultima barra chiusa; deve contenere BTC.
    ai_multiplier: moneta -> fattore in [0, 1] (assente = 1). funding: moneta -> serie giornaliera del funding (somma dei
    tassi del giorno); entra nel segnale di conviction e nei costi, come nella ricerca.
    memory: gerva.learn.TradeMemory, in cui ogni trade chiuso viene registrato con contesto, costi, MAE e MFE.
    rules: regole ATTIVE del ciclo di automiglioramento (gerva.learn.Rule): possono solo saltare o dimezzare un trade.
    Restituisce lo stato aggiornato."""
    day = str(max(b.index[-1] for b in bars.values()).date())
    if state.get("asof") == day:
        return state
    book = TradeBook(limits)
    for sym, t in state["open"].items():
        book.open[sym] = Trade(**{k: v for k, v in t.items() if k in _TRADE_FIELDS})
    eq0 = float(state["equity"])
    events = []
    # 1. gestione dei trade aperti
    for sym in list(book.open):
        if sym not in bars or str(bars[sym].index[-1].date()) != day:
            continue
        t, b = book.open[sym], bars[sym].iloc[-1]
        adverse = b["low"] if t.side == 1 else b["high"]
        favour = b["high"] if t.side == 1 else b["low"]
        extra = state["open"][sym]
        opened = extra.get("opened", day)
        risk_px = t.initial_stop_distance * t.entry
        extra["mae"] = min(extra.get("mae", 0.0), t.side * (float(adverse) - t.entry) / risk_px)
        extra["mfe"] = max(extra.get("mfe", 0.0), t.side * (float(favour) - t.entry) / risk_px)
        held = (pd.Timestamp(day) - pd.Timestamp(opened)).days
        exit_px, why = None, ""
        if t.side * (adverse - t.stop) <= 0:
            px = min(t.stop, b["open"]) if t.side == 1 else max(t.stop, b["open"])
            exit_px, why = px * (1 - t.side * STOP_SLIP), "stop"
        else:
            book.update_stop(sym, b["high"], b["low"])
            _, tier = _conviction(bars, sym, funding)
            if tier == "bassa" or held >= MAX_HOLD:
                exit_px, why = float(b["close"]), "conviction bassa" if tier == "bassa" else "durata massima"
        if exit_px is not None:
            risk = t.risk
            pnl = book.close(sym, float(exit_px), eq0, costs=(2 * FEE + funding_paid(funding, sym, opened, day)) * t.notional)
            state["equity"] = float(state["equity"]) + pnl
            rec = dict(symbol=sym, opened=opened, closed=day, entry=t.entry, exit=float(exit_px), leverage=t.leverage, tier=t.tier,
                       pnl=pnl, R=pnl / risk if risk else 0.0, why=why)
            state["closed"].append(rec)
            if memory is not None:
                from ..learn.memory import TradeRecord
                fpaid = funding_paid(funding, sym, opened, day) * t.notional
                memory.append(TradeRecord(strategy_id="TRADE-11X", symbol=sym, entry_time=opened, exit_time=day, entry_price=t.entry,
                                          exit_price=float(exit_px), notional=t.notional, leverage=t.leverage, risk=risk, pnl=pnl,
                                          R=rec["R"], exit_reason=why, commission=2 * FEE * t.notional, funding=fpaid,
                                          slippage=STOP_SLIP if why == "stop" else 0.0, mae=extra.get("mae"), mfe=extra.get("mfe"),
                                          source="paper", context=extra.get("ctx") or {}))
            events.append(f"chiuso {sym} ({why}): {pnl:+.2f}, R {rec['R']:+.2f}")
    # 2. nuovi ingressi
    new_ctx = {}
    if not book.must_flatten():
        for sym, b in bars.items():
            if sym in book.open or len(b) < 260 or str(b.index[-1].date()) != day:
                continue
            score, _ = _conviction(bars, sym, funding)
            atr = float(((b["high"] - b["low"]) / b["close"]).rolling(14).mean().iloc[-1])
            m = (ai_multiplier or {}).get(sym, 1.0)
            ctx = {}
            if score is not None and score > 0.60:
                from ..learn.features import context as _context
                from ..learn.improve import multiplier as _multiplier
                ctx = _context(bars, sym, funding)
                lm, why_rules = _multiplier(ctx, rules or [])
                if lm < 1.0:
                    events.append(f"{sym}: regole apprese -> taglia x{lm:g} ({'; '.join(why_rules)})")
                m = min(m, lm) if 0.0 <= m <= 1.0 else m
            d = book.propose(sym, 1, float(b["close"].iloc[-1]), atr, score, float(state["equity"]), venue_max_leverage,
                             engine_scale=engine_scale, ai_multiplier=m)
            if d.ok:
                book.add(d.trade)
                new_ctx[sym] = ctx
                events.append(f"aperto {sym} ({d.trade.tier}): leva {d.trade.leverage:.1f}x, rischio {d.trade.risk:.2f}, "
                              f"margine {d.trade.margin:.2f}, stop {d.trade.stop:.4g}")
            elif score is not None and score > 0.60:
                events.append(f"rifiutato {sym}: {d.reason}")
    # indicatore Gervasoni in OMBRA: si registra accanto alla conviction, non decide nulla
    shadow = {}
    for sym, b in bars.items():
        if "volume" in b.columns and len(b) >= 150 and str(b.index[-1].date()) == day:
            g = GV.gq(b, b["volume"], bars["BTC"]["close"]).iloc[-1]
            score, tier_c = _conviction(bars, sym, funding)
            shadow[sym] = dict(gq=None if g != g else round(float(g), 4), gq_tier=GV.tier(g), conviction=score, conviction_tier=tier_c,
                               close=float(b["close"].iloc[-1]))
    state["shadow"] = (state.get("shadow", []) + [dict(day=day, coins=shadow)])[-800:]
    opened_map = {s: state["open"].get(s, {}).get("opened", day) for s in book.open}
    keep = {s: {k: v for k, v in state["open"].get(s, {}).items() if k in ("mae", "mfe", "ctx")} for s in book.open}
    state["open"] = {s: dict(asdict(t), opened=opened_map[s], **({"ctx": new_ctx[s]} if s in new_ctx else {}), **keep[s])
                     for s, t in book.open.items()}
    state["asof"] = day
    state["totals"] = book.totals(float(state["equity"])) if state["equity"] > 0 else {}
    state["log"] = (state.get("log", []) + [dict(day=day, events=events)])[-400:]
    return state


def summary(state: dict) -> dict:
    """Le grandezze dei cancelli del libro dei trade (documento, sezione 4.2)."""
    c = state["closed"]
    n = len(c)
    return dict(asof=state.get("asof"), equity=state["equity"], open=len(state["open"]), closed=n,
                mean_R=(sum(x["R"] for x in c) / n) if n else None, hit=(sum(x["R"] > 0 for x in c) / n) if n else None,
                worst_R=min((x["R"] for x in c), default=None), gate_trades=n >= 40,
                gate_mean_R=bool(n and sum(x["R"] for x in c) > 0))
