"""Aggiorna research/v5/quant_v4.json (il file che la dashboard legge) con i numeri corretti dalla quinta e sesta tornata:
profili con debito vero e trade valutati ogni giorno (A10), GERVA Capital originale ricostruito (B8), livello a 30x ritirato (A9),
conteggio delle prove e Deflated Sharpe aggiornati, esito dei 18 analisti. Tutto SIMULATO."""
import json, sys, warnings; warnings.filterwarnings('ignore'); sys.path.insert(0, '/home/user/GERVA-Capital')
import numpy as np, pandas as pd
from gerva.validation import metrics as M
Q = json.load(open('research/v5/quant_v4.json'))
A = pd.read_parquet('research/v5/v5/a10_sistema/returns.parquet'); L = pd.read_parquet('research/v5/v6/b8_confronto/returns.parquet')
rf = pd.read_parquet('research/v5/v4/fondo_serie.parquet').rf.reindex(A.index).fillna(0)
leg = {'senza leva': L['LEG_v3_1x'].reindex(A.index).fillna(0), 'come usato ora (leva 150%)': L['LEG_v33_leva15'].reindex(A.index).fillna(0)}
print('colonne del vecchio sistema:', list(leg))
mm = lambda x: (1 + x).resample('ME').prod() - 1; mrf = mm(rf)
P = {}
for k, v in leg.items(): P['GERVA Capital originale: ' + k] = v
P.update({'B. Libro giornaliero 1x, cassa remunerata': A['B_cassa_in_tbill'], 'B2. Libro giornaliero 2x': A['B2_debito_reale'],
          'C1. Prudente: 1x + trade 11x (0,5%/1%)': A['C1_mtm_limiti'], 'C3. Massimo: 2x + trade 11x (1%/2%)': A['C3_mtm_limiti_debito_reale'],
          'C3 con gli scalini di rischio di oggi': A['C3_motore_di_rischio_attuale']})
def st(x, n):
    m = mm(x); e = m - mrf.reindex(m.index); s = lambda a, b: e[a:b].mean() / e[a:b].std() * np.sqrt(12); eq = (1 + m).cumprod(); d = (1 + x).cumprod()
    return dict(portafoglio=n, sharpe=s(None, None), sh_scelta=s(None, '2022-12-31'), sh_verifica=s('2023-01-01', None), cagr=eq.iloc[-1] ** (12 / len(m)) - 1, vol=m.std() * np.sqrt(12),
                maxdd_mensile=(d / d.cummax() - 1).min(), mese_medio=m.mean(), mese_mediano=m.median(), mese_peggiore=m.min(), mesi_negativi=(m < 0).mean(), mesi_ge10=(m >= .1).mean(), mesi_ge20=(m >= .2).mean())
rng = np.random.default_rng(4)
def mc(x, scen, n=5000, H=36, B=3):
    m = mm(x).values; e = (mm(x) - mrf.reindex(mm(x).index)).mean(); out = []
    for s in rng.integers(0, len(m) - B + 1, (n, H // B)):
        y = np.concatenate([m[a:a + B] for a in s]).copy()
        if scen == 'pessimista': y = y - 0.5 * e
        if scen == 'stress': y = y - (rng.random(H) < 0.03) * 0.15
        eq = np.cumprod(1 + np.maximum(y, -1)); out.append((eq[-1], (eq / np.maximum.accumulate(np.maximum(eq, 1e-9)) - 1).min(), eq.min(), (y >= .2).mean(), (y <= -.1).mean()))
    o = np.array(out); cg = o[:, 0] ** (1 / 3) - 1
    return dict(cagr_p50=np.median(cg), cagr_p05=np.quantile(cg, .05), cagr_p95=np.quantile(cg, .95), dd_p50=np.median(o[:, 1]), dd_p95=np.quantile(o[:, 1], .05), p_meno30=(o[:, 2] <= .7).mean(),
                p_dimezzato=(o[:, 2] <= .5).mean(), mese=(1 + np.median(cg)) ** (1 / 12) - 1, p_mese_ge20=o[:, 3].mean(), p_mese_le10=o[:, 4].mean())
def clean(o):
    if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)): return None if (o != o or abs(o) == np.inf) else round(float(o), 5)
    if isinstance(o, np.integer): return int(o)
    return o
Q['fund_stats'] = [st(x, n) for n, x in P.items()]
Q['fund_mc'] = [dict(mc(x, sc), portafoglio=n, scenario=sc) for n, x in P.items() for sc in ('base', 'pessimista', 'stress')]
W = pd.DataFrame(P).resample('W').apply(lambda x: (1 + x).prod() - 1)
Q['fund_curves'] = {n: [[d.strftime('%Y-%m-%d'), round(float(v), 4)] for d, v in (1 + W[n]).cumprod().items()] for n in P if not n.startswith(('B. ', 'C3 con'))}   # il grafico mostra cinque curve
Q['recommended'] = dict(prudent='C1. Prudente: 1x + trade 11x (0,5%/1%)', maximum='C3. Massimo: 2x + trade 11x (1%/2%)')
TRIALS = 2514 + 9 + 229 + 268 + 134 + 268 + 141 + 188 + 320
yrs = len(A) / 365.25; var = 1 / yrs
Q['trials'] = TRIALS
Q['deflated_sharpe'] = dict(old=M.dsr(A['B_pubblicato'] - rf, TRIALS, var, 365), new=M.dsr(A['B_cassa_in_tbill'] - rf, TRIALS, var, 365), fund=M.dsr(A['C3_mtm_limiti_debito_reale'] - rf, TRIALS, var, 365), threshold=0.95, expected_max=M.expected_max_sharpe(TRIALS, var),
                            note='Varianza nulla teorica 1/anni, rendimenti in eccesso, tutte le 4.071 prove contate. Con la varianza empirica delle prove usata nella quarta tornata i valori sono piu bassi (0,38 a 812 prove). In entrambi i casi sotto la soglia.')
s1, s2, s3 = [[x for x in Q['fund_stats'] if x['portafoglio'].startswith(p)][0] for p in ('B. ', 'B2.', 'C3. Massimo')]
Q['decomposition'].update(portfolio_sharpe=s1['sharpe'], portfolio_sharpe_verify=s1['sh_verifica'], cagr_1x=s1['cagr'], cagr_2x=s2['cagr'], cagr_fund=s3['cagr'])
for r in Q['stop_table']:                                   # prezzi veri dei perpetual (A9): il livello a 30x si dimezza in verifica
    if r['label'] == '1.7%': r['mean_R_verify'] = 0.104; r['note'] = 'Sui perpetual veri; con il funding di Hyperliquid +0,08. Ritirato.'
    if r['label'] == '1.0 x ATR': r['mean_R_verify'] = 0.159; r['note'] = 'Sui perpetual veri; con ordine limite all apertura +0,172.'
ex = [('A1 Indicatore Gervasoni (GQ) come soglia a 11x', 'in osservazione', 'verifica +0,22 R contro +0,13; vantaggio non distinguibile da zero'),
      ('A2 Gestione del trade (piramidare, uscite parziali)', 'scartata', 'nessuna regola scelta fino al 2022 migliora dopo'),
      ('A3 Rotture intraday a stop stretto (30-40x)', 'scartata', 'da -0,07 a -0,68 R dopo i costi'),
      ('A4 Universo ampio (30 perpetual)', 'scartata', '85 trade indipendenti al massimo, R a zero in verifica'),
      ('A5 Indici a leva con VIX sopra 20', 'in osservazione', 'ripete EQ-MR con piu leva: +0,06 / +0,09 R'),
      ('A6 Short delle nuove quotazioni', 'scartata', 'non eseguibile: 20% delle monete su Hyperliquid entro 24 ore'),
      ('A7 Rischio proporzionale alla conviction', 'passa', 'verifica: da 16% a 26% annuo a parita di caduta'),
      ('A8 Modelli statistici (meta-labelling)', 'scartata', 'IC 0,013 in verifica'),
      ('A9 Ordine limite all apertura', 'passa', '+0,013 R per trade; il 30x si dimezza sui perpetual veri'),
      ('B1 Vault HLP di Hyperliquid', 'scartata', '+7,2% in 12 mesi, mese tipico +0,16%: un deposito, non una strategia'),
      ('B1 Copiare i trader migliori', 'scartata', 'nessuna persistenza nei conti copiabili; classifica distorta'),
      ('B2 Alta frequenza e market making', 'scartata', 'vantaggio lordo 0,3-0,5 pb contro 9 pb di costi'),
      ('B3 ETP a leva 3x-5x sugli indici', 'scartata', 'leva ottimale circa 2x, non regge fuori campione'),
      ('B4 Premio di volatilita (short VIX)', 'scartata', 'Sharpe 0,54, coda di -96% in un giorno'),
      ('B5 Azioni tenute solo di notte', 'in osservazione', 'Sharpe 1,12 ma e mercato; alfa sparita dal 2023; fragile sui costi'),
      ('B6 Futures multi-mercato (trend, rotture)', 'scartata', 'Sharpe 0,47; -0,41 in verifica; non praticabile con 10.000 euro'),
      ('B7 Rotazione del funding su tutte le monete', 'scartata', '0,5-0,6% al mese; sotto i titoli di Stato dopo tasse e rischio di sede')]
Q['candidates'] = [c for c in Q['candidates'] if not c['name'][:3] in {e[0][:3] for e in ex}] + [dict(name=n, sharpe=None, sharpe_select=None, sharpe_verify=None, cagr=None, vol=None, maxdd=None, corr_portfolio=None, verdict=v, note=t, by_year={}) for n, v, t in ex]
Q['generated'] = str(pd.Timestamp.now(tz='UTC'))
json.dump(clean(Q), open('research/v5/quant_v4.json', 'w'), ensure_ascii=False)
print('prove', TRIALS, 'DSR', {k: (round(v, 3) if not isinstance(v, str) else '...') for k, v in Q['deflated_sharpe'].items()}); print(pd.DataFrame(Q['fund_stats']).set_index('portafoglio')[['sharpe', 'sh_verifica', 'cagr', 'maxdd_mensile', 'mese_mediano']].round(3).to_string())
print(pd.DataFrame(Q['fund_mc']).query("scenario!='stress'").set_index(['portafoglio', 'scenario'])[['mese', 'dd_p50', 'dd_p95', 'p_dimezzato']].round(3).to_string())
