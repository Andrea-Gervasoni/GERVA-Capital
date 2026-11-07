// GERVA Capital — interfaccia a vetro liquido. Il portale non invia ordini: legge e, solo per Andrea, cambia impostazioni.
"use strict";

const TOKEN = document.querySelector('meta[name="andrea-token"]').content;
let STATE = null;
const NAMES = {};                                   // id agente -> {name, role, dept}

async function api(path, opts = {}) {
  const r = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json", "X-Andrea-Token": TOKEN } }, opts));
  if (r.status === 401) { location.href = "/login"; throw new Error("sessione scaduta: accedi di nuovo"); }
  if (!r.ok) {
    const t = await r.text(); let msg = t;
    try { const j = JSON.parse(t); msg = j.detail || j.errore || t; } catch (_) { /* testo semplice */ }
    throw new Error(String(msg || r.status));
  }
  return r.json();
}
function toast(msg, bad = true) {
  const el = document.getElementById("toast");
  el.textContent = msg; el.className = bad ? "bad" : ""; el.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => (el.hidden = true), 5000);
}
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const eur = (x, d = 0) => (x == null ? "—" : (+x).toLocaleString("it-IT", { minimumFractionDigits: d, maximumFractionDigits: d }) + " €");
const num = (x, d = 2) => (x == null ? "—" : (+x).toLocaleString("it-IT", { minimumFractionDigits: d, maximumFractionDigits: d }));
const pct = (x, d = 1) => (x == null ? "—" : (x * 100).toFixed(d).replace(".", ",") + "%");
const day = (s) => (s || "").slice(0, 10);
const when = (s) => (s || "").slice(5, 16).replace("T", " ");
const sg = (v, d = 0) => (v == null ? "—" : `<span class="${v >= 0 ? "pos" : "neg"}">${v >= 0 ? "+" : ""}${eur(v, d)}</span>`);
const nm = (id) => (NAMES[id] ? NAMES[id].name : id || "—");
const initials = (n) => String(n || "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
const avatar = (id, big = false) => `<span class="av d-${esc((NAMES[id] || {}).dept || "x")}${big ? " big" : ""}">${esc(initials(nm(id)))}</span>`;
const card = (label, value, sub = "", cls = "") => `<div class="kcard ${cls}"><div class="kl">${esc(label)}</div><div class="kv">${value}</div><div class="ks">${sub}</div></div>`;
const table = (rows, cols) => !rows || !rows.length ? "<p class='muted'>Nessun dato.</p>" :
  "<div class='tablewrap'><table><tr>" + cols.map((c) => `<th>${esc(c[1])}</th>`).join("") + "</tr>" +
  rows.map((r) => "<tr>" + cols.map((c) => `<td>${c[2] ? c[2](r[c[0]], r) : esc(r[c[0]])}</td>`).join("") + "</tr>").join("") + "</table></div>";
const tag = (v) => `<span class="tag ${esc(v)}">${esc(String(v ?? "").replace(/_/g, " "))}</span>`;
function applyWidths(root) { root.querySelectorAll("[data-w]").forEach((e) => (e.style.width = (+e.dataset.w || 0) + "px")); }

// ---------------------------------------------------------------- tema
(function theme() {
  let t = null; try { t = localStorage.getItem("gerva-theme"); } catch (_) { /* privato */ }
  if (t) document.documentElement.dataset.theme = t;
  document.getElementById("theme").onclick = () => {
    const dark = matchMedia("(prefers-color-scheme: dark)").matches;
    const cur = document.documentElement.dataset.theme || (dark ? "dark" : "light"), nx = cur === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = nx; try { localStorage.setItem("gerva-theme", nx); } catch (_) { /* privato */ }
    render(CUR.page, CUR.arg, true);
  };
})();

// il bordo del vetro si accende dove c'e' il puntatore
document.addEventListener("pointermove", (e) => {
  const el = e.target.closest && e.target.closest(".lg"); if (!el) return;
  const r = el.getBoundingClientRect(), a = Math.atan2(e.clientY - (r.top + r.height / 2), e.clientX - (r.left + r.width / 2)) * 180 / Math.PI + 90;
  el.style.setProperty("--rim", a.toFixed(0) + "deg");
}, { passive: true });

// ---------------------------------------------------------------- stato in alto
async function refreshState() {
  try {
    const s = STATE = await api("/api/state");
    const lv = s.diretta || {};
    document.querySelector("#live-pill .dot").classList.toggle("on", !!lv.fresca);
    document.getElementById("live-txt").textContent = lv.fresca ? "in diretta" : lv.eta_s != null ? `${Math.round(lv.eta_s / 60)} min fa` : "al battito";
    document.getElementById("mailn").textContent = s.posta_aperta || "";
    document.getElementById("banner-demo").classList.toggle("hidden", !s.demo);
    document.getElementById("banner-sim").classList.toggle("hidden", !s.simulato);
    if (CUR.page === "panoramica") fillOverviewTop(s);
  } catch (e) { console.warn(e); }
}

// ---------------------------------------------------------------- movimento
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
function countUp(root) {
  if (REDUCED) return;
  root.querySelectorAll(".big, .mid, .kcard .kv").forEach((el) => {
    const txt = el.textContent, m = txt.match(/[+-]?\d{1,3}(?:\.\d{3})+(?:,\d+)?|[+-]?\d+(?:,\d+)?/);
    if (!m || el.children.length > 1) return;
    const raw = m[0], dec = (raw.split(",")[1] || "").length, target = parseFloat(raw.replace(/\./g, "").replace(",", "."));
    if (!isFinite(target) || Math.abs(target) < 2) return;
    const fmt = (v) => (v < 0 ? "-" : raw.startsWith("+") ? "+" : "") + Math.abs(v).toLocaleString("it-IT", { minimumFractionDigits: dec, maximumFractionDigits: dec });
    const t0 = performance.now(), dur = 900, html = el.innerHTML;
    const step = (now) => { const k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      el.innerHTML = html.replace(raw, fmt(target * e)); if (k < 1) requestAnimationFrame(step); else el.innerHTML = html; };
    requestAnimationFrame(step);
  });
}
function moveSlider() {
  const tabs = document.getElementById("tabs"), on = tabs.querySelector("button.on");
  let sl = tabs.querySelector(".slider");
  if (!sl) { sl = document.createElement("span"); sl.className = "slider"; tabs.prepend(sl); tabs.classList.add("has-slider"); }
  if (!on) { sl.style.height = "0px"; return; }
  sl.style.height = on.offsetHeight + "px"; sl.style.transform = `translateY(${on.offsetTop}px)`;
}
window.addEventListener("resize", () => moveSlider());
function sparkSvg(series) {
  if (!series || series.length < 3) return "";
  const vs = series.map((p) => p.v), lo = Math.min(...vs), hi = Math.max(...vs), sp = hi - lo || 1, W = 300, H = 54;
  const pts = vs.map((v, i) => [(i / (vs.length - 1)) * W, H - 6 - ((v - lo) / sp) * (H - 12)]);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(""), last = pts[pts.length - 1];
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="sparkfill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="rgba(27,63,216,.18)"/><stop offset="1" stop-color="rgba(27,63,216,0)"/></linearGradient></defs>` +
    `<path class="a" d="${d}L${W},${H}L0,${H}Z"/><path class="l" d="${d}"/><circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="3"/></svg>`;
}

// ---------------------------------------------------------------- orologio "uomo morto"
const CLOCK = { ok: null, frozen: null, why: "" };
const hms = (d) => d.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
async function refreshHealth() {
  try {
    const h = await api("/api/health");
    const down = h.parti.filter((p) => !p.ok);
    CLOCK.ok = h.ok; CLOCK.frozen = h.ok ? null : (h.bloccato_a ? new Date(h.bloccato_a) : CLOCK.frozen);   // mai partito: --:--:--
    CLOCK.why = h.ok ? "Tutto vivo: " + h.parti.map((p) => p.nome).join(", ") : "FERMO: " + down.map((p) => `${p.nome} (${p.motivo}; ultimo segnale ${p.ultimo ? when(p.ultimo) : "mai"})`).join(" · ");
    document.getElementById("systems").innerHTML = `<p class="side-h">Programmi</p>` + h.parti.map((p) =>
      `<div class="sys ${p.ok ? "ok" : "ko"}" title="${esc(p.ok ? "vivo" : p.motivo)}"><i></i><span>${esc(p.nome)}</span><time>${p.ultimo ? esc(new Date(p.ultimo).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })) : "mai"}</time></div>`).join("");
  } catch (e) {                                                        // il portale stesso non risponde: si blocca anche cosi'
    if (CLOCK.ok !== false) { CLOCK.ok = false; CLOCK.frozen = new Date(); CLOCK.why = "FERMO: il portale non risponde"; }
  }
  document.title = CLOCK.ok === false ? "■ FERMO · GERVA Capital" : "GERVA Capital";
  tickClock();
}
function tickClock() {
  const el = document.getElementById("clock"); if (!el) return;
  if (CLOCK.ok === false) { el.classList.add("stop"); el.textContent = CLOCK.frozen ? hms(CLOCK.frozen) : "--:--:--"; }
  else { el.classList.remove("stop"); el.textContent = hms(new Date()); }
  el.title = CLOCK.why || el.title;
}

// ---------------------------------------------------------------- seduta di Wall Street, ora di New York
function nyNow() {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false })
    .formatToParts(new Date()).map((x) => [x.type, x.value]));
  return { wd: parts.weekday, min: (+parts.hour % 24) * 60 + +parts.minute };
}
const dur = (m) => (m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}` : `${m} min`);
function refreshSession() {
  const el = document.getElementById("session"); if (!el) return;
  const { wd, min } = nyNow(), O = 570, C = 960, weekend = wd === "Sat" || wd === "Sun";
  let st, sub, k = 0;
  if (weekend) { st = "Chiusa"; sub = "weekend · crypto aperte 24/7"; }
  else if (min < O) { st = "Pre-mercato"; sub = `apre tra ${dur(O - min)}`; }
  else if (min < C) { st = "Aperta"; sub = `chiude tra ${dur(C - min)}`; k = (min - O) / (C - O); }
  else { st = "Chiusa"; sub = wd === "Fri" ? "riapre lunedì" : `riapre tra ${dur(24 * 60 - min + O)}`; k = 1; }
  el.innerHTML = `<p class="side-h">Wall Street</p><div class="sess-row"><b class="${st === "Aperta" ? "pos" : ""}">${st}</b><span>${k > 0 && k < 1 ? Math.round(k * 100) + "%" : ""}</span></div><div class="sess-sub">${sub}</div><div class="sess-bar"><i></i></div><div class="sess-ticks"><span>9:30</span><span>12:45</span><span>16:00</span></div>`;
  el.querySelector(".sess-bar i").style.width = (k * 100).toFixed(1) + "%";
}
// la luce segue il puntatore sulle schede
document.addEventListener("pointermove", (e) => {
  const el = e.target.closest && e.target.closest(".lg.card, .kcard, .person, .idea"); if (!el) return;
  const r = el.getBoundingClientRect();
  el.style.setProperty("--mx", (e.clientX - r.left).toFixed(0) + "px"); el.style.setProperty("--my", (e.clientY - r.top).toFixed(0) + "px");
}, { passive: true });
// filo di avanzamento della lettura
window.addEventListener("scroll", () => {
  const h = document.documentElement, k = h.scrollTop / Math.max(1, h.scrollHeight - h.clientHeight);
  document.getElementById("progress").style.transform = `scaleX(${Math.min(1, k).toFixed(4)})`;
}, { passive: true });

// ---------------------------------------------------------------- nastro di mercato
async function refreshTape() {
  try {
    const t = await api("/api/tape"), s = STATE || {}, pf = s.portafogli || {}, tt = pf.totale || {};
    const it = (k, v, cls = "") => `<span><b>${esc(k)}</b><span class="${cls}">${v}</span></span>`, ch = (v) => (v == null ? "" : `${v >= 0 ? "▲" : "▼"} ${Math.abs(v * 100).toFixed(2).replace(".", ",")}%`);
    const items = [
      tt.nav_eur ? it("FONDO", eur(tt.nav_eur) + " " + ch(tt.pnl_eur / ((tt.nav_eur - tt.pnl_eur) || 1)), tt.pnl_eur >= 0 ? "up" : "dn") : "",
      ...(t.voci || []).map((x) => it(x.nome, `${num(x.valore, x.dec ?? 2)} ${ch(x.var)}`, x.var >= 0 ? "up" : "dn")),
      t.regime ? it("REGIME", esc(t.regime)) : "", (pf.ibkr || {}).leva != null ? it("LEVA", num(pf.ibkr.leva, 2) + "×") : "",
    ].join("");
    document.getElementById("tape-items").innerHTML = `<div class="run">${items}${items}</div>`;
    document.getElementById("tape-clock").textContent = t.mercato || "";
  } catch (_) { /* il nastro e' un di piu' */ }
}

// ---------------------------------------------------------------- eventi
const FEED = [];
function feedText(ev) {
  const p = ev.payload || {};
  return ({
    "news.bulletin": () => "Bollettino: " + (p.testo || "").slice(0, 110), "risk.alert": () => "Allarme: " + p.cosa, "risk.kill": () => "KILL: " + p.motivo,
    "postmortem": () => `Post-mortem di ${nm(p.agente)}: ${p.lezione}`, "career.promozione": () => `${nm(p.agente)} promosso a ${p.a}`,
    "career.retrocessione": () => `${nm(p.agente)} retrocesso a ${p.a}`, "career.clawback": () => `Clawback a ${nm(p.agente)}: −${p.gc} GC`,
    "mailbox.new": () => "Posta del Capo: " + p.title, "committee.decision": () => `Comitato: ${p.ricerca} → ${p.esito}`,
    "meeting.start": () => `Riunione: ${p.titolo}`, "meeting.end": () => `Decisione della riunione: ${p.decisione}`,
    "meeting.resolved": () => `Riunione #${p.id}: aveva ragione chi ha detto «${p.giusta}»`, "gc.bonus": () => `${nm(p.agente)} +${num(p.gc, 1)} GC (differito)`,
    "task.handoff": () => `${nm(p.da)} → ${nm(p.a)}: ${p.titolo}`, "release.applied": () => "Rilascio di GERVA-Q applicato: " + p.id,
    "idea.new": () => `${nm(ev.actor)} presenta un'idea: ${p.titolo}`, "idea.review": () => `${nm(ev.actor)} valuta l'idea #${p.id}: ${String(p.decisione).replace("_", " ")}`,
    "idea.entered": () => `Idea #${p.id} entra nel conto: ${p.simbolo} ${num(p.peso_pct, 1)}%`, "idea.closed": () => `Idea #${p.id} chiusa (${p.motivo}): alpha ${pct(p.alpha, 1)}`,
    "free.trade": () => `${nm(ev.actor)} apre ${p.lato} ${p.simbolo} da ${num(p.usd, 0)} $`, "free.closed": () => `${nm(ev.actor)} chiude ${p.simbolo} (${p.motivo}): ${num(p.pnl, 2)} $`,
    "rule.applied": () => `Regola cambiata: ${p.chiave} ${p.vecchio} → ${p.nuovo}`, "house_rule": () => `Regola di casa: ${p.tipo} = ${p.valore}`,
    "desk.overlay": () => `Desk: ${p.titoli} titoli proposti (${pct(p.totale, 1)} del conto)`, "signal.decided": () => `Segnale #${p.id} ${p.moneta || ""}: ${p.stato}`,
    "alpaca.orders": () => `Crypto: ${p.n} ordini su Alpaca`, "free.riesame": () => `Riesame dopo una perdita del ${pct(-p.perdita, 1)}`,
  }[ev.kind] || (() => null))();
}
function addFeed(ev, front = true) {
  const t = feedText(ev); if (!t) return;
  if (ev.id != null && FEED.some((f) => f.id === ev.id)) return;       // gia' visto (riconnessione o primo caricamento)
  const item = { ts: ev.ts, t, id: ev.id, fresh: front };
  if (front) FEED.unshift(item); else FEED.push(item);
  while (FEED.length > 80) FEED.pop();
}
function renderFeed() {
  const ul = document.getElementById("feed"); if (!ul) return;
  setTimeout(() => FEED.forEach((f) => (f.fresh = false)), 2500);
  ul.innerHTML = FEED.slice(0, 40).map((f) => `<li class="${f.fresh ? "new" : ""}"><span class="tm">${esc((f.ts || "").slice(11, 16))}</span><span>${esc(f.t)}</span></li>`).join("") || "<li class='empty'>Ancora niente di nuovo: qui compaiono idee, trade, riunioni e allarmi appena succedono.</li>";
}
function connectWS() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onmessage = (m) => { JSON.parse(m.data).forEach((ev) => { addFeed(ev); try { onWorldEvent(ev); } catch (_) { /* ufficio non pronto */ } if (ev.kind.startsWith("career") || ev.kind === "meeting.end") refreshWorld(); }); renderFeed(); };
  ws.onclose = () => setTimeout(connectWS, 3000);
}

// ---------------------------------------------------------------- navigazione
const GROUPS = { panoramica: ["panoramica"], plancia: ["plancia"], mercati: ["grafici", "desk"], segnali: ["segnali"],
  azienda: ["ufficio", "conversazioni", "persone", "org", "riunioni", "compiti", "report"], idee: ["idee", "regole", "banco"], ricerca: ["tecniche", "strategie", "ricerca"],
  posta: ["posta"], impostazioni: ["impostazioni"] };
const GROUP_NAME = { panoramica: "Panoramica", plancia: "Plancia", mercati: "Mercati", segnali: "Segnali", azienda: "Azienda", idee: "Idee e regole", ricerca: "Ricerca", posta: "Posta", impostazioni: "Impostazioni" };
const SECTION = { panoramica: "Il fondo", plancia: "Il fondo", mercati: "Il fondo", segnali: "Il fondo", azienda: "L'azienda", idee: "L'azienda", ricerca: "L'azienda", posta: "Tu", impostazioni: "Tu" };
const LABEL = { ufficio: "Ufficio", conversazioni: "Conversazioni", tecniche: "Tecniche del fondo", persone: "Persone", org: "Organigramma", riunioni: "Riunioni", compiti: "Compiti", report: "Report", idee: "Idee", regole: "Regole", banco: "Banco libero", grafici: "Il fondo e i titoli", desk: "Desk", ricerca: "Prove e fascicoli", strategie: "Strategie dai paper" };
const groupOf = (p) => Object.keys(GROUPS).find((g) => GROUPS[g].includes(p)) || "panoramica";
const CUR = { page: "panoramica", arg: null };
function go(page, arg) { CUR.arg = arg ?? null; if (location.hash !== "#/" + page) location.hash = "#/" + page; else render(page, CUR.arg); }
window.addEventListener("hashchange", () => render(location.hash.replace("#/", "") || "panoramica", CUR.arg));
document.getElementById("tabs").addEventListener("click", (e) => { const b = e.target.closest("[data-go]"); if (b) { go(b.dataset.go); document.body.classList.remove("side-open"); } });
document.getElementById("menu").onclick = () => document.body.classList.toggle("side-open");
document.getElementById("subnav").addEventListener("click", (e) => { const b = e.target.closest("[data-go]"); if (b) go(b.dataset.go); });

async function render(page, arg, keepScroll = false) {
  if (!PANELS[page]) page = "panoramica";
  CUR.page = page; CUR.arg = arg ?? null;
  const g = groupOf(page);
  document.querySelectorAll("#tabs [data-go]").forEach((b) => b.classList.toggle("on", groupOf(b.dataset.go) === g));
  document.getElementById("subnav").innerHTML = GROUPS[g].length > 1 ? GROUPS[g].map((p) => `<button data-go="${p}" class="${p === page ? "on" : ""}">${esc(LABEL[p] || p)}</button>`).join("") : "";
  const body = document.getElementById("pnl-body"), title = document.getElementById("pnl-title");
  if (!keepScroll) window.scrollTo({ top: 0 });
  const stage = document.getElementById("stage");
  stage.classList.toggle("hidden", page !== "ufficio");
  if (page === "ufficio") { try { resizeCanvas(); } catch (_) { /* il mondo si sta ancora caricando */ } }
  let t, h;
  if (!keepScroll) { body.classList.remove("enter"); body.innerHTML = `<div class="skeleton"><i></i><i></i><i></i><i></i><i class="w"></i></div>`; }
  try { [t, h] = await PANELS[page](arg); }
  catch (err) { t = "Qualcosa non va"; h = `<p class="err">Non riesco a caricare questa pagina: ${esc(err.message)}</p>`; }
  if (CUR.page !== page) return;                          // nel frattempo si e' cambiata pagina
  title.innerHTML = t; body.innerHTML = h; applyWidths(body); tidy(body);
  if (!keepScroll) { body.classList.remove("enter"); void body.offsetWidth; body.classList.add("enter"); countUp(body); }
  moveSlider();
  const gi = String(Object.keys(GROUPS).indexOf(g) + 1).padStart(2, "0");
  document.getElementById("eyebrow").innerHTML = `<b>${gi}</b> · ${esc(SECTION[g])}`;
  document.getElementById("ghost").textContent = gi;
  const crumbs = [SECTION[g], SECTION[g].toLowerCase().includes(GROUP_NAME[g].toLowerCase()) ? null : GROUP_NAME[g], GROUPS[g].length > 1 ? LABEL[page] || page : null].filter(Boolean);
  document.getElementById("crumb").innerHTML = crumbs.map((c, i) => i === crumbs.length - 1 ? `<b>${esc(c)}</b>` : `<span>${esc(c)}</span>`).join("<i>/</i>");
  if (AFTER[page]) { try { await AFTER[page](arg); } catch (err) { body.insertAdjacentHTML("beforeend", `<p class="err">Grafico non disponibile: ${esc(err.message)}</p>`); } }
}

// ---------------------------------------------------------------- ordine nella pagina
const EMPTY = /^(nessun|ancora nessun|ancora niente|nulla)/i;
function tidy(body) {
  const lede = document.getElementById("lede");
  lede.classList.add("hidden"); lede.classList.remove("open"); lede.innerHTML = "";
  body.querySelectorAll(":scope > p.muted, .card p.muted, .lg p.muted").forEach((p) => { if (EMPTY.test(p.textContent.trim())) p.classList.add("empty"); });
  const intro = [...body.querySelectorAll(":scope > p.muted")].find((p) => !p.id && !p.classList.contains("empty") && p.textContent.trim().length > 70);
  if (intro) { lede.innerHTML = intro.innerHTML; lede.classList.remove("hidden"); intro.remove(); }
}
document.getElementById("lede").addEventListener("click", (e) => { if (!e.target.closest("a")) e.currentTarget.classList.toggle("open"); });

// ---------------------------------------------------------------- pagine
const AFTER = {};
let PLANCIA_FILTER = { venue: "", stato: "" };
let peopleSort = ["punteggio", -1];
const KIND_LABEL = { algo: "strategia in codice", idea: "idea", free: "banco libero", desk: "capo desk", modello: "modello GERVA-Q", lungo: "lungo periodo", segnale: "segnale", sconosciuta: "?" };

let LAST_NAV = null;
function fillOverviewTop(s) {
  const el = document.getElementById("o-top"); if (!el) return;
  const pf = s.portafogli || {}, ib = pf.ibkr || {}, al = pf.alpaca || {}, tt = pf.totale || {}, lv = s.diretta || {};
  const navNow = tt.nav_eur || s.nav, moved = LAST_NAV != null && navNow != null && Math.round(navNow) !== Math.round(LAST_NAV) ? (navNow > LAST_NAV ? "tick-up" : "tick-dn") : "";
  LAST_NAV = navNow; setTimeout(() => { const b = el.querySelector(".big"); if (b && moved) b.classList.add(moved); }, 0);
  const base = (ib.nav_eur || 0) - (ib.pnl_eur || 0) + (al.disponibile ? (al.nav_eur || 0) - (al.pnl_eur || 0) : 0);
  el.innerHTML =
    `<div class="lg card fringe"><div class="lbl">Valore totale</div><div class="big">${tt.nav_eur ? eur(tt.nav_eur) : eur(s.nav)}</div>` +
      `<p>${sg(tt.pnl_eur ?? s.pnl)} <span class="muted">${base ? pct((tt.pnl_eur ?? 0) / base, 2) : ""} dall'inizio · IBKR + Alpaca</span></p>` +
      `<p class="muted">${lv.fresca ? `<span class="busy">● in diretta</span>${lv.stima ? " (stima tra due letture esatte)" : ""}` : "aggiornato al battito"} · cambio ${num(pf.cambio_usd_eur, 4)} €/$</p></div>` +
    `<div class="lg card"><div class="lbl">IBKR · azioni</div><div class="mid">${eur(ib.nav_eur || s.nav)}</div><p>${sg(ib.pnl_eur)}</p><p class="muted">leva sul conto ${ib.leva == null ? "—" : num(ib.leva, 2) + "×"}</p></div>` +
    `<div class="lg card"><div class="lbl">Alpaca · crypto e banco libero</div><div class="mid">${al.disponibile ? eur(al.nav_eur) : "—"}</div><p>${al.disponibile ? sg(al.pnl_eur) + ` <span class="muted">${num(al.equity_usd, 0)} $</span>` : "<span class='muted'>non collegato</span>"}</p><p class="muted">leva sul conto ${al.leva == null ? "—" : num(al.leva, 2) + "×"}</p></div>` +
    `<div class="lg card"><div class="lbl">Rischio e risorse</div><div class="mid">${s.kill ? "<span class='neg'>KILL</span>" : `<span class="${s.semaforo === "verde" ? "pos" : s.semaforo === "rosso" ? "neg" : "gold"}">${esc(s.semaforo)}</span>`}</div>` +
      `<p>Agenti oggi ${num(s.budget_oggi, 2)} / ${num(s.tetto_oggi, 2)} €</p><p class="muted">${s.sciopero ? "sciopero in corso" : `autonomia ${s.giorni_residui == null ? "illimitata" : num(s.giorni_residui, 1) + " giorni"}`} · audit ${s.catena ? "integro" : "<span class='neg'>ROTTO</span>"}</p></div>`;
}

const PANELS = {
  async ufficio() {
    return ["Ufficio", `<p class="muted">L'azienda dal vivo. Le persone si muovono <b>solo per eventi veri</b>: un'idea portata al superiore, un compito affidato, una riunione con le parole dette, un trade aperto o chiuso, un segnale deciso, una regola votata. Se nessuno lavora, nessuno si muove. Clic su una persona per la sua scheda; tutto ciò che si dicono è in <a href="#/conversazioni">Conversazioni</a>.</p>`];
  },
  async conversazioni(arg) {
    const ag = typeof arg === "string" ? arg : "";
    const d = await api("/api/conversations?limit=80" + (ag ? "&agent=" + encodeURIComponent(ag) : ""));
    const opts = Object.entries(NAMES).sort((a, b) => a[1].name.localeCompare(b[1].name)).map(([id, v]) => `<option value="${esc(id)}" ${id === ag ? "selected" : ""}>${esc(v.name)}</option>`).join("");
    const msg = (m) => `<div class="msg"><div class="mh2">${m.chi && NAMES[m.chi] ? avatar(m.chi) : '<span class="av d-x">' + esc(initials(m.nome)) + "</span>"}<b>${esc(m.nome)}</b> <span class="tag">${esc(m.fase)}</span></div>` +
      `<p>${esc(m.testo)}</p>${(m.evidenze || []).length ? `<ul>${m.evidenze.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}${m.cambierei ? `<p class="muted">Cambierei idea se: ${esc(m.cambierei)}</p>` : ""}</div>`;
    return ["Conversazioni", `<div class="cbar"><select id="conv-agent"><option value="">Tutte le persone</option>${opts}</select><span class="muted">${d.length} conversazioni, le più recenti in alto</span></div>` +
      (d.map((c) => `<details class="mail conv"><summary class="mh"><span class="tag">${esc(c.tipo)}</span><b>${esc(c.titolo)}</b><span class="muted">${esc(when(c.ts))} · ${esc(c.motivo || "")} · ${c.messaggi.length} messaggi</span></summary>${c.messaggi.map(msg).join("")}</details>`).join("") ||
        "<p class='muted'>Ancora nessuna conversazione.</p>")];
  },
  async tecniche() {
    const d = await api("/api/techniques");
    const order = ["adottata", "approvata", "in attesa del voto", "in prova", "provata", "registrata", "bocciata"];
    const groups = {}; d.forEach((t) => (groups[t.stato] = groups[t.stato] || []).push(t));
    const keys = Object.keys(groups).sort((a, b) => (order.indexOf(a) + 99) % 99 - (order.indexOf(b) + 99) % 99);
    return ["Tecniche del fondo", `<div class="kgrid">${keys.map((k) => card(k, groups[k].length)).join("")}</div><p class="muted">Tutto ciò che il fondo usa, ha approvato, sta provando o ha bocciato, con la fonte. Le strategie dai paper si provano con <b>firm.py strategie --backtest tutte</b>; le regole le vota il comitato.</p>` +
      keys.map((k) => `<h3>${esc(k.charAt(0).toUpperCase() + k.slice(1))} (${groups[k].length})</h3>` + table(groups[k], [["nome", "Tecnica", (v) => `<b>${esc(v)}</b>`], ["tipo", "Tipo"], ["fonte", "Fonte", (v) => `<span class="muted">${esc(v)}</span>`], ["nota", "Stato e numeri"]])).join("")];
  },
  async panoramica() {
    const [office, blot, ideas] = await Promise.all([api("/api/office"), api("/api/blotter?stato=aperta").catch(() => null), api("/api/ideas?limit=8").catch(() => null)]);
    office.forEach((a) => (NAMES[a.id] = { name: a.name, role: a.role, dept: a.dept }));
    const now = Date.now(), recent = (ts) => ts && now - Date.parse(ts) < 15 * 60 * 1000;
    const busy = office.filter((a) => a.kind === "llm" && recent(a.ts) && a.stato !== "dorme");
    const ops = blot ? blot.operazioni.slice(0, 8) : [];
    const ID = ideas ? ideas.idee.slice(0, 6) : [];
    const hr = new Date().getHours(), hello = hr < 5 ? "Buonanotte" : hr < 13 ? "Buongiorno" : hr < 18 ? "Buon pomeriggio" : "Buonasera";
    return [`${hello}, <em>Andrea</em>`,
      `<div class="grid g-hero" id="o-top"></div>` +
      `<div class="grid g-2"><div class="lg card"><h3>Il conto contro l'S&P 500 <span class="sub">base 100</span></h3><canvas class="chart" id="o-eq"></canvas><p class="muted" id="o-eq-note"></p></div>` +
      `<div class="lg card"><h3>Cosa succede <span class="sub">in diretta</span></h3><ul class="feed" id="feed"></ul></div></div>` +
      `<div class="grid g-3">` +
        `<div class="lg card"><h3>Posizioni aperte <span class="sub"><a href="#/plancia">tutte →</a></span></h3>${ops.length ? ops.map((o) =>
          `<div class="tbl-row"><b>${esc(o.simbolo)}</b> ${tag(o.lato)} <span class="muted">${o.venue === "ibkr" ? "IBKR" : "Alpaca"}</span><span class="r">${sg(o.non_realizzato_eur, 0)} <small class="muted">${o.pnl_pct == null ? "" : num(o.pnl_pct, 1) + "%"}</small></span></div>`).join("") : "<p class='muted'>Nessuna posizione registrata ancora nella plancia.</p>"}</div>` +
        `<div class="lg card"><h3>Al lavoro adesso <span class="sub">${busy.length} di ${office.filter((a) => a.kind === "llm").length}</span></h3>${busy.length ? busy.map((a) =>
          `<div class="tbl-row clickable" data-agent="${esc(a.id)}">${avatar(a.id)}<span><b>${esc(a.name)}</b><br><span class="muted">${esc(a.stato)} · ${esc((a.compito || "").slice(0, 60))}</span></span></div>`).join("") : "<p class='muted'>Nessuno in questo momento: gli agenti lavorano a ogni battito (15 minuti), quando li chiama il banco libero o quando c'è una riunione.</p>"}</div>` +
        `<div class="lg card"><h3>Ultime idee <span class="sub"><a href="#/idee">tutte →</a></span></h3>${ID.length ? ID.map((i) =>
          `<div class="tbl-row clickable" data-idea="${i.id}"><span><b>${esc(i.title)}</b><br><span class="muted">${esc(nm(i.author))} · ${esc(i.kind)}</span></span><span class="r">${tag(i.status)}</span></div>`).join("") : "<p class='muted'>Ancora nessuna idea: ogni mattina tre agenti cercano.</p>"}</div>` +
      `</div>`];
  },

  async plancia(arg) {
    const f = PLANCIA_FILTER = Object.assign(PLANCIA_FILTER, typeof arg === "object" && arg ? arg : {});
    const q = new URLSearchParams(); if (f.venue) q.set("venue", f.venue); if (f.stato) q.set("stato", f.stato);
    const d = await api("/api/blotter?" + q), r = d.riepilogo, t = d.totali;
    const btn = (k, v, label) => `<button data-pf="${k}:${v}" class="${(f[k] || "") === v ? "on" : ""}">${label}</button>`;
    const rows = d.operazioni.map((o) => {
      const v = o.aperta ? o.non_realizzato_eur : o.realizzato_eur, pc = o.pnl_pct;
      return `<tr class="op" data-trade="${esc(o.chiave)}"><td>${esc(when(o.aperta_il))}</td><td>${o.venue === "ibkr" ? "IBKR" : "Alpaca"}</td><td><b>${esc(o.simbolo)}</b></td>` +
        `<td>${tag(o.lato)}</td><td>${num(o.qty, o.qty < 10 ? 4 : 0)}</td><td>${o.peso_conto_pct == null ? "—" : num(o.peso_conto_pct, 1) + "%"}</td>` +
        `<td>${num(o.ingresso, 2)} <small class="muted">${esc(o.valuta)}</small></td><td>${o.aperta ? `<span class="muted">ora</span> ${o.attuale == null ? "—" : num(o.attuale, 2)}` : num(o.uscita, 2)}</td>` +
        `<td>${sg(v, 2)} <small class="${(pc || 0) >= 0 ? "pos" : "neg"}">${pc == null ? "" : (pc >= 0 ? "+" : "") + num(pc, 2) + "%"}</small></td><td>${o.aperta ? tag("aperta") : tag("chiusa")}</td>` +
        `<td>${esc(KIND_LABEL[(o.origine || {}).kind] || "?")}${o.agente ? ` · ${esc(nm(o.agente))}` : ""}</td></tr><tr class="story hidden" data-for="${esc(o.chiave)}"><td colspan="11"><div class="sbox muted">Carico la storia…</div></td></tr>`;
    }).join("");
    return ["Plancia",
      `<div class="kgrid">${card("Totale · IBKR + Alpaca", eur(t.totale.nav_eur), sg(t.totale.pnl_eur) + " dall'inizio")}${card("IBKR · azioni", eur(t.ibkr.nav_eur), `leva ${t.ibkr.leva == null ? "—" : num(t.ibkr.leva, 2) + "×"}`)}` +
      `${card("Alpaca · crypto", t.alpaca.disponibile ? eur(t.alpaca.nav_eur) : "—", `leva ${t.alpaca.leva == null ? "—" : num(t.alpaca.leva, 2) + "×"}`)}` +
      `${card("Realizzato", sg(r.realizzato_eur), `${r.vincenti} in guadagno · ${r.perdenti} in perdita`)}${card("In corso", sg(r.non_realizzato_eur), `${r.aperte} posizioni aperte`)}</div>` +
      `<div class="cbar">${btn("stato", "", "Tutte")}${btn("stato", "aperta", "Aperte")}${btn("stato", "chiusa", "Chiuse")}<span class="muted">·</span>${btn("venue", "", "Tutti i conti")}${btn("venue", "ibkr", "IBKR")}${btn("venue", "alpaca", "Alpaca")}</div>` +
      (d.operazioni.length ? `<div class="scroll"><table class="tbl"><tr><th>Aperta</th><th>Conto</th><th>Titolo</th><th>Lato</th><th>Qtà</th><th>Peso</th><th>Ingresso</th><th>Uscita / ora</th><th>Risultato</th><th>Stato</th><th>Deciso da</th></tr>${rows}</table></div>` :
        "<p class='muted'>Ancora nessuna operazione registrata. Le esecuzioni di IBKR arrivano a ogni battito (con Trader Workstation collegata), quelle di Alpaca dal primo ordine.</p>") +
      `<p class="muted">Clic su una riga: come è nata la decisione (chi l'ha pensata, chi l'ha controllata, il comitato, il rischio) e cosa se ne è imparato. Peso = sul valore del conto. Leva = esposizione lorda diviso valore del conto. Commissioni crypto di Alpaca non ancora lette (risultato lordo). Cambio USD/EUR di IBKR: ${num(t.cambio_usd_eur, 4)}.</p>`];
  },

  async persone() {
    const rows = await api("/api/people");
    const [k, dir] = peopleSort;
    rows.sort((a, b) => ((a[k] ?? -1e9) > (b[k] ?? -1e9) ? 1 : -1) * dir);
    const H = (key, label) => `<th class="sort" data-sort="${key}">${label}${k === key ? (dir < 0 ? " ↓" : " ↑") : ""}</th>`;
    return ["Le persone dell'azienda", `<p class="muted">Clic su un nome per la scheda completa; clic su un'intestazione per ordinare.</p><div class="tablewrap"><table><tr>
      ${H("nome", "Nome")}${H("grado", "Grado")}${H("punteggio", "Punteggio")}${H("brier", "Brier")}${H("giuste", "Previsioni giuste")}${H("gc", "Gerva-Coin")}${H("differito", "Differito")}${H("costo", "Costo €")}${H("errori", "Errori")}</tr>
      ${rows.map((r) => `<tr><td><a href="#" data-agent="${r.id}" class="who-cell">${avatar(r.id)}<span><b>${esc(r.nome)}</b><br><span class="muted">${esc(r.ruolo)}</span></span></a></td><td>${esc(r.grado_nome)}<br><span class="muted">#${esc(r.rank_grado)} nel grado</span></td>
      <td>${r.punteggio == null ? "—" : `<span class="bar" data-w="${Math.round(r.punteggio * 70)}"></span> ${num(r.punteggio, 2)}`}</td>
      <td>${r.brier == null ? "—" : num(r.brier, 3)}</td><td>${r.giuste}/${r.previsioni}</td><td>${num(r.gc, 0)}</td><td>${num(r.differito, 0)}</td><td>${num(r.costo, 3)}</td><td>${r.errori}</td></tr>`).join("")}</table></div>`];
  },
  async riunioni() {
    const ms = await api("/api/meetings");
    if (!ms.length) return ["Riunioni", "<p class='muted'>Nessuna riunione ancora. Si convocano da sole: idee al comitato, ritmo di ingresso, regole, rischio.</p>"];
    return ["Riunioni", `<p class="muted">Chi vuole avere ragione deve averla nei fatti: le decisioni si pesano per la precisione storica di ognuno e vengono verificate dopo.</p>` + ms.map((m) => {
      const t = m.transcript || { posizioni: {}, repliche: {}, pesi: {} };
      const rows = Object.keys(t.repliche || {}).map((a) => {
        const p0 = t.posizioni[a] || {}, p1 = t.repliche[a] || {};
        return `<tr><td>${avatar(a)} <b>${esc(nm(a))}</b></td><td>${tag(p0.posizione)} ${esc(p0.argomento)}</td><td>${tag(p1.posizione_finale)} ${esc(p1.replica)}</td><td>${num(p1.fiducia, 2)}</td><td>${num(t.pesi?.[a], 2)}</td><td>${m.outcome ? (m.outcome.gc?.[a] >= 0 ? `<span class="pos">+${num(m.outcome.gc[a], 1)}</span>` : `<span class="neg">${num(m.outcome.gc?.[a], 1)}</span>`) : "<span class='muted'>in attesa</span>"}</td></tr>`;
      }).join("");
      return `<details class="meet"><summary class="mh"><b>#${m.id} ${esc(m.title)}</b> ${tag(m.kind)} ${tag(m.status)} <span class="muted">${esc(day(m.ts))} · decisione: <b>${esc(m.decision || "—")}</b></span></summary>
        <p class="muted">${esc(m.reason)}${m.outcome ? ` · i fatti: aveva ragione «${esc(m.outcome.giusta)}»` : m.resolve_after ? ` · si verifica dal ${esc(m.resolve_after)}` : ""}</p>
        <div class="tablewrap"><table><tr><th>Chi</th><th>Posizione</th><th>Replica</th><th>Fiducia</th><th>Peso</th><th>GC</th></tr>${rows}</table></div></details>`;
    }).join("")];
  },
  async report(dayArg) {
    const list = await api("/api/reports");
    const r = await api("/api/report/" + (dayArg || list[0] || "oggi"));
    const s = r.societa;
    return ["Report del " + esc(r.giorno), `<div class="reports">${list.map((d) => `<a href="#" data-report="${d}" class="${d === r.giorno ? "on" : ""}">${d}</a>`).join("")}</div>
      <div class="kgrid">${card("NAV", eur(s.nav), "rendimento " + pct(s.rendimento, 2))}${card("Rischio", esc(r.rischio.semaforo), r.rischio.allarmi.length + " allarmi")}
      ${card("Agenti oggi", eur(r.budget.spent_today, 3), "su " + eur(r.budget.daily_cap, 2))}${card("Posta", r.posta_aperta, "grandi richieste aperte")}</div>
      <h3>Correzioni proposte (${r.correzioni.length})</h3>${r.correzioni.map((c) => `<div class="fix g${c.gravita}"><b>[${c.gravita}] ${esc(c.cosa)}</b><p class="muted">${esc(c.evidenza)}</p><p>→ ${esc(c.azione)} <span class="b">${esc(c.chi)}</span></p></div>`).join("") || "<p class='muted'>Nessuna correzione necessaria.</p>"}
      <h3>Persone</h3>${table(r.persone, [["nome", "Nome"], ["grado", "Grado"], ["punteggio", "Punteggio", (v) => v == null ? "—" : num(v, 3)], ["gc", "GC", (v) => num(v, 0)], ["differito", "Differito", (v) => num(v, 0)], ["costo", "Costo €", (v) => num(v, 3)]])}
      <h3>Riunioni</h3>${table(r.riunioni, [["titolo", "Riunione"], ["decisione", "Decisione"], ["stato", "Stato", tag]])}`];
  },
  async org() {
    const t = await api("/api/org");
    const node = (n) => `<li><a href="#" data-agent="${n.id}">${esc(n.name)}</a> <span class="muted">${esc(n.role)} · ${esc(n.grade)}</span>${n.kind === "open" ? " " + tag("aperta") : n.kind === "code" ? ' <span class="tag">automa</span>' : ""}${n.children.length ? "<ul>" + n.children.map(node).join("") + "</ul>" : ""}</li>`;
    return ["Organigramma", `<div class="lg card tree"><ul>${node(t)}</ul></div>`];
  },
  async compiti(id) {
    const cmds = await api("/api/commands");
    id = id || (cmds[0] && cmds[0].id);
    let h = table(cmds, [["id", "#"], ["text", "Ordine", (v, r) => `<a href="#" data-cmd="${r.id}">${esc(v.slice(0, 90))}</a>`], ["status", "Stato", tag]]);
    if (id) {
      const t = await api("/api/tasks/" + id);
      const node = (n) => `<li><b>${esc(nm(n.assignee))}</b> ← ${esc(nm(n.assigner))}: ${esc(n.title)} ${tag(n.status)}${n.result ? `<div class="muted">${esc(typeof n.result === "string" ? n.result : (n.result.risultato || n.result.sintesi || JSON.stringify(n.result))).slice(0, 300)}</div>` : ""}${n.children.length ? "<ul>" + n.children.map(node).join("") + "</ul>" : ""}</li>`;
      h += `<h3>Ordine #${id}</h3><p>${esc(t.ordine ? t.ordine.text : "")}</p>${t.ordine && t.ordine.answer ? `<pre>${esc(t.ordine.answer)}</pre>` : ""}<div class="lg card tree"><ul>${t.compiti.map(node).join("") || '<li class="muted">Il Capo sta leggendo…</li>'}</ul></div>`;
    }
    return ["Compiti", `<p class="muted">Ciò che chiedi al Capo dalla barra in basso diventa un albero di compiti che scende nella gerarchia e risale con i risultati.</p>` + h];
  },

  async idee() {
    const d = await api("/api/ideas?limit=60"), I = d.idee;
    const by = (s) => I.filter((i) => s.includes(i.status)).length;
    return ["Idee", `<div class="kgrid">${card("In salita", by(["al_superiore"]), "dai superiori")}${card("Al comitato", by(["al_comitato"]))}${card("Nel conto", by(["in_corso"]), "posizioni aperte da idee")}` +
      `${card("Chiuse", by(["chiusa"]), I.filter((i) => i.status === "chiusa" && i.result && i.result.alpha > 0).length + " hanno battuto l'S&P 500")}${card("Respinte o scartate", by(["respinta", "scartata", "rimandata", "non_applicabile"]))}</div>` +
      `<p class="muted">Ogni agente è libero di cercare: presenta l'idea al superiore, che la porta su con le sue migliorie, fino al comitato che vota. Chi ha ragione nei fatti guadagna bonus e promozioni, chi sbaglia paga. Clic su un'idea per il percorso completo.</p>` +
      (I.map((i) => {
        const a = i.azione || {}, what = i.kind === "posizione" ? [`${esc(a.simbolo)} ${num(a.peso_pct, 1)}%`, a.stop_pct != null ? `stop ${num(a.stop_pct, 0)}%` : "", a.obiettivo_pct != null ? `obiettivo ${num(a.obiettivo_pct, 0)}%` : "", a.orizzonte_giorni ? `${a.orizzonte_giorni} giorni` : ""].filter(Boolean).join(" · ") : `${esc(a.chiave || a.riesame || "")} → ${esc(a.valore)}`;
        const res = i.result && i.result.alpha != null ? ` · <b class="${i.result.alpha >= 0 ? "pos" : "neg"}">alpha ${pct(i.result.alpha, 1)}</b> (${esc(i.result.motivo)})` : "";
        return `<div class="idea" data-idea="${i.id}"><div class="ih">${avatar(i.author)}<b>#${i.id} ${esc(i.title)}</b> ${tag(i.status)} <span class="tag">${esc(i.kind.replace("_", " "))}</span></div>` +
          `<p class="muted">${esc(nm(i.author))} · ${esc(when(i.ts))} · ${what} · probabilità dichiarata ${pct(i.p_success, 0)}${res}</p><div class="detail hidden"></div></div>`;
      }).join("") || "<p class='muted'>Ancora nessuna idea.</p>")];
  },
  async regole() {
    const [d, f] = await Promise.all([api("/api/ideas?limit=5"), api("/api/free")]);
    const hr = Object.entries(f.regole || {});
    return ["Regole", `<p class="muted">All'inizio nessuna regola: le scrivono gli agenti quando ne vedono il bisogno, le dibattono e le votano. Una regola votata si rispetta finché è in vigore, e si può riportare in consiglio per cambiarla, revocarla o riconfermarla. Ogni 14 giorni torna in consiglio da sola.</p>` +
      `<h3>Regole di casa del banco libero</h3>${hr.length ? `<div class="kgrid">${hr.map(([k, v]) => card(k.replace(/_/g, " "), esc(v), "in vigore")).join("")}</div>` : "<p class='muted'>Nessuna: libertà totale (valgono solo i limiti del broker).</p>"}` +
      `<h3>Storico delle regole di casa</h3>${table(f.storia_regole, [["ts", "Quando", (v) => esc(when(v))], ["kind", "Regola", (v) => esc(String(v).replace(/_/g, " "))], ["value", "Valore", (v) => (v ? esc(v) : "revocata")], ["who", "Chi"], ["status", "Stato", tag]])}` +
      `<h3>Impostazioni e motore cambiati dal comitato</h3>${table(d.regole, [["ts", "Quando", (v) => esc(when(v))], ["key", "Cosa"], ["old", "Prima"], ["new", "Dopo"], ["who", "Chi"], ["status", "Stato", tag]])}`];
  },
  async banco() {
    const f = await api("/api/free"), T = f.trade || [];
    const closed = T.filter((t) => t.status === "chiusa"), pnl = closed.reduce((a, t) => a + (t.pnl || 0), 0);
    return ["Banco libero", `<div class="kgrid">${card("Trade totali", T.length)}${card("Chiusi", closed.length, `${closed.filter((t) => t.pnl > 0).length} in guadagno`)}${card("Risultato chiusi", `<span class="${pnl >= 0 ? "pos" : "neg"}">${num(pnl, 2)} $</span>`, "lordo, conto Alpaca")}${card("Regole di casa", Object.keys(f.regole || {}).length || "nessuna")}</div>` +
      `<p class="muted">Sul conto paper di Alpaca gli agenti aprono e chiudono quando vogliono (anche trade di pochi minuti); il codice esegue e chiude per stop, obiettivo o tempo; guadagno e perdita sono loro.</p>` +
      table(T, [["ts", "Quando", (v) => esc(when(v))], ["agent", "Chi", (v) => esc(nm(v))], ["side", "Lato", tag], ["symbol", "Titolo", (v) => `<b>${esc(v)}</b>`], ["notional", "Importo $", (v) => num(v, 0)],
        ["stop_pct", "Stop", (v) => (v ? num(v, 2) + "%" : "—")], ["take_pct", "Obiettivo", (v) => (v ? num(v, 2) + "%" : "—")], ["status", "Stato", tag], ["pnl", "Risultato $", (v) => (v == null ? "—" : `<span class="${v >= 0 ? "pos" : "neg"}">${num(v, 2)}</span>`)], ["motivo", "Perché", (v) => `<span class="muted">${esc(String(v || "").slice(0, 120))}</span>`]])];
  },

  async desk() {
    const d = await api("/api/desk"), z = d.pod_zero, t = Object.entries(d.targets || {}).sort((x, y) => y[1] - x[1]);
    const tot = t.reduce((a, [, v]) => a + v, 0);
    return ["Desk", `<p class="muted">I capi desk propongono posizioni per il conto, il codice le valida e GERVA-Q le esegue.</p>` +
      (t.length ? `<div class="kgrid">${card("Proposte del", esc(d.data || "—"))}${card("Titoli", t.length)}${card("Totale sul conto", pct(tot, 1))}</div>` +
        table(t.map(([k, v]) => ({ k, v, desk: Object.entries(d.per_desk || {}).filter(([, m]) => m[k]).map(([n]) => n.replace("pod_", "")).join(", ") })), [["k", "Titolo"], ["v", "Peso sul conto", (v) => pct(v, 2)], ["desk", "Proposto da"]])
        : `<p class="muted">Nessuna proposta ancora: i capi desk lavorano ogni mattina.</p>`) +
      `<h3>Modello GERVA-Q</h3>${z.disponibile ? `<div class="kgrid">${card("Dati al", esc(z.dati_al))}${card("Esposizione target", pct(z.lorda))}${card("Quota crypto", pct(z.quota_crypto))}</div>` +
        table(Object.entries(z.pesi).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ k, v })), [["k", "Strumento"], ["v", "Peso sul conto", (v) => pct(v, 2)]]) : `<p class="muted">GERVA-Q non trovato (${esc(z.percorso)}).</p>`}`];
  },
  async grafici() {
    const ov = await api("/api/charts/overview"); CHARTS.ov = ov;
    if (!ov.simboli.length) return ["Il fondo e i titoli", "<p class='muted'>Servono i prezzi: lancia <b>firm.py data</b> sul Mac e riapri questa pagina.</p>"];
    const r = ov.regime || {}, opt = (s) => `<option value="${esc(s)}">${esc(s)}</option>`, sgnp = (v) => (v == null ? "" : `<span class="${v >= 0 ? "pos" : "neg"}">${pct(v, 1)}</span>`);
    CHARTS.sym = CHARTS.sym && ov.simboli.includes(CHARTS.sym) ? CHARTS.sym : (ov.portafoglio[0] || "SPY");
    const titoli = `<h3>Regime di mercato</h3><div class="kgrid">${card("S&P 500 (SPY)", r.spy != null ? num(r.spy, 2) : "—", r.spy_sopra_ema200 ? "sopra la media a 200 giorni" : "sotto la media a 200 giorni", r.spy_sopra_ema200 ? "" : "gold")}` +
      `${card("Distanza dalla EMA200", r.spy_vs_ema200 != null ? pct(r.spy_vs_ema200, 1) : "—")}${card("Ultimo mese", r.spy_r1m != null ? pct(r.spy_r1m, 1) : "—", "S&P 500")}` +
      `${card("VIX", r.vix != null ? num(r.vix, 1) : "—", r.vix_percentile != null ? `più alto del ${Math.round(r.vix_percentile * 100)}% degli ultimi 2 anni` : "")}${card("Lettura", esc(r.lettura || "—"))}</div>` +
      `<h3>Un titolo alla volta <span class="muted">(${ov.simboli.length} titoli)</span></h3><div class="cbar"><select id="c-sym">${ov.portafoglio.length ? `<optgroup label="Nel conto e dai desk">${ov.portafoglio.map(opt).join("")}</optgroup>` : ""}<optgroup label="Tutti">${ov.simboli.map(opt).join("")}</optgroup></select>` +
      [["3M", 63], ["6M", 126], ["1A", 252], ["3A", 756]].map(([n, d]) => `<button data-days="${d}">${n}</button>`).join("") + `</div>` +
      `<div class="kgrid" id="c-sum"></div><canvas class="chart" id="c-price"></canvas><canvas class="chart" id="c-rsi"></canvas><canvas class="chart" id="c-vol"></canvas><canvas class="chart" id="c-dd"></canvas>` +
      `<h3>Correlazioni a 120 giorni</h3><canvas class="chart" id="c-heat"></canvas>` +
      `<h3>Screener</h3>` + table(ov.screener, [["simbolo", "Titolo"], ["tipo", "Tipo"], ["nel_conto", "Nel conto", (v) => (v ? "sì" : "")], ["r1m", "1 mese", sgnp], ["r3m", "3 mesi", sgnp], ["r12m", "12 mesi", sgnp],
        ["vs_ema200", "vs EMA200", sgnp], ["rsi", "RSI"], ["vol", "Volatilità", (v) => pct(v, 0)], ["trend", "Trend", tag]]);
    return ["Il fondo e i titoli",
      `<div class="cbar"><button data-ctab="fondo">Il nostro fondo</button><button data-ctab="titoli">Titoli e indicatori</button></div>` +
      `<div id="sec-fondo"><p class="muted">Calcolo il portafoglio atteso e il Monte Carlo…</p></div><div id="sec-titoli" class="hidden">${titoli}</div>`];
  },
  async segnali() {
    const d = await api("/api/signals"), st = d.statistiche;
    const card1 = (r) => { const p = r.parsed || {}, c = r.controlli || {}, a = r.analisi || {};
      return `<div class="mail"><div class="mh"><b>#${r.id} ${esc(p.moneta || "?")} ${esc(p.direzione || "")}</b> ${tag(r.stato)} ${r.esito ? tag(r.esito) : ""}<span class="muted">${esc(when(r.ts))} · ${esc(r.fonte || "")}</span></div>` +
        `<p class="muted">${esc((r.testo || "").slice(0, 220))}</p>` +
        (p.ok ? `<p>Ingresso ${num(p.ingresso, 4)} · stop ${num(p.stop, 4)} · obiettivi ${(p.obiettivi || []).map((x) => num(x, 4)).join(", ")}${c.rr ? ` · rischio/rendimento ${num(c.rr, 1)}` : ""}</p>` : "") +
        ((c.problemi || []).length ? `<p class="neg">Controlli: ${esc(c.problemi.join("; "))}</p>` : "") +
        (a.motivo ? `<p><b>Analisi:</b> ${esc(a.motivo)}</p><p>Probabilità di arrivare all'obiettivo prima dello stop: <b>${pct(a.probabilita_tp1, 0)}</b> · peso: <b>${pct(r.peso, 2)}</b>${a.veto && a.veto.bloccato ? ` · <span class="neg">veto del Rischio: ${esc(a.veto.motivo)}</span>` : ""}</p>` : "") +
        `<p class="muted">Decisione: ${esc(r.motivo || "in analisi…")}${r.r_multiple != null ? ` · risultato ${num(r.r_multiple, 2)} R` : ""}</p></div>`; };
    return ["Segnali crypto", `<div class="lg card"><p class="muted">Incolla un segnale ricevuto: il desk crypto lo analizza con i dati veri e decide se tenerlo; il Rischio può solo bloccarlo. Quelli accettati si eseguono su Alpaca (paper). I segnali dalla chat Telegram arrivano da soli.</p>` +
      `<textarea id="sig-text" rows="4" placeholder="Es.: BUY SOL  entry 150  SL 140  TP1 165  TP2 180"></textarea><div class="cbar"><button id="sig-send" class="btn primary">Invia al desk crypto</button><span id="sig-msg" class="muted"></span></div></div>` +
      `<div class="kgrid">${card("Ricevuti", st.totale)}${card("Chiusi", st.chiusi, `${st.obiettivo} all'obiettivo · ${st.stop} allo stop · ${st.scaduti} scaduti`)}` +
      `${card("Arrivano all'obiettivo", st.tasso_obiettivo == null ? "—" : pct(st.tasso_obiettivo, 0), "sui segnali chiusi")}${card("Risultato medio", st.r_medio == null ? "—" : num(st.r_medio, 2) + " R", "R = rischio preso")}` +
      `${card("In posizione", Object.keys(d.posizioni).length ? Object.entries(d.posizioni).map(([k, v]) => `${esc(k)} ${pct(v, 1)}`).join(" · ") : "nessuna")}</div>` + d.segnali.map(card1).join("")];
  },
  async ricerca() {
    const d = await api("/api/research");
    return ["Ricerca", `<div class="kgrid">${card("Prove registrate", d.prove.n_trials, "contano nel Deflated Sharpe")}${card("Con Sharpe", d.prove.n_with_sharpe)}</div>` +
      table(d.fascicoli, [["title", "Fascicolo"], ["stage", "Fase", tag], ["gate", "Cancello", (v) => v ? (v.passa ? "passa" : "non passa") + (v.deflated ? ` · DSR ${num(v.deflated.dsr, 3)}` : "") : "—"], ["validation", "Validazione", (v) => v ? esc(v.esito) : "—"], ["decision", "Comitato", (v) => v && v.esito ? esc(v.esito) : "—"]])];
  },
  async strategie() {
    const d = await api("/api/strategies");
    return ["Strategie dai paper", `<p class="muted">Strategie scritte in codice a partire da studi pubblicati. Prima il backtest sui dati storici di Alpaca al netto dei costi, poi la prova entra nel registro (conta nel Deflated Sharpe), poi il comitato vota se accenderla. Accesa, gira da sola alla velocità di una macchina sul conto paper di Alpaca. Per il backtest: <b>firm.py strategie --backtest tutte</b>.</p>` +
      Object.entries(d).map(([k, v]) => { const b = v.backtest || {}, r = b.risultati || {};
        return `<div class="lg card"><h3>${esc(v.nome)} ${v.accesa ? tag("attivo") : '<span class="tag">spenta</span>'} <span class="sub">${esc(k)}</span></h3><p>${esc(v.ipotesi)}</p><p class="muted">Fonte: ${esc(v.fonte)}</p>` +
          (b.ok ? `<div class="kgrid">${card("Sharpe (netto costi)", num(r.sharpe, 2), `a costi doppi ${num((b.costi_doppi || {}).sharpe, 2)}`)}${card("Rendimento annuo", pct(r.rendimento_annuo, 1), `dal ${esc(r.dal)} al ${esc(r.al)}`)}${card("Calo massimo", pct(r.dd_max, 1))}${card("Deflated Sharpe", num((b.deflated || {}).dsr, 3), `${(b.deflated || {}).prove_totali} prove registrate`)}${card("Cancello statistico", (b.cancello || {}).passa ? "superato" : "non superato", "informazione per il voto")}${b.confronto ? card("Comprare e tenere", num(b.confronto.sharpe, 2), "Sharpe a confronto") : ""}</div>` : `<p class="muted">Backtest non ancora fatto.</p>`) +
          `<p class="muted">Capitale se accesa: ${pct(v.capitale, 0)} del conto Alpaca.</p></div>`; }).join("")];
  },
  async posta() {
    const items = await api("/api/mailbox");
    if (!items.length) return ["Posta del Capo", "<p class='muted'>Nessuna grande richiesta: il resto lo decide la società.</p>"];
    return ["Posta del Capo", `<p class="muted">Solo le grandi richieste: soldi veri, limiti di rischio, spese oltre il tetto, credenziali, cambi di direzione.</p>` + items.map((m) => `<div class="mail"><div class="mh"><b>${esc(m.title)}</b> ${tag(m.status)} <span class="tag">${esc(m.categoria)}</span></div><p>${esc(m.why)}</p>
      <p><b>Raccomandazione:</b> ${esc(m.recommendation)}</p><p class="muted"><b>Se non rispondi vale:</b> ${esc(m.safe_default)}</p>
      ${m.status === "aperta" ? m.options.map((o) => `<button class="btn" data-mail="${m.id}" data-choice="${esc(o)}">${esc(o)}</button>`).join("") + `<button class="btn ghost" data-mail="${m.id}" data-choice="__rimanda__">Rimanda</button>` : `<p class="muted">Scelta: ${esc(m.choice || "rimandata (vale il default)")}</p>`}</div>`).join("")];
  },
  async impostazioni() {
    const d = await api("/api/settings"), S_ = d.impostazioni;
    const row = (k, v, kind = "set") => `<div class="setrow"><label for="set-${esc(kind)}-${esc(k)}">${esc(k)}</label><input id="set-${esc(kind)}-${esc(k)}" data-k="${esc(k)}" data-kind="${kind}" value="${esc(JSON.stringify(v))}"><button class="btn" data-save="${esc(k)}" data-savekind="${kind}">Salva</button><em class="err" role="status"></em></div>`;
    const flat = (o, p = "") => Object.entries(o).flatMap(([k, v]) => (v && typeof v === "object" && !Array.isArray(v) ? flat(v, p + k + ".") : [[p + k, v]]));
    const groups = {};
    Object.entries(S_).filter(([k]) => k !== "firm.mode" && k !== "firm.strike").forEach(([k, v]) => { const g = k.split(".")[0]; (groups[g] = groups[g] || []).push([k, v]); });
    return ["Impostazioni", `<div class="lg card"><p>Ogni modifica va nel registro di audit. Autonomia degli agenti: <b>${d.budget.days_left == null ? "illimitata" : num(d.budget.days_left, 1) + " giorni"}</b> al ritmo di ${eur(d.budget.pace_eur_day, 3)} al giorno.</p>
      <div class="cbar"><button id="strikebtn" class="btn ${S_["firm.strike"] ? "" : "danger"}">${S_["firm.strike"] ? "Riprendi la società" : "Sciopero (ferma gli agenti)"}</button> <button class="btn danger" id="killbtn">${STATE && STATE.kill ? "Togli il KILL" : "KILL"}</button></div></div>` +
      Object.entries(groups).map(([g, rows]) => `<details class="mail"><summary class="mh"><b>${esc(g)}</b> <span class="muted">${rows.length} voci</span></summary>${rows.map(([k, v]) => row(k, v)).join("")}</details>`).join("") +
      `<details class="mail"><summary class="mh"><b>Limiti di rischio</b> <span class="muted">solo Andrea</span></summary>${flat(d.limiti).map(([k, v]) => row(k, v, "risk")).join("")}</details><p class="muted">I soldi veri sono bloccati: si sbloccano solo con la tua decisione.</p>`];
  },
};

// ---------------------------------------------------------------- dopo il caricamento
AFTER.panoramica = async () => {
  if (STATE) fillOverviewTop(STATE);
  renderFeed();
  const eq = await api("/api/equity"), c = document.getElementById("o-eq");
  const hero = document.querySelector("#o-top .card.fringe");
  if (hero && eq.conto && eq.conto.length > 2 && !hero.querySelector(".spark")) { hero.insertAdjacentHTML("beforeend", sparkSvg(eq.conto.slice(-200)));
    const pth = hero.querySelector(".spark path.l"); if (pth) pth.style.setProperty("--len", Math.ceil(pth.getTotalLength())); }
  if (c && eq.conto && eq.conto.length > 1) QC.equity(c, eq); else if (c) { c.classList.add("hidden"); document.getElementById("o-eq-note").textContent = eq.nota || "Servono almeno due letture del conto."; }
};
AFTER.segnali = async () => {
  const b = document.getElementById("sig-send"); if (!b) return;
  b.onclick = async () => {
    const t = document.getElementById("sig-text").value.trim(), m = document.getElementById("sig-msg");
    if (!t) { m.textContent = "Incolla prima il segnale."; return; }
    m.textContent = "Inviato: il desk lo sta analizzando (può servire un minuto)…";
    try { await api("/api/signals", { method: "POST", body: JSON.stringify({ text: t }) }); setTimeout(() => render("segnali"), 25000); } catch (e) { m.textContent = "Errore: " + e.message; }
  };
};
const CHARTS = { ov: null, sym: null, days: 252, years: 1, tab: "fondo", exp: null, zoom: 30 };
async function drawSymbol() {
  const d = await api(`/api/charts/series?sym=${encodeURIComponent(CHARTS.sym)}&days=${CHARTS.days}`), s = d.riepilogo;
  document.getElementById("c-sum").innerHTML = card(esc(d.simbolo), num(s.ultimo, 2), "ultimo prezzo al " + esc(s.data)) + card("Trend", esc(s.trend)) +
    card("1 / 3 / 12 mesi", [s.r1m, s.r3m, s.r12m].map((v) => (v == null ? "—" : pct(v, 0))).join(" · ")) + card("RSI", num(s.rsi, 0), esc(s.segnale_rsi)) +
    card("Volatilità 20 giorni", pct(s.vol20, 0), "annua") + card("Drawdown", pct(s.drawdown, 1), "dal massimo del periodo");
  QC.price(document.getElementById("c-price"), d); QC.rsi(document.getElementById("c-rsi"), d); QC.vol(document.getElementById("c-vol"), d); QC.drawdown(document.getElementById("c-dd"), d);
  document.querySelectorAll("#pnl-body [data-days]").forEach((b) => b.classList.toggle("on", +b.dataset.days === CHARTS.days));
}
async function drawFund() {
  const box = document.getElementById("sec-fondo"), f = await api(`/api/fund/overview?years=${CHARTS.years}`);
  CHARTS.exp = await api("/api/fund/expectation").catch(() => null);
  if (!f.ok) { box.innerHTML = `<p class="muted">${esc(f.motivo || "dati non disponibili")}</p>`; return; }
  const m = f.montecarlo, k = f.rischio, p = f.portafoglio, c = f.composizione, P = (v, d = 1) => pct(v, d);
  const E = (v) => (Math.abs(v) >= 1e6 ? (v / 1e6).toFixed(2).replace(".", ",") + " M" : (v / 1e3).toFixed(0) + " k") + " €";
  const X = CHARTS.exp, xs = X && X.registrata ? X.stato : null, pc2 = (v) => (v == null ? "—" : Math.round(v) + "°");
  const expHtml = !X || !X.registrata ? "" :
    `<h3>Aspettative scritte prima, e come sta andando</h3><div class="cbar">${[["1 sett.", 7], ["1 mese", 30], ["3 mesi", 90], ["1 anno", 365]].map(([n, d]) => `<button data-zoom="${d}">${n}</button>`).join("")}</div>` +
    `<canvas class="chart" id="f-exp"></canvas><div class="kgrid">${card("Dal via", P(X.rendimento_dal_via, 2), `${num(X.giorni_trascorsi, 1)} giorni di borsa`)}${card("Caso realistico", pc2(xs.realistico.percentile) + " percentile", esc(xs.realistico.lettura))}${card("Aspettativa del modello", pc2(xs.modello.percentile) + " percentile", esc(xs.modello.lettura))}` +
    `${card("A un anno (realistico)", `${eur(X.finale_realistico["5"])} – ${eur(X.finale_realistico["95"])}`, `mediana ${eur(X.finale_realistico["50"])}`)}</div>`;
  box.innerHTML = expHtml + `<h3>Cosa teniamo, con la leva</h3><div class="kgrid">${card("Esposizione lorda", P(p.lordo, 0), "del valore del conto")}${card("Leva", P(p.leva, 0), "denaro preso in prestito")}` +
    `${card("Azioni · ETF · crypto", [c.azioni, c.ETF, c.crypto].map((v) => P(v, 0)).join(" · "))}${card("Titoli indipendenti", num(k.titoli_indipendenti, 1), "rischi davvero diversi")}</div>` +
    `<h3>Quanto può perdere</h3><div class="kgrid">${card("In un giorno (VaR 95%)", E(k.var95_eur), P(k.var95, 2) + " del conto")}${card("Nei giorni peggiori (CVaR)", E(k.cvar95_eur))}${card("Volatilità annua", P(k.vol_annua, 1))}${card("Beta con l'S&P 500", num(k.beta_spy, 2))}${card("Peggior calo storico", P(k.dd_storico, 1))}</div>` +
    `<h3>Monte Carlo a ${m.anni === 1 ? "un anno" : m.anni + " anni"}</h3><div class="cbar"><button data-years="1">1 anno</button><button data-years="3">3 anni</button></div>` +
    `<canvas class="chart" id="f-fan"></canvas><div class="kgrid">${card("Caso mediano", E(m.finale["50"]), P(m.rendimento_mediano, 1))}${card("90% dei casi tra", E(m.finale["5"]) + " e " + E(m.finale["95"]))}${card("Chiude in perdita", P(m.p_perdita, 0))}${card("Tocca il freno", P(m.p_kill, 1))}</div><canvas class="chart" id="f-hist"></canvas>` +
    `<h3>Se tornasse una crisi già vista</h3><canvas class="chart" id="f-stress"></canvas><h3>Chi pesa sul rischio</h3><canvas class="chart" id="f-rc"></canvas>` +
    `<p class="muted">${m.percorsi.toLocaleString("it-IT")} percorsi ricampionando a blocchi di ${m.blocco} giorni la storia reale (${m.storia_giorni.toLocaleString("it-IT")} giorni dal ${esc(m.storia_dal)}). Scenari, non previsioni.</p>`;
  const fe = document.getElementById("f-exp");
  if (fe) {
    const draw = () => { QC.expect(fe, CHARTS.exp, CHARTS.zoom); document.querySelectorAll("#pnl-body [data-zoom]").forEach((b) => b.classList.toggle("on", +b.dataset.zoom === CHARTS.zoom)); };
    document.querySelectorAll("#pnl-body [data-zoom]").forEach((b) => (b.onclick = () => { CHARTS.zoom = +b.dataset.zoom; draw(); }));
    draw();
  }
  QC.fan(document.getElementById("f-fan"), m); QC.hist(document.getElementById("f-hist"), m);
  QC.bars(document.getElementById("f-stress"), f.stress.filter((x) => x.disponibile).map((x) => ({ name: x.nome, v: x.rendimento, label: `${(x.rendimento * 100).toFixed(1)}% · ${E(x.euro)}` })));
  QC.bars(document.getElementById("f-rc"), (k.contributi || []).map((x) => ({ name: x.simbolo, v: x.quota_rischio, label: `${(x.quota_rischio * 100).toFixed(1)}% del rischio · peso ${(x.peso * 100).toFixed(1)}%` })));
  document.querySelectorAll("#pnl-body [data-years]").forEach((b) => { b.classList.toggle("on", +b.dataset.years === CHARTS.years); b.onclick = async () => { CHARTS.years = +b.dataset.years; await drawFund(); }; });
}
function showTab(t) {
  CHARTS.tab = t;
  document.getElementById("sec-fondo").classList.toggle("hidden", t !== "fondo");
  document.getElementById("sec-titoli").classList.toggle("hidden", t !== "titoli");
  document.querySelectorAll("#pnl-body [data-ctab]").forEach((b) => b.classList.toggle("on", b.dataset.ctab === t));
}
AFTER.grafici = async () => {
  const body = document.getElementById("pnl-body");
  if (!document.getElementById("c-sym")) return;              // niente prezzi: la pagina lo dice gia', nessun grafico da disegnare
  body.querySelectorAll("[data-ctab]").forEach((b) => (b.onclick = () => showTab(b.dataset.ctab)));
  const sel = document.getElementById("c-sym"); sel.value = CHARTS.sym;
  sel.onchange = () => { CHARTS.sym = sel.value; drawSymbol(); };
  body.querySelectorAll("[data-days]").forEach((b) => (b.onclick = () => { CHARTS.days = +b.dataset.days; drawSymbol(); }));
  showTab(CHARTS.tab);
  const sec = document.getElementById("sec-titoli"), wasHidden = sec.classList.contains("hidden");
  sec.classList.remove("hidden");                             // i canvas si disegnano visibili (altrimenti larghezza zero)
  QC.heat(document.getElementById("c-heat"), CHARTS.ov.corr);
  await drawSymbol();
  if (wasHidden) sec.classList.add("hidden");
  await drawFund();
};

// ---------------------------------------------------------------- storie (plancia e idee)
const stepsHtml = (passi) => passi.map((p, i) => `<div class="step"><b>${p.chi.nome ? esc(p.chi.nome) : esc(p.chi.id || "")}</b>${p.chi.ruolo ? ` <span class="muted">${esc(p.chi.ruolo)}</span>` : ""} — ${esc(p.cosa)}` +
  (p.testo ? `<p>${esc(p.testo)}</p>` : "") + ((p.evidenze || []).length ? `<ul>${p.evidenze.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "") +
  (p.dati && Object.keys(p.dati).filter((k) => p.dati[k] != null).length ? `<p class="muted">${Object.entries(p.dati).filter(([, v]) => v != null).map(([k, v]) => `${esc(k.replace(/_/g, " "))}: ${esc(typeof v === "object" ? JSON.stringify(v) : v)}`).join(" · ")}</p>` : "") + `</div>`).join("");
async function toggleStory(key) {
  const row = [...document.querySelectorAll("tr.story")].find((r) => r.dataset.for === key); if (!row) return;
  row.classList.toggle("hidden"); if (row.classList.contains("hidden") || row.dataset.loaded) return;
  const box = row.querySelector(".sbox"), d = await api("/api/blotter/story?key=" + encodeURIComponent(key));
  if (!d.ok) { box.textContent = "Storia non disponibile."; return; }
  const o = d.operazione, l = d.lezione;
  const les = l ? `<div class="lesson ${esc(l.giudizio)}"><b>Cosa si è imparato</b> ${tag(l.giudizio === "errore" ? "errore" : l.giudizio === "tecnica_vincente" ? "approva" : "mantieni")} <span class="muted">${esc(l.giudizio.replace("_", " "))}</span><p>${esc(l.cosa)}</p><p><b>Lezione:</b> ${esc(l.lezione)}</p>${l.regola ? `<p><b>Per il futuro:</b> ${esc(l.regola)}</p>` : ""}</div>` :
    `<p class="muted">${o.aperta ? "Operazione aperta: la lezione si scrive dopo la chiusura." : "La lezione si scrive la sera, dopo le 21 UTC."}</p>`;
  const D = d.dossier || {}, I = D.indicatori || {}, F = D.previsione || {}, R = D.regime || {}, V = D.revisione || {};
  const ind = D.indicatori ? `<div class="kgrid">${card("Prezzo quel giorno", num(I.ultimo, 2), esc(I.data || ""))}${card("Trend", esc(I.trend || "—"), "prezzo, media 50, media 200")}${card("RSI 14", num(I.rsi, 0), esc(I.segnale_rsi || ""))}` +
    `${card("Rendimenti 1/3/12 mesi", [I.r1m, I.r3m, I.r12m].map((v) => (v == null ? "—" : pct(v, 0))).join(" · "))}${card("Volatilità 20 giorni", pct(I.vol20, 0), "annua")}${card("Distanza dalla media 200", pct(I.vs_ema200, 1))}${card("Bollinger %B", num(I.pct_b, 2))}` +
    `${card("Mercato", esc(R.lettura || "—"), R.vix != null ? `VIX ${num(R.vix, 1)} (${Math.round((R.vix_percentile || 0) * 100)}° percentile)` : "")}</div>` : "";
  const fc = F.ok ? `<div class="kgrid">${card(`Previsione a ${F.orizzonte_giorni} giorni`, pct(F.condizionata.p_sale, 0) + " sale", `quando il trend era «${esc(F.trend_oggi)}» · ${F.condizionata.casi} casi`)}${card("Mediana attesa", pct(F.condizionata.mediana, 2), `90% tra ${pct(F.condizionata.p5, 1)} e ${pct(F.condizionata.p95, 1)}`)}${card("Senza condizione", pct(F.tutte.p_sale, 0) + " sale", `${F.tutte.casi} casi`)}${D.modello ? card("Peso nel modello", pct(D.modello.peso_nel_conto, 2), "GERVA-Q, con la leva") : ""}</div>` : (D.previsione ? `<p class="muted">Previsione: ${esc(F.motivo || "non disponibile")}</p>` : "");
  const rv = (V.pro || V.contro) ? `<div class="grid g-2">${["pro", "contro"].map((k) => `<div class="lg card"><h3>${k === "pro" ? "A favore" : "Contro"}</h3>${(V[k] || []).map((x) => `<p><b>${esc(nm(x.agente))}</b> <span class="muted">probabilità di guadagno ${x.probabilita == null ? "—" : pct(x.probabilita, 0)}</span></p><p>${esc(x.testo)}</p><p class="muted">Indicatori usati: ${esc((x.indicatori || []).join(", "))}</p>`).join("") || "<p class='muted'>—</p>"}</div>`).join("")}</div>` :
    `<p class="muted">Argomenti a favore e contro: si scrivono la sera (dopo le 20 UTC) per ogni operazione nuova.</p>`;
  box.className = "sbox"; box.innerHTML = `<h4>Come è nata la decisione</h4>${stepsHtml(d.passi)}` + (d.grafico ? `<h4>Il grafico, con ingresso${o.aperta ? "" : " e uscita"}</h4><canvas class="chart" data-tradechart="1"></canvas>` : "") +
    (D.indicatori || D.previsione ? `<h4>Le prove al momento della decisione</h4>${ind}${fc}` : `<p class="muted">Dossier non disponibile: operazione registrata prima che i dossier esistessero.</p>`) + `<h4>Pro e contro</h4>${rv}${les}`;
  row.dataset.loaded = "1";
  const cv = box.querySelector("[data-tradechart]"); if (cv && d.grafico) QC.trade(cv, d.grafico);
}
async function toggleIdea(id, el) {
  const box = el.querySelector(".detail"); if (!box) { go("idee"); return; }
  box.classList.toggle("hidden"); if (box.classList.contains("hidden") || box.dataset.loaded) return;
  const d = await api("/api/ideas/" + id), i = d.idea, m = d.riunione;
  const hist = (i.history || []).map((h) => `<div class="step"><b>${esc(nm(h.chi))}</b> — ${esc(h.cosa)}${h.motivo ? `<p>${esc(h.motivo)}</p>` : ""}${h.miglioramenti ? `<p class="muted">Migliorie: ${esc(h.miglioramenti)}</p>` : ""}${h.p != null ? `<p class="muted">probabilità ${pct(h.p, 0)}</p>` : ""}</div>`).join("");
  const votes = m ? `<h4>Riunione #${m.id}: ${esc(m.decisione)}</h4>` + Object.entries(m.voti || {}).map(([p, v]) => `<div class="step"><b>${esc(nm(p))}</b> — ${tag(v.posizione)} fiducia ${num(v.fiducia, 2)}<p>${esc(v.argomento || "")}</p></div>`).join("") : "";
  box.innerHTML = `<p><b>Tesi:</b> ${esc(i.tesi)}</p>${(i.evidenze || []).length ? `<ul>${i.evidenze.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}<h4>Percorso</h4>${hist}${votes}`;
  box.dataset.loaded = "1";
}

// ---------------------------------------------------------------- scheda di un agente
const TIER_NAME = { ceo: "Suite del Capo", privato: "Ufficio privato", vetro: "Ufficio a vetri", open: "Open space", ops: "Sala operativa", trading: "Trading floor" };
function lineChart(series, { w = 340, h = 110, title = "", fmt = (v) => num(v, 2) } = {}) {
  if (!series || series.length < 2) return `<div class="chart empty">${esc(title)}<br><span class="muted">servono almeno due giorni di dati</span></div>`;
  const vs = series.map((p) => p.v), lo = Math.min(...vs), hi = Math.max(...vs), span = hi - lo || 1;
  const X = (i) => 34 + (i / (series.length - 1)) * (w - 44), Y = (v) => h - 18 - ((v - lo) / span) * (h - 34);
  const d = series.map((p, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(p.v).toFixed(1)}`).join("");
  return `<div class="chart"><div class="ct">${esc(title)}</div><svg viewBox="0 0 ${w} ${h}"><text x="0" y="${Y(hi) + 4}">${esc(fmt(hi))}</text><text x="0" y="${Y(lo) + 4}">${esc(fmt(lo))}</text><path d="${d}" fill="none" stroke="currentColor" stroke-width="2"/></svg></div>`;
}
async function openAgent(id) {
  const d = await api("/api/agent/" + id);
  const P_ = d.profilo, R_ = d.risultati, C_ = d.costi, pe = d.persona || {};
  NAMES[P_.id] = NAMES[P_.id] || { name: P_.nome, role: P_.ruolo, dept: P_.reparto };
  const head = document.getElementById("dlg-head"), body = document.getElementById("dlg-body"), tabs = document.getElementById("dlg-tabs");
  head.innerHTML = `${avatar(P_.id, true)}<div><h2>${esc(P_.nome)}</h2><div class="role">${esc(P_.ruolo)}</div><div class="badges"><span class="b gold">${esc(P_.grado)}</span><span class="b">${esc(P_.stato)}</span>${pe.rank_grado ? `<span class="b">#${esc(pe.rank_grado)} nel grado</span>` : ""}</div>` +
    `<div class="muted">Superiore: ${esc(P_.superiore ? nm(P_.superiore) : "Andrea")} · modello ${esc(P_.modello)}</div></div>`;
  const pt = R_.punteggio, F = R_.previsioni;
  const T_ = {
    "Panoramica": () => `<div class="kgrid">${card("Punteggio", pt.punteggio == null ? "—" : num(pt.punteggio, 3), `${pt.n_valutazioni} valutazioni`)}${card("Brier", F.brier == null ? "—" : num(F.brier, 3), "0,25 = tirare a indovinare")}` +
      `${card("Previsioni", `${F.giuste}/${F.risolte}`, `${F.aperte} aperte`)}${card("Gerva-Coin", num(C_.gc.saldo || 0, 1), `+${num(C_.gc.differito || 0, 1)} differiti`)}${card("Stipendio", pe.stipendio != null ? pe.stipendio + " GC/sett." : "—")}` +
      `${card("Costo API", eur(C_.totale.c, 3), `oggi ${eur(C_.oggi.c, 3)} · ${C_.totale.n} chiamate`)}${card("Errori", String(d.errori.length), "post-mortem")}</div>` +
      `<div class="charts">${lineChart(d.serie.punteggio, { title: "Punteggio medio per giorno" })}${lineChart(d.serie.gc, { title: "Gerva-Coin maturati", fmt: (v) => num(v, 0) })}</div>`,
    "Lavoro": () => `<p><b>Ora:</b> ${esc(d.ora.attivita.stato)} ${esc(d.ora.attivita.compito)}</p><ul class="timeline">${d.ora.eventi.map((e) => `<li><span class="tm">${esc(when(e.ts))}</span><b>${esc(e.kind)}</b> <span class="muted">${esc(JSON.stringify(e.payload).slice(0, 160))}</span></li>`).join("") || "<li class='muted'>Nessun evento.</li>"}</ul>`,
    "Previsioni": () => table(d.previsioni_lista, [["statement", "Enunciato"], ["prob", "Prob.", (v) => num(v, 2)], ["deadline", "Scadenza"], ["outcome", "Esito", (v) => (v == null ? "<span class='muted'>aperta</span>" : v ? "<span class='pos'>vera</span>" : "<span class='neg'>falsa</span>")]]),
    "Carriera": () => `<ul class="timeline">${d.carriera.map((c) => `<li><span class="tm">${esc(day(c.ts))}</span><b>${esc(c.kind)}</b> ${esc(c.reason)}</li>`).join("") || "<li class='muted'>Nessun evento di carriera.</li>"}</ul>`,
    "Errori": () => d.errori.map((e) => `<div class="pm"><b>${esc(e.what)}</b> <span class="b">gravità ${e.severity}</span><p>${esc(e.why)}</p><p class="muted">Lezione: ${esc(e.lesson)}</p></div>`).join("") || "<p class='muted'>Nessun errore registrato.</p>",
    "Memoria": () => `<pre>${esc(d.memoria || "(vuota)")}</pre>`,
  };
  tabs.innerHTML = Object.keys(T_).map((t, i) => `<button class="${i ? "" : "on"}">${t}</button>`).join("");
  const sel = (n) => { body.innerHTML = T_[n](); tabs.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.textContent === n)); };
  tabs.querySelectorAll("button").forEach((b) => (b.onclick = () => sel(b.textContent)));
  sel("Panoramica");
  document.getElementById("dialog").classList.remove("hidden"); document.getElementById("scrim").classList.remove("hidden");
}
function closeSheet() { document.getElementById("dialog").classList.add("hidden"); document.getElementById("scrim").classList.add("hidden"); }
document.getElementById("scrim").onclick = closeSheet;
document.querySelector("[data-close='dialog']").onclick = closeSheet;
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeSheet(); palClose(); document.body.classList.remove("side-open"); } });
document.addEventListener("click", (e) => { if (document.body.classList.contains("side-open") && !e.target.closest("#side, #menu")) document.body.classList.remove("side-open"); });

// ---------------------------------------------------------------- clic nelle pagine
document.getElementById("pnl-body").addEventListener("change", (e) => { if (e.target.id === "conv-agent") render("conversazioni", e.target.value, true); });
document.getElementById("pnl-body").addEventListener("click", async (e) => {
  const t = e.target.closest("[data-agent],[data-cmd],[data-mail],[data-save],[data-report],[data-sort],[data-pf],[data-trade],[data-idea],#strikebtn,#killbtn");
  if (!t || e.target.closest("a[href^='#/']")) return;
  if (t.tagName !== "SUMMARY") e.preventDefault();
  try {
    if (t.dataset.pf) { const [k, v] = t.dataset.pf.split(":"); render("plancia", { [k]: v }, true); return; }
    if (t.dataset.trade) { await toggleStory(t.dataset.trade); return; }
    if (t.dataset.idea) { await toggleIdea(t.dataset.idea, t); return; }
    if (t.dataset.agent) return openAgent(t.dataset.agent);
    if (t.dataset.cmd) return render("compiti", +t.dataset.cmd);
    if (t.dataset.report) return render("report", t.dataset.report);
    if (t.dataset.sort) { peopleSort = [t.dataset.sort, peopleSort[0] === t.dataset.sort ? -peopleSort[1] : -1]; return render("persone", null, true); }
    if (t.dataset.mail) { await api("/api/mailbox/" + t.dataset.mail, { method: "POST", body: JSON.stringify({ choice: t.dataset.choice }) }); render("posta"); refreshState(); return; }
    if (t.dataset.save) {
      const inp = document.querySelector(`input[data-k="${CSS.escape(t.dataset.save)}"][data-kind="${CSS.escape(t.dataset.savekind)}"]`);
      const err = t.parentElement.querySelector(".err"); err.textContent = "";
      let value;
      try { value = JSON.parse(inp.value); } catch (_) { err.textContent = "valore non valido: numero, true/false o testo tra virgolette"; return; }
      try { await api("/api/settings", { method: "POST", body: JSON.stringify({ key: t.dataset.save, value, kind: inp.dataset.kind }) }); t.textContent = "Salvato"; setTimeout(() => (t.textContent = "Salva"), 2000); refreshState(); }
      catch (e2) { err.textContent = e2.message; }
      return;
    }
    if (t.id === "strikebtn") { await api("/api/strike", { method: "POST", body: JSON.stringify({ on: t.textContent.startsWith("Sciopero") }) }); render("impostazioni", null, true); refreshState(); }
    if (t.id === "killbtn") {
      const on = !(STATE && STATE.kill);
      if (on && !t.dataset.armed) { t.dataset.armed = "1"; t.textContent = "Conferma: nessun ordine passerà"; setTimeout(() => { if (document.body.contains(t)) { delete t.dataset.armed; t.textContent = "KILL"; } }, 5000); return; }
      await api("/api/kill", { method: "POST", body: JSON.stringify({ on }) }); await refreshState(); render("impostazioni", null, true);
    }
  } catch (err) { toast(err.message); }
});

// ---------------------------------------------------------------- palette (⌘K): chiedi al Capo o vai a una pagina
const PAL = { sel: 0, items: [] };
const ASK = ["Chi ha aperto le posizioni crypto e perché?", "Fammi un riepilogo del rischio di oggi", "Cosa ha fatto il banco libero oggi?", "Quale idea sta andando meglio?"];
function palPages() {
  return Object.keys(GROUPS).flatMap((g) => GROUPS[g].map((p) => ({ go: p, t: LABEL[p] && GROUPS[g].length > 1 ? `${GROUP_NAME[g]} · ${LABEL[p]}` : GROUP_NAME[g], n: String(Object.keys(GROUPS).indexOf(g) + 1).padStart(2, "0") })));
}
function palRender() {
  const q = document.getElementById("cmdtext").value.trim(), ql = q.toLowerCase();
  const pages = palPages().filter((x) => !ql || x.t.toLowerCase().includes(ql)).slice(0, 7);
  PAL.items = q ? [{ ask: q }, ...pages] : [...ASK.map((a) => ({ ask: a, hint: true })), ...pages];
  PAL.sel = Math.min(PAL.sel, PAL.items.length - 1);
  document.getElementById("pal-list").innerHTML = (q ? "" : `<li class="pal-h">Domande al Capo</li>`) + PAL.items.map((x, i) =>
    (x.go && (i === 0 || !PAL.items[i - 1].go) ? `<li class="pal-h">Vai a</li>` : "") +
    `<li role="option" data-i="${i}" class="${i === PAL.sel ? "on" : ""}">${x.go ? `<span class="n">${x.n}</span>${esc(x.t)}<kbd>apri</kbd>` : `<span class="n">›</span>${x.hint ? "" : "Chiedi al Capo: "}<b>${esc(x.ask)}</b><kbd>invia</kbd>`}</li>`).join("");
}
function palOpen() {
  document.getElementById("palette").classList.remove("hidden"); PAL.sel = 0; palRender();
  setTimeout(() => document.getElementById("cmdtext").focus(), 10);
}
function palClose() { document.getElementById("palette").classList.add("hidden"); }
function palPick(i) {
  const x = PAL.items[i]; if (!x) return;
  if (x.go) { palClose(); go(x.go); return; }
  document.getElementById("cmdtext").value = x.ask; document.getElementById("cmd").requestSubmit();
}
document.getElementById("ask").onclick = palOpen;
document.getElementById("palette").addEventListener("click", (e) => { if (e.target.id === "palette") return palClose(); const li = e.target.closest("li[data-i]"); if (li) palPick(+li.dataset.i); });
document.getElementById("cmdtext").addEventListener("input", () => { PAL.sel = 0; palRender(); });
document.getElementById("cmdtext").addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); PAL.sel = (PAL.sel + (e.key === "ArrowDown" ? 1 : -1) + PAL.items.length) % PAL.items.length; palRender(); }
  else if (e.key === "Enter") { e.preventDefault(); palPick(PAL.sel); }
  else if (e.key === "Escape") palClose();
});
document.addEventListener("keydown", (e) => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target || {}).tagName || "");
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); return document.getElementById("palette").classList.contains("hidden") ? palOpen() : palClose(); }
  if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === "/") { e.preventDefault(); palOpen(); }
  else if (/^[1-9]$/.test(e.key)) { const g = Object.keys(GROUPS)[+e.key - 1]; if (g) go(GROUPS[g][0]); }
});

// ---------------------------------------------------------------- parla al Capo
document.getElementById("cmd").addEventListener("submit", async (e) => {
  e.preventDefault();
  const inp = document.getElementById("cmdtext"), text = inp.value.trim();
  if (!text) return;
  let r;
  try { r = await api("/api/command", { method: "POST", body: JSON.stringify({ text }) }); }
  catch (err) { toast("Ordine non inviato: " + err.message); return; }
  inp.value = ""; palClose(); toast("Ricevuto: il Capo sta lavorando.", false);
  go("compiti", r.id);
  let n = 0;
  const poll = setInterval(async () => { if (++n > 60 || CUR.page !== "compiti") return clearInterval(poll); render("compiti", r.id, true); }, 3000);
});

// ---------------------------------------------------------------- ufficio pixel (sim.js): eventi veri, clic, zoom
async function refreshWorld() { try { buildWorld(await api("/api/world")); } catch (e) { console.warn(e); } }
(function officeControls() {
  const cvs = document.getElementById("office"), tip = document.getElementById("tip");
  const entAt = (e) => { const [x, y] = screenToWorld(e); return Object.values(ENT).find((en) => x >= en.x - 9 && x <= en.x + 9 && y >= en.y - 26 && y <= en.y + 2); };
  cvs.addEventListener("mousemove", (e) => {
    const en = entAt(e); cvs.style.cursor = en ? "pointer" : "grab";
    if (!en) return tip.classList.add("hidden");
    tip.innerHTML = `<b>${esc(en.a.name)}</b><br>${esc(en.a.role)}<br><span class="muted">${esc(en.a.grade_name)} · ${esc(en.a.kind === "code" ? "automa (codice)" : en.a.stato)}</span>`;
    tip.style.left = e.clientX + 14 + "px"; tip.style.top = e.clientY + 10 + "px"; tip.classList.remove("hidden");
  });
  cvs.addEventListener("mouseleave", () => tip.classList.add("hidden"));
  cvs.addEventListener("click", (e) => { if (cam.drag && cam.drag.moved) return; const en = entAt(e); if (en) openAgent(en.id); });
  document.querySelectorAll("#zoom button").forEach((b) => (b.onclick = () => { const z = b.dataset.z; if (z === "fit") cam.z = 1; else zoomAt(cam.z * (+z), cam.cx, cam.cy); }));
})();

// ---------------------------------------------------------------- avvio
(async function start() {
  try { (await api("/api/office")).forEach((a) => (NAMES[a.id] = { name: a.name, role: a.role, dept: a.dept })); } catch (_) { /* il resto funziona lo stesso */ }
  try { (await api("/api/feed?limit=60")).forEach((ev) => addFeed(ev, false)); } catch (_) { /* idem */ }
  await refreshState();
  try { await document.fonts.load("11px VT323"); } catch (_) { /* carattere dell'ufficio */ }
  resizeCanvas(); await refreshWorld(); requestAnimationFrame(renderWorld);
  render(location.hash.replace("#/", "") || "panoramica");
  connectWS();
  setInterval(refreshState, 8000);
  setInterval(refreshWorld, 15000);
  refreshTape(); setInterval(refreshTape, 60000);
  refreshHealth(); setInterval(refreshHealth, 15000); setInterval(tickClock, 1000);
  refreshSession(); setInterval(refreshSession, 30000);
  setInterval(() => { if (CUR.page === "panoramica") renderFeed(); }, 8000);
})();
