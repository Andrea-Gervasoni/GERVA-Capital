"""
Raccolta notizie deterministica (nessun LLM): legge feed RSS/Atom di fonti ufficiali e testate
(config/feeds.yaml), salva titolo, link, dominio e un breve estratto. Il testo resta dato non
fidato: gli agenti lo ricevono dentro <dati_non_fidati>. Licenze: solo titolo, link ed estratto.
Senza rete (es. ambiente cloud) non fa nulla e lo dice.
"""
from __future__ import annotations

import html
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import yaml

from . import db, events, paths

UA = os.environ.get("SEC_USER_AGENT", "GERVA-Capital research bot")


def _strip(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()[:600]


def parse(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        g = {c.tag.split("}")[-1]: c for c in it}
        link = g.get("link")
        url = (link.get("href") if link is not None and link.get("href") else (link.text if link is not None else "")) or ""
        out.append(dict(title=_strip(g["title"].text if "title" in g else ""), url=url.strip(),
                        published=(g.get("pubDate") or g.get("updated") or g.get("published") or ET.Element("x")).text or "",
                        summary=_strip((g.get("description") or g.get("summary") or ET.Element("x")).text or "")))
    return out


def ingest(items: list[dict]) -> int:
    n = 0
    for i in items:
        if not i["url"] or db.one("SELECT id FROM news WHERE url=?", (i["url"],)):
            continue
        db.ex("INSERT INTO news(ts,title,url,domain,published,summary,status) VALUES(?,?,?,?,?,?,?)",
              (db.now_iso(), i["title"], i["url"], urlparse(i["url"]).netloc.replace("www.", ""),
               i["published"], i["summary"], "nuova"))
        n += 1
    return n


def fetch_all(timeout: int = 15) -> dict:
    feeds = yaml.safe_load(open(os.path.join(paths.CONFIG, "feeds.yaml")))["feeds"]
    got, errors = 0, []
    for f in feeds:
        try:
            req = urllib.request.Request(f["url"], headers={"User-Agent": UA})
            got += ingest(parse(urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")))
        except Exception as e:
            errors.append(f"{f['name']}: {type(e).__name__}")
    if got:
        events.publish("news.fetched", "data_engineer", dict(nuove=got, errori=len(errors)))
    return dict(nuove=got, errori=errors)
