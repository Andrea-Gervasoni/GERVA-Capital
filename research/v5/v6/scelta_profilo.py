"""Quale profilo mandare in paper? Si misura ogni combinazione CON il motore di rischio dentro (scalini di caduta, perdita di
giornata e di settimana), perche' e' cosi' che girera'. La scelta si fa sul periodo fino al 2022 e si controlla dal 2023. SIMULATO.
Motore replicato: caduta dal massimo >= r -> esposizione x0,5; >= h -> x0,25; >= k -> tutto chiuso per 20 giorni, poi riparte
con il massimo azzerato (nel reale lo riaccende Andrea). Perdita in 24 ore <= -4% -> x0,5 il giorno dopo; in 7 giorni <= -8% -> x0,25.
La scala si applica dal giorno successivo."""
import numpy as np, pandas as pd, itertools
A = pd.read_parquet('research/v5/v5/a10_sistema/returns.parquet'); rf = pd.read_parquet('research/v5/v4/fondo_serie.parquet').rf.reindex(A.index).fillna(0)
T1 = A['trade11_mtm']; T05 = A['C1_mtm_limiti'] - A['B_pubblicato']
print('controllo: C3 = B2 + trade 1%%/2%%, scarto massimo %.2e; trade 0,5%%/1%% = meta dei trade 1%%/2%%, correlazione %.3f' % ((A['C3_mtm_limiti_debito_reale'] - A['B2_debito_reale'] - T1).abs().max(), T05.corr(T1)))
BOOK = {'1x': A['B_cassa_in_tbill'], '1,5x': 0.5 * (A['B_cassa_in_tbill'] + A['B2_debito_reale']), '2x': A['B2_debito_reale']}
TR = {'nessun trade': 0 * T1, 'trade 0,5%/1%': T05, 'trade 1%/2%': T1}
STEPS = {'10/15/20 (oggi)': (.10, .15, .20), '15/22/30': (.15, .22, .30), '20/30/40': (.20, .30, .40), 'solo arresto a 35': (9, 9, .35)}
def engine(x, r, h, k, day=-0.04, week=-0.08, pause=20):
    v = x.values; out = np.zeros(len(v)); eq = 1.0; hw = 1.0; scale = 1.0; off = 0; kills = 0; red = 0; hist = []
    for i in range(len(v)):
        if off > 0:
            off -= 1; out[i] = 0.0; hist.append(eq)
            if off == 0: hw = eq; scale = 1.0
            continue
        out[i] = scale * v[i]; eq *= 1 + out[i]; hist.append(eq); hw = max(hw, eq); dd = eq / hw - 1
        s = 1.0
        if dd <= -k: kills += 1; off = pause; continue
        if dd <= -h: s = 0.25
        elif dd <= -r: s = 0.5
        if out[i] <= day: s = min(s, 0.5)
        if i >= 7 and eq / hist[i - 7] - 1 <= week: s = min(s, 0.25)
        scale = s; red += s < 1
    return pd.Series(out, index=x.index), kills, red / len(v)
mm = lambda y: (1 + y).resample('ME').prod() - 1
def stats(y):
    def one(z):
        m = mm(z); e = m - mm(rf).reindex(m.index); d = (1 + z).cumprod()
        return e.mean() / e.std() * np.sqrt(12), d.iloc[-1] ** (365 / len(z)) - 1, (d / d.cummax() - 1).min()
    return one(y), one(y[:'2022-12-31']), one(y['2023-01-01':])
rows = []
for (b, xb), (t, xt), (s, st) in itertools.product(BOOK.items(), TR.items(), STEPS.items()):
    y, kills, red = engine(xb + xt, *st); a, i, o = stats(y)
    rows.append(dict(libro=b, trade=t, scalini=s, sharpe=a[0], cagr=a[1], maxdd=a[2], sh_scelta=i[0], cagr_scelta=i[1], dd_scelta=i[2], sh_verifica=o[0], cagr_verifica=o[1], dd_verifica=o[2], arresti=kills, giorni_ridotti=red))
R = pd.DataFrame(rows); pd.set_option('display.width', 250, 'display.max_rows', 200)
print(R.round(3).to_string(index=False)); R.to_csv('research/v5/v6/scelta_profilo.csv', index=False)
ok = R[(R.dd_scelta >= -0.25) & (R.arresti == 0)].sort_values('cagr_scelta', ascending=False)
print('\nRegola di scelta, fissata prima di guardare la verifica: tra le combinazioni con caduta massima in scelta entro il 25% e nessun arresto,\nquella con il rendimento annuo di scelta piu alto. Prime cinque:'); print(ok.head(5).round(3).to_string(index=False))
ok2 = R[(R.dd_scelta >= -0.25) & (R.arresti == 0)].sort_values('sh_scelta', ascending=False)
print('\nStessa regola, ordinando per Sharpe di scelta. Prime cinque:'); print(ok2.head(5).round(3).to_string(index=False))
