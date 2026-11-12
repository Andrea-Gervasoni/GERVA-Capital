// Letture di sola consultazione usate dal terminale e dai grafici: prezzi, libro dei trade, storico dei trade, confronto.
// Ogni risorsa è una GET con cache breve nel browser; un 404 diventa `null` (la pagina mostra uno stato vuoto, mai un dato finto).

const TTL_MS = 5 * 60 * 1000;
const cache = new Map();

async function getJson(url) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 12000);
  try {
    const res = await fetch(url, { cache: 'no-store', signal: ctrl.signal, headers: { Accept: 'application/json' } });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`risposta ${res.status}`);
    const body = await res.json();
    return body && typeof body === 'object' ? body : null;
  } finally {
    clearTimeout(timer);
  }
}

function cached(key, url, ttl = TTL_MS) {
  const hit = cache.get(key);
  if (hit && hit.until > Date.now()) return hit.promise;
  const promise = getJson(url).catch(() => { cache.delete(key); return undefined; });   // undefined = errore, null = assente
  cache.set(key, { until: Date.now() + ttl, promise });
  return promise;
}

const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const col = (a) => (Array.isArray(a) ? a.map(num) : null);

/** Simboli disponibili: { source, example, symbols: [{ symbol, kind }] } oppure null. */
export const getSymbols = () => cached('symbols', 'api/v1/market/symbols');

/** Barre giornaliere di un simbolo, già in forma di colonne; t in millisecondi UTC. */
export async function getOhlc(symbol, limit = 1500) {
  const raw = await cached(`ohlc:${symbol}:${limit}`, `api/v1/market/ohlc?symbol=${encodeURIComponent(symbol)}&tf=1d&limit=${limit}`);
  if (!raw || !Array.isArray(raw.t)) return raw === undefined ? undefined : null;
  const t = raw.t.map((s) => Date.parse(`${s}T00:00:00Z`));
  if (t.some((x) => !Number.isFinite(x))) return null;
  return {
    symbol: String(raw.symbol || symbol), kind: String(raw.kind || ''), example: raw.example === true, source: String(raw.source || ''),
    t, o: col(raw.o), h: col(raw.h), l: col(raw.l), c: col(raw.c), v: col(raw.v) || t.map(() => null),
    conviction: col(raw.conviction), gq: col(raw.gq), thresholds: raw.thresholds && typeof raw.thresholds === 'object' ? raw.thresholds : null,
  };
}

export const getTradebook = () => cached('tradebook', 'api/v1/tradebook', 30000);
export const getTrades = () => cached('trades', 'api/v1/trades/history');
export const getCompare = () => cached('compare', 'api/v1/compare');
