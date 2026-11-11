// Panoramica: prima il patrimonio e il risultato di giornata, poi lo stato del rischio, poi l'andamento.

import { h, icon, fill, loadPref, savePref } from '../dom.js';
import { card, chip, dataTable, empty, explain, more, pair, segmented, signedMoney, signedPct, stat, toggle } from '../components.js';
import { bullet, columns, sparkline, timeChart } from '../charts.js';
import { DASH, arr, fmtAge, fmtAxisAmount, fmtDate, fmtDayTime, fmtMoney, fmtMonthLong, fmtNum, fmtPct, fmtPctSigned, fmtYear, num, obj, parseTs, stepDigits, str } from '../format.js';
import { RANGES, alertLevel, curveOf, isBacktest, limitStatus, modeKind, modeShort, rangeStart, rebaseBench, riskState, strategyStatus, utilization } from '../model.js';

const TABLE_ROWS = 366;

export function mount(root) {
  const saved = loadPref('range', '1A');
  const ui = { range: RANGES.some((r) => r.id === saved) ? saved : '1A', table: false, log: 'auto' };
  let ctx = null;

  // ---- scheda di testa: NAV, giornata, periodi, drawdown ----
  const hero = h('section', { class: 'card hero span-12', 'aria-label': 'Patrimonio e risultato' });

  // ---- andamento ----
  const range = segmented({
    label: 'Intervallo del grafico',
    options: RANGES.map((r) => ({ value: r.id, label: r.label })),
    value: ui.range,
    onChange: (v) => { ui.range = v; ui.log = 'auto'; savePref('range', v); drawChart(); },
  });
  const logBtn = toggle({ label: 'Scala logaritmica', text: 'Log', onChange: (on) => { ui.log = on ? 'on' : 'off'; drawChart(); } });
  const tableBtn = toggle({ label: 'Mostra i dati in tabella', iconName: 'table', onChange: (on) => { ui.table = on; drawChart(); } });
  const chartCard = card({
    title: 'Andamento del patrimonio', actions: [range.el, logBtn.el, tableBtn.el], cls: 'chart-card order-1',
    what: 'La linea blu è il valore del conto giorno per giorno; quella grigia è il benchmark, cioè che cosa avrebbe fatto la stessa somma in un investimento di confronto. Sotto, in rosso, il drawdown: quanto il conto è sceso dal suo massimo. Passa il dito o il mouse sul grafico per leggere i valori di un giorno.',
    method: 'Benchmark riportato al valore del fondo nel primo giorno dell\'intervallo (un solo asse). Drawdown calcolato sul massimo della curva disponibile. Scala logaritmica automatica se il rapporto massimo/minimo supera 3.',
  });
  const legend = h('div', { class: 'legend' });
  const chartHost = h('div', { class: 'chart-host' });
  const tableHost = h('div', { class: 'chart-table' });
  const chartEmpty = h('div', { class: 'chart-empty' });
  chartCard.body.append(legend, chartHost, tableHost, chartEmpty);
  const chart = timeChart(chartHost, { label: 'Andamento del patrimonio rispetto al benchmark, con il drawdown sotto. Frecce sinistra e destra per scorrere i giorni.' });
  const curveTable = dataTable({
    caption: 'Patrimonio, benchmark e drawdown per giorno',
    cls: 'table--dense',
    columns: [
      { key: 't', label: 'Data', cell: (r) => fmtDate(r.t, true) },
      { key: 'eq', label: 'Patrimonio', num: true, cell: (r) => fmtMoney(r.eq, ctx.ccy) },
      { key: 'ret', label: 'Da inizio periodo', num: true, cell: (r) => signedPct(r.ret, 2, { arrow: false }) },
      { key: 'bench', label: 'Benchmark', num: true, cell: (r) => (r.bench == null ? null : signedPct(r.bench, 2, { arrow: false })) },
      { key: 'dd', label: 'Drawdown', num: true, cell: (r) => fmtPct(r.dd, 2) },
    ],
  });
  tableHost.append(curveTable.el);

  // ---- rischio e avvisi ----
  const riskCard = card({ title: 'Rischio', actions: more('#/rischio', 'Dettaglio'), cls: 'risk-card', what: 'Lo stato del motore di rischio e i limiti più vicini alla loro soglia. Ogni barra mostra quanta parte del limite è già usata: sotto l\'80% è tranquillo, tra 80% e 100% è da tenere d\'occhio, oltre il 100% il limite è superato e il motore interviene.' });
  const alertsCard = card({ title: 'Avvisi recenti', actions: more('#/sistema', 'Registro'), cls: 'alerts-card' });
  const side = h('div', { class: 'span-4 stack order-2' }, riskCard.el, alertsCard.el);

  // ---- strategie ----
  const stratCard = card({ title: 'Strategie', actions: more('#/strategie', 'Schede complete'), cls: 'order-3', flush: true, what: 'Le quattro strategie del fondo. «Allocazione» è la quota di patrimonio assegnata a ciascuna; «Oggi» e «Mese» sono il suo guadagno o la sua perdita nel periodo; la linea a destra è l\'andamento recente.' });
  const miniCard = card({ title: 'Ultimi 30 giorni e ultimi 12 mesi', cls: 'order-3 only-esperto', method: 'Rendimenti giornalieri ricavati dalla curva del patrimonio; rendimenti mensili dallo snapshot. Nessun dato intraday: lo snapshot non lo contiene.' });
  const miniDays = h('div', { class: 'mini-chart' });
  const miniMonths = h('div', { class: 'mini-chart' });
  const miniStats = h('div', { class: 'pairs pairs--row' });
  miniCard.body.append(h('div', { class: 'mini-charts' }, h('div', null, h('h3', { class: 'subhead', text: 'Rendimento giornaliero' }), miniDays), h('div', null, h('h3', { class: 'subhead', text: 'Rendimento mensile' }), miniMonths)), miniStats);
  let miniKey = null;
  const stratTable = dataTable({
    caption: 'Strategie: stato, allocazione e risultato',
    sort: { key: 'alloc', dir: -1 },
    emptyTitle: 'Nessuna strategia nello snapshot',
    columns: [
      { key: 'id', label: 'Strategia', sort: (r) => str(r.id), cell: (r) => h('div', { class: 'cell-id cell-id--stack-sm' }, h('span', { class: 'code', text: str(r.id) || DASH }), h('span', { class: 'cell-id__name', text: str(r.name) })) },
      { key: 'status', label: 'Stato', sort: (r) => str(r.status), cell: (r) => chip(strategyStatus(r.status), { compact: true }) },
      { key: 'alloc', label: 'Allocazione', num: true, hide: 'sm', sort: (r) => num(r.allocation), cell: (r) => fmtPct(r.allocation, 1) },
      { key: 'day', label: 'Oggi', num: true, sort: (r) => num(r.pnl_day_pct), cell: (r) => signedPct(r.pnl_day_pct) },
      { key: 'mtd', label: 'Mese', num: true, hide: 'sm', sort: (r) => num(r.pnl_mtd_pct), cell: (r) => signedPct(r.pnl_mtd_pct) },
      { key: 'spark', label: 'Andamento', hide: 'md', cls: 'is-spark', cell: (r) => sparkline(r.spark, { width: 104, height: 28, label: `Andamento di ${str(r.id)}` }) },
    ],
  });
  stratCard.body.append(stratTable.el);

  root.append(h('div', { class: 'grid' }, hero, h('div', { class: 'col span-8' }, chartCard.el, stratCard.el, miniCard.el), side));

  // ---------------------------------------------------------------------------------------------------------------

  function fillHero() {
    const { snap, ccy } = ctx;
    const nav = obj(snap.nav);
    const meta = obj(snap.meta);
    const curve = curveOf(snap);
    const lastDay = curve.t.length ? curve.t[curve.t.length - 1] : parseTs(meta.as_of);
    const eq = num(nav.equity);
    const cash = num(nav.cash);
    fill(hero,
      h('div', { class: 'hero__main' },
        h('div', { class: 'hero__label' },
          h('span', { text: 'Patrimonio netto (NAV)' }),
          h('span', { class: `tag tag--${modeKind(meta)}`, text: modeShort(meta) })),
        h('div', { class: 'hero__value num', text: fmtMoney(eq, ccy) }),
        h('div', { class: 'hero__day' },
          signedMoney(nav.pnl_day, ccy, { cls: 'hero__day-amount' }),
          signedPct(nav.pnl_day_pct, 2, { arrow: false, cls: 'hero__day-pct' }),
          h('span', { class: 'hero__day-label', text: isBacktest(meta) ? 'ultimo giorno' : 'oggi' })),
        explain('Il valore di tutto il conto: liquidità più posizioni. Sotto, quanto ha guadagnato o perso oggi.', 'hero__explain')),
      h('div', { class: 'hero__stats' },
        stat({ label: 'Da inizio mese', value: signedPct(nav.pnl_mtd_pct), sub: lastDay == null ? 'MTD' : fmtMonthLong(lastDay, true), explain: 'Guadagno o perdita dal primo giorno del mese.' }),
        stat({ label: 'Da inizio anno', value: signedPct(nav.pnl_ytd_pct), sub: lastDay == null ? 'YTD' : `anno ${fmtYear(lastDay, true)}`, explain: 'Guadagno o perdita dal primo gennaio.' }),
        stat({ label: "Dall'avvio", value: signedPct(nav.pnl_total_pct), sub: num(nav.start_equity) == null ? null : `da ${fmtMoney(nav.start_equity, ccy, { digits: 0 })}`, explain: 'Risultato complessivo da quando il conto è partito.' }),
        stat({
          label: 'Drawdown dal massimo', value: fmtPct(nav.drawdown_pct, 2),
          sub: num(nav.high_water) == null ? null : `massimo ${fmtMoney(nav.high_water, ccy, { digits: 0 })}`,
          hint: 'Distanza del patrimonio dal suo massimo storico (high-water mark)',
          explain: 'Quanto siamo sotto il punto più alto mai raggiunto: il drawdown. Zero è il meglio; se scende troppo il motore riduce il rischio.',
        }),
        stat({
          label: 'Liquidità', value: fmtMoney(cash, ccy, { digits: 0 }),
          sub: cash != null && eq ? `${fmtPct(cash / eq, 1)} del patrimonio` : null,
          explain: 'Denaro non investito. Con la leva può essere vicino a zero: è normale.',
        })));
  }

  function drawChart() {
    if (!ctx) return;
    const { snap, ccy } = ctx;
    const c = curveOf(snap);
    const has = c.t.length >= 2;
    chartEmpty.hidden = has;
    legend.hidden = !has;
    chartHost.hidden = !has || ui.table;
    tableHost.hidden = !has || !ui.table;
    range.el.hidden = !has;
    logBtn.el.hidden = !has;
    tableBtn.el.hidden = !has;
    if (!has) {
      chartCard.setSub('');
      fill(chartEmpty, empty('Storico non ancora disponibile', 'La curva compare dopo i primi due giorni di dati.'));
      chart.update(null);
      return;
    }
    const i0 = rangeStart(c, ui.range);
    const x = c.t.slice(i0);
    const eq = c.equity.slice(i0);
    const dd = c.dd.slice(i0);
    const bench = rebaseBench(c, i0);
    const n = x.length;
    const hasBench = bench.some((v) => v != null);
    let lo = Infinity;
    let hi = -Infinity;
    let worst = 0;
    for (let i = 0; i < n; i++) {
      if (eq[i] < lo) lo = eq[i];
      if (eq[i] > hi) hi = eq[i];
      if (dd[i] < worst) worst = dd[i];
    }
    const useLog = ui.log === 'on' || (ui.log === 'auto' && lo > 0 && hi / lo >= 3);
    logBtn.set(useLog);
    const first = eq[0];
    const benchFirst = bench.find((v) => v != null);
    const benchLast = hasBench ? [...bench].reverse().find((v) => v != null) : null;
    const retOf = (v) => (first ? v / first - 1 : null);
    const benchRet = (v) => (v == null || !benchFirst ? null : v / benchFirst - 1);

    chartCard.setSub(`${fmtDate(x[0], true)} – ${fmtDate(x[n - 1], true)}${hasBench ? ' · benchmark riportato al valore del fondo a inizio periodo' : ''}${useLog ? ' · scala logaritmica' : ''}`);
    fill(legend,
      h('span', { class: 'legend__item' }, h('span', { class: 'key key--fund', 'aria-hidden': 'true' }), h('span', { text: str(obj(snap.meta).fund) || 'Fondo' }), signedPct(retOf(eq[n - 1]), 2, { arrow: false })),
      hasBench ? h('span', { class: 'legend__item' }, h('span', { class: 'key key--bench', 'aria-hidden': 'true' }), h('span', { text: 'Benchmark' }), signedPct(benchRet(benchLast), 2, { arrow: false })) : null,
      h('span', { class: 'legend__item legend__item--end' }, h('span', { class: 'key key--dd', 'aria-hidden': 'true' }), h('span', { text: 'Drawdown peggiore' }), h('span', { class: 'num', text: fmtPct(worst, 2) })));

    if (ui.table) {
      const rows = [];
      for (let i = n - 1; i >= Math.max(0, n - TABLE_ROWS); i--) rows.push({ t: x[i], eq: eq[i], ret: retOf(eq[i]), bench: benchRet(bench[i]), dd: dd[i] });
      curveTable.render(rows);
      tableHost.dataset.note = n > TABLE_ROWS ? `Ultimi ${TABLE_ROWS} giorni dell'intervallo` : '';
      return;
    }
    const narrow = (root.clientWidth || 800) < 560;
    chart.update({
      x,
      panels: [
        {
          height: narrow ? 190 : 250,
          scale: useLog ? 'log' : 'linear',
          format: fmtAxisAmount,
          series: [
            { values: bench, cls: 'bench' },
            { values: eq, cls: 'fund', area: true, end: true },
          ],
        },
        { height: narrow ? 56 : 68, title: 'Drawdown dal massimo', top: 0, format: (v, step) => fmtPct(v, stepDigits((step ?? 1) * 100, 2)), series: [{ values: dd, cls: 'dd', area: true }] },
      ],
      tip: (i) => ({
        title: fmtDate(x[i], true),
        rows: [
          { key: 'fund', label: 'Patrimonio', value: fmtMoney(eq[i], ccy) },
          { key: 'fund', label: 'Da inizio periodo', value: fmtPctSigned(retOf(eq[i]), 2) },
          bench[i] == null ? null : { key: 'bench', label: 'Benchmark', value: fmtPctSigned(benchRet(bench[i]), 2) },
          { key: 'dd', label: 'Drawdown', value: fmtPct(dd[i], 2) },
        ].filter(Boolean),
      }),
      say: (i) => `${fmtDate(x[i], true)}: patrimonio ${fmtMoney(eq[i], ccy)}, ${fmtPctSigned(retOf(eq[i]), 2)} da inizio periodo, drawdown ${fmtPct(dd[i], 2)}`,
    });
  }

  function fillRisk() {
    const { snap } = ctx;
    const risk = obj(snap.risk);
    const st = riskState(risk);
    const limits = arr(risk.limits)
      .map((l) => ({ l, u: utilization(l.value, l.limit) }))
      .filter((x) => x.u != null)
      .sort((a, b) => b.u - a.u)
      .slice(0, 3);
    const varPct = num(risk.var_95_1d_pct);
    fill(riskCard.body,
      h('div', { class: 'riskbox' },
        h('span', { class: `pill pill--lg pill--${st.kind}` }, icon(st.icon), h('span', { text: st.label })),
        h('p', { class: 'riskbox__reason', text: str(risk.state_reason) || st.text || 'Stato del rischio non presente nello snapshot.' }),
        st.light ? explain(`${st.light}: ${st.text.charAt(0).toLowerCase()}${st.text.slice(1)}`) : null),
      limits.length
        ? h('div', { class: 'meters' },
          h('div', { class: 'meters__head', text: 'Limiti più vicini alla soglia' }),
          limits.map(({ l, u }) => {
            const info = limitStatus(l.status);
            return h('div', { class: 'meter' },
              h('span', { class: 'meter__name', text: str(l.name) || DASH }),
              bullet({ ratio: u, kind: info.kind, label: `Utilizzo del limite ${str(l.name)}`, text: `${fmtPct(u, 0)} della soglia` }),
              h('span', { class: `meter__value num meter__value--${info.kind}` }, info.kind === 'ok' ? null : icon(info.icon), fmtPct(u, 0)));
          }))
        : null,
      h('div', { class: 'pairs' },
        pair('VaR 95% a 1 giorno', varPct == null ? null : fmtPct(Math.abs(varPct), 2)),
        pair('Volatilità 30g / obiettivo', num(risk.vol_realized_30d) == null && num(risk.vol_target) == null ? null : `${fmtPct(risk.vol_realized_30d, 1)} / ${fmtPct(risk.vol_target, 1)}`)),
      explain('VaR: la perdita di giornata che si supera solo un giorno su venti. Volatilità: quanto oscilla il conto, confrontata con l\'obiettivo che il fondo si è dato.'));
  }

  function fillMini() {
    const c = curveOf(ctx.snap);
    const months = arr(ctx.snap.monthly_returns).filter((m) => num(m.ret) != null).slice(-12);
    const key = `${c.t.length}|${c.equity[c.equity.length - 1]}|${months.length}|${months.length ? months[months.length - 1].ret : ''}`;
    if (key === miniKey) return;
    miniKey = key;
    const n = c.t.length;
    const k = Math.min(30, n - 1);
    const days = [];
    const dayLabels = [];
    for (let i = n - k; i < n && i > 0; i++) {
      days.push(c.equity[i - 1] > 0 ? c.equity[i] / c.equity[i - 1] - 1 : null);
      dayLabels.push(fmtDate(c.t[i], true));
    }
    if (!columns(miniDays, days, { labels: dayLabels, label: 'Rendimenti giornalieri degli ultimi 30 giorni' })) fill(miniDays, h('p', { class: 'muted', text: 'Servono almeno tre giorni di storico.' }));
    if (!columns(miniMonths, months.map((m) => num(m.ret)), { labels: months.map((m) => str(m.ym)), label: 'Rendimenti degli ultimi 12 mesi' })) fill(miniMonths, h('p', { class: 'muted', text: 'Servono almeno due mesi chiusi.' }));
    const valid = days.filter((v) => v != null);
    const mean = valid.length ? valid.reduce((a, b) => a + b, 0) / valid.length : null;
    const sd = valid.length > 2 ? Math.sqrt(valid.reduce((a, b) => a + (b - mean) ** 2, 0) / (valid.length - 1)) : null;
    fill(miniStats,
      pair('Giorno migliore', valid.length ? fmtPctSigned(Math.max(...valid), 2) : null), pair('Giorno peggiore', valid.length ? fmtPctSigned(Math.min(...valid), 2) : null),
      pair('Giorni positivi', valid.length ? `${valid.filter((v) => v > 0).length} su ${valid.length}` : null),
      pair('Dev. standard giornaliera', sd == null ? null : `${fmtPct(sd, 2)} (± ${fmtNum(sd / Math.sqrt(2 * (valid.length - 1)) * 100, 2)} pt)`));
  }

  function fillAlerts() {
    const { snap, now } = ctx;
    const all = arr(snap.alerts).map((a) => ({ a, t: parseTs(a.t) })).sort((p, q) => (q.t ?? -Infinity) - (p.t ?? -Infinity));
    if (!all.length) {
      fill(alertsCard.body, empty('Nessun avviso', 'Il motore non ha segnalato nulla.'));
      return;
    }
    fill(alertsCard.body,
      h('ul', { class: 'alerts' }, all.slice(0, 4).map(({ a, t }) => {
        const lv = alertLevel(a.level);
        return h('li', { class: `alert alert--${lv.kind}` },
          icon(lv.icon, 'alert__icon'),
          h('div', { class: 'alert__body' },
            h('p', { class: 'alert__msg' }, h('span', { class: 'sr-only', text: `${lv.label}: ` }), str(a.msg) || DASH),
            h('span', { class: 'alert__time num', title: t == null ? null : fmtDayTime(t), text: t == null ? DASH : fmtAge(a.t, now) })));
      })),
      all.length > 4 ? h('p', { class: 'card__foot', text: `Altri ${all.length - 4} nel registro degli avvisi.` }) : null);
  }

  return {
    update(next) {
      ctx = next;
      fillHero();
      drawChart();
      fillRisk();
      fillAlerts();
      stratTable.render(arr(ctx.snap.strategies));
      fillMini();
    },
    summary(c) {
      const nav = obj(c.snap.nav);
      const risk = obj(c.snap.risk);
      const st = riskState(risk);
      const eq = num(nav.equity);
      if (eq == null) return 'Lo snapshot non riporta il valore del conto.';
      const day = num(nav.pnl_day);
      const word = isBacktest(c.snap.meta) ? "Nell'ultimo giorno simulato" : 'Oggi';
      const moved = day == null ? '' : day > 0 ? `, ha guadagnato ${fmtMoney(day, c.ccy, { digits: 0 })}` : day < 0 ? `, ha perso ${fmtMoney(Math.abs(day), c.ccy, { digits: 0 })}` : ', è fermo rispetto a ieri';
      const statuses = arr(risk.limits).map((l) => str(l.status).toLowerCase());
      const riskLine = st.code && st.code !== 'NORMAL' ? `il motore di rischio è nello stato «${st.label}»`
        : statuses.includes('breach') ? 'ha superato almeno un limite di rischio'
          : statuses.includes('warn') ? 'è vicino a un limite di rischio ma dentro il consentito' : 'sta rischiando meno del consentito';
      return `${word} il fondo vale ${fmtMoney(eq, c.ccy, { digits: 0 })}${moved}; ${riskLine}.`;
    },
  };
}
