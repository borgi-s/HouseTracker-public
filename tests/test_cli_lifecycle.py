# tests/test_cli_lifecycle.py
import io

from housetracker.cli import main
from housetracker.store import HouseStore


class FakeProber:
    def __init__(self, *a, **k):
        pass

    def probe(self, url):
        return (404, url, "")           # -> classify 'gone' -> mark sold


class FakeBoligsiden:
    def __init__(self, *a, **k):
        pass

    def address(self, address_id):
        return {"cases": [], "registrations": [
            {"date": "2026-03-14", "amount": 5250000, "type": "normal"}]}


class FakeGeocoder:
    def __init__(self, *a, **k):
        pass

    def geocode(self, query):
        return {"address_id": "abc"}


def run(db, *args):
    buf = io.StringIO()
    return main(["--db", str(db), *args], buf), buf.getvalue()


def _add(db, url="https://x.dk/1"):
    run(db, "add-house", "--address", "Nyvej 2, 2800")
    s = HouseStore(db)
    hid = s.list_houses()[0].id
    s.conn.execute("UPDATE house SET listing_url = ?, created_at = '2026-01-01' WHERE id = ?",
                   (url, hid))
    s.conn.commit()
    return hid


def test_status_set_and_history(tmp_path):
    db = tmp_path / "data" / "ht.db"
    hid = _add(db)
    code, out = run(db, "status", "--house", hid, "--set", "shortlist")
    assert code == 0 and "shortlist" in out
    code, out = run(db, "status", "--house", hid)
    assert code == 0
    assert "not_visited" in out and "shortlist" in out


def test_set_sold_manual_override(tmp_path):
    db = tmp_path / "data" / "ht.db"
    hid = _add(db)
    code, out = run(db, "set-sold", "--house", hid, "--price", "4995000", "--date",
                    "2026-02-01")
    assert code == 0
    g = HouseStore(db).get_house(hid)
    assert g.status == "sold" and g.sold_price_dkk == 4995000.0 and g.sold_date == "2026-02-01"
    code, out = run(db, "show", "--house", hid)
    assert "sold: 4995000 DKK on 2026-02-01" in out


def test_lifecycle_marks_sold_and_prices(tmp_path, monkeypatch):
    monkeypatch.setattr("housetracker.cli.HttpProber", FakeProber)
    monkeypatch.setattr("housetracker.cli.BoligsidenClient", FakeBoligsiden)
    monkeypatch.setattr("housetracker.cli.AddressGeocoder", FakeGeocoder)
    db = tmp_path / "data" / "ht.db"
    hid = _add(db)
    code, out = run(db, "lifecycle")
    assert code == 0
    assert "marked_sold=1" in out and "priced=1" in out and "repriced=0" in out
    g = HouseStore(db).get_house(hid)
    assert g.status == "sold" and g.sold_price_dkk == 5250000.0


def test_lifecycle_no_boligsiden_skips_pricing(tmp_path, monkeypatch):
    monkeypatch.setattr("housetracker.cli.HttpProber", FakeProber)
    monkeypatch.setattr("housetracker.cli.BoligsidenClient", FakeBoligsiden)
    monkeypatch.setattr("housetracker.cli.AddressGeocoder", FakeGeocoder)
    db = tmp_path / "data" / "ht.db"
    hid = _add(db)
    code, out = run(db, "lifecycle", "--no-boligsiden")
    assert code == 0 and "priced=0" in out
    assert HouseStore(db).get_house(hid).sold_price_dkk is None    # sold, but unpriced


def test_lifecycle_reports_new_open_houses(tmp_path, monkeypatch):
    monkeypatch.setattr("housetracker.cli.HttpProber", FakeProber)
    monkeypatch.setattr("housetracker.cli.BoligsidenClient", FakeBoligsiden)
    monkeypatch.setattr("housetracker.cli.AddressGeocoder", FakeGeocoder)
    db = tmp_path / "data" / "ht.db"
    _add(db)
    code, out = run(db, "lifecycle")
    assert code == 0 and "open_new=0" in out
