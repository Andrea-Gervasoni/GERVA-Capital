"""
Ricerca v5: tutti i backtest del documento di rifondazione, riproducibili con un comando.

    python -m gerva.research.run            # usa data_cache/ se c'e', altrimenti scarica
    python -m gerva.research.run --refresh  # riscarica tutto

Scrive in research/v5/:
    RESULTS.md      tabelle (ogni numero e' SIMULATO su dati storici, al netto dei costi dichiarati)
    results.json    gli stessi numeri in forma leggibile da un programma
    series.parquet  rendimenti giornalieri delle strategie scelte e del portafoglio

Regole del laboratorio:
  * periodo di SCELTA fino al 31/12/2022; dal 1/1/2023 e' il periodo di VERIFICA (mai usato per scegliere);
  * ogni configurazione provata finisce nel registro delle prove: il Deflated Sharpe del portafoglio finale
    e' calcolato contro TUTTE le prove, non solo contro quelle riuscite;
  * lo Sharpe e' sempre sul rendimento in ECCESSO del tasso a breve (la cassa non e' alpha).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import warnings

import numpy as np
import pandas as pd
from scipy import stats as sps

from .. import indicators as ind
from ..backtest import Costs, run, scale_returns
from ..data import (Store, binance_funding, binance_klines, gex_squeezemetrics, hf_stock_minutes, histdata_m1,
                    yahoo, yahoo_panel)
from ..portfolio import combine, risk_parity, vol_target_leverage
from ..strategies import book
from ..strategies import daily as SD
from ..strategies import intraday as SI
from ..validation import metrics as M
from ..validation import montecarlo as MC

warnings.filterwarnings("ignore")
SPLIT = "2023-01-01"
ETF = ("SPY QQQ IWM EFA EEM VGK EWJ TLT IEF SHY BIL LQD HYG TIP GLD SLV DBC USO VNQ UUP FXE FXY "
       "SVXY ^VIX ^VIX3M ^IRX ^PUT").split()
TREND_U = "SPY QQQ IWM EFA EEM TLT IEF LQD HYG GLD SLV DBC USO VNQ UUP FXE FXY".split()
COINS = ("BTC ETH BNB XRP BCH LTC EOS XLM ADA TRX XMR DASH NEO ETC IOTA ZEC XTZ LINK ATOM ONT VET DOGE BAT QTUM OMG "
         "ALGO MATIC DOT UNI SOL AVAX LUNA FTT FIL AAVE SUSHI THETA ICP SHIB NEAR FTM SAND MANA AXS APE GMT APT OP ARB "
         "SUI PEPE TON WIF SEI INJ TIA RUNE HBAR").split()
PERPS = "BTC ETH SOL BNB XRP DOGE ADA LTC LINK AVAX".split()
# Prove fatte a mano durante l'esplorazione e non riprodotte qui (contano lo stesso nel test di fortuna):
# IBS con filtro a 200 giorni x2, IBS su 6 e 15 indici, turn-of-month, trend sui 10 maggiori dinamico, trend su perpetual
# long/short e solo long, VWAP con fascia 0,1% e 0,3%, VWAP solo long x3 monete, zona di rumore tenuta fino a chiusura x4 costi,
# ultima mezz'ora con GEX<0 e rango<0,35 x2 costi, momentum 3 su 10, PUT index, GEX "solo se basso", volatilita' con previsione GEX,
# trend BTC+ETH giornaliero x4, carry per moneta x6, zona di rumore oraria con VWAP x2.
EXTRA_TRIALS = 45
COLS = ("anni", "cagr", "vol", "sharpe", "max_dd", "mese_medio", "mese_peggiore", "mesi_ge_20")


class Lab:
    def __init__(self, root: str, refresh: bool = False):
        self.st = Store(os.path.join(root, "data_cache"))
        self.refresh = refresh
        self.trials: dict[str, float] = {}          # nome -> Sharpe annuo nel periodo di scelta
        self.tables: list[tuple[str, str]] = []     # (titolo, markdown)
        self.notes: list[str] = []
        self.json: dict = {}
        self.series: dict[str, pd.Series] = {}

    # ---- dati -------------------------------------------------------------
    def get(self, key, fn, src):
        return self.st.cached(key, fn, src, self.refresh)

    def load_daily(self):
        P = yahoo_panel(ETF, self.st, self.refresh)
        keep = P["adj"]["SPY"].notna()
        self.P = {k: v[keep] for k, v in P.items()}
        self.adj = self.P["adj"]
        self.ret = self.adj.pct_change(fill_method=None)
        self.rf = (self.adj["^IRX"] / 100 / 252).ffill()

    def load_crypto(self):
        cl, qv = {}, {}
        for c in COINS:
            try:
                d = self.get(f"bn_spot_1d_{c}USDT", lambda c=c: binance_klines(c + "USDT", "1d", "spot"), "binance.vision")
            except Exception:
                continue
            cl[c], qv[c] = d["close"], d["quote_volume"]
        close = pd.DataFrame(cl)
        idx = pd.date_range(close.index[0], close.index[-1], freq="D")
        self.cclose, self.cdvol = close.reindex(idx), pd.DataFrame(qv).reindex(idx)
        r = self.cclose.pct_change(fill_method=None)
        self.cret = r.mask(self.cclose.notna() & self.cclose.shift(1).isna())      # nessun rendimento attraverso un buco
        self.rf365 = (self.adj["^IRX"] / 100 / 365).reindex(idx).ffill()

    # ---- registro e tabelle ----------------------------------------------
    def reg(self, name: str, r: pd.Series, rf, periods: int):
        s = M.summary(r.loc[:SPLIT], rf, periods)
        if s:
            self.trials[name] = s["sharpe"]

    def three(self, rows: dict, name: str, r: pd.Series, rf, periods: int, extra: dict | None = None):
        r = r.dropna()
        rows[name] = dict(M.summary(r, rf, periods), **(extra or {}))
        rows[name + " · scelta"] = M.summary(r.loc[:SPLIT], rf, periods)
        rows[name + " · verifica"] = M.summary(r.loc[SPLIT:], rf, periods)
        self.reg(name, r, rf, periods)

    def table(self, title: str, rows: dict, cols=COLS, note: str = ""):
        self.tables.append((title, M.fmt_table(rows, cols) + (f"\n\n{note}" if note else "")))
        self.json[title] = {k: {c: (None if isinstance(v.get(c), float) and not math.isfinite(v.get(c)) else v.get(c))
                                for c in v} for k, v in rows.items()}


# ---------------------------------------------------------------------------
def lab_benchmarks(L: Lab):
    rows = {}
    for s in ("SPY", "QQQ", "TLT", "GLD"):
        rows[f"{s} comprato e tenuto"] = M.summary(L.ret[s].dropna(), L.rf)
    rows["60% SPY / 40% IEF"] = M.summary((0.6 * L.ret["SPY"] + 0.4 * L.ret["IEF"]).dropna(), L.rf)
    L.table("0. Riferimenti (nessuna strategia)", rows)


def lab_trend(L: Lab):
    c = L.adj[TREND_U].loc["2003":]
    R = c.pct_change(fill_method=None)
    rows = {}
    for name, lbs, lo, every, cap in [
        ("trend giornaliero long/short, vol 10%", (21, 63, 126, 252), False, 1, 3.0),
        ("trend lento long/short settimanale, vol 10%", (63, 126, 252), False, 5, 3.0),
        ("trend lento solo long settimanale, vol 10%", (63, 126, 252), True, 5, 3.0),
        ("trend lento solo long mensile, vol 10%", (126, 252), True, "M", 3.0),
    ]:
        W = SD.hold(SD.vol_target(SD.trend(c, lookbacks=lbs, long_only=lo), R, 0.10, max_leverage=cap), every)
        res = run(W, R, L.rf, Costs(trade=0.0010, cash_haircut=1.0 if cap == 1.0 else 0.005), band=0.0 if every == 1 else 0.02)
        r = res.ret.loc["2005":]
        L.three(rows, name, r, L.rf, 252, dict(turnover=res.turnover.loc["2005":].mean() * 252,
                                               lorda=res.gross.loc["2005":].mean()))
    res = book.ma_trend_returns(L.adj, L.rf)
    L.series["MA-TREND"] = r = res.ret.loc["2005":]
    L.three(rows, "MA-TREND: trend lento solo long settimanale, senza leva", r, L.rf, 252,
            dict(turnover=res.turnover.loc["2005":].mean() * 252, lorda=res.gross.loc["2005":].mean()))
    L.table("1. Trend following su 17 ETF (costo 10 punti base per lato)", rows, COLS + ("turnover", "lorda"),
            "Il trend giornaliero ha un turnover di oltre 100 volte l'anno: con i costi di un conto piccolo perde. "
            "Rallentare il segnale e ribilanciare ogni settimana salva la strategia, ma lo Sharpe netto resta tra 0,2 e 0,4.")


def _cfd(L: Lab, sym: str, w: pd.Series, trade: float = 0.0005, spread: float = 0.015) -> pd.Series:
    """Long via CFD o margine: ogni notte in posizione costa (tasso + spread) sul controvalore; la cassa non rende."""
    held = w.shift(1).fillna(0.0)
    return held * (L.ret[sym] - (L.rf + spread / 252)) - w.diff().abs().fillna(0.0) * trade


def lab_equity(L: Lab):
    H, Lo, C = L.P["high"], L.P["low"], L.P["close"]
    rows = {}
    legs = {}
    for s in ("SPY", "QQQ"):
        w = SD.ibs_reversion(H[s], Lo[s], C[s], trend_ma=None)
        legs[s] = _cfd(L, s, w)
        L.three(rows, f"IBS {s} (eseguito in chiusura)", legs[s].loc["2000":], L.rf, 252, dict(in_posizione=float(w.mean())))
        late = w.shift(1).fillna(0.0)                                  # un giorno di ritardo nell'esecuzione
        r2 = _cfd(L, s, late)
        rows[f"IBS {s} (eseguito il giorno dopo)"] = M.summary(r2.loc["2000":], L.rf)
        L.reg(f"IBS {s} ritardato", r2.loc["2000":], L.rf, 252)
    eq = book.eq_mr_returns(H, Lo, C, L.ret, L.rf).loc["2000":]
    L.three(rows, "EQ-MR: IBS su SPY e QQQ, meta' ciascuno", eq, L.rf, 252)
    L.series["EQ-MR"] = eq
    for s, lev in (("SPY", 1.0), ("SPY", 2.0), ("QQQ", 2.0)):
        w = SD.ma_regime(L.adj[s], 200, lev, 0.0)
        res = run(pd.DataFrame({s: w}), L.ret[[s]], L.rf, Costs(trade=0.0005))
        L.three(rows, f"media a 200 giorni, {lev:.0f}x {s}", res.ret.loc[w[w != 0].index.min():], L.rf, 252)
    w = SD.hold(pd.DataFrame({"SPY": SD.vol_managed(L.ret["SPY"], 0.15)}), 5)
    L.three(rows, "SPY a volatilita' gestita 15%", run(w, L.ret[["SPY"]], L.rf, Costs(trade=0.0005)).ret.loc["1994":], L.rf, 252)
    m12 = L.adj[["SPY", "EFA", "IEF"]].pct_change(252)
    bil = (1 + L.rf).rolling(252).apply(np.prod, raw=True) - 1
    W = pd.DataFrame(0.0, index=L.adj.index, columns=["SPY", "EFA", "IEF"])
    W["SPY"] = ((m12["SPY"] > bil) & (m12["SPY"] >= m12["EFA"])).astype(float)
    W["EFA"] = ((m12["EFA"] > bil) & (m12["EFA"] > m12["SPY"])).astype(float)
    W["IEF"] = 1 - W["SPY"] - W["EFA"]
    res = run(SD.hold(W.where(m12["SPY"].notna(), 0.0), "M"), L.ret[["SPY", "EFA", "IEF"]], L.rf, Costs(trade=0.0010, cash_haircut=1.0))
    L.three(rows, "dual momentum mensile (SPY, EFA, IEF)", res.ret.loc["2006":], L.rf, 252)
    L.table("2. Azioni: ritorno alla media, regimi, leva a regime (5 punti base per lato)", rows, COLS + ("in_posizione",),
            "IBS vive solo se si esegue SULLA chiusura che genera il segnale: con un giorno di ritardo perde meta' dello Sharpe.")
    # premio per il rischio di volatilita'
    rows = {}
    rows["SVXY comprato e tenuto"] = M.summary(L.ret["SVXY"].dropna(), L.rf)
    w = SD.vix_term_structure(L.adj["^VIX"], L.adj["^VIX3M"], 0.95)
    for wt in (1.0, 0.5):
        res = run(pd.DataFrame({"SVXY": w * wt}), L.ret[["SVXY"]], L.rf, Costs(trade=0.0005))
        L.three(rows, f"SVXY solo con VIX/VIX3M < 0,95, peso {wt:.0%}", res.ret.loc["2011-10-05":], L.rf, 252)
    L.table("3. Vendere volatilita' (SVXY)", rows, COLS + ("giorno_peggiore",),
            "Il 5/2/2018 SVXY ha perso l'83% in un giorno. Il filtro lo ha evitato solo perche' il rapporto era 0,98 "
            "il venerdi' prima: con una soglia a 1,00 lo avrebbe preso in pieno. Scartata: rischio di coda non controllabile, "
            "e SVXY non e' acquistabile da un cliente al dettaglio UE (manca il KID).")


def lab_gex(L: Lab):
    g = L.get("gex", gex_squeezemetrics, "squeezemetrics")
    L.gexf = f = ind.gex_features(g["gex"])
    r = g["price"].pct_change()
    d = pd.DataFrame(dict(rank=f["rank"], neg=f["neg"], nxt=r.shift(-1))).dropna()
    d["abs"] = d["nxt"].abs()
    d["q"] = pd.cut(d["rank"], [0, .2, .4, .6, .8, 1.0], labels=["Q1 (GEX basso)", "Q2", "Q3", "Q4", "Q5 (GEX alto)"],
                    include_lowest=True)
    t = d.groupby("q", observed=True).agg(n=("nxt", "size"), media_pb=("nxt", lambda x: x.mean() * 1e4),
                                          t=("nxt", lambda x: x.mean() / x.std() * math.sqrt(len(x))),
                                          vol_annua=("nxt", lambda x: x.std() * math.sqrt(252)), peggiore=("nxt", "min"))
    sp_abs = sps.spearmanr(d["rank"], d["abs"])
    sp_dir = sps.spearmanr(d["rank"], d["nxt"])
    vix = L.adj["^VIX"].reindex(d.index).ffill()
    y = d["abs"].to_numpy() * 100
    X1 = np.column_stack([np.ones(len(d)), vix.to_numpy()])
    X2 = np.column_stack([X1, d["rank"].to_numpy()])
    r2 = lambda X: 1 - ((y - X @ np.linalg.lstsq(X, y, rcond=None)[0]) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    md = "| quintile del GEX (rango a 252 giorni) | giorni | rendimento medio del giorno dopo (pb) | t | volatilita' annua del giorno dopo | giorno peggiore |\n|---|---:|---:|---:|---:|---:|\n"
    for k, row in t.iterrows():
        md += f"| {k} | {int(row.n)} | {row.media_pb:.1f} | {row.t:.2f} | {row.vol_annua:.1%} | {row.peggiore:.1%} |\n"
    md += (f"\nGiorni: {len(d)} ({d.index[0].date()} -> {d.index[-1].date()}); giorni con GEX negativo: {int(d.neg.sum())} ({d.neg.mean():.1%}). "
           f"Correlazione di rango GEX vs |rendimento del giorno dopo|: {sp_abs.statistic:.2f} (p = {sp_abs.pvalue:.0e}); "
           f"vs rendimento con segno: {sp_dir.statistic:.3f} (p = {sp_dir.pvalue:.4f}). "
           f"R² della regressione di |rendimento| sul solo VIX: {r2(X1):.3f}; aggiungendo il GEX: {r2(X2):.3f}.")
    L.tables.append(("4a. Che cosa predice il GEX (S&P 500, dati SqueezeMetrics)", md))
    L.json["gex_quintili"] = json.loads(t.reset_index().astype({"q": str}).to_json(orient="records"))
    rank = f["rank"].reindex(L.adj.index)
    neg = f["neg"].reindex(L.adj.index)
    rows = {}

    def one(name, w):
        res = run(pd.DataFrame({"SPY": w.reindex(L.adj.index).fillna(0)}), L.ret[["SPY"]], L.rf, Costs(trade=0.0005))
        L.three(rows, name, res.ret.loc["2011-11":], L.rf, 252)
    one("SPY comprato e tenuto (stesso periodo)", pd.Series(1.0, index=L.adj.index))
    one("regola diffusa: 1,5x se GEX nel 75% alto, cassa altrimenti", SD.gex_exposure(rank, 0.0, 1.5, 0.25))
    one("regola diffusa: long solo con GEX positivo", pd.Series(np.where(neg == 1, 0.0, 1.0), index=L.adj.index).where(rank.notna(), 0))
    one("contraria: 1,5x con GEX nel 25% basso, 1x altrimenti", SD.gex_exposure(rank, 1.5, 1.0, 0.25))
    one("volatilita' obiettivo 12% con la volatilita' realizzata", SD.vol_managed(L.ret["SPY"], 0.12, span=20))
    one("volatilita' obiettivo 12% con il VIX", (0.12 / (L.adj["^VIX"] / 100 * 0.8)).clip(upper=2.0).where(rank.notna(), 0))
    L.table("4b. Regole di esposizione basate sul GEX, su SPY", rows, COLS,
            "Nessuna regola GEX batte lo Sharpe del semplice comprare e tenere. Il GEX e' un previsore di volatilita' "
            "equivalente al VIX, non un segnale di direzione.")


def lab_intraday(L: Lab):
    rows = {}

    def add(name, d, periods=252, reg=True):
        rows[name] = dict(M.summary(d["ret"], 0.0, periods), operazioni_giorno=float(d["trades"].mean()),
                          lordo_pb_giorno=float(d["gross_ret"].mean() * 1e4), costo_pb_giorno=float(d["cost"].mean() * 1e4))
        if reg:
            L.reg(name, d["ret"], 0.0, periods)
    try:
        m1 = L.get("spx_m1", lambda: histdata_m1("SPXUSD"), "histdata.com via github")
    except Exception as e:
        L.notes.append(f"S&P 500 a 1 minuto non disponibile: {e}")
        m1 = None
    if m1 is not None:
        b30 = SI.resample_session(m1, 30)
        b30 = b30[b30.groupby(b30.index.normalize())["close"].transform("size") >= 12]
        dclose = b30["close"].groupby(b30.index.normalize()).last()
        pos = SI.noise_breakout(b30, 14)
        for cost in (0.0, 0.00003, 0.00005, 0.0001, 0.0002):
            add(f"S&P 500 2010-18: fuori dalla zona di rumore, stop sulla banda, costo {cost * 1e4:.1f} pb", SI.simulate(b30, pos, cost))
        lev = SI.daily_vol_leverage(dclose, 0.02, 14, 4.0)
        add("S&P 500 2010-18: idem con leva a volatilita' (max 4x), costo 0,5 pb", SI.simulate(b30, pos, 0.00005, leverage=lev))
        f = L.gexf
        rank_prev, dayidx = f["rank"].shift(1), pd.Series(b30.index.normalize(), index=b30.index)
        lh = SI.last_half_hour(b30, dclose.shift(1))
        for nm, mask in (("tutti i giorni", rank_prev.notna()), ("solo se il GEX di ieri era nel 20% basso", rank_prev < 0.2)):
            mk = pd.Series(mask.reindex(dayidx.to_numpy()).fillna(False).to_numpy(), index=b30.index)
            for cost in (0.00005, 0.0001):
                add(f"S&P 500 2011-18: momentum dell'ultima mezz'ora, {nm}, costo {cost * 1e4:.1f} pb",
                    SI.simulate(b30, lh.where(mk, 0.0), cost).loc["2011-11":])
        # fuori campione: barre orarie 2023-12 -> oggi
        oos = {}
        for s in ("SPY", "QQQ", "IWM"):
            h = L.get(f"yahoo_1h_{s}", lambda s=s: yahoo(s, "1h", "730d"), "yahoo")
            h = h[h.index.minute == 30]
            h = h[h.index.normalize() < h.index.normalize().max()]
            add(f"{s} orario 2023-26 (verifica): zona di rumore, costo 0,5 pb", SI.simulate(h, SI.noise_breakout(h, 14), 0.00005), reg=False)
            last = h[h.index.hour == 15]
            last = last[~last.index.normalize().duplicated()]
            dc = h["close"].groupby(h.index.normalize()).last()
            prev = dc.shift(1).reindex(last.index.normalize()).to_numpy()
            x = pd.DataFrame(dict(sig=np.sign(last["open"].to_numpy() / prev - 1),
                                  r=last["close"].to_numpy() / last["open"].to_numpy() - 1), index=last.index.normalize()).dropna()
            x["rk"] = rank_prev.reindex(x.index)
            for nm, mk in (("tutti i giorni", x.rk.notna()), ("GEX di ieri nel 20% basso", x.rk < 0.2)):
                y = (x.sig * x.r)[mk]
                oos[f"{s}, {nm}"] = dict(n=int(len(y)), lordo_pb=float(y.mean() * 1e4), t=float(y.mean() / y.std() * math.sqrt(len(y))))
        md = "| ultima mezz'ora, 2023-12 -> 2026-11 (lordo, senza costi) | giorni | rendimento medio (pb) | t |\n|---|---:|---:|---:|\n"
        md += "".join(f"| {k} | {v['n']} | {v['lordo_pb']:.2f} | {v['t']:.2f} |\n" for k, v in oos.items())
        L.json["ultima_mezzora_verifica"] = oos
    cols = ("anni", "cagr", "vol", "sharpe", "max_dd", "operazioni_giorno", "lordo_pb_giorno", "costo_pb_giorno")
    L.table("5a. Intraday sull'indice: zona di rumore e ultima mezz'ora", rows, cols,
            "pb = punti base (0,01%). La regola della zona di rumore guadagna 1,2 pb lordi al giorno: basta un costo di 0,6 pb "
            "per lato per azzerarla. L'ultima mezz'ora condizionata al GEX aveva Sharpe 1,4 nel 2011-2018.")
    if m1 is not None:
        L.tables.append(("5b. La stessa regola dell'ultima mezz'ora nel periodo di verifica", md +
                         "\nNel 2023-2026 l'effetto ha cambiato segno su tutti e tre gli indici: un backtest brillante su 7 anni "
                         "non ha superato la prova dei 3 anni successivi."))
    # VWAP trend
    rows = {}
    try:
        raw = L.get("hf_stk1m", hf_stock_minutes, "huggingface deerfieldgreen")
        ticks = sorted({c[0] for c in raw.columns})
        for cost in (0.0, 0.0001, 0.0002):
            ds = []
            for t in ticks:
                b = raw[t].dropna(subset=["close"])
                if len(b) > 50000:
                    ds.append(SI.simulate(b, SI.vwap_trend(b), cost))
            d = pd.DataFrame(dict(ret=pd.concat([x["ret"] for x in ds], axis=1).mean(axis=1),
                                  gross_ret=pd.concat([x["gross_ret"] for x in ds], axis=1).mean(axis=1),
                                  cost=pd.concat([x["cost"] for x in ds], axis=1).mean(axis=1),
                                  trades=pd.concat([x["trades"] for x in ds], axis=1).mean(axis=1)))
            add(f"VWAP trend a 1 minuto, {len(ds)} azioni Nasdaq 2022-24, costo {cost * 1e4:.0f} pb", d)
    except Exception as e:
        L.notes.append(f"azioni a 1 minuto non disponibili: {e}")
    for c in ("BTC", "ETH", "SOL"):
        b = L.get(f"bn_spot_5m_{c}USDT", lambda c=c: binance_klines(c + "USDT", "5m", "spot"), "binance.vision")
        for nm, pos, costs in (("VWAP trend", SI.vwap_trend(b), (0.0, 0.0007)),
                               ("VWAP trend con fascia 0,5%", SI.vwap_trend(b, deadband=0.005), (0.0007, 0.0030))):
            for cost in costs:
                add(f"{c} a 5 minuti 2017-26, {nm}, costo {cost * 1e4:.0f} pb", SI.simulate(b, pos, cost), 365)
    L.table("5c. VWAP trend (long sopra il VWAP di seduta, short sotto)", rows, cols,
            "17-20 cambi di posizione al giorno: e' lo stesso ordine di grandezza dei 15 al giorno del paper di Zarattini e Aziz, "
            "che pero' assume 0,0005 dollari per azione e nessuno slippage. Con qualunque costo realistico la regola distrugge il conto.")


def lab_crypto(L: Lab):
    close, dvol, ret, rf = L.cclose, L.cdvol, L.cret, L.rf365
    rows = {}
    for c in ("BTC", "ETH"):
        rows[f"{c} comprato e tenuto"] = M.summary(ret[c].loc["2018":], rf, 365)
    C = lambda fee: Costs(trade=fee, cash_haircut=1.0)
    maj = ["BTC", "ETH"]
    for name, lbs in (("trend BTC+ETH veloce (10-80 giorni)", (10, 20, 40, 80)), ("trend BTC+ETH lento (30-120 giorni)", (30, 60, 120))):
        W = SD.trend(close[maj], lookbacks=lbs, long_only=True, asset_vol=0.40, span=30, periods=365).clip(upper=0.5)
        for fee in (0.0010, 0.0030):
            res = run(SD.hold(W, 7), ret[maj], 0.0, C(fee), periods=365, band=0.03)
            r = res.ret.loc["2018":]
            L.three(rows, f"{name}, settimanale, {fee * 1e4:.0f} pb", r, rf, 365, dict(turnover=res.turnover.loc["2018":].mean() * 365))
    L.series["CR-TREND"] = book.cr_trend_returns(close, ret).ret.loc["2018":]       # = "lento, 30 pb" qui sopra
    btc_up = close["BTC"] > close["BTC"].rolling(100).mean()
    for name, top, uni, tf in (("momentum trasversale, 5 su 20", 5, 20, None),
                               ("momentum trasversale, 5 su 20, solo con BTC sopra la media a 100 giorni", 5, 20, btc_up)):
        W = SD.xs_momentum(close, dvol, (14, 28, 56), top, uni, 7, tf)
        for fee in (0.0010, 0.0030):
            res = run(W, ret, 0.0, C(fee), periods=365, band=0.03)
            r = res.ret.loc["2018":]
            L.three(rows, f"{name}, {fee * 1e4:.0f} pb", r, rf, 365, dict(turnover=res.turnover.loc["2018":].mean() * 365))
    raw = book.cr_xsmom_returns(close, dvol, ret).ret.loc["2018":]
    L.series["CR-XSMOM"] = xs = raw * book.xs_scale(raw)
    L.three(rows, "CR-XSMOM: momentum 5 su 20 con filtro, 30 pb, ridotto a volatilita' 25% (mai sopra 1x)", xs, rf, 365)
    L.table("6. Crypto giornaliero, solo long, spot (commissione + slippage per lato indicati)", rows, COLS + ("turnover",),
            "Universo: 60 monete scelte tra le maggiori di ogni anno, comprese quelle poi fallite (LUNA, FTT, EOS); a ogni "
            "ribilanciamento si guardano solo le 20 piu' scambiate IN QUEL MOMENTO. Resta una distorsione di sopravvivenza: "
            "le monete mai quotate su Binance non ci sono.")
    # carry
    rows, yr = {}, {}
    legs = {}
    for c in PERPS:
        sp = L.get(f"bn_spot_1d_{c}USDT", lambda c=c: binance_klines(c + "USDT", "1d", "spot"), "binance.vision")["close"]
        pp = L.get(f"bn_um_1d_{c}USDT", lambda c=c: binance_klines(c + "USDT", "1d", "um", "2019-09"), "binance.vision")["close"]
        f = L.get(f"bn_fund_{c}USDT", lambda c=c: binance_funding(c + "USDT", "2019-09").to_frame(), "binance.vision").iloc[:, 0]
        fd = f.groupby((f.index - pd.Timedelta(seconds=1)).normalize()).sum()      # il funding spetta a chi c'era PRIMA
        idx = sp.index.intersection(pp.index)
        yr[c] = fd.groupby(fd.index.year).sum()
        for nm, thr in (("sempre dentro", None), ("solo con funding > 5% annuo", 0.05)):
            legs[(c, nm)] = SD.funding_carry(sp.reindex(idx), pp.reindex(idx), fd, 0.0010, thr)["ret"]
    for nm in ("sempre dentro", "solo con funding > 5% annuo"):
        r = pd.concat([legs[(c, nm)] for c in PERPS], axis=1).mean(axis=1).dropna()
        L.three(rows, f"carry su 10 monete, {nm}", r, L.rf365, 365)
    L.table("7. Carry sui perpetual: long spot, short perpetual (10 pb per lato e per gamba)", rows, COLS,
            "Lo Sharpe qui e' in eccesso del tasso a breve. Il rischio vero non e' nei dati giornalieri: fallimento o blocco "
            "dell'exchange, auto-deleveraging dello short, liquidazione della gamba short in un rialzo violento.")
    fy = (pd.DataFrame(yr) * 100).round(1)
    md = "| anno | " + " | ".join(fy.columns) + " |\n|---|" + "---:|" * len(fy.columns) + "\n"
    md += "".join(f"| {y} | " + " | ".join("—" if pd.isna(v) else f"{v:.1f}" for v in row) + " |\n" for y, row in fy.iterrows())
    L.tables.append(("7b. Funding incassato dallo short in un anno, % (somma semplice, Binance USDT-M)", md +
                     "\nIl premio era del 30-40% nel 2021 ed e' sceso al 2-5% nel 2025-2026: oggi rende meno di un titolo di Stato a breve."))
    L.json["funding_annuo_pct"] = json.loads(fy.to_json())


def lab_walkforward(L: Lab):
    """Walk-forward vero su una famiglia: ogni 1 gennaio si sceglie la configurazione con lo Sharpe migliore nei 3 anni
    precedenti e la si usa per l'anno che segue. Misura quanto costa SCEGLIERE rispetto a non scegliere affatto."""
    close, ret, rf = L.cclose[["BTC", "ETH"]], L.cret[["BTC", "ETH"]], L.rf365
    grid = [(5, 20), (10, 40), (20, 80), (30, 120), (60, 200), (10, 120)]
    R = {}
    for f, sl in grid:
        W = SD.trend(close, lookbacks=(f, (f + sl) // 2, sl), long_only=True, asset_vol=0.40, span=30, periods=365).clip(upper=0.5)
        R[f"{f}-{sl}"] = run(SD.hold(W, 7), ret, 0.0, Costs(trade=book.CRYPTO_FEE, cash_haircut=1.0), periods=365, band=0.03).ret.loc["2018":]
        L.reg(f"walk-forward trend BTC+ETH {f}-{sl}", R[f"{f}-{sl}"], rf, 365)
    R = pd.DataFrame(R)
    sh = lambda x: x.mean() / x.std() * math.sqrt(365)
    parts, picks, train_sh = [], {}, []
    for y in range(2021, R.index[-1].year + 1):
        train = R.loc[str(y - 3):str(y - 1)]
        best = sh(train).idxmax()
        picks[y] = best
        train_sh.append(float(sh(train)[best]))
        parts.append(R.loc[str(y), best])
    wf = pd.concat(parts)
    test = R.loc[wf.index]
    rows = {"walk-forward: ogni anno la migliore dei 3 anni precedenti": M.summary(wf, rf, 365),
            "insieme delle 6 configurazioni (nessuna scelta)": M.summary(test.mean(axis=1), rf, 365),
            "la peggiore delle 6 (col senno di poi)": M.summary(test[sh(test).idxmin()], rf, 365),
            "la migliore delle 6 (col senno di poi, non ottenibile)": M.summary(test[sh(test).idxmax()], rf, 365)}
    L.table("6b. Walk-forward: scegliere i parametri contro non sceglierli (trend BTC+ETH, 2021 -> oggi)", rows, COLS,
            f"Scelte anno per anno: {', '.join(f'{y}: {k}' for y, k in picks.items())}. Sharpe medio delle configurazioni scelte "
            f"NEI LORO 3 anni di addestramento: {sum(train_sh) / len(train_sh):.2f}; Sharpe ottenuto nell'anno dopo: "
            f"{rows['walk-forward: ogni anno la migliore dei 3 anni precedenti']['sharpe']:.2f}. "
            "La differenza e' il sovradattamento da selezione, misurato. Per questo le strategie in produzione mediano su piu' "
            "orizzonti invece di scegliere il migliore.")
    L.json["walk_forward"] = dict(scelte=picks, sharpe_addestramento_medio=sum(train_sh) / len(train_sh))


def lab_portfolio(L: Lab):
    idx = pd.date_range("2018-01-01", L.cclose.index[-1], freq="D")
    S = pd.DataFrame({k: L.series[k] for k in ("CR-TREND", "CR-XSMOM", "EQ-MR", "MA-TREND")}).reindex(idx).fillna(0.0)
    rf = L.rf365.reindex(idx).ffill()
    a = risk_parity(S)
    port = combine(S, a)
    rows = {}
    for k in S:
        rows[k] = M.summary(S[k], rf, 365)
        rows[k + " · scelta"] = M.summary(S[k].loc[:SPLIT], rf, 365)
        rows[k + " · verifica"] = M.summary(S[k].loc[SPLIT:], rf, 365)
    L.table("8a. Le quattro strategie scelte (rendimenti sul capitale assegnato a ciascuna)", rows)
    mm = ((1 + S).resample("ME").prod() - 1).corr().round(2)
    md = "| | " + " | ".join(mm.columns) + " |\n|---|" + "---:|" * len(mm.columns) + "\n"
    md += "".join(f"| {i} | " + " | ".join(f"{v:.2f}" for v in row) + " |\n" for i, row in mm.iterrows())
    L.tables.append(("8b. Correlazione dei rendimenti mensili", md + "\nPesi medi (parita' di rischio): " +
                     ", ".join(f"{k} {v:.0%}" for k, v in a.mean().items()) + "."))
    # robustezza delle quattro: costi raddoppiati e un giorno di ritardo nell'esecuzione
    rb = {}
    H, Lo, C = L.P["high"], L.P["low"], L.P["close"]
    variants = {
        "CR-TREND": lambda fee, lag: book.cr_trend_returns(L.cclose, L.cret, book.CRYPTO_FEE * fee, lag).ret.loc["2018":],
        "CR-XSMOM": lambda fee, lag: (lambda raw: raw * book.xs_scale(raw))(
            book.cr_xsmom_returns(L.cclose, L.cdvol, L.cret, book.CRYPTO_FEE * fee, lag).ret.loc["2018":]),
        "EQ-MR": lambda fee, lag: book.eq_mr_returns(H, Lo, C, L.ret, L.rf, book.INDEX_FEE * fee, lag).loc["2018":],
        "MA-TREND": lambda fee, lag: book.ma_trend_returns(L.adj, L.rf, book.ETF_FEE * fee, lag).ret.loc["2018":],
    }
    alt = {"costi_doppi": {}, "ritardo_1g": {}}
    for k, fn in variants.items():
        per = book.SLEEVES[k].periods
        rfx = rf if per == 365 else L.rf
        r2, rl = fn(2.0, 1), fn(1.0, 2)
        alt["costi_doppi"][k], alt["ritardo_1g"][k] = r2, rl
        rb[k] = dict(base=M.sharpe(S[k], rf, 365), costi_doppi=M.sharpe(r2, rfx, per), ritardo_1g=M.sharpe(rl, rfx, per))
    for nm, d in alt.items():
        S2 = pd.DataFrame(d).reindex(idx).fillna(0.0)
        rb.setdefault("PORTAFOGLIO", dict(base=M.sharpe(port, rf, 365)))[nm] = M.sharpe(combine(S2, risk_parity(S2)), rf, 365)
    md = "| | Sharpe di base | con i costi raddoppiati | con un giorno di ritardo |\n|---|---:|---:|---:|\n"
    md += "".join(f"| {k} | {v['base']:.2f} | {v['costi_doppi']:.2f} | {v['ritardo_1g']:.2f} |\n" for k, v in rb.items())
    L.tables.append(("8b-bis. Robustezza: costi raddoppiati e ritardo di esecuzione (2018 -> oggi)", md +
                     "\nEQ-MR e' l'unica che dipende dall'eseguire sulla chiusura del segnale: in produzione va scambiata tra le 15:45 e le 16:00 di New York."))
    L.json["robustezza"] = rb
    rows = {}

    def three(name, r, extra=None):
        rows[name] = dict(M.summary(r, rf, 365), **(extra or {}))
        rows[name + " · scelta"] = M.summary(r.loc[:SPLIT], rf, 365)
        rows[name + " · verifica"] = M.summary(r.loc[SPLIT:], rf, 365)
    three("PORTAFOGLIO senza leva", port)
    lev_series = {}
    for tv, cap in ((0.10, 1.5), (0.15, 2.0), (0.20, 3.0), (0.30, 6.0), (0.40, 8.0), (0.60, 12.0)):
        Lv = vol_target_leverage(port, tv, 60, cap)
        r = scale_returns(port, Lv, rf, 0.015, 365).iloc[60:]
        three(f"volatilita' obiettivo {tv:.0%}, leva massima {cap:g}x", r, dict(leva_media=float(Lv.iloc[60:].mean())))
        lev_series[f"VT{int(tv * 100)}"] = r
    L.table("8c. Portafoglio e leva (costo della leva: tasso a breve + 1,5% sulla parte presa a prestito)", rows,
            COLS + ("mesi_le_m20", "leva_media"))
    # significativita' contro tutte le prove
    tr = pd.Series(L.trials).clip(-2.0, 3.0)     # le strategie distrutte dai costi (Sharpe -20) non sono "sfortuna": non devono gonfiare la varianza
    n = len(tr) + EXTRA_TRIALS
    years_sel = len(port.loc[:SPLIT]) / 365
    # Varianza dello Sharpe STIMATO di una strategia senza abilita' su quel numero di anni: 1/anni (Lo 2002).
    # Non si usa la varianza empirica delle prove: qui molte prove sono verifiche di affermazioni altrui che perdono
    # per i costi (media molto sotto zero), e la formula del massimo atteso presuppone prove a media nulla.
    var = 1.0 / years_sel
    var_emp = float(tr.var(ddof=1))
    ps = port.loc[:SPLIT]
    exc = port - rf
    d = dict(prove_riprodotte=len(tr), prove_esplorative=EXTRA_TRIALS, prove=n, varianza_sharpe_prove=var,
             sharpe_atteso_dal_migliore_a_caso=M.expected_max_sharpe(n, var),
             sharpe_tutto=M.sharpe(port, rf, 365), sharpe_scelta=M.sharpe(ps, rf.loc[:SPLIT], 365),
             sharpe_verifica=M.sharpe(port.loc[SPLIT:], rf.loc[SPLIT:], 365),
             psr_zero=M.psr(exc, 0.0, 365), psr_zero_verifica=M.psr(exc.loc[SPLIT:], 0.0, 365), dsr=M.dsr(exc, n, var, 365),
             errore_standard_sharpe=1.0 / math.sqrt(len(port) / 365))
    L.json["significativita"] = d
    L.tables.append(("8d. Quanto puo' essere fortuna", (
        f"- Configurazioni provate: **{n}** ({len(tr)} riprodotte da questo programma + {EXTRA_TRIALS} esplorative provate a mano e scartate); "
        f"varianza dello Sharpe di una strategia SENZA abilita' su {years_sel:.1f} anni: {var:.2f} "
        f"(quella empirica delle prove, {var_emp:.2f}, e' gonfiata dalle regole distrutte dai costi e non si usa).\n"
        f"- Sharpe che ci si aspetta dal MIGLIORE di {n} tentativi senza alcuna abilita': **{d['sharpe_atteso_dal_migliore_a_caso']:.2f}**.\n"
        f"- Sharpe del portafoglio: {d['sharpe_tutto']:.2f} su tutto il periodo, {d['sharpe_scelta']:.2f} nel periodo di scelta, "
        f"**{d['sharpe_verifica']:.2f} nel periodo di verifica**.\n"
        f"- Probabilita' che lo Sharpe vero sia sopra zero (PSR): {d['psr_zero']:.3f} su tutto il periodo, {d['psr_zero_verifica']:.3f} sul solo periodo di verifica.\n"
        f"- Deflated Sharpe (probabilita' che lo Sharpe vero superi quello del migliore a caso): **{d['dsr']:.2f}**. La soglia del progetto e' 0,95: "
        "il portafoglio NON la supera. Il test e' severo (il portafoglio e' una combinazione, non la migliore delle prove), ma il verdetto onesto e': "
        "evidenza promettente, non conclusiva. Decide il paper trading.\n"
        f"- Errore standard dello Sharpe con {len(port) / 365:.1f} anni di dati: ±{d['errore_standard_sharpe']:.2f}.")))
    # Kelly e Monte Carlo
    rfm = float(rf.iloc[-365:].mean())
    Lk, curve = MC.kelly_leverage(port, rfm, 0.015, 365)
    levs = [1, 1.5, 2, 3, 4, 6, 8, 10, 12, 15]
    sw = MC.leverage_sweep(port, levs, rfm, 0.015, horizon=3 * 365, n_paths=4000, block=30, ruin_level=0.5, periods=365)
    sw2 = MC.leverage_sweep(port, levs, rfm, 0.015, horizon=3 * 365, n_paths=4000, block=30, ruin_level=0.5, periods=365,
                            shock=(0.001, 0.15))
    half = MC.leverage_sweep(port - (port.mean() - rfm) * 0.5, levs, rfm, 0.015, horizon=3 * 365, n_paths=4000, block=30,
                             ruin_level=0.5, periods=365)

    def mc_table(df):
        md = ("| leva | CAGR 5° pct | CAGR mediano | CAGR 95° pct | caduta massima mediana | caduta massima 5° pct | P(perdita a 3 anni) | "
              "P(capitale dimezzato) | mese medio | P(mese ≥ +20%) | P(mese ≤ −20%) |\n|---:|" + "---:|" * 10 + "\n")
        for Lx, r in df.iterrows():
            md += (f"| {Lx:g}x | {r.cagr_p05:.0%} | {r.cagr_p50:.0%} | {r.cagr_p95:.0%} | {r.maxdd_p50:.0%} | {r.maxdd_p05:.0%} | "
                   f"{r.p_perdita:.1%} | {r.p_rovina:.1%} | {r.mese_medio:.1%} | {r.p_mese_ge_20:.1%} | {r.p_mese_le_m20:.1%} |\n")
        return md
    L.tables.append(("9a. Monte Carlo a 3 anni: il portafoglio a leva costante (4.000 percorsi, blocchi di 30 giorni)", mc_table(sw) +
                     f"\nLeva di Kelly empirica (massimizza la crescita logaritmica NEL campione): **{Lk:g}x**, crescita log {curve.max():.0%} l'anno. "
                     "E' un tetto teorico gonfiato dall'errore di stima: oltre quel punto piu' leva fa crescere MENO."))
    L.tables.append(("9b. Lo stesso, se il rendimento in eccesso vero fosse la META' di quello del backtest", mc_table(half) +
                     "\nE' il caso realistico: dopo la pubblicazione le anomalie perdono in media il 58% del rendimento (McLean e Pontiff 2016), "
                     "e qui il periodo di verifica ha reso il 58% di quello di scelta in termini di Sharpe."))
    L.tables.append(("9c. Lo stesso, con uno scenario che il campione non contiene", mc_table(sw2) +
                     "\nScenario: ogni giorno, con probabilita' 0,1% (una volta ogni 2,7 anni circa), il portafoglio senza leva perde un 15% "
                     "in piu' (exchange che blocca i prelievi, gap notturno, correlazioni che vanno a 1)."))
    L.json["monte_carlo"] = dict(base=json.loads(sw.to_json(orient="index")), meta_rendimento=json.loads(half.to_json(orient="index")),
                                 shock=json.loads(sw2.to_json(orient="index")), kelly_empirico=Lk,
                                 crescita_log_per_leva={str(k): (None if not math.isfinite(v) else float(v)) for k, v in curve.items()})
    out = S.copy()
    out["PORT"] = port
    for k, v in lev_series.items():
        out[k] = v
    out["RF"] = rf
    for c in a:
        out["W_" + c] = a[c]
    L.series_out = out


def main(root: str | None = None, refresh: bool = False, quick: bool = False):
    root = root or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    L = Lab(root, refresh)
    L.load_daily()
    L.load_crypto()
    labs = [lab_benchmarks, lab_trend, lab_equity, lab_gex] + ([] if quick else [lab_intraday]) + [lab_crypto, lab_walkforward, lab_portfolio]
    for f in labs:
        f(L)
        print("fatto:", f.__name__, flush=True)
    out_dir = os.path.join(root, "research", "v5")
    os.makedirs(out_dir, exist_ok=True)
    fps = {k: L.st.meta(k).get("fingerprint") for k in ("gex", "yahoo_1d_SPY", "bn_spot_1d_BTCUSDT", "spx_m1")}
    head = (f"# Ricerca v5: risultati\n\nGenerato da `python -m gerva.research.run` il {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M} UTC. "
            f"Dati fino al {L.adj.index[-1].date()} (azioni) e al {L.cclose.index[-1].date()} (crypto).\n\n"
            "**Tutti i numeri sono SIMULATI su dati storici**, al netto dei costi indicati in ogni tabella. Nessuno e' un risultato reale.\n"
            f"«scelta» = fino al 31/12/2022; «verifica» = dal 1/1/2023, mai usato per scegliere. Sharpe in eccesso del tasso a breve.\n"
            "cagr = rendimento annuo composto; vol = volatilita' annua; max_dd = caduta massima; mesi_ge_20 = quota di mesi con almeno +20%.\n\n"
            f"Impronte dei dati: {json.dumps(fps)}\n")
    body = "".join(f"\n## {t}\n\n{md}\n" for t, md in L.tables)
    notes = ("\n## Note\n\n" + "\n".join(f"- {n}" for n in L.notes) + "\n") if L.notes else ""
    with open(os.path.join(out_dir, "RESULTS.md"), "w") as fh:
        fh.write(head + body + notes)
    L.json["prove"] = L.trials
    with open(os.path.join(out_dir, "results.json"), "w") as fh:
        json.dump(L.json, fh, indent=1, default=str)
    L.series_out.to_parquet(os.path.join(out_dir, "series.parquet"))
    print("scritto", out_dir)
    return L


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--quick", action="store_true", help="salta i laboratori intraday (lenti)")
    a = ap.parse_args()
    main(refresh=a.refresh, quick=a.quick)
