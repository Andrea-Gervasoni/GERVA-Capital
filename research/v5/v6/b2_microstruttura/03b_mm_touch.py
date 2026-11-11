"""Sensibilita' del test 2 al modello di fill: 'touch' = riempito appena un trade stampa AL prezzo quotato (testa della coda:
limite superiore irrealistico per un retail) contro 'through' (coda in fondo, conservativo). Binance USDT-M, giorni 2024 (verifica)."""
import numpy as np, pandas as pd
from lib import *
from mm import *
exec(open("03_mm.py").read().split("cfgs =")[0].split("INV = 5")[1].replace("def load", "INV = 5\ndef load", 1)) if False else None
INV = 5
rows = []
for sym in ("BTCUSDT", "ETHUSDT"):
    for d, f in day_files(sym):
        df = pd.read_parquet(f)
        if "bid" not in df.columns: continue
        bid, ask = ffill(df["bid"]), ffill(df["ask"]); mid = (bid + ask) / 2
        thi = np.where(np.isnan(df["thi"]), -np.inf, df["thi"]); tlo = np.where(np.isnan(df["tlo"]), np.inf, df["tlo"]); z = np.zeros(len(bid))
        for dd in (0.0, 1.0, 2.0, 5.0):
            for touch in (False, True):
                r = mm_sim(bid, ask, thi, tlo, z, dd, 10, 2, INV, dd / INV, 0.0, 3000, touch)
                s = summarize(*r, mid); s.update(sym=sym, day=d, d=dd, touch=touch); rows.append(s)
T = pd.DataFrame(rows); T["per"] = np.where(T.day < "2024", "sel2023", "ver2024")
g = T.groupby(["sym", "d", "touch", "per"]).apply(lambda x: pd.Series(dict(fills_day=x.fills.mean(), capt=np.average(x.capt_bp, weights=x.fills), mo1s=np.average(x.mo_1s, weights=x.fills),
    mo60s=np.average(x.mo_60s, weights=x.fills), gross_bp=x["pnl_gross_$"].sum() / x.ntl.sum() * 1e4)))
g["net_fee1.5"] = g.gross_bp - 1.5; g["net_fee0"] = g.gross_bp; g["net_rebate0.3"] = g.gross_bp + 0.3
print(g.round(2).to_string())
