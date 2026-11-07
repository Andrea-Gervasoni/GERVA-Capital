// GERVA Capital — la vita dell'ufficio: persone che camminano, parlano, fanno pausa, vanno in riunione.
// Le azioni legate al lavoro (deleghe, consegne, riunioni, promozioni, allarmi) seguono gli EVENTI VERI
// della societa' con il loro testo; pause e chiacchiere sono animazioni d'ambiente (dichiarato nella legenda).
"use strict";

// il mondo si disegna su una tela fuori schermo a risoluzione nativa; la telecamera la porta sullo schermo
const cv = document.getElementById("office");
const dctx = cv.getContext("2d");
const wc = document.createElement("canvas");
wc.width = CW; wc.height = CH;
const ctx = wc.getContext("2d");
ctx.imageSmoothingEnabled = false;
const cam = { z: 1, cx: CW / 2, cy: CH / 2, drag: null };
function resizeCanvas() {
  const dpr = window.devicePixelRatio || 1;
  cv.width = Math.round(cv.clientWidth * dpr); cv.height = Math.round(cv.clientHeight * dpr);
}
function camScale() { return Math.min(cv.width / CW, cv.height / CH) * cam.z; }
function camView() {
  const s = camScale(), vw = cv.width / s, vh = cv.height / s;
  cam.cx = Math.max(vw / 2, Math.min(CW - vw / 2, cam.cx)); cam.cy = Math.max(vh / 2, Math.min(CH - vh / 2, cam.cy));
  if (vw >= CW) cam.cx = CW / 2;
  if (vh >= CH) cam.cy = CH / 2;
  return { s, x: cam.cx - vw / 2, y: cam.cy - vh / 2, vw, vh };
}
function screenToWorld(e) {
  const r = cv.getBoundingClientRect(), dpr = cv.width / r.width, v = camView();
  return [v.x + ((e.clientX - r.left) * dpr) / v.s, v.y + ((e.clientY - r.top) * dpr) / v.s];
}
function zoomAt(z, wx, wy) {
  const v0 = camView(); cam.z = Math.max(1, Math.min(4, z));
  const v1 = camView();
  if (wx != null) { cam.cx = wx - (wx - cam.cx) * (v1.vw / v0.vw); cam.cy = wy - (wy - cam.cy) * (v1.vh / v0.vh); }
}
cv.addEventListener("wheel", (e) => { e.preventDefault(); const [wx, wy] = screenToWorld(e); zoomAt(cam.z * (e.deltaY < 0 ? 1.25 : 0.8), wx, wy); }, { passive: false });
cv.addEventListener("mousedown", (e) => { cam.drag = { x: e.clientX, y: e.clientY, cx: cam.cx, cy: cam.cy, moved: false }; });
window.addEventListener("mouseup", () => setTimeout(() => (cam.drag = null), 0));
window.addEventListener("mousemove", (e) => {
  if (!cam.drag) return;
  const r = cv.getBoundingClientRect(), s = camScale() * (r.width / cv.width) / (cv.width / cv.width);
  const k = (cv.width / r.width) / camScale();
  const dx = (e.clientX - cam.drag.x) * k, dy = (e.clientY - cam.drag.y) * k;
  if (Math.abs(dx) + Math.abs(dy) > 3) cam.drag.moved = true;
  cam.cx = cam.drag.cx - dx; cam.cy = cam.drag.cy - dy;
});
// doppio clic: si entra nella stanza cliccata (lo zoom PRIMA, il centro DOPO: camView non lo riporta al centro)
cv.addEventListener("dblclick", (e) => { const [wx, wy] = screenToWorld(e); cam.z = cam.z < 2 ? 2.5 : 1; cam.cx = wx; cam.cy = wy; });
// telefono e tablet: un dito sposta, due dita zoomano, doppio tocco entra nella stanza
const touch = { pts: new Map(), d0: 0, z0: 1, last: 0 };
cv.style.touchAction = "none";
cv.addEventListener("pointerdown", (e) => {
  if (e.pointerType === "mouse") return;
  cv.setPointerCapture(e.pointerId);
  touch.pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (touch.pts.size === 1) {
    cam.drag = { x: e.clientX, y: e.clientY, cx: cam.cx, cy: cam.cy, moved: false };
    const now = performance.now();
    if (now - touch.last < 300) { const [wx, wy] = screenToWorld(e); cam.z = cam.z < 2 ? 2.5 : 1; cam.cx = wx; cam.cy = wy; }
    touch.last = now;
  } else if (touch.pts.size === 2) {
    const [a, b] = [...touch.pts.values()]; touch.d0 = Math.hypot(a.x - b.x, a.y - b.y); touch.z0 = cam.z; cam.drag = null;
  }
});
cv.addEventListener("pointermove", (e) => {
  if (e.pointerType === "mouse" || !touch.pts.has(e.pointerId)) return;
  touch.pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (touch.pts.size === 2 && touch.d0 > 0) {
    const [a, b] = [...touch.pts.values()];
    const mid = { clientX: (a.x + b.x) / 2, clientY: (a.y + b.y) / 2 }, [wx, wy] = screenToWorld(mid);
    zoomAt(touch.z0 * Math.hypot(a.x - b.x, a.y - b.y) / touch.d0, wx, wy);
  } else if (cam.drag) {
    const r = cv.getBoundingClientRect(), k = (cv.width / r.width) / camScale();
    const dx = (e.clientX - cam.drag.x) * k, dy = (e.clientY - cam.drag.y) * k;
    if (Math.abs(dx) + Math.abs(dy) > 3) cam.drag.moved = true;
    cam.cx = cam.drag.cx - dx; cam.cy = cam.drag.cy - dy;
  }
});
const touchEnd = (e) => { touch.pts.delete(e.pointerId); if (touch.pts.size < 2) touch.d0 = 0; if (!touch.pts.size) setTimeout(() => (cam.drag = null), 0); };
cv.addEventListener("pointerup", touchEnd);
cv.addEventListener("pointercancel", touchEnd);
window.addEventListener("resize", resizeCanvas);

let frame = 0, WORLD = null, OBJECTS = [], ENT = {}, LEVEL = 0, SERVICES = [];
const particles = [];
const meeting = { state: "idle", q: [], title: "", tally: {}, decision: null, until: 0, parts: [] };

// ---------------------------------------------------------------- entita'
function tileCenter([tx, ty]) { return [px(tx) + 8, px(ty) + 16]; }

class Ent {
  constructor(agent, lay) {
    this.id = agent.id; this.a = agent; this.lay = lay; this.look = lookFor(agent);
    [this.x, this.y] = tileCenter(lay.seat); this.tile = lay.seat.slice(0, 2);
    this.dir = lay.seat[2]; this.sitting = true; this.q = []; this.cur = null; this.path = [];
    this.bubble = null; this.carry = null; this.busy = false; this.anim = 0;
  }
  get home() { return this.lay.seat; }
  push(...steps) { this.q.push(...steps); }
  idle() { return !this.cur && !this.q.length && !this.busy; }
  say(text, ms = 3500, tone = "") { this.bubble = { text, until: performance.now() + ms, tone }; }
  update() {
    if (!this.cur) {
      this.cur = this.q.shift() || null;
      if (!this.cur) return;
      if (this.cur.t === "walk") {
        this.sitting = false;
        this.path = astar(this.tile[0], this.tile[1], this.cur.to[0], this.cur.to[1]).slice(1);
        if (!this.path.length && (this.tile[0] !== this.cur.to[0] || this.tile[1] !== this.cur.to[1])) { [this.x, this.y] = tileCenter(this.cur.to); this.tile = this.cur.to.slice(0, 2); }
      }
      if (this.cur.t === "say") { this.say(this.cur.text, this.cur.ms, this.cur.tone); this.cur.end = performance.now() + this.cur.ms; }
      if (this.cur.t === "wait") this.cur.end = performance.now() + this.cur.ms;
      if (this.cur.t === "sit") { [this.x, this.y] = tileCenter(this.home); this.tile = this.home.slice(0, 2); this.dir = this.home[2]; this.sitting = true; this.carry = null; this.cur = null; return; }
      if (this.cur.t === "face") { this.dir = this.cur.dir; this.cur = null; return; }
      if (this.cur.t === "carry") { this.carry = this.cur.what; this.cur = null; return; }
      if (this.cur.t === "do") { this.cur.fn(this); this.cur = null; return; }
    }
    const c = this.cur;
    if (c.t === "walk") {
      if (!this.path.length) { this.cur = null; if (c.face) this.dir = c.face; return; }
      const [tx, ty] = tileCenter(this.path[0]);
      const dx = tx - this.x, dy = ty - this.y, d = Math.hypot(dx, dy), sp = 1.3;
      if (Math.abs(dx) > Math.abs(dy)) this.dir = dx > 0 ? "right" : "left"; else this.dir = dy > 0 ? "down" : "up";
      if (d <= sp) { this.x = tx; this.y = ty; this.tile = this.path.shift(); } else { this.x += dx / d * sp; this.y += dy / d * sp; }
      this.anim++;
    } else if ((c.t === "say" || c.t === "wait") && performance.now() >= c.end) this.cur = null;
  }
  draw() {
    const fr = this.cur && this.cur.t === "walk" ? 1 + (Math.floor(this.anim / 8) % 2) : 0;
    const sx = Math.round(this.x - 8), sy = Math.round(this.y - 24);
    if (this.a.kind === "code") drawRobot(ctx, sx, sy, frame + this.id.length * 7, DEPT[this.a.dept]?.[0] || "#36a2ac");
    else drawPerson(ctx, sx, sy, this.look, this.dir, fr, this.sitting);
    if (this.sitting && this.a.stato === "dorme") { ctx.font = "10px VT323"; ctx.fillStyle = "#cfd8ff"; ctx.fillText("z".repeat(1 + (frame >> 5) % 3), sx + 12, sy + 2 - ((frame >> 3) % 4)); }
    if (this.sitting && this.a.kind === "llm" && ["scrive", "pensa", "legge", "verifica"].includes(this.a.stato) && (frame >> 3) % 2) R(ctx, sx + 5, sy + 19, 6, 1, P.paper);
    if (this.carry === "cartella") { R(ctx, sx + 10, sy + 14, 7, 5, P.goldDk); R(ctx, sx + 10, sy + 14, 7, 1, P.gold); }
    if (this.carry === "scatola") { R(ctx, sx + 2, sy + 8, 12, 9, P.woodDk); R(ctx, sx + 3, sy + 9, 10, 2, P.woodLt); }
  }
}

// ---------------------------------------------------------------- costruzione della scena
function buildWorld(w) {
  WORLD = w;
  LEVEL = w.edificio.livello;
  SERVICES = w.edificio.servizi;
  OFFICE_LABEL = {};
  const objs = commonObjects(SERVICES);
  objs.push({ y: 0, draw() {}, blocks: Array.from({ length: 32 }, (_, i) => [1 + (i % 16), 35 + Math.floor(i / 16)]) });   // schermi del trading
  const seen = new Set();
  for (const o of w.uffici) {
    const a = w.agenti[o.agent_id];
    if (!a) continue;
    const lay = officeLayout(o, a);
    if (!lay) continue;
    objs.push(...lay.objects);
    if (o.tier === "privato") OFFICE_LABEL["p" + o.slot] = o.vacante ? "UFFICIO LIBERO" : (a.name + " · " + a.grade_name).toUpperCase();
    if (o.tier === "vetro") OFFICE_LABEL["g" + o.slot] = o.vacante ? "UFFICIO LIBERO" : a.name.toUpperCase() + (o.in_attesa ? " · IN ATTESA" : "");
    if (o.vacante) continue;
    seen.add(a.id);
    const e = ENT[a.id];
    if (!e) ENT[a.id] = new Ent(a, lay);
    else {
      const moved = e.lay.seat[0] !== lay.seat[0] || e.lay.seat[1] !== lay.seat[1];
      e.a = a; e.look = lookFor(a);
      if (moved) {                                       // promozione o trasloco: si porta la scatola nel nuovo ufficio
        e.lay = lay;
        e.q = []; e.cur = null;
        e.push({ t: "carry", what: "scatola" }, { t: "say", text: "Nuovo ufficio!", ms: 2200 }, { t: "walk", to: lay.seat.slice(0, 2) }, { t: "sit" });
      } else e.lay = lay;
    }
  }
  for (const id of Object.keys(ENT)) if (!seen.has(id)) delete ENT[id];
  OBJECTS = objs;
  buildWalk(objs);
}

// ---------------------------------------------------------------- comportamenti d'ambiente
const LINES = {
  avidi: ["Il mio pod batterà il Pod Zero.", "Quel bonus differito lo voglio tutto.", "L'ufficio d'angolo sarà mio.",
    "Con questo Brier mi promuovono.", "Niente trucchi: il clawback non perdona.", "Alpha netto, non lordo. Sempre.",
    "Ho visto il DSR: 0,41. Archiviata.", "Il CRO mi ha bocciato di nuovo…", "Tre mesi non bastano a dire chi è bravo.",
    "Se ho ragione in riunione, sono GC.", "Il mercato non sa che esistiamo.", "Prima i costi, poi i sogni."],
  pausa: ["Caffè?", "Doppio, grazie.", "Giornata lunga.", "Hai sentito della promozione?", "Pausa di 5 minuti.", "Torno ai numeri."],
};
const pick = (a) => a[Math.floor(Math.random() * a.length)];
function serviceSpot() {
  const h = new Date().getHours();
  const act = SERVICES.filter((s) => s.attivo && (s.id !== "mensa" || (h >= 12 && h < 14)));
  if (!act.length) return null;
  const s = act[Math.floor(Math.random() * act.length)];
  const spots = SERVICE_SPOTS[s.id].filter((sp) => !Object.values(ENT).some((e) => e.tile[0] === sp[0] && e.tile[1] === sp[1]));
  return spots.length ? { s: s.id, spot: pick(spots) } : null;
}
function ambient() {
  const people = Object.values(ENT).filter((e) => e.a.kind === "llm" && e.idle() && e.a.stato !== "dorme" && meeting.state === "idle");
  if (!people.length || WORLD?.sciopero) return;
  if (Math.random() < 0.55) {                                         // pausa ai servizi
    const e = pick(people), t = serviceSpot();
    if (!t) return;
    const mate = Object.values(ENT).find((o) => o !== e && o.cur && o.cur.service === t.s);
    e.push({ t: "walk", to: t.spot, face: "down" }, { t: "wait", ms: 800, service: t.s },
      { t: "say", text: mate ? pick(LINES.avidi) : pick(LINES.pausa), ms: 3200, service: t.s },
      { t: "wait", ms: 2500 + Math.random() * 4000, service: t.s }, { t: "walk", to: e.home.slice(0, 2) }, { t: "sit" });
    if (mate) mate.push({ t: "say", text: pick(LINES.avidi), ms: 3000 });
  } else {                                                            // il superiore chiama un subordinato
    const bosses = people.filter((b) => b.a.grade >= 5 && b.lay.visitor);
    if (!bosses.length) return;
    const b = pick(bosses);
    const subs = Object.values(ENT).filter((s) => s.a.superior === b.id && s.idle() && s.a.kind === "llm");
    if (!subs.length) return;
    const s = pick(subs);
    summon(b, s, "Vieni un attimo: aggiornami.", "Eccomi, ci sto lavorando.", false);
  }
}

function summon(boss, sub, bossLine, subLine, folder = true) {
  if (!boss || !sub || !boss.lay.visitor) return;
  boss.busy = true;
  boss.say(bossLine, 3500);
  sub.q = [];                                   // lascia quello che stava facendo e va dal capo
  sub.push({ t: "walk", to: boss.lay.visitor.slice(0, 2), face: boss.lay.visitor[2] }, { t: "do", fn: () => boss.say(bossLine, 3800) },
    { t: "wait", ms: 1200 }, { t: "say", text: subLine, ms: 3000 }, ...(folder ? [{ t: "carry", what: "cartella" }] : []),
    { t: "do", fn: () => (boss.busy = false) }, { t: "walk", to: sub.home.slice(0, 2) }, { t: "sit" });
}
function deliver(from, to, line, reply) {
  if (!from || !to || !to.lay.visitor) return;
  from.push({ t: "carry", what: "cartella" }, { t: "walk", to: to.lay.visitor.slice(0, 2), face: to.lay.visitor[2] },
    { t: "say", text: line, ms: 3400 }, { t: "do", fn: () => to.say(reply, 2800) }, { t: "wait", ms: 1500 },
    { t: "walk", to: from.home.slice(0, 2) }, { t: "sit" });
}

// ---------------------------------------------------------------- riunioni (eventi veri)
function meetingTick() {
  const now = performance.now();
  if (meeting.state === "idle" && meeting.q.length && meeting.q[0].kind === "meeting.start") {
    const ev = meeting.q.shift(), p = ev.payload;
    meeting.state = "gathering"; meeting.title = p.titolo; meeting.reason = p.motivo; meeting.tally = {}; meeting.decision = null;
    meeting.parts = (p.partecipanti || []).map((id) => ENT[id]).filter(Boolean);
    meeting.parts.forEach((e, i) => {
      const [sx, sy] = MEET_SEATS[i % MEET_SEATS.length];
      e.q = []; e.cur = null; e.busy = true;
      e.push({ t: "say", text: "In riunione!", ms: 1500 }, { t: "walk", to: [sx, sy], face: sy === 7 ? "down" : sy === 11 ? "up" : sx < 60 ? "right" : "left" });
    });
    meeting.until = now + 16000;
    return;
  }
  if (meeting.state === "idle" && meeting.q.length && meeting.q[0].kind !== "meeting.start") meeting.q.shift();
  if (meeting.state === "gathering" && (meeting.parts.every((e) => !e.cur && !e.q.length) || now > meeting.until)) { meeting.state = "talking"; meeting.until = now; }
  if (meeting.state === "talking" && now >= meeting.until && meeting.q.length) {
    const ev = meeting.q.shift(), p = ev.payload;
    if (ev.kind === "meeting.statement") {
      const e = ENT[ev.actor];
      meeting.tally[ev.actor] = p.posizione;
      if (e) e.say(`${p.fase === "replica" ? (p.cambia ? "Cambio idea: " : "Confermo: ") : ""}${p.posizione.toUpperCase()} — ${p.testo}`, 5200, p.posizione);
      meeting.until = now + 5400;
    } else if (ev.kind === "meeting.end") {
      meeting.decision = p.decisione; meeting.state = "ending"; meeting.until = now + 7000;
      for (const e of meeting.parts) if (e.a.kind === "llm") e.say(meeting.tally[e.id] === p.decisione ? "Avevo ragione." : "Vedremo chi ha ragione.", 3000);
    }
  }
  if (meeting.state === "ending" && now >= meeting.until) {
    for (const e of meeting.parts) { e.busy = false; e.push({ t: "walk", to: e.home.slice(0, 2) }, { t: "sit" }); }
    meeting.state = "idle"; meeting.parts = [];
  }
}
function drawMeetingBoard() {
  const m = ROOM.meet, x = px(m.x + 2) + 2, y = px(m.y) + 4;
  ctx.font = "9px VT323";
  ctx.fillStyle = "#1a2a52";
  if (meeting.state !== "idle") {
    const t = meeting.title, span = 26, extra = Math.max(0, t.length - span);   // titolo lungo: scorre come un tabellone
    const off = extra ? Math.min(extra, Math.max(0, (Math.floor(frame / 12) % (extra + 16)) - 8)) : 0;
    ctx.fillText(t.slice(off, off + span), x + 2, y + 5);
    const counts = {};
    Object.values(meeting.tally).forEach((v) => (counts[v] = (counts[v] || 0) + 1));
    ctx.fillStyle = meeting.decision ? P.red : "#3c70c8";
    ctx.fillText(meeting.decision ? "DECISIONE: " + meeting.decision.toUpperCase() : Object.entries(counts).map(([k, v]) => `${k}:${v}`).join("  ") || "...", x + 2, y + 11);
  } else if (WORLD?.ultima_riunione) {
    ctx.fillText("ULTIMA: " + (WORLD.ultima_riunione.decision || "").toUpperCase(), x + 2, y + 8);
  }
}

// ---------------------------------------------------------------- particelle
function burst(e, kind) {
  for (let i = 0; i < (kind === "coriandoli" ? 40 : 12); i++)
    particles.push({ x: e.x, y: e.y - 24, vx: (Math.random() - 0.5) * 2.5, vy: -1 - Math.random() * 2, life: 70 + Math.random() * 30,
      c: kind === "coriandoli" ? pick([P.gold, P.red, P.green, "#3c70c8", P.white]) : P.gold, s: kind === "coriandoli" ? 2 : 3 });
}
function drawParticles() {
  for (let i = particles.length - 1; i >= 0; i--) {
    const p = particles[i]; p.x += p.vx; p.y += p.vy; p.vy += 0.05; p.life--;
    R(ctx, p.x, p.y, p.s, p.s, p.c);
    if (p.s === 3) R(ctx, p.x + 1, p.y + 1, 1, 1, P.goldDk);
    if (p.life <= 0) particles.splice(i, 1);
  }
}

function nameTags() {
  ctx.font = "9px VT323";
  for (const e of Object.values(ENT)) {
    const n = e.a.kind === "code" ? e.a.name.replace("Automa ", "") : e.a.name.split(" ")[0];
    const w = ctx.measureText(n).width + 4;
    R(ctx, Math.round(e.x - w / 2), Math.round(e.y - 33), w, 8, "rgba(11,10,20,0.7)");
    ctx.fillStyle = e.a.kind === "code" ? P.screenBlue : P.paper; ctx.fillText(n, Math.round(e.x - w / 2) + 2, Math.round(e.y - 27));
  }
}

// ---------------------------------------------------------------- fumetti
function wrap(text, maxW) {
  const words = String(text).split(" "), lines = [];
  let cur = "";
  for (const w of words) { const t = cur ? cur + " " + w : w; if (ctx.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t; }
  if (cur) lines.push(cur);
  return lines.slice(0, 3);
}
function drawBubbles() {
  ctx.font = "11px VT323";
  const now = performance.now();
  for (const e of Object.values(ENT)) {
    const b = e.bubble;
    if (!b || now > b.until) continue;
    const lines = wrap(b.text, 150);
    const w = Math.max(...lines.map((l) => ctx.measureText(l).width)) + 10, h = lines.length * 11 + 6;
    let bx = Math.round(e.x - w / 2), by = Math.round(e.y - 30 - h);
    bx = Math.max(2, Math.min(CW - w - 2, bx)); by = Math.max(px(4) + 2, by);
    const tone = { riduci: "#f6d0c8", respingi: "#f6d0c8", mantieni: "#f3ead2", aumenta: "#d4efd8", approva: "#d4efd8" }[b.tone] || P.white;
    R(ctx, bx - 1, by - 1, w + 2, h + 2, P.line); R(ctx, bx, by, w, h, tone);
    R(ctx, Math.round(e.x) - 2, by + h, 4, 3, P.line); R(ctx, Math.round(e.x) - 1, by + h, 2, 2, tone);
    ctx.fillStyle = P.ink;
    lines.forEach((l, i) => ctx.fillText(l, bx + 5, by + 11 + i * 11));
  }
}

// ---------------------------------------------------------------- ciclo di disegno
let lastAmbient = 0;
function renderWorld(ts) {
  const stage = document.getElementById("stage");
  if (stage && stage.classList.contains("hidden")) { requestAnimationFrame(renderWorld); return; }   // pagina non visibile: non si disegna
  frame++;
  if (frame % 24 === 0) for (const L of SCREENS) { L.shift(); L.push(Math.min(0.95, Math.max(0.05, L[L.length - 1] + (Math.random() - 0.48) * 0.12))); }
  if (WORLD) {
    // 8/11, richiesta di Andrea: niente animazioni d'ambiente. Ci si muove SOLO per eventi veri (vedi onWorldEvent).
    meetingTick();
    for (const e of Object.values(ENT)) e.update();
    drawExterior(LEVEL);
    drawFloors();
    drawWalls(SERVICES, LEVEL);
    drawMeetingBoard();
    const items = OBJECTS.map((o) => ({ y: o.y, d: o.draw })).concat(Object.values(ENT).map((e) => ({ y: e.y - (e.sitting ? 1 : 0), d: () => e.draw() })));
    items.sort((a, b) => a.y - b.y);
    for (const it of items) it.d();
    drawParticles();
    const h = hourNow();
    if (h >= 20 || h < 6) { ctx.fillStyle = "rgba(10,12,40,0.10)"; ctx.fillRect(0, px(4), CW, CH - px(4)); }
    if (WORLD.sciopero) { ctx.fillStyle = "rgba(10,12,40,0.35)"; ctx.fillRect(0, px(4), CW, CH - px(4)); }
    if (cam.z >= 1.8) nameTags();
    drawBubbles();
    const v = camView();
    dctx.imageSmoothingEnabled = false;
    dctx.fillStyle = "#000"; dctx.fillRect(0, 0, cv.width, cv.height);
    dctx.drawImage(wc, v.x, v.y, v.vw, v.vh, 0, 0, cv.width, cv.height);
  }
  requestAnimationFrame(renderWorld);
}

// ---------------------------------------------------------------- eventi veri dal backend
function onWorldEvent(ev) {
  const p = ev.payload || {}, E = (id) => ENT[id];
  switch (ev.kind) {
    case "task.handoff": summon(E(p.da), E(p.a), "Ti affido: " + (p.titolo || "un compito"), "Ricevuto, me ne occupo."); break;
    case "task.done": if (p.a && p.a !== "andrea") deliver(E(ev.actor), E(p.a), p.stato === "fatto" ? "Fatto, ecco il fascicolo." : "Servono dati: ecco cosa manca.", p.stato === "fatto" ? "Ottimo lavoro." : "Capito, procuriamoli."); break;
    case "meeting.start": case "meeting.statement": case "meeting.end": meeting.q.push(ev); break;
    case "career.promozione": { const e = E(p.agente); if (e) { burst(e, "coriandoli"); e.say("Promosso a " + p.a + "!", 4500); } break; }
    case "career.retrocessione": { const e = E(p.agente); if (e) e.say("Retrocesso… post-mortem.", 4000); break; }
    case "career.clawback": { const e = E(p.agente); if (e) e.say(`Clawback: -${p.gc} GC differiti.`, 4500); break; }
    case "gc.bonus": { const e = E(p.agente); if (e) { burst(e, "monete"); e.say(`+${p.gc} GC (maturano il ${p.matura})`, 3500); } break; }
    case "gateway.rejected": { const e = Object.values(ENT).find((x) => x.id === p.agente); if (e) e.say("Respinto dal Gateway: " + (p.motivi || [""])[0].slice(0, 50), 4000); break; }
    case "risk.alert": { const e = E("cro"); if (e) e.say("Allarme: " + (p.cosa || "").slice(0, 70), 4500); break; }
    case "risk.kill": Object.values(ENT).forEach((e) => e.say("KILL!", 3000)); break;
    case "mailbox.new": { const e = E("capo"); if (e) e.say("Scrivo ad Andrea: " + (p.title || "").slice(0, 50), 4000); break; }
    case "news.bulletin": { const e = E("head_intel"); if (e) e.say("Bollettino pronto per i desk.", 3500); break; }
    case "postmortem": { const e = E(p.agente); if (e) e.say("Lezione: " + (p.lezione || "").slice(0, 60), 4500); break; }
    case "agent.status": { const e = E(ev.actor); if (e) { e.a.stato = p.stato; if (["pensa", "cerca", "valuta", "trada", "rivede", "legge", "controlla"].includes(p.stato) && p.compito) e.say("(" + p.stato + ") " + String(p.compito).slice(0, 70), 3500); } break; }
    case "idea.new": if (p.a && p.a !== ev.actor) deliver(E(ev.actor), E(p.a), "Ho un'idea: " + String(p.titolo || "").slice(0, 60), "Vediamola con i dati."); else { const e = E(ev.actor); if (e) e.say("Idea: " + String(p.titolo || "").slice(0, 60), 4000); } break;
    case "idea.review": { const e = E(ev.actor); if (e) e.say("Idea #" + p.id + ": " + (({ porta_su: "la porto su", scarta: "scartata", rimanda: "da rifare" })[p.decisione] || p.decisione), 4000); break; }
    case "idea.entered": { const e = E(ev.actor); if (e) { burst(e, "monete"); e.say("La mia idea entra nel conto: " + p.simbolo + " " + p.peso_pct + "%", 4500); } break; }
    case "idea.closed": { const e = E(ev.actor); if (e) e.say("Idea #" + p.id + " chiusa (" + p.motivo + "): alpha " + (p.alpha * 100).toFixed(1) + "%", 4500); break; }
    case "free.trade": { const e = E(ev.actor); if (e) e.say("Apro " + p.lato + " " + p.simbolo + " " + Math.round(p.usd) + " $" + (p.minuti ? " per " + p.minuti + " min" : ""), 4000); break; }
    case "free.closed": { const e = E(ev.actor); if (e) { if (p.pnl > 0) burst(e, "monete"); e.say("Chiuso " + p.simbolo + " (" + p.motivo + "): " + (p.pnl >= 0 ? "+" : "") + Number(p.pnl).toFixed(2) + " $", 4000); } break; }
    case "signal.decided": { const e = E("senior_crypto"); if (e) e.say("Segnale #" + p.id + " " + (p.moneta || "") + ": " + p.stato, 4000); break; }
    case "rule.applied": case "house_rule": { const e = E("capo"); if (e) e.say("Nuova regola: " + (p.chiave || p.tipo) + " = " + (p.nuovo != null ? p.nuovo : p.valore), 4500); break; }
    case "desk.overlay": { const e = E("pod_trend"); if (e) e.say("Desk: " + p.titoli + " titoli proposti per il conto", 3500); break; }
    case "free.riesame": { const e = E("capo"); if (e) e.say("Riesame: abbiamo perso oggi, parliamone.", 4500); break; }
  }
}
