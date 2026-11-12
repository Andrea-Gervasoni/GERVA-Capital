// Una sola verità: ogni grandezza derivata si calcola QUI, una volta, e gli spazi la riusano (Oggi, Rischio, Mercati, fascia).
// Funzioni pure, senza DOM: i test le eseguono con Node e verificano che la stessa grandezza sia identica ovunque.
// Soglie, tetti e regole non sono mai scritti qui: arrivano dalla fotografia (risk.dd_ladder, risk.limits, risk.vol_target)
// e da /api/v1/health → rules (letti dal motore e dalla configurazione). Se mancano, il risultato è null e la pagina dice «n.d.».

import { arr, num, obj, parseTs, str } from './format.js';
import { curveOf } from './model.js';

const DAY = 86400000;

// ---- patrimonio --------------------------------------------------------------------------------------------------------------

/** Patrimonio totale = libro giornaliero + contributo dei trade (equity − start_equity del libro: stesso capitale, non un secondo conto). */
export function totalNav(snap, tb) {
  const daily = num(obj(obj(snap).nav).equity);
  const gain = tb && num(tb.equity) != null && num(tb.start_equity) != null ? tb.equity - tb.start_equity : null;
  return { daily, tradeGain: gain, total: daily == null ? null : daily + (gain || 0), complete: gain != null };
}

/** σ della giornata: rendimento di oggi diviso per la volatilità OBIETTIVO di un giorno (vol_target / √365). */
export function sigmaDay(snap) {
  const pct = num(obj(obj(snap).nav).pnl_day_pct);
  const target = num(obj(obj(snap).risk).vol_target);
  if (pct == null || !target) return null;
  const z = pct / (target / Math.sqrt(365));
  return { z, target, word: Math.abs(z) < 1 ? 'una giornata normale' : Math.abs(z) < 2 ? 'una giornata mossa' : 'una giornata fuori dal comune' };
}

// ---- livelli di conviction e GQ: i nomi del motore, uguali dappertutto ---------------------------------------------------------

/** Conviction → { tier: bassa | media | alta, trade: null | confermato | eccezionale }. Senza regole: tier null. */
export function convLevel(score, kind, rules) {
  const v = num(score);
  const r = obj(rules);
  const t = obj(r.conviction_tiers)[kind === 'crypto' ? 'crypto' : 'index'];
  if (v == null || !Array.isArray(t)) return { tier: null, trade: null, text: v == null ? 'n.d.' : 'livello n.d.' };
  const tier = v > t[1] ? 'alta' : v > t[0] ? 'media' : 'bassa';
  const trade = kind !== 'crypto' || num(r.score_confirmed) == null ? null : v >= r.score_exceptional ? 'eccezionale' : v >= r.score_confirmed ? 'confermato' : null;
  return { tier, trade, text: trade ? `${tier} · trade ${trade}` : kind === 'crypto' ? `${tier} · nessun trade` : tier };
}

/** Indicatore GQ → eccezionale | alta | media | bassa sulle tre soglie del motore; senza regole null. */
export function gqLevel(value, rules) {
  const v = num(value);
  const t = obj(obj(rules).gq_tiers);
  if (v == null || num(t.alta) == null) return null;
  return v >= t.eccezionale ? 'eccezionale' : v >= t.alta ? 'alta' : v <= t.bassa ? 'bassa' : 'media';
}

// ---- freschezza per fonte ------------------------------------------------------------------------------------------------------

/**
 * Età di una fonte datata a giorni (ultima barra, `asof` del libro, ultima riga del confronto) contro il massimo ammesso.
 * Una barra del giorno G chiude alla mezzanotte UTC di G+1: l'età si conta da lì. kind: 'crypto' | 'ibkr'.
 * → { hours, maxHours, stale: true | false | null (regola assente), day }.
 */
export function freshness(dayMs, now, kind, rules) {
  if (dayMs == null || now == null) return { hours: null, maxHours: null, stale: null, day: null };
  const hours = Math.max(0, (now - (dayMs + DAY)) / 3600000);
  const max = num(obj(obj(rules).max_data_age_h)[kind]);
  return { hours, maxHours: max, stale: max == null ? null : hours > max, day: dayMs };
}

/** Un trade aperto letto alla data del libro: giorni di vita contati fino ad `asof`, non fino a oggi; oltre la durata massima è un'anomalia. */
export function tradeAge(trade, tb, rules) {
  const opened = parseTs(str(obj(trade).opened));
  const asof = parseTs(str(obj(tb).asof));
  const maxHold = num(obj(rules).max_hold_days);
  if (opened == null || asof == null) return { held: null, maxHold, over: false };
  const held = Math.max(0, Math.round((asof - opened) / DAY));
  return { held, maxHold, over: maxHold != null && held > maxHold };
}

/** R di un trade a un prezzo: (prezzo − entrata) / distanza iniziale dallo stop, con il segno del lato. */
export function tradeR(trade, last) {
  const t = obj(trade);
  const entry = num(t.entry);
  const stop = num(t.stop);
  const side = num(t.side) === -1 ? -1 : 1;
  const dist = num(t.initial_stop_distance) != null && entry ? entry * t.initial_stop_distance : entry != null && stop != null ? Math.abs(entry - stop) : null;
  if (entry == null || num(last) == null || !dist) return null;
  return (side * (last - entry)) / dist;
}

// ---- freni ---------------------------------------------------------------------------------------------------------------------

/**
 * Stato dei freni: scalini della caduta (dalla fotografia), scalino successivo NON ancora toccato, condizione di rientro,
 * finestre mobili a 24 ore e 7 giorni calcolate dalla serie del patrimonio (mai lo 0,00% di «min(pnl, 0)»).
 */
export function brakes(snap) {
  const nav = obj(obj(snap).nav);
  const risk = obj(obj(snap).risk);
  const dd = num(nav.drawdown_pct);
  const peak = num(nav.high_water);
  const eq = num(nav.equity);
  const es = Math.abs(num(risk.es_95_1d_pct) || 0) || null;
  const steps = arr(risk.dd_ladder).map((st) => ({ level: num(st.level), action: str(st.action) })).filter((st) => st.level != null).sort((a, b) => b.level - a.level);
  const hit = dd == null ? 0 : steps.filter((st) => dd <= st.level).length;
  const next = steps[hit] || null;
  const last = hit ? steps[hit - 1] : null;
  // rientro: il motore risale solo quando la caduta torna sotto META' della soglia che lo aveva fatto scendere (gerva/risk/engine.py)
  const reentry = last ? last.level / 2 : null;
  const row = (name, level, now, base, action, isHit) => {
    const dist = now == null ? null : now - level;
    return { name, level, now, dist, eur: dist == null || base == null ? null : dist * base, at: base == null ? null : base * (1 + level), esDays: dist == null || !es ? null : dist / es, action, hit: !!isHit };
  };
  const rows = steps.map((st) => row(`Caduta ${pct0(st.level)}`, st.level, dd, peak, st.action, dd != null && dd <= st.level));

  // finestre mobili dalla curva giornaliera
  const curve = curveOf(snap);
  const n = curve.t.length;
  const windowRet = (days) => {
    if (n < 2) return null;
    const tEnd = curve.t[n - 1];
    let k = -1;
    for (let i = n - 2; i >= 0; i--) if (tEnd - curve.t[i] >= days * DAY - DAY / 2) { k = i; break; }
    if (k < 0 || tEnd - curve.t[k] > (days + 1.5) * DAY || !curve.equity[k]) return null;
    return { ret: curve.equity[n - 1] / curve.equity[k] - 1, ref: curve.equity[k] };
  };
  const limits = arr(risk.limits);
  const lane = (id, label, re, days, action) => {
    const lim = limits.find((l) => re.test(str(l.name)));
    if (!lim || num(lim.limit) == null) return null;
    const w = windowRet(days);
    return { id, label, limit: lim.limit, value: w ? w.ret : null, ref: w ? w.ref : null, used: num(lim.value), action,
      row: { ...row(`${label.replace(/^Ultim[ei]/, 'Perdita in')} ${pct0(lim.limit)}`, lim.limit, w ? Math.min(w.ret, 0) : null, w ? w.ref : null, action, w ? w.ret <= lim.limit : false), now: w ? w.ret : null } };
  };
  const lanes = [lane('d1', 'Ultime 24 ore', /24 ore|giornata/i, 1, 'esposizione dimezzata'), lane('d7', 'Ultimi 7 giorni', /7 giorni|settiman/i, 7, 'un quarto, nessun aumento')].filter(Boolean);
  return { dd, peak, equity: eq, es, steps, hit, next, last, reentry, distNext: next && dd != null ? dd - next.level : null, rows: [...rows, ...lanes.map((l) => l.row)], lanes, worstSoFar: num(nav.max_drawdown_pct) };
}
const pct0 = (v) => `${v < 0 ? '−' : ''}${Math.abs(Math.round(v * 100))}%`;

// ---- stress e peggior caso -------------------------------------------------------------------------------------------------------

/**
 * Una giornata storica sulle posizioni di oggi. Uno shock che manca NON vale zero: la posizione è «non coperta».
 * → { pnl (solo la parte coperta, frazione del patrimonio), coverage (quota dell'esposizione lorda coperta), missing: [simboli] }.
 */
export function stressDay(day, positions, equity) {
  const shocks = obj(obj(day).shocks);
  let pnl = 0;
  let covered = 0;
  let gross = 0;
  const missing = [];
  for (const p of arr(positions)) {
    const w = num(p.weight) ?? (num(p.value) != null && equity ? p.value / equity : null);
    if (w == null) continue;
    gross += Math.abs(w);
    const sym = str(p.symbol).toUpperCase();
    if (num(shocks[sym]) == null) { missing.push(sym); continue; }
    pnl += w * shocks[sym];
    covered += Math.abs(w);
  }
  return { day, pnl, coverage: gross > 0 ? covered / gross : null, missing };
}

export const stressDays = (snap, quant4) => arr(obj(obj(quant4).stress_days).days).map((d) => stressDay(d, obj(snap).positions, num(obj(obj(snap).nav).equity)));

/**
 * Peggior caso di oggi (ipotesi SIMULATA): tutti i trade perdono il margine isolato e il libro giornaliero subisce la peggiore
 * giornata storica. Un solo calcolo: patrimonio finale, perdita in un giorno, caduta dal massimo = finale / massimo − 1.
 * atLeast: true se manca il libro dei trade o la copertura degli shock non è completa («almeno −x%», mai «nessun freno»).
 */
export function worstCase(snap, tb, quant4) {
  const nav = obj(obj(snap).nav);
  const eq = num(nav.equity);
  if (eq == null) return null;
  const open = Object.values(obj(obj(tb).open)).filter((t) => t && typeof t === 'object');
  const stops = tb ? open.reduce((a, t) => a + (num(t.risk) || 0), 0) : null;
  const margins = tb ? open.reduce((a, t) => a + (num(t.margin) || 0), 0) : null;
  const beyond = tb ? Math.max(0, margins - stops) : null;
  const days = stressDays(snap, quant4);
  const worstDay = days.length ? days.reduce((a, b) => (b.pnl < a.pnl ? b : a)) : null;
  const gap = worstDay && worstDay.pnl < 0 ? -worstDay.pnl * eq : worstDay ? 0 : null;
  const total = (stops || 0) + (beyond || 0) + (gap || 0);
  const final = eq - total;
  const peak = num(nav.high_water);
  const ddAfter = peak ? final / peak - 1 : null;
  const b = brakes(snap);
  const stepHit = ddAfter == null ? null : [...b.steps].reverse().find((st) => ddAfter <= st.level) || null;
  const d1 = b.lanes.find((l) => l.id === 'd1');
  const dayHit = d1 ? -total / eq <= d1.limit : false;
  const atLeast = !tb || gap == null || (worstDay && worstDay.coverage != null && worstDay.coverage < 0.999);
  return { equity: eq, stops, beyond, gap, worstDay, total, final, loss: total / eq, ddAfter, stepHit, dayHit, dayLimit: d1 ? d1.limit : null, atLeast, coverage: worstDay ? worstDay.coverage : null };
}
