import pytest

from housetracker.model import ValidationError
from housetracker.store import HouseStore


def _store(tmp_path):
    s = HouseStore(tmp_path / "ht.db")
    s.add_house({"address": "Nyvej 2, 2800"}, now="2026-09-20")
    return s, s.list_houses()[0].id


def test_tables_exist(tmp_path):
    s, _ = _store(tmp_path)
    assert {"note", "tag"} <= s.table_names()


def test_note_roundtrip_keeps_author_and_order(tmp_path):
    s, hid = _store(tmp_path)
    a = s.add_note(hid, "alex", "Kitchen is dark", now="2026-09-20")
    b = s.add_note(hid, None, "Shared: offer deadline Friday", now="2026-09-21")
    assert a["id"] != b["id"]
    got = s.list_notes(hid)
    assert [n["body"] for n in got] == ["Kitchen is dark",
                                        "Shared: offer deadline Friday"]
    assert got[0]["person_id"] == "alex"
    assert got[1]["person_id"] is None          # nullable = shared
    assert got[0]["created_at"] == "2026-09-20"


def test_empty_note_body_is_rejected(tmp_path):
    s, hid = _store(tmp_path)
    with pytest.raises(ValidationError):
        s.add_note(hid, "alex", "   ", now="2026-09-20")


def test_tag_add_list_delete(tmp_path):
    s, hid = _store(tmp_path)
    t = s.add_tag(hid, "alex", "needs-new-roof")
    s.add_tag(hid, None, "walkable")
    assert {x["label"] for x in s.list_tags(hid)} == {"needs-new-roof", "walkable"}
    assert s.delete_tag(t["id"]) is True
    assert [x["label"] for x in s.list_tags(hid)] == ["walkable"]
    assert s.delete_tag(999999) is False        # already gone


def test_empty_tag_label_is_rejected(tmp_path):
    s, hid = _store(tmp_path)
    with pytest.raises(ValidationError):
        s.add_tag(hid, "alex", "")


def test_notes_and_tags_are_scoped_to_their_house(tmp_path):
    s, hid = _store(tmp_path)
    s.add_house({"address": "Andenvej 9, 2800"}, now="2026-09-20")
    other = [h.id for h in s.list_houses() if h.id != hid][0]
    s.add_note(hid, "alex", "only here", now="2026-09-20")
    s.add_tag(hid, "alex", "only-here")
    assert s.list_notes(other) == [] and s.list_tags(other) == []

def test_delete_note(tmp_path):
    s = HouseStore(tmp_path / "ht.db")
    n = s.add_note("h1", "alex", "Kitchen is dark", now="2026-09-21")
    assert s.delete_note(n["id"]) is True
    assert s.list_notes("h1") == []
    assert s.delete_note(n["id"]) is False
