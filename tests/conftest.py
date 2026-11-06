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
    # copia dei profili: i test (post-mortem, promozioni) non devono scrivere nei file versionati
    agents = tmp_path / "agents"
    shutil.copytree(paths.AGENTS, agents)
    for d, _, files in os.walk(agents):                 # nell'immagine il codice e' in sola lettura: la copia no
        os.chmod(d, 0o755)
        for f in files:
            os.chmod(os.path.join(d, f), 0o644)
    monkeypatch.setattr(paths, "AGENTS", str(agents))
    monkeypatch.setattr(paths, "RESEARCH", str(tmp_path / "research"))
    risk = tmp_path / "risk_limits.yaml"
    shutil.copy(settings.RISK_FILE, risk)
    # i test verificano il MECCANISMO dei limiti con i valori prudenti storici, non i numeri scelti da Andrea il 6/11
    import yaml
    lim = yaml.safe_load(open(risk))
    lim["order"]["max_notional_frac_nav"] = 0.05
    lim["pod"].update(max_gross=1.0, allow_short=False)
    lim["firm"].update(max_gross=1.0, kill_drawdown=0.15, max_crypto_frac=0.50)
    lim["instruments"].update(allowed_kinds=["etf_ucits", "stock", "etc", "crypto"],
                              forbidden_kinds=["etf_us", "cfd", "option", "future", "forex_speculative"])
    yaml.safe_dump(lim, open(risk, "w"), allow_unicode=True, sort_keys=False)
    monkeypatch.setattr(settings, "RISK_FILE", str(risk))
    monkeypatch.setenv("GERVA_SHADOW", "0")              # niente download di dati dal battito nei test
    for k in [k for k in os.environ if k.endswith("_API_KEY")]:
        monkeypatch.delenv(k, raising=False)
    db.reset_connection_cache()
    # i test storici descrivono la societa' con i pod accesi; il comportamento a pod spenti ha i suoi test
    db.connect()
    for k, v in (("pods.enabled", "true"), ("pods.initial_capital_frac", "0.05")):
        db.ex("INSERT INTO settings(key,value,updated_ts,updated_by) VALUES(?,?,?,?)", (k, v, db.now_iso(), "test"))
    yield tmp_path
    db.reset_connection_cache()
