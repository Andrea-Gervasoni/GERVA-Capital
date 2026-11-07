"""
Strategie in codice dai paper: girano alla velocita' di una macchina sul conto PAPER di Alpaca, le accende il comitato.

Ogni strategia ha una fonte pubblicata, un'ipotesi scritta (perche' dovrebbe funzionare), un backtest sui dati storici di Alpaca al netto
dei costi, e una prova registrata nel registro globale (conta nel Deflated Sharpe: piu' prove si fanno, piu' alta la soglia per tutti).
Il risultato del backtest va AL COMITATO come idea "accendere la strategia": il comitato decide. Il cancello statistico e' un'informazione
per il voto, non un blocco. Accesa, la strategia gira da sola; spenta, non tocca niente.

  crypto_tsmom          Momentum di serie storica sulle crypto (Liu e Tsyvinski, Review of Financial Studies 2021; Moskowitz, Ooi e
                        Pedersen, Journal of Financial Economics 2012), solo long (Alpaca non permette short crypto), con volatilita'
                        obiettivo (Moreira e Muir 2017; Harvey et al. 2018): si tiene una moneta quando il suo rendimento sulle ultime
                        24, 72 e 168 ore e' positivo, in misura inversa alla sua volatilita'. Barre a un'ora.
  spy_intraday_momentum Momentum intraday del mercato (Gao, Han, Li e Zhou, Journal of Financial Economics 2018): il rendimento
                        dell'S&P 500 dalla chiusura di ieri alle 10:00 di New York predice quello dell'ultima mezz'ora. Si entra alle 15:30
                        nella direzione della prima mezz'ora e si esce alla chiusura. Barre a 5 minuti.
Limiti dichiarati: i paper misurano periodi passati (il momentum intraday e' piu' debole dopo la pubblicazione); costi e spread di Alpaca
sono stimati; il backtest crypto usa rendimenti giornalieri per il registro delle prove (annualizzati su 252).
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import urllib.parse

import numpy as np
import pandas as pd

from . import audit, crypto_venue as V, db, events, paths
from . import settings as S

STRATS = {
    "crypto_tsmom": dict(
        nome="Momentum crypto con volatilita' obiettivo", autore="senior_crypto",
        fonte="Liu & Tsyvinski (2021, RFS) 'Risks and Returns of Cryptocurrency'; Moskowitz, Ooi & Pedersen (2012, JFE); Moreira & Muir (2017, JF)",
        ipotesi="Le crypto mostrano momentum di serie storica: l'attenzione e i flussi degli investitori arrivano a ondate, quindi un rendimento positivo "
                "nelle ultime ore/giorni tende a continuare. Pesare per l'inverso della volatilita' riduce i crolli e migliora lo Sharpe.",
        params=dict(coins=["BTC", "ETH", "SOL", "XRP", "DOGE", "LTC", "LINK", "AVAX", "BCH"], lookbacks=[24, 72, 168], target_vol=0.40, vol_hours=168,
                    max_coin=0.25, band=0.02, cost_bps=30.0)),
    "spy_intraday_momentum": dict(
        nome="Momentum dell'ultima mezz'ora (S&P 500)", autore="senior_trend",
        fonte="Gao, Han, Li & Zhou (2018, JFE) 'Market intraday momentum'",
        ipotesi="Chi ribilancia a fine giornata (fondi a leva, chi copre opzioni) e chi reagisce tardi alle notizie del mattino spinge il mercato "
                "nella stessa direzione della prima mezz'ora: il rendimento fino alle 10:00 predice quello dell'ultima mezz'ora.",
        params=dict(symbol="SPY", cost_bps=2.0, min_abs_first=0.0)),
}


def settings_key(name: str, what: str) -> str:
    return f"algo.{name}.{what}"


def enabled(name: str) -> bool:
    return float(S.get(settings_key(name, "on"), 0) or 0) >= 1


# ---------------------------------------------------------------------------------------------- dati (Alpaca, sola lettura)
def _cache(name: str) -> str:
    os.makedirs(os.path.join(paths.VAR, "data"), exist_ok=True)
    return os.path.join(paths.VAR, "data", f"alpaca_{name}.pkl")


def _pages(path: str, key: str) -> dict[str, list]:
    out: dict[str, list] = {}
    token = None
    for _ in range(200):
        d = V._data(path + (f"&page_token={urllib.parse.quote(token)}" if token else ""), timeout=30)
        for sym, bars in (d.get(key) or {}).items():
            out.setdefault(sym, []).extend(bars)
        token = d.get("next_page_token")
        if not token:
            break
    return out


def crypto_bars(coins: list[str], days: int = 730) -> pd.DataFrame:
    start = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    syms = ",".join(urllib.parse.quote(f"{c}/USD", safe="") for c in coins)
    raw = _pages(f"/v1beta3/crypto/us/bars?symbols={syms}&timeframe=1Hour&limit=10000&start={start}", "bars")
    df = pd.DataFrame({k.split("/")[0]: pd.Series({pd.Timestamp(b["t"]): float(b["c"]) for b in v}) for k, v in raw.items()}).sort_index()
    df.to_pickle(_cache("crypto_1h"))
    return df


def stock_bars(sym: str, days: int = 1100) -> pd.DataFrame:
    start = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")    # i dati gratuiti: non gli ultimi 15 minuti
    raw = {}
    for feed in ("sip", "iex"):
        try:
            raw = _pages(f"/v2/stocks/bars?symbols={sym}&timeframe=5Min&limit=10000&adjustment=all&start={start}&end={end}&feed={feed}", "bars")
            if raw.get(sym):
                break
        except Exception:
            continue
    bars = raw.get(sym, [])
    df = pd.DataFrame([dict(t=pd.Timestamp(b["t"]), o=float(b["o"]), c=float(b["c"])) for b in bars]).set_index("t").sort_index() if bars else pd.DataFrame()
    df.to_pickle(_cache(f"{sym}_5m"))
    return df


# ---------------------------------------------------------------------------------------------- backtest
def tsmom_weights(close: pd.DataFrame, p: dict) -> pd.DataFrame:
    """Peso per ora e moneta (frazione del capitale della strategia), deciso con i dati FINO a quell'ora."""
    r = close.pct_change(fill_method=None)
    sig = sum((close / close.shift(L) - 1 > 0).astype(float) for L in p["lookbacks"]) / len(p["lookbacks"])   # 0, 1/3, 2/3, 1
    vol = r.rolling(p["vol_hours"], min_periods=p["vol_hours"] // 2).std() * math.sqrt(24 * 365)
    n = max(close.shape[1], 1)
    w = (sig * (p["target_vol"] / vol) / math.sqrt(n)).clip(upper=p["max_coin"]).fillna(0.0)
    tot = w.sum(axis=1)
    return w.div(tot.where(tot > 1, 1), axis=0)                 # mai oltre il 100% del capitale della strategia (niente leva sulle crypto)


def bt_crypto_tsmom(close: pd.DataFrame, p: dict) -> pd.Series:
    """Rendimento orario netto: i pesi decisi alla chiusura di un'ora valgono per l'ora dopo; si ribilancia solo oltre la banda."""
    w = tsmom_weights(close, p)
    held = w.copy()
    prev = pd.Series(0.0, index=w.columns)
    rows = []
    for t, row in w.iterrows():                                  # banda: non si insegue il rumore (i costi lo mangerebbero)
        new = row.where((row - prev).abs() > p["band"], prev)
        rows.append(new); prev = new
    held = pd.DataFrame(rows, index=w.index)
    r = close.pct_change(fill_method=None).fillna(0.0)
    gross = (held.shift(1).fillna(0.0) * r).sum(axis=1)
    cost = held.diff().abs().sum(axis=1).fillna(0.0) * p["cost_bps"] / 1e4
    return gross - cost


def bt_spy_intraday(bars: pd.DataFrame, p: dict) -> pd.Series:
    """Per ogni giorno: segno del rendimento chiusura di ieri -> 10:00; posizione dalle 15:30 alla chiusura (ora di New York)."""
    if bars.empty:
        return pd.Series(dtype=float)
    ny = bars.tz_convert("America/New_York") if bars.index.tz is not None else bars.tz_localize("UTC").tz_convert("America/New_York")
    out = {}
    prev_close = None
    for d, g in ny.groupby(ny.index.date):
        g = g.between_time("09:30", "15:59")
        if len(g) < 60:
            prev_close = float(g["c"].iloc[-1]) if len(g) else prev_close
            continue
        p10 = g.between_time("09:55", "09:55")["c"]            # barra 9:55-10:00: chiude alle 10:00
        p1530 = g.between_time("15:25", "15:25")["c"]
        close = float(g["c"].iloc[-1])
        if prev_close and len(p10) and len(p1530):
            first = float(p10.iloc[0]) / prev_close - 1
            if abs(first) > p.get("min_abs_first", 0.0):
                out[pd.Timestamp(d)] = math.copysign(1.0, first) * (close / float(p1530.iloc[0]) - 1) - 2 * p["cost_bps"] / 1e4
            else:
                out[pd.Timestamp(d)] = 0.0
        prev_close = close
    return pd.Series(out).sort_index()


def stats(daily: pd.Series, periods: int = 252) -> dict:
    d = daily.dropna()
    if len(d) < 20:
        return dict(ok=False, motivo="storia troppo corta")
    eq = (1 + d).cumprod()
    yrs = len(d) / periods
    sd = float(d.std())
    return dict(ok=True, giorni=int(len(d)), dal=str(d.index[0])[:10], al=str(d.index[-1])[:10], sharpe=round(float(d.mean() / sd * math.sqrt(periods)), 3) if sd > 0 else None,
                rendimento_annuo=round(float(eq.iloc[-1] ** (1 / yrs) - 1), 4) if yrs > 0 else None, vol_annua=round(sd * math.sqrt(periods), 4),
                dd_max=round(float((eq / eq.cummax() - 1).min()), 4), giorni_positivi=round(float((d > 0).mean()), 3), totale=round(float(eq.iloc[-1] - 1), 4))


def to_daily(hourly: pd.Series) -> pd.Series:
    return (1 + hourly).groupby(hourly.index.floor("D")).prod() - 1


# ---------------------------------------------------------------------------------------------- dal backtest al comitato
def backtest(name: str, data=None, propose: bool = True) -> dict:
    """Backtest con i dati di Alpaca (o quelli passati), prova registrata (anche a costi doppi), proposta al comitato di accenderla."""
    from . import trials
    spec = STRATS[name]
    p = dict(spec["params"])
    if name == "crypto_tsmom":
        close = data if data is not None else crypto_bars(p["coins"])
        daily = to_daily(bt_crypto_tsmom(close, p))
        daily2 = to_daily(bt_crypto_tsmom(close, dict(p, cost_bps=p["cost_bps"] * 2)))
        bench = to_daily(close.pct_change(fill_method=None).fillna(0).mean(axis=1))     # comprare e tenere tutte le monete a pesi uguali
    else:
        bars = data if data is not None else stock_bars(p["symbol"])
        daily = bt_spy_intraday(bars, p)
        daily2 = bt_spy_intraday(bars, dict(p, cost_bps=p["cost_bps"] * 2))
        bench = None
    st, st2 = stats(daily), stats(daily2)
    if not st.get("ok"):
        return dict(ok=False, motivo=st.get("motivo"))
    tid = trials.register(spec["autore"], f"algo:{name}", name, p, spec["ipotesi"])
    d = trials.record_result(tid, daily.values, extra=dict(stats=st))
    g = trials.gate(tid, cost2x_sharpe=st2.get("sharpe"), lookahead_ok=True)
    res = dict(ok=True, strategia=name, prova=tid, risultati=st, costi_doppi=st2, deflated=dict(dsr=round(d["dsr"], 4), psr=round(d["psr"], 4), prove_totali=d["n_trials"]),
               cancello=dict(passa=bool(g.get("passa")), controlli={k: v for k, v in (g.get("controlli") or {}).items()}),
               confronto=stats(bench) if bench is not None else None, ts=db.now_iso())
    db.runtime_set(f"algo.{name}.backtest", res)
    audit.log(spec["autore"], "algo.backtest", dict(strategia=name, sharpe=st.get("sharpe"), dsr=res["deflated"]["dsr"]))
    if propose and not enabled(name):
        res["idea"] = _propose(name, res)
    return res


def _propose(name: str, res: dict) -> int | None:
    """Mette al voto l'accensione: tesi = fonte + ipotesi + numeri del backtest. Decide il comitato."""
    spec, st = STRATS[name], res["risultati"]
    if any((i.get("azione") or {}).get("chiave") == settings_key(name, "on") and i["status"] in ("al_superiore", "al_comitato")
           for i in __import__("firm.ideas", fromlist=["x"]).listing(100)):
        return None
    tesi = (f"{spec['nome']}. Fonte: {spec['fonte']}. Ipotesi: {spec['ipotesi']} Backtest dal {st['dal']} al {st['al']} ({st['giorni']} giorni), al netto dei costi: "
            f"Sharpe {st['sharpe']}, rendimento annuo {pct(st['rendimento_annuo'])}, volatilita' {pct(st['vol_annua'])}, calo massimo {pct(st['dd_max'])}; "
            f"a costi doppi Sharpe {res['costi_doppi'].get('sharpe')}. Deflated Sharpe {res['deflated']['dsr']} su {res['deflated']['prove_totali']} prove; "
            f"cancello statistico {'superato' if res['cancello']['passa'] else 'NON superato'}" +
            (f". Comprare e tenere le stesse monete: Sharpe {res['confronto'].get('sharpe')}, calo massimo {pct(res['confronto'].get('dd_max'))}" if res.get("confronto") else "") + ".")
    iid = db.ex("INSERT INTO ideas(ts,author,holder,kind,title,tesi,evidenze,azione,p_success,status,history) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (db.now_iso(), spec["autore"], "capo", "regola", f"Accendere la strategia: {spec['nome']}", tesi,
                 json.dumps([f"prova {res['prova']}", f"DSR {res['deflated']['dsr']}"], ensure_ascii=False),
                 json.dumps(dict(chiave=settings_key(name, "on"), valore=1.0, attuale=0.0)), 0.5, "al_comitato",
                 json.dumps([dict(ts=db.now_iso(), chi=spec["autore"], cosa="presentata con il backtest", p=0.5)])))
    events.publish("idea.new", spec["autore"], dict(id=iid, tipo="regola", titolo=f"Accendere {spec['nome']}", a="capo"))
    return iid


def pct(v):
    return "—" if v is None else f"{v * 100:.1f}%"


# ---------------------------------------------------------------------------------------------- dal vivo
def live_crypto(close: pd.DataFrame | None = None) -> dict:
    """Ogni ora: pesi della strategia -> obiettivi crypto (frazione del conto) che il ribilanciamento di Alpaca esegue."""
    name = "crypto_tsmom"
    if not enabled(name):
        if db.runtime_get("algo.crypto_targets"):
            db.runtime_set("algo.crypto_targets", {})                       # spenta: le sue posizioni escono al prossimo ribilanciamento
        return dict(nota="spenta")
    p = STRATS[name]["params"]
    if close is None:
        close = crypto_bars(p["coins"], days=10)
    w = tsmom_weights(close, p).iloc[-1]
    frac = float(S.get(settings_key(name, "capital_frac"), 0.3))
    tgt = {k: round(float(v) * frac, 5) for k, v in w.items() if v > 0}
    db.runtime_set("algo.crypto_targets", tgt)
    return dict(obiettivi=tgt, ora=str(close.index[-1]))


def live_spy(now: dt.datetime | None = None) -> dict:
    """Alle 15:30 di New York entra nella direzione della prima mezz'ora; alle 15:58 esce. Ordini a mercato sul conto paper di Alpaca."""
    name = "spy_intraday_momentum"
    if not enabled(name) or not V.keys_ok():
        return dict(nota="spenta")
    now = now or dt.datetime.now(dt.timezone.utc)
    ny = now.astimezone(__import__("zoneinfo").ZoneInfo("America/New_York"))
    if ny.weekday() >= 5:
        return dict(nota="weekend")
    st = db.runtime_get("algo.spy.state") or {}
    today = ny.date().isoformat()
    sym = STRATS[name]["params"]["symbol"]
    from . import blotter
    if ny.strftime("%H:%M") >= "15:30" and ny.strftime("%H:%M") < "15:55" and st.get("day") != today:
        bars = stock_bars(sym, days=5)
        nyb = bars.tz_convert("America/New_York")
        g = nyb[nyb.index.date == ny.date()]
        prev = nyb[nyb.index.date < ny.date()]
        if g.empty or prev.empty:
            return dict(nota="dati di oggi non disponibili")
        p10 = g.between_time("09:55", "09:55")["c"]
        if not len(p10):
            return dict(nota="manca la barra delle 10:00")
        first = float(p10.iloc[0]) / float(prev.between_time("09:30", "15:59")["c"].iloc[-1]) - 1
        side = "buy" if first > 0 else "sell"
        usd = float(V.account()["equity"]) * float(S.get(settings_key(name, "capital_frac"), 0.3))
        o = V._req("POST", "/v2/orders", dict(symbol=sym, side=side, type="market", time_in_force="day", notional=f"{usd:.2f}") if side == "buy"
                   else dict(symbol=sym, side=side, type="market", time_in_force="day", qty=str(int(usd / max(float(g["c"].iloc[-1]), 1)))))
        blotter.record_alpaca_order(str(o.get("id", "")), sym, side, usd, dict(kind="algo", strategia=name, agent=STRATS[name]["autore"]), STRATS[name]["autore"])
        db.runtime_set("algo.spy.state", dict(day=today, side=side, first=round(first, 5), open=True))
        return dict(entrato=side, prima_mezzora=first)
    if ny.strftime("%H:%M") >= "15:58" and st.get("day") == today and st.get("open"):
        try:
            V._req("DELETE", f"/v2/positions/{sym}")
        except Exception as e:
            return dict(nota=f"chiusura non riuscita: {str(e)[:80]}")
        db.runtime_set("algo.spy.state", dict(st, open=False))
        return dict(uscito=True)
    return dict(nota="niente da fare adesso")


def overview() -> dict:
    return {n: dict(nome=s["nome"], fonte=s["fonte"], ipotesi=s["ipotesi"], accesa=enabled(n), capitale=float(S.get(settings_key(n, "capital_frac"), 0.3)),
                    backtest=db.runtime_get(f"algo.{n}.backtest")) for n, s in STRATS.items()}
