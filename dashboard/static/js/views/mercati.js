// Spazio «Mercati»: che cosa fa lo strumento e dove sono i livelli del trade.
// Elenco (a sinistra) · grafico a candele con gli indicatori del fondo e il righello del trade · libro dei trade
// (Aperti, Chiusi, Decisioni). La selezione è collegata: scegliere una riga in un riquadro muove gli altri.
// Tasti: j / k strumento successivo / precedente · 1…5 intervalli · [ ] trade precedente / successivo.
// Conviction e GQ arrivano dal server (funzioni del fondo); il prezzo è sempre l'ultima barra chiusa, e lo si scrive.

import { candleChart, OVERLAYS, PANES } from '../candles.js';
import { segmented } from '../components.js';
import { h, icon } from '../dom.js';
import { arr, fmtDate, fmtDayMonth, fmtMoney, fmtNum, fmtPct, fmtPctSigned, fmtSigned, num, obj, parseTs, str } from '../format.js';
import { getOhlc, getSymbols, getTradebook } from '../market.js';
import { emptyState, panel, provOf, provTag, tradeR } from '../panels.js';

const DAY = 86400000;
const RANGES = [{ value: 1, label: '1M' }, { value: 3, label: '3M' }, { value: 6, label: '6M' }, { value: 12, label: '1A' }, { value: 0, label: 'Tutto' }];
const KIND = { crypto: 'crypto', etf: 'ETF', indice: 'indice' };
const px = (v) => (v == null ? 'n.d.' : fmtNum(v, Math.abs(v) >= 1000 ? 0 : Math.abs(v) >= 10 ? 2 : 4));
const tier = (v, th) => (v == null || !th ? '' : v >= th[1] ? 'eccezionale' : v >= th[0] ? 'alta' : 'media');

export function mount(root, api) {
  let ctxNow = null;
  let symbols;                 // undefined in arrivo · null assenti
  let example = false;
  let tb;
  let sel = null;
  let bars = null;             // barre dello strumento scelto
  let months = 6;
  let logScale = false;
  let bookTab = 'aperti';
  let tradeIdx = -1;
  const overlays = new Set(['sma50', 'sma200', 'vwap']);
  const cache = new Map();     // simbolo → riga dell'elenco { last, chg, conv, gq, th, t }

  // ---- elenco ----
  const pList = panel({ title: 'Elenco', span: 3, id: 'elenco', what: 'Gli strumenti di cui il fondo ha i prezzi. Per ognuno: ultima chiusura, variazione del giorno e, per le crypto e gli indici seguiti, il livello di conviction calcolato dal motore. Scegli una riga per vederne il grafico.' });
  const listBox = h('div', { class: 'wl', role: 'listbox', 'aria-label': 'Strumenti', tabindex: '0' });
  pList.body.append(listBox);

  // ---- grafico ----
  const rangeSeg = segmented({ label: 'Intervallo', options: RANGES, value: months, onChange: (v) => { months = v; chart.setRange(v || null); } });
  const logBtn = h('button', { class: 'btn btn--sm btn--ghost not-semplice', type: 'button', 'aria-pressed': 'false' }, 'Log');
  const ovBox = h('div', { class: 'ovs not-semplice', role: 'group', 'aria-label': 'Sovrapposizioni' });
  const pChart = panel({ title: 'Dov\'è il prezzo rispetto ai livelli del trade?', eyebrow: 'Grafico', span: 9, id: 'grafico', tools: [rangeSeg.el, logBtn],
    ask: 'Ogni candela è un giorno: vuota se ha chiuso in rialzo, piena se in ribasso. Le righe piene sono i livelli del trade aperto (entrata, stop, liquidazione); la fascia chiara tra entrata e stop vale 1 R, il rischio preso.',
    what: 'Sotto il prezzo: il volume, poi la conviction del motore (a gradini, con le soglie in cui il libro dei trade può aprire) e l\'indicatore Gervasoni, che per ora è solo osservato («in ombra»). Le medie a 50 e 200 giorni e il VWAP del mese sono le stesse grandezze che usano le strategie.' });
  const chartHost = h('div', { class: 'mk-chart' });
  const chartNote = h('p', { class: 'panel__ask' });
  pChart.body.append(ovBox, chartHost, chartNote);
  const chart = candleChart(chartHost, { label: 'Grafico a candele', panes: ['conv'], overlays: [...overlays], table: true });
  logBtn.addEventListener('click', () => { logScale = !logScale; logBtn.setAttribute('aria-pressed', String(logScale)); chart.setLog(logScale); });
  for (const ov of OVERLAYS) {
    const b = h('button', { class: 'btn btn--sm btn--ghost', type: 'button', 'aria-pressed': String(overlays.has(ov.id)), text: ov.label });
    b.addEventListener('click', () => { if (overlays.has(ov.id)) overlays.delete(ov.id); else overlays.add(ov.id); b.setAttribute('aria-pressed', String(overlays.has(ov.id))); chart.setOverlays([...overlays]); });
    ovBox.append(b);
  }

  // ---- libro dei trade ----
  const bookSeg = segmented({ label: 'Libro dei trade', options: [{ value: 'aperti', label: 'Aperti' }, { value: 'chiusi', label: 'Chiusi' }, { value: 'decisioni', label: 'Decisioni' }], value: bookTab, onChange: (v) => { bookTab = v; paintBook(); } });
  const pBook = panel({ title: 'Libro dei trade', span: 12, id: 'libro', tools: bookSeg.el,
    what: 'Il libro a margine isolato: scommesse a leva su BTC, ETH e SOL nei giorni ad alta conviction. Ogni trade rischia una piccola quota del fondo allo stop e, al massimo, il margine che ha bloccato. «Decisioni» mostra che cosa ha deciso il ciclo e che cosa dicono oggi conviction e indicatore GQ.' });
  const bookBox = h('div');
  pBook.body.append(bookBox);

  root.append(h('div', { class: 'ws' }, pList.el, pChart.el, pBook.el));

  // ---- dati ----
  const openTrades = () => Object.values(obj(obj(tb).open)).filter((t) => t && typeof t === 'object');
  const closedTrades = () => arr(obj(tb).closed);
  function watch() {
    const all = arr(symbols).map((s) => ({ symbol: str(s.symbol), kind: str(s.kind) }));
    const first = new Set([...openTrades().map((t) => str(t.symbol)), ...arr(obj(ctxNow && ctxNow.snap.ai).conviction).map((c) => str(c.asset)), 'BTC', 'ETH', 'SOL', 'SPY', 'QQQ']);
    return [...all.filter((s) => first.has(s.symbol)), ...all.filter((s) => !first.has(s.symbol))].slice(0, 16);
  }
  function loadRow(sym) {
    if (cache.has(sym)) return;
    cache.set(sym, null);
    getOhlc(sym, 1500).then((o) => {
      if (o && o.c.length > 1) {
        const n = o.c.length;
        cache.set(sym, { last: o.c[n - 1], chg: o.c[n - 2] ? o.c[n - 1] / o.c[n - 2] - 1 : null, conv: o.conviction ? o.conviction[n - 1] : null, gq: o.gq ? o.gq[n - 1] : null, th: o.thresholds, t: o.t[n - 1], bars: o });
      } else cache.set(sym, { missing: true });
      if (ctxNow) { paintList(); if (sym === sel) paintChart(); }
    });
  }

  function select(sym, { focus = false } = {}) {
    if (!sym || sym === sel) return;
    sel = sym;
    tradeIdx = -1;
    api.setParams({ s: sym });
    paintList();
    paintChart(true);
    paintBook();
    if (focus) { const row = listBox.querySelector('[aria-selected="true"]'); if (row) row.scrollIntoView({ block: 'nearest' }); }
  }

  function paintList() {
    if (symbols === undefined) { listBox.replaceChildren(emptyState('Strumenti in lettura…')); return; }
    const rows = watch();
    if (!rows.length) { listBox.replaceChildren(emptyState('Nessuno strumento', 'La cache dei prezzi è vuota: il motore non ha ancora scaricato le barre giornaliere.')); return; }
    pList.setProv(example ? provTag('demo') : null);
    const lv = ctxNow.lv;
    const open = new Set(openTrades().map((t) => str(t.symbol)));
    listBox.replaceChildren(...rows.map((r) => {
      loadRow(r.symbol);
      const c = cache.get(r.symbol);
      const t = c && !c.missing ? tier(c.conv, obj(c.th).conviction) : '';
      const row = h('div', { class: 'wl__row', role: 'option', 'aria-selected': String(r.symbol === sel), dataset: { sym: r.symbol } },
        h('div', { class: 'wl__sym' }, h('b', { text: r.symbol }), h('small', { text: KIND[r.kind] || r.kind })),
        h('div', { class: 'wl__px num' }, !c ? '…' : c.missing ? 'n.d.' : px(c.last), c && c.chg != null ? h('small', { class: c.chg > 0 ? 'pos' : c.chg < 0 ? 'neg' : '' }, c.chg === 0 ? null : icon(c.chg > 0 ? 'up' : 'down', 'icon--solid'), fmtPctSigned(c.chg, 2)) : null),
        h('div', { class: 'wl__sig' }, c && c.conv != null ? h('span', { class: `chip chip--xs ${t === 'media' ? '' : 'chip--accent'}`, title: 'Conviction del motore' }, lv === 'semplice' ? `conviction ${t}` : `conv ${fmtNum(c.conv, 2)}`) : c && !c.missing ? h('small', { text: 'conviction non calcolata' }) : null,
          open.has(r.symbol) ? h('span', { class: 'tag tag--paper', text: 'trade aperto' }) : lv !== 'semplice' && c && c.gq != null ? h('small', { class: 'num', text: `GQ ${fmtSigned(c.gq, 2)}` }) : null));
      row.addEventListener('click', () => select(r.symbol));
      return row;
    }));
    pList.setFoot(`${fmtNum(rows.length, 0)} di ${fmtNum(arr(symbols).length, 0)} strumenti · prezzi: ultima barra giornaliera chiusa`);
  }

  /** Segni del fondo sul grafico: livelli del trade aperto e trade chiusi sullo strumento scelto. */
  function markersFor(o) {
    const out = [];
    const idxOf = (day) => { const t = parseTs(str(day)); if (t == null) return -1; let k = -1; for (let i = 0; i < o.t.length; i++) if (o.t[i] <= t + DAY / 2) k = i; return k; };
    for (const t of openTrades().filter((x) => str(x.symbol) === sel)) {
      const i = Math.max(0, idxOf(t.opened));
      const entry = num(t.entry);
      const stop = num(t.stop);
      const init = entry != null && num(t.initial_stop_distance) != null ? entry * (1 - (num(t.side) === -1 ? -1 : 1) * t.initial_stop_distance) : null;
      if (entry != null && stop != null) out.push({ kind: 'zone', i, from: entry, to: init ?? stop, label: '1 R' });
      if (num(t.liquidation) != null) out.push({ kind: 'level', i, price: t.liquidation, label: 'Liq.', color: 'crit' });
      if (init != null && stop != null && Math.abs(init - stop) / entry > 0.002) out.push({ kind: 'level', i, price: init, label: 'Stop in.', color: 'warn', past: true });
      if (stop != null) out.push({ kind: 'level', i, price: stop, label: 'Stop', color: 'warn' });
      if (entry != null) { out.push({ kind: 'level', i, price: entry, label: 'Entr.', color: 'text' }); out.push({ kind: 'entry', i, price: entry }); }
    }
    for (const t of closedTrades().filter((x) => str(x.symbol) === sel)) {
      const a = idxOf(t.opened);
      const b = idxOf(t.closed);
      if (a >= 0 && num(t.entry) != null) out.push({ kind: 'entry', i: a, price: t.entry });
      if (b >= 0 && num(t.exit) != null) out.push({ kind: 'exit', i: b, price: t.exit, color: num(t.R) >= 0 ? 'up' : 'down', label: num(t.R) == null ? '' : `${fmtSigned(t.R, 1)} R` });
    }
    return out;
  }

  function paintChart(reset = false) {
    const c = sel ? cache.get(sel) : null;
    const lv = ctxNow.lv;
    chart.setPanes(lv === 'semplice' ? ['conv'] : PANES.map((p) => p.id));
    if (!sel) { chartNote.textContent = 'Scegli uno strumento dall\'elenco.'; return; }
    if (!c) { chartNote.textContent = `${sel}: barre in lettura…`; return; }
    if (c.missing) { chart.setData(null); chartNote.textContent = `${sel}: nessuna barra nella cache dei prezzi. Il grafico resta vuoto finché il motore non le scarica.`; return; }
    bars = c.bars;
    chart.setData({ ...bars, markers: tb ? markersFor(bars) : [] }, { keepView: !reset, months: months || 240 });
    if (reset && !months) chart.setRange(null);
    const noSig = !bars.conviction && !bars.gq;
    pChart.setProv(provTag(bars.example ? 'demo' : 'real', bars.example ? 'Esempio' : 'Prezzi reali'), openTrades().some((t) => str(t.symbol) === sel) ? provTag(tb && tb.example ? 'demo' : 'paper', 'Trade') : null);
    chartNote.replaceChildren(`${sel} · ultima barra chiusa: ${fmtDate(c.t, true)}.`, noSig ? ' Conviction e indicatore GQ non sono calcolati per questo strumento.' : bars.gq ? ' L\'indicatore GQ è in ombra: si osserva, non decide.' : '');
    chartNote.classList.remove('only-semplice');
  }

  function table(caption, head, rows, onRow) {
    return h('div', { class: 'table-wrap' }, h('table', { class: 'table table--dense' }, h('caption', { class: 'sr-only', text: caption }),
      h('thead', null, h('tr', null, head.map((c) => h('th', { scope: 'col', class: `${c.num ? 'is-num' : ''} ${c.cls || ''}`.trim(), text: c.t })))),
      h('tbody', null, rows.map((r, i) => {
        const tr = h('tr', { class: r.sym === sel ? 'is-marked' : '', tabindex: '0' }, r.cells.map((c, k) => h('td', { class: `${head[k].num ? 'is-num' : ''} ${head[k].cls || ''} ${c && c.cls ? c.cls : ''}`.trim() }, c && typeof c === 'object' && 'v' in c ? c.v : c)));
        const pick = () => onRow(r, i);
        tr.addEventListener('click', pick);
        tr.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); pick(); } });
        return tr;
      }))));
  }

  function focusTrade(t) {
    if (!bars || !t) return;
    const a = parseTs(str(t.opened));
    const b = parseTs(str(t.closed)) ?? bars.t[bars.t.length - 1];
    if (a != null) chart.setWindow(a - 25 * DAY, b + 12 * DAY);
  }

  function paintBook() {
    const { snap, ccy, lv, now } = ctxNow;
    if (tb === undefined) { bookBox.replaceChildren(emptyState('Libro dei trade in lettura…')); return; }
    if (!tb) { bookBox.replaceChildren(emptyState('Libro dei trade non disponibile', 'Il motore non ha ancora scritto lo stato del libro a margine isolato.')); pBook.setProv(); pBook.setFoot(); return; }
    pBook.setProv(provTag(tb.example ? 'demo' : provOf(snap.meta) === 'real' ? 'real' : 'paper'));
    const eq = num(obj(snap.nav).equity);
    const open = openTrades();
    const full = lv === 'terminale';
    if (bookTab === 'aperti') {
      if (!open.length) { bookBox.replaceChildren(emptyState('Nessun trade aperto', 'Il libro apre solo nei giorni ad alta conviction: oggi non ce ne sono.')); }
      else {
        const head = [{ t: 'Strumento' }, { t: 'Lato' }, { t: 'Leva', num: 1 }, { t: 'Entrata', num: 1 }, { t: 'Stop', num: 1 }, { t: 'Liquidazione', num: 1, cls: 'not-semplice' }, { t: 'Ultima chiusura', num: 1 }, { t: 'R', num: 1 },
          { t: 'Dallo stop', num: 1, cls: 'not-semplice' }, { t: 'Margine', num: 1 }, { t: 'A rischio', num: 1, cls: 'not-semplice' }, { t: 'Giorni', num: 1 }, ...(full ? [{ t: 'MAE / MFE', num: 1 }, { t: 'Livello' }] : [])];
        bookBox.replaceChildren(table('Trade a leva aperti', head, open.map((t) => {
          const sym = str(t.symbol);
          loadRow(sym);
          const c = cache.get(sym);
          const last = c && !c.missing ? c.last : null;
          const r = tradeR(t, last);
          const opened = parseTs(str(t.opened));
          return { sym, trade: t, cells: [h('b', { text: sym }), num(t.side) === -1 ? 'ribasso' : 'rialzo', `${fmtNum(t.leverage, 1)}x`, px(num(t.entry)), px(num(t.stop)), px(num(t.liquidation)), last == null ? '…' : px(last),
            { v: r == null ? 'n.d.' : `${fmtSigned(r, 2)} R`, cls: r > 0 ? 'pos' : r < 0 ? 'neg' : '' }, last != null && num(t.stop) ? fmtPctSigned(t.stop / last - 1, 1) : 'n.d.', fmtMoney(num(t.margin), ccy), fmtMoney(num(t.risk), ccy),
            opened == null ? 'n.d.' : fmtNum(Math.max(1, Math.round((now - opened) / DAY)), 0), ...(full ? [`${num(t.mae) == null ? 'n.d.' : fmtSigned(t.mae, 2)} / ${num(t.mfe) == null ? 'n.d.' : fmtSigned(t.mfe, 2)}`, str(t.tier) || 'n.d.'] : [])] };
        }), (r) => { select(r.sym); focusTrade(r.trade); }));
      }
      const margin = open.reduce((a, t) => a + (num(t.margin) || 0), 0);
      const risk = open.reduce((a, t) => a + (num(t.risk) || 0), 0);
      pBook.setFoot(`${fmtNum(open.length, 0)} aperti · margine ${fmtMoney(margin, ccy)} · a rischio agli stop ${fmtMoney(risk, ccy)}${eq ? ` (${fmtPct(risk / eq, 2)} del fondo)` : ''} · patrimonio del libro ${num(tb.equity) == null ? 'n.d.' : fmtMoney(tb.equity, ccy)} · funding: non misurato · aggiornato ${str(tb.asof) || 'n.d.'}`);
    } else if (bookTab === 'chiusi') {
      const closed = [...closedTrades()].reverse();
      if (!closed.length) { bookBox.replaceChildren(emptyState('Nessun trade chiuso in paper', 'Qui compariranno entrata, uscita, R e motivo di ogni trade chiuso.')); pBook.setFoot(); return; }
      const head = [{ t: 'Strumento' }, { t: 'Aperto' }, { t: 'Chiuso' }, { t: 'Entrata', num: 1 }, { t: 'Uscita', num: 1 }, { t: 'Leva', num: 1, cls: 'not-semplice' }, { t: 'R', num: 1 }, { t: 'P&L', num: 1 }, { t: 'Motivo' }, ...(full ? [{ t: 'Livello' }] : [])];
      const day = (v) => { const t = parseTs(str(v)); return t == null ? 'n.d.' : fmtDayMonth(t, true); };
      bookBox.replaceChildren(table('Trade chiusi', head, closed.map((t) => ({ sym: str(t.symbol), trade: t, cells: [h('b', { text: str(t.symbol) }), day(t.opened), day(t.closed), px(num(t.entry)), px(num(t.exit)), `${fmtNum(t.leverage, 1)}x`,
        { v: num(t.R) == null ? 'n.d.' : `${fmtSigned(t.R, 2)} R`, cls: t.R > 0 ? 'pos' : t.R < 0 ? 'neg' : '' }, { v: fmtMoney(num(t.pnl), ccy, { signed: true }), cls: t.pnl > 0 ? 'pos' : t.pnl < 0 ? 'neg' : '' }, str(t.why) || 'n.d.', ...(full ? [str(t.tier) || 'n.d.'] : [])] })),
      (r) => { select(r.sym); focusTrade(r.trade); }));
      const rs = closed.map((t) => num(t.R)).filter((v) => v != null);
      pBook.setFoot(`${fmtNum(closed.length, 0)} chiusi · vinti ${fmtNum(rs.filter((v) => v > 0).length, 0)} · R medio ${rs.length ? fmtSigned(rs.reduce((a, b) => a + b, 0) / rs.length, 2) : 'n.d.'}${rs.length < 30 ? ` · n = ${fmtNum(rs.length, 0)}: troppo pochi per una statistica` : ''}`);
    } else {
      const log = arr(tb.log).slice(-6).reverse();
      const shadow = arr(tb.shadow);
      const lastShadow = shadow.length ? shadow[shadow.length - 1] : null;
      const coins = Object.entries(obj(lastShadow && lastShadow.coins));
      bookBox.replaceChildren(h('div', { class: 'events' }, log.length ? log.map((e) => { const t = parseTs(str(e.day)); return h('div', { class: 'event' }, h('span', { class: 'event__t', text: t == null ? str(e.day) : fmtDayMonth(t, true) }), h('span', { class: 'event__k', text: 'Ciclo' }), h('span', { text: str(e.msg || e.event) || 'n.d.' })); }) : emptyState('Nessuna decisione registrata')),
        coins.length ? table(`Segnali del ${str(lastShadow.day)}`, [{ t: 'Strumento' }, { t: 'Conviction', num: 1 }, { t: 'Livello' }, { t: 'GQ (in ombra)', num: 1 }, { t: 'Livello GQ' }],
          coins.map(([sym, c]) => ({ sym, cells: [h('b', { text: sym }), num(c.conviction) == null ? 'n.d.' : fmtNum(c.conviction, 2), str(c.conviction_tier) || 'n.d.', num(c.gq) == null ? 'n.d.' : fmtSigned(c.gq, 2), str(c.gq_tier) || 'n.d.'] })), (r) => select(r.sym)) : null);
      pBook.setFoot(lastShadow ? `Segnali del ${str(lastShadow.day)} · l'indicatore GQ è in ombra: si registra, non decide.` : 'Nessun registro in ombra.');
    }
  }

  // ---- tastiera dello spazio ----
  function onKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey || document.querySelector('dialog[open]')) return;
    const t = e.target;
    if (t instanceof HTMLElement && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
    const rows = watch().map((r) => r.symbol);
    const onChart = t instanceof HTMLElement && t.classList.contains('cx__canvas');
    if ((e.key === 'j' || e.key === 'k' || ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && t === listBox)) && rows.length) {
      e.preventDefault();
      const i = rows.indexOf(sel);
      select(rows[Math.max(0, Math.min(rows.length - 1, i + (e.key === 'j' || e.key === 'ArrowDown' ? 1 : -1)))], { focus: true });
    } else if (/^[1-5]$/.test(e.key) && !onChart) {
      e.preventDefault();
      const r = RANGES[Number(e.key) - 1];
      months = r.value;
      rangeSeg.set(r.value);
      chart.setRange(r.value || null);
    } else if (e.key === '[' || e.key === ']') {
      const mine = [...closedTrades(), ...openTrades()].filter((x) => str(x.symbol) === sel);
      if (!mine.length) return;
      e.preventDefault();
      tradeIdx = tradeIdx < 0 ? mine.length - 1 : Math.max(0, Math.min(mine.length - 1, tradeIdx + (e.key === ']' ? 1 : -1)));
      focusTrade(mine[tradeIdx]);
    }
  }
  document.addEventListener('keydown', onKey);

  getSymbols().then((res) => { symbols = res && Array.isArray(res.symbols) ? res.symbols : null; example = !!(res && res.example); if (ctxNow) init(); });
  getTradebook().then((res) => { tb = res || null; if (ctxNow) { paintList(); paintChart(); paintBook(); } });
  function init() {
    const want = str(ctxNow.params.s).toUpperCase();
    const rows = watch().map((r) => r.symbol);
    const all = arr(symbols).map((s) => str(s.symbol));
    paintList();
    if (!sel) select(all.includes(want) ? want : rows[0]);
    if (ctxNow.params.v === 'libro') pBook.el.scrollIntoView({ block: 'start' });
  }

  return {
    update(ctx) {
      const lvChanged = !ctxNow || ctxNow.lv !== ctx.lv;
      const want = str(ctx.params.s).toUpperCase();
      ctxNow = ctx;
      if (symbols !== undefined) {
        if (!sel) init();
        else if (want && want !== sel && arr(symbols).some((s) => str(s.symbol) === want)) select(want);
        else { paintList(); if (lvChanged) paintChart(); }
      } else paintList();
      paintBook();
    },
    summary(ctx) {
      const open = Object.values(obj(obj(tb).open));
      const c = sel ? cache.get(sel) : null;
      return `${sel && c && !c.missing ? `${sel} ha chiuso a ${px(c.last)}${c.chg == null ? '' : ` (${fmtPctSigned(c.chg, 2)})`}. ` : ''}${tb === undefined ? '' : open.length ? `Nel libro dei trade ${open.length === 1 ? `c'è una scommessa aperta su ${str(open[0].symbol)}` : `ci sono ${fmtNum(open.length, 0)} scommesse aperte`}.` : 'Nessun trade a leva aperto.'}${ctx.fresh ? '' : ' Attenzione: i dati del conto sono fermi.'}`;
    },
    destroy() { document.removeEventListener('keydown', onKey); chart.destroy(); },
  };
}
