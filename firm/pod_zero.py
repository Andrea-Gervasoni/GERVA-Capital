"""
Adattatore di SOLA LETTURA verso GERVA-Q v3 (Pod Zero, brief <ruolo_dei_dati_esistenti>).

Legge state/model_latest.json, state/crypto_latest.json, state/nav_log.csv, challenge/ledger.csv
e i log, per mostrare nel portale le posizioni target e il NAV del conto paper. Non si collega
mai al broker e non scrive nulla nella cartella di GERVA-Q.
"""
from __future__ import annotations

import csv
import glob
import hashlib
import json
import os

from . import paths


def _read_json(rel: str) -> dict | None:
    p = os.path.join(paths.GERVA_Q, rel)
    try:
        return json.load(open(p))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _read_csv(rel: str) -> list[dict]:
    p = os.path.join(paths.GERVA_Q, rel)
    try:
        return list(csv.DictReader(open(p)))
    except FileNotFoundError:
        return []


def available() -> bool:
    return os.path.isdir(paths.GERVA_Q)


def equity_model() -> dict | None:
    return _read_json("state/model_latest.json")


def crypto_model() -> dict | None:
    return _read_json("state/crypto_latest.json")


V3_START = "2026-11-03"     # da questa data live.py salva i pesi gia' moltiplicati per EQUITY_SHARE


def equity_scale(eq: dict) -> float:
    """live.py v3 scrive weights = pesi_v2 * EQUITY_SHARE (0,5). Il file del 30/10/2026 e' stato
    scritto dalla v2 (pesi non scalati: le azioni S4 valgono 1/6/4 = 0,0417). Per rappresentare
    il portafoglio v3 i pesi v2 vanno dimezzati, quelli v3 no."""
    return 1.0 if str(eq.get("asof", "")) >= V3_START else 0.5


def target_weights() -> dict[str, float]:
    """Pesi target sul NAV totale: quota azionaria + quota crypto
    (crypto_latest e' gia' moltiplicato per CRYPTO_SHARE in crypto_live.py)."""
    w = {}
    eq = equity_model()
    if eq:
        s = equity_scale(eq)
        for k, v in eq.get("weights", {}).items():
            w[k] = w.get(k, 0.0) + s * float(v)
    cr = crypto_model()
    if cr:
        for k, v in cr.get("weights", {}).items():
            w[k] = w.get(k, 0.0) + float(v)
    return w


def gross_fraction() -> float:
    return float(sum(abs(v) for v in target_weights().values()))


def crypto_fraction() -> float:
    cr = crypto_model()
    return float(sum(cr.get("weights", {}).values())) if cr else 0.0


def nav_log() -> list[dict]:
    return _read_csv("state/nav_log.csv")


def challenge_ledger() -> list[dict]:
    return _read_csv("challenge/ledger.csv")


def code_hash() -> str | None:
    """Stesso hash di report.py (SHA-256 dei *.py, primi 16 caratteri): verifica il congelamento."""
    files = sorted(glob.glob(os.path.join(paths.GERVA_Q, "*.py")))
    if not files:
        return None
    h = hashlib.sha256()
    for f in files:
        h.update(open(f, "rb").read())
    return h.hexdigest()[:16]


def summary() -> dict:
    eq, cr = equity_model(), crypto_model()
    navs = nav_log()
    return dict(disponibile=available(), percorso=paths.GERVA_Q,
                dati_al=eq.get("asof") if eq else None, candela_crypto=cr.get("bar") if cr else None,
                profilo=eq.get("profile") if eq else None, sleeves=eq.get("sleeves") if eq else {},
                pesi=target_weights(), lorda=gross_fraction(), quota_crypto=crypto_fraction(),
                nav_paper=float(navs[-1]["nav_eur"]) if navs else None,
                hash_codice=code_hash(), ledger_sfida=challenge_ledger()[-5:])
