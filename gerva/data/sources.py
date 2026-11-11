"""
Sorgenti di dati pubbliche, tutte gratuite e senza chiave.

  yahoo()               barre giornaliere o orarie (OHLCV + chiusura rettificata per dividendi e split)
  fred()                serie macro (VIX, tassi) dal sito della Federal Reserve di St. Louis
  gex_squeezemetrics()  GEX e DIX giornalieri dell'S&P 500 dal 2011 (SqueezeMetrics, file pubblico)
  binance_klines()      candele spot o perpetual dall'archivio data.binance.vision (non serve un conto)
  binance_funding()     tassi di funding dei perpetual USDT-M dallo stesso archivio
  histdata_m1()         S&P 500 a 1 minuto 2010-2018 (quotazioni CFD di histdata.com, senza volumi)

Regole comuni:
  * ogni richiesta ha un timeout e fino a 5 tentativi con attesa esponenziale;
  * ogni tabella scaricata finisce nello Store con l'impronta SHA-256 del contenuto: un risultato
    di ricerca cita l'impronta, quindi due studi sono confrontabili solo se l'impronta coincide;
  * gli indici temporali sono sempre ordinati, senza duplicati, e l'ULTIMA barra giornaliera viene
    scartata se la seduta non e' ancora chiusa (una candela aperta e' un look-ahead mascherato).
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

import numpy as np
import pandas as pd

UA = {"User-Agent": "Mozilla/5.0 (compatible; research-client)"}


class DataError(RuntimeError):
    """La sorgente non ha risposto o ha risposto con dati inutilizzabili."""


def _get(url: str, timeout: float = 30.0, tries: int = 5, allow_404: bool = False) -> bytes | None:
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404 and allow_404:
                return None
            last = e
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:                      # rete, TLS, timeout: si riprova
            last = e
        time.sleep(min(2.0 ** k, 20.0))
    raise DataError(f"{url}: {last}")


# ---------------------------------------------------------------------------
# Store: cache su disco con impronta
# ---------------------------------------------------------------------------
class Store:
    def __init__(self, root: str = "data_cache"):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _p(self, key: str) -> str:
        return os.path.join(self.root, key.replace("/", "_") + ".parquet")

    @staticmethod
    def fingerprint(df: pd.DataFrame) -> str:
        h = hashlib.sha256()
        h.update("|".join(map(str, df.columns)).encode())
        h.update(pd.util.hash_pandas_object(df, index=True).values.tobytes())
        return h.hexdigest()[:16]

    def has(self, key: str) -> bool:
        return os.path.exists(self._p(key))

    def put(self, key: str, df: pd.DataFrame, source: str) -> str:
        fp = self.fingerprint(df)
        tmp = self._p(key) + ".tmp"
        df.to_parquet(tmp)
        os.replace(tmp, self._p(key))               # scrittura atomica: mai un file a meta'
        with open(self._p(key) + ".json", "w") as f:
            json.dump(dict(fingerprint=fp, source=source, rows=len(df),
                           first=str(df.index[0]) if len(df) else None,
                           last=str(df.index[-1]) if len(df) else None,
                           saved=pd.Timestamp.now(tz="UTC").isoformat()), f)
        return fp

    def get(self, key: str) -> pd.DataFrame:
        df = pd.read_parquet(self._p(key))
        meta = self.meta(key)
        if meta and self.fingerprint(df) != meta["fingerprint"]:
            raise DataError(f"cache corrotta: {key}")
        return df

    def meta(self, key: str) -> dict:
        try:
            with open(self._p(key) + ".json") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def cached(self, key: str, fn, source: str, refresh: bool = False) -> pd.DataFrame:
        if self.has(key) and not refresh:
            return self.get(key)
        df = fn()
        self.put(key, df, source)
        return df


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


# ---------------------------------------------------------------------------
# Yahoo Finance
# ---------------------------------------------------------------------------
def yahoo(symbol: str, interval: str = "1d", rng: str | None = None, keep_open_bar: bool = False) -> pd.DataFrame:
    """OHLCV + adj (chiusura rettificata). Giornaliero: tutta la storia. Orario: circa 730 giorni.
    Indice: data (giornaliero) oppure orario di New York (intraday).
    keep_open_bar: tiene la barra di oggi anche a mercato aperto. Serve SOLO alle strategie che decidono a ridosso
    della chiusura (EQ-MR alle 15:50): chi la usa sa che massimo, minimo e chiusura non sono definitivi."""
    q = urllib.parse.quote(symbol)
    if interval == "1d":
        url = (f"https://query2.finance.yahoo.com/v8/finance/chart/{q}"
               f"?period1=0&period2=4102444800&interval=1d&events=div%2Csplits")
    else:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{q}?range={rng or '730d'}&interval={interval}"
    raw = json.loads(_get(url))["chart"]
    if raw.get("error") or not raw.get("result"):
        raise DataError(f"yahoo {symbol}: {raw.get('error')}")
    res = raw["result"][0]
    ts = res.get("timestamp")
    if not ts:
        raise DataError(f"yahoo {symbol}: nessuna barra")
    qd = res["indicators"]["quote"][0]
    df = pd.DataFrame({k: qd.get(k) for k in ("open", "high", "low", "close", "volume")},
                      index=pd.to_datetime(ts, unit="s", utc=True)).astype(float)
    tz = res["meta"].get("exchangeTimezoneName", "America/New_York")
    if interval == "1d":
        adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose")
        df["adj"] = np.asarray(adj, float) if adj is not None else df["close"]
        df.index = df.index.tz_convert(tz).normalize().tz_localize(None)
        # la barra di oggi a mercato aperto non e' una chiusura: via
        now = pd.Timestamp.now(tz=tz)
        if not keep_open_bar and len(df) and df.index[-1] == now.normalize().tz_localize(None) and now.hour < 17:
            df = df.iloc[:-1]
    else:
        df.index = df.index.tz_convert(tz).tz_localize(None)
    df = _clean(df.dropna(subset=["close"]))
    df = df[df["close"] > 0]
    return df


def yahoo_panel(symbols, store: Store | None = None, refresh: bool = False, workers: int = 4) -> dict[str, pd.DataFrame]:
    """{campo: tabella date x simboli} per open, high, low, close, adj, volume."""
    def one(s):
        key = f"yahoo_1d_{s}"
        try:
            if store is not None:
                return s, store.cached(key, lambda: yahoo(s), "yahoo", refresh)
            return s, yahoo(s)
        except DataError:
            return s, None
    out = {}
    with cf.ThreadPoolExecutor(workers) as ex:
        for s, df in ex.map(one, list(symbols)):
            if df is not None and len(df):
                out[s] = df
    fields = ("open", "high", "low", "close", "adj", "volume")
    return {f: pd.DataFrame({s: d[f] for s, d in out.items()}).sort_index() for f in fields}


# ---------------------------------------------------------------------------
# FRED e SqueezeMetrics
# ---------------------------------------------------------------------------
def fred(series: str) -> pd.Series:
    raw = _get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}")
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = ["date", series]
    s = pd.to_numeric(df[series], errors="coerce")
    s.index = pd.to_datetime(df["date"])
    return s.dropna().sort_index()


def gex_squeezemetrics() -> pd.DataFrame:
    """Colonne: price (S&P 500), dix (quota di vendite allo scoperto nei dark pool), gex (dollari per 1%).
    Il valore del giorno t e' pubblicato DOPO la chiusura di t: si puo' usare solo da t+1."""
    raw = _get("https://squeezemetrics.com/monitor/static/DIX.csv")
    df = pd.read_csv(io.BytesIO(raw), parse_dates=["date"]).set_index("date")
    return _clean(df.astype(float))


# ---------------------------------------------------------------------------
# Binance: archivio pubblico
# ---------------------------------------------------------------------------
_KCOLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
          "trades", "taker_base", "taker_quote", "ignore"]


def _months(start: str, end: str | None = None):
    end_p = pd.Period(end or pd.Timestamp.now(tz="UTC").strftime("%Y-%m"), "M")
    p = pd.Period(start, "M")
    while p <= end_p:
        yield p.strftime("%Y-%m")
        p += 1


def _to_ts(x: pd.Series) -> pd.DatetimeIndex:
    # dal 2025 l'archivio spot usa i microsecondi invece dei millisecondi
    v = x.astype("int64")
    unit = np.where(v > 10 ** 14, 1000, 1)
    return pd.to_datetime((v // unit).values, unit="ms")


def _zip_csv(raw: bytes, names=None) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        with z.open(z.namelist()[0]) as f:
            head = f.read(64)
            f.seek(0)
            has_header = not head.lstrip()[:1].isdigit()
            return pd.read_csv(f, header=0 if has_header else None, names=None if has_header else names)


def binance_klines(symbol: str, interval: str = "1d", market: str = "spot", start: str = "2017-08",
                   end: str | None = None, workers: int = 8) -> pd.DataFrame:
    """Candele dall'archivio mensile. market: 'spot' oppure 'um' (perpetual USDT-M). Indice UTC di APERTURA."""
    base = ("https://data.binance.vision/data/spot/monthly/klines" if market == "spot"
            else "https://data.binance.vision/data/futures/um/monthly/klines")

    def one(m):
        raw = _get(f"{base}/{symbol}/{interval}/{symbol}-{interval}-{m}.zip", allow_404=True, timeout=60)
        if raw is None:
            return None
        d = _zip_csv(raw, _KCOLS)
        d.columns = _KCOLS[:len(d.columns)]
        return d
    with cf.ThreadPoolExecutor(workers) as ex:
        parts = [p for p in ex.map(one, list(_months(start, end))) if p is not None and len(p)]
    if not parts:
        raise DataError(f"binance {market} {symbol} {interval}: nessun file")
    d = pd.concat(parts, ignore_index=True)
    out = d[["open", "high", "low", "close", "volume", "quote_volume"]].astype(float)
    out.index = _to_ts(d["open_time"])
    return _clean(out)


def binance_funding(symbol: str, start: str = "2020-01", end: str | None = None, workers: int = 8) -> pd.Series:
    """Tasso di funding per intervallo (di norma ogni 8 ore). Positivo: i long pagano gli short."""
    base = "https://data.binance.vision/data/futures/um/monthly/fundingRate"

    def one(m):
        raw = _get(f"{base}/{symbol}/{symbol}-fundingRate-{m}.zip", allow_404=True)
        return None if raw is None else _zip_csv(raw, ["calc_time", "funding_interval_hours", "last_funding_rate"])
    with cf.ThreadPoolExecutor(workers) as ex:
        parts = [p for p in ex.map(one, list(_months(start, end))) if p is not None and len(p)]
    if not parts:
        raise DataError(f"binance funding {symbol}: nessun file")
    d = pd.concat(parts, ignore_index=True)
    d.columns = ["calc_time", "funding_interval_hours", "last_funding_rate"][:len(d.columns)]
    s = pd.Series(d["last_funding_rate"].astype(float).values, index=_to_ts(d["calc_time"]), name=symbol)
    return s[~s.index.duplicated(keep="last")].sort_index()


# ---------------------------------------------------------------------------
# S&P 500 a 1 minuto (histdata.com, copia pubblica su GitHub: 2010-2018)
# ---------------------------------------------------------------------------
def histdata_m1(symbol: str = "SPXUSD", years=range(2010, 2019)) -> pd.DataFrame:
    """OHLC a 1 minuto in orario di New York. La sorgente e' in EST fisso (UTC-5, senza ora legale)."""
    base = "https://raw.githubusercontent.com/FutureSharks/financial-data/master/pyfinancialdata/data/stocks/histdata"
    parts = []
    for y in years:
        raw = _get(f"{base}/{symbol}/DAT_ASCII_{symbol}_M1_{y}.csv", allow_404=True, timeout=120)
        if raw is None:
            continue
        d = pd.read_csv(io.BytesIO(raw), sep=";", header=None, names=["t", "open", "high", "low", "close", "v"])
        idx = pd.to_datetime(d["t"], format="%Y%m%d %H%M%S")
        idx = (idx + pd.Timedelta(hours=5)).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)
        d.index = pd.DatetimeIndex(idx)
        parts.append(d[["open", "high", "low", "close"]].astype(float))
    if not parts:
        raise DataError(f"histdata {symbol}: nessun anno disponibile")
    return _clean(pd.concat(parts))


# ---------------------------------------------------------------------------
# Azioni USA a 1 minuto (Hugging Face, dataset pubblico deerfieldgreen/stk-intraday-data-1min)
# ---------------------------------------------------------------------------
def hf_stock_minutes() -> pd.DataFrame:
    """25 titoli del Nasdaq, barre da 1 minuto con volumi, 2022-08 -> 2024-08, ora di New York.
    Colonne a due livelli: (simbolo, campo)."""
    import ast
    raw = _get("https://huggingface.co/datasets/deerfieldgreen/stk-intraday-data-1min/resolve/main/"
               "data/train-00000-of-00001.parquet", timeout=600)
    d = pd.read_parquet(io.BytesIO(raw))
    cols = [ast.literal_eval(c) if isinstance(c, str) and c.startswith("(") else c for c in d.columns]
    d.columns = pd.MultiIndex.from_tuples([c if isinstance(c, tuple) else (c, "") for c in cols])
    d = d.set_index(("date", "")).sort_index()
    d.index.name = "date"
    return d[~d.index.duplicated(keep="last")]


# ---------------------------------------------------------------------------
# Binance: ultime candele in tempo reale (specchio pubblico dei dati di mercato, senza chiave)
# ---------------------------------------------------------------------------
def binance_recent(symbol: str, interval: str = "1d", limit: int = 200) -> pd.DataFrame:
    """Ultime `limit` candele CHIUSE (quella in corso viene scartata). Indice UTC di apertura."""
    raw = json.loads(_get(f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"))
    if not raw:
        raise DataError(f"binance recent {symbol}: vuoto")
    d = pd.DataFrame(raw, columns=_KCOLS)
    now_ms = int(time.time() * 1000)
    d = d[d["close_time"].astype("int64") < now_ms]
    out = d[["open", "high", "low", "close", "volume", "quote_volume"]].astype(float)
    out.index = pd.to_datetime(d["open_time"].astype("int64").values, unit="ms")
    return _clean(out)
