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
  const heatCard = card({ title: 'Rendimenti mensili', sub: 'In percentuale. Il totale è il rendimento composto dell\'anno.', cls: 'span-12', what: 'Ogni casella è il risultato di un mese: verde se ha guadagnato, rosso se ha perso, più intenso quanto più grande è il numero. L\'ultima colonna è il risultato dell\'intero anno.', method: 'Rendimenti mensili composti dai rendimenti giornalieri; intensità del colore proporzionale al valore assoluto, saturata al 92° percentile.' });
  const heatHost = h('div', { class: 'heat-host' });
  heatCard.body.append(heatHost);

  const volCard = card({ title: 'Volatilità mobile', cls: 'span-6', what: 'Quanto ha oscillato il conto negli ultimi tre mesi, ricalcolato ogni giorno. La linea tratteggiata è l\'obiettivo che il fondo si è dato: sopra, il conto si sta muovendo più del previsto.', method: 'Deviazione standard dei rendimenti giornalieri sulla finestra, annualizzata con i giorni per anno dedotti dalle date.' });
  const volHost = h('div', { class: 'chart-host' });
  const volEmpty = h('div');
  volCard.body.append(volHost, volEmpty);
  const volChart = timeChart(volHost, { label: 'Volatilità annualizzata su finestra mobile. Frecce sinistra e destra per scorrere i giorni.' });

  const shCard = card({ title: 'Sharpe mobile', cls: 'span-6', what: 'Lo Sharpe calcolato solo sugli ultimi sei mesi. Sopra la linea dello zero il semestre è stato positivo. È normale che salga e scenda molto: su periodi brevi è una misura rumorosa.', method: 'Media / deviazione standard dei rendimenti giornalieri sulla finestra, annualizzata; tasso senza rischio non sottratto.' });
  const shHost = h('div', { class: 'chart-host' });
  const shEmpty = h('div');
  shCard.body.append(shHost, shEmpty);
  const shChart = timeChart(shHost, { label: 'Indice di Sharpe su finestra mobile. Frecce sinistra e destra per scorrere i giorni.' });

  root.append(h('div', { class: 'grid' }, tiles, heatCard.el, volCard.el, shCard.el));

  function fillTiles() {
    const p = obj(ctx.snap.performance);
    const nav = obj(ctx.snap.nav);
    const ratio = (v) => (num(v) == null ? null : fmtNum(v, 2));
    const years = num(p.days) ? num(p.days) / 365 : null;
    const se = num(p.sharpe) != null && years ? Math.sqrt((1 + num(p.sharpe) ** 2 / 2) / years) : null;
    fill(tiles,
      h('div', { class: 'tiles__grid' },
        stat({ label: 'Rendimento annuo (CAGR)', value: signedPct(p.cagr, 2, { arrow: false }), sub: 'composto, al netto dei costi', explain: 'Di quanto è cresciuto il conto in media ogni anno. Più alto è meglio.' }),
        stat({ label: 'Volatilità', value: num(p.vol) == null ? null : fmtPct(p.vol, 1), sub: 'annualizzata', explain: 'Quanto oscilla il valore del conto in un anno. Più bassa vuol dire un percorso più tranquillo.' }),
        stat({ label: 'Sharpe', value: ratio(p.sharpe), sub: se == null ? 'rendimento per unità di rischio' : [h('span', { class: 'only-semplice', text: 'rendimento per unità di rischio' }), h('span', { class: 'only-esperto num', text: `± ${fmtNum(se, 2)} errore standard` })], explain: 'Quanto rende ogni unità di rischio. Intorno a 1 è buono; sotto 0,5 è debole.' }),
        stat({ label: 'Sortino', value: ratio(p.sortino), sub: 'conta solo il rischio al ribasso', explain: 'Come lo Sharpe, ma considera «rischio» solo le oscillazioni in perdita. Più alto è meglio.' }),
        stat({ label: 'Calmar', value: ratio(p.calmar), sub: 'CAGR / drawdown massimo', explain: 'Rendimento annuo diviso per la caduta peggiore. Sopra 1: in un anno medio si recupera la caduta peggiore.' }),
        stat({ label: 'PSR', value: num(p.psr) == null ? null : fmtPct(p.psr, 1), sub: 'probabilità che lo Sharpe vero sia > 0', explain: 'Quanto è probabile che il risultato non sia solo fortuna. Sopra il 95% è un buon segno.' }),
        stat({ label: 'Mese migliore', value: signedPct(p.best_month, 2, { arrow: false }), explain: 'Il mese più favorevole della storia del conto.' }),
        stat({ label: 'Mese peggiore', value: signedPct(p.worst_month, 2, { arrow: false }), explain: 'Il mese più difficile: dà un\'idea di che cosa può succedere in un mese storto.' })),
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
    summary(c) {
      const p = obj(c.snap.performance);
      if (num(p.cagr) == null) return 'Lo storico è ancora troppo corto per calcolare le metriche di performance.';
      const sh = num(p.sharpe);
      const word = sh == null ? '' : sh < 0 ? 'negativo' : sh < 0.5 ? 'debole' : sh < 1 ? 'discreto' : sh < 2 ? 'buono' : 'molto alto';
      return `In ${fmtNum(p.days, 0)} giorni il fondo ha reso in media il ${fmtPct(p.cagr, 1)} l'anno, con oscillazioni del ${fmtPct(p.vol, 0)} l'anno${sh == null ? '' : `; il rapporto tra rendimento e rischio (Sharpe ${fmtNum(sh, 2)}) è ${word}`}.`;
    },
  };
}
