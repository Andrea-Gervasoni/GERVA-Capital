"""
Filtro dei dati sensibili (regola inviolabile 6).

Si applica a: tutto cio' che esce verso un LLM (soprattutto esterno), tutto cio' che entra
nell'audit log e negli eventi del portale. Toglie:
  * chiavi API (formati Anthropic, OpenAI, Google, generici sk-..., Bearer ...);
  * numeri di conto IBKR (DU/U seguiti da cifre);
  * valori delle variabili segrete presenti in .env / ambiente;
  * NAV reale se marcato (campi 'nav_real', 'account', 'password', 'secret', 'token', 'api_key').
Meglio un falso positivo (testo oscurato inutilmente) che un segreto in un log.
"""
from __future__ import annotations

import os
import re

PATTERNS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"), "[CHIAVE]"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), "[CHIAVE]"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}"), "[CHIAVE]"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9\._\-]{12,}"), "Bearer [CHIAVE]"),
    (re.compile(r"\b(?:DU|DF|U)\d{5,9}\b"), "[CONTO]"),
]
SENSITIVE_KEYS = {"nav_real", "account", "account_id", "password", "secret", "token",
                  "api_key", "apikey", "authorization"}
SECRET_ENV_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD")


def _env_secrets() -> list[str]:
    vals = []
    for k, v in os.environ.items():
        if any(h in k.upper() for h in SECRET_ENV_HINTS) and v and len(v) >= 8:
            vals.append(v)
    return sorted(set(vals), key=len, reverse=True)


def text(s: str) -> str:
    if not isinstance(s, str):
        return s
    for v in _env_secrets():
        s = s.replace(v, "[SEGRETO]")
    for rx, rep in PATTERNS:
        s = rx.sub(rep, s)
    return s


def obj(x):
    """Filtro ricorsivo su dict/list/str."""
    if isinstance(x, dict):
        return {k: ("[OSCURATO]" if str(k).lower() in SENSITIVE_KEYS else obj(v)) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [obj(v) for v in x]
    if isinstance(x, str):
        return text(x)
    return x
