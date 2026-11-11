"""A8 - modelli e walk-forward a finestra crescente con purga ed embargo."""
from lib import *
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from scipy.stats import spearmanr
PURGE = pd.Timedelta(days=7); EMB = pd.Timedelta(days=7)          # etichette lunghe fino a 7 giorni + 7 di embargo
SEL_BLOCKS = pd.date_range('2019-07-01', '2022-07-01', freq='6MS'); VER_BLOCKS = pd.date_range('2023-01-01', '2026-07-01', freq='6MS')
SEL_LAST = pd.Timestamp('2022-12-24')                              # candidati di scelta la cui etichetta non tocca il 2023

def load():
    D = pd.read_parquet(HERE + '/dataset.parquet').reset_index().sort_values(['date', 'coin']).reset_index(drop=True)
    F = [k for k in D.columns if k not in ('coin', 'date', 'sd', 'atr_stop', 'tier', 'score') and not k[:2] in ('R_', 'R2', 'Rd') and not k.startswith(('why_', 'days_'))]
    return D, F

class Clip:
    """Winsorizza ai percentili 1-99 stimati sul training (solo per la logistica)."""
    def fit(self, X, y=None): self.lo = np.nanpercentile(X, 1, axis=0); self.hi = np.nanpercentile(X, 99, axis=0); return self
    def transform(self, X): return np.clip(X, self.lo, self.hi)
    def fit_transform(self, X, y=None): return self.fit(X).transform(X)

def make(cfg):
    k = cfg['kind']
    if k == 'logit':
        return make_pipeline(Clip(), SimpleImputer(strategy='median', add_indicator=True), StandardScaler(), LogisticRegression(C=cfg['C'], max_iter=2000))
    P = dict(max_depth=cfg['depth'], max_iter=cfg['iters'], min_samples_leaf=cfg['leaf'], learning_rate=0.03, l2_regularization=10.0,
             max_features=0.5, max_bins=32, early_stopping=False, random_state=0)
    return HistGradientBoostingClassifier(**P) if k == 'hgbc' else HistGradientBoostingRegressor(**P)

def fit_pred(cfg, Xtr, ytr, rtr, Xte):
    m = make(cfg)
    if cfg['kind'] != 'logit':                       # colonne tutte NaN nel training (dati non ancora esistenti): costanti, ignorate anche in test
        dead = np.isnan(Xtr).all(axis=0)
        if dead.any(): Xtr = Xtr.copy(); Xte = Xte.copy(); Xtr[:, dead] = 0.0; Xte[:, dead] = 0.0
    if cfg['kind'] == 'hgbr': m.fit(Xtr, np.clip(rtr, -1.5, 4.0)); return m.predict(Xte), m
    m.fit(Xtr, ytr); return m.predict_proba(Xte)[:, 1], m

def walk(D, feats, cfg, blocks, rcol='R_L', R=None, keep_models=False):
    """Previsioni fuori campione: per ogni blocco semestrale si stima su tutte le righe con data < inizio - purga - embargo."""
    r = D[rcol].values if R is None else R; X = D[feats].values.astype(float); dts = D['date'].values
    p = np.full(len(D), np.nan); models = {}
    for b in blocks:
        tr = dts < np.datetime64(b - PURGE - EMB); te = (dts >= np.datetime64(b)) & (dts < np.datetime64(b + pd.DateOffset(months=6)))
        if te.sum() == 0 or tr.sum() < 300: continue
        p[te], m = fit_pred(cfg, X[tr], (r[tr] > 0).astype(int), r[tr], X[te])
        if keep_models: models[b] = m
    return (p, models) if keep_models else p

def block_ic(D, p, r, blocks, last=None):
    """IC di Spearman tra previsione e R, per blocco semestrale (lista)."""
    out = []
    for b in blocks:
        m = (D['date'] >= b) & (D['date'] < b + pd.DateOffset(months=6)) & np.isfinite(p)
        if last is not None: m &= D['date'] <= last
        if m.sum() > 30: out.append(spearmanr(p[m.values], r[m.values])[0])
    return np.array(out)
def top_minus_all(p, r, q=0.8):
    ok = np.isfinite(p); p = p[ok]; r = r[ok]; return r[p >= np.quantile(p, q)].mean() - r.mean()
