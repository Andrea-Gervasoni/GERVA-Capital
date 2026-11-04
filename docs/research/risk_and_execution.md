# Rischio ed esecuzione

Etichette: [A] primaria o dimostrato, [M] secondaria seria, [B] debole.

> «Il rischio viene dal non sapere quello che si sta facendo.» — attribuita a Warren Buffett (attribuzione comune, fonte originale non verificata: [B]).

## 1. Limiti a più livelli

Struttura adottata (valori iniziali in `config/risk_limits.yaml`, modificabili solo da Andrea):

| Livello | Limite | Valore iniziale | Perché |
|---|---|---|---|
| Ordine | fat-finger: valore massimo per ordine | 5% del NAV di società | un errore di digitazione non può diventare una perdita grande |
| Ordine | prezzo limite entro ±2% dall'ultimo prezzo | 2% | evita fill su prezzi anomali |
| Strumento | solo strumenti ammessi da REGOLE_SFIDA (UCITS, azioni, ETC, crypto IBKR) | lista | regola 2 della sfida |
| Pod | capitale massimo | 5% del NAV ciascuno | brief, campione minimo prima di dare di più |
| Pod | lorda ≤ 100% del capitale del pod, niente short | 1,0 | regola 3 della sfida |
| Pod | concentrazione per titolo | 25% del capitale del pod | 4 titoli minimo |
| Pod | drawdown −5% → capitale dimezzato; −7,5% → pod chiuso | 5% / 7,5% | meccanismo multi-manager ([firms.md](firms.md) §1) |
| Società | lorda ≤ 100% del NAV (somma dei pod + Pod Zero) | 1,0 | regola 3 |
| Società | drawdown −15% → KILL automatico | 15% | squalifica al −20% (regola 10): ci si ferma prima |
| Società | correlazione media tra pod (60 giorni) ≤ 0,5 | 0,5 | affollamento, agosto 2007 (§5) |

## 2. Stop sul drawdown a scalini: quando aiutano e quando no

- Per il **libro sistematico** lo stop peggiora lo Sharpe (0,71 contro 0,77 in STUDIO.md §3): la strategia trend taglia già le perdite e lo stop esce dopo il calo, mancando il rimbalzo. [A, risultato interno]
- Per i **pod sperimentali** la logica è diversa: lo stop non serve a migliorare lo Sharpe, ma a limitare il costo di un **errore di modello**. Se un pod sta perdendo, l'ipotesi più probabile non è "sfortuna" ma "idea sbagliata" (prior basso, vedi `alpha_research.md` §0). La regola a scalini rende la perdita massima nota prima: con capitale al 5% del NAV e chiusura al −7,5%, ogni pod può costare al massimo circa lo **0,375% del NAV** (meno, dopo il dimezzamento).

## 3. Stress test

Tre famiglie, tutte in codice (`firm/risk_engine.py`):
1. **Storici:** riapplicare ai pesi attuali i rendimenti di finestre reali: ottobre 2008, agosto 2011, marzo 2020, 2022 (rialzo dei tassi), maggio 2021 e novembre 2022 (crypto, FTX).
2. **Ipotetici:** shock sui fattori (azionario −20%, tassi +100bp, crypto −50% in 48 ore con spread allargati a 5 volte).
3. **Correlazione di crisi:** si ripete il calcolo della volatilità di portafoglio con tutte le correlazioni portate a 0,8 tra gli attivi rischiosi.

## 4. Correlazioni in crisi

- La correlazione tra i rendimenti negativi estremi dei mercati azionari è **molto più alta** di quanto previsto dalla normale multivariata; quella dei positivi estremi no. Conta la direzione del mercato, non la volatilità in sé. [A] ([Longin & Solnik, JF 2001](https://faculty.essec.edu/en/research/1188-extreme-correlation-of-international-equity-markets))
- Le correlazioni tra azioni e mercato USA sono molto maggiori nei ribassi che nei rialzi. [A] (Ang & Chen, JFE 2002)
- **Implicazione:** la matrice di covarianza "normale" sottostima il rischio proprio quando serve. Il motore di rischio usa la stima di crisi (§3, punto 3) come limite, non la stima media.

## 5. Liquidità e affollamento

- **Spirali di liquidità:** la liquidità di mercato e il finanziamento dei trader si rinforzano: margini più alti costringono a vendere, i prezzi si allontanano dai fondamentali, le perdite crescono, i margini salgono ancora. [A] ([Brunnermeier & Pedersen, RFS 2009](https://markus.scholar.princeton.edu/document/98))
- **Agosto 2007:** fondi quant long/short con portafogli simili subiscono perdite senza precedenti nella settimana del 6 agosto; la spiegazione più accreditata è la liquidazione forzata di un fondo grande e il ritiro temporaneo dei market maker. Gli autori dichiarano le ipotesi speculative. [A per i fatti, M per la causa] ([Khandani & Lo, NBER w14465](https://nber.org/system/files/working_papers/w14465/w14465.pdf))
- **Lezione:** più pod di agenti con prompt simili, nutriti con le stesse notizie, tendono a produrre le *stesse* posizioni. Per questo i pod non vedono le posizioni altrui, i prompt hanno filosofie diverse e il Rischio misura la correlazione tra pod.

## 6. Rischio di controparte crypto

- Su IBKR l'esecuzione e la custodia delle crypto sono di **Paxos Trust Company** o **Zero Hash LLC**; IBKR non è parte delle transazioni e non custodisce le crypto; le crypto non sono protette dalla SIPC. [A] ([IBKR, commissioni crypto](https://www.interactivebrokers.com/en/pricing/commissions-cryptocurrencies.php))
- Le condizioni specifiche di IBKR Ireland (entità EEA) **non le ho trovate**: da verificare nell'accordo cliente di IBKR Ireland.
- Commissioni: 0,18% del controvalore fino a 100.000 USD al mese, 0,15% fino a 1 milione, 0,12% oltre; minimo 1,75 USD per ordine con tetto all'1% del controvalore. [A, stessa fonte; IBKR può cambiarle] Il valore 0,18% usato da GERVA-Q è quindi corretto per il nostro volume.
- **Limite per noi:** esposizione crypto totale per controparte ≤ 50% del NAV (oggi coincide con la quota della sleeve v3); segnalazione automatica se una controparte compare in notizie verificate di insolvenza.

## 7. Costi di transazione e impatto

### 7.1 Modello a radice quadrata

$$ I(Q) = Y\,\sigma_{d}\,\sqrt{\frac{Q}{V_d}} $$

$I$ = impatto medio relativo del metaordine, $\sigma_d$ = volatilità giornaliera, $Q$ = dimensione, $V_d$ = volume giornaliero, $Y$ = costante di ordine 1. L'esponente empirico sta intorno a 0,5. [A] ([Tóth et al., Phys. Rev. X 2011](https://www.arxiv.org/abs/1105.1694v3)) Almgren et al. (2005) stimano invece un esponente **3/5** per l'impatto temporaneo e separano una componente permanente. [A] ([paper](https://www.cis.upenn.edu/~mkearns/finread/costestim.pdf))

### 7.2 Quanto costa davvero

- Su 1.700 miliardi di dollari di ordini istituzionali reali (1998–2016, 21 mercati) l'impatto medio è **poco sotto 9 bp** (mediana poco sopra 6 bp); sale con la frazione del volume giornaliero scambiata, in modo concavo, e con la volatilità di mercato. [M per i numeri, da sintesi del paper] ([Frazzini, Israel & Moskowitz 2018, sintesi](https://alphaarchitect.com/the-best-research-paper-ever-written-on-trading-costs/))
- **Per noi:** con un NAV di 100.000 EUR e ordini da qualche migliaio di euro su ETF da milioni di volume, $Q/V_d$ è dell'ordine di $10^{-4}$–$10^{-5}$ e l'impatto è trascurabile rispetto allo spread e alla commissione. Il costo vero è **spread + commissione**. Il modello che usiamo:

$$ c = \underbrace{\text{commissione}}_{\text{tariffa IBKR}} + \underbrace{\tfrac12\,\text{spread}}_{\text{osservato}} + \underbrace{Y\sigma_d\sqrt{Q/V_d}}_{\text{impatto}}, \quad Y = 0{,}7 $$

Il valore $Y = 0{,}7$ è una scelta prudente dentro l'intervallo riportato in letteratura, non una stima nostra. [B per il valore esatto]

### 7.3 TCA (analisi dei costi a posteriori)

Ogni fill viene confrontato con:
- **implementation shortfall** = (prezzo medio di esecuzione − prezzo di decisione) / prezzo di decisione, con segno secondo il lato (Perold 1988);
- il costo previsto dal modello del §7.2 al momento dell'ordine.

L'Execution Monitor segnala quando lo scarto medio su 20 fill supera di 2 deviazioni standard il previsto. Questo è l'unico modo per sapere se il backtest ha costi realistici: GERVA-Q oggi usa 8 bp per ETF e 23 bp per crypto *stimati*, e non li ha mai confrontati con i fill reali.

## 8. Kill switch

- File `KILL` nella radice di GERVA-Q (già esistente) e nella radice di GERVA Capital: il Gateway rifiuta tutto, il Pod Zero cancella gli ordini aperti al giro successivo.
- Chi può crearlo: Andrea dal portale, oppure il **motore di rischio deterministico** quando scatta un limite di società. Gli agenti di rischio possono solo *raccomandarlo* (evento `risk.kill_recommended`).
- Chi può toglierlo: solo Andrea, dal portale.
