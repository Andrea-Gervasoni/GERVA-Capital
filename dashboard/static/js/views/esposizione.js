// Esposizione: lordo, netto e leva contro il limite; ripartizione per classe e per venue; posizioni.

import { h, fill } from '../dom.js';
import { card, dataTable, empty, signedMoney, stat } from '../components.js';
import { barTable, bullet } from '../charts.js';
import { DASH, arr, fmtMoney, fmtNum, fmtPct, fmtPctSigned, fmtPrice, fmtQty, num, obj, str } from '../format.js';
import { exposureDivisor, isBacktest, utilization } from '../model.js';

export function mount(root) {
  let ctx = null;
  let barsKey = null;

  const band = h('section', { class: 'card tiles span-12', 'aria-label': 'Esposizione complessiva' });
  const classCard = card({ title: 'Per classe di attivo', sub: 'In percentuale del patrimonio', cls: 'span-6', what: 'In che tipo di strumenti è investito il conto. La barra grigia («lordo») somma tutte le posizioni; quella blu («netto») sottrae le posizioni al ribasso da quelle al rialzo.', method: 'Lordo = Σ |peso|, netto = Σ peso, in frazione del patrimonio.' });
  const venueCard = card({ title: 'Per venue', sub: 'In percentuale del patrimonio', cls: 'span-6', what: 'Presso quale broker o borsa («venue») si trovano le posizioni. Serve a non concentrare troppo denaro in un solo posto.' });
  const posCard = card({ title: 'Posizioni', cls: 'span-12', flush: true, what: 'Tutto ciò che il conto possiede in questo momento. «Peso» è la quota del patrimonio in quello strumento; «P&L oggi» è il guadagno o la perdita di oggi, «P&L aperto» quello da quando la posizione è stata aperta. «Corto» indica una posizione che guadagna se il prezzo scende.' });

  const weightOf = (r) => {
    const w = num(r.weight);
    if (w != null) return w;
    const v = num(r.value);
    const eq = num(obj(ctx.snap.nav).equity);
    return v != null && eq ? v / eq : null;
  };
  let maxWeight = 1;

  const posTable = dataTable({
    caption: 'Posizioni aperte',
    sort: { key: 'value', dir: -1 },
    emptyTitle: 'Nessuna posizione aperta',
    columns: [
      {
        key: 'symbol', label: 'Strumento', sort: (r) => str(r.symbol),
        cell: (r) => h('div', { class: 'cell-id' },
          h('span', { class: 'code code--strong', text: str(r.symbol) || DASH }),
          (num(r.value) ?? num(r.qty) ?? 0) < 0 ? h('span', { class: 'tag tag--plain', text: 'corto' }) : null,
          h('span', { class: 'cell-id__name show-sm', text: str(r.strategy) })),
      },
      { key: 'strategy', label: 'Strategia', hide: 'sm', sort: (r) => str(r.strategy), cell: (r) => (str(r.strategy) ? h('span', { class: 'code', text: str(r.strategy) }) : null) },
      { key: 'venue', label: 'Venue', hide: 'md', sort: (r) => str(r.venue), cell: (r) => str(r.venue) },
      { key: 'qty', label: 'Quantità', num: true, hide: 'md', sort: (r) => num(r.qty), cell: (r) => (num(r.qty) == null ? null : fmtQty(r.qty)) },
      { key: 'price', label: 'Prezzo', num: true, hide: 'md', sort: (r) => num(r.price), cell: (r) => (num(r.price) == null ? null : fmtPrice(r.price)) },
      { key: 'value', label: 'Valore', num: true, sort: (r) => (num(r.value) == null ? null : Math.abs(num(r.value))), cell: (r) => (num(r.value) == null ? null : fmtMoney(r.value, ctx.ccy)) },
      {
        key: 'weight', label: 'Peso', num: true, cls: 'is-weight', sort: (r) => { const w = weightOf(r); return w == null ? null : Math.abs(w); },
        cell: (r) => {
          const w = weightOf(r);
          if (w == null) return null;
          return h('div', { class: 'weight' },
            bullet({ ratio: Math.abs(w) / maxWeight, kind: 'plain', label: `Peso di ${str(r.symbol)}`, text: fmtPct(w, 1) }),
            h('span', { class: 'weight__value', text: w < 0 ? fmtPctSigned(w, 1) : fmtPct(w, 1) }));
        },
      },
      { key: 'pnl_day', label: 'P&L oggi', num: true, sort: (r) => num(r.pnl_day), cell: (r) => (num(r.pnl_day) == null ? null : signedMoney(r.pnl_day, ctx.ccy)) },
      { key: 'pnl_open', label: 'P&L aperto', num: true, hide: 'sm', sort: (r) => num(r.pnl_open), cell: (r) => (num(r.pnl_open) == null ? null : signedMoney(r.pnl_open, ctx.ccy, { arrow: false })) },
    ],
  });
  posCard.body.append(posTable.el);

  root.append(h('div', { class: 'grid' }, band, classCard.el, venueCard.el, posCard.el));

  function fillBand() {
    const { snap, ccy } = ctx;
    const e = obj(snap.exposure);
    const nav = obj(snap.nav);
    const eq = num(nav.equity);
    const div = exposureDivisor(snap);
    const gross = num(e.gross) == null ? null : num(e.gross) / div;
    const net = num(e.net) == null ? null : num(e.net) / div;
    const lev = num(e.leverage);
    const maxLev = num(e.max_leverage);
    const use = utilization(lev, maxLev);
    const amount = (f) => (f == null || eq == null ? null : fmtMoney(f * eq, ccy, { digits: 0 }));
    const cash = num(nav.cash);
    fill(band, h('div', { class: 'tiles__grid tiles__grid--4' },
      stat({ label: 'Esposizione lorda', value: gross == null ? null : fmtPct(gross, 1), sub: amount(gross), hint: 'Somma dei valori assoluti delle posizioni', explain: 'Quanto è investito in tutto, rispetto al patrimonio. Sopra il 100% si sta usando la leva.' }),
      stat({ label: 'Esposizione netta', value: net == null ? null : (net < 0 ? fmtPctSigned(net, 1) : fmtPct(net, 1)), sub: amount(net), hint: 'Posizioni lunghe meno posizioni corte', explain: 'Posizioni al rialzo meno posizioni al ribasso: quanto il conto è esposto alla direzione del mercato.' }),
      stat({
        label: 'Leva', value: lev == null ? null : `${fmtNum(lev, 2)}x`, cls: 'stat--meter',
        sub: maxLev == null ? null : [
          bullet({ ratio: use, kind: use != null && use >= 1 ? 'crit' : use != null && use >= 0.8 ? 'warn' : 'ok', label: 'Leva rispetto al limite', text: `${fmtPct(use, 0)} del limite` }),
          h('span', { text: `limite ${fmtNum(maxLev, 2)}x${use == null ? '' : ` · ${fmtPct(use, 0)} usato`}` }),
        ],
        explain: 'La leva del conto: esposizione totale divisa per il patrimonio. La barra mostra quanto è vicina al limite.',
      }),
      stat({ label: 'Liquidità', value: cash == null ? null : fmtMoney(cash, ccy, { digits: 0 }), sub: cash != null && eq ? `${fmtPct(cash / eq, 1)} del patrimonio` : null, explain: 'Denaro non investito, pronto per nuove operazioni o per coprire i margini.' })));
  }

  function fillBars() {
    const { snap, ccy } = ctx;
    const e = obj(snap.exposure);
    const eq = num(obj(snap.nav).equity);
    const div = exposureDivisor(snap);
    const key = JSON.stringify([e.by_asset_class ?? null, e.by_venue ?? null, eq, div, ccy]);
    if (key === barsKey) return;
    barsKey = key;
    const amount = eq == null ? null : (f) => fmtMoney(f * eq, ccy, { digits: 0 });
    const rowsOf = (raw) => arr(raw)
      .map((r) => ({ name: str(r.name), gross: num(r.gross) == null ? null : num(r.gross) / div, net: num(r.net) == null ? null : num(r.net) / div }))
      .filter((r) => r.gross != null || r.net != null)
      .sort((a, b) => Math.abs(b.gross ?? b.net ?? 0) - Math.abs(a.gross ?? a.net ?? 0));
    const classes = rowsOf(e.by_asset_class);
    const venues = rowsOf(e.by_venue);
    fill(classCard.body, classes.length ? barTable(classes, { nameHead: 'Classe', amount }) : empty('Nessuna esposizione per classe', 'Il portafoglio non ha posizioni ripartibili.'));
    fill(venueCard.body, venues.length ? barTable(venues, { nameHead: 'Venue', amount }) : empty('Nessuna esposizione per venue', isBacktest(snap.meta) ? 'In backtest non c\'è un conto collegato a un broker.' : 'Nessuna posizione aperta presso un broker.'));
  }

  function fillPositions() {
    const { snap, ccy } = ctx;
    const rows = arr(snap.positions);
    maxWeight = Math.max(0.0001, ...rows.map((r) => Math.abs(weightOf(r) ?? 0)));
    posCard.setSub(rows.length ? `${rows.length} ${rows.length === 1 ? 'posizione' : 'posizioni'} · clic sull'intestazione per ordinare` : '');
    const sum = (k) => {
      const vals = rows.map((r) => num(r[k])).filter((v) => v != null);
      return vals.length ? vals.reduce((a, b) => a + b, 0) : null;
    };
    const netW = rows.map(weightOf).filter((v) => v != null);
    posTable.render(rows, {
      emptyHint: isBacktest(snap.meta) ? 'Il backtest non ha un conto collegato: le posizioni compaiono in paper e in live.' : 'Il portafoglio è interamente in liquidità.',
      footer: rows.length ? {
        symbol: 'Totale netto',
        value: sum('value') == null ? '' : fmtMoney(sum('value'), ccy),
        weight: netW.length ? fmtPct(netW.reduce((a, b) => a + b, 0), 1) : '',
        pnl_day: sum('pnl_day') == null ? '' : signedMoney(sum('pnl_day'), ccy),
        pnl_open: sum('pnl_open') == null ? '' : signedMoney(sum('pnl_open'), ccy, { arrow: false }),
      } : null,
    });
  }

  return {
    update(next) {
      ctx = next;
      fillBand();
      fillBars();
      fillPositions();
    },
    summary(c) {
      const e = obj(c.snap.exposure);
      const div = exposureDivisor(c.snap);
      const gross = num(e.gross) == null ? null : num(e.gross) / div;
      const n = arr(c.snap.positions).length;
      if (gross == null) return 'Lo snapshot non riporta l\'esposizione del conto.';
      const lev = num(e.leverage);
      const max = num(e.max_leverage);
      return `Il fondo è investito per il ${fmtPct(gross, 0)} del patrimonio${lev != null && max != null ? ` (leva ${fmtNum(lev, 2)}x su un massimo di ${fmtNum(max, 0)}x)` : ''}${n ? `, in ${n} ${n === 1 ? 'posizione' : 'posizioni'}` : ', senza posizioni elencate in questo snapshot'}.`;
    },
  };
}
