# tests/test_store_price.py
import pytest

from housetracker.model import ValidationError
from housetracker.store import HouseStore


def _store(tmp_path):
    return HouseStore(tmp_path / "data" / "ht.db")


def _house(s, **extra):
    return s.add_house({"address": "Nyvej 2", "price_dkk": 5_000_000, **extra},
                       now="2026-09-22")


ADDED = {"price_dkk": 5_000_000.0, "at": "2026-09-22", "source": "added"}


def test_add_house_starts_the_price_history(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    assert s.price_events(h.id) == [ADDED]


def test_an_unpriced_house_has_no_history(tmp_path):
    s = _store(tmp_path)
    h = s.add_house({"address": "Nyvej 2"}, now="2026-09-22")
    assert s.price_events(h.id) == []
    assert s.original_price(h.id) is None


def test_houses_from_before_price_history_are_backfilled_once(tmp_path):
    db = tmp_path / "data" / "ht.db"
    s = HouseStore(db)
    h = _house(s)
    s.conn.execute("DELETE FROM price_event")      # as if added before the table existed
    s.conn.commit()
    HouseStore(db)
    HouseStore(db)                                 # two restarts: still one event
    assert HouseStore(db).price_events(h.id) == [ADDED]


def test_record_price_logs_it_and_makes_it_current(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    s.record_price(h.id, 4_800_000.0, "boligsiden", now="2026-09-26")
    assert s.get_house(h.id).price_dkk == 4_800_000.0
    assert s.price_events(h.id) == [
        ADDED, {"price_dkk": 4_800_000.0, "at": "2026-09-26", "source": "boligsiden"}]


def test_a_hand_edit_is_not_a_price_event(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    s.update_house(h.id, {"price_dkk": 5_100_000}, now="2026-09-23")
    assert s.price_events(h.id) == [ADDED]


def test_save_listing_changes_only_the_given_fields(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    assert s.get_listing(h.id) is None
    sales = [{"date": "2021-09-08", "price_dkk": 3_000_000.0, "type": "normal"}]
    s.save_listing(h.id, {"address_id": "abc", "listed_price_dkk": 5_200_000.0,
                          "sales": sales})
    s.save_listing(h.id, {"checked_at": "2026-09-26"})
    s.save_listing(h.id, {})                       # no-op
    got = s.get_listing(h.id)
    assert got["address_id"] == "abc" and got["listed_price_dkk"] == 5_200_000.0
    assert got["checked_at"] == "2026-09-26" and got["sales"] == sales
    assert got["listed_date"] is None


def test_save_listing_rejects_unknown_fields(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    with pytest.raises(ValidationError):
        s.save_listing(h.id, {"price_dkk": 1})


def test_original_price_prefers_the_first_asking_price(tmp_path):
    s = _store(tmp_path)
    h = _house(s)
    assert s.original_price(h.id) == 5_000_000.0          # first price we saw
    s.save_listing(h.id, {"listed_price_dkk": 5_200_000.0})
    assert s.original_price(h.id) == 5_200_000.0          # the agent's first price
