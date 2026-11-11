/* Imposta il tema prima del primo disegno (script classico: la CSP non ammette script inline).
   Ordine: scelta salvata dall'utente, poi preferenza del sistema, poi scuro. */
(function () {
  var theme = null;
  try { theme = window.localStorage.getItem('gerva.dash.theme'); } catch (e) { theme = null; }
  if (theme !== 'light' && theme !== 'dark') {
    var prefersLight = false;
    try { prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches; } catch (e) { prefersLight = false; }
    theme = prefersLight ? 'light' : 'dark';
  }
  document.documentElement.setAttribute('data-theme', theme);
})();
