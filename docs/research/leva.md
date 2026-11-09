# La leva: cosa dice la matematica, e come la usano gli agenti

Questo e' il materiale che gli agenti hanno davanti quando scelgono la leva su un segnale (campo `studio_leva`).
La scelta e' loro: non c'e' obbligo di usare il massimo che il segnale propone.

## Cosa fa la leva

- Rendimento sul margine = leva x rendimento del sottostante. La perdita massima e' il margine (liquidazione).
- La liquidazione avviene a circa 1/leva dall'ingresso (meno il margine di mantenimento): 10x = ~9,5%, 25x = ~3,5%.
  Se lo stop e' piu' lontano della liquidazione, la liquidazione arriva prima dello stop: lo stop non protegge piu'.

## Dimensione ottima (Kelly, 1956; Thorp)

Con probabilita' p di vincere e rapporto rendimento/rischio R, la frazione del conto da rischiare che massimizza la crescita e'
`f* = p - (1-p)/R`. Rischiare piu' di `2 x f*` fa diminuire la crescita attesa nel lungo periodo. Se p e' sbagliata (e di solito e' troppo
ottimista), la leva moltiplica l'errore: per questo si usa spesso mezzo Kelly.

## Trascinamento da volatilita'

La crescita geometrica e' circa `mu - sigma^2/2`. La leva L moltiplica mu per L e sigma^2 per L^2: la crescita attesa ha un massimo
(a L* = mu/sigma^2) e oltre `2 x L*` diventa negativa anche con un vantaggio statistico positivo.

## Perche' non e' ovvio che "piu' leva e' meglio" per un'AI

- Un modello linguistico stima male le probabilita': e' proprio l'errore di calibrazione, moltiplicato per la leva, che fa saltare il conto.
- Con leva alta bastano rumore e oscillazioni normali per essere liquidati prima che l'idea abbia ragione.
- Cio' che si puo' misurare qui, senza rischiare nulla, e' se la leva scelta aiuta o danneggia: il banco futures simulato registra ogni posizione
  e restituisce agli agenti i risultati per fascia di leva (1-3x, 4-6x, 7-10x, 11-25x), con numero di liquidazioni.

## Come si usa

1. L'agente legge `studio_leva`: liquidazione per ogni leva, stop prima o dopo la liquidazione, guadagno/perdita sul margine, esiti passati per fascia.
2. Sceglie leva e margine e li motiva (`motivo_leva`). Il codice mette solo i tetti fisici (leva massima, margine per segnale e totale).
3. La posizione virtuale si controlla ogni 15 minuti su massimi e minimi; il risultato torna nello storico per fascia.

Se un articolo specifico sostiene che alzare la leva migliora le AI, vale la pena metterlo qui con titolo e fonte: gli agenti lo leggeranno e
i dati del banco simulato diranno se, per questi segnali, e' vero.
