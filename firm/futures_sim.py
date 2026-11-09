"""
Banco futures simulato: la leva sui segnali, scelta dagli agenti.

Le crypto vere si eseguono su Alpaca, che non ha leva, ne' short, ne' tutte le monete. Molti segnali pero' sono futures (margine isolato, leva 3x-10x,
long e short). Per misurare COSA SUCCEDE con la leva, ogni segnale analizzato apre anche una posizione in un conto virtuale a margine:

  * l'agente sceglie la LEVA (da 1 fino alla massima che il segnale propone, o il tetto delle impostazioni) e il MARGINE (% del conto virtuale):
    nessun obbligo di usare il massimo, la scelta e' sua e va motivata; il codice mette solo i tetti fisici;
  * posizione = margine x leva; la perdita non supera mai il margine; liquidazione a circa 1/leva dall'ingresso (meno il margine di mantenimento);
  * stop, obiettivo e liquidazione si controllano sulle candele da 15 minuti (massimi e minimi); se in una candela se ne toccano due, vale il peggiore;
  * costi: commissione (taker) all'ingresso e all'uscita; il finanziamento (funding) non e' simulato.
  * i risultati per fascia di leva tornano agli agenti nei dati della scelta successiva: cosi' studiano, non vengono obbligati.

Non esegue nulla: e' un registro che misura. Nessun denaro, nemmeno quello paper di Alpaca o di IBKR.
"""
from __future__ import annotations

import datetime as dt

from . import db, events
from . import settings as S

BUCKETS = [(1, 3), (4, 6), (7, 10), (11, 25)]

PRINCIPI = (
    "Rendimento sul margine = leva x rendimento del sottostante; la perdita massima e' il margine (liquidazione). "
    "Liquidazione a ~1/leva dall'ingresso (meno lo 0,5% di mantenimento): se lo stop e' piu' lontano della liquidazione, la liquidazione arriva PRIMA dello stop. "
    "Criterio di Kelly: la frazione ottima del conto da rischiare e' f* = p - (1-p)/R (p = probabilita' di arrivare all'obiettivo, R = rendimento/rischio); "
    "rischiare piu' di 2 x f* fa DIMINUIRE la crescita attesa. "
    "Trascinamento da volatilita': la crescita di lungo periodo e' ~ mu - sigma^2/2; la leva moltiplica mu ma moltiplica sigma^2 al quadrato, quindi la crescita ha un massimo e poi cala. "
    "Una probabilita' p non calibrata e' il vero pericolo della leva alta: l'errore sulla probabilita' si moltiplica."
)


def _ensure() -> None:
    db.ex("""CREATE TABLE IF NOT EXISTS fut_positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, signal_id INTEGER, ts TEXT, coin TEXT, side TEXT, entry REAL, stop REAL, tp REAL, lev REAL,
        margin_usd REAL, notional_usd REAL, liq REAL, stato TEXT, exit_price REAL, esito TEXT, pnl_usd REAL, pnl_margin REAL, chiuso_ts TEXT,
        agent TEXT, motivo TEXT)""")


def enabled() -> bool:
    return bool(S.get("futures.enabled", True))


def equity0() -> float:
    return float(S.get("futures.equity0_usd", 100000))


def realized() -> float:
    _ensure()
    return float(db.one("SELECT COALESCE(SUM(pnl_usd),0) s FROM fut_positions WHERE stato='chiusa'")["s"])


def margin_used() -> float:
    _ensure()
    return float(db.one("SELECT COALESCE(SUM(margin_usd),0) s FROM fut_positions WHERE stato='aperta'")["s"])


def equity() -> float:
    return equity0() + realized()


def liq_price(entry: float, side: str, lev: float) -> float:
    m = float(S.get("futures.maint_margin", 0.005))
    return entry * (1 - 1 / lev + m) if side == "long" else entry * (1 + 1 / lev - m)


def lev_cap(p: dict) -> float:
    """La leva massima per questo segnale: quella che il segnale propone, o il tetto delle impostazioni; mai oltre il tetto fisico."""
    hard = float(S.get("signals.leverage_hard_cap", 25))
    proposed = p.get("leva_max") or float(S.get("signals.leverage_cap", 10))
    return max(1.0, min(float(proposed), hard))


def stats_by_leverage() -> list[dict]:
    _ensure()
    rows = db.q("SELECT lev, esito, pnl_margin, pnl_usd FROM fut_positions WHERE stato='chiusa'")
    out = []
    for lo, hi in BUCKETS:
        r = [x for x in rows if lo <= round(x["lev"]) <= hi]
        n = len(r)
        out.append(dict(fascia=f"{lo}-{hi}x", n=n, vincenti=sum(1 for x in r if x["pnl_usd"] > 0), liquidazioni=sum(1 for x in r if x["esito"] == "liquidazione"),
                        medio_su_margine=round(sum(x["pnl_margin"] for x in r) / n, 3) if n else None, pnl_usd=round(sum(x["pnl_usd"] for x in r), 2)))
    return out


def study(p: dict, ctl: dict) -> dict:
    """Quello che l'agente deve avere davanti per scegliere la leva: la geometria della liquidazione per questo segnale, i principi e lo storico per fascia."""
    cap = lev_cap(p)
    e, sl = p.get("ingresso"), p.get("stop")
    sd = abs(e - sl) / e if e and sl else None
    sigma = ctl.get("sigma_giornaliera")
    table = []
    for L in [1, 2, 3, 5, 8, 10, 15, 20, 25]:
        if L > cap:
            continue
        liq = 1 / L - float(S.get("futures.maint_margin", 0.005))
        table.append(dict(leva=L, distanza_liquidazione=round(liq, 4), stop_prima_della_liquidazione=bool(sd is not None and sd < liq),
                          perdita_allo_stop_su_margine=round(L * sd, 3) if sd else None,
                          guadagno_all_obiettivo_su_margine=round(L * abs(p["obiettivi"][0] - e) / e, 3) if p.get("obiettivi") and e else None))
    free = max(equity() * float(S.get("futures.margin_total_max_pct", 80)) / 100 - margin_used(), 0.0)
    return dict(leva_massima_ammessa=cap, il_segnale_propone=dict(minima=p.get("leva_min"), massima=p.get("leva_max")),
                distanza_stop=round(sd, 4) if sd else None, sigma_giornaliera=sigma, tabella_per_leva=table,
                conto_virtuale=dict(equity_usd=round(equity(), 2), margine_libero_usd=round(free, 2), margine_massimo_per_segnale_pct=float(S.get("futures.margin_per_signal_max_pct", 20))),
                esiti_passati_per_fascia_di_leva=stats_by_leverage(), principi=PRINCIPI,
                nota="Scegli TU leva e margine: non sei obbligato a usare il massimo che il segnale propone. Spiega la scelta. La perdita non supera mai il margine.")


def open_position(sid: int, p: dict, analysis: dict, agent: str = "senior_crypto") -> dict | None:
    """Apre la posizione virtuale con la leva e il margine scelti dall'agente (stretti ai tetti fisici). None se non si apre."""
    if not enabled() or not p.get("ok"):
        return None
    _ensure()
    if db.one("SELECT id FROM fut_positions WHERE signal_id=?", (sid,)):
        return None
    lev = max(1.0, min(float(analysis.get("leva") or 1.0), lev_cap(p)))
    eq = equity()
    per_sig = eq * float(S.get("futures.margin_per_signal_max_pct", 20)) / 100
    free = eq * float(S.get("futures.margin_total_max_pct", 80)) / 100 - margin_used()
    want = float(analysis.get("margine_pct", analysis.get("peso_pct", 2.0)) or 0) / 100 * eq
    margin = min(want, per_sig, free)
    if margin < eq * 0.001:
        return None
    side = "short" if p.get("direzione") == "short" else "long"
    e = float(p["ingresso"])
    pos = dict(signal_id=sid, ts=db.now_iso(), coin=p["moneta"], side=side, entry=e, stop=float(p["stop"]), tp=float(p["obiettivi"][0]), lev=lev,
               margin_usd=round(margin, 2), notional_usd=round(margin * lev, 2), liq=liq_price(e, side, lev), stato="aperta", agent=agent,
               motivo=str(analysis.get("motivo_leva") or "")[:300])
    db.ex("INSERT INTO fut_positions(signal_id,ts,coin,side,entry,stop,tp,lev,margin_usd,notional_usd,liq,stato,agent,motivo) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
          tuple(pos[k] for k in ("signal_id", "ts", "coin", "side", "entry", "stop", "tp", "lev", "margin_usd", "notional_usd", "liq", "stato", "agent", "motivo")))
    events.publish("futures.opened", agent, dict(signal=sid, moneta=pos["coin"], lato=side, leva=lev, margine=pos["margin_usd"]))
    return pos


def _close(row: dict, exit_px: float, esito: str, when: str) -> None:
    fee = float(S.get("futures.taker_fee", 0.0005)) * row["notional_usd"] * 2
    if esito == "liquidazione":
        pnl = -row["margin_usd"]
    else:
        move = (exit_px / row["entry"] - 1) * (1 if row["side"] == "long" else -1)
        pnl = max(move * row["notional_usd"] - fee, -row["margin_usd"])
    db.ex("UPDATE fut_positions SET stato='chiusa', exit_price=?, esito=?, pnl_usd=?, pnl_margin=?, chiuso_ts=? WHERE id=?",
          (exit_px, esito, round(pnl, 2), round(pnl / row["margin_usd"], 4), when, row["id"]))
    events.publish("futures.closed", row["agent"] or "senior_crypto", dict(signal=row["signal_id"], moneta=row["coin"], esito=esito, pnl=round(pnl, 2), leva=row["lev"]))


def first_event(rows: list, side: str, stop: float, tp: float, liq: float) -> tuple[str, float, int] | None:
    """Il primo evento sulle candele (massimi e minimi): liquidazione, stop o obiettivo. Se in una candela se ne toccano due, il peggiore."""
    long_ = side == "long"
    down_level = max(liq, stop) if long_ else min(liq, stop)                      # il livello avverso piu' vicino all'ingresso
    for k in rows:
        hi, lo = float(k[2]), float(k[3])
        adverse = lo <= down_level if long_ else hi >= down_level
        good = hi >= tp if long_ else lo <= tp
        if adverse:
            is_liq = (liq >= stop) if long_ else (liq <= stop)
            return ("liquidazione", liq, int(k[0])) if is_liq else ("stop", stop, int(k[0]))
        if good:
            return "obiettivo", tp, int(k[0])
    return None


def track() -> int:
    """Chiude le posizioni virtuali che hanno toccato liquidazione, stop, obiettivo o sono scadute. Ritorna quante."""
    if not enabled():
        return 0
    from . import signals
    _ensure()
    n = 0
    ttl = int(S.get("signals.ttl_days", 7))
    for r in db.q("SELECT * FROM fut_positions WHERE stato='aperta'"):
        rows = signals._candles(r["coin"], r["ts"])
        if not rows:
            continue
        ev = first_event(rows, r["side"], r["stop"], r["tp"], r["liq"])
        if ev:
            _close(r, ev[1], ev[0], dt.datetime.fromtimestamp(ev[2] / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
            n += 1
        elif dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(r["ts"].replace("Z", "+00:00")) > dt.timedelta(days=ttl):
            _close(r, float(rows[-1][4]), "scaduto", db.now_iso())
            n += 1
    return n


def overview() -> dict:
    """Per il portale: conto virtuale, posizioni aperte con il risultato di adesso, chiuse, e i risultati per fascia di leva."""
    from . import signals
    _ensure()
    open_rows = db.q("SELECT * FROM fut_positions WHERE stato='aperta' ORDER BY id DESC")
    unreal = 0.0
    for r in open_rows:
        px = signals.live_price(r["coin"])
        if px:
            move = (px / r["entry"] - 1) * (1 if r["side"] == "long" else -1)
            r["ora"] = dict(prezzo=px, pnl_usd=round(max(move * r["notional_usd"], -r["margin_usd"]), 2), pnl_margine=round(max(move * r["lev"], -1.0), 4))
            unreal += r["ora"]["pnl_usd"]
    closed = db.q("SELECT * FROM fut_positions WHERE stato='chiusa' ORDER BY id DESC LIMIT 40")
    allc = db.one("SELECT COUNT(*) n, COALESCE(SUM(CASE WHEN pnl_usd>0 THEN 1 ELSE 0 END),0) w, COALESCE(SUM(CASE WHEN esito='liquidazione' THEN 1 ELSE 0 END),0) l FROM fut_positions WHERE stato='chiusa'")
    eq = equity()
    return dict(attivo=enabled(), equity_usd=round(eq, 2), equity0_usd=equity0(), pnl_chiuso_usd=round(realized(), 2), pnl_aperto_usd=round(unreal, 2),
                margine_usato_usd=round(margin_used(), 2), margine_usato_pct=round(margin_used() / eq, 4) if eq else None,
                chiuse=allc["n"], vincenti=allc["w"], liquidazioni=allc["l"], per_leva=stats_by_leverage(), aperte=open_rows, ultime_chiuse=closed)
