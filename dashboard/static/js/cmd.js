// Barra dei comandi (/ oppure Ctrl+K): scrivi il nome di una pagina, uno strumento (BTC, SPY) o un comando.
// Frecce + Invio. «?» mostra le scorciatoie. I tasti 1–9 saltano alle pagine nell'ordine del menu.
// Nessun comando scrive qualcosa: «kill» porta soltanto al riquadro del KILL, che resta protetto da token e conferma.

import { h } from './dom.js';
import { getSymbols } from './market.js';

const SHORTCUTS = [
  ['/', 'apre la barra dei comandi'], ['Ctrl + K', 'apre la barra dei comandi'], ['1 … 9', 'vai alla pagina in quella posizione del menu'],
  ['?', 'mostra queste scorciatoie'], ['Esc', 'chiude finestre e riquadri'], ['← →', 'sul grafico: sposta il mirino'],
  ['Maiusc + ← →', 'sul grafico a candele: scorre nel tempo'], ['+ −', 'sul grafico a candele: zoom'], ['Inizio / Fine', 'sul grafico: primo e ultimo giorno'],
];

export function initCommandBar({ routes, go, openSymbol, setLevel, toggleTheme, openGlossary }) {
  const dialog = document.getElementById('cmdk');
  const input = document.getElementById('cmdk-input');
  const listEl = document.getElementById('cmdk-list');
  const help = document.getElementById('cmdk-help');
  if (!dialog || !input) return { open() {} };
  let items = [];
  let active = 0;
  let symbols = [];

  const commands = () => [
    { kind: 'Comando', label: 'kill', hint: 'va al riquadro del KILL nella pagina Rischio (non lo esegue)', run: () => { go('rischio'); setTimeout(() => { const b = document.querySelector('.killzone button'); if (b) { b.scrollIntoView({ block: 'center' }); b.focus(); } }, 150); } },
    { kind: 'Livello', label: 'semplice', hint: 'spiegazioni in chiaro', run: () => setLevel('semplice') },
    { kind: 'Livello', label: 'esperto', hint: 'colonne e note di metodo', run: () => setLevel('esperto') },
    { kind: 'Livello', label: 'terminale', hint: 'tema da terminale, densità compatta', run: () => setLevel('terminale') },
    { kind: 'Comando', label: 'tema', hint: 'cambia tra chiaro e scuro', run: () => toggleTheme() },
    { kind: 'Comando', label: 'glossario', hint: 'apre il glossario', run: () => openGlossary() },
    { kind: 'Comando', label: '?', hint: 'scorciatoie da tastiera', run: () => showHelp(true), keep: true },
  ];

  function build(query) {
    const q = query.trim().toLowerCase();
    const pages = routes().map((r, i) => ({ kind: 'Pagina', label: r.label, hint: i < 9 ? `tasto ${i + 1}` : '', run: () => go(r.id) }));
    const syms = symbols.map((s) => ({ kind: 'Strumento', label: s.symbol, hint: `${s.kind} · apre il grafico nel terminale`, run: () => openSymbol(s.symbol) }));
    const all = [...pages, ...commands(), ...(q ? syms : [])];
    if (!q) return all;
    const score = (it) => { const l = it.label.toLowerCase(); return l === q ? 0 : l.startsWith(q) ? 1 : l.includes(q) ? 2 : it.hint.toLowerCase().includes(q) ? 3 : 9; };
    return all.map((it) => ({ it, s: score(it) })).filter((x) => x.s < 9).sort((a, b) => a.s - b.s).map((x) => x.it).slice(0, 12);
  }

  function paint() {
    listEl.replaceChildren(...items.map((it, i) => {
      const li = h('li', { class: `cmdk__item ${i === active ? 'is-active' : ''}`.trim(), role: 'option', id: `cmdk-opt-${i}`, 'aria-selected': String(i === active) },
        h('span', { class: 'cmdk__kind', text: it.kind }), h('span', { class: 'cmdk__label', text: it.label }), h('span', { class: 'cmdk__hint', text: it.hint }));
      li.addEventListener('click', () => run(i));
      return li;
    }));
    if (!items.length) listEl.append(h('li', { class: 'cmdk__none', text: 'Nessuna corrispondenza. Prova il nome di una pagina, uno strumento (BTC) o «?».' }));
    input.setAttribute('aria-activedescendant', items.length ? `cmdk-opt-${active}` : '');
    const el = listEl.children[active];
    if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' });
  }

  function showHelp(on) {
    help.hidden = !on;
    listEl.hidden = on;
    if (on && !help.firstChild) help.append(h('dl', { class: 'cmdk__keys' }, SHORTCUTS.map(([k, t]) => h('div', null, h('dt', null, h('kbd', { text: k })), h('dd', { text: t })))));
  }

  function run(i) {
    const it = items[i];
    if (!it) return;
    if (!it.keep) dialog.close();
    it.run();
  }

  function open(query = '') {
    if (dialog.open) return;
    input.value = query;
    showHelp(query === '?');
    items = build(query === '?' ? '' : query);
    active = 0;
    paint();
    if (typeof dialog.showModal === 'function') dialog.showModal(); else dialog.setAttribute('open', '');
    input.focus();
    getSymbols().then((s) => { symbols = s && Array.isArray(s.symbols) ? s.symbols : []; });
  }

  input.addEventListener('input', () => {
    const q = input.value;
    showHelp(q.trim() === '?');
    items = build(q.trim() === '?' ? '' : q);
    active = 0;
    paint();
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); active = Math.min(items.length - 1, active + 1); paint(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); active = Math.max(0, active - 1); paint(); }
    else if (e.key === 'Enter') { e.preventDefault(); if (input.value.trim() === '?') return; run(active); }
  });
  dialog.addEventListener('click', (e) => { if (e.target === dialog) dialog.close(); });

  document.addEventListener('keydown', (e) => {
    const t = e.target;
    const typing = t instanceof HTMLElement && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName));
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); open(); return; }
    if (typing || e.ctrlKey || e.metaKey || e.altKey || document.querySelector('dialog[open]')) return;
    if (e.key === '/') { e.preventDefault(); open(); }
    else if (e.key === '?') { e.preventDefault(); open('?'); }
    else if (/^[1-9]$/.test(e.key) && !(t instanceof Element && t.closest('.cx, .chart'))) {
      const r = routes()[Number(e.key) - 1];
      if (r) { e.preventDefault(); go(r.id); }
    }
  });

  return { open };
}
