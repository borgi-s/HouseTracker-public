import io
from housetracker.cli import main

def run(db, *args):
    buf = io.StringIO()
    code = main(["--db", str(db), *args], buf)
    return code, buf.getvalue()

def test_end_to_end_rank(tmp_path):
    db = tmp_path / "ht.db"
    run(db, "add-person", "Alex")
    run(db, "add-criterion", "--key", "light", "--label", "Light", "--kind", "subjective")
    run(db, "add-house", "--address", "Good Vej 1")
    run(db, "add-house", "--address", "Meh Vej 2")
    run(db, "score", "--house", "good-vej-1", "--person", "alex", "--criterion", "light", "--value", "5")
    run(db, "score", "--house", "meh-vej-2", "--person", "alex", "--criterion", "light", "--value", "2")
    code, out = run(db, "rank", "--person", "alex")
    assert code == 0
    lines = [l for l in out.splitlines() if l.strip()]
    assert lines[0].startswith("good-vej-1")
    assert lines[1].startswith("meh-vej-2")

def test_show_reports_house(tmp_path):
    db = tmp_path / "ht.db"
    run(db, "add-house", "--address", "Sol Vej 9", "--price", "4000000", "--size", "100")
    code, out = run(db, "show", "--house", "sol-vej-9")
    assert code == 0
    assert "Sol Vej 9" in out
    assert "40000" in out  # price_per_m2

def test_delete_house(tmp_path):
    db = tmp_path / "ht.db"
    run(db, "add-house", "--address", "Sol Vej 9")
    (tmp_path / "houses" / "sol-vej-9").mkdir(parents=True)
    assert run(db, "delete-house", "--house", "sol-vej-9") == (0, "deleted sol-vej-9\n")
    assert not (tmp_path / "houses" / "sol-vej-9").exists()
    assert run(db, "delete-house", "--house", "sol-vej-9")[0] == 1
