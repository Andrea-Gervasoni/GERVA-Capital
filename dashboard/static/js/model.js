// Lettura dello snapshot: funzioni pure, senza DOM. Ogni campo può mancare o essere null.

import { arr, num, obj, parseTs, str } from './format.js';

export const DEFAULT_STALE_S = 120;

// ---- natura dei dati ------------------------------------------------------------------------------------------

/**
 * 'live' | 'paper' | 'sim' | 'unknown': decide il colore della fascia in alto.
 * Conta la modalità; l'etichetta vince solo se dichiara in testa DEMO o SIMULATO (un esempio servito al posto dei
 * dati veri non deve mai passare per reale). "PAPER: conto simulato…" resta paper.
 */
export function modeKind(meta) {
  const m = obj(meta);
  const mode = str(m.mode).toLowerCase();
  const head = str(m.data_label).toUpperCase().split(':')[0].trim();
  if (head.startsWith('DEMO') || head.startsWith('SIMULAT') || mode === 'backtest') return 'sim';
  if (mode.includes('paper') || head.startsWith('PAPER')) return 'paper';
  if (mode === 'live') return 'live';
  return 'unknown';
}

export function modeTag(meta) {
  const mode = str(obj(meta).mode).trim();
  if (!mode) return 'Modalità non dichiarata';
  const names = { live: 'Live', paper: 'Paper', backtest: 'Backtest' };
  return `Modalità ${names[mode.toLowerCase()] || mode}`;
}

/** Etichetta corta accanto al NAV: i numeri simulati non devono sembrare veri. */
export function modeShort(meta) {
  const m = obj(meta);
  if (str(m.data_label).toUpperCase().trim().startsWith('DEMO')) return 'Demo';
  const kind = modeKind(m);
  if (kind === 'sim') return 'Simulato';
  if (kind === 'paper') return 'Paper';
  if (kind === 'live') return 'Reale';
  return 'Non dichiarato';
}

export const isBacktest = (meta) => str(obj(meta).mode).toLowerCase() === 'backtest';

export function staleLimit(meta) {
  const n = num(obj(meta).stale_after_s);
  return n != null && n > 0 ? n : DEFAULT_STALE_S;
}

// ---- curva del patrimonio ---------------------------------------------------------------------------------------

const curveCache = new WeakMap();

/** { t: [ms], equity: [n], bench: [n|null], hasBench, dd: [frazione ≤ 0] }, ordinata per data. */
export function curveOf(snap) {
  const raw = obj(snap).equity_curve;
  if (!Array.isArray(raw)) return emptyCurve();
  const hit = curveCache.get(raw);
  if (hit) return hit;
  const rows = [];
  for (const p of raw) {
    if (!p || typeof p !== 'object') continue;
    const t = parseTs(p.t);
    const e = num(p.equity);
    if (t == null || e == null) continue;
    rows.push([t, e, num(p.benchmark)]);
  }
  rows.sort((a, b) => a[0] - b[0]);
  const out = { t: [], equity: [], bench: [], hasBench: false, dd: [] };
  let peak = -Infinity;
  for (const [t, e, b] of rows) {
    if (out.t.length && out.t[out.t.length - 1] === t) {       // stessa data due volte: vale l'ultima
      out.t.pop(); out.equity.pop(); out.bench.pop(); out.dd.pop();
    }
    peak = Math.max(peak, e);
    out.t.push(t);
    out.equity.push(e);
    out.bench.push(b);
    out.dd.push(peak > 0 ? e / peak - 1 : 0);
    if (b != null) out.hasBench = true;
  }
  curveCache.set(raw, out);
  return out;
}

function emptyCurve() {
  return { t: [], equity: [], bench: [], hasBench: false, dd: [] };
}

export const RANGES = [
  { id: '1M', label: '1M', months: 1, name: 'ultimo mese' },
  { id: '3M', label: '3M', months: 3, name: 'ultimi 3 mesi' },
  { id: '1A', label: '1A', months: 12, name: 'ultimo anno' },
  { id: 'ALL', label: 'Tutto', months: null, name: 'tutto lo storico' },
];

/** Indice del primo punto dell'intervallo scelto (sempre almeno due punti, se ci sono). */
export function rangeStart(curve, rangeId) {
  const n = curve.t.length;
  const r = RANGES.find((x) => x.id === rangeId) || RANGES[RANGES.length - 1];
  if (n < 2 || r.months == null) return 0;
  const end = new Date(curve.t[n - 1]);
  const cut = Date.UTC(end.getUTCFullYear(), end.getUTCMonth() - r.months, end.getUTCDate());
  let lo = 0;
  let hi = n - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (curve.t[mid] < cut) lo = mid + 1;
    else hi = mid;
  }
  return Math.min(lo, n - 2);
}

/** Benchmark riportato al valore del fondo nel primo punto dell'intervallo in cui entrambi esistono. */
export function rebaseBench(curve, i0) {
  const n = curve.t.length;
  const out = new Array(n - i0).fill(null);
  if (!curve.hasBench) return out;
  let k = -1;
  for (let i = i0; i < n; i++) {
    if (curve.bench[i] != null && curve.bench[i] !== 0) { k = i; break; }
  }
  if (k < 0) return out;
  const f = curve.equity[k] / curve.bench[k];
  for (let i = k; i < n; i++) out[i - i0] = curve.bench[i] == null ? null : curve.bench[i] * f;
  return out;
}

/** Punti per anno, dedotti dalle date (365 per serie di calendario, ~252 per giorni di borsa). */
export function periodsPerYear(curve) {
  const n = curve.t.length;
  if (n < 3) return 365;
  const years = (curve.t[n - 1] - curve.t[0]) / (365.25 * 86400000);
  return years > 0 ? Math.min(366, Math.max(12, (n - 1) / years)) : 365;
}

/** Volatilità e Sharpe mobili annualizzati su una finestra di `win` rendimenti: O(n). */
export function rolling(curve, win) {
  const n = curve.t.length;
  const vol = new Array(n).fill(null);
  const sharpe = new Array(n).fill(null);
  if (n < win + 1 || win < 5) return { vol, sharpe };
  const ppy = periodsPerYear(curve);
  const r = new Array(n).fill(0);
  for (let i = 1; i < n; i++) r[i] = curve.equity[i - 1] > 0 ? curve.equity[i] / curve.equity[i - 1] - 1 : 0;
  let sum = 0;
  let sq = 0;
  for (let i = 1; i < n; i++) {
    sum += r[i];
    sq += r[i] * r[i];
    if (i > win) {
      sum -= r[i - win];
      sq -= r[i - win] * r[i - win];
    }
    if (i >= win) {
      const mean = sum / win;
      const sd = Math.sqrt(Math.max(0, (sq - win * mean * mean) / (win - 1)));
      vol[i] = sd * Math.sqrt(ppy);
      sharpe[i] = sd > 1e-12 ? (mean / sd) * Math.sqrt(ppy) : null;
    }
  }
  return { vol, sharpe };
}

// ---- esposizione --------------------------------------------------------------------------------------------------

/**
 * Il contratto non dice se exposure.gross/net sono frazioni del NAV o importi. Il motore scrive frazioni;
 * se arrivassero importi lo si capisce dal confronto con la leva (lordo ≈ leva × patrimonio) e si convertono.
 * Ritorna il divisore da applicare ai valori di esposizione per ottenere frazioni del NAV.
 */
export function exposureDivisor(snap) {
  const e = obj(obj(snap).exposure);
  const eq = num(obj(obj(snap).nav).equity);
  const g = num(e.gross);
  const lev = num(e.leverage);
  if (eq == null || eq <= 0 || g == null) return 1;
  if (lev != null && lev > 0) return Math.abs(g - lev) <= Math.abs(g - lev * eq) ? 1 : eq;
  return Math.abs(g) > 25 ? eq : 1;
}

/** Utilizzo di un limite: |valore| / |soglia| (i limiti di perdita hanno entrambi i numeri negativi). */
export function utilization(value, limit) {
  const v = num(value);
  const l = num(limit);
  if (v == null || l == null || l === 0) return null;
  return Math.abs(v) / Math.abs(l);
}

// ---- rendimenti mensili -----------------------------------------------------------------------------------------

/** { years: [2024, ...], cell: Map("2024-3" → ret), totals: Map(2024 → rendimento composto), scale } */
export function monthlyGrid(snap) {
  const cell = new Map();
  const yearsSet = new Set();
  for (const m of arr(obj(snap).monthly_returns)) {
    const match = /^(\d{4})-(\d{1,2})/.exec(str(m.ym));
    const r = num(m.ret);
    if (!match || r == null) continue;
    const y = Number(match[1]);
    const mo = Number(match[2]);
    if (mo < 1 || mo > 12) continue;
    cell.set(`${y}-${mo}`, r);
    yearsSet.add(y);
  }
  const years = [...yearsSet].sort((a, b) => a - b);
  const totals = new Map();
  for (const y of years) {
    let acc = 1;
    for (let mo = 1; mo <= 12; mo++) if (cell.has(`${y}-${mo}`)) acc *= 1 + cell.get(`${y}-${mo}`);
    totals.set(y, acc - 1);
  }
  const mags = [...cell.values()].map(Math.abs).sort((a, b) => a - b);
  const scale = mags.length ? Math.max(0.01, mags[Math.min(mags.length - 1, Math.floor(mags.length * 0.92))]) : 0.01;
  return { years, cell, totals, scale };
}

// ---- etichette di stato -------------------------------------------------------------------------------------------

export const RISK_STATES = {
  NORMAL: { label: 'Normale', kind: 'ok', icon: 'check-circle', light: 'Semaforo verde', text: 'Esposizione piena, tutti i controlli attivi.' },
  REDUCED: { label: 'Ridotto', kind: 'warn', icon: 'warn', light: 'Semaforo giallo', text: 'Esposizione ridotta dal motore di rischio.' },
  HALTED: { label: 'Sospeso', kind: 'serious', icon: 'pause', light: 'Semaforo arancione', text: 'Esposizione al minimo, nessun aumento consentito.' },
  KILLED: { label: 'KILL', kind: 'crit', icon: 'power', light: 'Semaforo rosso', text: 'Tutto chiuso e bloccato: serve un intervento manuale.' },
};

export function riskState(risk) {
  const code = str(obj(risk).state).toUpperCase();
  return RISK_STATES[code] ? { code, ...RISK_STATES[code] } : { code: code || '', label: code || 'Non disponibile', kind: 'muted', icon: 'info', text: '' };
}

const pick = (table, value, fallbackKind = 'muted') => {
  const key = str(value).toLowerCase();
  return table[key] || { label: str(value) || '—', kind: fallbackKind, icon: 'info' };
};

export const limitStatus = (v) => pick({
  ok: { label: 'Nei limiti', kind: 'ok', icon: 'check' },
  warn: { label: 'Attenzione', kind: 'warn', icon: 'warn' },
  breach: { label: 'Superato', kind: 'crit', icon: 'crit' },
}, v);

export const strategyStatus = (v) => pick({
  active: { label: 'Attiva', kind: 'ok', icon: 'check' },
  paused: { label: 'In pausa', kind: 'warn', icon: 'pause' },
  disabled: { label: 'Disattivata', kind: 'muted', icon: 'off' },
}, v);

export const orderStatus = (v) => pick({
  filled: { label: 'Eseguito', kind: 'ok', icon: 'check' },
  partial: { label: 'Parziale', kind: 'accent', icon: 'clock' },
  pending: { label: 'In attesa', kind: 'accent', icon: 'clock' },
  rejected: { label: 'Rifiutato', kind: 'crit', icon: 'x' },
  cancelled: { label: 'Annullato', kind: 'muted', icon: 'off' },
  canceled: { label: 'Annullato', kind: 'muted', icon: 'off' },
  error: { label: 'Errore', kind: 'crit', icon: 'crit' },
}, v);

export const componentStatus = (v) => pick({
  ok: { label: 'Operativo', kind: 'ok', icon: 'check' },
  degraded: { label: 'Degradato', kind: 'warn', icon: 'warn' },
  warn: { label: 'Degradato', kind: 'warn', icon: 'warn' },
  down: { label: 'Fuori servizio', kind: 'crit', icon: 'crit' },
  error: { label: 'Fuori servizio', kind: 'crit', icon: 'crit' },
}, v);

export const alertLevel = (v) => pick({
  info: { label: 'Info', kind: 'muted', icon: 'info' },
  warn: { label: 'Attenzione', kind: 'warn', icon: 'warn' },
  warning: { label: 'Attenzione', kind: 'warn', icon: 'warn' },
  critical: { label: 'Critico', kind: 'crit', icon: 'crit' },
  error: { label: 'Critico', kind: 'crit', icon: 'crit' },
}, v);

export function orderSide(v) {
  const s = str(v).toUpperCase();
  if (s === 'BUY') return { label: 'Acquisto', dir: 1 };
  if (s === 'SELL') return { label: 'Vendita', dir: -1 };
  return { label: s || '—', dir: 0 };
}
