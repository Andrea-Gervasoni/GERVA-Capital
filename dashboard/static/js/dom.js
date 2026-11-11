// Costruzione del DOM senza innerHTML: ogni testo dello snapshot passa da textContent / createTextNode,
// quindi una stringa ostile non diventa mai markup. Gli stili si impostano via CSSOM (ammesso dalla CSP).

const SVG_NS = 'http://www.w3.org/2000/svg';

function append(el, kids) {
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false || kid === true) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

/** h('div', {class: 'x', text: 'ciao', onclick: fn, style: {'--w': '40%'}}, ...figli) */
export function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  if (props) {
    for (const [key, value] of Object.entries(props)) {
      if (value == null || value === false) continue;
      if (key === 'class') el.className = value;
      else if (key === 'text') el.textContent = String(value);
      else if (key === 'dataset') Object.assign(el.dataset, value);
      else if (key === 'style') for (const [p, v] of Object.entries(value)) el.style.setProperty(p, String(v));
      else if (key.startsWith('on') && typeof value === 'function') el.addEventListener(key.slice(2), value);
      else if (value === true) el.setAttribute(key, '');
      else el.setAttribute(key, String(value));
    }
  }
  return append(el, kids);
}

/** Elemento SVG: s('path', {d: '...', class: 'c-line'}) */
export function s(tag, attrs, ...kids) {
  const el = document.createElementNS(SVG_NS, tag);
  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (value == null || value === false) continue;
      el.setAttribute(key, String(value));
    }
  }
  return append(el, kids);
}

/** Icona dallo sprite di index.html. */
export function icon(name, cls = '') {
  const svg = s('svg', { class: `icon ${cls}`.trim(), 'aria-hidden': 'true', focusable: 'false' });
  svg.append(s('use', { href: `#i-${name}` }));
  return svg;
}

export function fill(el, ...kids) {
  el.replaceChildren();
  return append(el, kids);
}

/** Lettura/scrittura di una preferenza: localStorage può mancare o lanciare. */
export function loadPref(key, fallback) {
  try {
    const v = window.localStorage.getItem(`gerva.dash.${key}`);
    return v == null ? fallback : v;
  } catch (e) {
    return fallback;
  }
}

export function savePref(key, value) {
  try {
    window.localStorage.setItem(`gerva.dash.${key}`, String(value));
  } catch (e) {
    /* senza archivio la preferenza vale solo per questa sessione */
  }
}
