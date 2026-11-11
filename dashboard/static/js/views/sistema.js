// Sistema: battito del ciclo, salute dei componenti, requisiti per passare dal paper al reale, registro degli avvisi.

import { h, icon, fill } from '../dom.js';
import { card, chip, dataTable, empty, stat } from '../components.js';
import { bullet } from '../charts.js';
import { DASH, arr, fmtAge, fmtAgo, fmtDateTime, fmtDayTime, fmtDuration, fmtNum, fmtUnit, num, obj, parseTs, str } from '../format.js';
import { alertLevel, componentStatus, isBacktest, staleLimit } from '../model.js';

export function mount(root) {
  let ctx = null;

  const band = h('section', { class: 'card tiles span-12', 'aria-label': 'Stato del ciclo' });

  const compCard = card({ title: 'Componenti', cls: 'order-1', flush: true, what: 'I pezzi di cui è fatto il sistema (dati, esecuzione, archivio…) e se stanno funzionando. «Latenza» è il tempo di risposta; «Ultimo OK» dice da quanto tempo quel pezzo ha risposto correttamente l\'ultima volta.' });
  const compTable = dataTable({
    caption: 'Salute dei componenti',
    emptyTitle: 'Nessun componente nello snapshot',
    columns: [
      { key: 'name', label: 'Componente', sort: (r) => str(r.name), cell: (r) => h('div', { class: 'cell-id cell-id--stack' }, h('span', { class: 'cell-id__main', text: str(r.name) || DASH }), str(r.detail).trim() ? h('span', { class: 'cell-id__name', text: str(r.detail) }) : null) },
      { key: 'status', label: 'Stato', sort: (r) => ({ down: 0, error: 0, degraded: 1, warn: 1, ok: 2 }[str(r.status).toLowerCase()] ?? 3), cell: (r) => chip(componentStatus(r.status)) },
      { key: 'latency', label: 'Latenza', num: true, sort: (r) => num(r.latency_ms), cell: (r) => (num(r.latency_ms) == null ? null : `${fmtNum(r.latency_ms, 0)} ms`) },
      {
        key: 'last_ok', label: 'Ultimo OK', num: true, hide: 'sm', sort: (r) => parseTs(r.last_ok),
        cell: (r) => { const t = parseTs(r.last_ok); return t == null ? null : h('span', { title: fmtDateTime(t), text: fmtAge(r.last_ok, ctx.now) }); },
      },
    ],
  });
  compCard.body.append(compTable.el);

  const gateCard = card({ title: 'Dal paper al reale', cls: 'span-5 order-2', what: 'Il fondo passa al denaro vero solo quando tutti questi requisiti sono soddisfatti. Li verifica il codice sui dati del conto di prova: non sono opinioni. Uno solo non soddisfatto e si resta in paper.', method: 'Cancelli numerici valutati a ogni ciclo (gerva/live/gates.py). «Da calcolare» = il confronto richiede la replica del backtest.' });

  const logCard = card({ title: 'Registro degli avvisi', cls: 'order-3', flush: true, what: 'Tutto ciò che il motore ha segnalato, dal più recente. «Info» è solo una notizia, «Attenzione» merita uno sguardo, «Critico» richiede di capire che cosa è successo.' });
  const logTable = dataTable({
    caption: 'Avvisi del motore, dal più recente',
    sort: { key: 't', dir: -1 },
    emptyTitle: 'Nessun avviso',
    emptyHint: 'Il motore non ha segnalato nulla.',
    columns: [
      {
        key: 't', label: 'Ora', sort: (r) => parseTs(r.t),
        cell: (r) => { const t = parseTs(r.t); return t == null ? null : h('time', { class: 'num', datetime: new Date(t).toISOString(), title: fmtDateTime(t), text: fmtDayTime(t) }); },
      },
      { key: 'level', label: 'Livello', sort: (r) => ({ critical: 0, error: 0, warn: 1, warning: 1, info: 2 }[str(r.level).toLowerCase()] ?? 3), cell: (r) => chip(alertLevel(r.level), { compact: true }) },
      { key: 'msg', label: 'Messaggio', cls: 'is-wrap', cell: (r) => str(r.msg) },
    ],
  });
  logCard.body.append(logTable.el);

  root.append(h('div', { class: 'grid' }, band, h('div', { class: 'col span-7' }, compCard.el, logCard.el), gateCard.el));

  function fillBand() {
    const { snap, health } = ctx;
    const sys = obj(snap.system);
    const meta = obj(snap.meta);
    const hb = num(sys.heartbeat_age_s);
    const late = hb != null && hb > staleLimit(meta);
    const asOf = parseTs(meta.as_of);
    const source = obj(health).snapshot_source;
    const count = (v) => (num(v) == null ? null : fmtNum(v, 0));
    fill(band, h('div', { class: 'tiles__grid tiles__grid--5' },
      stat({
        label: 'Battito del ciclo', value: hb == null ? null : fmtAgo(hb),
        sub: hb == null ? 'non riportato' : chip(late ? { label: 'In ritardo', kind: 'warn', icon: 'warn' } : { label: 'Regolare', kind: 'ok', icon: 'check' }),
        hint: 'Tempo trascorso dall\'ultimo giro completo del motore',
        explain: 'Da quanto tempo il motore ha completato l\'ultimo giro. Se cresce troppo, il motore si è fermato.',
      }),
      stat({ label: 'In funzione da', value: num(sys.uptime_s) == null ? null : fmtDuration(sys.uptime_s), sub: num(sys.uptime_s) == null ? 'non riportato' : 'dall\'ultimo avvio', explain: 'Da quanto il motore gira senza interruzioni.' }),
      stat({ label: 'Riavvii nelle 24 ore', value: count(sys.restarts_24h), cls: num(sys.restarts_24h) > 0 ? 'stat--warn' : '', explain: 'Quante volte è ripartito oggi. Zero è il normale.' }),
      stat({ label: 'Errori e avvisi nelle 24 ore', value: count(sys.errors_24h), cls: num(sys.errors_24h) > 0 ? 'stat--warn' : '', explain: 'Segnalazioni di oggi: i dettagli sono nel registro in fondo.' }),
      stat({
        label: 'Ultimo snapshot', value: asOf == null ? null : fmtDayTime(asOf),
        sub: source === 'demo' ? 'esempio dimostrativo del server' : source === 'file' ? 'file scritto dal motore' : null,
        explain: 'Quando il motore ha scritto i dati che stai leggendo.',
      })));
  }

  function fillGates() {
    const gates = arr(ctx.snap.gates);
    if (!gates.length) {
      gateCard.setSub('');
      fill(gateCard.body, empty('Nessun requisito nello snapshot', 'I cancelli per il passaggio al reale non sono stati pubblicati.'));
      return;
    }
    const done = gates.filter((g) => g.ok === true).length;
    gateCard.setSub(done === gates.length
      ? 'Tutti i requisiti sono soddisfatti: il passaggio al reale è possibile.'
      : 'Si resta in paper finché tutti i requisiti non sono soddisfatti.');
    fill(gateCard.body,
      h('div', { class: 'gates__summary' },
        h('span', { class: 'gates__count' }, h('strong', { class: 'num', text: `${done} di ${gates.length}` }), ' requisiti soddisfatti'),
        bullet({ ratio: done / gates.length, kind: 'ok', label: 'Requisiti soddisfatti', text: `${done} di ${gates.length}` })),
      h('ul', { class: 'gates' }, gates.map((g) => {
        const ok = g.ok === true;
        const v = num(g.value);
        const target = num(g.target);
        let progress = null;
        if (ok) progress = { ratio: 1, kind: 'ok' };
        else if (v != null && target != null && target > 0 && v >= 0) progress = v < target ? { ratio: v / target, kind: 'ok' } : { ratio: 1, kind: 'warn' };
        return h('li', { class: `gate ${ok ? 'gate--ok' : ''}`.trim() },
          icon(ok ? 'check-circle' : 'circle', 'gate__icon'),
          h('div', { class: 'gate__body' },
            h('div', { class: 'gate__name' }, h('span', { class: 'sr-only', text: ok ? 'Soddisfatto: ' : 'Non soddisfatto: ' }), str(g.name) || DASH),
            h('div', { class: 'gate__figures' },
              h('span', { class: 'num gate__value', text: v == null ? 'da calcolare' : fmtUnit(v, g.unit) }),
              h('span', { class: 'gate__target' }, 'soglia ', h('span', { class: 'num', text: target == null ? DASH : fmtUnit(target, g.unit) }))),
            progress ? bullet({ ratio: progress.ratio, kind: progress.kind, label: `Avanzamento di ${str(g.name)}` }) : null));
      })));
  }

  return {
    update(next) {
      ctx = next;
      const backtest = isBacktest(ctx.snap.meta);
      fillBand();
      compTable.render(arr(obj(ctx.snap.system).components), {
        emptyHint: backtest ? 'In backtest non c\'è un ciclo in esecuzione da sorvegliare.' : 'Il motore non ha ancora pubblicato lo stato dei componenti.',
      });
      fillGates();
      logTable.render(arr(ctx.snap.alerts));
    },
    summary(c) {
      const sys = obj(c.snap.system);
      const comps = arr(sys.components).map((x) => str(x.status).toLowerCase());
      const bad = comps.filter((x) => x && x !== 'ok').length;
      const gates = arr(c.snap.gates);
      const done = gates.filter((g) => g.ok === true).length;
      const hb = num(sys.heartbeat_age_s);
      const first = hb == null ? 'Il battito del ciclo non è riportato in questo snapshot' : hb > staleLimit(c.snap.meta) ? `Il ciclo è in ritardo: ultimo giro ${fmtAgo(hb)}` : `Il ciclo gira regolarmente (ultimo giro ${fmtAgo(hb)})`;
      return `${first}${comps.length ? `; ${bad ? `${bad} ${bad === 1 ? 'componente ha' : 'componenti hanno'} un problema` : 'tutti i componenti rispondono'}` : ''}${gates.length ? `; ${done} requisiti su ${gates.length} soddisfatti per passare al denaro reale` : ''}.`;
    },
  };
}
