// Spazio «Sistema»: la macchina gira? Quanto manca al denaro reale?
// In quest'ordine: salute e battito · età dei dati per fonte contro i limiti del motore · il ciclo «come funziona» con lo stato vivo
// su ogni passaggio · registro degli ordini con stati e motivi di rifiuto · avvisi per gravità · cancelli paper → reale · livello AI.
// Sola lettura: l'unico comando che scrive resta il KILL nella fascia. Limiti, soglie e cancelli arrivano dalla fotografia e da
// /api/v1/health → rules; un cancello senza valore è «non ancora misurabile», mai spuntato.

import { dataTable, segmented } from '../components.js';
import { h, icon } from '../dom.js';
import { arr, fmtAgo, fmtDayMonth, fmtDayTime, fmtDuration, fmtMoney, fmtNum, fmtPct, fmtPrice, fmtQty, fmtUnit, num, obj, parseTs, str } from '../format.js';
import { getCompare, getOhlc, getSymbols, getTradebook } from '../market.js';
import { alertLevel, componentStatus, orderSide, orderStatus, riskState } from '../model.js';
import { convLevel, gateState, provenanceDays, sourceAges, watchedSymbols } from '../derive.js';
import { emptyState, meterRow, panel, provOf, provTag } from '../panels.js';
import { factRow, nd, stateChip, stepper } from './kit.js';

const DAY = 86400000;
const SCALE = { NORMAL: '1,0', REDUCED: '0,5', HALTED: '0,25', KILLED: '0' };
const REGIME = { calmo: ['ok', 'Calmo'], normale: ['muted', 'Normale'], teso: ['warn', 'Teso'], crisi: ['crit', 'Crisi'] };
const FILTERS = [
  { value: 'all', label: 'Tutti', match: () => true }, { value: 'filled', label: 'Eseguiti', match: (s) => s === 'filled' || s === 'partial' },
  { value: 'pending', label: 'In attesa', match: (s) => s === 'pending' }, { value: 'rejected', label: 'Rifiutati', match: (s) => s === 'rejected' || s === 'error' },
];
const chipOf = (st) => stateChip(st.kind === 'ok' ? 'ok' : st.kind, st.label, { iconName: st.icon });

export function mount(root, api) {
  let ctxNow = null;
  let tb;
  let cmp;
  let bars = null;
  let filter = 'all';

  // ---- 1. salute ----
  const pHealth = panel({ title: 'La macchina gira?', eyebrow: 'Salute e battito', span: 8, id: 'salute',
    ask: 'Il battito è l\'ultimo segno di vita del motore: deve essere di pochi secondi fa. Sotto, ogni pezzo della macchina con il suo stato a parole.',
    what: 'Il motore scrive un battito a ogni giro. Se il battito è vecchio il motore è fermo, e ogni numero della dashboard è l\'ultimo visto, non quello di adesso. Per ogni componente: stato, tempo di risposta e ultimo momento in cui ha risposto bene.' });
  const beat = h('div', { class: 'sp-beat' });
  const comps = h('div', { class: 'sp-comps' });
  pHealth.body.append(beat, comps);

  // ---- 2. età dei dati ----
  const pAges = panel({ title: 'I dati sono di adesso?', eyebrow: 'Età per fonte, contro i limiti del motore', span: 4, id: 'dati',
    ask: 'Ogni barra è l\'età di una fonte; la tacca bianca è l\'età massima che il motore tollera. Oltre la tacca la fonte è ferma.',
    what: 'Ogni fonte ha la sua età massima: la fotografia pochi minuti, le barre crypto un giorno e mezzo, quelle di borsa un fine settimana lungo. I limiti sono quelli del motore, letti da /api/v1/health: se un limite manca la riga dice «limite non letto», non usa un valore predefinito.' });
  const agesBox = h('div');
  pAges.body.append(agesBox);

  // ---- 3. come funziona, adesso ----
  const pFlow = panel({ title: 'Che cosa fa il motore a ogni giro, e a che punto è adesso?', eyebrow: 'Come funziona, con lo stato vivo', span: 12, id: 'ciclo',
    ask: 'Da sinistra a destra, il percorso di un giro: dai prezzi fino al conto. Su ogni passaggio c\'è il dato di adesso; il bordo tratteggiato segna i due passaggi che possono solo frenare.',
    what: 'Il ciclo del fondo: legge i prezzi, calcola i segnali delle quattro strategie, le pesa a parità di rischio, applica la leva, lascia che il livello AI riduca (mai aumenti), poi il motore di rischio decide per ultimo e solo allora partono gli ordini. Ogni nodo mostra il dato vivo della fotografia.' });
  const flowBox = h('div');
  const flowFacts = h('div');
  pFlow.body.append(flowBox, flowFacts);

  // ---- 4. ordini ----
  const seg = segmented({ label: 'Filtra gli ordini per stato', options: FILTERS.map((f) => ({ value: f.value, label: f.label })), value: filter, onChange: (v) => { filter = v; paintOrders(); } });
  const pOrders = panel({ title: 'Che cosa ha chiesto il motore, e com\'è finita?', eyebrow: 'Registro degli ordini', span: 8, tools: seg.el, id: 'ordini',
    what: 'Ogni ordine deciso dal motore, con l\'esito: eseguito, in attesa, annullato o rifiutato dal controllo di rischio, con il motivo scritto. In paper interno gli ordini sono simulati sull\'ultima chiusura: slittamento e costi reali non sono misurabili.' });
  const ordFacts = h('div');
  const ordTable = dataTable({
    caption: 'Ordini decisi dal motore', sort: { key: 't', dir: -1 }, emptyTitle: 'Nessun ordine', emptyHint: 'Il motore non ha deciso ordini nel periodo coperto dalla fotografia.', cls: 'table--dense sp-table sp-ordtable',
    rowClass: (r) => (['rejected', 'error'].includes(str(r.status).toLowerCase()) ? 'is-rejected' : null),
    detail: (r) => (str(r.reason).trim() ? h('div', { class: 'sp-reason' }, h('b', { text: 'Motivo del rifiuto. ' }), str(r.reason)) : null),
    columns: [
      { key: 't', label: 'Ora', sort: (r) => parseTs(r.t), cell: (r) => (parseTs(r.t) == null ? null : fmtDayTime(parseTs(r.t))) },
      { key: 'symbol', label: 'Strumento', sort: (r) => str(r.symbol), cell: (r) => h('b', { text: str(r.symbol) || '—' }) },
      { key: 'side', label: 'Lato', sort: (r) => str(r.side), cell: (r) => { const sd = orderSide(r.side); return h('span', { class: 'sp-side' }, sd.dir ? icon(sd.dir > 0 ? 'up' : 'down', 'icon--solid sp-arrow') : null, sd.label); } },
      { key: 'qty', label: 'Quantità', num: true, hide: 'sm', sort: (r) => num(r.qty), cell: (r) => (num(r.qty) == null ? null : fmtQty(r.qty)) },
      { key: 'price', label: 'Prezzo', num: true, hide: 'sm', sort: (r) => num(r.price), cell: (r) => (num(r.price) == null ? null : fmtPrice(r.price)) },
      { key: 'value', label: 'Controvalore', num: true, cls: 'not-semplice', hide: 'md', sort: (r) => (num(r.qty) == null || num(r.price) == null ? null : Math.abs(r.qty * r.price)), cell: (r) => (num(r.qty) == null || num(r.price) == null ? null : fmtMoney(Math.abs(r.qty * r.price), ctxNow.ccy, { digits: 0 })) },
      { key: 'strategy', label: 'Strategia', cls: 'not-semplice', hide: 'md', sort: (r) => str(r.strategy), cell: (r) => str(r.strategy) },
      { key: 'venue', label: 'Sede', cls: 'not-semplice', hide: 'md', sort: (r) => str(r.venue), cell: (r) => str(r.venue) },
      { key: 'status', label: 'Stato', sort: (r) => str(r.status), cell: (r) => chipOf(orderStatus(r.status)) },
    ],
  });
  pOrders.body.append(ordFacts, ordTable.el);

  // ---- 5. avvisi ----
  const pAlerts = panel({ title: 'Che cosa ha segnalato il sistema?', eyebrow: 'Avvisi per gravità', span: 4, id: 'avvisi',
    what: 'Gli avvisi della fotografia, raggruppati per gravità: i critici chiedono un intervento, quelli di attenzione vanno guardati, le informazioni sono un registro. La presa in carico si fa dal centro avvisi e resta nel browser.' });
  const alertsBox = h('div', { class: 'sp-alertgroups' });
  const alertsBtn = h('button', { class: 'btn btn--sm btn--ghost', type: 'button' }, icon('bell', 'icon--sm'), 'Apri il centro avvisi');
  alertsBtn.addEventListener('click', () => api.openAlerts());
  pAlerts.body.append(alertsBox);
  pAlerts.setFoot(alertsBtn, h('span', { text: 'Scorciatoia: a' }));

  // ---- 6. cancelli ----
  const pGates = panel({ title: 'Quanto manca al denaro reale?', eyebrow: 'Cancelli paper → reale', span: 6, id: 'cancelli',
    ask: 'Ogni riga è una prova che il paper deve superare. «Non ancora misurabile» vuol dire che servono più giorni o più ordini per calcolarla: non è né superata né fallita.',
    what: 'I cancelli numerici tra paper e denaro reale, valutati dal codice sul registro del paper (gerva/live/gates.py). Tutti devono essere superati; uno aperto vuol dire restare in paper. Un cancello senza valore non è mai contato come superato.' });
  const gatesBig = h('div', { class: 'bignum' });
  const gatesBox = h('div', { class: 'sp-gates' });
  pGates.body.append(gatesBig, gatesBox);

  // ---- 7. livello AI ----
  const pAI = panel({ title: 'Che cosa dice il livello AI, e che cosa sta frenando?', eyebrow: 'Livello AI: può solo ridurre', span: 6, id: 'ai',
    ask: 'Il regime è il «clima» dei mercati. La conviction dice se oggi il libro dei trade può aprire: serve superare la tacca. I freni riducono una strategia, mai la aumentano.',
    what: 'Tre cose: il regime di mercato (da calmo a crisi), la conviction del giorno su BTC, ETH e SOL con le soglie del libro dei trade, e l\'overlay in vigore: i moltiplicatori con cui il livello AI riduce l\'esposizione di una strategia, con motivo, fonti e scadenza. Il contributo dell\'AI al risultato non è mai mostrato come numero: è da misurare in paper.' });
  const aiBox = h('div', { class: 'sp-ai' });
  pAI.body.append(aiBox);

  root.append(h('div', { class: 'ws sp-ws' }, pHealth.el, pAges.el, pFlow.el, pOrders.el, pAlerts.el, pGates.el, pAI.el));

  // ---- disegno ----
  const worst = (list) => (list.some((c) => componentStatus(c.status).kind === 'crit') ? 'crit' : list.some((c) => componentStatus(c.status).kind !== 'ok') ? 'warn' : 'ok');

  function paintHealth() {
    const { snap, fresh, now } = ctxNow;
    const sys = obj(snap.system);
    const list = arr(sys.components);
    const prov = provOf(snap.meta);
    pHealth.setProv(provTag(prov));
    const hb = num(sys.heartbeat_age_s);
    const interval = num(obj(obj(ctxNow.health).rules).interval_s);
    const beatState = !fresh || hb == null ? 'unknown' : interval != null && hb > interval * 2 ? 'crit' : 'ok';
    const ok = list.filter((c) => componentStatus(c.status).kind === 'ok').length;
    beat.replaceChildren(
      h('div', { class: 'sp-beat__main', dataset: { state: beatState } }, h('i', { class: `sp-pulse ${beatState === 'ok' ? 'is-live' : ''}`.trim(), 'aria-hidden': 'true' }),
        h('div', null, h('div', { class: 'bignum', text: !fresh ? 'sconosciuto' : hb == null ? 'battito assente' : fmtAgo(hb) }),
          h('div', { class: 'sp-beat__sub', text: !fresh ? 'i dati sono fermi: il battito qui sotto è l\'ultimo visto' : hb == null ? 'la fotografia non riporta il battito del motore' : beatState === 'crit' ? `ultimo battito oltre due cicli (${fmtDuration(interval)} l'uno): il motore è fermo` : 'ultimo battito del motore' }))),
      h('dl', { class: 'sp-beat__stats' },
        h('div', { class: 'mini' }, h('dt', { text: 'In funzione da' }), h('dd', { text: num(sys.uptime_s) == null ? 'n.d.' : fmtDuration(sys.uptime_s) })),
        h('div', { class: 'mini' }, h('dt', { text: 'Riavvii · 24 ore' }), h('dd', { text: num(sys.restarts_24h) == null ? 'n.d.' : fmtNum(sys.restarts_24h, 0) })),
        h('div', { class: 'mini' }, h('dt', { text: 'Errori · 24 ore' }), h('dd', { class: sys.errors_24h > 0 ? 'sp-warn' : '', text: num(sys.errors_24h) == null ? 'n.d.' : fmtNum(sys.errors_24h, 0) })),
        h('div', { class: 'mini' }, h('dt', { text: 'Componenti' }), h('dd', { text: list.length ? `${fmtNum(ok, 0)} di ${fmtNum(list.length, 0)}` : 'n.d.' }), h('small', { class: 'not-terminale', text: 'operativi' }))));
    comps.replaceChildren(...(list.length ? list.map((c) => {
      const st = componentStatus(c.status);
      const lastOk = parseTs(c.last_ok);
      return h('div', { class: 'sp-comp', dataset: { state: st.kind === 'ok' ? 'ok' : st.kind === 'crit' ? 'crit' : 'warn' } },
        h('span', { class: 'sp-comp__state' }, chipOf(st)),
        h('span', { class: 'sp-comp__name' }, h('b', { text: str(c.name) }), str(c.detail) ? h('small', { text: str(c.detail) }) : null),
        h('span', { class: 'sp-comp__num num not-semplice', text: num(c.latency_ms) == null ? 'n.d.' : `${fmtNum(c.latency_ms, 0)} ms` }),
        h('span', { class: 'sp-comp__num num', text: lastOk == null ? 'mai visto' : fmtAgo(Math.max(0, (now - lastOk) / 1000)) }));
    }) : [emptyState('Componenti non dichiarati', 'La fotografia non riporta lo stato dei componenti.')]));
    const bad = list.filter((c) => componentStatus(c.status).kind !== 'ok');
    pHealth.setAsk(!list.length ? 'La fotografia non dice come stanno i pezzi della macchina.' : bad.length ? `Da guardare: ${bad.map((c) => str(c.name)).join(', ')}. Il resto risponde.` : 'Tutti i pezzi della macchina rispondono.');
    pHealth.setFoot(h('span', { class: 'not-semplice', text: 'Colonne: stato · componente · tempo di risposta · ultimo «tutto bene». «Mai visto» = il componente non ha mai risposto bene da quando il motore è acceso.' }));
  }

  function paintAges() {
    const { snap, health, now, fresh } = ctxNow;
    const rows = sourceAges({ snap, health, now, tradebook: tb, compare: cmp, bars: bars || [] });
    pAges.setProv(provTag(provOf(snap.meta)));
    const groups = [];
    for (const r of rows.filter((x) => x.id.startsWith('bar-'))) {
      const key = String(r.maxS);
      let g = groups.find((x) => x.key === key);
      if (!g) { g = { key, items: [] }; groups.push(g); }
      g.items.push(r);
    }
    const out = rows.filter((x) => !x.id.startsWith('bar-')).filter((r) => !(r.id === 'tb' && tb === undefined) && !(r.id === 'cmp' && cmp === undefined));
    for (const g of groups) {
      const seen = g.items.filter((r) => r.ageS != null);
      const old = seen.length ? seen.reduce((a, b) => (b.ageS > a.ageS ? b : a)) : null;
      const stale = g.items.filter((r) => r.state === 'stale');
      const hours = g.items[0].maxS == null ? null : g.items[0].maxS / 3600;
      out.push({ id: `bars-${g.key}`, name: `Barre ${hours != null && hours > 48 ? 'di borsa (IBKR)' : 'crypto'}`, ageS: old ? old.ageS : null, maxS: g.items[0].maxS, state: !old ? 'missing' : stale.length ? 'stale' : old.state,
        detail: `${fmtNum(g.items.length, 0)} strumenti · la più vecchia ${old ? old.name.replace('Barre ', '') : 'n.d.'}${stale.length ? ` · ferme: ${stale.map((r) => r.name.replace('Barre ', '')).join(', ')}` : ''}` });
    }
    const ageRow = (r) => {
      const state = r.state === 'stale' ? 'breach' : r.state === 'ok' ? (r.ageS / r.maxS > 0.75 ? 'warn' : 'ok') : 'none';
      const bar = h('div', { class: 'meter', dataset: { state } }, h('i'), r.maxS ? h('b') : null);
      const top = r.maxS ? r.maxS * 1.25 : (r.ageS || 1) * 1.5;
      bar.style.setProperty('--v', `${Math.min(100, ((r.ageS || 0) / top) * 100).toFixed(1)}%`);
      if (r.maxS) bar.style.setProperty('--t', '80%');
      return h('div', { class: 'sp-age', dataset: { state: r.state } },
        h('div', { class: 'sp-age__head' }, h('b', { text: r.name }), h('span', { class: 'num' }, r.ageS == null ? nd('assente') : r.ageS < 60 && r.maxS > 3600 ? 'di adesso' : fmtDuration(r.ageS), r.state === 'stale' ? stateChip('crit', 'Ferma') : null)),
        bar, h('div', { class: 'sp-age__foot' }, h('span', { text: r.detail }), h('span', { class: 'num', text: r.maxS == null ? 'limite non letto' : `limite ${fmtDuration(r.maxS)}` })));
    };
    agesBox.replaceChildren(...[...out.map(ageRow),
    bars === null ? h('p', { class: 'panel__ask', text: 'Barre di mercato: in lettura…' }) : !bars.length ? h('p', { class: 'panel__ask', text: 'Barre di mercato: nessuno strumento seguito è nella cache dei prezzi.' }) : null].filter(Boolean));
    const stale = out.filter((r) => r.state === 'stale');
    pAges.setAsk(!fresh ? 'La fotografia stessa è ferma: le età qui sotto sono calcolate sull\'ultima ricevuta.' : stale.length ? `Attenzione: ${stale.map((r) => r.name.toLowerCase()).join(', ')} oltre l'età massima. I numeri che ne dipendono valgono a quella data.` : 'Ogni barra è l\'età di una fonte; la tacca bianca è l\'età massima che il motore tollera. Per ora tutte le fonti sono dentro il limite.');
    pAges.setFoot(h('span', { class: 'not-semplice', text: 'Una barra del giorno G chiude alla mezzanotte UTC di G+1: l\'età si conta da lì. Limiti: meta.stale_after_s, rules.max_data_age_h, due cicli per il battito.' }));
  }

  function paintFlow() {
    const { snap, fresh, ccy } = ctxNow;
    const sys = obj(snap.system);
    const list = arr(sys.components);
    const feeds = list.filter((c) => /dati|gateway|ibkr|kraken|binance|feed/i.test(str(c.name)));
    const strategies = arr(snap.strategies);
    const active = strategies.filter((s) => /active/i.test(str(s.status))).length;
    const ex = obj(snap.exposure);
    const ai = obj(snap.ai);
    const brakes = arr(obj(ai.overlay).strategie).filter((o) => num(o.mult) != null && o.mult < 1);
    const regime = str(obj(ai.regime).stato).toLowerCase();
    const rs = riskState(snap.risk);
    const orders = arr(snap.orders).filter((o) => parseTs(o.t) != null && parseTs(o.t) >= ctxNow.now - DAY);
    const count = (re) => orders.filter((o) => re.test(str(o.status))).length;
    const pd = provenanceDays(snap, ctxNow.quant4);
    const mode = str(obj(snap.meta).mode).toLowerCase();
    const badFeeds = feeds.filter((c) => componentStatus(c.status).kind !== 'ok');
    const u = (s) => (fresh ? s : 'unknown');
    const steps = [
      { title: 'Dati', sub: 'prezzi giornalieri dalle sedi', live: feeds.length ? `${fmtNum(feeds.length, 0)} fonti${badFeeds.length ? ` · ${fmtNum(badFeeds.length, 0)} ${badFeeds.length === 1 ? 'lenta' : 'lente'}` : ' · tutte ok'}` : 'fonti n.d.', state: u(feeds.length ? worst(feeds) : 'unknown'), word: badFeeds.length ? badFeeds.map((c) => str(c.name)).join(', ') : '',
        text: 'Il motore legge le chiusure giornaliere da Kraken, Binance e Interactive Brokers. Se una fonte è ferma, la strategia che ne dipende non opera.' },
      { title: 'Quattro strategie', sub: 'un segnale al giorno ciascuna', live: strategies.length ? `${fmtNum(active, 0)} attive${strategies.length - active ? ` · ${fmtNum(strategies.length - active, 0)} in pausa` : ''}` : 'n.d.', state: u(!strategies.length ? 'unknown' : active === strategies.length ? 'ok' : 'warn'),
        text: 'Trend su BTC ed ETH, momentum sulle crypto più scambiate, ritorno alla media sugli indici, trend lento sugli ETF: regole fisse, calcolate una volta al giorno.' },
      { title: 'Pesi', sub: 'parità di rischio', live: strategies.length ? `quote ${strategies.map((s) => fmtNum((num(s.allocation) || 0) * 100, 0)).join(' · ')}%` : 'n.d.', state: u(strategies.length ? 'ok' : 'unknown'),
        text: 'Ogni strategia riceve una quota tale che tutte pesino uguale sul rischio totale: chi oscilla di più riceve meno denaro.' },
      { title: 'Leva', sub: 'fino al tetto del conto', live: num(ex.leverage) == null ? 'n.d.' : `${fmtNum(ex.leverage, 2)}x${num(ex.max_leverage) == null ? '' : ` su ${fmtNum(ex.max_leverage, 1)}x`}`, state: u(num(ex.leverage) == null ? 'unknown' : num(ex.max_leverage) != null && ex.leverage / ex.max_leverage >= 0.9 ? 'warn' : 'ok'),
        text: 'L\'esposizione viene portata verso la volatilità obiettivo, mai oltre il tetto di leva scritto nella configurazione.' },
      { title: 'Livello AI', sub: 'può solo ridurre', guard: true, live: !snap.ai ? 'non dichiarato' : brakes.length ? brakes.map((o) => `${str(o.id)} al ${fmtPct(o.mult, 0)}`).join(' · ') : 'nessun freno', state: u(!snap.ai ? 'unknown' : brakes.length || regime === 'teso' ? 'warn' : regime === 'crisi' ? 'crit' : 'ok'), word: regime ? `regime ${regime}` : '',
        text: 'Legge notizie ed eventi e può ridurre l\'esposizione di una strategia, con un motivo scritto e una scadenza. Non può aumentarla né aprire posizioni.' },
      { title: 'Motore di rischio', sub: 'decide per ultimo', guard: true, live: fresh ? `${rs.label} · scala ${SCALE[rs.code] || 'n.d.'}` : 'sconosciuto', state: u(rs.code === 'NORMAL' ? 'ok' : rs.code === 'REDUCED' ? 'warn' : 'crit'),
        text: 'Scalini di caduta, tetti di esposizione, freni a 24 ore e 7 giorni, arresto di emergenza: ciò che decide qui non può essere scavalcato da nessuno.' },
      { title: 'Ordini', sub: 'inviati, poi riconciliati', live: `${fmtNum(orders.length, 0)} in 24 ore${count(/pending/i) ? ` · ${fmtNum(count(/pending/i), 0)} in attesa` : ''}${count(/reject|error/i) ? ` · ${fmtNum(count(/reject|error/i), 0)} rifiutati` : ''}`, state: u(count(/error/i) ? 'crit' : count(/reject/i) ? 'warn' : 'ok'),
        text: 'Solo la differenza tra il portafoglio voluto e quello che c\'è diventa ordine. Ogni ordine viene riletto dalla sede: uno non riconciliato blocca il passaggio al reale.' },
      { title: mode === 'live' ? 'Conto reale' : 'Conto di prova', sub: mode === 'live' ? 'denaro vero' : 'paper: nessun denaro vero', live: pd.paper != null ? `giorno ${fmtNum(pd.paper, 0)}${pd.paperTarget ? ` di ${fmtNum(pd.paperTarget, 0)}` : ''}` : pd.real ? `giorno ${fmtNum(pd.real, 0)}` : 'n.d.', state: u('ok'), word: num(obj(snap.nav).equity) == null ? '' : `patrimonio ${fmtMoney(snap.nav.equity, ccy, { digits: 0 })}`,
        text: 'Per ora tutto avviene su un conto di prova. Il denaro reale arriva solo dopo che tutti i cancelli sono superati e il proprietario lo decide.' },
    ];
    const el = stepper(steps, { label: 'Il ciclo del motore, con lo stato di adesso su ogni passaggio' });
    el.style.setProperty('--cols', '4');
    el.classList.add('sp-steps--4');
    flowBox.replaceChildren(el);
    const interval = num(obj(obj(ctxNow.health).rules).interval_s);
    const open = tb ? Object.values(obj(tb.open)).filter((t) => t && typeof t === 'object').length : null;
    flowFacts.replaceChildren(factRow([['Un giro ogni', interval == null ? 'n.d.' : fmtDuration(interval)], ['Libro dei trade a leva', tb === undefined ? '…' : open == null ? 'non disponibile' : `${fmtNum(open, 0)} ${open === 1 ? 'aperto' : 'aperti'}${tb.example ? ' (esempio)' : ''}`], ['Automiglioramento', 'propone, non attiva']]),
      h('a', { class: 'linkrow', href: '#/apprendimento' }, 'Il ciclo che impara, in Apprendimento', icon('arrow')));
    pFlow.setProv(provTag(provOf(snap.meta)));
  }

  function paintOrders() {
    const { snap, now } = ctxNow;
    const all = arr(snap.orders);
    pOrders.setProv(provTag(provOf(snap.meta)));
    const f = FILTERS.find((x) => x.value === filter) || FILTERS[0];
    const st = (o) => str(o.status).toLowerCase();
    const n = (m) => all.filter((o) => m(st(o))).length;
    const gate = arr(snap.gates).find((g) => /non riconciliati/i.test(str(g.name)));
    const stuck = all.filter((o) => st(o) === 'pending' && parseTs(o.t) != null && now - parseTs(o.t) > 3600000);
    const reasons = new Map();
    for (const o of all.filter((x) => FILTERS[3].match(st(x)))) { const k = str(o.reason).trim() || 'motivo non dichiarato'; reasons.set(k, (reasons.get(k) || 0) + 1); }
    ordFacts.replaceChildren(h('div', { class: 'facts sp-facts' },
      h('span', null, 'Ordini', h('b', { text: fmtNum(all.length, 0) })), h('span', null, 'Eseguiti', h('b', { text: fmtNum(n(FILTERS[1].match), 0) })),
      h('span', null, 'In attesa', h('b', { class: stuck.length ? 'sp-warn' : '', text: `${fmtNum(n(FILTERS[2].match), 0)}${stuck.length ? ` · ${fmtNum(stuck.length, 0)} da più di un'ora` : ''}` })),
      h('span', null, 'Rifiutati', h('b', { class: n(FILTERS[3].match) ? 'sp-warn' : '', text: fmtNum(n(FILTERS[3].match), 0) })),
      h('span', null, 'Non riconciliati', h('b', { class: gate && gate.value > 0 ? 'neg' : '', text: gate && num(gate.value) != null ? fmtNum(gate.value, 0) : 'n.d.' }))),
    reasons.size ? h('div', { class: 'verdict' }, h('b', { text: 'Rifiuti per motivo. ' }), [...reasons].map(([k, v]) => `${k} (${fmtNum(v, 0)})`).join(' · ')) : '');
    ordTable.render(all.filter((o) => f.match(st(o))), { emptyHint: filter === 'all' ? 'Il motore non ha deciso ordini nel periodo coperto dalla fotografia.' : 'Nessun ordine in questo stato.' });
    pOrders.setFoot('Slittamento e costi reali: non misurabili in paper interno (gli ordini sono eseguiti all\'ultima chiusura). ', h('a', { class: 'linkrow', href: '#/mercati' }, 'Strumenti in Mercati', icon('arrow')));
  }

  function paintAlerts() {
    const { snap, now } = ctxNow;
    const all = arr(snap.alerts).map((a) => ({ ...a, ts: parseTs(a.t), lv: alertLevel(a.level) })).sort((a, b) => (b.ts || 0) - (a.ts || 0));
    pAlerts.setProv(provTag(provOf(snap.meta)));
    const groups = [['crit', 'Critici', 'critical'], ['warn', 'Attenzione', 'warn'], ['muted', 'Informazioni', 'info']];
    alertsBox.replaceChildren(...(all.length ? groups.map(([kind, name, level]) => {
      const list = all.filter((a) => a.lv.kind === kind);
      return h('section', { class: 'sp-alertgroup' },
        h('header', null, stateChip(kind, name, { iconName: kind === 'muted' ? 'info' : '' }), h('b', { class: 'num', text: fmtNum(list.length, 0) })),
        list.length ? h('div', { class: 'alerts' }, list.slice(0, ctxNow.lv === 'semplice' ? 2 : 4).map((a) => h('div', { class: 'alert', dataset: { level } }, icon(a.lv.icon), h('div', null, h('div', { class: 'alert__msg', text: str(a.msg) }), h('div', { class: 'alert__when', text: a.ts == null ? 'ora non dichiarata' : `${fmtDayTime(a.ts)} · ${fmtAgo(Math.max(0, (now - a.ts) / 1000))}` })))),
          list.length > (ctxNow.lv === 'semplice' ? 2 : 4) ? h('p', { class: 'panel__ask', text: `Altri ${fmtNum(list.length - (ctxNow.lv === 'semplice' ? 2 : 4), 0)} nel centro avvisi.` }) : null)
          : h('p', { class: 'sp-none', text: kind === 'crit' ? 'Nessun avviso critico.' : 'Nessuno.' }));
    }) : [emptyState('Nessun avviso', 'Il sistema non ha segnalato nulla nel periodo coperto dalla fotografia.')]));
  }

  function paintGates() {
    const { snap } = ctxNow;
    const gates = arr(snap.gates);
    pGates.setProv(provTag(provOf(snap.meta)));
    if (!gates.length) { gatesBig.replaceChildren('n.d.'); gatesBox.replaceChildren(emptyState('Cancelli non dichiarati', 'La fotografia non riporta i cancelli tra paper e denaro reale.')); return; }
    const states = gates.map(gateState);
    const ok = states.filter((s) => s === 'ok').length;
    const un = states.filter((s) => s === 'unmeasured').length;
    gatesBig.replaceChildren(`${fmtNum(ok, 0)} di ${fmtNum(gates.length, 0)}`, h('small', { text: 'superati' }), h('small', { class: 'bignum__sub', text: `${fmtNum(gates.length - ok - un, 0)} in corso · ${fmtNum(un, 0)} non ancora misurabili` }));
    gatesBox.replaceChildren(...gates.map((g, i) => {
      const s = states[i];
      const min = /giorni|disponibilit|psr|sharpe/i.test(str(g.name));
      const target = num(g.target);
      const value = num(g.value);
      const ratio = s !== 'unmeasured' && min && target > 0 ? Math.min(1, value / target) : null;
      const bar = ratio == null ? null : h('div', { class: 'meter sp-gate__meter', dataset: { state: s === 'ok' ? 'ok' : 'none' } }, h('i'), h('b'));
      if (bar) { bar.style.setProperty('--v', `${(ratio * 95).toFixed(1)}%`); bar.style.setProperty('--t', '95%'); }
      return h('div', { class: 'sp-gate', dataset: { state: s } },
        h('span', { class: 'sp-gate__state' }, s === 'ok' ? stateChip('ok', 'Superato') : s === 'open' ? stateChip('accent', 'In corso') : stateChip('unknown', 'Non ancora misurabile')),
        h('span', { class: 'sp-gate__name' }, h('b', { text: str(g.name) }), bar),
        h('span', { class: 'sp-gate__val num' }, s === 'unmeasured' ? nd('valore n.d.') : fmtUnit(value, g.unit), h('small', { text: target == null ? 'soglia non letta' : `${min ? 'almeno' : 'al massimo'} ${fmtUnit(target, g.unit)}` })));
    }));
    pGates.setAsk(ok === gates.length ? 'Tutti i cancelli sono superati: il passaggio al denaro reale è una decisione del proprietario.' : `Superati ${fmtNum(ok, 0)} cancelli su ${fmtNum(gates.length, 0)}. ${un ? `${fmtNum(un, 0)} non si possono ancora misurare: servono più giorni o più ordini. ` : ''}Finché non sono tutti superati si resta in paper.`);
    pGates.setFoot(h('span', { class: 'not-semplice', text: 'Nomi e soglie come li scrive il motore (gerva/live/gates.py). Un cancello senza valore non è mai contato come superato, anche se la fotografia lo desse per buono.' }));
  }

  function paintAI() {
    const { snap, now } = ctxNow;
    const ai = snap.ai ? obj(snap.ai) : null;
    pAI.setProv(provTag(provOf(snap.meta)));
    if (!ai) { aiBox.replaceChildren(emptyState('Livello AI non dichiarato', 'La fotografia non contiene il blocco «ai»: regime, conviction e overlay non si possono mostrare.')); return; }
    const rules = obj(obj(ctxNow.health).rules);
    const rg = obj(ai.regime);
    const [rk, rl] = REGIME[str(rg.stato).toLowerCase()] || ['unknown', str(rg.stato) || 'n.d.'];
    const conv = arr(ai.conviction);
    const ov = obj(ai.overlay);
    const brakes = arr(ov.strategie);
    const exp = parseTs(ov.scade);
    const cap = num(rules.score_confirmed);
    const hard = num(rules.score_exceptional);
    aiBox.replaceChildren(
      h('div', { class: 'sp-ai__block' }, h('div', { class: 'sp-sub', text: 'Regime di mercato' }),
        h('div', { class: 'statusline' }, h('span', { class: `pill pill--lg pill--${rk}` }, icon(rk === 'ok' ? 'check-circle' : rk === 'warn' ? 'warn' : rk === 'crit' ? 'crit' : 'circle'), h('span', { text: rl })),
          h('span', null, 'punteggio ', h('b', { text: num(rg.punteggio) == null ? 'n.d.' : `${fmtNum(rg.punteggio, 0)} di 4` })), h('span', { text: rg.scala_esposizione === true ? 'sta riducendo l\'esposizione' : rg.scala_esposizione === false ? 'non riduce l\'esposizione: è solo un\'informazione' : '' }))),
      h('div', { class: 'sp-ai__block' }, h('div', { class: 'sp-sub', text: 'Conviction di oggi · soglie del libro dei trade' }),
        conv.length ? conv.map((c) => { const lv = convLevel(c.score, 'crypto', rules); return meterRow({ name: str(c.asset), sub: lv.text, value: num(c.score) || 0, cap, hard, scale: 1, state: lv.trade ? 'ok' : 'none', text: num(c.score) == null ? 'n.d.' : fmtNum(c.score, 2) }); })
          : h('p', { class: 'sp-none', text: 'Conviction del giorno non dichiarata.' }),
        h('p', { class: 'panel__ask not-semplice', text: cap == null ? 'Soglie del libro dei trade: n.d. (regole del motore non lette).' : `Tacca bianca: trade confermato da ${fmtNum(cap, 2)}; tacca rossa: eccezionale da ${fmtNum(hard, 2)}. Sotto la prima tacca il libro non apre.` })),
      h('div', { class: 'sp-ai__block' }, h('div', { class: 'sp-sub', text: 'Freni in vigore (overlay)' }),
        ov.valido === false ? h('div', { class: 'verdict' }, h('b', { text: 'Overlay non valido. ' }), str(ov.nota) || 'Il motore lo ignora: nessun freno dell\'AI è applicato.') : null,
        num(ov.globale) != null && ov.globale < 1 ? h('div', { class: 'sp-brake' }, stateChip('accent', `Tutto il fondo al ${fmtPct(ov.globale, 0)}`, { iconName: 'ai' }), h('span', { text: str(ov.motivo_globale) || 'motivo non dichiarato' })) : null,
        ...(brakes.length ? brakes.map((o) => h('div', { class: 'sp-brake' }, stateChip('accent', `${str(o.id)} al ${fmtPct(o.mult, 0)}`, { iconName: 'ai' }),
          h('span', null, str(o.motivo) || 'motivo non dichiarato', arr0(o.fonti).length ? h('small', { class: 'not-semplice', text: ` Fonti: ${arr0(o.fonti).join(', ')}.` }) : null))) : [num(ov.globale) != null && ov.globale < 1 ? null : h('p', { class: 'sp-none', text: 'Nessun freno: le strategie operano alla loro quota piena.' })]),
        exp == null ? null : h('p', { class: 'panel__ask', text: exp > now ? `Scade tra ${fmtDuration((exp - now) / 1000)} (${fmtDayTime(exp)}): senza rinnovo i freni decadono da soli.` : `Scaduto il ${fmtDayMonth(exp)}: i freni non sono più in vigore.` })));
    pAI.setFoot('Il contributo dell\'AI al risultato non è mai mostrato come numero: è da misurare in paper. ', h('a', { class: 'linkrow', href: '#/mercati/ai' }, 'Regime e conviction in Mercati', icon('arrow')));
  }
  const arr0 = (v) => (Array.isArray(v) ? v.map(str) : []);

  function paintAll() { paintHealth(); paintAges(); paintFlow(); paintOrders(); paintAlerts(); paintGates(); paintAI(); }

  function loadBars() {
    const want = watchedSymbols(ctxNow.snap, tb).slice(0, 12);
    getSymbols().then((res) => new Set(arr(res && res.symbols).map((x) => str(x.symbol)))).then((have) => Promise.all(want.filter((w) => have.has(w.symbol)).map((w) => getOhlc(w.symbol, 5).then((o) => ({ symbol: w.symbol, kind: w.kind, t: o && o.t && o.t.length ? o.t[o.t.length - 1] : null })))))
      .then((list) => { bars = list; if (ctxNow) paintAges(); }).catch(() => { bars = []; if (ctxNow) paintAges(); });
  }
  let asked = false;
  getTradebook().then((res) => { tb = res || null; if (ctxNow) { paintAges(); paintFlow(); loadBars(); asked = true; } });
  getCompare().then((res) => { cmp = res || null; if (ctxNow) paintAges(); });

  return {
    update(ctx) {
      ctxNow = ctx;
      paintAll();
      if (!asked && tb !== undefined) { asked = true; loadBars(); }
    },
    summary(ctx) {
      const snap = ctx.snap;
      const sys = obj(snap.system);
      const list = arr(sys.components);
      const bad = list.filter((c) => componentStatus(c.status).kind !== 'ok');
      const gates = arr(snap.gates);
      const states = gates.map(gateState);
      if (!ctx.fresh) return 'Non so dirti se la macchina gira adesso: i dati sono fermi. Qui sotto c\'è l\'ultima fotografia ricevuta.';
      return `Il motore ha battuto ${num(sys.heartbeat_age_s) == null ? 'in un momento non dichiarato' : fmtAgo(sys.heartbeat_age_s)}${list.length ? ` e ${fmtNum(list.length - bad.length, 0)} componenti su ${fmtNum(list.length, 0)} rispondono${bad.length ? `: da guardare ${bad.map((c) => str(c.name)).join(', ')}` : ''}` : ''}. `
        + `${gates.length ? `Verso il denaro reale: ${fmtNum(states.filter((s) => s === 'ok').length, 0)} cancelli superati su ${fmtNum(gates.length, 0)}, ${fmtNum(states.filter((s) => s === 'unmeasured').length, 0)} non ancora misurabili.` : ''}`;
    },
  };
}
