"""A9/04 - DOVE mettere lo stop: % fissa, multipli di ATR, sotto il minimo di ieri, sotto il minimo degli ultimi N giorni, sotto il
numero tondo; e quanto spesso lo stop viene 'cacciato' (stop preso, poi il prezzo torna SOPRA l'ingresso entro 24 ore).
Placebo: stessa distribuzione di distanze dello stop 'minimo di ieri', ma presa da 5 giorni prima (nessun legame col livello).
Perpetual Binance 5m, 2020-2026, ingresso taker alle 00:00. SIMULATO. Scelta 2020-2022, verifica 2023+."""
from lib import *
COLS = ['cfg', 'n', 'N_anno', 's_med', 'R', 'sdR', 't', 'hit', 'R_sel', 't_sel', 'R_ver', 't_ver', 'K_sel', 'K_ver', 'costo_R', 'stop_pct', 'caccia_su_stop', 'caccia_su_tutti', 'caccia_sel', 'caccia_ver']
CFG = [('fix', 0.012), ('fix', 0.017), ('fix', 0.027), ('fix', 0.04), ('fix', 0.06), ('atr', 0.35), ('atr', 0.5), ('atr', 0.75), ('atr', 1.0), ('atr', 1.5), ('atr', 2.0),
       ('pdl', 0), ('pdl_placebo', 0), ('swing', 2), ('swing', 3), ('swing', 5), ('swing_placebo', 3), ('round', 0.5), ('round', 1.0), ('atr_noround', 1.0), ('atr_noround', 0.5)]
ALL = {}
for trail in (2.0, None):
    print(f'\n################ trailing = {trail} ################')
    rows = []
    for stp, k in CFG:
        T = run(perp=True, stop=stp, k=k, trail=trail); count('stop'); ALL[(stp, k, trail)] = T
        r = stats(T, f'{stp} {k} trail={trail}'); S = T[T.why != 'tempo']
        r.update(caccia_su_stop=S.hunt.mean(), caccia_su_tutti=S.hunt.sum() / len(T), caccia_sel=S[S.entry < CUT].hunt.mean(), caccia_ver=S[S.entry >= CUT].hunt.mean()); rows.append(r)
    R = show(rows, COLS)
    print('Migliori 5 per K_sel:'); show(R.sort_values('K_sel', ascending=False).head(5).to_dict('records'), COLS)
print('\n=== Stop sul minimo di ieri con margini diversi (trail 2) ===')
rows = []
for buf in (0.0, 0.001, 0.0025, 0.005, 0.01):
    T = run(perp=True, stop='pdl', trail=2.0, buf=buf); count('stop'); r = stats(T, f'pdl margine {buf:.2%}'); S = T[T.why != 'tempo']; r.update(caccia_su_stop=S.hunt.mean(), caccia_su_tutti=S.hunt.sum() / len(T)); rows.append(r)
show(rows, COLS)
print('\n=== Numeri tondi: stop 1xATR (trail 2). Lo stop che cade vicino a un tondo viene preso / cacciato piu\' spesso? ===')
T = ALL[('atr', 1.0, 2.0)].copy(); sp = T.pe * (1 - T.s); stp = 10.0 ** np.floor(np.log10(T.pe * 0.05)); T['dist'] = np.abs(sp / stp - np.round(sp / stp))      # 0 = sul tondo, 0.5 = a meta'
for lab, m in (('entro 10% del passo dal tondo', T.dist < 0.1), ('10-30%', (T.dist >= 0.1) & (T.dist < 0.3)), ('oltre 30%', T.dist >= 0.3)):
    x = T[m]; S = x[x.why != 'tempo']; print(f"{lab:32s} n={len(x):4d} stop presi {len(S)/len(x):.1%}  cacciati/stop {S.hunt.mean():.1%}  R medio {x.R.mean():+.3f}")
T2 = ALL[('atr', 1.0, None)]; S = T2[T2.why != 'tempo']
print('\n=== Stop iniziale 1xATR senza trailing: i primi stop (prima che il prezzo salga) ===')
print(f"stop presi {len(S)/len(T2):.1%}; di questi cacciati (ritorno sopra l'ingresso entro 24h) {S.hunt.mean():.1%} (scelta {S[S.entry<CUT].hunt.mean():.1%}, verifica {S[S.entry>=CUT].hunt.mean():.1%})")
print('\n=== Riferimento casuale: probabilita\' che un moto browniano senza deriva, sceso di d dall\'ingresso, risalga di d entro 24h, per d = stop/vol giornaliera ===')
from math import erf, sqrt
for stp, k in (('fix', 0.017), ('atr', 0.5), ('atr', 1.0), ('atr', 2.0), ('pdl', 0), ('swing', 3)):
    T = ALL[(stp, k, None)]; S = T[T.why != 'tempo'].copy()
    # vol giornaliera stimata = ATR/1.6 circa (range medio ~1,6 sigma); P(max in 1 giorno >= d) = 2*(1-Phi(d/sigma))
    a = pd.concat([pd.Series(ATR[c].reindex(pd.DatetimeIndex(S[S.coin == c].entry)).values, index=S[S.coin == c].index) for c in COINS]); sig = a / 1.6
    p = (2 * (1 - 0.5 * (1 + (S.s / sig / np.sqrt(2)).apply(erf)))).mean()
    print(f"{stp} {k}: cacciati osservati {S.hunt.mean():.1%} contro attesi per puro caso {p:.1%} (n stop {len(S)})")
save_trials('04'); print('prove:', TRIALS)
