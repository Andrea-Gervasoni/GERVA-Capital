"""Portale e battito aprono il database insieme: la creazione del trigger delle previsioni non deve mai dare
'trigger forecasts_frozen already exists' (errore visto sul Mac il 5/11)."""
import threading

from firm import db


def test_many_connections_at_once(tmp_path):
    path = str(tmp_path / "c.db")
    db.connect(path)                               # il file esiste gia' (e' cosi' sul Mac); si riconnettono in tanti insieme
    errors = []
    barrier = threading.Barrier(12)

    def go():
        try:
            barrier.wait()
            for _ in range(3):
                db.reset_connection_cache()
                db.connect(path).execute("SELECT 1")
        except Exception as e:                     # noqa: BLE001
            errors.append(repr(e))

    ts = [threading.Thread(target=go) for _ in range(12)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors, errors[:2]
