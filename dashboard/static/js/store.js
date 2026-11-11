// Interroga /api/v1/snapshot ogni 5 secondi e tiene lo stato della connessione.
// Regola: i numeri vecchi non si mostrano mai in silenzio. Se la richiesta fallisce lo stato è "offline";
// se lo snapshot è più vecchio di meta.stale_after_s lo stato è "stale". Un backtest è statico per natura:
// se ne mostra l'età ma non scatta l'allarme.

import { obj, parseTs } from './format.js';
import { isBacktest, staleLimit } from './model.js';

const SNAPSHOT_URL = 'api/v1/snapshot';
const HEALTH_URL = 'api/v1/health';
const POLL_MS = 5000;
const HEALTH_MS = 20000;
const TIMEOUT_MS = 4500;

async function getJson(url) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(url, { cache: 'no-store', signal: ctrl.signal, headers: { Accept: 'application/json' } });
    const text = await res.text();
    let body = null;
    try { body = JSON.parse(text); } catch (e) { body = null; }
    return { res, text, body };
  } finally {
    clearTimeout(timer);
  }
}

export function createStore() {
  const state = {
    snap: null,          // ultimo snapshot valido
    health: null,        // ultimo /health valido
    failures: 0,         // richieste fallite consecutive
    error: '',           // motivo dell'ultimo fallimento, già in italiano
    receivedAt: null,    // quando è arrivato l'ultimo snapshot (orologio locale, ms)
    clockOffset: 0,      // orologio del server − orologio locale (ms), dall'header Date
    status: 'loading',   // loading | ok | stale | offline
  };
  const subscribers = new Set();
  let lastText = null;
  let timer = null;
  let busy = false;
  let lastHealthAt = 0;

  const serverNow = () => Date.now() + state.clockOffset;

  /** Età in secondi dello snapshot secondo meta.as_of, oppure null se l'istante manca. */
  function ageSeconds() {
    const t = parseTs(obj(obj(state.snap).meta).as_of);
    return t == null ? null : Math.max(0, (serverNow() - t) / 1000);
  }

  function computeStatus() {
    if (state.failures > 0) return 'offline';
    if (!state.snap) return 'loading';
    const meta = obj(state.snap.meta);
    if (isBacktest(meta)) return 'ok';
    const age = ageSeconds();
    return age == null || age > staleLimit(meta) ? 'stale' : 'ok';
  }

  function emit(dataChanged) {
    const before = state.status;
    state.status = computeStatus();
    if (dataChanged || before !== state.status) for (const fn of subscribers) fn(state, dataChanged);
  }

  async function pollSnapshot() {
    try {
      const { res, text, body } = await getJson(SNAPSHOT_URL);
      const serverDate = Date.parse(res.headers.get('Date') || '');
      if (Number.isFinite(serverDate)) {
        const offset = serverDate - Date.now();
        state.clockOffset = Math.abs(offset) < 1500 ? 0 : offset;      // l'header Date ha la risoluzione del secondo
      }
      if (!res.ok || !body || typeof body !== 'object' || Array.isArray(body)) {
        const why = body && typeof body.error === 'string' ? body.error : `risposta ${res.status}`;
        throw new Error(why);
      }
      const changed = text !== lastText || state.failures > 0;
      lastText = text;
      state.snap = body;
      state.failures = 0;
      state.error = '';
      state.receivedAt = Date.now();
      emit(changed);
    } catch (err) {
      state.failures += 1;
      state.error = err && err.name === 'AbortError' ? 'il server non risponde' : (err && err.message) || 'errore di rete';
      if (err instanceof TypeError) state.error = 'server non raggiungibile';
      emit(state.failures === 1);
    }
  }

  async function pollHealth(force = false) {
    if (!force && Date.now() - lastHealthAt < HEALTH_MS) return;
    lastHealthAt = Date.now();
    try {
      const { res, body } = await getJson(HEALTH_URL);
      if (res.ok && body && typeof body === 'object') {
        const before = JSON.stringify(state.health);
        state.health = body;
        if (before !== JSON.stringify(body)) for (const fn of subscribers) fn(state, true);
      }
    } catch (e) {
      /* lo stato della connessione lo decide lo snapshot */
    }
  }

  async function tick() {
    if (busy) return;
    busy = true;
    try {
      await pollSnapshot();
      await pollHealth();
    } finally {
      busy = false;
      schedule();
    }
  }

  function schedule() {
    clearTimeout(timer);
    if (document.visibilityState === 'hidden') return;        // scheda nascosta: si riprende al ritorno
    timer = setTimeout(tick, POLL_MS);
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') tick();
  });

  return {
    state,
    serverNow,
    ageSeconds,
    start: tick,
    refresh: tick,
    refreshHealth: () => pollHealth(true),
    /** Da chiamare ogni secondo: lo stato può diventare "stale" senza che arrivi nulla di nuovo. */
    reevaluate: () => emit(false),
    subscribe(fn) {
      subscribers.add(fn);
      return () => subscribers.delete(fn);
    },
    staleLimit: () => staleLimit(obj(obj(state.snap).meta)),
  };
}
