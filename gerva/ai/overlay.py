"""
L'overlay: l'unica cosa che il livello AI puo' consegnare al ciclo live.

    {"ts": ..., "expires": ..., "sleeves": {"CR-TREND": {"mult": 0.5, "motivo": "...", "fonti": ["id1"]}, ...},
     "global": {"mult": 0.7, "motivo": "regime teso"}}

Validazione (in codice, non a parole):
  * ogni moltiplicatore sta in [0, 1]: un valore sopra 1 o non numerico rende NULLO l'intero overlay;
  * un overlay scaduto o illeggibile vale 1 ovunque (il sistema torna al comportamento di base, mai a uno piu' rischioso);
  * il file si scrive in modo atomico; il ciclo lo legge soltanto.
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field

MAX_TTL = 48 * 3600.0


@dataclass
class Overlay:
    sleeves: dict = field(default_factory=dict)        # id -> {"mult", "motivo", "fonti"}
    global_mult: float = 1.0
    global_reason: str = ""
    ts: float = 0.0
    expires: float = 0.0
    valid: bool = True
    note: str = ""

    def mult(self, sleeve: str) -> float:
        if not self.valid:
            return 1.0
        return float(self.sleeves.get(sleeve, {}).get("mult", 1.0)) * self.global_mult


def _ok(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and 0.0 <= x <= 1.0


def validate(raw: dict, now: float | None = None) -> Overlay:
    now = now or time.time()
    try:
        ts, exp = float(raw["ts"]), float(raw["expires"])
        sleeves = raw.get("sleeves") or {}
        g = raw.get("global") or {}
        gm = g.get("mult", 1.0)
        if not _ok(gm) or not all(_ok(v.get("mult")) for v in sleeves.values()):
            return Overlay(valid=False, note="moltiplicatore fuori da [0, 1]: overlay ignorato")
        if exp <= now or exp - ts > MAX_TTL or ts > now + 300:
            return Overlay(valid=False, note="overlay scaduto o con date non plausibili: ignorato")
        return Overlay({k: dict(mult=float(v["mult"]), motivo=str(v.get("motivo", ""))[:300], fonti=list(v.get("fonti", []))[:10])
                        for k, v in sleeves.items()}, float(gm), str(g.get("motivo", ""))[:300], ts, exp)
    except (KeyError, TypeError, ValueError, AttributeError):
        return Overlay(valid=False, note="overlay malformato: ignorato")


def load(path: str, now: float | None = None) -> Overlay:
    try:
        with open(path) as f:
            return validate(json.load(f), now)
    except FileNotFoundError:
        return Overlay(note="nessun overlay")
    except (OSError, json.JSONDecodeError):
        return Overlay(valid=False, note="overlay illeggibile: ignorato")


def combine(parts: list[dict], ttl: float = 24 * 3600.0, now: float | None = None) -> dict:
    """Unisce piu' fonti (agenti, regime, decadimento) prendendo per ogni strategia il moltiplicatore PIU' BASSO."""
    now = now or time.time()
    sleeves, g, gwhy = {}, 1.0, []
    for p in parts:
        gm = (p.get("global") or {}).get("mult", 1.0)
        if _ok(gm) and gm < 1.0:
            g = min(g, gm)
            gwhy.append(str((p.get("global") or {}).get("motivo", "")))
        for k, v in (p.get("sleeves") or {}).items():
            if not _ok(v.get("mult")):
                continue
            cur = sleeves.get(k, dict(mult=1.0, motivo="", fonti=[]))
            if v["mult"] < cur["mult"]:
                cur = dict(mult=float(v["mult"]), motivo=str(v.get("motivo", "")), fonti=list(v.get("fonti", [])))
            sleeves[k] = cur
    return dict(ts=now, expires=now + min(ttl, MAX_TTL), sleeves=sleeves, **{"global": dict(mult=g, motivo="; ".join(x for x in gwhy if x))})


def save(path: str, raw: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(raw, f)
    os.replace(tmp, path)
