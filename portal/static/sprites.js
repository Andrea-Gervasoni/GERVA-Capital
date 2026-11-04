// GERVA Capital — sprite originali generati da matrici di colori (nessun asset esterno).
// Ogni carattere della matrice e' un indice di palette; '.' e' trasparente.
"use strict";

const PAL = {
  ink: "#0d0b1a", night: "#1b1830", wall: "#3a3355", wallHi: "#5a5080", wallLo: "#262040",
  wood: "#8a5a3a", woodDk: "#5c3a24", woodHi: "#a8744c", paper: "#f2e8c9", gold: "#e8b04a",
  red: "#d9483b", redDk: "#8c2a22", green: "#4fb06a", greenDk: "#2c6a3e", cyan: "#5ec8d8",
  blue: "#3c6ec8", blueDk: "#24427a", purple: "#8a5cc0", pink: "#e07aa8", grey: "#9a9aaa",
  greyDk: "#5a5a6a", white: "#f4f4f4", black: "#000000", amber: "#f0a030", screen: "#14301c",
};

// colori della camicia per reparto
const DEPT_SHIRT = {
  direzione: ["#c0392b", "#7a1f16"], rischio: ["#e0a030", "#8a5a10"], ricerca: ["#3fa860", "#1f5a30"],
  validazione: ["#8a5cc0", "#4a2c70"], redazione: ["#3c6ec8", "#1f3a6a"], dati: ["#3aa8b0", "#1f5a60"],
  talent: ["#c07a40", "#6a3a18"], pod: ["#e0e0e8", "#8a8a98"],
};
const HAIR = ["#2a1a10", "#5a3418", "#a8742c", "#d8c070", "#1a1a1a", "#8a2a1a", "#c0c0c8", "#4a3a6a"];
const SKIN = ["#f0c8a0", "#d8a878", "#b07850", "#8a5a38", "#f8d8c0"];

// persona vista di fronte, 12x16. h capelli, s pelle, e occhi, m bocca, c camicia, C camicia scura,
// p pantaloni, b scarpe, g occhiali
const PERSON = [
  "...hhhhhh...",
  "..hhhhhhhh..",
  "..hssssssh..",
  "..sesssses..",
  "..ssssssss..",
  "...ssmmss...",
  "....ssss....",
  "..cccCCccc..",
  ".cccccccccc.",
  ".sccccccccs.",
  ".sccccccccs.",
  "..cccccccc..",
  "..pppppppp..",
  "..ppp..ppp..",
  "..ppp..ppp..",
  "..bbb..bbb..",
];
const LONG_HAIR_ROWS = { 2: "..hssssssh..", 3: ".hsesssesh..", 4: ".hssssssssh.", 5: ".h.ssmmss.h." };
const GLASSES_ROW = "..gegssgeg..";

// automa (codice deterministico): metallo, occhi ciano, LED che lampeggia
const ROBOT = [
  ".....a......",
  ".....L......",
  "...mmmmmm...",
  "..mMMMMMMm..",
  "..mMyMMyMm..",
  "..mMMMMMMm..",
  "..mMMwwMMm..",
  "...mmmmmm...",
  "....mmmm....",
  "..mmmmmmmm..",
  ".mmMMMMMMmm.",
  ".mmMddddMmm.",
  ".mmMMMMMMmm.",
  "..mmmmmmmm..",
  "..mm....mm..",
  "..kk....kk..",
];

const FOLDER = ["yyyy....", "yyyyyyyy", "yYYYYYYy", "yYYYYYYy", "yYYYYYYy", "yyyyyyyy"];
const LOCK = ["..gggg..", ".g....g.", ".g....g.", "gggggggg", "gGGGGGGg", "gGGkkGGg", "gGGkkGGg", "gggggggg"];

function hashStr(s) {
  let h = 2166136261;
  for (const ch of s) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

function drawMatrix(ctx, m, x, y, colors, scale = 1) {
  for (let r = 0; r < m.length; r++) {
    for (let c = 0; c < m[r].length; c++) {
      const k = m[r][c];
      if (k === "." || !(k in colors)) continue;
      ctx.fillStyle = colors[k];
      ctx.fillRect(x + c * scale, y + r * scale, scale, scale);
    }
  }
}

const _cache = new Map();

// sprite della persona, deterministico per agente (stesso aspetto a ogni avvio)
function personSprite(agent) {
  const key = "p:" + agent.id;
  if (_cache.has(key)) return _cache.get(key);
  const h = hashStr(agent.id);
  const rows = PERSON.slice();
  const longHair = (h >> 3) % 3 === 0;
  const glasses = (h >> 5) % 4 === 0;
  if (longHair) for (const [r, v] of Object.entries(LONG_HAIR_ROWS)) rows[+r] = v;
  if (glasses) rows[3] = GLASSES_ROW;
  const shirt = DEPT_SHIRT[agent.dept] || ["#888", "#555"];
  const colors = {
    h: HAIR[h % HAIR.length], s: SKIN[(h >> 8) % SKIN.length], e: PAL.ink, m: PAL.redDk,
    c: shirt[0], C: shirt[1], p: ["#2a2a40", "#3a2a20", "#202830"][(h >> 11) % 3], b: PAL.black, g: PAL.ink,
  };
  const cv = document.createElement("canvas");
  cv.width = 12; cv.height = 16;
  drawMatrix(cv.getContext("2d"), rows, 0, 0, colors);
  _cache.set(key, cv);
  return cv;
}

function robotSprite(ledOn) {
  const key = "r:" + ledOn;
  if (_cache.has(key)) return _cache.get(key);
  const cv = document.createElement("canvas");
  cv.width = 12; cv.height = 16;
  drawMatrix(cv.getContext("2d"), ROBOT, 0, 0, {
    a: PAL.grey, L: ledOn ? PAL.green : PAL.greenDk, m: PAL.greyDk, M: PAL.grey, y: PAL.cyan, w: PAL.white,
    d: PAL.screen, k: PAL.ink,
  });
  _cache.set(key, cv);
  return cv;
}

function folderSprite() {
  if (_cache.has("folder")) return _cache.get("folder");
  const cv = document.createElement("canvas");
  cv.width = 8; cv.height = 6;
  drawMatrix(cv.getContext("2d"), FOLDER, 0, 0, { y: "#c8902a", Y: PAL.gold });
  _cache.set("folder", cv);
  return cv;
}

function lockSprite() {
  if (_cache.has("lock")) return _cache.get("lock");
  const cv = document.createElement("canvas");
  cv.width = 8; cv.height = 8;
  drawMatrix(cv.getContext("2d"), LOCK, 0, 0, { g: PAL.gold, G: "#c8902a", k: PAL.ink });
  _cache.set("lock", cv);
  return cv;
}
