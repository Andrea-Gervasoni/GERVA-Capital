// Motore dei grafici, seconda parte: le primitive che servono a un terminale e che charts.js non aveva.
//   underwater    caduta dal massimo nel tempo (area sotto lo zero), da una curva del patrimonio o da valori già pronti
//   fanChart      ventaglio di percentili con mediana e linee sovrapposte (Monte Carlo, proiezioni)
//   stackedArea   aree impilate (esposizione per classe, contributi), anche normalizzate a 100%
//   waterfall     cascata: da un totale a un altro passando per le variazioni (attribuzione del P&L)
//   scatter       dispersione / bolle con gruppi attivabili, retta di regressione, diagonale, linee di riferimento
//   treemap       mappa ad albero a uno o due livelli (pesi, esposizioni)
//   heatGrid      griglia di calore righe × colonne qualsiasi (una vera <table>: ogni cella porta il suo numero)
//   linkCharts    lega mirino e finestra visibile di più grafici (timeChart, candleChart e i derivati)
// Solo geometria, scale, ricerca del punto più vicino, tastiera e tabella alternativa: nessun colore, raggio, spessore,
// carattere o tempo è scritto qui. Arrivano dalle classi CSS (token --chart-*) e da chartTheme().

import { chartTheme } from './chart-theme.js';
import { bindTip, divStep, hideTip, linearTicks, logTicks, onResize, showTip, tableFallback, timeChart } from './charts.js';
import { h, s } from './dom.js';
import { DASH, fmtDate, fmtNum, fmtPct, fmtPctSigned, fmtSigned, list, num } from './format.js';

const pct = (v, step) => fmtPct(v, step != null && step < 0.01 ? 1 : 0);
const signCls = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '');
const col = (a) => list(a).map(num);

/** I metodi di sincronizzazione di un timeChart, da riesporre nei grafici che lo avvolgono. */
function linkable(chart) {
  return {
    chart,
    onHover: chart.onHover, setHoverTime: chart.setHoverTime,
    setWindow: chart.setWindow, resetWindow: chart.resetWindow, onWindow: chart.onWindow,
  };
}

// ---- caduta dal massimo -----------------------------------------------------------------------------------------------------------

/** Caduta dal massimo di una serie: per ogni punto valore / massimo raggiunto fin lì − 1 (sempre ≤ 0). */
export function drawdownOf(values) {
  let peak = null;
  return col(values).map((v) => {
    if (v == null) return null;
    if (peak == null || v > peak) peak = v;
    return peak > 0 ? v / peak - 1 : null;
  });
}

/**
 * underwater(host, { label, zoom, table }).update({ x, equity | values, refs, height, format, title })
 *   equity: curva del patrimonio (la caduta si calcola qui) oppure values: cadute già calcolate (frazioni ≤ 0);
 *   refs: [{ value, label }] soglie orizzontali (per esempio gli scalini −20 / −30 / −40%).
 * update() restituisce { min, minIndex, current, daysUnder } oppure null se non c'è nulla da disegnare.
 */
export function underwater(host, opts = {}) {
  const chart = timeChart(host, { label: 'Caduta dal massimo', ...opts });
  return {
    ...linkable(chart),
    update(data) {
      const x = col(data && data.x);
      const dd = data && data.values ? col(data.values) : drawdownOf(data && data.equity);
      if (x.length < 2 || dd.filter((v) => v != null).length < 2) { chart.update(null); return null; }
      let minIndex = -1;
      let lastPeak = -1;
      const under = dd.map((v, i) => { if (v != null && v >= 0) lastPeak = i; return lastPeak < 0 ? null : Math.round((x[i] - x[lastPeak]) / 86400000); });
      dd.forEach((v, i) => { if (v != null && (minIndex < 0 || v < dd[minIndex])) minIndex = i; });
      const format = data.format || pct;
      chart.update({
        x,
        panels: [{ height: data.height || 150, title: data.title || '', top: 0, format, refs: data.refs || [], series: [{ values: dd, cls: 'dd', area: true, end: true, name: 'Caduta dal massimo' }] }],
        tip: (i) => ({ title: fmtDate(x[i], true), rows: [
          { key: 'dd', label: 'Caduta dal massimo', value: dd[i] == null ? DASH : fmtPctSigned(dd[i], 2), cls: dd[i] < 0 ? 'neg' : '' },
          { label: 'Giorni sotto il massimo', value: under[i] == null ? DASH : fmtNum(under[i], 0) }] }),
        say: (i) => `${fmtDate(x[i], true)}: caduta dal massimo ${dd[i] == null ? 'non disponibile' : fmtPctSigned(dd[i], 2)}`,
      });
      const last = dd.length - 1;
      return { min: dd[minIndex], minIndex, current: dd[last], daysUnder: under[last] };
    },
  };
}

// ---- ventaglio di percentili --------------------------------------------------------------------------------------------------------

/**
 * fanChart(host, { label, zoom, table }).update({
 *   x, bands: [{ lo, hi, name }] dalla più larga alla più stretta, median, lines: [{ values, cls, name }],
 *   scale: 'linear' | 'log', format, height, title, refs, marks, xTicks, xFormat, xHead })
 */
export function fanChart(host, opts = {}) {
  const chart = timeChart(host, { label: 'Ventaglio di percentili', ...opts });
  return {
    ...linkable(chart),
    update(data) {
      const x = col(data && data.x);
      const bands = list(data && data.bands).map((b) => ({ lo: col(b.lo), hi: col(b.hi), name: b.name || 'Fascia' }));
      const median = data && data.median ? col(data.median) : null;
      const lines = list(data && data.lines).map((l) => ({ values: col(l.values), cls: l.cls || 's2', name: l.name || 'Serie', end: true }));
      if (x.length < 2 || (!bands.length && !median && !lines.length)) { chart.update(null); return false; }
      const format = data.format || ((v) => fmtNum(v, 2));
      const xFormat = data.xFormat || ((t) => fmtDate(t, true));
      chart.update({
        x, xTicks: data.xTicks, marks: data.marks, xFormat, xHead: data.xHead,
        panels: [{
          height: data.height || 240, title: data.title || '', scale: data.scale || 'linear', format, refs: data.refs || [],
          bands: bands.map((b, i) => ({ lo: b.lo, hi: b.hi, cls: i === bands.length - 1 && bands.length > 1 ? 'fan-inner' : 'fan-outer' })),
          series: [...(median ? [{ values: median, cls: 'fund', end: true, name: 'Mediana' }] : []), ...lines],
        }],
        tip: (i) => ({ title: xFormat(x[i]), rows: [
          ...(median ? [{ key: 'fund', label: 'Mediana', value: median[i] == null ? DASH : format(median[i], null) }] : []),
          ...lines.map((l) => ({ key: l.cls, label: l.name, value: l.values[i] == null ? DASH : format(l.values[i], null) })),
          ...bands.map((b) => ({ label: b.name, value: b.lo[i] == null || b.hi[i] == null ? DASH : `${format(b.lo[i], null)} – ${format(b.hi[i], null)}` }))] }),
        say: (i) => `${xFormat(x[i])}: ${median && median[i] != null ? `mediana ${format(median[i], null)}` : ''}${bands[0] && bands[0].lo[i] != null ? `, ${bands[0].name} da ${format(bands[0].lo[i], null)} a ${format(bands[0].hi[i], null)}` : ''}`,
      });
      return true;
    },
  };
}

// ---- aree impilate ------------------------------------------------------------------------------------------------------------------

/**
 * stackedArea(host, { label, zoom, table }).update({ x, layers: [{ name, values, cls }], normalize, format, height, title })
 *   Gli strati si sommano dal basso nell'ordine dato; normalize: true porta ogni data a 100%.
 *   cls: s1…s5 (colori di serie); i valori negativi o mancanti contano zero.
 */
export function stackedArea(host, opts = {}) {
  const chart = timeChart(host, { label: 'Aree impilate', ...opts });
  return {
    ...linkable(chart),
    update(data) {
      const x = col(data && data.x);
      const layers = list(data && data.layers).map((l, k) => ({ name: l.name || `Serie ${k + 1}`, cls: l.cls || `s${(k % 5) + 1}`, values: col(l.values).map((v) => (v != null && v > 0 ? v : 0)) }));
      if (x.length < 2 || !layers.length) { chart.update(null); return false; }
      const n = x.length;
      const totals = x.map((_, i) => layers.reduce((a, l) => a + (l.values[i] || 0), 0));
      const share = (v, i) => (data.normalize ? (totals[i] > 0 ? v / totals[i] : 0) : v);
      let base = new Array(n).fill(0);
      const bands = layers.map((l) => {
        const top = base.map((b, i) => b + share(l.values[i] || 0, i));
        const band = { lo: base, hi: top, cls: l.cls };
        base = top;
        return band;
      });
      const format = data.format || (data.normalize ? pct : (v) => fmtNum(v, 2));
      chart.update({
        x,
        panels: [{
          height: data.height || 220, title: data.title || '', bottom: 0, top: data.normalize ? 1 : undefined, format, bands,
          series: [{ values: base, cls: 'total', name: 'Totale' }],
        }],
        tip: (i) => ({ title: fmtDate(x[i], true), rows: [
          ...[...layers].reverse().map((l) => ({ key: l.cls, label: l.name, value: format(share(l.values[i] || 0, i), null) })),
          { label: 'Totale', value: data.normalize ? fmtNum(totals[i], 2) : format(totals[i], null) }] }),
        say: (i) => `${fmtDate(x[i], true)}: ${layers.map((l) => `${l.name} ${format(share(l.values[i] || 0, i), null)}`).join(', ')}`,
      });
      return true;
    },
  };
}

// ---- cascata ------------------------------------------------------------------------------------------------------------------------

/**
 * waterfall(host, steps, { label, height, format, levelFormat, orient, valueHead, levelHead, table }) → { update(steps) }
 *   steps: [{ label, value, total, note }] — total: true è una barra da zero (totale iniziale, intermedio o finale),
 *   le altre sono variazioni che partono dal livello raggiunto. orient: 'auto' (in riga quando le colonne
 *   diventano troppo strette), 'v' colonne, 'h' righe.
 */
export function waterfall(host, steps, { label = 'Cascata', height = 240, format = (v) => fmtSigned(v, 2), levelFormat = (v) => fmtNum(v, 2), orient = 'auto', valueHead = 'Variazione', levelHead = 'Livello', table = false } = {}) {
  const svg = s('svg', { class: 'chart chart--static', role: 'img', 'aria-label': label });
  let data = [];
  let last = 0;
  host.replaceChildren(svg);
  if (table) {
    host.append(tableFallback({
      caption: label, head: ['Voce', valueHead, levelHead],
      rows: () => data.map((d) => [d.label, d.total ? null : format(d.value), levelFormat(d.to)]),
    }).el);
  }

  function prepare(raw) {
    let run = 0;
    return list(raw).map((st) => {
      const v = num(st && st.value);
      if (v == null) return null;
      const from = st.total ? 0 : run;
      const to = st.total ? v : run + v;
      run = to;
      return { label: String(st.label ?? ''), value: v, total: !!st.total, from, to, note: st.note || '' };
    }).filter(Boolean);
  }

  const tipOf = (d) => ({
    title: d.label,
    rows: d.total
      ? [{ label: levelHead, value: levelFormat(d.to) }]
      : [{ label: valueHead, value: format(d.value), cls: signCls(d.value) }, { label: 'Da', value: levelFormat(d.from) }, { label: 'A', value: levelFormat(d.to) }],
    note: d.note,
  });

  function draw(width, force = false) {
    const w = Math.floor(width);
    if (w < 80 || (w === last && !force)) return;
    last = w;
    svg.replaceChildren();
    const n = data.length;
    if (!n) { svg.setAttribute('height', 0); return; }
    const T = chartTheme();
    const lo = Math.min(0, ...data.flatMap((d) => [d.from, d.to]));
    const hi = Math.max(0, ...data.flatMap((d) => [d.from, d.to]));
    const pad = (hi - lo) * 0.08 || 1;
    const dom = [lo < 0 ? lo - pad : 0, hi > 0 ? hi + pad : 0];
    const horizontal = orient === 'h' || (orient === 'auto' && (w - 50) / n < 56);
    const bar = (d, i, x, y, bw, bh) => {
      const rect = s('rect', {
        class: `c-wf ${d.total ? 'c-wf--total' : d.value < 0 ? 'c-wf--down' : 'c-wf--up'}`, tabindex: '0',
        x: x.toFixed(1), y: y.toFixed(1), width: Math.max(1, bw).toFixed(1), height: Math.max(1, bh).toFixed(1), rx: Math.max(0, Math.min(T.barRadius, bw / 2, bh / 2)),
        'aria-label': d.total ? `${d.label}: ${levelFormat(d.to)}` : `${d.label}: ${format(d.value)}, da ${levelFormat(d.from)} a ${levelFormat(d.to)}`,
      });
      bindTip(rect, () => tipOf(d));
      return rect;
    };

    if (!horizontal) {
      const left = 1;
      const right = w - 50;
      const top = 20;
      const bottom = top + height;
      const yOf = (v) => bottom - ((v - dom[0]) / (dom[1] - dom[0])) * height;
      const band = (right - left) / n;
      const bw = Math.min(band * 0.64, 72);
      svg.setAttribute('viewBox', `0 0 ${w} ${bottom + 26}`);
      svg.setAttribute('width', w);
      svg.setAttribute('height', bottom + 26);
      for (const v of linearTicks(dom[0], dom[1], 4)) {
        const y = Math.round(yOf(v)) + 0.5;
        svg.append(s('line', { class: v === 0 ? 'c-grid c-grid--zero' : 'c-grid', x1: left, x2: right, y1: y, y2: y }), s('text', { class: 'c-tick', x: right + 8, y: y + 3.5 }, levelFormat(v)));
      }
      const chars = Math.max(3, Math.floor(band / 6.4));
      data.forEach((d, i) => {
        const cx = left + band * (i + 0.5);
        const y0 = yOf(Math.max(d.from, d.to));
        const y1 = yOf(Math.min(d.from, d.to));
        if (i < n - 1) {
          const yy = Math.round(yOf(d.to)) + 0.5;
          svg.append(s('line', { class: 'c-wf-link', x1: (cx + bw / 2).toFixed(1), x2: (cx + band - bw / 2).toFixed(1), y1: yy, y2: yy }));
        }
        svg.append(bar(d, i, cx - bw / 2, y0, bw, y1 - y0));
        if (band >= 46) svg.append(s('text', { class: 'c-val', x: cx.toFixed(1), y: (d.total || d.value >= 0 ? y0 - 5 : y1 + 13).toFixed(1) }, d.total ? levelFormat(d.to) : format(d.value)));
        svg.append(s('text', { class: 'c-cat', x: cx.toFixed(1), y: bottom + 17 }, d.label.length > chars ? `${d.label.slice(0, chars - 1)}…` : d.label));
      });
      svg.append(s('line', { class: 'c-axis', x1: left, x2: right, y1: bottom + 0.5, y2: bottom + 0.5 }));
      return;
    }

    // in riga: una voce per riga, il nome a sinistra e il valore a destra della barra
    const row = 28;
    const labelW = Math.min(150, Math.round(w * 0.36));
    const valueW = 66;
    const left = labelW + 6;
    const right = w - valueW;
    const top = 6;
    const bottom = top + row * n;
    const xOf = (v) => left + ((v - dom[0]) / (dom[1] - dom[0])) * (right - left);
    svg.setAttribute('viewBox', `0 0 ${w} ${bottom + 24}`);
    svg.setAttribute('width', w);
    svg.setAttribute('height', bottom + 24);
    for (const v of linearTicks(dom[0], dom[1], Math.max(2, Math.floor((right - left) / 80)))) {
      const x = Math.round(xOf(v)) + 0.5;
      svg.append(s('line', { class: v === 0 ? 'c-grid c-grid--zero' : 'c-grid', x1: x, x2: x, y1: top, y2: bottom }), s('text', { class: 'c-tick c-tick--x', x, y: bottom + 16 }, levelFormat(v)));
    }
    const chars = Math.max(4, Math.floor(labelW / 6.4));
    data.forEach((d, i) => {
      const cy = top + row * (i + 0.5);
      const x0 = xOf(Math.min(d.from, d.to));
      const x1 = xOf(Math.max(d.from, d.to));
      if (i < n - 1) {
        const xx = Math.round(xOf(d.to)) + 0.5;
        svg.append(s('line', { class: 'c-wf-link', x1: xx, x2: xx, y1: (cy + 8).toFixed(1), y2: (cy + row - 8).toFixed(1) }));
      }
      svg.append(bar(d, i, x0, cy - 8, x1 - x0, 16));
      svg.append(s('text', { class: 'c-cat c-cat--row', x: 0, y: cy + 4 }, d.label.length > chars ? `${d.label.slice(0, chars - 1)}…` : d.label));
      svg.append(s('text', { class: 'c-val c-val--row', x: w, y: cy + 4 }, d.total ? levelFormat(d.to) : format(d.value)));
    });
  }

  const api = {
    update(next) {
      data = prepare(next);
      draw(host.clientWidth, true);
      return data.length > 0;
    },
  };
  api.update(steps);
  onResize(host, (w) => draw(w));
  return api;
}

// ---- dispersione e bolle --------------------------------------------------------------------------------------------------------------

/** Retta ai minimi quadrati y = a + b·x; null se i punti non bastano. */
export function olsLine(points) {
  const n = points.length;
  if (n < 3) return null;
  const mx = points.reduce((a, p) => a + p.x, 0) / n;
  const my = points.reduce((a, p) => a + p.y, 0) / n;
  let sxx = 0;
  let sxy = 0;
  let syy = 0;
  for (const p of points) { sxx += (p.x - mx) ** 2; sxy += (p.x - mx) * (p.y - my); syy += (p.y - my) ** 2; }
  if (!(sxx > 0)) return null;
  const slope = sxy / sxx;
  return { slope, intercept: my - slope * mx, r: syy > 0 ? sxy / Math.sqrt(sxx * syy) : null, n };
}

/**
 * scatter(host, points, opts) → { update(points), setHidden([idGruppo…]), fit }
 *   points: [{ x, y, size, group, label, cls }] — size (facoltativo) diventa l'area della bolla;
 *   opts: label, height, xTitle, yTitle, sizeTitle, xFormat, yFormat, sizeFormat, xScale / yScale: 'linear' | 'log',
 *         groups: [{ id, label, cls }] (legenda con interruttori), diagonal: true (retta y = x, per i grafici quantile-quantile),
 *         fit: true (retta di regressione sui punti visibili), refsX / refsY: [{ value, label, cls }],
 *         showLabels: true (nome accanto a ogni punto, fino a 40 punti), tip: (punto) => contenuto, table: true.
 *   Mouse: il punto più vicino entro pochi pixel. Tastiera: ←/→ scorrono i punti in ordine di x, Inizio/Fine, Esc.
 */
export function scatter(host, points, opts = {}) {
  const {
    label = 'Dispersione', height = 320, xTitle = 'x', yTitle = 'y', sizeTitle = '', xFormat = (v) => fmtNum(v, 2), yFormat = (v) => fmtNum(v, 2),
    sizeFormat = (v) => fmtNum(v, 2), xScale = 'linear', yScale = 'linear', groups = [], diagonal = false, fit = false, refsX = [], refsY = [],
    showLabels = false, tip = null, table = false,
  } = opts;
  const groupOf = new Map(groups.map((g) => [g.id, g]));
  const hidden = new Set();
  const legend = h('div', { class: 'legend' });
  const svg = s('svg', { class: 'chart', role: 'img', tabindex: '0', 'aria-label': label });
  const live = h('div', { class: 'sr-only', 'aria-live': 'polite' });
  host.replaceChildren(...(groups.length ? [legend] : []), svg, live);
  let pts = [];
  let vis = [];
  let order = [];
  let nodes = [];
  let geo = null;
  let hover = null;
  let keyboard = false;
  let last = 0;
  let fitLine = null;

  if (table) {
    host.append(tableFallback({
      caption: label, head: ['Punto', xTitle, yTitle, ...(sizeTitle ? [sizeTitle] : [])],
      rows: () => order.map((k) => vis[k]).map((p) => [p.label || (groupOf.get(p.group) || {}).label || DASH, xFormat(p.x), yFormat(p.y), ...(sizeTitle ? [p.size == null ? null : sizeFormat(p.size)] : [])]),
    }).el);
  }
  for (const g of groups) {
    const btn = h('button', { class: 'legend__toggle', type: 'button', 'aria-pressed': 'true' }, h('span', { class: `key key--${g.cls || 's1'}`, 'aria-hidden': 'true' }), g.label);
    btn.addEventListener('click', () => {
      if (hidden.has(g.id)) hidden.delete(g.id); else hidden.add(g.id);
      btn.setAttribute('aria-pressed', hidden.has(g.id) ? 'false' : 'true');
      refresh();
    });
    legend.append(btn);
  }

  const clsOf = (p) => p.cls || (groupOf.get(p.group) || {}).cls || '';
  const tipOf = (p) => (tip ? tip(p) : {
    title: p.label || (groupOf.get(p.group) || {}).label || '',
    rows: [{ key: clsOf(p) || null, label: xTitle, value: xFormat(p.x) }, { label: yTitle, value: yFormat(p.y) }, ...(sizeTitle && p.size != null ? [{ label: sizeTitle, value: sizeFormat(p.size) }] : [])],
  });

  function refresh() {
    vis = pts.filter((p) => !hidden.has(p.group));
    order = vis.map((_, i) => i).sort((a, b) => vis[a].x - vis[b].x || vis[a].y - vis[b].y);
    fitLine = fit ? olsLine(vis) : null;
    hover = null;
    hideTip();
    draw(host.clientWidth, true);
  }

  function draw(width, force = false) {
    const w = Math.floor(width);
    if (w < 80 || (w === last && !force)) return;
    last = w;
    svg.replaceChildren();
    nodes = [];
    geo = null;
    if (!pts.length) { svg.setAttribute('height', 0); return; }
    const T = chartTheme();
    const domain = (key, scale, refs) => {
      let lo = Infinity;
      let hi = -Infinity;
      for (const p of pts) { if (p[key] < lo) lo = p[key]; if (p[key] > hi) hi = p[key]; }
      for (const r of refs) { const v = num(r.value); if (v != null && (scale !== 'log' || v > 0)) { lo = Math.min(lo, v); hi = Math.max(hi, v); } }
      if (scale === 'log') { const f = Math.max(1.05, (hi / lo) ** 0.07); return [lo / f, hi * f]; }
      const pad = (hi - lo) * 0.07 || Math.abs(hi) * 0.05 || 1;
      return [lo - pad, hi + pad];
    };
    const dx = domain('x', xScale, refsX);
    const dy = domain('y', yScale, refsY);
    if (diagonal) { dx[0] = dy[0] = Math.min(dx[0], dy[0]); dx[1] = dy[1] = Math.max(dx[1], dy[1]); }
    const yTicks = (yScale === 'log' ? logTicks : linearTicks)(dy[0], dy[1], Math.max(2, Math.round(height / 52))).filter((v) => v >= dy[0] && v <= dy[1]);
    const yLabels = yTicks.map((v) => yFormat(v));
    const gutter = Math.min(86, Math.max(40, Math.round(Math.max(4, ...yLabels.map((t) => t.length)) * 6.6 + 14)));
    const left = 1;
    const right = w - gutter;
    const top = 22;
    const bottom = top + height;
    const fx = xScale === 'log' ? Math.log10 : (v) => v;
    const fy = yScale === 'log' ? Math.log10 : (v) => v;
    const xOf = (v) => left + ((fx(v) - fx(dx[0])) / (fx(dx[1]) - fx(dx[0]))) * (right - left);
    const yOf = (v) => bottom - ((fy(v) - fy(dy[0])) / (fy(dy[1]) - fy(dy[0]))) * height;
    svg.setAttribute('viewBox', `0 0 ${w} ${bottom + 40}`);
    svg.setAttribute('width', w);
    svg.setAttribute('height', bottom + 40);

    yTicks.forEach((v, i) => {
      const y = Math.round(yOf(v)) + 0.5;
      svg.append(s('line', { class: v === 0 ? 'c-grid c-grid--zero' : 'c-grid', x1: left, x2: right, y1: y, y2: y }), s('text', { class: 'c-tick', x: right + 8, y: y + 3.5 }, yLabels[i]));
    });
    const xTicks = (xScale === 'log' ? logTicks : linearTicks)(dx[0], dx[1], Math.max(2, Math.floor((right - left) / 84))).filter((v) => v >= dx[0] && v <= dx[1]);
    for (const v of xTicks) {
      const x = Math.round(xOf(v)) + 0.5;
      svg.append(s('line', { class: v === 0 ? 'c-grid c-grid--zero' : 'c-grid', x1: x, x2: x, y1: top, y2: bottom }));
      if (x > left + 16 && x < right - 16) svg.append(s('text', { class: 'c-tick c-tick--x', x, y: bottom + 17 }, xFormat(v)));
    }
    svg.append(s('line', { class: 'c-axis', x1: left, x2: right, y1: bottom + 0.5, y2: bottom + 0.5 }));
    svg.append(s('text', { class: 'c-axis-title', x: left, y: 12 }, yTitle), s('text', { class: 'c-axis-title', x: right, y: bottom + 34, 'text-anchor': 'end' }, xTitle));

    const labels = [];
    const refLine = (ref, vertical) => {
      const v = num(ref.value);
      const d = vertical ? dx : dy;
      if (v == null || v < d[0] || v > d[1]) return;
      const c = Math.round(vertical ? xOf(v) : yOf(v)) + 0.5;
      svg.append(s('line', { class: `c-ref ${vertical ? 'c-ref--v' : ''} ${ref.cls ? `c-ref--${ref.cls}` : ''}`.trim(), x1: vertical ? c : left, x2: vertical ? c : right, y1: vertical ? top : c, y2: vertical ? bottom : c }));
      if (ref.label) labels.push(vertical ? { x: c + 5, y: top + 11, text: ref.label, end: c > right - 110 ? c - 5 : null } : { x: left + 4, y: c - 5, text: ref.label });
    };
    refsY.forEach((r) => refLine(r, false));
    refsX.forEach((r) => refLine(r, true));

    // una retta (in coordinate dei dati) ritagliata al riquadro: diagonale y = x e retta di regressione
    const clipped = (slope, intercept, cls) => {
      if (xScale === 'log' || yScale === 'log') return;
      let x0 = dx[0];
      let x1 = dx[1];
      if (slope !== 0) {
        const xa = (dy[0] - intercept) / slope;
        const xb = (dy[1] - intercept) / slope;
        x0 = Math.max(x0, Math.min(xa, xb));
        x1 = Math.min(x1, Math.max(xa, xb));
      } else if (intercept < dy[0] || intercept > dy[1]) return;
      if (!(x1 > x0)) return;
      svg.append(s('line', { class: cls, x1: xOf(x0).toFixed(1), y1: yOf(intercept + slope * x0).toFixed(1), x2: xOf(x1).toFixed(1), y2: yOf(intercept + slope * x1).toFixed(1) }));
    };
    if (diagonal) clipped(1, 0, 'c-line c-line--bench c-line--dash');
    if (fitLine) clipped(fitLine.slope, fitLine.intercept, 'c-line c-line--fit');

    const sizes = vis.map((p) => p.size).filter((v) => v != null && v > 0);
    const smax = sizes.length ? Math.max(...sizes) : 0;
    const rOf = (p) => (p.size != null && p.size > 0 && smax > 0 ? T.bubbleMin + Math.sqrt(p.size / smax) * (T.bubbleMax - T.bubbleMin) : T.dotRadius);
    const px = vis.map((p) => xOf(p.x));
    const py = vis.map((p) => yOf(p.y));
    const pr = vis.map(rOf);
    nodes = new Array(vis.length);
    const g = s('g', {});
    for (const i of vis.map((_, k) => k).sort((a, b) => pr[b] - pr[a])) {                  // le bolle grandi sotto, le piccole sopra
      nodes[i] = s('circle', { class: `c-pt ${clsOf(vis[i]) ? `c-pt--${clsOf(vis[i])}` : ''}`.trim(), cx: px[i].toFixed(1), cy: py[i].toFixed(1), r: pr[i].toFixed(1) });
      g.append(nodes[i]);
    }
    svg.append(g);
    if (showLabels && vis.length <= 40) {
      vis.forEach((p, i) => {
        if (!p.label) return;
        const flip = px[i] > right - 90;
        svg.append(s('text', { class: 'c-pt-label', x: (px[i] + (flip ? -1 : 1) * (pr[i] + 4)).toFixed(1), y: (py[i] + 3.5).toFixed(1), 'text-anchor': flip ? 'end' : null }, p.label));
      });
    }
    for (const rl of labels) {
      const text = s('text', { class: 'c-ref-label', x: rl.end != null ? rl.end : rl.x, y: rl.y, 'text-anchor': rl.end != null ? 'end' : null }, rl.text);
      svg.append(text);
      const box = typeof text.getBBox === 'function' ? text.getBBox() : null;
      if (box && box.width > 0) svg.insertBefore(s('rect', { class: 'c-ref-bg', x: box.x - 3, y: box.y - 1, width: box.width + 6, height: box.height + 2, rx: T.barRadius }), text);
    }
    geo = { px, py, pr };
    paint();
  }

  function paint() {
    nodes.forEach((node, i) => { if (node) node.classList.toggle('is-on', i === hover); });
    if (hover != null && nodes[hover]) nodes[hover].parentNode.append(nodes[hover]);        // il punto scelto sopra gli altri
  }

  function setHover(i, clientX, clientY) {
    hover = i;
    paint();
    if (i == null || !geo) { hideTip(); return; }
    const p = vis[i];
    if (clientX == null) {
      const r = svg.getBoundingClientRect();
      showTip(r.left + geo.px[i] + geo.pr[i], r.top + geo.py[i], tipOf(p));
      live.textContent = `${p.label ? `${p.label}: ` : ''}${xTitle} ${xFormat(p.x)}, ${yTitle} ${yFormat(p.y)}${sizeTitle && p.size != null ? `, ${sizeTitle} ${sizeFormat(p.size)}` : ''}`;
    } else showTip(clientX, clientY, tipOf(p));
  }

  /** Il punto visibile più vicino al puntatore, entro il suo raggio più un margine. */
  function hit(clientX, clientY) {
    if (!geo) return null;
    const r = svg.getBoundingClientRect();
    const mx = clientX - r.left;
    const my = clientY - r.top;
    let best = null;
    let bestD = Infinity;
    for (let i = 0; i < vis.length; i++) {
      const d = Math.hypot(geo.px[i] - mx, geo.py[i] - my) - geo.pr[i];
      if (d < bestD) { bestD = d; best = i; }
    }
    return bestD <= 14 ? best : null;
  }

  const onPointer = (e) => { keyboard = false; setHover(hit(e.clientX, e.clientY), e.clientX, e.clientY); };
  svg.addEventListener('pointermove', onPointer);
  svg.addEventListener('pointerdown', onPointer);
  svg.addEventListener('pointerleave', () => { if (!keyboard) setHover(null); });
  svg.addEventListener('blur', () => { keyboard = false; setHover(null); });
  svg.addEventListener('keydown', (e) => {
    if (!geo || !order.length) return;
    const pos = hover == null ? -1 : order.indexOf(hover);
    let next = null;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = Math.min(order.length - 1, pos + 1);
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = Math.max(0, pos < 0 ? order.length - 1 : pos - 1);
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = order.length - 1;
    else if (e.key === 'Escape') { keyboard = false; setHover(null); return; } else return;
    e.preventDefault();
    keyboard = true;
    setHover(order[next]);
  });

  const api = {
    update(next) {
      pts = list(next).map((p) => (p && typeof p === 'object' ? { ...p, x: num(p.x), y: num(p.y), size: num(p.size) } : null))
        .filter((p) => p && p.x != null && p.y != null && (xScale !== 'log' || p.x > 0) && (yScale !== 'log' || p.y > 0));
      refresh();
      return pts.length > 0;
    },
    setHidden(ids) {
      hidden.clear();
      for (const id of list(ids)) hidden.add(id);
      legend.querySelectorAll('.legend__toggle').forEach((btn, i) => btn.setAttribute('aria-pressed', hidden.has(groups[i].id) ? 'false' : 'true'));
      refresh();
    },
    get fit() { return fitLine; },
  };
  api.update(points);
  onResize(host, (w) => draw(w));
  return api;
}

// ---- mappa ad albero --------------------------------------------------------------------------------------------------------------------

/** Disposizione «squarified»: rettangoli di area proporzionale al valore, il più possibile vicini al quadrato. */
export function squarify(items, x, y, w, hgt) {
  const out = [];
  const total = items.reduce((a, it) => a + it.value, 0);
  if (!(total > 0) || w <= 0 || hgt <= 0) return out;
  const k = (w * hgt) / total;
  let rest = [...items].sort((a, b) => b.value - a.value).map((it) => ({ it, area: it.value * k }));
  const worst = (row, side) => {
    const sum = row.reduce((a, r) => a + r.area, 0);
    let max = 0;
    let min = Infinity;
    for (const r of row) { if (r.area > max) max = r.area; if (r.area < min) min = r.area; }
    return Math.max((side * side * max) / (sum * sum), (sum * sum) / (side * side * min));
  };
  while (rest.length) {
    const side = Math.min(w, hgt);
    const row = [rest[0]];
    let n = 1;
    while (n < rest.length && worst([...row, rest[n]], side) <= worst(row, side)) row.push(rest[n++]);
    const sum = row.reduce((a, r) => a + r.area, 0);
    const thick = sum / side;
    let pos = 0;
    for (const r of row) {
      const len = r.area / thick;
      out.push(w >= hgt ? { item: r.it, x, y: y + pos, w: thick, h: len } : { item: r.it, x: x + pos, y, w: len, h: thick });
      pos += len;
    }
    if (w >= hgt) { x += thick; w -= thick; } else { y += thick; hgt -= thick; }
    rest = rest.slice(n);
  }
  return out;
}

/**
 * treemap(host, items, { label, height, format, valueHead, tip, table }) → { update(items) }
 *   items: [{ name, value, cls, k, note, children: [{ name, value, cls, k, note }] }] — value > 0 decide l'area;
 *   cls: s1…s5 | up | down decide il colore, k (0…1) la sua intensità; con children la voce diventa un gruppo con intestazione.
 */
export function treemap(host, items, { label = 'Mappa ad albero', height = 320, format = (v) => fmtNum(v, 2), valueHead = 'Valore', tip = null, table = false } = {}) {
  const box = h('div', { class: 'tm', role: 'list', 'aria-label': label, style: { '--tm-height': `${height}px` } });
  let data = [];
  let last = 0;
  host.replaceChildren(box);
  if (table) {
    host.append(tableFallback({
      caption: label, head: ['Voce', 'Gruppo', valueHead],
      rows: () => data.flatMap((g) => (g.children ? g.children.map((c) => [c.name, g.name, format(c.value)]) : [[g.name, null, format(g.value)]])),
    }).el);
  }

  const clean = (it) => {
    if (!it || typeof it !== 'object') return null;
    const kids = Array.isArray(it.children) ? it.children.map(clean).filter(Boolean) : null;
    const value = kids && kids.length ? kids.reduce((a, c) => a + c.value, 0) : num(it.value);
    if (value == null || !(value > 0)) return null;
    return { name: String(it.name ?? ''), value, cls: it.cls || '', k: num(it.k), note: it.note || '', children: kids && kids.length ? kids : null };
  };
  const place = (el, r) => {
    for (const [prop, v] of [['left', r.x], ['top', r.y], ['width', r.w], ['height', r.h]]) el.style.setProperty(prop, `${v.toFixed(1)}px`);
    return el;
  };

  function leaf(it, r, group) {
    const total = data.reduce((a, d) => a + d.value, 0);
    const el = place(h('div', {
      class: `tm__leaf ${it.cls ? `tm__leaf--${it.cls}` : ''} ${r.w < 46 || r.h < 30 ? 'is-tiny' : ''}`.trim(), role: 'listitem', tabindex: '0',
      'aria-label': `${group ? `${group.name}, ` : ''}${it.name}: ${format(it.value)}`, style: { '--k': (it.k == null ? 0.5 : Math.max(0, Math.min(1, it.k))).toFixed(3) },
    }, h('span', { class: 'tm__name', text: it.name }), r.h >= 44 ? h('span', { class: 'tm__val', text: format(it.value) }) : null), r);
    bindTip(el, () => (tip ? tip(it, group) : {
      title: group ? `${group.name} · ${it.name}` : it.name,
      rows: [{ label: valueHead, value: format(it.value) }, { label: 'Quota del totale', value: fmtPct(it.value / total, 1) }], note: it.note,
    }));
    return el;
  }

  function draw(width, force = false) {
    const w = Math.floor(width);
    if (w < 60 || (w === last && !force)) return;
    last = w;
    box.replaceChildren();
    if (!data.length) return;
    for (const r of squarify(data, 0, 0, w, height)) {
      const it = r.item;
      if (!it.children) { box.append(leaf(it, r, null)); continue; }
      const head = r.h > 44 && r.w > 60 ? 18 : 0;
      const group = place(h('div', { class: 'tm__group', role: 'group', 'aria-label': `${it.name}: ${format(it.value)}` }), r);
      if (head) group.append(h('div', { class: 'tm__head', text: `${it.name} · ${format(it.value)}` }));
      for (const c of squarify(it.children.map((ch) => ({ ...ch, cls: ch.cls || it.cls })), 0, head, r.w - 2, r.h - 2 - head)) group.append(leaf(c.item, c, it));
      box.append(group);
    }
  }

  const api = {
    update(next) {
      data = list(next).map(clean).filter(Boolean);
      draw(host.clientWidth, true);
      return data.length > 0;
    },
  };
  api.update(items);
  onResize(host, (w) => draw(w));
  return api;
}

// ---- griglia di calore ------------------------------------------------------------------------------------------------------------------

/**
 * heatGrid(host, { rows, cols, values, counts }, { caption, corner, format, palette, scale, tip }) → { update(dati) }
 *   rows / cols: etichette; values[r][c]: numero o null; counts[r][c] (facoltativo): numerosità mostrata nel tooltip.
 *   palette: 'pnl' (verde/rosso secondo il segno), 'corr' (due tinte neutre) oppure 'seq' (una sola tinta, intensità = valore);
 *   scale: valore a cui l'intensità è piena (di norma il massimo assoluto). Ogni cella porta il suo numero: il colore
 *   non è mai l'unico canale. Per i rendimenti mensili anni × mesi resta heatmap() di charts.js.
 */
export function heatGrid(host, data, { caption = 'Griglia di calore', corner = '', format = (v) => fmtSigned(v, 2), palette = 'pnl', scale = null, tip = null } = {}) {
  const tones = { pnl: ['hm__cell--pos', 'hm__cell--neg'], corr: ['hm__cell--cool', 'hm__cell--warm'], seq: ['hm__cell--seq', 'hm__cell--seq'] }[palette] || ['hm__cell--pos', 'hm__cell--neg'];
  const api = {
    update(next) {
      const rows = list(next && next.rows).map(String);
      const cols = list(next && next.cols).map(String);
      const values = list(next && next.values);
      const counts = list(next && next.counts);
      if (!rows.length || !cols.length) { host.replaceChildren(); return false; }
      const flat = values.flatMap((r) => list(r).map(num)).filter((v) => v != null);
      const top = scale || Math.max(1e-12, ...flat.map(Math.abs));
      host.replaceChildren(h('div', { class: 'hm-wrap' }, h('table', { class: 'hm hm--grid' },
        h('caption', { class: 'sr-only', text: caption }),
        h('thead', null, h('tr', null, h('th', { class: 'hm__corner', text: corner }), cols.map((c) => h('th', { scope: 'col', text: c })))),
        h('tbody', null, rows.map((r, i) => h('tr', null,
          h('th', { scope: 'row', text: r }),
          cols.map((c, j) => {
            const v = num(list(values[i])[j]);
            if (v == null) return h('td', { class: 'hm__cell hm__cell--empty' });
            const n = num(list(counts[i])[j]);
            const td = palette === 'seq'
              ? h('td', { class: `hm__cell num ${tones[0]}`, style: { '--k': Math.min(1, Math.abs(v) / top).toFixed(3) }, text: format(v), tabindex: '0' })
              : h('td', { class: 'hm__cell num', dataset: { step: divStep(v / top) }, text: format(v), tabindex: '0' });
            bindTip(td, () => (tip ? tip(i, j, v, n) : { title: `${r} · ${c}`, rows: [{ label: 'Valore', value: format(v), cls: palette === 'pnl' ? signCls(v) : '' }, ...(n != null ? [{ label: 'Casi', value: fmtNum(n, 0) }] : [])] }));
            return td;
          })))))));
      return true;
    },
  };
  api.update(data);
  return api;
}

// ---- mirino e finestra condivisi --------------------------------------------------------------------------------------------------------

/**
 * Lega più grafici con asse del tempo: il mirino di uno compare alla stessa data sugli altri e, con window: true,
 * zoom e scorrimento di uno muovono anche gli altri. Vale per ciò che espone onHover / setHoverTime (e onWindow /
 * setWindow): timeChart, candleChart, underwater, fanChart, stackedArea. Restituisce la funzione che scioglie il legame.
 */
export function linkCharts(charts, { window: withWindow = false } = {}) {
  const all = list(charts).filter(Boolean);
  const offs = [];
  let busy = false;
  const fanOut = (source, method, ...args) => {
    if (busy) return;
    busy = true;
    try { for (const c of all) if (c !== source && typeof c[method] === 'function') c[method](...args); } finally { busy = false; }
  };
  for (const c of all) {
    if (typeof c.onHover === 'function') offs.push(c.onHover((t) => fanOut(c, 'setHoverTime', t)));
    if (withWindow && typeof c.onWindow === 'function') {
      offs.push(c.onWindow((range) => { if (range) fanOut(c, 'setWindow', range[0], range[1], { silent: true }); else fanOut(c, 'resetWindow'); }));
    }
  }
  return () => { for (const off of offs) if (typeof off === 'function') off(); };
}
