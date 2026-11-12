// Livello «Terminale», schermata d'apertura: a 1440 × 900 nulla scorre. Dieci riquadri su una griglia a 12 colonne:
//   1 fascia dei numeri · 2 grafico a candele con indicatori e righello del trade · 3 patrimonio contro benchmark, con la caduta
//   4 scala dei freni · 5 posizioni · 6 libro dei trade · 7 strategie · 8 attribuzione · 9 ordini · 0 avvisi
// Gli elenchi scorrono dentro il riquadro; i materiali sono gli stessi degli altri livelli (non è un altro tema).
// Tastiera: Tab e frecce passano da un riquadro all'altro · 1…9 e 0 saltano a un riquadro · j / k muovono la riga ·
// Invio apre lo strumento nel grafico (o lo spazio del riquadro) · o lo apre in Mercati · Esc torna al riquadro.
// La selezione è collegata: scegliere uno strumento in Posizioni, Libro dei trade o Ordini muove il grafico e segna gli altri elenchi.
// Sola lettura: nessuna richiesta che non sia GET parte da qui. Ogni grandezza derivata arriva da derive.js.

import { candleChart } from '../candles.js';
import { sparkline, timeChart } from '../charts.js';
import { segmented } from '../components.js';
import { h, icon } from '../dom.js';
import { arr, fmtAgo, fmtDate, fmtDayMonth, fmtMoney, fmtNum, fmtPct, fmtPctSigned, fmtSigned, num, obj, parseTs, str } from '../format.js';
import { getOhlc, getSymbols, getTradebook } from '../market.js';
import { alertLevel, curveOf, riskState } from '../model.js';
import { freshness, oldestSource, sigmaDay, totalNav, tradeAge, tradeR, watchedSymbols, worstCase } from '../derive.js';
import { brakeLadder, emptyState, freshLine, meterRow, panel, provOf, provTag, rollNumber, tradeMarkers } from '../panels.js';
import { ladderData, paperStart } from './oggi.js';

const DAY = 86400000;
const HHMM = new Intl.DateTimeFormat('it-IT', { hour: '2-digit', minute: '2-digit' });
const px = (v) => (v == null ? 'n.d.' : fmtNum(v, Math.abs(v) >= 1000 ? 0 : Math.abs(v) >= 10 ? 2 : 4));
const sign = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '');
const RANGES = [{ value: 1, label: '1M' }, { value: 3, label: '3M' }, { value: 6, label: '6M' }, { value: 12, label: '1A' }];
const EQ_RANGES = [{ value: 3, label: '3M' }, { value: 12, label: '1A' }, { value: 0, label: 'Avvio' }];

/** Un elenco dentro un riquadro: intestazione fissa, righe che scorrono, una riga scelta (j / k, clic), segno sugli strumenti collegati. */
function rowList(body, { cls, head, label, onPick, onOpen }) {
  const headEl = h('div', { class: `trow trow--head ${cls}`, 'aria-hidden': 'true' }, head.map((c) => h('span', { class: c.num ? 'is-num' : '', text: c.t })));
  const box = h('div', { class: 'tlist', role: 'listbox', 'aria-label': label });
  body.append(headEl, box);
  let items = [];
  let selKey = null;
  let sig = '';
  let linked = '';
  const paint = () => {
    for (const el of box.children) {
      const it = items[Number(el.dataset.i)];
      if (!it) continue;
      el.setAttribute('aria-selected', String(it.key === selKey));
      el.classList.toggle('is-linked', !!linked && it.sym === linked);
    }
  };
  const api = {
    box,
    /** items: [{ key, sym, cells: [nodo | testo], cls, data }]; empty: nodo mostrato se non ci sono righe. */
    set(next, empty = null) {
      items = next;
      const nodes = items.map((it, i) => {
        const el = h('div', { class: `trow ${cls} ${it.cls || ''}`.trim(), role: 'option', dataset: { i: String(i) } }, it.cells.map((c, k) => h('span', { class: `${head[k] && head[k].num ? 'is-num num' : ''} ${c && c.cls ? c.cls : ''}`.trim(), title: c && c.title ? c.title : null }, c && typeof c === 'object' && 'v' in c ? c.v : c)));
        el.addEventListener('click', () => { api.select(it.key); if (onPick) onPick(it); });
        el.addEventListener('dblclick', () => { if (onOpen) onOpen(it); });
        return el;
      });
      const nextSig = nodes.map((n, i) => `${items[i].key}|${n.textContent}`).join('\n');
      if (nextSig !== sig || (!items.length && empty)) {          // a dati invariati le righe restano dove sono: niente sfarfallio sotto il puntatore
        sig = nextSig;
        box.replaceChildren(...(nodes.length ? nodes : empty ? [empty] : []));
      }
      headEl.hidden = !items.length;
      if (selKey != null && !items.some((it) => it.key === selKey)) selKey = null;
      paint();
    },
    get items() { return items; },
    selected: () => items.find((it) => it.key === selKey) || null,
    select(key, { scroll = false } = {}) {
      selKey = key;
      paint();
      if (scroll) { const el = box.querySelector('[aria-selected="true"]'); if (el) el.scrollIntoView({ block: 'nearest' }); }
    },
    /** Sposta la riga scelta di d (j = +1, k = −1); senza riga scelta parte dalla prima. → la riga scelta. */
    move(d) {
      if (!items.length) return null;
      const i = items.findIndex((it) => it.key === selKey);
      const next = items[i < 0 ? 0 : Math.max(0, Math.min(items.length - 1, i + d))];
      api.select(next.key, { scroll: true });
      return next;
    },
    link(sym) { linked = sym || ''; paint(); },
  };
  return api;
}

export function mount(root, api) {
  let ctxNow = null;
  let tb;                        // undefined in arrivo · null assente
  let symbols;                   // strumenti con le barre: Map simbolo → tipo
  let sel = '';                  // strumento collegato tra i riquadri
  let bars = null;
  let months = 6;
  let eqMonths = 12;
  let period = 'day';
  let active = null;             // riquadro attivo (quello a fuoco, o l'ultimo che lo è stato)
  const barCache = new Map();    // simbolo → barre | null (assenti) | undefined (in lettura)
  document.body.dataset.term = '1';

  // ---- riquadri -------------------------------------------------------------------------------------------------------------
  const panels = [];
  const tp = (key, id, title, opts = {}) => {
    const p = panel({ title, what: opts.what || '', tools: opts.tools || null, cls: `tp tp--${id}`, span: 0, id: `t-${id}` });
    p.el.tabIndex = 0;
    p.el.dataset.key = key;
    p.id = id;
    p.title = title;
    p.meta = h('span', { class: 'tp__meta' });
    const row = p.el.querySelector('.card__title-row');
    row.prepend(h('kbd', { class: 'tp__n', 'aria-hidden': 'true', text: key }));
    row.append(p.meta);
    p.el.setAttribute('aria-label', `${title}: riquadro ${key}`);
    p.el.setAttribute('aria-keyshortcuts', key);
    panels.push(p);
    return p;
  };

  // 1 · fascia dei numeri
  const strip = h('section', { class: 'card tp tp--strip', id: 't-strip', tabindex: '0', 'aria-label': 'Numeri del conto: riquadro 1', 'aria-keyshortcuts': '1', dataset: { key: '1' } });
  const navNum = h('span', { class: 'kpi__big num' });
  const kpis = h('div', { class: 'kpis' });
  strip.append(h('kbd', { class: 'tp__n', 'aria-hidden': 'true', text: '1' }), kpis);
  panels.push({ el: strip, id: 'strip', title: 'Numeri del conto' });

  // 2 · grafico a candele
  const rangeSeg = segmented({ label: 'Intervallo del grafico', options: RANGES, value: months, onChange: (v) => { months = v; chart.setRange(v); } });
  const pChart = tp('2', 'chart', 'Grafico', { tools: rangeSeg.el,
    what: 'Candele giornaliere (vuota se ha chiuso in rialzo, piena se in ribasso) con medie a 50 e 200 giorni e VWAP del mese; sotto, volume, RSI e la conviction del motore. Se sullo strumento c\'è un trade aperto, a destra ci sono i cartellini di entrata, stop e liquidazione con la distanza dall\'ultima chiusura in % e in ATR.' });
  const chartHost = h('div', { class: 'tp__chart' });
  const chartNote = h('div', { class: 'tp__note' });
  pChart.body.append(chartHost, chartNote);
  const chart = candleChart(chartHost, { label: 'Grafico a candele dello strumento scelto', panes: ['rsi', 'conv'], overlays: ['sma50', 'sma200', 'vwap'] });

  // 3 · patrimonio contro benchmark
  const eqSeg = segmented({ label: 'Intervallo del patrimonio', options: EQ_RANGES, value: eqMonths, onChange: (v) => { eqMonths = v; eqMoved = true; paintEquity(); } });
  let eqMoved = false;
  const pEq = tp('3', 'equity', 'Patrimonio', { tools: eqSeg.el,
    what: 'La curva del patrimonio (tratteggiata fino all\'avvio del paper: simulata) contro il benchmark della fotografia, riportato al valore del fondo nel primo giorno dell\'intervallo. Sotto, la caduta dal massimo con gli scalini dei freni.' });
  const eqHost = h('div', { class: 'tp__plot' });
  const eqNote = h('div', { class: 'tp__note' });
  pEq.body.append(eqHost, eqNote);
  const eqChart = timeChart(eqHost, { label: 'Patrimonio, benchmark e caduta dal massimo' });

  // 4 · freni
  const pBrake = tp('4', 'brake', 'Freni', { what: 'Quanti punti mancano al prossimo scalino della caduta dal massimo, le due finestre mobili a 24 ore e 7 giorni contro la loro soglia, e il peggior caso di oggi (ipotesi simulata). La scala completa è nello spazio Rischio.' });
  const brakeBig = h('div', { class: 'tp__big' });
  const brakeHost = h('div', { class: 'chart-host' });
  const brakeLanes = h('div', { class: 'lanes' });
  const brakeWorst = h('div', { class: 'tp__line' });
  pBrake.body.append(brakeBig, brakeHost, brakeLanes, brakeWorst);
  const ladder = brakeLadder(brakeHost, { compact: true, label: 'Distanza dai freni automatici' });

  // 5 · posizioni
  const pPos = tp('5', 'pos', 'Posizioni', { what: 'Che cosa ha in mano il fondo adesso: peso sul patrimonio, controvalore e risultato di oggi per strumento. Scegli una riga: il grafico la segue.' });
  const posList = rowList(pPos.body, { cls: 'tl--pos', label: 'Posizioni', head: [{ t: 'Sigla' }, { t: 'Strategia' }, { t: 'Peso', num: 1 }, { t: 'Valore', num: 1 }, { t: 'Oggi', num: 1 }],
    onPick: (it) => pick(it.sym), onOpen: (it) => api.go('mercati', '', { s: it.sym }) });

  // 6 · libro dei trade
  const pBook = tp('6', 'book', 'Libro dei trade', { what: 'I trade a margine isolato: prima gli aperti (R all\'ultima chiusura, distanza dallo stop, giorno su durata massima, margine), poi gli ultimi chiusi con R e motivo dell\'uscita.' });
  const bookList = rowList(pBook.body, { cls: 'tl--book', label: 'Libro dei trade', head: [{ t: 'Trade' }, { t: 'R', num: 1 }, { t: 'Stop · uscita', num: 1 }, { t: 'G.', num: 1 }],
    onPick: (it) => { pick(it.sym); frame(it.data); }, onOpen: (it) => api.go('mercati', '', { s: it.sym }) });

  // 7 · strategie
  const pStrat = tp('7', 'strat', 'Strategie', { what: 'Le quattro strategie: quota del portafoglio, esposizione, risultato di oggi e del mese, andamento recente. Lo Sharpe in paper non compare prima di 60 giorni: fino ad allora non misura nulla.' });
  const stratList = rowList(pStrat.body, { cls: 'tl--strat', label: 'Strategie', head: [{ t: 'Strategia' }, { t: 'Peso', num: 1 }, { t: 'Oggi', num: 1 }, { t: 'Mese', num: 1 }, { t: '30 g' }], onOpen: () => api.go('portafoglio', 'strategie') });

  // 8 · attribuzione
  const perSeg = segmented({ label: 'Periodo dell\'attribuzione', options: [{ value: 'day', label: 'Oggi' }, { value: 'mtd', label: 'Mese' }], value: period, onChange: (v) => { period = v; paintAttr(); } });
  const pAttr = tp('8', 'attr', 'Attribuzione', { tools: perSeg.el, what: 'Da dove viene il risultato: contributo di ogni strategia in euro e in punti base del patrimonio. «Non attribuito» è ciò che la somma non spiega; il contributo del libro dei trade non è nella fotografia e resta n.d.' });
  const attrBox = h('div', { class: 'attr' });
  const attrFoot = h('div', { class: 'tp__line' });
  pAttr.body.append(attrBox, attrFoot);

  // 9 · ordini
  const pOrd = tp('9', 'orders', 'Ordini', { what: 'Il registro degli ordini della fotografia, dal più recente: ora, strumento, lato, quantità, prezzo ed esito. Un rifiuto porta il motivo del controllo di rischio.' });
  const ordList = rowList(pOrd.body, { cls: 'tl--ord', label: 'Ordini', head: [{ t: 'Ora' }, { t: 'Sigla' }, { t: 'Lato' }, { t: 'Valore', num: 1 }, { t: 'Esito' }],
    onPick: (it) => pick(it.sym), onOpen: () => api.go('sistema', 'ordini') });

  // 0 · avvisi
  const pAl = tp('0', 'alerts', 'Avvisi', { what: 'Gli avvisi del motore, dal più grave al più lieve e dal più recente. Il centro avvisi completo si apre con il tasto a.' });
  const alList = rowList(pAl.body, { cls: 'tl--al', label: 'Avvisi', head: [{ t: '' }, { t: 'Avviso' }, { t: 'Quando', num: 1 }], onOpen: () => api.openAlerts() });

  const hint = h('div', { class: 'tgrid__hint' });
  const hintActive = h('span', { class: 'tgrid__active', role: 'status' });
  const kb = (k, text) => h('span', null, h('kbd', { text: k }), ` ${text}`);
  hint.append(kb('/', 'cerca'), kb('1…9 0', 'riquadro'), kb('Tab ← →', 'riquadro vicino'), kb('j k', 'riga'), kb('Invio', 'apri nel grafico'), kb('o', 'apri in Mercati'), kb('i', 'in una frase'), kb('a', 'avvisi'), kb('?', 'scorciatoie'),
    h('a', { class: 'tgrid__more', href: '#/rischio' }, 'Rischio'), h('a', { class: 'tgrid__more', href: '#/mercati' }, 'Mercati'), hintActive);

  root.append(h('div', { class: 'tgrid' }, strip, pChart.el, pEq.el, pBrake.el, pPos.el, pBook.el, pStrat.el, pAttr.el, pOrd.el, pAl.el, hint));
  const lists = { pos: posList, book: bookList, strat: stratList, orders: ordList, alerts: alList };

  // ---- selezione collegata ----------------------------------------------------------------------------------------------------
  function loadBars(sym) {
    if (barCache.has(sym)) return;
    barCache.set(sym, undefined);
    if (symbols && !symbols.has(sym)) { barCache.set(sym, null); return; }
    getOhlc(sym, 1500).then((o) => { barCache.set(sym, o && o.c && o.c.length > 1 ? o : null); if (ctxNow) { if (sym === sel) paintChart(true); paintBook(); paintStrip(); } });
  }
  /** Sceglie lo strumento: il grafico lo segue, gli elenchi lo segnano, l'indirizzo lo ricorda. */
  function pick(sym, { reset = true } = {}) {
    if (!sym) return;
    const changed = sym !== sel;
    sel = sym;
    api.setParams({ s: sym });
    for (const l of Object.values(lists)) l.link(sym);
    if (changed) { loadBars(sym); paintChart(reset); }
  }
  function frame(t) {
    const o = barCache.get(sel);
    if (!o || !t) return;
    const a = parseTs(str(t.opened));
    const b = parseTs(str(t.closed)) ?? o.t[o.t.length - 1];
    if (a != null) chart.setWindow(a - 25 * DAY, b + 12 * DAY);
  }

  // ---- disegno ------------------------------------------------------------------------------------------------------------------
  /** Regola dell'eredità: la provenienza della fotografia sta nella fascia dei numeri; un riquadro porta l'etichetta solo se è diversa. */
  const provIf = (p, kind, text = '') => p.setProv(kind && kind !== provOf(ctxNow.snap.meta) ? provTag(kind, text) : null);
  const kpi = (label, value, sub = null, cls = '') => h('div', { class: `kpi ${cls}`.trim() }, h('span', { class: 'kpi__k', text: label }), h('span', { class: 'kpi__v num' }, value), sub ? h('span', { class: 'kpi__s num' }, sub) : null);
  const openTrades = () => Object.values(obj(obj(tb).open)).filter((t) => t && typeof t === 'object');

  function paintStrip() {
    const { snap, ccy, fresh, now } = ctxNow;
    const nav = obj(snap.nav);
    const risk = obj(snap.risk);
    const ex = obj(snap.exposure);
    const tn = totalNav(snap, tb);
    const total = tb === undefined ? null : tn.total;
    if (total == null) navNum.textContent = tb === undefined ? '…' : 'n.d.'; else rollNumber(navNum, fmtMoney(total, ccy));
    const day = num(nav.pnl_day);
    const sg = sigmaDay(snap);
    const ps = paperStart(snap);
    const bk = ladderData(ctxNow, tb).b;
    const lev = num(ex.leverage);
    const cap = num(ex.max_leverage) ?? num((arr(risk.limits).find((l) => /leva/i.test(str(l.name))) || {}).limit);
    const v = num(risk.var_95_1d_pct);
    const eq = num(nav.equity);
    const open = openTrades();
    const atRisk = open.reduce((a, t) => a + (num(t.risk) || 0), 0);
    const rules = obj(obj(ctxNow.health).rules);
    const srcs = [tb ? { name: 'libro dei trade', day: parseTs(str(tb.asof)), kind: 'crypto' } : null, ...watchedSymbols(snap, tb).map((w) => { const o = barCache.get(w.symbol); return o ? { name: `barre ${w.symbol}`, day: o.t[o.t.length - 1], kind: w.kind } : null; })].filter(Boolean);
    const old = oldestSource(srcs, now, rules);
    const mixedTag = () => h('span', { class: 'kpi__sim', title: 'Il periodo contiene giorni simulati prima dell\'avvio del paper', text: 'sim+' });
    const pct = (val, mixed) => (val == null ? 'n.d.' : [h('span', { class: sign(val), text: fmtPctSigned(val, 2) }), mixed ? mixedTag() : null]);
    const end = new Date(now);
    const mixedFrom = (from) => ps.t != null && from < ps.t - DAY / 2;
    kpis.replaceChildren(
      h('div', { class: 'kpi kpi--nav' }, h('span', { class: 'kpi__k' }, 'Patrimonio ', provTag(provOf(snap.meta))), navNum,
        h('span', { class: 'kpi__s num', text: tb === undefined ? 'libro dei trade in lettura' : !tn.complete ? 'solo libro giornaliero: trade n.d.' : `libro ${fmtMoney(tn.daily, ccy, { digits: 0 })} · trade ${fmtMoney(tn.tradeGain, ccy, { digits: 0, signed: true })}` })),
      kpi('Oggi', day == null ? 'n.d.' : [day === 0 ? null : icon(day > 0 ? 'up' : 'down', 'icon--solid'), h('span', { text: `${fmtMoney(day, ccy, { signed: true })} · ${fmtPctSigned(num(nav.pnl_day_pct), 2)}` })], sg ? `${fmtSigned(sg.z, 1)} σ sull'obiettivo ${fmtPct(sg.target, 0)}` : 'σ n.d.', sign(day)),
      kpi('Mese · Anno · Avvio', [pct(num(nav.pnl_mtd_pct), mixedFrom(Date.UTC(end.getUTCFullYear(), end.getUTCMonth(), 1))), ' · ', pct(num(nav.pnl_ytd_pct), mixedFrom(Date.UTC(end.getUTCFullYear(), 0, 1))), ' · ', pct(num(nav.pnl_total_pct), !!ps.simDays)].flat(),
        ps.simDays ? `sim+ contiene ${fmtNum(ps.simDays, 0)} giorni simulati` : ps.days != null ? `paper da ${fmtNum(ps.days, 0)} giorni` : ''),
      kpi('Al prossimo freno', !fresh ? 'sconosciuta' : !bk.steps.length || bk.dd == null ? 'soglia non letta' : !bk.next ? 'ultimo scalino superato' : `${fmtNum(bk.distNext * 100, 1)} punti`, !fresh ? 'dati fermi' : bk.next && bk.dd != null ? `al ${fmtPct(bk.next.level, 0)} · ora ${fmtPctSigned(bk.dd, 1)}` : '', !fresh ? 'is-unknown' : ''),
      kpi('Leva', `${lev == null ? 'n.d.' : `${fmtNum(lev, 2)}x`}${cap == null ? '' : ` / ${fmtNum(cap, 0)}x`}`, `lordo ${num(ex.gross) == null ? 'n.d.' : fmtPct(ex.gross, 0)} · netto ${num(ex.net) == null ? 'n.d.' : fmtPct(ex.net, 0)}`.replace(/ %/g, '%')),
      kpi('VaR 95% · 1 g', v == null ? 'n.d.' : `${fmtPct(Math.abs(v), 2)}${eq ? ` · ${fmtMoney(Math.abs(v) * eq, ccy, { digits: 0 })}` : ''}`, `vol ${num(risk.vol_realized_30d) == null ? 'n.d.' : fmtPct(risk.vol_realized_30d, 1)} / ${num(risk.vol_target) == null ? 'n.d.' : fmtPct(risk.vol_target, 0)}`),
      kpi('A rischio nei trade', tb === undefined ? '…' : !tb ? 'n.d.' : fmtMoney(atRisk, ccy), tb ? `${fmtNum(open.length, 0)} ${open.length === 1 ? 'aperto' : 'aperti'}${tn.total ? ` · ${fmtPct(atRisk / tn.total, 2)}` : ''}` : 'libro non disponibile'),
      h('div', { class: 'kpi kpi--src' }, h('span', { class: 'kpi__k', text: 'Fonti' }),
        freshLine([{ name: 'conto', text: ctxNow.status === 'offline' ? 'offline' : fresh ? 'adesso' : 'fermo', stale: !fresh },
          tb ? { name: 'libro', text: str(tb.asof) ? fmtDayMonth(parseTs(str(tb.asof)), true) : 'senza data', stale: !!(old && old.name === 'libro dei trade') } : tb === null ? { name: 'libro', text: 'assente', stale: true } : null,
          { name: 'barre', text: old && old.name !== 'libro dei trade' ? `${old.name.replace('barre ', '')} al ${fmtDayMonth(old.day, true)}` : srcs.length > (tb ? 1 : 0) ? fmtDayMonth(Math.min(...srcs.filter((sc) => sc.name !== 'libro dei trade').map((sc) => sc.day)), true) : 'in lettura', stale: !!(old && old.name !== 'libro dei trade') }])));
  }

  function paintChart(reset = false) {
    if (!sel) { chartNote.textContent = 'Scegli uno strumento in Posizioni o nel Libro dei trade.'; pChart.meta.textContent = ''; return; }
    const o = barCache.get(sel);
    const kind = symbols && symbols.get(sel);
    pChart.el.querySelector('.card__title').textContent = `Grafico · ${sel}`;
    if (o === undefined) { chartNote.textContent = `${sel}: barre in lettura…`; return; }
    if (!o) {
      bars = null;
      chart.setData(null);
      chartNote.textContent = `${sel}: nessuna barra giornaliera nella cache dei prezzi. Il grafico resta vuoto finché il motore non le scarica.`;
      pChart.setProv();
      pChart.meta.textContent = '';
      return;
    }
    bars = o;
    chart.setData({ ...o, markers: tb ? tradeMarkers(o, sel, tb) : [] }, { keepView: !reset, months });
    const n = o.c.length;
    const chg = o.c[n - 2] ? o.c[n - 1] / o.c[n - 2] - 1 : null;
    const hasTrade = openTrades().some((t) => str(t.symbol) === sel);
    pChart.setProv(o.example && provOf(ctxNow.snap.meta) === 'demo' ? null : provTag(o.example ? 'demo' : 'real', o.example ? 'Esempio' : 'Prezzi reali'), hasTrade && !(tb && tb.example && provOf(ctxNow.snap.meta) === 'demo') ? provTag(tb && tb.example ? 'demo' : 'paper', tb && tb.example ? 'Trade · esempio' : 'Trade · paper') : null);
    pChart.meta.replaceChildren(h('b', { class: 'num', text: px(o.c[n - 1]) }), chg == null ? '' : h('span', { class: `num ${sign(chg)}`, text: ` ${fmtPctSigned(chg, 2)}` }));
    const fr = freshness(o.t[n - 1], ctxNow.now, kind === 'crypto' ? 'crypto' : 'ibkr', obj(obj(ctxNow.health).rules));
    chartNote.replaceChildren(fr.stale ? h('b', { class: 'neg', text: `Dati fermi: ultima barra del ${fmtDate(o.t[n - 1], true)}. ` }) : `ultima barra chiusa ${fmtDayMonth(o.t[n - 1], true)}`, !o.conviction ? ' · conviction non calcolata per questo strumento' : '', ' · SMA 50 · SMA 200 · VWAP mese');
  }

  function paintEquity() {
    const { snap, ccy } = ctxNow;
    const curve = curveOf(snap);
    const n = curve.t.length;
    const prov = provOf(snap.meta);
    if (n < 2) { eqChart.update(null); eqNote.textContent = 'Curva non disponibile: servono almeno due giorni di storico.'; return; }
    const ps = paperStart(snap);
    let i0 = 0;
    if (eqMonths) { const end = new Date(curve.t[n - 1]); const cut = Date.UTC(end.getUTCFullYear(), end.getUTCMonth() - eqMonths, end.getUTCDate()); while (i0 < n - 2 && curve.t[i0] < cut) i0++; }
    const x = curve.t;
    const e = curve.equity;
    const kp = ps.t == null ? -1 : x.findIndex((tt) => tt >= ps.t - DAY / 2);
    const split = prov !== 'sim' && kp > 0;
    // benchmark riportato al valore del fondo nel primo giorno dell'intervallo: un solo asse
    const b0 = curve.hasBench ? curve.bench[i0] : null;
    const bench = b0 ? curve.bench.map((v) => (v == null ? null : (v / b0) * e[i0])) : null;
    const total = Math.max(110, eqHost.clientHeight || 0);
    const ddH = Math.max(26, Math.min(44, Math.round(total * 0.2)));
    const mainH = Math.max(40, total - ddH - 48);                 // 6 sopra + 14 tra i due + 24 di asse, più un margine
    const series = [
      bench ? { values: bench, cls: 'bench', name: 'Benchmark' } : null,
      ...(split ? [{ values: e.map((v, i) => (i <= kp ? v : null)), cls: 'fund sim', name: 'Patrimonio (simulato)' }, { values: e.map((v, i) => (i >= kp ? v : null)), cls: 'fund', area: true, end: true, name: 'Patrimonio (paper)' }]
        : [{ values: e, cls: prov === 'sim' || (ps.t != null && kp < 0) ? 'fund sim' : 'fund', area: true, end: true, name: 'Patrimonio' }]),
    ].filter(Boolean);
    const last = n - 1;
    const rel = bench && bench[last] ? e[last] / e[i0] - bench[last] / bench[i0] : null;
    eqNote.replaceChildren(rel == null ? 'benchmark n.d.' : h('b', { class: `num ${sign(rel)}`, text: `${fmtSigned(rel * 100, 1)} punti` }), rel == null ? '' : ' sul benchmark · sotto: caduta', split && kp > i0 ? ' · tratteggio: simulato' : '');
    eqChart.update({
      x,
      marks: split ? [{ t: x[kp], label: 'avvio del paper' }] : [],
      panels: [
        { height: mainH, series, format: (v) => fmtNum(v, 0) },
        { height: ddH, top: 0, series: [{ values: curve.dd, cls: 'dd', area: true, name: 'Caduta' }], format: (v) => fmtPct(v, 0),
          refs: arr(obj(snap.risk).dd_ladder).filter((st) => num(st.level) != null && st.level >= Math.min(...curve.dd.slice(i0).filter((v) => v != null)) * 1.6).map((st) => ({ value: st.level, label: fmtPct(st.level, 0) })) },
      ],
      tip: (i) => ({ title: fmtDate(x[i], true), rows: [{ key: 'fund', label: 'Patrimonio', value: fmtMoney(e[i], ccy) }, bench ? { key: 'bench', label: 'Benchmark (riportato)', value: bench[i] == null ? '—' : fmtMoney(bench[i], ccy) } : null,
        { key: 'dd', label: 'Caduta dal massimo', value: curve.dd[i] == null ? '—' : fmtPctSigned(curve.dd[i], 2) }, ps.t != null ? { label: 'Provenienza', value: x[i] < ps.t - DAY / 2 ? 'Simulato' : prov === 'demo' ? 'Paper (esempio)' : 'Paper' } : null].filter(Boolean) }),
      say: (i) => `${fmtDate(x[i], true)}: patrimonio ${fmtMoney(e[i], ccy)}, caduta ${curve.dd[i] == null ? 'non disponibile' : fmtPctSigned(curve.dd[i], 2)}`,
    });
    eqChart.setWindow(x[i0], x[last], { animate: eqMoved });
    eqMoved = false;
  }

  function paintBrake() {
    const { snap, ccy, fresh } = ctxNow;
    const worst = worstCase(snap, tb, ctxNow.quant4);
    const d = ladderData(ctxNow, tb, null);
    const b = d.b;
    brakeBig.replaceChildren(...(!b.steps.length || b.dd == null ? ['soglia non letta'] : !fresh ? ['sconosciuta', h('small', { text: 'dati fermi: nessuna distanza si può confermare' })] : !b.next ? ['ultimo scalino superato'] : [`${fmtNum(b.distNext * 100, 1)} punti`,
      h('small', { class: 'num', text: `${b.hit ? `al ${fmtPct(b.next.level, 0)} · ` : ''}${b.peak == null ? '' : `${fmtMoney(b.distNext * b.peak, ccy, { digits: 0 })}`}${b.es ? ` · ${fmtNum(b.distNext / b.es, 0)} giornate di ES` : ''}` })]));
    ladder.update(d);
    brakeLanes.replaceChildren(...b.lanes.map((l) => meterRow({ name: l.label.replace('Ultime ', '').replace('Ultimi ', ''), value: !fresh || l.value == null ? 0 : Math.max(0, -l.value), cap: Math.abs(l.limit), state: !fresh || l.value == null ? 'none' : l.value <= l.limit ? 'breach' : -l.value / Math.abs(l.limit) >= 0.6 ? 'warn' : 'ok',
      text: !fresh ? 'sconosciuta' : l.value == null ? 'non calcolabile' : `${fmtPctSigned(l.value, 2)} / ${fmtPct(l.limit, 0)}` })));
    brakeWorst.replaceChildren(...(!worst ? ['Peggior caso di oggi: n.d.'] : [provTag('sim', 'Sim'), h('span', { class: 'k', text: ' Peggior caso ' }), h('b', { class: 'num neg', text: `${worst.atLeast ? 'almeno ' : ''}${fmtPctSigned(-worst.loss, 1)}` }),
      worst.stepHit ? ` → scalino ${fmtPct(worst.stepHit.level, 0)}` : worst.dayHit ? ` → ${fmtPct(worst.dayLimit, 0)} / 24 h` : worst.atLeast ? '' : ' → nessun freno']));
    brakeWorst.title = worst ? `Ipotesi simulata: tutti i trade perdono il margine e il libro giornaliero subisce la peggiore giornata storica. ${worst.stepHit ? `Scatterebbe lo scalino ${fmtPct(worst.stepHit.level, 0)}.` : worst.dayHit ? `Scatterebbe il freno delle 24 ore (${fmtPct(worst.dayLimit, 0)}).` : ''}` : '';
    brakeWorst.classList.toggle('is-unknown', !fresh);
    if (b.hit && b.reentry != null) pBrake.meta.textContent = `rientro sotto ${fmtPct(b.reentry, 0)}`; else pBrake.meta.textContent = '';
  }

  function paintPositions() {
    const { snap, ccy } = ctxNow;
    const pos = arr(snap.positions);
    const ex = obj(snap.exposure);
    pPos.meta.textContent = `${fmtNum(pos.length, 0)} · lordo ${num(ex.gross) == null ? 'n.d.' : fmtPct(ex.gross, 0)} · netto ${num(ex.net) == null ? 'n.d.' : fmtPct(ex.net, 0)}`;
    const rows = [...pos].sort((a, b) => Math.abs(num(b.weight) || 0) - Math.abs(num(a.weight) || 0)).map((p) => {
      const sym = str(p.symbol).toUpperCase();
      const d = num(p.pnl_day);
      return { key: `${sym}|${str(p.strategy)}`, sym, cells: [h('b', { text: sym }), { v: str(p.strategy) || 'n.d.', cls: 'dim' }, num(p.weight) == null ? 'n.d.' : fmtPct(p.weight, 1), num(p.value) == null ? 'n.d.' : fmtMoney(p.value, ccy, { digits: 0 }),
        { v: d == null ? 'n.d.' : fmtMoney(d, ccy, { signed: true }), cls: sign(d) }] };
    });
    posList.set(rows, emptyState('Nessuna posizione', 'Il fondo è in liquidità.'));
  }

  function paintBook() {
    const { snap, ccy } = ctxNow;
    if (tb === undefined) { bookList.set([], emptyState('Libro dei trade in lettura…')); return; }
    if (!tb) { bookList.set([], emptyState('Libro dei trade non disponibile', 'Il motore non ha ancora scritto lo stato del libro a margine isolato.')); pBook.setProv(); pBook.meta.textContent = ''; return; }
    provIf(pBook, tb.example ? 'demo' : provOf(snap.meta) === 'real' ? 'real' : 'paper');
    const rules = obj(obj(ctxNow.health).rules);
    const open = openTrades();
    const tbFresh = freshness(parseTs(str(tb.asof)), ctxNow.now, 'crypto', rules);
    const total = totalNav(snap, tb).total;
    const margin = open.reduce((a, t) => a + (num(t.margin) || 0), 0);
    const risk = open.reduce((a, t) => a + (num(t.risk) || 0), 0);
    pBook.meta.replaceChildren(tbFresh.stale ? h('b', { class: 'neg', text: `fermo al ${fmtDayMonth(tbFresh.day, true)} · ` }) : '', `${fmtNum(open.length, 0)} ${open.length === 1 ? 'aperto' : 'aperti'}${total ? ` · rischio ${fmtPct(risk / total, 2)} · margini ${fmtPct(margin / total, 1)}` : ''}`);
    const rows = open.map((t) => {
      const sym = str(t.symbol);
      loadBars(sym);
      const o = barCache.get(sym);
      const last = o ? o.c[o.c.length - 1] : null;
      const r = tradeR(t, last);
      const age = tradeAge(t, tb, rules);
      const atr = num(obj(t.ctx).atr_pct);
      const ds = last != null && num(t.stop) ? last / t.stop - 1 : null;
      return { key: `open|${sym}`, sym, data: t, cls: tbFresh.stale ? 'is-stale' : '', cells: [h('span', null, h('b', { text: sym }), ` ${num(t.side) === -1 ? '▼' : '▲'} ${fmtNum(t.leverage, 0)}x`), { v: r == null ? '…' : `${fmtSigned(r, 2)} R`, cls: sign(r) },
        { v: ds == null ? '…' : `${fmtPct(ds, 1)}${atr ? ` · ${fmtNum(ds / atr, 1)} ATR` : ''}`, title: `Stop ${px(num(t.stop))} · liquidazione ${px(num(t.liquidation))} · margine ${fmtMoney(num(t.margin), ccy)} · a rischio ${fmtMoney(num(t.risk), ccy)}` },
        { v: age.held == null ? 'n.d.' : `${fmtNum(age.held, 0)}${age.maxHold == null ? '' : `/${fmtNum(age.maxHold, 0)}`}`, cls: age.over ? 'neg' : '' }] };
    });
    const closed = [...arr(tb.closed)].reverse().slice(0, 12).map((t, i) => {
      const day = parseTs(str(t.closed));
      return { key: `closed|${i}|${str(t.symbol)}|${str(t.closed)}`, sym: str(t.symbol), data: t, cls: 'trow--past', cells: [h('span', { title: 'Trade chiuso' }, h('b', { text: str(t.symbol) }), ` · ${day == null ? 'n.d.' : fmtDayMonth(day, true)}`), { v: num(t.R) == null ? 'n.d.' : `${fmtSigned(t.R, 2)} R`, cls: sign(num(t.R)) },
        { v: `${str(t.why) || 'n.d.'} · ${fmtMoney(num(t.pnl), ccy, { digits: 0, signed: true })}`, cls: 'dim' }, { v: '', cls: 'dim' }] };
    });
    bookList.set([...rows, ...closed], emptyState('Nessun trade', 'Il libro apre solo nei giorni ad alta conviction.'));
  }

  function paintStrategies() {
    const { snap } = ctxNow;
    const ov = new Map(arr(obj(obj(snap.ai).overlay).strategie).map((st) => [str(st.id), num(st.mult)]));
    const ps = paperStart(snap);
    pStrat.meta.textContent = ps.days != null && ps.days < 60 ? `Sharpe paper: — · ${fmtNum(ps.days, 0)} giorni su 60` : '';
    stratList.set(arr(snap.strategies).map((st) => {
      const mult = ov.get(str(st.id));
      return { key: str(st.id), sym: '', cells: [h('span', { title: str(st.name) }, h('b', { text: str(st.id) }), mult != null && mult < 1 ? h('span', { class: 'tchip tchip--ai', title: `Freno dell'AI in vigore: quota × ${fmtNum(mult, 2)}`, text: `×${fmtNum(mult, 2, 0)}` }) : null),
        num(st.allocation) == null ? 'n.d.' : fmtPct(st.allocation, 0), { v: num(st.pnl_day_pct) == null ? 'n.d.' : fmtPctSigned(st.pnl_day_pct, 2), cls: sign(num(st.pnl_day_pct)) }, { v: num(st.pnl_mtd_pct) == null ? 'n.d.' : fmtPctSigned(st.pnl_mtd_pct, 2), cls: sign(num(st.pnl_mtd_pct)) },
        sparkline(st.spark, { width: 30, height: 18, label: `Andamento di ${str(st.id)}` })] };
    }), emptyState('Nessuna strategia nella fotografia'));
  }

  function paintAttr() {
    const { snap, ccy } = ctxNow;
    const nav = obj(snap.nav);
    const eq = num(nav.equity);
    let rows = [];
    let total = null;
    if (period === 'day') {
      const by = new Map();
      for (const p of arr(snap.positions)) if (num(p.pnl_day) != null) by.set(str(p.strategy), (by.get(str(p.strategy)) || 0) + p.pnl_day);
      rows = arr(snap.strategies).map((st) => ({ label: str(st.id), value: by.get(str(st.id)) ?? null })).filter((r) => r.value != null);
      total = num(nav.pnl_day);
    } else {
      const pctAll = num(nav.pnl_mtd_pct);
      const startEq = eq != null && pctAll != null ? eq / (1 + pctAll) : null;
      rows = startEq == null ? [] : arr(snap.strategies).map((st) => ({ label: str(st.id), value: num(st.allocation) != null && num(st.pnl_mtd_pct) != null ? st.allocation * st.pnl_mtd_pct * startEq : null })).filter((r) => r.value != null);
      total = startEq == null ? null : eq - startEq;
    }
    if (!rows.length || total == null) { attrBox.replaceChildren(emptyState('Nessun contributo per questo periodo', 'La fotografia non riporta il P&L per strategia.')); attrFoot.replaceChildren(); return; }
    rows.sort((a, b) => b.value - a.value);
    const gap = total - rows.reduce((a, r) => a + r.value, 0);
    const all = [...rows, { label: 'Non attribuito', value: gap, dim: Math.abs(gap) < 0.005 }];
    const top = Math.max(...all.map((r) => Math.abs(r.value || 0)), 1e-9);
    const bp = (v) => (eq ? `${fmtSigned((v / eq) * 10000, 1)} pb` : '');
    attrBox.replaceChildren(...all.map((r) => {
      const bar = h('span', { class: `attr__bar ${r.value < 0 ? 'is-neg' : ''}`.trim(), 'aria-hidden': 'true' }, h('i'));
      bar.style.setProperty('--v', `${r.value == null ? 0 : Math.max(1.5, (Math.abs(r.value) / top) * 50).toFixed(1)}%`);
      return h('div', { class: `attr__row ${r.dim || r.value == null ? 'is-dim' : ''}`.trim() }, h('span', { class: 'attr__k', text: r.label }), bar,
        h('span', { class: `attr__v num ${sign(r.value)}`, text: r.value == null ? r.note : `${fmtMoney(r.value, ccy, { signed: true })} · ${bp(r.value)}` }));
    }), h('div', { class: 'attr__row attr__row--total' }, h('span', { class: 'attr__k', text: 'Totale' }), h('span'), h('span', { class: `attr__v num ${sign(total)}`, text: `${fmtMoney(total, ccy, { signed: true })} · ${bp(total)}` })));
    const byPos = arr(snap.positions).filter((p) => num(p.pnl_day) != null).sort((a, b) => b.pnl_day - a.pnl_day);
    const names = (list) => list.map((p) => `${str(p.symbol)} ${fmtSigned(p.pnl_day, 2)}`).join(' · ');
    attrFoot.replaceChildren(...(period === 'day' && byPos.length ? [h('span', { class: 'k', text: 'Migliori ' }), h('span', { class: 'num', text: names(byPos.slice(0, 2)) }), h('span', { class: 'k', text: '  Peggiori ' }), h('span', { class: 'num', text: names(byPos.slice(-2).reverse()) })]
      : [h('span', { class: 'k', text: 'Stima: quota × rendimento × patrimonio a inizio mese.' })]));
    attrFoot.title = `${attrFoot.textContent} · Libro giornaliero: il contributo del libro dei trade non è nella fotografia (n.d.).`;
  }

  function paintOrders() {
    const { snap, ccy, now } = ctxNow;
    const orders = arr(snap.orders).map((o) => ({ ...o, ts: parseTs(o.t) })).sort((a, b) => (b.ts || 0) - (a.ts || 0));
    const st = (o) => str(o.status).toLowerCase();
    const n = (re) => orders.filter((o) => re.test(st(o))).length;
    pOrd.meta.textContent = `${fmtNum(n(/fill/), 0)} eseguiti · ${fmtNum(n(/pending|intent|partial|unknown/), 0)} in attesa · ${fmtNum(n(/reject/), 0)} rifiutati`;
    const word = { filled: 'eseguito', rejected: 'rifiutato', pending: 'in attesa', partial: 'parziale', cancelled: 'annullato', canceled: 'annullato', intent: 'inviato' };
    ordList.set(orders.map((o, i) => {
      const val = Math.abs((num(o.qty) || 0) * (num(o.price) || 0));
      const s = st(o);
      const buy = /buy|long/i.test(str(o.side));
      return { key: `${i}|${str(o.t)}|${str(o.symbol)}`, sym: str(o.symbol).toUpperCase(), cells: [{ v: o.ts == null ? 'n.d.' : now - o.ts > DAY ? fmtDayMonth(o.ts) : HHMM.format(new Date(o.ts)), cls: 'dim num' }, h('b', { text: str(o.symbol) }), buy ? 'compra' : 'vende',
        { v: val ? fmtMoney(val, ccy, { digits: 0 }) : 'n.d.', title: `${fmtNum(num(o.qty), 4)} a ${px(num(o.price))} · ${str(o.strategy)} · ${str(o.venue)}` },
        { v: h('span', { class: `tchip tchip--${/reject/.test(s) ? 'warn' : /fill/.test(s) ? 'ok' : 'run'}`, text: word[s] || s || 'n.d.' }), title: str(o.reason) || null }] };
    }), emptyState('Nessun ordine oggi'));
  }

  function paintAlerts() {
    const { snap, now } = ctxNow;
    const rank = { critical: 0, warn: 1, warning: 1, info: 2 };
    const list = arr(snap.alerts).map((a) => ({ ...a, ts: parseTs(a.t), lv: str(a.level).toLowerCase() })).sort((a, b) => (rank[a.lv] ?? 3) - (rank[b.lv] ?? 3) || (b.ts || 0) - (a.ts || 0));
    const serious = list.filter((a) => a.lv !== 'info').length;
    pAl.meta.textContent = `${fmtNum(serious, 0)} da guardare · ${fmtNum(list.length, 0)} nel registro`;
    alList.set(list.map((a, i) => ({ key: `${i}|${str(a.t)}`, sym: '', cls: `trow--${a.lv === 'critical' ? 'crit' : a.lv === 'info' ? 'info' : 'warn'}`,
      cells: [{ v: icon(a.lv === 'critical' ? 'crit' : a.lv === 'info' ? 'info' : 'warn', 'icon--sm'), title: alertLevel(a.level).label }, { v: str(a.msg) || '—', cls: 'tl__msg' }, { v: a.ts == null ? 'n.d.' : fmtAgo(Math.max(0, (now - a.ts) / 1000)).replace(' fa', ''), cls: 'dim' }] })),
    emptyState('Nessun avviso', 'Il registro del motore è vuoto.'));
  }

  function paintAll() {
    paintStrip();
    paintBrake();
    paintPositions();
    paintBook();
    paintStrategies();
    paintAttr();
    paintOrders();
    paintAlerts();
    paintEquity();
    if (!sel && symbols) {
      const want = str(ctxNow.params.s).toUpperCase();
      const first = [want, ...openTrades().map((t) => str(t.symbol)), ...arr(ctxNow.snap.positions).map((p) => str(p.symbol).toUpperCase())].find((s) => s && symbols.has(s)) || [...symbols.keys()][0] || '';
      if (first) pick(first);
    }
  }

  // ---- tastiera: il fuoco viaggia da un riquadro all'altro ----------------------------------------------------------------------
  const visible = () => panels.filter((p) => p.el.offsetParent !== null);
  function setActive(p) {
    if (active === p) return;
    if (active) active.el.classList.remove('is-active');
    active = p;
    if (p) p.el.classList.add('is-active');
    hintActive.textContent = p ? `Riquadro attivo: ${p.title}` : '';
  }
  function focusPanel(p) { if (!p) return; p.el.focus({ preventScroll: false }); setActive(p); }
  /** Il riquadro più vicino nella direzione data, giudicato sulla geometria: funziona anche quando la griglia va a capo. */
  function neighbour(from, dx, dy) {
    const a = from.el.getBoundingClientRect();
    let best = null;
    let bestD = Infinity;
    for (const p of visible()) {
      if (p === from) continue;
      const b = p.el.getBoundingClientRect();
      // solo i riquadri che stanno davvero da quella parte (oltre il bordo), preferendo quelli che si affacciano
      const gap = dx > 0 ? b.left - a.right : dx < 0 ? a.left - b.right : dy > 0 ? b.top - a.bottom : a.top - b.bottom;
      if (gap < -4) continue;
      const miss = dx ? Math.max(0, Math.max(a.top, b.top) - Math.min(a.bottom, b.bottom)) : Math.max(0, Math.max(a.left, b.left) - Math.min(a.right, b.right));
      const drift = dx ? Math.abs(b.top - a.top) : Math.abs(b.left - a.left);
      const d = gap + miss * 6 + drift * 0.25;
      if (d < bestD) { bestD = d; best = p; }
    }
    return best;
  }
  function onFocusIn(e) {
    const p = panels.find((q) => q.el.contains(e.target));
    if (p) setActive(p);
  }
  function openRow(p, inMarkets = false) {
    const l = lists[p.id];
    const it = l ? l.selected() || l.move(0) : null;
    if (p.id === 'pos' || p.id === 'book' || p.id === 'orders') {
      if (!it || !it.sym) return;
      if (inMarkets) { api.go('mercati', '', { s: it.sym }); return; }
      pick(it.sym);
      if (p.id === 'book') frame(it.data);
      focusPanel(pChart);
    } else if (p.id === 'strat') api.go('portafoglio', 'strategie');
    else if (p.id === 'alerts') api.openAlerts();
    else if (p.id === 'attr') api.go('portafoglio');
    else if (p.id === 'brake') api.go('rischio');
    else if (p.id === 'equity') { const svg = eqHost.querySelector('svg'); if (svg) svg.focus(); }
    else if (p.id === 'chart') { if (inMarkets && sel) api.go('mercati', '', { s: sel }); else { const cv = chartHost.querySelector('canvas'); if (cv) cv.focus(); } }
    else if (p.id === 'strip') api.go('portafoglio');
  }
  function onKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey || document.querySelector('dialog[open]')) return;
    const t = e.target;
    if (t instanceof HTMLElement && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    const onPanel = t instanceof HTMLElement && t.classList.contains('tp');
    const inChart = t instanceof Element && (t.classList.contains('cx__canvas') || (t.tagName.toLowerCase() === 'svg' && t.classList.contains('chart')));
    if (e.key === 'Escape' && active && t instanceof Element && active.el.contains(t) && !onPanel && !t.closest('details[open]')) { focusPanel(active); return; }
    if (inChart) return;                                              // dentro un grafico frecce, + − 0 sono suoi
    if (/^[0-9]$/.test(e.key) && !e.shiftKey) {
      const p = panels.find((q) => q.el.dataset.key === e.key);
      if (p && p.el.offsetParent !== null) { e.preventDefault(); focusPanel(p); }
      return;
    }
    if (e.key === 'Tab' && onPanel) {
      const vis = visible();
      const i = vis.indexOf(active);
      const next = vis[i + (e.shiftKey ? -1 : 1)];
      if (next) { e.preventDefault(); focusPanel(next); }             // dopo l'ultimo (o prima del primo) Tab esce dalla griglia: nessuna trappola
      return;
    }
    if (onPanel && /^Arrow/.test(e.key)) {
      const next = neighbour(active || panels[0], e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0, e.key === 'ArrowDown' ? 1 : e.key === 'ArrowUp' ? -1 : 0);
      if (next) { e.preventDefault(); focusPanel(next); }
      return;
    }
    if (e.key === 'j' || e.key === 'k') {
      const p = active && lists[active.id] ? active : panels.find((q) => q.id === 'pos');
      const it = lists[p.id].move(e.key === 'j' ? 1 : -1);
      e.preventDefault();
      if (p !== active) setActive(p);
      if (it && it.sym && (p.id === 'pos' || p.id === 'book' || p.id === 'orders')) { pick(it.sym); if (p.id === 'book') frame(it.data); }
    } else if (e.key === 'Enter' && onPanel) { e.preventDefault(); openRow(active); }
    else if (e.key === 'o' && active) { e.preventDefault(); openRow(active, true); }
  }
  document.addEventListener('keydown', onKey);
  root.addEventListener('focusin', onFocusIn);
  root.addEventListener('pointerdown', onFocusIn);
  const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(() => { if (ctxNow) paintEquity(); }) : null;
  if (ro) ro.observe(eqHost);

  getSymbols().then((res) => { symbols = new Map(arr(res && res.symbols).map((s) => [str(s.symbol), str(s.kind)])); if (ctxNow) paintAll(); });
  getTradebook().then((res) => { tb = res || null; if (ctxNow) { paintAll(); if (sel) paintChart(); } });

  return {
    update(ctx) {
      ctxNow = ctx;
      for (const w of watchedSymbols(ctx.snap, tb)) if (symbols && symbols.has(w.symbol)) loadBars(w.symbol);
      paintAll();
      const want = str(ctx.params.s).toUpperCase();
      if (want && want !== sel && symbols && symbols.has(want)) pick(want);
    },
    summary(ctx) {
      const snap = ctx.snap;
      if (!ctx.fresh) return 'Non so dirti com\'è adesso: i dati sono fermi. I riquadri mostrano l\'ultima fotografia ricevuta.';
      const day = num(obj(snap.nav).pnl_day);
      const rs = riskState(snap.risk);
      const bk = ladderData(ctx, tb).b;
      const open = openTrades();
      return `Il conto vale ${fmtMoney(totalNav(snap, tb).total, ctx.ccy, { digits: 0 })}, oggi ${day == null ? 'ha un risultato non disponibile' : day >= 0 ? `guadagna ${fmtMoney(day, ctx.ccy, { digits: 0 })}` : `perde ${fmtMoney(Math.abs(day), ctx.ccy, { digits: 0 })}`}. `
        + `Stato ${rs.label}${bk.next && bk.distNext != null ? `, ${fmtNum(bk.distNext * 100, 1)} punti dal prossimo freno` : ''}. ${open.length ? `${fmtNum(open.length, 0)} trade a leva ${open.length === 1 ? 'aperto' : 'aperti'}.` : 'Nessun trade a leva aperto.'}`;
    },
    destroy() {
      document.removeEventListener('keydown', onKey);
      if (ro) ro.disconnect();
      chart.destroy();
      delete document.body.dataset.term;
    },
  };
}
