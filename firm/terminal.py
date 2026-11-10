"""Read-only operational terminal. Raw account observations, never fabricated returns."""
import math
import json
from . import db, health


def snapshot():
    # Latest observation for each UTC day; no outlier filter hiding losses.
    rows = db.q("SELECT day, nav FROM nav_marks WHERE pod='pod_zero' ORDER BY day")
    days = {}
    for r in db.q("SELECT ts, nav FROM nav_ticks WHERE id IN (SELECT MAX(id) FROM nav_ticks GROUP BY substr(ts,1,10)) ORDER BY ts, id"):
        days[r['ts'][:10]] = r['nav']
    # Marks are updated more frequently than sampled ticks by the live observer.
    days.update({r['day']: r['nav'] for r in rows})
    curve, peak = [], 0.0
    invalid = 0
    for day, value in sorted(days.items()):
        if value is None or not math.isfinite(float(value)) or float(value) <= 0:
            invalid += 1
            continue
        value = float(value)
        peak = max(peak, value)
        curve.append(dict(t=day, nav=value, drawdown=value / peak - 1))
    trials = db.q("SELECT family, status, COUNT(*) n FROM trials GROUP BY family, status ORDER BY family, status")
    incidents = db.q("SELECT ts, actor, kind, payload FROM events WHERE kind IN ('risk.alert','risk.kill') ORDER BY id DESC LIMIT 8")
    for r in incidents:
        payload = json.loads(r.pop('payload'))
        r['message'] = payload.get('cosa') or payload.get('motivo') or r['kind']
    return dict(asof=db.now_iso(), health=health.status(), curve=curve[-365:], observations=len(curve), invalid=invalid,
                nav=curve[-1]['nav'] if curve else None,
                change=curve[-1]['nav'] / curve[0]['nav'] - 1 if curve else None,
                max_drawdown=min((r['drawdown'] for r in curve), default=None),
                trials=trials, incidents=incidents,
                note='NAV IBKR osservato, non rendimento depurato da versamenti/prelievi. Nessun filtro aggiuntivo sugli scostamenti; i dati possono già essere stati filtrati alla raccolta. Flessione dal massimo sullo storico disponibile; grafico limitato agli ultimi 365 punti.')
