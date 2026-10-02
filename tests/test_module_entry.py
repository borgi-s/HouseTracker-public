# tests/test_module_entry.py
import subprocess
import sys


def test_python_m_housetracker_lifecycle_runs_on_empty_db(tmp_path):
    """The systemd ExecStart shape: `python -m housetracker --db <db> lifecycle
    --no-boligsiden` on an empty DB does no network and exits 0 — proves the module entry."""
    db = tmp_path / "data" / "ht.db"
    proc = subprocess.run(
        [sys.executable, "-m", "housetracker", "--db", str(db),
         "lifecycle", "--no-boligsiden"],
        capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "checked=0" in proc.stdout
