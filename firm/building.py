"""
L'edificio e gli uffici.

  * Livello dell'edificio = funzione del MASSIMO STORICO del valore della societa' (NAV paper sopra
    i 100.000 EUR iniziali). Non scende mai: un drawdown congela la crescita, non toglie i servizi.
    I servizi sbloccati valgono per tutti.
  * Ufficio = funzione del grado: suite d'angolo per il Capo, uffici privati per manager e head,
    uffici a vetri per i senior, open space per analisti e stagisti. Uffici piu' semplici per i gradi
    bassi, mai degradati. L'arredo cresce con il grado, con il livello dell'edificio e con i
    Gerva-Coin maturati (trofei, acquario, quadro d'oro).
E' uno strato di rappresentazione: non cambia nessuna regola di rischio.
"""
from __future__ import annotations

from . import db, gateway, economy

LEVELS = [
    # soglia sul massimo storico del rendimento, nome, servizio sbloccato
    (0.000, "Startup", "caffe", "Angolo caffe' e distributore d'acqua"),
    (0.005, "Crescita", "lounge", "Lounge con divani e piante"),
    (0.015, "Affermata", "mensa", "Mensa aziendale"),
    (0.030, "Solida", "palestra", "Palestra"),
    (0.060, "Prestigio", "biblioteca", "Biblioteca e sala silenziosa"),
    (0.100, "Eccellenza", "terrazza", "Terrazza panoramica e sala giochi"),
]

CAPACITY = {"ceo": 1, "privato": 4, "vetro": 6, "open": 12, "ops": 6, "trading": 2}
TRADING_CODE = ("pod_zero", "execution_monitor")


def value() -> dict:
    fb = gateway.firm_book()
    marks = [r["nav"] for r in db.q("SELECT nav FROM nav_marks WHERE pod='firm'")]
    hwm = max(marks + [fb["nav"], gateway.firm_start()])
    return dict(nav=fb["nav"], massimo=hwm, rendimento=fb["nav"] / gateway.firm_start() - 1,
                rendimento_massimo=hwm / gateway.firm_start() - 1)


def level() -> dict:
    v = value()
    lv = max(i for i, (thr, *_r) in enumerate(LEVELS) if v["rendimento_massimo"] >= thr)
    lv = max(lv, int(db.runtime_get("building.level", 0) or 0))          # monotono
    db.runtime_set("building.level", lv)
    nxt = LEVELS[lv + 1] if lv + 1 < len(LEVELS) else None
    prog = None
    if nxt:
        lo, hi = LEVELS[lv][0], nxt[0]
        prog = max(0.0, min(1.0, (v["rendimento_massimo"] - lo) / (hi - lo)))
    return dict(livello=lv, nome=LEVELS[lv][1], valore=v,
                servizi=[dict(id=s, nome=d, soglia=t, attivo=i <= lv) for i, (t, _n, s, d) in enumerate(LEVELS)],
                prossimo=dict(nome=nxt[1], soglia=nxt[0], servizio=nxt[3], progresso=prog) if nxt else None)


def tier_of(agent: dict) -> str:
    if agent["kind"] == "code":
        return "trading" if agent["id"] in TRADING_CODE else "ops"
    if agent["id"] == "capo":
        return "ceo"
    if agent["grade"] >= 5:
        return "privato"
    if agent["grade"] == 4:
        return "vetro"
    return "open"


FURNITURE = {
    "ceo": ["scrivania_executive", "poltrona_pelle", "monitor3", "divano", "divano2", "tavolino", "bar", "globo",
            "quadro_grande", "libreria_parete", "tappeto_lusso", "piante_lusso", "trofei", "vista_panoramica"],
    "privato": ["scrivania_grande", "poltrona", "monitor3", "pianta_grande", "libreria", "quadro", "tappeto", "finestra",
                "sedia_ospite"],
    "vetro": ["scrivania_legno", "sedia_ergonomica", "monitor2", "pianta", "libreria_piccola", "tappeto_piccolo",
              "sedia_ospite"],
    "open": ["scrivania_base", "sedia_base", "monitor1"],
    "ops": ["rack", "terminale"],
    "trading": ["schermi_trading", "terminale"],
}


def furniture(agent: dict, tier: str, lv: int) -> list[str]:
    f = list(FURNITURE[tier])
    if tier == "privato" and agent["grade"] >= 6:
        f += ["divano", "tavolino"]
    if tier == "open" and agent["grade"] >= 2:
        f += ["monitor2", "pianta_piccola", "lampada"]
    if lv >= 1 and "pianta_piccola" not in f and tier == "open":
        f.append("pianta_piccola")
    if lv >= 3 and "sedia_base" in f:
        f[f.index("sedia_base")] = "sedia_ergonomica"
    if agent["kind"] == "llm":
        gc = economy.gc_balance(agent["id"])
        if gc >= 100:
            f.append("trofeo")
        if gc >= 300:
            f.append("acquario")
        if gc >= 1000:
            f.append("quadro_oro")
    return f


def offices() -> list[dict]:
    from . import registry
    lv = level()["livello"]
    agents = registry.all_agents()
    used = {k: 0 for k in CAPACITY}
    out = []
    # prima gli agenti attivi (grado piu' alto per primo), poi le posizioni aperte nei posti rimasti
    order = sorted(agents, key=lambda a: (a["kind"] == "open", -a["grade"], a["id"]))
    for a in order:
        tier = tier_of(a)
        while used.get(tier, 0) >= CAPACITY.get(tier, 0):
            tier = {"ceo": "privato", "privato": "vetro", "vetro": "open"}.get(tier)
            if tier is None:
                break
        if tier is None:
            continue
        slot = used[tier]
        used[tier] += 1
        out.append(dict(agent_id=a["id"], tier=tier, slot=slot, vacante=a["kind"] == "open",
                        arredo=[] if a["kind"] == "open" else furniture(a, tier, lv)))
    return out
