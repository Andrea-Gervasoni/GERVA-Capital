// Spazio «Apprendimento»: che cosa ha provato, respinto, tenuto in ombra il ciclo di automiglioramento, e come sono fatti i trade.
// In quest'ordine: i sette passaggi con lo stato di adesso e le tre garanzie · tutti i trade contro i soli paper (mai sommati) ·
// distribuzione di R · R cumulato · R medio per fetta (conviction, giorno, moneta, anno: baffo e n su ogni barra) · MAE contro MFE
// (solo paper) · dove perde · regole provate con i sei controlli · in ombra e attive, con il comando esatto per attivare.
// SOLA LETTURA: qui non c'è, e non deve esserci, alcun comando che attivi una regola. Si attiva solo da terminale, a mano.

import { scatter } from '../chart-engine.js';
import { timeChart } from '../charts.js';
import { segmented } from '../components.js';
import { h, icon } from '../dom.js';
import { arr, fmtDate, fmtNum, fmtPct, fmtSigned, num, obj, parseTs, str } from '../format.js';
import { getTrades } from '../market.js';
import { SPLIT_T, groupR, histR, rStats } from '../derive.js';
import { emptyState, meterRow, panel, provTag } from '../panels.js';
import { plainRule, plainSlice, tidy } from './apprendimento.js';
import { colHist, errBars, factRow, legendRow, nd, plot, simpleTable, stateChip, statWell, stepper, yearStrip } from './kit.js';

const STATES = { RESPINTA: ['muted', 'Respinta', 'x'], IN_OMBRA: ['accent', 'In ombra', 'clock'], PROMUOVIBILE: ['warn', 'Promuovibile', 'warn'], ATTIVA: ['ok', 'Attiva', 'check'], RITIRATA: ['muted', 'Ritirata', 'off'] };
const stateOf = (v) => { const s = STATES[str(v).toUpperCase()] || ['muted', str(v) || 'n.d.', 'info']; return stateChip(s[0], s[1], { iconName: s[2] }); };
const CHECKS = [
  { key: 'numerosita', label: 'Colpisce abbastanza trade', hint: 'almeno 30 in campione e 15 fuori campione', find: /almeno|pochi|numeros/i },
  { key: 'quota', label: 'Non toglie troppi trade', hint: 'non più della metà', find: /quota|met[aà]'? dei trade|troppi/i },
  { key: 'in_campione', label: 'I trade colpiti perdono, in campione', hint: 'con una soglia che sale a ogni ipotesi provata', find: /in scelta|in campione/i },
  { key: 'fuori_campione', label: 'Perdono anche fuori campione', hint: 'sui dati mai usati per cercare la regola', find: /in verifica|fuori campione/i },
  { key: 'walk_forward', label: 'Regge anno per anno', hint: 'in almeno il 60% degli anni (walk-forward)', find: /anni/i },
  { key: 'soglie_vicine', label: 'Non dipende dalla soglia esatta', hint: 'spostandola del 20% il segno non cambia', find: /soglia del|spostando|vicin/i },
];
const DAYS = ['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom'];
const rr = (v, d = 2) => (num(v) == null ? 'n.d.' : `${fmtSigned(v, d)} R`);
const COMMAND = (id) => `python -m gerva learn --approve ${str(id)} --confirm`;

export function mount(root) {
  let ctxNow = null;
  let trades;                    // undefined = in arrivo, null = assente
  let source = 'sim';

  // ---- 1. il ciclo ----
  const pLoop = panel({ title: 'Come impara il fondo, e a che punto è il ciclo?', eyebrow: 'Sette passaggi in cerchio', span: 12, id: 'ciclo',
    ask: 'Il fondo studia i propri trade, cerca dove perde e propone correzioni. Ma chi propone non decide: ogni correzione passa da un validatore severo, poi da un periodo di sola osservazione, e alla fine dal proprietario. Il bordo tratteggiato segna i passaggi in cui decide qualcun altro.',
    what: 'Memoria dei trade → valutazione → ipotesi → validazione → ombra → approvazione → attiva, e poi di nuovo da capo con i trade nuovi. Su ogni passaggio c\'è il conteggio del rapporto più recente. «Respinta» è l\'esito normale e sano: vuol dire che il sistema non si lascia convincere da una coincidenza.' });
  const loopBox = h('div');
  const guards = h('div', { class: 'sp-three sp-guards' });
  pLoop.body.append(loopBox, h('div', { class: 'sp-sub', text: 'Tre garanzie che il codice fa rispettare' }), guards);

  // ---- 2. valutazione ----
  const pEval = panel({ title: 'Come stanno andando i trade?', eyebrow: 'Valutazione · tutti contro solo paper', span: 12, id: 'valutazione',
    ask: 'A sinistra tutti i trade in memoria, a destra solo quelli del conto di prova. Non si sommano mai: per giudicare il conto conta la colonna di destra. I numeri sono in R: 1 R è ciò che un trade rischiava.',
    what: 'R medio: quanto rende in media un trade rispetto a ciò che rischia. Vincenti: meno della metà è normale, pochi trade buoni pagano molti piccoli stop. Profit factor: guadagni totali divisi per perdite totali. t: quanto il risultato è lontano dal caso (sopra 2 è un buon segno, non una prova).' });
  const evalBox = h('div', { class: 'sp-two' });
  pEval.body.append(evalBox);

  // ---- 3. distribuzione di R ----
  const pDist = panel({ title: 'Come sono fatti i risultati dei trade?', eyebrow: 'Distribuzione di R', span: 6, id: 'distribuzione',
    ask: 'Le colonne contano i trade per risultato: il mucchio a sinistra sono gli stop (circa −1 R), la coda a destra i pochi trade che fanno la media.',
    what: 'R è il risultato di un trade diviso per il rischio iniziale: −1 R vuol dire aver perso esattamente quanto messo a rischio. Classi da 0,25 R; l\'ultima raccoglie tutto ciò che sta oltre. Le righe verticali sono lo zero, la media e la mediana. I trade paper, quando esisteranno, avranno un loro grafico: non si sommano ai simulati.' });
  const distFacts = h('div');
  const distPlot = plot();
  const distPaper = h('div');
  pDist.body.append(distFacts, distPlot.el, distPaper);
  const distChart = colHist(distPlot.host, { label: 'Distribuzione di R dei trade simulati' });

  // ---- 4. R cumulato ----
  const pCum = panel({ title: 'Il vantaggio si accumula con regolarità, o a strappi?', eyebrow: 'R cumulato', span: 6, id: 'cumulato',
    ask: 'La linea somma i risultati trade dopo trade. Se sale a gradini regolari il vantaggio è diffuso; se sale con pochi salti, dipende da pochi trade fortunati.',
    what: 'La somma di R trade dopo trade, alla data di uscita. Una scala che sale a gradini regolari è un vantaggio diffuso; pochi salti isolati sono un vantaggio che dipende da pochi trade. Simulati e paper sono due linee distinte, ognuna dal proprio zero.' });
  const cumFacts = h('div');
  const cumPlot = plot();
  pCum.body.append(cumFacts, cumPlot.el);
  const cumChart = timeChart(cumPlot.host, { label: 'R cumulato dei trade, per data di uscita', table: true });

  // ---- 5. da che cosa dipende ----
  const srcSeg = segmented({ label: 'Quali trade', options: [{ value: 'sim', label: 'Simulati' }, { value: 'paper', label: 'Paper' }], value: source, onChange: (v) => { source = v; paintSlices(); } });
  const pSlices = panel({ title: 'Da che cosa dipende il risultato: conviction, giorno, moneta, anno?', eyebrow: 'R medio per fetta', span: 12, tools: srcSeg.el, id: 'fette',
    ask: 'Ogni barra è il risultato medio di un gruppo di trade; il baffo dice quanto quella media è incerta (9 volte su 10 il valore vero sta lì dentro). Se il baffo attraversa la riga della media generale, quel gruppo non è distinguibile dagli altri.',
    what: 'R medio per gruppo con l\'intervallo al 90% (±1,645 errori standard) e il numero di trade a destra. I gruppi con meno di 30 trade sono attenuati e segnati con l\'asterisco. Con tante fette qualcuna sembra diversa per caso: è il motivo per cui una fetta debole diventa regola solo dopo sei controlli.' });
  const sliceGrid = h('div', { class: 'sp-two sp-slices' });
  const sliceNote = h('div');
  pSlices.body.append(sliceNote, sliceGrid);
  const sliceCols = [h('div', { class: 'sp-slicecol' }), h('div', { class: 'sp-slicecol' })];
  sliceGrid.append(...sliceCols);
  const SL = [['conv', 'Per conviction all\'ingresso', 0], ['day', 'Per giorno della settimana', 0], ['coin', 'Per moneta', 1], ['year', 'Per anno', 1]].map(([key, title, col]) => {
    const host = h('div', { class: 'chart-host' });
    const el = h('div', { class: 'sp-slice' }, h('div', { class: 'sp-sub', text: title }), host);
    sliceCols[col].append(el);
    return { key, title, host, el, chart: errBars(host, { label: `R medio ${title.toLowerCase()}` }) };
  });

  // ---- 6. MAE contro MFE ----
  const pMae = panel({ title: 'Quanto soffre un trade prima di chiudere?', eyebrow: 'MAE contro MFE · solo paper', span: 6, id: 'mae-mfe',
    ask: 'Ogni punto sarà un trade del conto di prova: a sinistra quanto è andato in perdita mentre era aperto, in alto quanto in guadagno.',
    what: 'MAE è la perdita massima toccata mentre il trade era aperto, MFE il guadagno massimo, entrambi in R. Trade che vincono dopo essere scesi molto dicono che lo stop è largo; trade che perdono dopo essere saliti molto dicono che l\'uscita è lenta. Si misura solo sui trade veri del paper: nelle simulazioni storiche MAE e MFE non sono annotati.' });
  const maeBox = h('div', { class: 'chart-host' });
  pMae.body.append(maeBox);
  let maeChart = null;

  // ---- 7. dove perde ----
  const pWeak = panel({ title: 'Dove perde?', eyebrow: 'Debolezze trovate dalla valutazione', span: 6, id: 'debolezze',
    ask: 'Le «fette» di trade che rendono meno del resto. Trovarne una non basta: per diventare regola deve superare i sei controlli.',
    what: '«Sospetta» vuol dire che la differenza c\'è ma potrebbe essere un caso; «significativa» che è abbastanza netta da meritare un\'ipotesi. t è la statistica della differenza tra la fetta e il resto: una fetta diventa ipotesi già a t ≤ −1,3, ma per passare la validazione serve molto di più.' });
  const weakBox = h('div', { class: 'sp-weaks' });
  pWeak.body.append(weakBox);

  // ---- 8. regole provate ----
  const pRules = panel({ title: 'Che cosa ha provato, e perché è stato respinto?', eyebrow: 'Regole proposte · i sei controlli', span: 12, id: 'regole',
    ask: 'Ogni riga è una correzione proposta. I sei segni dicono quali controlli ha superato; apri la riga per leggere il motivo di ognuno.',
    what: 'Il validatore è separato da chi propone ed è sempre lo stesso. Soglia in campione: t ≤ −√(2 ln K), mai sotto 2, con K = ipotesi provate fino a quel momento: cercare di più rende più difficile passare, non più facile. Guadagno in R = R che la regola avrebbe aggiunto (negativo: avrebbe tolto trade buoni).' });
  const rulesBox = h('div', { class: 'sp-rules' });
  pRules.body.append(rulesBox);

  // ---- 9. in ombra e attive ----
  const pShadow = panel({ title: 'Che cosa è in osservazione?', eyebrow: 'In ombra', span: 6, id: 'ombra',
    what: 'Regole che hanno superato la validazione sui dati storici e ora vengono solo osservate sui trade del conto di prova: si annota che cosa avrebbero fatto, senza toccare nulla. Quando i trade osservati bastano e la regola regge, diventa «promuovibile»: da lì serve il comando del proprietario.' });
  const shadowBox = h('div', { class: 'sp-shadows' });
  pShadow.body.append(shadowBox);
  const pActive = panel({ title: 'Che cosa è in funzione?', eyebrow: 'Attive', span: 6, id: 'attive',
    what: 'Regole approvate a mano dal proprietario. Possono solo saltare un trade o dimezzarne la taglia: non possono aumentare rischio, leva o esposizione, né toccare stop e limiti.' });
  const activeBox = h('div', { class: 'sp-shadows' });
  pActive.body.append(activeBox);

  // ---- 10. registro ----
  const pReg = panel({ title: 'Registro delle ipotesi', eyebrow: 'Ogni ipotesi provata resta qui per sempre', span: 12, cls: 'not-semplice', id: 'registro',
    what: 'Il registro non si cancella: è il conteggio che alza la soglia per le ipotesi successive.' });
  const regBox = h('div');
  pReg.body.append(regBox);

  const missing = h('div');
  root.append(missing, h('div', { class: 'ws sp-ws' }, pLoop.el, pEval.el, pDist.el, pCum.el, pSlices.el, pMae.el, pWeak.el, pRules.el, pShadow.el, pActive.el, pReg.el));

  // ---- disegno ----
  const L = () => obj(ctxNow.learn);
  const learnTags = () => [L().example ? provTag('demo') : null, L().simulated ? provTag('sim') : null];
  const rows = (src) => arr(obj(trades).rows).filter((r) => str(r.source) === src && num(r.R) != null);
  const tradeTags = (src) => [obj(trades).example || /^ESEMPIO/i.test(str(obj(trades).label)) ? provTag('demo') : null, provTag(src === 'paper' ? 'paper' : 'sim')];

  function paintLoop() {
    const imp = obj(L().improvement);
    const ev = obj(L().evaluation);
    const all = obj(ev.all);
    const paper = obj(ev.paper);
    const proposed = arr(imp.proposed);
    const rej = proposed.filter((r) => str(r.state).toUpperCase() === 'RESPINTA').length;
    const shadow = arr(imp.shadow);
    const ready = shadow.filter((r) => r.ready === true || str(r.state).toUpperCase() === 'PROMUOVIBILE').length;
    const active = arr(imp.active);
    const has = !!ctxNow.learn;
    const n = (v) => (has && num(v) != null ? fmtNum(v, 0) : 'n.d.');
    const steps = [
      { title: 'Memoria dei trade', sub: 'tutto annotato', live: `${n(all.n)} trade`, word: has ? `${n(num(all.n) - (num(paper.n) || 0))} simulati · ${n(paper.n || 0)} paper` : '', state: has ? 'ok' : 'unknown',
        text: 'Ogni trade chiuso viene annotato con il suo contesto: prezzi, stop, costi, motivo dell\'uscita. Senza memoria non si impara nulla.' },
      { title: 'Valutazione', sub: 'dove si perde', live: `${n(arr(L().weaknesses).length)} fette deboli`, state: has ? 'ok' : 'unknown',
        text: 'Il sistema misura come vanno i trade e cerca le «fette» (un giorno, un livello di volatilità…) che rendono chiaramente meno del resto.' },
      { title: 'Ipotesi', sub: 'una correzione proposta', live: `${n(proposed.length)} in questo giro`, word: has && num(imp.tried) != null ? `${fmtNum(imp.tried, 0)} provate in tutto` : '', state: has ? 'ok' : 'unknown',
        text: 'Da ogni debolezza nasce una regola semplice: «se accade X, salta il trade» oppure «dimezzalo». Proporre è facile: il difficile viene dopo.' },
      { title: 'Validazione', sub: 'sei controlli', guard: true, live: `${n(rej)} respinte su ${n(proposed.length)}`, word: has && num(imp.threshold_t) != null ? `soglia t ≤ −${fmtNum(imp.threshold_t, 2)}` : '', state: has ? 'ok' : 'unknown',
        text: 'Un validatore separato da chi propone, sempre uguale, sottopone la regola a sei controlli. Quasi tutte vengono respinte: è il comportamento atteso.' },
      { title: 'Ombra', sub: 'osservata, non applicata', live: `${n(shadow.length)} in osservazione`, state: has ? (shadow.length ? 'warn' : 'idle') : 'unknown',
        text: 'Una regola che passa non agisce subito: sui nuovi trade del paper si annota che cosa avrebbe fatto, senza toccare nulla.' },
      { title: 'Approvazione', sub: 'solo a mano, del proprietario', guard: true, live: `${n(ready)} promuovibili`, word: 'solo da terminale', state: has ? (ready ? 'warn' : 'idle') : 'unknown',
        text: 'Una regola che regge anche in ombra non si attiva da sola: serve un comando esplicito del proprietario. Questa pagina non può darlo.' },
      { title: 'Attiva', sub: 'salta o dimezza', live: `${n(active.length)} in funzione`, state: has ? (active.length ? 'ok' : 'idle') : 'unknown',
        text: 'Da quel momento la regola agisce sui nuovi trade: li salta o ne dimezza la taglia. I nuovi trade tornano nella memoria e il ciclo ricomincia.' },
    ];
    const el = stepper(steps, { label: 'Il ciclo di automiglioramento, con i conteggi del rapporto più recente' });
    el.style.setProperty('--cols', ctxNow.lv === 'semplice' ? '4' : '7');
    el.classList.add(ctxNow.lv === 'semplice' ? 'sp-steps--4' : 'sp-steps--7');
    loopBox.replaceChildren(el);
    guards.replaceChildren(
      h('div', { class: 'sp-guard' }, icon('risk'), h('div', null, h('b', { text: 'Chi propone non approva.' }), h('p', { text: 'Le ipotesi le genera la valutazione; il verdetto lo dà solo il validatore; l\'attivazione spetta al proprietario.' }))),
      h('div', { class: 'sp-guard' }, icon('pause'), h('div', null, h('b', { text: 'Una regola può solo saltare o dimezzare un trade.' }), h('p', { text: 'Non può aumentare rischio, leva o esposizione, né toccare stop e limiti.' }))),
      h('div', { class: 'sp-guard' }, icon('up'), h('div', null, h('b', { text: 'Ogni ipotesi provata alza la soglia.' }), h('p', { text: num(imp.tried) == null ? 'Cercare di più rende più difficile passare, non più facile.' : `Finora ${fmtNum(imp.tried, 0)} provate: la soglia è t ≤ −${fmtNum(imp.threshold_t, 2)}. Cercare di più rende più difficile passare.` }))));
    pLoop.setProv(...learnTags());
    const gen = parseTs(str(L().generated).replace(' ', 'T').replace(/(\.\d+)?\+00:00$/, 'Z'));
    pLoop.setFoot(gen == null ? 'Data del rapporto: n.d.' : `Rapporto del ${fmtDate(gen, true)}. Si rigenera con: `, gen == null ? null : h('code', { class: 'sp-code', text: 'python -m gerva learn' }));
  }

  function evalBlock(title, ev, tags, { paper = false } = {}) {
    const n = num(ev.n);
    const p = obj(ev.performance);
    const k = obj(ev.risk);
    const head = h('div', { class: 'sp-evalhead' }, h('b', { text: title }), ...tags.filter(Boolean), h('span', { class: 'num', text: n ? `${fmtNum(n, 0)} trade${num(ev.per_year) == null ? '' : ` · circa ${fmtNum(ev.per_year, 0)} l'anno`}` : '0 trade' }));
    if (!n) return h('div', { class: 'sp-eval' }, head, emptyState(paper ? 'Nessun trade paper ancora' : 'Nessun trade in memoria', paper ? 'Questa colonna si riempie con i trade chiusi dal conto di prova. Fino ad allora i numeri a sinistra restano simulazioni storiche: non dicono come va il conto.' : 'La memoria dei trade è vuota.'));
    return h('div', { class: 'sp-eval' }, head, h('dl', { class: 'sp-evalgrid' },
      statWell('R medio per trade', h('span', { class: p.mean_R > 0 ? 'pos' : p.mean_R < 0 ? 'neg' : '', text: rr(p.mean_R) })), statWell('Vincenti', num(p.win_rate) == null ? 'n.d.' : fmtPct(p.win_rate, 0)), statWell('Profit factor', num(p.profit_factor) == null ? 'n.d.' : fmtNum(p.profit_factor, 2)),
      statWell('t', num(p.t_stat) == null ? 'n.d.' : fmtSigned(p.t_stat, 2)), statWell('Serie perdente', num(k.max_losing_streak) == null ? 'n.d.' : `${fmtNum(k.max_losing_streak, 0)} di fila`), statWell('Caduta peggiore', num(k.max_drawdown_R) == null ? 'n.d.' : `${fmtNum(k.max_drawdown_R, 1)} R`)),
    h('div', { class: 'not-semplice' }, factRow([['R totale', num(p.total_R) == null ? 'n.d.' : `${fmtSigned(p.total_R, 1)} R`], ['Payoff', num(p.payoff) == null ? 'n.d.' : fmtNum(p.payoff, 2)], ['Kelly', num(p.kelly_fraction) == null ? 'n.d.' : fmtPct(p.kelly_fraction, 1)], ['Trade peggiore', rr(k.worst_R)], ['VaR 95%', rr(k.var95_R)], ['CVaR 95%', rr(k.cvar95_R)]])));
  }

  function paintEval() {
    const ev = obj(L().evaluation);
    const all = obj(ev.all);
    const paper = obj(ev.paper);
    const by = obj(all.by_source);
    const simN = num(obj(by.sim).n) || 0;
    const mixed = simN > 0 && (num(paper.n) || 0) > 0;
    pEval.setProv(...learnTags());
    evalBox.replaceChildren(
      h('div', null, evalBlock('Tutti i trade in memoria', all, [simN ? provTag('sim', `Simulati ${fmtNum(simN, 0)}`) : null, provTag('paper', `Paper ${fmtNum(paper.n || 0, 0)}`)]),
        mixed ? h('p', { class: 'panel__ask', text: 'Questa colonna contiene simulati e paper insieme: è la memoria su cui lavora il ciclo, non un giudizio sul conto. Per quello vale solo la colonna «Solo paper».' }) : null),
      evalBlock('Solo paper', paper, [provTag(L().example ? 'demo' : 'paper', L().example ? 'Esempio' : 'Paper')], { paper: true }));
    const rob = obj(all.robustness);
    const rp = obj(rob.recent_vs_past);
    const exits = Object.entries(obj(rob.by_exit)).filter(([, v]) => num(obj(v).mean_R) != null);
    const by2 = Object.fromEntries(Object.entries(obj(rob.by_year)).map(([y, v]) => [y, num(obj(v).mean_R)]));
    pEval.setFoot(...[exits.length ? h('span', null, 'Per uscita: ', exits.map(([k, v], i) => `${i ? ' · ' : ''}${k === 'stop' ? 'allo stop' : k === 'tempo' ? 'a tempo' : k} ${rr(v.mean_R)} (n ${fmtNum(v.n, 0)})`).join('')) : null,
      num(rp.recent_mean_R) == null ? null : h('span', null, ` Ultimi ${fmtNum(rp.recent_n, 0)} trade ${rr(rp.recent_mean_R)} contro ${rr(rp.past_mean_R)} prima${num(rp.t) == null ? '' : ` (t ${fmtSigned(rp.t, 2)})`}: ${num(rp.t) != null && rp.t <= -2 ? 'peggioramento netto, da capire' : 'nessun peggioramento evidente'}.`),
      Object.keys(by2).length ? h('span', { class: 'not-semplice sp-inline' }, 'R medio per anno, tutta la memoria: ', yearStrip(by2, { scale: 0.6, digits: 2, name: 'R medio' })) : null].filter(Boolean));
  }

  function paintDist() {
    if (trades === undefined) { distPlot.el.hidden = true; distFacts.replaceChildren(emptyState('Storico dei trade in lettura…')); distPaper.replaceChildren(); return; }
    const sim = rows('sim').map((r) => r.R);
    const paper = rows('paper').map((r) => r.R);
    if (!sim.length && !paper.length) { distPlot.el.hidden = true; distFacts.replaceChildren(emptyState('Storico dei trade non disponibile', 'Il motore non ha ancora scritto lo storico dei trade (simulati e paper).')); distPaper.replaceChildren(); pDist.setProv(); return; }
    pDist.setProv(...tradeTags('sim'));
    const st = rStats(sim);
    const top5 = [...sim].sort((a, b) => b - a).slice(5);
    distPlot.el.hidden = !sim.length;
    distFacts.replaceChildren(factRow([['R medio', rr(st.mean), st.mean > 0 ? 'pos' : 'neg'], ['Mediana', rr(st.median)], ['Vincenti', st.win == null ? 'n.d.' : fmtPct(st.win, 0)], ['Senza i 5 migliori', top5.length ? rr(rStats(top5).mean) : 'n.d.'], ['n', fmtNum(st.n, 0)]]));
    if (sim.length) {
      const hist = histR(sim, 0.25, -1.5, 6);
      distPlot.setTags(provTag('sim', `Simulato · n = ${fmtNum(st.n, 0)}`));
      distChart.update({ edges: hist.edges, counts: hist.counts, tagSide: 'right', ticks: [-1, 0, 1, 2, 3, 4, 5, 6], unit: 'Trade', height: ctxNow.lv === 'terminale' ? 150 : 190, tone: (mid) => (mid >= 0 ? 'up' : 'down'), xFormat: (v) => (v === 0 ? '0' : fmtSigned(v, Number.isInteger(v) ? 0 : 2)), overflow: `oltre +${fmtNum(hist.overflowFrom, 0)} R`, xTitle: 'risultato del trade, in R →',
        refs: [{ value: 0, label: 'zero', cls: 'strong' }, { value: st.mean, label: `media ${rr(st.mean)}` }, { value: st.median, label: `mediana ${rr(st.median)}`, cls: 'soft', side: 'left' }] });
    }
    distPaper.replaceChildren(paper.length ? factRow([['Paper · R medio', rr(rStats(paper).mean)], ['Paper · n', fmtNum(paper.length, 0)]]) : h('p', { class: 'panel__ask' }, provTag('paper'), ` 0 trade chiusi in paper: quando esisteranno avranno il loro grafico, a colonne piene, mai sommato a questo.`));
    pDist.setFoot(`R = P&L del trade / rischio iniziale, netto di commissioni e funding; classi da 0,25 R, l'ultima raccoglie tutto ciò che supera +6 R. ${str(obj(trades).label)}.`);
  }

  function paintCum() {
    if (!trades) { cumPlot.el.hidden = true; cumFacts.replaceChildren(trades === undefined ? emptyState('Storico dei trade in lettura…') : emptyState('Storico dei trade non disponibile')); return; }
    const mk = (src) => rows(src).map((r) => ({ t: parseTs(str(r.exit_time)), R: r.R })).filter((r) => r.t != null).sort((a, b) => a.t - b.t);
    const sim = mk('sim');
    const paper = mk('paper');
    if (sim.length + paper.length < 2) { cumPlot.el.hidden = true; cumFacts.replaceChildren(emptyState('Troppo pochi trade', 'Servono almeno due trade chiusi per disegnare il percorso.')); return; }
    cumPlot.el.hidden = false;
    pCum.setProv(...tradeTags('sim'), paper.length ? provTag('paper') : null);
    const x = [...new Set([...sim, ...paper].map((r) => r.t))].sort((a, b) => a - b);
    const line = (list) => { let acc = 0; let i = 0; let started = false; return x.map((t) => { while (i < list.length && list[i].t <= t) { acc += list[i].R; i++; started = true; } return started ? acc : null; }); };
    const a = line(sim);
    const b = paper.length ? line(paper) : null;
    let peak = -Infinity;
    let dd = 0;
    for (const v of a) if (v != null) { peak = Math.max(peak, v); dd = Math.min(dd, v - peak); }
    const top = [...sim].sort((p, q) => q.R - p.R).slice(0, 5).reduce((s, r) => s + r.R, 0);
    const tot = sim.reduce((s, r) => s + r.R, 0);
    cumFacts.replaceChildren(factRow([['R totale', `${fmtSigned(tot, 1)} R`], ['Caduta peggiore', `${fmtNum(dd, 1)} R`], ['Dai 5 trade migliori', tot > 0 ? fmtPct(top / tot, 0) : 'n.d.'], paper.length ? ['Paper', `${fmtSigned(paper.reduce((s, r) => s + r.R, 0), 1)} R`] : ['Paper', '0 trade']]));
    cumPlot.setTags(provTag('sim', `Simulato · n = ${fmtNum(sim.length, 0)}`), paper.length ? provTag('paper', `Paper · n = ${fmtNum(paper.length, 0)}`) : null);
    cumChart.update({ x, marks: [{ t: SPLIT_T, label: 'scelta | verifica' }],
      panels: [{ height: ctxNow.lv === 'terminale' ? 170 : 210, series: [{ values: a, cls: 'fund sim', step: true, end: true, name: 'Simulati' }, ...(b ? [{ values: b, cls: 'paper', step: true, end: true, name: 'Paper' }] : [])], format: (v) => `${fmtSigned(v, 0)} R`, refs: [{ value: 0, label: '' }] }],
      tip: (i) => ({ title: fmtDate(x[i], true), rows: [{ key: 'fund-sim', label: 'Simulati, cumulato', value: a[i] == null ? '—' : `${fmtSigned(a[i], 1)} R` }, ...(b ? [{ key: 'paper', label: 'Paper, cumulato', value: b[i] == null ? '—' : `${fmtSigned(b[i], 1)} R` }] : [])] }) });
    pCum.setFoot(legendRow([['fund-sim', 'trade simulati'], b ? ['paper', 'trade paper'] : null]), 'Gradini alla data di uscita di ogni trade.');
  }

  function paintSlices() {
    if (!trades) { sliceGrid.hidden = true; sliceNote.replaceChildren(trades === undefined ? emptyState('Storico dei trade in lettura…') : emptyState('Storico dei trade non disponibile')); return; }
    const list = rows(source);
    pSlices.setProv(...tradeTags(source));
    if (!list.length) {
      sliceGrid.hidden = true;
      sliceNote.replaceChildren(emptyState(source === 'paper' ? 'Nessun trade paper ancora' : 'Nessun trade simulato', source === 'paper' ? 'Le barre per fetta dei trade del conto di prova compariranno con i primi trade chiusi. Con meno di 30 per gruppo saranno attenuate: troppo pochi per dire qualcosa.' : 'Lo storico non contiene trade simulati.'));
      return;
    }
    sliceGrid.hidden = false;
    const all = rStats(list.map((r) => r.R));
    const rules = obj(obj(ctxNow.health).rules);
    const c1 = num(rules.score_confirmed);
    const c2 = num(rules.score_exceptional);
    const convKey = (r) => (c1 == null || num(r.conviction) == null ? (str(r.tier) || null) : r.conviction >= c2 ? `eccezionale (da ${fmtNum(c2, 2)})` : r.conviction >= c1 ? `confermato (${fmtNum(c1, 2)}–${fmtNum(c2, 2)})` : `sotto soglia (< ${fmtNum(c1, 2)})`);
    const sets = {
      conv: groupR(list, convKey), day: groupR(list, (r) => (num(r.weekday) == null ? null : num(r.weekday)), [0, 1, 2, 3, 4, 5, 6]).map((g) => ({ ...g, key: DAYS[g.key] || String(g.key) })),
      coin: groupR(list, (r) => str(r.symbol) || null), year: groupR(list, (r) => (parseTs(str(r.entry_time)) == null ? null : new Date(parseTs(str(r.entry_time))).getUTCFullYear())).map((g) => ({ ...g, key: `${g.key}${g.key >= new Date(SPLIT_T).getUTCFullYear() ? '' : ' · scelta'}` })),
    };
    for (const s of SL) s.chart.update({ rows: sets[s.key].map((g) => ({ label: g.key, mean: g.mean, lo: g.lo, hi: g.hi, n: g.n, win: g.win })), ref: { value: all.mean, label: `media ${rr(all.mean)}` }, solid: source === 'paper' });
    sliceNote.replaceChildren(factRow([[source === 'paper' ? 'Trade paper' : 'Trade simulati', fmtNum(all.n, 0)], ['Media generale', rr(all.mean), all.mean > 0 ? 'pos' : 'neg'], ['Intervallo al 90%', all.lo == null ? 'n.d.' : `${rr(all.lo)} … ${rr(all.hi)}`]]),
      legendRow([[all.mean >= 0 ? 'up' : 'down', source === 'paper' ? 'R medio (pieno = paper)' : 'R medio (velato = simulato)'], ['whisker', 'intervallo al 90%'], [null, '* meno di 30 trade: attenuato']].map((x) => (x[0] ? x : ['none', x[1]]))));
    pSlices.setFoot(`Anni dal ${new Date(SPLIT_T).getUTCFullYear()} = periodo di verifica. Soglie di conviction lette dalle regole del motore${c1 == null ? ' (non lette: si usa il livello annotato nel trade)' : ''}. ${str(obj(trades).label)}.`);
  }

  function paintMae() {
    if (trades === undefined) { maeBox.replaceChildren(emptyState('Storico dei trade in lettura…')); return; }
    const pts = rows('paper').filter((r) => num(r.mae) != null && num(r.mfe) != null).map((r) => ({ x: r.mae, y: r.mfe, group: r.R > 0 ? 'win' : 'loss', label: `${str(r.symbol)} ${str(r.exit_time).slice(0, 10)}`, R: r.R }));
    pMae.setProv(provTag(obj(trades).example ? 'demo' : 'paper', obj(trades).example ? 'Esempio' : 'Paper'));
    if (!pts.length) {
      maeChart = null;
      maeBox.replaceChildren(h('div', { class: 'sp-ghost' },
        h('div', { class: 'sp-ghost__plot', 'aria-hidden': 'true' }, h('span', { class: 'sp-ghost__y', text: 'MFE: guadagno massimo, in R ↑' }), h('span', { class: 'sp-ghost__x', text: '← MAE: perdita massima, in R' }), h('i'), h('i'), h('i')),
        h('div', { class: 'sp-ghost__text' }, h('p', { class: 'panel__empty-title', text: '0 trade paper chiusi' }),
          h('p', { class: 'panel__empty-text', text: 'Qui comparirà un punto per ogni trade chiuso dal conto di prova: pieno se ha vinto, ad anello se ha perso. Nelle simulazioni storiche MAE e MFE non sono annotati, quindi il grafico resta vuoto invece di mostrare numeri ricostruiti.' }))));
      pMae.setFoot('Solo trade paper con MAE e MFE annotati dal libro dei trade (learn/trades.jsonl).');
      return;
    }
    const opts = { label: 'MAE contro MFE dei trade paper, in R', height: 260, xTitle: 'MAE (R)', yTitle: 'MFE (R)', xFormat: (v) => fmtSigned(v, 1), yFormat: (v) => fmtSigned(v, 1), table: true,
      groups: [{ id: 'win', label: 'Vinti', cls: 'up' }, { id: 'loss', label: 'Persi', cls: 'down' }], refsX: [{ value: -1, label: '−1 R: lo stop' }],
      tip: (p) => ({ title: p.label, rows: [{ label: 'MAE', value: rr(p.x) }, { label: 'MFE', value: rr(p.y) }, { label: 'Risultato', value: rr(p.R) }] }) };
    if (!maeChart) maeChart = scatter(maeBox, pts, opts); else maeChart.update(pts);
    pMae.setFoot(`${fmtNum(pts.length, 0)} trade paper con MAE e MFE annotati.`);
  }

  function paintWeak() {
    const list = arr(L().weaknesses);
    pWeak.setProv(...learnTags());
    if (!list.length) { weakBox.replaceChildren(emptyState('Nessuna debolezza rilevata', 'Nessuna fetta di trade rende chiaramente meno delle altre.')); return; }
    weakBox.replaceChildren(...list.map((w) => {
      const c = obj(w.rule).feature ? obj(w.rule) : null;
      const top = Math.max(Math.abs(num(w.mean_R) || 0), Math.abs(num(w.rest_mean_R) || 0), 0.01) * 1.15;
      return h('div', { class: 'sp-weak' },
        h('div', { class: 'sp-weak__head' }, h('b', { text: c ? plainSlice(c.feature, c.op, c.value) : tidy(w.slice) }), stateChip(/^signif/i.test(str(w.level)) ? 'warn' : 'muted', /^signif/i.test(str(w.level)) ? 'Significativa' : 'Sospetta', { iconName: /^signif/i.test(str(w.level)) ? 'warn' : 'info' })),
        meterRow({ name: 'Questa fetta', sub: `${fmtNum(w.n, 0)} trade${num(w.share) == null ? '' : ` · ${fmtPct(w.share, 0)}`}`, value: Math.abs(num(w.mean_R) || 0), cap: null, scale: top, state: 'none', text: rr(w.mean_R) }),
        meterRow({ name: 'Tutti gli altri', value: Math.abs(num(w.rest_mean_R) || 0), cap: null, scale: top, state: 'ok', text: rr(w.rest_mean_R) }),
        h('p', { class: 'sp-weak__note' }, h('span', { class: 'not-semplice', text: `t ${num(w.t) == null ? 'n.d.' : fmtSigned(w.t, 2)} · R persi in tutto ${num(w.cost_total_R) == null ? 'n.d.' : fmtNum(w.cost_total_R, 1)} · ` }), str(w.action)));
    }));
  }

  function ruleItem(r) {
    const fails = Array.isArray(r.fails) ? r.fails.map(str) : [];
    const used = new Set();
    const checks = obj(r.checks);
    const items = CHECKS.map((c) => {
      const known = c.key in checks;
      const ok = checks[c.key] === true;
      const why = !known || ok ? null : fails.find((f, i) => !used.has(i) && c.find.test(f) && used.add(i));
      return { c, known, ok, why };
    });
    const passed = items.filter((x) => x.ok).length;
    const sel = obj(r.selection);
    const ver = obj(r.verification);
    return h('details', { class: 'sp-rule' },
      h('summary', { class: 'sp-rule__head' },
        h('span', { class: 'sp-rule__text', text: plainRule(r.rule) }), stateOf(r.state),
        h('span', { class: 'sp-rule__marks', role: 'img', 'aria-label': `${passed} controlli su ${CHECKS.length} superati` }, items.map((x) => h('i', { class: `sp-mark sp-mark--${!x.known ? 'na' : x.ok ? 'ok' : 'no'}`, title: `${x.c.label}: ${!x.known ? 'non valutato' : x.ok ? 'superato' : 'non superato'}` }, icon(!x.known ? 'circle' : x.ok ? 'check' : 'x')))),
        h('span', { class: 'sp-rule__meta num', text: `${passed} su ${CHECKS.length}` }), icon('arrow', 'sp-rule__caret')),
      h('div', { class: 'sp-rule__body' },
        h('ul', { class: 'sp-checks' }, items.map((x) => h('li', { class: `sp-check sp-check--${!x.known ? 'na' : x.ok ? 'ok' : 'no'}` }, icon(!x.known ? 'circle' : x.ok ? 'check' : 'x'),
          h('div', null, h('b', { text: x.c.label }), h('small', { text: ` ${x.c.hint}` }), x.why ? h('p', { text: tidy(x.why) }) : !x.known ? h('p', { text: 'Controllo non riportato nel rapporto.' }) : null)))),
        simpleTable('R medio dei trade colpiti dalla regola, in campione e fuori campione', [
          { label: 'Periodo', cell: (d) => d.name }, { label: 'Trade colpiti', cls: 'is-num', cell: (d) => rr(d.v.mean) }, { label: 'Tutti gli altri', cls: 'is-num', cell: (d) => rr(d.v.rest) },
          { label: 'Quanti colpiti', cls: 'is-num', cell: (d) => (num(d.v.n) == null ? null : fmtNum(d.v.n, 0)) }, { label: 't dei colpiti', cls: 'is-num not-semplice', cell: (d) => (num(d.v.t0) == null ? null : fmtSigned(d.v.t0, 2)) },
        ], [{ name: 'In campione (scelta, fino al 2022)', v: sel }, { name: 'Fuori campione (verifica, dal 2023)', v: ver }]),
        h('div', { class: 'not-semplice' }, factRow([['Soglia applicata', num(r.threshold_t) == null ? 'n.d.' : `t ≤ −${fmtNum(r.threshold_t, 2)}`], ['Ipotesi provate fin qui', num(r.k_tried) == null ? 'n.d.' : fmtNum(r.k_tried, 0)], ['Anni in cui regge', num(r.walk_forward) == null ? 'n.d.' : fmtPct(r.walk_forward, 0)],
          ['Guadagno in campione', num(r.gain_R_selection) == null ? 'n.d.' : `${fmtSigned(r.gain_R_selection, 1)} R`], ['Fuori campione', num(r.gain_R_verification) == null ? 'n.d.' : `${fmtSigned(r.gain_R_verification, 1)} R`], ['Proposta da', str(r.origin) || 'n.d.'], ['ID', str(r.id) || 'n.d.']]))));
  }

  function paintRules() {
    const list = arr(obj(L().improvement).proposed);
    pRules.setProv(...learnTags());
    if (!list.length) { rulesBox.replaceChildren(emptyState('Nessuna regola proposta in questo giro', 'Il sistema non ha trovato debolezze abbastanza nette da trasformare in ipotesi.')); return; }
    const rej = list.filter((r) => str(r.state).toUpperCase() === 'RESPINTA').length;
    rulesBox.replaceChildren(factRow([['Proposte in questo giro', fmtNum(list.length, 0)], ['Respinte', fmtNum(rej, 0)], ['Passate in ombra', fmtNum(list.length - rej, 0)]]),
      rej === list.length ? h('div', { class: 'verdict verdict--ok' }, h('b', { text: 'Tutte respinte: è l\'esito normale e sano. ' }), 'Una debolezza «sospetta» quasi mai regge a sei controlli severi, ed è meglio scartare una regola forse utile che attivarne una nata da una coincidenza.') : '',
      ...list.map(ruleItem));
  }

  const command = (id) => h('div', { class: 'sp-cmd' }, h('span', { text: 'Per attivarla, da terminale (solo il proprietario):' }), h('code', { class: 'sp-code', text: COMMAND(id) }));

  function paintShadowActive() {
    const imp = obj(L().improvement);
    const shadow = arr(imp.shadow);
    const active = arr(imp.active);
    pShadow.setProv(...learnTags());
    pActive.setProv(...learnTags());
    shadowBox.replaceChildren(...(shadow.length ? shadow.map((r) => {
      const n = num(r.n) ?? 0;
      const need = num(r.needed);
      const ready = r.ready === true || str(r.state).toUpperCase() === 'PROMUOVIBILE';
      return h('div', { class: 'sp-shadow' },
        h('div', { class: 'sp-weak__head' }, h('b', { text: plainRule(r.rule) }), stateOf(ready ? 'PROMUOVIBILE' : r.state || 'IN_OMBRA')),
        meterRow({ name: 'Trade paper osservati', value: n, cap: need, scale: need ? need * 1.05 : null, state: ready ? 'warn' : 'ok', text: need ? `${fmtNum(n, 0)} di ${fmtNum(need, 0)}` : fmtNum(n, 0) }),
        num(r.mean_R) == null ? null : h('p', { class: 'sp-weak__note', text: `Trade che avrebbe colpito: ${rr(r.mean_R)} · gli altri: ${rr(r.rest_mean_R)}` }),
        ready ? command(r.id) : h('p', { class: 'sp-weak__note', text: 'Non ancora promuovibile: servono più trade, e i trade colpiti devono rendere meno degli altri e meno di zero.' }));
    }) : [emptyState('Nessuna regola in ombra', 'Finora nessuna correzione ha superato la validazione sui dati storici.')]));
    pShadow.setFoot(h('span', null, 'Questa pagina non ha comandi per attivare una regola. Una regola promuovibile si attiva solo così, da terminale: '), h('code', { class: 'sp-code', text: COMMAND('<id>') }));
    activeBox.replaceChildren(...(active.length ? active.map((r) => h('div', { class: 'sp-shadow' }, h('div', { class: 'sp-weak__head' }, h('b', { text: plainRule(r.rule) }), stateOf('ATTIVA')), h('p', { class: 'sp-weak__note not-semplice', text: `ID ${str(r.id)}` })))
      : [emptyState('Nessuna regola attiva', 'Il sistema opera con le sue regole originali: nessuna correzione è stata approvata.')]));
    pActive.setFoot('Una regola attiva può solo saltare un trade o dimezzarne la taglia.');
  }

  function paintReg() {
    const list = arr(L().registry);
    regBox.replaceChildren(list.length ? simpleTable('Registro di tutte le ipotesi provate', [
      { label: 'Regola', cell: (r) => plainRule(r.rule) }, { label: 'Stato', cell: (r) => stateOf(r.state) }, { label: 'Verdetto di', cell: (r) => str(r.by) }, { label: 'Proposta da', cell: (r) => str(r.origin) }, { label: 'ID', cell: (r) => h('code', { class: 'sp-code', text: str(r.id) }) },
    ], list) : emptyState('Registro vuoto'));
  }

  function paintLearn() {
    const has = !!ctxNow.learn;
    missing.replaceChildren(...(has ? [] : [h('div', { class: 'placeholder glass sp-missing', role: 'status' }, h('p', { class: 'placeholder__title', text: ctxNow.learnStatus === 'loading' ? 'Rapporto in lettura…' : 'Il rapporto del ciclo di automiglioramento non c\'è ancora' }),
      ctxNow.learnStatus === 'loading' ? null : h('p', { class: 'placeholder__text' }, 'Si genera da terminale con ', h('code', { class: 'sp-code', text: 'python -m gerva learn' }), '. Qui non c\'è alcun comando che lo lanci: lo spazio è di sola lettura. Sotto restano i grafici dei trade.'))]));
    for (const p of [pEval, pWeak, pRules, pShadow, pActive, pReg]) p.el.hidden = !has;
    paintLoop();
    if (has) { paintEval(); paintWeak(); paintRules(); paintShadowActive(); paintReg(); }
  }

  function paintTrades() { paintDist(); paintCum(); paintSlices(); paintMae(); }

  getTrades().then((res) => { trades = res || null; if (ctxNow) paintTrades(); });

  let key = null;
  return {
    update(ctx) {
      const k = `${ctx.learnStatus}|${ctx.lv}|${ctx.learn ? str(ctx.learn.generated) + JSON.stringify(ctx.learn).length : ''}|${obj(obj(ctx.health).rules).score_confirmed}`;
      const first = !ctxNow;
      const lvChanged = ctxNow && ctxNow.lv !== ctx.lv;
      const changed = k !== key;
      ctxNow = ctx;
      if (changed) { key = k; paintLearn(); }              // il rapporto cambia solo quando gira `gerva learn`: le regole aperte restano aperte
      if (first || lvChanged || changed) paintTrades();
    },
    summary(ctx) {
      const l = obj(ctx.learn);
      if (!ctx.learn) return 'Il rapporto del ciclo di automiglioramento non è disponibile: si genera da terminale con «python -m gerva learn».';
      const imp = obj(l.improvement);
      const proposed = arr(imp.proposed);
      const rej = proposed.filter((r) => str(r.state).toUpperCase() === 'RESPINTA').length;
      const paper = num(obj(obj(l.evaluation).paper).n) || 0;
      return `Il ciclo ha in memoria ${fmtNum(obj(obj(l.evaluation).all).n, 0)} trade (${fmtNum(paper, 0)} del paper), ha proposto ${fmtNum(proposed.length, 0)} correzioni e ne ha respinte ${fmtNum(rej, 0)}. `
        + `${arr(imp.shadow).length ? `${fmtNum(arr(imp.shadow).length, 0)} in ombra` : 'Nessuna regola in ombra'}, ${arr(imp.active).length ? `${fmtNum(arr(imp.active).length, 0)} attive` : 'nessuna attiva'}: il sistema opera con le sue regole originali.`;
    },
  };
}
