"""
Il consiglio di ricerca: piu' agenti che collaborano, con il codice come arbitro.

    Proponente  ->  scrive una scheda (ipotesi + parametri) senza vedere i risultati
    Motore      ->  valida la scheda, esegue il backtest standard, conta la prova nel registro
    Critico     ->  riceve i risultati SENZA il nome dell'autore e deve indicare almeno un difetto concreto
    Rischio     ->  puo' solo porre il veto (mai approvare) con un motivo verificabile
    Decisione   ->  la prende `Council.review`: passa se il cancello numerico passa E non c'e' veto

Perche' cosi' (e non agenti che "dibattono" e poi tradano):
  * nei test indipendenti gli agenti LLM che decidono le operazioni non battono l'indice dopo i costi
    (FINSABER, StockBench, Alpha Arena: vedi docs/archivio_RIFONDAZIONE_v2.md, sezione 2.6);
  * un LLM e' utile per generare ipotesi e trovare difetti, cioe' dove un errore costa una prova in piu', non denaro;
  * il dibattito non migliora la decisione a parita' di calcolo; pareri indipendenti aggregati da codice si'.

I ruoli sono funzioni `contesto -> dict`. `default_roles()` ne da' di deterministici (funzionano senza chiave API);
`firm_role(agent_id, ...)` usa gli agenti LLM gia' definiti in agents/ tramite llm.runtime, con il loro budget.
"""
from __future__ import annotations

from typing import Callable

from .spec import FAMILIES, StrategySpec, TrialRegistry, evaluate, gate

BASELINE_TRIALS = 2514         # prove gia' consumate: 812 fino alla v4 + 1.702 dei dieci analisti (research/v5/v5)


def default_roles() -> dict[str, Callable]:
    def critic(ctx: dict) -> dict:
        r, flaws = ctx["result"], []
        if not r.get("valida"):
            return dict(difetti=r.get("errori", []))
        if r["sharpe_scelta"] and r["sharpe_verifica"] is not None and r["sharpe_verifica"] < 0.5 * r["sharpe_scelta"]:
            flaws.append(f"lo Sharpe di verifica ({r['sharpe_verifica']:.2f}) e' meno della meta' di quello di scelta "
                         f"({r['sharpe_scelta']:.2f}): possibile sovradattamento")
        if r["sharpe_ritardo_1g"] is not None and r["sharpe"] and r["sharpe_ritardo_1g"] < 0.6 * r["sharpe"]:
            flaws.append("il risultato dipende dall'eseguire esattamente sulla chiusura del segnale")
        if r["sharpe_costi_doppi"] is not None and r["sharpe"] and r["sharpe_costi_doppi"] < 0.7 * r["sharpe"]:
            flaws.append("il risultato e' sensibile ai costi: va verificato con le commissioni vere della sede")
        if not flaws:
            flaws.append(f"{r.get('anni_scelta', 0):.0f} anni di scelta sono pochi: l'errore standard dello Sharpe e' "
                         f"±{(1 / max(r.get('anni_scelta') or 1, 1)) ** 0.5:.2f}")
        return dict(difetti=flaws)

    def risk(ctx: dict) -> dict:
        r = ctx["result"]
        if r.get("valida") and (r["max_dd"] or 0) < -0.35:
            return dict(veto=True, motivo=f"caduta massima {r['max_dd']:.0%}: oltre il 35% non entra in un portafoglio a leva")
        if r.get("valida") and (r["mese_peggiore"] or 0) < -0.25:
            return dict(veto=True, motivo=f"mese peggiore {r['mese_peggiore']:.0%}")
        return dict(veto=False, motivo="")
    return dict(critic=critic, risk=risk)


def firm_role(agent_id: str, task: str, schema: dict) -> Callable:
    """Un ruolo affidato a un agente LLM della societa' (agents/<id>). Senza chiave risponde il simulatore."""
    def role(ctx: dict) -> dict:
        from llm import runtime                      # import pigro: il consiglio funziona anche senza la societa' inizializzata
        data = {k: v for k, v in ctx["result"].items() if k != "excess"} if "result" in ctx else {"famiglie": FAMILIES}
        out = runtime.call(agent_id, task, data=data, schema=schema, purpose="consiglio_ricerca")
        return out["output"] if out.get("ok") else {}
    return role


class Council:
    def __init__(self, lab, registry_path: str, roles: dict | None = None):
        self.lab, self.reg = lab, TrialRegistry(registry_path)
        self.roles = roles or default_roles()

    def review(self, spec: StrategySpec) -> dict:
        res = evaluate(spec, self.lab)
        n = BASELINE_TRIALS + self.reg.count() + 1
        verdict = gate(res, n)
        ctx = dict(result={k: v for k, v in res.items() if k != "excess"} | {"spec": {**res["spec"], "author": "(nascosto)"}})
        critique = self.roles["critic"](ctx) or {}
        veto = self.roles["risk"](ctx) or {}
        if not critique.get("difetti"):
            verdict = dict(verdict, passa=False, motivi=verdict["motivi"] + ["il critico non ha indicato alcun difetto: revisione non valida"])
        if veto.get("veto"):
            verdict = dict(verdict, passa=False, motivi=verdict["motivi"] + [f"veto del rischio: {veto.get('motivo', '')}"])
        row = self.reg.append(res, verdict)
        return dict(esito="AMMESSA AL PAPER TRADING" if verdict["passa"] else "RESPINTA", verdetto=verdict,
                    difetti=critique.get("difetti", []), veto=veto, registro=row["hash"],
                    numeri={k: res.get(k) for k in ("sharpe", "sharpe_scelta", "sharpe_verifica", "sharpe_costi_doppi",
                                                    "sharpe_ritardo_1g", "cagr", "vol", "max_dd")})

    def session(self, proposer: Callable[[dict], dict], rounds: int = 3) -> list[dict]:
        """Un giro di ricerca: il proponente vede l'elenco delle schede gia' provate (non i loro Sharpe) e propone."""
        out = []
        for _ in range(rounds):
            seen = [r["spec"] for r in self.reg.rows()]
            raw = proposer(dict(famiglie=FAMILIES, gia_provate=seen)) or {}
            try:
                spec = StrategySpec(**{k: raw[k] for k in ("family", "universe", "params", "hypothesis")}, author=raw.get("author", "agente"))
            except (KeyError, TypeError):
                out.append(dict(esito="RESPINTA", verdetto=dict(passa=False, motivi=["scheda malformata"])))
                continue
            out.append(self.review(spec))
        return out
