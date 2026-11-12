"""Genera TUTTI gli esempi della dashboard come un solo insieme coerente (seme fisso):

    python dashboard/tools/build_samples.py

Scrive in dashboard/static/: sample_snapshot.json, sample_ohlc.json, sample_tradebook.json, sample_compare.json.
Una sola storia: stesso giorno di riferimento, un solo prezzo per strumento (le posizioni sono valorizzate all'ultima
chiusura delle barre), un solo patrimonio (il confronto riporta la curva della fotografia piu' il contributo dei trade),
trade di esempio costruiti SULLE barre con le regole del libro (rischio 0,5% / 1%, stop a 1 ATR, durata massima 7 giorni:
R x rischio = P&L), cancelli con i nomi e le soglie di gerva/live/gates.py. Lo verifica tests/test_dashboard.py."""
import json
import math
import random
import statistics
import sys
from datetime import date, datetime, timedelta, timezone

from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "static"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = STATIC / "sample_snapshot.json"
START_EQ = 10_000.0
D0 = date(2024, 4, 1)
D1 = date(2026, 11, 10)
AS_OF = "2026-11-10T20:45:00Z"
PPY = 365.0
MAX_HOLD, RISK_CONFIRMED, RISK_EXCEPTIONAL, SCORE_CONFIRMED, SCORE_EXCEPTIONAL, MAX_TRADE_LEV, STOP_TO_LIQ = 7, 0.005, 0.010, 0.60, 0.75, 15.0, 0.6
CONV_TIERS = {"crypto": (0.30, 0.60), "etf": (0.55, 0.82)}       # gerva/ensemble.py THRESHOLDS
GQ_T = dict(eccezionale=1.4205535120908974, alta=0.5317842685566442, bassa=-0.5033858160836456)   # gerva/gervasoni.py
BOOK_DAYS = 12           # la storia dell'esempio: il paper è partito 12 giorni fa; prima, la curva è il backtest (simulato)


def conv_tier(score, kind="crypto"):
    lo, hi = CONV_TIERS[kind]
    return "bassa" if score is None else "alta" if score > hi else "media" if score > lo else "bassa"


def gq_tier(v):
    return "bassa" if v is None else "eccezionale" if v >= GQ_T["eccezionale"] else "alta" if v >= GQ_T["alta"] else "bassa" if v <= GQ_T["bassa"] else "media"


# --- barre: le stesse per prezzi, posizioni, trade e confronto ------------------------------------------------------
_ohlc = json.loads((STATIC / "sample_ohlc.json").read_text(encoding="utf-8"))
BARS = _ohlc["symbols"]
CRYPTO = ["BTC", "ETH", "SOL"]


def _atr(b, i, n=14):
    w = [(b["h"][j] - b["l"][j]) / b["c"][j] for j in range(max(0, i - n + 1), i + 1)]
    return sum(w) / len(w)


def run_book(k_end, start_eq, first):
    """Il libro dei trade sulle barre d'esempio, fino all'indice k_end compreso. Regole di gerva/live/tradecycle.py, semplificate."""
    equity, open_, closed, daily = start_eq, {}, [], {}
    for i in range(first, k_end + 1):
        for sym in CRYPTO:
            b = BARS[sym]
            day = b["t"][i]
            t = open_.get(sym)
            if t:
                held = i - t["_i"]
                dist = t["entry"] * t["initial_stop_distance"]
                t["mae"] = round(min(t["mae"], (b["l"][i] - t["entry"]) / dist), 2)
                t["mfe"] = round(max(t["mfe"], (b["h"][i] - t["entry"]) / dist), 2)
                t["best"] = max(t["best"], b["h"][i])
                why = exit_px = None
                if b["l"][i] <= t["stop"]:
                    why, exit_px = "stop", t["stop"]
                elif conv_tier(b["conviction"][i]) == "bassa":
                    why, exit_px = "conviction bassa", b["c"][i]
                elif held >= MAX_HOLD:
                    why, exit_px = "durata massima", b["c"][i]
                if why:
                    r = round((exit_px - t["entry"]) / dist, 4)
                    pnl = round(r * t["risk"], 2)
                    equity = round(equity + pnl, 2)
                    closed.append(dict(symbol=sym, opened=t["opened"], closed=day, entry=t["entry"], exit=round(exit_px, 2), leverage=t["leverage"], tier=t["tier"],
                                       pnl=pnl, R=r, why=why, risk=t["risk"], mae=t["mae"], mfe=t["mfe"]))
                    del open_[sym]
                    continue
            score = b["conviction"][i]
            if sym not in open_ and score is not None and score >= SCORE_CONFIRMED and i < k_end + 1:
                tier = "eccezionale" if score >= SCORE_EXCEPTIONAL else "confermato"
                dist = _atr(b, i)
                lev = round(min(MAX_TRADE_LEV, STOP_TO_LIQ / dist), 1)
                risk = round(equity * (RISK_EXCEPTIONAL if tier == "eccezionale" else RISK_CONFIRMED), 2)
                entry = b["c"][i]
                notional = round(risk / dist, 2)
                open_[sym] = dict(symbol=sym, side=1, entry=entry, stop=round(entry * (1 - dist), 2), notional=notional, margin=round(notional / lev, 2), leverage=lev, risk=risk,
                                  liquidation=round(entry * (1 - 1 / lev), 2), tier=tier, best=entry, initial_stop_distance=round(dist, 6), trail=None, opened=day, mae=0.0, mfe=0.0,
                                  ctx=dict(conviction=score, gq=b["gq"][i], atr_pct=round(dist, 6)), _i=i)
        daily[BARS["BTC"]["t"][i]] = equity
    return equity, open_, closed, daily


# il giorno di riferimento dell'esempio: l'ultima barra in cui BTC ha un trade aperto da 2-5 giorni (così il righello si vede)
_n = len(BARS["BTC"]["t"])
assert all(len(BARS[s]["t"]) == _n and BARS[s]["t"] == BARS["BTC"]["t"] for s in CRYPTO)
K = None
for _k in range(_n - 1, _n - 60, -1):
    _, _open, _, _ = run_book(_k, 10_000.0, _k - BOOK_DAYS + 1)
    if "BTC" in _open and 2 <= _k - _open["BTC"]["_i"] <= 5:
        K = _k
        break
assert K is not None, "nessun giorno con un trade aperto su BTC nelle ultime 60 barre"
_shift = (D1 - date.fromisoformat(BARS["BTC"]["t"][K])).days
_cut = BARS["BTC"]["t"][K]
for _sym, _b in BARS.items():                          # barre troncate al giorno di riferimento e portate alle date della fotografia
    _keep = [j for j, d in enumerate(_b["t"]) if d <= _cut]
    for _key in ("t", "o", "h", "l", "c", "v", "conviction", "gq"):
        if isinstance(_b.get(_key), list):
            _b[_key] = [_b[_key][j] for j in _keep]
    _b["t"] = [(date.fromisoformat(d) + timedelta(_shift)).isoformat() for d in _b["t"]]
    _b["rows"] = len(_b["t"])
K = len(BARS["BTC"]["t"]) - 1
PX = {sym: b["c"][-1] for sym, b in BARS.items()}


def simulate(seed, bseed=0):
    rng = random.Random(seed)
    brng = random.Random(1_000_003 + bseed)
    days = [(D0 + timedelta(n)) for n in range((D1 - D0).days + 1)]
    eq, bm, rets = [], [], []
    e, b = START_EQ, 100.0
    for d in days:
        wk = d.weekday() >= 5
        # regimi: una fase difficile a inizio 2025 e una debole a fine estate 2026
        drift = 0.00036
        vol = 0.0046
        if date(2025, 2, 10) <= d <= date(2025, 4, 8):
            drift, vol = -0.0011, 0.0060
        elif date(2025, 4, 9) <= d <= date(2025, 7, 15):
            drift, vol = 0.0009, 0.0048
        elif date(2026, 8, 17) <= d <= date(2026, 9, 25):
            drift, vol = -0.0008, 0.0052
        elif date(2026, 9, 26) <= d <= date(2026, 11, 2):
            drift, vol = 0.0007, 0.0045
        if wk:
            drift, vol = drift * 0.4, vol * 0.45       # nel fine settimana si muove solo la parte cripto
        z = rng.gauss(0, 1)
        if rng.random() < 0.03:
            z *= 2.2                                   # code grasse
        r = drift + vol * z
        zb = 0.45 * z + math.sqrt(1 - 0.45 ** 2) * brng.gauss(0, 1)
        rb = (0.0 if wk else 0.00032 + 0.0078 * zb)
        if date(2025, 2, 18) <= d <= date(2025, 4, 8) and not wk:
            rb -= 0.0022
        e *= 1 + r
        b *= 1 + rb
        e = round(e, 2)
        eq.append(e)
        bm.append(round(b, 2))
    prev = START_EQ
    for v in eq:
        rets.append(v / prev - 1)
        prev = v
    return days, eq, bm, rets


def stats(days, eq, rets):
    n = len(rets)
    mean = statistics.fmean(rets)
    sd = statistics.pstdev(rets)
    down = math.sqrt(sum(min(r, 0) ** 2 for r in rets) / n)
    hw, mdd, peak = START_EQ, 0.0, START_EQ
    for v in eq:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    hw = peak
    cagr = (eq[-1] / START_EQ) ** (PPY / n) - 1
    sharpe = mean / sd * math.sqrt(PPY)
    sortino = mean / down * math.sqrt(PPY)
    skew = sum((r - mean) ** 3 for r in rets) / n / sd ** 3
    kurt = sum((r - mean) ** 4 for r in rets) / n / sd ** 4
    sr_d = mean / sd
    psr_z = sr_d * math.sqrt(n - 1) / math.sqrt(1 - skew * sr_d + (kurt - 1) / 4 * sr_d ** 2)
    psr = 0.5 * (1 + math.erf(psr_z / math.sqrt(2)))
    return dict(mean=mean, sd=sd, hw=hw, mdd=mdd, cagr=cagr, vol=sd * math.sqrt(PPY), sharpe=sharpe, sortino=sortino,
                calmar=cagr / abs(mdd), hit=sum(1 for r in rets if r > 0) / n, psr=psr, n=n)


def monthly(days, eq):
    out, prev, cur_ym, last = [], START_EQ, None, None
    for d, v in zip(days, eq):
        ym = f"{d.year}-{d.month:02d}"
        if cur_ym is not None and ym != cur_ym:
            out.append((cur_ym, last / prev - 1))
            prev = last
        cur_ym, last = ym, v
    out.append((cur_ym, last / prev - 1))
    return out


def pick():
    seed = None
    for cand in range(413, 414):          # seme trovato con una ricerca su 40.000
        days, eq, bm, rets = simulate(cand)
        s = stats(days, eq, rets)
        dd_now = eq[-1] / s["hw"] - 1
        m = monthly(days, eq)
        ytd = eq[-1] / eq[days.index(date(2025, 12, 31))] - 1
        mtd = m[-1][1]
        if (11_900 <= eq[-1] <= 12_700 and -0.115 <= s["mdd"] <= -0.07 and 0.78 <= s["sharpe"] <= 1.25
                and -0.04 <= dd_now <= -0.008 and 0.001 <= rets[-1] <= 0.007 and 0.003 <= mtd <= 0.025 and 0.03 <= ytd <= 0.10
                and max(x[1] for x in m) < 0.065 and min(x[1] for x in m) > -0.065 and 0.05 <= eq[-1] / eq[-400] - 1 <= 0.16):
            seed = cand
            break
    if seed is None:
        raise SystemExit("nessun seme soddisfa i vincoli del fondo")
    for bseed in range(0, 6000):
        days, eq, bm, rets = simulate(seed, bseed)
        f400, b400 = eq[-1] / eq[-400] - 1, bm[-1] / bm[-400] - 1
        if 1.10 <= bm[-1] / bm[0] <= 1.30 and 0.03 <= b400 <= 0.10 and 0.02 <= f400 - b400 <= 0.08 and min(bm[-400:]) / bm[-400] > 0.90:
            return seed, bseed
    raise SystemExit("nessun seme soddisfa i vincoli del benchmark")


seed, bseed = pick()
days, eq, bm, rets = simulate(seed, bseed)
S = stats(days, eq, rets)
M = monthly(days, eq)
EQ = eq[-1]
PREV = eq[-2]
pnl_day = round(EQ - PREV, 2)
i_ytd = days.index(date(2025, 12, 31))
r6 = lambda x: round(x, 6)

rng = random.Random(seed * 7 + 1)

# --- posizioni: pesi sul NAV (negativo = corto) ------------------------------------------------------------
POS = [  # simbolo, venue, strategia, classe, peso, prezzo
    ("BTC", "KRAKEN", "CR-TREND", "Crypto", 0.170, PX["BTC"]),            # prezzo = ultima chiusura delle barre d'esempio
    ("ETH", "KRAKEN", "CR-TREND", "Crypto", 0.110, PX["ETH"]),
    ("SOL", "BINANCE", "CR-XSMOM", "Crypto", 0.085, PX["SOL"]),
    ("SPY", "IBKR", "MA-TREND", "Azioni", 0.165, PX["SPY"]),
    ("GLD", "IBKR", "MA-TREND", "Oro", 0.145, 248.60),
    ("IEF", "IBKR", "MA-TREND", "Obbligazioni", 0.105, 94.72),
    ("EFA", "IBKR", "EQ-MR", "Azioni", 0.060, 83.15),
    ("QQQ", "IBKR", "EQ-MR", "Azioni", -0.050, PX["QQQ"]),
]
day_split = [0.36, 0.19, 0.12, 0.16, 0.09, -0.03, 0.08, 0.03]      # quota del P&L di giornata; somma 1
assert abs(sum(day_split) - 1) < 1e-9
open_pct = [0.084, 0.051, 0.112, 0.046, 0.068, -0.012, 0.019, 0.008]
positions = []
acc = 0.0
for i, ((sym, venue, strat, cls, w, px), ds, op) in enumerate(zip(POS, day_split, open_pct)):
    value = round(EQ * w, 2)
    qty = value / px
    qty = round(qty, 6 if cls == "Crypto" and px > 1000 else (3 if cls == "Crypto" else 0))
    if cls != "Crypto":
        value = round(qty * px, 2)                     # gli ETF si comprano a quote intere
    else:
        value = round(qty * px, 2)
    pd = round(pnl_day * ds, 2) if i < len(POS) - 1 else round(pnl_day - acc, 2)
    acc += pd
    positions.append(dict(symbol=sym, venue=venue, strategy=strat, qty=qty, price=px, value=value,
                          weight=r6(value / EQ), pnl_day=pd, pnl_open=round(abs(value) * op, 2), _cls=cls))
gross = sum(abs(p["value"]) for p in positions)
net = sum(p["value"] for p in positions)
cash = round(EQ - net, 2)


def group(key, order):
    out = []
    for name in order:
        g = [p for p in positions if p[key] == name]
        out.append(dict(name=name, gross=r6(sum(abs(p["value"]) for p in g) / EQ), net=r6(sum(p["value"] for p in g) / EQ)))
    return out


by_class = group("_cls", ["Crypto", "Azioni", "Oro", "Obbligazioni"])
by_venue = group("venue", ["IBKR", "KRAKEN", "BINANCE"])
crypto_w = by_class[0]["gross"]
max_w = max(abs(p["weight"]) for p in positions)

# --- rischio ----------------------------------------------------------------------------------------------
last250 = sorted(rets[-250:])
k = max(1, int(len(last250) * 0.05))
var95 = -last250[k - 1]
es95 = -statistics.fmean(last250[:k])
vol30 = statistics.pstdev(rets[-30:]) * math.sqrt(PPY)
dd_now = EQ / S["hw"] - 1
lev = gross / EQ


# Limiti di config/gerva.yaml (profilo del paper): stessi nomi e stesse soglie di preavviso di gerva/live/snapshot.py::_limits
DD_REDUCE, DD_HALT, DD_KILL, DAILY_LOSS, WEEKLY_LOSS, MAX_WEIGHT, MAX_CRYPTO, VOL_TARGET = 0.20, 0.30, 0.40, 0.04, 0.08, 0.35, 0.40, 0.15


def row(name, value, limit, unit, warn=0.8):
    u = abs(value) / abs(limit)
    return dict(name=name, value=value, limit=limit, unit=unit, status="breach" if u >= 1 else ("warn" if u >= warn else "ok"))


week_ret = EQ / eq[-8] - 1
limits = [
    row("Leva lorda", round(lev, 3), 2.0, "x"),
    row("Caduta dal massimo", r6(dd_now), -DD_KILL, "%", warn=DD_REDUCE / DD_KILL),
    row("Perdita a 24 ore", r6(min(rets[-1], 0.0)), -DAILY_LOSS, "%"),
    row("Perdita a 7 giorni", r6(min(week_ret, 0.0)), -WEEKLY_LOSS, "%"),
    row("Peso massimo di uno strumento", r6(max_w), MAX_WEIGHT, "%", warn=0.9),
    row("Esposizione sulla sede crypto", r6(crypto_w), MAX_CRYPTO, "%", warn=0.9),
]
assert [l["status"] for l in limits].count("warn") == 1 and limits[-1]["status"] == "warn", [(l["name"], l["status"]) for l in limits]

dd_ladder = [
    dict(level=-DD_REDUCE, action="dimezza l'esposizione", hit=dd_now <= -DD_REDUCE),
    dict(level=-DD_HALT, action="un quarto dell'esposizione, nessun aumento", hit=dd_now <= -DD_HALT),
    dict(level=-DD_KILL, action="KILL: chiude tutto e si ferma", hit=dd_now <= -DD_KILL),
]


# --- strategie --------------------------------------------------------------------------------------------
def spark(n, drift, vol, start=100.0):
    v, out = start, []
    for _ in range(n):
        v *= 1 + rng.gauss(drift, vol)
        out.append(round(v, 2))
    return out


def strat_gross(sid):
    return r6(sum(abs(p["value"]) for p in positions if p["strategy"] == sid) / EQ)


strategies = [
    dict(id="CR-TREND", name="Crypto trend BTC+ETH", status="active", allocation=0.30, exposure=strat_gross("CR-TREND"),
         pnl_day_pct=0.0061, pnl_mtd_pct=0.0214, pnl_total_pct=0.3120, sharpe_live=0.94, sharpe_backtest=1.18,
         max_dd=-0.1420, last_signal="2026-11-10T16:00:00Z", spark=spark(30, 0.0022, 0.011)),
    dict(id="CR-XSMOM", name="Crypto momentum trasversale", status="active", allocation=0.20, exposure=strat_gross("CR-XSMOM"),
         pnl_day_pct=0.0027, pnl_mtd_pct=-0.0048, pnl_total_pct=0.1870, sharpe_live=0.71, sharpe_backtest=1.02,
         max_dd=-0.1760, last_signal="2026-11-10T00:05:00Z", spark=spark(30, 0.0002, 0.013)),
    dict(id="EQ-MR", name="Azioni ritorno alla media", status="paused", allocation=0.15, exposure=strat_gross("EQ-MR"),
         pnl_day_pct=0.0009, pnl_mtd_pct=0.0031, pnl_total_pct=0.0640, sharpe_live=None, sharpe_backtest=0.86,
         max_dd=-0.0580, last_signal="2026-11-06T15:35:00Z", spark=spark(30, 0.0003, 0.004)),
    dict(id="MA-TREND", name="Trend multi-asset", status="active", allocation=0.35, exposure=strat_gross("MA-TREND"),
         pnl_day_pct=0.0024, pnl_mtd_pct=0.0093, pnl_total_pct=0.1410, sharpe_live=1.06, sharpe_backtest=0.97,
         max_dd=-0.0710, last_signal="2026-11-10T08:10:00Z", spark=spark(30, 0.0009, 0.005)),
]

# --- ordini (i più recenti per primi) -----------------------------------------------------------------------
orders = [
    ("2026-11-10T16:00:14Z", "BTC", "BUY", 0.004120, round(PX["BTC"] * 0.999, 2), "filled", "CR-TREND", "KRAKEN", ""),
    ("2026-11-10T16:00:09Z", "ETH", "BUY", 0.0850, round(PX["ETH"] * 0.999, 2), "filled", "CR-TREND", "KRAKEN", ""),
    ("2026-11-10T14:31:52Z", "SPY", "BUY", 1, round(PX["SPY"] * 0.999, 2), "pending", "MA-TREND", "IBKR", ""),
    ("2026-11-10T08:10:41Z", "GLD", "BUY", 2, 248.31, "filled", "MA-TREND", "IBKR", ""),
    ("2026-11-10T08:10:37Z", "IEF", "SELL", 2, 94.80, "filled", "MA-TREND", "IBKR", ""),
    ("2026-11-10T00:05:33Z", "SOL", "BUY", 1.250, round(PX["SOL"] * 0.998, 2), "filled", "CR-XSMOM", "BINANCE", ""),
    ("2026-11-10T00:05:31Z", "AVAX", "BUY", 28.000, 23.412, "rejected", "CR-XSMOM", "BINANCE",
     "Esposizione cripto oltre il limite dopo l'ordine (41,2% > 40%)"),
    ("2026-11-09T16:00:11Z", "BTC", "SELL", 0.002300, round(BARS["BTC"]["c"][-2], 2), "filled", "CR-TREND", "KRAKEN", ""),
    ("2026-11-07T08:10:22Z", "SPY", "BUY", 1, round(BARS["SPY"]["c"][-3], 2), "cancelled", "MA-TREND", "IBKR", "Non eseguito entro la chiusura: ordine limite ritirato"),
    ("2026-11-06T15:35:48Z", "QQQ", "SELL", 1, round(BARS["QQQ"]["c"][-3], 2), "filled", "EQ-MR", "IBKR", ""),
    ("2026-11-06T15:35:44Z", "EFA", "BUY", 4, 82.94, "filled", "EQ-MR", "IBKR", ""),
    ("2026-11-05T16:00:07Z", "ETH", "SELL", 0.0400, round(BARS["ETH"]["c"][-6], 2), "filled", "CR-TREND", "KRAKEN", ""),
]
orders = [dict(t=t, symbol=s, side=sd, qty=q, price=p, status=st, strategy=sg, venue=v, reason=r)
          for (t, s, sd, q, p, st, sg, v, r) in orders]

system = dict(
    heartbeat_age_s=4, uptime_s=18 * 86400 + 4 * 3600 + 37 * 60, restarts_24h=0, errors_24h=2,
    components=[
        dict(name="Motore di rischio", status="ok", latency_ms=3, last_ok="2026-11-10T20:44:56Z", detail="7 limiti controllati a ogni ciclo"),
        dict(name="Esecuzione ordini", status="ok", latency_ms=41, last_ok="2026-11-10T20:44:56Z", detail="1 ordine in attesa"),
        dict(name="Dati Kraken", status="ok", latency_ms=182, last_ok="2026-11-10T20:44:52Z", detail=""),
        dict(name="Dati Binance", status="degraded", latency_ms=1840, last_ok="2026-11-10T20:43:10Z", detail="latenza elevata, 2 timeout nell'ultima ora"),
        dict(name="IBKR Gateway", status="ok", latency_ms=96, last_ok="2026-11-10T20:44:50Z", detail="mercati europei chiusi"),
        dict(name="Archivio (SQLite)", status="ok", latency_ms=2, last_ok="2026-11-10T20:44:56Z", detail=""),
        dict(name="Notifiche Telegram", status="ok", latency_ms=310, last_ok="2026-11-10T20:31:07Z", detail=""),
    ],
)

alerts = [
    dict(t="2026-11-10T20:43:10Z", level="warn", msg="Dati Binance: latenza elevata (1.840 ms), 2 timeout nell'ultima ora"),
    dict(t="2026-11-10T16:00:20Z", level="warn", msg=f"Esposizione cripto al {crypto_w / MAX_CRYPTO * 100:.0f}% del limite ({crypto_w * 100:.1f}% su 40%)".replace(".", ",")),
    dict(t="2026-11-10T00:05:31Z", level="warn", msg="Ordine AVAX rifiutato dal controllo di rischio: esposizione cripto oltre il limite"),
    dict(t="2026-11-10T08:10:45Z", level="info", msg="MA-TREND: ribilanciamento completato (2 ordini eseguiti)"),
    dict(t="2026-11-06T15:36:02Z", level="info", msg="EQ-MR messa in pausa: in attesa di 60 giorni di storico in paper"),
    dict(t="2026-11-04T06:12:40Z", level="critical", msg="IBKR Gateway non raggiungibile per 7 minuti: riconnesso automaticamente"),
]
alerts.sort(key=lambda a: a["t"], reverse=True)

from gerva.live import gates as G          # nomi e soglie dei cancelli: quelli del motore, mai riscritti qui

PAPER_DAYS = BOOK_DAYS
_paper = eq[-PAPER_DAYS - 1:]
PAPER_DD = min(v / max(_paper[:i + 1]) - 1 for i, v in enumerate(_paper))
gates = [
    dict(name="Giorni di paper trading", value=PAPER_DAYS, target=G.MIN_DAYS, unit="giorni", ok=PAPER_DAYS >= G.MIN_DAYS),
    dict(name="Disponibilita' del ciclo", value=0.996, target=G.MIN_UPTIME, unit="%", ok=True),
    dict(name="Ordini non riconciliati", value=0, target=0, unit="ordini", ok=True),
    dict(name="KILL scattati", value=0, target=0, unit="eventi", ok=True),
    dict(name="Caduta massima in paper", value=r6(PAPER_DD), target=-G.MAX_DD, unit="%", ok=PAPER_DD >= -G.MAX_DD),
    dict(name="PSR (Sharpe vero > 0)", value=None, target=G.MIN_PSR, unit="", ok=False),             # 12 giorni non bastano: in corso
    dict(name="Scostamento dal backtest", value=None, target=G.MAX_TRACKING, unit="%", ok=False),
    dict(name="Costi reali / costi ipotizzati", value=None, target=G.MAX_COST_RATIO, unit="x", ok=False),
]

N_CURVE = 400
snapshot = dict(
    meta=dict(fund="GERVA Capital", mode="paper", as_of=AS_OF, base_ccy="EUR", version="5.0.0",
              data_label="DEMO: dati di esempio", stale_after_s=120),
    nav=dict(equity=EQ, cash=cash, start_equity=START_EQ, high_water=S["hw"], pnl_day=pnl_day, pnl_day_pct=r6(rets[-1]),
             pnl_mtd_pct=r6(M[-1][1]), pnl_ytd_pct=r6(EQ / eq[i_ytd] - 1), pnl_total_pct=r6(EQ / START_EQ - 1),
             drawdown_pct=r6(dd_now), max_drawdown_pct=r6(S["mdd"])),
    equity_curve=[dict(t=d.isoformat(), equity=e, benchmark=b) for d, e, b in zip(days[-N_CURVE:], eq[-N_CURVE:], bm[-N_CURVE:])],
    monthly_returns=[dict(ym=ym, ret=r6(r)) for ym, r in M],
    performance=dict(cagr=r6(S["cagr"]), vol=r6(S["vol"]), sharpe=round(S["sharpe"], 3), sortino=round(S["sortino"], 3),
                     calmar=round(S["calmar"], 3), hit_rate_days=r6(S["hit"]), best_month=r6(max(x[1] for x in M)),
                     worst_month=r6(min(x[1] for x in M)), psr=round(S["psr"], 4), days=S["n"]),
    exposure=dict(gross=r6(gross / EQ), net=r6(net / EQ), leverage=round(lev, 3), max_leverage=2.0,
                  by_asset_class=by_class, by_venue=by_venue),
    positions=[{k: v for k, v in p.items() if not k.startswith("_")} for p in positions],
    risk=dict(state="NORMAL", state_reason="Tutti i limiti rispettati; esposizione cripto vicina alla soglia.",
              var_95_1d_pct=r6(-var95), es_95_1d_pct=r6(-es95), vol_target=VOL_TARGET, vol_realized_30d=r6(vol30),
              limits=limits, dd_ladder=dd_ladder),
    strategies=strategies,
    orders=orders,
    system=system,
    alerts=alerts,
    gates=gates,
    ai=dict(
        overlay=dict(valido=True, nota="", globale=1.0, motivo_globale="", scade="2026-11-11T02:45:00Z", strategie=[
            dict(id="CR-XSMOM", mult=0.5, motivo="Rischio evento: decisione sui tassi domani; il momentum sulle monete minori è il più sensibile.",
                 fonti=["macro:fomc-2026-11", "news:4821"])]),
        regime=dict(stato="teso", punteggio=2.0, scala_esposizione=False),
        conviction=[dict(asset=sym, score=BARS[sym]["conviction"][-1], livello=conv_tier(BARS[sym]["conviction"][-1])) for sym in CRYPTO]),
)


# --- scrittura: chiavi di primo livello su righe proprie, elementi delle liste su una riga -----------------
def one(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(", ", ": "))


def block(obj, ind=1):
    pad = " " * ind
    lines = []
    for key, val in obj.items():
        if isinstance(val, list) and val and isinstance(val[0], dict):
            body = ",\n".join(f"{pad}  {one(x)}" for x in val)
            lines.append(f'{pad}"{key}": [\n{body}\n{pad}]')
        elif isinstance(val, dict) and any(isinstance(v, (list, dict)) for v in val.values()):
            lines.append(f'{pad}"{key}": {block(val, ind + 1)}')
        else:
            lines.append(f'{pad}"{key}": {one(val)}')
    return "{\n" + ",\n".join(lines) + "\n" + " " * (ind - 1) + "}"


text = block(snapshot) + "\n"
json.loads(text)
open(OUT, "w", encoding="utf-8").write(text)

# --- libro dei trade, confronto e barre: la stessa storia della fotografia ------------------------------------------
first = K - BOOK_DAYS + 1
book_start = eq[-BOOK_DAYS]                               # il libro lavora sullo stesso capitale: parte dal patrimonio di quel giorno
book_eq, book_open, book_closed, book_daily = run_book(K, book_start, first)
for t in book_open.values():
    t.pop("_i")
last_days = [d.isoformat() for d in days[-BOOK_DAYS:]]
assert last_days == BARS["BTC"]["t"][-BOOK_DAYS:], "le date del confronto devono essere quelle delle barre"
shadow = [dict(day=BARS["BTC"]["t"][i], coins={sym: dict(gq=BARS[sym]["gq"][i], gq_tier=gq_tier(BARS[sym]["gq"][i]), conviction=BARS[sym]["conviction"][i],
                                                          conviction_tier=conv_tier(BARS[sym]["conviction"][i])) for sym in CRYPTO}) for i in range(K - 2, K + 1)]
log = [dict(day=c["closed"], msg=f"chiuso {c['symbol']} ({c['why']}): {c['R']:+.2f} R".replace(".", ",")) for c in book_closed[-4:]]
log += [dict(day=t["opened"], msg=f"aperto {t['symbol']} ({t['tier']}): leva {t['leverage']:.1f}x, rischio {t['risk']:.2f}".replace(".", ",")) for t in book_open.values()]
log.sort(key=lambda e: e["day"])
tradebook = dict(example=True, label="ESEMPIO: libro dei trade dimostrativo, costruito sulle barre d'esempio", asof=last_days[-1], equity=book_eq, start_equity=book_start,
                 open=book_open, closed=book_closed, log=log, shadow=shadow)
(STATIC / "sample_tradebook.json").write_text(json.dumps(tradebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

crng = random.Random(seed * 13 + 5)
legacy = 1_050_000.0
rows = []
spy = dict(zip(BARS["SPY"]["t"], BARS["SPY"]["c"]))
last_spy = None
for j, day in enumerate(last_days):
    if j:
        legacy = round(legacy * (1 + crng.gauss(0.0004, 0.006)), 2)
    last_spy = spy.get(day, last_spy)
    libro = eq[-BOOK_DAYS + j]
    trade = round(book_daily[day] - book_start, 2)
    rows.append(dict(data=day, nuovo_libro=libro, nuovo_trade=trade, nuovo_totale=round(libro + trade, 2), legacy_nav=legacy, legacy_flusso=0.0, legacy_fonte="esempio",
                     spy=last_spy, btc=BARS["BTC"]["c"][first + j], eurusd=1.08, nuovo_modo="paper", nuovo_as_of=None))
(STATIC / "sample_compare.json").write_text(json.dumps(dict(example=True, label="ESEMPIO: confronto dimostrativo", rows=rows), ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
_ohlc["label"] = "ESEMPIO: prezzi dimostrativi, portati alle date della fotografia d'esempio"
(STATIC / "sample_ohlc.json").write_text(json.dumps(_ohlc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
print("K", K, "trade chiusi", len(book_closed), "aperti", list(book_open), "libro", book_start, "->", book_eq, "BTC", PX["BTC"])
print("seed", seed, "equity", EQ, "day", pnl_day, f"{rets[-1]:.4%}", "mtd", f"{M[-1][1]:.3%}", "ytd", f"{EQ / eq[i_ytd] - 1:.3%}",
      "tot", f"{EQ / START_EQ - 1:.2%}")
print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in S.items()})
print("dd_now", round(dd_now, 4), "gross", round(gross / EQ, 4), "net", round(net / EQ, 4), "cash", cash, "var", round(var95, 4), "es", round(es95, 4), "vol30", round(vol30, 4))
print("months", len(M), "best", max(M, key=lambda x: x[1]), "worst", min(M, key=lambda x: x[1]))
print("limits", [(l["name"], l["status"]) for l in limits])
print("bench 400d", round(bm[-1] / bm[-400] - 1, 4), "fund 400d", round(eq[-1] / eq[-400] - 1, 4), "bytes", len(text))
