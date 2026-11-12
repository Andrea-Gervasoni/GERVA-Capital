"""
Dalle debolezze alle correzioni, con un validatore che non e' chi propone.

Una correzione e' una REGOLA dichiarativa sul contesto del trade:

    se  <grandezza> <operatore> <valore>   allora   taglia del trade x m      con m = 0 (salta) oppure 0,5 (dimezza)

Niente codice generato: una regola e' un dato, si legge in una riga, e per costruzione puo' solo ridurre il rischio.

Percorso di una regola:
    PROPOSTA -> validate() -> RESPINTA                       (quasi sempre: e' il comportamento atteso)
                           -> IN_OMBRA   si misura sui trade paper senza agire
                                         -> PROMUOVIBILE     quando regge anche sui trade paper
                                                             -> ATTIVA   solo con `learn --approve ID --confirm` di Andrea

Validazione (tutte le condizioni insieme; soglie fisse, non configurabili da un agente):
  1. in campione (trade fino al 31/12/2022): i trade colpiti dalla regola hanno R medio negativo, con t <= -soglia;
  2. la soglia NON e' fissa: e' il massimo atteso di |t| tra tutte le ipotesi provate finora, sqrt(2 ln K), mai sotto 2.
     Ogni ipotesi provata resta nel registro per sempre: cercare di piu' alza la soglia;
  3. fuori campione (dal 2023): i trade colpiti rendono meno degli altri E meno di zero;
  4. walk-forward: in almeno il 60% degli anni con almeno 5 trade colpiti, questi rendono meno degli altri;
  5. robustezza: per le soglie numeriche, spostando la soglia del 20% in entrambe le direzioni il segno non cambia;
  6. la regola non toglie piu' di meta' dei trade e ne colpisce almeno 30 in campione e 15 fuori.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .evaluate import weaknesses

SPLIT = "2022-12-31"
OPS = ("<=", ">", "==")
MULTS = (0.0, 0.5)
MIN_IS, MIN_OOS, MAX_SHARE, WF_MIN_YEARS_SHARE = 30, 15, 0.5, 0.6
SHADOW_MIN_TRADES = 20
PROPOSE_T = -1.3                # una fetta diventa IPOTESI gia' a t <= -1,3: proporre e' facile, passare la validazione no
STATES = ("RESPINTA", "IN_OMBRA", "PROMUOVIBILE", "ATTIVA", "RITIRATA")


@dataclass(frozen=True)
class Rule:
    feature: str
    op: str
    value: float | int | str
    mult: float = 0.0
    origin: str = "valutazione"        # chi l'ha proposta: "valutazione" (codice) | "llm" | "andrea"

    def __post_init__(self):
        if self.op not in OPS:
            raise ValueError(f"operatore non ammesso: {self.op}")
        if self.mult not in MULTS:
            raise ValueError("una regola puo' solo saltare (0) o dimezzare (0,5) un trade: mai aumentare")

    @property
    def id(self) -> str:
        raw = f"{self.feature}|{self.op}|{self.value}|{self.mult}"
        return hashlib.sha1(raw.encode()).hexdigest()[:10]

    def text(self) -> str:
        return f"se {self.feature} {self.op} {self.value}: " + ("salta il trade" if self.mult == 0 else "dimezza la taglia")

    def mask(self, df: pd.DataFrame) -> np.ndarray:
        if self.feature not in df.columns:
            return np.zeros(len(df), bool)
        x = df[self.feature]
        m = (x <= self.value) if self.op == "<=" else (x > self.value) if self.op == ">" else (x == self.value)
        return m.fillna(False).to_numpy(bool)

    def hits(self, ctx: dict) -> bool:
        v = (ctx or {}).get(self.feature)
        if v is None:
            return False                       # dato mancante: la regola non scatta
        try:
            return bool(v <= self.value) if self.op == "<=" else bool(v > self.value) if self.op == ">" else bool(v == self.value)
        except TypeError:
            return False


class Registry:
    """Registro a sola aggiunta delle ipotesi: ogni riga e' un evento (proposta, verdetto, ombra, approvazione)."""

    def __init__(self, path: str):
        self.path = path

    def _events(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        with open(self.path) as f:
            return [json.loads(x) for x in f if x.strip()]

    def log(self, rule: Rule, state: str, detail: dict | None = None, by: str = "codice") -> None:
        if state not in STATES:
            raise ValueError(state)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(dict(ts=time.time(), id=rule.id, rule=asdict(rule), state=state, by=by, detail=detail or {}),
                               ensure_ascii=False, default=str) + "\n")

    def current(self) -> dict[str, dict]:
        """id -> ultimo evento."""
        out = {}
        for e in self._events():
            out[e["id"]] = e
        return out

    def tried(self) -> int:
        """Numero di ipotesi distinte mai provate: e' il K della soglia statistica."""
        return len({e["id"] for e in self._events()})

    def rules(self, state: str) -> list[Rule]:
        return [Rule(**e["rule"]) for e in self.current().values() if e["state"] == state]


def threshold(k: int) -> float:
    """|t| atteso dal migliore di k tentativi senza alcun effetto vero (approssimazione di Gumbel), mai sotto 2."""
    return max(2.0, math.sqrt(2.0 * math.log(max(k, 1))))


def propose(df: pd.DataFrame, registry: Registry, max_new: int = 6, llm=None) -> list[Rule]:
    """Ipotesi dalle debolezze trovate SUL SOLO periodo di scelta. Le regole gia' nel registro non si ripropongono.
    llm: funzione facoltativa (debolezze, grandezze ammesse) -> lista di dict regola; le sue proposte passano dallo stesso
    validatore e sono rifiutate se usano grandezze o operatori non ammessi."""
    sel = df[df["entry_time"] <= SPLIT]
    known = set(registry.current())
    out = []
    for w in weaknesses(sel, ref=sel, t_min=PROPOSE_T):
        for mult in MULTS:
            r = Rule(mult=mult, **w["rule"])
            if r.id not in known and r.id not in {x.id for x in out}:
                out.append(r)
    if llm is not None:
        try:
            for raw in llm(weaknesses(sel, ref=sel, t_min=PROPOSE_T), sorted(df.columns)) or []:
                r = Rule(feature=str(raw["feature"]), op=str(raw["op"]), value=raw["value"], mult=float(raw.get("mult", 0.0)), origin="llm")
                if r.feature in df.columns and r.id not in known and r.id not in {x.id for x in out}:
                    out.append(r)
        except Exception:
            pass                                # una proposta malformata dell'LLM non ferma il ciclo: si ignora
    return out[:max_new]


def _cmp(df: pd.DataFrame, m: np.ndarray) -> dict:
    a, b = df["R"].to_numpy(float)[m], df["R"].to_numpy(float)[~m]
    if len(a) < 2 or len(b) < 2:
        return dict(n=int(len(a)), mean=None, rest=None, t0=None)
    sd = a.std(ddof=1)
    return dict(n=int(len(a)), mean=float(a.mean()), rest=float(b.mean()), t0=float(a.mean() / sd * math.sqrt(len(a))) if sd > 0 else 0.0)


def validate(rule: Rule, df: pd.DataFrame, k_tried: int) -> dict:
    """Verdetto deterministico. Restituisce stato ('IN_OMBRA' | 'RESPINTA'), le prove e il motivo di ogni bocciatura."""
    sel, ver = df[df["entry_time"] <= SPLIT], df[df["entry_time"] > SPLIT]
    ms, mv = rule.mask(sel), rule.mask(ver)
    i, o = _cmp(sel, ms), _cmp(ver, mv)
    thr = threshold(k_tried)
    checks, fails = {}, []

    def check(name, ok, why):
        checks[name] = bool(ok)
        if not ok:
            fails.append(why)

    check("numerosita", i["n"] >= MIN_IS and o["n"] >= MIN_OOS, f"pochi trade colpiti (scelta {i['n']}, verifica {o['n']})")
    check("quota", ms.mean() <= MAX_SHARE if len(ms) else False, "la regola toglie piu' di meta' dei trade")
    check("in_campione", i["t0"] is not None and i["mean"] < 0 and i["t0"] <= -thr,
          f"in scelta R medio {i['mean']}, t {i['t0']}: serve t <= -{thr:.2f} dopo {k_tried} ipotesi")
    check("fuori_campione", o["mean"] is not None and o["mean"] < 0 and o["mean"] < o["rest"],
          f"in verifica i trade colpiti rendono {o['mean']} contro {o['rest']} degli altri")
    yrs = []
    for _, g in df.groupby(df["entry_time"].dt.year):
        m = rule.mask(g)
        if m.sum() >= 5 and (~m).sum() >= 5:
            yrs.append(g["R"].to_numpy(float)[m].mean() < g["R"].to_numpy(float)[~m].mean())
    wf = float(np.mean(yrs)) if yrs else 0.0
    check("walk_forward", len(yrs) >= 3 and wf >= WF_MIN_YEARS_SHARE, f"regge nel {wf:.0%} degli anni ({len(yrs)} anni utili): serve il 60%")
    if rule.op in ("<=", ">") and isinstance(rule.value, (int, float)):
        ok = True
        for f in (0.8, 1.2):
            v = rule.value * f if rule.value != 0 else rule.value + (f - 1)
            c = _cmp(sel, Rule(rule.feature, rule.op, v, rule.mult).mask(sel))
            ok &= c["mean"] is not None and c["mean"] < c["rest"]
        check("soglie_vicine", ok, "spostando la soglia del 20% l'effetto cambia segno")
    else:
        checks["soglie_vicine"] = True
    gain = float(-(1 - rule.mult) * sel["R"].to_numpy(float)[ms].sum()) if len(sel) else 0.0
    gain_v = float(-(1 - rule.mult) * ver["R"].to_numpy(float)[mv].sum()) if len(ver) else 0.0
    return dict(state="IN_OMBRA" if not fails else "RESPINTA", checks=checks, fails=fails, threshold_t=thr, k_tried=k_tried,
                selection=i, verification=o, walk_forward=wf, gain_R_selection=gain, gain_R_verification=gain_v)


def shadow_report(rule: Rule, paper: pd.DataFrame) -> dict:
    """Come sarebbe andata la regola sui trade PAPER (mai usati per proporla ne' per validarla)."""
    if paper is None or not len(paper):
        return dict(n=0, ready=False)
    m = rule.mask(paper)
    c = _cmp(paper, m)
    ready = c["n"] >= SHADOW_MIN_TRADES and c["mean"] is not None and c["mean"] < c["rest"] and c["mean"] < 0
    return dict(n=c["n"], mean_R=c["mean"], rest_mean_R=c["rest"], ready=bool(ready), needed=SHADOW_MIN_TRADES)


def cycle(df: pd.DataFrame, registry: Registry, llm=None) -> dict:
    """Un giro di miglioramento: propone, valida, aggiorna l'ombra. Non attiva MAI nulla."""
    proposed = propose(df, registry, llm=llm)
    results = []
    for r in proposed:
        k = registry.tried() + 1
        v = validate(r, df, k)
        registry.log(r, v["state"], dict(checks=v["checks"], fails=v["fails"], threshold_t=v["threshold_t"], selection=v["selection"],
                                         verification=v["verification"]))
        results.append(dict(id=r.id, rule=r.text(), origin=r.origin, **v))
    paper = df[df["source"] != "sim"] if "source" in df.columns else df.iloc[0:0]
    shadow = []
    for r in registry.rules("IN_OMBRA") + registry.rules("PROMUOVIBILE"):
        s = shadow_report(r, paper)
        cur = registry.current()[r.id]["state"]
        if s["ready"] and cur == "IN_OMBRA":
            registry.log(r, "PROMUOVIBILE", s)
        shadow.append(dict(id=r.id, rule=r.text(), state="PROMUOVIBILE" if s["ready"] else cur, **s))
    return dict(proposed=results, shadow=shadow, active=[dict(id=r.id, rule=r.text()) for r in registry.rules("ATTIVA")],
                tried=registry.tried(), threshold_t=threshold(registry.tried() + 1))


def approve(registry: Registry, rule_id: str, by: str) -> Rule:
    """Attiva una regola. Solo da riga di comando, con --confirm: nessun agente ha uno strumento che la chiama."""
    cur = registry.current().get(rule_id)
    if cur is None:
        raise KeyError(f"regola sconosciuta: {rule_id}")
    if cur["state"] not in ("IN_OMBRA", "PROMUOVIBILE"):
        raise ValueError(f"la regola e' in stato {cur['state']}: si attivano solo regole che hanno passato la validazione")
    r = Rule(**cur["rule"])
    registry.log(r, "ATTIVA", dict(from_state=cur["state"]), by=by)
    return r


def retire(registry: Registry, rule_id: str, by: str) -> None:
    cur = registry.current().get(rule_id)
    if cur is None:
        raise KeyError(rule_id)
    registry.log(Rule(**cur["rule"]), "RITIRATA", by=by)


def multiplier(ctx: dict, rules: list[Rule]) -> tuple[float, list[str]]:
    """Moltiplicatore della taglia per un trade con questo contesto, date le regole ATTIVE. Sempre in [0, 1]."""
    m, why = 1.0, []
    for r in rules:
        if r.hits(ctx):
            m = min(m, r.mult)
            why.append(r.text())
    return max(0.0, min(1.0, m)), why
