// Ricerca: tutto ciò che viene dalle simulazioni sui dati storici (research/v5/quant.json). Nulla qui è un conto vero.

import { h, icon, fill } from '../dom.js';
import { card, chip, dataTable, empty, explain, method, segmented, signedPct, simTag, stat, toggle } from '../components.js';
import { bullet, dualBars, histogram, matrix, signedBars, timeChart } from '../charts.js';
import { DASH, arr, fmtDate, fmtNum, fmtPct, fmtPctSigned, fmtSigned, num, obj, parseTs, stepDigits, str } from '../format.js';
import { gloss } from '../glossary.js';

const DAY = 86400000;
const SLEEVES = ['CR-TREND', 'CR-XSMOM', 'EQ-MR', 'MA-TREND'];
const SPLIT = Date.UTC(2023, 0, 1);
const SCENARIOS = [
  { value: 'base', label: 'Base', text: 'la storia si ripete così com\'è' },
  { value: 'pessimista', label: 'Pessimista', text: 'metà del rendimento del backtest' },
  { value: 'stress', label: 'Stress', text: 'rendimenti dimezzati e crisi più frequenti' },
];
const FAN_LEVELS = ['1', '2', '3', '5', '10'];
const mult = (v, d = 2) => (num(v) == null ? DASH : `×${fmtNum(v, d)}`);
const levOf = (schema) => { const m = /^fissa\s+([\d.]+)x$/.exec(str(schema)); return m ? Number(m[1]) : null; };

function legend(items) {
  return h('div', { class: 'legend' }, items.filter(Boolean).map((it) => h('span', { class: `legend__item ${it.end ? 'legend__item--end' : ''}`.trim() },
    h('span', { class: `key key--${it.key}`, 'aria-hidden': 'true' }), h('span', { text: it.label }), it.value == null ? null : h('span', { class: 'num', text: it.value }))));
}

export function mount(root) {
  let ctx = null;
  let key = null;
  const ui = { scenario: 'base', fan: '2', fanLog: false, sleeveLog: true, histLog: false };

  const head = h('div', { class: 'section-head span-12' });
  const missing = h('section', { class: 'card span-12' });

  // ---- leva ----
  const scen = segmented({ label: 'Scenario della simulazione', options: SCENARIOS, value: ui.scenario, onChange: (v) => { ui.scenario = v; paintLeverage(); } });
  const levCard = card({
    title: 'Quanta leva', actions: scen.el, cls: 'span-12', flush: true, sim: true,
    what: 'Più leva del conto vuol dire guadagni più grandi ma anche cadute più grandi. La tabella simula tre anni con leve diverse, migliaia di volte: la colonna «dimezzare il conto» dice in quanti casi su cento il patrimonio è sceso almeno una volta sotto la metà.',
    method: 'Monte Carlo a blocchi (20 giorni) sui rendimenti giornalieri del portafoglio, orizzonte 3 anni. Rovina = minimo ≤ 50% del capitale; azzerato = minimo ≤ 5%. Distanza di liquidazione = 1 / leva massima dello schema.',
  });
  const levTable = dataTable({
    caption: 'Esiti simulati per livello di leva',
    emptyTitle: 'Nessuna simulazione per questo scenario',
    rowClass: (r) => `${r.lev == null ? 'only-esperto' : ''} ${r.mark ? 'is-marked' : ''}`.trim() || null,
    columns: [
      { key: 'schema', label: 'Leva del conto', sort: (r) => (r.lev == null ? 1000 : r.lev), cell: (r) => h('div', { class: 'cell-id' }, h('span', { class: 'code code--strong', text: r.lev == null ? str(r.schema) : `${fmtNum(r.lev, 0)}x` }), r.mark ? h('span', { class: `tag ${r.mark === 'operativa' ? 'tag--paper' : 'tag--sim'}`, text: r.mark }) : null, r.lev == null ? h('span', { class: 'cell-id__name', text: 'a livelli di conviction' }) : null) },
      { key: 'cagr', label: 'Rend. annuo (mediana)', num: true, sort: (r) => num(r.cagr_p50), cell: (r) => signedPct(r.cagr_p50, 1, { arrow: false }) },
      { key: 'cagr05', label: 'Rend. annuo (5° pct)', num: true, cls: 'only-esperto', sort: (r) => num(r.cagr_p05), cell: (r) => signedPct(r.cagr_p05, 1, { arrow: false }) },
      { key: 'dd', label: 'Caduta peggiore', num: true, hide: 'sm', sort: (r) => num(r.maxdd_p50), cell: (r) => (num(r.maxdd_p50) == null ? null : fmtPct(r.maxdd_p50, 1)) },
      {
        key: 'ruin', label: 'Prob. di dimezzare il conto', num: true, cls: 'is-weight', sort: (r) => num(r.p_rovina),
        cell: (r) => { const p = num(r.p_rovina); return p == null ? null : h('div', { class: 'weight' }, bullet({ ratio: p, kind: p >= 0.2 ? 'crit' : p >= 0.02 ? 'warn' : 'ok', label: 'Probabilità di dimezzare il conto' }), h('span', { class: 'weight__value', text: fmtPct(p, 1) })); },
      },
      { key: 'zero', label: 'Prob. di azzerarlo', num: true, cls: 'only-esperto', sort: (r) => num(r.p_azzerato), cell: (r) => (num(r.p_azzerato) == null ? null : fmtPct(r.p_azzerato, 1)) },
      { key: 'month', label: 'Mese medio', num: true, cls: 'only-esperto', sort: (r) => num(r.mese_medio), cell: (r) => signedPct(r.mese_medio, 1, { arrow: false }) },
      { key: 'ge20', label: 'Mesi ≥ +20%', num: true, cls: 'only-esperto', sort: (r) => num(r.p_mese_ge20), cell: (r) => (num(r.p_mese_ge20) == null ? null : fmtPct(r.p_mese_ge20, 1)) },
      { key: 'le20', label: 'Mesi ≤ −20%', num: true, cls: 'only-esperto', sort: (r) => num(r.p_mese_le20), cell: (r) => (num(r.p_mese_le20) == null ? null : fmtPct(r.p_mese_le20, 1)) },
      { key: 'liq', label: 'Dist. liquidazione', num: true, cls: 'only-esperto', sort: (r) => num(r.dist_liq), cell: (r) => (num(r.dist_liq) == null ? null : fmtPct(-num(r.dist_liq), 1)) },
    ],
  });
  const levNote = h('div', { class: 'card__note' });
  levCard.body.append(levTable.el, levNote);

  // ---- ventaglio ----
  const fanSeg = segmented({ label: 'Leva del ventaglio', options: FAN_LEVELS.map((l) => ({ value: l, label: `${l}x` })), value: ui.fan, onChange: (v) => { ui.fan = v; paintFan(); } });
  const fanLog = toggle({ label: 'Scala logaritmica', text: 'Log', onChange: (on) => { ui.fanLog = on; paintFan(); } });
  const fanCard = card({
    title: 'Dove può arrivare il patrimonio in tre anni', actions: [fanSeg.el, fanLog.el], cls: 'span-7', sim: true,
    what: 'Ogni simulazione è un possibile futuro. La linea è il caso di mezzo; la fascia scura contiene metà dei casi, quella chiara nove casi su dieci. Più leva allarga il ventaglio: in alto e, soprattutto, in basso. 1 = il capitale di partenza.',
    method: 'Percentili 5 / 25 / 50 / 75 / 95 del patrimonio simulato (scenario base), campionati ogni 15 giorni.',
  });
  const fanLegend = h('div');
  const fanHost = h('div', { class: 'chart-host' });
  fanCard.body.append(fanLegend, fanHost);
  const fanChart = timeChart(fanHost, { label: 'Ventaglio dei percentili del patrimonio simulato su tre anni. Frecce per scorrere.' });

  // ---- rovina ----
  const ruinCard = card({
    title: 'Rischio di dimezzare il conto, per leva', cls: 'span-5', sim: true,
    what: 'Sull\'asse orizzontale la leva del conto, su quello verticale la probabilità che in tre anni il conto scenda almeno una volta sotto la metà. Fino a 2x–3x la curva resta bassa, poi sale ripida: per questo il fondo opera a 2x e non supera 3x.',
    method: 'Asse x logaritmico, schemi a leva fissa. Tre scenari: base, pessimista (metà del rendimento), stress.',
  });
  const ruinLegend = h('div');
  const ruinHost = h('div', { class: 'chart-host' });
  ruinCard.body.append(ruinLegend, ruinHost);
  const ruinChart = timeChart(ruinHost, { label: 'Probabilità di rovina in funzione della leva, tre scenari. Frecce per scorrere.' });

  // ---- scenari e significatività ----
  const scenCard = card({
    title: 'Che cosa aspettarsi in un anno', cls: 'span-5', sim: true,
    what: 'Quattro esiti possibili del rendimento annuo a leva 2x, dal più favorevole al peggiore. Non sono previsioni: sono i punti di riferimento con cui giudicare ciò che accadrà davvero.',
  });
  const sigCard = card({
    title: 'È una prova? Non ancora', cls: 'span-7', sim: true,
    what: 'Più strategie si provano, più è facile che una sembri buona per puro caso. Qui si confronta il risultato ottenuto con quello che uscirebbe dalla migliore di tante prove a caso.',
    method: 'Deflated Sharpe Ratio (Bailey e López de Prado, 2014): PSR con soglia pari allo Sharpe atteso dal massimo di N prove, N = prove riprodotte + esplorative.',
  });

  // ---- curve delle strategie e correlazioni ----
  const sleeveLog = toggle({ label: 'Scala logaritmica', text: 'Log', pressed: true, onChange: (on) => { ui.sleeveLog = on; paintSleeves(); } });
  const sleeveCard = card({
    title: 'Le quattro strategie nel tempo', actions: sleeveLog.el, cls: 'span-8', sim: true,
    what: 'Come sarebbe cresciuto 1 investito in ciascuna strategia. La linea verticale separa il periodo di scelta (dati usati per decidere le regole) dal periodo di verifica (dati mai usati per decidere): a destra si vede se le regole reggono.',
    method: 'Curve cumulate settimanali al netto dei costi ipotizzati, base 1. Confine scelta/verifica: 1 gennaio 2023.',
  });
  const sleeveLegend = h('div');
  const sleeveHost = h('div', { class: 'chart-host' });
  sleeveCard.body.append(sleeveLegend, sleeveHost);
  const sleeveChart = timeChart(sleeveHost, { label: 'Curve cumulate delle quattro strategie, con il confine tra periodo di scelta e di verifica. Frecce per scorrere.' });

  const corrCard = card({
    title: 'Quanto si muovono insieme', cls: 'span-4', sim: true,
    what: 'Vicino a +1 due strategie guadagnano e perdono negli stessi giorni; vicino a 0 vanno ognuna per conto suo. Più i numeri sono bassi, più mettere insieme le strategie riduce le oscillazioni.',
    method: 'Correlazione di Pearson dei rendimenti giornalieri sull\'intero storico.',
  });

  // ---- pesi e Sharpe mobile ----
  const wCard = card({
    title: 'Come si divide il capitale', cls: 'span-6', sim: true,
    what: 'La quota di capitale assegnata a ogni strategia, mese per mese. Cambia perché a chi oscilla di più va meno capitale: così ogni strategia pesa uguale sul rischio.',
    method: 'Parità di rischio: pesi ∝ 1/volatilità a 180 giorni, ricalcolati a inizio mese, tetto 60%.',
  });
  const wLegend = h('div');
  const wHost = h('div', { class: 'chart-host' });
  wCard.body.append(wLegend, wHost);
  const wChart = timeChart(wHost, { label: 'Quote del capitale per strategia nel tempo, aree impilate. Frecce per scorrere.' });

  const rsCard = card({
    title: 'Sharpe degli ultimi 12 mesi', cls: 'span-6', sim: true,
    what: 'Lo Sharpe calcolato solo sull\'ultimo anno, ricalcolato ogni settimana. Mostra che il risultato non è costante: ci sono anni ottimi e anni vicini allo zero. Sopra la linea tratteggiata l\'anno è stato positivo.',
    method: 'Finestra mobile di 365 giorni sui rendimenti del portafoglio, campionata settimanalmente.',
  });
  const rsHost = h('div', { class: 'chart-host' });
  rsCard.body.append(rsHost);
  const rsChart = timeChart(rsHost, { label: 'Sharpe mobile a un anno del portafoglio simulato. Frecce per scorrere.' });

  // ---- drawdown e istogramma ----
  const ddCard = card({
    title: 'Sotto il massimo', cls: 'span-6', sim: true,
    what: 'Quanto il portafoglio simulato è stato sotto il suo massimo, giorno per giorno. Zero vuol dire nuovo massimo; ogni «buca» è un periodo di perdita da cui è poi risalito. Conta la profondità ma anche la durata.',
    method: 'Drawdown del portafoglio senza leva. Con leva L le cadute sono circa L volte più profonde.',
  });
  const ddHost = h('div', { class: 'chart-host' });
  ddCard.body.append(ddHost);
  const ddChart = timeChart(ddHost, { label: 'Drawdown del portafoglio simulato. Frecce per scorrere.' });

  const histLog = toggle({ label: 'Scala logaritmica', text: 'Log', onChange: (on) => { ui.histLog = on; paintHist(true); } });
  const histCard = card({
    title: 'Come sono distribuiti i giorni', actions: h('span', { class: 'only-esperto' }, histLog.el), cls: 'span-6', sim: true,
    what: 'Ogni colonna conta i giorni con un certo rendimento. La maggior parte sta vicino a zero; le colonne lontane dal centro sono i giorni eccezionali. La linea tratteggiata è la curva «a campana» teorica: i giorni estremi veri sono più frequenti di quanto la campana preveda.',
    method: 'Rendimenti giornalieri del portafoglio in classi da 0,2%. Sovrapposta la normale con la stessa media e deviazione standard; con la scala logaritmica si vedono le code.',
  });
  const histLegend = h('div');
  const histHost = h('div', { class: 'chart-host' });
  histCard.body.append(histLegend, histHost);

  // ---- conviction e robustezza ----
  const convCard = card({
    title: 'La conviction funziona?', cls: 'span-7', sim: true,
    what: 'Per ogni strumento, il rendimento medio del giorno dopo quando la conviction era bassa, media o alta, in punti base. Se le barre crescono dal livello basso a quello alto sia nella scelta sia nella verifica, il punteggio distingue davvero i giorni migliori. La quota di giorni positivi resta comunque vicina a metà.',
    method: 'Rendimento medio a un giorno per livello, in punti base; n = giorni nel livello. Soglie: crypto 0,30/0,60, indici 0,55/0,82.',
  });
  const robCard = card({
    title: 'E se le cose vanno peggio del previsto?', cls: 'span-5', sim: true,
    what: 'Lo Sharpe di ogni strategia in tre casi: come ipotizzato, con costi raddoppiati, con gli ordini eseguiti un giorno in ritardo. Una strategia solida perde poco; una fragile si spegne.',
    method: 'Stesso backtest con commissioni e slippage × 2, e con i pesi applicati con un giorno di ritardo.',
  });

  // ---- scartate e altre evidenze ----
  const rejCard = card({
    title: 'Idee provate e scartate', cls: 'span-12', flush: true, sim: true,
    what: 'Le idee che non hanno superato i controlli, e perché. Sapere che cosa non funziona è importante quanto sapere che cosa funziona: evita di rifare gli stessi errori.',
  });
  const moreCard = card({ title: 'Altre evidenze', cls: 'span-12 only-esperto', sim: true, sub: 'Walk-forward dei parametri del trend e rendimento per quintile di GEX.' });

  const body = h('div', { class: 'grid' }, head, missing, levCard.el, fanCard.el, ruinCard.el, scenCard.el, sigCard.el, sleeveCard.el, corrCard.el,
    wCard.el, rsCard.el, ddCard.el, histCard.el, convCard.el, robCard.el, rejCard.el, moreCard.el);
  root.append(body);
  const cards = [levCard, fanCard, ruinCard, scenCard, sigCard, sleeveCard, corrCard, wCard, rsCard, ddCard, histCard, convCard, robCard, rejCard, moreCard];

  // ---------------------------------------------------------------------------------------------------------------
  const q = () => obj(ctx.quant);
  const series = (rows, k) => arr(rows).map((r) => num(r[k]));
  const times = (rows) => arr(rows).map((r) => parseTs(r.t));

  function paintLeverage() {
    const dec = obj(q().leverage_decision);
    const rows = arr(q().leverage_mc).filter((r) => str(r.scenario) === ui.scenario).map((r) => {
      const lev = levOf(r.schema);
      return { ...r, lev, mark: lev != null && lev === num(dec.operativa) ? 'operativa' : lev != null && lev === num(dec.tetto) ? 'tetto' : null };
    }).sort((a, b) => (a.lev == null ? 1000 : a.lev) - (b.lev == null ? 1000 : b.lev));
    levTable.render(rows);
    const s = SCENARIOS.find((x) => x.value === ui.scenario);
    levCard.setSub(`Scenario ${s.label.toLowerCase()}: ${s.text}. Tre anni simulati migliaia di volte.`);
    fill(levNote, explain(`Il fondo opera a ${fmtNum(dec.operativa, 0)}x (riga «operativa») e non supera ${fmtNum(dec.tetto, 0)}x (riga «tetto»). Guarda come cambia la probabilità di dimezzare il conto passando allo scenario pessimista o di stress.`));
  }

  function paintFan() {
    const fan = obj(q().leverage_fan);
    const lv = obj(obj(fan.levels)[ui.fan]);
    const p50 = arr2(lv.p50);
    const step = num(fan.step_days) || 15;
    const ok = p50.length >= 2;
    fanHost.hidden = !ok;
    if (!ok) { fanChart.update(null); fill(fanLegend, empty('Ventaglio non disponibile')); return; }
    const x = p50.map((_, i) => i * step * DAY);
    const p5 = arr2(lv.p5); const p25 = arr2(lv.p25); const p75 = arr2(lv.p75); const p95 = arr2(lv.p95);
    const last = p50.length - 1;
    const dec = obj(q().leverage_decision);
    const note = Number(ui.fan) === num(dec.operativa) ? 'leva operativa' : Number(ui.fan) === num(dec.tetto) ? 'tetto' : Number(ui.fan) > num(dec.tetto) ? 'oltre il tetto: non usata' : 'sotto la leva operativa';
    fill(fanLegend, legend([
      { key: 'fund', label: 'Caso di mezzo', value: mult(p50[last]) },
      { key: 'fan-inner', label: 'Metà dei casi', value: `${mult(p25[last])} – ${mult(p75[last])}` },
      { key: 'fan-outer', label: '9 casi su 10', value: `${mult(p5[last])} – ${mult(p95[last])}` },
      { key: 'none', label: `${ui.fan}x: ${note}`, end: true },
    ]));
    const years = num(fan.years) || 3;
    const xTicks = [];
    for (let m = 6; m <= years * 12; m += 6) xTicks.push({ t: m * 30.4167 * DAY, label: m % 12 === 0 ? `${m / 12} ${m === 12 ? 'anno' : 'anni'}` : `${m} mesi` });
    fanChart.update({
      x, xTicks,
      panels: [{
        height: 240, scale: ui.fanLog ? 'log' : 'linear', format: (v, st) => `×${fmtNum(v, Math.max(1, stepDigits(st, 2)))}`,
        bands: [{ lo: p5, hi: p95, cls: 'fan-outer' }, { lo: p25, hi: p75, cls: 'fan-inner' }],
        refs: [{ value: 1, label: 'capitale iniziale' }, { value: 0.5, label: 'conto dimezzato' }],
        series: [{ values: p50, cls: 'fund', end: true }],
      }],
      tip: (i) => ({
        title: i === 0 ? 'Oggi' : `Dopo ${fmtNum(i * step / 30.4167, 0)} mesi`,
        rows: [
          { label: '95° percentile', value: mult(p95[i]) }, { label: '75° percentile', value: mult(p75[i]) },
          { key: 'fund', label: 'Mediana', value: mult(p50[i]) },
          { label: '25° percentile', value: mult(p25[i]) }, { label: '5° percentile', value: mult(p5[i]) },
        ],
      }),
      say: (i) => `Dopo ${fmtNum(i * step / 30.4167, 0)} mesi: mediana ${mult(p50[i])}, da ${mult(p5[i])} a ${mult(p95[i])} in nove casi su dieci`,
    });
  }
  const arr2 = (v) => (Array.isArray(v) ? v.map(num) : []);

  function paintRuin() {
    const rows = arr(q().leverage_mc).map((r) => ({ ...r, lev: levOf(r.schema) })).filter((r) => r.lev != null);
    const levs = [...new Set(rows.map((r) => r.lev))].sort((a, b) => a - b);
    const ok = levs.length >= 2;
    ruinHost.hidden = !ok;
    if (!ok) { ruinChart.update(null); fill(ruinLegend, empty('Curva non disponibile')); return; }
    const x = levs.map((l) => Math.log10(l) * 1e9);
    const val = (sc) => levs.map((l) => { const r = rows.find((y) => y.lev === l && str(y.scenario) === sc); return r ? num(r.p_rovina) : null; });
    const data = { base: val('base'), pessimista: val('pessimista'), stress: val('stress') };
    const dec = obj(q().leverage_decision);
    fill(ruinLegend, legend([{ key: 's1', label: 'Base' }, { key: 's2', label: 'Pessimista' }, { key: 's3', label: 'Stress' }]));
    ruinChart.update({
      x, xTicks: levs.map((l, i) => ({ t: x[i], label: `${fmtNum(l, 0)}x` })),
      marks: [num(dec.operativa) ? { t: Math.log10(num(dec.operativa)) * 1e9, label: 'operativa' } : null, num(dec.tetto) ? { t: Math.log10(num(dec.tetto)) * 1e9, label: 'tetto', row: 1 } : null].filter(Boolean),
      panels: [{
        height: 230, bottom: 0, format: (v) => fmtPct(v, 0),
        series: [{ values: data.stress, cls: 's3', dots: true }, { values: data.pessimista, cls: 's2', dots: true }, { values: data.base, cls: 's1', dots: true }],
      }],
      tip: (i) => ({
        title: `Leva del conto ${fmtNum(levs[i], 0)}x`,
        rows: [{ key: 's1', label: 'Base', value: fmtPct(data.base[i], 1) }, { key: 's2', label: 'Pessimista', value: fmtPct(data.pessimista[i], 1) }, { key: 's3', label: 'Stress', value: fmtPct(data.stress[i], 1) }],
        note: 'probabilità di scendere sotto la metà in 3 anni',
      }),
      say: (i) => `Leva ${fmtNum(levs[i], 0)}x: probabilità di dimezzare il conto ${fmtPct(data.base[i], 1)} nello scenario base, ${fmtPct(data.stress[i], 1)} nello stress`,
    });
  }

  function paintScenarios() {
    const rows = arr(q().scenarios).filter((r) => num(r.cagr) != null);
    fill(scenCard.body, rows.length
      ? signedBars(rows.map((r) => ({ label: str(r.nome), value: num(r.cagr), text: fmtPctSigned(r.cagr, 0), note: str(r.definizione) })), { labelHead: 'Scenario', valueHead: 'Rendimento annuo', noteHead: 'Che cos\'è', tone: true })
      : empty('Scenari non disponibili'));
  }

  function paintSignificance() {
    const g = obj(q().significance);
    const dsr = num(g.dsr);
    if (num(g.prove) == null && dsr == null) { fill(sigCard.body, empty('Analisi di significatività non disponibile')); return; }
    const pass = dsr != null && dsr >= 0.95;
    fill(sigCard.body,
      h('div', { class: 'verdict' },
        chip(pass ? { label: 'Supera la soglia', kind: 'ok', icon: 'check' } : { label: 'Non è ancora una prova', kind: 'warn', icon: 'warn' }),
        h('p', { class: 'verdict__text' }, gloss(`Sono state provate ${fmtNum(g.prove, 0)} varianti. Provandone così tante, la migliore avrebbe uno Sharpe di circa ${fmtNum(g.sharpe_atteso_dal_migliore_a_caso, 2)} anche se nessuna funzionasse davvero. Quello ottenuto è ${fmtNum(g.sharpe_tutto, 2)}${pass ? ': abbastanza sopra da reggere a questo esame.' : ': troppo vicino per escludere la fortuna. Il risultato dice che vale la pena verificarlo con il paper trading, non che funzionerà.'}`))),
      h('div', { class: 'tiles__grid tiles__grid--3 sig' },
        stat({ label: 'Prove contate', value: num(g.prove) == null ? null : fmtNum(g.prove, 0), sub: `${fmtNum(g.prove_riprodotte, 0)} riprodotte + ${fmtNum(g.prove_esplorative, 0)} esplorative`, explain: 'Tutte le varianti provate, comprese quelle scartate. Più sono, più severo deve essere il giudizio.' }),
        stat({ label: 'Sharpe atteso dal migliore a caso', value: num(g.sharpe_atteso_dal_migliore_a_caso) == null ? null : fmtNum(g.sharpe_atteso_dal_migliore_a_caso, 2), sub: `ottenuto ${fmtNum(g.sharpe_tutto, 2)}`, explain: 'Lo Sharpe che avrebbe la migliore di tante prove senza alcun valore. È l\'asticella da superare con margine.' }),
        stat({
          label: 'Deflated Sharpe', value: dsr == null ? null : fmtNum(dsr, 2), cls: 'stat--meter',
          sub: [bullet({ ratio: dsr == null ? null : dsr / 0.95, kind: pass ? 'ok' : 'warn', label: 'Deflated Sharpe rispetto alla soglia 0,95' }), h('span', { text: 'soglia 0,95' })],
          explain: 'La probabilità che il risultato sia vero dopo aver tolto l\'effetto delle tante prove. Serve almeno 0,95.',
        })),
      h('div', { class: 'pairs pairs--row only-esperto sig__more' },
        h('span', { class: 'pair' }, h('span', { class: 'pair__label', text: 'Sharpe scelta / verifica' }), h('span', { class: 'pair__value num', text: `${fmtNum(g.sharpe_scelta, 2)} / ${fmtNum(g.sharpe_verifica, 2)}` })),
        h('span', { class: 'pair' }, h('span', { class: 'pair__label', text: 'Errore standard dello Sharpe' }), h('span', { class: 'pair__value num', text: `±${fmtNum(g.errore_standard_sharpe, 2)}` })),
        h('span', { class: 'pair' }, h('span', { class: 'pair__label', text: 'PSR (Sharpe > 0) tutto / verifica' }), h('span', { class: 'pair__value num', text: `${fmtPct(g.psr_zero, 1)} / ${fmtPct(g.psr_zero_verifica, 1)}` })),
        h('span', { class: 'pair' }, h('span', { class: 'pair__label', text: 'Varianza degli Sharpe delle prove' }), h('span', { class: 'pair__value num', text: fmtNum(g.varianza_sharpe_prove, 3) }))));
  }

  function paintSleeves() {
    const rows = arr(q().sleeve_curves);
    const x = times(rows);
    const ok = rows.length >= 2 && x.every((t) => t != null);
    sleeveHost.hidden = !ok;
    if (!ok) { sleeveChart.update(null); fill(sleeveLegend, empty('Curve non disponibili')); return; }
    const data = SLEEVES.map((id) => series(rows, id));
    const last = rows.length - 1;
    fill(sleeveLegend, legend(SLEEVES.map((id, k) => ({ key: `s${k + 1}`, label: id, value: mult(data[k][last], 1) }))));
    sleeveChart.update({
      x, marks: [{ t: SPLIT, label: 'verifica →' }],
      panels: [{
        height: 270, scale: ui.sleeveLog ? 'log' : 'linear', format: (v, st) => `×${fmtNum(v, stepDigits(st, 1))}`,
        series: SLEEVES.map((id, k) => ({ values: data[k], cls: `s${k + 1}`, end: true })),
      }],
      tip: (i) => ({
        title: `${fmtDate(x[i], true)} · ${x[i] < SPLIT ? 'periodo di scelta' : 'periodo di verifica'}`,
        rows: SLEEVES.map((id, k) => ({ key: `s${k + 1}`, label: id, value: mult(data[k][i]) })),
      }),
      say: (i) => `${fmtDate(x[i], true)}: ${SLEEVES.map((id, k) => `${id} ${mult(data[k][i])}`).join(', ')}`,
    });
  }

  function paintCorr() {
    const c = obj(q().correlation);
    const labels = Array.isArray(c.labels) ? c.labels.map(str) : [];
    const m = Array.isArray(c.matrix) ? c.matrix : [];
    if (labels.length < 2 || m.length < labels.length) { fill(corrCard.body, empty('Correlazioni non disponibili')); return; }
    const off = [];
    for (let i = 0; i < labels.length; i++) for (let j = i + 1; j < labels.length; j++) if (num((m[i] || [])[j]) != null) off.push(num(m[i][j]));
    const avg = off.length ? off.reduce((a, b) => a + b, 0) / off.length : null;
    fill(corrCard.body, matrix(labels, m, { caption: 'Correlazione tra i rendimenti giornalieri delle strategie' }),
      h('div', { class: 'hm-legend', 'aria-hidden': 'true' }, h('span', { class: 'num', text: '−1' }),
        [-1, -0.5, 0, 0.5, 1].map((k) => h('span', { class: `hm-legend__swatch ${k > 0 ? 'hm__cell--cool' : k < 0 ? 'hm__cell--warm' : ''}`.trim(), style: { '--k': Math.abs(k) } })),
        h('span', { class: 'num', text: '+1' }), h('span', { class: 'hm-legend__note', text: avg == null ? '' : `media fuori diagonale ${fmtSigned(avg, 2)}` })));
  }

  function paintWeights() {
    const rows = arr(q().weights);
    const x = times(rows);
    const ok = rows.length >= 2 && x.every((t) => t != null);
    wHost.hidden = !ok;
    if (!ok) { wChart.update(null); fill(wLegend, empty('Quote non disponibili')); return; }
    const data = SLEEVES.map((id) => series(rows, id).map((v) => v ?? 0));
    const bands = [];
    let base = data[0].map(() => 0);
    SLEEVES.forEach((id, k) => {
      const topLine = base.map((b, i) => b + data[k][i]);
      bands.push({ lo: base, hi: topLine, cls: `s${k + 1}` });
      base = topLine;
    });
    const last = rows.length - 1;
    fill(wLegend, legend(SLEEVES.map((id, k) => ({ key: `s${k + 1}`, label: id, value: fmtPct(data[k][last], 0) }))));
    wChart.update({
      x,
      panels: [{ height: 200, top: 1, bottom: 0, format: (v) => fmtPct(v, 0), bands, series: [] }],
      tip: (i) => ({ title: fmtDate(x[i], true), rows: SLEEVES.map((id, k) => ({ key: `s${k + 1}`, label: id, value: fmtPct(data[k][i], 1) })) }),
      say: (i) => `${fmtDate(x[i], true)}: ${SLEEVES.map((id, k) => `${id} ${fmtPct(data[k][i], 0)}`).join(', ')}`,
    });
  }

  function paintLine(chart, host, rows, opts) {
    const x = times(rows);
    const y = series(rows, 'v');
    const ok = rows.length >= 2 && x.every((t) => t != null);
    host.hidden = !ok;
    if (!ok) { chart.update(null); return; }
    chart.update({
      x, marks: [{ t: SPLIT, label: 'verifica →' }],
      panels: [{ height: 190, ...opts.panel, series: [{ values: y, cls: opts.cls, area: opts.area, end: !opts.area }] }],
      tip: (i) => ({ title: fmtDate(x[i], true), rows: [{ key: opts.cls, label: opts.what, value: opts.fmt(y[i]) }] }),
      say: (i) => `${fmtDate(x[i], true)}: ${opts.what} ${opts.fmt(y[i])}`,
    });
  }

  function paintHist(force = false) {
    const d = obj(q().return_hist);
    const r = histogram(histHost, d, { log: ui.histLog, label: 'Istogramma dei rendimenti giornalieri del portafoglio simulato con la curva normale sovrapposta' });
    if (!r) { fill(histHost, empty('Distribuzione non disponibile')); fill(histLegend); return; }
    if (force) return;
    fill(histLegend, legend([
      { key: 'col', label: 'Giorni osservati', value: fmtNum(r.total, 0) },
      { key: 'dash', label: 'Curva normale' },
      { key: 'none', label: `media ${fmtPctSigned(r.mean, 2)} · dev. std ${fmtPct(r.sd, 2)}`, end: true },
    ]));
  }

  function paintConviction() {
    const rows = arr(q().conviction);
    const assets = [...new Set(rows.map((r) => str(r.asset)))];
    if (!assets.length) { fill(convCard.body, empty('Analisi della conviction non disponibile')); return; }
    const out = [];
    for (const a of assets) {
      for (const tier of ['bassa', 'media', 'alta']) {
        const sc = rows.find((r) => str(r.asset) === a && str(r.tier) === tier && str(r.periodo) === 'scelta') || {};
        const ve = rows.find((r) => str(r.asset) === a && str(r.tier) === tier && str(r.periodo) === 'verifica') || {};
        out.push({
          name: h('span', null, tier === 'bassa' ? h('span', { class: 'code code--strong', text: a }) : h('span', { class: 'bars__indent', text: a }), ` · ${tier}`), group: tier === 'bassa',
          a: num(sc.media_pb), b: num(ve.media_pb),
          aText: num(sc.media_pb) == null ? null : `${fmtSigned(sc.media_pb, 1)} pb`, bText: num(ve.media_pb) == null ? null : `${fmtSigned(ve.media_pb, 1)} pb`,
          extra: `${num(sc.hit) == null ? DASH : fmtPct(sc.hit, 0)} / ${num(ve.hit) == null ? DASH : fmtPct(ve.hit, 0)}`,
        });
      }
    }
    fill(convCard.body, dualBars(out, { nameHead: 'Strumento · livello', aHead: 'Scelta', bHead: 'Verifica', extraHead: 'Giorni positivi' }),
      explain('«Giorni positivi» è la quota di giorni chiusi in guadagno (scelta / verifica): resta intorno al 50% anche al livello alto. La conviction non indovina i giorni: sposta di poco le probabilità, e su molti giorni quel poco conta.'));
  }

  function paintRobust() {
    const rb = obj(q().robustness);
    const names = Object.keys(rb);
    if (!names.length) { fill(robCard.body, empty('Prove di robustezza non disponibili')); return; }
    const cell = (v, base) => {
      const n = num(v);
      const weak = n != null && (n <= 0 || (num(base) > 0 && n < 0.5 * num(base)));
      return h('td', { class: `num ${weak ? 'is-weak' : ''}`.trim() }, n == null ? DASH : fmtNum(n, 2), weak ? icon('warn') : null);
    };
    fill(robCard.body, h('table', { class: 'mini mini--wide' },
      h('thead', null, h('tr', null, h('th', { scope: 'col', text: 'Sharpe' }), h('th', { scope: 'col', class: 'num', text: 'Base' }), h('th', { scope: 'col', class: 'num', text: 'Costi doppi' }), h('th', { scope: 'col', class: 'num', text: 'Ritardo di 1 giorno' }))),
      h('tbody', null, names.map((k) => { const r = obj(rb[k]); return h('tr', { class: k === 'PORTAFOGLIO' ? 'mini__total' : null }, h('th', { scope: 'row' }, k === 'PORTAFOGLIO' ? 'Portafoglio' : h('span', { class: 'code', text: k })), h('td', { class: 'num', text: num(r.base) == null ? DASH : fmtNum(r.base, 2) }), cell(r.costi_doppi, r.base), cell(r.ritardo_1g, r.base)); }))),
      explain('Il triangolo segnala i casi in cui lo Sharpe si dimezza o diventa negativo: lì la strategia dipende molto da costi bassi o da un\'esecuzione puntuale.'));
  }

  function paintRejected() {
    const rows = arr(q().rejected);
    fill(rejCard.body, rows.length
      ? h('div', { class: 'table-wrap' }, h('table', { class: 'table' }, h('caption', { class: 'sr-only', text: 'Idee provate e scartate, con il motivo' }),
        h('thead', null, h('tr', null, h('th', { scope: 'col', text: 'Idea' }), h('th', { scope: 'col', text: 'Perché è stata scartata' }))),
        h('tbody', null, rows.map((r) => h('tr', null, h('td', { class: 'is-strong' }, icon('x', 'rej__icon'), h('span', { text: str(r.nome) || DASH })), h('td', { class: 'is-wrap', text: str(r.esito) || DASH }))))))
      : empty('Nessuna idea scartata in elenco'));
  }

  function paintMore() {
    const wf = obj(q().walk_forward);
    const choices = Object.entries(obj(wf.scelte));
    const gex = arr(q().gex_quintiles);
    const trials = Object.keys(obj(q().trials)).length;
    fill(moreCard.body, h('div', { class: 'more-grid' },
      h('div', null, h('h3', { class: 'subhead', text: 'Walk-forward del trend crypto' }),
        choices.length ? h('table', { class: 'mini' }, h('thead', null, h('tr', null, h('th', { scope: 'col', text: 'Anno' }), h('th', { scope: 'col', class: 'num', text: 'Finestre scelte (giorni)' }))),
          h('tbody', null, choices.map(([y, c]) => h('tr', null, h('th', { scope: 'row', class: 'num', text: y }), h('td', { class: 'num', text: str(c) }))))) : h('p', { class: 'muted', text: 'Non disponibile.' }),
        h('p', { class: 'method' }, `Parametri scelti ogni anno solo sui dati precedenti. Sharpe medio in addestramento ${fmtNum(wf.sharpe_addestramento_medio, 2)}; prove in registro: ${fmtNum(trials, 0)}.`)),
      h('div', null, h('h3', { class: 'subhead', text: 'Rendimento del giorno dopo per quintile di GEX' }),
        gex.length ? h('div', { class: 'table-wrap' }, h('table', { class: 'mini mini--wide' }, h('thead', null, h('tr', null, h('th', { scope: 'col', text: 'Quintile' }), h('th', { scope: 'col', class: 'num', text: 'n' }), h('th', { scope: 'col', class: 'num', text: 'Media (pb)' }), h('th', { scope: 'col', class: 'num', text: 't' }), h('th', { scope: 'col', class: 'num', text: 'Vol annua' }), h('th', { scope: 'col', class: 'num', text: 'Giorno peggiore' }))),
          h('tbody', null, gex.map((g) => h('tr', null, h('th', { scope: 'row', text: str(g.q) }), h('td', { class: 'num', text: fmtNum(g.n, 0) }), h('td', { class: 'num', text: fmtSigned(g.media_pb, 1) }), h('td', { class: 'num', text: fmtSigned(g.t, 2) }), h('td', { class: 'num', text: fmtPct(g.vol_annua, 1) }), h('td', { class: 'num', text: fmtPct(g.peggiore, 1) })))))) : h('p', { class: 'muted', text: 'Non disponibile.' }),
        h('p', { class: 'method', text: 'Il GEX ordina la volatilità (alta con GEX basso), non la direzione: per questo è stato scartato come segnale.' }))));
  }

  function paintAll() {
    const has = !!ctx.quant;
    for (const c of cards) c.el.hidden = !has;
    missing.hidden = has;
    if (!has) {
      fill(head, h('h2', { class: 'section-head__title', text: 'Ricerca sui dati storici' }), simTag(''));
      const st = ctx.quantStatus;
      fill(missing, st === 'loading' ? empty('Caricamento della ricerca…')
        : empty('Ricerca non disponibile', st === 'missing' ? 'Il file research/v5/quant.json non c\'è: si genera con la ricerca (python -m gerva research).' : 'Il file della ricerca non si legge. Nuovo tentativo tra un minuto.'));
      key = null;
      return;
    }
    const gen = parseTs(q().generated);
    fill(head,
      h('h2', { class: 'section-head__title', text: 'Ricerca sui dati storici' }), simTag(q().label),
      h('span', { class: 'section-head__meta num', text: gen == null ? '' : `generata il ${fmtDate(gen)}` }),
      explain('Tutto in questa pagina è simulato: mostra che cosa sarebbe successo applicando le regole ai dati del passato, con costi ipotizzati. Serve a decidere e a dimensionare il rischio, non a promettere risultati.'),
      method('Backtest giornaliero 2018–2026 al netto di commissioni e slippage; periodo di scelta fino al 2022, periodo di verifica dal 2023. I numeri del conto vero stanno nelle altre sezioni.'));
    paintLeverage(); paintFan(); paintRuin(); paintScenarios(); paintSignificance(); paintSleeves(); paintCorr(); paintWeights();
    paintLine(rsChart, rsHost, arr(q().rolling_sharpe), { cls: 'fund', what: 'Sharpe a 12 mesi', fmt: (v) => fmtNum(v, 2), panel: { refs: [{ value: 0, label: '' }], format: (v, st) => fmtNum(v, Math.max(1, stepDigits(st, 2))) } });
    paintLine(ddChart, ddHost, arr(q().drawdown), { cls: 'dd', area: true, what: 'Drawdown', fmt: (v) => fmtPct(v, 2), panel: { top: 0, format: (v, st) => fmtPct(v, stepDigits((st ?? 1) * 100, 2)) } });
    paintHist(); paintConviction(); paintRobust(); paintRejected(); paintMore();
  }

  return {
    update(next) {
      ctx = next;
      const k = `${ctx.quantStatus}|${ctx.quant ? str(ctx.quant.generated) + JSON.stringify(ctx.quant).length : ''}`;
      if (k === key) return;                      // la ricerca è statica: si ridisegna solo se cambia il file
      key = k;
      paintAll();
    },
    summary(c) {
      const quant = obj(c.quant);
      const pf = obj(obj(quant.portfolio).tutto);
      const dec = obj(quant.leverage_decision);
      const two = arr(quant.leverage_mc).find((r) => levOf(r.schema) === num(dec.operativa) && str(r.scenario) === 'base');
      if (num(pf.cagr) == null) return 'I risultati della ricerca sui dati storici non sono disponibili in questo momento.';
      return `Nelle simulazioni sul passato il portafoglio senza leva ha reso il ${fmtPct(pf.cagr, 0)} l'anno con una caduta peggiore del ${fmtPct(Math.abs(num(pf.max_dd)), 0)}${two ? `; a leva ${fmtNum(dec.operativa, 0)}x il caso di mezzo rende il ${fmtPct(two.cagr_p50, 0)} e la probabilità di dimezzare il conto in tre anni è ${fmtPct(two.p_rovina, 1)}` : ''}. Sono risultati simulati: non ancora una prova.`;
    },
  };
}
