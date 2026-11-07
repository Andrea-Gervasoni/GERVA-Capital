// Grafici quant del portale: gli indicatori che usano i bot di trading, disegnati sui prezzi veri.
// Solo lettura: i dati arrivano da /api/charts/* (firm/charts.py); niente librerie esterne (CSP: script-src 'self').
const QC = (() => {
  // colori e carattere presi dal tema della pagina (chiaro o scuro), a ogni disegno
  const K = {};
  let FONT = '12px "General Sans", sans-serif';
  function theme() {
    const st = getComputedStyle(document.documentElement), v = (n, d) => (st.getPropertyValue(n) || "").trim() || d;
    const c1 = v("--c1", "#0A3AE5");
    Object.assign(K, { grid: v("--chart-grid", "rgba(0,0,0,.1)"), text: v("--chart-text", "rgba(0,0,0,.55)"), paper: v("--text", "#14151F"), cyan: c1, gold: v("--c2", "#FC6C3A"),
      red: v("--c4", "#c6362b"), green: v("--c3", "#12804a"), band: "rgba(10,58,229,0.10)", bandLine: "rgba(10,58,229,0.45)" });
    FONT = '12px "General Sans", -apple-system, sans-serif';
  }
  function setup(canvas, w, h) {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); canvas.style.height = h + "px";
    const x = canvas.getContext("2d"); x.setTransform(dpr, 0, 0, dpr, 0, 0);
    theme(); x.clearRect(0, 0, w, h); x.font = FONT; x.textBaseline = "middle";
    return x;
  }
  const finite = (a) => a.filter((v) => v != null && isFinite(v));
  function frame(x, w, h, lo, hi, ticks, fmt, pad) {
    const L = pad.l, R = w - pad.r, T = pad.t, B = h - pad.b, y = (v) => B - ((v - lo) / (hi - lo || 1)) * (B - T);
    x.strokeStyle = K.grid; x.fillStyle = K.text; x.lineWidth = 1; x.textAlign = "right";
    for (let i = 0; i <= ticks; i++) {
      const v = lo + ((hi - lo) * i) / ticks, yy = Math.round(y(v)) + 0.5;
      x.beginPath(); x.moveTo(L, yy); x.lineTo(R, yy); x.stroke(); x.fillText(fmt(v), L - 6, yy);
    }
    return { L, R, T, B, y };
  }
  function xs(n, L, R) { return (i) => L + (i / Math.max(n - 1, 1)) * (R - L); }
  function line(x, arr, xf, yf, color, width = 1.4, dash) {
    x.beginPath(); x.strokeStyle = color; x.lineWidth = width; x.setLineDash(dash || []);
    let open = false;
    arr.forEach((v, i) => { if (v == null || !isFinite(v)) { open = false; return; } const px = xf(i), py = yf(v); open ? x.lineTo(px, py) : x.moveTo(px, py); open = true; });
    x.stroke(); x.setLineDash([]);
  }
  function dates(x, d, L, R, B, h) {
    x.fillStyle = K.text; x.textAlign = "center";
    [0, 0.25, 0.5, 0.75, 1].forEach((f) => { const i = Math.min(d.length - 1, Math.round(f * (d.length - 1))); x.fillText(d[i].slice(2), L + f * (R - L), h - 10); });
  }
  function legend(x, items, L, T) {
    x.textAlign = "left"; let px = L + 6;
    items.forEach(([name, col]) => { x.fillStyle = col; x.fillRect(px, T + 4, 12, 4); x.fillStyle = K.text; x.fillText(name, px + 16, T + 8); px += 24 + x.measureText(name).width + 6; });
  }
  const f0 = (v) => v.toFixed(0), f1 = (v) => v.toFixed(1), pc = (v) => (v * 100).toFixed(0) + "%";

  function price(canvas, d, w = 860, h = 320) {
    w = Math.max(320, canvas.clientWidth || canvas.parentElement.clientWidth || w);   // la larghezza vera: niente stiramenti
    const x = setup(canvas, w, h), pad = { l: 56, r: 12, t: 22, b: 24 }, n = d.close.length;
    const all = finite([...d.close, ...d.bb_su, ...d.bb_giu, ...d.ema200]); const lo = Math.min(...all) * 0.98, hi = Math.max(...all) * 1.02;
    const g = frame(x, w, h, lo, hi, 5, (v) => (hi > 200 ? f0(v) : v.toFixed(2)), pad), xf = xs(n, g.L, g.R);
    x.beginPath(); let started = false;
    d.bb_su.forEach((v, i) => { if (v == null) return; started ? x.lineTo(xf(i), g.y(v)) : x.moveTo(xf(i), g.y(v)); started = true; });
    for (let i = n - 1; i >= 0; i--) if (d.bb_giu[i] != null) x.lineTo(xf(i), g.y(d.bb_giu[i]));
    x.closePath(); x.fillStyle = K.band; x.fill();
    line(x, d.bb_su, xf, g.y, K.bandLine, 1, [4, 3]); line(x, d.bb_giu, xf, g.y, K.bandLine, 1, [4, 3]);
    line(x, d.ema200, xf, g.y, K.red, 1.6); line(x, d.ema50, xf, g.y, K.gold, 1.6); line(x, d.ema20, xf, g.y, K.cyan, 1.4);
    line(x, d.close, xf, g.y, K.paper, 1.8);
    const last = d.close[n - 1]; x.fillStyle = K.paper; x.textAlign = "left"; x.fillText(last.toFixed(2), Math.min(g.R - 50, xf(n - 1) - 20), g.y(last) - 12);
    legend(x, [["prezzo", K.paper], ["EMA20", K.cyan], ["EMA50", K.gold], ["EMA200", K.red], ["Bollinger", K.bandLine]], g.L, 0);
    dates(x, d.date, g.L, g.R, g.B, h);
  }
  function rsi(canvas, d, w = 860, h = 120) {
    w = Math.max(320, canvas.clientWidth || canvas.parentElement.clientWidth || w);   // la larghezza vera: niente stiramenti
    const x = setup(canvas, w, h), pad = { l: 56, r: 12, t: 16, b: 8 }, n = d.rsi.length;
    const g = frame(x, w, h, 0, 100, 2, f0, pad), xf = xs(n, g.L, g.R);
    x.fillStyle = "rgba(198,54,43,0.14)"; x.fillRect(g.L, g.y(100), g.R - g.L, g.y(70) - g.y(100));
    x.fillStyle = "rgba(18,128,74,0.14)"; x.fillRect(g.L, g.y(30), g.R - g.L, g.y(0) - g.y(30));
    line(x, d.rsi, xf, g.y, K.gold, 1.6);
    x.fillStyle = K.text; x.textAlign = "left"; x.fillText("RSI(14): sopra 70 ipercomprato, sotto 30 ipervenduto", g.L + 6, 8);
  }
  function vol(canvas, d, w = 860, h = 110) {
    w = Math.max(320, canvas.clientWidth || canvas.parentElement.clientWidth || w);   // la larghezza vera: niente stiramenti
    const x = setup(canvas, w, h), pad = { l: 56, r: 12, t: 16, b: 8 }, n = d.vol20.length, v = finite(d.vol20);
    const hi = Math.max(...v) * 1.1, g = frame(x, w, h, 0, hi, 2, pc, pad), xf = xs(n, g.L, g.R);
    line(x, d.vol20, xf, g.y, K.cyan, 1.6);
    x.fillStyle = K.text; x.textAlign = "left"; x.fillText("volatilità realizzata a 20 giorni (annua)", g.L + 6, 8);
  }
  function drawdown(canvas, d, w = 860, h = 110) {
    w = Math.max(320, canvas.clientWidth || canvas.parentElement.clientWidth || w);   // la larghezza vera: niente stiramenti
    const x = setup(canvas, w, h), pad = { l: 56, r: 12, t: 16, b: 8 }, n = d.drawdown.length, lo = Math.min(...d.drawdown, -0.02) * 1.1;
    const g = frame(x, w, h, lo, 0, 2, pc, pad), xf = xs(n, g.L, g.R);
    x.beginPath(); x.moveTo(xf(0), g.y(0)); d.drawdown.forEach((v, i) => x.lineTo(xf(i), g.y(v))); x.lineTo(xf(n - 1), g.y(0)); x.closePath();
    x.fillStyle = "rgba(198,54,43,0.35)"; x.fill(); line(x, d.drawdown, xf, g.y, K.red, 1.4);
    x.fillStyle = K.text; x.textAlign = "left"; x.fillText("drawdown dal massimo del periodo", g.L + 6, 8);
  }
  function equity(canvas, e, w = 860, h = 240) {
    w = Math.max(320, canvas.clientWidth || canvas.parentElement.clientWidth || w);   // la larghezza vera: niente stiramenti
    const x = setup(canvas, w, h), pad = { l: 56, r: 12, t: 22, b: 24 };
    const all = [...e.conto, ...e.spy], tt = (p) => new Date(p.t).getTime();
    if (!e.conto.length) { x.fillStyle = K.text; x.fillText("Il grafico parte appena la società ha letto il conto da IBKR.", 20, h / 2); return; }
    const t0 = Math.min(...all.map(tt)), t1 = Math.max(...all.map(tt)), vals = all.map((p) => p.v);
    const lo = Math.min(...vals, 100) - 0.3, hi = Math.max(...vals, 100) + 0.3, g = frame(x, w, h, lo, hi, 4, (v) => v.toFixed(1), pad);
    const xf = (p) => g.L + ((tt(p) - t0) / Math.max(t1 - t0, 1)) * (g.R - g.L);
    const draw = (arr, col, wd) => { x.beginPath(); x.strokeStyle = col; x.lineWidth = wd; arr.forEach((p, i) => (i ? x.lineTo(xf(p), g.y(p.v)) : x.moveTo(xf(p), g.y(p.v)))); x.stroke(); arr.forEach((p) => { x.fillStyle = col; x.fillRect(xf(p) - 2, g.y(p.v) - 2, 4, 4); }); };
    x.strokeStyle = K.grid; x.setLineDash([3, 3]); x.beginPath(); x.moveTo(g.L, g.y(100)); x.lineTo(g.R, g.y(100)); x.stroke(); x.setLineDash([]);
    draw(e.spy, K.cyan, 1.6); draw(e.conto, K.gold, 2.2);
    legend(x, [["il conto", K.gold], ["S&P 500 (SPY)", K.cyan]], g.L, 0);
    x.fillStyle = K.text; x.textAlign = "center"; [0, 0.5, 1].forEach((f) => x.fillText(new Date(t0 + f * (t1 - t0)).toISOString().slice(5, 10), g.L + f * (g.R - g.L), h - 10));
  }
  function heat(canvas, c, w = 860) {
    w = Math.max(320, canvas.clientWidth || canvas.parentElement.clientWidth || w);   // la larghezza vera: niente stiramenti
    const n = c.simboli.length, cell = Math.min(34, Math.floor((w - 70) / Math.max(n, 1))), h = 30 + n * cell + 8;
    const x = setup(canvas, w, h); x.textAlign = "center";
    const col = (v) => (v >= 0 ? `rgba(252,108,58,${0.12 + 0.88 * v})` : `rgba(10,58,229,${0.12 + 0.88 * -v})`);
    c.simboli.forEach((s, i) => {
      x.fillStyle = K.text; x.textAlign = "right"; x.fillText(s, 62, 30 + i * cell + cell / 2);
      x.save(); x.translate(70 + i * cell + cell / 2, 24); x.rotate(-Math.PI / 4); x.textAlign = "left"; x.fillText(s, 0, 0); x.restore();
      c.matrice[i].forEach((v, j) => { x.fillStyle = col(v); x.fillRect(70 + j * cell, 30 + i * cell, cell - 1, cell - 1); if (cell >= 26) { x.fillStyle = Math.abs(v) > 0.5 ? "#fff" : K.paper; x.textAlign = "center"; x.fillText(v.toFixed(1), 70 + j * cell + cell / 2, 30 + i * cell + cell / 2); } });
    });
  }

  const eur = (v) => (Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(2) + " M" : (v / 1e3).toFixed(0) + " k");
  function fan(canvas, m, w = 860, h = 300) {
    w = Math.max(320, canvas.clientWidth || canvas.parentElement.clientWidth || w);   // la larghezza vera: niente stiramenti
    const x = setup(canvas, w, h), pad = { l: 64, r: 78, t: 22, b: 24 }, F = m.ventaglio, n = m.passi.length;
    const all = [...F["5"], ...F["95"], m.kill_livello, m.nav0], lo = Math.min(...all) * 0.97, hi = Math.max(...all) * 1.03;
    const g = frame(x, w, h, lo, hi, 5, eur, pad), xf = xs(n, g.L, g.R);
    const band = (a, b, col) => { x.beginPath(); a.forEach((v, i) => (i ? x.lineTo(xf(i), g.y(v)) : x.moveTo(xf(i), g.y(v)))); for (let i = n - 1; i >= 0; i--) x.lineTo(xf(i), g.y(b[i])); x.closePath(); x.fillStyle = col; x.fill(); };
    band(F["95"], F["5"], "rgba(10,58,229,0.14)"); band(F["75"], F["25"], "rgba(10,58,229,0.28)");
    x.setLineDash([5, 4]); x.strokeStyle = K.paper; x.beginPath(); x.moveTo(g.L, g.y(m.nav0)); x.lineTo(g.R, g.y(m.nav0)); x.stroke();
    x.strokeStyle = K.red; x.beginPath(); x.moveTo(g.L, g.y(m.kill_livello)); x.lineTo(g.R, g.y(m.kill_livello)); x.stroke(); x.setLineDash([]);
    line(x, F["50"], xf, g.y, K.gold, 2.4);
    x.textAlign = "left"; [["95", K.cyan], ["75", K.cyan], ["50", K.gold], ["25", K.cyan], ["5", K.cyan]].forEach(([q, c]) => { x.fillStyle = c; x.fillText(q + "° " + eur(F[q][n - 1]), g.R + 6, g.y(F[q][n - 1])); });
    x.fillStyle = K.red; x.textAlign = "left"; x.fillText("KILL " + eur(m.kill_livello), g.L + 6, g.y(m.kill_livello) - 9);
    x.textAlign = "center"; x.fillStyle = K.text; [0, 0.25, 0.5, 0.75, 1].forEach((f) => x.fillText(Math.round((f * m.giorni) / 21) + " mesi", g.L + f * (g.R - g.L), h - 10));
    legend(x, [["mediana", K.gold], ["50% dei casi", "rgba(10,58,229,0.55)"], ["90% dei casi", "rgba(10,58,229,0.25)"], ["capitale oggi", K.paper]], g.L, 0);
  }
  function hist(canvas, m, w = 860, h = 190) {
    w = Math.max(320, canvas.clientWidth || canvas.parentElement.clientWidth || w);   // la larghezza vera: niente stiramenti
    const x = setup(canvas, w, h), pad = { l: 40, r: 12, t: 18, b: 26 }, c = m.istogramma.conteggi, e = m.istogramma.bordi, mx = Math.max(...c);
    const L = pad.l, R = w - pad.r, T = pad.t, B = h - pad.b, bw = (R - L) / c.length, lo = e[0], hi = e[e.length - 1], xv = (v) => L + ((v - lo) / (hi - lo)) * (R - L);
    c.forEach((v, i) => { const mid = (e[i] + e[i + 1]) / 2, bh = (v / mx) * (B - T); x.fillStyle = mid < 0 ? "rgba(198,54,43,0.8)" : "rgba(18,128,74,0.8)"; x.fillRect(L + i * bw + 1, B - bh, bw - 2, bh); });
    x.strokeStyle = K.paper; x.beginPath(); x.moveTo(xv(0), T); x.lineTo(xv(0), B); x.stroke();
    x.fillStyle = K.text; x.textAlign = "center"; [lo, lo / 2, 0, hi / 2, hi].forEach((v) => x.fillText((v * 100).toFixed(0) + "%", xv(v), h - 10));
    x.textAlign = "left"; x.fillText("come finisce l'anno, su 5.000 percorsi (rosso = in perdita)", L + 4, 8);
  }
  function bars(canvas, rows, w = 860) {
    w = Math.max(320, canvas.clientWidth || canvas.parentElement.clientWidth || w);   // la larghezza vera: niente stiramenti
    const rh = 26, h = 14 + rows.length * rh, x = setup(canvas, w, h), L = 210, R = w - 340, mx = Math.max(...rows.map((r) => Math.abs(r.v)), 1e-9);
    rows.forEach((r, i) => {
      const y = 8 + i * rh, bw = (Math.abs(r.v) / mx) * (R - L);
      x.fillStyle = K.text; x.textAlign = "right"; x.fillText(r.name, L - 8, y + 11);
      x.fillStyle = r.v < 0 ? "rgba(198,54,43,0.85)" : "rgba(252,108,58,0.85)"; x.fillRect(L, y + 2, Math.max(bw, 1), 16);
      x.fillStyle = K.paper; x.textAlign = "left"; x.fillText(r.label, L + Math.max(bw, 1) + 8, y + 11);
    });
  }

  function expect(canvas, e, zoom, w = 860, h = 340) {
    w = Math.max(320, canvas.clientWidth || canvas.parentElement.clientWidth || w);   // la larghezza vera: niente stiramenti
    const x = setup(canvas, w, h), pad = { l: 64, r: 76, t: 24, b: 26 }, T0 = new Date(e.registrata.slice(0, 19) + "Z").getTime(), T1 = T0 + zoom * 86400000;
    const tm = (iso) => new Date(iso.slice(0, 19) + (iso.endsWith("Z") ? "" : "Z")).getTime();
    const idx = e.date.map((d, i) => [tm(d), i]).filter(([t]) => t <= T1 + 86400000).map(([, i]) => i);
    const cut = (arr) => idx.map((i) => arr[i]), ts = idx.map((i) => tm(e.date[i]));
    const real = e.realizzato.map((p) => ({ t: tm(p.t), v: p.v })).filter((p) => p.t <= T1);
    const vals = [...cut(e.modello["5"]), ...cut(e.modello["95"]), ...cut(e.realistico["5"]), ...cut(e.realistico["95"]), ...real.map((p) => p.v), e.nav0];
    const lo = Math.min(...vals) * 0.995, hi = Math.max(...vals) * 1.005, g = frame(x, w, h, lo, hi, 5, eur, pad);
    const xf = (t) => g.L + ((t - T0) / (T1 - T0)) * (g.R - g.L);
    const band = (a, b, col) => { x.beginPath(); a.forEach((v, i) => (i ? x.lineTo(xf(ts[i]), g.y(v)) : x.moveTo(xf(ts[i]), g.y(v)))); for (let i = a.length - 1; i >= 0; i--) x.lineTo(xf(ts[i]), g.y(b[i])); x.closePath(); x.fillStyle = col; x.fill(); };
    band(cut(e.modello["95"]), cut(e.modello["5"]), "rgba(10,58,229,0.10)"); band(cut(e.modello["75"]), cut(e.modello["25"]), "rgba(10,58,229,0.20)");
    band(cut(e.realistico["95"]), cut(e.realistico["5"]), "rgba(252,108,58,0.12)"); band(cut(e.realistico["75"]), cut(e.realistico["25"]), "rgba(252,108,58,0.26)");
    const ln = (arr, col, wd, dash) => { x.beginPath(); x.strokeStyle = col; x.lineWidth = wd; x.setLineDash(dash || []); arr.forEach((v, i) => (i ? x.lineTo(xf(ts[i]), g.y(v)) : x.moveTo(xf(ts[i]), g.y(v)))); x.stroke(); x.setLineDash([]); };
    ln(cut(e.modello["50"]), K.cyan, 1.6, [6, 4]); ln(cut(e.realistico["50"]), K.gold, 2);
    x.setLineDash([3, 4]); x.strokeStyle = K.grid; x.beginPath(); x.moveTo(g.L, g.y(e.nav0)); x.lineTo(g.R, g.y(e.nav0)); x.stroke(); x.setLineDash([]);
    if (real.length) {
      x.beginPath(); x.strokeStyle = K.paper; x.lineWidth = 2.6; real.forEach((p, i) => (i ? x.lineTo(xf(p.t), g.y(p.v)) : x.moveTo(xf(p.t), g.y(p.v)))); x.stroke();
      const q = real[real.length - 1]; x.fillStyle = K.paper; x.beginPath(); x.arc(xf(q.t), g.y(q.v), 4, 0, 7); x.fill();
      x.textAlign = "left"; x.fillText(eur(q.v), Math.min(xf(q.t) + 8, g.R + 4), g.y(q.v));
    }
    x.textAlign = "center"; x.fillStyle = K.text;
    [0, 0.25, 0.5, 0.75, 1].forEach((f) => { const d = new Date(T0 + f * (T1 - T0)); x.fillText(d.getUTCDate() + "/" + (d.getUTCMonth() + 1), g.L + f * (g.R - g.L), h - 10); });
    legend(x, [["conto reale", K.paper], ["aspettativa del modello", K.cyan], ["aspettativa realistica", K.gold], ["capitale di partenza", K.grid]], g.L, 0);
  }
  return { price, rsi, vol, drawdown, equity, heat, fan, hist, bars, expect };
})();
