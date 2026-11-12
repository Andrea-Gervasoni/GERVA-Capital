// Spazio «Rischio»: che cosa può andare storto e chi frena. Una pagina sola, in quest'ordine:
// stato e scala dei freni (unica, con 24 ore e 7 giorni) · il peggio di oggi · tetti di esposizione · leva e volatilità ·
// stress sulle giornate storiche · dati e ordini · avvisi · rimando al KILL · statistiche.
// Soglie e tetti arrivano dalla fotografia (risk.dd_ladder, risk.limits): se mancano si scrive «soglia non letta».

import { histogram } from '../charts.js';
import { h, icon } from '../dom.js';
import { arr, fmtAgo, fmtDate, fmtDayTime, fmtMoney, fmtNum, fmtPct, fmtPctSigned, num, obj, parseTs, str } from '../format.js';
import { getOhlc, getTradebook } from '../market.js';
import { alertLevel, componentStatus, curveOf, limitStatus, riskState, utilization } from '../model.js';
import { brakeLadder, emptyState, meterRow, panel, provOf, provTag } from '../panels.js';
import { ladderData } from './oggi.js';

const DAY = 86400000;
const SCALE = { NORMAL: '1,0', REDUCED: '0,5', HALTED: '0,25', KILLED: '0' };
/** Fondi europei dell'esempio → ETF americano equivalente nella tabella degli shock (dichiarato nel piede del riquadro). */
const PROXY = { CSPX: 'SPY', EQQQ: 'QQQ', SGLN: 'GLD', IBTM: 'IEF', EXS1: 'EFA' };

/** Una giornata storica applicata alle posizioni di oggi: { pnl (frazione del patrimonio), covered, missing[], proxies[] }. */
export function applyStress(day, positions, equity) {
  const shocks = obj(day && day.shocks);
  let pnl = 0;
  let covered = 0;
  const missing = [];
  const proxies = [];
  for (const p of positions) {
    const w = num(p.weight) ?? (num(p.value) != null && equity ? p.value / equity : null);
    if (w == null) continue;
    const sym = str(p.symbol).toUpperCase();
    const key = shocks[sym] != null ? sym : PROXY[sym] && shocks[PROXY[sym]] != null ? PROXY[sym] : null;
    if (!key) { missing.push(sym); continue; }
    if (key !== sym) proxies.push(`${sym}→${key}`);
    pnl += w * shocks[key];
    covered += Math.abs(w);
  }
  return { pnl, covered, missing, proxies };
}

export function mount(root, api) {
  let ctxNow = null;
  let tb;
  const lastClose = new Map();

  // ---- stato e freni ----
  const pBrake = panel({ title: 'Quanto manca a ogni freno, e fin dove arriverebbe il peggior caso di oggi?', eyebrow: 'Stato e freni', span: 8, id: 'freni',
    ask: 'Lo zero è a sinistra: più un segno va a destra, più si è perso. Le tacche sono i freni automatici del motore, con scritto che cosa fanno. Il rombo tratteggiato è il peggio che può succedere oggi, sulla stessa scala.',
    what: 'Il motore di rischio decide per ultimo. Se il conto scende dal suo massimo oltre uno scalino, dimezza, poi riduce a un quarto, poi chiude tutto. Due freni più rapidi guardano le perdite delle ultime 24 ore e degli ultimi 7 giorni. Le soglie sono quelle della configurazione del motore, lette dalla fotografia.' });
  const stateLine = h('div', { class: 'statusline' });
  const ladderHost = h('div', { class: 'chart-host' });
  const tableHost = h('div', { class: 'table-wrap not-semplice' });
  pBrake.body.append(stateLine, ladderHost, tableHost);
  const ladder = brakeLadder(ladderHost, { label: 'Scala dei freni: caduta dal massimo, ultime 24 ore, ultimi 7 giorni' });

  // ---- il peggio di oggi ----
  const pWorst = panel({ title: 'Il peggio di oggi', span: 4, id: 'peggio',
    ask: 'Stop saltati, sede irraggiungibile e la peggiore giornata storica sul libro di oggi, tutti insieme.',
    what: 'Un\'ipotesi, non una previsione: tutti i trade a leva perdono fino al margine isolato (il massimo che possono perdere) e il libro giornaliero subisce la peggiore delle giornate storiche di stress, applicata alle posizioni di oggi. Serve a vedere quale freno scatterebbe.' });
  const worstKv = h('div', { class: 'kv' });
  const worstVerdict = h('div', { class: 'verdict' });
  pWorst.body.append(worstKv, worstVerdict);

  // ---- tetti ----
  const pCaps = panel({ title: 'Tetti di esposizione', span: 4, id: 'tetti', ask: 'La tacca bianca è il tetto: la barra non deve superarla.',
    what: 'Quanta parte del patrimonio è esposta su una sede o su un singolo strumento, contro il tetto fissato nella configurazione. Sopra il 90% del tetto la barra diventa ambra: il motore rifiuta gli ordini che lo supererebbero.' });
  const capsBox = h('div');
  pCaps.body.append(capsBox);

  // ---- leva e volatilità ----
  const pLev = panel({ title: 'Leva e volatilità', span: 4, id: 'leva', ask: 'Leva del conto e leva del singolo trade sono due numeri diversi: non stanno mai nella stessa cifra.',
    what: 'La leva del conto è l\'esposizione totale divisa per il patrimonio. La leva del trade riguarda solo il margine isolato di una scommessa: è alta perché blocca poco denaro, ma la perdita massima resta il margine. La volatilità realizzata si confronta con l\'obiettivo del fondo.' });
  const levBox = h('div');
  pLev.body.append(levBox);

  // ---- stress ----
  const pStress = panel({ title: 'Stress: le giornate storiche sul libro di oggi', span: 4, id: 'stress', ask: 'Che cosa succederebbe alle posizioni di oggi se si ripetesse una di queste giornate. La tacca ambra è il freno delle 24 ore.',
    what: 'Rendimenti veri di ogni strumento in quattro giornate di crisi, applicati ai pesi di oggi. Per i trade a leva conta il minimo toccato durante il giorno: se supera lo stop o la liquidazione il trade si chiude lì. È un calcolo su prezzi storici: SIMULATO.' });
  const stressBox = h('div');
  pStress.body.append(stressBox);

  // ---- dati e ordini ----
  const pData = panel({ title: 'Dati e ordini', span: 12, id: 'dati', what: 'La macchina che produce i numeri: componenti, età dei dati, errori e ordini in sospeso. Se qui qualcosa non è a posto, i numeri sopra possono non essere affidabili.' });
  const facts = h('div', { class: 'facts' });
  pData.body.append(facts);

  // ---- avvisi e KILL ----
  const pAlerts = panel({ title: 'Avvisi', span: 6, id: 'avvisi' });
  const alertsBox = h('div', { class: 'alerts' });
  const alertsBtn = h('button', { class: 'btn btn--sm btn--ghost', type: 'button' }, icon('bell', 'icon--sm'), 'Apri il centro avvisi');
  alertsBtn.addEventListener('click', () => api.openAlerts());
  pAlerts.body.append(alertsBox);
  pAlerts.setFoot(alertsBtn);
  const pKill = panel({ title: 'Arresto di emergenza', span: 6, id: 'kill', what: 'Il KILL crea un file sul server: al ciclo successivo il motore chiude tutte le posizioni, anche i trade a leva aperti, e si ferma. È un comando a senso unico, protetto da token e conferma. Il pulsante è sempre in alto a destra, in ogni spazio.' });
  const killText = h('p', { class: 'panel__ask' });
  const killBtn = h('button', { class: 'btn btn--sm btn--ghost', type: 'button' }, icon('power', 'icon--sm'), 'Apri la finestra del KILL (non invia)');
  killBtn.addEventListener('click', () => api.openKill());
  pKill.body.append(killText);
  pKill.setFoot(killBtn, h('span', { text: 'Scorciatoia: Maiusc K' }));

  // ---- statistiche ----
  const pStats = panel({ title: 'Quanto si perde in un giorno normale?', eyebrow: 'Statistiche', span: 12, cls: 'not-semplice', id: 'statistiche',
    what: 'La distribuzione dei rendimenti giornalieri del conto. Il VaR al 95% è la perdita che si supera un giorno su venti; l\'ES è la perdita media in quei giorni peggiori.' });
  const statsFacts = h('div', { class: 'facts' });
  const histHost = h('div', { class: 'chart-host' });
  pStats.body.append(statsFacts, histHost);

  root.append(h('div', { class: 'ws' }, pBrake.el, pWorst.el, pCaps.el, pLev.el, pStress.el, pData.el, pAlerts.el, pKill.el, pStats.el));

  // ---- calcoli condivisi ----
  function tradesAtRisk() {
    const open = Object.values(obj(obj(tb).open)).filter((t) => t && typeof t === 'object');
    const stops = open.reduce((a, t) => a + (num(t.risk) || 0), 0);
    const margins = open.reduce((a, t) => a + (num(t.margin) || 0), 0);
    return { open, stops, beyond: Math.max(0, margins - stops) };
  }
  function stressDays() {
    const { snap, quant4 } = ctxNow;
    const days = arr(obj(obj(quant4).stress_days).days);
    const eq = num(obj(snap.nav).equity);
    return days.map((d) => ({ day: d, ...applyStress(d, arr(snap.positions), eq) }));
  }

  function paintBrake() {
    const { snap, ccy, fresh } = ctxNow;
    const risk = obj(snap.risk);
    const rs = riskState(risk);
    const nav = obj(snap.nav);
    const prov = provOf(snap.meta);
    pBrake.setProv(provTag(prov), provTag('sim', 'Peggior caso: ipotesi'));
    const worst = worstCase();
    const d = ladderData(ctxNow, tb, worst && worst.loss > 0 ? { loss: worst.loss } : null);
    stateLine.replaceChildren(
      h('span', { class: `pill pill--lg pill--${!fresh ? 'unknown' : rs.code === 'KILLED' ? 'killed' : rs.kind}` }, icon(!fresh ? 'help' : rs.icon), h('span', { text: !fresh ? 'Sconosciuto' : rs.label })),
      h('span', null, 'scala ', h('b', { text: fresh ? SCALE[rs.code] || 'n.d.' : 'n.d.' })),
      h('span', { text: fresh ? str(risk.state_reason).trim() || rs.text : 'I dati sono fermi: lo stato qui sopra non si può confermare.' }),
      h('span', null, 'caduta ', h('b', { text: num(nav.drawdown_pct) == null ? 'n.d.' : fmtPctSigned(nav.drawdown_pct, 2) }), num(nav.high_water) == null ? '' : ` dal massimo di ${fmtMoney(nav.high_water, ccy, { digits: 0 })}`));
    if (!d.steps.length) { ladderHost.replaceChildren(emptyState('Soglia non letta', 'La fotografia non riporta gli scalini della caduta (risk.dd_ladder): nessun valore predefinito viene usato al loro posto.')); tableHost.replaceChildren(); return; }
    ladder.update(d);

    // tabella dei tre freni: adesso, mancano, in euro, scatta a, giornate di ES, che cosa fa il motore
    const es = Math.abs(num(risk.es_95_1d_pct) || 0);
    const peak = num(nav.high_water);
    const eq = num(nav.equity);
    const rows = [];
    const first = d.steps[0];
    if (first && d.dd != null) rows.push({ name: `Caduta ${fmtPct(first.level, 0)}`, now: d.dd, dist: d.dd - first.level, base: peak, at: peak == null ? null : peak * (1 + first.level), action: first.action });
    for (const l of d.lanes) if (l.value != null) rows.push({ name: `${l.label.replace('Ultime', 'Perdita in').replace('Ultimi', 'Perdita in')} ${fmtPct(l.limit, 0)}`, now: l.value, dist: l.value - l.limit, base: eq, at: eq == null ? null : eq * (1 + (l.limit - Math.min(l.value, 0))), action: l.action });
    tableHost.replaceChildren(h('table', { class: 'table table--dense' },
      h('caption', { class: 'sr-only', text: 'I freni automatici: distanza da ognuno' }),
      h('thead', null, h('tr', null, ['Freno', 'Adesso', 'Mancano', 'In euro', 'Scatta a', 'Giornate di ES', 'Che cosa fa il motore'].map((c, i) => h('th', { scope: 'col', class: i && i < 6 ? 'is-num' : '', text: c })))),
      h('tbody', null, rows.map((r) => h('tr', null,
        h('td', { text: r.name }), h('td', { class: 'is-num', text: fresh ? fmtPctSigned(r.now, 2) : 'n.d.' }), h('td', { class: 'is-num', text: fresh ? `${fmtNum(r.dist * 100, 1)} punti` : 'sconosciuta' }),
        h('td', { class: 'is-num', text: fresh && r.base != null ? fmtMoney(r.dist * r.base, ccy, { digits: 0 }) : 'n.d.' }), h('td', { class: 'is-num', text: r.at == null ? 'n.d.' : fmtMoney(r.at, ccy, { digits: 0 }) }),
        h('td', { class: 'is-num', text: fresh && es ? fmtNum(r.dist / es, 1) : 'n.d.' }), h('td', { class: 'is-action', text: r.action || 'n.d.' }))))));
    pBrake.setFoot('Percentuali sul patrimonio del fondo. Scalini e freni letti dalla fotografia del motore. ', d.simRef ? 'Riferimento tratteggiato: caduta tipica nelle simulazioni del profilo del paper (SIMULATO). ' : '', 'Mancano nella fotografia: da quando lo stato è in vigore e la condizione di rientro (n.d.).');
  }

  /** Peggior caso di oggi: margini dei trade + peggiore giornata storica sul libro giornaliero. */
  function worstCase() {
    const { snap } = ctxNow;
    const eq = num(obj(snap.nav).equity);
    if (eq == null) return null;
    const tr = tb ? tradesAtRisk() : null;
    const days = stressDays();
    const worstDay = days.length ? days.reduce((a, b) => (b.pnl < a.pnl ? b : a)) : null;
    const gap = worstDay && worstDay.pnl < 0 ? -worstDay.pnl * eq : null;
    const total = (tr ? tr.stops + tr.beyond : 0) + (gap || 0);
    return { eq, tr, worstDay, gap, total, loss: total / eq };
  }

  function paintWorst() {
    const { snap, ccy, quant4Status } = ctxNow;
    const w = worstCase();
    pWorst.setProv(provTag('sim'));
    if (!w) { worstKv.replaceChildren(); worstVerdict.hidden = true; pWorst.body.prepend(emptyState('Patrimonio non disponibile')); return; }
    const row = (k, v, cls = '') => h('div', null, h('span', { class: 'k', text: k }), h('span', { class: `v ${cls}`.trim(), text: v }));
    worstKv.replaceChildren(
      row('Patrimonio di oggi', fmtMoney(w.eq, ccy, { digits: 0 })),
      row('Perdite agli stop', tb === undefined ? '…' : !w.tr ? 'n.d. (libro dei trade assente)' : fmtMoney(-w.tr.stops, ccy), 'neg'),
      row('Oltre lo stop, fino ai margini', tb === undefined ? '…' : !w.tr ? 'n.d.' : fmtMoney(-w.tr.beyond, ccy), 'neg'),
      row(w.worstDay ? `Libro giornaliero: ${str(w.worstDay.day.name)}` : 'Gap del libro giornaliero', w.gap == null ? (quant4Status === 'loading' ? '…' : 'n.d. (manca la tabella degli shock)') : fmtMoney(-w.gap, ccy), 'neg'),
      row('Patrimonio finale', fmtMoney(w.eq - w.total, ccy, { digits: 0 })));
    const nav = obj(snap.nav);
    const ddAfter = num(nav.high_water) ? (w.eq - w.total) / nav.high_water - 1 : null;
    const steps = arr(obj(snap.risk).dd_ladder).filter((st) => num(st.level) != null).sort((a, b) => b.level - a.level);
    const hit = ddAfter == null ? null : [...steps].reverse().find((st) => ddAfter <= st.level);
    const day = arr(obj(snap.risk).limits).find((l) => /24 ore|giornata/i.test(str(l.name)));
    const dayHit = day && num(day.limit) != null && -w.loss <= day.limit;
    worstVerdict.hidden = false;
    worstVerdict.className = `verdict ${hit && /kill|chiud/i.test(str(hit.action)) ? 'verdict--crit' : !hit && !dayHit ? 'verdict--ok' : ''}`.trim();
    worstVerdict.replaceChildren(h('b', { text: `${fmtPctSigned(-w.loss, 1)} in un giorno` }), ddAfter == null ? '' : ` · caduta dal massimo ${fmtPctSigned(ddAfter, 1)}. `,
      hit ? `Scatterebbe lo scalino ${fmtPct(hit.level, 0)}: ${str(hit.action)}.` : dayHit ? `Scatterebbe il freno delle 24 ore (${fmtPct(day.limit, 0)}); nessuno scalino di caduta.` : 'Nessun freno scatterebbe.');
    pWorst.setFoot('Ipotesi dichiarata: tutti i trade perdono il margine isolato; il libro giornaliero subisce la peggiore delle giornate storiche di stress. ', w.worstDay && w.worstDay.missing.length ? `Senza shock: ${w.worstDay.missing.join(', ')}.` : '');
  }

  function paintCaps() {
    const { snap } = ctxNow;
    const limits = arr(obj(snap.risk).limits);
    const caps = limits.filter((l) => num(l.limit) > 0 && num(l.value) != null && str(l.unit) === '%' && !/var|volatilit/i.test(str(l.name)));
    const ex = obj(snap.exposure);
    pCaps.setProv(provTag(provOf(snap.meta)), h('span', { class: 'panel__ask', text: `lordo ${num(ex.gross) == null ? 'n.d.' : fmtPct(ex.gross, 0)} · netto ${num(ex.net) == null ? 'n.d.' : fmtPct(ex.net, 0)}` }));
    const rows = caps.map((l) => {
      const u = utilization(l.value, l.limit);
      return meterRow({ name: str(l.name).replace(/^Esposizione sulla /i, '').replace(/^Peso massimo di uno strumento$/i, 'Singolo strumento'), value: l.value, cap: l.limit, state: limitStatus(l.status).kind === 'ok' ? 'ok' : str(l.status) === 'breach' ? 'breach' : 'warn', text: `${fmtPct(l.value, 1)} / ${fmtPct(l.limit, 0)} · ${fmtPct(u, 0)}` });
    });
    const venues = arr(ex.by_venue).filter((v) => num(v.gross) != null);
    const top = Math.max(0.01, ...caps.map((l) => l.limit * 1.25), ...venues.map((v) => v.gross * 1.2));
    for (const v of venues) {
      const cap = limits.find((l) => new RegExp(`sede\\s+${str(v.name)}\\b`, 'i').test(str(l.name)));
      if (cap) continue;
      rows.push(meterRow({ name: str(v.name), sub: 'nessun tetto di sede', value: v.gross, cap: null, scale: top, state: 'none', text: fmtPct(v.gross, 1) }));
    }
    capsBox.replaceChildren(...(rows.length ? rows : [emptyState('Nessun tetto dichiarato', 'La fotografia non riporta tetti di esposizione.')]));
    const near = caps.filter((l) => utilization(l.value, l.limit) >= 0.6);
    pCaps.setFoot(near.length ? `${fmtNum(near.length, 0)} ${near.length === 1 ? 'tetto' : 'tetti'} sopra il 60% di utilizzo.` : 'Nessun limite sopra il 60%.');
  }

  function paintLev() {
    const { snap } = ctxNow;
    const risk = obj(snap.risk);
    const ex = obj(snap.exposure);
    const levLim = arr(risk.limits).find((l) => /leva/i.test(str(l.name)));
    const lev = num(ex.leverage) ?? num(levLim && levLim.value);
    const cap = num(levLim && levLim.limit) ?? num(ex.max_leverage);
    const rows = [meterRow({ name: 'Leva del conto', value: lev || 0, cap, state: cap && lev / cap >= 0.8 ? 'warn' : 'ok', text: `${lev == null ? 'n.d.' : `${fmtNum(lev, 2)}x`} / ${cap == null ? 'tetto non letto' : `${fmtNum(cap, 0)}x`}` })];
    const open = Object.values(obj(obj(tb).open));
    const maxLev = open.length ? Math.max(...open.map((t) => num(t.leverage) || 0)) : null;
    rows.push(tb === undefined ? meterRow({ name: 'Leva del trade', value: 0, cap: null, state: 'none', text: '…' })
      : meterRow({ name: 'Leva del trade', sub: open.length ? `${open.map((t) => str(t.symbol)).join(', ')} · tetto n.d.` : '', value: maxLev || 0, cap: null, scale: 20, state: 'none', text: maxLev == null ? 'nessun trade aperto' : `${fmtNum(maxLev, 1)}x` }));
    const vol = num(risk.vol_realized_30d);
    const target = num(risk.vol_target);
    rows.push(meterRow({ name: 'Volatilità 30 giorni', value: vol || 0, cap: target, state: 'ok', text: `${vol == null ? 'n.d.' : fmtPct(vol, 1)} / ${target == null ? 'obiettivo non letto' : fmtPct(target, 0)}` }));
    levBox.replaceChildren(...rows);
    pLev.setProv(provTag(provOf(snap.meta)));
    pLev.setFoot('Tacca bianca: tetto operativo o obiettivo. Manca nella fotografia la serie a 90 giorni della leva.');
  }

  function paintStress() {
    const { snap, ccy, quant4Status } = ctxNow;
    const days = stressDays();
    pStress.setProv(provTag('sim'));
    if (!days.length) {
      stressBox.replaceChildren(emptyState(quant4Status === 'loading' ? 'Ricerca in lettura…' : 'Non ancora calcolabile', 'Manca la tabella degli shock per strumento (research/v5/quant_v4.json, stress_days). Qui compariranno 12 mar 2020, 19 mag 2021, 5 ago 2024, 10 ott 2025 applicati al libro di oggi.'));
      pStress.setFoot();
      return;
    }
    const eq = num(obj(snap.nav).equity);
    const dayLim = arr(obj(snap.risk).limits).find((l) => /24 ore|giornata/i.test(str(l.name)));
    const lim = num(dayLim && dayLim.limit);
    const worst = Math.min(...days.map((d) => d.pnl), lim || 0, -0.01);
    const scale = Math.abs(worst) * 1.15;
    const open = Object.values(obj(obj(tb).open));
    const rows = days.map((d) => {
      const low = obj(d.day.intraday_low);
      let hitTxt = '';
      for (const t of open) {
        const sym = str(t.symbol);
        const last = lastClose.get(sym);
        if (last === undefined) { lastClose.set(sym, null); getOhlc(sym, 10).then((o) => { lastClose.set(sym, o && o.c.length ? o.c[o.c.length - 1] : null); if (ctxNow) paintStress(); }); }
        const mv = num(low[sym]);
        if (mv == null || !last) continue;
        const side = num(t.side) === -1 ? -1 : 1;
        const price = last * (1 + mv * side);
        const liq = num(t.liquidation);
        const stop = num(t.stop);
        if (liq != null && (side === 1 ? price <= liq : price >= liq)) hitTxt = `${sym}: liquidato (perde il margine)`;
        else if (stop != null && (side === 1 ? price <= stop : price >= stop)) hitTxt = `${sym}: chiuso allo stop`;
        else hitTxt = `${sym}: regge`;
      }
      const bar = h('div', { class: 'stressbar', role: 'img', 'aria-label': `${str(d.day.name)}: ${fmtPctSigned(d.pnl, 1)}` }, h('i'), lim ? h('b') : null);
      bar.style.setProperty('--v', `${Math.min(100, (Math.abs(Math.min(0, d.pnl)) / scale) * 100).toFixed(1)}%`);
      if (lim) bar.style.setProperty('--t', `${Math.min(100, (Math.abs(lim) / scale) * 100).toFixed(1)}%`);
      const date = parseTs(str(d.day.date));
      return h('div', { class: 'stressrow' }, h('div', null, str(d.day.name), h('small', { text: `${date == null ? str(d.day.date) : fmtDate(date, true)}${hitTxt ? ` · ${hitTxt}` : ''}` })), bar,
        h('div', { class: `stressrow__val num ${d.pnl < 0 ? 'neg' : 'pos'}` }, fmtPctSigned(d.pnl, 1), eq ? h('small', { text: fmtMoney(d.pnl * eq, ccy, { digits: 0, signed: true }) }) : null));
    });
    stressBox.replaceChildren(...rows);
    const miss = [...new Set(days.flatMap((d) => d.missing))];
    const prox = [...new Set(days.flatMap((d) => d.proxies))];
    pStress.setFoot('Rendimenti veri di chiusura per strumento, applicati ai pesi di oggi. ', prox.length ? `Equivalenti usati: ${prox.join(', ')}. ` : '', miss.length ? `Senza dato in almeno una giornata: ${miss.join(', ')}.` : '');
  }

  function paintData() {
    const { snap, now } = ctxNow;
    const sys = obj(snap.system);
    const comps = arr(sys.components);
    const bad = comps.filter((c) => componentStatus(c.status).kind !== 'ok');
    const orders = arr(snap.orders);
    const pending = orders.filter((o) => /pending|intent|partial|unknown/i.test(str(o.status)));
    const rejected = orders.filter((o) => /reject/i.test(str(o.status)) && parseTs(o.t) != null && parseTs(o.t) >= now - DAY);
    const fact = (k, v) => h('span', null, k, h('b', { text: v }));
    facts.replaceChildren(
      h('span', { class: `chip chip--${!comps.length ? 'unknown' : bad.length ? 'warn' : 'ok'}` }, icon(bad.length ? 'warn' : 'check-circle'), h('span', { text: !comps.length ? 'componenti n.d.' : bad.length ? `${fmtNum(comps.length - bad.length, 0)} di ${fmtNum(comps.length, 0)} a posto` : 'tutto a posto' })),
      ...bad.slice(0, 3).map((c) => fact(str(c.name), ` ${componentStatus(c.status).label}${num(c.latency_ms) != null ? ` · ${fmtNum(c.latency_ms, 0)} ms` : ''}`)),
      fact('Battito', num(sys.heartbeat_age_s) == null ? ' mai visto' : ` ${fmtAgo(sys.heartbeat_age_s)}`), fact('Errori in 24 ore', num(sys.errors_24h) == null ? ' n.d.' : ` ${fmtNum(sys.errors_24h, 0)}`),
      fact('Riavvii in 24 ore', num(sys.restarts_24h) == null ? ' n.d.' : ` ${fmtNum(sys.restarts_24h, 0)}`), fact('Ordini in attesa', ` ${fmtNum(pending.length, 0)}`), fact('Rifiuti in 24 ore', ` ${fmtNum(rejected.length, 0)}`),
      h('a', { class: 'linkrow', href: '#/sistema' }, 'Salute e ordini in Sistema', icon('arrow')));
    pData.setProv(provTag(provOf(snap.meta)));
  }

  function paintAlerts() {
    const { snap, now } = ctxNow;
    const list = arr(snap.alerts).filter((a) => str(a.level).toLowerCase() !== 'info').slice(0, 4);
    alertsBox.replaceChildren(...(list.length ? list.map((a) => {
      const lv = str(a.level).toLowerCase();
      const t = parseTs(a.t);
      return h('div', { class: 'alert', dataset: { level: lv } }, icon(lv === 'critical' ? 'crit' : 'warn'), h('div', null, h('div', { class: 'alert__msg', text: str(a.msg) }), h('div', { class: 'alert__when', text: `${alertLevel(a.level).label}${t == null ? '' : ` · ${fmtAgo(Math.max(0, (now - t) / 1000))} · ${fmtDayTime(t)}`}` })));
    }) : [emptyState('Nessun avviso', 'Nessun avviso di attenzione o critico nel registro.')]));
    const hl = obj(ctxNow.health);
    killText.replaceChildren(hl.kill_active === true ? 'Il file KILL è presente: il motore è fermo o si ferma al prossimo ciclo. Per ripartire va tolto a mano sul server.'
      : hl.kill_enabled === false ? 'Il comando è spento su questo server (manca GERVA_DASH_TOKEN). In emergenza si crea il file KILL a mano nella cartella del motore.'
        : 'Il comando è pronto. Sta in alto a destra in ogni spazio: apre una finestra con l\'anteprima degli effetti, il token e la parola di conferma. Da qui non parte nulla.');
  }

  function paintStats() {
    const { snap, ccy } = ctxNow;
    const risk = obj(snap.risk);
    const eq = num(obj(snap.nav).equity);
    const v = num(risk.var_95_1d_pct);
    const es = num(risk.es_95_1d_pct);
    const fact = (k, val) => h('span', null, k, h('b', { text: val }));
    statsFacts.replaceChildren(fact('VaR 95% · 1 giorno', v == null ? ' n.d.' : ` ${fmtPct(Math.abs(v), 2)}${eq ? ` · ${fmtMoney(Math.abs(v) * eq, ccy, { digits: 0 })}` : ''}`), fact('ES 95% · 1 giorno', es == null ? ' n.d.' : ` ${fmtPct(Math.abs(es), 2)}${eq ? ` · ${fmtMoney(Math.abs(es) * eq, ccy, { digits: 0 })}` : ''}`));
    const curve = curveOf(snap);
    const rets = [];
    for (let i = Math.max(1, curve.equity.length - 365); i < curve.equity.length; i++) if (curve.equity[i - 1]) rets.push(curve.equity[i] / curve.equity[i - 1] - 1);
    if (rets.length < 30) { histHost.replaceChildren(emptyState('Servono almeno 30 giorni di storico', `Oggi ce ne sono ${fmtNum(rets.length, 0)}.`)); return; }
    const lo = Math.min(...rets);
    const hi = Math.max(...rets);
    const bins = 28;
    const edges = Array.from({ length: bins + 1 }, (_, i) => lo + ((hi - lo) * i) / bins);
    const counts = new Array(bins).fill(0);
    for (const r of rets) counts[Math.min(bins - 1, Math.floor(((r - lo) / (hi - lo)) * bins))]++;
    histogram(histHost, { edges, counts }, { label: 'Distribuzione dei rendimenti giornalieri dell\'ultimo anno', height: 130, xFormat: (x) => fmtPctSigned(x, 1), rangeFormat: (x) => fmtPctSigned(x, 2),
      refs: [{ value: 0, label: 'zero' }, v != null ? { value: -Math.abs(v), label: 'VaR 95%', cls: 'warn' } : null, es != null ? { value: -Math.abs(es), label: 'ES 95%', cls: 'crit' } : null].filter(Boolean) });
    pStats.setProv(provTag(provOf(snap.meta)));
    pStats.setFoot(`${fmtNum(rets.length, 0)} giorni · rendimenti giornalieri del patrimonio · curva tratteggiata: normale con stessa media e deviazione.`);
  }

  function paintAll() { paintBrake(); paintWorst(); paintCaps(); paintLev(); paintStress(); paintData(); paintAlerts(); paintStats(); }
  getTradebook().then((res) => { tb = res || null; if (ctxNow) paintAll(); });

  return {
    update(ctx) { ctxNow = ctx; paintAll(); },
    summary(ctx) {
      if (!ctx.fresh) return 'I dati sono fermi: lo stato del rischio è sconosciuto e nessuna distanza dai freni si può confermare.';
      const rs = riskState(ctx.snap.risk);
      const d = ladderData(ctx, tb);
      const first = d.steps[0];
      const lims = arr(obj(ctx.snap.risk).limits).map((l) => ({ l, u: utilization(l.value, l.limit) })).filter((x) => x.u != null).sort((a, b) => b.u - a.u);
      return `Lo stato è ${rs.label}${first && d.dd != null ? `: mancano ${fmtNum((d.dd - first.level) * 100, 1)} punti al primo freno (${fmtPct(first.level, 0)})` : ''}. ${lims.length ? `Il limite più vicino è «${str(lims[0].l.name)}», al ${fmtPct(lims[0].u, 0)} del tetto.` : ''}`;
    },
  };
}
