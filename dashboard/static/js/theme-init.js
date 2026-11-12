/* Imposta tema e livello prima del primo disegno (script classico: la CSP non ammette script inline).
   Il tema scuro è il predefinito; il chiaro vale solo se l'utente lo ha scelto. */
(function () {
  var theme = null;
  var level = null;
  var glass = null;
  try { theme = window.localStorage.getItem('gerva.dash.theme'); level = window.localStorage.getItem('gerva.dash.level'); glass = window.localStorage.getItem('gerva.dash.glass'); } catch (e) { theme = null; }
  var root = document.documentElement;
  root.setAttribute('data-theme', theme === 'light' ? 'light' : 'dark');
  if (level === 'esperto' || level === 'terminale') root.setAttribute('data-level-init', level);
  if (glass === 'off' || glass === 'auto-off') root.classList.add('lite');            /* vetro leggero: scelto o misurato all'ultimo avvio */
  /* lo smusso che rifrange usa un filtro SVG nello sfondo: solo dove il browser lo accetta */
  try { if (window.CSS && CSS.supports('backdrop-filter', 'url(#gerva-lens)') && !/jsdom/i.test(navigator.userAgent)) root.classList.add('refract'); } catch (e) { /* senza: sfocatura corta */ }
})();
