// Diagramma di flusso in SVG: passaggi numerati collegati da frecce, a serpentina su schermi larghi e in colonna su
// quelli stretti. Ogni passaggio è un pulsante (clic, Invio, frecce). Usato da «Come funziona» e «Apprendimento».

import { s } from './dom.js';

/**
 * steps: [{ id, title, sub, guard }] — guard: bordo tratteggiato (un passaggio che può solo frenare o che decide).
 * Ritorna { select(id, focus), redraw(), selected }.
 */
export function flowDiagram(host, steps, { label = 'Diagramma di flusso', initial = null, onSelect = () => {}, cols = 4 } = {}) {
  const svg = s('svg', { class: 'flow', role: 'group', 'aria-label': label });
  host.append(svg);
  let selected = initial || (steps[0] && steps[0].id);
  let lastWidth = 0;

  function select(id, focus = false) {
    selected = id;
    draw(true);
    onSelect(id);
    if (focus) {
      const node = svg.querySelector(`[data-step="${id}"]`);
      if (node) node.focus();
    }
  }

  function draw(force = false) {
    const W = Math.floor(host.clientWidth);
    if (W < 120 || (!force && W === lastWidth)) return;
    lastWidth = W;
    svg.replaceChildren();
    const wide = W >= 720;
    const nc = wide ? cols : 1;
    const gapX = wide ? 34 : 0;
    const gapY = wide ? 40 : 18;
    const nw = wide ? (W - gapX * (nc - 1) - 2) / nc : W - 2;
    const nh = wide ? 76 : 54;
    const pos = steps.map((_, i) => {
      const row = Math.floor(i / nc);
      const col = wide && row % 2 === 1 ? nc - 1 - (i % nc) : i % nc;      // le righe dispari tornano indietro
      return { x: 1 + col * (nw + gapX), y: 1 + row * (nh + gapY) };
    });
    const H = Math.max(...pos.map((p) => p.y)) + nh + 2;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    for (let i = 0; i < steps.length - 1; i++) {
      const a = pos[i];
      const b = pos[i + 1];
      let d;
      let head;
      if (Math.abs(a.y - b.y) < 1) {
        const dir = b.x > a.x ? 1 : -1;
        const x1 = dir > 0 ? a.x + nw : a.x;
        const x2 = dir > 0 ? b.x : b.x + nw;
        const y = a.y + nh / 2;
        d = `M${x1 + 4 * dir},${y}L${x2 - 5 * dir},${y}`;
        head = `M${x2 - 11 * dir},${y - 5}L${x2 - 4 * dir},${y}L${x2 - 11 * dir},${y + 5}`;
      } else {
        const x = a.x + nw / 2;
        d = `M${x},${a.y + nh + 4}L${x},${b.y - 5}`;
        head = `M${x - 5},${b.y - 11}L${x},${b.y - 4}L${x + 5},${b.y - 11}`;
      }
      svg.append(s('path', { class: 'flow__arrow', d }), s('path', { class: 'flow__arrow', d: head }));
    }
    steps.forEach((st, i) => {
      const { x, y } = pos[i];
      const on = st.id === selected;
      const g = s('g', {
        class: `flow__node ${on ? 'is-on' : ''} ${st.guard ? 'flow__node--guard' : ''}`.trim(), role: 'button', tabindex: '0',
        'aria-pressed': String(on), 'aria-label': `Passaggio ${i + 1}: ${st.title}, ${st.sub}`, 'data-step': st.id,
      });
      const cy = y + nh / 2;
      g.append(s('rect', { class: 'flow__box', x, y, width: nw, height: nh, rx: 6 }));
      g.append(s('circle', { class: 'flow__badge', cx: x + 22, cy, r: 11 }));
      g.append(s('text', { class: 'flow__n', x: x + 22, y: cy + 4 }, String(i + 1)));
      g.append(s('text', { class: 'flow__title', x: x + 42, y: cy - 3 }, st.title));
      g.append(s('text', { class: 'flow__sub', x: x + 42, y: cy + 14 }, st.sub));
      g.addEventListener('click', () => select(st.id));
      g.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          select(st.id, true);
        } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
          e.preventDefault();
          select(steps[Math.min(steps.length - 1, i + 1)].id, true);
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
          e.preventDefault();
          select(steps[Math.max(0, i - 1)].id, true);
        }
      });
      svg.append(g);
    });
  }

  if (typeof ResizeObserver === 'function') new ResizeObserver(() => draw()).observe(host);
  return { select, redraw: () => draw(), get selected() { return selected; } };
}
