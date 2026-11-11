// Come funziona: il percorso dai dati agli ordini disegnato come diagramma, e le quattro strategie spiegate.

import { h, s, fill } from '../dom.js';
import { card, empty, explain, simTag } from '../components.js';
import { arr, fmtNum, fmtPct, fmtPctSigned, num, obj, str } from '../format.js';
import { gloss } from '../glossary.js';

const STEPS = [
  {
    id: 'dati', title: 'Dati', sub: 'prezzi e volumi', file: 'gerva/live/runner.py',
    plain: 'A ogni giro il motore scarica i prezzi di chiusura e i volumi di crypto ed ETF. Usa soltanto ciò che era noto la sera prima: nessuna regola può «sbirciare» nel futuro.',
    expert: 'Il ciclo (runner) legge le barre giornaliere tramite gerva/live/market.py; i segnali usano grandezze spostate di un giorno, come nel backtest.',
  },
  {
    id: 'strategie', title: '4 strategie', sub: 'regole fisse', file: 'gerva/strategies/book.py',
    plain: 'Quattro insiemi di regole indipendenti trasformano i prezzi in pesi obiettivo: quanto tenere di ogni strumento. Sono le stesse identiche regole provate sui dati storici.',
    expert: 'Ogni strategia è una funzione pura dati → pesi sul capitale assegnato. La stessa definizione è usata dalla ricerca e dal ciclo live: il backtest descrive davvero ciò che gira.',
  },
  {
    id: 'quote', title: 'Quote', sub: 'parità di rischio', file: 'gerva/portfolio/allocate.py',
    plain: 'Il capitale si divide tra le strategie in modo che ognuna porti lo stesso rischio: a chi oscilla di più va una quota più piccola. Nessuna strategia può superare il 60%.',
    expert: 'Pesi ∝ 1/volatilità a 180 giorni, ricalcolati a inizio mese, con tetto al 60% e pavimento sulla volatilità. Non richiede stime dei rendimenti attesi.',
  },
  {
    id: 'leva', title: 'Leva', sub: '2x, mai oltre 3x', file: 'gerva/portfolio/allocate.py',
    plain: 'Il portafoglio viene portato a una leva del conto di 2x: l\'esposizione totale è il doppio del patrimonio. Il tetto è 3x. Oltre, nelle simulazioni, il rischio di dimezzare il conto cresce molto in fretta.',
    expert: 'Leva operativa 2x, tetto 3x (quant.json → leverage_decision). La leva del trade può essere più alta, ma il rischio lo fissa la distanza dello stop.',
  },
  {
    id: 'ai', title: 'Livello AI', sub: 'può solo ridurre', file: 'gerva/ai/desk.py', guard: true,
    plain: 'Un livello di controllo legge notizie, dati macro e regime di mercato. Può soltanto abbassare l\'esposizione o vietare una strategia, mai aumentarla né scegliere le operazioni. Ogni riduzione ha un motivo, delle fonti e una scadenza.',
    expert: 'Overlay AI: moltiplicatori in [0, 1] per strategia e globale, da desk LLM, regime deterministico e decadimento. Un errore costa un\'occasione persa, non denaro.',
  },
  {
    id: 'rischio', title: 'Motore di rischio', sub: 'decide per ultimo', file: 'gerva/risk/engine.py', guard: true,
    plain: 'Controlla limiti di leva, di peso per strumento e di perdita. Se il conto scende troppo dal suo massimo riduce l\'esposizione a scalini, fino al KILL che chiude tutto. Nessun agente e nessuna AI lo può scavalcare.',
    expert: 'Stati NORMAL → REDUCED → HALTED → KILLED con scale 1 / 0,5 / 0,25 / 0. KILLED è a ritenuta: serve rimuovere il file e dare `gerva reset-kill`.',
  },
  {
    id: 'ordini', title: 'Ordini', sub: 'solo le differenze', file: 'gerva/live/runner.py',
    plain: 'Il motore confronta ciò che ha con ciò che dovrebbe avere e manda solo gli ordini necessari a colmare la differenza. Ogni ordine viene registrato prima di partire e riconciliato dopo.',
    expert: 'Ordini idempotenti con registro (intent → filled/rejected), banda di non-operatività per evitare micro-ribilanciamenti, riconciliazione a ogni giro.',
  },
  {
    id: 'broker', title: 'Broker', sub: 'paper, poi reale', file: 'gerva/execution/broker.py',
    plain: 'Gli ordini arrivano al broker. Oggi è un conto di prova con prezzi veri (paper); il denaro reale arriva solo dopo che tutti i requisiti della sezione Sistema sono soddisfatti.',
    expert: 'Interfaccia unica (paper interno, Alpaca paper, poi reale): il ciclo non sa con quale broker parla.',
  },
];

const STRATEGY_COPY = {
  'CR-TREND': {
    what: 'Compra Bitcoin ed Ether quando sono in tendenza al rialzo e resta in liquidità quando non lo sono.',
    why: 'Nelle crypto le tendenze durano: ciò che sale tende a continuare per settimane. Restare fuori nei ribassi evita le cadute peggiori.',
    kills: 'Mercati laterali pieni di falsi segnali e inversioni improvvise dopo un forte rialzo.',
  },
  'CR-XSMOM': {
    what: 'Ogni settimana compra le 5 monete più forti tra le 20 più scambiate, solo se Bitcoin è sopra la sua media a 100 giorni.',
    why: 'Le monete che hanno reso di più nelle ultime settimane tendono a restare le migliori ancora per un po\'.',
    kills: 'Rotazioni brusche tra monete, crolli di tutto il mercato e ritardi di esecuzione: muove molto e paga più commissioni.',
  },
  'EQ-MR': {
    what: 'Compra S&P 500 e Nasdaq 100 dopo una chiusura debole e vende al rimbalzo, nel giro di pochi giorni.',
    why: 'Sugli indici azionari una giornata molto debole è spesso seguita da un recupero.',
    kills: 'Ribassi che proseguono per giorni senza rimbalzo. Un solo giorno di ritardo nell\'esecuzione toglie gran parte del vantaggio.',
  },
  'MA-TREND': {
    what: 'Segue le tendenze lente su 17 ETF di azioni, obbligazioni, oro, materie prime e valute, solo al rialzo.',
    why: 'Le tendenze lunghe esistono su molte classi di attivo, e questa strategia si muove in modo diverso dalle altre tre.',
    kills: 'Anni senza tendenze chiare. Da sola rende poco: il suo compito è stabilizzare il portafoglio.',
  },
};

export function mount(root) {
  let ctx = null;
  let selected = 'dati';
  let lastWidth = 0;
  let stratKey = null;

  const flowCard = card({
    title: 'Dai dati agli ordini', cls: 'span-12',
    sub: 'Otto passaggi, sempre nello stesso ordine. Tocca un passaggio per leggerne la spiegazione.',
    what: 'Il fondo non è una persona che decide: è una catena di passaggi automatici. I primi quattro costruiscono il portafoglio; il livello AI e il motore di rischio possono solo frenarlo; gli ultimi due lo eseguono.',
  });
  const svg = s('svg', { class: 'flow', role: 'group', 'aria-label': 'Diagramma di flusso del fondo: dai dati agli ordini' });
  const detail = h('div', { class: 'flow-detail', 'aria-live': 'polite' });
  const host = h('div', { class: 'flow-host' }, svg);
  flowCard.body.append(host, detail);

  const stratHead = h('div', { class: 'section-head span-12' });
  const stratGrid = h('div', { class: 'strats span-12' });
  root.append(h('div', { class: 'grid' }, flowCard.el, stratHead, stratGrid));

  function select(id, focus = false) {
    selected = id;
    drawFlow(true);
    paintDetail();
    if (focus) {
      const node = svg.querySelector(`[data-step="${id}"]`);
      if (node) node.focus();
    }
  }

  function paintDetail() {
    const i = STEPS.findIndex((x) => x.id === selected);
    const st = STEPS[i] || STEPS[0];
    fill(detail,
      h('div', { class: 'flow-detail__head' },
        h('span', { class: 'flow-detail__n num', text: String(i + 1) }),
        h('h3', { class: 'flow-detail__title', text: st.title }),
        st.guard ? h('span', { class: 'tag tag--paper', text: 'può solo frenare' }) : null),
      h('p', { class: 'flow-detail__text' }, gloss(st.plain)),
      h('p', { class: 'flow-detail__expert only-esperto' }, gloss(st.expert)),
      h('p', { class: 'flow-detail__file only-esperto' }, 'Codice: ', h('code', { text: st.file })));
  }

  function drawFlow(force = false) {
    const W = Math.floor(host.clientWidth);
    if (W < 120 || (!force && W === lastWidth)) return;
    lastWidth = W;
    svg.replaceChildren();
    const wide = W >= 720;
    const cols = wide ? 4 : 1;
    const gapX = wide ? 34 : 0;
    const gapY = wide ? 40 : 18;
    const nw = wide ? (W - gapX * (cols - 1) - 2) / cols : W - 2;
    const nh = wide ? 76 : 54;
    const pos = STEPS.map((_, i) => {
      const row = Math.floor(i / cols);
      const col = wide && row % 2 === 1 ? cols - 1 - (i % cols) : i % cols;      // la seconda riga torna indietro: a serpentina
      return { x: 1 + col * (nw + gapX), y: 1 + row * (nh + gapY) };
    });
    const H = pos[pos.length - 1].y + nh + 2;
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', W);
    svg.setAttribute('height', H);
    // frecce
    for (let i = 0; i < STEPS.length - 1; i++) {
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
    STEPS.forEach((st, i) => {
      const { x, y } = pos[i];
      const on = st.id === selected;
      const g = s('g', {
        class: `flow__node ${on ? 'is-on' : ''} ${st.guard ? 'flow__node--guard' : ''}`.trim(), role: 'button', tabindex: '0',
        'aria-pressed': String(on), 'aria-label': `Passaggio ${i + 1}: ${st.title}, ${st.sub}`, 'data-step': st.id,
      });
      g.append(s('rect', { class: 'flow__box', x, y, width: nw, height: nh, rx: 6 }));
      const cy = y + nh / 2;
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
          select(STEPS[Math.min(STEPS.length - 1, i + 1)].id, true);
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
          e.preventDefault();
          select(STEPS[Math.max(0, i - 1)].id, true);
        }
      });
      svg.append(g);
    });
  }

  if (typeof ResizeObserver === 'function') new ResizeObserver(() => drawFlow()).observe(host);

  function metricRows(sl) {
    const a = obj(sl.scelta);
    const b = obj(sl.verifica);
    const t = obj(sl.tutto);
    const row = (label, key, fmt, cls = '') => h('tr', { class: cls },
      h('th', { scope: 'row', text: label }),
      h('td', { class: 'num', text: fmt(a[key]) }), h('td', { class: 'num', text: fmt(b[key]) }),
      h('td', { class: 'num only-esperto', text: fmt(t[key]) }));
    const pct = (v) => (num(v) == null ? '—' : fmtPctSigned(v, 1));
    const neg = (v) => (num(v) == null ? '—' : fmtPct(v, 1));
    const rat = (v) => (num(v) == null ? '—' : fmtNum(v, 2));
    return h('table', { class: 'mini' },
      h('thead', null, h('tr', null, h('th', { scope: 'col', text: 'Simulato' }), h('th', { scope: 'col', class: 'num', text: 'Scelta' }), h('th', { scope: 'col', class: 'num', text: 'Verifica' }), h('th', { scope: 'col', class: 'num only-esperto', text: 'Tutto' }))),
      h('tbody', null,
        row('Rendimento annuo', 'cagr', pct), row('Sharpe', 'sharpe', rat), row('Caduta peggiore', 'max_dd', neg), row('Mese peggiore', 'mese_peggiore', neg),
        row('Volatilità', 'vol', neg, 'only-esperto'), row('Sortino', 'sortino', rat, 'only-esperto'), row('PSR', 'psr0', (v) => (num(v) == null ? '—' : fmtPct(v, 1)), 'only-esperto'),
        row('Mesi positivi', 'mesi_positivi', neg, 'only-esperto')));
  }

  function fillStrategies() {
    const q = ctx.quant;
    const live = arr(ctx.snap && ctx.snap.strategies);
    const sleeves = arr(q && q.sleeves);
    const key = JSON.stringify([sleeves, live.map((x) => [x.id, x.name, x.status])]);
    if (key === stratKey) return;
    stratKey = key;
    fill(stratHead,
      h('h2', { class: 'section-head__title', text: 'Le quattro strategie' }),
      q ? simTag(q.label) : null,
      explain('Per ognuna: che cosa fa, perché dovrebbe funzionare e che cosa la mette in difficoltà. I numeri vengono dalla ricerca sui dati storici, divisi tra periodo di scelta (fino al 2022) e periodo di verifica (dal 2023): se la verifica somiglia alla scelta, la regola non era solo fortuna.'));
    const ids = Object.keys(STRATEGY_COPY);
    fill(stratGrid, ids.map((id) => {
      const copy = STRATEGY_COPY[id];
      const sl = sleeves.find((x) => str(x.id) === id);
      const lv = live.find((x) => str(x.id) === id);
      return h('article', { class: 'card strat' },
        h('header', { class: 'strat__head' }, h('div', { class: 'strat__title' },
          h('span', { class: 'code code--strong', text: id }), h('h3', { class: 'strat__name', text: str(lv && lv.name) || '' }))),
        h('dl', { class: 'facts' },
          h('div', null, h('dt', { text: 'Che cosa fa' }), h('dd', { text: copy.what })),
          h('div', null, h('dt', { text: 'Perché dovrebbe funzionare' }), h('dd', { text: copy.why })),
          h('div', null, h('dt', { text: 'Che cosa la mette in crisi' }), h('dd', { text: copy.kills }))),
        sl ? metricRows(sl) : h('p', { class: 'muted', text: 'Numeri della ricerca non disponibili.' }));
    }));
  }

  return {
    update(next) {
      ctx = next;
      drawFlow();
      if (!detail.firstChild) paintDetail();
      fillStrategies();
      if (!STEPS.length) fill(flowCard.body, empty('Diagramma non disponibile'));
    },
    summary() {
      return 'Quattro strategie con regole fisse si dividono il capitale a parità di rischio; il livello AI può solo frenare e il motore di rischio decide per ultimo.';
    },
  };
}
