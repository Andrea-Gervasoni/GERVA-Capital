// Strategie: una scheda per strategia con stato, allocazione, risultato, Sharpe reale contro backtest e ultimo segnale.

import { h, icon, fill } from '../dom.js';
import { chip, empty, explain, method, signedPct, stat } from '../components.js';
import { dumbbell, sparkline } from '../charts.js';
import { DASH, arr, fmtAge, fmtNum, fmtPct, fmtStamp, list, num, obj, parseTs, str } from '../format.js';
import { strategyStatus } from '../model.js';

export function mount(root) {
  const band = h('section', { class: 'card tiles span-12', 'aria-label': 'Riepilogo delle strategie' });
  const cards = h('div', { class: 'strats span-12' });
  const legendBox = h('div', { class: 'section-head span-12' },
    explain('In ogni scheda: «Allocazione» è la quota di patrimonio assegnata alla strategia, «Esposizione» quanta ne sta usando adesso. «Oggi», «Mese» e «Dall\'avvio» sono i suoi guadagni o perdite. «Drawdown massimo» è la sua caduta peggiore. Lo Sharpe confronta il rendimento con il rischio: il cerchio vuoto è quello atteso dal backtest, quello pieno è quello reale, se c\'è abbastanza storia.'),
    method('Sharpe reale mostrato solo con almeno 60 giorni di storico dal vivo; le curve sono il rendimento cumulato recente della strategia sul proprio capitale.'));
  root.append(h('div', { class: 'grid' }, band, legendBox, cards));

  function strategyCard(st, { now, maxShare, shMin, shMax }) {
    const info = strategyStatus(st.status);
    const alloc = num(st.allocation);
    const expo = num(st.exposure);
    const live = num(st.sharpe_live);
    const back = num(st.sharpe_backtest);
    const share = (v, cls) => (v == null ? null : h('span', { class: `bars__bar bars__bar--${cls}`, style: { left: '0%', width: `${Math.max(0.6, Math.abs(v) / maxShare * 100).toFixed(2)}%` } }));
    const signalAt = parseTs(st.last_signal);
    return h('article', { class: `card strat strat--${info.kind}` },
      h('header', { class: 'strat__head' },
        h('div', { class: 'strat__title' },
          h('span', { class: 'code code--strong', text: str(st.id) || DASH }),
          h('h2', { class: 'strat__name', text: str(st.name) || 'Strategia senza nome' })),
        chip(info)),
      h('div', { class: 'strat__body' },
        h('div', { class: 'strat__alloc' },
          h('div', { class: 'strat__alloc-row' },
            h('span', { class: 'strat__alloc-label' }, h('span', { class: 'key key--bench', 'aria-hidden': 'true' }), 'Allocazione'),
            h('span', { class: 'num strat__alloc-value', text: fmtPct(alloc, 1) })),
          h('div', { class: 'strat__alloc-row' },
            h('span', { class: 'strat__alloc-label' }, h('span', { class: 'key key--fund', 'aria-hidden': 'true' }), 'Esposizione'),
            h('span', { class: 'num strat__alloc-value', text: fmtPct(expo, 1) })),
          h('span', { class: 'bars__track', 'aria-hidden': 'true' }, share(alloc, 'gross'), share(expo, 'net'))),
        h('div', { class: 'strat__spark' },
          sparkline(st.spark, { width: 190, height: 52, label: `Andamento recente di ${str(st.id)}` }),
          h('span', { class: 'strat__spark-label', text: list(st.spark).length >= 2 ? `ultime ${list(st.spark).length} osservazioni` : '' }))),
      h('div', { class: 'strat__stats' },
        stat({ label: 'Oggi', value: signedPct(st.pnl_day_pct) }),
        stat({ label: 'Mese', value: signedPct(st.pnl_mtd_pct) }),
        stat({ label: "Dall'avvio", value: signedPct(st.pnl_total_pct, 1) }),
        stat({ label: 'Drawdown massimo', value: num(st.max_dd) == null ? null : fmtPct(st.max_dd, 1) })),
      h('div', { class: 'strat__sharpe' },
        h('span', { class: 'strat__sharpe-label', text: 'Sharpe' }),
        dumbbell({ from: back, to: live, min: shMin, max: shMax, label: `Sharpe: backtest ${fmtNum(back, 2)}, reale ${live == null ? 'non disponibile' : fmtNum(live, 2)}` }),
        h('span', { class: 'strat__sharpe-values' },
          h('span', { class: 'strat__sharpe-item' }, h('span', { class: 'dot dot--hollow', 'aria-hidden': 'true' }), 'backtest ', h('strong', { class: 'num', text: fmtNum(back, 2) })),
          h('span', { class: 'strat__sharpe-item' }, h('span', { class: 'dot dot--solid', 'aria-hidden': 'true' }), 'reale ', h('strong', { class: 'num', text: live == null ? DASH : fmtNum(live, 2) })),
          live == null ? h('span', { class: 'strat__sharpe-note', text: 'storico reale insufficiente' }) : null)),
      h('footer', { class: 'strat__foot' }, icon('clock'),
        h('span', null, 'Ultimo segnale: ',
          signalAt == null
            ? (str(st.last_signal) || 'non disponibile')
            : h('span', { class: 'num', text: `${fmtAge(st.last_signal, now)} (${fmtStamp(st.last_signal)})` }))));
  }

  return {
    update(ctx) {
      const list = arr(ctx.snap.strategies);
      const nav = obj(ctx.snap.nav);
      const active = list.filter((s) => str(s.status).toLowerCase() === 'active').length;
      const sumOf = (k) => {
        const v = list.map((s) => num(s[k])).filter((x) => x != null);
        return v.length ? v.reduce((a, b) => a + b, 0) : null;
      };
      fill(band, h('div', { class: 'tiles__grid tiles__grid--4' },
        stat({ label: 'Strategie attive', value: list.length ? `${active} di ${list.length}` : null, explain: 'Quante strategie stanno lavorando. Una strategia in pausa non apre nuove posizioni.' }),
        stat({ label: 'Allocazione totale', value: sumOf('allocation') == null ? null : fmtPct(sumOf('allocation'), 1), sub: 'quota del patrimonio assegnata', explain: 'La somma delle quote assegnate: di solito 100%.' }),
        stat({ label: 'Esposizione totale', value: sumOf('exposure') == null ? null : fmtPct(sumOf('exposure'), 1), sub: 'posizioni aperte dalle strategie', explain: 'Quanto è davvero investito adesso. Sopra il 100% si usa la leva.' }),
        stat({ label: 'Risultato del fondo oggi', value: signedPct(nav.pnl_day_pct), explain: 'Guadagno o perdita di oggi di tutto il conto.' })));
      if (!list.length) {
        fill(cards, h('section', { class: 'card' }, empty('Nessuna strategia nello snapshot', 'Il motore non ha ancora pubblicato le strategie.')));
        return;
      }
      const shares = list.flatMap((s) => [num(s.allocation), num(s.exposure)]).filter((v) => v != null).map(Math.abs);
      const sharpes = list.flatMap((s) => [num(s.sharpe_live), num(s.sharpe_backtest)]).filter((v) => v != null);
      const scale = {
        now: ctx.now,
        maxShare: Math.max(0.0001, ...shares),
        shMin: Math.min(0, ...sharpes),
        shMax: Math.max(1.5, ...sharpes) * 1.05,
      };
      fill(cards, list.map((s) => strategyCard(s, scale)));
    },
    summary(c) {
      const all = arr(c.snap.strategies);
      if (!all.length) return 'Lo snapshot non elenca strategie.';
      const act = all.filter((s) => str(s.status).toLowerCase() === 'active').length;
      const day = all.filter((s) => num(s.pnl_day_pct) != null).sort((a, b) => num(b.pnl_day_pct) - num(a.pnl_day_pct));
      const best = day[0];
      const worst = day[day.length - 1];
      return `${act} ${act === 1 ? 'strategia' : 'strategie'} su ${all.length} ${act === 1 ? 'è attiva' : 'sono attive'}${best && worst && best !== worst ? `; oggi la migliore è ${str(best.id)} (${fmtPct(best.pnl_day_pct, 2, { signed: true })}) e la più debole ${str(worst.id)} (${fmtPct(worst.pnl_day_pct, 2, { signed: true })})` : ''}.`;
    },
  };
}
