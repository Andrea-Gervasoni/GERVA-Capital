"""
La fotografia del fondo per la dashboard: un solo file JSON, scritto in modo atomico a ogni giro.

La dashboard non tocca ne' il database ne' il broker: legge questo file. Se il ciclo si ferma, la dashboard se ne
accorge dall'eta' della fotografia (`meta.as_of`) e lo mostra.

`demo()` costruisce la stessa fotografia dai risultati del backtest (research/v5/series.parquet): serve a vedere la
dashboard piena prima di avere un conto paper. E' marcata «SIMULATO» e non puo' essere scambiata per un conto vero.
"""
from __future__ import annotations

import json
import math
import os
import time

import numpy as np
import pandas as pd

from .. import __version__
from ..strategies.book import SLEEVES
from ..validation import metrics as M
from . import gates as G

LABEL = {"paper": "PAPER: conto simulato, prezzi reali", "alpaca-paper": "PAPER: conto di prova Alpaca",
         "backtest": "SIMULATO: backtest su dati storici", "live": "REALE"}


def _iso(ts: float | None) -> str | None:
    return None if ts is None else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _clean(x):
    """JSON non ammette NaN o infinito: diventano null."""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (float, np.floating)):
        return None if not math.isfinite(x) else float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def write(path: str, snap: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_clean(snap), f, separators=(",", ":"))
    os.replace(tmp, path)


def _perf(daily: pd.Series, periods: int) -> dict:
    s = M.summary(daily, 0.0, periods) if len(daily) >= 20 else {}
    return dict(cagr=s.get("cagr"), vol=s.get("vol"), sharpe=s.get("sharpe"), sortino=s.get("sortino"), calmar=s.get("calmar"),
                hit_rate_days=float((daily > 0).mean()) if len(daily) else None, best_month=s.get("mese_migliore"),
                worst_month=s.get("mese_peggiore"), psr=s.get("psr0"), days=int(len(daily)))


def _monthly(daily: pd.Series) -> list:
    m = M.monthly(daily) if len(daily) else pd.Series(dtype=float)
    return [dict(ym=f"{y}-{mo:02d}", ret=float(v)) for (y, mo), v in m.items()]


def _limits(l, a, gross: float, weights: dict, venue_w: dict) -> list:
    def row(name, value, limit, unit, warn=0.8):
        r = abs(value) / abs(limit) if limit else 0.0
        return dict(name=name, value=value, limit=limit, unit=unit, status="breach" if r >= 1 else "warn" if r >= warn else "ok")
    rows = [row("Leva lorda", gross, l.max_leverage, "x"),
            row("Caduta dal massimo", a.drawdown, -l.dd_kill, "%", warn=l.dd_reduce / l.dd_kill),
            row("Perdita a 24 ore", min(a.day_pnl, 0.0), -l.daily_loss, "%"),
            row("Perdita a 7 giorni", min(a.week_pnl, 0.0), -l.weekly_loss, "%"),
            row("Peso massimo di uno strumento", max([abs(v) for v in weights.values()] or [0.0]), l.max_weight, "%", warn=0.9)]
    for v, cap in l.max_venue.items():
        rows.append(row(f"Esposizione sulla sede {v}", venue_w.get(v, 0.0), cap, "%", warn=0.9))
    return rows


def model_daily(runner) -> pd.Series:
    """Rendimento giornaliero 'da modello': moltiplicatore annotato il giorno d x rendimento simulato del portafoglio in d+1."""
    t, expo = runner.targets, runner.j.get("expo") or {}
    if t is None or not expo:
        return pd.Series(dtype=float)
    m = pd.Series({pd.Timestamp(d) + pd.Timedelta(days=1): v for d, v in expo.items()})
    port = t.port_ret.reindex(m.index).dropna()
    return (m.reindex(port.index) * port).shift(1).dropna()      # il paper vede la chiusura di d+1 il giorno d+2


def build(runner, acct, pos: dict, a, notes: list) -> dict:
    j, l, s, t = runner.j, runner.l, runner.s, runner.targets
    now = runner.clock()
    nav = pd.DataFrame([dict(r) for r in j.nav_history()])
    if len(nav):
        nav["d"] = pd.to_datetime(nav["ts"], unit="s").dt.normalize()
        daily_eq = nav.groupby("d")["equity"].last()
    else:
        daily_eq = pd.Series(dtype=float)
    daily = daily_eq.pct_change().dropna()
    start = j.get("start_equity") or acct.equity
    eq = acct.equity
    month0 = daily_eq[daily_eq.index < pd.Timestamp(now, unit="s").normalize().replace(day=1)]
    year0 = daily_eq[daily_eq.index < pd.Timestamp(now, unit="s").normalize().replace(month=1, day=1)]
    dd_all = (daily_eq / daily_eq.cummax() - 1.0).min() if len(daily_eq) else 0.0
    venue_of = runner.market.venue_of
    weights = {k: p.value / eq for k, p in pos.items()} if eq > 0 else {}
    gross, net = sum(abs(v) for v in weights.values()), sum(weights.values())
    venue_w, class_w = {}, {}
    sleeve_of = {sym: sid for sid, m in (t.by_sleeve.items() if t else []) for sym in m}
    for k, v in weights.items():
        ven = venue_of(k)
        venue_w[ven] = venue_w.get(ven, 0.0) + abs(v)
        cls = SLEEVES[sleeve_of[k]].asset_class if k in sleeve_of else ("Crypto" if ven == "crypto" else "Azioni")
        g, n = class_w.get(cls, (0.0, 0.0))
        class_w[cls] = (g + abs(v), n + v)
    prev_px = {}
    try:
        for k in pos:
            ser = runner.market.cclose[k].dropna() if venue_of(k) == "crypto" else runner.market.P["close"][k].dropna()
            prev_px[k] = float(ser.iloc[-2]) if len(ser) > 1 else None
    except Exception:
        pass
    S = t.sleeve_ret if t else pd.DataFrame()
    strategies = []
    for sid, sl in SLEEVES.items():
        r = S[sid] if sid in S else pd.Series(dtype=float)
        live = r[r.index >= pd.Timestamp(j.get("start_ts") or now, unit="s").normalize()] if len(r) else r
        bt = M.summary(r[r.index.day_of_week < 5] if sl.periods == 252 else r, 0.0, sl.periods) if len(r) > 60 else {}
        strategies.append(dict(
            id=sid, name=sl.name, status="active" if t and sid in t.alloc else "disabled",
            allocation=t.alloc.get(sid) if t else None,
            exposure=sum(abs(v) for v in t.by_sleeve.get(sid, {}).values()) * a.scale if t else None,
            pnl_day_pct=float(r.iloc[-1]) if len(r) else None,
            pnl_mtd_pct=float((1 + r[r.index >= r.index[-1].replace(day=1)]).prod() - 1) if len(r) else None,
            pnl_total_pct=float((1 + live).prod() - 1) if len(live) else None,
            sharpe_live=M.sharpe(live, 0.0, sl.periods) if len(live) >= 60 else None,
            sharpe_backtest=bt.get("sharpe"), max_dd=bt.get("max_dd"),
            last_signal=(t.asof.get(sid) + "T00:00:00Z") if t and t.asof.get(sid) else None,
            spark=[float(x) for x in (1 + r.tail(90)).cumprod()] if len(r) else []))
    hb = j.heartbeats()
    since = now - 86400
    return dict(
        meta=dict(fund="GERVA Capital", mode=s.mode, as_of=_iso(now), base_ccy=s.base_ccy, version=__version__,
                  data_label=LABEL.get(s.mode, s.mode.upper()), stale_after_s=int(max(120, 2.5 * s.interval))),
        nav=dict(equity=eq, cash=acct.cash, start_equity=start, high_water=a.high_water,
                 pnl_day=eq * a.day_pnl / (1 + a.day_pnl) if a.day_pnl > -1 else None, pnl_day_pct=a.day_pnl,
                 pnl_mtd_pct=eq / month0.iloc[-1] - 1 if len(month0) else eq / start - 1,
                 pnl_ytd_pct=eq / year0.iloc[-1] - 1 if len(year0) else eq / start - 1,
                 pnl_total_pct=eq / start - 1, drawdown_pct=a.drawdown, max_drawdown_pct=float(min(dd_all, a.drawdown))),
        equity_curve=[dict(t=str(d.date()), equity=float(v), benchmark=None) for d, v in daily_eq.items()],
        monthly_returns=_monthly(daily),
        performance=_perf(daily, 365),
        exposure=dict(gross=gross, net=net, leverage=gross, max_leverage=l.max_leverage,
                      by_asset_class=[dict(name=k, gross=g, net=n) for k, (g, n) in sorted(class_w.items())],
                      by_venue=[dict(name=k, gross=v, net=v) for k, v in sorted(venue_w.items())]),
        positions=[dict(symbol=k, venue=venue_of(k), strategy=sleeve_of.get(k, ""), qty=p.qty, price=p.price, value=p.value,
                        weight=p.value / eq if eq else None,
                        pnl_day=p.qty * (p.price - prev_px[k]) if prev_px.get(k) else None, pnl_open=None)
                   for k, p in sorted(pos.items(), key=lambda kv: -abs(kv[1].value))],
        risk=dict(state=a.state, state_reason="; ".join(a.reasons + notes),
                  var_95_1d_pct=float(daily.quantile(0.05)) if len(daily) >= 60 else None,
                  es_95_1d_pct=float(daily[daily <= daily.quantile(0.05)].mean()) if len(daily) >= 60 else None,
                  vol_target=l.vol_target, vol_realized_30d=float(daily.tail(30).std() * math.sqrt(365)) if len(daily) >= 20 else None,
                  limits=_limits(l, a, gross, weights, venue_w),
                  dd_ladder=[dict(level=-l.dd_reduce, action="dimezza l'esposizione", hit=a.drawdown <= -l.dd_reduce),
                             dict(level=-l.dd_halt, action="un quarto dell'esposizione, nessun aumento", hit=a.drawdown <= -l.dd_halt),
                             dict(level=-l.dd_kill, action="KILL: chiude tutto e si ferma", hit=a.drawdown <= -l.dd_kill)]),
        strategies=strategies,
        orders=[dict(t=_iso(o["ts"]), symbol=o["symbol"], side=o["side"], qty=o["fill_qty"] and abs(o["fill_qty"]) or o["qty"],
                     price=o["fill_price"] or o["ref_price"], status={"intent": "pending", "partial": "filled", "unknown": "pending"}.get(o["status"], o["status"]),
                     strategy=o["strategy"], venue=o["venue"], reason=o["reason"]) for o in j.orders(50)],
        system=dict(heartbeat_age_s=0, uptime_s=now - runner.started,
                    restarts_24h=len([e for e in j.events(500, since) if e["component"] == "runner" and "avvio" in e["msg"]]),
                    errors_24h=len([e for e in j.events(500, since) if e["level"] in ("warn", "critical")]),
                    components=[dict(name=h["component"], status=h["status"], latency_ms=h["latency_ms"], last_ok=_iso(h["last_ok"]),
                                     detail=h["detail"]) for h in hb]),
        alerts=[dict(t=_iso(e["ts"]), level=e["level"], msg=f"{e['component']}: {e['msg']}") for e in j.events(30)],
        gates=G.evaluate(j, daily, now, s.interval, model_daily(runner)))


# ---------------------------------------------------------------------------
def demo(series_path: str, column: str = "VT15", start_equity: float = 12_000.0, limits=None) -> dict:
    """Fotografia costruita dal backtest. column: PORT (senza leva) oppure VT10/VT15/VT20 (volatilita' obiettivo)."""
    from ..risk.engine import Limits
    l = limits or Limits()
    D = pd.read_parquet(series_path)
    r = D[column].dropna()
    rf = D["RF"].reindex(r.index).fillna(0.0)
    eq = start_equity * (1 + r).cumprod()
    sp = D[["CR-TREND", "CR-XSMOM", "EQ-MR", "MA-TREND"]].reindex(r.index)
    bench = start_equity * (1 + 0.6 * 0.0 + rf).cumprod()         # riferimento: tasso a breve
    dd = eq / eq.cummax() - 1
    now = time.time()
    last = r.index[-1]
    alloc = {k[2:]: float(D[k].dropna().iloc[-1]) for k in D.columns if k.startswith("W_")}
    lev = float(r.tail(60).std() and (D[column].tail(60).std() / D["PORT"].tail(60).std()))
    m = M.summary(r, rf, 365)
    strategies = []
    for sid, slv in SLEEVES.items():
        x = sp[sid]
        s = M.summary(x, rf, 365)
        strategies.append(dict(id=sid, name=slv.name, status="active", allocation=alloc.get(sid), exposure=alloc.get(sid, 0) * lev,
                               pnl_day_pct=float(x.iloc[-1]), pnl_mtd_pct=float((1 + x[x.index >= last.replace(day=1)]).prod() - 1),
                               pnl_total_pct=float((1 + x).prod() - 1), sharpe_live=None, sharpe_backtest=s.get("sharpe"),
                               max_dd=s.get("max_dd"), last_signal=str(last.date()) + "T00:00:00Z",
                               spark=[float(v) for v in (1 + x.tail(90)).cumprod()]))
    gross = sum(alloc.values()) * lev * 0.7
    return dict(
        meta=dict(fund="GERVA Capital", mode="backtest", as_of=_iso(now), base_ccy="USD", version=__version__,
                  data_label=LABEL["backtest"], stale_after_s=10 ** 9),
        nav=dict(equity=float(eq.iloc[-1]), cash=float(eq.iloc[-1] * max(1 - gross, 0)), start_equity=start_equity,
                 high_water=float(eq.max()), pnl_day=float(eq.iloc[-1] - eq.iloc[-2]), pnl_day_pct=float(r.iloc[-1]),
                 pnl_mtd_pct=float((1 + r[r.index >= last.replace(day=1)]).prod() - 1),
                 pnl_ytd_pct=float((1 + r[r.index >= last.replace(month=1, day=1)]).prod() - 1),
                 pnl_total_pct=float(eq.iloc[-1] / start_equity - 1), drawdown_pct=float(dd.iloc[-1]), max_drawdown_pct=float(dd.min())),
        equity_curve=[dict(t=str(d.date()), equity=float(v), benchmark=float(b)) for d, v, b in zip(eq.index, eq, bench)],
        monthly_returns=_monthly(r),
        performance=dict(cagr=m["cagr"], vol=m["vol"], sharpe=m["sharpe"], sortino=m["sortino"], calmar=m["calmar"],
                         hit_rate_days=float((r > 0).mean()), best_month=m["mese_migliore"], worst_month=m["mese_peggiore"],
                         psr=m["psr0"], days=int(len(r))),
        exposure=dict(gross=gross, net=gross, leverage=gross, max_leverage=l.max_leverage,
                      by_asset_class=[dict(name="Crypto", gross=(alloc.get("CR-TREND", 0) + alloc.get("CR-XSMOM", 0)) * lev * 0.6,
                                           net=(alloc.get("CR-TREND", 0) + alloc.get("CR-XSMOM", 0)) * lev * 0.6),
                                      dict(name="Azioni", gross=alloc.get("EQ-MR", 0) * lev * 0.3, net=alloc.get("EQ-MR", 0) * lev * 0.3),
                                      dict(name="Multi-asset", gross=alloc.get("MA-TREND", 0) * lev, net=alloc.get("MA-TREND", 0) * lev)],
                      by_venue=[]),
        positions=[],
        risk=dict(state="NORMAL", state_reason="backtest: nessun conto collegato", var_95_1d_pct=float(r.quantile(0.05)),
                  es_95_1d_pct=float(r[r <= r.quantile(0.05)].mean()), vol_target=l.vol_target,
                  vol_realized_30d=float(r.tail(30).std() * math.sqrt(365)),
                  limits=[dict(name="Leva lorda", value=gross, limit=l.max_leverage, unit="x", status="ok"),
                          dict(name="Caduta dal massimo", value=float(dd.iloc[-1]), limit=-l.dd_kill, unit="%",
                               status="warn" if dd.iloc[-1] <= -l.dd_reduce else "ok")],
                  dd_ladder=[dict(level=-l.dd_reduce, action="dimezza l'esposizione", hit=bool(dd.iloc[-1] <= -l.dd_reduce)),
                             dict(level=-l.dd_halt, action="un quarto dell'esposizione, nessun aumento", hit=bool(dd.iloc[-1] <= -l.dd_halt)),
                             dict(level=-l.dd_kill, action="KILL: chiude tutto e si ferma", hit=bool(dd.iloc[-1] <= -l.dd_kill))]),
        strategies=strategies, orders=[],
        system=dict(heartbeat_age_s=None, uptime_s=None, restarts_24h=None, errors_24h=None, components=[]),
        alerts=[dict(t=_iso(now), level="info", msg="Fotografia dimostrativa costruita dal backtest (research/v5). Nessun conto collegato.")],
        gates=G.evaluate(None, pd.Series(dtype=float), now))
