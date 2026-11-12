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
import { DASH, fmtMoney, fmtNum, fmtPct, fmtPctSigned, num, str } from './format.js';
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
      h('div', { class: 'card__title-row' }, h('h2', { class: 'card__title', text: title }), prov, q),
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
  host.replaceChildren(svg);
  let d = null;
  let last = 0;

  function draw(width, force = false) {
    const w = Math.floor(width);
    if (w < 120 || (w === last && !force)) return;
    last = w;
    svg.replaceChildren();
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
    const top = compact ? 30 : 48;
    const gap = compact ? 0 : narrow ? 74 : 62;
    const H = top + laneH + (compact ? 30 : 66) + lanes.length * gap + (compact ? 0 : 22);
    svg.setAttribute('viewBox', `0 0 ${w} ${H}`);
    svg.setAttribute('width', w);
    svg.setAttribute('height', H);
    const money = (v) => (d.equity != null ? fmtMoney(v, d.ccy, { digits: 0 }) : DASH);
    const tipFor = (name, level, now, action) => () => {
      const dist = now - level;
      return { title: name, rows: [
        { label: 'Mancano', value: `${fmtNum(dist * 100, 1)} punti` },
        d.peak != null ? { label: 'In euro', value: money(dist * d.peak) } : null,
        d.peak != null ? { label: 'Scatta a un patrimonio di', value: money(d.peak * (1 + level)) } : null,
        d.es ? { label: 'Giornate di ES', value: fmtNum(dist / Math.abs(d.es), 1) } : null,
      ].filter(Boolean), note: action || '' };
    };
    const fit = (text, room) => { const n = Math.max(4, Math.floor(room / 5.7)); return text.length > n ? `${text.slice(0, n - 1).trimEnd()}…` : text; };
    const lane = (y, name, sub, value, zones, ticks, worstAt, unknown) => {
      if (labelW) svg.append(s('text', { class: 'bl-name', x: 0, y: y + 4 }, name), sub ? s('text', { class: 'bl-sub', x: 0, y: y + 19 }, sub) : null);
      else if (!compact) svg.append(s('text', { class: 'bl-name', x: left, y: y - 26 }, `${name}${sub ? ` · ${sub}` : ''}`));
      svg.append(s('rect', { class: 'bl-track', x: left, y: y - laneH / 2, width: right - left, height: laneH, rx: laneH / 2 }));
      for (const z of zones) {
        const x0 = xOf(Math.min(z.from, hi));
        const x1 = xOf(Math.max(z.to, lo));
        if (x1 - x0 > 1) svg.append(s('rect', { class: `bl-zone bl-zone--${z.kind}`, x: x0.toFixed(1), y: y - laneH / 2, width: (x1 - x0).toFixed(1), height: laneH, rx: 3 }));
      }
      let lastLabelX = -999;
      ticks.forEach((t, i) => {
        const x = Math.round(xOf(t.level)) + 0.5;
        const lift = x - lastLabelX < 46 ? 13 : 0;                      // tacche vicine: l'etichetta sale di una riga, con la tacca che la raggiunge
        lastLabelX = lift ? lastLabelX : x;
        const hit = s('rect', { class: 'bl-hit', x: x - 9, y: y - 30, width: 18, height: 46, tabindex: '0', 'aria-label': `${t.text}${t.action ? `: ${t.action}` : ''}` });
        bindTip(hit, tipFor(`${t.text}${t.action ? ` · ${t.action}` : ''}`, t.level, value ?? 0, ''));
        const flip = x > right - (compact ? 30 : 120);
        svg.append(s('line', { class: `bl-tick bl-tick--${t.kind}`, x1: x, x2: x, y1: y - (compact ? 13 : 24) - lift, y2: y + laneH / 2 + 1 }),
          s('text', { class: 'bl-tick-label', x: flip ? x - 5 : x + 5, y: y - (compact ? 15 : 26) - lift, 'text-anchor': flip ? 'end' : null }, t.text),
          !compact && t.action && !narrow && !flip && !lift ? s('text', { class: 'bl-tick-note', x: flip ? x - 5 : x + 5, y: y - 13, 'text-anchor': flip ? 'end' : null }, fit(t.action, flip ? 150 : (i + 1 < ticks.length ? xOf(ticks[i + 1].level) : right) - x - 12)) : null, hit);
      });
      if (value != null && !unknown) {
        const x = xOf(Math.max(lo, Math.min(hi, value)));
        if (worstAt != null) {
          const xw = xOf(Math.max(lo, worstAt));
          svg.append(s('line', { class: 'bl-worst', x1: x.toFixed(1), x2: xw.toFixed(1), y1: y, y2: y }),
            s('rect', { class: 'bl-worst-mark', x: (xw - 5).toFixed(1), y: y - 5, width: 10, height: 10, transform: `rotate(45 ${xw.toFixed(1)} ${y})` }));
        }
        svg.append(s('circle', { class: 'bl-now-halo', cx: x.toFixed(1), cy: y, r: 9 }), s('circle', { class: 'bl-now', cx: x.toFixed(1), cy: y, r: 5 }));
      }
      return y;
    };

    // corsia della caduta dal massimo: zone tra uno scalino e il successivo, tacche con che cosa fa il motore
    const kinds = ['warn', 'serious', 'crit'];
    const zones = [{ from: 0, to: steps.length ? steps[0].level : lo, kind: 'safe' }, ...steps.map((st, i) => ({ from: st.level, to: i + 1 < steps.length ? steps[i + 1].level : lo, kind: kinds[Math.min(i, 2)] }))];
    const y0 = top + laneH / 2;
    lane(y0, 'Caduta dal massimo', d.peak != null ? `dal picco di ${money(d.peak)}` : '', d.dd, zones,
      steps.map((st, i) => ({ level: st.level, text: fmtPct(st.level, 0), action: str(st.action), kind: kinds[Math.min(i, 2)] })),
      d.worst && d.worst.ddAfter != null ? d.worst.ddAfter : null, d.fresh === false);
    if (d.dd != null && d.fresh !== false) {
      const x = xOf(d.dd);
      svg.append(s('text', { class: 'bl-now-label', x: Math.max(left, x - 4).toFixed(1), y: y0 + 26 }, `adesso ${fmtPctSigned(d.dd, 1)}`));
    } else if (d.fresh === false) svg.append(s('text', { class: 'bl-now-label', x: left, y: y0 + 26 }, 'distanza sconosciuta: dati fermi'));
    if (!compact && d.worstPaper != null) {
      const x = xOf(d.worstPaper);
      svg.append(s('circle', { class: 'bl-ring', cx: x.toFixed(1), cy: y0, r: 4.5 }), s('text', { class: 'bl-note', x: (x + 8).toFixed(1), y: y0 + 26 }, `peggiore finora ${fmtPctSigned(d.worstPaper, 1)}`));
    }
    if (d.simRef && num(d.simRef.value) != null) {
      const x = Math.round(xOf(d.simRef.value)) + 0.5;
      svg.append(s('line', { class: 'bl-sim', x1: x, x2: x, y1: y0 - laneH / 2 - 2, y2: y0 + (compact ? 14 : 34) }),
        compact ? null : s('text', { class: 'bl-note', x: x + 5, y: y0 + 42 }, d.simRef.label));
    }
    if (!compact && d.worst && d.worst.ddAfter != null) {
      const xw = xOf(Math.max(lo, d.worst.ddAfter));
      svg.append(s('text', { class: 'bl-worst-label', x: Math.min(xw, right - 4).toFixed(1), y: y0 + 60, 'text-anchor': xw > right - 180 ? 'end' : 'middle' }, `peggior caso di oggi ${d.worst.atLeast ? 'almeno ' : ''}${fmtPctSigned(d.worst.ddAfter, 1)}`));
    }
    lanes.forEach((l, i) => {
      const y = y0 + 66 + (i + 1) * gap - (narrow ? 0 : 20);
      lane(y, l.label, l.sub || '', l.value, [{ from: l.limit, to: lo, kind: 'warn' }], [{ level: l.limit, text: fmtPct(l.limit, 0), action: str(l.action), kind: 'warn' }],
        d.worst && l.value != null ? Math.min(l.value, 0) - d.worst.loss : null, d.fresh === false);
      if (l.value != null && d.fresh !== false) svg.append(s('text', { class: 'bl-now-label', x: Math.max(left, xOf(Math.min(hi, l.value)) - 4).toFixed(1), y: y + 24 }, fmtPctSigned(l.value, 2)));
      else if (l.value == null) svg.append(s('text', { class: 'bl-note', x: left, y: y + 24 }, 'non calcolabile con i dati presenti'));
    });
    if (!compact) {
      const yA = H - 6;
      for (let v = 0; v >= lo; v -= 0.1) svg.append(s('text', { class: 'c-tick c-tick--x', x: xOf(v).toFixed(1), y: yA }, v === 0 ? '0' : fmtPct(v, 0)));
      svg.append(s('text', { class: 'c-tick', x: right, y: yA, 'text-anchor': 'end' }, 'perdita →'));
    }
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
    const marks = [
      { key: 'liq', name: 'liquidazione', v: num(t.liquidation) }, { key: 'stop', name: 'stop', v: num(t.stop) },
      { key: 'entry', name: 'entrata', v: num(t.entry) }, { key: 'last', name: 'ultima chiusura', v: num(d.last) },
    ].filter((m) => m.v != null);
    if (marks.length < 2) { svg.setAttribute('height', 0); return; }
    const vals = marks.map((m) => m.v);
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const pad = (hi - lo) * 0.09 || 1;
    const left = 4;
    const right = w - 4;
    const xOf = (v) => left + ((v - (lo - pad)) / (hi - lo + 2 * pad)) * (right - left);
    const y = 34;
    svg.setAttribute('viewBox', `0 0 ${w} 70`);
    svg.setAttribute('width', w);
    svg.setAttribute('height', 70);
    svg.append(s('rect', { class: 'bl-track', x: left, y: y - 4, width: right - left, height: 8, rx: 4 }));
    const get = (k) => (marks.find((m) => m.key === k) || {}).v;
    if (get('entry') != null && get('stop') != null) {
      const a = xOf(Math.min(get('entry'), get('stop')));
      const b = xOf(Math.max(get('entry'), get('stop')));
      svg.append(s('rect', { class: 'c-slab tr-risk', x: a.toFixed(1), y: y - 9, width: (b - a).toFixed(1), height: 18, rx: 3 }), s('line', { class: 'c-slab-edge', x1: a.toFixed(1), x2: b.toFixed(1), y1: y - 9, y2: y - 9 }));
    }
    if (get('entry') != null && get('last') != null) {
      const up = tradeR(t, get('last')) >= 0;
      svg.append(s('line', { class: `tr-run tr-run--${up ? 'up' : 'down'}`, x1: xOf(get('entry')).toFixed(1), x2: xOf(get('last')).toFixed(1), y1: y, y2: y }));
    }
    const sorted = [...marks].sort((a, b) => a.v - b.v);
    let prevTop = -99;
    let prevBot = -99;
    sorted.forEach((m) => {
      const x = xOf(m.v);
      if (m.key === 'last') svg.append(s('circle', { class: 'bl-now-halo', cx: x.toFixed(1), cy: y, r: 9 }), s('circle', { class: `tr-last tr-last--${tradeR(t, m.v) >= 0 ? 'up' : 'down'}`, cx: x.toFixed(1), cy: y, r: 5 }));
      else svg.append(s('line', { class: `tr-mark tr-mark--${m.key}`, x1: x.toFixed(1), x2: x.toFixed(1), y1: y - 12, y2: y + 12 }));
      const anchor = x < left + 34 ? 'start' : x > right - 34 ? 'end' : 'middle';
      const tx = anchor === 'start' ? left : anchor === 'end' ? right : x;
      const wide = px(m.v).length * 6.6 + 8;
      if (tx - prevTop > wide) { svg.append(s('text', { class: 'tr-price', x: tx.toFixed(1), y: 12, 'text-anchor': anchor }, px(m.v))); prevTop = tx; }
      if (tx - prevBot > m.name.length * 5.6 + 10) { svg.append(s('text', { class: 'tr-name', x: tx.toFixed(1), y: 64, 'text-anchor': anchor }, m.name)); prevBot = tx; }
    });
    svg.setAttribute('aria-label', `${label}: ${marks.map((m) => `${m.name} ${px(m.v)}`).join(', ')}`);
  }
  onResize(host, (w) => draw(w));
  return { update(next) { d = next; draw(host.clientWidth, true); } };
}

export { tradeR };
