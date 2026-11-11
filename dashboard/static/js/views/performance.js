// Performance: metriche del periodo, rendimenti mensili, statistiche mobili calcolate dalla curva.

import { h, fill } from '../dom.js';
import { card, empty, pair, signedPct, stat } from '../components.js';
import { heatmap, timeChart } from '../charts.js';
import { fmtDate, fmtNum, fmtPct, num, obj, stepDigits } from '../format.js';
import { curveOf, monthlyGrid, periodsPerYear, rolling } from '../model.js';

export function mount(root) {
  let ctx = null;
  let heatKey = null;

  const tiles = h('section', { class: 'card tiles span-12', 'aria-label': 'Metriche di performance' });
  const heatCard = card({ title: 'Rendimenti mensili', sub: 'In percentuale. Il totale è il rendimento composto dell\'anno.', cls: 'span-12' });
  const heatHost = h('div', { class: 'heat-host' });
  heatCard.body.append(heatHost);

  const volCard = card({ title: 'Volatilità mobile', cls: 'span-6' });
  const volHost = h('div', { class: 'chart-host' });
  const volEmpty = h('div');
  volCard.body.append(volHost, volEmpty);
  const volChart = timeChart(volHost, { label: 'Volatilità annualizzata su finestra mobile. Frecce sinistra e destra per scorrere i giorni.' });

  const shCard = card({ title: 'Sharpe mobile', cls: 'span-6' });
  const shHost = h('div', { class: 'chart-host' });
  const shEmpty = h('div');
  shCard.body.append(shHost, shEmpty);
  const shChart = timeChart(shHost, { label: 'Indice di Sharpe su finestra mobile. Frecce sinistra e destra per scorrere i giorni.' });

  root.append(h('div', { class: 'grid' }, tiles, heatCard.el, volCard.el, shCard.el));

  function fillTiles() {
    const p = obj(ctx.snap.performance);
    const nav = obj(ctx.snap.nav);
    const ratio = (v) => (num(v) == null ? null : fmtNum(v, 2));
    fill(tiles,
      h('div', { class: 'tiles__grid' },
        stat({ label: 'Rendimento annuo (CAGR)', value: signedPct(p.cagr, 2, { arrow: false }), sub: 'composto, al netto dei costi' }),
        stat({ label: 'Volatilità', value: num(p.vol) == null ? null : fmtPct(p.vol, 1), sub: 'annualizzata' }),
        stat({ label: 'Sharpe', value: ratio(p.sharpe), sub: 'rendimento per unità di rischio' }),
        stat({ label: 'Sortino', value: ratio(p.sortino), sub: 'conta solo il rischio al ribasso' }),
        stat({ label: 'Calmar', value: ratio(p.calmar), sub: 'CAGR / drawdown massimo' }),
        stat({ label: 'PSR', value: num(p.psr) == null ? null : fmtPct(p.psr, 1), sub: 'probabilità che lo Sharpe vero sia > 0' }),
        stat({ label: 'Mese migliore', value: signedPct(p.best_month, 2, { arrow: false }) }),
        stat({ label: 'Mese peggiore', value: signedPct(p.worst_month, 2, { arrow: false }) })),
      h('div', { class: 'tiles__foot pairs pairs--row' },
        pair('Giorni positivi', num(p.hit_rate_days) == null ? null : fmtPct(p.hit_rate_days, 1)),
        pair('Giorni di storico', num(p.days) == null ? null : fmtNum(p.days, 0)),
        pair('Drawdown massimo', num(nav.max_drawdown_pct) == null ? null : fmtPct(nav.max_drawdown_pct, 2))));
  }

  function fillHeat() {
    const raw = ctx.snap.monthly_returns;
    const key = JSON.stringify(raw ?? null);
    if (key === heatKey) return;                      // stessi dati: si conservano scorrimento e tooltip
    heatKey = key;
    const grid = monthlyGrid(ctx.snap);
    if (!grid.years.length) {
      fill(heatHost, empty('Nessun rendimento mensile', 'La tabella si riempie alla chiusura del primo mese.'));
      return;
    }
    fill(heatHost);
    heatmap(heatHost, grid);
  }

  function rollingChart(chart, host, emptyEl, cardRef, { values, win, months, format, digits, refs, what, t }) {
    let i0 = values.findIndex((v) => v != null);
    const ok = i0 >= 0 && values.length - i0 >= 2;
    host.hidden = !ok;
    emptyEl.hidden = ok;
    cardRef.setSub(`Finestra di ${months} mesi (${win} osservazioni), annualizzata`);
    if (!ok) {
      fill(emptyEl, empty('Storico insufficiente', `Servono almeno ${win + 1} giorni di dati.`));
      chart.update(null);
      return;
    }
    i0 = Math.max(0, i0);
    const x = t.slice(i0);
    const y = values.slice(i0);
    chart.update({
      x,
      panels: [{ height: 170, format, refs, series: [{ values: y, cls: 'fund', end: true }] }],
      tip: (i) => ({ title: fmtDate(x[i], true), rows: [{ key: 'fund', label: what, value: digits(y[i]) }] }),
      say: (i) => `${fmtDate(x[i], true)}: ${what} ${digits(y[i])}`,
    });
  }

  function fillRolling() {
    const c = curveOf(ctx.snap);
    const ppy = periodsPerYear(c);
    const w3 = Math.max(20, Math.round(ppy / 4));
    const w6 = Math.max(40, Math.round(ppy / 2));
    const target = num(obj(ctx.snap.risk).vol_target);
    rollingChart(volChart, volHost, volEmpty, volCard, {
      values: rolling(c, w3).vol, win: w3, months: 3, t: c.t, what: 'Volatilità',
      format: (v, step) => fmtPct(v, stepDigits((step ?? 1) * 100, 2)), digits: (v) => fmtPct(v, 1),
      refs: target == null ? [] : [{ value: target, label: `obiettivo ${fmtPct(target, 0)}` }],
    });
    rollingChart(shChart, shHost, shEmpty, shCard, {
      values: rolling(c, w6).sharpe, win: w6, months: 6, t: c.t, what: 'Sharpe',
      format: (v, step) => fmtNum(v, Math.max(1, stepDigits(step, 3))), digits: (v) => fmtNum(v, 2),
      refs: [{ value: 0, label: '' }],
    });
  }

  return {
    update(next) {
      ctx = next;
      fillTiles();
      fillHeat();
      fillRolling();
    },
  };
}
