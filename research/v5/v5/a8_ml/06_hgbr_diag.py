"""A8 - 06: diagnosi del modello SECONDARIO (HGBR, regressione su R) - l'unico con un segnale in verifica.
Domanda: prevede la DIREZIONE o soltanto l'AMPIEZZA (dispersione di R)? Con perdita limitata a ~-1R, piu' dispersione = piu' R medio.
Nessuna nuova variante di trading: solo descrizione delle previsioni gia' congelate."""
import json
from ml import *
from sklearn.inspection import permutation_importance
pd.set_option('display.width', 250)
D, F = load(); FZ = json.load(open(HERE + '/frozen.json')); CFG = FZ['fam_best']['HGBR']; ALLB = list(SEL_BLOCKS) + list(VER_BLOCKS)
P = pd.read_parquet(HERE + '/preds.parquet'); pr = P['HGBR'].values; r = D['R_L'].values; rs = D['R_S'].values
for lab, m in (('scelta', (D.date <= SEL_LAST).values & np.isfinite(pr)), ('verifica', (D.date >= SPL).values & np.isfinite(pr))):
    q = pd.qcut(pd.Series(pr[m]).rank(method='first'), 5, labels=False).values + 1
    x = pd.DataFrame(dict(q=q, ER=pr[m], R=r[m], RS=rs[m], absR=np.abs(r[m]), big=(r[m] > 3), alta=(D.tier[m] == 'alta').values, atr_pct=D.atr_pct[m].values, sd=D.sd[m].values))
    g = x.groupby('q').agg(n=('R', 'size'), ER_prev=('ER', 'mean'), R_long=('R', 'mean'), sd_R=('R', 'std'), hit=('R', lambda v: (v > 0).mean()), quota_R_gt3=('big', 'mean'), R_short=('RS', 'mean'), quota_alta=('alta', 'mean'), atr_pct=('atr_pct', 'mean'), stop_medio=('sd', 'mean'))
    print(f'-- {lab}: quintili di E[R] previsto (HGBR) --'); print(g.round(3).to_string())
    print(f"   IC(E[R], R long) {spearmanr(pr[m], r[m])[0]:+.3f} | IC(E[R], |R|) {spearmanr(pr[m], np.abs(r[m]))[0]:+.3f} | IC(E[R], R short) {spearmanr(pr[m], rs[m])[0]:+.3f} | IC(E[R], R long + R short) {spearmanr(pr[m], r[m] + rs[m])[0]:+.3f}")
_, models = walk(D, F, CFG, ALLB, keep_models=True); X = D[F].values.astype(float); dts = D['date'].values; imp = {}
for b, mdl in models.items():
    te = (dts >= np.datetime64(b)) & (dts < np.datetime64(b + pd.DateOffset(months=6))); tr = dts < np.datetime64(b - PURGE - EMB)
    Xte = X[te].copy(); Xte[:, np.isnan(X[tr]).all(axis=0)] = 0.0
    imp[str(b.date())] = permutation_importance(mdl, Xte, np.clip(r[te], -1.5, 4), scoring=lambda e, a, y: spearmanr(e.predict(a), y)[0], n_repeats=10, random_state=0).importances_mean
I = pd.DataFrame(imp, index=F); cs = I.corr(method='spearman').values; off = cs[np.triu_indices_from(cs, 1)]
print(f'\nHGBR: correlazione di rango media dell\'importanza tra fold {off.mean():+.3f}; prime 10 feature (importanza media sul test, quota di fold positiva):')
print(pd.DataFrame(dict(imp=I.mean(axis=1), quota_pos=(I > 0).mean(axis=1))).sort_values('imp', ascending=False).head(10).round(4).T.to_string())
