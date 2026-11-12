// Indicatori tecnici calcolati nel browser per le sovrapposizioni del grafico a candele.
// Conviction e indicatore Gervasoni NON si calcolano qui: arrivano dal server, dalle funzioni del motore.
// Ogni funzione restituisce un array lungo come l'ingresso, con null dove la finestra non è ancora piena.

export function sma(x, n) {
  const out = new Array(x.length).fill(null);
  let sum = 0;
  let cnt = 0;
  for (let i = 0; i < x.length; i++) {
    if (x[i] != null) { sum += x[i]; cnt++; }
    if (i >= n && x[i - n] != null) { sum -= x[i - n]; cnt--; }
    if (i >= n - 1 && cnt === n) out[i] = sum / n;
  }
  return out;
}

export function ema(x, n) {
  const out = new Array(x.length).fill(null);
  const k = 2 / (n + 1);
  let prev = null;
  let seed = 0;
  let cnt = 0;
  for (let i = 0; i < x.length; i++) {
    if (x[i] == null) continue;
    if (prev == null) {
      seed += x[i];
      cnt++;
      if (cnt === n) { prev = seed / n; out[i] = prev; }
    } else {
      prev = x[i] * k + prev * (1 - k);
      out[i] = prev;
    }
  }
  return out;
}

/** Bande di Bollinger (media a n giorni ± k deviazioni standard). */
export function bollinger(x, n = 20, k = 2) {
  const mid = sma(x, n);
  const up = new Array(x.length).fill(null);
  const lo = new Array(x.length).fill(null);
  for (let i = n - 1; i < x.length; i++) {
    if (mid[i] == null) continue;
    let s = 0;
    for (let j = i - n + 1; j <= i; j++) s += (x[j] - mid[i]) ** 2;
    const sd = Math.sqrt(s / n);
    up[i] = mid[i] + k * sd;
    lo[i] = mid[i] - k * sd;
  }
  return { mid, up, lo };
}

/** VWAP ancorato all'apertura del mese (prezzo tipico pesato per il volume, azzerato a ogni mese): come nel GQ. */
export function vwapMonth(t, h, l, c, v) {
  const out = new Array(t.length).fill(null);
  let pv = 0;
  let vol = 0;
  let month = -1;
  for (let i = 0; i < t.length; i++) {
    const d = new Date(t[i]);
    const m = d.getUTCFullYear() * 12 + d.getUTCMonth();
    if (m !== month) { month = m; pv = 0; vol = 0; }
    if (h[i] == null || l[i] == null || c[i] == null || !v[i]) { out[i] = vol > 0 ? pv / vol : null; continue; }
    pv += ((h[i] + l[i] + c[i]) / 3) * v[i];
    vol += v[i];
    out[i] = pv / vol;
  }
  return out;
}

/** Canale di Donchian: massimo e minimo delle n barre precedenti (esclusa quella corrente). */
export function donchian(h, l, n = 20) {
  const up = new Array(h.length).fill(null);
  const lo = new Array(h.length).fill(null);
  for (let i = n; i < h.length; i++) {
    let a = -Infinity;
    let b = Infinity;
    for (let j = i - n; j < i; j++) {
      if (h[j] != null && h[j] > a) a = h[j];
      if (l[j] != null && l[j] < b) b = l[j];
    }
    if (a > -Infinity) { up[i] = a; lo[i] = b; }
  }
  return { up, lo };
}

/** ATR%14 come nel motore (gerva/gervasoni.py): media a 14 giorni di (massimo − minimo) / chiusura. */
export function atrPct(h, l, c, n = 14) {
  return sma(h.map((x, i) => (x == null || l[i] == null || !c[i] ? null : (x - l[i]) / c[i])), n);
}

/** RSI di Wilder a n periodi. */
export function rsi(c, n = 14) {
  const out = new Array(c.length).fill(null);
  let gain = 0;
  let loss = 0;
  for (let i = 1; i < c.length; i++) {
    if (c[i] == null || c[i - 1] == null) continue;
    const d = c[i] - c[i - 1];
    const g = Math.max(d, 0);
    const ls = Math.max(-d, 0);
    if (i <= n) {
      gain += g / n;
      loss += ls / n;
      if (i === n) out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
    } else {
      gain = (gain * (n - 1) + g) / n;
      loss = (loss * (n - 1) + ls) / n;
      out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
    }
  }
  return out;
}
