"""A10 - 02: il libro dei trade valutato a mercato ogni giorno; cadute e Monte Carlo ereditano l'errore del 'giorno di uscita'?
Limiti del libro live applicati alla ricerca; contributo di SOL; effetto del motore di rischio. SIMULATO."""
from common import *
KEY = ('atr1.0', ('alta',), 2.0, 'long')
Tx, _, _, _ = trade_book(mtm=False); Tm, mg, no, rk = trade_book(mtm=True)
print('== 1. Libro dei trade 11x (1%/2%): P&L sul giorno di uscita (09_fondo) contro valutazione giornaliera a mercato')
print('   somma dei rendimenti: uscita %.4f  mtm %.4f (devono coincidere)' % (Tx.sum(), Tm.sum()))
def full(lab, x):
    a = ann(x); m = mm(x); eqm = (1 + m).cumprod()
    print(f"{lab:58s} Sh giorn {a['sh']:.2f} | Sh mens {msh(x):.2f} (sel {msh(x[:SEL_END]):.2f} ver {msh(x[SPL:]):.2f}) | CAGR {a['cagr']:.3f} | vol giorn {a['vol']:.3f} vol mens {m.std()*12**.5:.3f} | DD giorn {a['dd']:.3f} DD mens {(eqm/eqm.cummax()-1).min():.3f} | giorno peggiore {x.min():.3f} mese peggiore {m.min():.3f}")
    return a
for nm, T in (('uscita', Tx), ('mtm', Tm)):
    full(f'T solo trade [{nm}]', T); full(f'C2 = 6 strat 1x + trade [{nm}]', NEW + T); full(f'C3 = 6 strat 2x + trade [{nm}]', lev09(NEW, 2) + T)
    print('   correlazione GIORNALIERA trade-libro giornaliero: %.2f   mensile: %.2f' % (T.corr(NEW), mm(T).corr(mm(NEW))))
print('\n== 2. Composizione: sovrapposizione additiva sul patrimonio corrente (09) contro conto vero (controvalore fissato sul patrimonio di INGRESSO)')
X, paths = trade_tables(KEY)
def account(L=2.0, rc=.01, re=.02, limits=False, coins=None, fin='09', engine=False, lev_cap=None, ret_parts=False, m=1.0, h=0.5, hww=None):
    base = NEW.values; rfv = rf.values; n = len(IDX); pos = {d: i for i, d in enumerate(IDX)}
    by_entry = {}
    for (i, t), p in zip(X.iterrows(), paths):
        if coins is not None and t.coin not in coins: continue
        if pd.Timestamp(t.entry) in pos: by_entry.setdefault(pos[pd.Timestamp(t.entry)], []).append((t, p))
    cu = cash_used().values
    ORDER = dict(NORMAL=0, REDUCED=1, HALTED=2, KILLED=3); SC = dict(NORMAL=1.0, REDUCED=0.5, HALTED=0.25, KILLED=0.0); state = 'NORMAL'; hist = []; days_state = dict(NORMAL=0, REDUCED=0, HALTED=0, KILLED=0)
    E = 1.0; hw = 1.0; out = np.zeros(n); pt = np.zeros(n); pb = np.zeros(n); openT = []; scale = 1.0; killed_until = -1; nk = 0; skipped = 0; taken = 0
    for k in range(n):
        for t, p in by_entry.get(k, []):
            risk = (re if (t.score is not None and t.score > 0.75) else rc)
            if engine: risk *= scale
            Lt = t.L if lev_cap is None else min(t.L, lev_cap)
            if limits:
                risk = min(risk, 0.02); orisk = sum(o['risk'] for o in openT) / E; onot = sum(o['not'] for o in openT) / E; omar = sum(o['mar'] for o in openT) / E
                Lt = min(Lt, 15.0)
                risk = min(risk, 0.06 - orisk); notional = min(risk / t.s, 1.5 - onot)
                if notional / Lt > 0.15 - omar: notional = (0.15 - omar) * Lt
                if len(openT) >= 4 or notional <= 1e-9 or risk <= 1e-9: skipped += 1; continue
            else: notional = risk / t.s
            if notional <= 0: skipped += 1; continue
            taken += 1
            openT.append(dict(not_=notional * E, risk=notional * t.s * E, mar=notional * E / Lt, p=p.values, i=0, **{'not': notional * E}))
        tp = 0.0
        for o in openT: tp += o['not_'] * o['p'][o['i']]; o['i'] += 1
        openT = [o for o in openT if o['i'] < len(o['p'])]
        s = scale if engine else 1.0
        if fin == '09': b = L * base[k] - (L - 1) * (rfv[k] + 0.015 / 365)
        else: b = L * base[k] - max(L * cu[k] - 1, 0) * (rfv[k] + 0.015 / 365)
        bp = E * b * s
        E1 = E + bp + tp; out[k] = E1 / E - 1; pt[k] = tp; pb[k] = bp; E = E1; hw = max(hw, E)
        if engine:                                                          # replica di gerva.risk.engine.assess, una volta al giorno
            hist.append(E)
            if state == 'KILLED' and k >= killed_until: state = 'HALTED'; hw = E   # reset a mano dopo 30 giorni: riparte da HALTED, massimo azzerato
            if hww is not None and state != 'KILLED': hw = max(hist[-hww:])
            dd = E / hw - 1; day = out[k]; week = E / hist[-8] - 1 if len(hist) >= 8 else E / hist[0] - 1
            new = 'NORMAL'
            if state == 'KILLED' or dd <= -0.20 * m: new = 'KILLED'
            elif dd <= -0.15 * m or week <= -0.08 * m: new = 'HALTED'
            elif dd <= -0.10 * m or day <= -0.04 * m: new = 'REDUCED'
            if new != 'KILLED' and ORDER[new] < ORDER[state]:
                if state == 'HALTED' and dd <= -0.15 * m * h: new = 'HALTED'
                elif state in ('HALTED', 'REDUCED') and dd <= -0.10 * m * h: new = 'REDUCED'
            if new == 'KILLED' and state != 'KILLED': killed_until = k + 30; nk += 1; openT = []
            state = new; scale = SC[state]; days_state[state] += 1
    r = pd.Series(out, index=IDX)
    if ret_parts: return r, pd.Series(pt, index=IDX), pd.Series(pb, index=IDX), dict(kill=nk, saltati=skipped, presi=taken, giorni=days_state)
    return r, dict(kill=nk, saltati=skipped, presi=taken, giorni=days_state)
for L, (rc, re), nm in ((1, (.01, .02), 'C2'), (2, (.01, .02), 'C3'), (2, (.015, .03), 'C4'), (3, (.015, .03), 'C6')):
    a0, _ = account(L, rc, re); full(f'{nm} conto vero (mtm, sizing su patrimonio di ingresso)', a0)
    a1, i1 = account(L, rc, re, limits=True); full(f'{nm} + LIMITI del libro live (rischio<=2%, 6% aperto, 1,5x, 15% margine)', a1); print('      ', i1)
    a2, i2 = account(L, rc, re, limits=True, engine=True); full(f'{nm} + limiti + MOTORE DI RISCHIO (config/gerva.yaml: -10% meta, -15% un quarto, -20% KILL; -4% giorno, -8% settimana)', a2); print('      ', i2)
    aB, iB = account(L, 0.0, 0.0, engine=True); full(f'   solo libro giornaliero {L}x + motore di rischio', aB); print('      ', iB)
    a3, i3 = account(L, rc, re, limits=True, fin='reale'); full(f'{nm} + limiti, finanziamento sul debito reale', a3)
print('\n== 3. Sopravvivenza: SOL e\' stata scelta sapendo com\'e\' andata? Libro dei trade per moneta (1%/2%, mtm)')
for coins in (('BTC',), ('ETH',), ('SOL',), ('BTC', 'ETH'), ('BTC', 'ETH', 'SOL')):
    T, *_ = trade_book(coins=coins); x = X[X.coin.isin(coins)]
    t = line('trade ' + '+'.join(coins), T, monthly=True, extra=f" n={len(x)} R medio {x.R.mean():+.2f} (sel {x[x.entry < SPL].R.mean():+.2f}, ver {x[x.entry >= SPL].R.mean():+.2f}) t={x.R.mean()/x.R.std()*len(x)**.5:.2f}")
print('\n== 4. Monte Carlo: mensile a blocchi di 3 mesi (pubblicato) contro giornaliero mtm a blocchi di 30 e 90 giorni; 3 anni, 4000 percorsi')
def mc_d(x, B=30, n=4000, H=1095, seed=7):
    rng = np.random.default_rng(seed); v = x.values; o = []
    for s in rng.integers(0, len(v) - B, (n, H // B + 1)):
        y = np.concatenate([v[a:a + B] for a in s])[:H]; eq = np.cumprod(1 + np.maximum(y, -1)); o.append((eq[-1], (eq / np.maximum.accumulate(eq) - 1).min(), eq.min()))
    o = np.array(o); cg = o[:, 0] ** (1 / 3) - 1
    return dict(cagr_p50=np.median(cg), cagr_p05=np.quantile(cg, .05), dd_p50=np.median(o[:, 1]), dd_p95=np.quantile(o[:, 1], .05), p_meno30=(o[:, 2] <= .7).mean(), p_dimezzato=(o[:, 2] <= .5).mean())
def mc_m(x, B=3, n=4000, H=36, seed=7):
    rng = np.random.default_rng(seed); v = mm(x).values; o = []
    for s in rng.integers(0, len(v) - B + 1, (n, H // B)):
        y = np.concatenate([v[a:a + B] for a in s]); eq = np.cumprod(1 + np.maximum(y, -1)); o.append((eq[-1], (eq / np.maximum.accumulate(eq) - 1).min(), eq.min()))
    o = np.array(o); cg = o[:, 0] ** (1 / 3) - 1
    return dict(cagr_p50=np.median(cg), cagr_p05=np.quantile(cg, .05), dd_p50=np.median(o[:, 1]), dd_p95=np.quantile(o[:, 1], .05), p_meno30=(o[:, 2] <= .7).mean(), p_dimezzato=(o[:, 2] <= .5).mean())
rows = []
for nm, x in (('C2 1x+trade', NEW + Tm), ('C3 2x+trade', lev09(NEW, 2) + Tm), ('C3 conto vero + limiti', account(2, .01, .02, limits=True)[0])):
    rows.append(dict(p=nm, metodo='mensile blocchi 3m (pubblicato)', **mc_m(x))); rows.append(dict(p=nm, metodo='giornaliero mtm blocchi 30g', **mc_d(x, 30))); rows.append(dict(p=nm, metodo='giornaliero mtm blocchi 90g', **mc_d(x, 90)))
print(pd.DataFrame(rows).round(3).to_string(index=False))
print('\n== 5. Varianti del motore di rischio (soglie x m; isteresi h = frazione della soglia per risalire; massimo su finestra mobile). Scelta sul periodo di scelta')
import json; TR5 = {}
for nm, (L, rc, re) in (('B2 libro 2x', (2, 0, 0)), ('C3 2x+trade', (2, .01, .02))):
    a0, _ = account(L, rc, re, limits=True); t = line(f'{nm}: motore SPENTO (numeri pubblicati)', a0, monthly=True)
    for m in (1.0, 1.5, 2.0, 3.0):
        for h in (0.5, 0.8):
            for hww in (None, 365):
                a, i = account(L, rc, re, limits=True, engine=True, m=m, h=h, hww=hww)
                t = line(f'{nm}: soglie x{m} isteresi {h} massimo {"storico" if hww is None else "365g"}', a, monthly=True, extra=f"| kill {i['kill']} giorni ridotti/fermi {i['giorni']['REDUCED']}/{i['giorni']['HALTED']}"); TR5[f'{nm} {m} {h} {hww}'] = round(float(t['sh_sel']), 3)
json.dump(TR5, open(HERE + '/trials_02.json', 'w')); print('varianti provate:', len(TR5) + 5)
SER = {'trade11_mtm': Tm, 'B_pubblicato': NEW,
       'C2_mtm_limiti': account(1, .01, .02, limits=True)[0], 'C3_mtm_limiti': account(2, .01, .02, limits=True)[0],
       'C3_mtm_limiti_debito_reale': account(2, .01, .02, limits=True, fin='reale')[0], 'B2_debito_reale': account(2, 0, 0, fin='reale')[0],
       'C3_motore_di_rischio_attuale': account(2, .01, .02, limits=True, engine=True)[0], 'B2_motore_di_rischio_attuale': account(2, 0, 0, engine=True)[0],
       'C1_mtm_limiti': account(1, .005, .01, limits=True)[0], 'C1_motore_di_rischio_attuale': account(1, .005, .01, limits=True, engine=True)[0]}
pd.DataFrame(SER).to_parquet(HERE + '/_mtm.parquet')
