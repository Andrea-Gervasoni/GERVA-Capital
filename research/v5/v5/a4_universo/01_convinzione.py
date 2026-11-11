"""A4 (a) - ingressi di conviction per moneta con stop ATR, estesi dal trio BTC/ETH/SOL al top-N point-in-time. SIMULATO.
Regola identica al libro di trade v4 (leva_trade_isolato.py): long quando la conviction e' 'alta', stop k x ATR(14), trailing 2 x stop,
uscita se la conviction scende a 'bassa' o dopo 7 giorni. Qui il percorso e' a 1 ora sui perpetual."""
import sys, pickle; sys.path.insert(0, '/home/user/GERVA-Capital/research/v5/v5/a4_universo')
from lab import *
pd.set_option('display.width', 300); pd.set_option('display.max_columns', 50)
U, RANK = load_all(30, verbose=True)
TRIO = ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')
def sig_long(U, topn=None, only=None):
    ent, ext = {}, {}
    for s, o in U.items():
        if only is not None and s not in only: continue
        m = (o.rank <= topn) if topn else np.ones(len(o.days), bool)
        ent[s] = (o.tier == 'alta') & m; ext[s] = (o.tier == 'bassa')
    return ent, ext
def sig_short(U, topn, thr=0.2):
    ent, ext = {}, {}
    for s, o in U.items():
        ent[s] = (o.score <= thr) & (o.rank <= topn); ext[s] = (o.score > 0.45)
    return ent, ext
rows = []; KEEP = {}; nvar = 0
print('\n== (a) long conviction alta: universo x stop ==')
for k_ in (1.0, 2.0):
    for name, kw in (('trio BTC/ETH/SOL', dict(only=TRIO)), ('top10', dict(topn=10)), ('top20', dict(topn=20)), ('top30', dict(topn=30))):
        ent, ext = sig_long(U, **kw); T, M = run(U, ent, ext, atr_k=k_); nvar += 1
        lab = f'{name} stop {k_:.0f}xATR'; KEEP[lab] = (T, M); rows.append(row(lab, T, M))
print('\n== short conviction <= 0,2 (top30) ==')
for k_ in (1.0, 2.0):
    ent, ext = sig_short(U, 30); T, M = run(U, ent, ext, side=-1, atr_k=k_); nvar += 1
    lab = f'SHORT top30 stop {k_:.0f}xATR'; KEEP[lab] = (T, M); rows.append(row(lab, T, M))
R = pd.DataFrame(rows).set_index('cfg')
print(R[['n', 'R', 't', 'hit', 'R_sc', 't_sc', 'n_sc', 'R_ver', 't_ver', 'n_ver', 'lev']].round(3).to_string())
print('\nN = trade/anno; sR = dev.std di R; Neff = N^2 sR^2 / Var annua del P&L giornaliero sommato (da somme settimanali);')
print('K = N_eff*(Rm/sR)^2 = Sharpe annuo^2 del flusso; PR = rapporto di partecipazione della covarianza moneta x giorno; rho = correlazione esiti stesso giorno')
print(R[['N', 'sR', 'Neff', 'K', 'PR', 'rho', 'N_sc', 'Neff_sc', 'K_sc', 'N_ver', 'Neff_ver', 'K_ver', 'PR_ver', 'rho_ver']].round(2).to_string())
print('\n== solo le monete FUORI dal trio (top30, 1xATR): il contributo marginale ==')
T, M = KEEP['top30 stop 1xATR']; x = T[~T.symbol.isin(TRIO)]; print(pd.DataFrame([row('alt soltanto', x, M.drop(columns=list(TRIO)))]).round(3).T.to_string())
print('per fascia di rango (volume):'); T['fascia'] = pd.cut(T['rank'], [0, 3, 10, 20, 30]); g = T.groupby(['fascia', T.entry >= SPLIT])['R']
print(pd.DataFrame(dict(n=g.count(), R=g.mean(), t=g.mean() / g.std() * np.sqrt(g.count()))).round(3).to_string())
print('\n== per anno, top30 1xATR =='); print(per_year(T).round(3).to_string())
print('\n== per anno, trio 1xATR =='); print(per_year(KEEP['trio BTC/ETH/SOL stop 1xATR'][0]).round(3).to_string())
print('\n== robustezza top30 e trio, 1xATR: costi x2, ritardo +1 barra, tetto 10x ==')
rr = []
for name, kw in (('trio', dict(only=TRIO)), ('top30', dict(topn=30))):
    ent, ext = sig_long(U, **kw)
    for lab, k2 in (('base', {}), ('costi x2', dict(cost_mult=2.0)), ('ritardo +1h', dict(delay=1)), ('tetto leva 10x', dict(cap=10.0))):
        T2, M2 = run(U, ent, ext, atr_k=1.0, **k2); rr.append(row(f'{name} {lab}', T2, M2))
print(pd.DataFrame(rr).set_index('cfg')[['n', 'R', 't', 'R_sc', 'R_ver', 't_ver', 'Neff', 'K', 'K_ver']].round(3).to_string())
print('\n== tetto di liquidita\' (posizione <= 0,1% del volume mediano 90g; conto 100k) top30 1xATR ==')
T = KEEP['top30 stop 1xATR'][0]
for r in (0.01, 0.03, 0.05):
    sc = liq_scale(T, r); print(f'rischio {r:.0%}: trade tagliati {np.mean(sc < 1):.1%}, quota media eseguita {sc.mean():.3f}, R medio effettivo {np.mean(T.R * sc):.3f} (pieno {T.R.mean():.3f}); dal 2023: tagliati {np.mean(sc[T.entry >= SPLIT] < 1):.1%}')
print('\nvarianti provate in questo script:', nvar)
pickle.dump({k: v for k, v in KEEP.items()}, open('/home/user/GERVA-Capital/data_cache/v5_a4_a.pkl', 'wb'))
