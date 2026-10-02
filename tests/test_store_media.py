import pytest
from housetracker.store import HouseStore
from housetracker.model import ValidationError


def _store(tmp_path):
    s = HouseStore(tmp_path / "ht.db")
    s.add_house({"address": "A"}, now="2026-09-13")
    return s


def test_media_table_created(tmp_path):
    s = HouseStore(tmp_path / "ht.db")
    assert "media" in s.table_names()


def test_add_and_list_media(tmp_path):
    s = _store(tmp_path)
    s.add_media({"house_id": "a", "kind": "photo",
                 "path": "data/houses/a/photos/1.jpg"}, now="2026-09-13")
    s.add_media({"house_id": "a", "kind": "pdf",
                 "path": "data/houses/a/pdf/salg.pdf"}, now="2026-09-13")
    media = s.list_media("a")
    assert [m.kind for m in media] == ["pdf", "photo"]  # ordered by kind ('pdf' < 'photo')
    assert media[1].path.endswith("1.jpg")
    assert media[0].source == "scrape"
    assert media[0].added_at == "2026-09-13"


def test_media_rejects_bad_kind(tmp_path):
    s = _store(tmp_path)
    with pytest.raises(ValidationError):
        s.add_media({"house_id": "a", "kind": "video", "path": "x"}, now="2026-09-13")


def test_media_ids_unique_per_house_kind(tmp_path):
    s = _store(tmp_path)
    a = s.add_media({"house_id": "a", "kind": "photo", "path": "p1"}, now="2026-09-13")
    b = s.add_media({"house_id": "a", "kind": "photo", "path": "p2"}, now="2026-09-13")
    assert a.id != b.id
