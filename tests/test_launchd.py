"""I servizi del Mac (launchd): i programmi sempre accesi riparono da soli, GERVA-Q gira lun-ven agli orari di sempre e solo in paper."""
import importlib.util
import os
import plistlib

spec = importlib.util.spec_from_file_location("installa_launchd", os.path.join(os.path.dirname(__file__), "..", "deploy", "mac", "installa_launchd.py"))
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)


def test_services_are_valid_and_keep_alive(tmp_path):
    L.install(dest=str(tmp_path))
    files = sorted(os.listdir(tmp_path))
    assert len(files) == 8 and all(f.startswith("com.gerva.") and f.endswith(".plist") for f in files)
    for f in files:
        d = plistlib.load(open(tmp_path / f, "rb"))
        assert d["Label"] == f[:-6] and d["ProgramArguments"]
        assert "WorkingDirectory" not in d and "StandardOutPath" not in d              # launchd non deve toccare Documenti (errore 78): ci entra bash
    sv = L.services()
    for k in ("telegram", "freedesk", "livenav", "portal", "caffeinate"):
        assert sv[k]["KeepAlive"] is True                                                           # se esce (anche per un aggiornamento), riparte
    assert sv["heartbeat"]["StartInterval"] == 900                                                  # il battito ogni 15 minuti


def test_gervaq_schedule_is_weekdays_paper_only():
    sv = L.services()
    ch, se = sv["gervaq-chiusura"], sv["gervaq-seduta"]
    assert {(x["Weekday"], x["Hour"], x["Minute"]) for x in ch["StartCalendarInterval"]} == {(d, 22, 35) for d in range(1, 6)}
    assert {(x["Hour"], x["Minute"]) for x in se["StartCalendarInterval"]} == {(15, 45), (17, 45), (19, 45), (21, 45)}
    cmd_ch, cmd_se = ch["ProgramArguments"][2], se["ProgramArguments"][2]
    assert "--no-refresh" in cmd_se and "--no-refresh" not in cmd_ch
    assert ch["EnvironmentVariables"]["GERVAQ_IB_PORT"] == "7497" and "--mode paper" in cmd_ch and "live.py" in cmd_ch    # solo paper, porta 7497


def test_programs_start_through_bash_which_enters_the_folder_and_writes_its_own_log():
    sv = L.services()
    for k in ("telegram", "freedesk", "livenav", "portal", "heartbeat", "gervaq-chiusura", "gervaq-seduta"):
        a = sv[k]["ProgramArguments"]
        assert a[:2] == ["/bin/bash", "-c"] and a[2].startswith("cd ") and ">>" in a[2] and "2>&1" in a[2]
    assert "firm.py telegram" in sv["telegram"]["ProgramArguments"][2]
    assert sv["caffeinate"]["ProgramArguments"][0] == "/usr/bin/caffeinate"


def test_probe_reads_both_folders_with_python_through_the_same_mechanism():
    p = L.sonda_plist()
    assert p["Label"] == "com.gerva.sonda" and p["ProgramArguments"][:2] == ["/bin/bash", "-c"]
    assert ".venv/bin/python" in p["ProgramArguments"][2] and "GERVA-Q" in p["ProgramArguments"][2] and L.SONDA_OUT in p["ProgramArguments"][2]
