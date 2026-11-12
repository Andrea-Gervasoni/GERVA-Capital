// Spazio «Evidenza»: la vista da due minuti per chi non si fida. Il vantaggio è vero?
// In quest'ordine: verdetto a parole · come sarebbe andato (profili, confine scelta | verifica) · quanto può essere fortuna ·
// il paper sopra il cono dell'atteso · quanto in basso può scendere · contro il sistema originale (imbuto del caso, z) ·
// profili (mese medio contro mediano) · strategie provate · leva per trade e stress · sedi.
// Ogni riquadro dichiara la provenienza (SIMULATO / PAPER / ESEMPIO); paper e simulato non entrano mai nella stessa cifra.
// Soglie, scalini e criteri arrivano dai dati (quant_v4.json, /api/v1/compare via derive.js): nessuno è scritto qui.

import { fanChart } from '../chart-engine.js';
import { timeChart } from '../charts.js';
import { segmented } from '../components.js';
import { h, icon } from '../dom.js';
import { arr, fmtDate, fmtNum, fmtPct, fmtPctSigned, fmtSigned, list, num, obj, parseTs, str } from '../format.js';
import { getCompare } from '../market.js';
import { SPLIT_T, compareStats, coneData, drawdownSeries, luck, provenanceDays } from '../derive.js';
import { emptyState, meterRow, panel, provOf, provTag } from '../panels.js';
import { colHist, factRow, legendRow, luckChart, nd, plot, rangeBar, simpleTable, stateChip, statWell, yearStrip } from './kit.js';

const VERDICTS = [
  [/^passa$/i, 'ok', 'Passa'], [/^passa /i, 'warn', null], [/osservazione/i, 'accent', 'In osservazione'], [/ipotesi/i, 'unknown', 'Ipotesi'], [/scartat/i, 'muted', 'Scartata'],
];
const verdictChip = (v) => { const m = VERDICTS.find(([re]) => re.test(str(v))); const text = m && m[2] ? m[2] : str(v).replace(/^./, (c) => c.toUpperCase()); return stateChip(m ? m[1] : 'muted', text, { iconName: m && m[1] === 'muted' ? 'x' : '' }); };
const short = (name) => str(name).replace(/^GERVA Capital /, '').replace(/^([A-C]\d?)\. /, '$1 · ').replace(/^originale: /, 'Originale: ');
const pc = (v, d = 1) => (num(v) == null ? null : fmtPct(v, d));
const ps = (v, d = 1) => (num(v) == null ? null : fmtPctSigned(v, d));
const n2 = (v, d = 2) => (num(v) == null ? null : fmtNum(v, d));
const SCEN = [{ value: 'base', label: 'Base' }, { value: 'pessimista', label: 'Pessimista' }, { value: 'stress', label: 'Stress' }];

export function mount(root) {
  let ctxNow = null;
  let cmp;                       // undefined = in arrivo, null = assente
  let range = 'all';
  let horizon = 0;
  let scenario = 'base';
  let candAll = false;
  let liqWin = 'p_liq_24h';
  let tierScen = 'base';

  // ---- 1. verdetto ----
  const pVerdict = panel({ title: 'Verdetto', eyebrow: 'Evidenza in due minuti', span: 12, cls: 'sp-verdict', id: 'verdetto',
    what: 'Il giudizio in una riga, costruito dai numeri qui sotto: quante varianti sono state provate, se il risultato regge dopo aver tolto l\'effetto delle tante prove, quanti giorni di paper esistono. «Track record» vale solo per il denaro reale: qui non c\'è.' });
  const vTitle = h('p', { class: 'sp-verdict__title' });
  const vText = h('p', { class: 'sp-verdict__text' });
  const vDays = h('dl', { class: 'sp-verdict__days' });
  pVerdict.body.append(h('div', { class: 'sp-verdict__grid' }, h('div', null, vTitle, vText), vDays));

  // ---- 2. come sarebbe andato ----
  const rangeSeg = segmented({ label: 'Periodo', options: [{ value: 'all', label: 'Tutto' }, { value: 'verify', label: 'Dal 2023' }], value: range, onChange: (v) => { range = v; paintCurves(); } });
  const pCurve = panel({ title: 'Come sarebbe andato, e con quali cadute?', eyebrow: 'Profili · storia simulata', span: 8, tools: rangeSeg.el, id: 'profili-curve',
    ask: 'Ogni linea è un profilo del fondo ricostruito sulla storia, partito da 100. A sinistra della riga verticale i dati su cui le regole sono state scelte; a destra quelli mai usati per sceglierle: è lì che si guarda.',
    what: 'Curve simulate, al netto dei costi ipotizzati, in scala logaritmica: a pari pendenza, pari rendimento. Tutte tratteggiate perché nessuna è stata vissuta davvero. Sotto, la caduta dal massimo del profilo prudente con gli scalini del motore di rischio.' });
  const curveFacts = h('div');
  const curvePlot = plot();
  const curveLegend = h('div');
  pCurve.body.append(curveFacts, curvePlot.el, curveLegend);
  const curveChart = timeChart(curvePlot.host, { label: 'Profili simulati a base 100 e caduta dal massimo', table: true });

  // ---- 3. fortuna ----
  const pLuck = panel({ title: 'Quanto può essere fortuna?', eyebrow: 'Prove multiple', span: 4, id: 'fortuna',
    ask: 'Provando migliaia di varianti, la migliore sembra buona anche se nessuna funziona. La riga verticale è quanto buona sembrerebbe per puro caso.',
    what: 'Il Deflated Sharpe è la probabilità che il risultato sia vero dopo aver tolto l\'effetto di tutte le prove fatte. È mostrato come intervallo perché dipende dal metodo e dal portafoglio su cui lo si calcola: finché tutto l\'intervallo non supera la soglia, il vantaggio è promettente ma non provato.' });
  const luckBig = h('div', { class: 'bignum' });
  const luckPlot = plot();
  const luckBox = h('div', { class: 'sp-luckbox' });
  const luckKv = h('div', { class: 'kv not-semplice' });
  const luckVerdict = h('div', { class: 'verdict' });
  pLuck.body.append(luckBig, luckPlot.el, luckBox, luckKv, luckVerdict);
  const luckViz = luckChart(luckPlot.host, { label: 'Sharpe di una prova senza abilità, il migliore di tante, e lo Sharpe misurato' });

  // ---- 4. cono ----
  const hzSeg = segmented({ label: 'Orizzonte', options: [{ value: 0, label: 'Paper' }, { value: 12, label: '1 anno' }, { value: 36, label: '3 anni' }], value: horizon, onChange: (v) => { horizon = v; paintCone(); } });
  const pCone = panel({ title: 'Il paper va come previsto?', eyebrow: 'Atteso contro reale', span: 6, tools: hzSeg.el, id: 'cono',
    ask: 'La fascia è ciò che le simulazioni considerano normale; la linea piena è il conto. Dentro la fascia: tutto come previsto.',
    what: 'Ventaglio del profilo esatto del paper: fascia larga dal 5° al 95° percentile, fascia stretta dal 25° al 75°, mediana tratteggiata. Il percorso del conto è la linea piena sopra. Il percentile dice dove si trova oggi il conto rispetto ai percorsi simulati alla stessa data.' });
  const coneBig = h('div', { class: 'bignum' });
  const conePlot = plot();
  const coneFacts = h('div', { class: 'not-semplice' });
  pCone.body.append(coneBig, conePlot.el, coneFacts);
  const coneChart = fanChart(conePlot.host, { label: 'Ventaglio atteso del profilo del paper e percorso del conto', table: true });

  // ---- 5. distribuzione della caduta ----
  const pDD = panel({ title: 'Quanto in basso può scendere in tre anni?', eyebrow: 'Distribuzione della caduta', span: 6, id: 'caduta',
    ask: 'Ogni colonna conta i percorsi simulati che, nel loro momento peggiore, hanno toccato quella caduta. Le righe sono i freni del motore: a destra di ognuna c\'è la quota di percorsi in cui sarebbe scattato.',
    what: 'Caduta massima dal picco su tre anni, per ogni percorso del Monte Carlo del profilo del paper, con il motore di rischio applicato. La perdita cresce verso destra. Gli scalini sono quelli del profilo simulato, letti dal file della ricerca.' });
  const ddBig = h('div', { class: 'bignum' });
  const ddPlot = plot();
  const ddFacts = h('div');
  pDD.body.append(ddBig, ddPlot.el, ddFacts);
  const ddChart = colHist(ddPlot.host, { label: 'Distribuzione della caduta massima a tre anni' });

  // ---- 6. contro l'originale ----
  const pCmp = panel({ title: 'Batte davvero l\'originale, o è ancora il caso?', eyebrow: 'Confronto con il sistema originale', span: 12, id: 'originale',
    ask: 'A sinistra i due conti partiti da 100 nel primo giorno comune. A destra il vantaggio del nuovo sommato giorno per giorno, a parità di rischio: finché la linea resta dentro l\'imbuto, nessuno dei due ha battuto l\'altro.',
    what: 'Il distacco cumulato è la somma delle differenze giornaliere dei rendimenti, ciascuno diviso per la propria volatilità. L\'imbuto è quanto quella somma può allontanarsi dallo zero per puro caso. z è il distacco in unità di errore standard: oltre la soglia il motore di confronto dichiara un vincitore, ma solo dopo il numero minimo di giorni comuni.' });
  const cmpFacts = h('div');
  const cmpA = plot();
  const cmpB = plot();
  const cmpNeed = h('div');
  const cmpEmpty = h('div');
  const cmpGrid = h('div', { class: 'sp-two' }, h('div', null, h('div', { class: 'sp-sub', text: 'I due conti, base 100' }), cmpA.el), h('div', null, h('div', { class: 'sp-sub', text: 'Distacco cumulato a pari volatilità' }), cmpB.el));
  pCmp.body.append(cmpFacts, cmpEmpty, cmpGrid, cmpNeed);
  const cmpChart = timeChart(cmpA.host, { label: 'Nuovo sistema e sistema originale a base 100', table: true });
  const funnel = fanChart(cmpB.host, { label: 'Distacco cumulato a pari volatilità dentro l\'imbuto del caso' });

  // ---- 7. profili ----
  const scenSeg = segmented({ label: 'Scenario del Monte Carlo', options: SCEN, value: scenario, onChange: (v) => { scenario = v; paintProfiles(); } });
  const pProf = panel({ title: 'Quale profilo, e che cosa ci si può aspettare?', eyebrow: 'Profili', span: 12, tools: h('div', { class: 'not-semplice' }, scenSeg.el), id: 'profili',
    ask: 'Guarda il mese mediano, non quello medio: metà dei mesi rende meno della mediana. La media è tirata su da pochi mesi molto buoni.',
    what: 'Ogni riga è un modo di usare lo stesso motore: senza leva, con leva, con o senza il libro dei trade. Lo Sharpe è diviso tra periodo di scelta (fino al 2022) e di verifica (dal 2023). Le colonne del Monte Carlo dicono che cosa aspettarsi in tre anni nello scenario scelto: base, pessimista (metà del vantaggio) o stress.' });
  const profBox = h('div');
  pProf.body.append(profBox);

  // ---- 8. strategie provate ----
  const candSeg = segmented({ label: 'Quali idee mostrare', options: [{ value: 'kept', label: 'Rimaste' }, { value: 'all', label: 'Tutte' }], value: 'kept', onChange: (v) => { candAll = v === 'all'; paintCand(); } });
  const pCand = panel({ title: 'Che cosa è stato provato, e che cosa è rimasto?', eyebrow: 'Strategie provate', span: 12, tools: candSeg.el, id: 'provate',
    ask: 'Quasi tutto viene scartato: è il comportamento sano. Un\'idea resta solo se regge anche sui dati mai usati per sceglierla.',
    what: 'Ogni idea di strategia provata dalla ricerca, con l\'esito e il motivo. La striscia mostra lo Sharpe anno per anno: blu positivo, arancio negativo, con il numero in ogni cella; lo stacco separa gli anni di scelta da quelli di verifica. Una striscia a macchie alterne è un vantaggio che non tiene.' });
  const candFacts = h('div');
  const candBox = h('div');
  pCand.body.append(candFacts, candBox);

  // ---- 9. leva per trade ----
  const pLev = panel({ title: 'Quanta leva regge un singolo trade?', eyebrow: 'Leva per trade', span: 8, cls: 'not-semplice', id: 'leva',
    what: 'Per ogni distanza dello stop: la leva che ne deriva, quanti trade nella storia, quanto rende in media un trade in R (1 R = ciò che rischiava), lo stesso sul periodo di verifica, e quanto pesano i costi. Più lo stop è stretto, più la leva è alta e più i costi mangiano il risultato.' });
  const levBox = h('div');
  pLev.body.append(levBox);
  const liqSeg = segmented({ label: 'Finestra senza stop', options: [{ value: 'p_liq_1h', label: '1 ora' }, { value: 'p_liq_4h', label: '4 ore' }, { value: 'p_liq_24h', label: '24 ore' }], value: liqWin, onChange: (v) => { liqWin = v; paintStress(); } });
  const pStress = panel({ title: 'E se lo stop non viene eseguito?', eyebrow: 'Stress della leva', span: 4, cls: 'not-semplice', tools: liqSeg.el, id: 'stress-leva',
    what: 'Se la sede non risponde e lo stop resta ineseguito per la finestra scelta, questa è la probabilità storica che il prezzo arrivi fino alla liquidazione, per moneta e per leva. È il motivo per cui la leva del trade ha un tetto.' });
  const stressPlot = plot();
  const stressLegend = h('div');
  const stressTable = h('div');
  pStress.body.append(stressPlot.el, stressLegend, stressTable);
  const stressChart = timeChart(stressPlot.host, { label: 'Probabilità di liquidazione senza stop, per leva' });
  const tierSeg = segmented({ label: 'Scenario', options: [...SCEN.slice(0, 2), { value: 'verifica', label: 'Verifica' }, SCEN[2]], value: tierScen, onChange: (v) => { tierScen = v; paintTier(); } });
  const pTier = panel({ title: 'Quanto rischiare per trade?', eyebrow: 'Schemi di rischio', span: 12, cls: 'not-semplice', tools: tierSeg.el, id: 'schemi',
    what: 'Ogni schema fissa la leva e la quota di patrimonio rischiata nei trade confermati ed eccezionali. Il Monte Carlo dice rendimento e caduta attesi a tre anni nello scenario scelto. La riga evidenziata è lo schema in uso nel paper.' });
  const tierBox = h('div');
  pTier.body.append(tierBox);

  // ---- 10. sedi ----
  const pVenues = panel({ title: 'Dove si può operare, e con quali limiti?', eyebrow: 'Sedi', span: 12, cls: 'not-semplice', id: 'sedi',
    what: 'Le sedi valutate: stato legale per un residente in Italia, leva massima, commissioni, rischi propri e ruolo nel fondo. È ricerca documentale, non un dato di mercato.' });
  const venuesBox = h('div');
  pVenues.body.append(venuesBox);

  root.append(h('div', { class: 'ws sp-ws' }, pVerdict.el, pCurve.el, pLuck.el, pCone.el, pDD.el, pCmp.el, pProf.el, pCand.el, pLev.el, pStress.el, pTier.el, pVenues.el));

  // ---- disegno ----
  const q4 = () => obj(ctxNow.quant4);
  const missing = (what) => emptyState(ctxNow.quant4Status === 'loading' ? 'Ricerca in lettura…' : `${what} non disponibile`, ctxNow.quant4Status === 'loading' ? '' : 'Manca o non si legge il file della ricerca (research/v5/quant_v4.json). Lo spazio resta: i riquadri lo dicono.');

  function paintVerdict() {
    const { snap } = ctxNow;
    const L = luck(ctxNow.quant4);
    const pd = provenanceDays(snap, ctxNow.quant4);
    const demo = provOf(snap.meta) === 'demo';
    const gen = parseTs(str(q4().generated).replace(' ', 'T').replace(/(\.\d+)?\+00:00$/, 'Z'));
    if (!L) { vTitle.textContent = ctxNow.quant4Status === 'loading' ? 'Ricerca in lettura…' : 'Ricerca non disponibile.'; vText.textContent = 'Senza il file della ricerca il verdetto non si può formulare.'; }
    else {
      vTitle.textContent = L.pass ? 'Regge all\'esame delle prove.' : 'Promettente, non provato.';
      vText.replaceChildren(`Il vantaggio viene da simulazioni sulla storia. Dopo ${fmtNum(L.trials, 0)} prove contate, la probabilità che sia vero (Deflated Sharpe) sta tra ${fmtNum(L.lo, 2)} e ${fmtNum(L.hi, 2)}: `,
        h('b', { text: L.pass ? `sopra la soglia di ${fmtNum(L.threshold, 2)}` : `sotto la soglia di ${fmtNum(L.threshold, 2)}` }), '. ',
        pd.paper != null ? `Il paper è al giorno ${fmtNum(pd.paper, 0)}${pd.paperTarget ? ` di ${fmtNum(pd.paperTarget, 0)}` : ''}${demo ? ' (dati di esempio)' : ''}: può smentire le simulazioni, non provarle. ` : '',
        'Nessun giorno con denaro reale.');
    }
    const span = Object.values(obj(q4().fund_curves)).find((c) => Array.isArray(c) && c.length > 1);
    vDays.replaceChildren(
      statWell('Storia simulata', pd.sim == null ? 'n.d.' : [fmtNum(pd.sim, 0), h('span', { class: 'sp-unit', text: 'giorni' })], [provTag('sim'), h('span', { class: 'sp-well__note', text: span ? `ricerca ${str(span[0][0]).slice(0, 4)}–${str(span[span.length - 1][0]).slice(0, 4)}${gen == null ? '' : `, del ${fmtDate(gen, true)}`}` : '' })]),
      statWell('Paper', pd.paper == null ? 'n.d.' : [fmtNum(pd.paper, 0), h('span', { class: 'sp-unit', text: 'giorni' })], [provTag(demo ? 'demo' : 'paper'), h('span', { class: 'sp-well__note', text: pd.paperTarget ? `su ${fmtNum(pd.paperTarget, 0)} richiesti dai cancelli` : '' })]),
      statWell('Denaro reale', [fmtNum(pd.real || 0, 0), h('span', { class: 'sp-unit', text: 'giorni' })], [provTag('real'), h('span', { class: 'sp-well__note', text: '«track record» vale solo qui' })]));
  }

  function paintCurves() {
    const curves = obj(q4().fund_curves);
    const rec = obj(q4().recommended);
    const names = Object.keys(curves);
    if (!names.length) { curvePlot.el.hidden = true; curveFacts.replaceChildren(missing('Storia simulata dei profili')); curveLegend.replaceChildren(); pCurve.setProv(); return; }
    curvePlot.el.hidden = false;
    pCurve.setProv(provTag('sim'));
    const pick = [
      { name: names.find((n) => /originale.*senza leva/i.test(n)), cls: 'bench sim', key: 'bench-sim', label: 'originale senza leva' },
      { name: names.find((n) => /originale.*come usato/i.test(n)), cls: 'orig sim', key: 'orig-sim', label: 'originale come usato ora' },
      { name: names.includes(str(rec.maximum)) ? str(rec.maximum) : null, cls: 'alt sim', key: 'alt-sim', label: 'nuovo, profilo massimo' },
      { name: names.includes(str(rec.prudent)) ? str(rec.prudent) : names.find((n) => /^C1/.test(n)), cls: 'fund sim', key: 'fund-sim', label: 'nuovo, profilo prudente' },
    ].filter((p) => p.name);
    const main = pick[pick.length - 1];
    const t = curves[main.name].map((r) => parseTs(str(r[0])));
    let i0 = 0;
    if (range === 'verify') while (i0 < t.length - 2 && t[i0] < SPLIT_T) i0++;
    const x = t.slice(i0);
    const series = pick.map((p) => { const v = curves[p.name].map((r) => num(r[1])).slice(i0); return { ...p, values: v.map((y) => (y == null || !v[0] ? null : (y / v[0]) * 100)) }; });
    const mainVals = series[series.length - 1].values;
    const dd = drawdownSeries(mainVals);
    const steps = list(obj(obj(q4().paper_profile_cone).drawdown).steps).map(num).filter((v) => v != null);
    const stats = arr(q4().fund_stats);
    const stat = (name) => stats.find((s) => str(s.portafoglio) === name) || {};
    curveFacts.replaceChildren(factRow(series.slice().reverse().map((sr) => [short(sr.name).replace(/\s*\(.*\)$/, ''), `${ps(range === 'verify' ? null : stat(sr.name).cagr, 0) || fmtNum(sr.values[sr.values.length - 1], 0)}${range === 'verify' ? '' : ' l\'anno'}`])));
    curvePlot.setTags(provTag('sim', range === 'verify' ? 'Simulato · verifica dal 2023' : 'Simulato · scelta 2018–2022 | verifica dal 2023'));
    curveChart.update({
      x,
      panels: [
        { height: ctxNow.lv === 'terminale' ? 200 : 260, scale: 'log', series: series.map((sr) => ({ values: sr.values, cls: sr.cls, end: true, name: short(sr.name) })), format: (v) => fmtNum(v, 0), refs: [{ value: 100, label: 'base 100' }] },
        { height: 64, title: 'Caduta dal massimo · profilo prudente', top: 0, series: [{ values: dd, cls: 'dd', area: true, name: 'Caduta' }], format: (v) => fmtPct(v, 0), refs: steps.filter((v) => v >= Math.min(...dd.filter((d) => d != null)) * 1.5).map((v) => ({ value: v, label: fmtPct(v, 0) })) },
      ],
      marks: range === 'verify' ? [] : [{ t: SPLIT_T, label: 'scelta | verifica' }],
      tip: (i) => ({ title: `${fmtDate(x[i], true)} · ${x[i] >= SPLIT_T ? 'verifica' : 'scelta'}`, rows: [...series.slice().reverse().map((sr) => ({ key: sr.key, label: sr.label, value: sr.values[i] == null ? '—' : fmtNum(sr.values[i], 0) })), { key: 'dd', label: 'Caduta (prudente)', value: dd[i] == null ? '—' : fmtPctSigned(dd[i], 1) }] }),
      say: (i) => `${fmtDate(x[i], true)}: profilo prudente ${fmtNum(mainVals[i], 0)}, caduta dal massimo ${dd[i] == null ? 'non disponibile' : fmtPctSigned(dd[i], 1)}`,
    });
    curveLegend.replaceChildren(legendRow(series.slice().reverse().map((sr) => [sr.key, sr.label])));
    pCurve.setFoot('Base 100, scala logaritmica, dati settimanali al netto dei costi ipotizzati. Tratteggio = simulato. Fonte: research/v5/quant_v4.json (fund_curves).');
  }

  function paintLuck() {
    const L = luck(ctxNow.quant4);
    if (!L) { pLuck.body.replaceChildren(missing('Conteggio delle prove')); pLuck.setProv(); return; }
    if (!luckBig.isConnected) pLuck.body.replaceChildren(luckBig, luckPlot.el, luckBox, luckKv, luckVerdict);
    pLuck.setProv(provTag('sim'));
    const dec = obj(q4().decomposition);
    luckBig.replaceChildren(`${fmtNum(L.trials, 0)} prove`, h('small', { class: 'bignum__sub', text: L.expectedMax == null ? '' : `la migliore, senza alcuna abilità, avrebbe Sharpe ${fmtNum(L.expectedMax, 2)}` }));
    luckViz.update({ se: L.seNull, expectedMax: L.expectedMax, trials: L.trials, marks: [
      { value: num(dec.portfolio_sharpe), se: L.seNull, label: 'libro giornaliero' }, { value: num(dec.portfolio_sharpe_verify), label: 'solo verifica', ring: true }] });
    luckPlot.setTags();
    luckBox.replaceChildren(h('div', { class: 'sp-luckbox__head' }, h('span', { text: 'Deflated Sharpe' }), h('b', { class: 'num', text: `${fmtNum(L.lo, 2)} – ${fmtNum(L.hi, 2)}` })),
      rangeBar({ lo: L.lo, hi: L.hi, threshold: L.threshold, label: 'Deflated Sharpe' }));
    luckKv.replaceChildren(...L.values.map((v) => h('div', null, h('span', { class: 'k', text: v.label }), h('span', { class: 'v', text: fmtNum(v.value, 2) }))));
    luckVerdict.className = `verdict ${L.pass ? 'verdict--ok' : ''}`.trim();
    luckVerdict.replaceChildren(h('b', { text: L.pass ? 'Sopra la soglia con ogni metodo. ' : 'Sotto la soglia con ogni metodo. ' }), L.pass ? 'Il risultato regge anche contando tutte le prove.' : 'Lo Sharpe misurato supera di poco ciò che darebbe il caso: vale la pena verificarlo in paper, non è una prova.');
    pLuck.setFoot(`Curva teorica (non la distribuzione empirica delle prove, che non è stata salvata): errore standard ${fmtNum(L.seNull, 2)} ricavato da prove e Sharpe atteso. Baffo: ±1 errore standard. `, h('span', { class: 'not-semplice', text: L.note }));
  }

  function paintCone() {
    const { snap } = ctxNow;
    const c = coneData(snap, ctxNow.quant4, horizon || null);
    if (!c) { pCone.body.replaceChildren(missing('Cono dell\'atteso')); pCone.setProv(); return; }
    if (!coneBig.isConnected) pCone.body.replaceChildren(coneBig, conePlot.el, coneFacts);
    const demo = provOf(snap.meta) === 'demo';
    pCone.setProv(provTag('sim', 'Sim fascia'), provTag(demo ? 'demo' : 'paper', demo ? 'Esempio linea' : 'Paper linea'));
    conePlot.setTags(provTag('sim', `Simulato · ${fmtNum(c.paths, 0)} percorsi`), c.days >= 1 ? provTag(demo ? 'demo' : 'paper', `${demo ? 'Esempio' : 'Paper'} · giorno ${fmtNum(c.days, 0)}`) : null);
    coneBig.replaceChildren(c.pctNow == null ? 'troppo presto' : `${c.pctNow <= 0.05 ? '≤ 5' : c.pctNow >= 0.95 ? '≥ 95' : fmtNum(c.pctNow * 100, 0)}° percentile`, h('small', { class: 'bignum__sub', text: c.pctNow == null ? 'serve almeno un giorno di paper: per ora si vede solo l\'atteso' : `${c.where} · dopo ${fmtNum(c.days, 0)} giorni` }));
    pCone.setAsk(c.pctNow == null ? 'Il paper è appena partito: per ora si vede solo ciò che le simulazioni si aspettano.' : c.pctNow > 0.05 && c.pctNow < 0.95 ? 'La fascia è ciò che le simulazioni considerano normale; la linea piena è il conto. Per ora è dentro: tutto come previsto.' : 'Il conto è fuori da ciò che le simulazioni consideravano normale: da guardare.');
    const every = c.horizon > 18 ? 6 : c.horizon > 6 ? 3 : 1;
    coneChart.update({
      x: c.x, height: ctxNow.lv === 'terminale' ? 170 : ctxNow.lv === 'semplice' ? 250 : 220, xHead: 'Mese', xFormat: (m) => `mese ${fmtNum(m, 1)}`,
      xTicks: Array.from({ length: Math.floor(c.horizon / every) + 1 }, (_, i) => ({ t: i * every, label: i === 0 ? 'avvio' : `${i * every} m` })),
      bands: [{ lo: c.p05, hi: c.p95, name: '5°–95° percentile' }, { lo: c.p25, hi: c.p75, name: '25°–75° percentile' }],
      lines: [{ values: c.p50, cls: 'median', name: 'Mediana simulata' }, { values: c.path, cls: demo ? 'paper demo' : 'paper', name: demo ? 'Conto (esempio)' : 'Conto in paper' }],
      format: (v) => fmtPctSigned(v - 1, 0), refs: [{ value: 1, label: '' }],
    });
    coneFacts.replaceChildren(factRow([['Rendimento annuo atteso · mediana', ps(c.cagr.p50, 0) || 'n.d.'], ['1 caso su 20 sotto', ps(c.cagr.p05, 0) || 'n.d.'], ['1 su 20 sopra', ps(c.cagr.p95, 0) || 'n.d.']]));
    pCone.setFoot(legendRow([['band', 'fascia 5°–95° e 25°–75°'], ['fund-sim', 'mediana simulata'], [demo ? 'paper-demo' : 'paper', demo ? 'conto (esempio)' : 'conto in paper']]), h('span', { class: 'not-semplice', text: `${c.profile} · ${c.method}` }));
  }

  function paintDD() {
    const dd = obj(obj(q4().paper_profile_cone).drawdown);
    const edges = list(dd.edges).map(num);
    const counts = list(dd.counts).map(num);
    if (edges.length < 3 || counts.length !== edges.length - 1) { pDD.body.replaceChildren(missing('Distribuzione della caduta')); pDD.setProv(); return; }
    if (!ddBig.isConnected) pDD.body.replaceChildren(ddBig, ddPlot.el, ddFacts);
    pDD.setProv(provTag('sim'));
    const steps = list(dd.steps).map(num).filter((v) => v != null).sort((a, b) => b - a);
    const prob = (lv, i) => num(dd[`p_reach_${Math.round(-lv * 100)}`]) ?? (i === steps.length - 1 ? num(dd.p_kill) : null);
    const deepest = steps.length ? steps[steps.length - 1] : edges[0];
    let k0 = 0;                                                       // via le classi vuote più profonde dell'ultimo scalino
    while (k0 < counts.length - 1 && !counts[k0] && edges[k0 + 1] < deepest - 1e-9) k0++;
    const e = edges.slice(k0);
    const cts = counts.slice(k0);
    const total = cts.reduce((a, v) => a + v, 0);
    const kinds = ['warn', 'serious', 'crit'];
    const first = steps.length ? prob(steps[0], 0) : null;
    ddBig.replaceChildren(first == null ? fmtPct(dd.p50, 0) : `${fmtPct(first, 0)} dei percorsi`, h('small', { class: 'bignum__sub', text: first == null ? 'caduta tipica a tre anni' : `tocca il primo freno (${fmtPct(steps[0], 0)}) almeno una volta in tre anni` }));
    ddPlot.setTags(provTag('sim', `Simulato · n = ${fmtNum(total, 0)}`));
    ddChart.update({
      edges: e, counts: cts, reverse: true, height: ctxNow.lv === 'terminale' ? 130 : 170, unit: 'Percorsi', xFormat: (v) => (v === 0 ? '0' : fmtPct(v, 0)), xTitle: 'caduta massima dal picco →',
      zones: [{ from: 0, to: steps.length ? steps[0] : e[0], kind: 'safe' }, ...steps.map((lv, i) => ({ from: lv, to: i + 1 < steps.length ? steps[i + 1] : e[0], kind: kinds[Math.min(i, 2)] }))],
      refs: [
        num(dd.p50) != null ? { value: dd.p50, label: `mediana ${fmtPct(dd.p50, 0)}`, cls: 'soft', side: 'left' } : null,
        ...steps.map((lv, i) => ({ value: lv, label: fmtPct(lv, 0), sub: prob(lv, i) == null ? 'quota n.d.' : `${fmtPct(prob(lv, i), prob(lv, i) < 0.1 ? 1 : 0)} oltre`, cls: kinds[Math.min(i, 2)] })),
      ].filter(Boolean),
    });
    ddFacts.replaceChildren(factRow([['Caduta tipica (mediana)', fmtPct(dd.p50, 1)], num(dd.p05) != null ? ['1 percorso su 20 oltre', fmtPct(dd.p05, 1)] : null,
      ...steps.map((lv, i) => [`Oltre ${fmtPct(lv, 0)}`, prob(lv, i) == null ? 'n.d.' : fmtPct(prob(lv, i), 1)])]));
    pDD.setFoot('Colonne velate = simulato. Monte Carlo del profilo del paper con il motore di rischio applicato a ogni percorso. Fonte: quant_v4.json (paper_profile_cone.drawdown).');
  }

  function paintCmp() {
    if (cmp === undefined) { cmpGrid.hidden = true; cmpFacts.replaceChildren(); cmpNeed.replaceChildren(); cmpEmpty.replaceChildren(emptyState('Confronto in lettura…')); return; }
    const c = compareStats(cmp);
    const demo = !!obj(cmp).example;
    pCmp.setProv(cmp ? provTag(demo ? 'demo' : 'paper') : null);
    if (!cmp || c.rows < 2) {
      cmpGrid.hidden = true; cmpFacts.replaceChildren(); cmpNeed.replaceChildren();
      cmpEmpty.replaceChildren(emptyState(cmp ? 'Servono almeno 3 giorni comuni' : 'Confronto non ancora scritto', cmp ? `Per ora ce ne sono ${fmtNum(Math.max(0, c.n), 0)}: z e imbuto non si possono calcolare.` : 'Il motore scrive una riga al giorno con i due conti (confronto_nav.csv): comparirà dopo il primo giorno in comune.'));
      pCmp.setAsk('Il confronto giornaliero con il conto originale non ha ancora abbastanza giorni.');
      return;
    }
    cmpEmpty.replaceChildren();
    cmpGrid.hidden = false;
    const vk = { few: 'unknown', running: 'accent', open: 'muted', beats: 'ok', beaten: 'crit' }[c.verdict.code];
    cmpFacts.replaceChildren(h('div', { class: 'facts sp-facts' },
      h('span', null, stateChip(vk, `Esito: ${c.verdict.text}`, { xs: false })),
      h('span', null, 'z a pari volatilità', h('b', { text: c.z == null ? 'n.d.' : `${fmtSigned(c.z, 2)} (soglie ±${fmtNum(c.zWin, 1)})` })),
      h('span', null, 'Giorni comuni', h('b', { text: `${fmtNum(c.span, 0)} su ${fmtNum(c.minDays, 0)} minimi` })),
      h('span', null, 'Rendimento', h('b', { text: `${ps(c.cumNew, 2)} contro ${ps(c.cumOrig, 2)}` })),
      h('span', { class: 'not-semplice' }, 'Correlazione', h('b', { text: c.rho == null ? 'n.d.' : fmtSigned(c.rho, 2) }))));
    pCmp.setAsk(c.verdict.code === 'beats' ? 'Il nuovo sistema è uscito dall\'imbuto verso l\'alto dopo il numero minimo di giorni: batte l\'originale.' : c.verdict.code === 'beaten' ? 'Il nuovo sistema è uscito dall\'imbuto verso il basso: l\'originale lo batte.'
      : c.verdict.code === 'open' ? 'La linea è dentro l\'imbuto: dopo abbastanza giorni, nessuno dei due ha battuto l\'altro.' : `Troppo presto per dirlo: ${c.verdict.why}. Finché la linea resta dentro l'imbuto, nessuno dei due ha battuto l'altro.`);
    const lineCls = demo ? 'fund demo' : 'fund';
    cmpA.setTags(provTag(demo ? 'demo' : 'paper', demo ? 'Esempio' : 'Paper'));
    cmpChart.update({
      x: c.x,
      panels: [{ height: 190, series: [{ values: c.origIdx, cls: demo ? 'orig demo' : 'orig', end: true, name: 'Originale' }, { values: c.newIdx, cls: lineCls, end: true, name: 'Nuovo' }], format: (v) => fmtNum(v, 1), refs: [{ value: 100, label: 'base 100' }] }],
      tip: (i) => ({ title: fmtDate(c.x[i], true), rows: [{ key: 'fund', label: 'Nuovo sistema', value: fmtNum(c.newIdx[i], 2) }, { key: 'orig', label: 'Sistema originale', value: fmtNum(c.origIdx[i], 2) }, { label: 'Distacco', value: `${fmtSigned(c.newIdx[i] - c.origIdx[i], 2)} punti` }] }),
    });
    if (c.z == null) { cmpB.el.hidden = true; } else {
      cmpB.el.hidden = false;
      const end = Math.max(c.minDays, Math.ceil(c.n * 1.15));
      const xs = Array.from({ length: end + 1 }, (_, i) => i);
      const edge = xs.map((k) => c.zWin * c.su * Math.sqrt(k));
      const line = xs.map((k) => (k <= c.n ? c.cumU[k] : null));
      const step = end > 240 ? 90 : end > 120 ? 60 : 30;
      cmpB.setTags(provTag(demo ? 'demo' : 'paper', `${demo ? 'Esempio' : 'Paper'} · ${fmtNum(c.n, 0)} giorni`));
      funnel.update({
        x: xs, height: 190, xHead: 'Giorno comune', xFormat: (k) => `giorno ${fmtNum(k, 0)}`,
        xTicks: Array.from({ length: Math.floor(end / step) + 1 }, (_, i) => ({ t: i * step, label: String(i * step) })),
        bands: [{ lo: edge.map((v) => -v), hi: edge, name: `Fascia del caso (±${fmtNum(c.zWin, 1)} e.s.)` }],
        lines: [{ values: line, cls: lineCls, name: 'Distacco cumulato' }],
        format: (v) => fmtSigned(v, 0), refs: [{ value: 0, label: '' }],
        marks: c.n < c.minDays ? [{ t: c.minDays, label: 'minimo per un esito' }] : [],
      });
    }
    const need = c.need10;
    cmpNeed.replaceChildren(...(need == null ? [] : [meterRow({ name: 'Giorni osservati', sub: 'su quelli necessari', value: c.n, cap: need, scale: need, state: 'none', text: `${fmtNum(c.n, 0)} su ~${fmtNum(need, 0)}` }),
      h('p', { class: 'panel__ask', text: `Per distinguere dal caso una differenza di Sharpe di 1,0 servono circa ${fmtNum(need, 0)} giorni comuni${c.need05 == null ? '' : ` (${fmtNum(c.need05, 0)} per una differenza di 0,5)`}: con ${fmtNum(c.n, 0)} giorni qualunque distacco è rumore.` })]));
    pCmp.setFoot(legendRow([[demo ? 'fund-demo' : 'fund', 'nuovo sistema'], [demo ? 'orig-demo' : 'orig', 'sistema originale'], ['band', `imbuto ±${fmtNum(c.zWin, 1)} errori standard × √giorni`]]),
      h('span', { class: 'not-semplice', text: `Formula di research/v5/v6/b8_confronto/confronto.py: solo giorni comuni, versamenti tolti${c.fxApplied ? ', cambio applicato' : ''}. z oltre la soglia esce per caso circa una volta su dieci: è una regola di decisione, non una prova.` }));
  }

  function paintProfiles() {
    const stats = arr(q4().fund_stats);
    if (!stats.length) { profBox.replaceChildren(missing('Tabella dei profili')); pProf.setProv(); return; }
    pProf.setProv(provTag('sim'));
    const mc = arr(q4().fund_mc).filter((m) => str(m.scenario) === scenario);
    const rec = obj(q4().recommended);
    const maxMonth = Math.max(...stats.map((s) => Math.max(num(s.mese_medio) || 0, num(s.mese_mediano) || 0)));
    const mm = (s) => {
      const el = h('span', { class: 'sp-mm', role: 'img', 'aria-label': `mese medio ${ps(s.mese_medio, 2)}, mese mediano ${ps(s.mese_mediano, 2)}` }, h('i'), h('b'));
      el.style.setProperty('--a', `${Math.max(0, (num(s.mese_mediano) || 0) / maxMonth * 100).toFixed(1)}%`);
      el.style.setProperty('--b', `${Math.max(0, (num(s.mese_medio) || 0) / maxMonth * 100).toFixed(1)}%`);
      return el;
    };
    const m = (s) => mc.find((x) => str(x.portafoglio) === str(s.portafoglio)) || {};
    const E = 'is-num not-semplice';
    profBox.replaceChildren(simpleTable('Profili del fondo: statistiche simulate e Monte Carlo', [
      { label: 'Profilo', cell: (s) => h('span', { class: 'sp-name' }, short(s.portafoglio), str(s.portafoglio) === str(rec.prudent) ? stateChip('accent', 'prudente', { iconName: 'check' }) : str(s.portafoglio) === str(rec.maximum) ? stateChip('muted', 'massimo') : null) },
      { label: 'Sharpe scelta', cls: E, cell: (s) => n2(s.sh_scelta) },
      { label: 'Verifica', cls: `${E} sp-split`, cell: (s) => h('b', { text: n2(s.sh_verifica) || 'n.d.' }) },
      { label: 'Rend. annuo', cls: 'is-num', cell: (s) => ps(s.cagr, 1) },
      { label: 'Volatilità', cls: E, cell: (s) => pc(s.vol, 1) },
      { label: 'Caduta max', cls: 'is-num', cell: (s) => ps(s.maxdd_mensile, 1) },
      { label: 'Mese medio', cls: 'is-num', cell: (s) => ps(s.mese_medio, 2) },
      { label: 'Mese mediano', cls: 'is-num', cell: (s) => h('b', { text: ps(s.mese_mediano, 2) || 'n.d.' }) },
      { label: 'Mediano ○ medio ●', cls: 'sp-mmcol', cell: mm },
      { label: 'MC: rend. annuo 5° · 50° · 95°', cls: E, cell: (s) => (num(m(s).cagr_p50) == null ? null : `${ps(m(s).cagr_p05, 0)} · ${ps(m(s).cagr_p50, 0)} · ${ps(m(s).cagr_p95, 0)}`) },
      { label: 'MC: caduta al 95°', cls: E, cell: (s) => ps(m(s).dd_p95, 0) },
      { label: 'P(−30%)', cls: E, cell: (s) => pc(m(s).p_meno30, 1) },
    ], stats, { mark: (s) => str(s.portafoglio) === str(rec.prudent) }));
    const dec = obj(q4().decomposition);
    pProf.setFoot('Statistiche mensili simulate 2018–2026. Scelta = fino al 2022, verifica = dal 2023. Caduta massima misurata a fine mese. ',
      h('span', { class: 'not-semplice', text: `Monte Carlo a tre anni, scenario «${scenario}». Contributo dell'AI: ${num(dec.ai_contribution) == null ? 'da misurare in paper, mai mostrato come numero' : fmtPct(dec.ai_contribution, 1)}.` }));
  }

  function paintCand() {
    const all = arr(q4().candidates);
    if (!all.length) { candFacts.replaceChildren(); candBox.replaceChildren(missing('Elenco delle strategie provate')); pCand.setProv(); return; }
    pCand.setProv(provTag('sim'));
    const kept = all.filter((c) => !/scartat/i.test(str(c.verdict)));
    const counts = new Map();
    for (const c of all) counts.set(str(c.verdict), (counts.get(str(c.verdict)) || 0) + 1);
    const order = ['passa', 'passa con riserva', 'passa di misura', 'in osservazione', 'ipotesi', 'scartata'];
    candFacts.replaceChildren(h('div', { class: 'facts sp-facts' }, h('span', null, 'Idee provate', h('b', { text: fmtNum(all.length, 0) })),
      [...counts.keys()].sort((a, b) => order.indexOf(a) - order.indexOf(b)).map((k) => h('span', { class: 'sp-count' }, verdictChip(k), h('b', { text: fmtNum(counts.get(k), 0) })))));
    const rows = (candAll ? all : kept).slice().sort((a, b) => order.indexOf(str(a.verdict)) - order.indexOf(str(b.verdict)) || (num(b.sharpe_verify) ?? -9) - (num(a.sharpe_verify) ?? -9));
    const table = simpleTable('Strategie provate dalla ricerca', [
      { label: 'Idea', cell: (c) => h('span', { class: 'sp-idea' }, h('span', { class: 'sp-idea__name', text: str(c.name) }), str(c.note) ? h('small', { text: str(c.note) }) : null) },
      { label: 'Esito', cell: (c) => verdictChip(c.verdict) },
      { label: 'Sharpe scelta', cls: 'is-num not-semplice', cell: (c) => n2(c.sharpe_select) },
      { label: 'Verifica', cls: 'is-num sp-split', cell: (c) => (num(c.sharpe_verify) == null ? null : h('b', { text: n2(c.sharpe_verify) })) },
      { label: 'Corr. col fondo', cls: 'is-num not-semplice', cell: (c) => (num(c.corr_portfolio) == null ? null : fmtSigned(c.corr_portfolio, 2)) },
      { label: 'Caduta max', cls: 'is-num not-semplice', cell: (c) => ps(c.maxdd, 0) },
      { label: 'Sharpe per anno · scelta | verifica', cls: 'sp-yearcol', cell: (c) => (Object.keys(obj(c.by_year)).length ? yearStrip(c.by_year) : nd('senza serie annuale')) },
    ], rows);
    candBox.replaceChildren(h('div', { class: candAll ? 'sp-scroll' : '' }, table));
    pCand.setFoot(`${candAll ? `Tutte le ${fmtNum(all.length, 0)} idee` : `${fmtNum(kept.length, 0)} idee non scartate su ${fmtNum(all.length, 0)}`}, ordinate per esito e Sharpe di verifica. Le idee senza numeri sono state scartate prima del backtest (motivo nella riga). Fonte: quant_v4.json (candidates).`);
  }

  function paintLev() {
    const rows = arr(q4().stop_table);
    if (!rows.length) { levBox.replaceChildren(missing('Tabella della leva per trade')); pLev.setProv(); return; }
    pLev.setProv(provTag('sim'));
    const inUse = (r) => /^1\.0 x ATR$/i.test(str(r.label));
    const retired = (r) => /ritirat/i.test(str(r.note));
    levBox.replaceChildren(simpleTable('Stop, leva e R medio per operazione', [
      { label: 'Stop', cell: (r) => h('span', { class: 'sp-name' }, str(r.label).replace('.', ',').replace(' x ', ' × '), inUse(r) ? stateChip('accent', 'in uso', { iconName: 'check' }) : retired(r) ? stateChip('muted', 'ritirata', { iconName: 'x' }) : null) },
      { label: 'Leva', cls: 'is-num', cell: (r) => (num(r.leverage) == null ? null : `${fmtNum(r.leverage, 1)}×`) },
      { label: 'Trade', cls: 'is-num', cell: (r) => (num(r.n) == null ? null : fmtNum(r.n, 0)) },
      { label: 'R medio', cls: 'is-num', cell: (r) => (num(r.mean_R) == null ? null : h('span', { class: r.mean_R > 0 ? 'pos' : 'neg', text: `${fmtSigned(r.mean_R, 2)} R` })) },
      { label: 'In verifica', cls: 'is-num sp-split', cell: (r) => (num(r.mean_R_verify) == null ? null : h('b', { text: `${fmtSigned(r.mean_R_verify, 2)} R` })) },
      { label: 't', cls: 'is-num', cell: (r) => (num(r.t) == null ? null : fmtSigned(r.t, 1)) },
      { label: 'Vincenti', cls: 'is-num', cell: (r) => pc(r.hit, 0) },
      { label: 'Costo', cls: 'is-num', cell: (r) => (num(r.cost_R) == null ? null : `${fmtNum(r.cost_R, 2)} R`) },
      { label: 'Serie perdente', cls: 'is-num', cell: (r) => (num(r.max_losing_streak) == null ? null : fmtNum(r.max_losing_streak, 0)) },
    ], rows, { mark: inUse }));
    const notes = rows.filter((r) => str(r.note)).map((r) => `${str(r.label).replace('.', ',')}: ${str(r.note)}`);
    pLev.setFoot(`Trade simulati su BTC, ETH e SOL; R al netto di commissioni e funding. ${notes.join(' ')}`);
  }

  function paintStress() {
    const all = arr(q4().stress);
    const coins = [...new Set(all.map((r) => str(r.coin)))];
    const levs = [...new Set(all.map((r) => num(r.leverage)))].filter((v) => v != null).sort((a, b) => a - b);
    if (!coins.length || levs.length < 2) { stressPlot.el.hidden = true; stressLegend.replaceChildren(missing('Analisi di stress della leva')); stressTable.replaceChildren(); pStress.setProv(); return; }
    stressPlot.el.hidden = false;
    pStress.setProv(provTag('sim'));
    stressPlot.setTags(provTag('sim'));
    const cls = ['c1', 'c2', 'c3', 'c4'];
    const series = coins.map((c, i) => ({ name: c, cls: `${cls[i % 4]} sim`, key: `${cls[i % 4]}-sim`, values: levs.map((lv) => { const r = all.find((x) => str(x.coin) === c && num(x.leverage) === lv); return r ? num(r[liqWin]) : null; }), end: true, dots: true }));
    stressChart.update({
      x: levs, xHead: 'Leva', xFormat: (v) => `${fmtNum(v, 0)}×`, xTicks: levs.map((v) => ({ t: v, label: `${fmtNum(v, 0)}×` })),
      panels: [{ height: 170, bottom: 0, series, format: (v) => fmtPct(v, v < 0.1 ? 1 : 0) }],
      tip: (i) => ({ title: `Leva ${fmtNum(levs[i], 0)}×`, rows: series.map((sr) => ({ key: sr.key, label: sr.name, value: sr.values[i] == null ? '—' : fmtPct(sr.values[i], 2) })) }),
    });
    stressLegend.replaceChildren(legendRow(series.map((sr) => [sr.key, sr.name])));
    stressTable.replaceChildren(simpleTable('Probabilità di liquidazione senza stop, per leva e moneta', [
      { label: 'Leva', cell: (i) => `${fmtNum(levs[i], 0)}×` }, ...series.map((sr) => ({ label: sr.name, cls: 'is-num', cell: (i) => (sr.values[i] == null ? null : fmtPct(sr.values[i], sr.values[i] < 0.1 ? 1 : 0)) })),
    ], levs.map((_, i) => i)));
    pStress.setFoot('Quota storica dei casi in cui, senza stop, il prezzo raggiunge la liquidazione entro la finestra. Fonte: quant_v4.json (stress).');
  }

  function paintTier() {
    const rows = arr(q4().tier_mc).filter((r) => str(r.scenario) === tierScen);
    if (!rows.length) { tierBox.replaceChildren(missing('Schemi di rischio per trade')); pTier.setProv(); return; }
    pTier.setProv(provTag('sim'));
    tierBox.replaceChildren(simpleTable('Schemi di rischio per trade: Monte Carlo a tre anni', [
      { label: 'Schema · leva: rischio confermato / eccezionale', cell: (r) => h('span', { class: 'sp-name' }, str(r.schema), /^S1 /.test(str(r.schema)) ? stateChip('accent', 'in uso nel paper', { iconName: 'check' }) : null) },
      { label: 'Rend. annuo mediano', cls: 'is-num', cell: (r) => ps(r.cagr_p50, 1) },
      { label: '1 su 20 sotto', cls: 'is-num', cell: (r) => ps(r.cagr_p05, 1) },
      { label: 'Caduta mediana', cls: 'is-num', cell: (r) => ps(r.dd_p50, 1) },
      { label: 'Caduta al 95°', cls: 'is-num', cell: (r) => ps(r.dd_p95, 1) },
      { label: 'P(−30%)', cls: 'is-num', cell: (r) => pc(r.p_meno30, 2) },
      { label: 'P(dimezzato)', cls: 'is-num', cell: (r) => pc(r.p_dimezzato, 2) },
      { label: 'Mese tipico', cls: 'is-num', cell: (r) => ps(r.mese, 2) },
    ], rows, { mark: (r) => /^S1 /.test(str(r.schema)) }));
    pTier.setFoot(`Scenario «${tierScen}». Solo il libro dei trade a margine isolato, senza il libro giornaliero. Fonte: quant_v4.json (tier_mc).`);
  }

  function paintVenues() {
    const rows = arr(q4().venues);
    if (!rows.length) { venuesBox.replaceChildren(missing('Tabella delle sedi')); return; }
    pVenues.setProv(h('span', { class: 'tag tag--wait', text: 'Documentale' }));
    venuesBox.replaceChildren(simpleTable('Sedi di negoziazione valutate', [
      { label: 'Sede', cell: (r) => h('b', { text: str(r.venue) }) }, { label: 'Stato legale', cls: 'is-wrap', cell: (r) => str(r.legal) }, { label: 'Leva massima', cell: (r) => str(r.max_leverage) },
      { label: 'Commissioni', cell: (r) => str(r.fees) }, { label: 'Rischio proprio', cls: 'is-wrap', cell: (r) => str(r.risk) }, { label: 'Ruolo nel fondo', cls: 'is-wrap', cell: (r) => str(r.role) },
    ], rows, { cls: 'sp-table--text' }));
    pVenues.setFoot('Ricerca documentale, non un dato di mercato: va riverificata prima di aprire un conto. Fonte: quant_v4.json (venues).');
  }

  function paintAll() {
    paintVerdict(); paintCurves(); paintLuck(); paintCone(); paintDD(); paintCmp(); paintProfiles(); paintCand(); paintLev(); paintStress(); paintTier(); paintVenues();
  }

  getCompare().then((res) => { cmp = res || null; if (ctxNow) paintCmp(); });

  return {
    update(ctx) { ctxNow = ctx; paintAll(); },
    summary(ctx) {
      const L = luck(ctx.quant4);
      const pd = provenanceDays(ctx.snap, ctx.quant4);
      const c = cmp ? compareStats(cmp) : null;
      if (!L) return 'La ricerca non è disponibile: senza quel file non si può dire se il vantaggio è vero.';
      return `Dopo ${fmtNum(L.trials, 0)} prove il vantaggio è ${L.pass ? 'sopra' : 'promettente ma sotto'} la soglia di prova (Deflated Sharpe ${fmtNum(L.lo, 2)}–${fmtNum(L.hi, 2)} contro ${fmtNum(L.threshold, 2)}). `
        + `${pd.paper != null ? `Il paper è al giorno ${fmtNum(pd.paper, 0)}${pd.paperTarget ? ` di ${fmtNum(pd.paperTarget, 0)}` : ''}. ` : ''}${c ? `Contro l'originale: ${c.verdict.text.toLowerCase()} (${c.verdict.why}).` : ''}`;
    },
  };
}
