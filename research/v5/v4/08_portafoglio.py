"""Portafoglio: i quattro sleeve esistenti + i candidati che passano, con parita' di rischio (gerva.portfolio.allocate).
Scrive candidates.parquet (rendimenti giornalieri netti di TUTTI i candidati, indice di calendario) e stampa: tabella dei
candidati, portafogli, scomposizione, leva a volatilita' obiettivo 15% e 25% con costo del finanziamento, conteggio prove e
Deflated Sharpe. Tutti i numeri sono SIMULATI."""
from lab import *
import glob
from gerva.portfolio import risk_parity, combine, vol_target_leverage
from gerva.backtest import scale_returns
C = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(HERE + '/cand_*.parquet'))], axis=1).reindex(IDX)
C.to_parquet(HERE + '/candidates.parquet')
print('candidates.parquet:', C.shape, list(C.columns))
print('\n== A. Tutti i candidati (netti dei costi dichiarati; Sharpe in eccesso del tasso a breve; cassa a rendimento zero)')
rows = []
for c in C:
    r = C[c].dropna(); t = three(r); k = corrs(C[c])
    rows.append(dict(candidato=c[:44], dal=str(r.index[0].date()), sh_tot=t['sh_tot'], sh_scelta=t['sh_sel'], sh_verifica=t['sh_ver'], sh_rf0=sh0(r), cagr=t['cagr_tot'], cagr_ver=t['cagr_ver'], vol=t['vol_tot'], maxdd=t['dd_tot'],
                     **{'c_' + a[:8]: b for a, b in k.items()}))
T = pd.DataFrame(rows); print(T.round(2).to_string(index=False))
print('\nSharpe per anno:'); print(pd.DataFrame({c[:30]: by_year(C[c]) for c in C}).T.to_string())

def rp(S, carry=None, wc=0.20):
    """Parita' di rischio sugli sleeve 'a rischio di mercato'; il carry (rischio di controparte, volatilita' misurata quasi nulla)
    riceve una quota FISSA wc quando la serie esiste, il resto e' ripartito tra gli altri."""
    a = risk_parity(S)
    if carry is None: return combine(S, a), a
    has_c = carry.reindex(a.index).notna()
    a2 = a.mul(1 - wc * has_c.astype(float), axis=0); p = combine(S, a2) + wc * carry.reindex(a.index).fillna(0.0)
    a2['CARRY'] = wc * has_c.astype(float); return p, a2
def show(lab, p, w0=None):
    p = p.dropna();  p = p.loc[w0:] if w0 else p; t = three(p)
    print(f"{lab[:70]:70s} Sh {t['sh_tot']:5.2f} | {t['sh_sel']:5.2f} | {t['sh_ver']:5.2f}   CAGR {100 * t['cagr_tot']:5.1f}% {100 * t['cagr_sel']:5.1f}% {100 * t['cagr_ver']:5.1f}%   vol {100 * t['vol_tot']:4.1f}% {100 * t['vol_ver']:4.1f}%   DD {100 * t['dd_tot']:6.1f}% {100 * t['dd_ver']:6.1f}%", flush=True)
    return t
DIP = C['DIP-24h (compra il crollo, perp)']; CAR = C['CARRY-XS-HL (incollato)']
EXTRA = {k: C[k] for k in C if k.startswith(('NEW-LIST', 'XS-FUNDING'))}
base, a0 = rp(S0)
print('\ncontrollo: il portafoglio ricostruito coincide con PORT di series.parquet? differenza massima', float((base - PORT).abs().max()))
print('\n== B. Portafogli (tot | scelta | verifica). Finestra intera 2018-04 -> 2026-10')
P = {}
P['0. ATTUALE: 4 sleeve'] = base
P['1. 4 sleeve + DIP-24h'] = rp(pd.concat([S0, DIP.rename('DIP')], axis=1))[0]
P['2. 4 sleeve + CARRY (quota fissa 20%)'] = rp(S0, CAR)[0]
P['3. 4 sleeve + DIP-24h + CARRY 20%'], a3 = rp(pd.concat([S0, DIP.rename('DIP')], axis=1), CAR)
P['3b. come 3 ma CARRY 10%'] = rp(pd.concat([S0, DIP.rename('DIP')], axis=1), CAR, 0.10)[0]
P['3c. come 3 ma CARRY 30%'] = rp(pd.concat([S0, DIP.rename('DIP')], axis=1), CAR, 0.30)[0]
P['4. parita\' di rischio pura con CARRY (artefatto: il carry prende il tetto 60%)'] = rp(pd.concat([S0, DIP.rename('DIP'), CAR.rename('CARRY')], axis=1))[0]
for k, v in EXTRA.items():
    P[f'5. (NON passa, solo confronto) 3 + {k[:24]}'] = rp(pd.concat([S0, DIP.rename('DIP'), v.rename(k[:8])], axis=1), CAR)[0]
if len(EXTRA) > 1: P['6. (NON passa, solo confronto) 3 + tutti gli extra'] = rp(pd.concat([S0, DIP.rename('DIP')] + [v.rename(k[:8]) for k, v in EXTRA.items()], axis=1), CAR)[0]
for k, v in P.items(): show(k, v)
print('\n   Stessa tabella dalla data in cui i candidati esistono (2020-06 -> 2026-10): e\' il confronto alla pari')
for k, v in P.items(): show(k, v, '2020-06-01')
print('\n   Carry valutato SOLO dove un italiano puo\' eseguirlo oggi (Hyperliquid, verifica 2023-06 -> 2026-10):')
for k in list(P)[:4]: show(k, P[k], '2023-06-01')
FIN = '3. 4 sleeve + DIP-24h + CARRY 20%'; port = P[FIN].dropna()
print(f'\n== C. Scomposizione del portafoglio difendibile [{FIN}]')
S = pd.concat([S0, DIP.rename('DIP'), CAR.rename('CARRY')], axis=1).reindex(a3.index)
rows = []
for c in S:
    r = S[c].dropna(); t = three(r); contr = (a3[c] * S[c].fillna(0.0))
    rows.append(dict(sleeve=c, peso_medio=a3[c].mean(), peso_medio_verifica=a3[c].loc[SPL:].mean(), sh_tot=t['sh_tot'], sh_scelta=t['sh_sel'], sh_verifica=t['sh_ver'], cagr_da_solo=t['cagr_tot'], vol=t['vol_tot'],
                     contributo_annuo=contr.mean() * 365, contributo_annuo_verifica=contr.loc[SPL:].mean() * 365))
Dc = pd.DataFrame(rows); print(Dc.round(3).to_string(index=False))
tp = three(port)
print(f"somma dei contributi annui: {Dc.contributo_annuo.sum():.3f} (verifica {Dc.contributo_annuo_verifica.sum():.3f});  quota media investita (somma pesi): {a3.sum(axis=1).mean():.2f}")
print(f"Sharpe medio degli sleeve: tot {Dc.sh_tot.mean():.2f}, scelta {Dc.sh_scelta.mean():.2f}, verifica {Dc.sh_verifica.mean():.2f}  ->  Sharpe del portafoglio: {tp['sh_tot']:.2f} | {tp['sh_sel']:.2f} | {tp['sh_ver']:.2f}")
print(f"   (senza il CARRY, il cui Sharpe e' gonfiato dalla volatilita' quasi nulla: media sleeve tot {Dc[Dc.sleeve != 'CARRY'].sh_tot.mean():.2f}, verifica {Dc[Dc.sleeve != 'CARRY'].sh_verifica.mean():.2f})")
print('correlazioni mensili tra sleeve:'); print(((1 + S.fillna(0)).resample('ME').prod() - 1).loc['2020-07':].corr().round(2).to_string())
print('\n== D. Leva a volatilita\' obiettivo (leva = obiettivo / volatilita\' a 60 giorni, nota il giorno prima; costo: tasso a breve + 1,5% sulla parte presa a prestito)')
for nm, pp in (('ATTUALE 4 sleeve', base.dropna()), (FIN, port)):
    show(f'{nm[:34]}: senza leva', pp)
    for tv, cap in ((0.15, 2.0), (0.15, 4.0), (0.25, 4.0), (0.25, 6.0)):
        Lv = vol_target_leverage(pp, tv, 60, cap); r = scale_returns(pp, Lv, RF, 0.015, 365).iloc[60:]
        t = show(f'{nm[:34]}: vol {tv:.0%}, leva max {cap:g}x (media {Lv.iloc[60:].mean():.2f}x)', r)
        r0 = scale_returns(pp, Lv, RF * 0, 0.0, 365).iloc[60:]; print(f'{"":70s} costo del finanziamento: {100 * (r0.mean() - r.mean()) * 365:.1f}% l\'anno;  mese peggiore {100 * M.monthly(r).min():.1f}%')
print('\n== E. Prove e Deflated Sharpe')
tot = 0; allv = []
for f in sorted(glob.glob(HERE + '/trials_*.json')):
    j = json.load(open(f)); tot += len(j); allv += [v for v in j.values() if v is not None]; print(f'   {os.path.basename(f)}: {len(j)}')
PRIOR = 110 + 12; NPORT = len(P)
n = PRIOR + tot + NPORT
ys = len(port.loc[:SEL_END]) / 365; var = 1.0 / ys
print(f'varianti provate in questo laboratorio (v4): {tot} + {NPORT} portafogli;  precedenti (v5: 110, v3: 12): {PRIOR};  TOTALE: {n}')
for nm, pp in (('ATTUALE 4 sleeve', base.dropna()), (FIN, port)):
    exc = pp - RF.reindex(pp.index)
    print(f'{nm[:40]:40s} Sharpe atteso dal migliore di {n} prove senza abilita\': {M.expected_max_sharpe(n, var):.2f} (con 110: {M.expected_max_sharpe(110, var):.2f});  Sharpe {M.sharpe(pp, RF, 365):.2f};  PSR(>0) {M.psr(exc, 0.0, 365):.3f};  PSR(>0) verifica {M.psr(exc.loc[SPL:], 0.0, 365):.3f};  DSR {M.dsr(exc, n, var, 365):.2f}')
pd.DataFrame(P).to_parquet(HERE + '/portafogli.parquet')
