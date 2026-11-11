"""
Raccolta delle fonti per il desk: la fa il CODICE, non l'LLM (che cosi' non puo' inventarsi una notizia).

Solo fonti gratuite e senza chiave, usabili in automatico. Ogni voce ha un id stabile (hash di origine + titolo),
cosi' una citazione dell'LLM si puo' controllare. Una fonte che non risponde viene saltata e segnalata: non ferma nulla.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (compatible; research-client)"}
RSS = {
    "fed": "https://www.federalreserve.gov/feeds/press_all.xml",
    "bce": "https://www.ecb.europa.eu/rss/press.html",
    "sec": "https://www.sec.gov/news/pressreleases.rss",
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "esma": "https://www.esma.europa.eu/rss.xml",
}


def _get(url: str, timeout: float = 20.0) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def _id(source: str, title: str) -> str:
    return hashlib.sha256(f"{source}|{title}".encode()).hexdigest()[:10]


def rss(source: str, url: str, limit: int = 15) -> list[dict]:
    root = ET.fromstring(_get(url))
    out = []
    for it in list(root.iter("item"))[:limit]:
        title = (it.findtext("title") or "").strip()
        text = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
        out.append(dict(id=_id(source, title), source=source, ts=(it.findtext("pubDate") or "")[:31], title=title,
                        text=text.strip()[:1500], url=(it.findtext("link") or "").strip()))
    return out


def fear_greed() -> list[dict]:
    d = json.loads(_get("https://api.alternative.me/fng/?limit=1"))["data"][0]
    title = f"Indice Fear & Greed crypto: {d['value']} ({d['value_classification']})"
    return [dict(id=_id("fng", title), source="alternative.me", ts=time.strftime("%Y-%m-%d"), title=title, text="", url="https://alternative.me/crypto/fear-and-greed-index/")]


def collect(sources: dict | None = None) -> tuple[list[dict], dict]:
    """(voci, errori per fonte)."""
    items, errors = [], {}
    for name, url in (sources or RSS).items():
        try:
            items += rss(name, url)
        except Exception as e:
            errors[name] = type(e).__name__
    try:
        items += fear_greed()
    except Exception as e:
        errors["fng"] = type(e).__name__
    seen, uniq = set(), []
    for it in items:
        if it["id"] not in seen:
            seen.add(it["id"])
            uniq.append(it)
    return uniq, errors
