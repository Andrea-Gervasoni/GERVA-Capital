// Apprendimento: il ciclo con cui il fondo studia i propri trade, propone correzioni e le fa validare.
// Sola lettura: qui non c'è, e non deve esserci, alcun comando che attivi una regola. Si attiva solo da terminale.

import { h, icon, fill } from '../dom.js';
import { card, chip, dataTable, empty, explain, method, stat } from '../components.js';
import { bullet, signedBars } from '../charts.js';
import { flowDiagram } from '../flow.js';
import { DASH, arr, fmtNum, fmtPct, fmtSigned, num, obj, str } from '../format.js';
import { gloss } from '../glossary.js';

const STEPS = [
  { id: 'memoria', title: 'Memoria dei trade', sub: 'tutto annotato', file: 'gerva/learn/memory.py',
    plain: 'Ogni trade chiuso viene annotato con il suo contesto: prezzi, stop, costi, motivo dell\'uscita e quanto è andato in perdita e in guadagno mentre era aperto (MAE / MFE). Senza memoria non si impara nulla.' },
  { id: 'valutazione', title: 'Valutazione', sub: 'dove si perde', file: 'gerva/learn/evaluate.py',
    plain: 'Il sistema misura come stanno andando i trade e cerca le «fette» (un giorno della settimana, un livello di volatilità…) in cui rendono chiaramente meno del resto.' },
  { id: 'ipotesi', title: 'Ipotesi', sub: 'una correzione proposta', file: 'gerva/learn/improve.py · propose',
    plain: 'Da ogni debolezza nasce una regola semplice e leggibile: «se accade X, salta il trade» oppure «dimezzalo». Proporre è facile, ed è giusto che lo sia: il difficile viene dopo.' },
  { id: 'validazione', title: 'Validazione', sub: 'sei controlli', file: 'gerva/learn/improve.py · validate', guard: true,
    plain: 'Un validatore separato da chi propone, sempre uguale e non modificabile da un agente, sottopone la regola a sei controlli: in campione, fuori campione, walk-forward e robustezza. Quasi tutte le regole vengono respinte: è il comportamento atteso.' },
  { id: 'ombra', title: 'Ombra', sub: 'osservata, non applicata', file: 'gerva/learn/improve.py · shadow',
    plain: 'Una regola che passa non agisce subito: resta in ombra. Sui nuovi trade del conto di prova si annota che cosa avrebbe fatto, senza toccare nulla, finché non ci sono abbastanza casi per giudicarla.' },
  { id: 'approvazione', title: 'Approvazione di Andrea', sub: 'solo a mano', file: 'python -m gerva learn --approve ID --confirm', guard: true,
    plain: 'Una regola che regge anche in ombra diventa «promuovibile», ma non si attiva da sola: serve un comando esplicito del proprietario, da terminale. Questa pagina non può farlo.' },
  { id: 'attiva', title: 'Attiva', sub: 'salta o dimezza', file: 'gerva/learn/improve.py · multiplier',
    plain: 'Da quel momento la regola agisce sui nuovi trade: li salta o ne dimezza la taglia. Non può fare altro. I nuovi trade tornano nella memoria e il ciclo ricomincia.' },
];

const STATES = {
  RESPINTA: { label: 'Respinta', kind: 'muted', icon: 'x' },
  IN_OMBRA: { label: 'In ombra', kind: 'accent', icon: 'clock' },
  PROMUOVIBILE: { label: 'Promuovibile', kind: 'warn', icon: 'warn' },
  ATTIVA: { label: 'Attiva', kind: 'ok', icon: 'check' },
  RITIRATA: { label: 'Ritirata', kind: 'muted', icon: 'off' },
};
const stateOf = (v) => STATES[str(v).toUpperCase()] || { label: str(v) || DASH, kind: 'muted', icon: 'info' };

const CHECKS = [
  { key: 'numerosita', label: 'Colpisce abbastanza trade', hint: 'almeno 30 in campione e 15 fuori campione', find: /almeno|pochi|numeros/i },
  { key: 'quota', label: 'Non toglie troppi trade', hint: 'non più della metà', find: /quota|met[aà]'? dei trade|troppi/i },
  { key: 'in_campione', label: 'I trade colpiti perdono, in campione', hint: 'con una soglia statistica che sale a ogni ipotesi provata', find: /in scelta|in campione/i },
  { key: 'fuori_campione', label: 'Perdono anche fuori campione', hint: 'sui dati mai usati per cercare la regola', find: /in verifica|fuori campione/i },
  { key: 'walk_forward', label: 'Regge anno per anno (walk-forward)', hint: 'in almeno il 60% degli anni', find: /anni/i },
  { key: 'soglie_vicine', label: 'Non dipende dalla soglia esatta', hint: 'spostandola del 20% il risultato non cambia segno', find: /soglia del|spostando|vicin/i },
];

const DAYS = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica'];
const EXITS = { stop: 'Uscita allo stop', tempo: 'Uscita a tempo', target: 'Uscita al bersaglio', liquidazione: 'Liquidazione', manuale: 'Uscita manuale' };

/** Numeri lunghi del rapporto (0.07160833333333333) → cifre leggibili con la virgola. */
export function tidy(text) {
  return str(text).replace(/-?\d+\.\d+/g, (m) => {
    const v = Number(m);
    if (!Number.isFinite(v)) return m;
    const a = Math.abs(v);
    return fmtNum(v, a >= 10 ? 1 : a >= 0.1 ? 2 : 4, 0);
  });
}

/** Condizione in parole: {feature, op, value} oppure "atr_pct > 0.0716". */
export function plainSlice(feature, op, value) {
  const f = str(feature);
  const v = num(value);
  if (f === 'weekday' && v != null && DAYS[v]) return `Trade aperti di ${DAYS[v]}`;
  if (f === 'atr_pct' && v != null) return `Volatilità (ATR) ${op === '>' ? 'sopra' : 'fino a'} il ${fmtPct(v, 1)} del prezzo`;
  const words = { '>': 'sopra', '<=': 'fino a', '==': 'uguale a' };
  return `${f} ${words[op] || op} ${v == null ? str(value) : tidy(String(v))}`;
}

function parseCond(text) {
  const m = /^\s*(?:se\s+)?([\w.]+)\s*(<=|>|==|=)\s*(-?[\d.]+)/.exec(str(text));
  return m ? { feature: m[1], op: m[2] === '=' ? '==' : m[2], value: Number(m[3]) } : null;
}

/** "se atr_pct > 0.0716: salta il trade" → frase leggibile; se non si riconosce resta il testo ripulito. */
export function plainRule(text) {
  const c = parseCond(text);
  const act = /:\s*(.+)$/.exec(str(text));
  if (!c) return tidy(text);
  return `${plainSlice(c.feature, c.op, c.value)}${act ? ` → ${act[1].trim()}` : ''}`;
}

const rr = (v, d = 2) => (num(v) == null ? DASH : `${fmtSigned(v, d)} R`);

export function mount(root) {
  let ctx = null;
  let key = null;
  let selected = 'memoria';

  const head = h('div', { class: 'section-head span-12' });
  const missing = h('section', { class: 'card span-12' });

  const flowCard = card({
    title: 'Come impara', cls: 'span-12',
    sub: 'Sette passaggi in cerchio. Tocca un passaggio per leggerne la spiegazione.',
    what: 'Il fondo studia i propri trade, trova dove perde e propone correzioni. Ma chi propone non decide: ogni correzione passa da un validatore indipendente, poi da un periodo di sola osservazione, e infine dal proprietario. Dopo l\'ultimo passaggio i nuovi trade tornano al primo.',
  });
  const flowHost = h('div', { class: 'flow-host' });
  const detail = h('div', { class: 'flow-detail', 'aria-live': 'polite' });
  flowCard.body.append(flowHost, detail);
  const flow = flowDiagram(flowHost, STEPS, { label: 'Diagramma del ciclo di automiglioramento', initial: selected, onSelect: (id) => { selected = id; paintDetail(); } });

  const guard = h('section', { class: 'card rulecard span-12', 'aria-label': 'Le tre garanzie del ciclo' });

  const evalHead = h('div', { class: 'section-head span-12' });
  const evalAll = h('section', { class: 'card evalcard span-6' });
  const evalPaper = h('section', { class: 'card evalcard span-6' });
  const yearCard = card({
    title: 'R medio per anno', cls: 'span-6',
    what: 'Quanto ha reso in media un trade in ciascun anno, in R (1 R = ciò che il trade rischiava). Una barra verso destra è un anno in cui i trade hanno guadagnato in media; verso sinistra, perso. Conta che la maggior parte degli anni sia positiva, non che lo siano tutti.',
    method: 'Media di R per anno di ingresso; n = numero di trade dell\'anno. Anni con pochi trade sono poco indicativi.',
  });
  const exitCard = card({
    title: 'R medio per motivo di uscita', cls: 'span-6',
    what: 'I trade si chiudono per motivi diversi: allo stop (in perdita, circa −1 R meno i costi) oppure dopo il tempo previsto. Qui si vede quanto rende in media ciascun tipo di uscita e se il risultato recente è in linea con il passato.',
    method: 'recente contro passato: confronto tra gli ultimi trade e i precedenti, con la statistica t della differenza.',
  });

  const weakCard = card({
    title: 'Dove perde', cls: 'span-12', flush: true,
    what: 'Le «fette» di trade che rendono meno del resto: per esempio quelli aperti in un certo giorno o con molta volatilità. «Sospetta» vuol dire che la differenza c\'è ma potrebbe essere un caso; «significativa» che è abbastanza netta da meritare una regola. Trovare una fetta debole non basta: bisogna che superi la validazione.',
    method: 't = statistica t della differenza tra la fetta e il resto. Una fetta diventa ipotesi già a t ≤ −1,3; per passare la validazione serve molto di più.',
  });
  const weakTable = dataTable({
    caption: 'Fette di trade che rendono meno del resto',
    emptyTitle: 'Nessuna debolezza rilevata', emptyHint: 'Nessuna fetta di trade rende chiaramente meno delle altre.',
    columns: [
      { key: 'slice', label: 'Fetta di trade', cls: 'is-wrap is-name', sort: (r) => str(r.slice), cell: (r) => { const c = obj(r.rule).feature ? obj(r.rule) : parseCond(r.slice); return h('div', { class: 'cell-id cell-id--stack' }, h('span', { class: 'cell-id__main', text: c ? plainSlice(c.feature, c.op, c.value) : tidy(r.slice) }), h('span', { class: 'cell-id__name only-esperto code', text: tidy(r.slice) })); } },
      { key: 'n', label: 'Trade', num: true, sort: (r) => num(r.n), cell: (r) => (num(r.n) == null ? null : `${fmtNum(r.n, 0)}${num(r.share) == null ? '' : ` (${fmtPct(r.share, 0)})`}`) },
      { key: 'mean', label: 'R medio della fetta', num: true, sort: (r) => num(r.mean_R), cell: (r) => h('strong', { text: rr(r.mean_R) }) },
      { key: 'rest', label: 'R medio del resto', num: true, hide: 'sm', sort: (r) => num(r.rest_mean_R), cell: (r) => rr(r.rest_mean_R) },
      { key: 't', label: 't', num: true, cls: 'only-esperto', sort: (r) => num(r.t), cell: (r) => (num(r.t) == null ? null : fmtSigned(r.t, 2)) },
      { key: 'cost', label: 'R persi in tutto', num: true, cls: 'only-esperto', sort: (r) => num(r.cost_total_R), cell: (r) => (num(r.cost_total_R) == null ? null : `${fmtNum(r.cost_total_R, 1)} R`) },
      { key: 'level', label: 'Livello', sort: (r) => str(r.level), cell: (r) => chip(str(r.level).toLowerCase().startsWith('signif') ? { label: 'Significativa', kind: 'warn', icon: 'warn' } : { label: 'Sospetta', kind: 'muted', icon: 'info' }, { compact: true }) },
      { key: 'action', label: 'Che cosa si prova', cls: 'is-wrap', hide: 'md', blank: true, cell: (r) => str(r.action) },
    ],
  });
  weakCard.body.append(weakTable.el);

  const triedCard = card({
    title: 'Che cosa ha provato', cls: 'span-12',
    what: 'Le correzioni proposte e il verdetto del validatore. Apri una regola per vedere i sei controlli uno per uno. «Respinta» è l\'esito normale e sano: vuol dire che il sistema non si lascia convincere da una coincidenza.',
    method: 'Soglia in campione: t ≤ −√(2 ln K), mai sotto 2, con K = ipotesi provate fino a quel momento. Guadagno in R = R che la regola avrebbe aggiunto (negativo: avrebbe tolto trade buoni).',
  });
  const shadowCard = card({
    title: 'In ombra', cls: 'span-6',
    what: 'Regole che hanno superato la validazione sui dati storici e ora vengono solo osservate sui trade del conto di prova. La barra mostra quanti trade servono ancora prima di poterle giudicare.',
  });
  const activeCard = card({
    title: 'Attive', cls: 'span-6',
    what: 'Regole approvate dal proprietario e in funzione. Possono solo saltare un trade o dimezzarne la taglia.',
  });
  const regCard = card({ title: 'Registro delle ipotesi', cls: 'span-12 only-esperto', flush: true, sub: 'Ogni ipotesi provata resta qui per sempre: è il conteggio che alza la soglia.' });
  const regTable = dataTable({
    caption: 'Registro di tutte le ipotesi provate', emptyTitle: 'Registro vuoto',
    columns: [
      { key: 'id', label: 'ID', sort: (r) => str(r.id), cell: (r) => h('span', { class: 'code', text: str(r.id) || DASH }) },
      { key: 'rule', label: 'Regola', cls: 'is-wrap', sort: (r) => str(r.rule), cell: (r) => tidy(r.rule) },
      { key: 'state', label: 'Stato', sort: (r) => str(r.state), cell: (r) => chip(stateOf(r.state)) },
      { key: 'by', label: 'Verdetto di', sort: (r) => str(r.by), cell: (r) => str(r.by) },
      { key: 'origin', label: 'Proposta da', hide: 'sm', sort: (r) => str(r.origin), cell: (r) => str(r.origin) },
    ],
  });
  regCard.body.append(regTable.el);

  const cards = [flowCard, yearCard, exitCard, weakCard, triedCard, shadowCard, activeCard, regCard];
  root.append(h('div', { class: 'grid' }, head, missing, flowCard.el, guard, evalHead, evalAll, evalPaper, yearCard.el, exitCard.el, weakCard.el, triedCard.el, shadowCard.el, activeCard.el, regCard.el));

  const L = () => obj(ctx.learn);

  function paintDetail() {
    const i = STEPS.findIndex((x) => x.id === selected);
    const st = STEPS[i] || STEPS[0];
    fill(detail,
      h('div', { class: 'flow-detail__head' }, h('span', { class: 'flow-detail__n num', text: String(i + 1) }), h('h3', { class: 'flow-detail__title', text: st.title }),
        st.guard ? h('span', { class: 'tag tag--paper', text: 'decide qualcun altro' }) : null),
      h('p', { class: 'flow-detail__text' }, gloss(st.plain)),
      h('p', { class: 'flow-detail__file only-esperto' }, 'Codice: ', h('code', { text: st.file })));
  }

  function paintGuard() {
    const imp = obj(L().improvement);
    fill(guard, icon('risk', 'icon--xl rulecard__icon'), h('div', { class: 'rulecard__body' },
      h('h2', { class: 'rulecard__title', text: 'Tre garanzie che il codice fa rispettare' }),
      h('ol', { class: 'rules' },
        h('li', null, h('strong', { text: 'Chi propone non approva. ' }), 'Le ipotesi le genera il motore di valutazione; il verdetto lo dà solo il validatore, che è sempre lo stesso e non si può modificare. L\'attivazione spetta al proprietario.'),
        h('li', null, h('strong', { text: 'Una regola può solo saltare o dimezzare un trade. ' }), 'Non può aumentare rischio, leva o esposizione, né toccare stop e limiti.'),
        h('li', null, h('strong', { text: 'Ogni ipotesi provata alza la soglia per le successive. ' }),
          num(imp.tried) == null ? 'Cercare di più rende più difficile passare, non più facile.'
            : h('span', null, 'Finora ne sono state provate ', h('strong', { class: 'num', text: fmtNum(imp.tried, 0) }), ': la soglia attuale è ', h('strong', { class: 'num', text: `t ≤ −${fmtNum(imp.threshold_t, 2)}` }), '. Cercare di più rende più difficile passare, non più facile.')))));
  }

  function evalBlock(el, title, ev, { paper = false } = {}) {
    const n = num(ev.n);
    const p = obj(ev.performance);
    const k = obj(ev.risk);
    if (!n) {
      fill(el, h('header', { class: 'card__head' }, h('div', { class: 'card__titles' }, h('h2', { class: 'card__title', text: title }))),
        h('div', { class: 'card__body' }, empty(paper ? 'Nessun trade paper ancora' : 'Nessun trade in memoria',
          paper ? 'Per ora i numeri vengono dalle simulazioni storiche. Questa scheda si riempie con i trade del conto di prova.' : 'La memoria dei trade è vuota.')));
      return;
    }
    const src = Object.entries(obj(ev.by_source)).map(([s, v]) => `${fmtNum(obj(v).n, 0)} ${s === 'sim' ? 'simulati' : s}`).join(', ');
    fill(el, h('header', { class: 'card__head' }, h('div', { class: 'card__titles' },
      h('div', { class: 'card__title-row' }, h('h2', { class: 'card__title', text: title }), !paper && L().simulated ? h('span', { class: 'tag tag--sim simtag', text: 'SIMULATO: trade da simulazioni storiche' }) : null),
      h('p', { class: 'card__sub', text: `${fmtNum(n, 0)} trade${src ? ` (${src})` : ''}${num(ev.per_year) == null ? '' : ` · circa ${fmtNum(ev.per_year, 0)} l'anno`}` }))),
    h('div', { class: 'tiles__grid tiles__grid--3 evalcard__grid' },
      stat({ label: 'R medio per trade', value: rr(p.mean_R), explain: 'Quanto rende in media un trade rispetto a ciò che rischia. Sopra zero il sistema guadagna.' }),
      stat({ label: 'Trade vincenti', value: num(p.win_rate) == null ? null : fmtPct(p.win_rate, 0), explain: 'Meno della metà è normale: pochi trade buoni pagano molti piccoli stop.' }),
      stat({ label: 'Profit factor', value: num(p.profit_factor) == null ? null : fmtNum(p.profit_factor, 2), explain: 'Guadagni totali divisi per perdite totali. Sopra 1 il sistema è in attivo.' }),
      stat({ label: 't', value: num(p.t_stat) == null ? null : fmtSigned(p.t_stat, 2), explain: 'Quanto il risultato è lontano dal puro caso. Sopra 2 è un buon segno, non una prova.' }),
      stat({ label: 'Serie perdente più lunga', value: num(k.max_losing_streak) == null ? null : `${fmtNum(k.max_losing_streak, 0)} di fila`, explain: 'Quanti trade in perdita uno dopo l\'altro: bisogna saperli sopportare.' }),
      stat({ label: 'Caduta peggiore', value: num(k.max_drawdown_R) == null ? null : `${fmtNum(k.max_drawdown_R, 1)} R`, explain: 'La discesa più profonda dal massimo, in R: moltiplicata per il rischio per trade dà la caduta del conto.' })),
    h('div', { class: 'pairs pairs--row only-esperto evalcard__more' },
      [['R totale', num(p.total_R) == null ? null : `${fmtSigned(p.total_R, 1)} R`], ['Payoff', num(p.payoff) == null ? null : fmtNum(p.payoff, 2)], ['Frazione di Kelly', num(p.kelly_fraction) == null ? null : fmtPct(p.kelly_fraction, 1)],
        ['Trade peggiore', rr(k.worst_R)], ['VaR 95%', rr(k.var95_R)], ['CVaR 95%', rr(k.cvar95_R)]]
        .map(([a, b]) => h('span', { class: 'pair' }, h('span', { class: 'pair__label', text: a }), h('span', { class: 'pair__value num', text: b == null ? DASH : b })))));
  }

  function paintEval() {
    const ev = obj(L().evaluation);
    const all = obj(ev.all);
    const paper = obj(ev.paper);
    fill(evalHead, h('h2', { class: 'section-head__title', text: 'Come sta andando' }),
      !num(paper.n) ? explain('Nessun trade paper ancora: per ora i numeri vengono dalle simulazioni storiche. I numeri sono in R: 1 R è ciò che un trade rischiava.') : explain('A sinistra tutti i trade in memoria, a destra solo quelli del conto di prova. I numeri sono in R: 1 R è ciò che un trade rischiava.'));
    evalBlock(evalAll, 'Tutti i trade', all);
    evalBlock(evalPaper, 'Solo trade paper', paper, { paper: true });
    const rob = obj(all.robustness);
    const years = Object.entries(obj(rob.by_year)).filter(([, v]) => num(obj(v).mean_R) != null).sort((a, b) => Number(a[0]) - Number(b[0]));
    fill(yearCard.body, years.length
      ? signedBars(years.map(([y, v]) => ({ label: y, value: num(v.mean_R), text: rr(v.mean_R), note: `${fmtNum(v.n, 0)} trade` })), { labelHead: 'Anno', valueHead: 'R medio', noteHead: 'Quanti', tone: true })
      : empty('Nessun dato per anno'));
    const exits = Object.entries(obj(rob.by_exit)).filter(([, v]) => num(obj(v).mean_R) != null);
    const rp = obj(rob.recent_vs_past);
    const t = num(rp.t);
    fill(exitCard.body, exits.length
      ? signedBars(exits.map(([k, v]) => ({ label: EXITS[k] || k, value: num(v.mean_R), text: rr(v.mean_R), note: `${fmtNum(v.n, 0)} trade` })), { labelHead: 'Uscita', valueHead: 'R medio', noteHead: 'Quanti', tone: true })
      : empty('Nessun dato per motivo di uscita'),
    num(rp.recent_mean_R) == null ? null : h('div', { class: 'recent' },
      h('h3', { class: 'subhead', text: 'Di recente rispetto a prima' }),
      h('div', { class: 'pairs pairs--row' },
        h('span', { class: 'pair' }, h('span', { class: 'pair__label', text: `Ultimi ${fmtNum(rp.recent_n, 0)} trade` }), h('span', { class: 'pair__value num', text: rr(rp.recent_mean_R) })),
        h('span', { class: 'pair' }, h('span', { class: 'pair__label', text: 'Prima' }), h('span', { class: 'pair__value num', text: rr(rp.past_mean_R) })),
        h('span', { class: 'pair only-esperto' }, h('span', { class: 'pair__label', text: 't della differenza' }), h('span', { class: 'pair__value num', text: t == null ? DASH : fmtSigned(t, 2) }))),
      chip(t != null && t <= -2 ? { label: 'Peggioramento netto: da capire', kind: 'warn', icon: 'warn' } : { label: 'Nessun peggioramento evidente', kind: 'ok', icon: 'check' })));
  }

  function ruleItem(r) {
    const st = stateOf(r.state);
    const fails = Array.isArray(r.fails) ? r.fails.map(str) : [];
    const used = new Set();
    const checks = obj(r.checks);
    const rows = CHECKS.filter((c) => c.key in checks).map((c) => {
      const ok = checks[c.key] === true;
      const why = ok ? null : fails.find((f, i) => !used.has(i) && c.find.test(f) && used.add(i));
      return h('li', { class: `check ${ok ? 'check--ok' : 'check--no'}` }, icon(ok ? 'check' : 'x', 'check__icon'),
        h('div', null, h('span', { class: 'check__label' }, h('span', { class: 'sr-only', text: ok ? 'Superato: ' : 'Non superato: ' }), c.label), h('span', { class: 'check__hint', text: ` (${c.hint})` }),
          why ? h('p', { class: 'check__why', text: tidy(why) }) : null));
    });
    const other = fails.filter((_, i) => !used.has(i));
    const sel = obj(r.selection);
    const ver = obj(r.verification);
    const passed = rows.length ? CHECKS.filter((c) => checks[c.key] === true).length : null;
    return h('details', { class: 'rule' },
      h('summary', { class: 'rule__head' },
        h('span', { class: 'rule__text', text: plainRule(r.rule) }), chip(st),
        h('span', { class: 'rule__meta num', text: passed == null ? '' : `${passed} controlli su ${rows.length} superati` }),
        h('span', { class: 'code rule__id only-esperto', text: str(r.id) })),
      h('div', { class: 'rule__body' },
        h('ul', { class: 'checks' }, rows),
        other.length ? h('p', { class: 'check__why', text: `Altri motivi: ${other.map(tidy).join('; ')}` }) : null,
        h('div', { class: 'table-wrap' }, h('table', { class: 'mini mini--wide rule__table' },
          h('thead', null, h('tr', null, h('th', { scope: 'col', text: 'R medio' }), h('th', { scope: 'col', class: 'num', text: 'Trade colpiti dalla regola' }), h('th', { scope: 'col', class: 'num', text: 'Tutti gli altri' }), h('th', { scope: 'col', class: 'num', text: 'Quanti colpiti' }), h('th', { scope: 'col', class: 'num only-esperto', text: 't dei colpiti' }))),
          h('tbody', null, [['In campione (fino al 2022)', sel], ['Fuori campione (dal 2023)', ver]].map(([name, d]) => h('tr', null, h('th', { scope: 'row', text: name }),
            h('td', { class: 'num', text: rr(d.mean) }), h('td', { class: 'num', text: rr(d.rest) }), h('td', { class: 'num', text: num(d.n) == null ? DASH : fmtNum(d.n, 0) }), h('td', { class: 'num only-esperto', text: num(d.t0) == null ? DASH : fmtSigned(d.t0, 2) })))))),
        explain('Perché una regola abbia senso, i trade che colpisce devono rendere meno degli altri e meno di zero, sia in campione sia fuori campione. Se rendono più degli altri, la regola toglierebbe trade buoni.'),
        h('div', { class: 'pairs pairs--row only-esperto' },
          [['Soglia applicata', num(r.threshold_t) == null ? null : `t ≤ −${fmtNum(r.threshold_t, 2)}`], ['Ipotesi provate fino a qui', num(r.k_tried) == null ? null : fmtNum(r.k_tried, 0)], ['Anni in cui regge', num(r.walk_forward) == null ? null : fmtPct(r.walk_forward, 0)],
            ['Guadagno in campione', num(r.gain_R_selection) == null ? null : `${fmtSigned(r.gain_R_selection, 1)} R`], ['Guadagno fuori campione', num(r.gain_R_verification) == null ? null : `${fmtSigned(r.gain_R_verification, 1)} R`], ['Proposta da', str(r.origin) || null]]
            .map(([a, b]) => h('span', { class: 'pair' }, h('span', { class: 'pair__label', text: a }), h('span', { class: 'pair__value num', text: b == null ? DASH : b }))))));
  }

  function paintTried() {
    const list = arr(obj(L().improvement).proposed);
    const rej = list.filter((r) => str(r.state).toUpperCase() === 'RESPINTA').length;
    triedCard.setSub(list.length ? `${list.length} ${list.length === 1 ? 'regola proposta' : 'regole proposte'} in questo giro: ${rej} ${rej === 1 ? 'respinta' : 'respinte'}, ${list.length - rej} ${list.length - rej === 1 ? 'passata' : 'passate'} in ombra.` : '');
    fill(triedCard.body, list.length
      ? [rej === list.length ? explain('Tutte respinte: è l\'esito normale e sano. Una debolezza «sospetta» quasi mai regge a sei controlli severi, ed è meglio scartare una regola forse utile che attivarne una nata da una coincidenza.') : null,
        h('div', { class: 'rulelist' }, list.map(ruleItem))]
      : empty('Nessuna regola proposta in questo giro', 'Il sistema non ha trovato debolezze abbastanza nette da trasformare in ipotesi.'));
  }

  const command = (id) => h('div', { class: 'cmd' },
    h('span', { class: 'cmd__label', text: 'Per attivarla, da terminale:' }), h('code', { class: 'cmd__code', text: `python -m gerva learn --approve ${str(id)} --confirm` }));

  function paintShadowActive() {
    const imp = obj(L().improvement);
    const shadow = arr(imp.shadow);
    const active = arr(imp.active);
    fill(shadowCard.body, shadow.length
      ? [h('ul', { class: 'shadows' }, shadow.map((r) => {
        const n = num(r.n) ?? 0;
        const need = num(r.needed);
        const ready = r.ready === true || str(r.state).toUpperCase() === 'PROMUOVIBILE';
        return h('li', { class: 'shadow' },
          h('div', { class: 'shadow__head' }, h('span', { class: 'rule__text', text: plainRule(r.rule) }), chip(stateOf(ready ? 'PROMUOVIBILE' : r.state))),
          h('div', { class: 'shadow__progress' }, bullet({ ratio: need ? n / need : null, kind: ready ? 'warn' : 'ok', label: 'Trade paper osservati', text: `${n} di ${need}` }),
            h('span', { class: 'num', text: need ? `${fmtNum(n, 0)} di ${fmtNum(need, 0)} trade paper` : `${fmtNum(n, 0)} trade paper` })),
          num(r.mean_R) == null ? null : h('p', { class: 'shadow__figures' }, 'Trade che avrebbe colpito: ', h('strong', { class: 'num', text: rr(r.mean_R) }), ' · gli altri: ', h('strong', { class: 'num', text: rr(r.rest_mean_R) })),
          ready ? command(r.id) : h('p', { class: 'shadow__wait', text: 'Non ancora promuovibile: servono più trade, e i trade colpiti devono rendere meno degli altri e meno di zero.' }),
          h('span', { class: 'code only-esperto', text: str(r.id) }));
      })),
      h('p', { class: 'card__foot', text: 'Questa pagina non ha pulsanti per attivare una regola: si fa solo con il comando, dal proprietario.' })]
      : empty('Nessuna regola in ombra', 'Finora nessuna correzione ha superato la validazione sui dati storici.'));
    fill(activeCard.body, active.length
      ? h('ul', { class: 'shadows' }, active.map((r) => h('li', { class: 'shadow' },
        h('div', { class: 'shadow__head' }, h('span', { class: 'rule__text', text: plainRule(r.rule) }), chip(stateOf('ATTIVA'))), h('span', { class: 'code only-esperto', text: str(r.id) }))))
      : empty('Nessuna regola attiva', 'Il sistema opera con le sue regole originali: nessuna correzione è stata approvata.'));
  }

  return {
    update(next) {
      ctx = next;
      flow.redraw();
      if (!detail.firstChild) paintDetail();
      const k = `${ctx.learnStatus}|${ctx.learn ? str(ctx.learn.generated) + JSON.stringify(ctx.learn).length : ''}`;
      if (k === key) return;                    // il rapporto cambia solo quando gira `gerva learn`: le regole aperte restano aperte
      key = k;
      const has = !!ctx.learn;
      for (const c of cards) if (c !== flowCard) c.el.hidden = !has;
      for (const el of [guard, evalHead, evalAll, evalPaper]) el.hidden = !has;
      missing.hidden = has;
      fill(head, h('h2', { class: 'section-head__title', text: 'Il ciclo di automiglioramento' }),
        has && L().example === true ? h('span', { class: 'tag tag--sim simtag', text: 'ESEMPIO: rapporto dimostrativo' }) : null,
        has && str(L().note).trim() ? h('p', { class: 'explain section-head__note', text: str(L().note) }) : null,
        has ? method('Rapporto scritto da `python -m gerva learn` in $GERVA_HOME/learn/report.json; la pagina lo rilegge ogni 10 minuti.') : null);
      if (!has) {
        fill(missing, ctx.learnStatus === 'loading' ? empty('Caricamento del rapporto…')
          : empty('Nessun rapporto di apprendimento', ctx.learnStatus === 'missing' ? 'Il rapporto si crea con il comando: python -m gerva learn' : 'Il rapporto non si legge. Nuovo tentativo tra un minuto.'));
        return;
      }
      paintGuard(); paintEval(); weakTable.render(arr(L().weaknesses)); paintTried(); paintShadowActive(); regTable.render(arr(L().registry));
    },
    summary(c) {
      if (!c.learn) return 'Il rapporto del ciclo di automiglioramento non è disponibile in questo momento.';
      const l = obj(c.learn);
      const imp = obj(l.improvement);
      const all = obj(obj(l.evaluation).all);
      const paper = num(obj(obj(l.evaluation).paper).n) || 0;
      const prop = arr(imp.proposed);
      const rej = prop.filter((r) => str(r.state).toUpperCase() === 'RESPINTA').length;
      const act = arr(imp.active).length;
      return `Il sistema ha studiato ${fmtNum(all.n, 0)} trade (${paper ? `${fmtNum(paper, 0)} del conto di prova` : 'per ora solo simulati'}), ha trovato ${arr(l.weaknesses).length} punti deboli e provato ${prop.length} correzioni: ${rej === prop.length ? 'tutte respinte dal validatore, com\'è normale' : `${prop.length - rej} in osservazione`}. ${act ? `${act} ${act === 1 ? 'regola è attiva' : 'regole sono attive'}.` : 'Nessuna regola è attiva.'}`;
    },
  };
}
