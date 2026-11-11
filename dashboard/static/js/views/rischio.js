// Rischio: stato e motivo, VaR/ES, volatilità contro l'obiettivo, limiti, scala del drawdown, comando KILL.

import { h, icon, fill } from '../dom.js';
import { card, chip, dataTable, empty, explain, stat } from '../components.js';
import { term } from '../glossary.js';
import { bullet } from '../charts.js';
import { DASH, arr, fmtDayTime, fmtMoney, fmtNum, fmtPct, fmtUnit, num, obj, parseTs, str } from '../format.js';
import { limitStatus, riskState, utilization } from '../model.js';
import { openKill } from '../kill.js';

export function mount(root, api) {
  let ctx = null;
  let killKey = null;

  const stateCard = h('section', { class: 'card riskstate span-12', 'aria-label': 'Stato del rischio' });

  const limitsCard = card({ title: 'Limiti', sub: 'Utilizzo = valore / soglia. Sopra il 100% il limite è superato.', cls: 'span-8', flush: true, what: 'I paletti che il conto non deve superare. Per ognuno: il valore di adesso, la soglia e quanta parte della soglia è già usata. «Nei limiti» è tranquillo, «Attenzione» vuol dire oltre l\'80% circa, «Superato» fa intervenire il motore.', method: 'Utilizzo = |valore| / |soglia|; i limiti di perdita hanno valore e soglia negativi. Lo stato lo assegna il motore, non la pagina.' });
  const limitsTable = dataTable({
    caption: 'Limiti di rischio con valore, soglia, utilizzo e stato',
    emptyTitle: 'Nessun limite nello snapshot',
    columns: [
      { key: 'name', label: 'Limite', sort: (r) => str(r.name), cell: (r) => str(r.name) },
      { key: 'value', label: 'Valore', num: true, cell: (r) => (num(r.value) == null ? null : fmtUnit(r.value, r.unit)) },
      { key: 'limit', label: 'Soglia', num: true, hide: 'sm', cell: (r) => (num(r.limit) == null ? null : fmtUnit(r.limit, r.unit)) },
      {
        key: 'use', label: 'Utilizzo', num: true, cls: 'is-weight', sort: (r) => utilization(r.value, r.limit),
        cell: (r) => {
          const u = utilization(r.value, r.limit);
          if (u == null) return null;
          const info = limitStatus(r.status);
          return h('div', { class: 'weight weight--wide' },
            bullet({ ratio: u, kind: info.kind, label: `Utilizzo del limite ${str(r.name)}`, text: `${fmtPct(u, 0)} della soglia` }),
            h('span', { class: 'weight__value', text: fmtPct(u, 0) }));
        },
      },
      { key: 'status', label: 'Stato', sort: (r) => ({ breach: 0, warn: 1, ok: 2 }[str(r.status).toLowerCase()] ?? 3), cell: (r) => chip(limitStatus(r.status), { compact: true }) },
    ],
  });
  limitsCard.body.append(limitsTable.el);

  const ladderCard = card({ title: 'Scala del drawdown', sub: 'Che cosa fa il motore a ogni soglia di perdita dal massimo', cls: 'span-4', what: 'Se il conto scende dal suo massimo, il motore non aspetta: a ogni scalino riduce l\'esposizione, fino a chiudere tutto. Il pallino blu è dove siamo adesso; «mancano X punti» dice quanto dista lo scalino successivo.' });
  const levCard = card({
    title: 'Leva del trade e leva del conto', cls: 'span-12',
    what: 'Sono due cose diverse. La leva del trade riguarda una sola operazione e il margine che il broker chiede; la leva del conto riguarda tutto il patrimonio ed è quella che decide quanto si può perdere.',
    method: 'Vincoli del piano di trade (gerva/risk/tradeplan.py): stop prima della liquidazione (distanza stop ≤ 0,6 × distanza di liquidazione), leva del trade ≤ tetto di legge dello strumento, rischio per operazione fissato dal livello di conviction.',
  });

  const killCard = h('section', { class: 'card killzone span-12', 'aria-labelledby': 'killzone-title' });

  root.append(h('div', { class: 'grid' }, stateCard, limitsCard.el, ladderCard.el, levCard.el, killCard));
  let levKey = null;

  function fillState() {
    const { snap, ccy } = ctx;
    const risk = obj(snap.risk);
    const nav = obj(snap.nav);
    const st = riskState(risk);
    const eq = num(nav.equity);
    const v = num(risk.var_95_1d_pct);
    const es = num(risk.es_95_1d_pct);
    const vol = num(risk.vol_realized_30d);
    const target = num(risk.vol_target);
    const inMoney = (pct) => (pct == null || eq == null ? null : `≈ ${fmtMoney(Math.abs(pct) * eq, ccy, { digits: 0 })} sul patrimonio di oggi`);
    const volUse = utilization(vol, target);
    fill(stateCard,
      h('div', { class: 'riskstate__main' },
        h('div', { class: 'riskstate__label', text: 'Stato del motore di rischio' }),
        h('span', { class: `pill pill--xl pill--${st.kind}` }, icon(st.icon), h('span', { text: st.label })),
        h('p', { class: 'riskstate__reason', text: str(risk.state_reason) || st.text || 'Stato non presente nello snapshot.' }),
        st.text && str(risk.state_reason) ? h('p', { class: 'riskstate__meaning', text: st.text }) : null,
        st.light ? explain(`${st.light}. Verde: tutto regolare. Giallo: esposizione dimezzata. Arancione: esposizione al minimo. Rosso: tutto chiuso (KILL).`) : null),
      h('div', { class: 'riskstate__stats' },
        stat({ label: 'VaR 95% a 1 giorno', value: v == null ? null : fmtPct(Math.abs(v), 2), sub: inMoney(v), hint: 'Perdita di giornata che ci si aspetta di superare un giorno su venti', explain: 'Il VaR: in 19 giorni su 20 la perdita di giornata resta sotto questa cifra.' }),
        stat({ label: 'ES 95% a 1 giorno', value: es == null ? null : fmtPct(Math.abs(es), 2), sub: inMoney(es), hint: 'Perdita media nei giorni peggiori (il 5% dei casi)', explain: 'La perdita media nel giorno storto su venti: dice quanto fa male quando va male.' }),
        stat({
          label: 'Volatilità realizzata 30g', value: vol == null ? null : fmtPct(vol, 1), cls: 'stat--meter',
          sub: target == null ? null : [
            bullet({ ratio: volUse, kind: 'ok', label: 'Volatilità realizzata rispetto all\'obiettivo', text: `${fmtPct(volUse, 0)} dell'obiettivo` }),
            h('span', { text: `obiettivo ${fmtPct(target, 1)}${volUse == null ? '' : ` · ${fmtPct(volUse, 0)}`}` }),
          ],
          explain: 'La volatilità dell\'ultimo mese confrontata con l\'obiettivo: se la barra è piena il conto oscilla quanto previsto.',
        }),
        stat({
          label: 'Drawdown dal massimo', value: num(nav.drawdown_pct) == null ? null : fmtPct(nav.drawdown_pct, 2),
          sub: num(nav.max_drawdown_pct) == null ? null : `peggiore di sempre ${fmtPct(nav.max_drawdown_pct, 2)}`,
          explain: 'Il drawdown: quanto siamo sotto il massimo. È la grandezza su cui scattano gli scalini qui sotto.',
        })));
  }

  function fillLadder() {
    const { snap } = ctx;
    const dd = num(obj(snap.nav).drawdown_pct);
    const steps = arr(obj(snap.risk).dd_ladder)
      .map((s) => ({ level: num(s.level), action: str(s.action), hit: s.hit === true }))
      .filter((s) => s.level != null)
      .sort((a, b) => Math.abs(a.level) - Math.abs(b.level));
    if (!steps.length) {
      fill(ladderCard.body, empty('Nessuna scala definita', 'Lo snapshot non riporta soglie di drawdown.'));
      return;
    }
    const deepest = Math.abs(steps[steps.length - 1].level) || 1;
    const depth = dd == null ? null : Math.min(1, Math.abs(Math.min(dd, 0)) / deepest);
    const anyHit = steps.some((s) => s.hit);
    const track = h('div', { class: 'ladder__track', 'aria-hidden': 'true' },
      h('span', { class: `ladder__fill ${anyHit ? 'ladder__fill--hit' : ''}`.trim(), style: { width: `${((depth ?? 0) * 100).toFixed(1)}%` } }),
      steps.map((s) => h('span', { class: `ladder__tick ${s.hit ? 'ladder__tick--hit' : ''}`.trim(), style: { left: `${(Math.abs(s.level) / deepest * 100).toFixed(1)}%` } })));
    const now = h('li', { class: 'ladder__now' },
      h('span', { class: 'ladder__marker ladder__marker--now', 'aria-hidden': 'true' }),
      h('span', { class: 'ladder__level num', text: dd == null ? DASH : fmtPct(dd, 2) }),
      h('span', { class: 'ladder__action', text: 'Drawdown attuale' }));
    const items = [];
    let placed = false;
    for (const s of steps) {
      if (!placed && !s.hit) {
        items.push(now);
        placed = true;
      }
      const gap = dd == null ? null : Math.abs(s.level) - Math.abs(Math.min(dd, 0));
      items.push(h('li', { class: `ladder__step ${s.hit ? 'ladder__step--hit' : ''}`.trim() },
        h('span', { class: 'ladder__marker', 'aria-hidden': 'true' }),
        h('span', { class: 'ladder__level num', text: fmtPct(s.level, 0) }),
        h('span', { class: 'ladder__action' }, s.action || DASH,
          h('span', { class: 'ladder__gap' }, s.hit
            ? chip({ label: 'Scattato', kind: 'crit', icon: 'crit' })
            : (gap == null ? '' : `mancano ${fmtNum(gap * 100, 1)} punti`)))));
    }
    if (!placed) items.push(now);
    fill(ladderCard.body, track, h('ol', { class: 'ladder' }, items));
  }

  function fillLeverage() {
    const dec = obj(obj(ctx.quant).leverage_decision);
    const caps = obj(dec.legal_max);
    const ccy = ctx.ccy;
    const key = JSON.stringify([dec, ccy]);
    if (key === levKey) return;
    levKey = key;
    const money = (v) => fmtMoney(v, ccy, { digits: 0 });
    const names = { indici: 'Indici', cambi: 'Cambi', azioni: 'Azioni', crypto: 'Crypto' };
    const step = (n, label, value, note) => h('li', { class: 'steps__item' }, h('span', { class: 'steps__n num', text: String(n) }),
      h('div', { class: 'steps__body' }, h('span', { class: 'steps__label', text: label }), h('strong', { class: 'steps__value num', text: value }), h('span', { class: 'steps__note', text: note })));
    fill(levCard.body, h('div', { class: 'levex' },
      h('div', { class: 'levex__example' },
        h('h3', { class: 'subhead', text: 'Un esempio con i numeri' }),
        h('ol', { class: 'steps' },
          step(1, 'Conto', money(12000), 'il patrimonio'),
          step(2, 'Rischio accettato', money(120), '1% del conto: il massimo che questa operazione può perdere'),
          step(3, 'Stop', '2%', 'se il prezzo va contro del 2% si esce'),
          step(4, 'Controvalore', money(6000), '120 ÷ 2%: quanto si può comprare perché lo stop costi 120'),
          step(5, 'Margine a 20x', money(300), '6.000 ÷ 20: il denaro bloccato dal broker'))),
      h('div', { class: 'levex__result' },
        h('div', { class: 'levex__pair' },
          h('div', { class: 'levex__box' }, h('span', { class: 'levex__label' }, term('leva-trade', 'Leva del trade')), h('strong', { class: 'levex__value num', text: '20x' }), h('span', { class: 'levex__note', text: 'controvalore 6.000 ÷ margine 300' })),
          h('div', { class: 'levex__box levex__box--main' }, h('span', { class: 'levex__label' }, term('leva-conto', 'Leva del conto')), h('strong', { class: 'levex__value num', text: '0,5x' }), h('span', { class: 'levex__note', text: 'controvalore 6.000 ÷ conto 12.000' }))),
        h('p', { class: 'levex__moral', text: 'Stessa operazione, due numeri molto diversi. Il conto rischia 120 in entrambi i casi: la leva del trade alta serve solo a bloccare meno denaro, non a rischiare di più.' }),
        num(dec.operativa) != null || Object.keys(caps).length ? h('div', { class: 'levex__caps' },
          num(dec.operativa) != null ? h('p', null, 'Leva del conto del fondo: ', h('strong', { class: 'num', text: `${fmtNum(dec.operativa, 0)}x operativa` }), ', ', h('strong', { class: 'num', text: `${fmtNum(dec.tetto, 0)}x tetto` }), '.') : null,
          Object.keys(caps).length ? h('p', null, 'Tetti di legge alla leva del trade (cliente al dettaglio UE): ',
            Object.entries(caps).map(([k, v], i) => h('span', { class: 'levex__cap' }, i ? ' · ' : '', `${names[k] || k} `, h('strong', { class: 'num', text: `${fmtNum(v, 0)}x` })))) : null)
          : h('p', { class: 'muted', text: 'I tetti di legge compaiono quando è disponibile il file della ricerca.' }))));
  }

  function fillKill() {
    const hl = obj(ctx.health);
    const enabled = hl.kill_enabled !== false;          // se /health non ha ancora risposto si lascia provare
    const active = hl.kill_active === true;
    const done = api.killResult();
    const key = JSON.stringify([enabled, active, done]);
    if (key === killKey) return;                         // niente ridisegno a vuoto: il pulsante conserva il focus
    killKey = key;
    const btn = h('button', { class: 'btn btn--danger', type: 'button', disabled: !enabled || active }, icon('power'), h('span', { text: active ? 'KILL già attivo' : 'Attiva KILL…' }));
    btn.addEventListener('click', () => openKill());
    fill(killCard,
      h('div', { class: 'killzone__text' },
        h('h2', { class: 'killzone__title', id: 'killzone-title' }, icon('power'), h('span', { text: 'Arresto di emergenza' })),
        h('p', { text: 'Crea il file KILL sul server: al ciclo successivo il motore chiude tutte le posizioni e si ferma. È un comando a senso unico: da questa pagina non si può togliere.' }),
        active ? h('p', { class: 'killzone__state killzone__state--on' }, icon('crit'), h('span', { text: 'File KILL presente sul server. Per ripartire va rimosso a mano e va dato il comando di ripristino.' })) : null,
        !enabled ? h('p', { class: 'killzone__state' }, icon('off'), h('span', { text: 'Comando disabilitato: sul server non è impostato GERVA_DASH_TOKEN.' })) : null,
        done ? h('p', { class: `killzone__state ${done.ok ? 'killzone__state--on' : ''}`.trim(), role: 'status' }, icon(done.ok ? 'check-circle' : 'warn'),
          h('span', { text: done.ok
            ? `${done.already ? 'Il file KILL era già presente' : 'File KILL creato'} (richiesta delle ${fmtDayTime(parseTs(done.t) ?? Date.now())}).`
            : `Ultimo tentativo non riuscito: ${done.error}` })) : null),
      h('div', { class: 'killzone__action' }, btn,
        h('p', { class: 'killzone__hint', text: 'Chiede il token e la parola KILL prima di inviare.' })));
  }

  return {
    update(next) {
      ctx = next;
      fillState();
      limitsTable.render(arr(obj(ctx.snap.risk).limits));
      fillLadder();
      fillLeverage();
      fillKill();
    },
    summary(c) {
      const risk = obj(c.snap.risk);
      const st = riskState(risk);
      const near = arr(risk.limits).map((l) => ({ l, u: utilization(l.value, l.limit) })).filter((x) => x.u != null).sort((a, b) => b.u - a.u)[0];
      if (!st.code) return 'Lo snapshot non riporta lo stato del rischio.';
      return `${st.light || st.label}: ${st.text.charAt(0).toLowerCase()}${st.text.slice(1).replace(/\.$/, '')}${near ? `; il limite più vicino alla soglia è «${str(near.l.name)}», usato al ${fmtPct(near.u, 0)}` : ''}.`;
    },
  };
}
