"""Settings page writes: rename/remove people and criteria, remove anchors, the
notification switches. A removal takes every row that hangs off what it removes."""
from housetracker.store import HouseStore


def _store(tmp_path):
    s = HouseStore(tmp_path / "ht.db")
    s.add_house({"address": "Nyvej 2"}, now="2026-10-02")
    return s, s.list_houses()[0].id


def test_rename_person(tmp_path):
    s, _ = _store(tmp_path)
    p = s.add_person("Alx")
    assert s.rename_person(p.id, "Alex").name == "Alex"
    assert [x.name for x in s.list_persons()] == ["Alex"]
    assert s.list_persons()[0].id == p.id          # the id (and the cookie) stays


def test_delete_person_takes_their_scores_and_private_notes_and_tags(tmp_path):
    s, hid = _store(tmp_path)
    a, b = s.add_person("Alex"), s.add_person("Sam")
    c = s.add_criterion({"key": "light", "label": "Light", "kind": "subjective"}, now="x")
    for p in (a, b):
        s.upsert_score(hid, p.id, c.id, 4, now="x")
        s.add_note(hid, p.id, f"{p.name}'s note", now="x")
        s.add_tag(hid, p.id, p.name)
    s.add_note(hid, None, "shared", now="x")
    assert s.delete_person(a.id) is True
    assert [p.id for p in s.list_persons()] == [b.id]
    assert s.get_scores(hid) == {(b.id, c.id): 4.0}
    assert sorted(n["body"] for n in s.list_notes(hid)) == ["Sam's note", "shared"]
    assert [t["label"] for t in s.list_tags(hid)] == ["Sam"]
    assert s.delete_person(a.id) is False


def test_delete_criterion_takes_its_scores(tmp_path):
    s, hid = _store(tmp_path)
    p = s.add_person("Alex")
    c1 = s.add_criterion({"key": "light", "label": "Light", "kind": "subjective"}, now="x")
    c2 = s.add_criterion({"key": "noise", "label": "Noise", "kind": "subjective"}, now="x")
    s.upsert_score(hid, p.id, c1.id, 3, now="x")
    s.upsert_score(hid, p.id, c2.id, 5, now="x")
    assert s.delete_criterion(c1.id) is True
    assert [c.id for c in s.list_criteria(active_only=False)] == [c2.id]
    assert s.get_scores(hid) == {(p.id, c2.id): 5.0}


def test_delete_anchor_takes_its_commutes(tmp_path):
    s, hid = _store(tmp_path)
    a = s.add_anchor({"label": "Work", "lat": 55.7, "lon": 12.5})
    s.upsert_commute(hid, a.id, "car", 20, 9000, now="x")
    s.upsert_commute(hid, "school", "bike", 5, 1000, now="x")
    assert s.delete_anchor(a.id) is True
    assert s.list_anchors() == []
    assert [c.anchor_ref for c in s.list_commutes(hid)] == ["school"]


def test_settings_default_then_persist(tmp_path):
    s, _ = _store(tmp_path)
    assert s.get_setting("notify_price_drops", "1") == "1"
    s.set_setting("notify_price_drops", "0")
    s.set_setting("notify_price_drops", "0")       # upsert, not a second row
    assert HouseStore(tmp_path / "ht.db").get_setting("notify_price_drops", "1") == "0"


def test_update_anchor_new_place_drops_old_commutes(tmp_path):
    s, hid = _store(tmp_path)
    a = s.add_anchor({"label": "Work", "address": "A 1", "lat": 55.7, "lon": 12.5})
    s.upsert_commute(hid, a.id, "car", 20, 9000, now="x")
    b = s.update_anchor(a.id, {"label": "Office"})
    assert (b.label, b.lat) == ("Office", 55.7) and len(s.list_commutes(hid)) == 1
    b = s.update_anchor(a.id, {"address": "B 2", "lat": 56.0, "lon": 10.0})
    assert (b.id, b.label, b.address, b.lat) == (a.id, "Office", "B 2", 56.0)
    assert s.list_commutes(hid) == []
