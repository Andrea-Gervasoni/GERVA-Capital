// GERVA Capital — interfaccia: barra KPI, feed, schede persone, pannelli. Il portale non invia ordini.
"use strict";

const TOKEN = document.querySelector('meta[name="andrea-token"]').content;
let STATE = null, soundOn = false;

async function api(path, opts = {}) {
  const r = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json", "X-Andrea-Token": TOKEN } }, opts));
  if (r.status === 401) { location.href = "/login"; throw new Error("sessione scaduta: accedi di nuovo"); }
  if (!r.ok) {
    const t = await r.text();
    let msg = t;
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
const eur = (x, d = 0) => (x == null ? "—" : x.toLocaleString("it-IT", { minimumFractionDigits: d, maximumFractionDigits: d }) + " €");
const num = (x, d = 2) => (x == null ? "—" : (+x).toLocaleString("it-IT", { minimumFractionDigits: d, maximumFractionDigits: d }));
const pct = (x, d = 1) => (x == null ? "—" : (x * 100).toFixed(d).replace(".", ",") + "%");
const day = (s) => (s || "").slice(0, 10);

// ---------------------------------------------------------------- suoni (spenti di default)
let actx = null;
function beep(f = 660, d = 0.06, type = "square") {
  if (!soundOn) return;
  actx = actx || new (window.AudioContext || window.webkitAudioContext)();
  const o = actx.createOscillator(), g = actx.createGain(); o.type = type; o.frequency.value = f; g.gain.value = 0.035;
  o.connect(g).connect(actx.destination); o.start(); o.stop(actx.currentTime + d);
}

// ---------------------------------------------------------------- barra superiore
function kpi(id, v, cls = "") { const el = document.getElementById(id); el.innerHTML = v; el.className = "v " + cls; }
async function refreshState() {
  try {
    const s = STATE = await api("/api/state");
    const fromIb = s.capitale && s.capitale.fonte === "IBKR";
    kpi("k-nav", eur(s.nav) + (fromIb ? "" : ` <small title="Capitale non ancora letto da IBKR: cifra di prova">prova</small>`));
    document.getElementById("k-nav").title = fromIb ? `Capitale letto da IBKR il ${s.capitale.dal}` : "Capitale non ancora letto da IBKR";
    document.getElementById("k-navsub").innerHTML = fromIb && s.nav_pod_simulati > 1 ? `conto IBKR ${eur(s.nav_conto)} · pod simulati +${eur(s.nav_pod_simulati)}` : "";
    kpi("k-pnl", (s.pnl >= 0 ? "+" : "") + eur(s.pnl) + ` <small>${pct(s.pnl / (s.capitale_iniziale || 100000), 2)}</small>`, s.pnl >= 0 ? "pos" : "neg");
    kpi("k-risk", `<i class="light ${s.semaforo}"></i>${s.kill ? "KILL" : s.semaforo}`);
    kpi("k-bud", `${num(s.budget_oggi, 3)} / ${num(s.tetto_oggi, 2)} €`);
    kpi("k-days", s.sciopero ? "SCIOPERO" : s.giorni_residui == null ? "∞" : num(s.giorni_residui, 1) + " gg");
    kpi("k-chain", s.catena ? "integra" : "ROTTA", s.catena ? "" : "neg");
    document.getElementById("mailn").textContent = s.posta_aperta || "";
    document.getElementById("banner-demo").classList.toggle("hidden", !s.demo);
    document.getElementById("banner-sim").classList.toggle("hidden", !s.simulato);
  } catch (e) { console.warn(e); }
}
async function refreshWorld() {
  try {
    const w = await api("/api/world");
    buildWorld(w);
    const b = w.edificio, nx = b.prossimo;
    kpi("k-lvl", `Liv. ${b.livello} · ${esc(b.nome)}`);
    document.getElementById("k-lvlbar").style.width = (nx ? Math.round((nx.progresso || 0) * 100) : 100) + "%";
    document.getElementById("k-lvlnext").textContent = nx ? `prossimo: ${nx.servizio} a +${num(nx.soglia * 100, 1)}%` : "livello massimo";
  } catch (e) { console.warn(e); }
}

// ---------------------------------------------------------------- feed eventi
const ICON = { "news.bulletin": "📰", "risk.alert": "⚠", "risk.kill": "⛔", "postmortem": "✎", "career.promozione": "★", "career.retrocessione": "▼",
  "career.clawback": "✂", "gateway.rejected": "✕", "gateway.accepted": "✓", "mailbox.new": "✉", "committee.decision": "⚖", "meeting.start": "◉",
  "meeting.end": "◉", "meeting.resolved": "◎", "gc.bonus": "◆", "pod.capital": "◈", "budget.strike": "Zz", "task.handoff": "▤", "release.applied": "⚙" };
function feedText(ev) {
  const p = ev.payload || {}, A = (id) => (ENT[id] ? ENT[id].a.name : id);
  return ({
    "news.bulletin": () => "Bollettino: " + (p.testo || "").slice(0, 90), "risk.alert": () => "Allarme: " + p.cosa, "risk.kill": () => "KILL: " + p.motivo,
    "postmortem": () => `Post-mortem ${A(p.agente)}: ${p.lezione}`, "career.promozione": () => `${A(p.agente)} promosso a ${p.a}`,
    "career.retrocessione": () => `${A(p.agente)} retrocesso a ${p.a}`, "career.clawback": () => `Clawback ${A(p.agente)}: -${p.gc} GC`,
    "gateway.rejected": () => `Gateway respinge ${p.strumento} [${p.pod}]: ${(p.motivi || [])[0] || ""}`, "gateway.accepted": () => `Gateway accetta ${p.lato} ${p.strumento} [${p.pod}]`,
    "mailbox.new": () => "Posta del Capo: " + p.title, "committee.decision": () => `Comitato: ${p.ricerca} → ${p.esito}`,
    "meeting.start": () => `Riunione: ${p.titolo}`, "meeting.end": () => `Decisione della riunione: ${p.decisione}`,
    "meeting.resolved": () => `Riunione #${p.id}: aveva ragione chi ha detto «${p.giusta}»`, "gc.bonus": () => `${A(p.agente)} +${p.gc} GC (differito)`,
    "pod.capital": () => `Capitale ${p.pod}: ${pct(p.da)} → ${pct(p.a)}`, "budget.strike": () => "Sciopero: " + p.motivo,
    "task.handoff": () => `${A(p.da)} → ${A(p.a)}: ${p.titolo}`, "release.applied": () => "Rilascio GERVA-Q applicato: " + p.id,
  }[ev.kind] || (() => null))();
}
function pushFeed(ev) {
  const t = feedText(ev);
  if (!t) return;
  const li = document.createElement("li");
  li.innerHTML = `<span class="ic">${ICON[ev.kind] || "•"}</span><span class="tm">${esc((ev.ts || "").slice(11, 16))}</span>${esc(t)}`;
  const ul = document.getElementById("feed"); ul.prepend(li);
  while (ul.children.length > 40) ul.lastChild.remove();
}
function connectWS() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onmessage = (m) => JSON.parse(m.data).forEach((ev) => { onWorldEvent(ev); pushFeed(ev); if (ev.kind.startsWith("career") || ev.kind === "meeting.end") refreshWorld(); });
  ws.onclose = () => setTimeout(connectWS, 3000);
}

// ---------------------------------------------------------------- tooltip e click sui personaggi
const tip = document.getElementById("tip");
function entAt(e) {
  const [x, y] = screenToWorld(e);
  return Object.values(ENT).find((en) => x >= en.x - 9 && x <= en.x + 9 && y >= en.y - 26 && y <= en.y + 2);
}
cv.addEventListener("mousemove", (e) => {
  const en = entAt(e);
  cv.style.cursor = en ? "pointer" : "default";
  if (!en) return tip.classList.add("hidden");
  const a = en.a;
  tip.innerHTML = `<b>${esc(a.name)}</b><br>${esc(a.role)}<br><span class="muted">${esc(a.grade_name)} · ${esc(a.kind === "code" ? "automa (codice)" : a.stato)}</span>`;
  tip.style.left = e.clientX + 14 + "px"; tip.style.top = e.clientY + 10 + "px"; tip.classList.remove("hidden");
});
cv.addEventListener("mouseleave", () => tip.classList.add("hidden"));
cv.addEventListener("click", (e) => { if (cam.drag && cam.drag.moved) return; const en = entAt(e); if (en) openAgent(en.id); });
document.querySelectorAll("#zoom button").forEach((b) => (b.onclick = () => { const z = b.dataset.z; if (z === "fit") { cam.z = 1; } else zoomAt(cam.z * (+z), cam.cx, cam.cy); }));

// ---------------------------------------------------------------- grafici SVG
function lineChart(series, { w = 340, h = 110, color = "#e3b24a", fmt = (v) => num(v, 2), title = "" } = {}) {
  if (!series || series.length < 2) return `<div class="chart empty">${esc(title)}<br><span class="muted">servono almeno due giorni di dati</span></div>`;
  const vs = series.map((p) => p.v), lo = Math.min(...vs), hi = Math.max(...vs), span = hi - lo || 1;
  const X = (i) => 30 + (i / (series.length - 1)) * (w - 40), Y = (v) => h - 18 - ((v - lo) / span) * (h - 34);
  const d = series.map((p, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(p.v).toFixed(1)}`).join("");
  return `<div class="chart"><div class="ct">${esc(title)}</div><svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
    <line x1="30" y1="${h - 18}" x2="${w - 10}" y2="${h - 18}" stroke="#31478a"/><text x="2" y="${Y(hi) + 4}" fill="#9aa">${esc(fmt(hi))}</text>
    <text x="2" y="${Y(lo) + 4}" fill="#9aa">${esc(fmt(lo))}</text><path d="${d}" fill="none" stroke="${color}" stroke-width="2"/>
    ${series.map((p, i) => `<rect x="${X(i) - 2}" y="${Y(p.v) - 2}" width="4" height="4" fill="${color}"><title>${esc(p.d)}: ${esc(fmt(p.v))}</title></rect>`).join("")}
    <text x="30" y="${h - 4}" fill="#9aa">${esc(series[0].d)}</text><text x="${w - 70}" y="${h - 4}" fill="#9aa">${esc(series[series.length - 1].d)}</text></svg></div>`;
}
function calibChart(curve) {
  if (!curve || !curve.length) return `<div class="chart empty">Calibrazione<br><span class="muted">nessuna previsione risolta</span></div>`;
  const s = 110;
  return `<div class="chart"><div class="ct">Calibrazione (diagonale = perfetta)</div><svg width="${s + 30}" height="${s + 20}" viewBox="-20 -5 ${s + 30} ${s + 20}">
    <rect x="0" y="0" width="${s}" height="${s}" fill="#0b1636" stroke="#31478a"/><line x1="0" y1="${s}" x2="${s}" y2="0" stroke="#5a5080" stroke-dasharray="3"/>
    ${curve.map((c) => `<circle cx="${c.prob_media * s}" cy="${(1 - c.frequenza) * s}" r="${2 + Math.min(5, c.n / 3)}" fill="#e3b24a"><title>p=${c.prob_media.toFixed(2)} · freq=${c.frequenza.toFixed(2)} · n=${c.n}</title></circle>`).join("")}
    <text x="-18" y="8" fill="#9aa">1</text><text x="-18" y="${s}" fill="#9aa">0</text></svg></div>`;
}
const card = (label, value, sub = "", cls = "") => `<div class="kcard ${cls}"><div class="kl">${esc(label)}</div><div class="kv">${value}</div><div class="ks">${sub}</div></div>`;

// ---------------------------------------------------------------- scheda persona
function portrait(agent, scale = 5) {
  const c = document.createElement("canvas"); c.width = 16; c.height = 24;
  const x = c.getContext("2d");
  if (agent.kind === "code") drawRobot(x, 0, 0, 0, DEPT[agent.dept]?.[0]); else drawPerson(x, 0, 0, lookFor(agent), "down", 0, false);
  c.style.width = 16 * scale + "px"; c.style.height = 24 * scale + "px"; c.className = "portrait";
  return c;
}
const TIER_NAME = { ceo: "Suite del Capo", privato: "Ufficio privato", vetro: "Ufficio a vetri", open: "Open space", ops: "Sala operativa", trading: "Trading floor" };

async function openAgent(id) {
  const d = await api("/api/agent/" + id);
  const P_ = d.profilo, R_ = d.risultati, C_ = d.costi, pe = d.persona || {};
  const dlg = document.getElementById("dialog"), head = document.getElementById("dlg-head"), body = document.getElementById("dlg-body"), tabs = document.getElementById("dlg-tabs");
  head.innerHTML = "";
  head.appendChild(portrait({ id: P_.id, dept: P_.reparto, grade: d.persona ? d.persona.grado : 3, kind: P_.tipo }));
  const info = document.createElement("div");
  info.className = "who";
  info.innerHTML = `<h2>${esc(P_.nome)}</h2><div class="role">${esc(P_.ruolo)}</div>
    <div class="badges"><span class="b gold">${esc(P_.grado)}</span><span class="b">${esc(TIER_NAME[d.ufficio?.tier] || "—")}</span>
    <span class="b">${esc(P_.stato)}</span>${pe.rank_grado ? `<span class="b">#${esc(pe.rank_grado)} nel grado</span>` : ""}</div>
    <div class="muted">Superiore: ${esc(P_.superiore ? (ENT[P_.superiore]?.a.name || P_.superiore) : "Andrea")} · Modello: ${esc(P_.modello)}</div>`;
  head.appendChild(info);
  const pt = R_.punteggio, F = R_.previsioni;
  const T_ = {
    "Panoramica": () => `<div class="kgrid">
        ${card("Punteggio", pt.punteggio == null ? "—" : num(pt.punteggio, 3), `${pt.n_valutazioni} valutazioni · 70% dure / 30% pari`)}
        ${card("Brier", F.brier == null ? "—" : num(F.brier, 3), "0,25 = tirare a indovinare", F.brier != null && F.brier > 0.25 ? "bad" : "")}
        ${card("Previsioni", `${F.giuste}/${F.risolte}`, `giuste su risolte · ${F.aperte} aperte`)}
        ${card("Gerva-Coin", num(C_.gc.saldo || 0, 1), `+${num(C_.gc.differito || 0, 1)} differiti (4 settimane)`, "gold")}
        ${card("Stipendio", pe.stipendio != null ? pe.stipendio + " GC/sett." : "—", "per grado")}
        ${card("Costo API", eur(C_.totale.c, 3), `oggi ${eur(C_.oggi.c, 3)} · ${C_.totale.n} chiamate`)}
        ${card("Canarini", `${pt.canarini_superati}/${pt.canarini}`, "test a sorpresa superati")}
        ${card("Errori", String(d.errori.length), "post-mortem registrate", d.errori.length ? "bad" : "")}
      </div><div class="charts">${lineChart(d.serie.punteggio, { title: "Punteggio medio per giorno", fmt: (v) => num(v, 2) })}
      ${lineChart(d.serie.gc, { title: "Gerva-Coin maturati (cumulati)", color: "#4fb06a", fmt: (v) => num(v, 0) })}</div>`,
    "Lavoro": () => `<p><b>Ora:</b> ${esc(d.ora.attivita.stato)} ${esc(d.ora.attivita.compito)}</p><ul class="timeline">${d.ora.eventi.map((e) =>
      `<li><span class="tm">${esc((e.ts || "").slice(5, 16).replace("T", " "))}</span><b>${esc(e.kind)}</b> <span class="muted">${esc(JSON.stringify(e.payload).slice(0, 160))}</span></li>`).join("") || "<li class='muted'>Nessun evento.</li>"}</ul>`,
    "Previsioni": () => `<div class="charts">${calibChart(F.curva)}<div>${card("Affidabilità", F.affidabilita == null ? "—" : num(F.affidabilita, 4), "più bassa è meglio")}${card("Risoluzione", F.risoluzione == null ? "—" : num(F.risoluzione, 4), "più alta è meglio")}</div></div>
      <table><tr><th>Enunciato</th><th>Prob.</th><th>Scadenza</th><th>Esito</th></tr>${d.previsioni_lista.map((f) => `<tr><td>${esc(f.statement)}</td><td>${num(f.prob, 2)}</td><td>${esc(f.deadline)}</td><td>${f.outcome == null ? "<span class='muted'>aperta</span>" : f.outcome ? "<span class='pos'>vera</span>" : "<span class='neg'>falsa</span>"}</td></tr>`).join("")}</table>`,
    "Carriera": () => `<ul class="timeline">${d.carriera.map((c) => `<li><span class="tm">${esc(day(c.ts))}</span><b>${esc(c.kind)}</b> ${esc(c.reason)}</li>`).join("") || "<li class='muted'>Nessun evento di carriera.</li>"}</ul>
      <p class="muted">Promozione: ≥ 30 valutazioni, migliore della media del grado (Welch, p &lt; 0,05), poi 14 giorni di prova. Ogni grado porta un ufficio migliore.</p>`,
    "Errori": () => d.errori.map((e) => `<div class="pm"><b>${esc(e.what)}</b> <span class="b">gravità ${e.severity}</span><p><span class="muted">Perché:</span> ${esc(e.why)}</p><p><span class="muted">Cosa cambia:</span> ${esc(e.change)}</p><p><span class="muted">Lezione:</span> ${esc(e.lesson)}</p></div>`).join("") || "<p class='muted'>Nessun errore registrato.</p>",
    "Costi": () => `<div class="kgrid">${card("Token oggi", `${C_.oggi.i} / ${C_.oggi.o}`, "ingresso / uscita")}${card("Token totali", `${C_.totale.i} / ${C_.totale.o}`, "ingresso / uscita")}${card("Euro totali", eur(C_.totale.c, 3))}${card("Budget giorno", P_.budget_giorno ? eur(P_.budget_giorno, 2) : "—")}</div>
      ${lineChart(d.serie.costo, { title: "Costo per giorno (€)", color: "#d8473a", fmt: (v) => num(v, 3) })}
      <table><tr><th>Voce GC</th><th>Importo</th></tr>${Object.entries(C_.gc).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${num(v, 1)}</td></tr>`).join("")}</table>`,
    "Memoria": () => `<pre>${esc(d.memoria || "(vuota)")}</pre><p class="muted">Sola lettura: la aggiorna il Talent Manager dopo le post-mortem.</p>`,
  };
  tabs.innerHTML = Object.keys(T_).map((t, i) => `<button class="${i ? "" : "on"}">${t}</button>`).join("");
  const sel = (n) => { body.innerHTML = T_[n](); tabs.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.textContent === n)); };
  tabs.querySelectorAll("button").forEach((b) => (b.onclick = () => sel(b.textContent)));
  sel("Panoramica");
  dlg.classList.remove("hidden"); beep(760);
}

// la CSP vieta gli attributi style nell'HTML generato: le larghezze passano da data-w e CSSOM
function applyWidths(root) { root.querySelectorAll("[data-w]").forEach((e) => (e.style.width = (+e.dataset.w || 0) + "px")); }

// ---------------------------------------------------------------- pannelli
const table = (rows, cols) => !rows || !rows.length ? "<p class='muted'>Nessun dato.</p>" :
  "<table><tr>" + cols.map((c) => `<th>${esc(c[1])}</th>`).join("") + "</tr>" +
  rows.map((r) => "<tr>" + cols.map((c) => `<td>${c[2] ? c[2](r[c[0]], r) : esc(r[c[0]])}</td>`).join("") + "</tr>").join("") + "</table>";
const tag = (v) => `<span class="tag ${esc(v)}">${esc(v)}</span>`;
let peopleSort = ["punteggio", -1];

const PANELS = {
  async persone() {
    const rows = await api("/api/people");
    const [k, dir] = peopleSort;
    rows.sort((a, b) => ((a[k] ?? -1e9) > (b[k] ?? -1e9) ? 1 : -1) * dir);
    const H = (key, label) => `<th class="sort" data-sort="${key}">${label}${k === key ? (dir < 0 ? " ▼" : " ▲") : ""}</th>`;
    return ["Persone e statistiche", `<p class="muted">Clic su un'intestazione per ordinare, su un nome per la scheda completa.</p><table class="people"><tr>
      ${H("nome", "Nome")}${H("grado", "Grado")}${H("ufficio", "Ufficio")}${H("punteggio", "Punteggio")}${H("brier", "Brier")}${H("giuste", "Prev. giuste")}${H("gc", "GC")}${H("differito", "Differito")}${H("costo", "Costo €")}${H("errori", "Errori")}</tr>
      ${rows.map((r) => `<tr><td><a href="#" data-agent="${r.id}">${esc(r.nome)}</a><div class="muted">${esc(r.ruolo)}</div></td><td>${esc(r.grado_nome)}<div class="muted">#${esc(r.rank_grado)}</div></td>
      <td>${esc(TIER_NAME[r.ufficio] || "—")}</td><td>${r.punteggio == null ? "—" : `<span class="bar" data-w="${Math.round(r.punteggio * 70)}"></span> ${num(r.punteggio, 2)}`}</td>
      <td>${r.brier == null ? "—" : num(r.brier, 3)}</td><td>${r.giuste}/${r.previsioni}</td><td class="gold">${num(r.gc, 0)}</td><td>${num(r.differito, 0)}</td><td>${num(r.costo, 3)}</td><td>${r.errori}</td></tr>`).join("")}</table>`];
  },
  async riunioni() {
    const ms = await api("/api/meetings");
    if (!ms.length) return ["Sala riunioni", "<p class='muted'>Nessuna riunione ancora. Si convocano da sole: allarme su un pod, allocazione mensile, fascicolo che passa il cancello.</p>"];
    return ["Sala riunioni — chi vuole avere ragione deve averla nei fatti", ms.map((m) => {
      const t = m.transcript || { posizioni: {}, repliche: {}, pesi: {} };
      const rows = Object.keys(t.repliche || {}).map((a) => {
        const p0 = t.posizioni[a] || {}, p1 = t.repliche[a] || {};
        return `<tr><td><b>${esc(ENT[a]?.a.name || a)}</b></td><td>${tag(p0.posizione)} ${esc(p0.argomento)}</td><td>${tag(p1.posizione_finale)} ${esc(p1.replica)}</td><td>${num(p1.fiducia, 2)}</td><td>${num(t.pesi?.[a], 2)}</td><td>${m.outcome ? (m.outcome.gc?.[a] >= 0 ? `<span class="pos">+${num(m.outcome.gc[a], 1)}</span>` : `<span class="neg">${num(m.outcome.gc?.[a], 1)}</span>`) : "<span class='muted'>in attesa</span>"}</td></tr>`;
      }).join("");
      return `<div class="meet"><div class="mh"><b>#${m.id} ${esc(m.title)}</b> ${tag(m.kind)} ${tag(m.status)} <span class="muted">${esc(day(m.ts))} · ${esc(m.reason)}</span></div>
        <p>Decisione del codice: <b>${esc(m.decision || "—")}</b>${m.outcome ? ` · I fatti: aveva ragione «<b>${esc(m.outcome.giusta)}</b>»` : ` · si risolve dal ${esc(m.resolve_after || "")}`}</p>
        <table><tr><th>Chi</th><th>Posizione</th><th>Replica</th><th>Fiducia</th><th>Peso (calibrazione)</th><th>GC</th></tr>${rows}</table></div>`;
    }).join("")];
  },
  async report(dayArg) {
    const list = await api("/api/reports");
    const r = await api("/api/report/" + (dayArg || list[0] || "oggi"));
    const s = r.societa, b = r.edificio;
    return ["Report " + r.giorno, `<div class="reports">${list.map((d) => `<a href="#" data-report="${d}" class="${d === r.giorno ? "on" : ""}">${d}</a>`).join("")}</div>
      <div class="kgrid">${card("NAV", eur(s.nav), "rendimento " + pct(s.rendimento, 2))}${card("Rischio", r.rischio.semaforo, r.rischio.allarmi.length + " allarmi")}
      ${card("Budget oggi", eur(r.budget.spent_today, 3), "su " + eur(r.budget.daily_cap, 2))}${card("Edificio", "Liv. " + b.livello, b.nome)}
      ${card("Gateway", (r.gateway.accettato || 0) + (r.gateway.eseguito || 0) + " / " + (r.gateway.respinto || 0), "accettati / respinti")}${card("Posta", r.posta_aperta, "grandi richieste aperte")}</div>
      <h3>Correzioni proposte (${r.correzioni.length})</h3>${r.correzioni.map((c) => `<div class="fix g${c.gravita}"><b>[${c.gravita}] ${esc(c.cosa)}</b><p class="muted">${esc(c.evidenza)}</p><p>→ ${esc(c.azione)} <span class="b">${esc(c.chi)}</span></p></div>`).join("") || "<p class='muted'>Nessuna correzione necessaria.</p>"}
      <h3>Pod</h3>${table(r.pod, [["nome", "Pod"], ["capitale", "Capitale", (v) => pct(v)], ["giorni", "Giorni"], ["sharpe", "Sharpe", (v, x) => v == null ? "<span class='muted'>&lt;30 gg</span>" : num(v, 2) + (x.sharpe_ci90 ? ` <span class="muted">[${x.sharpe_ci90.map((y) => num(y, 2)).join("; ")}]</span>` : "")], ["alpha_netto_eur", "Alpha netto", (v) => v == null ? "benchmark" : eur(v)]])}
      <h3>Persone</h3>${table(r.persone, [["nome", "Nome"], ["grado", "Grado"], ["punteggio", "Punteggio", (v) => v == null ? "—" : num(v, 3)], ["gc", "GC", (v) => num(v, 0)], ["differito", "Differito", (v) => num(v, 0)], ["costo", "Costo €", (v) => num(v, 3)]])}
      <h3>Riunioni</h3>${table(r.riunioni, [["titolo", "Riunione"], ["decisione", "Decisione"], ["stato", "Stato", tag]])}`];
  },
  async edificio() {
    const w = await api("/api/world"), b = w.edificio;
    return ["Edificio e servizi", `<p>Il livello cresce con il <b>massimo storico</b> del valore di GERVA Capital e non scende mai: un drawdown congela la crescita, non toglie i servizi a nessuno.</p>
      <div class="kgrid">${card("Livello", `${b.livello} · ${esc(b.nome)}`)}${card("NAV", eur(b.valore.nav), "rendimento " + pct(b.valore.rendimento, 2))}${card("Massimo storico", pct(b.valore.rendimento_massimo, 2), "determina il livello")}</div>
      ${table(b.servizi, [["nome", "Servizio"], ["soglia", "Si apre a", (v) => "+" + pct(v, 1)], ["attivo", "Stato", (v) => v ? tag("attivo") : tag("in costruzione")]])}
      <p class="muted">Uffici per grado: Head e Manager → ufficio privato con finestra; Senior → ufficio a vetri; Analisti e Stagisti → open space (più arredato dal grado Analista Senior). Il Capo ha la suite d'angolo con vista panoramica. I Gerva-Coin maturati aggiungono trofei (≥100), acquario (≥300), quadro d'oro (≥1000).</p>`];
  },
  async org() {
    const t = await api("/api/org");
    const node = (n) => `<li><a href="#" data-agent="${n.id}">${esc(n.name)}</a> <span class="muted">${esc(n.role)} · ${esc(n.grade)}</span>${n.kind === "open" ? " " + tag("aperta") : n.kind === "code" ? ' <span class="tag">automa</span>' : ""}${n.children.length ? "<ul>" + n.children.map(node).join("") + "</ul>" : ""}</li>`;
    return ["Organigramma", `<div class="tree"><ul>${node(t)}</ul></div>`];
  },
  async compiti(id) {
    const cmds = await api("/api/commands");
    id = id || (cmds[0] && cmds[0].id);
    let h = table(cmds, [["id", "#"], ["text", "Ordine", (v, r) => `<a href="#" data-cmd="${r.id}">${esc(v.slice(0, 80))}</a>`], ["status", "Stato", tag]]);
    if (id) {
      const t = await api("/api/tasks/" + id);
      const node = (n) => `<li><b>${esc(ENT[n.assignee]?.a.name || n.assignee)}</b> ← ${esc(ENT[n.assigner]?.a.name || n.assigner)}: ${esc(n.title)} ${tag(n.status)}${n.result ? `<div class="muted">${esc(typeof n.result === "string" ? n.result : (n.result.risultato || n.result.sintesi || JSON.stringify(n.result))).slice(0, 300)}</div>` : ""}${n.children.length ? "<ul>" + n.children.map(node).join("") + "</ul>" : ""}</li>`;
      h += `<h3>Ordine #${id}</h3><p>${esc(t.ordine ? t.ordine.text : "")}</p>${t.ordine && t.ordine.answer ? `<pre>${esc(t.ordine.answer)}</pre>` : ""}<div class="tree"><ul>${t.compiti.map(node).join("") || '<li class="muted">Il Capo sta leggendo…</li>'}</ul></div>`;
    }
    return ["Albero dei compiti", h];
  },
  async posta() {
    const items = await api("/api/mailbox");
    if (!items.length) return ["Posta del Capo", "<p class='muted'>Nessuna grande richiesta: il resto lo decide la società.</p>"];
    return ["Posta del Capo — solo grandi richieste", items.map((m) => `<div class="mail"><b>${esc(m.title)}</b> ${tag(m.status)} <span class="tag">${esc(m.categoria)}</span><p>${esc(m.why)}</p>
      <p><b>Raccomandazione:</b> ${esc(m.recommendation)}</p><p><b>Default sicuro se non rispondi:</b> ${esc(m.safe_default)}</p>
      ${m.status === "aperta" ? m.options.map((o) => `<button data-mail="${m.id}" data-choice="${esc(o)}">Scegli: ${esc(o)}</button>`).join("") + `<button class="ghost" data-mail="${m.id}" data-choice="__rimanda__">Rimanda</button>` : `<p class="muted">Scelta: ${esc(m.choice || "rimandata (vale il default)")}</p>`}</div>`).join("")];
  },
  async pod() {
    const d = await api("/api/desk"), z = d.pod_zero, t = Object.entries(d.targets || {}).sort((x, y) => y[1] - x[1]);
    const tot = t.reduce((a, [, v]) => a + v, 0);
    return ["Desk: le posizioni che i capi desk propongono per il conto",
      `<p class="muted">I capi desk propongono, il codice valida (peso massimo per titolo e in totale), GERVA-Q esegue sul conto. Non esistono più capitali separati.</p>` +
      (t.length ? `<div class="kgrid">${card("Proposte del", esc(d.data || "—"))}${card("Titoli", t.length)}${card("Totale sul conto", pct(tot, 1))}</div>` +
        table(t.map(([k, v]) => ({ k, v, desk: Object.entries(d.per_desk || {}).filter(([, m]) => m[k]).map(([n]) => n.replace("pod_", "")).join(", ") })),
          [["k", "Titolo"], ["v", "Peso sul conto", (v) => pct(v, 2)], ["desk", "Proposto da"]])
        : `<p class="muted">Nessuna proposta ancora: i capi desk lavorano ogni mattina.</p>`) +
      `<h3>Modello GERVA-Q (sola lettura)</h3>${z.disponibile ? `<div class="kgrid">${card("Dati al", esc(z.dati_al))}${card("Lorda target", pct(z.lorda))}${card("Quota crypto", pct(z.quota_crypto))}</div>` +
        table(Object.entries(z.pesi).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ k, v })), [["k", "Strumento"], ["v", "Peso sul NAV", (v) => pct(v, 2)]]) : `<p class="muted">GERVA-Q non trovato (${esc(z.percorso)}).</p>`}`];
  },
  async ricerca() {
    const d = await api("/api/research");
    return ["Ricerca e approvazioni", `<div class="kgrid">${card("Prove registrate", d.prove.n_trials, "N del Deflated Sharpe")}${card("Con Sharpe", d.prove.n_with_sharpe)}</div>` +
      table(d.fascicoli, [["title", "Fascicolo"], ["stage", "Fase", tag], ["gate", "Cancello", (v) => v ? (v.passa ? "passa" : "non passa") + (v.deflated ? ` · DSR ${num(v.deflated.dsr, 3)}` : "") : "—"], ["validation", "Validazione", (v) => v ? esc(v.esito) : "—"], ["decision", "Comitato", (v) => v && v.esito ? esc(v.esito) : "—"]])];
  },
  async gateway() {
    const d = await api("/api/pods");
    return ["Gateway di Esecuzione", "<p class='muted'>Il portale non invia ordini. Arrivano solo dai Capi Pod e passano tutti dai controlli.</p>" +
      table(d.ordini, [["ts", "Quando", (v) => esc((v || "").slice(5, 16).replace("T", " "))], ["pod", "Pod"], ["side", "Lato"], ["qty", "Qtà", (v) => num(v, 4)], ["instrument", "Strumento"], ["status", "Esito", tag], ["reject", "Motivo", (v) => esc(v || "")]])];
  },
  async impostazioni() {
    const d = await api("/api/settings"), S_ = d.impostazioni;
    const row = (k, v, kind = "set") => `<div class="setrow"><label for="set-${esc(kind)}-${esc(k)}">${esc(k)}</label><input id="set-${esc(kind)}-${esc(k)}" data-k="${esc(k)}" data-kind="${kind}" value="${esc(JSON.stringify(v))}"><button data-save="${esc(k)}" data-savekind="${kind}">Salva</button><em class="err" role="status"></em></div>`;
    const flat = (o, p = "") => Object.entries(o).flatMap(([k, v]) => (v && typeof v === "object" && !Array.isArray(v) ? flat(v, p + k + ".") : [[p + k, v]]));
    return ["Impostazioni (solo Andrea)", `<p>Ogni modifica va nell'audit log. Autonomia: <b>${d.budget.days_left == null ? "∞" : num(d.budget.days_left, 1) + " giorni"}</b> al ritmo di ${eur(d.budget.pace_eur_day, 3)}/giorno.</p>
      <button id="strikebtn" class="${S_["firm.strike"] ? "" : "danger"}">${S_["firm.strike"] ? "Riprendi la società" : "Sciopero (ferma gli agenti)"}</button> <button class="danger" id="killbtn">${STATE && STATE.kill ? "Togli il KILL" : "KILL"}</button>
      <h3>Budget, modelli, rilascio, pod, economia</h3>${Object.entries(S_).filter(([k]) => k !== "firm.mode" && k !== "firm.strike").map(([k, v]) => row(k, v)).join("")}
      <h3>Limiti di rischio</h3>${flat(d.limiti).map(([k, v]) => row(k, v, "risk")).join("")}<p class="muted">LIVE è bloccato: servono i cancelli 13-15 della sfida e la firma dei titolari.</p>`];
  },
};

let lastFocus = null;
function showWin(id) {
  const w = document.getElementById(id);
  if (w.classList.contains("hidden")) lastFocus = document.activeElement;
  w.classList.remove("hidden");
  w.querySelector(".x")?.focus({ preventScroll: true });
}
function closeWin(id) {
  const w = document.getElementById(id);
  if (w.classList.contains("hidden")) return;
  w.classList.add("hidden");
  if (lastFocus && document.body.contains(lastFocus)) lastFocus.focus({ preventScroll: true });
}
async function openPanel(name, arg) {
  let title, html;
  try { [title, html] = await PANELS[name](arg); }
  catch (err) { title = "Errore"; html = `<p class="err">Non riesco a caricare questo pannello: ${esc(err.message)}</p>`; }
  document.getElementById("pnl-title").textContent = title;
  document.getElementById("pnl-body").innerHTML = html;
  applyWidths(document.getElementById("pnl-body"));
  const p = document.getElementById("panel"); p.dataset.name = name; showWin("panel");
  document.querySelectorAll("#menu button").forEach((b) => b.classList.toggle("on", b.dataset.panel === name));
}
document.querySelectorAll("#menu button[data-panel]").forEach((b) => (b.onclick = () => { beep(600); openPanel(b.dataset.panel); }));
document.querySelectorAll("[data-close]").forEach((b) => (b.onclick = () => closeWin(b.dataset.close)));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") ["dialog", "panel"].forEach(closeWin); });
document.getElementById("sound").onclick = (e) => { soundOn = !soundOn; e.target.textContent = "Suoni " + (soundOn ? "ON" : "OFF"); beep(880); };

document.getElementById("pnl-body").addEventListener("click", async (e) => {
  const t = e.target.closest("[data-agent],[data-cmd],[data-mail],[data-save],[data-report],[data-sort],#strikebtn,#killbtn");
  if (!t) return;
  e.preventDefault();
  try {
    if (t.dataset.agent) openAgent(t.dataset.agent);
    if (t.dataset.cmd) openPanel("compiti", +t.dataset.cmd);
    if (t.dataset.report) openPanel("report", t.dataset.report);
    if (t.dataset.sort) { peopleSort = [t.dataset.sort, peopleSort[0] === t.dataset.sort ? -peopleSort[1] : -1]; openPanel("persone"); }
    if (t.dataset.mail) { await api("/api/mailbox/" + t.dataset.mail, { method: "POST", body: JSON.stringify({ choice: t.dataset.choice }) }); openPanel("posta"); refreshState(); }
    if (t.dataset.save) {
      const inp = document.querySelector(`input[data-k="${CSS.escape(t.dataset.save)}"][data-kind="${CSS.escape(t.dataset.savekind)}"]`);
      const err = t.parentElement.querySelector(".err"); err.textContent = "";
      let value;
      try { value = JSON.parse(inp.value); } catch (_) { err.textContent = "valore non valido: numero, true/false o testo tra virgolette"; return; }
      try {
        await api("/api/settings", { method: "POST", body: JSON.stringify({ key: t.dataset.save, value, kind: inp.dataset.kind }) });
        t.textContent = "Salvato"; setTimeout(() => (t.textContent = "Salva"), 2000); refreshState();
      } catch (e2) { err.textContent = e2.message; }
      return;
    }
    if (t.id === "strikebtn") { await api("/api/strike", { method: "POST", body: JSON.stringify({ on: t.textContent.startsWith("Sciopero") }) }); openPanel("impostazioni"); refreshState(); refreshWorld(); }
    if (t.id === "killbtn") {
      const on = !(STATE && STATE.kill);
      if (on && !t.dataset.armed) {                 // conferma in due tempi, dentro la pagina
        t.dataset.armed = "1"; t.textContent = "Conferma: il Gateway rifiuterà ogni ordine";
        setTimeout(() => { if (document.body.contains(t)) { delete t.dataset.armed; t.textContent = "KILL"; } }, 5000);
        return;
      }
      await api("/api/kill", { method: "POST", body: JSON.stringify({ on }) }); await refreshState(); openPanel("impostazioni");
    }
  } catch (err) { toast(err.message); }
});

// ---------------------------------------------------------------- barra di comando
document.getElementById("cmd").addEventListener("submit", async (e) => {
  e.preventDefault();
  const inp = document.getElementById("cmdtext"), text = inp.value.trim();
  if (!text) return;
  let r;
  try { r = await api("/api/command", { method: "POST", body: JSON.stringify({ text }) }); }
  catch (err) { toast("Ordine non inviato: " + err.message); return; }
  inp.value = "";
  ENT.capo?.say("Ricevuto, Andrea: " + text.slice(0, 60), 4000);
  beep(880, 0.08);
  await openPanel("compiti", r.id);
  let n = 0;
  const poll = setInterval(async () => {
    const p = document.getElementById("panel");
    if (++n > 60 || p.classList.contains("hidden") || p.dataset.name !== "compiti") return clearInterval(poll);
    const [, html] = await PANELS.compiti(r.id); document.getElementById("pnl-body").innerHTML = html; applyWidths(document.getElementById("pnl-body"));
  }, 2000);
});

// ---------------------------------------------------------------- avvio
(function logo() {
  const c = document.getElementById("logo"), x = c.getContext("2d");
  x.imageSmoothingEnabled = false; emblem(x, 1, 1, 2);
  const fav = document.createElement("link"); fav.rel = "icon"; fav.href = c.toDataURL(); document.head.appendChild(fav);
})();
document.fonts.load("11px VT323").finally(async () => {
  resizeCanvas();
  await refreshState(); await refreshWorld();
  requestAnimationFrame(render);
  connectWS();
});
setInterval(refreshState, 6000);
setInterval(refreshWorld, 15000);
