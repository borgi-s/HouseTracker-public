from pathlib import Path

from housetracker.api.app import create_app


def test_health_reports_the_house_count(api):
    r = api.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "houses": 0}


def test_data_dir_defaults_to_the_db_parent(tmp_path):
    app = create_app(tmp_path / "data" / "ht.db")
    assert Path(app.state.data_dir) == (tmp_path / "data").resolve()


def test_each_request_gets_its_own_connection(api):
    # Two requests in a row must both work: a store leaked across threads would raise
    # "SQLite objects created in a thread can only be used in that same thread".
    assert api.get("/api/health").status_code == 200
    assert api.get("/api/health").status_code == 200
