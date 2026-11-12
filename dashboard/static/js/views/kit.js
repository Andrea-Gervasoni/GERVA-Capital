// Attrezzi condivisi dagli spazi Evidenza, Portafoglio, Apprendimento e Sistema (design_2_grafici.md).
//   errBars      medie per fetta: barra dallo zero, baffo al 90%, n scritto su ogni riga (n < 30 attenuato e segnato «*»)
//   colHist      istogramma a colonne con lastre (zone), righe verticali piene con il valore scritto, etichetta di provenienza
//   luckChart    quanto può essere fortuna: curva teorica di una prova senza abilità, il migliore di N, lo Sharpe misurato
//   rangeBar     un intervallo contro una soglia (Deflated Sharpe)
//   yearStrip    striscia di celle anno per anno sulla rampa blu ↔ arancio, con il numero in ogni cella e il confine 2023
//   stepper      diagramma di passaggi con lo stato vivo su ogni nodo (ciclo del motore, ciclo di automiglioramento)
//   statWell, factRow, plot, legendRow, stateChip: piccoli mattoni di impaginazione
// Solo geometria e classi: colori, raggi, spessori e tratteggi stanno in css/spaces.css, sui token --chart-*.

import { bindTip, divStep, linearTicks, onResize } from '../charts.js';
import { h, icon, s } from '../dom.js';
import { SPLIT_T } from '../derive.js';
import { fmtNum, fmtSigned, num, str } from '../format.js';
import { provTag } from '../panels.js';

// ---- mattoni -------------------------------------------------------------------------------------------------------------------

/** Pozzetto con una cifra secondaria: etichetta, valore, riga sotto. */
export const statWell = (label, value, sub = '', cls = '') => h('div', { class: `well sp-well ${cls}`.trim() }, h('dt', { text: label }), h('dd', null, value), sub ? h('small', null, sub) : null);

/** Riga dei valori chiave sopra l'area di un grafico: [[etichetta, valore, classe]…]; fa da legenda minima. */
export const factRow = (pairs) => h('div', { class: 'facts sp-facts' }, pairs.filter(Boolean).map(([k, v, cls]) => h('span', null, k, h('b', { class: cls || null }, v))));

/** Area di un grafico con l'etichetta di provenienza DENTRO il tracciato (in alto a sinistra) — design_2 §3.2. */
export function plot(cls = '') {
  const host = h('div', { class: 'chart-host' });
  const tags = h('div', { class: 'sp-ptag' });
  const el = h('div', { class: `sp-plot ${cls}`.trim() }, host, tags);
  return { el, host, setTags(...list) { tags.replaceChildren(...list.filter(Boolean)); } };
}

/** Legenda: [[classe del segno, testo]…] — il segno ripete tratto e colore della serie. */
export const legendRow = (items) => h('div', { class: 'legend sp-legend' }, items.filter(Boolean).map(([key, text]) => h('span', { class: 'legend__item' }, h('span', { class: `key sp-key sp-key--${key}`, 'aria-hidden': 'true' }), text)));

const CHIP_ICON = { ok: 'check', warn: 'warn', crit: 'crit', muted: 'circle', accent: 'clock', unknown: 'help', serious: 'warn' };
/** Pastiglia di stato: colore + icona + parola, mai solo il colore. */
export const stateChip = (kind, text, { xs = true, iconName = '' } = {}) => h('span', { class: `chip chip--${kind} ${xs ? 'chip--xs' : ''}`.trim() }, icon(iconName || CHIP_ICON[kind] || 'circle'), h('span', { text }));

const textW = (node, text) => { let m = 0; try { m = node.getComputedTextLength(); } catch (err) { m = 0; } return m > 0 ? m : String(text).length * 6.2; };

// ---- medie con baffo ------------------------------------------------------------------------------------------------------------

/**
 * errBars(host, { label }) → { update({ rows: [{ label, mean, lo, hi, n, win, group }], ref: { value, label }, format, solid, minN }) }
 *   Una riga per fetta: barra dallo zero alla media (velata con contorno = simulato, piena = paper con `solid`), baffo lo–hi al 90%,
 *   punto sulla media, n nella colonna di destra. Sotto minN (30) la riga è attenuata e segnata «*».
 */
export function errBars(host, { label = 'Media per fetta' } = {}) {
  const svg = s('svg', { class: 'chart chart--static sp-eb', role: 'img', 'aria-label': label });
  host.replaceChildren(svg);
  let d = null;
  let last = 0;
  function draw(width, force = false) {
    const w = Math.floor(width);
    if (w < 140 || (w === last && !force)) return;
    last = w;
    svg.replaceChildren();
    const rows = d ? d.rows.filter((r) => num(r.mean) != null) : [];
    if (!rows.length) { svg.setAttribute('height', 0); return; }
    const format = d.format || ((v) => `${fmtSigned(v, 2)} R`);
    const minN = d.minN ?? 30;
    const rowH = 30;
    const top = 26;
    const labelW = Math.min(Math.round(w * 0.36), Math.max(64, ...rows.map((r) => String(r.label).length * 6.6 + 10)));
    const nW = 46;
    const left = labelW;
    const right = w - nW;
    const H = top + rows.length * rowH + 26;
    svg.setAttribute('viewBox', `0 0 ${w} ${H}`);
    svg.setAttribute('width', w);
    svg.setAttribute('height', H);
    let lo = Math.min(0, ...rows.map((r) => num(r.lo) ?? r.mean));
    let hi = Math.max(0, ...rows.map((r) => num(r.hi) ?? r.mean));
    if (d.ref && num(d.ref.value) != null) { lo = Math.min(lo, d.ref.value); hi = Math.max(hi, d.ref.value); }
    const pad = (hi - lo) * 0.06 || 0.1;
    lo -= pad; hi += pad;
    const xOf = (v) => left + ((v - lo) / (hi - lo)) * (right - left);
    const ticks = linearTicks(lo, hi, Math.max(2, Math.floor((right - left) / 78))).filter((v) => v >= lo && v <= hi);
    for (const v of ticks) {
      const x = Math.round(xOf(v)) + 0.5;
      svg.append(s('line', { class: v === 0 ? 'c-grid c-grid--zero' : 'c-grid', x1: x, x2: x, y1: top - 4, y2: H - 22 }), s('text', { class: 'c-tick c-tick--x', x, y: H - 7 }, v === 0 ? '0' : format(v)));
    }
    svg.append(s('text', { class: 'c-tick', x: w, y: 12, 'text-anchor': 'end' }, 'n'));
    if (d.ref && num(d.ref.value) != null) {
      const x = Math.round(xOf(d.ref.value)) + 0.5;
      const flip = x > left + (right - left) * 0.6;
      svg.append(s('line', { class: 'sp-rule', x1: x, x2: x, y1: 4, y2: H - 22 }), s('text', { class: 'c-ref-label', x: flip ? x - 5 : x + 5, y: 12, 'text-anchor': flip ? 'end' : null }, d.ref.label || ''));
    }
    let prevGroup = null;
    rows.forEach((r, i) => {
      const y = top + i * rowH;
      const cy = y + rowH / 2;
      const dim = r.n != null && r.n < minN;
      const g = s('g', { class: `sp-eb__row ${dim ? 'is-dim' : ''}`.trim() });
      if (r.group && prevGroup && r.group !== prevGroup) svg.append(s('line', { class: 'c-grid', x1: 0, x2: w, y1: y + 0.5, y2: y + 0.5 }));
      prevGroup = r.group || prevGroup;
      const x0 = xOf(0);
      const x1 = xOf(r.mean);
      g.append(s('text', { class: 'sp-eb__label', x: 0, y: cy + 4 }, String(r.label)));
      g.append(s('rect', { class: `sp-bar sp-bar--${r.mean >= 0 ? 'up' : 'down'} ${d.solid ? 'sp-bar--solid' : ''}`.trim(), x: Math.min(x0, x1).toFixed(1), y: cy - 6, width: Math.max(1, Math.abs(x1 - x0)).toFixed(1), height: 12, rx: 3 }));
      if (num(r.lo) != null && num(r.hi) != null) {
        const a = xOf(r.lo).toFixed(1);
        const b = xOf(r.hi).toFixed(1);
        g.append(s('line', { class: 'sp-whisker', x1: a, x2: b, y1: cy, y2: cy }), s('line', { class: 'sp-whisker', x1: a, x2: a, y1: cy - 5, y2: cy + 5 }), s('line', { class: 'sp-whisker', x1: b, x2: b, y1: cy - 5, y2: cy + 5 }));
      }
      g.append(s('circle', { class: 'sp-eb__dot', cx: x1.toFixed(1), cy, r: 3.5 }));
      g.append(s('text', { class: 'sp-eb__n', x: w, y: cy + 4, 'text-anchor': 'end' }, r.n == null ? 'n.d.' : `${fmtNum(r.n, 0)}${dim ? ' *' : ''}`));
      const hit = s('rect', { class: 'sp-hit', x: 0, y, width: w, height: rowH, tabindex: '0', 'aria-label': `${r.label}: ${format(r.mean)}, n ${r.n}` });
      bindTip(hit, () => ({ title: String(r.label), rows: [
        { label: 'Media', value: format(r.mean) },
        num(r.lo) != null ? { label: 'Intervallo al 90%', value: `${format(r.lo)} … ${format(r.hi)}` } : { label: 'Intervallo', value: 'non calcolabile (n = 1)' },
        { label: 'Numero di trade', value: r.n == null ? 'n.d.' : fmtNum(r.n, 0) },
        num(r.win) != null ? { label: 'Vincenti', value: `${fmtNum(r.win * 100, 0)}%` } : null].filter(Boolean),
      note: dim ? `Meno di ${minN} trade: la media è poco affidabile.` : num(r.lo) != null && r.lo <= 0 && r.hi >= 0 ? 'Il baffo attraversa lo zero: non distinguibile da nessun vantaggio.' : '' }));
      g.append(hit);
      svg.append(g);
    });
  }
  onResize(host, (w) => draw(w));
  return { update(next) { d = next; draw(host.clientWidth, true); } };
}

// ---- istogramma a colonne ---------------------------------------------------------------------------------------------------------

/**
 * colHist(host, { label }) → { update({ edges, counts, tone: (centro) => 'up' | 'down' | 'neutral', solid,
 *     zones: [{ from, to, kind: safe | warn | serious | crit }], refs: [{ value, label, sub, cls }], xFormat, unit, height,
 *     overflow: testo dell'ultima classe, xTitle, reverse: true (la perdita cresce verso destra) }) }
 *   Colonne velate con contorno = simulato; `solid` = dati veri. Le righe verticali sono piene, con il valore scritto in testa.
 */
export function colHist(host, { label = 'Distribuzione' } = {}) {
  const svg = s('svg', { class: 'chart chart--static sp-hist', role: 'img', 'aria-label': label });
  host.replaceChildren(svg);
  let d = null;
  let last = 0;
  function draw(width, force = false) {
    const w = Math.floor(width);
    if (w < 140 || (w === last && !force)) return;
    last = w;
    svg.replaceChildren();
    const edges = d ? d.edges.map(Number) : [];
    const counts = d ? d.counts.map((c) => num(c) || 0) : [];
    const total = counts.reduce((a, c) => a + c, 0);
    if (edges.length < 2 || !total) { svg.setAttribute('height', 0); return; }
    const xFormat = d.xFormat || ((v) => fmtNum(v, 1));
    const refs = (d.refs || []).filter((r) => num(r.value) != null);
    const gutter = 42;
    const left = 1;
    const right = w - gutter;
    const lo = edges[0];
    const hi = edges[edges.length - 1];
    const xOf = (v) => (d.reverse ? right - ((v - lo) / (hi - lo)) * (right - left) : left + ((v - lo) / (hi - lo)) * (right - left));
    // etichette delle righe di riferimento: ognuna sulla prima riga libera sopra l'area, mai sovrapposte né tagliate
    const labels = refs.map((r) => ({ r, x: xOf(Math.max(lo, Math.min(hi, r.value))), text: r.label || '' })).sort((a, b) => a.x - b.x);
    const rowsEnd = [];
    for (const l of labels) {
      const probe = s('text', { class: 'c-ref-label sp-ref-label' }, l.text);
      svg.append(probe);
      l.tw = Math.max(textW(probe, l.text), l.r.sub ? String(l.r.sub).length * 6 : 0);
      probe.remove();
      l.flip = l.r.side === 'left' ? l.x - 6 - l.tw > left : l.x + 6 + l.tw > right;
      const x0 = l.flip ? l.x - 6 - l.tw : l.x + 6;
      let row = 0;
      while (rowsEnd[row] != null && rowsEnd[row] > x0 - 8) row++;
      rowsEnd[row] = x0 + l.tw;
      l.row = row;
    }
    const lines = Math.max(1, rowsEnd.length);
    const rowHt = labels.some((l) => l.r.sub) ? 28 : 15;
    const top = 6 + lines * rowHt;
    const ph = d.height || 170;
    const bottom = top + ph;
    const H = bottom + (d.xTitle ? 40 : 24);
    svg.setAttribute('viewBox', `0 0 ${w} ${H}`);
    svg.setAttribute('width', w);
    svg.setAttribute('height', H);
    const max = Math.max(...counts);
    const share = (c) => c / total;
    const yTicks = linearTicks(0, share(max), 3).filter((v) => v <= share(max) * 1.02);
    const yOf = (v) => bottom - (v / (share(max) * 1.06)) * ph;
    for (const z of d.zones || []) {
      const a = xOf(Math.max(lo, Math.min(hi, z.from)));
      const b = xOf(Math.max(lo, Math.min(hi, z.to)));
      if (Math.abs(b - a) < 1) continue;
      svg.append(s('rect', { class: `sp-zone sp-zone--${z.kind}`, x: Math.min(a, b).toFixed(1), y: top, width: Math.abs(b - a).toFixed(1), height: ph }), s('line', { class: 'c-slab-edge', x1: Math.min(a, b).toFixed(1), x2: Math.max(a, b).toFixed(1), y1: top + 0.5, y2: top + 0.5 }));
    }
    for (const v of yTicks) {
      const y = Math.round(yOf(v)) + 0.5;
      svg.append(s('line', { class: v === 0 ? 'c-grid c-grid--zero' : 'c-grid', x1: left, x2: right, y1: y, y2: y }), s('text', { class: 'c-tick', x: right + 8, y: y + 3.5 }, v === 0 ? '0' : `${fmtNum(v * 100, v < 0.1 ? 1 : 0, 0)}%`));
    }
    const bars = s('g', { class: 'sp-cols' });
    counts.forEach((c, i) => {
      if (!c) return;
      const a = xOf(edges[i]);
      const b = xOf(edges[i + 1]);
      const x = Math.min(a, b) + 1;
      const bw = Math.max(1, Math.abs(b - a) - 2);
      const y = yOf(share(c));
      const mid = (edges[i] + edges[i + 1]) / 2;
      const tone = d.tone ? d.tone(mid) : 'neutral';
      const over = d.overflow && i === counts.length - 1;
      const rect = s('rect', { class: `sp-bar sp-bar--${tone} ${d.solid ? 'sp-bar--solid' : ''}`.trim(), x: x.toFixed(1), y: y.toFixed(1), width: bw.toFixed(1), height: Math.max(1, bottom - y).toFixed(1), rx: Math.min(3, bw / 2), tabindex: '0',
        'aria-label': `${over ? d.overflow : `da ${xFormat(edges[i])} a ${xFormat(edges[i + 1])}`}: ${fmtNum(c, 0)} ${d.unit || 'casi'}` });
      rect.style.setProperty('--i', String(i));
      bindTip(rect, () => ({ title: over ? d.overflow : `da ${xFormat(edges[i])} a ${xFormat(edges[i + 1])}`, rows: [{ label: d.unit || 'Casi', value: fmtNum(c, 0) }, { label: 'Quota', value: `${fmtNum(share(c) * 100, 1)}%` }] }));
      bars.append(rect);
    });
    svg.append(bars);
    svg.append(s('line', { class: 'c-axis', x1: left, x2: right, y1: bottom + 0.5, y2: bottom + 0.5 }));
    const every = Math.max(1, Math.ceil((edges.length - 1) / Math.max(2, Math.floor((right - left) / 64))));
    for (let i = edges.length - 1; i >= 0; i -= every) {
      const x = xOf(edges[i]);
      const edge = x < left + 16 ? 'start' : x > right - 16 ? 'end' : null;
      svg.append(s('line', { class: 'c-axis', x1: Math.round(x) + 0.5, x2: Math.round(x) + 0.5, y1: bottom, y2: bottom + 4 }),
        s('text', { class: 'c-tick c-tick--x', x: x.toFixed(1), y: bottom + 17, 'text-anchor': edge }, d.overflow && i === edges.length - 1 ? '' : xFormat(edges[i])));
    }
    if (d.xTitle) svg.append(s('text', { class: 'c-tick', x: right, y: H - 6, 'text-anchor': 'end' }, d.xTitle));
    for (const l of labels) {
      const x = Math.round(l.x) + 0.5;
      const y = 6 + (lines - 1 - l.row) * rowHt + 10;
      svg.append(s('line', { class: `sp-rule ${l.r.cls ? `sp-rule--${l.r.cls}` : ''}`.trim(), x1: x, x2: x, y1: y - 9, y2: bottom }),
        s('text', { class: 'c-ref-label sp-ref-label', x: l.flip ? x - 6 : x + 6, y, 'text-anchor': l.flip ? 'end' : null }, l.text),
        l.r.sub ? s('text', { class: 'c-tick sp-ref-sub', x: l.flip ? x - 6 : x + 6, y: y + 13, 'text-anchor': l.flip ? 'end' : null }, l.r.sub) : null);
    }
    if (!svg.dataset.drawn) { svg.dataset.drawn = '1'; svg.classList.add('is-new'); svg.addEventListener('animationend', () => svg.classList.remove('is-new'), { once: true }); }
  }
  onResize(host, (w) => draw(w));
  return { update(next) { d = next; draw(host.clientWidth, true); } };
}

// ---- quanto può essere fortuna ---------------------------------------------------------------------------------------------------

/**
 * luckChart(host) → { update({ se, expectedMax, trials, marks: [{ value, label, se, ring }] }) }
 *   Curva: Sharpe di UNA prova senza abilità (normale di media zero e deviazione `se`, teorica e dichiarata). Riga piena: lo Sharpe
 *   atteso dal migliore di N. Segni: gli Sharpe misurati, con il baffo di ±1 errore standard (anello = periodo di verifica).
 */
export function luckChart(host, { label = 'Quanto può essere fortuna' } = {}) {
  const svg = s('svg', { class: 'chart chart--static sp-luck', role: 'img', 'aria-label': label });
  host.replaceChildren(svg);
  let d = null;
  let last = 0;
  function draw(width, force = false) {
    const w = Math.floor(width);
    if (w < 140 || (w === last && !force)) return;
    last = w;
    svg.replaceChildren();
    if (!d || !num(d.se) || num(d.expectedMax) == null) { svg.setAttribute('height', 0); return; }
    const marks = (d.marks || []).filter((m) => num(m.value) != null);
    const lo = -3 * d.se;
    const hi = Math.max(d.expectedMax + 1.2 * d.se, ...marks.map((m) => m.value + (m.se || 0) + 0.25));
    const left = 2;
    const right = w - 2;
    const top = 22;
    const ph = 108;
    const bottom = top + ph;
    const H = bottom + 22;
    svg.setAttribute('viewBox', `0 0 ${w} ${H}`);
    svg.setAttribute('width', w);
    svg.setAttribute('height', H);
    const xOf = (v) => left + ((v - lo) / (hi - lo)) * (right - left);
    const pdf = (v) => Math.exp(-0.5 * (v / d.se) ** 2);
    const pts = Array.from({ length: 81 }, (_, i) => { const v = lo + (i / 80) * (Math.min(hi, 3.4 * d.se) - lo); return [xOf(v), bottom - pdf(v) * (ph - 8)]; });
    const path = `M${pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join('L')}`;
    svg.append(s('path', { class: 'sp-luck__area', d: `${path}L${pts[pts.length - 1][0].toFixed(1)},${bottom}L${pts[0][0].toFixed(1)},${bottom}Z` }), s('path', { class: 'sp-luck__curve', d: path }));
    svg.append(s('line', { class: 'c-axis', x1: left, x2: right, y1: bottom + 0.5, y2: bottom + 0.5 }));
    for (let v = Math.ceil(lo * 2) / 2; v <= hi; v += 0.5) {
      const x = xOf(v);
      svg.append(s('line', { class: 'c-axis', x1: Math.round(x) + 0.5, x2: Math.round(x) + 0.5, y1: bottom, y2: bottom + 4 }));
      if (Number.isInteger(v) && x > left + 12 && x < right - 70) svg.append(s('text', { class: 'c-tick c-tick--x', x: x.toFixed(1), y: bottom + 17 }, fmtNum(v, 0)));
    }
    svg.append(s('text', { class: 'c-tick', x: right, y: bottom + 17, 'text-anchor': 'end' }, 'Sharpe →'));
    svg.append(s('text', { class: 'c-tick', x: xOf(0), y: bottom - ph * 0.36, 'text-anchor': 'middle' }, 'una prova'), s('text', { class: 'c-tick', x: xOf(0), y: bottom - ph * 0.36 + 13, 'text-anchor': 'middle' }, 'senza abilità'));
    const xm = Math.round(xOf(d.expectedMax)) + 0.5;
    svg.append(s('line', { class: 'sp-rule sp-rule--strong', x1: xm, x2: xm, y1: 14, y2: bottom }),
      s('text', { class: 'c-ref-label sp-ref-label', x: xm - 6, y: 12, 'text-anchor': 'end' }, `il migliore di ${fmtNum(d.trials, 0)} a caso: ${fmtNum(d.expectedMax, 2)}`));
    marks.forEach((m, i) => {
      const y = top + 30 + i * 30;
      const x = xOf(m.value);
      if (m.se) {
        const a = xOf(m.value - m.se).toFixed(1);
        const b = xOf(m.value + m.se).toFixed(1);
        svg.append(s('line', { class: 'sp-whisker', x1: a, x2: b, y1: y, y2: y }), s('line', { class: 'sp-whisker', x1: a, x2: a, y1: y - 5, y2: y + 5 }), s('line', { class: 'sp-whisker', x1: b, x2: b, y1: y - 5, y2: y + 5 }));
      }
      svg.append(s('circle', { class: `sp-luck__mark ${m.ring ? 'sp-luck__mark--ring' : ''}`.trim(), cx: x.toFixed(1), cy: y, r: 5 }));
      const text = `${m.label} ${fmtNum(m.value, 2)}${m.se ? ` ± ${fmtNum(m.se, 2)}` : ''}`;
      const node = s('text', { class: 'c-ref-label sp-ref-label' }, text);
      svg.append(node);
      const tw = textW(node, text);
      const tx = Math.min(right - tw, Math.max(left, x - tw / 2));
      node.setAttribute('x', tx.toFixed(1));
      node.setAttribute('y', y - 10);
    });
  }
  onResize(host, (w) => draw(w));
  return { update(next) { d = next; draw(host.clientWidth, true); } };
}

/** Un intervallo lo–hi su una scala min…max, con la tacca della soglia: tutto scritto, il colore non è l'unico segno. */
export function rangeBar({ lo, hi, threshold, min = 0, max = 1, label = '', format = (v) => fmtNum(v, 2) }) {
  const bar = h('div', { class: 'sp-range', role: 'img', 'aria-label': `${label}: da ${format(lo)} a ${format(hi)}${threshold == null ? '' : `, soglia ${format(threshold)}`}` }, h('i'), threshold == null ? null : h('b'));
  const pos = (v) => `${Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100)).toFixed(1)}%`;
  bar.style.setProperty('--a', pos(lo));
  bar.style.setProperty('--b', pos(hi));
  if (threshold != null) bar.style.setProperty('--t', pos(threshold));
  bar.dataset.state = threshold == null ? 'none' : lo >= threshold ? 'ok' : 'warn';
  return h('div', { class: 'sp-rangebox' }, bar,
    h('div', { class: 'sp-range__scale num' }, h('span', { text: format(min) }), threshold == null ? null : h('span', { class: 'sp-range__thr', text: `soglia ${format(threshold)}` }), h('span', { text: format(max) })));
}

// ---- striscia per anno --------------------------------------------------------------------------------------------------------------

/** Celle anno per anno (rampa blu ↔ arancio, numero in ogni cella); uno stacco segna il confine scelta | verifica. `scale` = valore a tinta piena. */
export function yearStrip(byYear, { scale = 2, digits = 1, name = 'Sharpe' } = {}) {
  const split = new Date(SPLIT_T).getUTCFullYear();
  const years = Object.keys(byYear || {}).map(Number).filter((y) => Number.isFinite(y)).sort((a, b) => a - b);
  if (!years.length) return h('span', { class: 'sp-nd', text: 'n.d.' });
  return h('span', { class: 'sp-years', role: 'img', 'aria-label': `${name} per anno: ${years.map((y) => `${y} ${fmtSigned(byYear[y], digits)}`).join(', ')}` }, years.map((y) => {
    const v = num(byYear[y]);
    const cell = h('span', { class: `hm__cell sp-years__cell ${y === split ? 'is-split' : ''}`.trim(), dataset: v == null ? {} : { step: divStep(Math.max(-1, Math.min(1, v / scale))) }, text: v == null ? '·' : Math.abs(v) >= 10 ? fmtSigned(v, 0) : fmtSigned(v, digits) });
    bindTip(cell, () => ({ title: `${y} · ${y >= split ? 'verifica' : 'scelta'}`, rows: [{ label: name, value: v == null ? 'n.d.' : fmtSigned(v, 2) }] }));
    return cell;
  }));
}

// ---- diagramma a passaggi con stato vivo ---------------------------------------------------------------------------------------------

/**
 * stepper(steps, { label }) → elemento. steps: [{ n, title, sub, live, state: ok | warn | crit | unknown | idle, word, guard, text }]
 *   Ogni nodo: numero, titolo, che cosa fa (sub), il dato vivo (live) e lo stato a parole. `guard` = passaggio che può solo frenare
 *   o in cui decide qualcun altro (bordo tratteggiato). `text` = spiegazione lunga, mostrata solo in Semplice.
 */
export function stepper(steps, { label = 'Diagramma dei passaggi' } = {}) {
  return h('ol', { class: 'sp-steps', 'aria-label': label }, steps.map((st, i) => h('li', { class: `sp-step ${st.guard ? 'sp-step--guard' : ''}`.trim(), dataset: { state: st.state || 'idle' } },
    h('div', { class: 'sp-step__head' }, h('span', { class: 'sp-step__n num', text: String(st.n ?? i + 1) }), h('span', { class: 'sp-step__title', text: st.title })),
    h('div', { class: 'sp-step__sub', text: st.sub || '' }),
    st.live != null ? h('div', { class: 'sp-step__live num' }, h('i', { class: 'sp-dot', 'aria-hidden': 'true' }), h('span', null, st.live)) : null,
    st.word ? h('div', { class: 'sp-step__word', text: st.word }) : null,
    st.text ? h('p', { class: 'sp-step__text only-semplice', text: st.text }) : null)));
}

/** Provenienza di un blocco di ricerca: sempre SIMULATO; il nome del file sta nel piede. */
export const simTag = (text = '') => provTag('sim', text);
export const nd = (text = 'n.d.') => h('span', { class: 'sp-nd', text: str(text) });

/**
 * Tabella semplice dentro un riquadro: cols: [{ label, cls, cell: (riga) => nodo | testo, head: nodo facoltativo }].
 * `mark(riga)` evidenzia la riga; le classi di livello (not-semplice…) valgono per intestazione e celle insieme.
 */
export function simpleTable(caption, cols, rows, { mark = null, cls = '' } = {}) {
  return h('div', { class: 'table-wrap' }, h('table', { class: `table table--dense sp-table ${cls}`.trim() },
    h('caption', { class: 'sr-only', text: caption }),
    h('thead', null, h('tr', null, cols.map((c) => h('th', { scope: 'col', class: c.cls || null }, c.head || c.label)))),
    h('tbody', null, rows.map((r) => h('tr', { class: mark && mark(r) ? 'is-marked' : null }, cols.map((c, i) => {
      const v = c.cell(r);
      return h(i === 0 ? 'th' : 'td', { class: c.cls || null, scope: i === 0 ? 'row' : null }, v == null || v === '' ? nd() : v);
    }))))));
}

/**
 * sparkArea(host, { label }) → { update({ values, prov }) } — andamento compatto con area sfumata e punto finale.
 * Il colore segue il segno della variazione (con freccia e cifra accanto, mai da solo); prov 'demo' = puntinato, 'sim' = tratteggiato;
 * anello finale = paper, pieno = reale.
 */
export function sparkArea(host, { label = 'Andamento', height = 54 } = {}) {
  const svg = s('svg', { class: 'chart chart--static sp-spark', role: 'img', 'aria-label': label });
  host.replaceChildren(svg);
  let d = null;
  let last = 0;
  function draw(width, force = false) {
    const w = Math.floor(width);
    if (w < 60 || (w === last && !force)) return;
    last = w;
    svg.replaceChildren();
    const v = d ? d.values.map(num).filter((x) => x != null) : [];
    if (v.length < 2) { svg.setAttribute('height', 0); return; }
    svg.setAttribute('viewBox', `0 0 ${w} ${height}`);
    svg.setAttribute('width', w);
    svg.setAttribute('height', height);
    const lo = Math.min(...v);
    const hi = Math.max(...v);
    const span = hi - lo || 1;
    const xOf = (i) => 2 + (i / (v.length - 1)) * (w - 10);
    const yOf = (y) => 6 + (1 - (y - lo) / span) * (height - 14);
    const tone = v[v.length - 1] >= v[0] ? 'up' : 'down';
    const path = `M${v.map((y, i) => `${xOf(i).toFixed(1)},${yOf(y).toFixed(1)}`).join('L')}`;
    const y0 = Math.round(yOf(v[0])) + 0.5;
    svg.append(s('line', { class: 'c-grid', x1: 2, x2: w - 8, y1: y0, y2: y0 }),
      s('path', { class: `sp-spark__area sp-spark__area--${tone}`, d: `${path}L${xOf(v.length - 1).toFixed(1)},${height}L${xOf(0).toFixed(1)},${height}Z` }),
      s('path', { class: `sp-spark__line sp-spark__line--${tone} ${d.prov || ''}`.trim(), d: path }),
      s('circle', { class: `sp-spark__end sp-spark__end--${tone} ${d.prov === 'real' ? 'is-real' : ''}`.trim(), cx: xOf(v.length - 1).toFixed(1), cy: yOf(v[v.length - 1]).toFixed(1), r: 4 }));
  }
  onResize(host, (w) => draw(w));
  return { update(next) { d = next; draw(host.clientWidth, true); } };
}
