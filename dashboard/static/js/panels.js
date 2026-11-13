// Riquadri e segni condivisi dagli spazi Oggi, Rischio e Mercati (design_2_grafici.md, design_3_architettura_interazione.md).
//   panel         scheda di vetro con la grammatica dei grafici: occhiello, titolo = domanda, «Come si legge», provenienza, «?»
//   provTag       etichetta di provenienza (ESEMPIO puntinato · SIMULATO tratteggiato · PAPER a filetto · REALE pieno)
//   rollNumber    cifra che rotola solo dove cambia (posizioni via CSSOM, nessun attributo style)
//   brakeLadder   la scala dei freni: una sola, orizzontale, la perdita cresce verso destra
//   tradeRuler    il righello del trade: liquidazione, stop, entrata, ultima chiusura sulla stessa scala
//   meterRow      valore contro tetto, con la tacca del tetto disegnata
// Nessun colore qui: classi CSS e token. Soglie e tetti arrivano sempre dai dati, mai scritti nella pagina.

import { bindTip, onResize } from './charts.js';
import { tradeR } from './derive.js';
import { h, s, icon } from './dom.js';
import { DASH, fmtMoney, fmtNum, fmtPct, fmtPctSigned, fmtSigned, num, parseTs, str } from './format.js';
import { gloss } from './glossary.js';
import { modeKind } from './model.js';

const PROV = { demo: 'Esempio', sim: 'Simulato', paper: 'Paper', real: 'Reale', unknown: 'Non dichiarato' };

/** Provenienza della fotografia: 'demo' | 'sim' | 'paper' | 'real' | 'unknown'. */
export function provOf(meta) {
  if (str(meta && meta.data_label).toUpperCase().trim().startsWith('DEMO')) return 'demo';
  const kind = modeKind(meta);
  return kind === 'live' ? 'real' : kind;
}
export const provTag = (kind, text = '') => h('span', { class: `tag tag--${kind}`, text: text || PROV[kind] || PROV.unknown });

/** Scheda di vetro: { title (la domanda), eyebrow, ask («Come si legge», solo Semplice), what (popover «?»), span, cls, tools }. */
export function panel({ title, eyebrow = '', ask = '', what = '', span = 4, cls = '', tools = null, id = '' } = {}) {
  const prov = h('span', { class: 'panel__prov' });
  const askEl = h('p', { class: 'panel__ask only-semplice' });
  const q = what ? h('details', { class: 'what panel__what' },
    h('summary', { class: 'what__btn', 'aria-label': `Che cosa significa: ${title}` }, icon('help'), h('span', { class: 'only-semplice', text: 'Che cosa significa?' })),
    h('div', { class: 'what__panel' }, h('p', null, gloss(what)))) : null;
  const head = h('header', { class: 'panel__head' },
    h('div', { class: 'panel__titles' },
      eyebrow ? h('div', { class: 'card__eyebrow not-terminale', text: eyebrow }) : null,
      h('div', { class: 'card__title-row' }, h('h2', { class: 'card__title', text: title }), h('span', { class: 'card__title-aux' }, prov, q)),
      askEl),
    tools ? h('div', { class: 'card__actions' }, tools) : null);
  const body = h('div', { class: 'panel__body' });
  const foot = h('footer', { class: 'panel__foot' });
  foot.hidden = true;
  const el = h('section', { class: `card panel span-${span} ${cls}`.trim(), id: id || null, 'aria-label': title }, head, body, foot);
  const setAsk = (text) => { askEl.replaceChildren(...(text ? [h('b', { text: 'Come si legge. ' }), text] : [])); askEl.hidden = !text; };
  setAsk(ask);
  return {
    el, head, body, foot,
    setAsk,
    setProv(...tags) { prov.replaceChildren(...tags.filter(Boolean)); },
    setFoot(...kids) { foot.replaceChildren(...kids.flat().filter(Boolean)); foot.hidden = !foot.childNodes.length; },
  };
}

/** Stato vuoto disegnato: che cosa manca, perché, quando arriverà. Mai uno zero al posto di un dato assente. */
export const emptyState = (title, text = '') => h('div', { class: 'panel__empty' }, h('p', { class: 'panel__empty-title', text: title }), text ? h('p', { class: 'panel__empty-text', text }) : null);

/** Freschezza per fonte, in una riga: [{ name, text, stale }] → «fascia: ricerca del 12 nov · linea: fotografia di adesso». Ciò che è fermo è marcato. */
export const freshLine = (sources) => h('span', { class: 'fresh' }, sources.filter(Boolean).map((sc) => h('span', { class: `fresh__src ${sc.stale ? 'is-stale' : ''}`.trim() },
  h('i', { 'aria-hidden': 'true' }), h('b', { text: `${sc.name}: ` }), sc.text, sc.stale ? h('span', { class: 'sr-only', text: ' (non attuale)' }) : null)));

// ---- cifra che rotola ---------------------------------------------------------------------------------------------------------

/** Mostra `text` in `host`: le cifre stanno su colonne 0…9 e scorrono alla nuova posizione; il resto è testo fermo. */
export function rollNumber(host, text) {
  const chars = [...String(text)];
  const prev = host.rollChars || [];
  const same = prev.length === chars.length && chars.every((c, i) => /\d/.test(c) === /\d/.test(prev[i]));
  if (!same) {
    host.replaceChildren(...chars.map((c) => {
      if (!/\d/.test(c)) return h('span', { class: 'roll__s', text: c });
      const col = h('span', { class: 'roll__col' }, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((d) => h('span', { text: String(d) })));
      return h('span', { class: 'roll__d', 'aria-hidden': 'true' }, col);
    }));
    host.classList.add('roll');
    host.classList.remove('is-ready');
    requestAnimationFrame(() => requestAnimationFrame(() => host.classList.add('is-ready')));
  }
  let k = 0;
  chars.forEach((c, i) => {
    const node = host.children[i];
    if (/\d/.test(c)) { node.firstChild.style.setProperty('--d', c); node.firstChild.style.setProperty('--i', String(k++)); }
    else if (node.textContent !== c) node.textContent = c;
  });
  host.rollChars = chars;
  host.setAttribute('aria-label', String(text));
  host.setAttribute('role', 'text');
}

// ---- valore contro tetto ------------------------------------------------------------------------------------------------------

/** Una riga: nome, barra con la tacca del tetto, «valore / tetto · utilizzo». state: ok | warn | breach | none. */
export function meterRow({ name, sub = '', value, cap, text, state = 'ok', scale = null, hard = null }) {
  const top = scale || (cap ? cap * 1.25 : Math.abs(value) * 1.5 || 1);
  const pos = (v) => `${Math.max(0, Math.min(100, (Math.abs(v) / top) * 100)).toFixed(1)}%`;
  const bar = h('div', { class: 'meter', dataset: { state } }, h('i'), cap ? h('b') : null, hard ? h('b', { class: 'meter__hard' }) : null);
  bar.style.setProperty('--v', pos(value || 0));
  if (cap) bar.style.setProperty('--t', pos(cap));
  if (hard) bar.style.setProperty('--h', pos(hard));
  return h('div', { class: 'meterrow' }, h('div', { class: 'meterrow__name' }, name, sub ? h('small', { text: ` ${sub}` }) : null), bar, h('div', { class: 'meterrow__val num', text }));
}

// ---- scala dei freni ------------------------------------------------------------------------------------------------------------

/**
 * brakeLadder(host, { compact }) → { update(d) }
 * d = { dd, peak, equity, ccy, es (frazione, giornata di ES), fresh,
 *       steps: [{ level, action }]            scalini letti dalla fotografia (risk.dd_ladder), mai scritti qui
 *       worstPaper, simRef: { value, label }   riferimenti sulla corsia della caduta
 *       lanes: [{ label, sub, value, limit, action }]   corsie 24 ore e 7 giorni (solo nella versione estesa)
 *       worst: { loss, text } }                peggior caso di oggi (frazione persa), ipotesi SIMULATA: tratteggiata }
 */
export function brakeLadder(host, { compact = false, label = 'Scala dei freni' } = {}) {
  const svg = s('svg', { class: 'chart chart--static bl', role: 'img', 'aria-label': label });
  const legend = h('ul', { class: 'bl-legend' });
  legend.hidden = true;
  host.replaceChildren(svg, legend);
  let d = null;
  let last = 0;

  function draw(width, force = false) {
    const w = Math.floor(width);
    if (w < 120 || (w === last && !force)) return;
    last = w;
    svg.replaceChildren();
    legend.hidden = true;
    if (!d) { svg.setAttribute('height', 0); return; }
    const steps = (d.steps || []).filter((st) => num(st.level) != null).sort((a, b) => b.level - a.level);
    const deepest = steps.length ? steps[steps.length - 1].level : -0.4;
    const lo = Math.min(deepest * 1.15, (d.dd || 0) - 0.02, d.worst && d.worst.ddAfter != null ? d.worst.ddAfter - 0.03 : 0);
    const hi = compact ? 0.012 : 0.04;                              // un po' di spazio a sinistra dello zero per i giorni in guadagno
    const narrow = w < 560;
    const labelW = compact || narrow ? 0 : 128;
    const left = labelW + 6;
    const right = w - 8;
    const xOf = (v) => left + ((hi - v) / (hi - lo)) * (right - left);          // la perdita cresce verso destra
    const lanes = compact ? [] : (d.lanes || []).filter((l) => num(l.limit) != null);
    const laneH = 12;
    const noteRow = !compact && !narrow;                           // a schermo largo l'azione sta sotto la soglia, sulla tacca
    const omitted = [];
    const money = (v) => (d.equity != null ? fmtMoney(v, d.ccy, { digits: 0 }) : DASH);
    const widthOf = (node, text) => { let m = 0; try { m = node.getComputedTextLength(); } catch (err) { m = 0; } return m > 0 ? m : text.length * 6.3; };
    const tipFor = (name, level, now, action) => () => {
      const dist = now - level;
      return { title: name, rows: [
        { label: 'Mancano', value: `${fmtNum(dist * 100, 1)} punti` },
        d.peak != null ? { label: 'In euro', value: money(dist * d.peak) } : null,
        d.peak != null ? { label: 'Scatta a un patrimonio di', value: money(d.peak * (1 + level)) } : null,
        d.es ? { label: 'Giornate di ES', value: fmtNum(dist / Math.abs(d.es), 1) } : null,
      ].filter(Boolean), note: action || '' };
    };
    /** Etichette sotto la corsia: ognuna sulla prima riga libera, sempre dentro i bordi. Nessuna si sovrappone, nessuna è troncata. */
    const place = (items, yBase) => {
      const rows = [];
      for (const it of items.filter(Boolean).sort((a, b) => a.x - b.x)) {
        const node = s('text', { class: it.cls }, it.text);
        svg.append(node);
        const tw = widthOf(node, it.text);
        const x0 = Math.max(left, Math.min(right - tw, it.center ? it.x - tw / 2 : it.x - 4));
        let r = 0;
        while (rows[r] != null && rows[r] > x0 - 10) r++;
        rows[r] = x0 + tw;
        node.setAttribute('x', x0.toFixed(1));
        node.setAttribute('y', yBase + r * 14);
        it.y = yBase + r * 14;
        it.x0 = x0;
      }
      return rows.length;
    };
    /** Una corsia: titolo (sopra, se non c'è la colonna dei nomi), soglie, barra, etichette sotto. Restituisce il fondo. */
    const lane = (yTop, L) => {
      let y = yTop;
      if (!labelW && !compact) { svg.append(s('text', { class: 'bl-name', x: left, y: y + 11 }, `${L.name}${L.sub ? ` · ${L.sub}` : ''}`)); y += 20; }
      const xs = L.ticks.map((t) => Math.round(xOf(t.level)) + 0.5);
      // soglie vicine: l'etichetta sale di una riga, con la tacca che la raggiunge
      const tickNodes = L.ticks.map((t) => s('text', { class: 'bl-tick-label' }, t.text));
      svg.append(...tickNodes);
      let lastEnd = -999;
      const lifts = L.ticks.map((t, i) => {
        const tw = widthOf(tickNodes[i], t.text);
        const flip = xs[i] + 5 + tw > right;
        const x0 = flip ? xs[i] - 5 - tw : xs[i] + 5;
        const lift = x0 < lastEnd + 6 ? 13 : 0;
        if (!lift) lastEnd = x0 + tw;
        return { flip, lift, x0, tw };
      });
      const anyLift = lifts.some((l) => l.lift);
      const yc = y + (noteRow ? 30 : 18) + (anyLift ? 13 : 0) + laneH / 2;          // centro della barra
      if (labelW) svg.append(s('text', { class: 'bl-name', x: 0, y: yc + 4 }, L.name), L.sub ? s('text', { class: 'bl-sub', x: 0, y: yc + 19 }, L.sub) : null);
      svg.append(s('rect', { class: 'bl-track', x: left, y: yc - laneH / 2, width: right - left, height: laneH, rx: laneH / 2 }));
      for (const z of L.zones) {
        const x0 = xOf(Math.min(z.from, hi));
        const x1 = xOf(Math.max(z.to, lo));
        if (x1 - x0 > 1) svg.append(s('rect', { class: `bl-zone bl-zone--${z.kind}`, x: x0.toFixed(1), y: yc - laneH / 2, width: (x1 - x0).toFixed(1), height: laneH, rx: 3 }));
      }
      L.ticks.forEach((t, i) => {
        const x = xs[i];
        const { flip, lift, x0 } = lifts[i];
        const yLabel = yc - laneH / 2 - (noteRow ? 20 : 8) - lift;
        tickNodes[i].setAttribute('x', x0.toFixed(1));
        tickNodes[i].setAttribute('y', yLabel);
        const hit = s('rect', { class: 'bl-hit', x: x - 9, y: yc - 30, width: 18, height: 46, tabindex: '0', 'aria-label': `${t.text}${t.action ? `: ${t.action}` : ''}` });
        bindTip(hit, tipFor(`${t.text}${t.action ? ` · ${t.action}` : ''}`, t.level, L.value ?? 0, ''));
        svg.append(s('line', { class: `bl-tick bl-tick--${t.kind}`, x1: x, x2: x, y1: yLabel - 9, y2: yc + laneH / 2 + 1 }));
        if (t.action) {
          // l'azione sta sulla tacca solo se entra per intero prima della soglia successiva; altrimenti va nell'elenco sotto la scala
          let shown = false;
          if (noteRow && !flip && !lift) {
            const node = s('text', { class: 'bl-tick-note', x: x + 5, y: yc - laneH / 2 - 7 }, t.action);
            svg.append(node);
            const room = (i + 1 < xs.length ? xs[i + 1] : right) - x - 14;
            if (widthOf(node, t.action) <= room) shown = true; else node.remove();
          }
          if (!shown && !compact) omitted.push({ text: t.text, action: t.action });
        }
        svg.append(hit);
      });
      if (L.value != null && !L.unknown) {
        const x = xOf(Math.max(lo, Math.min(hi, L.value)));
        if (L.worstAt != null) {
          const xw = xOf(Math.max(lo, L.worstAt));
          svg.append(s('line', { class: 'bl-worst', x1: x.toFixed(1), x2: xw.toFixed(1), y1: yc, y2: yc }),
            s('rect', { class: 'bl-worst-mark', x: (xw - 5).toFixed(1), y: yc - 5, width: 10, height: 10, transform: `rotate(45 ${xw.toFixed(1)} ${yc})` }));
        }
        svg.append(s('circle', { class: 'bl-now-halo', cx: x.toFixed(1), cy: yc, r: 9 }), s('circle', { class: 'bl-now', cx: x.toFixed(1), cy: yc, r: 5 }));
      }
      if (L.ring != null) svg.append(s('circle', { class: 'bl-ring', cx: xOf(L.ring).toFixed(1), cy: yc, r: 4.5 }));
      const rows = place(L.below || [], yc + 24);
      if (L.after) L.after(yc);
      return yc + laneH / 2 + 6 + Math.max(1, rows) * 14;
    };

    // corsia della caduta dal massimo: zone tra uno scalino e il successivo, tacche con che cosa fa il motore
    const kinds = ['warn', 'serious', 'crit'];
    const zones = [{ from: 0, to: steps.length ? steps[0].level : lo, kind: 'safe' }, ...steps.map((st, i) => ({ from: st.level, to: i + 1 < steps.length ? steps[i + 1].level : lo, kind: kinds[Math.min(i, 2)] }))];
    const fresh = d.fresh !== false;
    const sim = d.simRef && num(d.simRef.value) != null ? { x: Math.round(xOf(d.simRef.value)) + 0.5, text: d.simRef.label, cls: 'bl-note' } : null;
    const below = [
      d.dd != null && fresh ? { x: xOf(d.dd), text: `adesso ${fmtPctSigned(d.dd, 1)}`, cls: 'bl-now-label' } : !fresh ? { x: left, text: 'distanza sconosciuta: dati fermi', cls: 'bl-now-label' } : null,
      !compact && fresh && d.worstPaper != null ? { x: xOf(d.worstPaper) + 2, text: `peggiore finora ${fmtPctSigned(d.worstPaper, 1)}`, cls: 'bl-note' } : null,
      !compact && sim ? { ...sim, x: sim.x + 9 } : null,
      !compact && d.worst && d.worst.ddAfter != null ? { x: xOf(Math.max(lo, d.worst.ddAfter)), center: true, text: `peggior caso di oggi ${d.worst.atLeast ? 'almeno ' : ''}${fmtPctSigned(d.worst.ddAfter, 1)}`, cls: 'bl-worst-label' } : null,
    ];
    let y = lane(compact ? 6 : 2, {
      name: 'Caduta dal massimo', sub: d.peak != null ? `dal picco di ${money(d.peak)}` : '', value: d.dd, zones,
      ticks: steps.map((st, i) => ({ level: st.level, text: fmtPct(st.level, 0), action: str(st.action), kind: kinds[Math.min(i, 2)] })),
      worstAt: d.worst && d.worst.ddAfter != null ? d.worst.ddAfter : null, unknown: !fresh, below, ring: !compact && fresh && d.worstPaper != null ? d.worstPaper : null,
      after: (yc) => { if (sim) svg.append(s('line', { class: 'bl-sim', x1: sim.x, x2: sim.x, y1: yc - laneH / 2 - 2, y2: compact ? yc + 14 : (below[2] && below[2].y != null ? below[2].y + (below[2].x0 < sim.x + 2 ? -11 : 2) : yc + 30) })); },
    });
    lanes.forEach((l) => {
      y = lane(y + (narrow ? 12 : 4), {
        name: l.label, sub: l.sub || '', value: l.value, zones: [{ from: l.limit, to: lo, kind: 'warn' }],
        ticks: [{ level: l.limit, text: fmtPct(l.limit, 0), action: str(l.action), kind: 'warn' }],
        worstAt: d.worst && l.value != null ? Math.min(l.value, 0) - d.worst.loss : null, unknown: !fresh,
        below: [l.value != null && fresh ? { x: xOf(Math.min(hi, l.value)), text: fmtPctSigned(l.value, 2), cls: 'bl-now-label' } : l.value == null ? { x: left, text: 'non calcolabile con i dati presenti', cls: 'bl-note' } : null],
      });
    });
    if (!compact) {
      // asse: una tacca ogni dieci punti, su una riga sua; «perdita →» solo se c'è posto
      y += 12;
      let lastEnd = -999;
      for (let v = 0; v >= lo; v -= 0.1) {
        const text = Math.abs(v) < 1e-9 ? '0' : fmtPct(v, 0);
        const node = s('text', { class: 'c-tick c-tick--x', x: xOf(v).toFixed(1), y }, text);
        svg.append(node);
        const tw = widthOf(node, text);
        if (xOf(v) - tw / 2 < lastEnd + 8) node.remove(); else lastEnd = xOf(v) + tw / 2;
      }
      if (lastEnd < right - 74) svg.append(s('text', { class: 'c-tick', x: right, y, 'text-anchor': 'end' }, 'perdita →'));
      y += 6;
    }
    svg.setAttribute('viewBox', `0 0 ${w} ${y}`);
    svg.setAttribute('width', w);
    svg.setAttribute('height', y);
    // che cosa fa il motore a ogni soglia, quando non entra sulla tacca: un elenco vero, mai testo troncato
    const seen = new Set();
    const items = omitted.filter((o) => { const k = `${o.text}|${o.action}`; if (seen.has(k)) return false; seen.add(k); return true; });
    legend.hidden = !items.length;
    legend.replaceChildren(...items.map((o) => h('li', null, h('b', { class: 'num', text: o.text }), ' ', o.action)));
  }

  onResize(host, (w) => draw(w));
  return { update(next) { d = next; draw(host.clientWidth, true); } };
}

// ---- righello del trade ---------------------------------------------------------------------------------------------------------

const px = (v) => (v == null ? DASH : fmtNum(v, Math.abs(v) >= 1000 ? 0 : Math.abs(v) >= 10 ? 2 : 4));

/**
 * tradeRuler(host) → { update({ trade, last }) } — liquidazione, stop, entrata e ultima chiusura sulla stessa scala di prezzo.
 * La zona entrata–stop è una lastra («1 R»); il tratto entrata → prezzo prende il segno del risultato (più una freccia nel testo).
 */
export function tradeRuler(host, { label = 'Livelli del trade' } = {}) {
  const svg = s('svg', { class: 'chart chart--static tr', role: 'img', 'aria-label': label });
  host.replaceChildren(svg);
  let d = null;
  let lastW = 0;
  function draw(width, force = false) {
    const w = Math.floor(width);
    if (w < 120 || (w === lastW && !force)) return;
    lastW = w;
    svg.replaceChildren();
    if (!d || !d.trade) { svg.setAttribute('height', 0); return; }
    const t = d.trade;
    const lastV = num(d.last);
    const marks = [
      { key: 'liq', name: 'liquidazione', v: num(t.liquidation) }, { key: 'stop', name: 'stop', v: num(t.stop) },
      { key: 'entry', name: 'entrata', v: num(t.entry) }, { key: 'last', name: 'ultima chiusura', v: lastV },
    ].filter((m) => m.v != null);
    if (marks.length < 2) { svg.setAttribute('height', 0); return; }
    const vals = marks.map((m) => m.v);
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const pad = (hi - lo) * 0.09 || 1;
    const left = 4;
    const right = w - 4;
    const xOf = (v) => left + ((v - (lo - pad)) / (hi - lo + 2 * pad)) * (right - left);
    const widthOf = (node, text) => { let m = 0; try { m = node.getComputedTextLength(); } catch (err) { m = 0; } return m > 0 ? m : text.length * 6.4; };
    // prezzi sopra, nomi sotto: ogni etichetta sulla prima riga libera (mai una lasciata cadere, mai due sovrapposte)
    const sorted = [...marks].sort((a, b) => a.v - b.v);
    const layout = (cls, textOf) => {
      const rows = [];
      return { rows, items: sorted.map((m) => {
        const text = textOf(m);
        const node = s('text', { class: `${cls} ${cls}--${m.key}` }, text);
        svg.append(node);
        const tw = widthOf(node, text);
        const x = xOf(m.v);
        const x0 = Math.max(left, Math.min(right - tw, x - tw / 2));
        let r = 0;
        while (rows[r] != null && rows[r] > x0 - 12) r++;
        rows[r] = x0 + tw;
        return { m, node, x, x0, tw, r };
      }) };
    };
    // distanza dall'ultima chiusura, in percentuale: quanto manca a stop e liquidazione
    const dist = (m) => (lastV && m.key !== 'last' && m.key !== 'entry' ? ` ${fmtPctSigned(m.v / lastV - 1, 1)}` : '');
    const top = layout('tr-price', (m) => px(m.v));
    const bot = layout('tr-name', (m) => `${m.name}${dist(m)}`);
    const y = 14 + top.rows.length * 14 + 8;
    const H = y + 20 + bot.rows.length * 14;
    svg.setAttribute('viewBox', `0 0 ${w} ${H}`);
    svg.setAttribute('width', w);
    svg.setAttribute('height', H);
    const get = (k) => (marks.find((m) => m.key === k) || {}).v;
    const shapes = [s('rect', { class: 'bl-track', x: left, y: y - 4, width: right - left, height: 8, rx: 4 })];
    if (get('entry') != null && get('stop') != null) {
      const a = xOf(Math.min(get('entry'), get('stop')));
      const b = xOf(Math.max(get('entry'), get('stop')));
      shapes.push(s('rect', { class: 'c-slab tr-risk', x: a.toFixed(1), y: y - 9, width: (b - a).toFixed(1), height: 18, rx: 3 }), s('line', { class: 'c-slab-edge', x1: a.toFixed(1), x2: b.toFixed(1), y1: y - 9, y2: y - 9 }));
    }
    if (get('entry') != null && get('last') != null) {
      const up = tradeR(t, get('last')) >= 0;
      shapes.push(s('line', { class: `tr-run tr-run--${up ? 'up' : 'down'}`, x1: xOf(get('entry')).toFixed(1), x2: xOf(get('last')).toFixed(1), y1: y, y2: y }));
    }
    for (const it of top.items) {
      const { m, x } = it;
      const lead = bot.items.find((b) => b.m === m);
      // filo dall'etichetta al segno quando è stata spostata di riga o di lato
      const yTop = 14 + (top.rows.length - 1 - it.r) * 14;
      it.node.setAttribute('x', it.x0.toFixed(1));
      it.node.setAttribute('y', yTop);
      const yBot = y + 26 + lead.r * 14;
      lead.node.setAttribute('x', lead.x0.toFixed(1));
      lead.node.setAttribute('y', yBot);
      if (m.key === 'last') shapes.push(s('line', { class: 'tr-lead', x1: x.toFixed(1), x2: x.toFixed(1), y1: yTop + 3, y2: yBot - 11 }), s('circle', { class: 'bl-now-halo', cx: x.toFixed(1), cy: y, r: 9 }), s('circle', { class: `tr-last tr-last--${tradeR(t, m.v) >= 0 ? 'up' : 'down'}`, cx: x.toFixed(1), cy: y, r: 5 }));
      else shapes.push(s('line', { class: `tr-mark tr-mark--${m.key}`, x1: x.toFixed(1), x2: x.toFixed(1), y1: yTop + 3, y2: yBot - 11 }));
    }
    // il punto dell'ultima chiusura sta sopra le tacche: se coincide con l'entrata si vedono tutti e due
    shapes.sort((a, b) => (a.classList.contains('tr-last') || a.classList.contains('bl-now-halo') ? 1 : 0) - (b.classList.contains('tr-last') || b.classList.contains('bl-now-halo') ? 1 : 0));
    svg.prepend(...shapes);
    svg.setAttribute('aria-label', `${label}: ${marks.map((m) => `${m.name} ${px(m.v)}`).join(', ')}`);
  }
  onResize(host, (w) => draw(w));
  return { update(next) { d = next; draw(host.clientWidth, true); } };
}

/**
 * Segni del fondo per il grafico a candele: livelli del trade aperto (lastra 1 R, liquidazione, stop iniziale e attuale, entrata,
 * scala in R) e trade chiusi (anello → rombo con R) sullo strumento `sym`. `o` sono le barre ({ t }), `tb` il libro dei trade.
 */
export function tradeMarkers(o, sym, tb) {
  const out = [];
  const DAY = 86400000;
  const book = tb && typeof tb === 'object' ? tb : {};
  const idxOf = (day) => { const t0 = parseTs(str(day)); if (t0 == null) return -1; let k = -1; for (let i = 0; i < o.t.length; i++) if (o.t[i] <= t0 + DAY / 2) k = i; return k; };
  const open = Object.values(book.open && typeof book.open === 'object' ? book.open : {}).filter((t) => t && typeof t === 'object' && str(t.symbol) === sym);
  for (const t of open) {
    const i = Math.max(0, idxOf(t.opened));
    const entry = num(t.entry);
    const stop = num(t.stop);
    const init = entry != null && num(t.initial_stop_distance) != null ? entry * (1 - (num(t.side) === -1 ? -1 : 1) * t.initial_stop_distance) : null;
    if (entry != null && stop != null) out.push({ kind: 'zone', i, from: entry, to: init ?? stop, label: '1 R' });
    if (num(t.liquidation) != null) out.push({ kind: 'level', i, price: t.liquidation, label: 'Liquidazione', short: 'Liq.', color: 'crit' });
    if (init != null && stop != null && Math.abs(init - stop) / entry > 0.002) out.push({ kind: 'level', i, price: init, label: 'Stop iniziale', short: 'Stop in.', color: 'warn', past: true });
    if (stop != null) out.push({ kind: 'level', i, price: stop, label: 'Stop', short: 'Stop', color: 'warn' });
    if (entry != null) { out.push({ kind: 'level', i, price: entry, label: 'Entrata', short: 'Entr.', color: 'text' }); out.push({ kind: 'entry', i, price: entry }); }
    if (entry != null && num(t.initial_stop_distance)) out.push({ kind: 'rscale', entry, dist: entry * t.initial_stop_distance });
  }
  for (const t of (Array.isArray(book.closed) ? book.closed : []).filter((x) => x && str(x.symbol) === sym)) {
    const a = idxOf(t.opened);
    const b = idxOf(t.closed);
    if (a >= 0 && num(t.entry) != null) out.push({ kind: 'entry', i: a, price: t.entry });
    if (b >= 0 && num(t.exit) != null) out.push({ kind: 'exit', i: b, price: t.exit, color: num(t.R) >= 0 ? 'up' : 'down', label: num(t.R) == null ? '' : `${fmtSigned(t.R, 1)} R` });
  }
  return out;
}

export { tradeR };
