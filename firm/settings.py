"""
Impostazioni della societa' (regole che solo Andrea puo' cambiare, dal portale).

Come si garantisce che "solo Andrea" le cambi:
  1. la scrittura richiede un `AndreaCapability`, costruibile solo con il segreto di var/andrea.token
     (file 0600 creato da `firm.py init`); il portale lo legge all'avvio e lo usa per le richieste
     che arrivano dal pannello Impostazioni;
  2. nessuno strumento degli agenti (llm/tools.py) espone questa funzione: lo verifica un test;
  3. ogni modifica finisce nell'audit log e nel bus eventi (settings.changed).
I limiti di rischio veri stanno in config/risk_limits.yaml: il portale li scrive con la stessa
capability; il motore di rischio li legge in sola lettura.
"""
from __future__ import annotations

import hmac
import json
import os
import secrets

import yaml

from . import db, audit, events, paths

DEFAULTS_FILE = os.path.join(paths.CONFIG, "settings_defaults.yaml")
# sul server il codice e' in sola lettura: i limiti modificati da Andrea stanno nel volume (GERVA_RISK_FILE)
RISK_FILE = os.environ.get("GERVA_RISK_FILE", os.path.join(paths.CONFIG, "risk_limits.yaml"))


class SettingsPermissionError(PermissionError):
    pass


class AndreaCapability:
    """Prova di identita' del pannello Impostazioni. Senza il token giusto non si costruisce."""

    def __init__(self, token: str):
        if not hmac.compare_digest(token, _read_token()):
            raise SettingsPermissionError("token non valido: solo Andrea modifica le impostazioni")
        self._ok = True


def ensure_token() -> str:
    p = paths.ANDREA_TOKEN
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if not os.path.exists(p):
        try:
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)      # 0600 fin dalla creazione
            with os.fdopen(fd, "w") as f:
                f.write(secrets.token_urlsafe(32))
        except FileExistsError:
            pass
    return _read_token()


def _read_token() -> str:
    try:
        return open(paths.ANDREA_TOKEN).read().strip()
    except FileNotFoundError:
        return secrets.token_urlsafe(32)        # nessun token: nessuno puo' scrivere


def defaults() -> dict:
    return yaml.safe_load(open(DEFAULTS_FILE))


def _flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and not k.endswith("_map"):
            out.update(_flatten(v, key + "."))
        else:
            out[key] = v
    return out


def get(key: str, default=None):
    r = db.one("SELECT value FROM settings WHERE key=?", (key,))
    if r:
        return json.loads(r["value"])
    flat = _flatten(defaults())
    return flat.get(key, default)


def all_settings() -> dict:
    flat = _flatten(defaults())
    for r in db.q("SELECT key, value FROM settings"):
        flat[r["key"]] = json.loads(r["value"])
    return flat


def validate(key: str, value, default):
    """Stesso tipo del valore di partenza, numeri finiti e non negativi (un budget a -5 non ha senso)."""
    import math
    num = (int, float)
    if isinstance(default, bool):
        if not isinstance(value, bool):
            raise TypeError(f"{key}: serve vero/falso")
    elif isinstance(default, num):
        if isinstance(value, bool) or not isinstance(value, num) or not math.isfinite(value):
            raise TypeError(f"{key}: serve un numero")
        if value < 0 <= default:
            raise ValueError(f"{key}: non puo' essere negativo")
    elif isinstance(default, str):
        if not isinstance(value, str) or len(value) > 500:
            raise TypeError(f"{key}: serve un testo (massimo 500 caratteri)")
    elif isinstance(default, dict):
        if not isinstance(value, dict):
            raise TypeError(f"{key}: serve un oggetto chiave: valore")
        for k, v in value.items():
            if k in default:
                validate(f"{key}.{k}", v, default[k])
    elif isinstance(default, list):
        if not isinstance(value, list):
            raise TypeError(f"{key}: serve un elenco")
    return value


def set(key: str, value, cap: AndreaCapability):
    if not isinstance(cap, AndreaCapability) or not getattr(cap, "_ok", False):
        raise SettingsPermissionError("solo Andrea modifica le impostazioni")
    known = _flatten(defaults())
    if key not in known:
        raise KeyError(f"impostazione sconosciuta: {key}")
    validate(key, value, known[key])
    old = get(key)
    db.ex("INSERT INTO settings(key,value,updated_ts,updated_by) VALUES(?,?,?,?) "
          "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_ts=excluded.updated_ts, "
          "updated_by=excluded.updated_by", (key, db.dumps(value), db.now_iso(), "andrea"))
    events.publish("settings.changed", "andrea", dict(key=key, old=old, new=value))
    return value


# ---------------------------------------------------------------------------
# Limiti di rischio (file YAML, scritto solo dal portale con la capability)
# ---------------------------------------------------------------------------
def risk_limits() -> dict:
    return yaml.safe_load(open(RISK_FILE))


def set_risk_limit(path: str, value, cap: AndreaCapability):
    if not isinstance(cap, AndreaCapability) or not getattr(cap, "_ok", False):
        raise SettingsPermissionError("solo Andrea modifica i limiti di rischio")
    data = risk_limits()
    node = data
    parts = path.split(".")
    for p in parts[:-1]:
        node = node[p]
    if parts[-1] not in node:
        raise KeyError(path)
    old = node[parts[-1]]
    validate(f"risk_limits.{path}", value, old)
    node[parts[-1]] = value
    tmp = RISK_FILE + ".tmp"
    with open(tmp, "w") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    os.replace(tmp, RISK_FILE)
    events.publish("settings.changed", "andrea", dict(key=f"risk_limits.{path}", old=old, new=value))
    audit.log("andrea", "risk_limits.changed", dict(path=path, old=old, new=value))
