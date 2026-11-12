// Avvio della console: sette spazi in due gruppi (#/spazio/scheda?s=BTC), tre livelli di lettura, fascia di stato
// nella capsula in alto (modalità, stato del rischio, età dei dati, sistema, avvisi, KILL), tavolozza, coreografia.
// Sola lettura: l'unico comando che scrive è il KILL, e da qui si apre soltanto la finestra di conferma.

import { createStore } from './store.js';
import { h, icon, fill, loadPref, savePref } from './dom.js';
import { segmented } from './components.js';
import { glossaryList } from './glossary.js';
import { hideTip } from './charts.js';
import { initKill, lastKill, openKill, setKillEnabled, setKillPreview } from './kill.js';
import { initPalette, SHORTCUTS } from './cmd.js';
import { oldestSource, watchedSymbols } from './derive.js';
import { getOhlc, getSymbols, getTradebook } from './market.js';
import { arr, fmtAgo, fmtDate, fmtDateTime, fmtDayMonth, fmtDayTime, fmtDuration, fmtMoney, fmtNum, num, obj, parseTs, str } from './format.js';
import { alertLevel, componentStatus, isBacktest, modeKind, riskState } from './model.js';
import * as oggi from './views/oggi.js';
import * as mercati from './views/mercati.js';
import * as rischio from './views/rischio2.js';
import * as panoramica from './views/panoramica.js';
import * as performance from './views/performance.js';
import * as esposizione from './views/esposizione.js';
import * as rischioArchivio from './views/rischio.js';
import * as strategie from './views/strategie.js';
import * as ordini from './views/ordini.js';
import * as sistema from './views/sistema.js';
import * as comefunziona from './views/comefunziona.js';
import * as ricerca from './views/ricerca.js';
import * as ai from './views/ai.js';
import * as leva from './views/leva.js';
import * as apprendimento from './views/apprendimento.js';
import * as evidenza from './views/evidenza.js';

/** Gli spazi: quattro «ogni giorno», tre «quando serve». Le viste precedenti restano raggiungibili come schede. */
const SPACES = [
  { id: 'oggi', label: 'Oggi', icon: 'today', key: 'o', group: 'Ogni giorno', tabs: [{ id: '', label: 'Oggi', view: oggi }] },
  { id: 'mercati', label: 'Mercati', icon: 'trade', key: 'm', group: 'Ogni giorno', tabs: [
    { id: '', label: 'Grafico e libro', view: mercati }, { id: 'ai', label: 'Regime e conviction', view: ai }] },
  { id: 'portafoglio', label: 'Portafoglio', icon: 'portfolio', key: 'p', group: 'Ogni giorno', tabs: [
    { id: '', label: 'Risultato', view: performance }, { id: 'strategie', label: 'Strategie', view: strategie },
    { id: 'posizioni', label: 'Posizioni', view: esposizione }, { id: 'panoramica', label: 'Panoramica (archivio)', view: panoramica }] },
  { id: 'rischio', label: 'Rischio', icon: 'risk', key: 'r', group: 'Ogni giorno', tabs: [
    { id: '', label: 'Freni e tetti', view: rischio }, { id: 'limiti', label: 'Limiti e leva (archivio)', view: rischioArchivio }] },
  { id: 'evidenza', label: 'Evidenza', icon: 'evidence', key: 'e', group: 'Quando serve', tabs: [
    { id: '', label: 'Evidenza', view: evidenza }, { id: 'ricerca', label: 'Ricerca (archivio)', view: ricerca }, { id: 'leva', label: 'Leva per trade (archivio)', view: leva }] },
  { id: 'apprendimento', label: 'Apprendimento', icon: 'learn', key: 'a', group: 'Quando serve', tabs: [{ id: '', label: 'Apprendimento', view: apprendimento }] },
  { id: 'sistema', label: 'Sistema', icon: 'system', key: 's', group: 'Quando serve', tabs: [
    { id: '', label: 'Salute', view: sistema }, { id: 'ordini', label: 'Ordini', view: ordini }, { id: 'guida', label: 'Come funziona', view: comefunziona }] },
];
/** Indirizzi delle dodici pagine precedenti: continuano a funzionare. */
const LEGACY = {
  panoramica: 'portafoglio/panoramica', performance: 'portafoglio', esposizione: 'portafoglio/posizioni', strategie: 'portafoglio/strategie',
  ordini: 'sistema/ordini', ai: 'mercati/ai', ricerca: 'evidenza', 'leva-trade': 'evidenza/leva', 'come-funziona': 'sistema/guida', terminale: 'mercati',
};
const VIEW_REFRESH_MS = 30000;        // anche a dati invariati le età («3 min fa») vanno aggiornate
const SCALE = { NORMAL: '1,0', REDUCED: '0,5', HALTED: '0,25', KILLED: '0' };

const $ = (id) => document.getElementById(id);
const store = createStore();
const el = {
  view: $('view'), title: $('view-title'), date: $('view-date'), tabs: $('tabs'), nav: $('nav'), dock: $('dock'), foot: $('rail-foot'), main: $('main'),
  modebar: $('modebar'), modeTag: $('modebar-tag'), modeLabel: $('modebar-label'), modeMeta: $('modebar-meta'),
  pill: $('risk-pill'), why: $('risk-why'), conn: $('conn'), connText: $('conn-text'), connShort: $('conn-short'),
  connbar: $('connbar'), connbarIcon: $('connbar-icon'), connbarTitle: $('connbar-title'), connbarText: $('connbar-text'), connbarAck: $('connbar-ack'),
  sys: $('sys-item'), alertsBtn: $('alerts-btn'), alertsN: $('alerts-n'), alertsSheet: $('alerts-sheet'), alertsList: $('alerts-list'),
  killBtn: $('kill-open'), killState: $('kill-state'), themeBtn: $('theme-toggle'), themeIcon: $('theme-toggle-icon'),
  summary: $('summary'), summaryBtn: $('summary-btn'), sources: $('sources'), levelHost: $('level-switch'),
  glossary: $('glossary'), glossaryBody: $('glossary-body'), glossaryBtn: $('glossary-btn'), glossaryClose: $('glossary-close'),
  searchBtn: $('search-btn'), keysSheet: $('keys-sheet'), keysList: $('keys-list'), moreSheet: $('more-sheet'), moreBody: $('more-body'), aurora: $('aurora'),
};
const LEVELS = ['semplice', 'esperto', 'terminale'];
const LEVEL_LABEL = { semplice: 'Semplice', esperto: 'Esperto', terminale: 'Terminale' };
let level = LEVELS.includes(loadPref('level', 'semplice')) ? loadPref('level', 'semplice') : 'semplice';

let mounted = null;          // { key, space, tab, handle }
let lastViewUpdate = 0;
let leaving = false;
let summaryOpen = false;
let lastSeen = null;         // ultimo stato del rischio visto con dati freschi: { label, t }
let ack = null;              // presa in carico di una condizione critica: { key, t } (resta nel browser: una seconda scrittura è vietata)
let tradebook = null;
let barDays = [];            // ultima barra degli strumenti seguiti (trade aperti e posizioni): { name, day, kind }
const links = new Map();
const motionOn = () => !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
const narrow = () => window.innerWidth <= 860;
/** Terminale non è disponibile sotto i 860 px: ricade su Esperto. */
const shownLevel = () => (level === 'terminale' && narrow() ? 'esperto' : level);

// ---- tema ------------------------------------------------------------------------------------------------------------

function applyTheme(theme, persist) {
  document.documentElement.setAttribute('data-theme', theme);
  el.themeIcon.setAttribute('href', theme === 'dark' ? '#i-sun' : '#i-moon');
  el.themeBtn.setAttribute('aria-label', theme === 'dark' ? 'Passa al tema chiaro' : 'Passa al tema scuro');
  el.themeBtn.title = el.themeBtn.getAttribute('aria-label');
  if (persist) savePref('theme', theme);
}
const currentTheme = () => (document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark');
const toggleTheme = () => applyTheme(currentTheme() === 'dark' ? 'light' : 'dark', true);

// ---- indirizzi -------------------------------------------------------------------------------------------------------

/** #/spazio/scheda?s=BTC → { space, tab, params }. Un'ancora qualsiasi (es. #main) non è un indirizzo: si resta dove si è. */
function routeNow() {
  const m = /^#\/([a-z-]+)(?:\/([a-z-]+))?(?:\?(.*))?$/.exec(window.location.hash || '');
  if (!m) return mounted ? { space: mounted.space, tab: mounted.tab, params: mounted.params } : { space: SPACES[0], tab: SPACES[0].tabs[0], params: {} };
  let [, sid, tid, query] = m;
  if (LEGACY[sid] && !SPACES.some((s) => s.id === sid && s.tabs.some((t) => t.id === (tid || '')))) [sid, tid] = LEGACY[sid].split('/');
  const space = SPACES.find((s) => s.id === sid) || SPACES[0];
  const tab = space.tabs.find((t) => t.id === (tid || '')) || space.tabs[0];
  const params = {};
  for (const part of (query || '').split('&')) { const [k, v] = part.split('='); if (k) params[k] = decodeURIComponent(v || ''); }
  return { space, tab, params };
}
const hrefOf = (sid, tid = '', params = null) => `#/${sid}${tid ? `/${tid}` : ''}${params && Object.keys(params).length ? `?${Object.entries(params).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&')}` : ''}`;
function go(sid, tid = '', params = null) { window.location.hash = hrefOf(sid, tid, params); }

// ---- binario, barra del telefono, schede ---------------------------------------------------------------------------------

function navLink(sp) {
  const flag = h('span', { class: 'nav__flag' });
  flag.hidden = true;
  const a = h('a', { class: 'nav__link', href: hrefOf(sp.id), title: sp.label }, icon(sp.icon), h('span', { class: 'nav__label', text: sp.label }), flag,
    h('span', { class: 'nav__key', 'aria-hidden': 'true', text: `g ${sp.key}` }));
  a.flagEl = flag;
  return a;
}

function buildNav() {
  const drop = h('span', { class: 'nav__drop', 'aria-hidden': 'true' });
  el.nav.replaceChildren(drop);
  el.nav.dropEl = drop;
  links.clear();
  let group = null;
  for (const sp of SPACES) {
    if (sp.group !== group) { group = sp.group; el.nav.append(h('div', { class: 'nav__group', text: group })); }
    const a = navLink(sp);
    links.set(sp.id, [a]);
    el.nav.append(a);
  }
  // telefono: quattro spazi di ogni giorno + «Altro»
  const bd = el.dock.querySelector('.bd');
  el.dock.replaceChildren(...(bd ? [bd] : []));
  for (const sp of SPACES.slice(0, 4)) {
    const a = h('a', { href: hrefOf(sp.id) }, icon(sp.icon), h('span', { text: sp.label }));
    links.get(sp.id).push(a);
    el.dock.append(a);
  }
  const more = h('button', { type: 'button', 'aria-haspopup': 'dialog', id: 'more-btn' }, icon('more'), h('span', { text: 'Altro' }));
  more.addEventListener('click', () => openSheet(el.moreSheet));
  el.dock.append(more);
  el.moreBtn = more;
}

function markNav(space) {
  for (const [id, list] of links) for (const a of list) { if (id === space.id) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); }
  if (el.moreBtn) { if (SPACES.indexOf(space) > 3) el.moreBtn.setAttribute('aria-current', 'page'); else el.moreBtn.removeAttribute('aria-current'); }
  const active = links.get(space.id)[0];
  const drop = el.nav.dropEl;
  if (drop && active.offsetHeight) {
    drop.style.setProperty('--y', `${active.offsetTop}px`);
    drop.style.setProperty('--on', '1');
    if (!el.nav.classList.contains('is-ready')) requestAnimationFrame(() => el.nav.classList.add('is-ready'));
  }
}

/** Pallino accanto a una voce quando lì c'è qualcosa da guardare (con testo per i lettori di schermo). */
function setFlag(id, kind, text) {
  const a = (links.get(id) || [])[0];
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

let tabSeg = null;
let tabKey = '';
function syncTabs(route) {
  const key = `${route.space.id}:${level}`;
  if (key !== tabKey) {
    tabKey = key;
    tabSeg = null;
    el.tabs.replaceChildren();
    if (route.space.tabs.length > 1) {
      tabSeg = segmented({ label: `Schede di ${route.space.label}`, options: route.space.tabs.map((t) => ({ value: t.id, label: t.label })), value: route.tab.id, onChange: (v) => go(route.space.id, v) });
      el.tabs.append(tabSeg.el);
    }
  }
  if (tabSeg && tabSeg.value !== route.tab.id) tabSeg.set(route.tab.id);
}

// ---- fascia di stato --------------------------------------------------------------------------------------------------

function setText(node, text) {
  if (node.textContent !== text) node.textContent = text;
}
const gateDays = (snap) => arr(snap && snap.gates).find((g) => /giorni di paper/i.test(str(g.name)));

function syncChrome() {
  const st = store.state;
  const snap = st.snap;
  const meta = obj(snap && snap.meta);
  const fresh = st.status === 'ok';
  document.body.dataset.conn = st.status;

  // (1) modalità e provenienza: sempre visibili, con la forma del bordo che le distingue anche senza colore
  if (!snap) {
    el.modebar.dataset.kind = 'wait';
    el.modeTag.className = 'tag tag--wait';
    setText(el.modeTag, st.status === 'offline' ? 'Nessun dato' : 'In attesa dei dati');
    setText(el.modeLabel, '');
    setText(el.modeMeta, '');
  } else {
    const kind = modeKind(meta);
    const label = str(meta.data_label).trim();
    const demo = label.toUpperCase().startsWith('DEMO');
    el.modebar.dataset.kind = kind;
    el.modeTag.className = `tag tag--${demo ? 'demo' : kind === 'sim' ? 'sim' : kind === 'paper' ? 'paper' : kind === 'live' ? 'real' : 'unknown'}`;
    setText(el.modeTag, demo ? 'Esempio' : kind === 'sim' ? 'Simulato' : kind === 'paper' ? 'Paper' : kind === 'live' ? 'Reale' : 'Non dichiarato');
    const g = gateDays(snap);
    const day = g && num(g.value) != null && num(g.target) != null ? (g.value > g.target ? ` · giorno ${fmtNum(g.value, 0)} (minimo di ${fmtNum(g.target, 0)} superato)` : ` · giorno ${fmtNum(g.value, 0)} di ${fmtNum(g.target, 0)}`) : '';
    const mode = str(meta.mode).trim();
    fill(el.modeLabel, h('span', { class: 'band__text', text: label || 'Etichetta dei dati assente' }), h('span', { class: 'band__day', text: `${mode ? ` · ${mode}` : ' · modalità non dichiarata'}${day}` }));
    el.modeLabel.title = `${label || 'Etichetta dei dati assente'} · modalità ${mode || 'non dichiarata'}${day}`;
    const asOf = parseTs(meta.as_of);
    setText(el.modeMeta, `${asOf == null ? 'Ora dello snapshot assente' : `Snapshot del ${fmtDateTime(asOf)}`}${str(meta.version) ? ` · motore v${str(meta.version)}` : ''}`);
  }

  // (2) stato del rischio: con dati fermi diventa SCONOSCIUTO, mai l'ultimo «sicuro» visto
  if (snap) {
    const rs = riskState(snap.risk);
    if (fresh) lastSeen = { label: rs.label, t: st.receivedAt };
    const unknown = !fresh;
    const key = `${unknown ? 'unknown' : rs.code + rs.kind}`;
    el.pill.hidden = false;
    el.pill.className = `pill pill--${unknown ? 'unknown' : rs.code === 'KILLED' ? 'killed' : rs.kind}`;
    el.pill.setAttribute('aria-label', unknown ? 'Stato del rischio sconosciuto: i dati sono fermi. Apri Rischio' : `Stato del rischio: ${rs.label}. Apri Rischio`);
    if (el.pill.dataset.state !== key) {
      el.pill.dataset.state = key;
      fill(el.pill, icon(unknown ? 'help' : rs.icon), h('span', { text: unknown ? 'Sconosciuto' : rs.label }));
    }
    if (unknown) fill(el.why, lastSeen ? `ultimo visto: ${lastSeen.label} alle ${fmtDayTime(lastSeen.t)}` : 'nessuno stato visto con dati freschi');
    else fill(el.why, 'scala ', h('b', { text: SCALE[rs.code] || 'n.d.' }), ` · ${str(obj(snap.risk).state_reason).trim() || rs.text || 'motivo non dichiarato'}`);
    el.why.title = el.why.textContent;
  } else {
    el.pill.hidden = true;
    fill(el.why);
  }

  // (3) età dei dati: il punto respira solo se i dati sono freschi
  const age = store.ageSeconds();
  el.conn.dataset.state = st.status;
  let connText = 'Connessione…';
  if (st.status === 'ok') connText = isBacktest(meta) ? `backtest · generato ${fmtAgo(age)}` : `dati di ${fmtAgo(age)}`;
  else if (st.status === 'stale') connText = age == null ? 'Dati senza orario' : `Dati fermi da ${fmtDuration(age)}`;
  else if (st.status === 'offline') connText = 'Offline';
  // la fascia mostra la fonte più vecchia: un libro dei trade fermo non può stare dietro a «dati di adesso»
  const tbAge = oldestSource([tradebook ? { name: 'libro dei trade', day: parseTs(str(tradebook.asof)), kind: 'crypto' } : null, ...barDays], store.serverNow(), obj(obj(st.health).rules));
  if (st.status === 'ok' && tbAge) {
    connText = `fonte più vecchia: ${tbAge.name} del ${fmtDayMonth(tbAge.day, true)}${tbAge.count > 1 ? ` (+${tbAge.count - 1})` : ''}`;
    el.conn.dataset.state = 'stale';
  }
  setText(el.connText, connText);
  setText(el.connShort, st.status === 'ok' && tbAge ? `${tbAge.name.replace('libro dei trade', 'libro')} del ${fmtDayMonth(tbAge.day, true)}` : st.status === 'ok' ? fmtAgo(age) : st.status === 'stale' ? 'Fermi' : st.status === 'offline' ? 'Offline' : '…');

  // (4) sistema, solo se non tutto ok · (5) avvisi con contatore
  const comps = arr(obj(snap && snap.system).components);
  const bad = comps.filter((c) => componentStatus(c.status).kind !== 'ok');
  el.sys.hidden = !snap || !bad.length;
  if (bad.length) {
    fill(el.sys, icon('system', 'icon--sm'), h('span', { class: 'wide-only', text: 'Sistema ' }), h('span', { class: 'num', text: `${comps.length - bad.length} di ${comps.length}` }), h('span', { class: 'wide-only', text: ` · ${str(bad[0].name)}` }));
    el.sys.title = `Sistema: ${comps.length - bad.length} componenti su ${comps.length} a posto. Da guardare: ${bad.map((c) => str(c.name)).join(', ')}`;
    el.sys.setAttribute('aria-label', el.sys.title);
  }
  const alerts = arr(snap && snap.alerts);
  const serious = alerts.filter((a) => alertLevel(a.level).kind !== 'muted' && str(a.level).toLowerCase() !== 'info');
  el.alertsBtn.hidden = !snap;
  el.alertsBtn.dataset.kind = serious.some((a) => str(a.level).toLowerCase() === 'critical') ? 'crit' : serious.length ? 'warn' : 'none';
  setText(el.alertsN, String(serious.length));
  el.alertsBtn.setAttribute('aria-label', `Avvisi: ${serious.length} da guardare. Apri il centro avvisi`);

  // (6) KILL: dice prima se è utilizzabile
  const hl = obj(st.health);
  const ready = hl.kill_active === true ? 'active' : hl.kill_enabled === false ? 'no' : st.health ? 'yes' : 'wait';
  el.killBtn.dataset.ready = ready;
  setText(el.killState, ready === 'active' ? 'già attivo' : ready === 'no' ? 'serve il token' : ready === 'yes' ? 'pronto' : '…');
  setKillEnabled(hl.kill_enabled !== false);
  el.killBtn.title = ready === 'no' ? 'KILL spento su questo server (manca GERVA_DASH_TOKEN): la finestra spiega come fare a mano' : 'Apre la finestra di conferma: non invia';

  // riga in più: dati fermi, offline, stato critico. Mai numeri vecchi in silenzio.
  let bar = null;
  const rsNow = snap ? riskState(snap.risk) : null;
  if (snap && st.status === 'stale') {
    const asOf = parseTs(meta.as_of);
    bar = { kind: 'stale', icon: 'warn', title: 'Dati non aggiornati', text: asOf == null
      ? 'Lo snapshot non riporta l\'ora di aggiornamento: non si può verificare che i numeri siano attuali.'
      : `L'ultimo snapshot del motore è del ${fmtDateTime(asOf)}, oltre la soglia di ${fmtDuration(store.staleLimit())}. Lo stato del rischio è sconosciuto e i numeri qui sotto potrebbero non essere attuali.` };
  } else if (snap && st.status === 'offline') {
    bar = { kind: 'offline', icon: 'offline', title: 'Offline', text: `Il server della dashboard non risponde (${st.error}). I numeri qui sotto sono gli ultimi ricevuti, alle ${fmtDateTime(st.receivedAt)}. Nuovo tentativo ogni 5 secondi.` };
  } else if (rsNow && (rsNow.code === 'HALTED' || rsNow.code === 'KILLED')) {
    const key = `${rsNow.code}`;
    const taken = ack && ack.key === key;
    bar = { kind: 'crit', icon: 'crit', key, title: rsNow.code === 'KILLED' ? 'Arresto di emergenza attivo' : 'Motore sospeso',
      text: taken ? `Preso in carico alle ${fmtDayTime(ack.t)}. ${rsNow.text}`
        : `${str(obj(snap.risk).state_reason).trim() || rsNow.text} Il motore ha già ${rsNow.code === 'KILLED' ? 'chiuso tutto e si è fermato' : 'portato l\'esposizione al minimo'}. Tocca a te: guarda Rischio e il registro in Sistema.` };
  }
  el.connbar.hidden = !bar;
  if (bar) {
    el.connbar.dataset.kind = bar.kind;
    el.connbarIcon.setAttribute('href', `#i-${bar.icon}`);
    setText(el.connbarTitle, bar.title);
    setText(el.connbarText, bar.text);
    el.connbarAck.hidden = !(bar.kind === 'crit' && !(ack && ack.key === bar.key));
    el.connbarAck.dataset.key = bar.key || '';
    document.title = bar.kind === 'crit' ? `⚠ ${bar.title} · GERVA Capital` : document.title;
  }

  if (snap) {
    syncSources();
    syncFoot(snap);
    syncFlags(snap);
  }
}

/** Contatore di provenienza al piede del binario: quanti giorni simulati, in paper, reali stanno dietro ai numeri. */
function syncFoot(snap) {
  const meta = obj(snap.meta);
  const kind = modeKind(meta);
  const g = gateDays(snap);
  const perfDays = num(obj(snap.performance).days);
  const paperDays = g && num(g.value) != null ? g.value : null;
  // la storia prima dell'avvio del paper è simulata: giorni della curva meno giorni di paper
  const simDays = isBacktest(meta) ? perfDays : paperDays != null && perfDays != null && perfDays > paperDays ? perfDays - paperDays : num(obj(obj(store.state.quant).meta).days);
  const rows = [['Giorni simulati', simDays == null ? 'n.d.' : fmtNum(simDays, 0)], ['Giorni paper', g && num(g.value) != null ? fmtNum(g.value, 0) : kind === 'paper' && perfDays != null ? fmtNum(perfDays, 0) : '0'],
    ['Giorni reali', kind === 'live' && perfDays != null ? fmtNum(perfDays, 0) : '0']];
  const key = rows.map((r) => r[1]).join('|');
  if (el.foot.dataset.key === key) return;
  el.foot.dataset.key = key;
  fill(el.foot, rows.map(([k, v]) => h('div', null, h('span', { text: k }), h('b', { text: v }))));
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
  if (st.learnStatus === 'ok') {
    const lg = parseTs(str(obj(st.learn).generated).replace(' ', 'T').replace(/(\.\d+)?\+00:00$/, 'Z'));
    parts.push(`Apprendimento: letto ${fmtAgo(store.secondsSinceLearn())}${lg == null ? '' : `, rapporto di ${fmtAgo(Math.max(0, (store.serverNow() - lg) / 1000))}`}`);
  }
  setText(el.sources, parts.join('  ·  '));
}

// ---- livello di lettura -------------------------------------------------------------------------------------------------

const levelSegs = [];
function applyLevel(v, { announce = false } = {}) {
  if (!LEVELS.includes(v)) return;
  level = v;
  savePref('level', v);
  document.body.dataset.level = shownLevel();
  for (const seg of levelSegs) seg.set(v);
  summaryOpen = false;
  tabKey = '';
  syncView({ force: true });
  requestAnimationFrame(() => markNav(routeNow().space));
  if (announce) say(v === 'terminale' && narrow() ? 'Terminale non è disponibile su questo schermo: mostro il livello Esperto.' : `Livello ${LEVEL_LABEL[v]}`);
}

function levelSeg(cls = '') {
  const seg = segmented({ label: 'Livello di lettura', cls, options: LEVELS.map((v) => ({ value: v, label: LEVEL_LABEL[v] })), value: level, onChange: (v) => applyLevel(v, { announce: true }) });
  levelSegs.push(seg);
  return seg.el;
}

const live = h('div', { class: 'sr-only', role: 'status', 'aria-live': 'polite' });
function say(text) { live.textContent = ''; requestAnimationFrame(() => { live.textContent = text; }); }

// ---- fogli: glossario, avvisi, scorciatoie, «Altro» -------------------------------------------------------------------

function openSheet(dlg) {
  if (!dlg || dlg.open) return;
  hideTip();
  if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', '');
}

function openGlossary(id) {
  openSheet(el.glossary);
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

function openAlerts() {
  const snap = store.state.snap;
  const now = store.serverNow();
  const list = arr(snap && snap.alerts);
  fill(el.alertsList, list.length ? list.map((a) => {
    const lv = str(a.level).toLowerCase();
    const t = parseTs(a.t);
    return h('div', { class: 'alert', dataset: { level: lv } }, icon(lv === 'critical' ? 'crit' : lv === 'warn' ? 'warn' : 'info'),
      h('div', null, h('div', { class: 'alert__msg', text: str(a.msg) || '—' }), h('div', { class: 'alert__when', text: `${alertLevel(a.level).label}${t == null ? '' : ` · ${fmtAgo(Math.max(0, (now - t) / 1000))} · ${fmtDayTime(t)}`}` })));
  }) : h('p', { class: 'placeholder__text', text: 'Nessun avviso nel registro.' }));
  openSheet(el.alertsSheet);
}

function initSheets() {
  el.glossaryBody.append(glossaryList());
  el.glossaryBtn.addEventListener('click', () => openGlossary(null));
  el.glossaryClose.addEventListener('click', () => el.glossary.close());
  for (const dlg of [el.glossary, el.alertsSheet, el.keysSheet, el.moreSheet]) {
    dlg.addEventListener('click', (e) => { if (e.target === dlg || (e.target instanceof Element && e.target.closest('[data-close]'))) dlg.close(); });
  }
  el.alertsBtn.addEventListener('click', openAlerts);
  fill(el.keysList, SHORTCUTS.map(([k, v]) => h('div', null, h('dt', null, k.split(' · ').flatMap((part, i) => [i ? ' · ' : null, h('kbd', { text: part })])), h('dd', { text: v }))));
  // foglio «Altro» del telefono: gli altri spazi, livello, tema, cerca, glossario
  const moreNav = h('div', { class: 'more__nav' }, SPACES.slice(4).map((sp) => {
    const a = h('a', { class: 'nav__link', href: hrefOf(sp.id) }, icon(sp.icon), h('span', { class: 'nav__label', text: sp.label }));
    a.addEventListener('click', () => el.moreSheet.close());
    return a;
  }));
  const act = (label, ico, fn) => { const b = h('button', { class: 'btn btn--sm btn--ghost', type: 'button' }, icon(ico, 'icon--sm'), label); b.addEventListener('click', () => { el.moreSheet.close(); fn(); }); return b; };
  fill(el.moreBody, moreNav, h('div', null, h('div', { class: 'micro', text: 'Livello di lettura' }), h('div', { class: 'more__row' }, levelSeg('seg--block seg--lg'))),
    h('div', { class: 'more__row' }, act('Cerca', 'search', () => palette.open()), act('Glossario e guida', 'book', () => openGlossary(null)), act('Avvisi', 'bell', openAlerts), act('Tema', 'sun', toggleTheme)));
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
}

// ---- KILL: la finestra si apre soltanto; l'anteprima dice che cosa farebbe ----------------------------------------------

function killPreview() {
  const snap = store.state.snap;
  const hl = obj(store.state.health);
  const ccy = str(obj(snap && snap.meta).base_ccy) || 'EUR';
  const pos = arr(snap && snap.positions);
  const gross = pos.reduce((a, p) => a + Math.abs(num(p.value) || 0), 0);
  const open = Object.keys(obj(obj(tradebook).open));
  const lines = [
    hl.kill_active === true ? ['Il file KILL è già presente: ', h('b', { text: 'il motore è fermo o si ferma al prossimo ciclo.' })]
      : hl.kill_enabled === false ? [h('b', { text: 'Comando spento su questo server' }), ' (manca GERVA_DASH_TOKEN): crea il file KILL a mano nella cartella del motore.'] : ['Stato del comando: ', h('b', { text: 'pronto' }), '.'],
    snap ? ['Chiude ', h('b', { text: `${fmtNum(pos.length, 0)} posizioni` }), ` per circa ${fmtMoney(gross, ccy, { digits: 0 })} di controvalore`, tradebook ? [' e ', h('b', { text: `${fmtNum(open.length, 0)} trade a leva aperti` }), open.length ? ` (${open.join(', ')})` : ''] : '', '.'] : ['Posizioni: dato non disponibile.'],
    ['Entro quando: al ciclo successivo del motore (uno ogni 15 minuti).'],
    ['Che cosa non fa: non cancella gli ordini già eseguiti e non si annulla da qui. Per ripartire: togliere il file a mano e dare ', h('code', { text: 'gerva reset-kill' }), '.'],
  ];
  setKillPreview(lines.map((kids) => h('li', null, h('span', null, kids))));
}
function showKill() {
  killPreview();
  openKill();
  getTradebook().then((tb) => { tradebook = tb || null; killPreview(); });
}

// ---- spazio corrente ----------------------------------------------------------------------------------------------------

function placeholder() {
  const st = store.state;
  mounted = null;
  el.summary.hidden = true;
  el.summaryBtn.hidden = true;
  if (st.status === 'offline') {
    fill(el.view, h('div', { class: 'placeholder placeholder--offline glass', role: 'alert' },
      icon('offline', 'icon--xl'),
      h('p', { class: 'placeholder__title', text: 'Server non raggiungibile' }),
      h('p', { class: 'placeholder__text', text: `Nessun dato da mostrare (${st.error}). Nuovo tentativo ogni 5 secondi.` }),
      h('p', { class: 'placeholder__text' }, 'Avvio del server: ', h('code', { text: 'python -m dashboard.server' }))));
  } else {
    fill(el.view, h('div', { class: 'placeholder glass' }, h('p', { class: 'placeholder__title', text: 'Caricamento dei dati…' })));
  }
}

function context(route) {
  const st = store.state;
  const lv = shownLevel();
  return {
    snap: st.snap, health: st.health, status: st.status, now: store.serverNow(), ccy: str(obj(st.snap.meta).base_ccy) || 'EUR',
    quant: st.quant, quantStatus: st.quantStatus, quant4: st.quant4, quant4Status: st.quant4Status, learn: st.learn, learnStatus: st.learnStatus,
    level: lv === 'terminale' ? 'esperto' : lv,           // le viste precedenti conoscono due livelli
    lv, params: route.params, fresh: st.status === 'ok',
  };
}

const api = {
  killResult: lastKill,
  go, hrefOf, openKill: showKill, openAlerts, openGlossary,
  setParams(params) { const r = routeNow(); const next = hrefOf(r.space.id, r.tab.id, { ...r.params, ...params }); if (next !== window.location.hash) window.history.replaceState(null, '', next); if (mounted) mounted.params = { ...r.params, ...params }; },
};

/** Ingresso dei riquadri: da sfocati a nitidi, in sequenza nell'ordine di lettura (al massimo 8, poi insieme). */
function enter(root) {
  if (!motionOn()) return;
  const cards = [...root.querySelectorAll('.card, .glass')].filter((c) => !c.parentElement.closest('.card, .glass'));
  cards.forEach((c, i) => {
    c.style.setProperty('--i', String(Math.min(i, 8)));
    c.classList.add('enter');
    c.addEventListener('animationend', () => c.classList.remove('enter'), { once: true });
  });
}

function mount(route) {
  hideTip();
  if (mounted && mounted.handle && typeof mounted.handle.destroy === 'function') {
    try { mounted.handle.destroy(); } catch (err) { console.error(err); }
  }
  fill(el.view);
  el.view.classList.remove('is-leaving');
  const key = `${route.space.id}/${route.tab.id}`;
  try {
    mounted = { key, space: route.space, tab: route.tab, params: route.params, handle: route.tab.view.mount(el.view, api) };
  } catch (err) {
    console.error(err);
    mounted = { key, space: route.space, tab: route.tab, params: route.params, handle: null };
  }
  window.scrollTo(0, 0);
}

function syncView({ force = false, focus = false, entered = false } = {}) {
  const st = store.state;
  const route = routeNow();
  const key = `${route.space.id}/${route.tab.id}`;
  const label = route.tab.id ? `${route.space.label} · ${route.tab.label}` : route.space.label;
  setText(el.title, route.space.label);
  document.title = `${label} · GERVA Capital`;
  document.body.dataset.route = route.space.id;
  document.body.dataset.tab = route.tab.id;
  markNav(route.space);
  syncTabs(route);
  setText(el.date, route.space.id === 'oggi' && st.snap ? `${new Intl.DateTimeFormat('it-IT', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date(store.serverNow()))} · ${new Intl.DateTimeFormat('it-IT', { hour: '2-digit', minute: '2-digit' }).format(new Date(store.serverNow()))}` : '');
  if (!st.snap) {
    placeholder();
    return;
  }
  let fresh = false;
  if (!mounted || mounted.key !== key) {
    if (mounted && motionOn() && !leaving && !entered && el.view.childElementCount) {            // uscita breve, poi i nuovi riquadri entrano in sequenza
      leaving = true;
      el.view.classList.add('is-leaving');
      setTimeout(() => { leaving = false; syncView({ force: true, focus, entered: true }); }, 130);
      return;
    }
    if (leaving) return;
    mount(route);
    fresh = true;
  } else if (mounted) {
    mounted.params = route.params;
  }
  if (fresh || force || Date.now() - lastViewUpdate > VIEW_REFRESH_MS) {
    lastViewUpdate = Date.now();
    hideTip();
    try {
      if (!mounted.handle) throw new Error('sezione non disponibile');
      const c = context(route);
      mounted.handle.update(c);
      const line = typeof mounted.handle.summary === 'function' ? mounted.handle.summary(c) : '';
      const lv = shownLevel();
      el.summaryBtn.hidden = !line || lv === 'semplice';
      el.summaryBtn.setAttribute('aria-expanded', String(summaryOpen));
      el.summary.hidden = !line || (lv !== 'semplice' && !summaryOpen);
      fill(el.summary, line ? h('span', { class: 'summary__tag', text: 'In una frase' }) : null, line || null);
    } catch (err) {
      console.error(err);
      mounted = null;
      fill(el.view, h('div', { class: 'placeholder placeholder--offline glass', role: 'alert' },
        icon('crit', 'icon--xl'),
        h('p', { class: 'placeholder__title', text: 'Questo spazio non può essere mostrato' }),
        h('p', { class: 'placeholder__text', text: 'Lo snapshot contiene un dato che la pagina non sa leggere. Gli altri spazi restano disponibili.' })));
    }
    if (fresh) enter(el.view);
  }
  if (focus) el.title.focus({ preventScroll: true });
}

// ---- tastiera -----------------------------------------------------------------------------------------------------------

let gPending = 0;
function onKey(e) {
  if ((e.key === 'k' || e.key === 'K') && (e.ctrlKey || e.metaKey)) { e.preventDefault(); palette.open(); return; }
  if (e.key === 'Escape') {
    for (const d of document.querySelectorAll('details.what[open]')) {
      d.removeAttribute('open');
      const sm = d.querySelector('summary');
      if (sm && d.contains(document.activeElement)) sm.focus();
    }
    return;
  }
  const t = e.target;
  if (e.ctrlKey || e.metaKey || e.altKey || document.querySelector('dialog[open]')) return;
  if (t instanceof HTMLElement && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;       // i tasti a lettera singola sono spenti mentre si scrive
  if (e.key === 'K' && e.shiftKey) { e.preventDefault(); showKill(); return; }
  if (gPending && Date.now() - gPending < 1200) {
    gPending = 0;
    const sp = SPACES.find((s) => s.key === e.key);
    if (sp) { e.preventDefault(); go(sp.id); return; }
    if (e.key === 't') { e.preventDefault(); go('mercati', '', { v: 'libro' }); return; }
    if (e.key === 'b') { e.preventDefault(); go('sistema', 'ordini'); return; }
  }
  if (e.key === 'g') { gPending = Date.now(); return; }
  if (e.key === '/') { e.preventDefault(); palette.open(); }
  else if (e.key === '?') { e.preventDefault(); openSheet(el.keysSheet); }
  else if (e.key === 'a') { e.preventDefault(); openAlerts(); }
  else if (e.key === 'l') { e.preventDefault(); applyLevel(LEVELS[(LEVELS.indexOf(level) + 1) % LEVELS.length], { announce: true }); }
  else if (e.key === 'i') { e.preventDefault(); toggleSummary(); }
  else if (e.key === 'x' && !el.connbarAck.hidden) { e.preventDefault(); el.connbarAck.click(); }
}
function toggleSummary() {
  if (shownLevel() === 'semplice') return;
  summaryOpen = !summaryOpen;
  syncView({ force: true });
}

// ---- vetro pieno o leggero: scelta dell'utente, altrimenti misurata all'avvio ---------------------------------------------

/** 'on' vetro pieno · 'off' leggero · senza scelta: si misura. Se un fotogramma costa più di 34 ms i pannelli diventano pieni. */
function setGlass(mode) {
  savePref('glass', mode);
  document.documentElement.classList.toggle('lite', mode === 'off' || mode === 'auto-off');
}
function toggleGlass() {
  const lite = document.documentElement.classList.contains('lite');
  setGlass(lite ? 'on' : 'off');
  say(lite ? 'Vetro pieno.' : 'Vetro leggero: pannelli pieni, più fluido.');
}
function probeGlass() {
  const pref = loadPref('glass', '');
  if (pref === 'on' || pref === 'off' || !motionOn()) return;
  document.documentElement.classList.remove('lite');                 // si rimisura a ogni avvio partendo dal vetro pieno
  const ts = [];
  const tick = (t) => {
    ts.push(t);
    // a ogni fotogramma il fondale si sposta di un soffio: così si misura il costo vero del vetro che si ricalcola
    el.aurora.style.setProperty('--px', ts.length % 2 ? '0.02' : '0');
    if (ts.length < 24) { requestAnimationFrame(tick); return; }
    el.aurora.style.setProperty('--px', '0');
    const d = ts.slice(4).map((v, i) => v - ts[i + 3]).sort((a, b) => a - b);
    setGlass(d[Math.floor(d.length / 2)] > 34 ? 'auto-off' : 'auto-on');
  };
  setTimeout(() => requestAnimationFrame(tick), 1800);                 // dopo l'ingresso dei riquadri
}

// ---- fondale: parallasse a passi, fermo a scheda nascosta ---------------------------------------------------------------

function initBackdrop() {
  document.addEventListener('visibilitychange', () => document.body.classList.toggle('is-still', document.hidden));
  if (!motionOn() || !window.matchMedia('(pointer: fine)').matches) return;
  let last = 0;
  window.addEventListener('pointermove', (e) => {
    const now = e.timeStamp;
    if (now - last < 160) return;                       // pochi passi al secondo: il vetro non va ricalcolato a 60 fps
    last = now;
    el.aurora.style.setProperty('--px', ((e.clientX / window.innerWidth) * 2 - 1).toFixed(3));
    el.aurora.style.setProperty('--py', ((e.clientY / window.innerHeight) * 2 - 1).toFixed(3));
  }, { passive: true });
}

// ---- avvio -----------------------------------------------------------------------------------------------------------

document.body.append(live);
document.body.dataset.level = shownLevel();
buildNav();
applyTheme(currentTheme(), false);
el.themeBtn.addEventListener('click', toggleTheme);
el.levelHost.append(levelSeg());
initSheets();
const palette = initPalette({
  spaces: () => SPACES, go, openSymbol: (s) => go('mercati', '', { s }), setLevel: (v) => applyLevel(v, { announce: true }), toggleTheme,
  openGlossary, openAlerts, openKill: showKill, openKeys: () => openSheet(el.keysSheet), toggleGlass,
});
el.searchBtn.addEventListener('click', () => palette.open());
el.killBtn.addEventListener('click', showKill);
el.summaryBtn.addEventListener('click', toggleSummary);
el.connbarAck.addEventListener('click', () => { ack = { key: el.connbarAck.dataset.key, t: Date.now() }; syncChrome(); say('Preso in carico.'); });
document.addEventListener('keydown', onKey);
document.querySelector('.skip-link').addEventListener('click', (event) => {
  event.preventDefault();                     // niente cambio di hash: gli spazi vivono lì
  el.main.focus();
  el.main.scrollIntoView({ block: 'start' });
});
initKill({
  done: () => {
    store.refreshHealth();
    syncView({ force: true });
  },
});
initBackdrop();
probeGlass();
syncChrome();
syncView();

store.subscribe((state, dataChanged) => {
  if (dataChanged) getTradebook().then((tb) => {                                    // età del libro dei trade e delle barre per la fascia (cache nel browser)
    tradebook = tb || null;
    getSymbols().then((res) => new Set(arr(res && res.symbols).map((x) => str(x.symbol)))).then((have) => Promise.all(watchedSymbols(state.snap, tradebook).filter((w) => have.has(w.symbol)).slice(0, 12).map((w) => getOhlc(w.symbol, 5).then((o) => (o && o.t && o.t.length ? { name: `barre ${w.symbol}`, day: o.t[o.t.length - 1], kind: w.kind } : null)).catch(() => null)))).then((rows) => { barDays = rows.filter(Boolean); });
  });
  syncChrome();
  syncView({ force: dataChanged });
});
window.addEventListener('hashchange', () => syncView({ focus: true }));
window.addEventListener('resize', () => { if (document.body.dataset.level !== shownLevel()) applyLevel(level); else markNav(routeNow().space); });
setInterval(() => {
  store.reevaluate();
  syncChrome();
  if (store.state.snap && Date.now() - lastViewUpdate > VIEW_REFRESH_MS) syncView();
}, 1000);
store.start();
