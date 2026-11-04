"""Finestra di rilascio: solo domenica, solo con la scelta di Andrea, backup e changelog automatici."""
import datetime as dt
import os
import shutil
import subprocess

import pytest

SUN = dt.datetime(2026, 11, 8, 10, tzinfo=dt.timezone.utc)
WED = dt.datetime(2026, 11, 4, 10, tzinfo=dt.timezone.utc)
SNAP = os.path.join(os.path.dirname(__file__), "..", "_incoming", "quant_engine")
REPO_RELEASES = os.path.join(os.path.dirname(__file__), "..", "research", "releases")


@pytest.mark.skipif(not os.path.isdir(SNAP) or not shutil.which("patch"), reason="serve lo snapshot di GERVA-Q")
def test_release_applies_only_on_sunday_with_backup_and_changelog(firm_env, tmp_path):
    from firm import release, settings as S
    gq = tmp_path / "gq"
    shutil.copytree(SNAP, gq)
    cap = S.AndreaCapability(S.ensure_token())
    with pytest.raises(PermissionError):
        release.apply("2026-11-08", cap=None, now=SUN, gerva_q=str(gq))
    assert not release.apply("2026-11-08", cap, now=WED, gerva_q=str(gq))["ok"]
    # non tocca il file APPLIED vero del repository: si lavora su una copia della cartella del rilascio
    rel_copy = tmp_path / "releases"
    shutil.copytree(REPO_RELEASES, rel_copy)
    old = release.RELEASES
    release.RELEASES = str(rel_copy)
    try:
        r = release.apply("2026-11-08", cap, now=SUN, gerva_q=str(gq))
    finally:
        release.RELEASES = old
    assert r["ok"], r
    assert "hashlib.sha256" in open(gq / "engine.py").read()
    assert "abs(hash(" in open(gq / "backups" / "pre-2026-11-08" / "engine.py").read()
    assert "2026-11-08" in open(gq / "REGOLE_SFIDA.md").read().splitlines()[-1]
    for f in ("engine.py", "lab.py", "v3_validate.py", "crypto_live.py"):
        subprocess.run(["python", "-m", "py_compile", str(gq / f)], check=True)
