"""A4 (b) selezione trasversale per forza relativa e (c) libro neutrale long-forti/short-deboli con stop per gamba. SIMULATO.
Punteggio: rendimento a L giorni, rango tra i membri del top-30 point-in-time, noto alla chiusura del giorno prima.
(b) long i primi k (filtri: nessuno / BTC sopra la media a 100 giorni / conviction alta); short gli ultimi k solo con BTC sotto la media a 100 giorni.
(c) long i primi k e short gli ultimi k sempre. Uscita: stop 1xATR con trailing 2x, oppure la moneta esce dai primi (ultimi) 2k, oppure 7 giorni."""
import sys, pickle; sys.path.insert(0, '/home/user/GERVA-Capital/research/v5/v5/a4_universo')
from lab import *
pd.set_option('display.width', 300); pd.set_option('display.max_columns', 50)
U, RANK = load_all(30)
C = pd.DataFrame({s: o.D['close'].reindex(CAL) for s, o in U.items()})
MEM = pd.DataFrame({s: pd.Series(o.rank <= 30, index=o.days).reindex(CAL).fillna(False) for s, o in U.items()}).astype(bool)
btc = C['BTCUSDT']; BULL = (btc > btc.rolling(100).mean()).shift(1).fillna(False).astype(bool); BEAR = (btc < btc.rolling(100).mean()).shift(1).fillna(False).astype(bool)
def ranks(L, rev=False):
    sc = (C / C.shift(L) - 1).where(MEM)
    if rev: sc = -sc
    return sc.rank(axis=1, ascending=False).shift(1), sc.rank(axis=1, ascending=True).shift(1)      # noti la sera prima
def sig(rk, k, gate=None, conv=None, hyst=2):
    ent, ext = {}, {}
    for s, o in U.items():
        r = rk[s].reindex(o.days).values; e = r <= k; x = ~(r <= hyst * k)
        if gate is not None: g = gate.reindex(o.days).values.astype(bool); e = e & g; x = x | ~g
        if conv == 'alta': e = e & (o.tier == 'alta'); x = x | (o.tier == 'bassa')
        ent[s] = e; ext[s] = x
    return ent, ext
rows = []; KEEP = {}; nvar = 0
def add(lab, T, M): KEEP[lab] = (T, M); rows.append(row(lab, T, M))
for L in (7, 30, 90):
    top, bot = ranks(L)
    for k in (3, 5):
        for fn, kw in (('sempre', {}), ('BTC>MA100', dict(gate=BULL)), ('conv alta', dict(conv='alta'))):
            T, M = run(U, *sig(top, k, **kw)); add(f'b LONG L{L} k{k} {fn}', T, M); nvar += 1
        T, M = run(U, *sig(bot, k, gate=BEAR), side=-1); add(f'b SHORT L{L} k{k} BTC<MA100', T, M); nvar += 1
        Tl, Ml = run(U, *sig(top, k)); Ts, Ms = run(U, *sig(bot, k), side=-1)
        add(f'c NEUTRO L{L} k{k}', pd.concat([Tl, Ts]), Ml + Ms); add(f'c  solo gamba short L{L} k{k}', Ts, Ms); nvar += 1
for k in (3, 5):                                                    # inversione a 7 giorni: long i deboli, short i forti
    top, bot = ranks(7, rev=True)
    Tl, Ml = run(U, *sig(top, k)); Ts, Ms = run(U, *sig(bot, k), side=-1); add(f'c NEUTRO inversione L7 k{k}', pd.concat([Tl, Ts]), Ml + Ms); nvar += 1
R = pd.DataFrame(rows).set_index('cfg')
print(R[['n', 'R', 't', 'hit', 'R_sc', 't_sc', 'n_sc', 'R_ver', 't_ver', 'n_ver', 'lev']].round(3).to_string())
print(R[['N', 'sR', 'Neff', 'K', 'PR', 'rho', 'N_sc', 'Neff_sc', 'K_sc', 'N_ver', 'Neff_ver', 'K_ver', 'PR_ver', 'rho_ver']].round(2).to_string())
print('\nvarianti provate in questo script:', nvar)
pickle.dump(KEEP, open('/home/user/GERVA-Capital/data_cache/v5_a4_bc.pkl', 'wb'))
