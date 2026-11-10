// Operational data only. No random/demo fallback and no annualized claims from NAV ticks.
LABEL.terminal = 'Terminale';
LABEL.panoramica = 'Attività';
function terminalPlot(points, key, title, format, cls = '') {
  if (points.length < 2) return `<div class="terminal-empty">Servono almeno due osservazioni per ${esc(title.toLowerCase())}.</div>`;
  const values = points.map(p => p[key]), lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || Math.max(Math.abs(lo) * .01, .01);
  const x = i => 64 + i / (points.length - 1) * 816, y = v => 190 - (v - lo) / span * 160;
  const d = points.map((p,i) => `${i ? 'L' : 'M'}${x(i).toFixed(2)},${y(p[key]).toFixed(2)}`).join(' ');
  return `<svg class="terminal-plot ${cls}" viewBox="0 0 920 230" role="img" aria-label="${esc(title)}"><title>${esc(title)}: ${esc(format(values[values.length-1]))}</title>` +
    [0,.5,1].map(f => `<line x1="64" x2="880" y1="${190-f*160}" y2="${190-f*160}"/><text x="54" y="${194-f*160}" text-anchor="end">${esc(format(lo+f*span))}</text>`).join('') +
    `<path class="plot-area" d="${d} L880,190 L64,190 Z"/><path class="plot-line" d="${d}"/>` +
    points.map((p,i) => `<circle cx="${x(i)}" cy="${y(p[key])}" r="4"><title>${esc(p.t)} · ${esc(format(p[key]))}</title></circle>`).join('') +
    `<text x="64" y="220">${esc(points[0].t)}</text><text x="880" y="220" text-anchor="end">${esc(points[points.length-1].t)}</text></svg>`;
}
PANELS.terminal = async () => {
  const d = await api('/api/terminal'), h = d.health, up = h.parti.filter(p => p.ok || p.stato === 'riposo').length;
  const status = h.ok ? 'Servizi operativi' : 'Servizi da verificare';
  return ['Terminale <em>quant</em>',
    `<div class="terminal-mast"><span>GERVA / CONTROL ROOM</span><span class="${h.ok ? 'pos' : 'gold'}">● ${status} · ${up}/${h.parti.length}</span><span>Snapshot ${esc(when(d.asof))} UTC <button class="btn" id="terminal-refresh">Aggiorna</button></span></div>` +
    `<div class="kgrid terminal-kpis">${card('NAV · IBKR',eur(d.nav),'Ultima osservazione disponibile')}${card('Variazione NAV',pct(d.change),'Include eventuali flussi di capitale')}${card('Flessione massima NAV',pct(d.max_drawdown),'Dal massimo osservato · non annualizzata')}${card('Storico disponibile',num(d.observations,0)+' giorni','Osservazioni giornaliere UTC')}</div>` +
    `<div class="terminal-layout"><div class="terminal-main"><section class="lg card"><div class="terminal-section"><h3>Valore del conto</h3><span>IBKR / EUR / PAPER</span></div>${terminalPlot(d.curve,'nav','Valore del conto',v=>num(v,0))}<p class="muted">${esc(d.note)}</p></section>` +
    `<section class="lg card"><div class="terminal-section"><h3>Distanza dal massimo</h3><span>UNDERWATER / NAV</span></div>${terminalPlot(d.curve,'drawdown','Flessione NAV',v=>pct(v,1),'underwater')}</section></div>` +
    `<aside class="terminal-rail"><section class="lg card"><div class="terminal-section"><h3>Infrastruttura</h3><span>HEALTH</span></div>` + h.parti.map(p=>`<div class="terminal-service"><div><b>${esc(p.nome)}</b><span class="${p.ok?'pos':p.stato==='riposo'?'muted':'gold'}">${p.ok?'OPERATIVO':esc((p.breve||p.stato).toUpperCase())}</span></div><p>${p.eta_s == null ? 'Nessun segnale' : `${Math.max(0,Math.round(p.eta_s))} s dall’ultimo segnale · soglia ${p.soglia_s} s`}</p>${!p.ok && p.motivo ? `<small>${esc(p.motivo)}</small>` : ''}</div>`).join('') +
    `</section><section class="lg card"><div class="terminal-section"><h3>Ricerca</h3><span>TRIAL REGISTRY</span></div>${table(d.trials,[['family','Famiglia'],['status','Stato'],['n','Prove']])}<a class="terminal-link" href="#/tecniche">Apri strategie e fonti ↗</a></section>` +
    `<section class="lg card"><h3>Mandati operativi</h3><p><b>Ricerca</b> · ipotesi e test fuori campione</p><p><b>Validazione</b> · verifica indipendente</p><p><b>Portfolio</b> · rischio aggregato e costi</p><p><b>Operations</b> · dati, connessioni, riconciliazione</p><p class="muted">Responsabilità del processo; nessuna nuova autorità di trading.</p></section></aside></div>` +
    `<section class="lg card"><div class="terminal-section"><h3>Registro incidenti</h3><span>ULTIMI 8 EVENTI</span></div>${table(d.incidents,[['ts','Ora UTC',v=>esc(when(v))],['actor','Servizio'],['message','Diagnosi']])}</section>` +
    `<details class="terminal-data"><summary>Dati osservati · tabella accessibile</summary>${table(d.curve,[['t','Giorno UTC'],['nav','NAV EUR',v=>eur(v,2)],['drawdown','Flessione',v=>pct(v,2)]])}</details>`];
};
AFTER.terminal = () => { document.getElementById('terminal-refresh').onclick = () => render('terminal',null,true); };
let terminalBusy = false;
setInterval(async () => {
  if (CUR.page !== 'terminal' || document.hidden || terminalBusy) return;
  terminalBusy = true;
  try { await render('terminal',null,true); } finally { terminalBusy = false; }
},30000);
