// Leva per trade: quanto regge un'operazione a leva in funzione dello stop (quarta tornata di ricerca, tutto simulato).

import { h, fill } from '../dom.js';
import { card, chip, dataTable, empty, explain, method, segmented, signedPct, simTag } from '../components.js';
import { bullet, timeChart } from '../charts.js';
import { DASH, arr, fmtNum, fmtPct, fmtSigned, num, obj, stepDigits, str } from '../format.js';

const LABEL = 'SIMULATO: ricerca su dati storici';
const SCEN = [
  { value: 'base', label: 'Base', text: 'la storia si ripete così com\'è' },
  { value: 'pessimista', label: 'Pessimista', text: 'metà del vantaggio misurato' },
  { value: 'verifica', label: 'Verifica', text: 'solo i dati mai usati per scegliere le regole' },
  { value: 'stress', label: 'Stress', text: 'vantaggio ridotto e crisi più frequenti' },
];

/** sostenuta: leva ≤ 30x e R medio in verifica sopra 0,15; non sostenuta: oltre 30x; il resto è «debole». */
export function verdictOf(r) {
  const lev = num(r.leverage);
  const rv = num(r.mean_R_verify);
  if (lev == null || rv == null) return { label: 'Non valutabile', kind: 'muted', icon: 'info', code: 'na' };
  if (lev > 30.5) return { label: 'Non sostenuta', kind: 'crit', icon: 'x', code: 'no' };
  if (rv > 0.15) return { label: 'Sostenuta', kind: 'accent', icon: 'check', code: 'ok' };
  return { label: 'Debole in verifica', kind: 'muted', icon: 'off', code: 'weak' };
}

const lev = (v) => (num(v) == null ? DASH : `${fmtNum(v, num(v) % 1 ? 1 : 0)}x`);
const rr = (v) => (num(v) == null ? DASH : `${fmtSigned(v, 2)} R`);

export function mount(root) {
  let ctx = null;
  let key = null;
  const ui = { scenario: 'base', coin: 'BTC' };

  const head = h('div', { class: 'section-head span-12' });
  const missing = h('section', { class: 'card span-12' });

  const stopCard = card({
    title: 'Stop, leva e risultato per operazione', cls: 'span-12', flush: true, sim: LABEL,
    what: 'Ogni riga è una larghezza dello stop. Uno stop stretto permette una leva alta, ma viene colpito più spesso e i costi pesano di più. «R medio» è quanto rende in media un\'operazione rispetto a ciò che rischia: conta soprattutto la colonna «in verifica», calcolata su dati mai usati per scegliere le regole.',
    method: 'Leva = massimo consentito con stop ≤ 0,6 × distanza di liquidazione (tetto 50x). R medio al netto dei costi; t = statistica t della media; margine / rischio = distanza di liquidazione / stop.',
  });
  const stopTable = dataTable({
    caption: 'Risultato per operazione al variare dello stop e della leva',
    sort: { key: 'lev', dir: 1 },
    rowClass: (r) => `is-${verdictOf(r).code}`,
    columns: [
      { key: 'stop', label: 'Stop', sort: (r) => num(r.stop), cell: (r) => h('span', { class: 'code code--strong', text: str(r.label).replace('.', ',') || fmtPct(r.stop, 1) }) },
      { key: 'lev', label: 'Leva del trade', num: true, sort: (r) => num(r.leverage), cell: (r) => lev(r.leverage) },
      { key: 'verdict', label: 'Giudizio', sort: (r) => ({ ok: 0, weak: 1, no: 2, na: 3 }[verdictOf(r).code]), cell: (r) => chip(verdictOf(r), { compact: true }) },
      { key: 'liq', label: 'Dist. liquid.', num: true, hide: 'sm', sort: (r) => num(r.liq_distance), cell: (r) => (num(r.liq_distance) == null ? null : fmtPct(r.liq_distance, 1)) },
      { key: 'mr', label: 'Margine / rischio', num: true, cls: 'only-esperto', sort: (r) => (num(r.stop) ? num(r.liq_distance) / num(r.stop) : null), cell: (r) => (num(r.stop) && num(r.liq_distance) != null ? `${fmtNum(num(r.liq_distance) / num(r.stop), 2)}×` : null) },
      { key: 'n', label: 'Op. l\'anno', num: true, cls: 'only-esperto', sort: (r) => num(r.per_year), cell: (r) => (num(r.per_year) == null ? null : fmtNum(r.per_year, 0)) },
      { key: 'r', label: 'R medio', num: true, hide: 'sm', sort: (r) => num(r.mean_R), cell: (r) => rr(r.mean_R) },
      { key: 'rv', label: 'R in verifica', num: true, sort: (r) => num(r.mean_R_verify), cell: (r) => h('strong', { text: rr(r.mean_R_verify) }) },
      { key: 'hit', label: 'Vincenti', num: true, hide: 'md', sort: (r) => num(r.hit), cell: (r) => (num(r.hit) == null ? null : fmtPct(r.hit, 0)) },
      { key: 'streak', label: 'Serie perdente max', num: true, hide: 'md', sort: (r) => num(r.max_losing_streak), cell: (r) => (num(r.max_losing_streak) == null ? null : fmtNum(r.max_losing_streak, 0)) },
      { key: 'cost', label: 'Costo in R', num: true, cls: 'only-esperto', sort: (r) => num(r.cost_R), cell: (r) => (num(r.cost_R) == null ? null : fmtNum(r.cost_R, 3)) },
      { key: 't', label: 't', num: true, cls: 'only-esperto', sort: (r) => num(r.t), cell: (r) => (num(r.t) == null ? null : fmtSigned(r.t, 2)) },
      { key: 'liqn', label: 'Liquidazioni', num: true, cls: 'only-esperto', sort: (r) => num(r.liquidations), cell: (r) => (num(r.liquidations) == null ? null : fmtNum(r.liquidations, 0)) },
    ],
  });
  const stopNote = h('div', { class: 'card__note' });
  stopCard.body.append(stopTable.el, stopNote);

  const rCard = card({
    title: 'Più leva non vuol dire più rendimento', cls: 'span-7', sim: LABEL,
    what: 'Ogni punto è una riga della tabella, ordinata dalla leva più bassa alla più alta. La linea blu è il risultato sui dati di verifica. Fino a circa 30x resta sopra la soglia tratteggiata; a 50x, con stop strettissimi, scende sotto zero: i costi e i falsi segnali si mangiano tutto.',
    method: 'Asse x: righe ordinate per leva (non in scala). Soglia 0,15 R in verifica; oltre 30x la riga è «non sostenuta» a prescindere.',
  });
  const rLegend = h('div');
  const rHost = h('div', { class: 'chart-host' });
  rCard.body.append(rLegend, rHost);
  const rChart = timeChart(rHost, { label: 'R medio per operazione al crescere della leva, tutto lo storico e solo verifica. Frecce per scorrere.' });

  const ruleCard = h('section', { class: 'card rulecard span-5', 'aria-label': 'Tre cose da ricordare sulla leva per trade' });

  const scen = segmented({ label: 'Scenario della simulazione', options: SCEN, value: ui.scenario, onChange: (v) => { ui.scenario = v; paintTiers(); } });
  const tierCard = card({
    title: 'Quanto rischiare per operazione', actions: scen.el, cls: 'span-12', flush: true, sim: LABEL,
    what: 'Ogni schema fissa quanta parte del conto si rischia su un setup «confermato» e su uno «eccezionale» (per esempio 0,5% e 1%). La tabella simula tre anni: guarda come crescono insieme il rendimento e la probabilità di perdere il 30% o metà del conto quando il rischio per trade aumenta. La leva (11x o 30x) cambia poco; il rischio cambia tutto.',
    method: 'Monte Carlo a blocchi sul libro dei trade, tre anni. p(−30%) e p(dimezzato) = quota di percorsi il cui minimo scende sotto il 70% / 50% del capitale. dd 95° = caduta superata solo in un caso su venti.',
  });
  const tierTable = dataTable({
    caption: 'Esiti simulati per schema di rischio',
    emptyTitle: 'Nessuna simulazione per questo scenario',
    columns: [
      { key: 'schema', label: 'Schema', sort: (r) => str(r.schema), cell: (r) => h('span', { class: 'code code--strong', text: str(r.schema) }) },
      { key: 'cagr', label: 'Rend. annuo', num: true, sort: (r) => num(r.cagr_p50), cell: (r) => signedPct(r.cagr_p50, 1, { arrow: false }) },
      { key: 'c05', label: '5° pct', num: true, cls: 'only-esperto', sort: (r) => num(r.cagr_p05), cell: (r) => signedPct(r.cagr_p05, 1, { arrow: false }) },
      { key: 'dd', label: 'Caduta tipica', num: true, hide: 'sm', sort: (r) => num(r.dd_p50), cell: (r) => (num(r.dd_p50) == null ? null : fmtPct(r.dd_p50, 1)) },
      { key: 'dd95', label: 'Caduta 95°', num: true, cls: 'only-esperto', sort: (r) => num(r.dd_p95), cell: (r) => (num(r.dd_p95) == null ? null : fmtPct(r.dd_p95, 1)) },
      { key: 'm30', label: 'Prob. −30%', num: true, hide: 'sm', sort: (r) => num(r.p_meno30), cell: (r) => (num(r.p_meno30) == null ? null : fmtPct(r.p_meno30, 1)) },
      {
        key: 'half', label: 'Prob. dimezzare', num: true, cls: 'is-weight', sort: (r) => num(r.p_dimezzato),
        cell: (r) => { const p = num(r.p_dimezzato); return p == null ? null : h('div', { class: 'weight' }, bullet({ ratio: p, kind: p >= 0.2 ? 'crit' : p >= 0.02 ? 'warn' : 'ok', label: 'Probabilità di dimezzare il conto' }), h('span', { class: 'weight__value', text: fmtPct(p, 1) })); },
      },
      { key: 'mese', label: 'Mese medio', num: true, cls: 'only-esperto', sort: (r) => num(r.mese), cell: (r) => signedPct(r.mese, 1, { arrow: false }) },
    ],
  });
  tierCard.body.append(tierTable.el);

  const coinSeg = segmented({ label: 'Moneta', options: ['BTC', 'ETH', 'SOL'].map((c) => ({ value: c, label: c })), value: ui.coin, onChange: (v) => { ui.coin = v; paintStress(); } });
  const stressCard = card({
    title: 'Se la borsa non risponde e lo stop non scatta', actions: coinSeg.el, cls: 'span-12', sim: LABEL,
    what: 'Lo stop è un ordine: se la borsa è irraggiungibile può non essere eseguito. Il grafico dice quanto è probabile che, in quel caso, il prezzo percorra tutta la distanza fino alla liquidazione entro 1, 4 o 24 ore. A leva bassa è raro anche in un giorno intero; a 30x–50x succede spesso già in un\'ora. In quel caso si perde il margine isolato dell\'operazione, non il conto.',
    method: 'Frequenza storica, su barre orarie, dei movimenti contrari maggiori della distanza di liquidazione entro l\'orizzonte. Barre l\'anno oltre lo stop e oltre la liquidazione nella tabella.',
  });
  const sLegend = h('div');
  const sHost = h('div', { class: 'chart-host' });
  const sTable = h('div', { class: 'only-esperto stress-table' });
  stressCard.body.append(sLegend, sHost, sTable);
  const sChart = timeChart(sHost, { label: 'Probabilità di arrivare alla liquidazione entro 1, 4 e 24 ore, per leva. Frecce per scorrere.' });

  const cards = [stopCard, rCard, tierCard, stressCard];
  root.append(h('div', { class: 'grid' }, head, missing, stopCard.el, rCard.el, ruleCard, tierCard.el, stressCard.el));

  const q = () => obj(ctx.quant4);
  const sortedStops = () => arr(q().stop_table).filter((r) => num(r.leverage) != null).sort((a, b) => num(a.leverage) - num(b.leverage) || num(b.stop) - num(a.stop));

  function paintStops() {
    const rows = arr(q().stop_table);
    stopTable.render(rows);
    const ok = rows.filter((r) => verdictOf(r).code === 'ok').sort((a, b) => num(a.leverage) - num(b.leverage));
    fill(stopNote, explain(ok.length
      ? `Reggono alla verifica gli stop «${ok.map((r) => `${str(r.label).replace('.', ',')} (${lev(r.leverage)})`).join('», «')}». Le righe a 50x non sono sostenute: lo stop è così stretto che quasi tutte le operazioni vengono chiuse in perdita.`
      : 'Nessuna riga supera la soglia in verifica.'));
    const ratio = rows.map((r) => (num(r.stop) && num(r.liq_distance) != null ? num(r.liq_distance) / num(r.stop) : null)).filter((v) => v != null && v < 3);
    const typical = ratio.length ? ratio.sort((a, b) => a - b)[Math.floor(ratio.length / 2)] : 1.7;
    fill(ruleCard, h('div', { class: 'rulecard__body' },
      h('h2', { class: 'rulecard__title', text: 'Tre cose da ricordare' }),
      h('ol', { class: 'rules' },
        h('li', null, h('strong', { text: 'La leva segue dallo stop. ' }), 'Non si sceglie «quanta leva»: si sceglie dove mettere lo stop, e la leva possibile ne discende. Stop largo, leva bassa; stop stretto, leva alta.'),
        h('li', null, h('strong', { text: 'Su un\'operazione si può perdere il margine isolato. ' }), `È circa ${fmtNum(typical, 1)} volte il rischio dichiarato: se rischi 100 e lo stop non viene eseguito, la perdita peggiore è intorno a ${fmtNum(typical * 100, 0)}. Il resto del conto non è toccato.`),
        h('li', null, h('strong', { text: 'Rendimento e rovina dipendono dal rischio per trade, non dalla leva. ' }), 'Raddoppiare il rischio per trade raddoppia circa guadagni e cadute. A 30x lo stop è più stretto e scatta più spesso (18% di trade vincenti contro 43% a 11x): per avere cadute simili il rischio per trade va dimezzato.'))));
  }

  function paintR() {
    const rows = sortedStops();
    const ok = rows.length >= 2;
    rHost.hidden = !ok;
    if (!ok) { rChart.update(null); fill(rLegend, empty('Grafico non disponibile')); return; }
    const x = rows.map((_, i) => i * 1e9);
    const all = rows.map((r) => num(r.mean_R));
    const ver = rows.map((r) => num(r.mean_R_verify));
    const firstNo = rows.findIndex((r) => num(r.leverage) > 30.5);
    fill(rLegend, h('div', { class: 'legend' },
      h('span', { class: 'legend__item' }, h('span', { class: 'key key--fund', 'aria-hidden': 'true' }), h('span', { text: 'In verifica' })),
      h('span', { class: 'legend__item' }, h('span', { class: 'key key--bench', 'aria-hidden': 'true' }), h('span', { text: 'Tutto lo storico' }))));
    rChart.update({
      x, xTicks: rows.map((r, i) => ({ t: x[i], label: lev(r.leverage) })).filter((_, i) => rows.length <= 8 || i % 2 === 0 || i === rows.length - 1),
      marks: firstNo > 0 ? [{ t: (x[firstNo - 1] + x[firstNo]) / 2, label: 'oltre 30x: non sostenuta' }] : [],
      panels: [{
        height: 230, format: (v, st) => `${fmtSigned(v, Math.max(1, stepDigits(st, 2)))} R`,
        refs: [{ value: 0, label: '' }, { value: 0.15, label: 'soglia 0,15 R in verifica' }],
        series: [{ values: all, cls: 'bench', dots: true }, { values: ver, cls: 'fund', dots: true }],
      }],
      tip: (i) => ({
        title: `Stop ${str(rows[i].label).replace('.', ',')} · leva ${lev(rows[i].leverage)}`,
        rows: [{ key: 'fund', label: 'R medio in verifica', value: rr(ver[i]) }, { key: 'bench', label: 'R medio, tutto lo storico', value: rr(all[i]) }, { label: 'Giudizio', value: verdictOf(rows[i]).label }],
      }),
      say: (i) => `Stop ${str(rows[i].label)}, leva ${lev(rows[i].leverage)}: R medio in verifica ${rr(ver[i])}, ${verdictOf(rows[i]).label.toLowerCase()}`,
    });
  }

  function paintTiers() {
    tierTable.render(arr(q().tier_mc).filter((r) => str(r.scenario) === ui.scenario));
    const s = SCEN.find((x) => x.value === ui.scenario);
    tierCard.setSub(`Scenario ${s.label.toLowerCase()}: ${s.text}. Tre anni simulati migliaia di volte.`);
  }

  function paintStress() {
    const all = arr(q().stress);
    const coins = [...new Set(all.map((r) => str(r.coin)))];
    if (coins.length && !coins.includes(ui.coin)) ui.coin = coins[0];
    const rows = all.filter((r) => str(r.coin) === ui.coin && num(r.leverage) != null).sort((a, b) => num(a.leverage) - num(b.leverage));
    const ok = rows.length >= 2;
    sHost.hidden = !ok;
    if (!ok) { sChart.update(null); fill(sLegend, empty('Analisi di stress non disponibile')); fill(sTable); return; }
    const x = rows.map((r) => Math.log10(num(r.leverage)) * 1e9);
    const s1 = rows.map((r) => num(r.p_liq_1h));
    const s4 = rows.map((r) => num(r.p_liq_4h));
    const s24 = rows.map((r) => num(r.p_liq_24h));
    fill(sLegend, h('div', { class: 'legend' },
      [['s1', 'Entro 1 ora'], ['s2', 'Entro 4 ore'], ['s3', 'Entro 24 ore']].map(([k, t]) => h('span', { class: 'legend__item' }, h('span', { class: `key key--${k}`, 'aria-hidden': 'true' }), h('span', { text: t })))));
    sChart.update({
      x, xTicks: rows.map((r, i) => ({ t: x[i], label: lev(r.leverage) })),
      panels: [{ height: 220, bottom: 0, format: (v, st) => fmtPct(v, stepDigits((st ?? 1) * 100, 1)), series: [{ values: s24, cls: 's3', dots: true }, { values: s4, cls: 's2', dots: true }, { values: s1, cls: 's1', dots: true }] }],
      tip: (i) => ({
        title: `${ui.coin} · leva ${lev(rows[i].leverage)} · liquidazione a ${fmtPct(rows[i].liq_distance, 1)}`,
        rows: [{ key: 's1', label: 'Entro 1 ora', value: fmtPct(s1[i], 2) }, { key: 's2', label: 'Entro 4 ore', value: fmtPct(s4[i], 2) }, { key: 's3', label: 'Entro 24 ore', value: fmtPct(s24[i], 2) }],
        note: 'probabilità che il prezzo copra la distanza di liquidazione',
      }),
      say: (i) => `${ui.coin}, leva ${lev(rows[i].leverage)}: ${fmtPct(s1[i], 2)} entro un'ora, ${fmtPct(s24[i], 2)} entro 24 ore`,
    });
    fill(sTable, h('div', { class: 'table-wrap' }, h('table', { class: 'mini mini--wide' },
      h('thead', null, h('tr', null, ['Leva', 'Distanza dello stop', 'Distanza di liquidazione', 'Barre l\'anno tra stop e liquidazione', 'Barre l\'anno oltre la liquidazione'].map((t, i) => h('th', { scope: 'col', class: i ? 'num' : null, text: t })))),
      h('tbody', null, rows.map((r) => h('tr', null, h('th', { scope: 'row', class: 'num', text: lev(r.leverage) }),
        h('td', { class: 'num', text: fmtPct(r.stop_distance, 1) }), h('td', { class: 'num', text: fmtPct(r.liq_distance, 1) }),
        h('td', { class: 'num', text: fmtNum(r.bars_stop_to_liq_per_year, 1) }), h('td', { class: 'num', text: fmtNum(r.bars_beyond_liq_per_year, 1) })))))));
  }

  return {
    update(next) {
      ctx = next;
      const k = `${ctx.quant4Status}|${ctx.quant4 ? str(ctx.quant4.generated) + JSON.stringify(ctx.quant4).length : ''}`;
      if (k === key) return;
      key = k;
      const has = !!ctx.quant4;
      for (const c of cards) c.el.hidden = !has;
      ruleCard.hidden = !has;
      missing.hidden = has;
      fill(head, h('h2', { class: 'section-head__title', text: 'Leva per singola operazione' }), simTag(LABEL),
        has ? explain('Qui si guarda una sola operazione alla volta, non il conto. La domanda è: con quale stop e quale leva un\'operazione rende, in media, più di quanto costa? Tutti i numeri sono simulati sui dati storici.') : null,
        has ? method('Quarta tornata di ricerca (research/v5/quant_v4.json): operazioni su perpetual crypto con stop fisso o in multipli di ATR, costi inclusi.') : null);
      if (!has) {
        fill(missing, ctx.quant4Status === 'loading' ? empty('Caricamento della ricerca…')
          : empty('Ricerca non disponibile', ctx.quant4Status === 'missing' ? 'Il file research/v5/quant_v4.json non c\'è: lo genera research/v5/v4/export_v4.py.' : 'Il file della ricerca non si legge. Nuovo tentativo tra un minuto.'));
        return;
      }
      paintStops(); paintR(); paintTiers(); paintStress();
    },
    summary(c) {
      const rows = arr(obj(c.quant4).stop_table).filter((r) => verdictOf(r).code === 'ok').sort((a, b) => num(a.leverage) - num(b.leverage));
      if (!c.quant4) return 'I risultati della quarta tornata di ricerca non sono disponibili in questo momento.';
      if (!rows.length) return 'Nelle simulazioni nessuna combinazione di stop e leva supera la soglia sui dati di verifica.';
      return `Nelle simulazioni una singola operazione regge fino a circa ${lev(rows[rows.length - 1].leverage)} (stop ${str(rows[rows.length - 1].label).replace('.', ',')}); a 50x non regge. La leva segue dallo stop: quanto si guadagna o si perde lo decide il rischio per trade.`;
    },
  };
}
