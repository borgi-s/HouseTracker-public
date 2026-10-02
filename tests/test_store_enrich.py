import pytest

from housetracker.store import HouseStore


def _store(tmp_path):
    return HouseStore(tmp_path / "data" / "ht.db")


def test_anchor_and_commute_tables_exist(tmp_path):
    names = _store(tmp_path).table_names()
    assert "anchor" in names and "commute" in names


def test_a_new_db_has_no_anchors(tmp_path):
    assert _store(tmp_path).list_anchors() == []


def test_add_get_list_anchor(tmp_path):
    s = _store(tmp_path)
    a = s.add_anchor({"label": "Work", "address": "Rådhuspladsen 1",
                      "lat": 55.6759, "lon": 12.5655, "kind": "fixed"})
    assert a.id == "work"
    assert s.get_anchor("work").label == "Work"
    fixed = s.list_anchors(kind="fixed")
    assert {x.id for x in fixed} == {"work"}


def test_upsert_commute_roundtrip_and_replace(tmp_path):
    s = _store(tmp_path)
    s.add_house({"address": "Nyvej 2"}, now="2026-09-18")
    hid = s.list_houses()[0].id
    s.upsert_commute(hid, "work", "driving-car", 12.5, 8400.0, now="2026-09-18")
    got = s.list_commutes(hid)
    assert len(got) == 1
    assert got[0].mode == "driving-car"
    assert got[0].minutes == 12.5
    assert got[0].distance_m == 8400.0
    # same (house, anchor, mode) replaces, not duplicates
    s.upsert_commute(hid, "work", "driving-car", 15.0, 9000.0, now="2026-09-20")
    got = s.list_commutes(hid)
    assert len(got) == 1 and got[0].minutes == 15.0


def test_update_house_location(tmp_path):
    s = _store(tmp_path)
    s.add_house({"address": "Nyvej 2"}, now="2026-09-18")
    hid = s.list_houses()[0].id
    s.update_house_location(hid, lat=55.79, lon=12.52, kommune="Lyngby-Taarbæk",
                            postal_code="2800", city="Kongens Lyngby", now="2026-09-19")
    h = s.get_house(hid)
    assert h.lat == 55.79 and h.lon == 12.52
    assert h.kommune == "Lyngby-Taarbæk"
    assert h.postal_code == "2800" and h.city == "Kongens Lyngby"
    assert h.updated_at == "2026-09-19"


def test_bad_anchor_kind_rejected(tmp_path):
    from housetracker.model import Anchor, ValidationError
    with pytest.raises(ValidationError):
        Anchor.from_dict({"label": "x", "kind": "bogus"})
