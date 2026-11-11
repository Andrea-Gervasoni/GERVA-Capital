// Ordini: gli ultimi ordini con stato e, per i rifiutati, il motivo.

import { h } from '../dom.js';
import { card, chip, dataTable, segmented } from '../components.js';
import { DASH, arr, fmtDateTime, fmtDayTime, fmtMoney, fmtPrice, fmtQty, num, parseTs, str } from '../format.js';
import { isBacktest, orderSide, orderStatus } from '../model.js';

const FILTERS = [
  { value: 'all', label: 'Tutti', match: () => true },
  { value: 'filled', label: 'Eseguiti', match: (s) => s === 'filled' || s === 'partial' },
  { value: 'pending', label: 'In attesa', match: (s) => s === 'pending' },
  { value: 'rejected', label: 'Rifiutati', match: (s) => s === 'rejected' || s === 'error' },
  { value: 'cancelled', label: 'Annullati', match: (s) => s === 'cancelled' || s === 'canceled' },
];

export function mount(root) {
  let ctx = null;
  let filter = 'all';

  const seg = segmented({ label: 'Filtra per stato', options: FILTERS, value: filter, onChange: (v) => { filter = v; paint(); } });
  const box = card({ title: 'Ordini recenti', actions: seg.el, cls: 'span-12', flush: true, what: 'Gli ultimi ordini mandati al broker. «Eseguito» è andato a buon fine; «In attesa» non è ancora stato eseguito; «Rifiutato» è stato fermato dal controllo di rischio o dal broker, con il motivo; «Annullato» è stato ritirato. Il controvalore è quantità per prezzo.', method: 'Ultimi 50 ordini del registro; il prezzo è quello di esecuzione se c\'è, altrimenti il prezzo di riferimento.' });
  const notional = (r) => (num(r.qty) == null || num(r.price) == null ? null : Math.abs(num(r.qty) * num(r.price)));
  const table = dataTable({
    caption: 'Ordini recenti',
    sort: { key: 't', dir: -1 },
    emptyTitle: 'Nessun ordine registrato',
    rowClass: (r) => (['rejected', 'error'].includes(str(r.status).toLowerCase()) ? 'is-rejected' : null),
    detail: (r) => (str(r.reason).trim() ? h('div', { class: 'reason' }, h('span', { class: 'reason__label', text: 'Motivo: ' }), str(r.reason)) : null),
    columns: [
      {
        key: 't', label: 'Ora', num: false, sort: (r) => parseTs(r.t),
        cell: (r) => { const t = parseTs(r.t); return t == null ? null : h('time', { class: 'num', datetime: new Date(t).toISOString(), title: fmtDateTime(t), text: fmtDayTime(t) }); },
      },
      {
        key: 'symbol', label: 'Strumento', sort: (r) => str(r.symbol),
        cell: (r) => h('div', { class: 'cell-id cell-id--stack-sm' }, h('span', { class: 'code code--strong', text: str(r.symbol) || DASH }), h('span', { class: 'cell-id__name show-sm', text: orderSide(r.side).label })),
      },
      {
        key: 'side', label: 'Lato', hide: 'sm', sort: (r) => str(r.side),
        cell: (r) => { const sd = orderSide(r.side); return h('span', { class: `side side--${sd.dir > 0 ? 'buy' : sd.dir < 0 ? 'sell' : 'na'}`, text: sd.label }); },
      },
      { key: 'qty', label: 'Quantità', num: true, hide: 'sm', sort: (r) => num(r.qty), cell: (r) => (num(r.qty) == null ? null : fmtQty(r.qty)) },
      { key: 'price', label: 'Prezzo', num: true, sort: (r) => num(r.price), cell: (r) => (num(r.price) == null ? null : fmtPrice(r.price)) },
      { key: 'notional', label: 'Controvalore', num: true, hide: 'md', sort: notional, cell: (r) => (notional(r) == null ? null : fmtMoney(notional(r), ctx.ccy)) },
      { key: 'strategy', label: 'Strategia', hide: 'sm', sort: (r) => str(r.strategy), cell: (r) => (str(r.strategy) ? h('span', { class: 'code', text: str(r.strategy) }) : null) },
      { key: 'venue', label: 'Venue', hide: 'md', sort: (r) => str(r.venue), cell: (r) => str(r.venue) },
      { key: 'status', label: 'Stato', sort: (r) => str(r.status), cell: (r) => chip(orderStatus(r.status), { compact: true }) },
      { key: 'reason', label: 'Motivo', hide: 'lg', cls: 'is-wrap', blank: true, cell: (r) => (str(r.reason).trim() ? h('span', { class: 'reason-inline', text: str(r.reason) }) : null) },
    ],
  });
  box.body.append(table.el);
  root.append(h('div', { class: 'grid' }, box.el));

  function paint() {
    const all = arr(ctx.snap.orders);
    const status = (r) => str(r.status).toLowerCase();
    for (const f of FILTERS) seg.setCount(f.value, all.filter((r) => f.match(status(r))).length);
    const current = FILTERS.find((f) => f.value === filter) || FILTERS[0];
    const rows = all.filter((r) => current.match(status(r)));
    box.setSub(all.length ? `${all.length} ${all.length === 1 ? 'ordine' : 'ordini'} nello snapshot, dal più recente` : '');
    table.render(rows, {
      emptyHint: all.length
        ? 'Nessun ordine con questo stato.'
        : (isBacktest(ctx.snap.meta) ? 'Il backtest non registra ordini: compaiono in paper e in live.' : 'Il motore non ha ancora inviato ordini.'),
    });
  }

  return {
    update(next) {
      ctx = next;
      paint();
    },
    summary(c) {
      const all = arr(c.snap.orders);
      if (!all.length) return 'In questo snapshot non ci sono ordini.';
      const count = (f) => all.filter((r) => f.match(str(r.status).toLowerCase())).length;
      const rej = count(FILTERS[3]);
      return `Nello snapshot ci sono ${all.length} ordini: ${count(FILTERS[1])} eseguiti, ${count(FILTERS[2])} in attesa${rej ? `, ${rej} ${rej === 1 ? 'rifiutato' : 'rifiutati'} (il motivo è indicato nella riga)` : ', nessuno rifiutato'}.`;
    },
  };
}
