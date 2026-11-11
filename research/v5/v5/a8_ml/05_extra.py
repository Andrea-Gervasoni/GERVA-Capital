"""A8 - 05: prove aggiuntive con la configurazione congelata + salvataggio di trades.parquet / returns.parquet.
(1) lato SHORT (stesso modello, stessa configurazione, etichetta R del trade short generico);
(2) replica del risultato precedente: logistica ristimata sui 12 segnali contro pesi uguali, come libro eseguibile;
(3) serie giornaliere a rischio 1% per trade (P&L attribuito al giorno di uscita)."""
import json
from ml import *
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
D, F = load(); FZ = json.load(open(HERE + '/frozen.json')); PRIM = FZ['primary']; ALLB = list(SEL_BLOCKS) + list(VER_BLOCKS)
P = pd.read_parquet(HERE + '/preds.parquet'); dt = Data(); SIMS = {c: Sim(dt, c) for c in COINS}; ntr = 0
def exante_thr(p, q):
    thr = np.full(len(D), np.nan); dts = D['date'].values
    for b in ALLB[1:]:
        prev = np.isfinite(p) & (dts < np.datetime64(b)); te = (dts >= np.datetime64(b)) & (dts < np.datetime64(b + pd.DateOffset(months=6))); thr[te] = np.quantile(p[prev], q)
    return thr
def book(gate, side=1, cm=1.0, delay=0, t0='2020-01-01'):
    out = []
    for c in COINS:
        s = SIMS[c]; d = D[D.coin == c]; di = pd.DatetimeIndex(s.days)
        gi = pd.Series(gate[d.index.values], index=d['date'].values).reindex(di).fillna(False).values; sd_ = pd.Series(d['sd'].values, index=d['date'].values).reindex(di).values
        i = int(np.searchsorted(s.days, np.datetime64(t0)))
        while i < s.n - 8:
            if not gi[i]: i += 1; continue
            t = s.trade(i, side, float(sd_[i]), i + 7, cm=cm, delay=delay); out.append(t); i = t['j'] + 1
    return pd.DataFrame(out)
def line(lab, T):
    o = dict(libro=lab)
    for nm, x in (('sel', T[T.entry < SPL]), ('ver', T[T.entry >= SPL])):
        y = (x.entry.max() - x.entry.min()).days / 365.25; s = rstats(x.R); o.update({f'n_{nm}': s['n'], f'anno_{nm}': s['n'] / y, f'R_{nm}': s['R'], f'sd_{nm}': s['sd'], f'ir_{nm}': s['ir'], f't_{nm}': s['t'], f'hit_{nm}': s['hit'], f'NIR2_{nm}': s['n'] / y * s['ir'] ** 2 * np.sign(s['ir'])})
    return o
print('== 1. Lato SHORT: stessa configurazione congelata, etichetta = R del trade short generico ==')
rs = D['R_S'].values; ps = walk(D, F, PRIM, ALLB, rcol='R_S'); ntr += 1
for lab, m, bl in (('scelta', (D.date <= SEL_LAST).values, SEL_BLOCKS), ('verifica', (D.date >= SPL).values, VER_BLOCKS)):
    mm = m & np.isfinite(ps); ic = block_ic(D, np.where(m, ps, np.nan), rs, bl)
    print(f"{lab}: n {mm.sum()}  IC medio {ic.mean():+.3f} (t {ic.mean()/ic.std(ddof=1)*np.sqrt(len(ic)):+.2f}, blocchi>0 {(ic>0).sum()}/{len(ic)})  R tutti {rs[mm].mean():+.3f}  R top20% {rs[mm & (ps >= np.quantile(ps[mm], 0.8))].mean():+.3f}  R top10% {rs[mm & (ps >= np.quantile(ps[mm], 0.9))].mean():+.3f}")
rows = [line('short sempre', book(np.ones(len(D), bool), side=-1))]
for q in (0.8, 0.9): rows.append(line(f'short modello p>=q{q} ex-ante', book(np.isfinite(ps) & (ps >= exante_thr(ps, q)), side=-1))); ntr += 1
print(pd.DataFrame(rows).round(3).to_string(index=False))
print('\n== 2. Replica: logistica ristimata (semestrale) sui 12 segnali contro la conviction a pesi uguali, libri eseguibili ==')
alta = (D.tier == 'alta').values; rows = [line('pesi uguali: conviction alta', book(alta))]; BK = {'v4_alta': book(alta)}
for nm in ('LOGIT12', 'LOGITALL'):
    p = P[nm].values
    for q in (0.6, 0.8): rows.append(line(f'{nm} p>=q{q} ex-ante', book(np.isfinite(p) & (p >= exante_thr(p, q))))); ntr += 1
print(pd.DataFrame(rows).round(3).to_string(index=False))
print('(q0.6 lascia circa la stessa quota di giorni della conviction alta, ~40%)')
print('\n== 3. Salvataggio ==')
pp = P[FZ['primary_fam']].values; pr = P['HGBR'].values
BK['A8_HGBC_q0.9'] = book(np.isfinite(pp) & (pp >= exante_thr(pp, 0.9))); BK['A8_HGBC_q0.8'] = book(np.isfinite(pp) & (pp >= exante_thr(pp, 0.8))); BK['A8_HGBR_q0.8_secondario'] = book(np.isfinite(pr) & (pr >= exante_thr(pr, 0.8)))
T = pd.concat([v.drop(columns='j').assign(book=k) for k, v in BK.items()]).rename(columns=dict(coin='symbol', s='stop_dist', L='leverage'))
T['why_entry'] = T.book.map({'v4_alta': 'riferimento: conviction alta (regola attuale, trade generico)', 'A8_HGBC_q0.9': 'modello primario P(R>0) >= quantile 0.9 ex-ante', 'A8_HGBC_q0.8': 'modello primario P(R>0) >= quantile 0.8 ex-ante', 'A8_HGBR_q0.8_secondario': 'SECONDARIO (non pre-scelto): E[R] previsto >= quantile 0.8 ex-ante'})
T.to_parquet(HERE + '/trades.parquet'); idx = pd.date_range('2020-01-01', '2026-10-31'); RISK = 0.01
Rt = pd.DataFrame({k: (v.groupby('exit').R.sum() * RISK).reindex(idx).fillna(0.0) for k, v in BK.items()}); Rt.to_parquet(HERE + '/returns.parquet')
print('trades.parquet', T.shape, '| returns.parquet', Rt.shape, f'(rischio {RISK:.0%} del capitale per trade, non composto, P&L al giorno di uscita)')
sh = lambda x: x.mean() / x.std() * np.sqrt(365); print(pd.DataFrame({k: dict(sharpe_tot=sh(Rt[k]), sharpe_sel=sh(Rt[k][:'2022']), sharpe_ver=sh(Rt[k]['2023':]), rend_anno_ver=Rt[k]['2023':].mean() * 365, corr_v4_mensile=Rt[k].resample('ME').sum().corr(Rt['v4_alta'].resample('ME').sum())) for k in Rt}).T.round(3))
print(f'\nvarianti provate in questo script: {ntr}')
