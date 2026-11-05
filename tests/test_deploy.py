"""Regole del deploy che non devono mai regredire (si leggono i file, nessun Docker richiesto)."""
import os
import subprocess
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPOSE = yaml.safe_load(open(os.path.join(ROOT, "deploy", "docker-compose.yml")))
FIRM = ("gervaq", "heartbeat", "portal")


def test_nessuna_porta_su_internet():
    for name, svc in COMPOSE["services"].items():
        for p in svc.get("ports", []):
            assert str(p).startswith("127.0.0.1:"), f"{name}: porta {p} esposta oltre 127.0.0.1"


def test_container_della_societa_blindati():
    for name in FIRM:
        svc = COMPOSE["services"][name]
        assert svc.get("read_only") is True and svc.get("cap_drop") == ["ALL"], name
        assert "no-new-privileges:true" in svc.get("security_opt", []), name


def test_rete_dei_gateway_senza_internet_e_portale_isolato():
    assert COMPOSE["networks"]["ibnet"].get("internal") is True
    assert "ibnet" not in COMPOSE["services"]["portal"].get("networks", [])


def test_solo_paper():
    for name in ("ibgw-gervaq", "ibgw-firm"):
        assert COMPOSE["services"][name]["environment"]["TRADING_MODE"] == "paper"
    assert COMPOSE["services"]["gervaq"]["environment"]["GERVAQ_MODE"] == "paper"


def test_stato_mutabile_nel_volume_scrivibile():
    """Il codice nell'immagine e' in sola lettura: KILL, DB, limiti, profili devono stare in /data."""
    for name in ("heartbeat", "portal"):
        env = COMPOSE["services"][name]["environment"]
        for k in ("GERVA_VAR", "GERVA_AGENTS", "GERVA_RESEARCH", "GERVA_RISK_FILE", "GERVA_KILL_FILE"):
            assert str(env[k]).startswith("/data/"), f"{name}: {k}={env.get(k)}"
    out = subprocess.run([sys.executable, "-c", "from firm import paths; print(paths.KILL_FILE)"], cwd=ROOT,
                         env=dict(os.environ, GERVA_KILL_FILE="/data/var/KILL"), capture_output=True, text=True)
    assert out.stdout.strip() == "/data/var/KILL"


def test_segreti_fuori_da_git_e_dall_immagine():
    gi = open(os.path.join(ROOT, ".gitignore")).read().split()
    di = open(os.path.join(ROOT, ".dockerignore")).read().split()
    for pat in ("secrets/", ".env", "docs/FIRM_BRIEF.md", "_incoming/"):
        assert pat in gi, pat
    for pat in ("secrets/", ".env", "*.env", "var/", ".git"):
        assert pat in di, pat
    for f in os.listdir(os.path.join(ROOT, "deploy", "secrets.example")):
        for line in open(os.path.join(ROOT, "deploy", "secrets.example", f)):
            if "=" in line and not line.lstrip().startswith("#"):
                assert line.split("=", 1)[1].strip() == "", f"{f}: valore non vuoto in un esempio"
