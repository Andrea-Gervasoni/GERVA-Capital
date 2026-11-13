"""
Dati di mercato per il ciclo live: storia in cache + ultime barre, con misura della freschezza.

Il ciclo non decide mai su dati di cui non conosce l'eta'. `ages()` restituisce le ore passate dall'ultima barra
chiusa di ogni sede; il motore di rischio ferma gli aumenti di esposizione se superano il limite.
"""
from __future__ import annotations

import concurrent.futures as cf
import logging

import pandas as pd

from ..data import DataError, Store, binance_klines, binance_recent, yahoo
from ..research.run import COINS
from ..strategies import book

log = logging.getLogger("gerva.market")
EQUITY = sorted(set(book.TREND_UNIVERSE) | {"SPY", "QQQ", "^IRX", "^VIX", "^VIX3M"})


class Market:
    def __init__(self, store: Store, coins=COINS, equity=EQUITY, cash_symbol: str | None = None):
        self.st, self.coins, self.eq_symbols = store, list(coins), list(equity)
        self.cash_symbol = cash_symbol
        self.cclose = self.cdvol = self.cret = None
        self.P = None
        self.errors: dict[str, str] = {}

    def _save(self, key: str, df: pd.DataFrame, source: str) -> None:
        """Writes the refreshed daily bars back to the cache, so the terminal's charts and its data-age band see the same
        prices the engine uses (before this the cache kept the bars of the first download). Never fatal."""
        try:
            if df is not None and len(df) and (not self.st.has(key) or len(df) >= len(self.st.get(key))):
                self.st.put(key, df, source)
        except Exception as e:
            log.info("cache not updated for %s: %s", key, str(e)[:80])

    # ---- crypto -------------------------------------------------------------
    def _coin(self, c: str):
        key = f"bn_spot_1d_{c}USDT"
        try:
            hist = self.st.cached(key, lambda: binance_klines(c + "USDT", "1d", "spot"), "binance.vision")
        except DataError:
            return c, None
        try:
            rec = binance_recent(c + "USDT", "1d", 400)
            hist = pd.concat([hist[hist.index < rec.index[0]], rec])
            self._save(key, hist, "binance.vision + recent")
        except DataError as e:
            if c in ("BTC", "ETH"):
                raise
            log.info("%s: nessun dato recente (%s): trattata come non piu' quotata", c, str(e)[:60])
        return c, hist

    def refresh_crypto(self) -> None:
        with cf.ThreadPoolExecutor(8) as ex:
            parts = dict(ex.map(self._coin, self.coins))
        cl = {c: d["close"] for c, d in parts.items() if d is not None}
        qv = {c: d["quote_volume"] for c, d in parts.items() if d is not None}
        close = pd.DataFrame(cl)
        idx = pd.date_range(close.index[0], close.index[-1], freq="D")
        self.cclose, self.cdvol = close.reindex(idx), pd.DataFrame(qv).reindex(idx)
        r = self.cclose.pct_change(fill_method=None)
        self.cret = r.mask(self.cclose.notna() & self.cclose.shift(1).isna())

    # ---- azioni ed ETF ------------------------------------------------------
    def refresh_equity(self, keep_open_bar: bool = False) -> None:
        def one(s):
            return s, yahoo(s, keep_open_bar=keep_open_bar)
        with cf.ThreadPoolExecutor(4) as ex:
            out = dict(ex.map(one, self.eq_symbols))
        fields = ("open", "high", "low", "close", "adj", "volume")
        P = {f: pd.DataFrame({s: d[f] for s, d in out.items()}).sort_index() for f in fields}
        if not keep_open_bar:                      # closed bars only: they become the cache the terminal's charts read
            for sym, d in out.items():
                self._save(f"yahoo_1d_{sym}", d, "yahoo")
        keep = P["adj"]["SPY"].notna()
        self.P = {k: v[keep] for k, v in P.items()}
        if self.cash_symbol:                       # ETF monetario: se il dato manca si prosegue senza parcheggiare la cassa
            try:
                c = yahoo(self.cash_symbol, keep_open_bar=keep_open_bar)
                for f in fields:
                    self.P[f][self.cash_symbol] = c[f].reindex(self.P[f].index).ffill()
            except Exception as e:
                log.warning("ETF monetario %s non disponibile (%s): la liquidita' resta ferma", self.cash_symbol, str(e)[:80])

    def refresh(self, keep_open_bar: bool = False) -> None:
        self.errors = {}
        for name, fn in (("crypto", self.refresh_crypto), ("ibkr", lambda: self.refresh_equity(keep_open_bar))):
            try:
                fn()
            except Exception as e:                 # una sede giu' non deve togliere i dati dell'altra
                self.errors[name] = f"{type(e).__name__}: {str(e)[:120]}"
                log.warning("dati %s non aggiornati: %s", name, self.errors[name])

    # ---- letture ------------------------------------------------------------
    @property
    def rf(self) -> pd.Series:
        return (self.P["adj"]["^IRX"] / 100 / 252).ffill()

    def ages(self, now: pd.Timestamp | None = None) -> dict[str, float]:
        """Ore dall'ultima barra CHIUSA per sede (inf se la sede non ha dati)."""
        now = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
        now = now.tz_convert("UTC").tz_localize(None) if now.tzinfo else now
        out = {"crypto": float("inf"), "ibkr": float("inf")}
        if self.cclose is not None:
            last = self.cclose["BTC"].dropna().index[-1]
            out["crypto"] = (now - (last + pd.Timedelta(days=1))).total_seconds() / 3600
        if self.P is not None:
            last = self.P["close"]["SPY"].dropna().index[-1]
            out["ibkr"] = (now - (last + pd.Timedelta(hours=21))).total_seconds() / 3600      # chiusura di New York ~ 21:00 UTC
        return out

    def venue_of(self, symbol: str) -> str:
        return "crypto" if self.cclose is not None and symbol in self.cclose.columns else "ibkr"

    def last_prices(self, symbols: list[str]) -> dict[str, float]:
        out = {}
        for s in symbols:
            if self.cclose is not None and s in self.cclose.columns:
                v = self.cclose[s].dropna()
            elif self.P is not None and s in self.P["close"].columns:
                v = self.P["close"][s].dropna()
            else:
                continue
            if len(v):
                out[s] = float(v.iloc[-1])
        return out
