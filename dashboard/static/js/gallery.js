// Galleria tecnica (grafici.html): ogni primitiva del motore dei grafici con i dati di esempio del server.
// Serve a chi disegna lo stile (basta cambiare i token --chart-*) e alle verifiche automatiche; non è una pagina del prodotto.

import { candleChart, OVERLAYS } from './candles.js';
import { fanChart, heatGrid, linkCharts, scatter, stackedArea, treemap, underwater, waterfall } from './chart-engine.js';
import { histogram, timeChart } from './charts.js';
import { card } from './components.js';
import { h, savePref } from './dom.js';
import { fmtDate, fmtNum, fmtPct, fmtPctSigned, fmtSigned } from './format.js';
import { getCompare, getOhlc, getTrades } from './market.js';

const body = document.getElementById('gallery-body');
document.body.dataset.ready = 'no';

document.getElementById('gallery-theme').addEventListener('click', () => {
  const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
  document.documentElement.dataset.theme = next;
  savePref('theme', next);
});

const seg = (items, onPick, initial) => {
  const el = h('div', { class: 'seg', role: 'group' });
  for (const it of items) {
    const btn = h('button', { class: 'seg__btn', type: 'button', 'aria-pressed': String(it.id === initial), text: it.label });
    btn.addEventListener('click', () => {
      for (const b of el.children) b.setAttribute('aria-pressed', String(b === btn));
      onPick(it.id);
    });
    el.append(btn);
  }
  return el;
};

function section(title, sub, api, span = 6) {
  const c = card({ title, sub, sim: 'ESEMPIO' });
  c.el.classList.add(`span-${span}`);
  const hostEl = h('div', { class: 'chart-host' });
  c.body.append(hostEl, h('p', { class: 'gallery__api', text: api }));
  return { el: c.el, host: hostEl, card: c };
}

/** Generatore deterministico (i percentili del ventaglio non cambiano tra un caricamento e l'altro). */
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const quantile = (sorted, q) => {
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  return sorted[lo] + (sorted[Math.min(sorted.length - 1, lo + 1)] - sorted[lo]) * (pos - lo);
};

async function main() {
  const [btc, trades, compare] = await Promise.all([getOhlc('BTC', 1500), getTrades(), getCompare()]);
  const grid = h('div', { class: 'grid' });
  body.replaceChildren(grid);
  const rows = trades && Array.isArray(trades.rows) ? trades.rows.filter((r) => typeof r.R === 'number') : [];

  // ---- candele + pannelli legati --------------------------------------------------------------------------------------------
  if (btc) {
    const sec = section('Candele con volume e pannelli', 'BTC giornaliero · rotella = zoom, trascina = scorri, doppio clic = tutto, tastiera ←/→ + − Inizio Fine', 'candleChart(host, { label, panes, overlays, table }) · linkCharts([candele, caduta, conviction], { window: true })', 12);
    const candleHost = h('div', { class: 'gallery__candle' });
    const ddHost = h('div', { class: 'chart-host' });
    const cvHost = h('div', { class: 'chart-host' });
    sec.host.append(candleHost, ddHost, cvHost);
    const candles = candleChart(candleHost, { label: 'BTC, candele giornaliere', table: true });
    const active = new Set(['sma50', 'sma200']);
    const toggles = OVERLAYS.map((ov) => {
      const btn = h('button', { class: 'btn btn--sm btn--ghost', type: 'button', 'aria-pressed': String(active.has(ov.id)), text: ov.label });
      btn.addEventListener('click', () => {
        if (active.has(ov.id)) active.delete(ov.id); else active.add(ov.id);
        btn.setAttribute('aria-pressed', String(active.has(ov.id)));
        candles.setOverlays([...active]);
      });
      return btn;
    });
    let isLog = false;
    const logBtn = h('button', { class: 'btn btn--sm btn--ghost', type: 'button', 'aria-pressed': 'false', text: 'Scala log' });
    logBtn.addEventListener('click', () => { isLog = !isLog; logBtn.setAttribute('aria-pressed', String(isLog)); candles.setLog(isLog); });
    sec.card.body.prepend(h('div', { class: 'legend' },
      seg([{ id: 3, label: '3M' }, { id: 6, label: '6M' }, { id: 12, label: '1A' }, { id: 0, label: 'Tutto' }], (m) => candles.setRange(m || null), 6), logBtn, toggles));
    const last = btc.t.length - 1;
    const entry = last - 9;
    candles.setData({ ...btc, markers: [
      { i: entry, price: btc.c[entry], kind: 'entry', label: 'Entrata' },
      { i: entry, price: btc.c[entry] * 0.96, kind: 'level', label: 'Stop', color: 'crit' },
      { i: last - 2, price: btc.c[last - 2], kind: 'exit', label: 'Uscita' },
    ] }, { months: 6 });
    const dd = underwater(ddHost, { label: 'BTC, caduta dal massimo', zoom: true });
    dd.update({ x: btc.t, equity: btc.c, title: 'Caduta dal massimo', height: 90, refs: [{ value: -0.2, label: '−20%' }] });
    const cv = timeChart(cvHost, { label: 'BTC, conviction', zoom: true });
    cv.update({
      x: btc.t,
      panels: [{ height: 70, title: 'Conviction (a gradini)', bottom: 0, top: 1, format: (v) => fmtNum(v, 2), refs: [{ value: 0.6, label: 'alta' }], series: [{ values: btc.conviction || btc.t.map(() => null), cls: 'fund', step: true, name: 'Conviction' }] }],
      tip: (i) => ({ title: fmtDate(btc.t[i], true), rows: [{ key: 'fund', label: 'Conviction', value: btc.conviction && btc.conviction[i] != null ? fmtNum(btc.conviction[i], 2) : '—' }] }),
    });
    linkCharts([candles, dd, cv], { window: true });
    grid.append(sec.el);
  }

  // ---- caduta dal massimo, aree impilate ---------------------------------------------------------------------------------------
  const cmp = compare && Array.isArray(compare.rows) ? compare.rows.filter((r) => r && r.data) : [];
  if (cmp.length > 2) {
    const x = cmp.map((r) => Date.parse(`${r.data}T00:00:00Z`));
    const uw = section('Caduta dal massimo', 'Dal patrimonio totale del confronto di esempio', 'underwater(host, { label, zoom, table }).update({ x, equity | values, refs, height, format })');
    const st = underwater(uw.host, { label: 'Caduta dal massimo del patrimonio', table: true }).update({ x, equity: cmp.map((r) => r.nuovo_totale), refs: [{ value: -0.02, label: 'soglia di esempio −2%' }] });
    uw.card.setSub(`Peggiore ${st ? fmtPctSigned(st.min, 2) : '—'} · oggi ${st ? fmtPctSigned(st.current, 2) : '—'} · ${st ? fmtNum(st.daysUnder, 0) : '—'} giorni sotto il massimo`);
    const sa = section('Aree impilate', 'Libro delle strategie + libro dei trade = patrimonio', 'stackedArea(host, { label, zoom, table }).update({ x, layers: [{ name, values, cls }], normalize, format })');
    let normalize = false;
    const stack = stackedArea(sa.host, { label: 'Composizione del patrimonio', table: true });
    const paint = () => stack.update({
      x, normalize, layers: [{ name: 'Libro delle strategie', values: cmp.map((r) => r.nuovo_libro), cls: 's1' }, { name: 'Libro dei trade', values: cmp.map((r) => r.nuovo_trade), cls: 's2' }],
      format: normalize ? undefined : (v) => fmtNum(v, 0),
    });
    sa.card.body.prepend(h('div', { class: 'legend' }, seg([{ id: 'abs', label: 'Valori' }, { id: 'pct', label: '100%' }], (id) => { normalize = id === 'pct'; paint(); }, 'abs'),
      h('span', { class: 'legend__item' }, h('span', { class: 'key key--s1', 'aria-hidden': 'true' }), 'Strategie'), h('span', { class: 'legend__item' }, h('span', { class: 'key key--s2', 'aria-hidden': 'true' }), 'Trade')));
    paint();
    grid.append(uw.el, sa.el);
  }

  if (rows.length > 10) {
    const R = rows.map((r) => r.R);
    const sorted = [...R].sort((a, b) => a - b);
    const mean = R.reduce((a, b) => a + b, 0) / R.length;
    const symbols = [...new Set(rows.map((r) => r.symbol))];
    const groups = symbols.map((sym, k) => ({ id: sym, label: sym, cls: `s${(k % 5) + 1}` }));

    // ---- istogramma con linee di riferimento ----
    const lo = Math.floor(sorted[0]);
    const hi = Math.ceil(sorted[sorted.length - 1]);
    const bins = 24;
    const edges = Array.from({ length: bins + 1 }, (_, i) => lo + ((hi - lo) * i) / bins);
    const counts = new Array(bins).fill(0);
    for (const v of R) counts[Math.min(bins - 1, Math.floor(((v - lo) / (hi - lo)) * bins))]++;
    const hs = section('Istogramma con linee di riferimento', `${fmtNum(R.length, 0)} trade simulati, esito in multipli del rischio (R)`, 'histogram(host, { edges, counts }, { refs: [{ value, label, cls }], normal, unit, xFormat, rangeFormat, height, log, table })');
    histogram(hs.host, { edges, counts }, {
      label: 'Distribuzione degli esiti in R', unit: 'Trade', xFormat: (v) => `${fmtSigned(v, 0)}R`, rangeFormat: (v) => `${fmtSigned(v, 1)}R`, table: true,
      refs: [{ value: 0, label: 'pari' }, { value: mean, label: `media ${fmtSigned(mean, 2)}R`, cls: 'accent' }, { value: quantile(sorted, 0.5), label: `mediana ${fmtSigned(quantile(sorted, 0.5), 2)}R` }, { value: quantile(sorted, 0.05), label: '5° percentile', cls: 'crit' }],
    });

    // ---- cascata ----
    const bySym = symbols.map((sym) => ({ label: sym, value: rows.filter((r) => r.symbol === sym).reduce((a, r) => a + r.R, 0) }));
    const byExit = [...new Set(rows.map((r) => r.exit_reason || 'altro'))].map((why) => ({ label: `uscita: ${why}`, value: rows.filter((r) => (r.exit_reason || 'altro') === why).reduce((a, r) => a + r.R, 0) }));
    const wf = section('Cascata', 'Da zero al totale, per strumento e poi per motivo di uscita', 'waterfall(host, steps: [{ label, value, total, note }], { label, height, format, levelFormat, orient, valueHead, levelHead, table })');
    const total = bySym.reduce((a, d) => a + d.value, 0);
    waterfall(wf.host, [{ label: 'Inizio', value: 0, total: true }, ...bySym, { label: 'Totale', value: total, total: true }, ...byExit.map((d) => ({ ...d, value: -d.value })), { label: 'Verifica', value: 0, total: true }], {
      label: 'Somma degli esiti in R per strumento', format: (v) => `${fmtSigned(v, 1)}R`, levelFormat: (v) => `${fmtNum(v, 1)}R`, valueHead: 'Contributo', levelHead: 'Somma', table: true,
    });

    // ---- dispersione / bolle ----
    const sc = section('Dispersione e bolle', 'Ultimi 180 trade: indicatore GQ all\'ingresso contro esito; area della bolla = leva; retta di regressione', 'scatter(host, points: [{ x, y, size, group, label, cls }], { groups, fit, diagonal, refsX, refsY, xScale, yScale, showLabels, tip, table, … })');
    const plot = scatter(sc.host, rows.filter((r) => typeof r.gq === 'number').slice(-180).map((r) => ({ x: r.gq, y: r.R, size: r.leverage, group: r.symbol, label: `${r.symbol} ${r.entry_time}` })), {
      label: 'GQ all\'ingresso contro esito in R', xTitle: 'GQ all\'ingresso', yTitle: 'Esito (R)', sizeTitle: 'Leva', sizeFormat: (v) => `${fmtNum(v, 1)}x`, yFormat: (v) => fmtSigned(v, 1), groups, fit: true, table: true,
      refsY: [{ value: 0, label: 'pari' }], refsX: [{ value: 0.5318, label: 'GQ alta' }],
    });
    sc.card.setSub(`${sc.card.el.querySelector('.card__sub').textContent} · r = ${plot.fit && plot.fit.r != null ? fmtSigned(plot.fit.r, 2) : '—'}`);

    // ---- quantile-quantile (diagonale) ----
    const sd = Math.sqrt(R.reduce((a, v) => a + (v - mean) ** 2, 0) / R.length);
    const probit = (p) => {                       // inversa della normale standard (Acklam), sufficiente per un grafico
      const a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716, 2.506628277459239];
      const b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572];
      const c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
      const d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416];
      if (p < 0.02425) { const q = Math.sqrt(-2 * Math.log(p)); return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
      if (p > 1 - 0.02425) return -probit(1 - p);
      const q = p - 0.5;
      const r = q * q;
      return ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q) / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
    };
    const qq = section('Quantile-quantile', 'Esiti osservati contro quelli di una normale con stessa media e deviazione: sopra la diagonale a destra = coda grassa', 'scatter(host, points, { diagonal: true })');
    scatter(qq.host, sorted.map((v, i) => ({ x: mean + sd * probit((i + 0.5) / sorted.length), y: v })), {
      label: 'Grafico quantile-quantile degli esiti', xTitle: 'Atteso se normale (R)', yTitle: 'Osservato (R)', diagonal: true, height: 300, xFormat: (v) => fmtSigned(v, 1), yFormat: (v) => fmtSigned(v, 1),
    });

    // ---- ventaglio ----
    const fan = section('Ventaglio di percentili', '400 riordini casuali degli stessi trade: somma degli esiti lungo la sequenza', 'fanChart(host, { label, zoom, table }).update({ x, bands: [{ lo, hi, name }], median, lines, scale, format, xTicks, xFormat, refs, marks })');
    const rand = rng(20261112);
    const n = Math.min(R.length, 120);
    const paths = Array.from({ length: 400 }, () => { let acc = 0; return Array.from({ length: n }, () => { acc += R[Math.floor(rand() * R.length)]; return acc; }); });
    const q = (p) => Array.from({ length: n }, (_, i) => quantile(paths.map((path) => path[i]).sort((a, b) => a - b), p));
    let acc = 0;
    const xs = Array.from({ length: n }, (_, i) => i + 1);
    fanChart(fan.host, { label: 'Ventaglio della somma degli esiti', table: true }).update({
      x: xs, xHead: 'Trade', xFormat: (t) => `trade n. ${fmtNum(t, 0)}`, xTicks: [1, 20, 40, 60, 80, 100, 120].filter((t) => t <= n).map((t) => ({ t, label: String(t) })),
      bands: [{ lo: q(0.05), hi: q(0.95), name: '5°–95° percentile' }, { lo: q(0.25), hi: q(0.75), name: '25°–75° percentile' }], median: q(0.5),
      lines: [{ values: R.slice(0, n).map((v) => (acc += v)), cls: 's2', name: 'Sequenza storica' }], format: (v) => `${fmtSigned(v, 0)}R`, refs: [{ value: 0, label: 'pari' }],
    });

    // ---- mappa ad albero ----
    const tm = section('Mappa ad albero', 'Numero di trade per strumento; dentro, vinti e persi (intensità = quota)', 'treemap(host, items: [{ name, value, cls, k, note, children }], { label, height, format, valueHead, tip, table })');
    treemap(tm.host, symbols.map((sym) => {
      const mine = rows.filter((r) => r.symbol === sym);
      const won = mine.filter((r) => r.R > 0).length;
      return { name: sym, children: [{ name: 'Vinti', value: won, cls: 'up', k: won / mine.length }, { name: 'Persi', value: mine.length - won, cls: 'down', k: 1 - won / mine.length }] };
    }), { label: 'Trade per strumento ed esito', format: (v) => fmtNum(v, 0), valueHead: 'Trade', height: 280, table: true });

    // ---- griglia di calore ----
    const days = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom'];
    const cell = (sym, wd) => rows.filter((r) => r.symbol === sym && r.weekday === wd);
    const hg = section('Griglia di calore', 'Esito medio in R per strumento e giorno di ingresso (nel tooltip il numero di casi)', 'heatGrid(host, { rows, cols, values, counts }, { caption, corner, format, palette: pnl | corr | seq, scale, tip })');
    heatGrid(hg.host, {
      rows: symbols, cols: days,
      values: symbols.map((sym) => days.map((_, wd) => { const c = cell(sym, wd); return c.length ? c.reduce((a, r) => a + r.R, 0) / c.length : null; })),
      counts: symbols.map((sym) => days.map((_, wd) => cell(sym, wd).length)),
    }, { caption: 'Esito medio in R per strumento e giorno della settimana', corner: 'Strumento', format: (v) => fmtSigned(v, 1) });
    const hq = section('Griglia di calore, una sola tinta', 'Quota di trade vinti per strumento e giorno', 'heatGrid(…, { palette: \'seq\', scale: 1 })');
    heatGrid(hq.host, {
      rows: symbols, cols: days,
      values: symbols.map((sym) => days.map((_, wd) => { const c = cell(sym, wd); return c.length ? c.filter((r) => r.R > 0).length / c.length : null; })),
      counts: symbols.map((sym) => days.map((_, wd) => cell(sym, wd).length)),
    }, { caption: 'Quota di trade vinti', corner: 'Strumento', palette: 'seq', scale: 1, format: (v) => fmtPct(v, 0) });

    grid.append(hs.el, wf.el, sc.el, qq.el, fan.el, tm.el, hg.el, hq.el);
  }

  if (!grid.children.length) body.replaceChildren(h('p', { class: 'placeholder', text: 'Nessun dato di esempio disponibile: la galleria funziona in modalità dimostrativa.' }));
  document.body.dataset.ready = 'yes';
}

main().catch((err) => {
  body.replaceChildren(h('p', { class: 'placeholder', text: `La galleria non si è caricata: ${err && err.message ? err.message : 'errore'}` }));
  document.body.dataset.ready = 'errore';
});
