// Avvio della console: instradamento per hash, tema, fascia della modalità, stato della connessione, sezioni.

import { createStore } from './store.js';
import { h, icon, fill, loadPref, savePref } from './dom.js';
import { segmented } from './components.js';
import { glossaryList } from './glossary.js';
import { hideTip } from './charts.js';
import { initKill, lastKill } from './kill.js';
import { arr, fmtAgo, fmtDate, fmtDateTime, fmtDuration, obj, parseTs, str } from './format.js';
import { isBacktest, modeKind, modeTag, riskState } from './model.js';
import * as panoramica from './views/panoramica.js';
import * as performance from './views/performance.js';
import * as esposizione from './views/esposizione.js';
import * as rischio from './views/rischio.js';
import * as strategie from './views/strategie.js';
import * as ordini from './views/ordini.js';
import * as sistema from './views/sistema.js';
import * as comefunziona from './views/comefunziona.js';
import * as ricerca from './views/ricerca.js';
import * as ai from './views/ai.js';
import * as leva from './views/leva.js';

const ROUTES = [
  { id: 'panoramica', label: 'Panoramica', icon: 'overview', view: panoramica },
  { id: 'performance', label: 'Performance', icon: 'performance', view: performance },
  { id: 'esposizione', label: 'Esposizione', icon: 'exposure', view: esposizione },
  { id: 'rischio', label: 'Rischio', icon: 'risk', view: rischio },
  { id: 'strategie', label: 'Strategie', icon: 'strategies', view: strategie },
  { id: 'ordini', label: 'Ordini', icon: 'orders', view: ordini },
  { id: 'sistema', label: 'Sistema', icon: 'system', view: sistema },
  { id: 'ai', label: 'AI', icon: 'ai', view: ai, group: true },
  { id: 'ricerca', label: 'Ricerca', icon: 'research', view: ricerca },
  { id: 'leva-trade', label: 'Leva per trade', icon: 'lever', view: leva },
  { id: 'come-funziona', label: 'Come funziona', icon: 'flow', view: comefunziona },
];
const VIEW_REFRESH_MS = 30000;        // anche a dati invariati le età ("3 min fa") vanno aggiornate

const $ = (id) => document.getElementById(id);
const store = createStore();
const el = {
  view: $('view'), title: $('view-title'), nav: $('nav'), foot: $('rail-foot'), main: $('main'),
  modebar: $('modebar'), modeTag: $('modebar-tag'), modeLabel: $('modebar-label'), modeMeta: $('modebar-meta'),
  pill: $('risk-pill'), conn: $('conn'), connText: $('conn-text'), connShort: $('conn-short'),
  connbar: $('connbar'), connbarIcon: $('connbar-icon'), connbarTitle: $('connbar-title'), connbarText: $('connbar-text'),
  themeBtn: $('theme-toggle'), themeIcon: $('theme-toggle-icon'),
  summary: $('summary'), sources: $('sources'), levelHost: $('level-switch'),
  glossary: $('glossary'), glossaryBody: $('glossary-body'), glossaryBtn: $('glossary-btn'), glossaryClose: $('glossary-close'),
};
let level = loadPref('level', 'semplice') === 'esperto' ? 'esperto' : 'semplice';

let mounted = null;          // { route, handle }
let lastViewUpdate = 0;
const links = new Map();

// ---- tema ------------------------------------------------------------------------------------------------------------

function applyTheme(theme, persist) {
  document.documentElement.setAttribute('data-theme', theme);
  el.themeIcon.setAttribute('href', theme === 'dark' ? '#i-sun' : '#i-moon');
  el.themeBtn.setAttribute('aria-label', theme === 'dark' ? 'Passa al tema chiaro' : 'Passa al tema scuro');
  el.themeBtn.title = el.themeBtn.getAttribute('aria-label');
  if (persist) savePref('theme', theme);
}

function initTheme() {
  const current = () => (document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark');
  applyTheme(current(), false);
  el.themeBtn.addEventListener('click', () => applyTheme(current() === 'dark' ? 'light' : 'dark', true));
  let saved = null;
  try { saved = window.localStorage.getItem('gerva.dash.theme'); } catch (e) { saved = null; }
  if (!saved && window.matchMedia) {
    const mq = window.matchMedia('(prefers-color-scheme: light)');
    const follow = (e) => {
      let chosen = null;
      try { chosen = window.localStorage.getItem('gerva.dash.theme'); } catch (err) { chosen = null; }
      if (!chosen) applyTheme(e.matches ? 'light' : 'dark', false);
    };
    if (mq.addEventListener) mq.addEventListener('change', follow);
  }
}

// ---- navigazione -----------------------------------------------------------------------------------------------------

function routeNow() {
  const m = /^#\/([a-z-]+)/.exec(window.location.hash || '');
  const found = ROUTES.find((r) => r.id === (m && m[1]));
  // un'ancora qualsiasi (es. #main) non è una sezione: si resta dove si è
  return found || (mounted && !m ? mounted.route : ROUTES[0]);
}

function buildNav() {
  for (const r of ROUTES) {
    const flag = h('span', { class: 'nav__flag' });
    flag.hidden = true;
    const a = h('a', { class: `nav__link ${r.group ? 'nav__link--group' : ''}`.trim(), href: `#/${r.id}` }, icon(r.icon), h('span', { class: 'nav__label', text: r.label }), flag);
    a.flagEl = flag;
    links.set(r.id, a);
    el.nav.append(a);
  }
}

function markNav(route) {
  for (const [id, a] of links) {
    if (id === route.id) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  }
  const active = links.get(route.id);
  if (active && typeof active.scrollIntoView === 'function' && el.nav.scrollWidth > el.nav.clientWidth) {
    active.scrollIntoView({ block: 'nearest', inline: 'center' });
  }
}

/** Pallino accanto a una voce del menu quando lì c'è qualcosa da guardare (con testo per i lettori di schermo). */
function setFlag(id, kind, text) {
  const a = links.get(id);
  if (!a) return;
  a.flagEl.hidden = !kind;
  a.flagEl.className = `nav__flag ${kind ? `nav__flag--${kind}` : ''}`.trim();
  fill(a.flagEl, kind ? h('span', { class: 'sr-only', text: `, ${text}` }) : null);
}

function syncFlags(snap) {
  const risk = obj(snap.risk);
  const st = riskState(risk);
  const limits = arr(risk.limits).map((l) => str(l.status).toLowerCase());
  const riskKind = st.kind === 'crit' || st.kind === 'serious' || limits.includes('breach') ? 'crit' : (st.kind === 'warn' || limits.includes('warn') ? 'warn' : null);
  setFlag('rischio', riskKind, riskKind === 'crit' ? 'richiede attenzione immediata' : 'un limite è vicino alla soglia');
  const comps = arr(obj(snap.system).components).map((c) => str(c.status).toLowerCase());
  const sysKind = comps.some((c) => c === 'down' || c === 'error') ? 'crit' : (comps.some((c) => c === 'degraded' || c === 'warn') ? 'warn' : null);
  setFlag('sistema', sysKind, sysKind === 'crit' ? 'un componente è fuori servizio' : 'un componente è degradato');
}

// ---- cornice: fascia della modalità, stato del rischio, connessione ---------------------------------------------------

function setText(node, text) {
  if (node.textContent !== text) node.textContent = text;
}

function syncChrome() {
  const st = store.state;
  const snap = st.snap;
  const meta = obj(snap && snap.meta);
  document.body.dataset.conn = st.status;

  // fascia in alto: natura dei dati, sempre visibile
  if (!snap) {
    el.modebar.dataset.kind = 'wait';
    setText(el.modeTag, st.status === 'offline' ? 'Nessun dato' : 'In attesa dei dati');
    setText(el.modeLabel, '');
    setText(el.modeMeta, '');
  } else {
    el.modebar.dataset.kind = modeKind(meta);
    setText(el.modeTag, modeTag(meta));
    setText(el.modeLabel, str(meta.data_label).trim() || 'Etichetta dei dati assente');
    const asOf = parseTs(meta.as_of);
    setText(el.modeMeta, `${asOf == null ? 'Ora dello snapshot assente' : `Snapshot del ${fmtDateTime(asOf)}`}${str(meta.version) ? ` · motore v${str(meta.version)}` : ''}`);
    el.modeLabel.title = el.modeLabel.textContent;
  }

  // stato del rischio, in ogni sezione
  if (snap) {
    const rs = riskState(snap.risk);
    el.pill.hidden = false;
    el.pill.className = `pill pill--${rs.kind}`;
    el.pill.setAttribute('aria-label', `Stato del rischio: ${rs.label}. Apri la sezione Rischio`);
    if (el.pill.dataset.state !== rs.code + rs.kind) {
      el.pill.dataset.state = rs.code + rs.kind;
      fill(el.pill, icon(rs.icon), h('span', { text: rs.label }));
    }
  } else {
    el.pill.hidden = true;
  }

  // connessione ed età del dato
  const age = store.ageSeconds();
  el.conn.dataset.state = st.status;
  let connText = 'Connessione…';
  if (st.status === 'ok') connText = isBacktest(meta) ? `Backtest · generato ${fmtAgo(age)}` : `In linea · dati di ${fmtAgo(age)}`;
  else if (st.status === 'stale') connText = age == null ? 'Dati senza orario' : `Dati fermi da ${fmtDuration(age)}`;
  else if (st.status === 'offline') connText = 'Offline';
  setText(el.connText, connText);
  setText(el.connShort, st.status === 'ok' ? fmtAgo(age) : st.status === 'stale' ? 'Fermi' : st.status === 'offline' ? 'Offline' : '…');

  // avviso visibile: mai numeri vecchi in silenzio
  let bar = null;
  if (snap && st.status === 'stale') {
    const asOf = parseTs(meta.as_of);
    bar = {
      icon: 'warn', title: 'Dati non aggiornati',
      text: asOf == null
        ? 'Lo snapshot non riporta l\'ora di aggiornamento: non si può verificare che i numeri siano attuali.'
        : `L'ultimo snapshot del motore è del ${fmtDateTime(asOf)}, oltre la soglia di ${fmtDuration(store.staleLimit())}. I numeri qui sotto potrebbero non essere attuali.`,
    };
  } else if (snap && st.status === 'offline') {
    bar = {
      icon: 'offline', title: 'Offline',
      text: `Il server della dashboard non risponde (${st.error}). I numeri qui sotto sono gli ultimi ricevuti, alle ${fmtDateTime(st.receivedAt)}. Nuovo tentativo ogni 5 secondi.`,
    };
  }
  el.connbar.hidden = !bar;
  if (bar) {
    el.connbar.dataset.kind = st.status;
    el.connbarIcon.setAttribute('href', `#i-${bar.icon}`);
    setText(el.connbarTitle, bar.title);
    setText(el.connbarText, bar.text);
  }

  if (snap) {
    syncSources();
    const lines = [str(meta.version) ? `Motore v${str(meta.version)}` : null, `Valuta base ${str(meta.base_ccy) || 'EUR'}`, 'Aggiornamento ogni 5 s'].filter(Boolean).join('\n');
    setText(el.foot, lines);
    syncFlags(snap);
  }
}

// ---- fonti dei dati: quanto è fresco ciò che si legge ---------------------------------------------------------------

function syncSources() {
  const st = store.state;
  const age = store.ageSeconds();
  const parts = [`Conto: ${st.status === 'offline' ? 'non raggiungibile' : age == null ? 'orario assente' : `aggiornato ${fmtAgo(age)}`}`];
  const since = store.secondsSinceQuant();
  const gen = parseTs(obj(st.quant).generated);
  if (st.quantStatus === 'ok') parts.push(`Ricerca: letta ${fmtAgo(since)}${gen == null ? '' : `, generata il ${fmtDate(gen)}`}`);
  else parts.push(`Ricerca: ${st.quantStatus === 'loading' ? 'in caricamento' : 'non disponibile'}`);
  if (st.quant4Status === 'ok') parts.push('Quarta tornata: letta');
  else if (st.quant4Status !== 'loading') parts.push('Quarta tornata: non disponibile');
  setText(el.sources, parts.join('  ·  '));
}

// ---- livello di lettura e glossario ------------------------------------------------------------------------------------

function initLevel() {
  document.body.dataset.level = level;
  const seg = segmented({
    label: 'Livello di lettura',
    options: [{ value: 'semplice', label: 'Semplice' }, { value: 'esperto', label: 'Esperto' }],
    value: level,
    onChange: (v) => {
      level = v;
      document.body.dataset.level = v;
      savePref('level', v);
      syncView({ force: true });
    },
  });
  el.levelHost.append(seg.el);
}

function openGlossary(id) {
  if (!el.glossary.open) {
    if (typeof el.glossary.showModal === 'function') el.glossary.showModal();
    else el.glossary.setAttribute('open', '');
  }
  for (const n of el.glossaryBody.querySelectorAll('.is-target')) n.classList.remove('is-target');
  const item = id ? document.getElementById(`gl-${id}`) : null;
  if (item) {
    item.classList.add('is-target');
    item.scrollIntoView({ block: 'start' });
    item.focus({ preventScroll: true });
  } else {
    el.glossaryBody.scrollTop = 0;
  }
}

function initGlossary() {
  el.glossaryBody.append(glossaryList());
  el.glossaryBtn.addEventListener('click', () => openGlossary(null));
  el.glossaryClose.addEventListener('click', () => el.glossary.close());
  el.glossary.addEventListener('click', (e) => { if (e.target === el.glossary) el.glossary.close(); });   // clic sullo sfondo
  document.addEventListener('click', (e) => {
    const t = e.target instanceof Element ? e.target.closest('.term') : null;
    if (t) {
      e.preventDefault();
      openGlossary(t.getAttribute('data-term'));
      return;
    }
    // i riquadri «Che cosa significa?» si chiudono toccando altrove
    for (const d of document.querySelectorAll('details.what[open]')) if (!(e.target instanceof Node) || !d.contains(e.target)) d.removeAttribute('open');
  });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    for (const d of document.querySelectorAll('details.what[open]')) {
      d.removeAttribute('open');
      const sm = d.querySelector('summary');
      if (sm && d.contains(document.activeElement)) sm.focus();
    }
  });
}

// ---- sezione corrente ------------------------------------------------------------------------------------------------

function placeholder() {
  const st = store.state;
  mounted = null;
  el.summary.hidden = true;
  if (st.status === 'offline') {
    fill(el.view, h('div', { class: 'placeholder placeholder--offline', role: 'alert' },
      icon('offline', 'icon--xl'),
      h('p', { class: 'placeholder__title', text: 'Server non raggiungibile' }),
      h('p', { class: 'placeholder__text', text: `Nessun dato da mostrare (${st.error}). Nuovo tentativo ogni 5 secondi.` }),
      h('p', { class: 'placeholder__text' }, 'Avvio del server: ', h('code', { text: 'python -m dashboard.server' }))));
  } else {
    fill(el.view, h('div', { class: 'placeholder' }, h('p', { class: 'placeholder__title', text: 'Caricamento dei dati…' })));
  }
}

function context() {
  const st = store.state;
  return { snap: st.snap, health: st.health, status: st.status, now: store.serverNow(), ccy: str(obj(st.snap.meta).base_ccy) || 'EUR', quant: st.quant, quantStatus: st.quantStatus, quant4: st.quant4, quant4Status: st.quant4Status, level };
}

const api = {
  killResult: lastKill,
};

function syncView({ force = false, focus = false } = {}) {
  const st = store.state;
  const route = routeNow();
  setText(el.title, route.label);
  document.title = `${route.label} · GERVA Capital`;
  markNav(route);
  if (!st.snap) {
    placeholder();
    return;
  }
  let fresh = false;
  if (!mounted || mounted.route !== route) {
    hideTip();
    fill(el.view);
    try {
      mounted = { route, handle: route.view.mount(el.view, api) };
    } catch (err) {
      console.error(err);
      mounted = { route, handle: null };
    }
    fresh = true;
    window.scrollTo(0, 0);
  }
  if (fresh || force || Date.now() - lastViewUpdate > VIEW_REFRESH_MS) {
    lastViewUpdate = Date.now();
    hideTip();
    try {
      if (!mounted.handle) throw new Error('sezione non disponibile');
      const c = context();
      mounted.handle.update(c);
      const line = typeof mounted.handle.summary === 'function' ? mounted.handle.summary(c) : '';
      el.summary.hidden = !line;
      fill(el.summary, line ? h('span', { class: 'summary__tag', text: 'In una frase' }) : null, line || null);
    } catch (err) {
      console.error(err);
      mounted = null;
      fill(el.view, h('div', { class: 'placeholder placeholder--offline', role: 'alert' },
        icon('crit', 'icon--xl'),
        h('p', { class: 'placeholder__title', text: 'Questa sezione non può essere mostrata' }),
        h('p', { class: 'placeholder__text', text: 'Lo snapshot contiene un dato che la pagina non sa leggere. Le altre sezioni restano disponibili.' })));
    }
  }
  if (focus) el.title.focus({ preventScroll: true });
}

// ---- avvio -----------------------------------------------------------------------------------------------------------

buildNav();
initTheme();
initLevel();
initGlossary();
document.querySelector('.skip-link').addEventListener('click', (event) => {
  event.preventDefault();                     // niente cambio di hash: le sezioni vivono lì
  el.main.focus();
  el.main.scrollIntoView({ block: 'start' });
});
initKill({
  done: () => {
    store.refreshHealth();
    syncView({ force: true });
  },
});
syncChrome();
syncView();

store.subscribe((state, dataChanged) => {
  syncChrome();
  syncView({ force: dataChanged });
});
window.addEventListener('hashchange', () => syncView({ focus: true }));
setInterval(() => {
  store.reevaluate();
  syncChrome();
  if (store.state.snap && Date.now() - lastViewUpdate > VIEW_REFRESH_MS) syncView();
}, 1000);
store.start();

