// GERVA Capital — portale. Mostra e comanda; non esegue ordini (nessun pulsante invia ordini).
"use strict";

const TOKEN = document.querySelector('meta[name="andrea-token"]').content;
const cv = document.getElementById("office");
const ctx = cv.getContext("2d");
ctx.imageSmoothingEnabled = false;
const W = cv.width, H = cv.height;

// ------------------------------------------------------------------ pianta
const RW = 120, RH = 160, CORR_Y = 160, CORR_H = 24;
const ROOMS = {
  capo:        { c: 0, r: 0, name: "UFFICIO DEL CAPO",   floor: ["#4a1c28", "#56222f"] },
  rischio:     { c: 1, r: 0, name: "SALA RISCHIO",       floor: ["#262c34", "#2c333c"] },
  ricerca:     { c: 2, r: 0, name: "LABORATORIO RICERCA", floor: ["#1f3a2a", "#244230"] },
  validazione: { c: 3, r: 0, name: "SALA VALIDAZIONE",   floor: ["#2e2442", "#352a4a"] },
  trading:     { c: 0, r: 1, name: "TRADING FLOOR",      floor: ["#1a2440", "#1e2a48"] },
  redazione:   { c: 1, r: 1, name: "REDAZIONE",          floor: ["#3a2c1e", "#403222"] },
  dati:        { c: 2, r: 1, name: "SALA DATI",          floor: ["#1a3438", "#1e3c40"] },
  hr:          { c: 3, r: 1, name: "HR / TALENT",        floor: ["#34321e", "#3c3a24"] },
};
function roomXY(room) { const R = ROOMS[room] || ROOMS.capo; return [R.c * RW, R.r === 0 ? 0 : CORR_Y + CORR_H]; }
function deskXY(room, slot) {
  const [x, y] = roomXY(room);
  return [x + 14 + (slot % 2) * 56, y + 36 + Math.floor(slot / 2) * 30];
}
function charXY(a) { const [dx, dy] = deskXY(a.room, a.desk); return [dx + 14, dy - 13]; }

// ------------------------------------------------------------------ stato
let AGENTS = [], STATE = null, frame = 0, soundOn = false;
const walkers = [];            // agenti che camminano con una cartella
const flashes = [];            // lampi rossi su allarme
const screenLines = Array.from({ length: 4 }, () => Array.from({ length: 24 }, () => 0.5));

async function api(path, opts = {}) {
  const r = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json", "X-Andrea-Token": TOKEN } }, opts));
  if (!r.ok) throw new Error((await r.text()) || r.status);
  return r.json();
}
const fmtEur = (x) => (x == null ? "—" : x.toLocaleString("it-IT", { maximumFractionDigits: 0 }) + " €");
const fmtE2 = (x) => (x == null ? "—" : x.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 3 }) + " €");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pct = (x, d = 1) => (x == null ? "—" : (x * 100).toFixed(d).replace(".", ",") + "%");

// ------------------------------------------------------------------ suoni 8-bit (spenti di default)
let actx = null;
function beep(freq = 660, dur = 0.06, type = "square") {
  if (!soundOn) return;
  actx = actx || new (window.AudioContext || window.webkitAudioContext)();
  const o = actx.createOscillator(), g = actx.createGain();
  o.type = type; o.frequency.value = freq; g.gain.value = 0.04;
  o.connect(g).connect(actx.destination); o.start(); o.stop(actx.currentTime + dur);
}
document.getElementById("sound").onclick = (e) => { soundOn = !soundOn; e.target.textContent = "Suoni: " + (soundOn ? "ON" : "OFF"); beep(880); };

// ------------------------------------------------------------------ disegno
function px(x, y, w, h, c) { ctx.fillStyle = c; ctx.fillRect(Math.round(x), Math.round(y), w, h); }
function text(s, x, y, c = PAL.paper, size = 10) { ctx.font = size + "px VT323"; ctx.fillStyle = c; ctx.fillText(s, x, y); }

function drawRoom(id) {
  const R = ROOMS[id], [x, y] = roomXY(id);
  for (let ty = 0; ty < RH; ty += 8) for (let tx = 0; tx < RW; tx += 8)
    px(x + tx, y + ty, 8, 8, R.floor[((tx + ty) / 8) % 2]);
  px(x, y, RW, 14, PAL.wall); px(x, y + 14, RW, 2, PAL.wallLo);         // muro alto con targa
  px(x, y, 2, RH, PAL.wallHi); px(x + RW - 2, y, 2, RH, PAL.wallLo);
  px(x + RW / 2 - 10, y + RH - 2, 20, 2, R.floor[0]);                     // porta sul corridoio
  text(R.name, x + 5, y + 10, PAL.gold);
  decor(id, x, y);
}

function decor(id, x, y) {
  if (id === "capo") {                          // tappeto e pianta
    px(x + 30, y + 110, 60, 34, "#7a2a36"); px(x + 34, y + 114, 52, 26, "#8e3442");
    px(x + 104, y + 128, 8, 10, PAL.woodDk); px(x + 101, y + 118, 14, 10, PAL.greenDk); px(x + 104, y + 114, 8, 6, PAL.green);
  }
  if (id === "rischio") {                       // lampada di allerta
    const light = STATE ? STATE.semaforo : "verde";
    const on = light !== "rosso" || Math.floor(frame / 15) % 2 === 0;
    const col = light === "rosso" ? (on ? PAL.red : PAL.redDk) : light === "giallo" ? PAL.amber : PAL.green;
    px(x + 98, y + 20, 12, 12, PAL.ink); px(x + 100, y + 22, 8, 8, col);
    if (light === "rosso" && on) { ctx.fillStyle = "rgba(217,72,59,0.18)"; ctx.fillRect(x, y + 16, RW, RH - 16); }
    text(light.toUpperCase(), x + 74, y + 30, col, 9);
  }
  if (id === "ricerca") {                       // lavagna
    px(x + 64, y + 128, 50, 26, "#1e3324"); px(x + 64, y + 128, 50, 2, PAL.woodHi);
    text("SR=μ/σ·√252", x + 66, y + 140, "#cfe8cf", 9); text("DSR≥0,95", x + 66, y + 150, "#cfe8cf", 9);
  }
  if (id === "validazione") { text("RED TEAM", x + 72, y + 152, PAL.red, 10); px(x + 60, y + 144, 8, 8, PAL.grey); px(x + 66, y + 150, 4, 4, PAL.woodDk); }
  if (id === "trading") {                       // schermi a parete con le curve
    for (let s = 0; s < 4; s++) {
      const sx = x + 6 + s * 28, sy = y + 18;
      px(sx, sy, 26, 14, PAL.ink); px(sx + 1, sy + 1, 24, 12, PAL.screen);
      const L = screenLines[s];
      for (let i = 1; i < L.length; i++) px(sx + 1 + i, sy + 1 + Math.round(11 * (1 - L[i])), 1, 1, i % 2 ? PAL.green : "#7fe0a0");
    }
  }
  if (id === "redazione") { px(x + 100, y + 136, 14, 10, PAL.paper); px(x + 100, y + 139, 14, 1, PAL.grey); px(x + 100, y + 142, 14, 1, PAL.grey); }
  if (id === "dati") {                          // armadi server
    for (let s = 0; s < 2; s++) {
      const sx = x + 86 + s * 14, sy = y + 96;
      px(sx, sy, 12, 50, "#2a2a36"); px(sx, sy, 12, 1, PAL.grey);
      for (let l = 0; l < 6; l++) px(sx + 3 + (l % 2) * 5, sy + 5 + l * 7, 2, 2, (frame + l * 7 + s * 13) % 40 < 20 ? PAL.green : PAL.greenDk);
    }
  }
  if (id === "hr") { px(x + 88, y + 126, 26, 4, PAL.woodDk); px(x + 92, y + 118, 6, 8, PAL.gold); px(x + 104, y + 120, 6, 6, PAL.grey); text("MERITO", x + 86, y + 142, PAL.gold, 9); }
}

function drawCorridor() {
  for (let tx = 0; tx < W; tx += 8) for (let ty = 0; ty < CORR_H; ty += 8)
    px(tx, CORR_Y + ty, 8, 8, (tx / 8 + ty / 8) % 2 ? "#2a2636" : "#24202f");
}

function drawDesk(dx, dy, kind, status) {
  px(dx, dy, 40, 12, PAL.wood); px(dx, dy, 40, 2, PAL.woodHi); px(dx, dy + 12, 40, 2, PAL.woodDk);
  if (kind !== "open") {
    px(dx + 24, dy - 6, 12, 8, PAL.ink); px(dx + 25, dy - 5, 10, 6, kind === "code" ? "#163048" : PAL.screen);
    if ((frame >> 3) % 2) px(dx + 26, dy - 3, 4, 1, kind === "code" ? PAL.cyan : PAL.green);
    px(dx + 29, dy + 2, 2, 2, PAL.greyDk);
  } else {
    px(dx + 6, dy + 3, 28, 7, PAL.paper); text("VACANTE", dx + 8, dy + 9, PAL.redDk, 8);
  }
}

const BUBBLE = { pensa: "…", legge: "…", scrive: "✎", dorme: "Zz", riunione: "⚑", verifica: "✓", errore: "!", automa: "", attesa: "", cammina: "▤" };

function drawBubble(x, y, s, warn) {
  if (!s) return;
  const w = Math.max(10, s.length * 5 + 4);
  px(x, y, w, 9, warn ? PAL.red : PAL.paper); px(x + 2, y + 9, 2, 2, warn ? PAL.red : PAL.paper);
  text(s, x + 2, y + 8, warn ? PAL.white : PAL.ink, 9);
}

function drawAgents() {
  for (const a of AGENTS) {
    const [dx, dy] = deskXY(a.room, a.desk);
    const walking = walkers.find((w) => w.id === a.id);
    if (a.kind !== "open" && !walking) {
      const [cx, cy] = charXY(a);
      const bob = a.stato === "dorme" ? 0 : (frame + a.desk * 11) % 60 < 30 ? 0 : -1;
      const spr = a.kind === "code" ? robotSprite((frame >> 4) % 2 === 0) : personSprite(a);
      ctx.drawImage(spr, cx, cy + bob);
      let b = BUBBLE[a.stato] ?? "…";
      if (a.stato === "dorme") b = ["Z", "Zz", "Zzz"][(frame >> 4) % 3];
      if (a.stato === "scrive" && (frame >> 2) % 2) px(cx + 3, cy + 10, 6, 1, PAL.paper);   // mani sulla tastiera
      drawBubble(cx + 9, cy - 11, b, a.stato === "errore");
    }
    drawDesk(dx, dy, a.kind, a.status);
    if (a.kind !== "open") {          // targhetta col nome sul fronte della scrivania (non copre i vicini)
      const label = a.kind === "code" ? a.name.replace("Automa ", "").replace("GERVA-Q v3", "GERVA-Q") : a.name.split(" ")[0];
      px(dx + 2, dy + 5, 36, 7, PAL.woodDk);
      text(label.slice(0, 9), dx + 4, dy + 11, a.kind === "code" ? PAL.cyan : PAL.paper, 8);
    }
  }
}

// ------------------------------------------------------------------ cartelline che viaggiano
function pathBetween(a, b) {
  const [x1, y1] = charXY(a), [x2, y2] = charXY(b);
  const cy = CORR_Y + 6, doorA = roomXY(a.room)[0] + RW / 2 - 6, doorB = roomXY(b.room)[0] + RW / 2 - 6;
  if (a.room === b.room) return [[x1, y1], [x1, y1 + 14], [x2, y1 + 14], [x2, y2]];
  return [[x1, y1], [doorA, y1 < CORR_Y ? y1 : y1], [doorA, cy], [doorB, cy], [doorB, y2 + 14], [x2, y2 + 14], [x2, y2]];
}
function spawnWalker(fromId, toId, back = false) {
  const a = AGENTS.find((x) => x.id === fromId), b = AGENTS.find((x) => x.id === toId);
  if (!a || !b || a.kind === "open" || b.kind === "open" || walkers.length > 6) return;
  const go = pathBetween(a, b), path = back ? go : go.concat(go.slice().reverse().slice(1));
  walkers.push({ id: a.id, agent: a, path, seg: 0, t: 0, folder: true });
  beep(520, 0.05);
}
function drawWalkers() {
  for (let i = walkers.length - 1; i >= 0; i--) {
    const w = walkers[i];
    const [x1, y1] = w.path[w.seg], [x2, y2] = w.path[w.seg + 1];
    const d = Math.hypot(x2 - x1, y2 - y1) || 1;
    w.t += 1.4 / d;
    if (w.t >= 1) { w.t = 0; w.seg++; if (w.seg >= w.path.length - 1) { walkers.splice(i, 1); continue; } }
    const x = x1 + (x2 - x1) * w.t, y = y1 + (y2 - y1) * w.t;
    const spr = w.agent.kind === "code" ? robotSprite(true) : personSprite(w.agent);
    ctx.drawImage(spr, Math.round(x), Math.round(y) + ((frame >> 2) % 2));
    if (w.folder && w.seg < w.path.length / 2) ctx.drawImage(folderSprite(), Math.round(x) + 8, Math.round(y) + 8);
  }
}

function render() {
  frame++;
  if (frame % 20 === 0) for (const L of screenLines) { L.shift(); L.push(Math.min(0.95, Math.max(0.05, L[L.length - 1] + (Math.random() - 0.48) * 0.12))); }
  px(0, 0, W, H, PAL.ink);
  for (const id in ROOMS) drawRoom(id);
  drawCorridor();
  text("CORRIDOIO", 4, CORR_Y + 15, PAL.greyDk, 9);
  drawAgents();
  drawWalkers();
  for (let i = flashes.length - 1; i >= 0; i--) { const f = flashes[i]; ctx.fillStyle = `rgba(217,72,59,${f.a})`; ctx.fillRect(0, 0, W, H); f.a -= 0.01; if (f.a <= 0) flashes.splice(i, 1); }
  requestAnimationFrame(render);
}

// ------------------------------------------------------------------ dati dal backend
async function refreshState() {
  try {
    STATE = await api("/api/state");
    const s = STATE;
    document.getElementById("nav").textContent = fmtEur(s.nav);
    const p = document.getElementById("pnl"); p.textContent = (s.pnl >= 0 ? "+" : "") + fmtEur(s.pnl); p.className = s.pnl >= 0 ? "pos" : "neg";
    document.getElementById("light").className = "light " + s.semaforo;
    document.getElementById("lighttxt").textContent = s.kill ? "KILL" : s.semaforo;
    document.getElementById("bud").textContent = fmtE2(s.budget_oggi) + " / " + fmtE2(s.tetto_oggi);
    document.getElementById("budtot").textContent = fmtE2(s.budget_totale) + " / " + fmtE2(s.tetto_totale);
    document.getElementById("days").textContent = s.sciopero ? "SCIOPERO" : s.giorni_residui == null ? "∞ (nessuna spesa)" : s.giorni_residui.toFixed(1) + " gg";
    document.getElementById("ledger").textContent = s.ledger.disponibile ? (s.ledger.righe ? s.ledger.righe + " righe" : "nessuna riga") : "GERVA-Q non trovato";
    document.getElementById("chain").textContent = s.catena ? "integra" : "ROTTA";
    document.getElementById("mailn").textContent = s.posta_aperta || "";
    document.getElementById("simbanner").classList.toggle("hidden", !s.simulato);
    document.getElementById("demobanner").classList.toggle("hidden", !s.demo);
  } catch (e) { console.warn(e); }
}
async function refreshOffice() { try { AGENTS = await api("/api/office"); } catch (e) { console.warn(e); } }

const tickerItems = [];
function pushTicker(s) {
  tickerItems.unshift(s); tickerItems.length = Math.min(tickerItems.length, 12);
  document.getElementById("tickertext").textContent = tickerItems.join("   ◆   ");
}
function onEvent(ev) {
  const p = ev.payload || {};
  if (ev.kind === "task.handoff") spawnWalker(p.da, p.a);
  if (ev.kind === "task.done" && p.a && p.a !== "andrea") spawnWalker(ev.actor, p.a, true);
  if (ev.kind === "agent.status") { const a = AGENTS.find((x) => x.id === ev.actor); if (a) a.stato = p.stato; }
  if (ev.kind === "agent.error") { const a = AGENTS.find((x) => x.id === ev.actor); if (a) a.stato = "errore"; }
  if (ev.kind.startsWith("risk.alert") || ev.kind === "risk.kill") { flashes.push({ a: 0.25 }); beep(220, 0.2, "sawtooth"); }
  const T = {
    "news.bulletin": () => "📰 " + (p.testo || "").slice(0, 120), "risk.alert": () => "⚠ " + p.cosa, "risk.kill": () => "⛔ KILL: " + p.motivo,
    "risk.kill_recommended": () => "⚠ " + ev.actor + " raccomanda il KILL: " + p.motivo, "postmortem": () => "✎ Post-mortem " + p.agente + ": " + p.lezione,
    "career.promozione": () => "★ Promozione: " + p.agente + " → " + p.a, "career.retrocessione": () => "▼ Retrocessione: " + p.agente,
    "gateway.rejected": () => "✕ Gateway respinge " + p.strumento + " (" + (p.motivi || []).join("; ").slice(0, 80) + ")",
    "gateway.accepted": () => "✓ Gateway accetta " + p.lato + " " + p.qty + " " + p.strumento + " [" + p.pod + "]",
    "mailbox.new": () => "✉ Posta del Capo: " + p.title, "committee.decision": () => "⚖ Comitato: " + p.ricerca + " → " + p.esito,
    "budget.strike": () => "Zz Sciopero: " + p.motivo, "pod.capital": () => "◈ Capitale " + p.pod + ": " + pct(p.da) + " → " + pct(p.a),
  };
  if (T[ev.kind]) pushTicker(T[ev.kind]());
}
function connectWS() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (m) => JSON.parse(m.data).forEach(onEvent);
  ws.onclose = () => setTimeout(connectWS, 3000);
}

// ------------------------------------------------------------------ click su un personaggio -> dialogo RPG
cv.addEventListener("click", (e) => {
  const r = cv.getBoundingClientRect();
  const x = (e.clientX - r.left) * (W / r.width), y = (e.clientY - r.top) * (H / r.height);
  const hit = AGENTS.find((a) => { const [dx, dy] = deskXY(a.room, a.desk); return x >= dx - 2 && x <= dx + 42 && y >= dy - 26 && y <= dy + 22; });
  if (hit) openAgent(hit);
});

function show(id) { document.getElementById(id).classList.remove("hidden"); }
document.querySelectorAll("[data-close]").forEach((b) => (b.onclick = () => document.getElementById(b.dataset.close).classList.add("hidden")));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") ["dialog", "panel"].forEach((i) => document.getElementById(i).classList.add("hidden")); });

function kv(obj) { return '<div class="kv">' + Object.entries(obj).map(([k, v]) => `<span>${esc(k)}</span><span>${esc(Array.isArray(v) ? v.join(", ") : v)}</span>`).join("") + "</div>"; }
function table(rows, cols) {
  if (!rows || !rows.length) return '<p class="muted">Nessun dato.</p>';
  return "<table><tr>" + cols.map((c) => `<th>${esc(c[1])}</th>`).join("") + "</tr>" +
    rows.map((r) => "<tr>" + cols.map((c) => `<td>${typeof c[2] === "function" ? c[2](r[c[0]], r) : esc(r[c[0]])}</td>`).join("") + "</tr>").join("") + "</table>";
}

async function openAgent(a) {
  document.getElementById("dlgtitle").textContent = a.kind === "open" ? "POSIZIONE APERTA" : `${a.name} — ${a.role}`;
  const body = document.getElementById("dlgbody"), tabsEl = document.getElementById("dlgtabs");
  show("dialog"); beep(760);
  if (a.kind === "open") {
    tabsEl.innerHTML = "";
    body.innerHTML = `<p>Scrivania vuota: <b>${esc(a.role)}</b> (${esc(a.dept)}).</p><p class="muted">Si assume quando il costo e il valore lo giustificano. Superiore: ${esc(a.superior)}.</p>`;
    return;
  }
  body.innerHTML = '<p class="muted">Caricamento…</p>';
  const d = await api("/api/agent/" + a.id);
  const P = d.profilo, R = d.risultati, C = d.costi;
  const tabs = {
    "Profilo": () => kv({ Nome: P.nome, Ruolo: P.ruolo, Reparto: P.reparto, Grado: P.grado, Superiore: P.superiore || "—", Subordinati: P.subordinati.join(", ") || "—",
      Modello: P.modello, "Budget/giorno": P.budget_giorno ? fmtE2(P.budget_giorno) : "—", Stato: P.stato, Strumenti: P.strumenti.join(", ") || "—",
      ...(P.filosofia ? { Filosofia: P.filosofia } : {}), "Versione prompt": P.versione_prompt || "—" }),
    "Ora": () => `<p><b>${esc(d.ora.attivita.stato)}</b> ${esc(d.ora.attivita.compito)}</p>` +
      table(d.ora.eventi, [["ts", "Quando", (v) => esc((v || "").slice(5, 16).replace("T", " "))], ["kind", "Evento"], ["payload", "Dettagli", (v) => esc(JSON.stringify(v).slice(0, 140))]]),
    "Risultati": () => {
      const pt = R.punteggio, F = R.previsioni;
      let h = kv({ "Punteggio composito": pt.punteggio == null ? "nessuna valutazione ancora" : pt.punteggio.toFixed(3), "Metriche dure (70%)": pt.dure == null ? "—" : pt.dure.toFixed(3),
        "Valutazioni dei pari (30%)": pt.pari == null ? "—" : pt.pari.toFixed(3), "Valutazioni": pt.n_valutazioni, "Canarini superati": `${pt.canarini_superati}/${pt.canarini}`,
        "Previsioni giuste / sbagliate": `${F.giuste} / ${F.sbagliate} (aperte ${F.aperte})`, "Brier": F.brier == null ? "—" : F.brier.toFixed(3) + " (0,25 = moneta)" });
      h += "<h3>Calibrazione</h3>" + calibChart(F.curva || []);
      h += "<h3>Metriche</h3>" + table(R.metriche, [["metric", "Metrica"], ["n", "N"], ["media", "Media", (v) => (v == null ? "—" : (+v).toFixed(3))]]);
      return h;
    },
    "Errori": () => table(d.errori, [["ts", "Quando", (v) => esc((v || "").slice(0, 10))], ["what", "Cosa"], ["why", "Perché"], ["change", "Cosa cambia"], ["lesson", "Lezione"]]),
    "Carriera": () => table(d.carriera, [["ts", "Quando", (v) => esc((v || "").slice(0, 10))], ["kind", "Evento"], ["reason", "Motivo"]]),
    "Costi e GC": () => kv({ "Token oggi (in/out)": `${C.oggi.i} / ${C.oggi.o}`, "Euro oggi": fmtE2(C.oggi.c), "Token totali (in/out)": `${C.totale.i} / ${C.totale.o}`,
      "Euro totali": fmtE2(C.totale.c), "Chiamate": C.totale.n, "Gerva-Coin saldo": (C.gc.saldo || 0).toFixed(1), "GC bonus": (C.gc.bonus || 0).toFixed(1), "GC spesi": (-(C.gc.spesa || 0)).toFixed(1) }),
    "Memoria": () => `<pre>${esc(d.memoria || "(vuota)")}</pre><p class="muted">Sola lettura. La aggiorna il Talent Manager dopo le post-mortem.</p>`,
  };
  tabsEl.innerHTML = Object.keys(tabs).map((t, i) => `<button class="${i ? "" : "on"}">${t}</button>`).join("");
  const sel = (name) => { body.innerHTML = tabs[name](); tabsEl.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.textContent === name)); };
  tabsEl.querySelectorAll("button").forEach((b) => (b.onclick = () => sel(b.textContent)));
  sel("Profilo");
}

function calibChart(curve) {
  if (!curve.length) return '<p class="muted">Nessuna previsione risolta.</p>';
  const s = 120;
  let svg = `<svg width="${s + 20}" height="${s + 20}" viewBox="-10 -10 ${s + 20} ${s + 20}" style="background:#0b1636"><line x1="0" y1="${s}" x2="${s}" y2="0" stroke="#5a5080" stroke-dasharray="3"/>`;
  for (const c of curve) svg += `<rect x="${c.prob_media * s - 3}" y="${(1 - c.frequenza) * s - 3}" width="6" height="6" fill="#e8b04a"><title>p=${c.prob_media.toFixed(2)} freq=${c.frequenza.toFixed(2)} n=${c.n}</title></rect>`;
  return svg + "</svg><p class=\"muted\">Diagonale = calibrazione perfetta.</p>";
}

// ------------------------------------------------------------------ pannelli
const PANELS = {
  async org() {
    const t = await api("/api/org");
    const node = (n) => `<li>${esc(n.name)} <span class="muted">${esc(n.role)} · ${esc(n.grade)}</span>${n.kind === "open" ? ' <span class="tag aperta">aperta</span>' : n.kind === "code" ? ' <span class="tag">automa</span>' : ""}${n.children.length ? "<ul>" + n.children.map(node).join("") + "</ul>" : ""}</li>`;
    return ["Organigramma", `<div class="tree"><ul>${node(t)}</ul></div>`];
  },
  async tasks(id) {
    const cmds = await api("/api/commands");
    id = id || (cmds[0] && cmds[0].id);
    let h = table(cmds, [["id", "#"], ["text", "Ordine", (v, r) => `<a href="#" data-cmd="${r.id}">${esc(v.slice(0, 70))}</a>`], ["status", "Stato", (v) => `<span class="tag ${esc(v)}">${esc(v)}</span>`]]);
    if (id) {
      const t = await api("/api/tasks/" + id);
      const node = (n) => `<li><b>${esc(n.assignee)}</b> ← ${esc(n.assigner)}: ${esc(n.title)} <span class="tag ${esc(n.status)}">${esc(n.status)}</span>` +
        (n.result ? `<div class="muted">${esc(typeof n.result === "string" ? n.result : (n.result.risultato || n.result.sintesi || JSON.stringify(n.result))).slice(0, 300)}</div>` : "") +
        (n.children.length ? "<ul>" + n.children.map(node).join("") + "</ul>" : "") + "</li>";
      h += `<h3>Ordine #${id}</h3><p>${esc(t.ordine ? t.ordine.text : "")}</p>` + (t.ordine && t.ordine.answer ? `<pre>${esc(t.ordine.answer)}</pre>` : "") +
        `<div class="tree"><ul>${t.compiti.map(node).join("") || '<li class="muted">Il Capo sta leggendo…</li>'}</ul></div>`;
    }
    return ["Albero compiti", h];
  },
  async mail() {
    const items = await api("/api/mailbox");
    if (!items.length) return ["Posta del Capo", '<p class="muted">Nessuna grande richiesta. Il resto lo decide la società.</p>'];
    return ["Posta del Capo", items.map((m) => `<div class="mailitem"><b>${esc(m.title)}</b> <span class="tag ${esc(m.status)}">${esc(m.status)}</span> <span class="tag">${esc(m.categoria)}</span>
      <p>${esc(m.why)}</p><p><b>Raccomandazione:</b> ${esc(m.recommendation)}</p><p><b>Default sicuro se non rispondi:</b> ${esc(m.safe_default)}</p>
      ${m.status === "aperta" ? m.options.map((o) => `<button data-mail="${m.id}" data-choice="${esc(o)}">Scegli: ${esc(o)}</button>`).join("") + `<button data-mail="${m.id}" data-choice="__rimanda__">Rimanda</button>` : `<p class="muted">Scelta: ${esc(m.choice || "rimandata (vale il default)")}</p>`}</div>`).join("")];
  },
  async pods() {
    const d = await api("/api/pods");
    const rows = d.classifica.pod;
    let h = "<h3>Capitale e risultati (solo dati in avanti)</h3>" + table(rows, [["nome", "Pod"], ["capitale", "Capitale", (v) => `<span class="bar" style="width:${Math.round(v * 120)}px"></span> ${pct(v)}`],
      ["stato", "Stato", (v) => `<span class="tag ${esc(v)}">${esc(v)}</span>`], ["giorni", "Giorni"], ["sharpe", "Sharpe in avanti", (v, r) => (v == null ? "<span class='muted'>&lt;30 giorni</span>" : v.toFixed(2) + (r.sharpe_ci90 ? ` [${r.sharpe_ci90.map((x) => x.toFixed(2)).join("; ")}]` : ""))],
      ["drawdown", "Drawdown", (v) => pct(v)], ["alpha_netto_eur", "Alpha netto", (v) => (v == null ? "benchmark" : fmtEur(v))]]);
    h += `<p class="muted">Correlazione media tra pod: ${d.correlazione == null ? "dati insufficienti" : d.correlazione.toFixed(2)}. Confronto con il Pod Zero (benchmark interno) e con SPY quando i dati lo permettono.</p>`;
    h += "<h3>Classifica individuale (Gerva-Coin)</h3>" + table(d.classifica.persone, [["agente", "Agente"], ["gc", "GC", (v) => (+v).toFixed(1)]]);
    const z = d.pod_zero;
    h += "<h3>Pod Zero — GERVA-Q v3 (sola lettura)</h3>" + (z.disponibile ? kv({ "Dati al": z.dati_al, "Candela crypto": z.candela_crypto, Profilo: z.profilo, "Lorda target": pct(z.lorda), "Quota crypto": pct(z.quota_crypto), "Hash del codice": z.hash_codice })
      + table(Object.entries(z.pesi).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ k, v })), [["k", "Strumento"], ["v", "Peso sul NAV", (v) => pct(v, 2)]]) : `<p class="muted">Cartella GERVA-Q non trovata (${esc(z.percorso)}). Imposta GERVA_Q_PATH nel file .env.</p>`);
    return ["Classifica e portafoglio dei pod", h];
  },
  async research() {
    const d = await api("/api/research");
    return ["Ricerca e coda di approvazione", kv({ "Prove registrate (N del DSR)": d.prove.n_trials, "Prove con Sharpe": d.prove.n_with_sharpe, "Varianza Sharpe (giorn.)": d.prove.var_sr.toExponential(2) }) +
      table(d.fascicoli, [["title", "Fascicolo"], ["stage", "Fase", (v) => `<span class="tag ${esc(v)}">${esc(v)}</span>`], ["gate", "Cancello", (v) => (v ? (v.passa ? "passa" : "non passa") + (v.deflated ? ` · DSR ${v.deflated.dsr.toFixed(3)}` : "") : "—")],
        ["validation", "Validazione", (v) => (v ? esc(v.esito) : "—")], ["decision", "Comitato", (v) => (v && v.esito ? esc(v.esito) : "—")]])];
  },
  async gateway() {
    const d = await api("/api/pods");
    return ["Gateway di Esecuzione — ordini accettati e respinti", '<p class="muted">Il portale non invia ordini. Gli ordini arrivano solo dai Capi Pod e passano tutti dai controlli del Gateway.</p>' +
      table(d.ordini, [["ts", "Quando", (v) => esc((v || "").slice(5, 16).replace("T", " "))], ["pod", "Pod"], ["agent_id", "Agente"], ["side", "Lato"], ["qty", "Qtà", (v) => (+v).toFixed(4)], ["instrument", "Strumento"],
        ["status", "Esito", (v) => `<span class="tag ${esc(v)}">${esc(v)}</span>`], ["reject", "Motivo", (v) => esc(v || "")]])];
  },
  async settings() {
    const d = await api("/api/settings");
    const S = d.impostazioni;
    const row = (k, v, kind = "set") => `<div class="setrow"><span>${esc(k)}</span><input data-k="${esc(k)}" data-kind="${kind}" value='${esc(JSON.stringify(v))}'><button data-save="${esc(k)}">Salva</button></div>`;
    const flat = (o, p = "") => Object.entries(o).flatMap(([k, v]) => (v && typeof v === "object" && !Array.isArray(v) ? flat(v, p + k + ".") : [[p + k, v]]));
    let h = `<p>Solo Andrea modifica queste regole; ogni modifica finisce nell'audit log. Autonomia stimata: <b>${d.budget.days_left == null ? "∞" : d.budget.days_left.toFixed(1) + " giorni"}</b> al ritmo di ${fmtE2(d.budget.pace_eur_day)}/giorno.</p>`;
    h += `<button class="${S["firm.strike"] ? "" : "danger"}" id="strikebtn">${S["firm.strike"] ? "Riprendi la società" : "Sciopero (ferma gli agenti)"}</button> <button class="danger" id="killbtn">${STATE && STATE.kill ? "Togli il KILL" : "KILL"}</button>`;
    h += "<h3>Budget, modelli, finestra di rilascio, pod, economia</h3>" + Object.entries(S).filter(([k]) => k !== "firm.mode").map(([k, v]) => row(k, v)).join("");
    h += "<h3>Limiti di rischio (risk_limits.yaml)</h3>" + flat(d.limiti).map(([k, v]) => row(k, v, "risk")).join("");
    h += '<p class="muted">firm.mode è bloccato su «paper»: il passaggio a soldi veri richiede i cancelli 13-15 della sfida e la firma dei titolari del conto.</p>';
    return ["Impostazioni (solo Andrea)", h];
  },
};

async function openPanel(name, arg) {
  const [title, html] = await PANELS[name](arg);
  document.getElementById("pnltitle").textContent = title;
  document.getElementById("pnlbody").innerHTML = html;
  document.getElementById("panel").dataset.name = name;
  show("panel");
}
document.querySelectorAll("[data-panel]").forEach((b) => (b.onclick = () => { beep(600); openPanel(b.dataset.panel); }));

document.getElementById("pnlbody").addEventListener("click", async (e) => {
  const t = e.target;
  try {
    if (t.dataset.cmd) { e.preventDefault(); openPanel("tasks", +t.dataset.cmd); }
    if (t.dataset.mail) { await api("/api/mailbox/" + t.dataset.mail, { method: "POST", body: JSON.stringify({ choice: t.dataset.choice }) }); openPanel("mail"); refreshState(); }
    if (t.dataset.save) {
      const inp = document.querySelector(`input[data-k="${CSS.escape(t.dataset.save)}"]`);
      await api("/api/settings", { method: "POST", body: JSON.stringify({ key: t.dataset.save, value: JSON.parse(inp.value), kind: inp.dataset.kind }) });
      t.textContent = "✓"; refreshState();
    }
    if (t.id === "strikebtn") { const on = t.textContent.startsWith("Sciopero"); await api("/api/strike", { method: "POST", body: JSON.stringify({ on }) }); openPanel("settings"); refreshState(); }
    if (t.id === "killbtn") {
      const on = !(STATE && STATE.kill);
      if (on && !confirm("Attivare il KILL? Il Gateway rifiuterà tutti gli ordini e il Pod Zero cancellerà gli ordini aperti al prossimo giro.")) return;
      await api("/api/kill", { method: "POST", body: JSON.stringify({ on }) }); await refreshState(); openPanel("settings");
    }
  } catch (err) { alert("Errore: " + err.message); }
});

// ------------------------------------------------------------------ barra di comando
document.getElementById("cmd").addEventListener("submit", async (e) => {
  e.preventDefault();
  const inp = document.getElementById("cmdtext"), text = inp.value.trim();
  if (!text) return;
  inp.value = "";
  const r = await api("/api/command", { method: "POST", body: JSON.stringify({ text }) });
  pushTicker("▶ Ordine a Lorenzo Bassi (Capo): " + text.slice(0, 80));
  beep(880, 0.08);
  await openPanel("tasks", r.id);
  let n = 0;
  const poll = setInterval(async () => {
    n++;
    const panel = document.getElementById("panel");
    if (panel.classList.contains("hidden") || panel.dataset.name !== "tasks" || n > 60) return clearInterval(poll);
    const [, html] = await PANELS.tasks(r.id); document.getElementById("pnlbody").innerHTML = html;
  }, 2000);
});

// ------------------------------------------------------------------ avvio
drawMatrix(document.getElementById("lock").getContext("2d"), LOCK, 0, 0, { g: PAL.gold, G: "#c8902a", k: PAL.ink });
document.fonts.load("10px VT323").finally(() => { refreshState(); refreshOffice().then(() => requestAnimationFrame(render)); });
setInterval(refreshState, 5000);
setInterval(refreshOffice, 4000);
connectWS();
