# Ricerca di alpha: premi che sopravvivono, metodi che non mentono

Etichette come in `firms.md`: [A] fonte primaria o risultato matematico dimostrato, [M] fonte secondaria seria o risultato riportato senza aver letto le tabelle originali, [B] debole. Le formule scritte "a memoria" sono segnate e sono implementate e **testate** in `quantlab/` (i test verificano le proprietà note, non le copie dal paper).

> «The first principle is that you must not fool yourself — and you are the easiest person to fool.» — Richard Feynman, discorso al Caltech, 1974.

## 0. Il problema prima delle anomalie

- Su 97 anomalie pubblicate, i rendimenti scendono del **26% fuori campione** e del **58% dopo la pubblicazione**; la differenza (32%) è attribuita al trading informato dai paper. [A] ([McLean & Pontiff, JF 2016](https://Www.Gwern.net/doc/economics/2016-mclean.pdf))
- Con la correzione per test multipli, una nuova anomalia dovrebbe avere **t > 3,0**, non 2,0; «la maggior parte delle scoperte dichiarate è probabilmente falsa». [A] ([Harvey, Liu & Zhu, RFS 2016](https://nber.org/papers/w20592))
- Replicando 447 anomalie con procedure comuni, il 64% non è significativo al 5%; con t ≥ 3 si sale all'85%. [A] ([Hou, Xue & Zhang, RFS 2020](https://www.nber.org/papers/w23394.pdf))

**Conseguenza operativa:** il nostro prior per «una nuova idea di un agente funziona» deve essere basso. Se il prior è 10% e il test ha potenza 80% con falsi positivi al 5%, la probabilità che un'idea che passa il test sia vera è 0,1·0,8 / (0,1·0,8 + 0,9·0,05) = **64%**. Con 100 idee il numero assoluto di falsi positivi (≈4,5) è quasi uguale a quello dei veri (8). Questo è il calcolo che giustifica il `trial_registry` globale.

## 1. I premi documentati e la loro fragilità

### 1.1 Trend / momentum di serie storica (TSMOM)

Definizione (Moskowitz, Ooi, Pedersen 2012):

$$ r^{TSMOM}_{t,t+1} = \operatorname{sign}(r_{t-12,t}) \cdot \frac{\sigma^*}{\hat\sigma_t} \cdot r_{t,t+1}, \quad \sigma^*=40\% $$

- Significativo su **58** futures liquidi (indici, valute, materie prime, obbligazioni); persiste 1–12 mesi e si inverte in parte più avanti. [A] ([JFE 2012, SSRN](https://papers.ssrn.com/abstract=2089463))
- Positivo in **ogni decennio dal 1880**, su 67 mercati; Sharpe netto circa 0,77 nella versione 2014. [A per lo studio, M per il numero preciso] ([Hurst, Ooi & Pedersen, JPM 2017](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing))
- **Fragilità:** drawdown lunghi nei mercati senza direzione (2009–2012 citato dagli stessi autori), dipendenza dalla diversificazione tra classi di attivo. Con soli ETF UCITS long/flat si perde la metà corta del segnale: è il limite strutturale già scritto in STUDIO.md §4.

### 1.2 Momentum cross-section e i suoi crash

- I crash del momentum sono concentrati nelle fasi di panico, dopo i ribassi e con volatilità alta, in coincidenza con i rimbalzi; nei bear market il momentum si comporta come una **call venduta sul mercato** (beta in salita più che doppio di quello in discesa). [A] ([Daniel & Moskowitz, JFE 2016](https://www.nber.org/papers/w20439))
- Una versione dinamica che pesa con la previsione di media e varianza del momentum **circa raddoppia** alfa e Sharpe. [M per il numero]
- **Implicazione per GERVA-Q S3:** la rotazione settoriale 12-1 ha il filtro SMA200 come proxy grezzo del regime. Il candidato di ricerca è sostituirlo con la regola di Daniel–Moskowitz (bear market *e* volatilità alta → ridurre). Va registrato nel trial registry.

### 1.3 Value e momentum insieme

- Value e momentum hanno rendimenti positivi in otto mercati e classi di attivo e sono **negativamente correlati** tra loro (circa −0,5 in media secondo una sintesi secondaria). [A per il segno, M per il valore] ([Asness, Moskowitz & Pedersen, JF 2013](https://pages.stern.nyu.edu/~lpederse/papers/ValMomEverywhere.pdf))
- **Per noi:** il value non è nel motore attuale. Su ETF UCITS si può misurare solo in forma grezza (rendimento a 5 anni invertito, CAPE di paese). Candidato a bassa priorità e con prior basso.

### 1.4 Carry

Definizione indipendente dal modello (Koijen, Moskowitz, Pedersen, Vrugt 2018): carry = rendimento atteso se i prezzi restano invariati; per un future

$$ C_t = \frac{S_t - F_t}{F_t} $$

- Predice i rendimenti in sezione trasversale e nel tempo su azioni globali, obbligazioni, materie prime, valute; non spiegato dagli altri fattori. [A] ([JFE 2018](https://econpapers.repec.org/RePEc:eee:jfinec:v:127:y:2018:i:2:p:197-225))
- **Carry crypto:** la base futures–spot può superare il 40–60% annuo; un carry alto **predice crash** dei prezzi ed è guidato dagli investitori piccoli che inseguono la leva e dalla scarsità di capitale di arbitraggio. [A] ([Schmeling, Schrimpf & Todorov, BIS WP 1087](https://www.bis.org/publ/work1087.pdf))
- **Vincolo reale:** sul conto retail IBKR Ireland non abbiamo futures crypto. Possiamo però usare la base o il funding come **segnale di rischio** (dato pubblico) per ridurre l'esposizione spot quando il carry è estremo: è un'idea con meccanismo pubblicato e senza bisogno di short. Candidato ad alta priorità per il pod Crypto.

### 1.5 Reversal di breve e fornitura di liquidità

- I rendimenti delle strategie di reversal di breve sono **la remunerazione della fornitura di liquidità**, prevedibili con il VIX: Sharpe condizionato alto quando il VIX è alto. [A] ([Nagel, RFS 2012](https://nber.org/papers/w17653))
- **Implicazione per GERVA-Q S4:** oggi S4 ha dimensione fissa e un filtro che lo *spegne* sotto la SMA200 dell'S&P. Nagel suggerisce il contrario: il premio è più alto proprio nelle fasi di stress, quando però il rischio di coda è maggiore. Ipotesi da testare (con prior medio): dimensione proporzionale al VIX, con il tetto per titolo invariato.
- **Fragilità:** S4 usa l'universo attuale dell'S&P 100 (survivorship), è esposto ai crash di liquidità del 2008 e dell'agosto 2007.

### 1.6 Volatilità gestita

- Moreira & Muir (2017) trovano alfa positivo scalando i fattori con l'inverso della varianza. [A]
- Su 103 strategie, le versioni realizzabili in tempo reale **non battono sistematicamente** le originali (Sharpe più alto solo in 53 casi su 103); la causa è l'instabilità strutturale delle regressioni. [A] ([Cederburg et al., JFE 2020](https://www.lehigh.edu/~xuy219/research/COWY.pdf))
- **Implicazione per GERVA-Q S2:** lo Sharpe OOS 0,90 di S2 va trattato con sospetto finché non regge un test del tipo Cederburg (confronto diretto con SPY non scalato a pari volatilità, sottoperiodi). È un controllo, non una modifica.

### 1.7 Cross-section crypto

- Tre fattori (mercato, size, momentum) spiegano la sezione trasversale delle crypto 2014–2018; il momentum funziona solo nelle monete sopra la mediana di capitalizzazione. [A] ([Liu, Tsyvinski & Wu, JF 2022](https://cowles.yale.edu/sites/default/files/2022-10/LiuTsyvinskiWu2019%20COMMON%20RISK%20FACTORS.pdf))
- **Fragilità:** campione corto e mercato immaturo; il crollo fuori campione di H5 (Sharpe da 1,45 a 0,55) in STUDIO.md §7 è coerente con questa fragilità.

### 1.8 Segnali da LLM su notizie

- I punteggi di ChatGPT sui titoli predicono i rendimenti giornalieri, più nei titoli piccoli e dopo notizie negative; la versione 2025 aggiunge che i rendimenti **calano man mano che l'uso degli LLM si diffonde**. [A] ([Lopez-Lira & Tang, arXiv 2304.07619 v6](https://arxiv.org/abs/2304.07619v5))
- Una parte del vantaggio in-sample viene dalla conoscenza del futuro (look-ahead) e una dalla "distrazione" sul nome dell'azienda. [A] ([Glasserman & Lin 2023](https://arxiv.org/abs/2309.17322))
- **Regola per noi:** inutilizzabili in backtest (regola inviolabile 10). Si valutano solo in avanti, vedi `llm_agents_in_finance.md`.

## 2. Il motore: legge fondamentale e perché servono molti segnali deboli

Grinold (1989), generalizzata da Clarke, de Silva e Thorley (2002):

$$ IR = TC \cdot IC \cdot \sqrt{BR} $$

IC = correlazione previsione–esito, BR = scommesse indipendenti all'anno, TC = quanto del segnale sopravvive ai vincoli (0,3–0,8 nella pratica). [A] ([FAJ 2002](https://ideas.repec.org/a/taf/ufajxx/v58y2002i5p48-66.html))

Esempio: IC = 0,02 (pochissimo) su 500 scommesse indipendenti l'anno con TC = 0,5 dà IR ≈ 0,22; lo stesso IC su 10.000 scommesse dà IR ≈ 1. Con vincoli long-only la TC crolla: è la spiegazione quantitativa del "tetto" di Sharpe 0,7–0,8 in STUDIO.md §4. Le scommesse devono essere **indipendenti**: 15 ETF quasi tutti azionari non sono 15 scommesse.

## 3. Statistica del Sharpe ratio

Sia $\widehat{SR}$ lo Sharpe **alla frequenza originale** (giornaliera), $T$ le osservazioni, $\gamma_3$ l'asimmetria, $\gamma_4$ la curtosi **non in eccesso** (= 3 per la normale).

**Errore standard** (Lo 2002; Mertens 2002; Bailey & López de Prado 2012):

$$ \hat\sigma(\widehat{SR}) = \sqrt{\frac{1 - \gamma_3\,\widehat{SR} + \frac{\gamma_4 - 1}{4}\widehat{SR}^2}{T-1}} $$

**Probabilistic Sharpe Ratio**, probabilità che lo Sharpe vero superi la soglia $SR^*$:

$$ PSR(SR^*) = \Phi\!\left(\frac{(\widehat{SR} - SR^*)\sqrt{T-1}}{\sqrt{1 - \gamma_3\widehat{SR} + \frac{\gamma_4-1}{4}\widehat{SR}^2}}\right) $$

**Minimum Track Record Length**, quante osservazioni servono perché $PSR \ge 1-\alpha$:

$$ MinTRL = 1 + \left(1 - \gamma_3\widehat{SR} + \frac{\gamma_4-1}{4}\widehat{SR}^2\right)\left(\frac{z_{1-\alpha}}{\widehat{SR} - SR^*}\right)^2 $$

Esempio che conta per la sfida con Kimi: Sharpe annuo vero 1,0 (giornaliero 0,063), rendimenti normali, $SR^*=0$, $\alpha=5\%$: MinTRL ≈ 1 + (1,645/0,063)² ≈ **683 giorni di borsa (≈2,7 anni)**. Tre mesi di sfida (≈63 giorni) **non possono** distinguere un sistema da Sharpe 1 da uno da Sharpe 0 con confidenza al 95%. Lo calcola `quantlab.stats.min_trl` e lo mostra il portale.

## 4. Deflated Sharpe Ratio (Bailey & López de Prado 2014)

È il PSR con soglia pari allo **Sharpe massimo atteso tra N prove a Sharpe vero nullo**:

$$ SR_0 = \sqrt{V[\widehat{SR}_n]}\left((1-\gamma)\,\Phi^{-1}\!\left(1-\tfrac1N\right) + \gamma\,\Phi^{-1}\!\left(1-\tfrac{1}{Ne}\right)\right),\quad \gamma\approx0{,}5772 $$

$$ DSR = PSR(SR_0) $$

[A] ([SSRN 2460551](https://papers.ssrn.com/abstract=2460551))

**Due input che si truccano facilmente:**
1. **N**, il numero di prove *indipendenti*. Contarle tutte è il compito del `trial_registry`; le prove molto correlate tra loro si possono raggruppare (numero effettivo di prove), ma la regola di default è prudente: si contano tutte.
2. **V[SR_n]**, la varianza degli Sharpe delle prove. Deve venire dagli Sharpe **realmente osservati** delle prove registrate. In GERVA-Q `v3_validate.py` gli Sharpe delle 55 prove sono generati con `np.linspace(0.3, 1.55, 55)`, cioè inventati; il DSR 0,97 dichiarato non è quindi verificabile (vedi `gervaq_audit.md` R1). Nel nuovo sistema il DSR si calcola *solo* dal registro.

## 5. Probabilità di overfitting del backtest (PBO, CSCV)

Bailey, Borwein, López de Prado e Zhu (2017). [A per il metodo] ([SSRN 2326253](https://papers.ssrn.com/abstract=2326253))

Procedura (implementata in `quantlab.stats.pbo_cscv`):
1. Matrice $M$ di $T$ righe (periodi) e $N$ colonne (varianti). Si divide in $S$ blocchi (pari).
2. Per ognuna delle $\binom{S}{S/2}$ combinazioni: metà blocchi = in-sample $J$, l'altra metà = out-of-sample $\bar J$.
3. Si sceglie la variante $n^*$ col miglior Sharpe in $J$; si calcola il suo rango relativo $\bar\omega\in(0,1)$ in $\bar J$, e $\lambda = \ln\frac{\bar\omega}{1-\bar\omega}$.
4. $PBO = P(\lambda \le 0)$ sulla distribuzione delle combinazioni.

Interpretazione: PBO = 0,5 significa che scegliere la variante migliore in-sample equivale a scegliere a caso. Il test automatico in `tests/test_quantlab_stats.py` verifica proprio questo: su varianti di puro rumore la PBO deve stare intorno a 0,5; con una variante vera dominante deve andare verso 0.

## 6. Validazione incrociata nel tempo: walk-forward, purging, embargo, CPCV

- **Walk-forward:** una sola traiettoria storica; facile da capire, ma lo scenario testato è uno solo, quindi la varianza della stima è alta.
- **Purging:** dal training si tolgono le osservazioni la cui *finestra di etichetta* si sovrappone a quella del test (altrimenti il modello vede parte dell'esito). **Embargo:** si toglie anche un margine dopo il test, per l'autocorrelazione dei segnali. [A per le definizioni, da López de Prado, *Advances in Financial Machine Learning*, 2018, capp. 7 e 12] ([sintesi](https://en.wikipedia.org/wiki/Purged_cross-validation))
- **CPCV:** si divide la storia in $N$ gruppi, si testano tutte le combinazioni di $k$ gruppi di test, con purging ed embargo a ogni confine; si ottengono $\varphi = \frac{k}{N}\binom{N}{k}$ traiettorie di backtest, quindi una **distribuzione** dello Sharpe invece di un numero solo.
- Quando *non* serve: per regole senza parametri stimati (es. 1/N tra strategie) basta il fuori campione semplice. Serve quando un modello viene **addestrato** (ML, pesi stimati, soglie ottimizzate).

## 7. Costruzione del portafoglio

### 7.1 Shrinkage della covarianza (Ledoit & Wolf 2004)

$$ \hat\Sigma = \delta F + (1-\delta) S, \qquad \delta = \max\!\left(0, \min\!\left(\frac{\hat\kappa}{T}, 1\right)\right), \quad \hat\kappa = \frac{\hat\pi - \hat\rho}{\hat\gamma} $$

$F$ = matrice a correlazione costante, $S$ = covarianza campionaria; $\hat\pi$ = somma delle varianze asintotiche degli elementi di $S$, $\hat\rho$ = loro covarianza con $F$, $\hat\gamma$ = errore quadratico di specificazione del target. [A per l'impianto; M per $\hat\kappa$ che ho scritto a memoria e confrontato con una nota secondaria] ([paper](https://econ-papers.upf.edu/papers/691.pdf), [nota](https://reasonabledeviations.com/notes/papers/ledoit_wolf_covariance))
In `quantlab.portfolio.ledoit_wolf` il test verifica che lo stimatore riduca l'errore rispetto alla covarianza campionaria vera su dati simulati con T ≈ N.

### 7.2 Hierarchical Risk Parity (López de Prado 2016)

Tre passi: (1) clustering gerarchico con distanza $d_{ij} = \sqrt{\tfrac12(1-\rho_{ij})}$; (2) quasi-diagonalizzazione della covarianza secondo l'ordine delle foglie; (3) bisezione ricorsiva con pesi a varianza inversa tra i due sotto-cluster:

$$ \alpha = 1 - \frac{\tilde V_1}{\tilde V_1 + \tilde V_2}, \quad w_{C_1} \leftarrow \alpha\, w_{C_1},\; w_{C_2} \leftarrow (1-\alpha)\, w_{C_2} $$

dove $\tilde V_i = \tilde w_i^\top \Sigma_{C_i} \tilde w_i$ con $\tilde w_i$ a varianza inversa dentro il cluster. Non inverte la matrice; nelle simulazioni dell'autore ha varianza fuori campione più bassa del minimo-varianza. [A per il metodo; il risultato è su un processo simulato] ([SSRN 2708678](https://papers.ssrn.com/abstract=2708678)) **Non** equalizza i contributi al rischio: non chiamarla risk parity in senso stretto.

### 7.3 Risk parity (contributi uguali, ERC)

$$ w_i\,(\Sigma w)_i = \frac{w^\top\Sigma w}{N}\quad \forall i $$

Soluzione numerica per iterazioni moltiplicative. Utile tra *strategie* poco correlate; STUDIO.md mostra che tra le sleeve GERVA-Q la parità di rischio perde contro 1/N (0,66 contro 0,77), coerente con DeMiguel, Garlappi e Uppal (2009): l'errore di stima mangia il guadagno teorico. [A per il risultato interno, che ho letto nel codice]

### 7.4 Black–Litterman

Prior di equilibrio $\Pi = \delta\Sigma w_{mkt}$; viste $P\mu = Q + \varepsilon$, $\varepsilon\sim N(0,\Omega)$:

$$ \mu_{BL} = \left[(\tau\Sigma)^{-1} + P^\top\Omega^{-1}P\right]^{-1}\left[(\tau\Sigma)^{-1}\Pi + P^\top\Omega^{-1}Q\right] $$

[A] ([Black & Litterman, FAJ 1992](https://people.duke.edu/~charvey/Teaching/BA453_2006/Black_Litterman_Global_Portfolio_Optimization_1992.pdf)) **Uso da noi:** è il modo corretto di combinare le *viste degli agenti* (previsioni con probabilità) con il portafoglio sistematico: $\Omega$ si ricava dalla calibrazione storica dell'agente (Brier). Un agente mal calibrato ha $\Omega$ grande, quindi la sua vista quasi non sposta i pesi. Questo lega l'economia del merito al portafoglio in modo matematico, non a sensazione.

### 7.5 Kelly frazionato

Per un attivo con eccesso di rendimento $\mu$ e volatilità $\sigma$ (moto browniano geometrico), la crescita del logaritmo della ricchezza con frazione $f$ è $g(f) = r + f\mu - \tfrac12 f^2\sigma^2$; il massimo è $f^* = \mu/\sigma^2$. Con $f = c\,f^*$:

$$ g(c f^*) = r + c(2-c)\,\frac{\mu^2}{2\sigma^2}, \qquad \sigma_{\text{port}} = c\,\frac{\mu}{\sigma} $$

Mezzo Kelly ($c = 0{,}5$) dà il **75%** della crescita con **metà** della volatilità. Probabilità di scendere *mai* a una frazione $x$ della ricchezza iniziale: $P = x^{2/c - 1}$; con Kelly pieno $P(\text{toccare } 50\%) = 0{,}5$; con mezzo Kelly $0{,}5^3 = 12{,}5\%$. [A: derivazione standard nel caso continuo con parametri noti] Con parametri *stimati* il Kelly pieno è pericoloso: la frazione equivale a uno stimatore con shrinkage. [A] ([MacLean, Thorp & Ziemba](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf), [arXiv 2503.17927](https://www.arxiv.org/pdf/2503.17927))

**Uso da noi:** non per scegliere la leva (vietata), ma come **tetto** alla dimensione delle scommesse dei pod: nessun pod può dimensionare oltre ¼ Kelly stimato con lo Sharpe *deflazionato*.

## 8. Implicazioni per il motore (diventano decisioni in `DECISIONS.md`)

1. Il trial registry alimenta il DSR; niente Sharpe di prove inventati.
2. Ogni proposta riporta PSR, DSR, MinTRL, PBO (se ha varianti), sensibilità ai parametri e ai costi raddoppiati.
3. Le idee con meccanismo pubblicato e verificabile da noi (carry crypto come segnale di rischio, momentum dinamico, reversal condizionato al VIX) hanno prior più alto delle idee "trovate nei dati".
4. I segnali LLM si valutano solo in avanti.
