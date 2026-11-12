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

// ================================================================================================================================
// Evidenza, Portafoglio, Apprendimento, Sistema: le grandezze derivate dei quattro spazi «quando serve» (stesse regole di sopra).
// ================================================================================================================================

/** Confine tra periodo di scelta e periodo di verifica della ricerca (research/v5: scelta fino al 2022, verifica dal 1° gennaio 2023). */
export const SPLIT_T = Date.UTC(2023, 0, 1);
const Z90 = 1.645;                     // baffo al 90% di ogni media (design_2 §1, «Incertezza»)
const mean = (x) => x.reduce((a, v) => a + v, 0) / x.length;
const sdev = (x) => { if (x.length < 2) return NaN; const m = mean(x); return Math.sqrt(x.reduce((a, v) => a + (v - m) ** 2, 0) / (x.length - 1)); };

/** Quantile della normale standard (Abramowitz–Stegun 26.2.23, errore < 5e-4): basta per disegnare una curva teorica dichiarata. */
export function normInv(p) {
  if (!(p > 0 && p < 1)) return NaN;
  const q = p < 0.5 ? p : 1 - p;
  const t = Math.sqrt(-2 * Math.log(q));
  const z = t - (2.515517 + 0.802853 * t + 0.010328 * t * t) / (1 + 1.432788 * t + 0.189269 * t * t + 0.001308 * t * t * t);
  return p < 0.5 ? -z : z;
}

/**
 * Quanto può essere fortuna: prove contate, Sharpe atteso dal migliore di N senza abilità, Deflated Sharpe come INTERVALLO
 * (i valori calcolati dalla ricerca con metodi e portafogli diversi) contro la soglia. Tutto da quant_v4.json: nessuna soglia qui.
 * seNull = errore standard dello Sharpe di una prova senza abilità, ricavato da expected_max e dal numero di prove
 * (E[max di N] = se × [(1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(N·e))]): serve solo a disegnare la curva teorica.
 */
export function luck(quant4) {
  const q = obj(quant4);
  const d = obj(q.deflated_sharpe);
  const names = { old: 'libro giornaliero, come pubblicato', new: 'libro giornaliero, cassa remunerata', fund: 'fondo intero (profilo massimo)' };
  const values = Object.keys(names).map((k) => ({ id: k, label: names[k], value: num(d[k]) })).filter((v) => v.value != null);
  const trials = num(q.trials);
  const expectedMax = num(d.expected_max);
  const threshold = num(d.threshold);
  if (!values.length) return null;
  const lo = Math.min(...values.map((v) => v.value));
  const hi = Math.max(...values.map((v) => v.value));
  const g = 0.5772156649;
  const zMax = trials > 1 ? (1 - g) * normInv(1 - 1 / trials) + g * normInv(1 - 1 / (trials * Math.E)) : null;
  return { trials, expectedMax, threshold, values, lo, hi, pass: threshold == null ? null : lo >= threshold, seNull: expectedMax != null && zMax ? expectedMax / zMax : null, note: str(d.note) };
}

/** Giorni simulati (dalla prima all'ultima data delle curve della ricerca), di paper (cancello «Giorni di paper») e reali. */
export function provenanceDays(snap, quant4) {
  const curves = Object.values(obj(obj(quant4).fund_curves)).find((c) => Array.isArray(c) && c.length > 1);
  const t0 = curves ? parseTs(str(curves[0][0])) : null;
  const t1 = curves ? parseTs(str(curves[curves.length - 1][0])) : null;
  const gate = arr(obj(snap).gates).find((g) => /giorni di paper/i.test(str(g.name)));
  const live = str(obj(obj(snap).meta).mode).toLowerCase() === 'live';
  const days = gate && num(gate.value) != null ? Math.round(gate.value) : null;
  return { sim: t0 != null && t1 != null ? Math.round((t1 - t0) / DAY) : null, paper: live ? null : days, real: live ? days : 0, paperTarget: gate ? num(gate.target) : null };
}

/**
 * Cono dell'atteso (paper_profile_cone) con il percorso del conto sopra: dieci punti per mese, percentile di oggi.
 * horizon in mesi (null = quanto basta a contenere il paper, almeno 3). → null se manca il Monte Carlo del profilo.
 */
export function coneData(snap, quant4, horizon = null) {
  const c = obj(obj(quant4).paper_profile_cone);
  const months = Array.isArray(c.months) ? c.months : [];
  if (months.length < 3 || !Array.isArray(c.p50)) return null;
  const curve = curveOf(snap);
  const pd = provenanceDays(snap, quant4);
  const days = pd.paper != null || pd.real ? Math.min(curve.t.length - 1, Math.max(0, pd.paper ?? pd.real)) : 0;
  const hz = Math.min(months.length - 1, horizon || Math.max(3, Math.ceil(days / 30.44) + 2));
  const grid = 10;
  const x = Array.from({ length: hz * grid + 1 }, (_, i) => i / grid);
  const at = (a) => x.map((m) => { const i = Math.min(months.length - 2, Math.floor(m)); return Number(a[i]) + (Number(a[i + 1]) - Number(a[i])) * (m - i); });
  const [p05, p25, p50, p75, p95] = ['p05', 'p25', 'p50', 'p75', 'p95'].map((k) => at(c[k]));
  const path = x.map(() => null);
  let pctNow = null;
  let last = -1;
  if (days >= 1) {
    const i0 = curve.t.length - 1 - days;
    for (let k = 0; k <= days; k++) { const idx = Math.round((k / 30.44) * grid); if (idx < path.length) { path[idx] = curve.equity[i0 + k] / curve.equity[i0]; last = idx; } }
    for (let i = 1; i < last; i++) if (path[i] == null) { const a = i - 1; let b = i + 1; while (path[b] == null) b++; path[i] = path[a] + (path[b] - path[a]) * ((i - a) / (b - a)); }
    const v = path[last];
    const qs = [[0.05, p05[last]], [0.25, p25[last]], [0.5, p50[last]], [0.75, p75[last]], [0.95, p95[last]]];
    if (v <= qs[0][1]) pctNow = 0.05; else if (v >= qs[4][1]) pctNow = 0.95;
    else for (let i = 0; i < 4; i++) if (v >= qs[i][1] && v <= qs[i + 1][1]) pctNow = qs[i][0] + (qs[i + 1][0] - qs[i][0]) * ((v - qs[i][1]) / ((qs[i + 1][1] - qs[i][1]) || 1));
  }
  const where = pctNow == null ? '' : pctNow <= 0.05 ? 'sotto la fascia' : pctNow >= 0.95 ? 'sopra la fascia' : pctNow < 0.5 ? 'dentro la fascia, sotto la mediana' : 'dentro la fascia, sopra la mediana';
  const edge = pctNow == null ? null : pctNow <= 0.05 ? 'low' : pctNow >= 0.95 ? 'high' : 'in';          // fuori dalla fascia 5°–95°?
  return { x, p05, p25, p50, p75, p95, path, pctNow, edge, where, days, horizon: hz, last, paths: num(c.paths), method: str(c.method), profile: str(c.profile), cagr: { p05: num(c.cagr_p05), p50: num(c.cagr_p50), p95: num(c.cagr_p95) } };
}

/**
 * Confronto con il sistema originale: la stessa formula di research/v5/v6/b8_confronto/confronto.py (series + diff_stats + verdict).
 * Rendimenti sulle righe dove entrambi i conti esistono; versamenti tolti; cambio applicato se presente su ogni riga.
 * z a pari volatilità = media(u)/dev(u)·√n con u = a/σa − b/σb; distacco cumulato = Σu dentro l'imbuto ±zWin·dev(u)·√giorni.
 * Con meno di 3 rendimenti z non esiste: lo si dice, non si mostra uno zero.
 */
export function compareStats(cmp) {
  const MIN_DAYS = 90;                   // criteri di confronto.py: MIN_DAYS, Z_WIN (REPORT.md della ricerca, sezione 5)
  const Z_WIN = 1.3;
  const Z80 = 0.8416;
  const Z95 = 1.6449;
  const rows = arr(obj(cmp).rows).map((r) => ({ t: parseTs(str(r.data)), a: num(r.nuovo_totale), b: num(r.legacy_nav), f: num(r.legacy_flusso) || 0, fx: num(r.eurusd), spy: num(r.spy), btc: num(r.btc) }))
    .filter((r) => r.t != null && r.a && r.b).sort((p, c) => p.t - c.t);
  const fxOk = rows.length > 0 && rows.every((r) => r.fx);
  const t = [];
  const a = [];
  const b = [];
  for (let i = 1; i < rows.length; i++) {
    const p = rows[i - 1];
    const c = rows[i];
    let lr = (c.b - c.f) / p.b - 1;
    if (fxOk) lr = (1 + lr) * c.fx / p.fx - 1;
    t.push(c.t); a.push(c.a / p.a - 1); b.push(lr);
  }
  const n = a.length;
  const span = rows.length > 1 ? Math.round((rows[rows.length - 1].t - rows[0].t) / DAY) : 0;
  const perYear = 365 * n / Math.max(span, 1);
  const cum = (r) => r.reduce((acc, v) => { acc.push(acc[acc.length - 1] * (1 + v)); return acc; }, [100]);
  const base = { rows: rows.length, n, span, minDays: MIN_DAYS, zWin: Z_WIN, t0: rows.length ? rows[0].t : null, x: rows.map((r) => r.t), newIdx: cum(a), origIdx: cum(b), fxApplied: fxOk,
    cumNew: n ? cum(a)[n] / 100 - 1 : null, cumOrig: n ? cum(b)[n] / 100 - 1 : null };
  if (n < 3) return { ...base, z: null, zRaw: null, rho: null, u: [], su: null, cumU: [], needNow: null, need10: null, need05: null, verdict: { code: 'few', text: 'Troppo presto', why: `servono almeno 3 giorni comuni con entrambi i conti: ce ne sono ${Math.max(0, n)}` } };
  const d = a.map((v, i) => v - b[i]);
  const sa = sdev(a);
  const sb = sdev(b);
  const sd = sdev(d);
  const zRaw = sd > 0 ? mean(d) / sd * Math.sqrt(n) : null;
  let z = null;
  let u = [];
  let su = null;
  if (sa > 0 && sb > 0) { u = a.map((v, i) => v / sa - b[i] / sb); su = sdev(u); z = su > 0 ? mean(u) / su * Math.sqrt(n) : null; }
  const ma = mean(a);
  const mb = mean(b);
  const rho = sa > 0 && sb > 0 ? a.reduce((acc, v, i) => acc + (v - ma) * (b[i] - mb), 0) / ((n - 1) * sa * sb) : null;
  const k = rho == null ? null : (Z95 + Z80) ** 2 * 2 * (1 - rho) * perYear;
  const cumU = u.reduce((acc, v) => { acc.push(acc[acc.length - 1] + v); return acc; }, [0]);
  let verdict;
  if (span < MIN_DAYS) verdict = { code: 'running', text: 'In corso', why: `${span} giorni comuni su ${MIN_DAYS} richiesti` };
  else if (z != null && z > Z_WIN) verdict = { code: 'beats', text: 'Batte l\'originale', why: `z a pari volatilità sopra +${Z_WIN}` };
  else if (z != null && z < -Z_WIN) verdict = { code: 'beaten', text: 'Battuto dall\'originale', why: `z a pari volatilità sotto −${Z_WIN}` };
  else verdict = { code: 'open', text: 'Non smentito, non provato', why: 'il distacco è dentro la fascia del caso' };
  return { ...base, z, zRaw, rho, u, su, cumU, dSharpe: u.length ? mean(u) * Math.sqrt(perYear) : null,
    needNow: z != null && z > 0 ? Math.ceil(n * ((Z95 + Z80) / z) ** 2) : null, need10: k == null ? null : Math.ceil(k), need05: k == null ? null : Math.ceil(k / 0.25), verdict };
}

/** Curva settimanale a base 1 → caduta dal massimo per punto (≤ 0). */
export function drawdownSeries(values) {
  let peak = -Infinity;
  return values.map((v) => { if (v == null) return null; peak = Math.max(peak, v); return v / peak - 1; });
}

/**
 * Sharpe mobile di una curva (valori a passo costante), con la banda ±1,96 errori standard (e.s. ≈ √((1 + S²/2)/anni)).
 * win = punti della finestra, perYear = punti in un anno.
 */
export function rollingSharpe(values, win, perYear) {
  const r = values.map((v, i) => (i && v != null && values[i - 1] ? v / values[i - 1] - 1 : null));
  const out = { sharpe: [], lo: [], hi: [] };
  for (let i = 0; i < values.length; i++) {
    const w = i >= win ? r.slice(i - win + 1, i + 1).filter((v) => v != null) : [];
    if (w.length < win * 0.9) { out.sharpe.push(null); out.lo.push(null); out.hi.push(null); continue; }
    const sd = sdev(w);
    const sh = sd > 0 ? mean(w) / sd * Math.sqrt(perYear) : null;
    const se = sh == null ? null : Math.sqrt((1 + sh * sh / 2) / (w.length / perYear));
    out.sharpe.push(sh); out.lo.push(sh == null ? null : sh - 1.96 * se); out.hi.push(sh == null ? null : sh + 1.96 * se);
  }
  return out;
}

/**
 * Da dove viene il risultato: contributo per strategia, libro dei trade e «non attribuito», per oggi / mese / dall'avvio.
 * Oggi: somma del P&L di giornata delle posizioni. Mese e avvio: quota × rendimento del periodo × patrimonio di inizio periodo
 * (stima: la base del rendimento per strategia non è dichiarata nella fotografia). Il libro dei trade entra solo «dall'avvio»
 * (equity − start_equity); per oggi e per il mese il suo contributo non è nella fotografia: null, mai zero.
 */
export function attribution(snap, tb, period = 'day') {
  const nav = obj(obj(snap).nav);
  const eq = num(nav.equity);
  const strategies = arr(obj(snap).strategies);
  let rows = [];
  let total = null;
  let estimate = false;
  if (period === 'day') {
    const by = new Map();
    for (const p of arr(obj(snap).positions)) if (num(p.pnl_day) != null) by.set(str(p.strategy), (by.get(str(p.strategy)) || 0) + p.pnl_day);
    rows = strategies.map((st) => ({ id: str(st.id), name: str(st.name), value: by.get(str(st.id)) ?? null }));
    total = num(nav.pnl_day);
  } else {
    const key = period === 'mtd' ? 'pnl_mtd_pct' : 'pnl_total_pct';
    const all = num(nav[key]);
    const startEq = eq != null && all != null ? eq / (1 + all) : null;
    rows = startEq == null ? [] : strategies.map((st) => ({ id: str(st.id), name: str(st.name), value: num(st.allocation) != null && num(st[key]) != null ? st.allocation * st[key] * startEq : null }));
    total = startEq == null ? null : eq - startEq;
    estimate = true;
  }
  rows = rows.filter((r) => r.value != null);
  const trade = period === 'total' && tb && num(tb.equity) != null && num(tb.start_equity) != null ? tb.equity - tb.start_equity : null;
  if (!rows.length || total == null) return { rows: [], trade, gap: null, total: null, bp: null, estimate };
  const gap = total - rows.reduce((a, r) => a + r.value, 0);
  return { rows, trade, gap, total: total + (trade || 0), daily: total, bp: eq ? Math.abs(gap) / eq * 10000 : null, estimate };
}

/** Statistiche di un insieme di R: n, media, mediana, deviazione, errore standard e baffo al 90% (media ± 1,645 e.s.). */
export function rStats(values) {
  const v = values.filter((x) => num(x) != null);
  const n = v.length;
  if (!n) return { n: 0, mean: null, median: null, sd: null, se: null, lo: null, hi: null, win: null, total: null };
  const m = mean(v);
  const sd = n > 1 ? sdev(v) : null;
  const se = sd == null ? null : sd / Math.sqrt(n);
  const sorted = [...v].sort((a, b) => a - b);
  const median = n % 2 ? sorted[(n - 1) / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2;
  return { n, mean: m, median, sd, se, lo: se == null ? null : m - Z90 * se, hi: se == null ? null : m + Z90 * se, win: v.filter((x) => x > 0).length / n, total: v.reduce((a, x) => a + x, 0) };
}

/** R medio per fetta: rows = trade, keyOf(row) → chiave (null = escluso). Ogni fetta porta n e il baffo; l'ordine è quello di `order` se dato. */
export function groupR(rows, keyOf, order = null) {
  const by = new Map();
  for (const r of rows) { const k = keyOf(r); if (k == null || num(r.R) == null) continue; if (!by.has(k)) by.set(k, []); by.get(k).push(r.R); }
  const keys = order ? order.filter((k) => by.has(k)) : [...by.keys()].sort((a, b) => (a > b ? 1 : a < b ? -1 : 0));
  return keys.map((k) => ({ key: k, ...rStats(by.get(k)) }));
}

/** Istogramma di R a classi di larghezza `step` tra lo e hi; ciò che sta oltre hi finisce nell'ultima classe («> hi»), dichiarata. */
export function histR(values, step, lo, hi) {
  const nb = Math.round((hi - lo) / step) + 1;
  const edges = Array.from({ length: nb + 1 }, (_, i) => lo + i * step);
  const counts = new Array(nb).fill(0);
  for (const v of values) { if (num(v) == null) continue; counts[Math.max(0, Math.min(nb - 1, Math.floor((v - lo) / step + 1e-9)))]++; }
  return { edges, counts, overflowFrom: hi };
}

/** Un cancello paper → reale: 'ok' solo se il motore lo dà per superato E c'è un valore; senza valore è «non ancora misurabile», mai spuntato. */
export function gateState(g) {
  if (num(obj(g).value) == null) return 'unmeasured';
  return obj(g).ok === true ? 'ok' : 'open';
}

/**
 * Età dei dati per fonte contro i limiti del motore (health.rules.max_data_age_h, meta.stale_after_s).
 * → [{ id, name, ageS, maxS, state: 'ok' | 'stale' | 'unknown' (limite non letto) | 'missing' (fonte assente), detail }]
 */
export function sourceAges({ snap, health, now, tradebook, compare, bars = [] }) {
  const rules = obj(obj(health).rules);
  const meta = obj(obj(snap).meta);
  const out = [];
  const push = (id, name, ageS, maxS, detail, present = true) => out.push({ id, name, ageS, maxS, detail, state: !present ? 'missing' : ageS == null ? 'missing' : maxS == null ? 'unknown' : ageS > maxS ? 'stale' : 'ok' });
  const asOf = parseTs(str(meta.as_of));
  push('snap', 'Fotografia del conto', asOf == null || now == null ? null : Math.max(0, (now - asOf) / 1000), num(meta.stale_after_s), 'scritta a ogni ciclo');
  const hb = num(obj(obj(snap).system).heartbeat_age_s);
  push('hb', 'Battito del motore', hb, num(rules.interval_s) == null ? null : rules.interval_s * 2, num(rules.interval_s) == null ? 'intervallo del ciclo non letto' : `un ciclo ogni ${Math.round(rules.interval_s / 60)} minuti`);
  const dayAge = (id, name, dayMs, kind, detail, present) => { const f = freshness(dayMs, now, kind, rules); push(id, name, f.hours == null ? null : f.hours * 3600, f.maxHours == null ? null : f.maxHours * 3600, detail, present); };
  dayAge('tb', 'Libro dei trade', tradebook ? parseTs(str(tradebook.asof)) : null, 'crypto', tradebook ? 'data del libro' : 'il motore non ha scritto il libro', !!tradebook);
  for (const b of bars) dayAge(`bar-${b.symbol}`, `Barre ${b.symbol}`, b.t, b.kind === 'crypto' ? 'crypto' : 'ibkr', b.t == null ? 'nessuna barra nella cache' : 'ultima barra chiusa', b.t != null);
  const rowsC = arr(obj(compare).rows);
  dayAge('cmp', 'Confronto con l\'originale', rowsC.length ? parseTs(str(rowsC[rowsC.length - 1].data)) : null, 'ibkr', rowsC.length ? 'ultima riga' : 'confronto non ancora scritto', rowsC.length > 0);
  return out;
}

// ---- fonte più vecchia: libro dei trade e barre di mercato, per la fascia di stato ------------------------------------------------

/** Strumenti di cui si controlla l'ultima barra: trade aperti e posizioni. La sede IBKR chiude nel fine settimana (100 ore), le crypto no (36). */
export function watchedSymbols(snap, tb) {
  const out = new Map();
  for (const t of Object.values(obj(obj(tb).open))) if (t && str(t.symbol)) out.set(str(t.symbol).toUpperCase(), 'crypto');
  for (const p of arr(obj(snap).positions)) {
    const sym = str(p.symbol).toUpperCase();
    if (sym && !out.has(sym)) out.set(sym, /ibkr/i.test(str(p.venue)) ? 'ibkr' : 'crypto');
  }
  return [...out].map(([symbol, kind]) => ({ symbol, kind }));
}

/**
 * La fonte più in ritardo rispetto al suo massimo: sources = [{ name, day (ms della data), kind: 'crypto' | 'ibkr' }].
 * → null se nessuna è oltre l'età massima (o le regole mancano), altrimenti { name, day, hours, maxHours, count } della peggiore.
 */
export function oldestSource(sources, now, rules) {
  let worst = null;
  let count = 0;
  for (const sc of arr(sources)) {
    const f = freshness(num(sc.day), now, sc.kind, rules);
    if (!f.stale) continue;
    count += 1;
    if (!worst || f.hours - f.maxHours > worst.hours - worst.maxHours) worst = { name: str(sc.name), day: f.day, hours: f.hours, maxHours: f.maxHours };
  }
  return worst ? { ...worst, count } : null;
}
