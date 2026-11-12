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
import { brakes, freshness, sigmaDay, totalNav, tradeAge, tradeR } from '../derive.js';
import { brakeLadder, emptyState, meterRow, panel, provOf, provTag, rollNumber, tradeRuler } from '../panels.js';

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

export function mount(root, api) {
  let range = '3M';
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
  const side = h('dl', { class: 'hero__side' });
  const chartHost = h('div', { class: 'chart-host' });
  const chartNote = h('span');
  const rangeSeg = segmented({ label: 'Intervallo del grafico', options: [{ value: '1M', label: '1M' }, { value: '3M', label: '3M' }, { value: '1A', label: '1A' }, { value: 'ALL', label: 'Avvio' }], value: range, onChange: (v) => { range = v; paintNav(); } });
  pNav.body.append(h('div', { class: 'hero' },
    h('div', { class: 'hero__main' }, h('div', { class: 'hero__num num' }, heroNum, heroDec, heroCur), delta, ctxLine, books, side),
    h('div', { class: 'hero__chart' }, h('div', { class: 'hero__chart-head' }, chartNote, rangeSeg.el), chartHost)));
  const navChart = timeChart(chartHost, { label: 'Patrimonio e, sotto, caduta dal massimo' });

  // ---- 2. freni -------------------------------------------------------------------------------------------------------------
  const pBrake = panel({ title: 'Quanto manca ai freni', span: 4, what: 'Il motore di rischio riduce da solo le posizioni quando il conto scende troppo dal suo massimo. Qui vedi quanti punti mancano al primo scalino e che cosa succede a ognuno. La scala completa, con le perdite a 24 ore e 7 giorni, è nello spazio Rischio.' });
  const brakeBig = h('div', { class: 'bignum' });
  const brakeHost = h('div', { class: 'chart-host' });
  const brakeKv = h('div', { class: 'kv' });
  pBrake.body.append(brakeBig, brakeHost, brakeKv);
  const ladder = brakeLadder(brakeHost, { compact: true, label: 'Distanza dai freni automatici' });
  pBrake.setFoot(h('a', { class: 'linkrow', href: '#/rischio' }, 'Scala completa in Rischio', icon('arrow')));

  // ---- 3. da dove viene il risultato --------------------------------------------------------------------------------------
  const periodSeg = segmented({ label: 'Periodo', options: [{ value: 'day', label: 'Oggi' }, { value: 'mtd', label: 'Mese' }, { value: 'total', label: 'Dall\'avvio' }], value: period, onChange: (v) => { period = v; paintAttr(); } });
  const pAttr = panel({ title: 'Da dove viene il risultato', span: 4, tools: periodSeg.el, what: 'Il guadagno o la perdita del periodo, diviso tra le strategie. Ogni barra parte da dove finisce la precedente: l\'ultima è il totale. «Non attribuito» è la parte che la somma delle strategie non spiega: se supera un punto base viene segnalata.' });
  const attrHost = h('div', { class: 'chart-host' });
  const attrNote = h('p', { class: 'panel__ask' });
  pAttr.body.append(attrHost, attrNote);
  const attrChart = waterfall(attrHost, [], { label: 'Contributo delle strategie al risultato', orient: 'h', format: (v) => fmtMoney(v, 'EUR', { digits: 2, signed: true }), levelFormat: (v) => fmtMoney(v, 'EUR', { digits: 0 }), valueHead: 'Contributo', levelHead: 'Somma' });

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
  const pCmp = panel({ title: 'Confronto con il sistema originale', span: 4, what: 'Il nuovo sistema e quello originale del proprietario, partiti da 100 nel primo giorno in comune. Pochi giorni non bastano a dire chi è meglio: la differenza va letta insieme al numero di giorni osservati. Il test statistico completo (imbuto del caso) è nello spazio Evidenza.' });
  const cmpBig = h('div', { class: 'bignum' });
  const cmpHost = h('div', { class: 'chart-host' });
  pCmp.body.append(cmpBig, cmpHost);
  const cmpChart = timeChart(cmpHost, { label: 'Nuovo sistema e sistema originale a base 100' });

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
    const start = num(nav.start_equity);
    const well = (k, v, sub) => h('div', { class: 'mini' }, h('dt', { text: k }), h('dd', { class: v > 0 ? 'pos' : v < 0 ? 'neg' : '' }, v == null ? 'n.d.' : [v === 0 ? null : icon(v > 0 ? 'up' : 'down', 'icon--solid'), fmtPctSigned(v, 2)]), h('small', { class: 'not-terminale' }, sub));
    side.replaceChildren(well('Mese', num(nav.pnl_mtd_pct), 'dal primo del mese'), well('Anno', num(nav.pnl_ytd_pct), 'dal 1° gennaio'), well('Dall\'avvio', num(nav.pnl_total_pct), start == null ? '' : `da ${fmtMoney(start, ccy, { digits: 0 })}`));

    const curve = curveOf(snap);
    const n = curve.t.length;
    if (n < 2) { navChart.update(null); chartNote.textContent = 'La curva comparirà dopo i primi due giorni di storico.'; return; }
    const months = { '1M': 1, '3M': 3, '1A': 12, ALL: null }[range];
    let i0 = 0;
    if (months) { const end = new Date(curve.t[n - 1]); const cut = Date.UTC(end.getUTCFullYear(), end.getUTCMonth() - months, end.getUTCDate()); while (i0 < n - 2 && curve.t[i0] < cut) i0++; }
    const x = curve.t.slice(i0);
    const e = curve.equity.slice(i0);
    const dd = curve.dd.slice(i0);
    const cls = prov === 'demo' ? 'fund demo' : prov === 'sim' ? 'fund sim' : 'fund';
    chartNote.textContent = `${fmtDate(x[0], true)} – ${fmtDate(x[x.length - 1], true)}`;
    navChart.update({
      x,
      panels: [
        { height: ctxNow.lv === 'terminale' ? 96 : 184, series: [{ values: e, cls, area: true, end: true, name: 'Patrimonio' }], format: (v) => fmtNum(v, 0) },
        { height: 36, title: 'Caduta dal massimo', top: 0, series: [{ values: dd, cls: 'dd', area: true, name: 'Caduta' }], format: (v) => fmtPct(v, 0), refs: arr(obj(snap.risk).dd_ladder).filter((st) => num(st.level) != null && st.level >= Math.min(...dd.filter((v) => v != null)) * 1.6).map((st) => ({ value: st.level, label: fmtPct(st.level, 0) })) },
      ],
      tip: (i) => ({ title: fmtDate(x[i], true), rows: [{ key: 'fund', label: 'Patrimonio', value: fmtMoney(e[i], ccy) }, { key: 'dd', label: 'Caduta dal massimo', value: dd[i] == null ? '—' : fmtPctSigned(dd[i], 2) }] }),
      say: (i) => `${fmtDate(x[i], true)}: patrimonio ${fmtMoney(e[i], ccy)}, caduta dal massimo ${dd[i] == null ? 'non disponibile' : fmtPctSigned(dd[i], 2)}`,
    });
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
      attrNote.replaceChildren('Nessun contributo da mostrare per questo periodo: la fotografia non riporta il P&L per strategia.');
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
    for (const e of arr(obj(tb).log).slice(-3)) { const t = parseTs(e.day); if (t != null && t >= since - DAY) list.push({ t, kind: '', k: 'Trade', text: str(e.msg || e.event), dayOnly: true }); }
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
    pTrades.setFoot(h('a', { class: 'linkrow', href: '#/mercati' }, 'Grafico e libro in Mercati', icon('arrow')));
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
    pCone.setFoot(`${fmtNum(c.paths, 0)} percorsi · ${str(c.method)}`);
  }
  const arr0 = (v) => (Array.isArray(v) ? v : []);

  function paintCmp() {
    const { snap } = ctxNow;
    if (cmp === undefined) { cmpHost.hidden = true; cmpBig.replaceChildren('…'); return; }
    const rows = arr(obj(cmp).rows).map((r) => ({ t: parseTs(str(r.data)), a: num(r.nuovo_totale), b: num(r.legacy_nav), f: num(r.legacy_flusso) || 0 })).filter((r) => r.t != null && r.a != null && r.b != null);
    if (rows.length < 3) {
      cmpHost.hidden = true;
      cmpBig.replaceChildren('n.d.');
      pCmp.setAsk(cmp ? 'Servono almeno 3 giorni in comune tra i due conti.' : 'Il confronto giornaliero con il conto originale non è ancora stato scritto dal motore.');
      pCmp.setProv();
      return;
    }
    cmpHost.hidden = false;
    const x = rows.map((r) => r.t);
    const a = rows.map((r) => (r.a / rows[0].a) * 100);
    let acc = 100;
    const b = rows.map((r, i) => { if (i > 0 && rows[i - 1].b) acc *= (r.b - r.f) / rows[i - 1].b; return acc; });      // i versamenti non sono rendimento
    const n = rows.length;
    const diff = a[n - 1] - b[n - 1];
    pCmp.setProv(provTag(cmp.example ? 'demo' : 'paper'));
    cmpBig.replaceChildren('In corso', h('small', { class: 'bignum__sub', text: `${fmtNum(n, 0)} giorni comuni · distacco ${fmtSigned(diff, 1)} punti` }));
    pCmp.setAsk('Per ora nessuno dei due batte l\'altro: servono ancora molti giorni per saperlo.');
    cmpChart.update({
      x,
      panels: [{ height: 116, series: [{ values: b, cls: 'orig', end: true, name: 'Originale' }, { values: a, cls: 'fund', end: true, name: 'Nuovo' }], format: (v) => fmtNum(v, 0), refs: [{ value: 100, label: 'base 100' }] }],
      tip: (i) => ({ title: fmtDate(x[i], true), rows: [{ key: 'fund', label: 'Nuovo sistema', value: fmtNum(a[i], 1) }, { key: 'orig', label: 'Sistema originale', value: fmtNum(b[i], 1) }, { label: 'Distacco', value: `${fmtSigned(a[i] - b[i], 1)} punti` }] }),
    });
    pCmp.setFoot(h('span', { class: 'legend__item' }, h('span', { class: 'key key--fund', 'aria-hidden': 'true' }), ' nuovo'), h('span', { class: 'legend__item' }, h('span', { class: 'key key--orig', 'aria-hidden': 'true' }), ' originale'), ' · base 100 al primo giorno comune · il test completo è in Evidenza');
  }

  function paintGates() {
    const { snap } = ctxNow;
    const gates = arr(snap.gates);
    if (!gates.length) { gatesBig.replaceChildren('n.d.'); gatesBox.replaceChildren(emptyState('Cancelli non dichiarati', 'La fotografia non riporta i cancelli tra paper e denaro reale.')); return; }
    const ok = gates.filter((g) => g.ok === true).length;
    gatesBig.replaceChildren(`${fmtNum(ok, 0)} di ${fmtNum(gates.length, 0)}`, h('small', { text: 'cancelli superati' }));
    const open = gates.filter((g) => g.ok !== true && num(g.value) != null && num(g.target) > 0).slice(0, 3);
    gatesBox.replaceChildren(...open.map((g) => meterRow({ name: str(g.name).replace(/\s*\(.*\)$/, ''), value: g.value, cap: g.target, scale: g.target * 1.05, state: 'ok', text: `${fmtNum(g.value, 0)} / ${fmtNum(g.target, 0)}` })));
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
