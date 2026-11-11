"""A6 - stress del candidato LISTING-SHORT, aritmetica di Kelly, file finali (trades.parquet, returns.parquet), conteggio delle prove."""
import lib; from lib import *
import glob
lib.CLU = '7D'
T = pd.read_parquet(HERE + '/_ls_trades.parquet'); G = pd.read_parquet(HERE + '/_gap_btc.parquet')
yrs = (T.t_dec.max() - T.t_dec.min()).days / 365.25
print('=== LISTING-SHORT (trade tenuti con il limite di 8 aperti)')
def line(lab, x):
    y = (x.t_dec.max() - x.t_dec.min()).days / 365.25; g = x.R.groupby(x.t_dec.dt.floor('7D').values).sum(); t = g.mean() / g.std() * np.sqrt(len(g))
    print(f"  {lab:9s} n={len(x):4d} N/anno={len(x)/y:5.0f} R={x.R.mean():+.3f} sigma_R={x.R.std():.2f} R/sigma={x.R.mean()/x.R.std():+.3f} t(sett.)={t:+.2f} | N*(R/sigma)^2 ingenuo={len(x)/y*(x.R.mean()/x.R.std())**2:.2f} | corretto per il raggruppamento (t^2/anni)={t*t/y:.2f}")
line('tutto', T); line('scelta', T[T.t_dec < SPL]); line('verifica', T[T.t_dec >= SPL]); line('2025-26', T[T.t_dec >= '2025-01-01'])
print('--- stress: slippage sullo stop 100 pb invece di 5 (moneta nuova, strizzata degli short dentro l\'ora)')
st_ = T.why == 'stop'; R2 = T.R - st_ * (0.0095 / T['stop']); print(f"  R medio {R2.mean():+.3f} (verifica {R2[T.t_dec>=SPL].mean():+.3f})")
print('--- stress: i 5 trade migliori di ogni anno tolti')
x = T.sort_values('R').groupby(T.t_dec.dt.year).apply(lambda d: d.iloc[:-5]); print(f"  R medio {x.R.mean():+.3f}")
print('--- stress: funding raddoppiato a sfavore (-0,022 R in piu\')'); print(f"  R medio {T.R.mean()-0.022:+.3f}")
print('--- bootstrap a blocchi settimanali (2000 ricampionamenti): intervallo al 90% di R medio')
g = T.groupby(T.t_dec.dt.floor('7D').values).R.agg(['sum', 'size']); rng = np.random.default_rng(1)
bs = [(lambda s: s['sum'].sum() / s['size'].sum())(g.iloc[rng.integers(0, len(g), len(g))]) for _ in range(2000)]
print(f"  [{np.percentile(bs,5):+.3f}, {np.percentile(bs,95):+.3f}]; probabilita' R<=0: {np.mean(np.array(bs)<=0):.1%}")
print('\n=== GAP-CME BTC (in osservazione)'); lib.CLU = None
print(f"  n={len(G)} N/anno={len(G)/6.8:.0f} R={G.R.mean():+.3f} sigma_R={G.R.std():.2f} R/sigma={G.R.mean()/G.R.std():+.3f} | N*(R/sigma)^2={len(G)/6.8*(G.R.mean()/G.R.std())**2:.2f}")
# --- file finali
cols = ['cand', 'sym', 'entry', 'exit', 'side', 'stop', 'lev', 'R', 'ret', 'why']
TR = pd.concat([T.assign(cand='LISTING-SHORT')[cols], G.assign(cand='GAP-CME-BTC (osservazione)')[cols]]).rename(columns={'stop': 'stop_dist', 'why': 'exit_why'})
TR['why'] = np.where(TR.cand == 'LISTING-SHORT', 'short 24h dopo la quotazione del perp su Binance, stop 15%, 168h', 'apertura CME dom 17:00 CT: mossa del fine settimana >=1%, entro nella direzione, 24h')
TR.to_parquet(HERE + '/trades.parquet')
idx = pd.date_range('2020-01-01', '2026-10-31', freq='D')
RET = pd.DataFrame({'LISTING-SHORT_r0.5%': (T.R * 0.005).groupby(T.exit.dt.normalize().values).sum().reindex(idx).fillna(0.0),
                    'GAP-CME-BTC_r0.5%': (G.R * 0.005).groupby(G.exit.dt.normalize().values).sum().reindex(idx).fillna(0.0)})
RET.to_parquet(HERE + '/returns.parquet'); print('\nscritti trades.parquet', TR.shape, 'e returns.parquet', RET.shape, '(rischio 0,5% del capitale per trade, P&L al giorno di uscita)')
n = 0
for f in sorted(glob.glob(HERE + '/trials_*.json')):
    k = len(json.load(open(f))); n += k; print(f'  {os.path.basename(f):32s} {k}')
print('PROVE TOTALI A6:', n)
