// Spazio «Portafoglio»: da dove viene il risultato, che cosa ho in mano.
// In quest'ordine: cascata di attribuzione (oggi / mese / dall'avvio, con «non attribuito») · dove sono i soldi (sede → strumento,
// colore = strategia) · strategie una accanto all'altra · esposizione nel tempo e contro i tetti · posizioni · mesi × anni ·
// correlazioni · rischio e rendimento di strategie e profili, con il sistema originale.
// Ogni contributo si calcola in derive.js; tetti e soglie arrivano dalla fotografia (risk.limits); la storia che manca è uno stato vuoto.

import { scatter, stackedArea, treemap, waterfall } from '../chart-engine.js';
import { heatmap, matrix, timeChart } from '../charts.js';
import { dataTable, segmented } from '../components.js';
import { h, icon } from '../dom.js';
import { arr, fmtDate, fmtMoney, fmtNum, fmtPct, fmtPctSigned, fmtPrice, fmtQty, fmtSigned, list, num, obj, parseTs, str } from '../format.js';
import { getTradebook } from '../market.js';
import { monthlyGrid, strategyStatus, utilization } from '../model.js';
import { SPLIT_T, attribution, provenanceDays, rollingSharpe } from '../derive.js';
import { emptyState, meterRow, panel, provOf, provTag } from '../panels.js';
import { factRow, legendRow, nd, plot, sparkArea, stateChip } from './kit.js';

const SLEEVES = ['CR-TREND', 'CR-XSMOM', 'EQ-MR', 'MA-TREND'];            // ordine fisso: il colore segue la strategia, mai il rango
const MIN_LIVE_DAYS = 60;                                                  // prima, lo Sharpe del conto non si mostra (design_3, conflitto 3)
const signed = (v, text) => h('span', { class: v > 0 ? 'pos' : v < 0 ? 'neg' : '' }, v > 0 || v < 0 ? icon(v > 0 ? 'up' : 'down', 'icon--solid sp-arrow') : null, text);

export function mount(root) {
  let ctxNow = null;
  let tb;
  let period = 'day';
  let expoBy = 'strategy';
  const clsOf = (id) => { const ids = [...SLEEVES, ...arr(ctxNow && ctxNow.snap.strategies).map((s) => str(s.id)).filter((x) => !SLEEVES.includes(x))]; const i = ids.indexOf(str(id)); return i < 0 ? 'c4' : `c${(i % 4) + 1}`; };

  // ---- 1. attribuzione ----
  const periodSeg = segmented({ label: 'Periodo', options: [{ value: 'day', label: 'Oggi' }, { value: 'mtd', label: 'Mese' }, { value: 'total', label: 'Dall\'avvio' }], value: period, onChange: (v) => { period = v; paintAttr(); } });
  const pAttr = panel({ title: 'Da dove viene il risultato?', eyebrow: 'Attribuzione', span: 6, tools: periodSeg.el, id: 'attribuzione',
    ask: 'Ogni barra parte da dove finisce la precedente: verde aggiunge, rosso toglie. L\'ultima è il totale del periodo.',
    what: 'Il guadagno o la perdita del periodo, diviso tra le strategie e il libro dei trade. «Non attribuito» è la parte che la somma delle voci non spiega: se supera un punto base viene segnalata, perché vuol dire che una base di calcolo non è dichiarata.' });
  const attrBig = h('div', { class: 'bignum' });
  const attrHost = h('div', { class: 'chart-host' });
  const attrNote = h('p', { class: 'panel__ask' });
  pAttr.body.append(attrBig, attrHost, attrNote);
  const attrChart = waterfall(attrHost, [], { label: 'Contributo di strategie e libro dei trade al risultato', orient: 'h', format: (v) => fmtMoney(v, 'EUR', { digits: 2, signed: true }), levelFormat: (v) => fmtMoney(v, 'EUR', { digits: 0 }), valueHead: 'Contributo', levelHead: 'Somma', table: true });

  // ---- 2. dove sono i soldi ----
  const pTree = panel({ title: 'Dove sono i soldi, adesso?', eyebrow: 'Sede → strumento · colore = strategia', span: 6, id: 'mappa',
    ask: 'Ogni rettangolo è una posizione: più è grande, più pesa. I riquadri raggruppano per sede; il colore dice quale strategia la tiene.',
    what: 'Mappa ad albero del controvalore delle posizioni: primo livello la sede (dove sta il denaro), dentro gli strumenti, colorati secondo la strategia che li detiene. La liquidità non è nella mappa: è scritta sotto.' });
  const treeHost = h('div', { class: 'chart-host' });
  const treeLegend = h('div');
  pTree.body.append(treeHost, treeLegend);
  let tree = null;

  // ---- 3. strategie ----
  const pStrat = panel({ title: 'Quale strategia sta tenendo, e quale sta perdendo il suo vantaggio?', eyebrow: 'Strategie, una accanto all\'altra', span: 12, id: 'strategie',
    ask: 'Una scheda per regola, tutte con la stessa scala: in alto l\'ultimo mese del conto, sotto la «qualità» del rendimento nella storia simulata (sopra zero guadagna più di quanto rischia). La fascia è l\'incertezza: se contiene lo zero, non si può dire che funzioni ancora.',
    what: 'Per ogni strategia: quota di rischio, esposizione di adesso, risultato di oggi, del mese e dall\'avvio, andamento degli ultimi 30 giorni. Lo Sharpe del conto compare solo dopo 60 giorni di paper, con il suo errore; fino ad allora c\'è solo quello simulato, diviso tra periodo di scelta e di verifica. Sotto, lo Sharpe mobile a 52 settimane con la banda di ±1,96 errori standard.' });
  const stratGrid = h('div', { class: 'sp-four' });
  pStrat.body.append(stratGrid);
  const cards = new Map();

  // ---- 4. esposizione nel tempo ----
  const expoSeg = segmented({ label: 'Raggruppa per', options: [{ value: 'strategy', label: 'Strategia' }, { value: 'venue', label: 'Sede' }], value: expoBy, onChange: (v) => { expoBy = v; paintExpo(); } });
  const pExpo = panel({ title: 'Come si sposta il peso, e quanto manca ai tetti?', eyebrow: 'Esposizione', span: 12, tools: expoSeg.el, id: 'esposizione',
    ask: 'A sinistra come è cambiato il peso nel tempo; a destra quanto è esposto il conto adesso, con la tacca bianca del tetto dove un tetto esiste.',
    what: 'L\'esposizione è la parte del patrimonio investita, per strategia o per sede. I tetti sono quelli del motore di rischio, letti dalla fotografia: sopra il 90% di un tetto la barra diventa ambra e gli ordini che lo supererebbero vengono rifiutati.' });
  const expoPlot = plot();
  const expoLeft = h('div');
  const expoRight = h('div');
  pExpo.body.append(h('div', { class: 'sp-two sp-two--wide' }, h('div', null, h('div', { class: 'sp-sub', text: 'Nel tempo' }), expoLeft), h('div', null, h('div', { class: 'sp-sub', text: 'Adesso, contro i tetti' }), expoRight)));
  const expoChart = stackedArea(expoPlot.host, { label: 'Esposizione nel tempo' });

  // ---- 5. posizioni ----
  const pPos = panel({ title: 'Che cosa ho in mano?', eyebrow: 'Posizioni', span: 12, id: 'posizioni',
    what: 'Tutte le posizioni aperte del libro giornaliero. Il peso è il controvalore diviso per il patrimonio; la tacca sulla barra è il peso massimo ammesso per un singolo strumento. Tocca un\'intestazione per ordinare.' });
  const posFacts = h('div');
  const posTable = dataTable({
    caption: 'Posizioni aperte', sort: { key: 'weight', dir: -1 }, emptyTitle: 'Nessuna posizione', emptyHint: 'Il fondo è in liquidità.', cls: 'table--dense sp-table sp-postable',
    columns: [
      { key: 'symbol', label: 'Strumento', sort: (p) => str(p.symbol), cell: (p) => h('a', { class: 'sp-sym', href: `#/mercati?s=${encodeURIComponent(str(p.symbol))}` }, h('span', { class: `key sp-key sp-key--${clsOf(p.strategy)}`, 'aria-hidden': 'true' }), str(p.symbol)) },
      { key: 'strategy', label: 'Strategia', hide: 'sm', sort: (p) => str(p.strategy), cell: (p) => str(p.strategy) },
      { key: 'venue', label: 'Sede', hide: 'sm', sort: (p) => str(p.venue), cell: (p) => str(p.venue) },
      { key: 'qty', label: 'Quantità', num: true, hide: 'md', cls: 'not-semplice', sort: (p) => num(p.qty), cell: (p) => (num(p.qty) == null ? null : fmtQty(p.qty)) },
      { key: 'price', label: 'Prezzo', num: true, hide: 'md', cls: 'not-semplice', sort: (p) => num(p.price), cell: (p) => (num(p.price) == null ? null : fmtPrice(p.price)) },
      { key: 'value', label: 'Valore', num: true, sort: (p) => num(p.value), cell: (p) => (num(p.value) == null ? null : fmtMoney(p.value, ctxNow.ccy, { digits: 0 })) },
      { key: 'weight', label: 'Peso', num: true, sort: (p) => num(p.weight), cell: (p) => weightBar(p) },
      { key: 'day', label: 'Oggi', num: true, sort: (p) => num(p.pnl_day), cell: (p) => (num(p.pnl_day) == null ? null : signed(p.pnl_day, fmtMoney(p.pnl_day, ctxNow.ccy, { signed: true }))) },
      { key: 'open', label: 'Da quando è aperta', num: true, hide: 'sm', sort: (p) => num(p.pnl_open), cell: (p) => (num(p.pnl_open) == null ? null : signed(p.pnl_open, fmtMoney(p.pnl_open, ctxNow.ccy, { signed: true }))) },
    ],
  });
  pPos.body.append(posFacts, posTable.el);
  let capW = null;
  let maxW = 0.2;
  function weightBar(p) {
    const w = num(p.weight);
    if (w == null) return null;
    const bar = h('span', { class: 'sp-wbar', dataset: { state: capW && Math.abs(w) / capW >= 0.9 ? 'warn' : 'ok' } }, h('i'), capW ? h('b') : null);
    bar.style.setProperty('--v', `${Math.min(100, (Math.abs(w) / maxW) * 100).toFixed(1)}%`);
    if (capW) bar.style.setProperty('--t', `${Math.min(100, (capW / maxW) * 100).toFixed(1)}%`);
    return h('span', { class: 'sp-wcell' }, bar, h('span', { class: 'num', text: fmtPct(w, 1) }));
  }

  // ---- 6. mesi ----
  const pMonths = panel({ title: 'Quali mesi hanno fatto l\'anno?', eyebrow: 'Rendimenti mensili', span: 8, id: 'mesi',
    ask: 'Ogni cella è un mese: blu ha guadagnato, arancio ha perso, più intenso più grande. Il numero è il rendimento in percentuale.',
    what: 'Rendimenti mensili del conto per anno e per mese, con il totale dell\'anno. Il colore usa una rampa blu ↔ arancio leggibile anche da chi non distingue rosso e verde; il numero è sempre scritto nella cella.' });
  const monthsHost = h('div', { class: 'chart-host' });
  const monthsFacts = h('div', { class: 'not-semplice' });
  pMonths.body.append(monthsHost, monthsFacts);

  // ---- 7. correlazioni ----
  const pCorr = panel({ title: 'Le strategie si compensano?', eyebrow: 'Correlazioni', span: 4, id: 'correlazioni',
    ask: 'Vicino a zero (grigio): si muovono per conto proprio, ed è ciò che si vuole. Blu: insieme. Arancio: in senso opposto.',
    what: 'Correlazione tra i rendimenti delle quattro strategie nella storia simulata. Strategie poco correlate si compensano: quando una perde, le altre non perdono per forza. È il motivo per cui lo Sharpe del portafoglio supera la media di quelli delle singole strategie.' });
  const corrBox = h('div');
  pCorr.body.append(corrBox);

  // ---- 8. rischio e rendimento ----
  const pRR = panel({ title: 'Quanto rende ogni pezzo per il rischio che prende?', eyebrow: 'Rischio e rendimento', span: 12, cls: 'not-semplice', id: 'rischio-rendimento',
    what: 'Ogni punto è una strategia o un profilo del fondo nella storia simulata: a destra più volatile, in alto più redditizio. Sulla diagonale rendimento e volatilità sono uguali (Sharpe 1, a tasso zero): sopra è meglio. Il sistema originale è segnato in ambra.' });
  const rrHost = h('div', { class: 'chart-host' });
  pRR.body.append(rrHost);
  let rr = null;

  root.append(h('div', { class: 'ws sp-ws' }, pAttr.el, pTree.el, pStrat.el, pExpo.el, pPos.el, pMonths.el, pCorr.el, pRR.el));

  // ---- disegno ----
  function paintAttr() {
    const { snap, ccy, lv } = ctxNow;
    const prov = provOf(snap.meta);
    pAttr.setProv(provTag(prov));
    const a = attribution(snap, tb, period);
    const name = { day: 'oggi', mtd: 'nel mese', total: 'dall\'avvio' }[period];
    if (!a.rows.length) {
      attrHost.hidden = true; attrBig.replaceChildren('n.d.');
      attrNote.replaceChildren('Nessun contributo da mostrare per questo periodo: la fotografia non riporta il P&L per strategia.');
      return;
    }
    attrHost.hidden = false;
    attrBig.replaceChildren(signed(a.total, fmtMoney(a.total, ccy, { signed: true })), h('small', { text: name }));
    const rows = a.rows.slice().sort((x, y) => y.value - x.value).map((r) => ({ label: lv === 'semplice' ? r.name || r.id : r.id, value: r.value }));
    attrChart.update([...rows,
      ...(a.trade != null ? [{ label: 'Libro dei trade', value: a.trade, note: 'Contributo del libro a margine isolato: patrimonio del libro meno il suo capitale iniziale.' }] : []),
      ...(Math.abs(a.gap) >= 0.005 ? [{ label: 'Non attribuito', value: a.gap, note: a.bp > 1 ? `Scarto di ${fmtNum(a.bp, 0)} punti base: da spiegare.` : '' }] : []),
      { label: 'Totale', value: a.total, total: true }]);
    const best = rows[0];
    attrNote.replaceChildren(...[
      lv === 'semplice' ? `${a.total >= 0 ? 'Ha guadagnato' : 'Ha perso'} soprattutto con ${best.label}. ` : '',
      a.estimate ? 'Stima: quota × rendimento del periodo × patrimonio di inizio periodo (la base del rendimento per strategia non è dichiarata nella fotografia). ' : 'Somma del P&L di oggi delle posizioni, per strategia. ',
      a.bp > 1 ? h('b', { text: `Non attribuito: ${fmtNum(a.bp, 0)} punti base. ` }) : '',
      a.trade == null ? (tb === undefined ? 'Libro dei trade: in lettura…' : !tb ? 'Libro dei trade: non disponibile (n.d.).' : `Libro dei trade: il contributo ${period === 'day' ? 'di oggi' : 'del mese'} non è nella fotografia (n.d.); quello dall'avvio sì.`) : tb && tb.example ? 'Libro dei trade: esempio.' : ''].filter(Boolean));
  }

  function paintTree() {
    const { snap, ccy } = ctxNow;
    const pos = arr(snap.positions).filter((p) => num(p.value) != null && Math.abs(p.value) > 0);
    pTree.setProv(provTag(provOf(snap.meta)));
    const eq = num(obj(snap.nav).equity);
    if (!pos.length) { treeHost.replaceChildren(emptyState('Nessuna posizione', 'Il fondo è in liquidità: non c\'è nulla da disegnare.')); treeLegend.replaceChildren(); tree = null; return; }
    const venues = [...new Set(pos.map((p) => str(p.venue) || 'Sede n.d.'))];
    const items = venues.map((v) => ({ name: v, children: pos.filter((p) => (str(p.venue) || 'Sede n.d.') === v).map((p) => ({ name: str(p.symbol), value: Math.abs(p.value), cls: clsOf(p.strategy), k: 0.62, note: `${str(p.strategy)}${num(p.value) < 0 ? ' · al ribasso' : ''}` })) }));
    const opts = { label: 'Controvalore per sede e strumento, colore per strategia', height: ctxNow.lv === 'terminale' ? 250 : 300, format: (v) => (eq ? `${fmtPct(v / eq, 1)}` : fmtMoney(v, ccy, { digits: 0 })), valueHead: 'Peso sul patrimonio',
      tip: (it, group) => ({ title: `${group ? `${group.name} · ` : ''}${it.name}`, rows: [{ label: 'Controvalore', value: fmtMoney(it.value, ccy, { digits: 0 }) }, eq ? { label: 'Peso sul patrimonio', value: fmtPct(it.value / eq, 2) } : null].filter(Boolean), note: it.note }), table: true };
    if (!tree) tree = treemap(treeHost, items, opts); else tree.update(items);
    const used = [...new Set(pos.map((p) => str(p.strategy)))].sort((x, y) => clsOf(x).localeCompare(clsOf(y)));
    const cash = num(obj(snap.nav).cash);
    treeLegend.replaceChildren(legendRow(used.map((id) => [clsOf(id), id])), factRow([['Investito', eq ? fmtPct(pos.reduce((acc, p) => acc + Math.abs(p.value), 0) / eq, 1) : 'n.d.'], ['Liquidità', cash == null ? 'n.d.' : `${fmtMoney(cash, ccy, { digits: 0 })}${eq ? ` · ${fmtPct(cash / eq, 1)}` : ''}`]]));
  }

  function paintStrat() {
    const { snap, quant } = ctxNow;
    const list0 = arr(snap.strategies);
    const prov = provOf(snap.meta);
    pStrat.setProv(provTag(prov), provTag('sim', 'Sim Sharpe'));
    if (!list0.length) { stratGrid.replaceChildren(emptyState('Nessuna strategia nella fotografia')); cards.clear(); return; }
    const pd = provenanceDays(snap, ctxNow.quant4);
    const liveDays = pd.paper ?? pd.real ?? 0;
    const curves = arr(obj(quant).sleeve_curves);
    const sleeves = arr(obj(quant).sleeves);
    const t = curves.map((r) => parseTs(str(r.t)));
    const roll = new Map(list0.map((st) => [str(st.id), curves.length > 60 && curves.some((r) => num(r[str(st.id)]) != null) ? rollingSharpe(curves.map((r) => num(r[str(st.id)])), 52, 52) : null]));
    const all = [...roll.values()].filter(Boolean).flatMap((r) => [...r.lo, ...r.hi]).filter((v) => v != null).sort((a, b) => a - b);
    const yLo = all.length ? Math.floor(all[Math.floor(all.length * 0.02)]) : null;          // scala comune a tutte le schede, senza gli estremi isolati
    const yHi = all.length ? Math.ceil(all[Math.floor(all.length * 0.98)]) : null;
    const clip = (v) => (v == null ? null : Math.max(yLo, Math.min(yHi, v)));
    const ov = arr(obj(obj(snap.ai).overlay).strategie);
    const nodes = [];
    for (const st of list0) {
      const id = str(st.id);
      let c = cards.get(id);
      if (!c) {
        const sparkHost = h('div', { class: 'chart-host' });
        const rollPlot = plot();
        c = { head: h('div', { class: 'sp-strat__head' }), sub: h('div', { class: 'sp-strat__sub' }), sparkRow: h('div', { class: 'sp-strat__row' }), sparkHost, spark: sparkArea(sparkHost, { label: `${id}: ultimi 30 giorni` }),
          kv: h('div', { class: 'sp-strat__stats' }), rollHead: h('div', { class: 'sp-strat__row' }), rollPlot, roll: timeChart(rollPlot.host, { label: `${id}: Sharpe mobile a 52 settimane` }), rollFoot: h('div', { class: 'sp-strat__foot' }) };
        c.el = h('article', { class: 'sp-strat', 'aria-label': id }, c.head, c.sub, c.sparkRow, sparkHost, c.kv, c.rollHead, rollPlot.el, c.rollFoot);
        cards.set(id, c);
      }
      const status = strategyStatus(st.status);
      const brake = ov.find((o) => str(o.id) === id && num(o.mult) != null && o.mult < 1);
      c.head.replaceChildren(h('span', { class: 'sp-strat__id' }, h('span', { class: `key sp-key sp-key--${clsOf(id)}`, 'aria-hidden': 'true' }), id), stateChip(status.kind === 'ok' ? 'ok' : status.kind === 'warn' ? 'warn' : 'muted', status.label, { iconName: status.icon }));
      c.sub.replaceChildren(...[h('span', { class: 'sp-strat__name', title: str(st.name), text: str(st.name) }), h('span', { class: 'sp-strat__quota' }, `quota ${fmtPct(st.allocation, 0)}`, brake ? h('span', { title: str(brake.motivo) }, stateChip('accent', `Freno AI ${fmtPct(brake.mult, 0)}`, { iconName: 'ai' })) : null)]);
      const spark = list(st.spark).map(num).filter((v) => v != null);
      const chg = spark.length > 1 ? spark[spark.length - 1] / spark[0] - 1 : null;
      c.sparkRow.replaceChildren(h('span', { class: 'sp-strat__tag' }, provTag(prov === 'sim' ? 'sim' : prov), '30 giorni'), chg == null ? nd() : signed(chg, fmtPctSigned(chg, 2)));
      c.spark.update({ values: spark, prov });
      const sl = sleeves.find((x) => str(x.id) === id) || {};
      const cell = (k, v, sub = '') => h('div', null, h('span', { class: 'k', text: k }), h('span', { class: 'v' }, v), sub ? h('small', { text: sub }) : null);
      const pct = (v, d = 2) => (num(v) == null ? nd() : h('span', { class: v > 0 ? 'pos' : v < 0 ? 'neg' : '', text: fmtPctSigned(v, d) }));
      const liveOk = liveDays >= MIN_LIVE_DAYS && num(st.sharpe_live) != null;
      c.kv.replaceChildren(
        cell('Oggi', pct(st.pnl_day_pct)), cell('Mese', pct(st.pnl_mtd_pct)), cell('Avvio', pct(st.pnl_total_pct, 1)),
        cell('Esposizione', num(st.exposure) == null ? nd() : fmtPct(st.exposure, 1), 'del patrimonio'),
        cell('Sharpe del conto', liveOk ? fmtNum(st.sharpe_live, 2) : '—', liveOk ? `± ${fmtNum(Math.sqrt((1 + st.sharpe_live ** 2 / 2) / (liveDays / 365)), 1)}` : `${fmtNum(liveDays, 0)} giorni su ${MIN_LIVE_DAYS}`),
        cell('Sharpe simulato', num(st.sharpe_backtest) == null ? nd() : fmtNum(st.sharpe_backtest, 2), 'storia 2018–2026'),
        cell('Caduta massima', num(st.max_dd) == null ? nd() : fmtPctSigned(st.max_dd, 0), 'dal picco'));
      const r = roll.get(id);
      if (!r) { c.rollHead.replaceChildren(h('span', { class: 'sp-strat__tag' }, provTag('sim'), 'Sharpe a 52 sett.')); c.rollPlot.el.hidden = true; c.rollFoot.replaceChildren(nd('serie simulata non disponibile per questa strategia')); } else {
        c.rollPlot.el.hidden = false;
        const k0 = r.sharpe.findIndex((v) => v != null);
        const x = t.slice(k0);
        const last = r.sharpe[r.sharpe.length - 1];
        c.rollHead.replaceChildren(h('span', { class: 'sp-strat__tag' }, provTag('sim'), 'Sharpe a 52 sett.'), h('span', null, 'ora ', h('b', { text: last == null ? 'n.d.' : fmtSigned(last, 2) })));
        c.roll.update({
          x, marks: [{ t: SPLIT_T, label: '' }],
          panels: [{ height: 92, top: yHi, bottom: yLo, bands: [{ lo: r.lo.slice(k0).map(clip), hi: r.hi.slice(k0).map(clip), cls: 'neutral' }], series: [{ values: r.sharpe.slice(k0).map(clip), cls: `${clsOf(id)} sim`, end: true, name: 'Sharpe mobile' }], format: (v) => fmtSigned(v, 0), refs: [{ value: 0, label: '' }] }],
          tip: (i) => ({ title: `${fmtDate(x[i], true)} · ${x[i] >= SPLIT_T ? 'verifica' : 'scelta'}`, rows: [{ key: `${clsOf(id)}-sim`, label: 'Sharpe a 52 settimane', value: r.sharpe[k0 + i] == null ? '—' : fmtSigned(r.sharpe[k0 + i], 2) }, { label: 'Banda ±1,96 e.s.', value: r.lo[k0 + i] == null ? '—' : `${fmtSigned(r.lo[k0 + i], 1)} … ${fmtSigned(r.hi[k0 + i], 1)}` }] }),
        });
        c.rollFoot.replaceChildren(h('span', null, 'intero periodo: scelta ', h('b', { text: num(obj(sl.scelta).sharpe) == null ? 'n.d.' : fmtNum(sl.scelta.sharpe, 2) })), h('span', { class: 'sp-splitmark' }, 'verifica ', h('b', { text: num(obj(sl.verifica).sharpe) == null ? 'n.d.' : fmtNum(sl.verifica.sharpe, 2) })));
      }
      nodes.push(c.el);
    }
    if (stratGrid.childElementCount !== nodes.length || nodes.some((n, i) => stratGrid.children[i] !== n)) stratGrid.replaceChildren(...nodes);
    pStrat.setFoot(`Sharpe del conto: nascosto prima di ${MIN_LIVE_DAYS} giorni di paper (oggi ${fmtNum(liveDays, 0)}), poi con il suo errore standard. Sharpe mobile: rendimenti settimanali simulati, annualizzati con √52, fascia ±1,96 errori standard, stessa scala in tutte le schede; riga verticale = 1° gennaio 2023 (scelta | verifica). Fonte: research/v5/quant.json (sleeve_curves, sleeves).`);
  }

  function paintExpo() {
    const { snap, quant } = ctxNow;
    const ex = obj(snap.exposure);
    const prov = provOf(snap.meta);
    const limits = arr(obj(snap.risk).limits);
    const hist = arr(snap.exposure_history).map((r) => ({ t: parseTs(str(r.t)), by: obj(expoBy === 'strategy' ? r.by_strategy : r.by_venue) })).filter((r) => r.t != null);
    const strategies = arr(snap.strategies);
    // nel tempo
    if (hist.length >= 2) {
      const keys = [...new Set(hist.flatMap((r) => Object.keys(r.by)))];
      expoLeft.replaceChildren(expoPlot.el);
      expoPlot.setTags(provTag(prov));
      expoChart.update({ x: hist.map((r) => r.t), height: 220, format: (v) => fmtPct(v, 0), layers: keys.map((k, i) => ({ name: k, cls: expoBy === 'strategy' ? clsOf(k) : `c${(i % 4) + 1}`, values: hist.map((r) => num(r.by[k])) })) });
      pExpo.setProv(provTag(prov));
    } else if (expoBy === 'strategy' && arr(obj(quant).weights).length > 2) {
      const w = arr(quant.weights);
      const keys = Object.keys(w[0]).filter((k) => k !== 't');
      expoLeft.replaceChildren(expoPlot.el, h('p', { class: 'panel__ask sp-note' }, h('b', { text: 'La storia dell\'esposizione vera non è nella fotografia. ' }), 'Qui sopra le quote di rischio delle strategie nella storia simulata (parità di rischio, somma 100%): dicono come si sposta il peso, non quanto era investito il conto.'));
      expoPlot.setTags(provTag('sim', 'Simulato · quote di rischio'));
      expoChart.update({ x: w.map((r) => parseTs(str(r.t))), height: 220, normalize: true, layers: keys.map((k) => ({ name: k, cls: clsOf(k), values: w.map((r) => num(r[k])) })) });
      pExpo.setProv(provTag('sim', 'Sim storia'), provTag(prov, `${prov === 'demo' ? 'Esempio' : prov === 'paper' ? 'Paper' : 'Reale'} adesso`));
    } else {
      expoLeft.replaceChildren(emptyState(expoBy === 'venue' ? 'Storia per sede non disponibile' : 'Storia dell\'esposizione non disponibile',
        'La fotografia riporta solo l\'esposizione di adesso. La serie nel tempo, con i tetti, comparirà quando il motore la scriverà nella fotografia (exposure_history).'));
      pExpo.setProv(provTag(prov));
    }
    // adesso, contro i tetti
    const rows = [];
    const lev = limits.find((l) => /leva/i.test(str(l.name)));
    if (num(ex.gross) != null) rows.push(meterRow({ name: 'Esposizione lorda', sub: 'tutto il libro giornaliero', value: ex.gross, cap: lev ? num(lev.limit) : num(ex.max_leverage), state: stateOf(ex.gross, lev ? lev.limit : ex.max_leverage),
      text: `${fmtPct(ex.gross, 0)}${(lev ? num(lev.limit) : num(ex.max_leverage)) == null ? ' · tetto non letto' : ` su ${fmtPct(lev ? lev.limit : ex.max_leverage, 0)}`}` }));
    if (expoBy === 'strategy') {
      const top = Math.max(0.01, ...strategies.map((s) => Math.max(num(s.exposure) || 0, num(s.allocation) || 0))) * 1.2;
      for (const st of strategies) rows.push(meterRow({ name: h('span', { class: 'sp-name' }, h('span', { class: `key sp-key sp-key--${clsOf(st.id)}`, 'aria-hidden': 'true' }), str(st.id)), sub: str(st.name), value: num(st.exposure) || 0, cap: num(st.allocation), scale: top, state: 'none',
        text: `${num(st.exposure) == null ? 'n.d.' : fmtPct(st.exposure, 1)} · quota ${fmtPct(st.allocation, 0)}` }));
    } else {
      const venues = arr(ex.by_venue);
      const top = Math.max(0.01, ...venues.map((v) => num(v.gross) || 0), ...limits.filter((l) => /sede/i.test(str(l.name))).map((l) => num(l.limit) || 0)) * 1.15;
      for (const l of limits.filter((x) => /sede/i.test(str(x.name)))) rows.push(meterRow({ name: str(l.name).replace(/^Esposizione sulla /i, '').replace(/^./, (c) => c.toUpperCase()), sub: 'tetto del motore di rischio', value: num(l.value) || 0, cap: num(l.limit), scale: top, state: stateOf(l.value, l.limit), text: `${fmtPct(l.value, 1)} su ${fmtPct(l.limit, 0)} · ${fmtPct(utilization(l.value, l.limit), 0)} del tetto` }));
      for (const v of venues) rows.push(meterRow({ name: str(v.name), sub: 'nessun tetto di sede dichiarato', value: num(v.gross) || 0, cap: null, scale: top, state: 'none', text: num(v.gross) == null ? 'n.d.' : fmtPct(v.gross, 1) }));
    }
    expoRight.replaceChildren(...(rows.length ? rows : [emptyState('Esposizione non dichiarata', 'La fotografia non riporta l\'esposizione.')]));
    pExpo.setFoot(expoBy === 'strategy' ? 'La tacca sulle strategie è la quota di rischio assegnata, non un tetto. Tetti letti dalla fotografia (risk.limits).' : 'Tetti letti dalla fotografia (risk.limits); una sede senza tetto lo dichiara.');
  }
  const stateOf = (v, cap) => { const u = utilization(v, cap); return u == null ? 'none' : u >= 1 ? 'breach' : u >= 0.9 ? 'warn' : 'ok'; };

  function paintPos() {
    const { snap, ccy } = ctxNow;
    const pos = arr(snap.positions);
    pPos.setProv(provTag(provOf(snap.meta)));
    const lim = arr(obj(snap.risk).limits).find((l) => /peso massimo/i.test(str(l.name)));
    capW = lim ? num(lim.limit) : null;
    maxW = Math.max(0.05, capW || 0, ...pos.map((p) => Math.abs(num(p.weight) || 0))) * 1.08;
    const day = pos.reduce((a, p) => a + (num(p.pnl_day) || 0), 0);
    const big = pos.slice().sort((a, b) => Math.abs(num(b.weight) || 0) - Math.abs(num(a.weight) || 0))[0];
    posFacts.replaceChildren(factRow([['Posizioni', fmtNum(pos.length, 0)], big ? ['La più grande', `${str(big.symbol)} ${fmtPct(big.weight, 1)}${capW ? ` · tetto ${fmtPct(capW, 0)}` : ' · tetto non letto'}`] : null,
      pos.length ? ['P&L di oggi delle posizioni', fmtMoney(day, ccy, { signed: true }), day > 0 ? 'pos' : day < 0 ? 'neg' : ''] : null, ['Liquidità', num(obj(snap.nav).cash) == null ? 'n.d.' : fmtMoney(snap.nav.cash, ccy, { digits: 0 })]]));
    posTable.render(pos);
    pPos.setAsk(pos.length ? `Il conto tiene ${fmtNum(pos.length, 0)} posizioni; la più grande è ${str(big.symbol)}, al ${fmtPct(big.weight, 0)} del patrimonio.` : 'Nessuna posizione: il fondo è in liquidità.');
  }

  function paintMonths() {
    const { snap } = ctxNow;
    const grid = monthlyGrid(snap);
    const prov = provOf(snap.meta);
    const pd = provenanceDays(snap, ctxNow.quant4);
    const months = grid.cell.size;
    const mixed = prov === 'paper' && pd.paper != null && months > Math.ceil(pd.paper / 28) + 1;
    pMonths.setProv(provTag(prov), mixed ? provTag('sim', 'Sim prima del paper') : null);
    if (!months) { monthsHost.replaceChildren(emptyState('Nessun mese ancora', 'La griglia comparirà alla chiusura del primo mese.')); monthsFacts.replaceChildren(); return; }
    monthsHost.replaceChildren();
    heatmap(monthsHost, grid);
    const pf = obj(snap.performance);
    const vals = [...grid.cell.values()];
    monthsFacts.replaceChildren(factRow([['Mesi positivi', `${fmtNum(vals.filter((v) => v > 0).length, 0)} su ${fmtNum(vals.length, 0)}`], num(pf.best_month) != null ? ['Migliore', fmtPctSigned(pf.best_month, 1)] : null, num(pf.worst_month) != null ? ['Peggiore', fmtPctSigned(pf.worst_month, 1)] : null,
      num(pf.cagr) != null ? ['Rend. annuo', fmtPctSigned(pf.cagr, 1)] : null, num(pf.vol) != null ? ['Volatilità', fmtPct(pf.vol, 1)] : null]));
    pMonths.setFoot(`Rendimenti in percentuale; rampa blu ↔ arancio con il numero in ogni cella. ${num(pf.days) != null ? `Curva di ${fmtNum(pf.days, 0)} giorni${pd.paper != null ? `, di cui ${fmtNum(pd.paper, 0)} di paper` : ''}: rendimento annuo e volatilità valgono per tutta la curva, non per il solo paper.` : ''}`);
  }

  function paintCorr() {
    const c = obj(obj(ctxNow.quant).correlation);
    const labels = list(c.labels).map(str);
    if (labels.length < 2 || !Array.isArray(c.matrix)) { corrBox.replaceChildren(emptyState(ctxNow.quantStatus === 'loading' ? 'Ricerca in lettura…' : 'Correlazioni non disponibili', 'Manca il file della ricerca (research/v5/quant.json, correlation).')); pCorr.setProv(); return; }
    pCorr.setProv(provTag('sim'));
    const off = [];
    labels.forEach((_, i) => labels.forEach((__, j) => { if (j > i && num((c.matrix[i] || [])[j]) != null) off.push(c.matrix[i][j]); }));
    const avg = off.length ? off.reduce((a, v) => a + v, 0) / off.length : null;
    const max = off.length ? off.reduce((a, v) => (Math.abs(v) > Math.abs(a) ? v : a), 0) : null;
    corrBox.replaceChildren(matrix(labels, c.matrix, { caption: 'Correlazione tra i rendimenti delle strategie (simulata)' }),
      factRow([['Correlazione media', avg == null ? 'n.d.' : fmtSigned(avg, 2)], ['La più forte', max == null ? 'n.d.' : fmtSigned(max, 2)]]));
    pCorr.setFoot('Rendimenti giornalieri simulati 2018–2026. Fonte: research/v5/quant.json (correlation).');
  }

  function paintRR() {
    const sleeves = arr(obj(ctxNow.quant).sleeves);
    const stats = arr(obj(ctxNow.quant4).fund_stats);
    const pts = [
      ...sleeves.map((s) => ({ x: num(obj(s.tutto).vol), y: num(obj(s.tutto).cagr), group: 'sleeve', label: str(s.id), cls: clsOf(s.id) })),
      ...stats.map((s) => ({ x: num(s.vol), y: num(s.cagr), group: /originale/i.test(str(s.portafoglio)) ? 'orig' : 'profile', label: str(s.portafoglio).replace(/^GERVA Capital originale: /, 'Originale: ').replace(/^([A-C]\d?)\. .*$/, '$1').replace(/^C3 con.*$/, 'C3 scalini'), full: str(s.portafoglio) })),
    ].filter((p) => p.x != null && p.y != null);
    const spanX = Math.max(...pts.map((p) => p.x)) - Math.min(...pts.map((p) => p.x)) || 1;
    const spanY = Math.max(...pts.map((p) => p.y)) - Math.min(...pts.map((p) => p.y)) || 1;
    const hiddenNames = [];
    pts.forEach((p, i) => {                      // due punti quasi sovrapposti: l'etichetta resta solo al primo, l'altro è nominato nel piede e nel suggerimento
      if (pts.slice(0, i).some((q) => q.label && Math.abs(q.x - p.x) / spanX < 0.09 && Math.abs(q.y - p.y) / spanY < 0.05)) { hiddenNames.push(p.full || p.label); p.full = p.full || p.label; p.label = ''; }
    });
    if (pts.length < 2) { rrHost.replaceChildren(emptyState(ctxNow.quantStatus === 'loading' ? 'Ricerca in lettura…' : 'Rischio e rendimento non disponibili', 'Mancano i file della ricerca (quant.json, quant_v4.json).')); pRR.setProv(); rr = null; return; }
    pRR.setProv(provTag('sim'));
    const opts = { label: 'Volatilità e rendimento annuo di strategie e profili (simulati)', height: 340, xTitle: 'Volatilità annua', yTitle: 'Rendimento annuo', xFormat: (v) => fmtPct(v, 0), yFormat: (v) => fmtPct(v, 0), diagonal: true, showLabels: true, table: true,
      groups: [{ id: 'sleeve', label: 'Strategie', cls: 'c1' }, { id: 'profile', label: 'Profili del nuovo fondo', cls: 'fund' }, { id: 'orig', label: 'Sistema originale', cls: 'orig' }],
      tip: (p) => ({ title: p.full || p.label, rows: [{ label: 'Volatilità annua', value: fmtPct(p.x, 1) }, { label: 'Rendimento annuo', value: fmtPctSigned(p.y, 1) }, { label: 'Rendimento / volatilità', value: fmtNum(p.y / p.x, 2) }] }) };
    if (!rr) rr = scatter(rrHost, pts, opts); else rr.update(pts);
    pRR.setFoot(hiddenNames.length ? `Senza etichetta perché coperto da un punto vicino: ${hiddenNames.join('; ')}. ` : '', 'Diagonale: rendimento = volatilità. Storia simulata 2018–2026, al netto dei costi ipotizzati. Fonti: quant.json (sleeves), quant_v4.json (fund_stats).');
  }

  function paintAll() { paintAttr(); paintTree(); paintStrat(); paintExpo(); paintPos(); paintMonths(); paintCorr(); paintRR(); }

  getTradebook().then((res) => { tb = res || null; if (ctxNow) paintAttr(); });

  let lastKey = '';
  return {
    update(ctx) {
      const lvChanged = ctxNow && ctxNow.lv !== ctx.lv;
      ctxNow = ctx;
      if (lvChanged && tree) { tree = null; }
      paintAll();
      lastKey = ctx.lv;
    },
    summary(ctx) {
      const snap = ctx.snap;
      const a = attribution(snap, tb, 'day');
      const pos = arr(snap.positions);
      const best = a.rows.slice().sort((x, y) => y.value - x.value)[0];
      const ex = obj(snap.exposure);
      void lastKey;
      return `Il conto tiene ${fmtNum(pos.length, 0)} posizioni ed è investito al ${num(ex.gross) == null ? 'n.d.' : fmtPct(ex.gross, 0)}. `
        + `${a.total == null ? 'Il risultato di oggi non è disponibile.' : `Oggi ${a.total >= 0 ? 'guadagna' : 'perde'} ${fmtMoney(Math.abs(a.total), ctx.ccy, { digits: 0 })}${best ? `, soprattutto con ${best.name || best.id}` : ''}.`}`;
    },
  };
}
