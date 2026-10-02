import pytest
from housetracker.model import House, ValidationError

def test_house_roundtrip():
    h = House.from_dict({"address": "Vej 12", "price_dkk": 4_000_000, "size_m2": 100})
    assert h.address == "Vej 12"
    assert h.price_per_m2 == 40_000
    assert h.to_dict()["address"] == "Vej 12"

def test_house_requires_address():
    with pytest.raises(KeyError):
        House.from_dict({"price_dkk": 1})

def test_house_rejects_bad_status():
    with pytest.raises(ValidationError):
        House.from_dict({"address": "X", "status": "candidate"})

def test_house_rejects_negative_price():
    with pytest.raises(ValidationError):
        House.from_dict({"address": "X", "price_dkk": -5})

def test_price_per_m2_none_without_size():
    assert House.from_dict({"address": "X"}).price_per_m2 is None

def test_new_house_defaults_to_not_visited():
    h = House.from_dict({"address": "Vej 1"})
    assert h.status == "not_visited"

def test_not_visited_is_a_valid_status():
    h = House.from_dict({"address": "Vej 1", "status": "not_visited"})
    assert h.status == "not_visited"

def test_not_visited_to_visited_transition_accepted(tmp_path):
    from housetracker.store import HouseStore
    s = HouseStore(tmp_path / "ht.db")
    h = s.add_house({"address": "Vej 1"}, now="2026-09-23")
    assert h.status == "not_visited"
    updated = s.set_status(h.id, "visited", now="2026-09-23")
    assert updated.status == "visited"
    hist = [e["status"] for e in s.status_history(h.id)]
    assert hist == ["not_visited", "visited"]
