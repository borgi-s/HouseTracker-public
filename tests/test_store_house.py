import pytest
from housetracker.store import HouseStore
from housetracker.model import DuplicateHouse, ValidationError

def _store(tmp_path):
    return HouseStore(tmp_path / "ht.db")

def test_add_and_get(tmp_path):
    s = _store(tmp_path)
    h = s.add_house({"address": "Skovvej 3", "price_dkk": 5_000_000}, now="2026-09-13")
    assert h.id == "skovvej-3"
    got = s.get_house("skovvej-3")
    assert got.address == "Skovvej 3"
    assert got.status == "not_visited"
    assert got.created_at == "2026-09-13"

def test_add_logs_initial_status_event(tmp_path):
    s = _store(tmp_path)
    s.add_house({"address": "A"}, now="2026-09-13")
    hist = s.status_history(s.list_houses()[0].id)
    assert [e["status"] for e in hist] == ["not_visited"]

def test_set_status_updates_and_logs(tmp_path):
    s = _store(tmp_path)
    h = s.add_house({"address": "A"}, now="2026-09-13")
    s.set_status(h.id, "shortlist", now="2026-09-14")
    assert s.get_house(h.id).status == "shortlist"
    assert [e["status"] for e in s.status_history(h.id)] == ["not_visited", "shortlist"]

def test_set_status_rejects_bad_status(tmp_path):
    s = _store(tmp_path)
    h = s.add_house({"address": "A"}, now="2026-09-13")
    with pytest.raises(ValidationError):
        s.set_status(h.id, "sold-ish", now="2026-09-14")

def test_the_same_address_in_another_postal_code_is_another_house(tmp_path):
    s = _store(tmp_path)
    a = s.add_house({"address": "Same Vej 1", "postal_code": "2800"}, now="2026-09-13")
    b = s.add_house({"address": "Same Vej 1", "postal_code": "2830"}, now="2026-09-13")
    assert (a.id, b.id) == ("same-vej-1", "same-vej-1-2")


def test_an_address_we_track_is_refused_naming_the_tracked_house(tmp_path):
    s = _store(tmp_path)
    a = s.add_house({"address": "Åbakken 245", "postal_code": "2830"}, now="2026-09-26")
    s.set_status(a.id, "rejected", now="2026-09-27")
    with pytest.raises(DuplicateHouse) as e:
        s.add_house({"address": "åbakken  245", "postal_code": "2830"}, now="2026-10-01")
    assert (e.value.house.id, e.value.house.status) == (a.id, "rejected")
    with pytest.raises(DuplicateHouse):           # no postal code: the address alone decides
        s.add_house({"address": "Åbakken 245"}, now="2026-10-01")
    assert len(s.list_houses()) == 1


def test_a_listing_link_we_track_is_refused_whatever_its_tracking_tail(tmp_path):
    s = _store(tmp_path)
    s.add_house({"address": "Birkevang 58", "listing_url":
                 "https://www.nybolig.dk/raekkehus/2830/birkevang/n1?utm_source=boliga"},
                now="2026-09-30")
    with pytest.raises(DuplicateHouse):
        s.add_house({"address": "Birkevang 58, 2830 Virum",
                     "listing_url": "https://nybolig.dk/raekkehus/2830/birkevang/n1/"},
                    now="2026-10-01")


def test_update_house_changes_only_the_given_fields(tmp_path):
    s = HouseStore(tmp_path / "ht.db")
    h = s.add_house({"address": "Nyvej 2", "price_dkk": 5_000_000.0,
                     "size_m2": 100.0}, now="2026-09-20")
    u = s.update_house(h.id, {"price_dkk": 4_750_000.0, "energy_label": "C"},
                       now="2026-09-21")
    assert u.price_dkk == 4_750_000.0 and u.energy_label == "C"
    assert u.size_m2 == 100.0 and u.status == "not_visited"
    assert (u.created_at, u.updated_at) == ("2026-09-20", "2026-09-21")
    assert s.status_history(h.id) == [{"status": "not_visited", "at": "2026-09-20"}]


def test_update_house_validates_and_refuses_non_editable_fields(tmp_path):
    s = HouseStore(tmp_path / "ht.db")
    h = s.add_house({"address": "Nyvej 2"}, now="2026-09-20")
    with pytest.raises(ValidationError):
        s.update_house(h.id, {"price_dkk": -1.0}, now="2026-09-21")
    with pytest.raises(ValidationError):
        s.update_house(h.id, {"status": "sold"}, now="2026-09-21")   # has its own route
    with pytest.raises(ValidationError):
        s.update_house("nope", {"city": "X"}, now="2026-09-21")
    assert s.get_house(h.id).price_dkk is None

def test_a_store_opened_on_one_thread_works_on_another(tmp_path):
    # FastAPI enters a sync dependency and runs the route on different threadpool
    # threads; under uvicorn every request crossed threads and failed.
    import threading
    s = _store(tmp_path)
    errors = []
    def use():
        try:
            s.add_house({"address": "Trådvej 1"}, now="2026-09-22")
        except Exception as e:
            errors.append(e)
    t = threading.Thread(target=use)
    t.start()
    t.join()
    assert errors == []
    assert [h.address for h in s.list_houses()] == ["Trådvej 1"]
