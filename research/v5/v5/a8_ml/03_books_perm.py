"""A8 - 03: (A) libri ESEGUIBILI (una posizione per coin, non sovrapposti) filtrati dal modello contro la regola attuale;
(B) i trade veri del libro v4 ordinati per probabilita' prevista; (C) test di permutazione (etichette mescolate entro il mese;
spostamento circolare); (D) stabilita' dell'importanza delle feature tra i fold."""
import json, pickle, time, sys
from ml import *
from sklearn.inspection import permutation_importance
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 200)
D, F = load(); r = D['R_L'].values; FZ = json.load(open(HERE + '/frozen.json')); PRIM = FZ['primary']; PF = FZ['primary_fam']
P = pd.read_parquet(HERE + '/preds.parquet'); pp = P[PF].values; ALLB = list(SEL_BLOCKS) + list(VER_BLOCKS)
dt = Data(); SIMS = {c: Sim(dt, c) for c in COINS}; ntr = 0

def exante_thr(p, q):
    """Soglia nota in anticipo: quantile q delle previsioni OOS dei blocchi precedenti (finestra crescente). Primo blocco: nessun trade."""
    thr = np.full(len(D), np.nan); dts = D['date'].values
    for b in ALLB[1:]:
        prev = np.isfinite(p) & (dts < np.datetime64(b)); te = (dts >= np.datetime64(b)) & (dts < np.datetime64(b + pd.DateOffset(months=6)))
        thr[te] = np.quantile(p[prev], q)
    return thr
def book(gate, conv_exit=False, cm=1.0, delay=0, t0='2020-01-01'):
    """gate: vettore booleano allineato a D. Entra se flat e gate; stop 1xATR, trailing 2x, max 7 giorni; opzionale uscita 'bassa' (v4)."""
    out = []
    for c in COINS:
        s = SIMS[c]; d = D[D.coin == c]; g = pd.Series(gate[d.index.values], index=d['date'].values); sdv = pd.Series(d['sd'].values, index=d['date'].values)
        tier = pd.Series(d['tier'].values, index=d['date'].values).reindex(pd.DatetimeIndex(s.days)).values
        gi = g.reindex(pd.DatetimeIndex(s.days)).fillna(False).values; sd_ = sdv.reindex(pd.DatetimeIndex(s.days)).values; i = int(np.searchsorted(s.days, np.datetime64(t0)))
        while i < s.n - 8:
            if not gi[i]: i += 1; continue
            j = i + 1
            while not (j - i >= 7 or (conv_exit and tier[j] == 'bassa')): j += 1
            t = s.trade(i, 1, float(sd_[i]), j, cm=cm, delay=delay); out.append(t); i = t['j'] + 1
    return pd.DataFrame(out)
def line(lab, T):
    o = dict(libro=lab)
    for nm, x in (('sel', T[T.entry < SPL]), ('ver', T[T.entry >= SPL])):
        if len(x) < 5: continue
        y = (x.entry.max() - x.entry.min()).days / 365.25; s = rstats(x.R); o.update({f'n_{nm}': s['n'], f'anno_{nm}': s['n'] / y, f'R_{nm}': s['R'], f'sd_{nm}': s['sd'], f'ir_{nm}': s['ir'], f't_{nm}': s['t'], f'hit_{nm}': s['hit'], f'NIR2_{nm}': s['n'] / y * s['ir'] ** 2 * np.sign(s['ir'])})
    return o

print('== A. Libri eseguibili, 2020-01 -> 2026-10 (sel = 2020-2022, ver = 2023-2026). R netto; NIR2 = N/anno x (R/sd)^2 ==')
alta = (D.tier == 'alta').values; ok = np.isfinite(pp); BK = {}
BK['v4: alta + uscita bassa'] = dict(gate=alta, conv_exit=True); BK['alta (trade generico)'] = dict(gate=alta); BK['sempre long (nessun filtro)'] = dict(gate=np.ones(len(D), bool))
BK['NON alta (media+bassa)'] = dict(gate=~alta)
for q in (0.5, 0.7, 0.8, 0.9): BK[f'modello p>=q{q:.1f} ex-ante'] = dict(gate=ok & (pp >= exante_thr(pp, q)))
BK['alta E modello p>=mediana'] = dict(gate=alta & ok & (pp >= exante_thr(pp, 0.5))); BK['alta E modello p>=mediana + uscita bassa'] = dict(gate=alta & ok & (pp >= exante_thr(pp, 0.5)), conv_exit=True)
BK['alta E modello p<mediana (controprova)'] = dict(gate=alta & ok & (pp < exante_thr(pp, 0.5)))
g9 = ok & (pp >= exante_thr(pp, 0.9)); BK['alta OPPURE modello p>=q0.9'] = dict(gate=alta | g9)
pr = P['HGBR'].values; BK['[secondario] HGBR E[R]>=q0.8 ex-ante'] = dict(gate=np.isfinite(pr) & (pr >= exante_thr(pr, 0.8)))
rows = []; TR = {}
for k, kw in BK.items(): TR[k] = book(**kw); rows.append(line(k, TR[k])); ntr += 1
A = pd.DataFrame(rows); print(A.round(3).to_string(index=False))
v_ = (D.date >= SPL).values
print(f"giorni-candidato in verifica: alta {alta[v_].sum()}, modello q0.9 {g9[v_].sum()} (di cui alta: {(g9 & alta)[v_].sum()}), modello q0.8 {BK['modello p>=q0.8 ex-ante']['gate'][v_].sum()} (di cui alta: {(BK['modello p>=q0.8 ex-ante']['gate'] & alta)[v_].sum()})")
print('\n-- robustezza in VERIFICA: costi x2, ritardo +1 ora (12 barre 5m), ritardo +1 giorno --'); rows = []
for k in ('v4: alta + uscita bassa', 'sempre long (nessun filtro)', 'modello p>=q0.8 ex-ante', 'modello p>=q0.9 ex-ante', 'alta E modello p>=mediana', '[secondario] HGBR E[R]>=q0.8 ex-ante'):
    kw = BK[k]; v = lambda T: rstats(T[T.entry >= SPL].R); 
    a, b, c_ = v(book(**kw, cm=2.0)), v(book(**kw, delay=12)), v(book(**{**kw, 'gate': np.concatenate((np.zeros(0, bool), pd.Series(kw['gate']).groupby(D.coin).shift(1).fillna(False).values))}))
    rows.append(dict(libro=k, R_base=v(TR[k])['R'], R_costi2=a['R'], t_costi2=a['t'], R_rit1h=b['R'], t_rit1h=b['t'], R_rit1g=c_['R'], t_rit1g=c_['t']))
print(pd.DataFrame(rows).round(3).to_string(index=False))
print('\n-- per anno (R medio / n): --'); rows = []
for k in ('v4: alta + uscita bassa', 'sempre long (nessun filtro)', 'modello p>=q0.8 ex-ante', 'modello p>=q0.9 ex-ante', 'alta E modello p>=mediana', '[secondario] HGBR E[R]>=q0.8 ex-ante'):
    T = TR[k]; g = T.groupby(T.entry.dt.year).R.agg(['mean', 'size']); rows.append(dict(libro=k, **{str(y): f"{g.loc[y, 'mean']:+.2f}/{int(g.loc[y, 'size'])}" for y in g.index}))
print(pd.DataFrame(rows).to_string(index=False))
keep = TR['modello p>=q0.8 ex-ante'].drop(columns='j').assign(why_entry='A8 HGBC p>=q0.8 ex-ante (NON raccomandato: nessun vantaggio in verifica)')
keep.rename(columns=dict(coin='symbol', s='stop_dist', L='leverage')).to_parquet(HERE + '/trades.parquet')

print('\n== B. I trade veri del libro v4 (1xATR, alta, trail 2) ordinati per probabilita prevista alla data d\'ingresso ==')
ref = pickle.load(open(ROOT + '/research/v5/v4/_cache/trades.pkl', 'rb'))[('atr1.0', ('alta',), 2.0, 'long')]
ref = ref.merge(pd.DataFrame(dict(coin=D.coin, entry=D.date, p=pp, pr=pr)), on=['coin', 'entry'], how='left').dropna(subset=['p'])
for lab, x in (('scelta OOS 2019H2-2022', ref[ref.entry < SPL]), ('verifica', ref[ref.entry >= SPL])):
    x = x.copy(); x['terzile'] = pd.qcut(x.p.rank(method='first'), 3, labels=['basso', 'medio', 'alto'])
    g = x.groupby('terzile').R.agg(n='size', R='mean', sd='std', hit=lambda v: (v > 0).mean()); g['t'] = g.R / g.sd * np.sqrt(g.n)
    print(lab, f"(n={len(x)}, IC p-R = {spearmanr(x.p, x.R)[0]:+.3f}, IC E[R]-R = {spearmanr(x.pr, x.R)[0]:+.3f})"); print(g.round(3).to_string())

print('\n== D. Stabilita dell\'importanza delle feature (modello primario; importanza per permutazione sul blocco di TEST, metrica AUC) ==')
_, models = walk(D, F, PRIM, ALLB, keep_models=True); imp = {}; X = D[F].values.astype(float); dts = D['date'].values
for b, m in models.items():
    te = (dts >= np.datetime64(b)) & (dts < np.datetime64(b + pd.DateOffset(months=6))); tr = dts < np.datetime64(b - PURGE - EMB)
    Xte = X[te].copy(); dead = np.isnan(X[tr]).all(axis=0); Xte[:, dead] = 0.0
    pi = permutation_importance(m, Xte, (r[te] > 0).astype(int), scoring='roc_auc', n_repeats=10, random_state=0); imp[str(b.date())] = pi.importances_mean
I = pd.DataFrame(imp, index=F); rk = I.rank(ascending=False)
cs = I.corr(method='spearman').values; off = cs[np.triu_indices_from(cs, 1)]
print(f'correlazione di rango media dell\'importanza tra coppie di fold: {off.mean():+.3f} (min {off.min():+.2f}, max {off.max():+.2f}); fold consecutivi: {np.mean([cs[i, i+1] for i in range(len(cs)-1)]):+.3f}')
top = pd.DataFrame(dict(imp_media=I.mean(axis=1), quota_fold_positiva=(I > 0).mean(axis=1), quota_fold_top10=(rk <= 10).mean(axis=1), t=I.mean(axis=1) / I.std(axis=1, ddof=1) * np.sqrt(I.shape[1])))
print(top.sort_values('imp_media', ascending=False).head(12).round(4).to_string()); print('feature con importanza positiva in >=80% dei fold:', list(top.index[top.quota_fold_positiva >= 0.8]))
# importanza "interna" (frequenza di split non disponibile in HGB): confronto con la logistica a 12 segnali -> stabilita' dei segni
cfg12 = FZ['fam_best']['LOGIT12']; _, m12 = walk(D, SIG, cfg12, ALLB, keep_models=True)
C = pd.DataFrame({str(b.date()): m[-1].coef_[0][:len(SIG)] for b, m in m12.items()}, index=SIG)
print('\nlogistica sui 12 segnali: coefficiente medio (standardizzato) e quota di fold con segno positivo'); print(pd.DataFrame(dict(coef=C.mean(axis=1), quota_pos=(C > 0).mean(axis=1))).round(3).T.to_string())

print('\n== C. Test di permutazione (modello primario, pipeline completa ristimata a ogni permutazione) ==')
NP = int(sys.argv[1]) if len(sys.argv) > 1 else 300; rng = np.random.default_rng(42); mon = D['date'].dt.to_period('M').astype(str).values
sel = (D['date'] <= SEL_LAST).values; ver = (D['date'] >= SPL).values
dl = D['days_L'].values; CI = {c: np.where((D.coin == c).values)[0] for c in COINS}; CFGR = FZ['fam_best']['HGBR']
def fast_book(p, R, dd, q):
    """Libro non sovrapposto calcolato dalle righe del dataset (prossimo ingresso = ingresso + durata). Ritorna R dei trade in verifica."""
    g = np.isfinite(p) & (p >= exante_thr(p, q)); out = []
    for c in COINS:
        ix = CI[c]; nxt = -1
        for n_, k in enumerate(ix):
            if n_ < nxt or not g[k]: continue
            if ver[k]: out.append(R[k])
            nxt = n_ + int(dd[k])
    return np.array(out)
def stat(p, R, dd, pr_):
    o = {}
    for lab, m, bl in (('sel', sel, SEL_BLOCKS), ('ver', ver, VER_BLOCKS)):
        mm = m & np.isfinite(p); o[f'ic_{lab}'] = block_ic(D, np.where(m, p, np.nan), R, bl).mean(); o[f'top20_{lab}'] = top_minus_all(p[mm], R[mm], 0.8); o[f'top10_{lab}'] = top_minus_all(p[mm], R[mm], 0.9)
    for q in (0.8, 0.9): x = fast_book(p, R, dd, q); o[f'libro_q{q}_ver_R'] = x.mean() if len(x) > 5 else np.nan; o[f'libro_q{q}_ver_t'] = x.mean() / x.std(ddof=1) * np.sqrt(len(x)) if len(x) > 5 else np.nan
    mm = ver & np.isfinite(pr_); o['HGBR_top20_ver'] = top_minus_all(pr_[mm], R[mm], 0.8); x = fast_book(pr_, R, dd, 0.8); o['HGBR_libro_q0.8_ver_R'] = x.mean(); o['HGBR_libro_q0.8_ver_t'] = x.mean() / x.std(ddof=1) * np.sqrt(len(x))
    return o
real = stat(pp, r, dl, pr); t0 = time.time()
def perm_month():
    ix = np.arange(len(D))
    for m in np.unique(mon): w = np.where(mon == m)[0]; ix[w] = rng.permutation(w)
    return r[ix], dl[ix]
udates = np.sort(D['date'].unique())
def perm_shift():
    """Spostamento circolare delle etichette nel tempo (stesso scarto per tutti i coin): conserva l'autocorrelazione di etichette e feature."""
    k = int(rng.integers(60, len(udates) - 60)); mp = dict(zip(udates, np.roll(udates, k)))
    src = pd.Series(np.arange(len(D)), index=pd.MultiIndex.from_arrays([D.coin, D.date])); key = pd.MultiIndex.from_arrays([D.coin, D.date.map(mp)])
    ix = src.reindex(key).values; na = np.isnan(ix); ix[na] = rng.integers(0, len(D), na.sum()); ix = ix.astype(int); return r[ix], dl[ix]
for nm, fn in (('mescolate entro il mese', perm_month), ('spostamento circolare (>=60 giorni)', perm_shift)):
    S = []
    for _ in range(NP): R, dd = fn(); S.append(stat(walk(D, F, PRIM, ALLB, R=R), R, dd, walk(D, F, CFGR, ALLB, R=R)))
    S = pd.DataFrame(S); print(f'\n-- nullo: etichette {nm} ({NP} permutazioni, {time.time()-t0:.0f}s) --')
    print(pd.DataFrame(dict(reale=pd.Series(real), nullo_media=S.mean(), nullo_sd=S.std(), nullo_q95=S.quantile(0.95), p_value=pd.Series({k: ((S[k] >= real[k]).sum() + 1) / (NP + 1) for k in real}))).round(3).to_string())
print(f'\nvarianti (libri) provate in questo script: {ntr}')
