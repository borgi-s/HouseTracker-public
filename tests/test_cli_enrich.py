# tests/test_cli_enrich.py
import io

from housetracker.cli import main
from housetracker.store import HouseStore

LOC = {"lat": 55.7861, "lon": 12.5234, "postal_code": "2800",
       "city": "Kongens Lyngby", "kommune": "Lyngby-Taarbæk", "kommunekode": "0173"}


class FakeGeocoder:
    def __init__(self, *a, **k):
        pass

    def geocode(self, address):
        return LOC


class FakeRouter:
    def __init__(self, *a, **k):
        pass

    def route(self, start, end, mode):
        return (10.0, 5000.0)


def run(db, *args):
    buf = io.StringIO()
    return main(["--db", str(db), *args], buf), buf.getvalue()


def _add(db):
    run(db, "add-house", "--address", "Nyvej 2, 2800")
    s = HouseStore(db)
    s.add_anchor({"label": "Work", "lat": 55.7, "lon": 12.5, "kind": "fixed"})
    return s.list_houses()[0].id


def test_enrich_geocodes_and_routes(tmp_path, monkeypatch):
    monkeypatch.setattr("housetracker.cli.AddressGeocoder", FakeGeocoder)
    monkeypatch.setattr("housetracker.cli.ORSRouter", FakeRouter)
    monkeypatch.setenv("HT_ORS_KEY", "test-key")
    db = tmp_path / "data" / "ht.db"
    hid = _add(db)
    code, out = run(db, "enrich", "--house", hid)
    assert code == 0
    store = HouseStore(db)
    assert store.get_house(hid).lat == 55.7861
    assert len(store.list_commutes(hid)) == 3          # work x 3 modes


def test_enrich_no_key_geocodes_only(tmp_path, monkeypatch):
    monkeypatch.setattr("housetracker.cli.AddressGeocoder", FakeGeocoder)
    monkeypatch.setattr("housetracker.cli.ORSRouter", FakeRouter)
    monkeypatch.delenv("HT_ORS_KEY", raising=False)
    db = tmp_path / "data" / "ht.db"
    hid = _add(db)
    code, out = run(db, "enrich", "--house", hid)
    assert code == 0
    store = HouseStore(db)
    assert store.get_house(hid).lat == 55.7861         # geocoded
    assert store.list_commutes(hid) == []              # no key -> no routing


def test_show_prints_commute_and_school_map(tmp_path, monkeypatch):
    monkeypatch.setattr("housetracker.cli.AddressGeocoder", FakeGeocoder)
    monkeypatch.setattr("housetracker.cli.ORSRouter", FakeRouter)
    monkeypatch.setenv("HT_ORS_KEY", "test-key")
    db = tmp_path / "data" / "ht.db"
    hid = _add(db)
    run(db, "enrich", "--house", hid)
    code, out = run(db, "show", "--house", hid)
    assert code == 0
    assert "driving-car" in out
    assert "geofa-kort.geodanmark.dk" in out
