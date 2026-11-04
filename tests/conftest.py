import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


@pytest.fixture()
def firm_env(tmp_path, monkeypatch):
    """Societa' isolata: DB, token e limiti di rischio in una cartella temporanea."""
    from firm import paths, db, settings
    var = tmp_path / "var"
    var.mkdir()
    monkeypatch.setattr(paths, "VAR", str(var))
    monkeypatch.setattr(paths, "DB_PATH", str(var / "firm.sqlite"))
    monkeypatch.setattr(paths, "ANDREA_TOKEN", str(var / "andrea.token"))
    monkeypatch.setattr(paths, "KILL_FILE", str(tmp_path / "KILL"))
    monkeypatch.setattr(paths, "GERVA_Q", str(tmp_path / "gerva_q_assente"))
    risk = tmp_path / "risk_limits.yaml"
    shutil.copy(settings.RISK_FILE, risk)
    monkeypatch.setattr(settings, "RISK_FILE", str(risk))
    for k in [k for k in os.environ if k.endswith("_API_KEY")]:
        monkeypatch.delenv(k, raising=False)
    db.reset_connection_cache()
    yield tmp_path
    db.reset_connection_cache()
