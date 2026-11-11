// Glossario: definizioni brevi e precise, più gli strumenti per sottolineare i termini nel testo.
// Un termine sottolineato a puntini è un pulsante: apre il glossario su quella voce.

import { h } from './dom.js';

export const GLOSSARY = [
  {
    id: 'cagr', term: 'CAGR', match: ['CAGR', 'rendimento annuo composto'],
    short: 'Rendimento annuo composto.',
    text: 'Quanto è cresciuto il patrimonio in media ogni anno, tenendo conto che i guadagni si reinvestono. Un CAGR del 10% porta 10.000 a 11.000 dopo un anno e a 12.100 dopo due. Più alto è meglio, ma da solo non dice quanto rischio è servito per ottenerlo.',
    expert: 'CAGR = (valore finale / valore iniziale)^(1 / anni) − 1, al netto dei costi ipotizzati.',
  },
  {
    id: 'volatilita', term: 'Volatilità', match: ['volatilità', 'Volatilità'],
    short: 'Quanto oscilla il valore.',
    text: 'Misura l\'ampiezza delle oscillazioni giornaliere, riportata a un anno. Con una volatilità del 10% è normale che in un anno il patrimonio si muova di circa ±10% intorno alla sua tendenza. Più bassa significa un percorso più tranquillo; non distingue però le oscillazioni in su da quelle in giù.',
    expert: 'Deviazione standard dei rendimenti giornalieri × √(giorni per anno: 365 per le serie di calendario).',
  },
  {
    id: 'sharpe', term: 'Sharpe', match: ['Sharpe', 'indice di Sharpe'],
    short: 'Rendimento per unità di rischio.',
    text: 'Divide il rendimento in eccesso (sopra il tasso senza rischio) per la volatilità. Dice quanto «rende» ogni unità di rischio presa. Sotto 0,5 è debole, intorno a 1 è buono, sopra 2 su periodi lunghi è raro e va guardato con sospetto. Più alto è meglio.',
    expert: 'Sharpe annualizzato = media(r − rf) / dev.std(r) × √periodi. L\'errore standard su pochi anni è grande: circa √((1 + S²/2) / anni).',
  },
  {
    id: 'drawdown', term: 'Drawdown', match: ['drawdown', 'Drawdown', 'caduta dal massimo'],
    short: 'Caduta dal massimo.',
    text: 'Quanto il patrimonio è sotto il suo punto più alto mai raggiunto. Un drawdown del −10% significa che da quel massimo si è perso un decimo. Il drawdown massimo è la caduta peggiore della storia. È sempre zero o negativo: più vicino a zero è meglio.',
    expert: 'DD(t) = patrimonio(t) / max(patrimonio fino a t) − 1. Gli scalini del motore di rischio scattano su questa grandezza.',
  },
  {
    id: 'leva-conto', term: 'Leva del conto', match: ['leva del conto', 'Leva del conto', 'leva lorda'],
    short: 'Esposizione totale divisa per il patrimonio.',
    text: 'Somma del valore di tutte le posizioni divisa per il patrimonio. A 1x si è investiti per tutto il patrimonio; a 2x per il doppio, quindi guadagni e perdite raddoppiano. È questa la leva che decide quanto può perdere il conto. Il fondo opera a 2x e non supera 3x.',
    expert: 'Leva lorda = Σ |valore delle posizioni| / patrimonio. Il limite è applicato dal motore di rischio a ogni ciclo.',
  },
  {
    id: 'leva-trade', term: 'Leva del trade', match: ['leva del trade', 'Leva del trade'],
    short: 'Controvalore di una singola operazione diviso per il margine depositato.',
    text: 'Su una singola operazione, il rapporto tra il controvalore e il margine che il broker chiede. Una leva del trade alta (anche 20x) non vuol dire rischiare di più: serve a impegnare meno capitale per la stessa esposizione. Il rischio lo decide la distanza dello stop, non la leva del trade.',
    expert: 'Leva del trade = controvalore / margine. Rischio = controvalore × distanza dello stop. Vincolo: lo stop sta prima della liquidazione (distanza stop ≤ 0,6 × distanza di liquidazione).',
  },
  {
    id: 'var', term: 'VaR', match: ['VaR'],
    short: 'Perdita di giornata che si supera raramente.',
    text: 'Il VaR al 95% a un giorno è la perdita che ci si aspetta di superare solo un giorno su venti. Se vale 1%, in 19 giorni su 20 la perdita resta sotto l\'1% del patrimonio. Non dice quanto si perde nel giorno peggiore: per quello c\'è l\'ES, la perdita media in quei giorni.',
    expert: 'VaR storico: 5° percentile dei rendimenti giornalieri. ES (expected shortfall): media dei rendimenti sotto quel percentile.',
  },
  {
    id: 'psr', term: 'PSR', match: ['PSR'],
    short: 'Probabilità che lo Sharpe vero sia sopra zero.',
    text: 'Lo Sharpe misurato è una stima, e con pochi dati può essere alto per caso. Il PSR dice quanto è probabile che lo Sharpe vero sia positivo, tenendo conto della lunghezza dello storico e della forma dei rendimenti. Sopra il 95% è un buon segno; non tiene conto di quante strategie sono state provate.',
    expert: 'Probabilistic Sharpe Ratio (Bailey e López de Prado): Φ[(SR − SR*) √(n−1) / √(1 − γ₃·SR + (γ₄−1)/4·SR²)], con SR* = 0.',
  },
  {
    id: 'dsr', term: 'Deflated Sharpe', match: ['Deflated Sharpe', 'DSR'],
    short: 'PSR corretto per il numero di prove fatte.',
    text: 'Se si provano cento strategie, la migliore ha uno Sharpe alto anche se nessuna funziona davvero. Il Deflated Sharpe confronta lo Sharpe ottenuto con quello che ci si aspetta dalla migliore di tante prove a caso. Sopra 0,95 il risultato regge anche a questo esame; sotto, non è ancora una prova.',
    expert: 'DSR = PSR calcolato con SR* = Sharpe atteso dal massimo di N prove indipendenti (dipende da N e dalla varianza degli Sharpe delle prove).',
  },
  {
    id: 'conviction', term: 'Conviction', match: ['conviction', 'Conviction'],
    short: 'Quanti segnali indipendenti sono d\'accordo.',
    text: 'Un punteggio da 0 a 1: la quota di segnali accesi su uno strumento in quel momento. Si divide in tre livelli (bassa, media, alta) e decide quanto rischio è ammesso su una singola operazione: nessuno a livello basso, 0,5% del patrimonio a livello medio, 1% a livello alto. Non è una probabilità di vincere: anche a livello alto i giorni positivi sono poco più della metà.',
    expert: 'Score = media dei segnali binari validi. Soglie: crypto 0,30 / 0,60; indici 0,55 / 0,82. Segnali mancanti → livello «bassa».',
  },
  {
    id: 'overlay', term: 'Overlay AI', match: ['overlay AI', 'Overlay AI', 'overlay'],
    short: 'Riduzione dell\'esposizione proposta dal livello AI.',
    text: 'Il livello AI legge notizie, dati macro e regime di mercato e consegna al ciclo un moltiplicatore tra 0 e 1 per ogni strategia: 1 lascia tutto com\'è, 0,5 dimezza, 0 vieta. Non può mai aumentare un\'esposizione né scegliere le operazioni, ha una scadenza e deve citare le fonti. Il motore di rischio decide comunque per ultimo.',
    expert: 'L\'overlay unisce desk LLM, regime deterministico e decadimento delle strategie; viene validato e applicato ai pesi obiettivo prima del motore di rischio.',
  },
  {
    id: 'kill', term: 'KILL', match: ['KILL'],
    short: 'Arresto di emergenza.',
    text: 'L\'interruttore generale. Scatta da solo se la caduta dal massimo supera il limite, oppure a mano con un file sul server. Il motore chiude tutte le posizioni e si ferma; per ripartire servono due gesti volontari: togliere il file e dare il comando di ripristino. Si riparte a esposizione ridotta.',
    expert: 'Stato KILLED a ritenuta (gerva/risk/engine.py): si esce solo rimuovendo il file KILL e con `gerva reset-kill`; il massimo storico riparte dal valore attuale.',
  },
  {
    id: 'scelta-verifica', term: 'Periodo di scelta e di verifica', match: ['periodo di scelta', 'periodo di verifica', 'scelta e verifica', 'scelta e di verifica'],
    short: 'Dati usati per decidere le regole e dati tenuti da parte per controllarle.',
    text: 'Le regole sono state scelte guardando solo i dati fino alla fine del 2022 (periodo di scelta). I dati dal 2023 in poi (periodo di verifica) non sono stati usati per decidere nulla: servono a vedere se le regole funzionano anche su ciò che non hanno mai visto. Un risultato che regge nella verifica vale molto più di uno bello solo nella scelta.',
    expert: 'In-sample fino al 31/12/2022, out-of-sample dal 01/01/2023. La verifica è stata guardata, quindi non è più del tutto «vergine»: il paper trading è la prova successiva.',
  },
  {
    id: 'punto-base', term: 'Punto base', match: ['punto base', 'punti base', 'Punto base', 'pb'],
    short: 'Un centesimo di punto percentuale.',
    text: 'Un punto base (pb) è lo 0,01%. Cento punti base fanno l\'1%. Si usa per i rendimenti giornalieri e per i costi, dove le percentuali sarebbero numeri troppo piccoli: 5 pb al giorno sono lo 0,05% al giorno.',
    expert: '1 pb = 0,0001. 10 pb al giorno ≈ 44% l\'anno composto su 365 giorni.',
  },
];

const BY_ID = new Map(GLOSSARY.map((g) => [g.id, g]));
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const WORDS = GLOSSARY.flatMap((g) => g.match.map((m) => ({ m, id: g.id }))).sort((a, b) => b.m.length - a.m.length);
const PATTERN = new RegExp(`(?<![\\p{L}\\p{N}])(${WORDS.map((w) => esc(w.m)).join('|')})(?![\\p{L}\\p{N}])`, 'u');
const ID_OF = new Map(WORDS.map((w) => [w.m, w.id]));

/** Pulsante-termine: testo sottolineato a puntini che apre il glossario sulla voce. */
export function term(id, label) {
  const g = BY_ID.get(id);
  return h('button', { class: 'term', type: 'button', 'data-term': id, title: g ? g.short : null, text: label || (g ? g.term : id) });
}

/** Testo → nodi: la prima occorrenza di ogni termine del glossario diventa un pulsante-termine. */
export function gloss(text) {
  const out = [];
  const seen = new Set();
  let rest = String(text == null ? '' : text);
  for (let guard = 0; guard < 12 && rest; guard++) {
    const m = PATTERN.exec(rest);
    if (!m) break;
    const id = ID_OF.get(m[1]);
    if (seen.has(id)) {
      out.push(rest.slice(0, m.index + m[1].length));
    } else {
      seen.add(id);
      if (m.index) out.push(rest.slice(0, m.index));
      out.push(term(id, m[1]));
    }
    rest = rest.slice(m.index + m[1].length);
  }
  if (rest) out.push(rest);
  return out;
}

/** Contenuto del cassetto del glossario. */
export function glossaryList() {
  return h('dl', { class: 'glossary' }, GLOSSARY.map((g) => h('div', { class: 'glossary__item', id: `gl-${g.id}`, tabindex: '-1' },
    h('dt', { class: 'glossary__term' }, g.term, h('span', { class: 'glossary__short', text: g.short })),
    h('dd', { class: 'glossary__text', text: g.text }),
    h('dd', { class: 'glossary__expert only-esperto' }, h('span', { class: 'glossary__tag', text: 'Per esperti' }), g.expert))));
}
