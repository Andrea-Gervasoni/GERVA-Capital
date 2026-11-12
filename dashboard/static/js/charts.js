// Grafici scritti a mano in SVG/HTML, senza librerie.
//   timeChart   linee/aree su uno o più pannelli con asse del tempo comune, mirino e tooltip (mouse, tocco, tastiera)
//   sparkline   andamento compatto senza assi
//   heatmap     rendimenti mensili anni × mesi (una vera <table>: ogni cella porta il suo numero)
//   barTable    barre orizzontali lordo/netto con i valori a fianco
//   bullet      barra di utilizzo di un limite
//   dumbbell    due valori sulla stessa scala (Sharpe da backtest → reale)
// I colori arrivano dalle classi CSS (token --chart-*), quindi il cambio di tema non richiede di ridisegnare;
// raggi e altre misure che SVG vuole come attributi arrivano da chartTheme() (js/chart-theme.js).
// Le altre primitive (cascata, dispersione, mappa ad albero, griglia di calore, ventaglio, aree impilate) sono in chart-engine.js.

import { chartTheme } from './chart-theme.js';
import { h, s } from './dom.js';
import { DASH, fmtDate, fmtDayMonth, fmtMonth, fmtMonthLong, fmtNum, fmtPct, fmtPctSigned, fmtSigned, list, num } from './format.js';

const DAY = 86400000;

// ---- tooltip (uno solo per tutta la pagina) -------------------------------------------------------------------------

let tipNode = null;
const tip = () => tipNode || (tipNode = document.getElementById('tooltip'));

/** content: { title, rows: [{ key, label, value, cls }], note } — nel tooltip il valore è l'elemento forte. */
export function showTip(clientX, clientY, content) {
  const el = tip();
  if (!el || !content) return;
  el.replaceChildren();
  if (content.title) el.append(h('div', { class: 'tooltip__title', text: content.title }));
  for (const r of content.rows || []) {
    el.append(h('div', { class: 'tooltip__row' },
      h('span', { class: 'tooltip__label' }, r.key ? h('span', { class: `key key--${r.key}`, 'aria-hidden': 'true' }) : null, r.label),
      h('span', { class: `tooltip__value num ${r.cls || ''}`.trim(), text: r.value })));
  }
  if (content.note) el.append(h('div', { class: 'tooltip__note', text: content.note }));
  el.hidden = false;
  const w = el.offsetWidth;
  const hh = el.offsetHeight;
  const vw = document.documentElement.clientWidth;
  const vh = window.innerHeight;
  let left = clientX + 14;
  if (left + w > vw - 8) left = clientX - w - 14;
  left = Math.max(8, Math.min(left, vw - w - 8));
  let top = clientY + 16;
  if (top + hh > vh - 8) top = clientY - hh - 12;
  el.style.setProperty('left', `${Math.round(left)}px`);
  el.style.setProperty('top', `${Math.round(Math.max(8, top))}px`);
}

export function hideTip() {
  const el = tip();
  if (el) el.hidden = true;
}

/** Tooltip su un singolo segno (barra, cella): stesso contenuto al passaggio del mouse e al focus da tastiera. */
export function bindTip(el, getContent) {
  const show = (e) => showTip(e.clientX, e.clientY, getContent());
  el.addEventListener('pointerenter', show);
  el.addEventListener('pointermove', show);
  el.addEventListener('pointerleave', hideTip);
  el.addEventListener('focus', () => {
    const r = el.getBoundingClientRect();
    showTip(r.left + r.width / 2, r.bottom - 6, getContent());
  });
  el.addEventListener('blur', hideTip);
  return el;
}

// ---- ridisegno al cambio di larghezza -------------------------------------------------------------------------------

const sizeCallbacks = new WeakMap();
const sizeObserver = typeof ResizeObserver === 'function'
  ? new ResizeObserver((entries) => {
    for (const entry of entries) {
      const el = entry.target;
      if (!el.isConnected) {
        sizeObserver.unobserve(el);
        continue;
      }
      const cb = sizeCallbacks.get(el);
      if (cb) cb(entry.contentRect.width);
    }
  })
  : null;

export function onResize(el, cb) {
  if (!sizeObserver) return;
  sizeCallbacks.set(el, cb);
  sizeObserver.observe(el);
}

// ---- scale e tacche ---------------------------------------------------------------------------------------------------

function niceStep(raw) {
  const p = 10 ** Math.floor(Math.log10(raw));
  const f = raw / p;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
}

export function linearTicks(lo, hi, count) {
  if (!(hi > lo)) return [lo];
  const step = niceStep((hi - lo) / Math.max(1, count));
  const out = [];
  for (let v = Math.ceil(lo / step - 1e-9) * step; v <= hi + step * 1e-9; v += step) {
    out.push(Math.abs(v) < step * 1e-9 ? 0 : Number(v.toPrecision(12)));
  }
  return out;
}

export function logTicks(lo, hi, count) {
  let out = [];
  for (let k = Math.floor(Math.log10(lo)); k <= Math.ceil(Math.log10(hi)); k++) {
    for (const m of [1, 2, 5]) {
      const v = m * 10 ** k;
      if (v >= lo && v <= hi) out.push(Number(v.toPrecision(12)));
    }
  }
  if (out.length < 3) return linearTicks(lo, hi, count);
  while (out.length > count + 2) out = out.filter((_, i) => i % 2 === 0);
  return out;
}

/** Tacche dell'asse del tempo (date in UTC): giorni per intervalli brevi, poi mesi, poi anni. */
export function timeTicks(t0, t1, maxTicks) {
  const out = [];
  const span = t1 - t0;
  if (!(span > 0)) return out;
  const max = Math.max(2, maxTicks);
  if (span <= 75 * DAY) {
    const stepDays = [1, 2, 7, 14, 28].find((d) => span / (d * DAY) <= max) || 28;
    let t = Math.ceil(t0 / DAY) * DAY;
    if (stepDays >= 7) while (new Date(t).getUTCDay() !== 1) t += DAY;       // settimane: dal lunedì
    for (; t <= t1; t += stepDays * DAY) out.push({ t, label: fmtDayMonth(t, true) });
    return out;
  }
  const months = span / (30.44 * DAY);
  const step = [1, 2, 3, 6, 12, 24, 60, 120].find((m) => months / m <= max) || 120;
  const d0 = new Date(t0);
  let idx = d0.getUTCFullYear() * 12 + d0.getUTCMonth();
  if (d0.getUTCDate() > 1) idx += 1;
  idx = Math.ceil(idx / step) * step;
  for (;; idx += step) {
    const y = Math.floor(idx / 12);
    const m = idx % 12;
    const t = Date.UTC(y, m, 1);
    if (t > t1) break;
    out.push({ t, label: step >= 12 || m === 0 ? String(y) : fmtMonth(t, true) });
  }
  return out;
}

/** Indice del punto più vicino a t in un array ordinato. */
export function nearest(xs, t) {
  let lo = 0;
  let hi = xs.length - 1;
  if (hi < 0) return -1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] < t) lo = mid;
    else hi = mid;
  }
  return Math.abs(xs[lo] - t) <= Math.abs(xs[hi] - t) ? lo : hi;
}

/**
 * Punti (x, y) in pixel → segmenti da disegnare. Con più punti che pixel tiene, per ogni colonna di pixel,
 * primo, minimo, massimo e ultimo: la forma resta identica e 3.000 punti costano come 600.
 */
function segmentsOf(px, py, plotWidth) {
  const n = px.length;
  const segments = [];
  let cur = [];
  const flush = () => {
    if (cur.length) segments.push(cur);
    cur = [];
  };
  if (n <= plotWidth * 2) {
    for (let i = 0; i < n; i++) {
      if (py[i] == null) flush();
      else cur.push([px[i], py[i]]);
    }
    flush();
    return segments;
  }
  let bucket = null;
  let first = -1;
  let last = -1;
  let lo = -1;
  let hi = -1;
  const emit = () => {
    if (first < 0) return;
    for (const i of [...new Set([first, lo, hi, last])].sort((a, b) => a - b)) cur.push([px[i], py[i]]);
    first = -1;
  };
  for (let i = 0; i < n; i++) {
    if (py[i] == null) {
      emit();
      flush();
      bucket = null;
      continue;
    }
    const b = Math.round(px[i]);
    if (b !== bucket) {
      emit();
      bucket = b;
      first = i;
      lo = i;
      hi = i;
    } else {
      if (py[i] < py[lo]) lo = i;
      if (py[i] > py[hi]) hi = i;
    }
    last = i;
  }
  emit();
  flush();
  return segments;
}

export const pathOf = (seg) => 'M' + seg.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join('L');

// ---- timeChart -----------------------------------------------------------------------------------------------------------

/**
 * Grafico temporale a pannelli sovrapposti con un solo asse x (ogni pannello ha la sua scala y: non è un doppio asse).
 *
 * chart.update({
 *   x: [ms…],                                  date ordinate
 *   panels: [{
 *     height, title,                           altezza in px, etichetta sopra il pannello
 *     scale: 'linear' | 'log',
 *     series: [{ values, cls, area, end, dots, step, name }],
 *                                              cls → .c-line--<cls>; area: riempimento fino alla base; end: pallino finale;
 *                                              dots: un pallino per punto (fino a 40); step: linea a gradini; name: intestazione in tabella
 *     format: (v, passo) => testo,             etichette dell'asse y (passo = distanza tra due tacche)
 *     top, bottom,                             estremi fissi (es. top: 0 per il drawdown)
 *     refs: [{ value, label }],                linee di riferimento tratteggiate
 *     bands: [{ lo, hi, cls }],                fasce tra due serie (ventaglio di percentili, aree impilate)
 *   }],
 *   marks: [{ t, label }],                     linee verticali di riferimento
 *   xTicks: [{ t, label }],                    tacche dell'asse x, se non sono date
 *   tip: (i) => ({ title, rows }),             contenuto del tooltip per il punto i
 *   say: (i) => testo,                         stessa cosa in una frase, per i lettori di schermo
 *   xFormat: (t) => testo, xHead: testo,       etichetta e intestazione della x nella tabella alternativa (di norma la data)
 * })
 *
 * Opzioni: label (nome accessibile); zoom: true abilita rotella = zoom, trascinamento = scorrimento, doppio clic = tutto,
 * tasti + − 0; table: true aggiunge sotto il grafico la tabella alternativa (chiusa, costruita solo all'apertura).
 * Oltre a update(): onHover(fn(t|null, i)) / setHoverTime(t) per legare il mirino ad altri grafici (linkCharts),
 * setWindow(t0, t1) / resetWindow() / onWindow(fn([t0, t1]|null)) per la finestra visibile.
 */
export function timeChart(host, { label = 'Grafico', zoom = false, table = false } = {}) {
  const svg = s('svg', { class: 'chart', role: 'img', tabindex: '0', 'aria-label': label });
  const live = h('div', { class: 'sr-only', 'aria-live': 'polite' });
  host.append(svg, live);

  let full = null;           // specifica completa
  let win = null;            // finestra visibile { a, b } (indici nella specifica completa); null = tutto
  let off = 0;               // indice del primo punto visibile
  let drag = null;
  const hoverSubs = new Set();
  const winSubs = new Set();
  const fallback = table ? tableFallback({
    caption: label,
    head: () => (full ? [full.xHead || 'Data', ...full.panels.flatMap((p) => p.series.map((sr) => sr.name || p.title || sr.cls || 'Valore'))] : []),
    rows: () => (full ? full.x.map((t, i) => [full.xFormat ? full.xFormat(t) : fmtDate(t, true),
      ...full.panels.flatMap((p) => p.series.map((sr) => (sr.values[i] == null ? null : p.format ? p.format(sr.values[i], null) : fmtNum(sr.values[i], 2))))]) : []),
  }) : null;
  if (fallback) host.append(fallback.el);

  let spec = null;
  let geo = null;
  let hover = null;          // indice del punto sotto il mirino
  let pointer = null;        // ultima posizione del puntatore, se è sul grafico
  let keyboard = false;      // mirino guidato dalla tastiera
  let lastWidth = 0;
  let overlay = null;

  function draw() {
    const width = Math.floor(host.clientWidth);
    svg.replaceChildren();
    geo = null;
    overlay = null;
    if (!spec || width < 60) return;
    lastWidth = width;
    const T = chartTheme();
    const xs = spec.x;
    const n = xs.length;
    const panels = spec.panels.map((p) => ({ ...p, dom: domainOf(p) })).filter((p) => p.dom);
    if (n < 2 || !panels.length) return;

    // etichette y: decise prima, per sapere quanto è largo il margine destro
    for (const p of panels) {
      const count = Math.max(2, Math.round(p.height / 46));
      p.ticks = (p.scale === 'log' ? logTicks(p.dom[0], p.dom[1], count) : linearTicks(p.dom[0], p.dom[1], count)).filter((v) => v >= p.dom[0] && v <= p.dom[1]);
      const step = p.ticks.length > 1 ? Math.abs(p.ticks[1] - p.ticks[0]) : null;       // serve a scegliere i decimali
      p.labels = p.ticks.map((v) => (p.format ? p.format(v, step) : fmtNum(v, 2, 0)));
    }
    const longest = Math.max(4, ...panels.flatMap((p) => p.labels.map((t) => t.length)));
    const gutter = Math.min(86, Math.max(40, Math.round(longest * 6.6 + 14)));
    const left = 1;
    const right = width - gutter;
    const plotW = right - left;
    const t0 = xs[0];
    const t1 = xs[n - 1];
    const xOf = (t) => left + ((t - t0) / (t1 - t0)) * plotW;
    const px = xs.map(xOf);

    let y = 6;
    for (const p of panels) {
      if (p.title) {
        svg.append(s('text', { class: 'c-panel-title', x: left, y: y + 10 }, p.title));
        y += 20;
      }
      p.y0 = y;
      p.y1 = y + p.height;
      const f = p.scale === 'log' ? Math.log10 : (v) => v;
      const a = f(p.dom[0]);
      const b = f(p.dom[1]);
      p.yOf = (v) => p.y1 - ((f(v) - a) / (b - a)) * p.height;
      y = p.y1 + 14;
    }
    const total = y - 14 + 24;
    svg.setAttribute('viewBox', `0 0 ${width} ${total}`);
    svg.setAttribute('width', width);
    svg.setAttribute('height', total);

    const refLabels = [];
    for (const p of panels) {
      const g = s('g', {});
      p.ticks.forEach((v, i) => {
        const yy = Math.round(p.yOf(v)) + 0.5;
        g.append(s('line', { class: v === 0 ? 'c-grid c-grid--zero' : 'c-grid', x1: left, x2: right, y1: yy, y2: yy }));
        g.append(s('text', { class: 'c-tick', x: right + 8, y: yy + 3.5 }, p.labels[i]));
      });
      for (const ref of p.refs || []) {
        const v = num(ref.value);
        if (v == null || v < p.dom[0] || v > p.dom[1]) continue;
        const yy = Math.round(p.yOf(v)) + 0.5;
        g.append(s('line', { class: 'c-ref', x1: left, x2: right, y1: yy, y2: yy }));
        if (ref.label) refLabels.push({ x: left + 4, y: yy - 5, text: ref.label });
      }
      for (const band of p.bands || []) {
        const up = [];
        const down = [];
        for (let i = 0; i < n; i++) {
          const a = band.lo[i];
          const b = band.hi[i];
          if (a == null || b == null || (p.scale === 'log' && (a <= 0 || b <= 0))) continue;
          up.push(`${px[i].toFixed(1)},${p.yOf(b).toFixed(1)}`);
          down.push(`${px[i].toFixed(1)},${p.yOf(a).toFixed(1)}`);
        }
        if (up.length > 1) g.append(s('path', { class: `c-band c-band--${band.cls}`, d: `M${up.join('L')}L${down.reverse().join('L')}Z` }));
      }
      for (const sr of p.series) {
        const py = sr.values.map((v) => (v == null || (p.scale === 'log' && v <= 0) ? null : p.yOf(v)));
        let segs = segmentsOf(px, py, plotW);
        if (!segs.length) continue;
        if (sr.step) segs = segs.map((seg) => seg.flatMap((pt, i) => (i === 0 ? [pt] : [[pt[0], seg[i - 1][1]], pt])));
        if (sr.area) {
          const base = p.top === 0 ? p.yOf(0) : p.y1;
          const d = segs.map((seg) => `${pathOf(seg)}L${seg[seg.length - 1][0].toFixed(1)},${base.toFixed(1)}L${seg[0][0].toFixed(1)},${base.toFixed(1)}Z`).join('');
          g.append(s('path', { class: `c-area c-area--${sr.cls}`, d }));
        }
        g.append(s('path', { class: `c-line c-line--${sr.cls}`, d: segs.map(pathOf).join('') }));
        if (sr.dots && n <= 40) {
          for (let i = 0; i < n; i++) if (py[i] != null) g.append(s('circle', { class: `c-dot c-dot--${sr.cls}`, cx: px[i].toFixed(1), cy: py[i].toFixed(1), r: T.dotRadiusSmall }));
        }
        if (sr.end) {
          for (let i = n - 1; i >= 0; i--) {
            if (py[i] != null) {
              g.append(s('circle', { class: `c-dot c-dot--${sr.cls}`, cx: px[i].toFixed(1), cy: py[i].toFixed(1), r: T.dotRadius }));
              break;
            }
          }
        }
        sr.py = py;
      }
      svg.append(g);
    }

    // asse del tempo sotto l'ultimo pannello
    const bottom = panels[panels.length - 1].y1;
    svg.append(s('line', { class: 'c-axis', x1: left, x2: right, y1: bottom + 0.5, y2: bottom + 0.5 }));
    // linee verticali di riferimento (es. confine tra periodo di scelta e di verifica)
    for (const mk of spec.marks || []) {
      if (mk.t == null || mk.t < t0 || mk.t > t1) continue;
      const x = Math.round(xOf(mk.t)) + 0.5;
      svg.append(s('line', { class: 'c-mark', x1: x, x2: x, y1: panels[0].y0, y2: bottom }));
      if (mk.label) refLabels.push({ x: x + 5, y: panels[0].y0 + 11 + (mk.row || 0) * 15, text: mk.label, end: x > right - 120 ? x - 5 : null });
    }
    for (const tk of (spec.xTicks || timeTicks(t0, t1, Math.floor(plotW / 60)))) {
      const x = xOf(tk.t);
      const edge = x < left + 14 ? 'start' : x > right - 14 ? 'end' : null;
      if (x < left - 1 || x > right + 1 || (edge && !spec.xTicks)) continue;
      svg.append(s('line', { class: 'c-axis', x1: Math.round(x) + 0.5, x2: Math.round(x) + 0.5, y1: bottom, y2: bottom + 4 }));
      svg.append(s('text', { class: 'c-tick c-tick--x', x: x.toFixed(1), y: bottom + 17, 'text-anchor': edge }, tk.label));
    }

    // etichette delle linee di riferimento: sopra le serie, su un fondo del colore della scheda per restare leggibili
    for (const rl of refLabels) {
      const text = s('text', { class: 'c-ref-label', x: rl.end != null ? rl.end : rl.x, y: rl.y, 'text-anchor': rl.end != null ? 'end' : null }, rl.text);
      svg.append(text);
      const box = typeof text.getBBox === 'function' ? text.getBBox() : null;
      if (box && box.width > 0) svg.insertBefore(s('rect', { class: 'c-ref-bg', x: box.x - 3, y: box.y - 1, width: box.width + 6, height: box.height + 2, rx: T.barRadius }), text);
    }

    overlay = s('g', { class: 'c-overlay' });
    svg.append(overlay);
    geo = { left, right, t0, t1, px, panels, top: panels[0].y0, bottom, n };
    paintHover();
  }

  function domainOf(p) {
    let lo = Infinity;
    let hi = -Infinity;
    for (const sr of p.series) {
      for (const v of sr.values) {
        if (v == null || (p.scale === 'log' && v <= 0)) continue;
        if (v < lo) lo = v;
        if (v > hi) hi = v;
      }
    }
    for (const ref of p.refs || []) {
      const v = num(ref.value);
      if (v == null) continue;
      lo = Math.min(lo, v);
      hi = Math.max(hi, v);
    }
    for (const band of p.bands || []) {
      for (const arr2 of [band.lo, band.hi]) {
        for (const v of arr2) {
          if (v == null || (p.scale === 'log' && v <= 0)) continue;
          if (v < lo) lo = v;
          if (v > hi) hi = v;
        }
      }
    }
    if (lo === Infinity) return null;
    if (p.scale === 'log') {
      const f = Math.max(1.01, (hi / lo) ** 0.06);
      return [lo / f, hi * f];
    }
    const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.02 || 1;
    let a = lo - pad;
    let b = hi + pad;
    if (p.top != null) b = p.top;
    if (p.bottom != null) a = p.bottom;
    if (lo >= 0 && a < 0 && p.bottom == null) a = 0;            // una serie positiva non scende sotto zero per il margine
    if (!(b > a)) a = b - (Math.abs(b) * 0.02 || 0.01);
    return [a, b];
  }

  function paintHover() {
    if (!overlay || !geo) return;
    overlay.replaceChildren();
    if (hover == null || hover < 0 || hover >= geo.n) return;
    const x = geo.px[hover];
    overlay.append(s('line', { class: 'c-cross', x1: x.toFixed(1), x2: x.toFixed(1), y1: geo.top, y2: geo.bottom }));
    for (const p of geo.panels) {
      for (const sr of p.series) {
        const yv = sr.py ? sr.py[hover] : null;
        if (yv != null) overlay.append(s('circle', { class: `c-dot c-dot--${sr.cls}`, cx: x.toFixed(1), cy: yv.toFixed(1), r: chartTheme().dotRadius }));
      }
    }
  }

  function showHoverTip() {
    if (hover == null || !geo || !spec || !spec.tip) return;
    const content = spec.tip(hover);
    if (pointer) {
      showTip(pointer.x, pointer.y, content);
    } else if (keyboard) {
      const r = svg.getBoundingClientRect();
      showTip(r.left + geo.px[hover], r.top + geo.top + 8, content);
      if (spec.say) live.textContent = spec.say(hover);
    }
  }

  function setHover(i) {
    const changed = hover !== i;
    hover = i;
    paintHover();
    if (i == null) hideTip();
    else showHoverTip();
    if (changed) for (const fn of hoverSubs) fn(i == null || !spec ? null : spec.x[i], i == null ? null : i + off);
  }

  /** La specifica ristretta alla finestra visibile: il resto del disegno non sa che esiste uno zoom. */
  function windowed() {
    off = 0;
    if (!full) return null;
    if (!win) return full;
    const { a, b } = win;
    off = a;
    const cut = (arr2) => arr2.slice(a, b + 1);
    return {
      ...full, x: cut(full.x),
      panels: full.panels.map((p) => ({
        ...p, series: p.series.map((sr) => ({ ...sr, values: cut(sr.values) })),
        bands: (p.bands || []).map((bd) => ({ ...bd, lo: cut(bd.lo), hi: cut(bd.hi) })),
      })),
      tip: full.tip ? (i) => full.tip(i + a) : null, say: full.say ? (i) => full.say(i + a) : null,
    };
  }

  function setWin(a, b, silent = false) {
    if (!full) return;
    const n = full.x.length;
    const size = Math.max(Math.min(4, n - 1), Math.min(n - 1, Math.round(b - a)));
    a = Math.round(Math.max(0, Math.min(n - 1 - size, a)));
    b = a + size;
    const next = a <= 0 && b >= n - 1 ? null : { a, b };
    if ((!next && !win) || (next && win && next.a === win.a && next.b === win.b)) return;
    const keepT = hover != null && spec ? spec.x[hover] : null;
    win = next;
    spec = windowed();
    hover = keepT != null && keepT >= spec.x[0] && keepT <= spec.x[spec.x.length - 1] ? nearest(spec.x, keepT) : null;
    draw();
    if (!silent) for (const fn of winSubs) fn(win ? [full.x[win.a], full.x[win.b]] : null);
  }
  const bounds = () => win || { a: 0, b: full.x.length - 1 };
  function zoomBy(factor, anchor) {
    const { a, b } = bounds();
    const size = Math.max(8, (b - a) * factor);
    const frac = (anchor - a) / Math.max(1, b - a);
    setWin(anchor - frac * size, anchor - frac * size + size);
  }

  function indexAt(clientX) {
    if (!geo) return null;
    const r = svg.getBoundingClientRect();
    const frac = (clientX - r.left - geo.left) / (geo.right - geo.left);
    return nearest(spec.x, geo.t0 + Math.min(1, Math.max(0, frac)) * (geo.t1 - geo.t0));
  }

  const onPointer = (e) => {
    pointer = { x: e.clientX, y: e.clientY };
    keyboard = false;
    if (zoom && full && geo) {
      if (e.type === 'pointerdown' && win) drag = { x: e.clientX, a: win.a, b: win.b };
      else if (drag && e.buttons === 0 && e.pointerType === 'mouse') drag = null;
      if (drag && e.type === 'pointermove') {
        const shift = Math.round(((drag.x - e.clientX) / (geo.right - geo.left)) * (drag.b - drag.a));
        setWin(drag.a + shift, drag.b + shift);
      }
    }
    setHover(indexAt(e.clientX));
  };
  const onLeave = () => {
    pointer = null;
    drag = null;
    if (!keyboard) setHover(null);
  };
  svg.addEventListener('pointerup', () => { drag = null; });
  if (zoom) {
    svg.classList.add('chart--zoom');
    svg.addEventListener('wheel', (e) => {
      if (!full || !geo) return;
      e.preventDefault();
      zoomBy(e.deltaY > 0 ? 1.25 : 0.8, (indexAt(e.clientX) ?? spec.x.length - 1) + off);
    }, { passive: false });
    svg.addEventListener('dblclick', () => { if (full) setWin(0, full.x.length - 1); });
  }
  svg.addEventListener('pointermove', onPointer);
  svg.addEventListener('pointerdown', onPointer);
  svg.addEventListener('pointerleave', onLeave);
  svg.addEventListener('pointercancel', onLeave);
  svg.addEventListener('focus', () => {
    if (!geo || pointer || !svg.matches(':focus-visible')) return;
    keyboard = true;
    setHover(hover == null ? geo.n - 1 : hover);
  });
  svg.addEventListener('blur', () => {
    keyboard = false;
    if (!pointer) setHover(null);
  });
  svg.addEventListener('keydown', (e) => {
    if (!geo) return;
    const n = geo.n;
    const cur = hover == null ? n - 1 : hover;
    const big = Math.max(1, Math.round(n / 20));
    const moves = { ArrowLeft: -1, ArrowRight: 1, PageUp: -big, PageDown: big };
    let next = null;
    if (e.key in moves) next = cur + moves[e.key] * (e.shiftKey && Math.abs(moves[e.key]) === 1 ? 10 : 1);
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = n - 1;
    else if (e.key === 'Escape') {
      keyboard = false;
      setHover(null);
      return;
    } else if (zoom && full && (e.key === '+' || e.key === '=' || e.key === '-' || e.key === '_' || e.key === '0')) {
      e.preventDefault();
      if (e.key === '0') setWin(0, full.x.length - 1);
      else zoomBy(e.key === '+' || e.key === '=' ? 0.7 : 1.4, cur + off);
      return;
    } else return;
    e.preventDefault();
    keyboard = true;
    pointer = null;
    if (zoom && win && (next < 0 || next > n - 1)) {                // al bordo della finestra il mirino trascina la finestra
      const target = Math.max(0, Math.min(full.x.length - 1, next + off));
      const shift = next < 0 ? target - win.a : target - win.b;
      setWin(win.a + shift, win.b + shift);
      setHover(nearest(spec.x, full.x[target]));
      return;
    }
    setHover(Math.min(n - 1, Math.max(0, next)));
  });

  onResize(host, (w) => {
    if (Math.abs(Math.floor(w) - lastWidth) >= 1) draw();
  });

  return {
    update(next) {
      const keepT = hover != null && spec && spec.x[hover] != null ? spec.x[hover] : null;
      const range = win && full ? [full.x[win.a], full.x[win.b]] : null;
      full = next && Array.isArray(next.x) && next.x.length >= 2 ? next : null;
      win = null;
      if (full && range) {                                          // la finestra resta sulle stesse date
        const a = nearest(full.x, range[0]);
        const b = nearest(full.x, range[1]);
        if (b - a >= 2 && (a > 0 || b < full.x.length - 1)) win = { a, b };
      }
      spec = windowed();
      hover = spec && keepT != null && (pointer || keyboard) ? nearest(spec.x, keepT) : null;
      draw();
      if (hover != null) showHoverTip();
      if (fallback) fallback.refresh();
    },
    get empty() {
      return !spec;
    },
    /** fn(t | null, indice | null) a ogni spostamento del mirino; restituisce la funzione che toglie l'ascolto. */
    onHover(fn) { hoverSubs.add(fn); return () => hoverSubs.delete(fn); },
    /** Mirino comandato da fuori (un altro grafico): nessun tooltip e nessun avviso agli ascoltatori. */
    setHoverTime(t) {
      if (!spec || pointer || keyboard) return;
      hover = t == null || t < spec.x[0] || t > spec.x[spec.x.length - 1] ? null : nearest(spec.x, t);
      paintHover();
    },
    setWindow(t0, t1, { silent = false } = {}) { if (full) setWin(nearest(full.x, t0), nearest(full.x, t1), silent); },
    resetWindow() { if (full) setWin(0, full.x.length - 1); },
    onWindow(fn) { winSubs.add(fn); return () => winSubs.delete(fn); },
    get window() { return full && win ? [full.x[win.a], full.x[win.b]] : null; },
  };
}

// ---- tabella alternativa a un grafico ------------------------------------------------------------------------------------------

/**
 * Un <details> chiuso con gli stessi dati del grafico in una vera tabella; le righe si costruiscono solo all'apertura.
 * head: [testo…] (o funzione), rows: () => [[cella…]] (null diventa «—»); la prima colonna è testo, le altre numeri.
 */
export function tableFallback({ summary = 'Mostra i dati in tabella', caption = '', head = [], rows = () => [], max = 400 } = {}) {
  const body = h('div', { class: 'chart-fallback__body table-wrap' });
  const el = h('details', { class: 'chart-fallback' }, h('summary', { class: 'chart-fallback__summary', text: summary }), body);
  function build() {
    const cols = typeof head === 'function' ? head() : head;
    const all = list(rows());
    const shown = all.length > max ? all.slice(all.length - max) : all;
    body.replaceChildren(
      h('table', { class: 'table table--dense' },
        caption ? h('caption', { class: 'sr-only', text: caption }) : null,
        h('thead', null, h('tr', null, cols.map((c, i) => h('th', { scope: 'col', class: i ? 'is-num' : '', text: c })))),
        h('tbody', null, shown.map((r) => h('tr', null, r.map((c, i) => h('td', { class: i ? 'is-num' : '', text: c == null || c === '' ? DASH : c })))))),
      all.length > max ? h('p', { class: 'chart-fallback__note', text: `Mostrate le ultime ${fmtNum(max, 0)} righe su ${fmtNum(all.length, 0)}.` }) : null,
      !all.length ? h('p', { class: 'chart-fallback__note', text: 'Nessun dato.' }) : null);
  }
  el.addEventListener('toggle', () => { if (el.open) build(); else body.replaceChildren(); });
  return { el, refresh() { if (el.open) build(); } };
}

// ---- sparkline -------------------------------------------------------------------------------------------------------------

/** Andamento compatto: linea neutra, livello di partenza come filetto, ultimo punto nell'accento. */
export function sparkline(values, { width = 132, height = 36, label = 'Andamento' } = {}) {
  const pts = list(values).map(num).filter((v) => v != null);
  if (pts.length < 2) return h('span', { class: 'spark spark--empty num', text: DASH });
  const lo = Math.min(...pts);
  const hi = Math.max(...pts);
  const span = hi - lo || Math.abs(hi) * 0.01 || 1;
  const pad = 5;
  const xOf = (i) => pad + (i / (pts.length - 1)) * (width - pad * 2);
  const yOf = (v) => pad + (1 - (v - lo) / span) * (height - pad * 2);
  const change = pts[0] !== 0 ? pts[pts.length - 1] / pts[0] - 1 : null;
  const svg = s('svg', {
    class: 'spark', width, height, viewBox: `0 0 ${width} ${height}`, role: 'img',
    'aria-label': `${label}: ${change == null ? 'variazione non calcolabile' : fmtPctSigned(change, 1)} su ${pts.length} punti`,
  });
  const y0 = (Math.round(yOf(pts[0])) + 0.5).toFixed(1);
  svg.append(s('line', { class: 'spark__base', x1: pad, x2: width - pad, y1: y0, y2: y0 }));
  svg.append(s('path', { class: 'spark__line', d: 'M' + pts.map((v, i) => `${xOf(i).toFixed(1)},${yOf(v).toFixed(1)}`).join('L') }));
  svg.append(s('circle', { class: 'spark__dot', cx: xOf(pts.length - 1).toFixed(1), cy: yOf(pts[pts.length - 1]).toFixed(1), r: chartTheme().dotRadiusSmall }));
  return svg;
}

// ---- heatmap dei rendimenti mensili ------------------------------------------------------------------------------------------

const MONTHS = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic'];

/** Passo della rampa divergente blu ↔ arancio (1…9, 5 = neutro) per un valore in −1…+1: positivo = blu. */
export function divStep(t) {
  const a = Math.abs(t);
  if (!(a >= 0.08)) return 5;
  const st = a < 0.3 ? 1 : a < 0.55 ? 2 : a < 0.8 ? 3 : 4;
  return t > 0 ? 5 - st : 5 + st;
}

/**
 * grid: risultato di monthlyGrid(). Verde/rosso sono il segno del rendimento, e ogni cella porta comunque
 * il numero con il suo segno: il colore non è mai l'unico canale. Su schermi stretti la tabella si traspone
 * (mesi in riga, anni in colonna) così i numeri restano leggibili.
 */
export function heatmap(host, grid) {
  let narrow = null;

  function cell(year, month) {
    const r = grid.cell.get(`${year}-${month}`);
    if (r == null) return h('td', { class: 'hm__cell hm__cell--empty' });
    const td = h('td', { class: 'hm__cell num', dataset: { step: divStep(r / grid.scale) }, text: fmtSigned(r * 100, 1) });
    const when = Date.UTC(year, month - 1, 1);
    bindTip(td, () => ({ title: fmtMonthLong(when, true), rows: [{ label: 'Rendimento', value: fmtPctSigned(r, 2), cls: r > 0 ? 'pos' : r < 0 ? 'neg' : '' }] }));
    return td;
  }

  const total = (year) => {
    const v = grid.totals.get(year);
    return h('td', { class: `hm__total num ${v > 0 ? 'pos' : v < 0 ? 'neg' : ''}`.trim(), text: fmtPctSigned(v, 1) });
  };

  function build(isNarrow) {
    const table = h('table', { class: `hm ${isNarrow ? 'hm--narrow' : ''}`.trim() });
    table.append(h('caption', { class: 'sr-only', text: 'Rendimenti mensili in percentuale, per anno e per mese' }));
    if (!isNarrow) {
      const years = [...grid.years].reverse();                  // l'anno più recente in alto
      table.append(h('thead', null, h('tr', null,
        h('th', { scope: 'col', class: 'hm__corner', text: 'Anno' }),
        MONTHS.map((m) => h('th', { scope: 'col', text: m })),
        h('th', { scope: 'col', class: 'hm__total-head', text: 'Totale' }))));
      table.append(h('tbody', null, years.map((y) => h('tr', null,
        h('th', { scope: 'row', class: 'num', text: String(y) }),
        MONTHS.map((_, i) => cell(y, i + 1)),
        total(y)))));
    } else {
      const years = grid.years;                                 // il tempo scorre da sinistra a destra
      table.append(h('thead', null, h('tr', null,
        h('th', { scope: 'col', class: 'hm__corner', text: 'Mese' }),
        years.map((y) => h('th', { scope: 'col', class: 'num', text: String(y) })))));
      table.append(h('tbody', null,
        MONTHS.map((m, i) => h('tr', null, h('th', { scope: 'row', text: m }), years.map((y) => cell(y, i + 1)))),
        h('tr', { class: 'hm__total-row' }, h('th', { scope: 'row', text: 'Totale' }), years.map((y) => total(y)))));
    }
    return table;
  }

  function render(width) {
    const isNarrow = width < 620;
    if (isNarrow === narrow) return;
    narrow = isNarrow;
    const wrap = h('div', { class: 'hm-wrap' }, build(isNarrow));
    const steps = [-1, -0.5, 0, 0.5, 1];
    const legend = h('div', { class: 'hm-legend', 'aria-hidden': 'true' },
      h('span', { class: 'num', text: fmtPctSigned(-grid.scale, 0) }),
      steps.map((k) => h('span', { class: 'hm-legend__swatch', dataset: { step: divStep(k * 0.99) } })),
      h('span', { class: 'num', text: fmtPctSigned(grid.scale, 0) }),
      h('span', { class: 'hm-legend__note', text: 'arancio = perdita, blu = guadagno; intensità = ampiezza' }));
    host.replaceChildren(wrap, legend);
    if (isNarrow) wrap.scrollLeft = wrap.scrollWidth;           // parte dagli anni più recenti
  }

  render(host.clientWidth || 800);
  onResize(host, (w) => { if (w > 0) render(w); });
}

// ---- barre orizzontali lordo / netto ---------------------------------------------------------------------------------------

/**
 * rows: [{ name, gross, net }] in frazioni del NAV. Una riga per voce: due barre sottili sulla stessa scala
 * (lordo in grigio, netto nell'accento, a sinistra dello zero se corto) e i due valori a fianco.
 */
export function barTable(rows, { nameHead = 'Voce', amount = null } = {}) {
  const vals = rows.flatMap((r) => [num(r.gross), num(r.net)]).filter((v) => v != null);
  const hi = Math.max(0.0001, ...vals.map((v) => Math.max(0, v)));
  const lo = Math.min(0, ...vals);
  const span = hi - lo;
  const zero = ((0 - lo) / span) * 100;
  const hasShort = lo < 0;
  const bar = (v, cls) => {
    if (v == null) return null;
    const w = (Math.abs(v) / span) * 100;
    return h('span', { class: `bars__bar bars__bar--${cls} ${v < 0 ? 'bars__bar--left' : ''}`.trim(), style: { left: `${(v < 0 ? zero - w : zero).toFixed(2)}%`, width: `${Math.max(w, 0.6).toFixed(2)}%` } });
  };
  const table = h('table', { class: 'bars' },
    h('thead', null, h('tr', null,
      h('th', { scope: 'col', text: nameHead }),
      h('th', { scope: 'col', class: 'bars__viz-head' }, h('span', { class: 'sr-only', text: 'Grafico' })),
      h('th', { scope: 'col', class: 'bars__num' }, h('span', { class: 'key key--bench', 'aria-hidden': 'true' }), 'Lordo'),
      h('th', { scope: 'col', class: 'bars__num' }, h('span', { class: 'key key--fund', 'aria-hidden': 'true' }), 'Netto'))),
    h('tbody', null, rows.map((r) => {
      const g = num(r.gross);
      const nt = num(r.net);
      const viz = h('td', { class: 'bars__viz' },
        h('span', { class: 'bars__track' }, bar(g, 'gross'), bar(nt, 'net'), hasShort ? h('span', { class: 'bars__zero', style: { left: `${zero.toFixed(2)}%` } }) : null));
      const tr = h('tr', { tabindex: '0' },
        h('th', { scope: 'row', class: 'bars__name', text: r.name || DASH }),
        viz,
        h('td', { class: 'bars__num num', text: fmtPct(g, 1) }),
        h('td', { class: 'bars__num num', text: hasShort ? fmtPctSigned(nt, 1) : fmtPct(nt, 1) }));
      bindTip(tr, () => ({
        title: r.name || '',
        rows: [
          { key: 'bench', label: 'Lordo', value: amount && g != null ? `${fmtPct(g, 1)} · ${amount(g)}` : fmtPct(g, 1) },
          { key: 'fund', label: 'Netto', value: amount && nt != null ? `${fmtPctSigned(nt, 1)} · ${amount(nt)}` : fmtPctSigned(nt, 1) },
        ],
        note: 'in percentuale del patrimonio',
      }));
      return tr;
    })));
  return table;
}

// ---- barra di utilizzo di un limite ------------------------------------------------------------------------------------------

/** ratio: valore / soglia (1 = alla soglia). kind: ok | warn | crit | muted. La traccia intera è la soglia. */
export function bullet({ ratio, kind = 'ok', label = 'Utilizzo', text = '' }) {
  const r = num(ratio);
  const shown = r == null ? 0 : Math.min(1, Math.max(0, r));
  const el = h('span', { class: `bullet bullet--${kind} ${r != null && r > 1 ? 'bullet--over' : ''}`.trim() },
    h('span', { class: 'bullet__fill', style: { width: `${(shown * 100).toFixed(1)}%` } }));
  if (r != null) {
    el.setAttribute('role', 'meter');
    el.setAttribute('aria-valuemin', '0');
    el.setAttribute('aria-valuemax', '100');
    el.setAttribute('aria-valuenow', String(Math.round(shown * 100)));
    el.setAttribute('aria-label', label);
    if (text) el.setAttribute('aria-valuetext', text);
  }
  return el;
}

// ---- dumbbell: backtest → reale -----------------------------------------------------------------------------------------------

/** Due valori sulla stessa scala: cerchio vuoto = backtest, pieno = reale. Scala condivisa tra le righe (min, max). */
export function dumbbell({ from, to, min = 0, max = 1, width = 132, label = '' }) {
  const a = num(from);
  const b = num(to);
  const height = 18;
  const pad = 7;
  if (a == null && b == null) return h('span', { class: 'num muted', text: DASH });
  const span = max - min || 1;
  const xOf = (v) => pad + (Math.min(max, Math.max(min, v)) - min) / span * (width - pad * 2);
  const svg = s('svg', { class: 'dumbbell', width, height, viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': label });
  svg.append(s('line', { class: 'dumbbell__track', x1: pad, x2: width - pad, y1: 9.5, y2: 9.5 }));
  if (min < 0 && max > 0) svg.append(s('line', { class: 'dumbbell__zero', x1: xOf(0).toFixed(1), x2: xOf(0).toFixed(1), y1: 4, y2: 15 }));
  if (a != null && b != null) svg.append(s('line', { class: 'dumbbell__link', x1: xOf(a).toFixed(1), x2: xOf(b).toFixed(1), y1: 9.5, y2: 9.5 }));
  if (a != null) svg.append(s('circle', { class: 'dumbbell__from', cx: xOf(a).toFixed(1), cy: 9.5, r: chartTheme().dotRadius }));
  if (b != null) svg.append(s('circle', { class: 'dumbbell__to', cx: xOf(b).toFixed(1), cy: 9.5, r: chartTheme().dotRadius + 0.5 }));
  return svg;
}


// ---- barre con segno (una per riga) ----------------------------------------------------------------------------------------

/** rows: [{ label, value, text, note, tag, kind }] — barra dallo zero verso destra o sinistra, valore e nota a fianco. */
export function signedBars(rows, { labelHead = 'Voce', valueHead = 'Valore', noteHead = '', tone = false } = {}) {
  const vals = rows.map((r) => num(r.value)).filter((v) => v != null);
  const hi = Math.max(0.0001, ...vals.map((v) => Math.max(0, v)));
  const lo = Math.min(0, ...vals);
  const span = hi - lo;
  const zero = ((0 - lo) / span) * 100;
  return h('table', { class: 'bars bars--single' },
    h('thead', null, h('tr', null,
      h('th', { scope: 'col', text: labelHead }),
      h('th', { scope: 'col' }, h('span', { class: 'sr-only', text: 'Grafico' })),
      h('th', { scope: 'col', class: 'bars__num', text: valueHead }),
      noteHead ? h('th', { scope: 'col', class: 'bars__note', text: noteHead }) : null)),
    h('tbody', null, rows.map((r) => {
      const v = num(r.value);
      const w = v == null ? 0 : (Math.abs(v) / span) * 100;
      const cls = r.kind || (tone ? (v > 0 ? 'pos' : v < 0 ? 'neg' : 'net') : 'net');
      return h('tr', { class: r.mark ? 'is-marked' : null },
        h('th', { scope: 'row', class: 'bars__name' }, r.label, r.tag ? h('span', { class: 'tag tag--plain bars__tag', text: r.tag }) : null),
        h('td', { class: 'bars__viz' }, h('span', { class: 'bars__track bars__track--one' },
          v == null ? null : h('span', { class: `bars__bar bars__bar--one bars__bar--${cls} ${v < 0 ? 'bars__bar--left' : ''}`.trim(), style: { left: `${(v < 0 ? zero - w : zero).toFixed(2)}%`, width: `${Math.max(w, 0.6).toFixed(2)}%` } }),
          lo < 0 ? h('span', { class: 'bars__zero', style: { left: `${zero.toFixed(2)}%` } }) : null)),
        h('td', { class: `bars__num num ${tone && v != null ? (v > 0 ? 'pos' : v < 0 ? 'neg' : '') : ''}`.trim(), text: r.text == null ? DASH : r.text }),
        noteHead ? h('td', { class: 'bars__note', text: r.note || '' }) : null);
    })));
}

/** Due barre per riga su una scala comune (es. scelta contro verifica). rows: [{ name, a, b, aText, bText, extra }] */
export function dualBars(rows, { nameHead = 'Voce', aHead = 'A', bHead = 'B', extraHead = '', extraCls = '' } = {}) {
  const vals = rows.flatMap((r) => [num(r.a), num(r.b)]).filter((v) => v != null);
  const hi = Math.max(0.0001, ...vals.map((v) => Math.max(0, v)));
  const lo = Math.min(0, ...vals);
  const span = hi - lo;
  const zero = ((0 - lo) / span) * 100;
  const bar = (v, cls) => {
    if (v == null) return null;
    const w = (Math.abs(v) / span) * 100;
    return h('span', { class: `bars__bar bars__bar--${cls} ${v < 0 ? 'bars__bar--left' : ''}`.trim(), style: { left: `${(v < 0 ? zero - w : zero).toFixed(2)}%`, width: `${Math.max(w, 0.6).toFixed(2)}%` } });
  };
  return h('table', { class: 'bars' },
    h('thead', null, h('tr', null,
      h('th', { scope: 'col', text: nameHead }),
      h('th', { scope: 'col' }, h('span', { class: 'sr-only', text: 'Grafico' })),
      h('th', { scope: 'col', class: 'bars__num' }, h('span', { class: 'key key--bench', 'aria-hidden': 'true' }), aHead),
      h('th', { scope: 'col', class: 'bars__num' }, h('span', { class: 'key key--fund', 'aria-hidden': 'true' }), bHead),
      extraHead ? h('th', { scope: 'col', class: `bars__num bars__extra ${extraCls}`.trim(), text: extraHead }) : null)),
    h('tbody', null, rows.map((r) => h('tr', { class: r.group ? 'bars__group' : null },
      h('th', { scope: 'row', class: 'bars__name' }, r.name),
      h('td', { class: 'bars__viz' }, h('span', { class: 'bars__track' }, bar(num(r.a), 'gross'), bar(num(r.b), 'net'), lo < 0 ? h('span', { class: 'bars__zero', style: { left: `${zero.toFixed(2)}%` } }) : null)),
      h('td', { class: 'bars__num num', text: r.aText == null ? DASH : r.aText }),
      h('td', { class: 'bars__num num', text: r.bText == null ? DASH : r.bText }),
      extraHead ? h('td', { class: `bars__num bars__extra num ${extraCls}`.trim(), text: r.extra || DASH }) : null))));
}

// ---- matrice (correlazioni) ---------------------------------------------------------------------------------------------------

/** Matrice quadrata con il numero in ogni cella; blu = si muovono insieme, arancio = in senso opposto, grigio = indipendenti. */
export function matrix(labels, values, { caption = 'Matrice' } = {}) {
  return h('div', { class: 'hm-wrap' }, h('table', { class: 'hm hm--matrix' },
    h('caption', { class: 'sr-only', text: caption }),
    h('thead', null, h('tr', null, h('th', { class: 'hm__corner' }), labels.map((l) => h('th', { scope: 'col', text: l })))),
    h('tbody', null, labels.map((l, i) => h('tr', null,
      h('th', { scope: 'row', text: l }),
      labels.map((m, j) => {
        const v = num((values[i] || [])[j]);
        if (v == null) return h('td', { class: 'hm__cell hm__cell--empty' });
        const td = h('td', { class: `hm__cell num ${i === j ? 'hm__cell--diag' : ''}`.trim(), dataset: i === j ? {} : { step: divStep(v / 0.9) }, text: fmtSigned(v, 2) });
        bindTip(td, () => ({ title: `${l} · ${m}`, rows: [{ label: 'Correlazione', value: fmtSigned(v, 3) }] }));
        return td;
      }))))));
}

// ---- istogramma con curva normale -------------------------------------------------------------------------------------------

/**
 * data: { edges: [n+1], counts: [n] }. La curva è la gaussiana con la stessa media e deviazione standard:
 * dove le colonne la superano (centro e code) i rendimenti sono «più appuntiti e con code più grasse» del caso normale.
 * Opzioni: refs: [{ value, label, cls }] linee verticali di riferimento (media, mediana, VaR…; cls: warn | crit | accent);
 * normal: false toglie la curva; unit: nome di ciò che si conta; rangeFormat: testo degli estremi nel tooltip; table: true.
 */
export function histogram(host, data, { log = false, label = 'Distribuzione', xFormat = (v) => fmtPctSigned(v, 0), refs = [], normal: withNormal = true, height = 190, unit = 'Giorni', rangeFormat = (v) => fmtPctSigned(v, 1), table = false } = {}) {
  const edges = list(data && data.edges).map(num);
  const counts = list(data && data.counts).map(num);
  const n = Math.min(counts.length, edges.length - 1);
  if (n < 2 || edges.some((e) => e == null)) return false;
  const total = counts.reduce((a, b) => a + (b || 0), 0);
  const mids = counts.map((_, i) => (edges[i] + edges[i + 1]) / 2);
  const mean = mids.reduce((a, m, i) => a + m * (counts[i] || 0), 0) / total;
  const sd = Math.sqrt(mids.reduce((a, m, i) => a + (m - mean) ** 2 * (counts[i] || 0), 0) / total);
  const normal = mids.map((m, i) => total * (edges[i + 1] - edges[i]) * Math.exp(-0.5 * ((m - mean) / sd) ** 2) / (sd * Math.sqrt(2 * Math.PI)));
  const svg = s('svg', { class: 'chart chart--static', role: 'img', 'aria-label': label });
  host.replaceChildren(svg);
  if (table) {
    host.append(tableFallback({
      caption: label, head: ['Intervallo', unit, 'Quota'],
      rows: () => counts.slice(0, n).map((c, i) => [`da ${rangeFormat(edges[i])} a ${rangeFormat(edges[i + 1])}`, fmtNum(c || 0, 0), fmtPct((c || 0) / total, 1)]),
    }).el);
  }
  let last = 0;
  function draw(width) {
    const w = Math.floor(width);
    if (w < 80 || w === last) return;
    last = w;
    svg.replaceChildren();
    const H = height;
    const T = chartTheme();
    const left = 1;
    const right = w - 44;
    const top = 8;
    const bottom = top + H;
    const max = Math.max(...counts.map((c) => c || 0), ...(withNormal ? normal : [0]));
    const f = log ? (v) => Math.log10(Math.max(v, 0.5)) : (v) => v;
    const f0 = f(log ? 0.5 : 0);
    const yOf = (v) => bottom - ((f(v) - f0) / (f(max * 1.05) - f0)) * H;
    const xOf = (e) => left + ((e - edges[0]) / (edges[n] - edges[0])) * (right - left);
    svg.setAttribute('viewBox', `0 0 ${w} ${bottom + 24}`);
    svg.setAttribute('width', w);
    svg.setAttribute('height', bottom + 24);
    const ticks = log ? [1, 10, 100, 1000].filter((v) => v <= max * 1.05) : linearTicks(0, max * 1.05, 4);
    for (const v of ticks) {
      const y = Math.round(yOf(v)) + 0.5;
      svg.append(s('line', { class: 'c-grid', x1: left, x2: right, y1: y, y2: y }));
      svg.append(s('text', { class: 'c-tick', x: right + 8, y: y + 3.5 }, fmtNum(v, 0)));
    }
    for (let i = 0; i < n; i++) {
      const c = counts[i] || 0;
      if (c <= 0) continue;
      const x0 = xOf(edges[i]);
      const x1 = xOf(edges[i + 1]);
      const y = yOf(c);
      const rect = s('rect', { class: `c-col ${mids[i] < 0 ? 'c-col--neg' : 'c-col--pos'}`, x: (x0 + 1).toFixed(1), y: y.toFixed(1), width: Math.max(1, x1 - x0 - 2).toFixed(1), height: Math.max(1, bottom - y).toFixed(1), rx: Math.min(1.5, T.barRadius), tabindex: '0' });
      bindTip(rect, () => ({
        title: `da ${rangeFormat(edges[i])} a ${rangeFormat(edges[i + 1])}`,
        rows: [{ label: unit, value: fmtNum(c, 0) }, { label: 'Quota', value: fmtPct(c / total, 1) }, withNormal ? { label: 'Attesi se normale', value: fmtNum(normal[i], 1) } : null].filter(Boolean),
      }));
      svg.append(rect);
    }
    const pts = mids.map((m, i) => [xOf(m), yOf(Math.max(normal[i], log ? 0.5 : 0))]);
    if (withNormal) svg.append(s('path', { class: 'c-line c-line--bench c-line--dash', d: pathOf(pts) }));
    svg.append(s('line', { class: 'c-axis', x1: left, x2: right, y1: bottom + 0.5, y2: bottom + 0.5 }));
    list(refs).forEach((ref, k) => {
      const v = num(ref && ref.value);
      if (v == null || v < edges[0] || v > edges[n]) return;
      const x = Math.round(xOf(v)) + 0.5;
      svg.append(s('line', { class: `c-ref c-ref--v ${ref.cls ? `c-ref--${ref.cls}` : ''}`.trim(), x1: x, x2: x, y1: top, y2: bottom }));
      if (!ref.label) return;
      const flip = x > right - 110;
      const text = s('text', { class: 'c-ref-label', x: flip ? x - 5 : x + 5, y: top + 10 + (k % 4) * 14, 'text-anchor': flip ? 'end' : null }, ref.label);
      svg.append(text);
      const box = typeof text.getBBox === 'function' ? text.getBBox() : null;
      if (box && box.width > 0) svg.insertBefore(s('rect', { class: 'c-ref-bg', x: box.x - 3, y: box.y - 1, width: box.width + 6, height: box.height + 2, rx: T.barRadius }), text);
    });
    const step = Math.max(1, Math.round(n / Math.max(2, Math.floor((right - left) / 70))));
    for (let i = 0; i <= n; i += step) {
      const x = xOf(edges[i]);
      svg.append(s('text', { class: 'c-tick c-tick--x', x: Math.min(right - 14, Math.max(left + 14, x)).toFixed(1), y: bottom + 17 }, Math.abs(edges[i]) < 1e-9 ? '0%' : xFormat(edges[i])));
    }
  }
  draw(host.clientWidth);
  onResize(host, (w) => draw(w));
  return { mean, sd, total };
}

// ---- colonne compatte con segno (ultimi giorni, ultimi mesi) ---------------------------------------------------------------

/** values: frazioni con segno; labels: testo per il tooltip di ogni colonna. Verde sopra lo zero, rosso sotto. */
export function columns(host, values, { labels = [], height = 96, label = 'Colonne', fmt = (v) => fmtPctSigned(v, 2) } = {}) {
  const vals = list(values).map(num);
  if (vals.filter((v) => v != null).length < 2) return false;
  const svg = s('svg', { class: 'chart chart--static', role: 'img', 'aria-label': label });
  host.replaceChildren(svg);
  let last = 0;
  function draw(width) {
    const w = Math.floor(width);
    if (w < 60 || w === last) return;
    last = w;
    svg.replaceChildren();
    const hi = Math.max(0, ...vals.map((v) => v ?? 0));
    const lo = Math.min(0, ...vals.map((v) => v ?? 0));
    const span = hi - lo || 1;
    const right = w - 44;
    const yOf = (v) => 4 + ((hi - v) / span) * (height - 8);
    svg.setAttribute('viewBox', `0 0 ${w} ${height}`);
    svg.setAttribute('width', w);
    svg.setAttribute('height', height);
    const bw = right / vals.length;
    for (const v of [hi, lo]) {
      if (v === 0) continue;
      const y = Math.round(yOf(v)) + 0.5;
      svg.append(s('line', { class: 'c-grid', x1: 0, x2: right, y1: y, y2: y }), s('text', { class: 'c-tick', x: right + 6, y: y + 3.5 }, fmtPctSigned(v, 1)));
    }
    const y0 = Math.round(yOf(0)) + 0.5;
    vals.forEach((v, i) => {
      if (v == null) return;
      const y = yOf(Math.max(v, 0));
      const hgt = Math.max(1, Math.abs(yOf(v) - yOf(0)));
      const rect = s('rect', { class: `c-col ${v < 0 ? 'c-col--down' : 'c-col--up'}`, x: (i * bw + 1).toFixed(1), y: y.toFixed(1), width: Math.max(1, bw - 2).toFixed(1), height: hgt.toFixed(1), rx: Math.min(chartTheme().barRadius, bw / 4) });
      bindTip(rect, () => ({ title: labels[i] || '', rows: [{ label: 'Rendimento', value: fmt(v), cls: v > 0 ? 'pos' : v < 0 ? 'neg' : '' }] }));
      svg.append(rect);
    });
    svg.append(s('line', { class: 'c-axis', x1: 0, x2: right, y1: y0, y2: y0 }));
  }
  draw(host.clientWidth);
  onResize(host, (w) => draw(w));
  return true;
}
