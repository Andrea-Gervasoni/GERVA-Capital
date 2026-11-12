// Pezzi di interfaccia riusati dalle sezioni: schede, cifre, chip di stato, tabelle ordinabili, stati vuoti.

import { h, icon, fill } from './dom.js';
import { DASH, fmtMoney, fmtPctSigned, signOf, str } from './format.js';
import { gloss } from './glossary.js';

/** Spiegazione in parole semplici (solo nel livello Semplice); i termini del glossario diventano cliccabili. */
export function explain(text, cls = '') {
  return h('p', { class: `explain only-semplice ${cls}`.trim() }, gloss(text));
}

/** Nota di metodo (solo nel livello Esperto). */
export function method(text, cls = '') {
  return h('p', { class: `method only-esperto ${cls}`.trim() }, h('span', { class: 'method__tag', text: 'Metodo' }), gloss(text));
}

/** Etichetta fissa per tutto ciò che viene dalla ricerca: non è un conto vero. */
export function simTag(label) {
  return h('span', { class: 'tag tag--sim simtag', text: str(label).trim() || 'SIMULATO: ricerca su dati storici' });
}

/** «Che cosa significa?»: riquadro a comparsa accanto al titolo (elemento nativo, raggiungibile da tastiera). */
export function what(text) {
  return h('details', { class: 'what only-semplice' },
    h('summary', { class: 'what__btn' }, icon('info'), h('span', { text: 'Che cosa significa?' })),
    h('div', { class: 'what__panel' }, h('p', null, gloss(text))));
}

/** Scheda con intestazione. Ritorna { el, body, head, sub } per riempirla dopo. */
export function card({ title, sub = '', actions = null, cls = '', flush = false, what: whatText = '', method: methodText = '', sim = '' } = {}) {
  const subEl = h('p', { class: 'card__sub', text: sub });
  subEl.hidden = !sub;
  const head = h('header', { class: 'card__head' },
    h('div', { class: 'card__titles' },
      h('div', { class: 'card__title-row' }, h('h2', { class: 'card__title', text: title }), sim ? simTag(sim === true ? '' : sim) : null, whatText ? what(whatText) : null),
      subEl, methodText ? method(methodText) : null),
    actions ? h('div', { class: 'card__actions' }, actions) : null);
  const body = h('div', { class: `card__body ${flush ? 'card__body--flush' : ''}`.trim() });
  const el = h('section', { class: `card ${cls}`.trim() }, title ? head : null, body);
  return {
    el,
    body,
    head,
    setSub(text) {
      subEl.textContent = text || '';
      subEl.hidden = !text;
    },
  };
}

/** Cifra con etichetta: l'etichetta sopra, il valore grande, una riga di contesto sotto. */
export function stat({ label, value, sub = null, cls = '', hint = '', explain: why = '' }) {
  return h('div', { class: `stat ${cls}`.trim(), title: hint || null },
    h('div', { class: 'stat__label', text: label }),
    h('div', { class: 'stat__value num' }, value == null ? DASH : value),
    sub == null || sub === '' ? null : h('div', { class: 'stat__sub' }, sub),
    why ? h('p', { class: 'stat__explain only-semplice' }, gloss(why)) : null);
}

/**
 * Valore con segno: colore verde/rosso, segno + / − nel testo e freccia. Il colore non è mai l'unico canale.
 * text è già formattato (con il segno); value decide direzione e colore.
 */
export function signed(value, text, { arrow = true, cls = '' } = {}) {
  const sg = signOf(value);
  if (sg == null) return h('span', { class: `num muted ${cls}`.trim(), text: DASH });
  const tone = sg > 0 ? 'pos' : sg < 0 ? 'neg' : 'flat';
  return h('span', { class: `pnl pnl--${tone} num ${cls}`.trim() },
    arrow && sg !== 0 ? icon(sg > 0 ? 'up' : 'down', 'icon--solid pnl__arrow') : null,
    h('span', { text }));
}

export const signedPct = (v, digits = 2, opts) => signed(v, fmtPctSigned(v, digits), opts);
export const signedMoney = (v, ccy, opts) => signed(v, fmtMoney(v, ccy, { signed: true }), opts);

/** Chip di stato: sempre icona + parola. kind: ok | warn | serious | crit | accent | muted.
 *  compact: sugli schermi stretti mostra solo l'icona (la parola resta nel title e per i lettori di schermo). */
export function chip(info, { compact = false, cls = '' } = {}) {
  return h('span', { class: `chip chip--${info.kind} ${compact ? 'chip--compact' : ''} ${cls}`.trim(), title: compact ? info.label : null },
    icon(info.icon || 'info'), h('span', { class: 'chip__label', text: info.label }));
}

/** Stato vuoto: dice che cosa manca e, se serve, perché. */
export function empty(title, hint = '') {
  return h('div', { class: 'empty' }, icon('empty', 'icon--xl'), h('p', { class: 'empty__title', text: title }), hint ? h('p', { class: 'empty__hint', text: hint }) : null);
}

/** Collegamento "vai alla sezione". */
export function more(href, text) {
  return h('a', { class: 'more', href }, h('span', { text }), icon('arrow'));
}

/** Gruppo di pulsanti a scelta singola (intervallo, filtro). onChange riceve il valore scelto. */
export function segmented({ label, options, value, onChange, cls = '' }) {
  let current = value;
  const buttons = new Map();
  const thumb = h('span', { class: 'seg__thumb', 'aria-hidden': 'true' });
  const root = h('div', { class: `seg ${cls}`.trim(), role: 'group', 'aria-label': label }, thumb);
  // il cursore di vetro prende posto e larghezza della voce scelta: i valori passano da proprietà CSS impostate via CSSOM
  const place = () => {
    const b = buttons.get(current);
    if (!b || !b.offsetWidth) return;
    thumb.style.setProperty('--x', `${b.offsetLeft}px`);
    thumb.style.setProperty('--w', `${b.offsetWidth}px`);
    if (!root.classList.contains('is-ready')) requestAnimationFrame(() => root.classList.add('is-ready'));
  };
  const sync = () => {
    for (const [v, b] of buttons) b.setAttribute('aria-pressed', v === current ? 'true' : 'false');
    place();
  };
  if (typeof ResizeObserver === 'function') new ResizeObserver(place).observe(root);
  for (const opt of options) {
    const count = h('span', { class: 'seg__count num' });
    count.hidden = true;
    const b = h('button', {
      class: 'seg__btn', type: 'button',
      onclick: () => {
        if (current === opt.value) return;
        current = opt.value;
        sync();
        onChange(current);
      },
    }, h('span', { text: opt.label }), count);
    b.countEl = count;
    buttons.set(opt.value, b);
    root.append(b);
  }
  sync();
  return {
    el: root,
    get value() { return current; },
    set(v) { current = v; sync(); },
    setCount(v, n) {
      const b = buttons.get(v);
      if (!b) return;
      b.countEl.textContent = n == null ? '' : String(n);
      b.countEl.hidden = n == null;
    },
  };
}

/** Pulsante a due stati (es. tabella sì/no). */
export function toggle({ label, iconName, pressed = false, onChange, text = '' }) {
  let on = pressed;
  const b = h('button', { class: 'btn btn--ghost btn--sm', type: 'button', 'aria-pressed': String(on), title: label, 'aria-label': label },
    iconName ? icon(iconName) : null, text ? h('span', { text }) : null);
  b.addEventListener('click', () => {
    on = !on;
    b.setAttribute('aria-pressed', String(on));
    onChange(on);
  });
  return { el: b, get on() { return on; }, set(v) { on = v; b.setAttribute('aria-pressed', String(on)); } };
}

/**
 * Tabella con intestazioni ordinabili.
 * columns: [{ key, label, num, sort: (row) => valore | null, cell: (row) => nodo/testo, hide: 'sm' | 'md' | 'lg', cls, blank }]
 * L'intestazione si costruisce una volta sola (il focus resta sui pulsanti); render(rows) sostituisce le righe.
 */
export function dataTable({ columns, caption, sort = null, emptyTitle = 'Nessun dato', emptyHint = '', cls = '', rowClass = null, detail = null }) {
  const state = sort ? { ...sort } : { key: null, dir: 1 };
  let rows = [];
  let foot = null;
  let hint = emptyHint;
  const ths = new Map();
  const colClass = (c) => `${c.num ? 'is-num' : ''} ${c.hide ? `hide-${c.hide}` : ''} ${c.cls || ''}`.trim();

  const headRow = h('tr', null, columns.map((c) => {
    const th = h('th', { scope: 'col', class: colClass(c) });
    if (c.sort) {
      const btn = h('button', { class: 'th-sort', type: 'button' }, h('span', { text: c.label }), icon('sort', 'th-sort__icon'));
      btn.addEventListener('click', () => {
        if (state.key === c.key) state.dir = -state.dir;
        else {
          state.key = c.key;
          state.dir = c.num ? -1 : 1;                      // i numeri partono dal più grande
        }
        paint();
      });
      th.append(btn);
    } else {
      th.textContent = c.label;
    }
    ths.set(c.key, th);
    return th;
  }));
  const tbody = h('tbody');
  const tfoot = h('tfoot');
  const table = h('table', { class: `table ${cls}`.trim() },
    caption ? h('caption', { class: 'sr-only', text: caption }) : null, h('thead', null, headRow), tbody, tfoot);
  const wrap = h('div', { class: 'table-wrap' }, table);

  function sorted() {
    const col = columns.find((c) => c.key === state.key && c.sort);
    if (!col) return rows;
    const keyed = rows.map((r, i) => ({ r, i, v: col.sort(r) }));
    keyed.sort((a, b) => {
      const an = a.v == null || a.v === '';
      const bn = b.v == null || b.v === '';
      if (an || bn) return an && bn ? a.i - b.i : an ? 1 : -1;       // i vuoti sempre in fondo
      const cmp = typeof a.v === 'number' && typeof b.v === 'number' ? a.v - b.v : String(a.v).localeCompare(String(b.v), 'it', { numeric: true });
      return cmp * state.dir || a.i - b.i;
    });
    return keyed.map((k) => k.r);
  }

  function paint() {
    for (const c of columns) {
      const th = ths.get(c.key);
      if (!c.sort) continue;
      const active = state.key === c.key;
      th.setAttribute('aria-sort', active ? (state.dir > 0 ? 'ascending' : 'descending') : 'none');
      th.querySelector('use').setAttribute('href', active ? (state.dir > 0 ? '#i-asc' : '#i-desc') : '#i-sort');
    }
    if (!rows.length) {
      fill(tbody, h('tr', { class: 'table__empty' }, h('td', { colspan: columns.length }, empty(emptyTitle, hint))));
      fill(tfoot);
      return;
    }
    const out = [];
    for (const r of sorted()) {
      out.push(h('tr', { class: rowClass ? rowClass(r) : null }, columns.map((c) => {
        const content = c.cell(r);
        const blank = content == null || content === '';
        return h('td', { class: colClass(c) }, blank ? (c.blank ? null : h('span', { class: 'muted', text: DASH })) : content);
      })));
      const extra = detail ? detail(r) : null;
      if (extra) out.push(h('tr', { class: 'table__detail' }, h('td', { colspan: columns.length }, extra)));
    }
    fill(tbody, out);
    fill(tfoot, foot ? h('tr', null, columns.map((c) => h('td', { class: colClass(c) }, foot[c.key] == null ? '' : foot[c.key]))) : null);
  }

  return {
    el: wrap,
    render(nextRows, { footer = null, emptyHint: nextHint } = {}) {
      rows = nextRows;
      foot = footer;
      if (nextHint != null) hint = nextHint;
      paint();
    },
  };
}

/** Testo sicuro o trattino. */
export const text = (v) => (str(v).trim() ? str(v) : DASH);

/** Coppia "etichetta: valore" in riga, per i riepiloghi. */
export function pair(label, value) {
  return h('div', { class: 'pair' }, h('span', { class: 'pair__label', text: label }), h('span', { class: 'pair__value num' }, value == null ? DASH : value));
}

