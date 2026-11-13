// Spazio «Oggi»: una sola schermata che risponde in cinque secondi alle domande del gestore.
// Guadagno? Qualcosa è rotto o frenato? Perché? Quanto manca al freno? Che cosa è cambiato? Ho trade aperti?
// Poi, a uno scorrimento: atteso contro reale, confronto con l'originale, strada verso il denaro reale.
// Ogni soglia arriva dalla fotografia; ogni dato che manca è uno stato vuoto dichiarato, mai una serie finta.

import { fanChart, waterfall } from '../chart-engine.js';
import { timeChart } from '../charts.js';
import { segmented } from '../components.js';
import { h, icon } from '../dom.js';
import { arr, fmtDate, fmtDayMonth, fmtMoney, fmtNum, fmtPct, fmtPctSigned, fmtSigned, num, obj, parseTs, str } from '../format.js';
import { getCompare, getOhlc, getTradebook } from '../market.js';
import { alertLevel, curveOf, riskState, utilization } from '../model.js';
import { brakes, freshness, nextEquityWindow, sigmaDay, totalNav, tradeAge, tradeLog, tradeR } from '../derive.js';
import { brakeLadder, emptyState, freshLine, meterRow, panel, provOf, provTag, rollNumber, tradeRuler } from '../panels.js';

const DAY = 86400000;
const HHMM = new Intl.DateTimeFormat('it-IT', { hour: '2-digit', minute: '2-digit' });

/** Dati della scala dei freni: una sola fonte (derive.brakes), più il riferimento simulato e l'eventuale peggior caso. */
export function ladderData(ctx, tb, worst = null) {
  const b = brakes(ctx.snap);
  const cone = obj(obj(ctx.quant4).paper_profile_cone);
  const simDd = num(obj(cone.drawdown).p50);
  return {
    dd: b.dd, peak: b.peak, equity: b.equity, ccy: ctx.ccy, es: b.es, fresh: ctx.fresh, steps: b.steps, worstPaper: b.worstSoFar, b,
    simRef: simDd != null ? { value: simDd, label: `${fmtPct(simDd, 0)} caduta tipica simulata a 3 anni` } : null,
    lanes: b.lanes.map((l) => ({ label: l.label, sub: 'finestra mobile', value: l.value, limit: l.limit, action: l.action })),
    worst,
  };
}

/** Avvio del paper sulla curva: l'ultimo punto meno i giorni di paper del cancello. → { t (ms) | null, days, simDays }. */
export function paperStart(snap) {
  const gate = arr(obj(snap).gates).find((g) => /giorni di paper/i.test(str(g.name)));
  const days = gate && num(gate.value) != null ? Math.max(0, Math.round(gate.value)) : null;
  const curve = curveOf(snap);
  const n = curve.t.length;
  const mode = str(obj(obj(snap).meta).mode).toLowerCase();
  if (days == null || n < 2 || mode === 'backtest') return { t: null, days, simDays: null };
  const k = n - 1 - days;
  const perfDays = num(obj(obj(snap).performance).days);
  return { t: k > 0 ? curve.t[k] : curve.t[0], days, simDays: k > 0 ? Math.max(k, perfDays != null && perfDays > days ? perfDays - days : 0) : 0 };
}

export function mount(root, api) {
  let range = '3M';
  let rangeMoved = false;       // l'intervallo è appena stato cambiato dall'utente: la finestra scorre invece di scattare
  let period = 'day';
  let tb;                 // undefined = in arrivo, null = assente
  let cmp;
  const lastClose = new Map();
  let ctxNow = null;

  // ---- 1. patrimonio ------------------------------------------------------------------------------------------------------
  const pNav = panel({ title: 'Patrimonio', span: 8, cls: 'card--hero', what: 'Quanto vale tutto il conto adesso: liquidità più posizioni. Sotto, quanto ha guadagnato o perso oggi e come si colloca la giornata rispetto alle oscillazioni abituali (σ è la volatilità di un giorno normale).' });
  const heroNum = h('span', { class: 'hero__int' });
  const heroDec = h('span', { class: 'hero__dec' });
  const heroCur = h('span', { class: 'hero__cur' });
  const delta = h('span', { class: 'delta delta--flat' });
  const ctxLine = h('p', { class: 'hero__ctx' });
  const books = h('p', { class: 'hero__books' });
  const posLine = h('p', { class: 'hero__books hero__flat' });
  const side = h('dl', { class: 'hero__side' });
  const provLine = h('p', { class: 'hero__prov' });
  const chartHost = h('div', { class: 'chart-host' });
  const chartNote = h('span');
  const rangeSeg = segmented({ label: 'Intervallo del grafico', options: [{ value: '1M', label: '1M' }, { value: '3M', label: '3M' }, { value: '1A', label: '1A' }, { value: 'ALL', label: 'Avvio' }], value: range, onChange: (v) => { range = v; rangeMoved = true; paintNav(); } });
  pNav.body.append(h('div', { class: 'hero' },
    h('div', { class: 'hero__main' }, h('div', { class: 'hero__num num' }, heroNum, heroDec, heroCur), delta, ctxLine, books, posLine, side, provLine),
    h('div', { class: 'hero__chart' }, h('div', { class: 'hero__chart-head' }, chartNote, rangeSeg.el), chartHost)));
  const navChart = timeChart(chartHost, { label: 'Patrimonio e, sotto, caduta dal massimo' });

  // ---- 2. freni -------------------------------------------------------------------------------------------------------------
  const pBrake = panel({ title: 'Quanto manca ai freni', span: 4, what: 'Il motore di rischio riduce da solo le posizioni quando il conto scende troppo dal suo massimo. Qui vedi quanti punti mancano al primo scalino e che cosa succede a ognuno. La scala completa, con le perdite a 24 ore e 7 giorni, è nello spazio Rischio.' });
  const brakeBig = h('div', { class: 'bignum' });
  const brakeHost = h('div', { class: 'chart-host' });
  const brakeKv = h('div', { class: 'kv' });
  const brakeLanes = h('div', { class: 'lanes' });
  pBrake.body.append(brakeBig, brakeHost, brakeLanes, brakeKv);
  const ladder = brakeLadder(brakeHost, { compact: true, label: 'Distanza dai freni automatici' });
  pBrake.setFoot(h('a', { class: 'linkrow', href: '#/rischio' }, 'Scala completa in Rischio', icon('arrow')));

  // ---- 3. da dove viene il risultato --------------------------------------------------------------------------------------
  const periodSeg = segmented({ label: 'Periodo', options: [{ value: 'day', label: 'Oggi' }, { value: 'mtd', label: 'Mese' }, { value: 'total', label: 'Dall\'avvio' }], value: period, onChange: (v) => { period = v; paintAttr(); } });
  const pAttr = panel({ title: 'Da dove viene il risultato', span: 4, tools: periodSeg.el, what: 'Il guadagno o la perdita del periodo, diviso tra le strategie. Ogni barra parte da dove finisce la precedente: l\'ultima è il totale. «Non attribuito» è la parte che la somma delle strategie non spiega: se supera un punto base viene segnalata.' });
  const attrHost = h('div', { class: 'chart-host' });
  const attrNote = h('div', { class: 'panel__ask' });
  pAttr.body.append(attrHost, attrNote);
  const attrChart = waterfall(attrHost, [], { label: 'Contributo delle strategie al risultato', orient: 'h', format: (v) => fmtMoney(v, 'EUR', { digits: 2, signed: true }), levelFormat: (v) => fmtMoney(v, 'EUR', { digits: 0 }), totalFormat: (v) => fmtMoney(v, 'EUR', { digits: 2, signed: true }), valueHead: 'Contributo', levelHead: 'Somma' });

  // ---- 4. che cosa è cambiato -----------------------------------------------------------------------------------------------
  const pChg = panel({ title: 'Che cosa è cambiato da ieri', span: 4, what: 'Le cose che il sistema ha fatto o segnalato nelle ultime 24 ore: ordini, avvisi, movimenti del libro dei trade, freni dell\'AI in vigore. Tre righe in Semplice, fino a otto negli altri livelli.' });
  const events = h('div', { class: 'events' });
  pChg.body.append(events);

  // ---- 5. trade a leva aperti -----------------------------------------------------------------------------------------------
  const pTrades = panel({ title: 'Trade a leva aperti', span: 4, what: 'Le scommesse aperte nel libro dei trade a margine isolato. R è il risultato in multipli del rischio iniziale: +1 R vuol dire aver guadagnato quanto si era disposti a perdere. Il righello mostra liquidazione, stop, entrata e ultima chiusura sulla stessa scala di prezzo.' });
  const tradesBox = h('div', { class: 'panel__body' });
  pTrades.body.append(tradesBox);
  const rulers = new Map();

  // ---- 6. atteso contro reale -----------------------------------------------------------------------------------------------
  const pCone = panel({ title: 'Atteso contro reale', span: 4, what: 'La fascia è ciò che le simulazioni del profilo del paper considerano normale (dal 5° al 95° percentile, più scura tra il 25° e il 75°), la linea tratteggiata è la mediana simulata, la linea piena è il conto vero. Dentro la fascia: tutto come previsto.' });
  const coneBig = h('div', { class: 'bignum' });
  const coneHost = h('div', { class: 'chart-host' });
  pCone.body.append(coneBig, coneHost);
  const cone = fanChart(coneHost, { label: 'Ventaglio atteso del profilo del paper e percorso del conto' });

  // ---- 7. confronto con l'originale ---------------------------------------------------------------------------------------
  const pCmp = panel({ title: 'Il fondo contro i mercati', span: 4, what: 'Il fondo, l\'S&P 500 e il Bitcoin negli stessi giorni, partiti da 100 nel primo giorno del confronto; se il motore ha le righe del sistema originale del proprietario, c\'è anche lui. Pochi giorni non bastano a dire chi è meglio: la differenza va letta insieme al numero di giorni osservati. Il test statistico completo (imbuto del caso) è nello spazio Evidenza.' });
  const cmpBig = h('div', { class: 'bignum' });
  const cmpHost = h('div', { class: 'chart-host' });
  pCmp.body.append(cmpBig, cmpHost);
  const cmpChart = timeChart(cmpHost, { label: 'Fondo, S&P 500, Bitcoin e sistema originale a base 100' });

  // ---- 8. verso il denaro reale -----------------------------------------------------------------------------------------------
  const pGates = panel({ title: 'Verso il denaro reale', span: 4, what: 'I cancelli che il paper deve superare prima di poter usare denaro vero: giorni di prova, ordini eseguiti, errori, scostamento dal backtest. Finché non sono tutti verdi la modalità reale non esiste.' });
  const gatesBig = h('div', { class: 'bignum' });
  const gatesBox = h('div');
  pGates.body.append(gatesBig, gatesBox);
  pGates.setFoot(h('a', { class: 'linkrow', href: '#/sistema' }, 'Tutti i cancelli in Sistema', icon('arrow')));

  root.append(h('div', { class: 'ws' }, pNav.el, pBrake.el, pAttr.el, pChg.el, pTrades.el, pCone.el, pCmp.el, pGates.el));

  // ---- disegno --------------------------------------------------------------------------------------------------------------

  function paintNav() {
    const { snap, ccy } = ctxNow;
    const nav = obj(snap.nav);
    const tn = totalNav(snap, tb);
    const eq = tb === undefined ? null : tn.total;          // la cifra eroe aspetta il libro dei trade: mai un totale parziale
    const prov = provOf(snap.meta);
    pNav.setProv(provTag(prov));
    if (eq == null) { heroNum.textContent = tb === undefined ? '…' : 'n.d.'; heroDec.textContent = ''; heroCur.textContent = ''; } else {
      const [int, dec] = fmtNum(Math.abs(eq), 2).split(',');
      rollNumber(heroNum, `${eq < 0 ? '−' : ''}${int}`);
      rollNumber(heroDec, `,${dec || '00'}`);
      heroCur.textContent = fmtMoney(0, ccy, { digits: 0 }).replace(/[\d\s.,−-]/g, '') || ccy;
    }
    const day = num(nav.pnl_day);
    const dayPct = num(nav.pnl_day_pct);
    delta.className = `delta delta--${day > 0 ? 'pos' : day < 0 ? 'neg' : 'flat'}`;
    delta.replaceChildren(...(day == null ? [document.createTextNode('variazione di oggi n.d.')] : [day === 0 ? null : icon(day > 0 ? 'up' : 'down', 'icon--solid'), h('span', { text: fmtMoney(day, ccy, { signed: true }) }), h('i', { text: fmtPctSigned(dayPct, 2) })].filter(Boolean)));
    const sg = sigmaDay(snap);
    ctxLine.textContent = sg == null ? 'oggi · σ n.d. (manca la volatilità obiettivo)' : `oggi · ${fmtSigned(sg.z, 1)} σ sulla volatilità obiettivo (${fmtPct(sg.target, 0)}): ${sg.word}`;
    const tbDay = tb ? parseTs(str(tb.asof)) : null;
    books.textContent = tb === undefined ? 'Libro dei trade: in lettura…'
      : !tn.complete ? `Libro giornaliero ${fmtMoney(tn.daily, ccy)} · contributo dei trade n.d. (libro non disponibile): il totale è solo il libro giornaliero`
        : `Libro giornaliero ${fmtMoney(tn.daily, ccy)} · contributo dei trade ${fmtMoney(tn.tradeGain, ccy, { signed: true })}${tbDay == null ? '' : ` (libro del ${fmtDayMonth(tbDay, true)})`}${tb.example ? ' · esempio' : ''}`;
    // nessuna posizione: lo si dice, con il momento in cui il libro giornaliero può entrare (finestra delle azioni, regola del motore)
    const flat = Array.isArray(snap.positions) && !snap.positions.length;
    posLine.hidden = !flat;
    if (flat) {
      const win = nextEquityWindow(ctxNow.now, obj(obj(ctxNow.health).rules).equity_window);
      const rome = (t, o) => new Intl.DateTimeFormat('it-IT', { timeZone: 'Europe/Rome', ...o }).format(new Date(t));
      const sameDay = win && rome(win.start, { dateStyle: 'short' }) === rome(ctxNow.now, { dateStyle: 'short' });
      posLine.replaceChildren(h('b', { text: 'Nessuna posizione aperta. ' }), win
        ? `Azioni ed ETF entrano solo nella finestra ${rome(win.start, { hour: '2-digit', minute: '2-digit' })}–${rome(win.end, { hour: '2-digit', minute: '2-digit' })} ora italiana (${win.open ? 'aperta adesso' : sameDay ? 'prossima: oggi' : `prossima: ${rome(win.start, { weekday: 'short', day: 'numeric', month: 'short' })}`}); le crypto a ogni ciclo, se i segnali lo chiedono.`
        : 'Finestra delle azioni n.d. (regola del motore non letta); le crypto entrano a ogni ciclo, se i segnali lo chiedono.');
    }
    const start = num(nav.start_equity);
    const curve = curveOf(snap);
    const n = curve.t.length;
    // provenienza di ogni cifra di periodo: se il periodo comincia prima dell'avvio del paper, dentro ci sono giorni simulati e lo si scrive
    const ps = paperStart(snap);
    const endDay = n ? new Date(curve.t[n - 1]) : new Date(ctxNow.now);
    const mixed = (from) => (ps.t != null && from != null && from < ps.t - DAY / 2 ? Math.round((ps.t - from) / DAY) : 0);
    const well = (k, v, sub, simDays) => h('div', { class: `mini ${simDays > 0 ? 'mini--mixed' : ''}`.trim() }, h('dt', { text: k }), h('dd', { class: v > 0 ? 'pos' : v < 0 ? 'neg' : '' }, v == null ? 'n.d.' : [v === 0 ? null : icon(v > 0 ? 'up' : 'down', 'icon--solid'), fmtPctSigned(v, 2)]),
      h('small', { class: 'not-terminale' }, sub), simDays > 0 ? h('small', { class: 'mini__prov', title: `Il periodo comprende ${fmtNum(simDays, 0)} giorni simulati prima dell'avvio del paper${ps.days == null ? '' : ` e ${fmtNum(ps.days, 0)} giorni di paper`}: non è un risultato ottenuto.`, text: 'con giorni simulati' }) : null);
    side.replaceChildren(well('Mese', num(nav.pnl_mtd_pct), 'dal 1° del mese', mixed(Date.UTC(endDay.getUTCFullYear(), endDay.getUTCMonth(), 1))), well('Anno', num(nav.pnl_ytd_pct), 'dal 1° gennaio', mixed(Date.UTC(endDay.getUTCFullYear(), 0, 1))),
      well('Dall\'avvio', num(nav.pnl_total_pct), start == null ? '' : `da ${fmtMoney(start, ccy, { digits: 0 })}`, ps.simDays || 0));
    provLine.hidden = !ps.simDays;
    provLine.textContent = ps.simDays ? `Anno e Dall'avvio contengono ${fmtNum(ps.simDays, 0)} giorni simulati prima dell'avvio del paper (${fmtNum(ps.days, 0)} giorni fa): sul grafico il simulato è tratteggiato.` : '';
    if (n < 2) { navChart.update(null); chartNote.textContent = 'La curva comparirà dopo i primi due giorni di storico.'; return; }
    // il grafico riceve tutta la curva; l'intervallo è una finestra che scorre (--chart-range) invece di un taglio netto
    const months = { '1M': 1, '3M': 3, '1A': 12, ALL: null }[range];
    let i0 = 0;
    if (months) { const end = new Date(curve.t[n - 1]); const cut = Date.UTC(end.getUTCFullYear(), end.getUTCMonth() - months, end.getUTCDate()); while (i0 < n - 2 && curve.t[i0] < cut) i0++; }
    const x = curve.t;
    const e = curve.equity;
    const dd = curve.dd;
    // il tratto dice la provenienza: tratteggiato fino all'avvio del paper (simulato), pieno da lì in poi; il confine è disegnato
    const kp = ps.t == null ? -1 : x.findIndex((tt) => tt >= ps.t - DAY / 2);
    const allSim = prov === 'sim' || kp < 0;
    const split = !allSim && kp > 0;
    const series = split
      ? [{ values: e.map((v, i) => (i <= kp ? v : null)), cls: 'fund sim', area: true, name: 'Patrimonio (simulato)' }, { values: e.map((v, i) => (i >= kp ? v : null)), cls: 'fund', area: true, end: true, name: prov === 'demo' ? 'Patrimonio (paper di esempio)' : 'Patrimonio (paper)' }]
      : [{ values: e, cls: prov === 'sim' || (ps.t != null && kp < 0) ? 'fund sim' : 'fund', area: true, end: true, name: 'Patrimonio' }];
    const provAt = (i) => (ps.t == null ? '' : x[i] < ps.t - DAY / 2 ? 'Simulato' : prov === 'demo' ? 'Paper (esempio)' : prov === 'real' ? 'Reale' : 'Paper');
    chartNote.textContent = `${fmtDate(x[i0], true)} – ${fmtDate(x[x.length - 1], true)}${split && kp > i0 ? ' · tratteggiato: simulato' : ''}`;
    navChart.update({
      x,
      marks: split ? [{ t: x[kp], label: 'avvio del paper' }] : [],
      panels: [
        { height: ctxNow.lv === 'terminale' ? 96 : 184, series, format: (v) => fmtNum(v, 0) },
        { height: 36, title: 'Caduta dal massimo', top: 0, series: [{ values: dd, cls: 'dd', area: true, name: 'Caduta' }], format: (v) => fmtPct(v, 0), refs: arr(obj(snap.risk).dd_ladder).filter((st) => num(st.level) != null && st.level >= Math.min(...dd.slice(i0).filter((v) => v != null)) * 1.6).map((st) => ({ value: st.level, label: fmtPct(st.level, 0) })) },
      ],
      tip: (i) => ({ title: fmtDate(x[i], true), rows: [{ key: 'fund', label: 'Patrimonio', value: fmtMoney(e[i], ccy) }, { key: 'dd', label: 'Caduta dal massimo', value: dd[i] == null ? '—' : fmtPctSigned(dd[i], 2) }, provAt(i) ? { label: 'Provenienza', value: provAt(i) } : null].filter(Boolean) }),
      say: (i) => `${fmtDate(x[i], true)}${provAt(i) ? ` (${provAt(i).toLowerCase()})` : ''}: patrimonio ${fmtMoney(e[i], ccy)}, caduta dal massimo ${dd[i] == null ? 'non disponibile' : fmtPctSigned(dd[i], 2)}`,
    });
    navChart.setWindow(x[i0], x[n - 1], { animate: rangeMoved });
    rangeMoved = false;
  }

  function paintBrake() {
    const { snap, ccy, fresh } = ctxNow;
    const d = ladderData(ctxNow, tb);
    const b = d.b;
    if (!b.steps.length || b.dd == null) {
      brakeBig.replaceChildren('soglia non letta');
      pBrake.setAsk('La fotografia non riporta gli scalini della caduta: nessun valore predefinito viene usato al loro posto.');
    } else if (!fresh) {
      brakeBig.replaceChildren('sconosciuta');
      pBrake.setAsk('I dati sono fermi: la distanza dai freni non si può dire. Mai una barra verde su dati vecchi.');
    } else if (!b.next) {
      brakeBig.replaceChildren('ultimo scalino superato');
      pBrake.setAsk(`La caduta ha passato anche l'ultimo scalino (${fmtPct(b.last.level, 0)}): ${b.last.action}.`);
    } else {
      brakeBig.replaceChildren(`${fmtNum(b.distNext * 100, 1)} punti`, h('small', { class: 'bignum__sub', text: `${b.hit ? `al prossimo scalino (${fmtPct(b.next.level, 0)}) · ` : ''}${b.peak == null ? '' : `= ${fmtMoney(b.distNext * b.peak, ccy, { digits: 0 })} · scatta a ${fmtMoney(b.peak * (1 + b.next.level), ccy, { digits: 0 })}`}` }));
      pBrake.setAsk(b.hit ? `Lo scalino ${fmtPct(b.last.level, 0)} è già scattato (${b.last.action}). Mancano ${fmtNum(b.distNext * 100, 1)} punti al successivo; si torna indietro quando la caduta rientra sotto ${fmtPct(b.reentry, 0)}.`
        : `Siamo a ${fmtNum(b.distNext * 100, 1)} punti dal livello in cui il motore: ${b.next.action || 'riduce l\'esposizione'}.`);
    }
    pBrake.setProv(provTag(provOf(snap.meta)));
    ladder.update(d);
    const lims = arr(obj(snap.risk).limits).map((l) => ({ l, u: utilization(l.value, l.limit) })).filter((x) => x.u != null).sort((a, b) => b.u - a.u);
    const open = Object.values(obj(obj(tb).open));
    const atRisk = open.reduce((a, t) => a + (num(t.risk) || 0), 0);
    // i due freni rapidi in miniatura: perdita della finestra mobile contro la sua soglia (la scala estesa è in Rischio)
    brakeLanes.replaceChildren(...b.lanes.map((l) => meterRow({ name: l.label, value: !fresh || l.value == null ? 0 : Math.max(0, -l.value), cap: Math.abs(l.limit), state: !fresh || l.value == null ? 'none' : l.value <= l.limit ? 'breach' : -l.value / Math.abs(l.limit) >= 0.6 ? 'warn' : 'ok',
      text: !fresh ? 'sconosciuta' : l.value == null ? 'non calcolabile' : `${fmtPctSigned(l.value, 2)} / ${fmtPct(l.limit, 0)}` })));
    brakeKv.replaceChildren(
      h('div', null, h('span', { class: 'k', text: 'Limite più vicino' }), h('span', { class: 'v', title: lims.length ? str(lims[0].l.name) : null, text: lims.length ? `${str(lims[0].l.name).replace(/^Esposizione sulla /i, '').replace(/^Peso massimo di uno strumento$/i, 'peso di uno strumento')} · ${fmtPct(lims[0].u, 0)}` : 'n.d.' })),
      h('div', null, h('span', { class: 'k', text: 'A rischio nei trade' }), h('span', { class: 'v', title: 'Somma del rischio agli stop, in percentuale del patrimonio totale', text: tb === undefined ? '…' : !tb ? 'n.d.' : `${fmtMoney(atRisk, ccy)}${totalNav(snap, tb).total ? ` · ${fmtPct(atRisk / totalNav(snap, tb).total, 2)} del totale` : ''}` })));
  }

  function paintAttr() {
    const { snap, ccy } = ctxNow;
    const nav = obj(snap.nav);
    const eq = num(nav.equity);
    const strategies = arr(snap.strategies);
    const prov = provOf(snap.meta);
    pAttr.setProv(provTag(prov));
    let rows = [];
    let total = null;
    let base = '';
    if (period === 'day') {
      const by = new Map();
      for (const p of arr(snap.positions)) if (num(p.pnl_day) != null) by.set(str(p.strategy), (by.get(str(p.strategy)) || 0) + p.pnl_day);
      rows = strategies.map((st) => ({ label: ctxNow.lv === 'semplice' ? str(st.name) || str(st.id) : str(st.id), value: by.get(str(st.id)) ?? null })).filter((r) => r.value != null);
      total = num(nav.pnl_day);
      base = 'Somma del P&L di oggi delle posizioni, per strategia.';
    } else {
      const key = period === 'mtd' ? 'pnl_mtd_pct' : 'pnl_total_pct';
      const pctAll = num(period === 'mtd' ? nav.pnl_mtd_pct : nav.pnl_total_pct);
      const startEq = eq != null && pctAll != null ? eq / (1 + pctAll) : null;
      rows = startEq == null ? [] : strategies.map((st) => ({ label: ctxNow.lv === 'semplice' ? str(st.name) || str(st.id) : str(st.id), value: num(st.allocation) != null && num(st[key]) != null ? st.allocation * st[key] * startEq : null })).filter((r) => r.value != null);
      total = startEq == null ? null : eq - startEq;
      base = 'Quota di ogni strategia × il suo rendimento del periodo × patrimonio di inizio periodo: una stima, la base del rendimento per strategia non è dichiarata.';
    }
    if (!rows.length || total == null) {
      attrHost.hidden = true;
      const flat = Array.isArray(snap.positions) && !snap.positions.length;
      attrNote.replaceChildren(flat && (total == null || Math.abs(total) < 0.005)
        ? emptyState('Niente da attribuire', 'Nessuna posizione aperta e nessun guadagno o perdita nel periodo: la cascata per strategia compare con le prime posizioni.')
        : 'Nessun contributo da mostrare per questo periodo: la fotografia non riporta il P&L per strategia.');
      return;
    }
    attrHost.hidden = false;
    const sum = rows.reduce((a, r) => a + r.value, 0);
    const gap = total - sum;
    const bp = eq ? Math.abs(gap) / eq * 10000 : 0;
    attrChart.update([...rows.sort((a, b) => b.value - a.value), ...(Math.abs(gap) >= 0.005 ? [{ label: 'Non attribuito', value: gap, note: bp > 1 ? `Scarto di ${fmtNum(bp, 0)} punti base: da spiegare.` : '' }] : []), { label: 'Totale', value: total, total: true }]);
    const best = rows[0];
    attrNote.replaceChildren(ctxNow.lv === 'semplice' ? `${total >= 0 ? 'Ha guadagnato' : 'Ha perso'} soprattutto con ${best.label}. ` : '', base, bp > 1 ? ` Non attribuito: ${fmtNum(bp, 0)} pb.` : '', ' Libro dei trade: non è nella fotografia (n.d.).');
    attrNote.classList.remove('only-semplice');
    void ccy;
  }

  function paintChanges() {
    const { snap, now, ccy, lv } = ctxNow;
    const since = now - DAY;
    const list = [];
    for (const a of arr(snap.alerts)) {
      const t = parseTs(a.t);
      if (t == null || t < since) continue;
      const lvl = str(a.level).toLowerCase();
      list.push({ t, kind: lvl === 'critical' ? 'crit' : lvl === 'warn' ? 'warn' : '', k: alertLevel(a.level).label, text: str(a.msg) });
    }
    const orders = arr(snap.orders).map((o) => ({ ...o, ts: parseTs(o.t) })).filter((o) => o.ts != null && o.ts >= since);
    const filled = orders.filter((o) => str(o.status).toLowerCase() === 'filled');
    if (filled.length) list.push({ t: Math.max(...filled.map((o) => o.ts)), kind: '', k: 'Ordini', text: `${fmtNum(filled.length, 0)} ${filled.length === 1 ? 'ordine eseguito' : 'ordini eseguiti'}, ${fmtMoney(filled.reduce((a, o) => a + Math.abs((num(o.qty) || 0) * (num(o.price) || 0)), 0), ccy, { digits: 0 })} di controvalore.` });
    for (const o of orders.filter((x) => str(x.status).toLowerCase() === 'rejected')) list.push({ t: o.ts, kind: 'warn', k: 'Rifiuto', text: `${str(o.symbol)}: ${str(o.reason) || 'ordine rifiutato dal controllo di rischio'}` });
    for (const e of tradeLog(tb).filter((x) => !x.empty).slice(-3)) { if (e.t != null && e.t >= since - DAY) list.push({ t: e.t, kind: '', k: 'Trade', text: e.text, dayOnly: true }); }
    const ov = obj(obj(snap.ai).overlay);
    for (const st of arr(ov.strategie)) if (num(st.mult) != null && st.mult < 1) list.push({ t: now, kind: 'ai', k: 'Freno AI', text: `${str(st.id)} al ${fmtPct(st.mult, 0)}: ${str(st.motivo) || 'motivo non dichiarato'}`, nowish: true });
    list.sort((a, b) => b.t - a.t);
    const max = lv === 'semplice' ? 3 : 8;
    if (!list.length) { events.replaceChildren(emptyState('Nulla è cambiato', 'Nessun ordine, avviso o movimento nelle ultime 24 ore.')); pChg.setFoot(); return; }
    events.replaceChildren(...list.slice(0, max).map((e) => h('div', { class: 'event' },
      h('span', { class: 'event__t', text: e.nowish ? 'ora' : e.dayOnly ? fmtDayMonth(e.t, true) : HHMM.format(new Date(e.t)) }),
      h('span', { class: `event__k ${e.kind ? `event__k--${e.kind}` : ''}`.trim(), text: e.k }), h('span', { text: e.text }))));
    pChg.setAsk(`Nelle ultime 24 ore il sistema ha fatto o segnalato ${fmtNum(list.length, 0)} ${list.length === 1 ? 'cosa' : 'cose'}.`);
    pChg.setFoot(list.length > max ? h('a', { class: 'linkrow', href: '#/sistema' }, `Altri ${fmtNum(list.length - max, 0)} nel registro`, icon('arrow')) : h('a', { class: 'linkrow', href: '#/sistema' }, 'Registro completo', icon('arrow')));
  }

  function paintTrades() {
    const { snap, ccy } = ctxNow;
    if (tb === undefined) { tradesBox.replaceChildren(emptyState('Libro dei trade in lettura…')); return; }
    if (!tb) { tradesBox.replaceChildren(emptyState('Libro dei trade non disponibile', 'Il motore non ha ancora scritto lo stato del libro a margine isolato.')); pTrades.setProv(); return; }
    pTrades.setProv(provTag(tb.example ? 'demo' : provOf(snap.meta) === 'real' ? 'real' : 'paper'));
    const open = Object.values(obj(tb.open)).filter((t) => t && typeof t === 'object');
    if (!open.length) {
      const conv = arr(obj(snap.ai).conviction).map((c) => `${str(c.asset)} ${str(c.livello)}`).join(', ');
      tradesBox.replaceChildren(emptyState('Nessun trade aperto', conv ? `Conviction di oggi: ${conv}. Il libro apre solo nei giorni ad alta conviction.` : 'Il libro apre solo nei giorni ad alta conviction.'));
      pTrades.setAsk('Oggi non ci sono scommesse a leva aperte.');
      rulers.clear();
      return;
    }
    const nodes = [];
    const rules = obj(obj(ctxNow.health).rules);
    const anomalies = [];
    const tbFresh = freshness(parseTs(str(tb.asof)), ctxNow.now, 'crypto', rules);
    if (tbFresh.stale) anomalies.push(`libro dei trade fermo al ${fmtDayMonth(tbFresh.day, true)}`);
    let risk = 0;
    for (const t of open) {
      const sym = str(t.symbol);
      const last = lastClose.get(sym);
      if (last === undefined) { lastClose.set(sym, null); getOhlc(sym, 30).then((o) => { lastClose.set(sym, o && o.c.length ? { c: o.c[o.c.length - 1], t: o.t[o.t.length - 1] } : null); if (ctxNow) paintTrades(); }); }
      const r = tradeR(t, last && last.c);
      risk += num(t.risk) || 0;
      let entry = rulers.get(sym);
      if (!entry) { const host = h('div', { class: 'chart-host' }); entry = { host, ruler: tradeRuler(host, { label: `Livelli del trade su ${sym}` }) }; rulers.set(sym, entry); }
      const age = tradeAge(t, tb, rules);
      const fr = freshness(last && last.t, ctxNow.now, 'crypto', rules);
      if (age.over) anomalies.push(`${sym}: aperto da ${fmtNum(age.held, 0)} giorni, oltre la durata massima di ${fmtNum(age.maxHold, 0)}`);
      if (fr.stale) anomalies.push(`${sym}: prezzo fermo alla chiusura del ${fmtDayMonth(fr.day, true)}`);
      nodes.push(h('div', { class: 'trade' },
        h('div', { class: 'trade__head' }, h('span', { class: `trade__r ${r > 0 ? 'pos' : r < 0 ? 'neg' : ''}`, text: r == null ? 'R n.d.' : `${fmtSigned(r, 2)} R` }),
          h('span', { class: 'trade__meta', text: `${sym} ${num(t.side) === -1 ? 'al ribasso' : 'al rialzo'} · ${fmtNum(t.leverage, 1)}x${age.held == null ? '' : ` · giorno ${fmtNum(age.held, 0)}${age.maxHold == null ? '' : ` di ${fmtNum(age.maxHold, 0)}`}`}${last && last.t ? ` · prezzo: chiusura del ${fmtDayMonth(last.t, true)}` : ''}` })),
        entry.host));
      requestAnimationFrame(() => entry.ruler.update({ trade: t, last: last && last.c }));
    }
    tradesBox.replaceChildren(...(anomalies.length ? [h('div', { class: 'verdict verdict--crit', role: 'alert' }, h('b', { text: 'Dati non attuali. ' }), `${anomalies.join('; ')}. R e distanze qui sotto valgono a quella data.`)] : []), ...nodes);
    tradesBox.classList.toggle('is-stale', anomalies.length > 0);
    const one = open[0];
    pTrades.setAsk(open.length === 1 ? `C'è una scommessa aperta su ${str(one.symbol)}: al massimo può perdere ${fmtMoney(num(one.margin), ccy)} (il margine).` : `Ci sono ${fmtNum(open.length, 0)} scommesse aperte: insieme rischiano ${fmtMoney(risk, ccy)} agli stop.`);
    pTrades.setFoot(h('a', { class: 'linkrow linkrow--primary', href: '#/mercati' }, 'Apri il grafico in Mercati', icon('arrow')));
  }

  function paintCone() {
    const { snap, quant4, quant4Status } = ctxNow;
    const c = obj(obj(quant4).paper_profile_cone);
    const months = arr0(c.months);
    if (!months.length || !Array.isArray(c.p50)) {
      coneHost.hidden = true;
      coneBig.replaceChildren();
      pCone.body.replaceChildren(emptyState(quant4Status === 'loading' ? 'Ricerca in lettura…' : 'Cono dell\'atteso non disponibile', 'Manca il Monte Carlo del profilo del paper (research/v5/quant_v4.json, paper_profile_cone).'));
      return;
    }
    if (!coneHost.isConnected) pCone.body.replaceChildren(coneBig, coneHost);
    coneHost.hidden = false;
    const gate = arr(snap.gates).find((g) => /giorni di paper/i.test(str(g.name)));
    const curve = curveOf(snap);
    const days = gate && num(gate.value) != null ? Math.min(curve.t.length - 1, Math.max(0, Math.round(gate.value))) : 0;
    const horizon = Math.min(months.length - 1, Math.max(3, Math.ceil(days / 30.44) + 2));
    const grid = 10;                                           // dieci punti per mese: il percorso giornaliero si vede
    const x = Array.from({ length: horizon * grid + 1 }, (_, i) => i / grid);
    const at = (arr2) => x.map((m) => { const i = Math.min(months.length - 2, Math.floor(m)); return arr2[i] + (arr2[i + 1] - arr2[i]) * (m - i); });
    const [p05, p25, p50, p75, p95] = ['p05', 'p25', 'p50', 'p75', 'p95'].map((k) => at(c[k].map(Number)));
    const path = x.map(() => null);
    let pctNow = null;
    if (days >= 1) {
      const i0 = curve.t.length - 1 - days;
      for (let k = 0; k <= days; k++) { const idx = Math.round((k / 30.44) * grid); if (idx < path.length) path[idx] = curve.equity[i0 + k] / curve.equity[i0]; }
      let lastIdx = -1;
      path.forEach((v, i) => { if (v != null) lastIdx = i; });
      for (let i = 1; i < lastIdx; i++) if (path[i] == null) { let a = i - 1; let b = i + 1; while (path[b] == null) b++; path[i] = path[a] + (path[b] - path[a]) * ((i - a) / (b - a)); }
      const v = path[lastIdx];
      const qs = [[0.05, p05[lastIdx]], [0.25, p25[lastIdx]], [0.5, p50[lastIdx]], [0.75, p75[lastIdx]], [0.95, p95[lastIdx]]];
      if (v <= qs[0][1]) pctNow = 0.05; else if (v >= qs[4][1]) pctNow = 0.95;
      else for (let i = 0; i < 4; i++) if (v >= qs[i][1] && v <= qs[i + 1][1]) pctNow = qs[i][0] + (qs[i + 1][0] - qs[i][0]) * ((v - qs[i][1]) / ((qs[i + 1][1] - qs[i][1]) || 1));
    }
    const demo = provOf(snap.meta) === 'demo';
    pCone.setProv(provTag('sim', 'Sim fascia'), provTag(demo ? 'demo' : 'paper', demo ? 'Esempio linea' : 'Paper linea'));
    const where = pctNow == null ? '' : pctNow <= 0.05 ? 'sotto la fascia' : pctNow >= 0.95 ? 'sopra la fascia' : pctNow < 0.5 ? 'dentro la fascia, sotto la mediana' : 'dentro la fascia, sopra la mediana';
    coneBig.replaceChildren(pctNow == null ? 'troppo presto' : `${pctNow <= 0.05 ? '≤ 5' : pctNow >= 0.95 ? '≥ 95' : fmtNum(pctNow * 100, 0)}°`, h('small', { class: 'bignum__sub', text: pctNow == null ? 'serve almeno un giorno di paper' : `percentile: ${where}` }));
    pCone.setAsk(pctNow == null ? 'Il paper è appena partito: per ora si vede solo ciò che le simulazioni si aspettano.' : pctNow > 0.05 && pctNow < 0.95 ? 'Stiamo andando come le simulazioni dicevano.' : 'Siamo fuori da ciò che le simulazioni consideravano normale: da guardare.');
    cone.update({
      x, height: 132, xHead: 'Mese', xFormat: (m) => `mese ${fmtNum(m, 1)}`, xTicks: Array.from({ length: horizon + 1 }, (_, i) => ({ t: i, label: i === 0 ? 'avvio' : `${i} m` })),
      bands: [{ lo: p05, hi: p95, name: '5°–95° percentile' }, { lo: p25, hi: p75, name: '25°–75° percentile' }],
      lines: [{ values: p50, cls: 'median', name: 'Mediana simulata' }, { values: path, cls: 'paper', name: demo ? 'Conto (esempio)' : 'Conto in paper' }],
      format: (v) => fmtPctSigned(v - 1, 0), refs: [{ value: 1, label: '' }],
    });
    // freschezza per fonte: la fascia è la ricerca (statica, datata), la linea è la fotografia del conto
    const gen = parseTs(str(quant4.generated).replace(' ', 'T').replace(/(\.\d+)?\+00:00$/, 'Z'));
    pCone.setFoot(freshLine([{ name: 'fascia', text: gen == null ? 'ricerca senza data' : `ricerca del ${fmtDayMonth(gen)}` }, { name: 'linea', text: ctxNow.fresh ? `fotografia del conto, giorno ${fmtNum(days, 0)} di paper` : 'fotografia ferma', stale: !ctxNow.fresh }]),
      h('span', { class: 'not-semplice', text: `${fmtNum(c.paths, 0)} percorsi · ${str(c.method)}` }));
    coneHost.classList.toggle('is-stale', !ctxNow.fresh);
  }
  const arr0 = (v) => (Array.isArray(v) ? v : []);

  function paintCmp() {
    if (cmp === undefined) { cmpHost.hidden = true; cmpBig.replaceChildren('…'); return; }
    // Il fondo contro S&P 500 e Bitcoin negli stessi giorni (colonne spy / btc del confronto) e, se c'è, contro il sistema originale.
    const rows = arr(obj(cmp).rows).map((r) => ({ t: parseTs(str(r.data)), a: num(r.nuovo_totale), b: num(r.legacy_nav), f: num(r.legacy_flusso) || 0, spy: num(r.spy), btc: num(r.btc) }))
      .filter((r) => r.t != null && r.a).sort((p, c) => p.t - c.t);
    const n = rows.length;
    if (n < 2) {
      cmpHost.hidden = true;
      cmpBig.replaceChildren(n ? '1 giorno' : 'n.d.', h('small', { class: 'bignum__sub', text: n ? 'il confronto parte dal secondo giorno' : 'nessuna riga ancora' }));
      pCmp.setAsk(cmp ? 'Il confronto con S&P 500 e Bitcoin si riempie da solo: il motore scrive una riga al giorno con il patrimonio del fondo e le chiusure dei due mercati.' : 'Il confronto giornaliero non è ancora stato scritto dal motore: arriverà con il primo «python -m gerva daily».');
      pCmp.setProv(cmp && cmp.example ? provTag('demo') : null);
      pCmp.setFoot();
      return;
    }
    cmpHost.hidden = false;
    const x = rows.map((r) => r.t);
    const a = rows.map((r) => (r.a / rows[0].a) * 100);
    const rebase = (key) => { const i0 = rows.findIndex((r) => r[key]); return i0 < 0 ? null : rows.map((r, i) => (i < i0 || !r[key] ? null : (r[key] / rows[i0][key]) * 100)); };
    const spy = rebase('spy');
    const btc = rebase('btc');
    const hasOrig = rows.filter((r) => r.b).length >= 2;
    let acc = 100;
    const b = hasOrig ? rows.map((r, i) => { if (!r.b) return null; if (i > 0 && rows[i - 1].b) acc *= (r.b - r.f) / rows[i - 1].b; return acc; }) : null;      // i versamenti non sono rendimento
    const last = (v) => (v ? [...v].reverse().find((y) => y != null) : null);
    const ret = (v) => { const y = last(v); return y == null ? null : y / 100 - 1; };
    const days = Math.round((x[n - 1] - x[0]) / 86400000);
    pCmp.setProv(provTag(cmp.example ? 'demo' : 'paper'));
    const fund = ret(a);
    cmpBig.replaceChildren(fmtPctSigned(fund, 1), h('small', { class: 'bignum__sub', text: `il fondo in ${fmtNum(days, 0)} ${days === 1 ? 'giorno' : 'giorni'} · S&P 500 ${ret(spy) == null ? 'n.d.' : fmtPctSigned(ret(spy), 1)} · Bitcoin ${ret(btc) == null ? 'n.d.' : fmtPctSigned(ret(btc), 1)}${hasOrig ? ` · originale ${fmtPctSigned(ret(b), 1)}` : ''}` }));
    pCmp.setAsk(days < 30
      ? `Solo ${fmtNum(days, 0)} ${days === 1 ? 'giorno' : 'giorni'}: troppo pochi per dire chi va meglio. In poche settimane un mercato può salire o scendere del 10% per caso; il confronto conta dopo mesi.`
      : 'Stessi giorni, base 100 al primo giorno comune. Il fondo non cerca di battere un mercato in ogni periodo: conta il rendimento per il rischio preso, nello spazio Evidenza.');
    const series = [
      spy ? { values: spy, cls: 'bench', end: true, name: 'S&P 500' } : null,
      btc ? { values: btc, cls: 'c3', end: true, name: 'Bitcoin' } : null,
      b ? { values: b, cls: 'orig', end: true, name: 'Originale' } : null,
      { values: a, cls: 'fund', end: true, name: 'Fondo' }].filter(Boolean);
    const val = (v, i) => (v && v[i] != null ? fmtNum(v[i], 1) : '—');
    cmpChart.update({
      x,
      panels: [{ height: 116, series, format: (v) => fmtNum(v, 0), refs: [{ value: 100, label: 'base 100' }] }],
      tip: (i) => ({ title: fmtDate(x[i], true), rows: [{ key: 'fund', label: 'Fondo', value: val(a, i) }, spy ? { key: 'bench', label: 'S&P 500', value: val(spy, i) } : null, btc ? { key: 'c3', label: 'Bitcoin', value: val(btc, i) } : null, b ? { key: 'orig', label: 'Sistema originale', value: val(b, i) } : null].filter(Boolean) }),
    });
    // freschezza: il confronto è una fonte a sé, scritta una volta al giorno; oltre l'età massima lo si dichiara
    const fr = freshness(x[n - 1], ctxNow.now, 'ibkr', obj(obj(ctxNow.health).rules));
    cmpHost.classList.toggle('is-stale', fr.stale === true);
    if (fr.stale) cmpBig.replaceChildren('Fermo', h('small', { class: 'bignum__sub', text: `ultima riga del ${fmtDayMonth(x[n - 1], true)}: il confronto non è aggiornato` }));
    const key = (cls, text) => h('span', { class: 'legend__item' }, h('span', { class: `key key--${cls}`, 'aria-hidden': 'true' }), ` ${text}`);
    pCmp.setFoot(freshLine([{ name: 'confronto', text: `ultima riga del ${fmtDayMonth(x[n - 1], true)}`, stale: fr.stale === true }]),
      key('fund', 'fondo'), spy ? key('bench', 'S&P 500') : null, btc ? key('c3', 'Bitcoin') : null, b ? key('orig', 'originale') : null,
      hasOrig ? ' · base 100 al primo giorno comune · il test contro l\'originale è in Evidenza' : ' · base 100 al primo giorno · il sistema originale non ha ancora righe');
  }

  function paintGates() {
    const { snap } = ctxNow;
    const gates = arr(snap.gates);
    if (!gates.length) { gatesBig.replaceChildren('n.d.'); gatesBox.replaceChildren(emptyState('Cancelli non dichiarati', 'La fotografia non riporta i cancelli tra paper e denaro reale.')); return; }
    const ok = gates.filter((g) => g.ok === true).length;
    gatesBig.replaceChildren(`${fmtNum(ok, 0)} di ${fmtNum(gates.length, 0)}`, h('small', { text: 'cancelli superati' }));
    // tutti i cancelli, nell'ordine del motore: superato, in corso (con la barra se è un conteggio) o non ancora misurabile
    gatesBox.replaceChildren(h('ul', { class: 'gates' }, gates.map((g) => {
      const v = num(g.value);
      const target = num(g.target);
      const unit = str(g.unit);
      const fmt = (x) => (unit === '%' ? fmtPct(x, Math.abs(x * 100 - Math.round(x * 100)) < 0.05 ? 0 : 1) : unit === 'x' ? `${fmtNum(x, 1)}x` : fmtNum(x, Number.isInteger(x) ? 0 : 2));
      const state = g.ok === true ? 'ok' : v == null ? 'none' : 'run';
      const count = state === 'run' && target > 0 && v >= 0 && v < target && unit !== '%';
      const bar = count ? h('span', { class: 'gate__bar', 'aria-hidden': 'true' }, h('i')) : null;
      if (bar) bar.style.setProperty('--v', `${Math.max(2, Math.min(100, (v / target) * 100)).toFixed(1)}%`);
      return h('li', { class: 'gate', dataset: { state } },
        state === 'ok' ? icon('check-circle', 'icon--sm') : h('span', { class: 'gate__dot', 'aria-hidden': 'true' }),
        h('span', { class: 'gate__name', text: str(g.name).replace(/\s*\(.*\)$/, '').replace(/([aeiou])'(?=\s|$)/g, (m, c) => ({ a: 'à', e: 'è', i: 'ì', o: 'ò', u: 'ù' })[c]) }),
        h('span', { class: 'gate__val num', text: v == null ? 'non ancora misurabile' : target == null ? fmt(v) : count ? `${fmt(v)} / ${fmt(target)}` : `${fmt(v)} · soglia ${fmt(target)}` }),
        h('span', { class: 'sr-only', text: state === 'ok' ? ' (superato)' : state === 'none' ? ' (non ancora misurabile)' : ' (in corso)' }), bar);
    })));
    const miss = gates.find((g) => g.ok !== true && /giorni di paper/i.test(str(g.name)));
    pGates.setAsk(ok === gates.length ? 'Tutti i cancelli sono verdi: il passaggio al denaro reale è una decisione del proprietario.' : `Mancano ${miss && num(miss.target) != null ? `${fmtNum(miss.target - miss.value, 0)} giorni e ` : ''}${fmtNum(gates.length - ok, 0)} prove prima di poter usare denaro vero.`);
    pGates.setProv(provTag(provOf(snap.meta)));
  }

  function paintAll() {
    paintNav();
    paintBrake();
    paintAttr();
    paintChanges();
    paintTrades();
    paintCone();
    paintCmp();
    paintGates();
  }

  getTradebook().then((res) => { tb = res || null; if (ctxNow) { paintNav(); paintBrake(); paintChanges(); paintTrades(); } });
  getCompare().then((res) => { cmp = res || null; if (ctxNow) paintCmp(); });

  return {
    update(ctx) {
      ctxNow = ctx;
      paintAll();
    },
    summary(ctx) {
      const snap = ctx.snap;
      const nav = obj(snap.nav);
      const rs = riskState(snap.risk);
      if (!ctx.fresh) return 'Non so dirti com\'è adesso: i dati sono fermi. Qui sotto c\'è l\'ultima fotografia ricevuta.';
      const day = num(nav.pnl_day);
      const sg = sigmaDay(snap);
      const z = sg ? sg.z : null;
      const sigmaWord = () => sg.word;
      const comps = arr(obj(snap.system).components);
      const bad = comps.filter((c) => !/^(ok|up|healthy)$/i.test(str(c.status)));
      return `Il conto vale ${fmtMoney(totalNav(snap, tb).total, ctx.ccy, { digits: 0 })}, oggi ha ${day == null ? 'un risultato non disponibile' : day >= 0 ? `guadagnato ${fmtMoney(day, ctx.ccy, { digits: 0 })}` : `perso ${fmtMoney(Math.abs(day), ctx.ccy, { digits: 0 })}`}${z == null ? '' : ` ed è ${sigmaWord(z)}`}. `
        + `${bad.length ? `Da guardare: ${str(bad[0].name)}` : 'Il sistema gira'}, i dati sono di adesso e ${rs.code === 'NORMAL' ? 'nessun freno è tirato' : `il motore di rischio è in stato ${rs.label}`}.`;
    },
  };
}
