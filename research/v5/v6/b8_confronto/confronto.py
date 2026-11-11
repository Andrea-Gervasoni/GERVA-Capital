#!/usr/bin/env python3
"""
B8 - confronto in avanti tra il NUOVO fondo (gerva/) e il sistema ORIGINALE (GERVA-Q + firm/), con SPY e BTC di riferimento.

Si lancia UNA VOLTA AL GIORNO (alla stessa ora, meglio dopo la chiusura USA):

    /tmp/gv/bin/python research/v5/v6/b8_confronto/confronto.py                 # aggiunge la riga di oggi e stampa il confronto
    /tmp/gv/bin/python research/v5/v6/b8_confronto/confronto.py --report-only   # solo il confronto
    /tmp/gv/bin/python research/v5/v6/b8_confronto/confronto.py --selfcheck     # prova su dati sintetici (non tocca nulla)

Da dove legge (solo lettura; non modifica firm/ ne' gerva/):
  nuovo fondo   var/gerva/snapshot.json  -> nav.equity (formato di gerva/live/snapshot.py), piu'
                var/gerva/tradebook.json -> equity (stato del libro dei trade, gerva/live/tradecycle.py), se esiste
  originale     1) research/v5/v6/b8_confronto/legacy_nav.csv, che Andrea puo' aggiornare a mano: righe `data,nav_eur[,flusso_eur]`
                   (data AAAA-MM-GG; flusso = versamenti (+) o prelievi (-) del giorno, facoltativo). Vale l'ultima riga <= oggi.
                2) altrimenti var/firm.sqlite, tabella nav_marks, pod='pod_zero' (la scrive firm/ibkr.py dal NetLiquidation IBKR)
                3) altrimenti <GERVA_Q_PATH>/state/nav_log.csv, colonna nav_eur (la scrive GERVA-Q)
  riferimenti   SPY e EURUSD da Yahoo, BTC da Binance (tramite gerva.data.sources); senza rete restano vuoti e si riempiono a mano.

Scrive solo `confronto_nav.csv` nella propria cartella: una riga per data (rilanciare lo stesso giorno sostituisce la riga).

Che cosa stampa, sui soli giorni COMUNI (entrambi i NAV presenti): rendimento cumulato, volatilita', Sharpe, caduta massima,
differenza di rendimento (tracking difference), z della differenza a pari volatilita' e giorni ancora necessari.
ATTENZIONE (02_potenza.out): con correlazione 0,66 servono circa 6.200 giorni per vedere una differenza di Sharpe di 0,5
e 1.550 per una di 1,0 (80% di potenza). A 90 giorni il confronto misura la COERENZA con il backtest, non la superiorita'.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
COLS = ["data", "nuovo_libro", "nuovo_trade", "nuovo_totale", "legacy_nav", "legacy_flusso", "legacy_fonte", "spy", "btc", "eurusd",
        "nuovo_modo", "nuovo_as_of"]
Z80, Z95, Z90 = 0.8416, 1.6449, 1.2816
MIN_DAYS, DD_MULT, Z_WIN = 90, 1.5, 1.3            # criteri proposti (REPORT.md, sezione 5)


# ------------------------------------------------------------------------------------------------ letture
def _f(x):
    try:
        v = float(x)
        return v if math.isfinite(v) and v > 0 else None
    except (TypeError, ValueError):
        return None


def read_new(var_dir: str) -> dict:
    out = dict(nuovo_libro=None, nuovo_trade=None, nuovo_modo="", nuovo_as_of="")
    try:
        s = json.load(open(os.path.join(var_dir, "snapshot.json")))
        out["nuovo_libro"] = _f((s.get("nav") or {}).get("equity"))
        out["nuovo_modo"] = str((s.get("meta") or {}).get("mode") or "")
        out["nuovo_as_of"] = str((s.get("meta") or {}).get("as_of") or "")
    except (OSError, ValueError):
        pass
    try:
        t = json.load(open(os.path.join(var_dir, "tradebook.json")))
        out["nuovo_trade"] = _f(t.get("equity"))
    except (OSError, ValueError):
        pass
    return out


def read_legacy(day: str, legacy_file: str, db_path: str, gq_path: str | None) -> dict:
    """Ultimo NAV noto del conto originale con data <= day. Ordine: file di Andrea, firm.sqlite, GERVA-Q."""
    try:
        rows = [r for r in csv.DictReader(open(legacy_file)) if (r.get("data") or "")[:10] <= day and _f(r.get("nav_eur"))]
        if rows:
            r = sorted(rows, key=lambda x: x["data"])[-1]
            flow = float(r.get("flusso_eur") or 0) if r["data"][:10] == day else 0.0
            return dict(legacy_nav=_f(r["nav_eur"]), legacy_flusso=flow, legacy_fonte=f"file:{r['data'][:10]}")
    except (OSError, ValueError, KeyError):
        pass
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        r = con.execute("SELECT day, nav FROM nav_marks WHERE pod='pod_zero' AND nav>0 AND day<=? ORDER BY day DESC LIMIT 1", (day,)).fetchone()
        con.close()
        if r and _f(r[1]):
            return dict(legacy_nav=_f(r[1]), legacy_flusso=0.0, legacy_fonte=f"firm.sqlite:{r[0]}")
    except sqlite3.Error:
        pass
    if gq_path:
        try:
            rows = list(csv.DictReader(open(os.path.join(os.path.expanduser(gq_path), "state", "nav_log.csv"))))
            rows = [r for r in rows if _f(r.get("nav_eur"))]
            if rows:
                r = rows[-1]
                d = next((str(r[k])[:10] for k in ("date", "data", "day", "asof", "ts") if r.get(k)), "?")
                if d == "?" or d <= day:
                    return dict(legacy_nav=_f(r["nav_eur"]), legacy_flusso=0.0, legacy_fonte=f"gervaq:{d}")
        except (OSError, ValueError):
            pass
    return dict(legacy_nav=None, legacy_flusso=0.0, legacy_fonte="")


def read_market(no_net: bool) -> dict:
    out = dict(spy=None, btc=None, eurusd=None)
    if no_net:
        return out
    try:
        sys.path.insert(0, ROOT)
        from gerva.data import sources as DS
    except Exception:
        return out
    for key, fn in (("spy", lambda: DS.yahoo("SPY", "1d")["close"]), ("eurusd", lambda: DS.yahoo("EURUSD=X", "1d")["close"]),
                    ("btc", lambda: DS.binance_recent("BTCUSDT", "1d", 5)["close"])):
        try:
            s = fn().dropna()
            out[key] = _f(s.iloc[-1])
        except Exception:
            pass
    return out


# ------------------------------------------------------------------------------------------------ registro
def load_csv(path: str) -> list[dict]:
    try:
        return list(csv.DictReader(open(path)))
    except OSError:
        return []


def save_csv(path: str, rows: list[dict]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in sorted(rows, key=lambda x: x["data"]):
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in COLS})
    os.replace(tmp, path)


def append(path: str, day: str, var_dir: str, legacy_file: str, db_path: str, gq_path: str | None, no_net: bool,
           market: dict | None = None) -> dict:
    row = dict(data=day, **read_new(var_dir), **read_legacy(day, legacy_file, db_path, gq_path), **(market or read_market(no_net)))
    parts = [v for v in (row["nuovo_libro"], row["nuovo_trade"]) if v]
    row["nuovo_totale"] = sum(parts) if parts else None
    rows = [r for r in load_csv(path) if r.get("data") != day] + [row]
    save_csv(path, rows)
    return row


# ------------------------------------------------------------------------------------------------ statistica
def _mean(x): return sum(x) / len(x)
def _std(x):
    m = _mean(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1)) if len(x) > 1 else float("nan")
def _corr(a, b):
    ma, mb, sa, sb = _mean(a), _mean(b), _std(a), _std(b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / ((len(a) - 1) * sa * sb) if sa > 0 and sb > 0 else float("nan")
def _phi(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def perf(r: list[float], per_year: float, rf_annual: float = 0.0) -> dict:
    """r: rendimenti per riga; per_year: righe per anno."""
    if not r:
        return dict(n=0, cum=float("nan"), vol=float("nan"), sharpe=float("nan"), maxdd=float("nan"))
    eq, peak, dd = 1.0, 1.0, 0.0
    for x in r:
        eq *= 1 + x
        peak = max(peak, eq)
        dd = min(dd, eq / peak - 1)
    sd = _std(r)
    sh = (_mean(r) - rf_annual / per_year) / sd * math.sqrt(per_year) if len(r) > 1 and sd > 0 else float("nan")
    return dict(n=len(r), cum=eq - 1, vol=sd * math.sqrt(per_year) if len(r) > 1 else float("nan"), sharpe=sh, maxdd=dd)


def diff_stats(a: list[float], b: list[float], per_year: float) -> dict:
    """a = nuovo, b = originale, stesse righe. z_raw: differenza media dei rendimenti; z_vol: differenza a PARI volatilita'
    (a/sd_a - b/sd_b), cioe' la differenza di Sharpe; giorni ancora necessari a questo ritmo e per Delta 0,5 / 1,0."""
    n = len(a)
    if n < 3:
        return dict(n=n, z_raw=float("nan"), z_vol=float("nan"), rho=float("nan"), te=float("nan"), d_sharpe=float("nan"),
                    need_now=None, need_05=None, need_10=None)
    d = [x - y for x, y in zip(a, b)]
    sa, sb, sd = _std(a), _std(b), _std(d)
    z_raw = _mean(d) / sd * math.sqrt(n) if sd > 0 else float("nan")
    if sa > 0 and sb > 0:
        u = [x / sa - y / sb for x, y in zip(a, b)]
        su = _std(u)
        z_vol = _mean(u) / su * math.sqrt(n) if su > 0 else float("nan")
        d_sh = _mean(u) * math.sqrt(per_year)
    else:
        z_vol, d_sh = float("nan"), float("nan")
    rho = _corr(a, b)
    k = (Z95 + Z80) ** 2 * 2 * (1 - rho) * per_year if rho == rho else float("nan")      # righe per Delta = 1
    need_now = int(math.ceil(n * ((Z95 + Z80) / z_vol) ** 2)) if z_vol == z_vol and z_vol > 0 else None
    return dict(n=n, z_raw=z_raw, z_vol=z_vol, rho=rho, te=sd * math.sqrt(per_year), d_sharpe=d_sh,
                need_now=need_now, need_05=int(math.ceil(k / 0.25)) if k == k else None, need_10=int(math.ceil(k)) if k == k else None)


def series(rows: list[dict], legacy_usd: bool = True) -> dict:
    """Rendimenti per riga sulle righe dove ENTRAMBI i NAV esistono (in questa e nella riga comune precedente)."""
    rows = sorted([r for r in rows if _f(r.get("nuovo_totale")) and _f(r.get("legacy_nav"))], key=lambda x: x["data"])
    fx_ok = legacy_usd and all(_f(r.get("eurusd")) for r in rows)
    out = dict(dates=[], nuovo=[], legacy=[], spy=[], btc=[], legacy_ccy="USD" if fx_ok else "EUR (cambio non applicato)")
    for p, c in zip(rows, rows[1:]):
        flow = float(c.get("legacy_flusso") or 0)
        lr = (float(c["legacy_nav"]) - flow) / float(p["legacy_nav"]) - 1
        if fx_ok:
            lr = (1 + lr) * float(c["eurusd"]) / float(p["eurusd"]) - 1
        out["dates"].append(c["data"])
        out["nuovo"].append(float(c["nuovo_totale"]) / float(p["nuovo_totale"]) - 1)
        out["legacy"].append(lr)
        for k in ("spy", "btc"):
            out[k].append(float(c[k]) / float(p[k]) - 1 if _f(c.get(k)) and _f(p.get(k)) else None)
    if out["dates"]:
        d0 = dt.date.fromisoformat(rows[0]["data"]); d1 = dt.date.fromisoformat(rows[-1]["data"])
        out["per_year"] = 365.0 * len(out["dates"]) / max((d1 - d0).days, 1)
        out["span_days"] = (d1 - d0).days
    else:
        out["per_year"], out["span_days"] = 365.0, 0
    return out


def verdict(pn: dict, pl: dict, ds: dict, span_days: int) -> tuple[str, list[str]]:
    """I criteri di REPORT.md sezione 5. Ritorna (esito, motivi)."""
    why = []
    if span_days < MIN_DAYS:
        return "IN CORSO", [f"{span_days} giorni comuni su {MIN_DAYS} richiesti"]
    more = pn["cum"] > pl["cum"]
    dd_ok = pn["maxdd"] >= DD_MULT * min(pl["maxdd"], -0.02)
    z = ds["z_vol"]
    why.append(f"rendimento {'maggiore' if more else 'minore'} ({pn['cum']:+.2%} contro {pl['cum']:+.2%})")
    why.append(f"caduta {pn['maxdd']:.2%} contro limite {DD_MULT * min(pl['maxdd'], -0.02):.2%}: {'ok' if dd_ok else 'NO'}")
    why.append(f"z a pari volatilita' {z:+.2f}")
    if z == z and z > Z_WIN:
        return "BATTE (criterio B: z > 1,3)", why
    if z == z and z < -Z_WIN:
        return "BATTUTO (z < -1,3)", why
    if more and dd_ok:
        return "BATTE (criterio A: rende di piu', caduta entro 1,5x) - non ancora significativo", why
    return "NON BATTE (per ora)", why


def report(rows: list[dict], rf_annual: float = 0.0, out=print) -> dict:
    s = series(rows)
    n = len(s["dates"])
    out(f"\n=== CONFRONTO IN AVANTI: {n} rendimenti comuni" + (f", dal {s['dates'][0]} al {s['dates'][-1]} ({s['span_days']} giorni)" if n else "") + " ===")
    if n < 2:
        out("Servono almeno 3 righe con ENTRAMBI i valori (nuovo fondo e conto originale). Righe nel registro: "
            f"{len(rows)}; con il nuovo fondo: {sum(1 for r in rows if _f(r.get('nuovo_totale')))}; con l'originale: {sum(1 for r in rows if _f(r.get('legacy_nav')))}.")
        return dict(n=n)
    py = s["per_year"]
    P = {"NUOVO (gerva)": perf(s["nuovo"], py, rf_annual), f"ORIGINALE ({s['legacy_ccy']})": perf(s["legacy"], py, rf_annual)}
    for k in ("spy", "btc"):
        x = [v for v in s[k] if v is not None]
        if len(x) == n:
            P[k.upper()] = perf(x, py, rf_annual)
    out(f"{'':28s} {'cumulato':>9s} {'vol annua':>10s} {'Sharpe':>7s} {'caduta max':>11s}")
    for k, p in P.items():
        out(f"{k:28s} {p['cum']:+9.2%} {p['vol']:10.1%} {p['sharpe']:7.2f} {p['maxdd']:11.2%}")
    pn, pl = P["NUOVO (gerva)"], P[f"ORIGINALE ({s['legacy_ccy']})"]
    ds = diff_stats(s["nuovo"], s["legacy"], py)
    lev = pl["vol"] / pn["vol"] if pn["vol"] and pn["vol"] == pn["vol"] and pn["vol"] > 0 else float("nan")
    out(f"\ndifferenza di rendimento (nuovo - originale): {pn['cum'] - pl['cum']:+.2%}; errore di replica {ds['te']:.1%} l'anno; correlazione {ds['rho']:.2f}")
    out(f"a pari volatilita' il nuovo fondo andrebbe portato a {lev:.2f}x: rendimento {pn['cum'] * lev:+.2%} (approssimato) contro {pl['cum']:+.2%}")
    out(f"z della differenza: grezza {ds['z_raw']:+.2f}; a pari volatilita' {ds['z_vol']:+.2f} (differenza di Sharpe stimata {ds['d_sharpe']:+.2f}); "
        f"P(un distacco cosi' senza alcuna differenza vera) = {1 - _phi(abs(ds['z_vol'])) if ds['z_vol'] == ds['z_vol'] else float('nan'):.0%}")
    if ds["need_now"]:
        out(f"giorni necessari (80% potenza, 5%): al ritmo osservato {ds['need_now']} righe, ne mancano {max(ds['need_now'] - n, 0)}")
    else:
        out("giorni necessari al ritmo osservato: non definiti (il nuovo fondo non e' avanti a pari volatilita')")
    out(f"con la correlazione misurata: {ds['need_05']} righe per una differenza vera di Sharpe 0,5; {ds['need_10']} per 1,0")
    for k in ("spy", "btc"):
        x = s[k]
        if all(v is not None for v in x):
            for lab, y in (("nuovo", s["nuovo"]), ("originale", s["legacy"])):
                sx = _std(x)
                beta = _corr(y, x) * _std(y) / sx if sx > 0 else float("nan")
                out(f"  beta del {lab} su {k.upper()}: {beta:.2f}")
    v, why = verdict(pn, pl, ds, s["span_days"])
    out(f"\nESITO: {v}\n  " + "\n  ".join(why))
    return dict(n=n, perf=P, diff=ds, verdict=v, per_year=py)


# ------------------------------------------------------------------------------------------------ autoverifica
def selfcheck() -> int:
    import random
    import tempfile
    rnd = random.Random(20261111)
    fails = []

    def ok(name, cond, detail=""):
        print(("  ok   " if cond else "  FALLITO ") + name + (f"  [{detail}]" if detail else ""))
        if not cond:
            fails.append(name)

    with tempfile.TemporaryDirectory() as tmp:
        var_dir = os.path.join(tmp, "var"); os.makedirs(var_dir)
        legacy_file, path = os.path.join(tmp, "legacy_nav.csv"), os.path.join(tmp, "confronto_nav.csv")
        n, rho = 400, 0.6
        mu_a, sd_a, mu_b, sd_b = 0.0012, 0.008, 0.0004, 0.010       # il "nuovo" ha Sharpe piu' alto per costruzione
        ra, rb = [], []
        for _ in range(n):
            z1, z2 = rnd.gauss(0, 1), rnd.gauss(0, 1)
            ra.append(mu_a + sd_a * z1); rb.append(mu_b + sd_b * (rho * z1 + math.sqrt(1 - rho ** 2) * z2))
        d0 = dt.date(2026, 11, 12)
        book, trade, leg, spy = 9000.0, 3000.0, 1_060_000.0, 750.0
        with open(legacy_file, "w") as f:
            f.write("data,nav_eur,flusso_eur\n")
        row0 = None
        for i in range(n + 1):
            day = (d0 + dt.timedelta(days=i)).isoformat()
            if i:
                book *= 1 + ra[i - 1]; trade *= 1 + ra[i - 1]; leg *= 1 + rb[i - 1]; spy *= 1 + rb[i - 1] * 0.5
            flow = 50_000.0 if i == 200 else 0.0                     # un versamento sul conto originale: non deve contare come rendimento
            if flow:
                leg += flow
            json.dump(dict(meta=dict(mode="paper", as_of=day), nav=dict(equity=book)), open(os.path.join(var_dir, "snapshot.json"), "w"))
            json.dump(dict(asof=day, equity=trade, open={}, closed=[]), open(os.path.join(var_dir, "tradebook.json"), "w"))
            with open(legacy_file, "a") as f:
                f.write(f"{day},{leg:.6f},{flow}\n")
            r = append(path, day, var_dir, legacy_file, os.path.join(tmp, "nessuno.sqlite"), None, True, market=dict(spy=spy, btc=None, eurusd=1.0))
            row0 = row0 or r
        rows = load_csv(path)
        ok("una riga per giorno", len(rows) == n + 1, f"{len(rows)}")
        append(path, rows[-1]["data"], var_dir, legacy_file, os.path.join(tmp, "nessuno.sqlite"), None, True, market=dict(spy=spy, btc=None, eurusd=1.0))
        ok("rilanciare lo stesso giorno non duplica", len(load_csv(path)) == n + 1)
        ok("nuovo_totale = libro + trade", abs(float(rows[0]["nuovo_totale"]) - 12000.0) < 1e-6)
        s = series(rows)
        ok("rendimenti del nuovo fondo ricostruiti", max(abs(x - y) for x, y in zip(s["nuovo"], ra)) < 1e-9)
        ok("il versamento non conta come rendimento", max(abs(x - y) for x, y in zip(s["legacy"], rb)) < 1e-6,
           f"scarto {max(abs(x - y) for x, y in zip(s['legacy'], rb)):.1e}")
        ok("righe per anno = 365 con righe giornaliere", abs(s["per_year"] - 365.0) < 1e-9)
        pa = perf(ra, 365.0)
        cum = 1.0
        for x in ra:
            cum *= 1 + x
        ok("cumulato", abs(pa["cum"] - (cum - 1)) < 1e-12)
        ok("volatilita' vicina a quella generata", abs(pa["vol"] / (sd_a * math.sqrt(365)) - 1) < 0.10, f"{pa['vol']:.3f}")
        ok("caduta massima su percorso noto (1,1 -> 0,55 = -50%)", abs(perf([0.10, -0.50, 0.20, -0.10], 365)["maxdd"] + 0.50) < 1e-12)
        ok("Sharpe con tasso", abs(perf([0.01, 0.03], 2.0, rf_annual=0.02)["sharpe"] - ((0.02 - 0.01) / _std([0.01, 0.03]) * math.sqrt(2))) < 1e-12)
        ds = diff_stats(ra, rb, 365.0)
        d = [x - y for x, y in zip(ra, rb)]
        ok("z grezza = t della differenza appaiata", abs(ds["z_raw"] - _mean(d) / _std(d) * math.sqrt(n)) < 1e-12)
        ok("correlazione vicina a quella generata", abs(ds["rho"] - rho) < 0.10, f"{ds['rho']:.2f}")
        true_dsh = (mu_a / sd_a - mu_b / sd_b) * math.sqrt(365)
        est = []
        for _ in range(60):                                          # 60 repliche: la media della stima deve cadere sul valore vero
            a, b = [], []
            for _ in range(n):
                z1, z2 = rnd.gauss(0, 1), rnd.gauss(0, 1)
                a.append(mu_a + sd_a * z1); b.append(mu_b + sd_b * (rho * z1 + math.sqrt(1 - rho ** 2) * z2))
            est.append(diff_stats(a, b, 365.0)["d_sharpe"])
        se = math.sqrt(2 * (1 - rho) * 365 / n)
        ok("differenza di Sharpe: media di 60 repliche entro 3 errori standard dal vero", abs(_mean(est) - true_dsh) < 3 * se / math.sqrt(60),
           f"media {_mean(est):.2f}, vero {true_dsh:.2f}, es della media {se / math.sqrt(60):.2f}")
        ok("dispersione della stima = formula sqrt(2(1-rho)/anni)", abs(_std(est) / se - 1) < 0.30, f"osservata {_std(est):.2f}, formula {se:.2f}")
        ok("giorni per Delta 1,0 = (1,645+0,842)^2 * 2(1-rho) * 365", abs(ds["need_10"] - (Z95 + Z80) ** 2 * 2 * (1 - ds["rho"]) * 365) <= 1)
        ok("giorni per Delta 0,5 = 4 volte", abs(ds["need_05"] - 4 * (Z95 + Z80) ** 2 * 2 * (1 - ds["rho"]) * 365) <= 1)
        same = diff_stats(ra, ra, 365.0)
        ok("serie identiche: nessun giorno 'necessario', z non definita", same["need_now"] is None and not same["z_raw"] == same["z_raw"])
        # potenza: su 300 coppie senza differenza vera, z > 1,3 deve uscire circa il 10% delle volte
        hits = 0
        for _ in range(300):
            a, b = [], []
            for _ in range(120):
                z1, z2 = rnd.gauss(0, 1), rnd.gauss(0, 1)
                a.append(0.0005 + 0.008 * z1); b.append(0.000625 + 0.010 * (rho * z1 + math.sqrt(1 - rho ** 2) * z2))
            hits += diff_stats(a, b, 365.0)["z_vol"] > Z_WIN
        ok("falsi positivi di z > 1,3 senza differenza vera tra 4% e 17%", 0.04 <= hits / 300 <= 0.17, f"{hits / 300:.0%}")
        res = report(rows, out=lambda *_: None)
        ok("esito calcolato dopo >= 90 giorni", res["verdict"].startswith(("BATTE", "NON BATTE", "BATTUTO")), res["verdict"])
        ok("prima di 90 giorni l'esito e' IN CORSO", report(rows[:40], out=lambda *_: None)["verdict"] == "IN CORSO")
        ok("letture mancanti non fanno fallire", read_new(os.path.join(tmp, "vuoto"))["nuovo_libro"] is None
           and read_legacy("2026-11-12", os.path.join(tmp, "x.csv"), os.path.join(tmp, "y.sqlite"), None)["legacy_nav"] is None)
        # firm.sqlite: la tabella nav_marks viene letta in sola lettura
        dbp = os.path.join(tmp, "firm.sqlite")
        con = sqlite3.connect(dbp); con.execute("CREATE TABLE nav_marks(id INTEGER PRIMARY KEY, day TEXT, pod TEXT, nav REAL, capital REAL, gross REAL)")
        con.execute("INSERT INTO nav_marks(day,pod,nav) VALUES('2026-11-10','pod_zero',1059059.0)"); con.execute("INSERT INTO nav_marks(day,pod,nav) VALUES('2026-11-11','pod_zero',1089666.0)")
        con.execute("INSERT INTO nav_marks(day,pod,nav) VALUES('2026-11-11','firm',5.0)"); con.commit(); con.close()
        lg = read_legacy("2026-11-11", os.path.join(tmp, "x.csv"), dbp, None)
        ok("NAV dell'originale da firm.sqlite (nav_marks, pod_zero)", lg["legacy_nav"] == 1089666.0 and lg["legacy_fonte"] == "firm.sqlite:2026-11-11")
        ok("il file di Andrea ha la precedenza sul database", read_legacy(rows[3]["data"], legacy_file, dbp, None)["legacy_fonte"].startswith("file:"))
    print("AUTOVERIFICA: " + ("tutto ok" if not fails else f"{len(fails)} controlli falliti: {fails}"))
    return 1 if fails else 0


# ------------------------------------------------------------------------------------------------ comando
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Confronto giornaliero nuovo fondo / sistema originale / SPY / BTC")
    ap.add_argument("--var-dir", default=os.path.join(ROOT, "var", "gerva"))
    ap.add_argument("--legacy-file", default=os.path.join(HERE, "legacy_nav.csv"))
    ap.add_argument("--firm-db", default=os.path.join(os.environ.get("GERVA_VAR", os.path.join(ROOT, "var")), "firm.sqlite"))
    ap.add_argument("--gervaq", default=os.environ.get("GERVA_Q_PATH"))
    ap.add_argument("--csv", default=os.path.join(HERE, "confronto_nav.csv"))
    ap.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    ap.add_argument("--rf", type=float, default=0.0, help="tasso annuo senza rischio per lo Sharpe (es. 0.035)")
    ap.add_argument("--no-net", action="store_true", help="non scaricare SPY, BTC, EURUSD")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args(argv)
    if a.selfcheck:
        return selfcheck()
    if not a.report_only:
        r = append(a.csv, a.date, a.var_dir, a.legacy_file, a.firm_db, a.gervaq, a.no_net)
        print(f"[{a.date}] nuovo fondo: libro {r['nuovo_libro']} + trade {r['nuovo_trade']} = {r['nuovo_totale']} ({r['nuovo_modo'] or 'nessuna fotografia'}); "
              f"originale: {r['legacy_nav']} ({r['legacy_fonte'] or 'nessuna fonte: aggiornare legacy_nav.csv'}); SPY {r['spy']}, BTC {r['btc']}, EURUSD {r['eurusd']}")
    report(load_csv(a.csv), a.rf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
