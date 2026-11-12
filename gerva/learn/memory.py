"""Memoria dei trade: un registro a sola aggiunta. Di ogni trade non si salva solo se ha vinto o perso, ma perche' e' stato
aperto (il contesto), come e' stato eseguito (prezzi, costi, slippage) e come si e' comportato (MAE, MFE, motivo di uscita)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field

import pandas as pd


@dataclass
class TradeRecord:
    strategy_id: str
    symbol: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    notional: float
    leverage: float
    risk: float                      # perdita in valuta allo stop iniziale
    pnl: float
    R: float                         # pnl / risk
    exit_reason: str
    commission: float = 0.0
    funding: float = 0.0
    slippage: float = 0.0            # in frazione del prezzo, rispetto al prezzo teorico di ingresso o di stop
    mae: float | None = None         # escursione avversa massima, in multipli del rischio (negativa)
    mfe: float | None = None         # escursione favorevole massima, in multipli del rischio
    source: str = "paper"            # "paper" | "sim" (trade storici simulati) | "live"
    context: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.strategy_id}:{self.symbol}:{self.entry_time}"


class TradeMemory:
    def __init__(self, path: str):
        self.path = path

    def append(self, rec: TradeRecord) -> bool:
        """Aggiunge il trade se non c'e' gia' (stessa chiave): rieseguire un passo non duplica la memoria."""
        if rec.key in {r.key for r in self.load()}:
            return False
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(asdict(rec), ensure_ascii=False, default=str) + "\n")
        return True

    def load(self) -> list[TradeRecord]:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(TradeRecord(**json.loads(line)))
        return out

    def frame(self, extra: pd.DataFrame | None = None) -> pd.DataFrame:
        """Tabella dei trade con il contesto in colonne. extra: trade storici simulati da affiancare."""
        rows = []
        for r in self.load():
            d = asdict(r)
            ctx = d.pop("context") or {}
            rows.append({**d, **{k: v for k, v in ctx.items() if k not in d}})
        df = pd.DataFrame(rows)
        if extra is not None and len(extra):
            df = pd.concat([extra, df], ignore_index=True) if len(df) else extra.copy()
        if len(df):
            df["entry_time"] = pd.to_datetime(df["entry_time"])
            df = df.sort_values("entry_time").reset_index(drop=True)
        return df
