"""La serie del conto: via i picchi di lettura, un punto ogni quarto d'ora, un movimento vero non si tocca."""
import datetime as dt
import random

from firm import navclean


def _series(minutes=3 * 24 * 60, step=1):
    rng = random.Random(3)
    t0 = dt.datetime(2026, 11, 5, 8, 0)
    out = []
    for m in range(0, minutes, step):
        v = 1_000_000 * (1 + rng.uniform(-0.0003, 0.0003))
        if m > 2 * 24 * 60:                                        # un movimento vero: +1,5% che resta
            v *= 1.015
        if 700 <= m < 703:                                         # picco in alto di 3 letture
            v *= 1.025
        if 1500 <= m < 1600:                                       # blocco in basso di quasi due ore
            v *= 0.974
        out.append(((t0 + dt.timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%S"), v))
    return out


def test_spikes_and_blocks_are_removed_real_moves_stay():
    raw = _series()
    c = navclean.clean(raw)
    assert len(c) < len(raw) / 10                                          # da ~4300 punti a ~290
    vals = [v for _, v in c]
    base = 1_000_000
    assert max(vals) < base * 1.017 and min(vals) > base * 0.99            # nessun picco: 2,5% in su e 2,6% in giu' spariti
    late = [v for t, v in c if t >= "2026-11-07T08:30"]
    assert len(late) > 30 and all(v > base * 1.012 for v in late)         # il +1,5% vero resta


def test_first_point_stays_and_short_series_untouched():
    pts = [("2026-11-05T08:00", 100.0), ("2026-11-05T08:01:00", 100.1), ("2026-11-05T08:02:00", 99.9)]
    assert navclean.clean(pts) == pts
    raw = _series(minutes=600)
    assert navclean.clean(raw)[0] == raw[0]
