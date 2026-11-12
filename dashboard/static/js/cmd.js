// Tavolozza (/ oppure Ctrl/Cmd+K): quattro gruppi in ordine fisso — strumenti, spazi e schede, glossario, azioni.
// Nessuna voce scrive qualcosa: «KILL» apre soltanto la finestra protetta da token e conferma, senza inviare.
// ↑ ↓ scelgono, Invio apre, Tab salta al gruppo successivo, Esc chiude e rende il fuoco a dove era.

import { h, icon } from './dom.js';
import { GLOSSARY } from './glossary.js';
import { getSymbols } from './market.js';

export const SHORTCUTS = [
  ['/ · Ctrl K', 'cerca e vai (tavolozza)'], ['g poi o m p r e a s', 'vai allo spazio: Oggi, Mercati, Portafoglio, Rischio, Evidenza, Apprendimento, Sistema'],
  ['g t · g b', 'libro dei trade · ordini'], ['l', 'cambia livello di lettura'], ['i', '«In una frase» dello spazio'], ['a', 'centro avvisi'],
  ['?', 'queste scorciatoie'], ['Maiusc K', 'apre la finestra del KILL (non invia)'], ['Esc', 'chiude, torna, toglie il mirino'],
  ['← →', 'sul grafico: mirino di una barra (Maiusc × 10)'], ['+ − 0', 'sul grafico: zoom e ripristino'], ['1 … 5', 'in Mercati: intervalli 1M 3M 6M 1A Tutto'],
  ['[ ]', 'in Mercati: trade precedente / successivo'], ['j k', 'in Mercati: strumento successivo / precedente'],
];

export function initPalette({ spaces, go, openSymbol, setLevel, toggleTheme, openGlossary, openAlerts, openKill, openKeys, toggleGlass }) {
  const dialog = document.getElementById('cmdk');
  const input = document.getElementById('cmdk-input');
  const listEl = document.getElementById('cmdk-list');
  if (!dialog || !input || !listEl) return { open() {} };
  let items = [];
  let active = 0;
  let symbols = [];

  function build(query) {
    const q = query.trim().toLowerCase();
    const groups = [
      ['Strumenti', symbols.map((s) => ({ ico: 'trade', label: s.symbol, hint: `${s.kind} · apre il grafico in Mercati`, run: () => openSymbol(s.symbol) }))],
      ['Spazi e schede', spaces().flatMap((sp) => sp.tabs.map((t) => ({ ico: sp.icon, label: t.id ? `${sp.label} · ${t.label}` : sp.label, hint: t.id ? '' : `g ${sp.key}`, run: () => go(sp.id, t.id) })))],
      ['Glossario', GLOSSARY.map((g) => ({ ico: 'book', label: g.term, hint: g.short, run: () => openGlossary(g.id) }))],
      ['Azioni', [
        { ico: 'level', label: 'Livello Semplice', hint: 'frasi in chiaro, un numero protagonista', run: () => setLevel('semplice') },
        { ico: 'level', label: 'Livello Esperto', hint: 'colonne, errori, note di metodo', run: () => setLevel('esperto') },
        { ico: 'level', label: 'Livello Terminale', hint: 'più riquadri, meno testo', run: () => setLevel('terminale') },
        { ico: 'sun', label: 'Cambia tema', hint: 'scuro (predefinito) o chiaro', run: () => toggleTheme() },
        { ico: 'circle', label: 'Vetro pieno o leggero', hint: 'leggero = pannelli pieni, più fluido sulle macchine lente', run: () => toggleGlass() },
        { ico: 'bell', label: 'Apri gli avvisi', hint: 'tasto a', run: () => openAlerts() },
        { ico: 'help', label: 'Scorciatoie da tastiera', hint: 'tasto ?', run: () => openKeys() },
        { ico: 'power', label: 'Apri la finestra del KILL', hint: 'non invia: servono token e conferma', run: () => openKill() },
      ]],
    ];
    const score = (it) => { const l = it.label.toLowerCase(); return l === q ? 0 : l.startsWith(q) ? 1 : l.includes(q) ? 2 : it.hint.toLowerCase().includes(q) ? 3 : 9; };
    const out = [];
    for (const [name, list] of groups) {
      let rows = list;
      if (q) rows = list.map((it) => ({ it, s: score(it) })).filter((x) => x.s < 9).sort((a, b) => a.s - b.s).map((x) => x.it);
      else if (name === 'Glossario') rows = [];
      else if (name === 'Strumenti') rows = list.slice(0, 5);
      rows.slice(0, q ? 8 : 12).forEach((it) => out.push({ ...it, group: name }));
    }
    return out;
  }

  function paint() {
    listEl.replaceChildren();
    if (!items.length) { listEl.append(h('p', { class: 'cmdk__none', text: 'Nessun risultato. Prova con un simbolo (BTC), uno spazio (rischio) o un termine (drawdown).' })); return; }
    let group = null;
    items.forEach((it, i) => {
      if (it.group !== group) { group = it.group; listEl.append(h('div', { class: 'cmdk__group', text: group })); }
      const row = h('div', { class: `cmdk__item ${i === active ? 'is-active' : ''}`.trim(), role: 'option', id: `cmdk-o${i}`, 'aria-selected': String(i === active) },
        icon(it.ico), h('span', { class: 'cmdk__label', text: it.label }), h('span', { class: 'cmdk__hint', text: it.hint }));
      row.addEventListener('click', () => run(i));
      row.addEventListener('pointermove', () => { if (active !== i) { active = i; mark(); } });
      listEl.append(row);
    });
    mark();
  }
  function mark() {
    listEl.querySelectorAll('.cmdk__item').forEach((row, i) => {
      row.classList.toggle('is-active', i === active);
      row.setAttribute('aria-selected', String(i === active));
      if (i === active) { input.setAttribute('aria-activedescendant', row.id); row.scrollIntoView({ block: 'nearest' }); }
    });
  }
  function run(i) {
    const it = items[i];
    if (!it) return;
    dialog.close();
    it.run();
  }
  function open(query = '') {
    if (dialog.open) return;
    input.value = query;
    items = build(query);
    active = 0;
    paint();
    dialog.showModal();
    input.focus();
    getSymbols().then((res) => { if (res && Array.isArray(res.symbols)) { symbols = res.symbols; if (dialog.open) { items = build(input.value); active = Math.min(active, Math.max(0, items.length - 1)); paint(); } } });
  }

  input.addEventListener('input', () => { items = build(input.value); active = 0; paint(); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); active = Math.min(items.length - 1, active + 1); mark(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); active = Math.max(0, active - 1); mark(); }
    else if (e.key === 'Enter') { e.preventDefault(); run(active); }
    else if (e.key === 'Tab' && items.length) {
      e.preventDefault();
      const cur = items[active].group;
      let next = items.findIndex((it, i) => i > active && it.group !== cur);
      if (e.shiftKey || next < 0) next = 0;
      active = next;
      mark();
    }
  });
  dialog.addEventListener('click', (e) => { if (e.target === dialog) dialog.close(); });
  return { open };
}
