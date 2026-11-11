"""A10 - base: ricostruisce i 4 sleeve con pesi ed esposizione lorda (stesse funzioni di gerva.strategies.book) e
verifica che coincidano con research/v5/series.parquet. Salva base.pkl. SIMULATO."""
import sys, pickle, warnings; sys.path.insert(0, '/home/user/GERVA-Capital'); warnings.filterwarnings('ignore')
import numpy as np, pandas as pd
from gerva.research.run import Lab
from gerva.strategies import book
from gerva.backtest import Costs, run
HERE = '/home/user/GERVA-Capital/research/v5/v5/a10_sistema'
L = Lab('/home/user/GERVA-Capital'); L.load_daily(); L.load_crypto()
D = pd.read_parquet('/home/user/GERVA-Capital/research/v5/series.parquet')
out = {}
res = book.cr_trend_returns(L.cclose, L.cret); out['CR-TREND'] = res
resx = book.cr_xsmom_returns(L.cclose, L.cdvol, L.cret); out['CR-XSMOM'] = resx
resm = book.ma_trend_returns(L.adj, L.rf); out['MA-TREND'] = resm
H, Lo, C = L.P['high'], L.P['low'], L.P['close']
Weq = book.eq_mr(H, Lo, C); eq = book.eq_mr_returns(H, Lo, C, L.ret, L.rf)
idx = D.index
raw = resx.ret.loc['2018':]; xs = book.xs_scale(raw)
S = pd.DataFrame({'CR-TREND': res.ret.loc['2018':], 'CR-XSMOM': raw * xs, 'EQ-MR': eq.loc['2018':], 'MA-TREND': resm.ret.loc['2018':]}).reindex(idx).fillna(0.0)
print('differenza massima con series.parquet:', (S - D[S.columns]).abs().max().round(12).to_dict())
G = pd.DataFrame({'CR-TREND': res.gross, 'CR-XSMOM': (resx.gross.loc['2018':] * xs), 'EQ-MR': Weq.shift(1).fillna(0).abs().sum(axis=1), 'MA-TREND': resm.gross}).reindex(idx).ffill().fillna(0.0)
TO = pd.DataFrame({'CR-TREND': res.turnover, 'CR-XSMOM': resx.turnover.loc['2018':] * xs, 'EQ-MR': Weq.diff().abs().sum(axis=1), 'MA-TREND': resm.turnover}).reindex(idx).fillna(0.0)
CO = pd.DataFrame({'CR-TREND': res.cost, 'CR-XSMOM': resx.cost.loc['2018':] * xs, 'EQ-MR': Weq.diff().abs().sum(axis=1) * book.INDEX_FEE, 'MA-TREND': resm.cost}).reindex(idx).fillna(0.0)
print('esposizione lorda media per sleeve (2018-04 ->):'); print(G.loc['2018-04':].mean().round(3).to_string())
print('turnover annuo (volte il capitale dello sleeve):'); print((TO.loc['2018-04':].mean() * 365).round(1).to_string())
print('costi di scambio annui per sleeve:'); print((CO.loc['2018-04':].mean() * 365).round(4).to_string())
rf365 = L.rf365.reindex(idx).ffill(); print('RF medio annuo: tot %.3f  scelta %.3f  verifica %.3f' % (rf365.mean() * 365, rf365[:'2022'].mean() * 365, rf365['2023':].mean() * 365))
pickle.dump(dict(S=S, G=G, TO=TO, CO=CO, rf=rf365, Wtrend=res.weights, Wxs=resx.weights, xs=xs, Wma=resm.weights, Weq=Weq,
                 cclose=L.cclose, cret=L.cret, cdvol=L.cdvol, adj=L.adj, ret=L.ret, rfd=L.rf, H=H, Lo=Lo, C=C), open(HERE + '/base.pkl', 'wb'))
