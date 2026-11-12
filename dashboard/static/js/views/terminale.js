// Terminale: una sola schermata densa. Striscia di stato, nastro dei prezzi, grafico a candele con indicatori,
// patrimonio, rischio, posizioni, libro dei trade, strategie, ordini, avvisi. Tutto in sola lettura.

import { h, icon, fill, loadPref, savePref } from '../dom.js';
import { chip, dataTable, empty, segmented, signedMoney, signedPct, toggle } from '../components.js';
import { bullet, sparkline, timeChart } from '../charts.js';
import { OVERLAYS, candleChart } from '../candles.js';
import { getCompare, getOhlc, getSymbols, getTradebook } from '../market.js';
import { DASH, arr, fmtAgo, fmtAxisAmount, fmtDate, fmtDayTime, fmtMoney, fmtNum, fmtPct, fmtPctSigned, fmtPrice, fmtQty, fmtSigned, fmtUnit, num, obj, parseTs, stepDigits, str } from '../format.js';
import { alertLevel, curveOf, exposureDivisor, limitStatus, orderSide, orderStatus, rebaseBench, riskState, strategyStatus, utilization } from '../model.js';

const WATCH = ['BTC', 'ETH', 'SOL', 'SPY', 'QQQ'];
const RANGES = [{ value: '1', label: '1M' }, { value: '3', label: '3M' }, { value: '6', label: '6M' }, { value: '12', label: '1A' }, { value: '0', label: 'Tutto' }];
const SCALE = { NORMAL: 1, REDUCED: 0.5, HALTED: 0.25, KILLED: 0 };

/** Aggiorna un testo solo se cambia e, nel livello Terminale, lo fa lampeggiare un istante. */
function setFlash(node, text, cls = null) {
  if (cls != null && node.dataset.tone !== cls) { node.dataset.tone = cls; }
  if (node.textContent === text) return;
  const first = node.textContent === '';
  node.textContent = text;
  if (first) return;
  node.classList.remove('flash');
  void node.offsetWidth;                       // riavvia l'animazione
  node.classList.add('flash');
}

function panel(title, { cls = '', tools = null, sim = '' } = {}) {
  const body = h('div', { class: 'tp__body' });
  const note = h('span', { class: 'tp__note' });
  const el = h('section', { class: `tp ${cls}`.trim(), 'aria-label': title },
    h('header', { class: 'tp__head' }, h('h2', { class: 'tp__title', text: title }), sim ? h('span', { class: 'tag tag--sim simtag', text: sim }) : null, note, tools ? h('div', { class: 'tp__tools' }, tools) : null), body);
  return { el, body, note };
}

export function mount(root, api) {
  let ctx = null;
  let book = null;                 // libro dei trade (null = assente, undefined = non ancora letto)
  let compare = null;
  let symbols = [];
  let bars = null;
  let alive = true;
  const ui = {
    symbol: loadPref('term.symbol', 'BTC'), range: loadPref('term.range', '6'), log: false, table: false, eqMode: 'fondo',
    overlays: new Set(loadPref('term.overlays', 'sma50,sma200').split(',').filter(Boolean)),
  };
  const last = new Map();          // ultimo prezzo per simbolo (dal nastro)

  // ---- striscia di stato ----
  const cells = {};
  const cell = (key, label) => {
    const v = h('span', { class: 'ts__v num' });
    cells[key] = v;
    return h('div', { class: 'ts__c' }, h('span', { class: 'ts__l', text: label }), v);
  };
  const strip = h('section', { class: 'ts', 'aria-label': 'Stato del fondo' },
    cell('nav', 'NAV'), cell('day', 'Oggi'), cell('mtd', 'Mese'), cell('ytd', 'Anno'), cell('dd', 'Drawdown'), cell('expo', 'Lordo / netto'), cell('lev', 'Leva / tetto'),
    cell('risk', 'Rischio'), cell('scale', 'Scala motore'), cell('hb', 'Battito'), cell('data', 'Dati'), cell('utc', 'UTC'), cell('rome', 'Roma'));

  // ---- nastro ----
  const tapeTrack = h('div', { class: 'tape__track' });
  const tape = h('section', { class: 'tape', 'aria-label': 'Nastro dei prezzi degli strumenti seguiti', tabindex: '0' }, tapeTrack);

  // ---- grafico ----
  const symSel = h('select', { class: 'tsel', 'aria-label': 'Strumento del grafico' });
  symSel.addEventListener('change', () => loadSymbol(symSel.value));
  const rangeSeg = segmented({ label: 'Intervallo del grafico a candele', options: RANGES, value: ui.range, onChange: (v) => { ui.range = v; savePref('term.range', v); cx.setRange(Number(v) || null); } });
  const logBtn = toggle({ label: 'Scala logaritmica', text: 'Log', onChange: (on) => { ui.log = on; cx.setLog(on); } });
  const tableBtn = toggle({ label: 'Mostra le barre in tabella', iconName: 'table', onChange: (on) => { ui.table = on; paintChartMode(); } });
  const ovBar = h('div', { class: 'tov', role: 'group', 'aria-label': 'Sovrapposizioni del grafico' }, OVERLAYS.map((o) => {
    const b = h('button', { class: 'tov__btn', type: 'button', 'aria-pressed': String(ui.overlays.has(o.id)) }, h('span', { class: 'tov__key', style: { background: `var(${o.color})` } }), o.label);
    b.addEventListener('click', () => {
      if (ui.overlays.has(o.id)) ui.overlays.delete(o.id); else ui.overlays.add(o.id);
      b.setAttribute('aria-pressed', String(ui.overlays.has(o.id)));
      savePref('term.overlays', [...ui.overlays].join(','));
      cx.setOverlays(ui.overlays);
    });
    return b;
  }));
  const chartP = panel('Grafico', { cls: 'tp--chart', tools: [symSel, rangeSeg.el, logBtn.el, tableBtn.el] });
  const cxHost = h('div', { class: 'tchart' });
  const cxTable = h('div', { class: 'tchart__table' });
  const cxEmpty = h('div', { class: 'tchart__empty' });
  chartP.body.append(ovBar, cxHost, cxTable, cxEmpty);
  const cx = candleChart(cxHost, { label: 'Grafico a candele con volume e indicatori. Frecce per il mirino, più e meno per lo zoom, Maiusc e frecce per scorrere.' });
  cx.setOverlays(ui.overlays);

  // ---- patrimonio ----
  const eqSeg = segmented({ label: 'Che cosa confrontare', options: [{ value: 'fondo', label: 'Fondo' }, { value: 'confronto', label: 'Originale' }], value: 'fondo', onChange: (v) => { ui.eqMode = v; paintEquity(); } });
  const eqP = panel('Patrimonio', { cls: 'tp--eq', tools: eqSeg.el });
  const eqLegend = h('div', { class: 'legend tlegend' });
  const eqHost = h('div', { class: 'chart-host' });
  const eqEmpty = h('div');
  eqP.body.append(eqLegend, eqHost, eqEmpty);
  const eqChart = timeChart(eqHost, { label: 'Patrimonio contro benchmark con il drawdown sotto. Frecce per scorrere.' });

  const riskP = panel('Rischio', { cls: 'tp--risk' });
  const posP = panel('Posizioni', { cls: 'tp--pos' });
  const bookP = panel('Libro dei trade', { cls: 'tp--book' });
  const stratP = panel('Strategie', { cls: 'tp--strat' });
  const blotP = panel('Ordini', { cls: 'tp--blot' });
  const alertP = panel('Avvisi', { cls: 'tp--alert' });

  let maxW = 1;
  const weightOf = (r) => { const w = num(r.weight); if (w != null) return w; const v = num(r.value); const eq = num(obj(ctx.snap.nav).equity); return v != null && eq ? v / eq : null; };
  const posTable = dataTable({
    caption: 'Posizioni aperte', cls: 'table--dense', sort: { key: 'value', dir: -1 }, emptyTitle: 'Nessuna posizione aperta',
    columns: [
      { key: 'symbol', label: 'Strum.', sort: (r) => str(r.symbol), cell: (r) => { const b = h('button', { class: 'tlink code code--strong', type: 'button', text: str(r.symbol) || DASH, title: 'Apri nel grafico' }); b.addEventListener('click', () => loadSymbol(str(r.symbol).toUpperCase())); return b; } },
      { key: 'strategy', label: 'Strategia', hide: 'sm', sort: (r) => str(r.strategy), cell: (r) => (str(r.strategy) ? h('span', { class: 'code', text: str(r.strategy) }) : null) },
      { key: 'weight', label: 'Peso', num: true, cls: 'is-weight', sort: (r) => Math.abs(weightOf(r) ?? 0), cell: (r) => { const w = weightOf(r); return w == null ? null : h('div', { class: 'weight' }, bullet({ ratio: Math.abs(w) / maxW, kind: 'plain', label: `Peso di ${str(r.symbol)}` }), h('span', { class: 'weight__value', text: fmtPct(w, 1) })); } },
      { key: 'value', label: 'Valore', num: true, sort: (r) => Math.abs(num(r.value) ?? 0), cell: (r) => (num(r.value) == null ? null : fmtMoney(r.value, ctx.ccy, { digits: 0 })) },
      { key: 'pnl_day', label: 'Oggi', num: true, sort: (r) => num(r.pnl_day), cell: (r) => (num(r.pnl_day) == null ? null : signedMoney(r.pnl_day, ctx.ccy, { arrow: false })) },
      { key: 'pnl_open', label: 'Aperto', num: true, hide: 'sm', sort: (r) => num(r.pnl_open), cell: (r) => (num(r.pnl_open) == null ? null : signedMoney(r.pnl_open, ctx.ccy, { arrow: false })) },
      { key: 'age', label: 'Età', num: true, hide: 'md', blank: false, cell: (r) => { const t = parseTs(r.opened || r.since); return t == null ? null : fmtAgo((ctx.now - t) / 1000).replace(' fa', ''); } },
    ],
  });
  posP.body.append(posTable.el);

  const stratTable = dataTable({
    caption: 'Strategie', cls: 'table--dense', emptyTitle: 'Nessuna strategia',
    columns: [
      { key: 'id', label: 'Strategia', sort: (r) => str(r.id), cell: (r) => h('span', { class: 'code code--strong', text: str(r.id) || DASH, title: str(r.name) }) },
      { key: 'st', label: 'St.', cell: (r) => chip(strategyStatus(r.status), { cls: 'chip--icon' }) },
      { key: 'alloc', label: 'Alloc.', num: true, sort: (r) => num(r.allocation), cell: (r) => fmtPct(r.allocation, 0) },
      { key: 'expo', label: 'Espos.', num: true, sort: (r) => num(r.exposure), cell: (r) => fmtPct(r.exposure, 0) },
      { key: 'day', label: 'Oggi', num: true, sort: (r) => num(r.pnl_day_pct), cell: (r) => signedPct(r.pnl_day_pct, 2, { arrow: false }) },
      { key: 'mtd', label: 'Mese', num: true, sort: (r) => num(r.pnl_mtd_pct), cell: (r) => signedPct(r.pnl_mtd_pct, 1, { arrow: false }) },
      { key: 'sh', label: 'Sharpe r/b', num: true, cell: (r) => `${num(r.sharpe_live) == null ? DASH : fmtNum(r.sharpe_live, 2)} / ${num(r.sharpe_backtest) == null ? DASH : fmtNum(r.sharpe_backtest, 2)}` },
      { key: 'spark', label: '', cls: 'is-spark', hide: 'sm', cell: (r) => sparkline(r.spark, { width: 72, height: 20, label: `Andamento di ${str(r.id)}` }) },
    ],
  });
  stratP.body.append(stratTable.el);

  const blotTable = dataTable({
    caption: 'Ultimi ordini', cls: 'table--dense', sort: { key: 't', dir: -1 }, emptyTitle: 'Nessun ordine',
    rowClass: (r) => (['rejected', 'error'].includes(str(r.status).toLowerCase()) ? 'is-rejected' : null),
    columns: [
      { key: 't', label: 'Ora', sort: (r) => parseTs(r.t), cell: (r) => { const t = parseTs(r.t); return t == null ? null : h('span', { class: 'num', text: fmtDayTime(t) }); } },
      { key: 'symbol', label: 'Strum.', sort: (r) => str(r.symbol), cell: (r) => h('span', { class: 'code code--strong', text: str(r.symbol) || DASH }) },
      { key: 'side', label: 'Lato', cell: (r) => { const s = orderSide(r.side); return h('span', { class: s.dir > 0 ? 'pos' : s.dir < 0 ? 'neg' : '', text: s.dir > 0 ? '▲ ACQ' : s.dir < 0 ? '▼ VEN' : s.label }); } },
      { key: 'qty', label: 'Q.tà', num: true, hide: 'sm', cell: (r) => (num(r.qty) == null ? null : fmtQty(r.qty)) },
      { key: 'price', label: 'Prezzo', num: true, cell: (r) => (num(r.price) == null ? null : fmtPrice(r.price)) },
      { key: 'status', label: 'Stato', sort: (r) => str(r.status), cell: (r) => { const c = chip(orderStatus(r.status)); if (str(r.reason).trim()) c.title = str(r.reason); return c; } },
      { key: 'reason', label: 'Motivo', cls: 'is-clip', blank: true, hide: 'md', cell: (r) => (str(r.reason).trim() ? h('span', { title: str(r.reason), text: str(r.reason) }) : null) },
    ],
  });
  blotP.body.append(blotTable.el);

  root.append(h('div', { class: 'term' }, strip, tape, chartP.el, eqP.el, riskP.el, stratP.el, posP.el, bookP.el, blotP.el, alertP.el));

  // ---------------------------------------------------------------------------------------------------------------
  function paintStrip() {
    const { snap, ccy } = ctx;
    const nav = obj(snap.nav);
    const e = obj(snap.exposure);
    const div = exposureDivisor(snap);
    const st = riskState(snap.risk);
    const tone = (v) => (num(v) == null ? '' : num(v) > 0 ? 'pos' : num(v) < 0 ? 'neg' : '');
    setFlash(cells.nav, fmtMoney(nav.equity, ccy));
    setFlash(cells.day, num(nav.pnl_day) == null ? DASH : `${fmtMoney(nav.pnl_day, ccy, { signed: true, digits: 0 })} ${fmtPctSigned(nav.pnl_day_pct, 2)}`, tone(nav.pnl_day));
    setFlash(cells.mtd, fmtPctSigned(nav.pnl_mtd_pct, 2), tone(nav.pnl_mtd_pct));
    setFlash(cells.ytd, fmtPctSigned(nav.pnl_ytd_pct, 2), tone(nav.pnl_ytd_pct));
    setFlash(cells.dd, fmtPct(nav.drawdown_pct, 2));
    setFlash(cells.expo, `${num(e.gross) == null ? DASH : fmtPct(num(e.gross) / div, 0)} / ${num(e.net) == null ? DASH : fmtPct(num(e.net) / div, 0)}`);
    setFlash(cells.lev, `${num(e.leverage) == null ? DASH : `${fmtNum(e.leverage, 2)}x`} / ${num(e.max_leverage) == null ? DASH : `${fmtNum(e.max_leverage, 0)}x`}`);
    setFlash(cells.risk, st.label.toUpperCase(), st.kind === 'ok' ? '' : st.kind === 'crit' || st.kind === 'serious' ? 'neg' : 'warn');
    setFlash(cells.scale, st.code in SCALE ? `×${fmtNum(SCALE[st.code], 2)}` : DASH);
    const hb = num(obj(snap.system).heartbeat_age_s);
    setFlash(cells.hb, hb == null ? DASH : fmtAgo(hb).replace(' fa', ''));
    const feeds = arr(obj(snap.system).components).filter((c) => /dati|data|feed|gateway/i.test(str(c.name)) && parseTs(c.last_ok) != null);
    const age = (t) => fmtAgo(Math.max(0, (ctx.now - t) / 1000)).replace(' fa', '');
    const asOf = parseTs(obj(snap.meta).as_of);
    setFlash(cells.data, feeds.length ? feeds.slice(0, 3).map((c) => `${str(c.name).replace(/^dati\s+/i, '').slice(0, 8)} ${age(parseTs(c.last_ok))}`).join(' · ') : asOf == null ? DASH : `snapshot ${age(asOf)}`,
      feeds.some((c) => str(c.status).toLowerCase() !== 'ok') ? 'warn' : '');
  }

  function clock() {
    if (!alive) return;
    const now = new Date(ctx ? ctx.now + (Date.now() - ctx.at) : Date.now());
    const f = (tz) => new Intl.DateTimeFormat('it-IT', { hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: tz }).format(now);
    cells.utc.textContent = f('UTC');
    cells.rome.textContent = f('Europe/Rome');
  }
  const timer = setInterval(clock, 1000);

  async function paintTape() {
    const held = arr(ctx.snap.positions).map((p) => str(p.symbol).toUpperCase());
    const conv = arr(obj(ctx.snap.ai).conviction).map((c) => str(c.asset).toUpperCase());
    const have = new Set(symbols.map((s) => s.symbol));
    const list = [...new Set([...held, ...conv, ...WATCH])].filter((s) => have.has(s)).slice(0, 14);
    const key = list.join(',');
    if (tapeTrack.dataset.key === key) return;
    tapeTrack.dataset.key = key;
    if (!list.length) { fill(tapeTrack, h('span', { class: 'tape__empty', text: 'Nessun prezzo disponibile: il nastro si riempie quando la cache dei dati contiene gli strumenti seguiti.' })); return; }
    const data = await Promise.all(list.map((s) => getOhlc(s, 40)));
    if (!alive) return;
    const items = [];
    data.forEach((d, i) => {
      if (!d || !d.c || d.c.length < 2) return;
      const n = d.c.length;
      const chg = d.c[n - 2] ? d.c[n - 1] / d.c[n - 2] - 1 : null;
      last.set(list[i], d.c[n - 1]);
      const b = h('button', { class: 'tape__item', type: 'button', title: `Apri ${list[i]} nel grafico` },
        h('span', { class: 'tape__sym', text: list[i] }), held.includes(list[i]) ? h('span', { class: 'tape__held', title: 'in portafoglio', text: '●' }) : null,
        h('span', { class: 'num', text: fmtPrice(d.c[n - 1]) }),
        h('span', { class: `num ${chg > 0 ? 'pos' : chg < 0 ? 'neg' : ''}`, text: chg == null ? DASH : `${chg > 0 ? '▲' : chg < 0 ? '▼' : ''} ${fmtPctSigned(chg, 2)}` }),
        sparkline(d.c.slice(-30), { width: 54, height: 16, label: `Ultimi 30 giorni di ${list[i]}` }));
      b.addEventListener('click', () => loadSymbol(list[i]));
      items.push(b);
    });
    const example = data.some((d) => d && d.example);
    const group = (hidden) => h('div', { class: 'tape__group', 'aria-hidden': hidden ? 'true' : null }, example ? h('span', { class: 'tag tag--sim', text: 'ESEMPIO' }) : null, hidden ? items.map((x) => { const c = x.cloneNode(true); c.tabIndex = -1; return c; }) : items);
    fill(tapeTrack, group(false), group(true));
    tapeTrack.style.setProperty('--tape-s', `${Math.max(30, items.length * 7)}s`);
    paintBook();
  }

  function markersFor(symbol, d) {
    const idx = (iso) => { const t = parseTs(str(iso).slice(0, 10)); if (t == null) return -1; let k = d.t.findIndex((x) => x >= t); if (k < 0) k = d.t.length - 1; return k; };
    const out = [];
    const b = obj(book);
    const open = obj(obj(b.open)[symbol]);
    if (num(open.entry) != null) {
      const i = idx(open.opened);
      out.push({ i, price: num(open.entry), kind: 'entry' });
      out.push({ i, price: num(open.entry), kind: 'level', label: `ingresso ${fmtPrice(open.entry)}`, color: '--accent' });
      if (num(open.stop) != null) out.push({ i, price: num(open.stop), kind: 'level', label: `stop ${fmtPrice(open.stop)}`, color: '--crit' });
      if (num(open.liquidation) != null) out.push({ i, price: num(open.liquidation), kind: 'level', label: `liquidazione ${fmtPrice(open.liquidation)}`, color: '--text-3' });
    }
    for (const c of arr(b.closed)) {
      if (str(c.symbol).toUpperCase() !== symbol) continue;
      if (num(c.entry) != null) out.push({ i: idx(c.opened), price: num(c.entry), kind: 'entry' });
      if (num(c.exit) != null) out.push({ i: idx(c.closed), price: num(c.exit), kind: str(c.why).toLowerCase() === 'stop' ? 'stop' : 'exit' });
    }
    for (const o of arr(ctx.snap.orders)) {
      if (str(o.symbol).toUpperCase() !== symbol || str(o.status).toLowerCase() !== 'filled' || num(o.price) == null) continue;
      out.push({ i: idx(o.t), price: num(o.price), kind: orderSide(o.side).dir > 0 ? 'entry' : 'exit' });
    }
    return out.filter((m) => m.i >= 0);
  }

  function paintChartMode() {
    const ok = !!bars;
    cxEmpty.hidden = ok || bars === undefined;
    cxHost.hidden = !ok || ui.table;
    cxTable.hidden = !ok || !ui.table;
    ovBar.hidden = !ok || ui.table;
    if (ok && ui.table) {
      const v = cx.view || { from: 0, to: bars.t.length - 1 };
      const rows = [];
      for (let i = v.to; i >= Math.max(v.from, v.to - 250); i--) rows.push(i);
      fill(cxTable, h('div', { class: 'table-wrap' }, h('table', { class: 'table table--dense' },
        h('caption', { class: 'sr-only', text: `Barre giornaliere di ${bars.symbol}` }),
        h('thead', null, h('tr', null, ['Data', 'Apertura', 'Massimo', 'Minimo', 'Chiusura', 'Volume', bars.conviction ? 'Conviction' : null, bars.gq ? 'GQ' : null].filter(Boolean).map((t, i) => h('th', { scope: 'col', class: i ? 'is-num' : null, text: t })))),
        h('tbody', null, rows.map((i) => h('tr', null, h('td', { text: fmtDate(bars.t[i], true) }),
          [bars.o[i], bars.h[i], bars.l[i], bars.c[i]].map((x) => h('td', { class: 'is-num', text: fmtPrice(x) })), h('td', { class: 'is-num', text: fmtNum(bars.v[i], 0) }),
          bars.conviction ? h('td', { class: 'is-num', text: fmtNum(bars.conviction[i], 2) }) : null, bars.gq ? h('td', { class: 'is-num', text: fmtNum(bars.gq[i], 2) }) : null))))));
    }
    if (ok && !ui.table) cx.redraw();
  }

  async function loadSymbol(sym, { keepView = false } = {}) {
    const symbol = str(sym).toUpperCase();
    if (!symbol) return;
    ui.symbol = symbol;
    savePref('term.symbol', symbol);
    if ([...symSel.options].some((o) => o.value === symbol)) symSel.value = symbol;
    const d = await getOhlc(symbol, 1500);
    if (!alive || ui.symbol !== symbol) return;
    bars = d || null;
    if (!d) {
      fill(cxEmpty, empty(d === undefined ? 'Prezzi non leggibili' : `Nessun prezzo per ${symbol}`, 'Il grafico si riempie quando la cache dei dati (GERVA_CACHE) contiene le barre giornaliere dello strumento.'));
      cx.setData(null);
      chartP.note.textContent = '';
    } else {
      cx.setData({ ...d, markers: markersFor(symbol, d) }, { keepView, months: Number(ui.range) || null });
      chartP.note.textContent = `${d.kind}${d.example ? ' · ESEMPIO' : ''} · ${d.t.length} barre al ${fmtDate(d.t[d.t.length - 1], true)}${d.conviction ? ' · conviction e GQ dal motore' : ''}`;
    }
    paintChartMode();
  }

  function paintEquity() {
    const { snap, ccy } = ctx;
    const rows = arr(obj(compare).rows).filter((r) => num(r.nuovo_totale) != null && parseTs(r.data) != null);
    if (ui.eqMode === 'confronto') {
      const ok = rows.length >= 2;
      eqHost.hidden = !ok;
      eqEmpty.hidden = ok;
      if (!ok) {
        eqChart.update(null);
        fill(eqLegend);
        fill(eqEmpty, empty('Confronto non ancora disponibile', 'Compare quando esiste confronto_nav.csv: il valore giornaliero del nuovo sistema accanto al conto GERVA Capital originale.'));
        return;
      }
      const x = rows.map((r) => parseTs(r.data));
      const base = (k) => { const f = rows.find((r) => num(r[k]) != null); const b0 = f ? num(f[k]) : null; return rows.map((r) => (num(r[k]) == null || !b0 ? null : (num(r[k]) / b0) * 100)); };
      const a = base('nuovo_totale'); const l = base('legacy_nav'); const sp = base('spy');
      const n = rows.length - 1;
      fill(eqLegend, obj(compare).example ? h('span', { class: 'tag tag--sim', text: 'ESEMPIO' }) : null,
        [['fund', 'Nuovo', a[n]], ['s2', 'Originale', l[n]], ['bench', 'SPY', sp[n]]].map(([k, t, v]) => h('span', { class: 'legend__item' }, h('span', { class: `key key--${k}` }), t, h('span', { class: 'num', text: v == null ? DASH : fmtNum(v, 1) }))));
      eqChart.update({
        x, panels: [{ height: Math.max(90, eqHost.clientHeight - 30 || 150), format: (v, st) => fmtNum(v, stepDigits(st, 1)), refs: [{ value: 100, label: '' }], series: [{ values: sp, cls: 'bench' }, { values: l, cls: 's2' }, { values: a, cls: 'fund', end: true }] }],
        tip: (i) => ({ title: fmtDate(x[i], true), rows: [{ key: 'fund', label: 'Nuovo', value: fmtNum(a[i], 1) }, { key: 's2', label: 'Originale', value: l[i] == null ? DASH : fmtNum(l[i], 1) }, { key: 'bench', label: 'SPY', value: sp[i] == null ? DASH : fmtNum(sp[i], 1) }], note: 'base 100 al primo giorno' }),
      });
      return;
    }
    const c = curveOf(snap);
    const ok = c.t.length >= 2;
    eqHost.hidden = !ok;
    eqEmpty.hidden = ok;
    if (!ok) { eqChart.update(null); fill(eqLegend); fill(eqEmpty, empty('Storico non ancora disponibile', 'La curva compare dopo i primi due giorni di dati.')); return; }
    const bench = rebaseBench(c, 0);
    const n = c.t.length - 1;
    const hasBench = bench.some((v) => v != null);
    fill(eqLegend, h('span', { class: 'legend__item' }, h('span', { class: 'key key--fund' }), 'NAV', h('span', { class: 'num', text: fmtPctSigned(c.equity[n] / c.equity[0] - 1, 1) })),
      hasBench ? h('span', { class: 'legend__item' }, h('span', { class: 'key key--bench' }), 'Benchmark', h('span', { class: 'num', text: fmtPctSigned(bench[n] / bench.find((v) => v != null) - 1, 1) })) : null,
      h('span', { class: 'legend__item' }, h('span', { class: 'key key--dd' }), 'DD max', h('span', { class: 'num', text: fmtPct(Math.min(...c.dd), 1) })));
    const total = eqHost.clientHeight || 220;
    const ddH = Math.max(34, Math.round(total * 0.2));
    let lo = Infinity; let hi = -Infinity;
    for (const v of c.equity) { if (v < lo) lo = v; if (v > hi) hi = v; }
    eqChart.update({
      x: c.t,
      panels: [
        { height: Math.max(70, total - ddH - 70), scale: lo > 0 && hi / lo >= 3 ? 'log' : 'linear', format: fmtAxisAmount, series: [{ values: bench, cls: 'bench' }, { values: c.equity, cls: 'fund', area: true, end: true }] },
        { height: ddH, title: 'Sotto il massimo', top: 0, format: (v, st) => fmtPct(v, stepDigits((st ?? 1) * 100, 1)), series: [{ values: c.dd, cls: 'dd', area: true }] },
      ],
      tip: (i) => ({ title: fmtDate(c.t[i], true), rows: [{ key: 'fund', label: 'NAV', value: fmtMoney(c.equity[i], ccy, { digits: 0 }) }, bench[i] == null ? null : { key: 'bench', label: 'Benchmark', value: fmtMoney(bench[i], ccy, { digits: 0 }) }, { key: 'dd', label: 'Drawdown', value: fmtPct(c.dd[i], 2) }].filter(Boolean) }),
    });
  }

  function paintRisk() {
    const { snap } = ctx;
    const risk = obj(snap.risk);
    const st = riskState(risk);
    const limits = arr(risk.limits);
    const steps = arr(risk.dd_ladder).filter((s) => num(s.level) != null).sort((a, b) => Math.abs(num(a.level)) - Math.abs(num(b.level)));
    const dd = num(obj(snap.nav).drawdown_pct);
    const volUse = utilization(risk.vol_realized_30d, risk.vol_target);
    fill(riskP.body,
      h('div', { class: 'trisk__state' }, h('span', { class: `pill pill--${st.kind}` }, icon(st.icon), h('span', { text: st.label })), h('span', { class: 'trisk__why', text: str(risk.state_reason) || st.text, title: str(risk.state_reason) })),
      limits.length ? h('ul', { class: 'tlim' }, limits.map((l) => {
        const u = utilization(l.value, l.limit);
        const info = limitStatus(l.status);
        return h('li', { class: 'tlim__row' }, h('span', { class: 'tlim__name', text: str(l.name), title: str(l.name) }), bullet({ ratio: u, kind: info.kind, label: `Utilizzo di ${str(l.name)}` }),
          h('span', { class: `num tlim__v tlim__v--${info.kind}`, text: `${fmtUnit(l.value, l.unit)} / ${fmtUnit(l.limit, l.unit)}`, title: info.label }));
      })) : h('p', { class: 'muted', text: 'Nessun limite nello snapshot.' }),
      steps.length ? h('div', { class: 'tladder' }, h('span', { class: 'tladder__t', text: 'Scalini' }), steps.map((s) => h('span', { class: `tladder__s ${s.hit === true ? 'is-hit' : ''}`.trim(), title: str(s.action) },
        h('b', { class: 'num', text: fmtPct(s.level, 0) }), dd == null || s.hit === true ? (s.hit === true ? ' scattato' : '') : ` −${fmtNum((Math.abs(num(s.level)) - Math.abs(Math.min(dd, 0))) * 100, 1)} pt`))) : null,
      h('div', { class: 'tkv' },
        h('span', null, 'VaR 95 ', h('b', { class: 'num', text: num(risk.var_95_1d_pct) == null ? DASH : fmtPct(Math.abs(num(risk.var_95_1d_pct)), 2) })),
        h('span', null, 'ES 95 ', h('b', { class: 'num', text: num(risk.es_95_1d_pct) == null ? DASH : fmtPct(Math.abs(num(risk.es_95_1d_pct)), 2) })),
        h('span', null, 'Vol 30g ', h('b', { class: 'num', text: `${fmtPct(risk.vol_realized_30d, 1)} / ${fmtPct(risk.vol_target, 0)}` }), volUse == null ? '' : ` (${fmtPct(volUse, 0)})`)));
  }

  function paintBook() {
    if (book === undefined) { fill(bookP.body, h('p', { class: 'muted', text: 'Lettura del libro…' })); return; }
    if (!book) { fill(bookP.body, empty('Libro dei trade non ancora presente', 'Si crea al primo giro del ciclo dei trade a margine isolato (tradebook.json).')); bookP.note.textContent = ''; return; }
    const b = obj(book);
    bookP.note.textContent = `${b.example ? 'ESEMPIO · ' : ''}${str(b.asof) ? `al ${str(b.asof).slice(0, 10)}` : ''}${num(b.equity) == null ? '' : ` · capitale ${fmtNum(b.equity, 0)}`}`;
    const open = Object.entries(obj(b.open)).map(([k, v]) => ({ ...obj(v), symbol: str(obj(v).symbol) || k }));
    const closed = arr(b.closed).slice(-8).reverse();
    const rNow = (t) => { const px = last.get(str(t.symbol).toUpperCase()); const d = num(t.initial_stop_distance); return px == null || num(t.entry) == null || !d ? null : ((px - num(t.entry)) * (num(t.side) || 1)) / (num(t.entry) * d); };
    const cellR = (v) => h('td', { class: `is-num ${v > 0 ? 'pos' : v < 0 ? 'neg' : ''}`, text: v == null ? DASH : `${fmtSigned(v, 2)} R` });
    fill(bookP.body,
      h('h3', { class: 'tsub', text: `Aperti (${open.length})` }),
      open.length ? h('div', { class: 'table-wrap' }, h('table', { class: 'table table--dense' }, h('caption', { class: 'sr-only', text: 'Trade aperti a margine isolato' }),
        h('thead', null, h('tr', null, ['Strum.', 'Livello', 'Ingresso', 'Stop', 'Liquid.', 'Leva', 'Rischio', 'R ora', 'MAE / MFE'].map((t, i) => h('th', { scope: 'col', class: i > 1 ? 'is-num' : null, text: t })))),
        h('tbody', null, open.map((t) => h('tr', null, h('td', null, h('span', { class: 'code code--strong', text: t.symbol }), num(t.side) < 0 ? ' corto' : ''), h('td', { text: str(t.tier) || DASH }),
          h('td', { class: 'is-num', text: fmtPrice(t.entry) }), h('td', { class: 'is-num', text: fmtPrice(t.stop) }), h('td', { class: 'is-num', text: fmtPrice(t.liquidation) }),
          h('td', { class: 'is-num', text: num(t.leverage) == null ? DASH : `${fmtNum(t.leverage, 1)}x` }), h('td', { class: 'is-num', text: fmtNum(t.risk, 0) }), cellR(rNow(t)),
          h('td', { class: 'is-num', text: `${num(t.mae) == null ? DASH : fmtSigned(t.mae, 2)} / ${num(t.mfe) == null ? DASH : fmtSigned(t.mfe, 2)}` }))))))
        : h('p', { class: 'muted tnone', text: 'Nessun trade aperto.' }),
      h('h3', { class: 'tsub', text: 'Ultimi chiusi' }),
      closed.length ? h('div', { class: 'table-wrap' }, h('table', { class: 'table table--dense' }, h('caption', { class: 'sr-only', text: 'Ultimi trade chiusi' }),
        h('thead', null, h('tr', null, ['Strum.', 'Aperto', 'Chiuso', 'Leva', 'R', 'Uscita'].map((t, i) => h('th', { scope: 'col', class: i === 3 || i === 4 ? 'is-num' : null, text: t })))),
        h('tbody', null, closed.map((t) => h('tr', null, h('td', null, h('span', { class: 'code code--strong', text: str(t.symbol) })), h('td', { class: 'num', text: str(t.opened).slice(5, 10) }), h('td', { class: 'num', text: str(t.closed).slice(5, 10) }),
          h('td', { class: 'is-num', text: num(t.leverage) == null ? DASH : `${fmtNum(t.leverage, 0)}x` }), cellR(num(t.R)), h('td', { text: str(t.why) || DASH }))))))
        : h('p', { class: 'muted tnone', text: 'Nessun trade chiuso.' }));
  }

  function paintAlerts() {
    const all = arr(ctx.snap.alerts).map((a) => ({ a, t: parseTs(a.t), lv: alertLevel(a.level) }))
      .sort((p, q) => ({ crit: 0, warn: 1 }[p.lv.kind] ?? 2) - ({ crit: 0, warn: 1 }[q.lv.kind] ?? 2) || (q.t ?? 0) - (p.t ?? 0));
    fill(alertP.body, all.length ? h('ul', { class: 'talerts' }, all.slice(0, 30).map(({ a, t, lv }) => h('li', { class: `talert talert--${lv.kind}` }, icon(lv.icon),
      h('span', { class: 'num talert__t', text: t == null ? DASH : fmtDayTime(t) }), h('span', { class: 'talert__m' }, h('span', { class: 'sr-only', text: `${lv.label}: ` }), str(a.msg) || DASH))))
      : h('p', { class: 'muted tnone', text: 'Nessun avviso.' }));
  }

  // ---- letture una tantum ----
  (async () => {
    const s = await getSymbols();
    if (!alive) return;
    symbols = arr(s && s.symbols);
    fill(symSel, symbols.length ? symbols.map((x) => h('option', { value: x.symbol, text: `${x.symbol} · ${x.kind}` })) : h('option', { value: '', text: 'nessuno' }));
    const pick = symbols.some((x) => x.symbol === ui.symbol) ? ui.symbol : (symbols[0] && symbols[0].symbol) || '';
    if (pick) loadSymbol(pick); else { bars = null; fill(cxEmpty, empty('Nessun dato di mercato', 'La cache dei dati (GERVA_CACHE) è vuota: il grafico compare quando contiene barre giornaliere.')); paintChartMode(); }
    if (ctx) paintTape();
  })();
  (async () => { book = undefined; const b = await getTradebook(); if (!alive) return; book = b || null; paintBook(); if (bars) cx.setData({ ...bars, markers: markersFor(ui.symbol, bars) }, { keepView: true }); })();
  (async () => { const c = await getCompare(); if (!alive) return; compare = c || null; if (ctx) paintEquity(); })();
  paintChartMode();

  return {
    update(next) {
      ctx = { ...next, at: Date.now() };
      paintStrip();
      clock();
      paintTape();
      paintEquity();
      paintRisk();
      const pos = arr(ctx.snap.positions);
      maxW = Math.max(0.0001, ...pos.map((r) => Math.abs(weightOf(r) ?? 0)));
      posP.note.textContent = pos.length ? `${pos.length}` : '';
      posTable.render(pos, { emptyHint: 'Il portafoglio è in liquidità o lo snapshot non riporta posizioni.' });
      stratTable.render(arr(ctx.snap.strategies));
      blotTable.render(arr(ctx.snap.orders).slice(0, 40));
      paintBook();
      paintAlerts();
    },
    /** Usato dalla barra dei comandi: carica uno strumento nel grafico. Ritorna false se non è in elenco. */
    openSymbol(sym) {
      const s = str(sym).toUpperCase();
      if (symbols.length && !symbols.some((x) => x.symbol === s)) return false;
      loadSymbol(s);
      return true;
    },
    destroy() { alive = false; clearInterval(timer); cx.destroy(); },
  };
}
