// AI: regime di mercato, conviction di oggi, overlay in vigore. Il livello AI può solo ridurre o vietare.

import { h, icon, fill } from '../dom.js';
import { card, chip, empty, explain, method } from '../components.js';
import { bullet } from '../charts.js';
import { DASH, arr, fmtDayTime, fmtDuration, fmtNum, fmtPct, fmtUnit, num, obj, parseTs, str } from '../format.js';
import { isBacktest } from '../model.js';

const REGIMES = [
  { id: 'calmo', label: 'Calmo', kind: 'ok', text: 'Mercati tranquilli: nessun segnale di tensione acceso.' },
  { id: 'normale', label: 'Normale', kind: 'ok', text: 'Un segnale di tensione acceso su quattro: condizioni ordinarie.' },
  { id: 'teso', label: 'Teso', kind: 'warn', text: 'Due segnali di tensione accesi: volatilità sopra il normale, più attenzione.' },
  { id: 'crisi', label: 'Crisi', kind: 'crit', text: 'Tre o più segnali accesi: condizioni da crisi di mercato.' },
];
const INDEX_ASSETS = new Set(['SPY', 'QQQ', 'SPX', 'NDX']);
const thresholds = (asset) => (INDEX_ASSETS.has(str(asset).toUpperCase()) ? [0.55, 0.82] : [0.30, 0.60]);
const TIERS = {
  bassa: { label: 'Bassa', kind: 'muted', icon: 'off' },
  media: { label: 'Media', kind: 'accent', icon: 'check' },
  alta: { label: 'Alta', kind: 'ok', icon: 'check-circle' },
};

export function mount(root) {
  const rule = h('section', { class: 'card rulecard span-12', 'aria-label': 'Che cosa può fare il livello AI' },
    icon('risk', 'icon--xl rulecard__icon'),
    h('div', { class: 'rulecard__body' },
      h('h2', { class: 'rulecard__title', text: 'L\'AI può solo ridurre o vietare; il motore di rischio decide per ultimo' }),
      h('ul', { class: 'rulecard__list' },
        h('li', null, icon('check'), h('span', { text: 'Può abbassare l\'esposizione di una strategia (moltiplicatore tra 0 e 1) o metterla in pausa, citando le fonti.' })),
        h('li', null, icon('x'), h('span', { text: 'Non può aumentare un\'esposizione, scegliere le operazioni o toccare i limiti di rischio.' })),
        h('li', null, icon('clock'), h('span', { text: 'Ogni riduzione ha una scadenza: se non viene rinnovata, decade da sola.' })))));

  const regimeCard = card({
    title: 'Regime di mercato', cls: 'span-5',
    what: 'Una fotografia del «clima» dei mercati, da calmo a crisi. Si ricava da quattro misure note la sera prima (paura sul mercato azionario, forma della curva della volatilità, oscillazioni recenti del portafoglio, tendenza di Bitcoin): ogni misura in allarme vale un punto.',
    method: 'Classificatore deterministico (gerva/ai/regime.py): VIX sopra la mediana a un anno, VIX/VIX3M > 1, volatilità realizzata a 20 giorni sopra l\'80° percentile, BTC sotto la media a 100 giorni. Punteggio 0 → calmo, 1 → normale, 2 → teso, ≥ 3 → crisi.',
  });
  const convCard = card({
    title: 'Conviction di oggi', cls: 'span-7',
    what: 'Per ogni strumento, quanti segnali sono d\'accordo in questo momento, da 0 a 1. Le due tacche dividono la barra in tre zone: bassa, media, alta. Più alta la zona, più rischio è ammesso su una singola operazione. Non è la probabilità di guadagnare.',
    method: 'Score = quota di segnali binari accesi. Soglie: crypto 0,30 / 0,60; indici 0,55 / 0,82. Rischio per operazione: 0 (bassa), 0,5% (media), 1% (alta) del patrimonio.',
  });
  const overlayCard = card({
    title: 'Overlay in vigore', cls: 'span-12',
    what: 'Le riduzioni che il livello AI sta applicando adesso. Una barra piena (100%) vuol dire nessuna riduzione; al 50% l\'esposizione di quella strategia è dimezzata; a 0% la strategia è vietata fino alla scadenza.',
    method: 'L\'overlay AI unisce desk LLM, regime e decadimento; il moltiplicatore finale di una strategia è globale × strategia, applicato ai pesi obiettivo prima del motore di rischio.',
  });
  const gatesCard = card({ title: 'Requisiti per attivare il livello AI', cls: 'span-12' });
  const none = h('section', { class: 'card span-12' });
  root.append(h('div', { class: 'grid' }, rule, none, regimeCard.el, convCard.el, overlayCard.el, gatesCard.el));

  function fillRegime(ai) {
    const r = ai.regime;
    if (!r || typeof r !== 'object') {
      fill(regimeCard.body, empty('Regime non calcolato', 'Il classificatore non ha ancora pubblicato uno stato.'));
      return;
    }
    const idx = REGIMES.findIndex((x) => x.id === str(r.stato).toLowerCase());
    const cur = REGIMES[idx];
    const score = num(r.punteggio);
    fill(regimeCard.body,
      h('ol', { class: 'regime', 'aria-label': 'Scala del regime, dal più tranquillo al più teso' }, REGIMES.map((x, i) => h('li', {
        class: `regime__step ${i === idx ? `is-on regime__step--${x.kind}` : ''}`.trim(), 'aria-current': i === idx ? 'true' : null,
      }, h('span', { class: 'regime__bar' }), h('span', { class: 'regime__label', text: x.label })))),
      h('div', { class: 'regime__now' },
        cur ? chip({ label: `Oggi: ${cur.label.toLowerCase()}`, kind: cur.kind, icon: cur.kind === 'ok' ? 'check' : cur.kind === 'warn' ? 'warn' : 'crit' }) : chip({ label: str(r.stato) || 'Stato sconosciuto', kind: 'muted', icon: 'info' }),
        h('span', { class: 'regime__score' }, 'Punteggio ', h('strong', { class: 'num', text: score == null ? DASH : `${fmtNum(score, 0)} su 4` }))),
      h('p', { class: 'regime__text', text: cur ? cur.text : '' }),
      h('p', { class: 'regime__effect' }, icon(r.scala_esposizione === true ? 'warn' : 'info'),
        h('span', { text: r.scala_esposizione === true
          ? 'In questo momento il regime riduce l\'esposizione del portafoglio.'
          : 'Il regime è solo informativo: non riduce l\'esposizione. Nella ricerca, usarlo per ridurre ha peggiorato il risultato.' })));
  }

  function fillConviction(ai, risk) {
    const rows = arr(ai.conviction);
    if (!rows.length) {
      fill(convCard.body, empty('Nessuna conviction calcolata', 'Compare quando il ciclo ha i segnali di giornata degli strumenti seguiti.'));
      return;
    }
    const riskOf = { bassa: 0, media: num(risk.media) ?? 0.005, alta: num(risk.alta) ?? 0.01 };
    fill(convCard.body, h('ul', { class: 'convs' }, rows.map((c) => {
      const sc = num(c.score);
      const [lo, hi] = thresholds(c.asset);
      const lv = str(c.livello).toLowerCase();
      const tier = TIERS[lv] || { label: str(c.livello) || DASH, kind: 'muted', icon: 'info' };
      return h('li', { class: 'conv' },
        h('span', { class: 'code code--strong conv__asset', text: str(c.asset) || DASH }),
        h('div', { class: 'conv__gauge', role: 'img', 'aria-label': `Conviction di ${str(c.asset)}: ${sc == null ? 'non disponibile' : fmtNum(sc, 2)}, livello ${tier.label.toLowerCase()}; soglie ${fmtNum(lo, 2)} e ${fmtNum(hi, 2)}` },
          h('span', { class: 'conv__track' },
            sc == null ? null : h('span', { class: `conv__fill conv__fill--${lv}`, style: { width: `${(Math.min(1, Math.max(0, sc)) * 100).toFixed(1)}%` } }),
            h('span', { class: 'conv__tick', style: { left: `${lo * 100}%` } }), h('span', { class: 'conv__tick', style: { left: `${hi * 100}%` } })),
          h('span', { class: 'conv__zones', 'aria-hidden': 'true' },
            h('span', { style: { width: `${lo * 100}%` }, text: 'bassa' }), h('span', { style: { width: `${(hi - lo) * 100}%` }, text: 'media' }), h('span', { style: { width: `${(1 - hi) * 100}%` }, text: 'alta' }))),
        h('span', { class: 'conv__score num', text: sc == null ? DASH : fmtNum(sc, 2) }),
        chip(tier),
        h('span', { class: 'conv__risk' }, 'rischio per operazione ', h('strong', { class: 'num', text: riskOf[lv] == null ? DASH : fmtPct(riskOf[lv], 1) })));
    })),
    explain('Con conviction bassa su uno strumento non si aprono operazioni a leva su quello strumento; il portafoglio delle quattro strategie continua comunque a seguire le sue regole.'));
  }

  function fillOverlay(ai, snap, now) {
    const ov = ai.overlay;
    if (!ov || typeof ov !== 'object') {
      fill(overlayCard.body, empty('Nessun overlay pubblicato', 'Il livello AI non ha consegnato nulla al ciclo: le strategie girano senza riduzioni.'));
      return;
    }
    const glob = num(ov.globale);
    const per = arr(ov.strategie);
    const ids = [...new Set([...arr(snap.strategies).map((x) => str(x.id)), ...per.map((x) => str(x.id))])].filter(Boolean);
    const cut = per.filter((x) => num(x.mult) != null && num(x.mult) < 1);
    const active = (glob != null && glob < 1) || cut.length > 0;
    const exp = parseTs(ov.scade);
    const left = exp == null ? null : (exp - now) / 1000;
    const bar = (m, label) => h('div', { class: 'ovl__bar' },
      bullet({ ratio: m, kind: m == null ? 'muted' : m <= 0 ? 'crit' : m < 1 ? 'warn' : 'ok', label, text: m == null ? '' : fmtPct(m, 0) }),
      h('span', { class: 'num ovl__mult', text: m == null ? DASH : fmtPct(m, 0) }));
    fill(overlayCard.body,
      h('div', { class: 'ovl__head' },
        chip(ov.valido === false ? { label: 'Overlay non valido: ignorato', kind: 'crit', icon: 'crit' }
          : active ? { label: 'Riduzione in vigore', kind: 'warn', icon: 'warn' } : { label: 'Nessuna riduzione in vigore', kind: 'ok', icon: 'check' }),
        h('span', { class: 'ovl__expiry' }, icon('clock'),
          h('span', { class: 'num', text: exp == null ? 'senza scadenza' : left > 0 ? `scade tra ${fmtDuration(left)} (${fmtDayTime(exp)})` : `scaduto il ${fmtDayTime(exp)}` })),
        str(ov.nota).trim() ? h('span', { class: 'ovl__note', text: `Nota: ${str(ov.nota)}` }) : null),
      h('ul', { class: 'ovl' },
        h('li', { class: 'ovl__row ovl__row--global' },
          h('span', { class: 'ovl__name', text: 'Tutto il portafoglio' }), bar(glob, 'Moltiplicatore globale'),
          h('span', { class: 'ovl__why', text: str(ov.motivo_globale).trim() || (glob != null && glob < 1 ? 'Motivo non indicato.' : 'Nessuna riduzione globale.') })),
        ids.map((id) => {
          const o = per.find((x) => str(x.id) === id);
          const m = o ? num(o.mult) : 1;
          const fonti = o && Array.isArray(o.fonti) ? o.fonti.map(str).filter(Boolean) : [];
          return h('li', { class: 'ovl__row' },
            h('span', { class: 'ovl__name' }, h('span', { class: 'code code--strong', text: id })), bar(m, `Moltiplicatore di ${id}`),
            h('span', { class: 'ovl__why' }, o ? (str(o.motivo).trim() || 'Motivo non indicato.') : 'Nessuna riduzione.',
              fonti.length ? h('span', { class: 'ovl__sources' }, 'Fonti: ', fonti.map((f) => h('span', { class: 'code ovl__source', text: f }))) : null));
        })),
      explain('100% = la strategia lavora con tutta la sua quota. Il moltiplicatore finale è quello globale per quello della strategia; poi il motore di rischio può ridurre ancora, mai aumentare.'),
      method('Un overlay non valido (formato errato, moltiplicatori fuori da [0, 1], scaduto) viene ignorato: il ciclo prosegue senza riduzioni e lo segnala negli avvisi.'));
  }

  function fillGates(ai) {
    const gates = arr(ai.gates).concat(arr(ai.cancelli));
    gatesCard.el.hidden = !gates.length;
    if (!gates.length) return;
    fill(gatesCard.body, h('ul', { class: 'gates gates--cols' }, gates.map((g) => {
      const ok = g.ok === true;
      return h('li', { class: `gate ${ok ? 'gate--ok' : ''}`.trim() }, icon(ok ? 'check-circle' : 'circle', 'gate__icon'),
        h('div', { class: 'gate__body' }, h('div', { class: 'gate__name', text: str(g.name || g.nome) || DASH }),
          h('div', { class: 'gate__figures' }, h('span', { class: 'num gate__value', text: num(g.value) == null ? 'da calcolare' : fmtUnit(g.value, g.unit) }),
            h('span', { class: 'gate__target' }, 'soglia ', h('span', { class: 'num', text: num(g.target) == null ? DASH : fmtUnit(g.target, g.unit) })))));
    })));
  }

  return {
    update(ctx) {
      const ai = ctx.snap.ai;
      const has = ai && typeof ai === 'object' && !Array.isArray(ai);
      none.hidden = has;
      for (const c of [regimeCard, convCard, overlayCard]) c.el.hidden = !has;
      if (!has) {
        gatesCard.el.hidden = true;
        fill(none, empty('Il livello AI non ha pubblicato dati', isBacktest(ctx.snap.meta)
          ? 'In backtest il livello AI non gira: regime, conviction e overlay compaiono in paper e in live.'
          : 'Lo snapshot non contiene il blocco «ai». Le strategie girano senza riduzioni dell\'AI.'));
        return;
      }
      fillRegime(ai);
      fillConviction(ai, obj(obj(obj(ctx.quant).leverage_decision).rischio_trade));
      fillOverlay(ai, ctx.snap, ctx.now);
      fillGates(ai);
    },
    summary(ctx) {
      const ai = obj(ctx.snap.ai);
      if (!ctx.snap.ai) return 'In questo snapshot il livello AI non ha pubblicato dati: le strategie girano senza riduzioni dell\'AI.';
      const reg = REGIMES.find((x) => x.id === str(obj(ai.regime).stato).toLowerCase());
      const ov = obj(ai.overlay);
      const cut = arr(ov.strategie).filter((x) => num(x.mult) != null && num(x.mult) < 1).length + (num(ov.globale) != null && num(ov.globale) < 1 ? 1 : 0);
      const conv = arr(ai.conviction).map((c) => `${str(c.asset)} ${str(c.livello)}`).join(', ');
      return `${reg ? `Il mercato è in regime ${reg.label.toLowerCase()}` : 'Il regime di mercato non è disponibile'}; ${cut ? `l'AI sta riducendo l'esposizione in ${cut} ${cut === 1 ? 'punto' : 'punti'}` : 'nessuna riduzione dell\'AI è in vigore'}${conv ? `; conviction di oggi: ${conv}` : ''}.`;
    },
  };
}
