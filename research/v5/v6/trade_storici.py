"""Trade storici simulati con il loro contesto d'ingresso, per il ciclo di automiglioramento (gerva.learn).
Sono i 652 trade del libro a ~11x (stop 1 x ATR, stop mobile, giorni ad alta conviction su BTC, ETH, SOL, 2018-2026) della
ricerca v4, con il contesto calcolato dalla STESSA funzione che usa il ciclo paper (gerva.learn.features.context), sui dati
noti la sera prima dell'ingresso. SIMULATO. Uscita: research/v5/v6/trade_storici.parquet."""
import sys, pickle, warnings; warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/user/GERVA-Capital'); sys.path.insert(0, 'research/v5/v4')
import pandas as pd
import leva_trade_isolato as TR
from gerva.learn.features import context
ALL = pickle.load(open('research/v5/v4/_cache/trades.pkl', 'rb')); X = ALL[('atr1.0', ('alta',), 2.0, 'long')].sort_values('entry').reset_index(drop=True)
bars = {}
for c in TR.B:
    v = TR.B[c]['volume'].groupby(TR.B[c].index.normalize()).sum(); d = TR.D[c].copy(); d['volume'] = v.reindex(d.index); bars[c] = d
fund = {c: TR.fund(c) for c in bars if TR.fund(c) is not None}
rows = []
for _, t in X.iterrows():
    at = pd.Timestamp(t.entry) - pd.Timedelta(days=1)
    b = {k: x for k, x in bars.items() if x.index[0] <= at - pd.Timedelta(days=260)} | {'BTC': bars['BTC']}
    if t.coin not in b: b[t.coin] = bars[t.coin]
    ctx = context(b, t.coin, fund, at=at)
    rows.append(dict(strategy_id='TRADE-11X', symbol=t.coin, entry_time=str(pd.Timestamp(t.entry).date()), exit_time=str(pd.Timestamp(t.exit).date()), entry_price=None, exit_price=None,
                     notional=None, leverage=float(t.L), risk=1.0, pnl=float(t.R), R=float(t.R), exit_reason=str(t.why), commission=0.0, funding=0.0, slippage=0.0, mae=None, mfe=None, source='sim',
                     **{k: v for k, v in ctx.items() if k != 'symbol'}))
D = pd.DataFrame(rows); D.to_parquet('research/v5/v6/trade_storici.parquet')
print(len(D), 'trade;', 'tier all ingresso:', D.tier.value_counts().to_dict()); print(D[['R', 'conviction', 'gq', 'atr_pct', 'atr_rank', 'btc_ret30', 'funding7', 'n_alta', 'ret7']].describe().round(3).to_string())
