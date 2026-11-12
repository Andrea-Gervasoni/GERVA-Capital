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
  {
    id: 'rischio-trade', term: 'Rischio per trade', match: ['rischio per trade', 'Rischio per trade', 'rischio dichiarato'],
    short: 'Quanto del conto si accetta di perdere su una singola operazione.',
    text: 'La quota di patrimonio che si perde se l\'operazione va male ed esce allo stop: per esempio lo 0,5% o l\'1% del conto. È questa scelta, non la leva, a decidere quanto il conto può guadagnare o perdere nel tempo. Raddoppiare il rischio per trade raddoppia più o meno sia i rendimenti sia le cadute.',
    expert: 'Rischio = controvalore × distanza dello stop / patrimonio. I livelli usati: 0,5% (setup confermato) e 1% (eccezionale), o loro multipli negli schemi S1–S9.',
  },
  {
    id: 'r', term: 'R', match: ['R medio', 'in R', 'multipli di R'],
    short: 'Unità di misura: il rischio di un\'operazione.',
    text: '1 R è la somma che si era deciso di rischiare su un\'operazione. Un\'operazione chiusa a +2 R ha guadagnato il doppio di quanto rischiava; una chiusa allo stop vale −1 R. «R medio 0,2» vuol dire che, in media, ogni operazione rende un quinto del suo rischio, al netto dei costi. Sopra zero è positivo; più alto è meglio.',
    expert: 'R = P&L dell\'operazione / (controvalore × distanza dello stop). Aspettativa per operazione = media di R; costo in R = commissioni e slippage / rischio.',
  },
  {
    id: 'margine-isolato', term: 'Margine isolato', match: ['margine isolato', 'Margine isolato'],
    short: 'Il denaro bloccato su una singola operazione: è il massimo che quella operazione può perdere.',
    text: 'Con il margine isolato ogni operazione a leva ha il suo «salvadanaio» separato. Se il prezzo arriva alla liquidazione si perde quel salvadanaio e nient\'altro: il resto del conto non viene toccato. Nelle simulazioni il margine è circa 1,7 volte il rischio dichiarato: è la perdita peggiore se lo stop non viene eseguito.',
    expert: 'Margine = controvalore / leva. Perdita massima ≈ margine; rapporto margine / rischio = distanza di liquidazione / distanza dello stop (≈ 1,67 con stop a 0,6 × la distanza di liquidazione).',
  },
  {
    id: 'dist-liq', term: 'Distanza dalla liquidazione', match: ['distanza dalla liquidazione', 'Distanza dalla liquidazione', 'distanza di liquidazione'],
    short: 'Di quanto deve muoversi il prezzo contro perché il broker chiuda la posizione.',
    text: 'Più alta è la leva del trade, più vicino è il prezzo al quale il margine finisce e la posizione viene chiusa d\'ufficio. A 10x bastano circa 10% di movimento contrario, a 30x meno del 3%. Lo stop deve sempre stare prima di quel punto, con un margine di sicurezza.',
    expert: 'Distanza di liquidazione ≈ 1 / leva − margine di mantenimento. Vincolo del piano di trade: distanza stop ≤ 0,6 × distanza di liquidazione.',
  },
  {
    id: 'funding', term: 'Carry e funding', match: ['funding', 'carry', 'Carry'],
    short: 'Il pagamento periodico tra chi è lungo e chi è corto sui perpetual.',
    text: 'Sui contratti perpetual, ogni poche ore chi sta dalla parte più affollata paga una piccola somma all\'altra parte: è il funding. Incassarlo stando dalla parte meno affollata, coperti sul prezzo, si chiama carry. Nel 2021 rendeva il 30–40% l\'anno, oggi il 2–5%: è un premio che si è consumato.',
    expert: 'Carry = Σ funding incassato − costi di copertura. Dipende dalla venue; le serie di venue diverse non vanno incollate senza dichiararlo.',
  },
  {
    id: 'ombra', term: 'Ombra (shadow)', match: ['in ombra', 'In ombra', 'ombra'],
    short: 'Una regola osservata senza che agisca.',
    text: 'Una correzione che ha superato i controlli sui dati storici non viene applicata subito: entra «in ombra». Il sistema annota che cosa avrebbe fatto su ogni nuovo trade del conto di prova, senza toccare nulla. Solo se anche lì si dimostra utile diventa promuovibile, e solo il proprietario può attivarla.',
    expert: 'Stato IN_OMBRA: servono almeno 20 trade paper colpiti, con R medio sotto zero e sotto quello degli altri, per passare a PROMUOVIBILE.',
  },
  {
    id: 'walk-forward', term: 'Walk-forward', match: ['walk-forward', 'Walk-forward'],
    short: 'Controllo anno per anno, sempre in avanti nel tempo.',
    text: 'Invece di guardare tutto lo storico insieme, si controlla se una regola avrebbe aiutato in ciascun anno preso da solo. Una regola buona funziona in molti anni diversi; una che funziona solo in uno o due è probabilmente un caso.',
    expert: 'Qui: quota di anni (con almeno 5 trade colpiti) in cui i trade colpiti rendono meno degli altri; soglia 60%.',
  },
  {
    id: 'fuori-campione', term: 'Fuori campione', match: ['fuori campione', 'Fuori campione', 'in campione'],
    short: 'Dati che non sono serviti a trovare la regola.',
    text: 'Una regola si cerca su una parte dei dati («in campione») e si controlla su un\'altra parte che non ha mai visto («fuori campione»). Se funziona solo dove è stata cercata, ha imparato il passato a memoria; se funziona anche fuori, c\'è qualche speranza che valga in futuro. È la stessa idea del periodo di scelta e di verifica.',
    expert: 'In campione: trade fino al 31/12/2022. Fuori campione: dal 2023. La soglia in campione è t ≤ −√(2 ln K), mai sotto 2, con K = ipotesi provate.',
  },
  {
    id: 'mae-mfe', term: 'MAE / MFE', match: ['MAE', 'MFE'],
    short: 'Il momento peggiore e il momento migliore di un\'operazione mentre era aperta.',
    text: 'MAE (escursione avversa massima) è quanto un\'operazione è andata in perdita nel suo momento peggiore; MFE (escursione favorevole massima) è quanto è andata in guadagno nel momento migliore. Si misurano in R. Servono a capire se gli stop sono troppo stretti o se si esce troppo presto.',
    expert: 'MAE e MFE in multipli del rischio iniziale, registrati nella memoria dei trade (gerva/learn/memory.py).',
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
