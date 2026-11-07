// GERVA Capital — la pianta: stanze, uffici per grado, servizi, insegna, percorsi (A*).
"use strict";

const GW = 72, GH = 45, CW = GW * T, CH = GH * T;

const ROOMS = [
  { id: "ceo", kind: "ceo", x: 0, y: 4, w: 18, h: 12, name: "SUITE DEL CAPO", doors: [[9, 15]], ext: true },
  ...[0, 1, 2, 3].map((i) => ({ id: "p" + i, kind: "privato", x: 18 + i * 9, y: 4, w: 9, h: 12, name: "UFFICIO", doors: [[22 + i * 9, 15]], ext: true })),
  { id: "meet", kind: "meeting", x: 54, y: 4, w: 18, h: 12, name: "SALA RIUNIONI", doors: [[62, 15]], ext: true },
  ...[0, 1, 2].map((i) => ({ id: "g" + i, kind: "vetro", x: i * 12, y: 19, w: 12, h: 6, name: "UFFICIO", doors: [[6 + i * 12, 19]] })),
  ...[0, 1, 2].map((i) => ({ id: "g" + (i + 3), kind: "vetro", x: i * 12, y: 25, w: 12, h: 6, name: "UFFICIO", doors: [[6 + i * 12, 30]] })),
  { id: "open", kind: "open", x: 36, y: 19, w: 22, h: 12, name: "OPEN SPACE", doors: [[46, 19], [47, 19], [46, 30], [47, 30]] },
  { id: "ops", kind: "ops", x: 58, y: 19, w: 14, h: 12, name: "SALA OPERATIVA (AUTOMI)", doors: [[64, 19]] },
  { id: "trading", kind: "trading", x: 0, y: 34, w: 18, h: 11, name: "TRADING FLOOR", doors: [[9, 34]] },
  ...["caffe", "lounge", "mensa", "palestra", "biblioteca", "terrazza"].map((s, i) => ({ id: s, kind: "service", service: s, x: 18 + i * 9, y: 34, w: 9, h: 11, name: s.toUpperCase(), doors: [[22 + i * 9, 34]] })),
];
const ROOM = Object.fromEntries(ROOMS.map((r) => [r.id, r]));
const SERVICE_NAMES = { caffe: "CAFFÈ", lounge: "LOUNGE", mensa: "MENSA", palestra: "PALESTRA", biblioteca: "BIBLIOTECA", terrazza: "SALA GIOCHI" };
const FLOOR = { ceo: P.carpetCEO, privato: P.carpetMgr, vetro: P.carpetGlass, open: P.tileOpen, ops: P.tileOps, trading: P.tileTrading, meeting: P.tileMeeting, service: P.tileService };

// ---------------------------------------------------------------- calpestabilita'
let WALK = null;
function buildWalk(objects) {
  const g = Array.from({ length: GH }, () => new Uint8Array(GW));
  for (let x = 0; x < GW; x++) for (const y of [16, 17, 18, 31, 32, 33]) g[y][x] = 1;         // corridoi
  for (const r of ROOMS) {
    for (let y = r.y + 1; y < r.y + r.h - 1; y++) for (let x = r.x + 1; x < r.x + r.w - 1; x++) g[y][x] = 1;
    for (const [dx, dy] of r.doors) g[dy][dx] = 1;
  }
  for (const o of objects) for (const [x, y] of o.blocks || []) if (g[y]) g[y][x] = 0;
  WALK = g;
}

function astar(sx, sy, tx, ty) {
  if (!WALK) return [];
  const key = (x, y) => y * GW + x;
  const open = [[sx, sy]], came = new Map(), gs = new Map([[key(sx, sy), 0]]);
  const f = (x, y) => (gs.get(key(x, y)) ?? 1e9) + Math.abs(x - tx) + Math.abs(y - ty);
  const passable = (x, y) => x >= 0 && y >= 0 && x < GW && y < GH && (WALK[y][x] || (x === tx && y === ty));
  let guard = 0;
  while (open.length && guard++ < 6000) {
    let bi = 0;
    for (let i = 1; i < open.length; i++) if (f(...open[i]) < f(...open[bi])) bi = i;
    const [x, y] = open.splice(bi, 1)[0];
    if (x === tx && y === ty) {
      const path = [[x, y]];
      let k = key(x, y);
      while (came.has(k)) { const p = came.get(k); path.push(p); k = key(...p); }
      return path.reverse();
    }
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const nx = x + dx, ny = y + dy;
      if (!passable(nx, ny)) continue;
      const ng = gs.get(key(x, y)) + 1;
      if (ng < (gs.get(key(nx, ny)) ?? 1e9)) { gs.set(key(nx, ny), ng); came.set(key(nx, ny), [x, y]); if (!open.some((p) => p[0] === nx && p[1] === ny)) open.push([nx, ny]); }
    }
  }
  return [];
}

// ---------------------------------------------------------------- uffici: posto, ospite, arredi
const px = (t) => t * T;

function officeLayout(o, agent) {
  // ritorna { seat:[tx,ty,dir], visitor:[tx,ty,dir], objects:[{y, draw, blocks}] }
  const A = new Set(o.arredo || []);
  const objs = [];
  const add = (baseY, draw, blocks = []) => objs.push({ y: baseY, draw, blocks });
  const t = o.tier;
  if (t === "ceo") {
    const r = ROOM.ceo, X = r.x, Y = r.y;
    add(px(Y + 5), () => rug(ctx, px(X + 3), px(Y + 4) + 4, px(12), px(5), "#7a2232", "#8e2c40"));
    add(px(Y + 3), () => { for (const [ax, ay] of [[X + 1, Y + 1], [X + 16, Y + 1], [X + 1, Y + 10], [X + 16, Y + 10]]) plant(ctx, px(ax) + 8, px(ay) + 15, 3, true); }, [[X + 1, Y + 1], [X + 16, Y + 1], [X + 1, Y + 10], [X + 16, Y + 10]]);
    add(px(Y + 4), () => chair(ctx, px(X + 8), px(Y + 3) + 4, "pelle"));
    add(px(Y + 5) + 12, () => { desk(ctx, px(X + 6), px(Y + 5), px(5), "exec"); for (let i = 0; i < 3; i++) monitor(ctx, px(X + 6) + 14 + i * 16, px(Y + 5) - 4, frame); }, [[X + 6, Y + 5], [X + 7, Y + 5], [X + 8, Y + 5], [X + 9, Y + 5], [X + 10, Y + 5]]);
    add(px(Y + 2), () => { bar(ctx, px(X + 13), px(Y + 1) + 6); globe(ctx, px(X + 3), px(Y + 1) + 2); }, [[X + 13, Y + 1], [X + 14, Y + 1], [X + 3, Y + 1]]);
    add(px(Y + 9), () => { shelf(ctx, px(X + 16), px(Y + 3), 14, px(5) - 4); if (A.has("trofei")) for (let i = 0; i < 3; i++) trophy(ctx, px(X + 1) + 2, px(Y + 4) + i * 13); }, [[X + 16, Y + 3], [X + 16, Y + 4], [X + 16, Y + 5], [X + 16, Y + 6], [X + 16, Y + 7], [X + 1, Y + 4], [X + 1, Y + 5], [X + 1, Y + 6]]);
    add(px(Y + 10), () => { sofa(ctx, px(X + 3), px(Y + 9) + 2, px(4), P.sofaCEO, P.sofaCEOLt); sofa(ctx, px(X + 11), px(Y + 9) + 2, px(4), P.sofaCEO, P.sofaCEOLt); ftable(ctx, px(X + 7) + 8, px(Y + 9) + 4, px(3), 12, P.mahogLt); },
      [[X + 3, Y + 9], [X + 4, Y + 9], [X + 5, Y + 9], [X + 6, Y + 9], [X + 11, Y + 9], [X + 12, Y + 9], [X + 13, Y + 9], [X + 14, Y + 9], [X + 8, Y + 9], [X + 9, Y + 9]]);
    if (A.has("acquario")) add(px(Y + 8), () => aquarium(ctx, px(X + 13), px(Y + 7), frame), [[X + 13, Y + 7], [X + 14, Y + 7]]);
    add(px(Y + 8), () => { floorLamp(ctx, px(X + 2), px(Y + 7) - 4); floorLamp(ctx, px(X + 15), px(Y + 7) - 4); }, [[X + 2, Y + 7], [X + 15, Y + 7]]);
    add(px(Y + 5), () => { armchair(ctx, px(X + 12), px(Y + 3) + 2, P.sofaCEO, P.sofaCEOLt); roundTable(ctx, px(X + 13), px(Y + 4) + 2, P.mahogLt); armchair(ctx, px(X + 14), px(Y + 3) + 2, P.sofaCEO, P.sofaCEOLt); },
      [[X + 12, Y + 3], [X + 13, Y + 4], [X + 14, Y + 3]]);
    add(px(Y + 8) - 2, () => { chair(ctx, px(X + 7), px(Y + 7) - 2, "ospite"); chair(ctx, px(X + 9), px(Y + 7) - 2, "ospite"); });
    return { seat: [X + 8, Y + 4, "down"], visitor: [X + 8, Y + 7, "up"], visitor2: [X + 10, Y + 7, "up"], objects: objs };
  }
  if (t === "privato") {
    const r = ROOM["p" + o.slot], X = r.x, Y = r.y;
    if (A.has("tappeto")) add(px(Y + 3), () => rug(ctx, px(X + 1) + 4, px(Y + 3), px(6) + 8, px(4), "#3c5080", "#46598c", "#c8a050"));
    add(px(Y + 2), () => plant(ctx, px(X + 1) + 8, px(Y + 1) + 15, 2), [[X + 1, Y + 1]]);
    add(px(Y + 3), () => shelf(ctx, px(X + 7), px(Y + 1), 14, px(3) - 4), [[X + 7, Y + 1], [X + 7, Y + 2], [X + 7, Y + 3]]);
    add(px(Y + 4), () => chair(ctx, px(X + 4), px(Y + 3) + 4, A.has("poltrona") ? "poltrona" : "ergo"));
    add(px(Y + 5) + 12, () => { desk(ctx, px(X + 3), px(Y + 5), px(3), agent && agent.grade >= 6 ? "exec" : "grande"); for (let i = 0; i < (A.has("monitor3") ? 3 : 2); i++) monitor(ctx, px(X + 3) + 4 + i * 13, px(Y + 5) - 4, frame); },
      [[X + 3, Y + 5], [X + 4, Y + 5], [X + 5, Y + 5]]);
    add(px(Y + 8), () => { chair(ctx, px(X + 3), px(Y + 7) - 2, "ospite"); chair(ctx, px(X + 5), px(Y + 7) - 2, "ospite"); });
    add(px(Y + 6), () => { cabinet(ctx, px(X + 1), px(Y + 5) - 4); floorLamp(ctx, px(X + 7), px(Y + 5) - 6); }, [[X + 1, Y + 5], [X + 7, Y + 5]]);
    add(px(Y + 11), () => { plant(ctx, px(X + 7) + 8, px(Y + 10) + 15, 2); if (!A.has("divano")) coatRack(ctx, px(X + 1), px(Y + 9) - 4); }, [[X + 7, Y + 10], ...(A.has("divano") ? [] : [[X + 1, Y + 9]])]);
    if (A.has("divano")) add(px(Y + 10), () => { sofa(ctx, px(X + 1), px(Y + 9) + 2, px(3), P.sofa, P.sofaLt); ftable(ctx, px(X + 2), px(Y + 8) + 4, 22, 10, P.wood); }, [[X + 1, Y + 9], [X + 2, Y + 9], [X + 3, Y + 9], [X + 2, Y + 8]]);
    if (A.has("trofeo")) add(px(Y + 3), () => trophy(ctx, px(X + 7) + 3, px(Y + 4) + 2), [[X + 7, Y + 4]]);
    if (A.has("acquario")) add(px(Y + 10), () => aquarium(ctx, px(X + 5) + 6, px(Y + 9), frame), [[X + 6, Y + 9], [X + 7, Y + 9]]);
    return { seat: [X + 4, Y + 4, "down"], visitor: [X + 4, Y + 7, "up"], objects: objs };
  }
  if (t === "vetro") {
    const r = ROOM["g" + o.slot], X = r.x, Y = r.y;
    add(px(Y + 2), () => rug(ctx, px(X + 2), px(Y + 2), px(5), px(3) - 2, "#4a5a46", "#52634c", "#8a7a5a"));
    add(px(Y + 2), () => plant(ctx, px(X + 1) + 8, px(Y + 1) + 15, 1), [[X + 1, Y + 1]]);
    add(px(Y + 3), () => shelf(ctx, px(X + 10), px(Y + 1), 14, px(2) - 2), [[X + 10, Y + 1], [X + 10, Y + 2]]);
    add(px(Y + 2) + 8, () => chair(ctx, px(X + 4), px(Y + 1) + 8, "ergo"));
    add(px(Y + 3) + 12, () => { desk(ctx, px(X + 3), px(Y + 3), px(3), "legno"); monitor(ctx, px(X + 3) + 8, px(Y + 3) - 4, frame); monitor(ctx, px(X + 3) + 24, px(Y + 3) - 4, frame); },
      [[X + 3, Y + 3], [X + 4, Y + 3], [X + 5, Y + 3]]);
    if (A.has("trofeo")) add(px(Y + 3), () => trophy(ctx, px(X + 8), px(Y + 1) + 4), [[X + 8, Y + 1]]);
    if (A.has("acquario")) add(px(Y + 5), () => aquarium(ctx, px(X + 7), px(Y + 3) + 2, frame), [[X + 7, Y + 3], [X + 8, Y + 3]]);
    add(px(Y + 4), () => cabinet(ctx, px(X + 9), px(Y + 3) - 2), [[X + 9, Y + 3]]);
    return { seat: [X + 4, Y + 2, "down"], visitor: [X + 4, Y + 4, "up"], objects: objs };
  }
  if (t === "open") {
    const r = ROOM.open, c = o.slot % 4, rr = Math.floor(o.slot / 4);
    const dx = r.x + 2 + c * 5, sy = r.y + 2 + rr * 3;
    add(px(sy) + 8, () => chair(ctx, px(dx + 1), px(sy) + 8, A.has("sedia_ergonomica") ? "ergo" : "base"));
    add(px(sy + 1) + 12, () => {
      desk(ctx, px(dx), px(sy + 1), px(3), "base");
      monitor(ctx, px(dx) + 10, px(sy + 1) - 4, frame);
      if (A.has("monitor2")) monitor(ctx, px(dx) + 24, px(sy + 1) - 4, frame);
      if (A.has("pianta_piccola")) plant(ctx, px(dx) + 5, px(sy + 1) + 8, 0);
      if (A.has("lampada")) lamp(ctx, px(dx) + 38, px(sy + 1) - 6);
      if (o.vacante) { R(ctx, px(dx) + 13, px(sy + 1) + 2, 22, 7, P.paper); ctx.font = "9px VT323"; ctx.fillStyle = P.red; ctx.fillText("LIBERO", px(dx) + 15, px(sy + 1) + 8); }
    }, [[dx, sy + 1], [dx + 1, sy + 1], [dx + 2, sy + 1]]);
    return { seat: [dx + 1, sy, "down"], visitor: [dx + 3, sy, "left"], objects: objs };
  }
  if (t === "ops" || t === "trading") {
    const r = t === "ops" ? ROOM.ops : ROOM.trading;
    if (t === "ops") {
      const c = o.slot % 2, rr = Math.floor(o.slot / 2), dx = r.x + 2 + c * 6, sy = r.y + 2 + rr * 3;
      add(px(sy + 1) + 12, () => { desk(ctx, px(dx), px(sy + 1), px(3), "base"); monitor(ctx, px(dx) + 18, px(sy + 1) - 4, frame, false, P.screenBlue); }, [[dx, sy + 1], [dx + 1, sy + 1], [dx + 2, sy + 1]]);
      return { seat: [dx + 1, sy, "down"], visitor: [dx + 3, sy, "left"], objects: objs };
    }
    const dx = r.x + 3 + o.slot * 7, sy = r.y + 5;
    add(px(sy - 1) + 12, () => { desk(ctx, px(dx), px(sy - 1), px(3), "base"); monitor(ctx, px(dx) + 4, px(sy - 1) - 3, frame, false); monitor(ctx, px(dx) + 18, px(sy - 1) - 3, frame, false, P.screenBlue); }, [[dx, sy - 1], [dx + 1, sy - 1], [dx + 2, sy - 1]]);
    return { seat: [dx + 1, sy, "up"], visitor: [dx + 3, sy, "left"], objects: objs };
  }
  return null;
}

// ---------------------------------------------------------------- arredi fissi delle stanze comuni e servizi
function commonObjects(services) {
  const objs = [];
  const add = (y, draw, blocks = []) => objs.push({ y, draw, blocks });
  // sala riunioni
  const m = ROOM.meet;
  add(px(m.y + 7), () => { ftable(ctx, px(m.x + 4), px(m.y + 4) + 4, px(10), px(3), P.mahogLt); R(ctx, px(m.x + 4) + 4, px(m.y + 5), px(10) - 8, 2, "rgba(255,255,255,0.15)"); },
    Array.from({ length: 30 }, (_, i) => [m.x + 4 + (i % 10), m.y + 4 + Math.floor(i / 10)]));
  for (const [sx, sy, up] of MEET_SEATS) add(px(sy) + (up ? 12 : 4), () => chair(ctx, px(sx), px(sy) + (up ? 6 : 2), "ergo"));
  add(px(m.y + 10), () => { plant(ctx, px(m.x + 1) + 8, px(m.y + 10) + 15, 2); plant(ctx, px(m.x + 16) + 8, px(m.y + 10) + 15, 2); }, [[m.x + 1, m.y + 10], [m.x + 16, m.y + 10]]);
  // trading floor
  const tr = ROOM.trading;
  add(px(tr.y + 8), () => { plant(ctx, px(tr.x + 1) + 8, px(tr.y + 9) + 15, 1); plant(ctx, px(tr.x + 16) + 8, px(tr.y + 9) + 15, 1); }, [[tr.x + 1, tr.y + 9], [tr.x + 16, tr.y + 9]]);
  // sala operativa: armadi server
  const op = ROOM.ops;
  add(px(op.y + 9), () => { for (let i = 0; i < 3; i++) rack(ctx, px(op.x + 12) - 6, px(op.y + 1) + i * 32, frame + i * 11); }, Array.from({ length: 6 }, (_, i) => [op.x + 12, op.y + 1 + i]));
  // servizi
  for (const s of services) {
    const r = ROOM[s.id], X = r.x, Y = r.y;
    if (!s.attivo) continue;
    if (s.id === "caffe") {
      add(px(Y + 2), () => { coffeeMachine(ctx, px(X + 1), px(Y + 1) - 2, frame); waterCooler(ctx, px(X + 7) + 2, px(Y + 1) - 4); }, [[X + 1, Y + 1], [X + 7, Y + 1]]);
      add(px(Y + 5), () => { ftable(ctx, px(X + 3), px(Y + 4), px(2) + 8, 14, P.woodLt); mug(ctx, px(X + 3) + 6, px(Y + 4) + 3); mug(ctx, px(X + 4) + 8, px(Y + 4) + 4); }, [[X + 3, Y + 4], [X + 4, Y + 4]]);
      add(px(Y + 4), () => { stool(ctx, px(X + 2), px(Y + 4)); stool(ctx, px(X + 5) + 8, px(Y + 4)); });
      add(px(Y + 2), () => pastries(ctx, px(X + 3), px(Y + 1) + 2), [[X + 3, Y + 1], [X + 4, Y + 1]]);
      add(px(Y + 9), () => plant(ctx, px(X + 7) + 8, px(Y + 9) + 15, 1), [[X + 7, Y + 9]]);
    }
    if (s.id === "lounge") {
      add(px(Y + 9), () => { sofa(ctx, px(X + 1), px(Y + 8) + 2, px(3), P.sofa, P.sofaLt); sofa(ctx, px(X + 5), px(Y + 8) + 2, px(3), P.sofa, P.sofaLt); }, [[X + 1, Y + 8], [X + 2, Y + 8], [X + 3, Y + 8], [X + 5, Y + 8], [X + 6, Y + 8], [X + 7, Y + 8]]);
      add(px(Y + 3), () => rug(ctx, px(X + 2), px(Y + 3), px(5), px(5), "#6a4a7a", "#7a5a8a", "#c8a050"));
      add(px(Y + 5), () => { ftable(ctx, px(X + 3), px(Y + 5), px(3), 12, P.woodLt); plant(ctx, px(X + 1) + 8, px(Y + 1) + 15, 2); plant(ctx, px(X + 7) + 8, px(Y + 1) + 15, 2); tv(ctx, px(X + 3), px(Y + 1) + 1, frame); }, [[X + 3, Y + 5], [X + 4, Y + 5], [X + 5, Y + 5], [X + 1, Y + 1], [X + 7, Y + 1], [X + 3, Y + 1], [X + 4, Y + 1], [X + 5, Y + 1]]);
    }
    if (s.id === "mensa") {
      add(px(Y + 2), () => { R(ctx, px(X + 1), px(Y + 1), px(7), 14, P.line); R(ctx, px(X + 1) + 1, px(Y + 1) + 1, px(7) - 2, 12, "#d8d4cc"); for (let i = 0; i < 5; i++) R(ctx, px(X + 1) + 6 + i * 20, px(Y + 1) + 3, 12, 5, ["#d8473a", "#efa52f", "#4fb06a", "#e8e6e0", "#8a5a36"][i]); }, Array.from({ length: 7 }, (_, i) => [X + 1 + i, Y + 1]));
      for (const [tx, ty] of [[X + 1, Y + 4], [X + 5, Y + 4], [X + 1, Y + 7], [X + 5, Y + 7]]) {
        add(px(ty) + 2, () => { stool(ctx, px(tx), px(ty) - 8); stool(ctx, px(tx + 1), px(ty) - 8); });
        add(px(ty) + 14, () => { ftable(ctx, px(tx), px(ty), px(2) + 8, 14, P.woodLt); R(ctx, px(tx) + 4, px(ty) + 3, 8, 5, "#e8e6e0"); R(ctx, px(tx) + 20, px(ty) + 3, 8, 5, "#e8e6e0"); }, [[tx, ty], [tx + 1, ty]]);
      }
    }
    if (s.id === "palestra") {
      add(px(Y + 3), () => { treadmill(ctx, px(X + 1), px(Y + 1) + 4); treadmill(ctx, px(X + 5), px(Y + 1) + 4); }, [[X + 1, Y + 1], [X + 2, Y + 1], [X + 5, Y + 1], [X + 6, Y + 1]]);
      add(px(Y + 7), () => { weights(ctx, px(X + 2), px(Y + 6)); mat(ctx, px(X + 5), px(Y + 6), px(3), px(2)); bench(ctx, px(X + 2), px(Y + 9) - 4); }, [[X + 2, Y + 6], [X + 3, Y + 6], [X + 2, Y + 9], [X + 3, Y + 9]]);
    }
    if (s.id === "biblioteca") {
      add(px(Y + 3), () => { shelf(ctx, px(X + 1), px(Y + 1), px(3), px(2)); shelf(ctx, px(X + 5), px(Y + 1), px(3), px(2)); }, Array.from({ length: 6 }, (_, i) => [X + 1 + i + (i > 2 ? 1 : 0), Y + 1]));
      add(px(Y + 8), () => { chair(ctx, px(X + 2), px(Y + 6), "poltrona"); chair(ctx, px(X + 6), px(Y + 6), "poltrona"); lamp(ctx, px(X + 4) + 4, px(Y + 5)); }, [[X + 4, Y + 6]]);
    }
    if (s.id === "terrazza") {
      add(px(Y + 3), () => { arcade(ctx, px(X + 1), px(Y + 1) - 6, frame); arcade(ctx, px(X + 7), px(Y + 1) - 6, frame + 33); }, [[X + 1, Y + 1], [X + 7, Y + 1]]);
      add(px(Y + 7), () => pingpong(ctx, px(X + 2) + 8, px(Y + 5) + 4), [[X + 3, Y + 5], [X + 4, Y + 5], [X + 3, Y + 6], [X + 4, Y + 6]]);
    }
  }
  return objs;
}

const MEET_SEATS = [[59, 7, false], [61, 7, false], [63, 7, false], [65, 7, false], [59, 11, true], [61, 11, true], [63, 11, true], [65, 11, true], [57, 9, false], [68, 9, false]];
const SERVICE_SPOTS = {
  caffe: [[19, 36], [23, 36], [20, 39], [24, 39]], lounge: [[29, 41], [33, 41], [29, 37], [34, 37]],
  mensa: [[39, 38], [43, 38], [39, 41], [43, 41]], palestra: [[46, 37], [50, 37], [49, 41], [46, 41]],
  biblioteca: [[56, 41], [60, 41], [57, 39]], terrazza: [[64, 37], [67, 37], [64, 41], [69, 41]],
};

// ---------------------------------------------------------------- disegno di pavimenti, muri, finestre, cielo, insegna
function hourNow() { const d = new Date(); return d.getHours() + d.getMinutes() / 60; }
function skyColors(h) {
  if (h >= 7 && h < 17) return ["#6fb3e8", "#bfe3f6"];
  if (h >= 17 && h < 20) return ["#e0845a", "#f6c58a"];
  if (h >= 5 && h < 7) return ["#7a7ab8", "#f0b890"];
  return ["#0c1030", "#1e2450"];
}
function drawSky(x, y, w, h) {
  const [a, b] = skyColors(hourNow());
  const g = ctx.createLinearGradient(0, y, 0, y + h); g.addColorStop(0, a); g.addColorStop(1, b);
  ctx.fillStyle = g; ctx.fillRect(x, y, w, h);
}
function skyline(x0, y0, w, h, night) {
  let seed = 7;
  for (let x = x0; x < x0 + w; x += 0) {
    seed = (seed * 9301 + 49297) % 233280;
    const bw = 10 + (seed % 22), bh = 8 + (seed % (h - 4));
    R(ctx, x, y0 + h - bh, bw, bh, night ? "#1a1d34" : "#7d8fa8");
    for (let yy = y0 + h - bh + 3; yy < y0 + h - 2; yy += 4) for (let xx = x + 2; xx < x + bw - 2; xx += 4)
      if (((xx * 7 + yy * 13 + seed) % 5) < (night ? 2 : 1)) R(ctx, xx, yy, 2, 2, night ? "#f4d68a" : "#c8d8e8");
    x += bw + 1;
  }
}

function drawExterior(level) {
  const night = hourNow() >= 20 || hourNow() < 6;
  drawSky(0, 0, CW, px(4));
  skyline(0, 8, CW, px(4) - 12, night);
  R(ctx, 0, px(4) - 6, CW, 6, "#2c2840"); R(ctx, 0, px(4) - 6, CW, 1, "#5b5578");
  // insegna
  const name = "GERVA CAPITAL", sc = 3, tw = textWidth5(name, sc);
  const bw = tw + 76, bx = Math.round(CW / 2 - bw / 2), by = 6;
  const glow = level >= 2, neon = level >= 4;
  if (glow) { ctx.fillStyle = `rgba(227,178,74,${0.12 + (neon ? 0.06 * Math.sin(frame / 15) : 0)})`; ctx.fillRect(bx - 10, by - 4, bw + 20, 50); }
  R(ctx, bx, by, bw, 40, P.ink); R(ctx, bx + 2, by + 2, bw - 4, 36, "#141c38"); R(ctx, bx, by, bw, 2, P.gold); R(ctx, bx, by + 38, bw, 2, P.gold);
  R(ctx, bx + 8, by + 40, 4, 10, P.metalDk); R(ctx, bx + bw - 12, by + 40, 4, 10, P.metalDk);
  emblem(ctx, bx + 10, by + 7, 2, neon);
  pixelText(ctx, name, bx + 46, by + 9, sc, level >= 5 ? "#fff0a8" : P.gold);
  ctx.font = "10px VT323"; ctx.fillStyle = "#a8b0d0"; ctx.fillText("TRADING QUANTITATIVO · SOLO PAPER", bx + 46, by + 35);
  if (level >= 3) for (let i = 0; i < 8; i++) R(ctx, bx + 4 + i * ((bw - 8) / 7), by - 3, 3, 3, (Math.floor(frame / 12) + i) % 2 ? "#fff2b0" : P.goldDk);
}

function drawFloors() {
  for (let x = 0; x < GW; x++) for (const y of [16, 17, 18, 31, 32, 33]) R(ctx, px(x), px(y), T, T, P.corridor[(x + y) % 2]);
  for (let x = 0; x < GW; x += 6) { R(ctx, px(x), px(17) + 7, 8, 2, P.corridorLine); R(ctx, px(x), px(32) + 7, 8, 2, P.corridorLine); }
  for (const r of ROOMS) {
    const c = FLOOR[r.kind];
    for (let y = r.y + 1; y < r.y + r.h - 1; y++) for (let x = r.x + 1; x < r.x + r.w - 1; x++) {
      const X0 = px(x), Y0 = px(y);
      if (r.kind === "privato") {                      // parquet a doghe sfalsate
        for (let k = 0; k < 4; k++) { R(ctx, X0, Y0 + k * 4, T, 4, P.parquet[(x + k + y * 2) % 3]); R(ctx, X0 + ((k * 7 + x * 5) % 16), Y0 + k * 4, 1, 4, "rgba(0,0,0,0.18)"); }
      } else if (r.kind === "ceo") {                   // moquette con motivo a rombi
        R(ctx, X0, Y0, T, T, c[(x + y) % 2]); R(ctx, X0 + 7, Y0 + 3, 2, 2, "#7a2a3c"); R(ctx, X0 + 3, Y0 + 7, 2, 2, "#7a2a3c"); R(ctx, X0 + 11, Y0 + 7, 2, 2, "#7a2a3c"); R(ctx, X0 + 7, Y0 + 11, 2, 2, "#7a2a3c");
      } else {
        R(ctx, X0, Y0, T, T, c[(x + y) % 2]);
        if (r.kind === "open" || r.kind === "service") { R(ctx, X0, Y0, T, 1, "rgba(255,255,255,0.18)"); R(ctx, X0, Y0, 1, T, "rgba(255,255,255,0.12)"); }
        if (r.kind === "vetro") R(ctx, X0 + 4 + ((x * 3 + y) % 8), Y0 + 6, 1, 1, "rgba(255,255,255,0.08)");
      }
    }
  }
}

function drawWalls(services, level) {
  for (const r of ROOMS) {
    const glassy = r.kind === "vetro";
    const X = px(r.x), Y = px(r.y), Wd = px(r.w), Hd = px(r.h);
    // muro di fondo (faccia visibile)
    R(ctx, X, Y, Wd, T, glassy ? "#4f6070" : P.wallFace);
    R(ctx, X, Y, Wd, 3, P.wallTop); R(ctx, X, Y + T - 2, Wd, 2, P.wallTrim);
    if (r.ext) {                                                        // finestre sull'esterno
      const wins = r.kind === "ceo" ? [[1, 7], [10, 7]] : r.kind === "meeting" ? [[10, 7]] : [[2, 5]];
      for (const [a, b] of wins) { const wx = X + px(a), ww = px(b) - 4; R(ctx, wx - 1, Y + 2, ww + 2, 12, P.wallTrim); drawSky(wx, Y + 3, ww, 10); skyline(wx, Y + 4, ww, 9, hourNow() >= 20 || hourNow() < 6); for (let i = wx + 20; i < wx + ww; i += 24) R(ctx, i, Y + 3, 1, 10, P.wallTrim); }
      if (r.kind === "ceo") { art(ctx, X + px(8) + 4, Y + 3, 20, 10, 5, true); }
    } else if (!glassy) {
      if (r.kind === "open" || r.kind === "trading" || r.kind === "service") for (let i = X + 24; i < X + Wd - 24; i += 64) art(ctx, i, Y + 3, 14, 9, (i / 7) | 0);
    }
    if (r.kind === "meeting") { whiteboard(ctx, X + px(2), Y + 2, px(7), 13); }
    if (r.kind === "service" && r.service === "palestra" && services.find((x) => x.id === "palestra")?.attivo) mirror(ctx, X + px(2), Y + 2, px(5));
    if (r.kind === "trading") tradingWall(ctx, X + 8, Y + T + 1, Wd - 16, frame, SCREENS);
    // pareti laterali e di fronte (spessore di una tessera, viste dall'alto)
    const side = glassy ? P.glassEdge : P.wallTop;
    R(ctx, X, Y, 4, Hd, side); R(ctx, X + Wd - 4, Y, 4, Hd, side); R(ctx, X, Y + Hd - 4, Wd, 4, side);
    if (glassy) { ctx.fillStyle = P.glass; ctx.fillRect(X + 4, Y + Hd - 12, Wd - 8, 8); }
    // porte
    for (const [dx, dy] of r.doors) { R(ctx, px(dx), px(dy), T, dy === r.y ? T : 4, P.corridor[0]); R(ctx, px(dx), px(dy) + (dy === r.y ? 0 : 0), 2, dy === r.y ? T : 4, P.woodDk); R(ctx, px(dx) + 14, px(dy), 2, dy === r.y ? T : 4, P.woodDk); }
    // targa
    let label = r.kind === "service" ? SERVICE_NAMES[r.service] : r.name;
    if (r.kind === "privato" || r.kind === "vetro") label = OFFICE_LABEL[r.id] || "UFFICIO LIBERO";
    // targa sopra la porta, nel corridoio: non copre gli arredi
    ctx.font = "10px VT323"; const lw = ctx.measureText(label).width + 8;
    const [ddx, ddy] = r.doors[0], top = ddy === r.y;
    const lx = Math.max(2, Math.min(CW - lw - 2, px(ddx) + 8 - lw / 2)), ly = top ? Y - 12 : Y + Hd + 1;
    R(ctx, lx, ly, lw, 11, r.kind === "ceo" ? "#2a1a0e" : "rgba(11,10,20,0.85)"); R(ctx, lx, ly + 10, lw, 1, r.kind === "ceo" ? P.gold : P.edge || "#2c3a6e");
    ctx.fillStyle = r.kind === "ceo" ? P.gold : P.paper; ctx.fillText(label, lx + 4, ly + 9);
  }
  // servizi non ancora sbloccati
  for (const s of services) if (!s.attivo) {
    const r = ROOM[s.id], X = px(r.x) + 4, Y = px(r.y) + T, w = px(r.w) - 8, h = px(r.h) - T - 4;
    ctx.fillStyle = "rgba(20,18,30,0.72)"; ctx.fillRect(X, Y, w, h);
    ctx.save(); ctx.beginPath(); ctx.rect(X, Y, w, h); ctx.clip();
    for (let i = -h; i < w; i += 14) { ctx.fillStyle = "rgba(239,165,47,0.35)"; ctx.beginPath(); ctx.moveTo(X + i, Y + h); ctx.lineTo(X + i + 6, Y + h); ctx.lineTo(X + i + 6 + h * 0.4, Y); ctx.lineTo(X + i + h * 0.4, Y); ctx.fill(); }
    ctx.restore();
    ctx.font = "11px VT323"; ctx.fillStyle = P.amber;
    ctx.fillText("IN COSTRUZIONE", X + 14, Y + h / 2 - 6);
    ctx.fillStyle = P.paper; ctx.fillText(`si apre a +${(s.soglia * 100).toFixed(1).replace(".", ",")}%`, X + 12, Y + h / 2 + 8);
  }
}
let OFFICE_LABEL = {};
const SCREENS = Array.from({ length: 6 }, () => Array.from({ length: 28 }, () => 0.5));
