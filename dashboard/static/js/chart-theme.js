// Tema dei grafici: un solo oggetto, letto dalle proprietà CSS `--chart-*` (definite in css/tokens.css).
// La logica dei grafici non contiene colori, raggi, spessori, caratteri o tempi: li chiede qui. Per ridisegnare
// tutto basta cambiare i token nel CSS; al cambio di tema o di livello l'oggetto viene riletto da solo.

/** Token letti dal JavaScript e valore usato se il CSS non li definisce. */
export const CHART_TOKENS = {
  // colori
  surface: ['--chart-surface', '#121519'], text: ['--chart-text', '#e9ecf0'], textMuted: ['--chart-text-muted', '#7f8792'],
  grid: ['--chart-grid', '#20252b'], axis: ['--chart-axis', '#343a43'], crosshair: ['--chart-crosshair', '#7f8792'],
  up: ['--chart-up', '#61d19a'], down: ['--chart-down', '#f05f5a'], accent: ['--chart-accent', '#3987e5'], bench: ['--chart-bench', '#666e7a'],
  warn: ['--chart-warn', '#fab219'], crit: ['--chart-crit', '#d03b3b'],
  s1: ['--chart-series-1', '#3987e5'], s2: ['--chart-series-2', '#d95926'], s3: ['--chart-series-3', '#199e70'], s4: ['--chart-series-4', '#c98500'], s5: ['--chart-series-5', '#d55181'],
  // caratteri
  font: ['--chart-font', 'system-ui, sans-serif'], fontSize: ['--chart-font-size', 11, 'px'],
  // tratti
  lineWidth: ['--chart-line-width', 2, 'n'], lineWidthThin: ['--chart-line-width-thin', 1.5, 'n'], gridWidth: ['--chart-grid-width', 1, 'n'],
  dashRef: ['--chart-dash-ref', '4 4', 'dash'], dashMark: ['--chart-dash-mark', '2 3', 'dash'], dashCross: ['--chart-dash-cross', '3 3', 'dash'],
  // forme
  dotRadius: ['--chart-dot-radius', 4, 'n'], dotRadiusSmall: ['--chart-dot-radius-small', 3.5, 'n'], barRadius: ['--chart-bar-radius', 2, 'n'],
  bubbleMin: ['--chart-bubble-min', 5, 'n'], bubbleMax: ['--chart-bubble-max', 20, 'n'],
  candleBody: ['--chart-candle-body', 0.7, 'n'], candleMax: ['--chart-candle-max', 14, 'n'], gutter: ['--chart-gutter', 58, 'n'],
  // opacità
  areaOpacity: ['--chart-area-opacity', 0.1, 'n'], bandOpacity: ['--chart-band-opacity', 0.13, 'n'], bandOpacityStrong: ['--chart-band-opacity-strong', 0.24, 'n'], volumeOpacity: ['--chart-volume-opacity', 0.55, 'n'],
  // movimento
  motion: ['--chart-motion', 160, 'ms'],
};

let cached = null;
const listeners = new Set();

function read(el) {
  const cs = getComputedStyle(el);
  const out = {};
  for (const [key, [name, fallback, type]] of Object.entries(CHART_TOKENS)) {
    const raw = cs.getPropertyValue(name).trim();
    if (!type) out[key] = raw || fallback;
    else if (type === 'dash') out[key] = (raw || fallback).split(/[\s,]+/).map(Number).filter((v) => Number.isFinite(v));
    else { const v = parseFloat(raw); out[key] = Number.isFinite(v) ? v : fallback; }
  }
  out.series = [out.s1, out.s2, out.s3, out.s4, out.s5];
  out.canvasFont = `${out.fontSize}px ${out.font}`;
  out.reducedMotion = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (out.reducedMotion) out.motion = 0;
  return out;
}

/** L'oggetto del tema corrente (riletto solo quando cambia tema, livello o preferenza di movimento). */
export function chartTheme() {
  if (!cached) cached = read(document.body || document.documentElement);
  return cached;
}

/** Avvisa quando il tema cambia: i grafici su canvas si ridisegnano; quelli SVG seguono il CSS da soli. */
export function onChartThemeChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function invalidate() {
  cached = null;
  for (const fn of listeners) fn();
}

if (typeof MutationObserver === 'function' && typeof document !== 'undefined') {
  const mo = new MutationObserver(invalidate);
  mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'class', 'style'] });
  const watchBody = () => document.body && mo.observe(document.body, { attributes: true, attributeFilter: ['data-level', 'data-skin', 'class'] });
  if (document.body) watchBody(); else document.addEventListener('DOMContentLoaded', watchBody);
  if (typeof matchMedia === 'function') matchMedia('(prefers-reduced-motion: reduce)').addEventListener?.('change', invalidate);
}
