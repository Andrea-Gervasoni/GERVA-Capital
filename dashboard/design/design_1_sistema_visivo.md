# Design 1 · Sistema visivo «vetro liquido» (direzione: nero, vetro spesso, colore brillante)

File: `tokens.glass.css` (solo proprietà personalizzate; scuro = `:root`, chiaro sotto `[data-theme="light"]`) e `specimen.html` (ricette e prova a occhio). Schermate in `scratchpad/shots/ds-*.png`.

## 1. Cinque principi
1. Il terminale è nero vero: il colore non decora, arriva da dietro (sei luci che derivano) e da ciò che porta un significato.
2. Il vetro è un materiale con spessore: sfoca e satura il fondo, ha un velo scuro dentro che tiene il testo in AA, luce in alto, ombra in basso, orlo speculare.
3. Ciò che galleggia (capsula in alto, binario/dock, avvisi) ha uno smusso che rifrange quello che gli scorre sotto; ciò che sta fermo (schede) no.
4. Una sola cifra eroe per schermata; ogni cifra è tabellare; verde, rosso e stati non stanno mai da soli (segno, freccia, icona, parola, tratto).
5. Il movimento dice una cosa per volta, a molla, e si spegne del tutto con «riduci movimento»; con «riduci trasparenza» restano superfici piene pensate così.

## 2. Mappa dei token (nome storico → nuovo valore, tema scuro; il chiaro è nel file)
| Nome | Prima | Ora | Nota |
|---|---|---|---|
| `--bg` | `#0b0d10` | `#000000` | sotto le luci `--aurora-1…6` (blu, indaco, viola, magenta, acqua, arancio) |
| `--surface` | `#121519` | `var(--glass-panel-bg)` = `rgba(13,15,26,.56)` | ora ha alfa: per intestazioni appiccicose e anelli dei punti usare `--surface-solid` `#10131d` |
| `--surface-2` / `-3` | `#181c21` / `#1f242b` | bianco al 6% / 11% | veli sopra il vetro (hover, selezione) |
| `--border` / `--border-strong` | `#252a31` / `#343a43` | bianco al 9% / 18% | filetti; per i campi `--border-control` (46%, ≥ 4,1:1) |
| `--text` / `-2` / `-3` | `#e9ecf0` `#aab1bb` `#7f8792` | `#f5f7fb` `#c5ccda` `#9ea8bc` | bianco freddo, niente grigi fangosi |
| `--accent` / `--accent-ink` / `--accent-soft` | `#3987e5` `#6ea8f7` 14% | `#3b94ff` `#86bdff` `rgba(6,30,76,.58)` | i «soft» sul nero sono veli **scuri** della stessa tinta |
| `--pos` / `--neg` | `#61d19a` `#f05f5a` | `#2ee59a` `#ff6f7b` | più `--pos-soft`, `--neg-soft`, `--glow-pos`, `--glow-neg` |
| `--s1…--s5` | blu, arancio, acqua, giallo, magenta | `#4794fd #eb6701 #12ad8c #bf8a11 #f34a99` | più `--s6 #07b332 --s7 #9a78fe --s8 #fd4a55`; stesse 8 famiglie, croma al massimo |
| `--warn*`, `--serious*`, `--crit*` | ambra / arancio / rosso | `#ffc02e` · `#ff8a3d` · `#e0263a` (pieno) | `--crit-mark #ff4d5e` per linee; nuovi `--safe*` (`#1fd68a`), `--on-warn` |
| `--bench`, `--grid`, `--axis`, `--scrim`, `--hatch` | pieni | `#8b96ab`, bianco 7,5% / 22%, nero 62%, bianco 8% | |
| `--shadow` | un'ombra | `var(--elev-3)` | scala `--elev-0…4` a strati |
| `--radius-s` / `--radius-m` | 4 / 6 | 10 / 16 | nuovi `--radius-xs 6`, `-l 24`, `-xl 28`, `-pill` |
| `--fs-*` | 11 12 13 14 16 20 26 44 | 11 12 14 15 17 24 32 `clamp(48,…,88)` | nuovo `--fs-page 28` |
| `--sp-1…8`, `--rail-w`, `--topbar-h`, `--modebar-h` | 4…32, 216, 52, 30 | invariati, 232, 64, 32 | nuovi `--sp-10/12/16`, `--pad-card`, `--gap-grid`, `--dock-h 68`, `--control-h 40` |
| `--font-ui` / `--font-num` / `--font-brand` | General Sans / sistema / Bodoni | sistema per primo, General Sans in coda / sistema / Bodoni | nuovi `--font-display` (`ui-rounded` per le cifre grandi), `--font-mono` |
| `--chart-*` | — | stessi nomi | cambiati: linea 2,25, barra r4, cella r7, area 0,30, `--chart-surface: --surface-solid`, `--chart-crit: --crit-mark` |

Nuove famiglie: `--glass-{panel,raised,chrome,sheet}-{tint,solid,bg,filter,fx}`, `--glass-sheen/rim/depth/hairline/lens-*`, `--blur-*`, `--sat-*`, `--blur-bleed`, `--lens-w`, `--gloss-*`, `--well-*`, `--thumb-*`, `--accent-grad/-glow/-fill`, `--kill-grad/-glow/-guard`, `--glow-*`, `--prov-{demo,sim,paper,real}-*`, `--seq-1…7`, `--div-1…9`, `--pnl-1…7` (ognuna con `-ink`), `--focus*`, `--dur-*`, `--ease-*`, `--stagger`, `--chart-series-6…8`, `--chart-dash-sim/-demo`, interruttori `--glass-on`, `--motion-on`, `--parallax`.

## 3. Ricette dei materiali (scuro)
| Materiale | Velo | Sfocatura · saturazione | Dove |
|---|---|---|---|
| Pannello `.glass` | 56% | 30 px · 190% | schede, sempre sul fondale |
| Rialzato `.glass--raised` | 52% | 36 px · 200% | eroe |
| Cromatura `.lensed` | 76% | 24 px · 200% + smusso 6 px | capsula in alto, binario, dock, avvisi |
| Foglio `.glass--sheet` | 84% | 28 px · 180% | popover, finestre |

- Pannello: `background: var(--glass-sheen), var(--glass-panel-bg)`; `backdrop-filter: var(--glass-panel-filter)`; `box-shadow: var(--glass-panel-fx)` (luce interna alta, ombra interna bassa, filetto esterno, ombre a strati); orlo = `::before` con `--glass-rim` mascherato a 1 px, più vivo in alto a sinistra.
- Cromatura: tre strati sotto il contenuto. `<i class="bd">` = sfocatura, più alto del corpo di `--blur-bleed` e ritagliato; `::after` = velo, luce radente e spessore; `::before` = anello di `--lens-w` con `backdrop-filter: var(--glass-lens-filter)` (filtro SVG `#gerva-lens`: rumore + spostamento) solo se `html.refract` (Chromium), altrimenti `--glass-lens-fallback`.
- Comandi: capsule. `background: var(--gloss-bg)`; primario `var(--gloss-over), var(--accent-grad)` con `--accent-glow`; KILL `var(--gloss-over), var(--kill-grad)` con collare a strisce `--kill-guard` (= apre la conferma, non invia). Premuto: scala 0,97 e `--gloss-edge-pressed`. Segmentato: binario `--well-*`, cursore `--thumb-*` che cambia posto **e larghezza**.

## 4. Scala tipografica
Eroe 48–88/600, tracking −0,045em, `--font-display`, bagliore `--glow-hero` (un `filter` sul contenitore) · Cifra chiave 32/600 · Pagina 28/600 · Statistica 24/600 · Sezione 17/600 · Guida 15 · Testo 14/1,5 · Didascalia 12 · Micro-etichetta 11/600 maiuscola +0,08em. Ogni cifra: `font-variant-numeric: var(--num-variant)`. General Sans non ha i numeri tabellari (misurato): mai per le cifre.

## 5. Colore: ruoli e contrasto misurato
Metodo: `scratchpad/tools/contrast.mjs` + `contrast.py` campionano i **pixel resi** di ogni materiale nel punto più chiaro e più scuro del fondale, sopra otto strisce piene delle serie e sopra un blocco bianco; il rapporto è WCAG.

| Caso (tema scuro) | Testo peggiore | Segno peggiore |
|---|---|---|
| Pannello · rialzato · cromatura · foglio sul fondale | 5,17 · **4,84** · 5,75 · 5,94 (`--neg`) | 4,12 · **3,87** (`--s5`) · 4,41 · 4,46 |
| Cromatura sopra le otto serie piene | **4,23** (`--neg` nudo); il resto ≥ 4,5 | 3,38 |
| Foglio sopra le otto serie piene | 4,91 | 3,93 |
| Bottoni primario / KILL (riga del testo) | 4,84 / 4,96 | — |
| Celle delle rampe · `--on-crit` su `--crit` | ≥ 4,56 · 4,66 | — |
| Caso limite: campo bianco pieno sotto cromatura / foglio | 2,77 / 3,67 | 2,21 / 2,93 |

- Tema chiaro: testo ≥ 5,01 su ogni materiale; segni ≥ 3 tranne il pieno `--warn` (1,65–1,99: va sempre con icona e parola; per linee usare `--warn-ink`).
- Serie: validate con lo script della skill dataviz sul vetro più chiaro. Scuro: banda L, croma, CVD adiacente ΔE 10,5, visione normale 18,8, contrasto ≥ 3:1. Chiaro: CVD 8,1, normale 16,8. Dispersioni e piccoli multipli: solo le prime tre serie passano «tutte le coppie».
- Stati: sicuro (verde, cerchio con spunta) · attenzione (ambra, triangolo) · violazione (rosso, bordo marcato) · arrestato (rosso pieno lucido, l'unico pieno) · sconosciuto (tratteggio, senza colore).
- Provenienza: ESEMPIO punteggiato e tratteggiato a righe · SIMULATO viola tratteggiato · PAPER blu a filetto · REALE pieno. Nei grafici lo stesso ordine vale per il tratto (`--chart-dash-demo`, `--chart-dash-sim`, pieno, pieno più spesso).
- Rampe: sequenziale blu a 7 passi, divergente blu↔arancio a 9 con centro neutro, P&L rosso↔verde a 7 (toni gioiello, testo bianco in ogni cella). Il numero sta sempre nella cella.

## 6. Movimento
| Che cosa | Durata · curva | Perché |
|---|---|---|
| Pressione di un comando | 90 ms giù, 280 ms su · `--ease-spring-bouncy` | conferma del tocco |
| Riflesso al passaggio su un bottone | 900 ms, una passata | invito, non richiamo |
| Cursore del segmentato | 460 ms · molla 8% | la scelta si sposta, non scompare |
| Sollevamento di una scheda | 280 ms · molla 4%, −3 px | «questa risponde» |
| Ingresso dei pannelli | 480 ms, da sfocato a nitido, +18 px, scarto 55 ms | ordine di lettura |
| Fogli, popover, avvisi | 480 ms · molla 4% dal punto di origine | da dove viene |
| Rotolo delle cifre | 760 ms · molla morbida, da destra | il valore è cambiato davvero |
| Riflesso sull'eroe | 1,2 s, una passata per fotografia nuova | sono arrivati dati |
| Respiro del punto «vivo» e dell'ultimo punto del grafico | 2,4 s | i dati scorrono |
| Deriva del fondale · parallasse | 64 s a passi (circa 4 al secondo) · inerzia | profondità senza ridisegnare il vetro a 60 fps |

Mai animati: colore del P&L (niente lampeggi), assi e scale, posizione delle righe durante un aggiornamento, il KILL (nessun richiamo, nessun rimbalzo), le etichette di provenienza.

## 7. Ripieghi
- `prefers-reduced-transparency` e browser senza `backdrop-filter`: `--glass-*-bg` passa ai `-solid`, filtri a `none`, luci del fondale al 16%; restano orlo, luce interna e ombre (schermata `ds-dark-desktop-fallback.png`).
- `prefers-contrast: more`: superfici piene, `--text-3` = `--text-2`, filetti più forti, niente bagliori.
- `prefers-reduced-motion`: durate a 0,01 ms, spostamenti a zero, molle lineari; ferme deriva, parallasse, respiro, riflessi, caricamento; resta la dissolvenza (`--dur-fade`).
- Senza filtro SVG nello sfondo: lo smusso usa una sfocatura corta. Senza `linear()`: molle approssimate con `cubic-bezier`. Senza `corner-shape`: angoli a cerchio.

## 8. Fare / non fare
- Fare: pannelli solo sul fondale; cromatura e fogli sopra il contenuto. Non fare: vetro dentro vetro (dentro una scheda si usano `--well-*` e `--surface-2`).
- Fare: sulla cromatura solo `--text`, `--text-2` e capsule di stato. Non fare: `--text-3` o rosso P&L nudo sulla cromatura (4,2:1 nel caso peggiore).
- Fare: `animation-fill-mode: backwards` per gli ingressi. Non fare: lasciare un `filter` o un'opacità residua su un antenato del vetro: spegne la sfocatura dei figli (errore trovato e corretto qui).
- Fare: un solo primario blu per vista; il rosso pieno lucido è solo del KILL e dello stato arrestato.
- Fare: bagliore su cifra eroe, linea del fondo, punto vivo. Non fare: bagliore su testo corrente o su tutte le serie.
- Non fare: grandi campiture chiare sotto la cromatura nel tema scuro; colore senza segno, icona o tratto; una nona serie.

## 9. Dove non sono sicuro
- La sfocatura debole a densità 2 l'ho vista solo in Chromium senza GPU: lo strato allungato la risolve lì ed è innocuo altrove, ma non ho potuto provare Safari e Firefox, né misurare i fotogrammi su un portatile vero con otto pannelli di vetro e il fondale in deriva.
- Lo smusso che rifrange usa rumore, non una vera mappa del bordo: è «liquido», non otticamente esatto; costa un filtro SVG per elemento (oggi quattro).
- La pagina reale ha CSP senza stili in linea: `--x`, `--w` del segmentato e `--d` del rotolo vanno impostati via CSSOM, da verificare con il costruttore.
- `--surface` con alfa cambia il senso di alcune regole di `app.css` (intestazioni appiccicose, tooltip): vanno riviste una per una.
- Oro (`--s4`) e acqua (`--s3`) restano i meno brillanti: è il prezzo della banda di luminosità che tiene separate le serie per chi non distingue rosso e verde.
- Il tema chiaro funziona e passa i contrasti, ma non è stato rifinito quanto lo scuro.
