// GERVA Capital — grafica originale generata da codice: palette, persone, robot, arredi, insegna.
"use strict";

const T = 16; // lato della tessera in pixel
const P = {
  ink: "#0b0a14", line: "#1a1626", night: "#141225", shadow: "rgba(0,0,0,0.28)",
  wallTop: "#5b5578", wallFace: "#4a4566", wallFaceDk: "#3a3552", wallTrim: "#2c2840",
  corridor: ["#3b3a4a", "#413f52"], corridorLine: "#4a485c",
  parquet: ["#9a6a44", "#8c5f3c", "#a5734a"], carpetCEO: ["#5e1f2e", "#68243a"], carpetMgr: ["#2f3f62", "#34466c"],
  carpetGlass: ["#3d4a3a", "#435140"], tileOpen: ["#c9c6bd", "#bdb9af"], tileOps: ["#263038", "#2b3640"],
  tileTrading: ["#1b2236", "#20283e"], tileMeeting: ["#4a3b32", "#523f35"], tileService: ["#cdbb9a", "#c2b08e"],
  wood: "#8a5a36", woodLt: "#b07a4c", woodDk: "#5a3a22", mahog: "#5c2418", mahogLt: "#7e3424", gold: "#e3b24a",
  goldDk: "#a87a26", glass: "rgba(170,210,235,0.35)", glassEdge: "#9fc6dc", metal: "#8a93a6", metalDk: "#565e70",
  screen: "#0e2a1c", screenGlow: "#47d17a", screenBlue: "#3fa7e0", paper: "#f3ead2", white: "#f6f6f2", red: "#d8473a",
  green: "#4fb06a", amber: "#efa52f", leaf: "#3f9a4f", leafDk: "#2a6e38", leafLt: "#6cc070", pot: "#b5603a", potDk: "#7a3e24",
  leather: "#3a2418", leatherLt: "#5a3828", sofa: "#3f5a8a", sofaLt: "#5574aa", sofaCEO: "#6a2030", sofaCEOLt: "#8a3040",
};

const DEPT = {
  direzione: ["#b8332a", "#7a1f18"], rischio: ["#d99a2b", "#8a5c12"], ricerca: ["#3d9e5c", "#22603a"],
  validazione: ["#8a5cc0", "#563880"], redazione: ["#3c70c8", "#244a8a"], dati: ["#36a2ac", "#1f646c"],
  talent: ["#c27a3e", "#7a4820"], pod: ["#d9d9e2", "#8e8ea0"], lungo: ["#2e6f73", "#1b4447"],
};
const HAIR = ["#2a1a10", "#4a2c16", "#8a5a2a", "#caa25a", "#151515", "#7a2a18", "#b9b9c2", "#3a2a52", "#d8c88a"];
const SKIN = [["#f1c9a2", "#d9a87e"], ["#dcae80", "#c08e62"], ["#b47a52", "#94603c"], ["#8a5a3a", "#6c4228"], ["#f7dcc4", "#e2bea0"]];

function hashStr(s) { let h = 2166136261; for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }
function R(ctx, x, y, w, h, c) { ctx.fillStyle = c; ctx.fillRect(Math.round(x), Math.round(y), w, h); }

// ---------------------------------------------------------------- persone (16x24)
function lookFor(agent) {
  const h = hashStr(agent.id);
  const grade = agent.grade ?? 1;
  const ceo = agent.id === "capo";
  const [c1, c2] = DEPT[agent.dept] || ["#888", "#555"];
  return {
    skin: SKIN[(h >>> 4) % SKIN.length], hair: HAIR[h % HAIR.length], style: (h >>> 9) % 5, glasses: (h >>> 13) % 4 === 0,
    shirt: grade >= 5 || ceo ? "#e8e6e0" : c1, shirtDk: grade >= 5 || ceo ? "#bdbab2" : c2,
    jacket: ceo ? "#1c1c2a" : grade >= 6 ? "#2a2a3e" : grade >= 5 ? c2 : null,
    tie: ceo ? P.gold : grade >= 5 ? c1 : null, lanyard: grade <= 1, vest: grade === 4 ? c2 : null,
    pants: ceo || grade >= 5 ? "#1e1e2c" : ["#2c3448", "#3a2c22", "#26303a"][(h >>> 17) % 3],
    shoes: ceo ? "#0a0a0a" : "#1a1410", ceo,
  };
}

function drawPerson(ctx, x, y, L, dir = "down", frame = 0, sitting = false) {
  // (x, y) = angolo in alto a sinistra della cella 16x24
  const o = P.line;
  const sk = L.skin[0], skd = L.skin[1];
  const legY = sitting ? 0 : (frame === 1 ? 1 : frame === 2 ? -1 : 0);
  // ombra
  ctx.fillStyle = P.shadow; ctx.beginPath(); ctx.ellipse(x + 8, y + 23, 6, 2, 0, 0, Math.PI * 2); ctx.fill();
  // gambe e scarpe
  if (!sitting) {
    const l1 = frame === 1 ? -1 : frame === 2 ? 1 : 0;
    R(ctx, x + 5, y + 17, 3, 5 + l1, o); R(ctx, x + 8, y + 17, 3, 5 - l1, o);
    R(ctx, x + 5, y + 17, 2, 4 + l1, L.pants); R(ctx, x + 9, y + 17, 2, 4 - l1, L.pants);
    R(ctx, x + 4, y + 21 + l1, 4, 2, L.shoes); R(ctx, x + 8, y + 21 - l1, 4, 2, L.shoes);
  }
  const by = sitting ? 3 : 0; // da seduti il busto scende
  // busto
  const top = L.jacket || L.shirt;
  R(ctx, x + 3, y + 10 + by, 10, 8, o);
  R(ctx, x + 4, y + 10 + by, 8, 7, top);
  R(ctx, x + 4, y + 16 + by, 8, 1, L.jacket ? "#111" : L.shirtDk);
  if (dir === "down") {
    if (L.jacket) { R(ctx, x + 6, y + 10 + by, 4, 6, L.shirt); }
    if (L.vest) { R(ctx, x + 5, y + 11 + by, 6, 5, L.vest); R(ctx, x + 7, y + 11 + by, 2, 5, L.shirt); }
    if (L.tie) { R(ctx, x + 7, y + 11 + by, 2, 1, L.tie); R(ctx, x + 7, y + 12 + by, 2, 4, L.tie); }
    if (L.lanyard) { R(ctx, x + 6, y + 10 + by, 1, 4, "#e0e0e0"); R(ctx, x + 9, y + 10 + by, 1, 4, "#e0e0e0"); R(ctx, x + 6, y + 14 + by, 4, 2, P.white); }
    if (L.ceo) { R(ctx, x + 4, y + 11 + by, 1, 1, P.gold); }
  }
  // braccia
  const sw = sitting ? 0 : (frame === 1 ? 1 : frame === 2 ? -1 : 0);
  if (dir === "left" || dir === "right") {
    const ax = dir === "left" ? x + 6 : x + 8;
    R(ctx, ax, y + 11 + by + sw, 2, 6, o); R(ctx, ax, y + 11 + by + sw, 2, 5, top); R(ctx, ax, y + 16 + by + sw, 2, 1, sk);
  } else {
    R(ctx, x + 2, y + 11 + by + sw, 2, 6, o); R(ctx, x + 12, y + 11 + by - sw, 2, 6, o);
    R(ctx, x + 2, y + 11 + by + sw, 2, 5, top); R(ctx, x + 12, y + 11 + by - sw, 2, 5, top);
    R(ctx, x + 2, y + 16 + by + sw, 2, 1, sk); R(ctx, x + 12, y + 16 + by - sw, 2, 1, sk);
  }
  // testa
  const hx = x + 4, hy = y + 2 + by;
  R(ctx, hx - 1, hy, 10, 9, o);
  R(ctx, hx, hy + 1, 8, 7, sk);
  R(ctx, hx, hy + 7, 8, 1, skd);
  // capelli
  const hc = L.hair;
  if (dir === "up") {
    R(ctx, hx, hy, 8, 7, hc);
    if (L.style === 1) R(ctx, hx - 1, hy + 4, 10, 5, hc);
  } else {
    R(ctx, hx, hy, 8, 2, hc);
    if (L.style === 0) { R(ctx, hx, hy + 2, 1, 2, hc); R(ctx, hx + 7, hy + 2, 1, 2, hc); }
    if (L.style === 1) { R(ctx, hx - 1, hy + 1, 2, 7, hc); R(ctx, hx + 7, hy + 1, 2, 7, hc); }          // lunghi
    if (L.style === 2) { R(ctx, hx + 2, hy - 2, 4, 2, hc); R(ctx, hx, hy + 2, 2, 1, hc); }                 // chignon
    if (L.style === 3) { R(ctx, hx, hy, 8, 1, hc); }                                                       // rasati
    if (L.style === 4) { R(ctx, hx - 1, hy, 10, 3, hc); R(ctx, hx + 1, hy + 3, 1, 1, hc); R(ctx, hx + 6, hy + 3, 1, 1, hc); } // ricci
    if (dir === "down") {
      R(ctx, hx + 2, hy + 4, 1, 2, P.ink); R(ctx, hx + 5, hy + 4, 1, 2, P.ink);
      R(ctx, hx + 3, hy + 6, 2, 1, "#a0504a");
      if (L.glasses) { R(ctx, hx + 1, hy + 4, 3, 1, "#222"); R(ctx, hx + 4, hy + 4, 3, 1, "#222"); }
    } else {
      const ex = dir === "left" ? hx + 1 : hx + 6;
      R(ctx, ex, hy + 4, 1, 2, P.ink);
      R(ctx, dir === "left" ? hx + 5 : hx, hy + 1, 3, 5, hc);
    }
  }
}

// ---------------------------------------------------------------- robot (automi: codice deterministico)
function drawRobot(ctx, x, y, t, color = "#36a2ac") {
  const o = P.line, bob = Math.floor(t / 20) % 2;
  ctx.fillStyle = P.shadow; ctx.beginPath(); ctx.ellipse(x + 8, y + 23, 6, 2, 0, 0, Math.PI * 2); ctx.fill();
  R(ctx, x + 7, y + 1 + bob, 2, 3, P.metalDk); R(ctx, x + 6, y + bob, 4, 2, Math.floor(t / 30) % 2 ? P.green : "#2a6e3a");
  R(ctx, x + 2, y + 4 + bob, 12, 9, o); R(ctx, x + 3, y + 5 + bob, 10, 7, P.metal);
  R(ctx, x + 4, y + 6 + bob, 8, 5, "#102028");
  R(ctx, x + 5, y + 8 + bob, 2, 2, color); R(ctx, x + 9, y + 8 + bob, 2, 2, color);
  R(ctx, x + 3, y + 13, 10, 7, o); R(ctx, x + 4, y + 14, 8, 5, P.metalDk); R(ctx, x + 5, y + 15, 6, 2, color);
  R(ctx, x + 4, y + 20, 3, 3, o); R(ctx, x + 9, y + 20, 3, 3, o);
}

// ---------------------------------------------------------------- arredi (coordinate in pixel)
function plant(ctx, x, y, size = 1, lux = false) {
  const w = 6 + size * 3, h = 6 + size * 4;
  R(ctx, x - w / 2, y - 6, w, 6, lux ? P.gold : P.pot); R(ctx, x - w / 2, y - 6, w, 1, lux ? "#f6d27a" : "#d07a4a"); R(ctx, x - w / 2, y - 1, w, 1, lux ? P.goldDk : P.potDk);
  const leaves = [[0, -h], [-w / 2, -h + 3], [w / 2 - 2, -h + 3], [-w / 3, -h - 2], [w / 4, -h - 1], [-2, -h + 5]];
  for (const [dx, dy] of leaves) { R(ctx, x + dx - 2, y - 6 + dy, 5, 5, P.leafDk); R(ctx, x + dx - 1, y - 6 + dy, 3, 3, P.leaf); R(ctx, x + dx, y - 6 + dy, 1, 1, P.leafLt); }
  R(ctx, x - 1, y - 8, 2, 3, P.leafDk);
}
function rug(ctx, x, y, w, h, c1, c2, border = P.gold) {
  R(ctx, x, y, w, h, border); R(ctx, x + 2, y + 2, w - 4, h - 4, c1);
  for (let i = 6; i < w - 6; i += 8) R(ctx, x + i, y + 4, 3, h - 8, c2);
}
function desk(ctx, x, y, w, kind) {
  const top = { base: "#d2bf98", legno: P.woodLt, grande: P.wood, exec: P.mahogLt }[kind] || P.woodLt;
  const side = { base: "#a8946c", legno: P.wood, grande: P.woodDk, exec: P.mahog }[kind] || P.wood;
  R(ctx, x, y, w, 13, P.line); R(ctx, x + 1, y + 1, w - 2, 7, top); R(ctx, x + 1, y + 8, w - 2, 4, side);
  R(ctx, x + 1, y + 1, w - 2, 1, "rgba(255,255,255,0.28)");
  for (let i = x + 6; i < x + w - 6; i += 14) R(ctx, i, y + 9, 4, 1, kind === "exec" ? P.gold : "rgba(0,0,0,0.35)");
  if (kind === "exec") { R(ctx, x + 1, y + 8, w - 2, 1, P.gold); R(ctx, x + w / 2 - 9, y + 2, 18, 5, "#2e5a38"); R(ctx, x + 4, y - 5, 5, 4, P.gold); R(ctx, x + 6, y - 1, 1, 2, P.goldDk); R(ctx, x + w - 14, y + 2, 9, 3, P.gold); }
  if (kind === "grande") { R(ctx, x + w / 2 - 6, y + 2, 12, 4, "#2c4a3a"); }
  if (kind !== "exec") { mug(ctx, x + w - 9, y + 2); papers(ctx, x + 3, y + 2); }
}
function monitor(ctx, x, y, t, back = true, color = P.screenGlow) {
  R(ctx, x, y, 10, 7, P.line); R(ctx, x + 1, y + 1, 8, 5, back ? "#2a2a36" : P.screen);
  if (!back) { for (let i = 0; i < 6; i++) R(ctx, x + 2 + i, y + 2 + ((i * 7 + Math.floor(t / 8)) % 3), 1, 1, color); }
  else if (Math.floor(t / 25) % 2) R(ctx, x + 1, y + 6, 8, 1, color);
  R(ctx, x + 4, y + 7, 2, 2, P.metalDk);
}
function chair(ctx, x, y, kind) {
  const c = { base: "#4a4a58", ergo: "#22262e", poltrona: P.leather, pelle: "#2a1610", ospite: "#5a4a40" }[kind] || "#444";
  const hi = { base: "#62627a", ergo: "#3e4652", poltrona: P.leatherLt, pelle: "#4e2c1c", ospite: "#7e6a5a" }[kind] || "#666";
  const tall = kind === "pelle" || kind === "poltrona" ? 3 : 0;
  // schienale arrotondato (visto da dietro/sopra), seduta e base
  R(ctx, x + 3, y, 10, 9 + tall, P.line); R(ctx, x + 2, y + 1, 12, 7 + tall, P.line);
  R(ctx, x + 3, y + 1, 10, 7 + tall, c); R(ctx, x + 4, y + 2, 8, 2, hi); R(ctx, x + 4, y + 7 + tall, 8, 1, "rgba(0,0,0,0.3)");
  if (kind === "pelle") { for (const [dx, dy] of [[5, 5], [8, 5], [11, 5], [6, 8], [10, 8]]) R(ctx, x + dx - 1, y + dy, 1, 1, P.gold); R(ctx, x + 3, y + 1, 10, 1, P.goldDk); }
  if (kind === "ergo" || kind === "base") { R(ctx, x + 7, y + 9 + tall, 2, 2, P.metalDk); }
}
function floorLamp(ctx, x, y) { R(ctx, x + 2, y + 1, 9, 5, P.line); R(ctx, x + 3, y + 1, 7, 4, "#f4d68a"); R(ctx, x + 6, y + 6, 1, 14, P.metalDk); R(ctx, x + 3, y + 19, 7, 2, P.metalDk); ctx.fillStyle = "rgba(244,214,138,0.10)"; ctx.beginPath(); ctx.arc(x + 6, y + 10, 16, 0, 7); ctx.fill(); }
function cabinet(ctx, x, y) { R(ctx, x, y, 14, 18, P.line); R(ctx, x + 1, y + 1, 12, 16, "#7a8090"); R(ctx, x + 1, y + 6, 12, 1, P.line); R(ctx, x + 1, y + 11, 12, 1, P.line); for (const yy of [3, 8, 13]) R(ctx, x + 5, y + yy, 4, 1, "#c8ccd6"); }
function coatRack(ctx, x, y) { R(ctx, x + 6, y, 2, 20, P.woodDk); R(ctx, x + 2, y + 1, 10, 2, P.woodDk); R(ctx, x + 1, y + 3, 4, 7, "#3a4a6a"); R(ctx, x + 3, y + 19, 8, 2, P.woodDk); }
function armchair(ctx, x, y, c = P.sofa, cl = P.sofaLt) { R(ctx, x, y, 16, 14, P.line); R(ctx, x + 1, y + 1, 14, 5, cl); R(ctx, x + 1, y + 6, 14, 7, c); R(ctx, x + 1, y + 6, 3, 7, cl); R(ctx, x + 12, y + 6, 3, 7, cl); }
function roundTable(ctx, x, y, c = P.woodLt) { ctx.fillStyle = P.line; ctx.beginPath(); ctx.ellipse(x + 8, y + 7, 9, 6, 0, 0, 7); ctx.fill(); ctx.fillStyle = c; ctx.beginPath(); ctx.ellipse(x + 8, y + 6, 8, 5, 0, 0, 7); ctx.fill(); R(ctx, x + 5, y + 4, 4, 1, "rgba(255,255,255,0.3)"); }
function stool(ctx, x, y) { R(ctx, x + 4, y, 8, 4, P.line); R(ctx, x + 5, y + 1, 6, 2, P.red); R(ctx, x + 7, y + 4, 2, 6, P.metalDk); R(ctx, x + 5, y + 9, 6, 1, P.metalDk); }
function pastries(ctx, x, y) { R(ctx, x, y, 30, 12, P.line); R(ctx, x + 1, y + 1, 28, 9, "rgba(200,230,250,0.6)"); for (let i = 0; i < 5; i++) R(ctx, x + 3 + i * 5, y + 5, 4, 3, ["#c88a4a", "#e8c07a", "#a85a3a", "#f0d0a0", "#7a4a2a"][i]); }
function tv(ctx, x, y, t) { R(ctx, x, y, 34, 14, P.line); R(ctx, x + 1, y + 1, 32, 11, "#0e1a2e"); for (let i = 0; i < 28; i++) R(ctx, x + 3 + i, y + 3 + Math.round(4 + 3 * Math.sin((i + t / 6) / 3)), 1, 1, P.screenBlue); }
function mirror(ctx, x, y, w) { R(ctx, x, y, w, 12, P.metalDk); R(ctx, x + 1, y + 1, w - 2, 10, "#bcd8e8"); R(ctx, x + 4, y + 2, 3, 8, "rgba(255,255,255,0.6)"); }
function mat(ctx, x, y, w, h, c = "#2a5a8a") { R(ctx, x, y, w, h, P.line); R(ctx, x + 1, y + 1, w - 2, h - 2, c); }
function bench(ctx, x, y) { R(ctx, x, y + 5, 26, 5, P.line); R(ctx, x + 1, y + 6, 24, 3, "#2a2a30"); R(ctx, x + 2, y, 2, 6, P.metal); R(ctx, x + 22, y, 2, 6, P.metal); R(ctx, x - 2, y, 30, 2, P.metal); R(ctx, x - 4, y - 2, 4, 6, P.line); R(ctx, x + 26, y - 2, 4, 6, P.line); }
function mug(ctx, x, y) { R(ctx, x, y, 4, 4, P.white); R(ctx, x + 4, y + 1, 1, 2, P.white); R(ctx, x + 1, y, 2, 1, "#6a3a1a"); }
function papers(ctx, x, y) { R(ctx, x, y, 7, 5, P.paper); R(ctx, x + 1, y + 1, 5, 1, "#b8b0a0"); R(ctx, x + 1, y + 3, 4, 1, "#b8b0a0"); }
function sofa(ctx, x, y, w, c, cl) {
  R(ctx, x, y, w, 14, P.line); R(ctx, x + 1, y + 1, w - 2, 5, cl); R(ctx, x + 1, y + 6, w - 2, 7, c);
  R(ctx, x + 1, y + 6, 3, 7, cl); R(ctx, x + w - 4, y + 6, 3, 7, cl);
}
function shelf(ctx, x, y, w, h) {
  R(ctx, x, y, w, h, P.line); R(ctx, x + 1, y + 1, w - 2, h - 2, P.woodDk);
  const cols = ["#b8332a", "#3c70c8", "#e3b24a", "#3d9e5c", "#8a5cc0", "#e8e6e0"];
  for (let r = 0; r < Math.floor((h - 2) / 7); r++) {
    R(ctx, x + 1, y + 7 + r * 7, w - 2, 1, P.wood);
    for (let b = 0; b < (w - 4) / 3; b++) R(ctx, x + 2 + b * 3, y + 2 + r * 7, 2, 5, cols[(b + r * 3) % cols.length]);
  }
}
function art(ctx, x, y, w, h, seed, gold = false) {
  R(ctx, x - 1, y - 1, w + 2, h + 2, gold ? P.gold : P.woodDk); R(ctx, x, y, w, h, "#e8dcc0");
  const cols = ["#3c70c8", "#d8473a", "#e3b24a", "#3d9e5c", "#2a2a3a"];
  for (let i = 0; i < 6; i++) R(ctx, x + 1 + ((seed * (i + 3)) % (w - 4)), y + 1 + ((seed * (i + 7)) % (h - 4)), 3, 3, cols[(seed + i) % cols.length]);
}
function globe(ctx, x, y) { R(ctx, x + 3, y + 12, 6, 2, P.woodDk); R(ctx, x + 5, y + 9, 2, 4, P.gold); ctx.fillStyle = "#3c70c8"; ctx.beginPath(); ctx.arc(x + 6, y + 6, 5, 0, 7); ctx.fill(); R(ctx, x + 3, y + 4, 3, 2, P.leaf); R(ctx, x + 7, y + 7, 2, 2, P.leaf); }
function bar(ctx, x, y) { R(ctx, x, y, 22, 14, P.line); R(ctx, x + 1, y + 1, 20, 12, P.mahog); R(ctx, x + 1, y + 1, 20, 1, P.gold); const b = ["#7a2a18", "#d8c070", "#2a5a2a", "#b8b8c8"]; for (let i = 0; i < 5; i++) R(ctx, x + 3 + i * 4, y - 6, 2, 7, b[i % 4]); }
function trophy(ctx, x, y) { R(ctx, x + 2, y + 8, 6, 2, P.goldDk); R(ctx, x + 4, y + 5, 2, 3, P.gold); R(ctx, x + 1, y, 8, 5, P.gold); R(ctx, x + 2, y + 1, 2, 2, "#fff2b0"); }
function aquarium(ctx, x, y, t) { R(ctx, x, y, 26, 14, P.line); R(ctx, x + 1, y + 1, 24, 10, "#2f7fb0"); R(ctx, x + 1, y + 11, 24, 2, P.woodDk); const fx = (t / 3) % 22; R(ctx, x + 2 + fx, y + 4, 3, 2, P.amber); R(ctx, x + 22 - ((t / 4) % 20), y + 7, 3, 2, P.red); R(ctx, x + 4, y + 8, 2, 3, P.leaf); }
function lamp(ctx, x, y, on = true) { R(ctx, x + 3, y + 4, 2, 9, P.metalDk); R(ctx, x, y, 8, 5, on ? "#f4d68a" : "#9a8a60"); R(ctx, x + 1, y + 12, 6, 2, P.metalDk); }
function rack(ctx, x, y, t) {
  R(ctx, x, y, 14, 30, P.line); R(ctx, x + 1, y + 1, 12, 28, "#252a34");
  for (let i = 0; i < 6; i++) { R(ctx, x + 2, y + 3 + i * 4, 10, 2, "#353c48"); R(ctx, x + 10, y + 3 + i * 4, 1, 1, (Math.floor(t / 7) + i * 3) % 5 ? P.green : P.amber); }
}
function coffeeMachine(ctx, x, y, t) { R(ctx, x, y, 14, 18, P.line); R(ctx, x + 1, y + 1, 12, 16, "#3a3a44"); R(ctx, x + 3, y + 3, 8, 4, "#101018"); R(ctx, x + 4, y + 4, 2, 1, P.red); R(ctx, x + 5, y + 11, 4, 4, P.white); if (Math.floor(t / 20) % 3 === 0) R(ctx, x + 6, y + 8, 2, 2, "rgba(255,255,255,0.6)"); }
function waterCooler(ctx, x, y) { R(ctx, x + 2, y, 8, 8, "#7ac0e8"); R(ctx, x + 3, y + 1, 3, 3, "#bfe6fa"); R(ctx, x, y + 8, 12, 12, P.line); R(ctx, x + 1, y + 9, 10, 10, "#dedede"); }
function ftable(ctx, x, y, w, h, c = P.wood) { R(ctx, x, y, w, h, P.line); R(ctx, x + 1, y + 1, w - 2, h - 3, c); R(ctx, x + 1, y + 1, w - 2, 1, "rgba(255,255,255,0.25)"); }
function treadmill(ctx, x, y) { R(ctx, x, y + 6, 26, 10, P.line); R(ctx, x + 1, y + 7, 24, 7, "#2a2a30"); R(ctx, x + 2, y, 3, 8, P.metal); R(ctx, x + 1, y - 2, 8, 3, P.metalDk); }
function weights(ctx, x, y) { R(ctx, x, y + 4, 22, 2, P.metal); R(ctx, x - 1, y, 4, 10, P.line); R(ctx, x + 19, y, 4, 10, P.line); }
function arcade(ctx, x, y, t) { R(ctx, x, y, 16, 26, P.line); R(ctx, x + 1, y + 1, 14, 24, "#5a2a8a"); R(ctx, x + 3, y + 4, 10, 8, "#0a0a20"); R(ctx, x + 4 + (Math.floor(t / 10) % 7), y + 7, 2, 2, P.amber); R(ctx, x + 4, y + 15, 2, 2, P.red); R(ctx, x + 9, y + 15, 2, 2, P.green); }
function pingpong(ctx, x, y) { R(ctx, x, y, 34, 18, P.line); R(ctx, x + 1, y + 1, 32, 15, "#2a6a4a"); R(ctx, x + 16, y + 1, 1, 15, P.white); R(ctx, x + 1, y + 8, 32, 1, P.white); }
function whiteboard(ctx, x, y, w, h) { R(ctx, x, y, w, h, P.metalDk); R(ctx, x + 1, y + 1, w - 2, h - 2, "#f4f4ee"); }
function tradingWall(ctx, x, y, w, t, series) {
  R(ctx, x, y, w, 26, P.line);
  const n = Math.floor((w - 2) / 30);
  for (let s = 0; s < n; s++) {
    const sx = x + 2 + s * 30; R(ctx, sx, y + 2, 28, 22, "#08140e");
    const L = series[s % series.length];
    for (let i = 1; i < L.length && i < 26; i++) R(ctx, sx + 1 + i, y + 3 + Math.round(18 * (1 - L[i])), 1, 1, i % 3 ? P.screenGlow : "#a8f0c0");
  }
}

// ---------------------------------------------------------------- insegna: font pixel 5x7 e stemma
const FONT5 = {
  A: ["01110", "10001", "10001", "11111", "10001", "10001", "10001"], C: ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
  E: ["11111", "10000", "10000", "11110", "10000", "10000", "11111"], G: ["01111", "10000", "10000", "10111", "10001", "10001", "01111"],
  I: ["11111", "00100", "00100", "00100", "00100", "00100", "11111"], L: ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
  P: ["11110", "10001", "10001", "11110", "10000", "10000", "10000"], R: ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
  T: ["11111", "00100", "00100", "00100", "00100", "00100", "00100"], V: ["10001", "10001", "10001", "10001", "01010", "01010", "00100"],
  " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
};
function pixelText(ctx, s, x, y, scale, color, shadow = P.ink) {
  let cx = x;
  for (const ch of s) {
    const g = FONT5[ch] || FONT5[" "];
    for (let r = 0; r < 7; r++) for (let c = 0; c < 5; c++) if (g[r][c] === "1") {
      if (shadow) R(ctx, cx + c * scale + scale, y + r * scale + scale, scale, scale, shadow);
      R(ctx, cx + c * scale, y + r * scale, scale, scale, color);
    }
    cx += 6 * scale;
  }
  return cx - x;
}
function textWidth5(s, scale) { return s.length * 6 * scale - scale; }

// stemma: scudo con la G e tre barre in salita
function emblem(ctx, x, y, s = 1, glow = false) {
  const shield = ["0011111111100", "0111111111110", "1111111111111", "1111111111111", "1111111111111", "1111111111111",
    "1111111111111", "0111111111110", "0111111111110", "0011111111100", "0001111111000", "0000111110000", "0000011100000"];
  for (let r = 0; r < shield.length; r++) for (let c = 0; c < 13; c++) if (shield[r][c] === "1") {
    const edge = r === 0 || c === 0 || c === 12 || shield[r][c - 1] === "0" || shield[r][c + 1] === "0" || !shield[r + 1] || shield[r + 1][c] === "0";
    R(ctx, x + c * s, y + r * s, s, s, edge ? P.gold : "#1a2a52");
  }
  const g = ["01110", "10000", "10110", "10010", "01110"];
  for (let r = 0; r < 5; r++) for (let c = 0; c < 5; c++) if (g[r][c] === "1") R(ctx, x + (2 + c) * s, y + (2 + r) * s, s, s, P.gold);
  R(ctx, x + 8 * s, y + 6 * s, s, s, P.green); R(ctx, x + 9 * s, y + 5 * s, s, 2 * s, P.green); R(ctx, x + 10 * s, y + 3 * s, s, 4 * s, P.green);
  if (glow) { ctx.fillStyle = "rgba(227,178,74,0.18)"; ctx.fillRect(x - 3 * s, y - 3 * s, 19 * s, 19 * s); }
}
