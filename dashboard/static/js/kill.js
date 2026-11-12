// Comando KILL: finestra di conferma con token e parola "KILL", poi POST /api/v1/kill con l'header X-Gerva-Token.
// Il token è digitato dall'utente e vive solo nel campo e nella richiesta: non va in localStorage, cookie o URL,
// e il campo viene svuotato appena la richiesta parte o la finestra si chiude.

const KILL_URL = 'api/v1/kill';
const WORD = 'KILL';

let result = null;            // esito dell'ultimo tentativo: { ok, t, already } oppure { ok: false, error }
let onDone = () => {};
let els = null;
let enabled = true;          // false quando il server non ha il token: la finestra spiega, l'invio resta spento

export const lastKill = () => result;

function validate() {
  els.submit.disabled = !(enabled && els.token.value.length > 0 && els.confirm.value.trim() === WORD);
}

function say(text, tone = '') {
  els.msg.textContent = text;
  els.msg.dataset.tone = tone;
}

function wipe() {
  els.token.value = '';
  els.reason.value = '';
  els.confirm.value = '';
  say('');
  validate();
}

async function submit(event) {
  event.preventDefault();
  if (els.submit.disabled) return;
  const token = els.token.value;
  const reason = els.reason.value.trim();
  els.token.value = '';                       // da qui il token esiste solo nella variabile locale
  els.submit.disabled = true;
  els.cancel.disabled = true;
  say('Invio in corso…');
  try {
    const res = await fetch(KILL_URL, {
      method: 'POST',
      cache: 'no-store',
      headers: { 'X-Gerva-Token': token, 'Content-Type': 'application/json' },
      body: JSON.stringify(reason ? { reason } : {}),
    });
    let body = null;
    try { body = await res.json(); } catch (e) { body = null; }
    if (res.ok && body && body.ok) {
      result = { ok: true, t: body.t, already: body.already_active === true };
      els.dialog.close();
      onDone();
      return;
    }
    const why = res.status === 401 || res.status === 403
      ? 'Token non valido.'
      : (body && typeof body.error === 'string' ? `${body.error.charAt(0).toUpperCase()}${body.error.slice(1)}.` : `Il server ha risposto ${res.status}.`);
    result = { ok: false, error: why };
    say(`${why} Il KILL NON è stato attivato.`, 'error');
  } catch (e) {
    result = { ok: false, error: 'Server non raggiungibile.' };
    say('Server non raggiungibile. Il KILL NON è stato attivato: se serve, crea il file KILL a mano sul server.', 'error');
  } finally {
    els.cancel.disabled = false;
    validate();
    if (els.dialog.open) els.token.focus();
    onDone();
  }
}

export function initKill({ done }) {
  onDone = done || onDone;
  const byId = (id) => document.getElementById(id);
  els = {
    dialog: byId('kill-dialog'), form: byId('kill-form'), token: byId('kill-token'), reason: byId('kill-reason'),
    confirm: byId('kill-confirm'), msg: byId('kill-msg'), cancel: byId('kill-cancel'), submit: byId('kill-submit'),
  };
  if (!els.dialog) return;
  els.form.addEventListener('submit', submit);
  els.token.addEventListener('input', validate);
  els.confirm.addEventListener('input', validate);
  els.cancel.addEventListener('click', () => els.dialog.close());
  els.dialog.addEventListener('close', wipe);
  // Invio dentro il campo del token non invia: si passa alla parola di conferma
  els.token.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); els.confirm.focus(); } });
}

/** Il server dice se il comando è utilizzabile (token configurato): se no, «Attiva KILL» non si abilita mai. */
export function setKillEnabled(flag) {
  enabled = flag !== false;
  if (els) validate();
}

/** Anteprima degli effetti (quante posizioni, quale controvalore, che cosa non fa): la scrive chi conosce i dati. */
export function setKillPreview(nodes) {
  const box = document.getElementById('kill-preview');
  if (box) box.replaceChildren(...nodes);
}

export function openKill() {
  if (!els || !els.dialog || els.dialog.open) return;
  wipe();
  if (typeof els.dialog.showModal === 'function') els.dialog.showModal();
  else els.dialog.setAttribute('open', '');
  els.cancel.focus();                         // il fuoco parte da «Annulla»: un Invio distratto non fa nulla
}
