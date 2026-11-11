"""A5 - il flusso scelto (regole fissate sul solo periodo di scelta <=2022: t_scelta >= 2, positivo a costi doppi e con ritardo)
e che cosa aggiunge al libro dei trade cripto. SIMULATO.
Flusso:
  MR   : IBS<0.2 alla chiusura con VIX>=20 -> long all'apertura successiva su SPY, QQQ, IWM; stop 1 ATR(14); uscita all'apertura
         dopo la prima chiusura con IBS>0.7, o dopo 5 sedute. Rischio diviso tra gli indici entrati lo stesso giorno.
  TOM  : long alla chiusura dell'ultimo giorno di borsa del mese su SPY e QQQ, uscita alla chiusura del 3o giorno; stop 2 ATR.
  FOMC : long alla chiusura della vigilia dell'annuncio su SPY e QQQ, uscita alla chiusura del giorno dell'annuncio; stop 1 ATR.
  TREND: QQQ, chiusura sopra il massimo di 55 sedute -> long; stop 2 ATR, inseguimento 3 ATR dalla miglior chiusura.
  (fuori soglia, riportato a parte: TREND oro GLD N55 long, t_scelta 1.84)"""
import sys, pickle; sys.path.insert(0, '/home/user/GERVA-Capital/research/v5/v5/a5_indici')
from lab import *
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
IDX = ['SPY', 'QQQ', 'IWM']; D = {s: load(s) for s in IDX + ['GLD']}; A = {s: atr(D[s]) / D[s].close for s in D}
vix = pd.read_parquet(ROOT + '/data_cache/yahoo_1d_^VIX.parquet').close
fomc = pd.to_datetime(pd.read_csv(HERE + '/fomc_dates.csv').date)

def build(cost_mult=1.0, delay=False):
    P = {}
    eo = 'open2' if delay else 'open'; ec = 'open' if delay else 'close'
    for s in IDX:
        d = D[s]; x = ibs(d); v = vix.reindex(d.index)
        P[f'MR|{s}'] = sim(s, d, (x < 0.2) & (v >= 20), 1, A[s], entry=eo, exit_sig=x > 0.7, maxhold=5, cost_mult=cost_mult, name='MR')
    for s in ['SPY', 'QQQ']:
        d = D[s]; m = pd.Series(d.index.to_period('M'), index=d.index)
        pe = m.groupby(m).cumcount(ascending=False); ps = m.groupby(m).cumcount()
        P[f'TOM|{s}'] = sim(s, d, pe == 0, 1, 2 * A[s], entry=ec, exit_sig=ps == 2, exit_at='close', cost_mult=cost_mult, name='TOM')
        isf = pd.Series(d.index.isin(fomc), index=d.index)
        P[f'FOMC|{s}'] = sim(s, d, isf.shift(-1).fillna(False), 1, A[s], entry=ec, maxhold=1, exit_at='close', cost_mult=cost_mult, name='FOMC')
    for s in ['QQQ', 'GLD']:
        d = D[s]
        P[f'TREND|{s}'] = sim(s, d, d.close > d.high.rolling(55).max().shift(1), 1, 2 * A[s], entry=eo,
                             exit_sig=d.close < d.low.rolling(27).min().shift(1), trail=1.5, cost_mult=cost_mult, name='TREND')
    return P

def cluster(T):
    """Trade dello stesso setup entrati lo stesso giorno = un trade solo, rischio diviso in parti uguali."""
    g = T.groupby(['setup', 'entry'])
    return pd.DataFrame({'symbol': g.symbol.agg('+'.join), 'exit': g.exit.max(), 'side': 1, 'stop': g.stop.mean(), 'lev': g.lev.mean(),
                         'R': g.R.mean(), 'ret': g.ret.mean(), 'why': g.why.first(), 'days': g.days.max(), 'k': g.size()}).reset_index()

P = build(); P2 = build(2.0); P3 = build(delay=True)
core = [k for k in P if k != 'TREND|GLD']
def stream(P, keys): return cluster(pd.concat([P[k] for k in keys], ignore_index=True)).sort_values('entry').reset_index(drop=True)
S = stream(P, core); S2 = stream(P2, core); S3 = stream(P3, core)
S = S[S.entry >= '1994-01-01']; S2 = S2[S2.entry >= '1994-01-01']; S3 = S3[S3.entry >= '1994-01-01']
rows = []
for fam in ['MR', 'TOM', 'FOMC', 'TREND']:
    r = stats(S[S.setup == fam], fam + ' (raggruppato)'); r['R_costi2'] = S2[S2.setup == fam].R.mean(); r['R_ritardo'] = S3[S3.setup == fam].R.mean(); rows.append(r)
r = stats(S, 'FLUSSO A5 (MR+TOM+FOMC+TREND QQQ)'); r['R_costi2'] = S2.R.mean(); r['R_ritardo'] = S3.R.mean(); rows.append(r)
G = P['TREND|GLD']; r = stats(G, 'fuori soglia: TREND oro N55 long'); r['R_costi2'] = P2['TREND|GLD'].R.mean(); r['R_ritardo'] = P3['TREND|GLD'].R.mean(); rows.append(r)
Sx = S[S.entry >= '2018-04-01']; r = stats(Sx, 'FLUSSO A5, solo dal 2018-04 (finestra del libro cripto)'); rows.append(r)
T = pd.DataFrame(rows).set_index('setup')
cols = ['n', 'n_anno', 'meanR', 'sdR', 't', 'hit', 'q', 'NQ2', 'R_sel', 't_sel', 'q_sel', 'NQ2_sel', 'n_sel', 'R_ver', 't_ver', 'q_ver', 'NQ2_ver', 'n_ver', 'R_costi2', 'R_ritardo', 'lev', 'stop_pct']
print(T[cols].round(3).T.to_string())
print('\n--- per anno (flusso A5, R) ---')
py = per_year(S); py['MR'] = S[S.setup == 'MR'].groupby(S.entry.dt.year).R.sum(); py['TOM'] = S[S.setup == 'TOM'].groupby(S.entry.dt.year).R.sum()
py['FOMC'] = S[S.setup == 'FOMC'].groupby(S.entry.dt.year).R.sum(); py['TREND'] = S[S.setup == 'TREND'].groupby(S.entry.dt.year).R.sum()
print(py.round(2).fillna(0).to_string())
for a, b in (('1994', '2002'), ('2003', '2012'), ('2013', '2022'), ('2023', '2026')):
    x = S[(S.entry >= a) & (S.entry <= b + '-12-31')]
    print(f'{a}-{b}: n {len(x)}  R medio {x.R.mean():+.3f}  t {x.R.mean()/x.R.std()*np.sqrt(len(x)):+.2f}  q {x.R.mean()/x.R.std():+.3f}')
print('uscite:', S.why.value_counts().to_dict(), ' R minimo %.2f  massimo %.2f' % (S.R.min(), S.R.max()))

# ------------------- confronto con il libro cripto e con il libro giornaliero -------------------
F = pd.read_parquet(ROOT + '/research/v5/v4/fondo_serie.parquet')
ALL = pickle.load(open(ROOT + '/research/v5/v4/_cache/trades.pkl', 'rb')); C = ALL[('atr1.0', ('alta',), 2.0, 'long')].copy()
C['entry'] = pd.to_datetime(C.entry); C['exit'] = pd.to_datetime(C.exit)
pa = daily_pnl(S, 0.01, start=str(F.index[0].date()), end=str(F.index[-1].date()))
mm = lambda x: (1 + x).resample('ME').prod() - 1
M = pd.DataFrame({'a5': pa.resample('ME').sum(), 'trade11': mm(F.trade11), 'new': mm(F.new), 'trade30': mm(F.trade30)})
print('\n--- correlazione dei P&L MENSILI, 2018-04 -> 2026-10 (flusso A5 a rischio 1% per trade) ---')
for nm, sl in (('intero', slice(None, None)), ('scelta', slice(None, SEL_END)), ('verifica', slice(VER_START, None))):
    m = M.loc[sl]; print(f'{nm:9s} n mesi {len(m):3d}  corr(a5, trade11) {m.a5.corr(m.trade11):+.2f}   corr(a5, new) {m.a5.corr(m.new):+.2f}   corr(a5, trade30) {m.a5.corr(m.trade30):+.2f}')
Mall = pd.DataFrame({'a5': daily_pnl(S, 0.01).resample('ME').sum()})
print('mesi A5 dal 1994: media %.2f%%  dev.st %.2f%%  Sharpe annuo %.2f  mesi negativi %.0f%%  mese peggiore %.1f%%  migliore %.1f%%' % (
    Mall.a5.mean() * 100, Mall.a5.std() * 100, Mall.a5.mean() / Mall.a5.std() * np.sqrt(12), (Mall.a5 < 0).mean() * 100, Mall.a5.min() * 100, Mall.a5.max() * 100))

print('\n--- aritmetica N*(Rmedio/sigma)^2: cripto, A5, insieme ---')
def nq(x, y0, y1):
    x = x[(x.entry >= y0) & (x.entry <= y1)]; yrs = (pd.Timestamp(y1) - pd.Timestamp(y0)).days / 365.25
    q = x.R.mean() / x.R.std(); return len(x) / yrs, x.R.mean(), x.R.std(), q, len(x) / yrs * q * abs(q)
out = []
for nm, y0, y1 in (('intero 2018-04/2026-10', '2018-04-01', '2026-10-31'), ('scelta 2018-04/2022-12', '2018-04-01', '2022-12-31'), ('verifica 2023-01/2026-10', '2023-01-01', '2026-10-31')):
    c = nq(C, y0, y1); a = nq(S, y0, y1); both = pd.concat([C[['entry', 'R']], S[['entry', 'R']]]); b = nq(both, y0, y1)
    # Kelly per flusso su P&L mensili: Sharpe annuo^2 dei due flussi e della combinazione ottima (tiene conto della correlazione)
    m = M.loc[y0:y1, ['trade11', 'a5']]; mu = m.mean().values * 12; cov = m.cov().values * 12
    s2 = mu @ np.linalg.solve(cov, mu); sc = mu[0] ** 2 / cov[0, 0]; sa = mu[1] ** 2 / cov[1, 1] * np.sign(mu[1])
    out.append(dict(periodo=nm, N_cripto=c[0], q_cripto=c[3], NQ2_cripto=c[4], N_a5=a[0], R_a5=a[1], q_a5=a[3], NQ2_a5=a[4],
                    N_insieme=b[0], q_insieme=b[3], NQ2_unico_libro=b[4], NQ2_somma=c[4] + a[4],
                    SR2_cripto_mensile=sc, SR2_a5_mensile=sa, SR2_combinazione_ottima=s2))
print(pd.DataFrame(out).set_index('periodo').round(3).T.to_string())
a = nq(S, '1994-01-01', '2026-11-09'); print('A5 dal 1994: N/anno %.1f  Rmedio %.3f  sigma %.2f  q %.3f  N*q^2 %.2f   -> crescita log a Kelly pieno %.2f/anno = %.1f%%/mese; a mezzo Kelly %.1f%%/mese' % (
    a[0], a[1], a[2], a[3], a[4], a[4] / 2, (np.exp(a[4] / 2 / 12) - 1) * 100, (np.exp(a[4] * 0.375 / 12) - 1) * 100))
print('Kelly r* = Rmedio/sigma^2 = %.3f (rischio per trade); obiettivo 30%%/mese richiede N*q^2 = 6.3' % (a[1] / a[2] ** 2))

# ------------------- salvataggi -------------------
S.assign(leverage=S.lev, stop_distance=S.stop)[['entry', 'exit', 'symbol', 'side', 'stop_distance', 'leverage', 'R', 'why', 'setup', 'days']].to_parquet(HERE + '/trades.parquet')
ret = pd.DataFrame({'A5_flusso_r1%': daily_pnl(S, 0.01, '1994-01-01'), 'A5_MR_r1%': daily_pnl(S[S.setup == 'MR'], 0.01, '1994-01-01'),
                    'A5_TOM_r1%': daily_pnl(S[S.setup == 'TOM'], 0.01, '1994-01-01'), 'A5_FOMC_r1%': daily_pnl(S[S.setup == 'FOMC'], 0.01, '1994-01-01'),
                    'A5_TRENDQQQ_r1%': daily_pnl(S[S.setup == 'TREND'], 0.01, '1994-01-01'), 'fuori_soglia_TRENDGLD_r1%': daily_pnl(G, 0.01, '1994-01-01')})
ret.to_parquet(HERE + '/returns.parquet')
