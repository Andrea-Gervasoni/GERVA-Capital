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


@pytest.mark.skipif(not os.path.isdir(SNAP), reason="serve lo snapshot di GERVA-Q")
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


def test_diff_applier_is_strict(tmp_path):
    from firm.release import apply_unified_diff
    (tmp_path / "a.py").write_text("x = 1\ny = 2\nz = 3\n")
    patch = "--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,3 @@\n x = 1\n-y = 2\n+y = 20\n z = 3\n"
    apply_unified_diff(patch, str(tmp_path))
    assert (tmp_path / "a.py").read_text() == "x = 1\ny = 20\nz = 3\n"
    with pytest.raises(ValueError):                        # il contesto non coincide piu': niente scrittura
        apply_unified_diff(patch, str(tmp_path))


@pytest.mark.skipif(not os.path.isdir(SNAP), reason="serve lo snapshot di GERVA-Q")
def test_release_patches_apply_in_sequence_and_longterm_matches_config(tmp_path):
    """Le patch del rilascio si applicano in ordine su una copia di GERVA-Q; la quota di lungo periodo di config.py
    coincide con config/longterm.yaml della societa' (stessi titoli, stesso 3% + 2%)."""
    import glob
    import shutil
    import subprocess
    import sys
    import yaml
    from firm.release import apply_unified_diff
    rel = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research", "releases", "2026-11-08")
    patches = sorted(glob.glob(os.path.join(rel, "*.patch")))
    if len(patches) < 2:
        pytest.skip("patch del rilascio non presenti (sono fuori da git)")
    dst = tmp_path / "gq"
    shutil.copytree(SNAP, dst)
    for p in patches:
        apply_unified_diff(open(p).read(), str(dst))
    out = subprocess.run([sys.executable, "-c", "import config as C, json; print(json.dumps(C.LONGTERM))"],
                         cwd=dst, capture_output=True, text=True)
    lt = __import__("json").loads(out.stdout)
    cfg = yaml.safe_load(open(os.path.join(os.path.dirname(rel), "..", "..", "config", "longterm.yaml")))
    core, expl = set(cfg["titoli"]), set(cfg["esplorativo"]["titoli"])
    assert set(lt) == core | expl
    assert sum(lt[s] for s in core) == pytest.approx(cfg["quota_nav"])
    assert sum(lt[s] for s in expl) == pytest.approx(cfg["esplorativo"]["quota_nav"])
