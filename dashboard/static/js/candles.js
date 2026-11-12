// Grafico a candele su canvas: prezzo con volume, sovrapposizioni attivabili e pannelli sotto (ATR%, RSI, conviction, GQ).
// Canvas perché deve restare fluido trascinando e zoomando 1.500 barre; un solo disegno per fotogramma.
// Mouse: rotella = zoom, trascinamento = scorrimento, doppio clic = tutto. Tastiera: ←/→ mirino, Maiusc+←/→ scorre,
// +/− zoom, Inizio/Fine, Esc. Nessun colore, spessore o carattere è scritto qui: tutto arriva da chartTheme()
// (token CSS --chart-*), che si rilegge da solo al cambio di tema o di livello.
//
// candleChart(host, { label, panes, overlays, table }) → {
//   setData(data, { keepView, months }), setOverlays(ids), setPanes(ids), setLog(on), setRange(mesi | null), redraw(), view,
//   onHover(fn(t | null, i)), setHoverTime(t), setWindow(t0, t1), onWindow(fn([t0, t1])), destroy() }
// data: { symbol, t: [ms], o, h, l, c, v, conviction, gq, thresholds: { conviction: [a, b], gq: [a, b, c] },
//         markers: [{ i, price, kind: 'entry' | 'exit' | 'stop' | 'level', label, color: chiave del tema }] }

import { chartTheme, onChartThemeChange } from './chart-theme.js';
import { tableFallback } from './charts.js';
import { h } from './dom.js';
import { fmtDate, fmtNum, fmtPct, fmtPctSigned } from './format.js';
import { atrPct, bollinger, donchian, ema, rsi, sma, vwapMonth } from './indicators.js';

/** Sovrapposizioni disponibili; color è una chiave dell'oggetto del tema (chartTheme()). */
export const OVERLAYS = [
  { id: 'sma20', label: 'SMA 20', color: 's2' }, { id: 'sma50', label: 'SMA 50', color: 's3' },
  { id: 'sma100', label: 'SMA 100', color: 's4' }, { id: 'sma200', label: 'SMA 200', color: 's5' },
  { id: 'ema21', label: 'EMA 21', color: 'textSoft' }, { id: 'boll', label: 'Bollinger', color: 'bench' },
  { id: 'vwap', label: 'VWAP mese', color: 'accent' }, { id: 'donch', label: 'Donchian 20', color: 'textMuted' },
];
/** Pannelli sotto il prezzo (il volume c'è sempre). */
export const PANES = [
  { id: 'atr', title: 'ATR% 14' }, { id: 'rsi', title: 'RSI 14' }, { id: 'conv', title: 'CONVICTION' }, { id: 'gq', title: 'GQ · IN OMBRA' },
];
const AXIS = 18;
const DAY = 86400000;

const price = (v) => (v == null ? '—' : fmtNum(v, Math.abs(v) >= 1000 ? 0 : Math.abs(v) >= 10 ? 2 : 4));
const compact = (v) => (v == null ? '—' : v >= 1e9 ? `${fmtNum(v / 1e9, 2)} Mld` : v >= 1e6 ? `${fmtNum(v / 1e6, 1)} M` : v >= 1e3 ? `${fmtNum(v / 1e3, 1)} k` : fmtNum(v, 0));

function niceTicks(lo, hi, count) {
  const raw = (hi - lo) / Math.max(1, count);
  if (!(raw > 0)) return [lo];
  const p = 10 ** Math.floor(Math.log10(raw));
  const f = raw / p;
  const step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(Number(v.toPrecision(12)));
  return out;
}

export function candleChart(host, { label = 'Grafico a candele', panes: paneIds = PANES.map((p) => p.id), overlays: overlayIds = ['sma50', 'sma200'], table = false } = {}) {
  const read = h('div', { class: 'cx__read num', 'aria-hidden': 'true' });
  const canvas = h('canvas', { class: 'cx__canvas', tabindex: '0', role: 'img', 'aria-label': label });
  const live = h('div', { class: 'sr-only', 'aria-live': 'polite' });
  const wrap = h('div', { class: 'cx' }, read, h('div', { class: 'cx__plot' }, canvas), live);
  host.append(wrap);
  const fallback = table ? tableFallback({
    caption: label, head: ['Data', 'Apertura', 'Massimo', 'Minimo', 'Chiusura', 'Volume', 'Conviction', 'GQ'],
    rows: () => {
      if (!d) return [];
      const out = [];
      for (let i = Math.max(0, Math.floor(i0)); i <= Math.min(d.t.length - 1, Math.ceil(i1)); i++) {
        out.push([fmtDate(d.t[i], true), price(d.o[i]), price(d.h[i]), price(d.l[i]), price(d.c[i]), compact(d.v[i]),
          d.conviction && d.conviction[i] != null ? fmtNum(d.conviction[i], 2) : null, d.gq && d.gq[i] != null ? fmtNum(d.gq[i], 2) : null]);
      }
      return out;
    },
  }) : null;
  if (fallback) wrap.append(fallback.el);
  const plot = canvas.parentElement;
  const ctx = canvas.getContext('2d');

  let d = null;                 // dati correnti
  let ind = {};                 // indicatori calcolati una volta per serie
  let i0 = 0;                   // finestra visibile (indici, anche frazionari)
  let i1 = 0;
  let hover = null;
  let hoverY = null;
  let log = false;
  let overlays = new Set(overlayIds);
  let subPanes = new Set(paneIds);
  let theme = null;
  let lastA = -1;
  let lastB = -1;
  let silentWin = false;
  const hoverSubs = new Set();
  const winSubs = new Set();
  let W = 0;
  let H = 0;
  let queued = false;
  let drag = null;
  let geo = null;

  function setHover(i, y = null) {
    const changed = hover !== i;
    hover = i;
    hoverY = y;
    if (changed) for (const fn of hoverSubs) fn(i == null || !d ? null : d.t[i], i);
  }

  function resize() {
    const r = plot.getBoundingClientRect();
    const w = Math.floor(r.width);
    const hh = Math.floor(r.height);
    if (w < 40 || hh < 40) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (w !== W || hh !== H || canvas.width !== Math.round(w * dpr)) {
      W = w;
      H = hh;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(hh * dpr);
      canvas.style.setProperty('width', `${w}px`);
      canvas.style.setProperty('height', `${hh}px`);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    request();
  }

  function request() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; draw(); });
  }

  function compute() {
    const { t, h: hi, l: lo, c, v } = d;
    ind = {
      sma20: sma(c, 20), sma50: sma(c, 50), sma100: sma(c, 100), sma200: sma(c, 200), ema21: ema(c, 21),
      boll: bollinger(c, 20, 2), vwap: vwapMonth(t, hi, lo, c, v), donch: donchian(hi, lo, 20), atr: atrPct(hi, lo, c, 14), rsi: rsi(c, 14),
    };
  }

  function panes() {
    const subs = PANES.filter((p) => subPanes.has(p.id) && (p.id !== 'conv' || d.conviction) && (p.id !== 'gq' || d.gq));
    const avail = H - AXIS;
    const subH = Math.max(34, Math.min(62, Math.floor(avail * 0.105)));
    const use = avail < 260 ? [] : avail < 380 ? subs.slice(-Math.min(subs.length, 2)) : subs;
    const volH = Math.max(30, Math.min(56, Math.floor(avail * 0.11)));
    let y = avail - use.length * subH;
    const out = [{ id: 'price', y0: 4, y1: y - volH - 2 }, { id: 'vol', title: 'VOLUME', y0: y - volH, y1: y }];
    for (const sp of use) { out.push({ ...sp, y0: y + 2, y1: y + subH }); y += subH; }
    return out;
  }

  function draw() {
    theme = chartTheme();
    const GUTTER = theme.gutter;
    ctx.clearRect(0, 0, W, H);
    geo = null;
    if (!d || d.t.length < 2 || W < 80) return;
    const n = d.t.length;
    const a = Math.max(0, Math.floor(i0));
    const b = Math.min(n - 1, Math.ceil(i1));
    const plotW = W - GUTTER;
    const bw = plotW / Math.max(1, i1 - i0 + 1);
    const xOf = (i) => (i - i0 + 0.5) * bw;
    const ps = panes();
    ctx.font = theme.canvasFont;
    ctx.textBaseline = 'middle';
    ctx.lineWidth = theme.gridWidth;

    const scale = (p, lo, hi, isLog = false) => {
      const f = isLog ? Math.log : (x) => x;
      const A = f(lo);
      const B = f(hi) - A || 1;
      p.yOf = (v) => p.y1 - ((f(v) - A) / B) * (p.y1 - p.y0);
      p.vOf = (y) => { const u = A + ((p.y1 - y) / (p.y1 - p.y0)) * B; return isLog ? Math.exp(u) : u; };
      p.lo = lo;
      p.hi = hi;
    };
    const line = (p, arr, color, { dash = null, width = theme.lineWidthThin * 0.85, step = false } = {}) => {
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, p.y0 - 1, plotW, p.y1 - p.y0 + 2);
      ctx.clip();
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      if (dash) ctx.setLineDash(dash);
      ctx.beginPath();
      let pen = false;
      let py = 0;
      for (let i = Math.max(0, a - 1); i <= Math.min(n - 1, b + 1); i++) {
        const v = arr[i];
        if (v == null) { pen = false; continue; }
        const x = xOf(i);
        const y = p.yOf(v);
        if (!pen) ctx.moveTo(x, y);
        else { if (step) ctx.lineTo(x, py); ctx.lineTo(x, y); }
        pen = true;
        py = y;
      }
      ctx.stroke();
      ctx.restore();
    };
    const grid = (p, ticks, fmt) => {
      ctx.strokeStyle = theme.grid;
      ctx.fillStyle = theme.textMuted;
      ctx.textAlign = 'left';
      let lastY = null;
      for (const v of ticks) {
        const y = Math.round(p.yOf(v)) + 0.5;
        if (y < p.y0 - 1 || y > p.y1 + 1) continue;
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(plotW, y); ctx.stroke();
        if (lastY != null && Math.abs(y - lastY) < theme.fontSize + 1) continue;      // etichette troppo vicine: resta la prima
        lastY = y;
        ctx.fillText(fmt(v), plotW + 6, y);
      }
    };
    const title = (p) => {
      if (!p.title) return;
      ctx.fillStyle = theme.textMuted;
      ctx.textAlign = 'left';
      ctx.fillText(p.title, 4, p.y0 + 7);
    };
    const band = (p, lo, hi, color, alpha) => {
      const y0 = Math.max(p.y0, Math.min(p.y1, p.yOf(hi)));
      const y1 = Math.max(p.y0, Math.min(p.y1, p.yOf(lo)));
      ctx.globalAlpha = alpha;
      ctx.fillStyle = color;
      ctx.fillRect(0, y0, plotW, y1 - y0);
      ctx.globalAlpha = 1;
    };

    // ---- prezzo ----
    const pp = ps[0];
    let lo = Infinity;
    let hi = -Infinity;
    for (let i = a; i <= b; i++) {
      if (d.l[i] != null && d.l[i] < lo) lo = d.l[i];
      if (d.h[i] != null && d.h[i] > hi) hi = d.h[i];
    }
    for (const m of d.markers || []) if (m.kind === 'level' && !m.past && m.price > 0) { if (m.price < lo) lo = m.price; if (m.price > hi) hi = m.price; }
    if (!(hi > lo)) { hi = lo + 1; }
    const useLog = log && lo > 0;
    const pad = useLog ? 1 : (hi - lo) * 0.06;
    scale(pp, useLog ? lo / (hi / lo) ** 0.05 : lo - pad, useLog ? hi * (hi / lo) ** 0.05 : hi + pad, useLog);
    const pticks = useLog
      ? [1, 2, 5].flatMap((m) => Array.from({ length: 12 }, (_, k) => m * 10 ** (k - 4))).filter((v) => v >= pp.lo && v <= pp.hi).sort((x, y) => x - y)
      : niceTicks(pp.lo, pp.hi, Math.max(3, Math.floor((pp.y1 - pp.y0) / 44)));
    const levelYs = (d.markers || []).filter((m) => m.kind === 'level').map((m) => pp.yOf(m.price));
    grid(pp, pticks.length >= 2 ? pticks : niceTicks(pp.lo, pp.hi, 4), (v) => (levelYs.some((y) => Math.abs(y - pp.yOf(v)) < 12) ? '' : price(v)));

    if (overlays.has('boll')) {
      ctx.save();
      ctx.beginPath(); ctx.rect(0, pp.y0, plotW, pp.y1 - pp.y0); ctx.clip();
      ctx.beginPath();
      let started = false;
      for (let i = a; i <= b; i++) { if (ind.boll.up[i] == null) continue; const x = xOf(i); const y = pp.yOf(ind.boll.up[i]); if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y); }
      for (let i = b; i >= a; i--) { if (ind.boll.lo[i] == null) continue; ctx.lineTo(xOf(i), pp.yOf(ind.boll.lo[i])); }
      ctx.closePath();
      ctx.globalAlpha = theme.areaOpacity; ctx.fillStyle = theme.bench; ctx.fill(); ctx.globalAlpha = 1;
      ctx.restore();
      line(pp, ind.boll.up, theme.bench);
      line(pp, ind.boll.lo, theme.bench);
    }
    if (overlays.has('donch')) { line(pp, ind.donch.up, theme.textMuted, { step: true, dash: theme.dashCross }); line(pp, ind.donch.lo, theme.textMuted, { step: true, dash: theme.dashCross }); }

    // candele
    const body = Math.max(1, Math.min(theme.candleMax, Math.floor(bw * theme.candleBody)));
    for (let i = a; i <= b; i++) {
      const o = d.o[i]; const c = d.c[i]; const hh = d.h[i]; const ll = d.l[i];
      if (o == null || c == null || hh == null || ll == null) continue;
      const x = Math.round(xOf(i));
      const up = c >= o;
      ctx.fillStyle = up ? theme.up : theme.down;
      const y0 = pp.yOf(Math.max(o, c));
      const bh = Math.max(1, pp.yOf(Math.min(o, c)) - y0);
      if (up && theme.candleHollow && body >= 4 && bh >= 3) {       // vuota su, piena giù: la direzione non è affidata al solo colore
        ctx.fillRect(x, pp.yOf(hh), 1, Math.max(0, y0 - pp.yOf(hh)));
        ctx.fillRect(x, y0 + bh, 1, Math.max(0, pp.yOf(ll) - y0 - bh));
        ctx.strokeStyle = theme.up;
        ctx.strokeRect(x - Math.floor(body / 2) + 0.5, Math.round(y0) + 0.5, body - 1, Math.round(bh) - 1);
      } else {
        ctx.fillRect(x, pp.yOf(hh), 1, Math.max(1, pp.yOf(ll) - pp.yOf(hh)));
        ctx.fillRect(x - Math.floor(body / 2), y0, body, bh);
      }
    }
    for (const ov of OVERLAYS) {
      if (!overlays.has(ov.id) || ov.id === 'boll' || ov.id === 'donch') continue;
      line(pp, ind[ov.id], theme[ov.color], ov.id === 'vwap' ? { dash: theme.dashRef, width: theme.lineWidthThin } : {});
    }

    // righello del trade: zona entrata–stop (lastra «1 R»), livelli pieni con cartellino sul righello di destra,
    // stop iniziale puntinato (non più attivo), trade passati come anello → rombo con R. Il tratteggio resta al simulato.
    const tags = [];
    const exits = (d.markers || []).filter((m) => m.kind === 'exit' && m.i >= a && m.i <= b).length;
    ctx.save();
    ctx.beginPath(); ctx.rect(0, pp.y0, plotW, pp.y1 - pp.y0); ctx.clip();
    for (const m of d.markers || []) {
      if (m.kind === 'rscale') {                                 // scala in R accanto al righello: entrata = 0 R, stop iniziale = −1 R
        ctx.fillStyle = theme.textMuted; ctx.textAlign = 'left';                     // a sinistra: a destra stanno i cartellini dei livelli
        let lastY = 1e9;
        for (let k = -1; k <= 6; k++) { const y = pp.yOf(m.entry + k * m.dist); if (y > pp.y0 + 6 && y < pp.y1 - 6 && lastY - y >= 13) { ctx.fillText(`${k > 0 ? '+' : k < 0 ? '−' : ''}${Math.abs(k)} R`, 4, y); lastY = y; } }
        continue;
      }
      const idx = m.i;
      if (m.kind === 'zone') {
        const ya = pp.yOf(Math.max(m.from, m.to));
        const yb = pp.yOf(Math.min(m.from, m.to));
        const x0 = Math.max(0, xOf(Math.max(idx, a)) - bw / 2);
        if (yb < pp.y0 || ya > pp.y1 || x0 >= plotW) continue;
        const top = Math.max(pp.y0, ya);
        ctx.fillStyle = theme.slab;
        ctx.fillRect(x0, top, plotW - x0, Math.min(pp.y1, yb) - top);
        ctx.strokeStyle = theme.slabEdge;
        ctx.beginPath(); ctx.moveTo(x0, Math.round(top) + 0.5); ctx.lineTo(plotW, Math.round(top) + 0.5); ctx.stroke();
        if (m.label) { ctx.fillStyle = theme.textMuted; ctx.textAlign = 'left'; ctx.fillText(m.label, x0 + 6, top + 9); }
        continue;
      }
      if (m.kind === 'level') {
        const y = Math.round(pp.yOf(m.price)) + 0.5;
        if (y < pp.y0 || y > pp.y1) continue;
        const x0 = Math.max(0, xOf(Math.max(idx, a)));
        const color = theme[m.color] || theme.text;
        ctx.strokeStyle = color;
        ctx.lineWidth = theme.lineWidthThin * 0.85;
        ctx.setLineDash(m.past ? theme.dashPast : []);
        ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(plotW, y); ctx.stroke();
        ctx.setLineDash([]);
        ctx.lineWidth = theme.gridWidth;
        tags.push({ y, color, text: `${m.label} ${price(m.price)}`, past: !!m.past });
        continue;
      }
      if (idx < a || idx > b || m.price == null) continue;
      const x = xOf(idx);
      const y = pp.yOf(m.price);
      const r = theme.dotRadius + 0.5;
      ctx.lineWidth = theme.lineWidthThin;
      if (m.kind === 'entry') {                                   // anello: dove il trade è entrato
        ctx.fillStyle = theme.halo; ctx.strokeStyle = theme.text;
        ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      } else {                                                    // rombo: dove è uscito, colorato dal segno di R
        ctx.fillStyle = m.color ? theme[m.color] || theme.text : theme.text; ctx.strokeStyle = theme.halo;
        ctx.beginPath(); ctx.moveTo(x, y - r - 1.5); ctx.lineTo(x + r + 1.5, y); ctx.lineTo(x, y + r + 1.5); ctx.lineTo(x - r - 1.5, y); ctx.closePath(); ctx.fill(); ctx.stroke();
        if (m.label && exits <= 8) { ctx.fillStyle = theme.text; ctx.textAlign = 'center'; ctx.fillText(m.label, x, y - r - 10); }      // tanti trade: restano i segni, le cifre stanno nel libro
      }
      ctx.lineWidth = theme.gridWidth;
    }
    ctx.restore();
    // cartellini dei livelli sul righello di destra: di vetro (fondo scuro, filetto del colore del livello), mai sovrapposti
    tags.sort((u, v) => u.y - v.y);
    let lastTag = -99;
    for (const tg of tags) {
      const y = Math.max(lastTag + 15, tg.y);
      lastTag = y;
      const tw = Math.max(GUTTER - 1, ctx.measureText(tg.text).width + 10);      // il cartellino può sporgere nel grafico: nome e prezzo si leggono interi
      ctx.fillStyle = theme.halo;
      ctx.fillRect(W - tw, y - 8, tw, 16);
      ctx.strokeStyle = tg.color;
      ctx.setLineDash(tg.past ? theme.dashPast : []);
      ctx.strokeRect(W - tw + 0.5, y - 7.5, tw - 1, 15);
      ctx.setLineDash([]);
      ctx.fillStyle = tg.color === theme.text ? theme.text : tg.color;
      ctx.textAlign = 'left';
      ctx.fillText(tg.text, W - tw + 5, y);
    }

    // ---- volume ----
    const vp = ps[1];
    let vmax = 0;
    for (let i = a; i <= b; i++) if (d.v[i] > vmax) vmax = d.v[i];
    scale(vp, 0, vmax || 1);
    ctx.globalAlpha = theme.volumeOpacity;
    for (let i = a; i <= b; i++) {
      if (d.v[i] == null) continue;
      ctx.fillStyle = d.c[i] >= d.o[i] ? theme.up : theme.down;
      const y = vp.yOf(d.v[i]);
      ctx.fillRect(Math.round(xOf(i)) - Math.floor(body / 2), y, body, vp.y1 - y);
    }
    ctx.globalAlpha = 1;
    title(vp);
    ctx.fillStyle = theme.textMuted; ctx.textAlign = 'left'; ctx.fillText(compact(vmax), plotW + 6, vp.y0 + 6);

    // ---- pannelli sotto ----
    for (const p of ps.slice(2)) {
      ctx.strokeStyle = theme.axis;
      ctx.beginPath(); ctx.moveTo(0, p.y0 - 1.5); ctx.lineTo(W, p.y0 - 1.5); ctx.stroke();
      if (p.id === 'atr') {
        let m = 0;
        for (let i = a; i <= b; i++) if (ind.atr[i] > m) m = ind.atr[i];
        scale(p, 0, (m || 0.01) * 1.1);
        grid(p, [p.hi / 2.2], (v) => fmtPct(v, 1));
        line(p, ind.atr, theme.textSoft);
      } else if (p.id === 'rsi') {
        scale(p, 0, 100);
        band(p, 30, 70, theme.textMuted, theme.bandOpacity * 0.55);
        grid(p, [30, 70], (v) => fmtNum(v, 0));
        line(p, ind.rsi, theme.s2);
      } else if (p.id === 'conv') {
        const th = (d.thresholds && d.thresholds.conviction) || [0.6, 0.75];
        scale(p, 0, 1);
        band(p, th[0], th[1], theme.accent, theme.bandOpacity);
        band(p, th[1], 1, theme.accent, theme.bandOpacityStrong);
        grid(p, th, (v) => fmtNum(v, 2));
        line(p, d.conviction, theme.accent, { step: true, width: theme.lineWidthThin });
      } else if (p.id === 'gq') {
        const th = (d.thresholds && d.thresholds.gq) || [-0.5, 0.53, 1.42];
        let m = 2;
        for (let i = a; i <= b; i++) if (d.gq[i] != null && Math.abs(d.gq[i]) > m) m = Math.abs(d.gq[i]);
        scale(p, -m * 1.05, m * 1.05);
        band(p, -m * 1.05, th[0], theme.down, theme.bandOpacity * 0.8);
        band(p, th[1], th[2], theme.accent, theme.bandOpacity);
        band(p, th[2], m * 1.05, theme.accent, theme.bandOpacityStrong);
        grid(p, th, (v) => fmtNum(v, 2));
        line(p, d.gq, theme.neutral, { width: theme.lineWidthThin });                 // neutro: l'indicatore è in ombra
      }
      title(p);
    }

    // ---- asse del tempo ----
    const base = H - AXIS;
    ctx.strokeStyle = theme.axis;
    ctx.beginPath(); ctx.moveTo(0, base + 0.5); ctx.lineTo(W, base + 0.5); ctx.moveTo(plotW + 0.5, 0); ctx.lineTo(plotW + 0.5, base); ctx.stroke();
    ctx.fillStyle = theme.textMuted;
    ctx.textAlign = 'center';
    const spanDays = (d.t[b] - d.t[a]) / DAY;
    const months = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic'];
    let lastX = -100;
    for (let i = a; i <= b; i++) {
      const dt = new Date(d.t[i]);
      const prev = i > 0 ? new Date(d.t[i - 1]) : null;
      const newYear = !prev || prev.getUTCFullYear() !== dt.getUTCFullYear();
      const newMonth = !prev || prev.getUTCMonth() !== dt.getUTCMonth();
      const tick = spanDays > 900 ? newYear : spanDays > 100 ? newMonth : dt.getUTCDay() === 1;
      if (!tick) continue;
      const x = xOf(i);
      if (x - lastX < 46 || x > plotW - 16 || x < 16) continue;
      lastX = x;
      ctx.fillText(spanDays > 900 ? String(dt.getUTCFullYear()) : spanDays > 100 ? (dt.getUTCMonth() === 0 ? String(dt.getUTCFullYear()) : months[dt.getUTCMonth()]) : `${dt.getUTCDate()} ${months[dt.getUTCMonth()]}`, x, base + 9);
    }

    // ---- mirino ----
    geo = { a, b, bw, plotW, ps, xOf };
    if (a !== lastA || b !== lastB) {
      lastA = a;
      lastB = b;
      if (!silentWin) for (const fn of winSubs) fn([d.t[a], d.t[b]]);
      if (fallback) fallback.refresh();
    }
    silentWin = false;
    if (hover != null && hover >= a && hover <= b) {
      const x = Math.round(xOf(hover)) + 0.5;
      ctx.strokeStyle = theme.crossLine;
      ctx.setLineDash(theme.dashCross);
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, base); ctx.stroke();
      const hp = hoverY == null ? null : ps.find((p) => hoverY >= p.y0 && hoverY <= p.y1);
      if (hp && hp.vOf) {
        const y = Math.round(hoverY) + 0.5;
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(plotW, y); ctx.stroke();
        ctx.setLineDash([]);
        const v = hp.vOf(hoverY);
        const txt = hp.id === 'price' ? price(v) : hp.id === 'vol' ? compact(v) : hp.id === 'atr' ? fmtPct(v, 1) : fmtNum(v, 2);
        ctx.fillStyle = theme.text;
        ctx.fillRect(plotW + 1, y - 8, GUTTER - 1, 16);
        ctx.fillStyle = theme.surface;
        ctx.textAlign = 'left';
        ctx.fillText(txt, plotW + 6, y);
      }
      ctx.setLineDash([]);
    }
    paintReadout();
  }

  function paintReadout() {
    if (!d) { read.textContent = ''; return; }
    const i = hover != null ? hover : d.t.length - 1;
    const chg = i > 0 && d.c[i - 1] ? d.c[i] / d.c[i - 1] - 1 : null;
    const parts = [
      h('span', { class: 'cx__sym', text: d.symbol || '' }), h('span', { text: fmtDate(d.t[i], true) }),
      h('span', null, 'A ', h('b', { text: price(d.o[i]) })), h('span', null, 'Max ', h('b', { text: price(d.h[i]) })),
      h('span', null, 'Min ', h('b', { text: price(d.l[i]) })), h('span', null, 'C ', h('b', { text: price(d.c[i]) })),
      h('span', { class: chg > 0 ? 'pos' : chg < 0 ? 'neg' : '' }, chg == null ? '' : fmtPctSigned(chg, 2)),
      h('span', null, 'Vol ', h('b', { text: compact(d.v[i]) })),
      h('span', { class: 'cx__extra' }, 'ATR ', h('b', { text: ind.atr[i] == null ? '—' : fmtPct(ind.atr[i], 1) })),
      h('span', { class: 'cx__extra' }, 'RSI ', h('b', { text: ind.rsi[i] == null ? '—' : fmtNum(ind.rsi[i], 0) })),
      d.conviction ? h('span', { class: 'cx__extra' }, 'Conv ', h('b', { text: d.conviction[i] == null ? '—' : fmtNum(d.conviction[i], 2) })) : null,
      d.gq ? h('span', { class: 'cx__extra' }, 'GQ ', h('b', { text: d.gq[i] == null ? '—' : fmtNum(d.gq[i], 2) })) : null,
    ];
    read.replaceChildren(...parts.filter(Boolean));
  }

  function clampView() {
    const n = d.t.length;
    let w = i1 - i0;
    w = Math.max(15, Math.min(n - 1 + 6, w));
    if (i0 < -3) i0 = -3;
    if (i0 + w > n - 1 + 6) i0 = n - 1 + 6 - w;
    if (i0 < -3) i0 = -3;
    i1 = i0 + w;
  }

  function indexAt(clientX) {
    if (!geo) return null;
    const r = canvas.getBoundingClientRect();
    const i = Math.round(i0 + (clientX - r.left) / geo.bw - 0.5);
    return Math.max(0, Math.min(d.t.length - 1, i));
  }

  function zoom(factor, anchorIndex) {
    const w = (i1 - i0) * factor;
    const frac = (anchorIndex - i0) / Math.max(1e-9, i1 - i0);
    i0 = anchorIndex - frac * w;
    i1 = i0 + w;
    clampView();
    request();
  }

  canvas.addEventListener('wheel', (e) => {
    if (!d) return;
    e.preventDefault();
    if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) { const s = (e.deltaX / Math.max(1, geo ? geo.bw : 6)); i0 += s; i1 += s; clampView(); request(); return; }
    zoom(e.deltaY > 0 ? 1.18 : 1 / 1.18, indexAt(e.clientX) ?? d.t.length - 1);
  }, { passive: false });
  canvas.addEventListener('pointerdown', (e) => {
    if (!d || e.button > 0) return;
    drag = { x: e.clientX, i0, i1, moved: false };
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener('pointermove', (e) => {
    if (!d) return;
    if (drag && geo) {
      const shift = (drag.x - e.clientX) / geo.bw;
      if (Math.abs(drag.x - e.clientX) > 3) drag.moved = true;
      i0 = drag.i0 + shift;
      i1 = drag.i1 + shift;
      clampView();
    }
    const r = canvas.getBoundingClientRect();
    setHover(indexAt(e.clientX), e.clientY - r.top);
    request();
  });
  const endDrag = () => { drag = null; };
  canvas.addEventListener('pointerup', endDrag);
  canvas.addEventListener('pointercancel', endDrag);
  canvas.addEventListener('pointerleave', () => { if (!drag) { setHover(null); request(); } });
  canvas.addEventListener('dblclick', () => { if (d) { i0 = -1; i1 = d.t.length + 2; clampView(); request(); } });
  canvas.addEventListener('keydown', (e) => {
    if (!d) return;
    const n = d.t.length;
    const cur = hover == null ? Math.min(n - 1, Math.floor(i1)) : hover;
    const stepBig = Math.max(1, Math.round((i1 - i0) / 10));
    let used = true;
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      const dir = e.key === 'ArrowLeft' ? -1 : 1;
      if (e.shiftKey) { i0 += dir * stepBig; i1 += dir * stepBig; clampView(); }
      else {
        setHover(Math.max(0, Math.min(n - 1, cur + dir)));
        if (hover < i0) { const w = i1 - i0; i0 = hover - 2; i1 = i0 + w; clampView(); }
        if (hover > i1) { const w = i1 - i0; i1 = hover + 2; i0 = i1 - w; clampView(); }
        live.textContent = `${fmtDate(d.t[hover], true)}: apertura ${price(d.o[hover])}, massimo ${price(d.h[hover])}, minimo ${price(d.l[hover])}, chiusura ${price(d.c[hover])}`;
      }
    } else if (e.key === '+' || e.key === '=') zoom(1 / 1.3, cur);
    else if (e.key === '-' || e.key === '_') zoom(1.3, cur);
    else if (e.key === 'Home') { const w = i1 - i0; i0 = -1; i1 = i0 + w; clampView(); }
    else if (e.key === 'End') { const w = i1 - i0; i1 = n + 2; i0 = i1 - w; clampView(); }
    else if (e.key === 'Escape') { setHover(null); }
    else used = false;
    if (used) { e.preventDefault(); request(); }
  });

  const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(resize) : null;
  if (ro) ro.observe(plot);
  const offTheme = onChartThemeChange(request);

  let tween = 0;
  function setRange(months, opts = {}) {
    const a0 = i0;
    const a1 = i1;
    applyRange(months);
    const dur = chartTheme().range;
    cancelAnimationFrame(tween);
    if (!d || opts.animate === false || !(dur > 1) || chartTheme().reducedMotion || a1 - a0 < 2) return;
    const b0 = i0;
    const b1 = i1;
    const t0 = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - t0) / dur);
      const e = 1 - (1 - k) ** 3;
      i0 = a0 + (b0 - a0) * e;
      i1 = a1 + (b1 - a1) * e;
      request();
      if (k < 1) tween = requestAnimationFrame(step);
    };
    i0 = a0;
    i1 = a1;
    tween = requestAnimationFrame(step);
  }
  function applyRange(months) {
    if (!d) return;
    const n = d.t.length;
    if (!months) { i0 = -1; i1 = n + 2; } else {
      const end = new Date(d.t[n - 1]);
      const cut = Date.UTC(end.getUTCFullYear(), end.getUTCMonth() - months, end.getUTCDate());
      let k = n - 1;
      while (k > 0 && d.t[k - 1] >= cut) k--;
      i0 = k - 0.5;
      i1 = n + 2;
    }
    clampView();
    request();
  }

  return {
    /** data: { symbol, t: [ms], o, h, l, c, v, conviction, gq, thresholds, markers: [{ i, price, kind, label, color }] } */
    setData(next, { keepView = false, months = 6 } = {}) {
      const same = d && next && d.symbol === next.symbol && keepView;
      const atEnd = d ? i1 >= d.t.length - 1 : true;
      const grown = d && next ? next.t.length - d.t.length : 0;
      d = next && next.t && next.t.length >= 2 ? next : null;
      setHover(null);
      lastA = -1;
      if (d) {
        compute();
        if (same) { if (atEnd && grown > 0) { i0 += grown; i1 += grown; } clampView(); request(); }
        else setRange(months);
      } else request();
      paintReadout();
    },
    setOverlays(ids) { overlays = new Set(ids); request(); },
    setPanes(ids) { subPanes = new Set(ids); request(); },
    setLog(on) { log = !!on; request(); },
    setRange,
    redraw: resize,
    get view() { return d ? { from: Math.max(0, Math.round(i0)), to: Math.min(d.t.length - 1, Math.round(i1)) } : null; },
    /** fn(t | null, indice | null) a ogni spostamento del mirino; restituisce la funzione che toglie l'ascolto. */
    onHover(fn) { hoverSubs.add(fn); return () => hoverSubs.delete(fn); },
    /** Mirino comandato da un altro grafico: si posa sulla barra più vicina a t, senza avvisare gli ascoltatori. */
    setHoverTime(t) {
      if (!d || drag) return;
      let i = null;
      if (t != null && t >= d.t[0] - DAY && t <= d.t[d.t.length - 1] + DAY) {
        let lo = 0;
        let hi = d.t.length - 1;
        while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (d.t[mid] < t) lo = mid; else hi = mid; }
        i = Math.abs(d.t[lo] - t) <= Math.abs(d.t[hi] - t) ? lo : hi;
      }
      hover = i;
      hoverY = null;
      request();
    },
    /** Finestra visibile per date (ms): usata da linkCharts per tenere allineati più grafici. */
    setWindow(t0, t1, { silent = false } = {}) {
      if (!d) return;
      let a = 0;
      while (a < d.t.length - 1 && d.t[a] < t0) a++;
      let b = d.t.length - 1;
      while (b > a && d.t[b] > t1) b--;
      i0 = a - 0.5;
      i1 = b + 0.5;
      clampView();
      silentWin = silent;
      request();
    },
    resetWindow() { setRange(null); },
    onWindow(fn) { winSubs.add(fn); return () => winSubs.delete(fn); },
    destroy() { if (ro) ro.disconnect(); offTheme(); },
  };
}
