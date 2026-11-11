"""B4 - attrezzi comuni. Tutto SIMULATO su dati reali (settle CFE, indici CBOE/Yahoo)."""
import pickle, json, os, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
B = pickle.load(open(os.path.join(HERE, "base.pkl"), "rb"))
F, IX, ETN = B["fut"], B["ix"], B["etn"]
SEL_END, VER_START = "2022-12-31", "2023-01-01"
RF = (IX.IRX.ffill() / 100 / 252).reindex(F.index).ffill().fillna(0)
EVENTS = {"feb18": ("2018-02-02", "2018-02-09"), "ago15": ("2015-08-20", "2015-08-26"), "mar20": ("2020-02-24", "2020-03-18"), "ago24": ("2024-08-01", "2024-08-06")}
C_FUT = 0.0020      # per lato, sul nozionale: mezzo spread (0,025 punti su ~18) + commissioni e fee CFE su VXM
ROLL_D = 2 * C_FUT / 21   # costo di roll giornaliero di una posizione a scadenza costante (una gamba e mezza al mese ~ 2 lati)
TRIALS = {}
def count(k, n=1): TRIALS[k] = TRIALS.get(k, 0) + n
def save_trials(name): json.dump(TRIALS, open(os.path.join(HERE, name), "w"), indent=1)

def sharpe(r): r = r.dropna(); return np.nan if r.std() == 0 or len(r) < 20 else r.mean() / r.std() * np.sqrt(252)
def cagr(r): r = r.dropna(); return np.nan if len(r) < 20 or (1 + r).min() <= 0 else (1 + r).prod() ** (252 / len(r)) - 1
def maxdd(r): e = (1 + r.fillna(0)).cumprod(); return (e / e.cummax() - 1).min()
def worst_week(r): return ((1 + r.fillna(0)).rolling(5).apply(np.prod, raw=True) - 1).min()
def tstat(r): r = r.dropna(); return r.mean() / r.std() * np.sqrt(len(r))
def ev(r, k): a, b = EVENTS[k]; x = r.loc[a:b]; return (1 + x.fillna(0)).prod() - 1 if len(x) else np.nan
def split(r): return {"tutto": r, "scelta": r.loc[:SEL_END], "verifica": r.loc[VER_START:]}
def row(name, r, extra=""):
    p = split(r)
    return (f"{name:44s} Sh {sharpe(p['tutto']):5.2f}/{sharpe(p['scelta']):5.2f}/{sharpe(p['verifica']):5.2f}  CAGR {cagr(p['tutto']):+6.1%}/{cagr(p['scelta']):+6.1%}/{cagr(p['verifica']):+6.1%}"
            f"  DD {maxdd(r):+6.1%}  g.peggiore {r.min():+6.1%}  sett. {worst_week(r):+6.1%}  feb18 {ev(r,'feb18'):+6.1%} ago15 {ev(r,'ago15'):+6.1%} mar20 {ev(r,'mar20'):+6.1%} ago24 {ev(r,'ago24'):+6.1%} {extra}")
HEAD = f"{'':44s} Sharpe tutto/scelta/verifica   CAGR tutto/scelta/verifica   maxDD   giorno peggiore   settimana peggiore   finestre di crisi"
def kelly(r, lmax=20.0):
    """leva che massimizza la crescita geometrica sul campione; rendimento mensile composto a L* e L*/2."""
    r = r.dropna().values; best = (0.0, 0.0)
    for L in np.arange(0.05, lmax + 1e-9, 0.05):
        x = 1 + L * r
        if x.min() <= 0.02: break
        g = np.log(x).mean()
        if g > best[1]: best = (L, g)
    L = best[0]; m = lambda l: np.exp(21 * np.log(1 + l * r).mean()) - 1
    return L, m(L) if L else 0.0, m(L / 2) if L else 0.0
def boot_p50(r, L, shift=0.0, n=4000, months=36, seed=7):
    """P(drawdown >= 50% entro 3 anni) con ricampionamento a blocchi mensili; shift = quota del rendimento medio tolta (0,5 = meta' vantaggio)."""
    r = r.dropna(); r = r - shift * r.mean()
    blocks = [g.values for _, g in r.groupby([r.index.year, r.index.month])]
    rng = np.random.default_rng(seed); hit = 0; fin = []
    for _ in range(n):
        x = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), months)])
        e = np.cumprod(np.maximum(1 + L * x, 1e-9)); dd = (e / np.maximum.accumulate(e) - 1).min()
        hit += dd <= -0.5; fin.append(e[-1])
    return hit / n, np.median(fin) ** (1 / months) - 1
def fund():
    f = pd.read_parquet("/home/user/GERVA-Capital/research/v5/v5/a10_sistema/returns.parquet")
    return f[["B_cassa_in_tbill", "C1_mtm_limiti", "C3_mtm_limiti_debito_reale"]]
def to_cal(r):
    """rendimenti di borsa -> indice di calendario (0 nei giorni senza borsa)."""
    r = r.dropna(); return r.reindex(pd.date_range(r.index[0], r.index[-1], freq="D")).fillna(0.0)
def corr_fund(r):
    f = fund(); c = to_cal(r).reindex(f.index).fillna(0); out = {}
    for k in f:
        m = pd.concat([(1 + c).resample("ME").prod() - 1, (1 + f[k]).resample("ME").prod() - 1], axis=1).dropna()
        out[k] = (np.corrcoef(c, f[k])[0, 1], m.corr().iloc[0, 1])
    return out
def apply(sig, r, lag=1, cost=C_FUT, roll=ROLL_D):
    """sig = posizione desiderata decisa alla chiusura del giorno d (in unita' di nozionale/capitale).
    lag=0: eseguita alla stessa chiusura (ottimistico); lag=1 (base): al settle del giorno dopo; lag=2: un giorno in piu'."""
    p = sig.shift(1 + lag).reindex(r.index).fillna(0)
    return (p * r - cost * p.diff().abs().fillna(0) - roll * p.abs()).where(r.notna())
