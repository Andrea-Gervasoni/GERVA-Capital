// Formattazione in italiano, sempre tollerante: un valore assente o non numerico diventa "—", mai un'eccezione.

const LOCALE = 'it-IT';
export const DASH = '—';
const MINUS = '−';

/** Numero finito oppure null (accetta anche stringhe numeriche). */
export function num(v) {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  if (typeof v === 'string' && v.trim() !== '') {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export const str = (v) => (v == null ? '' : String(v));
export const obj = (v) => (v && typeof v === 'object' && !Array.isArray(v) ? v : {});
export const arr = (v) => (Array.isArray(v) ? v.filter((x) => x && typeof x === 'object') : []);
export const list = (v) => (Array.isArray(v) ? v : []);

const formatters = new Map();
function nf(options) {
  const key = JSON.stringify(options);
  let f = formatters.get(key);
  if (!f) {
    try {
      f = new Intl.NumberFormat(LOCALE, { useGrouping: 'always', ...options });
    } catch (e) {
      f = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    formatters.set(key, f);
  }
  return f;
}

const typo = (s) => s.replace(/-/g, MINUS);

/** 1234.5 → "1.234,50" */
export function fmtNum(v, max = 2, min = max) {
  const n = num(v);
  if (n == null) return DASH;
  return typo(nf({ minimumFractionDigits: Math.min(min, max), maximumFractionDigits: max }).format(n));
}

/** Come fmtNum ma con il segno esplicito: "+1,20" / "−0,35" / "0,00". */
export function fmtSigned(v, max = 2, min = max) {
  const n = num(v);
  if (n == null) return DASH;
  return typo(nf({ minimumFractionDigits: Math.min(min, max), maximumFractionDigits: max, signDisplay: 'exceptZero' }).format(n));
}

/** Importo nella valuta di base: "12.197,04 €". */
export function fmtMoney(v, ccy = 'EUR', { digits = 2, signed = false } = {}) {
  const n = num(v);
  if (n == null) return DASH;
  const code = /^[A-Za-z]{3}$/.test(str(ccy)) ? str(ccy).toUpperCase() : null;
  const base = { minimumFractionDigits: digits, maximumFractionDigits: digits, signDisplay: signed ? 'exceptZero' : 'auto' };
  if (!code) return typo(nf(base).format(n));
  return typo(nf({ ...base, style: 'currency', currency: code, currencyDisplay: 'narrowSymbol' }).format(n));
}

/** Frazione → percentuale: 0.0124 → "1,24%". Le percentuali grandi perdono decimali. */
export function fmtPct(v, digits = 2, { signed = false } = {}) {
  const n = num(v);
  if (n == null) return DASH;
  const p = n * 100;
  const a = Math.abs(p);
  const d = a >= 1000 ? 0 : a >= 100 ? Math.min(digits, 1) : digits;
  return (signed ? fmtSigned(p, d) : fmtNum(p, d)) + '%';
}

export const fmtPctSigned = (v, digits = 2) => fmtPct(v, digits, { signed: true });

/** Decimali necessari perché due tacche distanti `step` non abbiano la stessa etichetta. */
export function stepDigits(step, max = 4) {
  const s = num(step);
  if (s == null || s <= 0) return 0;
  for (let d = 0; d < max; d++) {
    const scaled = s * 10 ** d;
    if (Math.abs(scaled - Math.round(scaled)) < 1e-6 * Math.max(1, scaled)) return d;
  }
  return max;
}

/** Importi per gli assi: per esteso sotto 100.000, compatti sopra; i decimali seguono il passo delle tacche. */
export function fmtAxisAmount(v, step = null) {
  const n = num(v);
  if (n == null) return DASH;
  const a = Math.abs(n);
  if (a >= 1e6) return fmtNum(n / 1e6, a >= 1e7 ? 0 : 1, 0) + ' M';
  if (a >= 1e5) return fmtNum(n / 1e3, 0) + 'k';
  return fmtNum(n, stepDigits(step));
}

export function fmtQty(v) {
  const n = num(v);
  if (n == null) return DASH;
  const a = Math.abs(n);
  return fmtNum(n, a >= 1000 ? 2 : a >= 1 ? 4 : 6, 0);
}

export function fmtPrice(v) {
  const n = num(v);
  if (n == null) return DASH;
  const a = Math.abs(n);
  return fmtNum(n, a >= 100 ? 2 : a >= 1 ? 3 : 6, 2);
}

/** Valore di un limite o di un cancello nella sua unità ("x", "%", altro). */
export function fmtUnit(v, unit, { signed = false } = {}) {
  const n = num(v);
  if (n == null) return DASH;
  const u = str(unit).trim();
  if (u === '%') return fmtPct(n, Math.abs(n) < 0.1 ? 2 : 1, { signed });
  if (u.toLowerCase() === 'x') return fmtNum(n, 2) + 'x';
  const body = Number.isInteger(n) ? fmtNum(n, 0) : fmtNum(n, 2, 0);
  return u ? `${body} ${u}` : body;
}

// ---- tempo -------------------------------------------------------------------------------------------------

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;
const NO_ZONE = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/;

/** ISO-8601 (UTC se senza fuso) o epoch → millisecondi, oppure null. */
export function parseTs(v) {
  if (typeof v === 'number') return Number.isFinite(v) && v > 0 ? (v < 1e11 ? v * 1000 : v) : null;
  if (typeof v !== 'string') return null;
  let s = v.trim();
  if (!s) return null;
  if (DATE_ONLY.test(s)) s += 'T00:00:00Z';
  else if (NO_ZONE.test(s)) s = s.replace(' ', 'T') + 'Z';
  const t = Date.parse(s);
  return Number.isFinite(t) ? t : null;
}

/** True per "2026-01-02" e per le mezzanotti UTC esatte: date senza un'ora significativa. */
export function isDateOnly(v) {
  return typeof v === 'string' && (DATE_ONLY.test(v.trim()) || /T00:00(:00(\.0+)?)?(Z|\+00:?00)$/.test(v.trim()));
}

const dtf = new Map();
function df(options) {
  const key = JSON.stringify(options);
  let f = dtf.get(key);
  if (!f) {
    f = new Intl.DateTimeFormat(LOCALE, options);
    dtf.set(key, f);
  }
  return f;
}
const fmtWith = (ms, options) => (ms == null || !Number.isFinite(ms) ? DASH : df(options).format(ms));
const zone = (utc) => (utc ? { timeZone: 'UTC' } : {});

export const fmtDate = (ms, utc = false) => fmtWith(ms, { day: 'numeric', month: 'short', year: 'numeric', ...zone(utc) });
export const fmtDayMonth = (ms, utc = false) => fmtWith(ms, { day: 'numeric', month: 'short', ...zone(utc) });
export const fmtMonth = (ms, utc = false) => fmtWith(ms, { month: 'short', ...zone(utc) });
export const fmtMonthLong = (ms, utc = false) => fmtWith(ms, { month: 'long', year: 'numeric', ...zone(utc) });
export const fmtYear = (ms, utc = false) => fmtWith(ms, { year: 'numeric', ...zone(utc) });
export const fmtTime = (ms) => fmtWith(ms, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
export const fmtDateTime = (ms) => fmtWith(ms, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' });
export const fmtDayTime = (ms) => fmtWith(ms, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

/** Un istante dello snapshot: solo la data se non ha un'ora significativa. */
export function fmtStamp(v) {
  const ms = parseTs(v);
  if (ms == null) return DASH;
  return isDateOnly(v) ? fmtDate(ms, true) : fmtDayTime(ms);
}

/** Durata: 4 s · 12 min · 3 h 20 min · 18 g 4 h. */
export function fmtDuration(seconds) {
  const n = num(seconds);
  if (n == null || n < 0) return DASH;
  if (n < 60) return `${Math.round(n)} s`;
  if (n < 3600) return `${Math.floor(n / 60)} min`;
  if (n < 86400) {
    const hh = Math.floor(n / 3600);
    const mm = Math.floor((n % 3600) / 60);
    return mm ? `${hh} h ${mm} min` : `${hh} h`;
  }
  const dd = Math.floor(n / 86400);
  const hh = Math.floor((n % 86400) / 3600);
  return hh ? `${dd} g ${hh} h` : `${dd} g`;
}

export function fmtAgo(seconds) {
  const n = num(seconds);
  if (n == null) return DASH;
  if (n < 2) return 'adesso';
  return `${fmtDuration(n)} fa`;
}

/** Età di un istante rispetto a "adesso" (in ms), come testo. */
export function fmtAge(v, nowMs) {
  const ms = parseTs(v);
  if (ms == null) return DASH;
  return fmtAgo(Math.max(0, (nowMs - ms) / 1000));
}

/** +1, −1, 0 oppure null se il valore manca. */
export function signOf(v) {
  const n = num(v);
  if (n == null) return null;
  return n > 0 ? 1 : n < 0 ? -1 : 0;
}
