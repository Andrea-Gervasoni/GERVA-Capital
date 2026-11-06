# Registro delle modifiche ai prompt

Ogni modifica: versione, motivo, effetto atteso. Si adotta solo se gli eval non peggiorano (guida §5).

## v2 — 4/11/2026 (tutti gli agenti LLM)
- Aggiunte le sezioni <incentivi> e <riunioni> e un carattere per agente.
- Motivo: richiesta di Andrea di ruoli più reali e affamati di soldi. Il rischio noto è che la fame di rendimento spinga a prendere rischi nascosti; il rimedio è scritto nel prompt E applicato dal codice (bonus differito, clawback, regola di Brier propria).
- Caratteri diversi per ridurre il collasso delle opinioni nelle riunioni (llm_agents_in_finance.md §5).
- Eval: schema invariato; i casi trappola esistenti restano obbligatori.

## 2026-11-06 — capi desk (pod_trend, pod_reversal, pod_crypto)
I pod sono spenti per scelta di Andrea: i tre ex capi pod diventano capi desk e propongono posizioni LONG per il conto
reale (paper). Il codice valida (firm/desk.py), GERVA-Q esegue. Rimossi dal prompt il capitale del 5% e le regole a scalini dei pod.
